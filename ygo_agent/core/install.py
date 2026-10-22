"""Where an EDOPro install keeps the core, card databases, scripts and banlists.

Mirrors how EDOPro itself finds them (gframe/game.cpp ParseGithubRepositories/PopulateResourcesDirectories):
repositories from config/configs.json and config/user_configs.json with `should_read`, each contributing its
`.cdb` files, a script folder, optionally a core (`has_core` + `core_path`) and banlists (`lflist_path`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import cached_property

DEFAULT_EDOPRO_DIR = "~/Games/ProjectIgnis"
ENV_VAR = "YGO_AGENT_EDOPRO"
CORE_NAMES = ("libocgcore.so", "libocgcore.dylib", "ocgcore.dll")


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Repo:
    name: str
    path: str
    data_path: str
    script_path: str
    core_path: str | None
    lflist_path: str | None


def _join(base: str, rel: str) -> str:
    return os.path.normpath(os.path.join(base, rel))


def _sorted_ci(names):
    return sorted(names, key=lambda s: s.lower())


def _subfolders(path: str, layers: int) -> list[str]:
    """Utils::FindSubfolders: sub-folders up to `layers` deep, full paths, sorted case-insensitively."""
    out = []
    try:
        entries = os.listdir(path)
    except OSError:
        return out
    for name in entries:
        full = os.path.join(path, name)
        if name in (".", "..") or not os.path.isdir(full):
            continue
        out.append(full)
        if layers > 1:
            out += _subfolders(full, layers - 1)
    return _sorted_ci(out)


def _files(path: str, ext: str) -> list[str]:
    try:
        return [os.path.join(path, f) for f in _sorted_ci(os.listdir(path))
                if f.lower().endswith(ext) and os.path.isfile(os.path.join(path, f))]
    except OSError:
        return []


@dataclass
class EdoproInstall:
    root: str
    repos: list[Repo] = field(default_factory=list)

    @classmethod
    def find(cls, root: str | None = None) -> "EdoproInstall":
        """`root`, else $YGO_AGENT_EDOPRO, else ~/Games/ProjectIgnis."""
        root = os.path.abspath(os.path.expanduser(root or os.environ.get(ENV_VAR) or DEFAULT_EDOPRO_DIR))
        if not os.path.isdir(root):
            raise InstallError(f"EDOPro directory not found: {root} (set edopro_dir in config.local.toml, pass "
                               f"--edopro-dir, or set ${ENV_VAR})")
        return cls(root, cls._read_repos(root))

    @staticmethod
    def _read_repos(root: str) -> list[Repo]:
        repos = []
        for name in ("user_configs.json", "configs.json"):  # EDOPro reads user configs first
            path = os.path.join(root, "config", name)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            for r in data.get("repos", []):
                if not r.get("should_read", True) or r.get("is_language") or "repo_path" not in r:
                    continue
                base = os.path.normpath(os.path.join(root, r["repo_path"]))
                if any(x.path == base for x in repos):
                    continue
                repos.append(Repo(
                    name=r.get("repo_name", base),
                    path=base,
                    data_path=_join(base, r.get("data_path", "")),
                    script_path=_join(base, r.get("script_path", "script")),
                    core_path=_join(base, r.get("core_path", "")) if r.get("has_core") else None,
                    lflist_path=_join(base, r["lflist_path"]) if "lflist_path" in r else None,
                ))
        return repos

    # --- the core ---
    def core_candidates(self) -> list[str]:
        """EDOPro prefers a repository's core (later repos first), then the one in the install root."""
        dirs = [r.core_path for r in reversed(self.repos) if r.core_path] + [self.root]
        return [os.path.join(d, n) for d in dirs for n in CORE_NAMES if os.path.isfile(os.path.join(d, n))]

    @cached_property
    def core_path(self) -> str:
        found = self.core_candidates()
        if not found:
            raise InstallError(f"no libocgcore found in {self.root} or its repositories")
        return found[0]

    # --- card data ---
    @cached_property
    def cdb_paths(self) -> list[str]:
        """Load order: expansions/*.cdb, then each repo's *.cdb. A later file overrides an earlier one."""
        paths = _files(os.path.join(self.root, "expansions"), ".cdb")
        for r in self.repos:
            paths += _files(r.data_path, ".cdb")
        return paths

    @cached_property
    def strings_paths(self) -> list[str]:
        paths = [os.path.join(self.root, "config", "strings.conf"),
                 os.path.join(self.root, "expansions", "strings.conf")]
        paths += [os.path.join(r.data_path, "strings.conf") for r in self.repos]
        return [p for p in paths if os.path.isfile(p)]

    # --- scripts ---
    @cached_property
    def script_dirs(self) -> list[str]:
        """Search order: [repo script subfolders (2 deep), repo script dir] for each repo (last repo first),
        then expansions/script and its subfolders, then script and its subfolders."""
        dirs: list[str] = []
        exp = os.path.join(self.root, "expansions", "script")
        dirs.append(exp)
        dirs += _subfolders(exp, 1)
        base = os.path.join(self.root, "script")
        dirs.append(base)
        dirs += _subfolders(base, 1)
        for r in self.repos:
            dirs = _subfolders(r.script_path, 2) + [r.script_path] + dirs
        return [d for d in dirs if os.path.isdir(d)]

    @cached_property
    def init_scripts(self) -> list[str]:
        """Optional init.lua files EDOPro runs after constant.lua/utility.lua."""
        paths = [os.path.join(self.root, "init.lua")]
        paths += [os.path.join(r.script_path, "init.lua") for r in self.repos]
        return [p for p in paths if os.path.isfile(p)]

    # --- banlists ---
    @cached_property
    def lflist_paths(self) -> list[str]:
        paths = [os.path.join(self.root, "expansions", "lflist.conf"), os.path.join(self.root, "lflist.conf")]
        paths += _files(os.path.join(self.root, "lflists"), ".conf")
        for r in self.repos:
            paths.append(os.path.join(r.data_path, "lflist.conf"))
            if r.lflist_path:
                paths += _files(r.lflist_path, ".conf")
        return [p for p in paths if os.path.isfile(p)]

    # --- other ---
    @property
    def deck_dir(self) -> str:
        return os.path.join(self.root, "deck")

    @property
    def replay_dir(self) -> str:
        return os.path.join(self.root, "replay")

    @property
    def windbot_dir(self) -> str:
        return os.path.join(self.root, "WindBot")
