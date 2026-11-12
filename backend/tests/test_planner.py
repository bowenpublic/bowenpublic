"""
test_planner.py: the search planner (backend/app/planner.py), offline.

Every test uses a fake client; nothing reaches the network. The planner must
return None (never raise) on any failure, and must drop any Act or section
that is not in the index it is given.
"""

import json
from types import SimpleNamespace

import pytest

from backend.app import planner
from backend.app.planner import (
    CallStats, SearchPlan, build_section_index, held_titles, merge_plan, plan_search,
)

RTA = "Residential Tenancies Act 1986"
ERA = "Employment Relations Act 2000"
CRIMES = "Crimes Act 1961"

INDEX = build_section_index([
    {"act_title": RTA, "section_number": "48"},
    {"act_title": RTA, "section_number": "48"},
    {"act_title": RTA, "section_number": "40 "},
    {"act_title": RTA, "section_number": "22A"},
    {"act_title": ERA, "section_number": "6"},
    {"act_title": ERA, "section_number": "67A"},
    {"act_title": CRIMES, "section_number": "48"},
    {"act_title": "Not In The Registry Act 1999", "section_number": "1"},
])


def _usage(i=1500, o=60, cr=0, cw=0):
    return SimpleNamespace(input_tokens=i, output_tokens=o,
                           cache_read_input_tokens=cr, cache_creation_input_tokens=cw)


def _message(payload=None, *, text=None, stop_reason="end_turn", blocks=None):
    if blocks is None:
        if text is None:
            text = json.dumps(payload)
        blocks = [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=_usage())


class FakeMessages:
    def __init__(self, reply=None, exc=None):
        self.reply, self.exc, self.calls = reply, exc, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.reply


class FakeClient:
    def __init__(self, reply=None, exc=None):
        self.messages = FakeMessages(reply, exc)
        self.options = None

    def with_options(self, **kw):
        self.options = kw
        return self


def run(client, query="Can my landlord enter without telling me?", history=None, **kw):
    calls = []
    plan = plan_search(client, query, history or [], sections_by_act=INDEX,
                       on_call=calls.append, environ=kw.pop("environ", {}), **kw)
    assert len(calls) == 1 and isinstance(calls[0], CallStats)
    return plan, calls[0]


# --- Good plan -----------------------------------------------------------------

def test_good_plan_is_validated_and_mapped_to_the_act_filter():
    client = FakeClient(_message({"act": RTA, "sections": ["48", "s 40(1)"],
                                  "search_text": "landlord's right of entry, notice to tenant"}))
    plan, stats = run(client)
    assert isinstance(plan, SearchPlan)
    assert plan.act == "Residential Tenancies"          # the form main.py's act filter expects
    assert plan.act_title == RTA
    assert plan.sections == ["48", "40"]                # "s 40(1)" normalised to the index's "40"
    assert plan.search_text.startswith("landlord's right of entry")
    assert stats.outcome == "ok" and stats.dropped == []
    assert stats.input_tokens == 1500 and stats.output_tokens == 60
    assert stats.latency_ms >= 0 and stats.cost_usd > 0
    # one call, no retries, a short timeout, the configured model
    assert client.options == {"max_retries": 0, "timeout": planner.DEFAULT_TIMEOUT}
    req = client.messages.calls[0]
    assert req["model"] == "claude-haiku-5-5"
    assert req["output_config"]["format"]["type"] == "json_schema"


def test_model_env_override():
    client = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    run(client, environ={"BOWEN_PLANNER_MODEL": "claude-sonnet-5-5"})
    assert client.messages.calls[0]["model"] == "claude-sonnet-5-5"


# --- Validation drops what the index does not hold -------------------------------

def test_act_not_held_is_dropped_with_its_sections():
    client = FakeClient(_message({"act": "Holidays Act 2003", "sections": ["65"],
                                  "search_text": "sick leave entitlement"}))
    plan, stats = run(client, "How many sick days do I get?")
    assert plan is not None and plan.act is None and plan.act_title is None
    assert plan.sections == []
    assert plan.search_text == "sick leave entitlement"   # still a usable extra query
    assert "act_not_held:Holidays Act 2003" in stats.dropped
    assert any(d.startswith("section_without_act:") for d in stats.dropped)


def test_act_in_index_but_not_registry_is_not_offered_or_accepted():
    assert "Not In The Registry Act 1999" not in held_titles(INDEX)
    client = FakeClient(_message({"act": "Not In The Registry Act 1999", "sections": ["1"],
                                  "search_text": None}))
    plan, stats = run(client)
    assert plan is None
    assert stats.outcome == "empty"


def test_nonexistent_section_is_dropped():
    client = FakeClient(_message({"act": ERA, "sections": ["6", "999", "67a", "Schedule 9"],
                                  "search_text": None}))
    plan, stats = run(client, "Am I an employee or a contractor?")
    assert plan.sections == ["6", "67A"]
    assert f"section_not_in_index:{ERA} s 999" in stats.dropped
    assert f"section_not_in_index:{ERA} s Schedule 9" in stats.dropped


def test_section_of_another_act_is_not_borrowed():
    # Crimes Act has s 48; RTA does not have s 22B. Validation is per Act.
    client = FakeClient(_message({"act": RTA, "sections": ["22B"], "search_text": None}))
    plan, stats = run(client)
    assert plan.sections == [] and stats.dropped == [f"section_not_in_index:{RTA} s 22B"]


def test_act_name_case_insensitive_match():
    client = FakeClient(_message({"act": RTA.upper(), "sections": ["48"], "search_text": None}))
    plan, _ = run(client)
    assert plan.act_title == RTA and plan.sections == ["48"]


# --- Malformed or empty output -----------------------------------------------------

@pytest.mark.parametrize("reply", [
    _message(text="not json at all"),
    _message(text=""),
    _message(text="[1, 2, 3]"),
    _message(blocks=[]),
    _message(blocks=[SimpleNamespace(type="thinking", thinking="", signature="x")]),
    _message({"act": None, "sections": [], "search_text": None}),
    _message({"act": None, "sections": [], "search_text": "   "}),
    SimpleNamespace(),          # no content, no stop_reason, no usage
])
def test_malformed_or_empty_output_returns_none(reply):
    plan, stats = run(FakeClient(reply))
    assert plan is None
    assert stats.outcome in ("malformed", "empty")


def test_truncated_output_returns_none():
    plan, stats = run(FakeClient(_message(text='{"act": "Resid', stop_reason="max_tokens")))
    assert plan is None and stats.outcome == "max_tokens"


def test_wrong_types_in_fields_are_ignored():
    client = FakeClient(_message({"act": 42, "sections": "48", "search_text": ["x"]}))
    plan, stats = run(client)
    assert plan is None and stats.outcome == "empty"


# --- Exceptions and timeouts ----------------------------------------------------------

def test_exception_returns_none():
    plan, stats = run(FakeClient(exc=RuntimeError("boom")))
    assert plan is None and stats.outcome == "error"


def test_timeout_returns_none():
    plan, stats = run(FakeClient(exc=TimeoutError()))
    assert plan is None and stats.outcome == "timeout"


def test_sdk_timeout_and_status_errors_are_classified():
    import anthropic
    import httpx2

    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    plan, stats = run(FakeClient(exc=anthropic.APITimeoutError(request=req)))
    assert plan is None and stats.outcome == "timeout"

    resp = httpx2.Response(529, request=req)
    plan, stats = run(FakeClient(exc=anthropic.APIStatusError("overloaded", response=resp, body=None)))
    assert plan is None and stats.outcome == "http_529"


def test_custom_timeout_is_passed_to_the_client():
    client = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    run(client, timeout=1.5)
    assert client.options == {"max_retries": 0, "timeout": 1.5}


def test_on_call_failure_does_not_raise():
    def bad(_stats):
        raise ValueError("logger broke")
    plan = plan_search(FakeClient(_message({"act": RTA, "sections": ["48"], "search_text": None})),
                       "q", [], sections_by_act=INDEX, on_call=bad, environ={})
    assert plan is not None and plan.sections == ["48"]


# --- Off switch and stub ----------------------------------------------------------------

@pytest.mark.parametrize("value", ["off", "OFF", "0", "false", "no"])
def test_off_switch(value):
    client = FakeClient(_message({"act": RTA, "sections": ["48"], "search_text": None}))
    plan, stats = run(client, environ={"BOWEN_PLANNER": value})
    assert plan is None and stats.outcome == "disabled"
    assert client.messages.calls == []


def test_on_by_default():
    client = FakeClient(_message({"act": RTA, "sections": ["48"], "search_text": None}))
    plan, _ = run(client, environ={})
    assert plan is not None


def test_offline_stub_client_is_a_no_op(app_module):
    stub = app_module.STUB_CLIENT
    before = stub.beta.messages.last_request
    plan, stats = run(stub)
    assert plan is None and stats.outcome == "stub"
    assert stub.beta.messages.last_request is before   # the answer-call recorder is untouched


def test_none_client_is_a_no_op():
    plan, stats = run(None)
    assert plan is None and stats.outcome == "stub"


# --- Refusal --------------------------------------------------------------------------------

def test_refusal_returns_none():
    reply = _message(blocks=[], stop_reason="refusal")
    plan, stats = run(FakeClient(reply), "something the classifier declines")
    assert plan is None and stats.outcome == "refusal"


def test_refusal_with_schema_looking_text_still_returns_none():
    reply = _message({"act": RTA, "sections": ["48"], "search_text": None}, stop_reason="refusal")
    plan, stats = run(FakeClient(reply))
    assert plan is None and stats.outcome == "refusal"


# --- Prompt contents -----------------------------------------------------------------------

def test_history_is_included():
    client = FakeClient(_message({"act": ERA, "sections": ["114"], "search_text": None}))
    history = [
        {"role": "user", "content": "How long do I have to raise a personal grievance?"},
        {"role": "assistant", "content": "Under section 114 of the Employment Relations Act 2000, 90 days."},
    ]
    run(client, "what if i missed it by 2 weeks", history)
    user_msg = client.messages.calls[0]["messages"][0]["content"]
    assert "How long do I have to raise a personal grievance?" in user_msg
    assert "section 114 of the Employment Relations Act 2000" in user_msg
    assert "what if i missed it by 2 weeks" in user_msg
    assert user_msg.index("personal grievance?") < user_msg.index("what if i missed it")


def test_only_recent_history_is_sent_and_long_turns_are_clipped():
    client = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    history = [{"role": "user", "content": f"old message {i}"} for i in range(10)]
    history.append({"role": "assistant", "content": "x" * 5000})
    run(client, "and then?", history)
    user_msg = client.messages.calls[0]["messages"][0]["content"]
    assert "old message 0" not in user_msg and "old message 9" in user_msg
    assert len(user_msg) < 2500


def test_prompt_contains_the_held_acts_and_nothing_else():
    client = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    run(client)
    req = client.messages.calls[0]
    system = req["system"][0]
    assert system["cache_control"] == {"type": "ephemeral"}
    for title in (RTA, ERA, CRIMES):
        assert title in system["text"]
    assert "Not In The Registry Act 1999" not in system["text"]
    enum = req["output_config"]["format"]["schema"]["properties"]["act"]["anyOf"][0]["enum"]
    assert enum == sorted([CRIMES, ERA, RTA])


def test_request_shape_for_haiku():
    client = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    run(client)
    req = client.messages.calls[0]
    # No sampling params (400 on Haiku 5.5), no prefill, effort set explicitly.
    for k in ("temperature", "top_p", "top_k"):
        assert k not in req
    assert req["messages"][-1]["role"] == "user"
    assert req["output_config"]["effort"] == "low"
    assert req["thinking"] == {"type": "disabled"}


def test_system_prompt_is_byte_stable_across_calls():
    c1 = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    c2 = FakeClient(_message({"act": RTA, "sections": [], "search_text": None}))
    run(c1, "first question")
    run(c2, "a different question", [{"role": "user", "content": "earlier"}])
    assert c1.messages.calls[0]["system"] == c2.messages.calls[0]["system"]


def test_real_registry_prompt_lists_every_in_force_act():
    from backend.app.acts_registry import get_all_acts
    titles = {a["title"] for a in get_all_acts()}
    index = {t: frozenset({"1"}) for t in titles}
    client = FakeClient(_message({"act": None, "sections": [], "search_text": "x"}))
    plan_search(client, "q", [], sections_by_act=index, environ={})
    text = client.messages.calls[0]["system"][0]["text"]
    assert all(t in text for t in titles)


# --- merge_plan -----------------------------------------------------------------------------

def _plan(act_title=RTA, sections=("48",), text="landlord entry notice"):
    return SearchPlan(act=planner.act_base_name(act_title) if act_title else None,
                      act_title=act_title, sections=list(sections), search_text=text)


def test_merge_without_plan_is_todays_behaviour():
    m = merge_plan(None, "Residential Tenancies", ["48"])
    assert m.act_filter == "Residential Tenancies"
    assert m.extra_sections == [] and m.extra_query is None and not m.plan_act_used


def test_merge_by_default_keeps_todays_filter_on_the_users_words():
    m = merge_plan(_plan(), None)
    assert m.act_filter is None and not m.plan_act_used
    assert m.extra_sections == ["48"] and m.section_act_titles == [RTA]
    assert m.extra_query == "landlord entry notice"
    assert m.extra_query_act_filter == "Residential Tenancies"


def test_merge_keyword_act_wins_and_disagreeing_plan_sections_are_dropped():
    m = merge_plan(_plan(act_title=CRIMES, sections=["48"]), "Residential Tenancies")
    assert m.act_filter == "Residential Tenancies" and not m.plan_act_used
    assert m.extra_sections == []
    assert m.extra_query_act_filter == "Residential Tenancies"


def test_merge_caps_sections_and_skips_ones_the_user_named():
    m = merge_plan(_plan(sections=["48", "40", "22A"]), "Residential Tenancies", ["48"])
    assert m.extra_sections == ["40", "22A"]
    m = merge_plan(_plan(sections=["48", "40", "22A"]), None, max_plan_sections=1)
    assert m.extra_sections == ["48"]


def test_merge_can_let_plan_act_filter_the_users_query_when_none_detected():
    m = merge_plan(_plan(), None, plan_act_filters_user_query=True)
    assert m.act_filter == "Residential Tenancies" and m.plan_act_used
    m = merge_plan(_plan(), "Residential Tenancies", plan_act_filters_user_query=True)
    assert m.act_filter == "Residential Tenancies" and not m.plan_act_used


def test_merge_plan_with_text_only():
    m = merge_plan(_plan(act_title=None, sections=[], text="sick leave"), None)
    assert m.act_filter is None and m.extra_sections == []
    assert m.extra_query == "sick leave" and m.extra_query_act_filter is None
