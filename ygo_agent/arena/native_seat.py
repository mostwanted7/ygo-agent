"""Native AI seats: the agent plays an arena seat in-process, with no WindBot or mono involved.

    seat = AgentSeat.create("saffira", backend="opus")       # or AgentSeat(name, cfg, db, profile, backend_profile)
    room.add_local(1, seat, seat.deck(engine))               # or run_duel(..., seats=(seat, other))

The seat turns its team's filtered message stream and its SeatView into the same events and decisions the WindBot
fork's BrainBridge sends (docs/decision-protocol.md; native_view.py and native_decide.py), hands them to a
`DuelBrain` (one per game, logging to games/<time>_<deck>-vs-<opponent>/ as usual), and encodes the reply as a core
response. Brain calls run in one worker thread per seat (they block on LLM calls), so `choose` returns an awaitable
and never blocks the event loop; heuristic/random backends answer inline. When the brain raises, times out or
answers something the engine can't take, the heuristic policy answers; after an engine RETRY the brain answers with
its own fallback, and the seat makes sure the same response isn't sent twice.

Also here: `add_to_room` (an AgentSeat at a Room position, with chat both ways), `link` (seats of one duel share
the web panel's game id), `PacedSeat` (a minimum time per answer for any in-process seat) and `SeatWatcher` (the
decisions of a seat someone else plays, and their responses as option indices: coach mode).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import time
import traceback

from ..backends.heuristic import Policy, first_legal
from .duel import VIEW_TEAM0, DuelObserver
from .messages import Message, Prompt
from .native_decide import ChoiceError, Decision, build
from .native_view import NativeView, empty_state
from .policies import RandomPolicy
from .seats import Seat, SeatView

INLINE_BACKENDS = ("heuristic", "random", "scripted")  # fast, pure: no worker thread needed


class AgentSeat(Seat):
    def __init__(self, name: str, cfg: dict, db, profile, backend: dict, *, cards=None, pace: float = 0.0,
                 threaded: bool | None = None, position: int = 0, chat=None, timeout: float | None = None,
                 mode: str | None = None, opponent: dict | None = None, log_options: dict | None = None):
        """`cfg`: the agent config (config.load_config()); `db`: the agent CardDB; `profile`: the deck Profile;
        `backend`: a backend profile dict ({"name", "type", ...}). `cards`: the arena CardDatabase (printed stats
        and declarable names); `pace`: minimum seconds per decision; `position`: the lobby seat (chat events);
        `chat(text)`: sends the agent's chat lines to the room. `mode`, `opponent` and `log_options` go to each
        game's DuelBrain (the prompt's mode and opponent, the log's terminal tag and verbosity)."""
        self.name = name
        self.cfg, self.db, self.profile, self.backend = cfg, db, profile, backend
        self.mode, self.opponent, self.log_options = mode, opponent, log_options
        self.cards = cards
        self.view: SeatView | None = None
        self.native = NativeView(0, cards)
        self.pace = pace
        self.position = position
        self.chat = chat
        if threaded is None:
            threaded = backend.get("type") not in INLINE_BACKENDS
        self._worker = concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix=f"agent-{name}") if threaded \
            else None
        agent = cfg["agent"]
        # The brain enforces its own per-ask deadline; this guard only catches a brain that never returns.
        self.timeout = timeout or 2 * float(agent.get("decision_timeout_seconds", 120)) + 60
        self.brain = None
        self.room_event: dict | None = None
        self.next_id = 0
        self.fallback = Policy(db)
        self.random = RandomPolicy()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last: tuple[int, bytes] | None = None  # (decision id, response) of the last answer, for RETRY
        self.trace: list | None = None   # tests: set to a list to collect every event and decision sent
        self.match_id: str | None = None  # the web panel's game id prefix, the same for both seats (see link())
        self.stats = {"decisions": 0, "auto": 0, "fallbacks": 0, "errors": 0, "timeouts": 0, "retries": 0,
                      "rejected": 0, "games": 0}
        self.closed = False

    @classmethod
    def create(cls, deck: str, backend: str | None = None, *, cfg: dict | None = None, db=None, cards=None,
               **kw) -> "AgentSeat":
        """A seat for deck profile `deck` (decks/<deck>/) and backend profile `backend` (default: agent.backend)."""
        from ..config import backend as backend_profile, load_config
        from ..agent.carddb import CardDB
        from ..agent.profile import Profile
        cfg = cfg or load_config()
        db = db or CardDB(cfg["edopro_dir"])
        profile = Profile(deck, db, cfg)
        prof = backend_profile(cfg, backend)
        name = kw.pop("name", None) or f"{profile.name} ({prof['name']})"
        return cls(name[:20], cfg, db, profile, prof, cards=cards, **kw)

    def deck(self, engine):
        """The arena Deck for this seat's .ydk."""
        from .deck import load_ydk
        return load_ydk(self.profile.ydk, engine.cards).deck

    # --- plumbing ---------------------------------------------------------------------------------------------------
    def _run(self, fn):
        """Run `fn` where the brain lives: the worker thread (in order), or inline."""
        if self._worker is None:
            return fn()
        return self._worker.submit(fn)

    def _call(self, fn, timeout: float = 30.0):
        """Run `fn` on the brain's thread and wait for it (only for quick, non-backend calls)."""
        result = self._run(fn)
        return result.result(timeout) if isinstance(result, concurrent.futures.Future) else result

    def _say(self, text: str | None) -> None:
        if not text or self.chat is None:
            return
        try:
            self.chat(text)
        except Exception:
            traceback.print_exc()

    def _say_later(self, text: str | None) -> None:
        """Chat from the worker thread: hand it to the event loop's thread when there is one."""
        if not text:
            return
        if self._loop is not None and self._worker is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._say, text)
        else:
            self._say(text)

    def _capture_loop(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    def _record(self, msg: dict) -> None:
        if self.trace is not None:
            self.trace.append(msg)

    # --- brains -------------------------------------------------------------------------------------------------------
    def _brain_for(self, msg: dict):
        """Bridge Match semantics: a new game starts with its `start` event or first decision after a `win`."""
        b = self.brain
        starts = msg.get("t") == "event" and msg.get("e") == "start"
        decides = msg.get("t") == "decide" and msg.get("kind") != "game_over"
        if b is None or (b.over and (starts or decides)) or (starts and b.started):
            if b is not None:
                b.close()
            self.brain = self._new_brain()
            self.stats["games"] += 1
        return self.brain

    def _new_brain(self):
        from ..agent.brain import DuelBrain
        kw = {"prewarm": True, "room": self.room_event, "backend": self.backend, "fallback": "heuristic",
              "seat": self.position, "mode": self.mode, "opponent": self.opponent, "log_options": self.log_options}
        if self.match_id:
            kw["game_id"] = f"{self.match_id}-g{self.stats['games'] + 1}"  # shared by every seat of the duel
        return DuelBrain(self.cfg, self.db, self.profile, **kw)

    def game_info(self) -> dict | None:
        """The current (or just finished) game as its brain saw it: `game` (1, 2, ... for this seat), `dir` (its log
        folder), `result` (win/loss/draw, None if it never ended), `stats` (meta.json's), `label`. Call it on the
        brain's thread (`collect`), so that every message sent before is accounted for."""
        b = self.brain
        if b is None:
            return None
        log = b._log
        return {"game": self.stats["games"], "dir": log.dir if log else None,
                "result": log.meta.get("result") if log else None, "stats": b.stats.summary(), "label": b.label,
                "log": log}

    def collect(self, fn=None):
        """game_info() once the brain has handled everything sent so far (it runs on the brain's thread, after them):
        a Future with the worker thread, else the value. `fn(info)` runs there too, e.g. to add to the game's log."""
        def run():
            info = self.game_info()
            if fn is not None and info is not None:
                fn(info)
            return info
        return self._run(run)

    def record_spectator(self, state):
        # Queue behind the seat's events, but bypass the brain and its prompt/history entirely.
        def record():
            if self.brain and self.brain._log:
                self.brain._log.record("spectator_state", {"state": state})
        self._run(record)

    def _event(self, ev: dict) -> None:
        brain = self._brain_for(ev)
        try:
            brain.on_event(ev)
        except Exception:
            print("[agent seat] event handling failed:\n" + traceback.format_exc())

    # --- Seat hooks ---------------------------------------------------------------------------------------------------
    def set_room(self, config) -> None:
        """The `room` event, from the room's DuelConfig (the host calls this before the first game, so the event
        comes first in every game's log; otherwise the first `bind` makes it). AI seats have no time limit."""
        if self.room_event is not None:
            return
        self.room_event = {"t": "event", "e": "room", "duel_flags": config.flags & ~0x10,
                           "forbidden_types": config.forbidden_types, "best_of": config.best_of, "teams": [1, 1],
                           "start_lp": config.lp, "start_hand": config.start_hand,
                           "draw_count": config.draw_count, "time_limit": 0}
        self._record(self.room_event)
        if self.brain is not None:  # a go_first decision came first: its game still gets the event
            room = self.room_event
            self._run(lambda: self.brain.on_event(room))

    def bind(self, view: SeatView) -> None:
        super().bind(view)
        self.native.bind(view)
        self.native.reset()
        self._last = None
        self.set_room(view.config)

    def on_message(self, msg: Message) -> None:
        self._capture_loop()
        for ev in self.native.on_message(msg):
            ev = {"t": "event", **ev}
            self._record(ev)
            if ev["e"] == "win":
                state = self._safe_state()
                self._run(lambda ev=ev, state=state: self._game_over(ev, state))
            else:
                self._run(lambda ev=ev: self._event(ev))

    def _safe_state(self) -> dict:
        try:
            return self.native.state()
        except Exception:
            return empty_state()

    def _game_over(self, ev: dict, state: dict) -> None:
        """`win`, then the game_over round trip (its reply may carry a last chat line); ids restart at 1."""
        self._event(ev)
        self.next_id += 1
        d = {"t": "decide", "id": self.next_id, "kind": "game_over", "result": ev["result"], "reason": ev["reason"],
             "state": state}
        self._record(d)
        self.next_id = 0
        try:
            reply = self.brain.on_decide(d)
            self._say_later(reply.get("say"))
        except Exception:
            print("[agent seat] game_over failed:\n" + traceback.format_exc())

    def room_chat(self, message: str, source: str = "duelist", name: str = "", own: bool = False) -> None:
        """A chat line from the room (`!notes` included): `source` duelist/spectator/system, `own` for our team."""
        if source == "duelist":
            player = self.position if own else 1 - self.position
        else:
            player = 7 if source == "spectator" else 8
        ev = {"t": "event", "e": "chat", "player": player, "position": self.position, "message": message,
              "source": source, "name": name}
        self._record(ev)

        def deliver():
            if self.brain is None:
                return
            self.brain.on_event(ev)
            if self.brain.say_queue:  # acknowledge a !note right away instead of with the next decision
                text = "\n".join(self.brain.say_queue)
                self.brain.say_queue.clear()
                self._say_later(text)
        self._run(deliver)

    def go_first(self) -> bool:
        self.next_id += 1
        d = {"t": "decide", "id": self.next_id, "kind": "go_first", "state": empty_state()}
        self._record(d)

        def ask():
            reply = self._brain_for(d).on_decide(d)
            self._say_later(reply.get("say"))
            return reply.get("choice")
        try:
            choice = self._call(ask)
        except Exception:
            traceback.print_exc()
            choice = None
        return choice != [0]

    def choose(self, prompt: Prompt, retry: bool):
        self._capture_loop()
        decision = build(prompt, self.native)
        if decision.kind is None:
            self.stats["auto"] += 1
            return decision.auto
        self.next_id += 1
        d = {"t": "decide", "id": self.next_id, "kind": decision.kind, **decision.fields,
             "state": self.native.state()}
        self._record(d)
        self.stats["decisions"] += 1
        if retry:
            self.stats["retries"] += 1
        if self._worker is None and not self.pace:
            return self._answer(prompt, decision, d, self._ask(d), retry)
        return self._choose_async(prompt, decision, d, retry)

    async def _choose_async(self, prompt: Prompt, decision: Decision, d: dict, retry: bool) -> bytes:
        started = time.monotonic()
        if self._worker is None:
            reply = self._ask(d)
        else:
            future = asyncio.wrap_future(self._worker.submit(self._ask, d))
            try:
                reply = await asyncio.wait_for(asyncio.shield(future), self.timeout)
            except asyncio.TimeoutError:
                self.stats["timeouts"] += 1
                self._note(f"decision #{d['id']} took over {self.timeout:.0f}s; the heuristic answered it instead")
                reply = None
        data = self._answer(prompt, decision, d, reply, retry)
        left = self.pace - (time.monotonic() - started)
        if left > 0:
            await asyncio.sleep(left)
        return data

    def _ask(self, d: dict) -> dict | None:
        """The brain's reply (on the brain's thread); None when it failed."""
        try:
            return self._brain_for(d).on_decide(d)
        except Exception:
            self.stats["errors"] += 1
            print("[agent seat] decision failed, the heuristic answers:\n" + traceback.format_exc())
            return None

    def _answer(self, prompt: Prompt, decision: Decision, d: dict, reply: dict | None, retry: bool) -> bytes:
        choice = reply.get("choice") if reply else None
        if reply:
            self._say(reply.get("say"))
        data = None
        if choice is not None:
            try:
                data = decision.encode(choice)
            except ChoiceError as e:
                self.stats["rejected"] += 1
                self._note(f"the engine can't take {choice} ({e}); the heuristic answers instead")
        if data is not None and retry and self._last and self._last[1] == data:
            data = None  # the engine just refused exactly this
        if data is None:
            self.stats["fallbacks"] += 1
            data = self._fallback(prompt, decision, d, avoid=self._last[1] if retry and self._last else None)
        self._last = (d["id"], data)
        return data

    def _fallback(self, prompt: Prompt, decision: Decision, d: dict, avoid: bytes | None = None) -> bytes:
        for pick in (lambda: self.fallback.choose(d), lambda: first_legal(d)):
            try:
                data = decision.encode(pick())
            except Exception:
                continue
            if data != avoid:
                return data
        data = b""
        for _ in range(20):  # the arena's stress-tested random policy: always engine-legal
            data = self.random(prompt, self.view)
            if data != avoid:
                break
        return data

    def _note(self, text: str) -> None:
        brain = self.brain
        if brain is not None and brain._log is not None:
            self._run(lambda: brain.log.note(text))

    def close(self, timeout: float = 60) -> None:
        """End of the seat's life: close the last game's brain (log files, backend session) and the worker.
        `timeout`: how long to wait for a decision still in progress (e.g. 2 after Ctrl+C)."""
        if self.closed:
            return
        self.closed = True

        def shut():
            if self.brain is not None:
                self.brain.close()
        try:
            self._call(shut, timeout=timeout)
        except concurrent.futures.TimeoutError:
            pass
        except Exception:
            traceback.print_exc()
        if self._worker is not None:
            self._worker.shutdown(wait=False, cancel_futures=True)


class PacedSeat(Seat):
    """Wraps another in-process seat so each of its answers takes at least `pace` seconds (for spectators)."""

    def __init__(self, inner: Seat, pace: float):
        self.inner, self.pace = inner, pace
        self.name = inner.name

    def bind(self, view):
        super().bind(view)
        self.inner.bind(view)

    def on_message(self, msg):
        self.inner.on_message(msg)

    def record_spectator(self, state):
        publish = getattr(self.inner, "record_spectator", None)
        if publish:
            publish(state)

    def rps(self):
        return self.inner.rps()

    def go_first(self):
        return self.inner.go_first()

    def on_end(self, result, team):
        self.inner.on_end(result, team)

    def choose(self, prompt, retry):
        answer = self.inner.choose(prompt, retry)

        async def wait():
            data = await answer if inspect.isawaitable(answer) else answer
            await asyncio.sleep(self.pace)
            return data
        return wait()


class SeatWatcher(DuelObserver):
    """The decisions a seat faces, built for someone else's eyes (coach mode): attach it to a duel for any team,
    e.g. a human's, and it turns that team's prompts into decision JSON (that player's own view, as a native seat
    would get it) and their responses back into option indices.

        watcher = SeatWatcher(team, engine.cards, on_decision=advise, on_choice=compare)
        room.duel_observers.append(watcher)      # or Duel(..., observers=[watcher])

    `on_event(ev)`, `on_decision(d)` and `on_choice(d, choice)` are optional callbacks; `choice` is None when the
    response has no equivalent in the schema (unselecting a card in a select_unselect)."""

    def __init__(self, team: int, cards=None, on_event=None, on_decision=None, on_choice=None):
        self.team = team
        self.views = frozenset({VIEW_TEAM0 + team})
        self.native = NativeView(team, cards)
        self.on_event, self.on_decision, self.on_choice = on_event, on_decision, on_choice
        self.next_id = 0
        self.pending: tuple[dict, Decision] | None = None

    def on_start(self, duel) -> None:
        self.native.bind(SeatView(duel, self.team))
        self.native.reset()
        self.next_id = 0

    def on_message(self, view: int, msg: Message) -> None:
        for ev in self.native.on_message(msg):
            if self.on_event:
                self.on_event({"t": "event", **ev})

    def on_prompt(self, team: int, prompt: Prompt, retry: bool) -> None:
        if team != self.team:
            return
        decision = build(prompt, self.native)
        self.pending = None
        if decision.kind is None:
            return
        self.next_id += 1
        d = {"t": "decide", "id": self.next_id, "kind": decision.kind, **decision.fields,
             "state": self.native.state()}
        self.pending = (d, decision)
        if self.on_decision:
            self.on_decision(d)

    def on_response(self, team: int, prompt: Prompt, data: bytes) -> None:
        if team != self.team or self.pending is None:
            return
        d, decision = self.pending
        self.pending = None
        if self.on_choice:
            self.on_choice(d, decision.decode(data))


def link(*seats: AgentSeat, match_id: str | None = None) -> str:
    """Seats that play the same duels: their games share one web-panel id per game (`<match_id>-g<n>`), each seat
    with its own panel seat number (its lobby position; two seats both at 0 are numbered in order)."""
    match_id = match_id or f"arena-{time.strftime('%Y%m%d-%H%M%S')}"
    if len({s.position for s in seats}) < len(seats):
        for i, s in enumerate(seats):
            s.position = i
    for s in seats:
        s.match_id = match_id
    return match_id


def add_to_room(room, pos: int, seat: AgentSeat, deck):
    """Seat an AgentSeat at lobby position `pos` of an arena Room: its chat lines go to the room, and the room's chat
    (human `!notes` included) comes to it. Returns the room's LocalPlayer."""
    from .server import RoomObserver

    class ChatRelay(RoomObserver):
        def on_chat(self, p, text):
            if p is player:
                return  # its own line, relayed back
            spectator = p is None or p.pos is None or p.pos >= 2
            own = not spectator and p.team is not None and p.team == player.team
            seat.room_chat(text, "spectator" if spectator else "duelist", p.name if p else "", own=own)
    player = room.add_local(pos, seat, deck)
    seat.position = pos
    seat.chat = lambda text: room.chat_as(player, text)
    seat.set_room(room.config.duel)
    room.room_observers.append(ChatRelay())
    return player
