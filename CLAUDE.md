# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                        # install all dependencies
uv run pytest                  # run all tests with coverage
uv run pytest tests/test_foo.py::test_bar  # run a single test
uv run ruff check              # lint
uv run ruff format             # format
uv run mypy                    # type check
python pack.py                 # regenerate new_python_project.py after changing template files
```

## Architecture

This is a `src/` layout package. Source lives under `src/note_taker/`; tests live under `tests/`. The package is installed in editable mode by `uv sync`, so imports resolve to the `src/` tree.

All tool configuration (pytest, ruff, mypy, coverage) is in `pyproject.toml`. Mypy runs in strict mode against `src/` only.

## Renaming the package

1. Rename `src/note_taker/` to `src/<newname>/`
2. Update `[project] name` and `[tool.hatch.build.targets.wheel] packages` in `pyproject.toml`
3. Update `--cov=note_taker` in `[tool.pytest.ini_options] addopts`
4. Update imports in `tests/`
