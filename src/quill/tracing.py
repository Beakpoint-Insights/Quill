"""OpenTelemetry tracing setup for Quill."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

__all__ = ["init_tracing", "shutdown_tracing"]

_provider: TracerProvider | None = None


def init_tracing(
    *,
    project: str | None = None,
    department: str | None = None,
) -> TracerProvider:
    """Initialize OpenTelemetry tracing.

    Idempotent: returns the existing provider if already initialized.

    Args:
        project: Project or matter name set as ``service.name`` so
            Beakpoint can slice costs by project.
        department: Department name. When provided, replaces the
            default ``service.namespace`` value of ``"quill"``.

    Returns:
        The active TracerProvider.
    """
    global _provider
    if _provider is not None:
        return _provider

    from quill import __version__

    service_name = project or os.environ.get("OTEL_SERVICE_NAME", "quill")
    namespace = department or "quill"
    attributes: dict[str, str] = {
        "service.name": service_name,
        "service.namespace": namespace,
        "service.version": __version__,
    }
    resource = Resource.create(attributes)

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
    """Shut down the tracer provider and flush pending spans."""
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
