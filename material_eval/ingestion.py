from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf", ".docx", ".pptx"}


@dataclass(frozen=True)
class ParsedDocument:
    source: str
    markdown: str
    parser: str
    source_path: str


def parse_document(path: Path | str) -> ParsedDocument:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == ".txt":
        return ParsedDocument(
            source=source_path.name,
            markdown=source_path.read_text(encoding="utf-8", errors="ignore").strip(),
            parser="plain-text",
            source_path=str(source_path),
        )
    if suffix in SUPPORTED_SUFFIXES:
        return _parse_with_docling(source_path)
    raise ValueError(f"Unsupported document type: {source_path}")


def ingest_knowledge_base(root: Path | str) -> list[ParsedDocument]:
    return list(_ingest_knowledge_base_cached(str(Path(root).resolve())))


@lru_cache(maxsize=16)
def _ingest_knowledge_base_cached(root: str) -> tuple[ParsedDocument, ...]:
    knowledge_dir = Path(root)
    if not knowledge_dir.exists():
        return []

    parsed: list[ParsedDocument] = []
    for path in sorted(item for item in knowledge_dir.iterdir() if item.is_file()):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        parsed.append(parse_document(path))
    return tuple(parsed)


def _parse_with_docling(path: Path) -> ParsedDocument:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter
    except ImportError as exc:  # pragma: no cover - only exercised in installs without docling
        raise RuntimeError("Docling is required for non-txt document parsing. Install `docling`.") from exc

    converter = DocumentConverter()
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        content = path.read_text(encoding="utf-8", errors="ignore")
        result = converter.convert_string(content, format=InputFormat.MD, name=path.name)
    elif suffix in {".html", ".htm"}:
        content = path.read_text(encoding="utf-8", errors="ignore")
        result = converter.convert_string(content, format=InputFormat.HTML, name=path.name)
    else:
        result = converter.convert(path)

    return ParsedDocument(
        source=path.name,
        markdown=result.document.export_to_markdown().strip(),
        parser="docling",
        source_path=str(path),
    )
