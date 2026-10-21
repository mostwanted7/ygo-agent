"""A headless EDOPro LAN host: one room, two duelist positions, any number of spectators.

The room follows EDOPro's own host (gframe/netserver.cpp + generic_duel.cpp) packet by packet: lobby
(join, ready, kick, to duelist/observer, deck checks), rock-paper-scissors and the first-player choice, the
duel (filtered game messages, MSG_WAITING, time limit), chat, surrender, side decking and rematches, and
spectator catch-up. Positions can be held by network clients (EDOPro, WindBot) or by in-process seats.

    room = Room(engine, RoomConfig(...))
    room.add_local(1, PolicySeat("Bot", RandomPolicy()), deck)
    server = ArenaServer(room, port=7911)
    await server.serve()            # until the room is finished
"""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import logging
import random
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..core import Engine
from ..core.constants import WIN_REASON_CONNECTION_LOST, WIN_REASON_SURRENDERED, WIN_REASON_TIMED_OUT
from . import protocol as P
from .deck import (AllowedCards, Banlist, Deck, DeckError, DeckRules, DeckSizes, check_deck, classify)
from .duel import Duel, DuelConfig, DuelObserver, DuelResult, Pending, StartState
from .messages import Prompt
from .runner import rps_winner
from .seats import Seat, SeatFeed, SeatView
from .visibility import SPECTATORS, TEAM0, TEAM1

log = logging.getLogger("ygo_agent.arena")

STATE_ANY, STATE_NONE = 0, 0xFF
TIME_BONUS = 5      # EDOPro gives each player time_limit + 5 seconds per turn and shows time_limit
TIME_GRACE = 1.0    # ... and doesn't count the first second of each prompt


class Stage(Enum):
    LOBBY = "lobby"
    RPS = "rps"
    CHOOSE_FIRST = "choose_first"
    DUELING = "dueling"
    SIDING = "siding"
    REMATCH = "rematch"
    CLOSED = "closed"


@dataclass
class RoomConfig:
    name: str = "ygo-agent arena"
    password: str = ""
    duel: DuelConfig = field(default_factory=DuelConfig)
    best_of: int = 1
    time_limit: int = 0                 # seconds per player per turn, like EDOPro's host (0 = no limit)
    ai_time_exempt: bool = True         # in-process seats never time out
    deck_sizes: DeckSizes = field(default_factory=DeckSizes)
    check_deck_size: bool = True
    check_deck_content: bool = True
    allowed: AllowedCards = AllowedCards.ANY
    banlist: Banlist | None = None
    client_version: tuple[int, int] = (41, 0)
    auto_start: bool = True             # start when both duelists are ready (else the host presses Start)
    host_client: bool = True            # the first network client gets the host flag (Start, Kick, add bot)
    rematch: bool = True                # offer a rematch after a match, as EDOPro does
    max_matches: int | None = None      # close the room after this many matches
    send_replay: bool = True            # send our .yrpX to clients at the end (EDOPro's STOC_NEW_REPLAY)
    seed: int | None = None             # games are reproducible from this seed (and the players' choices)
    # Lobby position that goes first in game 1 of every match. None: the RPS winner chooses, as in EDOPro. Later games
    # of a Bo3 are always the previous loser's choice. The RPS still runs, so clients see the usual sequence.
    first: int | None = None
    stack: dict[int, list[int]] = field(default_factory=dict)   # lobby position -> codes on top of deck
    start_state: StartState | None = None
    reserved: dict[int, str] = field(default_factory=dict)      # lobby position -> client name it waits for
    lan_discovery: bool = True


class Participant:
    """Someone in the room: a network client or an in-process seat."""
    name: str = ""
    pos: int | None = None     # 0/1 duelist, 7 observer, None before joining
    ready: bool = False
    deck: Deck | None = None
    original_deck: Deck | None = None
    deck_unknown: list[int]
    team: int | None = None    # core team in the current game
    seat: Seat
    is_local = False

    def send(self, pid: int, payload: bytes = b"") -> None:
        pass


class NetworkSeat(Seat):
    """A network client's seat: `choose` resolves when its CTOS_RESPONSE arrives."""
    is_network = True

    def __init__(self, client: "Client"):
        self.client = client
        self.future: asyncio.Future | None = None

    @property
    def name(self) -> str:
        return self.client.name

    def choose(self, prompt: Prompt, retry: bool) -> asyncio.Future:
        self.future = asyncio.get_running_loop().create_future()
        return self.future

    def deliver(self, data: bytes) -> bool:
        if self.future is None or self.future.done():
            return False
        self.future.set_result(data)
        return True

    def cancel(self) -> None:
        if self.future is not None and not self.future.done():
            self.future.cancel()


class Client(Participant):
    def __init__(self, room: "Room", writer: asyncio.StreamWriter):
        self.room = room
        self.writer = writer
        self.deck_unknown = []
        self.state = STATE_ANY
        self.joined = False
        self.is_edopro = False
        self.seat = NetworkSeat(self)
        peer = writer.get_extra_info("peername")
        self.address = f"{peer[0]}:{peer[1]}" if peer else "?"
        self.closed = False

    def send(self, pid: int, payload: bytes = b"") -> None:
        if self.closed:
            return
        try:
            self.writer.write(P.frame(pid, payload))
        except (ConnectionError, RuntimeError):
            self.closed = True

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            try:
                self.writer.close()
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"<Client {self.name!r} pos={self.pos} {self.address}>"


class LocalPlayer(Participant):
    is_local = True

    def __init__(self, seat: Seat, deck: Deck):
        self.seat = seat
        self.name = seat.name
        self.deck = deck
        self.original_deck = deck.copy()
        self.deck_unknown = []
        self.ready = True

    def __repr__(self) -> str:
        return f"<Local {self.name!r} pos={self.pos}>"


class RoomObserver:
    """Lobby-level hooks. Duel-level hooks (messages, prompts, responses) are DuelObservers: pass them to
    `Room.duel_observers` or create them per game with `duel_observer_factory`."""

    def on_join(self, p: Participant) -> None: ...
    def on_leave(self, p: Participant) -> None: ...
    def on_chat(self, p: Participant | None, text: str) -> None: ...
    def on_deck_rejected(self, p: Participant, error: DeckError) -> None: ...
    def on_game_start(self, room: "Room", duel: Duel) -> None: ...
    def on_game_end(self, room: "Room", duel: Duel, result: DuelResult) -> None: ...
    def on_match_end(self, room: "Room", wins: tuple[int, int]) -> None: ...


class Room:
    def __init__(self, engine: Engine, config: RoomConfig):
        if config.duel.best_of != config.best_of:
            config = dataclasses.replace(config, duel=dataclasses.replace(config.duel, best_of=config.best_of))
        self.engine, self.config = engine, config
        self.slots: list[Participant | None] = [None, None]
        self.observers: list[Client] = []
        self.clients: list[Client] = []
        self.host: Participant | None = None
        self.stage = Stage.LOBBY
        self.rng = random.Random(config.seed)
        self.hands = [0, 0]
        self.chooser: Participant | None = None
        self.duel: Duel | None = None
        self.game_task: asyncio.Task | None = None
        self.match_results: list[int] = []   # winner lobby position per game (2 = draw)
        self.match_kill = False
        self.matches_played = 0
        self.games: list[tuple[Duel, DuelResult]] = []
        self.rejections: list[tuple[str, DeckError]] = []   # (client name, why) for decks refused at "ready"
        self.room_observers: list[RoomObserver] = []
        self.duel_observers: list[DuelObserver] = []
        self.duel_observer_factory: Callable[["Room", int], list[DuelObserver]] | None = None
        # Awaited before each match starts (e.g. until a spectator has joined); None starts at once.
        self.gate: Callable[["Room"], Awaitable[None]] | None = None
        self._gate_task: asyncio.Task | None = None
        self._gate_open = False
        self.finished = asyncio.Event()
        self._budget = [0.0, 0.0]
        self._turn_seen = -1
        self.team_positions = [0, 1]   # lobby position of core team 0 (moves first) and team 1, this game
        self._timer: asyncio.Task | None = None
        self._waiting: asyncio.Future | None = None   # the answer the game loop is waiting for
        self.version = P.ClientVersion(config.client_version[0], config.client_version[1], *engine.core.version)
        self.host_info = self._host_info()

    # --- setup ---------------------------------------------------------------------------------------------
    def _host_info(self) -> P.HostInfo:
        c = self.config
        sizes = DeckSizes.unlimited() if not c.check_deck_size else c.deck_sizes
        return P.HostInfo(
            lflist=c.banlist.hash if c.banlist else 0, rule=int(c.allowed), mode=0, duel_rule=0,
            no_check_deck_content=0 if c.check_deck_content else 1, no_shuffle_deck=0 if c.duel.shuffle else 1,
            start_lp=c.duel.lp, start_hand=c.duel.start_hand, draw_count=c.duel.draw_count,
            time_limit=c.time_limit, duel_flags=c.duel.flags & ~0x10, version=self.version,
            best_of=c.best_of, forbidden_types=c.duel.forbidden_types,
            sizes=(*sizes.main, *sizes.extra, *sizes.side))

    @property
    def deck_rules(self) -> DeckRules:
        c = self.config
        return DeckRules(sizes=c.deck_sizes, check_size=c.check_deck_size, check_content=c.check_deck_content,
                         forbidden_types=c.duel.forbidden_types, banlist=c.banlist, allowed=c.allowed)

    def add_local(self, pos: int, seat: Seat, deck: Deck) -> LocalPlayer:
        """Put an in-process seat at lobby position `pos` (before clients join)."""
        if self.slots[pos] is not None:
            raise ValueError(f"position {pos} is taken")
        err = check_deck(deck, self.engine.cards, self.deck_rules)
        if err:
            raise ValueError(f"{seat.name}'s deck is not legal here: {err}")
        p = LocalPlayer(seat, deck)
        p.pos = pos
        self.slots[pos] = p
        self._broadcast(P.STOC_HS_PLAYER_ENTER, P.player_enter(p.name, pos))
        self._broadcast(P.STOC_HS_PLAYER_CHANGE, P.player_change(pos, P.PLAYERCHANGE_READY))
        return p

    def start_if_ready(self) -> None:
        """Start a match when both positions are already filled and ready (e.g. two in-process seats)."""
        if self.config.auto_start:
            self._maybe_start()

    # --- sending ---------------------------------------------------------------------------------------------
    def duelists(self) -> list[Participant]:
        return [p for p in self.slots if p is not None]

    def everyone(self) -> list[Participant]:
        return self.duelists() + list(self.observers)

    def _broadcast(self, pid: int, payload: bytes = b"", exclude: Participant | None = None) -> None:
        for p in self.everyone():
            if p is not exclude:
                p.send(pid, payload)

    def _to_players(self, pid: int, payload: bytes = b"") -> None:
        for p in self.duelists():
            p.send(pid, payload)

    def _by_team(self, team: int) -> Participant | None:
        for p in self.duelists():
            if p.team == team:
                return p
        return None

    def _emit(self, mask: int, data: bytes) -> None:
        if mask & TEAM0:
            p = self._by_team(0)
            if p:
                p.send(P.STOC_GAME_MSG, data)
        if mask & TEAM1:
            p = self._by_team(1)
            if p:
                p.send(P.STOC_GAME_MSG, data)
        if mask & SPECTATORS:
            for o in self.observers:
                o.send(P.STOC_GAME_MSG, data)

    def say(self, text: str, sender: str = "", to: Participant | None = None) -> None:
        """A system chat line from the arena (STOC_CHAT_2 for EDOPro clients, STOC_CHAT for others)."""
        for p in ([to] if to else self.everyone()):
            if isinstance(p, Client):
                if p.is_edopro:
                    p.send(P.STOC_CHAT_2, P.chat2(P.CHAT2_SYSTEM, False, sender, text))
                else:
                    p.send(P.STOC_CHAT, P.chat(P.CHAT_SYSTEM_PLAYER, text))

    def chat_as(self, participant: Participant, text: str) -> None:
        """Chat from a duelist (e.g. an in-process AI seat), delivered like a client's CTOS_CHAT."""
        self._relay_chat(participant, text)

    # --- packet handling ---------------------------------------------------------------------------------------
    def handle(self, c: Client, pid: int, data: bytes) -> None:
        """NetServer::HandleCTOSPacket: drop packets the client isn't expected to send right now."""
        if pid not in (P.CTOS_SURRENDER, P.CTOS_CHAT) and (
                c.state == STATE_NONE or (c.state != STATE_ANY and c.state != pid)):
            log.debug("ignored %s from %r (state %#x)", P.PACKET_NAMES.get(pid, pid), c, c.state)
            return
        try:
            handler = _HANDLERS.get(pid)
            if handler:
                handler(self, c, data)
            else:
                log.debug("unhandled %s from %r", P.PACKET_NAMES.get(pid, hex(pid)), c)
        except P.ProtocolError as e:
            log.warning("bad packet %s from %r: %s", P.PACKET_NAMES.get(pid, pid), c, e)

    def on_player_info(self, c: Client, data: bytes) -> None:
        c.name = P.parse_player_info(data)

    def on_create_game(self, c: Client, data: bytes) -> None:
        log.info("%r tried to create a game; this host has one fixed room", c)
        c.send(P.STOC_ERROR_MSG, P.join_error(P.JOINERROR_REFUSED))

    def on_join(self, c: Client, data: bytes) -> None:
        """GenericDuel::JoinGame."""
        if c.joined:
            c.send(P.STOC_ERROR_MSG, P.join_error(P.JOINERROR_UNABLE))
            return
        pkt = P.JoinGame.unpack(data)
        if pkt.version2 != self.version:
            log.info("%r has version %s, room needs %s", c, pkt.version2, self.version)
            c.send(P.STOC_ERROR_MSG, P.version_error(self.version))
            return
        if pkt.password != self.config.password:
            c.send(P.STOC_ERROR_MSG, P.join_error(P.JOINERROR_PASSWORD))
            return
        if self.stage == Stage.CLOSED:
            c.send(P.STOC_ERROR_MSG, P.join_error(P.JOINERROR_UNABLE))
            return
        c.joined = True
        c.is_edopro = pkt.version == P.PRO_VERSION
        if self.stage != Stage.LOBBY:
            self._join_running(c)
        else:
            self._join_lobby(c)
        for o in self.room_observers:
            o.on_join(c)

    def _host_flag(self, p: Participant) -> int:
        return P.TYPE_HOST_FLAG if p is self.host else 0

    def _free_position(self, name: str) -> int | None:
        for pos, wanted in self.config.reserved.items():
            if wanted == name and self.slots[pos] is None:
                return pos
        for pos in range(2):
            if self.slots[pos] is None and pos not in self.config.reserved:
                return pos
        return None

    def _join_lobby(self, c: Client) -> None:
        if self.config.host_client and self.host is None and not any(
                isinstance(p, Client) for p in self.everyone() if p is not c):
            self.host = c
        pos = self._free_position(c.name)
        if pos is not None:
            self._broadcast(P.STOC_HS_PLAYER_ENTER, P.player_enter(c.name, pos))
            self.slots[pos] = c
            c.pos = pos
        else:
            self.observers.append(c)
            c.pos = P.NETPLAYER_TYPE_OBSERVER
            self._broadcast(P.STOC_HS_WATCH_CHANGE, P.watch_change(len(self.observers)))
        c.send(P.STOC_JOIN_GAME, self.host_info.pack())
        c.send(P.STOC_TYPE_CHANGE, bytes((self._host_flag(c) | c.pos,)))
        for p in self.duelists():
            c.send(P.STOC_HS_PLAYER_ENTER, P.player_enter(p.name, p.pos))
            if p.ready:
                c.send(P.STOC_HS_PLAYER_CHANGE, P.player_change(p.pos, P.PLAYERCHANGE_READY))
        if self.observers:
            c.send(P.STOC_HS_WATCH_CHANGE, P.watch_change(len(self.observers)))
        log.info("%s joined as %s", c.name, "observer" if c.pos == 7 else f"duelist {c.pos}")

    def _join_running(self, c: Client) -> None:
        """A spectator joining a running match: lobby info, DUEL_START, then the catch-up stream."""
        c.send(P.STOC_JOIN_GAME, self.host_info.pack())
        c.send(P.STOC_TYPE_CHANGE, bytes((P.NETPLAYER_TYPE_OBSERVER,)))
        c.pos = P.NETPLAYER_TYPE_OBSERVER
        c.state = P.CTOS_LEAVE_GAME
        for p in self.duelists():
            c.send(P.STOC_HS_PLAYER_ENTER, P.player_enter(p.name, p.pos))
        c.send(P.STOC_DUEL_START)
        if self.stage in (Stage.SIDING, Stage.REMATCH):
            c.send(P.STOC_WAITING_SIDE)
        if self.duel is not None and self.stage == Stage.DUELING:
            c.send(P.STOC_CATCHUP, b"\x01")
            for data in self.duel.spectator_cache:
                c.send(P.STOC_GAME_MSG, data)
            c.send(P.STOC_CATCHUP, b"\x00")
        self.observers.append(c)
        log.info("%s joined as spectator (catch-up: %d messages)", c.name,
                 len(self.duel.spectator_cache) if self.duel else 0)

    def on_leave_game(self, c: Client, data: bytes) -> None:
        self.leave(c)

    def leave(self, c: Client) -> None:
        """GenericDuel::LeaveGame (but the arena keeps running when the host leaves the lobby)."""
        if c not in self.clients:
            return
        self.clients.remove(c)
        c.seat.cancel()
        if c in self.observers:
            self.observers.remove(c)
            self._broadcast(P.STOC_HS_WATCH_CHANGE, P.watch_change(len(self.observers)))
        elif c.pos is not None and c.pos < 2 and self.slots[c.pos] is c:
            pos = c.pos
            if self.stage == Stage.LOBBY:
                self.slots[pos] = None
                self._broadcast(P.STOC_HS_PLAYER_CHANGE, P.player_change(pos, P.PLAYERCHANGE_LEAVE))
            elif self.stage != Stage.CLOSED:
                self.slots[pos] = None
                if self.duel is not None and self.duel.result is None and c.team is not None:
                    self.duel.end(1 - c.team, WIN_REASON_CONNECTION_LOST)
                    self._wake_game()
                elif self.stage in (Stage.SIDING, Stage.REMATCH, Stage.RPS, Stage.CHOOSE_FIRST):
                    self._broadcast(P.STOC_DUEL_END)
                    self._close_match()
        if c is self.host:
            self.host = None
        c.close()
        for o in self.room_observers:
            o.on_leave(c)
        log.info("%s left", c.name or c.address)

    def on_to_duelist(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.LOBBY:
            return
        if c in self.observers:
            pos = self._free_position(c.name)
            if pos is None:
                return
            self.observers.remove(c)
            self.slots[pos] = c
            c.pos = pos
            self._broadcast(P.STOC_HS_PLAYER_ENTER, P.player_enter(c.name, pos))
            self._broadcast(P.STOC_HS_WATCH_CHANGE, P.watch_change(len(self.observers)))
            c.send(P.STOC_TYPE_CHANGE, bytes((self._host_flag(c) | pos,)))
        elif c.pos is not None and c.pos < 2 and not c.ready:
            other = 1 - c.pos
            if self.slots[other] is None and other not in self.config.reserved:
                self._broadcast(P.STOC_HS_PLAYER_CHANGE, P.player_change(c.pos, other))
                c.send(P.STOC_TYPE_CHANGE, bytes((self._host_flag(c) | other,)))
                self.slots[other], self.slots[c.pos] = c, None
                c.pos = other

    def on_to_observer(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.LOBBY or c.pos is None or c.pos >= 2:
            return
        self._broadcast(P.STOC_HS_PLAYER_CHANGE, P.player_change(c.pos, P.PLAYERCHANGE_OBSERVE))
        self.slots[c.pos] = None
        c.pos, c.ready = P.NETPLAYER_TYPE_OBSERVER, False
        self.observers.append(c)
        c.send(P.STOC_TYPE_CHANGE, bytes((self._host_flag(c) | c.pos,)))

    def on_ready(self, c: Client, data: bytes, ready: bool = True) -> None:
        """GenericDuel::PlayerReady, with the deck check."""
        if self.stage != Stage.LOBBY or c.pos is None or c.pos >= 2 or c.ready == ready:
            return
        if ready:
            err = DeckError(type=0) if c.deck is None else check_deck(c.deck, self.engine.cards,
                                                                        self.deck_rules, c.deck_unknown)
            if c.deck is None or err:
                c.send(P.STOC_HS_PLAYER_CHANGE, P.player_change(c.pos, P.PLAYERCHANGE_NOTREADY))
                e = err or DeckError(type=0)
                c.send(P.STOC_ERROR_MSG, P.deck_error(int(e.type), e.code, e.current, e.minimum, e.maximum))
                log.info("%s's deck was rejected: %s", c.name, e if c.deck else "no deck sent")
                self.rejections.append((c.name, e))
                for o in self.room_observers:
                    o.on_deck_rejected(c, e)
                return
        c.ready = ready
        self._broadcast(P.STOC_HS_PLAYER_CHANGE,
                        P.player_change(c.pos, P.PLAYERCHANGE_READY if ready else P.PLAYERCHANGE_NOTREADY))
        if ready and self.config.auto_start:
            self._maybe_start()

    def on_not_ready(self, c: Client, data: bytes) -> None:
        self.on_ready(c, data, ready=False)

    def on_kick(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.LOBBY or c is not self.host or not data:
            return
        pos = data[0]
        target = self.slots[pos] if pos < 2 else None
        if isinstance(target, Client) and target is not c:
            self.leave(target)

    def on_start(self, c: Client, data: bytes) -> None:
        if self.stage == Stage.LOBBY and c is self.host:
            self._maybe_start()

    def on_update_deck(self, c: Client, data: bytes) -> None:
        if c.pos is None or c.pos >= 2:
            return
        main, side = P.parse_update_deck(data)
        result = classify(main, side, self.engine.cards)
        if self.stage == Stage.LOBBY:
            if c.ready:
                return
            c.deck, c.deck_unknown = result.deck, result.unknown
            c.original_deck = result.deck.copy()
            log.info("%s sent a deck: %d main, %d extra, %d side%s", c.name, len(result.deck.main),
                     len(result.deck.extra), len(result.deck.side),
                     f", unknown cards {result.unknown}" if result.unknown else "")
        elif self.stage == Stage.SIDING and not c.ready:
            if not _valid_side(c.original_deck, result.deck) or result.unknown:
                c.send(P.STOC_ERROR_MSG, P.side_error())
                return
            c.deck = result.deck
            c.ready = True
            c.send(P.STOC_DUEL_START)
            self._maybe_resume_after_siding()

    # --- starting a game ---------------------------------------------------------------------------------------
    def _gated(self, resume: Callable[[], None]) -> bool:
        """True while `gate` holds the next match back; `resume` is called again once it lets go."""
        if self.gate is None:
            return False
        if self._gate_open:
            self._gate_open = False
            return False
        if self._gate_task is None or self._gate_task.done():
            self._gate_task = asyncio.get_running_loop().create_task(self._pass_gate(resume))
        return True

    async def _pass_gate(self, resume: Callable[[], None]) -> None:
        try:
            await self.gate(self)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("match gate failed")
        self._gate_open = True
        resume()
        self._gate_open = False  # not used up when the match couldn't start after all (someone left)

    def _maybe_start(self) -> None:
        if self.stage != Stage.LOBBY or any(p is None or not p.ready for p in self.slots):
            return
        if self._gated(self._maybe_start):
            return
        self.stage = Stage.RPS
        self._broadcast(P.STOC_DUEL_START)
        for o in self.observers:
            o.state = P.CTOS_LEAVE_GAME
        self.match_results, self.match_kill = [], False
        log.info("match starting: %s vs %s", self.slots[0].name, self.slots[1].name)
        self._ask_rps()

    def _ask_rps(self) -> None:
        self.hands = [0, 0]
        for pos, p in enumerate(self.slots):
            if isinstance(p, Client):
                p.state = P.CTOS_HAND_RESULT
                p.send(P.STOC_SELECT_HAND)
        for pos, p in enumerate(self.slots):
            if isinstance(p, LocalPlayer):
                self._hand(pos, p.seat.rps())

    def on_hand_result(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.RPS or not data or not 1 <= data[0] <= 3 or c.pos is None or c.pos >= 2:
            return
        c.state = STATE_NONE
        self._hand(c.pos, data[0])

    def _hand(self, pos: int, hand: int) -> None:
        self.hands[pos] = hand
        if not all(self.hands):
            return
        h0, h1 = self.hands
        for p in [self.slots[0]] + self.observers:
            p.send(P.STOC_HAND_RESULT, bytes((h0, h1)))
        self.slots[1].send(P.STOC_HAND_RESULT, bytes((h1, h0)))
        winner = rps_winner(h0, h1)
        if winner is None:
            self._ask_rps()
            return
        self._ask_first(self.slots[winner])

    def _ask_first(self, chooser: Participant) -> None:
        self.stage = Stage.CHOOSE_FIRST
        self.chooser = chooser
        for p in self.duelists():
            if isinstance(p, Client):
                p.state = STATE_NONE
        if self.config.first is not None and not self.match_results:  # game 1: the room decides
            self._first_chosen(chooser, chooser.pos == self.config.first)
            return
        if isinstance(chooser, Client):
            chooser.state = P.CTOS_TP_RESULT
            chooser.send(P.STOC_SELECT_TP)
        else:
            self._first_chosen(chooser, chooser.seat.go_first())

    def on_tp_result(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.CHOOSE_FIRST or c is not self.chooser or not data:
            return
        c.state = STATE_NONE
        self._first_chosen(c, data[0] == 1)

    def _first_chosen(self, chooser: Participant, go_first: bool) -> None:
        first_pos = chooser.pos if go_first else 1 - chooser.pos
        self.slots[first_pos].team, self.slots[1 - first_pos].team = 0, 1
        self.stage = Stage.DUELING
        self.game_task = asyncio.get_running_loop().create_task(self._play_game())

    # --- the duel ----------------------------------------------------------------------------------------------
    async def _play_game(self) -> None:
        c = self.config
        first, second = self._by_team(0), self._by_team(1)
        index = len(self.games)
        game_seed = random.Random(f"{c.seed}:{index}").getrandbits(63) if c.seed is not None else None
        observers = list(self.duel_observers)
        if self.duel_observer_factory:
            observers += self.duel_observer_factory(self, index)
        for p in (first, second):
            if isinstance(p, LocalPlayer) and type(p.seat).on_message is not Seat.on_message:
                observers.append(SeatFeed(p.seat, p.team))
        stack = {p.team: c.stack[p.pos] for p in (first, second) if c.stack.get(p.pos)}
        duel = Duel(self.engine, c.duel, (first.deck, second.deck), (first.name, second.name), seed=game_seed,
                    stack=stack, start_state=c.start_state, spectator_team=self.slots[0].team,
                    emit=self._emit, observers=observers)
        self.duel = duel
        for p in (first, second):
            p.seat.bind(SeatView(duel, p.team))
            if isinstance(p, Client):
                p.state = STATE_NONE
        for o in self.room_observers:
            o.on_game_start(self, duel)
        self.team_positions = [first.pos, second.pos]
        self._budget = [float(c.time_limit + TIME_BONUS)] * 2
        self._turn_seen = 0
        log.info("game %d: %s goes first (seed %s)", index + 1, first.name, duel.seed)
        try:
            step = duel.start()
            while isinstance(step, Pending) and duel.result is None:
                data = await self._ask(duel, step)
                if duel.result is not None or data is None:
                    break
                step = duel.respond(data)
        except Exception:
            log.exception("duel crashed")
            if duel.result is None:
                duel.end(2, 0x6)
        finally:
            self._stop_timer()
        if duel.result is None:
            duel.end(2, 0x6)
        result = duel.result
        for p in (first, second):
            p.seat.on_end(result, p.team)
        self.games.append((duel, result))
        for o in self.room_observers:
            o.on_game_end(self, duel, result)
        self._end_game(duel, result)
        duel.close()

    async def _ask(self, duel: Duel, step: Pending) -> bytes | None:
        p = self._by_team(step.team)
        if p is None:
            return None
        if duel.turn != self._turn_seen:
            self._turn_seen = duel.turn
            self._budget = [float(self.config.time_limit + TIME_BONUS)] * 2
        timed = self.config.time_limit > 0 and not (isinstance(p, LocalPlayer) and self.config.ai_time_exempt)
        if isinstance(p, Client):
            p.state = P.CTOS_RESPONSE
        if timed:
            left = int(self._budget[step.team]) - TIME_BONUS
            for d in self.duelists():
                d.send(P.STOC_TIME_LIMIT, P.time_limit(step.team, left))
            self._timer = asyncio.get_running_loop().create_task(self._time_out(step.team))
        started = time.monotonic()
        try:
            answer = p.seat.choose(step.message, step.retry)
            if inspect.isawaitable(answer):
                self._waiting = asyncio.ensure_future(answer)
                answer = await self._waiting
            return answer
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            return None
        finally:
            self._waiting = None
            if isinstance(p, Client):
                p.state = STATE_NONE
            if timed:
                self._stop_timer()
                used = max(0.0, time.monotonic() - started - TIME_GRACE)
                self._budget[step.team] -= used

    async def _time_out(self, team: int) -> None:
        await asyncio.sleep(max(0.0, self._budget[team]) + TIME_GRACE)
        duel = self.duel
        if duel is not None and duel.result is None:
            log.info("team %d ran out of time", team)
            duel.end(1 - team, WIN_REASON_TIMED_OUT)
            self._wake_game()

    def _stop_timer(self) -> None:
        if self._timer is not None and not self._timer.done() and self._timer is not asyncio.current_task():
            self._timer.cancel()
        self._timer = None

    def _wake_game(self) -> None:
        """The duel was ended from outside (surrender, time out, disconnect): stop waiting for the answer."""
        for c in self.clients:
            c.seat.cancel()
        if self._waiting is not None and not self._waiting.done():
            self._waiting.cancel()

    def on_response(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.DUELING or self.duel is None:
            return
        pending = self.duel.pending
        if pending is None or c.team != pending.team:
            return
        c.state = STATE_NONE
        c.seat.deliver(data)

    def on_surrender(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.DUELING or self.duel is None or self.duel.result is not None:
            return
        if c.team is None or c.pos is None or c.pos >= 2:
            return  # spectators can't surrender (EDOPro would end the duel; Multirole ignores them)
        self.duel.end(1 - c.team, WIN_REASON_SURRENDERED)
        self._wake_game()

    def surrender_local(self, p: Participant) -> None:
        if self.duel is not None and self.duel.result is None and p.team is not None:
            self.duel.end(1 - p.team, WIN_REASON_SURRENDERED)
            self._wake_game()

    def on_time_confirm(self, c: Client, data: bytes) -> None:
        pass  # EDOPro's host ignores it too

    def on_chat(self, c: Client, data: bytes) -> None:
        from .buffer import read_utf16
        text = read_utf16(data[:512])
        if not c.joined:
            return
        self._relay_chat(c, text)

    def _relay_chat(self, sender: Participant, text: str) -> None:
        """GenericDuel::Chat: STOC_CHAT_2 with the sender's name; legacy STOC_CHAT for non-EDOPro clients."""
        observer = sender.pos is None or sender.pos >= 2
        sender_team = sender.team if self.stage == Stage.DUELING and sender.team is not None else sender.pos
        for p in self.everyone():
            if not isinstance(p, Client):
                continue
            if p.is_edopro:
                if observer:
                    payload = P.chat2(P.CHAT2_OBSERVER, False, sender.name, text)
                else:
                    mine = p.team if self.stage == Stage.DUELING and p.team is not None else p.pos
                    payload = P.chat2(P.CHAT2_DUELIST, mine == sender_team, sender.name, text)
                p.send(P.STOC_CHAT_2, payload)
            else:
                p.send(P.STOC_CHAT, P.chat(sender.pos if sender.pos is not None else P.NETPLAYER_TYPE_OBSERVER,
                                           text))
        for o in self.room_observers:
            o.on_chat(sender, text)

    # --- after a game ----------------------------------------------------------------------------------------
    def _end_game(self, duel: Duel, result: DuelResult) -> None:
        """GenericDuel::EndDuel + DuelEndProc."""
        c = self.config
        if c.send_replay and duel.replay is not None:
            data = duel.replay.yrpx()
            if len(data) <= P.MAX_PAYLOAD:
                self._broadcast(P.STOC_NEW_REPLAY, data)
            else:
                self.say("The replay is too big to send; it was saved on the host.")
            self._broadcast(P.STOC_REPLAY)
        winner_pos = 2 if result.is_draw else self.team_positions[result.winner]
        self.match_results.append(winner_pos)
        self.match_kill = self.match_kill or bool(duel.match_kill)
        wins = (self.match_results.count(0), self.match_results.count(1))
        needed = c.best_of // 2 + 1
        missing = any(p is None for p in self.slots)
        if missing or max(wins) >= needed or len(self.match_results) >= c.best_of or self.match_kill:
            self.matches_played += 1
            for o in self.room_observers:
                o.on_match_end(self, wins)
            more = c.max_matches is None or self.matches_played < c.max_matches
            if c.rematch and more and not missing:
                self._seek_rematch()
            else:
                self._broadcast(P.STOC_DUEL_END)
                self._close_match()
        else:
            self.stage = Stage.SIDING
            for p in self.duelists():
                p.ready = False
                if isinstance(p, Client):
                    p.state = P.CTOS_UPDATE_DECK
                    p.send(P.STOC_CHANGE_SIDE)
                else:
                    p.ready = True
            for o in self.observers:
                o.send(P.STOC_WAITING_SIDE)
            self._maybe_resume_after_siding()

    def _loser(self) -> Participant:
        last = self.match_results[-1] if self.match_results else 2
        return self.slots[1 - last] if last in (0, 1) else self.slots[0]

    def _maybe_resume_after_siding(self) -> None:
        if self.stage == Stage.SIDING and all(p is not None and p.ready for p in self.slots):
            self._ask_first(self._loser())

    def _seek_rematch(self) -> None:
        self.stage = Stage.REMATCH
        self._broadcast(P.STOC_WAITING_REMATCH)
        for p in self.duelists():
            p.deck = p.original_deck.copy() if p.original_deck else p.deck
            p.ready = False
            if isinstance(p, Client):
                p.state = P.CTOS_REMATCH_RESPONSE
                p.send(P.STOC_REMATCH)
        for p in self.duelists():
            if isinstance(p, LocalPlayer):
                self._rematch_answer(p, True)

    def on_rematch_response(self, c: Client, data: bytes) -> None:
        if self.stage != Stage.REMATCH or c.pos is None or c.pos >= 2:
            return
        self._rematch_answer(c, bool(data and data[0]))

    def _rematch_answer(self, p: Participant, yes: bool) -> None:
        if not yes:
            self._broadcast(P.STOC_DUEL_END)
            self._close_match()
            return
        p.ready = True
        if isinstance(p, Client):
            p.state = STATE_NONE
            p.send(P.STOC_DUEL_START)
        if self.stage == Stage.REMATCH and all(q is not None and q.ready for q in self.slots):
            self._start_rematch()

    def _start_rematch(self) -> None:
        if self.stage != Stage.REMATCH or not all(q is not None and q.ready for q in self.slots):
            return
        if self._gated(self._start_rematch):
            return
        loser = self._loser()
        self.match_results, self.match_kill = [], False
        self._ask_first(loser)

    def _close_match(self) -> None:
        """The match is over and everyone was told (STOC_DUEL_END). Clients leave on their own; the room
        then accepts a new match unless max_matches is reached."""
        self.stage = Stage.CLOSED
        for p in self.everyone():
            if isinstance(p, Client):
                p.state = STATE_NONE
        done = self.config.max_matches is not None and self.matches_played >= self.config.max_matches
        if done:
            self.finished.set()
        else:
            asyncio.get_running_loop().call_later(1.0, self._reset_lobby)

    def _reset_lobby(self) -> None:
        for p in list(self.everyone()):
            if isinstance(p, Client):
                self.leave(p)
        self.slots = [p if isinstance(p, LocalPlayer) else None for p in self.slots]
        for p in self.duelists():
            p.ready, p.team = True, None
        self.observers = []
        self.host = None
        self.duel = None
        self.stage = Stage.LOBBY
        log.info("room open for a new match")
        self.start_if_ready()

    # --- connections -----------------------------------------------------------------------------------------
    async def connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        c = Client(self, writer)
        self.clients.append(c)
        framer = P.PacketReader()
        try:
            while not c.closed:
                data = await reader.read(65536)
                if not data:
                    break
                for pid, payload in framer.feed(data):
                    self.handle(c, pid, payload)
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            self.leave(c)


def _valid_side(original: Deck | None, new: Deck) -> bool:
    """DeckManager::LoadSide: same cards overall, same Main and Extra Deck sizes."""
    if original is None:
        return False
    from collections import Counter
    if len(new.main) != len(original.main) or len(new.extra) != len(original.extra):
        return False
    return Counter(original.main + original.extra + original.side) == Counter(new.main + new.extra + new.side)


_HANDLERS: dict[int, Callable[[Room, Client, bytes], None]] = {
    P.CTOS_PLAYER_INFO: Room.on_player_info,
    P.CTOS_CREATE_GAME: Room.on_create_game,
    P.CTOS_JOIN_GAME: Room.on_join,
    P.CTOS_LEAVE_GAME: Room.on_leave_game,
    P.CTOS_HS_TODUELIST: Room.on_to_duelist,
    P.CTOS_HS_TOOBSERVER: Room.on_to_observer,
    P.CTOS_HS_READY: Room.on_ready,
    P.CTOS_HS_NOTREADY: Room.on_not_ready,
    P.CTOS_HS_KICK: Room.on_kick,
    P.CTOS_HS_START: Room.on_start,
    P.CTOS_UPDATE_DECK: Room.on_update_deck,
    P.CTOS_HAND_RESULT: Room.on_hand_result,
    P.CTOS_TP_RESULT: Room.on_tp_result,
    P.CTOS_RESPONSE: Room.on_response,
    P.CTOS_SURRENDER: Room.on_surrender,
    P.CTOS_TIME_CONFIRM: Room.on_time_confirm,
    P.CTOS_CHAT: Room.on_chat,
    P.CTOS_REMATCH_RESPONSE: Room.on_rematch_response,
}


class _LanDiscovery(asyncio.DatagramProtocol):
    """Answers EDOPro's LAN room search (UDP 7920 → reply to the sender's port 7921)."""

    def __init__(self, server: "ArenaServer"):
        self.server = server
        self.transport = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        if len(data) >= 2 and int.from_bytes(data[:2], "little") == P.NETWORK_CLIENT_ID:
            room = self.server.room
            reply = P.host_packet(self.server.port, room.config.name, room.host_info)
            self.transport.sendto(reply, (addr[0], P.LAN_REPLY_PORT))


class ArenaServer:
    def __init__(self, room: Room, host: str | None = None, port: int = 7911):
        """`host` None listens on every interface, IPv4 and IPv6, like EDOPro's dual-stack host."""
        self.room, self.host, self.port = room, host, port
        self._server: asyncio.base_events.Server | None = None
        self._udp = None

    async def start(self) -> None:
        if self.port == 0 and self.host is None:
            self.host = "127.0.0.1"  # an ephemeral port would differ between the IPv4 and IPv6 sockets
        self._server = await asyncio.start_server(self.room.connection, self.host, self.port)
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]
        if self.room.config.lan_discovery:
            await self._start_discovery()
        log.info("arena listening on %s:%d", self.host or "*", self.port)
        self.room.start_if_ready()

    async def _start_discovery(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("0.0.0.0", P.LAN_DISCOVERY_PORT))
            self._udp, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: _LanDiscovery(self), sock=sock)
        except OSError as e:
            log.info("LAN discovery disabled (UDP %d: %s); join by address instead", P.LAN_DISCOVERY_PORT, e)

    async def serve(self, timeout: float | None = None) -> None:
        """Run until the room is finished (or `timeout` seconds)."""
        if self._server is None:
            await self.start()
        try:
            await asyncio.wait_for(self.room.finished.wait(), timeout)
        finally:
            await self.close()

    async def close(self) -> None:
        if self.room._gate_task is not None and not self.room._gate_task.done():
            self.room._gate_task.cancel()
        if self.room.game_task and not self.room.game_task.done():
            if self.room.duel is not None and self.room.duel.result is None:
                self.room.duel.end(2, 0x6)
                self.room._wake_game()
            try:
                await asyncio.wait_for(self.room.game_task, 5)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
        for c in list(self.room.clients):
            c.close()
        if self._udp is not None:
            self._udp.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
