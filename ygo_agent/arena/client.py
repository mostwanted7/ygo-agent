"""A minimal EDOPro-protocol client (asyncio): joins a room, sends a deck, plays with a policy, or watches.

It behaves like EDOPro's client where the host can tell (version fields, packet order, CTOS_TIME_CONFIRM,
rematch and side-deck answers), which makes it the stand-in for a human client in the arena's tests.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from ..core.constants import PROMPT_MESSAGES
from . import protocol as P
from .deck import Deck
from .messages import Prompt, decode

PromptPolicy = Callable[[Prompt], bytes]


@dataclass
class ClientLog:
    packets: list[tuple[int, bytes]] = field(default_factory=list)
    game: list[bytes] = field(default_factory=list)         # every STOC_GAME_MSG payload, in order
    catchup: list[bytes] = field(default_factory=list)      # the ones that arrived between CATCHUP 1 and 0
    chats: list[tuple[str, str]] = field(default_factory=list)
    errors: list[bytes] = field(default_factory=list)
    replay: bytes | None = None
    host_info: P.HostInfo | None = None
    position: int | None = None
    is_host: bool = False
    team: int | None = None                                  # from MSG_START: 0 first, 1 second


class ArenaClient:
    def __init__(self, name: str, deck: Deck | None = None, policy: PromptPolicy | None = None, *,
                 edopro: bool = True, version: P.ClientVersion = P.ClientVersion(), password: str = "",
                 hand: Callable[[], int] | None = None, go_first: bool = True, rematch: bool = False,
                 auto_ready: bool = True, respond_delay: float = 0.0, stall: bool = False):
        self.name, self.deck, self.policy = name, deck, policy
        self.edopro, self.version, self.password = edopro, version, password
        self.hand = hand or (lambda: random.randint(1, 3))
        self.go_first, self.rematch, self.auto_ready = go_first, rematch, auto_ready
        self.respond_delay, self.stall = respond_delay, stall
        self.log = ClientLog()
        self.done = asyncio.Event()
        self._writer: asyncio.StreamWriter | None = None
        self._catching_up = False
        self._task: asyncio.Task | None = None

    # --- connection ---------------------------------------------------------------------------------------
    async def connect(self, host: str, port: int) -> "ArenaClient":
        reader, self._writer = await asyncio.open_connection(host, port)
        self.send(P.CTOS_PLAYER_INFO, P.player_info(self.name))
        join = P.JoinGame(P.PRO_VERSION if self.edopro else (self.version.as_int & 0xFFFF), 0, self.password,
                          self.version)
        self.send(P.CTOS_JOIN_GAME, join.pack())
        self._task = asyncio.get_running_loop().create_task(self._read(reader))
        return self

    def send(self, pid: int, payload: bytes = b"") -> None:
        if self._writer is not None and not self._writer.is_closing():
            self._writer.write(P.frame(pid, payload))

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError):
                pass
        if self._task is not None:
            self._task.cancel()
        self.done.set()

    async def wait(self, timeout: float | None = None) -> None:
        await asyncio.wait_for(self.done.wait(), timeout)

    async def _read(self, reader: asyncio.StreamReader) -> None:
        framer = P.PacketReader()
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                for pid, payload in framer.feed(data):
                    await self._on_packet(pid, payload)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self.done.set()

    # --- lobby actions ------------------------------------------------------------------------------------
    def send_deck(self) -> None:
        if self.deck is not None:
            main, side = self.deck.network_payload()
            self.send(P.CTOS_UPDATE_DECK, P.update_deck(main, side))

    def ready(self, ready: bool = True) -> None:
        self.send(P.CTOS_HS_READY if ready else P.CTOS_HS_NOTREADY)

    def chat(self, text: str) -> None:
        self.send(P.CTOS_CHAT, text.encode("utf-16-le") + b"\0\0")

    def surrender(self) -> None:
        self.send(P.CTOS_SURRENDER)

    # --- incoming -------------------------------------------------------------------------------------------
    async def _on_packet(self, pid: int, payload: bytes) -> None:
        log = self.log
        log.packets.append((pid, payload))
        if pid == P.STOC_JOIN_GAME:
            log.host_info = P.HostInfo.unpack(payload)
        elif pid == P.STOC_TYPE_CHANGE:
            log.position, log.is_host = payload[0] & 0xF, bool(payload[0] & 0x10)
            if log.position < 7 and self.auto_ready and self.deck is not None:
                self.send_deck()
                self.ready()
        elif pid == P.STOC_SELECT_HAND:
            self.send(P.CTOS_HAND_RESULT, bytes((self.hand(),)))
        elif pid == P.STOC_SELECT_TP:
            self.send(P.CTOS_TP_RESULT, bytes((1 if self.go_first else 0,)))
        elif pid == P.STOC_CHANGE_SIDE:
            self.send_deck()
        elif pid == P.STOC_REMATCH:
            self.send(P.CTOS_REMATCH_RESPONSE, bytes((1 if self.rematch else 0,)))
        elif pid == P.STOC_DUEL_END:
            self.done.set()
        elif pid == P.STOC_TIME_LIMIT:
            if self.log.team is not None and payload[0] == self.log.team:
                self.send(P.CTOS_TIME_CONFIRM)
        elif pid == P.STOC_CHAT_2:
            _kind, _team, name, text = P.parse_chat2(payload)
            log.chats.append((name, text))
        elif pid == P.STOC_CHAT:
            player, text = P.parse_chat(payload)
            log.chats.append((str(player), text))
        elif pid == P.STOC_ERROR_MSG:
            log.errors.append(payload)
            if payload[0] in (P.ERRMSG_JOINERROR, P.ERRMSG_VERERROR, P.ERRMSG_VERERROR2):
                self.done.set()
        elif pid == P.STOC_CATCHUP:
            self._catching_up = bool(payload[0])
        elif pid == P.STOC_NEW_REPLAY:
            log.replay = payload
        elif pid == P.STOC_GAME_MSG:
            await self._on_game_message(payload)

    async def _on_game_message(self, raw: bytes) -> None:
        self.log.game.append(raw)
        if self._catching_up:
            self.log.catchup.append(raw)
        if raw[0] == 4:  # MSG_START
            self.log.team = raw[1] & 0xF
        if raw[0] in PROMPT_MESSAGES and self.policy is not None and not self.stall:
            prompt = decode(raw)
            if self.respond_delay:
                await asyncio.sleep(self.respond_delay)
            self.send(P.CTOS_RESPONSE, self.policy(prompt))


def chat_texts(log: ClientLog) -> list[str]:
    return [text for _, text in log.chats]

