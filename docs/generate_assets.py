"""Generate the README screenshots from real tabletail output.

These are genuine renders of the tool's own ``render.py``: the output is produced
by rich, then drawn to PNG with Pillow so the colors match the terminal exactly.

    python docs/generate_assets.py

Produces (no database required):
    docs/tail_poll.png   docs/tail_wal.png   docs/diff.png
    docs/tail_where.png  docs/workflow.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.terminal_theme import MONOKAI

from tabletail import render
from tabletail.diff import compare
from tabletail.models import Change, Snapshot

# Pretty Unicode glyphs on the image surface, whatever the host console is.
render.ARROW = "→"
render.DOT = "·"
render.CHECK = "✓"

DOCS = Path(__file__).resolve().parent
FONT_PATH = r"C:\Windows\Fonts\CascadiaCode.ttf"
FONT_SIZE = 24
PAD = 26
TITLEBAR = 48
MARGIN = 22
WIDTH_COLS = 96

BG = (39, 40, 34)  # Monokai background
BAR = (49, 50, 44)
DEFAULT_FG = (248, 248, 242)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

COLUMNS = ["id", "customer", "status", "amount"]


def _console() -> Console:
    return Console(record=True, force_terminal=True, color_system="truecolor", width=WIDTH_COLS)


def _fonts():
    reg = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    faux = False
    try:
        bold.set_variation_by_name("Bold")
    except Exception:
        faux = True
    return reg, bold, faux


def _color(style) -> tuple[int, int, int]:
    if style and style.color:
        t = style.color.get_truecolor(theme=MONOKAI)
        rgb = (t.red, t.green, t.blue)
    else:
        rgb = DEFAULT_FG
    if style and style.dim:
        rgb = tuple(int(c * 0.55 + b * 0.45) for c, b in zip(rgb, BG, strict=False))
    return rgb


def _lines(console: Console):
    """Turn rich's recorded segments into lines of (text, rgb, bold, strike)."""
    lines: list[list[tuple]] = [[]]
    for seg in console._record_buffer:
        if seg.control:
            continue
        rgb = _color(seg.style)
        bold = bool(seg.style and seg.style.bold)
        strike = bool(seg.style and seg.style.strike)
        parts = seg.text.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((part, rgb, bold, strike))
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def _save(console: Console, name: str, title: str) -> None:
    reg, bold, faux = _fonts()
    cell_w = reg.getlength("M")
    ascent, descent = reg.getmetrics()
    line_h = ascent + descent + 6

    lines = _lines(console)
    ncols = max((sum(len(t) for t, *_ in line) for line in lines), default=1)
    win_w = int(PAD * 2 + ncols * cell_w)
    win_h = int(TITLEBAR + PAD + len(lines) * line_h + PAD // 2)

    img = Image.new("RGBA", (win_w + 2 * MARGIN, win_h + 2 * MARGIN), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x0, y0 = MARGIN, MARGIN
    draw.rounded_rectangle([x0, y0, x0 + win_w, y0 + win_h], radius=14, fill=BG)
    draw.rounded_rectangle(
        [x0, y0, x0 + win_w, y0 + TITLEBAR], radius=14, fill=BAR
    )
    draw.rectangle([x0, y0 + TITLEBAR - 14, x0 + win_w, y0 + TITLEBAR], fill=BG)

    for i, color in enumerate(DOTS):
        cx = x0 + 24 + i * 26
        cy = y0 + TITLEBAR // 2
        draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=color)
    tw = reg.getlength(title)
    draw.text(
        (x0 + (win_w - tw) / 2, y0 + (TITLEBAR - FONT_SIZE) / 2 - 2),
        title,
        font=reg,
        fill=(150, 150, 145),
    )

    y = y0 + TITLEBAR + PAD // 2
    for line in lines:
        x = x0 + PAD
        for text, rgb, is_bold, strike in line:
            font = bold if is_bold else reg
            draw.text((x, y), text, font=font, fill=rgb)
            if is_bold and faux:
                draw.text((x + 1, y), text, font=font, fill=rgb)
            seg_w = len(text) * cell_w
            if strike:
                my = y + ascent * 0.6
                draw.line([x, my, x + seg_w, my], fill=rgb, width=2)
            x += seg_w
        y += line_h

    img.save(DOCS / name)
    print(f"wrote docs/{name}")


def _prompt(console: Console, command: str) -> None:
    console.print(f"[bold #a6e22e]$[/] {command}", highlight=False)


# --------------------------------------------------------------------------- #
# Scenes                                                                       #
# --------------------------------------------------------------------------- #

PK = ["id"]


def _stream_changes():
    return [
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


def _before_after():
    before = Snapshot(
        "orders", PK, COLUMNS,
        [
            {"id": 1, "customer": "Ana Pop", "status": "paid", "amount": "120.00"},
            {"id": 2, "customer": "Mihai Ionescu", "status": "pending", "amount": "45.50"},
            {"id": 3, "customer": "Elena Radu", "status": "paid", "amount": "310.75"},
            {"id": 5, "customer": "Ioana Dumitru", "status": "pending", "amount": "150.00"},
        ],
        "2026-06-19T12:00:00+00:00",
    )
    after = Snapshot(
        "orders", PK, COLUMNS,
        [
            {"id": 1, "customer": "Ana Pop", "status": "paid", "amount": "120.00"},
            {"id": 2, "customer": "Mihai Ionescu", "status": "paid", "amount": "45.50"},
            {"id": 3, "customer": "Elena Radu", "status": "shipped", "amount": "500.00"},
            {"id": 6, "customer": "Vlad Nour", "status": "pending", "amount": "75.25"},
        ],
        "2026-06-19T12:05:00+00:00",
    )
    return before, after


def tail_poll_png() -> None:
    con = _console()
    render.console = con
    _prompt(con, "tabletail tail --table orders --interval 1")
    render.tail_header("orders", 5, 1, None)
    render.render_stream(_stream_changes(), COLUMNS, PK, console=con)
    _save(con, "tail_poll.png", "tabletail · tail (polling)")


def tail_wal_png() -> None:
    con = _console()
    render.console = con
    _prompt(con, "tabletail tail --table orders --mode wal")
    render.tail_header_wal("orders", 5, "test_decoding")
    render.render_stream(_stream_changes(), COLUMNS, PK, console=con)
    _save(con, "tail_wal.png", "tabletail · tail --mode wal")


def tail_where_png() -> None:
    con = _console()
    render.console = con
    _prompt(con, "tabletail tail --table orders --where \"status='paid'\"")
    render.tail_header("orders", 2, 1, "status='paid'")
    changes = [
        Change(
            key=(2,),
            kind="changed",
            before={"id": 2, "customer": "Mihai Ionescu", "status": "pending", "amount": "45.50"},
            after={"id": 2, "customer": "Mihai Ionescu", "status": "paid", "amount": "45.50"},
            columns=["status"],
        ),
        Change(
            key=(8,),
            kind="added",
            after={"id": 8, "customer": "Sorin Pop", "status": "paid", "amount": "60.00"},
        ),
    ]
    render.render_stream(changes, COLUMNS, PK, console=con)
    _save(con, "tail_where.png", "tabletail · tail --where")


def diff_png() -> None:
    con = _console()
    render.console = con
    _prompt(con, "tabletail diff before.json after.json")
    before, after = _before_after()
    render.render_diff(compare(before, after), console=con)
    _save(con, "diff.png", "tabletail · diff")


def workflow_png() -> None:
    con = _console()
    render.console = con
    _prompt(con, "tabletail snapshot --table orders --out before.json")
    render.confirm_snapshot("orders", 4, "before.json")
    con.print()
    _prompt(con, "tabletail snapshot --table orders --out after.json")
    render.confirm_snapshot("orders", 4, "after.json")
    con.print()
    _prompt(con, "tabletail diff before.json after.json")
    before, after = _before_after()
    render.render_diff(compare(before, after), console=con)
    _save(con, "workflow.png", "tabletail · snapshot + diff workflow")


if __name__ == "__main__":
    tail_poll_png()
    tail_wal_png()
    tail_where_png()
    diff_png()
    workflow_png()
