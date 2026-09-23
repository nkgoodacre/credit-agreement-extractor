"""CLI contract tests.

`fetch` is implemented (Phase 1) and is tested here only for its argument
handling and env-var guard -- with `cae.edgar.fetch.fetch_candidates`
monkeypatched out, so no test in this file ever touches the network.
`process` and `label` are still Phase 0 placeholders.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import cae.cli as cli_module
from cae.cli import app
from cae.edgar.fetch import FetchSummary

runner = CliRunner()

EXPECTED_COMMANDS = {"fetch", "process", "label", "extract", "evaluate", "report"}


def test_help_lists_all_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in EXPECTED_COMMANDS:
        assert command in result.stdout


def test_placeholder_commands_exit_nonzero() -> None:
    for command in ("process", "label"):
        result = runner.invoke(app, [command])
        assert result.exit_code == 1
        assert "not implemented" in result.stdout.lower()


def test_extract_requires_model_option() -> None:
    result = runner.invoke(app, ["extract"])
    assert result.exit_code != 0


def test_fetch_fails_clearly_without_sec_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(cli_module, "load_dotenv", lambda: None)

    result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 1
    assert "SEC_USER_AGENT" in result.stdout


def test_fetch_rejects_the_placeholder_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_USER_AGENT", "Your Name your@email.com")
    monkeypatch.setattr(cli_module, "load_dotenv", lambda: None)

    result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 1
    assert "SEC_USER_AGENT" in result.stdout


def test_fetch_reports_the_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_USER_AGENT", "credit-agreement-extractor test@example.com")
    monkeypatch.setattr(cli_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        cli_module,
        "fetch_candidates",
        lambda **kwargs: FetchSummary(downloaded=5, skipped=2, failed=0),
    )

    result = runner.invoke(app, ["fetch", "--limit", "5"])

    assert result.exit_code == 0
    assert "Downloaded 5" in result.stdout
    assert "skipped 2" in result.stdout
