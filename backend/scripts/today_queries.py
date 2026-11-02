#!/usr/bin/env python3
"""
Print the questions and answers Bowen handled today (New Zealand time).

Pulls /admin/logs from production using ADMIN_TOKEN from backend/.env.

Usage:
    python3 backend/scripts/today_queries.py              # today, NZ time
    python3 backend/scripts/today_queries.py --days 2     # last 2 NZ days
    python3 backend/scripts/today_queries.py --full       # untruncated answers
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROD = os.getenv("BOWEN_API_URL", "https://respectful-endurance-production.up.railway.app")
NZ = ZoneInfo("Pacific/Auckland")


def admin_token() -> str:
    tok = os.getenv("ADMIN_TOKEN")
    if tok:
        return tok
    env = Path(__file__).resolve().parents[1] / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ADMIN_TOKEN not found in env or backend/.env")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1, help="how many NZ days back (default 1 = today)")
    ap.add_argument("--full", action="store_true", help="print full answers")
    a = ap.parse_args()

    req = urllib.request.Request(f"{PROD}/admin/logs", headers={"X-Admin-Token": admin_token()})
    with urllib.request.urlopen(req, timeout=90) as r:
        entries = json.load(r)["entries"]

    start_nz = datetime.now(NZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=a.days - 1)
    start_utc = start_nz.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    today = [e for e in entries if e["timestamp"] >= start_utc]

    sessions = {e["session_id"] for e in today}
    no_src = sum(1 for e in today if not e.get("sources_count"))
    print(f"Since {start_nz:%a %d %b %Y 00:00} NZ: {len(today)} questions, {len(sessions)} sessions, "
          f"{no_src} answered with no retrieved sources\n")

    for e in today:
        t = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone(NZ)
        ans = e["response"] if a.full else e["response"][:300].replace("\n", " ")
        print(f"[{t:%H:%M}] session {e['session_id'][:8]}  act={e.get('detected_act')}  "
              f"sources={e.get('sources_count')}  {e.get('response_time_ms')}ms")
        print(f"  Q: {e['query']}")
        print(f"  A: {ans}\n")


if __name__ == "__main__":
    main()
