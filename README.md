# credit-agreement-extractor

Extract structured terms from US syndicated credit agreements filed on SEC
EDGAR into a validated schema, check every extracted value against a
verbatim evidence quote, and measure accuracy field by field against a
hand-labelled gold set — comparing a frontier API model with a small local
open model on accuracy, grounding, cost and latency.

The emphasis is the system around the model: acquisition, document
processing, schema validation, grounding checks, a review queue instead of
silent failure, and an evaluation harness with confidence intervals.

> **Status: Phase 0 (scaffold).** Project structure, tooling and a
> placeholder CLI are in place. The pipeline is not implemented yet.

## Quick start

```bash
uv sync
uv run cae --help
```

Copy `.env.example` to `.env` and fill in the values as each phase needs
them (`SEC_USER_AGENT` for Phase 1, `ANTHROPIC_API_KEY` for Phase 5).

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Design decisions are recorded in
`docs/DECISIONS.md`.

## Known limitations (planned v1)

- Only the initial financial-covenant threshold is captured; step-downs are ignored.
- Per-facility pricing margins are collapsed into a single min/max range.
- Multi-borrower structures record the lead borrower only.
- Amendments, waivers and joinders are deliberately excluded from
  acquisition (`cae fetch`) and not linked back to their base agreement.
  Only the base credit agreement's own terms are captured, as filed --
  not how those terms changed afterward. Tracking amendment history
  properly (linking amendments to a base agreement and applying changes
  chronologically) is a materially different feature, not a tweak to the
  current single-document schema, and is a candidate for future work.

This is a portfolio and research project, not production software. The
README describes the controls the pipeline has and the ones it lacks.
