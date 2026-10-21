"""Packet framing and struct layouts (sizes and offsets from EDOPro's network.h)."""

import struct

import pytest

from ygo_agent.arena import protocol as P


def test_frame_roundtrip_and_partial_reads():
    packets = [(P.STOC_GAME_MSG, b"\x0b" + bytes(range(40))), (P.STOC_DUEL_START, b""),
               (P.STOC_CHAT_2, P.chat2(P.CHAT2_DUELIST, True, "Ann", "hi"))]
    wire = b"".join(P.frame(pid, data) for pid, data in packets)
    assert wire[:2] == struct.pack("<H", 1 + 41)
    reader = P.PacketReader()
    got = []
    for i in range(0, len(wire), 3):  # byte-dribbled
        got += reader.feed(wire[i:i + 3])
    assert got == packets


def test_empty_packets_are_skipped():
    assert P.PacketReader().feed(b"\0\0" + P.frame(P.CTOS_HS_READY)) == [(P.CTOS_HS_READY, b"")]


def test_frame_rejects_oversized_payload():
    with pytest.raises(P.ProtocolError):
        P.frame(P.STOC_NEW_REPLAY, b"x" * 70000)


def test_host_info_layout():
    info = P.HostInfo(lflist=0x1234, rule=3, start_lp=8000, start_hand=5, draw_count=1, time_limit=180,
                      duel_flags=0x1_000D1800, best_of=3, forbidden_types=0x4000000)
    raw = info.pack()
    assert len(raw) == P.HostInfo.SIZE == 68
    assert struct.unpack_from("<I", raw, 0)[0] == 0x1234
    assert raw[4] == 3
    assert struct.unpack_from("<I", raw, 12)[0] == 8000
    assert struct.unpack_from("<H", raw, 18)[0] == 180
    assert struct.unpack_from("<I", raw, 20)[0] == 1                 # duel_flag_high
    assert struct.unpack_from("<I", raw, 24)[0] == P.SERVER_HANDSHAKE
    assert raw[28:32] == bytes((41, 0, 11, 0))
    assert struct.unpack_from("<iii", raw, 32) == (1, 1, 3)
    assert struct.unpack_from("<I", raw, 44)[0] == 0xD1800            # duel_flag_low
    assert struct.unpack_from("<I", raw, 48)[0] == 0x4000000
    assert struct.unpack_from("<6H", raw, 54) == (40, 60, 0, 15, 0, 15)
    assert P.HostInfo.unpack(raw) == info


def test_client_version_matches_windbot_number():
    assert P.ClientVersion(41, 0, 11, 0).as_int == 720937


def test_join_game_layout():
    pkt = P.JoinGame(P.PRO_VERSION, 0, "pw", P.ClientVersion())
    raw = pkt.pack()
    assert len(raw) == 52
    assert raw[48:52] == bytes((41, 0, 11, 0))
    assert P.JoinGame.unpack(raw) == pkt
    with pytest.raises(P.ProtocolError):
        P.JoinGame.unpack(raw[:40])


def test_lobby_structs():
    enter = P.player_enter("Alice", 1)
    assert len(enter) == 42 and enter[40] == 1
    assert P.parse_player_enter(enter) == ("Alice", 1)
    assert P.player_change(1, P.PLAYERCHANGE_READY) == bytes((0x19,))
    assert P.watch_change(3) == b"\x03\x00"
    assert P.time_limit(1, 175) == b"\x01\x00\xaf\x00"


def test_chat_layouts():
    c2 = P.chat2(P.CHAT2_OBSERVER, False, "Spec", "gg")
    assert len(c2) == 42 + 2 * len("gg") + 2   # what GenericDuel::Chat sends: 4 + 40 + msglen * 2
    assert P.parse_chat2(c2) == (P.CHAT2_OBSERVER, False, "Spec", "gg")
    legacy = P.chat(1, "hello")
    assert P.parse_chat(legacy) == (1, "hello")


def test_error_layouts():
    deck = P.deck_error(6, code=0, current=39, minimum=40, maximum=60)
    assert len(deck) == 24 and deck[0] == P.ERRMSG_DECKERROR
    assert struct.unpack_from("<5I", deck, 4) == (6, 39, 40, 60, 0)
    assert P.join_error(P.JOINERROR_PASSWORD) == b"\x01\x00\x00\x00\x01\x00\x00\x00"
    assert P.version_error(P.ClientVersion()) == b"\x05\x00\x00\x00\x29\x00\x0b\x00"


def test_update_deck_roundtrip_and_size_check():
    raw = P.update_deck([1, 2, 3], [9])
    assert P.parse_update_deck(raw) == ([1, 2, 3], [9])
    with pytest.raises(P.ProtocolError):
        P.parse_update_deck(struct.pack("<ii", 5, 0) + b"\0" * 8)


def test_host_packet_layout():
    raw = P.host_packet(7911, "Room", P.HostInfo())
    assert len(raw) == P.HOST_PACKET_SIZE == 120
    assert struct.unpack_from("<HHH", raw, 0) == (P.NETWORK_SERVER_ID, P.PRO_VERSION, 7911)
    assert P.HostInfo.unpack(raw[52:]) == P.HostInfo()
