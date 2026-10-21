"""Lua script lookup the way EDOPro does it (Game::FindScript / ReadScript): first hit in the search path wins,
a UTF-8 BOM is skipped. Contents are cached, since every duel loads the same files again."""

from __future__ import annotations

import os

_BOM = b"\xef\xbb\xbf"


class ScriptLoader:
    def __init__(self, dirs: list[str], init_scripts: list[str] = ()):
        self.dirs = list(dirs)
        self.init_scripts = list(init_scripts)
        self._cache: dict[str, bytes | None] = {}

    def find(self, name: str) -> str | None:
        for d in self.dirs:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path
        return None

    def read(self, name: str) -> bytes | None:
        """Script contents without a BOM, or None when no file has that name."""
        if name in self._cache:
            return self._cache[name]
        path = self.find(name)
        data = None
        if path:
            with open(path, "rb") as f:
                data = f.read()
            if data.startswith(_BOM):
                data = data[3:]
        self._cache[name] = data
        return data
