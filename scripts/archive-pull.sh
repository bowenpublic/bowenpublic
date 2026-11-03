#!/bin/sh
# Pull the production query log into the archive copy.
#
#   scripts/archive-pull.sh
#
# Fetches GET /admin/logs from the Bowen backend and writes it, one JSON line per
# question, to ~/Library/Application Support/bowen/archive/queries.jsonl (a link
# at data/archive/). The copy is a mirror of the source and is overwritten on each
# pull; the fire log and the state capture read it, never production directly.
# One line per pull goes to archive/pull.log.
#
# The pull refuses to replace the copy with a shorter one, because production
# losing lines is something to look at, not something to copy. Set
# ARCHIVE_ALLOW_SHRINK=1 to accept it once, knowingly.
#
# Backend URL: BOWEN_API_URL, else the Keychain (service bowen-usage, account
# backend-url), else the built-in default. Token: ADMIN_TOKEN, else the Keychain
# (account admin-token). Nothing secret is written anywhere.
set -e
HOME_DIR="${BOWEN_HOME:-$HOME/Library/Application Support/bowen}"
ARCHIVE="${ARCHIVE_DIR:-$HOME_DIR/archive}"
PYTHON="${PYTHON:-/usr/bin/python3}"

URL="${BOWEN_API_URL:-$(security find-generic-password -s bowen-usage -a backend-url -w 2>/dev/null || true)}"
[ -n "$URL" ] || URL="https://respectful-endurance-production.up.railway.app"
URL="${URL%/}"
TOKEN="${ADMIN_TOKEN:-$(security find-generic-password -s bowen-usage -a admin-token -w 2>/dev/null || true)}"

mkdir -p "$ARCHIVE"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$ARCHIVE/pull.log"; }

if [ -z "$TOKEN" ]; then
  log "pull failed: no admin token (ADMIN_TOKEN or Keychain bowen-usage/admin-token)"
  exit 1
fi

TMPJ="$ARCHIVE/.pull.json.tmp"
TMPL="$ARCHIVE/.queries.jsonl.tmp"
rm -f "$TMPJ" "$TMPL"

if ! curl -sS -f --max-time 180 -H "X-Admin-Token: $TOKEN" "$URL/admin/logs" -o "$TMPJ"; then
  log "pull failed: could not fetch $URL/admin/logs"
  rm -f "$TMPJ"
  exit 1
fi

COUNT=$("$PYTHON" - "$TMPJ" "$TMPL" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
entries = d["entries"]
with open(sys.argv[2], "w") as f:
    for e in entries:
        f.write(json.dumps(e) + "\n")
if d.get("total") not in (None, len(entries)):
    sys.exit(f"the response says total {d.get('total')} but holds {len(entries)} entries")
print(len(entries))
PY
) || { log "pull failed: the response did not parse as the admin log"; rm -f "$TMPJ" "$TMPL"; exit 1; }
rm -f "$TMPJ"

OLD=0
[ -f "$ARCHIVE/queries.jsonl" ] && OLD=$(wc -l < "$ARCHIVE/queries.jsonl" | tr -d ' ')
if [ "$COUNT" -lt "$OLD" ] && [ "${ARCHIVE_ALLOW_SHRINK:-0}" != "1" ]; then
  log "pull refused: production returned $COUNT entries but the copy on file has $OLD; copy kept (ARCHIVE_ALLOW_SHRINK=1 to accept)"
  rm -f "$TMPL"
  exit 1
fi

mv "$TMPL" "$ARCHIVE/queries.jsonl"
log "pulled $COUNT entries from $URL/admin/logs (copy had $OLD)"
