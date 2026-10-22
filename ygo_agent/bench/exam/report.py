"""The exam's numbers and report: each model's grades and rates, the paired per-position comparisons, the judge
checks, the whole-game reviews and the recommendation, written as summary.json and report.md."""

from __future__ import annotations

import itertools
import math
import os
import random
import time

from .. import judge as J
from ..metrics import mean, percentile, wilson
from . import files
from .files import FILES, ExamError, latest, load_json, load_jsonl, rel, save_json, tally


# ---- statistics ----

def bootstrap_ci(values: list[float], b: int = 2000, seed: int = 0) -> list[float] | None:
    """A 95% percentile-bootstrap interval for the mean (seeded, so a report rebuilds identically)."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(b))
    return [means[int(0.025 * b)], means[int(0.975 * b) - 1]]


def sign_test(wins: int, losses: int) -> float | None:
    """Two-sided exact binomial p-value for wins vs losses (ties dropped)."""
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _rate(k: int, n: int):
    return k / n if n else None


def _ci(k: int, n: int):
    ci = wilson(k, n)
    return list(ci) if ci else None


# ---- the summary ----

def load_run(folder: str) -> dict:
    data = {name: (load_jsonl if name.endswith(".jsonl") else load_json)(os.path.join(folder, name))
            for name in FILES}
    if not data["exam.json"] or not data["run.json"]:
        raise ExamError(f"{folder} is not an exam run (no exam.json / run.json)")
    return data


def model_of(profile: dict | None) -> str | None:
    return (profile or {}).get("model") or (profile or {}).get("name")


def summarize(data: dict) -> dict:
    exam, run = data["exam.json"], data["run.json"]
    prepared = data["prepared.json"] or {}
    cands = list(run.get("candidates") or {})
    judges = run.get("judges") or []
    primary = judges[0] if judges else None
    positions = {p["id"]: p for p in exam["positions"]}
    answers = latest(data["answers.jsonl"], ("position", "candidate"))
    judged_all = [r for r in data["judge.jsonl"] if r.get("status") == "done"]

    def current(judge):
        """The judge's latest grades for answers that are still the candidates' latest ones."""
        out = {}
        for r in latest([r for r in judged_all if r.get("judge") == judge], ("position",)).values():
            got = {c: answers.get((r["position"], c)) for c in cands}
            if not all(a and a.get("status") == "done" for a in got.values()):
                continue
            mine = {c: {"key": a["key"], "answer": a["answer"], "why": a.get("why")} for c, a in got.items()}
            if J.answers_sha(mine) == r.get("answers_sha"):
                out[r["position"]] = r
        return out

    graded = {j: current(j) for j in judges}
    main = graded.get(primary, {})
    rows = []
    for pid, r in sorted(main.items()):
        p = positions.get(pid)
        if not p:
            continue
        per = J.unblind(r["mapping"], r["result"]["grades"])
        keys = {c: answers[(pid, c)]["key"] for c in cands}
        for c in cands:
            g = per.get(c) or {}
            rows.append({"position": pid, "candidate": c, "deck": p["deck"], "group": p["group"], "sub": p["sub"],
                         "grade": g.get("grade"), "score": J.SCORE.get(g.get("grade")), "label": g.get("label"),
                         "reason": g.get("reason"), "key": keys[c],
                         "shown_from": (r["mapping"].get(g.get("label")) or {}).get("why_from"),
                         "agree": keys[c] == r.get("own_key") or g.get("label") in r["result"]["equivalent"],
                         "unique": sum(1 for x in cands if keys[x] == keys[c]) == 1})
    rows = [x for x in rows if x["score"] is not None]
    models = {}
    for c in cands:
        mine = [x for x in rows if x["candidate"] == c]
        done = [a for (pid, cand), a in answers.items() if cand == c and a.get("status") == "done"]
        models[c] = model_stats(c, mine, done, run)
    pairs = []
    by_pos = {}
    for x in rows:
        by_pos.setdefault(x["position"], {})[x["candidate"]] = x["score"]
    for a, b in itertools.combinations(cands, 2):
        common = [v for v in by_pos.values() if a in v and b in v]
        diffs = [v[a] - v[b] for v in common]
        wins, losses = sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0)
        pairs.append({"a": a, "b": b, "n": len(diffs), "diff": mean(diffs), "ci95": bootstrap_ci(diffs, seed=1),
                      "a_better": wins, "ties": len(diffs) - wins - losses, "b_better": losses,
                      "p_sign": sign_test(wins, losses)})
    excluded = {pid: v.get("reason") for pid, v in prepared.items() if v.get("status") != "ok"}
    asked = [pid for pid, v in prepared.items() if v.get("status") == "ok"]
    summary = {
        "name": exam["name"], "folder": rel(data["_folder"]) if data.get("_folder") else None,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "positions": len(exam["positions"]), "asked": len(asked), "graded": len(by_pos), "excluded": excluded,
        "candidates": cands, "judge": primary, "judges": judges, "run": {k: run.get(k) for k in (
            "created", "candidates", "judge_profiles", "model_ids", "prompts", "prompts_now", "settings")},
        "exam": {k: exam.get(k) for k in ("seed", "n", "decks", "sources", "pool", "created")},
        "models": models, "pairs": pairs,
        "judge_checks": judge_checks(rows, main, run, cands, primary),
        "cross_judges": cross_judges(graded, primary, cands, run),
        "prompt_mismatch": sorted({a["position"] for a in answers.values() if a.get("status") == "done"
                                   and a.get("same_prompt") is False}),
        "incomplete": sorted(pid for pid in asked if any((answers.get((pid, c)) or {}).get("status") != "done"
                                                         for c in cands)),
        "disagreements": disagreements(rows, main, positions, answers, prepared),
        "games": games_summary(data["games.jsonl"], cands),
        "bench": bench_context(run, cands),
        "rows": rows,
        "sources": {p["id"]: f"{short_game(p['game'])} #{p['decision']}" for p in exam["positions"]},
    }
    summary["recommendation"] = recommend(summary)
    return summary


def model_stats(c: str, mine: list[dict], done: list[dict], run: dict) -> dict:
    n = len(mine)
    scores = [x["score"] for x in mine]
    count = lambda *gs: sum(1 for x in mine if x["grade"] in gs)  # noqa: E731
    lat = [a["seconds"] for a in done if a.get("seconds") is not None]
    costs = [a["cost_usd"] for a in done if a.get("cost_usd") is not None]
    toks = {k: sum((a.get("tokens") or {}).get(k, 0) for a in done) for k in ("input", "output", "cache_read",
                                                                             "cache_write")}
    unique = [x for x in mine if x["unique"]]

    def split(key):
        out = {}
        for x in mine:
            out.setdefault(x[key], []).append(x)
        return {k: {"n": len(v), "mean_score": mean(y["score"] for y in v),
                    "mistake_rate": _rate(sum(1 for y in v if y["grade"] in ("mistake", "blunder")), len(v))}
                for k, v in sorted(out.items())}
    return {
        "candidate": c, "model": model_of((run.get("candidates") or {}).get(c)),
        "model_ids": (run.get("model_ids") or {}).get(c), "graded": n,
        "mean_score": mean(scores), "ci95": bootstrap_ci(scores),
        "best": _rate(count("best"), n), "best_or_good": _rate(count("best", "good"), n),
        "mistake_rate": _rate(count("mistake", "blunder"), n), "mistake_ci": _ci(count("mistake", "blunder"), n),
        "blunder_rate": _rate(count("blunder"), n), "blunder_ci": _ci(count("blunder"), n),
        "grades": {g: count(g) for g in J.GRADES},
        "agreement": _rate(sum(1 for x in mine if x["agree"]), n),
        "unique": len(unique), "unique_best": _rate(sum(1 for x in unique if x["grade"] == "best"), len(unique)),
        "answered": len(done), "latency_mean_s": mean(lat), "latency_p95_s": percentile(lat, 0.95),
        "cost_per_decision": sum(costs) / len(costs) if costs else None, "cost_usd": sum(costs) if costs else None,
        "tokens_per_decision": {k: v / len(done) for k, v in toks.items()} if done else None,
        "invalid_replies": sum(a.get("invalid") or 0 for a in done),
        "by_group": split("group"), "by_deck": split("deck"),
    }


def judge_checks(rows: list[dict], main: dict, run: dict, cands: list[str], primary: str | None) -> dict:
    """Self-preference (the judge's model among the candidates being "best" far more often when it stands alone),
    the judge's self-contradictions, and its probe agreement (the same move graded twice)."""
    judge_model = model_of((run.get("judge_profiles") or {}).get(primary))
    same = [c for c in cands if model_of((run.get("candidates") or {}).get(c)) == judge_model]
    rates = {}
    for c in cands:
        unique = [x for x in rows if x["candidate"] == c and x["unique"]]
        rates[c] = {"unique": len(unique), "unique_best": _rate(sum(1 for x in unique if x["grade"] == "best"),
                                                                len(unique))}
    flag = None
    for c in same:
        mine, others = rates[c], [rates[o]["unique_best"] for o in cands if o != c and rates[o]["unique"] >= 4
                                  and rates[o]["unique_best"] is not None]
        if mine["unique"] >= 4 and mine["unique_best"] is not None and others and \
                mine["unique_best"] - max(others) >= 0.3:
            flag = (f"{c} (the judge's own model) is graded best in {mine['unique_best']:.0%} of the positions where "
                    f"its answer differs from every other candidate's, against at most {max(others):.0%} for the "
                    "others. That gap may be real skill or self-preference: re-judge with another model "
                    "(--judge sonnet on --resume) and compare.")
    issues = [(pid, i) for pid, r in main.items() for i in r.get("issues") or []]
    probes = [p for r in main.values() for p in r.get("probes") or [] if p[0] and p[1]]
    return {"judge_model": judge_model, "same_model_candidates": same, "unique": rates, "self_preference": flag,
            "positions_with_issues": len({pid for pid, _ in issues}), "issues": issues[:10],
            "probes": len(probes), "probes_same": sum(1 for a, b in probes if a == b),
            "probes_within_one": sum(1 for a, b in probes if abs(J.SCORE[a] - J.SCORE[b]) <= 1),
            "confidence": tally(r["result"].get("confidence") for r in main.values())}


def cross_judges(graded: dict, primary: str | None, cands: list[str], run: dict) -> list[dict]:
    """Each extra judge's grades of the same answers: agreement with the primary judge, and the models' mean grades
    and paired differences by that judge alone (a judge of another model is the self-preference cross-check)."""
    out = []
    base = graded.get(primary) or {}
    for judge, records in graded.items():
        if judge == primary:
            continue
        same = within = n = 0
        scores = {c: [] for c in cands}
        for pid, r in records.items():
            mine = J.unblind(r["mapping"], r["result"]["grades"])
            theirs = J.unblind(base[pid]["mapping"], base[pid]["result"]["grades"]) if pid in base else {}
            for c in cands:
                g = (mine.get(c) or {}).get("grade")
                if g:
                    scores[c].append(J.SCORE[g])
                h = (theirs.get(c) or {}).get("grade")
                if g and h:
                    n += 1
                    same += g == h
                    within += abs(J.SCORE[g] - J.SCORE[h]) <= 1
        by_pos = {pid: {c: J.SCORE[g["grade"]] for c, g in J.unblind(r["mapping"], r["result"]["grades"]).items()
                        if g.get("grade")} for pid, r in records.items()}
        pairs = []
        for a, b in itertools.combinations(cands, 2):
            diffs = [v[a] - v[b] for v in by_pos.values() if a in v and b in v]
            wins, losses = sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0)
            pairs.append({"a": a, "b": b, "n": len(diffs), "diff": mean(diffs), "ci95": bootstrap_ci(diffs, seed=1),
                          "a_better": wins, "b_better": losses, "p_sign": sign_test(wins, losses)})
        means = {c: mean(v) for c, v in scores.items()}
        ranked = [c for c in sorted(means, key=lambda c: -(means[c] if means[c] is not None else -1))]
        out.append({"judge": judge, "model": model_of((run.get("judge_profiles") or {}).get(judge)),
                    "positions": len(records), "compared": n, "same": _rate(same, n),
                    "within_one": _rate(within, n), "mean_score": means, "ranking": ranked, "pairs": pairs})
    return out


def disagreements(rows: list[dict], main: dict, positions: dict, answers: dict, prepared: dict, k: int = 5):
    """The positions where the candidates' grades are furthest apart (most instructive first)."""
    by = {}
    for x in rows:
        by.setdefault(x["position"], []).append(x)
    conf = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(by, key=lambda pid: (-(max(x["score"] for x in by[pid]) - min(x["score"] for x in by[pid])),
                                         conf.get(main[pid]["result"].get("confidence"), 1), pid))
    out, groups = [], []
    for pid in ranked:
        spread = max(x["score"] for x in by[pid]) - min(x["score"] for x in by[pid])
        if spread == 0 or len(out) >= k:
            break
        p = positions[pid]
        if groups.count(p["group"]) >= 2 and len(ranked) > 2 * k:
            continue  # keep the examples varied
        groups.append(p["group"])
        r = main[pid]
        prep = prepared.get(pid) or {}
        out.append({"position": pid, "deck": p["deck"], "kind": p["kind"], "sub": p["sub"], "turn": p.get("turn"),
                    "source": f"{p['game']} #{p['decision']}", "question": prep.get("question"),
                    "spread": spread, "assessment": r["result"].get("assessment"), "own": r.get("own_answer"),
                    "confidence": r["result"].get("confidence"),
                    "answers": [{"candidate": x["candidate"], "grade": x["grade"], "reason": x["reason"],
                                 "answer": answers[(pid, x["candidate"])]["answer"],
                                 "why": answers[(pid, x["candidate"])].get("why"), "shown_from": x.get("shown_from")}
                                for x in sorted(by[pid], key=lambda y: -y["score"])]})
    return out


def games_summary(records: list[dict], cands: list[str]) -> dict | None:
    done = [r for r in latest(records, ("id",)).values() if r.get("status") == "done" and r.get("review")]
    if not done:
        return None
    out = {}
    order = {"blunder": 0, "major": 1, "minor": 2}
    for c in cands:
        mine = [r for r in done if r["candidate"] == c]
        mistakes = [{**m, "game": r["id"], "deck": r["deck"], "opponent": r["opponent"], "result": r["result"]}
                    for r in mine for m in r["review"].get("mistakes") or []]
        worst = sorted((m for m in mistakes if m.get("severity") in ("blunder", "major")),
                       key=lambda m: (order.get(m.get("severity"), 3), m["game"], m.get("decision") or 0))
        out[c] = {"games": len(mine), "like_for_like": sum(1 for r in mine if r.get("like_for_like")),
                  "mistakes_per_game": _rate(len(mistakes), len(mine)),
                  "significant_per_game": _rate(sum(r.get("significant") or 0 for r in mine), len(mine)),
                  "blunders_per_game": _rate(sum(1 for m in mistakes if m.get("severity") == "blunder"), len(mine)),
                  "wins": sum(1 for r in mine if r.get("result") == "win"),
                  "per_game": [{"game": r["id"], "deck": r["deck"], "opponent": r["opponent"], "index": r["index"],
                                "result": r["result"], "mistakes": len(r["review"].get("mistakes") or []),
                                "significant": r.get("significant"), "log_dir": r["log_dir"]} for r in mine],
                  "worst": worst[:3]}
    return out


def bench_context(run: dict, cands: list[str]) -> dict:
    """Win rate and cost per game of the candidates in the benchmark run the games came from (or the newest one)."""
    folder = (run.get("settings") or {}).get("games_from") or files.default_bench_run()
    summary = load_json(os.path.join(folder, "summary.json")) if folder else None
    if not summary:
        return {}
    out = {"folder": rel(folder)}
    for b in summary.get("backends") or []:
        if b.get("backend") in cands:
            out[b["backend"]] = {k: b.get(k) for k in ("games", "wins", "win_rate", "cost_per_game",
                                                       "latency_mean_s", "decisions_per_game")}
    return out


def recommend(s: dict) -> dict:
    """The model to standardise on: the cheapest one that the exam can't tell apart from the best (a paired difference
    whose 95% interval reaches within a quarter grade of zero), with how sure that is."""
    models = {c: m for c, m in s["models"].items() if m["graded"]}
    if not models:
        return {"choice": None, "confidence": "none", "text": "No graded positions yet."}
    best = max(models, key=lambda c: models[c]["mean_score"])
    pair = {(p["a"], p["b"]): p for p in s["pairs"]}

    def versus(a, b):
        """mean score a - b with its CI."""
        if (a, b) in pair:
            p = pair[(a, b)]
            return p["diff"], p["ci95"], p["n"]
        p = pair.get((b, a))
        if not p:
            return None, None, 0
        return -p["diff"] if p["diff"] is not None else None, [-p["ci95"][1], -p["ci95"][0]] if p["ci95"] else None, \
            p["n"]

    def cost(c):
        v = (s["bench"].get(c) or {}).get("cost_per_game")
        return v if v is not None else (models[c]["cost_per_decision"] or 0) * 60

    lines, choice = [], best
    for c in sorted(models, key=cost):
        if c == best:
            choice = best
            break
        diff, ci, n = versus(c, best)
        close_mistakes = (models[c]["mistake_rate"] or 0) <= (models[best]["mistake_rate"] or 0) + 0.10
        if diff is not None and ci and ci[1] >= -0.25 and ci[0] > -0.75 and close_mistakes:
            choice = c
            lines.append(f"{c} is within reach of {best} (mean grade {diff:+.2f}, 95% CI {ci[0]:+.2f} to "
                         f"{ci[1]:+.2f} over {n} positions) and cheaper.")
            break
        if diff is not None:
            lines.append(f"{c} scores below {best}: {diff:+.2f} grade points"
                         + (f" (95% CI {ci[0]:+.2f} to {ci[1]:+.2f})" if ci else "") + f" over {n} positions.")
    others = [c for c in models if c != choice]
    separated, significant = [], []
    for c in others:
        diff, ci, n = versus(choice, c)
        if ci and (ci[0] > 0 or ci[1] < 0):
            separated.append(c)
        p = pair.get((choice, c)) or pair.get((c, choice)) or {}
        if p.get("p_sign") is not None and p["p_sign"] < 0.05:
            significant.append(c)
    n = models[choice]["graded"]
    checks = s["judge_checks"]
    # A second judge of another model that also puts the same model first answers the self-preference question.
    backed = [x for x in s.get("cross_judges") or [] if x.get("model") != checks.get("judge_model")
              and x.get("ranking") and x["ranking"][0] == best]
    doubt = checks.get("self_preference") and not backed
    if n < 20 or doubt:
        confidence = "low"
    elif len(separated) == len(others) and len(significant) == len(others) and n >= 30:
        confidence = "high"
    else:
        confidence = "medium"
    why = []
    if n < 20:
        why.append(f"only {n} graded positions")
    if doubt:
        why.append("a possible self-preference of the judge")
    elif checks.get("self_preference"):
        x = backed[0]
        why.append(f"the self-preference flag is answered: the second judge ({x['judge']}) also ranks "
                   + " > ".join(f"{c} {x['mean_score'][c]:.2f}" for c in x["ranking"]))
    loose = [c for c in separated if c not in significant]
    if loose:
        why.append(f"the sign test vs {', '.join(loose)} is not below 0.05 (the interval excludes 0)")
    if checks.get("probes") and checks["probes_same"] / checks["probes"] < 0.6:
        why.append(f"the judge gave the same move the same grade only {checks['probes_same']}/{checks['probes']} "
                   "times")
    close = [c for c in others if c not in separated]
    if choice != best:
        why.append(f"statistically tied with {best}, and cheaper")
        close = [c for c in close if c != best]
    if close:
        why.append(f"not separated from {', '.join(close)} at 95%")
    return {"choice": choice, "best": best, "confidence": confidence, "reasons": why, "lines": lines,
            "separated_from": separated}


# ---- report.md ----

def _pct(v) -> str:
    return "–" if v is None else f"{v:.0%}"


def _num(v, fmt="{:.2f}") -> str:
    return "–" if v is None else fmt.format(v)


def _ci_text(ci, fmt="{:.2f}") -> str:
    return "" if not ci else f" ({fmt.format(ci[0])}–{fmt.format(ci[1])})"


def report_md(s: dict) -> str:
    cands = s["candidates"]
    m = s["models"]
    rec = s["recommendation"]
    out = [f"# Decision exam: {s['name']}", ""]
    out.append(f"{s['graded']} positions graded by **{s['judge']}** (blind) out of {s['asked']} asked "
               f"({s['positions']} sampled; {len(s['excluded'])} excluded). Candidates: {', '.join(cands)}. "
               f"Each position is re-asked exactly as `ygo-agent replay` does: a fresh session with the duel history, "
               f"today's playbook and rules. Generated {s['generated']}.")
    out += ["", "## Recommendation", ""]
    if rec.get("choice"):
        bench = s["bench"].get(rec["choice"]) or {}
        out.append(f"**Standardise on {rec['choice']}** (confidence: {rec['confidence']}"
                   + (f"; {', '.join(rec['reasons'])}" if rec.get("reasons") else "") + ").")
        out.append("")
        for line in rec.get("lines") or []:
            out.append(f"- {line}")
        mc = m[rec["choice"]]
        out.append(f"- {rec['choice']}: mean grade {_num(mc['mean_score'])} of 4, mistakes or blunders in "
                   f"{_pct(mc['mistake_rate'])} of decisions, {_num(mc['latency_mean_s'], '{:.1f}')} s and "
                   f"${_num(mc['cost_per_decision'], '{:.3f}')} per exam decision"
                   + (f"; ${bench['cost_per_game']:.2f} per game in the benchmark" if bench.get("cost_per_game")
                      else "") + ".")
        if rec["best"] != rec["choice"]:
            mb = m[rec["best"]]
            out.append(f"- {rec['best']} scored highest ({_num(mb['mean_score'])}), at "
                       f"${_num(mb['cost_per_decision'], '{:.3f}')} per decision.")
    else:
        out.append(rec.get("text") or "No recommendation yet.")
    out += ["", "## Leaderboard", "",
            "Grades: best 4, good 3, acceptable 2, mistake 1, blunder 0. Intervals are 95% (bootstrap for the mean, "
            "Wilson for rates). \"Agrees\" = the judge would have played the same move.", "",
            "| model | graded | mean grade | best | best/good | mistake+blunder | blunder | agrees "
            "| latency (mean / p95) | cost / decision | invalid |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in sorted(cands, key=lambda c: -(m[c]["mean_score"] or -1)):
        x = m[c]
        ids = f" ({', '.join(x['model_ids'])})" if x.get("model_ids") else ""
        out.append(f"| {c}{ids} | {x['graded']} | {_num(x['mean_score'])}{_ci_text(x['ci95'])} | {_pct(x['best'])} | "
                   f"{_pct(x['best_or_good'])} | {_pct(x['mistake_rate'])}{_ci_text(x['mistake_ci'], '{:.0%}')} | "
                   f"{_pct(x['blunder_rate'])} | {_pct(x['agreement'])} | {_num(x['latency_mean_s'], '{:.1f}')} / "
                   f"{_num(x['latency_p95_s'], '{:.1f}')} s | ${_num(x['cost_per_decision'], '{:.3f}')} | "
                   f"{x['invalid_replies']} |")
    out.append("")
    out.append("Latency includes the CLI start-up of a fresh session per position (in games, pre-warming hides it), "
               "and every exam decision is a turn's first message (the whole duel log), so cost per decision is "
               "higher than in a game.")
    if s["pairs"]:
        out += ["", "## Paired comparisons", "", "Every candidate answered the same positions, so the differences are "
                "per position (luck-free).", "",
                "| A vs B | positions | mean grade A − B | A better | tie | B better | sign test p |",
                "|---|---:|---:|---:|---:|---:|---:|"]
        for p in s["pairs"]:
            out.append(f"| {p['a']} vs {p['b']} | {p['n']} | {_num(p['diff'], '{:+.2f}')}"
                       f"{_ci_text(p['ci95'], '{:+.2f}')} | {p['a_better']} | {p['ties']} | {p['b_better']} | "
                       f"{_num(p['p_sign'], '{:.3f}')} |")
    for title, key in (("By decision kind", "by_group"), ("By deck", "by_deck")):
        keys = sorted({k for c in cands for k in m[c][key]})
        if not keys:
            continue
        out += ["", f"## {title}", "", "Mean grade (mistake+blunder rate), n.", "",
                "| | " + " | ".join(cands) + " |", "|---|" + "---:|" * len(cands)]
        for k in keys:
            cells = []
            for c in cands:
                v = m[c][key].get(k)
                cells.append(f"{_num(v['mean_score'])} ({_pct(v['mistake_rate'])}), {v['n']}" if v else "–")
            out.append(f"| {k} | " + " | ".join(cells) + " |")
    jc = s["judge_checks"]
    out += ["", "## Can the judge be trusted?", ""]
    out.append(f"- **Self-preference.** The judge runs on {jc.get('judge_model')}"
               + (f", which is also the candidate {', '.join(jc['same_model_candidates'])}" if
                  jc.get("same_model_candidates") else "") + ". Graded best when its answer was the only one of its "
               "kind: " + ", ".join(f"{c} {_pct(v['unique_best'])} of {v['unique']}" for c, v in jc["unique"].items())
               + ".")
    out.append(f"  - {'⚠️ ' + jc['self_preference'] if jc.get('self_preference') else 'No sign of self-preference.'}")
    out.append(f"- **Self-consistency.** {jc['positions_with_issues']} of {s['graded']} positions have a reply that "
               "contradicts itself (e.g. its own pick not graded best)"
               + ("; e.g. " + "; ".join(f"{pid}: {i}" for pid, i in jc["issues"][:3]) if jc["issues"] else "") + ".")
    if jc["probes"]:
        out.append(f"- **Probes.** The same move shown twice (with two candidates' different reasons) got the same "
                   f"grade {jc['probes_same']}/{jc['probes']} times, within one grade {jc['probes_within_one']}/"
                   f"{jc['probes']}.")
    out.append(f"- **Confidence it reported:** " + ", ".join(f"{k} {v}" for k, v in jc["confidence"].items()) + ".")
    for x in s["cross_judges"]:
        out.append(f"- **Second judge {x['judge']}** ({x['positions']} positions): the same grade as {s['judge']} "
                   f"{_pct(x['same'])}, within one {_pct(x['within_one'])}; mean grades "
                   + ", ".join(f"{c} {_num(x['mean_score'][c])}" for c in x["ranking"]) + "; paired: "
                   + "; ".join(f"{p['a']} − {p['b']} {_num(p['diff'], '{:+.2f}')}{_ci_text(p['ci95'], '{:+.2f}')} "
                               f"({p['a_better']}–{p['b_better']}, p {_num(p['p_sign'], '{:.3f}')})"
                               for p in x.get("pairs") or []) + ".")
    if s["disagreements"]:
        out += ["", "## The most instructive disagreements", ""]
        for d in s["disagreements"]:
            out.append(f"### {d['position']}: {d['deck']} {d['kind']} ({d['sub']}), turn {d.get('turn')}")
            out.append("")
            out.append(f"From `{d['source']}`. {d.get('question') or ''}")
            out.append("")
            out.append(f"> **Judge** ({d.get('confidence')} confidence): {d.get('assessment')}"
                       + (f" It would play {d['own']}." if d.get("own") else ""))
            out.append("")
            for a in d["answers"]:
                out.append(f"- **{a['candidate']}: {a['grade']}** — {a['answer']}")
                out.append(f"  - its reason: \"{(a.get('why') or '').strip()}\"")
                seen = a.get("shown_from")
                out.append(f"  - judge: {a.get('reason')}" if not seen or seen == a["candidate"] else
                           f"  - judge (it graded this move once, shown with {seen}'s reason): {a.get('reason')}")
            out.append("")
    g = s.get("games")
    if g:
        out += ["", "## Whole-game reviews", "", "A blind review of whole logged games (model names removed) that "
                "counts the significant mistakes. Like-for-like games are the same deal (deck, opponent, seed) for "
                "every candidate.", "",
                "| model | games (like-for-like) | wins | mistakes / game | significant / game | blunders / game |",
                "|---|---:|---:|---:|---:|---:|"]
        for c in cands:
            x = g.get(c)
            if x:
                out.append(f"| {c} | {x['games']} ({x['like_for_like']}) | {x['wins']} | "
                           f"{_num(x['mistakes_per_game'], '{:.1f}')} | {_num(x['significant_per_game'], '{:.1f}')} | "
                           f"{_num(x['blunders_per_game'], '{:.1f}')} |")
        for c in cands:
            x = g.get(c)
            if x and x["worst"]:
                out += ["", f"**{c}, worst mistakes:**"]
                for w in x["worst"]:
                    out.append(f"- {w['severity']}, {w['deck']} vs {w['opponent']} ({w['result']}), decision "
                               f"#{w.get('decision')}: {w.get('what')} Better: {w.get('better')}")
    out += ["", "## Positions", "", "| id | deck | kind | from | " + " | ".join(cands) + " |",
            "|---|---|---|---|" + "---|" * len(cands)]
    by = {}
    for x in s["rows"]:
        by.setdefault(x["position"], {})[x["candidate"]] = x["grade"]
    exam_pos = {r["position"]: r for r in s["rows"]}
    for pid in sorted(by):
        r = exam_pos[pid]
        out.append(f"| {pid} | {r['deck']} | {r['group']}/{r['sub']} | " + s["sources"].get(pid, "") + " | "
                   + " | ".join(by[pid].get(c) or "–" for c in cands) + " |")
    if s["excluded"]:
        out += ["", "Excluded: " + "; ".join(f"{pid} ({why})" for pid, why in sorted(s["excluded"].items())) + "."]
    if s["incomplete"]:
        out += ["", f"Not graded yet (an answer is missing or failed; `--resume` retries): "
                    f"{', '.join(s['incomplete'])}."]
    if s["prompt_mismatch"]:
        out += ["", f"⚠️ Some candidates saw a different prompt than the prepared one (a per-profile prompt budget?): "
                    f"{', '.join(s['prompt_mismatch'])}."]
    prompts = s["run"].get("prompts") or {}
    out += ["", "## Notes", "", f"- Prompt versions (sha256 prefixes): " + ", ".join(f"{k} `{v}`" for k, v in
                                                                                   prompts.items()) + "."]
    if s["run"].get("prompts_now"):
        out.append("- ⚠️ The prompts changed while this run was in progress; answers span two versions.")
    pool = s["exam"].get("pool") or {}
    played = ", ".join(f"{k} {v}" for k, v in (pool.get("by_backend") or {}).items())
    out.append(f"- Sampled with seed {s['exam'].get('seed')} from {pool.get('decisions')} usable decisions in "
               f"{pool.get('games')} logged games ({played}).")
    out.append("- A candidate's answer is graded once per distinct move: copies of the same card and the same cards "
               "in another order count as one move, so identical choices always get the same grade.")
    return "\n".join(out) + "\n"


def short_game(game: str) -> str:
    """A game folder's name in a table: a benchmark game's job folder (deck--backend--opponent--n), else its own."""
    parts = os.path.normpath(game).split(os.sep)
    return parts[-2] if "bench" in parts[:-2] else parts[-1]


def build(folder: str) -> dict:
    data = load_run(folder)
    data["_folder"] = folder
    s = summarize(data)
    save_json(os.path.join(folder, "summary.json"), s)
    with open(os.path.join(folder, "report.md"), "w", encoding="utf-8") as f:
        f.write(report_md(s))
    return s


def leaderboard_lines(s: dict) -> list[str]:
    out = []
    for c in sorted(s["candidates"], key=lambda c: -(s["models"][c]["mean_score"] or -1)):
        x = s["models"][c]
        out.append(f"  {c:<10} mean grade {_num(x['mean_score'])}{_ci_text(x['ci95'])}  mistakes "
                   f"{_pct(x['mistake_rate'])}  best {_pct(x['best'])}  ${_num(x['cost_per_decision'], '{:.3f}')}"
                   f"/decision  {x['graded']} graded")
    rec = s["recommendation"]
    if rec.get("choice"):
        out.append(f"  → {rec['choice']} (confidence {rec['confidence']})")
    return out
