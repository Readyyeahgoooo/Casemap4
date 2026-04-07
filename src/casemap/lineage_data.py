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
]
