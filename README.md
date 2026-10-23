# ygo-agent

[![CI](https://github.com/mostwanted7/ygo-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/mostwanted7/ygo-agent/actions/workflows/ci.yml)

**An LLM-powered Yu-Gi-Oh! opponent, coach and testing environment for [EDOPro](https://projectignis.github.io/).**
Play against it, watch AI decks face each other, or get advice while you play. A local browser app shows the board,
each decision, and the model's explanation and plan.

**[v0.1.0-beta.2](https://github.com/mostwanted7/ygo-agent/releases/tag/v0.1.0-beta.2) · Linux · Open source (AGPL-3.0-or-later).**
See the [changelog](CHANGELOG.md) for changes.

![The web panel: a live duel with the agent's decisions, explanations and plan](docs/img/demo.gif)

ygo-agent connects a language model to EDOPro's game engine; it is not a separately trained model. Claude Code is
the default backend, using your existing login. The Anthropic API and OpenAI-compatible servers such as Ollama,
vLLM, llama.cpp, LM Studio and OpenRouter are also supported. You can change the model independently of the deck.

## Install and play

You need:

- **Linux and Python 3.11+**, with Git, pip and Python's `venv` support.
- **EDOPro**, including its downloaded card databases, scripts and `libocgcore.so`. The default location is
  `~/Games/ProjectIgnis`.
- **Claude Code**, installed and logged in, or another configured [backend](docs/backends.md).
- **Mono with `xbuild`** to build the WindBot fork used for scripted opponents and joining rooms you host.

```sh
git clone --recursive https://github.com/mostwanted7/ygo-agent.git
cd ygo-agent
python3 -m venv .venv
.venv/bin/pip install -e .
./build.sh
.venv/bin/ygo-agent doctor
.venv/bin/ygo-agent web --open
```

If EDOPro is elsewhere, create `config.local.toml` in the repository root before running `doctor`:

```toml
edopro_dir = "/path/to/ProjectIgnis"
```

`doctor` checks your setup and explains anything missing. The app opens at **http://127.0.0.1:7930/**. Choose
**Duel the agent**, start the game, then join from EDOPro's **LAN Mode** using host **127.0.0.1**, port **7911**.
Select your deck and ready up. Enter the address directly rather than relying on LAN discovery.

Three deck profiles are included: **Saffira, Blackwing and Geargia**. Use **Decks → New deck** to prepare your own
`.ydk` deck.

**Current supported focus: pre-Pendulum play (MR2-era mechanics).** The browser board has no complete Pendulum-zone layout;
Pendulum and Link formats are outside the supported UI scope. The engine currently defaults to **Master Rule 3**,
and the published benchmarks use MR3. You can select `--rules MR2`; other engine rule flags do not imply complete
browser support for those formats.

Prefer the terminal? Run `.venv/bin/ygo-agent play --deck blackwing --web`. Use `--backend sonnet` to change the
model profile, `--effort high` to request more reasoning effort on supported backends, and `--help` for options.
Hosted models use your provider's subscription allowance or API billing; local models use your own hardware.

## What you can do

| Mode | Purpose |
|---|---|
| **Play** | Duel an AI through EDOPro, with its explanations visible in the browser. |
| **Self-play** | Run AI vs AI or AI vs WindBot games; watch live or run batches with fixed seeds. |
| **Teach** | Watch the agent play a deck and explain its decisions. |
| **Coach** | Make your own moves in EDOPro while the agent advises and reviews the game. |
| **Train / Learn** | Build a deck playbook, practise it, then incorporate feedback from your games. |
| **Benchmark / Test** | Compare models, replay decisions, and check saved regression cases. |

Play, self-play, teaching, coaching and deck training are available through the [web app](docs/web.md) and terminal
commands; benchmarking, decision replay and regression tests use the terminal. Every game saves readable logs,
model prompts and replies, statistics, and an EDOPro replay under `games/`.

## How it works

1. **EDOPro runs the duel.** The engine generates the available decisions and resolves card effects.
2. **The agent describes the position.** The model receives its permitted view of the game, card texts, a deck
   playbook, recent events and the available options. Opponent hands and face-down identities stay hidden.
3. **The model chooses.** It returns option indices with a short explanation and optional plan. The agent validates
   the reply before passing it to the engine; a few deck rules handle specific cases directly.
4. **The browser shows what happened.** You can follow both players, inspect decisions, and leave feedback.

The model can misunderstand an interaction or choose a bad line, but it cannot override the engine's rules.
Legal play is not necessarily good play, and the explanations are the model's stated reasons—not a guarantee
that its reasoning is correct.

**“Training” improves guidance, not model weights.** For a new deck, the trainer reads card texts and scripts,
asks for your advice, writes a playbook, and reviews practice games. During later games, leave notes in the web
panel or type `!your feedback` in EDOPro chat. Press **Learn** on the deck page (or run
`ygo-agent learn --deck NAME`) to review those notes, apply checked playbook corrections, and save regression cases.
Ordinary games do not silently rewrite the playbook. See [training](docs/training.md) and
[adding a deck](docs/adding-a-deck.md).

## How well does it play?

**Model quality matters.** Opus is the default because it performed best across the available decision exam and
whole-game reviews. The available comparisons consistently favor Opus, and the remaining mistakes suggest room
for stronger models and better guidance. No performance ceiling has been established; the effect of raising
reasoning effort still needs a controlled comparison.

In the **40-position blind decision exam** on 2026-10-22, each model answered the same logged positions. An Opus
judge graded anonymised answers; a second Sonnet judge also ranked Opus first.

| Model | Mean grade / 4 | Best move | Mistake or blunder | Significant mistakes / reviewed game |
|---|---:|---:|---:|---:|
| **Opus 5.5** | **3.73** | **88%** | **5%** | **0.25** |
| Sonnet 5.5 | 3.30 | 72% | 15% | 1.0 |
| Haiku 5.5 | 3.15 | 62% | 15% | 2.0 |

The last column comes from four matched whole-game reviews per model. These are model-judged results with small
samples and possible judge bias; Sonnet and Haiku were not reliably separated.
[Full exam and judge checks](bench/exams/results/2026-10-22_014130_main/report.md).

The earlier **game benchmark** used Saffira and Blackwing against WindBot's Blue-Eyes and Time Thief under MR3:

| Backend | Wins / games | Win rate (95% interval) |
|---|---:|---:|
| Opus 5.5 | 4 / 4 | 100% (51–100%) |
| Sonnet 5.5 | 7 / 12 | 58% (32–81%) |
| Haiku 5.5 | 7 / 12 | 58% (32–81%) |
| Heuristic baseline | 26 / 120 | 22% (15–30%) |
| Random baseline | 2 / 120 | 2% (0–6%) |

**Opus only played four games, all going first.** Its 100% is not a general win-rate estimate. On those same four
seeded deals, Sonnet won three and Haiku one. In this run, Opus's median decision took 2.7 seconds and its reported
API-equivalent cost averaged $1.15 per game; a Claude Code subscription is not billed per call.
[Full results, latency, costs and replays](bench/results/2026-10-21_212557_readme/report.md).

Run `ygo-agent bench readme` or `ygo-agent bench exam` to repeat or extend the measurements.
[Benchmark methodology](docs/bench.md) explains seeds, sample sizes, model judging and limitations.

## Configuration and development

Put overrides in `config.local.toml`; [config/default.toml](config/default.toml) documents the settings. CLI flags
win over both files. See [backends](docs/backends.md) for model profiles and [adding a backend](docs/adding-a-backend.md)
for extending support.

```sh
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

Tests make no real model calls unless explicitly enabled. Integration checks skip when their external tools are
unavailable. For the implementation, read the [architecture](docs/architecture.md) and
[decision protocol](docs/decision-protocol.md); for coaching, see the [coach guide](docs/coach.md).

Licensed under [AGPL-3.0-or-later](LICENSE). Built on the work of Project Ignis, EDOPro, ygopro-core and WindBot.
