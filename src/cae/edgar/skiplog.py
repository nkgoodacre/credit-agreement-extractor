"""Records why a candidate document was not added to the manifest.

Kept as its own append-only CSV, separate from the manifest, so a `cae
fetch` run leaves an audit trail: "558 candidates, 214 downloaded" is not
useful on its own without knowing which of the other 344 were skipped and
why -- the build spec requires every skip or failure to be logged with a
reason, not dropped silently.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_LOG_FIELDS = ["doc_id", "reason"]


@dataclass(frozen=True)
class SkipRecord:
    doc_id: str
    reason: str


def append_skips(path: Path, records: list[SkipRecord]) -> None:
    if not records:
        return
    is_new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SKIP_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
