"""End-to-end tests verifying attribution flows through to exported spans (QUIL-17).

These tests confirm that --project and --department values propagate all the
way through the tracing pipeline and appear as resource attributes on every
exported span, matching what Beakpoint would see.

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
    val = span.resource.attributes.get("service.name")
    assert val == "Acme-Acquisition", f"Expected 'Acme-Acquisition', got {val!r}"
""")

    def test_project_with_spaces_and_special_chars(self):
        """Project names with spaces and special characters are preserved."""
        _run_attribution_check("""
from quill.tracing import init_tracing

provider = init_tracing(project="Project With Spaces & Special-Chars")
val = provider.resource.attributes.get("service.name")
assert val == "Project With Spaces & Special-Chars", f"Got {val!r}"
""")


class TestDepartmentAttribution:
    """Verify --department overrides service.namespace on exported spans."""

    def test_department_sets_namespace_on_spans(self):
        """Exported spans carry service.namespace from --department."""
        _run_attribution_check("""
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from quill.tracing import init_tracing

provider = init_tracing(department="M&A")
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))

tracer = provider.get_tracer("test")
with tracer.start_as_current_span("test-span"):
    pass
provider.force_flush()

spans = exporter.get_finished_spans()
assert len(spans) > 0, "No spans exported"
for span in spans:
    val = span.resource.attributes.get("service.namespace")
    assert val == "M&A", f"Expected 'M&A', got {val!r}"
""")

    def test_default_namespace_is_quill(self):
        """service.namespace defaults to 'quill' without --department."""
        _run_attribution_check("""
from quill.tracing import init_tracing

provider = init_tracing()
val = provider.resource.attributes.get("service.namespace")
assert val == "quill", f"Expected 'quill', got {val!r}"
""")


class TestCombinedAttribution:
    """Verify both attributes work together end-to-end."""

    def test_both_attributes_on_every_span(self):
        """service.name and service.namespace are both set correctly."""
        _run_attribution_check("""
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from quill.tracing import init_tracing

provider = init_tracing(project="Acme-Acquisition", department="M&A")
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))

tracer = provider.get_tracer("test")
with tracer.start_as_current_span("test-span"):
    pass
provider.force_flush()

spans = exporter.get_finished_spans()
assert len(spans) > 0, "No spans exported"
for span in spans:
    attrs = span.resource.attributes
    assert attrs["service.name"] == "Acme-Acquisition"
    assert attrs["service.namespace"] == "M&A"
""")

    def test_version_preserved_alongside_attribution(self):
        """service.version is still present with attribution flags."""
        _run_attribution_check("""
from quill.tracing import init_tracing

provider = init_tracing(project="Test", department="Legal")
attrs = provider.resource.attributes
assert "service.version" in attrs, "Missing service.version"
""")

    def test_no_project_keeps_default_service_name(self):
        """Without --project, service.name uses default or env var."""
        _run_attribution_check("""
import os
os.environ.pop("OTEL_SERVICE_NAME", None)
from quill.tracing import init_tracing

provider = init_tracing()
attrs = provider.resource.attributes
assert attrs["service.name"] == "quill"
assert attrs["service.namespace"] == "quill"
""")


class TestAnalyzerSpansWithAttribution:
    """Verify analyzer spans carry correct resource attributes."""

    def test_quill_analyze_span_carries_attribution(self):
        """The quill.analyze span has attribution in its resource."""
        _run_attribution_check("""
from unittest.mock import patch
from anthropic.types import Message, TextBlock, Usage
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from quill.tracing import init_tracing
from quill.cache import ResponseCache

provider = init_tracing(project="Test-Project", department="Legal")
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))

mock_response = Message(
    id="msg_test", type="message", role="assistant",
    content=[TextBlock(type="text", text="Analysis result.")],
    model="claude-sonnet-4-20250514",
    stop_reason="end_turn",
    usage=Usage(input_tokens=100, output_tokens=50),
)

import tempfile, pathlib
tmp = tempfile.mkdtemp()
cache = ResponseCache(cache_dir=pathlib.Path(tmp) / "cache")

with patch("anthropic.Anthropic") as mock_cls, \\
     patch("quill.analyzer.ResponseCache", return_value=cache):
    mock_cls.return_value.messages.create.return_value = mock_response
    from quill.analyzer import analyze_document
    analyze_document("Test legal document.", api_key="test-key")

provider.force_flush()
spans = exporter.get_finished_spans()
span_names = [s.name for s in spans]
assert "quill.analyze" in span_names, f"Missing quill.analyze in {span_names}"

for span in spans:
    attrs = span.resource.attributes
    assert attrs["service.name"] == "Test-Project"
    assert attrs["service.namespace"] == "Legal"

analyze_span = [s for s in spans if s.name == "quill.analyze"][0]
span_attrs = dict(analyze_span.attributes)
assert "quill.role" in span_attrs, f"Missing quill.role in {span_attrs}"
assert "quill.model" in span_attrs, f"Missing quill.model in {span_attrs}"
""")
