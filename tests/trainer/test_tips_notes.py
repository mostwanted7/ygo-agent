import json
import os

from ygo_agent.trainer import notes, tips


def game(tmp_path, name, deck="geargia", mode="play", feedback=""):
    folder = tmp_path / name
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"deck": deck, "mode": mode}))
    if feedback:
        (folder / "feedback.md").write_text(feedback)
    return str(folder)


def test_tips_round_trip(tmp_path):
    deck = str(tmp_path / "chaos")
    assert tips.read(deck) == "" and tips.digest(deck) == ""
    assert tips.save_answers(deck, [{"question": "Go first?", "answer": "Yes, always."},
                                    {"question": "Skipped", "answer": "  "}], name="Chaos") == 1
    assert tips.add(deck, "Keep Lightpulsar for the end.\n## not a section")
    assert not tips.add(deck, "")
    got = tips.entries(deck)
    assert [e["title"] for e in got] == ["Go first?", "Tip"]
    assert got[0]["text"] == "Yes, always." and "not a section" in got[1]["text"] and got[1]["date"]
    assert tips.read(deck).startswith("# Tips for Chaos") and tips.digest(deck)


def test_notes_pending_trust_and_mark(tmp_path):
    a = game(tmp_path, "2026-10-22_100000_geargia", feedback=(
        "- (turn 3, right after decision #14; from Web panel) Attack first.\n"
        "- (turn 4, right after decision #20; from Spectator bob) Bad play.\n"
        "- (turn 1, right after decision #2) Old note without an author.\n"
        "  - Processed 2026-10-21: already fine\n"))
    game(tmp_path, "2026-10-22_110000_geargia", mode="selfplay",
         feedback="- (turn 2, right after decision #5; from Opponent ai) An AI's chat line.\n")
    game(tmp_path, "2026-10-22_120000_saffira", deck="saffira", feedback="- (turn 1, right after decision #1; "
                                                                         "from Web panel) Other deck.\n")
    os.symlink(a, tmp_path / "latest")
    every = notes.for_deck("Geargia", str(tmp_path))
    assert [n.key for n in every] == ["2026-10-22_110000_geargia:0", "2026-10-22_100000_geargia:0",
                                      "2026-10-22_100000_geargia:1", "2026-10-22_100000_geargia:2"]
    first = every[1]
    assert (first.decision, first.turn, first.author, first.trusted) == (14, 3, "Web panel", True)
    assert every[3].author == "Opponent" and every[3].learned.startswith("Processed")
    assert not every[0].trusted and not every[2].trusted
    todo = notes.pending("geargia", str(tmp_path))
    assert [n.text for n in todo] == ["Attack first."]
    assert len(notes.pending("geargia", str(tmp_path), include_untrusted=True)) == 3
    spectator = every[2]
    assert notes.mark(first, "new principle in Lethal check", when="2026-10-22")
    assert notes.mark(spectator, "disagree: the play was fine")  # its line moved down by one
    text = open(os.path.join(a, "feedback.md")).read().splitlines()
    assert text[1] == "  - Learned 2026-10-22: new principle in Lethal check"
    assert text[2].startswith("- (turn 4") and text[3].startswith("  - Learned")
    assert notes.pending("geargia", str(tmp_path)) == []
    assert [n.key for n in notes.for_deck("geargia", str(tmp_path))][1:] == [
        "2026-10-22_100000_geargia:0", "2026-10-22_100000_geargia:1", "2026-10-22_100000_geargia:2"]
