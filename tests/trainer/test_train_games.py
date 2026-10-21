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


def test_the_schedule_decides_who_goes_first(monkeypatch):
    """run_games' `first` (the agent is seat A), for a WindBot opponent as for an AI one: no room patching."""
    from ygo_agent.match import GameResult, RunResult, SeatResult
    calls = []

    def fake_run_games(a, b, games, **kw):
        calls.append((b.kind, kw.get("first"), kw.get("on_room")))
        seats = [SeatResult("A", str(a), "agent", "me", "Deck", result="win", stats={}),
                 SeatResult("B", str(b), b.kind, "them", "Them", result="loss")]
        game = GameResult(1, 1, 0, "LP reached 0", 5, 1.0, kw.get("first") or 0, 1, seats)
        return RunResult(specs=[str(a), str(b)], names=["A", "B"], games=[game])
    monkeypatch.setattr(games, "run_games", fake_run_games)
    player = games.SeatSpec.parse("saffira:heuristic")
    for opponent in ("windbot:Blue-Eyes", "blackwing:heuristic"):
        for first, want in ((True, 0), (False, 1), (None, None)):
            record = games.play_game(player, opponent, seed=1, first=first, cfg={}, db=None, engine=None, out="x")
            assert calls[-1] == (games.SeatSpec.parse(opponent).kind, want, None)
            assert record["result"] == "win"


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
