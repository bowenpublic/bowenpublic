#!/usr/bin/env python3
"""
Summarise the questions Bowen handled in a window of time.

Reads the production query log (GET /admin/logs) or a local copy of it, keeps the
entries whose timestamp falls in the window, and prints a report: a count header,
then every question with the answer. With --raw it prints the entries themselves
as JSON lines instead, which is how the fire log builds a week's bundle.

The window is in UTC, `--since` inclusive and `--until` exclusive. A bare date means
00:00 UTC on that day. `--days N` is the old shortcut: midnight N-1 days ago, NZ
time, to now. Fixed windows are what the fire log and the state capture use, so the
same command run later gives the same answer.

Usage:
    python3 backend/scripts/today_queries.py                        # today, NZ time, from production
    python3 backend/scripts/today_queries.py --days 2               # the last two NZ days
    python3 backend/scripts/today_queries.py --since 2026-10-27 --until 2026-11-03
    python3 backend/scripts/today_queries.py --file data/archive/queries.jsonl --since 2026-10-27 --until 2026-11-03
    python3 backend/scripts/today_queries.py ... --raw              # the entries as JSON lines
    python3 backend/scripts/today_queries.py ... --full             # untruncated answers
    python3 backend/scripts/today_queries.py ... --test-sessions data/archive/test-sessions.txt

Production access: the backend URL comes from BOWEN_API_URL, then the macOS Keychain
(service bowen-usage, account backend-url), then a built-in default. The admin token
comes from ADMIN_TOKEN, then the Keychain (account admin-token), then backend/.env.
Needs only the standard library; runs under the system python3 (3.9).
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_PROD = "https://respectful-endurance-production.up.railway.app"
NZ = ZoneInfo("Pacific/Auckland")
KEYCHAIN_SERVICE = "bowen-usage"


# --- Access to production ------------------------------------------------------

def keychain(account):
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def backend_url():
    return (os.getenv("BOWEN_API_URL") or keychain("backend-url") or DEFAULT_PROD).rstrip("/")


def admin_token():
    tok = os.getenv("ADMIN_TOKEN") or keychain("admin-token")
    if tok:
        return tok
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ADMIN_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ADMIN_TOKEN not found in the environment, the Keychain or backend/.env")


def fetch_production():
    req = urllib.request.Request(backend_url() + "/admin/logs", headers={"X-Admin-Token": admin_token()})
    with urllib.request.urlopen(req, timeout=120) as r:
        entries = json.load(r)["entries"]
    return [(json.dumps(e), e) for e in entries]


def read_file(path):
    """Yield (original line, parsed entry) so --raw can reproduce the file byte for byte."""
    out = []
    with open(path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            out.append((line, json.loads(line)))
    return out


# --- The window ----------------------------------------------------------------

def parse_when(s):
    """'2026-10-27' -> 2026-10-27T00:00:00Z; full ISO with Z or an offset is honoured; naive means UTC."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if len(s) == 10:
        s += "T00:00:00+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def entry_time(e):
    return datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)


def resolve_window(a, now=None):
    now = now or datetime.now(timezone.utc)
    if a.since or a.until:
        since = parse_when(a.since) if a.since else None
        until = parse_when(a.until) if a.until else now
    else:
        start_nz = now.astimezone(NZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=a.days - 1)
        since, until = start_nz.astimezone(timezone.utc), now
    return since, until


def in_window(rows, since, until):
    kept = []
    for line, e in rows:
        t = entry_time(e)
        if since is not None and t < since:
            continue
        if t >= until:
            continue
        kept.append((line, e))
    return kept


def load_test_sessions(path):
    """One session id per line; blank lines and # comments ignored."""
    ids = set()
    if not path:
        return ids
    p = Path(path)
    if not p.exists():
        return ids
    for line in p.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.add(line)
    return ids


# --- The report ----------------------------------------------------------------

def fmt_utc(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_nz(dt):
    return dt.astimezone(NZ).strftime("%a %d %b %Y %H:%M")


def summary_lines(rows, since, until, test_ids):
    entries = [e for _, e in rows]
    sessions = {e["session_id"] for e in entries}
    no_src = sum(1 for e in entries if not e.get("sources_count"))
    times = sorted(e["response_time_ms"] for e in entries if isinstance(e.get("response_time_ms"), int))
    acts = {}
    for e in entries:
        k = e.get("detected_act") or "none"
        acts[k] = acts.get(k, 0) + 1
    test_entries = [e for e in entries if e["session_id"] in test_ids]
    test_sessions = {e["session_id"] for e in test_entries}

    lines = []
    lines.append(f"window: {'(start of log)' if since is None else fmt_utc(since)} to {fmt_utc(until)} (UTC)")
    if since is not None:
        lines.append(f"        {fmt_nz(since)} to {fmt_nz(until)} (NZ)")
    lines.append(f"{len(entries)} questions, {len(sessions)} sessions, {no_src} answered with no retrieved sources")
    if times:
        lines.append(f"answer time: median {int(statistics.median(times))} ms, slowest {times[-1]} ms, fastest {times[0]} ms")
    if acts:
        top = sorted(acts.items(), key=lambda kv: (-kv[1], kv[0]))
        lines.append("by act: " + ", ".join(f"{k} {n}" for k, n in top))
    if test_ids:
        lines.append(f"known test sessions: {len(test_entries)} questions in {len(test_sessions)} sessions "
                     f"(so {len(entries) - len(test_entries)} questions in {len(sessions) - len(test_sessions)} sessions from everyone else)")
    return lines


def print_report(rows, since, until, test_ids, full):
    for line in summary_lines(rows, since, until, test_ids):
        print(line)
    print()
    for _, e in rows:
        t = entry_time(e).astimezone(NZ)
        ans = e["response"] if full else e["response"][:300].replace("\n", " ")
        tag = "  [test]" if e["session_id"] in test_ids else ""
        print(f"[{t:%Y-%m-%d %H:%M} NZ] session {e['session_id'][:8]}{tag}  act={e.get('detected_act')}  "
              f"sources={e.get('sources_count')}  {e.get('response_time_ms')}ms")
        print(f"  Q: {e['query']}")
        print(f"  A: {ans}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Summarise Bowen's query log over a window")
    ap.add_argument("--days", type=int, default=1, help="NZ days back from now (default 1 = today); ignored if --since or --until is given")
    ap.add_argument("--since", help="window start, UTC, inclusive: 2026-10-27 or 2026-10-27T00:00:00Z")
    ap.add_argument("--until", help="window end, UTC, exclusive (default now)")
    ap.add_argument("--file", help="read this queries.jsonl instead of calling production")
    ap.add_argument("--raw", action="store_true", help="print the entries in the window as JSON lines, not a report")
    ap.add_argument("--full", action="store_true", help="print full answers")
    ap.add_argument("--test-sessions", help="file of session ids known to be the trust's own tools, one per line")
    a = ap.parse_args(argv)

    rows = read_file(a.file) if a.file else fetch_production()
    since, until = resolve_window(a)
    rows = in_window(rows, since, until)

    if a.raw:
        for line, _ in rows:
            print(line)
        return

    print_report(rows, since, until, load_test_sessions(a.test_sessions), a.full)


if __name__ == "__main__":
    main()
