"""Second opinion: an OpenAI model checks Claude's finished answer against the
excerpts Claude was shown (option [C] in docs/2026-11-13-LLM-FLOW.md).

Claude stays the only writer. This module never rewrites the answer: it returns
a Verdict, which the caller logs (shadow mode) or turns into one fixed caution
line appended after the answer (enforce mode).

Vendor API (confirmed 2026-11-13 from developers.openai.com: the models page,
guides/structured-outputs and guides/reasoning)
-----------------------------------------------------------------------------
POST https://api.openai.com/v1/responses, header "Authorization: Bearer <key>".
Request: {"model", "instructions", "input", "text": {"format": {"type":
"json_schema", "name", "schema", "strict": true}}, "reasoning": {"effort"},
"max_output_tokens", "store": false}.
Response: "status" ("completed" / "incomplete"), "output": [ {"type":
"reasoning", ...}, {"type": "message", "content": [{"type": "output_text",
"text": "<json>"} | {"type": "refusal", "refusal": "..."}]} ], "usage":
{"input_tokens", "output_tokens", ...}.
Default model gpt-6.1-sol ("balances intelligence and cost"; it does not accept
reasoning effort "none" or "minimal", so the default effort is "low").
Not confirmed from the docs fetched: the "store" field (it is a long-standing
Responses API field, set false so OpenAI does not keep the user's question).

Environment
-----------
OPENAI_API_KEY                  the key; missing, empty or "your-..." means off
BOWEN_SECOND_OPINION            off | shadow | enforce. Default: shadow when a
                                key is present, off otherwise. A mode other than
                                off without a key is off.
BOWEN_SECOND_OPINION_MODEL      default gpt-6.1-sol
BOWEN_SECOND_OPINION_EFFORT     default low (reasoning.effort)
BOWEN_SECOND_OPINION_TIMEOUT    seconds, default 8

How main.py calls it (wired 13 Nov 2026 in main._second_look)
------------------------------------------
check_answer() is ASYNC and uses httpx.AsyncClient, so it never blocks the event
loop and can run concurrently with web_context.fetch_web_context() through
asyncio.gather(). (The existing Anthropic client is sync and blocks the loop
while Claude writes; this call starts only after Claude has finished, so that
does not matter here, but a sync httpx call would block every other request
for up to 8 s.) It never raises and returns None on any failure.

Shared preparation (both endpoints), after finalise_answer / _finalise and only
when the answer is not REFUSED:

    cfg = second_opinion.load_config()          # once, at startup
    second_opinion.log_startup(cfg)             # in startup(): one log line
    ...
    run_check = second_opinion.should_check(cfg, is_legal_query=is_legal_query,
                                            refused=raw_text is REFUSED,
                                            has_attachments=has_attachments)
    excerpts = second_opinion.excerpts_from_results(results)
    notes = "\n".join(filter(None, [build_repeal_notes(query), reference_context]))
    # plus any PARTIALLY_REPEALED_ACTS status note for the Acts in results

Check `body` (the answer with the SOURCES line removed) and NOT the backend's
not-held footer, the caution line or the web block: those are Bowen's fixed
text, not Claude's claims. Skip attachments: the attachment is never sent to
OpenAI, so statements about it could not be judged.

/chat (non-stream):
    body, footer, sources = _finalise(raw_text, results, is_legal_query, held)
    verdict = await second_opinion.check_answer(query, excerpts, body, notes=notes,
                                                config=cfg) if run_check else None
    (or gather it with web_context.fetch_web_context(query) - see that module)
    second_opinion.log_verdict(verdict, session_id)          # shadow and enforce
    caution = second_opinion.caution_text(verdict, cfg.mode) # "" unless enforce
    response_text = _join_footer(body, footer)
    shown = _join_footer(response_text, caution)              # what the user sees
    _store_history(session_id, query, response_text)          # history WITHOUT caution
    log_query(..., response=shown) and add second_opinion.verdict_log_fields(verdict)
    as an extra field when log_query grows one.

/chat/stream: the answer is already on screen before the check can finish, so
the caution line is a tail, sent after the existing stream_tail:
    yield token(tail)                           # existing: rest of body + footer
    yield done(sources, disclaimer)             # existing: send it now, see below
    verdict = await check_answer(...)           # or gather with web context
    caution = caution_text(verdict, cfg.mode)
    if caution: yield token("\n\n" + caution)
    history: response_text without the caution, as in /chat.
Reading frontend/src/hooks/useChat.ts (not run): onToken appends to the last
assistant message whenever a token arrives, including after "done", and the
stream stays open (isLoading) until the server closes it. So the backend can
send "done" first (the sources box appears at once) and the caution after it.
Never emit an "error" event in this tail: onError removes the user's question
and the whole answer from the screen. Wrap the tail in its own try/except that
logs and yields nothing. If the founder prefers the caution before the sources
box, send it before "done" instead; the sources then wait up to the timeout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Sequence

import httpx

log = logging.getLogger("bowen.second_opinion")

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_EFFORT = "low"
DEFAULT_TIMEOUT_S = 8.0
MAX_OUTPUT_TOKENS = 4000
MAX_ISSUES = 8
MAX_REASON_CHARS = 200
MIN_SENTENCE_CHARS = 12
MAX_EXCERPT_CHARS = 20000

MODES = ("off", "shadow", "enforce")

KINDS = ("unsupported_claim", "wrong_section_number", "describes_unseen_section", "misquote")

# Appended by the caller in enforce mode when the verdict has issues. Plain,
# short, says nothing about models, checks or vendors beyond "a second check".
CAUTION_LINE = (
    "A second check could not confirm every statement above against the legislation "
    "shown. Read the sections cited before relying on it."
)


# =============================================================================
# Data
# =============================================================================

@dataclass(frozen=True)
class Excerpt:
    act: str
    section: str
    text: str
    heading: str = ""


@dataclass(frozen=True)
class Issue:
    sentence: str   # copied from the answer; verified to occur in it
    kind: str       # one of KINDS
    reason: str     # one line


@dataclass(frozen=True)
class Verdict:
    ok: bool
    issues: list[Issue]
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    dropped: int = 0  # issues the model returned that failed validation


@dataclass(frozen=True)
class Config:
    mode: str
    model: str
    effort: str
    timeout_s: float
    api_key: str = field(default="", repr=False)  # never printed

    @property
    def enabled(self) -> bool:
        return self.mode != "off" and bool(self.api_key)


# =============================================================================
# Configuration
# =============================================================================

def _usable_key(value: Optional[str]) -> str:
    v = (value or "").strip()
    if not v or v.lower().startswith("your-") or v.lower().startswith("your_"):
        return ""
    return v


def load_config(environ: Mapping[str, str] = os.environ) -> Config:
    key = _usable_key(environ.get("OPENAI_API_KEY"))
    raw_mode = (environ.get("BOWEN_SECOND_OPINION") or "").strip().lower()
    if raw_mode and raw_mode not in MODES:
        log.warning("BOWEN_SECOND_OPINION=%r is not one of off|shadow|enforce; using the default",
                    raw_mode)
        raw_mode = ""
    mode = raw_mode or ("shadow" if key else "off")
    if not key:
        mode = "off"
    try:
        timeout = float(environ.get("BOWEN_SECOND_OPINION_TIMEOUT") or DEFAULT_TIMEOUT_S)
        if timeout <= 0:
            raise ValueError
    except ValueError:
        timeout = DEFAULT_TIMEOUT_S
    return Config(
        mode=mode,
        model=(environ.get("BOWEN_SECOND_OPINION_MODEL") or "").strip() or DEFAULT_MODEL,
        effort=(environ.get("BOWEN_SECOND_OPINION_EFFORT") or "").strip() or DEFAULT_EFFORT,
        timeout_s=timeout,
        api_key=key,
    )


_startup_logged = False


def log_startup(config: Config) -> None:
    """One line at startup saying whether the check is on. Logs once per process."""
    global _startup_logged
    if _startup_logged:
        return
    _startup_logged = True
    if config.enabled:
        log.info("second opinion: mode=%s model=%s effort=%s timeout=%ss",
                 config.mode, config.model, config.effort, config.timeout_s)
    else:
        log.info("second opinion: off (%s)",
                 "no OPENAI_API_KEY" if not config.api_key else "BOWEN_SECOND_OPINION=off")


def should_check(config: Config, *, is_legal_query: bool, refused: bool,
                 has_attachments: bool = False) -> bool:
    """Run the check only on a legal answer Claude actually wrote, without an
    attachment (attachments are never sent to OpenAI)."""
    return config.enabled and is_legal_query and not refused and not has_attachments


# =============================================================================
# Input shaping
# =============================================================================

def _get(d, *names, default=""):
    for n in names:
        if isinstance(d, Mapping) and d.get(n) is not None:
            return d.get(n)
        if not isinstance(d, Mapping) and getattr(d, n, None) is not None:
            return getattr(d, n)
    return default


def excerpts_from_results(results: Iterable) -> list[Excerpt]:
    """Accepts main.py result dicts (act_title, section_number, section_heading,
    text), the eval files' shape (act, section, heading, text), or Excerpt."""
    out = []
    for r in results or []:
        if isinstance(r, Excerpt):
            out.append(r)
            continue
        out.append(Excerpt(
            act=str(_get(r, "act_title", "act")),
            section=str(_get(r, "section_number", "section")).strip(),
            heading=str(_get(r, "section_heading", "heading")),
            text=str(_get(r, "text")),
        ))
    return out


CHECKER_INSTRUCTIONS = """You check an ANSWER written by a legal information chatbot about New Zealand legislation. The chatbot was told to answer ONLY from the EXCERPTS below. Your only job is to find sentences in the ANSWER that the EXCERPTS (and the NOTES, if any) do not support.

You have no knowledge of New Zealand law for this task. Judge every sentence ONLY against the EXCERPTS and NOTES you are given. If a sentence states something you believe is true law but no excerpt supports it, it is unsupported: flag it, and do not say what the law is. If a sentence states something you believe is wrong but an excerpt supports it, do NOT flag it. Never correct the law, never add law, never suggest what the answer should have said.

Flag a sentence only for one of these kinds:
- unsupported_claim: it states a rule, entitlement, duty, time limit, amount, rate, test, offence, penalty, procedure, or what an Act or the law provides or requires, or names an organisation's legal role, and no excerpt or note supports it. A fair paraphrase or a plain-language summary of an excerpt IS supported. A sound inference that applies an excerpt's words to the user's facts IS supported.
- wrong_section_number: it attributes content to a section, subsection, Schedule or clause number, but the excerpt that holds that content has a different number or belongs to a different Act.
- describes_unseen_section: it says, suggests or guesses ("may", "likely", "generally", "deals with", "covers") what a section, Part, Schedule, clause or Act contains, when that provision's own text is not among the EXCERPTS. Naming a provision only to say it was not retrieved or not shown is fine. Naming a provision the way an excerpt mentions it (for example in a heading such as "Exceptions to sections 21, 22, 24, and 26") is fine, if the sentence describes it no further than that excerpt does.
- misquote: words inside quotation marks that do not appear word for word in an excerpt. Ignore straight versus curly quotation marks and apostrophes, and ellipses marking omitted words. Quotation marks around the user's own words or the user's document are fine.

NEVER flag any of these; they are allowed and expected:
- Sign-offs and disclaimers, such as "As always, verify at legislation.govt.nz and consult a lawyer for your specific situation", "As always - verify and get advice for your situation", or saying it gives information, not legal advice.
- Any statement that a section, Part, Act or topic was not retrieved, was not shown, is not held, is not covered by what was retrieved, or that the excerpts do not say something; and "I hold the X Act but didn't retrieve the section that deals with this".
- Naming the Act that probably governs the topic, together with saying that Bowen holds it, does not hold it, or that its section was not among the sections pulled, for example "Liquor licensing is governed by the Sale and Supply of Alcohol Act 2012, which I don't hold" or "This is governed by the Employment Relations Act 2000, which I hold". Flag such a sentence only if it goes on to state what that Act provides (a rate, amount, test, duty, process, time limit or an agency's role).
- Pointers to legislation.govt.nz or to Community Law (communitylaw.org.nz) for free legal help.
- Safety help: 111, 1737, Women's Refuge 0800 733 843, Lifeline 0800 543 354, Oranga Tamariki 0508 326 459.
- Declining to help with something that would harm another person, and saying such conduct is unlawful.
- Greetings, questions back to the user, statements about the chatbot itself, and restating or explaining the user's own question or document.
- Statements that come from the NOTES (for example that an Act was repealed, when, and what replaced it).

Rules for your output:
- "sentence" must be copied character for character from the ANSWER: one whole sentence, or the shortest exact span that contains the problem. Do not fix typos, do not change punctuation, do not join text from two places.
- "reason" is one short line (at most 25 words) saying which excerpt is missing or what differs. Do not state what the law actually is.
- When in doubt, do not flag. A false alarm is worse than a miss. Most answers have no issues; then return an empty list.
- Flag each sentence at most once, with the single best kind."""


def _excerpt_block(excerpts: Sequence[Excerpt]) -> str:
    if not excerpts:
        return "(no excerpts were retrieved for this question)"
    parts = []
    for i, e in enumerate(excerpts, 1):
        head = f"[{i}] {e.act}"
        if e.section:
            head += f", section {e.section}"
        if e.heading:
            head += f" ({e.heading})"
        parts.append(f"{head}\n{(e.text or '')[:MAX_EXCERPT_CHARS]}")
    return "\n\n".join(parts)


def build_input(question: str, excerpts: Sequence[Excerpt], answer: str, notes: str = "") -> str:
    blocks = [
        "QUESTION:\n" + (question or "(none)"),
        "EXCERPTS:\n" + _excerpt_block(excerpts),
    ]
    if notes and notes.strip():
        blocks.append("NOTES:\n" + notes.strip())
    blocks.append("ANSWER:\n" + (answer or ""))
    return "\n\n=====\n\n".join(blocks)


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "reason": {"type": "string"},
                },
                "required": ["sentence", "kind", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["issues"],
    "additionalProperties": False,
}


def build_request(config: Config, question: str, excerpts: Sequence[Excerpt], answer: str,
                  notes: str = "") -> dict:
    return {
        "model": config.model,
        "instructions": CHECKER_INSTRUCTIONS,
        "input": [{"role": "user", "content": build_input(question, excerpts, answer, notes)}],
        "text": {"format": {"type": "json_schema", "name": "answer_check",
                            "schema": OUTPUT_SCHEMA, "strict": True}},
        "reasoning": {"effort": config.effort},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
    }


# =============================================================================
# Validation
# =============================================================================

_QUOTE_MAP = str.maketrans({
    "‘": "'", "’": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "‟": '"', "″": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
    "…": "...",
})


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(_QUOTE_MAP)
    s = re.sub(r"[*_`]+", "", s)          # markdown emphasis and code
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


# Whole sentences that are Bowen's fixed text: never an issue, whatever the model says.
_FIXED_SENTENCES = tuple(_norm(s) for s in (
    "As always, verify at legislation.govt.nz and consult a lawyer for your specific situation.",
    "As always - verify and get advice for your situation.",
    "As always — verify and get advice for your situation.",
    "I don't always find the section a question needs, so ask me again naming the Act and "
    "the section number, or read it at legislation.govt.nz.",
    "You can read the current law at legislation.govt.nz, and Community Law "
    "(communitylaw.org.nz) offers free legal help.",
    "I haven't stated the rule here because I didn't retrieve the legislation text that "
    "governs this question.",
    CAUTION_LINE,
))

_QUOTED_RE = re.compile(r'"([^"]{3,})"')


def _quotes_in(sentence_norm: str) -> list[str]:
    return [q.strip(" .,;:") for q in _QUOTED_RE.findall(sentence_norm)]


def _quote_is_verbatim(quote: str, excerpts_norm: str) -> bool:
    # Ellipses mark omitted words: each piece must be in the excerpts.
    pieces = [p.strip(" .,;:") for p in quote.split("...")]
    pieces = [p for p in pieces if p]
    return bool(pieces) and all(p in excerpts_norm for p in pieces)


def validate_issues(raw_issues, answer: str, excerpts: Sequence[Excerpt]) -> tuple[list[Issue], int]:
    """Keep only issues whose sentence occurs in the answer, with a known kind
    and a reason. Returns (kept, dropped_count)."""
    answer_norm = _norm(answer)
    excerpts_norm = _norm(" ".join(f"{e.heading} {e.text}" for e in excerpts))
    kept, seen, dropped = [], set(), 0
    for item in raw_issues if isinstance(raw_issues, list) else []:
        if not isinstance(item, Mapping):
            dropped += 1
            continue
        sentence = str(item.get("sentence") or "").strip()
        kind = str(item.get("kind") or "").strip()
        reason = " ".join(str(item.get("reason") or "").split())
        s_norm = _norm(sentence)
        if (kind not in KINDS or not reason or len(s_norm) < MIN_SENTENCE_CHARS
                or s_norm not in answer_norm or s_norm in _FIXED_SENTENCES or s_norm in seen):
            dropped += 1
            continue
        if kind == "misquote":
            quotes = _quotes_in(s_norm)
            # A misquote needs quoted words, at least one of them not verbatim.
            if not quotes or all(_quote_is_verbatim(q, excerpts_norm) for q in quotes):
                dropped += 1
                continue
        seen.add(s_norm)
        if len(reason) > MAX_REASON_CHARS:
            reason = reason[:MAX_REASON_CHARS - 1].rstrip() + "…"
        kept.append(Issue(sentence=sentence, kind=kind, reason=reason))
        if len(kept) >= MAX_ISSUES:
            break
    return kept, dropped


# =============================================================================
# Response parsing
# =============================================================================

def _output_text(payload: Mapping) -> Optional[str]:
    """The JSON text from a Responses API payload, or None on refusal/incomplete."""
    if payload.get("status") not in (None, "completed"):
        return None
    texts = []
    for item in payload.get("output") or []:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") == "refusal":
                return None
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if texts:
        return "".join(texts)
    top = payload.get("output_text")
    return top if isinstance(top, str) and top else None


def _usage(payload: Mapping) -> tuple[int, int]:
    u = payload.get("usage") or {}
    try:
        return int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0, 0


def parse_response(payload, answer: str, excerpts: Sequence[Excerpt], model: str,
                   latency_ms: int) -> Optional[Verdict]:
    if not isinstance(payload, Mapping):
        return None
    text = _output_text(payload)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, Mapping) or not isinstance(data.get("issues"), list):
        return None
    issues, dropped = validate_issues(data["issues"], answer, excerpts)
    tin, tout = _usage(payload)
    return Verdict(ok=not issues, issues=issues, model=str(payload.get("model") or model),
                   latency_ms=latency_ms, tokens_in=tin, tokens_out=tout, dropped=dropped)


# =============================================================================
# The call
# =============================================================================

async def check_answer(
    question: str,
    excerpts: Sequence,
    answer: str,
    *,
    notes: str = "",
    config: Optional[Config] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Optional[Verdict]:
    """Ask the checker model about `answer`. Never raises; None when off, on
    any failure, or when the model refuses or returns something unusable.

    `excerpts`: what Claude was shown (Excerpt, main.py result dicts, or the
    eval files' dicts). `notes`: other text Claude may rely on (repeal notes,
    status notes, curated Te Tiriti references). `transport` is for tests.
    """
    try:
        cfg = config or load_config()
        if not cfg.enabled:
            log_startup(cfg)
            return None
        if not (answer or "").strip():
            return None
        exs = excerpts_from_results(excerpts)
        body = build_request(cfg, question, exs, answer, notes)
        start = time.monotonic()
        async with httpx.AsyncClient(transport=transport,
                                     timeout=httpx.Timeout(cfg.timeout_s)) as client:
            resp = await asyncio.wait_for(
                client.post(API_URL, json=body,
                            headers={"Authorization": f"Bearer {cfg.api_key}"}),
                timeout=cfg.timeout_s,
            )
        latency_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code != 200:
            log.warning("second opinion: HTTP %s", resp.status_code)
            return None
        try:
            payload = resp.json()
        except ValueError:
            log.warning("second opinion: response was not JSON")
            return None
        verdict = parse_response(payload, answer, exs, cfg.model, latency_ms)
        if verdict is None:
            log.warning("second opinion: unusable response (refusal, incomplete or bad JSON)")
        return verdict
    except (asyncio.TimeoutError, httpx.TimeoutException):
        log.warning("second opinion: timed out")
        return None
    except Exception as e:  # never raise into the chat path; never log the key
        log.warning("second opinion: failed (%s)", type(e).__name__)
        return None


# =============================================================================
# Caller helpers (pure)
# =============================================================================

def caution_text(verdict: Optional[Verdict], mode: str) -> str:
    """The text to append after the answer: CAUTION_LINE in enforce mode when
    the check found issues, otherwise ""."""
    if mode == "enforce" and verdict is not None and verdict.issues:
        return CAUTION_LINE
    return ""


def verdict_log_fields(verdict: Optional[Verdict]) -> dict:
    """A JSON-safe dict for queries.jsonl. {} when no verdict."""
    if verdict is None:
        return {}
    return {
        "ok": verdict.ok,
        "model": verdict.model,
        "latency_ms": verdict.latency_ms,
        "tokens_in": verdict.tokens_in,
        "tokens_out": verdict.tokens_out,
        "dropped": verdict.dropped,
        "issues": [{"kind": i.kind, "sentence": i.sentence, "reason": i.reason}
                   for i in verdict.issues],
    }


def log_verdict(verdict: Optional[Verdict], session_id: str = "") -> None:
    """One log line per check: counts and kinds, no answer text."""
    if verdict is None:
        return
    kinds = ",".join(i.kind for i in verdict.issues) or "-"
    log.info("second opinion: session=%s ok=%s issues=%d kinds=%s dropped=%d model=%s "
             "latency_ms=%d tokens=%d/%d", (session_id or "")[:8], verdict.ok,
             len(verdict.issues), kinds, verdict.dropped, verdict.model,
             verdict.latency_ms, verdict.tokens_in, verdict.tokens_out)
