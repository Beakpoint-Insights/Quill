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


def test_project_flag_accepted(tmp_path: Path, mock_anthropic):
    """--project flag is accepted without error."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        ["analyze", str(doc), "--project", "Acme-Acquisition", "--single-role"],
    )
    assert result.exit_code == 0


def test_department_flag_accepted(tmp_path: Path, mock_anthropic):
    """--department flag is accepted without error."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        ["analyze", str(doc), "--department", "M&A", "--single-role"],
    )
    assert result.exit_code == 0


def test_both_flags_together(tmp_path: Path, mock_anthropic):
    """Both flags can be used in a single command."""
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


def test_flags_are_optional(tmp_path: Path, mock_anthropic):
    """Omitting both flags does not change existing behavior."""
    doc = tmp_path / "contract.txt"
    doc.write_text("This is a legal contract.")
    result = CliRunner().invoke(
        main,
        ["analyze", str(doc), "--single-role"],
    )
    assert result.exit_code == 0


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
            "--department",
            "R&D / Legal-Ops",
            "--single-role",
        ],
    )
    assert result.exit_code == 0
