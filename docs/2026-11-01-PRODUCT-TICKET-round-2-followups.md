# Product ticket: after the second testing pass

_From the Bowen Public Charitable Trust repository, 1 November 2026. For the product repository (`~/Desktop/bowenpublic`). Owner: Joe. Follows `2026-11-01-PRODUCT-TICKET-testing-gate.md` and the product's handback `2026-11-01-PRODUCT-HANDBACK-testing-gate-changes.md`. Full results: `~/bpct/media/campaigns/2026-11-launch/TESTING-ROUND-2.md`; raw responses in `~/bpct/media/campaigns/2026-11-launch/testing-raw/2026-11-01-round2/`._

## Where the gate stands

Run against commit 3693ea1 on the live service, 40 questions (the 35 from the first pass plus five new), fresh session each, every citation read on legislation.govt.nz.

- 24 answers stated a rule with sources: 23 verified correct, 1 wrong (A12).
- 4 answers said the Act is not held, correctly. 11 said the section was not retrieved and stated no rule.
- No repealed Act cited. No unrelated Act in any sources panel. Harm and distress 9 of 9, no lecturing.
- First pass for comparison: 11 of 26 wrong, 12 of 26 with unrelated sources shown.

Three things remain. The first two are small and are what stands between the service and the campaign going out. The third is the next piece of real work.

## 1. Phone passcodes: Search and Surveillance Act 2012 s 130 (blocks the send)

Question A12, "Do I have to let the police search my phone?". The answer now states the s 178 offence (good) but adds: "However, the protection in section 103(7) means you can't be forced to provide information that would tend to incriminate you. There's real tension between those provisions." s 103(7) only covers an assistance condition on a warrant under s 103(3)(b)(ii). The rule for passcodes is s 130(3): the self-incrimination protection in s 130(2) "does not prevent" a requirement to provide access information or assistance. There is no tension; the reader can be required to give the passcode. The answer also reconstructs s 130(1) from the text of s 178, which refers to it, while saying s 130 was not retrieved.

The handback put s 130 at rank 58 for this wording and parked the scoring change. Whatever the route (an exact-section boost that fires on "phone" or "passcode" or "password" with "police" or "search"; or lexical matching next to the embedding), the acceptance is: this question retrieves ss 130 and 178 and the answer says the passcode can be required and refusal is an offence. Until then, the answer must not reach for s 103(7) on this question.

## 2. "I don't hold that Act" said of Acts that are held (blocks the send)

Four answers said an Act is not in the index when `/api/v1/acts` lists it:

- A4: Consumer Guarantees Act 1993 ("I don't hold that Act and didn't retrieve the relevant sections"). D1, on the same Act, says "I hold that Act but didn't retrieve".
- A18: Limitation Act 2010 ("I don't hold the Limitation Act 2010").
- D3: Care of Children Act 2004 ("I don't hold that Act in my database").
- C8: Harmful Digital Communications Act 2015 ("which I don't hold the text of for this query"), ambiguous.

The model cannot tell "not retrieved" from "not held", so it guesses, and the prompt's three named examples of Acts not held make "not held" the easy guess. The backend knows the index. Either put a line in the context ("Of the Acts Bowen holds, these match this question: ...", or "Bowen holds the X Act; no section of it was retrieved for this question"), or have the backend write the not-held or not-retrieved sentence itself and tell the model only to point to it. Acceptance: a question on a held Act never produces "not held"; a question on a non-held Act always does. The campaign writes to people who will take "I don't hold the Consumer Guarantees Act" at face value.

## 3. Retrieval for plain wording on held Acts (after the send)

Eleven of 40 questions ended "not retrieved" although the Act is held and the governing section is clear. The formal versions of the same questions (B1 to B5, D5, "Under the X Act, ...") retrieve well; the everyday versions do not.

- A1 picture hooks: RTA s 42B not retrieved (the boost added in 3693ea1 did not fire for "picture hooks in the wall"; only s 22A came back).
- A3 fence cost: Fencing Act ss 9, 10, 11 (B2 retrieved ss 10 and 11 for the formal wording).
- A5 OIA time limit: OIA s 15, LGOIMA s 13.
- A16 record a call: Crimes Act s 216B (known, rank 9).
- A19 noisy party: RMA ss 326 to 328.
- B4 agenda availability: only the tail of LGOIMA s 46A (subsections 9 and 10) was retrieved; s 46A(1) holds the "at least 2 working days" rule. Looks like a chunking boundary, worth a look on its own.
- B5 privacy extensions: Privacy Act 2020 s 48.
- C8 intimate images: HDCA s 22A (retrieved for C6 but not for this wording).
- D1 faulty car from a dealer: CGA ss 6 to 8 (retrieval returned the Arms Act and the Motor Vehicle Sales Act banning provisions).
- D4 debt collector fees: CCCFA (retrieval returned government debt recovery sections).

These refuse cleanly and are safe to ship; they are the next quality step, not a gate item. A golden set built from these ten wordings would catch regressions.

### 3a. Act detection has no tolerance for a misspelt title (found 2 Nov)

Joe asked, on the site: "whats the consitution act of 1986 and what was it designed to fix so to speak" (missing t). Retrieval returned Commerce Act amendments, aviation and GST chunks; the answer said it did not have the excerpts, and on a repeat in a fresh session said "I don't hold the text of the Constitution Act 1986". The same question spelt correctly returned Constitution Act 1986 ss 1, 12, 20, 27 and 28 and a proper answer. So a one-letter typo in an Act's name switches off detection, the similarity search drifts, and the model then guesses "not held". Typed questions will often be misspelt. Fuzzy matching on Act titles (edit distance, or a spelling-tolerant keyword index) in `detect_act_from_query`, and the item 2 fix for the wording. Evidence: two ad hoc calls on 2 Nov 2026, recorded here only (not in the round-two raw folder).

## 4. Section wording, small

- C7: "under sections 69 and 70, applications can be made on behalf of a person who lacks capacity or is prevented from applying personally". Lacking capacity is s 67; s 69 is an adult prevented by physical incapacity, fear of harm or another sufficient cause, and s 69(1)(a) excludes the s 67 case. s 69 is also cited in the text but absent from the sources panel, so the SOURCES line and the prose disagreed.
- C3: s 75 is paraphrased as "a risk of harm to a child"; the Act says "for the applicant, or a child of the applicant's family, or both", and includes undue hardship.
- A2: s 67B(3) as at 10 July 2026 allows the s 103(1)(b) ground only "if the ground does not relate to the dismissal"; the answer says "(b) to (k)" flat.

## 5. Live evidence from the first campaign day (added 2 Nov, from the product's own log)

Five visitor sessions after the batch 1 emails, 52 questions, 19 answered with no retrieved source text. Joe's extract is in the product repo at `logs/campaign-2026-11-02-sessions.md`; question text stays there and is not copied here. What the day adds to items 2 and 3, by Act:

- **Item 2 again, Property (Relationships) Act 1976.** A visitor asked about an unequal split of a house between separating partners. Act detection returned none, retrieval returned nothing, and the answer said "I don't hold that Act in my database". The index holds it: 207 chunks, registered. Same defect as A4, A18 and D3, now seen by a member of the public.
- **Item 3 again, Residential Tenancies Act 1986.** A tenancy worker ran 14 realistic tenant scenarios in 15 minutes. Three plain questions on a held Act came back with no RTA source: a landlord refusing a pet, a landlord demanding entry for an inspection without notice (retrieval returned Building Act inspection sections instead), and whether a rental must have heating. Two more detected no Act for a retaliatory 90-day notice and for a sale-of-house notice, though sources were found. The RTA is the Act the campaign's first audience will test hardest.
- **Not held, said correctly, worth adding.** Charities Act 2005 (asked three times in one session, likely a community organisation checking its own law), End of Life Choice Act 2019, and the Residential Tenancies (Healthy Homes Standards) Regulations 2019 (asked twice; the answer named the regulations and declined, which is right, but healthy homes is a top tenancy topic and the regulations are not in the index). These join the Holidays Act, Minimum Wage Act and Order, and Sale and Supply of Alcohol Act from the gate ticket's item 5.
- **Pattern in detection.** 25 of 52 questions detected no Act. Many were general civics ("is NZBORA supreme law", "what is stare decisis") where none is fine, but the tenancy and relationship-property misses above are the ones that cost a user an answer.

Nothing wrong was stated: every no-source answer declined and pointed to legislation.govt.nz and Community Law. The cost of the day was answers not given, not answers given wrongly. Separately, the access log was printing the admin token because `/admin/stats` took it as a URL parameter; v1.0.11 (12a7b15) moved it to the `X-Admin-Token` header and the token was rotated the same day. Done.

## Do not change

Tone. The openers ("Great question!", "Good on you") were listed here as a small item; Joe read the live answers on 2 Nov and wants the tone kept as it is. Leave the voice alone.

Harm and distress: 9 of 9, help first, declines without lectures (C4 and C5 are now as the Board asked). The SOURCES protocol and the hard fallback are doing their job; 15 refusals, none invented anything.

## Bring back

A short note as before: what changed for items 1 and 2, the commit, and whether anything in 3 to 5 was done (the tone note that was here is withdrawn: Joe likes the tone as it is, 2 Nov). The trust's agent will re-check A12, A4, A18 and D3 (four calls), and the campaign's first batch goes out on the next working day after that passes.
