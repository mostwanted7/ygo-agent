"""Seats: whoever answers a team's prompts.

* `PolicySeat` wraps a callable `policy(prompt, view) -> bytes` and runs in-process (random/simple policies
  now; Stage 3's native AI seat is another in-process seat).
* Network clients (EDOPro, WindBot) are seats too; server.py creates them (`NetworkSeat`): their `choose`
  resolves when the client's CTOS_RESPONSE arrives.

Every seat gets its team's filtered message stream through `on_message` (decoded, exactly what that player's
EDOPro client would receive), and a `SeatView` for on-demand queries limited to what the team may see.
"""

from __future__ import annotations

import asyncio
import inspect
import random
from collections.abc import Awaitable, Callable

from ..core.cards import CardDatabase
from ..core.constants import (LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND, LOCATION_MZONE,
                              LOCATION_REMOVED, LOCATION_SZONE, QUERY_ALL)
from .duel import VIEW_TEAM0, Duel, DuelObserver, DuelResult
from .messages import Message, Prompt
from .query import CardQuery, FieldState


class SeatView:
    """What a seat may look at during the duel: everything public, its own hand and set cards, but neither
    the opponent's hidden cards (they come back without codes) nor its own deck order (only the count).
    Seats should only use this, never the Duel itself, to stay fair."""

    def __init__(self, duel: Duel, team: int):
        self._duel = duel
        self.team = team

    @property
    def cards(self) -> CardDatabase:
        return self._duel.engine.cards

    @property
    def names(self) -> tuple[str, str]:
        return self._duel.names

    @property
    def config(self):
        """The duel's DuelConfig (rules flags, LP, hand size, ...): public, the room shows it to everyone."""
        return self._duel.config

    @property
    def turn(self) -> int:
        return self._duel.turn

    @property
    def turn_player(self) -> int:
        return self._duel.turn_player

    @property
    def phase(self) -> int:
        return self._duel.phase

    @property
    def opponent(self) -> int:
        return 1 - self.team

    def location(self, controller: int, location: int, flags: int = QUERY_ALL) -> list[CardQuery | None]:
        if location == LOCATION_DECK and controller == self.team:
            # Your own deck order is hidden information too: only the count is public.
            return [None] * self._duel.count(controller, location)
        return self._duel.view_location(self.team, controller, location, flags)

    def card(self, controller: int, location: int, sequence: int, flags: int = QUERY_ALL) -> CardQuery | None:
        if location == LOCATION_DECK:
            return None
        return self._duel.view_card(self.team, controller, location, sequence, flags)

    def count(self, controller: int, location: int) -> int:
        return self._duel.count(controller, location)

    def field(self) -> FieldState:
        return self._duel.field_state()

    def snapshot(self) -> dict[str, list[CardQuery | None]]:
        """Hand, field, GY, banished and Extra Deck of both players, keyed like "me.hand" / "opp.mzone"."""
        out = {}
        for who, con in (("me", self.team), ("opp", self.opponent)):
            for name, loc in (("hand", LOCATION_HAND), ("mzone", LOCATION_MZONE), ("szone", LOCATION_SZONE),
                              ("grave", LOCATION_GRAVE), ("banished", LOCATION_REMOVED),
                              ("extra", LOCATION_EXTRA)):
                out[f"{who}.{name}"] = self.location(con, loc)
        return out


class Seat:
    """Base class. Override `choose`; the other hooks are optional."""
    name: str = "seat"
    is_network: bool = False

    def bind(self, view: SeatView) -> None:
        self.view = view

    def on_message(self, msg: Message) -> None:
        pass

    def choose(self, prompt: Prompt, retry: bool) -> bytes | Awaitable[bytes]:
        raise NotImplementedError

    def rps(self) -> int:
        """Rock-paper-scissors: 1 scissors, 2 rock, 3 paper."""
        return random.randint(1, 3)

    def go_first(self) -> bool:
        """Asked when this seat won the RPS (or lost the previous game of a match)."""
        return True

    def on_end(self, result: DuelResult, team: int) -> None:
        pass


Policy = Callable[[Prompt, SeatView], bytes]


class PolicySeat(Seat):
    def __init__(self, name: str, policy: Policy, go_first: bool = True):
        self.name = name
        self.policy = policy
        self._go_first = go_first

    def choose(self, prompt: Prompt, retry: bool) -> bytes:
        return self.policy(prompt, self.view)

    def go_first(self) -> bool:
        return self._go_first


class SeatFeed(DuelObserver):
    """Feeds a seat its team's message stream."""

    def __init__(self, seat: Seat, team: int):
        self.seat, self.team = seat, team
        self.views = frozenset({VIEW_TEAM0 + team})

    def on_message(self, view: int, msg: Message) -> None:
        self.seat.on_message(msg)


def resolve(value):
    """A seat's answer, waiting for it when the seat returned an awaitable (sync callers only)."""
    if inspect.isawaitable(value):
        return asyncio.run(_await(value))
    return value


async def _await(value):
    return await value
