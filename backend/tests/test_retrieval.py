"""
test_retrieval.py — surface S1 (retrieval).

Covers charter invariants R1 (uniqueness), R3 (act filter honoured),
R4 (score sanity) and R5 (latency), plus the result-level dedupe added to
search_similar().

The committed fixture is deduplicated, so R1 is trivially true over it. To
exercise the real defect these tests also run against an in-memory index that
has been tiled 12x — the same shape the deployed corpus has, where every chunk
is present ~10-12 times as an identical row (see NOTES-duplication.md).
"""

import math
import time

import pytest

import golden_runner

DUPLICATION_FACTOR = 12


@pytest.fixture(scope="module")
def dup_index(app_module):
    """The loaded index, tiled 12x — production-shaped duplication."""
    with golden_runner.duplicated_index(app_module, DUPLICATION_FACTOR):
        yield app_module


def result_keys(results):
    return [(r["act_title"], r["section_number"], r["text"]) for r in results]


# --- basic behaviour ---------------------------------------------------------

def test_index_loaded(app_module):
    assert app_module.embeddings is not None
    assert app_module.metadata
    assert app_module.embeddings.shape[0] == len(app_module.metadata)
    assert app_module.embeddings.shape[1] == 384


def test_search_returns_results(app_module):
    results = app_module.search_similar("maximum bond for a residential tenancy", top_k=5)
    assert results, "expected at least one result for a core demo query"
    assert len(results) <= 5
    assert results[0]["act_title"]


def test_search_returns_empty_without_model(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "embedding_model", None)
    assert app_module.search_similar("anything at all") == []


def test_top_k_respected(app_module):
    for k in (1, 3, 6, 10):
        results = app_module.search_similar("privacy breach notification", top_k=k)
        assert len(results) <= k


# --- R1 uniqueness -----------------------------------------------------------

@pytest.mark.parametrize("query", [
    "maximum bond for a residential tenancy",
    "freedom of expression",
    "unjustified dismissal",
    "misleading and deceptive conduct",
    "notifiable privacy breach",
])
def test_r1_uniqueness_on_fixture(app_module, query):
    results = app_module.search_similar(query, top_k=10)
    keys = result_keys(results)
    assert len(keys) == len(set(keys)), "duplicate (act, section, text) in results"


@pytest.mark.parametrize("query", [
    "maximum bond for a residential tenancy",
    "freedom of expression",
    "unjustified dismissal",
    "misleading and deceptive conduct",
    "notifiable privacy breach",
])
def test_r1_uniqueness_on_duplicated_index(dup_index, query):
    """The whole point of the dedupe: a 12x-duplicated corpus must still
    produce distinct results."""
    results = dup_index.search_similar(query, top_k=6)
    keys = result_keys(results)
    assert len(keys) == len(set(keys)), (
        "duplicate (act, section, text) survived dedupe on the duplicated index"
    )


def test_duplicated_index_without_dedupe_collapses(dup_index):
    """Regression evidence: with the over-fetch disabled (the pre-change
    behaviour) a duplicated corpus returns a single distinct section."""
    query = "maximum bond for a residential tenancy"
    with golden_runner.candidate_multiplier(dup_index, 1):
        before = dup_index.search_similar(query, top_k=6)
    after = dup_index.search_similar(query, top_k=6)

    before_unique = len(set(result_keys(before)))
    after_unique = len(set(result_keys(after)))

    assert before_unique == 1, (
        f"expected the un-deduped path to collapse to one section, got {before_unique}"
    )
    assert after_unique == 6, f"expected 6 distinct sections after dedupe, got {after_unique}"


def test_dedupe_preserves_descending_order(dup_index):
    results = dup_index.search_similar("landlord right of entry", top_k=6)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_dedupe_keeps_highest_scoring_copy(app_module):
    """Dedupe must keep the best-scoring row for a key, not an arbitrary one."""
    results = app_module.search_similar("information privacy principles", top_k=6)
    assert results
    top_score = results[0]["score"]
    for r in results[1:]:
        assert r["score"] <= top_score + 1e-9


# --- R3 act filter -----------------------------------------------------------

@pytest.mark.parametrize("query,expected_act_fragment", [
    ("What is the maximum bond under the Residential Tenancies Act?", "Residential Tenancies"),
    ("What does the Privacy Act say about data breaches?", "Privacy"),
    ("unjustified dismissal under the Employment Relations Act", "Employment Relations"),
    ("misleading conduct under the Fair Trading Act", "Fair Trading"),
])
def test_r3_act_filter_honoured(app_module, query, expected_act_fragment):
    detected = app_module.detect_act_from_query(query)
    assert detected, f"expected an act to be detected for {query!r}"
    results = app_module.search_similar(query, top_k=6, act_filter=detected)
    assert results
    for r in results:
        haystack = (r["act_title"] + " " + r["act_short_name"]).lower()
        assert detected.lower() in haystack, (
            f"result from {r['act_title']!r} leaked past act filter {detected!r}"
        )
    assert expected_act_fragment.lower() in results[0]["act_title"].lower()


def test_r3_act_filter_holds_on_duplicated_index(dup_index):
    detected = dup_index.detect_act_from_query("bond under the Residential Tenancies Act")
    results = dup_index.search_similar("bond under the Residential Tenancies Act",
                                       top_k=6, act_filter=detected)
    assert results
    for r in results:
        assert detected.lower() in r["act_title"].lower()


def test_act_filter_with_no_matching_act_returns_nothing(app_module):
    results = app_module.search_similar("director duties", top_k=6, act_filter="Companies")
    assert results == [], "no Companies Act rows are in the fixture"


# --- R4 score sanity ---------------------------------------------------------

@pytest.mark.parametrize("query", [
    "maximum bond",
    "what is the purpose of the Privacy Act 2020",
    "self defence",
    "unfair contract terms",
])
def test_r4_score_sanity(app_module, query):
    results = app_module.search_similar(query, top_k=10)
    scores = [r["score"] for r in results]
    assert all(math.isfinite(s) for s in scores), "non-finite score"
    assert scores == sorted(scores, reverse=True), "scores not descending"
    # A pinned key section may sit below MIN_SIMILARITY, down to PINNED_MIN_SIMILARITY.
    assert all(r["score"] >= (app_module.PINNED_MIN_SIMILARITY if r["pinned"] else app_module.MIN_SIMILARITY)
               for r in results), "score below the floor"
    # Raw cosine similarity of normalised vectors is <= 1, so the capped
    # boosted score can never exceed MAX_BOOST.
    assert all(s <= app_module.MAX_BOOST + 1e-6 for s in scores), "boost cap exceeded"


def test_r4_no_results_below_threshold(app_module):
    results = app_module.search_similar("zxqv wumpus flibbertigibbet", top_k=10)
    for r in results:
        assert r["score"] >= app_module.MIN_SIMILARITY


# --- R5 latency --------------------------------------------------------------

def test_r5_latency_budget(app_module, golden):
    budget = golden["header"]["latency_budget_ms"]
    questions = [e["question"] for e in golden["entries"][:20]]
    timings = []
    for q in questions:
        started = time.perf_counter()
        app_module.search_similar(q, top_k=6,
                                  act_filter=app_module.detect_act_from_query(q))
        timings.append((time.perf_counter() - started) * 1000.0)
    timings.sort()
    p95 = timings[max(0, int(len(timings) * 0.95) - 1)]
    assert p95 <= budget["per_query_p95"], (
        f"p95 {p95:.1f} ms exceeds budget {budget['per_query_p95']} ms"
    )
    assert max(timings) <= budget["per_query_max"], (
        f"max {max(timings):.1f} ms exceeds budget {budget['per_query_max']} ms"
    )
