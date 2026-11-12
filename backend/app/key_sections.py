"""
key_sections.py

Maps common legal topics to their key section numbers.
This helps the RAG prioritise substantive rules over procedural sections.

When a query matches a topic, these sections get boosted in search results,
and a topic that names only a few sections has them pinned into the results
(see PIN_MAX_SECTIONS and main.search_similar).

Every section number here was checked against the heading and text of that
Act in the index (audit of 2026-11-12). A topic whose governing Act is not
held has no entry: a neighbouring Act's sections pinned in its place read as
the law on the topic and are not. backend/tests/test_key_sections_audit.py
checks that every listed section exists.
"""

import re

# Key sections for common topics
# Format: "topic_keyword": [(act_short_name, section_numbers), ...]

KEY_SECTIONS = {
    # === TENANCY ===
    # Note: Use "rta" to match act_short_name "RTA" in metadata
    "bond": [
        ("rta", ["18", "19", "20", "21", "22", "22A", "22B"]),
    ],
    "maximum bond": [
        ("rta", ["18"]),
    ],
    "bond limit": [
        ("rta", ["18"]),
    ],
    # "notice period" is in COMBINED_TOPICS: an employee asks about one too.
    "notice to end tenancy": [
        ("rta", ["51", "60A"]),
    ],
    "landlord entry": [
        ("rta", ["48"]),
    ],
    "entry without permission": [
        ("rta", ["48"]),
    ],
    "rent increase": [
        ("rta", ["24", "25"]),
    ],
    "tenancy termination": [
        ("rta", ["50", "51", "53", "55", "59", "60"]),
    ],
    "90 day notice": [
        ("rta", ["51"]),
    ],
    # s51(2) is the 42-day notice; s55 is termination by the Tribunal.
    "42 day notice": [
        ("rta", ["51"]),
    ],
    # s13A healthy homes statement, s45/s66I the duty, s123A records, s138B
    # the standards.
    "healthy homes": [
        ("rta", ["13A", "45", "66I", "123A", "138B"]),
    ],
    # No "flatmate" entry: the RTA has no flatmate sections (the old entry
    # named ss 10A-10B, which do not exist).

    # === EMPLOYMENT ===
    # ERA = Employment Relations Act. Leave, public holidays and the minimum
    # wage are set by the Holidays Act 2003, the Parental Leave and Employment
    # Protection Act 1987 and the Minimum Wage Act 1983, none of them held, so
    # those topics have no entry.
    "90 day trial": [
        ("era", ["67A", "67B"]),
    ],
    "trial period": [
        ("era", ["67A", "67B"]),
    ],
    "personal grievance": [
        ("era", ["103", "103A", "104", "105", "106", "107", "108", "109", "110", "111", "112", "113", "114"]),
    ],
    "unjustified dismissal": [
        ("era", ["103", "103A"]),
    ],
    "redundancy": [
        ("era", ["103", "103A"]),
    ],
    "employee vs contractor": [
        ("era", ["6"]),
    ],

    # === BUILDING ===
    # BA = Building Act
    "building consent": [
        ("ba", ["40", "41", "42", "43", "44", "45", "49", "50", "51", "52"]),
    ],
    "code compliance": [
        ("ba", ["91", "92", "93", "94", "95"]),
    ],
    "consent exemption": [
        ("ba", ["41", "42"]),
    ],
    "building warrant": [
        ("ba", ["100", "108", "108A", "109", "110", "111"]),
    ],
    # s96 certificate of acceptance and s164 notice to fix deal with work done
    # without consent; ss 124-128 (dangerous buildings) do not.
    "unconsented work": [
        ("ba", ["40", "41", "96", "97", "99", "164"]),
    ],

    # === COMPANIES ===
    # CA = Companies Act
    "director duties": [
        ("ca", ["131", "132", "133", "134", "135", "136", "137", "138", "139", "140"]),
    ],
    "director liability": [
        ("ca", ["135", "136", "137", "301"]),
    ],
    "trading while insolvent": [
        ("ca", ["135", "136", "380"]),
    ],
    "minority shareholder": [
        ("ca", ["165", "174", "175"]),
    ],
    "oppression": [
        ("ca", ["174", "175"]),
    ],
    "liquidation": [
        ("ca", ["240", "241", "242", "243", "244", "245", "246", "247", "248", "312", "313"]),
    ],
    "creditor priority": [
        ("ca", ["312", "313"]),
    ],

    # === CONSUMER ===
    # Guarantees and remedies are in the Consumer Guarantees Act; the Fair
    # Trading Act numbers once listed here were CGA numbers applied to the FTA.
    "faulty product": [
        ("consumer guarantees act", ["6", "7", "16", "18", "19"]),
    ],
    "consumer guarantee": [
        ("consumer guarantees act", ["5", "5A", "6", "7", "8", "9", "10", "11", "12", "13", "16", "18"]),
    ],
    "refund": [
        ("consumer guarantees act", ["18", "20", "21", "22", "23"]),
    ],
    "repair or replace": [
        ("consumer guarantees act", ["18", "19"]),
    ],
    "misleading conduct": [
        ("fta", ["9", "10", "11", "12", "12A", "13", "14"]),
    ],
    "unfair contract": [
        ("fta", ["26A", "26B", "26C", "26D"]),
    ],

    # === PRIVACY ===
    # PA = Privacy Act 2020, OIA = Official Information Act
    "privacy principle": [
        ("pa", ["22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"]),
    ],
    "data breach": [
        ("pa", ["114", "115", "116", "117", "118"]),
    ],
    "access to information": [
        ("pa", ["40", "44", "45", "46", "49", "50", "51", "52", "53"]),
        ("oia", ["12", "13", "14", "15", "16", "17", "18"]),
    ],
    # There is no right to deletion; a correction request (s59) is the route.
    "delete my information": [
        ("pa", ["59"]),
    ],

    # === HEALTH & SAFETY ===
    # HSWA = Health and Safety at Work Act
    "pcbu duties": [
        ("hswa", ["36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"]),
    ],
    "refuse unsafe work": [
        ("hswa", ["83", "84"]),
    ],
    "notifiable event": [
        ("hswa", ["23", "24", "25", "56", "57"]),
    ],
    "officer duties": [
        ("hswa", ["44"]),
    ],
    "worker duties": [
        ("hswa", ["45", "46"]),
    ],

    # === RMA ===
    # RMA = Resource Management Act
    "resource consent": [
        ("rma", ["87", "87A", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97", "98", "99", "100", "101", "102", "103", "104", "105", "106", "107", "108"]),
    ],
    "rma purpose": [
        ("rma", ["5", "6", "7", "8"]),
    ],
    "permitted activity": [
        ("rma", ["87A"]),
    ],
    "controlled activity": [
        ("rma", ["87A"]),
    ],
    "discretionary activity": [
        ("rma", ["87A", "104"]),
    ],
    "subdivision consent": [
        ("rma", ["218", "219", "220", "221", "222", "223", "224"]),
    ],
    "appeal resource consent": [
        ("rma", ["120", "121"]),
    ],

    # === CRIMINAL ===
    # CA1961 = Crimes Act 1961. No "diversion" entry: police diversion is not
    # statutory, and the word also means a water diversion under the RMA.
    "self defence": [
        ("ca1961", ["48"]),
    ],
    "assault": [
        ("ca1961", ["188", "189", "190", "191", "192", "193", "194", "195", "196"]),
    ],
    "theft": [
        ("ca1961", ["219", "220", "220AA", "220A", "221", "222", "223", "226", "227", "228"]),
    ],
    # Sentencing Act 2002; its ss 8 and 9 are missing from the index.
    "sentencing": [
        ("sentencing act 2002", ["7", "8A", "9A", "10", "10A"]),
    ],

    # === PROPERTY ===
    # PLA = Property Law Act. Part 3 (mortgages) starts at s75; ss 119-122 are
    # the notice before exercising powers, s176 the duty on a mortgagee sale.
    "mortgage": [
        ("pla", [str(n) for n in range(75, 123)] + ["176", "185"]),
    ],
    # "lease" is in COMBINED_TOPICS: as a substring it fired on "please".
    "easement": [
        ("pla", [str(n) for n in range(291, 301)] + ["313", "317"]),
    ],

    # === TESTING GATE (2026-11-01): everyday wording ===
    # Act identifiers here are lower-case fragments of the full act_title, not
    # short names: a short id like "lea" or "ssa" names no Act in the strict
    # match (_act_matches_strictly) unless it equals that Act's short name.
    "picture hooks": [
        ("rta", ["42A", "42B"]),
    ],
    "minor changes": [
        ("rta", ["42A", "42B"]),
    ],
    "quiet enjoyment": [
        ("rta", ["38"]),
    ],
    "stand for council": [
        ("local electoral act", ["25", "26", "55", "58"]),
    ],
    "nominated": [
        ("local electoral act", ["25", "26", "55", "58"]),
    ],
    "nomination": [
        ("local electoral act", ["25", "26", "55", "58"]),
    ],
    "passcode": [
        ("search and surveillance act", ["130", "178", "88"]),
    ],
    "password": [
        ("search and surveillance act", ["130", "178", "88"]),
    ],
    "search my phone": [
        ("search and surveillance act", ["130", "178", "88"]),
    ],
    "access information": [
        ("search and surveillance act", ["130", "178", "88"]),
    ],
    "record a phone call": [
        ("crimes act 1961", ["216B"]),
    ],
    "record phone": [
        ("crimes act 1961", ["216B"]),
    ],
    "recording a call": [
        ("crimes act 1961", ["216B"]),
    ],
    "intercept": [
        ("crimes act 1961", ["216B"]),
    ],
    "intimate": [
        ("harmful digital communications act", ["22A"]),
        ("crimes act 1961", ["216G", "216H", "216I", "216J"]),
    ],
}


# === ROUND 2 (2026-11-02): everyday wording, whole words, every group ===
# These words are too ambiguous for KEY_SECTIONS' substring match ("pet" is in
# "petition"; a building inspection is not a tenancy one), so a topic here fires
# only when each group has a whole-word match. Act ids follow the title-fragment
# convention above.
_TENANCY_WORDS = ("landlord", "landlords", "owner", "tenant", "tenants", "tenancy",
                  "rental", "rent", "renting", "flat", "property manager")

# Unqualified legal practice (ticket 2026-11-12). "legal advice" alone is in
# ordinary questions ("can I get legal advice about my tenancy"), so it fires
# only beside a word for someone who is not a lawyer.
_NOT_A_LAWYER = ("non lawyer", "non lawyers", "not a lawyer", "not lawyers",
                 "not being a lawyer", "isn't a lawyer", "unqualified",
                 "lawyer's title", "lawyer’s title", "lawyers title", "title of lawyer",
                 "ai", "artificial intelligence", "chatbot", "chatbots",
                 "chat bot", "accountant", "accountants", "paralegal", "paralegals")
_LEGAL_SERVICES = ("legal advice", "legal services", "legal service", "legal work",
                   "practise law", "practice law", "practising law", "practicing law")
_RESERVED_WORK = ("reserved area of work", "reserved areas of work", "reserved legal work",
                  "unauthorised practice", "unauthorized practice",
                  "unqualified practice", "unqualified legal practice")
_LCA = "lawyers and conveyancers act"
# s24 (the reserved-areas offence) and the s6 definition of reserved areas of
# work rank below the top results on similarity, so they are pinned (two pins,
# within main.MAX_PINNED). ss 21, 22, 23 and 27 rank well once boosted; listing
# five sections keeps that entry over PIN_MAX_SECTIONS, so they are not pinned
# and cannot displace the two that need it.
_LCA_ENTRIES = [(_LCA, ["24", "6"]),
                (_LCA, ["21", "22", "23", "24", "27"])]

COMBINED_TOPICS = [
    ((("pet", "pets"), _TENANCY_WORDS),
     [("rta", ["42C", "42E", "42F"])]),
    ((("inspection", "inspections", "inspect"), _TENANCY_WORDS + ("let them in",)),
     [("rta", ["48"])]),
    ((("heating", "heater", "heaters", "heat pump", "heatpump"), _TENANCY_WORDS),
     [("rta", ["45", "138B"])]),
    ((("fence", "fences", "fencing"),),
     [("fencing act 1978", ["9", "10", "11"])]),
    ((("noisy", "noise"),),
     [("resource management act", ["326", "327", "328"])]),
    ((("faulty", "broke", "broken", "failed", "defective", "stopped working"),
      ("bought", "buy", "purchased", "dealer", "shop", "store", "retailer")),
     [("consumer guarantees act", ["6", "7", "8"])]),
    ((("debt collector", "debt collectors", "debt collection"),),
     [("credit contracts and consumer finance act", ["41", "44A", "132A"])]),
    ((("official information",), ("how long", "days", "working days", "time limit")),
     [("official information act 1982", ["15"]),
      ("local government official information and meetings act", ["13"])]),
    ((("extend", "extension", "extensions"), ("privacy", "personal information")),
     [("privacy act 2020", ["48"])]),
    # === AUDIT (2026-11-12): moved from KEY_SECTIONS, whole words ===
    # An employee has a notice period too.
    ((("notice period", "notice periods"), _TENANCY_WORDS),
     [("rta", ["51", "52", "53", "54", "55", "56"])]),
    # Part 4 PLA leases (ss 206-274). RTA s142 disapplies Part 4 to residential
    # tenancies, so a plain "lease" is not enough: it needs a commercial word,
    # or the lessor/lessee wording residential tenants rarely use.
    ((("lease", "leases", "leased", "sublease", "lessee", "lessees", "lessor", "lessors"),
      ("commercial", "business", "shop", "office", "retail", "warehouse", "industrial",
       "lessee", "lessees", "lessor", "lessors")),
     [("pla", [str(n) for n in range(206, 275)])]),
    ((_NOT_A_LAWYER, _LEGAL_SERVICES), _LCA_ENTRIES),
    ((_RESERVED_WORK,), _LCA_ENTRIES),
    # "reserved area" alone is also a park or a fishery.
    ((("reserved area", "reserved areas"), ("lawyer", "lawyers", "legal")), _LCA_ENTRIES),
]

_COMBINED_PATTERNS = [
    ([re.compile(r"\b(?:" + "|".join(re.escape(w) for w in group) + r")\b") for group in groups], entries)
    for groups, entries in COMBINED_TOPICS
]


def matches_combined_topic(query: str) -> bool:
    """True if a COMBINED_TOPICS entry fires: whole words, every group. Used by
    the query gate; the substring topics in KEY_SECTIONS are too loose for that
    ("I forgot my password" is not a legal question)."""
    query_lower = query.lower().replace("-", " ")
    return any(all(p.search(query_lower) for p in patterns) for patterns, _ in _COMBINED_PATTERNS)


def get_key_sections_for_query(query: str) -> list:
    """
    Returns a list of (act_identifier, section_numbers) tuples
    for sections that should be boosted for this query.
    """
    # "90-day trial" must match the topic "90 day trial".
    query_lower = query.lower().replace("-", " ")
    matched_sections = []

    for topic, act_sections in KEY_SECTIONS.items():
        if topic in query_lower:
            matched_sections.extend(act_sections)

    for patterns, act_sections in _COMBINED_PATTERNS:
        if all(p.search(query_lower) for p in patterns):
            matched_sections.extend(act_sections)

    return matched_sections


def should_boost_section(meta: dict, key_sections: list) -> float:
    """
    Returns a boost multiplier (1.0 = no boost, >1.0 = boost).

    Args:
        meta: The chunk metadata containing act_title, act_short_name, section_number
        key_sections: List of (act_identifier, section_numbers) from get_key_sections_for_query

    Returns:
        Boost multiplier (2.0 for exact match, 1.3 for act match, 1.0 otherwise)
    """
    if not key_sections:
        return 1.0

    section_num = meta.get('section_number', '').strip()

    # Check every matched entry: "bond" and "picture hooks" both name the RTA,
    # and stopping at the first would deny s42B its exact-section boost.
    boost = 1.0
    for act_id, sections in key_sections:
        # The strict match, as for pins: a substring match let "ca" boost 35
        # Acts ("lawyers and conveyancers act"), "rma" every title with
        # "information" in it, and "era" six Acts.
        if _act_matches_strictly(act_id, meta):
            # Check if this is one of the key sections
            if section_num in sections and _is_key_chunk(act_id, section_num, meta):
                return 2.0  # Strong boost for exact section match
            boost = 1.3  # Moderate boost for same act

    return boost


# A topic that lists this few sections names *the* governing sections, so
# search_similar() pins them into the results even when their similarity is
# low. Longer lists are ranges ("bond" -> ss 18-22B) and only boost.
PIN_MAX_SECTIONS = 4


# A long section (an interpretation section runs to many chunks) is named for
# one definition in it. Only the chunk holding that text is boosted and pinned:
# boosting every chunk let the definitions crowd the rule out of the results,
# and the pin keeps the best-scoring chunk, which was another definition.
# (act id, section) -> lower-case text the chunk must contain.
KEY_CHUNK_TEXT = {
    ("lawyers and conveyancers act", "6"): "reserved areas of work means",
}


def _is_key_chunk(act_id: str, section_num: str, meta: dict) -> bool:
    needle = KEY_CHUNK_TEXT.get((act_id.lower(), section_num))
    return needle is None or needle in meta.get('text', '').lower()


# Pins exempt from main.PINNED_MIN_SIMILARITY. That floor stops a loose
# substring topic pinning a section that has nothing to do with the question.
# "Can an AI chatbot give legal advice in New Zealand?" names no Act and scores
# 0.13 against s24, under the floor, yet s24 is the section that answers it
# (ticket 2026-11-12); the topic's whole-word triggers are the safeguard here.
PIN_WITHOUT_FLOOR = {
    ("lawyers and conveyancers act", "24"),
    ("lawyers and conveyancers act", "6"),
}


def pin_ignores_floor(meta: dict) -> bool:
    """True if this chunk's pin is exempt from the similarity floor. Call only
    for a chunk is_pinned_section() has already accepted."""
    section_num = meta.get('section_number', '').strip()
    return any(section_num == sec and _act_matches_strictly(act_id, meta)
               for act_id, sec in PIN_WITHOUT_FLOOR)


def _act_matches_strictly(act_id: str, meta: dict) -> bool:
    """Used for both boosting and pinning: a short id must equal act_short_name
    ("pa" is also inside "companies act"), and a title fragment must be long
    enough to identify one Act."""
    act_id = act_id.lower()
    if act_id == meta.get('act_short_name', '').lower():
        return True
    return len(act_id) >= 8 and act_id in meta.get('act_title', '').lower()


def is_pinned_section(meta: dict, key_sections: list) -> bool:
    """True if this chunk is an exact section of a short key-section entry."""
    section_num = meta.get('section_number', '').strip()
    if not section_num:
        return False
    for act_id, sections in key_sections:
        if (len(sections) <= PIN_MAX_SECTIONS and section_num in sections
                and _act_matches_strictly(act_id, meta)
                and _is_key_chunk(act_id, section_num, meta)):
            return True
    return False
