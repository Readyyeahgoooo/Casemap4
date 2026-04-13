from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import hashlib
import json
import re
import ssl
import tempfile
import time

CASE_CITATION_RE = re.compile(r"\[(\d{4})\]\s+([A-Z]{2,8})\s+(\d+)")
CASE_PATH_RE = re.compile(r"^/(?P<lang>[a-z]+)/cases/(?P<abbr>[^/]+)/(?P<year>\d{4})/(?P<num>[^/?#]+)$", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
TITLE_RE = re.compile(r"<title>\s*(.*?)\s*</title>", re.IGNORECASE | re.DOTALL)
CORAM_RE = re.compile(r"<coram>\s*(.*?)\s*</coram>", re.IGNORECASE | re.DOTALL)
CASE_LINK_RE = re.compile(
    r'<a\b[^>]*href="(?P<href>/[a-z]+/cases/[^"]+)"[^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
STATUTE_LINK_RE = re.compile(
    r'<a\b[^>]*href="(?P<href>/[a-z]+/legis/[^"]+)"[^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
SPACE_RE = re.compile(r"\s+")


def _clean_text(value: str) -> str:
    text = unescape(HTML_TAG_RE.sub(" ", value or ""))
    text = text.replace("\xa0", " ")
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def _slugify_for_cache(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "item"
    if len(slug) <= 140:
        return slug
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{slug[:120].rstrip('_')}_{digest}"


@dataclass
class HKLIISearchResult:
    title: str
    subtitle: str
    path: str
    db: str
    pub_date: str = ""

    @property
    def is_case(self) -> bool:
        return "/cases/" in self.path and "court" in self.db.lower()

    @property
    def public_url(self) -> str:
        return f"https://www.hklii.hk{self.path}"


@dataclass
class HKLIIReference:
    label: str
    url: str
    kind: str


@dataclass
class HKLIIParagraph:
    paragraph_span: str
    text: str


@dataclass
class HKLIICaseDocument:
    case_name: str
    court_name: str
    neutral_citation: str
    decision_date: str
    court_code: str
    public_url: str
    raw_html: str
    paragraphs: list[HKLIIParagraph] = field(default_factory=list)
    judges: list[str] = field(default_factory=list)
    cited_cases: list[HKLIIReference] = field(default_factory=list)
    cited_statutes: list[HKLIIReference] = field(default_factory=list)
    title: str = ""

    @property
    def text(self) -> str:
        return "\n\n".join(paragraph.text for paragraph in self.paragraphs if paragraph.text)


class HKLIICrawler:
    def __init__(
        self,
        cache_dir: str | Path = "data/cache/hklii",
        user_agent: str = "Mozilla/5.0 (Codex HKLII crawler)",
        timeout_seconds: int = 30,
        max_workers: int = 4,
        retry_delay_seconds: float = 0.3,
    ) -> None:
        self.base_url = "https://www.hklii.hk"
        self.api_url = f"{self.base_url}/api"
        self.cache_dir = self._prepare_cache_dir(cache_dir)
        self.timeout_seconds = timeout_seconds
        self.max_workers = max_workers
        self.retry_delay_seconds = retry_delay_seconds
        self.user_agent = user_agent
        self.warnings: list[str] = []
        self._cache_warning_emitted = False

    def _prepare_cache_dir(self, cache_dir: str | Path) -> Path | None:
        candidates = [
            Path(cache_dir).expanduser(),
            Path(tempfile.gettempdir()) / "casemap_hklii_cache",
        ]
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                resolved.mkdir(parents=True, exist_ok=True)
                probe = resolved / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return resolved
            except OSError:
                continue
        return None

    def simple_search(self, query: str, limit: int = 10) -> list[HKLIISearchResult]:
        if limit <= 0:
            return []
        try:
            payload = self._request_json(
                "simplesearch",
                {"searchstring": query, "disablefuzzy": "true"},
                cache_prefix="search",
            )
        except Exception as exc:  # pragma: no cover - network failures are environment-dependent.
            self.warnings.append(f"Search failed for '{query}': {exc}")
            return []
        results: list[HKLIISearchResult] = []
        for item in payload.get("results", []):
            record = HKLIISearchResult(
                title=item.get("title", "").strip(),
                subtitle=item.get("subtitle", "").strip(),
                path=item.get("path", "").strip(),
                db=item.get("db", "").strip(),
                pub_date=item.get("pub_date", "").strip(),
            )
            if record.is_case:
                results.append(record)
            if len(results) >= limit:
                break
        return results

    def fetch_case_document(self, public_path: str) -> HKLIICaseDocument:
        match = CASE_PATH_RE.match(public_path)
        if not match:
            raise ValueError(f"Unsupported HKLII case path: {public_path}")
        lang = match.group("lang")
        abbr = match.group("abbr")
        year = match.group("year")
        num = match.group("num")
        payload = self._request_json(
            "getjudgment",
            {"lang": lang, "abbr": abbr, "year": year, "num": num},
            cache_prefix="judgment",
        )
        raw_html = payload.get("content", "")
        title_text = _clean_text(TITLE_RE.search(raw_html).group(1)) if TITLE_RE.search(raw_html) else ""
        case_name = self._derive_case_name(title_text, payload.get("neutral", ""))
        coram_html = CORAM_RE.search(raw_html).group(1) if CORAM_RE.search(raw_html) else ""
        judges_text = _clean_text(coram_html)
        paragraphs = self._extract_paragraphs(raw_html)
        return HKLIICaseDocument(
            case_name=case_name,
            court_name=payload.get("db", "").strip(),
            neutral_citation=payload.get("neutral", "").strip(),
            decision_date=(payload.get("date", "") or "").strip(),
            court_code=abbr.upper(),
            public_url=f"{self.base_url}{public_path}",
            raw_html=raw_html,
            paragraphs=paragraphs,
            judges=[judges_text] if judges_text else [],
            cited_cases=self._extract_case_links(raw_html),
            cited_statutes=self._extract_statute_links(raw_html),
            title=title_text,
        )

    def crawl_paths(self, public_paths: list[str]) -> list[HKLIICaseDocument]:
        documents: list[HKLIICaseDocument] = []
        unique_paths = sorted(set(public_paths))
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self.fetch_case_document, path): path for path in unique_paths}
            for future in as_completed(future_map):
                path = future_map[future]
                try:
                    documents.append(future.result())
                except Exception as exc:  # pragma: no cover - network failures are environment-dependent.
                    self.warnings.append(f"Failed to fetch {path}: {exc}")
        return sorted(documents, key=lambda item: (item.decision_date, item.case_name))

    def _request_json(self, endpoint: str, params: dict[str, str], cache_prefix: str) -> dict:
        query = urllib_parse.urlencode(params)
        cache_key = f"{cache_prefix}_{endpoint}_{_slugify_for_cache(query)}.json"
        cache_path = (self.cache_dir / cache_key) if self.cache_dir is not None else None
        if cache_path is not None and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        url = f"{self.api_url}/{endpoint}?{query}"
        request = urllib_request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json,text/plain,*/*",
            },
        )
        try:
            data = self._open_json(request, context=None)
        except urllib_error.URLError as exc:
            reason = getattr(exc, "reason", "")
            if "CERTIFICATE_VERIFY_FAILED" not in str(reason):
                raise
            self.warnings.append(f"SSL verification failed for {url}; retried with an unverified TLS context.")
            data = self._open_json(request, context=ssl._create_unverified_context())
        if cache_path is not None:
            try:
                cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError as exc:
                if not self._cache_warning_emitted:
                    self.warnings.append(f"HKLII cache write skipped: {exc}")
                    self._cache_warning_emitted = True
        time.sleep(self.retry_delay_seconds)
        return data

    def _open_json(self, request: urllib_request.Request, context: ssl.SSLContext | None) -> dict:
        with urllib_request.urlopen(request, timeout=self.timeout_seconds, context=context) as response:
            raw = response.read().decode("utf-8", "ignore")
        return json.loads(raw)

    def _derive_case_name(self, title_text: str, neutral_citation: str) -> str:
        cleaned = title_text.strip()
        if neutral_citation:
            cleaned = cleaned.replace(neutral_citation, "").strip()
        if " " in cleaned and re.match(r"^[A-Z0-9()/.-]+\s", cleaned):
            cleaned = cleaned.split(" ", 1)[1].strip()
        return cleaned or neutral_citation or "Untitled HKLII Case"

    def _extract_paragraphs(self, html: str) -> list[HKLIIParagraph]:
        paragraphs: list[HKLIIParagraph] = []
        for block in PARAGRAPH_RE.findall(html):
            span_match = re.search(r'id="p(\d+)"', block, re.IGNORECASE)
            text = _clean_text(block)
            if len(text) < 20:
                continue
            paragraph_span = f"para {span_match.group(1)}" if span_match else ""
            paragraphs.append(HKLIIParagraph(paragraph_span=paragraph_span, text=text))
        return paragraphs

    def _extract_case_links(self, html: str) -> list[HKLIIReference]:
        references: list[HKLIIReference] = []
        seen: set[str] = set()
        for match in CASE_LINK_RE.finditer(html):
            href = match.group("href")
            if href in seen:
                continue
            seen.add(href)
            label = _clean_text(match.group("label"))
            references.append(HKLIIReference(label=label or href.rsplit("/", 1)[-1], url=f"{self.base_url}{href}", kind="case"))
        for citation_match in CASE_CITATION_RE.finditer(_clean_text(html)):
            neutral = f"[{citation_match.group(1)}] {citation_match.group(2)} {citation_match.group(3)}"
            synthetic_url = f"https://www.hklii.hk/search/?query={urllib_parse.quote_plus(neutral)}"
            if synthetic_url in seen:
                continue
            seen.add(synthetic_url)
            references.append(HKLIIReference(label=neutral, url=synthetic_url, kind="case"))
        return references

    def _extract_statute_links(self, html: str) -> list[HKLIIReference]:
        references: list[HKLIIReference] = []
        seen: set[str] = set()
        for match in STATUTE_LINK_RE.finditer(html):
            href = match.group("href")
            if href in seen:
                continue
            seen.add(href)
            label = _clean_text(match.group("label"))
            references.append(HKLIIReference(label=label or href, url=f"{self.base_url}{href}", kind="statute"))
        return references
