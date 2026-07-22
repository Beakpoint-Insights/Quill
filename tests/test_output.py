"""Tests for Rich-formatted output rendering."""

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from quill.analyzer import AnalysisResult
from quill.output import display_analysis, display_multi_analysis
from quill.roles import ALL_ROLES


def _make_result(**overrides) -> AnalysisResult:
    defaults = dict(
        text="## Executive Summary\nThis is an NDA.",
        role="Senior Partner",
        model="claude-sonnet-5",
        input_tokens=1200,
        output_tokens=85,
    )
    defaults.update(overrides)
    return AnalysisResult(**defaults)


def _capture_output(result: AnalysisResult) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=80)

    with patch("quill.output.Console", return_value=console):
        display_analysis(result)

    return buf.getvalue()


def _capture_multi_output(results: list[AnalysisResult]) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=100)

    with patch("quill.output.Console", return_value=console):
        display_multi_analysis(results)

    return buf.getvalue()


# --- Single-result display (existing tests) ---


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

    with patch("quill.output.Console", return_value=console):
        display_analysis(_make_result())

    output = buf.getvalue()
    assert "Senior Partner" in output
    assert len(output) > 0


# --- Multi-result display (QUIL-18) ---


def _make_five_results() -> list[AnalysisResult]:
    return [
        _make_result(
            role=role.name,
            model=role.model,
            text=f"## Analysis\nAnalysis from {role.name}.",
            input_tokens=(i + 1) * 100,
            output_tokens=(i + 1) * 50,
        )
        for i, role in enumerate(ALL_ROLES)
    ]


class TestMultiAnalysisDisplay:
    def test_displays_five_sections_in_order(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        positions = []
        for role in ALL_ROLES:
            pos = output.find(role.name)
            assert pos != -1, f"{role.name} not found in output"
            positions.append(pos)

        assert positions == sorted(positions), "Roles not in expected order"

    def test_each_section_is_a_panel_with_role_title(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        for role in ALL_ROLES:
            assert role.name in output

    def test_renders_markdown_content_per_role(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        for role in ALL_ROLES:
            assert f"Analysis from {role.name}" in output

    def test_summary_table_shows_all_roles(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        assert "Usage Summary" in output
        for role in ALL_ROLES:
            assert role.name in output

    def test_summary_table_shows_token_counts(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        assert "100" in output
        assert "500" in output

    def test_summary_table_has_total_row(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        assert "Total" in output
        total_input = sum(r.input_tokens for r in results)
        assert f"{total_input:,}" in output

    def test_summary_shows_model_per_role(self) -> None:
        results = _make_five_results()
        output = _capture_multi_output(results)

        for role in ALL_ROLES:
            assert role.model in output

    def test_error_role_shows_error_panel(self) -> None:
        results = _make_five_results()
        results[2] = _make_result(
            role="Paralegal",
            model="claude-sonnet-4",
            text="",
            input_tokens=0,
            output_tokens=0,
            error="Rate limited by the Anthropic API.",
        )
        output = _capture_multi_output(results)

        assert "Rate limited" in output
        assert "failed" in output

    def test_renders_at_80_columns(self) -> None:
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=80)

        with patch("quill.output.Console", return_value=console):
            display_multi_analysis(_make_five_results())

        output = buf.getvalue()
        lines = output.split("\n")
        long_lines = [line for line in lines if len(line) > 80]
        assert not long_lines, f"Lines exceed 80 columns: {long_lines[:3]}"

    def test_cached_result_shows_cached_label(self) -> None:
        results = _make_five_results()
        results[0] = _make_result(
            role="Law Clerk",
            model="claude-haiku-3-5",
            text="## Analysis\nCached analysis.",
            input_tokens=0,
            output_tokens=0,
            cache_hit=True,
        )
        output = _capture_multi_output(results)

        assert "cached" in output

    def test_non_tty_output_has_no_escape_codes(self) -> None:
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, no_color=True, width=100)

        with patch("quill.output.Console", return_value=console):
            display_multi_analysis(_make_five_results())

        output = buf.getvalue()
        assert "\033" not in output
