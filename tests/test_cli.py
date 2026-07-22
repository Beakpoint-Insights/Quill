from click.testing import CliRunner

from quill.cli import main


def test_cli_help():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Quill" in result.output


def test_cli_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_analyze_missing_file():
    result = CliRunner().invoke(main, ["analyze", "nonexistent.txt"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_analyze_no_argument():
    result = CliRunner().invoke(main, ["analyze"])
    assert result.exit_code != 0
    assert "Missing argument" in result.output


def test_analyze_help_documents_no_cache_flag():
    result = CliRunner().invoke(main, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--no-cache" in result.output
