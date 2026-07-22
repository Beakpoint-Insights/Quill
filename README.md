# Quill

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

## Usage

```bash
quill analyze path/to/document.txt
```

Supported file formats: plain text, Markdown, PDF.

### Options

```
quill --help       Show usage
quill --version    Show version
```

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key | Yes |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | No |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP auth headers (e.g. `x-bkpt-key=...`) | No |
| `OTEL_SERVICE_NAME` | Service name for traces (default: `quill`) | No |

## License

See [LICENSE](LICENSE).
