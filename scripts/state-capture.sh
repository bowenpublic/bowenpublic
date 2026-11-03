#!/bin/sh
# The state capture: a snapshot of Bowen's usage record as it stands, taken by
# hand whenever Joe wants one. Nothing runs this on a schedule.
#
#   scripts/state-capture.sh            pull the log, then capture
#   scripts/state-capture.sh --no-pull  capture from the archive copy as it stands
#
# Each capture is a folder named by the moment it was taken (UTC) under
# data/state/ (a link to ~/Library/Application Support/bowen/state, beside the
# archive copy and the fire log), and data/state/latest points at the newest:
#
#   report.txt          the summary from the epoch, 2026-10-27 00:00 UTC, to now
#   day.txt             the last 24 hours (never reaching back before the epoch)
#   health.json         GET /health as answered at that moment
#   stats.json          GET /admin/stats (the backend's own month buckets)
#   root.json           GET / (the version the backend reports)
#   test-sessions.txt   the list of the trust's own session ids, as it stood
#   archive.txt         the archive copy's files and sizes at that moment
#   manifest.txt        when, from what, and whether the pull succeeded
#
# state/log.txt keeps one line per capture. A capture is never rewritten; take
# another instead. A write-up that quotes a capture names its folder.
set -e
EPOCH="${FIRE_EPOCH:-2026-10-27}"
HOME_DIR="${BOWEN_HOME:-$HOME/Library/Application Support/bowen}"
ARCHIVE="${ARCHIVE_DIR:-$HOME_DIR/archive}"
STATE="${STATE_DIR:-$HOME_DIR/state}"
PYTHON="${PYTHON:-/usr/bin/python3}"
NOW="${STATE_NOW:-$(date -u +%s)}"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
SUMMARISE="$PROJECT/backend/scripts/today_queries.py"
TESTS="$ARCHIVE/test-sessions.txt"
LINK="$PROJECT/data/state"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$STATE/log.txt"; }

mkdir -p "$STATE" "$PROJECT/data"
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "data/state exists and is not a link; move it aside and run again" >&2
  exit 1
fi
[ -L "$LINK" ] || ln -sfn "$STATE" "$LINK"

if [ "$1" = "--no-pull" ]; then
  PULLED="not pulled (--no-pull)"
elif sh "$PROJECT/scripts/archive-pull.sh"; then
  PULLED="pulled $(date -u +%Y-%m-%dT%H:%M:%SZ)"
else
  PULLED="pull failed; captured from the copy as it stood"
  echo "The pull failed; capturing from the archive copy as it stands" >&2
fi
if [ ! -f "$ARCHIVE/queries.jsonl" ]; then
  echo "No archive copy at $ARCHIVE/queries.jsonl; nothing to capture" >&2
  exit 1
fi

STAMP=$(date -u -r "$NOW" +%Y-%m-%dT%H%MZ)
DIR="$STATE/$STAMP"
[ -e "$DIR" ] && DIR="$STATE/$(date -u -r "$NOW" +%Y-%m-%dT%H%M%SZ)"
TMP="$DIR.tmp"
rm -rf "$TMP"
mkdir -p "$TMP"

UNTIL=$(date -u -r "$NOW" +%Y-%m-%dT%H:%M:%SZ)
EPOCH_S=$(TZ=UTC date -j -f "%Y-%m-%d %H:%M:%S" "$EPOCH 00:00:00" +%s)
DAY_AGO=$((NOW - 86400))
[ "$DAY_AGO" -lt "$EPOCH_S" ] && DAY_AGO=$EPOCH_S
TESTOPT=""
[ -f "$TESTS" ] && TESTOPT="--test-sessions $TESTS" && cp "$TESTS" "$TMP/test-sessions.txt"

"$PYTHON" "$SUMMARISE" --file "$ARCHIVE/queries.jsonl" --since "$EPOCH" --until "$UNTIL" $TESTOPT --full > "$TMP/report.txt"
"$PYTHON" "$SUMMARISE" --file "$ARCHIVE/queries.jsonl" --since "$(date -u -r "$DAY_AGO" +%Y-%m-%dT%H:%M:%SZ)" --until "$UNTIL" $TESTOPT --full > "$TMP/day.txt"

# The backend as it stands. Health needs no token; stats does. Failures are recorded, not fatal.
URL="${BOWEN_API_URL:-$(security find-generic-password -s bowen-usage -a backend-url -w 2>/dev/null || true)}"
[ -n "$URL" ] || URL="https://respectful-endurance-production.up.railway.app"
URL="${URL%/}"
TOKEN="${ADMIN_TOKEN:-$(security find-generic-password -s bowen-usage -a admin-token -w 2>/dev/null || true)}"
BACKEND="reached"
if [ "$1" = "--no-pull" ]; then
  BACKEND="not asked (--no-pull)"
else
  curl -sS -f --max-time 30 "$URL/health" -o "$TMP/health.json" || BACKEND="health not reached"
  curl -sS -f --max-time 30 "$URL/" -o "$TMP/root.json" || BACKEND="$BACKEND; root not reached"
  if [ -n "$TOKEN" ]; then
    curl -sS -f --max-time 60 -H "X-Admin-Token: $TOKEN" "$URL/admin/stats" -o "$TMP/stats.json" || BACKEND="$BACKEND; stats not reached"
  else
    BACKEND="$BACKEND; stats skipped, no token"
  fi
fi

ls -l "$ARCHIVE" | awk 'NR > 1 { print $5, $6, $7, $8, $9 }' > "$TMP/archive.txt"
LINES=$(wc -l < "$ARCHIVE/queries.jsonl" | tr -d ' ')
SUM=$(shasum -a 256 "$ARCHIVE/queries.jsonl" | cut -d' ' -f1)

QUESTIONS=$(sed -n 's/^\([0-9][0-9]*\) questions, \([0-9][0-9]*\) sessions.*/\1 questions, \2 sessions/p' "$TMP/report.txt" | head -1)
[ -n "$QUESTIONS" ] || QUESTIONS="no questions"
{
  echo "captured: $UNTIL"
  echo "window: $EPOCH 00:00 UTC to $UNTIL (report.txt); last 24 hours to $UNTIL, cut at the epoch (day.txt)"
  echo "archive: $ARCHIVE/queries.jsonl, $LINES lines, sha256 $SUM, $PULLED"
  echo "backend: $URL, $BACKEND"
  echo "since the epoch: $QUESTIONS"
  echo "test sessions: $([ -f "$TESTS" ] && echo "$(grep -cv '^[[:space:]]*\(#\|$\)' "$TESTS" | tr -d ' ') ids from $TESTS, copied" || echo "no list on file")"
  echo "report: today_queries.py --since $EPOCH --until $UNTIL, $("$PYTHON" --version 2>&1)"
} > "$TMP/manifest.txt"
mv "$TMP" "$DIR"
ln -sfn "$DIR" "$STATE/latest"
log "captured $STAMP: $QUESTIONS since $EPOCH ($PULLED)"
echo "Written to data/state/$(basename "$DIR") (data/state/latest points at it)"
