"""WAL decoding: pure parser units, plus a real slot lifecycle test."""

from __future__ import annotations

import uuid

import pytest

from tabletail import tail_wal as w
from tabletail.connection import connect
from tabletail.diff import read_snapshot

# --- pure parsing / normalization (no database) ---------------------------- #


def test_normalize_typed_basics():
    assert w._normalize_typed("integer", "5") == 5
    assert w._normalize_typed("numeric", "10.50") == "10.50"  # kept as string like snapshots
    assert w._normalize_typed("text", "hi") == "hi"
    assert w._normalize_typed("boolean", "t") is True
    assert w._normalize_typed("integer", None) is None


def test_timestamp_matches_iso():
    # PostgreSQL text form -> the same ISO string a snapshot would store.
    iso = w._ts_to_iso("2026-06-19 08:36:21.042433+00")
    assert iso == "2026-06-19T08:36:21.042433+00:00"


def test_parse_test_decoding_insert():
    line = (
        "table public.orders: INSERT: id[integer]:6 customer[text]:'Vlad Nou' "
        "status[text]:'pending' amount[numeric]:75.25"
    )
    events = w._parse_test_decoding(line)
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == "insert"
    assert event["schema"] == "public"
    assert event["table"] == "orders"
    assert event["row"] == {"id": 6, "customer": "Vlad Nou", "status": "pending", "amount": "75.25"}


def test_parse_test_decoding_handles_quotes_and_spaces():
    line = "table public.orders: INSERT: id[integer]:1 customer[text]:'O''Brien & Sons'"
    row = w._parse_test_decoding(line)[0]["row"]
    assert row["customer"] == "O'Brien & Sons"


def test_parse_test_decoding_delete_key_only():
    events = w._parse_test_decoding("table public.orders: DELETE: id[integer]:5")
    assert events[0]["kind"] == "delete"
    assert events[0]["key"] == {"id": 5}


def test_parse_test_decoding_skips_begin_commit():
    assert w._parse_test_decoding("BEGIN 742") == []
    assert w._parse_test_decoding("COMMIT 742") == []


def test_parse_wal2json_update():
    data = (
        '{"action":"U","schema":"public","table":"orders",'
        '"columns":[{"name":"id","type":"integer","value":2},'
        '{"name":"status","type":"text","value":"paid"}],'
        '"identity":[{"name":"id","type":"integer","value":2}]}'
    )
    event = w._parse_wal2json(data)[0]
    assert event["kind"] == "update"
    assert event["row"] == {"id": 2, "status": "paid"}
    assert event["key"] == {"id": 2}


# --- real replication slot lifecycle --------------------------------------- #


def test_wal_captures_insert_update_delete(dsn, orders, writer):
    with connect(dsn, autocommit=True, read_only=False) as conn:
        try:
            w._require_logical(conn)
        except w.WalError as exc:
            pytest.skip(str(exc))

        seed = read_snapshot(conn, orders)
        cache = seed.by_key()
        slot = f"tt_slot_{uuid.uuid4().hex[:10]}"
        plugin = w._create_slot(conn, slot)
        try:
            writer.execute(
                f"INSERT INTO {orders} (customer, status, amount) VALUES ('Zoe', 'new', 1.00)"
            )
            # Ana is 'paid'; change it so exactly one column differs.
            writer.execute(f"UPDATE {orders} SET status = 'shipped' WHERE id = 1")
            writer.execute(f"DELETE FROM {orders} WHERE id = 2")
            changes = w._consume_once(
                conn,
                slot,
                w._get_changes_sql(plugin),
                plugin,
                w._target(orders),
                seed.pk_columns,
                cache,
            )
        finally:
            w._drop_slot(conn, slot)

    kinds = [c.kind for c in changes]
    assert "added" in kinds and "changed" in kinds and "removed" in kinds

    deleted = next(c for c in changes if c.kind == "removed")
    assert deleted.before is not None  # full old row recovered from cache
    assert deleted.before["customer"] == "Bob"

    updated = next(c for c in changes if c.kind == "changed")
    assert updated.columns == ["status"]  # updated_at not spuriously flagged


def test_wal_slot_is_dropped_after_use(dsn, orders, writer):
    with connect(dsn, autocommit=True, read_only=False) as conn:
        try:
            w._require_logical(conn)
        except w.WalError as exc:
            pytest.skip(str(exc))

        slot = f"tt_slot_{uuid.uuid4().hex[:10]}"
        w._create_slot(conn, slot)
        w._drop_slot(conn, slot)

        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_replication_slots WHERE slot_name = %s", (slot,))
            assert cur.fetchone() is None
