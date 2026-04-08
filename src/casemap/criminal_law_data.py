from __future__ import annotations

CRIMINAL_AUTHORITY_TREE = [
    {
        "id": "general_principles",
        "label_en": "General Principles",
        "label_zh": "刑事責任總則",
        "summary_en": "Foundational criminal-law rules governing conduct, fault, causation, participation, and inchoate liability.",
        "summary_zh": "涵蓋行為、罪責、因果關係、共同參與及未完成罪行的基礎規則。",
        "subgrounds": [
            {
                "id": "actus_reus_causation",
                "label_en": "Actus Reus and Causation",
                "label_zh": "犯罪行為與因果關係",
                "summary_en": "The external elements of offences, omissions, and causal responsibility.",
                "summary_zh": "外部犯罪構成、作為與不作為，以及因果責任。",
                "topics": [
                    {
                        "id": "actus_reus",
                        "label_en": "Actus Reus",
                        "label_zh": "犯罪行為",
                        "search_queries": ["actus reus HKSAR criminal", "criminal omission HKSAR", "causation homicide HKSAR"],
                    },
                    {
                        "id": "causation",
                        "label_en": "Causation",
                        "label_zh": "因果關係",
                        "search_queries": ["causation murder HKSAR", "novus actus interveniens HKSAR criminal"],
                    },
                ],
                "children": [
                    {"en": "Positive acts and omissions", "zh": "作為與不作為"},
                    {"en": "Legal and factual causation", "zh": "法律及事實因果"},
                ],
            },
            {
                "id": "mens_rea_fault",
                "label_en": "Mens Rea and Fault",
                "label_zh": "主觀罪責",
                "summary_en": "Intent, knowledge, recklessness, dishonesty, and other mental elements.",
                "summary_zh": "故意、明知、魯莽、不誠實等主觀要素。",
                "topics": [
                    {
                        "id": "intention",
                        "label_en": "Intention and Knowledge",
                        "label_zh": "故意與明知",
                        "search_queries": ["intention murder HKSAR", "knowledge criminal liability HKSAR"],
                    },
                    {
                        "id": "recklessness_dishonesty",
                        "label_en": "Recklessness and Dishonesty",
                        "label_zh": "魯莽與不誠實",
                        "search_queries": ["recklessness HKSAR criminal", "dishonesty theft HKSAR", "Ghosh Ivey Hong Kong criminal"],
                    },
                ],
                "children": [
                    {"en": "Intent and foresight", "zh": "故意與預見"},
                    {"en": "Recklessness and dishonesty", "zh": "魯莽與不誠實"},
                ],
            },
            {
                "id": "participation_inchoate",
                "label_en": "Participation and Inchoate Liability",
                "label_zh": "共同參與與未完成罪行",
                "summary_en": "Secondary liability, conspiracy, attempts, and joint enterprise questions.",
                "summary_zh": "從犯責任、串謀、企圖及共同犯罪問題。",
                "topics": [
                    {
                        "id": "secondary_liability",
                        "label_en": "Secondary Liability",
                        "label_zh": "從犯責任",
                        "search_queries": ["secondary liability HKSAR criminal", "joint enterprise murder HKSAR", "aiding abetting HKSAR"],
                    },
                    {
                        "id": "conspiracy_attempt",
                        "label_en": "Conspiracy and Attempt",
                        "label_zh": "串謀與企圖",
                        "search_queries": ["criminal conspiracy HKSAR", "attempt offence HKSAR criminal"],
                    },
                ],
                "children": [
                    {"en": "Joint enterprise", "zh": "共同犯罪"},
                    {"en": "Conspiracy and attempt", "zh": "串謀與企圖"},
                ],
            },
        ],
    },
    {
        "id": "offences_against_person",
        "label_en": "Offences Against the Person",
        "label_zh": "侵害人身罪行",
        "summary_en": "Homicide, violence, and sexual offences.",
        "summary_zh": "包括殺人、暴力及性罪行。",
        "subgrounds": [
            {
                "id": "homicide",
                "label_en": "Homicide",
                "label_zh": "殺人罪",
                "summary_en": "Murder, manslaughter, and homicide-specific doctrines.",
                "summary_zh": "謀殺、誤殺及相關原則。",
                "topics": [
                    {
                        "id": "murder",
                        "label_en": "Murder",
                        "label_zh": "謀殺",
                        "search_queries": ["murder HKSAR appeal", "murder secondary liability HKSAR", "murder sentencing HKSAR"],
                    },
                    {
                        "id": "manslaughter",
                        "label_en": "Manslaughter",
                        "label_zh": "誤殺",
                        "search_queries": ["manslaughter HKSAR appeal", "gross negligence manslaughter HKSAR", "unlawful act manslaughter HKSAR"],
                    },
                ],
                "children": [
                    {"en": "Murder", "zh": "謀殺"},
                    {"en": "Manslaughter", "zh": "誤殺"},
                ],
            },
            {
                "id": "non_fatal_violence",
                "label_en": "Non-fatal Violence",
                "label_zh": "非致命暴力罪行",
                "summary_en": "Assault, wounding, grievous bodily harm, and related offences.",
                "summary_zh": "襲擊、傷人、嚴重身體傷害等。",
                "topics": [
                    {
                        "id": "assault_wounding",
                        "label_en": "Assault and Wounding",
                        "label_zh": "襲擊與傷人",
                        "search_queries": ["wounding HKSAR", "assault occasioning bodily harm HKSAR", "grievous bodily harm HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Assault and wounding", "zh": "襲擊與傷人"},
                ],
            },
            {
                "id": "kidnapping_false_imprisonment",
                "label_en": "Kidnapping and False Imprisonment",
                "label_zh": "綁架與非法禁錮",
                "summary_en": "Kidnapping, false imprisonment, and unlawful detention offences.",
                "summary_zh": "綁架、非法禁錮及非法拘禁罪行。",
                "topics": [
                    {
                        "id": "kidnapping",
                        "label_en": "Kidnapping and False Imprisonment",
                        "label_zh": "綁架與非法禁錮",
                        "search_queries": ["kidnapping HKSAR criminal appeal", "false imprisonment HKSAR", "unlawful detention HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Kidnapping and false imprisonment", "zh": "綁架與非法禁錮"},
                ],
            },
            {
                "id": "intimidation_threats",
                "label_en": "Intimidation and Criminal Threats",
                "label_zh": "恐嚇與刑事威脅",
                "summary_en": "Criminal intimidation, blackmail, and threatening behaviour.",
                "summary_zh": "刑事恐嚇、勒索及威脅行為。",
                "topics": [
                    {
                        "id": "criminal_intimidation",
                        "label_en": "Criminal Intimidation and Blackmail",
                        "label_zh": "刑事恐嚇與勒索",
                        "search_queries": ["criminal intimidation HKSAR", "blackmail HKSAR criminal appeal", "threats to kill HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Criminal intimidation and blackmail", "zh": "刑事恐嚇與勒索"},
                ],
            },
            {
                "id": "sexual_offences",
                "label_en": "Sexual Offences",
                "label_zh": "性罪行",
                "summary_en": "Consent, complainant evidence, and major sexual offences.",
                "summary_zh": "同意、證據評價及主要性罪行。",
                "topics": [
                    {
                        "id": "rape_consent",
                        "label_en": "Rape and Consent",
                        "label_zh": "強姦與同意",
                        "search_queries": ["rape consent HKSAR", "sexual offences HKSAR appeal", "indecent assault HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Consent and sexual offences", "zh": "同意與性罪行"},
                ],
            },
        ],
    },
    {
        "id": "property_dishonesty",
        "label_en": "Property and Dishonesty Offences",
        "label_zh": "財產與不誠實罪行",
        "summary_en": "Theft, robbery, burglary, fraud, deception, and criminal damage.",
        "summary_zh": "盜竊、搶劫、入屋犯法、詐騙、欺騙及刑事毀壞。",
        "subgrounds": [
            {
                "id": "theft_robbery",
                "label_en": "Theft and Robbery",
                "label_zh": "盜竊與搶劫",
                "summary_en": "Appropriation, dishonesty, force, and related property offences.",
                "summary_zh": "挪佔、不誠實、武力及相關財產罪行。",
                "topics": [
                    {
                        "id": "theft",
                        "label_en": "Theft",
                        "label_zh": "盜竊",
                        "search_queries": ["theft HKSAR appeal", "appropriation dishonesty HKSAR", "handling stolen goods HKSAR"],
                    },
                    {
                        "id": "robbery",
                        "label_en": "Robbery",
                        "label_zh": "搶劫",
                        "search_queries": ["robbery HKSAR appeal", "armed robbery HKSAR sentence"],
                    },
                ],
                "children": [
                    {"en": "Theft and handling stolen goods", "zh": "盜竊與處理贓物"},
                    {"en": "Robbery", "zh": "搶劫"},
                ],
            },
            {
                "id": "burglary_damage",
                "label_en": "Burglary and Criminal Damage",
                "label_zh": "爆竊與刑事毀壞",
                "summary_en": "Entry, trespass, intent, and property interference.",
                "summary_zh": "進入、侵入、意圖及財產侵害。",
                "topics": [
                    {
                        "id": "burglary",
                        "label_en": "Burglary",
                        "label_zh": "爆竊",
                        "search_queries": ["burglary HKSAR", "aggravated burglary HKSAR", "criminal damage HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Burglary and criminal damage", "zh": "爆竊與刑事毀壞"},
                ],
            },
            {
                "id": "fraud_deception",
                "label_en": "Fraud and Deception",
                "label_zh": "詐騙與欺騙",
                "summary_en": "Fraud schemes, false representations, and deception-based liability.",
                "summary_zh": "欺詐安排、虛假陳述及欺騙類罪責。",
                "topics": [
                    {
                        "id": "fraud",
                        "label_en": "Fraud and Deception",
                        "label_zh": "詐騙與欺騙",
                        "search_queries": ["fraud HKSAR appeal", "obtaining by deception HKSAR", "conspiracy to defraud HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Fraud and deception", "zh": "詐騙與欺騙"},
                ],
            },
            {
                "id": "forgery_counterfeiting",
                "label_en": "Forgery and Counterfeiting",
                "label_zh": "偽造與假冒",
                "summary_en": "Forgery of documents, counterfeiting, and related offences under Cap. 200.",
                "summary_zh": "偽造文件、假冒及第200章相關罪行。",
                "topics": [
                    {
                        "id": "forgery",
                        "label_en": "Forgery and Counterfeiting",
                        "label_zh": "偽造與假冒",
                        "search_queries": ["forgery HKSAR criminal appeal", "using false instrument HKSAR", "counterfeiting HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Forgery and counterfeiting", "zh": "偽造與假冒"},
                ],
            },
            {
                "id": "handling_stolen_goods",
                "label_en": "Handling Stolen Goods",
                "label_zh": "處理贓物",
                "summary_en": "Receiving and handling stolen property.",
                "summary_zh": "收受及處理被盜財物。",
                "topics": [
                    {
                        "id": "handling_stolen",
                        "label_en": "Handling Stolen Goods",
                        "label_zh": "處理贓物",
                        "search_queries": ["handling stolen goods HKSAR", "receiving stolen property HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Handling stolen goods", "zh": "處理贓物"},
                ],
            },
            {
                "id": "criminal_damage",
                "label_en": "Criminal Damage",
                "label_zh": "刑事毀壞",
                "summary_en": "Criminal damage, arson, and destruction of property under Cap. 60.",
                "summary_zh": "刑事毀壞、縱火及第60章相關罪行。",
                "topics": [
                    {
                        "id": "criminal_damage_arson",
                        "label_en": "Criminal Damage and Arson",
                        "label_zh": "刑事毀壞與縱火",
                        "search_queries": ["criminal damage HKSAR appeal", "arson HKSAR criminal", "crimes ordinance cap 60 HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Criminal damage and arson", "zh": "刑事毀壞與縱火"},
                ],
            },
        ],
    },
    {
        "id": "public_order_regulatory",
        "label_en": "Dangerous Drugs, Public Order, and Corruption",
        "label_zh": "危險藥物、公共秩序與廉政罪行",
        "summary_en": "Drug trafficking, weapons, public order, bribery, and misconduct cases.",
        "summary_zh": "危險藥物、武器、公共秩序、賄賂及公職失當案件。",
        "subgrounds": [
            {
                "id": "dangerous_drugs",
                "label_en": "Dangerous Drugs",
                "label_zh": "危險藥物",
                "summary_en": "Trafficking, possession, and sentencing in dangerous-drugs cases.",
                "summary_zh": "販毒、管有及相關量刑。",
                "topics": [
                    {
                        "id": "drug_trafficking",
                        "label_en": "Drug Trafficking",
                        "label_zh": "販運危險藥物",
                        "search_queries": ["drug trafficking HKSAR appeal", "dangerous drugs possession HKSAR", "ketamine trafficking HKSAR sentence"],
                    }
                ],
                "children": [
                    {"en": "Trafficking and possession", "zh": "販運與管有"},
                ],
            },
            {
                "id": "public_order_weapons",
                "label_en": "Public Order and Weapons",
                "label_zh": "公共秩序與武器",
                "summary_en": "Rioting, unlawful assembly, weapons, and protest-related criminal liability.",
                "summary_zh": "暴動、非法集結、武器及示威相關刑責。",
                "topics": [
                    {
                        "id": "public_order",
                        "label_en": "Public Order and Weapons",
                        "label_zh": "公共秩序與武器",
                        "search_queries": ["rioting HKSAR appeal", "unlawful assembly HKSAR", "possession offensive weapon HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Public order and weapons", "zh": "公共秩序與武器"},
                ],
            },
            {
                "id": "corruption_misconduct",
                "label_en": "Corruption and Misconduct",
                "label_zh": "貪污與公職失當",
                "summary_en": "Bribery, misconduct in public office, and corruption-linked conspiracies.",
                "summary_zh": "賄賂、公職人員行為失當及相關串謀。",
                "topics": [
                    {
                        "id": "bribery_misconduct",
                        "label_en": "Bribery and Misconduct in Public Office",
                        "label_zh": "賄賂與公職人員行為失當",
                        "search_queries": ["bribery HKSAR appeal", "misconduct in public office HKSAR", "prevention of bribery ordinance HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Bribery and public office misconduct", "zh": "賄賂與公職失當"},
                ],
            },
            {
                "id": "money_laundering",
                "label_en": "Money Laundering",
                "label_zh": "洗黑錢",
                "summary_en": "Money laundering, dealing with proceeds of crime under OSCO (Cap. 455) and DTROP (Cap. 405).",
                "summary_zh": "洗黑錢、處理犯罪得益（第455章及第405章）。",
                "topics": [
                    {
                        "id": "money_laundering",
                        "label_en": "Money Laundering",
                        "label_zh": "洗黑錢",
                        "search_queries": ["money laundering HKSAR appeal", "organized serious crimes ordinance cap 455 HKSAR", "dealing with proceeds crime HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Money laundering and proceeds of crime", "zh": "洗黑錢與犯罪得益"},
                ],
            },
            {
                "id": "computer_crimes",
                "label_en": "Computer Crimes",
                "label_zh": "電腦罪行",
                "summary_en": "Unauthorised access to computers, online fraud, and technology-related offences.",
                "summary_zh": "未經授權取用電腦、網絡欺詐及科技相關罪行。",
                "topics": [
                    {
                        "id": "computer_crimes",
                        "label_en": "Computer Crimes",
                        "label_zh": "電腦罪行",
                        "search_queries": ["access to computer with criminal intent HKSAR", "section 161 crimes ordinance HKSAR", "computer crime hong kong criminal"],
                    }
                ],
                "children": [
                    {"en": "Unauthorised computer access and online fraud", "zh": "未經授權取用電腦與網絡詐騙"},
                ],
            },
            {
                "id": "tax_evasion",
                "label_en": "Tax Evasion",
                "label_zh": "逃稅",
                "summary_en": "Tax evasion and related offences under the Inland Revenue Ordinance (Cap. 112).",
                "summary_zh": "逃稅及《稅務條例》（第112章）相關罪行。",
                "topics": [
                    {
                        "id": "tax_evasion",
                        "label_en": "Tax Evasion",
                        "label_zh": "逃稅",
                        "search_queries": ["tax evasion HKSAR criminal", "inland revenue ordinance cap 112 HKSAR", "wilful tax evasion hong kong"],
                    }
                ],
                "children": [
                    {"en": "Tax evasion offences", "zh": "逃稅罪行"},
                ],
            },
        ],
    },
    {
        "id": "defences",
        "label_en": "Defences",
        "label_zh": "抗辯事由",
        "summary_en": "Substantive and excuse-based defences across criminal liability.",
        "summary_zh": "涵蓋實質性及免責性抗辯。",
        "subgrounds": [
            {
                "id": "self_defence",
                "label_en": "Self-defence",
                "label_zh": "自衛",
                "summary_en": "Reasonable force, defensive action, and proportionality.",
                "summary_zh": "合理武力、防衛行為及相稱性。",
                "topics": [
                    {
                        "id": "self_defence_reasonable_force",
                        "label_en": "Self-defence and Reasonable Force",
                        "label_zh": "自衛與合理武力",
                        "search_queries": ["self defence HKSAR criminal", "reasonable force HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Reasonable force", "zh": "合理武力"},
                ],
            },
            {
                "id": "duress_necessity",
                "label_en": "Duress and Necessity",
                "label_zh": "脅迫與必要性",
                "summary_en": "Excusatory defences grounded in coercion or emergency.",
                "summary_zh": "基於脅迫或緊急情況的抗辯。",
                "topics": [
                    {
                        "id": "duress",
                        "label_en": "Duress and Necessity",
                        "label_zh": "脅迫與必要性",
                        "search_queries": ["duress HKSAR criminal", "necessity defence HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Duress and necessity", "zh": "脅迫與必要性"},
                ],
            },
            {
                "id": "mental_condition_intoxication",
                "label_en": "Mental Condition and Intoxication",
                "label_zh": "精神狀態與醉酒",
                "summary_en": "Insanity, automatism, diminished responsibility, and intoxication.",
                "summary_zh": "精神失常、自動行為、責任能力減低及醉酒。",
                "topics": [
                    {
                        "id": "insanity_intoxication",
                        "label_en": "Insanity, Automatism, and Intoxication",
                        "label_zh": "精神失常、自動行為與醉酒",
                        "search_queries": ["insanity HKSAR criminal", "automatism HKSAR criminal", "intoxication defence HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Insanity and intoxication", "zh": "精神失常與醉酒"},
                ],
            },
        ],
    },
    {
        "id": "evidence_procedure",
        "label_en": "Criminal Evidence and Procedure",
        "label_zh": "刑事證據與程序",
        "summary_en": "Evidence doctrines, investigative powers, fair-trial issues, and procedure.",
        "summary_zh": "證據法、調查權、公平審訊及程序問題。",
        "subgrounds": [
            {
                "id": "confession_exclusion",
                "label_en": "Confession and Exclusion",
                "label_zh": "招認與排除",
                "summary_en": "Voluntariness, oppression, and exclusionary doctrines.",
                "summary_zh": "自願性、壓迫及排除規則。",
                "topics": [
                    {
                        "id": "confessions",
                        "label_en": "Confessions",
                        "label_zh": "招認",
                        "search_queries": ["confession evidence HKSAR criminal", "voluntariness confession HKSAR", "oppression confession HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Voluntariness and exclusion", "zh": "自願性與排除"},
                ],
            },
            {
                "id": "identification_hearsay",
                "label_en": "Identification and Hearsay",
                "label_zh": "辨認與傳聞",
                "summary_en": "Visual identification, hearsay limits, and reliability concerns.",
                "summary_zh": "目擊辨認、傳聞限制及可靠性問題。",
                "topics": [
                    {
                        "id": "identification_evidence",
                        "label_en": "Identification Evidence",
                        "label_zh": "辨認證據",
                        "search_queries": ["identification evidence HKSAR criminal", "Turnbull HKSAR criminal"],
                    },
                    {
                        "id": "hearsay",
                        "label_en": "Hearsay",
                        "label_zh": "傳聞證據",
                        "search_queries": ["hearsay HKSAR criminal", "criminal hearsay ordinance HKSAR"],
                    },
                ],
                "children": [
                    {"en": "Identification evidence", "zh": "辨認證據"},
                    {"en": "Hearsay", "zh": "傳聞證據"},
                ],
            },
            {
                "id": "arrest_search_fair_trial",
                "label_en": "Arrest, Search, and Fair Trial",
                "label_zh": "拘捕、搜查與公平審訊",
                "summary_en": "Police powers, disclosure, and procedural fairness in criminal litigation.",
                "summary_zh": "警方權力、披露義務及刑事訴訟中的程序公平。",
                "topics": [
                    {
                        "id": "investigative_powers",
                        "label_en": "Arrest, Search, and Fair Trial",
                        "label_zh": "拘捕、搜查與公平審訊",
                        "search_queries": ["arrest search HKSAR criminal", "fair trial HKSAR criminal appeal", "disclosure criminal HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Investigative powers and fairness", "zh": "調查權與程序公平"},
                ],
            },
            {
                "id": "expert_evidence",
                "label_en": "Expert Evidence",
                "label_zh": "專家證據",
                "summary_en": "Admissibility and reliability of expert evidence in criminal proceedings.",
                "summary_zh": "刑事訴訟中專家證據的可接納性及可靠性。",
                "topics": [
                    {
                        "id": "expert_evidence",
                        "label_en": "Expert Evidence",
                        "label_zh": "專家證據",
                        "search_queries": ["expert evidence HKSAR criminal", "expert witness admissibility HKSAR", "forensic evidence HKSAR criminal"],
                    }
                ],
                "children": [
                    {"en": "Expert evidence admissibility", "zh": "專家證據可接納性"},
                ],
            },
            {
                "id": "character_bad_acts",
                "label_en": "Character and Similar Fact Evidence",
                "label_zh": "品格與類似事實證據",
                "summary_en": "Character evidence, similar fact evidence, and propensity reasoning.",
                "summary_zh": "品格證據、類似事實證據及傾向推理。",
                "topics": [
                    {
                        "id": "character_evidence",
                        "label_en": "Character and Similar Fact Evidence",
                        "label_zh": "品格與類似事實證據",
                        "search_queries": ["similar fact evidence HKSAR criminal", "character evidence HKSAR", "propensity evidence criminal HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Character and similar fact evidence", "zh": "品格與類似事實證據"},
                ],
            },
            {
                "id": "bail_remand",
                "label_en": "Bail and Remand",
                "label_zh": "保釋與還柙",
                "summary_en": "Bail applications, conditions, and remand in custody.",
                "summary_zh": "保釋申請、條件及還柙羈押。",
                "topics": [
                    {
                        "id": "bail",
                        "label_en": "Bail and Remand",
                        "label_zh": "保釋與還柙",
                        "search_queries": ["bail HKSAR criminal", "remand custody HKSAR", "bail application criminal HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Bail and remand", "zh": "保釋與還柙"},
                ],
            },
        ],
    },
    {
        "id": "appeals_sentencing",
        "label_en": "Appeals, Sentencing, and Confiscation",
        "label_zh": "上訴、量刑與沒收",
        "summary_en": "Appeal standards, sentencing methodology, and proceeds-related orders.",
        "summary_zh": "上訴標準、量刑方法及收益沒收。",
        "subgrounds": [
            {
                "id": "conviction_appeals",
                "label_en": "Conviction Appeals",
                "label_zh": "定罪上訴",
                "summary_en": "Unsafe verdicts, leave standards, and appellate intervention.",
                "summary_zh": "不安全裁決、上訴許可及介入標準。",
                "topics": [
                    {
                        "id": "appeal_standards",
                        "label_en": "Conviction Appeals",
                        "label_zh": "定罪上訴",
                        "search_queries": ["criminal appeal HKSAR conviction unsafe", "leave to appeal conviction HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Unsafe verdicts and appellate review", "zh": "不安全裁決與上訴審查"},
                ],
            },
            {
                "id": "sentencing",
                "label_en": "Sentencing",
                "label_zh": "量刑",
                "summary_en": "Tariffs, totality, guilty pleas, mitigation, and aggravation.",
                "summary_zh": "量刑起點、整體性、認罪扣減、減刑及加刑因素。",
                "topics": [
                    {
                        "id": "sentencing_principles",
                        "label_en": "Sentencing Principles",
                        "label_zh": "量刑原則",
                        "search_queries": ["sentencing principle HKSAR criminal", "guilty plea discount HKSAR", "totality sentencing HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Tariffs and totality", "zh": "量刑起點與整體性"},
                ],
            },
            {
                "id": "confiscation_proceeds",
                "label_en": "Confiscation and Proceeds",
                "label_zh": "沒收與犯罪得益",
                "summary_en": "Drug-trafficking proceeds, confiscation orders, and financial penalties.",
                "summary_zh": "販毒得益、沒收令及財產處分。",
                "topics": [
                    {
                        "id": "confiscation_orders",
                        "label_en": "Confiscation and Proceeds",
                        "label_zh": "沒收與犯罪得益",
                        "search_queries": ["confiscation order HKSAR criminal", "drug trafficking recovery proceeds HKSAR"],
                    }
                ],
                "children": [
                    {"en": "Confiscation and proceeds", "zh": "沒收與犯罪得益"},
                ],
            },
        ],
    },
    {
        "id": "regulatory_and_welfare_offences",
        "label_en": "Regulatory and Welfare Offences",
        "label_zh": "規管及福利罪行",
        "summary_en": "Offences under regulatory ordinances protecting animals, the environment, and public welfare.",
        "summary_zh": "保護動物、環境及公眾福祉的規管條例下的罪行。",
        "subgrounds": [
            {
                "id": "animal_cruelty",
                "label_en": "Animal Cruelty",
                "label_zh": "虐待動物",
                "summary_en": "Offences of cruelty, neglect, and unnecessary suffering under the Prevention of Cruelty to Animals Ordinance (Cap. 169).",
                "summary_zh": "根據《防止殘酷對待動物條例》（第169章）的虐待、疏忽及不必要痛苦罪行。",
                "topics": [
                    {
                        "id": "prevention_cruelty_animals",
                        "label_en": "Prevention of Cruelty to Animals Ordinance (Cap. 169)",
                        "label_zh": "防止殘酷對待動物條例（第169章）",
                        "search_queries": [
                            "prevention of cruelty to animals ordinance cap 169 hong kong",
                            "animal cruelty offence hong kong criminal",
                            "unnecessary suffering animal hong kong",
                            "SPCA hong kong animal welfare prosecution",
                            "cruelty to animals HKSAR conviction",
                            "animal welfare ordinance hong kong",
                            "stabbing animal hong kong offence",
                            "injuring animal hong kong criminal liability",
                        ],
                    },
                    {
                        "id": "animal_welfare_sentencing",
                        "label_en": "Animal Cruelty Sentencing",
                        "label_zh": "虐待動物量刑",
                        "search_queries": [
                            "animal cruelty sentencing hong kong",
                            "cap 169 penalty hong kong",
                            "imprisonment animal cruelty hong kong",
                        ],
                    },
                ],
                "children": [
                    {"en": "Unnecessary suffering and cruelty", "zh": "不必要痛苦與虐待"},
                    {"en": "Neglect and abandonment", "zh": "疏忽及遺棄"},
                    {"en": "Sentencing for animal cruelty", "zh": "虐待動物量刑"},
                ],
            },
            {
                "id": "road_traffic",
                "label_en": "Road Traffic Offences",
                "label_zh": "道路交通罪行",
                "summary_en": "Dangerous driving, drink driving, and causing death by dangerous driving under Cap. 374.",
                "summary_zh": "危險駕駛、醉酒駕駛及因危險駕駛引致死亡（第374章）。",
                "topics": [
                    {
                        "id": "dangerous_driving",
                        "label_en": "Dangerous Driving and Road Traffic Offences",
                        "label_zh": "危險駕駛與道路交通罪行",
                        "search_queries": [
                            "dangerous driving HKSAR appeal",
                            "causing death by dangerous driving HKSAR",
                            "drink driving HKSAR criminal",
                            "road traffic ordinance cap 374 HKSAR",
                        ],
                    }
                ],
                "children": [
                    {"en": "Dangerous driving and drink driving", "zh": "危險駕駛及醉駕"},
                ],
            },
            {
                "id": "environmental_offences",
                "label_en": "Environmental Offences",
                "label_zh": "環境罪行",
                "summary_en": "Pollution, waste dumping, and environmental protection offences.",
                "summary_zh": "污染、廢物傾倒及環境保護罪行。",
                "topics": [
                    {
                        "id": "environmental_crimes",
                        "label_en": "Environmental Offences",
                        "label_zh": "環境罪行",
                        "search_queries": [
                            "water pollution HKSAR criminal",
                            "waste disposal ordinance HKSAR prosecution",
                            "environmental protection HKSAR criminal",
                        ],
                    }
                ],
                "children": [
                    {"en": "Pollution and environmental protection", "zh": "污染與環保"},
                ],
            },
            {
                "id": "occupational_safety",
                "label_en": "Occupational Safety Offences",
                "label_zh": "職業安全罪行",
                "summary_en": "Industrial safety offences, construction-site fatalities, and employer liability.",
                "summary_zh": "工業安全罪行、工地死亡事故及僱主責任。",
                "topics": [
                    {
                        "id": "workplace_safety",
                        "label_en": "Occupational Safety Offences",
                        "label_zh": "職業安全罪行",
                        "search_queries": [
                            "occupational safety HKSAR prosecution",
                            "factories and industrial undertakings HKSAR",
                            "construction site fatality HKSAR criminal",
                        ],
                    }
                ],
                "children": [
                    {"en": "Occupational safety and employer liability", "zh": "職業安全與僱主責任"},
                ],
            },
        ],
    },
]


def iter_criminal_topics() -> list[dict]:
    topics: list[dict] = []
    for module in CRIMINAL_AUTHORITY_TREE:
        for subground in module["subgrounds"]:
            for topic in subground.get("topics", []):
                topics.append(
                    {
                        **topic,
                        "module_id": module["id"],
                        "module_label_en": module["label_en"],
                        "module_label_zh": module["label_zh"],
                        "subground_id": subground["id"],
                        "subground_label_en": subground["label_en"],
                        "subground_label_zh": subground["label_zh"],
                        "summary_en": subground["summary_en"],
                        "summary_zh": subground["summary_zh"],
                    }
                )
    return topics
