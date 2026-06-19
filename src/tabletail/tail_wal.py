"""Live tail via logical replication (WAL decoding).

Unlike polling, this captures *every* change — including DELETEs and rows that
appear and vanish quickly — because PostgreSQL buffers all changes in a
replication slot until we read them. We:

1. create a TEMPORARY logical replication slot,
2. read decoded changes from it with ``pg_logical_slot_get_changes``,
3. render them live, and
4. always drop the slot on the way out.

Slot cleanup is critical: an orphaned slot makes the server retain WAL forever.
The slot is created TEMPORARY (PostgreSQL drops it automatically when our session
ends, even on a crash) *and* we drop it explicitly in a ``finally`` block.

Output plugin: ``wal2json`` is used when installed (clean JSON); otherwise we fall
back to ``test_decoding``, which ships with stock PostgreSQL. (The plan mentioned
``pgoutput`` as the fallback, but its binary protocol cannot be consumed through
the ``pg_logical_slot_get_changes`` SQL function — ``test_decoding`` can.)

To show old → new on UPDATE and the full row on DELETE without altering the
user's table (no ``REPLICA IDENTITY FULL``), we keep an in-memory cache of the
current rows, seeded from one initial read and updated as changes stream in.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from typing import Any

import psycopg

from . import render
from .connection import connect
from .diff import read_snapshot
from .models import Change, Row

PREFERRED_PLUGINS = ("wal2json", "test_decoding")
POLL_SECONDS = 0.5


class WalError(Exception):
    """Raised when logical replication cannot be used (config, privileges, plugins)."""


# --------------------------------------------------------------------------- #
# Value normalization (shared by both output plugins)                         #
# --------------------------------------------------------------------------- #

_TZ_RE = re.compile(r"[+-]\d{2}(?::?\d{2})?$")


def _ts_to_iso(text: str) -> str:
    """Normalize a PostgreSQL timestamp string to match snapshot ISO formatting."""
    s = text.strip().strip("'")
    candidate = s.replace(" ", "T", 1)
    match = _TZ_RE.search(candidate)
    if match:
        tz = match.group(0)
        body, sign, digits = candidate[: match.start()], tz[0], tz[1:].replace(":", "")
        if len(digits) == 2:
            digits += "00"
        candidate = f"{body}{sign}{digits[:2]}:{digits[2:]}"
    try:
        return dt.datetime.fromisoformat(candidate).isoformat()
    except ValueError:
        return s


def _normalize_typed(type_name: str, value: Any) -> Any:
    """Coerce a decoded value into the same primitive form snapshots use."""
    if value is None:
        return None
    t = type_name.lower()
    if "timestamp" in t:
        return _ts_to_iso(str(value))
    if t in ("smallint", "integer", "bigint", "int2", "int4", "int8", "oid"):
        return int(value)
    if t in ("boolean", "bool"):
        return value if isinstance(value, bool) else str(value).lower() in ("t", "true")
    # numeric/text/uuid/json/etc: keep as string (matches Snapshot normalization).
    return str(value)


# --------------------------------------------------------------------------- #
# Decoded-change parsing                                                       #
# --------------------------------------------------------------------------- #
# Each parser yields dicts: {"kind", "schema", "table", "row", "key"} where
# row is the new tuple (insert/update) and key is the identifying PK (update/delete).


def _parse_wal2json(data: str) -> list[dict[str, Any]]:
    obj = json.loads(data)
    action = obj.get("action")
    kinds = {"I": "insert", "U": "update", "D": "delete"}
    if action not in kinds:
        return []  # begin / commit / message / truncate
    def _fields(items: list[dict]) -> dict[str, Any]:
        return {c["name"]: _normalize_typed(c.get("type", ""), c.get("value")) for c in items}

    columns = _fields(obj.get("columns", []))
    identity = _fields(obj.get("identity", []))
    return [
        {
            "kind": kinds[action],
            "schema": obj.get("schema"),
            "table": obj.get("table"),
            "row": columns or None,
            "key": identity or None,
        }
    ]


_FIELD_RE = re.compile(r"(?P<name>[^\s\[]+)\[(?P<type>[^\]]+)\]:")


def _parse_test_decoding(data: str) -> list[dict[str, Any]]:
    if not data.startswith("table "):
        return []  # BEGIN / COMMIT
    header, _, tail = data[len("table ") :].partition(": ")
    action_word, _, fields = tail.partition(": ")
    kinds = {"INSERT": "insert", "UPDATE": "update", "DELETE": "delete"}
    if action_word not in kinds:
        return []
    schema, _, table = header.partition(".")
    row = _scan_test_decoding_fields(fields)
    return [{"kind": kinds[action_word], "schema": schema, "table": table, "row": row, "key": row}]


def _scan_test_decoding_fields(text: str) -> dict[str, Any]:
    """Parse `col[type]:value col[type]:value ...`, honoring quoted strings."""
    fields: dict[str, Any] = {}
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] == " ":
            i += 1
        match = _FIELD_RE.match(text, i)
        if not match:
            break
        name, type_name = match.group("name"), match.group("type")
        i = match.end()
        if i < n and text[i] == "'":
            i += 1
            chars: list[str] = []
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":  # '' -> escaped quote
                        chars.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                chars.append(text[i])
                i += 1
            fields[name] = _normalize_typed(type_name, "".join(chars))
        else:
            start = i
            while i < n and text[i] != " ":
                i += 1
            raw = text[start:i]
            fields[name] = None if raw == "null" else _normalize_typed(type_name, raw)
    return fields


# --------------------------------------------------------------------------- #
# Slot lifecycle                                                               #
# --------------------------------------------------------------------------- #


def _require_logical(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SHOW wal_level")
        level = cur.fetchone()[0]
    if level != "logical":
        raise WalError(
            f"WAL mode needs wal_level=logical, but the server is '{level}'.\n"
            "  Set it with: ALTER SYSTEM SET wal_level = 'logical';  then restart PostgreSQL\n"
            "  (or add `command: postgres -c wal_level=logical` for a Docker server)."
        )


def _create_slot(conn: psycopg.Connection, slot: str) -> str:
    """Create a temporary slot with the best available plugin; return the plugin used."""
    last_error: Exception | None = None
    for plugin in PREFERRED_PLUGINS:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_create_logical_replication_slot(%s, %s, true)", (slot, plugin)
                )
            return plugin
        except psycopg.errors.InsufficientPrivilege as exc:
            raise WalError(
                "WAL mode needs the REPLICATION privilege (or a superuser).\n"
                "  Grant it with: ALTER ROLE <user> WITH REPLICATION;"
            ) from exc
        except psycopg.errors.ConfigurationLimitExceeded as exc:
            raise WalError(
                "No replication slots available (max_replication_slots reached)."
            ) from exc
        except psycopg.Error as exc:
            last_error = exc  # plugin missing — try the next one
    raise WalError(
        "Could not create a logical replication slot. None of the output plugins "
        f"{PREFERRED_PLUGINS} are available.\n  Last error: {last_error}"
    )


def _drop_slot(conn: psycopg.Connection, slot: str) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_drop_replication_slot(%s)", (slot,))
    except psycopg.Error:
        # Temporary slots vanish with the session anyway; never mask the real exit.
        pass


# --------------------------------------------------------------------------- #
# Main loop                                                                    #
# --------------------------------------------------------------------------- #


def _target(table: str) -> tuple[str | None, str]:
    if "." in table:
        schema, name = table.split(".", 1)
        return schema, name
    return None, table


def _changes_from_data(
    data: str, plugin: str, target: tuple[str | None, str], pk: list[str], cache: dict
) -> list[Change]:
    """Parse one decoded message and fold it into the row cache, returning Changes."""
    parse = _parse_wal2json if plugin == "wal2json" else _parse_test_decoding
    target_schema, target_table = target
    out: list[Change] = []

    for event in parse(data):
        if event["table"] != target_table:
            continue
        if target_schema is not None and event["schema"] != target_schema:
            continue

        kind, row, key_fields = event["kind"], event["row"], event["key"]

        if kind == "insert":
            new_row: Row = row or {}
            key = tuple(new_row.get(c) for c in pk)
            cache[key] = new_row
            out.append(Change(key=key, kind="added", after=new_row))
        elif kind == "update":
            new_row = row or {}
            new_key = tuple(new_row.get(c) for c in pk)
            old_key = tuple((key_fields or {}).get(c, new_row.get(c)) for c in pk)
            old_row = cache.pop(old_key, None)
            cache[new_key] = new_row
            changed = [c for c, v in new_row.items() if (old_row or {}).get(c) != v]
            out.append(
                Change(key=new_key, kind="changed", before=old_row, after=new_row, columns=changed)
            )
        elif kind == "delete":
            key = tuple((key_fields or {}).get(c) for c in pk)
            old_row = cache.pop(key, None)
            out.append(Change(key=key, kind="removed", before=old_row))

    return out


def tail_wal(dsn: str, table: str, where: str | None = None) -> None:
    """Stream every change to a table via a temporary logical replication slot."""
    if where:
        raise WalError("--where is not supported with --mode wal.")

    slot = f"tabletail_{os.getpid()}"
    target = _target(table)

    # Not read-only: slot consumption advances replication state (never user data).
    with connect(dsn, autocommit=True, read_only=False) as conn:
        _require_logical(conn)

        seed = read_snapshot(conn, table)  # also validates table + primary key
        pk, columns = seed.pk_columns, seed.columns
        cache: dict[tuple, Row] = seed.by_key()

        plugin = _create_slot(conn, slot)
        get_changes = (
            "SELECT data FROM pg_logical_slot_get_changes(%s, NULL, NULL, "
            "'format-version', '2', 'numeric-data-types-as-string', '1')"
            if plugin == "wal2json"
            else "SELECT data FROM pg_logical_slot_get_changes(%s, NULL, NULL)"
        )
        try:
            render.tail_header_wal(table, len(cache), plugin)
            while True:
                with conn.cursor() as cur:
                    cur.execute(get_changes, (slot,))
                    rows = cur.fetchall()
                batch: list[Change] = []
                for (data,) in rows:
                    batch.extend(_changes_from_data(data, plugin, target, pk, cache))
                if batch:
                    render.render_stream(batch, columns, pk)
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            render.console.print("[dim]stopped.[/]")
        finally:
            _drop_slot(conn, slot)
