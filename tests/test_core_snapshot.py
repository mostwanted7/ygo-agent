"""The core is loaded from a private copy, so EDOPro's updater rewriting its file can't crash a running game."""

import os

from ygo_agent.core.ocgcore import _snapshot


def test_snapshot_copies_by_content(tmp_path):
    src = tmp_path / "edopro" / "libocgcore.so"
    src.parent.mkdir()
    src.write_bytes(b"core v1")
    cache = str(tmp_path / "cache")

    first = _snapshot(str(src), cache)
    assert first != str(src) and open(first, "rb").read() == b"core v1"
    assert _snapshot(str(src), cache) == first  # same content, same copy

    src.write_bytes(b"core v2")  # EDOPro updates in place
    second = _snapshot(str(src), cache)
    assert second != first
    assert open(first, "rb").read() == b"core v1"  # the copy a running game loaded is untouched
    assert open(second, "rb").read() == b"core v2"


def test_snapshot_keeps_three_copies(tmp_path):
    src = tmp_path / "libocgcore.so"
    cache = tmp_path / "cache"
    for i in range(5):
        src.write_bytes(f"core v{i}".encode())
        path = _snapshot(str(src), str(cache))
        os.utime(path, (i, i))
    assert len(os.listdir(cache)) == 3


def test_snapshot_falls_back_to_the_original(tmp_path):
    src = tmp_path / "libocgcore.so"
    src.write_bytes(b"core")
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("")
    assert _snapshot(str(src), str(blocked / "cache")) == str(src)
