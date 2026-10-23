"""The panel in a real (headless) browser, following live games: a logged native-seat game replayed through the bus
the way a live seat publishes it, and a native self-play game. Needs the EDOPro install, Firefox and Node >= 22
(tests/web/check.mjs drives the browser); skipped without them.

Regression: in a live game the board froze at a decision for the rest of the game, while the header still said
LIVE. Clicking the newest decision card pinned the timeline cursor on it, so new decisions kept arriving in the
reasoning list but the board and the timeline stayed put."""

import json
import copy
import os
import shutil
import subprocess
import threading
import time

import pytest

from live_replay import replay_live, rows

pytestmark = pytest.mark.integration

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "..", "fixtures", "web", "native-place-game")
CHECK = os.path.join(HERE, "check.mjs")


def browser_or_skip():
    if not shutil.which("firefox") or not shutil.which("node"):
        pytest.skip("needs firefox and node for the browser checks")
    version = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
    if int(version.split(".")[0] or 0) < 22:
        pytest.skip("needs Node >= 22 (its built-in WebSocket)")


def run_check(url, steps, tmp_path, timeout=180):
    path = tmp_path / "steps.json"
    path.write_text(json.dumps(steps))
    out = subprocess.run(["node", CHECK, url, str(path)], capture_output=True, text=True, timeout=timeout)
    lines = [line for line in out.stdout.splitlines() if line.startswith("{")]
    assert lines, f"check.mjs printed no report:\n{out.stdout}\n{out.stderr}"
    report = json.loads(lines[-1])
    errors = [c for c in report["console"] if c["level"] == "error"]
    assert not errors, errors
    assert report["ok"], report["steps"]
    return [s.get("value") for s in report["steps"]]


@pytest.fixture(scope="module")
def engine():
    from ygo_agent.core import Engine, InstallError
    try:
        return Engine.load()
    except (InstallError, OSError) as e:
        pytest.skip(f"EDOPro install not available: {e}")


@pytest.fixture(scope="module")
def agent_db(engine):
    from ygo_agent.agent.carddb import CardDB
    return CardDB(engine.install.root)


@pytest.fixture
def agent_cfg(tmp_path):
    from ygo_agent.config import load_config
    return load_config(local=None, overrides={"games_dir": str(tmp_path / "games"), "chat": "off"})


@pytest.fixture
def panel(engine, agent_db, agent_cfg):
    from ygo_agent.web import server
    from ygo_agent.web.bus import BUS
    BUS.reset()
    srv = server.start(agent_cfg, agent_db, port=0)
    yield srv
    srv.stop()
    BUS.reset()


BOARD = ("({turn: document.querySelector('#turn-no').textContent, "
         "lp: [...document.querySelectorAll('.plate .lp')].map(e => e.firstChild.nodeValue), "
         "label: document.querySelector('#tl-label').textContent, chip: document.querySelector('#status-chip').textContent, "
         "paused: !document.querySelector('#pausebar').classList.contains('hidden'), "
         "past: document.querySelector('#board').classList.contains('past'), errors: app.renderErrors || 0, "
         "state: app.board && [app.board.opp.lp, app.board.me.lp]})")
CLICK_NEWEST = ("(() => { const cards = document.querySelectorAll('#stream .dc'); const c = cards[cards.length - 1]; "
                "c.querySelector('.q').click(); return c.querySelector('.num').textContent; })()")
CLICK_OLD = "(() => { const c = document.querySelectorAll('#stream .dc')[2]; c.querySelector('.q').click(); " \
            "return c.querySelector('.num').textContent; })()"


@pytest.mark.parametrize("mode", ["selfplay", "play", "coach", "teach"])
def test_god_view_reveals_hands_and_set_cards(panel, tmp_path, mode):
    browser_or_skip()
    from ygo_agent.web.bus import BUS
    gid = "god-" + mode
    side = {"lp": 8000, "deck": 30, "extra": [], "gy": [], "ban": [],
            "hand": [{"id": 89631139, "c": 0, "l": 2, "s": 0, "p": 10}],
            "mz": [{"id": 89631139, "c": 0, "l": 4, "s": 0, "p": 8}] + [None] * 6,
            "sz": [{"id": 53129443, "c": 0, "l": 8, "s": 0, "p": 10}] + [None] * 7}
    state = {"turn": 1, "turn_player": 0, "phase": 4, "me": side, "opp": copy.deepcopy(side), "chain": []}
    for zone in ("hand", "mz", "sz"):
        state["opp"][zone][0]["c"] = 1
    filtered = copy.deepcopy(state)
    for zone in ("hand", "mz", "sz"):
        filtered["opp"][zone][0]["id"] = 0
    for seat in range(2 if mode == "selfplay" else 1):
        base = {"game_id": gid, "seat": seat}
        BUS.publish({**base, "type": "game_start", "deck_name": f"Player {seat}", "mode": mode})
        BUS.publish({**base, "type": "spectator_state", "state": copy.deepcopy(state)})
        # The other AI hasn't made a decision yet. Its private hand must still be visible in God view.
        if seat == 0:
            BUS.publish({**base, "type": "decision", "decision": {
                "id": 1, "kind": "yesno", "options": [], "state": filtered}})
    later, later_filtered = copy.deepcopy(state), copy.deepcopy(filtered)
    later["me"]["hand"][0]["id"] = later_filtered["me"]["hand"][0]["id"] = 46986414
    BUS.publish({"game_id": gid, "seat": 0, "type": "spectator_state", "state": later})
    BUS.publish({"game_id": gid, "seat": 0, "type": "decision", "decision": {
        "id": 2, "kind": "yesno", "options": [], "state": later_filtered}})
    counts = """({hands: [...document.querySelectorAll('.hand')].map(e => e.querySelectorAll('[data-card]').length),
        sets: document.querySelectorAll('.zone .card.mine-set[data-card]').length,
        toggle: !document.querySelector('#god-toggle').classList.contains('hidden')})"""
    steps = [
        {"wait": "app.board && app.game.decs.length === 2"},
        {"eval": counts},
        {"eval": "document.querySelector('#god').click()"},
        {"eval": counts},
        {"eval": "document.querySelector('#god').click()"},
        {"eval": counts},
    ]
    steps += [{"eval": "app.board.me.hand[0].id"},
              {"eval": "document.querySelector('#stream .dc .q').click()"},
              {"eval": "app.board.me.hand[0].id"}]
    if mode == "selfplay":
        steps += [{"eval": "document.querySelector('[data-seat=\"1\"]').click()"}, {"eval": counts},
                  {"eval": "[app.board.turn_player, app.board.me.hand[0].c, app.board.opp.hand[0].c]"}]
    values = run_check(f"{panel.url}?game={gid}", steps, tmp_path)
    revealed = {"hands": [1, 1], "sets": 4, "toggle": True}
    assert values[1] == values[5] == revealed
    assert values[3] == {"hands": [0, 1], "sets": 2, "toggle": True}
    assert values[6] == 46986414 and values[8] == 89631139  # scrubbing cannot borrow future knowledge
    if mode == "selfplay":
        assert values[-2] == revealed
        assert values[-1] == [1, 0, 1]



def test_player_colors_and_reasoning_filter_are_independent(panel, tmp_path):
    browser_or_skip()
    from ygo_agent.web.bus import BUS
    gid = "mirror-colors"
    side = {"lp": 8000, "deck": 30, "hand": [], "extra": [], "gy": [], "ban": [],
            "mz": [None] * 7, "sz": [None] * 8}
    for seat, model in enumerate(("Model Alpha", "Model Beta")):
        base = {"game_id": gid, "seat": seat}
        BUS.publish({**base, "type": "game_start", "deck_name": "Blackwing", "mode": "selfplay",
                     "backend": {"model": model, "label": model}})
        state = {"turn": 1, "turn_player": seat, "phase": 4,
                 "me": copy.deepcopy(side), "opp": copy.deepcopy(side), "chain": []}
        BUS.publish({**base, "type": "decision", "decision": {
            "id": 1, "kind": "yesno", "options": [], "state": state}})
    snapshot = """({seat: app.seat, filter: app.streamSeats,
        buttons: [...document.querySelectorAll('#seat-tabs button')].map(e => e.textContent),
        dots: [...document.querySelectorAll('#seat-tabs .sw')].map(e => getComputedStyle(e).backgroundColor),
        badges: [...document.querySelectorAll('#stream .seatb')].map(e => ({text: e.textContent, color: getComputedStyle(e).color})),
        bottom: document.querySelector('#side-me .nm b').textContent,
        bottomColor: getComputedStyle(document.body).getPropertyValue('--me').trim(),
        topColor: getComputedStyle(document.body).getPropertyValue('--opp').trim(),
        bar: getComputedStyle(document.querySelector('#side-me .lpbar .fill')).backgroundImage,
        filterVisible: !document.querySelector('#reasoning-seats').classList.contains('hidden')})"""
    steps = [
        {"wait": "app.board && app.game.decs.length === 2 && document.querySelectorAll('#seat-tabs button').length === 2"},
        {"eval": snapshot},
        {"eval": "document.querySelector('#seat-tabs [data-seat=\"1\"]').click()"},
        {"eval": snapshot},
        {"eval": "document.querySelector('#reasoning-seats [data-stream-seat=\"0\"]').click()"},
        {"eval": snapshot},
        {"eval": "document.querySelector('#seat-tabs [data-seat=\"0\"]').click()"},
        {"eval": snapshot},
        {"eval": "document.querySelector('#reasoning-seats [data-stream-seat=\"all\"]').click()"},
        {"eval": snapshot},
        {"eval": "document.querySelector('#theme-btn').click()"},
        {"eval": snapshot},
        {"eval": "document.querySelector('#seat-tabs [data-seat=\"1\"]').click()"},
        {"eval": snapshot},
        {"eval": "document.querySelector('[data-tab=\"log\"]').click()"},
        {"eval": snapshot},
    ]
    values = run_check(f"{panel.url}?game={gid}", steps, tmp_path)
    a, b, filtered, flipped, both, light_a, light_b, log = values[1::2]
    assert a["buttons"] == b["buttons"] == ["Blackwing 1", "Blackwing 2"]
    assert a["dots"] == b["dots"] and a["dots"][0] != a["dots"][1]
    assert a["badges"] == b["badges"]
    assert a["bottom"] == "Blackwing 1" and b["bottom"] == "Blackwing 2"
    assert a["bottomColor"] == b["topColor"] and a["topColor"] == b["bottomColor"]
    assert a["bar"] != b["bar"]
    assert a["filter"] == b["filter"] == "all"
    assert filtered["seat"] == 1 and filtered["filter"] == 0
    assert [x["text"] for x in filtered["badges"]] == ["Blackwing 1"]
    assert flipped["seat"] == 0 and flipped["filter"] == 0
    assert both["seat"] == 0 and both["filter"] == "all" and len(both["badges"]) == 2
    assert light_a["dots"] == light_b["dots"] and light_a["dots"] != a["dots"]
    assert light_a["bottomColor"] == light_b["topColor"]
    assert light_a["badges"] == light_b["badges"]
    assert log["filterVisible"] is False

def final_board(game_dir):
    """Turn and LP (opponent, me: the board's plate order) after the game's last events."""
    turn, lp = 0, [8000, 8000]
    for r in rows(game_dir):
        m = r["msg"]
        if r["kind"] == "decide" and m.get("kind") != "game_over" and (m.get("state") or {}).get("me"):
            turn, lp = m["state"]["turn"], [m["state"]["me"]["lp"], m["state"]["opp"]["lp"]]
        elif r["kind"] == "event" and m.get("e") in ("damage", "pay_lp", "recover", "lp"):
            lp[m["player"]] = m["lp"]
    return str(turn), [str(lp[1]), str(lp[0])]


@pytest.mark.parametrize("source", ["decision", "spectator_state", "event"])
def test_old_wrapped_lp_shows_zero_after_lethal(panel, tmp_path, source):
    browser_or_skip()
    from ygo_agent.web.bus import BUS
    gid = "wrapped-lp-" + source
    side = {"lp": 6700, "deck": 20, "hand": [], "extra": [], "gy": [], "ban": [],
            "mz": [None] * 7, "sz": [None] * 8}
    state = {"turn": 5, "turn_player": 0, "phase": 8, "me": side, "opp": copy.deepcopy(side), "chain": []}
    state["opp"]["lp"] = 4294965196 if source != "event" else 800
    base = {"game_id": gid, "seat": 0}
    BUS.publish({**base, "type": "game_start", "deck_name": "Winner"})
    BUS.publish({**base, "type": "decision", "decision": {
        "id": 1, "kind": "yesno", "options": [], "state": state}})
    if source == "spectator_state":
        BUS.publish({**base, "type": "spectator_state", "state": state})
    elif source == "event":
        BUS.publish({**base, "type": "event", "ev": {"e": "damage", "player": 1,
                                                      "amount": 2900, "lp": 4294965196}})
    BUS.publish({**base, "type": "game_end", "result": "win", "reason": 1})
    values = run_check(f"{panel.url}?game={gid}", [
        {"wait": "app.board && document.querySelector('#status-chip').textContent === 'ENDED'"},
        {"eval": BOARD},
        {"eval": "document.querySelector('#god').click()"},
        {"eval": BOARD},
    ], tmp_path)
    for v in (values[1], values[3]):
        assert v["lp"] == ["0", "6700"] and v["state"] == [0, 6700]
        assert v["errors"] == 0


def test_the_board_follows_a_live_native_game_to_the_end(panel, agent_cfg, agent_db, tmp_path):
    browser_or_skip()
    from ygo_agent.web.bus import BUS
    gid = "live-native-place-game"
    stop = threading.Event()
    t = threading.Thread(target=replay_live, args=(GAME, agent_cfg, agent_db, gid), kwargs={"delay": 0.3, "stop": stop},
                         daemon=True)
    t.start()
    for _ in range(100):
        if BUS.has(gid):
            break
        time.sleep(0.05)
    steps = [
        {"wait": "app.game && app.game.decs.length >= 14", "timeout": 60000},
        {"eval": CLICK_NEWEST},          # what froze the board: reading the newest card
        {"sleep": 1500},
        {"eval": BOARD},
        {"eval": CLICK_OLD},             # an explicit look back: paused, and it says so
        {"eval": BOARD},
        {"shot": str(tmp_path / "paused.png")},
        {"key": "Escape"},               # back to live
        {"sleep": 400},
        {"eval": BOARD},
        {"wait": "document.querySelector('#status-chip').textContent === 'ENDED'", "timeout": 90000},
        {"sleep": 2500},  # the LP counters animate
        {"eval": BOARD},
    ]
    try:
        values = run_check(f"{panel.url}?game={gid}", steps, tmp_path)
    finally:
        stop.set()
        t.join(30)
    after_newest, paused, clicked_old, back, final = values[3], values[5], values[4], values[9], values[12]
    assert not after_newest["paused"] and not after_newest["past"] and after_newest["chip"] == "LIVE"
    assert paused["paused"] and paused["past"] and paused["chip"] == f"PAUSED AT {clicked_old}"
    assert not back["paused"] and back["chip"] == "LIVE"
    turn, lp = final_board(GAME)
    last = [r["msg"]["id"] for r in rows(GAME) if r["kind"] == "decide" and r["msg"]["kind"] not in ("place", "game_over")][-1]
    assert final["turn"] == turn and final["lp"] == lp and [str(x) for x in final["state"]] == lp, final
    assert final["label"].startswith(f"#{last} ·") and final["errors"] == 0
    assert os.path.getsize(tmp_path / "paused.png") > 10000


def test_a_native_selfplay_game_renders_without_errors(panel, engine, agent_cfg, agent_db, tmp_path):
    """Native-only message shapes (zone masks, partial select_unselect picks, announce_card codes, confirm/coin/dice
    events...): the board reaches the end of a heuristic-vs-random game with no render error."""
    browser_or_skip()
    from ygo_agent.match import run_games
    from ygo_agent.web.bus import BUS
    out = {}

    def play():
        out["run"] = run_games("saffira:heuristic", "blackwing:random", games=1, seed=11, pace=0.05, cfg=agent_cfg,
                               db=agent_db, engine=engine, quiet=True, lan=False)
    games_before = {g["game_id"] for g in BUS.games()}
    t = threading.Thread(target=play, daemon=True)
    t.start()
    find = ("(async () => { const r = await fetch('/api/games'); const d = await r.json(); "
            f"const g = d.live.find(x => !{json.dumps(sorted(games_before))}.includes(x.game_id)); "
            "if (g && (!app.game || app.game.id !== g.game_id)) openLive(g.game_id); return !!g; })()")
    steps = [
        {"wait": find, "timeout": 60000},
        {"wait": "document.querySelector('#status-chip').textContent === 'ENDED'", "timeout": 240000},
        {"sleep": 800},
        {"eval": BOARD},
        {"eval": "app.game.decs.length"},
    ]
    values = run_check(panel.url, steps, tmp_path, timeout=300)
    t.join(120)
    final, decisions = values[3], values[4]
    assert final["errors"] == 0 and decisions > 20 and not final["paused"], final
    assert out["run"].games and final["turn"] == str(out["run"].games[0].turns) or int(final["turn"]) > 0


def native_shapes(game_dir):
    """Messages only native seats send, to slip into a replayed game: coin/dice/equip/counter/swap/declared/confirm
    events, an announce_card answered with the card code itself, a select_unselect picked in several steps."""
    log = rows(game_dir)
    d = next(r["msg"] for r in log if r["kind"] == "decide" and r["msg"]["id"] == 12)
    mine = [c for c in d["state"]["me"]["mz"] if c][0]
    hand = [c for c in d["state"]["me"]["hand"] if c]
    theirs = {"id": 0, "c": 1, "l": 0x8, "s": 2, "p": 10}
    ev = lambda e, **f: {"t": "event", "e": e, **f}  # noqa: E731
    return {12: [
        ev("coin", player=0, results=[1, 0]), ev("dice", player=1, results=[4]),
        ev("equip", card={**theirs, "id": 50078509, "p": 5}, target=mine),
        ev("counter", card=mine, type=0x1, count=2, add=True), ev("counter", card=mine, type=0x1, count=1, add=False),
        ev("declared", player=1, kind="card", value=hand[0]["id"]), ev("declared", player=1, kind="attribute", value=0x10),
        ev("confirm", player=1, cards=[{**hand[0], "c": 0, "l": 0x2}]),
        ev("swap", cards=[{**mine, "c": 1}, {**mine, "c": 0}]), ev("swap", cards=[{**mine, "c": 0}, {**mine, "c": 1}]),
        {"t": "decide", "id": 901, "kind": "announce_card", "options": [hand[0]["id"], 50078509], "answer": [1]},
        {"t": "decide", "id": 902, "kind": "select_unselect", "options": hand[:3], "selected": [], "min": 2, "max": 2,
         "hint": 501, "finishable": False, "cancelable": False, "answer": [0, 1]},
        {"t": "decide", "id": 903, "kind": "select_unselect", "options": hand[1:3], "selected": hand[:1], "min": 2,
         "max": 2, "hint": 501, "finishable": False, "cancelable": False},
        {"t": "decide", "id": 904, "kind": "option", "options": [1068, 1069], "answer": [0]},
    ]}


def test_native_only_message_shapes_render(panel, agent_cfg, agent_db, tmp_path):
    browser_or_skip()
    from ygo_agent.web.bus import BUS
    gid = "live-native-shapes"
    t = threading.Thread(target=replay_live, args=(GAME, agent_cfg, agent_db, gid),
                         kwargs={"delay": 0.05, "inject": native_shapes(GAME)}, daemon=True)
    t.start()
    for _ in range(100):
        if BUS.has(gid):
            break
        time.sleep(0.05)
    steps = [
        {"wait": "document.querySelector('#status-chip').textContent === 'ENDED'", "timeout": 90000},
        {"sleep": 2500},
        {"eval": BOARD},
        {"eval": "(() => { const r = app.game.byKey.get('0:901'); return r && r.reply && [r.reply.choice, r.reply.sent]; })()"},
        {"eval": "(() => { let bad = 0; const t = timeline(app.game); for (let k = 0; k < t.length; k++) { "
                 "try { seek(k); } catch (e) { bad++; console.error('seek', k, e); } } return [t.length, bad]; })()"},
        {"eval": "app.renderErrors || 0"},
    ]
    values = run_check(f"{panel.url}?game={gid}", steps, tmp_path)
    t.join(30)
    final, announced, (decisions, bad), errors = values[2], values[3], values[4], values[5]
    turn, lp = final_board(GAME)
    assert final["turn"] == turn and final["lp"] == lp and final["errors"] == 0, final
    assert announced == [[1], [50078509]]  # the panel gets the option index; the bot was sent the code
    assert decisions > 28 and bad == 0 and errors == 0
