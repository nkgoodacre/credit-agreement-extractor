"""The fetch manifest: the durable record of what `cae fetch` downloaded.

Kept separate from fetch orchestration so it can be read back cheaply to
make `cae fetch` resumable -- skip doc_ids already recorded here -- without
re-parsing every file under data/raw/ on each run.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

MANIFEST_FIELDS = [
    "doc_id",
    "company_name",
    "cik",
    "form_type",
    "filing_date",
    "exhibit_name",
    "url",
]


@dataclass(frozen=True)
class ManifestRow:
    doc_id: str
    company_name: str
    cik: str
    form_type: str
    filing_date: str  # ISO date, kept as str for a stable CSV round-trip
    exhibit_name: str
    url: str


def read_manifest(path: Path) -> list[ManifestRow]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [ManifestRow(**{name: row[name] for name in MANIFEST_FIELDS}) for row in reader]


def read_existing_doc_ids(path: Path) -> set[str]:
    return {row.doc_id for row in read_manifest(path)}


def append_rows(path: Path, rows: list[ManifestRow]) -> None:
    """Append `rows` to the manifest CSV, writing the header only if the
    file doesn't exist yet. Called once per `cae fetch` run rather than
    once per row, so a resumed run's I/O stays cheap."""
    if not rows:
        return
    is_new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
