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


def test_department_sets_service_namespace():
    """service.namespace resource attribute is set from --department."""
    provider = init_tracing(department="M&A")
    assert provider.resource.attributes["service.namespace"] == "M&A"


def test_project_sets_beakpoint_project():
    """beakpoint.project resource attribute is set from --project."""
    provider = init_tracing(project="Acme-Acquisition")
    assert provider.resource.attributes["beakpoint.project"] == "Acme-Acquisition"


def test_both_attributes_set_together():
    """Both attributes are present when both flags are provided."""
    provider = init_tracing(project="Acme-Acquisition", department="M&A")
    attrs = provider.resource.attributes
    assert attrs["service.namespace"] == "M&A"
    assert attrs["beakpoint.project"] == "Acme-Acquisition"


def test_no_namespace_when_department_omitted():
    """service.namespace is absent when --department is not provided."""
    provider = init_tracing()
    assert "service.namespace" not in provider.resource.attributes


def test_no_project_when_project_omitted():
    """beakpoint.project is absent when --project is not provided."""
    provider = init_tracing()
    assert "beakpoint.project" not in provider.resource.attributes


def test_only_department_sets_only_namespace():
    """Only service.namespace is set when only --department is provided."""
    provider = init_tracing(department="Litigation")
    attrs = provider.resource.attributes
    assert attrs["service.namespace"] == "Litigation"
    assert "beakpoint.project" not in attrs


def test_only_project_sets_only_project():
    """Only beakpoint.project is set when only --project is provided."""
    provider = init_tracing(project="Widget-Deal")
    attrs = provider.resource.attributes
    assert attrs["beakpoint.project"] == "Widget-Deal"
    assert "service.namespace" not in attrs


def test_attributes_on_tracer_provider_resource():
    """Attributes are set on the TracerProvider resource, not per-span."""
    provider = init_tracing(project="Test-Project", department="Legal")
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        span_attrs = dict(span.attributes) if span.attributes else {}
        assert "beakpoint.project" not in span_attrs
        assert "service.namespace" not in span_attrs
    resource_attrs = provider.resource.attributes
    assert resource_attrs["beakpoint.project"] == "Test-Project"
    assert resource_attrs["service.namespace"] == "Legal"


def test_base_attributes_still_present_with_attribution():
    """service.name and service.version are still set alongside attribution."""
    provider = init_tracing(project="Acme", department="R&D")
    attrs = provider.resource.attributes
    assert attrs["service.name"] == "quill"
    assert "service.version" in attrs
