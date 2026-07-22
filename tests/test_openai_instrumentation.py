"""Tests for OpenAI auto-instrumentation (QUIL-20)."""

from unittest.mock import patch

import httpx
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import quill.tracing
from quill.tracing import init_tracing, shutdown_tracing


def _reset_otel() -> None:
    """Reset global OTel state so each test gets a fresh provider."""
    quill.tracing._provider = None
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


def setup_function() -> None:
    _reset_otel()


def teardown_function() -> None:
    shutdown_tracing()
    _reset_otel()


def test_openai_instrumentor_activates_alongside_anthropic() -> None:
    """Both instrumentors should be active after init_tracing."""
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

    init_tracing()
    assert AnthropicInstrumentor().is_instrumented_by_opentelemetry
    assert OpenAIInstrumentor().is_instrumented_by_opentelemetry


def test_openai_span_has_gen_ai_system_openai(monkeypatch) -> None:
    """OpenAI span must have gen_ai.system=openai for Beakpoint cost calculation."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    provider = init_tracing()

    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    openai_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4.1-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Test response."},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75,
        },
    }

    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    mock_response = httpx.Response(
        200,
        json=openai_response,
        headers={"content-type": "application/json"},
        request=mock_request,
    )

    import openai

    with patch("httpx.Client.send", return_value=mock_response):
        client = openai.OpenAI(api_key="test-key")
        client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )

    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) > 0

    span = spans[0]
    attrs = dict(span.attributes or {})
    assert attrs["gen_ai.system"] == "openai"


def test_openai_span_includes_token_usage(monkeypatch) -> None:
    """OpenAI span should include non-zero input and output token counts."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    provider = init_tracing()

    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    openai_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4.1-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Token test."},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165,
        },
    }

    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    mock_response = httpx.Response(
        200,
        json=openai_response,
        headers={"content-type": "application/json"},
        request=mock_request,
    )

    import openai

    with patch("httpx.Client.send", return_value=mock_response):
        client = openai.OpenAI(api_key="test-key")
        client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Token test"}],
        )

    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) > 0

    span = spans[0]
    attrs = dict(span.attributes or {})
    assert attrs["gen_ai.usage.input_tokens"] > 0
    assert attrs["gen_ai.usage.output_tokens"] > 0


def test_both_providers_get_correct_gen_ai_system(monkeypatch) -> None:
    """Anthropic spans get gen_ai.system=anthropic, OpenAI spans get openai."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    provider = init_tracing()

    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    from anthropic.types import Message, TextBlock, Usage

    anthropic_api_response = Message(
        id="msg_test",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text="Anthropic response.")],
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
        usage=Usage(input_tokens=100, output_tokens=50),
    )

    anthropic_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    anthropic_http_response = httpx.Response(
        200,
        json=anthropic_api_response.model_dump(),
        headers={"content-type": "application/json"},
        request=anthropic_request,
    )

    openai_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4.1-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "OpenAI response."},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 80,
            "completion_tokens": 30,
            "total_tokens": 110,
        },
    }
    openai_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    openai_http_response = httpx.Response(
        200,
        json=openai_response,
        headers={"content-type": "application/json"},
        request=openai_request,
    )

    import anthropic
    import openai

    def route_send(request: httpx.Request, **kwargs: object) -> httpx.Response:
        if "anthropic" in str(request.url):
            return anthropic_http_response
        return openai_http_response

    with patch("httpx.Client.send", side_effect=route_send):
        anthropic_client = anthropic.Anthropic(api_key="test-key")
        anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello Anthropic"}],
        )

        openai_client = openai.OpenAI(api_key="test-key")
        openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Hello OpenAI"}],
        )

    provider.force_flush()
    spans = exporter.get_finished_spans()

    system_values = {dict(s.attributes or {}).get("gen_ai.system") for s in spans}
    assert "anthropic" in system_values
    assert "openai" in system_values


def test_resource_does_not_set_gen_ai_system() -> None:
    """Resource-level gen_ai.system must be absent so span-level values win."""
    provider = init_tracing()
    assert "gen_ai.system" not in provider.resource.attributes
