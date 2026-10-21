"""Fast direct-core games and Bo1/Bo3 matches between in-process seats (no sockets)."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from ..core import Engine
from .deck import Deck
from .duel import Duel, DuelConfig, DuelObserver, DuelResult, Pending, StartState
from .seats import Seat, SeatFeed, SeatView, resolve


def _wants_messages(seat: Seat) -> bool:
    return type(seat).on_message is not Seat.on_message


def run_duel(engine: Engine, config: DuelConfig, decks: tuple[Deck, Deck], seats: tuple[Seat, Seat], *,
             seed: int | None = None, stack: dict[int, list[int]] | None = None,
             start_state: StartState | None = None, observers: Iterable[DuelObserver] = (),
             max_responses: int = 20000, log: Callable[[str, int], None] | None = None) -> Duel:
    """Play one duel to the end. Index 0 of `decks`/`seats` is core team 0 (moves first).
    Returns the finished (not yet closed) Duel: `duel.result`, `duel.replay`."""
    observers = list(observers)
    observers += [SeatFeed(s, team) for team, s in enumerate(seats) if _wants_messages(s)]
    duel = Duel(engine, config, decks, (seats[0].name, seats[1].name), seed=seed, stack=stack,
                start_state=start_state, observers=observers, log=log)
    for team, seat in enumerate(seats):
        seat.bind(SeatView(duel, team))
    step = duel.start()
    while isinstance(step, Pending):
        if duel.responses >= max_responses:
            step = duel.end(2, 0)
            break
        data = resolve(seats[step.team].choose(step.message, step.retry))
        step = duel.respond(data)
    for team, seat in enumerate(seats):
        seat.on_end(duel.result, team)
    return duel


@dataclass
class GameRecord:
    index: int
    seed: int
    core_seed: tuple[int, int, int, int]
    first: int                 # which seat (0/1) moved first
    result: DuelResult
    seconds: float
    replay: bytes | None = None

    @property
    def winner_seat(self) -> int | None:
        if self.result.is_draw:
            return None
        return self.first if self.result.winner == 0 else 1 - self.first


@dataclass
class MatchResult:
    games: list[GameRecord] = field(default_factory=list)

    @property
    def wins(self) -> tuple[int, int]:
        w = [0, 0]
        for g in self.games:
            if g.winner_seat is not None:
                w[g.winner_seat] += 1
        return w[0], w[1]

    @property
    def winner(self) -> int | None:
        a, b = self.wins
        return 0 if a > b else 1 if b > a else None


def rock_paper_scissors(seats: tuple[Seat, Seat], rng: random.Random, max_rounds: int = 50) -> int:
    """Rock-paper-scissors between two seats until someone wins (ties repeat); returns the winner's index."""
    for _ in range(max_rounds):
        h0, h1 = seats[0].rps(), seats[1].rps()
        w = rps_winner(h0, h1)
        if w is not None:
            return w
    return rng.randrange(2)


def rps_winner(h0: int, h1: int) -> int | None:
    """Lobby position that wins RPS: position 1 wins on (1,2), (2,3), (3,1); a tie is None."""
    if h0 == h1:
        return None
    return 1 if (h0, h1) in ((1, 2), (2, 3), (3, 1)) else 0


def run_match(engine: Engine, config: DuelConfig, decks: tuple[Deck, Deck], seats: tuple[Seat, Seat], *,
              best_of: int = 1, seed: int | None = None, first: int | None = None,
              stack: dict[int, list[int]] | None = None, start_state: StartState | None = None,
              observers: Iterable[DuelObserver] = (),
              on_game: Callable[[GameRecord, Duel], None] | None = None) -> MatchResult:
    """Bo1/Bo3 between two in-process seats. `first` forces who moves first in game 1 (seat index); otherwise
    the RPS winner chooses, and in later games the loser of the previous game chooses (as in EDOPro).
    `stack` is keyed by seat index."""
    rng = random.Random(seed)
    match = MatchResult()
    needed = best_of // 2 + 1
    chooser = None
    for index in range(best_of):
        if index == 0 and first is not None:
            first_seat = first
        else:
            if chooser is None:
                chooser = rock_paper_scissors(seats, rng)
            first_seat = chooser if seats[chooser].go_first() else 1 - chooser
        order = (first_seat, 1 - first_seat)
        game_seed = rng.getrandbits(63)
        team_stack = {t: stack[s] for t, s in enumerate(order) if stack and stack.get(s)}
        t0 = time.perf_counter()
        duel = run_duel(engine, config, (decks[order[0]], decks[order[1]]), (seats[order[0]], seats[order[1]]),
                        seed=game_seed, stack=team_stack, start_state=start_state, observers=observers)
        try:
            rec = GameRecord(index, game_seed, duel.core_seed, first_seat, duel.result, time.perf_counter() - t0,
                             duel.replay.yrpx() if duel.replay else None)
            if on_game:
                on_game(rec, duel)
        finally:
            duel.close()
        match.games.append(rec)
        if max(match.wins) >= needed or duel.match_kill:
            break
        loser = rec.winner_seat
        chooser = None if loser is None else 1 - loser
    return match


class ScriptedSeat(Seat):
    """Answers prompts from a fixed list of responses (replays, regression tests)."""

    def __init__(self, name: str, responses: list[bytes]):
        self.name = name
        self.responses = responses

    def choose(self, prompt, retry):
        raise RuntimeError("ScriptedSeat is driven by replay_duel")


def replay_duel(engine: Engine, replay, observers: Iterable[DuelObserver] = ()) -> Duel:
    """Re-run an old-style replay (a .yrp, or the one embedded in a .yrpX) on the core: same seed, flags,
    decks in their recorded order, the recorded responses in sequence. The returned duel's `replay` holds
    the stream as this arena records it, which should match EDOPro's .yrpX for the same game."""
    from .replay import Replay
    old: Replay | None = replay.old
    if old is None:
        raise ValueError("this replay has no old-style (.yrp) part to re-simulate")
    if len(old.decks) != 2:
        raise ValueError("only 1v1 replays can be re-simulated")
    flags = old.duel_flags
    config = DuelConfig(rules=flags & ~0x10, extra_flags=flags & 0x10, lp=old.start_lp,
                        start_hand=old.start_hand, draw_count=old.draw_count, shuffle=not flags & 0x10,
                        max_retries=0)
    empty = (Deck(), Deck())
    names = (old.names[0][0] if old.names[0] else "", old.names[1][0] if old.names[1] else "")
    duel = Duel(engine, config, empty, names, core_seed=old.seed, observers=observers,
                insertion_order=(old.decks[0], old.decks[1]))
    if duel.replay is not None:
        duel.replay.timestamp = old.header.timestamp
    step = duel.start()
    responses = iter(old.responses)
    while isinstance(step, Pending):
        data = next(responses, None)
        if data is None:
            break
        step = duel.respond(data)
    return duel
