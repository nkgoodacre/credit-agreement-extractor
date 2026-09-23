"""Tests for query building and response parsing in cae.edgar.search.

Uses a saved, real (trimmed) EDGAR full-text search response as a fixture
-- captured live before this module was written, per docs/DECISIONS.md --
rather than a hand-typed guess at the shape.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx

from cae.edgar.client import EdgarClient
from cae.edgar.search import SEARCH_URL, parse_hit, parse_response, search

FIXTURES = Path(__file__).parent / "fixtures" / "edgar"


def _load_fixture() -> dict[str, object]:
    return json.loads((FIXTURES / "search_response_mixed.json").read_text(encoding="utf-8"))


def test_parse_response_returns_all_hits_and_total() -> None:
    hits, total = parse_response(_load_fixture())
    assert total == 10
    assert len(hits) == 10


def test_parse_hit_uses_ciks_not_accession_prefix() -> None:
    """The accession number '0001213900-22-009497' starts with the filing
    agent's CIK (0001213900), not the filer's. The filer's real CIK
    (0001747172) only appears in _source.ciks -- see docs/DECISIONS.md,
    Phase 1, for how this was discovered."""
    payload = _load_fixture()
    raw_hit = next(
        h
        for h in payload["hits"]["hits"]  # type: ignore[index]
        if h["_id"] == "0001213900-22-009497:ea156212ex10-1_kayneanderson.htm"
    )
    hit = parse_hit(raw_hit)
    assert hit.cik == "1747172"
    assert hit.accession_no == "0001213900-22-009497"
    assert "1747172" in hit.download_url
    assert "1213900" not in hit.download_url.split("/data/")[1].split("/")[0]


def test_parse_hit_strips_ticker_and_cik_from_company_name() -> None:
    payload = _load_fixture()
    raw_hit = next(
        h
        for h in payload["hits"]["hits"]  # type: ignore[index]
        if h["_id"] == "0000950157-22-000211:ex10-1.htm"
    )
    hit = parse_hit(raw_hit)
    assert hit.company_name == "SCIENTIFIC GAMES CORP"
    assert hit.file_date == date(2022, 3, 1)
    assert hit.file_description == "AMENDMENT NO. 9"


def test_doc_id_is_stable_and_filesystem_safe() -> None:
    payload = _load_fixture()
    raw_hit = payload["hits"]["hits"][0]  # type: ignore[index]
    hit = parse_hit(raw_hit)
    assert hit.doc_id == parse_hit(raw_hit).doc_id
    assert "/" not in hit.doc_id
    assert ":" not in hit.doc_id


def test_search_paginates_until_exhausted() -> None:
    """A fake two-page result set: page 1 has 2 hits, page 2 has 1 and
    signals exhaustion via a total of 3."""
    page1 = _load_fixture()
    hits_list = page1["hits"]["hits"]  # type: ignore[index]
    page_one_payload = {"hits": {"total": {"value": 3, "relation": "eq"}, "hits": hits_list[:2]}}
    page_two_payload = {"hits": {"total": {"value": 3, "relation": "eq"}, "hits": hits_list[2:3]}}
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        offset = request.url.params.get("from", "0")
        payload = page_one_payload if offset == "0" else page_two_payload
        return httpx.Response(200, json=payload, request=request)

    client = EdgarClient(
        user_agent="test-agent test@example.com", transport=httpx.MockTransport(handler)
    )
    results = list(search(client, "test query", ["8-K"], date(2022, 1, 1), date(2022, 12, 31)))
    assert len(results) == 3
    assert len(calls) == 2
    assert all(SEARCH_URL in c for c in calls)


def test_search_stops_at_max_results() -> None:
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = EdgarClient(
        user_agent="test-agent test@example.com", transport=httpx.MockTransport(handler)
    )
    results = list(
        search(client, "q", ["8-K"], date(2022, 1, 1), date(2022, 12, 31), max_results=3)
    )
    assert len(results) == 3
