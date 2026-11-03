"""
Tests for backend/scripts/today_queries.py: the fixed window, the raw bundle, the summary.

The script is loaded from its path (it is not a package). Every test reads a local file;
production is never called (the conftest blocks the network anyway).
"""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "today_queries.py"
spec = importlib.util.spec_from_file_location("today_queries", SCRIPT)
tq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tq)


def entry(ts, session="s1", act=None, sources=0, ms=1000, query="q", response="a"):
    return {"timestamp": ts, "session_id": session, "query": query, "response": response,
            "detected_act": act, "sources_count": sources, "response_time_ms": ms}


ENTRIES = [
    entry("2026-10-26T23:59:59.000000Z", "before"),
    entry("2026-10-27T00:00:00.000000Z", "first", "Privacy", 3, 5000),
    entry("2026-10-30T12:00:00.500000Z", "mid", None, 0, 9000),
    entry("2026-11-02T23:59:59.999999Z", "last", "Privacy", 2, 17000),
    entry("2026-11-03T00:00:00.000000Z", "after", "Residential Tenancies", 4, 3000),
]


@pytest.fixture
def logfile(tmp_path):
    p = tmp_path / "queries.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in ENTRIES))
    return p


# --- parse_when ----------------------------------------------------------------

def test_bare_date_is_midnight_utc():
    assert tq.parse_when("2026-10-27") == datetime(2026, 10, 27, tzinfo=timezone.utc)


def test_z_suffix_and_offset_are_honoured():
    assert tq.parse_when("2026-11-03T00:00:00Z") == datetime(2026, 11, 3, tzinfo=timezone.utc)
    # 13:00 NZDT on 3 Nov is 00:00 UTC on 3 Nov
    assert tq.parse_when("2026-11-03T13:00:00+13:00") == datetime(2026, 11, 3, tzinfo=timezone.utc)


def test_naive_timestamp_means_utc():
    assert tq.parse_when("2026-11-03T05:30:00") == datetime(2026, 11, 3, 5, 30, tzinfo=timezone.utc)


# --- the window ----------------------------------------------------------------

def test_since_inclusive_until_exclusive(logfile):
    rows = tq.in_window(tq.read_file(logfile), tq.parse_when("2026-10-27"), tq.parse_when("2026-11-03"))
    assert [e["session_id"] for _, e in rows] == ["first", "mid", "last"]


def test_no_since_reads_from_start_of_log(logfile):
    rows = tq.in_window(tq.read_file(logfile), None, tq.parse_when("2026-10-27"))
    assert [e["session_id"] for _, e in rows] == ["before"]


def test_days_resolves_to_nz_midnight():
    class A:
        since = until = None
        days = 1
    now = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)  # 14:00 NZDT on 3 Nov
    since, until = tq.resolve_window(A, now)
    assert since == datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc)  # 00:00 NZDT 3 Nov
    assert until == now


def test_days_two_goes_back_a_further_nz_day():
    class A:
        since = until = None
        days = 2
    now = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)
    since, _ = tq.resolve_window(A, now)
    assert since == datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc)


def test_since_overrides_days():
    class A:
        since = "2026-10-27"
        until = None
        days = 99
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    assert tq.resolve_window(A, now) == (tq.parse_when("2026-10-27"), now)


# --- --raw ---------------------------------------------------------------------

def test_raw_reproduces_the_lines_in_the_window(logfile, capsys):
    tq.main(["--file", str(logfile), "--since", "2026-10-27", "--until", "2026-11-03", "--raw"])
    out = capsys.readouterr().out
    original = logfile.read_text().splitlines()
    assert out.splitlines() == original[1:4]


def test_raw_skips_blank_lines(tmp_path, capsys):
    p = tmp_path / "q.jsonl"
    p.write_text(json.dumps(ENTRIES[1]) + "\n\n" + json.dumps(ENTRIES[2]) + "\n")
    tq.main(["--file", str(p), "--since", "2026-10-27", "--until", "2026-11-03", "--raw"])
    assert len(capsys.readouterr().out.splitlines()) == 2


# --- the summary ---------------------------------------------------------------

def test_summary_counts(logfile):
    rows = tq.in_window(tq.read_file(logfile), tq.parse_when("2026-10-27"), tq.parse_when("2026-11-03"))
    lines = tq.summary_lines(rows, tq.parse_when("2026-10-27"), tq.parse_when("2026-11-03"), set())
    assert lines[0] == "window: 2026-10-27T00:00:00Z to 2026-11-03T00:00:00Z (UTC)"
    assert "Tue 27 Oct 2026 13:00 to Tue 03 Nov 2026 13:00 (NZ)" in lines[1]
    assert lines[2] == "3 questions, 3 sessions, 1 answered with no retrieved sources"
    assert lines[3] == "answer time: median 9000 ms, slowest 17000 ms, fastest 5000 ms"
    assert lines[4] == "by act: Privacy 2, none 1"


def test_summary_labels_test_sessions(logfile, tmp_path, capsys):
    ts = tmp_path / "test-sessions.txt"
    ts.write_text("# the trust's own runs\nmid\n\nlast   # re-check\n")
    tq.main(["--file", str(logfile), "--since", "2026-10-27", "--until", "2026-11-03", "--test-sessions", str(ts)])
    out = capsys.readouterr().out
    assert "known test sessions: 2 questions in 2 sessions (so 1 questions in 1 sessions from everyone else)" in out
    assert out.count("[test]") == 2


def test_report_is_empty_but_well_formed_for_an_empty_window(logfile, capsys):
    tq.main(["--file", str(logfile), "--since", "2027-01-01", "--until", "2027-01-08"])
    out = capsys.readouterr().out
    assert "0 questions, 0 sessions, 0 answered with no retrieved sources" in out
