#!/usr/bin/env python3
"""
main.py

FastAPI backend for Bowen - NZ Legal Assistant
Uses numpy-based vector search and Claude API.

Run from magna root:
    cd ~/Desktop/bowenpublic
    uvicorn backend.app.main:app --reload --port 8000
"""

import sys
import os
import json
import uuid
import time

print("[BOOT] Starting module imports...", flush=True)

import numpy as np

from .key_sections import get_key_sections_for_query, should_boost_section
from pathlib import Path
from typing import List, Optional
from datetime import datetime

print("[BOOT] Core imports OK", flush=True)

from fastapi import FastAPI, HTTPException, APIRouter, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

print("[BOOT] FastAPI imports OK", flush=True)


# Load environment variables
load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")  # For accessing logs
LOGS_DIR = Path(os.getenv("LOGS_DIR", "logs"))  # Use env var for Railway volume
EMBEDDINGS_DIR = Path(os.getenv("EMBEDDINGS_DIR", "data/embeddings"))
REFERENCES_DIR = Path("data/references")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 5
MIN_SIMILARITY = 0.25  # Floor: discard results below this cosine similarity
MAX_BOOST = 2.5        # Cap: prevent multiplicative boost inflation
MAX_HISTORY = 10       # Max conversation turns (user+assistant pairs) to keep
CANDIDATE_MULTIPLIER = 12  # Over-fetch factor before result-level dedupe

# Offline test/swarm switch: when set, no Anthropic call is ever made.
STUB_LLM = os.getenv("BOWEN_STUB_LLM", "").strip().lower() in ("1", "true", "yes", "on")
STUB_RESPONSE = "[stub] This is a stubbed Bowen response generated without calling the Anthropic API."

# In-memory conversation history keyed by session_id
conversation_history: dict[str, list[dict]] = {}

# Attachment constants
ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"
}
MAX_ATTACHMENTS = 3


# Pydantic models
class Attachment(BaseModel):
    filename: str = Field(..., max_length=255)
    content_type: str
    data: str = Field(..., description="Base64-encoded file content")

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"Unsupported content type: {v}. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}")
        return v


class ChatRequest(BaseModel):
    message: str = Field("", max_length=5000, description="User message")
    session_id: Optional[str] = Field(None, max_length=100, description="Session ID for conversation tracking")
    attachments: Optional[List[Attachment]] = Field(None, description="File attachments (max 3)")

    @field_validator("attachments")
    @classmethod
    def validate_attachments_count(cls, v):
        if v is not None and len(v) > MAX_ATTACHMENTS:
            raise ValueError(f"Maximum {MAX_ATTACHMENTS} attachments allowed")
        return v

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v, info):
        # Allow empty message if attachments are present (validated after all fields parsed)
        return v

class Source(BaseModel):
    act_title: str
    section_number: str
    section_heading: str
    url: str
    excerpt: str
    score: float

class ChatResponse(BaseModel):
    response: str
    sources: List[Source]
    disclaimer: str

# API Version
API_VERSION = "1.0.6"

# Initialize FastAPI
app = FastAPI(
    title="Bowen - NZ Legal Assistant",
    description="Chatbot legal information retrieval for New Zealand legislation",
    version=API_VERSION
)

# API v1 Router
api_v1 = APIRouter(prefix="/api/v1", tags=["v1"])

# CORS - Configure allowed origins from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
DEFAULT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3005", "http://127.0.0.1:3005"]
CORS_ORIGINS = ALLOWED_ORIGINS if ALLOWED_ORIGINS else DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

class _StubAnthropicClient:
    """Sentinel stand-in for the Anthropic client when BOWEN_STUB_LLM is set.

    It has no network methods at all, so any accidental attempt to make a real
    completion raises AttributeError rather than reaching api.anthropic.com.
    """
    def __repr__(self):
        return "<StubAnthropicClient>"


STUB_CLIENT = _StubAnthropicClient()

# Global state
embeddings = None
metadata = None
embedding_model = None
anthropic_client = None
references = []  # Curated scholarly references

# Import act detection from registry (single source of truth)
print("[BOOT] Importing acts_registry...", flush=True)
from .acts_registry import detect_act_from_query, get_all_acts, has_registry_signal, ACTS_REGISTRY
print(f"[BOOT] Acts registry OK ({len(ACTS_REGISTRY)} acts)", flush=True)

# System prompt
SYSTEM_PROMPT = f"""You are Bowen, a chatbot legal information assistant for New Zealand legislation.

## IDENTITY
You ARE Bowen. Always refer to yourself in the first person — "I", "me", "my". Never say "Bowen is..." or "Bowen has..." — say "I am...", "I have...". When someone asks "What's Bowen about?", respond with "I'm a legal information assistant..." not "Bowen is a legal information assistant...".

## YOUR KNOWLEDGE
You have general knowledge about NZ law from your training, including:
- The purpose and scope of major NZ Acts
- How NZ legal system works
- Common legal concepts and terminology

## TE TIRITI O WAITANGI / TREATY OF WAITANGI
The Treaty is foundational to NZ law and requires particular care in your responses.

### Constitutional Status
The Treaty is not formally part of NZ's constitution, but has been described as a "constitutional document" by the courts. Its legal effect depends on incorporation into statute - it has no direct legal force unless Parliament gives it effect through legislation. However, its principles increasingly permeate NZ law.

### The Two Texts
There are material differences between the Māori and English texts:
- Article 1: Māori text cedes "kāwanatanga" (governance), English cedes "sovereignty"
- Article 2: Māori guarantees "tino rangatiratanga" (full chieftainship) over taonga; English guarantees "exclusive and undisturbed possession" of lands, estates, forests, fisheries
- Article 2 also established Crown pre-emption (exclusive right to purchase Māori land)
- Article 3: Both texts grant Māori the rights of British subjects

### Treaty Principles (from case law)
Key principles developed through litigation include:
- **Partnership**: The Crown and Māori are partners, requiring good faith and reasonable cooperation
- **Active Protection**: The Crown must actively protect Māori interests, not merely avoid harming them
- **Redress**: Where the Crown has breached Treaty obligations, it should provide redress
- **Informed Decision-making**: Māori should have sufficient information to make decisions about their taonga

### Key Cases
- **R v Symonds (1847)**: Recognised native title; Crown's exclusive pre-emption right
- **Wi Parata v Bishop of Wellington (1877)**: Described Treaty as "a simple nullity" - this was the dominant view for over a century but is now discredited
- **NZ Maori Council v Attorney-General [1987] (Lands Case)**: Pivotal case establishing Treaty principles; Court of Appeal held the Crown must act in good faith and make informed decisions
- **Te Runanga o Muriwhenua v Attorney-General [1990]**: Fisheries and Treaty rights
- **Ngati Apa v Attorney-General [2003]**: Recognised Māori customary title to foreshore and seabed may not have been extinguished

### Treaty Clauses in Modern Legislation
Many NZ Acts now contain Treaty clauses requiring decision-makers to consider Treaty principles:
- RMA 1991, s8: "shall take into account the principles of the Treaty"
- Conservation Act 1987, s4: "shall give effect to the principles of the Treaty"
- Education and Training Act 2020, s9: Treaty obligations
- Local Government Act 2002, s4: Treaty principles in local governance

### The Waitangi Tribunal
Established by the Treaty of Waitangi Act 1975, the Tribunal:
- Investigates Crown breaches of Treaty principles
- Makes recommendations (generally not binding)
- Can investigate historical claims back to 1840
- Has produced significant reports on Treaty settlements

### Responding to Treaty Questions
When users ask about Treaty matters:
1. Acknowledge the complexity and ongoing nature of Treaty jurisprudence
2. Note the difference between Māori and English texts where relevant
3. Distinguish between historical positions (like Wi Parata) and modern law
4. Reference specific Treaty clauses in relevant Acts
5. Be respectful of the significance of these issues to Māori and to NZ's constitutional development

## YOUR ROLE
1. Use your general knowledge to EXPLAIN and provide context about NZ legislation
2. Use the PROVIDED EXCERPTS to cite SPECIFIC sections and current wording
3. Combine both to give comprehensive, accurate answers

## CRITICAL RULES
1. You provide INFORMATION only, NOT legal advice
2. When citing specific provisions, use the exact wording from the excerpts
3. If excerpts don't contain relevant detail, use your general knowledge but note "Based on my general knowledge..." vs "According to Section X..."
4. Always distinguish between:
   - What you know generally about the law
   - What is specifically cited from the excerpts provided
5. For "What is [Act]?" questions, explain the Act's purpose and scope from general knowledge, then cite any relevant sections from excerpts
6. IMPORTANT: The user's question may contain quoted legal text they want explained. This is NOT an excerpt from the database - it's text the user is asking about. Only treat content under "LEGISLATION EXCERPTS FROM DATABASE:" as official excerpts. If the user pastes text and asks about it, help them understand it using the database excerpts and your knowledge.
7. In some of the User testing Bowen took on a legal personality, which was good, but remember that Bowen is also his own personality, with his data bank and precision on access to legal documentation. Bowen has passion and humour but never provides advice only information. Bowen believes that information transmission is one of the essences of the universe. And that perhaps Law is like a semantic engine that constantly translates between different levels of abstraction - from broad principles to specific rules to particular applications. The real tension is temporal and contextual: how do we write rules today that will make sense when applied to unforeseen situations tomorrow?
8. If you establish that a user is real and interested in the work you're doing (not trolling), then you may become more conversational and chat about other matters based on your general knowledge. 

## RESPONSE STYLE
BREVITY IS PARAMOUNT. If you can say it in 2 sentences, don't use 4. Prefer clear prose over bullet lists — use bullets only when genuinely listing items, not as a default structure.

For general questions ("What is the RMA?"): 1-2 sentence explanation, cite the single most relevant section, done.
For specific questions ("What is the bond limit?"): Answer directly with the provision. No preamble.

Do NOT exhaustively list every related section. Cite what matters most. The user can always ask for more.

## AVAILABLE ACTS
You have FULL-TEXT coverage of {len(ACTS_REGISTRY)} NZ Acts (retrieved March to May 2026), sourced directly from legislation.govt.nz. This is comprehensive — not "bits and pieces" or selective excerpts. For example, the Resource Management Act 1991 alone has over 1,300 provisions in your database. When users ask what you have access to, be confident: you hold the complete published text of every Act in your registry. Do NOT guess or understate your coverage.

## CITATION FORMAT
When citing from excerpts: "Under Section X of the [Act Name]..."
When using general knowledge: "The [Act] generally provides for..." or "Based on my understanding of NZ law..."

## UPLOADED DOCUMENTS & IMAGES
Users may upload PDFs or images (e.g., tenancy agreements, court notices, contracts, legal correspondence).
When document text or images are provided:
1. Analyse the document content carefully
2. Cross-reference with relevant NZ legislation from the excerpts
3. For images, describe what you see and relate it to relevant legal context
4. Identify key clauses, dates, obligations, and rights mentioned
5. Maintain "information only, not legal advice" stance — do NOT tell users what to do, just explain what the law says
6. If the document appears to contain personal information, handle it respectfully and focus on the legal aspects

## SIGN-OFF
On the FIRST response in a conversation, end with: "As always, verify at legislation.govt.nz and consult a lawyer for your specific situation."
On subsequent responses, keep it short: "As always — verify and get advice for your situation." or omit entirely if the flow is conversational."""

DISCLAIMER = """⚠️ Bowen is a chatbot, not legal advice. It may be incomplete or outdated. For legal decisions, consult a qualified NZ lawyer or Community Law Centre."""


from .logger import logger, LogEvent
from .errors import (
    raise_empty_message,
    raise_invalid_query,
    raise_embeddings_not_loaded,
    raise_model_not_loaded,
    raise_anthropic_unavailable,
    raise_generation_failed,
    ErrorCode,
    InternalError
)


async def _load_embedding_model():
    """Load embedding model in background after startup."""
    global embedding_model
    import asyncio
    await asyncio.sleep(0)  # Yield to let startup finish
    try:
        from sentence_transformers import SentenceTransformer
        print(f"[BG] Loading embedding model: {EMBEDDING_MODEL}...", flush=True)
        embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        print("[BG] ✓ Embedding model loaded", flush=True)
    except Exception as e:
        print(f"[BG] ✗ Could not load embedding model: {e}", flush=True)


@app.on_event("startup")
async def startup():
    """Load models and data on startup."""
    global embeddings, metadata, embedding_model, anthropic_client, references

    print("\n" + "=" * 50, flush=True)
    print("Starting Bowen Backend...", flush=True)
    print("=" * 50, flush=True)

    # Validate required environment variables
    missing_vars = []
    if not ANTHROPIC_API_KEY and not STUB_LLM:
        missing_vars.append("ANTHROPIC_API_KEY")

    if missing_vars:
        print(f"\n✗ CRITICAL: Missing required environment variables: {', '.join(missing_vars)}")
        print("  Set these in your .env file or environment before starting the server.")
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Log CORS configuration
    print(f"\n✓ CORS origins: {CORS_ORIGINS}")
    print(f"✓ ADMIN_TOKEN loaded: {'yes' if ADMIN_TOKEN else 'NO (empty)'} (length={len(ADMIN_TOKEN)})")
    
    # Load embeddings
    embeddings_path = EMBEDDINGS_DIR / "embeddings.npy"
    metadata_path = EMBEDDINGS_DIR / "metadata.json"
    
    if embeddings_path.exists() and metadata_path.exists():
        import gc

        print(f"\nLoading embeddings from {embeddings_path}...")
        embeddings = np.load(embeddings_path, mmap_mode='r')
        print(f"✓ Memory-mapped embeddings: {embeddings.shape} ({embeddings.dtype})", flush=True)

        print(f"Loading metadata from {metadata_path}...", flush=True)
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        gc.collect()  # Free JSON parse buffers before loading model

        print(f"✓ Loaded {len(metadata):,} chunks", flush=True)
    else:
        print(f"✗ Embeddings not found at {EMBEDDINGS_DIR}")
        print("  Run generate_embeddings.py first")

    # Load embedding model in background so healthcheck passes immediately
    import asyncio
    asyncio.get_event_loop().create_task(_load_embedding_model())
    
    # Initialize Anthropic client
    if STUB_LLM:
        anthropic_client = STUB_CLIENT
        print("✓ BOWEN_STUB_LLM=1 — using stub LLM, no Anthropic calls will be made", flush=True)
    elif ANTHROPIC_API_KEY:
        try:
            import anthropic
            anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            print("✓ Anthropic client initialized", flush=True)
        except Exception as e:
            print(f"✗ Could not initialize Anthropic: {e}", flush=True)
    else:
        print("✗ ANTHROPIC_API_KEY not set in .env", flush=True)

    # Initialize logs directory
    LOGS_DIR.mkdir(exist_ok=True)
    print("✓ Logs directory ready", flush=True)

    # Load curated references
    if REFERENCES_DIR.exists():
        for ref_file in REFERENCES_DIR.glob("*.json"):
            try:
                with open(ref_file, 'r') as f:
                    ref_data = json.load(f)
                    references.append(ref_data)
                    print(f"✓ Loaded reference: {ref_data.get('title', ref_file.name)}")
            except Exception as e:
                print(f"✗ Could not load reference {ref_file.name}: {e}")
        print(f"✓ Loaded {len(references)} curated references")
    else:
        print("  No references directory found (optional)")

    print("\n" + "=" * 50)
    print("Startup complete!")
    print("=" * 50 + "\n")


def search_similar(query: str, top_k: int = TOP_K, act_filter: str = None) -> List[dict]:
    """
    Search for similar chunks with:
    - Optional act filtering
    - Keyword boosting for overview questions
    - KEY SECTION boosting for common topics
    """
    if embeddings is None or embedding_model is None:
        return []

    # Encode query
    query_embedding = embedding_model.encode(query, convert_to_numpy=True)

    # Calculate cosine similarities
    similarities = np.dot(embeddings, query_embedding).copy()

    query_lower = query.lower()

    # Get key sections for this query
    key_sections = get_key_sections_for_query(query)

    # Keyword boosting for "what is" questions
    boost_terms = ['purpose', 'interpretation', 'application', 'object', 'principle', 'definition']
    is_overview_question = any(q in query_lower for q in ['what is', 'what are', 'explain', 'overview', 'purpose of'])

    for i, meta in enumerate(metadata):
        raw_score = similarities[i]

        # Skip chunks below minimum similarity (no point boosting junk)
        if raw_score < MIN_SIMILARITY:
            continue

        text_lower = meta.get('text', '').lower()
        heading_lower = meta.get('section_heading', '').lower()
        section_num = meta.get('section_number', '').strip()

        # Track total boost to cap it
        total_boost = 1.0

        # Apply key section boosting
        section_boost = should_boost_section(meta, key_sections)
        if section_boost > 1.0:
            total_boost *= section_boost

        # Boost purpose/interpretation sections for overview questions
        if is_overview_question:
            for term in boost_terms:
                if term in heading_lower or term in text_lower[:200]:
                    total_boost *= 1.3
                    break  # Only one term boost per chunk

            # Boost early sections (usually purpose/interpretation)
            if section_num.isdigit() and int(section_num) <= 10:
                total_boost *= 1.2

        # Boost chunks with actual section numbers
        if section_num and section_num.replace('.', '').isdigit():
            total_boost *= 1.1

        # Boost chunks where section heading matches query terms
        query_terms = [t for t in query_lower.split() if len(t) > 3]
        for term in query_terms:
            if term in heading_lower:
                total_boost *= 1.4
                break  # Only boost once per chunk

        # Cap total boost to prevent weak matches from inflating
        total_boost = min(total_boost, MAX_BOOST)
        similarities[i] = raw_score * total_boost

    # Apply act filter if specified
    if act_filter:
        act_filter_lower = act_filter.lower()
        for i, meta in enumerate(metadata):
            act_title = meta.get('act_title', '').lower()
            act_short = meta.get('act_short_name', '').lower()
            if act_filter_lower not in act_title and act_filter_lower not in act_short:
                similarities[i] = -1  # Exclude non-matching acts

    # Over-fetch candidates so that duplicate rows in the corpus (the same
    # (act, section, text) embedded many times) cannot crowd out distinct
    # sections. See backend/tests/NOTES-duplication.md.
    n_candidates = min(len(similarities), max(top_k * CANDIDATE_MULTIPLIER, top_k))

    if n_candidates >= len(similarities):
        candidate_indices = np.argsort(similarities)[::-1]
    else:
        part = np.argpartition(similarities, -n_candidates)[-n_candidates:]
        candidate_indices = part[np.argsort(similarities[part])[::-1]]

    # Filter out low-relevance and excluded results
    candidate_indices = [i for i in candidate_indices if similarities[i] >= MIN_SIMILARITY]

    # Result-level dedupe: keep the highest-scoring row for each distinct
    # (act_title, section_number, text). Ordering is preserved (descending
    # score), and the act filter has already excluded non-matching rows.
    top_indices = []
    seen_keys = set()
    for idx in candidate_indices:
        meta = metadata[idx]
        key = (meta.get("act_title", ""), meta.get("section_number", ""), meta.get("text", ""))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        top_indices.append(idx)
        if len(top_indices) >= top_k:
            break

    results = []
    for idx in top_indices:
        meta = metadata[idx]
        results.append({
            "text": meta.get("text", ""),
            "act_title": meta.get("act_title", ""),
            "act_short_name": meta.get("act_short_name", ""),
            "section_number": meta.get("section_number", ""),
            "section_heading": meta.get("section_heading", ""),
            "section_url": meta.get("section_url", ""),
            "act_url": meta.get("act_url", ""),
            "score": float(similarities[idx])
        })

    return results


def build_context(results: List[dict]) -> str:
    """Build context string with better organization."""
    if not results:
        return "No specific legislation excerpts found for this query. Please use your general knowledge about NZ law."

    # Group by Act
    by_act = {}
    for r in results:
        act = r['act_title']
        if act not in by_act:
            by_act[act] = []
        by_act[act].append(r)

    parts = []
    for act_title, act_results in by_act.items():
        act_section = f"## {act_title}\n\n"
        for r in act_results:
            if r['section_number']:
                act_section += f"**Section {r['section_number']}"
                if r['section_heading']:
                    act_section += f" - {r['section_heading']}"
                act_section += f"**\n{r['text']}\n\n"
            else:
                act_section += f"{r['text']}\n\n"
        parts.append(act_section)

    return "\n---\n\n".join(parts)


def find_matching_references(query: str) -> List[dict]:
    """Find curated references that match the query based on keywords."""
    if not references:
        return []

    query_lower = query.lower()
    matches = []

    for ref in references:
        # Check if any keywords match
        keywords = ref.get('keywords', [])
        topics = ref.get('topics', [])
        all_terms = keywords + topics

        matched_terms = []
        for term in all_terms:
            if term.lower() in query_lower:
                matched_terms.append(term)

        # Also check for partial matches on important terms
        important_terms = ['treaty', 'waitangi', 'maori', 'land', 'possession', 'title', 'property']
        for term in important_terms:
            if term in query_lower and term not in [t.lower() for t in matched_terms]:
                # Check if reference covers this term
                if any(term in kw.lower() for kw in all_terms):
                    matched_terms.append(term)

        if matched_terms:
            matches.append({
                'reference': ref,
                'matched_terms': list(set(matched_terms)),
                'score': len(set(matched_terms))
            })

    # Sort by number of matched terms (relevance)
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches


def build_reference_context(matched_refs: List[dict]) -> str:
    """Build context string from matched references."""
    if not matched_refs:
        return ""

    parts = []
    for match in matched_refs[:2]:  # Limit to top 2 most relevant references
        ref = match['reference']
        parts.append(f"""## Curated Reference: {ref.get('title', 'Unknown')}
**Source:** Essay on Bowen's Te Tiriti page (bowenpublic.com/te-tiriti)
**Relevance:** Matched on: {', '.join(match['matched_terms'])}

**Summary:** {ref.get('summary', '')}

**Key Historical Context:**
{chr(10).join('- ' + str(e['year']) + ': ' + e['event'] for e in ref.get('historical_timeline', [])[:5])}

**Key Cases Discussed:**
{chr(10).join('- ' + c['name'] + ' ' + c['citation'] + ' - ' + c['relevance'] for c in ref.get('key_cases', [])[:4])}
""")

    return "\n---\n\n".join(parts)


def _build_claude_messages(
    query: str,
    context: str,
    reference_context: str = "",
    session_id: str = "",
    attachment_context: str = "",
    image_blocks: list | None = None,
) -> tuple[list, int]:
    """Build the messages array and max_tokens for a Claude API call."""
    # Build the reference section if we have matching references
    reference_section = ""
    if reference_context:
        reference_section = f"""
---

CURATED SCHOLARLY REFERENCES (use for historical context and case law background):
{reference_context}

---
"""

    # Build the attachment section if we have PDF text
    attachment_section = ""
    if attachment_context:
        attachment_section = f"""
---

UPLOADED DOCUMENT TEXT (the user has uploaded document(s) — analyse this content and cross-reference with legislation excerpts above):
{attachment_context}

---
"""

    # Build the current user message with context
    display_query = query if query else "Please analyse the uploaded document(s)."
    current_user_text = f"""USER'S QUESTION:
{display_query}

---

LEGISLATION EXCERPTS FROM DATABASE (these are the official excerpts you should cite):
{context}
{reference_section}{attachment_section}
Please answer the user's question using:
1. Your general knowledge about NZ law to provide context and explanation
2. The specific excerpts above to cite exact provisions and wording
3. The curated scholarly references (if provided) for historical context and case law
4. The uploaded document text (if provided) — analyse it and cross-reference with relevant legislation

Note: If the user's question contains quoted legal text, that is text THEY are asking about - not an official excerpt. Only cite from the "LEGISLATION EXCERPTS FROM DATABASE" section above.

If the excerpts don't contain the specific information needed, use your general knowledge but make clear what comes from the excerpts vs your training.

When using curated references, cite them as: "According to the essay on Bowen's Te Tiriti page..." or "As discussed in the essay 'From Possession to Ownership' on Bowen's Te Tiriti page..." Never attribute the essay to a named individual.

Remember: Provide information, not legal advice. Cite specific sections where possible."""

    # Increase max_tokens when attachments are present
    has_attachments = bool(attachment_context or image_blocks)
    max_tokens = 2500 if has_attachments else 1750

    # Build messages array with conversation history
    # When attachments are present, use fewer history turns to stay within token limits
    messages = []
    if session_id and session_id in conversation_history:
        history = conversation_history[session_id]
        if has_attachments and len(history) > 4:
            messages.extend(history[-4:])
        else:
            messages.extend(history)

    # Build the user message content — multimodal if images are present
    if image_blocks:
        user_content = []
        user_content.extend(image_blocks)
        user_content.append({"type": "text", "text": current_user_text})
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": current_user_text})

    return messages, max_tokens


async def generate_response(
    query: str,
    context: str,
    reference_context: str = "",
    session_id: str = "",
    attachment_context: str = "",
    image_blocks: list | None = None,
) -> str:
    """Generate response using Claude (non-streaming)."""
    if not anthropic_client:
        raise_anthropic_unavailable()

    messages, max_tokens = _build_claude_messages(
        query, context, reference_context, session_id,
        attachment_context, image_blocks,
    )

    if STUB_LLM:
        _store_history(session_id, query, STUB_RESPONSE)
        return STUB_RESPONSE

    try:
        message = anthropic_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        response_text = message.content[0].text

        _store_history(session_id, query, response_text)
        return response_text
    except Exception as e:
        logger.error(LogEvent.CLAUDE_ERROR, f"Claude API error: {e}", error=e)
        raise_generation_failed(str(e))


async def generate_response_stream(
    query: str,
    context: str,
    reference_context: str = "",
    session_id: str = "",
    attachment_context: str = "",
    image_blocks: list | None = None,
):
    """Streaming variant of generate_response. Yields text chunks as they arrive."""
    if not anthropic_client:
        raise_anthropic_unavailable()

    # Reuse the same message-building logic
    messages, max_tokens = _build_claude_messages(
        query, context, reference_context, session_id,
        attachment_context, image_blocks,
    )

    if STUB_LLM:
        for piece in STUB_RESPONSE.split(" "):
            yield piece + " "
        _store_history(session_id, query, STUB_RESPONSE)
        return

    try:
        full_text = []
        with anthropic_client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_text.append(text)
                yield text

        _store_history(session_id, query, "".join(full_text))
    except Exception as e:
        logger.error(LogEvent.CLAUDE_ERROR, f"Claude API error: {e}", error=e)
        raise


def _store_history(session_id: str, query: str, response_text: str):
    """Store conversation turn in history."""
    if session_id:
        if session_id not in conversation_history:
            conversation_history[session_id] = []
        history_content = query if query else "[User uploaded document(s) for analysis]"
        conversation_history[session_id].append({"role": "user", "content": history_content})
        conversation_history[session_id].append({"role": "assistant", "content": response_text})
        if len(conversation_history[session_id]) > MAX_HISTORY * 2:
            conversation_history[session_id] = conversation_history[session_id][-(MAX_HISTORY * 2):]


def log_query(
    session_id: str,
    ip: str,
    query: str,
    response: str,
    detected_act: str,
    sources_count: int,
    response_time_ms: int
):
    """Log query to JSON file."""
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "ip": ip,
            "query": query,
            "response": response,
            "detected_act": detected_act,
            "sources_count": sources_count,
            "response_time_ms": response_time_ms
        }

        log_file = LOGS_DIR / "queries.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(LogEvent.ANALYTICS_FAILURE, f"Failed to log query: {e}", error=e)


@app.get("/")
async def root():
    return {
        "name": "Bowen - NZ Legal Assistant",
        "version": "0.2.0",
        "status": "running",
        "chunks_loaded": len(metadata) if metadata else 0
    }


@app.get("/health")
async def health():
    failure_counts = logger.get_failure_counts()
    return {
        "status": "healthy",
        "embeddings_loaded": embeddings is not None,
        "model_loaded": embedding_model is not None,
        "anthropic_ready": anthropic_client is not None,
        "chunks": len(metadata) if metadata else 0,
        "analytics_failures": failure_counts,
        "has_failures": len(failure_counts) > 0
    }


@app.get("/admin/logs")
async def get_logs(token: str = Query(..., description="Admin token")):
    """Download query logs. Requires ADMIN_TOKEN."""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    log_file = LOGS_DIR / "queries.jsonl"
    if not log_file.exists():
        return {"message": "No logs yet", "entries": []}

    entries = []
    with open(log_file, "r") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    return {
        "total": len(entries),
        "entries": entries
    }


@app.get("/admin/stats")
async def get_stats(token: str = Query(..., description="Admin token")):
    """Get quick stats. Requires ADMIN_TOKEN."""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    log_file = LOGS_DIR / "queries.jsonl"
    if not log_file.exists():
        return {"total_queries": 0, "top_acts": {}}

    entries = []
    with open(log_file, "r") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    # Count by act
    act_counts = {}
    for e in entries:
        act = e.get("detected_act") or "Unknown"
        act_counts[act] = act_counts.get(act, 0) + 1

    # Sort by count
    top_acts = dict(sorted(act_counts.items(), key=lambda x: x[1], reverse=True)[:10])

    return {
        "total_queries": len(entries),
        "top_acts": top_acts
    }


import re

# Legal signal patterns — if any match, always retrieve
_LEGAL_SIGNALS = re.compile(
    r'(?i)'
    r'(?:\bsection\s+\d|'          # "section 5"
    r'\bs\s?\d|'                    # "s5" or "s 5"
    r'\bact\b|'                     # "act"
    r'\blaw\b|'                     # "law"
    r'\blegal\b|'                   # "legal"
    r'\blegislat|'                  # "legislation/legislative"
    r'\bstatut|'                    # "statute/statutory"
    r'\bconsent\b|'                 # "consent"
    r'\btribunal\b|'               # "tribunal"
    r'\bcourt\b|'                   # "court"
    r'\bliable|liability\b|'       # "liable/liability"
    r'\boffence\b|'                # "offence"
    r'\bpenalt|'                   # "penalty/penalties"
    r'\bbond\b|'                   # "bond"
    r'\btenant|tenancy\b|'         # "tenant/tenancy"
    r'\blandlord\b|'              # "landlord"
    r'\bresource\s+consent|'       # "resource consent"
    r'\bemployment\b|'             # "employment"
    r'\bwhat\s+is\b|'             # "what is" (likely asking about a concept)
    r'\bhow\s+does\b|'            # "how does"
    r'\bcan\s+(?:i|you|they)\b|'  # "can I/you/they"
    r'\bam\s+i\s+allowed\b|'      # "am I allowed"
    r'\brights?\b|'               # "right/rights"
    r'\bobligat|'                  # "obligation/obligations"
    r'\btreaty\b|'                 # "treaty"
    r'\btiriti\b|'                 # "tiriti"
    r'\bmāori\b|'                  # "māori"
    r'\bproperty\b|'              # "property"
    r'\bcontract\b|'              # "contract"
    r'\bcriminal\b|'              # "criminal"
    r'\bfine\b|'                   # "fine"
    r'\bnotice\b|'                 # "notice"

    # --- C-003 widening ------------------------------------------------------
    # Swarm run 3 rejected ordinary phrasings of real legal questions. Stems
    # rather than whole words where the stem is unambiguous, plus the everyday
    # vocabulary people actually use instead of legal terms.
    r'\blegal\w*|'                 # "legally" (\blegal\b missed it), "legalities"
    r'\bemploy\w*|'                # "employer/employee/employment/employed"
    r'\btenan\w*|'                 # "tenant/tenants/tenancy/tenancies"
    r'\bcomplain\w*|'              # "complain/complaint/complaining"
    r'\bbusiness\b|'
    r'\bgovernment\b|'
    r'\bparliament\b|'
    r'\bhouse\s+of\s+representatives\b|'
    r'\bcouncil\b|'
    r'\bagreement\b|'
    r'\brefund\b|'
    r'\bwarrant(?:y|ies)\b|'
    r'\bguarantee\w*|'
    r'\bdispute\w*|'
    r'\ballowed\b|'
    r'\brequired\b|'
    r'\bmust\b|'
    r'\bentitled\b|'
    r'\bcan\s+(?:my|a|an|the)\b|'  # "can my employer", "can a business"
    r'\bwho\s+can\b|'
    r'\bis\s+it\s+(?:legal|illegal|allowed)\b|'

    # Consumer grievances: people describe the problem, not the statute. These
    # are the phrasings the gate dropped in the C-002 report's examples.
    r'\bwhat\s+should\s+i\s+do\b|'
    r'\bwhat\s+can\s+i\s+do\b|'
    r'\bmoney\s+back\b|'           # everyday synonym for "refund"
    r'\b(?:builder|plumber|electrician|mechanic|tradesman|'
    r'retailer|trader|supplier)\b|'

    # Golden questions the gate would otherwise drop. Each is a term of art,
    # narrow enough not to fire on casual text.
    r'\bworkplace\b|'
    r'\bdut(?:y|ies)\b|'
    r'\breasonable\s+care\b|'
    r'\bfalse\s+(?:claim|advertis|represent)\w*)'
)


def _is_legal_query(query: str, detected_act: str | None, session_id: str = "") -> bool:
    """Lightweight check: should we search the legislation database?

    Errs on the side of inclusion — only skips clearly casual messages.
    """
    # If an act was detected, always search
    if detected_act:
        return True

    # An act filter needs strong, unambiguous evidence; deciding to *retrieve*
    # does not. Any registry keyword — including the ambiguous ones that can no
    # longer select an act on their own ("employer", "business", "charge") — is
    # enough of a legal signal to search. Without this the gate silently
    # tightens whenever detection does.
    if has_registry_signal(query):
        return True

    # If there's conversation history, check if any recent message was legal
    # Short vague follow-ups ("what about part 1?", "and section 6?") should retrieve
    # but purely casual messages ("haha thanks", "hey how are you") should not
    if session_id and session_id in conversation_history and conversation_history[session_id]:
        # Check last 3 user messages — if any had legal signals, this is likely a follow-up
        recent_user_msgs = [m['content'] for m in conversation_history[session_id] if m['role'] == 'user'][-3:]
        has_recent_legal = any(_LEGAL_SIGNALS.search(m) for m in recent_user_msgs)
        # Only treat as follow-up if query looks like a question or reference, not a greeting
        query_words = query.lower().split()
        followup_starts = ['what', 'which', 'tell', 'explain', 'and', 'also', 'part', 'section', 'how']
        is_followup_shaped = (len(query_words) > 0 and query_words[0] in followup_starts) or any(w in query.lower() for w in ['about', 'part ', 'section'])
        if has_recent_legal and is_followup_shaped:
            return True

    # If any legal signal word/pattern is present, search
    if _LEGAL_SIGNALS.search(query):
        return True

    # Short casual messages (greetings, dev notes) — skip
    # Longer messages are more likely to contain a real question
    if len(query.split()) <= 30:
        return False

    # Default: search (err on side of inclusion)
    return True


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Main chat endpoint with improved retrieval."""
    start_time = time.time()
    query = request.message.strip()

    has_attachments = bool(request.attachments)
    if not query and not has_attachments:
        raise_empty_message()

    # Check service availability
    if embeddings is None or metadata is None:
        raise_embeddings_not_loaded()

    if embedding_model is None:
        raise_model_not_loaded()

    if anthropic_client is None:
        raise_anthropic_unavailable()

    # Get or generate session ID
    session_id = request.session_id or str(uuid.uuid4())

    # Detect if asking about specific Act
    detected_act = detect_act_from_query(query)

    # Log incoming request
    logger.log_chat_request(session_id, len(query), detected_act)

    # Skip retrieval for clearly non-legal casual messages
    # Attachment-only messages (empty query) skip retrieval — Claude analyses the document directly
    is_legal_query = bool(query) and _is_legal_query(query, detected_act, session_id)

    if is_legal_query:
        # Search with optional act filter
        results = search_similar(
            query,
            top_k=6,  # Retrieve 6, display up to 3 after filtering
            act_filter=detected_act
        )

        # Build context
        context = build_context(results)

        # Find matching curated references
        matched_refs = find_matching_references(query)
        reference_context = build_reference_context(matched_refs)
    else:
        results = []
        context = "No legislation search performed — this appears to be a casual/non-legal message."
        reference_context = ""

    # Process attachments
    attachment_context = ""
    image_blocks = []
    if request.attachments:
        from .utils.attachments import validate_attachment, extract_pdf_text

        for att in request.attachments:
            try:
                raw_bytes, verified_type = validate_attachment(att.data, att.content_type)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Attachment '{att.filename}': {e}")

            if verified_type == "application/pdf":
                try:
                    pdf_text = extract_pdf_text(raw_bytes)
                    attachment_context += f"\n\n### {att.filename}\n{pdf_text}"
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=f"Attachment '{att.filename}': {e}")
            else:
                # Image — pass as base64 content block for Claude vision
                image_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": verified_type,
                        "data": att.data,
                    },
                })

    # Generate response
    response_text = await generate_response(
        query, context, reference_context, session_id,
        attachment_context=attachment_context.strip(),
        image_blocks=image_blocks if image_blocks else None,
    )

    # Format sources (deduplicate by act+section, or by text hash if no section)
    sources = []
    seen = set()
    for r in results:
        section_num = r['section_number'].strip() if r['section_number'] else ''

        if section_num:
            # Standard deduplication by act:section
            key = f"{r['act_title']}:{section_num}"
        else:
            # For chunks without section numbers, use text hash to avoid false duplicates
            text_hash = hash(r['text'][:100])
            key = f"{r['act_title']}:__no_section__{text_hash}"

        if key not in seen:
            seen.add(key)
            sources.append(Source(
                act_title=r['act_title'],
                section_number=section_num if section_num else 'General',
                section_heading=r['section_heading'] or 'General Provisions',
                url=r['section_url'] or r['act_url'],
                excerpt=r['text'][:200] + "..." if len(r['text']) > 200 else r['text'],
                score=r['score']
            ))

    # Calculate response time
    response_time_ms = int((time.time() - start_time) * 1000)

    # Log query to JSON file
    client_ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()  # Get first IP if multiple

    log_query(
        session_id=session_id,
        ip=client_ip,
        query=query,
        response=response_text,
        detected_act=detected_act,
        sources_count=len(sources),
        response_time_ms=response_time_ms
    )

    # Log response metrics
    logger.log_chat_response(session_id, response_time_ms, len(sources), success=True)

    return ChatResponse(
        response=response_text,
        sources=sources[:3],  # Limit to top 3 most relevant sources
        disclaimer=DISCLAIMER
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Streaming chat endpoint — returns SSE events."""
    start_time = time.time()
    query = request.message.strip()

    has_attachments = bool(request.attachments)
    if not query and not has_attachments:
        raise_empty_message()

    if embeddings is None or metadata is None:
        raise_embeddings_not_loaded()
    if embedding_model is None:
        raise_model_not_loaded()
    if anthropic_client is None:
        raise_anthropic_unavailable()

    session_id = request.session_id or str(uuid.uuid4())
    detected_act = detect_act_from_query(query)
    logger.log_chat_request(session_id, len(query), detected_act)

    is_legal_query = bool(query) and _is_legal_query(query, detected_act, session_id)

    if is_legal_query:
        results = search_similar(query, top_k=6, act_filter=detected_act)
        context = build_context(results)
        matched_refs = find_matching_references(query)
        reference_context = build_reference_context(matched_refs)
    else:
        results = []
        context = "No legislation search performed — this appears to be a casual/non-legal message."
        reference_context = ""

    # Process attachments
    attachment_context = ""
    image_blocks = []
    if request.attachments:
        from .utils.attachments import validate_attachment, extract_pdf_text

        for att in request.attachments:
            try:
                raw_bytes, verified_type = validate_attachment(att.data, att.content_type)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Attachment '{att.filename}': {e}")

            if verified_type == "application/pdf":
                try:
                    pdf_text = extract_pdf_text(raw_bytes)
                    attachment_context += f"\n\n### {att.filename}\n{pdf_text}"
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=f"Attachment '{att.filename}': {e}")
            else:
                image_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": verified_type,
                        "data": att.data,
                    },
                })

    # Build sources before streaming starts
    sources = []
    seen = set()
    for r in results:
        section_num = r['section_number'].strip() if r['section_number'] else ''
        if section_num:
            key = f"{r['act_title']}:{section_num}"
        else:
            text_hash = hash(r['text'][:100])
            key = f"{r['act_title']}:__no_section__{text_hash}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "act_title": r['act_title'],
                "section_number": section_num if section_num else 'General',
                "section_heading": r['section_heading'] or 'General Provisions',
                "url": r['section_url'] or r['act_url'],
                "excerpt": r['text'][:200] + "..." if len(r['text']) > 200 else r['text'],
                "score": r['score'],
            })
    sources = sources[:3]

    async def event_stream():
        full_text = []
        try:
            async for chunk in generate_response_stream(
                query, context, reference_context, session_id,
                attachment_context=attachment_context.strip(),
                image_blocks=image_blocks if image_blocks else None,
            ):
                full_text.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            # Send sources and disclaimer as final event
            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'disclaimer': DISCLAIMER})}\n\n"

            # Log after stream completes
            response_time_ms = int((time.time() - start_time) * 1000)
            response_text = "".join(full_text)
            client_ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown")
            if "," in client_ip:
                client_ip = client_ip.split(",")[0].strip()
            log_query(
                session_id=session_id, ip=client_ip, query=query,
                response=response_text, detected_act=detected_act,
                sources_count=len(sources), response_time_ms=response_time_ms,
            )
            logger.log_chat_response(session_id, response_time_ms, len(sources), success=True)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    conversation_history.pop(session_id, None)
    return {"status": "cleared"}


@app.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=1000, description="Search query"),
    limit: int = Query(default=10, ge=1, le=20, description="Maximum results to return")
):
    """Direct search endpoint."""
    if embeddings is None or embedding_model is None:
        raise_embeddings_not_loaded()

    results = search_similar(q, top_k=limit)
    
    return {
        "query": q,
        "results": [
            {
                "act_title": r["act_title"],
                "section_number": r["section_number"],
                "section_heading": r["section_heading"],
                "text": r["text"],
                "score": r["score"],
                "url": r["section_url"] or r["act_url"]
            }
            for r in results
        ]
    }


@app.get("/acts")
async def list_acts():
    """List all available acts from the registry (single source of truth)."""
    return {"acts": get_all_acts()}


# =============================================================================
# API v1 Routes (versioned endpoints)
# =============================================================================

@api_v1.get("/health")
async def v1_health():
    """Health check endpoint (v1)."""
    return await health()


@api_v1.post("/chat", response_model=ChatResponse)
async def v1_chat(request: ChatRequest, req: Request):
    """Chat endpoint (v1)."""
    return await chat(request, req)


@api_v1.post("/chat/stream")
async def v1_chat_stream(request: ChatRequest, req: Request):
    """Streaming chat endpoint (v1)."""
    return await chat_stream(request, req)


@api_v1.get("/search")
async def v1_search(
    q: str = Query(..., min_length=1, max_length=1000, description="Search query"),
    limit: int = Query(default=10, ge=1, le=20, description="Maximum results to return")
):
    """Search endpoint (v1)."""
    return await search(q, limit)


@api_v1.get("/acts")
async def v1_list_acts():
    """List acts endpoint (v1)."""
    return await list_acts()


@api_v1.delete("/session/{session_id}")
async def v1_clear_session(session_id: str):
    """Clear session endpoint (v1)."""
    return await clear_session(session_id)


@api_v1.get("/version")
async def v1_version():
    """Get API version information."""
    return {
        "api_version": API_VERSION,
        "app_version": "0.3.0",
        "endpoints": [
            "/api/v1/health",
            "/api/v1/chat",
            "/api/v1/search",
            "/api/v1/acts",
            "/api/v1/version"
        ]
    }


# Mount the v1 router
app.include_router(api_v1)


# =============================================================================
# Stripe Donation Endpoints
# =============================================================================

print("[BOOT] Importing stripe...", flush=True)
try:
    import stripe
    print("[BOOT] Stripe import OK", flush=True)
except Exception as e:
    print(f"[BOOT] Stripe import FAILED: {e}", flush=True)
    stripe = None

if stripe:
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")

class DonateRequest(BaseModel):
    amount: int = Field(..., ge=1, le=10000, description="Donation amount in NZD")

@app.post("/api/donate/checkout")
async def create_checkout_session(req: DonateRequest, request: Request):
    """Create a Stripe Checkout Session for a one-time donation."""
    origin = request.headers.get("origin", "http://localhost:3005")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            currency="nzd",
            line_items=[{
                "price_data": {
                    "currency": "nzd",
                    "unit_amount": req.amount * 100,
                    "product_data": {
                        "name": f"Bowen Public Donation — ${req.amount} NZD",
                    },
                },
                "quantity": 1,
            }],
            success_url=f"{origin}/donate?success=true",
            cancel_url=f"{origin}/donate",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        amount = session.get("amount_total", 0) / 100
        print(f"[DONATION] ${amount:.2f} NZD received — session {session['id']}")

    return {"status": "ok"}


# =============================================================================
# Debug endpoint to test retrieval without Claude
# =============================================================================

# Debug endpoints - only available in development
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"


@app.get("/debug/search")
async def debug_search(q: str, limit: int = Query(default=10, ge=1, le=50)):
    """
    Debug endpoint to see what sections are being retrieved.
    Shows key section boosting in action.
    Only available when DEBUG=true environment variable is set.
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")

    key_sections = get_key_sections_for_query(q)
    detected_act = detect_act_from_query(q)

    results = search_similar(q, top_k=limit, act_filter=detected_act)

    return {
        "query": q,
        "detected_act": detected_act,
        "key_sections_matched": key_sections,
        "results": [
            {
                "act": r["act_title"],
                "section": r["section_number"],
                "heading": r["section_heading"],
                "score": round(r["score"], 4),
                "text_preview": r["text"][:150] + "..."
            }
            for r in results
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)