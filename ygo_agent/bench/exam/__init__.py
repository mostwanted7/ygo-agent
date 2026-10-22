"""`ygo-agent bench exam`: compare models on the same decisions instead of on win rates (docs/bench.md).

Win rates need many games before the luck of the draw averages out. The exam takes a fixed set of real decision
points from logged games instead, re-asks each one of every candidate model exactly the way `ygo-agent replay` does
(a fresh session with the duel history, the current playbook and rules), and has a blind judge grade the answers.

    ygo-agent bench exam --select                  # sample the positions into bench/exams/main.json (no LLM)
    ygo-agent bench exam --dry-run                 # the positions, and what a run would cost
    ygo-agent bench exam                           # candidates answer, the judge grades, report.md
    ygo-agent bench exam --resume                  # continue the newest run (finished answers and grades are kept)
    ygo-agent bench exam report DIR                # rebuild report.md and summary.json

A run folder is bench/exams/results/<time>_<name>/: exam.json (the positions), run.json (settings, model ids, prompt
hashes), prepared.json (what each position shows), answers.jsonl, judge.jsonl, games.jsonl (with --games), and
report.md + summary.json. The candidates' replay logs go to games/exams/<run folder>/.

positions.py samples the pool, runs.py plays a run (answers, grades, whole games), report.py adds up and writes
the report, files.py holds the run's files; this module is the command.
"""

from __future__ import annotations

import glob
import os
import sys
import time

from ... import paths
from ..spec import split_list
from .files import ExamError, latest, load_json, load_jsonl, rel, save_json, tally  # noqa: F401
from .positions import GROUPS, SKIP_KINDS, allocate, answer_key, find_games, make_exam, scan_game, select  # noqa: F401
from .report import bootstrap_ci, build, leaderboard_lines, report_md, sign_test, summarize  # noqa: F401
from .runs import ExamRun  # noqa: F401

EXAMS = os.path.join(paths.ROOT, "bench", "exams")
RESULTS = os.path.join(EXAMS, "results")
DEFAULT_CANDIDATES = ["opus", "sonnet", "haiku"]
DEFAULT_DECKS = ["saffira", "blackwing"]
# Rough (USD, seconds) per position answered, from the pilot benchmark's first-of-turn decisions (a fresh session,
# like the exam's); per position judged and per whole game reviewed, from the smoke run (sonnet) scaled by API price.
EST_ANSWER = {"opus": (0.10, 12.0), "sonnet": (0.04, 8.0), "haiku": (0.006, 7.0)}
EST_JUDGE = {"opus": (0.20, 30.0), "sonnet": (0.10, 15.0), "haiku": (0.03, 10.0)}
EST_GAME = {"opus": (0.60, 120.0), "sonnet": (0.25, 60.0), "haiku": (0.08, 40.0)}


def exam_path(name: str) -> str:
    if name.endswith(".json") or os.sep in name:
        return paths.resolve(name)
    return os.path.join(EXAMS, f"{name}.json")


def newest_run(name: str) -> str | None:
    found = sorted(glob.glob(os.path.join(RESULTS, f"*_{name}")))
    return found[-1] if found else None


def estimate(exam: dict, candidates: list[str], judges: list[str], cfg: dict, games: int) -> dict:
    from ...config import ConfigError, backend

    def model(name):
        try:
            return backend(cfg, name).get("model") or name
        except ConfigError:
            return name
    n = len(exam["positions"])
    cost = secs = 0.0
    for c in candidates:
        c_cost, c_secs = EST_ANSWER.get(model(c), (0.0, 0.1) if c in ("heuristic", "random") else EST_ANSWER["sonnet"])
        cost += n * c_cost
        secs += n * c_secs
    jcost = jsecs = 0.0
    for j in judges:
        j_cost, j_secs = EST_JUDGE.get(model(j), EST_JUDGE["sonnet"])
        jcost += n * j_cost
        jsecs += n * j_secs
    gcost = gsecs = 0.0
    if games and judges:
        g_cost, g_secs = EST_GAME.get(model(judges[0]), EST_GAME["sonnet"])
        gcost, gsecs = games * len(candidates) * g_cost, games * len(candidates) * g_secs
    return {"positions": n, "answers_usd": cost, "answers_s": secs, "judge_usd": jcost, "judge_s": jsecs,
            "games_usd": gcost, "games_s": gsecs, "total_usd": cost + jcost + gcost}


def main(args, cfg, what: list[str]) -> int:
    """`ygo-agent bench exam [NAME | report DIR]` (flags from bench/cli.py)."""
    if what and what[0] == "report":
        if len(what) != 2:
            sys.exit("usage: ygo-agent bench exam report <run folder>")
        s = build(what[1])
        print("\n".join(leaderboard_lines(s)))
        print(f"\nWrote {os.path.join(what[1], 'report.md')} and summary.json.")
        return 0
    if len(what) > 1:
        sys.exit("give at most one exam name (bench/exams/<name>.json)")
    name = os.path.splitext(os.path.basename(what[0]))[0] if what else (args.name or "main")
    path = exam_path(what[0] if what else name)
    decks = split_list(args.decks) if args.decks else DEFAULT_DECKS
    candidates = split_list(args.backends) if args.backends else DEFAULT_CANDIDATES
    judges = split_list(args.judge) if args.judge else ["opus"]
    try:
        from ...cli import load_db
        db = load_db(cfg)
        folder = None
        if args.resume:
            folder = args.resume if isinstance(args.resume, str) else newest_run(name)
            if not folder or not os.path.isfile(os.path.join(folder, "run.json")):
                sys.exit(f"nothing to resume{f' in {folder}' if folder else ''} (no run.json)")
            exam = load_json(os.path.join(folder, "exam.json"))
        elif args.select or args.resample or not os.path.isfile(path):
            if os.path.isfile(path) and not args.resample:
                sys.exit(f"{rel(path)} exists; --resample replaces it (runs keep their own copy)")
            exam = make_exam(name, cfg, db, decks, args.positions or 40, args.seed if args.seed is not None else 1,
                             split_list(args.sources) if args.sources else None)
            save_json(path, exam)
            print(f"Selected {len(exam['positions'])} positions from {exam['pool']['decisions']} usable decisions in "
                  f"{exam['pool']['games']} games → {rel(path)}")
            print("  " + ", ".join(f"{k} {v}" for k, v in tally(f"{p['deck']}/{p['group']}"
                                                                for p in exam["positions"]).items()))
            if args.select:
                return 0
        else:
            exam = load_json(path)
        if args.dry_run:
            for p in exam["positions"]:
                print(f"  {p['id']} {p['deck']:<10} {p['group'] + '/' + p['sub']:<26} turn {p.get('turn')!s:<3} "
                      f"{p['choices']:>2} choices  score {p['score']:<4} {p['game']} #{p['decision']}")
            est = estimate(exam, candidates, judges, cfg, args.games or 0)
            par = args.parallel or 4
            minutes = (est["answers_s"] + est["judge_s"] + est["games_s"]) / par / 60
            print(f"\nEstimate: answers ${est['answers_usd']:.2f}, judge ${est['judge_usd']:.2f}"
                  + (f", game reviews ${est['games_usd']:.2f}" if est["games_usd"] else "")
                  + f" → about ${est['total_usd']:.0f} (API prices) and {minutes:.0f} min at --parallel {par}.")
            return 0
        if folder is None:
            folder = os.path.abspath(args.out) if args.out else os.path.join(
                RESULTS, f"{time.strftime('%Y-%m-%d_%H%M%S')}_{name}")
        runner = ExamRun(exam, folder, cfg, db, candidates, judges, parallel=args.parallel or 4,
                         budget=args.budget_usd, judge_batch=args.judge_batch or 3,
                         agentic=False if args.inline_judge else None,
                         probe=args.probe if args.probe is not None else 0.15, games=args.games or 0,
                         games_from=args.games_from, judge_effort=args.judge_effort,
                         probe_backends=not args.no_probe, argv=["ygo-agent", "bench"] + sys.argv[2:])
        print(f"Exam {name}: {len(exam['positions'])} positions, candidates {', '.join(candidates)}, judge "
              f"{', '.join(judges)} → {rel(folder)}")
        s = runner.run()
    except ExamError as e:
        sys.exit(f"error: {e}")
    print()
    print("\n".join(leaderboard_lines(s)))
    print(f"\nReport: {rel(os.path.join(folder, 'report.md'))}")
    return 0
