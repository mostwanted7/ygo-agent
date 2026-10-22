"""`ygo-agent coach`: you play in EDOPro, the agent coaches you live and reviews the game afterwards.

    ygo-agent coach [--deck NAME] [--backend opus] [--opponent windbot:Blue-Eyes] [--level beginner] [--web]
    ygo-agent coach --review games/<dir> [--review-backend sonnet]      # review a finished coach game again
"""

import os
import sys
import time

LEVELS = ("beginner", "intermediate")


def register(sub):
    from ..cli import add_web, match_help, seconds
    p = sub.add_parser("coach", help="you play a deck in EDOPro, the agent coaches you live and reviews the game")
    p.add_argument("--deck", dest="coach_deck", metavar="DECK",
                   help="the deck you play: one `ygo-agent decks` lists, a .ydk or an EDOPro deck name (default: "
                        "recognised from the deck you submit in EDOPro)")
    p.add_argument("--backend", help="the coach's backend profile (default agent.backend: opus; e.g. sonnet, "
                                     "haiku)")
    p.add_argument("--model", help="override the backend's model")
    p.add_argument("--effort", help="override the backend's effort level")
    p.add_argument("--opponent", metavar="SEAT", help="who you play against (default from the config: "
                                                      "windbot:Blue-Eyes). " + match_help())
    p.add_argument("--level", choices=LEVELS, help="how the advice is written (default from the config: beginner)")
    p.add_argument("--review", metavar="GAME_DIR", help="don't play: write the review of a finished coach game again")
    p.add_argument("--review-backend", metavar="NAME", help="backend profile for the review (default: the coach's)")
    p.add_argument("--no-review", action="store_true", help="skip the review after each game")
    p.add_argument("--games", type=int, help="close the room after this many matches (default: when you press Ctrl+C)")
    p.add_argument("--port", type=int, help="room port (default from the config: 7911)")
    p.add_argument("--password", help="room password")
    p.add_argument("--best-of", type=int, choices=(1, 3, 5), default=1, help="games per match (default 1)")
    p.add_argument("--time-limit", type=int, help="your seconds per turn (default from the config: coach.time_limit; "
                                                  "0 = none)")
    p.add_argument("--no-lan", action="store_true", help="don't answer EDOPro's LAN room search (join by address)")
    p.add_argument("--seed", type=int, help="make the games reproducible")
    p.add_argument("--pace", type=seconds, default=0.0, metavar="SECONDS", help="minimum time per AI opponent decision")
    p.add_argument("--quiet", action="store_true", help="only the coach's advice in the terminal, not every event")
    add_web(p)
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--games-dir", help="where game logs go")
    p.add_argument("--rules", help="duel rules: MR1-MR5, GOAT, SPEED, RUSH (default from the config: MR3)")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")
    p.set_defaults(handler=main)
    return p


def settings(cfg):
    return {"opponent": "windbot:Blue-Eyes", "level": "beginner", "time_limit": 1200, "review_backend": "",
            "review_timeout_seconds": 600, **cfg.get("coach", {})}


def review_backend(cfg, name):
    from ..config import ConfigError, backend
    from .. import backends
    try:
        profile = backend(cfg, name or None)
        backends.check(profile)
    except (ConfigError, backends.BackendError) as e:
        sys.exit(f"error: {e}")
    return profile


def main(args, cfg):
    from ..agent.gamelog import BOLD, CYAN, DIM, YELLOW, paint
    from ..cli import check_backend, load_db, room_options
    opts = settings(cfg)
    reviewer = args.review_backend or opts["review_backend"] or None
    if args.review:
        return review_again(args, cfg, reviewer)
    from .. import backends
    from ..match import MatchError, SeatSpec, load_profile, run_games, wait_for_enter
    coach_profile = check_backend(cfg)
    review_profile = review_backend(cfg, reviewer) if reviewer else coach_profile
    db = load_db(cfg)
    profile = None
    if args.coach_deck:
        try:
            profile = load_profile(args.coach_deck, db, cfg)
        except MatchError as e:
            sys.exit(f"error: {e}")
    try:
        opponent = SeatSpec.parse(args.opponent or opts["opponent"])
    except MatchError as e:
        sys.exit(f"error: {e}")
    if opponent.kind == "human":
        sys.exit("error: the opponent can't be another human here; pick a WindBot deck AI or an AI deck")
    if opponent.kind == "agent":
        opponent = opponent.with_(mode="selfplay")
    level = args.level or opts["level"]
    room = room_options(args, cfg)
    room["time_limit"] = args.time_limit if args.time_limit is not None else int(opts["time_limit"])
    detail = backends.describe(coach_profile)
    deck = f"{profile.name} ({len(profile.main)} main / {len(profile.extra)} extra)" if profile else \
        "recognised from the deck you submit"
    print(paint(BOLD + ";" + CYAN, f"ygo-agent coach — your deck: {deck}; coach: {backends.label(coach_profile)}"
                                   f"{' — ' + detail if detail else ''}, {level} level; opponent: {opponent}; rules "
                                   f"{room['rules']}"))
    print(paint(DIM, f"{len(db.cards)} cards loaded from {len(db.db_paths)} databases."))
    limit = room["time_limit"]
    print(paint(YELLOW, ("You have " + (f"{limit} s per turn" if limit else "no time limit") + " (--time-limit N; "
                         "reading the advice takes time, so keep it long). The advice appears here"
                         + (" and in the web panel" if room["web"] else " (add --web for the browser panel, "
                            "which shows your hand and the advice on the board)")
                         + "; type !note in the duel chat (or in the panel's note box) to leave feedback.")))
    if room["web"]:
        from ..cli import start_panel
        start_panel(cfg, db)
    from ..arena.windbot import mono_path
    if opponent.kind == "windbot" and mono_path() is None:
        sys.exit("error: WindBot opponents need mono; pick an AI opponent (--opponent saffira:heuristic)")
    from .live import Coach
    engine = load_engine(cfg)
    coach = Coach(cfg, db, backend=coach_profile, profile=profile, level=level, opponent=opponent_info(opponent, db, cfg),
                  cards=engine.cards, echo="decisions" if args.quiet else "all",
                  review=None if args.no_review else reviewing(cfg, db, review_profile, level), say=say)
    run = None
    try:
        run = run_games(SeatSpec("human"), opponent, games=args.games, cfg=cfg, db=db, engine=engine,
                        echo=("all", "off"), on_room=coach.attach, on_game=coach.on_game, **room)
    except MatchError as e:
        coach.close(timeout=0)
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        print()
    if coach.reviews and any(t.is_alive() for t in coach.reviews):
        print(paint(DIM, "Waiting for the review to finish (Ctrl+C skips it)..."))
    try:
        coach.close()
    except KeyboardInterrupt:
        print()
    if run is not None:
        for line in run.summary_lines():
            print(line)
    if room["web"] and run is not None and run.games and sys.stdin.isatty():
        try:
            wait_for_enter(paint(DIM, f"The web panel stays up at {run.web_url} to look back at the games and their "
                                      "reviews. Press Enter to quit. "))
        except (KeyboardInterrupt, EOFError):
            print()
    return run


def say(*lines):
    from ..agent.gamelog import emit
    emit(lines)


def load_engine(cfg):
    from .. import paths
    from ..core import Engine, InstallError
    try:
        return Engine.load(paths.resolve(cfg["edopro_dir"]))
    except (InstallError, OSError) as e:
        sys.exit(f"can't load EDOPro's core: {e}")


def opponent_info(spec, db, cfg):
    """How the coach's prompt names the opponent (prompts.opponent_text)."""
    if spec.kind == "windbot":
        return {"kind": "windbot", "deck": spec.deck}
    from ..config import backend
    from ..match import MatchError, load_profile
    try:
        name = load_profile(spec.deck, db, cfg).name
    except (MatchError, FileNotFoundError):
        name = spec.deck
    return {"kind": "agent", "deck": name, "backend": backend(cfg, spec.backend).get("type")}


def reviewing(cfg, db, review_profile, level):
    """The review step of each finished game: write review.md, print it, push it to the panel."""
    def review(game):
        from ..agent.gamelog import BOLD, CYAN, DIM, paint
        from .review import write_review
        log = game.brain._log
        if log is None:
            return
        say(paint(DIM, f"\nCoach: writing the review of game {game.number} ({review_profile['name']})..."))
        started = time.monotonic()
        path, markdown, info = write_review(log.dir, cfg, db, review_profile, profile=game.brain.profile, level=level)
        took = round(time.monotonic() - started, 1)
        log.web.send("review", markdown=markdown, path=path, seconds=took, label=review_profile["name"])
        say("", paint(BOLD + ";" + CYAN, f"━━ Review of game {game.number} ({took}s) — {path}"), "", markdown.rstrip(), "")
    return review


def review_again(args, cfg, reviewer):
    from ..agent.gamelog import BOLD, CYAN, paint
    from ..cli import check_backend, load_db
    from .review import write_review
    if not os.path.isfile(os.path.join(args.review, "game.jsonl")):
        sys.exit(f"{args.review} is not a game log folder (no game.jsonl)")
    profile = review_backend(cfg, reviewer) if reviewer else check_backend(cfg)
    db = load_db(cfg)
    from ..match import MatchError, load_profile
    try:
        deck = load_profile(args.coach_deck, db, cfg) if args.coach_deck else None
        path, markdown, info = write_review(args.review, cfg, db, profile, profile=deck, level=args.level)
    except MatchError as e:
        sys.exit(f"error: {e} (pass --deck to say which deck the game was played with)")
    print(markdown)
    print(paint(BOLD + ";" + CYAN, f"Saved {path}"))
    return path
