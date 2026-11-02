"""
key_sections.py

Maps common legal topics to their key section numbers.
This helps the RAG prioritise substantive rules over procedural sections.

When a query matches a topic, these sections get boosted in search results,
and a topic that names only a few sections has them pinned into the results
(see PIN_MAX_SECTIONS and main.search_similar).
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
    "notice period": [
        ("rta", ["51", "52", "53", "54", "55", "56", "57"]),
    ],
    "notice to end tenancy": [
        ("rta", ["51", "53", "55"]),
    ],
    "landlord entry": [
        ("rta", ["48"]),
    ],
    "entry without permission": [
        ("rta", ["48"]),
    ],
    "rent increase": [
        ("rta", ["24", "25", "26"]),
    ],
    "tenancy termination": [
        ("rta", ["50", "51", "53", "55", "59", "60"]),
    ],
    "90 day notice": [
        ("rta", ["51"]),
    ],
    "42 day notice": [
        ("rta", ["51", "55"]),
    ],
    "healthy homes": [
        ("rta", ["45", "45A", "45B", "66I", "66J"]),
    ],
    "flatmates": [
        ("rta", ["10A", "10B"]),
    ],
    "flatmate": [
        ("rta", ["10A", "10B"]),
    ],
    
    # === EMPLOYMENT ===
    # ERA = Employment Relations Act, HA = Holidays Act (not in current corpus)
    "minimum wage": [
        ("era", ["131"]),
    ],
    "sick leave": [
        ("era", ["63", "64", "65"]),
    ],
    "annual leave": [
        ("era", ["16", "17", "18", "19", "20", "21"]),
    ],
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
        ("era", ["103", "103A", "104"]),
    ],
    "parental leave": [
        ("era", ["67", "68", "69", "70"]),
    ],
    "employee vs contractor": [
        ("era", ["6"]),
    ],
    "public holiday": [
        ("era", ["44", "45", "46", "47", "48", "49", "50"]),
    ],
    "bereavement leave": [
        ("era", ["69", "70", "71"]),
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
        ("ba", ["108", "109", "110", "111", "112"]),
    ],
    "unconsented work": [
        ("ba", ["40", "41", "124", "125", "126", "127", "128"]),
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
        ("ca", ["174", "175", "176"]),
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
    # FTA = Fair Trading Act (Consumer Guarantees Act not in corpus)
    "faulty product": [
        ("fta", ["5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18"]),
    ],
    "consumer guarantee": [
        ("fta", ["5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18"]),
    ],
    "refund": [
        ("fta", ["18", "19", "20", "21", "22", "23"]),
    ],
    "repair or replace": [
        ("fta", ["18", "19", "20", "21"]),
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
        ("pa", ["49", "50", "51", "52", "53", "54", "55"]),
        ("oia", ["12", "13", "14", "15", "16", "17", "18"]),
    ],
    "delete my information": [
        ("pa", ["58", "59", "60"]),
    ],
    
    # === HEALTH & SAFETY ===
    # HSWA = Health and Safety at Work Act
    "pcbu duties": [
        ("hswa", ["36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"]),
    ],
    "refuse unsafe work": [
        ("hswa", ["83", "84", "85"]),
    ],
    "notifiable event": [
        ("hswa", ["23", "24", "25", "26", "56", "57"]),
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
    # CA1961 = Crimes Act 1961
    "self defence": [
        ("ca1961", ["48"]),
    ],
    "assault": [
        ("ca1961", ["188", "189", "190", "191", "192", "193", "194", "195", "196"]),
    ],
    "theft": [
        ("ca1961", ["219", "220", "221", "222", "223", "224", "225", "226", "227", "228"]),
    ],
    "diversion": [
        ("ca1961", ["379", "380"]),
    ],
    "sentencing": [
        ("ca1961", ["7", "8", "9", "10", "11", "12", "13", "14", "15", "16"]),
    ],
    
    # === PROPERTY ===
    # PLA = Property Law Act
    "mortgage": [
        ("pla", ["73", "74", "75", "76", "77", "78", "79", "80", "81", "82", "83", "84", "85", "86", "87", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97", "98", "99", "100", "101", "102", "103", "104", "105", "106", "107", "108", "109", "110", "111", "112", "113", "114", "115", "116", "117", "118", "119"]),
    ],
    "lease": [
        ("pla", ["206", "207", "208", "209", "210", "211", "212", "213", "214", "215", "216", "217", "218", "219", "220", "221", "222", "223", "224", "225", "226", "227", "228", "229", "230", "231", "232", "233", "234", "235", "236", "237", "238", "239", "240", "241", "242", "243", "244", "245", "246", "247", "248", "249", "250", "251", "252", "253", "254", "255", "256", "257", "258", "259", "260", "261", "262", "263", "264", "265", "266", "267", "268", "269", "270", "271", "272", "273", "274", "275", "276", "277", "278", "279", "280", "281", "282", "283", "284", "285", "286", "287", "288", "289", "290", "291", "292", "293", "294", "295", "296", "297", "298", "299", "300", "301", "302", "303", "304", "305", "306", "307", "308", "309", "310", "311", "312", "313", "314", "315", "316", "317", "318", "319", "320", "321", "322", "323", "324", "325", "326", "327", "328", "329", "330", "331", "332", "333", "334", "335", "336", "337", "338", "339", "340", "341", "342", "343", "344", "345", "346", "347", "348", "349", "350"]),
    ],
    "easement": [
        ("pla", ["289", "290", "291", "292", "293", "294", "295", "296", "297", "298"]),
    ],

    # === TESTING GATE (2026-11-01): everyday wording ===
    # Act identifiers here are lower-case fragments of the full act_title, not
    # short names: should_boost_section() substring-matches, and a short id like
    # "lea" or "ssa" would also match unrelated titles.
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
        Boost multiplier (1.5 for exact match, 1.2 for act match, 1.0 otherwise)
    """
    if not key_sections:
        return 1.0
    
    act_title = meta.get('act_title', '').lower()
    act_short = meta.get('act_short_name', '').lower()
    section_num = meta.get('section_number', '').strip()
    
    # Check every matched entry: "bond" and "picture hooks" both name the RTA,
    # and stopping at the first would deny s42B its exact-section boost.
    boost = 1.0
    for act_id, sections in key_sections:
        act_id_lower = act_id.lower()
        
        # Check if this chunk is from the relevant act
        if act_id_lower in act_title or act_id_lower in act_short:
            # Check if this is one of the key sections
            if section_num in sections:
                return 2.0  # Strong boost for exact section match
            boost = 1.3  # Moderate boost for same act
    
    return boost


# A topic that lists this few sections names *the* governing sections, so
# search_similar() pins them into the results even when their similarity is
# low. Longer lists are ranges ("bond" -> ss 18-22B) and only boost.
PIN_MAX_SECTIONS = 4


def _act_matches_strictly(act_id: str, meta: dict) -> bool:
    """Pinning bypasses ranking, so it needs a tighter act match than boosting:
    a short id must equal act_short_name ("pa" is also inside "companies act"),
    and a title fragment must be long enough to identify one Act."""
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
                and _act_matches_strictly(act_id, meta)):
            return True
    return False