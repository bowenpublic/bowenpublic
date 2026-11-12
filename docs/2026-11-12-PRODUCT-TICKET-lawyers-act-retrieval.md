# Product ticket: questions about the tool's own legal position

_12 November 2026. From the trust repo. Source: a lawyer's test session of 11 Nov, transcript in `media/campaigns/2026-11-launch/correspondence/BATCH-5-REPLIES.md` (Wilkinson Smith). Product read at 893fc56, v1.0.12._

A lawyer asked the tool what limits the Lawyers and Conveyancers Act 2006 puts on a non-lawyer, and on a legal AI, giving legal help. Five turns. Three faults.

**1. The governing sections were never retrieved**
- Needed: s 24 (reserved areas of work: the offence), the s 6 definition of "reserved areas of work", s 21, s 22, s 23, s 27. All are in the corpus
- Got: s 21 and s 23 on turns 1 and 2; nothing from the Act on turns 3 and 4; s 27 only on turn 5. Section 25 was asked for by number three times and never came
- Wanted: a topic in `backend/app/key_sections.py` for unqualified legal practice (non-lawyer, legal advice, legal services, reserved areas, unauthorised practice, legal AI, chatbot) pinning those sections. A question that names an Act and section numbers ("sections 25 and 27 of the Lawyers and Conveyancers Act") should fetch exactly those sections

**2. Wrong Acts on follow-up turns**
- Turn 3 ("please answer the question again and use sections 25(2) and 27") retrieved the Property Law Act 2007 and the Building Act 2004. Turn 4 retrieved four more unrelated Acts
- The follow-up carried no Act name, so retrieval ran on the bare sentence. The Tenants Union saw the same two Acts open unrelated answers on 2 Nov
- Wanted: carry the Act in play from the previous turn into retrieval for a follow-up that names sections but no Act

**3. Two rule breaches in the answers**
- Rule 3: the model said unseen ss 25 and 27 "likely deal with reserved areas of work" (they do not) and later that ss 24 to 26 "may independently prohibit" non-lawyers. That is characterising sections it had not been shown
- Rule 9: on turn 4 it described the retrieval system, listed the irrelevant Acts it had been handed, and said "I find it a bit frustrating too". The user asked why, so some answer is needed, but it should be one fixed sentence, not a tour of the internals
- Wanted: tighten rule 3 to cover guesses about what a numbered section contains; give the model a fixed line for "why can't you find it"

**Regression set**
- Add the five turns as a named multi-turn set (`wilkinson-smith-lca-5`)

**Why this one matters**
- It is the question every lawyer on the mailing list is most likely to ask, and the tool's answer to it is the trust's public account of its own position. It should be the best answer the tool gives, not one of the weakest
