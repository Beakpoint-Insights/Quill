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

## OpenTelemetry

Quill instruments every API call with OpenTelemetry and exports spans to Beakpoint for cost attribution. Two types of spans are emitted:

- **`quill.analyze`** — orchestration span covering the full analysis, including cache hit/miss
- **`anthropic.chat`** — auto-instrumented span (child of `quill.analyze`) with `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens`

Use `quill -v analyze ...` to see export activity in the console.

## License

See [LICENSE](LICENSE).
