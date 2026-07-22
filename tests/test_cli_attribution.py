"""Tests for --project and --department CLI flags (QUIL-15)."""

from pathlib import Path

from click.testing import CliRunner

from quill.cli import main


def test_analyze_help_documents_project_flag():
    """--project flag appears in help output."""
    result = CliRunner().invoke(main, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--project" in result.output


def test_analyze_help_documents_department_flag():
    """--department flag appears in help output."""
    result = CliRunner().invoke(main, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--department" in result.output


def test_both_flags_accepted(tmp_path: Path, mock_anthropic):
    """Both required flags are accepted together."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(doc),
            "--project",
            "Acme-Acquisition",
            "--department",
            "M&A",
            "--single-role",
        ],
    )
    assert result.exit_code == 0


def test_missing_project_fails(tmp_path: Path):
    """Omitting --project causes an error."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        ["analyze", str(doc), "--department", "M&A", "--single-role"],
    )
    assert result.exit_code != 0
    assert "project" in result.output.lower()


def test_missing_department_fails(tmp_path: Path):
    """Omitting --department causes an error."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        ["analyze", str(doc), "--project", "Acme", "--single-role"],
    )
    assert result.exit_code != 0
    assert "department" in result.output.lower()


def test_missing_both_fails(tmp_path: Path):
    """Omitting both flags causes an error."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        ["analyze", str(doc), "--single-role"],
    )
    assert result.exit_code != 0


def test_project_with_spaces(tmp_path: Path, mock_anthropic):
    """Flag values containing spaces are accepted."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(doc),
            "--project",
            "Project With Spaces",
            "--department",
            "Legal",
            "--single-role",
        ],
    )
    assert result.exit_code == 0


def test_department_with_special_characters(tmp_path: Path, mock_anthropic):
    """Flag values containing special characters are accepted."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(doc),
            "--project",
            "Acme",
            "--department",
            "R&D / Legal-Ops",
            "--single-role",
        ],
    )
    assert result.exit_code == 0
