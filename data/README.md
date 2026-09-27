# Data

## What is in git

- `raw/html/`: one page per Act, as downloaded from legislation.govt.nz. This is the
  source everything else is built from. Tracked with Git LFS.
- `references/`: curated reference material the backend loads at startup.
- `expansion-manifest.json`: the batches used by `backend/scripts/batch_ingest.py`.

## What is not in git

- `processed/`: parsed and chunked Acts.
- `embeddings/`: the search index the backend loads.

Both are built from `raw/html/` and are ignored. The index is published as a GitHub
release, which is where production gets it. The release in use is named in the
`Dockerfile` as `DATA_RELEASE`.

## Getting the index on a fresh clone

Download the release named in the `Dockerfile`:

```bash
gh release download v1.1-data --dir data/embeddings
```

Or build it from the raw HTML, which takes about ten minutes:

```bash
python backend/scripts/parse_legislation.py
python backend/scripts/chunk_legislation.py
python backend/scripts/generate_embeddings.py
```

Run these from the repo root. If the backend starts with no index, check that
`EMBEDDINGS_DIR` points at `data/embeddings`.

## Publishing a new index

1. Build it as above and run the tests.
2. Publish a new release with `embeddings.npy`, `metadata.json` and `config.json`.
3. Change `DATA_RELEASE` in the `Dockerfile`.
4. Update `DATABASE_STATS` in `frontend/src/components/chat.tsx`.
5. Push. The release must exist before the push, because Railway builds on push.
