"""Benchmark statistics: Wilson intervals, percentiles, Bradley-Terry ratings (no EDOPro, no LLM)."""

import math

import pytest

from ygo_agent.bench.metrics import bradley_terry, percentile, wilson


@pytest.mark.parametrize("k, n, lo, hi", [
    (5, 10, 0.2366, 0.7634),     # textbook values
    (0, 10, 0.0, 0.2775),
    (10, 10, 0.7225, 1.0),
    (1, 6, 0.0300, 0.5635),
    (81, 263, 0.2553, 0.3662),   # Wilson (1927) / Newcombe (1998) worked example
])
def test_wilson_known_values(k, n, lo, hi):
    a, b = wilson(k, n)
    assert a == pytest.approx(lo, abs=1e-4) and b == pytest.approx(hi, abs=1e-4)


def test_wilson_edge_cases():
    assert wilson(0, 0) is None
    a, b = wilson(3, 7)
    assert 0 <= a < 3 / 7 < b <= 1
    # symmetric: k successes and k failures mirror each other
    a1, b1 = wilson(2, 9)
    a2, b2 = wilson(7, 9)
    assert a1 == pytest.approx(1 - b2) and b1 == pytest.approx(1 - a2)
    # narrower with more games at the same rate
    assert (lambda ci: ci[1] - ci[0])(wilson(50, 100)) < (lambda ci: ci[1] - ci[0])(wilson(5, 10))


def test_percentile_nearest_rank():
    values = list(range(1, 21))  # 1..20
    assert percentile(values, 0.5) == 10
    assert percentile(values, 0.95) == 19
    assert percentile([4.2], 0.95) == 4.2
    assert percentile([], 0.5) is None
    assert percentile([3, 1, 2], 1.0) == 3


def test_bradley_terry_orders_and_stays_finite():
    games = [("a", "x", 1.0)] * 9 + [("a", "x", 0.0)] + [("b", "x", 1.0)] * 5 + [("b", "x", 0.0)] * 5 \
        + [("c", "x", 0.0)] * 10
    r = bradley_terry(games)
    assert r["a"] > r["b"] > r["c"]
    assert all(math.isfinite(v) for v in r.values())
    # b went 50/50 with x, so they end up level with each other
    assert r["b"] == pytest.approx(r["x"], abs=40)


def test_bradley_terry_symmetry_and_anchor():
    r = bradley_terry([("a", "b", 1.0), ("a", "b", 0.0), ("a", "b", 0.5)])
    assert r["a"] == pytest.approx(r["b"]) == pytest.approx(1500)
    # an unbeaten player is pulled toward the anchor by the prior, not sent to infinity
    r = bradley_terry([("a", "b", 1.0)] * 3)
    assert 1500 < r["a"] < 2100 and 900 < r["b"] < 1500
    assert r["a"] - 1500 == pytest.approx(1500 - r["b"], abs=1e-6)
    assert bradley_terry([]) == {}


def test_bradley_terry_uses_transitivity():
    # a beats b, b beats c (each 3-1): a ends above c though they never met
    games = [("a", "b", 1.0)] * 3 + [("a", "b", 0.0)] + [("b", "c", 1.0)] * 3 + [("b", "c", 0.0)]
    r = bradley_terry(games)
    assert r["a"] > r["b"] > r["c"]
