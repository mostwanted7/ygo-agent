"""EDOPro core access: install discovery, the libocgcore binding, card data and scripts.

    engine = Engine.load()            # ~/Games/ProjectIgnis, or $YGO_AGENT_EDOPRO, or Engine.load(path)
    duel = engine.new_duel(seed=(1, 2, 3, 4), flags=DUEL_MODE_MR3)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from .cards import CardData, CardDatabase, Strings
from .install import EdoproInstall, InstallError
from .ocgcore import CoreDuel, CoreError, OcgCore
from .scripts import ScriptLoader

__all__ = ["CardData", "CardDatabase", "CoreDuel", "CoreError", "EdoproInstall", "Engine", "InstallError",
           "OcgCore", "ScriptLoader", "Strings"]

_shared: dict[tuple, "Engine"] = {}
_lock = threading.Lock()


@dataclass
class Engine:
    install: EdoproInstall
    core: OcgCore
    cards: CardDatabase
    scripts: ScriptLoader
    strings: Strings

    @classmethod
    def load(cls, edopro_dir: str | None = None, core_path: str | None = None) -> "Engine":
        """Load (once per process and directory) the core, all card databases and the script path."""
        install = EdoproInstall.find(edopro_dir)
        key = (install.root, core_path)
        with _lock:
            if key not in _shared:
                _shared[key] = cls(
                    install=install,
                    core=OcgCore(core_path or install.core_path),
                    cards=CardDatabase(install.cdb_paths),
                    scripts=ScriptLoader(install.script_dirs, install.init_scripts),
                    strings=Strings(install.strings_paths),
                )
            return _shared[key]

    def new_duel(self, *, seed, flags: int, team1=(8000, 5, 1), team2=(8000, 5, 1), log=None) -> CoreDuel:
        return CoreDuel(self.core, self.cards, self.scripts, seed=seed, flags=flags, team1=team1, team2=team2,
                        log=log)
