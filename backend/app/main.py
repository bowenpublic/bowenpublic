#!/usr/bin/env python3
"""
main.py

FastAPI backend for Bowen - NZ Legal Assistant
Uses numpy-based vector search and Claude API.

Run from magna root:
    cd ~/Desktop/bowenpublic
    uvicorn backend.app.main:app --reload --port 8000
"""

import asyncio
import sys
import os
import re
import json
import uuid
import time

print("[BOOT] Starting module imports...", flush=True)

import numpy as np

from .key_sections import (get_key_sections_for_query, should_boost_section, is_pinned_section,
                           matches_combined_topic, pin_ignores_floor)
from pathlib import Path
from typing import List, Optional
from datetime import datetime

print("[BOOT] Core imports OK", flush=True)

from fastapi import FastAPI, HTTPException, APIRouter, Request, Query, Header
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
# Exact key sections for an everyday wording can sit far down the raw ranking
# (A12: SSA s130 at cosine 0.37, rank 276), out of reach of any capped boost, and
# can fall below MIN_SIMILARITY (A1: RTA s42B at 0.22). They are pinned into the
# results if their raw cosine clears this lower floor, which still keeps out a
# listed section that has nothing to do with the question.
PINNED_MIN_SIMILARITY = 0.15
MAX_PINNED = 3  # At most this many pinned sections displace ranked results
# Sections a question names by number ("sections 25 and 27 of the ... Act")
# are fetched by exact (act, section) and placed ahead of ranked results.
MAX_EXPLICIT_SECTIONS = 6
MAX_SECTION_RANGE = 6           # "ss 24 to 26" is expanded; a wider range is not
MAX_CHUNKS_PER_SECTION = 2      # Long sections (LCA s 6 has 19 chunks) keep their best two

# Claude request settings, shared by /chat and /chat/stream.
# BOWEN_CLAUDE_MODEL swaps the model without a code change (e.g. claude-sonnet-5-5).
CLAUDE_MODEL_ENV = "BOWEN_CLAUDE_MODEL"
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"


def resolve_claude_model(environ=os.environ) -> str:
    return (environ.get(CLAUDE_MODEL_ENV) or "").strip() or DEFAULT_CLAUDE_MODEL


CLAUDE_MODEL = resolve_claude_model()
# Thinking is always on for Opus 5.5 and effort sets how much it thinks. The
# API default is also medium; it is set here so a model change cannot move it.
CLAUDE_EFFORT = "medium"
# Thinking counts against max_tokens. This is room for it on top of the reply
# allowance (1750, or 2500 with attachments); it does not lengthen answers.
THINKING_TOKEN_HEADROOM = 8000
# On a safety-classifier decline the API re-runs the request on Anthropic's
# recommended fallback model. A model without fallbacks just runs alone.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CLAUDE_FALLBACKS = "default"

# fetch_section: on a legal question Claude may read a held section it was not
# shown (an excerpt depends on it, or the person named it) before answering.
MAX_TOOL_ROUNDS = 3          # rounds of fetching; the next request must answer
MAX_FETCHED_SECTIONS = 6     # fetch calls per answer, whatever they return
MAX_FETCH_CHARS = 16000      # text returned per section (LCA s 6 is ~23,500)
# In a round where Claude may still fetch, its text is held back until this
# many characters have arrived, so a sentence written before a fetch is never
# shown. Past it the round streams live and a later fetch is declined.
FETCH_COMMIT_CHARS = 300
FETCH_TOOL_NAME = "fetch_section"
FETCH_SECTION_TOOL = {
    "name": FETCH_TOOL_NAME,
    "description": (
        "Returns the text of one section of an Act Bowen holds, from the same database as "
        "the excerpts. Use it when an excerpt your answer relies on depends on a section you "
        "were not shown (it cites it, or uses a term defined there), or when the person asked "
        "about a section by number that is not in the excerpts. The text returned counts as "
        "an excerpt. If the Act is not held or has no such section, the result says so; then "
        "describe nothing about that section."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "act": {
                "type": "string",
                "description": "Full title of the Act, as in the excerpt headings or the list of "
                               "Acts you hold, e.g. \"Lawyers and Conveyancers Act 2006\".",
            },
            "section": {
                "type": "string",
                "description": "The section number only, without subsections, e.g. \"6\", "
                               "\"42B\", \"Schedule 1 cl 11\".",
            },
            "find": {
                "type": "string",
                "description": "Optional. The term or phrase you need, e.g. \"reserved areas of "
                               "work\". Used when the section is too long to return whole, such "
                               "as an interpretation section.",
            },
        },
        "required": ["act", "section"],
        "additionalProperties": False,
    },
}

# Shown, with no sources, when every model in the chain declines to answer.
# Draft for the founder to approve.
REFUSAL_MESSAGE = (
    "I can't help with this request. If you or someone else is in danger, call 111; "
    "to talk with a trained counsellor, call or text 1737 (free). You can read the current "
    "law at legislation.govt.nz, and Community Law (communitylaw.org.nz) offers free legal help."
)


class _Refused:
    """Returned or yielded by the generators in place of text when the model
    declined (stop_reason "refusal"); the endpoints answer with REFUSAL_MESSAGE."""
    def __repr__(self):
        return "<REFUSED>"


REFUSED = _Refused()

# Offline test/swarm switch: when set, no Anthropic call is ever made.
STUB_LLM = os.getenv("BOWEN_STUB_LLM", "").strip().lower() in ("1", "true", "yes", "on")
# Ends with the SOURCES line every real answer carries (see finalise_answer).
STUB_RESPONSE = (
    "[stub] This is a stubbed Bowen response generated without calling the Anthropic API.\n"
    "SOURCES: none"
)

# In-memory conversation history keyed by session_id
conversation_history: dict[str, list[dict]] = {}
# Act filter last used per session. Only a follow-up that names sections but
# no Act ("use sections 25(2) and 27") inherits it; see _act_in_play().
session_acts: dict[str, str] = {}

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
API_VERSION = "1.0.13"

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

def _stub_message(model: str, text: str, stop_reason: str = "end_turn", stop_details=None,
                  tool_calls=(), extra_blocks=()):
    """A BetaMessage shaped like Opus 5.5's: an empty thinking block, then text,
    then a tool_use block per (name, input) in tool_calls (stop_reason becomes
    "tool_use" when there are any). extra_blocks go first, e.g. a fallback block."""
    from anthropic.types.beta import BetaMessage
    content = list(extra_blocks) + [{"type": "thinking", "thinking": "", "signature": "stub"}]
    if text:
        content.append({"type": "text", "text": text})
    for n, (name, tool_input) in enumerate(tool_calls):
        content.append({"type": "tool_use", "id": f"toolu_stub_{n}", "name": name, "input": tool_input})
    if tool_calls and stop_reason == "end_turn":
        stop_reason = "tool_use"
    return BetaMessage.model_validate({
        "id": "msg_stub", "type": "message", "role": "assistant", "model": model,
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "stop_details": stop_details, "usage": {"input_tokens": 0, "output_tokens": 0},
    })


class _StubStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        text = "".join(b.text for b in self._message.content if b.type == "text")
        pieces = text.split(" ")
        for i, piece in enumerate(pieces):
            yield piece if i == len(pieces) - 1 else piece + " "

    def get_final_message(self):
        return self._message


class _StubMessages:
    """beta.messages for the stub client. Answers each request with the next
    entry of .script (a BetaMessage, or a callable taking the request kwargs
    and returning one), and with STUB_RESPONSE (read at call time, so tests can
    swap it) once the script is empty. Keeps the last request's arguments in
    .last_request and a snapshot of every request in .requests, so a test can
    script a fetch_section round and inspect each round's request."""
    def __init__(self):
        self.last_request = None
        self.requests: list[dict] = []
        self.script: list = []

    def _answer(self, kwargs):
        # The tool loop appends to the same messages list between rounds, so
        # each request is recorded with its own copy of the list.
        snapshot = dict(kwargs)
        if "messages" in snapshot:
            snapshot["messages"] = list(snapshot["messages"])
        self.last_request = snapshot
        self.requests.append(snapshot)
        if self.script:
            nxt = self.script.pop(0)
            return nxt(kwargs) if callable(nxt) else nxt
        return _stub_message(kwargs["model"], STUB_RESPONSE)

    def reset(self):
        self.last_request = None
        self.requests.clear()
        self.script.clear()

    def create(self, **kwargs):
        return self._answer(kwargs)

    def stream(self, **kwargs):
        return _StubStream(self._answer(kwargs))


class _StubAnthropicClient:
    """Stand-in for the Anthropic client when BOWEN_STUB_LLM is set.

    It never opens a connection: client.beta.messages.create/stream answer
    locally, in the real response shape, with the next scripted message or
    STUB_RESPONSE (see _StubMessages). Nothing else is defined, so any other
    API use raises AttributeError.
    """
    def __init__(self):
        self.beta = type("StubBeta", (), {})()
        self.beta.messages = _StubMessages()

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
from .acts_registry import (
    detect_act_from_query, get_all_acts, has_registry_signal, ACTS_REGISTRY,
    REPEALED_TITLES, PARTIALLY_REPEALED_ACTS, count_in_force_acts,
    detect_repealed_mentions, repealed_note, held_acts_for_query, titles_for_base_name,
)
print(f"[BOOT] Acts registry OK ({len(ACTS_REGISTRY)} acts)", flush=True)

# The search planner (Claude Haiku), the second opinion (OpenAI) and the web
# context (OpenAI or Perplexity web search). Each never raises and returns None
# when off or failing.
from . import planner
from . import second_opinion
from . import web_context


def _vendor_configs():
    """(second_opinion.Config, web_context.Config) from the environment. Under
    BOWEN_STUB_LLM both are off whatever keys the environment holds, so an
    offline run calls no vendor; tests that need them on set the globals."""
    so_cfg, web_cfg = second_opinion.load_config(), web_context.load_config()
    if STUB_LLM:
        import dataclasses
        so_cfg = dataclasses.replace(so_cfg, mode="off")
        web_cfg = dataclasses.replace(web_cfg, mode="off")
    return so_cfg, web_cfg


# Loaded once here and again in startup(); requests read these globals.
SECOND_OPINION_CONFIG, WEB_CONTEXT_CONFIG = _vendor_configs()

# Every in-force title, as /acts lists them, for the AVAILABLE ACTS section: the
# model guessed "not held" for held Acts when it only knew the count.
HELD_ACT_TITLES = sorted({a["title"] for a in get_all_acts()})

# Bowen's whole answer to "why can't you find it / why didn't you retrieve it /
# how do you find sections" (12 Nov ticket, item 3). The founder approves this
# wording; change it here only. It reaches the model through rule 9 and
# CASUAL_CONTEXT.
RETRIEVAL_LINE = "I don't always find the section a question needs, so ask me again naming the Act and the section number, or read it at legislation.govt.nz."

# System prompt
SYSTEM_PROMPT = f"""You are Bowen, a chatbot legal information assistant for New Zealand legislation.

## IDENTITY
You ARE Bowen. Always refer to yourself in the first person — "I", "me", "my". Never say "Bowen is..." or "Bowen has..." — say "I am...", "I have...". When someone asks "What's Bowen about?", respond with "I'm a legal information assistant..." not "Bowen is a legal information assistant...".

Bowen has his own personality: passion and humour, with precision about the legal text he holds. He provides information, never advice. He believes that information transmission is one of the essences of the universe, and that law is perhaps like a semantic engine that constantly translates between levels of abstraction, from broad principles to specific rules to particular applications.

Who runs you, as your About page (bowenpublic.com/about) states it: Bowen Public is operated by the Bowen Public Charitable Trust, a charitable trust board incorporated under the Charitable Trusts Act 1957; the service is free to use; registration with Charities Services is in progress. You may say this when asked, since it is about you, not a statement of law. For anything else about the Trust, point to that page. Whether this changes how any law applies is a legal question, answered under the rules below.

## WHERE YOUR ANSWERS COME FROM
Each user message arrives with a block headed "LEGISLATION EXCERPTS FROM DATABASE". Those excerpts are your only source of law. You do not answer legal questions from your own memory of NZ law, even when you are confident: memory can be out of date, can get section numbers wrong, and can describe law that has been repealed. A section you fetch with the fetch_section tool, when it is offered, counts as an excerpt for this answer.

## FETCHING A SECTION
When the fetch_section tool is offered, use it to read a section of a held Act that you need but were not shown, in two cases: an excerpt your answer relies on depends on another section (it cites the section, or uses a term defined elsewhere in the Act, such as in its interpretation section), or the person asked about a section by number and it is not in the excerpts. Fetch before you write any of the answer, then write the whole answer once. You may use what you know of an Act's layout to choose which section to fetch; what you rely on is the text that comes back, and if it is not the section you needed, say so and do not describe what you expected. For a long section, give the term you need as "find". Fetch only what the answer needs. If a fetch says the section is not held or does not exist, say that, and describe nothing about it. A section you have neither been shown nor fetched is unseen under rule 2.

## RULES
1. You provide information, not legal advice.
2. Answer only from the LEGISLATION EXCERPTS FROM DATABASE. Every rule, section number, time limit, amount, rate, entitlement, duty or offence you state must come from an excerpt you have been shown. If it is not in an excerpt, do not state it.
   This covers what a section, Part, Schedule or clause says. Unless its own text is in this turn's excerpts, do not say, suggest or guess what a numbered provision contains, deals with or "likely" covers, not even with "may", "probably" or a disclaimer, and not in a partial answer under rule 4. If your answer needs it, fetch it (FETCHING A SECTION). If you cannot, say that it was not among the sections you pulled for this answer and give the next step, in this form: "Section 6 wasn't among the sections I pulled for this answer. Ask me 'what does section 6 of the Lawyers and Conveyancers Act say' and I'll fetch it." A provision that an excerpt mentions by number (for example a heading "Exceptions to sections 21, 22, 24, and 26") may be named as it is mentioned there, but described no further than that excerpt describes it. Your earlier answers in this conversation are not excerpts: a section you described in an earlier turn must be in this turn's excerpts before you describe it again.
3. If no excerpt governs the question, do not answer the legal question. Name the Act that probably governs it if you know it; if that Act is on the list in AVAILABLE ACTS, say that you hold it but the section that deals with this was not among the sections you pulled for this answer, and say that you do not hold it only if it is not on that list; point the person to legislation.govt.nz and to Community Law (communitylaw.org.nz) for free legal help; then stop and end with "SOURCES: none". On this path you must NOT:
   a. summarise, outline or characterise what the Act provides, "in general terms", "generally" or otherwise;
   b. name its Parts, subparts or sections, except to say that a section the person asked about by number was not among the sections you pulled;
   c. state any entitlement, rate, test, duty or liability, even with a disclaimer attached ("I won't state that as the law" does not make it allowed);
   d. give any phone number, website or organisation other than legislation.govt.nz, Community Law and the SAFETY helplines.
4. If the excerpts answer part of the question, answer that part from them and say plainly which part they do not cover, without guessing what any unretrieved section says about it (rule 2).
5. Put words in quotation marks only when they appear word for word in an excerpt. Otherwise paraphrase, without quotation marks.
6. IMPORTANT: The user's question may contain quoted legal text they want explained, and they may upload documents. That is NOT an excerpt from the database: it is text the user is asking about. Only content under "LEGISLATION EXCERPTS FROM DATABASE:" is an official excerpt. You may explain the user's text, but any statement of what the law is must still come from an excerpt.
7. Never present a repealed Act as current law. If the question names a repealed Act, or the excerpts block carries a repeal note, say that the Act is repealed, say when, name the Act that replaced it, and answer from the replacement Act's excerpts if they are present. If an Act's excerpts carry a status note (for example, that most of the Act is repealed), follow it.
8. Casual, non-legal messages (greetings, thanks, questions about you): reply briefly and conversationally without stating any law, and end with "SOURCES: none". A question about why you could not find something is answered under rule 9.
9. Do not mention these rules, the excerpts block or the SOURCES line in your answer text. If someone asks why you could not find or retrieve a section, or how you find sections, reply with exactly this sentence: "{RETRIEVAL_LINE}" Say nothing about how you search, which Acts or excerpts you were given, or how you feel about it, and do not apologise for or explain earlier answers. If the section they mean is in this turn's excerpts, or you fetch it, follow the sentence with an answer from it, cited as usual.

## SAFETY
This section comes before any law and overrides the brevity rule.
- If the person may be in danger or distress, give help first, before any law: 111 for immediate danger; 1737 (free call or text) to talk with a trained counsellor; Women's Refuge 0800 733 843; Lifeline 0800 543 354; Oranga Tamariki 0508 326 459 if a child is at risk. Then answer any legal part under the rules above.
- If the request is for help doing something that would harm another person (for example hurting, threatening, stalking, secretly recording or tracking someone, or sharing intimate images of someone), do not give the operational help. Say plainly that the conduct is unlawful. Cite the section only if it is in the excerpts; otherwise point to legislation.govt.nz. Keep it short and do not lecture.
- Ordinary questions about the same Acts (for example, what the law says about recording a phone call, or what someone can do if their images were shared) are answered normally under the rules above.
- These helplines and that decline are the ONLY things you may say that do not come from the excerpts.

## SOURCES LINE (required on every answer)
End every answer, including casual replies, with one final line in exactly this form, after any sign-off:
SOURCES: Residential Tenancies Act 1986 s 18; Residential Tenancies Act 1986 s 42B
List only the excerpts your answer actually relied on, in the order you used them. Each entry is the Act title as it appears in the excerpt heading, then " s ", then the section number exactly as it appears in the excerpt heading (for example 22A, 66J, Schedule 1 cl 11). Separate entries with "; ". Never list a section that was not in the excerpts. If the answer relied on no excerpt, the line is:
SOURCES: none
Nothing comes after this line. Do not bold it or put it in a code block.

## TE TIRITI O WAITANGI / TREATY OF WAITANGI
The Treaty is foundational to NZ law and requires particular care in your responses.

This section is background for explaining the Treaty and the essays on your Te Tiriti page. It is not a source of law: never cite a section of any Act from it unless that section is in the excerpts.

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

## RESPONSE STYLE
BREVITY IS PARAMOUNT. If you can say it in 2 sentences, don't use 4. Prefer clear prose over bullet lists — use bullets only when genuinely listing items, not as a default structure.

For general questions ("What is the RMA?"): 1-2 sentence explanation from the excerpts, cite the single most relevant section, done.
For specific questions ("What is the bond limit?"): Answer directly with the provision. No preamble.

Do NOT exhaustively list every related section. Cite what matters most. The user can always ask for more.

## AVAILABLE ACTS
You hold the published text of {count_in_force_acts()} in-force NZ Acts, retrieved from legislation.govt.nz between March and May 2026; they are listed below. For each question you are shown only a handful of excerpts retrieved from them; an Act or section that is not in the excerpts was not retrieved for this question, and you must not fill the gap from memory (you may fetch a section: FETCHING A SECTION).

If the Act that governs the question is on this list, you HOLD it: say "I hold the X Act, but the section that deals with this wasn't among the sections I pulled for this answer", and if the person can name the section, invite them to ask for it by number. Say "I don't hold" ONLY for an Act that is not on this list. A line in the excerpts block, "ACTS BOWEN HOLDS THAT MATCH THIS QUESTION", names the listed Acts that match each question.

You hold Acts only, no regulations or orders. Some things people often ask about are not held, for example the Holidays Act 2003, the Minimum Wage Act 1983, the Sale and Supply of Alcohol Act 2012, the Charities Act 2005, the End of Life Choice Act 2019 and the Residential Tenancies (Healthy Homes Standards) Regulations 2019. When users ask what you have access to, describe it accurately, without overstating or understating it.

Acts you hold: {"; ".join(HELD_ACT_TITLES)}.

## CITATION FORMAT
When citing an excerpt: "Under section X of the [Act title]..."

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
On subsequent responses, keep it short: "As always — verify and get advice for your situation." or omit entirely if the flow is conversational.
The SOURCES line still comes last, after the sign-off."""


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


def drop_repealed_rows(emb, meta):
    """Drop every row whose act_title is a wholly repealed Act.

    Returns (embeddings, metadata, n_dropped) with the two kept aligned by one
    boolean mask. When nothing is dropped the inputs are returned unchanged, so
    a memory-mapped array stays memory-mapped. Used by startup() and by the
    test harness (conftest.py), so both see the same index.
    """
    keep = np.fromiter(
        (row.get("act_title", "") not in REPEALED_TITLES for row in meta),
        dtype=bool, count=len(meta),
    )
    if len(emb) != len(meta):
        raise ValueError(f"embeddings ({len(emb)}) and metadata ({len(meta)}) are misaligned")
    dropped = int((~keep).sum())
    if dropped == 0:
        return emb, meta, 0
    new_emb = np.ascontiguousarray(emb[keep])
    new_meta = [row for row, k in zip(meta, keep) if k]
    return new_emb, new_meta, dropped


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

        embeddings, metadata, dropped = drop_repealed_rows(embeddings, metadata)
        print(f"✓ Dropped {dropped:,} rows of wholly repealed Acts "
              f"({', '.join(sorted(REPEALED_TITLES))}); {len(metadata):,} chunks remain", flush=True)
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
            print(f"✓ Anthropic client initialized (model {CLAUDE_MODEL}, effort {CLAUDE_EFFORT})",
                  flush=True)
        except Exception as e:
            print(f"✗ Could not initialize Anthropic: {e}", flush=True)
    else:
        print("✗ ANTHROPIC_API_KEY not set in .env", flush=True)

    # The planner's held-Act index, built after the repealed rows are dropped.
    if metadata is not None:
        n_acts = len(_sections_by_act())
        print(f"✓ Search planner: {'on' if planner.planner_enabled() else 'off'} "
              f"(model {planner.planner_model()}, {n_acts} Acts indexed)", flush=True)

    # Second opinion and web context: one config each, read here, one log line each.
    global SECOND_OPINION_CONFIG, WEB_CONTEXT_CONFIG
    SECOND_OPINION_CONFIG, WEB_CONTEXT_CONFIG = _vendor_configs()
    second_opinion.log_startup(SECOND_OPINION_CONFIG)
    web_context.log_startup(WEB_CONTEXT_CONFIG)
    print(f"✓ Second opinion: {SECOND_OPINION_CONFIG.mode if SECOND_OPINION_CONFIG.enabled else 'off'}; "
          f"web context: {WEB_CONTEXT_CONFIG.mode if WEB_CONTEXT_CONFIG.enabled else 'off'}", flush=True)

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
    raw_scores = np.dot(embeddings, query_embedding)
    similarities = raw_scores.copy()

    query_lower = query.lower()

    # Get key sections for this query
    key_sections = get_key_sections_for_query(query)

    # Keyword boosting for "what is" questions
    boost_terms = ['purpose', 'interpretation', 'application', 'object', 'principle', 'definition']
    is_overview_question = any(q in query_lower for q in ['what is', 'what are', 'explain', 'overview', 'purpose of'])

    # Best row per exact pinned (act, section), by raw score.
    pin_rows = {}

    for i, meta in enumerate(metadata):
        raw_score = similarities[i]

        if (key_sections and is_pinned_section(meta, key_sections)
                and (raw_score >= PINNED_MIN_SIMILARITY or pin_ignores_floor(meta))):
            pin_key = (meta.get("act_title", ""), meta.get("section_number", "").strip())
            if pin_key not in pin_rows or raw_score > raw_scores[pin_rows[pin_key]]:
                pin_rows[pin_key] = i

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

    pinned = _apply_pins(top_indices, pin_rows, raw_scores, similarities, top_k)

    # Sections named by number are looked up only inside an Act in play; with
    # no Act there is no telling whose "section 25" is meant.
    if act_filter:
        explicit = _explicit_section_rows(query, act_filter, raw_scores, similarities, top_k)
        if explicit:
            taken = {_row_key(i) for i in explicit}
            rest = [i for i in top_indices if _row_key(i) not in taken]
            top_indices = explicit + rest[:max(0, top_k - len(explicit))]
            pinned |= set(explicit)

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
            "score": float(similarities[idx]),
            "pinned": idx in pinned,
        })

    return results


def _apply_pins(top_indices: list, pin_rows: dict, raw_scores, similarities, top_k: int) -> set:
    """Guarantee the pinned key sections a place in top_indices (in place).

    Missing pins, highest raw score first and at most MAX_PINNED, replace the
    lowest-ranked results that are not themselves pinned; top_k is kept and
    the act filter (score -1) is respected. Returns the pinned indices.
    """
    if not pin_rows:
        return set()

    def key(i):
        return (metadata[i].get("act_title", ""), metadata[i].get("section_number", "").strip())

    pin_keys = {k for k, i in pin_rows.items() if similarities[i] > -1}
    protected = {i for i in top_indices if key(i) in pin_keys}
    present = {key(i) for i in top_indices}
    missing = sorted((pin_rows[k] for k in pin_keys if k not in present),
                     key=lambda i: raw_scores[i], reverse=True)[:MAX_PINNED]

    for idx in missing:
        if len(top_indices) >= top_k:
            drop = next((j for j in range(len(top_indices) - 1, -1, -1)
                         if top_indices[j] not in protected), None)
            if drop is None:
                break
            del top_indices[drop]
        top_indices.append(idx)
        protected.add(idx)

    top_indices.sort(key=lambda i: similarities[i], reverse=True)
    return protected


# A section reference needs its prefix ("section", "sections", "sec", "s",
# "ss"), so "90 day notice" and bare years are never read as sections. The
# lookbehind keeps "it's 25" and "pages 2" out; at most three digits (the
# corpus tops out at s 726) keeps "s 2020" out, and ordinals ("25th") are not
# letter suffixes. "(2)" subsections are dropped.
_SECTION_NUM = r"(\d{1,3}(?!(?:st|nd|rd|th)\b)[a-z]{0,2})(?!\w)(?:\s*\([0-9a-z]{1,4}\))*"
_SECTION_PREFIX = r"(?<![\w'’])(?:sections?|secs?\.?|ss\.?|s\.?)\s*"
_SECTION_REF_RE = re.compile(
    _SECTION_PREFIX + _SECTION_NUM
    + r"(?:\s*(?:,|and|or|&|to|-|–|—)\s*(?:" + _SECTION_PREFIX + r")?" + _SECTION_NUM + r")*",
    re.IGNORECASE,
)
_SECTION_NUM_RE = re.compile(_SECTION_NUM, re.IGNORECASE)
_RANGE_SEP_RE = re.compile(r"^\s*(?:to|-|–|—)\s*$", re.IGNORECASE)


def parse_section_refs(query: str) -> List[str]:
    """Section numbers the question names, upper-cased, in order, without
    subsections: "sections 25(2) and 27" -> ["25", "27"]. A small numeric range
    ("ss 24 to 26") is expanded; at most MAX_EXPLICIT_SECTIONS are returned."""
    refs: List[str] = []

    def add(sec: str):
        if sec not in refs:
            refs.append(sec)

    for match in _SECTION_REF_RE.finditer(query or ""):
        span = match.group(0)
        nums = list(_SECTION_NUM_RE.finditer(span))
        for k, m in enumerate(nums):
            sec = m.group(1).upper()
            prev = nums[k - 1] if k else None
            if (prev and sec.isdigit() and prev.group(1).isdigit()
                    and _RANGE_SEP_RE.match(span[prev.end():m.start()])):
                lo, hi = int(prev.group(1)), int(sec)
                if 0 < hi - lo <= MAX_SECTION_RANGE:
                    for n in range(lo + 1, hi):
                        add(str(n))
            add(sec)
    return refs[:MAX_EXPLICIT_SECTIONS]


def _row_key(i: int) -> tuple:
    meta = metadata[i]
    return (meta.get("act_title", ""), meta.get("section_number", ""), meta.get("text", ""))


def _section_rows(wanted: set, keep) -> dict:
    """{SECTION: [row indices in corpus order]} for every row whose section
    number, stripped and upper-cased, is in wanted and for which keep(i, meta)
    is true. The (act, section) lookup shared by _explicit_section_rows and
    fetch_section_text."""
    by_section: dict = {}
    for i, meta in enumerate(metadata):
        sec = meta.get("section_number", "").strip().upper()
        if sec in wanted and keep(i, meta):
            by_section.setdefault(sec, []).append(i)
    return by_section


def _explicit_section_rows(query: str, act_filter: str, raw_scores, similarities, top_k: int) -> list:
    """Row indices for the sections the question names, inside the act filter
    (rows it excluded score -1). Each section keeps its MAX_CHUNKS_PER_SECTION
    chunks most similar to the question; every named section's best chunk
    comes before any second chunk, so a cap at top_k drops second chunks first.

    The act filter is a substring match ("Crimes" also admits the International
    Crimes and International Criminal Court Act); ranking sorts that out, but a
    lookup by number would return that Act's s 48 too. So when the filter is a
    registry base name, only the Acts with exactly that name are looked up."""
    refs = parse_section_refs(query)
    if not refs:
        return []
    exact_titles = set(titles_for_base_name(act_filter))
    return _named_section_rows(
        refs,
        lambda i, meta: similarities[i] > -1
        and (not exact_titles or meta.get("act_title", "") in exact_titles),
        lambda i: raw_scores[i], MAX_CHUNKS_PER_SECTION, top_k)


def _named_section_rows(sections: list, keep, score, per_section: int, limit: int) -> list:
    """Row indices for sections looked up by number: the exact-row lookup
    shared by sections the user names and sections the search planner names.
    Each section keeps its per_section distinct chunks with the highest
    score(i); every section's best chunk comes before any second chunk, so a
    cap at limit drops second chunks first."""
    by_section = _section_rows({s.strip().upper() for s in sections}, keep)
    chunks = []
    for sec in sections:
        rows, seen = [], set()
        for i in sorted(by_section.get(sec.strip().upper(), []), key=score, reverse=True):
            if _row_key(i) not in seen:
                seen.add(_row_key(i))
                rows.append(i)
        chunks.append(rows[:per_section])

    ordered = [rows[n] for n in range(per_section) for rows in chunks if n < len(rows)]
    return ordered[:limit]


# =============================================================================
# The search planner's plan, merged into the six excerpts
# =============================================================================

_sections_by_act_cache: dict = {"key": None, "index": {}}
# The best rows of the user's own search that a plan can never push out. The
# rewrite's rows can outscore every one of them (measured: "can my boss read my
# emails" lost all six to a plan for the wrong Act), so these are kept first.
PLAN_KEEPS_OWN_ROWS = 2


def _sections_by_act() -> dict:
    """planner.build_section_index of the loaded index (after the repealed rows
    are dropped), built once per index; startup() builds it eagerly."""
    key = (id(metadata), len(metadata or []))
    if _sections_by_act_cache["key"] != key:
        _sections_by_act_cache.update(key=key, index=planner.build_section_index(metadata or []))
    return _sections_by_act_cache["index"]


def _result_from_row(idx: int, score: float, pinned: bool) -> dict:
    """One index row in the dict shape search_similar returns."""
    meta = metadata[idx]
    return {
        "text": meta.get("text", ""),
        "act_title": meta.get("act_title", ""),
        "act_short_name": meta.get("act_short_name", ""),
        "section_number": meta.get("section_number", ""),
        "section_heading": meta.get("section_heading", ""),
        "section_url": meta.get("section_url", ""),
        "act_url": meta.get("act_url", ""),
        "score": float(score),
        "pinned": pinned,
    }


def _result_key(r: dict) -> tuple:
    return (r["act_title"], r["section_number"], r["text"])


def _section_of(r: dict) -> tuple:
    return (r["act_title"], (r["section_number"] or "").strip())


def merged_search(query: str, detected_act: Optional[str], merged=None, top_k: int = 6) -> List[dict]:
    """The excerpts for a legal question: today's search_similar, plus what a
    search plan adds (planner.merge_plan's MergedSearch). With no plan, or a
    plan that adds nothing, this IS search_similar(query, top_k, detected_act),
    the same list unchanged.

    Order: 1. sections the user named by number (as search_similar placed
    them); 2. at most planner.MAX_PLAN_SECTIONS plan sections, one chunk each
    (the chunk closest to the user's words), by exact row in the plan's own
    titles, pinned; 3. today's other pinned rows; 4. the PLAN_KEEPS_OWN_ROWS
    best other rows of the user's own search; 5. the rest by score from the
    user's own search and the rewrite's search together. Distinct rows
    only, at most MAX_CHUNKS_PER_SECTION chunks of one section. The plan's Act
    never filters the user's own words (merged.act_filter is today's filter).
    """
    act_filter = merged.act_filter if merged is not None else detected_act
    base = search_similar(query, top_k=top_k, act_filter=act_filter)
    if merged is None or not (merged.extra_sections or merged.extra_query):
        return base

    # 1. The user's named sections: search_similar pinned them ahead of the rest.
    refs = set(parse_section_refs(query)) if act_filter else set()
    exact = set(titles_for_base_name(act_filter)) if act_filter else set()
    explicit = [r for r in base if r["pinned"] and r["section_number"].strip().upper() in refs
                and (not exact or r["act_title"] in exact)]

    out: list = []
    seen: set = set()
    per_section: dict = {}

    def add(r: dict) -> bool:
        k, s = _result_key(r), _section_of(r)
        if len(out) >= top_k or k in seen or per_section.get(s, 0) >= MAX_CHUNKS_PER_SECTION:
            return False
        seen.add(k)
        per_section[s] = per_section.get(s, 0) + 1
        out.append(r)
        return True

    for r in explicit:
        add(r)

    # 2. Plan sections, one chunk each, into the slots that are left.
    if merged.extra_sections and merged.section_act_titles and len(out) < top_k:
        titles = set(merged.section_act_titles)
        qv = embedding_model.encode(query, convert_to_numpy=True)
        scores: dict = {}

        def score(i):
            if i not in scores:
                scores[i] = float(np.dot(embeddings[i], qv))
            return scores[i]

        rows = _named_section_rows(merged.extra_sections,
                                   lambda i, meta: meta.get("act_title", "") in titles,
                                   score, 1, planner.MAX_PLAN_SECTIONS)
        for i in rows:
            add(_result_from_row(i, score(i), pinned=True))

    # 3 and 4. Today's pinned rows, then everything else by score.
    extra = (search_similar(merged.extra_query, top_k=top_k, act_filter=merged.extra_query_act_filter)
             if merged.extra_query else [])
    rest = [r for r in base if r not in explicit]
    own = [r for r in rest if not r["pinned"]]
    pool = ([r for r in rest if r["pinned"]] + own[:PLAN_KEEPS_OWN_ROWS]
            + sorted(own[PLAN_KEEPS_OWN_ROWS:] + extra, key=lambda r: -r["score"]))
    for r in pool:
        add(r)
    return out


# =============================================================================
# fetch_section: the one tool Claude is given, on legal questions only
# =============================================================================

_corpus_titles_cache: dict = {"key": None, "titles": [], "short": {}}
_YEAR_SUFFIX_RE = re.compile(r"\s+\d{4}$")
_FETCH_PREFIX_RE = re.compile(r"^(?:sections?|secs?\.?|ss?\.?)\s*(?=\d)", re.IGNORECASE)
_SUBSECTION_RE = re.compile(r"(?<=[0-9a-z])(?:\s*\([0-9a-z]{1,4}\))+", re.IGNORECASE)


def _corpus_titles():
    """(sorted Act titles in the loaded index, {SHORT NAME: {titles}})."""
    key = (id(metadata), len(metadata or []))
    if _corpus_titles_cache["key"] != key:
        titles, short = set(), {}
        for meta in metadata or []:
            title = meta.get("act_title", "")
            if not title:
                continue
            titles.add(title)
            sn = (meta.get("act_short_name") or "").strip().upper()
            if sn:
                short.setdefault(sn, set()).add(title)
        _corpus_titles_cache.update(key=key, titles=sorted(titles), short=short)
    return _corpus_titles_cache["titles"], _corpus_titles_cache["short"]


def _resolve_held_act(act: str):
    """(title, candidates). title is the held Act the name means, or None;
    candidates are held titles when the name fits more than one."""
    want = _norm_title(act)
    if want.startswith("the "):
        want = want[4:]
    if not want:
        return None, []
    titles, short = _corpus_titles()
    for t in titles:
        if _norm_title(t) == want:
            return t, []
    bare = _YEAR_SUFFIX_RE.sub("", want)
    same_name = [t for t in titles if _YEAR_SUFFIX_RE.sub("", _norm_title(t)) == bare]
    if len(same_name) == 1:
        return same_name[0], []
    if same_name:
        return None, same_name[:5]
    by_short = short.get(act.strip().upper(), set())
    if len(by_short) == 1:
        return next(iter(by_short)), []
    contained = [t for t in titles if _titles_match(want, t)]
    if len(contained) == 1:
        return contained[0], []
    return None, contained[:5]


def _fetch_section_key(section: str) -> str:
    """"s 6(1)(a)" -> "6"; "Schedule 1 cl 11" -> "SCHEDULE 1 CL 11"."""
    sec = " ".join((section or "").split())
    sec = _FETCH_PREFIX_RE.sub("", sec)
    sec = _SUBSECTION_RE.sub("", sec)
    return sec.strip(" .,;").upper()


def _norm_find(text: str) -> str:
    return " ".join((text or "").lower().replace("’", "'").replace("“", '"')
                    .replace("”", '"').split())


def _fit_section_text(texts: list, find: Optional[str]) -> tuple[str, str]:
    """(text, note) for a section's chunks, within MAX_FETCH_CHARS. A long
    section keeps the chunks containing `find` and the chunk after each (a
    definition can run across a chunk boundary), else its start."""
    total = sum(len(t) for t in texts) + len(texts) - 1
    if total <= MAX_FETCH_CHARS:
        return " ".join(texts), ""
    picked: list = []
    if find and _norm_find(find):
        needle = _norm_find(find)
        for k, t in enumerate(texts):
            if needle in _norm_find(t):
                picked += [j for j in (k, k + 1) if j < len(texts) and j not in picked]
    if picked:
        note = (f'This section is {total:,} characters long, so only the parts containing '
                f'"{find}" are shown, in order; "[...]" marks text left out.')
    else:
        picked = list(range(len(texts)))
        note = ((f'"{find}" does not appear in this section. ' if find else "")
                + f"This section is {total:,} characters long, so only its start is shown; "
                  "to see another part, fetch it again with find set to the term you need.")
    out, used, prev = [], 0, None
    if min(picked) > 0:
        out.append("[...]")
    for j in sorted(picked):
        if used + len(texts[j]) > MAX_FETCH_CHARS and out:
            break
        piece = texts[j][:MAX_FETCH_CHARS - used]
        if prev is not None and j != prev + 1:
            out.append("[...]")
        out.append(piece)
        used += len(piece)
        prev = j
    if prev is not None and prev < len(texts) - 1:
        out.append("[...]")
    return " ".join(out), note


def fetch_section_text(act: str, section: str, find: Optional[str] = None):
    """What fetch_section returns: (tool_result_text, result). result is the
    section in the same dict shape search_similar returns, so the SOURCES line
    can match it, or None when nothing was found. Nothing is listed that is not
    in the index."""
    title, candidates = _resolve_held_act(act)
    if not title:
        repealed = [t for t in REPEALED_TITLES if _titles_match(act, t)]
        if repealed:
            return f"NOT HELD: {repealed_note(repealed[0])}", None
        if candidates:
            return (f'NOT FOUND: "{act}" fits more than one Act Bowen holds: '
                    f'{"; ".join(candidates)}. Fetch again with the full title.'), None
        return (f'NOT HELD: Bowen does not hold an Act titled "{act}". Say so, and describe '
                "nothing from it."), None

    key = _fetch_section_key(section)
    rows = _section_rows({key}, lambda i, meta: meta.get("act_title", "") == title).get(key, []) if key else []
    if not rows:
        return (f'NO SUCH SECTION: the {title} that Bowen holds has no section "{section}". '
                "Say it was not found, and describe nothing about it."), None

    texts, seen = [], set()
    for i in sorted(rows):
        text = metadata[i].get("text", "") or ""
        if text and text not in seen:
            seen.add(text)
            texts.append(text)
    body, note = _fit_section_text(texts, find)
    first = metadata[rows[0]]
    sec_number = (first.get("section_number") or "").strip()
    heading = first.get("section_heading") or ""
    result = {
        "text": body,
        "act_title": title,
        "act_short_name": first.get("act_short_name", ""),
        "section_number": sec_number,
        "section_heading": heading,
        "section_url": first.get("section_url", ""),
        "act_url": first.get("act_url", ""),
        "score": 1.0,  # an exact lookup, not a similarity
        "pinned": True,
        "fetched": True,
    }
    parts = [f'FETCHED FROM DATABASE. This counts as an excerpt; if you rely on it, list it on '
             f'the SOURCES line as "{title} s {sec_number}".', f"## {title}"]
    status_note = PARTIALLY_REPEALED_ACTS.get(title)
    if status_note:
        parts.append(f"STATUS NOTE: {status_note}")
    parts.append(f"**Section {sec_number}" + (f" - {heading}" if heading else "") + f"**\n{body}")
    if note:
        parts.append(note)
    return "\n\n".join(parts), result


class _FetchState:
    """One answer's fetches. results (the list the endpoint passed in) collects
    each section found, once, for the SOURCES-line matching."""

    def __init__(self, results: list):
        self.results = results
        self.calls = 0
        self._seen: dict = {}
        self.found: list = []   # sections found, in fetch order (for the status line)

    @property
    def full(self) -> bool:
        return self.calls >= MAX_FETCHED_SECTIONS

    def run(self, block) -> dict:
        """The tool_result block for one tool_use block."""
        args = block.input if isinstance(block.input, dict) else {}
        act, section, find = args.get("act"), args.get("section"), args.get("find")
        if (block.name != FETCH_TOOL_NAME or not isinstance(act, str) or not isinstance(section, str)
                or not (find is None or isinstance(find, str))):
            return _tool_result(block, f"Invalid call: {FETCH_TOOL_NAME} takes act and section "
                                       "as text, and optionally find.", error=True)
        key = (_norm_title(act), _fetch_section_key(section), _norm_find(find or ""))
        if key in self._seen:
            return _tool_result(block, "Already fetched for this answer; its text is above.")
        if self.full:
            return _tool_result(block, (
                f"Not fetched: the limit of {MAX_FETCHED_SECTIONS} fetches for one answer is "
                "reached. Answer now from what you have; for a section you could not fetch, "
                "say it was not among the sections you pulled and how to ask for it."), error=True)
        self.calls += 1
        text, result = fetch_section_text(act, section, find)
        self._seen[key] = True
        logger.info(LogEvent.SEARCH, "fetch_section", act=act, section=section, find=find,
                    found=bool(result))
        if result:
            self.found.append(result)
        if result and not any(r["act_title"] == result["act_title"]
                              and r["section_number"] == result["section_number"]
                              for r in self.results):
            self.results.append(result)
        return _tool_result(block, text)


class FetchStatus:
    """Yielded by _answer_rounds after a fetch round, before Claude's next
    request: /chat/stream sends .text as a "status" event so the reader sees
    why the answer is taking longer. The text names only Acts and sections the
    index resolved (fetch_section_text's result), never the model's input."""

    def __init__(self, text: str):
        self.text = text

    def __repr__(self):
        return f"<FetchStatus {self.text!r}>"


MAX_STATUS_SECTIONS = 3


def fetch_status_text(found: List[dict]) -> str:
    """"Reading section 6 of the Lawyers and Conveyancers Act 2006…" for the
    sections found in one fetch round; "" when none was found."""
    by_act: dict = {}
    for r in found[:MAX_STATUS_SECTIONS]:
        sec = (r.get("section_number") or "").strip()
        title = r.get("act_title") or ""
        if sec and title and sec not in by_act.setdefault(title, []):
            by_act[title].append(sec)
    parts = []
    for title, secs in by_act.items():
        numbered = [s for s in secs if s[:1].isdigit()]
        other = [s for s in secs if not s[:1].isdigit()]   # "Schedule 1 cl 11"
        names = []
        if numbered:
            word = "section" if len(numbered) == 1 else "sections"
            names.append(f"{word} {' and '.join(numbered)}")
        names += other
        if names:
            parts.append(f"{' and '.join(names)} of the {title}")
    if not parts:
        return ""
    return f"Reading {' and '.join(parts)}…"


def _tool_result(block, text: str, error: bool = False) -> dict:
    out = {"type": "tool_result", "tool_use_id": block.id, "content": text}
    if error:
        out["is_error"] = True
    return out


NO_EXCERPTS_CONTEXT = (
    "No legislation excerpts were retrieved for this question. Do not answer it from memory: "
    "name the Act that probably governs it if you know it; if it is on the list of Acts you "
    "hold, say that you hold it but the relevant section was not among the sections you pulled "
    "for this answer, and say that you do "
    "not hold it only if it is not on that list; point to legislation.govt.nz and Community Law "
    "(communitylaw.org.nz), and stop. Do not summarise or characterise what the Act says "
    "\"in general terms\", do not name its Parts or sections (other than to say that a section "
    "the person asked about was not among the sections you pulled), do not state any entitlement, "
    "rate, test or liability even with a disclaimer, and give no other phone number or "
    "organisation (except the safety helplines). End with \"SOURCES: none\"."
)

CASUAL_CONTEXT = (
    "No legislation search performed — this appears to be a casual/non-legal message. "
    "Reply briefly without stating any law, and end with \"SOURCES: none\". "
    "If they ask why you could not find or retrieve something, reply with exactly: "
    f"\"{RETRIEVAL_LINE}\" Nothing about how you search, what you were given or how you feel."
)


def build_context(results: List[dict]) -> str:
    """Build context string with better organization."""
    if not results:
        return NO_EXCERPTS_CONTEXT

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
        status_note = PARTIALLY_REPEALED_ACTS.get(act_title)
        if status_note:
            act_section += f"STATUS NOTE: {status_note}\n\n"
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


MAX_HELD_LINE_ACTS = 6


def held_acts_line(query: str, results: List[dict], detected_act: Optional[str] = None) -> str:
    """Names the held Acts that match this question, so that the model does not
    say "I don't hold" an Act it holds but did not retrieve (round 2, item 2).
    The Acts retrieved are not listed (they are often unrelated, and their
    headings are in the excerpts); the line only says they are held."""
    titles = []
    for title in titles_for_base_name(detected_act) + held_acts_for_query(query):
        if title not in titles:
            titles.append(title)
    titles = titles[:MAX_HELD_LINE_ACTS]
    if titles:
        line = (f"ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: {'; '.join(titles)}. If the answer "
                "lies in one of these and its section is not in the excerpts below, say you hold "
                "the Act but its section was not among those you pulled; do not say you don't hold it.")
    else:
        line = ("ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: none. No held Act matched this "
                "question by name or keyword; the Act may or may not be held, check the list "
                "in your instructions.")
    if results:
        line += " Every Act in the excerpts below is held."
    return line


def build_repeal_notes(query: str) -> str:
    """Notes for any wholly repealed Act the question names (empty if none)."""
    titles = detect_repealed_mentions(query)
    if not titles:
        return ""
    return "\n".join(f"REPEAL NOTE: {repealed_note(t)}" for t in titles)


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

LEGISLATION EXCERPTS FROM DATABASE (the only source of law you may use for this answer):
{context}
{reference_section}{attachment_section}
Answer the user's question using only:
1. The legislation excerpts above, for every statement of what the law is: rules, section numbers, time limits, amounts, rates, entitlements, duties and offences.
2. The curated scholarly references (if provided), for historical context and case law background only, never as a source of a section.
3. The uploaded document text (if provided): analyse it against the excerpts. It is not itself an excerpt.

If the excerpts do not govern the question, do not answer it from memory. Name the Act that probably governs it if you know it; if it is on the list of Acts you hold or in the ACTS BOWEN HOLDS line above, say that you hold it but the relevant section was not among the sections you pulled for this answer, and say that you do not hold it only if it is not on that list; point to legislation.govt.nz and Community Law (communitylaw.org.nz), and stop. Do not summarise or characterise what the Act says "in general terms", do not name its Parts or sections (other than to say that a section the person asked about was not among the sections you pulled), do not state any entitlement, rate, test or liability even with a disclaimer, and give no other phone number or organisation (except the safety helplines).

Do not say or guess what any section, Part, Schedule or clause contains unless its own text is in the excerpts above; that holds in a partial answer too. Your earlier answers in this conversation are not excerpts.

If the user asks why you could not find or retrieve something, reply with the fixed sentence in rule 9 of your instructions, and nothing about how you search or what you were given.

Put words in quotation marks only if they appear word for word in an excerpt above. If the user's question contains quoted legal text, that is text THEY are asking about, not an official excerpt.

If the person may be in danger or distress, give the safety help from your instructions first.

When using curated references, cite them as: "According to the essay on Bowen's Te Tiriti page..." or "As discussed in the essay 'From Possession to Ownership' on Bowen's Te Tiriti page..." Never attribute the essay to a named individual.

Provide information, not legal advice. End with the SOURCES line: the excerpts you relied on, as "Act title s section" entries separated by "; ", or "SOURCES: none"."""

    # Increase max_tokens when attachments are present; thinking needs room on top.
    has_attachments = bool(attachment_context or image_blocks)
    max_tokens = (2500 if has_attachments else 1750) + THINKING_TOKEN_HEADROOM

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


# =============================================================================
# Sources the answer used (not sources retrieved)
# =============================================================================
# The model ends every answer with one line:
#     SOURCES: Residential Tenancies Act 1986 s 18; Residential Tenancies Act 1986 s 42B
# or "SOURCES: none". finalise_answer() strips that line, keeps only the entries
# that name a retrieved excerpt (searched, or fetched by Claude with
# fetch_section; the endpoints pass both), and is the single post-processing step for both
# /chat and /chat/stream. SourcesLineFilter keeps the line from ever reaching a
# streaming client.

# Neutral on held/not held: the backend cannot tell which it was, and "I don't
# hold the Act" was being read at face value for Acts that are held (round 2,
# item 2). Not held implies not retrieved, so this is true either way.
NOT_HELD_FOOTER = (
    "I haven't stated the rule here because the legislation text that governs this "
    "question wasn't among the sections I pulled for this answer. You can read the current "
    "law at legislation.govt.nz, and Community Law (communitylaw.org.nz) offers free legal help."
)

_FOOTER_HELP = (
    "You can read the current law at legislation.govt.nz, and Community Law "
    "(communitylaw.org.nz) offers free legal help."
)


def footer_acts(query: str, detected_act: Optional[str] = None) -> List[str]:
    """Held Acts the footer may name: the question's strong matches only, since
    the backend asserts these in its own voice."""
    titles = titles_for_base_name(detected_act)
    titles += [t for t in held_acts_for_query(query, include_weak=False) if t not in titles]
    return titles[:2]


def not_held_footer(held_titles=()) -> str:
    """NOT_HELD_FOOTER, or, when the backend knows the question's held Acts, a
    footer that says they are held and the section was not retrieved."""
    if not held_titles:
        return NOT_HELD_FOOTER
    acts = " and the ".join(held_titles)
    # Same wording as the prompt's (AVAILABLE ACTS, rule 2), with its next step.
    return (f"I hold the {acts}, but the section that deals with this question wasn't among "
            f"the sections I pulled for this answer, so I haven't stated the rule here. If you "
            f"know the section number, ask me about it by number and I'll fetch it. {_FOOTER_HELP}")

# "SOURCES:" at the start of a line, optionally wrapped in markdown emphasis.
_EMPHASIS = r"(?:\*\*|\*|__|_)?"
_SOURCES_LINE_RE = re.compile(r"^" + _EMPHASIS + r"sources" + _EMPHASIS + r":(.*)$", re.IGNORECASE)
# Every line-start form _SOURCES_LINE_RE accepts, lower-cased, for the stream filter.
_EMPHASIS_FORMS = ("", "*", "**", "_", "__")
SOURCES_MARKERS = tuple(
    f"\n{a}sources{b}:" for a in _EMPHASIS_FORMS for b in _EMPHASIS_FORMS
)
_MAX_MARKER_LEN = max(len(m) for m in SOURCES_MARKERS)

# Splits "Residential Tenancies Act 1986 s 42B" into title and section.
_ENTRY_SPLIT_RE = re.compile(
    r"^(?P<title>.+?)[\s,]+(?:ss?|sections?|sec)\.?(?:\s+|(?=\d))(?P<section>\S.*)$",
    re.IGNORECASE,
)
_ENTRY_SCHEDULE_RE = re.compile(r"^(?P<title>.+?)[\s,]+(?P<section>(?:schedule|sch)\b.*)$", re.IGNORECASE)


def _norm_title(title: str) -> str:
    return " ".join((title or "").lower().replace("\u2019", "'").split())


def _norm_section(section: str) -> str:
    sec = " ".join((section or "").strip().lower().split())
    sec = re.sub(r"^(?:sections?|ss?|sec)\.?\s*(?=[0-9a-z])", "", sec)
    return sec.strip(" .,;")


def _titles_match(listed: str, retrieved: str) -> bool:
    a, b = _norm_title(listed), _norm_title(retrieved)
    if not a or not b:
        return False
    if a == b:
        return True
    # Containment either way ("Privacy Act" vs "Privacy Act 2020"), but not on
    # a fragment too short to identify an Act.
    shorter = a if len(a) <= len(b) else b
    return len(shorter) >= 8 and (a in b or b in a)


def _parse_sources_entries(payload: str) -> list[tuple[str, str]]:
    payload = payload.strip().strip("*_").strip()
    if not payload or payload.lower().rstrip(".") in ("none", "n/a", "nil"):
        return []
    entries = []
    for raw in payload.split(";"):
        raw = raw.strip().strip("*_").strip().rstrip(".")
        if not raw:
            continue
        m = _ENTRY_SPLIT_RE.match(raw) or _ENTRY_SCHEDULE_RE.match(raw)
        if m:
            entries.append((m.group("title").strip(" ,"), m.group("section").strip()))
    return entries


def _split_sources_line(response_text: str) -> tuple[str, Optional[list[tuple[str, str]]]]:
    """Remove every SOURCES line. Returns (body, entries); entries is None when
    the model wrote no SOURCES line at all. The last SOURCES line wins."""
    lines = (response_text or "").split("\n")
    kept, payload = [], None
    for line in lines:
        m = _SOURCES_LINE_RE.match(line.strip()) if line[:1] not in (" ", "\t") else None
        if m:
            payload = m.group(1)
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    body = "\n".join(kept).rstrip()
    return body, (None if payload is None else _parse_sources_entries(payload))


def _source_from_result(r: dict) -> dict:
    text = r.get("text", "") or ""
    return {
        "act_title": r["act_title"],
        "section_number": (r.get("section_number") or "").strip(),
        "section_heading": r.get("section_heading") or "General Provisions",
        "url": r.get("section_url") or r.get("act_url") or "",
        "excerpt": text[:200] + "..." if len(text) > 200 else text,
        "score": float(r.get("score", 0.0)),
    }


def _match_sources(entries: list[tuple[str, str]], results: List[dict]) -> list[dict]:
    """Listed entries that name a retrieved result, in the model's order, deduped."""
    retrievable = [r for r in results if (r.get("section_number") or "").strip()]
    cap = len({(r["act_title"], _norm_section(r["section_number"])) for r in retrievable})
    sources, seen = [], set()
    for title, section in entries:
        want = _norm_section(section)
        for r in retrievable:
            if _norm_section(r["section_number"]) == want and _titles_match(title, r["act_title"]):
                key = (r["act_title"], want)
                if key not in seen:
                    seen.add(key)
                    sources.append(_source_from_result(r))
                break
        if len(sources) >= cap:
            break
    return sources


def _needs_not_held_footer(body: str, sources: list, is_legal_query: bool) -> bool:
    if not is_legal_query or sources:
        return False
    low = body.lower()
    # The model's own not-held answer names both; a bare sign-off ("verify at
    # legislation.govt.nz") does not count, or the gate would never fire on a
    # first answer.
    return not ("legislation.govt.nz" in low and "community law" in low)


def _finalise(response_text: str, results: List[dict], is_legal_query: bool, held_titles=()):
    """(body, footer, sources). body has the SOURCES line removed; footer is
    not_held_footer(held_titles) or ""."""
    body, entries = _split_sources_line(response_text)
    sources = _match_sources(entries, results) if entries else []
    footer = not_held_footer(held_titles) if _needs_not_held_footer(body, sources, is_legal_query) else ""
    return body, footer, sources


def _join_footer(body: str, footer: str) -> str:
    if not footer:
        return body
    return f"{body}\n\n{footer}" if body else footer


def finalise_answer(response_text: str, results: List[dict], is_legal_query: bool,
                    held_titles=()) -> tuple[str, list[dict]]:
    """Shared post-processing for /chat and /chat/stream.

    Returns (clean_text, sources). clean_text has the SOURCES line stripped and,
    for a legal question with no usable source, the not-held footer appended.
    sources are the retrieved excerpts the model listed, in its order, deduped,
    each in the Source shape. A missing SOURCES line gives no sources: the
    retrieval hits are never shown as if the answer had used them.
    """
    body, footer, sources = _finalise(response_text, results, is_legal_query, held_titles)
    return _join_footer(body, footer), sources


class SourcesLineFilter:
    """Streams text through while withholding the SOURCES line.

    Any suffix of the unsent text that could be the start of a SOURCES marker
    (at most len("\n**sources**:") - 1 characters), plus any trailing
    whitespace, is held back until the next chunk decides it. Once a marker is
    seen nothing more is emitted; text that follows the SOURCES line, if any,
    is recovered by stream_tail() after finalise_answer has run.
    """

    def __init__(self):
        self.parts: list[str] = []
        self.emitted = ""
        self._pending = ""
        self.stopped = False

    @property
    def full_text(self) -> str:
        return "".join(self.parts)

    @staticmethod
    def _held_suffix_len(low: str) -> int:
        for k in range(min(len(low), _MAX_MARKER_LEN - 1), 0, -1):
            tail = low[-k:]
            if any(m.startswith(tail) for m in SOURCES_MARKERS):
                return k
        return 0

    def feed(self, chunk: str) -> str:
        self.parts.append(chunk)
        if self.stopped or not chunk:
            return ""
        self._pending += chunk
        # The start of the stream counts as a line start.
        lead = "" if self.emitted else "\n"
        text = lead + self._pending
        low = text.lower()
        hits = [i for i in (low.find(m) for m in SOURCES_MARKERS) if i >= 0]
        if hits:
            cut = min(hits)
            self.stopped = True
        else:
            cut = len(text) - self._held_suffix_len(low)
        # Trailing whitespace is also held: it is invisible until real text
        # follows, and finalise_answer strips it before the SOURCES line.
        while cut > len(lead) and text[cut - 1].isspace():
            cut -= 1
        out = text[len(lead):max(cut, len(lead))]
        self._pending = self._pending[len(out):]
        self.emitted += out
        return out


def stream_tail(body: str, footer: str, emitted: str) -> str:
    """What the client still needs after the stream ends so that it ends up
    with finalise_answer's text: held-back text that was not a marker, any text
    after the SOURCES line, and the not-held footer."""
    tail = ""
    if body.startswith(emitted):
        tail = body[len(emitted):]
    elif body.startswith(emitted.rstrip()):
        tail = body[len(emitted.rstrip()):]
    if footer:
        tail += f"\n\n{footer}"
    return tail


async def generate_response(
    query: str,
    context: str,
    reference_context: str = "",
    session_id: str = "",
    attachment_context: str = "",
    image_blocks: list | None = None,
    fetched: Optional[list] = None,
) -> str:
    """Generate response using Claude (non-streaming). When fetched is a list
    (legal questions), Claude is offered fetch_section and each section it
    fetches is appended to that list."""
    if not anthropic_client:
        raise_anthropic_unavailable()

    messages, max_tokens = _build_claude_messages(
        query, context, reference_context, session_id,
        attachment_context, image_blocks,
    )

    # History is stored by the endpoint, after finalise_answer, so that it holds
    # the clean text (no SOURCES line). Under BOWEN_STUB_LLM the client is the
    # offline stub, which answers with STUB_RESPONSE.
    fetch = _FetchState(fetched) if fetched is not None else None
    parts = []
    try:
        for piece in _answer_rounds(messages, max_tokens, fetch, streaming=False):
            if piece is REFUSED:
                return REFUSED
            if isinstance(piece, FetchStatus):
                continue
            parts.append(piece)
    except Exception as e:
        logger.error(LogEvent.CLAUDE_ERROR, f"Claude API error: {e}", error=e)
        raise_generation_failed(str(e))
    return "".join(parts)


async def generate_response_stream(
    query: str,
    context: str,
    reference_context: str = "",
    session_id: str = "",
    attachment_context: str = "",
    image_blocks: list | None = None,
    fetched: Optional[list] = None,
):
    """Streaming variant of generate_response. Yields text chunks as they
    arrive, and a FetchStatus when a fetch runs (see _answer_rounds for what
    is held back around a fetch)."""
    if not anthropic_client:
        raise_anthropic_unavailable()

    # Reuse the same message-building logic
    messages, max_tokens = _build_claude_messages(
        query, context, reference_context, session_id,
        attachment_context, image_blocks,
    )

    # As in generate_response, the endpoint stores history after finalising.
    # text_stream carries text deltas only, so thinking never reaches the client.
    fetch = _FetchState(fetched) if fetched is not None else None
    try:
        for piece in _answer_rounds(messages, max_tokens, fetch, streaming=True):
            yield piece
    except Exception as e:
        logger.error(LogEvent.CLAUDE_ERROR, f"Claude API error: {e}", error=e)
        raise


def _claude_round(request: dict, streaming: bool):
    """One Claude call. Yields the text as it arrives and returns the final
    message (read it with `message = yield from _claude_round(...)`)."""
    if streaming:
        with anthropic_client.beta.messages.stream(**request) as stream:
            for text in stream.text_stream:
                yield text
            return stream.get_final_message()
    message = anthropic_client.beta.messages.create(**request)
    # A response can open with thinking blocks; the answer is the text blocks.
    for block in message.content:
        if block.type == "text":
            yield block.text
    return message


def _last_fallback_index(content) -> int:
    return max((i for i, b in enumerate(content) if b.type == "fallback"), default=-1)


def _echo_content(content) -> list:
    """The assistant turn as it is sent back for the next round: unchanged,
    except that after a mid-output fallback the declined model's thinking and
    tool_use blocks before the last fallback block are left out (its text and
    the fallback block itself stay where they were)."""
    last = _last_fallback_index(content)
    return [b for i, b in enumerate(content) if i >= last or b.type in ("text", "fallback")]


def _answer_rounds(messages: list, max_tokens: int, fetch: Optional[_FetchState], streaming: bool):
    """The Claude call, with fetch_section rounds when `fetch` is given (legal
    questions). Yields the text the user sees, a FetchStatus after each fetch
    round that found a section, then REFUSED if the whole fallback chain
    declined. Shared by /chat and /chat/stream so both give the
    same answer.

    While Claude may still fetch, a round's text is held back; if the round
    ends in a fetch before FETCH_COMMIT_CHARS arrive, that text is dropped
    (Claude was told to fetch before writing), so nothing shown is later
    contradicted by a section it then read. Once text has been shown, any
    further fetch is declined and the next request may not call the tool. The
    same holds after MAX_TOOL_ROUNDS rounds or MAX_FETCHED_SECTIONS fetches:
    the request is sent with tool_choice none, so Claude must answer.
    `messages` is extended in place with each round's turns."""
    rounds, shown = 0, False
    while True:
        may_fetch = (fetch is not None and rounds < MAX_TOOL_ROUNDS
                     and not shown and not fetch.full)
        request = _claude_request(messages, max_tokens, tools=fetch is not None,
                                  allow_tool_calls=may_fetch)
        held, released = [], False
        gen = _claude_round(request, streaming)
        while True:
            try:
                piece = next(gen)
            except StopIteration as stop:
                message = stop.value
                break
            if not piece:
                continue
            if may_fetch and not released:
                held.append(piece)
                if sum(len(p) for p in held) >= FETCH_COMMIT_CHARS:
                    released = True
                    yield "".join(held)
                    held = []
            else:
                released = True
                yield piece
        if _check_stop(message):
            yield REFUSED
            return
        last = _last_fallback_index(message.content)
        calls = [b for b in message.content[last + 1:] if b.type == "tool_use"]
        if not (may_fetch and message.stop_reason == "tool_use" and calls):
            if held:
                yield "".join(held)
            return
        if released:
            shown = True
            results = [_tool_result(b, "Not fetched: you had already begun the answer. Finish it "
                                       "from the excerpts you have.", error=True) for b in calls]
        else:
            if held:
                logger.info(LogEvent.SEARCH, "Text written before a fetch was not shown",
                            chars=sum(len(p) for p in held))
            before = len(fetch.found)
            results = [fetch.run(b) for b in calls]
            status = fetch_status_text(fetch.found[before:])
            if status:
                yield FetchStatus(status)
        messages.append({"role": "assistant", "content": _echo_content(message.content)})
        messages.append({"role": "user", "content": results})
        rounds += 1


def _claude_request(messages: list, max_tokens: int, tools: bool = False,
                    allow_tool_calls: bool = True) -> dict:
    """Arguments for client.beta.messages.create/stream, the same for both paths.
    tools offers fetch_section; once the tool has been offered it stays in the
    request (the history holds its calls), and allow_tool_calls=False sets
    tool_choice none so that this request must answer."""
    request = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "output_config": {"effort": CLAUDE_EFFORT},
        "betas": [FALLBACK_BETA],
        "fallbacks": CLAUDE_FALLBACKS,
    }
    if tools:
        request["tools"] = [FETCH_SECTION_TOOL]
        if not allow_tool_calls:
            request["tool_choice"] = {"type": "none"}
    return request


def _check_stop(message) -> bool:
    """True if every model in the fallback chain declined. Logs a decline and a
    reply cut off at max_tokens."""
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        logger.warning(LogEvent.CLAUDE_ERROR, "Claude declined the request",
                       model=getattr(message, "model", None),
                       category=getattr(details, "category", None))
        return True
    if message.stop_reason == "max_tokens":
        logger.warning(LogEvent.CLAUDE_ERROR, "Claude reply cut off at max_tokens",
                       model=getattr(message, "model", None))
    return False


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
    query: str,
    response: str,
    detected_act: str,
    sources_count: int,
    response_time_ms: int,
    extra: Optional[dict] = None,
):
    """Log query to JSON file. No IP address or other network identifier is recorded.

    extra holds optional fields, present only when the step ran: "planner"
    (planner.CallStats.as_log(), plus "plan" when it added to the search),
    "fetched" ([{act, section}] Claude fetched), "second_opinion"
    (second_opinion.verdict_log_fields) and "web_context" (web_context.log_fields).
    None of them carries an API key. They never replace the fixed fields."""
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "query": query,
            "response": response,
            "detected_act": detected_act,
            "sources_count": sources_count,
            "response_time_ms": response_time_ms
        }
        for k, v in (extra or {}).items():
            log_entry.setdefault(k, v)

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
async def get_logs(token: str = Header(..., alias="X-Admin-Token", description="Admin token")):
    """Download query logs. Requires ADMIN_TOKEN in the X-Admin-Token header (never the URL, so it stays out of access logs)."""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    log_file = LOGS_DIR / "queries.jsonl"
    if not log_file.exists():
        return {"message": "No logs yet", "entries": []}

    entries = []
    with open(log_file, "r") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                entry.pop("ip", None)  # older entries carry one
                entries.append(entry)

    return {
        "total": len(entries),
        "entries": entries
    }


@app.get("/admin/stats")
async def get_stats(token: str = Header(..., alias="X-Admin-Token", description="Admin token")):
    """Get quick stats. Requires ADMIN_TOKEN in the X-Admin-Token header."""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    log_file = LOGS_DIR / "queries.jsonl"
    if not log_file.exists():
        return {"total_queries": 0, "total_sessions": 0, "top_acts": {}, "by_month": {}}

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

    # Counts by month (UTC, from the entry timestamp). Aggregates only.
    month_queries = {}
    month_sessions = {}
    all_sessions = set()
    for e in entries:
        month = (e.get("timestamp") or "")[:7] or "unknown"
        month_queries[month] = month_queries.get(month, 0) + 1
        sid = e.get("session_id")
        if sid:
            month_sessions.setdefault(month, set()).add(sid)
            all_sessions.add(sid)
    by_month = {
        m: {"queries": month_queries[m], "sessions": len(month_sessions.get(m, ()))}
        for m in sorted(month_queries)
    }

    return {
        "total_queries": len(entries),
        "total_sessions": len(all_sessions),
        "top_acts": top_acts,
        "by_month": by_month
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
    r'\bfalse\s+(?:claim|advertis|represent)\w*|'

    # Testing gate (2026-11-01), C6: "post intimate photos of my ex online"
    # fell through the gate, so no search ran and the answer came from memory.
    r'\bintimate\b|'
    r'\bphotos?\b|'
    r'\bimages?\b|'

    # Round 2 (2 Nov): "House seperation and unequal splits between partners"
    # fell through the gate, so no search ran and the answer said the Property
    # (Relationships) Act was not held. Misspelling included on purpose.
    r'\bsep[ae]rat(?:e|ed|ing|ion)\b|'
    r'\bsue\b)'
)

_WHY_CAN_YOU = re.compile(r"(?i)^\s*why\s+can\s+you\b")
_CAN_YOU = re.compile(r"(?i)\bcan\s+you\b")


def _is_legal_query(query: str, detected_act: str | None, session_id: str = "") -> bool:
    """Lightweight check: should we search the legislation database?

    Errs on the side of inclusion — only skips clearly casual messages.
    """
    # If an act was detected, always search
    if detected_act:
        return True

    # Naming a repealed Act is a legal question even though the Act is no
    # longer a registry signal.
    if detect_repealed_mentions(query):
        return True

    # An act filter needs strong, unambiguous evidence; deciding to *retrieve*
    # does not. Any registry keyword — including the ambiguous ones that can no
    # longer select an act on their own ("employer", "business", "charge") — is
    # enough of a legal signal to search. Without this the gate silently
    # tightens whenever detection does.
    if has_registry_signal(query):
        return True

    # A combined topic (whole words, every group) names the governing sections;
    # "I want to have a pet, but the owner has refused" (live, 2 Nov) carried no
    # other signal, so no search ran. The substring topics are not used here:
    # "password" alone would make "I forgot my password" a legal question.
    if matches_combined_topic(query):
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

    # If any legal signal word/pattern is present, search. In "Why can you not
    # retrieve them?" (12 Nov ticket, turn 4) "can you" asks about Bowen, not
    # the law, and the search returned four unrelated Acts; "Why can't you
    # find it?" never matched, so this treats the two alike.
    signal_text = _CAN_YOU.sub(" ", query) if _WHY_CAN_YOU.match(query) else query
    if _LEGAL_SIGNALS.search(signal_text):
        return True

    # Short casual messages (greetings, dev notes) — skip
    # Longer messages are more likely to contain a real question
    if len(query.split()) <= 30:
        return False

    # Default: search (err on side of inclusion)
    return True


def _act_in_play(query: str, session_id: str) -> Optional[str]:
    """The Act filter for this message, shared by /chat and /chat/stream.

    An Act the message names wins and is remembered for the session. A
    follow-up that names sections but no Act ("use sections 25(2) and 27")
    uses the Act remembered from an earlier turn; anything else gets none, as
    before, so a carried filter cannot narrow an unrelated question.
    """
    detected = detect_act_from_query(query)
    if detected:
        if session_id:
            session_acts[session_id] = detected
        return detected
    if session_id and parse_section_refs(query):
        return session_acts.get(session_id)
    return None


def _retrieve_for_query(query: str, detected_act: str | None, session_id: str, merged=None):
    """Shared by /chat and /chat/stream.

    Returns (is_legal_query, results, context, reference_context). The context
    carries a repeal note for any wholly repealed Act the question names.
    merged is the search plan's planner.MergedSearch, or None for today's search.
    """
    is_legal_query = bool(query) and _is_legal_query(query, detected_act, session_id)
    if not is_legal_query:
        return False, [], CASUAL_CONTEXT, ""

    # Retrieve 6; the answer's SOURCES line decides which are shown. The
    # held-Acts line below stays true with plan rows in the results: it names
    # only the keyword matches, and says every Act in the excerpts is held.
    results = merged_search(query, detected_act, merged, top_k=6)
    context = f"{held_acts_line(query, results, detected_act)}\n\n{build_context(results)}"
    notes = build_repeal_notes(query)
    if notes:
        context = f"{notes}\n\n{context}"
    matched_refs = find_matching_references(query)
    reference_context = build_reference_context(matched_refs)
    return True, results, context, reference_context


async def _plan_for_query(query: str, detected_act: Optional[str], session_id: str):
    """(merged, stats) for a legal question: one planner call, off the event
    loop, merged with what the keyword detection decided. (None, stats) when
    the planner is off, stubbed or fails; the search is then today's.

    The plan's Act is NOT remembered in session_acts: a remembered Act becomes
    the filter on a later section-number follow-up's own words, and the
    planner sometimes picks a wrong Act. The planner reads the last turns
    itself, so it carries the topic into a follow-up without that memory."""
    calls: list = []
    history = conversation_history.get(session_id, []) if session_id else []
    plan = await asyncio.to_thread(
        planner.plan_search, anthropic_client, query, history,
        sections_by_act=_sections_by_act(), on_call=calls.append)
    stats = calls[0] if calls else None
    if plan is None:
        return None, stats
    # Sections the user named are looked up by number only inside a detected
    # Act (search_similar); without one, the plan's own sections may cover them.
    explicit = parse_section_refs(query) if detected_act else []
    merged = planner.merge_plan(plan, detected_act, explicit)
    return merged, stats


async def _retrieve(query: str, detected_act: Optional[str], session_id: str):
    """The planner (legal questions only) and the search, for both endpoints.
    Returns (is_legal_query, results, context, reference_context, run)."""
    run = _RunLog()
    is_legal = bool(query) and _is_legal_query(query, detected_act, session_id)
    merged = None
    if is_legal:
        merged, run.planner = await _plan_for_query(query, detected_act, session_id)
        if merged is not None:
            run.plan = planner_plan_fields(merged)
    # Without a plan the call is exactly today's (tests spy on it with three arguments).
    args = (query, detected_act, session_id) + ((merged,) if merged is not None else ())
    is_legal_query, results, context, reference_context = _retrieve_for_query(*args)
    return is_legal_query, results, context, reference_context, run


def planner_plan_fields(merged) -> dict:
    return {"sections": [f"{t} s {s}" for t in merged.section_act_titles for s in merged.extra_sections],
            "search_text": merged.extra_query,
            "extra_query_act_filter": merged.extra_query_act_filter}


class _RunLog:
    """What one question's optional steps did, for the query log."""

    def __init__(self):
        self.planner = None          # planner.CallStats, or None when not called
        self.plan = None             # what the plan added to the search
        self.verdict = None          # second_opinion.Verdict
        self.web = None              # web_context.WebContext
        self.shadow = None           # the shadow-mode check's asyncio.Task, if one runs

    def fields(self, fetched: Optional[list]) -> dict:
        out: dict = {}
        if self.planner is not None and self.planner.outcome not in ("disabled", "stub"):
            out["planner"] = dict(self.planner.as_log())
            if self.plan:
                out["planner"]["plan"] = self.plan
        if fetched:
            out["fetched"] = [{"act": r["act_title"], "section": r["section_number"]} for r in fetched]
        if self.verdict is not None:
            out["second_opinion"] = second_opinion.verdict_log_fields(self.verdict)
        if self.web is not None:
            out["web_context"] = web_context.log_fields(self.web)
        return out


async def _none():
    return None


def _checker_notes(query: str, reference_context: str, excerpts: List[dict]) -> str:
    """Text other than the excerpts that Claude may rely on: repeal notes, the
    status notes of partly repealed Acts in the excerpts, curated references."""
    notes = [build_repeal_notes(query)]
    for title in dict.fromkeys(r["act_title"] for r in excerpts):
        if PARTIALLY_REPEALED_ACTS.get(title):
            notes.append(f"STATUS NOTE ({title}): {PARTIALLY_REPEALED_ACTS[title]}")
    notes.append(reference_context)
    return "\n".join(n for n in notes if n)


SECOND_LOOK_TIMEOUT_GRACE = 2.0


async def _check(query, excerpts, body, notes, cfg, session_id, run: _RunLog):
    """One second-opinion call, bounded; sets run.verdict. Never raises."""
    try:
        verdict = await asyncio.wait_for(
            second_opinion.check_answer(query, excerpts, body, notes=notes, config=cfg),
            cfg.timeout_s + SECOND_LOOK_TIMEOUT_GRACE)
    except Exception as e:   # includes the wait_for timeout; cancellation propagates
        logger.warning(LogEvent.CLAUDE_ERROR, f"Second opinion failed: {type(e).__name__}")
        verdict = None
    run.verdict = verdict
    if verdict is not None:
        second_opinion.log_verdict(verdict, session_id)
    return verdict


async def _web(query, cfg, run: _RunLog):
    """One web-context call, bounded; sets run.web. Never raises."""
    try:
        ctx = await asyncio.wait_for(web_context.fetch_web_context(query, config=cfg),
                                     cfg.timeout_s + SECOND_LOOK_TIMEOUT_GRACE)
    except Exception as e:
        logger.warning(LogEvent.CLAUDE_ERROR, f"Web context failed: {type(e).__name__}")
        ctx = None
    run.web = ctx
    return ctx


# Shadow checks run after the response has gone; references are kept here so
# the tasks are not garbage-collected before they finish.
_background: set = set()


def _in_background(coro) -> asyncio.Task:
    task = asyncio.get_running_loop().create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)
    return task


async def _drain_background():
    """Wait for every pending shadow check and its log line (tests, shutdown)."""
    while _background:
        await asyncio.gather(*list(_background), return_exceptions=True)


async def _second_look(query: str, *, is_legal_query: bool, refused: bool, has_attachments: bool,
                       excerpts: List[dict], reference_context: str, body: str, footer: str,
                       sources_count: int, session_id: str, run: _RunLog) -> tuple[str, str]:
    """After the answer is final: the second opinion and the web context.
    Returns (caution, web_block), each "" when off, skipped or failed. Never
    raises. excerpts are every excerpt Claude was shown, searched and fetched;
    body is Claude's answer without the SOURCES line and without Bowen's footer.

    What the user can see is awaited, concurrently: the check in enforce mode
    and the web context. A shadow-mode check changes nothing the user sees, so
    it is not awaited: it runs as run.shadow after the response, and the
    query-log line is written when it ends (_log_turn)."""
    try:
        so_cfg, web_cfg = SECOND_OPINION_CONFIG, WEB_CONTEXT_CONFIG
        run_check = second_opinion.should_check(
            so_cfg, is_legal_query=is_legal_query, refused=refused, has_attachments=has_attachments)
        run_web = web_context.should_fetch(
            web_cfg, query=query, is_legal_query=is_legal_query, refused=refused,
            sources_count=sources_count, answer_text=_join_footer(body, footer))
        check = None
        if run_check:
            check = _check(query, excerpts, body, _checker_notes(query, reference_context, excerpts),
                           so_cfg, session_id, run)
            if so_cfg.mode != "enforce":
                run.shadow = _in_background(check)
                check = None
        if check is None and not run_web:
            return "", ""
        verdict, ctx = await asyncio.gather(check or _none(), _web(query, web_cfg, run) if run_web else _none())
        caution = second_opinion.caution_text(verdict, so_cfg.mode) if check is not None else ""
        return caution, web_context.render_block(ctx)
    except Exception as e:
        logger.warning(LogEvent.CLAUDE_ERROR, f"Second look failed: {type(e).__name__}")
        return "", ""


def _log_turn(run: _RunLog, fetched: Optional[list], **fields):
    """log_query now, or, while a shadow check is still running, when it ends
    (so its verdict is in the same line). response_time_ms is the user's wait,
    measured by the caller, not the check's."""
    def write():
        log_query(**fields, extra=run.fields(fetched))

    task = run.shadow
    if task is None or task.done():
        write()
        return

    async def after():
        try:
            await task
        except BaseException:
            pass
        write()

    _in_background(after())


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

    # Detect if asking about specific Act (or carry it into a section follow-up)
    detected_act = _act_in_play(query, session_id)

    # Log incoming request
    logger.log_chat_request(session_id, len(query), detected_act)

    # Skip retrieval for clearly non-legal casual messages
    # Attachment-only messages (empty query) skip retrieval — Claude analyses the document directly
    is_legal_query, results, context, reference_context, run = await _retrieve(
        query, detected_act, session_id
    )

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

    # Generate response. On a legal question Claude may fetch sections too;
    # they join the search results as sources the SOURCES line can name.
    fetched = [] if is_legal_query else None
    raw_text = await generate_response(
        query, context, reference_context, session_id,
        attachment_context=attachment_context.strip(),
        image_blocks=image_blocks if image_blocks else None,
        fetched=fetched,
    )

    # Sources are the retrieved excerpts the answer says it used, nothing else.
    # A declined request gets the fixed message, no sources and no footer.
    excerpts = results + (fetched or [])
    refused = raw_text is REFUSED
    if refused:
        response_text, source_dicts, shown = REFUSAL_MESSAGE, [], REFUSAL_MESSAGE
    else:
        body, footer, source_dicts = _finalise(raw_text, excerpts, is_legal_query,
                                               footer_acts(query, detected_act))
        response_text = _join_footer(body, footer)
        # The second opinion and the web context: a caution line (enforce mode
        # only) and a labelled web block after the answer. Neither is stored in
        # history, and web links are never sources.
        caution, web_block = await _second_look(
            query, is_legal_query=is_legal_query, refused=False, has_attachments=has_attachments,
            excerpts=excerpts, reference_context=reference_context, body=body, footer=footer,
            sources_count=len(source_dicts), session_id=session_id, run=run)
        shown = _join_footer(_join_footer(response_text, caution), web_block)
    sources = [Source(**d) for d in source_dicts]
    _store_history(session_id, query, response_text)

    # Calculate response time
    response_time_ms = int((time.time() - start_time) * 1000)

    # Log query to JSON file
    _log_turn(
        run, fetched,
        session_id=session_id,
        query=query,
        response=shown,
        detected_act=detected_act,
        sources_count=len(sources),
        response_time_ms=response_time_ms,
    )

    # Log response metrics
    logger.log_chat_response(session_id, response_time_ms, len(sources), success=True)

    return ChatResponse(
        response=shown,
        sources=sources,
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
    detected_act = _act_in_play(query, session_id)
    logger.log_chat_request(session_id, len(query), detected_act)

    is_legal_query, results, context, reference_context, run = await _retrieve(
        query, detected_act, session_id
    )

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

    async def event_stream():
        filt = SourcesLineFilter()
        refused = False
        fetched = [] if is_legal_query else None
        try:
            async for chunk in generate_response_stream(
                query, context, reference_context, session_id,
                attachment_context=attachment_context.strip(),
                image_blocks=image_blocks if image_blocks else None,
                fetched=fetched,
            ):
                if chunk is REFUSED:
                    refused = True
                    continue
                if isinstance(chunk, FetchStatus):
                    # Only before the first token (a fetch is declined once
                    # text has been shown); the client shows it until then.
                    yield f"data: {json.dumps({'type': 'status', 'text': chunk.text})}\n\n"
                    continue
                out = filt.feed(chunk)
                if out:
                    yield f"data: {json.dumps({'type': 'token', 'text': out})}\n\n"

            body = footer = ""
            if refused:
                # Fixed message, no sources, no footer. A partial answer already
                # streamed cannot be withdrawn (the client has no such event), so
                # the message follows it; history keeps the message alone.
                sources = []
                response_text = REFUSAL_MESSAGE
                tail = f"\n\n{REFUSAL_MESSAGE}" if filt.emitted else REFUSAL_MESSAGE
            else:
                # Same post-processing as /chat: strip the SOURCES line, keep only
                # the retrieved excerpts the answer used, add the not-held footer.
                body, footer, sources = _finalise(filt.full_text, results + (fetched or []),
                                                  is_legal_query, footer_acts(query, detected_act))
                tail = stream_tail(body, footer, filt.emitted)
                response_text = _join_footer(body, footer)
            if tail:
                yield f"data: {json.dumps({'type': 'token', 'text': tail})}\n\n"
            _store_history(session_id, query, response_text)

            # Send sources and disclaimer now; the sources box shows at once.
            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'disclaimer': DISCLAIMER})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            return

        # After "done": the caution line (enforce mode) and the web block, as
        # one more token. The client appends tokens that arrive after "done".
        # This part never sends an "error" event: the client would delete the
        # question and the answer already on screen.
        shown = response_text
        try:
            if not refused:
                caution, web_block = await _second_look(
                    query, is_legal_query=is_legal_query, refused=False,
                    has_attachments=has_attachments, excerpts=results + (fetched or []),
                    reference_context=reference_context, body=body, footer=footer,
                    sources_count=len(sources), session_id=session_id, run=run)
                extra_tail = "\n\n".join(x for x in (caution, web_block) if x)
                if extra_tail:
                    shown = _join_footer(_join_footer(response_text, caution), web_block)
                    yield f"data: {json.dumps({'type': 'token', 'text': chr(10) * 2 + extra_tail})}\n\n"
        except Exception as e:
            logger.warning(LogEvent.CLAUDE_ERROR, f"Stream tail failed: {type(e).__name__}")
        finally:
            # Logged here so that a client leaving during the tail still logs the turn.
            response_time_ms = int((time.time() - start_time) * 1000)
            _log_turn(
                run, fetched,
                session_id=session_id, query=query,
                response=shown, detected_act=detected_act,
                sources_count=len(sources), response_time_ms=response_time_ms,
            )
            logger.log_chat_response(session_id, response_time_ms, len(sources), success=True)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    conversation_history.pop(session_id, None)
    session_acts.pop(session_id, None)
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

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
# Public site URL used for Checkout success/cancel redirects. Falls back to the
# request Origin (if it is an allowed CORS origin), then the local dev frontend.
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    print(f"[BOOT] Stripe configured ({'live' if STRIPE_SECRET_KEY.startswith('sk_live_') else 'test'} mode)", flush=True)
else:
    print("[BOOT] Stripe NOT configured — STRIPE_SECRET_KEY missing; donations disabled", flush=True)


def _stripe_ready() -> bool:
    return bool(stripe and STRIPE_SECRET_KEY)


def _frontend_base(request: Request) -> str:
    if FRONTEND_URL:
        return FRONTEND_URL
    origin = request.headers.get("origin", "").rstrip("/")
    if origin and origin in CORS_ORIGINS:
        return origin
    return "http://localhost:3005"

class DonateRequest(BaseModel):
    amount: int = Field(..., ge=1, le=10000, description="Donation amount in NZD")

@app.post("/api/donate/checkout")
async def create_checkout_session(req: DonateRequest, request: Request):
    """Create a Stripe Checkout Session for a one-time donation."""
    if not _stripe_ready():
        raise HTTPException(status_code=503, detail="Donations are not configured on this server")
    base = _frontend_base(request)
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
            submit_type="donate",
            metadata={"source": "bowenpublic-donate-page", "amount_nzd": str(req.amount)},
            success_url=f"{base}/donate?success=true",
            cancel_url=f"{base}/donate",
        )
        return {"url": session.url}
    except stripe.StripeError as e:
        print(f"[DONATION] Checkout session creation failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail="Payment provider error; please try again")

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    if not _stripe_ready() or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhooks are not configured on this server")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # construct_event has verified the signature; stripe-python v8+ StripeObjects
    # lack dict .get(), so read the verified raw payload as a plain dict.
    data = json.loads(payload)
    if data.get("type") == "checkout.session.completed":
        session = data["data"]["object"]
        amount = (session.get("amount_total") or 0) / 100
        currency = (session.get("currency") or "nzd").upper()
        print(f"[DONATION] {amount:.2f} {currency} received — session {session.get('id')} "
              f"(livemode={data.get('livemode')})", flush=True)

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