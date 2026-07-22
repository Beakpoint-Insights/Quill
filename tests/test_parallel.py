"""Tests for parallel multi-role analysis (QUIL-19 / QUIL-23)."""

import time
from unittest.mock import MagicMock, patch

import anthropic
import click
import openai
import pytest
from anthropic.types import Message, TextBlock, Usage

from quill.analyzer import analyze_document_all_roles
from quill.roles import ALL_ROLES, LAW_CLERK, SENIOR_PARTNER, Role

_ANTHROPIC_ROLES: list[Role] = [r for r in ALL_ROLES if r.provider == "anthropic"]
_OPENAI_ROLES: list[Role] = [r for r in ALL_ROLES if r.provider == "openai"]
_ANTHROPIC_NAMES: set[str] = {r.name for r in _ANTHROPIC_ROLES}
_OPENAI_NAMES: set[str] = {r.name for r in _OPENAI_ROLES}


def _make_anthropic_response(
    role_name: str, model: str = "claude-sonnet-4-20250514"
) -> Message:
    return Message(
        id=f"msg_{role_name.replace(' ', '_').lower()}",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text=f"Analysis from {role_name}.")],
        model=model,
        stop_reason="end_turn",
        usage=Usage(input_tokens=100, output_tokens=50),
    )


def _make_openai_response(role_name: str, model: str = "gpt-4.1-mini") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = f"Analysis from {role_name}."
    mock_resp.choices[0].finish_reason = "stop"
    mock_resp.model = model
    mock_resp.usage.prompt_tokens = 100
    mock_resp.usage.completion_tokens = 50
    return mock_resp


class TestAnalyzeAllRoles:
    def test_returns_five_results(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = [
                _make_anthropic_response(r.name) for r in _ANTHROPIC_ROLES
            ]
            mock_oai.return_value.chat.completions.create.side_effect = [
                _make_openai_response(r.name, r.model) for r in _OPENAI_ROLES
            ]
            results = analyze_document_all_roles("contract text")

        assert len(results) == 5

    def test_results_preserve_role_order(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = [
                _make_anthropic_response(r.name) for r in _ANTHROPIC_ROLES
            ]
            mock_oai.return_value.chat.completions.create.side_effect = [
                _make_openai_response(r.name, r.model) for r in _OPENAI_ROLES
            ]
            results = analyze_document_all_roles("contract text")

        role_names = [r.role for r in results]
        expected = [r.name for r in ALL_ROLES]
        assert role_names == expected

    def test_results_have_correct_providers(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = [
                _make_anthropic_response(r.name) for r in _ANTHROPIC_ROLES
            ]
            mock_oai.return_value.chat.completions.create.side_effect = [
                _make_openai_response(r.name, r.model) for r in _OPENAI_ROLES
            ]
            results = analyze_document_all_roles("contract text")

        for result, role in zip(results, ALL_ROLES, strict=True):
            assert result.provider == role.provider, (
                f"{role.name}: expected {role.provider}, got {result.provider}"
            )

    def test_missing_anthropic_key_fails_fast(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with pytest.raises(click.ClickException, match="ANTHROPIC_API_KEY"):
            analyze_document_all_roles("some text")

    def test_missing_openai_key_fails_fast(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(click.ClickException, match="OPENAI_API_KEY"):
            analyze_document_all_roles("some text")

    def test_missing_both_keys_reports_both(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(click.ClickException, match="ANTHROPIC_API_KEY") as exc_info:
            analyze_document_all_roles("some text")
        assert "OPENAI_API_KEY" in exc_info.value.message

    def test_accepts_explicit_api_key(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = [
                _make_anthropic_response(r.name) for r in _ANTHROPIC_ROLES
            ]
            mock_oai.return_value.chat.completions.create.side_effect = [
                _make_openai_response(r.name, r.model) for r in _OPENAI_ROLES
            ]
            results = analyze_document_all_roles(
                "contract text", api_key="explicit-key"
            )

        assert len(results) == 5


class TestFailureIsolation:
    def test_one_failure_does_not_crash_others(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        anthropic_call_count = 0

        def anthropic_side_effect(**kwargs):
            nonlocal anthropic_call_count
            idx = anthropic_call_count
            anthropic_call_count += 1
            if idx == 1:
                raise anthropic.APIConnectionError(request=MagicMock())
            return _make_anthropic_response(f"Role{idx}")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = anthropic_side_effect
            mock_oai.return_value.chat.completions.create.side_effect = [
                _make_openai_response(r.name, r.model) for r in _OPENAI_ROLES
            ]
            results = analyze_document_all_roles("contract text")

        assert len(results) == 5
        successes = [r for r in results if r.error is None]
        failures = [r for r in results if r.error is not None]
        assert len(successes) == 4
        assert len(failures) == 1

    def test_failed_role_contains_error_message(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = (
                anthropic.RateLimitError(
                    message="Rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            )
            mock_oai.return_value.chat.completions.create.side_effect = (
                openai.RateLimitError(
                    message="Rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            )
            results = analyze_document_all_roles("contract text")

        for result in results:
            assert result.error is not None
            assert result.text == ""
            assert result.input_tokens == 0
            assert result.output_tokens == 0

    def test_failed_role_preserves_role_name(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = (
                anthropic.APIConnectionError(request=MagicMock())
            )
            mock_oai.return_value.chat.completions.create.side_effect = (
                openai.APIConnectionError(request=MagicMock())
            )
            results = analyze_document_all_roles("contract text")

        role_names = [r.role for r in results]
        expected = [r.name for r in ALL_ROLES]
        assert role_names == expected


class TestConcurrency:
    def test_runs_concurrently_not_sequentially(self, monkeypatch) -> None:
        """Verify wall-clock time is closer to one call than five sequential calls."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        delay_per_call = 0.1

        def slow_anthropic(**kwargs):
            time.sleep(delay_per_call)
            return _make_anthropic_response("Test")

        def slow_openai(**kwargs):
            time.sleep(delay_per_call)
            return _make_openai_response("Test")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
        ):
            mock_anth.return_value.messages.create.side_effect = slow_anthropic
            mock_oai.return_value.chat.completions.create.side_effect = slow_openai

            start = time.monotonic()
            results = analyze_document_all_roles("contract text")
            elapsed = time.monotonic() - start

        assert len(results) == 5
        sequential_time = delay_per_call * 5
        assert elapsed < sequential_time * 0.8, (
            f"Took {elapsed:.2f}s, sequential would be {sequential_time:.2f}s"
        )


class TestOtelSpans:
    def test_all_roles_span_attributes(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_anth,
            patch("quill.analyzer.openai.OpenAI") as mock_oai,
            patch("quill.analyzer.tracer") as mock_tracer,
        ):
            mock_anth.return_value.messages.create.side_effect = [
                _make_anthropic_response(r.name) for r in _ANTHROPIC_ROLES
            ]
            mock_oai.return_value.chat.completions.create.side_effect = [
                _make_openai_response(r.name, r.model) for r in _OPENAI_ROLES
            ]

            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            analyze_document_all_roles("contract text")

            span_calls = mock_tracer.start_as_current_span.call_args_list
            span_names = [c.args[0] for c in span_calls]
            assert "quill.analyze_all" in span_names


class TestCustomRoleSubset:
    def test_two_anthropic_roles_only(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        subset = (LAW_CLERK, SENIOR_PARTNER)

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_anthropic_response(r.name) for r in subset
            ]
            results = analyze_document_all_roles("contract text", roles=subset)

        assert len(results) == 2
        assert results[0].role == "Law Clerk"
        assert results[1].role == "Senior Partner"
