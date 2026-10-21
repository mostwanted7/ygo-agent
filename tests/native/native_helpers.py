"""Helpers shared by the native-seat tests."""

from ygo_agent.arena.duel import DuelConfig
from ygo_agent.arena.runner import run_duel


def play(engine, seats, decks, seed, observers=(), rules="mr3"):
    """One in-process duel; returns the finished (closed) Duel."""
    duel = run_duel(engine, DuelConfig(rules=rules), decks, seats, seed=seed, observers=observers)
    duel.close()
    return duel

