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
    """A partial long enough to have been streamed stays; the message follows it."""
    partial = "The bond can be up to " * 20
    assert len(partial) > app_module.FETCH_COMMIT_CHARS
    msg = refusal(app_module, partial_text=partial)
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, msg))
    sid = "refusal-mid-stream"
    events = sse_events(client.post("/chat/stream", json={"message": LEGAL_Q, "session_id": sid}))
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed.startswith("The bond can be up to")
    assert streamed.endswith("\n\n" + app_module.REFUSAL_MESSAGE)
    assert events[-1]["type"] == "done" and events[-1]["sources"] == []
    assert app_module.conversation_history[sid][-1]["content"] == app_module.REFUSAL_MESSAGE


def test_short_partial_before_a_refusal_is_never_shown(client, app_module, monkeypatch):
    """On a legal question the first FETCH_COMMIT_CHARS of a round are held back
    (Claude may still fetch), so a short declined partial never reaches the user."""
    msg = refusal(app_module, partial_text="The bond can be up to ")
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, msg))
    events = sse_events(client.post("/chat/stream", json={"message": LEGAL_Q}))
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed == app_module.REFUSAL_MESSAGE


@pytest.mark.parametrize("stop_reason", ["end_turn", "max_tokens"])
def test_non_refusal_stop_reasons_return_the_text(client, app_module, monkeypatch, stop_reason):
    msg = app_module._stub_message(app_module.CLAUDE_MODEL, "Kia ora.\nSOURCES: none",
                                   stop_reason=stop_reason)
    monkeypatch.setattr(app_module, "anthropic_client", FakeClient(app_module, msg))
    assert client.post("/chat", json={"message": "hey there, thanks!"}).json()["response"] == "Kia ora."


# --- fetch_section: Claude reads a section mid-answer (13 Nov) -----------------
# The stub client answers from its .script, one entry per request, so a test
# can play a fetch round: a tool_use message, then the final answer.

PRIVACY = "Privacy Act 2020"
CASUAL_Q = "hey there, thanks!"


def tool_use(app_module, *calls, text=""):
    """A message that calls fetch_section once per (act, section[, find])."""
    inputs = []
    for call in calls:
        inp = {"act": call[0], "section": call[1]}
        if len(call) > 2:
            inp["find"] = call[2]
        inputs.append((app_module.FETCH_TOOL_NAME, inp))
    return app_module._stub_message(app_module.CLAUDE_MODEL, text, tool_calls=inputs)


def answer(app_module, text):
    return app_module._stub_message(app_module.CLAUDE_MODEL, text)


def tool_results(request):
    """The tool_result blocks in a request's last user turn."""
    content = request["messages"][-1]["content"]
    assert isinstance(content, list)
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
def test_fetch_tool_is_offered_only_on_legal_turns(client, app_module, path):
    stub = app_module.STUB_CLIENT.beta.messages
    resp = client.post(path, json={"message": LEGAL_Q})
    assert resp.status_code == 200
    assert stub.last_request["tools"] == [app_module.FETCH_SECTION_TOOL]
    assert "tool_choice" not in stub.last_request  # auto: Claude decides
    resp = client.post(path, json={"message": CASUAL_Q})
    assert resp.status_code == 200
    assert "tools" not in stub.last_request and "tool_choice" not in stub.last_request


def test_fetch_tool_definition(app_module):
    tool = app_module.FETCH_SECTION_TOOL
    assert tool["name"] == "fetch_section"
    schema = tool["input_schema"]
    assert schema["required"] == ["act", "section"]
    assert set(schema["properties"]) == {"act", "section", "find"}
    assert schema["additionalProperties"] is False
    assert (app_module.MAX_TOOL_ROUNDS, app_module.MAX_FETCHED_SECTIONS) == (3, 6)


def test_a_fetch_round_on_chat(client, app_module):
    """Claude asks for a section, the loop fetches it, and the final text is the
    answer. The fetched section is a source with a searched source's shape."""
    _, results, _, _ = app_module._retrieve_for_query(LEGAL_Q, "Residential Tenancies", "")
    assert not any(r["act_title"] == PRIVACY for r in results)
    stub = app_module.STUB_CLIENT.beta.messages
    stub.script[:] = [
        tool_use(app_module, (PRIVACY, "22"), text="Let me check."),
        answer(app_module, f"From section 22, the principles apply.\nSOURCES: {PRIVACY} s 22"),
    ]
    data = client.post("/chat", json={"message": LEGAL_Q}).json()
    assert data["response"] == "From section 22, the principles apply."  # not "Let me check."
    assert [(s["act_title"], s["section_number"]) for s in data["sources"]] == [(PRIVACY, "22")]
    src = data["sources"][0]
    assert set(src) == {"act_title", "section_number", "section_heading", "url", "excerpt", "score"}
    assert src["section_heading"] == "22 Information privacy principles"
    assert src["url"].startswith("http")

    first, second = stub.requests
    assert first["tools"] == second["tools"] == [app_module.FETCH_SECTION_TOOL]
    assert "tool_choice" not in second
    # The assistant turn goes back unchanged, thinking block first.
    echoed = second["messages"][-2]
    assert echoed["role"] == "assistant"
    assert [b.type for b in echoed["content"]] == ["thinking", "text", "tool_use"]
    assert echoed["content"][0].signature == "stub"
    (result,) = tool_results(second)
    assert result["tool_use_id"] == echoed["content"][2].id
    assert not result.get("is_error")
    assert f'"{PRIVACY} s 22"' in result["content"]
    assert "**Section 22 - 22 Information privacy principles**" in result["content"]


def test_fetched_section_is_matched_by_the_sources_line(app_module):
    _, fetched = app_module.fetch_section_text("Residential Tenancies Act 1986", "77")
    searched = [{"act_title": "Residential Tenancies Act 1986", "section_number": "18",
                 "section_heading": "18 General bonds", "section_url": "u", "text": "t", "score": .5}]
    text, sources = app_module.finalise_answer(
        "Answer.\nSOURCES: Residential Tenancies Act 1986 s 77; Residential Tenancies Act 1986 s 18",
        searched + [fetched], True)
    assert text == "Answer."
    assert [s["section_number"] for s in sources] == ["77", "18"]
    assert set(sources[0]) == set(sources[1])


def test_round_cap_forces_an_answer(client, app_module):
    """After MAX_TOOL_ROUNDS fetch rounds the next request carries tool_choice
    none, so Claude has to answer; that answer is returned."""
    stub = app_module.STUB_CLIENT.beta.messages
    sections = ["17", "19", "77", "23"]
    stub.script[:] = [tool_use(app_module, ("Residential Tenancies Act 1986", s)) for s in sections]
    stub.script.append(answer(app_module, "Done.\nSOURCES: Residential Tenancies Act 1986 s 77"))
    data = client.post("/chat", json={"message": LEGAL_Q}).json()
    rounds = app_module.MAX_TOOL_ROUNDS
    assert len(stub.requests) == rounds + 1
    for req in stub.requests[:rounds]:
        assert "tool_choice" not in req
    assert stub.requests[rounds]["tool_choice"] == {"type": "none"}
    assert stub.requests[rounds]["tools"] == [app_module.FETCH_SECTION_TOOL]
    # The 4th scripted tool_use answered the forced request: its (empty) text
    # is the answer, and the loop did not run a 4th fetch.
    assert data["response"].endswith(app_module.not_held_footer(["Residential Tenancies Act 1986"]))


def test_fetch_cap_declines_extra_calls(client, app_module):
    stub = app_module.STUB_CLIENT.beta.messages
    cap = app_module.MAX_FETCHED_SECTIONS
    calls = [("Residential Tenancies Act 1986", str(n)) for n in range(1, cap + 2)]
    stub.script[:] = [tool_use(app_module, *calls),
                      answer(app_module, "Done.\nSOURCES: Residential Tenancies Act 1986 s 2")]
    client.post("/chat", json={"message": LEGAL_Q})
    second = stub.requests[1]
    results = tool_results(second)
    assert len(results) == cap + 1  # every tool_use gets its result
    assert [bool(r.get("is_error")) for r in results] == [False] * cap + [True]
    assert "limit" in results[-1]["content"]
    assert second["tool_choice"] == {"type": "none"}


def test_repeat_fetch_is_not_counted(app_module):
    state = app_module._FetchState([])
    block = tool_use(app_module, ("Residential Tenancies Act 1986", "18")).content[-1]
    state.run(block)
    again = state.run(block)
    assert state.calls == 1 and "Already fetched" in again["content"]
    assert len(state.results) == 1


def test_unknown_section_and_act_reach_claude_plainly(client, app_module):
    stub = app_module.STUB_CLIENT.beta.messages
    stub.script[:] = [tool_use(app_module, ("Residential Tenancies Act 1986", "999"),
                               ("Holidays Act 2003", "16")),
                      answer(app_module, "Not found.\nSOURCES: none")]
    data = client.post("/chat", json={"message": LEGAL_Q}).json()
    no_section, not_held = tool_results(stub.requests[1])
    assert no_section["content"].startswith("NO SUCH SECTION")
    assert not_held["content"].startswith("NOT HELD")
    assert data["sources"] == []


def test_invalid_tool_input_is_an_error_result(app_module):
    msg = app_module._stub_message(app_module.CLAUDE_MODEL, "",
                                   tool_calls=[(app_module.FETCH_TOOL_NAME, {"act": 6})])
    result = app_module._FetchState([]).run(msg.content[-1])
    assert result["is_error"] is True


def test_a_fetch_round_on_chat_stream(client, app_module):
    """Text written before the fetch is never streamed; the final round's text
    streams in pieces, and the fetched section is a source in the done event."""
    stub = app_module.STUB_CLIENT.beta.messages
    final = ("Section 77 sets out what the Tribunal can decide, and the bond rules sit with "
             "it. " * 6 + "\nSOURCES: Residential Tenancies Act 1986 s 77")
    assert len(final) > app_module.FETCH_COMMIT_CHARS + 100
    stub.script[:] = [
        tool_use(app_module, ("Residential Tenancies Act 1986", "77"), text="I hold the Act, but "),
        answer(app_module, final),
    ]
    events = sse_events(client.post("/chat/stream", json={"message": LEGAL_Q}))
    tokens = [e["text"] for e in events if e["type"] == "token"]
    streamed = "".join(tokens)
    assert "I hold the Act" not in streamed
    assert streamed == final.split("\nSOURCES")[0].rstrip()
    # Past the first FETCH_COMMIT_CHARS the answer streams word by word.
    assert len(tokens) > 10
    assert [(s["act_title"], s["section_number"]) for s in events[-1]["sources"]] == [
        ("Residential Tenancies Act 1986", "77")]
    assert len(stub.requests) == 2


def test_text_already_shown_stops_further_fetching(client, app_module):
    """If Claude writes past FETCH_COMMIT_CHARS and then calls the tool, the text
    has been shown: the call is declined and the next request must answer."""
    stub = app_module.STUB_CLIENT.beta.messages
    opening = "The bond rules are these. " * 20
    stub.script[:] = [
        tool_use(app_module, ("Residential Tenancies Act 1986", "77"), text=opening),
        answer(app_module, " That is all.\nSOURCES: none"),
    ]
    events = sse_events(client.post("/chat/stream", json={"message": LEGAL_Q}))
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed.startswith(opening.strip()[:50]) and "That is all." in streamed
    (result,) = tool_results(stub.requests[1])
    assert result["is_error"] and result["content"].startswith("Not fetched")
    assert stub.requests[1]["tool_choice"] == {"type": "none"}


def test_refusal_after_a_fetch_round(client, app_module):
    stub = app_module.STUB_CLIENT.beta.messages
    for path in ("/chat", "/chat/stream"):
        stub.reset()
        stub.script[:] = [tool_use(app_module, ("Residential Tenancies Act 1986", "77")),
                          refusal(app_module)]
        resp = client.post(path, json={"message": LEGAL_Q})
        if path == "/chat":
            assert resp.json()["response"] == app_module.REFUSAL_MESSAGE
            assert resp.json()["sources"] == []
        else:
            events = sse_events(resp)
            assert "".join(e["text"] for e in events if e["type"] == "token") == \
                app_module.REFUSAL_MESSAGE
            assert events[-1]["sources"] == []


FALLBACK_BLOCK = {"type": "fallback", "from": {"model": "claude-opus-5-5"},
                  "to": {"model": "claude-opus-4-8"},
                  "trigger": {"type": "refusal", "category": "cyber"}}


def test_fallback_model_answer_is_used(client, app_module):
    msg = app_module._stub_message("claude-opus-4-8", "Kia ora.\nSOURCES: none",
                                   extra_blocks=[FALLBACK_BLOCK])
    stub = app_module.STUB_CLIENT.beta.messages
    for path in ("/chat", "/chat/stream"):
        stub.script[:] = [msg]
        resp = client.post(path, json={"message": LEGAL_Q})
        text = (resp.json()["response"] if path == "/chat" else
                "".join(e["text"] for e in sse_events(resp) if e["type"] == "token"))
        assert text.startswith("Kia ora.")
        assert app_module.REFUSAL_MESSAGE not in text


def test_tool_call_after_a_mid_output_fallback_is_echoed_per_the_api_rules(client, app_module):
    """The declined model's thinking and tool_use before the fallback block are
    left out of the echo; the fallback block stays in place; only the fallback
    model's tool call (after the block) is run."""
    from anthropic.types.beta import BetaMessage
    declined_call = {"type": "tool_use", "id": "toolu_declined", "name": "fetch_section",
                     "input": {"act": "Residential Tenancies Act 1986", "section": "18"}}
    msg = BetaMessage.model_validate({
        "id": "m", "type": "message", "role": "assistant", "model": "claude-opus-4-8",
        "stop_reason": "tool_use", "stop_sequence": None, "stop_details": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "content": [
            {"type": "thinking", "thinking": "", "signature": "declined"},
            {"type": "text", "text": "Partial "},
            declined_call,
            FALLBACK_BLOCK,
            {"type": "thinking", "thinking": "", "signature": "fallback"},
            {"type": "tool_use", "id": "toolu_fb", "name": "fetch_section",
             "input": {"act": "Residential Tenancies Act 1986", "section": "77"}},
        ]})
    stub = app_module.STUB_CLIENT.beta.messages
    stub.script[:] = [msg, answer(app_module, "Done.\nSOURCES: Residential Tenancies Act 1986 s 77")]
    data = client.post("/chat", json={"message": LEGAL_Q}).json()
    echoed = stub.requests[1]["messages"][-2]["content"]
    assert [b.type for b in echoed] == ["text", "fallback", "thinking", "tool_use"]
    assert echoed[2].signature == "fallback"
    (result,) = tool_results(stub.requests[1])
    assert result["tool_use_id"] == "toolu_fb"
    assert [s["section_number"] for s in data["sources"]] == ["77"]
