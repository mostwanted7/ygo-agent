"""Native seat vs WindBot bridge: the same game through both paths, decision by decision.

    python tests/native/parity.py --games 5 [--seed 1] [--deck saffira] [--opponent Blackwing]

1. Bridge game: the WindBot fork (deck Agent, Brain= this process's bridge server, heuristic backend with the
   heuristic fallback) plays seat 0 of an arena room; an in-process random policy plays seat 1.
2. Shadow replay: the recorded game is re-simulated on the core with a native AgentSeat (same heuristic profile)
   on WindBot's team. Every prompt is turned into a native decision and asked to the agent, but the response the
   bridge game gave is the one played, so the whole game is compared even after the policies disagree. For each
   decision: kind, option count, option and question text (describe.py), state text, the bridge's choice against
   the bridge response decoded with the native option mapping (ordering/semantics), and the heuristic's native
   choice against the bridge's choice (policy-level parity).
3. Free run: the native seat plays the same deal (same core seed and deck order, same opponent policy) on its
   own; if every choice matches, the response streams are identical (the same game).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import contextlib
import copy
import difflib
import io
import json
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ygo_agent.agent import bridge_server  # noqa: E402
from ygo_agent.agent.carddb import CardDB  # noqa: E402
from ygo_agent.agent.describe import Describer  # noqa: E402
from ygo_agent.agent.profile import Profile  # noqa: E402
from ygo_agent.arena import server as S  # noqa: E402
from ygo_agent.arena.deck import load_ydk  # noqa: E402
from ygo_agent.arena.duel import Duel, DuelConfig, Pending  # noqa: E402
from ygo_agent.arena.messages import decode_cards  # noqa: E402
from ygo_agent.arena.native_seat import AgentSeat  # noqa: E402
from ygo_agent.arena.policies import RandomPolicy  # noqa: E402
from ygo_agent.arena.replay import parse_replay  # noqa: E402
from ygo_agent.arena.seats import PolicySeat, SeatFeed, SeatView  # noqa: E402
from ygo_agent.arena.windbot import BotInfo, WindBotInstall, WindBotProcess  # noqa: E402
from ygo_agent.config import load_config  # noqa: E402

BOT = "WB-Agent"


def agent_config(games_dir: str) -> dict:
    cfg = load_config(local=None, overrides={"games_dir": games_dir, "chat": "off"})
    cfg["agent"]["backend"] = "heuristic"
    cfg["agent"]["fallback"] = "heuristic"
    return cfg


def bridge_game(engine, seed: int, deck: str, opponent: str, work: str, db) -> dict:
    """Play one game WindBot(bridge, heuristic) vs a random policy through the arena; return what parity needs."""
    cfg = agent_config(os.path.join(work, "bridge"))
    profile = Profile(deck, db, cfg)
    runtime = bridge_server.Runtime(cfg, db, profile)
    srv = bridge_server.listen(0)
    port = srv.getsockname()[1]
    threading.Thread(target=bridge_server.serve, args=(srv, runtime), daemon=True).start()
    install = WindBotInstall.find(engine.install.root, prefer_fork=True)
    if not install.is_fork:
        raise RuntimeError("the WindBot fork isn't built (./build.sh)")
    opp_deck = load_ydk(os.path.join(engine.install.deck_dir, f"{opponent}.ydk"), engine.cards).deck

    async def scenario():
        room = S.Room(engine, S.RoomConfig(duel=DuelConfig(rules="mr3"), max_matches=1, rematch=False, seed=seed,
                                           lan_discovery=False, reserved={0: BOT}, time_limit=0))
        room.add_local(1, PolicySeat("Random AI", RandomPolicy(seed)), opp_deck)
        server = S.ArenaServer(room, "127.0.0.1", 0)
        await server.start()
        bot = WindBotProcess(install, BotInfo("Agent", "Agent"), BOT, server.port, version=room.version.as_int,
                             cdb_paths=engine.install.cdb_paths, scratch=os.path.join(work, f"wb-{seed}"),
                             extra_args={"DeckFile": profile.ydk, "Brain": f"127.0.0.1:{port}"}).start()
        try:
            await asyncio.wait_for(room.finished.wait(), 300)
        finally:
            await server.close()
            bot.stop()
        return room
    with contextlib.redirect_stdout(io.StringIO()):
        room = asyncio.run(scenario())
    srv.close()
    (duel, result), = room.games
    team = room.team_positions.index(0)
    games = sorted(d for d in os.listdir(cfg["games_dir"]) if d != "latest" and not d.startswith("windbot"))
    jsonl = os.path.join(cfg["games_dir"], games[-1], "game.jsonl")
    records = [json.loads(line) for line in open(jsonl, encoding="utf-8")]
    return {"replay": parse_replay(duel.replay.yrpx()), "team": team, "records": records, "result": result,
            "responses": list(duel.replay.responses), "seed": seed, "deck": deck, "opponent": opponent}


class ShadowSeat(AgentSeat):
    """A native seat that asks its agent as usual but plays the recorded response."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.forced: bytes | None = None
        self.log: list[dict] = []

    def _answer(self, prompt, decision, d, reply, retry):
        self.log.append({"decision": d, "agent": reply.get("choice") if reply else None,
                         "played": decision.decode(self.forced)})
        return self.forced


def deal(replay, observers=()):
    old = replay.old
    flags = old.duel_flags
    config = DuelConfig(rules=flags & ~0x10, extra_flags=flags & 0x10, lp=old.start_lp, start_hand=old.start_hand,
                        draw_count=old.draw_count, shuffle=not flags & 0x10, max_retries=0)
    names = (old.names[0][0] if old.names[0] else "", old.names[1][0] if old.names[1] else "")
    return config, names, old


def shadow_game(engine, game: dict, db, work: str) -> list[dict]:
    cfg = agent_config(os.path.join(work, "shadow"))
    seat = ShadowSeat(BOT, cfg, db, Profile(game["deck"], db, cfg), dict(cfg["backends"]["heuristic"],
                                                                         name="heuristic"), cards=engine.cards)
    seat.trace = []
    team = game["team"]
    config, names, old = deal(game["replay"])
    from ygo_agent.arena.deck import Deck
    duel = Duel(engine, config, (Deck(), Deck()), names, core_seed=old.seed, observers=[SeatFeed(seat, team)],
                insertion_order=(old.decks[0], old.decks[1]))
    seat.bind(SeatView(duel, team))
    with contextlib.redirect_stdout(io.StringIO()):
        step = duel.start()
        responses = iter(old.responses)
        while isinstance(step, Pending):
            data = next(responses, None)
            if data is None:
                break
            if step.team == team:
                seat.forced = data
                seat.choose(step.message, step.retry)
            step = duel.respond(data)
        seat.close()
    duel.close()
    game["native_events"] = [m for m in seat.trace if m["t"] == "event"]
    return seat.log


def free_game(engine, game: dict, db, work: str) -> list[bytes]:
    cfg = agent_config(os.path.join(work, "free"))
    seat = AgentSeat(BOT, cfg, db, Profile(game["deck"], db, cfg), dict(cfg["backends"]["heuristic"],
                                                                        name="heuristic"), cards=engine.cards)
    team = game["team"]
    other = PolicySeat("Random AI", RandomPolicy(game["seed"]))
    config, names, old = deal(game["replay"])
    from ygo_agent.arena.deck import Deck
    seats = {team: seat, 1 - team: other}
    duel = Duel(engine, config, (Deck(), Deck()), names, core_seed=old.seed, observers=[SeatFeed(seat, team)],
                insertion_order=(old.decks[0], old.decks[1]))
    for t, s in seats.items():
        s.bind(SeatView(duel, t))
    with contextlib.redirect_stdout(io.StringIO()):
        step = duel.start()
        while isinstance(step, Pending) and duel.responses < 20000:
            step = duel.respond(seats[step.team].choose(step.message, step.retry))
        seat.close()
    out = list(duel.replay.responses)
    duel.close()
    return out


def same_response(a: bytes, b: bytes) -> bool:
    """Byte-equal, or the same card list in another of the core's list encodings (WindBot sends SELECT_SUM
    picks as one-byte indices, the arena as four-byte ones)."""
    if a == b:
        return True
    try:
        return decode_cards(a, 256) == decode_cards(b, 256) and len(a) >= 8 and len(b) >= 8
    except Exception:
        return False


def same_option(d: dict, a, b) -> bool:
    opts = d.get("options", [])
    if not (a and b and len(a) == len(b) == 1 and all(0 <= k < len(opts) for k in a + b)):
        return False
    x, y = opts[a[0]], opts[b[0]]
    if not (isinstance(x, dict) and isinstance(y, dict)):
        return False
    key = lambda o: (o.get("a"), (o.get("card") or {}).get("id"), (o.get("card") or {}).get("uid"), o.get("desc"))
    return key(x) == key(y)


NATIVE_EVENTS = ("confirm", "equip", "swap", "counter", "coin", "dice", "declared", "room", "chat")
UNRELIABLE = ("att", "ov")                         # WindBot's own reconstruction of these is often wrong
NATIVE_ONLY = ("ctr", "sc", "blv", "own", "uid")    # fields only native seats send


def normalized(d: dict) -> dict:
    """A decision without the fields where the two paths differ for a known reason (see KNOWN in the report)."""
    d = copy.deepcopy(d)

    def fix(c):
        if isinstance(c, dict):
            for k in UNRELIABLE + NATIVE_ONLY:
                c.pop(k, None)
            if c.get("l") == 0x80:
                c["c"] = 0  # WindBot gives Xyz materials in a selection the raw player id as controller
            for v in c.values():
                fix(v)
        elif isinstance(c, list):
            for v in c:
                fix(v)
    fix(d)
    return d


def compare(game: dict, shadow: list[dict], free: list[bytes], db) -> dict:
    describer = Describer(db)
    bridge = [r["msg"] for r in game["records"] if r["kind"] == "decide"
              and r["msg"]["kind"] not in ("go_first", "game_over")]
    replies = {r["msg"]["id"]: r["msg"] for r in game["records"] if r["kind"] == "reply"}
    out = collections.Counter()
    diffs = collections.Counter()
    examples = {}
    details = []
    out["bridge_decisions"], out["native_decisions"] = len(bridge), len(shadow)
    for b, n in zip(bridge, shadow):
        d = n["decision"]
        out["compared"] += 1
        if b["kind"] != d["kind"]:
            diffs[f"kind {b['kind']} vs {d['kind']}"] += 1
            examples.setdefault("kind", (b["id"], b["kind"], d["kind"]))
            continue
        out["kind_match"] += 1
        bo, no = describer.options(b), describer.options(d)
        if len(b.get("options", [])) == len(d.get("options", [])):
            out["count_match"] += 1
        if bo == no:
            out["options_match"] += 1
        else:
            for x, y in zip(bo, no):
                if x != y:
                    key = f"option text ({b['kind']})"
                    diffs[key] += 1
                    examples.setdefault(key, (b["id"], x, y))
                    break
        if describer.question(b) == describer.question(d):
            out["question_match"] += 1
        else:
            diffs[f"question ({b['kind']})"] += 1
            examples.setdefault(f"question ({b['kind']})", (b["id"], describer.question(b), describer.question(d)))
        nb, nn = normalized(b), normalized(d)
        if describer.options(nb) == describer.options(nn) and describer.question(nb) == describer.question(nn):
            out["normalized_options_match"] += 1
        else:
            details.append(("normalized options", b, d, describer.options(nb), describer.options(nn)))
        if describer.state(nb["state"]) == describer.state(nn["state"]):
            out["normalized_state_match"] += 1
        else:
            x, y = describer.state(nb["state"]), describer.state(nn["state"])
            line = next(((a, c) for a, c in zip(x.splitlines(), y.splitlines()) if a != c), None)
            details.append(("normalized state", b, d, line and line[0], line and line[1]))
        sb, sn = describer.state(b["state"]), describer.state(d["state"])
        if sb == sn:
            out["state_match"] += 1
        else:
            for x, y in zip(sb.splitlines(), sn.splitlines()):
                if x != y:
                    key = "state: " + x.split(":")[0].split("(")[0].strip()[:30]
                    diffs[key] += 1
                    examples.setdefault(key, (b["id"], x, y))
                    break
        chosen = replies.get(b["id"], {}).get("choice")
        if b["kind"] == "select_unselect" and chosen:
            chosen = chosen[:1]
        if n["played"] == chosen:
            out["semantics_match"] += 1
        elif same_option(d, chosen, n["played"]):
            # The same card twice in one list (e.g. two Special Summon procedures): WindBot sends the card's last
            # index for both options (ClientCard.ActionIndex is per card), the native seat the one chosen.
            out["semantics_windbot_duplicate"] += 1
            diffs[f"duplicate option, WindBot sends the last index ({b['kind']})"] += 1
        else:
            key = f"decoded response != bridge choice ({b['kind']})"
            diffs[key] += 1
            examples.setdefault(key, (b["id"], chosen, n["played"]))
            details.append(("semantics", b, d, chosen, n["played"]))
        if n["agent"] == chosen:
            out["policy_match"] += 1
        else:
            key = f"heuristic choice differs ({b['kind']})"
            diffs[key] += 1
            examples.setdefault(key, (b["id"], chosen, n["agent"]))
            details.append(("policy", b, d, chosen, n["agent"]))
    # The event streams, as the agent reads them (native-only events left out).
    lines = []
    for events in ([r["msg"] for r in game["records"] if r["kind"] == "event"], game.get("native_events", [])):
        lines.append([t for t in (describer.event(e) for e in events if e["e"] not in NATIVE_EVENTS) if t])
    matcher = difflib.SequenceMatcher(None, *lines, autojunk=False)
    out["event_lines"], out["native_event_lines"] = len(lines[0]), len(lines[1])
    out["event_lines_match"] = sum(b.size for b in matcher.get_matching_blocks())
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "equal":
            key = f"event lines ({op})"
            diffs[key] += max(i2 - i1, j2 - j1)
            examples.setdefault(key, (lines[0][i1:i2][:3], lines[1][j1:j2][:3]))
    rec = game["responses"]
    same = 0
    for x, y in zip(rec, free):
        if not same_response(x, y):
            break
        same += 1
    out["free_same_prefix"], out["responses"], out["free_responses"] = same, len(rec), len(free)
    out["free_identical"] = int(same == len(rec) == len(free))
    return {"counts": dict(out), "diffs": dict(diffs), "examples": examples, "details": details}


def run(games: int, seed: int, deck: str, opponent: str, work: str | None = None) -> list[dict]:
    from ygo_agent.core import Engine
    engine = Engine.load()
    db = CardDB(load_config(local=None)["edopro_dir"])
    work = work or tempfile.mkdtemp(prefix="parity-")
    results = []
    for k in range(games):
        g = bridge_game(engine, seed + k, deck, opponent, os.path.join(work, f"g{k}"), db)
        shadow = shadow_game(engine, g, db, os.path.join(work, f"g{k}"))
        free = free_game(engine, g, db, os.path.join(work, f"g{k}"))
        r = compare(g, shadow, free, db)
        r["seed"], r["team"], r["turns"] = g["seed"], g["team"], g["result"].turns
        results.append(r)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--deck", default="saffira")
    ap.add_argument("--opponent", default="Blackwing")
    ap.add_argument("--work", default=None)
    ap.add_argument("-v", "--verbose", action="store_true", help="print every mismatched choice in full")
    args = ap.parse_args(argv)
    results = run(args.games, args.seed, args.deck, args.opponent, args.work)
    total, diffs = collections.Counter(), collections.Counter()
    for r in results:
        total.update(r["counts"])
        diffs.update(r["diffs"])
        print(json.dumps({"seed": r["seed"], "team": r["team"], "turns": r["turns"], **r["counts"]}))
    print("TOTAL", json.dumps(dict(total)))
    for k, v in diffs.most_common():
        print(f"  {v:5d}  {k}")
    for r in results:
        for k, ex in r["examples"].items():
            print(f"  e.g. seed {r['seed']} {k}: {ex}")
        if args.verbose:
            for what, b, d, chosen, other in r["details"]:
                print(f"--- seed {r['seed']} {what} #{b['id']} {b['kind']}: bridge {chosen}, native {other}")
                print("  bridge:", json.dumps({k: v for k, v in b.items() if k != "state"}))
                print("  native:", json.dumps({k: v for k, v in d.items() if k != "state"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
