"""Live tail via polling.

The polling tail is, at heart, a repeated diff: each interval we re-read the
table and compare it to the previous read, streaming any added / changed /
removed rows to the terminal.

Known limitations (honest by design):

* It can miss changes that happen and are undone *within* a single interval
  (e.g. a row inserted and deleted between two polls).
* Change detection compares the full row against the previous poll, matched by
  primary key — so it needs a primary key and sees only the net change per poll.

For complete, every-change capture (including transient rows) use the WAL mode.
"""

from __future__ import annotations

import time

from . import render
from .connection import connect
from .diff import compare, read_snapshot


def tail_poll(dsn: str, table: str, interval: float = 2.0, where: str | None = None) -> None:
    """Poll a table every ``interval`` seconds and stream changes until Ctrl-C."""
    # autocommit so every poll sees freshly committed data and no transaction lingers.
    with connect(dsn, autocommit=True) as conn:
        previous = read_snapshot(conn, table, where=where)
        render.tail_header(table, len(previous.rows), interval, where)

        try:
            while True:
                time.sleep(interval)
                current = read_snapshot(conn, table, where=where)
                result = compare(previous, current)
                if not result.is_empty:
                    render.render_changes(result)
                previous = current
        except KeyboardInterrupt:
            render.console.print("[dim]stopped.[/]")
