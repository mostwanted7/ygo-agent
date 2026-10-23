"""A lethal hit must leave zero LP in player and spectator snapshots."""

import json

import pytest

from ygo_agent.arena.duel import DuelConfig
from ygo_agent.arena.runner import run_duel


@pytest.mark.integration
def test_overkill_is_zero_in_final_agent_and_spectator_states(engine, make_seat):
    seats = (make_seat("blackwing"), make_seat("saffira"))
    for seat in seats:
        seat.trace = []
    duel = run_duel(engine, DuelConfig(lp=800), tuple(s.deck(engine) for s in seats), seats, seed=3)
    try:
        assert duel.result.winner in (0, 1)
        loser = 1 - duel.result.winner
        assert duel.field_state().players[loser].lp < 0  # exercise actual overkill, not exact lethal
        for team, seat in enumerate(seats):
            side = "me" if team == loser else "opp"
            final = next(d for d in reversed(seat.trace) if d.get("kind") == "game_over")
            assert final["state"][side]["lp"] == 0
            info = seat.collect()
            with open(info["dir"] + "/game.jsonl") as f:
                snapshots = [r["msg"]["state"] for line in f
                             if (r := json.loads(line))["kind"] == "spectator_state"]
            assert snapshots[-1][side]["lp"] == 0
    finally:
        duel.close()
