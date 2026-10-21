"""Benchmarks: headless tournaments that compare backends on the same decks, opponents and seeds (docs/bench.md).

    from ygo_agent.bench import BenchSpec, Bench, build_report
    spec = BenchSpec(name="smoke", decks=["saffira"], backends=["heuristic", "random"],
                     opponents=["windbot:Blue-Eyes"], games=4)
    Bench(spec, folder, cfg).run()       # appends one line per game to folder/results.jsonl
    build_report(folder)                 # summary.json, report.md, chart.svg
"""

from .report import build as build_report  # noqa: F401
from .runner import Bench  # noqa: F401
from .spec import BenchSpec, Job  # noqa: F401
