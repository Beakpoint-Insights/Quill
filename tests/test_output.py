from io import StringIO

from rich.console import Console

from quill.analyzer import AnalysisResult
from quill.output import display_analysis


def _make_result(**overrides) -> AnalysisResult:
    defaults = dict(
        text="## Executive Summary\nThis is an NDA.",
        role="Senior Partner",
        model="claude-opus-4-20250514",
        input_tokens=1200,
        output_tokens=85,
    )
    defaults.update(overrides)
    return AnalysisResult(**defaults)


def _capture_output(result: AnalysisResult) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=80)

    from unittest.mock import patch
    with patch("quill.output.Console", return_value=console):
        display_analysis(result)

    return buf.getvalue()


def test_output_contains_role_title():
    output = _capture_output(_make_result())
    assert "Senior Partner" in output


def test_output_renders_markdown_content():
    output = _capture_output(_make_result(text="## Key Risks\nUnfavorable terms."))
    assert "Key Risks" in output
    assert "Unfavorable terms" in output


def test_output_shows_usage_summary():
    output = _capture_output(_make_result())
    assert "Usage Summary" in output
    assert "1,200" in output
    assert "85" in output


def test_output_shows_model():
    output = _capture_output(_make_result(model="claude-opus-4-20250514"))
    assert "claude-opus-4-20250514" in output


def test_output_non_tty():
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=80)

    from unittest.mock import patch
    with patch("quill.output.Console", return_value=console):
        display_analysis(_make_result())

    output = buf.getvalue()
    assert "Senior Partner" in output
    assert len(output) > 0
