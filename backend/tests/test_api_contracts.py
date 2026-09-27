"""
test_api_contracts.py — surface S3 (API contracts).

Charter invariants A1 (shape stability), A2 (validation returns 4xx with a
documented code, never 5xx) and A3 (/api/v1 mirror parity).

Every request runs against the in-process ASGI app with the stub LLM; no
socket leaves the machine (conftest blocks non-local connects outright).
"""

import base64
import json

import pytest

# A 1x1 transparent PNG — passes the magic-byte check in utils/attachments.py.
PNG_1PX = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)).decode()

DEMO_QUESTION = "What is the maximum bond a landlord can require?"


def sse_events(body: str):
    """Parse an SSE body into a list of decoded `data:` payloads."""
    events = []
    for block in body.strip().split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


# --- /health -----------------------------------------------------------------

def test_health_shape(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "status", "embeddings_loaded", "model_loaded", "anthropic_ready",
        "chunks", "analytics_failures", "has_failures",
    }
    assert body["status"] == "healthy"
    assert body["embeddings_loaded"] is True
    assert body["model_loaded"] is True
    assert body["anthropic_ready"] is True
    assert isinstance(body["chunks"], int) and body["chunks"] > 0


def test_root_shape(client):
    body = client.get("/").json()
    assert set(body) == {"name", "version", "status", "chunks_loaded"}


def test_security_headers_present(client):
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in headers


# --- /acts -------------------------------------------------------------------

def test_acts_shape(client):
    response = client.get("/acts")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"acts"}
    assert body["acts"]
    for act in body["acts"]:
        assert set(act) == {"short_name", "title", "year", "topics", "url"}
        assert isinstance(act["year"], int)


# --- /search -----------------------------------------------------------------

def test_search_shape(client):
    response = client.get("/search", params={"q": DEMO_QUESTION, "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"query", "results"}
    assert body["query"] == DEMO_QUESTION
    assert 0 < len(body["results"]) <= 5
    for r in body["results"]:
        assert set(r) == {"act_title", "section_number", "section_heading",
                          "text", "score", "url"}
        assert isinstance(r["score"], float)


def test_search_results_unique(client):
    """A1 + R1 at the endpoint boundary."""
    body = client.get("/search", params={"q": "privacy breach", "limit": 10}).json()
    keys = [(r["act_title"], r["section_number"], r["text"]) for r in body["results"]]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("params,reason", [
    ({}, "q is required"),
    ({"q": ""}, "q below min_length"),
    ({"q": "x" * 1001}, "q above max_length"),
    ({"q": "bond", "limit": 0}, "limit below minimum"),
    ({"q": "bond", "limit": 21}, "limit above maximum"),
    ({"q": "bond", "limit": "many"}, "limit not an int"),
])
def test_search_validation_is_4xx(client, params, reason):
    response = client.get("/search", params=params)
    assert 400 <= response.status_code < 500, f"{reason}: got {response.status_code}"
    assert response.status_code != 500


# --- /chat -------------------------------------------------------------------

def test_chat_shape_stubbed(client, app_module):
    response = client.post("/chat", json={"message": DEMO_QUESTION,
                                          "session_id": "test-chat-shape"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"response", "sources", "disclaimer"}
    assert body["response"] == app_module.STUB_RESPONSE
    assert body["disclaimer"] == app_module.DISCLAIMER
    assert 0 < len(body["sources"]) <= 3
    for source in body["sources"]:
        assert set(source) == {"act_title", "section_number", "section_heading",
                               "url", "excerpt", "score"}


def test_chat_sources_are_distinct_sections(client):
    """The demo-visible symptom: /chat must not answer from a single source
    just because the corpus repeats it."""
    body = client.post("/chat", json={"message": DEMO_QUESTION,
                                      "session_id": "test-chat-distinct"}).json()
    keys = [(s["act_title"], s["section_number"]) for s in body["sources"]]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 2, "expected more than one distinct source for a core demo question"


def test_chat_casual_message_skips_retrieval(client):
    body = client.post("/chat", json={"message": "hey there, thanks!",
                                      "session_id": "test-casual"}).json()
    assert body["sources"] == []


def test_chat_stores_history(client, app_module):
    client.post("/chat", json={"message": DEMO_QUESTION, "session_id": "test-history"})
    history = app_module.conversation_history["test-history"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["content"] == app_module.STUB_RESPONSE


def test_chat_accepts_valid_png_attachment(client):
    response = client.post("/chat", json={
        "message": "What does this say?",
        "session_id": "test-attach",
        "attachments": [{"filename": "a.png", "content_type": "image/png", "data": PNG_1PX}],
    })
    assert response.status_code == 200


# --- A2 validation -----------------------------------------------------------

def test_empty_message_returns_documented_code(client):
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "EMPTY_MESSAGE"
    assert detail["error"]


def test_missing_message_and_attachments(client):
    response = client.post("/chat", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "EMPTY_MESSAGE"


def test_oversize_message_is_4xx(client):
    response = client.post("/chat", json={"message": "x" * 5001})
    assert response.status_code == 422
    assert response.status_code != 500


def test_too_many_attachments_is_4xx(client):
    attachment = {"filename": "a.png", "content_type": "image/png", "data": PNG_1PX}
    response = client.post("/chat", json={"message": "hi", "attachments": [attachment] * 4})
    assert response.status_code == 422


def test_disallowed_content_type_is_4xx(client):
    response = client.post("/chat", json={
        "message": "check this",
        "attachments": [{"filename": "a.exe", "content_type": "application/x-msdownload",
                         "data": PNG_1PX}],
    })
    assert response.status_code == 422


def test_content_type_mismatch_is_400_not_500(client):
    """Declared PNG, actually a PDF header — caught by validate_attachment."""
    fake_pdf = base64.b64encode(b"%PDF-1.4 not really a png").decode()
    response = client.post("/chat", json={
        "message": "check this",
        "attachments": [{"filename": "a.png", "content_type": "image/png", "data": fake_pdf}],
    })
    assert response.status_code == 400
    assert "does not match" in json.dumps(response.json())


def test_oversize_session_id_is_4xx(client):
    response = client.post("/chat", json={"message": "hi", "session_id": "s" * 101})
    assert response.status_code == 422


# --- /chat/stream SSE framing ------------------------------------------------

def test_chat_stream_framing(client, app_module):
    response = client.post("/chat/stream", json={"message": DEMO_QUESTION,
                                                 "session_id": "test-stream"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = sse_events(response.text)
    assert events, "no SSE events emitted"

    types = [e["type"] for e in events]
    assert types.count("done") == 1, f"expected exactly one done event, got {types.count('done')}"
    assert types[-1] == "done", "done must be the final event"
    assert "error" not in types
    assert all(t == "token" for t in types[:-1]), "only token events may precede done"
    assert types[:-1], "expected at least one token event"

    streamed = "".join(e["text"] for e in events[:-1])
    assert streamed.strip() == app_module.STUB_RESPONSE

    done = events[-1]
    assert set(done) == {"type", "sources", "disclaimer"}
    assert done["disclaimer"] == app_module.DISCLAIMER
    assert 0 < len(done["sources"]) <= 3
    for source in done["sources"]:
        assert set(source) == {"act_title", "section_number", "section_heading",
                               "url", "excerpt", "score"}


def test_chat_stream_validation_is_4xx(client):
    assert client.post("/chat/stream", json={"message": ""}).status_code == 400
    assert client.post("/chat/stream", json={"message": "x" * 5001}).status_code == 422


# --- /session ----------------------------------------------------------------

def test_clear_session(client, app_module):
    client.post("/chat", json={"message": DEMO_QUESTION, "session_id": "test-clear"})
    assert "test-clear" in app_module.conversation_history
    response = client.delete("/session/test-clear")
    assert response.status_code == 200
    assert response.json() == {"status": "cleared"}
    assert "test-clear" not in app_module.conversation_history


# --- A3 mirror parity --------------------------------------------------------

def test_v1_health_parity(client):
    a = client.get("/health").json()
    b = client.get("/api/v1/health").json()
    assert a == b


def test_v1_acts_parity(client):
    assert client.get("/acts").json() == client.get("/api/v1/acts").json()


def test_v1_search_parity(client):
    params = {"q": DEMO_QUESTION, "limit": 5}
    assert client.get("/search", params=params).json() == \
        client.get("/api/v1/search", params=params).json()


def test_v1_chat_parity(client):
    payload = {"message": DEMO_QUESTION}
    a = client.post("/chat", json=payload).json()
    b = client.post("/api/v1/chat", json=payload).json()
    assert a == b


def test_v1_chat_stream_parity(client):
    payload = {"message": DEMO_QUESTION}
    a = sse_events(client.post("/chat/stream", json=payload).text)
    b = sse_events(client.post("/api/v1/chat/stream", json=payload).text)
    assert [e["type"] for e in a] == [e["type"] for e in b]
    assert a[-1]["sources"] == b[-1]["sources"]
    assert a[-1]["disclaimer"] == b[-1]["disclaimer"]


def test_v1_validation_parity(client):
    a = client.post("/chat", json={"message": ""})
    b = client.post("/api/v1/chat", json={"message": ""})
    assert a.status_code == b.status_code == 400
    assert a.json() == b.json()


def test_v1_version_shape(client, app_module):
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"api_version", "app_version", "endpoints"}
    assert body["api_version"] == app_module.API_VERSION
    assert "/api/v1/health" in body["endpoints"]


def test_v1_clear_session(client):
    response = client.delete("/api/v1/session/does-not-exist")
    assert response.status_code == 200
    assert response.json() == {"status": "cleared"}


# --- /debug/search gate ------------------------------------------------------

def test_debug_search_404_by_default(client):
    """Verified against production too: the endpoint 404s unless DEBUG=true.
    The briefing's 'unauthenticated debug endpoint' claim is stale."""
    response = client.get("/debug/search", params={"q": DEMO_QUESTION})
    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"


def test_debug_search_available_when_debug_enabled(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "DEBUG_MODE", True)
    response = client.get("/debug/search", params={"q": DEMO_QUESTION, "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"query", "detected_act", "key_sections_matched", "results"}


# --- admin endpoints stay shut ----------------------------------------------

@pytest.mark.parametrize("path", ["/admin/logs", "/admin/stats"])
def test_admin_requires_token(client, path):
    assert client.get(path).status_code == 422          # token param missing
    assert client.get(path, params={"token": "wrong"}).status_code == 401


# --- query log carries no network identifier ---------------------------------

@pytest.fixture
def log_dir(app_module, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(app_module, "ADMIN_TOKEN", "test-admin-token")
    return tmp_path


def read_log(log_dir):
    path = log_dir / "queries.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_chat_log_has_no_ip(client, log_dir):
    client.post("/chat", json={"message": DEMO_QUESTION, "session_id": "test-log-chat"},
                headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    entries = read_log(log_dir)
    assert len(entries) == 1
    assert set(entries[0]) == {"timestamp", "session_id", "query", "response",
                               "detected_act", "sources_count", "response_time_ms"}
    assert "203.0.113.7" not in json.dumps(entries[0])


def test_chat_stream_log_has_no_ip(client, log_dir):
    client.post("/chat/stream", json={"message": DEMO_QUESTION, "session_id": "test-log-stream"},
                headers={"X-Forwarded-For": "203.0.113.7"})
    entries = read_log(log_dir)
    assert len(entries) == 1
    assert "ip" not in entries[0]
    assert "203.0.113.7" not in json.dumps(entries[0])


def test_admin_logs_strips_legacy_ip(client, log_dir):
    legacy = {"timestamp": "2026-03-02T01:00:00Z", "session_id": "s1", "ip": "203.0.113.7",
              "query": "q", "response": "r", "detected_act": None,
              "sources_count": 0, "response_time_ms": 1}
    (log_dir / "queries.jsonl").write_text(json.dumps(legacy) + "\n")
    body = client.get("/admin/logs", params={"token": "test-admin-token"}).json()
    assert body["total"] == 1
    assert "ip" not in body["entries"][0]


def test_admin_stats_by_month(client, log_dir):
    rows = [
        {"timestamp": "2026-03-02T01:00:00Z", "session_id": "s1", "detected_act": "Residential Tenancies Act 1986"},
        {"timestamp": "2026-03-09T01:00:00Z", "session_id": "s1", "detected_act": "Residential Tenancies Act 1986"},
        {"timestamp": "2026-03-10T01:00:00Z", "session_id": "s2", "detected_act": None},
        {"timestamp": "2026-04-01T01:00:00Z", "session_id": "s2", "detected_act": None},
    ]
    (log_dir / "queries.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    body = client.get("/admin/stats", params={"token": "test-admin-token"}).json()
    assert set(body) == {"total_queries", "total_sessions", "top_acts", "by_month"}
    assert body["total_queries"] == 4
    assert body["total_sessions"] == 2
    assert body["by_month"] == {"2026-03": {"queries": 3, "sessions": 2},
                                "2026-04": {"queries": 1, "sessions": 1}}


def test_admin_stats_empty(client, log_dir):
    body = client.get("/admin/stats", params={"token": "test-admin-token"}).json()
    assert body == {"total_queries": 0, "total_sessions": 0, "top_acts": {}, "by_month": {}}
