"""Command-line interface for tabletail.

Three commands mirror the two things the tool does:

* ``tail``     — follow changes in a table live (polling or WAL).
* ``snapshot`` — capture the current state of a table to a file.
* ``diff``     — compare two snapshots, or take two snapshots over time.

In this scaffolding phase the commands only validate and echo their
arguments; the real behaviour arrives in later phases.
"""

from __future__ import annotations

import time
from pathlib import Path

import typer

from . import __version__, render
from . import diff as diff_mod
from .connection import ConnectionError, resolve_dsn
from .diff import SnapshotError
from .models import Snapshot
from .tail_poll import tail_poll
from .tail_wal import WalError, tail_wal

app = typer.Typer(
    name="tabletail",
    help="See what changes in a PostgreSQL table — live (tail) or between snapshots (diff).",
    add_completion=False,
    no_args_is_help=True,
)

DSN_HELP = "PostgreSQL connection string. Falls back to the DATABASE_URL environment variable."


def _fail(message: str) -> typer.Exit:
    """Print an error in red and return the exception for the caller to raise."""
    render.console.print(f"[bold red]error:[/] {message}")
    return typer.Exit(code=1)


def _capture(dsn: str | None, table: str, where: str | None) -> Snapshot:
    """Resolve the DSN, snapshot the table, and translate failures to clean errors."""
    try:
        return diff_mod.snapshot(resolve_dsn(dsn), table, where=where)
    except (ConnectionError, SnapshotError) as exc:
        raise _fail(str(exc)) from exc


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tabletail {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """tabletail — `tail -f` and `git diff`, but for PostgreSQL tables."""


@app.command()
def tail(
    table: str = typer.Option(..., "--table", "-t", help="Table to watch."),
    dsn: str | None = typer.Option(None, "--dsn", envvar="DATABASE_URL", help=DSN_HELP),
    mode: str = typer.Option(
        "poll", "--mode", help="Change source: 'poll' (default, zero setup) or 'wal'."
    ),
    where: str | None = typer.Option(
        None, "--where", help="Optional SQL filter, e.g. \"status='paid'\"."
    ),
    interval: float = typer.Option(
        2.0, "--interval", "-i", help="Polling interval in seconds (poll mode)."
    ),
) -> None:
    """Follow changes in a table live, like `tail -f` for rows.

    Default mode is 'poll': the table is re-read every --interval seconds and the
    difference from the previous read is streamed (INSERT green, UPDATE yellow,
    DELETE red). Polling needs only a primary key and works on any server.

    Limitation: polling sees the net change per interval, so changes made and
    undone between two polls can be missed. For complete capture use --mode wal.
    """
    if mode not in ("poll", "wal"):
        raise _fail(f"Unknown --mode '{mode}'. Use 'poll' or 'wal'.")
    if interval <= 0:
        raise _fail("--interval must be greater than 0.")

    try:
        if mode == "wal":
            tail_wal(resolve_dsn(dsn), table, where=where)
        else:
            tail_poll(resolve_dsn(dsn), table, interval=interval, where=where)
    except (ConnectionError, SnapshotError, WalError) as exc:
        raise _fail(str(exc)) from exc


@app.command()
def snapshot(
    table: str = typer.Option(..., "--table", "-t", help="Table to snapshot."),
    out: Path = typer.Option(..., "--out", "-o", help="Where to write the snapshot JSON file."),
    dsn: str | None = typer.Option(None, "--dsn", envvar="DATABASE_URL", help=DSN_HELP),
    where: str | None = typer.Option(
        None, "--where", help="Optional SQL filter applied before snapshotting."
    ),
) -> None:
    """Capture the current state of a table to a snapshot file."""
    snap = _capture(dsn, table, where)
    snap.save(out)
    render.confirm_snapshot(snap.table, len(snap.rows), str(out))


@app.command()
def diff(
    snapshots: list[Path] | None = typer.Argument(
        None, help="Two snapshot files to compare: SNAP1 SNAP2."
    ),
    dsn: str | None = typer.Option(None, "--dsn", envvar="DATABASE_URL", help=DSN_HELP),
    table: str | None = typer.Option(
        None, "--table", "-t", help="Table to diff live (instead of two snapshot files)."
    ),
    where: str | None = typer.Option(
        None, "--where", help="Optional SQL filter for live diff."
    ),
    wait: int | None = typer.Option(
        None, "--wait", help="Live diff: seconds to wait between the two snapshots."
    ),
) -> None:
    """Compare two snapshots, or snapshot a table now and again after --wait."""
    snapshots = snapshots or []

    if table is not None or wait is not None:
        # Live mode: snapshot now, wait, snapshot again.
        if snapshots:
            raise _fail("Pass either two snapshot files or --table/--wait, not both.")
        if table is None or wait is None:
            raise _fail("Live diff needs both --table and --wait.")
        before = _capture(dsn, table, where)
        render.console.print(f"[dim]captured {len(before.rows)} rows, waiting {wait}s...[/]")
        time.sleep(wait)
        after = _capture(dsn, table, where)
    else:
        # File mode: compare two snapshot files.
        if len(snapshots) != 2:
            raise _fail("Provide exactly two snapshot files: SNAP_A SNAP_B.")
        for path in snapshots:
            if not path.exists():
                raise _fail(f"Snapshot file not found: {path}")
        before, after = (Snapshot.load(snapshots[0]), Snapshot.load(snapshots[1]))

    try:
        result = diff_mod.compare(before, after)
    except SnapshotError as exc:
        raise _fail(str(exc)) from exc
    render.render_diff(result)


if __name__ == "__main__":
    app()
