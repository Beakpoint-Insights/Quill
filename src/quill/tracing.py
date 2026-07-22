import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_provider: TracerProvider | None = None


def init_tracing() -> TracerProvider:
    global _provider

    from quill import __version__

    service_name = os.environ.get("OTEL_SERVICE_NAME", "quill")
    resource = Resource.create({
        "service.name": service_name,
        "service.version": __version__,
    })

    _provider = TracerProvider(resource=resource)

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)
    instrumentor = AnthropicInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    instrumentor.instrument(tracer_provider=_provider)

    return _provider


def shutdown_tracing() -> None:
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
