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

### `SEC_USER_AGENT` uses a project name and an email alias, not a personal name
EDGAR's fair-access policy only requires a descriptive, non-generic
identifier plus a reachable contact (their own example is
`"Sample Company Name AdminContact@sample.com"`, an organisation, not a
person). Used `"credit-agreement-extractor <alias>@mozmail.com"` — a
Firefox Relay alias that forwards to a real inbox without exposing it in
request headers SEC logs on its servers. Satisfies the requirement without
putting a personal name/address in a header sent thousands of times.

## Phase 1 — EDGAR acquisition

### Full-text search response shape (verified against the live API, 2026-09-22)
Made real requests to `https://efts.sec.gov/LATEST/search-index` before
writing any parser, per the spec. Findings that shaped the implementation:

- **Endpoint and query params**: `q` (quoted phrases work, e.g.
  `"credit agreement" "administrative agent"` — space-joined phrases are
  ANDed), `forms` (comma-separated, e.g. `8-K,10-Q,10-K`), `dateRange=custom`
  with `startdt`/`enddt` (`YYYY-MM-DD`), `from` for pagination (offset-based).
- **Page size defaults to 100** results per request, not 10 as some
  third-party write-ups claim. Confirmed by requesting the same query with
  no `size` param and counting `len(hits.hits)`.
- **Response shape**:
  `{"hits": {"total": {"value": int, "relation": "eq"|"gte"}, "hits": [...]}}`.
  Each hit's `_id` is `"{accession-no-with-dashes}:{filename}"`. The fields
  actually used: `_source.ciks` (list), `_source.display_names` (list,
  `"Company Name  (TICKER)  (CIK 0001234567)"`), `_source.form`,
  `_source.file_date`, `_source.file_type` (e.g. `"EX-10.1"`, or `"8-K"` for
  the filing's own cover document), `_source.file_description` (often just
  repeats `file_type`, sometimes the real document title).
- **The primary 8-K/10-Q/10-K document itself is returned alongside its
  exhibits** in search hits (`file_type == form`, e.g. `"8-K"`). Filtering to
  `file_type` starting with `EX-10` excludes the cover filing and unrelated
  exhibit types (`EX-99`, `EX-4`, guaranty agreements, etc.) that also
  happened to contain both search phrases.
- **Critical, non-obvious finding: the CIK in the download URL must come
  from `_source.ciks[0]`, not from the accession-number prefix.** The
  accession number `0001213900-22-009497` has `0001213900` as its leading
  segment, but that is the filing agent's CIK, not the filer's — using it in
  `https://www.sec.gov/Archives/edgar/data/{cik}/...` 404s. Verified by
  constructing the URL both ways against a live document; only
  `_source.ciks[0]` (here `1747172`) resolves. Download URL pattern:
  `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_no_dashes}/{filename}`.
- **`file_description` is not reliable for amendment detection.** A hit with
  `file_description: "EX-10.1"` (i.e. no descriptive title at all) turned
  out, on download, to open with "SECOND AMENDMENT TO REVOLVING CREDIT...".
  Confirms the build spec's own hint ("titles **or first pages**") —
  amendment/waiver/joinder filtering has to check the document's own first
  ~3,000 characters after download, not just the search-index metadata.
  `file_description` is still checked first as a cheap pre-filter (skips
  the download entirely when the title is already unambiguous, e.g.
  `"AMENDMENT NO. 9"`), but it cannot be the only check.
- One nuance for that filter: **"Amended and Restated Credit Agreement" is
  not an amendment** for this project's purposes — it is a full replacement
  document (a complete, re-executed agreement), unlike a bare "Amendment"
  or "Waiver" or "Joinder" document, which only contains the delta and
  lacks most of the fields the schema needs. The exclusion check matches
  the bare word **"amendment"** (case-insensitive, word-boundary), which
  is deliberately distinct from **"amended"** — different word, no
  substring overlap — so `"Amended and Restated Credit Agreement"` is
  never excluded while `"SECOND AMENDMENT TO REVOLVING CREDIT AGREEMENT"`
  and `"AMENDMENT NO. 9"` both are.

### Rate limiting implemented client-side regardless of observed behaviour
A handful of rapid manual test requests during API exploration didn't get
throttled, but that's not evidence the limit doesn't apply at `cae fetch`'s
real volume (up to 300 documents). Implemented an 8 req/s cap (below SEC's
documented 10 req/s ceiling) as a fixed minimum-interval sleep in the HTTP
client, applied to every request regardless of endpoint.

### Two bugs the test suite caught before any real run
Writing the tests against real fixture data (rather than hand-typed happy
paths) surfaced two mistakes in the first implementation, both fixed
before `cae fetch` was ever run for real:

1. **CIK not un-padded.** `_source.ciks` gives a zero-padded CIK (e.g.
   `"0001747172"`); the Archives download URL needs the unpadded form
   (`1747172`). `parse_hit` now does `str(int(ciks[0]))`.
2. **Amendment regex too narrow.** The first pattern only matched
   `"Amendment No. N"`. A real downloaded document opened with "SECOND
   AMENDMENT TO REVOLVING CREDIT AGREEMENT" — no "No." at all — and
   slipped through as a false negative, which a dedicated test
   (`test_looks_like_amendment_checks_document_content`) caught. Fixed by
   broadening to the bare word "amendment" (see above).

### Skip log does not re-record "already downloaded" on a resumed run
`fetch_candidates` treats "already in the manifest / already on disk" as a
silent `continue`, not a skip-log entry. Every *other* skip reason (wrong
form, before cutoff, not Exhibit 10.x, amendment/waiver/joinder, download
failure) is logged. Rationale: the skip log is meant to explain why a
*candidate* was rejected; re-explaining "already downloaded" on every
resumed run would dominate the log with noise rather than useful signal.
A trade-off worth naming: content-rejected candidates (the amendment
found only by downloading and reading it) have no record either, so a
resumed run legitimately re-downloads and re-checks them — only
successfully saved documents are skipped on resume.

### The query also surfaces ancillary documents, not just amendments -- and this filter is a heuristic, not a guarantee
`"credit agreement" "administrative agent"` matches any Exhibit 10.x
document that *references* a credit agreement, not only the agreement
itself. A live `cae fetch --limit 15` run (before this filter existed)
downloaded a **Guaranty**, a **Limited Guarantee**, a **Security
Agreement**, a **Lender Confirmation**, a **Limited Consent**, and (on a
second round, after the first fix) a **Successor Agency Agreement** —
none of them a credit agreement, all mentioning one. `flags.py`'s
`is_excluded_document_type` now excludes documents whose own declared
type (checked in a short "title area" -- the first ~500 visible
characters, chosen because every real title, good or bad, appeared within
~110 characters in the documents checked) names one of: amendment,
waiver, joinder, guaranty/guarantee, security agreement, pledge
agreement, confirmation, consent, subordination agreement, intercreditor
agreement, notice of default, agency agreement, assignment and
assumption, resignation, fee letter.

**This list is not, and cannot be, exhaustive.** It was built by finding
real false positives in actual runs and adding a pattern for each, not by
enumerating every ancillary document type syndicated loan agreements
produce. A second round confirmed this: a 20-document random spot check
against a real 40-document run (the spec's own acceptance-criteria check)
found 3 more false positives from a different family -- documents that
add or modify a *lender* on an existing facility rather than being the
base agreement: an **Incremental Commitment and Assumption Agreement**, a
**First Incremental Assumption Agreement**, and a **New Lender
Agreement**. Added `incremental commitment`, `assumption agreement` and
`new lender agreement` to the exclusion list in response (`filters.py`).

A third round confirmed it again: a fresh 20-document spot check on a
real 50-document run found 2 *more* false positives from yet another
family -- a plain, informal **letter agreement** with no capitalised
title at all (just "September 12, 2023 ... Re: Credit Agreement..."),
and a **"REFINANCING FACILITY AGREEMENT NO. 2"** that never uses the word
"amendment" but explicitly modifies an earlier, separately-dated credit
agreement ("...the Credit Agreement as amended hereby..."). The second
one was caught on *substance* (`as amended hereby`/`as amended thereby`)
rather than a document-type label, since enumerating every possible label
for "this modifies an existing facility" is a losing game. (An earlier
version of this entry claimed the second-round spot check "came back
clean" -- it hadn't been re-run yet when that was written; corrected
here rather than left standing.)

Decided against trying to make this airtight in Phase 1: the honest
position is that title/content keyword filtering is a heuristic that
narrows the candidate pool, not a guarantee of 100% precision --
documented here as a known, permanent limitation, to be caught downstream
by (a) human review during Phase 4 gold-set labelling, and (b) Phase 5's
evidence-grounding check, which will naturally return null/ungrounded
fields for a document that isn't actually a credit agreement rather than
hallucinate values. Kept as a design decision explicitly stated rather
than silently assumed, per this project's own stated purpose (validation
layers over the AI/scraping, not just plumbing).

**Update -- a fourth round, on the real 300-document run, changed the
calculus above.** A 20-document random spot check on the actual
`cae fetch --limit 300` output (not another disposable test batch) came
back **6/20 (30%) false positive** -- a materially worse rate than the
earlier rounds, and on the real deliverable this time, not a validation
run. That justified going further rather than accepting a documented
27%+ error rate in what becomes Phase 4's sampling pool. The family this
time: documents that increase, extend, or partially modify an *existing*
facility -- "Commitment Increase Agreement/Supplement/Request",
"Accordion Increase", "Augmenting/Additional Lender Supplement",
"Reaffirmation Agreement", "Suspension of Rights Agreement", "[N]th
Modification Agreement", "Incremental Term Loan/Tranche [B] Agreement",
"Extension Request/No. N", "Board Observer Agreement" -- plus a real
regex bug: **"AMENDING AGREEMENT"** (the gerund) had never matched the
original `\bamendments?\b` pattern, only the noun form.

This round was found differently on purpose: instead of trusting another
random 20-document sample, the title area of **all 300** downloaded
documents was grepped for suspicious keywords and reviewed by hand, since
a full-corpus review is strictly more thorough than a lucky/unlucky
sample once the documents are already on disk (no extra network cost).
That review also tested a **file-size heuristic**: every confirmed false
positive across all four rounds was under ~181KB, while every confirmed
genuine credit agreement was over ~190KB -- but that ~10KB margin came
from one sample and was judged too thin to trust as the *primary* filter
(a smaller company's genuinely short bilateral facility could plausibly
land in that gap). Used it only as a conservative low floor instead
(`MIN_CONTENT_BYTES = 20_000`, `filters.is_large_enough`) -- comfortably
below every genuine document seen, so it only catches a stray one-page
letter that dodges every keyword, without risking a real agreement.

**Validating the fix without another live fetch:** since all 300 real
documents were already on disk, the updated filter functions were re-run
directly against the saved files (`is_excluded_document_type`,
`looks_like_credit_agreement`, `is_large_enough` on the saved content and
file size) rather than re-running `cae fetch` against EDGAR again. 262 of
300 survived (well above the 200 floor); the 38 rejected were removed
from `manifest.csv`/`data/raw/` and logged to `skip_log.csv` with a
reason, exactly as a live run would have done.

**Why exactly 300 -> 262 (the 38 broken down):**
- **33 rejected as an excluded document type** -- caught by
  `is_excluded_document_type` against the downloaded content: the fourth
  wave of ancillary/amendment-family documents described above
  (Commitment Increase Agreements, Accordion Increases, Modification
  Agreements, "Amending Agreement", etc.), all documents that were
  downloaded under the *older* filter rules (rounds 1-3, already applied
  during the live run) but only caught once the fourth wave's patterns
  existed.
- **5 rejected as too small** -- under the new `MIN_CONTENT_BYTES =
  20,000` floor; short letters/requests that happened not to match any
  keyword pattern but were obviously not full agreements by size alone.
- 33 + 5 = 38 rejected, 300 - 38 = 262 kept. (This is a different number
  from the earlier `skipped=3247` reported by the live `cae fetch --limit
  300` run itself -- that count is candidates rejected *before* or
  *during* download, under the filter rules active *at the time of the
  run*; these 38 are a *second*, retroactive pass over the 300 documents
  that had already been downloaded and kept, re-checked against the
  *fourth-wave* rules added afterward.)

Two independent 20-document random spot checks against the surviving 262
(different random seeds) both came back **0/20 false positives**.
Considered this enough evidence to stop iterating -- not because the
heuristic is provably perfect (it isn't, and can't be, per the limitation
above), but because the two checks that mattered (thorough full-corpus
review, then two clean random samples afterward) both passed.

**Final Phase 1 acceptance-criteria state:** manifest contains 262
documents (>= 200), a 20-document spot check found no amendments (twice,
with different random samples), `cae fetch` is resumable (unit tested),
and every skip is logged with a reason (unit tested, and true of the
retroactive cleanup too).

### Scope confirmed: amendments stay excluded, not a future "amendment history" feature
Raised directly and considered on its merits: amendments to a credit
agreement carry real information (a loosened covenant, an upsized
facility), so "why throw them away" is a fair question, not just an
implementation detail. Decided to keep the original spec's scope
(base agreements only) rather than expand it, because capturing amendment
history properly is a materially different, larger feature -- linking
each amendment back to its base agreement and applying changes
chronologically -- not a tweak to this pipeline's single-document
snapshot schema. Feeding an amendment through the current schema would
mostly return nulls (an amendment typically restates only the one clause
being changed, cross-referencing everything else back to the base
document), which would look like a bad extraction in Phase 6's evaluation
rather than the wrong document type being asked the wrong question.
Recorded here as a deliberate scope decision, not an oversight -- worth
naming as a real "what I'd do next" item in the README's known
limitations (per BUILD_SPEC Phase 3's own instruction to document v1
limitations honestly) rather than leaving it invisible in a filter file.
