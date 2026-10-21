"""Who receives what. Each case mirrors a branch of GenericDuel::Sending (or one of the documented
hardenings); the audit at the bottom checks the property on real games: no player ever receives a card code
of the opponent's hidden cards."""

import struct

import pytest

from ygo_agent.arena import visibility as V
from ygo_agent.arena.buffer import LocInfo
from ygo_agent.core.constants import (LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND,
                                      LOCATION_MZONE, LOCATION_OVERLAY, LOCATION_SZONE, POS_FACEDOWN,
                                      POS_FACEDOWN_DEFENSE, POS_FACEUP, POS_FACEUP_ATTACK, Msg)

CODE = 89631139


def loc(c, l, s=0, p=0):
    return LocInfo(c, l, s, p).pack()


def move(code, prev, cur):
    return bytes([Msg.MOVE]) + struct.pack("<I", code) + prev + cur + struct.pack("<I", 0)


def to(route, audience):
    got = route.for_audience(audience)
    assert len(got) <= 1
    return got[0] if got else None


def code_of(data):
    return struct.unpack_from("<I", data, 1)[0]


def test_move_to_hand_hides_the_code_from_opponent_and_spectators():
    r = V.route(move(CODE, loc(0, LOCATION_DECK, 0, POS_FACEDOWN_DEFENSE), loc(0, LOCATION_HAND, 2, 10)))
    assert code_of(to(r, V.TEAM0)) == CODE
    assert code_of(to(r, V.TEAM1)) == 0 and code_of(to(r, V.SPECTATORS)) == 0
    assert r.cache == to(r, V.SPECTATORS) and r.record


def test_move_to_grave_or_face_up_is_public():
    for cur in (loc(1, LOCATION_GRAVE, 0, POS_FACEUP), loc(1, LOCATION_MZONE, 2, POS_FACEUP_ATTACK),
                loc(1, LOCATION_OVERLAY | LOCATION_MZONE, 0, 1)):
        r = V.route(move(CODE, loc(1, LOCATION_HAND, 0, 10), cur))
        assert code_of(to(r, V.TEAM0)) == CODE


def test_move_face_down_to_field_is_hidden():
    r = V.route(move(CODE, loc(1, LOCATION_HAND, 0, 10), loc(1, LOCATION_SZONE, 1, POS_FACEDOWN_DEFENSE)))
    assert code_of(to(r, V.TEAM1)) == CODE and code_of(to(r, V.TEAM0)) == 0


def test_set_is_hidden_from_everyone_but_recorded_in_full():
    raw = bytes([Msg.SET]) + struct.pack("<I", CODE) + loc(0, LOCATION_SZONE, 1, POS_FACEDOWN_DEFENSE)
    r = V.route(raw)
    assert all(code_of(d) == 0 for _, d in r.sends) and r.record


def test_draw_strips_face_down_cards_for_others():
    raw = bytes([Msg.DRAW, 1]) + struct.pack("<I", 2) + struct.pack("<II", CODE, 10) + struct.pack("<II", 7, 5)
    r = V.route(raw)
    assert to(r, V.TEAM1) == raw
    other = to(r, V.TEAM0)
    assert struct.unpack_from("<IIII", other, 6) == (0, 10, 7, 5)   # face-up draws stay visible
    assert to(r, V.SPECTATORS) == other


def test_shuffle_hand_codes_only_for_owner():
    raw = bytes([Msg.SHUFFLE_HAND, 0]) + struct.pack("<III", 2, CODE, 7)
    r = V.route(raw)
    assert to(r, V.TEAM0) == raw
    assert struct.unpack_from("<II", to(r, V.TEAM1), 6) == (0, 0)


def test_face_down_special_summon():
    raw = bytes([Msg.SPSUMMONING]) + struct.pack("<I", CODE) + loc(0, LOCATION_MZONE, 1, POS_FACEDOWN_DEFENSE)
    r = V.route(raw)
    assert code_of(to(r, V.TEAM0)) == CODE and code_of(to(r, V.TEAM1)) == 0
    up = bytes([Msg.SPSUMMONING]) + struct.pack("<I", CODE) + loc(0, LOCATION_MZONE, 1, POS_FACEUP_ATTACK)
    assert code_of(to(V.route(up), V.TEAM1)) == CODE


def confirm(player, cards):
    body = b"".join(struct.pack("<IBBI", code, con, l, seq) for code, con, l, seq in cards)
    return bytes([Msg.CONFIRM_CARDS, player]) + struct.pack("<I", len(cards)) + body


def test_confirm_from_deck_is_private_to_the_viewer():
    r = V.route(confirm(1, [(CODE, 1, LOCATION_DECK, 30)]))
    assert to(r, V.TEAM1) and not to(r, V.TEAM0) and not to(r, V.SPECTATORS) and r.cache is None


def test_confirm_hand_is_public_and_extra_mixed_is_private():
    assert to(V.route(confirm(0, [(CODE, 1, LOCATION_HAND, 0)])), V.SPECTATORS)
    mixed = V.route(confirm(0, [(CODE, 1, LOCATION_HAND, 0), (7, 0, LOCATION_EXTRA, 3)]))
    assert to(mixed, V.TEAM0) and not to(mixed, V.TEAM1)   # stricter than EDOPro (first card only)


@pytest.mark.parametrize("kind,team0,team1,spec,record", [
    (1, True, False, False, False), (2, True, False, False, False), (3, True, False, False, False),
    (5, True, False, False, False), (4, False, True, True, True), (6, False, True, True, True),
    (8, False, True, True, True), (11, False, True, True, True), (10, True, True, True, True),
    (200, True, False, False, True), (99, False, False, False, True),
])
def test_hint_routing(kind, team0, team1, spec, record):
    r = V.route(bytes([Msg.HINT, kind, 0]) + struct.pack("<Q", 1))
    assert (bool(to(r, V.TEAM0)), bool(to(r, V.TEAM1)), bool(to(r, V.SPECTATORS))) == (team0, team1, spec)
    assert r.record == record and r.cache is None


def test_prompt_goes_to_its_player_with_waiting_for_the_other():
    raw = bytes([Msg.SELECT_YESNO, 1]) + struct.pack("<Q", 30)
    r = V.route(raw)
    assert to(r, V.TEAM1) == raw and to(r, V.TEAM0) == V.WAITING
    assert not to(r, V.SPECTATORS) and not r.record and r.prompt_team == 1


def test_select_card_hides_opponent_cards_even_face_up():
    cards = [(CODE, loc(0, LOCATION_HAND, 0, 10)), (7, loc(1, LOCATION_MZONE, 0, POS_FACEUP_ATTACK))]
    raw = bytes([Msg.SELECT_CARD, 0, 0]) + struct.pack("<III", 1, 1, 2) + \
        b"".join(struct.pack("<I", c) + l for c, l in cards)
    out = to(V.route(raw), V.TEAM0)
    assert struct.unpack_from("<I", out, 15)[0] == CODE and struct.unpack_from("<I", out, 29)[0] == 0


def test_select_unselect_and_tribute_strip_both_lists():
    entry = struct.pack("<I", 7) + loc(1, LOCATION_MZONE, 0, 1)
    raw = bytes([Msg.SELECT_UNSELECT_CARD, 0, 1, 0]) + struct.pack("<III", 1, 1, 1) + entry + \
        struct.pack("<I", 1) + entry
    out = to(V.route(raw), V.TEAM0)
    assert struct.unpack_from("<I", out, 16)[0] == 0 and struct.unpack_from("<I", out, 34)[0] == 0
    trib = bytes([Msg.SELECT_TRIBUTE, 0, 0]) + struct.pack("<III", 1, 1, 1) + struct.pack("<IBBIB", 7, 1, 4, 0, 1)
    assert struct.unpack_from("<I", to(V.route(trib), V.TEAM0), 15)[0] == 0


def test_select_sum_hides_only_opponent_face_down_cards():
    def item(code, con, pos):
        return struct.pack("<I", code) + loc(con, LOCATION_MZONE, 0, pos) + struct.pack("<I", 4)
    raw = bytes([Msg.SELECT_SUM, 0, 0]) + struct.pack("<III", 8, 1, 2) + struct.pack("<I", 0) + \
        struct.pack("<I", 3) + item(1, 0, POS_FACEDOWN_DEFENSE) + item(2, 1, POS_FACEDOWN_DEFENSE) + \
        item(3, 1, POS_FACEUP_ATTACK)
    out = to(V.route(raw), V.TEAM0)
    codes = [struct.unpack_from("<I", out, 23 + 18 * i)[0] for i in range(3)]
    assert codes == [1, 0, 3]


def test_pos_change_between_face_down_positions_hides_code():
    raw = bytes([Msg.POS_CHANGE]) + struct.pack("<I", CODE) + bytes([1, LOCATION_MZONE, 0, 0x8, 0x2])
    r = V.route(raw)
    assert code_of(to(r, V.TEAM1)) == CODE and code_of(to(r, V.TEAM0)) == 0
    flip = bytes([Msg.POS_CHANGE]) + struct.pack("<I", CODE) + bytes([1, LOCATION_MZONE, 0, 0x8, 0x1])
    assert code_of(to(V.route(flip), V.TEAM0)) == CODE


def test_swap_hides_face_down_codes_from_non_controllers():
    raw = bytes([Msg.SWAP]) + struct.pack("<I", CODE) + loc(0, LOCATION_MZONE, 0, POS_FACEDOWN_DEFENSE) + \
        struct.pack("<I", 7) + loc(1, LOCATION_MZONE, 1, POS_FACEUP_ATTACK)
    r = V.route(raw)
    assert code_of(to(r, V.TEAM0)) == CODE and code_of(to(r, V.TEAM1)) == 0
    assert struct.unpack_from("<I", to(r, V.TEAM1), 15)[0] == 7


def test_missed_effect_and_match_kill():
    raw = bytes([Msg.MISSED_EFFECT]) + loc(1, LOCATION_MZONE, 0, 1) + struct.pack("<I", CODE)
    r = V.route(raw)
    assert to(r, V.TEAM1) and not to(r, V.TEAM0)
    kill = bytes([Msg.MATCH_KILL]) + struct.pack("<I", CODE)
    assert not V.route(kill).sends and V.route(kill, best_of=3).sends


def test_default_messages_go_to_everyone_and_the_cache():
    raw = bytes([Msg.NEW_TURN, 0])
    r = V.route(raw)
    assert r.sends == [(V.EVERYONE, raw)] and r.cache == raw


def test_refresh_plans_match_generic_duel():
    from ygo_agent.core.constants import REFRESH_HAND, REFRESH_MZONE, REFRESH_SINGLE
    idle = V.pre_refreshes(bytes([Msg.SELECT_IDLECMD, 0]))
    assert [(r.controller, r.location) for r in idle] == [(0, 4), (1, 4), (0, 8), (1, 8), (0, 2), (1, 2)]
    assert idle[0].flags == REFRESH_MZONE and idle[4].flags == REFRESH_HAND
    end = V.post_refreshes(bytes([Msg.CHAIN_END]))
    assert end[0].replay_only and end[0].location == LOCATION_DECK and len(end) == 8
    mv = V.post_refreshes(move(CODE, loc(0, LOCATION_HAND, 1, 10), loc(0, LOCATION_MZONE, 3, 1)))
    assert mv == [V.Refresh(0, LOCATION_MZONE, REFRESH_SINGLE, 3)]
    assert V.post_refreshes(move(CODE, loc(0, LOCATION_MZONE, 1, 1), loc(0, LOCATION_MZONE, 3, 1))) == []
    assert V.post_refreshes(move(CODE, loc(0, LOCATION_MZONE, 1, 1), loc(0, LOCATION_OVERLAY | 4, 3, 0))) == []


# --- the audit on real games -----------------------------------------------------------------------------

class FairnessAudit:
    """Checks every message a duelist receives for codes of cards that duelist may not know."""

    def __init__(self):
        from ygo_agent.arena.duel import VIEW_SPECTATOR, VIEW_TEAM0, VIEW_TEAM1
        self.views = frozenset({VIEW_TEAM0, VIEW_TEAM1, VIEW_SPECTATOR})
        self.problems = []
        self.checked = 0

    def on_start(self, duel):
        pass

    def on_prompt(self, team, prompt, retry):
        self.on_message(team, prompt)

    def on_response(self, *a):
        pass

    def on_end(self, *a):
        pass

    def fail(self, view, msg, why):
        self.problems.append((view, msg.name, why))

    def on_message(self, view, msg):
        from ygo_agent.arena import messages as M
        from ygo_agent.arena.query import CardQuery
        me = view if view in (0, 1) else None
        self.checked += 1

        def secret(con, location, position):
            if con == me:
                return False
            if location & LOCATION_OVERLAY:
                return False
            if location & (LOCATION_DECK | LOCATION_HAND | LOCATION_EXTRA):
                return not position & POS_FACEUP
            if location & (LOCATION_MZONE | LOCATION_SZONE):
                return bool(position & POS_FACEDOWN)
            return False

        def check_query(con, location, q: CardQuery | None):
            if q is None or con == me or not q.code:
                return
            if q.is_public or (q.position or 0) & POS_FACEUP:
                return
            self.fail(view, msg, f"query reveals {q.code} at p{con} loc {location:#x}")

        if isinstance(msg, M.Move) and msg.code and secret(msg.current.controller, msg.current.location,
                                                            msg.current.position):
            self.fail(view, msg, "move reveals a hidden destination")
        elif isinstance(msg, M.Draw) and msg.player != me and any(c and not p & POS_FACEUP for c, p in msg.cards):
            self.fail(view, msg, "opponent draw revealed")
        elif isinstance(msg, (M.ShuffleHand, M.ShuffleExtra)) and msg.player != me and any(msg.codes):
            self.fail(view, msg, "opponent shuffle revealed")
        elif isinstance(msg, M.SetCard) and msg.code:
            self.fail(view, msg, "set card revealed")
        elif isinstance(msg, M.SpSummoning) and msg.code and secret(msg.location.controller, msg.location.location,
                                                                     msg.location.position):
            self.fail(view, msg, "face-down summon revealed")
        elif isinstance(msg, M.UpdateData):
            for q in msg.cards:
                check_query(msg.player, msg.location, q)
        elif isinstance(msg, M.UpdateCard):
            check_query(msg.player, msg.location, msg.card)
        elif isinstance(msg, (M.SelectCard, M.SelectUnselectCard, M.SelectTribute)):
            refs = msg.cards if not isinstance(msg, M.SelectUnselectCard) else msg.selectable + msg.selected
            if any(r.code and r.controller != me for r in refs):
                self.fail(view, msg, "selection shows an opponent card code")
        elif isinstance(msg, M.ConfirmCards) and msg.player != me and any(
                c.location in (LOCATION_DECK, LOCATION_EXTRA) for c in msg.cards):
            self.fail(view, msg, "someone else's deck confirmation")
        elif isinstance(msg, M.Hint) and msg.hint_type in (1, 2, 3, 5) and msg.player != me:
            self.fail(view, msg, "private hint")
        elif isinstance(msg, M.Prompt) and msg.player != me:
            self.fail(view, msg, "someone else's prompt")


@pytest.mark.integration
def test_fairness_on_real_games(engine, decks):
    from ygo_agent.arena.duel import DuelConfig
    from ygo_agent.arena.policies import RandomPolicy
    from ygo_agent.arena.runner import run_duel
    from ygo_agent.arena.seats import PolicySeat
    audit = FairnessAudit()
    for seed in range(12):
        pair = (decks["Saffira"], decks["Blackwing"]) if seed % 2 else (decks["Blackwing"], decks["Saffira"])
        duel = run_duel(engine, DuelConfig(rules="mr3" if seed % 3 else "mr5"), pair,
                        (PolicySeat("a", RandomPolicy(seed, pass_rate=0.3)),
                         PolicySeat("b", RandomPolicy(seed + 50, pass_rate=0.3))), seed=seed, observers=[audit])
        duel.close()
    assert audit.checked > 10000
    assert audit.problems == []
