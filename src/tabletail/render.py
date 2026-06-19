"""Rich terminal rendering for diff results.

A git-diff feel: green for additions, red for removals, and an old -> new
column-level view for changed rows.
"""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import Change, DiffResult


def _force_utf8() -> None:
    """Best-effort UTF-8 output so non-ASCII never crashes the renderer."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


_force_utf8()
console = Console()

# Pretty glyphs on capable terminals; plain ASCII on legacy Windows consoles.
ARROW = "->" if console.legacy_windows else "→"
CHECK = "[ok]" if console.legacy_windows else "✓"

NULL = Text("NULL", style="dim italic")


def _cell(value: Any) -> Any:
    """Render a value for a table cell, showing NULL distinctly."""
    if value is None:
        return NULL
    return str(value)


def _key_label(pk_columns: list[str], key: tuple[Any, ...]) -> str:
    """Human label for a primary key, e.g. 'id=42' or 'a=1, b=2'."""
    return ", ".join(f"{col}={val}" for col, val in zip(pk_columns, key, strict=False))


def render_diff(result: DiffResult, console: Console = console) -> None:
    """Print a full diff: a summary line, then detail tables per change kind."""
    console.print(_summary(result))

    if result.is_empty:
        return

    if result.added:
        console.print()
        console.print(_rows_table("Added", "green", result.columns, result.added, "after"))
    if result.removed:
        console.print()
        console.print(_rows_table("Removed", "red", result.columns, result.removed, "before"))
    if result.changed:
        console.print()
        console.print(_changed_table(result))


def _summary(result: DiffResult) -> Text:
    text = Text()
    text.append(f"{result.table}: ", style="bold")
    if result.is_empty:
        text.append("no changes", style="dim")
        return text
    text.append(f"+{len(result.added)} added", style="bold green")
    text.append("  ")
    text.append(f"~{len(result.changed)} changed", style="bold yellow")
    text.append("  ")
    text.append(f"-{len(result.removed)} removed", style="bold red")
    return text


def _rows_table(
    title: str,
    style: str,
    columns: list[str],
    changes: list[Change],
    which: str,
) -> Table:
    table = Table(
        title=f"{title} ({len(changes)})",
        title_style=f"bold {style}",
        border_style=style,
    )
    for col in columns:
        table.add_column(col, overflow="fold")
    for change in changes:
        row = getattr(change, which) or {}
        table.add_row(*[_cell(row.get(col)) for col in columns])
    return table


def _changed_table(result: DiffResult) -> Table:
    table = Table(
        title=f"Changed ({len(result.changed)})",
        title_style="bold yellow",
        border_style="yellow",
    )
    table.add_column("row", style="bold cyan", overflow="fold")
    table.add_column("column", style="bold")
    table.add_column(f"old {ARROW} new", overflow="fold")

    for change in result.changed:
        label = _key_label(result.pk_columns, change.key)
        before = change.before or {}
        after = change.after or {}
        for i, col in enumerate(change.columns):
            diff = Text()
            diff.append_text(_old_new(before.get(col)))
            diff.append(f" {ARROW} ", style="dim")
            diff.append_text(_new(after.get(col)))
            # Show the row label only on its first changed column for a cleaner read.
            table.add_row(label if i == 0 else "", col, diff)
        table.add_section()
    return table


def _old_new(value: Any) -> Text:
    if value is None:
        return Text("NULL", style="dim italic red")
    return Text(str(value), style="red strike")


def _new(value: Any) -> Text:
    if value is None:
        return Text("NULL", style="dim italic green")
    return Text(str(value), style="green")


def confirm_snapshot(snap_table: str, count: int, path: str) -> None:
    """Print a one-line confirmation after a snapshot is written."""
    text = Text()
    text.append(f"{CHECK} ", style="bold green")
    text.append(f"snapshot of {snap_table}: ", style="bold")
    text.append(f"{count} rows", style="cyan")
    text.append(" → ")
    text.append(path, style="dim")
    console.print(text)
