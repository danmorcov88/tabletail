"""Internal data structures for snapshots and diffs.

Snapshot values are always stored as JSON-friendly primitives (str, int, float,
bool, None) so that an in-memory snapshot and one round-tripped through a file
compare identically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SNAPSHOT_FORMAT = 1

# A primary-key value: the tuple of normalized pk-column values identifying a row.
Key = tuple[Any, ...]
# A row: column name -> normalized value.
Row = dict[str, Any]


@dataclass
class Snapshot:
    """The captured state of a table at one point in time."""

    table: str
    pk_columns: list[str]
    columns: list[str]
    rows: list[Row]
    captured_at: str
    where: str | None = None

    def key_of(self, row: Row) -> Key:
        """The primary-key tuple for a row."""
        return tuple(row[c] for c in self.pk_columns)

    def by_key(self) -> dict[Key, Row]:
        """Index the rows by primary key."""
        return {self.key_of(row): row for row in self.rows}

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": SNAPSHOT_FORMAT,
            "table": self.table,
            "pk_columns": self.pk_columns,
            "columns": self.columns,
            "captured_at": self.captured_at,
            "where": self.where,
            "rows": self.rows,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(
            table=data["table"],
            pk_columns=data["pk_columns"],
            columns=data["columns"],
            rows=data["rows"],
            captured_at=data["captured_at"],
            where=data.get("where"),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Snapshot:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


@dataclass
class Change:
    """One row-level difference between two snapshots."""

    key: Key
    kind: str  # "added" | "removed" | "changed"
    before: Row | None = None
    after: Row | None = None
    columns: list[str] = field(default_factory=list)  # changed columns (kind == "changed")


@dataclass
class DiffResult:
    """The full set of differences between two snapshots, matched by primary key."""

    table: str
    pk_columns: list[str]
    columns: list[str]
    added: list[Change] = field(default_factory=list)
    removed: list[Change] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)

    @property
    def is_empty(self) -> bool:
        return self.total == 0
