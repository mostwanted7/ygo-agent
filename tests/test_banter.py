import random

from ygo_agent.agent.banter import LINES, Banter


def test_at_most_four_lines_and_one_big_play():
    for seed in range(50):
        b = Banter(rng=random.Random(seed))
        said = [b.line(m) for m in ["start", "start"] + ["boss", "wipe"] * 10]
        said.append(b.result(0))
        said = [s for s in said if s]
        assert len(said) <= Banter.MAX
        assert sum(s in LINES["boss"] or s in LINES["wipe"] for s in said) <= 1
        assert sum(s in LINES["start"] for s in said) == 1
        assert said[-1] in LINES["win"]


def test_cap_holds_even_with_many_moments():
    b = Banter(rng=random.Random(1))
    b.MAX = 2
    assert b.line("start") and b.result(1)
    assert b.line("draw") is None


def test_off_says_nothing():
    b = Banter(enabled=False)
    assert all(b.line(m) is None for m in LINES)


def test_lines_are_short():
    assert all(0 < len(line) <= 100 for lines in LINES.values() for line in lines)
