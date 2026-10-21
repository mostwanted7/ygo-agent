"""`ygo-agent train` and `ygo-agent train-compare` (registered from ygo_agent/cli.py)."""

from __future__ import annotations

import sys

PHASES = ("study", "lab", "games")


def register(sub) -> None:
    p = sub.add_parser("train", help="train the agent on a new deck: study the cards and scripts, test lines in a "
                                     "lab, play and review games, and write the deck's playbook.md")
    p.add_argument("ydk", nargs="?", help="the deck file (.ydk); not needed with --resume")
    p.add_argument("--name", dest="deck_key", required=True,
                   help="the deck to create: a folder <name>/ in your decks dir (`ygo-agent decks` shows where)")
    p.add_argument("--into", choices=("user", "repo"),
                   help="where the deck folder goes: user = your decks dir (default), repo = decks/ in the checkout")
    p.add_argument("--display-name", help="the deck's name in prompts (default: the .ydk's file name)")
    p.add_argument("--backend", help="the reviewer's backend profile (default trainer.backend: opus)")
    p.add_argument("--player-backend", help="the backend that plays the lab and the games (default "
                                            "trainer.player_backend: sonnet)")
    p.add_argument("--opponents", help="comma-separated opponent seats: WindBot deck AIs legal under the rules, or "
                                       "heuristic:<deck> etc. (default trainer.opponents)")
    p.add_argument("--lab-hands", type=int, help="lab hands in round 1 (default trainer.lab_hands: 10)")
    p.add_argument("--second-hands", type=int, help="of those, going second into a fixed board (default 2)")
    p.add_argument("--games", type=int, help="games per round (default trainer.games: 4)")
    p.add_argument("--max-rounds", type=int, help="rounds of lab + games (default trainer.max_rounds: 3)")
    p.add_argument("--budget-usd", type=float, help="stop cleanly before going over this (API-price USD)")
    p.add_argument("--resume", action="store_true", help="continue the run in <deck folder>/train/")
    p.add_argument("--phases", help="which phases to run (default study,lab,games)")
    p.add_argument("--seed", type=int, help="lab hands and game seeds (default 1)")
    p.add_argument("--parallel", type=int, help="games at a time (default 2)")
    p.add_argument("--lab-parallel", type=int, help="lab hands at a time (default 3)")
    p.add_argument("--test-repeat", type=int, help="runs per saved case at the end (default 3)")
    p.add_argument("--gate-repeat", type=int, help="runs per saved case when a condense or rewrite is checked against "
                                                   "them (default 2; 0 turns the check off)")
    p.add_argument("--write-rules", action="store_true", help="write rule proposals that qualify into rules.py "
                                                              "(default: only train/rule-proposals.md)")
    p.add_argument("--inline", action="store_true", help="claude-code reviewer without tools (excerpts inline)")
    p.add_argument("--out", help="put the deck folder here instead (outside the deck dirs: only with --phases study)")
    p.add_argument("--quiet", action="store_true", help="no key plays in the terminal, only the trainer's lines")
    add_config(p)
    p.set_defaults(handler=cmd_train)

    p = sub.add_parser("train-compare", help="play the same games with the trained playbook, the study draft and no "
                                             "playbook, to see what training bought")
    p.add_argument("--name", dest="deck_key", required=True, help="a trained deck (its name)")
    p.add_argument("--backend", default=None, help="the player backend (default sonnet)")
    p.add_argument("--opponent", default="windbot:Blue-Eyes", help="the opponent seat (default windbot:Blue-Eyes)")
    p.add_argument("--games", type=int, default=3, help="games per variant (default 3)")
    p.add_argument("--variants", default="trained,draft,none", help="which playbooks (default trained,draft,none)")
    p.add_argument("--seed", type=int, default=7, help="game seeds (the same for every variant)")
    p.add_argument("--parallel", type=int, default=2, help="games at a time (default 2)")
    p.add_argument("--budget-usd", type=float, help="stop before going over this")
    add_config(p)
    p.set_defaults(handler=cmd_compare)


def add_config(p):
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")


def cmd_train(args, cfg) -> int:
    """Options: the flags given, else (with --resume) the run's own, else [trainer] in the config, else defaults."""
    import dataclasses
    import json
    import os
    from .pipeline import Options, Trainer
    from .workspace import TrainerError
    if not args.ydk and not args.resume:
        sys.exit("give the deck's .ydk file (or --resume)")
    given = {"ydk": args.ydk, "backend": args.backend, "player_backend": args.player_backend,
             "opponents": [x.strip() for x in args.opponents.split(",") if x.strip()] if args.opponents else None,
             "lab_hands": args.lab_hands, "second_hands": args.second_hands, "games": args.games,
             "max_rounds": args.max_rounds, "budget": args.budget_usd, "seed": args.seed,
             "phases": tuple(x.strip() for x in args.phases.split(",") if x.strip()) if args.phases else None,
             "parallel": args.parallel, "lab_parallel": args.lab_parallel, "test_repeat": args.test_repeat,
             "gate_repeat": args.gate_repeat, "write_rules": True if args.write_rules else None,
             "out": args.out, "deck_name": args.display_name, "agentic": False if args.inline else None,
             "echo": "off" if args.quiet else None}
    bad = [x for x in given["phases"] or () if x not in PHASES]
    if bad:
        sys.exit(f"unknown phase(s) {', '.join(bad)}; use {', '.join(PHASES)}")
    fields = {f.name for f in dataclasses.fields(Options)}
    base = {k: v for k, v in (cfg.get("trainer") or {}).items() if k in fields}
    try:
        given["out"] = deck_folder(args, cfg)
    except FileNotFoundError as e:  # decks.DeckError
        sys.exit(f"error: {e}")
    if args.resume:
        state = os.path.join(given["out"], "train", "state.json")
        try:
            with open(state, encoding="utf-8") as f:
                base.update({k: v for k, v in (json.load(f).get("options") or {}).items() if k in fields})
        except (OSError, ValueError):
            pass
    values = {**base, **{k: v for k, v in given.items() if v is not None}}
    values.update(name=args.deck_key, rules=cfg["duel"]["rules"])
    if isinstance(values.get("phases"), list):
        values["phases"] = tuple(values["phases"])
    opts = Options(**values)
    cfg["chat"] = "off"
    try:
        status = Trainer(opts, cfg, resume=args.resume).run()
    except TrainerError as e:
        sys.exit(f"error: {e}")
    print(f"Training {status}.")
    return 0 if status == "done" else 2


def deck_folder(args, cfg) -> str:
    """Where the deck being trained lives: --out; else <user decks dir>/<name> (--into repo: decks/<name>). A resume
    without --into continues the run wherever it is (runs before the user decks dir existed are in decks/)."""
    import os
    from .. import decks
    if args.out:
        return os.path.abspath(args.out)
    if args.resume and not args.into:
        for location in ("user", "repo"):
            folder = os.path.join(decks.root_dir(location, cfg), args.deck_key)
            if os.path.isfile(os.path.join(folder, "train", "state.json")):
                return folder
    if args.resume:
        return os.path.join(decks.root_dir(args.into or "user", cfg), args.deck_key)
    return decks.target(args.deck_key, args.into or "user", cfg)


def cmd_compare(args, cfg) -> int:
    from .compare import compare
    from .workspace import TrainerError
    cfg["chat"] = "off"
    try:
        path = compare(cfg, args.deck_key, backend=args.backend or "sonnet", opponent=args.opponent,
                       games=args.games, variants=[v.strip() for v in args.variants.split(",") if v.strip()],
                       seed=args.seed, parallel=args.parallel, budget=args.budget_usd)
    except TrainerError as e:
        sys.exit(f"error: {e}")
    print(f"Comparison: {path}")
    return 0

