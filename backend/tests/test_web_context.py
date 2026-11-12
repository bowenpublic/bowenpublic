"""Offline tests for backend/app/web_context.py (httpx.MockTransport; no network)."""

import asyncio
import json
import logging

import httpx
import pytest

from backend.app import web_context as wc


@pytest.fixture(autouse=True)
def clean_history():
    """Overrides conftest's autouse fixture: these tests do not need main.py."""
    yield


KEY = "pplx-test-SECRET-KEY-456"
QUESTION = "Is the Residential Tenancies Amendment Act 2024 in force?"
CLAUDE_ANSWER = "I hold the Residential Tenancies Act 1986 but didn't retrieve the section on this."
HISTORY_TEXT = "Earlier turn: my landlord kept my bond"


def cfg(mode="gap", timeout=12.0, key=KEY, domains=wc.NZ_DOMAINS):
    return wc.Config(mode=mode, model="perplexity/sonar", timeout_s=timeout, domains=domains,
                     provider="perplexity", api_key=key)


def pparse(payload, model, latency_ms):
    return wc.parse_response(payload, model, latency_ms, provider="perplexity")


def pplx_payload(text="The Residential Tenancies Amendment Act 2024 came into force on "
                      "30 January 2025 for most provisions [1]. Tenancy Services publishes "
                      "guidance on the changes [2].",
                 results=None, annotations=None, status="completed"):
    if results is None:
        results = [
            {"id": 1, "url": "https://www.tenancy.govt.nz/law-changes/", "title": "Law changes",
             "snippet": "s", "date": "2025-01-30"},
            {"id": 2, "url": "https://www.example.com/blog", "title": "A blog", "snippet": "s"},
            {"id": 3, "url": "https://www.legislation.govt.nz/act/public/2024/0001/latest/",
             "title": "Residential Tenancies Amendment Act 2024", "snippet": "s"},
        ]
    return {
        "id": "resp_1", "object": "response", "created_at": 1, "status": status,
        "model": "perplexity/sonar",
        "output": [
            {"type": "search_results", "queries": ["q"], "results": results},
            {"type": "message", "id": "m1", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": text,
                          "annotations": annotations or []}]},
        ],
        "usage": {"input_tokens": 120, "output_tokens": 80, "total_tokens": 200},
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

def test_missing_key_means_off():
    for env in ({}, {"PERPLEXITY_API_KEY": " "}, {"PERPLEXITY_API_KEY": "your-perplexity-key"},
                {"BOWEN_WEB_CONTEXT": "always"}):
        c = wc.load_config(env)
        assert c.mode == "off" and not c.enabled


def test_defaults_with_key():
    c = wc.load_config({"PERPLEXITY_API_KEY": KEY})
    assert c.mode == "gap" and c.enabled
    assert c.model == wc.DEFAULT_MODEL == "perplexity/sonar"
    assert c.timeout_s == 12.0 and c.domains == wc.NZ_DOMAINS
    assert len(wc.NZ_DOMAINS) <= 20
    assert KEY not in repr(c)


def test_env_overrides():
    c = wc.load_config({"PERPLEXITY_API_KEY": KEY, "BOWEN_WEB_CONTEXT": "Always",
                        "BOWEN_WEB_CONTEXT_MODEL": "openai/gpt-6-luna",
                        "BOWEN_WEB_CONTEXT_TIMEOUT": "6",
                        "BOWEN_WEB_CONTEXT_DOMAINS": "justice.govt.nz, nzlii.org,justice.govt.nz"})
    assert (c.mode, c.model, c.timeout_s) == ("always", "openai/gpt-6-luna", 6.0)
    assert c.domains == ("justice.govt.nz", "nzlii.org")
    assert wc.load_config({"PERPLEXITY_API_KEY": KEY,
                           "BOWEN_WEB_CONTEXT_DOMAINS": "none"}).domains == ()
    many = ",".join(f"d{i}.nz" for i in range(30))
    assert len(wc.load_config({"PERPLEXITY_API_KEY": KEY,
                               "BOWEN_WEB_CONTEXT_DOMAINS": many}).domains) == 20
    assert wc.load_config({"PERPLEXITY_API_KEY": KEY, "BOWEN_WEB_CONTEXT": "x"}).mode == "gap"
    assert wc.load_config({"PERPLEXITY_API_KEY": KEY, "BOWEN_WEB_CONTEXT": "off"}).mode == "off"


def test_missing_key_returns_none_without_calling_out():
    seen = []
    assert run(wc.fetch_web_context(QUESTION, config=cfg(key=""),
                                    transport=transport_returning(pplx_payload(), seen=seen))) is None
    assert run(wc.fetch_web_context(QUESTION, config=cfg(mode="off"),
                                    transport=transport_returning(pplx_payload(), seen=seen))) is None
    assert seen == []


def test_startup_log_once(caplog, monkeypatch):
    monkeypatch.setattr(wc, "_startup_logged", False)
    with caplog.at_level(logging.INFO, logger="bowen.web_context"):
        wc.log_startup(cfg(key=""))
        run(wc.fetch_web_context(QUESTION, config=cfg(key="")))
        run(wc.fetch_web_context(QUESTION, config=cfg(key="")))
    assert len([r for r in caplog.records if "web context" in r.getMessage()]) == 1


# --- should_fetch -------------------------------------------------------------

def sf(c, **kw):
    args = dict(query=QUESTION, is_legal_query=True, refused=False, sources_count=2,
                answer_text="Under section 18 the bond is 4 weeks' rent.")
    args.update(kw)
    return wc.should_fetch(c, **args)


def test_gap_mode():
    c = cfg("gap")
    assert not sf(c)                                     # cited answer, no gap
    assert sf(c, sources_count=0)                        # not-held path
    assert sf(c, answer_text=CLAUDE_ANSWER)              # answer says not retrieved
    assert sf(c, answer_text="I don't hold the Holidays Act 2003.")
    assert sf(c, answer_text="The definitions section was not retrieved.")
    assert sf(c, answer_text="That is not in the legislation Bowen holds.")
    assert sf(c, answer_text="I haven't stated the rule here because I didn't retrieve the "
                             "legislation text that governs this question.")


def test_always_mode():
    assert sf(cfg("always"))


def test_never_for_casual_refusal_empty_or_off():
    for c in (cfg("gap"), cfg("always")):
        assert not sf(c, is_legal_query=False, sources_count=0)
        assert not sf(c, refused=True, sources_count=0)
        assert not sf(c, query="  ", sources_count=0)    # attachment-only message
    assert not sf(cfg("off"), sources_count=0)
    assert not sf(cfg("always", key=""), sources_count=0)


def test_never_for_safety_answers():
    c = cfg("always")
    assert not sf(c, answer_text="If you are in danger call 111. You can call or text 1737.")
    assert not sf(c, answer_text="Women's Refuge 0800 733 843 can help.")
    # A section numbered 111 is not a phone number.
    assert sf(c, answer_text="Under section 111 of the Act the time limit is 90 days.")


# --- happy path and parsing ---------------------------------------------------

def test_happy_path():
    ctx = run(wc.fetch_web_context(QUESTION, config=cfg(),
                                   transport=transport_returning(pplx_payload())))
    assert ctx is not None
    assert "[1]" not in ctx.text and "30 January 2025" in ctx.text
    urls = [l.url for l in ctx.links]
    # NZ official domains first, then others; cited [1] before uncited [3].
    assert urls == ["https://www.tenancy.govt.nz/law-changes/",
                    "https://www.legislation.govt.nz/act/public/2024/0001/latest/",
                    "https://www.example.com/blog"]
    assert (ctx.model, ctx.tokens_in, ctx.tokens_out) == ("perplexity/sonar", 120, 80)


def test_annotations_used_and_links_capped():
    results = [{"id": i, "url": f"https://www.justice.govt.nz/p{i}", "title": f"T{i}",
                "snippet": "s"} for i in range(1, 8)]
    ann = [{"type": "url_citation", "url": "https://www.courtsofnz.govt.nz/judgment",
            "title": "Judgment", "start_index": 0, "end_index": 5}]
    ctx = pparse(pplx_payload(results=results, annotations=ann), "m", 1)
    assert len(ctx.links) == wc.MAX_LINKS
    assert ctx.links[0].url == "https://www.courtsofnz.govt.nz/judgment"


def test_no_links_returns_none():
    assert run(wc.fetch_web_context(QUESTION, config=cfg(),
                                    transport=transport_returning(pplx_payload(results=[])))) is None


def test_bad_urls_dropped():
    results = [{"id": 1, "url": "javascript:alert(1)", "title": "x", "snippet": "s"},
               {"id": 2, "url": "ftp://files.govt.nz/a", "title": "x", "snippet": "s"},
               {"id": 3, "url": "https://user:pw@evil.example/", "title": "x", "snippet": "s"},
               {"id": 4, "url": "not a url", "title": "x", "snippet": "s"},
               {"id": 5, "url": None, "title": "x", "snippet": "s"}]
    assert pparse(pplx_payload(results=results), "m", 1) is None


def test_url_with_parentheses_and_spaces_is_escaped():
    results = [{"id": 1, "url": "https://www.nzlii.org/nz/cases/A (B) case.html",
                "title": "Case [2024] NZSC 1", "snippet": "s"}]
    ctx = pparse(pplx_payload(results=results), "m", 1)
    url = ctx.links[0].url
    assert "(" not in url and ")" not in url and " " not in url
    assert "[" not in ctx.links[0].title and "]" not in ctx.links[0].title


def test_incomplete_or_empty_text_returns_none():
    assert pparse(pplx_payload(status="incomplete"), "m", 1) is None
    assert pparse(pplx_payload(text=""), "m", 1) is None
    assert pparse(pplx_payload(text="I think so. My view is yes."), "m", 1) is None
    assert pparse("not a dict", "m", 1) is None


# --- failures -----------------------------------------------------------------

def test_malformed_json():
    assert run(wc.fetch_web_context(QUESTION, config=cfg(),
                                    transport=transport_returning(raw=b"{bad json"))) is None


def test_unexpected_shape():
    for payload in ({"output": "nope"}, {"output": [1, 2, "x"]}, [], {"status": "failed"}):
        assert run(wc.fetch_web_context(QUESTION, config=cfg(),
                                        transport=transport_returning(payload))) is None


@pytest.mark.parametrize("status", [400, 401, 402, 429, 500])
def test_http_error(status):
    assert run(wc.fetch_web_context(QUESTION, config=cfg(),
                                    transport=transport_returning({"error": "x"}, status=status))) is None


def test_transport_timeout():
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)
    assert run(wc.fetch_web_context(QUESTION, config=cfg(),
                                    transport=httpx.MockTransport(handler))) is None


def test_overall_deadline():
    async def handler(request):
        await asyncio.sleep(2)
        return httpx.Response(200, json=pplx_payload())
    assert run(wc.fetch_web_context(QUESTION, config=cfg(timeout=0.05),
                                    transport=httpx.MockTransport(handler))) is None


def test_other_exception_never_raises():
    def handler(request):
        raise RuntimeError("boom")
    assert run(wc.fetch_web_context(QUESTION, config=cfg(),
                                    transport=httpx.MockTransport(handler))) is None


# --- request body -------------------------------------------------------------

def test_request_contains_only_the_question(caplog):
    seen = []
    with caplog.at_level(logging.DEBUG):
        run(wc.fetch_web_context(QUESTION, config=cfg(),
                                 transport=transport_returning(pplx_payload(), seen=seen)))
    assert len(seen) == 1
    req = seen[0]
    assert req.method == "POST" and str(req.url) == wc.API_URL
    assert req.headers["authorization"] == f"Bearer {KEY}"
    others = {k: v for k, v in req.headers.items() if k.lower() != "authorization"}
    assert KEY not in json.dumps(others) and KEY not in str(req.url)
    raw = req.content.decode()
    assert KEY not in raw and KEY not in caplog.text
    body = json.loads(raw)
    assert set(body) == {"model", "instructions", "input", "tools", "max_output_tokens"}
    assert body["input"] == QUESTION                      # a plain string: no history items
    assert body["instructions"] == wc.instructions_for("perplexity")
    assert "[n] markers" in body["instructions"] and "{cite}" not in body["instructions"]
    # Nothing from Claude's answer or the conversation history.
    for text in (CLAUDE_ANSWER, HISTORY_TEXT, "SOURCES", "assistant"):
        assert text not in raw
    tool = body["tools"][0]
    assert tool["type"] == "web_search" and tool["user_location"] == {"country": "NZ"}
    assert tool["filters"]["search_domain_filter"] == list(wc.NZ_DOMAINS)


def test_no_domain_filter_when_disabled():
    body = wc.build_request(cfg(domains=()), QUESTION)
    assert "filters" not in body["tools"][0]


def test_question_is_stripped_and_empty_question_skips():
    seen = []
    assert run(wc.fetch_web_context("   ", config=cfg(),
                                    transport=transport_returning(pplx_payload(), seen=seen))) is None
    assert seen == []


# --- cleaning and rendering ---------------------------------------------------

def test_clean_text_strips_html_markers_sources_and_voice():
    raw = ("<p>The Act is <b>in force</b> [1][2].</p>\n"
           "## Heading\n"
           "SOURCES: Residential Tenancies Act 1986 s 18\n"
           "**Sources:** none\n"
           "I am Bowen and I can help. As always, verify at legislation.govt.nz. "
           "See [this page](https://x.govt.nz) or https://y.govt.nz for more. "
           "&lt;script&gt;alert(1)&lt;/script&gt; Guidance was issued in 2025.")
    out = wc.clean_text(raw)
    low = out.lower()
    assert "<" not in out and ">" not in out and "script" not in low
    assert "[1]" not in out and "sources" not in low and "bowen" not in low
    assert "as always" not in low and "http" not in low and "#" not in out
    assert "The Act is in force." in out and "Guidance was issued in 2025." in out
    assert "See this page or for more." in out   # link text kept, URLs removed


def test_clean_text_word_cap():
    long = " ".join(f"Sentence {i} has five words." for i in range(60))
    out = wc.clean_text(long)
    assert len(out.split()) <= wc.MAX_WORDS
    one = " ".join(["word"] * 300) + "."
    out = wc.clean_text(one)
    assert len(out.split()) == wc.MAX_WORDS and out.endswith("…")


def test_render_block():
    ctx = pparse(pplx_payload(), "m", 1)
    block = wc.render_block(ctx)
    lines = block.split("\n")
    assert lines[0] == "---"
    assert f"**{wc.HEADING}**" in block
    assert block.rstrip().endswith(f"_{wc.CLOSING}_")
    assert block.count("\n- [") == 3
    assert "](https://www.tenancy.govt.nz/law-changes/)" in block
    assert "SOURCES" not in block.upper().replace("SOURCES ", "")  # no SOURCES: line
    assert not any(l.lower().startswith("sources") for l in lines)
    body = block.split(f"**{wc.HEADING}**")[1].split("\n- [")[0]
    assert len(body.split()) <= wc.MAX_WORDS


def test_render_block_empty_cases():
    assert wc.render_block(None) == ""
    assert wc.render_block(wc.WebContext("text.", [], "m", 1, 1, 1)) == ""
    assert wc.render_block(wc.WebContext("", [wc.Link("t", "https://a.govt.nz/")], "m", 1, 1, 1)) == ""
    # A hand-built context with an unsafe link renders nothing for that link.
    assert wc.render_block(wc.WebContext("Fine text.", [wc.Link("t", "javascript:x")],
                                         "m", 1, 1, 1)) == ""


def test_render_block_recleans_hand_built_text():
    ctx = wc.WebContext("<b>Bold</b> claim [3]. SOURCES: none", [wc.Link("T", "https://a.govt.nz/")],
                        "m", 1, 1, 1)
    block = wc.render_block(ctx)
    assert "<b>" not in block and "[3]" not in block and "SOURCES" not in block


def test_log_fields():
    ctx = pparse(pplx_payload(), "m", 7)
    f = wc.log_fields(ctx)
    json.dumps(f)
    assert f["latency_ms"] == 7 and len(f["links"]) == 3
    assert wc.log_fields(None) == {}


@pytest.mark.parametrize("answer", [
    # The prompt's rule 2 and AVAILABLE ACTS wording, and main.py's footer (13 Nov).
    "Section 6 wasn't among the sections I pulled for this answer. Ask me 'what does section 6 "
    "of the Lawyers and Conveyancers Act say' and I'll fetch it.",
    "I hold the Residential Tenancies Act 1986, but the section that deals with this wasn't "
    "among the sections I pulled for this answer.",
    "Sections 21 and 22 weren't among the sections I pulled for this answer.",
    "Those sections weren’t among those I pulled.",
    "The relevant section was not among the sections I pulled for this answer.",
    "I haven't stated the rule here because the legislation text that governs this question "
    "wasn't among the sections I pulled for this answer.",
])
def test_gap_mode_recognises_the_new_wording(answer):
    assert wc.answer_reports_gap(answer)
    assert sf(cfg("gap"), answer_text=answer)


def test_gap_wording_does_not_fire_on_an_ordinary_answer():
    assert not wc.answer_reports_gap("Under section 48 the landlord must give 48 hours' notice, "
                                     "among the sections of the Act that deal with entry.")


def test_http_error_status_logged_once(caplog, monkeypatch):
    """A key without paid credits answers 403 on every request: one warning."""
    monkeypatch.setattr(wc, "_statuses_logged", set())
    with caplog.at_level(logging.DEBUG, logger="bowen.web_context"):
        for _ in range(3):
            assert run(wc.fetch_web_context(QUESTION, config=cfg(), transport=transport_returning(
                {"error": {"type": "restricted_api_key"}}, status=403))) is None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "403" in r.getMessage()]
    assert len(warnings) == 1 and "paid credits" in warnings[0].getMessage()
    assert KEY not in caplog.text


# =============================================================================
# Provider selection
# =============================================================================

OKEY = "sk-test-SECRET-OPENAI-789"


@pytest.mark.parametrize("env, provider, enabled", [
    ({}, "openai", False),
    ({"OPENAI_API_KEY": OKEY}, "openai", True),
    ({"PERPLEXITY_API_KEY": KEY}, "perplexity", True),
    ({"OPENAI_API_KEY": OKEY, "PERPLEXITY_API_KEY": KEY}, "openai", True),
    ({"OPENAI_API_KEY": "your-openai-key-here", "PERPLEXITY_API_KEY": KEY}, "perplexity", True),
    ({"OPENAI_API_KEY": " ", "PERPLEXITY_API_KEY": "your-perplexity-key"}, "openai", False),
    # The override wins, and is on only with that provider's own key.
    ({"OPENAI_API_KEY": OKEY, "PERPLEXITY_API_KEY": KEY,
      "BOWEN_WEB_CONTEXT_PROVIDER": "Perplexity"}, "perplexity", True),
    ({"OPENAI_API_KEY": OKEY, "BOWEN_WEB_CONTEXT_PROVIDER": "perplexity"}, "perplexity", False),
    ({"PERPLEXITY_API_KEY": KEY, "BOWEN_WEB_CONTEXT_PROVIDER": "openai"}, "openai", False),
    # An unknown value is ignored: the default applies.
    ({"PERPLEXITY_API_KEY": KEY, "BOWEN_WEB_CONTEXT_PROVIDER": "bing"}, "perplexity", True),
])
def test_provider_selection(env, provider, enabled):
    c = wc.load_config(env)
    assert (c.provider, c.enabled) == (provider, enabled)
    if not enabled:
        assert c.mode == "off"
    expected_key = {"openai": OKEY, "perplexity": KEY}[provider] if enabled else ""
    assert c.api_key == expected_key
    assert OKEY not in repr(c) and KEY not in repr(c)


def test_openai_defaults():
    c = wc.load_config({"OPENAI_API_KEY": OKEY})
    assert (c.mode, c.model, c.timeout_s) == ("gap", "gpt-6.1-sol", wc.OPENAI_DEFAULT_TIMEOUT_S)
    assert c.domains == wc.NZ_DOMAINS
    many = ",".join(f"d{i}.nz" for i in range(130))
    c = wc.load_config({"OPENAI_API_KEY": OKEY, "BOWEN_WEB_CONTEXT_DOMAINS": many,
                        "BOWEN_WEB_CONTEXT_MODEL": "gpt-6.1-terra", "BOWEN_WEB_CONTEXT_TIMEOUT": "9"})
    assert len(c.domains) == wc.OPENAI_MAX_DOMAINS == 100
    assert (c.model, c.timeout_s) == ("gpt-6.1-terra", 9.0)
    assert wc.load_config({"OPENAI_API_KEY": OKEY,
                           "BOWEN_WEB_CONTEXT_DOMAINS": "none"}).domains == ()


def test_startup_log_names_the_provider(caplog, monkeypatch):
    monkeypatch.setattr(wc, "_startup_logged", False)
    with caplog.at_level(logging.INFO, logger="bowen.web_context"):
        wc.log_startup(wc.load_config({"OPENAI_API_KEY": OKEY}))
    assert "provider=openai" in caplog.text and OKEY not in caplog.text


# =============================================================================
# OpenAI: request, parsing, failures
# =============================================================================

def ocfg(mode="gap", timeout=20.0, key=OKEY, domains=wc.NZ_DOMAINS):
    return wc.Config(mode=mode, model="gpt-6.1-sol", timeout_s=timeout, domains=domains,
                     provider="openai", api_key=key)


# A real response (13 Nov 2026, gpt-6.1-sol, NZ domain filter, question:
# "my landlord just let himself into my flat yesterday ... how much notice is he
# ment to give??"), trimmed: ids shortened, action.sources emptied (they are
# only returned with include=["web_search_call.action.sources"]), shape kept.
OPENAI_REAL = {
    "id": "resp_0b18ae62", "object": "response", "created_at": 1794518386,
    "status": "completed", "error": None, "incomplete_details": None,
    "model": "gpt-6.1-sol", "store": False, "tool_choice": "required",
    "output": [
        {"id": "ws_1", "type": "web_search_call", "status": "completed",
         "action": {"type": "search",
                    "queries": ["site.tenancy.govt.nz landlord access property 48 hours 24 hours "
                                "notice entry"],
                    "query": "site.tenancy.govt.nz landlord access property 48 hours 24 hours "
                             "notice entry",
                    "sources": []}},
        {"id": "ws_2", "type": "web_search_call", "status": "completed",
         "action": {"type": "open_page",
                    "url": "https://www.tenancy.govt.nz/maintenance-and-inspections/access/",
                    "sources": []}},
        {"id": "msg_1", "type": "message", "status": "completed", "phase": "final_answer",
         "role": "assistant",
         "content": [{
             "type": "output_text", "logprobs": [],
             "annotations": [
                 {"type": "url_citation", "end_index": 377, "start_index": 254,
                  "title": "Residential Tenancy Agreement",
                  "url": "https://www.tenancy.govt.nz/assets/forms-templates/"
                         "residential-tenancy-agreement.pdf?utm_source=openai"},
                 {"type": "url_citation", "end_index": 689, "start_index": 587,
                  "title": "Access » Tenancy Services",
                  "url": "https://www.tenancy.govt.nz/maintenance-and-inspections/access/"
                         "?utm_source=openai"}],
             "text": "Tenancy Services says landlords generally need at least 48 hours’ notice "
                     "for an inspection, or 24 hours for necessary repairs or maintenance. These "
                     "visits must be between 8 am and 7 pm. A tenant being away at work does not "
                     "remove the notice requirement. ([tenancy.govt.nz](https://www.tenancy.govt.nz"
                     "/assets/forms-templates/residential-tenancy-agreement.pdf?utm_source=openai)) "
                     "Entry without notice can be allowed in an emergency, under a Tribunal order, "
                     "or with the tenant’s consent given at or immediately before entry. Without "
                     "a valid exception, an unannounced entry may be unlawful. "
                     "([tenancy.govt.nz](https://www.tenancy.govt.nz/maintenance-and-inspections/"
                     "access/?utm_source=openai))"}]},
    ],
    "usage": {"input_tokens": 9126,
              "input_tokens_details": {"cache_write_tokens": 34, "cached_tokens": 4635},
              "output_tokens": 214, "output_tokens_details": {"reasoning_tokens": 68},
              "total_tokens": 9340},
}

LANDLORD_Q = ("my landlord just let himself into my flat yesterday while i was at work, didnt "
              "tell me or anything. how much notice is he ment to give??")


def openai_payload(**changes):
    p = json.loads(json.dumps(OPENAI_REAL))
    p.update(changes)
    return p


def test_fixture_offsets_match_the_real_text():
    part = OPENAI_REAL["output"][2]["content"][0]
    for a in part["annotations"]:
        span = part["text"][a["start_index"]:a["end_index"]]
        assert span.startswith("([tenancy.govt.nz](") and span.endswith("))")


def test_openai_request_body(caplog):
    seen = []
    with caplog.at_level(logging.DEBUG):
        ctx = run(wc.fetch_web_context(LANDLORD_Q, config=ocfg(),
                                       transport=transport_returning(OPENAI_REAL, seen=seen)))
    assert ctx is not None and len(seen) == 1
    req = seen[0]
    assert req.method == "POST" and str(req.url) == wc.OPENAI_API_URL
    assert req.headers["authorization"] == f"Bearer {OKEY}"
    others = {k: v for k, v in req.headers.items() if k.lower() != "authorization"}
    raw = req.content.decode()
    assert OKEY not in json.dumps(others) and OKEY not in str(req.url)
    assert OKEY not in raw and OKEY not in caplog.text
    body = json.loads(raw)
    assert set(body) == {"model", "instructions", "input", "tools", "tool_choice", "reasoning",
                         "max_output_tokens", "store"}
    assert body["input"] == LANDLORD_Q                     # the question only, a plain string
    for text in (CLAUDE_ANSWER, HISTORY_TEXT, "SOURCES", "assistant"):
        assert text not in raw
    assert body["store"] is False
    assert body["tool_choice"] == "required"
    assert body["model"] == "gpt-6.1-sol" and body["reasoning"] == {"effort": "low"}
    assert body["instructions"] == wc.instructions_for("openai")
    assert "[n] markers" not in body["instructions"].replace("Do not add [n] markers", "")
    assert "third person" in body["instructions"] and "100 words" in body["instructions"]
    (tool,) = body["tools"]
    assert tool["type"] == "web_search"
    assert tool["user_location"] == {"type": "approximate", "country": "NZ"}
    assert tool["search_context_size"] == "low"
    assert tool["filters"] == {"allowed_domains": list(wc.NZ_DOMAINS)}


def test_openai_no_domain_filter_when_none():
    body = wc.build_request(ocfg(domains=()), QUESTION)
    assert "filters" not in body["tools"][0]


def test_openai_happy_path_real_shape():
    ctx = run(wc.fetch_web_context(LANDLORD_Q, config=ocfg(),
                                   transport=transport_returning(OPENAI_REAL)))
    assert ctx.provider == "openai" and ctx.model == "gpt-6.1-sol"
    assert (ctx.tokens_in, ctx.tokens_out) == (9126, 214)
    # Citation markup gone, prose kept.
    for gone in ("](", "([", "utm_source", "http", "tenancy.govt.nz)"):
        assert gone not in ctx.text
    assert ctx.text.startswith("Tenancy Services says landlords generally need at least 48")
    assert ctx.text.endswith("an unannounced entry may be unlawful.")
    assert "remove the notice requirement. Entry without notice" in ctx.text
    # Links from the url_citation annotations, tracking parameter removed, in order.
    assert [(l.title, l.url) for l in ctx.links] == [
        ("Residential Tenancy Agreement",
         "https://www.tenancy.govt.nz/assets/forms-templates/residential-tenancy-agreement.pdf"),
        ("Access » Tenancy Services",
         "https://www.tenancy.govt.nz/maintenance-and-inspections/access/"),
    ]
    block = wc.render_block(ctx)
    assert block.startswith("---\n\n**" + wc.HEADING + "**")
    assert "- [Access » Tenancy Services](https://www.tenancy.govt.nz/maintenance-and-inspections/access/)" in block
    assert "utm_source" not in block and block.endswith(f"_{wc.CLOSING}_")
    f = wc.log_fields(ctx)
    json.dumps(f)
    assert f["provider"] == "openai" and len(f["links"]) == 2


def test_openai_duplicate_citations_and_other_params_kept():
    p = openai_payload()
    part = p["output"][2]["content"][0]
    part["annotations"][0]["url"] = ("https://www.tenancy.govt.nz/maintenance-and-inspections/"
                                     "access/?utm_source=openai")
    part["annotations"].append({"type": "url_citation", "start_index": 0, "end_index": 5,
                                "title": "Case", "url": "https://www.nzlii.org/x?id=3&utm_source=openai"})
    ctx = wc.parse_response(p, "m", 1, provider="openai")
    assert [l.url for l in ctx.links] == [
        "https://www.tenancy.govt.nz/maintenance-and-inspections/access/",
        "https://www.nzlii.org/x?id=3"]
    # The span 0..5 ("Tenan") is prose, not link markup: never cut.
    assert ctx.text.startswith("Tenancy Services says")


def test_openai_no_citations_returns_none():
    p = openai_payload()
    p["output"][2]["content"][0]["annotations"] = []
    assert wc.parse_response(p, "m", 1, provider="openai") is None
    # web_search_call items alone (no message) are not a result either.
    assert wc.parse_response(openai_payload(output=OPENAI_REAL["output"][:2]), "m", 1,
                             provider="openai") is None
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(),
                                    transport=transport_returning(p))) is None


def test_openai_refusal_returns_none():
    p = openai_payload()
    p["output"][2]["content"] = [{"type": "refusal", "refusal": "I can't help with that."}]
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(),
                                    transport=transport_returning(p))) is None
    # A refusal next to text is still a refusal.
    p = openai_payload()
    p["output"][2]["content"].append({"type": "refusal", "refusal": "No."})
    assert wc.parse_response(p, "m", 1, provider="openai") is None


def test_openai_incomplete_returns_none():
    p = openai_payload(status="incomplete",
                       incomplete_details={"reason": "max_output_tokens"})
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(),
                                    transport=transport_returning(p))) is None
    for status in ("failed", "in_progress", "cancelled"):
        assert wc.parse_response(openai_payload(status=status), "m", 1, provider="openai") is None


def test_openai_only_final_answer_phase_used():
    p = openai_payload()
    p["output"].insert(0, {"type": "message", "phase": "commentary", "content": [
        {"type": "output_text", "text": "Searching tenancy.govt.nz now.",
         "annotations": [{"type": "url_citation", "url": "https://evil.example/",
                          "title": "x", "start_index": 0, "end_index": 3}]}]})
    ctx = wc.parse_response(p, "m", 1, provider="openai")
    assert "Searching" not in ctx.text
    assert all("evil.example" not in l.url for l in ctx.links)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_openai_http_error(status):
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(), transport=transport_returning(
        {"error": {"message": "x"}}, status=status))) is None


def test_openai_timeouts_and_errors():
    def slow_transport(request):
        raise httpx.ReadTimeout("slow", request=request)
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(),
                                    transport=httpx.MockTransport(slow_transport))) is None

    async def hang(request):
        await asyncio.sleep(2)
        return httpx.Response(200, json=OPENAI_REAL)
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(timeout=0.05),
                                    transport=httpx.MockTransport(hang))) is None
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(),
                                    transport=transport_returning(raw=b"<html>"))) is None


def test_openai_missing_key_never_calls_out():
    seen = []
    assert run(wc.fetch_web_context(QUESTION, config=ocfg(key=""),
                                    transport=transport_returning(OPENAI_REAL, seen=seen))) is None
    assert seen == []


def test_perplexity_selected_by_env_still_works():
    c = wc.load_config({"OPENAI_API_KEY": OKEY, "PERPLEXITY_API_KEY": KEY,
                        "BOWEN_WEB_CONTEXT_PROVIDER": "perplexity"})
    seen = []
    ctx = run(wc.fetch_web_context(QUESTION, config=c,
                                   transport=transport_returning(pplx_payload(), seen=seen)))
    assert str(seen[0].url) == wc.API_URL
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"
    assert "store" not in json.loads(seen[0].content)   # Perplexity body unchanged
    assert ctx.provider == "perplexity" and wc.log_fields(ctx)["provider"] == "perplexity"
    assert ctx.links[0].url == "https://www.tenancy.govt.nz/law-changes/"


def test_clean_text_strips_openai_inline_citations():
    raw = ("The rate is $23.95 an hour ([employment.govt.nz](https://www.employment.govt.nz/"
           "a?utm_source=openai)). Two at once ([a.govt.nz](https://a.govt.nz/), "
           "[b.govt.nz](https://b.govt.nz/)) here [1].")
    out = wc.clean_text(raw)
    assert out == "The rate is $23.95 an hour. Two at once here."
