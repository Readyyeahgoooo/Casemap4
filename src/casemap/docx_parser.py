from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _clean_text(text: str) -> str:
    cleaned = text.replace("\xa0", " ")
    cleaned = cleaned.replace(" ,", ",")
    cleaned = cleaned.replace(" .", ".")
    cleaned = cleaned.replace(" ;", ";")
    cleaned = cleaned.replace(" :", ":")
    cleaned = cleaned.replace(" ,.", ".")
    cleaned = cleaned.replace(",,", ",")
    cleaned = cleaned.replace(",.", ".")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_paragraphs(docx_path: str | Path) -> list[str]:
    path = Path(docx_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Input document not found: {path}")

    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ET.fromstring(document_xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", WORD_NAMESPACE):
        pieces = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)]
        text = _clean_text("".join(pieces))
        if text:
            paragraphs.append(text)

    return paragraphs
