"""
core/chart_generator.py

Generates matplotlib bar charts as PNG bytes from aggregate() tool results.
Used by both the /chart API endpoint (so the frontend can <img> it) and
the PDF exporter (embedded directly as an image) -- one rendering path,
consistent everywhere.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import matplotlib
matplotlib.use("Agg")  # no display server needed, safe for a backend process
import matplotlib.pyplot as plt

import re

def infer_top_n(question: str, default: int = 10) -> int:
    """
    Best-effort extraction of how many items the user actually asked for
    (e.g. "top 5", "5 most expensive"), so the chart shows the same count
    as what the agent's text answer presents -- not an arbitrary default.
    """
    if not question:
        return default
    patterns = [
        r'top\s+(\d+)',
        r'first\s+(\d+)',
        r'\b(\d+)\s+(?:most|highest|largest|biggest|top|expensive|cheapest|smallest|lowest)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            n = int(match.group(1))
            if 1 <= n <= 30:
                return n
    return default

# Matches the frontend's indigo/purple palette
COLORS = ["#4f46e5", "#7c3aed", "#0891b2", "#16a34a", "#ea580c",
          "#dc2626", "#0d9488", "#ca8a04", "#db2777", "#0284c7"]


def render_bar_chart_png(
    title: str,
    groups: dict[str, dict[str, Any]],
    max_bars: int = 12,
    figsize: tuple[float, float] = (7.5, 4.2),
) -> bytes:
    """
    groups: the {label: {"value": ..., ...}} shape returned by
    core.tools.aggregate() when group_by is used.
    Returns PNG image bytes.
    """
    items = [
        (label, info.get("value"))
        for label, info in groups.items()
        if info.get("value") is not None
    ]
    items.sort(key=lambda x: x[1], reverse=True)
    items = items[:max_bars]

    labels = [str(l) for l, _ in items]
    values = [v for _, v in items]
    colors = [COLORS[i % len(COLORS)] for i in range(len(items))]

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 10

    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    bars = ax.bar(labels, values, color=colors, width=0.62, zorder=3)

    ax.set_title(title, fontsize=12.5, fontweight="bold", color="#14161f", pad=14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e6e8f0")
    ax.spines["bottom"].set_color("#e6e8f0")
    ax.tick_params(axis="x", rotation=32, labelsize=8.5, colors="#6b7080")
    ax.tick_params(axis="y", labelsize=8.5, colors="#6b7080")
    ax.yaxis.grid(True, color="#eceefc", zorder=0)
    ax.set_axisbelow(True)
    plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")

    # Value labels on top of each bar
    for bar, val in zip(bars, values):
        ax.annotate(
            f"{val:,.0f}" if val == int(val) else f"{val:,.1f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center", fontsize=7.5, color="#14161f", fontweight="medium",
        )

    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def find_chartable_steps(tool_calls: list[dict[str, Any]], max_charts: int = 4) -> list[dict[str, Any]]:
    """Pick which aggregate(group_by=...) tool calls in a trace are worth
    charting -- more than one group, no error, reasonable size."""
    chartable = [
        s for s in tool_calls
        if s.get("tool_name") == "aggregate"
        and s.get("result", {}).get("groups")
        and len(s["result"]["groups"]) > 1
        and not s["result"].get("error")
    ]
    return chartable[-max_charts:]

def render_daily_stats_chart(days_data: list[dict]) -> bytes:
    """Stacked bar chart of daily run counts per track, in the same visual
    style as the other charts in the app."""
    dates = [d["date"][5:] for d in days_data]  # MM-DD
    a_counts = [d["A"] for d in days_data]
    b_counts = [d["B"] for d in days_data]
    c_counts = [d["C"] for d in days_data]

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 10

    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=150)

    ax.bar(dates, a_counts, label="Track A (Query)", color="#4f46e5", zorder=3)
    ax.bar(dates, b_counts, bottom=a_counts, label="Track B (Audit)", color="#dc2626", zorder=3)
    bottom_c = [a + b for a, b in zip(a_counts, b_counts)]
    ax.bar(dates, c_counts, bottom=bottom_c, label="Track C (Review Board)", color="#7c3aed", zorder=3)

    ax.set_title("Daily Agent Runs by Track", fontsize=12.5, fontweight="bold", color="#14161f", pad=14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e6e8f0")
    ax.spines["bottom"].set_color("#e6e8f0")
    ax.tick_params(axis="x", rotation=45, labelsize=8, colors="#6b7080")
    ax.tick_params(axis="y", labelsize=8.5, colors="#6b7080")
    ax.yaxis.grid(True, color="#eceefc", zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")

    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()