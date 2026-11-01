"""Tests for OTel resource attribute attribution (QUIL-14)."""

from opentelemetry import trace

import quill.tracing
from quill.tracing import get_department, init_tracing, shutdown_tracing


def _reset_otel():
    """Reset global OTel state so each test gets a fresh provider."""
    quill.tracing._provider = None
    quill.tracing._department = None
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


def setup_function():
    _reset_otel()


def teardown_function():
    shutdown_tracing()
    _reset_otel()


def test_service_name_is_always_quill():
    """service.name is always 'quill' regardless of flags."""
    provider = init_tracing(project="Acme", department="M&A")
    assert provider.resource.attributes["service.name"] == "quill"


def test_service_name_quill_without_flags(monkeypatch):
    """service.name is 'quill' even with no flags."""
    monkeypatch.delenv("QUILL_PROJECT", raising=False)
    provider = init_tracing()
    assert provider.resource.attributes["service.name"] == "quill"


def test_project_sets_quill_project():
    """--project sets quill.project."""
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["quill.project"] == "Acme-Acquisition"


def test_default_no_quill_project_without_project(monkeypatch):
    """quill.project is absent when --project is not set."""
    monkeypatch.delenv("QUILL_PROJECT", raising=False)
    provider = init_tracing()
    assert "quill.project" not in provider.resource.attributes


def test_project_takes_precedence_over_env_var(monkeypatch):
    """--project overrides QUILL_PROJECT env var."""
    monkeypatch.setenv("QUILL_PROJECT", "quill-from-env")
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["quill.project"] == "Acme-Acquisition"


def test_department_stored_for_span_use():
    """--department is stored via get_department() for span-level use."""
    init_tracing(department="M&A")
    assert get_department() == "M&A"


def test_department_none_when_omitted():
    """get_department() returns None when --department is not set."""
    init_tracing()
    assert get_department() is None


def test_department_not_on_resource():
    """Department is NOT set as a resource attribute."""
    provider = init_tracing(department="M&A")
    attrs = provider.resource.attributes
    assert "department" not in attrs


def test_gen_ai_system_not_on_resource():
    """gen_ai.system must not be set at resource level (set per-span instead)."""
    provider = init_tracing(project="Acme")
    assert "gen_ai.system" not in provider.resource.attributes


def test_service_version_always_present():
    """service.version is always set regardless of flags."""
    provider = init_tracing(project="Acme", department="R&D")
    assert "service.version" in provider.resource.attributes


def test_shutdown_clears_department():
    """shutdown_tracing() clears the stored department."""
    init_tracing(department="M&A")
    assert get_department() == "M&A"
    shutdown_tracing()
    assert get_department() is None


def test_processor_propagates_department_to_child_spans():
    """SpanProcessor injects department onto auto-instrumented spans."""
    init_tracing(department="Marketing")
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span(
        "anthropic.chat",
        attributes={"gen_ai.provider.name": "anthropic"},
    ) as span:
        assert span.attributes["department"] == "Marketing"


def test_processor_skips_department_when_not_set():
    """SpanProcessor does not inject department when department is None."""
    init_tracing()
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span(
        "anthropic.chat",
        attributes={"gen_ai.provider.name": "anthropic"},
    ) as span:
        assert "department" not in span.attributes


def test_processor_sets_cloud_provider_from_gen_ai_provider_name():
    """SpanProcessor sets cloud.provider from gen_ai.provider.name."""
    init_tracing()
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span(
        "anthropic.chat",
        attributes={"gen_ai.provider.name": "anthropic"},
    ) as span:
        assert span.attributes["cloud.provider"] == "anthropic"


def test_processor_sets_cloud_provider_openai():
    """SpanProcessor sets cloud.provider to openai for OpenAI spans."""
    init_tracing()
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span(
        "openai.chat",
        attributes={"gen_ai.provider.name": "openai"},
    ) as span:
        assert span.attributes["cloud.provider"] == "openai"
