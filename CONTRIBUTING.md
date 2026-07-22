# Contributing to Quill

## Local Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Getting Started

```bash
git clone https://github.com/Beakpoint-Insights/Quill.git
cd Quill

uv venv
uv pip install -e ".[dev]"
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Copy the environment template and fill in your keys:

```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and Beakpoint credentials
```

Verify the install:

```bash
quill --version
```

### Project Structure

```
Quill/
├── pyproject.toml          # Package config and dependencies
├── src/quill/              # Source code
│   ├── __init__.py
│   ├── analyzer.py         # Claude API integration and analysis logic
│   ├── cache.py            # Local response cache
│   ├── cli.py              # Click CLI entry point
│   ├── output.py           # Rich terminal output
│   ├── reader.py           # File reader (txt, md, PDF)
│   └── tracing.py          # OpenTelemetry setup and Beakpoint export
├── tests/                  # Tests
│   ├── conftest.py         # Shared fixtures
│   ├── fixtures/           # 40 real legal documents for testing
│   ├── test_analyzer.py
│   ├── test_cli.py
│   ├── test_output.py
│   ├── test_reader.py
│   └── test_tracing.py
└── cache/responses/        # Cached API responses (committed)
```

### Running Tests

```bash
pytest
```

All tests use mocked API responses — no API key or network access needed.

### Adding Dependencies

Add new dependencies to the `[project.dependencies]` list in `pyproject.toml`, then re-install:

```bash
uv pip install -e ".[dev]"
```

### Code Style

- Format with [ruff](https://docs.astral.sh/ruff/)
- Type hints on all public function signatures
- Keep files under 500 lines
- See [CLAUDE.md](CLAUDE.md) for full coding standards

### Branch Naming

Branches follow the pattern `QUIL-<number>-<short-description>`, matching the Jira ticket.
