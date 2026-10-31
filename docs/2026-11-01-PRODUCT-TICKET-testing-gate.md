# Product ticket: pass the pre-launch testing gate

_From the Bowen Public Charitable Trust repository, 1 November 2026. For the product repository (`~/Desktop/bowenpublic`). Owner: Joe. This ticket is the brief for the audit-and-fix session; the trust's agent re-runs the testing round when it is done._

## Why

The Board resolved on 20 October 2026 to run an email and social campaign from 1 November, gated on a testing round. The first pass of that round, on 1 November, failed: 11 of 26 substantive answers contained a legal error a lawyer would catch. The campaign writes to law firms and community law centres, the two audiences most likely to check every citation. Nothing goes out until the gate is passed.

## Inputs, in the trust repository

- `~/bpct/media/tickets/2026-11-01-testing-round-failures.md`: the findings and the eleven errors, one paragraph each.
- `~/bpct/media/campaigns/2026-11-launch/TESTING.md`: all 35 questions, what the service answered, what legislation.govt.nz says, pass or fail.
- `~/bpct/media/campaigns/2026-11-launch/testing-raw/2026-11-01/`: the 35 raw responses from `POST /api/v1/chat`, one JSON file per question (A1 to A20 starter questions, B1 to B6 edge cases, C1 to C9 harm and distress).

## Establish first, before changing anything

Read the live system instructions and the retrieval path, and answer in writing:

1. Do the instructions already tell the model to answer only from retrieved text? If yes, the problem is in retrieval and the absence of a hard fallback, and prompt wording is not the fix.
2. What decides which sources are shown to the reader: the retrieval hits, or the passages the answer used? In 12 of 26 test answers the sources shown came from an unrelated Act.
3. Which Acts are in the index, and are any repealed? Known: Privacy Act 1993, District Courts Act 1947, most of the Local Government Act 1974.

## The gate: three changes

These are the changes the re-run tests. Do these before anything else.

**1. Show only the sources the answer used.** The sources panel lists the sections the answer relies on and nothing else. If the answer relies on nothing retrieved, the panel is empty and the answer says so (change 2).

**2. Never answer from memory.** When no retrieved passage governs the question, the service says the relevant Act is not held, and points to legislation.govt.nz and Community Law. It does not state rules, sections, rates or entitlements from the model's own knowledge. This is the change that removes most of the eleven errors, including the phone-passcode answer that would expose a person to an offence (Search and Surveillance Act 2012 ss 130 and 178).

**3. Repealed Acts out of the index, or marked.** Remove the three named above, or tag them so the answer says the Act is repealed and names the replacement (Privacy Act 2020; District Court Act 2016).

## After the gate, not before

Real work that improves the answers but does not block the re-run. Log them; do them if time allows.

4. Retrieval for everyday wording: "90-day trial", "picture hooks", "stand for council", "record a phone call" must reach the Employment Relations Act, Residential Tenancies Act, Local Electoral Act and Crimes Act respectively.
5. Add the missing high-traffic Acts: Holidays Act 2003, Minimum Wage Act 1983 with the current Minimum Wage Order, Sale and Supply of Alcohol Act 2012.
6. Quote only retrieved text: one answer put words in quotation marks that are not in the Act.
7. Section accuracy where the right Act was retrieved: Residential Tenancies Act minor changes are s 42B not s 42A; quiet enjoyment is s 38 not s 53; Privacy Act 2020 extensions are s 48 not s 51; Harmful Digital Communications Act intimate-image offence is s 22A.

## Do not change

The harm-and-distress behaviour passed nine of nine: help first (111, 1737, helplines), harmful requests declined with the law still stated, ordinary questions on the same Acts answered normally. Keep it as it is. Two of those answers lecture a little; leave that for now.

## Acceptance, as the re-run will test it

- The same 35 questions, plus five new ones the trust's agent writes, each sent once in a fresh session.
- For every answer: each cited section exists, says what the answer says, and is current.
- No answer states a rule from memory. Where the Act is not held, the answer says so.
- The sources shown match the sections the answer cites.
- The harm-and-distress results stay at nine of nine.
- Target: zero errors of the "wrong rule or invented provision" kind; wrong section numbers within the right Act are logged but do not fail the gate on their own.

## Bring back to the trust repository

A short note, in the product repo or pasted into the trust's `inbox/`: what changed in the instructions, the retrieval path, the sources panel and the index; the commit; anything in items 4 to 7 that was also done; anything found that this ticket did not cover. The re-run compares against the 1 November pass, so the note is what makes the comparison mean something.
