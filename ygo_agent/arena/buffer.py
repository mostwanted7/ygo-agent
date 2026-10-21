"""Little-endian readers and writers for core messages, queries and network packets."""

from __future__ import annotations

import struct
from dataclasses import dataclass

_U8, _U16, _U32, _I32, _U64, _I16 = (struct.Struct(f) for f in ("<B", "<H", "<I", "<i", "<Q", "<h"))
_LOC = struct.Struct("<BBII")
_LOC_COMPACT = struct.Struct("<BBB")


class BufferUnderrun(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocInfo:
    """Where a card is (core loc_info): controller, location, sequence, position.

    For an Xyz material, `location` has LOCATION_OVERLAY set and `position` is its index under the monster."""
    controller: int
    location: int
    sequence: int
    position: int = 0

    def pack(self) -> bytes:
        return _LOC.pack(self.controller, self.location, self.sequence, self.position)


class Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes, pos: int = 0):
        self.buf, self.pos = buf, pos

    def _read(self, s: struct.Struct):
        try:
            v = s.unpack_from(self.buf, self.pos)[0]
        except struct.error:
            raise BufferUnderrun(f"need {s.size} bytes at offset {self.pos} of {len(self.buf)}") from None
        self.pos += s.size
        return v

    def u8(self) -> int:
        return self._read(_U8)

    def u16(self) -> int:
        return self._read(_U16)

    def i16(self) -> int:
        return self._read(_I16)

    def u32(self) -> int:
        return self._read(_U32)

    def i32(self) -> int:
        return self._read(_I32)

    def u64(self) -> int:
        return self._read(_U64)

    def loc(self) -> LocInfo:
        try:
            c, l, s, p = _LOC.unpack_from(self.buf, self.pos)
        except struct.error:
            raise BufferUnderrun(f"need a loc_info at offset {self.pos}") from None
        self.pos += 10
        return LocInfo(c, l, s, p)

    def loc_compact(self) -> LocInfo:
        """controller u8, location u8, sequence u8 (used by a few prompts)."""
        try:
            c, l, s = _LOC_COMPACT.unpack_from(self.buf, self.pos)
        except struct.error:
            raise BufferUnderrun(f"need 3 bytes at offset {self.pos}") from None
        self.pos += 3
        return LocInfo(c, l, s, 0)

    def bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise BufferUnderrun(f"need {n} bytes at offset {self.pos} of {len(self.buf)}")
        out = self.buf[self.pos:self.pos + n]
        self.pos += n
        return out

    def rest(self) -> bytes:
        out = self.buf[self.pos:]
        self.pos = len(self.buf)
        return out

    @property
    def remaining(self) -> int:
        return len(self.buf) - self.pos


class Writer:
    __slots__ = ("parts",)

    def __init__(self):
        self.parts: list[bytes] = []

    def u8(self, v: int) -> "Writer":
        self.parts.append(_U8.pack(v & 0xFF))
        return self

    def u16(self, v: int) -> "Writer":
        self.parts.append(_U16.pack(v & 0xFFFF))
        return self

    def i16(self, v: int) -> "Writer":
        self.parts.append(_I16.pack(v))
        return self

    def u32(self, v: int) -> "Writer":
        self.parts.append(_U32.pack(v & 0xFFFFFFFF))
        return self

    def i32(self, v: int) -> "Writer":
        self.parts.append(_I32.pack(v))
        return self

    def u64(self, v: int) -> "Writer":
        self.parts.append(_U64.pack(v & 0xFFFFFFFFFFFFFFFF))
        return self

    def loc(self, loc: LocInfo) -> "Writer":
        self.parts.append(loc.pack())
        return self

    def raw(self, b: bytes) -> "Writer":
        self.parts.append(b)
        return self

    def getvalue(self) -> bytes:
        return b"".join(self.parts)


def utf16_field(text: str, chars: int) -> bytes:
    """A fixed-size, NUL-terminated UTF-16LE field (EDOPro's `uint16_t name[20]` and friends)."""
    raw = text.encode("utf-16-le")[: 2 * (chars - 1)]
    return raw + b"\0" * (2 * chars - len(raw))


def utf16_text(text: str, max_chars: int = 256) -> bytes:
    """Variable-length UTF-16LE text plus its NUL, as BufferIO::CopyStr produces it (chat messages)."""
    raw = text.encode("utf-16-le")[: 2 * (max_chars - 1)]
    return raw + b"\0\0"


def read_utf16(buf: bytes) -> str:
    """Decode UTF-16LE up to the first NUL character."""
    out = buf[: len(buf) & ~1].decode("utf-16-le", errors="replace")
    i = out.find("\0")
    return out if i < 0 else out[:i]
