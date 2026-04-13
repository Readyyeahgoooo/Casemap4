from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from urllib import parse as urllib_parse
import http.client
import json
import math
import os
import re
import signal
import ssl
import urllib.error
import urllib.request

from .criminal_law_data import CRIMINAL_AUTHORITY_TREE
from .domain_classifier import classification_matches_target
from .embeddings import create_embedding_backend
from .graphrag import CASE_RE, STATUTE_RE, slugify, tokenize, top_keywords
from .hklii_crawler import HKLIICaseDocument, HKLIICrawler, HKLIISearchResult
from .hybrid_graph import build_hierarchical_graph_bundle, write_hybrid_graph_artifacts
from .lineage_discovery import DISCOVERED_LINEAGES_DEFAULT_PATH, discover_lineages_from_payload, load_discovered_lineages
from .relationship_graph import augment_public_payload_with_lineages
from .source_parser import Passage, SourceDocument, load_source_document
from .viewer import render_relationship_family_tree, render_relationship_map

HKLII_SOURCE_ID = "source:hklii_api"
HKLII_SOURCE_LABEL = "HKLII API"
MONITOR_REFRESH_SECONDS = 300
SOURCE_LOAD_TIMEOUT_SECONDS = 300
DOMAIN_TREE_DIR = Path("data") / "batch" / "domain_trees"
DEEPSEEK_API_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
CASE_NAME_CORE_RE = re.compile(
    r"([A-Z][A-Za-z0-9&'./()\- ]{1,120}\s+v\.?\s+[A-Z][A-Za-z0-9&'./()\- ]{1,160})"
)
LEADING_CASE_PREFIX_RE = re.compile(
    r"^(?:see(?:\s+also)?|in|the court of appeal in|the court of final appeal in|"
    r"the position in|with the intention of|custody or control|"
    r"intending by the destruction .*? of another|computer .*? in this part\.?\s*in)\s+",
    re.IGNORECASE,
)

CIVIL_DOMAIN_TREE_PROMPT = """Create a comprehensive Hong Kong civil law authority tree as strict JSON.

Return one JSON object with label_en, label_zh, summary_en, summary_zh, and modules.
Each module must have id, label_en, label_zh, summary_en, summary_zh, and subgrounds.
Each subground must have id, label_en, label_zh, summary_en, summary_zh, topics, and children.
Each topic must have id, label_en, label_zh, and 2-4 HKLII simplesearch search_queries.

Scope: civil is an umbrella branch for non-criminal Hong Kong disputes. Include at least
8 modules and at least 36 topics. Use practical Hong Kong terminology, ordinance names
and Cap. references where useful, and short search terms instead of long sentences.

Required modules:
- General Principles of Civil Procedure: pleadings, writs/originating summons, service,
  discovery/disclosure, interlocutory applications, summary judgment, strike out,
  trial, costs, enforcement, appeals, limitation.
- Contract Law: formation, consideration, intention, terms, interpretation,
  misrepresentation, mistake, duress/undue influence, breach, repudiation, frustration,
  damages, specific performance, injunctions, restitution, sale of goods, third-party rights.
- Tort Law: negligence, duty of care, breach, causation, remoteness, contributory negligence,
  occupiers' liability, vicarious liability, nuisance, defamation, personal injury,
  professional negligence.
- Property and Land Law: conveyancing, sale and purchase, leases, landlord and tenant,
  mortgages, co-ownership, adverse possession, easements, covenants, building management,
  deed of mutual covenant.
- Company and Commercial Law: directors' duties, shareholders' rights, unfair prejudice,
  derivative actions, winding up, insolvency overlap, banking, insurance, agency,
  sale of goods, securities/regulatory civil proceedings.
- Employment Law: employment contracts, wages, termination, wrongful/unreasonable dismissal,
  discrimination, employees' compensation, MPF, restraint of trade.
- Family Law: divorce, custody, care and control, access, maintenance, ancillary relief,
  domestic violence, injunctions, child welfare.
- Constitutional and Administrative Law: judicial review, natural justice, legitimate
  expectation, procedural fairness, Basic Law, Hong Kong Bill of Rights, remedies.
- Probate, Trusts and Equity: wills, probate, intestacy, estate administration, trusts,
  fiduciary duties, equitable remedies.
- Arbitration and ADR: arbitration agreements, stay of proceedings, award enforcement,
  setting aside, mediation/settlement.

Search query rules:
- Use 2-4 concise queries per topic, suitable for HKLII simplesearch.
- Prefer phrases like "summary judgment", "Order 14", "specific performance",
  "Misrepresentation Ordinance Cap. 284", "Occupiers Liability Ordinance Cap. 314",
  "unfair prejudice Companies Ordinance Cap. 622", "judicial review natural justice".
- Do not include criminal-only offences or broad questions.
- Keep ids stable snake_case and avoid duplicate topic ids.

Return only valid JSON with no markdown fences."""

DOMAIN_TREE_PROMPTS = {
    "civil": CIVIL_DOMAIN_TREE_PROMPT,
}


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_domain_id(value: str) -> str:
    normalized = slugify(value.replace("-", "_"))
    return normalized or "general"


def default_domain_label(domain_id: str) -> str:
    domain_id = normalize_domain_id(domain_id)
    try:
        from .domain_classifier import LEGAL_DOMAINS

        taxonomy_label = str(LEGAL_DOMAINS.get(domain_id, {}).get("label_en") or "").strip()
    except Exception:
        taxonomy_label = ""
    if taxonomy_label:
        if taxonomy_label.lower().startswith("hong kong"):
            return taxonomy_label
        return f"Hong Kong {taxonomy_label}"
    words = domain_id.replace("_", " ").strip()
    if not words:
        return "Hong Kong Legal Domain"
    if words.endswith(" law"):
        return f"Hong Kong {words.title()}"
    return f"Hong Kong {words.title()} Law"


def _domain_display_label(tree: dict, domain_id: str) -> str:
    label = str(tree.get("label_en") or default_domain_label(domain_id))
    label = re.sub(r"\s+Knowledge Graph$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+Authority Tree$", "", label, flags=re.IGNORECASE)
    return label


def _tree_text(item: dict, key: str, fallback: str = "") -> str:
    value = item.get(key)
    if value in (None, ""):
        return fallback
    return str(value)


def _coerce_domain_tree(payload: dict | list, domain_id: str) -> dict:
    domain_id = normalize_domain_id(domain_id)
    if isinstance(payload, list):
        modules = payload
        tree: dict = {}
    elif isinstance(payload, dict):
        modules = payload.get("modules") or payload.get("tree") or payload.get("authority_tree") or []
        tree = dict(payload)
    else:
        raise TypeError("Domain tree must be a JSON object or list of modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("Domain tree must contain a non-empty modules list")
    label_en = str(tree.get("label_en") or tree.get("label") or default_domain_label(domain_id))
    summary_en = str(
        tree.get("summary_en")
        or tree.get("summary")
        or f"Authority tree for {label_en}."
    )
    return {
        "id": str(tree.get("id") or f"authority_tree:hk_{domain_id}_law"),
        "domain_id": domain_id,
        "label_en": label_en,
        "label_zh": str(tree.get("label_zh") or ""),
        "summary_en": summary_en,
        "summary_zh": str(tree.get("summary_zh") or ""),
        "modules": modules,
    }


def _generate_domain_tree(domain_id: str, output_path: Path) -> dict:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise FileNotFoundError(
            f"No domain tree found for '{domain_id}'. Provide --tree or set DEEPSEEK_API_KEY "
            f"to generate {output_path}."
        )
    domain_label = default_domain_label(domain_id)
    prompt = DOMAIN_TREE_PROMPTS.get(domain_id) or (
        "Create a concise Hong Kong legal authority tree as strict JSON. "
        "Return an object with label_en, label_zh, summary_en, summary_zh, and modules. "
        "Each module must have id, label_en, label_zh, summary_en, summary_zh, and subgrounds. "
        "Each subground must have id, label_en, label_zh, summary_en, summary_zh, topics, and children. "
        "Each topic must have id, label_en, label_zh, and 2-4 HKLII-oriented search_queries. "
        f"The legal domain is {domain_label}. Keep it practical and suitable for HKLII case discovery."
    )
    request_payload = {
        "model": os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": "You return only valid JSON, with no markdown fences."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": int(os.environ.get("DEEPSEEK_MAX_TOKENS", "8192")),
    }
    request = urllib.request.Request(
        DEEPSEEK_API_ENDPOINT,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    def _post(context=None):
        kwargs = {"timeout": 90}
        if context is not None:
            kwargs["context"] = context
        with urllib.request.urlopen(request, **kwargs) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        try:
            response_payload = _post()
        except urllib.error.URLError as exc:
            if not isinstance(getattr(exc, "reason", None), ssl.SSLError):
                raise
            response_payload = _post(ssl._create_unverified_context())
    except (urllib.error.URLError, http.client.HTTPException) as exc:
        raise RuntimeError(f"DeepSeek domain tree generation failed for '{domain_id}': {exc}") from exc
    content = response_payload["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        tree = _coerce_domain_tree(json.loads(content), domain_id)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DeepSeek returned invalid JSON for generated '{domain_id}' tree") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    return tree


def load_domain_tree(domain_id: str, tree_path: str | Path | None = None, *, allow_generate: bool = True) -> dict:
    domain_id = normalize_domain_id(domain_id)
    tree_path = tree_path or None
    if domain_id == "criminal" and tree_path is None:
        return {
            "id": "authority_tree:hk_criminal_law",
            "domain_id": "criminal",
            "label_en": "Hong Kong Criminal Law Knowledge Graph",
            "label_zh": "香港刑法知識圖譜",
            "summary_en": "Criminal-law authority tree spanning general principles, substantive offences, defences, evidence, procedure, appeals, and sentencing.",
            "summary_zh": "涵蓋總則、實體罪行、抗辯、證據、程序、上訴及量刑的刑法權威樹。",
            "modules": CRIMINAL_AUTHORITY_TREE,
        }

    path = Path(tree_path).expanduser() if tree_path else DOMAIN_TREE_DIR / f"{domain_id}_tree.json"
    if path.exists():
        return _coerce_domain_tree(json.loads(path.read_text(encoding="utf-8")), domain_id)
    if allow_generate:
        return _generate_domain_tree(domain_id, path)
    raise FileNotFoundError(f"No domain tree found for '{domain_id}' at {path}")


def iter_domain_topics(tree: dict) -> list[dict]:
    topics: list[dict] = []
    for module in tree["modules"]:
        module_id = _tree_text(module, "id", slugify(_tree_text(module, "label_en", "module")))
        module_label_en = _tree_text(module, "label_en", module_id.replace("_", " ").title())
        module_label_zh = _tree_text(module, "label_zh")
        for subground in module.get("subgrounds", []):
            subground_id = _tree_text(subground, "id", slugify(_tree_text(subground, "label_en", "subground")))
            subground_label_en = _tree_text(subground, "label_en", subground_id.replace("_", " ").title())
            subground_label_zh = _tree_text(subground, "label_zh")
            summary_en = _tree_text(subground, "summary_en", _tree_text(subground, "summary", module.get("summary_en", "")))
            summary_zh = _tree_text(subground, "summary_zh")
            for topic in subground.get("topics", []):
                topic_id = _tree_text(topic, "id", slugify(_tree_text(topic, "label_en", "topic")))
                topics.append(
                    {
                        **topic,
                        "id": topic_id,
                        "label_en": _tree_text(topic, "label_en", topic_id.replace("_", " ").title()),
                        "label_zh": _tree_text(topic, "label_zh"),
                        "module_id": module_id,
                        "module_label_en": module_label_en,
                        "module_label_zh": module_label_zh,
                        "subground_id": subground_id,
                        "subground_label_en": subground_label_en,
                        "subground_label_zh": subground_label_zh,
                        "summary_en": summary_en,
                        "summary_zh": summary_zh,
                    }
                )
    return topics


_CAP_NUMBER_RE = re.compile(r"Cap\.?\s*(\d+)", re.IGNORECASE)


def _hklii_legislation_url(label: str) -> str:
    """Build an HKLII legislation URL from a statute label like 'Theft Ordinance (Cap. 210)'."""
    match = _CAP_NUMBER_RE.search(label)
    if match:
        return f"https://www.hklii.hk/en/legis/ord/{match.group(1)}"
    return ""


def _normalize_statute_label(label: str) -> str:
    """Remove noisy trailing text and normalize a statute label to 'Name (Cap. NNN)' form."""
    match = _CAP_NUMBER_RE.search(label)
    if not match:
        return label.strip()
    cap_num = match.group(1)
    # Try to extract ordinance name before Cap reference
    name_match = re.match(r"(.+?)\s*\(?\s*Cap\.?\s*\d+\s*\)?", label, re.IGNORECASE)
    ordinance_name = name_match.group(1).strip().rstrip("(") if name_match else label[:label.find("Cap")].strip().rstrip("(")
    if ordinance_name:
        return f"{ordinance_name} (Cap. {cap_num})"
    return f"Cap. {cap_num}"


CURATED_CASE_OVERRIDES = {
    _normalize_label("[2022] HKDC 1083"): {
        "canonical_label": "HKSAR v. ALI MUMTAZ",
        "public_path": "/en/cases/hkdc/2022/1083",
    },
    _normalize_label("HKSAR v Ali Mumtaz"): {
        "canonical_label": "HKSAR v. ALI MUMTAZ",
        "public_path": "/en/cases/hkdc/2022/1083",
    },
    _normalize_label("HKSAR v Shum Wai Kee"): {
        "canonical_label": "HKSAR v. SHUM WAI KEE",
        "public_path": "/en/cases/hkcfa/2019/2",
    },
    _normalize_label("HKSAR v Kanjanapas Chong Kwong Derek & Ors"): {
        "canonical_label": "HKSAR v. KANJANAPAS CHONG KWONG DEREK AND OTHERS",
        "public_path": "/en/cases/hkca/2009/46",
    },
    _normalize_label("Po Koon-tai & Ors v R"): {
        "canonical_label": "PO KOON TAI AND OTHERS v. THE QUEEN",
        "public_path": "/en/cases/hkca/1980/214",
    },
    _normalize_label("HKSAR v Chan Kam Shing"): {
        "canonical_label": "HKSAR v. CHAN KAM SHING",
        "public_path": "/en/cases/hkcfa/2016/87",
    },
    _normalize_label("HKSAR v Sze Kwan Lung"): {
        "canonical_label": "SZE KWAN LUNG AND OTHERS v. HKSAR",
        "public_path": "/en/cases/hkcfa/2004/85",
    },
    _normalize_label("HKSAR v Chan Sung Wing"): {
        "canonical_label": "HKSAR v. CHAN SUNG WING",
        "public_path": "/en/cases/hkca/2007/509",
    },
    _normalize_label("HKSAR v Lo Kwong Yin"): {
        "canonical_label": "LO KWONG YIN v. HKSAR",
        "public_path": "/en/cases/hkcfa/2010/21",
    },
    _normalize_label("Lo Kwong Yin v HKSAR"): {
        "canonical_label": "LO KWONG YIN v. HKSAR",
        "public_path": "/en/cases/hkcfa/2010/21",
    },
    _normalize_label("Sin Kam Wah & Anor v HKSAR"): {
        "canonical_label": "SIN KAM WAH LAM CHUEN IP AND ANOTHER v. HKSAR",
        "public_path": "/en/cases/hkcfa/2005/29",
    },
    _normalize_label("Sin Kam Wah & Anor v. HKSAR"): {
        "canonical_label": "SIN KAM WAH LAM CHUEN IP AND ANOTHER v. HKSAR",
        "public_path": "/en/cases/hkcfa/2005/29",
    },
    _normalize_label("HKSAR v Arthur John Paymer & Anor"): {
        "canonical_label": "HKSAR v. ARTHUR JOHN PAYMER AND ANOTHER",
        "public_path": "/en/cases/hkca/2004/39",
    },
}


def _clean_case_candidate(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip(" ,.;:")
    compact = LEADING_CASE_PREFIX_RE.sub("", compact).strip(" ,.;:")
    matches = CASE_NAME_CORE_RE.findall(compact)
    if matches:
        compact = matches[-1].strip(" ,.;:")
    if len(compact) > 140 or len(compact.split()) > 18:
        return ""
    override = CURATED_CASE_OVERRIDES.get(_normalize_label(compact))
    if override:
        return str(override["canonical_label"])
    return compact


def _excerpt(text: str, limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _score_topic(text: str, topic: dict) -> float:
    text_tokens = set(tokenize(text))
    topic_tokens = topic["token_set"]
    if not text_tokens or not topic_tokens:
        return 0.0
    overlap = len(text_tokens & topic_tokens)
    if not overlap:
        return 0.0
    score = overlap / max(math.sqrt(len(text_tokens) * len(topic_tokens)), 1)
    if topic["label_en"].lower() in text.lower():
        score += 0.5
    return score


def _topic_catalog(tree: dict) -> list[dict]:
    topics: list[dict] = []
    for index, topic in enumerate(iter_domain_topics(tree), start=1):
        topic_id = f"topic:{topic['module_id']}:{index:02d}:{slugify(topic['label_en'])[:40]}"
        domain_id = f"domain:{slugify(topic['module_id'])}"
        topics.append(
            {
                **topic,
                "topic_id": topic_id,
                "domain_id": domain_id,
                "token_set": set(
                    tokenize(
                        " ".join(
                            [
                                topic["label_en"],
                                topic["summary_en"],
                                topic["module_label_en"],
                                topic["subground_label_en"],
                                " ".join(topic.get("search_queries", [])),
                            ]
                        )
                    )
                ),
            }
        )
    return topics


def _match_topic_ids(text: str, topics: list[dict], seed_ids: set[str] | None = None, threshold: float = 0.14) -> list[str]:
    scored = [
        (topic["topic_id"], _score_topic(text, topic))
        for topic in topics
    ]
    ranked = [topic_id for topic_id, score in sorted(scored, key=lambda item: item[1], reverse=True) if score >= threshold]
    selected = list(dict.fromkeys([*(seed_ids or set()), *ranked[:4]]))
    return selected


def _candidate_public_path(candidate: dict) -> str:
    source_url = str(candidate.get("source_url") or candidate.get("public_url") or "").strip()
    if not source_url:
        return ""
    if source_url.startswith("http://") or source_url.startswith("https://"):
        source_url = urllib_parse.urlparse(source_url).path
    if source_url.startswith("/") and "/cases/" in source_url:
        return source_url
    return ""


def _load_candidate_registry(candidates_path: str | Path | None, domain_id: str) -> list[dict]:
    if not candidates_path:
        return []
    path = Path(candidates_path).expanduser()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        return []

    retained: list[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if not _candidate_public_path(candidate):
            continue
        classification = candidate.get("domain_classification") or {}
        if classification.get("domain") and not classification_matches_target(classification, domain_id):
            continue
        retained.append(candidate)
    return retained


def _candidate_topic_ids(candidate: dict, topic_catalog: list[dict], domain_id: str) -> set[str]:
    by_id: defaultdict[str, list[str]] = defaultdict(list)
    by_label: defaultdict[str, list[str]] = defaultdict(list)
    for topic in topic_catalog:
        by_id[str(topic.get("id") or "")].append(topic["topic_id"])
        by_label[_normalize_label(str(topic.get("label_en") or ""))].append(topic["topic_id"])

    topic_ids: set[str] = set()
    raw_topic_ids = [str(candidate.get("topic_id") or "")]
    for ref in candidate.get("cross_references", []) or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("domain") and not classification_matches_target({"domain": ref.get("domain")}, domain_id):
            continue
        raw_topic_ids.append(str(ref.get("topic_id") or ""))

    for raw_topic_id in raw_topic_ids:
        topic_ids.update(by_id.get(raw_topic_id, []))

    if not topic_ids:
        topic_label = _normalize_label(str(candidate.get("topic_label") or ""))
        topic_ids.update(by_label.get(topic_label, []))

    if not topic_ids:
        text_parts: list[str] = []
        for principle in candidate.get("principles", [])[:3]:
            if not isinstance(principle, dict):
                continue
            text_parts.extend(
                str(part)
                for part in (
                    principle.get("principle_label", ""),
                    principle.get("label_en", ""),
                    principle.get("paraphrase_en", ""),
                    principle.get("statement_en", ""),
                )
                if part
            )
        text = " ".join(text_parts)
        topic_ids.update(_match_topic_ids(text, topic_catalog))
    return topic_ids


def _candidate_principles(candidate: dict, fallback_label: str = "Key holding") -> list[dict]:
    principles: list[dict] = []
    for principle in candidate.get("principles", [])[:5]:
        if not isinstance(principle, dict):
            continue
        label = str(principle.get("principle_label") or principle.get("label_en") or fallback_label)
        statement = str(
            principle.get("statement_en")
            or principle.get("paraphrase_en")
            or principle.get("public_excerpt")
            or ""
        )
        if not statement:
            continue
        principles.append(
            {
                "paragraph_span": str(principle.get("paragraph_span") or ""),
                "label_en": label,
                "label_zh": str(principle.get("label_zh") or ""),
                "statement_en": _excerpt(statement, limit=420),
                "statement_zh": str(principle.get("statement_zh") or ""),
            }
        )
    return principles


def _seed_candidate_search_hits(
    search_hits: dict[str, dict],
    candidate_registry: list[dict],
    topic_catalog: list[dict],
    domain_id: str,
) -> set[str]:
    candidate_paths: set[str] = set()
    for candidate in candidate_registry:
        path = _candidate_public_path(candidate)
        topic_ids = _candidate_topic_ids(candidate, topic_catalog, domain_id)
        if not path or not topic_ids:
            continue
        candidate_paths.add(path)
        entry = search_hits.setdefault(
            path,
            {
                "result": HKLIISearchResult(
                    title=str(candidate.get("case_name") or path),
                    subtitle=str(candidate.get("court_code") or ""),
                    path=path,
                    db=str(candidate.get("court_code") or "Hong Kong courts"),
                ),
                "topic_ids": set(),
                "queries": set(),
                "candidates": [],
            },
        )
        entry["topic_ids"].update(topic_ids)
        entry["queries"].add("candidate_registry")
        entry.setdefault("candidates", []).append(candidate)
    return candidate_paths


def _build_case_summary(case_doc: HKLIICaseDocument, topic_labels: list[str]) -> str:
    lead_paragraphs = [paragraph.text for paragraph in case_doc.paragraphs[:3] if paragraph.text]
    summary = " ".join(lead_paragraphs)
    if not summary:
        summary = case_doc.title or case_doc.case_name
    if topic_labels:
        summary = f"{summary} Topics: {', '.join(topic_labels[:3])}."
    return _excerpt(summary, limit=560)


def _build_case_principles(case_doc: HKLIICaseDocument, topic_labels: list[str]) -> list[dict]:
    principles: list[dict] = []
    label = topic_labels[0] if topic_labels else "Key holding"
    for paragraph in case_doc.paragraphs[:3]:
        if len(paragraph.text) < 80:
            continue
        principles.append(
            {
                "paragraph_span": paragraph.paragraph_span,
                "label_en": label,
                "label_zh": "",
                "statement_en": _excerpt(paragraph.text, limit=420),
                "statement_zh": "",
            }
        )
        if len(principles) >= 3:
            break
    return principles


def _reference_payload(source_id: str, source_label: str, source_kind: str, location: str, snippet: str) -> dict:
    return {
        "source_id": source_id,
        "source_label": source_label,
        "source_kind": source_kind,
        "location": location,
        "snippet": _excerpt(snippet, limit=320),
    }


def _load_source_document_with_timeout(source_path: str | Path, timeout_seconds: int = SOURCE_LOAD_TIMEOUT_SECONDS):
    if timeout_seconds <= 0 or not hasattr(signal, "SIGALRM"):
        return load_source_document(source_path)

    def _timeout_handler(signum, frame):  # pragma: no cover - signal timing is environment-dependent.
        raise TimeoutError(f"Timed out loading source after {timeout_seconds} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        return load_source_document(source_path)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _render_monitor_dashboard(title: str, progress: dict, report: dict | None = None) -> str:
    percent = int(round(float(progress.get("percent", 0.0))))
    stage = escape(str(progress.get("stage", "pending")).replace("_", " ").title())
    message = escape(str(progress.get("message", "Preparing domain graph build.")))
    updated_at = escape(str(progress.get("updated_at", "")))
    status = escape(str(progress.get("status", "running")).title())
    stats = progress.get("stats", {}) or {}
    warnings = list(progress.get("warnings", []) or [])
    storage = (report or {}).get("storage", {}) or {}
    low_coverage = len((report or {}).get("low_coverage_topics", []) or [])
    uncovered = len((report or {}).get("uncovered_topics", []) or [])
    case_count = (report or {}).get("case_count", stats.get("case_count", 0))
    topic_count = (report or {}).get("topic_count", stats.get("topic_count", 0))
    refresh_seconds = int(progress.get("refresh_seconds", MONITOR_REFRESH_SECONDS))
    stats_markup = "".join(
        f"<li><strong>{escape(str(key).replace('_', ' ').title())}:</strong> {escape(str(value))}</li>"
        for key, value in stats.items()
    )
    warnings_markup = "".join(f"<li>{escape(str(item))}</li>" for item in warnings[-12:]) or "<li>No warnings recorded.</li>"
    next_actions = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in ((report or {}).get("next_actions", []) or [])
    ) or "<li>Build still in progress.</li>"
    summary_markup = ""
    if report:
        summary_markup = f"""
        <section class="panel">
          <h2>Coverage Summary</h2>
          <ul class="metric-list">
            <li><strong>Cases:</strong> {escape(str(case_count))}</li>
            <li><strong>Topics:</strong> {escape(str(topic_count))}</li>
            <li><strong>Uncovered topics:</strong> {escape(str(uncovered))}</li>
            <li><strong>Low-coverage topics:</strong> {escape(str(low_coverage))}</li>
            <li><strong>Embedding backend:</strong> {escape(str(storage.get('embedding_backend', {}).get('backend', 'n/a')))}</li>
            <li><strong>Embedding records:</strong> {escape(str(storage.get('embedding_record_count', 0)))}</li>
          </ul>
        </section>
        """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{refresh_seconds}">
  <title>{escape(title)} Monitor</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #10151d;
      --panel: rgba(15, 23, 42, 0.82);
      --line: rgba(148, 163, 184, 0.25);
      --text: #e5eef7;
      --muted: #9fb0c6;
      --accent: #f97316;
      --accent-soft: rgba(249, 115, 22, 0.18);
      --ok: #34d399;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      background:
        radial-gradient(circle at top left, rgba(249, 115, 22, 0.14), transparent 32%),
        radial-gradient(circle at bottom right, rgba(52, 211, 153, 0.1), transparent 28%),
        var(--bg);
      color: var(--text);
    }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: var(--muted); line-height: 1.55; }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      backdrop-filter: blur(10px);
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.22);
    }}
    .hero {{ margin-bottom: 18px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
    }}
    .status-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 14px 0 18px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(148, 163, 184, 0.08);
      border: 1px solid var(--line);
    }}
    .progress-track {{
      width: 100%;
      height: 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      overflow: hidden;
      border: 1px solid var(--line);
    }}
    .progress-bar {{
      height: 100%;
      width: {percent}%;
      background: linear-gradient(90deg, var(--accent), #fb923c, var(--ok));
    }}
    .metric-list, .warning-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}
    .metric-list li, .warning-list li {{
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(15, 23, 42, 0.55);
      border: 1px solid rgba(148, 163, 184, 0.14);
    }}
    .summary-number {{
      font-size: 2.2rem;
      color: var(--accent);
      margin: 6px 0 0;
    }}
    code {{
      color: #fdba74;
      background: rgba(15, 23, 42, 0.8);
      padding: 2px 6px;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{escape(title)}</h1>
      <p>This monitor refreshes every {refresh_seconds // 60} minutes so you can leave it open while the domain graph build continues.</p>
      <div class="status-row">
        <span class="pill"><strong>Status</strong> {status}</span>
        <span class="pill"><strong>Stage</strong> {stage}</span>
        <span class="pill"><strong>Updated</strong> {updated_at}</span>
      </div>
      <p>{message}</p>
      <div class="progress-track"><div class="progress-bar"></div></div>
      <p class="summary-number">{percent}%</p>
    </section>
    <section class="grid">
      <section class="panel">
        <h2>Live Build Stats</h2>
        <ul class="metric-list">{stats_markup or "<li>No stage statistics recorded yet.</li>"}</ul>
      </section>
      {summary_markup or '<section class="panel"><h2>Coverage Summary</h2><p>Final monitor coverage appears here once the build completes.</p></section>'}
    </section>
    <section class="grid" style="margin-top: 18px;">
      <section class="panel">
        <h2>Warnings</h2>
        <ul class="warning-list">{warnings_markup}</ul>
      </section>
      <section class="panel">
        <h2>Next Actions</h2>
        <ul class="warning-list">{next_actions}</ul>
      </section>
    </section>
  </main>
</body>
</html>
"""


def _write_monitor_surface(output_dir: Path, title: str, progress: dict, report: dict | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "build_progress.json", progress)
    (output_dir / "monitor_report.html").write_text(
        _render_monitor_dashboard(title, progress, report=report),
        encoding="utf-8",
    )


def _write_relationship_payload(payload: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = output_dir / "relationship_graph.json"
    map_path = output_dir / "relationship_map.html"
    tree_path = output_dir / "relationship_tree.html"
    manifest_path = output_dir / "manifest.json"
    graph_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    map_path.write_text(render_relationship_map(payload), encoding="utf-8")
    tree_path.write_text(render_relationship_family_tree(payload), encoding="utf-8")
    manifest_path.write_text(json.dumps(payload["meta"], indent=2, ensure_ascii=False), encoding="utf-8")
    return payload["meta"]


def _storage_exports(
    payload: dict,
    bundle: dict | None,
    output_dir: Path,
    *,
    domain_id: str,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
) -> dict:
    backend = create_embedding_backend(
        backend=embedding_backend,
        model=embedding_model,
        dimensions=embedding_dimensions,
    )
    records: list[dict] = []
    documents: list[str] = []
    metadata_records: list[dict] = []
    for node in payload["nodes"]:
        if node["type"] not in {"topic", "case", "statute"}:
            continue
        if node["type"] == "topic":
            text = f"{node['label']} {node.get('summary', '')}"
        else:
            text = f"{node['label']} {node.get('summary_en', node.get('summary', ''))}"
        documents.append(text.strip())
        metadata_records.append(
            {
                "id": node["id"],
                "document": text.strip(),
                "metadata": {
                    "type": node["type"],
                    "label": node["label"],
                    "keywords": node.get("keywords", []),
                },
            }
        )
    embeddings = backend.embed_documents(documents)
    for record, embedding in zip(metadata_records, embeddings, strict=True):
        records.append({**record, "embedding": embedding})
    embeddings_path = output_dir / "embedding_records.json"
    chroma_path = output_dir / "chroma_records.json"
    embeddings_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    chroma_path.write_text(
        json.dumps(
            {
                "collection": f"hk_{normalize_domain_id(domain_id)}_cases",
                "embedding_backend": backend.manifest(),
                "records": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sql_lines = [
        "create table if not exists casemap_documents (",
        "  id text primary key,",
        "  kind text not null,",
        "  label text not null,",
        "  document_text text not null,",
        "  metadata jsonb not null default '{}'::jsonb",
        ");",
        "",
        "create table if not exists casemap_embeddings (",
        "  document_id text primary key references casemap_documents(id) on delete cascade,",
        "  embedding jsonb not null",
        ");",
        "",
    ]
    for record in records:
        metadata_sql = json.dumps(record["metadata"], ensure_ascii=False).replace("'", "''")
        document_sql = record["document"].replace("'", "''")
        label_sql = record["metadata"]["label"].replace("'", "''")
        embedding_sql = json.dumps(record["embedding"]).replace("'", "''")
        sql_lines.append(
            "insert into casemap_documents (id, kind, label, document_text, metadata) values "
            f"('{record['id']}', '{record['metadata']['type']}', '{label_sql}', '{document_sql}', '{metadata_sql}'::jsonb) "
            "on conflict (id) do update set kind = excluded.kind, label = excluded.label, document_text = excluded.document_text, metadata = excluded.metadata;"
        )
        sql_lines.append(
            "insert into casemap_embeddings (document_id, embedding) values "
            f"('{record['id']}', '{embedding_sql}'::jsonb) "
            "on conflict (document_id) do update set embedding = excluded.embedding;"
        )
    supabase_path = output_dir / "supabase_export.sql"
    supabase_path.write_text("\n".join(sql_lines), encoding="utf-8")

    return {
        "embedding_record_count": len(records),
        "embedding_dimensions": backend.dimensions,
        "embedding_backend": backend.manifest(),
        "chroma_export": str(chroma_path),
        "supabase_export": str(supabase_path),
        "hybrid_bundle_written": bool(bundle),
    }


def _monitor_report(
    payload: dict,
    topic_catalog: list[dict],
    output_dir: Path,
    crawler_warnings: list[str],
    storage_status: dict,
    *,
    domain_label: str,
) -> dict:
    topic_case_counts: Counter[str] = Counter()
    for edge in payload["edges"]:
        if edge["type"] == "discusses_case":
            topic_case_counts[edge["source"]] += 1
    uncovered_topics = [
        {
            "topic_id": topic["topic_id"],
            "label_en": topic["label_en"],
            "label_zh": topic["label_zh"],
            "search_queries": topic.get("search_queries", []),
        }
        for topic in topic_catalog
        if topic_case_counts[topic["topic_id"]] == 0
    ]
    low_coverage_topics = [
        {
            "topic_id": topic["topic_id"],
            "label_en": topic["label_en"],
            "case_count": topic_case_counts[topic["topic_id"]],
        }
        for topic in topic_catalog
        if 0 < topic_case_counts[topic["topic_id"]] < 3
    ]
    case_nodes = [node for node in payload["nodes"] if node["type"] == "case"]
    missing_principles = [node["label"] for node in case_nodes if not node.get("principles")]
    report = {
        "title": payload["meta"]["title"],
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(case_nodes),
        "topic_count": len(topic_catalog),
        "uncovered_topics": uncovered_topics,
        "low_coverage_topics": low_coverage_topics,
        "cases_missing_principles": missing_principles[:30],
        "warnings": crawler_warnings,
        "storage": storage_status,
        "next_actions": [
            f"Run a second HKLII crawl on the uncovered {domain_label} topics using more specific doctrine queries.",
            "Feed uncovered topics into NotebookLM or a DeepSeek/OpenRouter enrichment pass if an MCP or API becomes available.",
            f"Review the low-coverage topics before promoting this graph as a full-production {domain_label} map.",
        ],
    }
    _write_json(output_dir / "monitor_report.json", report)
    return report


def _authority_tree_payload(payload_nodes: list[dict], payload_edges: list[dict], topic_catalog: list[dict], tree: dict) -> dict:
    node_lookup = {node["id"]: node for node in payload_nodes}
    incoming: defaultdict[str, list[dict]] = defaultdict(list)
    outgoing: defaultdict[str, list[dict]] = defaultdict(list)
    for edge in payload_edges:
        incoming[edge["target"]].append(edge)
        outgoing[edge["source"]].append(edge)

    topic_ids_by_subground: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    case_ids_by_subground: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    statute_ids_by_subground: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    source_ids_by_subground: defaultdict[tuple[str, str], set[str]] = defaultdict(set)

    topic_by_id = {topic["topic_id"]: topic for topic in topic_catalog}
    for topic in topic_catalog:
        topic_ids_by_subground[(topic["module_id"], topic["subground_id"])].append(topic["topic_id"])
        for edge in outgoing[topic["topic_id"]]:
            if edge["type"] == "discusses_case":
                case_ids_by_subground[(topic["module_id"], topic["subground_id"])].add(edge["target"])
            elif edge["type"] == "discusses_statute":
                statute_ids_by_subground[(topic["module_id"], topic["subground_id"])].add(edge["target"])
        for edge in incoming[topic["topic_id"]]:
            if edge["type"] == "covers_topic":
                source_ids_by_subground[(topic["module_id"], topic["subground_id"])].add(edge["source"])

    modules: list[dict] = []
    for module in tree["modules"]:
        subgrounds: list[dict] = []
        module_case_ids: set[str] = set()
        module_statute_ids: set[str] = set()
        module_source_ids: set[str] = set()
        module_id = _tree_text(module, "id", slugify(_tree_text(module, "label_en", "module")))
        module_label_en = _tree_text(module, "label_en", module_id.replace("_", " ").title())
        module_label_zh = _tree_text(module, "label_zh")
        module_summary_en = _tree_text(module, "summary_en", _tree_text(module, "summary"))
        module_summary_zh = _tree_text(module, "summary_zh")
        for subground in module.get("subgrounds", []):
            subground_id = _tree_text(subground, "id", slugify(_tree_text(subground, "label_en", "subground")))
            subground_label_en = _tree_text(subground, "label_en", subground_id.replace("_", " ").title())
            subground_label_zh = _tree_text(subground, "label_zh")
            subground_summary_en = _tree_text(subground, "summary_en", _tree_text(subground, "summary", module_summary_en))
            subground_summary_zh = _tree_text(subground, "summary_zh")
            key = (module_id, subground_id)
            topic_ids = topic_ids_by_subground[key]
            case_ids = case_ids_by_subground[key]
            statute_ids = statute_ids_by_subground[key]
            source_ids = source_ids_by_subground[key]
            module_case_ids.update(case_ids)
            module_statute_ids.update(statute_ids)
            module_source_ids.update(source_ids)
            subgrounds.append(
                {
                    "id": f"subground:{module_id}:{subground_id}",
                    "module_id": f"module:{module_id}",
                    "slug": subground_id,
                    "type": "subground",
                    "label_en": subground_label_en,
                    "label_zh": subground_label_zh,
                    "label": f"{subground_label_en} / {subground_label_zh}" if subground_label_zh else subground_label_en,
                    "secondary_label": subground_label_zh,
                    "summary_en": subground_summary_en,
                    "summary_zh": subground_summary_zh,
                    "summary": subground_summary_en,
                    "children": list(subground.get("children", [])),
                    "topic_ids": topic_ids,
                    "topic_labels": [topic_by_id[topic_id]["label_en"] for topic_id in topic_ids],
                    "lineage_ids": [],
                    "lineage_titles": [],
                    "case_ids": sorted(case_ids, key=lambda case_id: node_lookup[case_id]["label"]),
                    "statute_ids": sorted(statute_ids, key=lambda statute_id: node_lookup[statute_id]["label"]),
                    "source_ids": sorted(source_ids, key=lambda source_id: node_lookup[source_id]["label"]),
                    "metrics": {
                        "topics": len(topic_ids),
                        "cases": len(case_ids),
                        "statutes": len(statute_ids),
                        "sources": len(source_ids),
                        "lineages": 0,
                    },
                    "coverage": "mapped" if case_ids or statute_ids else "placeholder",
                }
            )
        modules.append(
            {
                "id": f"module:{module_id}",
                "slug": module_id,
                "type": "module",
                "label_en": module_label_en,
                "label_zh": module_label_zh,
                "label": f"{module_label_en} / {module_label_zh}" if module_label_zh else module_label_en,
                "secondary_label": module_label_zh,
                "summary_en": module_summary_en,
                "summary_zh": module_summary_zh,
                "summary": module_summary_en,
                "subgrounds": subgrounds,
                "metrics": {
                    "subgrounds": len(subgrounds),
                    "topics": sum(len(item["topic_ids"]) for item in subgrounds),
                    "cases": len(module_case_ids),
                    "statutes": len(module_statute_ids),
                    "sources": len(module_source_ids),
                    "lineages": 0,
                },
            }
        )
    return {
        "id": tree["id"],
        "label_en": tree["label_en"],
        "label_zh": tree["label_zh"],
        "summary_en": tree["summary_en"],
        "summary_zh": tree["summary_zh"],
        "modules": modules,
    }


def build_domain_relationship_payload(
    domain_id: str,
    tree: dict,
    source_paths: list[str | Path],
    title: str | None = None,
    per_query_limit: int = 8,
    max_cases: int = 400,
    max_textbook_case_fetches: int = 80,
    candidate_registry: list[dict] | None = None,
    progress_callback=None,
) -> tuple[dict, list[dict], list[SourceDocument], list[Passage], list[HKLIICaseDocument], list[str]]:
    domain_id = normalize_domain_id(domain_id)
    tree = _coerce_domain_tree(tree, domain_id)
    domain_label = _domain_display_label(tree, domain_id)
    title = title or f"{domain_label} Relationship Graph"
    topic_catalog = _topic_catalog(tree)
    crawler = HKLIICrawler()
    total_seed_queries = sum(len(topic.get("search_queries", [])) for topic in topic_catalog)
    if progress_callback:
        progress_callback(
            "searching_hklii",
            f"Running seeded HKLII searches across the {domain_label} topic catalog.",
            topic_count=len(topic_catalog),
            seed_query_count=total_seed_queries,
        )

    search_hits: dict[str, dict] = {}
    candidate_paths = _seed_candidate_search_hits(
        search_hits,
        candidate_registry or [],
        topic_catalog,
        domain_id,
    )
    for topic_index, topic in enumerate(topic_catalog, start=1):
        for query in topic.get("search_queries", []):
            for result in crawler.simple_search(query, limit=per_query_limit):
                entry = search_hits.setdefault(
                    result.path,
                    {
                        "result": result,
                        "topic_ids": set(),
                        "queries": set(),
                        "candidates": [],
                    },
                )
                entry["topic_ids"].add(topic["topic_id"])
                entry["queries"].add(query)
        if progress_callback and (topic_index == len(topic_catalog) or topic_index % 5 == 0):
            progress_callback(
                "searching_hklii",
                f"Processed seeded HKLII searches for {topic_index} of {len(topic_catalog)} topics.",
                topics_processed=topic_index,
                topic_count=len(topic_catalog),
                search_hit_count=len(search_hits),
                warning_count=len(crawler.warnings),
            )

    ranked_paths = sorted(
        search_hits,
        key=lambda path: (
            path in candidate_paths,
            len(search_hits[path]["topic_ids"]),
            len(search_hits[path]["queries"]),
            path,
        ),
        reverse=True,
    )[:max_cases]
    if progress_callback:
        progress_callback(
            "fetching_primary_cases",
            f"Fetching {len(ranked_paths)} HKLII judgments selected from seeded search hits.",
            search_hit_count=len(search_hits),
            ranked_case_paths=len(ranked_paths),
            warning_count=len(crawler.warnings),
        )
    case_documents = crawler.crawl_paths(ranked_paths)

    supplemental_sources: list[SourceDocument] = [
        SourceDocument(source_id=HKLII_SOURCE_ID, label=HKLII_SOURCE_LABEL, path="https://www.hklii.hk/api", kind="api")
    ]
    supplemental_passages: list[Passage] = []
    if progress_callback:
        progress_callback(
            "loading_textbooks",
            f"Loading {len(source_paths)} local textbook or note sources for supplemental coverage.",
            source_path_count=len(source_paths),
            fetched_case_count=len(case_documents),
            warning_count=len(crawler.warnings),
        )
    for source_index, source_path in enumerate(source_paths, start=1):
        try:
            source, passages = _load_source_document_with_timeout(source_path)
        except Exception as exc:
            crawler.warnings.append(f"Failed to load source '{source_path}': {exc}")
            if progress_callback:
                progress_callback(
                    "loading_textbooks",
                    f"Skipped unreadable source {source_index} of {len(source_paths)} and continued the build.",
                    source_path_count=len(source_paths),
                    loaded_source_count=len(supplemental_sources) - 1,
                    failed_source_count=len(crawler.warnings),
                    fetched_case_count=len(case_documents),
                    warning_count=len(crawler.warnings),
                )
            continue
        supplemental_sources.append(source)
        supplemental_passages.extend(passages)
        if progress_callback:
            progress_callback(
                "loading_textbooks",
                f"Loaded source {source_index} of {len(source_paths)} for supplemental {domain_label} coverage.",
                source_path_count=len(source_paths),
                loaded_source_count=len(supplemental_sources) - 1,
                supplemental_passage_count=len(supplemental_passages),
                fetched_case_count=len(case_documents),
                warning_count=len(crawler.warnings),
            )

    nodes: list[dict] = []
    edges: list[dict] = []
    node_lookup: dict[str, dict] = {}
    edge_keys: set[tuple[str, str, str]] = set()

    def add_node(node: dict) -> dict:
        if node["id"] in node_lookup:
            existing = node_lookup[node["id"]]
            for key, value in node.items():
                if value not in ("", None, [], {}):
                    existing[key] = value
            return existing
        node_lookup[node["id"]] = node
        nodes.append(node)
        return node

    def add_edge(source: str, target: str, edge_type: str, **extra: object) -> None:
        key = (source, target, edge_type)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edge = {"source": source, "target": target, "type": edge_type, "weight": float(extra.pop("weight", 1.0))}
        edge.update(extra)
        edges.append(edge)

    add_node(
        {
            "id": HKLII_SOURCE_ID,
            "label": HKLII_SOURCE_LABEL,
            "type": "source",
            "summary": "Primary-source judgments and legislation fetched from HKLII's public API.",
            "references": [],
            "links": [{"label": "HKLII", "url": "https://www.hklii.hk"}],
            "metrics": {"kind": "api"},
        }
    )
    for source in supplemental_sources:
        if source.source_id == HKLII_SOURCE_ID:
            continue
        add_node(
            {
                "id": source.source_id,
                "label": source.label,
                "type": "source",
                "summary": f"{source.kind.upper()} textbook or note source used to fill {domain_label} topic coverage.",
                "references": [],
                "links": [],
                "metrics": {"kind": source.kind},
            }
        )

    for module in tree["modules"]:
        module_id = _tree_text(module, "id", slugify(_tree_text(module, "label_en", "module")))
        module_label_en = _tree_text(module, "label_en", module_id.replace("_", " ").title())
        module_summary_en = _tree_text(module, "summary_en", _tree_text(module, "summary"))
        add_node(
            {
                "id": f"domain:{slugify(module_id)}",
                "label": module_label_en,
                "type": "domain",
                "summary": module_summary_en,
                "references": [],
                "links": [],
                "metrics": {},
                "keywords": top_keywords(f"{module_label_en} {module_summary_en}"),
            }
        )
    for topic in topic_catalog:
        add_node(
            {
                "id": topic["topic_id"],
                "label": topic["label_en"],
                "type": "topic",
                "summary": topic["summary_en"],
                "references": [],
                "links": [],
                "metrics": {},
                "domain_id": topic["domain_id"],
                "keywords": top_keywords(f"{topic['label_en']} {topic['summary_en']}"),
            }
        )
        add_edge(topic["domain_id"], topic["topic_id"], "contains", mentions=1)

    textbook_case_mentions: defaultdict[str, list[dict]] = defaultdict(list)
    statute_mentions: defaultdict[str, list[dict]] = defaultdict(list)
    co_mentioned_cases: Counter[tuple[str, str]] = Counter()
    covered_topics_by_source: defaultdict[str, set[str]] = defaultdict(set)

    for passage in supplemental_passages:
        topic_ids = _match_topic_ids(passage.text, topic_catalog)
        if not topic_ids:
            continue
        covered_topics_by_source[passage.source_id].update(topic_ids)
        case_names = sorted(
            {
                candidate
                for candidate in (_clean_case_candidate(match.strip(" ,.;")) for match in CASE_RE.findall(passage.text))
                if candidate
            }
        )
        statutes = sorted({match.strip(" ,.;") for match in STATUTE_RE.findall(passage.text)})
        for topic_id in topic_ids:
            add_node(node_lookup[topic_id])
        for case_name in case_names:
            textbook_case_mentions[_normalize_label(case_name)].append(
                {
                    "case_name": case_name,
                    "source_id": passage.source_id,
                    "source_label": passage.source_label,
                    "source_kind": passage.source_kind,
                    "location": passage.location,
                    "snippet": passage.text,
                    "topic_ids": topic_ids,
                }
            )
        for left_index, left_case in enumerate(case_names):
            for right_case in case_names[left_index + 1 :]:
                pair = tuple(sorted((_normalize_label(left_case), _normalize_label(right_case))))
                co_mentioned_cases[pair] += 1
        for statute_label in statutes:
            statute_mentions[_normalize_label(statute_label)].append(
                {
                    "label": statute_label,
                    "source_id": passage.source_id,
                    "source_label": passage.source_label,
                    "source_kind": passage.source_kind,
                    "location": passage.location,
                    "snippet": passage.text,
                    "topic_ids": topic_ids,
                }
            )
        for statute_label in statutes:
            normalized_statute = _normalize_statute_label(statute_label)
            hklii_legis_url = _hklii_legislation_url(statute_label)
            statute_links = [{"label": "HKLII legislation", "url": hklii_legis_url}] if hklii_legis_url else []
            statute_node = add_node(
                {
                    "id": f"statute:{slugify(normalized_statute)[:80]}",
                    "label": normalized_statute,
                    "type": "statute",
                    "summary": f"Hong Kong legislation discussed in {domain_label} secondary sources.",
                    "summary_en": f"Hong Kong legislation discussed in {domain_label} secondary sources.",
                    "references": [],
                    "links": statute_links,
                    "metrics": {},
                    "keywords": top_keywords(normalized_statute),
                }
            )
            latest_references = statute_mentions[_normalize_label(statute_label)][-1:]
            for reference in latest_references:
                statute_node.setdefault("references", []).append(
                    _reference_payload(reference["source_id"], reference["source_label"], reference["source_kind"], reference["location"], reference["snippet"])
                )
            for topic_id in topic_ids:
                add_edge(topic_id, statute_node["id"], "discusses_statute", mentions=1)
                for reference in latest_references:
                    add_edge(reference["source_id"], topic_id, "covers_topic", mentions=1)

    fetched_case_labels = {_normalize_label(_clean_case_candidate(case.case_name)) for case in case_documents}
    textbook_fetch_candidates = sorted(
        textbook_case_mentions.items(),
        key=lambda item: (len(item[1]), len(item[0])),
        reverse=True,
    )
    textbook_fetch_paths: list[str] = []
    if progress_callback:
        progress_callback(
            "backfilling_textbook_cases",
            "Running a second HKLII lookup pass for textbook-only case names.",
            textbook_case_candidates=len(textbook_fetch_candidates),
            fetched_case_count=len(case_documents),
            warning_count=len(crawler.warnings),
        )

    # --- Separate curated overrides (instant, no network) from names that need search ---
    needs_search: list[tuple[str, str]] = []  # (normalized_name, candidate_label)
    for normalized_case_name, mentions in textbook_fetch_candidates:
        if normalized_case_name in fetched_case_labels:
            continue
        override = CURATED_CASE_OVERRIDES.get(normalized_case_name)
        if override and override.get("public_path"):
            textbook_fetch_paths.append(str(override["public_path"]))
            fetched_case_labels.add(normalized_case_name)
            if len(textbook_fetch_paths) >= max_textbook_case_fetches:
                break
        else:
            needs_search.append((normalized_case_name, mentions[0]["case_name"]))

    # --- Parallel batch search for remaining textbook case names ---
    # Use a higher worker count than crawl_paths (searches are lightweight HEAD-like API calls)
    _BACKFILL_SEARCH_WORKERS = max(crawler.max_workers, 12)
    remaining_budget = max(0, max_textbook_case_fetches - len(textbook_fetch_paths))
    if needs_search and remaining_budget > 0:
        # Over-query to fill budget after misses; sorted by frequency already
        batch = needs_search[:remaining_budget * 3]
        search_results: dict[str, list] = {}
        completed_count = 0

        def _search_one(item: tuple[str, str]) -> tuple[str, list]:
            norm_name, label = item
            return norm_name, crawler.simple_search(label, limit=1)

        with ThreadPoolExecutor(max_workers=_BACKFILL_SEARCH_WORKERS) as _pool:
            future_map = {_pool.submit(_search_one, item): item for item in batch}
            for future in as_completed(future_map):
                try:
                    norm_name, results = future.result()
                    search_results[norm_name] = results
                except Exception as exc:
                    crawler.warnings.append(f"Parallel textbook search failed: {exc}")
                completed_count += 1
                # Report progress every 10 completed searches so the monitor doesn't look stuck
                if progress_callback and completed_count % 10 == 0:
                    progress_callback(
                        "backfilling_textbook_cases",
                        f"Searching HKLII for textbook cases: {completed_count}/{len(batch)} searched, "
                        f"{len(textbook_fetch_paths)} paths queued so far.",
                        textbook_case_candidates=len(textbook_fetch_candidates),
                        searches_completed=completed_count,
                        searches_total=len(batch),
                        paths_queued=len(textbook_fetch_paths),
                        warning_count=len(crawler.warnings),
                    )

        # Collect results in original frequency order (batch is already ordered)
        for normalized_case_name, _label in batch:
            if len(textbook_fetch_paths) >= max_textbook_case_fetches:
                break
            if normalized_case_name in fetched_case_labels:
                continue
            results = search_results.get(normalized_case_name, [])
            if not results:
                continue
            textbook_fetch_paths.append(results[0].path)
            fetched_case_labels.add(normalized_case_name)

    if textbook_fetch_paths:
        case_documents.extend(crawler.crawl_paths(textbook_fetch_paths))
    if progress_callback:
        progress_callback(
            "assembling_graph",
            f"Merging HKLII judgments, textbook passages, statutes, and topic links into one {domain_label} payload.",
            fetched_case_count=len(case_documents),
            textbook_case_candidates=len(textbook_fetch_candidates),
            supplemental_passage_count=len(supplemental_passages),
            warning_count=len(crawler.warnings),
        )

    fetched_case_ids: dict[str, str] = {}
    for case_doc in case_documents:
        search_entry = search_hits.get(urllib_parse.urlparse(case_doc.public_url).path, {})
        seed_topic_ids = set(search_entry.get("topic_ids", set()))
        candidate_records = [
            item for item in search_entry.get("candidates", [])
            if isinstance(item, dict)
        ]
        matched_topic_ids = set(_match_topic_ids(case_doc.text, topic_catalog, seed_ids=seed_topic_ids))
        if not matched_topic_ids:
            matched_topic_ids.update(seed_topic_ids)
        if not matched_topic_ids and topic_catalog:
            matched_topic_ids.add(topic_catalog[0]["topic_id"])
        topic_labels = [node_lookup[topic_id]["label"] for topic_id in matched_topic_ids if topic_id in node_lookup]
        case_summary = _build_case_summary(case_doc, topic_labels)
        case_id = f"case:{slugify(case_doc.neutral_citation or case_doc.case_name)[:80]}"
        fetched_case_ids[_normalize_label(_clean_case_candidate(case_doc.case_name))] = case_id
        candidate_principles: list[dict] = []
        for candidate in candidate_records[:2]:
            candidate_principles.extend(_candidate_principles(candidate, topic_labels[0] if topic_labels else "Key holding"))
        candidate_domain_tags = [
            str((candidate.get("domain_classification") or {}).get("domain") or "")
            for candidate in candidate_records
        ]
        domain_tags = list(dict.fromkeys([domain_id, *[tag for tag in candidate_domain_tags if tag]]))
        candidate_classification = candidate_records[0].get("domain_classification", {}) if candidate_records else {}
        case_node = add_node(
            {
                "id": case_id,
                "label": case_doc.case_name,
                "type": "case",
                "summary": case_summary,
                "summary_en": case_summary,
                "summary_zh": "",
                "neutral_citation": case_doc.neutral_citation,
                "court_name": case_doc.court_name,
                "court_code": case_doc.court_code,
                "decision_date": case_doc.decision_date,
                "judges": case_doc.judges,
                "source_links": [{"label": "HKLII judgment", "url": case_doc.public_url}],
                "links": [{"label": "HKLII judgment", "url": case_doc.public_url}],
                "references": [
                    _reference_payload(HKLII_SOURCE_ID, HKLII_SOURCE_LABEL, "api", case_doc.neutral_citation or case_doc.public_url, case_summary)
                ],
                "keywords": top_keywords(f"{case_doc.case_name} {case_summary}"),
                "principles": candidate_principles or _build_case_principles(case_doc, topic_labels),
                "domain_classification": candidate_classification,
                "target_domain": domain_id,
                "domain_tags": domain_tags,
                "metrics": {
                    "paragraphs": len(case_doc.paragraphs),
                    "seed_topics": len(seed_topic_ids),
                    "matched_queries": len(search_entry.get("queries", set())),
                    "candidate_registry_hits": len(candidate_records),
                    "cited_cases": len(case_doc.cited_cases),
                    "cited_statutes": len(case_doc.cited_statutes),
                },
            }
        )
        for topic_id in matched_topic_ids:
            add_edge(topic_id, case_id, "discusses_case", mentions=1)
            add_edge(HKLII_SOURCE_ID, topic_id, "covers_topic", mentions=1)
        for statute in case_doc.cited_statutes:
            normalized_statute_label = _normalize_statute_label(statute.label)
            hklii_legis = _hklii_legislation_url(statute.label) or statute.url
            statute_links = [{"label": "HKLII legislation", "url": hklii_legis}] if hklii_legis else []
            statute_node = add_node(
                {
                    "id": f"statute:{slugify(normalized_statute_label)[:80]}",
                    "label": normalized_statute_label,
                    "type": "statute",
                    "summary": f"Hong Kong legislation cited in {domain_label} judgments or textbooks.",
                    "summary_en": f"Hong Kong legislation cited in {domain_label} judgments or textbooks.",
                    "references": [],
                    "links": statute_links,
                    "metrics": {},
                    "keywords": top_keywords(normalized_statute_label),
                }
            )
            statute_node.setdefault("references", []).append(
                _reference_payload(HKLII_SOURCE_ID, HKLII_SOURCE_LABEL, "api", case_doc.neutral_citation or case_doc.public_url, statute.label)
            )
            add_edge(case_id, statute_node["id"], "cites_statute", mentions=1)
            for topic_id in matched_topic_ids:
                add_edge(topic_id, statute_node["id"], "discusses_statute", mentions=1)
        for cited_case in case_doc.cited_cases[:20]:
            target_case_id = f"case:{slugify(cited_case.label)[:80]}"
            add_node(
                {
                    "id": target_case_id,
                    "label": cited_case.label,
                    "type": "case",
                    "summary": f"Authority cited inside an HKLII {domain_label} judgment.",
                    "summary_en": f"Authority cited inside an HKLII {domain_label} judgment.",
                    "summary_zh": "",
                    "neutral_citation": cited_case.label if cited_case.label.startswith("[") else "",
                    "source_links": [{"label": "HKLII / search", "url": cited_case.url}],
                    "links": [{"label": "HKLII / search", "url": cited_case.url}],
                    "references": [],
                    "keywords": top_keywords(cited_case.label),
                    "principles": [],
                    "metrics": {},
                }
            )
            add_edge(case_id, target_case_id, "cites_case", mentions=1)

    for normalized_case_name, mentions in textbook_case_mentions.items():
        if normalized_case_name in fetched_case_ids:
            case_id = fetched_case_ids[normalized_case_name]
            case_node = node_lookup[case_id]
            for mention in mentions[:3]:
                case_node.setdefault("references", []).append(
                    _reference_payload(mention["source_id"], mention["source_label"], mention["source_kind"], mention["location"], mention["snippet"])
                )
                for topic_id in mention["topic_ids"]:
                    add_edge(topic_id, case_id, "discusses_case", mentions=1)
                    add_edge(mention["source_id"], topic_id, "covers_topic", mentions=1)
            continue
        mention = mentions[0]
        case_label = _clean_case_candidate(mention["case_name"])
        override = CURATED_CASE_OVERRIDES.get(_normalize_label(case_label), {})
        case_id = f"case:{slugify(case_label)[:80]}"
        add_node(
            {
                "id": case_id,
                "label": str(override.get("canonical_label", case_label)),
                "type": "case",
                "summary": _excerpt(mention["snippet"], limit=460),
                "summary_en": _excerpt(mention["snippet"], limit=460),
                "summary_zh": "",
                "neutral_citation": "",
                "source_links": [{"label": "HKLII judgment", "url": f"https://www.hklii.hk{override['public_path']}"}] if override.get("public_path") else [],
                "links": [{"label": "HKLII judgment", "url": f"https://www.hklii.hk{override['public_path']}"}] if override.get("public_path") else [],
                "references": [
                    _reference_payload(mention["source_id"], mention["source_label"], mention["source_kind"], mention["location"], mention["snippet"])
                ],
                "keywords": top_keywords(case_label + " " + mention["snippet"]),
                "principles": [],
                "metrics": {"placeholder": True, "curated_override": bool(override)},
            }
        )
        for topic_id in mention["topic_ids"]:
            add_edge(topic_id, case_id, "discusses_case", mentions=1)
            add_edge(mention["source_id"], topic_id, "covers_topic", mentions=1)

    for (left_case, right_case), mentions in co_mentioned_cases.items():
        left_id = fetched_case_ids.get(left_case) or f"case:{slugify(left_case)[:80]}"
        right_id = fetched_case_ids.get(right_case) or f"case:{slugify(right_case)[:80]}"
        if left_id in node_lookup and right_id in node_lookup:
            add_edge(left_id, right_id, "co_mentioned", mentions=mentions, weight=min(1.0, 0.2 * mentions))

    for node in nodes:
        node.setdefault("legal_domain", domain_id)
        node.setdefault("domain_tags", [domain_id])

    payload = {
        "meta": {
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "source_documents": [
                {"label": source.label, "kind": source.kind, "path": source.path}
                for source in supplemental_sources
            ],
            "source_count": len(supplemental_sources),
            "passage_count": len(supplemental_passages) + sum(len(case.paragraphs) for case in case_documents),
            "retained_case_count": sum(1 for node in nodes if node["type"] == "case"),
            "retained_statute_count": sum(1 for node in nodes if node["type"] == "statute"),
            "public_mode": True,
            "notes": [
                f"Primary {domain_label} judgments were fetched from HKLII's public API.",
                "Supplemental textbook passages were used to improve topic coverage and backfill missing authorities.",
                "NotebookLM is optional in this build; uncovered topics are surfaced in monitor_report.json for later enrichment.",
            ],
            "lineages": [],
            "curated_lineage_count": 0,
            "lineage_codes": [],
            "viewer_heading_public": f"{domain_label} Hierarchical Knowledge Graph",
            "viewer_heading_internal": f"{domain_label} Internal Hierarchy Explorer",
            "viewer_intro_public": f"A {domain_label} hierarchy and authority network built from HKLII judgments plus local textbook passages. Start at the doctrinal modules, then drill into topics, cases, and statutes.",
            "viewer_intro_internal": f"This internal {domain_label} explorer uses the same hierarchy shell but keeps the graph centered on case metadata, textbook support passages, and statute links.",
            "legal_domain": domain_id,
            "domain_tags": [domain_id],
        },
        "nodes": nodes,
        "edges": edges,
    }
    payload["meta"]["node_count"] = len(nodes)
    payload["meta"]["edge_count"] = len(edges)
    payload["meta"]["authority_tree"] = _authority_tree_payload(nodes, edges, topic_catalog, tree)
    return payload, topic_catalog, supplemental_sources, supplemental_passages, case_documents, crawler.warnings


def build_domain_graph_artifacts(
    domain_id: str,
    source_paths: list[str | Path],
    relationship_output_dir: str | Path,
    hybrid_output_dir: str | Path | None = None,
    title: str | None = None,
    tree: dict | None = None,
    tree_path: str | Path | None = None,
    candidates_path: str | Path | None = None,
    per_query_limit: int = 8,
    max_cases: int = 400,
    max_textbook_case_fetches: int = 80,
    max_enrich: int = 80,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
    discover_lineages: bool = False,
    lineages_path: str | Path | None = None,
) -> dict:
    domain_id = normalize_domain_id(domain_id)
    tree = _coerce_domain_tree(tree, domain_id) if tree is not None else load_domain_tree(domain_id, tree_path)
    domain_label = _domain_display_label(tree, domain_id)
    title = title or f"{domain_label} Relationship Graph"
    relationship_output_path = Path(relationship_output_dir).expanduser().resolve()
    relationship_output_path.mkdir(parents=True, exist_ok=True)

    stage_percent = {
        "initializing": 4,
        "searching_hklii": 18,
        "fetching_primary_cases": 34,
        "loading_textbooks": 48,
        "backfilling_textbook_cases": 62,
        "assembling_graph": 74,
        "writing_relationship": 82,
        "building_hybrid": 88,
        "embedding_exports": 94,
        "finalizing_monitor": 98,
        "completed": 100,
    }

    latest_progress: dict[str, object] = {}

    def update_progress(stage: str, message: str, status: str = "running", **stats: object) -> None:
        latest_progress.clear()
        latest_progress.update(
            {
                "title": title,
                "updated_at": datetime.now(UTC).isoformat(),
                "status": status,
                "stage": stage,
                "message": message,
                "percent": stage_percent.get(stage, 0),
                "refresh_seconds": MONITOR_REFRESH_SECONDS,
                "stats": stats,
            }
        )
        _write_monitor_surface(relationship_output_path, title, latest_progress)

    update_progress(
        "initializing",
        f"Preparing {domain_label} graph generation and monitor outputs.",
        source_path_count=len(source_paths),
        embedding_backend=embedding_backend,
    )
    candidate_registry = _load_candidate_registry(candidates_path, domain_id)
    payload, topic_catalog, sources, passages, case_documents, crawler_warnings = build_domain_relationship_payload(
        domain_id=domain_id,
        tree=tree,
        source_paths=source_paths,
        title=title,
        per_query_limit=per_query_limit,
        max_cases=max_cases,
        max_textbook_case_fetches=max_textbook_case_fetches,
        candidate_registry=candidate_registry,
        progress_callback=update_progress,
    )
    effective_lineages_path = Path(lineages_path or DISCOVERED_LINEAGES_DEFAULT_PATH)
    extra_lineages: list[dict] = []
    if discover_lineages:
        update_progress(
            "assembling_graph",
            f"Discovering {domain_label} authority lineages from existing graph authorities.",
            node_count=len(payload["nodes"]),
            edge_count=len(payload["edges"]),
            lineages_path=str(effective_lineages_path),
        )
        discovery = discover_lineages_from_payload(
            payload,
            domain_id=domain_id,
            output_path=effective_lineages_path,
        )
        extra_lineages = discovery.get("lineages", [])
    elif lineages_path:
        extra_lineages = load_discovered_lineages(effective_lineages_path)
    augment_public_payload_with_lineages(payload, extra_lineages=extra_lineages)
    update_progress(
        "writing_relationship",
        "Writing relationship graph files and viewer artifacts.",
        node_count=len(payload["nodes"]),
        edge_count=len(payload["edges"]),
        warning_count=len(crawler_warnings),
    )
    manifest = _write_relationship_payload(payload, relationship_output_path)

    bundle = None
    if hybrid_output_dir:
        update_progress(
            "building_hybrid",
            f"Building the hierarchical {domain_label} explorer bundle.",
            node_count=len(payload["nodes"]),
            edge_count=len(payload["edges"]),
        )
        bundle = build_hierarchical_graph_bundle(
            payload,
            title=title.replace("Relationship", "Hierarchical"),
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            max_enrich=max_enrich,
        )
        write_hybrid_graph_artifacts(bundle, hybrid_output_dir)

    update_progress(
        "embedding_exports",
        "Generating embedding, Chroma, and Supabase export artifacts.",
        node_count=len(payload["nodes"]),
        relationship_output_dir=str(relationship_output_path),
    )
    storage_status = _storage_exports(
        payload,
        bundle,
        relationship_output_path,
        domain_id=domain_id,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
    )
    update_progress(
        "finalizing_monitor",
        "Calculating coverage gaps and final monitor guidance.",
        embedding_record_count=storage_status["embedding_record_count"],
        embedding_backend=storage_status["embedding_backend"]["backend"],
        warning_count=len(crawler_warnings),
    )
    monitor = _monitor_report(
        payload,
        topic_catalog,
        relationship_output_path,
        crawler_warnings,
        storage_status,
        domain_label=domain_label,
    )
    manifest["storage"] = storage_status
    manifest["monitor_report"] = str(relationship_output_path / "monitor_report.json")
    manifest["monitor_dashboard"] = str(relationship_output_path / "monitor_report.html")
    manifest["build_progress"] = str(relationship_output_path / "build_progress.json")
    manifest["crawler_warnings"] = crawler_warnings
    manifest["source_count"] = len(sources)
    manifest["passage_count"] = len(passages) + sum(len(case.paragraphs) for case in case_documents)
    manifest["case_count"] = len(case_documents)
    if candidates_path:
        manifest["candidates_registry"] = str(Path(candidates_path).expanduser())
        manifest["candidate_registry_count"] = len(candidate_registry)
    manifest["monitor"] = {
        "uncovered_topics": len(monitor["uncovered_topics"]),
        "low_coverage_topics": len(monitor["low_coverage_topics"]),
    }
    update_progress(
        "completed",
        f"{domain_label} graph build completed. Monitor report and exports are ready.",
        status="completed",
        node_count=manifest["node_count"],
        edge_count=manifest["edge_count"],
        case_count=monitor["case_count"],
        topic_count=monitor["topic_count"],
        uncovered_topics=len(monitor["uncovered_topics"]),
        low_coverage_topics=len(monitor["low_coverage_topics"]),
    )
    _write_monitor_surface(relationship_output_path, title, latest_progress, report=monitor)
    _write_json(relationship_output_path / "manifest.json", manifest)
    return manifest


def build_criminal_relationship_payload(
    source_paths: list[str | Path],
    title: str = "Hong Kong Criminal Law Relationship Graph",
    per_query_limit: int = 8,
    max_cases: int = 400,
    max_textbook_case_fetches: int = 80,
    progress_callback=None,
) -> tuple[dict, list[dict], list[SourceDocument], list[Passage], list[HKLIICaseDocument], list[str]]:
    return build_domain_relationship_payload(
        domain_id="criminal",
        tree=load_domain_tree("criminal"),
        source_paths=source_paths,
        title=title,
        per_query_limit=per_query_limit,
        max_cases=max_cases,
        max_textbook_case_fetches=max_textbook_case_fetches,
        progress_callback=progress_callback,
    )


def build_criminal_graph_artifacts(
    source_paths: list[str | Path],
    relationship_output_dir: str | Path,
    hybrid_output_dir: str | Path | None = None,
    title: str = "Hong Kong Criminal Law Relationship Graph",
    per_query_limit: int = 8,
    max_cases: int = 400,
    max_textbook_case_fetches: int = 80,
    max_enrich: int = 80,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
    discover_lineages: bool = False,
    lineages_path: str | Path | None = None,
) -> dict:
    return build_domain_graph_artifacts(
        domain_id="criminal",
        source_paths=source_paths,
        relationship_output_dir=relationship_output_dir,
        hybrid_output_dir=hybrid_output_dir,
        title=title,
        per_query_limit=per_query_limit,
        max_cases=max_cases,
        max_textbook_case_fetches=max_textbook_case_fetches,
        max_enrich=max_enrich,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        discover_lineages=discover_lineages,
        lineages_path=lineages_path,
    )
