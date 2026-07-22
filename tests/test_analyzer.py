"""Tests for the analyzer module."""

from unittest.mock import MagicMock, patch

import anthropic
import click
import openai
import pytest

from quill.analyzer import analyze_document
from quill.prompts import VARIANT_REGISTRY
from quill.roles import LAW_CLERK, PARALEGAL, RESEARCH_ASSISTANT, SENIOR_PARTNER


class TestAnthropicRoles:
    def test_analyze_returns_response_text(self, monkeypatch, anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            result = analyze_document("Some legal text")

        assert result.text == "This document is a mutual non-disclosure agreement."
        assert result.role == "Senior Partner"
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.input_tokens == 1200
        assert result.output_tokens == 85

    def test_analyze_uses_role_model(self, monkeypatch, anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            analyze_document("Some legal text", role=SENIOR_PARTNER)

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            assert call_kwargs["model"] == "claude-sonnet-5"

    def test_analyze_uses_role_system_prompt(self, monkeypatch, anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            analyze_document("Some legal text", role=SENIOR_PARTNER)

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            assert call_kwargs["system"] == SENIOR_PARTNER.system_prompt

    def test_analyze_with_different_role(self, monkeypatch, anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            result = analyze_document("Some legal text", role=LAW_CLERK)

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            assert call_kwargs["model"] == "claude-haiku-4-5"
            assert call_kwargs["system"] == LAW_CLERK.system_prompt
            assert result.role == "Law Clerk"

    def test_analyze_accepts_explicit_api_key(self, anthropic_response):
        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            result = analyze_document("Some legal text", api_key="explicit-key")

        assert result.text == "This document is a mutual non-disclosure agreement."
        mock_cls.assert_called_with(api_key="explicit-key")

    def test_analyze_passes_document_as_user_message(
        self, monkeypatch, anthropic_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            analyze_document("Contract text here")

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            messages = call_kwargs["messages"]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "Contract text here"

    def test_analyze_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(click.ClickException, match="ANTHROPIC_API_KEY"):
            analyze_document("Some text")

    def test_analyze_auth_error(self, monkeypatch):
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

    def test_analyze_rate_limit_error(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_cls.return_value.messages.create.side_effect = (
                anthropic.RateLimitError(
                    message="Rate limited",
                    response=mock_response,
                    body=None,
                )
            )

            with pytest.raises(click.ClickException, match="Rate limited"):
                analyze_document("Some text")

    def test_analyze_connection_error(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = (
                anthropic.APIConnectionError(
                    request=MagicMock(),
                )
            )

            with pytest.raises(click.ClickException, match="Could not connect"):
                analyze_document("Some text")

    def test_analyze_default_role_is_senior_partner(
        self, monkeypatch, anthropic_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            result = analyze_document("Some legal text")

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            assert call_kwargs["model"] == "claude-sonnet-5"
            assert call_kwargs["system"] == SENIOR_PARTNER.system_prompt
        assert result.role == "Senior Partner"


class TestOpenAIRoles:
    def _make_openai_response(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "OpenAI analysis result."
        mock_resp.choices[0].finish_reason = "stop"
        mock_resp.model = "gpt-4.1-mini"
        mock_resp.usage.prompt_tokens = 200
        mock_resp.usage.completion_tokens = 100
        return mock_resp

    def test_openai_role_uses_openai_client(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = (
                self._make_openai_response()
            )
            result = analyze_document("Some legal text", role=RESEARCH_ASSISTANT)

        assert result.provider == "openai"
        assert result.text == "OpenAI analysis result."
        assert result.role == "Research Assistant"
        assert result.input_tokens == 200
        assert result.output_tokens == 100
        mock_cls.assert_called_with(api_key="test-openai-key")

    def test_openai_role_sends_system_and_user_messages(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = (
                self._make_openai_response()
            )
            analyze_document("Contract text", role=RESEARCH_ASSISTANT)

            call_kwargs = mock_cls.return_value.chat.completions.create.call_args.kwargs
            messages = call_kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == RESEARCH_ASSISTANT.system_prompt
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "Contract text"

    def test_openai_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(click.ClickException, match="OPENAI_API_KEY"):
            analyze_document("Some text", role=RESEARCH_ASSISTANT)

    def test_openai_auth_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "bad-key")

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = (
                openai.AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(status_code=401),
                    body=None,
                )
            )
            with pytest.raises(click.ClickException, match="Invalid OPENAI_API_KEY"):
                analyze_document("Some text", role=RESEARCH_ASSISTANT)

    def test_openai_rate_limit_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = (
                openai.RateLimitError(
                    message="Rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            )
            with pytest.raises(click.ClickException, match="Rate limited"):
                analyze_document("Some text", role=RESEARCH_ASSISTANT)

    def test_openai_connection_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = (
                openai.APIConnectionError(request=MagicMock())
            )
            with pytest.raises(click.ClickException, match="Could not connect"):
                analyze_document("Some text", role=RESEARCH_ASSISTANT)

    def test_paralegal_uses_openai(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_resp = self._make_openai_response()
        mock_resp.model = "gpt-4.1"

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_resp
            result = analyze_document("Some text", role=PARALEGAL)

        assert result.provider == "openai"
        assert result.role == "Paralegal"

    def test_openai_api_key_ignored_for_anthropic_roles(
        self, monkeypatch, anthropic_response
    ):
        """Explicit api_key param is used for Anthropic, not OpenAI."""
        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            result = analyze_document(
                "Some text", role=SENIOR_PARTNER, api_key="explicit-key"
            )

        assert result.provider == "anthropic"


class TestCaching:
    def test_no_cache_bypasses_cache(self, monkeypatch, anthropic_response, _no_cache):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response

            first = analyze_document("Cached text")
            _no_cache.put(
                SENIOR_PARTNER.model,
                SENIOR_PARTNER.system_prompt,
                "Cached text",
                first,
            )
            result = analyze_document("Cached text", no_cache=True)

            assert result.cache_hit is False
            assert mock_cls.return_value.messages.create.call_count == 2


class TestOtelSpanAttributes:
    def test_analyze_sets_otel_attributes(self, monkeypatch, anthropic_response):
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
            assert attrs["quill.provider"] == "anthropic"

    def test_analyze_sets_token_usage_on_span(self, monkeypatch, anthropic_response):
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

            mock_span.set_attribute.assert_any_call("gen_ai.usage.input_tokens", 1200)
            mock_span.set_attribute.assert_any_call("gen_ai.usage.output_tokens", 85)

    def test_analyze_sets_zero_tokens_on_cache_hit(
        self, monkeypatch, anthropic_response, _no_cache
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

            first = analyze_document("Cached text")
            _no_cache.put(
                SENIOR_PARTNER.model,
                SENIOR_PARTNER.system_prompt,
                "Cached text",
                first,
            )
            result = analyze_document("Cached text")

            assert result.cache_hit is True
            mock_span.set_attribute.assert_any_call("gen_ai.usage.input_tokens", 0)
            mock_span.set_attribute.assert_any_call("gen_ai.usage.output_tokens", 0)


class TestDocTypePromptRouting:
    def test_anthropic_uses_variant_prompt_for_nda(
        self, monkeypatch, anthropic_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            analyze_document("Some text", role=LAW_CLERK, doc_type="nda")

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            expected = VARIANT_REGISTRY[("Law Clerk", "nda")]
            assert call_kwargs["system"] == expected

    def test_anthropic_uses_generic_when_no_doc_type(
        self, monkeypatch, anthropic_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            analyze_document("Some text", role=LAW_CLERK)

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            assert call_kwargs["system"] == LAW_CLERK.system_prompt

    def test_openai_uses_variant_prompt_for_msa(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("quill.analyzer.openai.OpenAI") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "Analysis."
            mock_resp.choices[0].finish_reason = "stop"
            mock_resp.model = "gpt-4.1-mini"
            mock_resp.usage.prompt_tokens = 100
            mock_resp.usage.completion_tokens = 50
            mock_cls.return_value.chat.completions.create.return_value = mock_resp
            analyze_document("Some text", role=RESEARCH_ASSISTANT, doc_type="msa")

            call_kwargs = mock_cls.return_value.chat.completions.create.call_args.kwargs
            expected = VARIANT_REGISTRY[("Research Assistant", "msa")]
            assert call_kwargs["messages"][0]["content"] == expected

    def test_unknown_doc_type_falls_back_to_generic(
        self, monkeypatch, anthropic_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = anthropic_response
            analyze_document("Some text", role=SENIOR_PARTNER, doc_type="lease")

            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
            assert call_kwargs["system"] == SENIOR_PARTNER.system_prompt

    def test_doc_type_appears_in_span_attributes(self, monkeypatch, anthropic_response):
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

            analyze_document("Some text", doc_type="nda")

            call_kwargs = mock_tracer.start_as_current_span.call_args
            attrs = call_kwargs.kwargs.get("attributes", {})
            assert attrs["quill.doc_type"] == "nda"

    def test_no_doc_type_omits_span_attribute(self, monkeypatch, anthropic_response):
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

            call_kwargs = mock_tracer.start_as_current_span.call_args
            attrs = call_kwargs.kwargs.get("attributes", {})
            assert "quill.doc_type" not in attrs
