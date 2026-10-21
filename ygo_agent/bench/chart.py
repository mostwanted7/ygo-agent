"""The report's chart as a self-contained SVG (no plotting library): win rate with 95% CI per backend, and cost per
game against win rate. Light and dark colours follow prefers-color-scheme; every mark has a <title> tooltip."""

from __future__ import annotations

import math
from html import escape

STYLE = """
  .surface { fill: #fcfcfb; } .ink { fill: #0b0b0b; } .ink2 { fill: #52514e; } .muted { fill: #898781; }
  .grid { stroke: #e1e0d9; } .axis { stroke: #c3c2b7; }
  .llm { fill: #2a78d6; stroke: #fcfcfb; } .llm-ci { stroke: #2a78d6; }
  .base { fill: #898781; stroke: #fcfcfb; } .base-ci { stroke: #898781; }
  @media (prefers-color-scheme: dark) {
    .surface { fill: #1a1a19; } .ink { fill: #f0efec; } .ink2 { fill: #c3c2b7; }
    .grid { stroke: #2c2c2a; } .axis { stroke: #383835; }
    .llm { fill: #3987e5; stroke: #1a1a19; } .llm-ci { stroke: #3987e5; } .base { stroke: #1a1a19; }
  }
  text { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 12px; }
  .title { font-size: 13px; font-weight: 600; } .tick { font-size: 11px; font-variant-numeric: tabular-nums; }
"""


def _pct(x):
    return f"{x * 100:.0f}%"


def _money(x):
    if x is None:
        return "unknown"
    if x == 0:
        return "free"
    return f"${x:.2f}" if x >= 0.1 else f"${x:.3f}"


def render(rows: list[dict], title: str = "") -> str:
    """rows: {"name", "baseline": bool, "games", "win_rate", "ci95": [lo, hi], "cost_per_game": float | None},
    in leaderboard order."""
    rows = [r for r in rows if r.get("games")]
    row_h, top, label_w = 30, 52, 118
    left_w = 400
    plot_l, plot_r = label_w, left_w - 44
    height = max(top + row_h * len(rows) + 46, 250)
    width = left_w + 420
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           f'role="img" aria-label="{escape(title or "Benchmark chart")}">',
           f"<style>{STYLE}</style>", f'<rect class="surface" width="{width}" height="{height}" rx="8"/>']

    def x_of(v):
        return plot_l + v * (plot_r - plot_l)

    # Panel 1: win rate with 95% CI.
    out.append(f'<text class="title ink" x="16" y="24">Win rate, with 95% CI</text>')
    bottom = top + row_h * len(rows) - 8
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        x = x_of(t)
        out.append(f'<line class="grid" x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{bottom}" stroke-width="1"/>')
        out.append(f'<text class="tick muted" x="{x:.1f}" y="{bottom + 16}" text-anchor="middle">{_pct(t)}</text>')
    for i, r in enumerate(rows):
        y = top + row_h * i + 6
        kind = "base" if r.get("baseline") else "llm"
        name = escape(str(r["name"]))
        out.append(f'<text class="ink" x="{label_w - 12}" y="{y + 4}" text-anchor="end">{name}</text>')
        lo, hi = r.get("ci95") or (r["win_rate"], r["win_rate"])
        tip = escape(f"{r['name']}: {_pct(r['win_rate'])} of {r['games']} games (95% CI {_pct(lo)}–{_pct(hi)})")
        out.append(f'<g><title>{tip}</title>'
                   f'<line class="{kind}-ci" x1="{x_of(lo):.1f}" y1="{y}" x2="{x_of(hi):.1f}" y2="{y}" '
                   f'stroke-width="2" stroke-linecap="round"/>'
                   f'<circle class="{kind}" cx="{x_of(r["win_rate"]):.1f}" cy="{y}" r="5" stroke-width="2"/></g>')
        games = f"{r['games']} game{'s' if r['games'] != 1 else ''}"
        out.append(f'<text class="tick ink2" x="{x_of(hi) + 8:.1f}" y="{y + 4}">{_pct(r["win_rate"])} · {games}</text>')
    # Legend (two kinds of seat), under the axis.
    ly = height - 14
    out.append(f'<circle class="llm" cx="22" cy="{ly - 4}" r="5" stroke-width="2"/>'
               f'<text class="ink2" x="32" y="{ly}">LLM backend</text>'
               f'<circle class="base" cx="132" cy="{ly - 4}" r="5" stroke-width="2"/>'
               f'<text class="ink2" x="142" y="{ly}">no-LLM baseline</text>')

    # Panel 2: cost per game vs win rate. Baselines sit in a "free" column; costs on a log scale.
    px0, px1, py0, py1 = left_w + 66, width - 30, top - 10, height - 58
    out.append(f'<text class="title ink" x="{left_w + 16}" y="24">Cost per game (at API prices) vs win rate</text>')
    costs = [r["cost_per_game"] for r in rows if r.get("cost_per_game")]
    lo_c = 10 ** math.floor(math.log10(min(costs))) if costs else 0.01
    hi_c = 10 ** math.ceil(math.log10(max(costs))) if costs else 1.0
    if hi_c <= lo_c:
        hi_c = lo_c * 10
    free_x = px0 + 8
    log_l, log_r = px0 + 56, px1

    def cx(cost):
        if not cost:
            return free_x
        return log_l + (math.log10(cost) - math.log10(lo_c)) / (math.log10(hi_c) - math.log10(lo_c)) * (log_r - log_l)

    def cy(rate):
        return py1 - rate * (py1 - py0)
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        y = cy(t)
        out.append(f'<line class="grid" x1="{px0}" y1="{y:.1f}" x2="{px1}" y2="{y:.1f}" stroke-width="1"/>')
        out.append(f'<text class="tick muted" x="{px0 - 8}" y="{y + 4:.1f}" text-anchor="end">{_pct(t)}</text>')
    out.append(f'<text class="tick muted" x="{free_x}" y="{py1 + 16}" text-anchor="middle">free</text>')
    decade = lo_c
    while decade <= hi_c * 1.0001:
        x = cx(decade)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{py1}" x2="{x:.1f}" y2="{py1 + 4}" stroke-width="1"/>')
        out.append(f'<text class="tick muted" x="{x:.1f}" y="{py1 + 16}" text-anchor="middle">${decade:g}</text>')
        decade *= 10
    out.append(f'<text class="tick muted" x="{(log_l + log_r) / 2:.1f}" y="{py1 + 34}" text-anchor="middle">'
               'cost per game (log scale)</text>')
    placed = []
    for r in rows:
        cost = r.get("cost_per_game")
        if cost is None and not r.get("baseline"):
            continue  # unknown cost: not plotted (the tables say so)
        x, y = cx(cost or 0), cy(r["win_rate"])
        kind = "base" if r.get("baseline") else "llm"
        tip = escape(f"{r['name']}: {_money(cost or 0)} per game, {_pct(r['win_rate'])} wins")
        out.append(f'<g><title>{tip}</title><circle class="{kind}" cx="{x:.1f}" cy="{y:.1f}" r="5" '
                   f'stroke-width="2"/></g>')
        ly = y + 4
        while any(abs(ly - p[1]) < 13 and abs(x - p[0]) < 70 for p in placed):
            ly += 13  # nudge labels of points at the same spot apart
        placed.append((x, ly))
        anchor, lx = ("end", x - 9) if x > px1 - 60 else ("start", x + 9)
        out.append(f'<text class="ink2" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{escape(str(r["name"]))}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
