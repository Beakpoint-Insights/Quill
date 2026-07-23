# Quill

[![Lint](https://github.com/Beakpoint-Insights/Quill/actions/workflows/lint.yml/badge.svg)](https://github.com/Beakpoint-Insights/Quill/actions/workflows/lint.yml)
[![Test](https://github.com/Beakpoint-Insights/Quill/actions/workflows/test.yml/badge.svg)](https://github.com/Beakpoint-Insights/Quill/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

![Winston, a colorful animated bird, is Beakpoint's mascot. Here, he's pretending to be a lawyer.](images/Winston%20the%20Lawyer.jpeg "Winston")

A sample app that shows how to add [Beakpoint](https://beakpoint.io) LLM cost tracking to a Python application using OpenTelemetry. Quill is a legal document analyzer that calls multiple LLM providers (Anthropic and OpenAI), making it a realistic example for multi-model cost attribution.

## What you'll be able to answer

Once your app sends traces to Beakpoint, you can answer questions like these:

| Which department spends the most?                                                                                                                          | Which LLM provider costs the most?                                                                                                          | Which project is driving spend?                                                                                                                   |
|------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| [![Cost Breakdown By Department.png](images/thumbnails/Cost%20Breakdown%20By%20Department.png)](images/screenshots/Cost%20Breakdown%20By%20Department.png) | [![Cost Breakdown by Model.png](images/thumbnails/Cost%20Breakdown%20by%20Model.png)](images/screenshots/Cost%20Breakdown%20by%20Model.png) | [![Cost Breakdown by Project.png](images/thumbnails/Cost%20Breakdown%20by%20Project.png)](images/screenshots/Cost%20Breakdown%20by%20Project.png) |
| See which teams to charge back for LLM usage.                                                                                                              | Compare spend across Anthropic, OpenAI, and others.                                                                                         | Find which projects are driving the most cost.                                                                                                    |

**Want to see this for your own LLM usage?** [Request a demo](https://beakpoint.io/demo)

> [!IMPORTANT]
> Quill is a demo, not a production legal tool. It exists to show how instrumentation works with Beakpoint.

## What it takes to integrate

Adding Beakpoint to your Python app takes about 100 lines of instrumentation code. Here's the short version:

1. **Install the OTel SDK and provider instrumentors:**
   ```
   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
   pip install opentelemetry-instrumentation-anthropic opentelemetry-instrumentation-openai-v2
   ```

2. **Call `.instrument()` on each instrumentor.** This gives you token counts, model names, and provider info on every LLM call automatically.

3. **Add a small `SpanProcessor` to set `gen_ai.system`.** The auto-instrumentors set `gen_ai.provider.name`, but Beakpoint needs `gen_ai.system` for pricing lookups. A few lines in an `on_start` hook copies one to the other. (See [`_GenAiSystemProcessor` in tracing.py](src/quill/tracing.py) for the exact pattern.)

4. **Set `service.name`** to whatever you want to group costs by: project name, service name, team, or matter.

5. **Point the exporter at Beakpoint:**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.beakpoint.io/api/traces
   OTEL_EXPORTER_OTLP_HEADERS=x-bkpt-key=bpk_your_key_here
   ```

6. **Add attribution attributes** where you want cost breakdowns: `app.user.org.id` for department, `code.function.name` for function-level cost slicing.

No Beakpoint-specific SDK. Standard OTLP/HTTP. If you already export traces somewhere, you can export to Beakpoint in parallel.

> **📖 Full setup guide:** [Track LLM Costs with Beakpoint](https://docs.beakpoint.io/docs/tasks/getting-started/track-llm-costs)

## Try it yourself

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Install

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

### Configure

Copy `.env.example` or create a `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.beakpoint.io/api/traces
OTEL_EXPORTER_OTLP_HEADERS=x-bkpt-key=your-key
OTEL_SERVICE_NAME=quill
```

### Run

```bash
quill analyze path/to/document.txt --project "Acme-Acquisition" --department "Finance"
```

`--project` and `--department` are required. They set the cost attribution tags that Beakpoint uses to slice spend by project and team. Supported file formats: plain text, Markdown, PDF.

Use `quill -v analyze ...` to see OTel export activity in the console.

## How the instrumentation works

All OTel setup lives in one file: [`src/quill/tracing.py`](src/quill/tracing.py). When Quill starts, it calls `init_tracing()`, which does four things:

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

Here's what each piece does in plain English:

- **Resource** is a set of key-value pairs describing your service. Beakpoint uses `service.name` for project-level cost grouping. You set it once at startup and it attaches to every span.
- **TracerProvider** is the OTel engine that creates and exports spans. You give it a resource and one or more processors.
- **`_GenAiSystemProcessor`** is a custom span processor (about 20 lines). It runs every time a span starts and copies `gen_ai.provider.name` to `gen_ai.system` (which Beakpoint needs for pricing). It also propagates the `app.user.org.id` department tag to child spans so every LLM call carries the attribution.
- **`BatchSpanProcessor` + `OTLPSpanExporter`** batches spans and sends them over HTTP. If no endpoint is configured, no exporter is added, and spans are silently dropped. Your app works fine without Beakpoint; it just doesn't export.
- **`AnthropicInstrumentor` and `OpenAIInstrumentor`** monkey-patch their respective SDKs. After calling `.instrument()`, every API call automatically produces a span with token counts, model name, and provider info. You don't write any code for these spans.

### What spans are emitted

Every `quill analyze` run produces a trace like this:

```
quill.analyze_all
  ├── quill.analyze          (×N, one per role)
  │     └── anthropic.chat   (or openai.chat)
  ...
```

| Span                             | Created by                                            | What it captures                                                       |
|----------------------------------|-------------------------------------------------------|------------------------------------------------------------------------|
| `quill.analyze_all`              | Application code in [`analyzer.py`](src/quill/analyzer.py) | Top-level orchestration: wraps the full multi-role analysis run        |
| `quill.analyze`                  | Application code in [`analyzer.py`](src/quill/analyzer.py) | Per-role span: wraps a single role's analysis including cache lookup   |
| `anthropic.chat` / `openai.chat` | Auto-instrumentors (no application code needed)       | Each LLM API call with token counts and model info                     |

The `anthropic.chat` and `openai.chat` spans are created automatically. You never write code for them.

## Reference

### Attributes that Beakpoint uses

Beakpoint reads these OpenTelemetry attributes to calculate costs and slice spend by project, team, and environment.

#### Resource attributes (set once at startup, attached to all spans)

| Attribute           | Value in Quill                             | Beakpoint uses it for                                    |
|---------------------|--------------------------------------------|----------------------------------------------------------|
| `service.name`      | `--project` flag (e.g. `Acme-Acquisition`) | **Cost attribution**: slice spend by project/matter      |
| `service.namespace` | `quill` (hardcoded)                        | **Cost attribution**: group related services             |
| `service.version`   | Package version (`0.1.0`)                  | **Cost attribution**: compare spend across releases      |

#### Span attributes on application spans

Set in [`analyzer.py`](src/quill/analyzer.py) on `quill.analyze_all` and `quill.analyze`:

| Attribute                    | Value in Quill                              | Beakpoint uses it for                                    |
|------------------------------|---------------------------------------------|----------------------------------------------------------|
| `code.function.name`         | `quill.analyzer.analyze_document_all_roles` | **Cost attribution**: see which code path incurred cost  |
| `app.user.org.id`            | `--department` flag (e.g. `M&A`)            | **Cost attribution**: slice spend by department/team     |
| `gen_ai.usage.input_tokens`  | Input tokens from child LLM call            | **Cost calculation**: propagated for parent-span rollup  |
| `gen_ai.usage.output_tokens` | Output tokens from child LLM call           | **Cost calculation**: propagated for parent-span rollup  |

#### Span attributes on LLM spans (set automatically)

The auto-instrumentors and `_GenAiSystemProcessor` set these on every LLM span:

| Attribute                    | Example value          | Beakpoint uses it for                                                 |
|------------------------------|------------------------|-----------------------------------------------------------------------|
| `gen_ai.system`              | `anthropic` / `openai` | **Cost calculation**: provider identification for pricing table       |
| `cloud.provider`             | `anthropic` / `openai` | **Cost calculation**: provider identification                         |
| `gen_ai.request.model`       | `claude-sonnet-4-6`    | **Cost calculation**: determines per-token price                      |
| `gen_ai.response.model`      | `claude-sonnet-4-6`    | **Cost calculation**: exact model version for pricing                 |
| `gen_ai.usage.input_tokens`  | `512`                  | **Cost calculation**: input token count                               |
| `gen_ai.usage.output_tokens` | `128`                  | **Cost calculation**: output token count                              |
| `app.user.org.id`            | `M&A`                  | **Cost attribution**: propagated by `_GenAiSystemProcessor`           |
| `gen_ai.operation.name`      | `chat`                 | Operation type                                                        |
| `gen_ai.response.id`         | (response ID string)   | Response tracking                                                     |

### Environment variables

| Variable                      | Description                                | Required |
|-------------------------------|--------------------------------------------|----------|
| `ANTHROPIC_API_KEY`           | Anthropic API key                          | Yes      |
| `OPENAI_API_KEY`              | OpenAI API key                             | Yes      |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Full OTLP traces endpoint URL              | No       |
| `OTEL_EXPORTER_OTLP_HEADERS`  | OTLP auth headers (e.g. `x-bkpt-key=...`) | No       |
| `OTEL_SERVICE_NAME`           | Service name for traces (default: `quill`) | No       |

## Developing Quill

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development setup, project structure, and coding standards.

### CLI options

```
quill --help                  Show usage
quill --version               Show version
quill -v analyze ...          Enable debug logging (shows OTel export activity)
quill analyze ... --no-cache  Bypass the local response cache
quill analyze ... --single-role  Run only the Senior Partner role
quill analyze ... --doc-type nda  Use specialised prompts (nda, msa, employment)
```

### Response cache

Quill caches raw API responses in `~/.cache/quill/responses/` to avoid redundant API calls during development. The cache key is a hash of the model, system prompt, and document text. Delete a cached JSON file to force a fresh API call, or pass `--no-cache` to bypass the cache entirely.

## Get started with Beakpoint

Ready to track LLM costs across your own tools? [Request a demo](https://beakpoint.io/demo) and we'll help you get set up.

## License

See [LICENSE](LICENSE).
