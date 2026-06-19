"""DSN resolution and read-only PostgreSQL connections.

Everything tabletail does is read-only. The connection is opened in read-only
mode so the tool can *never* modify the data it is watching, even by accident.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import sql


class ConnectionError(Exception):
    """Raised when a DSN is missing or a connection cannot be established."""


def resolve_dsn(dsn: str | None) -> str:
    """Return the DSN from the flag, falling back to the DATABASE_URL env var."""
    resolved = dsn or os.environ.get("DATABASE_URL")
    if not resolved:
        raise ConnectionError(
            "No connection string. Pass --dsn or set the DATABASE_URL environment variable."
        )
    return resolved


@contextmanager
def connect(
    dsn: str, autocommit: bool = False, read_only: bool = True
) -> Iterator[psycopg.Connection]:
    """Open a connection to PostgreSQL and close it on exit.

    By default the session is read-only — a hard guarantee the tool can never
    modify user data. WAL mode passes ``read_only=False`` because consuming a
    replication slot advances server-side replication state (it still never
    touches user tables). Pass ``autocommit=True`` for long-lived streaming so
    each query sees freshly committed data and no idle transaction lingers.
    """
    try:
        conn = psycopg.connect(dsn)
    except psycopg.OperationalError as exc:
        raise ConnectionError(f"Could not connect to PostgreSQL: {exc}") from exc
    try:
        conn.read_only = read_only
        conn.autocommit = autocommit
        yield conn
    finally:
        conn.close()


def table_identifier(table: str) -> sql.Composable:
    """Build a safe, optionally schema-qualified identifier (e.g. public.orders)."""
    parts = table.split(".")
    return sql.SQL(".").join(sql.Identifier(p) for p in parts)
