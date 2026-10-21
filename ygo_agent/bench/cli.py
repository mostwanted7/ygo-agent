"""`ygo-agent bench`: run a benchmark from a plan file (bench/configs/<name>.toml) and/or flags, or rebuild a report.

    ygo-agent bench readme                                   # bench/configs/readme.toml
    ygo-agent bench --decks saffira --backends sonnet,heuristic --opponents windbot:Blue-Eyes --games 4
    ygo-agent bench readme --resume                          # continue the newest run of that plan
    ygo-agent bench report bench/results/<run>               # rebuild report.md, summary.json, chart.svg
    ygo-agent bench exam [NAME] [--backends opus,sonnet,haiku --judge opus]   # the decision exam (exam.py)
"""

from __future__ import annotations

import argparse
import os
import sys

from .. import paths

CONFIGS = os.path.join(paths.ROOT, "bench", "configs")


def register(sub) -> None:
    p = sub.add_parser("bench", help="benchmark backends: headless games against WindBot deck AIs (or AI seats), "
                                     "with win rates, latency, tokens, cost and reliability",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("what", nargs="*", metavar="PLAN | report DIR | exam [NAME]",
                   help="a plan: a name in bench/configs/ or a .toml file (flags override it); or `report DIR`; or "
                        "`exam [NAME]`: grade the models on logged decisions (bench/exams/NAME.json, default main)")
    p.add_argument("--name", help="the benchmark's name (run folders are bench/results/<time>_<name>)")
    p.add_argument("--decks", help="comma-separated AI-piloted decks, e.g. saffira,blackwing")
    p.add_argument("--backends", help="comma-separated backend profiles, e.g. opus,sonnet,haiku,heuristic,random")
    p.add_argument("--opponents", help="comma-separated opponent seats: windbot:<deck AI> or an AI seat such as "
                                       "saffira:sonnet")
    p.add_argument("--games", type=int, help="games per (deck, backend, opponent); default 6. With exam: also review "
                                             "this many logged games per model")
    p.add_argument("--games-for", metavar="B=N,...", help="per-backend game counts, e.g. heuristic=30,opus=2")
    p.add_argument("--seed", type=int, help="first seed of the shared seed list (default 1000)")
    p.add_argument("--rules", help="duel rules (default MR3)")
    p.add_argument("--parallel", type=int, metavar="K", help="games at a time (default 3)")
    p.add_argument("--budget-usd", type=float, metavar="USD",
                   help="start no more games once the finished ones cost this much (the backends' cost figures)")
    p.add_argument("--timeout", type=float, metavar="SECONDS", help="give up a WindBot game after this long "
                                                                    "(default 5400)")
    p.add_argument("--resume", nargs="?", const=True, metavar="DIR",
                   help="continue a run: its folder, or (no DIR) the newest run of this plan; finished games are "
                        "skipped")
    p.add_argument("--out", metavar="DIR", help="the run folder (default bench/results/<time>_<name>; for a scratch "
                                                "run games/bench-smoke/<time>_<name>)")
    p.add_argument("--scratch", action="store_true", default=None,
                   help="a test run: put it under games/bench-smoke/ (git-ignored) instead of bench/results/ "
                        "(plans can say scratch = true, as smoke does)")
    p.add_argument("--no-probe", action="store_true", help="skip the one-call check of each LLM backend")
    p.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    p.add_argument("--publish", metavar="DIR", help="with report: also copy the leaderboard (leaderboard.md) and "
                                                    "chart.svg to DIR, e.g. docs/bench for the README")
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")
    x = p.add_argument_group("exam", "ygo-agent bench exam [NAME]: --backends are the candidates (default "
                                     "opus,sonnet,haiku), --decks the decks (saffira,blackwing), --seed the sampling "
                                     "seed, --parallel the asks at a time (4); --resume, --out, --budget-usd, "
                                     "--dry-run and --no-probe work as for games")
    x.add_argument("--judge", metavar="B[,B2]", help="the judge's backend profile (default opus); a second one "
                                                     "re-judges the same answers as a cross-check")
    x.add_argument("--positions", type=int, metavar="N", help="positions to sample (default 40)")
    x.add_argument("--select", action="store_true", help="only sample the positions into bench/exams/NAME.json")
    x.add_argument("--resample", action="store_true", help="sample again, replacing bench/exams/NAME.json")
    x.add_argument("--sources", metavar="DIR,...", help="where to look for logged games (default: the games folder)")
    x.add_argument("--judge-batch", type=int, metavar="K", help="positions per judge call (default 3)")
    x.add_argument("--judge-effort", help="the judge's effort (default: its profile's)")
    x.add_argument("--inline-judge", action="store_true", help="no tools for the judge: card texts in the prompt "
                                                               "instead of reading scripts")
    x.add_argument("--probe", type=float, metavar="F", help="share of positions where the judge sees one move twice, "
                                                            "to measure its consistency (default 0.15)")
    x.add_argument("--games-from", metavar="DIR", help="the benchmark run to take the --games logs from (default: the "
                                                       "newest in bench/results)")
    p.set_defaults(handler=main)


def plan_path(name: str) -> str:
    if os.path.isfile(name):
        return name
    path = os.path.join(CONFIGS, name if name.endswith(".toml") else name + ".toml")
    if os.path.isfile(path):
        return path
    known = sorted(f[:-5] for f in os.listdir(CONFIGS) if f.endswith(".toml")) if os.path.isdir(CONFIGS) else []
    sys.exit(f"no benchmark plan {name!r} (a .toml file, or one of bench/configs/: {', '.join(known) or 'none'})")


def flag_values(args) -> dict:
    from .spec import parse_games_for, split_list
    out = {}
    for key in ("name", "games", "seed", "rules", "parallel", "budget_usd", "timeout"):
        value = getattr(args, key)
        if value is not None:
            out[key] = value
    for key in ("decks", "backends", "opponents"):
        if getattr(args, key):
            out[key] = split_list(getattr(args, key))
    if args.games_for:
        out["games_for"] = parse_games_for(args.games_for)
    if args.scratch:
        out["scratch"] = True
    return out


def main(args, cfg) -> int:
    from ..match import MatchError
    from . import report, runner
    from .spec import BenchSpec, SpecError, opponent_label

    what = list(args.what)
    if what and what[0] == "exam":
        from . import exam
        return exam.main(args, cfg, what[1:])
    if what and what[0] == "report":
        if len(what) != 2:
            sys.exit("usage: ygo-agent bench report <run folder>")
        folder = what[1]
        if not os.path.isfile(os.path.join(folder, runner.RESULTS)):
            sys.exit(f"{folder} has no {runner.RESULTS}")
        summary = report.build(folder)
        print(report.leaderboard_md(summary))
        print(f"\nWrote {os.path.join(folder, 'report.md')}, summary.json and chart.svg.")
        if args.publish:
            print(f"Published {', '.join(report.publish(folder, summary, args.publish))}.")
        return 0
    if what and what[0] == "run":
        what = what[1:]
    if len(what) > 1:
        sys.exit("give at most one plan (a name in bench/configs/ or a .toml file)")
    try:
        data = {}
        if what:
            data = BenchSpec.load(plan_path(what[0])).to_dict()
        folder = None
        if args.resume:
            folder = args.resume if isinstance(args.resume, str) else runner.latest_folder(
                flag_values(args).get("name") or data.get("name"), [runner.RESULTS_ROOT, runner.scratch_root(cfg)])
            if not folder or not os.path.isfile(os.path.join(folder, "spec.json")):
                sys.exit(f"nothing to resume{f' in {folder}' if folder else ''} (no spec.json)")
            stored = report._load(folder, "spec.json").get("spec", {})
            for locked in ("seed", "rules"):
                new = {**data, **flag_values(args)}.get(locked)
                if new is not None and stored.get(locked) is not None and new != stored[locked]:
                    sys.exit(f"--resume keeps the run's {locked} ({stored[locked]}), so its games stay comparable")
            data = {**stored, **data}
        data.update(flag_values(args))
        spec = BenchSpec.from_dict(data).validate()
    except SpecError as e:
        sys.exit(f"error: {e}")
    jobs = spec.jobs()
    if args.dry_run:
        print(f"{spec.name}: {len(jobs)} games, seeds {spec.seed}..{spec.seed + max(spec.games_of(b) for b in spec.backends) - 1}")
        for j in jobs:
            print(f"  {j.deck:<10} {j.backend:<10} vs {opponent_label(j.opponent):<24} game {j.index + 1:>2}  seed "
                  f"{j.seed}  {'AI seat' if j.first == 'player' else 'opponent'} goes first")
        return 0
    root = runner.scratch_root(cfg) if spec.scratch else runner.RESULTS_ROOT
    folder = folder or (os.path.abspath(args.out) if args.out else runner.new_folder(spec.name, root))
    os.makedirs(folder, exist_ok=True)
    bench = runner.Bench(spec, folder, cfg, argv=["ygo-agent", "bench"] + sys.argv[2:],
                         probe_backends=not args.no_probe)
    try:
        bench.run()
    except MatchError as e:
        sys.exit(f"error: {e}")
    summary = report.build(folder)
    print()
    print(report.leaderboard_md(summary))
    print(f"\nReport: {runner.rel(os.path.join(folder, 'report.md'))} (summary.json, chart.svg, replays/ next to it).")
    return 0
