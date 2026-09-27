"""
scrub_log_ips.py

Remove the "ip" field from every entry in a query log written by an earlier version,
when the backend recorded the client IP address beside each query.

Dry run by default: prints how many entries carry an IP and changes nothing.
With --apply the file is rewritten in place through a temporary file in the
same directory, so a crash cannot leave a half-written log. No backup is kept,
because a backup would hold the addresses this script exists to remove.

Usage:
    python backend/scripts/scrub_log_ips.py                      # dry run, $LOGS_DIR/queries.jsonl
    python backend/scripts/scrub_log_ips.py --apply
    python backend/scripts/scrub_log_ips.py path/to/queries.jsonl --apply
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Remove IP addresses from a Bowen query log")
    p.add_argument("logfile", nargs="?", default=None,
                   help="path to queries.jsonl (default: $LOGS_DIR/queries.jsonl, or logs/queries.jsonl)")
    p.add_argument("--apply", action="store_true", help="rewrite the file (default is a dry run)")
    a = p.parse_args()

    path = Path(a.logfile) if a.logfile else Path(os.getenv("LOGS_DIR", "logs")) / "queries.jsonl"
    if not path.exists():
        sys.exit(f"No log file at {path}")

    total = with_ip = unparsed = 0
    out_lines = []
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # Keep the count honest; an unparseable line cannot be scrubbed safely, so it is dropped on --apply
                unparsed += 1
                continue
            if "ip" in entry:
                with_ip += 1
                del entry["ip"]
            out_lines.append(json.dumps(entry) + "\n")

    print(f"{path}: {total} entries, {with_ip} with an IP address, {unparsed} unparseable")
    if not a.apply:
        print("(dry run, nothing changed; add --apply to rewrite the file)")
        return
    if with_ip == 0 and unparsed == 0:
        print("Nothing to scrub.")
        return

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".queries-scrub-")
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(out_lines)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    print(f"Rewritten: {len(out_lines)} entries kept, {with_ip} IP addresses removed, {unparsed} unparseable lines dropped.")


if __name__ == "__main__":
    main()
