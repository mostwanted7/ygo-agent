"""God view knows both hands and set cards without changing either player's knowledge."""

import json

import pytest

from ygo_agent.arena.duel import Duel, DuelConfig, Placement, StartState
from ygo_agent.arena.native_seat import SeatWatcher
from ygo_agent.arena.seats import SeatFeed, SeatView
from ygo_agent.arena.spectator import SpectatorFeed
from ygo_agent.core.constants import LOCATION_MZONE, LOCATION_SZONE, POS_FACEDOWN_DEFENSE
from ygo_agent.web.recorded import load_game

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("team", [0, 1])
@pytest.mark.parametrize("coached", [False, True])
def test_spectator_reveals_before_opponent_decides(engine, make_seat, agent_db, team, coached):
    seat = make_seat("blackwing")
    deck = seat.deck(engine)
    monster = next(c for c in deck.main if engine.cards.get(c).type & 1)
    spell = next(c for c in deck.main if engine.cards.get(c).type & 2)
    start = StartState([Placement(p, c, loc, 0, POS_FACEDOWN_DEFENSE)
                        for p in (0, 1) for c, loc in ((monster, LOCATION_MZONE), (spell, LOCATION_SZONE))],
                       start_hand=(5, 5))
    snapshots, decisions = [], []
    observers = [SpectatorFeed(team, snapshots.append),
                 SeatWatcher(team, engine.cards, on_decision=decisions.append)] if coached else [SeatFeed(seat, team)]
    duel = Duel(engine, DuelConfig(), (deck, deck), seed=3, start_state=start, observers=observers)
    seat.bind(SeatView(duel, team))
    try:
        duel.start()
        if not coached:
            info = seat.collect()
            with open(info["dir"] + "/game.jsonl") as f:
                rows = [json.loads(line) for line in f]
            snapshots = [r["msg"]["state"] for r in rows if r["kind"] == "spectator_state"]
            replay = load_game(info["dir"], agent_db)
            saved = [m for m in replay if m["type"] == "spectator_state"]
            assert saved and saved[-1]["state"] == snapshots[-1]
            assert saved[-1].get("cards")  # spectator-only identities get names/art metadata too
        assert snapshots
        for side in ("me", "opp"):
            assert len(snapshots[-1][side]["hand"]) >= 5
            assert all(c["id"] for c in snapshots[-1][side]["hand"])
            assert snapshots[-1][side]["mz"][0]["id"] == monster
            assert snapshots[-1][side]["sz"][0]["id"] == spell
        normal = observers[1].native.state() if coached else seat.native.state()
        assert all(c["id"] == 0 for c in normal["opp"]["hand"])
        assert normal["opp"]["mz"][0]["id"] == 0
        assert normal["opp"]["sz"][0]["id"] == 0
        assert all(not d["state"]["opp"]["hand"][0]["id"] for d in decisions)
    finally:
        duel.close()
