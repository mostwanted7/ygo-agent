"""Training games: the player against the opponent pool (WindBot deck AIs by default), alternating who goes first.

    problems = check_pool(["windbot:Blue-Eyes", "windbot:Dragunity"], engine, db, rules="mr3")
    record = play_game(spec, opponent, seed=..., first=True, cfg=..., out=...)

A WindBot deck AI is in the pool only if its bots.json entry allows the rules (Master Rule 3) and its deck has no Link
monsters. Who goes first is what the schedule says (run_games' `first`, in rooms with a WindBot as in-process).
"""

from __future__ import annotations

import os
import re

from ..match import MatchError, SeatSpec, run_games

LINK = 0x4000000


def bot_deck_file(windbot, bot) -> str | None:
    """The .ydk a WindBot deck AI plays (bots.json names don't always match the file: "Blue-Eyes" → AI_BlueEyes)."""
    decks = os.path.join(windbot.assets, "Decks")
    if not os.path.isdir(decks):
        return None
    wanted = {re.sub(r"[^a-z0-9]", "", f"ai_{bot.deck}".lower()), re.sub(r"[^a-z0-9]", "", f"ai_{bot.name}".lower())}
    roman = {"viii": "8", "vii": "7", "vi": "6", "v": "5", "iv": "4", "iii": "3"}
    for w in list(wanted):
        for r, n in roman.items():
            if w.endswith(r):
                wanted.add(w[: -len(r)] + n)
    for f in sorted(os.listdir(decks)):
        if f.lower().endswith(".ydk") and re.sub(r"[^a-z0-9]", "", f[:-4].lower()) in wanted:
            return os.path.join(decks, f)
    return None


def check_pool(specs: list[str], engine, db, rules: str = "mr3") -> tuple[list[str], list[str]]:
    """(usable specs, problems). Non-WindBot specs (heuristic:<deck>, <deck>:<backend>) pass through."""
    from ..agent.profile import parse_ydk
    from ..arena.windbot import WindBotError, WindBotInstall, mono_path
    ok, problems = [], []
    rule_no = int(m.group(1)) if (m := re.fullmatch(r"mr(\d)", str(rules).lower())) else None
    windbot = None
    for text in specs:
        try:
            spec = SeatSpec.parse(text)
        except MatchError as e:
            problems.append(f"{text}: {e}")
            continue
        if spec.kind == "human":
            problems.append(f"{text}: a human can't be a training opponent")
            continue
        if spec.kind != "windbot":
            ok.append(text)
            continue
        if mono_path() is None:
            problems.append(f"{text}: WindBot opponents need mono")
            continue
        try:
            windbot = windbot or WindBotInstall.find(engine.install.root)
            bot = windbot.resolve(spec.deck)
        except WindBotError as e:
            problems.append(f"{text}: {e}")
            continue
        if rule_no and bot.master_rules and rule_no not in bot.master_rules:
            problems.append(f"{text}: plays Master Rule {'/'.join(map(str, bot.master_rules))}, not {rule_no}")
            continue
        path = bot_deck_file(windbot, bot)
        if path and rule_no is not None and rule_no < 4:
            main, extra, side = parse_ydk(path)
            links = sorted({db.name(c) for c in main + extra if db.get(c) and db.get(c).type & LINK})
            if links:
                problems.append(f"{text}: its deck has Link monsters ({', '.join(links[:3])}), not legal under "
                                f"Master Rule {rule_no}")
                continue
        ok.append(text)
    return ok, problems


def play_game(player: SeatSpec, opponent: str, *, seed: int, first: bool | None, cfg: dict, db, engine, out: str,
              rules: str = "mr3", echo: str = "key", timeout: float = 5400) -> dict:
    """One game; returns its record (result for the player, first, turns, the player's log folder and stats)."""
    opp = SeatSpec.parse(opponent)
    run = run_games(player, opp, games=1, rules=rules, seed=seed, cfg=cfg, db=db, engine=engine, out=out,
                    echo=(echo, "off"), tags=False, lan=False, port=None, bind="127.0.0.1", timeout=timeout,
                    first=None if first is None else (0 if first else 1))
    if not run.games:
        raise MatchError("the game didn't finish" + (" (interrupted)" if run.interrupted else ""))
    g = run.games[0]
    me = g.seats[0]
    stats = me.stats or {}
    return {"result": me.result, "first": g.first == 0, "turns": g.turns, "reason": g.reason,
            "seconds": g.seconds, "log": me.log_dir, "replay": g.replay, "stats": stats,
            "cost": stats.get("cost_usd") or 0.0, "opponent": opponent, "retries": g.retries,
            "lua_errors": g.lua_errors, "backend": me.backend}


def opponent_text(spec: str) -> str:
    s = SeatSpec.parse(spec)
    if s.kind == "windbot":
        return f"WindBot's {s.deck} deck AI"
    return f"{s.deck or 'the default deck'} ({s.backend or 'default backend'})"
