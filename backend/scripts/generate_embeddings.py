#!/usr/bin/env python3
"""
generate_embeddings.py

Generates vector embeddings for legislation chunks.
Uses simple JSON storage (no ChromaDB) for Python 3.14 compatibility.

Run from the magna root directory:
    cd ~/Desktop/bowenpublic
    python backend/scripts/generate_embeddings.py
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Configuration - paths relative to magna root
CHUNKS_DIR = Path("data/processed/chunks")
EMBEDDINGS_DIR = Path("data/embeddings")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast and good quality
BATCH_SIZE = 100


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def main():
    print("=" * 60)
    print("NZ Legislation Embedding Generator")
    print("=" * 60)
    
    # Check for required packages
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("\nError: sentence-transformers not installed")
        print("Run: pip install sentence-transformers")
        return
    
    # Load chunks
    chunks_path = CHUNKS_DIR / "all_chunks.json"
    if not chunks_path.exists():
        print(f"\nError: {chunks_path} not found")
        print("Please run chunk_legislation.py first.")
        return
    
    print(f"\nLoading chunks from {chunks_path}...")
    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks):,} chunks")

    # Drop exact duplicates so no pipeline bug can put them in the index.
    # Same key as the runtime dedupe in search_similar().
    chunks = list({
        (c.get("metadata", {}).get("act_title", ""),
         c.get("metadata", {}).get("section_number", ""),
         c.get("text", "")): c
        for c in chunks
    }.values())
    print(f"After dedupe: {len(chunks):,} chunks")

    # Initialize embedding model
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    print("(This may take a moment on first run...)")
    model = SentenceTransformer(EMBEDDING_MODEL)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"Model loaded. Dimension: {embedding_dim}")
    
    # Prepare texts for embedding
    print("\nPreparing texts...")
    texts = []
    for chunk in chunks:
        text = chunk.get("text", "")
        meta = chunk.get("metadata", {})
        
        # Add context for better retrieval
        prefix = f"{meta.get('act_title', '')} Section {meta.get('section_number', '')}: "
        texts.append(prefix + text)
    
    # Generate embeddings
    print(f"\nGenerating embeddings for {len(texts):,} chunks...")
    print("This will take a few minutes...\n")
    
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        batch_size=BATCH_SIZE,
        convert_to_numpy=True
    )
    print(f"\nGenerated {len(embeddings):,} embeddings")
    
    # Create output directory
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save embeddings as numpy array
    embeddings_path = EMBEDDINGS_DIR / "embeddings.npy"
    print(f"\nSaving embeddings to {embeddings_path}...")
    np.save(embeddings_path, embeddings)
    
    # Save chunk metadata
    metadata_path = EMBEDDINGS_DIR / "metadata.json"
    print(f"Saving metadata to {metadata_path}...")

    metadata_list = []
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        metadata_list.append({
            "id": chunk.get("id", str(i)),
            "text": chunk.get("text", ""),  # Full chunk: a cut-off would drop statute text
            "act_title": meta.get("act_title", ""),
            "act_short_name": meta.get("act_short_name", ""),
            "section_number": meta.get("section_number", ""),
            "section_heading": meta.get("section_heading", ""),
            "section_url": meta.get("section_url", ""),
            "act_url": meta.get("act_url", ""),
            "as_at": meta.get("act_as_at", "")
        })
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata_list, f, ensure_ascii=False)
    
    # Save config
    config = {
        "generated_at": datetime.now().isoformat(),
        "embedding_model": EMBEDDING_MODEL,
        "total_chunks": len(chunks),
        "embedding_dimension": embedding_dim,
        "embeddings_file": "embeddings.npy",
        "metadata_file": "metadata.json"
    }
    
    config_path = EMBEDDINGS_DIR / "config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Test retrieval
    print("\n" + "-" * 40)
    print("Testing retrieval...")
    test_query = "What is the maximum bond for a residential tenancy?"
    
    query_embedding = model.encode(test_query, convert_to_numpy=True)
    
    # Calculate similarities
    similarities = np.dot(embeddings, query_embedding)
    top_indices = np.argsort(similarities)[-3:][::-1]
    
    print(f"\nQuery: '{test_query}'")
    print("\nTop 3 results:")
    for i, idx in enumerate(top_indices):
        meta = metadata_list[idx]
        print(f"\n{i+1}. {meta['act_title']} - Section {meta['section_number']}")
        print(f"   Score: {similarities[idx]:.4f}")
        print(f"   {meta['text'][:150]}...")
    
    print("\n" + "=" * 60)
    print("EMBEDDING COMPLETE!")
    print("=" * 60)
    print(f"Total chunks: {len(chunks):,}")
    print(f"Embeddings saved to: {EMBEDDINGS_DIR.absolute()}")
    print(f"\nFiles created:")
    print(f"  - embeddings.npy ({embeddings.nbytes / 1024 / 1024:.1f} MB)")
    print(f"  - metadata.json")
    print(f"  - config.json")
    print(f"\nReady for RAG queries!")


if __name__ == "__main__":
    main()