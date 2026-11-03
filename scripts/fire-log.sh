#!/bin/sh
# The fire log: one sealed record a week of Bowen's usage, written by launchd
# and never edited.
#
#   scripts/fire-log.sh              seal every complete week not yet on file
#   scripts/fire-log.sh --no-pull    the same, from the archive copy as it stands
#   scripts/fire-log.sh --install    install the weekly launchd job (Tuesday 14:00)
#
# Weeks run from the epoch, 2026-10-27 00:00 UTC, in whole UTC days: the first
# is 27 October to 2 November, the next 3 to 9 November, and so on. Nothing
# before the epoch is read. A week is sealed once it has ended and the log has
# been pulled since; a week already on file is never touched, so a run after a
# missed one writes every week it owes and nothing else. Each week is a folder
# named by its first day under data/fire/ (a link to the copy below):
#
#   report.txt          the summary for exactly that week (--since/--until)
#   events.jsonl.gz     the week's raw entries, as the backend wrote them
#   test-sessions.txt   the list of the trust's own session ids, as it stood
#   manifest.txt        the window, the archive copy read, the count, the checksum
#
# fire/log.txt keeps one line per run. The folder lives outside the project,
# under ~/Library/Application Support/bowen/fire, because macOS will not let a
# launchd job touch ~/Desktop. So --install also copies this script, the pull
# script and backend/scripts/today_queries.py to
# ~/Library/Application Support/bowen/app/ and points the job at that copy.
# Run --install again after changing any of them.
set -e
EPOCH="${FIRE_EPOCH:-2026-10-27}"
HOME_DIR="${BOWEN_HOME:-$HOME/Library/Application Support/bowen}"
ARCHIVE="${ARCHIVE_DIR:-$HOME_DIR/archive}"
FIRE="${FIRE_DIR:-$HOME_DIR/fire}"
PYTHON="${PYTHON:-/usr/bin/python3}"
NOW="${FIRE_NOW:-$(date -u +%s)}"
APP="$(cd "$(dirname "$0")/.." && pwd)"
SUMMARISE="$APP/backend/scripts/today_queries.py"
TESTS="$ARCHIVE/test-sessions.txt"
LABEL="org.bowenpublic.fire-log"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WEEK=$((7 * 86400))

day_of() { date -u -r "$1" +%Y-%m-%d; }
secs_of() { TZ=UTC date -j -f "%Y-%m-%d %H:%M:%S" "$1 00:00:00" +%s; }
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$FIRE/log.txt"; }

if [ "$1" = "--install" ]; then
  PROJECT="$APP"
  mkdir -p "$HOME/Library/LaunchAgents" "$FIRE" "$ARCHIVE" "$HOME_DIR/state" \
           "$HOME_DIR/app/scripts" "$HOME_DIR/app/backend/scripts" "$PROJECT/data"
  for pair in "fire:$FIRE" "archive:$ARCHIVE" "state:$HOME_DIR/state"; do
    name="${pair%%:*}"; target="${pair#*:}"; link="$PROJECT/data/$name"
    if [ -e "$link" ] && [ ! -L "$link" ]; then
      echo "data/$name exists and is not a link; move it aside and run --install again" >&2
      exit 1
    fi
    ln -sfn "$target" "$link"
  done
  cp "$PROJECT/scripts/fire-log.sh" "$PROJECT/scripts/archive-pull.sh" "$HOME_DIR/app/scripts/"
  cp "$PROJECT/backend/scripts/today_queries.py" "$HOME_DIR/app/backend/scripts/"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/sh</string><string>$HOME_DIR/app/scripts/fire-log.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>14</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$FIRE/launchd.log</string>
  <key>StandardErrorPath</key><string>$FIRE/launchd.log</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string><key>PYTHON</key><string>$PYTHON</string></dict>
</dict>
</plist>
PL
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  echo "Installed: $LABEL runs every Tuesday at 14:00 (or at the next wake), sealing into data/fire/"
  echo "Weeks start on $EPOCH and run seven UTC days; the first seal is due after $(day_of $(( $(secs_of "$EPOCH") + WEEK ))) 00:00 UTC"
  exit 0
fi

mkdir -p "$FIRE"
if [ "$1" = "--no-pull" ]; then
  PULLED="not pulled (--no-pull)"
else
  if sh "$APP/scripts/archive-pull.sh"; then
    PULLED="pulled $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  else
    log "the pull failed, so no week is sealed this run; it will be tried again next time"
    exit 0
  fi
fi
if [ ! -x "$PYTHON" ]; then
  log "python3 not found at $PYTHON; nothing sealed" >&2
  exit 1
fi
if [ ! -f "$ARCHIVE/queries.jsonl" ]; then
  log "no archive copy at $ARCHIVE/queries.jsonl; nothing sealed" >&2
  exit 1
fi
ARCHIVE_LINES=$(wc -l < "$ARCHIVE/queries.jsonl" | tr -d ' ')
ARCHIVE_SUM=$(shasum -a 256 "$ARCHIVE/queries.jsonl" | cut -d' ' -f1)

START=$(secs_of "$EPOCH")
SEALED=0
while [ $((START + WEEK)) -le "$NOW" ]; do
  END=$((START + WEEK))
  FIRST=$(day_of "$START")
  LAST=$(day_of $((END - 86400)))
  UNTIL="$(day_of "$END")T00:00:00Z"
  DIR="$FIRE/$FIRST"
  if [ -e "$DIR" ]; then
    START=$END
    continue
  fi
  TMP="$DIR.tmp"
  rm -rf "$TMP"
  mkdir -p "$TMP"

  TESTOPT=""
  if [ -f "$TESTS" ]; then
    TESTOPT="--test-sessions $TESTS"
    cp "$TESTS" "$TMP/test-sessions.txt"
  fi
  "$PYTHON" "$SUMMARISE" --file "$ARCHIVE/queries.jsonl" --since "$FIRST" --until "$UNTIL" --raw | gzip -9n > "$TMP/events.jsonl.gz"
  "$PYTHON" "$SUMMARISE" --file "$ARCHIVE/queries.jsonl" --since "$FIRST" --until "$UNTIL" $TESTOPT --full > "$TMP/report.txt"

  COUNT=$(gzcat "$TMP/events.jsonl.gz" | wc -l | tr -d ' ')
  SUM=$(gzcat "$TMP/events.jsonl.gz" | shasum -a 256 | cut -d' ' -f1)
  REPORTED=$(sed -n 's/^\([0-9][0-9]*\) questions, .*/\1/p' "$TMP/report.txt" | head -1)
  CHECK="events and report agree"
  [ "$REPORTED" = "$COUNT" ] || CHECK="MISMATCH: report says $REPORTED questions"
  {
    echo "week: $FIRST to $LAST (UTC days), $FIRST 00:00 to $(day_of "$END") 00:00 UTC"
    echo "sealed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "archive: $ARCHIVE/queries.jsonl, $ARCHIVE_LINES lines, sha256 $ARCHIVE_SUM, $PULLED"
    echo "events: $COUNT lines in events.jsonl.gz ($CHECK)"
    echo "sha256: $SUM events.jsonl.gz, of the lines uncompressed (gzip -n, so the .gz is reproducible too)"
    echo "test sessions: $([ -f "$TESTS" ] && echo "$(grep -cv '^[[:space:]]*\(#\|$\)' "$TESTS" | tr -d ' ') ids from $TESTS, copied" || echo "no list on file")"
    echo "report: today_queries.py --since $FIRST --until $UNTIL, $("$PYTHON" --version 2>&1)"
  } > "$TMP/manifest.txt"
  mv "$TMP" "$DIR"
  log "sealed week $FIRST to $LAST: $COUNT questions, sha256 $SUM ($CHECK)"
  SEALED=$((SEALED + 1))
  START=$END
done

if [ "$SEALED" -eq 0 ]; then
  log "nothing to seal: the current week ($(day_of "$START") to $(day_of $((START + WEEK - 86400)))) ends $(day_of $((START + WEEK))) 00:00 UTC"
fi
