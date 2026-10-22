"""EDOPro replays: `.yrpX` files with the full message stream plus an embedded old-style `.yrp`.

EDOPro (gframe/replay.cpp, generic_duel.cpp) records two replays per duel:

* `.yrp` ("old" mode, REPLAY_YRP1): names, LP/hand/draw, duel flags, both decks in the order they were added
  to the core, and every response. EDOPro re-simulates it with the core (Replay mode, "old replay" checkbox).
* `.yrpX` (REPLAY_YRPX): names, duel flags, then the unfiltered message stream as the host saw it (prompts
  and private hints left out, field refreshes in), ending with an OLD_REPLAY_MODE packet that embeds the
  `.yrp`. This is what EDOPro's Replay mode plays by default and what it saves from a network duel.

Both start with an ExtendedReplayHeader (72 bytes, little-endian):
    u32 id, u32 version, u32 flag, u32 timestamp, u32 datasize, u32 hash, u8 props[8],
    u64 header_version (1), u64 seed[4]
and the body is raw LZMA (props byte 0x5D, 16 MiB dictionary) when REPLAY_COMPRESSED is set.
"""

from __future__ import annotations

import lzma
import struct
import time
from dataclasses import dataclass, field

from ..core.constants import OLD_REPLAY_MODE, Msg
from .buffer import Reader, read_utf16, utf16_field

REPLAY_COMPRESSED = 0x1
REPLAY_TAG = 0x2
REPLAY_DECODED = 0x4
REPLAY_SINGLE_MODE = 0x8
REPLAY_LUA64 = 0x10
REPLAY_NEWREPLAY = 0x20
REPLAY_HAND_TEST = 0x40
REPLAY_DIRECT_SEED = 0x80
REPLAY_64BIT_DUELFLAG = 0x100
REPLAY_EXTENDED_HEADER = 0x200
REPLAY_YRP1 = 0x31707279  # "yrp1"
REPLAY_YRPX = 0x58707279  # "yrpX"
DEFAULT_FLAGS = REPLAY_LUA64 | REPLAY_NEWREPLAY | REPLAY_64BIT_DUELFLAG | REPLAY_EXTENDED_HEADER

_HEADER = struct.Struct("<6I8sQ4Q")
HEADER_SIZE = _HEADER.size  # 72
_DICT_SIZE = 1 << 24
_LZMA_FILTERS = [{"id": lzma.FILTER_LZMA1, "dict_size": _DICT_SIZE, "lc": 3, "lp": 0, "pb": 2}]


def client_version(client: tuple[int, int] = (41, 0), core: tuple[int, int] = (11, 0)) -> int:
    """EDOPro's CLIENT_VERSION: client major/minor and core major/minor, one byte each (41.0 + 11.0 = 720937)."""
    return client[0] | client[1] << 8 | core[0] << 16 | core[1] << 24


class ReplayError(ValueError):
    pass


@dataclass
class ReplayHeader:
    id: int
    version: int
    flag: int
    timestamp: int
    datasize: int = 0
    hash: int = 0
    props: bytes = b"\0" * 8
    header_version: int = 1
    seed: tuple[int, int, int, int] = (0, 0, 0, 0)

    def pack(self) -> bytes:
        return _HEADER.pack(self.id, self.version, self.flag, self.timestamp, self.datasize, self.hash,
                            self.props.ljust(8, b"\0")[:8], self.header_version, *self.seed)


def _compress(data: bytes) -> tuple[bytes, bytes]:
    props = bytes([(2 * 5 + 0) * 9 + 3]) + struct.pack("<I", _DICT_SIZE) + b"\0\0\0"
    return lzma.compress(data, format=lzma.FORMAT_RAW, filters=_LZMA_FILTERS), props


def _decompress(data: bytes, props: bytes, size: int) -> bytes:
    d = props[0]
    lc, rest = d % 9, d // 9
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": struct.unpack_from("<I", props, 1)[0] or _DICT_SIZE,
                "lc": lc, "lp": rest % 5, "pb": rest // 5}]
    out = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filters).decompress(data, max_length=size)
    if len(out) != size:
        raise ReplayError(f"replay body decompressed to {len(out)} bytes, header says {size}")
    return out


def _serialize(header: ReplayHeader, body: bytes, compress: bool) -> bytes:
    h = ReplayHeader(**header.__dict__)
    h.datasize = len(body)
    if compress:
        body, h.props = _compress(body)
        h.flag |= REPLAY_COMPRESSED
    else:
        h.flag &= ~REPLAY_COMPRESSED
    return h.pack() + body


def _names_block(home: list[str], opposing: list[str]) -> bytes:
    out = [struct.pack("<I", len(home))] + [utf16_field(n, 20) for n in home]
    out += [struct.pack("<I", len(opposing))] + [utf16_field(n, 20) for n in opposing]
    return b"".join(out)


@dataclass
class ReplayRecorder:
    """Collects one duel's replay data as the duel driver runs."""
    seed: tuple[int, int, int, int]
    duel_flags: int
    start_lp: int
    start_hand: int
    draw_count: int
    names: tuple[list[str], list[str]]  # (team 0 duelists, team 1 duelists)
    timestamp: int = field(default_factory=lambda: int(time.time()))
    version: int = client_version()
    decks: list[tuple[list[int], list[int]]] = field(default_factory=list)  # in core insertion order
    rule_cards: list[int] = field(default_factory=list)
    packets: list[bytes] = field(default_factory=list)   # core messages, unfiltered, with their type byte
    responses: list[bytes] = field(default_factory=list)
    old_replay_valid: bool = True  # False for custom start states, which a .yrp can't describe

    def record(self, raw: bytes) -> None:
        self.packets.append(raw)

    def respond(self, data: bytes) -> None:
        if len(data) > 255:
            self.old_replay_valid = False  # the .yrp stores response lengths in one byte
        self.responses.append(bytes(data))

    def pop_response(self) -> None:
        if self.responses:
            self.responses.pop()

    def _header(self, rid: int) -> ReplayHeader:
        return ReplayHeader(rid, self.version, DEFAULT_FLAGS, self.timestamp, seed=self.seed)

    def yrp_body(self) -> bytes:
        parts = [_names_block(*self.names),
                 struct.pack("<IIIQ", self.start_lp, self.start_hand, self.draw_count, self.duel_flags)]
        for main, extra in self.decks:
            parts.append(struct.pack(f"<I{len(main)}I", len(main), *main))
            parts.append(struct.pack(f"<I{len(extra)}I", len(extra), *extra))
        parts.append(struct.pack(f"<I{len(self.rule_cards)}I", len(self.rule_cards), *self.rule_cards))
        parts += [bytes([len(r) & 0xFF]) + r for r in self.responses]
        return b"".join(parts)

    def yrp(self, compress: bool = True) -> bytes:
        return _serialize(self._header(REPLAY_YRP1), self.yrp_body(), compress)

    def yrpx_body(self, embed_yrp: bool = True) -> bytes:
        parts = [_names_block(*self.names), struct.pack("<Q", self.duel_flags)]
        for raw in self.packets:
            parts.append(struct.pack("<BI", raw[0], len(raw) - 1))
            parts.append(raw[1:])
        if embed_yrp and self.old_replay_valid:
            old = self.yrp(compress=True)
            parts.append(struct.pack("<BI", OLD_REPLAY_MODE, len(old)))
            parts.append(old)
        return b"".join(parts)

    def yrpx(self, compress: bool = True, embed_yrp: bool = True) -> bytes:
        return _serialize(self._header(REPLAY_YRPX), self.yrpx_body(embed_yrp), compress)


# --- comparing -----------------------------------------------------------------------------------------------

_UNORDERED = (Msg.CARD_HINT, Msg.PLAYER_HINT)


def _canonical(packets: list[bytes]) -> list:
    """Runs of consecutive card/player hint messages as sorted tuples: when an effect resets, the core emits
    their "description removed" hints while iterating pointer-keyed containers, so their order depends on
    memory layout and can differ between two runs of the same game (EDOPro's own replays included)."""
    out: list = []
    run: list[bytes] = []
    for p in packets:
        if p[0] in _UNORDERED:
            run.append(p)
            continue
        if run:
            out.append(tuple(sorted(run)))
            run = []
        out.append(p)
    if run:
        out.append(tuple(sorted(run)))
    return out


def streams_match(a: list[bytes], b: list[bytes]) -> bool:
    """True when two message streams describe the same game (identical, up to the order of hint messages)."""
    return a == b or _canonical(a) == _canonical(b)


# --- reading -----------------------------------------------------------------------------------------------

@dataclass
class Replay:
    header: ReplayHeader
    names: tuple[list[str], list[str]]
    duel_flags: int
    start_lp: int = 0
    start_hand: int = 0
    draw_count: int = 0
    decks: list[tuple[list[int], list[int]]] = field(default_factory=list)
    rule_cards: list[int] = field(default_factory=list)
    responses: list[bytes] = field(default_factory=list)
    packets: list[bytes] = field(default_factory=list)  # yrpX: messages with their type byte
    embedded: "Replay | None" = None                      # yrpX: the old-style replay inside it

    @property
    def is_streamed(self) -> bool:
        return self.header.id == REPLAY_YRPX

    @property
    def seed(self) -> tuple[int, int, int, int]:
        return self.header.seed

    @property
    def turns(self) -> int:
        return sum(1 for p in self.packets if p[0] == Msg.NEW_TURN)

    @property
    def old(self) -> "Replay | None":
        """The replay EDOPro's "old replay mode" would re-simulate."""
        return self if self.header.id == REPLAY_YRP1 else self.embedded


def _read_names(r: Reader, flag: int) -> tuple[list[str], list[str]]:
    teams = []
    for _ in range(2):
        n = r.u32() if flag & REPLAY_NEWREPLAY else (2 if flag & REPLAY_TAG else 1)
        teams.append([read_utf16(r.bytes(40)) for _ in range(n)])
    return teams[0], teams[1]


def parse_replay(data: bytes) -> Replay:
    """Parse a .yrp/.yrpX the way Replay::OpenReplayFromBuffer does."""
    if len(data) < 32:
        raise ReplayError("file too short for a replay header")
    rid, version, flag, ts, datasize, h = struct.unpack_from("<6I", data, 0)
    props = data[24:32]
    header_size, header_version, seed = 32, 0, (0, 0, 0, 0)
    if flag & REPLAY_EXTENDED_HEADER:
        if len(data) < HEADER_SIZE:
            raise ReplayError("truncated extended header")
        header_version = struct.unpack_from("<Q", data, 32)[0]
        seed = struct.unpack_from("<4Q", data, 40)
        header_size = HEADER_SIZE
    if rid not in (REPLAY_YRP1, REPLAY_YRPX):
        raise ReplayError(f"not an EDOPro replay (id {rid:#x})")
    header = ReplayHeader(rid, version, flag, ts, datasize, h, props, header_version, seed)
    body = data[header_size:]
    if flag & REPLAY_COMPRESSED:
        body = _decompress(body, props, datasize)
    r = Reader(body)
    names = _read_names(r, flag)
    rep = Replay(header, names, 0)
    if rid == REPLAY_YRP1:
        rep.start_lp, rep.start_hand, rep.draw_count = r.u32(), r.u32(), r.u32()
    rep.duel_flags = r.u64() if flag & REPLAY_64BIT_DUELFLAG else r.u32()
    if rid == REPLAY_YRP1:
        for _ in range(len(names[0]) + len(names[1])):
            main = [r.u32() for _ in range(r.u32())]
            extra = [r.u32() for _ in range(r.u32())]
            rep.decks.append((main, extra))
        if flag & REPLAY_NEWREPLAY:
            rep.rule_cards = [r.u32() for _ in range(r.u32())]
        while r.remaining:
            n = r.u8()
            if n == 0:
                break
            rep.responses.append(r.bytes(n))
        return rep
    while r.remaining >= 5:
        msg, n = r.u8(), r.u32()
        payload = r.bytes(n)
        if msg == OLD_REPLAY_MODE:
            rep.embedded = parse_replay(payload)
        else:
            rep.packets.append(bytes([msg]) + payload)
    if r.remaining:
        raise ReplayError(f"{r.remaining} trailing bytes in the replay stream")
    return rep


def read_replay(path: str) -> Replay:
    with open(path, "rb") as f:
        return parse_replay(f.read())
