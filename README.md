# note_taker

A Python project template using `uv`, `ruff`, `mypy`, and `pytest`.

## Setup

```bash
uv sync
```

## Usage

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check

# Format
uv run ruff format

# Type check
uv run mypy
```

## Project structure

```
├── src/
│   └── note_taker/      # package source
├── tests/              # pytest tests
├── pyproject.toml      # project config, tool config, dependencies
└── .github/workflows/  # CI
```

## Logging

Use `get_logger` from `note_taker.logger` instead of `print`. Direct `print` calls are not allowed.

```python
from note_taker.logger import get_logger

log = get_logger(__name__)
log.info("started")
```

Console output shows a level icon, a colour-coded logger name, and the message. All logs are also written in ISO 8601 format to `app.log`.

## Renaming the package

1. Rename `src/note_taker/` to `src/<yourpackage>/`
2. Update `name` and `packages` in `pyproject.toml`
3. Update imports in `tests/`
