"""ctypes binding for EDOPro's libocgcore, API 11.0 (ocgapi.h / ocgapi_types.h of edo9300/ygopro-core).

`OcgCore` is the loaded library (one per process). `CoreDuel` wraps one OCG_Duel handle with the card and
script readers wired in, the way EDOPro's Game::SetupDuel does it.
"""

from __future__ import annotations

import ctypes as C
import struct
from collections.abc import Callable, Iterable

from .cards import CardDatabase
from .constants import OCG_DUEL_CREATION_STATUS, OCG_LOG_TYPE_ERROR
from .scripts import ScriptLoader

SUPPORTED_MAJOR = 11

OCG_Duel = C.c_void_p


class OCG_CardData(C.Structure):
    _fields_ = [("code", C.c_uint32), ("alias", C.c_uint32), ("setcodes", C.POINTER(C.c_uint16)),
                ("type", C.c_uint32), ("level", C.c_uint32), ("attribute", C.c_uint32), ("race", C.c_uint64),
                ("attack", C.c_int32), ("defense", C.c_int32), ("lscale", C.c_uint32), ("rscale", C.c_uint32),
                ("link_marker", C.c_uint32)]


class OCG_Player(C.Structure):
    _fields_ = [("startingLP", C.c_uint32), ("startingDrawCount", C.c_uint32), ("drawCountPerTurn", C.c_uint32)]


DataReader = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.POINTER(OCG_CardData))
DataReaderDone = C.CFUNCTYPE(None, C.c_void_p, C.POINTER(OCG_CardData))
ScriptReader = C.CFUNCTYPE(C.c_int, C.c_void_p, OCG_Duel, C.c_char_p)
LogHandler = C.CFUNCTYPE(None, C.c_void_p, C.c_char_p, C.c_int)


class OCG_DuelOptions(C.Structure):
    _fields_ = [("seed", C.c_uint64 * 4), ("flags", C.c_uint64), ("team1", OCG_Player), ("team2", OCG_Player),
                ("cardReader", DataReader), ("payload1", C.c_void_p),
                ("scriptReader", ScriptReader), ("payload2", C.c_void_p),
                ("logHandler", LogHandler), ("payload3", C.c_void_p),
                ("cardReaderDone", DataReaderDone), ("payload4", C.c_void_p),
                ("enableUnsafeLibraries", C.c_uint8)]


class OCG_NewCardInfo(C.Structure):
    _fields_ = [("team", C.c_uint8), ("duelist", C.c_uint8), ("code", C.c_uint32), ("con", C.c_uint8),
                ("loc", C.c_uint32), ("seq", C.c_uint32), ("pos", C.c_uint32)]


class OCG_QueryInfo(C.Structure):
    _fields_ = [("flags", C.c_uint32), ("con", C.c_uint8), ("loc", C.c_uint32), ("seq", C.c_uint32),
                ("overlay_seq", C.c_uint32)]


class CoreError(RuntimeError):
    pass


class OcgCore:
    """The loaded core library. Raises CoreError when the API major version isn't 11."""

    def __init__(self, path: str):
        self.path = path
        lib = C.CDLL(path)
        sig = {
            "OCG_GetVersion": ([C.POINTER(C.c_int), C.POINTER(C.c_int)], None),
            "OCG_CreateDuel": ([C.POINTER(OCG_Duel), C.POINTER(OCG_DuelOptions)], C.c_int),
            "OCG_DestroyDuel": ([OCG_Duel], None),
            "OCG_DuelNewCard": ([OCG_Duel, C.POINTER(OCG_NewCardInfo)], None),
            "OCG_StartDuel": ([OCG_Duel], None),
            "OCG_DuelProcess": ([OCG_Duel], C.c_int),
            "OCG_DuelGetMessage": ([OCG_Duel, C.POINTER(C.c_uint32)], C.c_void_p),
            "OCG_DuelSetResponse": ([OCG_Duel, C.c_void_p, C.c_uint32], None),
            "OCG_LoadScript": ([OCG_Duel, C.c_char_p, C.c_uint32, C.c_char_p], C.c_int),
            "OCG_DuelQueryCount": ([OCG_Duel, C.c_uint8, C.c_uint32], C.c_uint32),
            "OCG_DuelQuery": ([OCG_Duel, C.POINTER(C.c_uint32), C.POINTER(OCG_QueryInfo)], C.c_void_p),
            "OCG_DuelQueryLocation": ([OCG_Duel, C.POINTER(C.c_uint32), C.POINTER(OCG_QueryInfo)], C.c_void_p),
            "OCG_DuelQueryField": ([OCG_Duel, C.POINTER(C.c_uint32)], C.c_void_p),
        }
        for name, (args, res) in sig.items():
            try:
                fn = getattr(lib, name)
            except AttributeError:
                raise CoreError(f"{path}: no {name}; not an EDOPro core with API {SUPPORTED_MAJOR}?") from None
            fn.argtypes, fn.restype = args, res
        self.lib = lib
        major, minor = C.c_int(), C.c_int()
        lib.OCG_GetVersion(C.byref(major), C.byref(minor))
        self.version = (major.value, minor.value)
        if major.value != SUPPORTED_MAJOR:
            raise CoreError(f"{path}: core API {major.value}.{minor.value}, this binding supports "
                            f"{SUPPORTED_MAJOR}.x")


LogCallback = Callable[[str, int], None]


def _check_seed(seed: Iterable[int]) -> tuple[int, int, int, int]:
    seed = tuple(int(s) & 0xFFFFFFFFFFFFFFFF for s in seed)
    if len(seed) != 4:
        raise ValueError("a core seed is 4 unsigned 64-bit integers")
    if not any(seed):
        raise ValueError("an all-zero core seed is rejected by the core")
    return seed


class CoreDuel:
    """One duel inside the core. Not thread-safe; use it from one thread."""

    def __init__(self, core: OcgCore, cards: CardDatabase, scripts: ScriptLoader, *, seed: Iterable[int],
                 flags: int, team1: tuple[int, int, int], team2: tuple[int, int, int],
                 log: LogCallback | None = None):
        self.core, self.cards, self.scripts = core, cards, scripts
        self.seed = _check_seed(seed)
        self.flags = flags
        self.log = log
        self.lua_errors: list[str] = []
        self.missing_scripts: list[str] = []
        self._setcodes: dict[int, C.Array] = {}
        lib = core.lib

        @DataReader
        def card_reader(_payload, code, data):
            card = cards.cards.get(code)
            if card is None:
                return  # the core keeps zeroed data: a card without data, like EDOPro
            d = data.contents
            d.code, d.alias, d.type = card.code, card.alias, card.type
            d.level = card.level & 0xFFFFFFFF
            d.attribute, d.race = card.attribute, card.race
            d.attack, d.defense = card.attack, card.defense
            d.lscale, d.rscale, d.link_marker = card.lscale, card.rscale, card.link_marker
            if card.setcodes:
                arr = self._setcodes.get(code)
                if arr is None:
                    arr = self._setcodes[code] = (C.c_uint16 * (len(card.setcodes) + 1))(*card.setcodes, 0)
                d.setcodes = C.cast(arr, C.POINTER(C.c_uint16))

        @DataReaderDone
        def card_reader_done(_payload, _data):
            pass  # setcode arrays stay cached in self._setcodes for the duel's lifetime

        @ScriptReader
        def script_reader(_payload, duel, name):
            return self._load_script(duel, name.decode())

        @LogHandler
        def log_handler(_payload, text, kind):
            msg = text.decode("utf-8", errors="replace")
            if kind == OCG_LOG_TYPE_ERROR:
                self.lua_errors.append(msg)
            if self.log:
                self.log(msg, kind)

        self._callbacks = (card_reader, card_reader_done, script_reader, log_handler)
        opts = OCG_DuelOptions()
        opts.seed = (C.c_uint64 * 4)(*self.seed)
        opts.flags = flags
        opts.team1 = OCG_Player(*team1)
        opts.team2 = OCG_Player(*team2)
        opts.cardReader, opts.cardReaderDone = card_reader, card_reader_done
        opts.scriptReader, opts.logHandler = script_reader, log_handler
        opts.enableUnsafeLibraries = 1  # as EDOPro's SetupDuel
        self._ptr = OCG_Duel()
        status = lib.OCG_CreateDuel(C.byref(self._ptr), C.byref(opts))
        if status != 0:
            raise CoreError(f"OCG_CreateDuel failed: {OCG_DUEL_CREATION_STATUS.get(status, status)}")
        # Like Game::SetupDuel: the API user loads constant.lua and utility.lua (which pulls in the rest), then
        # any init.lua.
        for base in ("constant.lua", "utility.lua"):
            if not self.load_script(base):
                self.close()
                raise CoreError(f"could not load {base} from {scripts.dirs[:3]}...")
        for path in scripts.init_scripts:
            with open(path, "rb") as f:
                data = f.read().removeprefix(b"\xef\xbb\xbf")
            lib.OCG_LoadScript(self._ptr, data, len(data), path.encode())

    # --- scripts ---
    def _load_script(self, duel, name: str) -> int:
        data = self.scripts.read(name)
        if data is None:
            if name != "c0.lua":  # the core asks for its placeholder card's script; EDOPro has none either
                self.missing_scripts.append(name)
            return 0
        return self.core.lib.OCG_LoadScript(duel, data, len(data), name.encode())

    def load_script(self, name: str) -> bool:
        return bool(self._load_script(self._ptr, name))

    def run_lua(self, code: str, name: str = " ") -> bool:
        """Run a Lua snippet in the duel (EDOPro uses this for `Debug.ReloadFieldEnd()`)."""
        data = code.encode()
        return bool(self.core.lib.OCG_LoadScript(self._ptr, data, len(data), name.encode()))

    # --- setup ---
    def new_card(self, team: int, code: int, location: int, sequence: int = 0, position: int = 0x8,
                 controller: int | None = None, duelist: int = 0) -> None:
        info = OCG_NewCardInfo(team, duelist, code, team if controller is None else controller, location,
                               sequence, position)
        self.core.lib.OCG_DuelNewCard(self._ptr, C.byref(info))

    def start(self) -> None:
        self.core.lib.OCG_StartDuel(self._ptr)

    # --- processing ---
    def process(self) -> int:
        return self.core.lib.OCG_DuelProcess(self._ptr)

    def messages(self) -> list[bytes]:
        """Pending core messages, each starting with its MSG_* byte."""
        n = C.c_uint32()
        p = self.core.lib.OCG_DuelGetMessage(self._ptr, C.byref(n))
        if not n.value:
            return []
        buf = C.string_at(p, n.value)
        out, off, end = [], 0, len(buf)
        unpack = struct.unpack_from
        while off < end:
            (size,) = unpack("<I", buf, off)
            out.append(buf[off + 4: off + 4 + size])
            off += 4 + size
        return out

    def set_response(self, data: bytes) -> None:
        self.core.lib.OCG_DuelSetResponse(self._ptr, data, len(data))

    # --- queries ---
    def query_count(self, team: int, location: int) -> int:
        return self.core.lib.OCG_DuelQueryCount(self._ptr, team, location)

    def query(self, con: int, location: int, sequence: int, flags: int, overlay_seq: int = 0) -> bytes | None:
        """One card's query buffer, or None when there is no card there."""
        info = OCG_QueryInfo(flags, con, location, sequence, overlay_seq)
        n = C.c_uint32()
        p = self.core.lib.OCG_DuelQuery(self._ptr, C.byref(n), C.byref(info))
        if not p:
            return None
        return C.string_at(p, n.value)

    def query_location(self, con: int, location: int, flags: int) -> bytes:
        """`u32 size` + one entry per card (a zero `u16` for an empty zone)."""
        info = OCG_QueryInfo(flags, con, location, 0, 0)
        n = C.c_uint32()
        p = self.core.lib.OCG_DuelQueryLocation(self._ptr, C.byref(n), C.byref(info))
        return C.string_at(p, n.value) if n.value else b""

    def query_field(self) -> bytes:
        n = C.c_uint32()
        p = self.core.lib.OCG_DuelQueryField(self._ptr, C.byref(n))
        return C.string_at(p, n.value) if n.value else b""

    # --- teardown ---
    @property
    def closed(self) -> bool:
        return not self._ptr

    def close(self) -> None:
        if self._ptr:
            self.core.lib.OCG_DestroyDuel(self._ptr)
            self._ptr = OCG_Duel()

    def __enter__(self) -> "CoreDuel":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
