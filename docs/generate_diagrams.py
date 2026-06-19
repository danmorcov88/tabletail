"""Render the 'How it works' architecture diagrams to PNG.

Custom-drawn with matplotlib so they share the terminal screenshots' dark Monokai
look. Run:

    python docs/generate_diagrams.py

Produces:
    docs/how_poll.png   docs/how_wal.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

DOCS = Path(__file__).resolve().parent

BG = "#272822"
CARD = "#32332c"
TEXT = "#f8f8f2"
DIM = "#a59f85"
GREEN = "#a6e22e"
ORANGE = "#fd971f"
PINK = "#f92672"
CYAN = "#66d9ef"
PURPLE = "#ae81ff"

MONO = fm.FontProperties(family="monospace")


def _box(ax, cx, cy, w, h, text, edge, *, textcolor=TEXT, bold=False):
    ax.add_patch(
        FancyBboxPatch(
            (cx - w / 2, cy - h / 2),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=2.2,
            edgecolor=edge,
            facecolor=CARD,
            zorder=3,
        )
    )
    ax.text(
        cx,
        cy,
        text,
        ha="center",
        va="center",
        color=textcolor,
        fontsize=12.5,
        fontproperties=MONO,
        fontweight="bold" if bold else "normal",
        zorder=4,
    )


def _cylinder(ax, cx, cy, w, h, text, edge):
    """A database-style cylinder for data stores."""
    rx, ry = w / 2, h * 0.14
    body_top, body_bot = cy + h / 2 - ry, cy - h / 2 + ry
    ax.add_patch(
        plt.Rectangle(
            (cx - rx, body_bot), w, body_top - body_bot, facecolor=CARD, edgecolor="none", zorder=3
        )
    )
    for yc, z in ((body_bot, 3), (body_top, 5)):
        ax.add_patch(
            mpatches.Ellipse(
                (cx, yc), w, ry * 2, facecolor=CARD, edgecolor=edge, linewidth=2.2, zorder=z
            )
        )
    ax.plot(
        [cx - rx, cx - rx], [body_bot, body_top], color=edge, linewidth=2.2, zorder=4
    )
    ax.plot(
        [cx + rx, cx + rx], [body_bot, body_top], color=edge, linewidth=2.2, zorder=4
    )
    ax.text(
        cx, cy - ry * 0.3, text, ha="center", va="center", color=TEXT, fontsize=12.5,
        fontproperties=MONO, zorder=6,
    )


def _arrow(ax, x1, x2, y, label=None, *, color=DIM):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y),
            (x2, y),
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=2,
            color=color,
            shrinkA=2,
            shrinkB=2,
            zorder=2,
        )
    )
    if label:
        ax.text(
            (x1 + x2) / 2,
            y + 0.16,
            label,
            ha="center",
            va="bottom",
            color=DIM,
            fontsize=9.5,
            fontproperties=MONO,
            zorder=2,
        )


def _feedback(ax, x_from, x_to, y, label):
    """A curved return arrow drawn below the main row."""
    drop = y - 0.95
    verts = [(x_from, y - 0.5), (x_from, drop), (x_to, drop), (x_to, y - 0.5)]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
    ax.add_patch(
        PathPatch(MplPath(verts, codes), fill=False, edgecolor=DIM, linewidth=1.6, zorder=1)
    )
    ax.add_patch(
        FancyArrowPatch(
            (x_to + 0.001, drop),
            (x_to, y - 0.5),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.6,
            color=DIM,
            zorder=1,
        )
    )
    ax.text((x_from + x_to) / 2, drop - 0.16, label, ha="center", va="top", color=DIM,
            fontsize=9, fontproperties=MONO, zorder=1)


GAP = 2.4
MARGIN = 0.5
Y = 1.95


def _layout(widths):
    """Return box centers and the (right_edge, left_edge) of each gap between them."""
    centers, x = [], MARGIN
    for w in widths:
        centers.append(x + w / 2)
        x += w + GAP
    edges = [(centers[i] + widths[i] / 2, centers[i + 1] - widths[i + 1] / 2)
             for i in range(len(widths) - 1)]
    total = x - GAP + MARGIN
    return centers, edges, total


def _figure(width):
    fig, ax = plt.subplots(figsize=(width, 3.3), dpi=170)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, width)
    ax.set_ylim(0, 3.3)
    ax.axis("off")
    return fig, ax


def poll_diagram():
    widths = [1.7, 1.9, 2.2, 1.9]
    centers, edges, total = _layout(widths)
    fig, ax = _figure(total)

    _cylinder(ax, centers[0], Y, widths[0], 1.5, "orders\ntable", CYAN)
    _box(ax, centers[1], Y, widths[1], 1.2, "read\nsnapshot", PURPLE)
    _box(ax, centers[2], Y, widths[2], 1.2, "compare by\nprimary key", ORANGE)
    _box(ax, centers[3], Y, widths[3], 1.2, "colored\nlive output", GREEN,
         textcolor=GREEN, bold=True)

    _arrow(ax, *edges[0], Y, "SELECT *\nevery --interval")
    _arrow(ax, *edges[1], Y)
    _arrow(ax, *edges[2], Y, "added · changed\n· removed")
    _feedback(ax, centers[2], centers[1], Y, "kept as the new 'previous'")

    fig.savefig(DOCS / "how_poll.png", facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote docs/how_poll.png")


def wal_diagram():
    widths = [1.7, 1.4, 2.1, 2.5, 1.9]
    centers, edges, total = _layout(widths)
    fig, ax = _figure(total)

    _cylinder(ax, centers[0], Y, widths[0], 1.5, "orders\ntable", CYAN)
    _cylinder(ax, centers[1], Y, widths[1], 1.5, "WAL", PINK)
    _box(ax, centers[2], Y, widths[2], 1.2, "temporary\nlogical slot", PURPLE)
    _box(ax, centers[3], Y, widths[3], 1.3, "decode\nwal2json /\ntest_decoding", ORANGE)
    _box(ax, centers[4], Y, widths[4], 1.2, "colored\nlive output", GREEN,
         textcolor=GREEN, bold=True)

    _arrow(ax, *edges[0], Y, "every\nchange")
    _arrow(ax, *edges[1], Y)
    _arrow(ax, *edges[2], Y, "pg_logical_slot_\nget_changes")
    _arrow(ax, *edges[3], Y)

    fig.savefig(DOCS / "how_wal.png", facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote docs/how_wal.png")


if __name__ == "__main__":
    poll_diagram()
    wal_diagram()
