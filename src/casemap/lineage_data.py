from __future__ import annotations

CURATED_LINEAGES = [
    {
        "id": "interpretation_context_text",
        "title": 'Contractual Interpretation: "Context vs. Text"',
        "topic_hints": ["interpretation", "express terms", "parol evidence"],
        "cases": [
            {
                "label": "Investors Compensation Scheme Ltd v West Bromwich Building Society",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Originating UK authority for Lord Hoffmann's contextual principles.",
            },
            {
                "label": "Sinoearn International Ltd v Hyundai-CCECC Joint Venture",
                "treatment": "adopted",
                "code": "FLLW",
                "note": "Hong Kong CFA endorsement of the contextual approach.",
            },
            {
                "label": "Rainy Sky SA v Kookmin Bank",
                "treatment": "relevant authority",
                "code": "APPD",
                "note": 'Commercial common-sense peak in the UK line.',
            },
            {
                "label": "Fully Profit (Asia) Ltd v Secretary for Justice",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong treatment following Rainy Sky.",
            },
            {
                "label": "Arnold v Britton",
                "treatment": "qualified",
                "code": "DIST",
                "note": "Textualist correction emphasizing contractual language.",
            },
            {
                "label": "Sany Heavy Industry (HK) Ltd v Sany-Kenton (HK) Ltd",
                "treatment": "applied",
                "code": "APPD",
                "note": "Recent Hong Kong application of the textualist correction.",
            },
            {
                "label": "Wood v Capita",
                "treatment": "qualified",
                "code": "APPD",
                "note": "Modern unitary synthesis balancing text and context.",
            },
        ],
        "edges": [
            {
                "from": "Investors Compensation Scheme Ltd v West Bromwich Building Society",
                "to": "Sinoearn International Ltd v Hyundai-CCECC Joint Venture",
                "code": "FLLW",
                "label": "HK adoption",
            },
            {
                "from": "Rainy Sky SA v Kookmin Bank",
                "to": "Fully Profit (Asia) Ltd v Secretary for Justice",
                "code": "FLLW",
                "label": "followed in HK",
            },
            {
                "from": "Arnold v Britton",
                "to": "Sany Heavy Industry (HK) Ltd v Sany-Kenton (HK) Ltd",
                "code": "APPD",
                "label": "recent HK application",
            },
            {
                "from": "Sinoearn International Ltd v Hyundai-CCECC Joint Venture",
                "to": "Wood v Capita",
                "code": "APPD",
                "label": "modern synthesis",
            },
        ],
    },
    {
        "id": "consideration_practical_benefit",
        "title": 'Consideration and Variations: "Practical Benefit"',
        "topic_hints": ["consideration", "variations"],
        "cases": [
            {
                "label": "Stilk v Myrick",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Traditional existing-duty rule.",
            },
            {
                "label": "Williams v Roffey Bros & Nicholls",
                "treatment": "qualified",
                "code": "APPD",
                "note": 'UK practical-benefit exception to the traditional rule.',
            },
            {
                "label": "UBC (Construction) Ltd v Sung Foo Kee Ltd",
                "treatment": "adopted",
                "code": "FLLW",
                "note": "Hong Kong adoption of Williams v Roffey.",
            },
            {
                "label": "Re Selectmove",
                "treatment": "qualified",
                "code": "DIST",
                "note": "Refused to extend practical benefit to part-payment of debt.",
            },
            {
                "label": "Chong Cheng Lin Courtney v Cathay Pacific Airways Ltd",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong follow-on treatment of the Selectmove limitation.",
            },
            {
                "label": "MWB Business Exchange Centres Ltd v Rock Advertising Ltd",
                "treatment": "relevant authority",
                "code": "DIST",
                "note": "Illustrates continuing caution in this area.",
            },
        ],
        "edges": [
            {"from": "Stilk v Myrick", "to": "Williams v Roffey Bros & Nicholls", "code": "DIST", "label": "modern exception"},
            {"from": "Williams v Roffey Bros & Nicholls", "to": "UBC (Construction) Ltd v Sung Foo Kee Ltd", "code": "FLLW", "label": "HK adoption"},
            {"from": "Re Selectmove", "to": "Chong Cheng Lin Courtney v Cathay Pacific Airways Ltd", "code": "FLLW", "label": "HK limitation followed"},
            {"from": "Re Selectmove", "to": "MWB Business Exchange Centres Ltd v Rock Advertising Ltd", "code": "DIST", "label": "continuing conflict"},
        ],
    },
    {
        "id": "penalty_clauses_modern_test",
        "title": 'Penalty Clauses: "Modern Test"',
        "topic_hints": ["penalt", "liquidated damages"],
        "cases": [
            {
                "label": "Dunlop Pneumatic Tyre Co Ltd v New Garage & Motor Co Ltd",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Classic genuine pre-estimate versus deterrent framing.",
            },
            {
                "label": "Cavendish Square Holding BV v El Makdessi",
                "treatment": "qualified",
                "code": "APPD",
                "note": "Modern legitimate-interest and proportionality test.",
            },
            {
                "label": "Law Ting Pong Secondary School v Chen Wai-mick",
                "treatment": "adopted",
                "code": "FLLW",
                "note": "Hong Kong adoption of the Makdessi test.",
            },
            {
                "label": "China Great Wall AMC (International) Holdings Co Ltd v Royal-Investment Group Corp",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong application refining the Law Ting Pong line.",
            },
        ],
        "edges": [
            {"from": "Dunlop Pneumatic Tyre Co Ltd v New Garage & Motor Co Ltd", "to": "Cavendish Square Holding BV v El Makdessi", "code": "DIST", "label": "modernized test"},
            {"from": "Cavendish Square Holding BV v El Makdessi", "to": "Law Ting Pong Secondary School v Chen Wai-mick", "code": "FLLW", "label": "HK adoption"},
            {"from": "Law Ting Pong Secondary School v Chen Wai-mick", "to": "China Great Wall AMC (International) Holdings Co Ltd v Royal-Investment Group Corp", "code": "APPD", "label": "further application"},
        ],
    },
    {
        "id": "undue_influence_etridge",
        "title": 'Undue Influence: "Etridge"',
        "topic_hints": ["undue influence"],
        "cases": [
            {
                "label": "Royal Bank of Scotland v Etridge (No 2)",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Set the modern bank-procedure approach to constructive notice.",
            },
            {
                "label": "Li Sau Keung v Bank of China (Hong Kong) Ltd",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong follow-on application.",
            },
        ],
        "edges": [
            {"from": "Royal Bank of Scotland v Etridge (No 2)", "to": "Li Sau Keung v Bank of China (Hong Kong) Ltd", "code": "FLLW", "label": "followed in HK"},
        ],
    },
    {
        "id": "unconscionability_statutory",
        "title": 'Unconscionability: "Statutory"',
        "topic_hints": ["unconscionab"],
        "cases": [
            {
                "label": "Unconscionable Contracts Ordinance (Cap. 458)",
                "treatment": "codified",
                "code": "CODI",
                "note": "Statutory foundation of the Hong Kong doctrine.",
            },
            {
                "label": "Shum Kong v Chan Man-fai",
                "treatment": "applied",
                "code": "APPD",
                "note": "Seminal Hong Kong interpretation of the Ordinance.",
            },
        ],
        "edges": [
            {"from": "Unconscionable Contracts Ordinance (Cap. 458)", "to": "Shum Kong v Chan Man-fai", "code": "APPD", "label": "leading HK interpretation"},
        ],
    },
    {
        "id": "intermediate_terms_hongkong_fir",
        "title": 'Breach and Termination: "Intermediate Terms"',
        "topic_hints": ["innominate", "intermediate terms", "breach"],
        "cases": [
            {
                "label": "Hongkong Fir Shipping Co Ltd v Kawasaki Kisen Kaisha Ltd",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Foundational innominate-term authority with Hong Kong facts.",
            },
            {
                "label": "Billion Star Development Ltd v Wong Tak-fai",
                "treatment": "applied",
                "code": "APPD",
                "note": "Modern Hong Kong application on termination rights.",
            },
        ],
        "edges": [
            {"from": "Hongkong Fir Shipping Co Ltd v Kawasaki Kisen Kaisha Ltd", "to": "Billion Star Development Ltd v Wong Tak-fai", "code": "APPD", "label": "modern HK application"},
        ],
    },

    # ── Criminal Law Lineages ──────────────────────────────────────────────────

    {
        "id": "joint_enterprise_liability",
        "title": "Joint Enterprise / Secondary Liability",
        "topic_hints": ["secondary liability", "joint enterprise", "common purpose", "parasitic accessory"],
        "cases": [
            {
                "label": "Chan Wing-siu v R",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Privy Council established parasitic accessory liability — foresight of possible harm sufficient for secondary liability in murder.",
            },
            {
                "label": "R v Powell and English",
                "treatment": "followed",
                "code": "FLLW",
                "note": "House of Lords confirmed Chan Wing-siu — foresight extends secondary murderer liability.",
            },
            {
                "label": "HKSAR v Chan Kam-shing",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong Court of Appeal applied Chan Wing-siu joint enterprise doctrine.",
            },
            {
                "label": "R v Jogee",
                "treatment": "departed",
                "code": "DPRT",
                "note": "UK Supreme Court repudiated Chan Wing-siu — mere foresight is evidence of intent, not a substitute. Requires intention to assist or encourage.",
            },
        ],
        "edges": [
            {"from": "Chan Wing-siu v R", "to": "R v Powell and English", "code": "FLLW", "label": "HL confirmation"},
            {"from": "R v Powell and English", "to": "HKSAR v Chan Kam-shing", "code": "APPD", "label": "HK application"},
            {"from": "Chan Wing-siu v R", "to": "R v Jogee", "code": "DPRT", "label": "UKSC departure — corrected error"},
        ],
    },
    {
        "id": "confession_voluntariness",
        "title": "Confessions and Voluntariness",
        "topic_hints": ["confessions", "voluntariness", "voir dire", "oppression", "inducement"],
        "cases": [
            {
                "label": "Ibrahim v R",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Privy Council — confession must be free and voluntary; inadmissible if obtained by fear of prejudice or hope of advantage.",
            },
            {
                "label": "R v Wong Kam-ming",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong Privy Council applied Ibrahim voluntariness rule; voir dire procedure confirmed.",
            },
            {
                "label": "HKSAR v Lam Tat-ming",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal reaffirmed Hong Kong approach to oppression and inducement.",
            },
            {
                "label": "HKSAR v Cheung Tze-keung",
                "treatment": "applied",
                "code": "APPD",
                "note": "Application of voluntariness standard in complex conspiracy trial; judge's directions on voir dire.",
            },
        ],
        "edges": [
            {"from": "Ibrahim v R", "to": "R v Wong Kam-ming", "code": "FLLW", "label": "HK Privy Council application"},
            {"from": "R v Wong Kam-ming", "to": "HKSAR v Lam Tat-ming", "code": "APPD", "label": "post-handover continuity"},
            {"from": "HKSAR v Lam Tat-ming", "to": "HKSAR v Cheung Tze-keung", "code": "APPD", "label": "complex trial application"},
        ],
    },
    {
        "id": "provocation_reasonable_man",
        "title": "Provocation: The Reasonable Man Test",
        "topic_hints": ["provocation", "diminished responsibility", "loss of self-control", "reasonable man"],
        "cases": [
            {
                "label": "DPP v Camplin",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — reasonable man test personalised by age and sex of accused.",
            },
            {
                "label": "R v Smith (Morgan)",
                "treatment": "applied",
                "code": "APPD",
                "note": "Extended personalisation to include individual characteristics bearing on gravity of provocation.",
            },
            {
                "label": "Attorney General for Jersey v Holley",
                "treatment": "qualified",
                "code": "DIST",
                "note": "Privy Council nine-judge board — external standard restored; characteristics only relevant to gravity, not loss of control.",
            },
            {
                "label": "HKSAR v Liang Yaoqiang",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong Court of Final Appeal applied Holley standard to provocation defence.",
            },
        ],
        "edges": [
            {"from": "DPP v Camplin", "to": "R v Smith (Morgan)", "code": "APPD", "label": "personalisation extended"},
            {"from": "R v Smith (Morgan)", "to": "Attorney General for Jersey v Holley", "code": "DIST", "label": "objective standard restored"},
            {"from": "Attorney General for Jersey v Holley", "to": "HKSAR v Liang Yaoqiang", "code": "APPD", "label": "HK CFA adoption"},
        ],
    },
    {
        "id": "identification_turnbull",
        "title": "Identification Evidence: Turnbull Warnings",
        "topic_hints": ["identification evidence", "Turnbull", "eyewitness", "recognition"],
        "cases": [
            {
                "label": "R v Turnbull",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Court of Appeal — mandatory judicial warning on dangers of mistaken identity evidence; ADVOKATE factors.",
            },
            {
                "label": "HKSAR v Shing Siu-ming",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong adopted Turnbull guidelines; warning required where conviction rests substantially on identification.",
            },
            {
                "label": "HKSAR v Wong Sau-ming",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal considered quality of identification and adequacy of Turnbull direction.",
            },
            {
                "label": "HKSAR v So Wai-lun",
                "treatment": "applied",
                "code": "APPD",
                "note": "Modern Hong Kong application extending Turnbull to CCTV and dock identification scenarios.",
            },
        ],
        "edges": [
            {"from": "R v Turnbull", "to": "HKSAR v Shing Siu-ming", "code": "FLLW", "label": "HK adoption"},
            {"from": "HKSAR v Shing Siu-ming", "to": "HKSAR v Wong Sau-ming", "code": "APPD", "label": "quality of ID assessment"},
            {"from": "HKSAR v Wong Sau-ming", "to": "HKSAR v So Wai-lun", "code": "APPD", "label": "CCTV/dock ID extension"},
        ],
    },
    {
        "id": "mens_rea_intention",
        "title": "Mens Rea: Intention and Foresight",
        "topic_hints": ["intention", "mens rea", "foresight", "murder", "virtual certainty"],
        "cases": [
            {
                "label": "DPP v Smith",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — objective foresight of natural consequences as test for intention in murder.",
            },
            {
                "label": "R v Moloney",
                "treatment": "qualified",
                "code": "DIST",
                "note": "Corrected DPP v Smith — intention not the same as foresight of consequences; purpose or aim test.",
            },
            {
                "label": "R v Woollin",
                "treatment": "applied",
                "code": "APPD",
                "note": "House of Lords — virtual certainty test: jury may find intention where result is virtually certain and accused foresaw it as such.",
            },
            {
                "label": "HKSAR v Kissel",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong Court of Final Appeal adopted Woollin virtual certainty approach for murder intention.",
            },
            {
                "label": "Sin Kam-wah v HKSAR",
                "treatment": "applied",
                "code": "APPD",
                "note": "Further Hong Kong refinement on directions to jury on intent and foresight.",
            },
        ],
        "edges": [
            {"from": "DPP v Smith", "to": "R v Moloney", "code": "DIST", "label": "objective excess corrected"},
            {"from": "R v Moloney", "to": "R v Woollin", "code": "APPD", "label": "virtual certainty formulation"},
            {"from": "R v Woollin", "to": "HKSAR v Kissel", "code": "FLLW", "label": "HK CFA adoption"},
            {"from": "HKSAR v Kissel", "to": "Sin Kam-wah v HKSAR", "code": "APPD", "label": "jury direction refinement"},
        ],
    },
    {
        "id": "sentencing_tariff_principles",
        "title": "Sentencing: Tariff and Deterrence Principles",
        "topic_hints": ["sentencing", "tariff", "deterrence", "starting point", "totality"],
        "cases": [
            {
                "label": "R v Lau Tak-ming",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Hong Kong Court of Appeal — established sentencing tariff framework for drug trafficking offences.",
            },
            {
                "label": "Secretary for Justice v Cheng Chun-pong",
                "treatment": "applied",
                "code": "APPD",
                "note": "Review of sentencing principles; prosecution appeal jurisdiction and appellate intervention threshold.",
            },
            {
                "label": "HKSAR v Ngo Van Nam",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal issued tariff guidelines for drug trafficking — quantity-based starting points.",
            },
            {
                "label": "HKSAR v Lo Hau-wai",
                "treatment": "applied",
                "code": "APPD",
                "note": "Application of totality principle and enhancement for organiser/leadership role.",
            },
        ],
        "edges": [
            {"from": "R v Lau Tak-ming", "to": "Secretary for Justice v Cheng Chun-pong", "code": "APPD", "label": "review jurisdiction clarified"},
            {"from": "Secretary for Justice v Cheng Chun-pong", "to": "HKSAR v Ngo Van Nam", "code": "APPD", "label": "drug tariff guidelines"},
            {"from": "HKSAR v Ngo Van Nam", "to": "HKSAR v Lo Hau-wai", "code": "APPD", "label": "totality and role enhancement"},
        ],
    },
    {
        "id": "drug_knowledge_possession",
        "title": "Drug Trafficking: Knowledge and Possession",
        "topic_hints": ["drug trafficking", "possession", "knowledge", "container", "presumption"],
        "cases": [
            {
                "label": "R v Warner",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — possession requires knowledge that one has something; but not necessarily knowledge of its precise nature.",
            },
            {
                "label": "R v McNamara",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal applied Warner — knowledge of substance in container sufficient for possession.",
            },
            {
                "label": "HKSAR v Abdallah",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong Court of Final Appeal — container doctrine; accused unaware of drugs in concealed compartment; knowledge presumption rebuttable.",
            },
            {
                "label": "HKSAR v Ching Kwong-yuen",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Followed Abdallah container doctrine; prosecution must establish knowledge or wilful blindness.",
            },
        ],
        "edges": [
            {"from": "R v Warner", "to": "R v McNamara", "code": "APPD", "label": "container knowledge"},
            {"from": "R v McNamara", "to": "HKSAR v Abdallah", "code": "APPD", "label": "HK CFA container doctrine"},
            {"from": "HKSAR v Abdallah", "to": "HKSAR v Ching Kwong-yuen", "code": "FLLW", "label": "wilful blindness clarified"},
        ],
    },
    {
        "id": "self_defence_proportionality",
        "title": "Self-Defence and Reasonable Force",
        "topic_hints": ["self defence", "reasonable force", "proportionality", "householder"],
        "cases": [
            {
                "label": "Palmer v R",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Privy Council — no duty to retreat; force used must be reasonable in the circumstances as genuinely believed.",
            },
            {
                "label": "R v Clegg",
                "treatment": "applied",
                "code": "APPD",
                "note": "House of Lords — excessive force negates self-defence but does not reduce murder to manslaughter.",
            },
            {
                "label": "HKSAR v Chan Wai-man",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong adopted Palmer — jury must consider what accused genuinely believed and whether force was reasonable.",
            },
            {
                "label": "HKSAR v Yip Kwong-lam",
                "treatment": "applied",
                "code": "APPD",
                "note": "Modern Hong Kong application; directions on instinctive reaction and proportionality.",
            },
        ],
        "edges": [
            {"from": "Palmer v R", "to": "R v Clegg", "code": "APPD", "label": "excessive force — no reduction"},
            {"from": "Palmer v R", "to": "HKSAR v Chan Wai-man", "code": "FLLW", "label": "HK adoption"},
            {"from": "HKSAR v Chan Wai-man", "to": "HKSAR v Yip Kwong-lam", "code": "APPD", "label": "proportionality directions"},
        ],
    },
    {
        "id": "hearsay_res_gestae",
        "title": "Hearsay: Res Gestae and Modern Exceptions",
        "topic_hints": ["hearsay", "res gestae", "spontaneous declaration", "evidence ordinance"],
        "cases": [
            {
                "label": "R v Andrews",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — res gestae exception: statement admissible if made when declarant's mind dominated by event, leaving no room for concoction.",
            },
            {
                "label": "HKSAR v To Kun-sun",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong applied Andrews res gestae test; court cautioned against expansive use.",
            },
            {
                "label": "HKSAR v Tsang Wai-hung",
                "treatment": "applied",
                "code": "APPD",
                "note": "Application of res gestae in domestic violence context; contemporaneity requirement assessed.",
            },
        ],
        "edges": [
            {"from": "R v Andrews", "to": "HKSAR v To Kun-sun", "code": "FLLW", "label": "HK adoption"},
            {"from": "HKSAR v To Kun-sun", "to": "HKSAR v Tsang Wai-hung", "code": "APPD", "label": "domestic violence application"},
        ],
    },
    {
        "id": "money_laundering_knowledge",
        "title": "Money Laundering: Knowledge and Reasonable Grounds",
        "topic_hints": ["money laundering", "proceeds of crime", "reasonable grounds", "OSCO"],
        "cases": [
            {
                "label": "HKSAR v Pang Hung-fai",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Hong Kong Court of Final Appeal — mens rea under OSCO s.25(1): knowledge or belief, or having reasonable grounds to believe, that property represents proceeds of crime.",
            },
            {
                "label": "HKSAR v Yeung Ka-sing Carson",
                "treatment": "applied",
                "code": "APPD",
                "note": "Applied Pang Hung-fai — subjective awareness and objective reasonable grounds test; no need to know exact predicate offence.",
            },
            {
                "label": "HKSAR v Doraiswamy Sinnasamy",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal extended analysis to wilful blindness as equivalent to knowledge under OSCO.",
            },
        ],
        "edges": [
            {"from": "HKSAR v Pang Hung-fai", "to": "HKSAR v Yeung Ka-sing Carson", "code": "APPD", "label": "knowledge/reasonable grounds"},
            {"from": "HKSAR v Yeung Ka-sing Carson", "to": "HKSAR v Doraiswamy Sinnasamy", "code": "APPD", "label": "wilful blindness extension"},
        ],
    },
    {
        "id": "dishonesty_ghosh_ivey",
        "title": "Dishonesty: From Ghosh to Ivey",
        "topic_hints": ["dishonesty", "theft", "fraud", "Ghosh test", "Ivey"],
        "cases": [
            {
                "label": "R v Ghosh",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Court of Appeal — two-stage test: (1) objectively dishonest by standards of reasonable and honest people; (2) accused knew it was dishonest.",
            },
            {
                "label": "HKSAR v Wai Yu-tsang",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Privy Council applied Ghosh dishonesty test in Hong Kong fraud conspiracy context.",
            },
            {
                "label": "Ivey v Genting Casinos (UK) Ltd",
                "treatment": "departed",
                "code": "DPRT",
                "note": "UK Supreme Court — Ghosh second limb abolished; single objective test: what was accused's state of knowledge, then ask if that conduct was dishonest by ordinary standards.",
            },
            {
                "label": "HKSAR v Chan Chi-wai",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong courts post-Ivey; moved towards objective standard while acknowledging Ghosh remains technically binding in HK.",
            },
        ],
        "edges": [
            {"from": "R v Ghosh", "to": "HKSAR v Wai Yu-tsang", "code": "FLLW", "label": "HK Privy Council"},
            {"from": "R v Ghosh", "to": "Ivey v Genting Casinos (UK) Ltd", "code": "DPRT", "label": "UKSC — objective standard"},
            {"from": "Ivey v Genting Casinos (UK) Ltd", "to": "HKSAR v Chan Chi-wai", "code": "APPD", "label": "HK post-Ivey treatment"},
        ],
    },
    {
        "id": "bail_risk_principles",
        "title": "Bail: Risk Assessment and Grounds for Refusal",
        "topic_hints": ["bail", "remand", "flight risk", "interference", "national security"],
        "cases": [
            {
                "label": "R v Vernege",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Established common law grounds for refusing bail — flight risk, interference with witnesses, commission of further offences.",
            },
            {
                "label": "Re Kwan Kong",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong application of bail grounds; court balances liberty with risks.",
            },
            {
                "label": "HKSAR v Lai Chee-ying",
                "treatment": "applied",
                "code": "APPD",
                "note": "NSL bail restrictions under Art.42(2) — presumption against bail for national security offences; higher threshold.",
            },
        ],
        "edges": [
            {"from": "R v Vernege", "to": "Re Kwan Kong", "code": "APPD", "label": "HK common law bail"},
            {"from": "Re Kwan Kong", "to": "HKSAR v Lai Chee-ying", "code": "APPD", "label": "NSL higher threshold"},
        ],
    },

    # ── Civil Law Lineages ─────────────────────────────────────────────────────

    {
        "id": "estoppel_promissory_proprietary",
        "title": "Estoppel: From Promissory to Proprietary",
        "topic_hints": ["estoppel", "promissory estoppel", "proprietary estoppel", "High Trees", "reliance"],
        "cases": [
            {
                "label": "Central London Property Trust Ltd v High Trees House Ltd",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Denning J — promissory estoppel: promisor who clearly indicates that strict rights will not be enforced cannot insist on those rights while promise operative.",
            },
            {
                "label": "Combe v Combe",
                "treatment": "qualified",
                "code": "DIST",
                "note": "Court of Appeal — promissory estoppel is a shield not a sword; cannot found a cause of action without consideration.",
            },
            {
                "label": "Crabb v Arun District Council",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal — proprietary estoppel: equity arises where landowner encouraged belief in right over land and claimant detrimentally relied.",
            },
            {
                "label": "Luo Xing Juan v Estate of Hui Shui See",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong Court of Final Appeal — proprietary estoppel requires representation, reliance, and detriment; equity satisfied by appropriate remedy.",
            },
            {
                "label": "Kim Eng Securities (Hong Kong) Ltd v Tang Kin Kwok",
                "treatment": "applied",
                "code": "APPD",
                "note": "Modern Hong Kong application of promissory estoppel in commercial context; requirements of clear and unequivocal promise.",
            },
        ],
        "edges": [
            {"from": "Central London Property Trust Ltd v High Trees House Ltd", "to": "Combe v Combe", "code": "DIST", "label": "shield not sword"},
            {"from": "Central London Property Trust Ltd v High Trees House Ltd", "to": "Crabb v Arun District Council", "code": "APPD", "label": "proprietary extension"},
            {"from": "Crabb v Arun District Council", "to": "Luo Xing Juan v Estate of Hui Shui See", "code": "FLLW", "label": "HK CFA adoption"},
            {"from": "Luo Xing Juan v Estate of Hui Shui See", "to": "Kim Eng Securities (Hong Kong) Ltd v Tang Kin Kwok", "code": "APPD", "label": "commercial HK application"},
        ],
    },
    {
        "id": "negligence_duty_of_care",
        "title": "Negligence: Duty of Care",
        "topic_hints": ["duty of care", "negligence", "proximity", "Caparo", "Donoghue"],
        "cases": [
            {
                "label": "Donoghue v Stevenson",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — neighbour principle; duty of care owed to those who ought reasonably to be in contemplation as affected by acts or omissions.",
            },
            {
                "label": "Anns v Merton London Borough Council",
                "treatment": "applied",
                "code": "APPD",
                "note": "Two-stage test: sufficient proximity? Any policy reasons to limit duty? Enabled significant expansion of duty.",
            },
            {
                "label": "Caparo Industries plc v Dickman",
                "treatment": "qualified",
                "code": "DIST",
                "note": "House of Lords — three-stage test: (1) foreseeable harm, (2) proximity, (3) fair just and reasonable. Replaced Anns incrementalism.",
            },
            {
                "label": "Luen Hing Fat Cooked Food Stall v Yau Tsim Mong District Board",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong Court of Final Appeal applied Caparo three-stage test as the applicable framework.",
            },
        ],
        "edges": [
            {"from": "Donoghue v Stevenson", "to": "Anns v Merton London Borough Council", "code": "APPD", "label": "two-stage expansion"},
            {"from": "Anns v Merton London Borough Council", "to": "Caparo Industries plc v Dickman", "code": "DIST", "label": "Anns limited/corrected"},
            {"from": "Caparo Industries plc v Dickman", "to": "Luen Hing Fat Cooked Food Stall v Yau Tsim Mong District Board", "code": "APPD", "label": "HK CFA adoption"},
        ],
    },
    {
        "id": "judicial_review_wednesbury_proportionality",
        "title": "Judicial Review: From Wednesbury to Proportionality",
        "topic_hints": ["judicial review", "Wednesbury", "proportionality", "irrationality", "Basic Law"],
        "cases": [
            {
                "label": "Associated Provincial Picture Houses Ltd v Wednesbury Corporation",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Court of Appeal — unreasonableness: decision so unreasonable that no reasonable authority could ever have come to it.",
            },
            {
                "label": "Council of Civil Service Unions v Minister for Civil Service",
                "treatment": "applied",
                "code": "APPD",
                "note": "House of Lords — three grounds of review: illegality, irrationality, procedural impropriety.",
            },
            {
                "label": "Hysan Development Co Ltd v Town Planning Board",
                "treatment": "qualified",
                "code": "DIST",
                "note": "Hong Kong Court of Final Appeal — proportionality test applies for BOR/Basic Law rights; Wednesbury applies for non-rights matters.",
            },
            {
                "label": "Leung Kwok Hung v HKSAR",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Final Appeal applied proportionality to freedom of assembly restrictions under Basic Law.",
            },
        ],
        "edges": [
            {"from": "Associated Provincial Picture Houses Ltd v Wednesbury Corporation", "to": "Council of Civil Service Unions v Minister for Civil Service", "code": "APPD", "label": "three grounds systematised"},
            {"from": "Council of Civil Service Unions v Minister for Civil Service", "to": "Hysan Development Co Ltd v Town Planning Board", "code": "DIST", "label": "HK bifurcated standard"},
            {"from": "Hysan Development Co Ltd v Town Planning Board", "to": "Leung Kwok Hung v HKSAR", "code": "APPD", "label": "assembly rights proportionality"},
        ],
    },
    {
        "id": "unfair_prejudice_minority_shareholders",
        "title": "Unfair Prejudice and Minority Shareholder Protection",
        "topic_hints": ["unfair prejudice", "minority shareholders", "directors duties", "winding up", "just and equitable"],
        "cases": [
            {
                "label": "O'Neill v Phillips",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — unfair prejudice requires conduct unfair in a commercial sense; legitimate expectations from informal understanding enforceable.",
            },
            {
                "label": "Re Kong Thai Sawmill (Miri) Sdn Bhd",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong Privy Council — just and equitable winding up; loss of mutual confidence in small quasi-partnership company.",
            },
            {
                "label": "Re Kam Kwan Lai",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong Court of First Instance — applied Companies Ordinance s.724 unfair prejudice; buyout remedy ordered.",
            },
            {
                "label": "Re Chime Communications Ltd",
                "treatment": "applied",
                "code": "APPD",
                "note": "Court of Appeal — scope of unfair prejudice petition under Cap.622; management exclusion and valuation principles.",
            },
        ],
        "edges": [
            {"from": "O'Neill v Phillips", "to": "Re Kong Thai Sawmill (Miri) Sdn Bhd", "code": "APPD", "label": "quasi-partnership winding up"},
            {"from": "O'Neill v Phillips", "to": "Re Kam Kwan Lai", "code": "FLLW", "label": "HK Cap.622 s.724 application"},
            {"from": "Re Kam Kwan Lai", "to": "Re Chime Communications Ltd", "code": "APPD", "label": "management exclusion/valuation"},
        ],
    },
    {
        "id": "mareva_freezing_orders",
        "title": "Mareva Injunctions and Freezing Orders",
        "topic_hints": ["Mareva", "freezing order", "interlocutory injunction", "asset dissipation", "worldwide"],
        "cases": [
            {
                "label": "Mareva Compania Naviera SA v International Bulkcarriers SA",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "Court of Appeal — Mareva injunction: equity jurisdiction to freeze defendant assets to prevent frustration of judgment.",
            },
            {
                "label": "Derby and Co Ltd v Weldon (No 1)",
                "treatment": "applied",
                "code": "APPD",
                "note": "Worldwide Mareva extended to assets outside jurisdiction where domestic assets insufficient.",
            },
            {
                "label": "Zi Hua Inc v Standard Chartered Bank",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong Court adopted Mareva jurisdiction; conditions — good arguable case, real risk of dissipation, balance of convenience.",
            },
            {
                "label": "CITIC Pacific Ltd v Secretary for Justice",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong CFA — freezing order principles in investigation context; privilege and disclosure obligations.",
            },
        ],
        "edges": [
            {"from": "Mareva Compania Naviera SA v International Bulkcarriers SA", "to": "Derby and Co Ltd v Weldon (No 1)", "code": "APPD", "label": "worldwide extension"},
            {"from": "Mareva Compania Naviera SA v International Bulkcarriers SA", "to": "Zi Hua Inc v Standard Chartered Bank", "code": "FLLW", "label": "HK adoption"},
            {"from": "Zi Hua Inc v Standard Chartered Bank", "to": "CITIC Pacific Ltd v Secretary for Justice", "code": "APPD", "label": "investigation context"},
        ],
    },
    {
        "id": "ancillary_relief_equality",
        "title": "Ancillary Relief: From Discretion to Equality",
        "topic_hints": ["ancillary relief", "financial provision", "divorce", "equality", "sharing principle"],
        "cases": [
            {
                "label": "White v White",
                "treatment": "originating authority",
                "code": "ORIG",
                "note": "House of Lords — yardstick of equality as check on discretion; no bias against non-money earner; outcome should not discriminate.",
            },
            {
                "label": "Miller v Miller; McFarlane v McFarlane",
                "treatment": "applied",
                "code": "APPD",
                "note": "House of Lords — sharing principle, compensation principle, and needs; sharing based on equal partnership of marriage.",
            },
            {
                "label": "LKW v DD",
                "treatment": "followed",
                "code": "FLLW",
                "note": "Hong Kong Court of Final Appeal — adopted White/Miller framework; equal sharing as starting point; departure requires good reason.",
            },
            {
                "label": "SPH v SA",
                "treatment": "applied",
                "code": "APPD",
                "note": "Hong Kong Court of Appeal applied LKW v DD — factors justifying departure from equal sharing in long and short marriages.",
            },
        ],
        "edges": [
            {"from": "White v White", "to": "Miller v Miller; McFarlane v McFarlane", "code": "APPD", "label": "sharing/needs/compensation"},
            {"from": "Miller v Miller; McFarlane v McFarlane", "to": "LKW v DD", "code": "FLLW", "label": "HK CFA adoption"},
            {"from": "LKW v DD", "to": "SPH v SA", "code": "APPD", "label": "departure factors"},
        ],
    },
]
