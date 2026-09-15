# Design decisions

Running log of design choices worth being able to explain. One entry per
decision: what was decided, and why.

## Phase 0 — repository setup

### Python floor pinned at 3.12, not 3.11
The project targets "Python 3.11+". The build machine runs 3.12.4, and that is
the only interpreter the scaffold has been exercised against, so
`requires-python` is `>=3.12`. Claiming 3.11 support without testing it
would be unfounded. Easy to lower later once 3.11 is in CI.

### `uv` installed via `pip install uv`
`uv` was not present on the machine. Installed it as a normal wheel rather
than piping the vendor install script to a shell. `uv` then manages its
own virtual environment (`.venv/`) and the lockfile.

### CLI entry point is `cae.cli:main`, not the Typer app object
`[project.scripts]` needs a plain callable. `main()` in `cli.py` wraps
`app()`. Keeps the console-script contract independent of Typer internals.

### All six subcommands are placeholders that exit non-zero
`fetch`, `process`, `label`, `extract`, `evaluate`, `report` exist from day
one so the `--help` surface and the test contract are stable across
phases. Unimplemented commands print a notice and exit 1 rather than
exiting 0, so a half-built pipeline cannot look like a successful run in a
script.

### `config/models.yaml` ships with `null` prices
Prices are left unset with `TODO(Phase 5)` markers. The Phase 5 cost guard
is expected to refuse to run on a missing price rather than assume one, so
`null` is the correct starting state, not a placeholder number.

### `data/processed/` and `data/gold/` are tracked; `data/raw/` and `data/runs/` are not
Raw filings and run artefacts are large and reproducible. The gold set and
its split assignment are project evidence and must be reviewable in git.
`.gitkeep` files preserve the ignored directories.

### ruff configured to leave Typer defaults and `docs/` alone
`flake8-bugbear` B008 flags call-valued argument defaults; Typer requires
them, so `typer.Option`/`typer.Argument` are marked immutable. `docs/` is
excluded from ruff entirely because the build spec under `docs/` contains
illustrative, non-runnable code snippets the formatter should not touch.

### mypy `--strict` on `src/` only
Set via `[tool.mypy]` in `pyproject.toml` (so bare `uv run mypy src`
works). A few untyped third-party packages (`duckdb`, `rapidfuzz`, `bs4`,
`streamlit`) have `ignore_missing_imports` overrides; everything first-party
is strictly typed.
