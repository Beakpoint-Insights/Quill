import pytest
from click import ClickException

from quill.reader import read_file


def test_read_plain_text(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("This is a legal document.")
    assert read_file(str(f)) == "This is a legal document."


def test_read_markdown(sample_nda):
    text = read_file(str(sample_nda))
    assert len(text) > 0
    assert "Confidential Information" in text


def test_read_all_fixtures(fixtures_dir):
    files = list(fixtures_dir.rglob("*.md"))
    files = [f for f in files if f.name != "ATTRIBUTIONS.md"]
    assert len(files) >= 30
    for f in files:
        text = read_file(str(f))
        assert len(text) > 0, f"Empty content from {f}"


def test_read_pdf(tmp_path):
    import pymupdf

    pdf_path = tmp_path / "doc.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Legal terms and conditions apply.")
    doc.save(str(pdf_path))
    doc.close()

    text = read_file(str(pdf_path))
    assert "Legal terms" in text


def test_read_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    with pytest.raises(ClickException, match="empty"):
        read_file(str(f))


def test_read_large_file(tmp_path):
    f = tmp_path / "large.txt"
    f.write_text("Section 1. " * 20_000)
    text = read_file(str(f))
    assert len(text) > 100_000
