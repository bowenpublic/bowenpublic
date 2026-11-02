# Bowen retrieval + contract harness

Prerequisites for the probe swarm described in `tests/SWARM-CHARTER.md`
(commission C-001). Nothing here ever calls the Anthropic API or touches a
remote host: `conftest.py` blocks every non-local socket for the duration of the
run and swaps in a stub LLM.

## Running

From the repo root:

```bash
EMBEDDINGS_DIR=backend/tests/fixtures/mini BOWEN_STUB_LLM=1 \
  backend/venv/bin/python -m pytest backend/tests -q
```

Both variables have safe defaults in `conftest.py`, so a bare
`backend/venv/bin/python -m pytest backend/tests -q` works too. `BOWEN_STUB_LLM`
is mandatory — the suite refuses to run without it.

## Layout

| Path | What it is |
|---|---|
| `conftest.py` | Imports `backend.app.main` *without* running `startup()`, loads the index from `EMBEDDINGS_DIR`, installs the stub client, blocks the network |
| `golden/retrieval.json` | 63 golden `(question, act, section, notes)` entries + header (data release, latency budget) |
| `golden/baseline.json` | Recorded pass set and known misses; the regression lock |
| `golden_runner.py` | Shared evaluation helpers (also used by `scripts/run_golden.py`) |
| `test_retrieval.py` | S1 — R1 uniqueness, R3 act filter, R4 score sanity, R5 latency, dedupe behaviour |
| `test_golden_retrieval.py` | S1 — R2 golden hits |
| `test_query_gate.py` | S2 — G1/G2/G3, 34 accept/reject cases plus act detection |
| `test_api_contracts.py` | S3 — A1/A2/A3, SSE framing, validation, `/debug/search` gate |
| `test_round2_followups.py` | Round-two ticket: pinned key sections, held-Acts line and footer, misspelt Act titles, everyday-wording topics |
| `NOTES-duplication.md` | Root-cause note for the ~10x corpus duplication |
| `fixtures/mini/` | 10-act deduplicated index, 25 MB (committed) |
| `scripts/build_fixture.py` | Builds a fixture from a full (embeddings, metadata) pair |
| `scripts/run_golden.py` | Prints the golden pass/fail table |

## Rebuilding the fixture

`fixtures/mini` holds 10,790 deduplicated rows across the 10 acts listed in
`scripts/mini_acts.txt` (25.2 MB total, so it is committed rather than
gitignored). It was cut from the working-tree expansion artifacts
(`data/embeddings`, 2,619,279 rows) because the `v1.0-data` release cache was
still downloading. To rebuild:

```bash
backend/venv/bin/python backend/tests/scripts/build_fixture.py \
  --embeddings data/embeddings/embeddings.npy \
  --metadata   data/embeddings/metadata.json \
  --out        backend/tests/fixtures/mini \
  --acts-file  backend/tests/scripts/mini_acts.txt
```

The metadata source is ~2 GB; the builder streams it rather than loading it, so
it runs in a few hundred MB of RAM. Swap `--embeddings`/`--metadata` for
`~/.cache/bowen-data/v1.0-data/` once that download completes, then re-record
the baseline (below).

## Golden pass/fail table

```bash
EMBEDDINGS_DIR=backend/tests/fixtures/mini BOWEN_STUB_LLM=1 \
  backend/venv/bin/python backend/tests/scripts/run_golden.py

# pre-dedupe behaviour, on a production-shaped (12x duplicated) index:
EMBEDDINGS_DIR=backend/tests/fixtures/mini BOWEN_STUB_LLM=1 \
  backend/venv/bin/python backend/tests/scripts/run_golden.py --duplicate 12 --multiplier 1
```

`--multiplier 1` disables the over-fetch, reproducing the selection the old
`argsort(similarities)[-top_k:]` performed.

## Updating the baseline

`golden/baseline.json` pins which entries currently pass. Entries in
`known_misses` are non-strict `xfail`, so a retrieval improvement reports XPASS
instead of failing the build. When retrieval improves (or the fixture changes),
re-record it and commit the new file — `test_golden_pass_rate_not_regressed`
will not let the count go backwards.
