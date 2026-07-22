# Agent Guidelines for Python Code Quality

This document governs all code written in this repository. These rules MUST be
followed by all AI coding agents and contributors.

---

## Core Principles

All code you write MUST be fully optimized. "Fully optimized" means:

- Maximizing algorithmic efficiency (time and space complexity)
- Using parallelization and vectorization where appropriate
- Following language conventions and maximizing code reuse (DRY)
- No code beyond what is necessary to solve the problem (no technical debt)

If the code is not fully optimized before handoff, you will be fined $100. You
have permission to do a second pass if you are not confident the code meets this
bar.

---

## Project Structure

- **MUST** use `src/` layout — all package code lives under `src/<package_name>/`
- Tests live in `tests/` at the project root, mirroring the `src/` structure
- One `pyproject.toml` at the project root; no `setup.py`, no `requirements.txt`
- Structure example:

```
my_project/
├── src/
│   └── my_project/
│       ├── __init__.py
│       └── ...
├── tests/
│   └── test_*.py
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
└── .pre-commit-config.yaml
```

---

## pyproject.toml

Every project **MUST** have a well-structured `pyproject.toml`. Include all of
the following sections:

```toml
[project]
name = "my-project"
version = "0.1.0"
description = "..."
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "mypy", "ruff", "pre-commit"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = []

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## Tooling

- **Package management:** `uv` exclusively — never bare `pip`
  - Create `.venv` with `uv venv` if not present
  - Install deps with `uv pip install -e ".[dev]"`
- **Formatting and linting:** `ruff` (replaces Black, isort, flake8)
- **Type checking:** `mypy --strict`
- **Testing:** `pytest`
- **Pre-commit hooks:** configure `.pre-commit-config.yaml` to run Ruff and
  mypy automatically on every commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: []
```

- **JSON:** use `orjson` for all JSON serialization/deserialization
- **Error reporting:** use `logger.error(...)` — never `print()` for errors

---

## Logging

Every module that emits log output **MUST** use a module-level logger:

```python
import logging

logger = logging.getLogger(__name__)
```

Never configure logging globally inside library code. Only configure it in
entry points (e.g., `__main__.py` or CLI scripts).

---

## Public API and Module Exports

- **MUST** define `__all__` in every public module to explicitly declare its
  exported interface
- Use `__all__` to signal intentionality to readers and static analysis tools

```python
__all__ = ["MyClass", "my_function"]
```

---

## Code Style and Formatting

- **MUST** follow PEP 8 style guidelines
- **MUST** use 4 spaces for indentation (never tabs)
- **NEVER** use emoji or decorative unicode (e.g. ✓, ✗) except in tests
  targeting multibyte character behavior
- Use `snake_case` for functions/variables, `PascalCase` for classes,
  `UPPER_CASE` for constants
- Line length: 88 characters (Ruff default)
- Organize imports: standard library → third-party → local; use `ruff` to
  enforce automatically

---

## Type Hints

- **MUST** use type hints for all function signatures (parameters and return
  values)
- **NEVER** use `Any` unless unavoidable and explicitly justified in a comment
- Use `X | None` syntax (Python 3.10+) rather than `Optional[X]`
- **MUST** pass `mypy --strict` with zero errors before committing

---

## Documentation

- **MUST** include docstrings for all public functions, classes, and methods
- **MUST** document parameters, return values, and exceptions raised
- Use Google-style docstrings consistently

```python
def calculate_total(items: list[dict], tax_rate: float = 0.0) -> float:
    """Calculate the total cost of items including tax.

    Args:
        items: List of item dictionaries with 'price' keys.
        tax_rate: Tax rate as a decimal (e.g., 0.08 for 8%).

    Returns:
        Total cost including tax.

    Raises:
        ValueError: If items is empty or tax_rate is negative.

    Example:
        >>> calculate_total([{"price": 10.0}], tax_rate=0.1)
        11.0
    """
```

- Keep comments current with code changes; delete stale comments rather than
  updating them incorrectly
- **NEVER** commit commented-out code

---

## Error Handling

- **NEVER** silently swallow exceptions
- **NEVER** use bare `except:` clauses — always catch specific exception types
- **MUST** use context managers (`with`) for all resource cleanup
- Provide meaningful, actionable error messages

---

## Function Design

- Single responsibility per function
- **NEVER** use mutable objects (lists, dicts) as default argument values
- Prefer early returns to reduce nesting
- Limit parameters to 5 or fewer; use a dataclass for larger parameter sets

---

## Class Design

- Single responsibility per class
- Keep `__init__` simple — no complex logic
- Use `@dataclass` for plain data containers
- Prefer composition over inheritance
- Use `@property` for computed attributes
- Only create methods that are necessary; avoid padding classes with helpers
  that belong at module level

---

## Testing

- **MUST** write unit tests for all new public functions and classes
- **MUST** mock all external dependencies (APIs, databases, file I/O)
- Follow the Arrange-Act-Assert pattern
- **NEVER** run generated tests without first saving them as a discrete file
- **NEVER** delete test files after running them
- Add the test output folder to `.gitignore`
- Do not commit commented-out tests

---

## Security

- **NEVER** store secrets, API keys, or tokens in code — use `.env` only
- Ensure `.env` is in `.gitignore`
- **NEVER** log sensitive information (passwords, tokens, PII)
- **NEVER** print or log URLs that contain embedded API keys

---

## Repository Hygiene

- **MUST** include a `README.md` with: project description, installation
  instructions, usage examples, and license
- **MUST** include a `CONTRIBUTING.md` with: how to set up the dev environment,
  coding standards pointer (this file), and how to run tests and linting
- **NEVER** commit debug statements, breakpoints, or temporary scaffolding
- **NEVER** commit credentials or sensitive data
- Write clear, descriptive commit messages (imperative mood: "Add X", "Fix Y")

---

## Before Every Commit

- [ ] All tests pass (`pytest`)
- [ ] Type checking passes (`mypy --strict`)
- [ ] Linting and formatting pass (`ruff check` and `ruff format`)
- [ ] All public functions/classes have docstrings and type hints
- [ ] `__all__` is defined in all public modules
- [ ] No commented-out code, debug statements, or hardcoded credentials

---

**Remember:** Optimize for the reader. Code is read far more often than it is written.
