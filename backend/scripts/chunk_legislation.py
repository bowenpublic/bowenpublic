#!/usr/bin/env python3
"""
chunk_legislation.py

Breaks parsed legislation JSON into smaller chunks suitable for RAG.

Run from the magna root directory:
    cd ~/Desktop/bowenpublic
    python backend/scripts/chunk_legislation.py
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    ENCODER = tiktoken.get_encoding("cl100k_base")
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    print("Note: tiktoken not installed. Using word count approximation.")


# Configuration - paths relative to magna root
INPUT_DIR = Path("data/processed/json")
OUTPUT_DIR = Path("data/processed/chunks")

# Chunking parameters
MAX_CHUNK_TOKENS = 512
OVERLAP_TOKENS = 50
MIN_CHUNK_TOKENS = 50


def count_tokens(text: str) -> int:
    """Count tokens in text."""
    if HAS_TIKTOKEN:
        return len(ENCODER.encode(text))
    else:
        return int(len(text.split()) * 1.3)


def generate_chunk_id(text: str, metadata: Dict) -> str:
    """Generate a unique ID for a chunk."""
    content = f"{metadata.get('act_short_name', '')}:{metadata.get('section_number', '')}:{text[:100]}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def split_text_into_chunks(text: str, max_tokens: int = MAX_CHUNK_TOKENS) -> List[str]:
    """Split text into chunks of approximately max_tokens."""
    if not text:
        return []
    
    if count_tokens(text) <= max_tokens:
        return [text]
    
    chunks = []
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    current_chunk = []
    current_tokens = 0
    
    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        
        if sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            words = sentence.split()
            word_chunk = []
            word_tokens = 0
            
            for word in words:
                wt = count_tokens(word + ' ')
                if word_tokens + wt > max_tokens:
                    if word_chunk:
                        chunks.append(' '.join(word_chunk))
                    word_chunk = [word]
                    word_tokens = wt
                else:
                    word_chunk.append(word)
                    word_tokens += wt
            
            if word_chunk:
                current_chunk = word_chunk
                current_tokens = word_tokens
            continue
        
        if current_tokens + sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
    
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        if count_tokens(chunk_text) >= MIN_CHUNK_TOKENS or not chunks:
            chunks.append(chunk_text)
        elif chunks:
            chunks[-1] = chunks[-1] + ' ' + chunk_text
    
    return chunks


def chunk_section(section: Dict[str, Any], act_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a section into one or more chunks with metadata."""
    chunks = []
    
    section_text = section.get("text", "")
    section_heading = section.get("heading", "")
    section_number = section.get("section_number", "")
    
    full_text = f"{section_heading}\n\n{section_text}" if section_heading else section_text
    
    if not full_text.strip():
        return chunks
    
    text_chunks = split_text_into_chunks(full_text)
    
    for i, chunk_text in enumerate(text_chunks):
        chunk_metadata = {
            "act_title": act_metadata.get("title", ""),
            "act_short_name": act_metadata.get("short_name", ""),
            "act_year": act_metadata.get("year", 0),
            "act_url": act_metadata.get("url", ""),
            "act_as_at": act_metadata.get("as_at", ""),
            "topics": act_metadata.get("topics", []),
            "section_number": section_number,
            "section_heading": section_heading,
            "section_level": section.get("level", "section"),
            "section_part": section.get("part", ""),
            "section_url": section.get("url", ""),
            "chunk_index": i,
            "total_chunks": len(text_chunks),
            "token_count": count_tokens(chunk_text)
        }
        
        chunk_id = generate_chunk_id(chunk_text, chunk_metadata)
        
        chunks.append({
            "id": chunk_id,
            "text": chunk_text,
            "metadata": chunk_metadata
        })
    
    return chunks


def process_act(json_path: Path) -> List[Dict[str, Any]]:
    """Process a single act JSON file into chunks."""
    print(f"  Processing: {json_path.name}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        act_data = json.load(f)
    
    act_metadata = act_data.get("metadata", {})
    sections = act_data.get("sections", [])
    
    all_chunks = []
    
    for section in sections:
        section_chunks = chunk_section(section, act_metadata)
        all_chunks.extend(section_chunks)
    
    print(f"    Generated {len(all_chunks)} chunks from {len(sections)} sections")
    
    return all_chunks


def main():
    """Main entry point."""
    print("=" * 60)
    print("NZ Legislation Chunker")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    json_files = [f for f in INPUT_DIR.glob("*.json") if f.name != "acts_index.json"]
    
    if not json_files:
        print(f"\nNo JSON files found in {INPUT_DIR.absolute()}")
        print("Please run parse_legislation.py first.")
        return
    
    print(f"\nFound {len(json_files)} act files to process:\n")
    
    all_chunks = []
    chunks_by_act = {}
    
    for json_path in sorted(json_files):
        act_chunks = process_act(json_path)
        all_chunks.extend(act_chunks)
        
        act_name = json_path.stem
        chunks_by_act[act_name] = len(act_chunks)
        
        act_output_path = OUTPUT_DIR / f"{act_name}_chunks.json"
        with open(act_output_path, 'w', encoding='utf-8') as f:
            json.dump(act_chunks, f, ensure_ascii=False)
    
    # Save combined chunks
    combined_path = OUTPUT_DIR / "all_chunks.json"
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False)
    
    # Save index
    index_data = {
        "generated_at": datetime.now().isoformat(),
        "total_chunks": len(all_chunks),
        "chunk_config": {
            "max_tokens": MAX_CHUNK_TOKENS,
            "overlap_tokens": OVERLAP_TOKENS,
            "min_tokens": MIN_CHUNK_TOKENS
        },
        "acts": chunks_by_act
    }
    
    index_path = OUTPUT_DIR / "chunks_index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2)
    
    total_tokens = sum(c["metadata"]["token_count"] for c in all_chunks)
    
    print("\n" + "=" * 60)
    print("CHUNKING COMPLETE!")
    print("=" * 60)
    print(f"Total chunks: {len(all_chunks):,}")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Avg tokens/chunk: {total_tokens // len(all_chunks) if all_chunks else 0}")
    print(f"\nOutput: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()