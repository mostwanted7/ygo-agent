"""The opponent pool and the first-player schedule (no WindBot run here; test_pipeline plays real games)."""

from types import SimpleNamespace

from ygo_agent.trainer import compare, games


def test_bot_deck_files_are_found_despite_their_names(tmp_path):
    decks = tmp_path / "Decks"
    decks.mkdir()
    for name in ("AI_BlueEyes.ydk", "AI_Level8.ydk", "AI_Rank5.ydk", "AI_Dragunity.ydk"):
        (decks / name).write_text("#main\n")
    wb = SimpleNamespace(assets=str(tmp_path))
    bot = lambda name, deck: SimpleNamespace(name=name, deck=deck)  # noqa: E731
    assert games.bot_deck_file(wb, bot("Blue-Eyes", "Blue-Eyes")).endswith("AI_BlueEyes.ydk")
    assert games.bot_deck_file(wb, bot("Rose Scrap Synchro", "Level VIII")).endswith("AI_Level8.ydk")
    assert games.bot_deck_file(wb, bot("R5NK", "Rank V")).endswith("AI_Rank5.ydk")
    assert games.bot_deck_file(wb, bot("Nope", "Nope")) is None


def test_non_windbot_opponents_pass_and_humans_dont():
    ok, problems = games.check_pool(["heuristic:saffira", "blackwing:sonnet", "human", "windbot:"], None, None)
    assert ok == ["heuristic:saffira", "blackwing:sonnet"] and len(problems) == 2


class FakeRoom:
    def __init__(self, agent):
        self.slots = [agent, SimpleNamespace(is_local=False, name="WindBot")]
        self.chosen = None

    def _ask_first(self, chooser):
        self.chosen = (chooser, chooser.seat.go_first())


def test_force_first_makes_the_agent_choose():
    for want in (True, False):
        agent = SimpleNamespace(is_local=True, seat=SimpleNamespace(go_first=lambda: None))
        room = FakeRoom(agent)
        games.force_first(want)(room)
        room._ask_first(room.slots[1])  # the WindBot won the RPS...
        assert room.chosen == (agent, want)  # ...but the agent chooses, as scheduled


def test_compare_report(tmp_path):
    from ygo_agent.trainer.workspace import Workspace
    ws = Workspace(str(tmp_path / "deck"), quiet=True)
    results = {"trained-1": {"variant": "trained", "result": "win", "first": True, "turns": 7, "cost": 2.0},
               "trained-2": {"variant": "trained", "result": "loss", "first": False, "turns": 9, "cost": 2.5},
               "none-1": {"variant": "none", "result": "loss", "first": True, "turns": 6, "cost": 1.0}}
    path = compare.write_report(ws, results, ["trained", "none"], 2, "windbot:Blue-Eyes", "sonnet", None)
    text = open(path).read()
    assert "| trained | 2 | 1-1-0 | 50% | 8.0 | $4.50 |" in text
    assert "| none | 1 | 0-1-0 | 0% |" in text and "| 2 | loss (2nd, 9t) | – |" in text
