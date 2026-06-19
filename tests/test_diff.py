"""Snapshot and compare correctness."""

from __future__ import annotations

from tabletail.diff import compare, snapshot
from tabletail.models import Snapshot

COLUMNS = ["id", "customer", "status"]


def make(rows: list[dict]) -> Snapshot:
    return Snapshot("orders", ["id"], COLUMNS, rows, "2026-01-01T00:00:00+00:00")


# --- pure compare() logic (no database) ----------------------------------- #


def test_no_changes():
    snap = make([{"id": 1, "customer": "Ana", "status": "paid"}])
    result = compare(snap, snap)
    assert result.is_empty
    assert result.total == 0


def test_added_row():
    before = make([{"id": 1, "customer": "Ana", "status": "paid"}])
    after = make(
        [
            {"id": 1, "customer": "Ana", "status": "paid"},
            {"id": 2, "customer": "Bob", "status": "new"},
        ]
    )
    result = compare(before, after)
    assert [c.key for c in result.added] == [(2,)]
    assert not result.removed and not result.changed


def test_removed_row():
    before = make(
        [
            {"id": 1, "customer": "Ana", "status": "paid"},
            {"id": 2, "customer": "Bob", "status": "new"},
        ]
    )
    after = make([{"id": 1, "customer": "Ana", "status": "paid"}])
    result = compare(before, after)
    assert [c.key for c in result.removed] == [(2,)]
    assert not result.added and not result.changed


def test_changed_row_identifies_columns():
    before = make([{"id": 1, "customer": "Ana", "status": "paid"}])
    after = make([{"id": 1, "customer": "Ana", "status": "shipped"}])
    result = compare(before, after)
    assert len(result.changed) == 1
    change = result.changed[0]
    assert change.key == (1,)
    assert change.columns == ["status"]
    assert change.before["status"] == "paid"
    assert change.after["status"] == "shipped"


def test_multiple_changed_columns():
    before = make([{"id": 1, "customer": "Ana", "status": "paid"}])
    after = make([{"id": 1, "customer": "Anna", "status": "shipped"}])
    result = compare(before, after)
    assert result.changed[0].columns == ["customer", "status"]


def test_mixed_changes():
    before = make(
        [
            {"id": 1, "customer": "Ana", "status": "paid"},
            {"id": 2, "customer": "Bob", "status": "pending"},
            {"id": 3, "customer": "Cleo", "status": "paid"},
        ]
    )
    after = make(
        [
            {"id": 1, "customer": "Ana", "status": "paid"},  # unchanged
            {"id": 2, "customer": "Bob", "status": "shipped"},  # changed
            {"id": 4, "customer": "Dan", "status": "new"},  # added; id=3 removed
        ]
    )
    result = compare(before, after)
    assert {c.key for c in result.added} == {(4,)}
    assert {c.key for c in result.removed} == {(3,)}
    assert {c.key for c in result.changed} == {(2,)}


# --- snapshot() against a real database ------------------------------------ #


def test_snapshot_reads_table(dsn, orders):
    snap = snapshot(dsn, orders)
    assert snap.pk_columns == ["id"]
    assert {"id", "customer", "status", "amount", "updated_at"}.issubset(snap.columns)
    assert len(snap.rows) == 3


def test_snapshot_roundtrip(dsn, orders, tmp_path):
    snap = snapshot(dsn, orders)
    path = tmp_path / "snap.json"
    snap.save(path)
    loaded = Snapshot.load(path)
    assert loaded.rows == snap.rows
    assert compare(snap, loaded).is_empty


def test_snapshot_then_mutate_then_compare(dsn, orders, writer):
    before = snapshot(dsn, orders)
    writer.execute(f"UPDATE {orders} SET status = 'shipped' WHERE id = 1")
    writer.execute(f"DELETE FROM {orders} WHERE id = 2")
    writer.execute(f"INSERT INTO {orders} (customer, status, amount) VALUES ('Dan', 'new', 9.99)")
    after = snapshot(dsn, orders)

    result = compare(before, after)
    assert len(result.added) == 1
    assert len(result.removed) == 1
    assert len(result.changed) == 1
    assert result.changed[0].columns == ["status"]


def test_snapshot_where_filter(dsn, orders):
    snap = snapshot(dsn, orders, where="status = 'paid'")
    assert len(snap.rows) == 2
    assert all(row["status"] == "paid" for row in snap.rows)
