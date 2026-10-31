#!/usr/bin/env python3
"""
run_golden.py

Runs the golden retrieval set and prints the pass/fail table. Use
`--multiplier 1` to reproduce the pre-dedupe behaviour of search_similar()
and `--multiplier 12` (the default in main.py) for the current behaviour.

    EMBEDDINGS_DIR=backend/tests/fixtures/mini BOWEN_STUB_LLM=1 \
      backend/venv/bin/python backend/tests/scripts/run_golden.py --multiplier 1
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend" / "tests"))

os.environ.setdefault("EMBEDDINGS_DIR", "backend/tests/fixtures/mini")
os.environ.setdefault("BOWEN_STUB_LLM", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--multiplier", type=int, default=None,
                    help="override CANDIDATE_MULTIPLIER (1 = pre-dedupe behaviour)")
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--duplicate", type=int, default=None,
                    help="tile the index N times to reproduce the deployed corpus's duplication")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    import numpy as np
    from sentence_transformers import SentenceTransformer
    from backend.app import main as app_main
    import golden_runner

    embeddings_dir = Path(os.environ["EMBEDDINGS_DIR"])
    if not embeddings_dir.is_absolute():
        embeddings_dir = REPO_ROOT / embeddings_dir

    app_main.embeddings = np.load(embeddings_dir / "embeddings.npy", mmap_mode="r")
    with open(embeddings_dir / "metadata.json", encoding="utf-8") as fh:
        app_main.metadata = json.load(fh)
    app_main.embeddings, app_main.metadata, _ = app_main.drop_repealed_rows(
        app_main.embeddings, app_main.metadata)
    app_main.embedding_model = SentenceTransformer(app_main.EMBEDDING_MODEL)
    app_main.anthropic_client = app_main.STUB_CLIENT

    golden_path = REPO_ROOT / "backend" / "tests" / "golden" / "retrieval.json"
    with open(golden_path, encoding="utf-8") as fh:
        golden = json.load(fh)

    label = ("CANDIDATE_MULTIPLIER=%s" % args.multiplier) if args.multiplier \
        else ("CANDIDATE_MULTIPLIER=%d (default)" % app_main.CANDIDATE_MULTIPLIER)
    if args.duplicate:
        label += ", index tiled x%d" % args.duplicate
    rows = golden_runner.evaluate_all(app_main, golden["entries"], top_k=args.top_k,
                                      multiplier=args.multiplier, duplicate=args.duplicate)
    print(golden_runner.format_table(rows, "Golden retrieval set — %s, top_k=%d" % (label, args.top_k)))

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print("\nwrote %s" % args.json_out)


if __name__ == "__main__":
    main()
