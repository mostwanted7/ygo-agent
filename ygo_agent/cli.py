"""ygo-agent: command line.

    ygo-agent play --join          # host a LAN room in EDOPro, the agent's bot joins it
    ygo-agent play --join --brain-only
    ygo-agent teach                # the bot plays and explains every decision for a spectator
    ygo-agent copilot              # you choose every move in this terminal, the agent recommends
    ygo-agent replay games/latest 14 [--save NAME --expect '[[2]]' --note "..."]
    ygo-agent test [NAME ...]      # re-run saved regression cases
    ygo-agent web [--demo games/<dir> --speed 2]   # the web panel: recorded games, or one replayed live
"""

import argparse
import json
import sys

from . import backends
from .config import ConfigError, load_config, backend


def add_common(p):
    p.add_argument("--deck", help="deck profile: a folder under decks/ (default from the config)")
    p.add_argument("--backend", help="backend profile: a [backends.NAME] table in the config (e.g. opus, sonnet, "
                                     "api-opus, local, heuristic, random)")
    p.add_argument("--model", help="override the backend's model (e.g. opus, sonnet, qwen3:14b)")
    p.add_argument("--effort", help="override the backend's effort level (low, medium, high, xhigh, max)")
    p.add_argument("--edopro-dir", help="EDOPro install folder")
    p.add_argument("--games-dir", help="where game logs go")
    p.add_argument("--rules", help="rules stated when the room doesn't report them (e.g. MR3, MR5)")
    p.add_argument("--config", metavar="FILE", help="use FILE instead of config.local.toml")


def add_bot(p):
    p.add_argument("--brain-only", action="store_true",
                   help="run only the brain server (start the bot yourself; the command is printed)")
    p.add_argument("--host", help="room address (default from the config)")
    p.add_argument("--port", type=int, help="room port (default from the config)")
    p.add_argument("--password", help="room password")
    p.add_argument("--name", help="the bot's player name in EDOPro")
    p.add_argument("--brain-port", type=int, help="local port for the bot ⇄ agent bridge")
    p.add_argument("--chat", choices=("banter", "off"), help="in-duel chat: a few jokes, or none")
    p.add_argument("--web", action="store_true", default=None,
                   help="also serve the web panel (board, reasoning, feedback box) on http://127.0.0.1:7930/")
    p.add_argument("--web-port", type=int, help="port for the web panel (default from the config)")


def parser():
    ap = argparse.ArgumentParser(prog="ygo-agent", description="LLM-driven Yu-Gi-Oh! players for EDOPro.")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    p = sub.add_parser("play", help="duel the agent")
    p.add_argument("--join", action="store_true",
                   help="the bot joins the LAN room you host in EDOPro (the only way to play for now)")
    p.add_argument("--teach", action="store_true", help="explain every decision for someone learning the deck")
    p.add_argument("--copilot", action="store_true",
                   help="you make the decisions in this terminal, the agent recommends (implies --teach)")
    add_bot(p)
    add_common(p)

    p = sub.add_parser("teach", help="the agent plays and explains every decision; watch as a spectator")
    add_bot(p)
    add_common(p)

    p = sub.add_parser("copilot", help="you pilot the deck from this terminal, the agent recommends each move")
    add_bot(p)
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

    p = sub.add_parser("test", help="re-run saved regression cases (decks/<deck>/tests)")
    p.add_argument("names", nargs="*", metavar="NAME", help="case names (default: every case of the deck)")
    p.add_argument("--repeat", type=int, default=3, help="runs per case (the model isn't deterministic)")
    add_common(p)

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


def mode_of(args):
    if args.cmd in ("teach", "copilot"):
        return args.cmd
    if getattr(args, "copilot", False):
        return "copilot"
    return "teach" if getattr(args, "teach", False) else "play"


def load_db(cfg):
    from .agent.carddb import CardDB
    db = CardDB(cfg["edopro_dir"])
    if not db.cards:
        sys.exit(f"No EDOPro card databases found in {db.root} (set edopro_dir in config.local.toml or --edopro-dir).")
    return db


def load_profile(cfg, db, key=None):
    from .agent.profile import Profile
    try:
        return Profile(key or cfg["deck"], db, cfg)
    except FileNotFoundError as e:
        sys.exit(str(e))


def load_deck(cfg, key=None):
    db = load_db(cfg)
    return db, load_profile(cfg, db, key)


def cmd_play(args, cfg):
    import os
    from . import paths, join
    from .agent.bridge_server import Runtime
    from .agent.gamelog import paint, BOLD, CYAN, DIM

    if args.cmd == "play" and not args.join:
        sys.exit("Arena-hosted play (the agent hosts, you join from EDOPro) isn't available yet.\n"
                 "Use `ygo-agent play --join`: you host a LAN room in EDOPro and the bot joins it.")
    cfg["mode"] = mode_of(args)
    if cfg["mode"] == "copilot":
        cfg["chat"] = "off"
    profile_cfg = check_backend(cfg)
    if not args.brain_only and not os.path.exists(paths.WINDBOT_EXE):
        sys.exit(f"{paths.WINDBOT_EXE} is missing — run ./build.sh first.")
    os.makedirs(paths.resolve(cfg["games_dir"]), exist_ok=True)
    db, profile = load_deck(cfg)
    detail = backends.describe(profile_cfg)
    mode = {"copilot": " — COPILOT: you choose, the agent recommends", "teach": " — teaching mode"}.get(cfg["mode"], "")
    print(paint(BOLD + ";" + CYAN, f"ygo-agent — deck: {profile.name} ({len(profile.main)} main / "
                                   f"{len(profile.extra)} extra), backend: {backends.label(profile_cfg)}"
                                   f"{' — ' + detail if detail else ''}{mode}"))
    print(paint(DIM, f"{len(db.cards)} cards loaded from {len(db.db_paths)} databases."))
    if cfg["web"].get("enabled"):
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
    from .web import server
    try:
        srv = server.start(cfg, db)
    except OSError as e:
        sys.exit(str(e))
    print(paint(BOLD + ";" + CYAN, f"Web panel: {srv.url}"))
    if cfg["web"].get("open_browser"):
        import webbrowser
        webbrowser.open(srv.url)
    return srv


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
                         "panel of the process that plays them (play/teach/copilot --web). Ctrl+C stops."))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print()
    finally:
        srv.stop()


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
    deck = args.deck or replay.game_deck(args.game_dir)
    db, profile = load_deck(cfg, deck)
    replay.replay_one(args.game_dir, args.decision, cfg, db, profile, save=args.save,
                      expect=json.loads(args.expect) if args.expect else None,
                      reject=json.loads(args.reject) if args.reject else None, note=args.note)
    return 0


def run_tests(args, cfg, names):
    """Cases of --deck (or the configured deck); named cases are looked up in every deck unless --deck is given."""
    from .agent import replay
    from .agent.profile import deck_keys
    cfg["chat"] = "off"
    check_backend(cfg)
    decks = [args.deck] if args.deck else (deck_keys() if names else [cfg["deck"]])
    cases = replay.case_paths(decks, names)
    db = load_db(cfg)
    profiles = {}

    def profile_for(key):
        if key not in profiles:
            profiles[key] = load_profile(cfg, db, key)
        return profiles[key]
    return replay.run_tests(cases, cfg, db, profile_for, args.repeat)


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parser().parse_args(argv)
    try:
        cfg = configure(args)
    except ConfigError as e:
        sys.exit(f"config error: {e}")
    if args.cmd in ("play", "teach", "copilot"):
        return cmd_play(args, cfg)
    if args.cmd == "replay":
        sys.exit(cmd_replay(args, cfg))
    if args.cmd == "test":
        sys.exit(run_tests(args, cfg, args.names))
    if args.cmd == "web":
        return cmd_web(args, cfg)


if __name__ == "__main__":
    main()
