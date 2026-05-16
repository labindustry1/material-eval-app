from __future__ import annotations

import re
from pathlib import Path


DEFAULT_REPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "artifacts" / "reports"


def write_markdown_report(
    *,
    filename: str,
    markdown: str,
    root: Path | str = DEFAULT_REPORT_DIR,
) -> Path:
    output_dir = Path(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _safe_filename(filename)
    path.write_text(markdown, encoding="utf-8")
    return path


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip(" .")
    return cleaned or "report.md"
