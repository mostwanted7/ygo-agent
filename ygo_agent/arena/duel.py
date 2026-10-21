"""The duel driver: one game on the core, with EDOPro's host behaviour (generic_duel.cpp) around it.

A `Duel` is a synchronous state machine. `start()` and `respond(data)` run the core until it needs a response
(`Pending`) or the game ends (`DuelResult`). Everything the core says is filtered per audience (see
visibility.py) and handed to:

  * `emit(mask, data)`: raw STOC_GAME_MSG payloads for network clients (bit mask of TEAM0/TEAM1/SPECTATORS);
  * observers (`DuelObserver`): decoded messages per view, every prompt, every response;
  * the replay recorder (the unfiltered stream, as EDOPro records it).

Teams are core teams: team 0 moves first. Seats and lobby positions are mapped onto teams by the caller.
"""

from __future__ import annotations

import random
import struct
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from ..core import Engine
from ..core.constants import (DUEL_SIMPLE_AI, HINT_SELECTMSG, LOCATION_DECK, LOCATION_EXTRA, OCG_DUEL_STATUS_AWAITING,
                              OCG_DUEL_STATUS_END, POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK, QUERY_ALL,
                              WIN_REASON_WRONG_RESPONSE, Msg, rule_set)
from ..core.ocgcore import CoreDuel
from .deck import Deck
from .messages import Message, Prompt, decode
from .query import CardQuery, FieldState, ViewCache, card_views, location_views, parse_card, parse_field, \
    parse_location
from .replay import ReplayRecorder
from .visibility import (EVERYONE, SPECTATORS, TEAM0, TEAM1, Refresh, post_refreshes, pre_refreshes, route,
                         start_refreshes, team_bit)

VIEW_TEAM0, VIEW_TEAM1, VIEW_SPECTATOR, VIEW_FULL = 0, 1, 2, 3
_MASK_VIEWS = ((TEAM0, VIEW_TEAM0), (TEAM1, VIEW_TEAM1), (SPECTATORS, VIEW_SPECTATOR))
_START = struct.Struct("<BBIIHHHH")


class DuelError(RuntimeError):
    pass


@dataclass
class DuelConfig:
    rules: str | int = "mr3"         # "mr1".."mr5", "goat", "speed", "rush", or raw duel flags
    extra_flags: int = 0              # OR-ed into the rule flags
    lp: int = 8000
    start_hand: int = 5
    draw_count: int = 1
    shuffle: bool = True              # host-side deck shuffle (EDOPro's "don't shuffle deck" unticked)
    best_of: int = 1                  # only affects whether MSG_MATCH_KILL is forwarded
    max_retries: int = 1              # invalid responses allowed per prompt before the replier loses
    record_replay: bool = True

    @property
    def flags(self) -> int:
        flags = rule_set(self.rules).flags | self.extra_flags
        if not self.shuffle:
            flags |= 0x10  # DUEL_PSEUDO_SHUFFLE, as EDOPro sets it with no_shuffle_deck
        return flags

    @property
    def forbidden_types(self) -> int:
        return rule_set(self.rules).forbidden_types


@dataclass(frozen=True)
class Placement:
    """A card put somewhere before the duel starts (custom start state)."""
    team: int
    code: int
    location: int
    sequence: int = 0
    position: int = POS_FACEUP_ATTACK


@dataclass
class StartState:
    """Cards placed directly with OCG_DuelNewCard before the duel starts (hand, field, GY, banished).
    `start_hand` overrides the opening draw per team (often 0 when the hand is placed by hand)."""
    placements: list[Placement] = field(default_factory=list)
    start_hand: tuple[int, int] | None = None


@dataclass
class Pending:
    team: int
    prompt: bytes          # the prompt as that team receives it (filtered)
    retry: bool = False
    _message: Prompt | None = field(default=None, repr=False)

    @property
    def message(self) -> Prompt:
        if self._message is None:
            self._message = decode(self.prompt)
        return self._message


@dataclass
class DuelResult:
    winner: int            # core team, or 2 for a draw
    reason: int            # WIN_REASON_* / MSG_WIN reason
    turns: int
    responses: int
    retries: int
    lua_errors: list[str]
    missing_scripts: list[str]

    @property
    def is_draw(self) -> bool:
        return self.winner > 1


class DuelObserver:
    """Subclass and override what you need. `views` selects which decoded streams `on_message` gets:
    VIEW_TEAM0/VIEW_TEAM1 (what that duelist's client receives), VIEW_SPECTATOR, VIEW_FULL (unfiltered)."""
    views: frozenset[int] = frozenset()

    def on_start(self, duel: "Duel") -> None: ...
    def on_message(self, view: int, msg: Message) -> None: ...
    def on_prompt(self, team: int, prompt: Prompt, retry: bool) -> None: ...
    def on_response(self, team: int, prompt: Prompt, data: bytes) -> None: ...
    def on_end(self, duel: "Duel", result: DuelResult) -> None: ...


def derive_core_seed(rng: random.Random) -> tuple[int, int, int, int]:
    seed = tuple(rng.getrandbits(64) for _ in range(4))
    return seed if any(seed) else (1, 0, 0, 0)


def stack_deck(main: list[int], top: list[int]) -> list[int]:
    """`main` reordered so `top` comes first, in order (top[0] is drawn first). Each code in `top` must be in
    `main` (one copy is moved per mention)."""
    rest = list(main)
    for code in top:
        try:
            rest.remove(code)
        except ValueError:
            raise DuelError(f"cannot stack card {code}: not in the Main Deck (or not enough copies)") from None
    return list(top) + rest


class Duel:
    def __init__(self, engine: Engine, config: DuelConfig, decks: tuple[Deck, Deck],
                 names: tuple[str, str] = ("Player 1", "Player 2"), *, seed: int | None = None,
                 core_seed: Iterable[int] | None = None, stack: dict[int, list[int]] | None = None,
                 start_state: StartState | None = None, spectator_team: int = 0,
                 emit: Callable[[int, bytes], None] | None = None, observers: Iterable[DuelObserver] = (),
                 insertion_order: tuple[tuple[list[int], list[int]], tuple[list[int], list[int]]] | None = None,
                 log: Callable[[str, int], None] | None = None):
        """`seed` drives both the core seed and the deck shuffle (random when None). `stack[team]` lists
        codes to put on top of that team's deck. `insertion_order` bypasses shuffling and stacking: the exact
        (main, extra) lists to add to the core, as a .yrp records them (bottom card first)."""
        if config.flags & DUEL_SIMPLE_AI:
            raise DuelError("DUEL_SIMPLE_AI would let the core answer for player 1")
        self.engine, self.config = engine, config
        self.decks, self.names = decks, names
        self.seed = seed if seed is not None else random.SystemRandom().getrandbits(63)
        self.rng = random.Random(self.seed)
        self.core_seed = tuple(core_seed) if core_seed is not None else derive_core_seed(self.rng)
        self.stack = stack or {}
        self.start_state = start_state
        self.spectator_team = spectator_team
        self.emit = emit
        self.observers: list[DuelObserver] = list(observers)
        self.log = log
        self.pending: Pending | None = None
        self.result: DuelResult | None = None
        self.turn = 0
        self.turn_player = 0
        self.phase = 0
        self.responses = 0
        self.retries = 0
        self.spectator_cache: list[bytes] = []
        self.match_kill = 0  # MSG_MATCH_KILL's card code in a best-of-3: the whole match ends
        self.replay: ReplayRecorder | None = None
        self._core: CoreDuel | None = None
        self._views = ViewCache()
        self._prompt_retries = 0
        self._select_hint: dict[int, bytes] = {}
        self._insertion = insertion_order or self._prepare_decks()

    # --- setup ---------------------------------------------------------------------------------------------
    def _prepare_decks(self):
        out = []
        for team, deck in enumerate(self.decks):
            main = list(deck.main)
            if self.config.shuffle:
                self.rng.shuffle(main)
            if self.stack.get(team):
                main = stack_deck(main, self.stack[team])
            # EDOPro adds the Main Deck back to front so main[0] ends up on top.
            out.append((main[::-1], list(deck.extra)[::-1]))
        return tuple(out)

    def _create_core(self) -> CoreDuel:
        c = self.config
        hands = (c.start_hand, c.start_hand)
        if self.start_state and self.start_state.start_hand is not None:
            hands = self.start_state.start_hand
        return self.engine.new_duel(seed=self.core_seed, flags=c.flags, team1=(c.lp, hands[0], c.draw_count),
                                    team2=(c.lp, hands[1], c.draw_count), log=self.log)

    @property
    def core(self) -> CoreDuel:
        if self._core is None:
            raise DuelError("duel not started")
        return self._core

    def start(self) -> Pending | DuelResult:
        if self._core is not None:
            raise DuelError("duel already started")
        self._core = core = self._create_core()
        c = self.config
        if c.record_replay:
            self.replay = ReplayRecorder(seed=self.core_seed, duel_flags=c.flags, start_lp=c.lp,
                                         start_hand=c.start_hand, draw_count=c.draw_count,
                                         names=([self.names[0]], [self.names[1]]))
            self.replay.decks = [(list(m), list(e)) for m, e in self._insertion]
        for team, (main, extra) in enumerate(self._insertion):
            for code in main:
                core.new_card(team, code, LOCATION_DECK, 0, POS_FACEDOWN_DEFENSE)
            for code in extra:
                core.new_card(team, code, LOCATION_EXTRA, 0, POS_FACEDOWN_DEFENSE)
        if self.start_state:
            for p in self.start_state.placements:
                core.new_card(p.team, p.code, p.location, p.sequence, p.position)
            if self.replay:
                self.replay.old_replay_valid = False
            core.run_lua("Debug.ReloadFieldEnd()")
        for obs in self.observers:
            obs.on_start(self)
        start = _START.pack(Msg.START, 0, c.lp, c.lp, core.query_count(0, LOCATION_DECK),
                            core.query_count(0, LOCATION_EXTRA), core.query_count(1, LOCATION_DECK),
                            core.query_count(1, LOCATION_EXTRA))
        self._send(TEAM0, start)
        self._send(TEAM1, start[:1] + b"\x01" + start[2:])
        spec = start[:1] + bytes([0x10 | self.spectator_team]) + start[2:]
        self._send(SPECTATORS, spec)
        self.spectator_cache.append(spec)
        self._record(start)
        for ref in start_refreshes():
            self._refresh(ref)
        core.start()
        return self._run()

    # --- running ---------------------------------------------------------------------------------------------
    def respond(self, data: bytes) -> Pending | DuelResult:
        if self.result is not None:
            return self.result
        if self.pending is None:
            raise DuelError("no prompt is waiting for a response")
        pending = self.pending
        for obs in self.observers:
            obs.on_response(pending.team, pending.message, data)
        self.pending = None
        self.responses += 1
        if self.replay:
            self.replay.respond(data)
        self.core.set_response(data)
        return self._run(after=pending)

    def _run(self, after: Pending | None = None) -> Pending | DuelResult:
        core = self.core
        while True:
            status = core.process()
            for raw in core.messages():
                if raw[0] == Msg.RETRY:
                    if after is None:
                        raise DuelError("MSG_RETRY without a response")
                    return self._retry(after)
                self._dispatch(raw)
                if self.result is not None:
                    return self.result
                if self.pending is not None:
                    return self.pending  # a prompt is always the last message of a batch
            if status == OCG_DUEL_STATUS_END:
                return self._finish(2, 0)
            if status == OCG_DUEL_STATUS_AWAITING:
                raise DuelError("core is waiting for a response but sent no prompt")

    def _retry(self, prompt: Pending) -> Pending | DuelResult:
        """The response was invalid. Like Multirole: tell the player, re-send the prompt (with its selection
        hint), drop the bad response from the replay; after `max_retries` the replier loses."""
        self.retries += 1
        self._prompt_retries += 1
        if self.replay:
            self.replay.pop_response()
        if self._prompt_retries > self.config.max_retries:
            return self.end(1 - prompt.team, WIN_REASON_WRONG_RESPONSE)
        bit = team_bit(prompt.team)
        self._send(bit, bytes([Msg.RETRY]))
        hint = self._select_hint.get(prompt.team)
        if hint:
            self._send(bit, hint)
        self._send(bit, prompt.prompt)
        self.pending = Pending(prompt.team, prompt.prompt, retry=True)
        for obs in self.observers:
            obs.on_prompt(prompt.team, self.pending.message, True)
        return self.pending

    def _dispatch(self, raw: bytes) -> None:
        t = raw[0]
        if t == Msg.NEW_TURN:
            self.turn += 1
            self.turn_player = raw[1]
        elif t == Msg.NEW_PHASE:
            self.phase = raw[1] | raw[2] << 8
        elif t == Msg.MATCH_KILL and self.config.best_of > 1:
            self.match_kill = struct.unpack_from("<I", raw, 1)[0]
        for ref in pre_refreshes(raw):
            self._refresh(ref)
        r = route(raw, self.config.best_of)
        for mask, data in r.sends:
            self._send(mask, data)
        if r.cache is not None:
            self.spectator_cache.append(r.cache)
        if r.record:
            self._record(raw)
        if t == Msg.HINT and raw[1] == HINT_SELECTMSG and raw[2] < 2:
            self._select_hint[raw[2]] = raw
        for ref in post_refreshes(raw, custom_start=self.start_state is not None):
            self._refresh(ref)
        if r.prompt_team is not None:
            delivered = next(data for mask, data in r.sends if mask == team_bit(r.prompt_team))
            self._prompt_retries = 0
            self.pending = Pending(r.prompt_team, delivered)
            for obs in self.observers:
                obs.on_prompt(r.prompt_team, self.pending.message, False)
        elif t == Msg.WIN:
            self._finish(raw[1], raw[2])

    def _refresh(self, ref: Refresh) -> None:
        core = self.core
        if ref.sequence is None:
            raw = core.query_location(ref.controller, ref.location, ref.flags)
            if not raw:
                return
            head = bytes((Msg.UPDATE_DATA, ref.controller, ref.location))
            if ref.replay_only:
                self._record(head + raw)
                return
            v = self._views.get(raw, True)
        else:
            raw = core.query(ref.controller, ref.location, ref.sequence, ref.flags)
            if raw is None:
                return
            head = bytes((Msg.UPDATE_CARD, ref.controller, ref.location, ref.sequence))
            v = self._views.get(raw, False)
        self._record(head + v.full)
        owner = team_bit(ref.controller)
        self._send(owner, head + v.owner)
        public = head + v.public
        self._send(EVERYONE & ~owner, public)
        self.spectator_cache.append(public)

    # --- output -----------------------------------------------------------------------------------------------
    def _send(self, mask: int, data: bytes) -> None:
        if not mask:
            return
        if self.emit:
            self.emit(mask, data)
        if self.observers:
            msg = None
            for bit, view in _MASK_VIEWS:
                if mask & bit:
                    for obs in self.observers:
                        if view in obs.views:
                            msg = msg or decode(data)
                            obs.on_message(view, msg)

    def _record(self, raw: bytes) -> None:
        if self.replay:
            self.replay.record(raw)
        if self.observers:
            msg = None
            for obs in self.observers:
                if VIEW_FULL in obs.views:
                    msg = msg or decode(raw)
                    obs.on_message(VIEW_FULL, msg)

    # --- ending ---------------------------------------------------------------------------------------------
    def end(self, winner: int, reason: int) -> DuelResult:
        """End the duel from outside the core (surrender, time out, disconnect, invalid responses). Sends
        MSG_WIN to everyone and records it, as EDOPro's host does."""
        if self.result is not None:
            return self.result
        win = bytes((Msg.WIN, winner, reason))
        self._send(EVERYONE, win)
        self._record(win)
        return self._finish(winner, reason)

    def _finish(self, winner: int, reason: int) -> DuelResult:
        if self.result is None:
            core = self._core
            self.pending = None
            self.result = DuelResult(winner, reason, self.turn, self.responses, self.retries,
                                     list(core.lua_errors) if core else [],
                                     sorted(set(core.missing_scripts)) if core else [])
            for obs in self.observers:
                obs.on_end(self, self.result)
        return self.result

    def close(self) -> None:
        if self._core is not None:
            self._core.close()

    def __enter__(self) -> "Duel":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- filtered views of the state (for in-process seats and observers) ------------------------------------
    def view_location(self, viewer: int | None, controller: int, location: int, flags: int = QUERY_ALL
                      ) -> list[CardQuery | None]:
        """Cards in a location as `viewer` (a team, or None for a spectator) may see them."""
        raw = self.core.query_location(controller, location, flags)
        if not raw:
            return []
        v = location_views(raw)
        return parse_location(v.owner if viewer == controller else v.public)

    def view_card(self, viewer: int | None, controller: int, location: int, sequence: int,
                  flags: int = QUERY_ALL) -> CardQuery | None:
        raw = self.core.query(controller, location, sequence, flags)
        if raw is None:
            return None
        v = card_views(raw)
        return parse_card(v.owner if viewer == controller else v.public)

    def field_state(self) -> FieldState:
        """LP, zone occupancy, pile sizes and the current chain: all public."""
        return parse_field(self.core.query_field())

    def count(self, team: int, location: int) -> int:
        return self.core.query_count(team, location)
