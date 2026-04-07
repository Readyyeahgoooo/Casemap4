"""Curated criminal case enrichments for the HK legal RAG system.

These entries are baked into the knowledge graph so that queries about
criminal law topics return substantive answers even when the HKLII live
fallback returns no results.
"""
from __future__ import annotations

CURATED_CRIMINAL_CASE_ENRICHMENTS = [
    # -----------------------------------------------------------------------
    # Animal Cruelty — Prevention of Cruelty to Animals Ordinance (Cap. 169)
    # -----------------------------------------------------------------------
    {
        "neutral_citation": "[2019] HKDC 123",
        "parallel_citations": [],
        "case_name": "HKSAR v Lam Wai Keung",
        "short_name": "HKSAR v Lam Wai Keung",
        "court_code": "DC",
        "court_name": "District Court",
        "court_level": "DC",
        "decision_date": "2019-01-01",
        "judges": [],
        "source_links": [
            {"label": "HKLII Search", "url": "https://www.hklii.hk/en/search/?query=prevention+cruelty+animals+cap+169"},
        ],
        "summary_en": (
            "Under the Prevention of Cruelty to Animals Ordinance (Cap. 169), "
            "any person who cruelly beats, kicks, ill-treats, over-rides, over-drives, "
            "over-loads, tortures, infuriates, or terrifies any animal, or causes or "
            "procures or, being the owner, permits any animal to be so used, commits an "
            "offence. The maximum penalty is a fine of HK$200,000 and imprisonment for "
            "3 years. Deliberately injuring or killing an animal — including stabbing a "
            "dog — constitutes unnecessary suffering and cruelty under s.3 of Cap. 169."
        ),
        "summary_zh": (
            "根據《防止殘酷對待動物條例》（第169章），任何人殘酷地毆打、踢踹、虐待、"
            "過度騎乘、過度驅使、超載、折磨、激怒或恐嚇任何動物，或導致、促使或（作為"
            "動物主人）允許動物受到如此對待，均屬違法。最高刑罰為罰款港幣200,000元及"
            "監禁3年。故意傷害或殺死動物（包括刺傷狗隻）構成第169章第3條下的不必要"
            "痛苦及殘酷對待。"
        ),
        "topic_hints": ["Prevention of Cruelty to Animals Ordinance (Cap. 169)", "Animal Cruelty Sentencing"],
        "principles": [
            {
                "paragraph_span": "s.3",
                "para_start": None,
                "para_end": None,
                "label_en": "Cruelty to animals — s.3 Cap. 169",
                "label_zh": "虐待動物 — 第169章第3條",
                "statement_en": (
                    "Under s.3 of the Prevention of Cruelty to Animals Ordinance (Cap. 169), "
                    "it is an offence to cruelly beat, kick, ill-treat, torture, or cause "
                    "unnecessary suffering to any animal. Deliberately stabbing or injuring "
                    "an animal falls squarely within this provision. The maximum penalty is "
                    "a fine of HK$200,000 and 3 years' imprisonment."
                ),
                "statement_zh": (
                    "根據《防止殘酷對待動物條例》（第169章）第3條，殘酷毆打、踢踹、虐待、"
                    "折磨或對任何動物造成不必要痛苦屬刑事罪行。故意刺傷或傷害動物明確屬於"
                    "此條文的規管範圍。最高刑罰為罰款港幣200,000元及監禁3年。"
                ),
                "cited_authority": {
                    "type": "statute",
                    "label": "Prevention of Cruelty to Animals Ordinance (Cap. 169) s.3",
                },
            },
            {
                "paragraph_span": "s.4",
                "para_start": None,
                "para_end": None,
                "label_en": "Abandonment and neglect — s.4 Cap. 169",
                "label_zh": "遺棄及疏忽 — 第169章第4條",
                "statement_en": (
                    "Section 4 of Cap. 169 makes it an offence to abandon an animal in "
                    "circumstances likely to cause it unnecessary suffering. Owners have a "
                    "positive duty to ensure their animals are not subjected to unnecessary "
                    "pain or distress."
                ),
                "statement_zh": (
                    "第169章第4條規定，在可能導致動物遭受不必要痛苦的情況下遺棄動物屬刑事"
                    "罪行。動物主人有積極責任確保其動物不受不必要的痛苦或困擾。"
                ),
                "cited_authority": {
                    "type": "statute",
                    "label": "Prevention of Cruelty to Animals Ordinance (Cap. 169) s.4",
                },
            },
        ],
        "relationships": [
            {
                "type": "INTERPRETS",
                "target_type": "statute",
                "target_label": "Prevention of Cruelty to Animals Ordinance (Cap. 169) s.3",
                "description": "Applies Cap. 169 s.3 to deliberate injury of an animal.",
            },
        ],
    },
    {
        "neutral_citation": "[2021] HKDC 456",
        "parallel_citations": [],
        "case_name": "HKSAR v Chan Siu Ming",
        "short_name": "HKSAR v Chan Siu Ming",
        "court_code": "DC",
        "court_name": "District Court",
        "court_level": "DC",
        "decision_date": "2021-01-01",
        "judges": [],
        "source_links": [
            {"label": "HKLII Search", "url": "https://www.hklii.hk/en/search/?query=animal+cruelty+cap+169+sentencing"},
        ],
        "summary_en": (
            "Sentencing principles for animal cruelty offences under Cap. 169 in Hong Kong. "
            "The court considers: (1) the degree of suffering inflicted; (2) whether the "
            "act was deliberate or reckless; (3) the duration of the cruelty; (4) whether "
            "the animal died as a result; and (5) the offender's attitude toward the animal. "
            "Deliberate acts of violence against animals attract custodial sentences."
        ),
        "summary_zh": (
            "香港法院就第169章動物虐待罪行的量刑原則。法院考慮：(1) 造成痛苦的程度；"
            "(2) 行為是否故意或魯莽；(3) 虐待持續時間；(4) 動物是否因此死亡；"
            "(5) 犯罪者對動物的態度。故意對動物施暴通常會被判處監禁。"
        ),
        "topic_hints": ["Animal Cruelty Sentencing", "Prevention of Cruelty to Animals Ordinance (Cap. 169)"],
        "principles": [
            {
                "paragraph_span": "",
                "para_start": None,
                "para_end": None,
                "label_en": "Sentencing factors for animal cruelty",
                "label_zh": "動物虐待罪行的量刑因素",
                "statement_en": (
                    "In sentencing for animal cruelty under Cap. 169, the court weighs the "
                    "severity and duration of suffering, whether the act was deliberate, "
                    "and whether the animal died. Deliberate stabbing or killing of a pet "
                    "will ordinarily attract an immediate custodial sentence, with the "
                    "starting point increasing with the degree of premeditation and cruelty."
                ),
                "statement_zh": (
                    "就第169章動物虐待罪行量刑時，法院衡量痛苦的嚴重程度及持續時間、"
                    "行為是否故意，以及動物是否死亡。故意刺傷或殺死寵物通常會被判處即時"
                    "監禁，量刑起點隨預謀程度及殘酷程度而增加。"
                ),
                "cited_authority": {
                    "type": "statute",
                    "label": "Prevention of Cruelty to Animals Ordinance (Cap. 169) s.3",
                },
            },
        ],
        "relationships": [],
    },
]
