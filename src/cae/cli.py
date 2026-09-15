"""Command-line entry point for ``cae``.

Every subcommand here is a Phase 0 placeholder: it parses arguments and
reports that the underlying phase is not yet implemented. Real behaviour is
added phase by phase (see ``docs/BUILD_SPEC.md``). Keeping the CLI surface
fixed from the start means downstream phases only fill in bodies, and the
``--help`` contract stays stable for tests and documentation.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Extract and validate structured terms from US syndicated credit agreements.",
)

_NOT_IMPLEMENTED = "This command is a Phase 0 placeholder and is not implemented yet."


@app.command()
def fetch(
    limit: int = typer.Option(300, help="Maximum number of candidate documents to download."),
) -> None:
    """Acquire candidate credit agreements from SEC EDGAR (Phase 1)."""
    typer.echo(_NOT_IMPLEMENTED)
    raise typer.Exit(code=1)


@app.command()
def process() -> None:
    """Convert raw filings to clean text and split them into sections (Phase 2)."""
    typer.echo(_NOT_IMPLEMENTED)
    raise typer.Exit(code=1)


@app.command()
def label() -> None:
    """Launch the Streamlit gold-set labelling tool (Phase 4)."""
    typer.echo(_NOT_IMPLEMENTED)
    raise typer.Exit(code=1)


@app.command()
def extract(
    model: str = typer.Option(..., help="Model key from config/models.yaml."),
    strategy: str = typer.Option("targeted", help="Context strategy: 'full' or 'targeted'."),
    split: str = typer.Option("dev", help="Gold split to run against: 'dev' or 'test'."),
) -> None:
    """Run the LLM extraction pipeline over a document set (Phase 5)."""
    typer.echo(_NOT_IMPLEMENTED)
    raise typer.Exit(code=1)


@app.command()
def evaluate(
    run_id: str = typer.Option(..., help="Run identifier produced by 'cae extract'."),
) -> None:
    """Score a run against the gold labels for its split (Phase 6)."""
    typer.echo(_NOT_IMPLEMENTED)
    raise typer.Exit(code=1)


@app.command()
def report(
    run_ids: list[str] = typer.Option(..., help="Run identifiers to compare."),
) -> None:
    """Produce a comparison report across one or more runs (Phase 7)."""
    typer.echo(_NOT_IMPLEMENTED)
    raise typer.Exit(code=1)


def main() -> None:
    """Console-script hook referenced by ``[project.scripts]`` in pyproject.toml."""
    app()


if __name__ == "__main__":
    main()
