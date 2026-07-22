"""End-to-end tests verifying attribution flows through to exported spans (QUIL-17).

Each test runs in a subprocess to get truly fresh OTel global state.
"""

import os
import subprocess
import sys

import pytest


def _run_attribution_check(script: str) -> None:
    """Run a Python script in a subprocess and assert it exits cleanly."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_EXPORTER")}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestProjectAttribution:
    """Verify --project maps to service.name on exported spans."""

    def test_project_sets_service_name_on_spans(self):
        """Exported spans carry service.name from --project."""
        _run_attribution_check("""
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from quill.tracing import init_tracing

provider = init_tracing(project="Acme-Acquisition")
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))

tracer = provider.get_tracer("test")
with tracer.start_as_current_span("test-span"):
    pass
provider.force_flush()

spans = exporter.get_finished_spans()
assert len(spans) > 0, "No spans exported"
for span in spans:
    assert span.resource.attributes["service.name"] == "Acme-Acquisition"
""")


class TestDepartmentAttribution:
    """Verify --department maps to app.user.org.id on analyzer spans."""

    def test_department_on_analyze_span(self):
        """app.user.org.id is set on quill.analyze spans."""
        _run_attribution_check("""
from unittest.mock import patch
from anthropic.types import Message, TextBlock, Usage
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from quill.tracing import init_tracing
from quill.cache import ResponseCache
import tempfile, pathlib

provider = init_tracing(project="Test-Project", department="M&A")
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))

mock_response = Message(
    id="msg_test", type="message", role="assistant",
    content=[TextBlock(type="text", text="Analysis result.")],
    model="claude-sonnet-4-20250514",
    stop_reason="end_turn",
    usage=Usage(input_tokens=100, output_tokens=50),
)

tmp = tempfile.mkdtemp()
cache = ResponseCache(cache_dir=pathlib.Path(tmp) / "cache")

with patch("anthropic.Anthropic") as mock_cls, \\
     patch("quill.analyzer.ResponseCache", return_value=cache):
    mock_cls.return_value.messages.create.return_value = mock_response
    from quill.analyzer import analyze_document
    analyze_document("Test legal document.", api_key="test-key")

provider.force_flush()
spans = exporter.get_finished_spans()

analyze_spans = [s for s in spans if s.name == "quill.analyze"]
assert len(analyze_spans) == 1, f"Expected 1 analyze span, got {len(analyze_spans)}"
attrs = dict(analyze_spans[0].attributes)
assert attrs["app.user.org.id"] == "M&A", f"Got {attrs.get('app.user.org.id')!r}"
""")

    def test_department_not_on_resource(self):
        """app.user.org.id is NOT a resource attribute."""
        _run_attribution_check("""
from quill.tracing import init_tracing

provider = init_tracing(project="Test", department="M&A")
attrs = provider.resource.attributes
assert "app.user.org.id" not in attrs, "department should be span-level only"
""")


class TestNamespaceAlwaysQuill:
    """Verify service.namespace is always 'quill'."""

    def test_namespace_always_quill(self):
        """service.namespace is 'quill' regardless of flags."""
        _run_attribution_check("""
from quill.tracing import init_tracing

provider = init_tracing(project="Acme", department="M&A")
assert provider.resource.attributes["service.namespace"] == "quill"
""")

    def test_namespace_quill_without_flags(self):
        """service.namespace is 'quill' with no flags."""
        _run_attribution_check("""
import os
os.environ.pop("OTEL_SERVICE_NAME", None)
from quill.tracing import init_tracing

provider = init_tracing()
assert provider.resource.attributes["service.namespace"] == "quill"
""")


class TestFullPipeline:
    """Verify the complete attribution pipeline end-to-end."""

    def test_all_attributes_correct(self):
        """Full pipeline: service.name from project, service.namespace
        is quill, app.user.org.id from department on spans."""
        _run_attribution_check("""
from unittest.mock import patch
from anthropic.types import Message, TextBlock, Usage
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from quill.tracing import init_tracing
from quill.cache import ResponseCache
import tempfile, pathlib

provider = init_tracing(project="Acme-Acquisition", department="Litigation")
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))

mock_response = Message(
    id="msg_test", type="message", role="assistant",
    content=[TextBlock(type="text", text="Analysis.")],
    model="claude-sonnet-4-20250514",
    stop_reason="end_turn",
    usage=Usage(input_tokens=100, output_tokens=50),
)

tmp = tempfile.mkdtemp()
cache = ResponseCache(cache_dir=pathlib.Path(tmp) / "cache")

with patch("anthropic.Anthropic") as mock_cls, \\
     patch("quill.analyzer.ResponseCache", return_value=cache):
    mock_cls.return_value.messages.create.return_value = mock_response
    from quill.analyzer import analyze_document
    analyze_document("Test document.", api_key="test-key")

provider.force_flush()
spans = exporter.get_finished_spans()
assert len(spans) > 0

# Resource attributes (same on all spans)
for span in spans:
    r = span.resource.attributes
    assert r["service.name"] == "Acme-Acquisition"
    assert r["service.namespace"] == "quill"
    assert "app.user.org.id" not in r

# Span-level attribute on quill.analyze
analyze_span = [s for s in spans if s.name == "quill.analyze"][0]
attrs = dict(analyze_span.attributes)
assert attrs["app.user.org.id"] == "Litigation"
assert "quill.role" in attrs
assert "quill.model" in attrs
""")
