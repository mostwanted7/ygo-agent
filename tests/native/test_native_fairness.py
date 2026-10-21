"""Fairness: across many seeded native games, no event or decision a seat sends its agent contains a card code
hidden from that seat at that moment (ground truth: the core's unfiltered state). Deliberately leaky seats prove the
check catches each kind of leak. See fairness.py for what is checked."""

import pytest

from fairness import FairnessChecker
from native_helpers import play
from ygo_agent.arena.duel import VIEW_FULL, DuelObserver
from ygo_agent.arena.native_seat import AgentSeat
from ygo_agent.arena.native_view import NativeView
from ygo_agent.arena.query import parse_location
from ygo_agent.core.constants import LOCATION_HAND, LOCATION_MZONE, LOCATION_SZONE, POS_FACEDOWN, QUERY_ALL

pytestmark = pytest.mark.integration
DECKS = ("saffira", "blackwing")


def checked_game(engine, db, cfg, seed, seat_cls=AgentSeat, extra_observers=()):
    """A native heuristic seat vs a native random seat; both are checked. Returns the two checkers."""
    cfg["backends"]["random"]["seed"] = seed
    a = seat_cls.create(DECKS[seed % 2], "heuristic", cfg=cfg, db=db, cards=engine.cards)
    b = seat_cls.create(DECKS[1 - seed % 2], "random", cfg=cfg, db=db, cards=engine.cards)
    checks = [FairnessChecker(0, a), FairnessChecker(1, b)]
    a.trace, b.trace = checks
    observers = list(checks) + [o(s) for s in (a, b) for o in extra_observers]
    play(engine, (a, b), (a.deck(engine), b.deck(engine)), seed + 100, observers=observers)
    a.close()
    b.close()
    return checks


def test_no_hidden_information_reaches_a_native_seat(engine, agent_db, agent_cfg, quiet):
    totals = {"events": 0, "decisions": 0, "visible": 0}
    for seed in range(12):
        for check in checked_game(engine, agent_db, agent_cfg, seed):
            assert not check.leaks, check.leaks[:3]
            for k in totals:
                totals[k] += check.checked[k]
    assert totals["decisions"] > 500 and totals["events"] > 2000 and totals["visible"] > 10000, totals


# --- deliberately leaky seats -------------------------------------------------------------------------------------

def truth(seat, player, location):
    duel = seat.view._duel  # what a fair seat must never touch
    raw = duel.core.query_location(player, location, QUERY_ALL)
    return parse_location(raw) if raw else []


class PeeksAtTheHand(AgentSeat):
    """Fills in the opponent's hand from the unfiltered core."""

    def bind(self, view):
        super().bind(view)
        self.native.state = self._state

    def _state(self):
        s = NativeView.state(self.native)
        opp = 1 - self.native.team
        for c, q in zip(s["opp"]["hand"], truth(self, opp, LOCATION_HAND)):
            c["id"] = q.code
        return s


class PeeksAtSetCards(AgentSeat):
    """Fills in the opponent's face-down cards on the field."""

    def bind(self, view):
        super().bind(view)
        self.native.state = self._state

    def _state(self):
        s = NativeView.state(self.native)
        opp = 1 - self.native.team
        for key, loc in (("mz", LOCATION_MZONE), ("sz", LOCATION_SZONE)):
            for c, q in zip(s["opp"][key], truth(self, opp, loc)):
                if c is not None and q is not None and q.position & POS_FACEDOWN:
                    c["id"] = q.code
        return s


class ReadsTheFullStream(AgentSeat):
    """Builds its events from the unfiltered message stream instead of its team's."""

    def on_message(self, msg):
        pass

    def full(self, msg):
        AgentSeat.on_message(self, msg)


class FullFeed(DuelObserver):
    views = frozenset({VIEW_FULL})

    def __init__(self, seat):
        self.seat = seat

    def on_message(self, view, msg):
        if isinstance(self.seat, ReadsTheFullStream):
            self.seat.full(msg)


class LeaksTheDeckOrder(AgentSeat):
    """Options keep the Deck sequence of searched cards (the order of the Deck is hidden information)."""

    def bind(self, view):
        super().bind(view)
        self.native.card_dict = self._card_dict

    def _card_dict(self, card, player, location, sequence, position=None, *, ref=True, code=None):
        d = NativeView.card_dict(self.native, card, player, location, sequence, position, ref=ref, code=code)
        if location == 0x1:
            d["s"] = sequence
        return d


class KeepsUidsThroughShuffles(AgentSeat):
    """Follows the opponent's hidden hand cards through a shuffle (it can't really tell them apart)."""

    def bind(self, view):
        super().bind(view)
        native = self.native

        def reshuffle(cards, codes):
            if any(codes):
                return NativeView._reshuffle(native, cards, codes)
            for card in cards:
                card.code = 0
            return list(cards)
        native._reshuffle = reshuffle


class PeeksAtTargets(AgentSeat):
    """Fills in the codes of the opponent's face-down cards it is offered in a selection."""

    def bind(self, view):
        super().bind(view)
        native, seat = self.native, self

        def option_card(ref):
            d = NativeView.option_card(native, ref)
            if ref.location in (LOCATION_MZONE, LOCATION_SZONE) and not d["id"]:
                q = truth(seat, ref.controller, ref.location)
                if ref.sequence < len(q) and q[ref.sequence] is not None:
                    d["id"] = q[ref.sequence].code
            return d
        native.option_card = option_card


LEAKS = [(PeeksAtTheHand, ()), (PeeksAtSetCards, ()), (ReadsTheFullStream, (FullFeed,)),
         (LeaksTheDeckOrder, ()), (KeepsUidsThroughShuffles, ()), (PeeksAtTargets, ())]


@pytest.mark.parametrize("leaky,observers", LEAKS, ids=[c.__name__ for c, _ in LEAKS])
def test_the_check_catches_injected_leaks(engine, agent_db, agent_cfg, quiet, leaky, observers):
    for seed in range(12):
        checks = checked_game(engine, agent_db, agent_cfg, seed, leaky, observers)
        leaks = [leak for c in checks for leak in c.leaks]
        if leaks:
            return
    pytest.fail(f"{leaky.__name__}: no leak detected in 12 games")


def test_codes_of_a_never_seen_card_are_caught():
    """Unit check of the never-seen rule on a hand-made event."""
    check = FairnessChecker(0)
    check.append({"t": "event", "e": "move", "id": 12345, "from": {}, "to": {}, "reason": 0})
    assert check.leaks and "never saw" in check.leaks[0]
