"""
test_round2_followups.py — the round-two testing ticket
(docs/2026-11-01-PRODUCT-TICKET-round-2-followups.md).

Item 1: exact key sections are pinned into the results, not only boosted.
Item 2: the model is told which Acts are held, so it does not say "I don't
        hold" an Act that is held but not retrieved.
Item 3a: a misspelt Act title still detects the Act.
"""

import pytest

from backend.app import acts_registry as reg
from backend.app.key_sections import get_key_sections_for_query, is_pinned_section

RTA = "Residential Tenancies Act 1986"
HOOKS = "Can I put picture hooks in the wall of my rental?"

# Round-two wordings that drew a wrong "I don't hold that Act".
A4 = "The shop says no refunds on sale items. Is that right?"
A18 = "How long do I have to file a Disputes Tribunal claim?"
D3 = "My ex won't let me see the kids. What does the law say about who decides where the children live?"
C8 = "Is it an offence to post someone's intimate images online without their consent?"
PRA_LIVE = "House seperation and unequal splits between partners"
PRA_PLAIN = "we are separating and I want more than half of the house because I paid the deposit, is that allowed?"


# --- Item 1: pinned key sections ---------------------------------------------

def test_picture_hooks_pins_s42B_below_min_similarity(app_module):
    """A1: s42B's cosine (0.22) is under MIN_SIMILARITY, so no boost could
    ever reach it; the pin does."""
    q = HOOKS
    results = app_module.search_similar(q, top_k=6, act_filter=reg.detect_act_from_query(q))
    hit = [r for r in results if r["act_title"] == RTA and r["section_number"] == "42B"]
    assert hit and hit[0]["pinned"]
    assert len(results) <= 6
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_pin_respects_act_filter(app_module):
    results = app_module.search_similar(HOOKS, top_k=6, act_filter="Privacy")
    assert all(r["act_title"] == "Privacy Act 2020" for r in results)
    unfiltered = app_module.search_similar(HOOKS, top_k=6)
    assert (RTA, "42B") in {(r["act_title"], r["section_number"]) for r in unfiltered}


def test_pin_keeps_dedupe_and_top_k(app_module):
    q = "My landlord wants to keep my bond because I put picture hooks in the wall. Can he?"
    results = app_module.search_similar(q, top_k=6, act_filter="Residential Tenancies")
    keys = [(r["act_title"], r["section_number"], r["text"]) for r in results]
    assert len(results) == 6 and len(keys) == len(set(keys))
    assert (RTA, "42B") in {(r["act_title"], r["section_number"]) for r in results}


def test_pin_matches_acts_strictly():
    """Boosting substring-matches the act id; pinning must not, or "pa" (Privacy
    Act) would pin sections of the Companies Act."""
    ks = [("pa", ["22"]), ("search and surveillance act", ["130"])]
    assert is_pinned_section({"act_title": "Privacy Act 2020", "act_short_name": "PA",
                              "section_number": "22"}, ks)
    assert not is_pinned_section({"act_title": "Companies Act 1993", "act_short_name": "CA",
                                  "section_number": "22"}, ks)
    assert is_pinned_section({"act_title": "Search and Surveillance Act 2012",
                              "act_short_name": "SSA", "section_number": "130"}, ks)


def test_long_section_ranges_are_not_pinned():
    """"bond" lists ss 18-22B: a range to boost, not sections to pin."""
    ks = get_key_sections_for_query("bond")
    assert not is_pinned_section({"act_title": RTA, "act_short_name": "RTA",
                                  "section_number": "18"}, ks)


def test_phone_search_topic_pins_s130_and_s178():
    ks = get_key_sections_for_query("Do I have to let the police search my phone?")
    for sec in ("130", "178"):
        assert is_pinned_section({"act_title": "Search and Surveillance Act 2012",
                                  "act_short_name": "SSA", "section_number": sec}, ks)


# --- Item 2: held Acts --------------------------------------------------------

def test_every_held_title_is_in_the_system_prompt(app_module):
    titles = {a["title"] for a in reg.get_all_acts()}
    assert len(titles) == reg.count_in_force_acts()
    assert app_module.HELD_ACT_TITLES == sorted(titles)
    missing = [t for t in titles if t not in app_module.SYSTEM_PROMPT]
    assert not missing, missing


def test_held_titles_match_the_acts_endpoint(client, app_module):
    titles = sorted({a["title"] for a in client.get("/api/v1/acts").json()["acts"]})
    assert titles == app_module.HELD_ACT_TITLES


@pytest.mark.parametrize("title", [
    "Consumer Guarantees Act 1993",
    "Limitation Act 2010",
    "Care of Children Act 2004",
    "Harmful Digital Communications Act 2015",
    "Property (Relationships) Act 1976",
])
def test_round_two_acts_are_listed_as_held(app_module, title):
    assert title in app_module.HELD_ACT_TITLES
    assert title in app_module.SYSTEM_PROMPT


@pytest.mark.parametrize("title", [
    "Holidays Act 2003",
    "Minimum Wage Act 1983",
    "Sale and Supply of Alcohol Act 2012",
    "Charities Act 2005",
    "End of Life Choice Act 2019",
    "Residential Tenancies (Healthy Homes Standards) Regulations 2019",
])
def test_not_held_examples_are_named_and_not_held(app_module, title):
    assert title in app_module.SYSTEM_PROMPT
    assert title not in app_module.HELD_ACT_TITLES


def test_held_rule_is_stated(app_module):
    assert ("If the Act that governs the question is on this list, you HOLD it: say \"I hold "
            "the X Act but didn't retrieve the section that deals with this\". Say \"I don't "
            "hold\" ONLY for an Act that is not on this list.") in app_module.SYSTEM_PROMPT


def test_no_either_or_not_held_wording_left(app_module):
    messages, _ = app_module._build_claude_messages("q", "CTX")
    for text in (app_module.SYSTEM_PROMPT, messages[-1]["content"], app_module.NO_EXCERPTS_CONTEXT):
        low = text.lower()
        assert "do not hold that act, or did not retrieve" not in low
        assert "do not hold that act or did not retrieve" not in low
        assert "do not hold it or did not retrieve" not in low
        assert "say that you do not hold it only if it is not on that list" in low


@pytest.mark.parametrize("query,title", [
    (A4, "Consumer Guarantees Act 1993"),
    ("I bought a toaster and it broke after two weeks, what are my rights?", "Consumer Guarantees Act 1993"),
    (A18, "Limitation Act 2010"),
    ("How long do I have to sue someone over a debt?", "Limitation Act 2010"),
    (D3, "Care of Children Act 2004"),
    ("Who gets the kids if we separate?", "Care of Children Act 2004"),
    (C8, "Harmful Digital Communications Act 2015"),
    (PRA_LIVE, "Property (Relationships) Act 1976"),
    (PRA_PLAIN, "Property (Relationships) Act 1976"),
])
def test_held_acts_line_names_the_act(app_module, query, title):
    line = app_module.held_acts_line(query, [])
    assert line.startswith("ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: ")
    assert title in line
    assert "do not say you don't hold it" in line


def test_held_acts_line_says_none_for_a_casual_query(app_module):
    line = app_module.held_acts_line("hey, how are you today?", [])
    assert line.startswith("ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: none.")
    assert "check the list in your instructions" in line


def test_held_acts_line_adds_detected_act_but_not_retrieved_ones(app_module):
    line = app_module.held_acts_line("whats the consitution act of 1986", [
        {"act_title": "Goods and Services Tax Act 1985"}], detected_act="Constitution")
    assert line.startswith("ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: Constitution Act 1986.")
    assert "Goods and Services Tax" not in line
    assert line.endswith("Every Act in the excerpts below is held.")


def test_held_acts_line_reaches_both_context_paths(app_module, monkeypatch):
    q = "Can my landlord keep my bond?"
    _, results, context, _ = app_module._retrieve_for_query(q, reg.detect_act_from_query(q), "")
    assert results
    assert context.startswith("ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: " + RTA)
    monkeypatch.setattr(app_module, "search_similar", lambda *a, **k: [])
    _, results, context, _ = app_module._retrieve_for_query(q, None, "")
    assert not results
    assert context.startswith("ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: " + RTA)
    assert context.endswith(app_module.NO_EXCERPTS_CONTEXT)


def test_footer_names_held_acts(app_module):
    q = "What does the Consumer Guarantees Act say about refunds?"
    held = app_module.footer_acts(q, reg.detect_act_from_query(q))
    assert held == ["Consumer Guarantees Act 1993"]
    text, sources = app_module.finalise_answer("Not retrieved.\nSOURCES: none", [], True, held)
    assert sources == []
    assert text.endswith("I hold the Consumer Guarantees Act 1993, but I didn't retrieve the "
                         "section that deals with this question, so I haven't stated the rule "
                         "here. You can read the current law at legislation.govt.nz, and "
                         "Community Law (communitylaw.org.nz) offers free legal help.")
    assert "don't hold" not in text


def test_footer_ignores_hint_words(app_module):
    """Hints feed the held-Acts line only: "post" and "online" must not have the
    footer assert the Harmful Digital Communications Act or Dog Control Act."""
    # "dog" is a strong registry keyword, so the Dog Control Act may stay.
    assert "Harmful Digital Communications Act 2015" not in app_module.footer_acts("I posted a photo online of my dog")
    # A4 still names the CGA: "refund" is one of its registry keywords, not a hint.
    assert app_module.footer_acts("I bought a toaster and it broke after two weeks") == []


def test_generic_footer_never_says_not_held(app_module):
    assert "hold" not in app_module.NOT_HELD_FOOTER


@pytest.mark.parametrize("query", ["I forgot my password", "what's the wifi password"])
def test_substring_topics_do_not_open_the_gate(app_module, query):
    assert app_module._is_legal_query(query, reg.detect_act_from_query(query)) is False


def test_footer_generic_without_a_match(app_module):
    assert app_module.footer_acts("What is stare decisis?") == []
    text, _ = app_module.finalise_answer("Hmm.\nSOURCES: none", [], True, [])
    assert text.endswith(app_module.NOT_HELD_FOOTER)


def test_footer_skips_weak_only_matches(app_module):
    """"police" alone names the Policing Act weakly; the footer must not claim it."""
    assert "Policing Act 2008" not in app_module.footer_acts("Do I have to let the police search my phone?")


def test_children_alone_does_not_detect_child_poverty():
    """D3 detected the Child Poverty Reduction Act on "children" and filtered
    the Care of Children Act out of retrieval."""
    assert reg.detect_act_from_query(D3) != "Child Poverty Reduction"
    assert reg.detect_act_from_query("What does the Child Poverty Reduction Act require?") == "Child Poverty Reduction"


# --- Item 3a: misspelt Act titles ---------------------------------------------

@pytest.mark.parametrize("query,expected", [
    ("whats the consitution act of 1986 and what was it designed to fix so to speak", "Constitution"),
    ("whats the constitution act of 1986 and what was it designed to fix so to speak", "Constitution"),
    ("what does the residental tenancies act say about bonds", "Residential Tenancies"),
    ("what does the residental tenancies act say", "Residential Tenancies"),
    ("what is an act of parliament", None),
    ("how do I act in self defence", None),
    ("the consitution act 1990", None),  # year disagrees with the Act's
    ("act now", None),
])
def test_misspelt_act_titles(query, expected):
    assert reg.detect_act_from_query(query) == expected


# --- Item 3: everyday wording -------------------------------------------------

@pytest.mark.parametrize("query", [
    PRA_LIVE,
    "Who gets the kids if we separate?",
    "How long do I have to sue someone over a debt?",
    "I want to have a pet, but the owner has refused.",
])
def test_everyday_wording_passes_the_gate(app_module, query):
    """The live Property (Relationships) question fell through the gate: no
    search ran, and the answer said the Act was not held."""
    assert app_module._is_legal_query(query, reg.detect_act_from_query(query)) is True


@pytest.mark.parametrize("query", ["hey thanks so much", "haha nice", "good morning Bowen"])
def test_casual_messages_still_skip_retrieval(app_module, query):
    assert app_module._is_legal_query(query, reg.detect_act_from_query(query)) is False


@pytest.mark.parametrize("query,act_id,section", [
    ("I want to have a pet, but the owner has refused.", "rta", "42E"),
    ("The owner didn't give any notice for the inspection and demanded I let them in", "rta", "48"),
    ("Must a rental house have heating?", "rta", "45"),
    ("My neighbour wants me to pay half for a new fence", "fencing act 1978", "10"),
    ("Can a council fine me for a noisy party?", "resource management act", "326"),
    ("I bought a toaster and it broke after two weeks", "consumer guarantees act", "6"),
    ("Can a debt collector add their fees on top of what I owe?",
     "credit contracts and consumer finance act", "41"),
    ("How long does a council have to answer an official information request?",
     "local government official information and meetings act", "13"),
    ("Can an agency extend the time to answer my Privacy Act request?", "privacy act 2020", "48"),
])
def test_round_two_topics(query, act_id, section):
    matched = get_key_sections_for_query(query)
    assert any(a == act_id and section in secs for a, secs in matched), matched


@pytest.mark.parametrize("query", [
    "Can I sign a petition about council rates?",            # "pet" inside "petition"
    "When does the council do a building inspection?",       # not a tenancy inspection
    "My heating bill is huge this winter",                   # no tenancy word
    "My laptop broke",                                       # no purchase word
])
def test_round_two_topics_need_every_group(query):
    secs = {(a, s) for a, ss in get_key_sections_for_query(query) for s in ss}
    assert not secs & {("rta", "42E"), ("rta", "48"), ("rta", "45"), ("consumer guarantees act", "6")}


def test_fine_alone_does_not_detect_sentencing():
    assert reg.detect_act_from_query("Can a council fine me for a noisy party?") != "Sentencing"
    assert reg.detect_act_from_query("What is the maximum fine under the Sentencing Act?") == "Sentencing"
