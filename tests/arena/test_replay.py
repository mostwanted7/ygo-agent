"""EDOPro replays: our writer/reader round trip, LZMA compatibility, and byte-for-byte agreement with a
replay EDOPro itself recorded."""

import lzma
import os
import struct
import subprocess

import pytest

from ygo_agent.arena import replay as R
from ygo_agent.core.constants import OLD_REPLAY_MODE

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def recorder():
    rec = R.ReplayRecorder(seed=(1, 2, 3, 4), duel_flags=0xD1800, start_lp=8000, start_hand=5, draw_count=1,
                           names=(["Alice"], ["Bob"]), timestamp=1_700_000_000)
    rec.decks = [([1, 2, 3], [9]), ([4, 5], [])]
    rec.record(bytes([4, 0]) + struct.pack("<IIHHHH", 8000, 8000, 3, 1, 2, 0))
    rec.record(bytes([40, 0]))
    rec.respond(b"\x07\x00\x00\x00")
    rec.respond(b"\xff")
    rec.pop_response()
    return rec


@pytest.mark.parametrize("compress", [True, False])
def test_yrpx_roundtrip(compress):
    rec = recorder()
    data = rec.yrpx(compress=compress)
    assert struct.unpack_from("<I", data, 0)[0] == R.REPLAY_YRPX
    flag = struct.unpack_from("<I", data, 8)[0]
    assert flag & R.REPLAY_EXTENDED_HEADER and flag & R.REPLAY_NEWREPLAY and flag & R.REPLAY_64BIT_DUELFLAG
    assert bool(flag & R.REPLAY_COMPRESSED) == compress
    rep = R.parse_replay(data)
    assert rep.is_streamed and rep.names == (["Alice"], ["Bob"]) and rep.duel_flags == 0xD1800
    assert rep.packets == rec.packets and rep.seed == (1, 2, 3, 4) and rep.turns == 1
    old = rep.embedded
    assert old.header.id == R.REPLAY_YRP1 and old.header.header_version == 1
    assert old.decks == rec.decks and old.responses == [b"\x07\x00\x00\x00"]
    assert (old.start_lp, old.start_hand, old.draw_count) == (8000, 5, 1)


def test_header_and_props_match_edopro_defaults():
    data = recorder().yrpx()
    rid, version, flag, ts, size, h = struct.unpack_from("<6I", data, 0)
    assert version == 720937 and ts == 1_700_000_000
    assert data[24:29] == b"\x5d\x00\x00\x00\x01"    # LzmaCompress(level 5, dict 1 << 24, lc 3, lp 0, pb 2)
    assert struct.unpack_from("<Q", data, 32)[0] == 1 and struct.unpack_from("<4Q", data, 40) == (1, 2, 3, 4)


def test_custom_start_states_skip_the_old_replay():
    rec = recorder()
    rec.old_replay_valid = False
    assert R.parse_replay(rec.yrpx()).embedded is None


def test_rejects_garbage():
    with pytest.raises(R.ReplayError):
        R.parse_replay(b"nope")
    with pytest.raises(R.ReplayError):
        R.parse_replay(b"\0" * 80)


@pytest.mark.integration
def test_7zip_decodes_our_lzma_stream(tmp_path, seven_zip):
    """7-Zip's LZMA decoder is the LZMA SDK EDOPro uses; feed it our raw stream as a .lzma file."""
    rec = recorder()
    for i in range(200):
        rec.record(bytes([90, 0]) + struct.pack("<III", 1, 1000 + i, 10))
    body = rec.yrpx_body()
    data = rec.yrpx()
    (tmp_path / "r.lzma").write_bytes(data[24:29] + struct.pack("<Q", len(body)) + data[R.HEADER_SIZE:])
    subprocess.run([seven_zip, "x", "-y", f"-o{tmp_path}", str(tmp_path / "r.lzma")], check=True,
                   capture_output=True)
    assert (tmp_path / "r").read_bytes() == body


def edopro_fixture():
    with lzma.open(os.path.join(FIXTURES, "edopro_bo1_mr3.yrpX.xz")) as f:
        return f.read()


def test_parse_a_replay_edopro_wrote():
    rep = R.parse_replay(edopro_fixture())
    assert rep.is_streamed and rep.names == (["[AI] Blue-Eyes"], ["Claude"])
    assert rep.duel_flags == 0xD1800 and len(rep.packets) == 470
    assert rep.embedded is not None and len(rep.embedded.responses) == 58
    assert [len(m) for m, _ in rep.embedded.decks] == [40, 40]


@pytest.mark.integration
def test_resimulating_edopros_replay_reproduces_its_stream(engine):
    """Same seed, decks and responses through our duel driver → the same message stream EDOPro's host
    recorded, byte for byte (EDOPro repeats its last batch once at the end; see replay.py)."""
    from ygo_agent.arena.runner import replay_duel
    rep = R.parse_replay(edopro_fixture())
    duel = replay_duel(engine, rep)
    try:
        ours = duel.replay.packets
        assert rep.packets[-4:] == rep.packets[-8:-4]
        assert R.streams_match(ours, rep.packets[:-4]), (
            "stream differs; EDOPro's card scripts may have changed since the fixture was recorded (2026-10-21)")
    finally:
        duel.close()


@pytest.mark.integration
def test_our_replays_resimulate_to_the_same_stream(engine, decks, tmp_path):
    from ygo_agent.arena.duel import DuelConfig
    from ygo_agent.arena.policies import RandomPolicy
    from ygo_agent.arena.runner import replay_duel, run_duel
    from ygo_agent.arena.seats import PolicySeat
    duel = run_duel(engine, DuelConfig(), (decks["Saffira"], decks["Blackwing"]),
                    (PolicySeat("A", RandomPolicy(1)), PolicySeat("B", RandomPolicy(2))), seed=11)
    path = tmp_path / "game.yrpX"
    path.write_bytes(duel.replay.yrpx())
    duel.close()
    rep = R.read_replay(str(path))
    assert rep.packets[-1][0] == 5  # MSG_WIN
    again = replay_duel(engine, rep)
    assert R.streams_match(again.replay.packets, rep.packets) and again.result.winner == rep.packets[-1][1]
    again.close()


def test_streams_match_ignores_only_hint_order():
    hint_a, hint_b = bytes([160, 1]), bytes([165, 2])
    a = [bytes([40, 0]), hint_a, hint_b, bytes([41, 4, 0])]
    assert R.streams_match(a, [a[0], hint_b, hint_a, a[3]])
    assert not R.streams_match(a, [a[0], hint_a, a[3], hint_b])
    assert not R.streams_match(a, [a[0], hint_a, hint_a, a[3]])


def test_old_replay_packet_id():
    assert OLD_REPLAY_MODE == 231
