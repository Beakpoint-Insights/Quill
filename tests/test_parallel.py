"""Tests for parallel multi-role analysis (QUIL-19)."""

import time
from unittest.mock import MagicMock, patch

import anthropic
import click
import pytest
from anthropic.types import Message, TextBlock, Usage

from quill.analyzer import analyze_document_all_roles
from quill.roles import ALL_ROLES, LAW_CLERK, SENIOR_PARTNER


def _make_response(role_name: str, model: str = "claude-sonnet-4-20250514") -> Message:
    return Message(
        id=f"msg_{role_name.replace(' ', '_').lower()}",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text=f"Analysis from {role_name}.")],
        model=model,
        stop_reason="end_turn",
        usage=Usage(input_tokens=100, output_tokens=50),
    )


class TestAnalyzeAllRoles:
    def test_returns_five_results(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            results = analyze_document_all_roles("contract text")

        assert len(results) == 5

    def test_results_preserve_role_order(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            results = analyze_document_all_roles("contract text")

        role_names = [r.role for r in results]
        expected = [r.name for r in ALL_ROLES]
        assert role_names == expected

    def test_each_role_uses_its_assigned_model(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            analyze_document_all_roles("contract text")

            calls = mock_cls.return_value.messages.create.call_args_list
            called_models = {c.kwargs["model"] for c in calls}
            expected_models = {r.model for r in ALL_ROLES}
            assert called_models == expected_models

    def test_each_role_uses_its_system_prompt(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            analyze_document_all_roles("contract text")

            calls = mock_cls.return_value.messages.create.call_args_list
            called_prompts = {c.kwargs["system"] for c in calls}
            expected_prompts = {r.system_prompt for r in ALL_ROLES}
            assert called_prompts == expected_prompts

    def test_missing_api_key_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(click.ClickException, match="ANTHROPIC_API_KEY"):
            analyze_document_all_roles("some text")

    def test_accepts_explicit_api_key(self) -> None:
        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            results = analyze_document_all_roles(
                "contract text", api_key="explicit-key"
            )

        assert len(results) == 5


class TestFailureIsolation:
    def test_one_failure_does_not_crash_others(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        responses = [_make_response(r.name) for r in ALL_ROLES]

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            idx = call_count
            call_count += 1
            if idx == 2:
                raise anthropic.APIConnectionError(request=MagicMock())
            return responses[idx]

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = side_effect
            results = analyze_document_all_roles("contract text")

        assert len(results) == 5
        successes = [r for r in results if r.error is None]
        failures = [r for r in results if r.error is not None]
        assert len(successes) == 4
        assert len(failures) == 1

    def test_failed_role_contains_error_message(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        def always_fail(**kwargs):
            raise anthropic.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429),
                body=None,
            )

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = always_fail
            results = analyze_document_all_roles("contract text")

        for result in results:
            assert result.error is not None
            assert result.text == ""
            assert result.input_tokens == 0
            assert result.output_tokens == 0

    def test_failed_role_preserves_role_name(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        def always_fail(**kwargs):
            raise anthropic.APIConnectionError(request=MagicMock())

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = always_fail
            results = analyze_document_all_roles("contract text")

        role_names = [r.role for r in results]
        expected = [r.name for r in ALL_ROLES]
        assert role_names == expected


class TestConcurrency:
    def test_runs_concurrently_not_sequentially(self, monkeypatch) -> None:
        """Verify wall-clock time is closer to one call than five sequential calls."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        delay_per_call = 0.1

        def slow_create(**kwargs):
            time.sleep(delay_per_call)
            return _make_response("Test")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = slow_create

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

        with (
            patch("quill.analyzer.anthropic.Anthropic") as mock_cls,
            patch("quill.analyzer.tracer") as mock_tracer,
        ):
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
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
    def test_two_roles_only(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        subset = (LAW_CLERK, SENIOR_PARTNER)

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in subset
            ]
            results = analyze_document_all_roles("contract text", roles=subset)

        assert len(results) == 2
        assert results[0].role == "Law Clerk"
        assert results[1].role == "Senior Partner"
