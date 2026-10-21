"""The lab's opponent and stopwatch: a dummy that never acts, an observer that ends the duel after the player's turn
and records the end board, and the fixed board a going-second lab turn plays into.

    dummy = goldfish_seat()                                  # PolicySeat: ends every phase, passes every chain
    stop = TurnStop(player_team=0, last_turn=2, own_turn=1)  # board at turn 2, then the dummy's turn, stop at 3
    run_duel(engine, config, decks, (agent, dummy), observers=[stop], ...)
    stop.board, stop.after                                   # the end boards (LPs, the opponent's field too)
"""

from __future__ import annotations

from ..arena.duel import VIEW_TEAM0, DuelObserver, Placement, StartState
from ..arena.messages import (BattleAction, IdleAction, NewTurn, SelectBattleCmd, SelectCard, SelectChain,
                              SelectEffectYn, SelectIdleCmd, SelectOption, SelectYesNo)
from ..arena.policies import RandomPolicy
from ..arena.seats import PolicySeat
from ..core.constants import (LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND, LOCATION_MZONE, LOCATION_REMOVED,
                              LOCATION_SZONE, POS_FACEDOWN, POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
                              WIN_REASON_SURRENDERED)

DUMMY_NAME = "Lab dummy"
# The going-second lab board (core team 0's field; the dummy never activates its Set cards): a 3000-ATK boss, a
# face-down blocker and two Set traps. It asks "can this hand get through a typical turn-1 board?".
COMMON_BOARD = [
    ("Blue-Eyes White Dragon", 89631139, LOCATION_MZONE, 2, POS_FACEUP_ATTACK),
    ("Giant Soldier of Stone", 13039848, LOCATION_MZONE, 1, POS_FACEDOWN_DEFENSE),
    ("Mirror Force", 44095762, LOCATION_SZONE, 1, POS_FACEDOWN),
    ("Call of the Haunted", 97077563, LOCATION_SZONE, 2, POS_FACEDOWN),
]
COMMON_BOARD_TEXT = ("Blue-Eyes White Dragon (3000 ATK, face-up Attack), a face-down Defense Position monster (Giant "
                     "Soldier of Stone, 1300/2000) and two Set Spell/Trap cards (Mirror Force, Call of the Haunted) "
                     "that the dummy never activates; the opponent's LP is 8000")
POSITIONS = {0x1: "face-up Attack", 0x2: "face-down Attack", 0x4: "face-up Defense", 0x8: "face-down Defense"}


class GoldfishPolicy:
    """Never does anything it can avoid: ends the Main and Battle Phases, passes every chain, says no to every optional
    effect, and picks the minimum wherever the engine insists (hand-size discards, forced selections)."""

    def __init__(self, seed: int = 0):
        self.fallback = RandomPolicy(seed, pass_rate=1.0)

    def __call__(self, p, view) -> bytes:
        if isinstance(p, SelectIdleCmd):
            if p.can_end_phase:
                return p.respond(IdleAction.END)
            if p.can_battle_phase:
                return p.respond(IdleAction.BATTLE)
        elif isinstance(p, SelectBattleCmd):
            if p.can_end_phase:
                return p.respond(BattleAction.END)
            if p.can_main2:
                return p.respond(BattleAction.MAIN2)
        elif isinstance(p, SelectChain):
            return p.respond(0 if p.forced and p.chains else None)
        elif isinstance(p, (SelectEffectYn, SelectYesNo)):
            return p.respond(False)
        elif isinstance(p, SelectOption):
            return p.respond(0)
        elif isinstance(p, SelectCard):
            if p.min == 0 and p.cancelable:
                return p.respond(None)
            return p.respond(list(range(max(p.min, 1))))
        return self.fallback(p, view)


def goldfish_seat(name: str = DUMMY_NAME) -> PolicySeat:
    return PolicySeat(name, GoldfishPolicy(), go_first=True)


def common_board(team: int = 0) -> StartState:
    return StartState([Placement(team, code, loc, seq, pos) for _, code, loc, seq, pos in COMMON_BOARD])


class TurnStop(DuelObserver):
    """Ends the duel as soon as a turn after `last_turn` starts. `board` is the board when the player's turn
    (`own_turn`, default `last_turn`) is over, End Phase effects included; when the dummy's next turn is played too
    (last_turn > own_turn: it only passes, while the player can use Set cards and quick effects in its windows),
    `after` is the board when that turn is over. The duel can also end some other way (an OTK)."""
    views = frozenset({VIEW_TEAM0})

    def __init__(self, player_team: int, last_turn: int, cards=None, own_turn: int | None = None):
        self.player_team, self.last_turn, self.cards = player_team, last_turn, cards
        self.own_turn = last_turn if own_turn is None else own_turn
        self.duel = None
        self.board: dict | None = None
        self.after: dict | None = None
        self.stopped = False

    def on_start(self, duel) -> None:
        self.duel = duel
        self.cards = self.cards or duel.engine.cards

    def on_message(self, view, msg) -> None:
        if not isinstance(msg, NewTurn) or self.duel is None or self.stopped:
            return
        turn = self.duel.turn
        if turn == self.own_turn + 1 and self.board is None:
            self.board = snapshot(self.duel, self.player_team, self.cards)
        if turn > self.last_turn:
            self.stopped = True
            if self.last_turn > self.own_turn:
                self.after = snapshot(self.duel, self.player_team, self.cards)
            self.duel.end(self.player_team, WIN_REASON_SURRENDERED)

    def on_end(self, duel, result) -> None:
        if self.board is None:
            self.board = snapshot(duel, self.player_team, self.cards)


def describe_card(q, cards, zone: str) -> str:
    if q is None:
        return ""
    if not q.code:
        return "a face-down card" if zone != "hand" else "a card"
    name = cards.name(q.code) if cards else str(q.code)
    if zone not in ("mzone", "szone"):
        return name
    bits = []
    if q.position is not None:
        bits.append(POSITIONS.get(q.position & 0xF, f"position {q.position}"))
    if zone == "mzone":
        if q.attack is not None:
            bits.append(f"ATK {q.attack}/DEF {q.defense}")
        if q.rank:
            bits.append(f"Rank {q.rank}")
        elif q.level:
            bits.append(f"Lv{q.level}")
        if q.overlay_cards:
            bits.append(f"{len(q.overlay_cards)} material(s): " + ", ".join(
                cards.name(c) if cards else str(c) for c in q.overlay_cards))
    elif q.position is not None and q.position & POS_FACEDOWN:
        bits = ["Set"]
    return f"{name} ({', '.join(bits)})" if bits else name


def snapshot(duel, team: int, cards=None) -> dict:
    """The player's hand, field, GY, banished and Extra Deck count, the opponent's visible field, both LPs."""
    zones = (("hand", LOCATION_HAND), ("mzone", LOCATION_MZONE), ("szone", LOCATION_SZONE),
             ("gy", LOCATION_GRAVE), ("banished", LOCATION_REMOVED))
    out = {"turn": duel.turn}
    try:
        field = duel.field_state()
        out["lp"] = [field.players[team].lp, field.players[1 - team].lp]
    except Exception:
        out["lp"] = None
    me, opp = {}, {}
    for name, loc in zones:
        me[name] = [d for d in (describe_card(q, cards, name) for q in duel.view_location(team, team, loc)) if d]
    me["extra"] = duel.count(team, LOCATION_EXTRA)
    for name, loc in zones[1:3] + zones[3:4]:
        opp[name] = [d for d in (describe_card(q, cards, name) for q in duel.view_location(team, 1 - team, loc))
                     if d]
    opp["hand"] = duel.count(1 - team, LOCATION_HAND)
    out["me"], out["opp"] = me, opp
    return out


def board_text(board: dict | None) -> str:
    if not board:
        return "(no end board recorded)"
    me, opp = board["me"], board["opp"]
    lines = [f"Your field: {', '.join(me['mzone']) or 'no monsters'}; Spell/Trap Zones: "
             f"{', '.join(me['szone']) or 'empty'}",
             f"Your hand ({len(me['hand'])}): {', '.join(me['hand']) or 'empty'}",
             f"Your GY: {', '.join(me['gy']) or 'empty'}" + (f"; banished: {', '.join(me['banished'])}"
                                                             if me['banished'] else ""),
             f"Extra Deck left: {me['extra']}"]
    if opp.get("mzone") or opp.get("szone") or opp.get("gy"):
        lines.append(f"Opponent's field: {', '.join(opp['mzone']) or 'no monsters'}; Spell/Trap Zones: "
                     f"{', '.join(opp['szone']) or 'empty'}; GY: {', '.join(opp['gy']) or 'empty'}")
    if board.get("lp"):
        lines.append(f"LP: you {board['lp'][0]}, opponent {board['lp'][1]}")
    return "\n".join(lines)
