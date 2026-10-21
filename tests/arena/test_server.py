"""The network host, end to end over TCP, with Python clients that speak EDOPro's protocol (no mono needed)."""

import asyncio
import socket
import struct

import pytest

from arena_helpers import client_policy
from ygo_agent.arena import protocol as P
from ygo_agent.arena import server as S
from ygo_agent.arena.client import ArenaClient, chat_texts
from ygo_agent.arena.deck import Deck
from ygo_agent.arena.duel import DuelConfig
from ygo_agent.arena.policies import RandomPolicy
from ygo_agent.arena.replay import parse_replay
from ygo_agent.arena.seats import PolicySeat
from ygo_agent.core.constants import PROMPT_MESSAGES, Msg

pytestmark = pytest.mark.integration

HOST = "127.0.0.1"


def run(coro, timeout=90):
    return asyncio.run(asyncio.wait_for(coro, timeout))


async def start(engine, **kw):
    kw.setdefault("lan_discovery", False)
    kw.setdefault("seed", 1)
    room = S.Room(engine, S.RoomConfig(**kw))
    server = S.ArenaServer(room, HOST, 0)
    await server.start()
    return room, server


async def until(cond, timeout=30.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.01)


def packets(client, pid):
    return [p for i, p in client.log.packets if i == pid]


def test_two_clients_and_a_spectator_play_a_game(engine, decks):
    async def scenario():
        room, server = await start(engine, max_matches=1, rematch=False)
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 1)).connect(HOST, server.port)
        b = await ArenaClient("Bob", decks["Blackwing"], client_policy(engine, 2), edopro=False).connect(HOST,
                                                                                                          server.port)
        spec = await ArenaClient("Watcher").connect(HOST, server.port)
        await until(lambda: room.stage != S.Stage.LOBBY)
        a.chat("good luck")
        await asyncio.wait_for(room.finished.wait(), 60)
        await asyncio.sleep(0.2)
        await server.close()
        return room, a, b, spec
    room, a, b, spec = run(scenario())
    duel, result = room.games[0]
    assert result.retries == 0 and not result.lua_errors
    assert a.log.position == 0 and b.log.position == 1 and spec.log.position == 7
    assert a.log.is_host and not b.log.is_host
    assert {a.log.team, b.log.team} == {0, 1}
    start_msgs = [m for m in spec.log.game if m[0] == Msg.START]
    assert start_msgs and start_msgs[0][1] & 0x10
    for c, team in ((a, a.log.team), (b, b.log.team)):
        prompts = [m for m in c.log.game if m[0] in PROMPT_MESSAGES]
        assert prompts and all(m[1] == team for m in prompts)
        assert any(m[0] == Msg.WAITING for m in c.log.game)
        assert c.log.game[-1][0] == Msg.WIN or any(m[0] == Msg.WIN for m in c.log.game)
    assert not any(m[0] in PROMPT_MESSAGES or m[0] == Msg.WAITING for m in spec.log.game)
    # chat: CHAT_2 with names for EDOPro clients, legacy STOC_CHAT for the other
    assert ("Alice", "good luck") in a.log.chats and ("Alice", "good luck") in spec.log.chats
    assert "good luck" in chat_texts(b.log) and packets(b, P.STOC_CHAT) and not packets(b, P.STOC_CHAT_2)
    # everyone got the replay, and it is the host's replay of this game
    rep = parse_replay(a.log.replay)
    assert rep.packets == duel.replay.packets and packets(a, P.STOC_REPLAY)
    assert packets(a, P.STOC_DUEL_END) and packets(spec, P.STOC_DUEL_END)


def test_late_spectator_catches_up(engine, decks):
    async def scenario():
        room, server = await start(engine, max_matches=1, rematch=False)
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 3), respond_delay=0.003).connect(
            HOST, server.port)
        b = await ArenaClient("Bob", decks["Blackwing"], client_policy(engine, 4)).connect(HOST, server.port)
        early = await ArenaClient("Early").connect(HOST, server.port)
        await until(lambda: room.duel is not None and room.duel.turn >= 3)
        late = await ArenaClient("Late").connect(HOST, server.port)
        await asyncio.wait_for(room.finished.wait(), 60)
        await asyncio.sleep(0.2)
        await server.close()
        return early, late
    early, late = run(scenario())
    assert packets(late, P.STOC_CATCHUP) == [b"\x01", b"\x00"]
    assert late.log.catchup and late.log.catchup[0][0] == Msg.START
    uncached = (Msg.HINT, Msg.WAITING, Msg.WIN)
    assert [m for m in late.log.game if m[0] not in uncached] == [m for m in early.log.game if m[0] not in uncached]
    assert P.STOC_DUEL_START in [i for i, _ in late.log.packets]


def test_surrender_and_disconnect(engine, decks):
    async def scenario(disconnect):
        room, server = await start(engine, max_matches=1, rematch=False)
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 5), respond_delay=0.002).connect(
            HOST, server.port)
        b = await ArenaClient("Bob", decks["Blackwing"], client_policy(engine, 6)).connect(HOST, server.port)
        await until(lambda: room.duel is not None and room.duel.turn >= 2)
        if disconnect:
            await a.close()
        else:
            a.surrender()
        await asyncio.wait_for(room.finished.wait(), 30)
        await server.close()
        return room, a, b
    for disconnect, reason in ((False, 0x0), (True, 0x4)):
        room, a, b = run(scenario(disconnect))
        duel, result = room.games[0]
        assert result.reason == reason
        alice_team = room.games[0][0].names.index("Alice")
        assert result.winner == 1 - alice_team
        assert any(m[0] == Msg.WIN and m[2] == reason for m in b.log.game)


def test_time_limit(engine, decks, monkeypatch):
    monkeypatch.setattr(S, "TIME_BONUS", 0)
    monkeypatch.setattr(S, "TIME_GRACE", 0.2)

    async def scenario():
        room, server = await start(engine, max_matches=1, rematch=False, time_limit=1)
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 7), stall=True,
                              go_first=True).connect(HOST, server.port)
        b = await ArenaClient("Bob", decks["Blackwing"], client_policy(engine, 8), go_first=False).connect(
            HOST, server.port)
        await asyncio.wait_for(room.finished.wait(), 30)
        await server.close()
        return room, a, b
    room, a, b = run(scenario())
    duel, result = room.games[0]
    assert result.reason == 0x3 and duel.names[1 - result.winner] == "Alice"
    limits = packets(b, P.STOC_TIME_LIMIT)
    assert limits and all(len(x) == 4 for x in limits)
    assert P.CTOS_TIME_CONFIRM  # clients answer STOC_TIME_LIMIT; the host ignores it like EDOPro's


def test_deck_password_and_version_errors(engine, decks):
    async def scenario():
        room, server = await start(engine, password="pw")
        bad_pw = await ArenaClient("NoPw", decks["Saffira"]).connect(HOST, server.port)
        old = await ArenaClient("Old", decks["Saffira"], password="pw",
                                version=P.ClientVersion(40, 1, 10, 0)).connect(HOST, server.port)
        small = await ArenaClient("Small", Deck(decks["Saffira"].main[:30]), password="pw").connect(HOST,
                                                                                                     server.port)
        await until(lambda: bad_pw.log.errors and old.log.errors and small.log.errors)
        state = room.stage, [p.ready if p else None for p in room.slots]
        await server.close()
        return bad_pw, old, small, state
    bad_pw, old, small, state = run(scenario())
    assert bad_pw.log.errors[0] == P.join_error(P.JOINERROR_PASSWORD)
    assert old.log.errors[0][0] == P.ERRMSG_VERERROR2 and old.log.errors[0][4:8] == bytes((41, 0, 11, 0))
    err = small.log.errors[0]
    assert err[0] == P.ERRMSG_DECKERROR and struct.unpack_from("<4I", err, 4) == (6, 30, 40, 60)
    assert P.player_change(0, P.PLAYERCHANGE_NOTREADY) in packets(small, P.STOC_HS_PLAYER_CHANGE)
    assert state == (S.Stage.LOBBY, [False, None])


def test_best_of_three_with_side_decking(engine, decks):
    async def scenario():
        room, server = await start(engine, best_of=3, max_matches=1, rematch=False)
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 9)).connect(HOST, server.port)
        b = await ArenaClient("Bob", decks["Blackwing"], client_policy(engine, 10)).connect(HOST, server.port)
        spec = await ArenaClient("Spec").connect(HOST, server.port)
        await asyncio.wait_for(room.finished.wait(), 90)
        await server.close()
        return room, a, spec
    room, a, spec = run(scenario(), timeout=120)
    assert 2 <= len(room.games) <= 3
    assert max(room.match_results.count(0), room.match_results.count(1)) == 2
    assert len(packets(a, P.STOC_CHANGE_SIDE)) == len(room.games) - 1
    assert len(packets(spec, P.STOC_WAITING_SIDE)) == len(room.games) - 1
    assert all(r.retries == 0 for _, r in room.games)


def test_rematch_and_a_local_seat(engine, decks):
    async def scenario():
        room, server = await start(engine, max_matches=2, rematch=True)
        room.add_local(1, PolicySeat("Local AI", RandomPolicy(3)), decks["Blackwing"])
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 11), rematch=True).connect(
            HOST, server.port)
        await asyncio.wait_for(room.finished.wait(), 60)
        await server.close()
        return room, a
    room, a = run(scenario())
    assert len(room.games) == 2 and all(r.retries == 0 for _, r in room.games)
    assert packets(a, P.STOC_REMATCH) and packets(a, P.STOC_WAITING_REMATCH)
    assert ("Local AI", 1) in [P.parse_player_enter(p) for p in packets(a, P.STOC_HS_PLAYER_ENTER)]


def test_lobby_moves_and_kick(engine, decks):
    async def scenario():
        room, server = await start(engine, auto_start=False)
        host = await ArenaClient("Host", decks["Saffira"], auto_ready=False).connect(HOST, server.port)
        guest = await ArenaClient("Guest", decks["Blackwing"], auto_ready=False).connect(HOST, server.port)
        await until(lambda: room.slots[1] is guest_slot(room))
        guest.send(P.CTOS_HS_TOOBSERVER)
        await until(lambda: room.slots[1] is None and len(room.observers) == 1)
        guest.send(P.CTOS_HS_TODUELIST)
        await until(lambda: room.slots[1] is not None)
        host.send(P.CTOS_HS_KICK, b"\x01")
        await until(lambda: room.slots[1] is None)
        await server.close()
        return host, guest
    host, guest = run(scenario())
    changes = packets(host, P.STOC_HS_PLAYER_CHANGE)
    assert P.player_change(1, P.PLAYERCHANGE_OBSERVE) in changes
    assert P.player_change(1, P.PLAYERCHANGE_LEAVE) in changes


def guest_slot(room):
    return next((c for c in room.clients if c.name == "Guest"), None)


def test_lan_discovery_reply(engine):
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, P.LAN_REPLY_PORT))
    except OSError as e:
        pytest.skip(f"cannot bind UDP {P.LAN_REPLY_PORT}: {e}")
    listener.settimeout(3)

    async def scenario():
        room, server = await start(engine, lan_discovery=True, name="Test Room")
        if server._udp is None:
            await server.close()
            pytest.skip("UDP 7920 is in use")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(struct.pack("<H", P.NETWORK_CLIENT_ID), (HOST, P.LAN_DISCOVERY_PORT))
        await asyncio.sleep(0.3)
        data = await asyncio.get_running_loop().run_in_executor(None, listener.recv, 1024)
        port = server.port
        await server.close()
        return data, port
    try:
        data, port = run(scenario())
    finally:
        listener.close()
    assert len(data) == P.HOST_PACKET_SIZE
    ident, _ver, got_port = struct.unpack_from("<HHH", data, 0)
    assert ident == P.NETWORK_SERVER_ID and got_port == port
    assert data[12:12 + 2 * len("Test Room")].decode("utf-16-le") == "Test Room"
    info = P.HostInfo.unpack(data[52:])
    assert info.duel_flags == DuelConfig().flags and info.handshake == P.SERVER_HANDSHAKE


class SlowSeat(PolicySeat):
    """An in-process seat that answers asynchronously (as an LLM-backed seat would)."""

    def __init__(self, name, policy, stall_after=None):
        super().__init__(name, policy)
        self.asked, self.stall_after = 0, stall_after

    async def _answer(self, prompt):
        self.asked += 1
        if self.stall_after is not None and self.asked > self.stall_after:
            await asyncio.sleep(3600)
        await asyncio.sleep(0.0005)
        return self.policy(prompt, self.view)

    def choose(self, prompt, retry):
        return self._answer(prompt)


def test_async_local_seat_and_surrender_while_it_thinks(engine, decks):
    async def scenario(stall_after):
        room, server = await start(engine, max_matches=1, rematch=False)
        seat = SlowSeat("Thinker", RandomPolicy(5), stall_after)
        room.add_local(1, seat, decks["Blackwing"])
        a = await ArenaClient("Alice", decks["Saffira"], client_policy(engine, 12)).connect(HOST, server.port)
        if stall_after is not None:
            await until(lambda: seat.asked > stall_after)
            a.surrender()
        await asyncio.wait_for(room.finished.wait(), 60)
        await server.close()
        return room
    room = run(scenario(None))
    assert room.games[0][1].retries == 0 and room.games[0][1].reason in (1, 2)
    room = run(scenario(3))
    duel, result = room.games[0]
    assert result.reason == 0 and duel.names[result.winner] == "Thinker"
