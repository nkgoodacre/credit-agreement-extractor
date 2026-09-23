"""Orchestrates `cae fetch`: search, filter, download, and record.

This is the only module that ties search + filters + manifest + skip-log
together, so the acceptance-criteria behaviour (resumable, no amendments
in the manifest, every skip logged with a reason) lives in one place and
is testable end to end against a fake client instead of the network.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cae.edgar.client import EdgarClient
from cae.edgar.filters import (
    is_after_cutoff,
    is_downloadable_type,
    is_excluded_document_type,
    is_exhibit_10,
    is_large_enough,
    is_target_form,
    looks_like_credit_agreement,
)
from cae.edgar.manifest import ManifestRow, append_rows, read_existing_doc_ids
from cae.edgar.search import SearchHit, search
from cae.edgar.skiplog import SkipRecord, append_skips

DEFAULT_QUERY = '"credit agreement" "administrative agent"'
DEFAULT_FORMS = ("8-K", "10-Q", "10-K")
DEFAULT_START_DATE = date(2022, 1, 1)

# Characters of the downloaded document inspected for amendment/waiver/
# joinder titles that the search index's file_description didn't reveal
# (see docs/DECISIONS.md, Phase 1).
CONTENT_PREVIEW_CHARS = 3000

ALREADY_DOWNLOADED = "already downloaded"


@dataclass(frozen=True)
class FetchSummary:
    downloaded: int
    skipped: int
    failed: int


def _pre_download_skip_reason(hit: SearchHit, existing: set[str], raw_dir: Path) -> str | None:
    """Cheap checks against search-index metadata alone, before spending a
    download on a candidate that a title or filter would rule out anyway."""
    if hit.doc_id in existing or (raw_dir / f"{hit.doc_id}.htm").exists():
        return ALREADY_DOWNLOADED
    if not is_target_form(hit.form):
        return f"form {hit.form} not in target forms"
    if not is_after_cutoff(hit.file_date):
        return "filed before cutoff date"
    if not is_exhibit_10(hit.file_type):
        return f"file_type {hit.file_type!r} is not an Exhibit 10.x"
    if not is_downloadable_type(hit.filename):
        return "not HTML/plain-text (likely a PDF)"
    if is_excluded_document_type(hit.file_description):
        return "amendment/waiver/joinder/ancillary document (title)"
    return None


def fetch_candidates(
    client: EdgarClient,
    raw_dir: Path,
    manifest_path: Path,
    skip_log_path: Path,
    limit: int = 300,
    query: str = DEFAULT_QUERY,
    forms: Iterable[str] = DEFAULT_FORMS,
    start_date: date = DEFAULT_START_DATE,
    end_date: date | None = None,
) -> FetchSummary:
    """Search EDGAR, download up to `limit` filtered candidates to
    `raw_dir`, and append their records to the manifest and skip log.
    Safe to re-run: documents already in the manifest or already present
    on disk are skipped without a new download.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = read_existing_doc_ids(manifest_path)
    end = end_date or datetime.now().date()

    downloaded = 0
    skipped = 0
    failed = 0
    new_rows: list[ManifestRow] = []
    new_skips: list[SkipRecord] = []

    for hit in search(client, query, forms, start_date, end):
        if downloaded >= limit:
            break

        reason = _pre_download_skip_reason(hit, existing, raw_dir)
        if reason is not None:
            if reason != ALREADY_DOWNLOADED:
                new_skips.append(SkipRecord(doc_id=hit.doc_id, reason=reason))
                skipped += 1
            continue

        try:
            response = client.get(hit.download_url)
        except Exception as exc:
            # Any failure here (network, retries exhausted, unexpected
            # status) is recorded, never silently dropped, per the spec.
            new_skips.append(SkipRecord(doc_id=hit.doc_id, reason=f"download failed: {exc}"))
            failed += 1
            continue

        if not is_large_enough(len(response.content)):
            new_skips.append(
                SkipRecord(doc_id=hit.doc_id, reason="too small to be a full agreement")
            )
            skipped += 1
            continue

        preview = response.text[:CONTENT_PREVIEW_CHARS]
        if is_excluded_document_type(preview):
            reason = "amendment/waiver/joinder/ancillary document (content)"
            new_skips.append(SkipRecord(doc_id=hit.doc_id, reason=reason))
            skipped += 1
            continue
        if not looks_like_credit_agreement(preview):
            new_skips.append(
                SkipRecord(doc_id=hit.doc_id, reason="not a credit agreement (content)")
            )
            skipped += 1
            continue

        (raw_dir / f"{hit.doc_id}.htm").write_text(response.text, encoding="utf-8")
        new_rows.append(
            ManifestRow(
                doc_id=hit.doc_id,
                company_name=hit.company_name,
                cik=hit.cik,
                form_type=hit.form,
                filing_date=hit.file_date.isoformat(),
                exhibit_name=hit.filename,
                url=hit.download_url,
            )
        )
        existing.add(hit.doc_id)
        downloaded += 1

    append_rows(manifest_path, new_rows)
    append_skips(skip_log_path, new_skips)
    return FetchSummary(downloaded=downloaded, skipped=skipped, failed=failed)
