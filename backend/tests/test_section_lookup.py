"""
test_section_lookup.py — the Lawyers and Conveyancers Act ticket
(docs/2026-11-12-PRODUCT-TICKET-lawyers-act-retrieval.md).

1. A question that names section numbers, with an Act in play, gets exactly
   those sections, pinned ahead of the ranked results.
2. A follow-up that names sections but no Act uses the Act from an earlier
   turn of the same session, through both /chat and /chat/stream.
3. "Why can you not retrieve them?" no longer runs a search.

The `wilkinson-smith-lca-5` tests need the Lawyers and Conveyancers Act, which
is not in the mini fixture; they skip there and run against the full index
(EMBEDDINGS_DIR=data/embeddings). The mini equivalents use the Residential
Tenancies Act.
"""

import pytest

from backend.app import acts_registry as reg

RTA = "Residential Tenancies Act 1986"
LCA = "Lawyers and Conveyancers Act 2006"


# --- The section-reference parser --------------------------------------------

@pytest.mark.parametrize("query,expected", [
    ("Please answer the question again and use sections 25(2) and 27", ["25", "27"]),
    ("What do sections 25 and 27 of the Lawyers and Conveyancers Act say?", ["25", "27"]),
    ("section 25", ["25"]),
    ("s 25", ["25"]),
    ("s27", ["27"]),
    ("s. 27(1)(a)", ["27"]),
    ("ss 24 to 26", ["24", "25", "26"]),
    ("ss 24-26", ["24", "25", "26"]),
    ("section 22A", ["22A"]),
    ("section 42b of the RTA", ["42B"]),
    ("sections 21, 22 and 23", ["21", "22", "23"]),
    ("What about s 25 and s 27?", ["25", "27"]),
    ("Tell me about s103 of the ERA", ["103"]),
    ("s 5 to 100", ["5", "100"]),  # a wide range keeps its ends only
])
def test_parser_finds_section_refs(app_module, query, expected):
    assert app_module.parse_section_refs(query) == expected


@pytest.mark.parametrize("query", [
    "I got a 90 day notice from my landlord",
    "What is the purpose of the Privacy Act 2020?",
    "it's 25 degrees and the heat pump is broken",
    "The tenancy started in 2019 and rent is 450 a week",
    "pages 25 to 27 of my contract",
    "the sections are long",
    "section 2020",
    "on the 25th of March",
    "s 25th",
    "Why can you not retrieve them?",
])
def test_parser_ignores_ordinary_numbers(app_module, query):
    assert app_module.parse_section_refs(query) == []


def test_parser_caps_the_number_of_sections(app_module):
    refs = app_module.parse_section_refs("sections 1, 2, 3, 4, 5, 6, 7, 8 and 9")
    assert len(refs) == app_module.MAX_EXPLICIT_SECTIONS


# --- Lookup with a detected Act (mini fixture) -------------------------------

def _search(app_module, q, act=None):
    act = act if act is not None else reg.detect_act_from_query(q)
    return app_module.search_similar(q, top_k=6, act_filter=act)


def test_named_sections_come_first_and_pinned(app_module):
    q = "What do sections 23 and 42B(1) of the Residential Tenancies Act say?"
    results = _search(app_module, q)
    assert [(r["act_title"], r["section_number"]) for r in results[:2]] == [(RTA, "23"), (RTA, "42B")]
    assert results[0]["pinned"] and results[1]["pinned"]
    assert {r["act_title"] for r in results} == {RTA}
    assert len(results) <= 6


def test_long_section_keeps_its_best_chunks_only(app_module):
    """RTA s 77 has 9 chunks in the fixture; it may not take the whole answer."""
    q = "What does section 77 of the Residential Tenancies Act say?"
    results = _search(app_module, q)
    s77 = [r for r in results if r["section_number"] == "77"]
    assert results[0]["section_number"] == "77"
    assert len([r for r in s77 if r["pinned"]]) == app_module.MAX_CHUNKS_PER_SECTION


def test_range_is_expanded(app_module):
    results = _search(app_module, "What do ss 17 to 19 of the Residential Tenancies Act say?")
    assert [r["section_number"] for r in results[:3]] == ["17", "18", "19"]


def test_no_act_no_lookup(app_module):
    """With no Act in play, whose "section 23" is meant is unknown: unchanged."""
    q = "What does section 23 say?"
    assert reg.detect_act_from_query(q) is None
    assert not any(r["pinned"] for r in _search(app_module, q))


def test_missing_section_falls_back_to_ranked(app_module):
    results = _search(app_module, "What does section 999 of the Residential Tenancies Act say?")
    assert results and all(r["act_title"] == RTA and not r["pinned"] for r in results)


# --- Carry-over through the real endpoints -----------------------------------

@pytest.fixture
def spy(app_module, monkeypatch):
    """Record what each request's retrieval and footer were given."""
    calls = {"retrieve": [], "footer": []}
    real_retrieve, real_footer = app_module._retrieve_for_query, app_module.footer_acts

    def retrieve(query, detected_act, session_id):
        out = real_retrieve(query, detected_act, session_id)
        calls["retrieve"].append({"query": query, "act": detected_act,
                                  "results": out[1], "context": out[2]})
        return out

    def footer(query, detected_act=None):
        calls["footer"].append(detected_act)
        return real_footer(query, detected_act)

    monkeypatch.setattr(app_module, "_retrieve_for_query", retrieve)
    monkeypatch.setattr(app_module, "footer_acts", footer)
    return calls


def _send(client, path, message, session_id):
    response = client.post(path, json={"message": message, "session_id": session_id})
    assert response.status_code == 200
    return response


def _pairs(results):
    return [(r["act_title"], r["section_number"]) for r in results]


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
def test_follow_up_carries_the_act(client, spy, path):
    sid = f"carry-{path}"
    _send(client, path, "What does the Residential Tenancies Act say about bonds?", sid)
    _send(client, path, "Please answer the question again and use sections 23 and 42B(1)", sid)

    turn = spy["retrieve"][-1]
    assert turn["act"] == "Residential Tenancies"
    assert _pairs(turn["results"])[:2] == [(RTA, "23"), (RTA, "42B")]
    assert {r["act_title"] for r in turn["results"]} == {RTA}
    assert f"MATCH THIS QUESTION: {RTA}" in turn["context"]
    assert spy["footer"][-1] == "Residential Tenancies"


def test_carry_only_applies_to_section_follow_ups(client, spy):
    sid = "carry-narrow"
    _send(client, "/chat", "What does the Residential Tenancies Act say about bonds?", sid)
    _send(client, "/chat", "What is the purpose of the Privacy Act 2020?", sid)
    assert spy["retrieve"][-1]["act"] == "Privacy"
    _send(client, "/chat", "Can my employer read my emails?", sid)
    assert spy["retrieve"][-1]["act"] is None


def test_carry_is_per_session(client, spy):
    _send(client, "/chat", "What does the Residential Tenancies Act say about bonds?", "carry-a")
    _send(client, "/chat", "Please use sections 23 and 42B", "carry-b")
    assert spy["retrieve"][-1]["act"] is None


@pytest.mark.parametrize("path", ["/session/{}", "/api/v1/session/{}"])
def test_session_clear_forgets_the_act(client, app_module, spy, path):
    sid = "carry-clear"
    _send(client, "/chat", "What does the Residential Tenancies Act say about bonds?", sid)
    assert app_module.session_acts.get(sid) == "Residential Tenancies"
    assert client.delete(path.format(sid)).status_code == 200
    assert sid not in app_module.session_acts
    _send(client, "/chat", "Please use sections 23 and 42B", sid)
    assert spy["retrieve"][-1]["act"] is None


# --- Item 3: a question about Bowen itself does not search -------------------

def test_why_can_you_not_skips_retrieval(client, spy):
    sid = "why-not"
    _send(client, "/chat", "What does the Residential Tenancies Act say about bonds?", sid)
    _send(client, "/chat", "Why can you not retrieve them?", sid)
    assert spy["retrieve"][-1]["results"] == []


@pytest.mark.parametrize("query", [
    "Why can you not evict a tenant in winter?",
    "Why can you not see section 23?",
    "Can you explain the bond rules?",
])
def test_why_can_you_keeps_real_legal_questions(app_module, query):
    assert app_module._is_legal_query(query, reg.detect_act_from_query(query))


# --- Regression set wilkinson-smith-lca-5 (full index) -----------------------

WILKINSON_SMITH_LCA_5 = [
    "What limits apply to a legal AI answering legal questions without breaching the "
    "prohibition on non-lawyers giving legal advice under the Lawyers and Conveyancers Act 2006?",
    "Is it lawful for an accountant to give legal advice if they do not use a lawyer's title?",
    "Please answer the question again and use sections 25(2) and 27",
    "Why can you not retrieve them?",
    "What do sections 25 and 27 of the Lawyers and Conveyancers Act say?",
]


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
def test_wilkinson_smith_lca_5(client, spy, fixture_acts, path):
    if LCA not in fixture_acts:
        pytest.skip(f"{LCA} is not in the loaded index (run with EMBEDDINGS_DIR=data/embeddings)")
    sid = f"wilkinson-smith-lca-5-{path}"
    for message in WILKINSON_SMITH_LCA_5:
        _send(client, path, message, sid)
    turns = spy["retrieve"]
    assert len(turns) == 5

    # Turn 3: no Act named, so the Act comes from turn 2.
    t3 = turns[2]
    assert t3["act"] == "Lawyers and Conveyancers"
    assert _pairs(t3["results"])[:2] == [(LCA, "25"), (LCA, "27")]
    assert {r["act_title"] for r in t3["results"]} == {LCA}

    # Turn 4: a question about Bowen; no unrelated Acts are handed over.
    assert turns[3]["results"] == []

    # Turn 5: both named sections, first.
    assert _pairs(turns[4]["results"])[:2] == [(LCA, "25"), (LCA, "27")]


def test_named_section_comes_only_from_the_named_act(app_module, fixture_acts):
    """The "Crimes" filter is a substring and also admits the International
    Crimes and International Criminal Court Act; a lookup by number must not
    bring back that Act's s 48 (audit, 12 Nov)."""
    icc = "International Crimes and International Criminal Court Act 2000"
    if "Crimes Act 1961" not in fixture_acts or icc not in fixture_acts:
        pytest.skip("needs the Crimes Act and the International Crimes Act in the index")
    results = app_module.search_similar("What does section 48 of the Crimes Act say?",
                                        top_k=6, act_filter="Crimes")
    named = [r for r in results if r["section_number"].strip() == "48"]
    assert named and results[0]["act_title"] == "Crimes Act 1961"
    assert all(r["act_title"] == "Crimes Act 1961" for r in named)


# --- fetch_section_text: the tool's lookup (13 Nov) ----------------------------

@pytest.mark.parametrize("act,section", [
    (RTA, "77"),
    ("Residential Tenancies Act", "77"),     # no year
    ("the Residential Tenancies Act 1986", "s 77"),
    ("RTA", "section 77(2)(a)"),            # short name; subsections dropped
])
def test_fetch_finds_every_chunk_in_order(app_module, act, section):
    text, result = app_module.fetch_section_text(act, section)
    rows = [i for i, m in enumerate(app_module.metadata)
            if m["act_title"] == RTA and m["section_number"].strip() == "77"]
    assert len(rows) > 2
    assert result["text"] == " ".join(app_module.metadata[i]["text"] for i in rows)
    assert result["act_title"] == RTA and result["section_number"] == "77"
    assert result["fetched"] is True
    assert set(app_module._source_from_result(result)) == {
        "act_title", "section_number", "section_heading", "url", "excerpt", "score"}
    assert text.startswith("FETCHED FROM DATABASE")
    assert f'"{RTA} s 77"' in text and "**Section 77 - 77 Jurisdiction of Tribunal**" in text


def test_fetch_uses_the_same_row_lookup_as_named_sections(app_module):
    """Both go through _section_rows: same rows for the same (act, section)."""
    by_lookup = app_module._section_rows({"77"}, lambda i, m: m["act_title"] == RTA)["77"]
    _, result = app_module.fetch_section_text(RTA, "77")
    assert result["text"].startswith(app_module.metadata[by_lookup[0]]["text"])


def test_fetch_unknown_section(app_module):
    text, result = app_module.fetch_section_text(RTA, "999")
    assert result is None
    assert text.startswith("NO SUCH SECTION") and "999" in text


def test_fetch_act_not_held(app_module):
    text, result = app_module.fetch_section_text("Holidays Act 2003", "16")
    assert result is None and text.startswith("NOT HELD")
    assert "Holidays Act 2003" in text


def test_fetch_repealed_act_says_so(app_module):
    title = sorted(app_module.REPEALED_TITLES)[0]
    text, result = app_module.fetch_section_text(title, "1")
    assert result is None
    assert text.startswith("NOT HELD") and "repealed" in text


def test_fetch_ambiguous_act_lists_only_held_titles(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_corpus_titles",
                        lambda: (["Crimes Act 1908", "Crimes Act 1961"], {}))
    text, result = app_module.fetch_section_text("Crimes Act", "1")
    assert result is None and text.startswith("NOT FOUND")
    assert "Crimes Act 1908; Crimes Act 1961" in text


def test_long_section_is_capped_and_find_picks_the_part(app_module, monkeypatch):
    rows = [i for i, m in enumerate(app_module.metadata)
            if m["act_title"] == RTA and m["section_number"].strip() == "77"]
    texts = [app_module.metadata[i]["text"] for i in rows]
    cap = max(len(a) + len(b) for a, b in zip(texts, texts[1:])) + 20
    assert sum(len(t) for t in texts) > cap
    monkeypatch.setattr(app_module, "MAX_FETCH_CHARS", cap)
    # Without find: the start, and a note on how to get the rest.
    _, start = app_module.fetch_section_text(RTA, "77")
    assert start["text"].startswith(texts[0]) and len(start["text"]) <= app_module.MAX_FETCH_CHARS + 20
    text, _ = app_module.fetch_section_text(RTA, "77")
    assert "only its start is shown" in text
    # With find: the chunk holding the phrase, and the one after it.
    k = len(texts) - 3
    phrase = " ".join(texts[k].split()[5:10])
    assert phrase and all(phrase not in t for t in texts[:k])
    text, picked = app_module.fetch_section_text(RTA, "77", find=phrase.upper())
    assert picked["text"].startswith("[...] " + texts[k])
    assert texts[k + 1][:40] in picked["text"]
    assert f'containing "{phrase.upper()}"' in text


def test_fetch_find_is_ignored_when_the_section_fits(app_module):
    _, whole = app_module.fetch_section_text(RTA, "18")
    _, found = app_module.fetch_section_text(RTA, "18", find="not in the text at all")
    assert whole["text"] == found["text"]
