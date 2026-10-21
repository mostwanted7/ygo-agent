import pytest

from ygo_agent import cache, join
from ygo_agent.cli import configure, mode_of, parser
from ygo_agent.config import ConfigError, backend, deck_overrides, load_config


def test_defaults():
    cfg = load_config(local=None)
    assert cfg["deck"] == "saffira" and cfg["chat"] == "banter"
    assert cfg["duel"]["rules"] == "MR3"
    assert cfg["room"] == {"host": "127.0.0.1", "port": 7911, "password": ""}
    assert cfg["bot"]["brain_port"] == 7922 and cfg["bot"]["protocol_version"] == 0
    assert cfg["agent"]["decision_timeout_seconds"] == 120 and cfg["agent"]["max_messages_per_session"] == 40
    assert backend(cfg) == {"name": "opus", "type": "claude-code", "model": "opus", "effort": "medium"}
    assert cfg["agent"]["fallback"] == "bot" and cfg["agent"]["card_texts"] == "full"
    assert cfg["agent"]["history_lines"] == 500 and cfg["bot"]["name"] == "ygo-agent"
    for name in ("opus", "sonnet", "haiku", "api-opus", "local", "heuristic", "random"):
        assert backend(cfg, name)["name"] == name
    assert backend(cfg, "api-opus")["type"] == "anthropic" and backend(cfg, "local")["type"] == "openai"
    assert backend(cfg, "local")["base_url"] == "http://localhost:11434/v1"


def test_local_file_merges_tables(tmp_path):
    local = tmp_path / "local.toml"
    local.write_text('chat = "off"\n[room]\nport = 7912\n[decks.saffira]\nydk = "~/x.ydk"\n'
                     '[backends.fast]\ntype = "claude-code"\nmodel = "sonnet"\n[agent]\nbackend = "fast"\n')
    cfg = load_config(local=str(local))
    assert cfg["chat"] == "off"
    assert cfg["room"] == {"host": "127.0.0.1", "port": 7912, "password": ""}
    assert deck_overrides(cfg, "saffira") == {"ydk": "~/x.ydk"} and deck_overrides(cfg, "blackwing") == {}
    assert backend(cfg)["model"] == "sonnet" and cfg["agent"]["decision_timeout_seconds"] == 120


def test_bad_values_are_reported(tmp_path):
    with pytest.raises(ConfigError):
        load_config(local=None, overrides={"chat": "main"})
    with pytest.raises(ConfigError):
        load_config(local=None, overrides={"agent": {"backend": "nope"}})
    with pytest.raises(ConfigError, match="supported"):
        load_config(local=None, overrides={"backends": {"x": {"type": "gpt"}}, "agent": {"backend": "x"}})
    with pytest.raises(ConfigError, match="card_texts"):
        load_config(local=None, overrides={"agent": {"card_texts": "tiny"}})
    with pytest.raises(ConfigError, match="fallback"):
        load_config(local=None, overrides={"agent": {"fallback": "human"}})
    broken = tmp_path / "broken.toml"
    broken.write_text("chat = \n")
    with pytest.raises(ConfigError):
        load_config(local=str(broken))


def test_cli_flags_win(tmp_path):
    local = tmp_path / "local.toml"
    local.write_text('[room]\nport = 7912\n')
    args = parser().parse_args(["play", "--join", "--port", "7999", "--model", "sonnet", "--effort", "low",
                                "--deck", "blackwing", "--chat", "off", "--brain-port", "7930",
                                "--config", str(local), "--games-dir", str(tmp_path)])
    cfg = configure(args)
    assert cfg["room"]["port"] == 7999 and cfg["deck"] == "blackwing" and cfg["chat"] == "off"
    assert cfg["bot"]["brain_port"] == 7930 and cfg["games_dir"] == str(tmp_path)
    assert backend(cfg)["model"] == "sonnet" and backend(cfg)["effort"] == "low"
    assert mode_of(args) == "play"
    args = parser().parse_args(["test", "--backend", "local", "--model", "llama3.1:8b", "--config", str(local)])
    cfg = configure(args)
    assert backend(cfg)["name"] == "local" and backend(cfg)["model"] == "llama3.1:8b"
    assert mode_of(parser().parse_args(["play", "--join", "--copilot"])) == "copilot"
    assert mode_of(parser().parse_args(["teach"])) == "teach"


def test_play_without_join_explains(capsys):
    from ygo_agent.cli import main
    with pytest.raises(SystemExit) as e:
        main(["play"])
    assert "--join" in str(e.value)


def test_protocol_version_comes_from_config_then_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(cache, "CACHE", str(tmp_path))
    cfg = load_config(local=None)
    assert join.protocol_version(cfg) == join.DEFAULT_PROTOCOL_VERSION
    cache.put("protocol_version", 123)
    assert join.protocol_version(cfg) == 123
    cfg["bot"]["protocol_version"] = 456
    assert join.protocol_version(cfg) == 456


def test_bot_command(cfg):
    class DB:
        db_paths = ["/x/cards.cdb"]

    class Prof:
        ydk = "/decks/saffira/deck.ydk"
    cmd = join.bot_command(cfg, DB(), Prof(), 720937)
    args = dict(a.split("=", 1) for a in cmd[2:])
    assert cmd[0] == "mono" and cmd[1].endswith("windbot-src/bin/Release/WindBot.exe")
    assert args["Deck"] == "Agent" and args["DeckFile"] == "/decks/saffira/deck.ydk"
    assert args["Brain"] == "127.0.0.1:7922" and args["Version"] == "720937"
    assert args["Host"] == "127.0.0.1" and args["Port"] == "7911" and args["Name"] == "ygo-agent"
    assert args["Chat"] == "false"
