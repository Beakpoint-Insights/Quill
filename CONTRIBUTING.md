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
uv pip install -e .
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Verify the install:

```bash
quill --version
```

### Project Structure

```
Quill/
├── pyproject.toml        # Package config and dependencies
├── src/quill/            # Source code
│   ├── __init__.py
│   └── cli.py            # CLI entry point
└── tests/                # Tests
```

### Running Tests

```bash
pytest
```

### Adding Dependencies

Add new dependencies to the `[project.dependencies]` list in `pyproject.toml`, then re-install:

```bash
uv pip install -e .
```

### Code Style

- Format with [ruff](https://docs.astral.sh/ruff/)
- Type hints on all public function signatures
- Keep files under 500 lines

### Branch Naming

Branches follow the pattern `QUIL-<number>-<short-description>`, matching the Jira ticket.
