"""Legal-domain classifier and quarantine logic.

Classifies HKLII cases into legal domains (criminal, civil, commercial, etc.)
to prevent cross-domain contamination when scaling to 50K+ cases.

Two classification modes:
  1. Rule-based (fast, free) — keyword/statute/court heuristics
  2. LLM-assisted (accurate, costs tokens) — DeepSeek classifies ambiguous cases

Usage:
  from casemap.domain_classifier import classify_domain, filter_candidates_by_domain
"""
from __future__ import annotations

import json
import os
import re
import ssl
from urllib import error as urllib_error
from urllib import request as urllib_request

# ── Legal domain taxonomy ──────────────────────────────────────

LEGAL_DOMAINS = {
    "criminal": {
        "label_en": "Criminal Law",
        "label_zh": "刑事法",
        "description": "Substantive criminal offences, defences, evidence, procedure, sentencing.",
    },
    "civil": {
        "label_en": "Civil Law and Procedure",
        "label_zh": "民事訴訟",
        "description": "Umbrella civil branch covering civil procedure plus non-criminal private and public law disputes.",
    },
    "contract": {
        "label_en": "Contract Law",
        "label_zh": "合約法",
        "description": "Formation, terms, breach, remedies, specific performance.",
    },
    "tort": {
        "label_en": "Tort Law",
        "label_zh": "侵權法",
        "description": "Negligence, nuisance, defamation, personal injury.",
    },
    "commercial": {
        "label_en": "Commercial Law",
        "label_zh": "商業法",
        "description": "Sale of goods, insurance, banking, agency, partnerships.",
    },
    "company": {
        "label_en": "Company Law",
        "label_zh": "公司法",
        "description": "Incorporation, directors, shareholders, winding up, unfair prejudice.",
    },
    "land": {
        "label_en": "Land and Property Law",
        "label_zh": "土地及物業法",
        "description": "Conveyancing, leases, adverse possession, covenants, landlord-tenant.",
    },
    "family": {
        "label_en": "Family Law",
        "label_zh": "家事法",
        "description": "Divorce, custody, maintenance, domestic violence, adoption.",
    },
    "employment": {
        "label_en": "Employment Law",
        "label_zh": "勞工法",
        "description": "Employment contracts, unfair dismissal, discrimination, MPF.",
    },
    "constitutional": {
        "label_en": "Constitutional and Administrative Law",
        "label_zh": "憲制及行政法",
        "description": "Basic Law, judicial review, Bill of Rights, human rights.",
    },
    "tax": {
        "label_en": "Tax Law",
        "label_zh": "稅法",
        "description": "Profits tax, salaries tax, stamp duty, tax avoidance.",
    },
    "insolvency": {
        "label_en": "Insolvency Law",
        "label_zh": "破產法",
        "description": "Bankruptcy, winding up, receivership, schemes of arrangement.",
    },
    "arbitration": {
        "label_en": "Arbitration and ADR",
        "label_zh": "仲裁與替代爭議解決",
        "description": "Arbitration awards, enforcement, mediation, ADR.",
    },
    "ip": {
        "label_en": "Intellectual Property",
        "label_zh": "知識產權",
        "description": "Trademarks, copyright, patents, design rights.",
    },
    "probate": {
        "label_en": "Probate and Trusts",
        "label_zh": "遺產及信託",
        "description": "Wills, intestacy, estate administration, trusts.",
    },
}


# ── Rule-based signals ─────────────────────────────────────────

CIVIL_UMBRELLA_DOMAINS = frozenset(
    {
        "civil",
        "contract",
        "tort",
        "commercial",
        "company",
        "land",
        "family",
        "employment",
        "constitutional",
        "tax",
        "insolvency",
        "arbitration",
        "ip",
        "probate",
    }
)

_TARGET_CONFIDENCE_THRESHOLDS = {
    "criminal": 0.6,
    "civil": 0.2,
}


def domain_matches_target(domain_id: str | None, target_domain: str) -> bool:
    """Return whether a classified domain belongs in the requested target branch."""
    domain = (domain_id or "").strip().lower().replace("-", "_")
    target = (target_domain or "").strip().lower().replace("-", "_")
    if not domain or domain == "unknown" or not target:
        return False
    if domain == target:
        return True
    if target == "civil":
        return domain in CIVIL_UMBRELLA_DOMAINS
    return False


def classification_matches_target(
    classification: dict | None,
    target_domain: str,
    *,
    include_secondary: bool = True,
) -> bool:
    """Return whether a classification should be retained for a target branch."""
    classification = classification or {}
    if domain_matches_target(classification.get("domain"), target_domain):
        return True
    if include_secondary:
        return any(
            domain_matches_target(domain, target_domain)
            for domain in classification.get("secondary_domains", []) or []
        )
    return False


def target_confidence_threshold(target_domain: str) -> float:
    """Confidence needed for a rule-based match in a target branch."""
    target = (target_domain or "").strip().lower().replace("-", "_")
    return _TARGET_CONFIDENCE_THRESHOLDS.get(target, 0.25)

# Strong criminal indicators
# Case-number/court-list codes that are specific to criminal proceedings.
# Neutral citation court codes such as HKCA, HKCFA, HKCFI, and HKDC are generic
# and appear in many civil/commercial cases, so they are intentionally excluded.
_CRIMINAL_COURT_CODES = {"HKMC", "CACC", "CAQL", "DCCC", "ESCC", "KCCC", "TMCC", "STCC", "FLCC", "KTCC", "WKCC", "TSCC"}
_CRIMINAL_PARTIES_RE = re.compile(
    r"\b(HKSAR|The Queen|R\s+v\.?|Secretary for Justice\s+v|DPP\s+v)\b", re.IGNORECASE
)
_CRIMINAL_STATUTE_RE = re.compile(
    r"\b(Cap\.?\s*(?:200|210|212|134|220|221|238|245|405|455|461|169|374|571|366|60))\b", re.IGNORECASE
)
_CRIMINAL_KEYWORD_RE = re.compile(
    r"\b(murder|manslaughter|robbery|theft|burglary|rape|indecent\s+assault|"
    r"drug\s+trafficking|dangerous\s+drugs|wounding|grievous\s+bodily\s+harm|"
    r"arson|kidnapping|blackmail|forgery|money\s+laundering|bribery|"
    r"misconduct\s+in\s+public\s+office|perjury|perverting|triad|"
    r"sentence|conviction|acquittal|indictment|plea|guilty|"
    r"imprisonment|probation|community\s+service|suspended\s+sentence|"
    r"criminal\s+appeal|CACC|DCCC)\b", re.IGNORECASE
)

# Strong civil/commercial indicators
_CIVIL_PARTIES_RE = re.compile(
    r"\b(Ltd\.?|Limited|Corporation|Company|Inc\.?|Plc|Co\.?\s+Ltd|Holdings)\b", re.IGNORECASE
)
_CIVIL_KEYWORD_RE = re.compile(
    r"\b(breach\s+of\s+contract|specific\s+performance|injunction|damages|"
    r"pleading|statement\s+of\s+claim|writ|originating\s+summons|service\s+of\s+process|"
    r"discovery|disclosure|summary\s+judgment|strike\s+out|default\s+judgment|"
    r"security\s+for\s+costs|costs|taxation\s+of\s+costs|enforcement|garnishee|"
    r"interlocutory\s+injunction|mareva|anton\s+piller|limitation\s+period|"
    r"misrepresentation|repudiat|frustration|contractual\s+terms?|exemption\s+clause|"
    r"penalty\s+clause|liquidated\s+damages|quantum\s+meruit|estoppel|"
    r"negligence|duty\s+of\s+care|breach\s+of\s+duty|causation|remoteness|"
    r"contributory\s+negligence|personal\s+injury|occupiers?\s+liability|"
    r"vicarious\s+liability|nuisance|defamation|"
    r"winding\s+up|liquidat|bankruptcy|petition|receiver|"
    r"plaintiff|defendant|claimant|counterclaim|"
    r"lease|tenancy|conveyancing|adverse\s+possession|easement|mortgage|"
    r"co-ownership|deed\s+of\s+mutual\s+covenant|building\s+management|"
    r"directors?\s+dut(?:y|ies)|shareholders?\s+rights?|unfair\s+prejudice|"
    r"derivative\s+action|minority\s+shareholder|company\s+restoration|"
    r"sale\s+of\s+goods|banking|letters?\s+of\s+credit|insurance|indemnity|subrogation|agency|"
    r"divorce|custody|care\s+and\s+control|ancillary\s+relief|maintenance|matrimonial|"
    r"domestic\s+violence|non-molestation|"
    r"employment\s+ordinance|wrongful\s+dismissal|unreasonable\s+dismissal|"
    r"unfair\s+dismissal|discrimination|mandatory\s+provident\s+fund|mpf|"
    r"arbitrat|mediat|tribunal|"
    r"judicial\s+review|certiorari|mandamus|natural\s+justice|legitimate\s+expectation|"
    r"procedural\s+fairness|bill\s+of\s+rights|basic\s+law|"
    r"stamp\s+duty|profits\s+tax|salaries\s+tax|"
    r"trademark|copyright|patent|"
    r"will|probate|intestacy|trust|"
    r"trustee|estate\s+administration)\b", re.IGNORECASE
)

# Domain-specific statute mappings
_STATUTE_DOMAIN_MAP = {
    # Criminal
    "cap 200": ("criminal",), "cap 210": ("criminal",), "cap 212": ("criminal",),
    "cap 134": ("criminal",), "cap 220": ("criminal",), "cap 221": ("criminal",),
    "cap 238": ("criminal",), "cap 455": ("criminal",), "cap 405": ("criminal",),
    "cap 169": ("criminal",), "cap 374": ("criminal",), "cap 366": ("criminal",),
    "cap 60": ("criminal",),
    # Civil/Commercial
    "cap 32": ("company", "insolvency", "civil"),  # Companies / winding-up legacy references
    "cap 336": ("civil",),  # High Court Ordinance
    "cap 347": ("civil",),  # Limitation Ordinance
    "cap 4": ("civil",),  # District Court Ordinance
    "cap 6": ("civil", "insolvency"),  # Bankruptcy Ordinance / shared evidence references
    "cap 26": ("contract", "commercial"),  # Sale of Goods Ordinance
    "cap 71": ("contract",),  # Control of Exemption Clauses Ordinance
    "cap 284": ("contract",),  # Misrepresentation Ordinance
    "cap 457": ("contract",),  # Supply of Services (Implied Terms) Ordinance
    "cap 623": ("contract",),  # Contracts (Rights of Third Parties) Ordinance
    "cap 314": ("tort",),  # Occupiers Liability Ordinance
    "cap 21": ("tort",),  # Defamation Ordinance
    # Company
    "cap 622": ("company",),
    # Land
    "cap 219": ("land",),  # Conveyancing and Property Ordinance
    "cap 7": ("land",),  # Landlord and Tenant (Consolidation) Ordinance
    "cap 128": ("land",),  # Land Registration Ordinance
    "cap 344": ("land",),  # Building Management Ordinance
    # Family
    "cap 13": ("family",),  # Guardianship of Minors Ordinance
    "cap 16": ("family",),  # Separation and Maintenance Orders Ordinance
    "cap 179": ("family",),  # Matrimonial Causes Ordinance
    "cap 181": ("family",),  # Marriage Ordinance
    "cap 189": ("family",),  # Domestic and Cohabitation Relationships Violence Ordinance
    "cap 192": ("family",),  # Matrimonial Proceedings and Property Ordinance
    # Employment
    "cap 57": ("employment",),  # Employment Ordinance
    "cap 282": ("employment", "tort"),  # Employees' Compensation Ordinance
    "cap 485": ("employment",),  # Mandatory Provident Fund Schemes Ordinance
    "cap 487": ("employment",),  # Disability Discrimination
    "cap 480": ("employment",),  # Sex Discrimination
    "cap 527": ("employment",),  # Family Status Discrimination
    "cap 602": ("employment",),  # Race Discrimination
    # Constitutional / administrative
    "cap 383": ("constitutional",),  # Hong Kong Bill of Rights Ordinance
    "cap 442": ("constitutional",),  # Administrative Appeals Board Ordinance
    # Tax
    "cap 112": ("tax",),  # Inland Revenue Ordinance
    "cap 117": ("tax",),  # Stamp Duty Ordinance
    # IP
    "cap 559": ("ip",),  # Trade Marks Ordinance
    "cap 528": ("ip",),  # Copyright Ordinance
    # Arbitration
    "cap 609": ("arbitration",),  # Arbitration Ordinance
    # Securities
    "cap 571": ("criminal", "commercial"),  # SFO can be criminal or regulatory
}


# ── Rule-based classifier ─────────────────────────────────────

def classify_domain_rules(
    case_name: str,
    neutral_citation: str = "",
    text_snippet: str = "",
    statutes_cited: list[str] | None = None,
) -> dict:
    """Classify legal domain using rule-based heuristics.

    Returns:
        {
            "domain": "criminal",
            "confidence": 0.85,
            "signals": ["HKSAR party", "Cap. 210 cited"],
            "secondary_domains": ["commercial"],
        }
    """
    combined = f"{case_name} {neutral_citation} {text_snippet}"
    signals: list[str] = []
    domain_scores: dict[str, float] = {d: 0.0 for d in LEGAL_DOMAINS}

    # 1. Party names
    if _CRIMINAL_PARTIES_RE.search(case_name):
        domain_scores["criminal"] += 0.35
        signals.append("criminal_party_name")

    if _CIVIL_PARTIES_RE.search(case_name):
        domain_scores["commercial"] += 0.15
        domain_scores["company"] += 0.10
        signals.append("corporate_party_name")

    # 2. Criminal court codes in citation
    if neutral_citation:
        for code in _CRIMINAL_COURT_CODES:
            if code in neutral_citation.upper():
                domain_scores["criminal"] += 0.25
                signals.append(f"criminal_court:{code}")
                break

    # 3. Criminal keywords
    crim_hits = _CRIMINAL_KEYWORD_RE.findall(combined)
    if crim_hits:
        domain_scores["criminal"] += min(0.3, len(crim_hits) * 0.06)
        signals.append(f"criminal_keywords:{len(crim_hits)}")

    # 4. Civil keywords
    civil_hits = _CIVIL_KEYWORD_RE.findall(combined)
    if civil_hits:
        # Map to specific domains
        civil_text = " ".join(civil_hits).lower()
        if any(
            w in civil_text
            for w in (
                "pleading", "statement of claim", "writ", "originating summons",
                "service of process", "discovery", "disclosure", "summary judgment",
                "strike out", "default judgment", "security for costs", "costs",
                "enforcement", "garnishee", "injunction", "mareva", "anton piller",
                "limitation period",
            )
        ):
            domain_scores["civil"] += 0.35
            signals.append("civil_procedure_keywords")
        if any(w in civil_text for w in ("divorce", "custody", "maintenance", "matrimonial")):
            domain_scores["family"] += 0.3
            signals.append("family_keywords")
        if any(w in civil_text for w in ("care and control", "ancillary relief", "domestic violence", "non-molestation")):
            domain_scores["family"] += 0.3
            signals.append("family_keywords")
        if any(w in civil_text for w in ("employment", "dismissal", "discrimination", "provident fund", "mpf")):
            domain_scores["employment"] += 0.3
            signals.append("employment_keywords")
        if any(w in civil_text for w in ("winding", "liquidat", "bankruptcy", "receiver")):
            domain_scores["insolvency"] += 0.3
            signals.append("insolvency_keywords")
        if any(w in civil_text for w in ("arbitrat", "mediat")):
            domain_scores["arbitration"] += 0.3
            signals.append("arbitration_keywords")
        if any(w in civil_text for w in ("judicial review", "certiorari", "mandamus", "natural justice", "legitimate expectation", "procedural fairness", "bill of rights", "basic law")):
            domain_scores["constitutional"] += 0.3
            signals.append("constitutional_keywords")
        if any(w in civil_text for w in ("lease", "tenancy", "conveyancing", "adverse", "easement", "mortgage", "co-ownership", "deed of mutual covenant", "building management")):
            domain_scores["land"] += 0.3
            signals.append("land_keywords")
        if any(w in civil_text for w in ("trademark", "copyright", "patent")):
            domain_scores["ip"] += 0.3
            signals.append("ip_keywords")
        if any(w in civil_text for w in ("will", "probate", "intestacy", "trust", "trustee", "estate administration")):
            domain_scores["probate"] += 0.3
            signals.append("probate_keywords")
        if any(w in civil_text for w in ("negligence", "duty of care", "breach of duty", "causation", "remoteness", "contributory negligence", "personal injury", "occupiers", "vicarious", "nuisance", "defamation")):
            domain_scores["tort"] += 0.3
            signals.append("tort_keywords")
        if any(w in civil_text for w in ("breach of contract", "specific performance", "misrepresentation", "repudiat", "frustration", "contractual", "exemption clause", "penalty clause", "liquidated damages", "quantum meruit", "estoppel")):
            domain_scores["contract"] += 0.3
            signals.append("contract_keywords")
        if any(w in civil_text for w in ("sale of goods", "banking", "letter of credit", "insurance", "indemnity", "subrogation", "agency")):
            domain_scores["commercial"] += 0.3
            signals.append("commercial_keywords")
        if any(w in civil_text for w in ("director", "shareholder", "unfair prejudice", "derivative action", "company restoration")):
            domain_scores["company"] += 0.3
            signals.append("company_keywords")
        if any(w in civil_text for w in ("stamp duty", "profits tax", "salaries tax")):
            domain_scores["tax"] += 0.3
            signals.append("tax_keywords")
        # Generic civil
        remaining = len(civil_hits) - sum(1 for s in signals if s != "corporate_party_name" and not s.startswith("criminal"))
        if remaining > 0:
            domain_scores["civil"] += min(0.2, remaining * 0.05)
            signals.append(f"generic_civil_keywords:{remaining}")

    # 5. Statutes cited
    for statute in (statutes_cited or []):
        statute_lower = statute.lower()
        for cap_pattern, domains in _STATUTE_DOMAIN_MAP.items():
            if cap_pattern in statute_lower:
                weight = 0.20 if len(domains) == 1 else 0.12
                for domain in domains:
                    domain_scores[domain] += weight
                signals.append(f"statute:{cap_pattern}→{'/'.join(domains)}")
                break

    # Find winner
    best_domain = max(domain_scores, key=domain_scores.__getitem__)
    best_score = domain_scores[best_domain]

    # If no clear signal, mark as uncertain
    if best_score < 0.15:
        best_domain = "unknown"
        best_score = 0.0

    # Secondary domains (score > 0.15 and not the primary)
    secondary = [
        d for d, s in sorted(domain_scores.items(), key=lambda x: -x[1])
        if s >= 0.15 and d != best_domain
    ]

    return {
        "domain": best_domain,
        "confidence": round(min(best_score, 1.0), 2),
        "signals": signals,
        "secondary_domains": secondary[:3],
        "scores": {d: round(s, 3) for d, s in domain_scores.items() if s > 0},
    }


# ── LLM-assisted classifier ───────────────────────────────────

_DOMAIN_CLASSIFY_PROMPT = """You are a Hong Kong legal-domain classifier. Given a case, classify it into ONE primary legal domain.

Case name: {case_name}
Citation: {neutral_citation}
Text excerpt: {text_snippet}

Legal domains:
- criminal: Criminal offences, defences, evidence, procedure, sentencing
- civil: General civil procedure, injunctions, enforcement, limitation
- contract: Formation, breach, remedies
- tort: Negligence, nuisance, defamation, personal injury
- commercial: Sale of goods, insurance, banking, agency
- company: Directors, shareholders, winding up
- land: Conveyancing, leases, landlord-tenant
- family: Divorce, custody, maintenance, domestic violence
- employment: Employment contracts, dismissal, discrimination
- constitutional: Basic Law, judicial review, Bill of Rights
- tax: Profits tax, salaries tax, stamp duty
- insolvency: Bankruptcy, winding up, receivership
- arbitration: Arbitration awards, enforcement, mediation
- ip: Trademarks, copyright, patents
- probate: Wills, trusts, estate administration

Return ONLY a JSON object:
{{"domain": "criminal", "confidence": 0.95, "reasoning": "short explanation", "secondary_domains": []}}
"""


def classify_domain_llm(
    case_name: str,
    neutral_citation: str = "",
    text_snippet: str = "",
) -> dict:
    """Classify legal domain via DeepSeek (for ambiguous cases)."""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not deepseek_key and not openrouter_key:
        return {"domain": "unknown", "confidence": 0.0, "signals": ["no_api_key"]}

    if deepseek_key:
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        api_key = deepseek_key
        model = "deepseek-chat"
    else:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        api_key = openrouter_key
        model = os.environ.get("OPENROUTER_MODEL", "") or "deepseek/deepseek-chat"

    prompt = _DOMAIN_CLASSIFY_PROMPT.format(
        case_name=case_name,
        neutral_citation=neutral_citation,
        text_snippet=text_snippet[:2000],
    )

    payload = json.dumps({
        "model": model, "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib_request.Request(
        endpoint, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    try:
        def _do(ctx=None):
            kw = {"timeout": 30}
            if ctx is not None:
                kw["context"] = ctx
            with urllib_request.urlopen(req, **kw) as resp:
                return resp.read().decode("utf-8")
        try:
            raw = _do()
        except (ssl.SSLError, urllib_error.URLError):
            raw = _do(ssl._create_unverified_context())

        parsed = json.loads(raw)
        content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Extract JSON from response
        import re as _re
        m = _re.search(r"\{[^{}]*\}", content)
        if m:
            result = json.loads(m.group())
            result.setdefault("signals", ["llm_classified"])
            result.setdefault("secondary_domains", [])
            return result
    except Exception:
        pass

    return {"domain": "unknown", "confidence": 0.0, "signals": ["llm_error"]}


# ── Combined classifier ───────────────────────────────────────

def classify_domain(
    case_name: str,
    neutral_citation: str = "",
    text_snippet: str = "",
    statutes_cited: list[str] | None = None,
    use_llm_for_ambiguous: bool = False,
    ambiguity_threshold: float = 0.4,
) -> dict:
    """Classify case into legal domain. Falls back to LLM for ambiguous cases.

    Returns:
        {
            "domain": "criminal",
            "confidence": 0.85,
            "signals": [...],
            "secondary_domains": [...],
            "method": "rules" | "llm",
        }
    """
    result = classify_domain_rules(case_name, neutral_citation, text_snippet, statutes_cited)
    result["method"] = "rules"

    if use_llm_for_ambiguous and result["confidence"] < ambiguity_threshold:
        llm_result = classify_domain_llm(case_name, neutral_citation, text_snippet)
        if llm_result.get("confidence", 0) > result["confidence"]:
            llm_result["method"] = "llm"
            return llm_result

    return result


# ── Batch filtering ───────────────────────────────────────────

def _has_strong_target_signal(classification: dict, target_domain: str) -> bool:
    """Accept lower-confidence target matches only when the signals are specific."""
    signals = classification.get("signals", [])
    target_domain = (target_domain or "").strip().lower().replace("-", "_")

    if target_domain == "criminal":
        if "criminal_party_name" in signals:
            return True
        if any(signal.startswith("statute:") and "criminal" in signal for signal in signals):
            return True
        for signal in signals:
            if not signal.startswith("criminal_keywords:"):
                continue
            try:
                if int(signal.split(":", 1)[1]) >= 3:
                    return True
            except (IndexError, ValueError):
                continue
        return False

    if target_domain == "civil":
        domain = str(classification.get("domain") or "")
        if domain_matches_target(domain, "civil"):
            if any(signal in {"civil_procedure_keywords", "corporate_party_name"} for signal in signals):
                return True
            if any(signal.endswith("_keywords") and not signal.startswith("criminal") for signal in signals):
                return True
            if any(signal.startswith("statute:") and "criminal" not in signal for signal in signals):
                return True
        return False

    if any(signal.startswith("statute:") and target_domain in signal for signal in signals):
        return True
    if any(signal == f"{target_domain}_keywords" for signal in signals):
        return True
    return False


def filter_candidates_by_domain(
    candidates: list[dict],
    target_domain: str = "criminal",
    use_llm_for_ambiguous: bool = False,
    force_reclassify: bool = False,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split candidates into matched, cross-domain, and out-of-domain.

    Returns:
        (matched, cross_domain, out_of_domain)
        - matched: cases clearly in the target domain
        - cross_domain: cases touching both target and another domain
        - out_of_domain: cases that don't belong in target domain
    """
    matched = []
    cross_domain = []
    out_of_domain = []

    for candidate in candidates:
        case_name = candidate.get("case_name", "")
        nc = candidate.get("neutral_citation", "")

        # Build text snippet from principles
        snippets = []
        statutes_cited: list[str] = []
        for p in candidate.get("principles", [])[:3]:
            snippets.append(p.get("principle_label", ""))
            snippets.append(p.get("paraphrase_en", ""))
            snippets.append(p.get("statement_en", ""))
            snippets.append(p.get("public_excerpt", ""))
            statutes_cited.extend(str(item) for item in p.get("cited_statutes", []) or [])
        text_snippet = " ".join(snippets)

        existing_classification = candidate.get("domain_classification") or {}
        existing_confidence = float(existing_classification.get("confidence") or 0)
        if (
            not force_reclassify
            and existing_classification.get("domain")
            and existing_confidence >= 0.6
        ):
            classification = existing_classification
            classification.setdefault("method", "existing")
        else:
            classification = classify_domain(
                case_name, nc, text_snippet,
                statutes_cited=statutes_cited,
                use_llm_for_ambiguous=use_llm_for_ambiguous,
            )

        candidate["domain_classification"] = classification

        confidence = float(classification.get("confidence") or 0)
        primary_matches = domain_matches_target(classification.get("domain"), target_domain)
        secondary_matches = any(
            domain_matches_target(domain, target_domain)
            for domain in classification.get("secondary_domains", []) or []
        )
        confident_match = (
            confidence >= target_confidence_threshold(target_domain)
            or _has_strong_target_signal(classification, target_domain)
        )
        if (
            primary_matches
            and confident_match
        ):
            matched.append(candidate)
        elif primary_matches:
            candidate["domain_classification"]["quarantine_reason"] = "low_confidence_target_domain"
            cross_domain.append(candidate)
        elif secondary_matches:
            candidate["domain_classification"]["quarantine_reason"] = "cross_domain"
            cross_domain.append(candidate)
        else:
            candidate["domain_classification"]["quarantine_reason"] = "out_of_domain"
            out_of_domain.append(candidate)

    return matched, cross_domain, out_of_domain


# ── Non-criminal topic tree generator ──────────────────────────

DOMAIN_TREE_PROMPT = """You are a Hong Kong legal expert. Design a topic tree for **{domain_label}** ({domain_id}) in Hong Kong.

Follow this exact structure (same as our criminal law tree):

[
  {{
    "id": "module_id",
    "label_en": "Module Name",
    "label_zh": "中文名稱",
    "summary_en": "Description",
    "summary_zh": "中文描述",
    "subgrounds": [
      {{
        "id": "subground_id", 
        "label_en": "Subground Name",
        "label_zh": "中文名稱",
        "summary_en": "Description",
        "summary_zh": "中文描述",
        "topics": [
          {{
            "id": "topic_id",
            "label_en": "Topic Name", 
            "label_zh": "中文名稱",
            "search_queries": ["HKLII search query 1", "query 2"]
          }}
        ],
        "children": [{{"en": "concept", "zh": "概念"}}]
      }}
    ]
  }}
]

Requirements:
1. Cover all major areas of {domain_label} in Hong Kong
2. Include 3-6 modules, each with 2-4 subgrounds
3. Each subground should have 2-5 topics
4. search_queries should work on HKLII (use Hong Kong case names and ordinance references)
5. Include relevant Hong Kong ordinance references (Cap. numbers)
6. Use Hong Kong legal terminology

Return ONLY the JSON array, no other text.
"""


def generate_domain_tree(domain_id: str) -> list[dict] | None:
    """Ask DeepSeek to generate a topic tree for a non-criminal legal domain."""
    if domain_id not in LEGAL_DOMAINS:
        return None

    domain = LEGAL_DOMAINS[domain_id]
    prompt = DOMAIN_TREE_PROMPT.format(
        domain_id=domain_id,
        domain_label=domain["label_en"],
    )

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not deepseek_key and not openrouter_key:
        return None

    if deepseek_key:
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        api_key = deepseek_key
        model = "deepseek-chat"
    else:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        api_key = openrouter_key
        model = os.environ.get("OPENROUTER_MODEL", "") or "deepseek/deepseek-chat"

    payload = json.dumps({
        "model": model, "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib_request.Request(
        endpoint, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    try:
        def _do(ctx=None):
            kw = {"timeout": 90}
            if ctx is not None:
                kw["context"] = ctx
            with urllib_request.urlopen(req, **kw) as resp:
                return resp.read().decode("utf-8")
        try:
            raw = _do()
        except (ssl.SSLError, urllib_error.URLError):
            raw = _do(ssl._create_unverified_context())

        parsed = json.loads(raw)
        content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Extract JSON array
        import re as _re
        m = _re.search(r"\[[\s\S]*\]", content)
        if m:
            tree = json.loads(m.group())
            if isinstance(tree, list):
                return tree
    except Exception:
        pass
    return None
