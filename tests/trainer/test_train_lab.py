"""The lab: hand planning (no EDOPro), the goldfish seat, stacked hands and the turn stop (real duels on the core)."""

import collections
import os

import pytest

from ygo_agent.trainer import dossier as dossier_mod
from ygo_agent.trainer import goldfish, lab
from ygo_agent.trainer.dossier import CardEntry, Dossier


def fake_dossier():
    def card(i, name, n):
        return CardEntry(i, name, n, "main", "", "", "Monster")
    cards = [card(1, "Geargiarsenal", 3), card(2, "Geargiaccelerator", 3), card(3, "Geargiarmor", 3),
             card(4, "Geargiano Mk-II", 2), card(5, "Pot of Greed", 1)] + [card(10 + k, f"Filler {k}", 3)
                                                                          for k in range(9)]
    return Dossier("Fake", cards, "", "")


LINES = [{"id": "L1", "name": "Arsenal", "going": "first", "key_cards": ["Geargiarsenal", "Geargiaccelerator"]},
         {"id": "L2", "name": "Mk-II", "going": "first", "key_cards": ["geargiano mk-ii", "Pot of Greed",
                                                                         "Pot of Greed"]},
         {"id": "L3", "name": "Duster", "going": "second", "key_cards": ["Harpie's Feather Duster"]},
         {"id": "L4", "name": "Armor", "going": "first", "key_cards": ["Geargiarmour"]}]


def test_plan_hands_stacks_each_line_and_fills_at_random():
    d = fake_dossier()
    hands = lab.plan_hands(d, LINES, 8, seed=1)
    assert len(hands) == 8 and len({h.id for h in hands}) == 8
    kinds = collections.Counter(h.kind for h in hands)
    assert kinds["line"] == 3 and kinds["second"] == 2 and kinds["random"] == 3
    l1 = next(h for h in hands if h.line == "L1")
    assert l1.first and len(l1.cards) == 5 and l1.cards[:2] == [1, 2]
    l2 = next(h for h in hands if h.line == "L2")
    assert l2.cards[:2] == [4, 5] and l2.missing == ["Pot of Greed"]  # only 1 copy in the deck
    l4 = next(h for h in hands if h.line == "L4")
    assert l4.cards[0] == 3  # "Geargiarmour" is close enough to "Geargiarmor"
    l3 = next(h for h in hands if h.line == "L3")
    assert not l3.first and len(l3.cards) == 6 and l3.missing == ["Harpie's Feather Duster"]
    main = collections.Counter(d.main_codes())
    for h in hands:
        assert all(collections.Counter(h.cards)[c] <= main[c] for c in h.cards)
    assert [h.cards for h in lab.plan_hands(d, LINES, 8, seed=1)] == [h.cards for h in hands]
    assert [h.cards for h in lab.plan_hands(d, LINES, 8, seed=2)] != [h.cards for h in hands]
    again = lab.LabHand.from_dict(hands[0].to_dict())
    assert again == hands[0]


def test_small_labs():
    d = fake_dossier()
    assert [h.kind for h in lab.plan_hands(d, LINES, 2, seed=1)] == ["line", "random"]
    assert lab.plan_hands(d, [], 0, seed=1) == []
    assert all(h.kind == "random" for h in lab.plan_hands(d, [], 3, seed=1))


@pytest.mark.integration
def test_goldfish_passes_and_the_stacked_hand_is_dealt(engine, agent_db, quiet):
    from ygo_agent.arena.deck import load_ydk
    from ygo_agent.arena.duel import DuelConfig
    from ygo_agent.arena.policies import SimplePolicy
    from ygo_agent.arena.runner import run_duel
    from ygo_agent.arena.seats import PolicySeat
    from ygo_agent.core.constants import LOCATION_HAND
    path = os.path.join(engine.install.deck_dir, "Blackwing.ydk")
    if not os.path.isfile(path):
        pytest.skip("no Blackwing.ydk")
    deck = load_ydk(path, engine.cards).deck
    hand = list(dict.fromkeys(deck.main))[:5]
    seen = {}

    class Watch(PolicySeat):
        def choose(self, prompt, retry):
            if "hand" not in seen:
                seen["hand"] = sorted(c.code for c in self.view.location(self.view.team, LOCATION_HAND))
            return super().choose(prompt, retry)
    player = Watch("player", SimplePolicy(3))
    stop = goldfish.TurnStop(0, last_turn=1)
    duel = run_duel(engine, DuelConfig(), (deck, deck.copy()), (player, goldfish.goldfish_seat()), seed=9,
                    stack={0: hand}, observers=[stop])
    try:
        assert seen["hand"] == sorted(hand)
        assert stop.stopped and duel.result.turns == 2 and duel.result.winner == 0
        assert stop.board["turn"] == 2 and stop.board["lp"] == [8000, 8000]
        assert not stop.board["opp"]["mzone"] and not stop.board["opp"]["szone"]  # the dummy never got to play
    finally:
        duel.close()
    # going second into the fixed board: the dummy passes turn 1, the player's turn 2 is recorded
    stop = goldfish.TurnStop(1, last_turn=2)
    duel = run_duel(engine, DuelConfig(), (deck, deck.copy()), (goldfish.goldfish_seat(), PolicySeat(
        "player", SimplePolicy(4))), seed=10, stack={1: list(dict.fromkeys(deck.main))[:6]},
        start_state=goldfish.common_board(0),
        observers=[stop])
    try:
        assert stop.stopped and duel.result.turns == 3
        assert stop.board["opp"]["mzone"] or stop.board["opp"]["gy"]  # the board was there
        assert len(goldfish.board_text(stop.board).splitlines()) >= 4
    finally:
        duel.close()


@pytest.mark.integration
def test_run_hand_with_the_heuristic_player(engine, agent_db, tmp_path, quiet):
    from ygo_agent.agent.profile import Profile
    from ygo_agent.config import backend, load_config
    path = os.path.join(engine.install.deck_dir, "Blackwing.ydk")
    if not os.path.isfile(path):
        pytest.skip("no Blackwing.ydk")
    cfg = load_config(local=None, overrides={"games_dir": str(tmp_path / "games"), "chat": "off"})
    profile = Profile("blackwing-lab", agent_db, cfg, ydk=path)
    d = dossier_mod.build(path, agent_db, engine.install.script_dirs, str(tmp_path / "train"), "Blackwing")
    hands = lab.plan_hands(d, [{"id": "L1", "name": "Simoon", "going": "first",
                                "key_cards": ["Blackwing - Simoon the Poison Wind"]}], 4, seed=3, second=1)
    out = tmp_path / "lab"
    out.mkdir()
    results = [lab.run_hand(h, engine, cfg, agent_db, profile, backend(cfg, "heuristic"), str(out), echo="off")
               for h in (hands[0], hands[-1])]
    first, second = results
    assert os.path.isfile(os.path.join(first["log"], "game.md")) and os.path.basename(first["log"]) == "hand-01"
    assert first["decisions"] > 0 and first["board"]["turn"] == 2 and first["engine_retries"] == 0
    assert first["after"]["turn"] == 3 and first["turns"] == 3  # the dummy's turn 2 was played out
    assert not first["after"]["opp"]["mzone"]  # ...and it did nothing
    assert "Blackwing - Simoon the Poison Wind" in first["names"]
    assert not second["first"] and second["board"]["turn"] == 3
    md = lab.results_markdown(results, [{"id": "L1", "name": "Simoon", "expected_board": ["X"]}],
                              goldfish.COMMON_BOARD_TEXT)
    assert "## hand-01 — line L1" in md and "Expected end board: X" in md and "going second" in md
    assert "After the dummy's turn" in md
    assert not (out / ".games-hand-01").exists()
