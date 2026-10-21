"""EDOPro's network protocol (gframe/network.h): packet framing, packet ids and the structs that travel.

Every packet is `u16 length` (of what follows), `u8 id`, payload. Structs are packed with C alignment, as
EDOPro sends them with memcpy.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .buffer import read_utf16, utf16_field, utf16_text

# --- client to server ---
CTOS_RESPONSE = 0x01
CTOS_UPDATE_DECK = 0x02
CTOS_HAND_RESULT = 0x03
CTOS_TP_RESULT = 0x04
CTOS_PLAYER_INFO = 0x10
CTOS_CREATE_GAME = 0x11
CTOS_JOIN_GAME = 0x12
CTOS_LEAVE_GAME = 0x13
CTOS_SURRENDER = 0x14
CTOS_TIME_CONFIRM = 0x15
CTOS_CHAT = 0x16
CTOS_HS_TODUELIST = 0x20
CTOS_HS_TOOBSERVER = 0x21
CTOS_HS_READY = 0x22
CTOS_HS_NOTREADY = 0x23
CTOS_HS_KICK = 0x24
CTOS_HS_START = 0x25
CTOS_REMATCH_RESPONSE = 0xF0

# --- server to client ---
STOC_GAME_MSG = 0x01
STOC_ERROR_MSG = 0x02
STOC_SELECT_HAND = 0x03
STOC_SELECT_TP = 0x04
STOC_HAND_RESULT = 0x05
STOC_TP_RESULT = 0x06
STOC_CHANGE_SIDE = 0x07
STOC_WAITING_SIDE = 0x08
STOC_CREATE_GAME = 0x11
STOC_JOIN_GAME = 0x12
STOC_TYPE_CHANGE = 0x13
STOC_LEAVE_GAME = 0x14
STOC_DUEL_START = 0x15
STOC_DUEL_END = 0x16
STOC_REPLAY = 0x17
STOC_TIME_LIMIT = 0x18
STOC_CHAT = 0x19
STOC_HS_PLAYER_ENTER = 0x20
STOC_HS_PLAYER_CHANGE = 0x21
STOC_HS_WATCH_CHANGE = 0x22
STOC_NEW_REPLAY = 0x30
STOC_CATCHUP = 0xF0
STOC_REMATCH = 0xF1
STOC_WAITING_REMATCH = 0xF2
STOC_CHAT_2 = 0xF3

PACKET_NAMES = {v: k for k, v in globals().items() if k.startswith(("CTOS_", "STOC_")) and isinstance(v, int)}

PLAYERCHANGE_OBSERVE = 0x8
PLAYERCHANGE_READY = 0x9
PLAYERCHANGE_NOTREADY = 0xA
PLAYERCHANGE_LEAVE = 0xB

ERRMSG_JOINERROR = 0x1
ERRMSG_DECKERROR = 0x2
ERRMSG_SIDEERROR = 0x3
ERRMSG_VERERROR = 0x4
ERRMSG_VERERROR2 = 0x5
JOINERROR_UNABLE, JOINERROR_PASSWORD, JOINERROR_REFUSED = 0, 1, 2

NETPLAYER_TYPE_OBSERVER = 7
TYPE_HOST_FLAG = 0x10  # STOC_TYPE_CHANGE: this client is the room host

CHAT2_DUELIST, CHAT2_OBSERVER, CHAT2_SYSTEM, CHAT2_SYSTEM_ERROR, CHAT2_SYSTEM_SHOUT = 0, 1, 2, 3, 4
CHAT_SYSTEM_PLAYER = 8  # STOC_CHAT "player" value for a system message

SERVER_HANDSHAKE = 4043399681
NETWORK_SERVER_ID = 0x7428
NETWORK_CLIENT_ID = 0xDEF6
PRO_VERSION = 0x1354  # EDOPro 41.x sends this as CTOS_JoinGame.version; WindBot sends its Version's low 16 bits
LAN_DISCOVERY_PORT, LAN_REPLY_PORT = 7920, 7921
MAX_PAYLOAD = 0xFFFF - 1


class ProtocolError(ValueError):
    pass


# --- framing -----------------------------------------------------------------------------------------------

def frame(packet_id: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError(f"packet {PACKET_NAMES.get(packet_id, packet_id)} too big ({len(payload)} bytes)")
    return struct.pack("<HB", len(payload) + 1, packet_id) + payload


class PacketReader:
    """Incremental de-framer: feed bytes, get (id, payload) tuples. Empty packets are skipped, as EDOPro does."""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        self._buf += data
        out = []
        while len(self._buf) >= 2:
            (n,) = struct.unpack_from("<H", self._buf, 0)
            if len(self._buf) < 2 + n:
                break
            body = bytes(self._buf[2:2 + n])
            del self._buf[:2 + n]
            if n:
                out.append((body[0], body[1:]))
        return out


# --- structs -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ClientVersion:
    client_major: int = 41
    client_minor: int = 0
    core_major: int = 11
    core_minor: int = 0

    def pack(self) -> bytes:
        return bytes((self.client_major, self.client_minor, self.core_major, self.core_minor))

    @classmethod
    def unpack(cls, b: bytes) -> "ClientVersion":
        return cls(*b[:4])

    @property
    def as_int(self) -> int:
        """WindBot's Version= argument (720937 for 41.0 / 11.0)."""
        return self.client_major | self.client_minor << 8 | self.core_major << 16 | self.core_minor << 24


_HOSTINFO = struct.Struct("<IBBBBB3xIBBHII4siiiIIH6H2x")


@dataclass
class HostInfo:
    lflist: int = 0
    rule: int = 4                 # allowed cards (deck.AllowedCards)
    mode: int = 0
    duel_rule: int = 0
    no_check_deck_content: int = 0
    no_shuffle_deck: int = 0
    start_lp: int = 8000
    start_hand: int = 5
    draw_count: int = 1
    time_limit: int = 0
    duel_flags: int = 0           # split into duel_flag_low / duel_flag_high on the wire
    handshake: int = SERVER_HANDSHAKE
    version: ClientVersion = field(default_factory=ClientVersion)
    team1: int = 1
    team2: int = 1
    best_of: int = 1
    forbidden_types: int = 0
    extra_rules: int = 0
    sizes: tuple[int, int, int, int, int, int] = (40, 60, 0, 15, 0, 15)

    SIZE = _HOSTINFO.size  # 68

    def pack(self) -> bytes:
        return _HOSTINFO.pack(self.lflist, self.rule, self.mode, self.duel_rule, self.no_check_deck_content,
                              self.no_shuffle_deck, self.start_lp, self.start_hand, self.draw_count,
                              self.time_limit, (self.duel_flags >> 32) & 0xFFFFFFFF, self.handshake,
                              self.version.pack(), self.team1, self.team2, self.best_of,
                              self.duel_flags & 0xFFFFFFFF, self.forbidden_types, self.extra_rules, *self.sizes)

    @classmethod
    def unpack(cls, b: bytes) -> "HostInfo":
        (lfl, rule, mode, drule, nocheck, noshuf, lp, hand, draw, tl, fhigh, hs, ver, t1, t2, bo, flow, forb,
         extra, *sizes) = _HOSTINFO.unpack_from(b, 0)
        return cls(lfl, rule, mode, drule, nocheck, noshuf, lp, hand, draw, tl, fhigh << 32 | flow, hs,
                   ClientVersion.unpack(ver), t1, t2, bo, forb, extra, tuple(sizes))


@dataclass
class JoinGame:
    version: int        # u16 PRO_VERSION
    game_id: int
    password: str
    version2: ClientVersion

    SIZE = 52

    @classmethod
    def unpack(cls, b: bytes) -> "JoinGame":
        if len(b) < cls.SIZE:
            raise ProtocolError(f"CTOS_JOIN_GAME too short ({len(b)} bytes)")
        ver, gid = struct.unpack_from("<H2xI", b, 0)
        return cls(ver, gid, read_utf16(b[8:48]), ClientVersion.unpack(b[48:52]))

    def pack(self) -> bytes:
        return struct.pack("<H2xI", self.version, self.game_id) + utf16_field(self.password, 20) + \
            self.version2.pack()


def player_info(name: str) -> bytes:
    return utf16_field(name, 20)


def parse_player_info(b: bytes) -> str:
    return read_utf16(b[:40])


def update_deck(main_and_extra: list[int], side: list[int]) -> bytes:
    codes = list(main_and_extra) + list(side)
    return struct.pack(f"<ii{len(codes)}I", len(main_and_extra), len(side), *codes)


def parse_update_deck(b: bytes) -> tuple[list[int], list[int]]:
    """CTOS_UPDATE_DECK → (main + extra, side). Raises ProtocolError on a bad size, like EDOPro INVALIDSIZE."""
    if len(b) < 8:
        raise ProtocolError("deck packet too short")
    mainc, sidec = struct.unpack_from("<II", b, 0)
    if mainc + sidec > (len(b) - 8) // 4:
        raise ProtocolError("deck packet size mismatch")
    codes = struct.unpack_from(f"<{mainc + sidec}I", b, 8)
    return list(codes[:mainc]), list(codes[mainc:])


def player_enter(name: str, pos: int) -> bytes:
    return utf16_field(name, 20) + bytes((pos, 0))  # sizeof(STOC_HS_PlayerEnter) == 42


def parse_player_enter(b: bytes) -> tuple[str, int]:
    return read_utf16(b[:40]), b[40]


def player_change(pos: int, state: int) -> bytes:
    return bytes(((pos << 4) | state,))


def watch_change(count: int) -> bytes:
    return struct.pack("<H", count)


def time_limit(player: int, left: int) -> bytes:
    return struct.pack("<BxH", player, max(0, min(left, 0xFFFF)))


def chat2(kind: int, is_team: bool, name: str, text: str) -> bytes:
    return bytes((kind, 1 if is_team else 0)) + utf16_field(name, 20) + utf16_text(text, 256)


def parse_chat2(b: bytes) -> tuple[int, bool, str, str]:
    return b[0], bool(b[1]), read_utf16(b[2:42]), read_utf16(b[42:])


def chat(player: int, text: str) -> bytes:
    return struct.pack("<H", player) + utf16_text(text, 256)


def parse_chat(b: bytes) -> tuple[int, str]:
    return struct.unpack_from("<H", b, 0)[0], read_utf16(b[2:])


def deck_error(error_type: int, code: int = 0, current: int = 0, minimum: int = 0, maximum: int = 0) -> bytes:
    """STOC_ERROR_MSG with a DeckError (24 bytes)."""
    return struct.pack("<B3xIIIII", ERRMSG_DECKERROR, error_type, current, minimum, maximum, code)


def join_error(error: int) -> bytes:
    return struct.pack("<B3xI", ERRMSG_JOINERROR, error)


def version_error(version: ClientVersion) -> bytes:
    return struct.pack("<B3x", ERRMSG_VERERROR2) + version.pack()


def side_error() -> bytes:
    return struct.pack("<B3xI", ERRMSG_SIDEERROR, 0)


def host_packet(port: int, name: str, info: HostInfo) -> bytes:
    """LAN discovery reply (HostPacket): identifier, version, port, ipaddr, name[20], HostInfo."""
    return struct.pack("<HHH2xI", NETWORK_SERVER_ID, PRO_VERSION, port, 0) + utf16_field(name, 20) + info.pack()


HOST_PACKET_SIZE = 52 + HostInfo.SIZE  # 120
