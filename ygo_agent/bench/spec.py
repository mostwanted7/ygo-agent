"""What a benchmark plays: decks × backends × opponents, N games per pairing, on a fixed seed list.

Game i (0-based) of every pairing uses seed `seed + i`, and the benchmarked seat goes first when i is even and
second when it is odd. So every backend faces the same deals in the same order, and a run cut short keeps the
backends comparable game for game.
"""

from __future__ import annotations

import dataclasses
import os
import tomllib
from dataclasses import dataclass, field

from ..agent.gamelog import slug
from ..match import MatchError, SeatSpec

BASELINES = ("heuristic", "random")


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Job:
    deck: str
    backend: str
    opponent: str
    index: int           # 0-based game number within the pairing
    seed: int
    first: str           # "player" (the benchmarked seat) or "opponent"

    @property
    def key(self) -> str:
        return f"{self.deck}|{self.backend}|{self.opponent}|{self.index + 1}"

    @property
    def slug(self) -> str:
        return f"{slug(self.deck, 16)}--{slug(self.backend, 16)}--{slug(self.opponent, 28)}--{self.index + 1:03d}"

    @property
    def player_spec(self) -> str:
        return f"{self.deck}:{self.backend}"


@dataclass
class BenchSpec:
    name: str = "bench"
    decks: list[str] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    opponents: list[str] = field(default_factory=list)
    games: int = 6                                         # per (deck, backend, opponent)
    games_for: dict[str, int] = field(default_factory=dict)  # per-backend overrides, e.g. {"heuristic": 30}
    seed: int = 1000
    rules: str = "MR3"
    parallel: int = 3
    budget_usd: float | None = None                        # stop starting games past this (CLI cost estimate)
    timeout: float = 5400                                  # seconds per game in a WindBot room
    note: str = ""                                         # shown at the top of the report (e.g. "a pilot")
    scratch: bool = False                                  # a test run: <games_dir>/bench-smoke/, not bench/results/

    def games_of(self, backend: str) -> int:
        return int(self.games_for.get(backend, self.games))

    def validate(self) -> "BenchSpec":
        for what in ("decks", "backends", "opponents"):
            if not getattr(self, what):
                raise SpecError(f"the benchmark needs at least one entry in {what}")
            if len(set(getattr(self, what))) != len(getattr(self, what)):
                raise SpecError(f"{what} lists an entry twice")
        if self.games < 1 or any(int(v) < 0 for v in self.games_for.values()):
            raise SpecError("games must be at least 1 (games_for may be 0 to skip a backend)")
        unknown = set(self.games_for) - set(self.backends)
        if unknown:
            raise SpecError(f"games_for names backends that aren't benchmarked: {', '.join(sorted(unknown))}")
        if self.parallel < 1:
            raise SpecError("parallel must be at least 1")
        for b in self.backends:
            if ":" in b:
                raise SpecError(f"backend {b!r}: give a profile name (decks are listed separately)")
        for o in self.opponents:
            try:
                seat = SeatSpec.parse(o)
            except MatchError as e:
                raise SpecError(f"opponent {o!r}: {e}") from None
            if seat.kind == "human":
                raise SpecError("a benchmark can't have a human opponent")
        return self

    def jobs(self) -> list[Job]:
        """Every game of the plan, ordered game number first, so all pairings advance together."""
        rounds = max((self.games_of(b) for b in self.backends), default=0)
        out = []
        for i in range(rounds):
            for deck in self.decks:
                for opponent in self.opponents:
                    for backend in self.backends:
                        if i < self.games_of(backend):
                            out.append(Job(deck, backend, opponent, i, self.seed + i,
                                           "player" if i % 2 == 0 else "opponent"))
        return out

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BenchSpec":
        known = {f.name for f in dataclasses.fields(cls)}
        extra = set(data) - known
        if extra:
            raise SpecError(f"unknown benchmark setting(s): {', '.join(sorted(extra))}")
        data = dict(data)
        for key in ("decks", "backends", "opponents"):
            if isinstance(data.get(key), str):
                data[key] = split_list(data[key])
        if data.get("budget_usd") in (0, 0.0):
            data["budget_usd"] = None
        return cls(**data)

    @classmethod
    def load(cls, path: str) -> "BenchSpec":
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except OSError as e:
            raise SpecError(f"can't read {path}: {e.strerror or e}") from None
        except tomllib.TOMLDecodeError as e:
            raise SpecError(f"{path}: {e}") from None
        data.setdefault("name", os.path.splitext(os.path.basename(path))[0])
        return cls.from_dict(data)


def split_list(text: str) -> list[str]:
    return [x.strip() for x in str(text).split(",") if x.strip()]


def parse_games_for(text: str) -> dict[str, int]:
    """--games-for heuristic=30,opus=2"""
    out = {}
    for part in split_list(text):
        name, sep, value = part.partition("=")
        if not sep or not value.strip().isdigit():
            raise SpecError(f"--games-for wants backend=N pairs, got {part!r}")
        out[name.strip()] = int(value)
    return out


def opponent_label(opponent: str) -> str:
    """windbot:Blue-Eyes -> "Blue-Eyes (WindBot)"; AI seats stay as written."""
    head, _, rest = opponent.partition(":")
    return f"{rest} (WindBot)" if head.lower() == "windbot" else opponent
