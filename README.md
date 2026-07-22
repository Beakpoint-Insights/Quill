# Quill

[![Lint](https://github.com/Beakpoint-Insights/Quill/actions/workflows/lint.yml/badge.svg)](https://github.com/Beakpoint-Insights/Quill/actions/workflows/lint.yml)
[![Test](https://github.com/Beakpoint-Insights/Quill/actions/workflows/test.yml/badge.svg)](https://github.com/Beakpoint-Insights/Quill/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

AI-powered legal document analyzer that routes work across multiple LLM providers and model tiers, mirroring how a law firm staffs tasks from clerk to senior partner.

Built to showcase [Beakpoint](https://beakpoint.io) token usage tracking, multi-model cost attribution, and per-project spend analysis using real OpenTelemetry instrumentation.

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

## Installation

```bash
uv venv
uv pip install -e .
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Copy `.env.example` or create a `.env` file in the project root:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.beakpoint.io/api/traces
OTEL_EXPORTER_OTLP_HEADERS=x-bkpt-key=your-key
OTEL_SERVICE_NAME=quill
```

The `.env` file is loaded automatically at startup and is excluded from version control.

## Usage

```bash
quill analyze path/to/document.txt
```

Supported file formats: plain text, Markdown, PDF.

### Options

```
quill --help          Show usage
quill --version       Show version
quill -v analyze ...  Enable debug logging (shows OTel export activity)
```

### Response Cache

Quill caches raw API responses in `cache/responses/` to avoid redundant API calls during development. The cache key is a hash of the model, system prompt, and document text. Delete a cached JSON file to force a fresh API call.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key | Yes |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Full OTLP traces endpoint URL | No |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP auth headers (e.g. `x-bkpt-key=...`) | No |
| `OTEL_SERVICE_NAME` | Service name for traces (default: `quill`) | No |

## OpenTelemetry & Beakpoint Integration

Quill instruments every Anthropic API call with [OpenTelemetry](https://opentelemetry.io/) and exports traces to [Beakpoint](https://beakpoint.io) for per-model, per-project cost attribution. This section explains how the pieces fit together so you can follow the pattern in your own application.

### How tracing is initialized

All OTel setup lives in [`src/quill/tracing.py`](src/quill/tracing.py). The `init_tracing()` function does three things:

1. **Creates a `Resource`** — a bundle of key-value pairs that describe *this service* and are attached to every span it exports.
2. **Builds a `TracerProvider`** with an OTLP exporter — the provider is the SDK entry point; the exporter sends spans over HTTP to whatever endpoint you configure.
3. **Activates auto-instrumentation** — the `AnthropicInstrumentor` monkey-patches the Anthropic SDK so every `client.messages.create()` call automatically produces a span with token counts, model name, and other `gen_ai.*` attributes.

```
init_tracing()
  │
  ├─ Resource (service.name, service.namespace, service.version, gen_ai.system)
  │
  ├─ TracerProvider ──► BatchSpanProcessor ──► OTLPSpanExporter
  │                                             (sends to OTEL_EXPORTER_OTLP_ENDPOINT)
  │
  └─ AnthropicInstrumentor.instrument()
       (patches anthropic.Anthropic so every API call emits a span)
```

The CLI ([`src/quill/cli.py`](src/quill/cli.py)) calls `init_tracing()` at startup and registers `shutdown_tracing()` via `atexit` so pending spans are flushed on exit.

### What spans are emitted

Every `quill analyze` invocation produces a trace with two layers of spans:

| Span | Created by | Purpose |
|---|---|---|
| `quill.analyze` (or `quill.analyze_all`) | Application code in [`analyzer.py`](src/quill/analyzer.py) | Orchestration span — wraps the full analysis lifecycle including cache lookup |
| `anthropic.chat` | Auto-instrumentation (`AnthropicInstrumentor`) | Child span for each `client.messages.create()` call — carries token counts and model info |

The `anthropic.chat` spans are created automatically. You never write code for them — the instrumentor intercepts every SDK call.

### Attributes that Beakpoint uses

Beakpoint reads specific OpenTelemetry attributes to calculate costs and let you slice spend by project, environment, and team. Here is every attribute Quill sets, where it is set, and why.

#### Resource attributes (set once at startup, attached to all spans)

These are configured in `init_tracing()` when building the `Resource`:

| Attribute | Value in Quill | Beakpoint purpose |
|---|---|---|
| `service.name` | `--project` flag (e.g. `Acme-Acquisition`) | **Cost attribution** — slice spend by project/matter |
| `service.namespace` | `quill` (hardcoded) | **Cost attribution** — group related services |
| `service.version` | Package version (`0.1.0`) | **Cost attribution** — compare spend across releases |
| `gen_ai.system` | `anthropic` | **Cost calculation** — tells Beakpoint which provider's pricing table to use |

#### Span attributes (set per-span by application code)

These are set in `analyze_document()` and `analyze_document_all_roles()` in [`analyzer.py`](src/quill/analyzer.py):

| Attribute | Value in Quill | Beakpoint purpose |
|---|---|---|
| `code.function.name` | Fully-qualified function name | **Cost attribution** — see which code path incurred cost |
| `app.user.org.id` | `--department` flag (e.g. `M&A`) | **Cost attribution** — slice spend by department/team |
| `quill.role` | Role name (e.g. `Senior Partner`) | Application-specific (not read by Beakpoint) |
| `quill.model` | Model identifier | Application-specific (not read by Beakpoint) |
| `quill.cache.hit` | `true` / `false` | Application-specific (not read by Beakpoint) |

#### Span attributes (set automatically by the instrumentation library)

The `opentelemetry-instrumentation-anthropic` package sets these on every `anthropic.chat` span without any code from you:

| Attribute | Example value | Beakpoint purpose |
|---|---|---|
| `gen_ai.system` | `anthropic` | **Cost calculation** — provider identification |
| `gen_ai.request.model` | `claude-sonnet-4-6` | **Cost calculation** — determines per-token price |
| `gen_ai.response.model` | `claude-sonnet-4-6-20250514` | **Cost calculation** — exact model version (takes precedence over request model for pricing) |
| `gen_ai.usage.input_tokens` | `512` | **Cost calculation** — input token count |
| `gen_ai.usage.output_tokens` | `128` | **Cost calculation** — output token count |
| `gen_ai.usage.input_tokens.cache_creation` | `100` | **Cost calculation** — tokens written to prompt cache (billed at premium rate) |
| `gen_ai.usage.input_tokens.cache_read` | `400` | **Cost calculation** — tokens read from cache (reduced rate) |

### Configuring Beakpoint as the trace destination

Beakpoint receives traces via the standard OTLP/HTTP protocol. No Beakpoint-specific SDK is needed — you just point the OTel exporter at Beakpoint's endpoint and authenticate with a header.

Set these environment variables (or add them to `.env`):

```bash
# Where to send traces (Beakpoint's OTLP ingest endpoint)
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.beakpoint.io/api/traces

# Authenticate with your Beakpoint API key
OTEL_EXPORTER_OTLP_HEADERS=x-bkpt-key=bpk_your_key_here
```

The `OTLPSpanExporter` in `tracing.py` reads `OTEL_EXPORTER_OTLP_ENDPOINT` automatically. If the variable is unset, no exporter is added and spans are silently discarded — so the app works fine without Beakpoint, just without trace export.

### Summary: what you need to replicate this in your own app

1. **Install the OTel SDK and an instrumentation library** for your LLM provider:
   ```
   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
   pip install opentelemetry-instrumentation-anthropic   # or opentelemetry-instrumentation-openai-v2
   ```

2. **Set `gen_ai.system` as a resource attribute** — tells Beakpoint which pricing table to apply.

3. **Call `.instrument()` on the instrumentor** — this gives you `gen_ai.usage.*` token counts and model names on every LLM call for free.

4. **Set `service.name`** to whatever you want to group costs by (project, service, team).

5. **Point the exporter at Beakpoint** — set `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS`.

6. **Add span-level attribution attributes** where useful — `app.user.org.id` for department, `code.function.name` for function-level cost breakdown.

Use `quill -v analyze ...` to see export activity in the console.

## License

See [LICENSE](LICENSE).
