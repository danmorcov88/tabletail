"""Snapshotting a table and comparing two snapshots on the primary key."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .connection import connect, table_identifier
from .models import Change, DiffResult, Row, Snapshot


class SnapshotError(Exception):
    """Raised when a table cannot be snapshotted (missing table, no primary key)."""


def _normalize(value: Any) -> Any:
    """Convert a database value to a JSON-friendly primitive.

    Keeping snapshots as primitives means in-memory and on-disk snapshots compare
    identically, and the JSON file is human-readable.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (list, tuple, dict)):
        return value
    return str(value)


def _primary_key_columns(conn: psycopg.Connection, table: str) -> list[str]:
    """Return the primary-key columns of a table, in key order."""
    query = """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
        ORDER BY array_position(i.indkey, a.attnum)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (table,))
            return [r[0] for r in cur.fetchall()]
    except psycopg.errors.UndefinedTable as exc:
        raise SnapshotError(f"Table '{table}' does not exist.") from exc


def snapshot(dsn: str, table: str, where: str | None = None) -> Snapshot:
    """Read a table (optionally filtered) into a Snapshot, ordered by primary key."""
    with connect(dsn) as conn:
        pk_columns = _primary_key_columns(conn, table)
        if not pk_columns:
            raise SnapshotError(
                f"Table '{table}' has no primary key; tabletail needs one to match rows."
            )

        ident = table_identifier(table)
        query = sql.SQL("SELECT * FROM {}").format(ident)
        if where:
            query += sql.SQL(" WHERE ") + sql.SQL(where)  # user-supplied filter on their own data
        order_by = sql.SQL(", ").join(sql.Identifier(c) for c in pk_columns)
        query += sql.SQL(" ORDER BY ") + order_by

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            columns = [d.name for d in cur.description]
            rows: list[Row] = [{k: _normalize(v) for k, v in row.items()} for row in cur]

        captured_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        return Snapshot(
            table=table,
            pk_columns=pk_columns,
            columns=columns,
            rows=rows,
            captured_at=captured_at,
            where=where,
        )


def compare(before: Snapshot, after: Snapshot) -> DiffResult:
    """Diff two snapshots, matching rows by primary key."""
    if before.pk_columns != after.pk_columns:
        raise SnapshotError(
            "Snapshots have different primary keys "
            f"({before.pk_columns} vs {after.pk_columns}); cannot compare."
        )

    # Column order: keep `before`'s order, then append any columns new in `after`.
    columns = list(before.columns)
    columns += [c for c in after.columns if c not in before.columns]

    before_rows = before.by_key()
    after_rows = after.by_key()

    result = DiffResult(table=after.table, pk_columns=after.pk_columns, columns=columns)

    for key, row in after_rows.items():
        if key not in before_rows:
            result.added.append(Change(key=key, kind="added", after=row))

    for key, row in before_rows.items():
        if key not in after_rows:
            result.removed.append(Change(key=key, kind="removed", before=row))

    for key, old_row in before_rows.items():
        new_row = after_rows.get(key)
        if new_row is None:
            continue
        changed_cols = [c for c in columns if old_row.get(c) != new_row.get(c)]
        if changed_cols:
            result.changed.append(
                Change(
                    key=key,
                    kind="changed",
                    before=old_row,
                    after=new_row,
                    columns=changed_cols,
                )
            )

    return result
