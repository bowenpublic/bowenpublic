"""The Claude call on /chat and /chat/stream: request settings, reading the
response by block type, and the refusal path. All offline, through the stub
client or a fake one built from the same real SDK response types."""
import json

import pytest

LEGAL_Q = "How much bond can a landlord ask for under the Residential Tenancies Act?"


class FakeClient:
    """Answers every request with one fixed BetaMessage."""

    def __init__(self, app_module, message):
        self._app = app_module
        self._message = message
        self.last_request = None
        self.beta = type("FakeBeta", (), {})()
        self.beta.messages = self

    def create(self, **kwargs):
        self.last_request = kwargs
        return self._message

    def stream(self, **kwargs):
        self.last_request = kwargs
        return self._app._StubStream(self._message)


def refusal(app_module, partial_text=""):
    return app_module._stub_message(
        app_module.CLAUDE_MODEL, partial_text, stop_reason="refusal",
        stop_details={"type": "refusal", "category": "bio", "explanation": None})


def sse_events(resp):
    """Parse an SSE body, asserting every event is a well-formed data line."""
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    chunks = [c for c in resp.text.split("\n\n") if c]
    events = []
    for c in chunks:
        assert c.startswith("data: ") and "\n" not in c, repr(c)
        events.append(json.loads(c[6:]))
    return events


# --- Request settings --------------------------------------------------------

def test_model_effort_and_fallback_reach_the_client_on_chat(client, app_module):
    stub = app_module.STUB_CLIENT.beta.messages
    stub.last_request = None
    assert client.post("/chat", json={"message": LEGAL_Q}).status_code == 200
    req = stub.last_request
    assert req["model"] == app_module.CLAUDE_MODEL == "claude-opus-5-5"
    assert req["output_config"] == {"effort": app_module.CLAUDE_EFFORT}
    assert app_module.CLAUDE_EFFORT == "medium"
    assert req["betas"] == ["server-side-fallback-2026-07-01"]
    assert req["fallbacks"] == "default"
    assert req["max_tokens"] == 1750 + app_module.THINKING_TOKEN_HEADROOM
    assert req["system"] == app_module.SYSTEM_PROMPT
    assert "thinking" not in req and "temperature" not in req


def test_same_settings_reach_the_client_on_chat_stream(client, app_module):
    stub = app_module.STUB_CLIENT.beta.messages
    stub.last_request = None
    client.post("/chat", json={"message": LEGAL_Q})
    on_chat = dict(stub.last_request)
    stub.last_request = None
    sse_events(client.post("/chat/stream", json={"message": LEGAL_Q}))
    on_stream = stub.last_request
    for key in ("model", "output_config", "betas", "fallbacks", "max_tokens", "system"):
        assert on_stream[key] == on_chat[key], key


def test_attachments_keep_their_larger_reply_allowance(app_module):
    _, max_tokens = app_module._build_claude_messages("q", "CTX", attachment_context="doc text")
    assert max_tokens == 2500 + app_module.THINKING_TOKEN_HEADROOM


def test_model_env_override(app_module):
    resolve = app_module.resolve_claude_model
    assert resolve({}) == "claude-opus-5-5"
    assert resolve({"BOWEN_CLAUDE_MODEL": ""}) == "claude-opus-5-5"
    assert resolve({"BOWEN_CLAUDE_MODEL": "  "}) == "claude-opus-5-5"
    assert resolve({"BOWEN_CLAUDE_MODEL": " claude-sonnet-5-5 "}) == "claude-sonnet-5-5"


def test_overridden_model_is_the_one_sent(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "CLAUDE_MODEL",
                        app_module.resolve_claude_model({"BOWEN_CLAUDE_MODEL": "claude-sonnet-5-5"}))
    stub = app_module.STUB_CLIENT.beta.messages
    client.post("/chat", json={"message": LEGAL_Q})
    assert stub.last_request["model"] == "claude-sonnet-5-5"
    sse_events(client.post("/chat/stream", json={"message": LEGAL_Q}))
    assert stub.last_request["model"] == "claude-sonnet-5-5"


# --- Reading the response by block type ---------------------------------------

def test_stub_response_opens_with_a_thinking_block(app_module):
    msg = app_module.STUB_CLIENT.beta.messages.create(model="m")
    assert [b.type for b in msg.content] == ["thinking", "text"]


def test_text_after_a_thinking_block_is_the_answer(client, app_module, monkeypatch):
    msg = app_module._stub_message(app_module.CLAUDE_MODEL,
                                   "The answer.\nSOURCES: none")
    assert msg.content[0].type == "thinking"
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, msg))
    data = client.post("/chat", json={"message": "hey there, thanks!"}).json()
    assert data["response"] == "The answer."
    assert data["sources"] == []


# --- Refusal --------------------------------------------------------------------

def test_refusal_message_is_plain_and_points_to_help(app_module):
    msg = app_module.REFUSAL_MESSAGE
    assert msg.startswith("I")
    assert "legislation.govt.nz" in msg and "Community Law" in msg
    assert "SOURCES" not in msg
    assert "111" in msg and "1737" in msg
    assert "retrieve" not in msg.lower()  # not the not-held footer's wording
    for internal in ("model", "classifier", "refus", "policy", "Claude", "Anthropic"):
        assert internal not in msg


def test_refusal_on_chat_gives_fixed_message_and_no_sources(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, refusal(app_module)))
    sid = "refusal-chat"
    resp = client.post("/chat", json={"message": LEGAL_Q, "session_id": sid})
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == app_module.REFUSAL_MESSAGE  # no not-held footer either
    assert app_module.NOT_HELD_FOOTER not in data["response"]
    assert data["sources"] == []
    assert app_module.conversation_history[sid][-1] == {
        "role": "assistant", "content": app_module.REFUSAL_MESSAGE}


def test_refusal_on_chat_stream_gives_fixed_message_and_no_sources(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, refusal(app_module)))
    sid = "refusal-stream"
    events = sse_events(client.post("/chat/stream", json={"message": LEGAL_Q, "session_id": sid}))
    assert [e["type"] for e in events][-1] == "done"
    assert not any(e["type"] == "error" for e in events)
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed == app_module.REFUSAL_MESSAGE
    assert events[-1]["sources"] == []
    assert app_module.conversation_history[sid][-1]["content"] == app_module.REFUSAL_MESSAGE


def test_mid_stream_refusal_follows_partial_text_and_stores_only_message(client, app_module,
                                                                        monkeypatch):
    msg = refusal(app_module, partial_text="The bond can be up to ")
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, msg))
    sid = "refusal-mid-stream"
    events = sse_events(client.post("/chat/stream", json={"message": LEGAL_Q, "session_id": sid}))
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed.endswith("\n\n" + app_module.REFUSAL_MESSAGE)
    assert events[-1]["type"] == "done" and events[-1]["sources"] == []
    assert app_module.conversation_history[sid][-1]["content"] == app_module.REFUSAL_MESSAGE


@pytest.mark.parametrize("stop_reason", ["end_turn", "max_tokens"])
def test_non_refusal_stop_reasons_return_the_text(client, app_module, monkeypatch, stop_reason):
    msg = app_module._stub_message(app_module.CLAUDE_MODEL, "Kia ora.\nSOURCES: none",
                                   stop_reason=stop_reason)
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, msg))
    assert client.post("/chat", json={"message": "hey there, thanks!"}).json()["response"] == "Kia ora."
