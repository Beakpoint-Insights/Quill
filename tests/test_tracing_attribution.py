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


def test_namespace_is_always_quill():
    """service.namespace is always 'quill' regardless of flags."""
    provider = init_tracing(project="Acme", department="M&A")
    assert provider.resource.attributes["service.namespace"] == "quill"


def test_namespace_quill_without_flags(monkeypatch):
    """service.namespace is 'quill' even with no flags."""
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    provider = init_tracing()
    assert provider.resource.attributes["service.namespace"] == "quill"


def test_project_sets_service_name():
    """--project sets service.name."""
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["service.name"] == "Acme-Acquisition"


def test_default_service_name_without_project(monkeypatch):
    """service.name defaults to 'quill' when --project is not set."""
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    provider = init_tracing()
    assert provider.resource.attributes["service.name"] == "quill"


def test_project_takes_precedence_over_env_var(monkeypatch):
    """--project overrides OTEL_SERVICE_NAME env var."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "quill-from-env")
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["service.name"] == "Acme-Acquisition"


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
    assert "app.user.org.id" not in attrs


def test_gen_ai_system_is_anthropic():
    """gen_ai.system is always 'anthropic'."""
    provider = init_tracing(project="Acme")
    assert provider.resource.attributes["gen_ai.system"] == "anthropic"


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
