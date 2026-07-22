from unittest.mock import patch, MagicMock

import anthropic
import click
import pytest

from quill.analyzer import analyze_document, SENIOR_PARTNER_PROMPT


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


def test_analyze_calls_claude_opus(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        analyze_document("Some legal text")

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-5"


def test_analyze_uses_senior_partner_prompt(monkeypatch, anthropic_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = anthropic_response
        analyze_document("Some legal text")

        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        assert call_kwargs["system"] == SENIOR_PARTNER_PROMPT


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
        mock_cls.return_value.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body=None,
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
        mock_cls.return_value.messages.create.side_effect = anthropic.APIConnectionError(
            request=MagicMock(),
        )

        with pytest.raises(click.ClickException, match="Could not connect"):
            analyze_document("Some text")
