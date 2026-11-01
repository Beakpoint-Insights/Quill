from unittest.mock import patch

import httpx
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import quill.tracing
from quill.tracing import init_tracing, shutdown_tracing


def _reset_otel():
    """Reset global OTel state so each test gets a fresh provider."""
    quill.tracing._provider = None
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


def setup_function():
    _reset_otel()


def teardown_function():
    shutdown_tracing()
    _reset_otel()


def test_init_creates_tracer_provider():
    provider = init_tracing()
    assert isinstance(provider, TracerProvider)
    assert trace.get_tracer_provider() is provider


def test_service_name_is_always_quill(monkeypatch):
    monkeypatch.delenv("QUILL_PROJECT", raising=False)
    provider = init_tracing()
    assert provider.resource.attributes.get("service.name") == "quill"


def test_project_sets_quill_project():
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes.get("service.name") == "quill"
    assert provider.resource.attributes.get("quill.project") == "Acme-Acquisition"


def test_anthropic_instrumentation_produces_spans(monkeypatch, anthropic_response):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    provider = init_tracing()

    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    mock_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    mock_response = httpx.Response(
        200,
        json=anthropic_response.model_dump(),
        headers={"content-type": "application/json"},
        request=mock_request,
    )

    import anthropic

    with patch("httpx.Client.send", return_value=mock_response):
        client = anthropic.Anthropic(api_key="test-key")
        client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello"}],
        )

    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) > 0

    span = spans[0]
    attrs = dict(span.attributes)
    provider_name = attrs.get("gen_ai.system") or attrs.get("gen_ai.provider.name")
    assert provider_name == "anthropic"
    input_tokens = attrs.get("gen_ai.usage.input_tokens") or attrs.get(
        "gen_ai.response.input_tokens", 0
    )
    output_tokens = attrs.get("gen_ai.usage.output_tokens") or attrs.get(
        "gen_ai.response.output_tokens", 0
    )
    assert input_tokens > 0
    assert output_tokens > 0


def test_shutdown_is_clean():
    init_tracing()
    shutdown_tracing()


def test_no_exporter_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    with patch("quill.tracing.OTLPSpanExporter") as exporter:
        init_tracing()
    exporter.assert_not_called()


def test_base_endpoint_lets_the_sdk_append_v1_traces(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otel.beakpoint.io")
    with patch("quill.tracing.OTLPSpanExporter") as exporter:
        init_tracing()
    exporter.assert_called_once_with()


def test_traces_endpoint_is_read_by_the_sdk(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://otel.beakpoint.io/v1/traces"
    )
    with patch("quill.tracing.OTLPSpanExporter") as exporter:
        init_tracing()
    exporter.assert_called_once_with()


def test_legacy_full_traces_url_is_used_as_is(monkeypatch):
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "https://otel.beakpoint.io/api/traces"
    )
    with patch("quill.tracing.OTLPSpanExporter") as exporter:
        init_tracing()
    exporter.assert_called_once_with(endpoint="https://otel.beakpoint.io/api/traces")
