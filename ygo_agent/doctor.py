"""ygo-agent doctor: a setup check for a first-time user.

Each check looks at one thing (Python, the config, the EDOPro install and its core, mono and WindBot, the backend
profiles, the decks, the ports) and returns a Result per report line, with a hint saying what to do when something
is off. `run()` calls them in order and turns an unexpected exception into a FAIL line, so the report always
completes; `main()` prints it (`--json` for scripts) and exits 1 when anything failed.
"""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass

from .agent.rules import load_rules
from . import decks, paths
from .config import ConfigError, DEFAULT_PATH, LOCAL_PATH, load_config

OK, WARN, FAIL, SKIP = "ok", "warn", "FAIL", "skip"
MIN_PYTHON = (3, 11)
SAMPLE_SCRIPT = ("c55144522.lua", "Pot of Greed")  # a card script every install has (Normal Monsters have none)
HTTP_TIMEOUT = 3    # seconds, for an OpenAI-compatible server's /models
TOOL_TIMEOUT = 15   # seconds, for `mono --version` and `claude --version`

short = decks.short  # repo-relative inside the checkout, ~-abbreviated under the home folder


@dataclass
class Result:
    name: str
    status: str
    detail: str
    hint: str = ""


class Setup:
    """What the checks share: how the config is loaded (as the commands load it) and what earlier checks found."""

    def __init__(self, local=LOCAL_PATH, overrides=None):
        self.local = local
        self.overrides = overrides or {}
        self.cfg = None       # set by check_config (the defaults when the local file is broken)
        self.install = None   # set by check_edopro: the EdoproInstall, when the folder exists


def _n(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def _first_line(cmd):
    """The first line a tool prints for `cmd` (its version), or "" when it can't be run."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for line in (proc.stdout + proc.stderr).splitlines():
        if line.strip():
            return line.strip()
    return ""


def _local_sets(setup, key):
    """Whether the local config file sets a top-level key (to say where a value came from)."""
    try:
        with open(setup.local, "rb") as f:
            return key in tomllib.load(f)
    except (OSError, TypeError, tomllib.TOMLDecodeError):
        return False


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # a port in TIME_WAIT is free, one in LISTEN isn't
        try:
            s.bind(("", int(port)))
        except OSError:
            return False
    return True


# ---- the checks, in report order ----

def check_python(setup):
    v = sys.version_info
    detail = f"Python {v[0]}.{v[1]}.{v[2]} ({sys.executable}); ygo-agent at {paths.ROOT}"
    if tuple(v[:2]) < MIN_PYTHON:
        return Result("python", FAIL, detail, f"ygo-agent needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer: "
                                              "make the venv with a newer python3")
    return Result("python", OK, detail)


def check_config(setup):
    files = [short(DEFAULT_PATH)]
    local = setup.local
    try:
        setup.cfg = load_config(local=local, overrides=setup.overrides)
    except ConfigError as e:
        setup.cfg = load_config(local=None, overrides=setup.overrides)  # the report goes on with the defaults
        return Result("config", FAIL, str(e), f"fix {short(local)}; the checks below use the defaults")
    backend = f"agent.backend = {setup.cfg['agent']['backend']}"
    if local and os.path.exists(local):
        files.append(short(local))
    elif local and local != LOCAL_PATH:
        return Result("config", WARN, f"{files[0]} only; {backend}", f"--config {short(local)} does not exist")
    else:
        files.append("no config.local.toml")
    return Result("config", OK, f"{' + '.join(files)}; {backend}")


def check_edopro(setup):
    from .core.install import ENV_VAR, EdoproInstall, InstallError
    root = paths.resolve(setup.cfg["edopro_dir"])
    if "edopro_dir" in setup.overrides:
        source = "--edopro-dir"
    elif _local_sets(setup, "edopro_dir"):
        source = short(setup.local)
    else:
        source = f"the default in {short(DEFAULT_PATH)}"
    env = os.environ.get(ENV_VAR)
    note = ""
    if env and paths.resolve(env) != root:  # the commands read edopro_dir from the config, not the variable
        note = f"; ${ENV_VAR}={env} differs and is not what the commands use"
    try:
        setup.install = EdoproInstall.find(root)
    except InstallError:
        return Result("edopro", FAIL, f"{root} ({source}) is not a folder{note}",
                      "install EDOPro (Project Ignis) and set edopro_dir in config.local.toml, or pass --edopro-dir")
    repos = ", ".join(r.name for r in setup.install.repos) or "none"
    return Result("edopro", OK, f"{short(root)} ({source}); repositories: {repos}{note}")


def check_core(setup):
    if setup.install is None:
        return Result("core", SKIP, "no EDOPro install")
    from .core.ocgcore import CoreError, OcgCore
    found = setup.install.core_candidates()
    if not found:
        return Result("core", FAIL, f"no libocgcore.so in {short(setup.install.root)} or its repositories",
                      "start EDOPro once so it downloads the core (repositories/*/bin/libocgcore.so)")
    path = found[0]
    try:
        core = OcgCore(path)
    except (OSError, AttributeError, CoreError) as e:
        text = str(e) if str(e).startswith(path) else f"{short(path)}: {e}"
        return Result("core", FAIL, text, "ygo-agent needs the Linux build of EDOPro's core (ocgcore API 11): "
                                          "start EDOPro once so it updates it")
    return Result("core", OK, f"{short(path)}: ocgcore API {core.version[0]}.{core.version[1]}")


def check_cards(setup):
    if setup.install is None:
        return Result("cards", SKIP, "no EDOPro install")
    from .core.cards import CardDatabase
    cdbs = setup.install.cdb_paths
    if not cdbs:
        return Result("cards", FAIL, f"no .cdb files in {short(setup.install.root)}/expansions or its repositories",
                      "start EDOPro once so it downloads the card databases")
    try:
        count = len(CardDatabase(cdbs))
    except sqlite3.Error as e:
        return Result("cards", FAIL, f"{_n(len(cdbs), '.cdb file')}, one can't be read: {e}",
                      "delete the broken file and start EDOPro once so it downloads it again")
    strings = setup.install.strings_paths
    detail = f"{_n(len(cdbs), '.cdb file')}, {_n(count, 'card')}; strings.conf {'found' if strings else 'missing'}"
    if not count:
        return Result("cards", FAIL, detail, "the databases are empty: start EDOPro once so it downloads them")
    if not strings:
        return Result("cards", WARN, detail, "config/strings.conf names counters and archetypes in the prompts: "
                                             "start EDOPro once to restore it")
    return Result("cards", OK, detail)


def check_scripts(setup):
    if setup.install is None:
        return Result("scripts", SKIP, "no EDOPro install")
    from .core.scripts import ScriptLoader
    dirs = setup.install.script_dirs
    loader = ScriptLoader(dirs)
    names = ["constant.lua", "utility.lua", SAMPLE_SCRIPT[0]]
    missing = [n for n in names if loader.find(n) is None]
    where = f"{_n(len(dirs), 'script folder')} under {short(setup.install.root)}"
    if missing:
        return Result("scripts", FAIL, f"{where}; missing {', '.join(missing)}",
                      "start EDOPro once so it downloads the scripts (script/ and repositories/*/script)")
    sample = os.path.dirname(loader.find(SAMPLE_SCRIPT[0]))
    return Result("scripts", OK, f"{where}; constant.lua, utility.lua and {SAMPLE_SCRIPT[0]} ({SAMPLE_SCRIPT[1]}, "
                                 f"in {short(sample)}) found")


def check_pics(setup):
    if setup.install is None:
        return Result("pics", SKIP, "no EDOPro install")
    folder = os.path.join(setup.install.root, "pics")
    cache = os.path.join(paths.CACHE, "pics")
    if setup.cfg.get("web", {}).get("fetch_pics", True):
        tail = f"the web panel downloads missing ones to {short(cache)}"
    else:
        tail = "web.fetch_pics = false: the web panel shows placeholders for missing ones"
    try:
        count = sum(1 for e in os.scandir(folder) if e.is_file())
    except OSError:
        return Result("pics", WARN, f"no {short(folder)} folder; {tail}",
                      "optional: EDOPro downloads card pictures as you play")
    return Result("pics", OK, f"{short(folder)}: {_n(count, 'picture')}; {tail}")


def check_mono(setup):
    out = []
    mono = shutil.which("mono")
    if mono is None:
        out.append(Result("mono", WARN, "not on PATH", "install mono (dnf install mono-core / apt install mono-runtime) "
                                                       "to run WindBot: play --join and WindBot opponents need it"))
    else:
        out.append(Result("mono", OK, f"{_first_line([mono, '--version']) or 'version unknown'} at {mono}"))
    tools = {t: shutil.which(t) for t in ("xbuild", "mcs")}
    missing = [t for t, path in tools.items() if path is None]
    if missing:
        out.append(Result("mono build tools", WARN, f"missing {', '.join(missing)} (only needed to rebuild the WindBot "
                                                    "fork)", "install mono-devel for ./build.sh"))
    else:
        out.append(Result("mono build tools", OK, f"{tools['xbuild']}, {tools['mcs']}"))
    return out


def check_windbot(setup):
    from .arena.windbot import WindBotError, WindBotInstall
    out = []
    src, exe = paths.WINDBOT, paths.WINDBOT_EXE
    if not os.path.isfile(os.path.join(src, "WindBot.csproj")):
        out.append(Result("windbot fork", WARN, f"{short(src)} is missing or empty",
                          "git submodule update --init, then ./build.sh (play --join needs the fork; WindBot "
                          "opponents also work with EDOPro's own WindBot)"))
    elif not os.path.isfile(exe):
        out.append(Result("windbot fork", WARN, f"{short(src)} present, {short(exe)} not built",
                          "./build.sh (needs mono-devel: xbuild)"))
    else:
        built = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(exe)))
        out.append(Result("windbot fork", OK, f"{short(exe)} (built {built})"))
    root = setup.install.root if setup.install else None
    try:
        wb = WindBotInstall.find(root)
        what = "the fork" if wb.is_fork else "EDOPro's own WindBot"
        out.append(Result("windbot opponents", OK, f"{what}: {short(wb.exe)}, {_n(len(wb.bots()), 'deck AI')}"))
    except WindBotError as e:
        bundled = short(os.path.join(root, "WindBot")) if root else "EDOPro's WindBot folder"
        out.append(Result("windbot opponents", WARN, f"no WindBot.exe in {short(src)} or {bundled}: {e}",
                          "selfplay/teach/coach against windbot:<deck> need one: ./build.sh, or install EDOPro's "
                          "WindBot"))
    return out


def _check_claude_code(p):
    cmd = p.get("command", "claude")
    model = f"model {p.get('model') or 'opus'}" + (f", effort {p['effort']}" if p.get("effort") else "")
    path = shutil.which(cmd)
    if path is None:
        return FAIL, f"{model}; `{cmd}` is not on PATH", ("install Claude Code (npm install -g "
                                                          "@anthropic-ai/claude-code) and log in, or pick another "
                                                          "backend (--backend, agent.backend)")
    return OK, f"{model}; {cmd} {_first_line([path, '--version']) or 'version unknown'} at {path}", ""


def _check_anthropic(p):
    env = p.get("api_key_env") or "ANTHROPIC_API_KEY"
    model = f"model {p.get('model') or 'opus'}"
    if os.environ.get(env):
        return OK, f"{model}; ${env} is set", ""
    return FAIL, f"{model}; ${env} is not set", (f"export {env}=<your key> in the shell that runs ygo-agent (the "
                                                 "key is never logged)")


def _check_openai(p):
    base = (p.get("base_url") or "http://localhost:11434/v1").rstrip("/")
    url = base + ("/models" if base.endswith("/v1") else "/v1/models")
    model = p.get("model") or "?"
    headers = dict(p.get("headers") or {})
    env = p.get("api_key_env")
    key_note = ""
    if env and os.environ.get(env):
        headers["Authorization"] = f"Bearer {os.environ[env]}"
    elif env:
        key_note = f"; ${env} is not set"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=HTTP_TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        return WARN, f"model {model}; {url}: HTTP {e.code}{key_note}", ("the server is up but refused the request: "
                                                                        "check api_key_env and base_url")
    except (OSError, ValueError) as e:  # URLError and timeouts are OSErrors; a bad URL is a ValueError
        reason = getattr(e, "reason", e)
        return WARN, f"model {model}; {url}: unreachable ({reason}){key_note}", (
            "start the server (e.g. `ollama serve`) or fix base_url; harmless unless you use this profile")
    try:
        served = [m.get("id") for m in json.loads(body).get("data", []) if isinstance(m, dict)]
    except (ValueError, AttributeError):
        served = []
    detail = f"model {model}; {url}: {_n(len(served), 'model') if served else 'reachable'}{key_note}"
    if key_note:
        return WARN, detail, f"export {env}=<your key>; the server answered without it"
    if served and model not in served:
        return WARN, f"{detail}, {model} not among them", (f"pull or load the model (e.g. `ollama pull {model}`), or "
                                                           "set model to one the server has")
    return OK, detail, ""


_BACKEND_CHECKS = {"claude-code": _check_claude_code, "anthropic": _check_anthropic, "openai": _check_openai,
                   "heuristic": lambda p: (OK, "no model needed", ""), "random": lambda p: (OK, "no model needed", ""),
                   "scripted": lambda p: (OK, "for the tests", "")}


def check_backends(setup):
    from .backends import TYPES
    default = setup.cfg["agent"]["backend"]
    out = []
    for name, profile in setup.cfg.get("backends", {}).items():
        if not isinstance(profile, dict):
            continue
        label = f"backend {name}" + (" (default)" if name == default else "")
        kind = profile.get("type")
        checker = _BACKEND_CHECKS.get(kind)
        if checker is None:
            out.append(Result(label, FAIL, f"unknown type {kind!r}", f"type must be one of {', '.join(TYPES)}"))
            continue
        status, detail, hint = checker(profile)
        if status == FAIL and name != default:  # only the profile in use has to work
            status = WARN
        out.append(Result(label, status, f"{kind}: {detail}", hint))
    return out


def _rules_error(folder):
    """Why a deck's rules.py doesn't import, or None when it does (the listing only parses it; the doctor is the
    one command that imports every deck's rules to check them)."""
    path = os.path.join(folder, "rules.py")
    if not os.path.isfile(path):
        return None
    try:
        load_rules(path)
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None


def check_decks(setup):
    cfg = setup.cfg
    out = []
    rows = decks.listing(cfg)
    if not rows:
        out.append(Result("decks", WARN, f"no deck profiles in {decks.where(cfg)}",
                          "a deck profile is a folder with deck.json, deck.ydk and playbook.md (`ygo-agent train`)"))
    for row in rows:
        name, key, folder = f"deck {row['key']}", row["key"], row["dir"]
        where = row["location"]
        if row.get("error"):
            out.append(Result(name, FAIL, f"{where}: {row['error']}", f"fix deck.json in {short(folder)}"))
            continue
        if row.get("clash") == "shadowed":
            out.append(Result(name, SKIP, f"{where}: shadowed by the {decks.preference(cfg)} copy ([decks] prefer)"))
            continue
        size = f"{row['playbook_bytes'] / 1024:.1f} KB" if row["playbook_bytes"] else "none"
        rules = "? rules" if row["rules"] is None else _n(row["rules"], "rule")
        detail = f"{where}: playbook {size}, {rules}, {_n(row['tests'], 'case')}, ydk {short(row['ydk'])}"
        if row.get("clash") == "clash":
            out.append(Result(name, FAIL, f"{detail}; a deck of this name is in both deck dirs",
                              'rename one, or set [decks] prefer = "user" or "repo" in config.local.toml'))
        elif (error := _rules_error(folder)) is not None:
            out.append(Result(name, FAIL, f"{detail}; rules.py: {error}",
                              f"fix {short(os.path.join(folder, 'rules.py'))} so that it imports"))
        elif not row["ydk_ok"]:
            out.append(Result(name, FAIL, f"{detail} (missing)",
                              f"put the deck list there, or fix [decks.{key}] ydk in config.local.toml"))
        elif not row["playbook_bytes"]:
            out.append(Result(name, WARN, detail, "write a playbook.md (or `ygo-agent train`): without one the "
                                                  "model plays on card texts alone"))
        else:
            out.append(Result(name, OK, detail))
    user = decks.user_dir(cfg)
    if os.path.isdir(user):
        count = sum(1 for d in decks.scan(cfg) if d.location == "user")
        out.append(Result("user decks dir", OK, f"{short(user)}: {_n(count, 'deck')}"))
    else:
        out.append(Result("user decks dir", OK, f"{short(user)}: not created yet (`ygo-agent train` writes there)"))
    return out


def check_ports(setup):
    cfg = setup.cfg
    ports = [("arena room", cfg["room"]["port"]), ("bot bridge", cfg["bot"]["brain_port"]),
             ("web panel", cfg["web"]["port"])]
    listed = ", ".join(f"{label} {port}" for label, port in ports)
    busy = [f"{label} {port}" for label, port in ports if not _port_free(port)]
    if busy:
        return Result("ports", WARN, f"in use: {', '.join(busy)} (of {listed})",
                      "another program, or a running ygo-agent, listens there: stop it, or pick other ports (--port, "
                      "--brain-port, --web-port, or [room]/[bot]/[web] in config.local.toml)")
    return Result("ports", OK, f"free: {listed}")


CHECKS = [check_python, check_config, check_edopro, check_core, check_cards, check_scripts, check_pics, check_mono,
          check_windbot, check_backends, check_decks, check_ports]


# ---- running and printing ----

def run(setup=None):
    """Every check in order; an exception inside one becomes a FAIL line instead of ending the report."""
    setup = setup or Setup()
    results = []
    for check in CHECKS:
        try:
            out = check(setup)
        except Exception as e:  # a check must never take the report down
            out = Result(check.__name__.removeprefix("check_"), FAIL, f"{type(e).__name__}: {e}",
                         "unexpected; please report it with the output of `ygo-agent doctor --json`")
        results += out if isinstance(out, list) else [out]
    return results


def summary(results):
    counts = {s: sum(1 for r in results if r.status == s) for s in (OK, WARN, FAIL, SKIP)}
    text = f"{counts[OK]} ok, {counts[WARN]} warnings, {counts[FAIL]} failures"
    return text + (f", {counts[SKIP]} skipped" if counts[SKIP] else "")


def report(results):
    """The report: one line per result, a hint line under anything that isn't ok, the summary last."""
    from .agent.gamelog import paint, BOLD, DIM, GREEN, RED, YELLOW
    colors = {OK: GREEN, WARN: YELLOW, FAIL: RED, SKIP: DIM}
    width = max(len(r.name) for r in results)
    lines = []
    for r in results:
        mark = paint(colors[r.status], f"{r.status:<4}")
        lines.append(f"{mark}  {r.name:<{width}}  {r.detail}")
        if r.hint:
            lines.append(f"{'':<{width + 6}}  → {r.hint}")
    lines.append(paint(BOLD, summary(results)))
    return "\n".join(lines)


def main(args):
    """`ygo-agent doctor`: print the report (or --json) and return the exit code (1 when anything failed)."""
    overrides = {"edopro_dir": args.edopro_dir} if getattr(args, "edopro_dir", None) else {}
    results = run(Setup(local=getattr(args, "config", None) or LOCAL_PATH, overrides=overrides))
    if getattr(args, "json", False):
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print(report(results))
    return 1 if any(r.status == FAIL for r in results) else 0
