#!/usr/bin/env python3
"""
batch_ingest.py

Batch ingestion pipeline for expanding Bowen's legislation bank.
Downloads HTML from legislation.govt.nz, parses, chunks, and regenerates embeddings.

Usage:
    cd ~/Desktop/bowenpublic
    source backend/venv/bin/activate
    python backend/scripts/batch_ingest.py --batch 1
    python backend/scripts/batch_ingest.py --batch 1 --dry-run
    python backend/scripts/batch_ingest.py --list
"""

import os
import sys
import json
import time
import argparse
import re
from pathlib import Path
from datetime import datetime

# Ensure we can import from backend/scripts
MAGNA_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(MAGNA_ROOT)

MANIFEST_PATH = Path("data/expansion-manifest.json")
RAW_HTML_DIR = Path("data/raw/html")
PROCESSED_JSON_DIR = Path("data/processed/json")
PROCESSED_CHUNKS_DIR = Path("data/processed/chunks")
EMBEDDINGS_DIR = Path("data/embeddings")
ACTS_REGISTRY_PATH = Path("backend/app/acts_registry.py")
PARSE_SCRIPT_PATH = Path("backend/scripts/parse_legislation.py")

DOWNLOAD_DELAY = 2  # seconds between requests


def load_manifest():
    """Load the expansion manifest."""
    with open(MANIFEST_PATH, 'r') as f:
        return json.load(f)


def save_manifest(manifest):
    """Save the expansion manifest."""
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def build_url(year, number):
    """Build a legislation.govt.nz whole-act URL."""
    return f"https://www.legislation.govt.nz/act/public/{year}/{number:04d}/latest/whole.html"


def build_dlm_url(year, number):
    """Build DLM-style URL (landing page, used for acts_registry)."""
    return f"https://www.legislation.govt.nz/act/public/{year}/{number:04d}/latest/DLM1.html"


def download_html(act, dry_run=False):
    """Download an act's HTML from legislation.govt.nz."""
    import requests

    slug = act["slug"]
    html_path = RAW_HTML_DIR / f"{slug}.html"

    if html_path.exists():
        print(f"    [skip] {slug}.html already exists")
        return html_path

    url = build_url(act["year"], act["number"])

    if dry_run:
        print(f"    [dry-run] Would download {url} -> {html_path}")
        return None

    print(f"    Downloading {url}")
    try:
        resp = requests.get(url, timeout=60, headers={
            "User-Agent": "BowenPublic-LegislationIngester/1.0 (research; joe@bowenpublic.com)"
        })
        resp.raise_for_status()
        # The site sends UTF-8 without declaring it in the header, and requests
        # then falls back to Latin-1, which corrupts macrons and dashes.
        resp.encoding = "utf-8"

        # Check if we got a meaningful page (not a redirect to an error page)
        if len(resp.text) < 1000:
            print(f"    [warn] Response too small ({len(resp.text)} bytes) — may be an error page")
            return None

        # Check for repealed notice
        if "This Act has been repealed" in resp.text or "repealed" in resp.text[:2000].lower():
            print(f"    [skip] Act appears to be repealed — skipping (in-force only policy)")
            act["status"] = "skipped_repealed"
            return None

        # The URL is built from a year and number; if the number is wrong the
        # site returns a different Act. Check the page is the one asked for.
        sys.path.insert(0, str(MAGNA_ROOT / "backend" / "scripts"))
        from parse_legislation import extract_page_title, titles_match
        page_title = extract_page_title(resp.text)
        if not titles_match(act["title"], page_title):
            print(f"    [error] Expected {act['title']!r} but the page is {page_title!r}")
            act["status"] = "wrong_act"
            return None

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(resp.text)

        print(f"    [ok] Saved {html_path} ({len(resp.text):,} bytes)")
        return html_path

    except requests.RequestException as e:
        print(f"    [error] Download failed: {e}")
        act["status"] = "download_failed"
        return None


def register_in_parse_script(act):
    """Add the act to ACT_METADATA in parse_legislation.py."""
    slug = act["slug"]
    filename = f"{slug}.html"

    # Read current parse script
    content = PARSE_SCRIPT_PATH.read_text()

    # Check if already registered
    if filename in content:
        print(f"    [skip] {filename} already in parse_legislation.py")
        return

    url = build_url(act["year"], act["number"])
    topics_str = json.dumps(act.get("keywords", act.get("topics", [])))

    entry = f'''    "{filename}": {{
        "title": "{act['title']}",
        "year": {act['year']},
        "number": {act['number']},
        "url": "{url}",
        "short_name": "{act['code']}",
        "topics": {topics_str}
    }},
'''

    # Insert before the closing brace of ACT_METADATA
    # Find the last entry (before the closing })
    insert_marker = "\n}\n\n\ndef clean_text"
    if insert_marker in content:
        content = content.replace(insert_marker, f"\n{entry}}}\n\n\ndef clean_text")
    else:
        # Fallback: find the dict closing brace before clean_text
        pattern = r'(\n\}\n)(.*?def clean_text)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            content = content[:match.start()] + f"\n{entry}}}\n" + match.group(2) + content[match.end():]
        else:
            print(f"    [error] Could not find insertion point in parse_legislation.py")
            return

    PARSE_SCRIPT_PATH.write_text(content)
    print(f"    [ok] Added {act['code']} to parse_legislation.py")


def register_in_acts_registry(act):
    """Add the act to ACTS_REGISTRY in acts_registry.py."""
    content = ACTS_REGISTRY_PATH.read_text()

    # Check if already registered
    if f'"{act["code"]}"' in content:
        print(f"    [skip] {act['code']} already in acts_registry.py")
        return

    url = build_url(act["year"], act["number"]).replace("/whole.html", "/DLM1.html")
    keywords = json.dumps(act.get("keywords", []))
    topics = json.dumps(act.get("topics", []))

    entry = f'''    "{act['code']}": {{
        "title": "{act['title']}",
        "short_name": "{act['code']}",
        "year": {act['year']},
        "keywords": {keywords},
        "topics": {topics},
        "url": "{url}"
    }},
'''

    # Insert before the closing brace of ACTS_REGISTRY
    # Find the pattern: last entry followed by closing }
    # The registry ends with "}\n\n" before the next function/variable
    lines = content.split('\n')
    insert_idx = None
    brace_depth = 0
    in_registry = False

    for i, line in enumerate(lines):
        if 'ACTS_REGISTRY' in line and '{' in line:
            in_registry = True
            brace_depth = 1
            continue
        if in_registry:
            brace_depth += line.count('{') - line.count('}')
            if brace_depth == 0:
                insert_idx = i
                break

    if insert_idx is not None:
        # Insert the new entry just before the closing brace
        lines.insert(insert_idx, entry.rstrip())
        ACTS_REGISTRY_PATH.write_text('\n'.join(lines))
        print(f"    [ok] Added {act['code']} to acts_registry.py")
    else:
        print(f"    [error] Could not find insertion point in acts_registry.py")


def parse_single_act(slug):
    """Parse a single act's HTML into JSON using the existing parser logic."""
    # Import the parse script's functions
    sys.path.insert(0, str(MAGNA_ROOT / "backend" / "scripts"))
    import importlib
    parse_mod = importlib.import_module("parse_legislation")
    importlib.reload(parse_mod)  # Reload to pick up new ACT_METADATA entries

    html_path = RAW_HTML_DIR / f"{slug}.html"
    if not html_path.exists():
        print(f"    [error] HTML file not found: {html_path}")
        return None

    metadata = parse_mod.ACT_METADATA.get(f"{slug}.html", {
        "title": slug.replace("-", " ").title(),
        "year": 0,
        "number": 0,
        "url": "",
        "short_name": slug[:3].upper(),
        "topics": []
    })

    result = parse_mod.parse_legislation_html(html_path, metadata)

    output_path = PROCESSED_JSON_DIR / f"{slug}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"    [ok] Parsed {len(result['sections'])} sections -> {output_path.name}")
    return result


def chunk_single_act(slug):
    """Chunk a single act's JSON using the existing chunker logic."""
    sys.path.insert(0, str(MAGNA_ROOT / "backend" / "scripts"))
    import importlib
    chunk_mod = importlib.import_module("chunk_legislation")
    importlib.reload(chunk_mod)

    json_path = PROCESSED_JSON_DIR / f"{slug}.json"
    if not json_path.exists():
        print(f"    [error] JSON file not found: {json_path}")
        return None

    act_chunks = chunk_mod.process_act(json_path)

    # Save individual chunks file
    chunks_path = PROCESSED_CHUNKS_DIR / f"{slug}_chunks.json"
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(act_chunks, f, ensure_ascii=False)

    print(f"    [ok] Generated {len(act_chunks)} chunks -> {chunks_path.name}")
    return act_chunks


def rebuild_all_chunks():
    """Rebuild the combined all_chunks.json from individual chunk files."""
    print("\n  Rebuilding all_chunks.json...")
    # all_chunks.json is this function's own output and matches the glob;
    # reading it back in re-ingests the previous build (NOTES-duplication.md).
    chunk_files = sorted(f for f in PROCESSED_CHUNKS_DIR.glob("*_chunks.json")
                         if f.name != "all_chunks.json")

    all_chunks = []
    for cf in chunk_files:
        with open(cf, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
            all_chunks.extend(chunks)

    combined_path = PROCESSED_CHUNKS_DIR / "all_chunks.json"
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False)

    print(f"  [ok] Combined {len(all_chunks):,} chunks from {len(chunk_files)} acts")
    return len(all_chunks)


def regenerate_embeddings():
    """Regenerate embeddings for all chunks."""
    print("\n  Regenerating embeddings (this may take several minutes)...")
    sys.path.insert(0, str(MAGNA_ROOT / "backend" / "scripts"))
    import importlib
    embed_mod = importlib.import_module("generate_embeddings")
    importlib.reload(embed_mod)
    embed_mod.main()


def process_batch(batch_num, dry_run=False, skip_embeddings=False):
    """Process a single batch of acts."""
    manifest = load_manifest()

    # Find the batch
    batch = None
    for b in manifest["batches"]:
        if b["batch"] == batch_num:
            batch = b
            break

    if batch is None:
        print(f"Error: Batch {batch_num} not found in manifest")
        return

    print(f"\n{'=' * 60}")
    print(f"BATCH {batch_num}: {batch['name']}")
    print(f"{'=' * 60}")
    print(f"Acts: {len(batch['acts'])}")
    if dry_run:
        print("[DRY RUN MODE — no files will be created]\n")
    print()

    successful = 0
    failed = 0

    for act in batch["acts"]:
        if act["status"] == "complete":
            print(f"\n  [{act['code']}] Already complete — skipping")
            successful += 1
            continue

        print(f"\n  [{act['code']}] {act['title']}")
        print(f"  {'─' * 50}")

        # Step 1: Download HTML
        html_path = download_html(act, dry_run=dry_run)
        if html_path is None and not dry_run:
            failed += 1
            save_manifest(manifest)
            if act.get("status") != "skipped_repealed":
                time.sleep(DOWNLOAD_DELAY)
            continue

        if not dry_run:
            # Step 2: Register in both files
            register_in_parse_script(act)
            register_in_acts_registry(act)

            # Step 3: Parse HTML -> JSON
            result = parse_single_act(act["slug"])
            if result is None:
                failed += 1
                act["status"] = "parse_failed"
                save_manifest(manifest)
                time.sleep(DOWNLOAD_DELAY)
                continue

            # Step 4: Chunk JSON
            chunks = chunk_single_act(act["slug"])
            if chunks is None:
                failed += 1
                act["status"] = "chunk_failed"
                save_manifest(manifest)
                time.sleep(DOWNLOAD_DELAY)
                continue

            act["status"] = "complete"
            act["sections"] = len(result["sections"])
            act["chunks"] = len(chunks)
            act["completed_at"] = datetime.now().isoformat()
            successful += 1
            save_manifest(manifest)

        time.sleep(DOWNLOAD_DELAY)

    if not dry_run and successful > 0:
        # Rebuild combined chunks
        total_chunks = rebuild_all_chunks()

        # Regenerate embeddings (unless skipped)
        if not skip_embeddings:
            regenerate_embeddings()
        else:
            print("\n  [skip] Embedding generation skipped (--skip-embeddings)")

        # Update manifest
        batch["status"] = "complete" if failed == 0 else "partial"
        manifest["current"] = manifest.get("current", 89) + successful
        save_manifest(manifest)

    print(f"\n{'=' * 60}")
    print(f"BATCH {batch_num} {'DRY RUN ' if dry_run else ''}COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Successful: {successful}")
    print(f"  Failed:     {failed}")
    if not dry_run:
        print(f"  Total acts: {manifest.get('current', '?')}/{manifest['target']}")


def list_batches():
    """List all batches and their status."""
    manifest = load_manifest()

    print(f"\n{'=' * 60}")
    print(f"EXPANSION MANIFEST — {manifest.get('current', 89)}/{manifest['target']} acts")
    print(f"{'=' * 60}")

    for batch in manifest["batches"]:
        status_icon = {"pending": "○", "complete": "●", "partial": "◐"}.get(batch["status"], "?")
        complete = sum(1 for a in batch["acts"] if a["status"] == "complete")
        total = len(batch["acts"])
        print(f"\n  {status_icon} Batch {batch['batch']}: {batch['name']} [{complete}/{total}]")

        for act in batch["acts"]:
            act_icon = {"pending": "  ○", "complete": "  ●", "skipped_repealed": "  ⊘", "download_failed": "  ✗", "parse_failed": "  ✗", "chunk_failed": "  ✗"}.get(act["status"], "  ?")
            extra = ""
            if act.get("chunks"):
                extra = f" — {act['chunks']} chunks"
            print(f"    {act_icon} {act['code']}: {act['title']}{extra}")


def main():
    parser = argparse.ArgumentParser(description="Batch legislation ingestion pipeline")
    parser.add_argument("--batch", type=int, help="Batch number to process (1-11)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without downloading or modifying files")
    parser.add_argument("--list", action="store_true", help="List all batches and their status")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding regeneration (useful for processing multiple batches)")
    args = parser.parse_args()

    if args.list:
        list_batches()
    elif args.batch:
        process_batch(args.batch, dry_run=args.dry_run, skip_embeddings=args.skip_embeddings)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
