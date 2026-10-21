Benchmark `readme`, 2026-10-21: 268 games. Full report: [bench/results/2026-10-21_212557_readme/report.md](../../bench/results/2026-10-21_212557_readme/report.md).

> A small-sample pilot: 3 games per (deck, model, opponent) for Haiku and Sonnet and 1 for Opus, so the 95% intervals are wide and the ordering between the Claude models isn't settled. Opus played only game 1 of each pairing, where the AI seat goes first; the like-for-like table compares every backend on those same games. The baselines play 30 games per pairing. The run is resumable: raise the counts in bench/configs/readme.toml and `ygo-agent bench readme --resume` plays only the new games, on the same seeds.

| # | Backend | Model | Games | W-L-D | Win rate (95% CI) | Rating | Going first / second | Avg turns |
|---:|---|---|---:|---:|---|---:|---:|---:|
| 1 | opus | `claude-opus-5-5` | 4 | 4-0-0 | **100%** (51%–100%) | 1845 | 4/4 · – | 3.8 |
| 2 | sonnet | `claude-sonnet-5-5` | 12 | 7-5-0 | **58%** (32%–81%) | 1597 | 5/8 · 2/4 | 7.7 |
| 3 | haiku | `claude-haiku-5-5` | 12 | 7-5-0 | **58%** (32%–81%) | 1597 | 4/8 · 3/4 | 6.2 |
| 4 | heuristic *(baseline)* | no model | 120 | 26-94-0 | **22%** (15%–30%) | 1282 | 15/60 · 11/60 | 7.6 |
| 5 | random *(baseline)* | no model | 120 | 2-118-0 | **2%** (0%–6%) | 838 | 0/60 · 2/60 | 7.4 |

| Backend | Time per game | Decision latency mean · p50 · p95 | Tokens per game: in · out · cache read | Cost per game | Invalid replies | Fallbacks | Rule-answered | Errors (timeouts) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| opus | 2m51s | 3.57s · 2.73s · 7.53s | 93 · 10.6k · 1.18M | $1.15 | 0.0% (0/186) | 0.0% | 0.9% | 0 (0) |
| sonnet | 3m05s | 2.42s · 1.86s · 5.53s | 145 · 13.0k · 1.86M | $0.80 | 0.0% (0/871) | 0.0% | 7.2% | 0 (0) |
| haiku | 3m03s | 2.79s · 1.56s · 9.04s | 126 · 30.5k · 1.88M | $0.058 | 0.0% (0/754) | 0.0% | 5.5% | 0 (0) |
| heuristic | 5.8s | – | – | free | – | 0.0% | 3.2% | 0 (0) |
| random | 5.5s | – | – | free | – | 0.0% | 4.0% | 0 (0) |

The 4 games every backend played (game 1 of each deck × opponent pairing: the same seeds and the same player going first for everyone):

| Backend | Games | Wins | Win rate (95% CI) |
|---|---:|---:|---|
| opus | 4 | 4 | **100%** (51%–100%) |
| sonnet | 4 | 3 | **75%** (30%–95%) |
| haiku | 4 | 1 | **25%** (5%–70%) |
| heuristic | 4 | 1 | **25%** (5%–70%) |
| random | 4 | 0 | **0%** (0%–49%) |
