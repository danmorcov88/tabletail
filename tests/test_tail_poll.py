"""Polling tail change-detection core (tested without the long-running loop)."""

from __future__ import annotations

from tabletail.connection import connect
from tabletail.diff import compare, read_snapshot
from tabletail.models import Snapshot

COLUMNS = ["id", "status"]


def make(rows: list[dict]) -> Snapshot:
    return Snapshot("orders", ["id"], COLUMNS, rows, "2026-01-01T00:00:00+00:00")


def test_net_change_per_interval():
    """Two updates between polls collapse into a single observed change."""
    before = make([{"id": 1, "status": "a"}])
    after = make([{"id": 1, "status": "c"}])  # a -> b -> c, but we only see a -> c
    result = compare(before, after)
    assert len(result.changed) == 1
    assert result.changed[0].before["status"] == "a"
    assert result.changed[0].after["status"] == "c"


def test_poll_detects_insert_update_delete(dsn, orders, writer):
    with connect(dsn, autocommit=True) as conn:
        before = read_snapshot(conn, orders)
        writer.execute(f"UPDATE {orders} SET status = 'shipped' WHERE id = 1")
        writer.execute(f"DELETE FROM {orders} WHERE id = 2")
        writer.execute(
            f"INSERT INTO {orders} (customer, status, amount) VALUES ('Dan', 'new', 9.99)"
        )
        after = read_snapshot(conn, orders)

    result = compare(before, after)
    assert {c.key for c in result.changed} and result.changed[0].columns == ["status"]
    assert len(result.added) == 1
    assert len(result.removed) == 1


def test_poll_reports_no_changes_when_idle(dsn, orders):
    with connect(dsn, autocommit=True) as conn:
        first = read_snapshot(conn, orders)
        second = read_snapshot(conn, orders)
    assert compare(first, second).is_empty
