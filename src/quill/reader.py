"""File reading utilities for Quill document analysis."""

from pathlib import Path

import click
import pymupdf

__all__ = ["read_file"]

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".csv", ".json", ".xml", ".html"}


def read_file(path: str) -> str:
    """Read a file and return its text content.

    Args:
        path: Filesystem path to the file.

    Returns:
        The text content of the file.

    Raises:
        click.ClickException: If the file is empty, unsupported, or unreadable.
    """
    filepath = Path(path)
    suffix = filepath.suffix.lower()

    if suffix == ".pdf":
        text = _read_pdf(filepath)
    elif suffix in SUPPORTED_TEXT_EXTENSIONS or suffix == "":
        text = filepath.read_text(encoding="utf-8", errors="replace")
    else:
        raise click.ClickException(
            f"Unsupported file format: {suffix}. "
            f"Supported: .pdf, {', '.join(sorted(SUPPORTED_TEXT_EXTENSIONS))}"
        )

    if not text.strip():
        raise click.ClickException(f"File is empty: {path}")

    return text


def _read_pdf(filepath: Path) -> str:
    """Extract text from a PDF file.

    Args:
        filepath: Path to the PDF file.

    Returns:
        Concatenated text from all pages.

    Raises:
        click.ClickException: If the PDF cannot be opened or read.
    """
    try:
        with pymupdf.open(filepath) as doc:  # type: ignore[no-untyped-call]
            pages = [page.get_text() for page in doc]
    except Exception as exc:
        raise click.ClickException(f"Cannot read PDF: {exc}") from exc
    return "\n".join(pages)
