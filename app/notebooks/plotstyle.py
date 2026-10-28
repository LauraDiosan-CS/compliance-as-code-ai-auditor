"""Shared matplotlib style for the report figures (colorblind-safe, consistent, print-friendly).

Categorical slots follow a fixed order validated for colour-vision deficiency (adjacent pairs);
sequential data uses a single-hue ramp (Blues). Figures are saved as PDF (report) + PNG (slides/web).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "docs" / "report" / "figures"

# fixed categorical order (never cycled): blue, orange, aqua, yellow, magenta, green, violet, red
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MODE_COLOR = {"deterministic": CAT[0], "hybrid": CAT[1], "llm": CAT[2]}
# status colours: ordinal (good -> bad) + neutral greys for non-graded outcomes
STATUS_COLOR = {
    "compliant": "#1baf7a",
    "partial": "#eda100",
    "non_compliant": "#e34948",
    "needs_review": "#8a8984",
    "not_applicable": "#c9c8c2",
}
STATUS_ORDER = ["compliant", "partial", "non_compliant", "needs_review", "not_applicable"]
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"


def setup() -> None:
    mpl.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "font.size": 9.5,
        "axes.titlesize": 10.5,
        "axes.titleweight": "semibold",
        "axes.labelsize": 9.5,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "axes.axisbelow": True,
        "axes.prop_cycle": mpl.cycler(color=CAT),
        "xtick.color": INK2,
        "ytick.color": INK2,
        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "lines.linewidth": 2,
        "patch.edgecolor": "white",
        "patch.linewidth": 1.0,
    })


def save(fig, name: str) -> list[Path]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("pdf", "png"):
        p = FIG_DIR / f"{name}.{ext}"
        fig.savefig(p)
        out.append(p)
    return out


def bar_labels(ax, bars, fmt="{:.0f}", inside=False, color=INK, fontsize=8, show_zero=False) -> None:
    for b in bars:
        h = b.get_height()
        if h != h or (h == 0 and not show_zero):  # NaN or hidden zero
            continue
        y = b.get_y() + (h / 2 if inside else h)
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, y), ha="center",
                    va="center" if inside else "bottom", fontsize=fontsize, color=color,
                    xytext=(0, 0 if inside else 2), textcoords="offset points")


setup()
plt.close("all")
