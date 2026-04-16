from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
import json
import math
import os
import re
import ssl
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .case_enrichment_data import CURATED_CASE_ENRICHMENTS
from .criminal_enrichment_data import CURATED_CRIMINAL_CASE_ENRICHMENTS
from .embeddings import create_embedding_backend
from .graphrag import normalize_scores, slugify, tokenize
from .hklii_crawler import HKLIICrawler
from .lineage_discovery import append_hallucination_log
from .relationship_graph import export_public_relationship_payload

CASE_EDGE_TYPES = {"CITES", "FOLLOWS", "APPLIES", "DISTINGUISHES", "OVERRULES", "DOUBTS"}
TREATMENT_EDGE_TYPES = {"FOLLOWS", "APPLIES", "DISTINGUISHES", "OVERRULES", "DOUBTS", "INTERPRETS"}
COURT_LEVEL_SCORES = {"CFA": 1.0, "CA": 0.82, "CFI": 0.6, "DC": 0.45, "TRIB": 0.3}
VECTOR_DIMENSIONS = 1536
NEO4J_CONSTRAINTS_CYPHER = f"""// Core uniqueness constraints
CREATE CONSTRAINT module_id IF NOT EXISTS FOR (n:Module) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT subground_id IF NOT EXISTS FOR (n:Subground) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (n:Topic) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_path IF NOT EXISTS FOR (n:Topic) REQUIRE n.path IS UNIQUE;
CREATE CONSTRAINT lineage_id IF NOT EXISTS FOR (n:AuthorityLineage) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT statute_id IF NOT EXISTS FOR (n:Statute) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT paragraph_id IF NOT EXISTS FOR (n:Paragraph) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT proposition_id IF NOT EXISTS FOR (n:Proposition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT judge_id IF NOT EXISTS FOR (n:Judge) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:SourceDocument) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT case_neutral_citation IF NOT EXISTS FOR (n:Case) REQUIRE n.neutral_citation IS UNIQUE;
CREATE CONSTRAINT statute_cap_section_key IF NOT EXISTS FOR (n:Statute) REQUIRE n.cap_section_key IS UNIQUE;

// Search indexes
CREATE INDEX case_name IF NOT EXISTS FOR (n:Case) ON (n.case_name);
CREATE INDEX case_court_code IF NOT EXISTS FOR (n:Case) ON (n.court_code);
CREATE INDEX case_decision_date IF NOT EXISTS FOR (n:Case) ON (n.decision_date);
CREATE INDEX topic_label_en IF NOT EXISTS FOR (n:Topic) ON (n.label_en);

// Vector indexes
CREATE VECTOR INDEX case_summary_embedding IF NOT EXISTS
FOR (n:Case) ON (n.summary_embedding)
OPTIONS {{indexConfig: {{`vector.dimensions`: {VECTOR_DIMENSIONS}, `vector.similarity_function`: 'cosine'}}}};

CREATE VECTOR INDEX paragraph_embedding IF NOT EXISTS
FOR (n:Paragraph) ON (n.embedding)
OPTIONS {{indexConfig: {{`vector.dimensions`: {VECTOR_DIMENSIONS}, `vector.similarity_function`: 'cosine'}}}};
"""

NEO4J_IMPORT_TEMPLATE = """// Requires APOC for dynamic labels.
// Load hierarchical_graph.json externally and pass {nodes: [...], edges: [...]} as parameters.
UNWIND $nodes AS node
CALL apoc.merge.node([node.type], {id: node.id}, node, node) YIELD node AS merged_node
RETURN count(merged_node) AS merged_nodes;

UNWIND $edges AS edge
MATCH (source {id: edge.source})
MATCH (target {id: edge.target})
CALL apoc.merge.relationship(source, edge.type, {source: edge.source, target: edge.target}, edge, target)
YIELD rel
RETURN count(rel) AS merged_relationships;
"""

OPENROUTER_API_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEFAULT_MODEL = "openrouter/auto"
OPENROUTER_TIMEOUT_SECONDS = 25
OPENROUTER_CITATION_TAG_RE = re.compile(r"\[(C\d+)\]")
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "by",
    "can",
    "could",
    "do",
    "does",
    "for",
    "from",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "legal",
    "liability",
    "my",
    "of",
    "on",
    "or",
    "own",
    "the",
    "their",
    "there",
    "to",
    "under",
    "what",
    "when",
    "which",
    "with",
    "would",
    # Domain stopwords: appear in nearly every criminal-law node,
    # so they add noise rather than signal to lexical scoring.
    "hong",
    "kong",
    "criminal",
    "crime",
    "crimes",
    "hksar",
    "offence",
    "offences",
    "offense",
    "law",
}

# Maps inflected / colloquial verb forms to their canonical legal token.
# Applied during score token expansion so that "stealing my friend's jacket"
# surfaces theft propositions even though the graph uses "theft"/"appropriation".
QUERY_SYNONYMS: dict[str, str] = {
    # Theft
    "stealing": "theft",
    "steal": "theft",
    "stole": "theft",
    "stolen": "theft",
    "shoplifting": "theft",
    "shoplift": "theft",
    "shoplifted": "theft",
    "took": "theft",
    "taking": "theft",
    "appropriating": "appropriation",
    "appropriated": "appropriation",
    # Robbery
    "robbing": "robbery",
    "robbed": "robbery",
    "rob": "robbery",
    # Burglary
    "burgling": "burglary",
    "burgled": "burglary",
    "broke": "burglary",
    "breaking": "burglary",
    # Homicide
    "killing": "murder",
    "killed": "murder",
    "kill": "murder",
    "slaying": "murder",
    "slew": "murder",
    # Assault / violence
    "beating": "assault",
    "beat": "assault",
    "hit": "assault",
    "hitting": "assault",
    "punching": "assault",
    "punch": "assault",
    "punched": "assault",
    "kicked": "assault",
    "kicking": "assault",
    "attacking": "assault",
    "attacked": "assault",
    # Stabbing / wounding — NOTE: "stabbing" is NOT mapped here
    # because CRIMINAL_QUERY_HINTS already handle the expansion
    # and adding "wounding" to scoring_tokens would boost the
    # "Assault and Wounding" topic even for "stab a dog" queries.
    "slashing": "wounding",
    "slashed": "wounding",
    # Fraud / deception
    "cheating": "deception",
    "cheat": "deception",
    "cheated": "deception",
    "tricking": "deception",
    "tricked": "deception",
    "scamming": "fraud",
    "scammed": "fraud",
    "scam": "fraud",
    # Drugs
    "dealing": "trafficking",
    "deal": "trafficking",
    "dealt": "trafficking",
    # Driving
    "drove": "driving",
    "drunk": "drink",
    "drinking": "drink",
    # Sexual offences
    "raping": "rape",
    "raped": "rape",
    # Damage
    "burning": "arson",
    "burned": "arson",
    "burnt": "arson",
    "destroying": "damage",
    "destroyed": "damage",
    # Handling / laundering
    "laundering": "laundering",
    "launder": "laundering",
    "laundered": "laundering",
    # Securities / market misconduct
    "manipulating": "manipulation",
    "manipulated": "manipulation",
    "manipulative": "manipulation",
    # Bribing
    "bribing": "bribery",
    "bribed": "bribery",
    "bribe": "bribery",
}

PLACEHOLDER_SUMMARY_PATTERNS = (
    "authority cited inside an hklii",
    "hong kong legislation cited in",
    "case linked to",
    "current graph placeholder",
)


def _is_placeholder_summary(text: str) -> bool:
    normalized = " ".join((text or "").strip().lower().split())
    return bool(normalized) and any(pattern in normalized for pattern in PLACEHOLDER_SUMMARY_PATTERNS)


CRIMINAL_QUERY_HINTS = {
    # Animal welfare
    "dog": ["animal cruelty dog hong kong", "prevention of cruelty to animals ordinance cap 169 hong kong"],
    "animal": ["animal cruelty hong kong", "prevention of cruelty to animals ordinance cap 169 hong kong"],
    "pet": ["animal cruelty pet hong kong", "prevention of cruelty to animals hong kong"],
    "cat": ["animal cruelty cat hong kong", "prevention of cruelty to animals hong kong"],
    "bird": ["animal cruelty bird hong kong", "prevention of cruelty to animals hong kong"],
    "livestock": ["animal cruelty livestock hong kong", "prevention of cruelty to animals hong kong"],
    "wildlife": ["wildlife protection hong kong criminal", "animals ordinance hong kong"],
    "cruelty": ["animal cruelty hong kong", "prevention of cruelty to animals ordinance cap 169"],
    "stab": ["assault wounding hong kong criminal", "grievous bodily harm stabbing HKSAR"],
    "stabbing": ["assault wounding hong kong criminal", "grievous bodily harm stabbing HKSAR"],
    "wound": ["wounding hong kong criminal", "grievous bodily harm HKSAR"],
    "wounding": ["wounding hong kong criminal", "offences against the person HKSAR"],
    "grievous": ["grievous bodily harm hong kong criminal", "offences against the person HKSAR"],
    "bodily": ["grievous bodily harm hong kong criminal", "assault occasioning HKSAR"],
    "gbh": ["grievous bodily harm hong kong criminal", "wounding HKSAR"],
    # Evidence
    "hearsay": ["hearsay evidence criminal hong kong"],
    "confession": ["confession evidence criminal hong kong", "admissibility confession HKSAR"],
    "identification": ["identification evidence criminal hong kong", "dock identification HKSAR"],
    "corroboration": ["corroboration evidence criminal hong kong"],
    "admissibility": ["admissibility evidence criminal hong kong"],
    "witness": ["witness evidence criminal hong kong", "accomplice witness HKSAR"],
    # Sentencing
    "sentencing": ["sentencing criminal hong kong", "sentencing guidelines HKSAR"],
    "tariff": ["sentencing tariff hong kong criminal"],
    "mitigation": ["mitigation sentencing hong kong criminal"],
    "totality": ["totality principle sentencing hong kong"],
    # Corruption and bribery
    "bribery": ["bribery hong kong criminal", "prevention of bribery ordinance HKSAR"],
    "corruption": ["corruption ICAC hong kong criminal", "misconduct public office HKSAR"],
    # Money and financial crime
    "money": ["money laundering hong kong criminal", "drug trafficking proceeds HKSAR"],
    "laundering": ["money laundering hong kong criminal", "organized serious crimes ordinance HKSAR"],
    "fraud": ["fraud deception hong kong criminal", "theft ordinance fraud HKSAR"],
    "deception": ["deception offence hong kong criminal", "obtaining property deception HKSAR"],
    # Securities and market misconduct under the Securities and Futures Ordinance
    "market": ["market manipulation false trading securities futures ordinance cap 571", "market misconduct tribunal HKSAR", "false trading securities HKSAR"],
    "manipulation": ["market manipulation false trading securities futures ordinance cap 571", "managed manipulation securities HKSAR", "market misconduct tribunal HKSAR"],
    "securities": ["securities futures ordinance cap 571 market misconduct", "false trading securities HKSAR", "insider dealing securities HKSAR"],
    "futures": ["securities futures ordinance cap 571 market misconduct", "false trading securities HKSAR"],
    "sfo": ["securities futures ordinance cap 571 market misconduct", "false trading securities HKSAR"],
    "sfc": ["securities futures commission market misconduct HKSAR", "market manipulation SFC HKSAR"],
    "insider": ["insider dealing securities futures ordinance HKSAR", "market misconduct insider dealing HKSAR"],
    "misconduct": ["market misconduct securities futures ordinance HKSAR", "market manipulation false trading HKSAR"],
    # Theft and property offences
    "theft": ["theft hong kong criminal", "theft ordinance HKSAR"],
    "steal": ["theft hong kong criminal", "theft ordinance HKSAR"],
    "stealing": ["theft hong kong criminal", "theft ordinance HKSAR"],
    "stole": ["theft hong kong criminal", "theft ordinance HKSAR"],
    "stolen": ["theft hong kong criminal", "theft ordinance HKSAR"],
    "shoplifting": ["theft shoplifting hong kong criminal", "theft ordinance HKSAR"],
    "robbery": ["robbery hong kong criminal", "armed robbery HKSAR"],
    "robbing": ["robbery hong kong criminal", "armed robbery HKSAR"],
    "rob": ["robbery hong kong criminal", "armed robbery HKSAR"],
    "burglary": ["burglary hong kong criminal", "breaking entering HKSAR"],
    "blackmail": ["blackmail extortion hong kong criminal"],
    "handling": ["handling stolen goods hong kong criminal"],
    # Drug offences
    "drug": ["drug trafficking hong kong criminal", "dangerous drugs ordinance HKSAR"],
    "narcotic": ["narcotic drug offence hong kong", "dangerous drugs ordinance HKSAR"],
    "trafficking": ["drug trafficking hong kong criminal", "dangerous drugs ordinance cap 134 HKSAR"],
    "possession": ["possession dangerous drugs hong kong", "drug possession HKSAR criminal"],
    "cannabis": ["cannabis drug offence hong kong criminal"],
    "heroin": ["heroin drug trafficking hong kong criminal"],
    # Road traffic
    "driving": ["dangerous driving hong kong criminal", "road traffic ordinance HKSAR"],
    "vehicle": ["road traffic offence hong kong criminal", "dangerous driving HKSAR"],
    "traffic": ["road traffic ordinance hong kong criminal", "careless driving HKSAR"],
    "accident": ["road traffic accident hong kong criminal liability"],
    "drink": ["drink driving hong kong criminal", "driving under influence HKSAR"],
    # Sexual offences
    "rape": ["rape sexual offence hong kong criminal", "crimes ordinance rape HKSAR"],
    "sexual": ["sexual offence hong kong criminal", "indecent assault HKSAR"],
    "indecent": ["indecent assault hong kong criminal", "sexual offence HKSAR"],
    "assault": ["assault hong kong criminal", "common assault HKSAR"],
    # Public order
    "riot": ["riot public order hong kong criminal", "public order ordinance HKSAR"],
    "affray": ["affray hong kong criminal", "public order offence HKSAR"],
    "unlawful": ["unlawful assembly hong kong criminal", "public order ordinance HKSAR"],
    # Firearms and weapons
    "firearm": ["firearm offence hong kong criminal", "firearms ordinance HKSAR"],
    "weapon": ["offensive weapon hong kong criminal", "possession weapon HKSAR"],
    "arms": ["arms ammunition hong kong criminal", "firearms ordinance HKSAR"],
    "knife": ["offensive weapon knife hong kong criminal"],
    # Homicide
    "murder": ["murder hong kong criminal", "homicide HKSAR"],
    "manslaughter": ["manslaughter hong kong criminal", "involuntary manslaughter HKSAR"],
    "killing": ["homicide killing hong kong criminal"],
    # Defences
    "self": ["self defence hong kong criminal", "defence of person HKSAR"],
    "insanity": ["insanity defence hong kong criminal", "mental disorder HKSAR"],
    "duress": ["duress defence hong kong criminal"],
    "intoxication": ["intoxication defence hong kong criminal", "voluntary intoxication HKSAR"],
    # Kidnapping and false imprisonment
    "kidnap": ["kidnapping hong kong criminal", "false imprisonment HKSAR"],
    "kidnapping": ["kidnapping hong kong criminal", "abduction HKSAR"],
    "imprison": ["false imprisonment hong kong criminal"],
    "detention": ["unlawful detention hong kong criminal"],
    # Intimidation and threats
    "intimidat": ["criminal intimidation hong kong", "intimidation offence HKSAR"],
    "blackmail": ["blackmail extortion hong kong criminal", "criminal intimidation HKSAR"],
    "threat": ["criminal threats hong kong", "threats to kill HKSAR"],
    # Forgery
    "forgery": ["forgery hong kong criminal", "using false instrument HKSAR"],
    "counterfeit": ["counterfeiting hong kong criminal"],
    "forging": ["forgery document hong kong criminal"],
    # Criminal damage and arson
    "arson": ["arson hong kong criminal", "criminal damage fire HKSAR"],
    "damage": ["criminal damage hong kong", "crimes ordinance cap 60 HKSAR"],
    # Computer crime
    "computer": ["computer crime hong kong criminal", "section 161 crimes ordinance HKSAR"],
    "hacking": ["unauthorised access computer hong kong criminal"],
    "cyber": ["computer crime hong kong criminal", "online fraud HKSAR"],
    # Money laundering (expanded)
    "proceeds": ["proceeds of crime hong kong", "organized serious crimes ordinance HKSAR"],
    # Crypto / virtual asset financial crime
    "bitcoin": ["money laundering hong kong criminal", "proceeds of crime cryptocurrency HKSAR"],
    "crypto": ["money laundering hong kong criminal", "cryptocurrency virtual asset crime HKSAR"],
    "cryptocurrency": ["money laundering hong kong criminal", "virtual asset crime HKSAR"],
    "usdt": ["money laundering hong kong criminal", "proceeds of crime cryptocurrency HKSAR"],
    "tether": ["money laundering hong kong criminal", "proceeds of crime cryptocurrency HKSAR"],
    "ethereum": ["money laundering hong kong criminal", "cryptocurrency virtual asset crime HKSAR"],
    "wallet": ["money laundering hong kong criminal", "proceeds of crime cryptocurrency HKSAR"],
    "virtual": ["virtual asset crime hong kong", "money laundering cryptocurrency HKSAR"],
    "stablecoin": ["money laundering hong kong criminal", "virtual asset crime HKSAR"],
    # Tax evasion
    "tax": ["tax evasion hong kong criminal", "inland revenue ordinance HKSAR"],
    "evasion": ["tax evasion hong kong criminal"],
    # Expert evidence
    "expert": ["expert evidence hong kong criminal", "expert witness admissibility HKSAR"],
    "forensic": ["forensic evidence hong kong criminal"],
    "dna": ["DNA evidence hong kong criminal"],
    # Character evidence
    "character": ["character evidence hong kong criminal", "similar fact evidence HKSAR"],
    "propensity": ["propensity evidence hong kong criminal"],
    # Bail
    "bail": ["bail hong kong criminal", "bail application HKSAR"],
    "remand": ["remand custody hong kong criminal"],
    # Environmental
    "pollution": ["pollution offence hong kong criminal", "waste disposal ordinance HKSAR"],
    "environmental": ["environmental offence hong kong criminal"],
    # Occupational safety
    "occupational": ["occupational safety hong kong criminal", "factory ordinance HKSAR"],
    "workplace": ["workplace safety hong kong criminal prosecution"],
    "construction": ["construction site offence hong kong criminal"],
}


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _infer_legal_domain(metadata: dict | None) -> str:
    meta = metadata or {}
    explicit = str(meta.get("legal_domain", "")).strip().lower()
    if explicit:
        return explicit
    combined = " ".join(
        str(meta.get(key, ""))
        for key in (
            "title",
            "viewer_heading_public",
            "viewer_heading_internal",
            "viewer_intro_public",
            "viewer_intro_internal",
        )
    ).lower()
    if "criminal" in combined:
        return "criminal"
    return "contract"


def _domain_tags(metadata: dict | None, legal_domain: str) -> list[str]:
    meta = metadata or {}
    tags = [
        str(item).strip().lower()
        for item in meta.get("domain_tags", [])
        if str(item).strip()
    ]
    if legal_domain and legal_domain not in tags:
        tags.append(legal_domain)
    return tags


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _hklii_search_queries(question: str, legal_domain: str) -> list[str]:
    compact_question = re.sub(r"\s+", " ", question).strip()
    keywords = [token for token in tokenize(question) if token not in QUERY_STOPWORDS][:7]
    base_keywords = " ".join(keywords)
    queries = [compact_question, base_keywords]
    if legal_domain == "criminal" and base_keywords:
        queries.extend(
            [
                f"{base_keywords} hong kong criminal law",
                f"{base_keywords} offence hong kong",
            ]
        )
        for token in keywords:
            queries.extend(CRIMINAL_QUERY_HINTS.get(token, []))
    return _dedupe_strings(queries)


def _lexical_overlap_score(query_tokens: list[str], text: str, title: str = "") -> float:
    text_tokens = set(tokenize(text))
    if not text_tokens:
        return 0.0
    query_set = set(query_tokens)
    overlap = len(query_set & text_tokens)
    if not overlap:
        return 0.0
    score = overlap / max(math.sqrt(len(query_set) * len(text_tokens)), 1)
    title_tokens = set(tokenize(title))
    if title_tokens:
        score += 0.08 * len(query_set & title_tokens)
    return round(score, 6)


def _live_hklii_grounding(question: str, legal_domain: str, max_results: int = 4, max_citations: int = 8) -> dict:
    crawler = HKLIICrawler()
    query_tokens = tokenize(question)
    search_queries = _hklii_search_queries(question, legal_domain)
    search_trace: list[dict] = []
    public_paths: list[str] = []
    seen_paths: set[str] = set()
    for search_query in search_queries[:5]:
        results = crawler.simple_search(search_query, limit=max_results)
        search_trace.append({"query": search_query, "result_count": len(results)})
        for result in results:
            if result.path in seen_paths:
                continue
            seen_paths.add(result.path)
            public_paths.append(result.path)
            if len(public_paths) >= max_results:
                break
        if len(public_paths) >= max_results:
            break

    documents = crawler.crawl_paths(public_paths[:max_results]) if public_paths else []
    citation_pool: list[dict] = []
    for document in documents:
        ranked_paragraphs = sorted(
            (
                {
                    "paragraph_span": paragraph.paragraph_span,
                    "quote": paragraph.text.strip(),
                    "support_score": _lexical_overlap_score(query_tokens, paragraph.text, document.case_name) + 0.12,
                }
                for paragraph in document.paragraphs[:20]
                if paragraph.text.strip()
            ),
            key=lambda item: (item["support_score"], len(item["quote"])),
            reverse=True,
        )
        if not ranked_paragraphs:
            fallback_quote = (document.text or document.title or document.case_name).strip()
            if fallback_quote:
                ranked_paragraphs = [
                    {
                        "paragraph_span": "",
                        "quote": fallback_quote[:420],
                        "support_score": 0.08,
                    }
                ]
        for ranked in ranked_paragraphs[:2]:
            citation_pool.append(
                {
                    "case_id": f"hklii_live:{slugify(document.neutral_citation or document.case_name)[:80]}",
                    "focus_node_id": "",
                    "case_name": document.case_name,
                    "neutral_citation": document.neutral_citation,
                    "paragraph_span": ranked["paragraph_span"],
                    "principle_label": "Live HKLII fallback",
                    "quote": ranked["quote"],
                    "lineage_titles": [],
                    "support_score": ranked["support_score"],
                    "links": [{"label": "HKLII judgment", "url": document.public_url}],
                    "retrieval_origin": "hklii_live",
                    "legal_domain": legal_domain,
                }
            )

    citations = sorted(
        citation_pool,
        key=lambda item: (item["support_score"], len(item["quote"]), item["case_name"]),
        reverse=True,
    )[:max_citations]

    sources: list[dict] = []
    seen_cases: set[str] = set()
    for citation in citations:
        case_key = citation["case_id"]
        if case_key in seen_cases:
            continue
        seen_cases.add(case_key)
        sources.append(
            {
                "case_id": citation["case_id"],
                "case_name": citation["case_name"],
                "neutral_citation": citation["neutral_citation"],
                "paragraph_span": citation["paragraph_span"],
                "text": citation["quote"],
                "links": citation.get("links", []),
                "citation_ids": [],
                "retrieval_origin": "hklii_live",
                "legal_domain": legal_domain,
            }
        )

    return {
        "citations": citations,
        "sources": sources,
        "warnings": list(crawler.warnings),
        "search_trace": search_trace,
    }


def _stable_statute_key(label: str) -> str:
    cap_match = re.search(r"Cap(?:\.|\s)(\d+[A-Z]?)", label, flags=re.IGNORECASE)
    section_match = re.search(r"\bs(?:ection)?s?\.?\s*([0-9A-Z(),.\-\s]+)", label, flags=re.IGNORECASE)
    cap = cap_match.group(1).upper() if cap_match else "UNK"
    section = section_match.group(1).strip().upper() if section_match else "GEN"
    section = re.sub(r"\s+", "", section)
    return f"{cap}:{section}"


def _short_case_name(label: str) -> str:
    compact = re.sub(r"\s+", " ", label).strip()
    if len(compact) <= 60:
        return compact
    if " v " in compact:
        left, right = compact.split(" v ", 1)
        return f"{left[:24].strip()} v {right[:24].strip()}".strip()
    return compact[:57].rstrip() + "..."


def _court_score(court_level: str, lineage_count: int, typed_links: int, degree: int) -> float:
    base = COURT_LEVEL_SCORES.get(court_level.upper(), 0.25) if court_level else 0.25
    score = base + (0.08 * min(lineage_count, 4)) + (0.03 * min(typed_links, 8)) + (0.01 * min(degree, 15))
    return round(min(score, 1.6), 4)


def _first_hklii_url(links: list[dict] | None) -> str:
    for link in links or []:
        url = str(link.get("url", "")).strip()
        if "hklii" in url.lower() and "/search" not in url.lower() and "search?" not in url.lower():
            return url
    return ""


def _hklii_deep_link(links: list[dict] | None, paragraph_span: str = "", para_start: int | None = None) -> str:
    hklii_url = _first_hklii_url(links)
    if not hklii_url:
        return ""
    para_number = para_start
    if not para_number:
        match = re.search(r"\[(\d+)\]", paragraph_span or "")
        if match:
            para_number = int(match.group(1))
    return f"{hklii_url}#p{para_number}" if para_number else hklii_url


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    mag_left = math.sqrt(sum(a * a for a in left))
    mag_right = math.sqrt(sum(b * b for b in right))
    if mag_left <= 0 or mag_right <= 0:
        return 0.0
    return max(0.0, dot / (mag_left * mag_right))


def _extract_openrouter_message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text") or part.get("content")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _openrouter_grounded_answer(question: str, citations: list[dict], model: str = "") -> tuple[str, str]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    if not citations:
        raise RuntimeError("No citations available for grounded synthesis")

    selected_model = model.strip() or os.environ.get("OPENROUTER_MODEL", "").strip() or OPENROUTER_DEFAULT_MODEL
    evidence_lines = []
    for citation in citations:
        evidence_lines.append(
            (
                f"[{citation['citation_id']}] "
                f"Case: {citation.get('case_name', '')} {citation.get('neutral_citation', '')}\n"
                f"Paragraph: {citation.get('paragraph_span', '') or 'n/a'}\n"
                f"Quote: {citation.get('quote', '')}"
            ).strip()
        )

    payload = {
        "model": selected_model,
        "temperature": 0,
        "top_p": 1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a legal GraphRAG synthesis assistant. Answer using only the provided evidence. "
                    "Do not invent cases, statutes, facts, or paragraphs. Every factual sentence must end with one or more "
                    "citation tags like [C1]. If evidence is insufficient, explicitly say so."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question.strip()}\n\n"
                    "Evidence:\n"
                    + "\n\n".join(evidence_lines)
                    + "\n\nReturn a concise legal analysis grounded only in the evidence above."
                ),
            },
        ],
    }

    request = urllib_request.Request(
        OPENROUTER_API_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(request, timeout=OPENROUTER_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {body[:240]}".strip()) from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

    parsed = json.loads(raw)
    choices = parsed.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter returned no choices")
    message = choices[0].get("message", {})
    answer = _extract_openrouter_message_text(message.get("content", ""))
    if not answer:
        raise RuntimeError("OpenRouter returned an empty message")

    valid_ids = {citation["citation_id"] for citation in citations}
    cited_ids = set(OPENROUTER_CITATION_TAG_RE.findall(answer))
    if not cited_ids:
        raise RuntimeError("OpenRouter response did not include citation tags")
    if not cited_ids.issubset(valid_ids):
        unknown = sorted(cited_ids - valid_ids)
        raise RuntimeError(f"OpenRouter response referenced unknown citations: {', '.join(unknown)}")
    return answer.strip(), selected_model


def _code_to_edge_type(code: str, fallback_treatment: str = "") -> str:
    normalized = (code or "").upper()
    if normalized == "FLLW":
        return "FOLLOWS"
    if normalized == "APPD":
        return "APPLIES"
    if normalized == "DIST":
        return "DISTINGUISHES"
    if normalized == "DPRT":
        return "OVERRULES"
    treatment = fallback_treatment.lower()
    if "follow" in treatment or "adopt" in treatment:
        return "FOLLOWS"
    if "distinguish" in treatment or "qualif" in treatment:
        return "DISTINGUISHES"
    if "overrule" in treatment or "depart" in treatment:
        return "OVERRULES"
    if "doubt" in treatment:
        return "DOUBTS"
    return "APPLIES"


def _clone_public(value):
    if isinstance(value, dict):
        return {key: _clone_public(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_public(item) for item in value]
    return value


def _strip_private_fields(node: dict) -> dict:
    public_node = _clone_public(node)
    for key in ("embedding", "summary_embedding", "text_private"):
        public_node.pop(key, None)
    if public_node.get("type") == "Paragraph":
        public_node["public_excerpt"] = public_node.get("public_excerpt", "")
    return public_node


def _strip_private_case_card(card: dict) -> dict:
    public_card = _clone_public(card)
    for principle in public_card.get("principles", []):
        principle.pop("text_private", None)
        principle.pop("embedding", None)
    return public_card


def _match_existing_topic_ids(hint: str, topic_nodes: dict[str, dict], subground_lookup: dict[str, dict]) -> list[str]:
    normalized_hint = _normalize_label(hint)
    if not normalized_hint:
        return []

    direct_matches = [
        topic_id
        for topic_id, topic in topic_nodes.items()
        if normalized_hint == _normalize_label(topic.get("label_en", topic.get("label", "")))
        or normalized_hint == _normalize_label(topic.get("label", ""))
    ]
    if direct_matches:
        return direct_matches

    contains_matches = [
        topic_id
        for topic_id, topic in topic_nodes.items()
        if normalized_hint in _normalize_label(topic.get("label_en", topic.get("label", "")))
        or _normalize_label(topic.get("label_en", topic.get("label", ""))) in normalized_hint
    ]
    if contains_matches:
        return contains_matches[:2]

    subground_matches = [
        subground_id
        for subground_id, subground in subground_lookup.items()
        if normalized_hint == _normalize_label(subground.get("label_en", subground.get("label", "")))
        or normalized_hint in _normalize_label(subground.get("label_en", subground.get("label", "")))
    ]
    topic_ids: list[str] = []
    for subground_id in subground_matches:
        topic_ids.extend(subground_lookup[subground_id].get("topic_ids", []))
    return topic_ids[:2]


def _make_topic_path(module_label: str, subground_label: str, topic_label: str) -> str:
    return f"{module_label}/{subground_label}/{topic_label}"


def _summary_embedding_text(node: dict) -> str:
    node_type = node.get("type", "")
    if node_type == "Case":
        return " ".join(
            part
            for part in (
                node.get("case_name", node.get("label", "")),
                node.get("summary_en", node.get("summary", "")),
                " ".join(node.get("topic_paths", [])),
            )
            if part
        ).strip()
    if node_type == "Topic":
        return " ".join(
            part
            for part in (
                node.get("label_en", node.get("label", "")),
                node.get("summary", ""),
            )
            if part
        ).strip()
    if node_type == "Proposition":
        return " ".join(
            part
            for part in (
                node.get("label_en", node.get("label", "")),
                node.get("statement_en", node.get("public_excerpt", "")),
            )
            if part
        ).strip()
    return ""


def _populate_summary_embeddings(
    nodes: list[dict],
    *,
    backend=None,
    allow_openai: bool = True,
) -> None:
    embedder = backend
    if embedder is None:
        embedder = create_embedding_backend()
    if getattr(embedder, "name", "") == "openai" and not allow_openai:
        return

    pending_nodes: list[dict] = []
    pending_texts: list[str] = []
    for node in nodes:
        if node.get("type") not in {"Case", "Topic", "Proposition"}:
            continue
        if node.get("summary_embedding"):
            continue
        text = _summary_embedding_text(node)
        if not text:
            continue
        pending_nodes.append(node)
        pending_texts.append(text)

    if not pending_texts:
        return

    embeddings = embedder.embed_documents(pending_texts)
    for node, embedding in zip(pending_nodes, embeddings, strict=True):
        node["summary_embedding"] = embedding


# ---------------------------------------------------------------------------
# Auto-enrichment: extract principles from HKLII case documents via LLM
# ---------------------------------------------------------------------------

_RATIO_KEYWORDS_RE = re.compile(
    r"\b(held|principle|ratio|conclude|find|determined|ruling|essential element|test is|"
    r"court held|we hold|it is settled|the law is|the correct approach)\b",
    re.IGNORECASE,
)

_AUTO_ENRICH_PROMPT = """You are a Hong Kong criminal law analyst. Given paragraphs from a judgment, extract the key legal principles (ratio decidendi).

Return a JSON object with two arrays: "principles" and "relationships".

For EACH principle in "principles", output JSON with:
- "principle_label": short title (e.g. "Mens rea for murder")
- "paraphrase_en": restate the principle IN YOUR OWN WORDS (do NOT copy verbatim from the judgment)
- "paragraph_span": the paragraph range where this principle appears (e.g. "[47]-[52]")
- "cited_statutes": list of relevant ordinance references (e.g. ["Cap. 210 s.9"])

For EACH case-law relationship in "relationships", output JSON with:
- "target_case_name": the other authority mentioned in the judgment
- "target_neutral_citation": neutral citation if stated, otherwise ""
- "relationship_type": one of FOLLOWS, APPLIES, DISTINGUISHES, OVERRULES, DOUBTS, or CITES
- "description": 1 sentence paraphrase of how the present judgment treats that authority

Maximum 5 principles per case and maximum 6 relationships per case.
If no clear ratio decidendi or case-law relationships can be identified, return {{"principles": [], "relationships": []}}.
Do not invent citations or authorities not reasonably supported by the supplied paragraphs.

Case: {case_name}
Citation: {neutral_citation}

Paragraphs:
{paragraphs}

Output JSON object only, no other text:"""


def _extract_json_payload(raw_text: str):
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw_text or ""):
        if char not in "[{":
            continue
        try:
            payload, _end = decoder.raw_decode(raw_text[index:])
            return payload
        except json.JSONDecodeError:
            continue
    return None


def _normalize_case_relationship_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized in CASE_EDGE_TYPES:
        return normalized
    lowered = (value or "").strip().lower()
    if "follow" in lowered or "adopt" in lowered:
        return "FOLLOWS"
    if "apply" in lowered or "applied" in lowered:
        return "APPLIES"
    if "distinguish" in lowered or "qualified" in lowered:
        return "DISTINGUISHES"
    if "overrule" in lowered or "depart" in lowered:
        return "OVERRULES"
    if "doubt" in lowered:
        return "DOUBTS"
    return "CITES"


def _auto_enrich_case_via_llm(case_name: str, neutral_citation: str, paragraphs: list[dict]) -> dict[str, list[dict]]:
    """Call DeepSeek/OpenRouter to extract principles from case paragraphs."""
    empty_payload = {"principles": [], "relationships": []}
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not deepseek_key and not openrouter_key:
        return empty_payload

    # Select candidate paragraphs that likely contain ratio
    candidates = []
    for para in paragraphs:
        text = para.get("text", "")
        if len(text) < 60:
            continue
        if _RATIO_KEYWORDS_RE.search(text):
            candidates.append(para)
    if not candidates:
        # Fallback: use first 8 substantial paragraphs
        candidates = [p for p in paragraphs if len(p.get("text", "")) > 80][:8]
    if not candidates:
        return empty_payload

    # Truncate to avoid token limits
    para_text = "\n\n".join(
        f"[{p.get('paragraph_span', '?')}] {p['text'][:600]}"
        for p in candidates[:15]
    )

    prompt = _AUTO_ENRICH_PROMPT.format(
        case_name=case_name,
        neutral_citation=neutral_citation,
        paragraphs=para_text[:8000],
    )

    if deepseek_key:
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        api_key = deepseek_key
        model = "deepseek-chat"
    else:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        api_key = openrouter_key
        model = os.environ.get("OPENROUTER_MODEL", "").strip() or "deepseek/deepseek-chat"

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    request_obj = urllib_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    def _call(ctx=None):
        kw = {"timeout": 60}
        if ctx is not None:
            kw["context"] = ctx
        with urllib_request.urlopen(request_obj, **kw) as response:
            return response.read().decode("utf-8")

    try:
        try:
            raw = _call()
        except ssl.SSLError:
            raw = _call(ssl._create_unverified_context())
        except urllib_error.URLError as exc:
            if "certificate" in str(exc).lower() or "ssl" in str(exc).lower():
                raw = _call(ssl._create_unverified_context())
            else:
                raise
        parsed = json.loads(raw)
        content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
        payload_obj = _extract_json_payload(content)
        if isinstance(payload_obj, list):
            return {
                "principles": [item for item in payload_obj if isinstance(item, dict)],
                "relationships": [],
            }
        if isinstance(payload_obj, dict):
            return {
                "principles": [item for item in payload_obj.get("principles", []) if isinstance(item, dict)],
                "relationships": [item for item in payload_obj.get("relationships", []) if isinstance(item, dict)],
            }
    except Exception:
        pass
    return empty_payload


# ── Enrichment Cache ──────────────────────────────────────────────────────────

def save_enrichment_cache(
    bundle_nodes: list[dict],
    bundle_edges: list[dict],
    path: str | Path,
) -> int:
    """Persist per-case paragraph/proposition nodes and associated edges.

    Returns the number of cases stored.  The cache is keyed by case node id so
    future builds can inject previously enriched data without re-calling DeepSeek.
    """
    # Build paragraph-id → case-id mapping (paragraphs store case_id directly)
    para_ids: set[str] = set()
    para_to_case: dict[str, str] = {}
    for node in bundle_nodes:
        if node["type"] == "Paragraph":
            para_ids.add(node["id"])
            if node.get("case_id"):
                para_to_case[node["id"]] = node["case_id"]

    # Supplement para→case via PART_OF edges in case the field was missing
    for edge in bundle_edges:
        if edge["type"] == "PART_OF" and edge["source"] in para_ids:
            para_to_case.setdefault(edge["source"], edge["target"])

    # Map proposition-id → case-id via SUPPORTS edges (paragraph → proposition)
    prop_ids: set[str] = set()
    prop_to_case: dict[str, str] = {}
    for edge in bundle_edges:
        if edge["type"] == "SUPPORTS" and edge["source"] in para_ids:
            prop_to_case[edge["target"]] = para_to_case.get(edge["source"], "")
    for node in bundle_nodes:
        if node["type"] == "Proposition" and node["id"] in prop_to_case:
            prop_ids.add(node["id"])

    cache: dict[str, dict] = {}

    for node in bundle_nodes:
        if node["type"] == "Paragraph" and node["id"] in para_to_case:
            case_id = para_to_case[node["id"]]
            # Omit heavy embedding vector — not needed for cache
            entry = {k: v for k, v in node.items() if k != "embedding"}
            cache.setdefault(case_id, {"paragraphs": [], "propositions": [], "edges": []})["paragraphs"].append(entry)
        elif node["type"] == "Proposition" and node["id"] in prop_to_case:
            case_id = prop_to_case[node["id"]]
            if case_id:
                cache.setdefault(case_id, {"paragraphs": [], "propositions": [], "edges": []})["propositions"].append(node)

    for edge in bundle_edges:
        src_enrichment = edge["source"] in para_ids or edge["source"] in prop_ids
        tgt_enrichment = edge["target"] in para_ids or edge["target"] in prop_ids
        if src_enrichment or tgt_enrichment:
            case_id = (
                para_to_case.get(edge["source"])
                or para_to_case.get(edge["target"])
                or prop_to_case.get(edge["source"])
                or prop_to_case.get(edge["target"])
                or ""
            )
            if case_id:
                cache.setdefault(case_id, {"paragraphs": [], "propositions": [], "edges": []})["edges"].append(edge)
        elif edge.get("reason") == "auto-enrichment lineage":
            # Case-to-case relationship edges discovered during enrichment
            case_id = edge["source"]
            cache.setdefault(case_id, {"paragraphs": [], "propositions": [], "edges": []})["edges"].append(edge)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cache, separators=(",", ":")))
    return len(cache)


def load_enrichment_cache(path: str | Path) -> dict[str, dict]:
    """Load enrichment cache from *path*; returns ``{}`` when the file does not exist."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _inject_enrichment_cache(
    bundle_nodes: list[dict],
    bundle_edges: list[dict],
    add_node,
    add_edge,
    pre_enriched: dict[str, dict],
) -> int:
    """Inject cached paragraph/proposition nodes/edges for previously enriched cases.

    Marks each matched case as ``auto_enriched`` so that
    ``_auto_enrich_cases_in_bundle`` will skip it.

    Returns the number of cases injected.
    """
    case_lookup: dict[str, dict] = {n["id"]: n for n in bundle_nodes if n["type"] == "Case"}
    injected = 0
    for case_id, cached in pre_enriched.items():
        case_node = case_lookup.get(case_id)
        if case_node is None:
            continue
        for para_node in cached.get("paragraphs", []):
            add_node({**para_node, "embedding": []})
        for prop_node in cached.get("propositions", []):
            add_node(prop_node)
        for edge in cached.get("edges", []):
            add_edge(
                edge["source"],
                edge["target"],
                edge["type"],
                **{k: v for k, v in edge.items() if k not in {"source", "target", "type"}},
            )
        case_node["enrichment_status"] = "auto_enriched"
        injected += 1
    return injected


def _auto_enrich_cases_in_bundle(
    bundle_nodes: list[dict],
    bundle_edges: list[dict],
    add_node,
    add_edge,
    ensure_case,
    ensure_statute,
    legal_domain: str,
    domain_tags: list[str],
    max_enrich: int = 80,
) -> int:
    """Auto-enrich case nodes that lack principles by fetching from HKLII + LLM extraction."""
    crawler = HKLIICrawler()
    enriched = 0

    unenriched = [
        node for node in bundle_nodes
        if node["type"] == "Case"
        and node.get("enrichment_status") == "case_only"
        and (node.get("source_links") or node.get("neutral_citation"))
    ][:max_enrich]

    for case_node in unenriched:
        # Try to get HKLII URL (must be a direct judgment URL, not a search URL)
        hklii_url = ""
        for link in case_node.get("source_links", []):
            url = link.get("url", "")
            if "hklii" in url.lower() and "/search" not in url and "search?" not in url:
                hklii_url = url
                break

        if not hklii_url and case_node.get("neutral_citation"):
            # Try search by neutral citation
            results = crawler.simple_search(case_node["neutral_citation"], limit=1)
            if results:
                hklii_url = results[0].public_url
                case_node.setdefault("source_links", []).append(
                    {"label": "HKLII judgment", "url": hklii_url}
                )

        if not hklii_url:
            continue

        # Fetch case document
        parsed_url = urllib_parse.urlparse(hklii_url)
        try:
            case_doc = crawler.fetch_case_document(parsed_url.path)
        except Exception:
            continue

        if not case_doc or not case_doc.paragraphs:
            continue
        case_node["hklii_verified"] = True

        # Fill missing metadata
        if not case_node.get("neutral_citation") and case_doc.neutral_citation:
            case_node["neutral_citation"] = case_doc.neutral_citation
        if not case_node.get("court_name") and case_doc.court_name:
            case_node["court_name"] = case_doc.court_name
        if not case_node.get("decision_date") and case_doc.decision_date:
            case_node["decision_date"] = case_doc.decision_date
        if not case_node.get("judges") and case_doc.judges:
            case_node["judges"] = case_doc.judges

        # Extract principles via LLM
        para_dicts = [
            {"text": p.text, "paragraph_span": p.paragraph_span}
            for p in case_doc.paragraphs
            if p.text
        ]
        enrichment = _auto_enrich_case_via_llm(
            case_node.get("case_name", case_node.get("label", "")),
            case_node.get("neutral_citation", ""),
            para_dicts,
        )
        principles = enrichment.get("principles", [])
        relationships = enrichment.get("relationships", [])

        if not principles and not relationships:
            # Even without LLM principles, mark as fetched and update metadata
            case_node["enrichment_status"] = "metadata_enriched"
            enriched += 1
            continue

        citation_base = case_node.get("neutral_citation") or case_node.get("case_name", "")
        short_name = case_node.get("short_name", case_node.get("label", ""))

        for idx, principle in enumerate(principles[:5], start=1):
            para_span_raw = principle.get("paragraph_span", "")
            para_span = ", ".join(para_span_raw) if isinstance(para_span_raw, list) else str(para_span_raw)
            paragraph_id = f"paragraph:{slugify(citation_base + ':' + str(idx))[:80]}"
            proposition_id = f"proposition:{slugify(citation_base + ':' + principle.get('principle_label', str(idx)))[:80]}"

            # Build HKLII deep link to specific paragraph
            hklii_deep = hklii_url
            span_match = re.search(r"\[(\d+)\]", para_span)
            if span_match:
                hklii_deep = f"{hklii_url}#p{span_match.group(1)}"

            paragraph_node = add_node({
                "id": paragraph_id,
                "type": "Paragraph",
                "label": f"{short_name} {para_span}".strip(),
                "case_id": case_node["id"],
                "paragraph_span": para_span,
                "public_excerpt": principle.get("paraphrase_en", ""),
                "text_private": "",  # We don't store original text publicly
                "hklii_deep_link": hklii_deep,
                "embedding": [],
                "principle_ids": [proposition_id],
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            })
            proposition_node = add_node({
                "id": proposition_id,
                "type": "Proposition",
                "label": principle.get("principle_label", f"Principle {idx}"),
                "label_en": principle.get("principle_label", f"Principle {idx}"),
                "statement_en": principle.get("paraphrase_en", ""),
                "doctrine_key": slugify(principle.get("principle_label", "")),
                "confidence": 0.85,
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            })
            add_edge(paragraph_node["id"], case_node["id"], "PART_OF")
            add_edge(paragraph_node["id"], proposition_node["id"], "SUPPORTS")

            # Link cited statutes
            for statute_ref in principle.get("cited_statutes", []):
                for existing in bundle_nodes:
                    if existing["type"] == "Statute" and statute_ref.lower() in existing.get("label", "").lower():
                        add_edge(proposition_node["id"], existing["id"], "CITES", reason="auto-enrichment")
                        break

        for relationship in relationships[:6]:
            target_case_name = str(
                relationship.get("target_case_name")
                or relationship.get("target_label")
                or relationship.get("case_name")
                or ""
            ).strip()
            if not target_case_name:
                continue
            target_neutral_citation = str(
                relationship.get("target_neutral_citation")
                or relationship.get("neutral_citation")
                or ""
            ).strip()
            hklii_target_url = str(
                relationship.get("hklii_url")
                or relationship.get("target_hklii_url")
                or ""
            ).strip()
            explanation = str(
                relationship.get("description")
                or relationship.get("application")
                or relationship.get("note")
                or ""
            ).strip()
            edge_type = _normalize_case_relationship_type(
                relationship.get("relationship_type")
                or relationship.get("type")
                or relationship.get("treatment")
                or ""
            )
            target_node = ensure_case(
                target_case_name,
                target_neutral_citation,
                source_links=(
                    [{"label": "HKLII judgment", "url": hklii_target_url}]
                    if hklii_target_url
                    else None
                ),
            )
            if target_node["id"] == case_node["id"]:
                continue
            add_edge(case_node["id"], target_node["id"], edge_type, explanation=explanation, reason="auto-enrichment lineage")
            if edge_type != "CITES":
                add_edge(case_node["id"], target_node["id"], "CITES", explanation=explanation, reason="auto-enrichment lineage")

        case_node["enrichment_status"] = "auto_enriched"
        enriched += 1

    return enriched


def build_hierarchical_graph_bundle(
    relationship_payload: dict,
    title: str | None = None,
    *,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
    max_enrich: int = 80,
    enrichment_cache_path: str | Path | None = None,
) -> dict:
    public_projection = (
        relationship_payload
        if relationship_payload.get("meta", {}).get("authority_tree")
        else export_public_relationship_payload(relationship_payload, title=title)
    )
    effective_title = title or public_projection.get("meta", {}).get("title") or relationship_payload.get("meta", {}).get("title")
    legal_domain = _infer_legal_domain(public_projection.get("meta") or relationship_payload.get("meta"))
    domain_tags = _domain_tags(public_projection.get("meta") or relationship_payload.get("meta"), legal_domain)

    bundle_nodes: list[dict] = []
    bundle_edges: list[dict] = []
    node_ids: set[str] = set()
    edge_keys: set[tuple[str, str, str]] = set()
    original_node_lookup = {node["id"]: node for node in relationship_payload.get("nodes", [])}
    public_node_lookup = {node["id"]: node for node in public_projection.get("nodes", [])}
    tree = public_projection["meta"]["authority_tree"]
    topic_context: dict[str, dict] = {}
    topic_nodes: dict[str, dict] = {}
    subground_lookup: dict[str, dict] = {}
    module_lookup: dict[str, dict] = {}

    def add_node(node: dict) -> dict:
        if node["id"] in node_ids:
            existing = next(item for item in bundle_nodes if item["id"] == node["id"])
            existing.update({key: value for key, value in node.items() if value not in (None, [], "", {})})
            return existing
        node_ids.add(node["id"])
        bundle_nodes.append(node)
        return node

    def add_edge(source: str, target: str, edge_type: str, **properties: object) -> None:
        key = (source, target, edge_type)
        if key in edge_keys or source not in node_ids or target not in node_ids:
            return
        edge = {
            "source": source,
            "target": target,
            "type": edge_type,
            "weight": float(properties.pop("weight", 1.0)),
        }
        edge.update(properties)
        bundle_edges.append(edge)
        edge_keys.add(key)

    def ensure_source_document(label: str, kind: str, path: str = "") -> dict:
        source_id = f"source_document:{slugify(label)[:80]}"
        return add_node(
            {
                "id": source_id,
                "type": "SourceDocument",
                "label": label,
                "label_en": label,
                "kind": kind,
                "path": path,
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            }
        )

    def ensure_case(case_name: str, neutral_citation: str = "", **updates: object) -> dict:
        normalized = _normalize_label(case_name)
        for node in bundle_nodes:
            if node["type"] != "Case":
                continue
            if neutral_citation and node.get("neutral_citation") == neutral_citation:
                node.update({key: value for key, value in updates.items() if value not in (None, "")})
                return node
            if normalized and _normalize_label(node.get("case_name", node.get("label", ""))) == normalized:
                if neutral_citation and not node.get("neutral_citation"):
                    node["neutral_citation"] = neutral_citation
                node.update({key: value for key, value in updates.items() if value not in (None, "")})
                return node
        case_id = f"case:{slugify(neutral_citation or case_name)[:80]}"
        case_node = {
            "id": case_id,
            "type": "Case",
            "label": case_name,
            "case_name": case_name,
            "short_name": _short_case_name(case_name),
            "neutral_citation": neutral_citation,
            "parallel_citations": [],
            "court_code": "",
            "court_name": "",
            "court_level": "",
            "decision_date": "",
            "judges": [],
            "source_links": [],
            "summary_en": "",
            "summary_zh": "",
            "authority_score": 0.0,
            "topic_paths": [],
            "lineage_ids": [],
            "enrichment_status": "case_only",
            "primary_topic": "",
            "offence_family": "",
            "secondary_topics": [],
            "summary_embedding": [],
            "references": [],
            "legal_domain": legal_domain,
            "domain_tags": list(domain_tags),
        }
        case_node.update({key: value for key, value in updates.items() if value is not None})
        return add_node(case_node)

    def ensure_statute(label: str) -> dict:
        normalized = _normalize_label(label)
        for node in bundle_nodes:
            if node["type"] == "Statute" and _normalize_label(node.get("label", "")) == normalized:
                return node
        return add_node(
            {
                "id": f"statute:{slugify(label)[:80]}",
                "type": "Statute",
                "label": label,
                "title": label,
                "cap_section_key": _stable_statute_key(label),
                "source_links": [],
                "summary_en": "",
                "summary_zh": "",
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            }
        )

    def ensure_synthetic_subground(module_id: str, label: str) -> dict:
        synthetic_id = f"subground:{slugify(module_id)}:synthetic:{slugify(label)[:40]}"
        if synthetic_id in subground_lookup:
            return subground_lookup[synthetic_id]
        module = module_lookup[module_id]
        node = add_node(
            {
                "id": synthetic_id,
                "type": "Subground",
                "label": label,
                "label_en": label,
                "label_zh": "",
                "module_id": module_id,
                "summary": f"Synthetic subground created to absorb additional graph concepts under {module['label_en']}.",
                "topic_ids": [],
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            }
        )
        subground_lookup[synthetic_id] = node
        add_edge(module_id, synthetic_id, "CONTAINS")
        return node

    def ensure_synthetic_topic(hint: str) -> str:
        topic_id = f"topic:synthetic:{slugify(hint)[:56]}"
        if topic_id in topic_nodes:
            return topic_id
        chosen_subground_id = ""
        normalized_hint = _normalize_label(hint)
        for subground_id, subground in subground_lookup.items():
            label = _normalize_label(subground.get("label_en", subground.get("label", "")))
            if normalized_hint and (normalized_hint in label or label in normalized_hint):
                chosen_subground_id = subground_id
                break
        if not chosen_subground_id:
            fallback_module_id = "module:cross_cutting" if "module:cross_cutting" in module_lookup else next(iter(module_lookup))
            chosen_subground_id = ensure_synthetic_subground(fallback_module_id, "Derived Topics")["id"]
        subground = subground_lookup[chosen_subground_id]
        module = module_lookup[subground["module_id"]]
        topic_node = add_node(
            {
                "id": topic_id,
                "type": "Topic",
                "label": hint,
                "label_en": hint,
                "label_zh": "",
                "summary": f"Synthetic topic created from case enrichment data for {hint}.",
                "path": _make_topic_path(module["label_en"], subground.get("label_en", subground["label"]), hint),
                "module_id": module["id"],
                "subground_id": chosen_subground_id,
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            }
        )
        topic_nodes[topic_id] = topic_node
        subground.setdefault("topic_ids", []).append(topic_id)
        add_edge(chosen_subground_id, topic_id, "CONTAINS")
        topic_context[topic_id] = {
            "module_id": module["id"],
            "module_label": module["label_en"],
            "subground_id": chosen_subground_id,
            "subground_label": subground.get("label_en", subground["label"]),
            "path": topic_node["path"],
        }
        return topic_id

    def resolve_topic_ids(hints: list[str]) -> list[str]:
        resolved: list[str] = []
        for hint in hints:
            matched = _match_existing_topic_ids(hint, topic_nodes, subground_lookup)
            if matched:
                for topic_id in matched:
                    if topic_id not in resolved:
                        resolved.append(topic_id)
                continue
            synthetic_id = ensure_synthetic_topic(hint)
            if synthetic_id not in resolved:
                resolved.append(synthetic_id)
        return resolved

    for module in tree["modules"]:
        module_id = module["id"]
        module_node = add_node(
            {
                "id": module_id,
                "type": "Module",
                "label": module["label_en"],
                "label_en": module["label_en"],
                "label_zh": module.get("label_zh", ""),
                "summary": module.get("summary_en", module.get("summary", "")),
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            }
        )
        module_lookup[module_id] = module_node
        for subground in module.get("subgrounds", []):
            subground_node = add_node(
                {
                    "id": subground["id"],
                    "type": "Subground",
                    "label": subground["label_en"],
                    "label_en": subground["label_en"],
                    "label_zh": subground.get("label_zh", ""),
                    "summary": subground.get("summary_en", subground.get("summary", "")),
                    "module_id": module_id,
                    "children": subground.get("children", []),
                    "topic_ids": list(subground.get("topic_ids", [])),
                    "legal_domain": legal_domain,
                    "domain_tags": list(domain_tags),
                }
            )
            subground_lookup[subground["id"]] = subground_node
            add_edge(module_id, subground["id"], "CONTAINS")

    for topic_id, public_topic in public_node_lookup.items():
        if public_topic["type"] != "topic":
            continue
        context = None
        for module in tree["modules"]:
            for subground in module.get("subgrounds", []):
                if topic_id in subground.get("topic_ids", []):
                    context = {
                        "module_id": module["id"],
                        "module_label": module["label_en"],
                        "subground_id": subground["id"],
                        "subground_label": subground["label_en"],
                    }
                    break
            if context:
                break
        if not context:
            synthetic_subground = ensure_synthetic_subground("module:cross_cutting", "Derived Topics")
            context = {
                "module_id": "module:cross_cutting",
                "module_label": module_lookup["module:cross_cutting"]["label_en"],
                "subground_id": synthetic_subground["id"],
                "subground_label": synthetic_subground["label_en"],
            }
        path = _make_topic_path(context["module_label"], context["subground_label"], public_topic["label"])
        topic_node = add_node(
            {
                "id": topic_id,
                "type": "Topic",
                "label": public_topic["label"],
                "label_en": public_topic["label"],
                "label_zh": "",
                "summary": public_topic.get("summary", ""),
                "path": path,
                "module_id": context["module_id"],
                "subground_id": context["subground_id"],
                "legal_domain": legal_domain,
                "domain_tags": list(domain_tags),
            }
        )
        topic_nodes[topic_id] = topic_node
        topic_context[topic_id] = {**context, "path": path}
        add_edge(context["subground_id"], topic_id, "CONTAINS")

    for subground_id, subground in subground_lookup.items():
        topic_ids = [topic_id for topic_id in subground.get("topic_ids", []) if topic_id in topic_nodes]
        for index, left_topic in enumerate(topic_ids):
            for right_topic in topic_ids[index + 1 :]:
                add_edge(left_topic, right_topic, "RELATED_TOPIC", reason="same subground", weight=0.35)

    source_documents_by_id: dict[str, dict] = {}
    for source in relationship_payload.get("meta", {}).get("source_documents", []):
        source_node = ensure_source_document(source["label"], source.get("kind", "unknown"), source.get("path", ""))
        source_documents_by_id[source_node["id"]] = source_node
    for node in relationship_payload.get("nodes", []):
        if node.get("type") != "source":
            continue
        source_node = ensure_source_document(node["label"], node.get("metrics", {}).get("kind", "unknown"))
        source_documents_by_id[source_node["id"]] = source_node

    source_aliases = {
        source.get("label", ""): ensure_source_document(source.get("label", ""), source.get("kind", "unknown")).get("id")
        for source in relationship_payload.get("meta", {}).get("source_documents", [])
        if source.get("label")
    }

    for node in public_projection.get("nodes", []):
        if node["type"] == "case":
            original = original_node_lookup.get(node["id"], node)
            case_node = ensure_case(
                node["label"],
                neutral_citation=original.get("neutral_citation", node.get("neutral_citation", "")),
                summary_en=original.get("summary", node.get("summary", "")),
                source_links=original.get("source_links", original.get("links", node.get("links", []))),
                references=original.get("references", node.get("references", [])),
                court_name=original.get("court_name", node.get("court_name", "")),
                court_code=original.get("court_code", node.get("court_code", "")),
                decision_date=original.get("decision_date", node.get("decision_date", "")),
                judges=original.get("judges", node.get("judges", [])),
                summary_embedding=original.get("summary_embedding", original.get("embedding", [])),
            )
            for reference in original.get("references", node.get("references", [])):
                source_label = reference.get("source_label", "")
                source_id = source_aliases.get(source_label)
                if source_id:
                    add_edge(source_id, case_node["id"], "MENTIONS", location=reference.get("location", ""))
        elif node["type"] == "statute":
            statute_node = ensure_statute(node["label"])
            statute_node["summary_en"] = original_node_lookup.get(node["id"], node).get("summary", node.get("summary", ""))
            statute_node["source_links"] = original_node_lookup.get(node["id"], node).get("links", node.get("links", []))
            for reference in original_node_lookup.get(node["id"], node).get("references", node.get("references", [])):
                source_label = reference.get("source_label", "")
                source_id = source_aliases.get(source_label)
                if source_id:
                    add_edge(source_id, statute_node["id"], "MENTIONS", location=reference.get("location", ""))

    for edge in public_projection.get("edges", []):
        source_node = public_node_lookup.get(edge["source"])
        target_node = public_node_lookup.get(edge["target"])
        edge_type = edge["type"]
        if source_node and source_node["type"] == "topic" and target_node and target_node["type"] == "case":
            context = topic_context.get(source_node["id"], {})
            case_node = ensure_case(target_node["label"])
            path = context.get("path", source_node["label"])
            if path not in case_node["topic_paths"]:
                case_node["topic_paths"].append(path)
            _is_curated = edge_type == "lineage_case"
            add_edge(
                case_node["id"],
                source_node["id"],
                "BELONGS_TO_TOPIC",
                score=round(float(edge.get("weight", 1.0)), 4),
                primary=_is_curated,
                assignment_source=edge_type,
                curated=_is_curated,
                assignment_confidence=1.0 if _is_curated else 0.6,
                assignment_status="verified" if _is_curated else "candidate",
            )
        elif source_node and source_node["type"] == "topic" and target_node and target_node["type"] == "statute":
            statute_node = ensure_statute(target_node["label"])
            add_edge(statute_node["id"], source_node["id"], "BELONGS_TO_TOPIC", score=round(float(edge.get("weight", 1.0)), 4), assignment_source=edge_type, curated=edge_type == "lineage_statute")
        elif source_node and source_node["type"] == "source":
            mapped_source_id = source_aliases.get(source_node["label"])
            if mapped_source_id and target_node and target_node["type"] == "topic":
                add_edge(mapped_source_id, target_node["id"], "MENTIONS", mention_source=edge_type)

    for lineage in public_projection["meta"].get("lineages", []):
        lineage_id = f"lineage:{lineage['id']}"
        add_node(
            {
                "id": lineage_id,
                "type": "AuthorityLineage",
                "label": lineage["title"],
                "title": lineage["title"],
                "codes": lineage.get("codes", []),
                "topic_ids": list(lineage.get("topic_ids", [])),
                "topic_labels": list(lineage.get("topic_labels", [])),
                "topic_hints": list(lineage.get("topic_hints", [])),
                "source": lineage.get("source", "curated"),
                "confidence_status": lineage.get("confidence_status", "established" if lineage.get("source", "curated") == "curated" else "preliminary"),
                "confidence_score": float(lineage.get("confidence_score", 1.0 if lineage.get("source", "curated") == "curated" else 0.65)),
                "created_at": lineage.get("created_at", ""),
                "last_updated": lineage.get("last_updated", ""),
                "discovery_rounds": lineage.get("discovery_rounds", []),
                "legal_domain": legal_domain,
                "domain_tags": list(lineage.get("domain_tags") or domain_tags),
            }
        )
        for topic_id in lineage.get("topic_ids", []):
            if topic_id in topic_nodes:
                add_edge(lineage_id, topic_id, "ABOUT_TOPIC")
        previous_member_id = ""
        previous_member_type = ""
        for member in lineage.get("members", []):
            if member["type"] == "case":
                member_node = ensure_case(member["label"])
            else:
                member_node = ensure_statute(member["label"])
            if lineage["id"] not in member_node.get("lineage_ids", []):
                member_node.setdefault("lineage_ids", []).append(lineage["id"])
            add_edge(
                lineage_id,
                member_node["id"],
                "HAS_MEMBER",
                position=member["position"],
                code=member.get("code", ""),
                treatment=member.get("treatment", ""),
                note=member.get("note", ""),
            )
            if previous_member_id and previous_member_type == member["type"]:
                lineage_edge_type = _code_to_edge_type(member.get("code", ""), member.get("treatment", ""))
                add_edge(previous_member_id, member_node["id"], lineage_edge_type, lineage_id=lineage["id"], curated=True, explanation=member.get("note", ""))
                if member["type"] == "case":
                    add_edge(previous_member_id, member_node["id"], "CITES", lineage_id=lineage["id"], curated=True)
            previous_member_id = member_node["id"]
            previous_member_type = member["type"]

    if legal_domain == "contract":
        curated_enrichments = CURATED_CASE_ENRICHMENTS
    elif legal_domain == "criminal":
        curated_enrichments = CURATED_CRIMINAL_CASE_ENRICHMENTS
    else:
        curated_enrichments = []
    for enrichment in curated_enrichments:
        case_node = ensure_case(
            enrichment["case_name"],
            enrichment["neutral_citation"],
            parallel_citations=enrichment.get("parallel_citations", []),
            short_name=enrichment.get("short_name", _short_case_name(enrichment["case_name"])),
            court_code=enrichment.get("court_code", ""),
            court_name=enrichment.get("court_name", ""),
            court_level=enrichment.get("court_level", ""),
            decision_date=enrichment.get("decision_date", ""),
            judges=enrichment.get("judges", []),
            source_links=enrichment.get("source_links", []),
            summary_en=enrichment.get("summary_en", ""),
            summary_zh=enrichment.get("summary_zh", ""),
            enrichment_status="seeded",
        )
        topic_ids = resolve_topic_ids(enrichment.get("topic_hints", []))
        for topic_id in topic_ids:
            context = topic_context.get(topic_id, {})
            if context.get("path") and context["path"] not in case_node["topic_paths"]:
                case_node["topic_paths"].append(context["path"])
            add_edge(case_node["id"], topic_id, "BELONGS_TO_TOPIC", score=1.0, primary=True, assignment_source="curated_case_enrichment", curated=True, assignment_confidence=1.0, assignment_status="verified")
        for judge in enrichment.get("judges", []):
            judge_id = f"judge:{slugify(judge)[:80]}"
            add_node({"id": judge_id, "type": "Judge", "label": judge, "name": judge})
            add_edge(case_node["id"], judge_id, "DECIDED_BY")
        for index, principle in enumerate(enrichment.get("principles", []), start=1):
            paragraph_id = f"paragraph:{slugify((enrichment['neutral_citation'] or enrichment['case_name']) + ':' + str(index))[:80]}"
            proposition_id = f"proposition:{slugify((enrichment['neutral_citation'] or enrichment['case_name']) + ':' + principle['label_en'])[:80]}"
            paragraph_node = add_node(
                {
                    "id": paragraph_id,
                    "type": "Paragraph",
                    "label": f"{case_node['short_name']} {principle.get('paragraph_span', '').strip()}".strip(),
                    "case_id": case_node["id"],
                    "para_start": principle.get("para_start"),
                    "para_end": principle.get("para_end"),
                    "paragraph_span": principle.get("paragraph_span", ""),
                    "public_excerpt": principle.get("statement_en", ""),
                    "text_private": principle.get("statement_en", ""),
                    "hklii_deep_link": _hklii_deep_link(
                        case_node.get("source_links", []),
                        principle.get("paragraph_span", ""),
                        principle.get("para_start"),
                    ),
                    "embedding": [],
                    "principle_ids": [proposition_id],
                    "legal_domain": legal_domain,
                    "domain_tags": list(domain_tags),
                }
            )
            proposition_node = add_node(
                {
                    "id": proposition_id,
                    "type": "Proposition",
                    "label": principle["label_en"],
                    "label_en": principle["label_en"],
                    "label_zh": principle.get("label_zh", ""),
                    "statement_en": principle.get("statement_en", ""),
                    "statement_zh": principle.get("statement_zh", ""),
                    "doctrine_key": slugify(principle["label_en"]),
                    "confidence": 0.98,
                    "legal_domain": legal_domain,
                    "domain_tags": list(domain_tags),
                }
            )
            add_edge(paragraph_node["id"], case_node["id"], "PART_OF")
            add_edge(paragraph_node["id"], proposition_node["id"], "SUPPORTS")
            cited_authority = principle.get("cited_authority")
            if cited_authority:
                if cited_authority["type"] == "case":
                    authority_node = ensure_case(cited_authority["label"])
                    add_edge(case_node["id"], authority_node["id"], "CITES", reason="principle citation", curated=True)
                else:
                    authority_node = ensure_statute(cited_authority["label"])
                add_edge(proposition_node["id"], authority_node["id"], "CITES", reason="principle citation", curated=True)
        for relationship in enrichment.get("relationships", []):
            if relationship["target_type"] == "case":
                target_node = ensure_case(relationship["target_label"])
                add_edge(case_node["id"], target_node["id"], relationship["type"], explanation=relationship["description"], curated=True)
                add_edge(case_node["id"], target_node["id"], "CITES", explanation=relationship["description"], curated=True)
            else:
                target_node = ensure_statute(relationship["target_label"])
                add_edge(case_node["id"], target_node["id"], relationship["type"], explanation=relationship["description"], curated=True)

    # ── Inject cached enrichments from previous builds ───────────
    if enrichment_cache_path:
        pre_enriched = load_enrichment_cache(enrichment_cache_path)
        if pre_enriched:
            _inject_enrichment_cache(bundle_nodes, bundle_edges, add_node, add_edge, pre_enriched)

    # ── Auto-enrich unenriched cases via HKLII + LLM ──────────────
    if os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        _auto_enrich_cases_in_bundle(
            bundle_nodes, bundle_edges, add_node, add_edge,
            ensure_case, ensure_statute,
            legal_domain=legal_domain,
            domain_tags=list(domain_tags),
            max_enrich=max_enrich,
        )

    # ── Persist enrichment results for next build ─────────────────
    if enrichment_cache_path:
        save_enrichment_cache(bundle_nodes, bundle_edges, enrichment_cache_path)

    try:
        _populate_summary_embeddings(
            bundle_nodes,
            backend=create_embedding_backend(
                backend=embedding_backend,
                model=embedding_model,
                dimensions=embedding_dimensions,
            ),
            allow_openai=True,
        )
    except Exception:
        pass

    outgoing: defaultdict[str, list[dict]] = defaultdict(list)
    incoming: defaultdict[str, list[dict]] = defaultdict(list)
    for edge in bundle_edges:
        outgoing[edge["source"]].append(edge)
        incoming[edge["target"]].append(edge)

    shared_topic_counts: Counter[tuple[str, str]] = Counter()
    case_topic_memberships: defaultdict[str, set[str]] = defaultdict(set)
    for edge in bundle_edges:
        if edge["type"] == "BELONGS_TO_TOPIC":
            case_topic_memberships[edge["source"]].add(edge["target"])
    for topic_ids in case_topic_memberships.values():
        topic_list = sorted(topic_ids)
        for index, left_topic in enumerate(topic_list):
            for right_topic in topic_list[index + 1 :]:
                shared_topic_counts[(left_topic, right_topic)] += 1
    for (left_topic, right_topic), count in shared_topic_counts.items():
        if count >= 2:
            add_edge(left_topic, right_topic, "RELATED_TOPIC", reason="shared authoritative cases", weight=min(1.0, 0.22 * count))

    bundle_node_lookup = {node["id"]: node for node in bundle_nodes}
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    for edge in bundle_edges:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])

    for node in bundle_nodes:
        node["degree"] = len(adjacency.get(node["id"], set()))
        if node["type"] == "Case":
            typed_link_count = sum(1 for edge in outgoing[node["id"]] + incoming[node["id"]] if edge["type"] in TREATMENT_EDGE_TYPES)
            lineage_count = len(node.get("lineage_ids", []))
            node["authority_score"] = _court_score(node.get("court_level", ""), lineage_count, typed_link_count, node["degree"])

    # ── Derive primary_topic and offence_family for each case ──
    # Uses the BELONGS_TO_TOPIC edge with the highest confidence,
    # preferring curated/verified assignments over auto-assigned ones.
    _OFFENCE_FAMILY_MAP: dict[str, str] = {
        "theft": "theft", "robbery": "theft", "burglary": "theft",
        "fraud": "fraud", "deception": "fraud",
        "money laundering": "money_laundering", "proceeds": "money_laundering",
        "murder": "homicide", "manslaughter": "homicide",
        "assault": "violence", "wounding": "violence", "grievous": "violence",
        "rape": "sexual_offences", "sexual": "sexual_offences", "indecent": "sexual_offences",
        "drug": "dangerous_drugs", "trafficking": "dangerous_drugs", "dangerous drugs": "dangerous_drugs",
        "arson": "criminal_damage", "criminal damage": "criminal_damage",
        "animal": "animal_cruelty", "cruelty": "animal_cruelty",
        "riot": "public_order", "unlawful assembly": "public_order",
        "bribery": "bribery", "corruption": "bribery",
        "computer": "computer_crimes", "forgery": "forgery",
        "kidnap": "kidnapping", "false imprisonment": "kidnapping",
        "intoxication": "defences", "insanity": "defences", "duress": "defences",
        "sentencing": "sentencing", "tariff": "sentencing",
    }
    for node in bundle_nodes:
        if node["type"] != "Case":
            continue
        # Find best topic assignment
        best_topic_label = ""
        best_conf = -1.0
        for edge in outgoing.get(node["id"], []):
            if edge["type"] != "BELONGS_TO_TOPIC":
                continue
            conf = edge.get("assignment_confidence", 0.5)
            if edge.get("primary"):
                conf += 0.5
            if conf > best_conf:
                best_conf = conf
                target = bundle_node_lookup.get(edge["target"], {})
                best_topic_label = target.get("label_en", target.get("label", ""))
        if best_topic_label and not node.get("primary_topic"):
            node["primary_topic"] = best_topic_label
        # Derive offence_family from primary topic or topic_paths
        if not node.get("offence_family"):
            combined = (node.get("primary_topic", "") + " " + " ".join(node.get("topic_paths", []))).lower()
            for keyword, family in _OFFENCE_FAMILY_MAP.items():
                if keyword in combined:
                    node["offence_family"] = family
                    break

    case_cards: dict[str, dict] = {}
    for node in bundle_nodes:
        if node["type"] != "Case":
            continue
        principles: list[dict] = []
        relationships: list[dict] = []
        lineage_memberships: list[dict] = []
        for edge in outgoing[node["id"]]:
            target = bundle_node_lookup[edge["target"]]
            if edge["type"] == "PART_OF":
                continue
            if target["type"] == "Paragraph":
                continue
            if edge["type"] in {"BELONGS_TO_TOPIC", "DECIDED_BY"}:
                continue
            if edge["type"] in TREATMENT_EDGE_TYPES or edge["type"] == "CITES":
                relationships.append(
                    {
                        "direction": "outgoing",
                        "type": edge["type"],
                        "target_id": target["id"],
                        "target_label": target.get("label", target.get("case_name", "")),
                        "target_type": target["type"],
                        "explanation": edge.get("explanation") or edge.get("reason") or edge.get("note") or "",
                    }
                )
        for edge in incoming[node["id"]]:
            source = bundle_node_lookup[edge["source"]]
            if edge["type"] == "HAS_MEMBER":
                lineage_memberships.append(
                    {
                        "lineage_id": source["id"].removeprefix("lineage:"),
                        "lineage_node_id": source["id"],
                        "lineage_title": source.get("title", source["label"]),
                        "position": edge.get("position"),
                        "code": edge.get("code", ""),
                        "treatment": edge.get("treatment", ""),
                        "topic_ids": source.get("topic_ids", []),
                        "note": edge.get("note", ""),
                    }
                )
                continue
            if edge["type"] in TREATMENT_EDGE_TYPES or edge["type"] == "CITES":
                relationships.append(
                    {
                        "direction": "incoming",
                        "type": edge["type"],
                        "target_id": source["id"],
                        "target_label": source.get("label", source.get("case_name", "")),
                        "target_type": source["type"],
                        "explanation": edge.get("explanation") or edge.get("reason") or edge.get("note") or "",
                    }
                )
        paragraph_nodes = [bundle_node_lookup[edge["source"]] for edge in incoming[node["id"]] if edge["type"] == "PART_OF"]
        for paragraph in sorted(paragraph_nodes, key=lambda item: (item.get("para_start") or 0, item["id"])):
            support_edges = outgoing[paragraph["id"]]
            proposition = next((bundle_node_lookup[edge["target"]] for edge in support_edges if edge["type"] == "SUPPORTS"), None)
            cited_edges = outgoing[proposition["id"]] if proposition else []
            cited_target = next((bundle_node_lookup[edge["target"]] for edge in cited_edges if edge["type"] == "CITES"), None)
            principles.append(
                {
                    "paragraph_span": paragraph.get("paragraph_span", ""),
                    "para_start": paragraph.get("para_start"),
                    "para_end": paragraph.get("para_end"),
                    "label_en": proposition.get("label_en", proposition.get("label", "")) if proposition else "",
                    "label_zh": proposition.get("label_zh", "") if proposition else "",
                    "statement_en": proposition.get("statement_en", paragraph.get("public_excerpt", "")) if proposition else paragraph.get("public_excerpt", ""),
                    "statement_zh": proposition.get("statement_zh", "") if proposition else "",
                    "public_excerpt": paragraph.get("public_excerpt", ""),
                    "text_private": paragraph.get("text_private", ""),
                    "hklii_deep_link": paragraph.get("hklii_deep_link", ""),
                    "cited_authority": (
                        {
                            "id": cited_target["id"],
                            "label": cited_target.get("label", cited_target.get("title", "")),
                            "type": cited_target["type"],
                        }
                        if cited_target
                        else None
                    ),
                }
            )

        lineage_titles = {membership["lineage_title"] for membership in lineage_memberships}
        same_lineage_cases: list[dict] = []
        for other in bundle_nodes:
            if other["type"] != "Case" or other["id"] == node["id"]:
                continue
            if set(other.get("lineage_ids", [])) & set(node.get("lineage_ids", [])):
                same_lineage_cases.append(
                    {
                        "id": other["id"],
                        "label": other["case_name"],
                        "neutral_citation": other.get("neutral_citation", ""),
                    }
                )
        derived_relationships = {
            "upstream_authorities": [
                relation for relation in relationships if relation["direction"] == "outgoing" and relation["type"] in {"FOLLOWS", "APPLIES", "CITES"}
            ],
            "downstream_applications": [
                relation for relation in relationships if relation["direction"] == "incoming" and relation["type"] in {"FOLLOWS", "APPLIES", "CITES"}
            ],
            "same_lineage_cases": sorted(same_lineage_cases, key=lambda item: item["label"])[:12],
            "statutory_interpretations": [
                relation for relation in relationships if relation["type"] == "INTERPRETS"
            ],
        }
        case_cards[node["id"]] = {
            "id": node["id"],
            "metadata": {
                "id": node["id"],
                "neutral_citation": node.get("neutral_citation", ""),
                "parallel_citations": node.get("parallel_citations", []),
                "case_name": node.get("case_name", node["label"]),
                "short_name": node.get("short_name", _short_case_name(node.get("case_name", node["label"]))),
                "court_code": node.get("court_code", ""),
                "court_name": node.get("court_name", ""),
                "court_level": node.get("court_level", ""),
                "decision_date": node.get("decision_date", ""),
                "judges": node.get("judges", []),
                "source_links": node.get("source_links", []),
                "summary_en": node.get("summary_en", ""),
                "summary_zh": node.get("summary_zh", ""),
                "authority_score": node.get("authority_score", 0.0),
                "topic_paths": sorted(node.get("topic_paths", [])),
                "lineage_ids": sorted(node.get("lineage_ids", [])),
                "lineage_titles": sorted(lineage_titles),
                "enrichment_status": node.get("enrichment_status", "case_only"),
            },
            "principles": principles,
            "relationships": sorted(relationships, key=lambda item: (item["type"], item["direction"], item["target_label"])),
            "lineage_memberships": sorted(lineage_memberships, key=lambda item: (item["lineage_title"], item["position"] or 0)),
            "derived_relationships": derived_relationships,
        }

    tree_modules: list[dict] = []
    for module in tree["modules"]:
        module_id = module["id"]
        module_case_ids: set[str] = set()
        module_lineage_ids: set[str] = set()
        subground_payloads: list[dict] = []
        for subground in [item for item in subground_lookup.values() if item["module_id"] == module_id]:
            topic_ids = [topic_id for topic_id in subground.get("topic_ids", []) if topic_id in topic_nodes]
            case_ids: set[str] = set()
            lineage_ids: set[str] = set()
            for topic_id in topic_ids:
                for edge in incoming[topic_id]:
                    if edge["type"] == "BELONGS_TO_TOPIC" and bundle_node_lookup[edge["source"]]["type"] == "Case":
                        case_ids.add(edge["source"])
                for edge in incoming[topic_id]:
                    if edge["type"] == "ABOUT_TOPIC":
                        lineage_ids.add(edge["source"].removeprefix("lineage:"))
            module_case_ids.update(case_ids)
            module_lineage_ids.update(lineage_ids)
            subground_payloads.append(
                {
                    "id": subground["id"],
                    "label_en": subground.get("label_en", subground["label"]),
                    "label_zh": subground.get("label_zh", ""),
                    "topic_ids": topic_ids,
                    "metrics": {
                        "topics": len(topic_ids),
                        "cases": len(case_ids),
                        "lineages": len(lineage_ids),
                    },
                }
            )
        tree_modules.append(
            {
                "id": module_id,
                "label_en": module_lookup[module_id]["label_en"],
                "label_zh": module_lookup[module_id].get("label_zh", ""),
                "metrics": {
                    "subgrounds": len(subground_payloads),
                    "cases": len(module_case_ids),
                    "lineages": len(module_lineage_ids),
                },
                "subgrounds": sorted(subground_payloads, key=lambda item: item["label_en"]),
            }
        )

    lineage_summaries: list[dict] = []
    for lineage_node in sorted(
        (node for node in bundle_nodes if node["type"] == "AuthorityLineage"),
        key=lambda item: item.get("title", item.get("label", "")),
    ):
        member_edges = [edge for edge in outgoing.get(lineage_node["id"], []) if edge["type"] == "HAS_MEMBER"]
        lineage_summaries.append(
            {
                "id": lineage_node["id"].removeprefix("lineage:"),
                "node_id": lineage_node["id"],
                "title": lineage_node.get("title", lineage_node.get("label", "")),
                "member_count": len(member_edges),
                "topic_ids": list(lineage_node.get("topic_ids", [])),
                "topic_labels": list(lineage_node.get("topic_labels", [])),
                "topic_hints": list(lineage_node.get("topic_hints", lineage_node.get("topic_labels", []))),
                "codes": list(lineage_node.get("codes", [])),
                "source": lineage_node.get("source", "curated"),
                "confidence_status": lineage_node.get("confidence_status", "established"),
                "confidence_score": lineage_node.get("confidence_score", 1.0),
                "domain_tags": list(lineage_node.get("domain_tags", [])),
            }
        )

    bundle = {
        "meta": {
            "title": effective_title,
            "generated_at": datetime.now(UTC).isoformat(),
            "node_count": len(bundle_nodes),
            "edge_count": len(bundle_edges),
            "case_count": sum(1 for node in bundle_nodes if node["type"] == "Case"),
            "statute_count": sum(1 for node in bundle_nodes if node["type"] == "Statute"),
            "topic_count": sum(1 for node in bundle_nodes if node["type"] == "Topic"),
            "lineage_count": sum(1 for node in bundle_nodes if node["type"] == "AuthorityLineage"),
            "lineages": lineage_summaries,
            "paragraph_count": sum(1 for node in bundle_nodes if node["type"] == "Paragraph"),
            "proposition_count": sum(1 for node in bundle_nodes if node["type"] == "Proposition"),
            "enriched_case_count": sum(1 for node in bundle_nodes if node["type"] == "Case" and node.get("enrichment_status") != "case_only"),
            "notes": [
                "Hybrid hierarchical graph bundle generated from the Casemap relationship graph.",
                "Hierarchy is represented explicitly as Module -> Subground -> Topic while authorities remain graph-native.",
                "Neo4j constraints and import templates are included for database-backed deployment.",
            ],
            "neo4j": {
                "vector_dimensions": VECTOR_DIMENSIONS,
                "constraints_file": "neo4j_constraints.cypher",
                "import_file": "neo4j_import.cypher",
            },
            "legal_domain": legal_domain,
            "domain_tags": domain_tags,
            "viewer_heading_public": public_projection.get("meta", {}).get("viewer_heading_public", ""),
            "viewer_heading_internal": public_projection.get("meta", {}).get("viewer_heading_internal", ""),
            "viewer_intro_public": public_projection.get("meta", {}).get("viewer_intro_public", ""),
            "viewer_intro_internal": public_projection.get("meta", {}).get("viewer_intro_internal", ""),
        },
        "tree": {
            "id": tree["id"],
            "label_en": tree["label_en"],
            "label_zh": tree["label_zh"],
            "modules": sorted(tree_modules, key=lambda item: item["label_en"]),
        },
        "nodes": bundle_nodes,
        "edges": bundle_edges,
        "case_cards": case_cards,
    }
    return bundle


def export_public_projection(bundle: dict, title: str | None = None) -> dict:
    public_projection = {
        "meta": {
            **_clone_public(bundle["meta"]),
            "title": title or bundle["meta"]["title"],
            "public_mode": True,
        },
        "tree": _clone_public(bundle["tree"]),
        "nodes": [_strip_private_fields(node) for node in bundle["nodes"] if node["type"] != "SourceDocument"],
        "edges": _clone_public(bundle["edges"]),
        "case_cards": {
            case_id: _strip_private_case_card(card)
            for case_id, card in bundle.get("case_cards", {}).items()
            if bundle["case_cards"][case_id]["metadata"].get("enrichment_status") != "case_only"
        },
    }
    return public_projection


def _edge_merge_key(edge: dict) -> tuple[str, str, str, str]:
    metadata = {key: value for key, value in edge.items() if key not in {"source", "target", "type"}}
    return (
        str(edge.get("source", "")),
        str(edge.get("target", "")),
        str(edge.get("type", "")),
        json.dumps(metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
    )


def _lineage_meta_summaries(nodes: list[dict], edges: list[dict]) -> list[dict]:
    outgoing: defaultdict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.get("source", "")].append(edge)
    summaries: list[dict] = []
    for lineage_node in sorted(
        (node for node in nodes if node.get("type") == "AuthorityLineage"),
        key=lambda item: item.get("title", item.get("label", "")),
    ):
        member_edges = [edge for edge in outgoing.get(lineage_node["id"], []) if edge.get("type") == "HAS_MEMBER"]
        summaries.append(
            {
                "id": lineage_node["id"].removeprefix("lineage:"),
                "node_id": lineage_node["id"],
                "title": lineage_node.get("title", lineage_node.get("label", "")),
                "member_count": len(member_edges),
                "topic_ids": list(lineage_node.get("topic_ids", [])),
                "topic_labels": list(lineage_node.get("topic_labels", [])),
                "topic_hints": list(lineage_node.get("topic_hints", lineage_node.get("topic_labels", []))),
                "codes": list(lineage_node.get("codes", [])),
                "source": lineage_node.get("source", "curated"),
                "confidence_status": lineage_node.get("confidence_status", "established"),
                "confidence_score": lineage_node.get("confidence_score", 1.0),
                "domain_tags": list(lineage_node.get("domain_tags", [])),
            }
        )
    return summaries


def _repair_orphan_topic_paths(bundle: dict) -> dict:
    nodes_by_id = {node["id"]: node for node in bundle.get("nodes", []) if node.get("id")}
    topic_paths = {
        node.get("path")
        for node in nodes_by_id.values()
        if node.get("type") == "Topic" and node.get("path")
    }
    added_paths = 0
    removed_paths = 0
    case_nodes = {
        node["id"]: node
        for node in nodes_by_id.values()
        if node.get("type") == "Case"
    }

    for edge in bundle.get("edges", []):
        if edge.get("type") != "BELONGS_TO_TOPIC":
            continue
        case_node = case_nodes.get(edge.get("source"))
        topic_node = nodes_by_id.get(edge.get("target"))
        if not case_node or not topic_node or topic_node.get("type") != "Topic":
            continue
        topic_path = topic_node.get("path")
        if topic_path and topic_path not in case_node.setdefault("topic_paths", []):
            case_node["topic_paths"].append(topic_path)
            added_paths += 1

    if topic_paths:
        for case_node in case_nodes.values():
            original_paths = list(case_node.get("topic_paths", []))
            repaired_paths: list[str] = []
            for topic_path in original_paths:
                if topic_path in topic_paths and topic_path not in repaired_paths:
                    repaired_paths.append(topic_path)
            removed_paths += len(original_paths) - len(repaired_paths)
            case_node["topic_paths"] = repaired_paths

    for case_id, card in bundle.get("case_cards", {}).items():
        case_node = case_nodes.get(case_id)
        if not case_node:
            continue
        metadata = card.setdefault("metadata", {})
        metadata["topic_paths"] = sorted(case_node.get("topic_paths", []))
        metadata["authority_score"] = case_node.get("authority_score", metadata.get("authority_score", 0.0))
        metadata["lineage_ids"] = sorted(case_node.get("lineage_ids", metadata.get("lineage_ids", [])))
        metadata["enrichment_status"] = case_node.get("enrichment_status", metadata.get("enrichment_status", "case_only"))

    return {"added_topic_paths": added_paths, "removed_orphan_topic_paths": removed_paths}


def _drop_low_value_case_shells(bundle: dict, max_total_nodes: int | None) -> dict:
    if not max_total_nodes or max_total_nodes <= 0:
        return {"max_total_nodes": max_total_nodes, "pruned_case_only_nodes": 0, "cap_applied": False}
    nodes = bundle.get("nodes", [])
    if len(nodes) <= max_total_nodes:
        return {"max_total_nodes": max_total_nodes, "pruned_case_only_nodes": 0, "cap_applied": False}

    nodes_by_id = {node["id"]: node for node in nodes if node.get("id")}
    protected_case_ids: set[str] = set()
    for node in nodes:
        if node.get("type") != "Case":
            continue
        if node.get("enrichment_status") != "case_only" or node.get("lineage_ids"):
            protected_case_ids.add(node["id"])

    for edge in bundle.get("edges", []):
        edge_type = edge.get("type")
        source = edge.get("source")
        target = edge.get("target")
        if edge_type == "PART_OF" and target in nodes_by_id and nodes_by_id[target].get("type") == "Case":
            protected_case_ids.add(target)
        if edge_type == "HAS_MEMBER" and target in nodes_by_id and nodes_by_id[target].get("type") == "Case":
            protected_case_ids.add(target)
        if edge_type in CASE_EDGE_TYPES | TREATMENT_EDGE_TYPES:
            if source in nodes_by_id and nodes_by_id[source].get("type") == "Case":
                protected_case_ids.add(source)
            if target in nodes_by_id and nodes_by_id[target].get("type") == "Case":
                protected_case_ids.add(target)

    candidates = [
        node
        for node in nodes
        if node.get("type") == "Case"
        and node.get("enrichment_status", "case_only") == "case_only"
        and node.get("id") not in protected_case_ids
    ]
    candidates.sort(
        key=lambda node: (
            float(node.get("authority_score") or 0.0),
            int(node.get("degree") or 0),
            node.get("decision_date", ""),
            node.get("case_name", node.get("label", "")),
        )
    )
    trim_count = min(len(nodes) - max_total_nodes, len(candidates))
    if trim_count <= 0:
        return {"max_total_nodes": max_total_nodes, "pruned_case_only_nodes": 0, "cap_applied": False}

    dropped_ids = {node["id"] for node in candidates[:trim_count]}
    bundle["nodes"] = [node for node in nodes if node.get("id") not in dropped_ids]
    bundle["edges"] = [
        edge for edge in bundle.get("edges", [])
        if edge.get("source") not in dropped_ids and edge.get("target") not in dropped_ids
    ]
    for case_id in dropped_ids:
        bundle.get("case_cards", {}).pop(case_id, None)
    return {"max_total_nodes": max_total_nodes, "pruned_case_only_nodes": trim_count, "cap_applied": True}


def _recalculate_hybrid_meta(bundle: dict, merge_meta: dict | None = None) -> dict:
    nodes = bundle.get("nodes", [])
    node_ids = {node["id"] for node in nodes if node.get("id")}
    bundle["case_cards"] = {
        case_id: card
        for case_id, card in bundle.get("case_cards", {}).items()
        if case_id in node_ids
    }
    meta = dict(bundle.get("meta", {}))
    meta.update(
        {
            "node_count": len(nodes),
            "edge_count": len(bundle["edges"]),
            "case_count": sum(1 for node in nodes if node.get("type") == "Case"),
            "statute_count": sum(1 for node in nodes if node.get("type") == "Statute"),
            "topic_count": sum(1 for node in nodes if node.get("type") == "Topic"),
            "lineage_count": sum(1 for node in nodes if node.get("type") == "AuthorityLineage"),
            "lineages": _lineage_meta_summaries(nodes, bundle["edges"]),
            "paragraph_count": sum(1 for node in nodes if node.get("type") == "Paragraph"),
            "proposition_count": sum(1 for node in nodes if node.get("type") == "Proposition"),
            "enriched_case_count": sum(
                1
                for node in nodes
                if node.get("type") == "Case" and node.get("enrichment_status") != "case_only"
            ),
        }
    )
    if merge_meta:
        meta.setdefault("cumulative_merge", {}).update(merge_meta)
    bundle["meta"] = meta
    return bundle


def merge_with_previous_artifact(
    new_bundle: dict,
    previous_graph_path: str | Path,
    *,
    max_total_nodes: int | None = 10_000,
) -> dict:
    """Merge a freshly generated hybrid bundle with the previous published artifact.

    The fresh bundle wins for matching ids. Previous-only nodes, edges, and case
    cards are retained so an unlucky crawl/build cycle cannot make the published
    graph shrink. If ``max_total_nodes`` is exceeded, only low-value unenriched
    case-only shells are pruned; enriched cases, lineage members, and cited
    authorities are preserved.
    """
    previous_path = Path(previous_graph_path).expanduser()
    if not previous_path.exists():
        return _recalculate_hybrid_meta(_clone_public(new_bundle), {"enabled": True, "previous_found": False})

    previous_bundle = json.loads(previous_path.read_text(encoding="utf-8"))
    previous_nodes = previous_bundle.get("nodes", [])
    new_nodes = new_bundle.get("nodes", [])
    new_node_ids = {node["id"] for node in new_nodes if node.get("id")}
    merged_nodes = [_clone_public(node) for node in new_nodes]
    merged_nodes.extend(_clone_public(node) for node in previous_nodes if node.get("id") not in new_node_ids)
    node_ids = {node["id"] for node in merged_nodes if node.get("id")}

    edge_by_key: dict[tuple[str, str, str, str], dict] = {}
    for edge in previous_bundle.get("edges", []):
        edge_by_key[_edge_merge_key(edge)] = _clone_public(edge)
    for edge in new_bundle.get("edges", []):
        edge_by_key[_edge_merge_key(edge)] = _clone_public(edge)
    new_edge_keys: set[tuple[str, str, str, str]] = set()
    merged_edges: list[dict] = []
    for edge in new_bundle.get("edges", []):
        key = _edge_merge_key(edge)
        if key in edge_by_key and key not in new_edge_keys:
            merged_edges.append(edge_by_key[key])
            new_edge_keys.add(key)
    merged_edges.extend(edge for key, edge in edge_by_key.items() if key not in new_edge_keys)

    merged_case_cards = {
        **_clone_public(previous_bundle.get("case_cards", {})),
        **_clone_public(new_bundle.get("case_cards", {})),
    }
    merged_bundle = {
        **_clone_public(new_bundle),
        "nodes": merged_nodes,
        "edges": merged_edges,
        "case_cards": merged_case_cards,
    }

    topic_repair = _repair_orphan_topic_paths(merged_bundle)
    cap_status = _drop_low_value_case_shells(merged_bundle, max_total_nodes)
    merge_meta = {
        "enabled": True,
        "previous_found": True,
        "previous_path": str(previous_path),
        "previous_node_count": len(previous_nodes),
        "previous_edge_count": len(previous_bundle.get("edges", [])),
        "fresh_node_count": len(new_nodes),
        "fresh_edge_count": len(new_bundle.get("edges", [])),
        "retained_previous_only_nodes": sum(1 for node in previous_nodes if node.get("id") not in new_node_ids),
        **topic_repair,
        **cap_status,
    }
    return _recalculate_hybrid_meta(merged_bundle, merge_meta)


def write_hybrid_graph_artifacts(bundle: dict, output_dir: str | Path) -> dict:
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    graph_file = output_path / "hierarchical_graph.json"
    manifest_file = output_path / "manifest.json"
    public_projection_file = output_path / "public_projection.json"
    neo4j_constraints_file = output_path / "neo4j_constraints.cypher"
    neo4j_import_file = output_path / "neo4j_import.cypher"

    graph_file.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_file.write_text(json.dumps(bundle["meta"], indent=2, ensure_ascii=False), encoding="utf-8")
    public_projection_file.write_text(json.dumps(export_public_projection(bundle), indent=2, ensure_ascii=False), encoding="utf-8")
    neo4j_constraints_file.write_text(NEO4J_CONSTRAINTS_CYPHER, encoding="utf-8")
    neo4j_import_file.write_text(NEO4J_IMPORT_TEMPLATE, encoding="utf-8")
    return bundle["meta"]


def build_hybrid_graph_artifacts(
    graph_path: str | Path,
    output_dir: str | Path,
    title: str | None = None,
    *,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
) -> dict:
    payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    bundle = build_hierarchical_graph_bundle(
        payload,
        title=title,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
    )
    return write_hybrid_graph_artifacts(bundle, output_dir)


class HybridGraphStore:
    def __init__(self, bundle: dict) -> None:
        self.bundle = bundle
        self.nodes = {node["id"]: node for node in bundle["nodes"]}
        self.edges = bundle["edges"]
        self.case_cards = bundle.get("case_cards", {})
        self.outgoing: defaultdict[str, list[dict]] = defaultdict(list)
        self.incoming: defaultdict[str, list[dict]] = defaultdict(list)
        for edge in self.edges:
            self.outgoing[edge["source"]].append(edge)
            self.incoming[edge["target"]].append(edge)
        # Lazy embedding backend for semantic retrieval boost
        self._embedding_backend = None
        try:
            self._embedding_backend = create_embedding_backend(
                backend=os.environ.get("CASEMAP_QUERY_EMBEDDING_BACKEND", "auto"),
            )
        except Exception:
            pass
        if self._embedding_backend is not None:
            try:
                _populate_summary_embeddings(
                    list(self.nodes.values()),
                    backend=self._embedding_backend,
                    allow_openai=bool(os.environ.get("CASEMAP_QUERY_EMBEDDING_BACKEND", "").strip()),
                )
            except Exception:
                pass

    @classmethod
    def from_file(cls, path: str | Path) -> "HybridGraphStore":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def manifest(self) -> dict:
        return self.bundle["meta"]

    def tree_counts(self) -> dict:
        return self.bundle["tree"]

    def case_card(self, case_id: str) -> dict:
        card = self.case_cards.get(case_id)
        if card:
            derived = dict(card.get("derived_relationships", {}))
            if "factually_similar" not in derived:
                derived["factually_similar"] = self.find_similar_cases(case_id, top_k=5)
            return {**card, "derived_relationships": derived}
        node = self.nodes.get(case_id)
        if not node or node["type"] != "Case":
            raise KeyError(case_id)

        # Build principles from Paragraph → Proposition edges dynamically
        principles = []
        for edge in self.incoming.get(case_id, []):
            if edge["type"] != "PART_OF":
                continue
            para_node = self.nodes.get(edge["source"])
            if not para_node or para_node["type"] != "Paragraph":
                continue
            prop_node = None
            cited_authority = None
            for sup_edge in self.outgoing.get(para_node["id"], []):
                if sup_edge["type"] == "SUPPORTS":
                    prop_node = self.nodes.get(sup_edge["target"])
                    if prop_node:
                        for cite_edge in self.outgoing.get(prop_node["id"], []):
                            if cite_edge["type"] == "CITES":
                                ct = self.nodes.get(cite_edge["target"])
                                if ct:
                                    cited_authority = {"id": ct["id"], "label": ct.get("label", ""), "type": ct["type"]}
                                    break
                    break
            principles.append({
                "paragraph_span": para_node.get("paragraph_span", ""),
                "label_en": prop_node.get("label_en", "") if prop_node else "",
                "statement_en": prop_node.get("statement_en", para_node.get("public_excerpt", "")) if prop_node else para_node.get("public_excerpt", ""),
                "public_excerpt": para_node.get("public_excerpt", ""),
                "hklii_deep_link": para_node.get("hklii_deep_link", ""),
                "cited_authority": cited_authority,
            })

        return {
            "id": case_id,
            "metadata": {
                "id": node["id"],
                "neutral_citation": node.get("neutral_citation", ""),
                "parallel_citations": node.get("parallel_citations", []),
                "case_name": node.get("case_name", node["label"]),
                "short_name": node.get("short_name", _short_case_name(node.get("case_name", node["label"]))),
                "court_code": node.get("court_code", ""),
                "court_name": node.get("court_name", ""),
                "court_level": node.get("court_level", ""),
                "decision_date": node.get("decision_date", ""),
                "judges": node.get("judges", []),
                "source_links": node.get("source_links", []),
                "summary_en": node.get("summary_en", ""),
                "summary_zh": node.get("summary_zh", ""),
                "authority_score": node.get("authority_score", 0.0),
                "topic_paths": node.get("topic_paths", []),
                "lineage_ids": node.get("lineage_ids", []),
                "enrichment_status": node.get("enrichment_status", "case_only"),
            },
            "principles": principles,
            "relationships": [],
            "lineage_memberships": [],
            "derived_relationships": {
                "upstream_authorities": [],
                "downstream_applications": [],
                "same_lineage_cases": [],
                "factually_similar": self.find_similar_cases(case_id, top_k=5),
                "statutory_interpretations": [],
            },
        }

    def _case_similarity_payload(self, node: dict, score: float) -> dict:
        return {
            "id": node["id"],
            "case_id": node["id"],
            "case_name": node.get("case_name", node.get("label", "")),
            "label": node.get("label", node.get("case_name", "")),
            "neutral_citation": node.get("neutral_citation", ""),
            "summary_en": node.get("summary_en", ""),
            "source_links": node.get("source_links", []),
            "hklii_verified": bool(node.get("hklii_verified") or _first_hklii_url(node.get("source_links", []))),
            "similarity_score": round(score, 6),
        }

    def find_similar_cases(self, case_id: str, top_k: int = 5, exclude_same_lineage: bool = True) -> list[dict]:
        source = self.nodes.get(case_id)
        if not source or source.get("type") != "Case":
            return []
        source_lineages = set(source.get("lineage_ids", []))
        source_embedding = source.get("summary_embedding", [])
        source_tokens = set(tokenize(f"{source.get('case_name', '')} {source.get('summary_en', '')} {' '.join(source.get('topic_paths', []))}"))
        scored: list[tuple[float, dict]] = []
        for node in self.nodes.values():
            if node.get("type") != "Case" or node["id"] == case_id:
                continue
            if exclude_same_lineage and source_lineages and (source_lineages & set(node.get("lineage_ids", []))):
                continue
            score = _cosine_similarity(source_embedding, node.get("summary_embedding", []))
            if score <= 0:
                target_tokens = set(tokenize(f"{node.get('case_name', '')} {node.get('summary_en', '')} {' '.join(node.get('topic_paths', []))}"))
                overlap = len(source_tokens & target_tokens)
                score = overlap / max(math.sqrt(len(source_tokens) * len(target_tokens)), 1) if source_tokens and target_tokens else 0.0
            if score > 0:
                scored.append((score, node))
        return [self._case_similarity_payload(node, score) for score, node in sorted(scored, key=lambda item: item[0], reverse=True)[: max(1, min(int(top_k or 5), 20))]]

    def find_similar_cases_for_text(self, text: str, top_k: int = 5) -> list[dict]:
        query = (text or "").strip()
        if not query:
            return []
        query_embedding: list[float] = []
        if self._embedding_backend is not None:
            try:
                query_embedding = self._embedding_backend.embed(query)
            except Exception:
                query_embedding = []
        query_tokens = set(tokenize(query))
        scored: list[tuple[float, dict]] = []
        for node in self.nodes.values():
            if node.get("type") != "Case":
                continue
            score = _cosine_similarity(query_embedding, node.get("summary_embedding", []))
            if score <= 0:
                target_tokens = set(tokenize(f"{node.get('case_name', '')} {node.get('summary_en', '')} {' '.join(node.get('topic_paths', []))}"))
                overlap = len(query_tokens & target_tokens)
                score = overlap / max(math.sqrt(len(query_tokens) * len(target_tokens)), 1) if query_tokens and target_tokens else 0.0
            if score > 0:
                scored.append((score, node))
        return [self._case_similarity_payload(node, score) for score, node in sorted(scored, key=lambda item: item[0], reverse=True)[: max(1, min(int(top_k or 5), 20))]]

    def _lineage_detail(self, lineage_node_id: str) -> dict:
        lineage = self.nodes.get(lineage_node_id, {})
        member_edges = sorted(
            [edge for edge in self.outgoing.get(lineage_node_id, []) if edge["type"] == "HAS_MEMBER"],
            key=lambda edge: edge.get("position") or 0,
        )
        members = []
        for edge in member_edges:
            node = self.nodes.get(edge["target"])
            if not node:
                continue
            members.append(
                {
                    "id": node["id"],
                    "case_id": node["id"] if node["type"] == "Case" else "",
                    "label": node.get("case_name", node.get("label", "")),
                    "type": node["type"],
                    "neutral_citation": node.get("neutral_citation", ""),
                    "position": edge.get("position"),
                    "code": edge.get("code", ""),
                    "treatment": edge.get("treatment", ""),
                    "note": edge.get("note", ""),
                    "source_links": node.get("source_links", []),
                    "hklii_verified": bool(node.get("hklii_verified") or _first_hklii_url(node.get("source_links", []))),
                }
            )
        return {
            "id": lineage_node_id.removeprefix("lineage:"),
            "node_id": lineage_node_id,
            "title": lineage.get("title", lineage.get("label", "")),
            "codes": lineage.get("codes", []),
            "topic_ids": lineage.get("topic_ids", []),
            "topic_labels": lineage.get("topic_labels", []),
            "source": lineage.get("source", "curated"),
            "confidence_status": lineage.get("confidence_status", "established"),
            "confidence_score": lineage.get("confidence_score", 1.0),
            "members": members,
            "member_count": len(members),
        }

    def _match_lineages(self, scoring_tokens: list[str] | set[str], limit: int = 5) -> list[dict]:
        token_set = set(scoring_tokens)
        if not token_set:
            return []
        scored: list[tuple[float, str]] = []
        for node in self.nodes.values():
            if node.get("type") != "AuthorityLineage":
                continue
            topic_labels = list(node.get("topic_labels", []))
            if not topic_labels:
                for edge in self.outgoing.get(node["id"], []):
                    if edge["type"] == "ABOUT_TOPIC" and edge["target"] in self.nodes:
                        topic_labels.append(self.nodes[edge["target"]].get("label_en", self.nodes[edge["target"]].get("label", "")))
            member_text = []
            for edge in self.outgoing.get(node["id"], []):
                if edge["type"] != "HAS_MEMBER":
                    continue
                member = self.nodes.get(edge["target"], {})
                member_text.append(f"{member.get('case_name', member.get('label', ''))} {edge.get('note', '')} {edge.get('treatment', '')}")
            lineage_tokens = set(tokenize(f"{node.get('title', node.get('label', ''))} {' '.join(topic_labels)} {' '.join(member_text)}"))
            overlap = len(token_set & lineage_tokens)
            if overlap:
                score = overlap / max(math.sqrt(len(token_set) * len(lineage_tokens)), 1)
                scored.append((score, node["id"]))
        return [self._lineage_detail(lineage_id) | {"match_score": round(score, 6)} for score, lineage_id in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]

    def focus_graph(self, node_id: str, depth: int = 1) -> dict:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        bounded_depth = max(1, min(depth, 2))
        visited = {node_id}
        queue = deque([(node_id, 0)])
        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= bounded_depth:
                continue
            neighbors = self.outgoing[current] + self.incoming[current]
            ranked_neighbors = sorted(
                neighbors,
                key=lambda edge: (
                    edge["type"] not in TREATMENT_EDGE_TYPES,
                    -float(edge.get("weight", 1.0)),
                    edge["target"],
                ),
            )
            limit = 18 if current_depth == 0 else 12
            for edge in ranked_neighbors[:limit]:
                other = edge["target"] if edge["source"] == current else edge["source"]
                if other in visited:
                    continue
                visited.add(other)
                queue.append((other, current_depth + 1))
        nodes = [self.nodes[visited_id] for visited_id in visited]
        node_set = {node["id"] for node in nodes}
        edges = [edge for edge in self.edges if edge["source"] in node_set and edge["target"] in node_set]
        facets = Counter(node["type"] for node in nodes)
        return {"focus": node_id, "nodes": nodes, "edges": edges, "facets": dict(facets)}

    def topic_detail(self, topic_id: str) -> dict:
        if topic_id not in self.nodes or self.nodes[topic_id]["type"] != "Topic":
            raise KeyError(topic_id)
        topic = self.nodes[topic_id]
        case_ids = [edge["source"] for edge in self.incoming[topic_id] if edge["type"] == "BELONGS_TO_TOPIC" and self.nodes[edge["source"]]["type"] == "Case"]
        lead_cases = sorted(
            (self.case_card(case_id) for case_id in case_ids),
            key=lambda card: (card["metadata"]["authority_score"], card["metadata"]["case_name"]),
            reverse=True,
        )[:8]
        lineages = []
        for edge in self.incoming[topic_id]:
            if edge["type"] != "ABOUT_TOPIC":
                continue
            lineage = self.nodes[edge["source"]]
            members = [
                {
                    "id": member_edge["target"],
                    "label": self.nodes[member_edge["target"]].get("label", self.nodes[member_edge["target"]].get("case_name", "")),
                    "type": self.nodes[member_edge["target"]]["type"],
                    "position": member_edge.get("position"),
                    "code": member_edge.get("code", ""),
                    "treatment": member_edge.get("treatment", ""),
                }
                for member_edge in self.outgoing[lineage["id"]]
                if member_edge["type"] == "HAS_MEMBER"
            ]
            lineages.append(
                {
                    "id": lineage["id"],
                    "title": lineage.get("title", lineage["label"]),
                    "codes": lineage.get("codes", []),
                    "members": sorted(members, key=lambda item: item["position"] or 0),
                }
            )
        return {
            "topic": topic,
            "lead_cases": lead_cases,
            "lineages": sorted(lineages, key=lambda item: item["title"]),
            "focus_graph": self.focus_graph(topic_id, depth=1),
        }

    def query(
        self,
        question: str,
        top_k: int = 5,
        mode: str = "extractive",
        model: str = "",
        max_citations: int = 8,
        classification_area: str = "",
        offence_keywords: list[str] | None = None,
    ) -> dict:
        try:
            bounded_top_k = max(1, min(int(top_k), 10))
        except (TypeError, ValueError):
            bounded_top_k = 5
        try:
            bounded_max_citations = max(2, min(int(max_citations), 20))
        except (TypeError, ValueError):
            bounded_max_citations = 8
        requested_mode = (mode or "extractive").strip().lower()
        legal_domain = _infer_legal_domain(self.bundle.get("meta"))
        query_tokens = tokenize(question)
        if not query_tokens:
            return {
                "question": question.strip(),
                "answer": "No usable legal terms were found in the query.",
                "answer_mode": "extractive",
                "sources": [],
                "citations": [],
                "authority_path": [],
                "authority_lineage_path": [],
                "matched_lineages": [],
                "supporting_nodes": [],
                "retrieval_trace": {"query_tokens": [], "matched_node_ids": []},
                "warnings": [],
                "llm": {
                    "requested": requested_mode == "openrouter",
                    "used": False,
                    "provider": "openrouter",
                    "model": model.strip() or os.environ.get("OPENROUTER_MODEL", "").strip() or OPENROUTER_DEFAULT_MODEL,
                },
                "legal_domain": legal_domain,
            }

        searchable: list[tuple[str, str, str]] = []
        for node in self.nodes.values():
            if node["type"] == "Case":
                searchable.append((node["id"], "Case", f"{node.get('case_name', '')} {node.get('summary_en', '')} {' '.join(node.get('topic_paths', []))}"))
            elif node["type"] == "Topic":
                searchable.append((node["id"], "Topic", f"{node.get('label_en', node.get('label', ''))} {node.get('summary', '')}"))
            elif node["type"] == "Proposition":
                searchable.append((node["id"], "Proposition", f"{node.get('label_en', '')} {node.get('statement_en', '')}"))

        # ── Stopword-filtered tokens for scoring ────────────────
        # Remove domain-generic words (hong, kong, criminal …) from
        # the scoring token set so they don't inflate every node
        # equally and drown out the distinctive query terms.
        scoring_tokens = [t for t in query_tokens if t not in QUERY_STOPWORDS]
        if not scoring_tokens:
            # All tokens were stopwords; fall back to original tokens
            scoring_tokens = query_tokens

        # ── Synonym expansion ────────────────────────────────────
        # Map inflected verb forms (stealing→theft, robbing→robbery …)
        # to their canonical legal forms so colloquial phrasing still
        # matches graph propositions that use formal legal vocabulary.
        synonym_expansions: list[str] = []
        for tok in scoring_tokens:
            canonical = QUERY_SYNONYMS.get(tok)
            if canonical and canonical not in scoring_tokens:
                synonym_expansions.append(canonical)
        if synonym_expansions:
            scoring_tokens = scoring_tokens + synonym_expansions

        # ── Query expansion via CRIMINAL_QUERY_HINTS ────────────
        # When query tokens match hint keys (e.g. "usdt" → money
        # laundering), derive extra tokens so that relevant topics and
        # cases receive a scoring bonus even when the original query
        # has zero lexical overlap with domain terms.
        # Domain-common words are excluded so they don't boost every
        # single node equally and drown out the real signal.
        _HINT_DOMAIN_STOPWORDS = {
            "hong", "kong", "criminal", "hksar", "law", "ordinance",
            "cap", "offence", "charge", "court", "section", "act",
            "crime", "crimes",
        }
        hint_expanded_tokens: set[str] = set()
        if legal_domain == "criminal":
            for token in query_tokens:
                if token in CRIMINAL_QUERY_HINTS:
                    for hint_query in CRIMINAL_QUERY_HINTS[token]:
                        hint_expanded_tokens.update(tokenize(hint_query))
            hint_expanded_tokens -= set(query_tokens)
            hint_expanded_tokens -= _HINT_DOMAIN_STOPWORDS

        # ── Area-aware topic path matching ──────────────────────
        # When classification_area is known (sentencing, defences, etc.)
        # and offence_keywords provide criminal_hits, build a set of
        # topic-path keywords to boost cases that match the doctrinal
        # area queried.  This prevents "murder sentencing" from
        # returning burglary authorities.
        _AREA_TOPIC_KEYWORDS: dict[str, set[str]] = {
            "sentencing": {"sentencing", "sentence", "penalty", "tariff", "imprisonment", "discount", "starting point"},
            "defences": {"defence", "defense", "duress", "self-defence", "insanity", "intoxication", "provocation", "diminished", "automatism", "consent"},
            "procedure": {"bail", "arrest", "confession", "evidence", "admissibility", "identification", "witness", "disclosure", "warrant", "caution", "silence", "police"},
            "offence_elements": set(),  # rely on offence_keywords instead
        }
        area_boost_tokens: set[str] = set()
        resolved_area = (classification_area or "").strip().lower()
        if resolved_area and resolved_area in _AREA_TOPIC_KEYWORDS:
            area_boost_tokens = _AREA_TOPIC_KEYWORDS[resolved_area]
        # Add offence keywords (e.g. "murder", "theft", "drug") for
        # sub-topic matching.  Also expand slang terms through hints
        # (e.g. "usdt" → "money laundering") so area matching works.
        # Verb-form synonyms (e.g. "stabbing") are resolved to their
        # canonical noun before hint expansion, and only expanded if
        # their canonical form aligns with (or doesn't conflict with)
        # tokens already in the boost set.  This prevents "stabbing a
        # dog" from boosting "Assault & Wounding" when the classifier
        # already identified "animal_cruelty" via the "dog" token.
        if offence_keywords:
            area_boost_tokens = area_boost_tokens | {k.lower() for k in offence_keywords}
            # Resolve synonyms to decide which hints to expand
            _resolved_offence_kws: set[str] = set()
            for kw in offence_keywords:
                kw_lower = kw.lower()
                canonical = QUERY_SYNONYMS.get(kw_lower, kw_lower)
                _resolved_offence_kws.add(canonical)
                _resolved_offence_kws.add(kw_lower)
            for kw in sorted(_resolved_offence_kws):
                if kw in CRIMINAL_QUERY_HINTS:
                    for hint_q in CRIMINAL_QUERY_HINTS[kw]:
                        for ht in tokenize(hint_q):
                            if ht not in _HINT_DOMAIN_STOPWORDS:
                                area_boost_tokens.add(ht)
        # Pre-compute per-case area relevance flag
        # Also build sibling-exclusion map for closely-related offences
        # (e.g. theft vs burglary) so that "theft elements" doesn't
        # return burglary-only cases.
        _OFFENCE_SIBLINGS: dict[str, set[str]] = {
            "theft": {"burglary", "robbery"},
            "burglary": {"theft", "robbery"},
            "robbery": {"theft", "burglary"},
            "murder": {"manslaughter"},
            "manslaughter": {"murder"},
            "assault": {"rape", "indecent"},
            "rape": {"assault", "indecent"},
        }
        # Identify the primary offence keyword from the query
        _primary_offences: set[str] = set()
        _sibling_offences: set[str] = set()
        if offence_keywords:
            for kw in offence_keywords:
                kw_lower = kw.lower()
                if kw_lower in _OFFENCE_SIBLINGS:
                    _primary_offences.add(kw_lower)
                    _sibling_offences |= _OFFENCE_SIBLINGS[kw_lower]
            # Don't exclude siblings that are also explicitly queried
            _sibling_offences -= _primary_offences
            _sibling_offences -= set(query_tokens)

        _case_area_match: dict[str, bool] = {}
        if area_boost_tokens:
            for node in self.nodes.values():
                if node["type"] == "Case":
                    paths_text = " ".join(node.get("topic_paths", [])).lower()
                    summary_text = (node.get("summary_en", "") or "").lower()
                    combined = paths_text + " " + summary_text
                    match_count = sum(1 for kw in area_boost_tokens if kw in combined)
                    matched = match_count >= 1
                    # Sibling exclusion: if the case matches a sibling
                    # offence but NOT the primary offence, treat as
                    # non-matching (e.g. burglary-only for theft query)
                    if matched and _primary_offences and _sibling_offences:
                        has_primary = any(p in combined for p in _primary_offences)
                        has_sibling = any(s in combined for s in _sibling_offences)
                        if has_sibling and not has_primary:
                            matched = False
                    _case_area_match[node["id"]] = matched

        lexical_scores: dict[str, float] = {}
        for node_id, kind, text in searchable:
            text_tokens = tokenize(text)
            if not text_tokens:
                lexical_scores[node_id] = 0.0
                continue
            text_token_set = set(text_tokens)
            query_token_set = set(scoring_tokens)
            overlap = len(query_token_set & text_token_set)
            score = overlap / max(math.sqrt(len(text_token_set) * len(query_token_set)), 1)
            if kind == "Proposition":
                score += 0.18
            elif kind == "Topic" and overlap:
                # Topics that match query terms should rank alongside
                # propositions so they enter best_node_ids and trigger
                # topic-mediated case retrieval downstream.
                score += 0.20
                # Extra boost for propositions from area-matched cases
                if _case_area_match:
                    prop_node = self.nodes.get(node_id, {})
                    for edge in self.incoming.get(node_id, []):
                        if edge["type"] == "SUPPORTS":
                            for pe in self.outgoing.get(edge["source"], []):
                                if pe["type"] == "PART_OF" and _case_area_match.get(pe["target"], False):
                                    score += 0.15
                                    break
                            break
                # Sibling-offence penalty at proposition level:
                # If the proposition text mentions a sibling offence
                # (e.g. "burglary") but NOT the primary offence
                # (e.g. "theft"), reduce its score significantly.
                if _primary_offences and _sibling_offences:
                    text_lower = text.lower()
                    prop_has_primary = any(p in text_lower for p in _primary_offences)
                    prop_has_sibling = any(s in text_lower for s in _sibling_offences)
                    if prop_has_sibling and not prop_has_primary:
                        score *= 0.3
            # Hint expansion bonus (50% dampening) — bridges lexical
            # gaps like "usdt" → "money laundering"
            if hint_expanded_tokens:
                hint_overlap = len(hint_expanded_tokens & text_token_set)
                if hint_overlap > 0:
                    hint_score = hint_overlap / max(math.sqrt(len(text_token_set) * len(hint_expanded_tokens)), 1)
                    score += hint_score * 0.5
            lexical_scores[node_id] = score
        lexical_norm = normalize_scores(lexical_scores)

        # ── Semantic embedding boost (30% weight) ─────────────────
        # If nodes have summary_embedding, compute cosine similarity with query
        semantic_boost: dict[str, float] = {}
        if hasattr(self, '_embedding_backend') and self._embedding_backend is not None:
            try:
                query_emb = self._embedding_backend.embed(question)
                if query_emb:
                    for node_id, _kind, _text in searchable:
                        node_emb = self.nodes[node_id].get("summary_embedding", [])
                        if node_emb and len(node_emb) == len(query_emb):
                            dot = sum(a * b for a, b in zip(query_emb, node_emb))
                            mag_q = math.sqrt(sum(a * a for a in query_emb))
                            mag_n = math.sqrt(sum(a * a for a in node_emb))
                            if mag_q > 0 and mag_n > 0:
                                semantic_boost[node_id] = max(0.0, dot / (mag_q * mag_n))
            except Exception:
                pass

        # Combine lexical (70%) + semantic (30%) scores
        combined_scores: dict[str, float] = {}
        for node_id in lexical_norm:
            lex = lexical_norm.get(node_id, 0.0)
            sem = semantic_boost.get(node_id, 0.0)
            combined_scores[node_id] = 0.7 * lex + 0.3 * sem if semantic_boost else lex

        best_node_ids = [
            node_id
            for node_id in sorted(combined_scores, key=combined_scores.get, reverse=True)
            if combined_scores[node_id] > 0
        ][: max(bounded_top_k * 2, 8)]
        lineage_match_tokens = set(scoring_tokens) | set(hint_expanded_tokens) | set(area_boost_tokens)
        matched_lineages = self._match_lineages(lineage_match_tokens, limit=5)

        supporting_node_ids: set[str] = set(best_node_ids[:bounded_top_k])
        support_case_ids: set[str] = set()
        support_case_scores: defaultdict[str, float] = defaultdict(float)
        for node_id in best_node_ids[:6]:
            node = self.nodes[node_id]
            node_score = lexical_norm.get(node_id, 0.0)
            if node["type"] == "Case":
                support_case_ids.add(node_id)
                support_case_scores[node_id] += node_score
            elif node["type"] == "Proposition":
                for edge in self.incoming[node_id]:
                    if edge["type"] != "SUPPORTS":
                        continue
                    paragraph_id = edge["source"]
                    supporting_node_ids.add(paragraph_id)
                    for paragraph_edge in self.outgoing[paragraph_id]:
                        if paragraph_edge["type"] == "PART_OF":
                            support_case_ids.add(paragraph_edge["target"])
                            supporting_node_ids.add(paragraph_edge["target"])
                            support_case_scores[paragraph_edge["target"]] += node_score + 0.22
            elif node["type"] == "Topic":
                topic_label_tokens = set(tokenize(node.get("label_en", node.get("label", ""))))
                scoring_token_set = set(scoring_tokens)
                _topic_common = topic_label_tokens & scoring_token_set
                # Use the better of topic-side and query-side overlap
                # so that a topic like "Insanity, Automatism and
                # Intoxication" still gets boosted even though only
                # 1/3 of its tokens match, because 1/2 of the query
                # tokens ("intoxication") are covered.
                topic_overlap = (
                    max(
                        len(_topic_common) / max(len(topic_label_tokens), 1),
                        len(_topic_common) / max(len(scoring_token_set), 1),
                    )
                    if topic_label_tokens else 0.0
                )
                # Also check hint-expanded tokens so that USDT → money
                # laundering hint fires the topic multiplier for the
                # "Money Laundering" topic.
                if topic_overlap < 0.5 and hint_expanded_tokens and topic_label_tokens:
                    hint_topic_overlap = (
                        len(topic_label_tokens & hint_expanded_tokens) / max(len(topic_label_tokens), 1)
                    )
                    topic_overlap = max(topic_overlap, hint_topic_overlap)
                # When the topic label strongly matches the query (e.g. "Money
                # Laundering" for a money laundering question), give its linked
                # cases a boost comparable to proposition-linked cases so they
                # rank competitively.
                if topic_overlap >= 0.5:
                    topic_multiplier = 1.5 + 0.3 * topic_overlap
                else:
                    topic_multiplier = 0.75
                for edge in self.incoming[node_id]:
                    if edge["type"] == "BELONGS_TO_TOPIC" and self.nodes[edge["source"]]["type"] == "Case":
                        support_case_ids.add(edge["source"])
                        supporting_node_ids.add(edge["source"])
                        support_case_scores[edge["source"]] += node_score * topic_multiplier
            for edge in self.outgoing[node_id][:8] + self.incoming[node_id][:8]:
                supporting_node_ids.add(edge["source"])
                supporting_node_ids.add(edge["target"])
                if self.nodes.get(edge["source"], {}).get("type") == "Case":
                    support_case_ids.add(edge["source"])
                    support_case_scores[edge["source"]] += node_score * 0.15
                if self.nodes.get(edge["target"], {}).get("type") == "Case":
                    support_case_ids.add(edge["target"])
                    support_case_scores[edge["target"]] += node_score * 0.15

        for lineage in matched_lineages:
            supporting_node_ids.add(lineage["node_id"])
            for member in lineage.get("members", []):
                member_id = member.get("id", "")
                if member.get("type") == "Case" and member_id in self.nodes:
                    support_case_ids.add(member_id)
                    supporting_node_ids.add(member_id)
                    support_case_scores[member_id] += 0.25

        # ── Area-aware reranking ────────────────────────────────
        # Boost cases matching the classified doctrinal area and
        # penalise cases that clearly belong to a different area.
        # This prevents "murder sentencing" from returning burglary
        # sentencing authorities.
        if _case_area_match:
            for case_id in support_case_ids:
                if _case_area_match.get(case_id, False):
                    support_case_scores[case_id] *= 1.6
                else:
                    # Stronger demotion for offence-mismatched cases
                    support_case_scores[case_id] *= 0.35

        support_cases = [
            self.case_card(case_id)
            for case_id in support_case_ids
            if case_id in self.nodes and self.nodes[case_id]["type"] == "Case"
        ]
        support_cases = sorted(
            support_cases,
            key=lambda card: (
                support_case_scores.get(card["id"], 0.0),
                len(card["principles"]),
                card["metadata"]["authority_score"],
                lexical_norm.get(card["id"], 0.0),
            ),
            reverse=True,
        )[:bounded_top_k]

        citation_pool: list[dict] = []
        for card in support_cases:
            case_score = support_case_scores.get(card["id"], 0.0)
            lineage_titles = sorted({entry["lineage_title"] for entry in card.get("lineage_memberships", []) if entry.get("lineage_title")})
            lineage_ids = sorted({entry["lineage_id"] for entry in card.get("lineage_memberships", []) if entry.get("lineage_id")})
            matched_lineage_ids = sorted(set(lineage_ids) & {item["id"] for item in matched_lineages})
            principles = card.get("principles", [])
            if principles:
                for position, principle in enumerate(principles[:3], start=1):
                    quote = (principle.get("statement_en") or principle.get("public_excerpt") or "").strip()
                    if not quote:
                        continue
                    citation_pool.append(
                        {
                            "case_id": card["id"],
                            "focus_node_id": card["id"],
                            "case_name": card["metadata"]["case_name"],
                            "neutral_citation": card["metadata"]["neutral_citation"],
                            "paragraph_span": principle.get("paragraph_span", ""),
                            "principle_label": principle.get("label_en", ""),
                            "quote": quote,
                            "hklii_deep_link": principle.get("hklii_deep_link", ""),
                            "links": card["metadata"]["source_links"],
                            "lineage_titles": lineage_titles,
                            "lineage_ids": lineage_ids,
                            "matched_lineage_ids": matched_lineage_ids,
                            "hklii_verified": bool(principle.get("hklii_deep_link") or _first_hklii_url(card["metadata"].get("source_links", []))),
                            "support_score": round(case_score + (0.06 / position), 6),
                        }
                    )
            else:
                summary = (card["metadata"].get("summary_en") or "").strip()
                if summary and not _is_placeholder_summary(summary):
                    citation_pool.append(
                        {
                            "case_id": card["id"],
                            "focus_node_id": card["id"],
                            "case_name": card["metadata"]["case_name"],
                            "neutral_citation": card["metadata"]["neutral_citation"],
                            "paragraph_span": "",
                            "principle_label": "",
                            "quote": summary,
                            "hklii_deep_link": "",
                            "links": card["metadata"]["source_links"],
                            "lineage_titles": lineage_titles,
                            "lineage_ids": lineage_ids,
                            "matched_lineage_ids": matched_lineage_ids,
                            "hklii_verified": bool(_first_hklii_url(card["metadata"].get("source_links", []))),
                            "support_score": round(case_score, 6),
                        }
                    )

        citations = sorted(
            citation_pool,
            key=lambda item: (item["support_score"], len(item["quote"]), item["case_name"]),
            reverse=True,
        )[:bounded_max_citations]

        live_hklii_trace: dict = {"attempted": False, "used": False, "searches": []}
        distinctive_query_tokens: set[str] = set()
        token_coverage: float | None = None
        suppress_local_summary = False
        prefer_live_grounding = False
        if legal_domain == "criminal":
            top_local_support = max((citation["support_score"] for citation in citations), default=0.0)
            distinctive_query_tokens = {token for token in query_tokens if token not in QUERY_STOPWORDS}
            local_grounding_text = " ".join(
                f"{citation.get('case_name', '')} {citation.get('quote', '')} {citation.get('principle_label', '')}"
                for citation in citations[:3]
            )
            # Include matched topic labels so topic-mediated retrieval
            # (e.g. "Money Laundering" topic → 30 cases) counts toward coverage.
            matched_topic_labels = " ".join(
                self.nodes[nid].get("label_en", self.nodes[nid].get("label", ""))
                for nid in best_node_ids[:6]
                if nid in self.nodes and self.nodes[nid]["type"] == "Topic"
            )
            local_grounding_tokens = set(tokenize(local_grounding_text + " " + matched_topic_labels))
            token_coverage = (
                len(distinctive_query_tokens & local_grounding_tokens) / max(len(distinctive_query_tokens), 1)
                if distinctive_query_tokens
                else 1.0
            )
            weak_local_grounding = (
                len(citations) < min(3, bounded_top_k)
                or top_local_support < 0.22
                or token_coverage < 0.34
            )
            # When hint expansion triggered a strong topic match
            # (e.g. "usdt" → money laundering), treat local results
            # as strong even if raw token_coverage is low — the
            # query uses slang/crypto terms that won't appear in
            # case text, but hint expansion already bridged the gap.
            if weak_local_grounding and hint_expanded_tokens and len(citations) >= 3 and top_local_support >= 0.22:
                hint_grounding_tokens = set(tokenize(local_grounding_text + " " + matched_topic_labels))
                hint_coverage = (
                    len(hint_expanded_tokens & hint_grounding_tokens) / max(len(hint_expanded_tokens), 1)
                )
                if hint_coverage >= 0.25:
                    weak_local_grounding = False
            if not weak_local_grounding:
                # Check if query tokens map to CRIMINAL_QUERY_HINTS but local
                # citations lack the domain-specific hint terms. This catches
                # cases like "stabbing one's dog" where 'stab' matches
                # human-violence cases giving false token_coverage.
                hint_triggered_tokens = [t for t in distinctive_query_tokens if t in CRIMINAL_QUERY_HINTS]
                if hint_triggered_tokens:
                    hint_terms: set[str] = set()
                    for ht in hint_triggered_tokens:
                        for hint_query in CRIMINAL_QUERY_HINTS[ht]:
                            hint_terms.update(tokenize(hint_query))
                    hint_terms -= QUERY_STOPWORDS
                    local_hint_coverage = (
                        len(hint_terms & local_grounding_tokens) / max(len(hint_terms), 1)
                        if hint_terms
                        else 1.0
                    )
                    if local_hint_coverage < 0.15:
                        weak_local_grounding = True
                        prefer_live_grounding = True
            if weak_local_grounding:
                prefer_live_grounding = token_coverage < 0.34
                live_hklii_trace["attempted"] = True
                live_grounding = _live_hklii_grounding(
                    question,
                    legal_domain=legal_domain,
                    max_results=max(3, bounded_top_k),
                    max_citations=bounded_max_citations,
                )
                live_hklii_trace["searches"] = live_grounding.get("search_trace", [])
                warnings_from_live = live_grounding.get("warnings", [])
                if warnings_from_live:
                    warnings = warnings_from_live[:]
                else:
                    warnings = []
                if live_grounding.get("citations"):
                    combined_citations = citations + live_grounding["citations"]
                    deduped: list[dict] = []
                    seen_citation_keys: set[tuple[str, str, str, str]] = set()
                    for citation in sorted(
                        combined_citations,
                        key=lambda item: (
                            1 if prefer_live_grounding and item.get("retrieval_origin") == "hklii_live" else 0,
                            item["support_score"],
                            len(item["quote"]),
                            item["case_name"],
                        ),
                        reverse=True,
                    ):
                        key = (
                            citation.get("case_name", "").lower(),
                            citation.get("neutral_citation", "").lower(),
                            citation.get("paragraph_span", "").lower(),
                            citation.get("quote", "")[:180].lower(),
                        )
                        if key in seen_citation_keys:
                            continue
                        seen_citation_keys.add(key)
                        deduped.append(citation)
                        if len(deduped) >= bounded_max_citations:
                            break
                    citations = deduped
                    live_hklii_trace["used"] = True
                    if not support_cases:
                        warnings.append("Local criminal graph coverage was weak, so live HKLII authorities were retrieved.")
                else:
                    # Keep local citations as fallback even when live grounding
                    # was preferred but returned nothing.  Clearing them left
                    # the user with 0 results despite having relevant cases.
                    # Filter out weak local citations that would confuse users.
                    # Only keep citations with support_score above a minimum
                    # relevance threshold *or* those from curated enrichments.
                    _MIN_WEAK_FALLBACK_SCORE = 0.15
                    citations = [
                        c for c in citations
                        if c.get("support_score", 0) >= _MIN_WEAK_FALLBACK_SCORE
                    ]
                    if not warnings_from_live:
                        if citations:
                            warnings = ["Local criminal graph coverage was weak, and no live HKLII matches were found.  Showing best local results."]
                        else:
                            warnings = ["No reliable local citations were found for this query.  Try rephrasing with specific legal terms."]
            else:
                warnings = []
        else:
            warnings = []

        for index, citation in enumerate(citations, start=1):
            citation.setdefault("retrieval_origin", "bundle")
            citation.setdefault("legal_domain", legal_domain)
            citation.setdefault("hklii_verified", bool(citation.get("hklii_deep_link") or _first_hklii_url(citation.get("links", []))))
            citation["citation_id"] = f"C{index}"

        if citations:
            extractive_answer = " ".join(
                f"[{citation['citation_id']}] {citation['quote']}"
                for citation in citations[: min(3, len(citations))]
            ).strip()
        elif suppress_local_summary:
            extractive_answer = (
                "No directly relevant criminal authority was recovered from the current graph bundle or the live HKLII fallback for this query."
            )
        elif support_cases:
            extractive_answer = " ".join(
                card["metadata"]["summary_en"]
                for card in support_cases[:2]
                if card["metadata"]["summary_en"] and not _is_placeholder_summary(card["metadata"]["summary_en"])
            ).strip() or "Related graph records were found, but none currently has paragraph-level verified authority for this query."
        else:
            extractive_answer = "No sufficiently relevant authority path was found in the current graph bundle."

        answer_mode = "extractive"
        resolved_model = model.strip() or os.environ.get("OPENROUTER_MODEL", "").strip() or OPENROUTER_DEFAULT_MODEL
        answer = extractive_answer
        if requested_mode == "openrouter":
            try:
                answer, resolved_model = _openrouter_grounded_answer(question, citations, model=model)
                answer_mode = "openrouter_grounded"
            except Exception as exc:  # pragma: no cover - exercised only when OpenRouter mode is requested.
                warnings.append(f"OpenRouter synthesis skipped: {exc}")

        authority_path = []
        for card in support_cases:
            if card["lineage_memberships"]:
                first_lineage = card["lineage_memberships"][0]
                authority_path.append(
                    {
                        "lineage_id": first_lineage["lineage_id"],
                        "lineage_title": first_lineage["lineage_title"],
                        "case_id": card["id"],
                        "case_name": card["metadata"]["case_name"],
                        "position": first_lineage.get("position"),
                    }
                )
        if not authority_path and support_cases:
            top_case = support_cases[0]
            authority_path = [
                {
                    "lineage_id": "",
                    "lineage_title": "Derived authority neighborhood",
                    "case_id": top_case["id"],
                    "case_name": top_case["metadata"]["case_name"],
                    "position": None,
                }
            ]
        if not authority_path and citations:
            first_citation = citations[0]
            authority_path = [
                {
                    "lineage_id": "",
                    "lineage_title": "Live authority fallback" if first_citation.get("retrieval_origin") == "hklii_live" else "Derived authority neighborhood",
                    "case_id": first_citation.get("case_id", ""),
                    "case_name": first_citation.get("case_name", ""),
                    "position": None,
                }
            ]

        authority_lineage_path = matched_lineages[:]
        if not authority_lineage_path:
            seen_lineage_ids: set[str] = set()
            for card in support_cases:
                for membership in card.get("lineage_memberships", []):
                    lineage_node_id = membership.get("lineage_node_id") or f"lineage:{membership.get('lineage_id', '')}"
                    if lineage_node_id in self.nodes and lineage_node_id not in seen_lineage_ids:
                        seen_lineage_ids.add(lineage_node_id)
                        authority_lineage_path.append(self._lineage_detail(lineage_node_id))
                    if len(authority_lineage_path) >= 3:
                        break
                if len(authority_lineage_path) >= 3:
                    break

        sources = []
        seen_cases: set[str] = set()
        for citation in citations:
            case_id = citation["case_id"]
            if case_id in seen_cases:
                continue
            seen_cases.add(case_id)
            card = next((entry for entry in support_cases if entry["id"] == case_id), None)
            sources.append(
                {
                    "case_id": case_id,
                    "case_name": citation["case_name"],
                    "neutral_citation": citation["neutral_citation"],
                    "paragraph_span": citation["paragraph_span"],
                    "text": citation["quote"],
                    "links": card["metadata"]["source_links"] if card else citation.get("links", []),
                    "citation_ids": [entry["citation_id"] for entry in citations if entry["case_id"] == case_id],
                    "retrieval_origin": citation.get("retrieval_origin", "bundle"),
                    "legal_domain": citation.get("legal_domain", legal_domain),
                    "hklii_verified": bool(citation.get("hklii_verified")),
                }
            )

        return {
            "question": question.strip(),
            "answer": answer.strip(),
            "answer_mode": answer_mode,
            "sources": sources,
            "citations": citations,
            "authority_path": authority_path,
            "authority_lineage_path": authority_lineage_path,
            "matched_lineages": matched_lineages,
            "supporting_nodes": [
                {
                    "id": node_id,
                    "type": self.nodes[node_id]["type"],
                    "label": self.nodes[node_id].get("label", self.nodes[node_id].get("case_name", "")),
                }
                for node_id in sorted(supporting_node_ids)
                if node_id in self.nodes
            ][:25],
            "retrieval_trace": {
                "legal_domain": legal_domain,
                "query_tokens": query_tokens[:24],
                "matched_node_ids": best_node_ids[:12],
                "top_case_scores": [
                    {
                        "case_id": card["id"],
                        "case_name": card["metadata"]["case_name"],
                        "support_score": round(support_case_scores.get(card["id"], 0.0), 6),
                    }
                    for card in support_cases
                ],
                "distinctive_query_tokens": sorted(distinctive_query_tokens),
                "local_token_coverage": round(token_coverage, 4) if legal_domain == "criminal" else None,
                "live_hklii": live_hklii_trace,
            },
            "warnings": warnings,
            "llm": {
                "requested": requested_mode == "openrouter",
                "used": answer_mode == "openrouter_grounded",
                "provider": "openrouter",
                "model": resolved_model,
            },
            "legal_domain": legal_domain,
        }


_CASE_NAME_MENTION_RE = re.compile(r"\b([A-Z][A-Za-z'().&\- ]{1,90}\s+v\.?\s+[A-Z][A-Za-z'().&\- ]{1,120})")

_CASE_ANALYSIS_PROMPT = """You are a Hong Kong legal analysis assistant.

You must answer only from the supplied graph evidence, matched authority lineages, and factually similar cases.
Rules:
- Cite only supplied citation IDs such as [C1] and supplied lineage IDs.
- Do not invent case names, neutral citations, paragraph numbers, or HKLII links.
- If the evidence is incomplete, say which issue is not safely grounded.
- Keep the answer educational and not legal advice.

User facts:
{facts}

Graph citations:
{citations}

Matched lineages:
{lineages}

Factually similar cases:
{similar_cases}

Return a concise structured analysis."""


def validate_grounded_answer(
    answer: str,
    *,
    allowed_citation_ids: set[str],
    allowed_case_names: set[str],
    context: str = "case_analysis",
) -> tuple[list[str], list[dict]]:
    warnings: list[str] = []
    log_entries: list[dict] = []
    cited_ids = set(re.findall(r"\[C\d+\]", answer or ""))
    unknown_citations = sorted(cited_id for cited_id in cited_ids if cited_id.strip("[]") not in allowed_citation_ids)
    if unknown_citations:
        warnings.append(f"Removed confidence in {len(unknown_citations)} unsupported citation marker(s): {', '.join(unknown_citations)}.")
        log_entries.append({"context": context, "type": "unknown_citation_marker", "values": unknown_citations})

    normalized_allowed = {_normalize_label(name) for name in allowed_case_names if name}
    unknown_cases: list[str] = []
    for match in _CASE_NAME_MENTION_RE.findall(answer or ""):
        normalized = _normalize_label(match)
        if normalized and normalized not in normalized_allowed:
            unknown_cases.append(match.strip())
    if unknown_cases:
        unique_unknown = sorted(set(unknown_cases))
        warnings.append(f"Detected {len(unique_unknown)} case name(s) not present in the supplied graph evidence.")
        log_entries.append({"context": context, "type": "unknown_case_name", "values": unique_unknown})
    if log_entries:
        append_hallucination_log(log_entries)
    return warnings, log_entries


def _case_analysis_llm(
    facts: str,
    query_result: dict,
    similar_cases: list[dict],
    *,
    mode: str = "deepseek",
    model: str = "",
) -> tuple[str, str]:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if mode == "deepseek" and deepseek_key:
        endpoint = DEEPSEEK_API_ENDPOINT
        api_key = deepseek_key
        selected_model = model.strip() or DEEPSEEK_DEFAULT_MODEL
    elif openrouter_key:
        endpoint = OPENROUTER_API_ENDPOINT
        api_key = openrouter_key
        selected_model = model.strip() or os.environ.get("OPENROUTER_MODEL", "").strip() or OPENROUTER_DEFAULT_MODEL
    elif deepseek_key:
        endpoint = DEEPSEEK_API_ENDPOINT
        api_key = deepseek_key
        selected_model = model.strip() or DEEPSEEK_DEFAULT_MODEL
    else:
        raise RuntimeError("No LLM API key configured for case analysis.")

    citation_lines = []
    for citation in query_result.get("citations", [])[:10]:
        citation_lines.append(
            f"[{citation.get('citation_id', '')}] {citation.get('case_name', '')} {citation.get('neutral_citation', '')} "
            f"{citation.get('paragraph_span', '')}: {citation.get('quote', '')[:360]}"
        )
    lineage_lines = []
    for lineage in query_result.get("authority_lineage_path", [])[:5]:
        member_names = " -> ".join(member.get("label", "") for member in lineage.get("members", [])[:8])
        lineage_lines.append(f"- {lineage.get('id', '')}: {lineage.get('title', '')} ({lineage.get('confidence_status', '')}) {member_names}")
    similar_lines = [
        f"- {case.get('case_name', case.get('label', ''))} {case.get('neutral_citation', '')}: score {case.get('similarity_score', 0)}"
        for case in similar_cases[:8]
    ]
    prompt = _CASE_ANALYSIS_PROMPT.format(
        facts=facts.strip(),
        citations="\n".join(citation_lines) or "(none)",
        lineages="\n".join(lineage_lines) or "(none)",
        similar_cases="\n".join(similar_lines) or "(none)",
    )
    request = urllib_request.Request(
        endpoint,
        data=json.dumps({"model": selected_model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(request, timeout=OPENROUTER_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", "ignore")
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"Case analysis HTTP {exc.code}: {body[:240]}") from exc
    parsed = json.loads(raw)
    choices = parsed.get("choices", [])
    if not choices:
        raise RuntimeError("Case analysis LLM returned no choices.")
    return _extract_openrouter_message_text(choices[0].get("message", {}).get("content", "")), selected_model


def analyse_case_facts(
    store: "HybridGraphStore",
    facts: str,
    *,
    mode: str = "extractive",
    model: str = "",
    top_k: int = 5,
) -> dict:
    bounded_top_k = max(1, min(int(top_k or 5), 10))
    query_result = store.query(facts, top_k=bounded_top_k, mode="extractive", max_citations=max(8, bounded_top_k))
    similar_cases = store.find_similar_cases_for_text(facts, top_k=bounded_top_k)
    warnings = list(query_result.get("warnings", []))
    answer = query_result.get("answer", "")
    answer_mode = "extractive_case_analysis"
    model_used = ""
    if mode in {"deepseek", "openrouter"} and query_result.get("citations"):
        try:
            answer, model_used = _case_analysis_llm(facts, query_result, similar_cases, mode=mode, model=model)
            answer_mode = f"{mode}_case_analysis"
        except Exception as exc:
            warnings.append(f"Case analysis LLM skipped: {exc}")
    elif not query_result.get("citations"):
        warnings.append("No verified citations were available, so only retrieval metadata is shown.")

    allowed_citation_ids = {citation.get("citation_id", "") for citation in query_result.get("citations", [])}
    allowed_case_names = {citation.get("case_name", "") for citation in query_result.get("citations", [])}
    allowed_case_names |= {case.get("case_name", case.get("label", "")) for case in similar_cases}
    hallucination_warnings, log_entries = validate_grounded_answer(
        answer,
        allowed_citation_ids=allowed_citation_ids,
        allowed_case_names=allowed_case_names,
    )
    warnings.extend(hallucination_warnings)
    return {
        "facts": facts.strip(),
        "answer": answer.strip(),
        "answer_mode": answer_mode,
        "model_used": model_used,
        "citations": query_result.get("citations", []),
        "sources": query_result.get("sources", []),
        "matched_lineages": query_result.get("matched_lineages", []),
        "authority_lineage_path": query_result.get("authority_lineage_path", []),
        "factually_similar_cases": similar_cases,
        "retrieval_trace": query_result.get("retrieval_trace", {}),
        "warnings": warnings,
        "hallucination_log_entries": log_entries,
        "disclaimer": (
            "This tool provides legal information for educational purposes only and does not constitute legal advice. "
            "Always consult a qualified Hong Kong lawyer for advice on specific facts."
        ),
    }


# ---------------------------------------------------------------------------
# Determinator Pipeline
# ---------------------------------------------------------------------------

DEEPSEEK_API_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"

DETERMINATOR_SYSTEM_PROMPT = """You are an HK criminal law assistant. Apply this 8-step framework strictly:

Step 0 – Classify: Is this a criminal law / procedure question? If yes, which area: offence elements | defences | sentencing | pre-trial procedure | trial rights | post-conviction.

Step 1 – Offence & Ordinance: Map the described conduct to the correct HK ordinance and section. Examples: violence → Cap. 212; theft → Cap. 210; drugs → Cap. 134; animal cruelty → Cap. 169; tax evasion → Cap. 112 s.82. If unclear, list top 2-3 possible offences and ask for clarification.

Step 2 – Elements: State actus reus and mens rea for the identified offence. Note: some offences are strict liability (no mens rea required). Check each element against the user's stated facts — note which are present, missing, or ambiguous.

Step 3 – Defences: List only defences legally available for this specific offence in HK (e.g. duress, self-defence, intoxication if negates MR, mental disorder under CPO s.75, lawful authority). For each applicable defence, cite 1-2 relevant HK cases.

Step 4 – Procedure & Rights: Identify relevant procedural issues: police powers (Cap. 232 ss.50-59), right to silence, confession admissibility (voir dire under Cap. 221 s.65), bail (Cap. 221 s.9G), legal representation (Legal Aid Ordinance Cap. 227).

Step 5 – Sentencing: State maximum penalty from the ordinance. Apply HK sentencing principles. List applicable aggravating factors (planning, abuse of trust, vulnerable victim, repeat offending) and mitigating factors (remorse, guilty plea, no record, restitution).

Step 6 – Practical Guidance: Tailor advice: (a) if facing investigation — remain silent, seek lawyer, do not consent to searches without warrant; (b) if charged — duty lawyer, Legal Aid, plea options; (c) if third party/student — general legal education only.

Step 7 – Sources: For each case cited, provide: case name + neutral citation + 1-2 sentence ratio summary + how it applies to the facts + HKLII URL if known. No verbatim quotes longer than 2 sentences.

If you identify a new HK case or principle not in the existing knowledge base, return it in a JSON field "new_knowledge" as an array: [{"type": "Case", "label": "...", "neutral_citation": "...", "ratio": "...", "ordinance": "Cap. XXX", "hklii_url": "https://..."}]

IMPORTANT: Do not return irrelevant cases. Only cite cases directly applicable to the identified offence and the user's facts."""

NON_CRIMINAL_INDICATORS = {
    "contract", "tort", "negligence", "landlord", "tenant", "divorce",
    "employment", "company", "shareholder", "copyright", "trademark",
    "defamation", "nuisance", "trespass", "conveyancing", "probate",
    "bankruptcy", "winding", "arbitration", "mediation",
}

OFFENCE_ORDINANCE_RULES = [
    {
        "offence_family": "animal_cruelty",
        "ordinance": "Prevention of Cruelty to Animals Ordinance (Cap. 169)",
        "section": "s.3",
        "keywords": {"animal", "dog", "cat", "pet", "cruelty", "torture", "neglect", "abandon"},
        "phrases": {"animal cruelty", "cruelty to animals", "stab dog", "stab my dog"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "tax_evasion",
        "ordinance": "Inland Revenue Ordinance (Cap. 112)",
        "section": "s.82(1)",
        "keywords": {"tax", "ird", "income", "return", "evasion", "evade"},
        "phrases": {"not pay tax", "tax evasion", "omit from return"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "theft",
        "ordinance": "Theft Ordinance (Cap. 210)",
        "section": "s.9",
        "keywords": {"steal", "stole", "stolen", "stealing", "theft", "dishonestly", "property", "shoplift", "shoplifting", "shoplifted", "appropriat"},
        "phrases": {"take property", "shop theft", "stealing from", "took without"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "fraud",
        "ordinance": "Theft Ordinance (Cap. 210)",
        "section": "s.16A",
        "keywords": {"fraud", "deceit", "deception", "scam", "obtain"},
        "phrases": {"deception offence", "obtain by deception"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "assault_violence",
        "ordinance": "Offences against the Person Ordinance (Cap. 212)",
        "section": "general offences under Cap. 212",
        "keywords": {"assault", "wound", "wounding", "violence", "stab", "injure", "harm"},
        "phrases": {"inflict grievous bodily harm", "cause bodily harm"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "homicide",
        "ordinance": "Offences against the Person Ordinance (Cap. 212)",
        "section": "homicide offences",
        "keywords": {"murder", "manslaughter", "kill", "killed", "death", "homicide"},
        "phrases": {"cause death", "unlawful killing"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "dangerous_drugs",
        "ordinance": "Dangerous Drugs Ordinance (Cap. 134)",
        "section": "drug trafficking and possession offences",
        "keywords": {"drug", "drugs", "cocaine", "heroin", "ketamine", "meth", "trafficking", "possess"},
        "phrases": {"dangerous drugs", "drug trafficking"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "road_traffic",
        "ordinance": "Road Traffic Ordinance (Cap. 374)",
        "section": "road traffic offences",
        "keywords": {"drive", "driving", "vehicle", "car", "drink", "speed", "traffic"},
        "phrases": {"dangerous driving", "drink driving"},
        "strict_liability_possible": True,
    },
    {
        "offence_family": "public_order",
        "ordinance": "Public Order Ordinance (Cap. 245)",
        "section": "public order offences",
        "keywords": {"riot", "assembly", "unlawful", "public", "disorder"},
        "phrases": {"unlawful assembly", "public order"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "bribery",
        "ordinance": "Prevention of Bribery Ordinance (Cap. 201)",
        "section": "corruption offences",
        "keywords": {"bribe", "bribery", "corrupt", "advantage", "icac"},
        "phrases": {"prevention of bribery", "accept advantage"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "money_laundering",
        "ordinance": "Organized and Serious Crimes Ordinance (Cap. 455)",
        "section": "money laundering offences",
        "keywords": {"launder", "laundering", "proceeds", "indictable", "property"},
        "phrases": {"money laundering", "proceeds of crime"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "market_misconduct",
        "ordinance": "Securities and Futures Ordinance (Cap. 571)",
        "section": "market misconduct, false trading, price rigging, stock market manipulation, and insider dealing provisions",
        "keywords": {"market", "manipulation", "manipulat", "securities", "futures", "sfo", "sfc", "insider", "misconduct"},
        "phrases": {"market manipulation", "false trading", "insider dealing", "market misconduct", "front desk trader"},
        "strict_liability_possible": True,
    },
    {
        "offence_family": "sexual_offences",
        "ordinance": "Crimes Ordinance (Cap. 200)",
        "section": "sexual offences",
        "keywords": {"rape", "sexual", "indecent", "assault", "intercourse", "minor"},
        "phrases": {"sexual assault", "indecent assault"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "kidnapping",
        "ordinance": "Offences against the Person Ordinance (Cap. 212)",
        "section": "s.42 kidnapping; common law false imprisonment",
        "keywords": {"kidnap", "kidnapping", "abduct", "abduction", "imprison", "detention", "hostage"},
        "phrases": {"false imprisonment", "unlawful detention", "kidnap for ransom"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "criminal_intimidation",
        "ordinance": "Crimes Ordinance (Cap. 200)",
        "section": "s.24 criminal intimidation",
        "keywords": {"intimidat", "threaten", "threat", "extort", "extortion"},
        "phrases": {"criminal intimidation", "threats to kill", "demand with menaces"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "forgery",
        "ordinance": "Crimes Ordinance (Cap. 200)",
        "section": "Part IX forgery and related offences",
        "keywords": {"forgery", "forge", "forging", "counterfeit", "false instrument"},
        "phrases": {"using false instrument", "making false instrument"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "criminal_damage",
        "ordinance": "Crimes Ordinance (Cap. 200)",
        "section": "s.60 criminal damage; s.60(2) arson",
        "keywords": {"arson", "damage", "destroy", "fire", "vandal", "vandalism"},
        "phrases": {"criminal damage", "damage property", "set fire"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "computer_crimes",
        "ordinance": "Crimes Ordinance (Cap. 200)",
        "section": "s.161 access to computer with criminal or dishonest intent",
        "keywords": {"computer", "hack", "hacking", "cyber", "online", "internet", "phishing"},
        "phrases": {"access to computer", "computer crime", "criminal intent computer"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "handling_stolen_goods",
        "ordinance": "Theft Ordinance (Cap. 210)",
        "section": "s.24 handling stolen goods",
        "keywords": {"handling", "stolen", "receive", "receiving", "goods"},
        "phrases": {"handling stolen goods", "receiving stolen property"},
        "strict_liability_possible": False,
    },
    {
        "offence_family": "environmental",
        "ordinance": "Waste Disposal Ordinance (Cap. 354)",
        "section": "environmental protection offences",
        "keywords": {"pollution", "waste", "dump", "dumping", "effluent", "environment"},
        "phrases": {"water pollution", "waste disposal", "environmental offence"},
        "strict_liability_possible": True,
    },
    {
        "offence_family": "occupational_safety",
        "ordinance": "Factories and Industrial Undertakings Ordinance (Cap. 59)",
        "section": "occupational safety offences",
        "keywords": {"workplace", "factory", "construction", "safety", "occupational", "scaffold"},
        "phrases": {"occupational safety", "industrial accident", "workplace fatality"},
        "strict_liability_possible": True,
    },
]
NEUTRAL_CITATION_RE = re.compile(r"\[\d{4}\]\s+[A-Z]{2,8}\s+\d+")


class DeterminatorPipeline:
    """8-step structured RAG pipeline for HK criminal law queries."""

    def _map_offence_candidates(self, question: str) -> list[dict]:
        tokens = set(tokenize(question))
        joined = " ".join(tokenize(question))
        candidates: list[dict] = []
        for rule in OFFENCE_ORDINANCE_RULES:
            token_hits = sorted(rule["keywords"] & tokens)
            phrase_hits = sorted([phrase for phrase in rule.get("phrases", set()) if phrase in joined])
            score = len(token_hits) + (2 * len(phrase_hits))
            if score <= 0:
                continue
            candidates.append(
                {
                    "offence_family": rule["offence_family"],
                    "ordinance": rule["ordinance"],
                    "section": rule["section"],
                    "strict_liability_possible": rule["strict_liability_possible"],
                    "match_score": score,
                    "keyword_hits": token_hits,
                    "phrase_hits": phrase_hits,
                }
            )
        candidates.sort(key=lambda item: (item["match_score"], len(item["keyword_hits"]), len(item["phrase_hits"])), reverse=True)
        return candidates[:3]

    def _classify(self, question: str) -> dict:
        tokens = set(tokenize(question))
        non_criminal_hits = tokens & NON_CRIMINAL_INDICATORS
        criminal_hits = tokens & set(CRIMINAL_QUERY_HINTS.keys())
        criminal_keywords = {
            "crime", "criminal", "offence", "offense", "guilty", "innocent",
            "arrest", "charge", "prosecution", "defendant", "accused", "police",
            "court", "magistrate", "sentence", "imprisonment", "fine", "bail",
            "murder", "theft", "assault", "drug", "fraud", "bribery",
            # Verb / colloquial forms
            "steal", "stealing", "stole", "stolen",
            "rob", "robbing", "robbed",
            "kill", "killing", "killed",
            "stabbing", "stabbed",
            "shoplifting", "shoplifted",
            "laundering", "launder",
        }
        criminal_hits |= tokens & criminal_keywords

        is_criminal = bool(criminal_hits) or (not non_criminal_hits and len(tokens) > 2)

        area = "offence_elements"
        if any(t in tokens for t in {"sentence", "sentencing", "penalty", "imprisonment", "tariff"}):
            area = "sentencing"
        elif any(t in tokens for t in {"defence", "defences", "defense", "defenses", "duress", "self", "insanity", "intoxication"}):
            area = "defences"
        elif any(t in tokens for t in {"arrest", "bail", "confession", "police", "warrant", "right", "silence"}):
            area = "procedure"

        offence_candidates = self._map_offence_candidates(question)
        return {
            "is_criminal": is_criminal,
            "area": area,
            "criminal_hits": sorted(criminal_hits),
            "offence_candidates": offence_candidates,
            "primary_ordinance": offence_candidates[0] if offence_candidates else None,
        }

    def _llm_query(self, question: str, citations: list[dict], mode: str, model: str, classification: dict) -> dict:
        evidence_lines = []
        for citation in citations[:6]:
            evidence_lines.append(
                f"[{citation.get('citation_id', 'C?')}] {citation.get('case_name', '')} "
                f"{citation.get('neutral_citation', '')}\n"
                f"Paragraph: {citation.get('paragraph_span', 'n/a')}\n"
                f"Summary: {citation.get('quote', '')[:300]}"
            )

        ordinance_context = classification.get("primary_ordinance") or {}
        offence_lines = []
        for candidate in classification.get("offence_candidates", []):
            offence_lines.append(
                f"- {candidate['offence_family']}: {candidate['ordinance']} {candidate['section']} "
                f"(hits: {', '.join(candidate.get('keyword_hits', []))})"
            )

        messages = [
            {"role": "system", "content": DETERMINATOR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question:\n{question.strip()}\n\n"
                    + (
                        "Determined offence / ordinance candidates:\n"
                        + "\n".join(offence_lines)
                        + "\n\n"
                        if offence_lines
                        else ""
                    )
                    + (
                        f"Primary ordinance candidate: {ordinance_context.get('ordinance', '')} {ordinance_context.get('section', '')}\n\n"
                        if ordinance_context
                        else ""
                    )
                    + (
                        "Local knowledge base evidence:\n" + "\n\n".join(evidence_lines)
                        if evidence_lines
                        else (
                            "Grounding status: no verified local or live HKLII citations were recovered for this query.\n"
                            "You may still answer using general HK criminal law knowledge, but do not invent case citations.\n"
                            "Clearly signal when a proposition is general / unverified rather than citation-grounded."
                        )
                    )
                    + "\n\nProvide a structured answer following the 8-step framework."
                ),
            },
        ]

        # Try DeepSeek first if key available
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

        if deepseek_key and mode != "openrouter":
            selected_model = model.strip() or DEEPSEEK_DEFAULT_MODEL
            endpoint = DEEPSEEK_API_ENDPOINT
            api_key = deepseek_key
        elif openrouter_key:
            selected_model = model.strip() or os.environ.get("OPENROUTER_MODEL", "").strip() or OPENROUTER_DEFAULT_MODEL
            endpoint = OPENROUTER_API_ENDPOINT
            api_key = openrouter_key
        else:
            raise RuntimeError("No LLM API key configured (DEEPSEEK_API_KEY or OPENROUTER_API_KEY)")

        payload = {
            "model": selected_model,
            "temperature": 0,
            "messages": messages,
        }
        request = urllib_request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(request, timeout=OPENROUTER_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            raise RuntimeError(f"LLM HTTP {exc.code}: {body[:240]}") from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        parsed = json.loads(raw)
        choices = parsed.get("choices", [])
        if not choices:
            raise RuntimeError("LLM returned no choices")
        answer = _extract_openrouter_message_text(choices[0].get("message", {}).get("content", ""))

        # Extract new_knowledge JSON if present
        new_knowledge: list[dict] = []
        nk_match = re.search(r'"new_knowledge"\s*:\s*(\[.*?\])', answer, re.DOTALL)
        if nk_match:
            try:
                new_knowledge = json.loads(nk_match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        return {
            "answer": answer,
            "answer_mode": (
                "deepseek_determinator"
                if deepseek_key and mode != "openrouter"
                else "openrouter_determinator"
            ) + ("_ungrounded" if not citations else ""),
            "model_used": selected_model,
            "new_knowledge": new_knowledge,
        }

    def _ungrounded_answer(self, question: str, classification: dict) -> str:
        primary = classification.get("primary_ordinance") or {}
        alternatives = classification.get("offence_candidates", [])[1:3]
        lines = [
            "**Step 0 - Classification**",
            f"- Question type: Criminal law / procedure",
            f"- Primary area: {classification.get('area', 'offence_elements').replace('_', ' ')}",
            "",
            "**Step 1 - Potential Offence & Ordinance**",
        ]
        if primary:
            strict_note = " Possible strict-liability / regulatory features may apply." if primary.get("strict_liability_possible") else ""
            lines.append(
                f"- Most likely ordinance from the current classifier: {primary.get('ordinance', '')} {primary.get('section', '')}.{strict_note}"
            )
        else:
            lines.append("- No reliable ordinance mapping was produced from the current query wording.")
        if alternatives:
            lines.append("- Other possible offence families:")
            for candidate in alternatives:
                lines.append(f"  - {candidate.get('ordinance', '')} {candidate.get('section', '')}")
        lines.extend(
            [
                "",
                "**Step 2 - Elements / Application**",
                "- A fully grounded element-by-element analysis cannot be given yet because no verified local or live HKLII case authority was recovered for this query.",
                "",
                "**Step 3 - Defences / Procedure / Sentencing**",
                "- These steps should be treated cautiously until verified authorities are retrieved. The app is intentionally avoiding invented case citations here.",
                "",
                "**Step 4 - Source Status**",
                "- No verified supporting citations were found from the current graph bundle or the live HKLII fallback.",
                f"- Query asked: {question.strip()}",
                "",
                "**Step 5 - Next Step**",
                "- Rephrase the query with clearer facts or connect additional verified authorities before relying on a case-specific answer.",
            ]
        )
        return "\n".join(lines)

    def query(
        self,
        question: str,
        store: "HybridGraphStore",
        mode: str = "openrouter",
        model: str = "",
        max_citations: int = 8,
    ) -> dict:
        disclaimer = (
            "This tool provides legal information for educational purposes only "
            "and does not constitute legal advice. Always consult a qualified "
            "Hong Kong lawyer for advice on your specific situation."
        )

        classification = self._classify(question)
        if not classification["is_criminal"]:
            return {
                "question": question,
                "is_criminal": False,
                "answer": (
                    "This query does not appear to relate to Hong Kong criminal law. "
                    "Please rephrase your question or consult a general legal resource."
                ),
                "answer_mode": "classification_reject",
                "citations": [],
                "sources": [],
                "new_knowledge": [],
                "offence_candidates": classification["offence_candidates"],
                "primary_ordinance": classification["primary_ordinance"],
                "used_fallback": False,
                "disclaimer": disclaimer,
            }

        local_result = store.query(
            question,
            top_k=5,
            mode="extractive",
            max_citations=max_citations,
            classification_area=classification.get("area", ""),
            offence_keywords=classification.get("criminal_hits", []),
        )
        top_score = max((c.get("support_score", 0.0) for c in local_result.get("citations", [])), default=0.0)
        use_llm = mode in ("openrouter", "deepseek") and (
            os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        )
        used_fallback = top_score < 0.15 or len(local_result.get("citations", [])) < 2

        llm_answer = ""
        llm_mode = "extractive"
        model_used = ""
        new_knowledge: list[dict] = []

        if use_llm and local_result.get("citations"):
            try:
                llm_result = self._llm_query(question, local_result.get("citations", []), mode, model, classification)
                llm_answer = llm_result["answer"]
                llm_mode = llm_result["answer_mode"]
                model_used = llm_result["model_used"]
                new_knowledge = llm_result.get("new_knowledge", [])
            except Exception as exc:
                local_result.setdefault("warnings", []).append(f"LLM synthesis skipped: {exc}")
        elif use_llm and not local_result.get("citations"):
            try:
                llm_result = self._llm_query(question, [], mode, model, classification)
                llm_answer = llm_result["answer"]
                llm_mode = llm_result["answer_mode"]
                model_used = llm_result["model_used"]
                new_knowledge = llm_result.get("new_knowledge", [])
                local_result.setdefault("warnings", []).append(
                    "No verified citations were available, so the answer was generated as an ungrounded LLM fallback."
                )
            except Exception as exc:
                local_result.setdefault("warnings", []).append(f"Ungrounded LLM fallback failed: {exc}")

        final_answer = llm_answer or local_result.get("answer", "")
        final_mode = llm_mode
        if not local_result.get("citations"):
            if not llm_answer:
                final_answer = self._ungrounded_answer(question, classification)
                final_mode = "ungrounded_classifier_only"

        verifier = KnowledgeGrowthWriter()
        verified_new_knowledge, rejected_new_knowledge = verifier.verify_items(
            new_knowledge,
            legal_domain=_infer_legal_domain(store.bundle.get("meta")),
        )
        if rejected_new_knowledge:
            local_result.setdefault("warnings", []).append(
                f"Rejected {len(rejected_new_knowledge)} unverified proposed knowledge item(s)."
            )

        return {
            **local_result,
            "is_criminal": True,
            "classification_area": classification["area"],
            "offence_candidates": classification["offence_candidates"],
            "primary_ordinance": classification["primary_ordinance"],
            "answer": final_answer,
            "answer_mode": final_mode,
            "model_used": model_used,
            "new_knowledge": verified_new_knowledge,
            "rejected_new_knowledge": rejected_new_knowledge,
            "used_fallback": used_fallback,
            "disclaimer": disclaimer,
        }


# ---------------------------------------------------------------------------
# Knowledge Growth Writer
# ---------------------------------------------------------------------------

class KnowledgeGrowthWriter:
    """Persists new knowledge items extracted from LLM responses."""

    def _can_sync_supabase(self) -> bool:
        return bool(
            os.environ.get("SUPABASE_URL", "").strip()
            and os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
            and os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        )

    def _append_local_chroma_record(self, graph_path, item: dict, node: dict) -> None:
        graph_path_obj = Path(graph_path)
        chroma_path = graph_path_obj.with_name("llm_growth_chroma_records.json")
        payload = {"collection": "hk_criminal_live_growth", "records": []}
        if chroma_path.exists():
            try:
                payload = json.loads(chroma_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = {"collection": "hk_criminal_live_growth", "records": []}
        embedder = create_embedding_backend(backend=os.environ.get("CASEMAP_GROWTH_EMBEDDING_BACKEND", "auto"))
        text = item.get("ratio", "") or node.get("summary_en", "") or node.get("label", "")
        vector = embedder.embed_documents([text])[0] if text else []
        payload.setdefault("collection", "hk_criminal_live_growth")
        payload.setdefault("embedding_backend", embedder.manifest())
        payload.setdefault("records", []).append(
            {
                "id": node["id"],
                "document": text,
                "metadata": {
                    "label": node.get("label", ""),
                    "neutral_citation": node.get("neutral_citation", ""),
                    "ordinance": node.get("ordinance", ""),
                    "source": "llm_growth",
                },
                "embedding": vector,
            }
        )
        chroma_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _labels_match(self, proposed_label: str, actual_label: str) -> bool:
        proposed_tokens = set(tokenize(proposed_label))
        actual_tokens = set(tokenize(actual_label))
        if not proposed_tokens or not actual_tokens:
            return False
        overlap = len(proposed_tokens & actual_tokens) / max(1, len(proposed_tokens))
        return overlap >= 0.5

    def verify_items(
        self,
        new_knowledge_items: list[dict],
        *,
        legal_domain: str = "criminal",
    ) -> tuple[list[dict], list[dict]]:
        if not new_knowledge_items:
            return [], []
        crawler = HKLIICrawler()
        verified: list[dict] = []
        rejected: list[dict] = []
        for raw_item in new_knowledge_items:
            item = dict(raw_item)
            item_type = str(item.get("type", "Case")).strip() or "Case"
            label = str(item.get("label", "")).strip()
            if item_type != "Case":
                rejected.append({"item": item, "reason": "Only Case growth items are persisted at this stage."})
                continue
            if not label:
                rejected.append({"item": item, "reason": "Missing label."})
                continue
            if item.get("_verified_case_document") is not None and item.get("verification_status") == "verified_hklii":
                verified.append(item)
                continue
            hklii_url = str(item.get("hklii_url", "")).strip()
            if not hklii_url:
                rejected.append({"item": item, "reason": "Missing HKLII URL for verification."})
                continue
            parsed = urllib_parse.urlparse(hklii_url)
            if "hklii.hk" not in parsed.netloc or "/cases/" not in parsed.path:
                rejected.append({"item": item, "reason": "HKLII URL is missing or not a case page."})
                continue
            try:
                case_doc = crawler.fetch_case_document(parsed.path)
            except Exception as exc:
                rejected.append({"item": item, "reason": f"HKLII verification failed: {exc}"})
                continue
            provided_citation = str(item.get("neutral_citation", "")).strip()
            if provided_citation and case_doc.neutral_citation and provided_citation != case_doc.neutral_citation:
                rejected.append({"item": item, "reason": "Neutral citation did not match HKLII judgment."})
                continue
            if not self._labels_match(label, case_doc.case_name):
                rejected.append({"item": item, "reason": "Case label did not sufficiently match HKLII judgment title."})
                continue
            verified_item = {
                **item,
                "label": case_doc.case_name,
                "neutral_citation": case_doc.neutral_citation or provided_citation,
                "hklii_url": case_doc.public_url,
                "_verified_source": "hklii",
                "_verified_case_document": case_doc,
                "verification_status": "verified_hklii",
                "legal_domain": legal_domain,
            }
            verified.append(verified_item)
        return verified, rejected

    def _make_node(self, item: dict, legal_domain: str = "criminal") -> dict:
        label = item.get("label", "Unknown")
        node_type = item.get("type", "Case")
        node_id = f"{node_type.lower()}:llm_growth:{slugify(label)[:60]}"
        return {
            "id": node_id,
            "type": node_type,
            "label": label,
            "label_en": label,
            "case_name": label if node_type == "Case" else "",
            "short_name": _short_case_name(label) if node_type == "Case" else label[:60],
            "neutral_citation": item.get("neutral_citation", ""),
            "summary_en": item.get("ratio", ""),
            "source_links": (
                [{"label": "HKLII", "url": item["hklii_url"]}]
                if item.get("hklii_url")
                else []
            ),
            "topic_paths": [],
            "lineage_ids": [],
            "authority_score": 0.3,
            "enrichment_status": "llm_growth",
            "verification_status": item.get("verification_status", "unverified"),
            "legal_domain": legal_domain,
            "domain_tags": [legal_domain],
            "degree": 0,
            "ordinance": item.get("ordinance", ""),
        }

    def persist(
        self,
        new_knowledge_items: list[dict],
        store: "HybridGraphStore",
        graph_path,
        legal_domain: str = "criminal",
    ) -> list[str]:
        if not new_knowledge_items:
            return []
        verified_items, rejected_items = self.verify_items(new_knowledge_items, legal_domain=legal_domain)
        new_knowledge_items = verified_items
        store.bundle.setdefault("meta", {})["llm_growth_rejected_count"] = store.bundle.get("meta", {}).get("llm_growth_rejected_count", 0) + len(rejected_items)
        if not new_knowledge_items:
            return []
        added_ids: list[str] = []
        existing_ids = {n["id"] for n in store.bundle.get("nodes", [])}
        for item in new_knowledge_items:
            node = self._make_node(item, legal_domain)
            if node["id"] in existing_ids:
                continue
            store.bundle["nodes"].append(node)
            store.nodes[node["id"]] = node
            existing_ids.add(node["id"])
            added_ids.append(node["id"])
            try:
                self._append_local_chroma_record(graph_path, item, node)
            except Exception:
                pass
            case_doc = item.get("_verified_case_document")
            if case_doc and self._can_sync_supabase():
                try:
                    from .supabase_sync import sync_case_document_to_supabase
                    sync_case_document_to_supabase(
                        case_doc,
                        prefix="casemap/hk_criminal/live_growth",
                        catchwords=item.get("ratio", ""),
                        legal_principles=[item.get("ratio", "")] if item.get("ratio") else [],
                        local_path_hint=str(graph_path),
                        embedding_backend=os.environ.get("CASEMAP_GROWTH_EMBEDDING_BACKEND", "auto"),
                        embedding_model=os.environ.get("CASEMAP_GROWTH_EMBEDDING_MODEL", ""),
                    )
                except Exception:
                    pass

        if added_ids:
            store.bundle["meta"]["node_count"] = len(store.bundle["nodes"])
            try:
                graph_path_obj = Path(graph_path)
                graph_path_obj.write_text(
                    json.dumps(store.bundle, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                pass  # Non-fatal — in-memory update still valid

        return added_ids
