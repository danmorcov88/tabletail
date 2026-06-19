"""Command-line interface for tabletail.

Three commands mirror the two things the tool does:

* ``tail``     — follow changes in a table live (polling or WAL).
* ``snapshot`` — capture the current state of a table to a file.
* ``diff``     — compare two snapshots, or take two snapshots over time.

In this scaffolding phase the commands only validate and echo their
arguments; the real behaviour arrives in later phases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__

app = typer.Typer(
    name="tabletail",
    help="See what changes in a PostgreSQL table — live (tail) or between two points in time (diff).",
    add_completion=False,
    no_args_is_help=True,
)

DSN_HELP = "PostgreSQL connection string. Falls back to the DATABASE_URL environment variable."


def _mask(dsn: Optional[str]) -> str:
    """Render a DSN for display without leaking the password."""
    if not dsn:
        return "<none>"
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        if "@" in rest:
            creds, host = rest.split("@", 1)
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


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
    dsn: Optional[str] = typer.Option(None, "--dsn", envvar="DATABASE_URL", help=DSN_HELP),
    mode: str = typer.Option(
        "poll", "--mode", help="Change source: 'poll' (default, zero setup) or 'wal'."
    ),
    where: Optional[str] = typer.Option(
        None, "--where", help="Optional SQL filter, e.g. \"status='paid'\"."
    ),
    interval: float = typer.Option(
        2.0, "--interval", "-i", help="Polling interval in seconds (poll mode)."
    ),
) -> None:
    """Follow changes in a table live, like `tail -f` for rows."""
    typer.echo("tail: not implemented yet")
    typer.echo(
        f"  table={table} dsn={_mask(dsn)} mode={mode} "
        f"where={where!r} interval={interval}"
    )


@app.command()
def snapshot(
    table: str = typer.Option(..., "--table", "-t", help="Table to snapshot."),
    out: Path = typer.Option(..., "--out", "-o", help="Where to write the snapshot JSON file."),
    dsn: Optional[str] = typer.Option(None, "--dsn", envvar="DATABASE_URL", help=DSN_HELP),
    where: Optional[str] = typer.Option(
        None, "--where", help="Optional SQL filter applied before snapshotting."
    ),
) -> None:
    """Capture the current state of a table to a snapshot file."""
    typer.echo("snapshot: not implemented yet")
    typer.echo(f"  table={table} out={out} dsn={_mask(dsn)} where={where!r}")


@app.command()
def diff(
    snapshots: Optional[list[Path]] = typer.Argument(
        None, help="Two snapshot files to compare: SNAP1 SNAP2."
    ),
    dsn: Optional[str] = typer.Option(None, "--dsn", envvar="DATABASE_URL", help=DSN_HELP),
    table: Optional[str] = typer.Option(
        None, "--table", "-t", help="Table to diff live (instead of two snapshot files)."
    ),
    wait: Optional[int] = typer.Option(
        None, "--wait", help="Live diff: seconds to wait between the two snapshots."
    ),
) -> None:
    """Compare two snapshots, or snapshot a table now and again after --wait."""
    typer.echo("diff: not implemented yet")
    typer.echo(
        f"  snapshots={[str(p) for p in snapshots or []]} "
        f"dsn={_mask(dsn)} table={table} wait={wait}"
    )


if __name__ == "__main__":
    app()
