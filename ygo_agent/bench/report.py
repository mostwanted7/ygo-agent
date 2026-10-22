"""A run folder's summary.json, report.md and chart.svg, rebuilt from results.jsonl (plus spec.json and env.json)
whenever a benchmark ends, or with `ygo-agent bench report <folder>`."""

from __future__ import annotations

import json
import os
import shutil
import time

from .. import paths
from ..match import duration
from . import chart, metrics
from .runner import finished, game_cost, read_results, write_json
from .spec import BASELINES, opponent_label


def _load(folder, name):
    try:
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def is_baseline(name: str, env: dict) -> bool:
    kind = (env.get("backends", {}).get(name) or {}).get("type")
    return kind in BASELINES if kind else name in BASELINES


def summarize(folder: str) -> dict:
    records = read_results(folder)
    done = sorted(finished(records).values(), key=lambda r: (r["deck"], r["backend"], r["opponent"], r["game"]))
    spec_file, env = _load(folder, "spec.json"), _load(folder, "env.json")
    spec = spec_file.get("spec", {})
    planned = set(spec_file.get("planned", [])) or {r["key"] for r in records}
    keys_done = {r["key"] for r in done}
    order = spec.get("backends") or []
    names = sorted({r["backend"] for r in done}, key=lambda b: (order.index(b) if b in order else len(order), b))
    ratings = metrics.bradley_terry([(r["backend"], r["opponent"], 1.0 if r["result"] == "win" else
                                      0.5 if r["result"] == "draw" else 0.0) for r in done])
    backends = []
    for name in names:
        games = [r for r in done if r["backend"] == name]
        info = env.get("backends", {}).get(name, {})
        probe = info.get("probe") or {}
        row = {"backend": name, "label": info.get("label", name), "type": info.get("type"),
               "model": info.get("model"), "effort": info.get("effort"), "model_ids": probe.get("model_ids") or [],
               "baseline": is_baseline(name, env), "rating": ratings.get(name), **metrics.aggregate(games)}
        if row["baseline"] and row["cost_per_game"] is None:
            row["cost_per_game"] = 0.0
        backends.append(row)
    backends.sort(key=lambda b: (-(b["rating"] or 0), -(b["win_rate"] or 0)))
    matchups = [{"deck": d, "backend": b, "opponent": o, "baseline": is_baseline(b, env), **metrics.aggregate(g)}
                for (d, b, o), g in metrics.group(done, "deck", "backend", "opponent").items()]
    decks = [{"deck": d, "backend": b, **metrics.aggregate(g)}
             for (d, b), g in metrics.group(done, "deck", "backend").items()]
    opponents = []
    for (o,), g in metrics.group(done, "opponent").items():
        bot = env.get("windbot", {}).get(o, {})
        agg = metrics.aggregate(g)
        opponents.append({"opponent": o, "difficulty": bot.get("difficulty"), "rating": ratings.get(o),
                          "games": agg["games"], "seat_wins": agg["wins"], "seat_win_rate": agg["win_rate"]})
    opponents.sort(key=lambda x: -(x["rating"] or 0))
    # The games every backend played (same deck, opponent and game number, so the same seed and first player):
    # the like-for-like comparison when the backends played different numbers of games.
    slots = [{(r["deck"], r["opponent"], r["game"]) for r in done if r["backend"] == name} for name in names]
    shared = set.intersection(*slots) if slots else set()
    common = {"slots": len(shared), "games_numbers": sorted({g for _, _, g in shared}), "backends": []}
    if shared and any(len(x) > len(shared) for x in slots):
        for b in backends:
            games = [r for r in done if r["backend"] == b["backend"] and (r["deck"], r["opponent"], r["game"]) in shared]
            agg = metrics.aggregate(games)
            common["backends"].append({"backend": b["backend"], "games": agg["games"], "wins": agg["wins"],
                                       "win_rate": agg["win_rate"], "ci95": agg["ci95"]})
    started = [r.get("started") for r in done if r.get("started")]
    ended = [r.get("ended") for r in done if r.get("ended")]
    known = [r for r in done if any(((s or {}).get("stats") or {}).get("cost_usd") is not None
                                    for s in (r.get("player"), r.get("opponent_seat")))]
    return {
        "name": spec.get("name") or os.path.basename(folder), "folder": os.path.basename(folder),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "period": {"first": min(started) if started else None, "last": max(ended) if ended else None},
        "games": {"planned": len(planned), "done": len(done),
                  "aborted": sum(1 for r in records if r.get("status") == "aborted"),
                  "errors": sum(1 for r in records if r.get("status") == "error"),
                  "left": len(planned - keys_done)},
        "game_seconds": sum(r["seconds"] for r in done),
        "cost_usd": sum(game_cost(r) for r in known) if known else None,  # both seats, when both are AIs
        "spec": spec, "backends": backends, "common": common, "matchups": matchups, "decks": decks,
        "opponents": opponents,
        "skipped": [{"key": r["key"], "status": r["status"], "error": r.get("error")}
                    for r in records if r.get("status") != "done" and r["key"] not in keys_done],
    }


# --- formatting -------------------------------------------------------------------------------------------------

def pct(x, digits=0):
    return "–" if x is None else f"{x * 100:.{digits}f}%"


def rate_ci(row):
    if not row["games"]:
        return "–"
    lo, hi = row["ci95"]
    return f"**{pct(row['win_rate'])}** ({pct(lo)}–{pct(hi)})"


def num(x, digits=1):
    return "–" if x is None else f"{x:.{digits}f}"


def secs(x):
    return "–" if x is None else (f"{x:.2f}s" if x < 10 else f"{x:.1f}s")


def tokens(x):
    if x is None:
        return "–"
    return f"{x / 1e6:.2f}M" if x >= 1e6 else f"{x / 1e3:.1f}k" if x >= 1e3 else f"{x:.0f}"


def money(x, baseline=False):
    if x is None:
        return "–"
    if x == 0:
        return "free" if baseline else "$0"
    return f"${x:.2f}" if x >= 0.1 else f"${x:.3f}"


def wld(row):
    return f"{row['wins']}-{row['losses']}-{row['draws']}"


def split(row, side):
    s = row[side]
    return f"{s['wins']}/{s['games']}" if s["games"] else "–"


def model_of(row):
    ids = row.get("model_ids") or []
    if ids:
        return ", ".join(f"`{m}`" for m in ids)
    if row.get("baseline"):
        return "no model"
    return f"`{row['model']}`" if row.get("model") else "–"


def leaderboard_md(summary: dict, link_report: str | None = None) -> str:
    """The two leaderboard tables (strength, then cost and reliability): the README copies these."""
    rows = summary["backends"]
    out = ["| # | Backend | Model | Games | W-L-D | Win rate (95% CI) | Rating | Going first / second | Avg turns |",
           "|---:|---|---|---:|---:|---|---:|---:|---:|"]
    for i, b in enumerate(rows, 1):
        name = b["backend"] + (" *(baseline)*" if b["baseline"] else "")
        out.append(f"| {i} | {name} | {model_of(b)} | {b['games']} | {wld(b)} | {rate_ci(b)} | "
                   f"{num(b['rating'], 0)} | {split(b, 'first')} · {split(b, 'second')} | {num(b['turns_mean'])} |")
    out += ["", "| Backend | Time per game | Decision latency mean · p50 · p95 | Tokens per game: in · out · cache read |"
                " Cost per game | Invalid replies | Fallbacks | Rule-answered | Errors (timeouts) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for b in rows:
        tpg = b.get("tokens_per_game") or {}
        tok = "–" if b["baseline"] else f"{tokens(tpg.get('input'))} · {tokens(tpg.get('output'))} · " \
                                        f"{tokens(tpg.get('cache_read'))}"
        lat = "–" if b["baseline"] else f"{secs(b['latency_mean_s'])} · {secs(b['latency_p50_s'])} · " \
                                        f"{secs(b['latency_p95_s'])}"
        invalid = "–" if b["baseline"] else f"{pct(b['invalid_rate'], 1)} ({b['invalid_replies']}/{b['replies']})"
        out.append(f"| {b['backend']} | {duration(b['seconds_mean'])} | {lat} | {tok} | "
                   f"{money(b['cost_per_game'], b['baseline'])} | {invalid} | {pct(b['fallback_rate'], 1)} | "
                   f"{pct(b['rule_share'], 1)} | {b['errors']} ({b['timeouts']}) |")
    if link_report:
        out += ["", f"Full report: [{link_report}]({link_report})"]
    return "\n".join(out)


def common_md(summary: dict) -> str | None:
    common = summary.get("common") or {}
    if not common.get("backends"):
        return None
    numbers = ", ".join(str(g) for g in common["games_numbers"])
    out = [f"The {common['slots']} games every backend played (game {numbers} of each deck × opponent pairing: "
           "the same seeds and the same player going first for everyone):", "",
           "| Backend | Games | Wins | Win rate (95% CI) |", "|---|---:|---:|---|"]
    for b in common["backends"]:
        out.append(f"| {b['backend']} | {b['games']} | {b['wins']} | {rate_ci(b)} |")
    return "\n".join(out)


def matchups_md(summary: dict) -> str:
    out = ["| Deck | Backend | Opponent | Games | W-L-D | Win rate (95% CI) | Avg turns | Time per game | "
           "Latency p50 · p95 | Cost per game | Invalid | Fallbacks |",
           "|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    order = {b["backend"]: i for i, b in enumerate(summary["backends"])}
    for m in sorted(summary["matchups"], key=lambda m: (m["deck"], m["opponent"], order.get(m["backend"], 99))):
        lat = "–" if m["baseline"] else f"{secs(m['latency_p50_s'])} · {secs(m['latency_p95_s'])}"
        out.append(f"| {m['deck']} | {m['backend']} | {opponent_label(m['opponent'])} | {m['games']} | {wld(m)} | "
                   f"{rate_ci(m)} | {num(m['turns_mean'])} | {duration(m['seconds_mean'])} | {lat} | "
                   f"{money(m['cost_per_game'], m['baseline']) if not m['baseline'] else 'free'} | "
                   f"{'–' if m['baseline'] else pct(m['invalid_rate'], 1)} | {pct(m['fallback_rate'], 1)} |")
    return "\n".join(out)


def pivot_md(summary: dict) -> str:
    """Wins / games per backend (rows) and deck × opponent (columns)."""
    cols = sorted({(m["deck"], m["opponent"]) for m in summary["matchups"]})
    cell = {(m["backend"], m["deck"], m["opponent"]): m for m in summary["matchups"]}
    head = "| Backend | " + " | ".join(f"{d} vs {opponent_label(o).replace(' (WindBot)', '')}" for d, o in cols) + " |"
    out = [head, "|---|" + "---:|" * len(cols)]
    for b in summary["backends"]:
        cells = []
        for d, o in cols:
            m = cell.get((b["backend"], d, o))
            cells.append(f"{m['wins']}/{m['games']}" if m else "–")
        out.append(f"| {b['backend']} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def games_md(folder: str) -> str:
    done = sorted(finished(read_results(folder)).values(),
                  key=lambda r: (r["deck"], r["opponent"], r["backend"], r["game"]))
    out = ["| Deck | Backend | Opponent | Game | Seed | First | Result | Turns | Time | Replay |",
           "|---|---|---|---:|---:|---|---|---:|---:|---|"]
    for r in done:
        replay = f"[replay]({r['replay']})" if r.get("replay") else "–"
        out.append(f"| {r['deck']} | {r['backend']} | {opponent_label(r['opponent'])} | {r['game']} | {r['seed']} | "
                   f"{'AI seat' if r['first'] == 'player' else 'opponent'} | {r['result']} | {r['turns']} | "
                   f"{duration(r['seconds'])} | {replay} |")
    return "\n".join(out)


def notes_md(summary: dict, env: dict) -> str:
    spec = summary["spec"]
    lines = []
    g = summary["games"]
    lines.append(f"- **Plan:** decks {', '.join(spec.get('decks', []))}; backends {', '.join(spec.get('backends', []))}; "
                 f"opponents {', '.join(opponent_label(o) for o in spec.get('opponents', []))}. "
                 f"{spec.get('games')} games per (deck, backend, opponent)"
                 + (", except " + ", ".join(f"{k} {v}" for k, v in spec.get("games_for", {}).items())
                    if spec.get("games_for") else "") + ".")
    lines.append(f"- **Seeds:** game *i* of every pairing uses seed {spec.get('seed')} + *i*, and the AI seat goes "
                 "first in odd-numbered games and second in even ones, so every backend gets the same deals in the "
                 "same order.")
    status = f"{g['done']} of {g['planned']} planned games finished"
    if g["left"]:
        status += f"; {g['left']} not played"
    if g["aborted"]:
        status += f"; {g['aborted']} attempts not counted because the backend ran out of usage mid-game"
    if g["errors"]:
        status += f"; {g['errors']} attempts failed to run"
    lines.append(f"- **Status:** {status}.")
    rules = env.get("rules", {})
    if rules:
        lines.append(f"- **Rules:** {rules.get('text', rules.get('name'))} (duel flags {rules.get('flags')}), "
                     "Bo1, 8000 LP.")
    core = env.get("core", {})
    if core:
        lines.append(f"- **Engine:** ygopro-core {core.get('version')} (`{core.get('path')}`), card scripts as of "
                     f"{env.get('scripts', {}).get('newest')}, {env.get('cards', {}).get('count')} cards from "
                     f"{env.get('cards', {}).get('databases')} databases (newest {env.get('cards', {}).get('newest')}).")
    for key, d in env.get("decks", {}).items():
        lines.append(f"- **Deck {d['name']}:** {d['main']} main / {d['extra']} extra (`{d['ydk']}`, sha {d['ydk_sha']}); "
                     f"playbook {d['playbook_chars']} chars (sha {d['playbook_sha']}), hard rules: {d['rules']}.")
    for o, b in env.get("windbot", {}).items():
        if b.get("ai"):
            lines.append(f"- **Opponent {o}:** an AI seat ({b['deck']['name']} on {b.get('backend')}).")
        else:
            lines.append(f"- **Opponent {opponent_label(o)}:** WindBot deck AI `{b['deck']}`, difficulty "
                         f"{b['difficulty']} ({'the repo fork' if b.get('fork') else 'EDOPro bundle'}, deck sha "
                         f"{b.get('ydk_sha')}).")
    for name, b in env.get("backends", {}).items():
        probe = b.get("probe") or {}
        bits = [f"type {b.get('type')}"] + [f"{k} {b[k]}" for k in ("model", "effort", "base_url", "card_texts")
                                             if b.get(k)]
        if probe.get("model_ids"):
            bits.append("model id " + ", ".join(probe["model_ids"]))
        lines.append(f"- **Backend {name}:** " + ", ".join(bits) + ".")
    if env.get("claude_cli") and any(b.get("type") == "claude-code" for b in env.get("backends", {}).values()):
        lines.append(f"- **Claude Code CLI:** {env['claude_cli']}. Its cost figure is what the tokens would cost at API "
                     "prices; a subscription login isn't billed per call.")
    lines.append(f"- **Software:** ygo-agent {env.get('ygo_agent')}, Python {env.get('python')}.")
    lines.append("- **Metrics:** win rate = wins / games (draws count as not won), with a Wilson 95% interval. "
                 "Rating: Bradley-Terry on the Elo scale over every game (backends and opponents as players), each "
                 "with one virtual win and loss against a 1500-rated anchor, so it accounts for opponent strength "
                 "and stays finite at 0 or 100%. Latency: backend seconds per decision it was asked (re-asks "
                 "included). Invalid replies: model outputs that couldn't be read or named an illegal option "
                 "(the agent re-asks once). Fallbacks: decisions the heuristic answered because the backend didn't "
                 "(timeout, error, two invalid replies). Rule-answered: decisions the deck's hard rules made. "
                 "Turns count both players' turns.")
    for s in summary.get("skipped", [])[:10]:
        lines.append(f"- Not counted: `{s['key']}` ({s['status']}: {s['error']}).")
    return "\n".join(lines)


def report_md(summary: dict, env: dict, folder: str) -> str:
    g = summary["games"]
    period = summary["period"]
    when = period["first"][:10] if period["first"] else "–"
    if period["last"] and period["first"] and period["last"][:10] != period["first"][:10]:
        when += f" to {period['last'][:10]}"
    cost = summary["cost_usd"]
    head = [f"# Benchmark: {summary['name']}", "",
            f"{when} · {g['done']} games ({g['planned']} planned) · {env.get('rules', {}).get('text', 'Master Rule 3')} · "
            f"{duration(summary['game_seconds'])} of play"
            + (f" · {money(cost)} at API prices" if cost else ""), "",
            *([f"> {' '.join(summary['spec']['note'].split())}", ""] if summary["spec"].get("note") else []),
            "![Win rate with 95% CI, and cost per game against win rate](chart.svg)", "",
            "## Leaderboard", "", leaderboard_md(summary), "",
            *(["### Like for like", "", common_md(summary), ""] if common_md(summary) else []),
            "## Wins by matchup", "", pivot_md(summary), "",
            "## Matchups", "", matchups_md(summary), "",
            "## Opponents", "",
            "| Opponent | WindBot difficulty | Games | AI seat's wins | Rating |", "|---|---:|---:|---:|---:|"]
    for o in summary["opponents"]:
        head.append(f"| {opponent_label(o['opponent'])} | {o['difficulty'] if o['difficulty'] is not None else '–'} | "
                    f"{o['games']} | {o['seat_wins']} ({pct(o['seat_win_rate'])}) | {num(o['rating'], 0)} |")
    head += ["", "## Notes", "", notes_md(summary, env), "",
             "## Games", "", "<details><summary>Every game, with its EDOPro replay (open it in EDOPro's replay "
                             "menu)</summary>", "", games_md(folder), "", "</details>", ""]
    return "\n".join(head)


def build(folder: str) -> dict:
    """Write summary.json, report.md and chart.svg in a run folder; returns the summary."""
    summary = summarize(folder)
    env = _load(folder, "env.json")
    write_json(os.path.join(folder, "summary.json"), summary)
    rows = [{"name": b["backend"], "baseline": b["baseline"], "games": b["games"], "win_rate": b["win_rate"],
             "ci95": b["ci95"], "cost_per_game": b["cost_per_game"]} for b in summary["backends"]]
    with open(os.path.join(folder, "chart.svg"), "w", encoding="utf-8") as f:
        f.write(chart.render(rows, f"Benchmark {summary['name']}"))
    with open(os.path.join(folder, "report.md"), "w", encoding="utf-8") as f:
        f.write(report_md(summary, env, folder))
    return summary


def publish(folder: str, summary: dict, target: str) -> list[str]:
    """Copy the leaderboard and the chart to `target` (docs/bench for the README), linking the full report."""
    os.makedirs(target, exist_ok=True)
    report_link = os.path.relpath(os.path.join(folder, "report.md"), target)
    g = summary["games"]
    lines = [f"Benchmark `{summary['name']}`, {(summary['period']['first'] or '')[:10]}: {g['done']} games. "
             f"Full report: [{os.path.relpath(os.path.join(folder, 'report.md'), paths.ROOT)}]({report_link}).", ""]
    if summary["spec"].get("note"):
        lines += [f"> {' '.join(summary['spec']['note'].split())}", ""]
    lines += [leaderboard_md(summary), ""]
    common = common_md(summary)
    if common:
        lines += [common, ""]
    md = os.path.join(target, "leaderboard.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    svg = os.path.join(target, "chart.svg")
    shutil.copyfile(os.path.join(folder, "chart.svg"), svg)
    return [md, svg]
