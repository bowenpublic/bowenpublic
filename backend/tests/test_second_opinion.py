"""Offline tests for backend/app/second_opinion.py (httpx.MockTransport; no network)."""

import asyncio
import json
import logging

import httpx
import pytest

from backend.app import second_opinion as so


@pytest.fixture(autouse=True)
def clean_history():
    """Overrides conftest's autouse fixture: these tests do not need main.py,
    which keeps them independent of edits to it."""
    yield


KEY = "sk-test-SECRET-KEY-123"

EXCERPTS = [
    {"act": "Residential Tenancies Act 1986", "section": "18", "heading": "18 General bonds",
     "text": "(1) A landlord may require payment of a bond (a general bond) of no more than "
             "4 weeks’ rent lawfully payable under the tenancy agreement."},
    {"act": "Residential Tenancies Act 1986", "section": "22",
     "heading": "22 Agreed applications to chief executive for payment of bond",
     "text": "(2) The chief executive must pay the bond in accordance with the terms of the application."},
]

ANSWER = (
    "Under section 18 of the Residential Tenancies Act 1986, a landlord may require a bond of "
    "\"no more than 4 weeks' rent\". The bond is held by the chief executive (MBIE). "
    "I didn't retrieve the section on bond disputes.\n\n"
    "As always, verify at legislation.govt.nz and consult a lawyer for your specific situation."
)
QUESTION = "What is the maximum bond?"


def cfg(mode="shadow", timeout=8.0, key=KEY):
    return so.Config(mode=mode, model="gpt-test", effort="low", timeout_s=timeout, api_key=key)


def openai_payload(issues, status="completed", model="gpt-test-2026", refusal=False):
    content = ([{"type": "refusal", "refusal": "no"}] if refusal else
               [{"type": "output_text", "text": json.dumps({"issues": issues}), "annotations": []}])
    return {
        "id": "resp_1", "object": "response", "status": status, "model": model,
        "output": [
            {"type": "reasoning", "id": "rs_1", "summary": []},
            {"type": "message", "role": "assistant", "status": "completed", "content": content},
        ],
        "usage": {"input_tokens": 1234, "output_tokens": 56, "total_tokens": 1290},
    }


def transport_returning(payload=None, status=200, raw=None, seen=None):
    def handler(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        if raw is not None:
            return httpx.Response(status, content=raw)
        return httpx.Response(status, json=payload)
    return httpx.MockTransport(handler)


def run(coro):
    return asyncio.run(coro)


# --- configuration and modes --------------------------------------------------

def test_missing_key_means_off_whatever_the_mode():
    for env in ({}, {"OPENAI_API_KEY": ""}, {"OPENAI_API_KEY": "your-openai-key-here"},
                {"BOWEN_SECOND_OPINION": "enforce"}):
        c = so.load_config(env)
        assert c.mode == "off" and not c.enabled


def test_default_mode_is_shadow_with_key():
    c = so.load_config({"OPENAI_API_KEY": KEY})
    assert c.mode == "shadow" and c.enabled
    assert c.model == so.DEFAULT_MODEL == "gpt-6.1-sol"
    assert c.effort == "low" and c.timeout_s == 8.0


def test_explicit_modes_and_overrides():
    env = {"OPENAI_API_KEY": KEY, "BOWEN_SECOND_OPINION": "ENFORCE",
           "BOWEN_SECOND_OPINION_MODEL": "gpt-6-astra", "BOWEN_SECOND_OPINION_EFFORT": "medium",
           "BOWEN_SECOND_OPINION_TIMEOUT": "5"}
    c = so.load_config(env)
    assert (c.mode, c.model, c.effort, c.timeout_s) == ("enforce", "gpt-6-astra", "medium", 5.0)
    assert so.load_config({"OPENAI_API_KEY": KEY, "BOWEN_SECOND_OPINION": "off"}).mode == "off"
    # Unknown mode falls back to the default; bad timeout to 8 s.
    c = so.load_config({"OPENAI_API_KEY": KEY, "BOWEN_SECOND_OPINION": "loud",
                        "BOWEN_SECOND_OPINION_TIMEOUT": "abc"})
    assert c.mode == "shadow" and c.timeout_s == 8.0


def test_key_never_in_repr():
    assert KEY not in repr(so.load_config({"OPENAI_API_KEY": KEY}))


def test_missing_key_returns_none_without_calling_out():
    seen = []
    v = run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(key=""),
                            transport=transport_returning(openai_payload([]), seen=seen)))
    assert v is None and seen == []


def test_off_mode_returns_none_without_calling_out():
    seen = []
    v = run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(mode="off"),
                            transport=transport_returning(openai_payload([]), seen=seen)))
    assert v is None and seen == []


def test_startup_log_once(caplog, monkeypatch):
    monkeypatch.setattr(so, "_startup_logged", False)
    with caplog.at_level(logging.INFO, logger="bowen.second_opinion"):
        so.log_startup(cfg(key=""))
        so.log_startup(cfg(key=""))
        run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(key="")))
    lines = [r for r in caplog.records if "second opinion" in r.getMessage()]
    assert len(lines) == 1 and "off" in lines[0].getMessage()


def test_should_check():
    on = cfg()
    assert so.should_check(on, is_legal_query=True, refused=False)
    assert not so.should_check(on, is_legal_query=False, refused=False)
    assert not so.should_check(on, is_legal_query=True, refused=True)
    assert not so.should_check(on, is_legal_query=True, refused=False, has_attachments=True)
    assert not so.should_check(cfg(mode="off"), is_legal_query=True, refused=False)
    assert not so.should_check(cfg(key=""), is_legal_query=True, refused=False)


# --- happy path ---------------------------------------------------------------

def test_happy_path_no_issues():
    v = run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                            transport=transport_returning(openai_payload([]))))
    assert v is not None and v.ok and v.issues == []
    assert (v.model, v.tokens_in, v.tokens_out) == ("gpt-test-2026", 1234, 56)
    assert v.latency_ms >= 0


def test_happy_path_with_issue():
    issue = {"sentence": "The bond is held by the chief executive (MBIE).",
             "kind": "unsupported_claim", "reason": "No excerpt names MBIE."}
    v = run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                            transport=transport_returning(openai_payload([issue]))))
    assert v is not None and not v.ok
    assert v.issues == [so.Issue(issue["sentence"], "unsupported_claim", "No excerpt names MBIE.")]


# --- failures -----------------------------------------------------------------

def test_malformed_json_in_output_text():
    payload = openai_payload([])
    payload["output"][1]["content"][0]["text"] = "{not json"
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                               transport=transport_returning(payload))) is None


def test_json_without_issues_list():
    payload = openai_payload([])
    payload["output"][1]["content"][0]["text"] = json.dumps({"verdict": "ok"})
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                               transport=transport_returning(payload))) is None


def test_body_not_json():
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                               transport=transport_returning(raw=b"<html>oops</html>"))) is None


def test_refusal_and_incomplete():
    for payload in (openai_payload([], refusal=True), openai_payload([], status="incomplete")):
        assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                                   transport=transport_returning(payload))) is None


@pytest.mark.parametrize("status", [400, 401, 429, 500, 503])
def test_http_error(status):
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                               transport=transport_returning({"error": {"message": "x"}},
                                                             status=status))) is None


def test_transport_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                               transport=httpx.MockTransport(handler))) is None


def test_overall_deadline():
    async def handler(request):
        await asyncio.sleep(2)
        return httpx.Response(200, json=openai_payload([]))
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(timeout=0.05),
                               transport=httpx.MockTransport(handler))) is None


def test_connection_error_never_raises():
    def handler(request):
        raise httpx.ConnectError("down", request=request)
    assert run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                               transport=httpx.MockTransport(handler))) is None


def test_failure_logs_do_not_contain_key(caplog):
    with caplog.at_level(logging.DEBUG):
        run(so.check_answer(QUESTION, EXCERPTS, ANSWER, config=cfg(),
                            transport=transport_returning({}, status=401)))
    assert KEY not in caplog.text


# --- validation ---------------------------------------------------------------

def test_validation_drops_bad_items():
    raw = [
        {"sentence": "The landlord must return the bond within 10 days.",   # not in answer
         "kind": "unsupported_claim", "reason": "x"},
        {"sentence": "The bond is held by the chief executive (MBIE).",     # bad kind
         "kind": "opinion", "reason": "x"},
        {"sentence": "The bond is held by the chief executive (MBIE).",     # empty reason
         "kind": "unsupported_claim", "reason": "  "},
        {"sentence": "As always, verify at legislation.govt.nz and consult a lawyer for your "
                     "specific situation.", "kind": "unsupported_claim", "reason": "x"},  # fixed line
        {"sentence": "rent", "kind": "misquote", "reason": "x"},            # too short
        "not a dict",
        {"sentence": "a landlord may require a bond of \"no more than 4 weeks' rent\"",  # verbatim quote
         "kind": "misquote", "reason": "x"},
        {"sentence": "The bond is held by the chief executive (MBIE).",     # kept
         "kind": "unsupported_claim", "reason": "No excerpt names MBIE.\nSecond line."},
        {"sentence": "The bond is held by the chief executive (MBIE).",     # duplicate
         "kind": "unsupported_claim", "reason": "again"},
    ]
    kept, dropped = so.validate_issues(raw, ANSWER, so.excerpts_from_results(EXCERPTS))
    assert [i.sentence for i in kept] == ["The bond is held by the chief executive (MBIE)."]
    assert kept[0].reason == "No excerpt names MBIE. Second line."   # one line
    assert dropped == 8


def test_validation_tolerates_markdown_and_curly_quotes():
    answer = "The maximum is **4 weeks’ rent**, says “the Act” somewhere."
    raw = [{"sentence": "The maximum is 4 weeks' rent, says \"the Act\" somewhere.",
            "kind": "misquote", "reason": "'the Act' is not in an excerpt"}]
    kept, dropped = so.validate_issues(raw, answer, so.excerpts_from_results(EXCERPTS))
    assert len(kept) == 1 and dropped == 0


def test_misquote_needs_a_non_verbatim_quote():
    answer = 'It says "a bond of no more than 6 weeks rent".'
    raw = [{"sentence": answer, "kind": "misquote", "reason": "6 weeks is not in s 18"}]
    kept, _ = so.validate_issues(raw, answer, so.excerpts_from_results(EXCERPTS))
    assert len(kept) == 1
    no_quotes = "A landlord can ask for six weeks of rent as bond."
    kept, dropped = so.validate_issues(
        [{"sentence": no_quotes, "kind": "misquote", "reason": "x"}], no_quotes,
        so.excerpts_from_results(EXCERPTS))
    assert kept == [] and dropped == 1


def test_validation_caps_issue_count():
    answer = " ".join(f"Claim number {i} is here." for i in range(20))
    raw = [{"sentence": f"Claim number {i} is here.", "kind": "unsupported_claim", "reason": "r"}
           for i in range(20)]
    kept, _ = so.validate_issues(raw, answer, [])
    assert len(kept) == so.MAX_ISSUES


# --- request body -------------------------------------------------------------

def test_request_body_and_auth_header():
    seen = []
    run(so.check_answer(QUESTION, EXCERPTS, ANSWER, notes="REPEAL NOTE: x", config=cfg(),
                        transport=transport_returning(openai_payload([]), seen=seen)))
    assert len(seen) == 1
    req = seen[0]
    assert req.method == "POST" and str(req.url) == so.API_URL
    assert req.headers["authorization"] == f"Bearer {KEY}"
    # The key is only in the Authorization header.
    other_headers = {k: v for k, v in req.headers.items() if k.lower() != "authorization"}
    assert KEY not in json.dumps(other_headers) and KEY not in str(req.url)
    raw_body = req.content.decode()
    assert KEY not in raw_body
    body = json.loads(raw_body)
    assert set(body) == {"model", "instructions", "input", "text", "reasoning",
                         "max_output_tokens", "store"}
    assert body["model"] == "gpt-test" and body["store"] is False
    assert body["reasoning"] == {"effort": "low"}
    fmt = body["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert fmt["schema"]["properties"]["issues"]["items"]["properties"]["kind"]["enum"] == list(so.KINDS)
    content = body["input"][0]["content"]
    assert QUESTION in content and ANSWER in content and "REPEAL NOTE: x" in content
    assert "section 18" in content and "4 weeks’ rent" in content


def test_excerpts_from_main_result_shape():
    rows = [{"act_title": "Privacy Act 2020", "section_number": "22", "section_heading": "IPPs",
             "text": "t", "score": 0.4}]
    assert so.excerpts_from_results(rows) == [so.Excerpt("Privacy Act 2020", "22", "t", "IPPs")]


def test_empty_excerpts_are_stated():
    assert "no excerpts were retrieved" in so.build_input("q", [], "a")


def test_instructions_guard_against_own_knowledge_and_fixed_lines():
    text = so.CHECKER_INSTRUCTIONS
    assert "no knowledge of New Zealand law" in text
    assert "NEVER flag" in text and "legislation.govt.nz" in text
    assert "not retrieved" in text and "When in doubt, do not flag" in text


# --- caller helpers -----------------------------------------------------------

def test_caution_text_only_in_enforce_with_issues():
    bad = so.Verdict(False, [so.Issue("s", "misquote", "r")], "m", 1, 1, 1)
    good = so.Verdict(True, [], "m", 1, 1, 1)
    assert so.caution_text(bad, "enforce") == so.CAUTION_LINE
    assert so.caution_text(bad, "shadow") == ""
    assert so.caution_text(bad, "off") == ""
    assert so.caution_text(good, "enforce") == ""
    assert so.caution_text(None, "enforce") == ""
    line = so.CAUTION_LINE.lower()
    for word in ("openai", "gpt", "model", "sources:", "claude"):
        assert word not in line


def test_log_fields_and_log_line(caplog):
    v = so.Verdict(False, [so.Issue("The bond is held by MBIE.", "unsupported_claim", "r")],
                   "m", 10, 2, 3, dropped=1)
    fields = so.verdict_log_fields(v)
    json.dumps(fields)
    assert fields["issues"][0]["kind"] == "unsupported_claim" and fields["dropped"] == 1
    assert so.verdict_log_fields(None) == {}
    with caplog.at_level(logging.INFO, logger="bowen.second_opinion"):
        so.log_verdict(v, "abcdefghijkl")
        so.log_verdict(None)
    assert "kinds=unsupported_claim" in caplog.text and "abcdefgh" in caplog.text
    assert "abcdefghi" not in caplog.text and "MBIE" not in caplog.text


def test_naming_the_governing_act_is_never_flagged():
    """Live trial 13 Nov: "governed by the X Act, which I don't hold" was flagged
    (N02, N03, E07, E12). Bowen's rule 3 allows naming the Act and saying
    whether it is held; only what the Act provides is checkable."""
    text = so.CHECKER_INSTRUCTIONS
    never = text[text.index("NEVER flag any of these"):text.index("Rules for your output")]
    assert ("Naming the Act that probably governs the topic, together with saying that Bowen "
            "holds it, does not hold it, or that its section was not among the sections pulled"
            in never)
    assert "Flag such a sentence only if it goes on to state what that Act provides" in never
