"""Stage 4 without EDOPro: seat specs, deck lookup, the opponent in the prompt, the terminal tags, and the three fixes
Stage 3 left open (false rollovers, confirm events' card texts; the numbered Special Summon entries are tested in
tests/native/test_native_describe.py)."""

import io
import contextlib
import json
import os
import shutil

import pytest

from helpers import CASES, load_case
from ygo_agent import paths
from ygo_agent.agent import prompts
from ygo_agent.agent.brain import DuelBrain, event_ids
from ygo_agent.agent.gamelog import GameLog
from ygo_agent.agent.profile import Profile
from ygo_agent.match import MatchError, SeatSpec, load_profile


# ---- seat specs ----

@pytest.mark.parametrize("text, want", [
    ("saffira", SeatSpec("agent", deck="saffira")),
    ("saffira:opus", SeatSpec("agent", deck="saffira", backend="opus")),
    ("blackwing:api-opus", SeatSpec("agent", deck="blackwing", backend="api-opus")),
    ("heuristic", SeatSpec("agent", backend="heuristic")),
    ("random", SeatSpec("agent", backend="random")),
    ("heuristic:blackwing", SeatSpec("agent", deck="blackwing", backend="heuristic")),
    ("windbot:Blue-Eyes", SeatSpec("windbot", deck="Blue-Eyes")),
    ("WindBot:Dragunity", SeatSpec("windbot", deck="Dragunity")),
    ("human", SeatSpec("human")),
    ("~/decks/Geargia.ydk", SeatSpec("agent", deck="~/decks/Geargia.ydk")),
    ("~/decks/Geargia.ydk:sonnet", SeatSpec("agent", deck="~/decks/Geargia.ydk", backend="sonnet")),
    ("/tmp/x:y/deck.ydk", SeatSpec("agent", deck="/tmp/x:y/deck.ydk")),
])
def test_seat_specs_parse(text, want):
    assert SeatSpec.parse(text) == want


def test_seat_specs_print_back_and_reject_nonsense():
    for text in ("saffira:opus", "windbot:Blue-Eyes", "human", "blackwing"):
        assert str(SeatSpec.parse(text)) == text
    assert str(SeatSpec.parse("heuristic")) == "(default deck):heuristic"
    for bad in ("", "  ", "windbot", "windbot:"):
        with pytest.raises(MatchError):
            SeatSpec.parse(bad)
    assert SeatSpec.coerce("human") == SeatSpec("human") and SeatSpec.coerce(SeatSpec("human")).kind == "human"


def test_decks_come_from_folders_paths_or_edopro(db, cfg, tmp_path):
    assert load_profile("saffira", db, cfg).key == "saffira"
    assert load_profile("Blackwing", db, cfg).key == "blackwing"  # folders match case-insensitively
    assert load_profile(None, db, cfg).key == cfg["deck"]
    src = os.path.join(paths.DECKS, "saffira", "deck.ydk")
    loose = tmp_path / "My Deck.ydk"
    shutil.copyfile(src, loose)
    p = load_profile(str(loose), db, cfg)
    assert p.adhoc and p.key == "my-deck" and p.name == "My Deck" and p.playbook == "(no playbook yet)"
    (tmp_path / "My Deck.md").write_text("Open with the good cards.")
    p = load_profile(str(loose), db, cfg)
    assert p.playbook == "Open with the good cards." and "Open with the good cards." in p.system_prompt()
    edopro = tmp_path / "edopro"
    (edopro / "deck").mkdir(parents=True)
    shutil.copyfile(src, edopro / "deck" / "Geargia.ydk")
    cfg["edopro_dir"] = str(edopro)
    assert load_profile("geargia", db, cfg).name == "Geargia"
    with pytest.raises(MatchError, match="no deck 'nope'"):
        load_profile("nope", db, cfg)


# ---- the opponent in the prompt ----

def test_the_prompt_names_the_opponent_in_every_mode(db, cfg):
    p = Profile("saffira", db, cfg)
    human = p.system_prompt("play", "MR3", opponent={"kind": "human"})
    legacy = p.system_prompt("play", "MR3")
    assert "human who is coaching you" in human and human == legacy
    ai = p.system_prompt("selfplay", "MR3", opponent={"kind": "agent", "deck": "Blackwing", "backend": "claude-code"})
    assert "your opponent is another AI playing Blackwing" in ai and "coaching you" not in ai
    assert "# Teaching mode" not in ai
    bot = p.system_prompt("selfplay", "MR3", opponent={"kind": "windbot", "deck": "Blue-Eyes"})
    assert "WindBot, EDOPro's built-in scripted AI, playing its Blue-Eyes deck" in bot
    teach = p.system_prompt("teach", "MR3", opponent={"kind": "windbot", "deck": "Blue-Eyes"})
    assert "spectator seat" in teach and "your opponent is WindBot" in teach and "# Teaching mode" in teach
    assert "another player (an AI or a human)" in p.system_prompt("teach", "MR3")  # teach --join: unknown
    assert prompts.opponent_text({"kind": "agent", "deck": "Saffira", "backend": "heuristic"}) == \
        "a simple rule-based bot playing Saffira"
    assert "random legal moves" in prompts.opponent_text({"kind": "agent", "backend": "random"})
    play_vs_bot = p.system_prompt("play", "MR3", opponent={"kind": "windbot", "deck": "Dragunity"})
    assert "Your opponent is WindBot" in play_vs_bot and "coaching you" not in play_vs_bot


def test_the_brain_passes_its_opponent_to_the_prompt(db, cfg, scripted):
    opponent = {"kind": "agent", "deck": "Blackwing", "backend": "claude-code"}
    brain = DuelBrain(cfg, db, Profile("saffira", db, cfg), prewarm=False, mode="selfplay", opponent=opponent)
    play(brain, case("set-lance-before-ending"), decisions=3)
    brain.close()
    assert scripted["sessions"] and "another AI playing Blackwing" in scripted["sessions"][0].system_prompt
    meta = json.load(open(os.path.join(brain.log.dir, "meta.json")))
    assert meta["mode"] == "selfplay" and meta["opponent_info"] == opponent


# ---- Stage 3 fixes ----

def case(name):
    return load_case(next(p for p in CASES if p.endswith(f"/{name}.json")))


def play(brain, c, decisions=None):
    n = 0
    for m in c["messages"]:
        m = json.loads(json.dumps(m))
        if m.get("t") == "event":
            brain.on_event(m)
        else:
            brain.on_decide(m)
            n += 1
            if decisions and n >= decisions:
                return


def first_idle(c):
    events, d = [], None
    for m in c["messages"]:
        if m.get("t") == "decide" and m["kind"] == "idle":
            d = m
            break
        if m.get("t") == "event":
            events.append(m)
    return events, json.loads(json.dumps(d))


def test_rules_answering_a_turns_first_decisions_is_no_rollover(db, cfg, scripted):
    """Stage 3 (1): a session's first prompt counted as a rollover when the rules had answered decisions before it."""
    events, idle = first_idle(case("set-lance-before-ending"))
    brain = DuelBrain(cfg, db, Profile("saffira", db, cfg), prewarm=False)
    for ev in events:
        brain.on_event(json.loads(json.dumps(ev)))
    turn = idle["state"]["turn"]
    brain.on_event({"t": "event", "e": "new_turn", "turn": turn + 1, "player": 0})
    state = dict(idle["state"], turn=turn + 1)
    position = {"t": "decide", "id": 900, "kind": "position", "card_id": 0, "options": [1], "state": state}
    assert brain.on_decide(position)["choice"] == [0]  # a built-in rule: only one position
    brain.on_decide(dict(idle, id=901, state=state))
    brain.close()
    first = scripted["sessions"][-1].prompts[0]
    assert "previous session for this turn ended" not in first
    assert "Decisions already made this turn:" in first and "#900" in first
    assert brain.stats.rollovers == 0 and brain.stats.sessions == 1


def test_a_real_rollover_still_counts(db, cfg, scripted):
    cfg["backends"]["test"]["max_session_messages"] = 1
    brain = DuelBrain(cfg, db, Profile("saffira", db, cfg), prewarm=False)
    play(brain, case("set-lance-before-ending"))
    brain.close()
    rolled = [s.prompts[0] for s in scripted["sessions"] if "previous session for this turn ended" in s.prompts[0]]
    assert rolled and brain.stats.rollovers == len(rolled)


def test_confirmed_cards_get_their_texts_into_the_prompt(db, cfg, scripted):
    """Stage 3 (2): event_ids ignored confirm.cards, so a revealed card's text never reached the prompt."""
    profile = Profile("saffira", db, cfg)
    outsider = next(i for i in sorted(db.cards) if i not in profile.ids and db.get(i).name)
    confirm = {"t": "event", "e": "confirm", "player": 0,
               "cards": [{"id": outsider, "c": 1, "l": 2, "s": 0, "p": 0}]}
    assert event_ids(confirm) == {outsider}
    assert event_ids({"e": "swap", "cards": [{"id": 1, "c": 0, "l": 4, "s": 0}, {"id": 2, "c": 1, "l": 4, "s": 1}]}) \
        == {1, 2}
    events, idle = first_idle(case("set-lance-before-ending"))
    brain = DuelBrain(cfg, db, profile, prewarm=False)
    for ev in events:
        brain.on_event(json.loads(json.dumps(ev)))
    brain.on_event(confirm)
    brain.on_decide(idle)
    brain.close()
    prompt = scripted["sessions"][-1].prompts[-1]
    texts = prompt.split("Card texts (not shown to you yet this turn):", 1)[1].split("\n\n")[0]
    assert db.name(outsider) in texts


# ---- terminal ----

def test_tagged_logs_and_verbosity(tmp_path):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        log = GameLog(str(tmp_path), "Saffira", deck_key="saffira", tag="[A Saffira·opus]", echo="decisions",
                      publish=False)
        log.event("=== TURN 1 (your turn) ===")
        log.decision(1, "Main Phase: choose.", ["Normal Summon X", "End your turn"], [0], "because", "plan line",
                     "backend", 1.5, label="opus (claude-code)", key=True, turn=1)
        key = GameLog(str(tmp_path), "Blackwing", deck_key="blackwing", tag="[B Blackwing·sonnet]", echo="key",
                      publish=False)
        key.decision(2, "Main Phase: choose.", ["Normal Summon Y", "End your turn"], [0], "why " * 60, None,
                     "backend", 1.0, key=True, turn=2)
        key.decision(3, "Main Phase: choose.", ["Normal Summon Y", "End your turn"], [1], "end", None, "backend",
                     key=False, turn=2)
        log.close()
        key.close()
    text = out.getvalue()
    lines = [line for line in text.splitlines() if line.strip()]
    assert all(line.startswith("[A Saffira·opus]") or line.startswith("[B Blackwing·sonnet]") for line in lines)
    assert "TURN 1" not in text  # "decisions": the other seat prints the events
    assert "▶ [0] Normal Summon X" in text and "✎ plan: plan line" in text
    key_lines = [line for line in lines if line.startswith("[B")]
    assert len(key_lines) == 1 and "T2 #2 Normal Summon Y" in key_lines[0] and key_lines[0].endswith("...")
    assert "TURN 1" in open(os.path.join(log.dir, "game.md")).read()  # game.md has everything either way
