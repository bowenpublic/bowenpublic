"""
test_answer_gate.py — the pre-launch testing gate (2026-11-01).

See docs/2026-11-01-PRODUCT-TICKET-testing-gate.md. Three changes are locked
here, all offline (stub LLM, no network):

  1. Sources shown are the sections the answer used: finalise_answer() parses
     the model's trailing SOURCES line and keeps only entries that name a
     retrieved excerpt. The SOURCES line never reaches a streaming client.
  2. Never answer from memory: no "general knowledge" instruction survives, and
     a legal answer with no usable source carries NOT_HELD_FOOTER.
  3. Wholly repealed Acts are out of the index, the registry's detection and
     /acts; a question naming one gets a repeal note.
"""

import json

import numpy as np
import pytest

RTA = "Residential Tenancies Act 1986"
HDCA = "Harmful Digital Communications Act 2015"


def result(act, section, heading="Heading", text="Excerpt text.", score=0.5):
    return {
        "text": text, "act_title": act, "act_short_name": "",
        "section_number": section, "section_heading": heading,
        "section_url": f"https://example.test/{section}", "act_url": "https://example.test/act",
        "score": score,
    }


@pytest.fixture
def results():
    return [
        result(RTA, "18", "Bond not to exceed 4 weeks' rent"),
        result(RTA, "42B", "Tenant may make minor changes"),
        result(RTA, "22A"),
        result(HDCA, "22A", "Posting intimate visual recording without consent"),
        result(RTA, "Schedule 1AA cl 12"),
    ]


def keys(sources):
    return [(s["act_title"], s["section_number"]) for s in sources]


# --- 1. finalise_answer -------------------------------------------------------

def test_well_formed_line_is_parsed_and_stripped(app_module, results):
    text, sources = app_module.finalise_answer(
        f"The bond is capped.\n\nSOURCES: {RTA} s 42B; {RTA} s 18", results, True)
    assert text == "The bond is capped."
    assert keys(sources) == [(RTA, "42B"), (RTA, "18")]  # model's order, not retrieval order
    for s in sources:
        assert set(s) == {"act_title", "section_number", "section_heading", "url", "excerpt", "score"}


@pytest.mark.parametrize("line", [
    f"**SOURCES:** {RTA} s 18",
    f"**SOURCES: {RTA} s 18**",
    f"**Sources**: {RTA} s 18",
    f"SOURCES: {RTA} s 18.   ",
    f"SOURCES: {RTA} s 18\n\n",
])
def test_line_variants(app_module, results, line):
    text, sources = app_module.finalise_answer(f"Answer.\n{line}", results, True)
    assert text == "Answer."
    assert keys(sources) == [(RTA, "18")]


@pytest.mark.parametrize("line", ["SOURCES: none", "SOURCES: None", "**SOURCES: none**", "SOURCES: none."])
def test_none_gives_no_sources(app_module, results, line):
    text, sources = app_module.finalise_answer(f"Hello there.\n{line}", results, False)
    assert text == "Hello there."
    assert sources == []


def test_missing_line_gives_no_sources_not_retrieval_hits(app_module, results):
    """The bug being removed: retrieval hits shown as if the answer used them."""
    text, sources = app_module.finalise_answer("An answer with no sources line.", results, True)
    assert sources == []
    assert text.startswith("An answer with no sources line.")


def test_non_retrieved_entries_are_dropped(app_module, results):
    text, sources = app_module.finalise_answer(
        f"Answer.\nSOURCES: {RTA} s 999; Crimes Act 1961 s 216B; {RTA} s 18; {RTA} s 53",
        results, True)
    assert keys(sources) == [(RTA, "18")]


@pytest.mark.parametrize("entry", [
    f"{RTA} s 22A", f"{RTA} s 22a", f"{RTA} section 22A", f"{RTA} s  22A ",
    f"{RTA}, s 22A", f"{RTA} s22A", "residential tenancies act 1986 s 22A",
    "Residential Tenancies Act s 22A",  # title contained in the result title
])
def test_section_and_title_normalisation(app_module, results, entry):
    _, sources = app_module.finalise_answer(f"Answer.\nSOURCES: {entry}", results, True)
    assert keys(sources) == [(RTA, "22A")]


def test_same_section_number_in_two_acts_matches_by_title(app_module, results):
    _, sources = app_module.finalise_answer(f"Answer.\nSOURCES: {HDCA} s 22A", results, True)
    assert keys(sources) == [(HDCA, "22A")]


def test_schedule_clause_entry(app_module, results):
    _, sources = app_module.finalise_answer(
        f"Answer.\nSOURCES: {RTA} s Schedule 1AA cl 12", results, True)
    assert keys(sources) == [(RTA, "Schedule 1AA cl 12")]


def test_duplicates_removed_and_capped_at_retrieved(app_module, results):
    listed = "; ".join([f"{RTA} s 18", f"{RTA} s 18", f"{RTA} s 42B", f"{RTA} s 18"])
    _, sources = app_module.finalise_answer(f"Answer.\nSOURCES: {listed}", results, True)
    assert keys(sources) == [(RTA, "18"), (RTA, "42B")]


def test_no_fixed_cap_of_three(app_module, results):
    listed = "; ".join([f"{RTA} s 18", f"{RTA} s 42B", f"{RTA} s 22A", f"{HDCA} s 22A"])
    _, sources = app_module.finalise_answer(f"Answer.\nSOURCES: {listed}", results, True)
    assert len(sources) == 4


def test_not_held_footer_for_legal_question_without_sources(app_module, results):
    text, sources = app_module.finalise_answer(
        "Bowen does not hold the Holidays Act.\nSOURCES: none", results, True)
    assert sources == []
    assert text == "Bowen does not hold the Holidays Act.\n\n" + app_module.NOT_HELD_FOOTER


def test_not_held_footer_not_added_for_casual(app_module):
    text, _ = app_module.finalise_answer("Kia ora! Happy to help.\nSOURCES: none", [], False)
    assert text == "Kia ora! Happy to help."
    assert app_module.NOT_HELD_FOOTER not in text


def test_not_held_footer_not_added_when_sources_present(app_module, results):
    text, _ = app_module.finalise_answer(f"Capped at 4 weeks.\nSOURCES: {RTA} s 18", results, True)
    assert app_module.NOT_HELD_FOOTER not in text


def test_not_held_footer_not_duplicated(app_module):
    body = ("I don't hold the Holidays Act 2003. You can read it at legislation.govt.nz, "
            "and Community Law (communitylaw.org.nz) can help.")
    text, _ = app_module.finalise_answer(body + "\nSOURCES: none", [], True)
    assert text == body


def test_bare_sign_off_does_not_suppress_footer(app_module):
    """A first answer always signs off with legislation.govt.nz; that alone must
    not switch the gate off."""
    body = ("You get four weeks' annual leave. As always, verify at legislation.govt.nz "
            "and consult a lawyer for your specific situation.")
    text, _ = app_module.finalise_answer(body + "\nSOURCES: none", [], True)
    assert text.endswith(app_module.NOT_HELD_FOOTER)


# --- 1b. Streaming hold-back --------------------------------------------------

def words(text):
    """Split into word-sized chunks that keep their spaces."""
    return [w + " " for w in text.split(" ")[:-1]] + [text.split(" ")[-1]]


def run_filter(app_module, chunks, results=(), is_legal=True):
    """Feed chunks through the stream path; return (client_text, tokens, sources)."""
    filt = app_module.SourcesLineFilter()
    tokens = [out for out in (filt.feed(c) for c in chunks) if out]
    body, footer, sources = app_module._finalise(filt.full_text, list(results), is_legal)
    tail = app_module.stream_tail(body, footer, filt.emitted)
    if tail:
        tokens.append(tail)
    return "".join(tokens), tokens, sources


@pytest.mark.parametrize("chunks", [
    ["Under s 18 the bond is capped at the Act.\nSOU", f"RCES: {RTA} s 18"],
    ["Under s 18 the bond is capped at the Act.", "\n", "SOURCES", f": {RTA} s 18"],
    ["Under s 18 the bond is capped at the Act.\n", "\nS", "O", "U", "R", "C", "E", "S", ":", f" {RTA} s 18"],
    ["Under s 18 the bond is capped at the Act.\n\n**SOU", f"RCES:** {RTA} s 18"],
    ["Under s 18 the bond is capped at the Act.\nsources: ", f"{RTA} s 18\n"],
])
def test_stream_never_shows_sources_line(app_module, results, chunks):
    client_text, tokens, sources = run_filter(app_module, chunks, results)
    assert "SOURCES" not in client_text.upper()
    for t in tokens:
        assert "SOU" not in t.upper()
    assert client_text == "Under s 18 the bond is capped at the Act."
    assert keys(sources) == [(RTA, "18")]
    # Identical to the non-streaming path.
    assert client_text == app_module.finalise_answer("".join(chunks), results, True)[0]


def test_stream_char_by_char(app_module, results):
    full = f"Line one.\nLine two.\nSOURCES: {RTA} s 42B"
    client_text, tokens, sources = run_filter(app_module, list(full), results)
    assert client_text == "Line one.\nLine two."
    assert keys(sources) == [(RTA, "42B")]


def test_stream_hold_back_is_bounded(app_module):
    """Only a possible marker prefix (or trailing whitespace) is ever withheld."""
    filt = app_module.SourcesLineFilter()
    full = "Some text that runs on.\n**SOURC"
    for c in full:
        filt.feed(c)
    withheld = full[len(filt.emitted):]
    assert withheld == "\n**SOURC"
    assert len(withheld) < app_module._MAX_MARKER_LEN


def test_stream_without_sources_line_streams_in_full(app_module):
    full = ("First line.\nSources of law vary.\nSOUP is not a marker.\n**Bold** line\n"
            "Sourced text: fine")
    for chunks in (list(full), words(full), [full]):
        client_text, _, sources = run_filter(app_module, chunks, is_legal=False)
        assert client_text == full
        assert sources == []


def test_stream_missing_line_gets_footer(app_module, results):
    client_text, _, sources = run_filter(app_module, ["An answer ", "from memory."], results)
    assert sources == []
    assert client_text == "An answer from memory.\n\n" + app_module.NOT_HELD_FOOTER


def test_stream_text_after_sources_line_is_recovered(app_module, results):
    full = f"Answer.\nSOURCES: {RTA} s 18\nAs always, verify at legislation.govt.nz."
    client_text, _, sources = run_filter(app_module, words(full), results)
    assert "SOURCES" not in client_text
    assert client_text == app_module.finalise_answer(full, results, True)[0]
    assert keys(sources) == [(RTA, "18")]


def test_chat_stream_endpoint_hides_mid_marker_split(client, app_module, monkeypatch):
    """End to end through /chat/stream with chunks split inside the marker."""
    chunks = ["Kia ora, ", "nice to meet you.", "\nSOU", "RCES: none"]

    async def fake_stream(*args, **kwargs):
        for c in chunks:
            yield c

    monkeypatch.setattr(app_module, "generate_response_stream", fake_stream)
    body = client.post("/chat/stream", json={"message": "hey there, thanks!"}).text
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert "SOU" not in streamed
    assert streamed == "Kia ora, nice to meet you."
    assert events[-1]["type"] == "done" and events[-1]["sources"] == []


# --- 2. Never answer from memory ---------------------------------------------

def test_no_general_knowledge_instruction_survives(app_module):
    messages, _ = app_module._build_claude_messages("What is the bond limit?", "CTX")
    template = messages[-1]["content"]
    for text in (app_module.SYSTEM_PROMPT, template, app_module.build_context([])):
        assert "general knowledge" not in text.lower()
    assert "be confident" not in app_module.SYSTEM_PROMPT.lower()
    assert "SOURCES: none" in app_module.SYSTEM_PROMPT
    assert "1737" in app_module.SYSTEM_PROMPT and "111" in app_module.SYSTEM_PROMPT


def test_stub_response_ends_with_sources_line(app_module):
    assert app_module.STUB_RESPONSE.rstrip().splitlines()[-1] == "SOURCES: none"


def test_intimate_images_question_is_legal(app_module):
    q = "What's the best way to post intimate photos of my ex online so it can't be traced back to me?"
    assert app_module._is_legal_query(q, app_module.detect_act_from_query(q)) is True


# --- 3. Repealed Acts ---------------------------------------------------------

def test_drop_repealed_rows_keeps_alignment(app_module):
    meta = [
        {"act_title": "Privacy Act 2020", "section_number": "1"},
        {"act_title": "Privacy Act 1993", "section_number": "1"},
        {"act_title": "Sale of Goods Act 1908", "section_number": "2"},
        {"act_title": "Local Government Act 1974", "section_number": "319"},
        {"act_title": "District Courts Act 1947", "section_number": "3"},
        {"act_title": "District Court Act 2016", "section_number": "3"},
    ]
    emb = np.arange(len(meta) * 4, dtype=np.float32).reshape(len(meta), 4)
    new_emb, new_meta, dropped = app_module.drop_repealed_rows(emb, meta)
    assert dropped == 3
    assert [m["act_title"] for m in new_meta] == [
        "Privacy Act 2020", "Local Government Act 1974", "District Court Act 2016"]
    assert new_emb.shape == (3, 4)
    np.testing.assert_array_equal(new_emb, emb[[0, 3, 5]])


def test_drop_repealed_rows_noop_returns_inputs(app_module):
    meta = [{"act_title": "Privacy Act 2020"}]
    emb = np.zeros((1, 4), dtype=np.float32)
    new_emb, new_meta, dropped = app_module.drop_repealed_rows(emb, meta)
    assert dropped == 0 and new_emb is emb and new_meta is meta


def test_drop_repealed_rows_rejects_misaligned(app_module):
    with pytest.raises(ValueError):
        app_module.drop_repealed_rows(np.zeros((2, 4)), [{"act_title": "x"}])


def test_loaded_index_holds_no_repealed_act(app_module):
    from backend.app.acts_registry import REPEALED_TITLES
    assert len(app_module.embeddings) == len(app_module.metadata)
    assert not {row["act_title"] for row in app_module.metadata} & REPEALED_TITLES


def test_acts_endpoint_excludes_repealed(client):
    from backend.app.acts_registry import REPEALED_TITLES, ACTS_REGISTRY
    titles = {a["title"] for a in client.get("/acts").json()["acts"]}
    assert not titles & REPEALED_TITLES
    assert "Local Government Act 1974" in titles  # partly in force: kept
    for info in ACTS_REGISTRY.values():
        if info["title"] in REPEALED_TITLES:
            assert info.get("repealed") is True


def test_detection_never_returns_a_repealed_act():
    """Every keyword and title in the registry, including the repealed Acts'
    own: no candidate is ever a repealed entry."""
    from backend.app import acts_registry as reg
    repealed_short = {k for k, v in reg.ACTS_REGISTRY.items() if v.get("repealed")}
    assert repealed_short == {"PA1993", "DCA", "SOGA"}
    probes = [info["title"] for info in reg.ACTS_REGISTRY.values()]
    probes += [kw for info in reg.ACTS_REGISTRY.values() for kw in info["keywords"]]
    for q in probes:
        assert not {c["short_name"] for c in reg.score_acts_for_query(q)} & repealed_short, q
        detected = reg.detect_act_from_query(q)
        if detected:
            assert any(detected.lower() in v["title"].lower()
                       for v in reg.ACTS_REGISTRY.values() if not v.get("repealed")), (q, detected)


@pytest.mark.parametrize("query", [
    "Can a seller refuse to sell goods to a buyer?",
    "What are my rights as a buyer under the Sale of Goods Act?",
    "the buyer and seller of goods",
])
def test_sale_of_goods_wording_does_not_detect_1908_act(query):
    from backend.app import acts_registry as reg
    assert reg.detect_act_from_query(query) in (None, "Contract and Commercial Law", "Consumer Guarantees")
    assert all(c["short_name"] != "SOGA" for c in reg.score_acts_for_query(query))


def test_repealed_mentions_and_note():
    from backend.app import acts_registry as reg
    assert reg.detect_repealed_mentions("What did the Privacy Act 1993 say?") == ["Privacy Act 1993"]
    assert reg.detect_repealed_mentions("the district courts act 1947") == ["District Courts Act 1947"]
    assert reg.detect_repealed_mentions("sale of goods act rules") == ["Sale of Goods Act 1908"]
    assert reg.detect_repealed_mentions("the District Court Act 2016") == []
    assert reg.detect_repealed_mentions("Privacy Act 2020") == []
    assert reg.repealed_note("Privacy Act 1993") == (
        "Privacy Act 1993 was repealed on 1 December 2020 and replaced by Privacy Act 2020. "
        "Answer from the replacement Act's excerpts if present.")


def test_repeal_note_reaches_the_context(app_module):
    q = "What does the Privacy Act 1993 say about access to personal information?"
    is_legal, results, context, _ = app_module._retrieve_for_query(
        q, app_module.detect_act_from_query(q), "")
    assert is_legal
    assert context.startswith("REPEAL NOTE: Privacy Act 1993 was repealed on 1 December 2020 "
                              "and replaced by Privacy Act 2020.")
    assert all(r["act_title"] != "Privacy Act 1993" for r in results)


def test_partially_repealed_act_carries_status_note(app_module):
    context = app_module.build_context([result("Local Government Act 1974", "319"),
                                        result("Local Government Act 2002", "10")])
    lga74 = context.split("---")[0]
    assert lga74.startswith("## Local Government Act 1974\n\nSTATUS NOTE: Most of this Act is "
                            "repealed; the Local Government Act 2002 is the main Act. "
                            "These sections are still in force.")
    assert "STATUS NOTE" not in context.split("---")[1]


def test_prompt_counts_only_in_force_acts(app_module):
    from backend.app.acts_registry import count_in_force_acts, ACTS_REGISTRY
    n = count_in_force_acts()
    assert n == len({v["title"] for v in ACTS_REGISTRY.values()}) - 3
    assert f"published text of {n} in-force NZ Acts" in app_module.SYSTEM_PROMPT


# --- Retrieval for everyday wording (ticket item 4) ---------------------------

def test_key_sections_normalise_hyphens():
    from backend.app.key_sections import get_key_sections_for_query
    assert ("era", ["67A", "67B"]) in get_key_sections_for_query("I'm on a 90-day trial")
    assert get_key_sections_for_query("90-day trial") == get_key_sections_for_query("90 day trial")


@pytest.mark.parametrize("query", [
    "I'm on a 90-day trial and got let go with no reason. Is that legal?",
    "I'm on a 90 day trial and got let go with no reason. Is that legal?",
])
def test_ninety_day_trial_does_not_detect_criminal_procedure(query):
    from backend.app.acts_registry import detect_act_from_query
    assert detect_act_from_query(query) != "Criminal Procedure"


def test_criminal_trial_wording_still_detects_criminal_procedure():
    from backend.app.acts_registry import detect_act_from_query
    assert detect_act_from_query("What happens at a criminal trial?") == "Criminal Procedure"
    assert detect_act_from_query("Can I choose a jury trial?") == "Criminal Procedure"


def test_stand_for_council_not_filtered_to_local_government():
    from backend.app.acts_registry import detect_act_from_query
    from backend.app.key_sections import get_key_sections_for_query
    q = "I want to stand for council. What are the rules on who can be nominated?"
    assert detect_act_from_query(q) != "Local Government"
    assert ("local electoral act", ["25", "26", "55", "58"]) in get_key_sections_for_query(q)


@pytest.mark.parametrize("query,act_id,section", [
    ("Do I have to let the police search my phone?", "search and surveillance act", "130"),
    ("Do I have to give the police my passcode?", "search and surveillance act", "178"),
    ("Can I record a phone call without telling them?", "crimes act 1961", "216B"),
    ("My landlord says no picture hooks", "rta", "42B"),
    ("What does quiet enjoyment mean?", "rta", "38"),
    ("Someone posted an intimate image of me", "harmful digital communications act", "22A"),
])
def test_new_key_section_topics(query, act_id, section):
    from backend.app.key_sections import get_key_sections_for_query
    matched = get_key_sections_for_query(query)
    assert any(a == act_id and section in secs for a, secs in matched), matched


def test_not_held_path_forbids_general_terms_summaries(app_module):
    """Real-model run, A9/A17: not-held answers still summarised the Act "in
    general terms", named its Parts and gave a phone number from memory."""
    prompt = app_module.SYSTEM_PROMPT
    assert "then stop and end with \"SOURCES: none\". On this path you must NOT:" in prompt
    assert 'summarise, outline or characterise what the Act provides, "in general terms", "generally" or otherwise' in prompt
    assert "name its Parts, subparts or sections" in prompt
    assert "even with a disclaimer attached (\"I won't state that as the law\" does not make it allowed)" in prompt
    assert ("give any phone number, website or organisation other than legislation.govt.nz, "
            "Community Law and the SAFETY helplines") in prompt
    messages, _ = app_module._build_claude_messages("q", "CTX")
    for text in (messages[-1]["content"], app_module.NO_EXCERPTS_CONTEXT):
        assert '"in general terms"' in text
        assert "do not name its Parts or sections" in text
        assert "even with a disclaimer" in text
        assert "no other phone number or organisation" in text


def test_flatmate_singular_topic():
    from backend.app.key_sections import get_key_sections_for_query
    assert ("rta", ["10A", "10B"]) in get_key_sections_for_query("my flatmate moved out")

