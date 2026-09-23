"""Tests for the fetch manifest: round-tripping and resumability support."""

from __future__ import annotations

from pathlib import Path

from cae.edgar.manifest import (
    ManifestRow,
    append_rows,
    read_existing_doc_ids,
    read_manifest,
)

ROW_A = ManifestRow(
    doc_id="1747172_000121390022009497_ea156212ex10-1_kayneanderson",
    company_name="Kayne Anderson BDC, Inc.",
    cik="1747172",
    form_type="8-K",
    filing_date="2022-02-25",
    exhibit_name="ea156212ex10-1_kayneanderson.htm",
    url="https://www.sec.gov/Archives/edgar/data/1747172/000121390022009497/ea156212ex10-1_kayneanderson.htm",
)
ROW_B = ManifestRow(
    doc_id="750004_000095015722000211_ex10-1",
    company_name="SCIENTIFIC GAMES CORP",
    cik="750004",
    form_type="8-K",
    filing_date="2022-03-01",
    exhibit_name="ex10-1.htm",
    url="https://www.sec.gov/Archives/edgar/data/750004/000095015722000211/ex10-1.htm",
)


def test_read_manifest_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_manifest(tmp_path / "manifest.csv") == []
    assert read_existing_doc_ids(tmp_path / "manifest.csv") == set()


def test_append_and_read_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    append_rows(path, [ROW_A])
    append_rows(path, [ROW_B])

    rows = read_manifest(path)
    assert rows == [ROW_A, ROW_B]
    assert read_existing_doc_ids(path) == {ROW_A.doc_id, ROW_B.doc_id}


def test_append_writes_header_once(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    append_rows(path, [ROW_A])
    append_rows(path, [ROW_B])

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("doc_id,")
    assert sum(1 for line in lines if line.startswith("doc_id,")) == 1
    assert len(lines) == 3  # header + 2 rows


def test_append_empty_list_does_not_create_file(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    append_rows(path, [])
    assert not path.exists()
