# Product handback: round-two follow-ups

_From the product repository, 2 November 2026. Answers `docs/2026-11-01-PRODUCT-TICKET-round-2-followups.md`. Owner: Joe. Everything below was verified against the full production index (63k rows, 180 in-force Acts) through the real retrieval path, with the LLM stubbed. The answer wording itself ("I hold the X Act but didn't retrieve...") still needs the trust's live re-check of A12, A4, A18 and D3._

## Item 1: phone passcodes (A12)

**What was wrong**
- The "search my phone" boost did fire, but s 130 sits at raw cosine 0.37, rank 276. A multiplicative boost capped at 2.5 could never lift it into the top six.
- The same shape blocked A1: RTA s 42B sits at 0.21, below the 0.25 floor, so the "picture hooks" boost never ran at all.

**What changed**
- Key-section topics that name four or fewer sections now have those sections pinned into the results when their raw cosine clears a lower floor (0.15). At most three pins; the act filter is respected; lowest-ranked unpinned results are displaced.
- `should_boost_section` now checks every matched topic rather than stopping at the first.

**Result for A12**
- Detected: Search and Surveillance. Top six: s 88, s 178, s 103, s 29, s 27, s 130.
- Both s 130 and s 178 are in context. No prompt change was made for s 103(7); with s 130(3) present the model has the actual rule.

## Item 2: "I don't hold that Act" said of held Acts

**What changed**
- The system prompt now lists all 180 held titles (the same list `/api/v1/acts` serves, enforced by a test) and states the rule: if the Act is on the list, say you hold it but did not retrieve the section; say "I don't hold" only for an Act not on the list.
- The not-held examples now also name the Charities Act 2005, the End of Life Choice Act 2019 and the Healthy Homes Standards Regulations 2019, and the prompt says regulations and orders are not held at all.
- Every excerpts block opens with a backend-written line, "ACTS BOWEN HOLDS THAT MATCH THIS QUESTION: ...", built from the detected Act, registry keywords and a small set of everyday hint words. For A4, A18, D3, C8 and the live Property (Relationships) question it names the right Act.
- The backend footer no longer says "I don't hold the Act ... or didn't retrieve". The generic form is now neutral ("I didn't retrieve the legislation text that governs this question"). When the question strongly matches a held Act, the footer says "I hold the X Act, but I didn't retrieve the section that deals with this question".
- The live Property (Relationships) question had a second defect: "House seperation and unequal splits between partners" failed the legal-question gate, so no search ran at all. The gate now accepts separation wordings, misspelt or not.
- D3 was being detected as the Child Poverty Reduction Act on the word "children", which filtered the Care of Children Act out of retrieval. "children" is now a weak keyword; D3 now retrieves Care of Children Act sections.

**Cost**
- The static system prompt grew from about 2,500 to about 4,300 tokens. It is sent on every call and is not currently marked for prompt caching; that is a one-line change worth making if cost shows up.

## Item 3a: misspelt Act titles

- When no registry keyword matches and the question contains the word "act", the words before it are fuzzy-matched against each held Act's base name (difflib, ratio 0.85 or better, year must agree if given, unique best match only).
- "whats the consitution act of 1986 ..." now detects Constitution and retrieves ss 27, 12, 20, 28, 21 and 1. "act of parliament" and "act in self defence" stay undetected.
- Re-ran old versus new detection over 186 real questions (golden set, query log, campaign sessions, testing raw files): only D3 and A19 changed, both intended.

## Item 3: plain wording on held Acts

Now retrieving the governing section (full index, top six):
- A1 picture hooks: RTA s 42B.
- A3 fence cost: Fencing Act ss 9, 10, 11.
- A5 OIA time limit: OIA s 15 and LGOIMA s 13 at ranks 1 and 2.
- A16 record a call: Crimes Act s 216B.
- A19 noisy party: RMA ss 326, 327, 328 at the top (needed "fine" made a weak keyword; it was detecting the Sentencing Act).
- B5 privacy extension: Privacy Act 2020 s 48 at rank 1.
- D1 faulty car from a dealer: CGA ss 6, 7, 8 (the Arms Act still takes some slots on "dealer").
- D4 debt collector fees: CCCFA ss 41, 44A, 132A.
- Live RTA misses: pet (ss 42C, 42E, 42F), inspection without notice (s 48 at rank 1), heating (s 45 and s 138B). The pet question had also been failing the gate.

Still not retrieved:
- B4 agenda availability: only the tail of LGOIMA s 46A, as before. Chunking, not touched.
- C8 intimate images: HDCA s 22A. The question detects the Crimes Act, and the act filter excludes the HDCA. Left as is rather than loosen the filter.

Golden set: eight everyday wordings added (63 entries, 53 pass on the mini fixture, no previous pass or fail changed). A3, A19, B4, C8 and D4 could not be added because those Acts are not in the ten-Act test fixture; recorded in the baseline note.

## Items 4 and 5

- Item 4 (section wording): no code change. Model behaviour; re-check live.
- Item 5: the not-held additions are in the prompt (above). The Property (Relationships) and RTA cases are covered under items 2 and 3.

## Not changed

Tone, voice, SAFETY section, SOURCES protocol and sign-off are untouched.

## Tests

- 403 passed, 10 xfailed (was 325 and 10). New file `backend/tests/test_round2_followups.py`.
- Commit: see git log for this file's commit.
