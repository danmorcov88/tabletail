"""Shared test fixtures.

Tests run against a real PostgreSQL reached via a DSN — the same mechanism
locally and in CI:

* set ``TABLETAIL_TEST_DSN`` to point at a database (CI does this), or
* rely on the bundled demo Postgres from ``examples/docker-compose.yml``.

If no database is reachable, DB-backed tests are skipped — unless
``TABLETAIL_REQUIRE_DB`` is set (CI sets it), in which case they fail loudly so a
misconfigured CI never goes green without actually testing anything.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

DEFAULT_DSN = "postgres://demo:demo@localhost:5433/demo"


def _test_dsn() -> str:
    return os.environ.get("TABLETAIL_TEST_DSN", DEFAULT_DSN)


@pytest.fixture(scope="session")
def dsn() -> str:
    """Return a reachable test DSN, or skip (fail in CI) if none is available."""
    target = _test_dsn()
    try:
        with psycopg.connect(target, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError as exc:
        if os.environ.get("TABLETAIL_REQUIRE_DB"):
            raise
        pytest.skip(f"No test database reachable at {target}: {exc}")
    return target


@pytest.fixture
def writer(dsn: str) -> psycopg.Connection:
    """An autocommit connection used to set up and mutate test data."""
    conn = psycopg.connect(dsn, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def orders(writer: psycopg.Connection) -> str:
    """Create a fresh orders-like table with three rows; drop it afterwards."""
    table = f"tt_{uuid.uuid4().hex[:8]}"
    writer.execute(
        f"""
        CREATE TABLE {table} (
            id         serial PRIMARY KEY,
            customer   text NOT NULL,
            status     text NOT NULL DEFAULT 'pending',
            amount     numeric(10, 2) NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    writer.execute(
        f"INSERT INTO {table} (customer, status, amount) VALUES "
        "('Ana', 'paid', 10.00), ('Bob', 'pending', 20.00), ('Cleo', 'paid', 30.00)"
    )
    try:
        yield table
    finally:
        writer.execute(f"DROP TABLE IF EXISTS {table}")
