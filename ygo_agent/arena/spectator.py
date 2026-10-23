"""Viewer-only board snapshots. These never enter a seat's decision state or the coach's history."""

from .duel import VIEW_FULL, DuelObserver
from .native_view import NativeView
from .query import parse_location
from .seats import SeatView
from ..core.constants import LOCATION_DECK, LOCATION_MZONE, LOCATION_SZONE, QUERY_ALL, QUERY_CODE, QUERY_POSITION


class _SpectatorQueries(SeatView):
    def location(self, controller, location, flags=QUERY_ALL):
        if location == LOCATION_DECK:
            return super().location(controller, location, flags)
        if location not in (LOCATION_MZONE, LOCATION_SZONE):
            flags = QUERY_CODE | QUERY_POSITION
        # The viewer needs no privacy filtering. Avoid constructing owner/public copies of every query.
        raw = self._duel.core.query_location(controller, location, flags)
        return parse_location(raw) if raw else []


class SpectatorFeed(DuelObserver):
    views = frozenset({VIEW_FULL})

    def __init__(self, team, publish):
        self.team, self.publish = team, publish
        self.native = NativeView(team)

    def on_start(self, duel):
        self.native = NativeView(self.team, duel.engine.cards)
        self.native.bind(_SpectatorQueries(duel, self.team))

    def on_message(self, view, msg):
        self.native.on_message(msg)

    def on_prompt(self, team, prompt, retry):
        self.publish(self.native.state())

    def on_end(self, duel, result):
        self.publish(self.native.state())
