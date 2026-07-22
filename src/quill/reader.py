from pathlib import Path

import click
import pymupdf


def read_file(path: str) -> str:
    filepath = Path(path)
    suffix = filepath.suffix.lower()

    if suffix == ".pdf":
        text = _read_pdf(filepath)
    else:
        text = filepath.read_text(encoding="utf-8", errors="replace")

    if not text.strip():
        raise click.ClickException(f"File is empty: {path}")

    return text


def _read_pdf(filepath: Path) -> str:
    doc = pymupdf.open(filepath)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)
