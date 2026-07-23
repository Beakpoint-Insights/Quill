"""OpenTelemetry tracing setup for Quill."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

__all__ = ["get_department", "init_tracing", "shutdown_tracing"]

_provider: TracerProvider | None = None
_department: str | None = None


class _GenAiSystemProcessor(SpanProcessor):
    """Enrich auto-instrumented GenAI spans on start.

    - Copies ``gen_ai.provider.name`` to ``gen_ai.system`` (Beakpoint
      cost calculation requires ``gen_ai.system``).
    - Propagates ``app.user.org.id`` (department) from the module-level
      ``_department`` so that every LLM span carries the attribution tag,
      not only the parent ``quill.analyze`` span.
    - Sets ``cloud.provider`` from the resolved provider name.
    """

    def on_start(self, span: Span, parent_context: object = None) -> None:
        attrs = span.attributes
        if attrs is None:
            return
        provider_name = attrs.get("gen_ai.provider.name")
        if provider_name:
            provider_str = str(provider_name)
            if not attrs.get("gen_ai.system"):
                span.set_attribute("gen_ai.system", provider_str)
            if not attrs.get("cloud.provider"):
                span.set_attribute("cloud.provider", provider_str)
        if _department is not None and not attrs.get("app.user.org.id"):
            span.set_attribute("app.user.org.id", _department)

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def get_department() -> str | None:
    """Return the department set during initialization.

    Returns:
        The department string, or None if not set.
    """
    return _department


def init_tracing(
    *,
    project: str | None = None,
    department: str | None = None,
) -> TracerProvider:
    """Initialize OpenTelemetry tracing.

    Idempotent: returns the existing provider if already initialized.

    Args:
        project: Project or matter name set as ``service.name``.
        department: Department name stored for ``app.user.org.id``
            span-level attribution.

    Returns:
        The active TracerProvider.
    """
    global _provider, _department
    if _provider is not None:
        return _provider

    _department = department

    from quill import __version__

    service_name = project or os.environ.get("OTEL_SERVICE_NAME", "quill")
    attributes: dict[str, str] = {
        "service.name": service_name,
        "service.namespace": "quill",
        "service.version": __version__,
    }
    resource = Resource.create(attributes)

    _provider = TracerProvider(resource=resource)
    _provider.add_span_processor(_GenAiSystemProcessor())

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)
    instrumentor = AnthropicInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    instrumentor.instrument(tracer_provider=_provider)

    openai_instrumentor = OpenAIInstrumentor()  # type: ignore[no-untyped-call]
    if openai_instrumentor.is_instrumented_by_opentelemetry:
        openai_instrumentor.uninstrument()
    openai_instrumentor.instrument(tracer_provider=_provider)

    return _provider


def shutdown_tracing() -> None:
    """Shut down the tracer provider and flush pending spans."""
    global _provider, _department
    if _provider is not None:
        _provider.shutdown()
        _provider = None
    _department = None
