"""ygo-agent doctor, the setup check (ygo_agent/doctor.py), against a fake EDOPro install under tmp_path."""

import argparse
import json
import os
import socket
import sqlite3
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ygo_agent import cli, doctor, paths
from ygo_agent.arena import windbot

# The tables core/cards.py reads (EDOPro's cards.cdb).
SCHEMA = ("create table datas(id integer primary key, ot integer, alias integer, setcode integer, type integer, "
          "atk integer, def integer, level integer, race integer, attribute integer, category integer);"
          "create table texts(id integer primary key, name text, desc text, " +
          ", ".join(f"str{i} text" for i in range(1, 17)) + ");")
POT_OF_GREED = 55144522


def make_cdb(path, cards=(POT_OF_GREED,)):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for code in cards:
        con.execute("insert into datas values (?, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0)", (code,))
        con.execute("insert into texts values (?, ?, ?" + ", ''" * 16 + ")", (code, f"Card {code}", "Draw 2 cards."))
    con.commit()
    con.close()


def make_install(root, core=b"not a shared library", cards=(POT_OF_GREED,), bundled_windbot=True):
    """A folder laid out like an EDOPro install: configs.json with one repository holding the core, a card
    database, the base scripts plus Pot of Greed's, one picture, and EDOPro's bundled WindBot."""
    (root / "config").mkdir(parents=True)
    (root / "config" / "configs.json").write_text(json.dumps({
        "repos": [{"repo_name": "fake repo", "repo_path": "./repositories/fake", "data_path": "",
                   "script_path": "script", "has_core": True, "core_path": "bin", "should_read": True}],
        "urls": [{"url": "default", "type": "pic"}]}))
    (root / "config" / "strings.conf").write_text("!system 1 test\n")
    (root / "expansions").mkdir()
    make_cdb(root / "expansions" / "cards.cdb", cards)
    (root / "script" / "official").mkdir(parents=True)
    for name in ("constant.lua", "utility.lua"):
        (root / "script" / name).write_text("-- base\n")
    (root / "script" / "official" / f"c{POT_OF_GREED}.lua").write_text("-- Pot of Greed\n")
    (root / "repositories" / "fake" / "bin").mkdir(parents=True)
    (root / "repositories" / "fake" / "script").mkdir()
    (root / "repositories" / "fake" / "bin" / "libocgcore.so").write_bytes(core)
    (root / "pics").mkdir()
    (root / "pics" / f"{POT_OF_GREED}.jpg").write_bytes(b"\xff\xd8\xff")
    if bundled_windbot:
        make_windbot(root / "WindBot")
    return root


def make_windbot(folder, bots=("Blue-Eyes",)):
    (folder / "Decks").mkdir(parents=True)
    (folder / "WindBot.exe").write_bytes(b"MZ")
    (folder / "bots.json").write_text(json.dumps([{"name": b, "deck": b} for b in bots]))


def make_tool(folder, name, output):
    """A fake command on PATH that prints `output` (its version line)."""
    path = folder / name
    path.write_text(f"#!/bin/sh\necho '{output}'\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def make_deck(root, key, rules="RULES = []\n", ydk=True, playbook=True):
    folder = root / key
    folder.mkdir(parents=True)
    (folder / "deck.json").write_text(json.dumps({"name": key.title(), "ydk": "deck.ydk"}))
    if ydk:
        (folder / "deck.ydk").write_text("#main\n55144522\n")
    if playbook:
        (folder / "playbook.md").write_text("# Playbook\n\nDraw.\n")
    if rules is not None:
        (folder / "rules.py").write_text(rules)
    return folder


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ModelsServer:
    """A GET /v1/models endpoint, as an OpenAI-compatible server answers it; records the requests."""

    def __init__(self, models=("fake-model",)):
        self.requests = []
        server = self
        body = json.dumps({"object": "list", "data": [{"id": m} for m in models]}).encode()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                server.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """A fake install, fake tools on PATH (mono, xbuild, mcs, claude), an empty windbot-src, one repo deck, and
    a config.local.toml pointing at all of it. Returns a dict the tests adjust before calling `run`."""
    install = make_install(tmp_path / "edopro")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_tool(bin_dir, "mono", "Mono JIT compiler version 9.9 (fake)")
    make_tool(bin_dir, "xbuild", "XBuild fake")
    make_tool(bin_dir, "mcs", "Mono C# compiler fake")
    make_tool(bin_dir, "claude", "9.9.9 (Claude Code fake)")
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DOCTOR_TEST_KEY", raising=False)
    monkeypatch.delenv("YGO_AGENT_EDOPRO", raising=False)
    fork = tmp_path / "windbot-src"
    monkeypatch.setattr(paths, "WINDBOT", str(fork))
    monkeypatch.setattr(paths, "WINDBOT_EXE", str(fork / "bin" / "Release" / "WindBot.exe"))
    monkeypatch.setattr(windbot, "FORK_EXE", str(fork / "bin" / "Release" / "WindBot.exe"))
    repo_decks = tmp_path / "repo-decks"
    make_deck(repo_decks, "fake")
    monkeypatch.setattr(paths, "DECKS", str(repo_decks))
    ports = {"room": free_port(), "bridge": free_port(), "web": free_port()}
    local = tmp_path / "config.local.toml"
    state = {"install": install, "bin": bin_dir, "fork": fork, "repo_decks": repo_decks, "local": local,
             "ports": ports, "user_decks": tmp_path / "user-decks", "tmp": tmp_path}
    write_local(state)
    return state


def write_local(state, backend="heuristic", extra=""):
    ports = state["ports"]
    state["local"].write_text(f"""
edopro_dir = "{state['install']}"
[decks]
user_dir = "{state['user_decks']}"
[room]
port = {ports['room']}
[bot]
brain_port = {ports['bridge']}
[web]
port = {ports['web']}
[agent]
backend = "{backend}"
[backends.cc]
type = "claude-code"
model = "opus"
[backends.api]
type = "anthropic"
api_key_env = "DOCTOR_TEST_KEY"
[backends.off]
type = "openai"
base_url = "http://127.0.0.1:{free_port()}/v1"
model = "nothing"
{extra}
""")


def run(state, **kw):
    results = doctor.run(doctor.Setup(local=str(state["local"]), **kw))
    assert all(r.status in (doctor.OK, doctor.WARN, doctor.FAIL, doctor.SKIP) for r in results)
    return {r.name: r for r in results}


def test_fake_install_is_read_like_a_real_one(fake):
    rows = run(fake)
    names = list(rows)
    assert names[:8] == ["python", "config", "edopro", "core", "cards", "scripts", "pics", "mono"]
    assert rows["python"].status == "ok" and paths.ROOT in rows["python"].detail
    assert rows["config"].status == "ok" and "agent.backend = heuristic" in rows["config"].detail
    assert doctor.short(str(fake["local"])) in rows["config"].detail
    assert rows["edopro"].status == "ok" and "fake repo" in rows["edopro"].detail
    assert doctor.short(str(fake["local"])) in rows["edopro"].detail  # where edopro_dir came from
    # The dummy core can't be loaded: reported, with a hint, instead of raising.
    assert rows["core"].status == "FAIL" and "libocgcore.so" in rows["core"].detail and rows["core"].hint
    assert rows["cards"].status == "ok" and rows["cards"].detail.startswith("1 .cdb file, 1 card; strings.conf found")
    assert rows["scripts"].status == "ok" and "c55144522.lua" in rows["scripts"].detail
    assert rows["pics"].status == "ok" and "1 picture" in rows["pics"].detail
    assert rows["mono"].status == "ok" and rows["mono"].detail.startswith("Mono JIT compiler version 9.9 (fake) at ")
    assert rows["mono build tools"].status == "ok"
    assert rows["windbot fork"].status == "warn" and "git submodule update --init" in rows["windbot fork"].hint
    assert rows["windbot opponents"].status == "ok" and "EDOPro's own WindBot" in rows["windbot opponents"].detail
    assert "1 deck AI" in rows["windbot opponents"].detail
    assert rows["deck fake"].status == "ok" and "playbook" in rows["deck fake"].detail
    assert rows["user decks dir"].status == "ok" and "not created yet" in rows["user decks dir"].detail
    assert rows["ports"].status == "ok" and str(fake["ports"]["web"]) in rows["ports"].detail


def test_backend_profiles_are_checked_by_type(fake, monkeypatch):
    rows = run(fake)
    assert rows["backend heuristic (default)"].status == "ok"
    assert rows["backend cc"].status == "ok" and "claude 9.9.9 (Claude Code fake) at " in rows["backend cc"].detail
    # Only the profile in use has to work: the others warn.
    assert rows["backend api"].status == "warn" and "$DOCTOR_TEST_KEY is not set" in rows["backend api"].detail
    assert "export DOCTOR_TEST_KEY=" in rows["backend api"].hint
    assert rows["backend off"].status == "warn" and "unreachable" in rows["backend off"].detail
    assert "ollama serve" in rows["backend off"].hint
    # Bundled profiles from default.toml are there too.
    assert rows["backend random"].status == "ok" and rows["backend opus"].status == "ok"

    monkeypatch.setenv("DOCTOR_TEST_KEY", "sk-secret")
    rows = run(fake)
    assert rows["backend api"].status == "ok" and "$DOCTOR_TEST_KEY is set" in rows["backend api"].detail
    assert "sk-secret" not in json.dumps([vars(r) for r in rows.values()])  # never the value


def test_the_default_backend_must_work(fake):
    os.remove(fake["bin"] / "claude")
    write_local(fake, backend="cc")
    rows = run(fake)
    assert rows["backend cc (default)"].status == "FAIL" and "`claude` is not on PATH" in rows["backend cc (default)"].detail
    assert "npm install -g @anthropic-ai/claude-code" in rows["backend cc (default)"].hint
    assert rows["backend opus"].status == "warn"  # not the default: a warning
    write_local(fake, backend="api")
    assert run(fake)["backend api (default)"].status == "FAIL"


def test_openai_server_is_asked_for_its_models(fake, monkeypatch):
    with ModelsServer(models=("qwen3:14b", "other")) as srv:
        write_local(fake, extra=f'[backends.oai]\ntype = "openai"\nbase_url = "{srv.base_url}"\nmodel = "qwen3:14b"\n'
                                f'api_key_env = "DOCTOR_TEST_KEY"\n'
                                f'[backends.oai2]\ntype = "openai"\nbase_url = "{srv.base_url[:-3]}"\nmodel = "gone"\n')
        rows = run(fake)
        assert rows["backend oai"].status == "warn" and "2 models; $DOCTOR_TEST_KEY is not set" in rows["backend oai"].detail
        assert rows["backend oai2"].status == "warn" and "gone not among them" in rows["backend oai2"].detail
        assert "ollama pull gone" in rows["backend oai2"].hint
        assert [r["path"] for r in srv.requests] == ["/v1/models", "/v1/models"]  # with or without /v1 in base_url
        assert "authorization" not in srv.requests[0]["headers"]

        monkeypatch.setenv("DOCTOR_TEST_KEY", "sk-secret")
        rows = run(fake)
        assert rows["backend oai"].status == "ok" and rows["backend oai"].detail.endswith("/v1/models: 2 models")
        assert srv.requests[-2]["headers"]["authorization"] == "Bearer sk-secret"


def test_missing_edopro_fails_and_the_rest_is_skipped(fake, monkeypatch):
    rows = run(fake, overrides={"edopro_dir": str(fake["tmp"] / "nowhere")})
    assert rows["edopro"].status == "FAIL" and "--edopro-dir" in rows["edopro"].detail
    assert "edopro_dir in config.local.toml" in rows["edopro"].hint
    assert [rows[n].status for n in ("core", "cards", "scripts", "pics")] == ["skip"] * 4
    assert rows["windbot opponents"].status == "warn"  # no bundled WindBot without the install either
    assert rows["ports"].status == "ok"  # the later checks still run

    monkeypatch.setenv("YGO_AGENT_EDOPRO", str(fake["install"]))
    rows = run(fake, overrides={"edopro_dir": str(fake["tmp"] / "nowhere")})
    assert "$YGO_AGENT_EDOPRO=" in rows["edopro"].detail  # set, but not what the commands read


def test_broken_install_parts_are_reported(fake):
    install = fake["install"]
    os.remove(install / "config" / "strings.conf")
    os.remove(install / "script" / "utility.lua")
    os.remove(install / "repositories" / "fake" / "bin" / "libocgcore.so")
    os.remove(install / "expansions" / "cards.cdb")
    make_cdb(install / "expansions" / "cards.cdb", cards=())
    (install / "pics" / f"{POT_OF_GREED}.jpg").unlink()
    (install / "pics").rmdir()
    rows = run(fake)
    assert rows["core"].status == "FAIL" and "no libocgcore.so" in rows["core"].detail
    assert rows["cards"].status == "FAIL" and "0 cards; strings.conf missing" in rows["cards"].detail
    assert rows["scripts"].status == "FAIL" and "missing utility.lua" in rows["scripts"].detail
    assert rows["pics"].status == "warn" and "downloads missing ones" in rows["pics"].detail
    os.remove(install / "expansions" / "cards.cdb")
    assert run(fake)["cards"].status == "FAIL"
    (install / "expansions" / "cards.cdb").write_text("not a database")
    rows = run(fake)
    assert rows["cards"].status == "FAIL" and "can't be read" in rows["cards"].detail
    os.remove(install / "config" / "configs.json")  # no repositories at all: the base folders still count
    rows = run(fake)
    assert rows["edopro"].status == "ok" and "repositories: none" in rows["edopro"].detail
    assert rows["scripts"].status == "FAIL"


def test_windbot_fork_states(fake, monkeypatch):
    fork = fake["fork"]
    fork.mkdir()
    (fork / "WindBot.csproj").write_text("<Project/>")
    rows = run(fake)
    assert rows["windbot fork"].status == "warn" and "not built" in rows["windbot fork"].detail
    assert rows["windbot fork"].hint.startswith("./build.sh")
    make_windbot(fork / "bin" / "Release", bots=("Blue-Eyes", "Dragunity"))
    rows = run(fake)
    assert rows["windbot fork"].status == "ok" and "(built " in rows["windbot fork"].detail
    assert rows["windbot opponents"].detail.startswith("the fork: ") and "2 deck AIs" in rows["windbot opponents"].detail
    # Without mono nothing runs the exe; the build tools are only a warning.
    for tool in ("mono", "xbuild"):
        os.remove(fake["bin"] / tool)
    rows = run(fake)
    assert rows["mono"].status == "warn" and "play --join" in rows["mono"].hint
    assert rows["mono build tools"].status == "warn" and rows["mono build tools"].detail.startswith("missing xbuild")


def test_decks_with_problems(fake):
    make_deck(fake["repo_decks"], "broken", rules="import nothing_like_this\nRULES = []\n")
    make_deck(fake["repo_decks"], "listless", ydk=False)
    make_deck(fake["repo_decks"], "mute", playbook=False, rules=None)
    make_deck(fake["user_decks"], "Fake")  # the same name in both roots
    rows = run(fake)
    assert rows["deck broken"].status == "FAIL" and "ModuleNotFoundError" in rows["deck broken"].detail
    assert rows["deck broken"].hint.endswith("rules.py so that it imports")
    assert rows["deck listless"].status == "FAIL" and rows["deck listless"].detail.endswith("(missing)")
    assert rows["deck mute"].status == "warn" and "playbook none, 0 rules" in rows["deck mute"].detail
    assert rows["deck fake"].status == "FAIL" and "both deck dirs" in rows["deck fake"].detail
    assert rows["deck Fake"].status == "FAIL"
    assert rows["user decks dir"].status == "ok" and rows["user decks dir"].detail.endswith(": 1 deck")
    fake["local"].write_text(fake["local"].read_text().replace("[decks]\n", '[decks]\nprefer = "repo"\n'))
    rows = run(fake)
    assert rows["deck fake"].status == "ok" and rows["deck Fake"].status == "skip"
    assert "shadowed by the repo copy" in rows["deck Fake"].detail


def test_ports_in_use_warn(fake):
    with socket.socket() as s:
        s.bind(("127.0.0.1", fake["ports"]["web"]))
        s.listen()
        rows = run(fake)
    assert rows["ports"].status == "warn" and rows["ports"].detail.startswith(f"in use: web panel {fake['ports']['web']}")
    assert "--web-port" in rows["ports"].hint


def test_broken_config_is_a_finding_and_the_report_goes_on(fake):
    fake["local"].write_text("chat = 'loud'\n")
    rows = run(fake)
    assert rows["config"].status == "FAIL" and "chat must be one of" in rows["config"].detail
    assert "the checks below use the defaults" in rows["config"].hint
    assert "7930" in rows["ports"].detail  # the defaults
    rows = run(fake, overrides={"edopro_dir": str(fake["install"])})
    assert rows["edopro"].status == "ok" and "(--edopro-dir)" in rows["edopro"].detail  # flags still apply
    rows = doctor.run(doctor.Setup(local=str(fake["tmp"] / "absent.toml")))
    rows = {r.name: r for r in rows}
    assert rows["config"].status == "warn" and "does not exist" in rows["config"].hint


def test_old_python_and_a_crashing_check(fake, monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 4, "final", 0))
    rows = run(fake)
    assert rows["python"].status == "FAIL" and "Python 3.10.4" in rows["python"].detail
    assert "3.11 or newer" in rows["python"].hint

    def check_boom(setup):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(doctor, "CHECKS", [doctor.check_python, check_boom, doctor.check_config])
    rows = doctor.run(doctor.Setup(local=str(fake["local"])))
    assert [r.name for r in rows] == ["python", "boom", "config"]
    assert rows[1].status == "FAIL" and rows[1].detail == "RuntimeError: kaboom" and "--json" in rows[1].hint


def test_main_prints_the_report_or_json_and_sets_the_exit_code(fake, capsys, monkeypatch):
    from ygo_agent.agent import gamelog
    monkeypatch.setattr(gamelog, "COLOR", False)  # what paint() decides when stdout isn't a tty
    args = argparse.Namespace(config=str(fake["local"]), edopro_dir=None, json=False)
    assert doctor.main(args) == 1  # the dummy core fails
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].startswith("ok    python  ") and any(line.startswith("FAIL  core  ") for line in lines)
    assert any(line.strip().startswith("→ ") for line in lines)  # a hint line under a problem
    assert lines[-1].endswith("1 failures")
    assert "\033[" not in out
    monkeypatch.setattr(gamelog, "COLOR", True)
    doctor.main(args)
    assert "\033[31mFAIL\033[0m  core" in capsys.readouterr().out  # the CLI's own paint helper, on a tty

    args.json = True
    assert doctor.main(args) == 1
    rows = json.loads(capsys.readouterr().out)
    assert [set(r) for r in rows] == [{"name", "status", "detail", "hint"}] * len(rows)
    assert {r["name"]: r["status"] for r in rows}["core"] == "FAIL"

    args.edopro_dir = str(fake["tmp"] / "nowhere")
    args.json = False
    monkeypatch.setattr(gamelog, "COLOR", False)
    assert doctor.main(args) == 1
    assert "FAIL  edopro" in capsys.readouterr().out


def test_cli_wiring():
    args = cli.parser().parse_args(["doctor", "--json", "--edopro-dir", "/x", "--config", "c.toml"])
    assert (args.cmd, args.json, args.edopro_dir, args.config) == ("doctor", True, "/x", "c.toml")
    assert cli.parser().parse_args(["doctor"]).json is False


@pytest.mark.integration
def test_doctor_on_this_machine(capsys):
    """The real install: nothing fails, and the only warnings are for optional things (an API key, a local model
    server, the WindBot fork, pictures, a port a running game holds)."""
    with pytest.raises(SystemExit) as exit_:
        cli.main(["doctor", "--json"])
    rows = json.loads(capsys.readouterr().out)
    failures = [r for r in rows if r["status"] == "FAIL"]
    assert not failures, failures
    assert exit_.value.code == 0
    optional = ("backend ", "windbot ", "mono", "pics", "ports")
    unexpected = [r for r in rows if r["status"] == "warn" and not r["name"].startswith(optional)]
    assert not unexpected, unexpected
    assert {r["name"] for r in rows} >= {"python", "config", "edopro", "core", "cards", "scripts", "deck saffira"}
