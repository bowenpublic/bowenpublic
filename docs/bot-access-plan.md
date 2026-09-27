# Bot access plan

How other AI assistants (Claude, ChatGPT, Perplexity, custom agents) come to use Bowen
when a user asks them about New Zealand law.

Drafted 28 September 2026. Status: proposal, nothing built.

## The idea in one paragraph

A bot cannot be made to choose Bowen. It uses Bowen in one of two situations: Bowen is
**installed** as a tool the bot can call, or Bowen is **found** when the bot searches the
web. This plan builds both, in that order, on top of the retrieval that already exists.
Bowen gives bots verbatim section text with citations, not generated answers. The calling
bot does its own reasoning; Bowen is the source it reasons over.

## Where we start from

Checked against the code on 28 September 2026.

**Already in place**
- `GET /api/v1/search` returns ranked sections with act, section number, heading, text,
  score and a legislation.govt.nz link (`backend/app/main.py:1288`)
- `GET /api/v1/acts` lists the registry, 183 acts (`backend/app/acts_registry.py`)
- `search_similar()` already supports an act filter and result-level dedupe
  (`backend/app/main.py:403`)
- FastAPI generates an OpenAPI spec at `/openapi.json` for free
- Backend on Railway, frontend on Netlify (Next.js 14, app router)

**Missing**
- No rate limiting anywhere in the backend
- No API keys for anything except the admin endpoints
- The act filter is not exposed on the public search endpoint
- No way to fetch a section by act and number
- The index now holds each Act's version date, but the API does not return it yet
- Frontend has no `robots.txt`, `sitemap.xml` or `llms.txt`, and no per-act or
  per-section pages. The only pages are home, about, donate, data policy and Te Tiriti
- Search still loops over every row in Python on each query. At 63,167 rows that
  takes 55 to 90 ms locally
- 11 Acts were removed because the downloaded file held a different Act. They need
  downloading again from the right address before they can come back

## Principles

- **Retrieval only.** The bot-facing surface never calls the Anthropic API. This keeps
  the cost per call close to zero and keeps Bowen out of the business of one model
  paraphrasing for another.
- **Every result is citable.** Act title, section number, heading, verbatim text,
  legislation.govt.nz link, and the date the text was retrieved.
- **A miss is stated as a miss.** If the act is not in the registry, or nothing clears
  the similarity floor, the response says so in plain words. It never returns the
  nearest wrong section.
- **Information, not advice.** The disclaimer travels with every response.
- **Same privacy rules as the site.** Bot queries are logged under the existing data
  policy and anonymisation, and flagged by channel.

## Phase 0: make retrieval fit to expose

Nothing public changes in this phase. It is the work that has to be true before a bot
is pointed at Bowen.

**0.1 Dedupe the corpus**
- What: finish the dedupe already identified as Path C in the expansion notes
- Why: search latency and memory. Bots call in loops and give up on slow tools
- Done when: one row per distinct (act, section, text), and the golden set still passes
- Status: done on 28 September 2026. The index went from 2,619,279 rows to 63,167
  across 183 verified Acts. Rows with no section number went from about 74% to 0.1%.
  Golden set over the full index: 42 of 55, against 41 of 55 for the old index
  deduplicated. Details in `backend/tests/NOTES-duplication.md`

**0.1a Fix act metadata**
- Status: done on 28 September 2026. Every Act in the index carries the title it
  gives itself, its year and a working link. Section links were all 404s and now
  resolve

**0.1b Decide on chunk size**
- What: chunks are up to 512 tokens, but the embedding model only reads the first
  256. On the ten test acts, 120-token chunks scored 48 of 55 against 45 of 55
- Why not done yet: it loses one question that passes today, and 55 questions is a
  small set to tune against
- Done when: tested on a larger golden set and either adopted or dropped

**0.2 Add a version date to chunk metadata**
- What: record each Act's "as at" date at parse time, carry it into each chunk
- Done when: every search result carries `as_at`
- Status: the index has it for every row. Still to do: return it from
  `search_similar()` and the search endpoint. Note the oldest version held is from
  2013, and 35 Acts are on versions from 2022 or earlier

**0.2a Re-download the 11 removed Acts**
- What: find the right address for each, download, and let the new title check
  confirm the page is the Act asked for
- Note: two of them, the Education Act 1989 and the Water Services Entities Act
  2022, have been repealed, so they should stay out. Three of the labels may not be
  real Acts at all and need checking against legislation.govt.nz

**0.3 Explicit coverage answers**
- What: a response shape for "not covered" and "no confident match", separate from an
  empty result list
- Done when: a query about an act outside the registry returns `covered: false` with
  the act name it looked for, and the swarm harness has cases for it

**0.4 Section lookup**
- What: fetch a section by act and section number, all chunks joined in order
- Done when: `get_section("Residential Tenancies Act 1986", "18")` returns the full
  text of that section

**0.5 Rate limiting**
- What: per-IP limits on the public endpoints, tighter on `/chat` than on `/search`
- Done when: a loop of requests gets a 429 with a `Retry-After` header

## Phase 1: MCP server

The main deliverable. One server works in Claude, ChatGPT, Cursor and most agent
frameworks.

**Transport and hosting**
- Remote server over streamable HTTP, mounted in the existing FastAPI app at `/mcp`
- Same Railway service, so it shares the loaded embeddings rather than loading a
  second copy
- Public and read-only, no login, rate limited per IP

**Tools**

`search_nz_legislation`
- Inputs: `query` (required), `act` (optional), `limit` (optional, default 5, max 10)
- Returns: ranked sections, each with act title, section number, heading, verbatim
  text, link, retrieval date and score, plus a `covered` flag
- Description to ship: "Search the full text of New Zealand Acts of Parliament. Use
  this whenever a question involves New Zealand legislation. Returns verbatim section
  text with citations to legislation.govt.nz. Information only, not legal advice."

`get_nz_legislation_section`
- Inputs: `act` (required), `section` (required)
- Returns: the full text of that section, with the same citation fields

`list_nz_acts`
- Inputs: none, or an optional `topic`
- Returns: the acts Bowen covers, so a bot can check coverage before it searches

**Known risk**
- `requirements.txt` pins `fastapi==0.109.0` and `pydantic==2.6.0`. The MCP Python SDK
  probably needs newer versions of both. Check this first, and if a bump is needed, do
  it as its own change with the test suite run before and after.

**Done when**
- The server can be added to Claude and to ChatGPT as a custom connector
- Asked "what is the maximum bond a landlord can charge in New Zealand", each calls
  the tool and cites the right section of the Residential Tenancies Act
- Asked about an act outside the registry, each reports that Bowen does not cover it

## Phase 2: REST API for everything else

For GPT Actions, LangChain-style agents and developers who do not use MCP.

- Expose the act filter on `GET /api/v1/search`
- Add `GET /api/v1/section`
- Tidy the OpenAPI spec: clear operation names and descriptions, since models read them
  the same way they read MCP tool descriptions
- Hide admin, debug and Stripe routes from the public spec
- Publish a short developer page on the site: what it is, the endpoints, the limits,
  the disclaimer
- Optional API keys for higher limits. Anonymous use stays available

## Phase 3: be found on the web

The no-install path. It reaches the most people and takes the longest to pay off.

**3.1 Crawler files**
- `robots.txt` that allows GPTBot, ClaudeBot, PerplexityBot and Google-Extended
- `sitemap.xml` generated from the acts registry
- `llms.txt` describing what Bowen is, what it covers, and where the API and MCP
  server are

**3.2 Act and section pages**
- Server-rendered pages at stable addresses, for example
  `/acts/residential-tenancies-act-1986/section-18`
- Each page: the verbatim text, the link to legislation.govt.nz, the retrieval date,
  and schema.org `Legislation` markup

**3.3 The honest problem**
- legislation.govt.nz is the canonical source and will outrank Bowen on raw text. A
  mirror adds nothing
- The pages need something the official site does not have. Candidates: a plain-language
  summary per section, "people also ask" questions drawn from anonymised query logs,
  and links between related sections across acts
- Decide which of these the trust is willing to stand behind before building 3.2.
  Generated summaries need a review process, since they would be published in the
  trust's name

## Phase 4: distribution

Only after Phase 1 is stable and coverage is wide enough to stand behind.

- List in the official MCP registry
- Submit to the Claude connectors directory and the ChatGPT apps directory
- A Bowen custom GPT that wraps the REST API, as a shop window
- A post on the launch, through the channels in the trust repo's media register

## Measurement

- Tag each logged query with its channel: `web`, `mcp`, `api`
- Record the client name the MCP handshake reports
- Report weekly: calls per channel, share of calls that returned `covered: false`, and
  the acts most often asked for that Bowen does not hold
- That last figure is the input for choosing which acts to ingest next

## Risks

**Wrong section returned with confidence**
- Effect: a bot repeats it to a user as law
- Mitigation: similarity floor, explicit misses, the swarm harness run against the
  bot-facing tools before launch

**Stale text**
- Effect: a bot cites a repealed or amended provision
- Mitigation: retrieval date on every result, and a refresh schedule for the corpus

**Cost and abuse**
- Effect: a looping agent saturates the Railway service
- Mitigation: rate limits from Phase 0.5, retrieval-only tools, no LLM calls

**Coverage gaps**
- Effect: 147 acts is a fraction of the statute book, and bots will ask about all of it
- Mitigation: `list_nz_acts`, explicit misses, and the measurement loop above

**Dependency bump**
- Effect: upgrading FastAPI and pydantic for the MCP SDK breaks something in production
- Mitigation: separate change, tests before and after

## Decisions for Joe

1. **Summaries on public pages.** Should the trust publish generated plain-language
   summaries under its name (Phase 3.3)? Recommendation: not until there is a review
   process, and start with the twenty most-asked sections.
2. **Anonymous access.** Keep the MCP server open with no key? Recommendation: yes,
   with rate limits. A sign-up step would stop most installs.
3. **Order of work.** Dedupe first, or MCP first on the current corpus?
   Recommendation: dedupe first. It is already diagnosed, and it removes the latency
   problem that would otherwise be the first thing bots hit.

## Suggested order

1. Phase 0.1 dedupe and 0.5 rate limiting
2. Phase 0.2 to 0.4
3. Phase 1 MCP server, tested privately as a custom connector
4. Phase 3.1 crawler files (small, can ship any time)
5. Phase 2 REST tidy-up
6. Decision on 3.3, then 3.2
7. Phase 4 listings
