"""
test_key_sections_audit.py — the key-sections audit and the unqualified legal
practice topic (docs/2026-11-12-PRODUCT-TICKET-lawyers-act-retrieval.md).

Many KEY_SECTIONS entries carried section numbers from an Act the tool does not
hold (the Holidays Act, the Consumer Guarantees Act) applied to one it does, so
"sick leave" pinned ERA ss 63-65. The structural test catches the cases where a
wrong number does not exist in the Act; the rest were checked by hand against
the headings and text.
"""

import pytest

from backend.app import acts_registry as reg
from backend.app import key_sections as ks

LCA = "Lawyers and Conveyancers Act 2006"
TURN_1 = ("What limits apply to a legal AI answering legal questions without breaching "
          "the prohibition on non-lawyers giving legal advice under the Lawyers and "
          "Conveyancers Act 2006?")
TURN_2 = "Is it lawful for an accountant to give legal advice if they do not use a lawyer's title?"


def _all_entries():
    for topic, entries in ks.KEY_SECTIONS.items():
        for act_id, sections in entries:
            yield topic, act_id, sections
    for groups, entries in ks.COMBINED_TOPICS:
        for act_id, sections in entries:
            yield groups[0][0], act_id, sections


@pytest.fixture(scope="module")
def index(app_module):
    """{(act_title, act_short_name): {section_number: [text, ...]}}"""
    out = {}
    for row in app_module.metadata:
        key = (row.get("act_title", ""), row.get("act_short_name", ""))
        out.setdefault(key, {}).setdefault(row.get("section_number", "").strip(), []).append(
            row.get("text", ""))
    return out


def _acts_for(act_id, index):
    return [key for key in index
            if ks._act_matches_strictly(act_id, {"act_title": key[0], "act_short_name": key[1]})]


# --- (a) structure -------------------------------------------------------------

def test_every_listed_section_exists_in_its_act(index):
    """A section number taken from another Act often does not exist in this
    one (RTA "10A"). Acts absent from the loaded index are skipped, so this
    also runs on the mini fixture for the Acts it holds."""
    missing, ambiguous, checked = [], [], 0
    for topic, act_id, sections in _all_entries():
        acts = _acts_for(act_id, index)
        if len(acts) > 1:
            ambiguous.append((topic, act_id, acts))
        for act in acts:
            for section in sections:
                checked += 1
                if section not in index[act]:
                    missing.append((topic, act_id, section))
    assert not ambiguous, ambiguous
    assert not missing, missing
    assert checked, "no listed Act is in the loaded index"


def test_key_chunk_text_is_in_its_section(index):
    for (act_id, section), needle in ks.KEY_CHUNK_TEXT.items():
        for act in _acts_for(act_id, index):
            assert any(needle in t.lower() for t in index[act].get(section, [])), (act_id, section)


def test_short_ids_boost_only_their_own_act():
    """Boosting used a substring match: "ca" boosted every section of 35 Acts,
    the Lawyers and Conveyancers Act among them, and "rma" every title
    containing "information"."""
    lca = {"act_title": LCA, "act_short_name": "LCA", "section_number": "131"}
    oia = {"act_title": "Official Information Act 1982", "act_short_name": "OIA",
           "section_number": "5"}
    companies = {"act_title": "Companies Act 1993", "act_short_name": "CA",
                 "section_number": "131"}
    assert ks.should_boost_section(lca, [("ca", ["131"])]) == 1.0
    assert ks.should_boost_section(oia, [("rma", ["5"])]) == 1.0
    assert ks.should_boost_section(companies, [("ca", ["131"])]) == 2.0
    assert ks.should_boost_section(companies, [("ca", ["132"])]) == 1.3


@pytest.mark.parametrize("query", [
    "How much sick leave am I entitled to?",
    "Do I get paid for a public holiday?",
    "How many weeks of annual leave do I get?",
    "What is the minimum wage?",
    "Can I take bereavement leave for my aunt?",
    "How long is parental leave?",
    "Can I get diversion for drink driving?",
])
def test_topics_whose_act_is_not_held_name_no_sections(query):
    """Holidays Act 2003, Minimum Wage Act 1983 and the Parental Leave Act are
    not held; diversion is not statutory. No pin is better than a wrong one."""
    assert ks.get_key_sections_for_query(query) == []


def test_please_does_not_fire_the_lease_topic():
    """Ticket fault 2, turn 3: "please" contains "lease" and pulled in the
    Property Law Act."""
    assert ks.get_key_sections_for_query(
        "please answer the question again and use sections 25(2) and 27") == []
    assert not any(a == "pla" for a, _ in ks.get_key_sections_for_query("Can you please help?"))
    assert any(a == "pla" for a, _ in ks.get_key_sections_for_query(
        "Can my commercial lease be cancelled for late rent?"))


def test_consumer_topics_point_at_the_consumer_guarantees_act():
    for query in ("I want a refund", "Must the shop repair or replace it?",
                  "What is a consumer guarantee?", "faulty product"):
        acts = {a for a, _ in ks.get_key_sections_for_query(query)}
        assert acts == {"consumer guarantees act"}, (query, acts)


# --- (b) unqualified legal practice: trigger wording ---------------------------

def _lca_sections(query):
    return {s for a, ss in ks.get_key_sections_for_query(query)
            if a == "lawyers and conveyancers act" for s in ss}


@pytest.mark.parametrize("query", [
    TURN_1,
    TURN_2,
    "Can an AI chatbot give legal advice in New Zealand?",
    "Can a non-lawyer provide legal services for a fee?",
    "I'm not a lawyer. Can I give my friend legal advice?",
    "Can a paralegal give legal advice?",
    "What are the reserved areas of work for lawyers?",
    "Is unauthorised practice of law an offence?",
    "Is unauthorized practice a crime here?",
    "Which reserved areas are limited to lawyers?",
])
def test_unqualified_practice_topic_fires(query):
    assert {"6", "21", "22", "23", "24", "27"} <= _lca_sections(query)


@pytest.mark.parametrize("query", [
    "Can I get legal advice about my tenancy?",
    "Where can I find free legal advice?",
    "My lawyer gave me bad legal advice. Can I complain?",
    "Is my landlord allowed to use AI to screen tenants?",
    "My accountant made a mistake on my tax return",
    "The council has a reserved area for dogs in the park",
    "Do I need a lawyer to apply for legal aid?",
    "please answer the question again and use sections 25(2) and 27",
])
def test_unqualified_practice_topic_does_not_fire(query):
    assert not _lca_sections(query)


def test_unqualified_practice_pins_only_s24_and_s6():
    """Two pins fit main.MAX_PINNED; ss 21, 22, 23 and 27 are boosted only."""
    matched = ks.get_key_sections_for_query(TURN_1)
    pinned = {s for s in ("6", "21", "22", "23", "24", "27")
              if ks.is_pinned_section({"act_title": LCA, "act_short_name": "LCA",
                                       "section_number": s,
                                       "text": "reserved areas of work means"}, matched)}
    assert pinned == {"6", "24"}


def test_s6_pins_and_boosts_only_the_definition_chunk():
    matched = ks.get_key_sections_for_query(TURN_1)
    meta = {"act_title": LCA, "act_short_name": "LCA", "section_number": "6"}
    definition = dict(meta, text="... reserved areas of work means the work carried out ...")
    other = dict(meta, text="bank means a registered bank ...")
    assert ks.is_pinned_section(definition, matched)
    assert not ks.is_pinned_section(other, matched)
    assert ks.should_boost_section(definition, matched) == 2.0
    assert ks.should_boost_section(other, matched) == 1.3


# --- (c) the ticket's turns on the full index -----------------------------------

@pytest.fixture(scope="module")
def lca_index(app_module):
    if not any(row.get("act_title") == LCA for row in app_module.metadata):
        pytest.skip("Lawyers and Conveyancers Act not in the loaded index (full index only)")
    return app_module


@pytest.mark.parametrize("query", [TURN_1, TURN_2])
def test_ticket_turns_retrieve_s24_and_the_s6_definition(lca_index, query):
    results = lca_index.search_similar(query, top_k=6,
                                       act_filter=reg.detect_act_from_query(query))
    by_section = {r["section_number"]: r for r in results if r["act_title"] == LCA}
    assert "24" in by_section, sorted(by_section)
    assert "6" in by_section, sorted(by_section)
    assert "reserved areas of work means" in by_section["6"]["text"].lower()
    assert {"21", "23"} <= set(by_section), sorted(by_section)


def test_s24_is_pinned_when_no_act_is_named(lca_index):
    """"Can an AI chatbot give legal advice in New Zealand?" scores under the
    pin floor against s 24; PIN_WITHOUT_FLOOR exempts it (audit, 12 Nov)."""
    results = lca_index.search_similar("Can an AI chatbot give legal advice in New Zealand?", top_k=6)
    lca = {r["section_number"].strip() for r in results
           if r["act_title"] == "Lawyers and Conveyancers Act 2006" and r["pinned"]}
    assert {"24", "6"} <= lca


def test_pin_floor_exemption_is_limited_to_the_listed_sections():
    meta = {"act_title": "Lawyers and Conveyancers Act 2006", "act_short_name": "LCA"}
    assert ks.pin_ignores_floor({**meta, "section_number": "24"})
    assert not ks.pin_ignores_floor({**meta, "section_number": "25"})
    assert not ks.pin_ignores_floor({"act_title": "Residential Tenancies Act 1986",
                                     "act_short_name": "RTA", "section_number": "24"})
