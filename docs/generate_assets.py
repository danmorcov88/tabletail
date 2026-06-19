"""Generate the README images from real tabletail output.

These are genuine renders of the tool's own ``render.py`` — not mock-ups and not
screenshots. Run after any change to the output styling:

    python docs/generate_assets.py

Produces (no database required):
    docs/tail.svg   — the live tail stream (INSERT / UPDATE / DELETE)
    docs/diff.svg   — a diff between two snapshots
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.terminal_theme import MONOKAI

from tabletail import render
from tabletail.diff import compare
from tabletail.models import Change, Snapshot

# Force pretty Unicode glyphs on the image surface, whatever the host console is.
render.ARROW = "→"
render.DOT = "·"
render.CHECK = "✓"

DOCS = Path(__file__).resolve().parent
COLUMNS = ["id", "customer", "status", "amount"]


def _console() -> Console:
    return Console(record=True, force_terminal=True, color_system="truecolor", width=86)


def _save(console: Console, name: str, title: str) -> None:
    console.save_svg(str(DOCS / name), title=title, theme=MONOKAI)
    print(f"wrote docs/{name}")


def tail_image() -> None:
    pk = ["id"]
    changes = [
        Change(
            key=(6,),
            kind="added",
            after={"id": 6, "customer": "Vlad Nour", "status": "pending", "amount": "75.25"},
        ),
        Change(
            key=(2,),
            kind="changed",
            before={"id": 2, "customer": "Mihai Ionescu", "status": "pending", "amount": "45.50"},
            after={"id": 2, "customer": "Mihai Ionescu", "status": "paid", "amount": "45.50"},
            columns=["status"],
        ),
        Change(
            key=(3,),
            kind="changed",
            before={"id": 3, "customer": "Elena Radu", "status": "paid", "amount": "310.75"},
            after={"id": 3, "customer": "Elena Radu", "status": "shipped", "amount": "500.00"},
            columns=["status", "amount"],
        ),
        Change(
            key=(5,),
            kind="removed",
            before={"id": 5, "customer": "Ioana Dumitru", "status": "pending", "amount": "150.00"},
        ),
    ]
    console = _console()
    render.console = console  # so the header uses the recording console too
    render.tail_header("orders", 5, 1, None)
    render.render_stream(changes, COLUMNS, pk, console=console)
    _save(console, "tail.svg", "tabletail tail --table orders")


def diff_image() -> None:
    before = Snapshot(
        "orders",
        ["id"],
        COLUMNS,
        [
            {"id": 1, "customer": "Ana Pop", "status": "paid", "amount": "120.00"},
            {"id": 2, "customer": "Mihai Ionescu", "status": "pending", "amount": "45.50"},
            {"id": 3, "customer": "Elena Radu", "status": "paid", "amount": "310.75"},
            {"id": 5, "customer": "Ioana Dumitru", "status": "pending", "amount": "150.00"},
        ],
        "2026-06-19T12:00:00+00:00",
    )
    after = Snapshot(
        "orders",
        ["id"],
        COLUMNS,
        [
            {"id": 1, "customer": "Ana Pop", "status": "paid", "amount": "120.00"},
            {"id": 2, "customer": "Mihai Ionescu", "status": "paid", "amount": "45.50"},
            {"id": 3, "customer": "Elena Radu", "status": "shipped", "amount": "500.00"},
            {"id": 6, "customer": "Vlad Nour", "status": "pending", "amount": "75.25"},
        ],
        "2026-06-19T12:05:00+00:00",
    )
    console = _console()
    render.console = console
    render.render_diff(compare(before, after), console=console)
    _save(console, "diff.svg", "tabletail diff before.json after.json")


if __name__ == "__main__":
    tail_image()
    diff_image()
