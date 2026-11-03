# The usage record: archive copy, fire log, state capture

Bowen's only persistent record of use is `queries.jsonl` on the Railway volume, one JSON line
per answered question, served whole by `GET /admin/logs`. Three things are kept beside a copy of
it on this Mac, under `~/Library/Application Support/bowen/`, linked into the project as
`data/archive/`, `data/fire/` and `data/state/` (all git ignored). None of them writes to
production; they only read it. The pattern is written up in the Headless club's
`docs/2026-11-03-fire-log-and-state-capture-pattern.md`; the audit that led to this port is
`docs/2026-11-03-data-report-audit.md`.

The epoch is **27 October 2026, 00:00 UTC**. Nothing before it is read by the fire log or the
capture (the archive copy still holds everything back to March 2026). Weeks run seven UTC days
from the epoch: 27 October to 2 November, 3 to 9 November, and so on. The epoch, a sealed week
and a capture are never changed afterwards.

## The three scripts

**`scripts/archive-pull.sh`**
- What: pulls `/admin/logs` and writes it as JSON lines to `data/archive/queries.jsonl`, a
  mirror of the source, overwritten each pull. One line per pull in `data/archive/pull.log`.
- Refuses to replace the copy with a shorter one (`ARCHIVE_ALLOW_SHRINK=1` to accept, knowingly).
- Secrets: the backend URL and admin token come from the macOS Keychain, service `bowen-usage`,
  accounts `backend-url` and `admin-token` (the same entries the trust repo's `tools/usage` uses).
  `BOWEN_API_URL` and `ADMIN_TOKEN` in the environment override them. Nothing is written down.

**`scripts/state-capture.sh`** (by hand, whenever wanted; never on a schedule)
- What: pulls, then writes `data/state/<UTC moment>/` and repoints `data/state/latest`:
  `report.txt` (epoch to now), `day.txt` (the last 24 hours), both with answers in full, `health.json`, `stats.json`,
  `root.json` (what the backend answered at that moment), `test-sessions.txt` (copied, if on
  file), `archive.txt` (the copy's files and sizes), `manifest.txt`.
- `--no-pull` captures from the copy as it stands. A failed pull is recorded in the manifest and
  the capture goes ahead from the copy.
- A write-up that quotes numbers names the capture folder it was drawn from.

**`scripts/fire-log.sh`** (launchd, every Tuesday at 14:00 local; by hand only to catch up)
- What: pulls, then seals every finished week not yet on file as `data/fire/<first UTC day>/`:
  `report.txt` (the summary for exactly that week, answers in full), `events.jsonl.gz` (the week's raw entries as
  the backend wrote them), `test-sessions.txt` (copied, if on file), `manifest.txt` (window,
  archive copy read, line count, sha256 of the uncompressed lines).
- A week already on file is never touched. A run before the week has ended writes nothing. If
  the pull fails nothing is sealed and it is tried again next Tuesday, so no sealed week is
  missing its last hours. A Mac asleep on Tuesday seals every week it owes when it next runs.
- `data/fire/log.txt` has one line per run, including "nothing to seal"; `data/fire/launchd.log`
  whatever the job printed.
- Tuesday 14:00 local is after the 00:00 UTC Tuesday boundary in both NZ zones (13:00 NZDT,
  12:00 NZST).

## The summariser

`backend/scripts/today_queries.py` is what all three read with. It takes a fixed window in UTC,
`--since` inclusive and `--until` exclusive, a bare date meaning 00:00 UTC; `--file` reads the
archive copy instead of calling production; `--raw` prints the entries themselves (the bundle);
`--test-sessions FILE` labels questions from the trust's own tools. `--days N` is still there for
a quick look at the last N NZ days. Tests: `backend/tests/test_today_queries.py`.

```
python3 backend/scripts/today_queries.py --file data/archive/queries.jsonl --since 2026-10-27 --until 2026-11-03
```

## launchd and the copy of the code

launchd cannot read or write under `~/Desktop`, where this repo lives, so `--install` copies
`scripts/fire-log.sh`, `scripts/archive-pull.sh` and `backend/scripts/today_queries.py` to
`~/Library/Application Support/bowen/app/` and points the job (`org.bowenpublic.fire-log`) at
that copy. The copy is only as fresh as the last `--install`. **Run `sh scripts/fire-log.sh
--install` again after changing any of the three.** The job runs the system `/usr/bin/python3`
(3.9); the summariser uses only the standard library for that reason.

To run the job now by hand: `launchctl kickstart -k gui/$(id -u)/org.bowenpublic.fire-log`,
then read `data/fire/log.txt`. To remove it: `launchctl bootout gui/$(id -u)/org.bowenpublic.fire-log`
and delete `~/Library/LaunchAgents/org.bowenpublic.fire-log.plist`.

## Test sessions

`data/archive/test-sessions.txt` lists session ids known to be the trust's own tools (testing
rounds, the question-of-the-day drafts, re-checks), one per line, `#` for comments. When it
exists, every report labels those questions and gives the count from everyone else, and every
sealed week and capture keeps a copy of the list as it stood. The trust's tools do not record
their session ids yet; until they do the file is empty or absent and the split is by eye.

## Testing a change

Run into a scratch folder against the real copy, with the environment overrides, before
reinstalling:

```
BOWEN_HOME=/path/to/scratch ARCHIVE_DIR="$HOME/Library/Application Support/bowen/archive" \
  FIRE_EPOCH=2026-10-27 sh scripts/fire-log.sh --no-pull
```

Expected: every finished week since the epoch sealed, a second identical run seals nothing, and
the line count in each `manifest.txt` equals the question count in its `report.txt` (the script
checks this and says MISMATCH if not). `FIRE_NOW=<epoch seconds>` moves the clock.

## What is where, and what never changes

- `archive/`: the mirror of production and `pull.log`. Overwritten by each pull. Also
  `test-sessions.txt`.
- `fire/`: one folder per sealed week. Never rewritten.
- `state/`: one folder per capture, `latest` pointing at the newest. Never rewritten.
- `legacy/`: the two local development logs from March 2026, which still carry an IP field.
  Kept for posterity, never in a repository, never rewritten. `legacy/README.txt` says what
  each is.
- `app/`: the copy of the code launchd runs.

The question text in the archive, the sealed weeks and the captures is what members of the
public typed. It stays in this folder. Write-ups in `docs/` quote counts, not people; a file
that does quote a question goes in `logs/` or is git ignored by name.
