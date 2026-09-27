"""
acts_registry.py

Single source of truth for all NZ Acts supported by Bowen.
Used by both the backend for act detection and served to frontend via API.
"""

import re
from typing import List, Dict, Optional

# Acts Registry - the single source of truth
ACTS_REGISTRY: Dict[str, Dict] = {
    "RTA": {
        "title": "Residential Tenancies Act 1986",
        "short_name": "RTA",
        "year": 1986,
        "keywords": ["rta", "residential tenancies", "tenancy", "tenant", "landlord", "bond", "rental", "rent"],
        "topics": ["tenancy", "bonds", "housing"],
        "url": "https://www.legislation.govt.nz/act/public/1986/0120/latest/DLM94278.html"
    },
    "ERA": {
        "title": "Employment Relations Act 2000",
        "short_name": "ERA",
        "year": 2000,
        "keywords": ["era", "employment relations", "employment", "employer", "employee", "dismissal", "redundancy", "leave", "wages", "union"],
        "topics": ["employment", "dismissal", "leave"],
        "url": "https://www.legislation.govt.nz/act/public/2000/0024/latest/DLM58317.html"
    },
    "CA": {
        "title": "Companies Act 1993",
        "short_name": "CA",
        "year": 1993,
        "keywords": ["companies act", "company", "director", "shareholder", "incorporation", "liquidation"],
        "topics": ["directors", "shareholders", "incorporation"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0105/latest/DLM319570.html"
    },
    "CGA": {
        "title": "Consumer Guarantees Act 1993",
        "short_name": "CGA",
        "year": 1993,
        "keywords": ["cga", "consumer guarantees", "consumer", "refund", "repair", "guarantee"],
        "topics": ["refunds", "repairs", "guarantees"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0091/latest/DLM311053.html"
    },
    "PLA": {
        "title": "Property Law Act 2007",
        "short_name": "PLA",
        "year": 2007,
        "keywords": ["pla", "property law", "mortgage", "lease", "easement", "property"],
        "topics": ["property", "mortgages", "leases"],
        "url": "https://www.legislation.govt.nz/act/public/2007/0091/latest/DLM968962.html"
    },
    "FTA": {
        "title": "Fair Trading Act 1986",
        "short_name": "FTA",
        "year": 1986,
        "keywords": ["fta", "fair trading", "misleading", "deceptive", "consumer protection"],
        "topics": ["consumer protection", "misleading conduct"],
        "url": "https://www.legislation.govt.nz/act/public/1986/0121/latest/DLM96439.html"
    },
    "PA": {
        "title": "Privacy Act 2020",
        "short_name": "PA",
        "year": 2020,
        "keywords": ["privacy act", "privacy", "personal information", "data protection", "ipp"],
        "topics": ["personal information", "data breaches"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0031/latest/LMS23223.html"
    },
    "BA": {
        "title": "Building Act 2004",
        "short_name": "BA",
        "year": 2004,
        "keywords": ["building act", "building consent", "building code", "construction", "ccc", "code compliance"],
        "topics": ["consents", "code compliance"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0072/latest/DLM306036.html"
    },
    "CCLA": {
        "title": "Contract and Commercial Law Act 2017",
        "short_name": "CCLA",
        "year": 2017,
        "keywords": ["ccla", "contract", "commercial law", "sale of goods", "contracts"],
        "topics": ["contracts", "sale of goods"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0005/latest/DLM6844033.html"
    },
    "RMA": {
        "title": "Resource Management Act 1991",
        "short_name": "RMA",
        "year": 1991,
        "keywords": ["rma", "resource management", "resource consent", "environmental", "environment", "planning"],
        "topics": ["environment", "resource consents"],
        "url": "https://www.legislation.govt.nz/act/public/1991/0069/latest/DLM230265.html"
    },
    "CA1961": {
        "title": "Crimes Act 1961",
        "short_name": "CA1961",
        "year": 1961,
        "keywords": ["crimes act", "criminal", "crime", "offence", "sentencing"],
        "topics": ["criminal offences", "sentencing"],
        "url": "https://www.legislation.govt.nz/act/public/1961/0043/latest/DLM327382.html"
    },
    "HSWA": {
        "title": "Health and Safety at Work Act 2015",
        "short_name": "HSWA",
        "year": 2015,
        "keywords": ["hswa", "health and safety", "workplace safety", "pcbu", "worksafe"],
        "topics": ["workplace safety", "PCBU duties"],
        "url": "https://www.legislation.govt.nz/act/public/2015/0070/latest/DLM5976660.html"
    },
    "HRA": {
        "title": "Human Rights Act 1993",
        "short_name": "HRA",
        "year": 1993,
        "keywords": ["human rights", "discrimination", "equality", "hrc"],
        "topics": ["discrimination", "equality"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0082/latest/DLM304212.html"
    },
    "ITA": {
        "title": "Income Tax Act 2007",
        "short_name": "ITA",
        "year": 2007,
        "keywords": ["income tax", "tax", "ird", "deduction", "taxable income"],
        "topics": ["tax", "deductions", "income"],
        "url": "https://www.legislation.govt.nz/act/public/2007/0097/latest/DLM1512301.html"
    },
    "LTA": {
        "title": "Land Transport Act 1998",
        "short_name": "LTA",
        "year": 1998,
        "keywords": ["land transport", "driving", "licence", "traffic", "road"],
        "topics": ["driving", "licences", "traffic"],
        "url": "https://www.legislation.govt.nz/act/public/1998/0110/latest/DLM433613.html"
    },
    "IA": {
        "title": "Immigration Act 2009",
        "short_name": "IA",
        "year": 2009,
        "keywords": ["immigration", "visa", "residence", "deportation", "migrant"],
        "topics": ["visas", "residence", "deportation"],
        "url": "https://www.legislation.govt.nz/act/public/2009/0051/latest/DLM1440303.html"
    },
    "TA": {
        "title": "Trusts Act 2019",
        "short_name": "TA",
        "year": 2019,
        "keywords": ["trusts act", "trust", "trustee", "beneficiary", "settlor"],
        "topics": ["trusts", "trustees", "beneficiaries"],
        "url": "https://www.legislation.govt.nz/act/public/2019/0038/latest/LMS82334.html"
    },
    "INSA": {
        "title": "Insolvency Act 2006",
        "short_name": "INSA",
        "year": 2006,
        "keywords": ["insolvency", "bankruptcy", "liquidation", "bankrupt"],
        "topics": ["bankruptcy", "liquidation"],
        "url": "https://www.legislation.govt.nz/act/public/2006/0055/latest/DLM385299.html"
    },
    "CRA": {
        "title": "Copyright Act 1994",
        "short_name": "CRA",
        "year": 1994,
        "keywords": ["copyright", "intellectual property", "ip", "infringement"],
        "topics": ["copyright", "intellectual property"],
        "url": "https://www.legislation.govt.nz/act/public/1994/0143/latest/DLM345634.html"
    },
    "CCCFA": {
        "title": "Credit Contracts and Consumer Finance Act 2003",
        "short_name": "CCCFA",
        "year": 2003,
        "keywords": ["cccfa", "credit", "loan", "consumer finance", "interest"],
        "topics": ["loans", "credit", "interest"],
        "url": "https://www.legislation.govt.nz/act/public/2003/0052/latest/DLM211512.html"
    },
    "OIA": {
        "title": "Official Information Act 1982",
        "short_name": "OIA",
        "year": 1982,
        "keywords": ["oia", "official information", "government information", "disclosure"],
        "topics": ["government", "requests", "disclosure"],
        "url": "https://www.legislation.govt.nz/act/public/1982/0156/latest/DLM64785.html"
    },
    "FVA": {
        "title": "Family Violence Act 2018",
        "short_name": "FVA",
        "year": 2018,
        "keywords": ["family violence", "domestic violence", "protection order", "abuse"],
        "topics": ["protection orders", "domestic violence"],
        "url": "https://www.legislation.govt.nz/act/public/2018/0046/latest/LMS112966.html"
    },
    "ACA": {
        "title": "Accident Compensation Act 2001",
        "short_name": "ACA",
        "year": 2001,
        "keywords": ["acc", "accident compensation", "injury", "compensation"],
        "topics": ["ACC", "injury", "compensation"],
        "url": "https://www.legislation.govt.nz/act/public/2001/0049/latest/DLM99494.html"
    },
    "FMCA": {
        "title": "Financial Markets Conduct Act 2013",
        "short_name": "FMCA",
        "year": 2013,
        "keywords": ["fmca", "financial markets", "securities", "investment", "fma"],
        "topics": ["securities", "investment", "disclosure"],
        "url": "https://www.legislation.govt.nz/act/public/2013/0069/latest/DLM4090578.html"
    },
    "HDCA": {
        "title": "Harmful Digital Communications Act 2015",
        "short_name": "HDCA",
        "year": 2015,
        "keywords": ["hdca", "harmful digital", "cyberbullying", "online harassment", "netsafe"],
        "topics": ["cyberbullying", "online harassment"],
        "url": "https://www.legislation.govt.nz/act/public/2015/0063/latest/whole.html"
    },
    "UTA": {
        "title": "Unit Titles Act 2010",
        "short_name": "UTA",
        "year": 2010,
        "keywords": ["unit titles", "body corporate", "apartment", "strata"],
        "topics": ["body corporate", "apartments"],
        "url": "https://www.legislation.govt.nz/act/public/2010/0022/latest/DLM1160440.html"
    },
    "LGA": {
        "title": "Local Government Act 2002",
        "short_name": "LGA",
        "year": 2002,
        "keywords": ["local government", "council", "rates", "bylaws"],
        "topics": ["councils", "rates", "bylaws"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0084/latest/DLM170873.html"
    },
    "FCA": {
        "title": "Family Court Act 1980",
        "short_name": "FCA",
        "year": 1980,
        "keywords": ["family court", "family proceedings"],
        "topics": ["family court", "jurisdiction"],
        "url": "https://www.legislation.govt.nz/act/public/1980/0161/latest/DLM42254.html"
    },
    "CORA": {
        "title": "Coroners Act 2006",
        "short_name": "CORA",
        "year": 2006,
        "keywords": ["coroner", "inquest", "death inquiry"],
        "topics": ["inquests", "death inquiries"],
        "url": "https://www.legislation.govt.nz/act/public/2006/0038/latest/DLM377057.html"
    },
    "SOGA": {
        "title": "Sale of Goods Act 1908",
        "short_name": "SOGA",
        "year": 1908,
        "keywords": ["sale of goods", "goods", "buyer", "seller"],
        "topics": ["sale", "goods", "contracts"],
        "url": "https://www.legislation.govt.nz/act/public/1908/0168/latest/DLM173958.html"
    },
    "CONST": {
        "title": "Constitution Act 1986",
        "short_name": "CONST",
        "year": 1986,
        "keywords": ["constitution", "parliament", "sovereignty", "executive", "crown"],
        "topics": ["parliament", "sovereignty", "executive"],
        "url": "https://www.legislation.govt.nz/act/public/1986/0114/latest/DLM94204.html"
    },
    "ELEC": {
        "title": "Electoral Act 1993",
        "short_name": "ELEC",
        "year": 1993,
        "keywords": ["electoral", "election", "voting", "mmp", "parliament"],
        "topics": ["voting", "elections", "parliament"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0087/latest/DLM307519.html"
    },
    "CITZ": {
        "title": "Citizenship Act 1977",
        "short_name": "CITZ",
        "year": 1977,
        "keywords": ["citizenship", "naturalisation", "citizen"],
        "topics": ["citizenship", "naturalisation"],
        "url": "https://www.legislation.govt.nz/act/public/1977/0061/latest/DLM443684.html"
    },
    "AML": {
        "title": "Anti-Money Laundering and Countering Financing of Terrorism Act 2009",
        "short_name": "AML",
        "year": 2009,
        "keywords": ["aml", "anti-money laundering", "money laundering", "terrorism financing", "kyc"],
        "topics": ["money laundering", "terrorism financing", "reporting"],
        "url": "https://www.legislation.govt.nz/act/public/2009/0035/latest/DLM2140700.html"
    },
    "TMA": {
        "title": "Trade Marks Act 2002",
        "short_name": "TMA",
        "year": 2002,
        "keywords": ["trade mark", "trademark", "brand", "registration"],
        "topics": ["trade marks", "registration", "infringement"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0049/latest/DLM164240.html"
    },
    "PATA": {
        "title": "Patents Act 2013",
        "short_name": "PATA",
        "year": 2013,
        "keywords": ["patent", "invention", "iponz"],
        "topics": ["patents", "inventions", "intellectual property"],
        "url": "https://www.legislation.govt.nz/act/public/2013/0068/latest/DLM1419043.html"
    },
    "CCRA": {
        "title": "Climate Change Response Act 2002",
        "short_name": "CCRA",
        "year": 2002,
        "keywords": ["climate change", "emissions", "carbon", "ets"],
        "topics": ["emissions", "carbon", "climate"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0040/latest/DLM158584.html"
    },
    "CONS": {
        "title": "Conservation Act 1987",
        "short_name": "CONS",
        "year": 1987,
        "keywords": ["conservation", "doc", "protected area", "national park"],
        "topics": ["conservation", "DOC", "protected areas"],
        "url": "https://www.legislation.govt.nz/act/public/1987/0065/latest/DLM103610.html"
    },
    "PSA": {
        "title": "Public Service Act 2020",
        "short_name": "PSA",
        "year": 2020,
        "keywords": ["public service", "government agency", "state sector"],
        "topics": ["public service", "government agencies"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0040/latest/LMS106159.html"
    },
    "FENZ": {
        "title": "Fire and Emergency New Zealand Act 2017",
        "short_name": "FENZ",
        "year": 2017,
        "keywords": ["fire", "emergency", "fenz", "fire service", "rescue"],
        "topics": ["fire", "emergency", "rescue"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0017/latest/DLM6712701.html"
    },
    "PFA": {
        "title": "Public Finance Act 1989",
        "short_name": "PFA",
        "year": 1989,
        "keywords": ["public finance", "budget", "appropriation", "crown accounts"],
        "topics": ["budget", "appropriation", "crown"],
        "url": "https://www.legislation.govt.nz/act/public/1989/0044/latest/DLM160809.html"
    },
    "DCA": {
        "title": "District Courts Act 1947",
        "short_name": "DCA",
        "year": 1947,
        "keywords": ["district court", "district courts"],
        "topics": ["district court", "jurisdiction"],
        "url": "https://www.legislation.govt.nz/act/public/1947/0016/latest/DLM242776.html"
    },
    "BSA": {
        "title": "Biosecurity Act 1993",
        "short_name": "BSA",
        "year": 1993,
        "keywords": ["biosecurity", "pest", "quarantine", "mpi"],
        "topics": ["biosecurity", "pest", "quarantine"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0095/latest/DLM314623.html"
    },
    "FA": {
        "title": "Fisheries Act 1996",
        "short_name": "FA",
        "year": 1996,
        "keywords": ["fisheries", "fishing", "quota", "marine"],
        "topics": ["fishing", "quota", "marine"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0088/latest/DLM394192.html"
    },
    "HSNO": {
        "title": "Hazardous Substances and New Organisms Act 1996",
        "short_name": "HSNO",
        "year": 1996,
        "keywords": ["hsno", "hazardous substances", "chemicals", "gmo", "new organisms"],
        "topics": ["hazardous", "chemicals", "GMO"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0030/latest/DLM381222.html"
    },
    "FCAM": {
        "title": "Freedom Camping Act 2011",
        "short_name": "FCAM",
        "year": 2011,
        "keywords": ["freedom camping", "camping", "campervan"],
        "topics": ["camping", "vehicles", "local authority"],
        "url": "https://www.legislation.govt.nz/act/public/2011/0061/latest/DLM3742828.html"
    },
    "HA": {
        "title": "Health Act 1956",
        "short_name": "HA",
        "year": 1956,
        "keywords": ["health act", "public health", "sanitation", "disease"],
        "topics": ["public health", "sanitation", "disease"],
        "url": "https://www.legislation.govt.nz/act/public/1956/0065/latest/DLM305840.html"
    },
    "MA": {
        "title": "Medicines Act 1981",
        "short_name": "MA",
        "year": 1981,
        "keywords": ["medicines", "pharmacy", "prescription", "drug"],
        "topics": ["medicine", "pharmacy", "prescription"],
        "url": "https://www.legislation.govt.nz/act/public/1981/0118/latest/DLM53790.html"
    },
    "SEA": {
        "title": "Smokefree Environments and Regulated Products Act 1990",
        "short_name": "SEA",
        "year": 1990,
        "keywords": ["smokefree", "smoking", "tobacco", "vaping"],
        "topics": ["smoking", "tobacco", "vaping"],
        "url": "https://www.legislation.govt.nz/act/public/1990/0108/latest/DLM223191.html"
    },
    "CDEM": {
        "title": "Civil Defence Emergency Management Act 2002",
        "short_name": "CDEM",
        "year": 2002,
        "keywords": ["civil defence", "emergency management", "cdem", "disaster", "emergency"],
        "topics": ["civil defence", "emergency", "disaster response"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0033/latest/DLM149789.html"
    },
    "HPCA": {
        "title": "Health Practitioners Competence Assurance Act 2003",
        "short_name": "HPCA",
        "year": 2003,
        "keywords": ["health practitioners", "medical registration", "competence", "hpca"],
        "topics": ["health practitioners", "registration", "competence"],
        "url": "https://www.legislation.govt.nz/act/public/2003/0048/latest/DLM203312.html"
    },
    "HNZPT": {
        "title": "Heritage New Zealand Pouhere Taonga Act 2014",
        "short_name": "HNZPT",
        "year": 2014,
        "keywords": ["heritage", "pouhere taonga", "historic places", "archaeological"],
        "topics": ["heritage", "historic places", "archaeology"],
        "url": "https://www.legislation.govt.nz/act/public/2014/0026/latest/DLM4005414.html"
    },
    "LEA": {
        "title": "Local Electoral Act 2001",
        "short_name": "LEA",
        "year": 2001,
        "keywords": ["local electoral", "local elections", "council elections", "sts voting"],
        "topics": ["local elections", "voting", "councils"],
        "url": "https://www.legislation.govt.nz/act/public/2001/0035/latest/DLM93301.html"
    },
    "LGA1974": {
        "title": "Local Government Act 1974",
        "short_name": "LGA1974",
        "year": 1974,
        "keywords": ["local government 1974", "roads", "drainage", "public works"],
        "topics": ["local government", "roads", "public works"],
        "url": "https://www.legislation.govt.nz/act/public/1974/0066/latest/DLM415532.html"
    },
    "LGACA": {
        "title": "Local Government (Auckland Council) Act 2009",
        "short_name": "LGACA",
        "year": 2009,
        "keywords": ["auckland council", "auckland supercity", "auckland local government"],
        "topics": ["Auckland", "council", "local government"],
        "url": "https://www.legislation.govt.nz/act/public/2009/0032/latest/DLM2044909.html"
    },
    "LGOIMA": {
        "title": "Local Government Official Information and Meetings Act 1987",
        "short_name": "LGOIMA",
        "year": 1987,
        "keywords": ["lgoima", "local government official information", "council meetings", "council information"],
        "topics": ["official information", "meetings", "councils"],
        "url": "https://www.legislation.govt.nz/act/public/1987/0174/latest/DLM122242.html"
    },
    "LGRA": {
        "title": "Local Government (Rating) Act 2002",
        "short_name": "LGRA",
        "year": 2002,
        "keywords": ["rating", "rates", "council rates", "property rates"],
        "topics": ["rates", "rating", "property tax"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0006/latest/DLM131394.html"
    },
    "MFA": {
        "title": "Maori Fisheries Act 2004",
        "short_name": "MFA",
        "year": 2004,
        "keywords": ["maori fisheries", "te ohu kaimoana", "iwi fisheries", "settlement assets"],
        "topics": ["Maori fisheries", "Te Ohu Kaimoana", "iwi"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0078/latest/DLM311464.html"
    },
    "MCAA": {
        "title": "Marine and Coastal Area (Takutai Moana) Act 2011",
        "short_name": "MCAA",
        "year": 2011,
        "keywords": ["marine coastal area", "takutai moana", "foreshore seabed", "customary rights"],
        "topics": ["marine area", "coastal", "customary rights"],
        "url": "https://www.legislation.govt.nz/act/public/2011/0003/latest/DLM3213131.html"
    },
    "NWMWR": {
        "title": "Nga Wai o Maniapoto (Waipa River) Act 2012",
        "short_name": "NWMWR",
        "year": 2012,
        "keywords": ["maniapoto", "waipa river", "nga wai o maniapoto"],
        "topics": ["Waipa River", "Maniapoto", "treaty settlement"],
        "url": "https://www.legislation.govt.nz/act/public/2012/0029/latest/DLM3335204.html"
    },
    "NTCS": {
        "title": "Ngai Tahu Claims Settlement Act 1998",
        "short_name": "NTCS",
        "year": 1998,
        "keywords": ["ngai tahu", "ngai tahu settlement", "south island iwi"],
        "topics": ["Ngai Tahu", "treaty settlement", "South Island"],
        "url": "https://www.legislation.govt.nz/act/public/1998/0097/latest/DLM429090.html"
    },
    "NTRTA": {
        "title": "Ngati Tuwharetoa, Raukawa, and Te Arawa River Iwi Waikato River Act 2010",
        "short_name": "NTRTA",
        "year": 2010,
        "keywords": ["ngati tuwharetoa", "raukawa", "te arawa", "waikato river"],
        "topics": ["Waikato River", "river iwi", "treaty settlement"],
        "url": "https://www.legislation.govt.nz/act/public/2010/0119/latest/DLM2921815.html"
    },
    "OTA": {
        "title": "Oranga Tamariki Act 1989",
        "short_name": "OTA",
        "year": 1989,
        "keywords": ["oranga tamariki", "children young persons", "child protection", "youth justice", "cyf"],
        "topics": ["child protection", "youth justice", "welfare"],
        "url": "https://www.legislation.govt.nz/act/public/1989/0024/latest/DLM147088.html"
    },
    "PA1993": {
        "title": "Privacy Act 1993",
        "short_name": "PA1993",
        "year": 1993,
        "keywords": ["privacy 1993", "old privacy act", "information privacy"],
        "topics": ["privacy", "personal information", "data protection"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0028/latest/DLM296639.html"
    },
    "RRA": {
        "title": "Rates Rebate Act 1973",
        "short_name": "RRA",
        "year": 1973,
        "keywords": ["rates rebate", "rates relief", "low income rates"],
        "topics": ["rates rebate", "low income", "relief"],
        "url": "https://www.legislation.govt.nz/act/public/1973/0005/latest/DLM409766.html"
    },
    "RVA": {
        "title": "Rating Valuations Act 1998",
        "short_name": "RVA",
        "year": 1998,
        "keywords": ["rating valuations", "property valuation", "qv", "valuation roll"],
        "topics": ["valuations", "property", "rating"],
        "url": "https://www.legislation.govt.nz/act/public/1998/0069/latest/DLM427297.html"
    },
    "RA": {
        "title": "Reserves Act 1977",
        "short_name": "RA",
        "year": 1977,
        "keywords": ["reserves", "reserve land", "recreation reserves", "scenic reserves"],
        "topics": ["reserves", "recreation", "conservation"],
        "url": "https://www.legislation.govt.nz/act/public/1977/0066/latest/DLM444305.html"
    },
    "TAT": {
        "title": "Te Awa Tupua (Whanganui River Claims Settlement) Act 2017",
        "short_name": "TAT",
        "year": 2017,
        "keywords": ["te awa tupua", "whanganui river", "river personhood", "whanganui settlement"],
        "topics": ["Whanganui River", "legal personhood", "treaty settlement"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0007/latest/DLM6830851.html"
    },
    "TRMA": {
        "title": "Te Ture mo Te Reo Maori 2016 (Maori Language Act)",
        "short_name": "TRMA",
        "year": 2016,
        "keywords": ["te reo maori", "maori language", "te taura whiri", "te matawai"],
        "topics": ["Te Reo Maori", "language", "revitalisation"],
        "url": "https://www.legislation.govt.nz/act/public/2016/0017/latest/DLM6174509.html"
    },
    "TRNT": {
        "title": "Te Runanga o Ngai Tahu Act 1996",
        "short_name": "TRNT",
        "year": 1996,
        "keywords": ["te runanga o ngai tahu", "ngai tahu governance", "ngai tahu runanga"],
        "topics": ["Ngai Tahu", "governance", "iwi"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0001/latest/DLM371876.html"
    },
    "TTWM": {
        "title": "Te Ture Whenua Maori Act 1993 (Maori Land Act)",
        "short_name": "TTWM",
        "year": 1993,
        "keywords": ["te ture whenua", "maori land", "maori land court", "whenua maori"],
        "topics": ["Maori land", "land court", "succession"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0004/latest/DLM289882.html"
    },
    "TUA": {
        "title": "Te Urewera Act 2014",
        "short_name": "TUA",
        "year": 2014,
        "keywords": ["te urewera", "tuhoe", "urewera national park"],
        "topics": ["Te Urewera", "Tuhoe", "treaty settlement"],
        "url": "https://www.legislation.govt.nz/act/public/2014/0051/latest/DLM6183601.html"
    },
    "TOWA": {
        "title": "Treaty of Waitangi Act 1975",
        "short_name": "TOWA",
        "year": 1975,
        "keywords": ["treaty of waitangi", "waitangi tribunal", "treaty claims"],
        "topics": ["Treaty of Waitangi", "Waitangi Tribunal", "claims"],
        "url": "https://www.legislation.govt.nz/act/public/1975/0114/latest/DLM435368.html"
    },
    "TOWFS": {
        "title": "Treaty of Waitangi (Fisheries Claims) Settlement Act 1992",
        "short_name": "TOWFS",
        "year": 1992,
        "keywords": ["sealord deal", "fisheries settlement", "treaty fisheries"],
        "topics": ["fisheries settlement", "Sealord", "Treaty"],
        "url": "https://www.legislation.govt.nz/act/public/1992/0121/latest/DLM281433.html"
    },
    "WRCS": {
        "title": "Waikato Raupatu Claims Settlement Act 1995",
        "short_name": "WRCS",
        "year": 1995,
        "keywords": ["waikato raupatu", "tainui settlement", "waikato-tainui"],
        "topics": ["Waikato-Tainui", "raupatu", "treaty settlement"],
        "url": "https://www.legislation.govt.nz/act/public/1995/0058/latest/DLM370102.html"
    },
    "WTWR": {
        "title": "Waikato-Tainui Raupatu Claims (Waikato River) Settlement Act 2010",
        "short_name": "WTWR",
        "year": 2010,
        "keywords": ["waikato river settlement", "waikato-tainui river", "river settlement"],
        "topics": ["Waikato River", "Waikato-Tainui", "river settlement"],
        "url": "https://www.legislation.govt.nz/act/public/2010/0024/latest/DLM1630002.html"
    },
    "SA": {
        "title": "Sentencing Act 2002",
        "short_name": "SA",
        "year": 2002,
        "keywords": ["sentencing act", "sentencing", "sentence", "imprisonment", "home detention", "community detention", "discharge", "fine"],
        "topics": ["sentencing", "imprisonment", "community sentences"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0009/latest/DLM135342.html"
    },
    "CPA": {
        "title": "Criminal Procedure Act 2011",
        "short_name": "CPA",
        "year": 2011,
        "keywords": ["criminal procedure", "criminal procedure act", "charge", "plea", "trial", "jury trial", "prosecution", "judge-alone trial"],
        "topics": ["criminal procedure", "trials", "charges"],
        "url": "https://www.legislation.govt.nz/act/public/2011/0081/latest/DLM3359902.html"
    },
    "EVA": {
        "title": "Evidence Act 2006",
        "short_name": "EVA",
        "year": 2006,
        "keywords": ["evidence act", "admissibility", "hearsay", "witness", "privilege", "propensity evidence", "testimony"],
        "topics": ["evidence", "admissibility", "witnesses"],
        "url": "https://www.legislation.govt.nz/act/public/2006/0069/latest/DLM393462.html"
    },
    "BAIL": {
        "title": "Bail Act 2000",
        "short_name": "BAIL",
        "year": 2000,
        "keywords": ["bail act", "bail", "remand", "custody", "surety", "bail conditions"],
        "topics": ["bail", "remand", "conditions"],
        "url": "https://www.legislation.govt.nz/act/public/2000/0038/latest/DLM68380.html"
    },
    "COCA": {
        "title": "Care of Children Act 2004",
        "short_name": "COCA",
        "year": 2004,
        "keywords": ["coca", "care of children", "custody", "guardianship", "parenting order", "day-to-day care", "contact order"],
        "topics": ["children", "guardianship", "parenting orders"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0090/latest/DLM317233.html"
    },
    "PRA": {
        "title": "Property (Relationships) Act 1976",
        "short_name": "PRA",
        "year": 1976,
        "keywords": ["pra", "property relationships", "relationship property", "matrimonial property", "separation", "de facto", "division of property"],
        "topics": ["relationship property", "separation", "division"],
        "url": "https://www.legislation.govt.nz/act/public/1976/0166/latest/DLM440945.html"
    },
    "LA": {
        "title": "Limitation Act 2010",
        "short_name": "LA",
        "year": 2010,
        "keywords": ["limitation act", "limitation period", "time bar", "statute of limitations", "limitation"],
        "topics": ["limitation periods", "time bars", "claims"],
        "url": "https://www.legislation.govt.nz/act/public/2010/0110/latest/DLM2033101.html"
    },
    "LCA": {
        "title": "Lawyers and Conveyancers Act 2006",
        "short_name": "LCA",
        "year": 2006,
        "keywords": ["lawyers and conveyancers", "lawyer", "conveyancer", "legal profession", "practising certificate", "trust account", "law society"],
        "topics": ["legal profession", "conduct", "discipline"],
        "url": "https://www.legislation.govt.nz/act/public/2006/0001/latest/DLM364939.html"
    },
    "SSA": {
        "title": "Search and Surveillance Act 2012",
        "short_name": "SSA",
        "year": 2012,
        "keywords": ["search and surveillance", "search warrant", "surveillance", "interception", "seizure", "police search"],
        "topics": ["search warrants", "surveillance", "police powers"],
        "url": "https://www.legislation.govt.nz/act/public/2012/0024/latest/DLM2136536.html"
    },
    "PPPR": {
        "title": "Protection of Personal and Property Rights Act 1988",
        "short_name": "PPPR",
        "year": 1988,
        "keywords": ["pppr", "personal and property rights", "enduring power of attorney", "welfare guardian", "property manager", "epa", "capacity"],
        "topics": ["enduring powers of attorney", "welfare guardians", "capacity"],
        "url": "https://www.legislation.govt.nz/act/public/1988/0004/latest/DLM126528.html"
    },
    "WSA": {
        "title": "Water Services Act 2021",
        "short_name": "WSA",
        "year": 2021,
        "keywords": ["water services", "drinking water", "water supply", "water infrastructure"],
        "topics": ["water", "infrastructure"],
        "url": "https://www.legislation.govt.nz/act/public/2021/0036/latest/DLM1.html"
    },
    "ETrA": {
        "title": "Education and Training Act 2020",
        "short_name": "ETrA",
        "year": 2020,
        "keywords": ["education", "training", "school", "teacher", "university", "tertiary"],
        "topics": ["education", "training"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0038/latest/DLM1.html"
    },
    "CPHRA": {
        "title": "COVID-19 Public Health Response Act 2020",
        "short_name": "CPHRA",
        "year": 2020,
        "keywords": ["covid", "pandemic", "public health", "lockdown", "vaccination order"],
        "topics": ["public health", "emergency"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0012/latest/DLM1.html"
    },
    "URBA": {
        "title": "Urban Development Act 2020",
        "short_name": "URBA",
        "year": 2020,
        "keywords": ["urban development", "kainga ora", "housing", "urban"],
        "topics": ["urban development", "housing"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0042/latest/DLM1.html"
    },
    "INFRA": {
        "title": "Infrastructure Funding and Financing Act 2020",
        "short_name": "INFRA",
        "year": 2020,
        "keywords": ["infrastructure", "funding", "financing", "levy"],
        "topics": ["infrastructure", "finance"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0047/latest/DLM1.html"
    },
    "CPA2018": {
        "title": "Child Poverty Reduction Act 2018",
        "short_name": "CPA2018",
        "year": 2018,
        "keywords": ["child poverty", "poverty reduction", "children"],
        "topics": ["poverty", "children"],
        "url": "https://www.legislation.govt.nz/act/public/2018/0057/latest/DLM1.html"
    },
    "SATA": {
        "title": "Substance Addiction (Compulsory Assessment and Treatment) Act 2017",
        "short_name": "SATA",
        "year": 2017,
        "keywords": ["substance addiction", "compulsory treatment", "addiction", "drugs"],
        "topics": ["health", "addiction"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0004/latest/DLM1.html"
    },
    "ISA": {
        "title": "Intelligence and Security Act 2017",
        "short_name": "ISA",
        "year": 2017,
        "keywords": ["intelligence", "security", "gcsb", "nzsis", "surveillance"],
        "topics": ["intelligence", "security"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0010/latest/DLM1.html"
    },
    "SCA": {
        "title": "Senior Courts Act 2016",
        "short_name": "SCA",
        "year": 2016,
        "keywords": ["senior courts", "high court", "court of appeal", "supreme court"],
        "topics": ["courts", "judiciary"],
        "url": "https://www.legislation.govt.nz/act/public/2016/0048/latest/DLM1.html"
    },
    "DCA2016": {
        "title": "District Court Act 2016",
        "short_name": "DCA2016",
        "year": 2016,
        "keywords": ["district court", "court"],
        "topics": ["courts", "judiciary"],
        "url": "https://www.legislation.govt.nz/act/public/2016/0049/latest/DLM1.html"
    },
    "JRPA": {
        "title": "Judicial Review Procedure Act 2016",
        "short_name": "JRPA",
        "year": 2016,
        "keywords": ["judicial review", "review procedure"],
        "topics": ["courts", "judicial review"],
        "url": "https://www.legislation.govt.nz/act/public/2016/0050/latest/DLM1.html"
    },
    "FDA": {
        "title": "Food Act 2014",
        "short_name": "FDA",
        "year": 2014,
        "keywords": ["food", "food safety", "food standards"],
        "topics": ["food safety", "health"],
        "url": "https://www.legislation.govt.nz/act/public/2014/0032/latest/DLM1.html"
    },
    "VSA": {
        "title": "Veterans' Support Act 2014",
        "short_name": "VSA",
        "year": 2014,
        "keywords": ["veterans", "veteran support", "military"],
        "topics": ["veterans", "welfare"],
        "url": "https://www.legislation.govt.nz/act/public/2014/0056/latest/DLM1.html"
    },
    "RESA": {
        "title": "Real Estate Agents Act 2008",
        "short_name": "RESA",
        "year": 2008,
        "keywords": ["real estate", "real estate agent", "property sale"],
        "topics": ["real estate", "property"],
        "url": "https://www.legislation.govt.nz/act/public/2008/0066/latest/DLM1.html"
    },
    "PA2008": {
        "title": "Policing Act 2008",
        "short_name": "PA2008",
        "year": 2008,
        "keywords": ["policing", "police", "law enforcement"],
        "topics": ["police", "law enforcement"],
        "url": "https://www.legislation.govt.nz/act/public/2008/0072/latest/DLM1.html"
    },
    "MVSA": {
        "title": "Motor Vehicle Sales Act 2003",
        "short_name": "MVSA",
        "year": 2003,
        "keywords": ["motor vehicle", "car sales", "vehicle dealer"],
        "topics": ["consumer", "vehicles"],
        "url": "https://www.legislation.govt.nz/act/public/2003/0012/latest/DLM1.html"
    },
    "GA": {
        "title": "Gambling Act 2003",
        "short_name": "GA",
        "year": 2003,
        "keywords": ["gambling", "casino", "pokie", "betting", "lottery"],
        "topics": ["gambling", "regulation"],
        "url": "https://www.legislation.govt.nz/act/public/2003/0051/latest/DLM1.html"
    },
    "CORA2004": {
        "title": "Corrections Act 2004",
        "short_name": "CORA2004",
        "year": 2004,
        "keywords": ["corrections", "prison", "prisoner", "parole", "sentence"],
        "topics": ["corrections", "criminal justice"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0050/latest/DLM1.html"
    },
    "PAROLE": {
        "title": "Parole Act 2002",
        "short_name": "PAROLE",
        "year": 2002,
        "keywords": ["parole", "release", "parole board"],
        "topics": ["parole", "criminal justice"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0010/latest/DLM1.html"
    },
    "VRA": {
        "title": "Victims' Rights Act 2002",
        "short_name": "VRA",
        "year": 2002,
        "keywords": ["victims rights", "victim", "victim impact"],
        "topics": ["victims", "criminal justice"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0039/latest/DLM1.html"
    },
    "CSLA": {
        "title": "Criminal Records (Clean Slate) Act 2004",
        "short_name": "CSLA",
        "year": 2004,
        "keywords": ["clean slate", "criminal record", "conviction"],
        "topics": ["criminal records", "rehabilitation"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0036/latest/DLM1.html"
    },
    "MDA": {
        "title": "Misuse of Drugs Act 1975",
        "short_name": "MDA",
        "year": 1975,
        "keywords": ["drugs", "misuse of drugs", "controlled substance", "cannabis", "methamphetamine"],
        "topics": ["drugs", "criminal law"],
        "url": "https://www.legislation.govt.nz/act/public/1975/0116/latest/DLM1.html"
    },
    "SOA": {
        "title": "Summary Offences Act 1981",
        "short_name": "SOA",
        "year": 1981,
        "keywords": ["summary offences", "minor offences", "disorderly conduct", "trespass"],
        "topics": ["offences", "criminal law"],
        "url": "https://www.legislation.govt.nz/act/public/1981/0113/latest/DLM1.html"
    },
    "ARMSA": {
        "title": "Arms Act 1983",
        "short_name": "ARMSA",
        "year": 1983,
        "keywords": ["arms", "firearms", "gun", "weapon", "licence"],
        "topics": ["firearms", "public safety"],
        "url": "https://www.legislation.govt.nz/act/public/1983/0044/latest/DLM1.html"
    },
    "IPCAA": {
        "title": "Independent Police Conduct Authority Act 1988",
        "short_name": "IPCAA",
        "year": 1988,
        "keywords": ["police conduct", "ipca", "police complaints"],
        "topics": ["police oversight", "accountability"],
        "url": "https://www.legislation.govt.nz/act/public/1988/0002/latest/DLM1.html"
    },
    "NZBORA": {
        "title": "New Zealand Bill of Rights Act 1990",
        "short_name": "NZBORA",
        "year": 1990,
        "keywords": ["bill of rights", "human rights", "civil liberties", "freedom of expression", "right to life"],
        "topics": ["rights", "civil liberties"],
        "url": "https://www.legislation.govt.nz/act/public/1990/0109/latest/DLM1.html"
    },
    "DEFA": {
        "title": "Defence Act 1990",
        "short_name": "DEFA",
        "year": 1990,
        "keywords": ["defence", "military", "armed forces", "nzdf"],
        "topics": ["defence", "military"],
        "url": "https://www.legislation.govt.nz/act/public/1990/0028/latest/DLM1.html"
    },
    "OMBA": {
        "title": "Ombudsmen Act 1975",
        "short_name": "OMBA",
        "year": 1975,
        "keywords": ["ombudsman", "ombudsmen", "complaint", "investigation"],
        "topics": ["ombudsman", "accountability"],
        "url": "https://www.legislation.govt.nz/act/public/1975/0009/latest/DLM1.html"
    },
    "COMA": {
        "title": "Commerce Act 1986",
        "short_name": "COMA",
        "year": 1986,
        "keywords": ["commerce", "competition", "merger", "anti-competitive", "market"],
        "topics": ["competition", "commerce"],
        "url": "https://www.legislation.govt.nz/act/public/1986/0005/latest/DLM1.html"
    },
    "OIA2005": {
        "title": "Overseas Investment Act 2005",
        "short_name": "OIA2005",
        "year": 2005,
        "keywords": ["overseas investment", "foreign investment", "sensitive land"],
        "topics": ["investment", "foreign ownership"],
        "url": "https://www.legislation.govt.nz/act/public/2005/0082/latest/DLM1.html"
    },
    "FSPA": {
        "title": "Financial Service Providers (Registration and Dispute Resolution) Act 2008",
        "short_name": "FSPA",
        "year": 2008,
        "keywords": ["financial service provider", "fsp", "dispute resolution"],
        "topics": ["financial services", "regulation"],
        "url": "https://www.legislation.govt.nz/act/public/2008/0097/latest/DLM1.html"
    },
    "GSTA": {
        "title": "Goods and Services Tax Act 1985",
        "short_name": "GSTA",
        "year": 1985,
        "keywords": ["gst", "goods and services tax", "tax"],
        "topics": ["tax", "gst"],
        "url": "https://www.legislation.govt.nz/act/public/1985/0141/latest/DLM1.html"
    },
    "TAA": {
        "title": "Tax Administration Act 1994",
        "short_name": "TAA",
        "year": 1994,
        "keywords": ["tax administration", "ird", "tax return", "tax compliance"],
        "topics": ["tax", "administration"],
        "url": "https://www.legislation.govt.nz/act/public/1994/0166/latest/DLM1.html"
    },
    "CEA": {
        "title": "Customs and Excise Act 2018",
        "short_name": "CEA",
        "year": 2018,
        "keywords": ["customs", "excise", "import", "export", "border"],
        "topics": ["customs", "trade"],
        "url": "https://www.legislation.govt.nz/act/public/2018/0004/latest/DLM1.html"
    },
    "TELA": {
        "title": "Telecommunications Act 2001",
        "short_name": "TELA",
        "year": 2001,
        "keywords": ["telecommunications", "broadband", "internet", "network"],
        "topics": ["telecommunications", "regulation"],
        "url": "https://www.legislation.govt.nz/act/public/2001/0103/latest/DLM1.html"
    },
    "ARBA": {
        "title": "Arbitration Act 1996",
        "short_name": "ARBA",
        "year": 1996,
        "keywords": ["arbitration", "dispute", "arbitral tribunal"],
        "topics": ["arbitration", "dispute resolution"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0099/latest/DLM1.html"
    },
    "DTA": {
        "title": "Disputes Tribunal Act 1988",
        "short_name": "DTA",
        "year": 1988,
        "keywords": ["disputes tribunal", "small claims", "dispute"],
        "topics": ["disputes", "tribunal"],
        "url": "https://www.legislation.govt.nz/act/public/1988/0110/latest/DLM1.html"
    },
    "WHRS": {
        "title": "Weathertight Homes Resolution Services Act 2006",
        "short_name": "WHRS",
        "year": 2006,
        "keywords": ["weathertight", "leaky homes", "leaky building"],
        "topics": ["housing", "construction"],
        "url": "https://www.legislation.govt.nz/act/public/2006/0084/latest/DLM1.html"
    },
    "MHCA": {
        "title": "Mental Health (Compulsory Assessment and Treatment) Act 1992",
        "short_name": "MHCA",
        "year": 1992,
        "keywords": ["mental health", "compulsory treatment", "psychiatric"],
        "topics": ["mental health", "health"],
        "url": "https://www.legislation.govt.nz/act/public/1992/0046/latest/DLM1.html"
    },
    "HDCA1994": {
        "title": "Health and Disability Commissioner Act 1994",
        "short_name": "HDCA1994",
        "year": 1994,
        "keywords": ["health commissioner", "disability commissioner", "patient rights", "hdc"],
        "topics": ["health", "disability"],
        "url": "https://www.legislation.govt.nz/act/public/1994/0088/latest/DLM1.html"
    },
    "SSA2018": {
        "title": "Social Security Act 2018",
        "short_name": "SSA2018",
        "year": 2018,
        "keywords": ["social security", "benefit", "welfare", "jobseeker", "sole parent"],
        "topics": ["welfare", "benefits"],
        "url": "https://www.legislation.govt.nz/act/public/2018/0032/latest/DLM1.html"
    },
    "SWRA": {
        "title": "Social Workers Registration Act 2003",
        "short_name": "SWRA",
        "year": 2003,
        "keywords": ["social worker", "registration", "social work"],
        "topics": ["social work", "registration"],
        "url": "https://www.legislation.govt.nz/act/public/2003/0017/latest/DLM1.html"
    },
    "NZPHDA": {
        "title": "New Zealand Public Health and Disability Act 2000",
        "short_name": "NZPHDA",
        "year": 2000,
        "keywords": ["public health", "disability", "dhb", "health board"],
        "topics": ["public health", "disability"],
        "url": "https://www.legislation.govt.nz/act/public/2000/0091/latest/DLM1.html"
    },
    "AWA": {
        "title": "Animal Welfare Act 1999",
        "short_name": "AWA",
        "year": 1999,
        "keywords": ["animal welfare", "animal cruelty", "animal"],
        "topics": ["animal welfare"],
        "url": "https://www.legislation.govt.nz/act/public/1999/0142/latest/DLM1.html"
    },
    "DCA1996": {
        "title": "Dog Control Act 1996",
        "short_name": "DCA1996",
        "year": 1996,
        "keywords": ["dog control", "dog", "dangerous dog", "menacing dog"],
        "topics": ["dog control", "animals"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0013/latest/DLM1.html"
    },
    "BURIALS": {
        "title": "Burial and Cremation Act 1964",
        "short_name": "BURIALS",
        "year": 1964,
        "keywords": ["burial", "cremation", "funeral", "cemetery"],
        "topics": ["burial", "cremation"],
        "url": "https://www.legislation.govt.nz/act/public/1964/0075/latest/DLM1.html"
    },
    "CEA2004": {
        "title": "Crown Entities Act 2004",
        "short_name": "CEA2004",
        "year": 2004,
        "keywords": ["crown entity", "statutory entity", "crown agent"],
        "topics": ["governance", "public sector"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0115/latest/DLM1.html"
    },
    "LEGA": {
        "title": "Legislation Act 2019",
        "short_name": "LEGA",
        "year": 2019,
        "keywords": ["legislation", "interpretation", "statutory interpretation", "enactment"],
        "topics": ["legislation", "interpretation"],
        "url": "https://www.legislation.govt.nz/act/public/2019/0058/latest/DLM1.html"
    },
    "MTA": {
        "title": "Maritime Transport Act 1994",
        "short_name": "MTA",
        "year": 1994,
        "keywords": ["maritime", "shipping", "vessel", "port", "sea"],
        "topics": ["maritime", "transport"],
        "url": "https://www.legislation.govt.nz/act/public/1994/0104/latest/DLM1.html"
    },
    "CAA": {
        "title": "Civil Aviation Act 1990",
        "short_name": "CAA",
        "year": 1990,
        "keywords": ["civil aviation", "aircraft", "aviation", "airline", "pilot"],
        "topics": ["aviation", "transport"],
        "url": "https://www.legislation.govt.nz/act/public/1990/0098/latest/DLM1.html"
    },
    "RA2005": {
        "title": "Railways Act 2005",
        "short_name": "RA2005",
        "year": 2005,
        "keywords": ["railways", "rail", "train", "rail network"],
        "topics": ["railways", "transport"],
        "url": "https://www.legislation.govt.nz/act/public/2005/0037/latest/DLM1.html"
    },
    "GOVA": {
        "title": "Government Roading Powers Act 1989",
        "short_name": "GOVA",
        "year": 1989,
        "keywords": ["roading", "road", "highway", "motorway"],
        "topics": ["roading", "transport"],
        "url": "https://www.legislation.govt.nz/act/public/1989/0075/latest/DLM1.html"
    },
    "CMA": {
        "title": "Crown Minerals Act 1991",
        "short_name": "CMA",
        "year": 1991,
        "keywords": ["crown minerals", "mining", "petroleum", "minerals"],
        "topics": ["minerals", "mining"],
        "url": "https://www.legislation.govt.nz/act/public/1991/0070/latest/DLM1.html"
    },
    "EPA": {
        "title": "Environmental Protection Authority Act 2011",
        "short_name": "EPA",
        "year": 2011,
        "keywords": ["epa", "environmental protection", "environment"],
        "topics": ["environment", "regulation"],
        "url": "https://www.legislation.govt.nz/act/public/2011/0014/latest/DLM1.html"
    },
    "FRRA": {
        "title": "Forestry Rights Registration Act 1983",
        "short_name": "FRRA",
        "year": 1983,
        "keywords": ["forestry", "forestry rights", "timber"],
        "topics": ["forestry", "land"],
        "url": "https://www.legislation.govt.nz/act/public/1983/0042/latest/DLM1.html"
    },
    "ELECA": {
        "title": "Electricity Act 1992",
        "short_name": "ELECA",
        "year": 1992,
        "keywords": ["electricity", "power", "energy", "electrical"],
        "topics": ["electricity", "energy"],
        "url": "https://www.legislation.govt.nz/act/public/1992/0122/latest/DLM1.html"
    },
    "GASA": {
        "title": "Gas Act 1992",
        "short_name": "GASA",
        "year": 1992,
        "keywords": ["gas", "natural gas", "gas supply"],
        "topics": ["gas", "energy"],
        "url": "https://www.legislation.govt.nz/act/public/1992/0124/latest/DLM1.html"
    },
    "TSSA": {
        "title": "Telecommunications (Interception Capability and Security) Act 2013",
        "short_name": "TSSA",
        "year": 2013,
        "keywords": ["interception", "surveillance", "telecommunications security"],
        "topics": ["telecommunications", "security"],
        "url": "https://www.legislation.govt.nz/act/public/2013/0091/latest/DLM1.html"
    },
    "LATA": {
        "title": "Local Authorities (Members' Interests) Act 1968",
        "short_name": "LATA",
        "year": 1968,
        "keywords": ["members interests", "local authority", "conflict of interest"],
        "topics": ["local government", "integrity"],
        "url": "https://www.legislation.govt.nz/act/public/1968/0147/latest/whole.html"
    },
    "RDA": {
        "title": "Referenda (Postal Voting) Act 2000",
        "short_name": "RDA",
        "year": 2000,
        "keywords": ["referendum", "postal voting", "vote"],
        "topics": ["elections", "referendums"],
        "url": "https://www.legislation.govt.nz/act/public/2000/0048/latest/whole.html"
    },
    "CIR": {
        "title": "Citizens Initiated Referenda Act 1993",
        "short_name": "CIR",
        "year": 1993,
        "keywords": ["citizens referendum", "initiated referendum", "petition"],
        "topics": ["democracy", "referendums"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0101/latest/whole.html"
    },
    "IGISA": {
        "title": "Inspector-General of Intelligence and Security Act 1996",
        "short_name": "IGISA",
        "year": 1996,
        "keywords": ["inspector general", "intelligence oversight"],
        "topics": ["intelligence", "oversight"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0047/latest/whole.html"
    },
    "FVPCA": {
        "title": "Films, Videos, and Publications Classification Act 1993",
        "short_name": "FVPCA",
        "year": 1993,
        "keywords": ["classification", "censorship", "films", "publications", "objectionable"],
        "topics": ["classification", "censorship"],
        "url": "https://www.legislation.govt.nz/act/public/1993/0094/latest/whole.html"
    },
    "RBNZA": {
        "title": "Reserve Bank of New Zealand Act 2021",
        "short_name": "RBNZA",
        "year": 2021,
        "keywords": ["reserve bank", "monetary policy", "financial stability", "rbnz"],
        "topics": ["banking", "monetary policy"],
        "url": "https://www.legislation.govt.nz/act/public/2021/0031/latest/whole.html"
    },
    "PPSA": {
        "title": "Personal Property Securities Act 1999",
        "short_name": "PPSA",
        "year": 1999,
        "keywords": ["personal property", "security interest", "ppsr", "financing statement"],
        "topics": ["property", "security"],
        "url": "https://www.legislation.govt.nz/act/public/1999/0126/latest/whole.html"
    },
    "CCEA": {
        "title": "Construction Contracts Act 2002",
        "short_name": "CCEA",
        "year": 2002,
        "keywords": ["construction contract", "payment claim", "adjudication"],
        "topics": ["construction", "contracts"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0046/latest/whole.html"
    },
    "LTA2017": {
        "title": "Land Transfer Act 2017",
        "short_name": "LTA2017",
        "year": 2017,
        "keywords": ["land transfer", "torrens", "record of title"],
        "topics": ["land", "property"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0030/latest/whole.html"
    },
    "CSA": {
        "title": "Cadastral Survey Act 2002",
        "short_name": "CSA",
        "year": 2002,
        "keywords": ["cadastral", "survey", "land survey", "boundary"],
        "topics": ["survey", "land"],
        "url": "https://www.legislation.govt.nz/act/public/2002/0012/latest/whole.html"
    },
    "PWA": {
        "title": "Public Works Act 1981",
        "short_name": "PWA",
        "year": 1981,
        "keywords": ["public works act", "compulsory acquisition", "land taking"],
        "topics": ["land acquisition", "public works"],
        "url": "https://www.legislation.govt.nz/act/public/1981/0035/latest/whole.html"
    },
    "FFA": {
        "title": "Fencing Act 1978",
        "short_name": "FFA",
        "year": 1978,
        "keywords": ["fencing", "fence", "boundary fence", "neighbour"],
        "topics": ["fencing", "property"],
        "url": "https://www.legislation.govt.nz/act/public/1978/0050/latest/whole.html"
    },
    "AUPA": {
        "title": "Auctioneers Act 2013",
        "short_name": "AUPA",
        "year": 2013,
        "keywords": ["auctioneer", "auction"],
        "topics": ["auctions", "regulation"],
        "url": "https://www.legislation.govt.nz/act/public/2013/0148/latest/whole.html"
    },
    "HNA": {
        "title": "Public and Community Housing Management Act 1992",
        "short_name": "HNA",
        "year": 1992,
        "keywords": ["housing restructuring", "state housing", "housing nz"],
        "topics": ["housing", "tenancy"],
        "url": "https://www.legislation.govt.nz/act/public/1992/0076/latest/whole.html"
    },
    "SULA": {
        "title": "Resource Management (Simplifying and Streamlining) Amendment Act 2009",
        "short_name": "SULA",
        "year": 2009,
        "keywords": ["simplifying and streamlining"],
        "topics": ["subdivision", "planning"],
        "url": "https://www.legislation.govt.nz/act/public/2009/0031/latest/whole.html"
    },
    "RAPA": {
        "title": "Raukawa Claims Settlement Act 2014",
        "short_name": "RAPA",
        "year": 2014,
        "keywords": ["raukawa claims"],
        "topics": ["treaty settlements"],
        "url": "https://www.legislation.govt.nz/act/public/2014/0007/latest/whole.html"
    },
    "TAPA": {
        "title": "Tapuika Claims Settlement Act 2014",
        "short_name": "TAPA",
        "year": 2014,
        "keywords": ["tapuika", "claims settlement"],
        "topics": ["treaty settlements"],
        "url": "https://www.legislation.govt.nz/act/public/2014/0015/latest/whole.html"
    },
    "NTTSA": {
        "title": "Ngati Tuwharetoa Claims Settlement Act 2018",
        "short_name": "NTTSA",
        "year": 2018,
        "keywords": ["ngati tuwharetoa claims", "tuwharetoa claims"],
        "topics": ["treaty settlements"],
        "url": "https://www.legislation.govt.nz/act/public/2018/0055/latest/whole.html"
    },
    "TWMA": {
        "title": "Te Ture Whenua Maori (Succession, Dispute Resolution, and Related Matters) Amendment Act 2020",
        "short_name": "TWMA",
        "year": 2020,
        "keywords": ["te ture whenua maori amendment"],
        "topics": ["Maori land", "succession"],
        "url": "https://www.legislation.govt.nz/act/public/2020/0051/latest/whole.html"
    },
    "EXTR": {
        "title": "Extradition Act 1999",
        "short_name": "EXTR",
        "year": 1999,
        "keywords": ["extradition", "surrender", "fugitive"],
        "topics": ["extradition", "international"],
        "url": "https://www.legislation.govt.nz/act/public/1999/0055/latest/whole.html"
    },
    "MLAT": {
        "title": "Mutual Assistance in Criminal Matters Act 1992",
        "short_name": "MLAT",
        "year": 1992,
        "keywords": ["mutual assistance", "criminal matters", "international cooperation"],
        "topics": ["international", "criminal law"],
        "url": "https://www.legislation.govt.nz/act/public/1992/0086/latest/whole.html"
    },
    "DIPA": {
        "title": "Diplomatic Privileges and Immunities Act 1968",
        "short_name": "DIPA",
        "year": 1968,
        "keywords": ["diplomatic", "immunity", "privileges"],
        "topics": ["diplomacy", "international"],
        "url": "https://www.legislation.govt.nz/act/public/1968/0036/latest/whole.html"
    },
    "ICCA": {
        "title": "International Crimes and International Criminal Court Act 2000",
        "short_name": "ICCA",
        "year": 2000,
        "keywords": ["international crimes", "icc", "war crimes", "genocide"],
        "topics": ["international law", "criminal law"],
        "url": "https://www.legislation.govt.nz/act/public/2000/0026/latest/whole.html"
    },
    "CHMA": {
        "title": "Chemical Weapons (Prohibition) Act 1996",
        "short_name": "CHMA",
        "year": 1996,
        "keywords": ["chemical weapons", "prohibition", "arms control"],
        "topics": ["arms control", "international"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0037/latest/whole.html"
    },
    "NWFA": {
        "title": "New Zealand Nuclear Free Zone, Disarmament, and Arms Control Act 1987",
        "short_name": "NWFA",
        "year": 1987,
        "keywords": ["nuclear free", "disarmament", "arms control", "nuclear"],
        "topics": ["nuclear", "disarmament"],
        "url": "https://www.legislation.govt.nz/act/public/1987/0086/latest/whole.html"
    },
    "GENA": {
        "title": "Geneva Conventions Act 1958",
        "short_name": "GENA",
        "year": 1958,
        "keywords": ["geneva conventions", "war", "humanitarian law"],
        "topics": ["international humanitarian law"],
        "url": "https://www.legislation.govt.nz/act/public/1958/0019/latest/whole.html"
    },
    "AEA": {
        "title": "Anti-Money Laundering and Countering Financing of Terrorism Amendment Act 2017",
        "short_name": "AEA",
        "year": 2017,
        "keywords": ["aml/cft amendment", "anti-money laundering amendment"],
        "topics": ["money laundering", "regulation"],
        "url": "https://www.legislation.govt.nz/act/public/2017/0035/latest/whole.html"
    },
    "PROCA": {
        "title": "Criminal Proceeds (Recovery) Act 2009",
        "short_name": "PROCA",
        "year": 2009,
        "keywords": ["criminal proceeds", "asset forfeiture", "proceeds of crime"],
        "topics": ["criminal proceeds", "law enforcement"],
        "url": "https://www.legislation.govt.nz/act/public/2009/0008/latest/whole.html"
    },
    "WINA": {
        "title": "Wine Act 2003",
        "short_name": "WINA",
        "year": 2003,
        "keywords": ["wine", "winemaking", "viticulture"],
        "topics": ["wine", "food safety"],
        "url": "https://www.legislation.govt.nz/act/public/2003/0114/latest/whole.html"
    },
    "APA": {
        "title": "Animal Products Act 1999",
        "short_name": "APA",
        "year": 1999,
        "keywords": ["animal products"],
        "topics": ["food safety", "animal products"],
        "url": "https://www.legislation.govt.nz/act/public/1999/0093/latest/whole.html"
    },
    "MARA": {
        "title": "Marine Reserves Act 1971",
        "short_name": "MARA",
        "year": 1971,
        "keywords": ["marine reserve", "marine protection", "ocean"],
        "topics": ["conservation", "marine"],
        "url": "https://www.legislation.govt.nz/act/public/1971/0015/latest/whole.html"
    },
    "NPHA": {
        "title": "National Parks Act 1980",
        "short_name": "NPHA",
        "year": 1980,
        "keywords": ["national parks"],
        "topics": ["conservation", "national parks"],
        "url": "https://www.legislation.govt.nz/act/public/1980/0066/latest/whole.html"
    },
    "WCA": {
        "title": "Wildlife Act 1953",
        "short_name": "WCA",
        "year": 1953,
        "keywords": ["wildlife", "protected species", "hunting"],
        "topics": ["wildlife", "conservation"],
        "url": "https://www.legislation.govt.nz/act/public/1953/0031/latest/whole.html"
    },
    "WATERA": {
        "title": "Water Services Legislation Act 2023",
        "short_name": "WATERA",
        "year": 2023,
        "keywords": ["water services legislation", "water reform"],
        "topics": ["water", "reform"],
        "url": "https://www.legislation.govt.nz/act/public/2023/0052/latest/whole.html"
    },
    "EEZA": {
        "title": "Exclusive Economic Zone and Continental Shelf (Environmental Effects) Act 2012",
        "short_name": "EEZA",
        "year": 2012,
        "keywords": ["eez", "continental shelf", "marine environment"],
        "topics": ["marine", "environment"],
        "url": "https://www.legislation.govt.nz/act/public/2012/0072/latest/whole.html"
    },
    "WRMA": {
        "title": "Waste Minimisation Act 2008",
        "short_name": "WRMA",
        "year": 2008,
        "keywords": ["waste", "recycling", "waste minimisation", "landfill"],
        "topics": ["waste", "environment"],
        "url": "https://www.legislation.govt.nz/act/public/2008/0089/latest/whole.html"
    },
    "OZLA": {
        "title": "Ozone Layer Protection Act 1996",
        "short_name": "OZLA",
        "year": 1996,
        "keywords": ["ozone", "ozone layer", "atmosphere"],
        "topics": ["environment", "atmosphere"],
        "url": "https://www.legislation.govt.nz/act/public/1996/0040/latest/whole.html"
    },
    "FORA": {
        "title": "Forests Act 1949",
        "short_name": "FORA",
        "year": 1949,
        "keywords": ["forests act"],
        "topics": ["forestry", "conservation"],
        "url": "https://www.legislation.govt.nz/act/public/1949/0019/latest/whole.html"
    },
    "AQUA": {
        "title": "Aquaculture Reform (Repeals and Transitional Provisions) Act 2004",
        "short_name": "AQUA",
        "year": 2004,
        "keywords": ["aquaculture", "marine farming", "fish farming"],
        "topics": ["aquaculture", "marine"],
        "url": "https://www.legislation.govt.nz/act/public/2004/0109/latest/whole.html"
    },
}


# =============================================================================
# Act detection
# =============================================================================
#
# Detection act-filters retrieval, so a wrong answer here is worse than no
# answer: the response silently cites the wrong statute. The matcher therefore
# scores every act that matches and only commits when one is clearly ahead.
#
# Scoring: each matched keyword is worth (words * _WORD_WEIGHT + characters), so
# a multi-word keyword always outranks any number of characters of a single-word
# one. An act's score is the sum over its matched keywords.

_WORD_WEIGHT = 1000

# The winner must beat the runner-up by at least this much. 100 sits above any
# plausible character-count difference between two single-word keywords and
# below one whole word, so the rule reads: win on matched words, not on
# incidental keyword length. Ties are ambiguous and yield None.
_DETECTION_MARGIN = 100

# Keywords too ambiguous to select an act on their own. They still add to an
# act's score once something stronger has matched, but an act whose *only*
# evidence is an ambiguous keyword is never chosen — retrieval decides instead.
# Two recurring failure shapes are represented here: ordinary English words that
# happen to be a keyword, and words naming the *actor* in a question rather than
# its subject-matter. Every entry is a wrong citation observed in C-001 triage
# or the first swarm run:
#
#   "power to make laws"           -> Electricity Act           (power)
#   "if the police arrest me"      -> Policing Act              (police)
#   "use force in self defence"    -> Defence Act               (defence)
#   "duties do company officers"   -> Companies Act             (company)
#   "consumer contracts"           -> Consumer Guarantees       (consumer)
#   "never supplying the goods"    -> Sale of Goods Act         (goods)
#   "unfair contract terms"        -> Contract and Commercial   (contract)
#   "search and seizure"           -> Search and Surveillance   (seizure)
#   "business charge extra"        -> Criminal Procedure        (charge)
#   "request from a government agency" -> Public Service        (government agency)
#   "a New Zealand citizen"        -> Citizenship Act           (citizen)
#   "can my employer check my social media" -> Employment Relations (employer)
#
# See the C-002 report for the registry keyword changes proposed alongside this.
_WEAK_KEYWORDS = frozenset({
    "power",       # Electricity Act — "power to make laws", "powers of entry"
    "police",      # Policing Act — most police questions are about other acts
    "defence",     # Defence Act — collides with the defence of self-defence
    "company",     # Companies Act — any business question mentions a company
    "consumer",    # Consumer Guarantees — collides with Fair Trading
    "goods",       # Sale of Goods — collides with Consumer Guarantees / FTA
    "contract",    # Contract and Commercial Law — every area of law has contracts
    "contracts",
    "seizure",     # Search and Surveillance — collides with NZBORA s21
    "dispute",     # claimed by both Arbitration and Disputes Tribunals
    "leave",       # Employment Relations — ordinary English verb
    "charge",      # Criminal Procedure — "charge a fee" vs "charged with"
    "citizen",     # Citizenship Act — names the person, not the subject
    "employer",    # Employment Relations — names the actor; the subject is
                   # often privacy, health and safety, or tax
    "government agency",  # Public Service — names the actor in any question
                          # about dealing with government
})


def _keyword_score(keyword: str) -> int:
    """Word count dominates; characters break ties within the same word count."""
    return _WORD_WEIGHT * len(keyword.split()) + len(keyword)


def _build_keyword_index():
    """Precompile every keyword pattern once, at import."""
    index = []
    for short_name, act_info in ACTS_REGISTRY.items():
        entries = []
        for kw in act_info["keywords"]:
            kw_lower = kw.lower()
            # Word boundaries stop 'pla' matching 'explain'.
            pattern = re.compile(r'\b' + re.escape(kw_lower) + r'\b')
            entries.append((pattern, _keyword_score(kw_lower),
                            kw_lower in _WEAK_KEYWORDS))
        index.append((short_name, act_info, entries))
    return index


_KEYWORD_INDEX = _build_keyword_index()


def _act_base_name(act_info: Dict) -> str:
    """The filter string search_similar() matches against act_title."""
    title = act_info["title"]
    return title.rsplit(" Act", 1)[0] if " Act" in title else title


def score_acts_for_query(query: str) -> List[Dict]:
    """Every act matching `query`, best first. Exposed for tests and triage."""
    query_lower = query.lower()
    scored = []

    for short_name, act_info, entries in _KEYWORD_INDEX:
        score = 0
        matched = 0
        has_strong = False
        for pattern, kw_score, is_weak in entries:
            if pattern.search(query_lower):
                score += kw_score
                matched += 1
                if not is_weak:
                    has_strong = True
        if matched:
            scored.append({
                "short_name": short_name,
                "base_name": _act_base_name(act_info),
                "score": score,
                "matched": matched,
                "has_strong": has_strong,
            })

    scored.sort(key=lambda a: (a["score"], a["matched"]), reverse=True)
    return scored


def has_registry_signal(query: str) -> bool:
    """True if the query mentions ANY registry keyword, strong or ambiguous.

    Deliberately separate from detect_act_from_query(). A question can carry a
    real legal signal ("can my employer...", "a business charged me...") without
    there being enough evidence to commit to an act filter. Retrieval and
    filtering are different decisions: this answers "is this a legal question?",
    detection answers "which act do we restrict to?".

    Conflating the two is what C-002 broke — the gate treated a detected act as
    its only registry evidence, so tightening detection silently made the gate
    reject questions it used to accept.
    """
    query_lower = query.lower()
    for _short_name, _act_info, entries in _KEYWORD_INDEX:
        for pattern, _score, _is_weak in entries:
            if pattern.search(query_lower):
                return True
    return False


def detect_act_from_query(query: str) -> Optional[str]:
    """Detect which Act a query is about, or None if it is not clear.

    Returns the act's base name (title without " Act <year>"), which
    search_similar() uses as its act filter. Returns None when nothing matches,
    when the only evidence is a weak keyword, or when two acts are within
    _DETECTION_MARGIN of each other — in those cases an unfiltered search is
    safer than a confidently wrong citation.
    """
    candidates = [a for a in score_acts_for_query(query) if a["has_strong"]]
    if not candidates:
        return None

    best = candidates[0]
    if len(candidates) > 1:
        runner_up = candidates[1]
        if best["score"] - runner_up["score"] < _DETECTION_MARGIN:
            return None

    return best["base_name"]


def get_all_acts() -> List[Dict]:
    """Get all acts as a list for the API."""
    return [
        {
            "short_name": short_name,
            "title": info["title"],
            "year": info["year"],
            "topics": info["topics"],
            "url": info["url"]
        }
        for short_name, info in ACTS_REGISTRY.items()
    ]


def get_act_by_short_name(short_name: str) -> Optional[Dict]:
    """Get a specific act by its short name."""
    return ACTS_REGISTRY.get(short_name.upper())
