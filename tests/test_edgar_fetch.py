"""End-to-end tests for `fetch_candidates`, the orchestration behind
`cae fetch`, against a fake EDGAR built from real, saved responses.

Covers the acceptance criteria from docs/BUILD_SPEC.md Phase 1: filtering
excludes amendments/waivers/joinders (by title AND by content), reruns are
resumable, and every skip is logged with a reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from cae.edgar.client import EdgarClient
from cae.edgar.fetch import fetch_candidates
from cae.edgar.manifest import read_manifest
from cae.edgar.skiplog import SKIP_LOG_FIELDS

FIXTURES = Path(__file__).parent / "fixtures" / "edgar"

# CIKs (from docs/DECISIONS.md's Phase 1 findings) identifying two specific
# hits in the fixture that need distinct download bodies for this test.
CLEAN_CANDIDATE_CIK = "1747172"  # Kayne Anderson -- passes every filter
GENERIC_TITLE_AMENDMENT_CIK = "1756761"  # file_description "EX-10.1", but
# the document itself opens "SECOND AMENDMENT TO REVOLVING CREDIT..."

DEFAULT_DOC_BODY = "AMENDED AND RESTATED CREDIT AGREEMENT among the parties named herein..."

# fetch.py rejects anything under filters.MIN_CONTENT_BYTES before it even
# looks at content -- pad every fixture body used here past that floor so
# each test still exercises the check it's meant to, rather than being
# pre-empted by the size floor (see docs/DECISIONS.md, Phase 1, fourth
# wave, for why the floor exists).
_PAD = " filler text to clear the minimum document size" * 500


def _mixed_payload() -> dict[str, object]:
    return json.loads((FIXTURES / "search_response_mixed.json").read_text(encoding="utf-8"))


def _make_transport(calls: list[str]) -> httpx.MockTransport:
    clean_content = (FIXTURES / "content_clean_agreement.htm").read_text(encoding="utf-8") + _PAD
    amendment_content = (FIXTURES / "content_generic_title_is_amendment.htm").read_text(
        encoding="utf-8"
    ) + _PAD

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "efts.sec.gov" in url:
            return httpx.Response(200, json=_mixed_payload(), request=request)
        if f"/data/{CLEAN_CANDIDATE_CIK}/" in url:
            return httpx.Response(200, text=clean_content, request=request)
        if f"/data/{GENERIC_TITLE_AMENDMENT_CIK}/" in url:
            return httpx.Response(200, text=amendment_content, request=request)
        return httpx.Response(200, text=DEFAULT_DOC_BODY + _PAD, request=request)

    return httpx.MockTransport(handler)


def test_fetch_downloads_only_full_agreements(tmp_path: Path) -> None:
    calls: list[str] = []
    client = EdgarClient(user_agent="test test@example.com", transport=_make_transport(calls))
    raw_dir = tmp_path / "raw"
    manifest_path = raw_dir / "manifest.csv"
    skip_log_path = raw_dir / "skip_log.csv"

    summary = fetch_candidates(
        client=client,
        raw_dir=raw_dir,
        manifest_path=manifest_path,
        skip_log_path=skip_log_path,
        limit=300,
    )

    # 10 hits in the fixture: 2 genuinely downloadable (one plain
    # candidate, one "Amended and Restated" full document), 7 filtered
    # before download, 1 filtered after download by its content.
    assert summary.downloaded == 2
    assert summary.skipped == 8
    assert summary.failed == 0

    manifest_rows = read_manifest(manifest_path)
    assert len(manifest_rows) == 2
    doc_ids = {row.doc_id for row in manifest_rows}
    assert any(CLEAN_CANDIDATE_CIK in doc_id for doc_id in doc_ids)
    # The amendment-by-content document must not be in the manifest.
    assert not any(GENERIC_TITLE_AMENDMENT_CIK in doc_id for doc_id in doc_ids)

    for row in manifest_rows:
        assert (raw_dir / f"{row.doc_id}.htm").exists()


def test_fetch_logs_a_reason_for_every_skip(tmp_path: Path) -> None:
    calls: list[str] = []
    client = EdgarClient(user_agent="test test@example.com", transport=_make_transport(calls))
    raw_dir = tmp_path / "raw"
    manifest_path = raw_dir / "manifest.csv"
    skip_log_path = raw_dir / "skip_log.csv"

    fetch_candidates(
        client=client, raw_dir=raw_dir, manifest_path=manifest_path, skip_log_path=skip_log_path
    )

    lines = skip_log_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(SKIP_LOG_FIELDS)
    assert len(lines) == 1 + 8  # header + 8 skips
    for line in lines[1:]:
        doc_id, reason = line.split(",", 1)
        assert doc_id
        assert reason


def test_fetch_is_resumable(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    manifest_path = raw_dir / "manifest.csv"
    skip_log_path = raw_dir / "skip_log.csv"

    calls_first: list[str] = []
    client1 = EdgarClient(
        user_agent="test test@example.com", transport=_make_transport(calls_first)
    )
    first = fetch_candidates(
        client=client1, raw_dir=raw_dir, manifest_path=manifest_path, skip_log_path=skip_log_path
    )
    assert first.downloaded == 2
    download_calls_first = [c for c in calls_first if "efts.sec.gov" not in c]

    calls_second: list[str] = []
    client2 = EdgarClient(
        user_agent="test test@example.com", transport=_make_transport(calls_second)
    )
    second = fetch_candidates(
        client=client2, raw_dir=raw_dir, manifest_path=manifest_path, skip_log_path=skip_log_path
    )

    # Nothing new downloaded, and the document that's actually on disk from
    # the first run is not re-fetched. (A candidate that was rejected by
    # its *content* rather than saved -- e.g. the amendment-in-disguise --
    # has no record to resume from and is legitimately re-checked; that's
    # a separate, narrower guarantee than "don't redownload saved files".)
    assert second.downloaded == 0
    download_calls_first = [c for c in download_calls_first if CLEAN_CANDIDATE_CIK in c]
    download_calls_second = [c for c in calls_second if CLEAN_CANDIDATE_CIK in c]
    assert download_calls_first  # sanity: the first run did fetch it
    assert not download_calls_second  # the second run must not

    manifest_rows = read_manifest(manifest_path)
    assert len(manifest_rows) == 2  # no duplicate rows from the second run
