# Audit: how Bowen records and reports its own usage data

Written 3 November 2026, against the pattern in the Headless club's
`docs/2026-11-03-fire-log-and-state-capture-pattern.md` (four layers: source, fire log, state
capture, write-ups). Everything below was checked against the live backend and the two
repositories on this Mac the same afternoon.

## Verdict in one paragraph

Bowen has a source and it has write-ups. It has neither of the two layers in between. Nothing
is sealed on a clock, nothing is captured as a folder, and every number in every write-up to
date was read from a pull that was thrown away. The trust repo's weekly usage capture is the
closest thing to a fire log, but it holds aggregates only, fires on a session-start hook rather
than a clock, and cannot be re-run because it keeps no raw lines. The port is small: the
summariser is one Python file, the source is one HTTPS call, and a Bowen launchd job already
exists to copy from.

## Layer 1: the source

**What it is**
- File: `queries.jsonl` on the Railway volume `respectful-endurance-volume`, mounted at
  `/app/logs` (5 GB allocated, 151 MB reported used; the log itself serialises to about 1 MB).
- Written by: `log_query` in `backend/app/main.py`, one JSON line per answered question.
- Fields: timestamp (UTC, microseconds), session_id, query, response, detected_act,
  sources_count, response_time_ms. No IP since 28 Sep 2026; the one scrub rewrote the file.
- Size today: 483 entries, 198 sessions, 2 Mar 2026 to 3 Nov 2026 03:17 UTC. Timestamps are
  in order.
- Read by: `GET /admin/logs` with the `X-Admin-Token` header, which returns the whole file as
  one JSON document. Took 2.1 seconds for 1 MB today. There is no `since` parameter; the
  client filters.

**How it measures against the pattern**
- One file for all time, not one file per day. The pattern wants day boundaries that match the
  source's own. Bowen's source has no boundaries, so the fire log must cut by timestamp. That
  is fine; it just means the raw bundle is "lines with timestamp in window", and the manifest
  must say so.
- Not strictly read-only. It has been rewritten in place once (the IP scrub). Acceptable, but
  it should stay the only exception.
- No second copy anywhere. The Railway volume is the only persistent copy of the whole log. If
  the volume is lost or the service is recreated, eight months of record go with it. The two
  local copies are a March development log (49 lines, all still carrying 127.0.0.1 IPs) and an
  8-line local copy (3 with IPs). Neither is a mirror. Both are still on the open list from the
  27 Sep ticket in the trust repo.
- The 151 MB used on the volume is unexplained against a 1 MB log. Worth one `ls -la` over
  `railway ssh` to see what else is there.

## Layer 2: the fire log. Does not exist.

Three things act a little like it, none of them is one:

**Trust repo, `tools/usage/usage.py pulse`**
- What it does: on every Claude session start, calls `/admin/stats` and files a JSON capture
  under `media/reports/captures/` if the newest one is seven days old.
- Series so far: 28 Sep, 5 Oct, 14 Oct, 27 Oct, 3 Nov. Gaps of 7, 9, 13 and 7 days.
- Why it is not a fire log: it fires when Joe opens a session, not on a clock, so the period is
  whatever the gap happened to be. It holds aggregates (monthly totals, top Acts) with no raw
  lines, so nothing can be re-run when the query or classification changes. It is a mirror of
  the backend's own month buckets, which is useful, but it is not a sealed week.

**Trust repo, `tools/railway/railway.py pulse`**
- Counts requests since the last deploy from Railway's deployment log. The window starts at
  the deploy, so it resets every push. A health signal, not a record.

**Product repo, `backend/scripts/today_queries.py`**
- Prints to stdout and files nothing. Its only window is `--days N`, meaning "the last N NZ
  days from now", which is exactly the moving window the pattern says not to use.

## Layer 3: the state capture. Does not exist.

- The 3 Nov trustee report says "pulled at 14:13". That pull was not kept. The report gives 28
  questions and 13 sessions for the day; the same day now reads 52 questions and 30 sessions,
  because the day went on. Nobody can re-read the report against the numbers it was written
  from.
- The 2 Nov campaign session file was pulled "at about 16:30". Same situation.
- The mutable state that would belong in a capture: `/health` and `/admin/stats` output, the
  deployed commit and version (`/` still says 0.2.0), the corpus release tag, and the list of
  known test sessions (see below). None of it is written down beside any report.

## Layer 4: the write-ups. Exist, but the citations point at nothing.

**On file**
- `logs/week1-analysis.md` (March, NZ-time week, from a local copy; gitignored).
- `logs/campaign-2026-11-02-sessions.md` (gitignored).
- `docs/trust-traffic-2026-11-03.md` and `docs/session-8514bf3a-raw-2026-11-03.md` (untracked,
  in a tracked folder).
- `~/bpct/media/METRICS.md` (trust repo, append-only register, cites the capture files).

**Problems**
- Three clocks. `today_queries.py` and the write-ups count NZ days. `/admin/stats` and
  `METRICS.md` count UTC months. The headless pattern uses UTC days. The March figures already
  disagree between the two (132 for the NZ-time week, 152 for the UTC month), and the note in
  `METRICS.md` has to explain it. Pick one clock for the record and translate in prose.
- Test traffic is in the same file as real traffic and is separated by eye each time. The
  trust's own notes say "subtract 75 test queries from November" and the 3 Nov report decides
  by timing pattern which sessions were scripted. This is the "classification rules move"
  problem in its purest form: a report written next month would draw the line somewhere else.
- Two write-ups holding verbatim public questions and answers are sitting in `docs/` of a
  public repository, untracked. One `git add -A` publishes them. The trust repo's own rule is
  that nothing a member of the public typed is copied into a repository. These belong with the
  2 Nov file in a gitignored or out-of-tree folder. This is the one item to act on today.

## What the pattern needs from Bowen, decided

**The source and its unit**
- A full pull of `/admin/logs`, converted back to JSONL, written to `archive/queries.jsonl`
  as a mirror. Overwritten each pull; it is a copy of the source, not the record.
- The raw bundle for a week is the lines whose timestamp falls in the window. The manifest
  names the window, the line count, the sha256 and the version at `/`.

**The query**
- `backend/scripts/today_queries.py`, given `--since` and `--until` (UTC ISO timestamps) and a
  `--file` option so it can read the mirror instead of calling production. Keep `--days` as a
  convenience that resolves to the fixed window.
- Add a summary header the fire log can print: questions, sessions, answered without sources,
  median and slowest answer time, questions per detected Act, and a count of questions from
  known test sessions.

**The epoch**
- Recommended: 2026-10-27 00:00 UTC, a Tuesday, so weeks seal at the same boundary as the
  club's and week 1 (27 Oct to 2 Nov UTC) holds the testing rounds and campaign day 1 as one
  unit. The data for it is on hand, so sealing a past week is exact, not a reconstruction.
- Alternative: 2026-11-03, today, which is what the pattern literally says. It leaves the
  campaign's first days outside the record. Joe's call; the script takes either.

**The period**
- A week. The site moves daily now, but 50 to 80 questions a day is a week's worth of reading,
  not a day's.

**The mutable state**
- `/health`, `/admin/stats`, `/` (version), the current corpus release tag from the Dockerfile.
- A `test-sessions.txt` list: every session id the trust's own tools create when they ask the
  live site (the question-of-the-day tool, testing rounds, re-checks). Today those tools do not
  record the session id they used. They should, in one line each, so the summariser can label
  the traffic instead of guessing from timing.

**Where the records live**
- `~/Library/Application Support/bowen/` with `archive/`, `fire/`, `state/`, and `app/` (the
  copy of the summariser for launchd). launchd cannot write under `~/Desktop`, where the
  product repo lives, and the raw bundles must not sit in either repository: the product repo
  is public and the trust repo forbids public text.
- Symlinks `data/fire` and `data/state` in the product repo, gitignored. Write-ups stay in
  `docs/` but quote counts, not people.
- The admin token from the Keychain (service `bowen-usage`, already set up for the trust
  tools), never from a file the job reads.

**The scheduler**
- A copy of `~/Library/LaunchAgents/org.bowenpublic.social-fire.plist` with the label
  `org.bowenpublic.fire-log`, Tuesday 14:00 local, after the 00:00 UTC Tuesday boundary in
  both NZ zones. The pull is an HTTPS call, so the "failed pull" case is a non-200 or timeout,
  logged and retried next Tuesday.

## Order of work

1. Move the two verbatim write-ups out of `docs/` today. Scrub or delete the two local
   March log copies while at it (open since 27 Sep).
2. `--since`, `--until`, `--file` on `today_queries.py`, with tests.
3. `scripts/state-capture.sh`: pull, convert, summarise epoch to now, copy the mutable state,
   manifest. Run it once and cite that folder in the next trustee note.
4. `scripts/fire-log.sh` with `--no-pull` and the environment overrides, tested into a
   scratch folder with the epoch above. Expected: one or two sealed weeks, a second run seals
   nothing, line count in each manifest equals the question count in its report.
5. `--install`, kickstart once, read `log.txt`.
6. Have the trust's live-site tools write their session ids to the test-sessions list, so
   from week 2 the split between test and visitor traffic is a lookup, not a judgement.
7. Point `METRICS.md` rows at fire weeks rather than at pulse captures, once two weeks exist.

What never changes afterwards: the epoch, a sealed week, a capture. If `today_queries.py` or
the Act detection changes, the old reports stand and the raw bundle is there to re-run.

## Addendum, 4 November 2026: what was built

Steps 2 to 5 of the order of work were done the next morning. The epoch is 27 October 2026
00:00 UTC. `scripts/README.md` is the reference for what each folder holds and when to rerun
`--install`.

- `backend/scripts/today_queries.py` takes `--since`, `--until`, `--file`, `--raw` and
  `--test-sessions`; 13 tests in `backend/tests/test_today_queries.py`.
- `scripts/archive-pull.sh`, `scripts/state-capture.sh` and `scripts/fire-log.sh` under
  `~/Library/Application Support/bowen/`, linked in as `data/archive`, `data/fire`, `data/state`.
- First capture: `data/state/2026-11-03T2130Z/` (223 questions, 135 sessions since the epoch).
- First sealed week, written by launchd: `data/fire/2026-10-27/` (189 questions, 117 sessions,
  27 October to 2 November UTC). The next seals on Tuesday 10 November at 14:00.
- The two local March logs were moved, unscrubbed, to `legacy/` in the same folder, with a
  README. The 27 September ticket's "scrub the local copies" item is closed by archiving them
  out of tree instead, on Joe's decision.
- Still open: step 6 (the trust's tools recording their session ids into
  `data/archive/test-sessions.txt`) and step 7 (`METRICS.md` rows pointing at fire weeks).
