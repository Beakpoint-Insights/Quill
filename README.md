# Quill

[![Lint](https://github.com/Beakpoint-Insights/Quill/actions/workflows/lint.yml/badge.svg)](https://github.com/Beakpoint-Insights/Quill/actions/workflows/lint.yml)
[![Test](https://github.com/Beakpoint-Insights/Quill/actions/workflows/test.yml/badge.svg)](https://github.com/Beakpoint-Insights/Quill/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

![Winston, a colorful animated bird, is Beakpoint's mascot. Here, he's pretending to be a lawyer.](images/Winston%20the%20Lawyer.jpeg "Winston")

AI-powered legal document analyzer that routes work across multiple LLM providers and model tiers, mirroring how a law firm staffs tasks from clerk to senior partner.

## Showcasing Beakpoint LLM cost attribution and usage tracking

This is built to showcase [Beakpoint](https://beakpoint.io) token usage tracking, multi-model cost attribution, and per-project spend analysis using real OpenTelemetry instrumentation.

Consider this scenario: your company has built a legal document review tool that uses multiple LLM providers and model tiers. You want to know how much each department is spending, which LLM provider is the most expensive, and which project is driving the most cost. Quill demonstrates how to instrument your LLM calls with OpenTelemetry and export traces to Beakpoint for this kind of analysis.

| Cost by Department                                                                                                                                         | Cost by LLM Provider                                                                                                                        | Cost by Project                                                                                                                                   |
|------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| [![Cost Breakdown By Department.png](images/thumbnails/Cost%20Breakdown%20By%20Department.png)](images/screenshots/Cost%20Breakdown%20By%20Department.png) | [![Cost Breakdown by Model.png](images/thumbnails/Cost%20Breakdown%20by%20Model.png)](images/screenshots/Cost%20Breakdown%20by%20Model.png) | [![Cost Breakdown by Project.png](images/thumbnails/Cost%20Breakdown%20by%20Project.png)](images/screenshots/Cost%20Breakdown%20by%20Project.png) |
| The tax team is the heaviest user of Quill.                                                                                                                | Anthropic is the most expensive LLM provider                                                                                                | The "Review new Services Agreement" project is the most expensive.                                                                                |


> [!IMPORTANT]
> This application isn't really meant to give you legal advice. It's a demo of how to instrument LLM calls for cost attribution and usage tracking. Relying on it to make legal decisions is a bad idea.

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)
- An [OpenAI API key](https://platform.openai.com/api-keys)

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
OPENAI_API_KEY=sk-...
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.beakpoint.io/api/traces
OTEL_EXPORTER_OTLP_HEADERS=x-bkpt-key=your-key
OTEL_SERVICE_NAME=quill
```

The `.env` file is loaded automatically at startup and is excluded from version control.

## Usage

```bash
quill analyze path/to/document.txt --project "Acme-Acquisition" --department "Finance"
```

`--project` and `--department` are required. They set the cost attribution tags that Beakpoint uses to slice spend by project and team.

Supported file formats: plain text, Markdown, PDF.

### Options

```
quill --help                  Show usage
quill --version               Show version
quill -v analyze ...          Enable debug logging (shows OTel export activity)
quill analyze ... --no-cache  Bypass the local response cache
quill analyze ... --single-role  Run only the Senior Partner role
quill analyze ... --doc-type nda  Use specialised prompts (nda, msa, employment)
```

### Response Cache

Quill caches raw API responses in `~/.cache/quill/responses/` to avoid redundant API calls during development. The cache key is a hash of the model, system prompt, and document text. Delete a cached JSON file to force a fresh API call, or pass `--no-cache` to bypass the cache entirely.

## Environment Variables

| Variable                      | Description                                | Required |
|-------------------------------|--------------------------------------------|----------|
| `ANTHROPIC_API_KEY`           | Anthropic API key                          | Yes      |
| `OPENAI_API_KEY`              | OpenAI API key                             | Yes      |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Full OTLP traces endpoint URL              | No       |
| `OTEL_EXPORTER_OTLP_HEADERS`  | OTLP auth headers (e.g. `x-bkpt-key=...`)  | No       |
| `OTEL_SERVICE_NAME`           | Service name for traces (default: `quill`) | No       |

## OpenTelemetry & Beakpoint Integration

Quill instruments every LLM API call with [OpenTelemetry](https://opentelemetry.io/) and exports traces to [Beakpoint](https://beakpoint.io) for per-model, per-project cost attribution. This section explains how the pieces fit together so you can follow the pattern in your own application.

### How tracing is initialized

All OTel setup lives in [`src/quill/tracing.py`](src/quill/tracing.py). The `init_tracing()` function does four things:

1. **Creates a `Resource`** — a bundle of key-value pairs that describe *this service* and are attached to every span it exports.
2. **Builds a `TracerProvider`** with an OTLP exporter - the provider is the SDK entry point; the exporter sends spans over HTTP to whatever endpoint you configure.
3. **Registers a `_GenAiSystemProcessor`** — a custom `SpanProcessor` that runs on every span start and enriches auto-instrumented LLM spans by copying `gen_ai.provider.name` to `gen_ai.system` and `cloud.provider` (Beakpoint requires `gen_ai.system` for pricing), and propagating `app.user.org.id` (department) so every child LLM span carries the attribution tag.
4. **Activates auto-instrumentation for both providers** - `AnthropicInstrumentor` and `OpenAIInstrumentor` monkey-patch their respective SDKs so every API call automatically produces a span with token counts, model name, and other `gen_ai.*` attributes.

```
init_tracing(project=..., department=...)
  │
  ├─ Resource (service.name, service.namespace, service.version)
  │
  ├─ TracerProvider
  │     ├─ _GenAiSystemProcessor  (copies gen_ai.provider.name → gen_ai.system,
  │     │                          sets cloud.provider, propagates app.user.org.id)
  │     └─ BatchSpanProcessor ──► OTLPSpanExporter
  │                                 (sends to OTEL_EXPORTER_OTLP_ENDPOINT)
  │
  ├─ AnthropicInstrumentor.instrument()
  │     (patches anthropic.Anthropic so every API call emits a span)
  │
  └─ OpenAIInstrumentor.instrument()
        (patches openai.OpenAI so every API call emits a span)
```

The CLI ([`src/quill/cli.py`](src/quill/cli.py)) calls `init_tracing()` at startup and registers `shutdown_tracing()` via `atexit` so pending spans are flushed on exit.

### What spans are emitted

Every `quill analyze` invocation produces a trace with three layers of spans:

```
quill.analyze_all
  ├── quill.analyze          (×N, one per role)
  │     └── anthropic.chat   (or openai.chat)
  ...
```

| Span                             | Created by                                                            | Purpose                                                                |
|----------------------------------|-----------------------------------------------------------------------|------------------------------------------------------------------------|
| `quill.analyze_all`              | Application code in [`analyzer.py`](src/quill/analyzer.py)            | Top-level orchestration span — wraps the full multi-role analysis run  |
| `quill.analyze`                  | Application code in [`analyzer.py`](src/quill/analyzer.py)            | Per-role span — wraps a single role's analysis including cache lookup  |
| `anthropic.chat` / `openai.chat` | Auto-instrumentation (`AnthropicInstrumentor` / `OpenAIInstrumentor`) | Child span for each LLM API call — carries token counts and model info |

When using `--single-role`, the trace has just `quill.analyze` → `anthropic.chat`/`openai.chat` (no `quill.analyze_all` wrapper).

The `anthropic.chat` and `openai.chat` spans are created automatically. You never write code for them — the instrumentors intercept every SDK call.

### Attributes that Beakpoint uses

Beakpoint reads specific OpenTelemetry attributes to calculate costs and let you slice spend by project, environment, and team. Here is every attribute Quill sets, where it is set, and why.

#### Resource attributes (set once at startup, attached to all spans)

These are configured in `init_tracing()` when building the `Resource`:

| Attribute           | Value in Quill                             | Beakpoint purpose                                        |
|---------------------|--------------------------------------------|----------------------------------------------------------|
| `service.name`      | `--project` flag (e.g. `Acme-Acquisition`) | **Cost attribution** — slice spend by project/matter     |
| `service.namespace` | `quill` (hardcoded)                        | **Cost attribution** — group related services            |
| `service.version`   | Package version (`0.1.0`)                  | **Cost attribution** — compare spend across releases     |

#### Span attributes on `quill.analyze_all`

Set in `analyze_document_all_roles()` in [`analyzer.py`](src/quill/analyzer.py):

| Attribute            | Value in Quill                              | Beakpoint purpose                                        |
|----------------------|---------------------------------------------|----------------------------------------------------------|
| `code.function.name` | `quill.analyzer.analyze_document_all_roles` | **Cost attribution** — see which code path incurred cost |
| `app.user.org.id`    | `--department` flag (e.g. `M&A`)            | **Cost attribution** — slice spend by department/team    |

#### Span attributes on `quill.analyze`

Set in `analyze_document()` in [`analyzer.py`](src/quill/analyzer.py):

| Attribute                    | Value in Quill                    | Beakpoint purpose                                        |
|------------------------------|-----------------------------------|----------------------------------------------------------|
| `code.function.name`         | `quill.analyzer.analyze_document` | **Cost attribution** — see which code path incurred cost |
| `app.user.org.id`            | `--department` flag (e.g. `M&A`)  | **Cost attribution** — slice spend by department/team    |
| `gen_ai.usage.input_tokens`  | Input tokens from child LLM call  | **Cost calculation** — propagated for parent-span rollup |
| `gen_ai.usage.output_tokens` | Output tokens from child LLM call | **Cost calculation** — propagated for parent-span rollup |

#### Span attributes on `anthropic.chat` / `openai.chat` (set automatically)

The auto-instrumentation libraries and the `_GenAiSystemProcessor` set these on every LLM span without any application code:

| Attribute                    | Example value          | Beakpoint purpose                                                     |
|------------------------------|------------------------|-----------------------------------------------------------------------|
| `gen_ai.system`              | `anthropic` / `openai` | **Cost calculation** — provider identification (pricing table)        |
| `cloud.provider`             | `anthropic` / `openai` | **Cost calculation** — provider identification                        |
| `gen_ai.provider.name`       | `anthropic` / `openai` | Source for `gen_ai.system` and `cloud.provider` (set by instrumentor) |
| `app.user.org.id`            | `M&A`                  | **Cost attribution** — propagated by `_GenAiSystemProcessor`          |
| `gen_ai.request.model`       | `claude-sonnet-4-6`    | **Cost calculation** — determines per-token price                     |
| `gen_ai.response.model`      | `claude-sonnet-4-6`    | **Cost calculation** — exact model version for pricing                |
| `gen_ai.response.id`         | (response ID string)   | Response tracking                                                     |
| `gen_ai.operation.name`      | `chat`                 | Operation type                                                        |
| `gen_ai.usage.input_tokens`  | `512`                  | **Cost calculation** — input token count                              |
| `gen_ai.usage.output_tokens` | `128`                  | **Cost calculation** — output token count                             |

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

> **📖 Full setup guide:** [Track LLM Costs with Beakpoint](https://docs.beakpoint.io/docs/tasks/getting-started/track-llm-costs)

### Summary: what you need to replicate this in your own app

1. **Install the OTel SDK and instrumentation libraries** for your LLM providers:
   ```
   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
   pip install opentelemetry-instrumentation-anthropic opentelemetry-instrumentation-openai-v2
   ```

2. **Call `.instrument()` on each instrumentor** — this gives you `gen_ai.usage.*` token counts, model names, and `gen_ai.provider.name` on every LLM call for free.

3. **Add a `SpanProcessor` to propagate `gen_ai.system`** — the auto-instrumentors set `gen_ai.provider.name` but Beakpoint requires `gen_ai.system` for pricing. A simple `on_start` processor can copy one to the other (see `_GenAiSystemProcessor` in `tracing.py` for the pattern). This is also a good place to propagate `app.user.org.id` and `cloud.provider` onto every LLM span.

4. **Set `service.name`** to whatever you want to group costs by (project, service, team).

5. **Point the exporter at Beakpoint** — set `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS`.

6. **Add span-level attribution attributes** where useful — `app.user.org.id` for department, `code.function.name` for function-level cost breakdown.

Use `quill -v analyze ...` to see export activity in the console.

## Limitations

Beakpoint does not yet support the following Anthropic pricing dimensions. These are all coming soon:

- Prompt cache write token pricing
- Batch API discount pricing
- Fast mode pricing
- Data residency pricing multiplier
- Web search per-request pricing
- Code execution runtime billing
- Managed Agents session runtime pricing
- Platform on AWS CCU billing conversion
- Platform on Microsoft Foundry CCU billing conversion

## License

See [LICENSE](LICENSE).
