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
def connect(dsn: str, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    """Open a read-only connection to PostgreSQL and close it on exit.

    Pass ``autocommit=True`` for long-lived polling so each query sees freshly
    committed data and no idle transaction is held open between polls.
    """
    try:
        conn = psycopg.connect(dsn)
    except psycopg.OperationalError as exc:
        raise ConnectionError(f"Could not connect to PostgreSQL: {exc}") from exc
    try:
        # Read-only at the session level: a hard guarantee, not just convention.
        conn.read_only = True
        conn.autocommit = autocommit
        yield conn
    finally:
        conn.close()


def table_identifier(table: str) -> sql.Composable:
    """Build a safe, optionally schema-qualified identifier (e.g. public.orders)."""
    parts = table.split(".")
    return sql.SQL(".").join(sql.Identifier(p) for p in parts)
