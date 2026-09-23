"""Query construction and response parsing for EDGAR's full-text search API.

The endpoint and response shape were verified against the live API before
this was written (see docs/DECISIONS.md, Phase 1) rather than assumed from
documentation, which is thin and in places misleading -- notably the
commonly cited page size of 10 is not what the API actually returns.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from cae.edgar.client import EdgarClient

SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# EDGAR's full-text search only paginates through the first 10,000 hits of
# a query; requesting beyond that offset errors.
MAX_OFFSET = 10_000


@dataclass(frozen=True)
class SearchHit:
    """One document reference from an EDGAR full-text search result."""

    accession_no: str  # e.g. "0001213900-22-009497"
    # Filer CIK, taken from _source.ciks[0]. NOT the accession-number
    # prefix -- that is the filing agent's CIK and 404s when used to build
    # a download URL (see docs/DECISIONS.md, Phase 1).
    cik: str
    company_name: str
    form: str
    file_date: date
    filename: str
    file_type: str
    file_description: str | None

    @property
    def doc_id(self) -> str:
        """Stable, filesystem-safe identifier for this document."""
        accession_no_compact = self.accession_no.replace("-", "")
        stem = self.filename.rsplit(".", 1)[0]
        return f"{self.cik}_{accession_no_compact}_{stem}"

    @property
    def download_url(self) -> str:
        accession_no_compact = self.accession_no.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{self.cik}/{accession_no_compact}/{self.filename}"
        )


def _parse_company_name(display_names: Sequence[str]) -> str:
    """Strip the trailing ticker/CIK annotation EDGAR appends, e.g.
    'Acme Corp  (ACME)  (CIK 0001234567)' -> 'Acme Corp'."""
    if not display_names:
        return ""
    return display_names[0].split("  (")[0].strip()


def parse_hit(raw_hit: dict[str, Any]) -> SearchHit:
    """Parse one raw hit (an ``_id`` + ``_source`` pair) from a search
    response into a `SearchHit`."""
    hit_id = str(raw_hit["_id"])
    accession_no, _, filename = hit_id.partition(":")
    source = raw_hit["_source"]
    ciks = source.get("ciks") or []
    if not ciks:
        raise ValueError(f"search hit {hit_id!r} has no ciks; cannot build a download URL")
    file_description = source.get("file_description")
    # EDGAR zero-pads CIKs in _source.ciks (e.g. "0001747172"), but the
    # Archives download URL needs the unpadded form -- verified live (see
    # docs/DECISIONS.md, Phase 1); a padded CIK 404s.
    cik = str(int(ciks[0]))
    return SearchHit(
        accession_no=accession_no,
        cik=cik,
        company_name=_parse_company_name(source.get("display_names") or []),
        form=str(source["form"]),
        file_date=date.fromisoformat(str(source["file_date"])),
        filename=filename,
        file_type=str(source.get("file_type", "")),
        file_description=str(file_description) if file_description else None,
    )


def parse_response(payload: dict[str, Any]) -> tuple[list[SearchHit], int]:
    """Parse a full search response into (hits on this page, total hits)."""
    hits_block = payload["hits"]
    total = int(hits_block["total"]["value"])
    hits = [parse_hit(h) for h in hits_block["hits"]]
    return hits, total


def search(
    client: EdgarClient,
    query: str,
    forms: Iterable[str],
    start_date: date,
    end_date: date,
    max_results: int = MAX_OFFSET,
) -> Iterator[SearchHit]:
    """Yield search hits for `query`, paginating until `max_results` have
    been yielded, the API is exhausted, or EDGAR's pagination ceiling is
    reached. Each page is one rate-limited, retried request via `client`.
    """
    forms_param = ",".join(forms)
    offset = 0
    yielded = 0
    while yielded < max_results and offset < MAX_OFFSET:
        params = {
            "q": query,
            "forms": forms_param,
            "dateRange": "custom",
            "startdt": start_date.isoformat(),
            "enddt": end_date.isoformat(),
            "from": str(offset),
        }
        response = client.get(SEARCH_URL, params=params)
        hits, total = parse_response(response.json())
        if not hits:
            return
        for hit in hits:
            if yielded >= max_results:
                return
            yield hit
            yielded += 1
        offset += len(hits)
        if offset >= total:
            return
