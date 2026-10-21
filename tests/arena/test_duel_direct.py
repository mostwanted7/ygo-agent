"""Direct-core games (no sockets): many seeds with random policies, stacking, custom starts, determinism."""

import time

import pytest

from ygo_agent.arena.duel import (VIEW_TEAM0, Duel, DuelConfig, DuelError, DuelObserver, Placement, StartState,
                                  stack_deck)
from ygo_agent.arena.messages import Draw
from ygo_agent.arena.policies import RandomPolicy, SimplePolicy
from ygo_agent.arena.runner import run_duel, run_match
from ygo_agent.arena.seats import PolicySeat, Seat
from ygo_agent.core.constants import LOCATION_GRAVE, LOCATION_HAND, LOCATION_MZONE, POS_FACEUP_ATTACK, Msg

pytestmark = pytest.mark.integration


def seats(seed, a=RandomPolicy, b=RandomPolicy):
    return PolicySeat("A", a(seed)), PolicySeat("B", b(seed + 7919))


@pytest.mark.parametrize("rules", ["mr3", "mr5"])
def test_many_random_games_end_cleanly(engine, decks, rules):
    pair = (decks["Saffira"], decks["Blackwing"])
    t0, n = time.perf_counter(), 24
    for seed in range(n):
        d = pair if seed % 2 else pair[::-1]
        duel = run_duel(engine, DuelConfig(rules=rules), d, seats(seed), seed=seed)
        r = duel.result
        assert r is not None and (r.reason in (0x1, 0x2) or r.reason >= 0x10 or r.is_draw), r
        assert r.retries == 0, f"seed {seed}: invalid response"
        assert r.lua_errors == [], f"seed {seed}: {r.lua_errors[:3]}"
        assert duel.replay.packets[-1][0] == Msg.WIN
        duel.close()
    per_game = (time.perf_counter() - t0) / n
    assert per_game < 1.0, f"{per_game:.2f}s per game"


def test_simple_policy_games(engine, decks):
    for seed in range(4):
        duel = run_duel(engine, DuelConfig(), (decks["Blackwing"], decks["Saffira"]),
                        seats(seed, SimplePolicy, SimplePolicy), seed=seed)
        assert duel.result.retries == 0 and not duel.result.lua_errors
        duel.close()


class DrawWatcher(DuelObserver):
    views = frozenset({VIEW_TEAM0, VIEW_TEAM0 + 1})

    def __init__(self):
        self.first = {}

    def on_message(self, view, msg):
        if isinstance(msg, Draw):
            self.first.setdefault((view, msg.player), msg)


def test_stacked_opening_hands(engine, decks):
    saffira, blackwing = decks["Saffira"], decks["Blackwing"]
    want0 = sorted(set(saffira.main), key=saffira.main.index)[:5]
    want1 = [blackwing.main[-1], blackwing.main[-2]]
    for seed in (1, 2, 3):
        watch = DrawWatcher()
        duel = run_duel(engine, DuelConfig(), (saffira, blackwing), seats(seed), seed=seed,
                        stack={0: want0, 1: want1}, observers=[watch])
        assert watch.first[0, 0].codes == want0
        assert watch.first[1, 1].codes[:2] == want1
        assert set(watch.first[1, 0].codes) == {0}      # the opponent only sees card backs
        duel.close()


def test_stack_rejects_cards_not_in_deck():
    with pytest.raises(DuelError):
        stack_deck([1, 2, 3], [4])
    with pytest.raises(DuelError):
        stack_deck([1, 2, 3], [1, 1])
    assert stack_deck([1, 2, 3, 2], [2, 3]) == [2, 3, 1, 2]


def test_same_seed_same_game(engine, decks):
    def play():
        duel = run_duel(engine, DuelConfig(), (decks["Saffira"], decks["Blackwing"]), seats(5), seed=99)
        out = list(duel.replay.packets)
        duel.close()
        return out
    from ygo_agent.arena.replay import streams_match
    assert streams_match(play(), play())


def test_seed_zero_and_simple_ai_are_rejected(engine, decks):
    with pytest.raises(ValueError):
        Duel(engine, DuelConfig(), (decks["Saffira"], decks["Blackwing"]), core_seed=(0, 0, 0, 0)).start()
    with pytest.raises(DuelError):
        Duel(engine, DuelConfig(extra_flags=0x40), (decks["Saffira"], decks["Blackwing"]))


def test_custom_start_state(engine, decks):
    saffira, blackwing = decks["Saffira"], decks["Blackwing"]
    monster = next(c for c in saffira.main if engine.cards.get(c).type & 1)
    state = StartState([Placement(0, monster, LOCATION_MZONE, 2, POS_FACEUP_ATTACK),
                        Placement(1, blackwing.main[0], LOCATION_GRAVE, 0)], start_hand=(5, 5))
    duel = Duel(engine, DuelConfig(), (saffira, blackwing), start_state=state, seed=4)
    step = duel.start()
    assert duel.pending is not None
    mz = duel.view_location(1, 0, LOCATION_MZONE)
    assert mz[2] is not None and mz[2].code == monster          # face-up: the opponent sees it
    assert duel.view_location(0, 1, LOCATION_GRAVE)[0].code == blackwing.main[0]
    assert duel.count(0, LOCATION_HAND) in (5, 6)
    assert any(p[0] == Msg.RELOAD_FIELD for p in duel.replay.packets)
    assert not duel.replay.old_replay_valid
    duel.close()
    del step


def test_seat_view_hides_opponent_hand_and_own_deck_order(engine, decks):
    duel = Duel(engine, DuelConfig(), (decks["Saffira"], decks["Blackwing"]), seed=3)
    duel.start()
    from ygo_agent.arena.seats import SeatView
    me = SeatView(duel, 0)
    assert all(c is not None and c.code for c in me.location(0, LOCATION_HAND))
    assert all(c is not None and not c.code for c in me.location(1, LOCATION_HAND))
    assert all(c is None for c in me.location(0, 0x1))           # own deck: only the count
    snap = me.snapshot()
    assert len(snap["me.hand"]) == 5 and len(snap["opp.hand"]) == 5
    duel.close()


class Chooser(Seat):
    def __init__(self, name, first):
        self.name, self.first, self.policy = name, first, RandomPolicy(len(name))

    def choose(self, prompt, retry):
        return self.policy(prompt, self.view)

    def go_first(self):
        return self.first


def test_best_of_three_match(engine, decks):
    games = []
    match = run_match(engine, DuelConfig(), (decks["Saffira"], decks["Blackwing"]),
                      (Chooser("A", True), Chooser("B", False)), best_of=3, seed=8,
                      on_game=lambda rec, duel: games.append(rec))
    assert 2 <= len(match.games) <= 3 and max(match.wins) == 2
    # Whoever chooses (RPS winner, then the previous loser), A wants to go first and B doesn't.
    assert [g.first for g in match.games] == [0] * len(match.games)
    assert all(g.replay for g in games)


def test_invalid_responses_retry_then_lose(engine, decks):
    class Broken(Seat):
        name = "broken"

        def choose(self, prompt, retry):
            return b"\x7f\x7f\x7f\x7f"
    duel = run_duel(engine, DuelConfig(max_retries=2), (decks["Saffira"], decks["Blackwing"]),
                    (Broken(), PolicySeat("B", RandomPolicy(1))), seed=1)
    r = duel.result
    assert r.winner == 1 and r.reason == 0x5 and r.retries == 3
    assert duel.replay.responses == []   # invalid responses are not kept in the replay
    duel.close()
