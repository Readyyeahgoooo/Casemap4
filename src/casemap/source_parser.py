from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .docx_parser import extract_paragraphs
from .graphrag import CASE_RE, STATUTE_RE, slugify

PDF_SKIP_MARKERS = (
    "table of contents",
    "table of cases",
    "table of statutes",
    "table of legislation",
    "index",
)


@dataclass
class SourceDocument:
    source_id: str
    label: str
    path: str
    kind: str


@dataclass
class Passage:
    passage_id: str
    source_id: str
    source_label: str
    source_kind: str
    location: str
    order: int
    text: str


def _label_from_path(path: Path) -> str:
    label = path.stem.replace("_", " ").strip()
    label = re.sub(r"\s*\(?(?:Z[- ]?Library)\)?\s*", " ", label, flags=re.IGNORECASE)
    label = re.sub(r"\s{2,}", " ", label)
    return label.strip(" -_,")


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"/g\d+", " ", normalized)
    normalized = normalized.replace("\u2011", "-")
    normalized = normalized.replace("\u2013", "-")
    normalized = normalized.replace("\u2014", "-")
    normalized = normalized.replace("\u00a0", " ")
    normalized = re.sub(r"(\w)-\n(\w)", r"\1\2", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _skip_pdf_page(text: str) -> bool:
    lowered = text[:1200].lower()
    if any(marker in lowered for marker in PDF_SKIP_MARKERS):
        return True
    dot_leaders = lowered.count("....") + lowered.count(" . . .")
    if dot_leaders >= 5:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    average_length = sum(len(line) for line in lines) / len(lines)
    if average_length < 24 and len(lines) > 20:
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _chunk_text(text: str, max_chars: int = 900) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        compact = re.sub(r"\s+", " ", text).strip()
        return [compact] if compact else []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for sentence in sentences:
        sentence_length = len(sentence)
        if current and current_length + sentence_length + 1 > max_chars:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_length = sentence_length
            continue
        current.append(sentence)
        current_length += sentence_length + 1
    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def _split_pdf_blocks(text: str) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []

    raw_blocks = re.split(r"\n\s*\n", text)
    blocks: list[str] = []
    for block in raw_blocks:
        block = block.strip()
        if len(block) < 120:
            continue
        if block.lower().startswith("chapter ") and len(block.splitlines()) <= 4:
            continue
        single_line = re.sub(r"\s*\n\s*", " ", block)
        single_line = re.sub(r"\s+", " ", single_line).strip()
        if len(single_line) < 120:
            continue
        case_hits = len(CASE_RE.findall(single_line))
        statute_hits = len(STATUTE_RE.findall(single_line))
        sentence_hits = len(re.split(r"(?<=[.!?])\s+", single_line))
        if case_hits >= 6:
            continue
        if (case_hits + statute_hits) >= 5 and sentence_hits <= 3:
            continue
        blocks.extend(_chunk_text(single_line))
    return blocks


def extract_pdf_passages(path: str | Path, label: str | None = None) -> tuple[SourceDocument, list[Passage]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF ingestion requires the optional dependency 'pypdf'. "
            "Install it with `pip install pypdf`."
        ) from exc

    pdf_path = Path(path).expanduser().resolve()
    reader = PdfReader(str(pdf_path))
    source_id = f"source:{slugify(pdf_path.stem)}"
    source = SourceDocument(
        source_id=source_id,
        label=label or _label_from_path(pdf_path),
        path=str(pdf_path),
        kind="pdf",
    )

    passages: list[Passage] = []
    order = 0
    for page_index, page in enumerate(reader.pages, start=1):
        text = _normalize_text(page.extract_text() or "")
        if not text or _skip_pdf_page(text):
            continue
        blocks = _split_pdf_blocks(text)
        for block_index, block in enumerate(blocks, start=1):
            order += 1
            passages.append(
                Passage(
                    passage_id=f"{source_id}:p{page_index:04d}:{block_index:02d}",
                    source_id=source_id,
                    source_label=source.label,
                    source_kind=source.kind,
                    location=f"page {page_index}",
                    order=order,
                    text=block,
                )
            )
    return source, passages


def extract_docx_passages(path: str | Path, label: str | None = None) -> tuple[SourceDocument, list[Passage]]:
    docx_path = Path(path).expanduser().resolve()
    paragraphs = extract_paragraphs(docx_path)
    source_id = f"source:{slugify(docx_path.stem)}"
    source = SourceDocument(
        source_id=source_id,
        label=label or _label_from_path(docx_path),
        path=str(docx_path),
        kind="docx",
    )

    passages: list[Passage] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        passages.append(
            Passage(
                passage_id=f"{source_id}:para:{index:04d}",
                source_id=source_id,
                source_label=source.label,
                source_kind=source.kind,
                location=f"paragraph {index}",
                order=index,
                text=paragraph,
            )
        )
    return source, passages


def load_source_document(path: str | Path, label: str | None = None) -> tuple[SourceDocument, list[Passage]]:
    resolved = Path(path).expanduser().resolve()
    suffix = resolved.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_passages(resolved, label=label)
    if suffix == ".docx":
        return extract_docx_passages(resolved, label=label)
    raise ValueError(f"Unsupported source document type: {resolved}")
