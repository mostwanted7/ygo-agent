"""`python -m ygo_agent.arena`: host EDOPro rooms, run WindBot or in-process games headlessly, inspect replays."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time

from ..core import Engine, InstallError
from ..core.constants import RULES, WIN_REASON_NAMES
from .deck import (AllowedCards, Deck, DeckRules, check_deck, deck_problems, find_banlist, find_deck, load_banlists,
                   load_ydk)
from .duel import DuelConfig
from .gamelog import DEFAULT_OUT, REPO_ROOT, GameLog, game_dir, write_result
from .policies import POLICIES
from .runner import replay_duel, run_match
from .seats import PolicySeat

log = logging.getLogger("ygo_agent.arena")
ALLOWED = {"ocg": AllowedCards.OCG_ONLY, "tcg": AllowedCards.TCG_ONLY, "ocg-tcg": AllowedCards.OCG_TCG,
           "prerelease": AllowedCards.WITH_PRERELEASE, "any": AllowedCards.ANY}


def _engine(args) -> Engine:
    try:
        return Engine.load(args.edopro)
    except InstallError as e:
        sys.exit(f"error: {e}")


def _deck(engine: Engine, ref: str, rules: DeckRules, label: str) -> Deck:
    dirs = [engine.install.deck_dir, os.path.join(REPO_ROOT, "decks")]
    try:
        path = find_deck(ref, dirs)
    except FileNotFoundError as e:
        sys.exit(f"error: {e}")
    loaded = load_ydk(path, engine.cards)
    problems = deck_problems(loaded.deck, engine.cards, rules, loaded.unknown)
    for p in problems:
        print(f"warning: {label} deck {loaded.deck.name}: {p}", file=sys.stderr)
    err = check_deck(loaded.deck, engine.cards, rules, loaded.unknown)
    if err:
        sys.exit(f"error: {label} deck {path} is not legal here: {err}")
    return loaded.deck


def _stack(engine: Engine, spec: str | None) -> list[int]:
    if not spec:
        return []
    try:
        return [engine.cards.resolve(part.strip()) for part in spec.split(",") if part.strip()]
    except KeyError as e:
        sys.exit(f"error: --stack-hand: {e.args[0]}")


def _duel_config(args) -> DuelConfig:
    return DuelConfig(rules=args.rules, lp=args.lp, start_hand=args.start_hand, draw_count=args.draw,
                      max_retries=args.retries)


def _deck_rules(args, engine: Engine, config: DuelConfig) -> DeckRules:
    banlist = None
    if getattr(args, "lflist", None):
        try:
            banlist = find_banlist(load_banlists(engine.install.lflist_paths), args.lflist)
        except KeyError as e:
            sys.exit(f"error: {e.args[0]}")
    return DeckRules(check_size=not args.no_check_deck, check_content=not args.no_check_deck,
                     forbidden_types=config.forbidden_types, banlist=banlist,
                     allowed=ALLOWED[getattr(args, "allowed", "any")])


def _summary(names, records) -> str:
    wins = [0, 0, 0]
    for rec in records:
        wins[2 if rec["winner_seat"] is None else rec["winner_seat"]] += 1
    return f"{names[0]} {wins[0]} - {wins[1]} {names[1]}" + (f" ({wins[2]} draws)" if wins[2] else "")


# --- selfplay-direct -----------------------------------------------------------------------------------------

def cmd_selfplay(args) -> int:
    engine = _engine(args)
    config = _duel_config(args)
    config.record_replay = not args.no_replay
    rules = _deck_rules(args, engine, config)
    decks = (_deck(engine, args.deck0, rules, "seat 0"), _deck(engine, args.deck1, rules, "seat 1"))
    stack = {0: _stack(engine, args.stack_hand0), 1: _stack(engine, args.stack_hand1)}
    out = None if args.no_output else game_dir(args.out, f"direct_{decks[0].name}-vs-{decks[1].name}")
    names = (f"{decks[0].name} ({args.policy0})", f"{decks[1].name} ({args.policy1})")
    records, failures, t0 = [], 0, time.perf_counter()
    for i in range(args.games):
        seed = None if args.seed is None else args.seed + i
        seats = (PolicySeat(names[0], POLICIES[args.policy0](None if seed is None else seed * 2)),
                 PolicySeat(names[1], POLICIES[args.policy1](None if seed is None else seed * 2 + 1)))
        observers = []
        if out and not args.no_log:
            observers.append(GameLog(os.path.join(out, f"game-{i + 1:03d}.log"), engine.cards))

        def on_game(rec, duel, i=i):
            if out and duel.replay is not None:
                with open(os.path.join(out, f"game-{i + 1:03d}.yrpX"), "wb") as f:
                    f.write(rec.replay)
        match = run_match(engine, config, decks, seats, best_of=1, seed=seed, first=args.first, stack=stack,
                          observers=observers, on_game=on_game)
        for o in observers:
            o.close()
        g = match.games[0]
        r = g.result
        bad = r.retries or r.lua_errors
        failures += bool(bad)
        records.append({"game": i + 1, "seed": g.seed, "first_seat": g.first, "winner_seat": g.winner_seat,
                        "reason": WIN_REASON_NAMES.get(r.reason, r.reason), "turns": r.turns,
                        "responses": r.responses, "retries": r.retries, "lua_errors": r.lua_errors,
                        "seconds": round(g.seconds, 3)})
        if not args.quiet:
            who = "draw" if g.winner_seat is None else names[g.winner_seat]
            print(f"game {i + 1}: {who} wins ({WIN_REASON_NAMES.get(r.reason, r.reason)}) in {r.turns} turns, "
                  f"{r.responses} responses, {r.retries} retries, {len(r.lua_errors)} lua errors, "
                  f"{g.seconds:.2f}s")
    elapsed = time.perf_counter() - t0
    print(f"{args.games} games in {elapsed:.1f}s ({elapsed / max(args.games, 1):.2f}s/game): "
          f"{_summary(names, records)}; {failures} with retries or Lua errors")
    if out:
        with open(os.path.join(out, "results.json"), "w") as f:
            json.dump({"names": names, "games": records}, f, indent=2)
        print(f"logs and replays: {out}")
    return 1 if failures else 0


# --- host / bots -----------------------------------------------------------------------------------------------

def _seat_spec(spec: str) -> tuple[str, str]:
    kind, _, arg = spec.partition(":")
    kind = kind.lower()
    if kind not in ("human", "windbot", "ai"):
        raise argparse.ArgumentTypeError(f"seat must be human, windbot:<deck AI> or ai:<policy>, got {spec!r}")
    if kind == "ai" and arg not in POLICIES:
        raise argparse.ArgumentTypeError(f"ai policy must be one of {', '.join(POLICIES)}")
    if kind == "windbot" and not arg:
        raise argparse.ArgumentTypeError("windbot seat needs a deck AI name, e.g. windbot:Blue-Eyes")
    return kind, arg


async def _host(args, engine: Engine, seats: list[tuple[str, str]], max_matches: int | None, rematch: bool,
                label: str) -> int:
    from .server import ArenaServer, Room, RoomConfig, RoomObserver
    from .windbot import WindBotInstall, WindBotProcess, WindBotError
    config = _duel_config(args)
    rules = _deck_rules(args, engine, config)
    banlist = rules.banlist
    out = game_dir(args.out, label)
    reserved, local, bots = {}, {}, []
    install = None
    for pos, (kind, arg) in enumerate(seats):
        if kind == "windbot":
            try:
                install = install or WindBotInstall.find(engine.install.root, prefer_fork=not args.stock_windbot)
                bot = install.resolve(arg)
            except WindBotError as e:
                sys.exit(f"error: {e}")
            name = f"{bot.name} AI" if seats.count((kind, arg)) == 1 else f"{bot.name} AI {pos + 1}"
            reserved[pos] = name[:19]
            bots.append((pos, bot, name[:19]))
        elif kind == "ai":
            deck_ref = getattr(args, f"deck{pos}")
            if not deck_ref:
                sys.exit(f"error: seat {pos} is ai:{arg}; give it a deck with --deck{pos}")
            local[pos] = (PolicySeat(f"{arg.capitalize()} AI", POLICIES[arg](args.seed)),
                          _deck(engine, deck_ref, rules, f"seat {pos}"))
    stack = {pos: _stack(engine, getattr(args, f"stack_hand{pos}")) for pos in (0, 1)}
    rc = RoomConfig(name=args.name, password=args.password, duel=config, best_of=args.best_of,
                    time_limit=args.time_limit, check_deck_size=not args.no_check_deck,
                    check_deck_content=not args.no_check_deck, allowed=ALLOWED[args.allowed], banlist=banlist,
                    rematch=rematch, max_matches=max_matches, seed=args.seed, stack={k: v for k, v in stack.items() if v},
                    reserved=reserved, lan_discovery=not args.no_lan)
    room = Room(engine, rc)
    for pos, (seat, deck) in local.items():
        room.add_local(pos, seat, deck)
    records = []

    class Recorder(RoomObserver):
        def on_join(self, p):
            print(f"{p.name} joined ({'spectator' if p.pos is None or p.pos >= 2 else f'seat {p.pos}'})", flush=True)

        def on_chat(self, p, text):
            print(f"[chat] {p.name if p else 'system'}: {text}", flush=True)

        def on_game_end(self, room, duel, result):
            n = len(records) + 1
            write_result(out, duel)
            os.replace(os.path.join(out, "result.json"), os.path.join(out, f"game-{n:03d}.json"))
            if duel.replay:
                with open(os.path.join(out, f"game-{n:03d}.yrpX"), "wb") as f:
                    f.write(duel.replay.yrpx())
            first_pos = room.team_positions[0]
            winner = None if result.is_draw else room.team_positions[result.winner]
            records.append({"game": n, "seed": duel.seed, "first_seat": first_pos, "winner_seat": winner,
                            "names": [room.slots[i].name if room.slots[i] else "?" for i in (0, 1)],
                            "reason": WIN_REASON_NAMES.get(result.reason, result.reason), "turns": result.turns,
                            "responses": result.responses, "retries": result.retries,
                            "lua_errors": result.lua_errors})
            who = "draw" if winner is None else duel.names[result.winner]
            print(f"game {n}: {who} wins ({WIN_REASON_NAMES.get(result.reason, result.reason)}) in "
                  f"{result.turns} turns, {result.responses} responses, {result.retries} retries", flush=True)

        def on_deck_rejected(self, p, error):
            print(f"{p.name}'s deck was rejected: {error}", file=sys.stderr, flush=True)
            if p.name in reserved.values():  # a WindBot won't fix its deck: give up instead of waiting
                failed.append(f"{p.name}'s deck is not legal under these rules ({error})")
                room.finished.set()

    failed: list[str] = []
    room.room_observers.append(Recorder())
    if not args.no_log:
        room.duel_observer_factory = lambda room, index: [GameLog(os.path.join(out, f"game-{index + 1:03d}.log"),
                                                                  engine.cards)]
    server = ArenaServer(room, args.bind, args.port)
    try:
        await server.start()
    except OSError as e:
        sys.exit(f"error: cannot listen on {args.bind or '*'}:{args.port}: {e}")
    print(f"arena room {args.name!r} on port {server.port} ({RULES[args.rules].description}, "
          f"best of {args.best_of}); join from EDOPro: LAN → Host address 127.0.0.1, port {server.port}",
          flush=True)
    procs: list[WindBotProcess] = []

    def launch(index: int) -> WindBotProcess:
        pos, bot, name = bots[index]
        p = WindBotProcess(install, bot, name, server.port, version=room.version.as_int,
                           cdb_paths=engine.install.cdb_paths,
                           scratch=os.path.join(out, f"windbot-{pos}-{room.matches_played + 1}"))
        p.start()
        print(f"started WindBot {bot.name} as {name!r} (pid {p.pid})", flush=True)
        return p

    try:
        procs += [launch(i) for i in range(len(bots))]

        async def watch_bots():
            """Fail fast when a WindBot can't play (it would leave the room waiting forever); start a new one
            when the room reopens after a match it left."""
            while not room.finished.is_set():
                await asyncio.sleep(1.0)
                if room.stage.value != "lobby":
                    continue
                for i, (pos, _bot, name) in enumerate(bots):
                    p = procs[i]
                    if room.slots[pos] is not None or p.running():
                        continue
                    problem = p.problem()
                    if problem or room.matches_played == 0:
                        failed.append(f"WindBot {name} can't play: {problem or 'exited'} (see {p.log_path})")
                        room.finished.set()
                    else:
                        procs[i] = launch(i)
        watcher = asyncio.get_running_loop().create_task(watch_bots())
        await server.serve(timeout=args.timeout)
        watcher.cancel()
    except asyncio.TimeoutError:
        print(f"timed out after {args.timeout}s in stage {room.stage.value}", file=sys.stderr)
    finally:
        for p in procs:
            p.stop()
            crash = p.crash_log()
            if crash:
                print(f"WindBot {p.name} crash.log:\n{crash[-2000:]}", file=sys.stderr)
    for msg in failed:
        print(f"error: {msg}", file=sys.stderr)
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump({"games": records}, f, indent=2)
    if records:
        names = records[-1]["names"]
        print(f"{len(records)} games: {_summary(names, records)}; logs and replays: {out}")
    bad = sum(1 for r in records if r["retries"] or r["lua_errors"])
    return 1 if bad or not records else 0


def cmd_host(args) -> int:
    engine = _engine(args)
    seats = [args.seat0, args.seat1]
    label = "host_" + "-vs-".join(a or k for k, a in seats)
    return asyncio.run(_host(args, engine, seats, args.games, rematch=True, label=label))


def cmd_bots(args) -> int:
    engine = _engine(args)
    seats = [("windbot", args.deck_a), ("windbot", args.deck_b)]
    args.best_of = 1
    if args.timeout is None:
        args.timeout = 120 + 180 * args.games
    return asyncio.run(_host(args, engine, seats, args.games, rematch=True,
                             label=f"bots_{args.deck_a}-vs-{args.deck_b}"))


# --- small commands -------------------------------------------------------------------------------------

def cmd_list_bots(args) -> int:
    from .windbot import WindBotInstall, WindBotError
    engine = _engine(args)
    try:
        install = WindBotInstall.find(engine.install.root, prefer_fork=not args.stock_windbot)
    except WindBotError as e:
        sys.exit(f"error: {e}")
    print(f"WindBot: {install.exe}{' (fork)' if install.is_fork else ''}")
    for b in install.bots():
        print(f"  {b.name:28} deck {b.deck:22} {b.description}")
    return 0


def cmd_replay_info(args) -> int:
    from .replay import read_replay, streams_match
    rep = read_replay(args.file)
    kind = "yrpX (streamed)" if rep.is_streamed else "yrp (old)"
    print(f"{args.file}: {kind}, version {rep.header.version}, flags {rep.header.flag:#x}, "
          f"duel flags {rep.duel_flags:#x}")
    print(f"  players: {', '.join(rep.names[0])} vs {', '.join(rep.names[1])}")
    if rep.is_streamed:
        print(f"  {len(rep.packets)} messages, {rep.turns} turns, embedded yrp: {rep.embedded is not None}")
    old = rep.old
    if old:
        print(f"  decks: {[(len(m), len(e)) for m, e in old.decks]}, {len(old.responses)} responses, "
              f"seed {list(old.seed)}")
    if args.resimulate:
        engine = _engine(args)
        duel = replay_duel(engine, rep)
        ours = duel.replay.packets
        theirs = rep.packets
        same = sum(1 for a, b in zip(ours, theirs) if a == b)
        print(f"  re-simulated: {len(ours)} messages, {same} identical to the file's stream"
              + (f" (file has {len(theirs)})" if rep.is_streamed else ""))
        if rep.is_streamed:
            verdict = "same game" if streams_match(ours, theirs) or streams_match(ours, theirs[:len(ours)]) \
                else "DIFFERENT game"
            print(f"  verdict: {verdict}")
        duel.close()
    return 0


# --- argument parsing ------------------------------------------------------------------------------------------

def _common_duel(p: argparse.ArgumentParser) -> None:
    p.add_argument("--rules", default="mr3", choices=sorted(RULES), help="duel rules (default mr3)")
    p.add_argument("--lp", type=int, default=8000)
    p.add_argument("--start-hand", type=int, default=5)
    p.add_argument("--draw", type=int, default=1, help="cards drawn per turn")
    p.add_argument("--seed", type=int, default=None, help="make games reproducible")
    p.add_argument("--retries", type=int, default=1, help="invalid responses tolerated per prompt")
    p.add_argument("--stack-hand0", metavar="CARDS", help="comma-separated card names/codes put on top of "
                   "seat 0's deck (the first 5 are its opening hand)")
    p.add_argument("--stack-hand1", metavar="CARDS", help="same for seat 1")
    p.add_argument("--no-check-deck", action="store_true", help="skip deck size and content checks")
    p.add_argument("--out", default=None, help=f"output directory (default {DEFAULT_OUT})")
    p.add_argument("--no-log", action="store_true", help="don't write per-game logs")


def _common_host(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=7911)
    p.add_argument("--bind", default=None, help="address to listen on (default: all, IPv4 and IPv6)")
    p.add_argument("--name", default="ygo-agent arena", help="room name shown in EDOPro's LAN list")
    p.add_argument("--password", default="")
    p.add_argument("--time-limit", type=int, default=600,
                   help="seconds per player per turn, as in EDOPro (0 = none; in-process AI seats are exempt)")
    p.add_argument("--allowed", default="any", choices=sorted(ALLOWED), help="card pool")
    p.add_argument("--lflist", default=None, help="banlist name (from EDOPro's lflists), default none")
    p.add_argument("--no-lan", action="store_true", help="don't answer EDOPro's LAN room search")
    p.add_argument("--timeout", type=float, default=None, help="give up after this many seconds")
    p.add_argument("--stock-windbot", action="store_true", help="use EDOPro's WindBot, not the fork build")
    p.add_argument("--deck0", help="deck for an ai seat at position 0 (path or EDOPro deck name)")
    p.add_argument("--deck1", help="deck for an ai seat at position 1")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m ygo_agent.arena", description=__doc__)
    ap.add_argument("--edopro", default=None, help="EDOPro install directory (default ~/Games/ProjectIgnis)")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("host", help="host a room EDOPro clients can join (LAN → host address)")
    p.add_argument("--seat0", type=_seat_spec, default=("human", ""), help="human | windbot:<deck AI> | ai:<policy>")
    p.add_argument("--seat1", type=_seat_spec, default=("windbot", "Blue-Eyes"))
    p.add_argument("--best-of", type=int, default=1, choices=(1, 3, 5))
    p.add_argument("--games", type=int, default=None, help="close the room after this many matches")
    _common_duel(p)
    _common_host(p)
    p.set_defaults(func=cmd_host)

    p = sub.add_parser("bots", help="WindBot vs WindBot through the arena, headless")
    p.add_argument("--deck-a", default="Blue-Eyes", help="WindBot deck AI for seat 0")
    p.add_argument("--deck-b", default="Blackwing", help="WindBot deck AI for seat 1")
    p.add_argument("--games", type=int, default=1)
    _common_duel(p)
    _common_host(p)
    p.set_defaults(func=cmd_bots, port=0, time_limit=0)

    p = sub.add_parser("selfplay-direct", help="in-process policies straight on the core (fast)")
    p.add_argument("--deck0", default="Saffira")
    p.add_argument("--deck1", default="Blackwing")
    p.add_argument("--policy0", default="random", choices=sorted(POLICIES))
    p.add_argument("--policy1", default="random", choices=sorted(POLICIES))
    p.add_argument("--games", type=int, default=1)
    p.add_argument("--first", type=int, choices=(0, 1), default=None, help="seat that moves first (default RPS)")
    p.add_argument("--no-replay", action="store_true")
    p.add_argument("--no-output", action="store_true", help="write nothing to disk")
    p.add_argument("--quiet", action="store_true", help="only print the summary")
    p.add_argument("--lflist", default=None)
    p.add_argument("--allowed", default="any", choices=sorted(ALLOWED))
    _common_duel(p)
    p.set_defaults(func=cmd_selfplay)

    p = sub.add_parser("list-bots", help="WindBot deck AIs available as opponents")
    p.add_argument("--stock-windbot", action="store_true")
    p.set_defaults(func=cmd_list_bots)

    p = sub.add_parser("replay-info", help="summarize a .yrp/.yrpX (and optionally re-simulate it)")
    p.add_argument("file")
    p.add_argument("--resimulate", action="store_true", help="re-run it on the core and compare the stream")
    p.set_defaults(func=cmd_replay_info)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING - 10 * min(args.verbose, 2),
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    return args.func(args) or 0
