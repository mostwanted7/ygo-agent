"""ygo-agent: command line.

    ygo-agent play [--deck saffira] [--backend opus] [--web]   # the agent hosts a room, you join it from EDOPro
    ygo-agent play --join          # legacy: host a LAN room in EDOPro, the agent's bot (WindBot fork) joins it
    ygo-agent selfplay --a saffira:opus --b blackwing:sonnet [--games N] [--parallel K] [--spectate --pace 2]
    ygo-agent teach --deck blackwing [--opponent windbot:Blue-Eyes]   # the agent plays and explains; you watch
    ygo-agent teach --join         # legacy: the bot explains every decision in a room you host
    ygo-agent coach [--deck saffira] [--web]   # you play in EDOPro, the agent coaches you live and reviews the game
    ygo-agent replay games/latest 14 [--save NAME --expect '[[2]]' --note "..."]
    ygo-agent test [NAME ...]      # re-run saved regression cases
    ygo-agent decks                # every deck profile: where it lives, playbook, rules, saved cases, .ydk
    ygo-agent web [--demo games/<dir> --speed 2]   # the web panel: recorded games, or one replayed live
"""

import argparse
import json
import sys

from . import backends
from .config import ConfigError, load_config, backend


def add_common(p):
    p.add_argument("--deck", help="deck profile: a deck in decks/ or your decks dir (`ygo-agent decks`), a .ydk file "
                                  "or a deck in EDOPro's deck folder (default from the config)")
    p.add_argument("--backend", help="backend profile: a [backends.NAME] table in the config (e.g. opus, sonnet, "
                                     "api-opus, local, heuristic, random; default agent.backend: opus)")
    p.add_argument("--model", help="override the backend's model (e.g. opus, sonnet, qwen3:14b)")
    p.add_argument("--effort", help="override the backend's effort level (low, medium, high, xhigh, max)")
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--games-dir", help="where game logs go")
    p.add_argument("--rules", help="rules stated when the room doesn't report them (e.g. MR3, MR5)")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")


def seconds(text):
    """--pace 2 or --pace 2s."""
    try:
        value = float(str(text).strip().removesuffix("s"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of seconds: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError("can't be negative")
    return value


def add_web(p):
    p.add_argument("--web", action=argparse.BooleanOptionalAction, default=None,
                   help="also serve the web panel (board, reasoning, feedback box) on http://127.0.0.1:7930/; "
                        "--no-web overrides web.auto in the config")
    p.add_argument("--web-port", type=int, help="port for the web panel (default from the config)")


def add_bot(p, arena=False):
    """Room and bot options. `arena`: the command can also host the room itself (play, teach)."""
    p.add_argument("--brain-only", action="store_true",
                   help="with --join: run only the brain server (start the bot yourself; the command is printed)")
    p.add_argument("--host", help="with --join: the room's address (default from the config)")
    p.add_argument("--port", type=int, help="room port (default from the config: 7911)")
    p.add_argument("--password", help="room password")
    p.add_argument("--name", help="the agent's player name in EDOPro")
    p.add_argument("--brain-port", type=int, help="with --join: local port for the bot ⇄ agent bridge")
    p.add_argument("--chat", choices=("banter", "off"), help="in-duel chat: a few jokes, or none")
    add_web(p)
    if arena:
        add_room(p)


def add_room(p):
    """Options for a room the arena hosts."""
    p.add_argument("--best-of", type=int, choices=(1, 3, 5), default=1, help="games per match (default 1)")
    p.add_argument("--time-limit", type=int, help="seconds per turn for a human player (default from the config: "
                                                  "arena.time_limit; AI seats have none)")
    p.add_argument("--no-lan", action="store_true", help="don't answer EDOPro's LAN room search (join by address)")
    p.add_argument("--seed", type=int, help="make the games reproducible")
    p.add_argument("--pace", type=seconds, default=0.0, metavar="SECONDS",
                   help="minimum time per AI decision, so a watcher can follow (e.g. 2 or 2s)")


def parser():
    ap = argparse.ArgumentParser(prog="ygo-agent", description="LLM-driven Yu-Gi-Oh! players for EDOPro.")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    p = sub.add_parser("play", help="duel the agent: it hosts a room and you join it from EDOPro")
    p.add_argument("--join", action="store_true",
                   help="legacy: you host a LAN room in EDOPro and the agent's bot (the WindBot fork) joins it")
    p.add_argument("--teach", action="store_true", help="with --join: explain every decision for someone learning "
                                                        "the deck (arena-hosted: use `ygo-agent teach`)")
    p.add_argument("--games", type=int, help="close the room after this many matches (default: when you press Ctrl+C)")
    add_bot(p, arena=True)
    add_common(p)

    p = sub.add_parser("selfplay", help="two seats duel each other: AI vs AI, or AI vs a WindBot deck AI")
    p.add_argument("--a", metavar="SEAT", help="seat A (default: the config's deck and backend). " + match_help())
    p.add_argument("--b", metavar="SEAT", default="windbot:Blue-Eyes",
                   help="seat B (default windbot:Blue-Eyes); same forms as --a")
    p.add_argument("--games", type=int, default=1, help="matches to play (default 1)")
    p.add_argument("--parallel", type=int, default=1, metavar="K", help="matches at a time (default 1)")
    p.add_argument("--spectate", action="store_true",
                   help="host the room on --port and wait for you to join as a spectator (or Enter) before each match")
    p.add_argument("--quiet", action="store_true", help="print only the key plays and the results")
    p.add_argument("--first", choices=("a", "b"), help="who goes first in game 1 of each match (default: the RPS "
                                                       "winner chooses)")
    p.add_argument("--stack-a", metavar="CARDS", help="comma-separated card names/codes put on top of A's Deck "
                                                       "(the first 5 are its opening hand)")
    p.add_argument("--stack-b", metavar="CARDS", help="same for B")
    p.add_argument("--out", help="the run's folder (default games/matches/<time>_<a>-vs-<b>/)")
    p.add_argument("--timeout", type=float, help="give up a room after this many seconds")
    p.add_argument("--port", type=int, help="with --spectate: the room's port (default from the config: 7911)")
    p.add_argument("--password", help="room password")
    p.add_argument("--chat", choices=("banter", "off"), help="in-duel chat: a few jokes, or none")
    add_web(p)
    add_room(p)
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--games-dir", help="where game logs go")
    p.add_argument("--rules", help="duel rules: MR1-MR5, GOAT, SPEED, RUSH (default from the config: MR3)")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")

    p = sub.add_parser("teach", help="the agent plays and explains every decision; watch as a spectator")
    p.add_argument("--opponent", metavar="SEAT", default="windbot:Blue-Eyes",
                   help="who it plays against (default windbot:Blue-Eyes): " + match_help())
    p.add_argument("--games", type=int, default=1, help="matches to play (default 1)")
    p.add_argument("--join", action="store_true",
                   help="legacy: host the room in EDOPro yourself, add an AI opponent, sit as a spectator; the bot joins")
    add_bot(p, arena=True)
    add_common(p)

    p = sub.add_parser("replay", help="re-ask a logged decision with the current playbook and rules")
    p.add_argument("game_dir", nargs="?")
    p.add_argument("decision", nargs="?", type=int)
    p.add_argument("--tests", nargs="*", metavar="NAME", help="run saved cases instead (all if no names)")
    p.add_argument("--save", metavar="NAME", help="save this decision as a test case")
    p.add_argument("--expect", help="JSON list of acceptable choices, e.g. '[[0], [2]]' or '[[]]' for pass")
    p.add_argument("--reject", help="JSON list of choices that count as the old mistake")
    p.add_argument("--note", default="", help="what the case checks")
    p.add_argument("--repeat", type=int, default=3, help="runs per saved case (the model isn't deterministic)")
    add_common(p)

    p = sub.add_parser("test", help="re-run saved regression cases (<deck folder>/tests)")
    p.add_argument("names", nargs="*", metavar="NAME", help="case names (default: every case of the deck)")
    p.add_argument("--repeat", type=int, default=3, help="runs per case (the model isn't deterministic)")
    p.add_argument("--ablate-rules", action="store_true",
                   help="replay each deck rule's cases with that rule disabled, to find rules the model no longer needs")
    add_common(p)

    p = sub.add_parser("decks", help="list the deck profiles: decks/ in the repo, then your decks dir "
                                     "([decks] user_dir; `train` puts new decks there)")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")

    p = sub.add_parser("doctor", help="check the setup: Python, config, EDOPro and its core, mono and WindBot, "
                                      "backends, decks, ports (exit 1 when something fails)")
    p.add_argument("--json", action="store_true", help="print the results as JSON (name, status, detail, hint)")
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")

    p = sub.add_parser("web", help="the web panel on its own: browse and replay recorded games, or a live demo")
    p.add_argument("--demo", metavar="GAME_DIR", help="replay a recorded game (games/<dir>) live, as if it were "
                                                       "being played now")
    p.add_argument("--speed", type=float, default=2.0, help="demo speed (default 2: about twice real time)")
    p.add_argument("--loop", action="store_true", help="restart the demo when it ends")
    p.add_argument("--port", dest="web_port", type=int, help="port (default from the config: 7930)")
    p.add_argument("--host", dest="web_host", help="bind address (default 127.0.0.1)")
    p.add_argument("--open", action="store_true", help="open the panel in your browser")
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--games-dir", help="where game logs are")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")
    from .bench.cli import register as register_bench  # ygo-agent bench (ygo_agent/bench/cli.py)
    register_bench(sub)
    from .trainer.cli import register as register_train  # ygo-agent train, train-compare (ygo_agent/trainer/cli.py)
    register_train(sub)
    from .coach.cli import register as register_coach  # ygo-agent coach (ygo_agent/coach/cli.py)
    register_coach(sub)
    return ap


def overrides(args):
    """CLI flags as a config overlay."""
    o = {}

    def put(path, value):
        if value is None:
            return
        node = o
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value

    put(("deck",), getattr(args, "deck", None))
    put(("edopro_dir",), getattr(args, "edopro_dir", None))
    put(("games_dir",), getattr(args, "games_dir", None))
    put(("duel", "rules"), getattr(args, "rules", None))
    put(("agent", "backend"), getattr(args, "backend", None))
    for flag in ("host", "port", "password"):
        put(("room", flag), getattr(args, flag, None))
    put(("bot", "name"), getattr(args, "name", None))
    put(("bot", "brain_port"), getattr(args, "brain_port", None))
    put(("chat",), getattr(args, "chat", None))
    put(("web", "auto"), getattr(args, "web", None))
    put(("web", "enabled"), getattr(args, "web", None))
    put(("web", "port"), getattr(args, "web_port", None))
    put(("web", "host"), getattr(args, "web_host", None))
    put(("web", "open_browser"), getattr(args, "open", None) or None)
    return o


def configure(args):
    local = args.config if args.config else None
    cfg = load_config(**({"local": local} if local else {}), overrides=overrides(args))
    name = cfg["agent"]["backend"]
    for key in ("model", "effort"):
        value = getattr(args, key, None)
        if value is not None:
            cfg["backends"][name][key] = value
    return cfg


def match_help():
    from .match import SPEC_HELP
    return "SEAT: " + SPEC_HELP


def web_on(cfg):
    """--web, or web.auto (web.enabled before Stage 4) in the config."""
    web = cfg.get("web", {})
    return bool(web.get("auto") or web.get("enabled"))


def mode_of(args):
    if args.cmd == "teach":
        return args.cmd
    return "teach" if getattr(args, "teach", False) else "play"


def load_db(cfg):
    from .agent.carddb import CardDB
    db = CardDB(cfg["edopro_dir"])
    if not db.cards:
        sys.exit(f"No EDOPro card databases found in {db.root} (set edopro_dir in config.local.toml or --edopro-dir).")
    return db


def load_profile(cfg, db, key=None):
    """A deck folder under decks/, or a .ydk path / EDOPro deck name (see match.load_profile)."""
    from .match import MatchError, load_profile as find
    try:
        return find(key or cfg["deck"], db, cfg)
    except (MatchError, FileNotFoundError) as e:
        sys.exit(str(e))


def load_deck(cfg, key=None):
    db = load_db(cfg)
    return db, load_profile(cfg, db, key)


def cmd_play(args, cfg):
    """play --join and teach --join: the WindBot fork joins a room the user hosts in EDOPro."""
    import os
    from . import paths, join
    from .agent.bridge_server import Runtime
    from .agent.gamelog import paint, BOLD, CYAN, DIM

    cfg["mode"] = mode_of(args)
    profile_cfg = check_backend(cfg)
    if not args.brain_only and not os.path.exists(paths.WINDBOT_EXE):
        sys.exit(f"{paths.WINDBOT_EXE} is missing — run ./build.sh first.")
    os.makedirs(paths.resolve(cfg["games_dir"]), exist_ok=True)
    db, profile = load_deck(cfg)
    detail = backends.describe(profile_cfg)
    mode = " — teaching mode" if cfg["mode"] == "teach" else ""
    print(paint(BOLD + ";" + CYAN, f"ygo-agent — deck: {profile.name} ({len(profile.main)} main / "
                                   f"{len(profile.extra)} extra), backend: {backends.label(profile_cfg)}"
                                   f"{' — ' + detail if detail else ''}{mode}"))
    print(paint(DIM, f"{len(db.cards)} cards loaded from {len(db.db_paths)} databases."))
    if web_on(cfg):
        start_panel(cfg, db)
    try:
        join.play(Runtime(cfg, db, profile), brain_only=args.brain_only)
    except OSError as e:
        sys.exit(str(e))
    except (KeyboardInterrupt, EOFError):
        print()


def start_panel(cfg, db):
    """Serve the web panel in the background (the agent's seats publish to it) and print where it is."""
    from .agent.gamelog import paint, BOLD, CYAN
    from .match import MatchError, ensure_panel
    try:
        srv = ensure_panel(cfg, db)
    except MatchError as e:
        sys.exit(str(e))
    print(paint(BOLD + ";" + CYAN, f"Web panel: {srv.url}"))
    if cfg["web"].get("open_browser"):
        import webbrowser
        webbrowser.open(srv.url)
    return srv


def cmd_decks(args, cfg):
    from . import decks
    from .agent.gamelog import paint, BOLD, DIM, RED, YELLOW
    rows = decks.listing(cfg)
    print(paint(BOLD, "Deck profiles") + paint(DIM, f"  (repo: {decks.short(decks.repo_dir())}, "
                                                    f"user: {decks.short(decks.user_dir(cfg))})"))
    if not rows:
        print("  none")
        return 0
    head = f"  {'deck':<14} {'where':<5} {'playbook':>9} {'rules':>5} {'tests':>5}  ydk"
    print(paint(DIM, head))
    for r in rows:
        size = f"{r['playbook_bytes'] / 1024:.1f} KB" if r["playbook_bytes"] else "none"
        rules = "?" if r["rules"] is None else str(r["rules"])
        ydk = decks.short(r["ydk"]) if r["ydk"] else r.get("error", "?")
        if r["ydk"] and not r["ydk_ok"]:
            ydk += " (missing)"
        name = r["key"] + (f" ({r['name']})" if r["name"].lower() != r["key"].lower() else "")
        line = f"  {name:<14} {r['location']:<5} {size:>9} {rules:>5} {r['tests']:>5}  {ydk}"
        clash = r.get("clash")
        if clash == "clash":
            line = paint(RED, line + "  ← in both deck dirs: rename one, or set [decks] prefer")
        elif clash == "shadowed":
            line = paint(DIM, line + "  (shadowed: [decks] prefer)")
        elif not r["ydk_ok"]:
            line = paint(YELLOW, line)
        print(line)
    return 0


def cmd_web(args, cfg):
    import os
    import threading
    from .agent.gamelog import paint, DIM
    from .web import demo
    db = load_db(cfg)
    if args.demo and not os.path.isfile(os.path.join(args.demo, "game.jsonl")):
        sys.exit(f"{args.demo} is not a game log folder (no game.jsonl)")
    srv = start_panel(cfg, db)
    if args.demo:
        demo.Demo(args.demo, db, speed=args.speed, loop=args.loop).start()
        print(paint(DIM, f"Demo: replaying {args.demo} at {args.speed:g}x speed as a live game. Ctrl+C stops."))
    else:
        games = len(srv.panel.library.names())
        print(paint(DIM, f"{games} recorded game(s) in {srv.panel.library.games_dir}. Live games show up in the "
                         "panel of the process that plays them (play/teach/coach --web). Ctrl+C stops."))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print()
    finally:
        srv.stop()


# ---- arena-hosted commands: play, selfplay, teach ----

def room_options(args, cfg):
    """run_games() keywords for the room options shared by play, selfplay and teach."""
    arena = cfg.get("arena", {})
    return {"rules": cfg["duel"]["rules"], "best_of": args.best_of, "seed": args.seed, "pace": args.pace,
            "port": cfg["room"]["port"], "password": cfg["room"].get("password", ""),
            "lan": not args.no_lan and arena.get("lan", True),
            "time_limit": args.time_limit if args.time_limit is not None else arena.get("time_limit", 600),
            "room_name": arena.get("room_name", "ygo-agent"), "web": web_on(cfg),
            "web_port": cfg["web"].get("port")}


def run_match(cfg, db, a, b, header, **kw):
    """Print the header, play, print the summary. A web panel is started first, so its address comes first."""
    from .agent.gamelog import paint, BOLD, CYAN, DIM
    from .match import MatchError, run_games
    print(paint(BOLD + ";" + CYAN, header))
    if kw.get("web"):
        start_panel(cfg, db)
    try:
        run = run_games(a, b, cfg=cfg, db=db, **kw)
    except MatchError as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        print()
        return None
    for line in run.summary_lines():
        print(line)
    if run.interrupted:
        print(paint(DIM, "(stopped early with Ctrl+C)"))
    if kw.get("web") and run.games and sys.stdin.isatty():
        from .match import wait_for_enter
        try:
            wait_for_enter(paint(DIM, f"The web panel stays up at {run.web_url} to look back at the games. "
                                      "Press Enter to quit. "))
        except (KeyboardInterrupt, EOFError):
            print()
    return run


def cmd_play_arena(args, cfg):
    """play: the arena hosts a room, the agent sits in it, and the user joins from EDOPro."""
    from .agent.gamelog import paint, DIM
    from .match import SeatSpec
    if args.teach:
        sys.exit("--teach goes with --join (the legacy flow). For the arena-hosted version of teaching, run "
                 "`ygo-agent teach`; to be coached while you play, `ygo-agent coach`.")
    cfg["mode"] = "play"
    profile_cfg = check_backend(cfg)
    db, profile = load_deck(cfg)
    detail = backends.describe(profile_cfg)
    ai = SeatSpec("agent", deck=profile.key if not profile.adhoc else profile.ydk, backend=profile_cfg["name"],
                  name=args.name or cfg["bot"]["name"])
    opts = room_options(args, cfg)
    header = (f"ygo-agent play — deck: {profile.name} ({len(profile.main)} main / {len(profile.extra)} extra), backend: "
              f"{backends.label(profile_cfg)}{' — ' + detail if detail else ''}; rules {opts['rules']}, best of "
              f"{opts['best_of']}")
    print(paint(DIM, f"{len(db.cards)} cards loaded from {len(db.db_paths)} databases."))
    run_match(cfg, db, ai, SeatSpec("human"), header, games=args.games, **opts)


def cmd_selfplay(args, cfg):
    from .match import MatchError, SeatSpec
    try:
        a = SeatSpec.parse(args.a) if args.a else SeatSpec("agent", deck=cfg["deck"], backend=cfg["agent"]["backend"])
        b = SeatSpec.parse(args.b)
    except MatchError as e:
        sys.exit(f"error: {e}")
    db = load_db(cfg)
    opts = room_options(args, cfg)
    if not args.spectate and not any(s.kind == "human" for s in (a, b)):
        opts["port"] = None  # a free port for a WindBot-only room
    stack = {k: v.split(",") for k, v in (("A", args.stack_a), ("B", args.stack_b)) if v}
    where = "in a room you can spectate" if args.spectate else (
        "through the arena" if any(s.kind != "agent" for s in (a, b)) else "in-process")
    header = (f"ygo-agent selfplay — A {a} vs B {b}: {args.games} match(es), best of {args.best_of}, rules "
              f"{opts['rules']}{f', {args.parallel} at a time' if args.parallel > 1 else ''}, {where}"
              + (f", pace {args.pace:g}s" if args.pace else ""))
    run_match(cfg, db, a, b, header, games=args.games, parallel=args.parallel, spectate=args.spectate,
              quiet=args.quiet, first=None if args.first is None else "ab".index(args.first), stack=stack,
              out=args.out, timeout=args.timeout, **opts)


def cmd_teach_arena(args, cfg):
    """teach: the agent plays a duel (against a WindBot deck AI by default) and explains every play; the user
    watches as a spectator in EDOPro and/or in the web panel."""
    from .match import MatchError, SeatSpec
    cfg["mode"] = "teach"
    profile_cfg = check_backend(cfg)
    db, profile = load_deck(cfg)
    try:
        opponent = SeatSpec.parse(args.opponent)
    except MatchError as e:
        sys.exit(f"error: {e}")
    teacher = SeatSpec("agent", deck=profile.key if not profile.adhoc else profile.ydk, backend=profile_cfg["name"],
                       mode="teach", name=args.name or cfg["bot"]["name"])
    opts = room_options(args, cfg)
    header = (f"ygo-agent teach — {profile.name} on {backends.label(profile_cfg)} explains its plays against "
              f"{opponent}; rules {opts['rules']}. Watch as a spectator in EDOPro"
              + (" or in the web panel." if opts["web"] else " (add --web for the browser panel)."))
    run_match(cfg, db, teacher, opponent, header, games=args.games, spectate=True, **opts)


def check_backend(cfg):
    """The active backend profile, after checking it can run here (exits with the reason if not)."""
    profile = backend(cfg)
    try:
        backends.check(profile)
    except backends.BackendError as e:
        sys.exit(str(e))
    return profile


def cmd_replay(args, cfg):
    from .agent import replay
    cfg["chat"] = "off"
    check_backend(cfg)
    if args.tests is not None:
        return run_tests(args, cfg, args.tests)
    if not args.game_dir or args.decision is None:
        sys.exit("give a game folder and a decision number, or --tests")
    deck = args.deck or replay.game_deck(args.game_dir, cfg)
    db, profile = load_deck(cfg, deck)
    replay.replay_one(args.game_dir, args.decision, cfg, db, profile, save=args.save,
                      expect=json.loads(args.expect) if args.expect else None,
                      reject=json.loads(args.reject) if args.reject else None, note=args.note)
    return 0


def run_tests(args, cfg, names):
    """Cases of --deck (or the configured deck); named cases are looked up in every deck unless --deck is given."""
    from . import decks as deck_dirs
    from .agent import replay
    cfg["chat"] = "off"
    check_backend(cfg)
    decks = [args.deck] if args.deck else (deck_dirs.keys(cfg) if names else [cfg["deck"]])
    try:
        cases = replay.case_paths(decks, names, cfg)
    except deck_dirs.DeckError as e:
        sys.exit(str(e))
    db = load_db(cfg)
    profiles = {}

    def profile_for(key):
        if key not in profiles:
            profiles[key] = load_profile(cfg, db, key)
        return profiles[key]
    if args.ablate_rules:
        from .agent import ablation
        for key in decks:
            ablation.ablate(profile_for(key), cfg, db, args.repeat)
        return 0
    return replay.run_tests(cases, cfg, db, profile_for, args.repeat)


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parser().parse_args(argv)
    if args.cmd == "doctor":  # loads the config itself, so a broken config is a finding rather than an exit
        from .doctor import main as doctor
        sys.exit(doctor(args))
    try:
        cfg = configure(args)
    except ConfigError as e:
        sys.exit(f"config error: {e}")
    if args.cmd == "play" and not args.join:
        return cmd_play_arena(args, cfg)
    if args.cmd == "teach" and not args.join:
        return cmd_teach_arena(args, cfg)
    if args.cmd == "selfplay":
        return cmd_selfplay(args, cfg)
    if args.cmd in ("play", "teach"):
        return cmd_play(args, cfg)
    if args.cmd == "replay":
        sys.exit(cmd_replay(args, cfg))
    if args.cmd == "test":
        sys.exit(run_tests(args, cfg, args.names))
    if args.cmd == "web":
        return cmd_web(args, cfg)
    if args.cmd == "decks":
        sys.exit(cmd_decks(args, cfg))
    if getattr(args, "handler", None):  # subcommands that register themselves (bench)
        return args.handler(args, cfg)


if __name__ == "__main__":
    main()
