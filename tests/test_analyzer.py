"""Tests for the analyzer module."""

from unittest.mock import MagicMock, patch

import anthropic
import click
import pytest

from quill.analyzer import analyze_document
from quill.roles import LAW_CLERK, SENIOR_PARTNER


def test_analyze_returns_response_text(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        result = analyze_document("Some legal text")

    assert result.text == "This document is a mutual non-disclosure agreement."
    assert result.role == "Senior Partner"
    assert result.model == "claude-sonnet-4-20250514"
    assert result.input_tokens == 1200
    assert result.output_tokens == 85


def test_analyze_uses_role_model(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        analyze_document("Some legal text", role=SENIOR_PARTNER)

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-5"


def test_analyze_uses_role_system_prompt(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        analyze_document("Some legal text", role=SENIOR_PARTNER)

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        assert call_kwargs["system"] == SENIOR_PARTNER.system_prompt


def test_analyze_with_different_role(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        result = analyze_document("Some legal text", role=LAW_CLERK)

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        assert call_kwargs["system"] == LAW_CLERK.system_prompt
        assert result.role == "Law Clerk"


def test_analyze_accepts_explicit_api_key(anthropic_response):
    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        result = analyze_document("Some legal text", api_key="explicit-key")

    assert result.text == "This document is a mutual non-disclosure agreement."
    mock_cls.assert_called_with(api_key="explicit-key")


def test_analyze_passes_document_as_user_message(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        analyze_document("Contract text here")

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Contract text here"


def test_analyze_missing_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(click.ClickException, match="ANTHROPIC_API_KEY"):
        analyze_document("Some text")


def test_analyze_auth_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_cls.return_value.messages.create.side_effect = (
            anthropic.AuthenticationError(
                message="Invalid API key",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(click.ClickException, match="Invalid ANTHROPIC_API_KEY"):
            analyze_document("Some text")


def test_analyze_rate_limit_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_cls.return_value.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited",
            response=mock_response,
            body=None,
        )

        with pytest.raises(click.ClickException, match="Rate limited"):
            analyze_document("Some text")


def test_analyze_connection_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.side_effect = (
            anthropic.APIConnectionError(
                request=MagicMock(),
            )
        )

        with pytest.raises(click.ClickException, match="Could not connect"):
            analyze_document("Some text")


def test_analyze_default_role_is_senior_partner(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        result = analyze_document("Some legal text")

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-5"
        assert call_kwargs["system"] == SENIOR_PARTNER.system_prompt
    assert result.role == "Senior Partner"


def test_analyze_no_cache_bypasses_cache(
    monkeypatch, anthropic_response, _no_cache
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response

        _no_cache.put(
            SENIOR_PARTNER.model,
            SENIOR_PARTNER.system_prompt,
            "Cached text",
            anthropic_response,
        )
        result = analyze_document("Cached text", no_cache=True)

        assert result.cache_hit is False
        assert mock_cls.return_value.messages.create.called


def test_analyze_sets_otel_attributes(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with (
        patch("quill.analyzer.anthropic.Anthropic") as mock_cls,
        patch("quill.analyzer.tracer") as mock_tracer,
    ):
        mock_cls.return_value.messages.create.return_value = anthropic_response
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        analyze_document("Some text", role=LAW_CLERK)

        call_kwargs = mock_tracer.start_as_current_span.call_args
        attrs = call_kwargs.kwargs.get("attributes", {})
        assert attrs["quill.role"] == "Law Clerk"
        assert attrs["quill.model"] == "claude-haiku-4-5"


def test_analyze_sets_token_usage_on_span(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with (
        patch("quill.analyzer.anthropic.Anthropic") as mock_cls,
        patch("quill.analyzer.tracer") as mock_tracer,
    ):
        mock_cls.return_value.messages.create.return_value = anthropic_response
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        analyze_document("Some text")

        mock_span.set_attribute.assert_any_call(
            "gen_ai.usage.input_tokens", 1200
        )
        mock_span.set_attribute.assert_any_call(
            "gen_ai.usage.output_tokens", 85
        )


def test_analyze_sets_zero_tokens_on_cache_hit(
    monkeypatch, anthropic_response, _no_cache
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with (
        patch("quill.analyzer.anthropic.Anthropic") as mock_cls,
        patch("quill.analyzer.tracer") as mock_tracer,
    ):
        mock_cls.return_value.messages.create.return_value = anthropic_response
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        _no_cache.put(
            SENIOR_PARTNER.model,
            SENIOR_PARTNER.system_prompt,
            "Cached text",
            anthropic_response,
        )
        result = analyze_document("Cached text")

        assert result.cache_hit is True
        mock_span.set_attribute.assert_any_call(
            "gen_ai.usage.input_tokens", 0
        )
        mock_span.set_attribute.assert_any_call(
            "gen_ai.usage.output_tokens", 0
        )
