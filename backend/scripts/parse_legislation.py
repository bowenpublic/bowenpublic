#!/usr/bin/env python3
"""
parse_legislation.py

Parses HTML files from legislation.govt.nz and extracts structured content.
Outputs JSON files with sections, definitions, and metadata.

Run from the magna root directory:
    cd ~/Desktop/bowenpublic
    python backend/scripts/parse_legislation.py
"""

import os
import re
import html
import json
import unicodedata
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional


# Configuration - paths relative to magna root
RAW_HTML_DIR = Path("data/raw/html")
OUTPUT_DIR = Path("data/processed/json")

# Act metadata - maps filename to metadata
ACT_METADATA = {
    "accident-compensation-act-2001.html": {
        "title": "Accident Compensation Act 2001",
        "year": 2001,
        "number": 49,
        "url": "https://www.legislation.govt.nz/act/public/2001/0049/latest/whole.html",
        "short_name": "ACA",
        "topics": ["ACC", "injury", "compensation", "rehabilitation", "cover"]
    },
    "aml-cft-amendment-2017.html": {
        "title": "Anti-Money Laundering and Countering Financing of Terrorism Amendment Act 2017",
        "year": 2017,
        "number": 35,
        "url": "https://www.legislation.govt.nz/act/public/2017/0035/latest/whole.html",
        "short_name": "AEA",
        "topics": ["aml", "cft", "money laundering", "terrorism financing"]
    },
    "animal-products-1999.html": {
        "title": "Animal Products Act 1999",
        "year": 1999,
        "number": 93,
        "url": "https://www.legislation.govt.nz/act/public/1999/0093/latest/whole.html",
        "short_name": "APA",
        "topics": ["animal products", "meat", "dairy", "food safety"]
    },
    "animal-welfare-1999.html": {
        "title": "Animal Welfare Act 1999",
        "year": 1999,
        "number": 142,
        "url": "https://www.legislation.govt.nz/act/public/1999/0142/latest/whole.html",
        "short_name": "AWA",
        "topics": ["animal welfare", "animal cruelty", "animal"]
    },
    "anti-money-laundering-2009.html": {
        "title": "Anti-Money Laundering and Countering Financing of Terrorism Act 2009",
        "year": 2009,
        "number": 35,
        "url": "https://www.legislation.govt.nz/act/public/2009/0035/latest/whole.html",
        "short_name": "AML",
        "topics": ["money laundering", "terrorism financing", "reporting", "compliance"]
    },
    "aquaculture-reform-2004.html": {
        "title": "Aquaculture Reform (Repeals and Transitional Provisions) Act 2004",
        "year": 2004,
        "number": 109,
        "url": "https://www.legislation.govt.nz/act/public/2004/0109/latest/whole.html",
        "short_name": "AQUA",
        "topics": ["aquaculture", "marine farming", "fish farming"]
    },
    "arbitration-1996.html": {
        "title": "Arbitration Act 1996",
        "year": 1996,
        "number": 99,
        "url": "https://www.legislation.govt.nz/act/public/1996/0099/latest/whole.html",
        "short_name": "ARBA",
        "topics": ["arbitration", "dispute", "arbitral tribunal"]
    },
    "arms-1983.html": {
        "title": "Arms Act 1983",
        "year": 1983,
        "number": 44,
        "url": "https://www.legislation.govt.nz/act/public/1983/0044/latest/whole.html",
        "short_name": "ARMSA",
        "topics": ["arms", "firearms", "gun", "weapon", "licence"]
    },
    "auctioneers-2013.html": {
        "title": "Auctioneers Act 2013",
        "year": 2013,
        "number": 148,
        "url": "https://www.legislation.govt.nz/act/public/2013/0148/latest/whole.html",
        "short_name": "AUPA",
        "topics": ["auctioneer", "auction"]
    },
    "bail-2000.html": {
        "title": "Bail Act 2000",
        "year": 2000,
        "number": 38,
        "url": "https://www.legislation.govt.nz/act/public/2000/0038/latest/whole.html",
        "short_name": "BAIL",
        "topics": ["bail", "remand", "custody", "surety", "conditions", "arrest"]
    },
    "biosecurity-1993.html": {
        "title": "Biosecurity Act 1993",
        "year": 1993,
        "number": 95,
        "url": "https://www.legislation.govt.nz/act/public/1993/0095/latest/whole.html",
        "short_name": "BSA",
        "topics": ["biosecurity", "pest", "border", "quarantine", "organism"]
    },
    "building-2004.html": {
        "title": "Building Act 2004",
        "year": 2004,
        "number": 72,
        "url": "https://www.legislation.govt.nz/act/public/2004/0072/latest/whole.html",
        "short_name": "BA",
        "topics": ["building", "consent", "code", "construction", "inspection"]
    },
    "burial-cremation-1964.html": {
        "title": "Burial and Cremation Act 1964",
        "year": 1964,
        "number": 75,
        "url": "https://www.legislation.govt.nz/act/public/1964/0075/latest/whole.html",
        "short_name": "BURIALS",
        "topics": ["burial", "cremation", "funeral", "cemetery"]
    },
    "cadastral-survey-2002.html": {
        "title": "Cadastral Survey Act 2002",
        "year": 2002,
        "number": 12,
        "url": "https://www.legislation.govt.nz/act/public/2002/0012/latest/whole.html",
        "short_name": "CSA",
        "topics": ["cadastral", "survey", "land survey", "boundary"]
    },
    "care-of-children-2004.html": {
        "title": "Care of Children Act 2004",
        "year": 2004,
        "number": 90,
        "url": "https://www.legislation.govt.nz/act/public/2004/0090/latest/whole.html",
        "short_name": "COCA",
        "topics": ["children", "custody", "guardianship", "parenting order", "care", "welfare"]
    },
    "chemical-weapons-prohibition-1996.html": {
        "title": "Chemical Weapons (Prohibition) Act 1996",
        "year": 1996,
        "number": 37,
        "url": "https://www.legislation.govt.nz/act/public/1996/0037/latest/whole.html",
        "short_name": "CHMA",
        "topics": ["chemical weapons", "prohibition", "arms control"]
    },
    "child-poverty-reduction-2018.html": {
        "title": "Child Poverty Reduction Act 2018",
        "year": 2018,
        "number": 57,
        "url": "https://www.legislation.govt.nz/act/public/2018/0057/latest/whole.html",
        "short_name": "CPA2018",
        "topics": ["child poverty", "poverty reduction", "children"]
    },
    "citizens-initiated-referenda-1993.html": {
        "title": "Citizens Initiated Referenda Act 1993",
        "year": 1993,
        "number": 101,
        "url": "https://www.legislation.govt.nz/act/public/1993/0101/latest/whole.html",
        "short_name": "CIR",
        "topics": ["citizens referendum", "initiated referendum", "petition"]
    },
    "citizenship-1977.html": {
        "title": "Citizenship Act 1977",
        "year": 1977,
        "number": 61,
        "url": "https://www.legislation.govt.nz/act/public/1977/0061/latest/whole.html",
        "short_name": "CITZ",
        "topics": ["citizenship", "naturalisation", "passport", "nationality"]
    },
    "civil-aviation-1990.html": {
        "title": "Civil Aviation Act 1990",
        "year": 1990,
        "number": 98,
        "url": "https://www.legislation.govt.nz/act/public/1990/0098/latest/whole.html",
        "short_name": "CAA",
        "topics": ["civil aviation", "aircraft", "aviation", "airline", "pilot"]
    },
    "civil-defence-emergency-management-2002.html": {
        "title": "Civil Defence Emergency Management Act 2002",
        "year": 2002,
        "number": 33,
        "url": "https://www.legislation.govt.nz/act/public/2002/0033/latest/whole.html",
        "short_name": "CDEM",
        "topics": ["civil defence", "emergency", "disaster response"]
    },
    "climate-change-response-2002.html": {
        "title": "Climate Change Response Act 2002",
        "year": 2002,
        "number": 40,
        "url": "https://www.legislation.govt.nz/act/public/2002/0040/latest/whole.html",
        "short_name": "CCRA",
        "topics": ["climate change", "emissions", "carbon", "ETS"]
    },
    "commerce-1986.html": {
        "title": "Commerce Act 1986",
        "year": 1986,
        "number": 5,
        "url": "https://www.legislation.govt.nz/act/public/1986/0005/latest/whole.html",
        "short_name": "COMA",
        "topics": ["commerce", "competition", "merger", "anti-competitive", "market"]
    },
    "companies-1993.html": {
        "title": "Companies Act 1993",
        "year": 1993,
        "number": 105,
        "url": "https://www.legislation.govt.nz/act/public/1993/0105/latest/whole.html",
        "short_name": "CA",
        "topics": ["company", "director", "shareholder", "incorporation", "liquidation"]
    },
    "conservation-1987.html": {
        "title": "Conservation Act 1987",
        "year": 1987,
        "number": 65,
        "url": "https://www.legislation.govt.nz/act/public/1987/0065/latest/whole.html",
        "short_name": "CONS",
        "topics": ["conservation", "DOC", "national park", "wildlife", "nature"]
    },
    "constitution-1986.html": {
        "title": "Constitution Act 1986",
        "year": 1986,
        "number": 114,
        "url": "https://www.legislation.govt.nz/act/public/1986/0114/latest/whole.html",
        "short_name": "CONST",
        "topics": ["constitution", "parliament", "sovereign", "government"]
    },
    "construction-contracts-2002.html": {
        "title": "Construction Contracts Act 2002",
        "year": 2002,
        "number": 46,
        "url": "https://www.legislation.govt.nz/act/public/2002/0046/latest/whole.html",
        "short_name": "CCEA",
        "topics": ["construction contract", "payment claim", "adjudication"]
    },
    "consumer-guarantees-1993.html": {
        "title": "Consumer Guarantees Act 1993",
        "year": 1993,
        "number": 91,
        "url": "https://www.legislation.govt.nz/act/public/1993/0091/latest/whole.html",
        "short_name": "CGA",
        "topics": ["consumer", "guarantee", "refund", "repair", "goods", "services"]
    },
    "contract-commercial-law-2017.html": {
        "title": "Contract and Commercial Law Act 2017",
        "year": 2017,
        "number": 5,
        "url": "https://www.legislation.govt.nz/act/public/2017/0005/latest/whole.html",
        "short_name": "CCLA",
        "topics": ["contract", "sale", "goods", "carriage", "mercantile", "privity"]
    },
    "copyright-1994.html": {
        "title": "Copyright Act 1994",
        "year": 1994,
        "number": 143,
        "url": "https://www.legislation.govt.nz/act/public/1994/0143/latest/whole.html",
        "short_name": "CRA",
        "topics": ["copyright", "intellectual property", "infringement", "licence", "moral rights"]
    },
    "coroners-2006.html": {
        "title": "Coroners Act 2006",
        "year": 2006,
        "number": 38,
        "url": "https://www.legislation.govt.nz/act/public/2006/0038/latest/whole.html",
        "short_name": "CORA",
        "topics": ["coroner", "death", "inquest", "inquiry"]
    },
    "corrections-2004.html": {
        "title": "Corrections Act 2004",
        "year": 2004,
        "number": 50,
        "url": "https://www.legislation.govt.nz/act/public/2004/0050/latest/whole.html",
        "short_name": "CORA2004",
        "topics": ["corrections", "prison", "prisoner", "parole", "sentence"]
    },
    "covid-19-public-health-response-2020.html": {
        "title": "COVID-19 Public Health Response Act 2020",
        "year": 2020,
        "number": 12,
        "url": "https://www.legislation.govt.nz/act/public/2020/0012/latest/whole.html",
        "short_name": "CPHRA",
        "topics": ["covid", "pandemic", "public health", "lockdown", "vaccination order"]
    },
    "credit-contracts-2003.html": {
        "title": "Credit Contracts and Consumer Finance Act 2003",
        "year": 2003,
        "number": 52,
        "url": "https://www.legislation.govt.nz/act/public/2003/0052/latest/whole.html",
        "short_name": "CCCFA",
        "topics": ["credit", "loan", "interest", "consumer finance", "lender", "borrower"]
    },
    "crimes-1961.html": {
        "title": "Crimes Act 1961",
        "year": 1961,
        "number": 43,
        "url": "https://www.legislation.govt.nz/act/public/1961/0043/latest/whole.html",
        "short_name": "CA1961",
        "topics": ["criminal", "offence", "murder", "assault", "theft", "fraud", "sentence"]
    },
    "criminal-procedure-2011.html": {
        "title": "Criminal Procedure Act 2011",
        "year": 2011,
        "number": 81,
        "url": "https://www.legislation.govt.nz/act/public/2011/0081/latest/whole.html",
        "short_name": "CPA",
        "topics": ["criminal procedure", "charge", "plea", "trial", "jury", "appeal", "prosecution"]
    },
    "criminal-proceeds-recovery-2009.html": {
        "title": "Criminal Proceeds (Recovery) Act 2009",
        "year": 2009,
        "number": 8,
        "url": "https://www.legislation.govt.nz/act/public/2009/0008/latest/whole.html",
        "short_name": "PROCA",
        "topics": ["criminal proceeds", "asset forfeiture", "proceeds of crime"]
    },
    "criminal-records-clean-slate-2004.html": {
        "title": "Criminal Records (Clean Slate) Act 2004",
        "year": 2004,
        "number": 36,
        "url": "https://www.legislation.govt.nz/act/public/2004/0036/latest/whole.html",
        "short_name": "CSLA",
        "topics": ["clean slate", "criminal record", "conviction"]
    },
    "crown-entities-2004.html": {
        "title": "Crown Entities Act 2004",
        "year": 2004,
        "number": 115,
        "url": "https://www.legislation.govt.nz/act/public/2004/0115/latest/whole.html",
        "short_name": "CEA2004",
        "topics": ["crown entity", "statutory entity", "crown agent"]
    },
    "crown-minerals-1991.html": {
        "title": "Crown Minerals Act 1991",
        "year": 1991,
        "number": 70,
        "url": "https://www.legislation.govt.nz/act/public/1991/0070/latest/whole.html",
        "short_name": "CMA",
        "topics": ["crown minerals", "mining", "petroleum", "minerals"]
    },
    "customs-excise-2018.html": {
        "title": "Customs and Excise Act 2018",
        "year": 2018,
        "number": 4,
        "url": "https://www.legislation.govt.nz/act/public/2018/0004/latest/whole.html",
        "short_name": "CEA",
        "topics": ["customs", "excise", "import", "export", "border"]
    },
    "defence-1990.html": {
        "title": "Defence Act 1990",
        "year": 1990,
        "number": 28,
        "url": "https://www.legislation.govt.nz/act/public/1990/0028/latest/whole.html",
        "short_name": "DEFA",
        "topics": ["defence", "military", "armed forces", "nzdf"]
    },
    "diplomatic-privileges-immunities-1968.html": {
        "title": "Diplomatic Privileges and Immunities Act 1968",
        "year": 1968,
        "number": 36,
        "url": "https://www.legislation.govt.nz/act/public/1968/0036/latest/whole.html",
        "short_name": "DIPA",
        "topics": ["diplomatic", "immunity", "privileges"]
    },
    "disputes-tribunals-1988.html": {
        "title": "Disputes Tribunal Act 1988",
        "year": 1988,
        "number": 110,
        "url": "https://www.legislation.govt.nz/act/public/1988/0110/latest/whole.html",
        "short_name": "DTA",
        "topics": ["disputes tribunal", "small claims", "dispute"]
    },
    "district-court-2016.html": {
        "title": "District Court Act 2016",
        "year": 2016,
        "number": 49,
        "url": "https://www.legislation.govt.nz/act/public/2016/0049/latest/whole.html",
        "short_name": "DCA2016",
        "topics": ["district court", "court"]
    },
    "district-courts-1947.html": {
        "title": "District Courts Act 1947",
        "year": 1947,
        "number": 16,
        "url": "https://www.legislation.govt.nz/act/public/1947/0016/latest/whole.html",
        "short_name": "DCA",
        "topics": ["district court", "jurisdiction", "judge", "civil", "criminal"]
    },
    "dog-control-1996.html": {
        "title": "Dog Control Act 1996",
        "year": 1996,
        "number": 13,
        "url": "https://www.legislation.govt.nz/act/public/1996/0013/latest/whole.html",
        "short_name": "DCA1996",
        "topics": ["dog control", "dog", "dangerous dog", "menacing dog"]
    },
    "education-training-2020.html": {
        "title": "Education and Training Act 2020",
        "year": 2020,
        "number": 38,
        "url": "https://www.legislation.govt.nz/act/public/2020/0038/latest/whole.html",
        "short_name": "ETrA",
        "topics": ["education", "training", "school", "teacher", "university", "tertiary"]
    },
    "electoral-act-1993.html": {
        "title": "Electoral Act 1993",
        "year": 1993,
        "number": 87,
        "url": "https://www.legislation.govt.nz/act/public/1993/0087/latest/whole.html",
        "short_name": "ELEC",
        "topics": ["voting", "election", "parliament", "electoral roll", "MMP"]
    },
    "electricity-1992.html": {
        "title": "Electricity Act 1992",
        "year": 1992,
        "number": 122,
        "url": "https://www.legislation.govt.nz/act/public/1992/0122/latest/whole.html",
        "short_name": "ELECA",
        "topics": ["electricity", "power", "energy", "electrical"]
    },
    "employment-relations-2000.html": {
        "title": "Employment Relations Act 2000",
        "year": 2000,
        "number": 24,
        "url": "https://www.legislation.govt.nz/act/public/2000/0024/latest/whole.html",
        "short_name": "ERA",
        "topics": ["employment", "workplace", "union", "dismissal", "leave", "wages"]
    },
    "environmental-protection-authority-2011.html": {
        "title": "Environmental Protection Authority Act 2011",
        "year": 2011,
        "number": 14,
        "url": "https://www.legislation.govt.nz/act/public/2011/0014/latest/whole.html",
        "short_name": "EPA",
        "topics": ["epa", "environmental protection", "environment"]
    },
    "evidence-2006.html": {
        "title": "Evidence Act 2006",
        "year": 2006,
        "number": 69,
        "url": "https://www.legislation.govt.nz/act/public/2006/0069/latest/whole.html",
        "short_name": "EVA",
        "topics": ["evidence", "witness", "hearsay", "admissibility", "privilege", "testimony"]
    },
    "exclusive-economic-zone-2012.html": {
        "title": "Exclusive Economic Zone and Continental Shelf (Environmental Effects) Act 2012",
        "year": 2012,
        "number": 72,
        "url": "https://www.legislation.govt.nz/act/public/2012/0072/latest/whole.html",
        "short_name": "EEZA",
        "topics": ["eez", "continental shelf", "marine environment"]
    },
    "extradition-1999.html": {
        "title": "Extradition Act 1999",
        "year": 1999,
        "number": 55,
        "url": "https://www.legislation.govt.nz/act/public/1999/0055/latest/whole.html",
        "short_name": "EXTR",
        "topics": ["extradition", "surrender", "fugitive"]
    },
    "fair-trading-1986.html": {
        "title": "Fair Trading Act 1986",
        "year": 1986,
        "number": 121,
        "url": "https://www.legislation.govt.nz/act/public/1986/0121/latest/whole.html",
        "short_name": "FTA",
        "topics": ["consumer", "misleading", "deceptive", "unfair", "trade", "advertising"]
    },
    "family-court-1980.html": {
        "title": "Family Court Act 1980",
        "year": 1980,
        "number": 161,
        "url": "https://www.legislation.govt.nz/act/public/1980/0161/latest/whole.html",
        "short_name": "FCA",
        "topics": ["family court", "jurisdiction", "proceedings"]
    },
    "family-violence-2018.html": {
        "title": "Family Violence Act 2018",
        "year": 2018,
        "number": 46,
        "url": "https://www.legislation.govt.nz/act/public/2018/0046/latest/whole.html",
        "short_name": "FVA",
        "topics": ["family violence", "protection order", "domestic", "safety"]
    },
    "fencing-1978.html": {
        "title": "Fencing Act 1978",
        "year": 1978,
        "number": 50,
        "url": "https://www.legislation.govt.nz/act/public/1978/0050/latest/whole.html",
        "short_name": "FFA",
        "topics": ["fencing", "fence", "boundary fence", "neighbour"]
    },
    "films-videos-publications-classification-1993.html": {
        "title": "Films, Videos, and Publications Classification Act 1993",
        "year": 1993,
        "number": 94,
        "url": "https://www.legislation.govt.nz/act/public/1993/0094/latest/whole.html",
        "short_name": "FVPCA",
        "topics": ["classification", "censorship", "films", "publications", "objectionable"]
    },
    "financial-markets-conduct-2013.html": {
        "title": "Financial Markets Conduct Act 2013",
        "year": 2013,
        "number": 69,
        "url": "https://www.legislation.govt.nz/act/public/2013/0069/latest/whole.html",
        "short_name": "FMCA",
        "topics": ["financial markets", "securities", "disclosure", "investment", "FMA"]
    },
    "financial-service-providers-2008.html": {
        "title": "Financial Service Providers (Registration and Dispute Resolution) Act 2008",
        "year": 2008,
        "number": 97,
        "url": "https://www.legislation.govt.nz/act/public/2008/0097/latest/whole.html",
        "short_name": "FSPA",
        "topics": ["financial service provider", "fsp", "dispute resolution"]
    },
    "fire-emergency-2017.html": {
        "title": "Fire and Emergency New Zealand Act 2017",
        "year": 2017,
        "number": 17,
        "url": "https://www.legislation.govt.nz/act/public/2017/0017/latest/whole.html",
        "short_name": "FENZ",
        "topics": ["fire", "emergency", "firefighter", "rescue", "hazard"]
    },
    "fisheries-1996.html": {
        "title": "Fisheries Act 1996",
        "year": 1996,
        "number": 88,
        "url": "https://www.legislation.govt.nz/act/public/1996/0088/latest/whole.html",
        "short_name": "FA",
        "topics": ["fishing", "quota", "marine", "aquaculture", "commercial fishing"]
    },
    "food-2014.html": {
        "title": "Food Act 2014",
        "year": 2014,
        "number": 32,
        "url": "https://www.legislation.govt.nz/act/public/2014/0032/latest/whole.html",
        "short_name": "FDA",
        "topics": ["food", "food safety", "food standards"]
    },
    "forestry-rights-registration-1983.html": {
        "title": "Forestry Rights Registration Act 1983",
        "year": 1983,
        "number": 42,
        "url": "https://www.legislation.govt.nz/act/public/1983/0042/latest/whole.html",
        "short_name": "FRRA",
        "topics": ["forestry", "forestry rights", "timber"]
    },
    "forests-1949.html": {
        "title": "Forests Act 1949",
        "year": 1949,
        "number": 19,
        "url": "https://www.legislation.govt.nz/act/public/1949/0019/latest/whole.html",
        "short_name": "FORA",
        "topics": ["forests", "forestry", "timber", "logging"]
    },
    "freedom-camping-2011.html": {
        "title": "Freedom Camping Act 2011",
        "year": 2011,
        "number": 61,
        "url": "https://www.legislation.govt.nz/act/public/2011/0061/latest/whole.html",
        "short_name": "FCAM",
        "topics": ["camping", "freedom camping", "local authority", "vehicles"]
    },
    "gambling-2003.html": {
        "title": "Gambling Act 2003",
        "year": 2003,
        "number": 51,
        "url": "https://www.legislation.govt.nz/act/public/2003/0051/latest/whole.html",
        "short_name": "GA",
        "topics": ["gambling", "casino", "pokie", "betting", "lottery"]
    },
    "gas-1992.html": {
        "title": "Gas Act 1992",
        "year": 1992,
        "number": 124,
        "url": "https://www.legislation.govt.nz/act/public/1992/0124/latest/whole.html",
        "short_name": "GASA",
        "topics": ["gas", "natural gas", "gas supply"]
    },
    "geneva-conventions-1958.html": {
        "title": "Geneva Conventions Act 1958",
        "year": 1958,
        "number": 19,
        "url": "https://www.legislation.govt.nz/act/public/1958/0019/latest/whole.html",
        "short_name": "GENA",
        "topics": ["geneva conventions", "war", "humanitarian law"]
    },
    "goods-services-tax-1985.html": {
        "title": "Goods and Services Tax Act 1985",
        "year": 1985,
        "number": 141,
        "url": "https://www.legislation.govt.nz/act/public/1985/0141/latest/whole.html",
        "short_name": "GSTA",
        "topics": ["gst", "goods and services tax", "tax"]
    },
    "government-roading-powers-1989.html": {
        "title": "Government Roading Powers Act 1989",
        "year": 1989,
        "number": 75,
        "url": "https://www.legislation.govt.nz/act/public/1989/0075/latest/whole.html",
        "short_name": "GOVA",
        "topics": ["roading", "road", "highway", "motorway"]
    },
    "harmful-digital-communications-2015.html": {
        "title": "Harmful Digital Communications Act 2015",
        "year": 2015,
        "number": 63,
        "url": "https://www.legislation.govt.nz/act/public/2015/0063/latest/whole.html",
        "short_name": "HDCA",
        "topics": ["cyberbullying", "online harassment", "digital", "netsafe"]
    },
    "hazardous-substances-1996.html": {
        "title": "Hazardous Substances and New Organisms Act 1996",
        "year": 1996,
        "number": 30,
        "url": "https://www.legislation.govt.nz/act/public/1996/0030/latest/whole.html",
        "short_name": "HSNO",
        "topics": ["hazardous", "chemicals", "GMO", "organisms", "EPA"]
    },
    "health-1956.html": {
        "title": "Health Act 1956",
        "year": 1956,
        "number": 65,
        "url": "https://www.legislation.govt.nz/act/public/1956/0065/latest/whole.html",
        "short_name": "HA",
        "topics": ["health", "public health", "sanitation", "disease", "medical"]
    },
    "health-disability-commissioner-1994.html": {
        "title": "Health and Disability Commissioner Act 1994",
        "year": 1994,
        "number": 88,
        "url": "https://www.legislation.govt.nz/act/public/1994/0088/latest/whole.html",
        "short_name": "HDCA1994",
        "topics": ["health commissioner", "disability commissioner", "patient rights", "hdc"]
    },
    "health-practitioners-competence-2003.html": {
        "title": "Health Practitioners Competence Assurance Act 2003",
        "year": 2003,
        "number": 48,
        "url": "https://www.legislation.govt.nz/act/public/2003/0048/latest/whole.html",
        "short_name": "HPCA",
        "topics": ["health practitioners", "registration", "competence"]
    },
    "health-safety-work-2015.html": {
        "title": "Health and Safety at Work Act 2015",
        "year": 2015,
        "number": 70,
        "url": "https://www.legislation.govt.nz/act/public/2015/0070/latest/whole.html",
        "short_name": "HSWA",
        "topics": ["workplace", "safety", "health", "PCBU", "worker", "hazard", "risk"]
    },
    "heritage-nz-pouhere-taonga-2014.html": {
        "title": "Heritage New Zealand Pouhere Taonga Act 2014",
        "year": 2014,
        "number": 26,
        "url": "https://www.legislation.govt.nz/act/public/2014/0026/latest/whole.html",
        "short_name": "HNZPT",
        "topics": ["heritage", "historic places", "archaeology"]
    },
    "housing-restructuring-1992.html": {
        "title": "Public and Community Housing Management Act 1992",
        "year": 1992,
        "number": 76,
        "url": "https://www.legislation.govt.nz/act/public/1992/0076/latest/whole.html",
        "short_name": "HNA",
        "topics": ["housing restructuring", "state housing", "housing nz"]
    },
    "human-rights-1993.html": {
        "title": "Human Rights Act 1993",
        "year": 1993,
        "number": 82,
        "url": "https://www.legislation.govt.nz/act/public/1993/0082/latest/whole.html",
        "short_name": "HRA",
        "topics": ["discrimination", "human rights", "equality", "complaint", "tribunal"]
    },
    "immigration-2009.html": {
        "title": "Immigration Act 2009",
        "year": 2009,
        "number": 51,
        "url": "https://www.legislation.govt.nz/act/public/2009/0051/latest/whole.html",
        "short_name": "IA",
        "topics": ["visa", "immigration", "deportation", "residence", "refugee", "border"]
    },
    "income-tax-2007.html": {
        "title": "Income Tax Act 2007",
        "year": 2007,
        "number": 97,
        "url": "https://www.legislation.govt.nz/act/public/2007/0097/latest/whole.html",
        "short_name": "ITA",
        "topics": ["tax", "income", "deduction", "GST", "business", "investment"]
    },
    "independent-police-conduct-authority-1988.html": {
        "title": "Independent Police Conduct Authority Act 1988",
        "year": 1988,
        "number": 2,
        "url": "https://www.legislation.govt.nz/act/public/1988/0002/latest/whole.html",
        "short_name": "IPCAA",
        "topics": ["police conduct", "ipca", "police complaints"]
    },
    "infrastructure-funding-financing-2020.html": {
        "title": "Infrastructure Funding and Financing Act 2020",
        "year": 2020,
        "number": 47,
        "url": "https://www.legislation.govt.nz/act/public/2020/0047/latest/whole.html",
        "short_name": "INFRA",
        "topics": ["infrastructure", "funding", "financing", "levy"]
    },
    "insolvency-2006.html": {
        "title": "Insolvency Act 2006",
        "year": 2006,
        "number": 55,
        "url": "https://www.legislation.govt.nz/act/public/2006/0055/latest/whole.html",
        "short_name": "INSA",
        "topics": ["bankruptcy", "insolvency", "debt", "creditor", "liquidation"]
    },
    "inspector-general-intelligence-security-1996.html": {
        "title": "Inspector-General of Intelligence and Security Act 1996",
        "year": 1996,
        "number": 47,
        "url": "https://www.legislation.govt.nz/act/public/1996/0047/latest/whole.html",
        "short_name": "IGISA",
        "topics": ["inspector general", "intelligence oversight"]
    },
    "intelligence-security-2017.html": {
        "title": "Intelligence and Security Act 2017",
        "year": 2017,
        "number": 10,
        "url": "https://www.legislation.govt.nz/act/public/2017/0010/latest/whole.html",
        "short_name": "ISA",
        "topics": ["intelligence", "security", "gcsb", "nzsis", "surveillance"]
    },
    "international-crimes-icc-2000.html": {
        "title": "International Crimes and International Criminal Court Act 2000",
        "year": 2000,
        "number": 26,
        "url": "https://www.legislation.govt.nz/act/public/2000/0026/latest/whole.html",
        "short_name": "ICCA",
        "topics": ["international crimes", "icc", "war crimes", "genocide"]
    },
    "judicial-review-procedure-2016.html": {
        "title": "Judicial Review Procedure Act 2016",
        "year": 2016,
        "number": 50,
        "url": "https://www.legislation.govt.nz/act/public/2016/0050/latest/whole.html",
        "short_name": "JRPA",
        "topics": ["judicial review", "review procedure"]
    },
    "land-transfer-2017.html": {
        "title": "Land Transfer Act 2017",
        "year": 2017,
        "number": 30,
        "url": "https://www.legislation.govt.nz/act/public/2017/0030/latest/whole.html",
        "short_name": "LTA2017",
        "topics": ["land transfer", "title", "registration", "torrens"]
    },
    "land-transport-1998.html": {
        "title": "Land Transport Act 1998",
        "year": 1998,
        "number": 110,
        "url": "https://www.legislation.govt.nz/act/public/1998/0110/latest/whole.html",
        "short_name": "LTA",
        "topics": ["driving", "licence", "vehicle", "road", "traffic", "transport"]
    },
    "lawyers-conveyancers-2006.html": {
        "title": "Lawyers and Conveyancers Act 2006",
        "year": 2006,
        "number": 1,
        "url": "https://www.legislation.govt.nz/act/public/2006/0001/latest/whole.html",
        "short_name": "LCA",
        "topics": ["lawyer", "conveyancer", "legal profession", "conduct", "discipline", "trust account"]
    },
    "legislation-2019.html": {
        "title": "Legislation Act 2019",
        "year": 2019,
        "number": 58,
        "url": "https://www.legislation.govt.nz/act/public/2019/0058/latest/whole.html",
        "short_name": "LEGA",
        "topics": ["legislation", "interpretation", "statutory interpretation", "enactment"]
    },
    "limitation-2010.html": {
        "title": "Limitation Act 2010",
        "year": 2010,
        "number": 110,
        "url": "https://www.legislation.govt.nz/act/public/2010/0110/latest/whole.html",
        "short_name": "LA",
        "topics": ["limitation", "time bar", "statute of limitations", "claim", "period"]
    },
    "local-authorities-members-interests-1968.html": {
        "title": "Local Authorities (Members' Interests) Act 1968",
        "year": 1968,
        "number": 147,
        "url": "https://www.legislation.govt.nz/act/public/1968/0147/latest/whole.html",
        "short_name": "LATA",
        "topics": ["members interests", "local authority", "conflict of interest"]
    },
    "local-electoral-2001.html": {
        "title": "Local Electoral Act 2001",
        "year": 2001,
        "number": 35,
        "url": "https://www.legislation.govt.nz/act/public/2001/0035/latest/whole.html",
        "short_name": "LEA",
        "topics": ["local elections", "voting", "councils"]
    },
    "local-government-1974.html": {
        "title": "Local Government Act 1974",
        "year": 1974,
        "number": 66,
        "url": "https://www.legislation.govt.nz/act/public/1974/0066/latest/whole.html",
        "short_name": "LGA1974",
        "topics": ["local government", "roads", "public works"]
    },
    "local-government-2002.html": {
        "title": "Local Government Act 2002",
        "year": 2002,
        "number": 84,
        "url": "https://www.legislation.govt.nz/act/public/2002/0084/latest/whole.html",
        "short_name": "LGA",
        "topics": ["council", "local authority", "rates", "bylaws", "planning"]
    },
    "local-government-auckland-council-2009.html": {
        "title": "Local Government (Auckland Council) Act 2009",
        "year": 2009,
        "number": 32,
        "url": "https://www.legislation.govt.nz/act/public/2009/0032/latest/whole.html",
        "short_name": "LGACA",
        "topics": ["Auckland", "council", "local government"]
    },
    "local-government-official-information-1987.html": {
        "title": "Local Government Official Information and Meetings Act 1987",
        "year": 1987,
        "number": 174,
        "url": "https://www.legislation.govt.nz/act/public/1987/0174/latest/whole.html",
        "short_name": "LGOIMA",
        "topics": ["official information", "meetings", "councils"]
    },
    "local-government-rating-2002.html": {
        "title": "Local Government (Rating) Act 2002",
        "year": 2002,
        "number": 6,
        "url": "https://www.legislation.govt.nz/act/public/2002/0006/latest/whole.html",
        "short_name": "LGRA",
        "topics": ["rates", "rating", "property tax"]
    },
    "maori-fisheries-2004.html": {
        "title": "Maori Fisheries Act 2004",
        "year": 2004,
        "number": 78,
        "url": "https://www.legislation.govt.nz/act/public/2004/0078/latest/whole.html",
        "short_name": "MFA",
        "topics": ["Maori fisheries", "Te Ohu Kaimoana", "iwi"]
    },
    "marine-coastal-area-2011.html": {
        "title": "Marine and Coastal Area (Takutai Moana) Act 2011",
        "year": 2011,
        "number": 3,
        "url": "https://www.legislation.govt.nz/act/public/2011/0003/latest/whole.html",
        "short_name": "MCAA",
        "topics": ["marine area", "coastal", "customary rights"]
    },
    "marine-reserves-1971.html": {
        "title": "Marine Reserves Act 1971",
        "year": 1971,
        "number": 15,
        "url": "https://www.legislation.govt.nz/act/public/1971/0015/latest/whole.html",
        "short_name": "MARA",
        "topics": ["marine reserve", "marine protection", "ocean"]
    },
    "maritime-transport-1994.html": {
        "title": "Maritime Transport Act 1994",
        "year": 1994,
        "number": 104,
        "url": "https://www.legislation.govt.nz/act/public/1994/0104/latest/whole.html",
        "short_name": "MTA",
        "topics": ["maritime", "shipping", "vessel", "port", "sea"]
    },
    "medicines-1981.html": {
        "title": "Medicines Act 1981",
        "year": 1981,
        "number": 118,
        "url": "https://www.legislation.govt.nz/act/public/1981/0118/latest/whole.html",
        "short_name": "MA",
        "topics": ["medicine", "pharmacy", "prescription", "drug", "therapeutic"]
    },
    "mental-health-1992.html": {
        "title": "Mental Health (Compulsory Assessment and Treatment) Act 1992",
        "year": 1992,
        "number": 46,
        "url": "https://www.legislation.govt.nz/act/public/1992/0046/latest/whole.html",
        "short_name": "MHCA",
        "topics": ["mental health", "compulsory treatment", "psychiatric"]
    },
    "misuse-of-drugs-1975.html": {
        "title": "Misuse of Drugs Act 1975",
        "year": 1975,
        "number": 116,
        "url": "https://www.legislation.govt.nz/act/public/1975/0116/latest/whole.html",
        "short_name": "MDA",
        "topics": ["drugs", "misuse of drugs", "controlled substance", "cannabis", "methamphetamine"]
    },
    "motor-vehicle-sales-2003.html": {
        "title": "Motor Vehicle Sales Act 2003",
        "year": 2003,
        "number": 12,
        "url": "https://www.legislation.govt.nz/act/public/2003/0012/latest/whole.html",
        "short_name": "MVSA",
        "topics": ["motor vehicle", "car sales", "vehicle dealer"]
    },
    "mutual-assistance-criminal-1992.html": {
        "title": "Mutual Assistance in Criminal Matters Act 1992",
        "year": 1992,
        "number": 86,
        "url": "https://www.legislation.govt.nz/act/public/1992/0086/latest/whole.html",
        "short_name": "MLAT",
        "topics": ["mutual assistance", "criminal matters", "international cooperation"]
    },
    "national-parks-1980.html": {
        "title": "National Parks Act 1980",
        "year": 1980,
        "number": 66,
        "url": "https://www.legislation.govt.nz/act/public/1980/0066/latest/whole.html",
        "short_name": "NPHA",
        "topics": ["national park", "park", "conservation"]
    },
    "new-zealand-bill-of-rights-1990.html": {
        "title": "New Zealand Bill of Rights Act 1990",
        "year": 1990,
        "number": 109,
        "url": "https://www.legislation.govt.nz/act/public/1990/0109/latest/whole.html",
        "short_name": "NZBORA",
        "topics": ["bill of rights", "human rights", "civil liberties", "freedom of expression", "right to life"]
    },
    "nga-wai-maniapoto-waipa-river-2012.html": {
        "title": "Nga Wai o Maniapoto (Waipa River) Act 2012",
        "year": 2012,
        "number": 29,
        "url": "https://www.legislation.govt.nz/act/public/2012/0029/latest/whole.html",
        "short_name": "NWMWR",
        "topics": ["Waipa River", "Maniapoto", "treaty settlement"]
    },
    "ngai-tahu-claims-settlement-1998.html": {
        "title": "Ngai Tahu Claims Settlement Act 1998",
        "year": 1998,
        "number": 97,
        "url": "https://www.legislation.govt.nz/act/public/1998/0097/latest/whole.html",
        "short_name": "NTCS",
        "topics": ["Ngai Tahu", "treaty settlement", "South Island"]
    },
    "ngati-tuwharetoa-claims-2018.html": {
        "title": "Ngati Tuwharetoa Claims Settlement Act 2018",
        "year": 2018,
        "number": 55,
        "url": "https://www.legislation.govt.nz/act/public/2018/0055/latest/whole.html",
        "short_name": "NTTSA",
        "topics": ["ngati tuwharetoa", "claims settlement", "tuwharetoa"]
    },
    "ngati-tuwharetoa-raukawa-te-arawa-river-2010.html": {
        "title": "Ngati Tuwharetoa, Raukawa, and Te Arawa River Iwi Waikato River Act 2010",
        "year": 2010,
        "number": 119,
        "url": "https://www.legislation.govt.nz/act/public/2010/0119/latest/whole.html",
        "short_name": "NTRTA",
        "topics": ["Waikato River", "river iwi", "treaty settlement"]
    },
    "nuclear-free-zone-1987.html": {
        "title": "New Zealand Nuclear Free Zone, Disarmament, and Arms Control Act 1987",
        "year": 1987,
        "number": 86,
        "url": "https://www.legislation.govt.nz/act/public/1987/0086/latest/whole.html",
        "short_name": "NWFA",
        "topics": ["nuclear free", "disarmament", "arms control", "nuclear"]
    },
    "nz-public-health-disability-2000.html": {
        "title": "New Zealand Public Health and Disability Act 2000",
        "year": 2000,
        "number": 91,
        "url": "https://www.legislation.govt.nz/act/public/2000/0091/latest/whole.html",
        "short_name": "NZPHDA",
        "topics": ["public health", "disability", "dhb", "health board"]
    },
    "official-information-1982.html": {
        "title": "Official Information Act 1982",
        "year": 1982,
        "number": 156,
        "url": "https://www.legislation.govt.nz/act/public/1982/0156/latest/whole.html",
        "short_name": "OIA",
        "topics": ["official information", "government", "request", "disclosure", "public"]
    },
    "ombudsmen-1975.html": {
        "title": "Ombudsmen Act 1975",
        "year": 1975,
        "number": 9,
        "url": "https://www.legislation.govt.nz/act/public/1975/0009/latest/whole.html",
        "short_name": "OMBA",
        "topics": ["ombudsman", "ombudsmen", "complaint", "investigation"]
    },
    "oranga-tamariki-1989.html": {
        "title": "Oranga Tamariki Act 1989",
        "year": 1989,
        "number": 24,
        "url": "https://www.legislation.govt.nz/act/public/1989/0024/latest/whole.html",
        "short_name": "OTA",
        "topics": ["child protection", "youth justice", "welfare"]
    },
    "overseas-investment-2005.html": {
        "title": "Overseas Investment Act 2005",
        "year": 2005,
        "number": 82,
        "url": "https://www.legislation.govt.nz/act/public/2005/0082/latest/whole.html",
        "short_name": "OIA2005",
        "topics": ["overseas investment", "foreign investment", "sensitive land"]
    },
    "ozone-layer-protection-1996.html": {
        "title": "Ozone Layer Protection Act 1996",
        "year": 1996,
        "number": 40,
        "url": "https://www.legislation.govt.nz/act/public/1996/0040/latest/whole.html",
        "short_name": "OZLA",
        "topics": ["ozone", "ozone layer", "atmosphere"]
    },
    "parole-2002.html": {
        "title": "Parole Act 2002",
        "year": 2002,
        "number": 10,
        "url": "https://www.legislation.govt.nz/act/public/2002/0010/latest/whole.html",
        "short_name": "PAROLE",
        "topics": ["parole", "release", "parole board"]
    },
    "patents-2013.html": {
        "title": "Patents Act 2013",
        "year": 2013,
        "number": 68,
        "url": "https://www.legislation.govt.nz/act/public/2013/0068/latest/whole.html",
        "short_name": "PATA",
        "topics": ["patent", "invention", "intellectual property", "innovation"]
    },
    "personal-property-securities-1999.html": {
        "title": "Personal Property Securities Act 1999",
        "year": 1999,
        "number": 126,
        "url": "https://www.legislation.govt.nz/act/public/1999/0126/latest/whole.html",
        "short_name": "PPSA",
        "topics": ["personal property", "security interest", "ppsr", "financing statement"]
    },
    "policing-2008.html": {
        "title": "Policing Act 2008",
        "year": 2008,
        "number": 72,
        "url": "https://www.legislation.govt.nz/act/public/2008/0072/latest/whole.html",
        "short_name": "PA2008",
        "topics": ["policing", "police", "law enforcement"]
    },
    "privacy-1993.html": {
        "title": "Privacy Act 1993",
        "year": 1993,
        "number": 28,
        "url": "https://www.legislation.govt.nz/act/public/1993/0028/latest/whole.html",
        "short_name": "PA1993",
        "topics": ["privacy", "personal information", "data", "principles"]
    },
    "privacy-2020.html": {
        "title": "Privacy Act 2020",
        "year": 2020,
        "number": 31,
        "url": "https://www.legislation.govt.nz/act/public/2020/0031/latest/whole.html",
        "short_name": "PA",
        "topics": ["privacy", "personal information", "data", "breach", "access"]
    },
    "property-law-2007.html": {
        "title": "Property Law Act 2007",
        "year": 2007,
        "number": 91,
        "url": "https://www.legislation.govt.nz/act/public/2007/0091/latest/whole.html",
        "short_name": "PLA",
        "topics": ["property", "land", "mortgage", "lease", "covenant", "easement"]
    },
    "property-relationships-1976.html": {
        "title": "Property (Relationships) Act 1976",
        "year": 1976,
        "number": 166,
        "url": "https://www.legislation.govt.nz/act/public/1976/0166/latest/whole.html",
        "short_name": "PRA",
        "topics": ["relationship property", "separation", "matrimonial", "de facto", "division", "spouse"]
    },
    "protection-personal-property-rights-1988.html": {
        "title": "Protection of Personal and Property Rights Act 1988",
        "year": 1988,
        "number": 4,
        "url": "https://www.legislation.govt.nz/act/public/1988/0004/latest/whole.html",
        "short_name": "PPPR",
        "topics": ["enduring power of attorney", "welfare guardian", "personal rights", "property manager", "capacity"]
    },
    "public-finance-1989.html": {
        "title": "Public Finance Act 1989",
        "year": 1989,
        "number": 44,
        "url": "https://www.legislation.govt.nz/act/public/1989/0044/latest/whole.html",
        "short_name": "PFA",
        "topics": ["public finance", "budget", "appropriation", "crown", "accounts"]
    },
    "public-service-2020.html": {
        "title": "Public Service Act 2020",
        "year": 2020,
        "number": 40,
        "url": "https://www.legislation.govt.nz/act/public/2020/0040/latest/whole.html",
        "short_name": "PSA",
        "topics": ["public service", "government", "departments", "employment"]
    },
    "public-works-1981.html": {
        "title": "Public Works Act 1981",
        "year": 1981,
        "number": 35,
        "url": "https://www.legislation.govt.nz/act/public/1981/0035/latest/whole.html",
        "short_name": "PWA",
        "topics": ["public works", "compulsory acquisition", "land taking"]
    },
    "railways-2005.html": {
        "title": "Railways Act 2005",
        "year": 2005,
        "number": 37,
        "url": "https://www.legislation.govt.nz/act/public/2005/0037/latest/whole.html",
        "short_name": "RA2005",
        "topics": ["railways", "rail", "train", "rail network"]
    },
    "rates-rebate-1973.html": {
        "title": "Rates Rebate Act 1973",
        "year": 1973,
        "number": 5,
        "url": "https://www.legislation.govt.nz/act/public/1973/0005/latest/whole.html",
        "short_name": "RRA",
        "topics": ["rates rebate", "low income", "relief"]
    },
    "rating-valuations-1998.html": {
        "title": "Rating Valuations Act 1998",
        "year": 1998,
        "number": 69,
        "url": "https://www.legislation.govt.nz/act/public/1998/0069/latest/whole.html",
        "short_name": "RVA",
        "topics": ["valuations", "property", "rating"]
    },
    "raukawa-claims-settlement-2014.html": {
        "title": "Raukawa Claims Settlement Act 2014",
        "year": 2014,
        "number": 7,
        "url": "https://www.legislation.govt.nz/act/public/2014/0007/latest/whole.html",
        "short_name": "RAPA",
        "topics": ["raukawa", "claims settlement"]
    },
    "real-estate-agents-2008.html": {
        "title": "Real Estate Agents Act 2008",
        "year": 2008,
        "number": 66,
        "url": "https://www.legislation.govt.nz/act/public/2008/0066/latest/whole.html",
        "short_name": "RESA",
        "topics": ["real estate", "real estate agent", "property sale"]
    },
    "referendums-postal-voting-2000.html": {
        "title": "Referenda (Postal Voting) Act 2000",
        "year": 2000,
        "number": 48,
        "url": "https://www.legislation.govt.nz/act/public/2000/0048/latest/whole.html",
        "short_name": "RDA",
        "topics": ["referendum", "postal voting", "vote"]
    },
    "reserve-bank-2021.html": {
        "title": "Reserve Bank of New Zealand Act 2021",
        "year": 2021,
        "number": 31,
        "url": "https://www.legislation.govt.nz/act/public/2021/0031/latest/whole.html",
        "short_name": "RBNZA",
        "topics": ["reserve bank", "monetary policy", "financial stability", "rbnz"]
    },
    "reserves-1977.html": {
        "title": "Reserves Act 1977",
        "year": 1977,
        "number": 66,
        "url": "https://www.legislation.govt.nz/act/public/1977/0066/latest/whole.html",
        "short_name": "RA",
        "topics": ["reserves", "recreation", "conservation"]
    },
    "residential-tenancies-1986.html": {
        "title": "Residential Tenancies Act 1986",
        "year": 1986,
        "number": 120,
        "url": "https://www.legislation.govt.nz/act/public/1986/0120/latest/whole.html",
        "short_name": "RTA",
        "topics": ["tenancy", "rental", "landlord", "tenant", "bond", "housing"]
    },
    "resource-management-1991.html": {
        "title": "Resource Management Act 1991",
        "year": 1991,
        "number": 69,
        "url": "https://www.legislation.govt.nz/act/public/1991/0069/latest/whole.html",
        "short_name": "RMA",
        "topics": ["environment", "resource consent", "planning", "land use", "subdivision"]
    },
    "resource-management-simplifying-2009.html": {
        "title": "Resource Management (Simplifying and Streamlining) Amendment Act 2009",
        "year": 2009,
        "number": 31,
        "url": "https://www.legislation.govt.nz/act/public/2009/0031/latest/whole.html",
        "short_name": "SULA",
        "topics": ["subdivision", "resource consent", "simplifying"]
    },
    "sale-of-goods-1908.html": {
        "title": "Sale of Goods Act 1908",
        "year": 1908,
        "number": 168,
        "url": "https://www.legislation.govt.nz/act/public/1908/0168/latest/whole.html",
        "short_name": "SOGA",
        "topics": ["sale", "goods", "contract", "title", "delivery"]
    },
    "search-surveillance-2012.html": {
        "title": "Search and Surveillance Act 2012",
        "year": 2012,
        "number": 24,
        "url": "https://www.legislation.govt.nz/act/public/2012/0024/latest/whole.html",
        "short_name": "SSA",
        "topics": ["search", "surveillance", "warrant", "interception", "police powers", "seizure"]
    },
    "senior-courts-2016.html": {
        "title": "Senior Courts Act 2016",
        "year": 2016,
        "number": 48,
        "url": "https://www.legislation.govt.nz/act/public/2016/0048/latest/whole.html",
        "short_name": "SCA",
        "topics": ["senior courts", "high court", "court of appeal", "supreme court"]
    },
    "sentencing-2002.html": {
        "title": "Sentencing Act 2002",
        "year": 2002,
        "number": 9,
        "url": "https://www.legislation.govt.nz/act/public/2002/0009/latest/whole.html",
        "short_name": "SA",
        "topics": ["sentencing", "conviction", "imprisonment", "fine", "discharge", "home detention", "community"]
    },
    "smokefree-1990.html": {
        "title": "Smokefree Environments and Regulated Products Act 1990",
        "year": 1990,
        "number": 108,
        "url": "https://www.legislation.govt.nz/act/public/1990/0108/latest/whole.html",
        "short_name": "SEA",
        "topics": ["smoking", "tobacco", "vaping", "smokefree", "health"]
    },
    "social-security-2018.html": {
        "title": "Social Security Act 2018",
        "year": 2018,
        "number": 32,
        "url": "https://www.legislation.govt.nz/act/public/2018/0032/latest/whole.html",
        "short_name": "SSA2018",
        "topics": ["social security", "benefit", "welfare", "jobseeker", "sole parent"]
    },
    "social-workers-registration-2003.html": {
        "title": "Social Workers Registration Act 2003",
        "year": 2003,
        "number": 17,
        "url": "https://www.legislation.govt.nz/act/public/2003/0017/latest/whole.html",
        "short_name": "SWRA",
        "topics": ["social worker", "registration", "social work"]
    },
    "substance-addiction-2017.html": {
        "title": "Substance Addiction (Compulsory Assessment and Treatment) Act 2017",
        "year": 2017,
        "number": 4,
        "url": "https://www.legislation.govt.nz/act/public/2017/0004/latest/whole.html",
        "short_name": "SATA",
        "topics": ["substance addiction", "compulsory treatment", "addiction", "drugs"]
    },
    "summary-offences-1981.html": {
        "title": "Summary Offences Act 1981",
        "year": 1981,
        "number": 113,
        "url": "https://www.legislation.govt.nz/act/public/1981/0113/latest/whole.html",
        "short_name": "SOA",
        "topics": ["summary offences", "minor offences", "disorderly conduct", "trespass"]
    },
    "tapuika-claims-settlement-2014.html": {
        "title": "Tapuika Claims Settlement Act 2014",
        "year": 2014,
        "number": 15,
        "url": "https://www.legislation.govt.nz/act/public/2014/0015/latest/whole.html",
        "short_name": "TAPA",
        "topics": ["tapuika", "claims settlement"]
    },
    "tax-administration-1994.html": {
        "title": "Tax Administration Act 1994",
        "year": 1994,
        "number": 166,
        "url": "https://www.legislation.govt.nz/act/public/1994/0166/latest/whole.html",
        "short_name": "TAA",
        "topics": ["tax administration", "ird", "tax return", "tax compliance"]
    },
    "te-awa-tupua-2017.html": {
        "title": "Te Awa Tupua (Whanganui River Claims Settlement) Act 2017",
        "year": 2017,
        "number": 7,
        "url": "https://www.legislation.govt.nz/act/public/2017/0007/latest/whole.html",
        "short_name": "TAT",
        "topics": ["Whanganui River", "legal personhood", "treaty settlement"]
    },
    "te-reo-maori-2016.html": {
        "title": "Te Ture mo Te Reo Maori 2016 (Maori Language Act)",
        "year": 2016,
        "number": 17,
        "url": "https://www.legislation.govt.nz/act/public/2016/0017/latest/whole.html",
        "short_name": "TRMA",
        "topics": ["Te Reo Maori", "language", "revitalisation"]
    },
    "te-runanga-ngai-tahu-1996.html": {
        "title": "Te Runanga o Ngai Tahu Act 1996",
        "year": 1996,
        "number": 1,
        "url": "https://www.legislation.govt.nz/act/private/1996/0001/latest/whole.html",
        "short_name": "TRNT",
        "topics": ["Ngai Tahu", "governance", "iwi"]
    },
    "te-ture-whenua-maori-1993.html": {
        "title": "Te Ture Whenua Maori Act 1993 (Maori Land Act)",
        "year": 1993,
        "number": 4,
        "url": "https://www.legislation.govt.nz/act/public/1993/0004/latest/whole.html",
        "short_name": "TTWM",
        "topics": ["Maori land", "land court", "succession"]
    },
    "te-ture-whenua-maori-amendment-2020.html": {
        "title": "Te Ture Whenua Maori (Succession, Dispute Resolution, and Related Matters) Amendment Act 2020",
        "year": 2020,
        "number": 51,
        "url": "https://www.legislation.govt.nz/act/public/2020/0051/latest/whole.html",
        "short_name": "TWMA",
        "topics": ["maori land", "te ture whenua", "succession"]
    },
    "te-urewera-2014.html": {
        "title": "Te Urewera Act 2014",
        "year": 2014,
        "number": 51,
        "url": "https://www.legislation.govt.nz/act/public/2014/0051/latest/whole.html",
        "short_name": "TUA",
        "topics": ["Te Urewera", "Tuhoe", "treaty settlement"]
    },
    "telecommunications-2001.html": {
        "title": "Telecommunications Act 2001",
        "year": 2001,
        "number": 103,
        "url": "https://www.legislation.govt.nz/act/public/2001/0103/latest/whole.html",
        "short_name": "TELA",
        "topics": ["telecommunications", "broadband", "internet", "network"]
    },
    "telecommunications-interception-2013.html": {
        "title": "Telecommunications (Interception Capability and Security) Act 2013",
        "year": 2013,
        "number": 91,
        "url": "https://www.legislation.govt.nz/act/public/2013/0091/latest/whole.html",
        "short_name": "TSSA",
        "topics": ["interception", "surveillance", "telecommunications security"]
    },
    "trade-marks-2002.html": {
        "title": "Trade Marks Act 2002",
        "year": 2002,
        "number": 49,
        "url": "https://www.legislation.govt.nz/act/public/2002/0049/latest/whole.html",
        "short_name": "TMA",
        "topics": ["trademark", "brand", "registration", "infringement"]
    },
    "treaty-waitangi-1975.html": {
        "title": "Treaty of Waitangi Act 1975",
        "year": 1975,
        "number": 114,
        "url": "https://www.legislation.govt.nz/act/public/1975/0114/latest/whole.html",
        "short_name": "TOWA",
        "topics": ["Treaty of Waitangi", "Waitangi Tribunal", "claims"]
    },
    "treaty-waitangi-fisheries-settlement-1992.html": {
        "title": "Treaty of Waitangi (Fisheries Claims) Settlement Act 1992",
        "year": 1992,
        "number": 121,
        "url": "https://www.legislation.govt.nz/act/public/1992/0121/latest/whole.html",
        "short_name": "TOWFS",
        "topics": ["fisheries settlement", "Sealord", "Treaty"]
    },
    "trusts-2019.html": {
        "title": "Trusts Act 2019",
        "year": 2019,
        "number": 38,
        "url": "https://www.legislation.govt.nz/act/public/2019/0038/latest/whole.html",
        "short_name": "TA",
        "topics": ["trust", "trustee", "beneficiary", "settlement", "fiduciary"]
    },
    "unit-titles-2010.html": {
        "title": "Unit Titles Act 2010",
        "year": 2010,
        "number": 22,
        "url": "https://www.legislation.govt.nz/act/public/2010/0022/latest/whole.html",
        "short_name": "UTA",
        "topics": ["unit title", "body corporate", "apartment", "strata"]
    },
    "urban-development-2020.html": {
        "title": "Urban Development Act 2020",
        "year": 2020,
        "number": 42,
        "url": "https://www.legislation.govt.nz/act/public/2020/0042/latest/whole.html",
        "short_name": "URBA",
        "topics": ["urban development", "kainga ora", "housing", "urban"]
    },
    "veterans-support-2014.html": {
        "title": "Veterans' Support Act 2014",
        "year": 2014,
        "number": 56,
        "url": "https://www.legislation.govt.nz/act/public/2014/0056/latest/whole.html",
        "short_name": "VSA",
        "topics": ["veterans", "veteran support", "military"]
    },
    "victims-rights-2002.html": {
        "title": "Victims' Rights Act 2002",
        "year": 2002,
        "number": 39,
        "url": "https://www.legislation.govt.nz/act/public/2002/0039/latest/whole.html",
        "short_name": "VRA",
        "topics": ["victims rights", "victim", "victim impact"]
    },
    "waikato-raupatu-claims-settlement-1995.html": {
        "title": "Waikato Raupatu Claims Settlement Act 1995",
        "year": 1995,
        "number": 58,
        "url": "https://www.legislation.govt.nz/act/public/1995/0058/latest/whole.html",
        "short_name": "WRCS",
        "topics": ["Waikato-Tainui", "raupatu", "treaty settlement"]
    },
    "waikato-tainui-waikato-river-2010.html": {
        "title": "Waikato-Tainui Raupatu Claims (Waikato River) Settlement Act 2010",
        "year": 2010,
        "number": 24,
        "url": "https://www.legislation.govt.nz/act/public/2010/0024/latest/whole.html",
        "short_name": "WTWR",
        "topics": ["Waikato River", "Waikato-Tainui", "river settlement"]
    },
    "waste-minimisation-2008.html": {
        "title": "Waste Minimisation Act 2008",
        "year": 2008,
        "number": 89,
        "url": "https://www.legislation.govt.nz/act/public/2008/0089/latest/whole.html",
        "short_name": "WRMA",
        "topics": ["waste", "recycling", "waste minimisation", "landfill"]
    },
    "water-services-2021.html": {
        "title": "Water Services Act 2021",
        "year": 2021,
        "number": 36,
        "url": "https://www.legislation.govt.nz/act/public/2021/0036/latest/whole.html",
        "short_name": "WSA",
        "topics": ["water services", "drinking water", "water supply", "water infrastructure"]
    },
    "water-services-legislation-2023.html": {
        "title": "Water Services Legislation Act 2023",
        "year": 2023,
        "number": 52,
        "url": "https://www.legislation.govt.nz/act/public/2023/0052/latest/whole.html",
        "short_name": "WATERA",
        "topics": ["water services", "water reform"]
    },
    "weathertight-homes-2006.html": {
        "title": "Weathertight Homes Resolution Services Act 2006",
        "year": 2006,
        "number": 84,
        "url": "https://www.legislation.govt.nz/act/public/2006/0084/latest/whole.html",
        "short_name": "WHRS",
        "topics": ["weathertight", "leaky homes", "leaky building"]
    },
    "wildlife-1953.html": {
        "title": "Wildlife Act 1953",
        "year": 1953,
        "number": 31,
        "url": "https://www.legislation.govt.nz/act/public/1953/0031/latest/whole.html",
        "short_name": "WCA",
        "topics": ["wildlife", "protected species", "hunting"]
    },
    "wine-2003.html": {
        "title": "Wine Act 2003",
        "year": 2003,
        "number": 114,
        "url": "https://www.legislation.govt.nz/act/public/2003/0114/latest/whole.html",
        "short_name": "WINA",
        "topics": ["wine", "winemaking", "viticulture"]
    },
}


def clean_text(text: str) -> str:
    """Clean extracted text by normalizing whitespace."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def extract_section_number(heading_text: str) -> Optional[str]:
    """Extract section number from heading text."""
    patterns = [
        r'^(\d+[A-Z]*)\s',
        r'^Section\s+(\d+[A-Z]*)',
        r'^(Schedule\s+\d+[A-Z]*)',
    ]
    for pattern in patterns:
        match = re.match(pattern, heading_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def repair_mojibake(text: str) -> str:
    """Undo UTF-8 text that was decoded as Latin-1 before it was saved.

    Many downloads were written that way, turning "—" into "â€”" and "ā" into
    "Ä". Correctly decoded text fails the round trip and is returned as is.
    """
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _normalise_title(title: str) -> str:
    title = html.unescape(title)
    title = unicodedata.normalize('NFKD', title)
    title = ''.join(c for c in title if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', title.lower())


def extract_page_title(html_content: str) -> str:
    """The Act's own title, from the page's <title> element."""
    match = re.search(r'<title>(.*?)</title>', html_content, re.DOTALL)
    if not match:
        return ""
    title = clean_text(match.group(1))
    title = re.sub(r'\s+No \d+.*$', '', title)   # "... Act 1986 No 120 (as at ...)"
    title = re.sub(r'\s*\|.*$', '', title)        # "... Act 1986 | New Zealand Legislation"
    return html.unescape(title)


def titles_match(expected: str, page_title: str) -> bool:
    """True if the page is the Act the metadata says it is."""
    e, p = _normalise_title(expected), _normalise_title(page_title)
    return bool(e and p) and (e.startswith(p) or p.startswith(e))


def extract_as_at(html_content: str) -> str:
    """The version date the page states ("as at 1 December 2025"), as ISO."""
    match = re.search(r'as at\s*(?:<[^>]+>\s*)*(\d{1,2} \w+ \d{4})', html_content)
    if not match:
        return ""
    try:
        return datetime.strptime(match.group(1), "%d %B %Y").date().isoformat()
    except ValueError:
        return ""


def parse_legislation_html(html_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a legislation HTML file and extract structured content."""
    print(f"  Parsing: {html_path.name}")

    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = repair_mojibake(f.read())

    # Refuse a file whose content is a different Act from its label: the
    # text would be indexed, and cited, under the wrong Act.
    page_title = extract_page_title(html_content)
    if page_title and metadata.get("title") and not titles_match(metadata["title"], page_title):
        raise ValueError(
            f"{html_path.name} is labelled {metadata['title']!r} but contains {page_title!r}")

    soup = BeautifulSoup(html_content, 'lxml')

    output = {
        "metadata": {
            **metadata,
            "as_at": extract_as_at(html_content),
            "parsed_at": datetime.now().isoformat(),
            "source_file": html_path.name
        },
        "sections": [],
        "definitions": []
    }
    
    # Find all section elements - legislation.govt.nz uses 'prov' class.
    # Match the class exactly: a substring match also returns the nested
    # div.prov-body and div.subprov fragments as records of their own, with
    # overlapping text and no section number (NOTES-duplication.md).
    sections = soup.find_all('div', class_='prov')

    if not sections:
        # Fallback: try finding by heading structure
        sections = soup.find_all(['section', 'div'], class_=re.compile(r'section|provision'))
    
    print(f"    Found {len(sections)} provision elements")
    
    current_part = ""
    current_subpart = ""
    
    for section in sections:
        try:
            # Get section ID for URL linking
            section_id = section.get('id', '')
            
            # Find the section heading
            heading_elem = section.find(class_=re.compile(r'prov-heading|heading'))
            if not heading_elem:
                heading_elem = section.find(['h1', 'h2', 'h3', 'h4', 'h5'])
            
            heading = clean_text(heading_elem.get_text()) if heading_elem else ""
            
            # Find section number
            num_elem = section.find(class_=re.compile(r'prov-num|section-num'))
            if not num_elem and heading_elem:
                num_elem = heading_elem.find('span', class_='label')
            section_num = clean_text(num_elem.get_text()) if num_elem else ""
            if not section_num:
                section_num = extract_section_number(heading) or ""

            # Clauses inside a schedule restart at 1, so qualify them with the
            # schedule's own label to keep them distinct from sections.
            schedule_elem = section.find_parent('div', class_='schedule')
            schedule_label = ""
            if schedule_elem:
                label_elem = schedule_elem.find('span', class_='label')
                schedule_label = clean_text(label_elem.get_text()) if label_elem else "Schedule"
                if section_num:
                    section_num = f"{schedule_label} cl {section_num}"

            # Get the body text
            body_elem = section.find(class_=re.compile(r'prov-body|section-body'))
            if body_elem:
                body_text = clean_text(body_elem.get_text())
            else:
                # Get all text minus the heading
                body_text = clean_text(section.get_text())
                if heading:
                    body_text = body_text.replace(heading, '', 1).strip()
            
            if not body_text and not heading:
                continue
            
            # Determine level
            level = "section"
            if re.match(r'^Part\s+\d+', heading, re.IGNORECASE):
                level = "part"
                current_part = heading
            elif re.match(r'^Subpart\s+', heading, re.IGNORECASE):
                level = "subpart"
                current_subpart = heading
            elif schedule_label or re.match(r'^Schedule', heading, re.IGNORECASE):
                level = "schedule"

            # Build section URL
            section_url = metadata.get("url", "")
            if section_id and section_url:
                # Anchor on the whole-Act page; ".../latest/<id>" is a 404.
                section_url = f"{section_url}#{section_id}"

            output["sections"].append({
                "section_number": section_num,
                "heading": heading,
                "level": level,
                "part": current_part,
                "subpart": current_subpart,
                "text": body_text,  # Full text: the chunker splits long sections
                "url": section_url,
                "act_title": metadata.get("title", ""),
                "act_short_name": metadata.get("short_name", "")
            })
            
        except Exception as e:
            print(f"    Warning: Error parsing section: {e}")
            continue
    
    # The preamble sits outside any div.prov. Settlement Acts carry their
    # historical account and acknowledgements there.
    preamble = soup.find('div', class_='preamble')
    preamble_text = clean_text(preamble.get_text()) if preamble else ""
    if preamble_text and output["sections"]:
        output["sections"].insert(0, {
            "section_number": "Preamble",
            "heading": "Preamble",
            "level": "preamble",
            "part": "",
            "subpart": "",
            "text": preamble_text,
            "url": metadata.get("url", ""),
            "act_title": metadata.get("title", ""),
            "act_short_name": metadata.get("short_name", "")
        })

    # If no sections found with prov class, try a simpler approach
    if not output["sections"]:
        print(f"    Using fallback text extraction...")
        output["sections"] = extract_by_text_patterns(soup, metadata)
    
    print(f"    Extracted {len(output['sections'])} sections")
    
    return output


def extract_by_text_patterns(soup: BeautifulSoup, metadata: Dict) -> List[Dict]:
    """Fallback: Extract sections by looking for numbered headings in text."""
    sections = []
    
    # Get the main content
    body = soup.find('body')
    if not body:
        return sections
    
    # Find all heading-like elements
    headings = body.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    for heading in headings:
        heading_text = clean_text(heading.get_text())
        
        # Check if this looks like a section heading
        if re.match(r'^\d+[A-Z]?\s+\w', heading_text):
            section_num = extract_section_number(heading_text) or ""
            
            # Get the next sibling content
            content_parts = []
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                content_parts.append(clean_text(sibling.get_text()))
                sibling = sibling.find_next_sibling()
            
            body_text = ' '.join(content_parts)[:5000]
            
            if body_text:
                sections.append({
                    "section_number": section_num,
                    "heading": heading_text,
                    "level": "section",
                    "part": "",
                    "subpart": "",
                    "text": body_text,
                    "url": metadata.get("url", ""),
                    "act_title": metadata.get("title", ""),
                    "act_short_name": metadata.get("short_name", "")
                })
    
    return sections


def main():
    """Main entry point."""
    print("=" * 60)
    print("NZ Legislation Parser")
    print("=" * 60)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Find HTML files
    html_files = list(RAW_HTML_DIR.glob("*.html"))
    
    if not html_files:
        print(f"\nNo HTML files found in {RAW_HTML_DIR.absolute()}")
        print("Please download the legislation HTML files first.")
        return
    
    print(f"\nFound {len(html_files)} HTML files to process:\n")
    
    all_acts = []
    total_sections = 0
    
    for html_path in sorted(html_files):
        # Get metadata for this file
        metadata = ACT_METADATA.get(html_path.name, {
            "title": html_path.stem.replace("-", " ").title(),
            "year": 0,
            "number": 0,
            "url": "",
            "short_name": html_path.stem[:3].upper(),
            "topics": []
        })
        
        # Parse the HTML
        try:
            result = parse_legislation_html(html_path, metadata)
        except ValueError as e:
            print(f"    [skip] {e}")
            continue
        all_acts.append(result)
        total_sections += len(result["sections"])
        
        # Save individual JSON file
        output_path = OUTPUT_DIR / f"{html_path.stem}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    # Save combined index
    index_path = OUTPUT_DIR / "acts_index.json"
    index_data = {
        "generated_at": datetime.now().isoformat(),
        "total_acts": len(all_acts),
        "total_sections": total_sections,
        "acts": [
            {
                "title": act["metadata"]["title"],
                "short_name": act["metadata"].get("short_name", ""),
                "year": act["metadata"].get("year", 0),
                "sections_count": len(act["sections"]),
                "file": f"{Path(act['metadata']['source_file']).stem}.json"
            }
            for act in all_acts
        ]
    }
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("PARSING COMPLETE!")
    print("=" * 60)
    print(f"Acts processed: {len(all_acts)}")
    print(f"Total sections: {total_sections}")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"\nFiles created:")
    for act in all_acts:
        stem = Path(act['metadata']['source_file']).stem
        print(f"  - {stem}.json ({len(act['sections'])} sections)")
    print(f"  - acts_index.json")


if __name__ == "__main__":
    main()