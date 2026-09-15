"""Phase 0 CLI contract: the subcommand surface is fixed and discoverable.

Downstream phases fill in command bodies; these tests pin the command
names and the fact that unimplemented commands fail loudly rather than
exiting 0.
"""

from __future__ import annotations

from typer.testing import CliRunner

from cae.cli import app

runner = CliRunner()

EXPECTED_COMMANDS = {"fetch", "process", "label", "extract", "evaluate", "report"}


def test_help_lists_all_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in EXPECTED_COMMANDS:
        assert command in result.stdout


def test_placeholder_commands_exit_nonzero() -> None:
    for command in ("fetch", "process", "label"):
        result = runner.invoke(app, [command])
        assert result.exit_code == 1
        assert "not implemented" in result.stdout.lower()


def test_extract_requires_model_option() -> None:
    result = runner.invoke(app, ["extract"])
    assert result.exit_code != 0
