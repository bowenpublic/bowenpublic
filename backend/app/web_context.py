"""Web context: a web search adds outside context the corpus does not hold (case
law, whether an amendment is in force, a regulator's guidance), as a separate,
clearly labelled block after Claude's answer (option [D] in
docs/2026-11-13-LLM-FLOW.md).

The block is never mixed into Claude's cited answer and never becomes a source.
Only the user's question text is sent: never attachments, conversation history
or Claude's answer.

Two providers share everything (config, when to run, the call, cleaning,
rendering, logging) except request building and response parsing:
"openai" (OpenAI Responses API web_search tool, the default) and "perplexity"
(Perplexity Agent API).

OpenAI (confirmed 2026-11-13 from developers.openai.com: api/docs/guides/
tools-web-search, api/reference/resources/responses/methods/create,
api/docs/pricing, api/docs/models; then against the real API the same day)
-----------------------------------------------------------------------------
POST https://api.openai.com/v1/responses, header "Authorization: Bearer <key>".
Request: {"model", "instructions", "input": <string>, "tools": [{"type":
"web_search", "filters": {"allowed_domains": [<= 100 domains, no scheme;
subdomains included]}, "user_location": {"type": "approximate", "country":
"NZ"}, "search_context_size": "low" | "medium" | "high"}], "tool_choice":
"required" (forces a search; "auto" makes it optional), "reasoning":
{"effort"}, "max_output_tokens", "store": false}.
Response: "status" ("completed" / "incomplete"), "output": [{"type":
"reasoning", ...}, {"type": "web_search_call", "status", "action": {"type":
"search", "queries", "query"}}, {"type": "message", "phase": "final_answer",
"content": [{"type": "output_text", "text", "annotations": [{"type":
"url_citation", "url", "title", "start_index", "end_index"}]} | {"type":
"refusal", "refusal"}]}], "usage": {"input_tokens", "output_tokens", ...}.
Seen in real responses (not in the docs): the text carries each citation
inline as "([domain](url))", and the annotation's start_index/end_index (Python
string offsets) cover exactly that span; the cited URLs end in
"?utm_source=openai". tool_choice {"type": "web_search"} is accepted but
echoed back as "web_search_preview", so "required" is used. The model may also
add "[1]" markers. Search content tokens count as input tokens (about 9k per
call at search_context_size "low").
Pricing (api/docs/pricing, 13 Nov 2026): web search $10 per 1k calls plus
search content tokens at model rates; gpt-6.1-sol $2 in / $10 out per 1M
tokens.

Perplexity (confirmed 2026-11-13 from docs.perplexity.ai: api-reference/agent-post,
docs/agent-api/migrate-from-sonar/how-to, docs/agent-api/tools/web-search,
docs/agent-api/models)
-----------------------------------------------------------------------------
Sonar Chat Completions (/chat/completions, "sonar" models) lost support on
27 Sep 2026; this module uses the Agent API that replaced it.
POST https://api.perplexity.ai/v1/agent, header "Authorization: Bearer <key>".
Request: {"model": "perplexity/sonar" (provider/model form), "instructions",
"input": <string>, "tools": [{"type": "web_search", "filters":
{"search_domain_filter": [<= 20 domains]}, "max_results": 1-50,
"user_location": {"country": "NZ"}}], "max_output_tokens"}.
Response: {"id", "status", "model", "output": [{"type": "search_results",
"results": [{"id", "url", "title", "snippet", "date", ...}]}, {"type": "message",
"content": [{"type": "output_text", "text", "annotations": [{"type", "url",
"title", "start_index", "end_index"}]}]}], "usage": {"input_tokens",
"output_tokens", "total_tokens", "cost"}}. Inline "[n]" markers in the text
refer to search result id n.
Not confirmed from the docs: whether the model always searches when the
web_search tool is offered (the docs show it offered, not forced), and whether
a domain entry such as "govt.nz" also matches its subdomains (so the list names
the subdomains too). A result with no links is treated as a failure (None).

Environment
-----------
OPENAI_API_KEY                  the OpenAI key (shared with second_opinion);
                                missing, empty or "your-..." means none
PERPLEXITY_API_KEY              the Perplexity key, same rule
BOWEN_WEB_CONTEXT_PROVIDER      openai | perplexity. Default: openai when an
                                OpenAI key is usable, else perplexity when a
                                Perplexity key is, else off. Web context is on
                                only when the chosen provider's key is usable.
BOWEN_WEB_CONTEXT               off | gap | always. Default: gap when the key is
                                present, off otherwise.
BOWEN_WEB_CONTEXT_MODEL         default gpt-6.1-sol (openai) or perplexity/sonar
                                (perplexity); applies to the chosen provider
BOWEN_WEB_CONTEXT_TIMEOUT       seconds, default 20 (openai) or 12 (perplexity)
BOWEN_WEB_CONTEXT_DOMAINS       comma-separated allowlist for the search (max
                                100 for openai, 20 for perplexity); default
                                NZ_DOMAINS below; "none" searches the whole web

How main.py calls it (wired 13 Nov 2026 in main._second_look)
------------------------------------------
fetch_web_context() is ASYNC (httpx.AsyncClient), so it does not block the
event loop and can run alongside second_opinion.check_answer() with
asyncio.gather() once Claude has finished. Never raises; None on any failure.

    cfg = web_context.load_config()        # once, at startup
    web_context.log_startup(cfg)           # in startup()

/chat (non-stream), after finalise:
    body, footer, sources = _finalise(raw_text, results, is_legal_query, held)
    run_web = web_context.should_fetch(cfg, query=query, is_legal_query=is_legal_query,
                                       refused=raw_text is REFUSED,
                                       sources_count=len(sources), answer_text=body + footer)
    ctx, verdict = await asyncio.gather(
        web_context.fetch_web_context(query, config=cfg) if run_web else _none(),
        second_opinion.check_answer(...) if run_check else _none())
    response_text = _join_footer(body, footer)            # Claude + footer: history
    shown = _join_footer(response_text, caution)          # caution first (it is about the answer)
    shown = _join_footer(shown, web_context.render_block(ctx))   # web block last
    return ChatResponse(response=shown, ...); sources are unchanged (the web links
    are never Source objects).
    _store_history(session_id, query, response_text)      # NOT the web block: next
    turn Claude must not see web text as its own earlier answer.
    log_query: response=shown, plus web_context.log_fields(ctx).

/chat/stream: the web block is a tail after the answer, like stream_tail's
footer:
    yield token(stream_tail(...))          # existing
    yield done(sources, disclaimer)        # existing; can go first, see below
    ctx, verdict = await asyncio.gather(...)
    tail2 = "\n\n".join(x for x in (caution, render_block(ctx)) if x)
    if tail2: yield token("\n\n" + tail2)
Reading frontend/src/hooks/useChat.ts and src/lib/api.ts (not run): onToken
appends to the last assistant message whenever it arrives, also after "done",
and the stream stays open until the server closes it, so "done" can go first
and the sources box shows at once while the web search runs (the web block then
renders above the sources box, which sits under the message text). Never emit
an "error" event in this tail: onError deletes the question and the answer
from the screen. Wrap the tail in its own try/except that logs and yields
nothing.

Frontend rendering (frontend/src/components/ChatMessage.tsx, react-markdown
10.1.0 with no plugins): "**bold**", "_italic_", "---", "- " lists and
"[title](https://...)" links render. No remark-gfm, so bare URLs are NOT
turned into links and tables do not render. Raw HTML is shown as literal text,
not rendered. Links open in the same tab (no target attribute).
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Mapping, Optional
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

log = logging.getLogger("bowen.web_context")

PROVIDERS = ("openai", "perplexity")
DEFAULT_PROVIDER = "openai"

# Perplexity Agent API
API_URL = "https://api.perplexity.ai/v1/agent"
DEFAULT_MODEL = "perplexity/sonar"
DEFAULT_TIMEOUT_S = 12.0
MAX_OUTPUT_TOKENS = 400
MAX_SEARCH_RESULTS = 8
MAX_DOMAINS = 20  # the API's limit

# OpenAI Responses API
OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_DEFAULT_MODEL = "gpt-6.1-sol"
OPENAI_DEFAULT_TIMEOUT_S = 20.0
OPENAI_EFFORT = "low"            # gpt-6.1-sol does not accept "none"/"minimal"
OPENAI_SEARCH_CONTEXT = "low"    # a 100-word note; "medium" costs more input tokens
OPENAI_MAX_OUTPUT_TOKENS = 2000  # includes reasoning tokens
OPENAI_MAX_DOMAINS = 100         # the API's limit

MAX_WORDS = 120
MAX_LINKS = 4
MAX_TITLE_CHARS = 90

MODES = ("off", "gap", "always")

# Allowlist for the search filter (Perplexity takes up to 20, OpenAI up to
# 100). Subdomains are listed because the Perplexity docs do not say whether
# "govt.nz" covers them (OpenAI's do: subdomains are included).
NZ_DOMAINS = (
    "legislation.govt.nz",
    "justice.govt.nz",
    "courtsofnz.govt.nz",
    "tenancy.govt.nz",
    "employment.govt.nz",
    "worksafe.govt.nz",
    "govt.nz",
    "communitylaw.org.nz",
    "nzlii.org",
    "privacy.org.nz",
    "consumerprotection.govt.nz",
    "comcom.govt.nz",
    "ird.govt.nz",
    "police.govt.nz",
    "mbie.govt.nz",
    "dia.govt.nz",
    "ombudsman.parliament.nz",
    "parliament.nz",
    "lawsociety.org.nz",
    "hrc.co.nz",
)

HEADING = "From the web, not from the legislation Bowen holds"
CLOSING = "Web results are not checked against the legislation."

INSTRUCTIONS = """Search the web and give a short factual note on the user's question about New Zealand law.
- Focus on what a reader would not find in the text of an Act: court decisions, whether an amendment or Act is in force and from when, and guidance from New Zealand regulators and government agencies.
- Prefer official New Zealand sources (govt.nz sites, the courts, legislation.govt.nz, Community Law, NZLII). Ignore sources from other countries.
- At most 100 words, plain prose, no headings, no lists, no tables, no HTML.{cite}
- Write in the third person. Never write "I", "me" or "my", never give legal advice or tell the reader what to do, and never claim to be a lawyer or a legal information service.
- If the question asks for help harming, threatening, stalking, tracking or secretly recording someone, give no operational help: say only that it may be unlawful.
- If you find nothing reliable, say so in one sentence."""

# The one line that differs: Perplexity's text points at results by [n];
# OpenAI attaches citations itself (url_citation annotations).
_CITE = {"perplexity": " Cite sources with [n] markers.", "openai": " Do not add [n] markers."}


def instructions_for(provider: str) -> str:
    return INSTRUCTIONS.replace("{cite}", _CITE.get(provider, ""))


# =============================================================================
# Data
# =============================================================================

@dataclass(frozen=True)
class Link:
    title: str
    url: str


@dataclass(frozen=True)
class WebContext:
    text: str
    links: list[Link]
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    provider: str = ""


@dataclass(frozen=True)
class Config:
    mode: str
    model: str
    timeout_s: float
    domains: tuple[str, ...]
    provider: str = DEFAULT_PROVIDER
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


def _domains(raw: Optional[str], limit: int = MAX_DOMAINS) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return NZ_DOMAINS[:limit]
    if raw.strip().lower() == "none":
        return ()
    out = []
    for d in raw.split(","):
        d = d.strip().lower()
        if d and len(d) <= 253 and d not in out:
            out.append(d)
    return tuple(out[:limit])


_KEY_ENV = {"openai": "OPENAI_API_KEY", "perplexity": "PERPLEXITY_API_KEY"}


def _select_provider(environ: Mapping[str, str]) -> tuple[str, str]:
    """(provider, key). BOWEN_WEB_CONTEXT_PROVIDER wins; otherwise openai when
    its key is usable, else perplexity when its key is, else openai with no
    key (off)."""
    keys = {p: _usable_key(environ.get(env)) for p, env in _KEY_ENV.items()}
    raw = (environ.get("BOWEN_WEB_CONTEXT_PROVIDER") or "").strip().lower()
    if raw and raw not in PROVIDERS:
        log.warning("BOWEN_WEB_CONTEXT_PROVIDER=%r is not one of openai|perplexity; "
                    "using the default", raw)
        raw = ""
    if raw:
        return raw, keys[raw]
    for p in PROVIDERS:
        if keys[p]:
            return p, keys[p]
    return DEFAULT_PROVIDER, ""


def load_config(environ: Mapping[str, str] = os.environ) -> Config:
    provider, key = _select_provider(environ)
    spec = _PROVIDER_SPECS[provider]
    raw_mode = (environ.get("BOWEN_WEB_CONTEXT") or "").strip().lower()
    if raw_mode and raw_mode not in MODES:
        log.warning("BOWEN_WEB_CONTEXT=%r is not one of off|gap|always; using the default",
                    raw_mode)
        raw_mode = ""
    mode = raw_mode or ("gap" if key else "off")
    if not key:
        mode = "off"
    try:
        timeout = float(environ.get("BOWEN_WEB_CONTEXT_TIMEOUT") or spec.default_timeout_s)
        if timeout <= 0:
            raise ValueError
    except ValueError:
        timeout = spec.default_timeout_s
    return Config(
        mode=mode,
        model=(environ.get("BOWEN_WEB_CONTEXT_MODEL") or "").strip() or spec.default_model,
        timeout_s=timeout,
        domains=_domains(environ.get("BOWEN_WEB_CONTEXT_DOMAINS"), spec.max_domains),
        provider=provider,
        api_key=key,
    )


_startup_logged = False


def log_startup(config: Config) -> None:
    """One line at startup saying whether web context is on. Logs once."""
    global _startup_logged
    if _startup_logged:
        return
    _startup_logged = True
    if config.enabled:
        log.info("web context: provider=%s mode=%s model=%s timeout=%ss domains=%d",
                 config.provider, config.mode, config.model, config.timeout_s,
                 len(config.domains))
    else:
        log.info("web context: off (%s)",
                 f"no {_KEY_ENV.get(config.provider, 'API key')} (provider {config.provider})"
                 if not config.api_key else "BOWEN_WEB_CONTEXT=off")


# =============================================================================
# When to run (pure)
# =============================================================================

# The answer itself says a needed section or topic was not retrieved or held.
_GAP_RE = re.compile(
    r"\b(?:did\s*n[o']t|didn['’]t|have\s*n[o']t|haven['’]t|was\s*n[o']t|wasn['’]t|"
    r"were\s*n[o']t|weren['’]t|could\s*n[o']t|couldn['’]t)\s+(?:been\s+)?"
    r"(?:retrieve|retrieved|find|found|shown)\b"
    r"|\bnot\s+(?:been\s+)?(?:retrieved|shown)\b"
    # The prompt's and the footer's wording since 13 Nov: "wasn't among the
    # sections I pulled", "weren't among those I pulled", "not among the ...".
    r"|\b(?:was|were)n['’]t\s+among\s+(?:the\s+sections|those)\s+(?:i|bowen)\s+pulled\b"
    r"|\bnot\s+among\s+(?:the\s+sections|those)\s+(?:i|you|bowen)\s+pulled\b"
    r"|\b(?:do\s+not|don['’]t)\s+hold\b"
    r"|\bnot\s+in\s+the\s+legislation\s+(?:i|bowen)\s+holds?\b",
    re.IGNORECASE,
)

# A safety answer (helplines) is not a place for web text.
# "111" alone would also match "section 111", so it counts only as a phone number.
_SAFETY_RE = re.compile(
    r"\b1737\b|0800\s?733\s?843|0800\s?543\s?354|0508\s?326\s?459"
    r"|\b(?:call|ring|dial|phone)\s+111\b|\b111\s+(?:for|if|in\s+an?)\b",
    re.IGNORECASE,
)


def answer_reports_gap(answer_text: str) -> bool:
    return bool(_GAP_RE.search(answer_text or ""))


def should_fetch(config: Config, *, query: str, is_legal_query: bool, refused: bool,
                 sources_count: int, answer_text: str) -> bool:
    """gap: a legal question whose answer cited no retrieved source, or says a
    needed section or topic was not retrieved / not held. always: every legal
    question. Never for casual turns, refusals, attachment-only messages (no
    question text) or safety answers."""
    if not config.enabled or not is_legal_query or refused or not (query or "").strip():
        return False
    if _SAFETY_RE.search(answer_text or ""):
        return False
    if config.mode == "always":
        return True
    return sources_count == 0 or answer_reports_gap(answer_text)


# =============================================================================
# Request
# =============================================================================

def _perplexity_request(config: Config, question: str) -> dict:
    tool = {"type": "web_search", "max_results": MAX_SEARCH_RESULTS,
            "user_location": {"country": "NZ"}}
    if config.domains:
        tool["filters"] = {"search_domain_filter": list(config.domains[:MAX_DOMAINS])}
    return {
        "model": config.model,
        "instructions": instructions_for("perplexity"),
        "input": question,
        "tools": [tool],
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def _openai_request(config: Config, question: str) -> dict:
    tool = {"type": "web_search", "user_location": {"type": "approximate", "country": "NZ"},
            "search_context_size": OPENAI_SEARCH_CONTEXT}
    if config.domains:
        tool["filters"] = {"allowed_domains": list(config.domains[:OPENAI_MAX_DOMAINS])}
    return {
        "model": config.model,
        "instructions": instructions_for("openai"),
        "input": question,
        "tools": [tool],
        "tool_choice": "required",   # always search; never answer from memory
        "reasoning": {"effort": OPENAI_EFFORT},
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
        "store": False,
    }


def build_request(config: Config, question: str) -> dict:
    return _PROVIDER_SPECS[config.provider].build(config, question)


# =============================================================================
# Cleaning (the web text must not pass for Bowen's own voice or a SOURCES line)
# =============================================================================

_TAG_RE = re.compile(r"<[^>]*>")
_MARKER_RE = re.compile(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]")
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
# OpenAI's inline citation: "([employment.govt.nz](https://...))", sometimes
# several in one pair of brackets. Removed whole (the links are shown below).
_PAREN_CITE_RE = re.compile(r"\s*\(\s*(?:\[[^\]]*\]\([^)]*\)\s*[,;]?\s*)+\)")
_BARE_URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)
_SOURCES_RE = re.compile(r"^\W*sources?\W*:.*$", re.IGNORECASE | re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
# Sentences that sound like Bowen or speak in the first person are dropped.
_VOICE_RE = re.compile(
    r"\bbowen\b|\b(?:i|i'm|i've|i'd|i'll|me|my|myself)\b|as always|"
    r"consult a lawyer for your specific situation|verify and get advice",
    re.IGNORECASE,
)


def clean_text(raw: str, max_words: int = MAX_WORDS) -> str:
    s = html.unescape(raw or "")
    s = _TAG_RE.sub(" ", s)
    s = s.replace("<", " ").replace(">", " ")
    s = _SOURCES_RE.sub(" ", s)
    s = _PAREN_CITE_RE.sub("", s)
    s = _MD_LINK_RE.sub(r"\1", s)
    s = _BARE_URL_RE.sub(" ", s)
    s = _MARKER_RE.sub("", s)
    s = re.sub(r"(?m)^\s*(?:#{1,6}|>+|[-*+]|\d+[.)])\s+", " ", s)   # headings, quotes, lists
    s = re.sub(r"[*_`|~]+", "", s)                                     # emphasis, code, tables
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    sentences = [x.strip() for x in _SENTENCE_SPLIT_RE.split(s) if x.strip()]
    sentences = [x for x in sentences
                 if not _VOICE_RE.search(x) and not re.match(r"^\W*sources?\W*:", x, re.I)]
    out, words = [], 0
    for x in sentences:
        n = len(x.split())
        if words + n > max_words:
            if not out:  # one very long sentence: cut it
                out.append(" ".join(x.split()[:max_words]).rstrip(",;:") + "…")
            break
        out.append(x)
        words += n
    return " ".join(out)


def _clean_url(url) -> Optional[str]:
    if not isinstance(url, str):
        return None
    url = url.strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc or " " in parts.netloc:
        return None
    if "@" in parts.netloc:  # credentials in a URL: not a link to show
        return None
    safe = "/%:@!$&'*+,;=-._~"
    path = quote(parts.path, safe=safe)
    query = quote(parts.query, safe=safe + "?/")
    rebuilt = urlunsplit((parts.scheme, parts.netloc.lower(), path, query, ""))
    # Markdown link destinations must not contain these.
    return rebuilt.replace("(", "%28").replace(")", "%29").replace("<", "%3C").replace(">", "%3E")


def _clean_title(title, url: str) -> str:
    t = html.unescape(title if isinstance(title, str) else "")
    t = _TAG_RE.sub(" ", t)
    t = re.sub(r"[\[\]()<>*_`|#\\]", " ", t)
    t = " ".join(t.split())
    if "bowen" in t.lower():  # a title must not read as Bowen speaking
        t = ""
    if not t:
        t = urlsplit(url).netloc
    if len(t) > MAX_TITLE_CHARS:
        t = t[:MAX_TITLE_CHARS - 1].rstrip() + "…"
    return t


def _is_preferred(url: str, domains: tuple[str, ...]) -> bool:
    host = urlsplit(url).netloc.lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in domains or NZ_DOMAINS)


# =============================================================================
# Response parsing
# =============================================================================

def _usage(payload: Mapping) -> tuple[int, int]:
    u = payload.get("usage") or {}
    try:
        return int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0, 0


def _perplexity_parse(payload: Mapping) -> Optional[tuple[str, list]]:
    """(raw text, [(title, url), ...] in preference order), or None."""
    texts, candidates, results_by_id = [], [], {}
    for item in payload.get("output") or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("type") == "search_results":
            for r in item.get("results") or []:
                if isinstance(r, Mapping):
                    results_by_id[str(r.get("id"))] = r
        elif item.get("type") == "message":
            for part in item.get("content") or []:
                if not isinstance(part, Mapping) or part.get("type") != "output_text":
                    continue
                if isinstance(part.get("text"), str):
                    texts.append(part["text"])
                for a in part.get("annotations") or []:
                    if isinstance(a, Mapping) and a.get("url"):
                        candidates.append((a.get("title"), a.get("url")))
    raw_text = "".join(texts) or (payload.get("output_text") if isinstance(
        payload.get("output_text"), str) else "")
    # Results the text cites by [n], then the rest of the results.
    cited = []
    for m in re.finditer(r"\[(\d+)\]", raw_text):
        if m.group(1) in results_by_id and m.group(1) not in cited:
            cited.append(m.group(1))
    for rid in cited + [k for k in results_by_id if k not in cited]:
        r = results_by_id[rid]
        candidates.append((r.get("title"), r.get("url")))
    for c in payload.get("citations") or []:  # older Sonar shape, harmless if absent
        candidates.append((None, c))
    return raw_text, candidates


_TRACKING_PARAM_RE = re.compile(r"^(?:utm_[a-z_]+)=", re.IGNORECASE)


def _strip_tracking(url) -> object:
    """Drop utm_* query parameters (OpenAI adds ?utm_source=openai)."""
    if not isinstance(url, str) or "?" not in url:
        return url
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url
    kept = [p for p in parts.query.split("&") if p and not _TRACKING_PARAM_RE.match(p)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(kept), parts.fragment))


def _openai_parse(payload: Mapping) -> Optional[tuple[str, list]]:
    """(raw text with the inline citation spans removed, [(title, url), ...]),
    or None on a refusal. Links come only from the url_citation annotations:
    the citations for the text, not every page the search consulted."""
    messages = [item for item in payload.get("output") or []
                if isinstance(item, Mapping) and item.get("type") == "message"]
    final = [m for m in messages if m.get("phase") == "final_answer"]
    texts, candidates = [], []
    for item in final or messages:
        for part in item.get("content") or []:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") == "refusal":
                return None
            if part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                continue
            text, spans = part["text"], []
            for a in part.get("annotations") or []:
                if not isinstance(a, Mapping) or a.get("type") != "url_citation":
                    continue
                if a.get("url"):
                    candidates.append((a.get("title"), _strip_tracking(a.get("url"))))
                s, e = a.get("start_index"), a.get("end_index")
                if isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text):
                    spans.append((s, e))
            # Cut the cited spans (the inline "([domain](url))"), last first.
            # Only spans that are themselves link markup: never cut prose.
            for s, e in sorted(set(spans), reverse=True):
                if re.fullmatch(r"\s*\(?\s*\[[^\]]*\]\([^)]*\)\s*\)?\s*", text[s:e]):
                    text = text[:s] + text[e:]
            texts.append(text)
    return "".join(texts), candidates


def parse_response(payload, model: str, latency_ms: int,
                   domains: tuple[str, ...] = NZ_DOMAINS,
                   provider: str = DEFAULT_PROVIDER) -> Optional[WebContext]:
    if not isinstance(payload, Mapping):
        return None
    if payload.get("status") not in (None, "completed"):
        return None
    spec = _PROVIDER_SPECS.get(provider)
    parsed = spec.parse(payload) if spec else None
    if parsed is None:
        return None
    raw_text, candidates = parsed

    links, seen = [], set()
    for title, url in candidates:
        u = _clean_url(url)
        if not u or u in seen:
            continue
        seen.add(u)
        links.append(Link(title=_clean_title(title, u), url=u))
    # Preferred NZ domains first, order otherwise kept.
    links = sorted(links, key=lambda l: 0 if _is_preferred(l.url, domains) else 1)[:MAX_LINKS]

    text = clean_text(raw_text)
    if not text or not links:
        return None
    tin, tout = _usage(payload)
    return WebContext(text=text, links=links, model=str(payload.get("model") or model),
                      latency_ms=latency_ms, tokens_in=tin, tokens_out=tout, provider=provider)


# =============================================================================
# Providers: everything else above and below is shared
# =============================================================================

@dataclass(frozen=True)
class _ProviderSpec:
    api_url: str
    default_model: str
    default_timeout_s: float
    max_domains: int
    build: object   # (Config, question) -> dict
    parse: object   # (payload) -> (raw_text, [(title, url)]) | None


_PROVIDER_SPECS = {
    "openai": _ProviderSpec(OPENAI_API_URL, OPENAI_DEFAULT_MODEL, OPENAI_DEFAULT_TIMEOUT_S,
                            OPENAI_MAX_DOMAINS, _openai_request, _openai_parse),
    "perplexity": _ProviderSpec(API_URL, DEFAULT_MODEL, DEFAULT_TIMEOUT_S, MAX_DOMAINS,
                                _perplexity_request, _perplexity_parse),
}


# =============================================================================
# The call
# =============================================================================

_statuses_logged: set = set()


def _log_http_status(status: int) -> None:
    """A warning the first time each HTTP error status is seen in this
    process, then debug: a key without credits answers 403 on every request,
    and one clear line is enough. Never shown to the user."""
    if status in _statuses_logged:
        log.debug("web context: HTTP %s", status)
        return
    _statuses_logged.add(status)
    hint = " (key refused or no paid credits; web context returns nothing until fixed)" \
        if status in (401, 402, 403) else ""
    log.warning("web context: HTTP %s%s; further HTTP %s responses are logged at debug level",
                status, hint, status)

async def fetch_web_context(
    question: str,
    *,
    config: Optional[Config] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Optional[WebContext]:
    """Search the web for the question. Sends the question text and nothing
    else. Never raises; None when off, on any failure, or with no links."""
    try:
        cfg = config or load_config()
        if not cfg.enabled:
            log_startup(cfg)
            return None
        q = (question or "").strip()
        if not q:
            return None
        spec = _PROVIDER_SPECS[cfg.provider]
        body = spec.build(cfg, q)
        start = time.monotonic()
        async with httpx.AsyncClient(transport=transport,
                                     timeout=httpx.Timeout(cfg.timeout_s)) as client:
            resp = await asyncio.wait_for(
                client.post(spec.api_url, json=body,
                            headers={"Authorization": f"Bearer {cfg.api_key}"}),
                timeout=cfg.timeout_s,
            )
        latency_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code != 200:
            _log_http_status(resp.status_code)
            return None
        try:
            payload = resp.json()
        except ValueError:
            log.warning("web context: response was not JSON")
            return None
        ctx = parse_response(payload, cfg.model, latency_ms, cfg.domains, cfg.provider)
        if ctx is None:
            log.info("web context: no usable text or links (provider %s, status %s)",
                     cfg.provider, payload.get("status") if isinstance(payload, Mapping) else "-")
        return ctx
    except (asyncio.TimeoutError, httpx.TimeoutException):
        log.warning("web context: timed out")
        return None
    except Exception as e:  # never raise into the chat path; never log the key
        log.warning("web context: failed (%s)", type(e).__name__)
        return None


# =============================================================================
# Rendering (pure)
# =============================================================================

def render_block(ctx: Optional[WebContext]) -> str:
    """The markdown block the caller appends after the answer, or "".

    ---

    **From the web, not from the legislation Bowen holds**

    <text, at most 120 words>

    - [Title](https://...)

    _Web results are not checked against the legislation._
    """
    if ctx is None or not ctx.links:
        return ""
    text = clean_text(ctx.text)  # idempotent; guards a hand-built WebContext
    if not text:
        return ""
    lines = [f"- [{_clean_title(l.title, l.url)}]({l.url})"
             for l in ctx.links[:MAX_LINKS] if _clean_url(l.url) == l.url]
    if not lines:
        return ""
    return "\n\n".join([
        "---",
        f"**{HEADING}**",
        text,
        "\n".join(lines),
        f"_{CLOSING}_",
    ])


def log_fields(ctx: Optional[WebContext]) -> dict:
    """A JSON-safe dict for queries.jsonl. {} when no web context."""
    if ctx is None:
        return {}
    return {"provider": ctx.provider, "model": ctx.model, "latency_ms": ctx.latency_ms,
            "tokens_in": ctx.tokens_in, "tokens_out": ctx.tokens_out,
            "links": [l.url for l in ctx.links]}
