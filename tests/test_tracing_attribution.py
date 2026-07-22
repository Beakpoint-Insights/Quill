"""Tests for OTel resource attribute attribution (QUIL-14)."""

from opentelemetry import trace

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


def test_default_namespace_is_quill(monkeypatch):
    """service.namespace defaults to 'quill' when no flags are set."""
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    provider = init_tracing()
    assert provider.resource.attributes["service.namespace"] == "quill"


def test_department_overrides_namespace():
    """--department overrides service.namespace from 'quill'."""
    provider = init_tracing(department="M&A")
    assert provider.resource.attributes["service.namespace"] == "M&A"


def test_project_sets_service_name():
    """--project sets service.name."""
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["service.name"] == "Acme-Acquisition"


def test_both_flags_together():
    """Both flags set their respective attributes."""
    provider = init_tracing(project="Acme-Acquisition", department="M&A")
    attrs = provider.resource.attributes
    assert attrs["service.name"] == "Acme-Acquisition"
    assert attrs["service.namespace"] == "M&A"


def test_namespace_stays_quill_with_only_project(monkeypatch):
    """service.namespace remains 'quill' when only --project is set."""
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    provider = init_tracing(project="Widget-Deal")
    attrs = provider.resource.attributes
    assert attrs["service.name"] == "Widget-Deal"
    assert attrs["service.namespace"] == "quill"


def test_project_takes_precedence_over_env_var(monkeypatch):
    """--project overrides OTEL_SERVICE_NAME env var."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "quill-from-env")
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["service.name"] == "Acme-Acquisition"


def test_env_var_used_when_no_project(monkeypatch):
    """OTEL_SERVICE_NAME env var is used when --project is not set."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "quill-staging")
    provider = init_tracing()
    assert provider.resource.attributes["service.name"] == "quill-staging"


def test_attributes_on_resource_not_spans():
    """Attribution attributes are on the resource, not per-span."""
    provider = init_tracing(project="Test-Project", department="Legal")
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        span_attrs = dict(span.attributes) if span.attributes else {}
        assert "service.name" not in span_attrs
        assert "service.namespace" not in span_attrs
    attrs = provider.resource.attributes
    assert attrs["service.name"] == "Test-Project"
    assert attrs["service.namespace"] == "Legal"


def test_service_version_always_present():
    """service.version is always set regardless of flags."""
    provider = init_tracing(project="Acme", department="R&D")
    assert "service.version" in provider.resource.attributes
