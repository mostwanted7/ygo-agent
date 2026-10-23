"""Live coaching in an arena room: the human plays their seat in EDOPro, the coach watches it and advises.

    coach = Coach(cfg, db, backend=profile_dict, profile=None, level="beginner", cards=engine.cards)
    run_games(SeatSpec("human"), opponent, on_room=coach.attach, on_game=coach.on_game, ...)
    coach.close()

For every game the human's seat gets a SeatWatcher (their own view, the same decision JSON an AI seat would get)
and a CoachGame. Nothing here ever blocks the duel: the arena's callbacks only queue work. A "brain" thread keeps
the log, the history and the panel up to date as the game goes, and asks the backend on an "ask" thread, one
request at a time, always for the decision the human is looking at now. A decision the human answered before the
coach got to it is dropped (no cost), except idle/battle/chain decisions, which get a short "looking back" ask for
the review once the coach has caught up. Advice that arrives after the human's move is marked late.
"""

import asyncio
import concurrent.futures
import math
import os
import shutil
import threading
import time
import traceback
from dataclasses import dataclass, field

from ..agent.brain import card_key
from ..agent.gamelog import BOLD, CYAN, DIM, GREEN, MAGENTA, RED, YELLOW, paint, same_pick
from ..agent.prompts import SCHEMA
from ..arena.native_seat import SeatWatcher
from ..arena.server import RoomObserver
from ..backends import Request, new_info
from ..core.constants import WIN_REASON_INTERNAL_ERROR
from .brain import CoachBrain

HINDSIGHT_KINDS = ("idle", "battle", "chain")  # worth a "what would I have done" for the review
HINDSIGHT_BACKLOG = 4    # past decisions waiting for a look back; older ones are dropped so the coach keeps up
HINDSIGHT_AFTER_GAME = 6  # looks back still asked once the game is over


@dataclass
class Rec:
    """One decision of the human's, as the coach handles it."""
    d: dict
    question: str
    options: list
    shown: float                   # monotonic time the human got it
    status: str = "new"            # auto, queued, asking, advised, skipped, failed
    advice: dict | None = None
    human: list | None = None
    human_seconds: float | None = None
    answered: bool = False         # the human's move is logged (game.md block written)
    hindsight: bool = False
    attempts: int = 0
    seconds: float = 0.0           # backend time
    header: bool = False           # its "? #N question" line is on the terminal

    @property
    def id(self):
        return self.d["id"]

    @property
    def kind(self):
        return self.d["kind"]

    @property
    def turn(self):
        return (self.d.get("state") or {}).get("turn") or 0


@dataclass
class CoachStats:
    decisions: int = 0
    advised: int = 0       # the backend recommended something (live or late)
    auto: int = 0          # trivial, rules or a planned pick: no backend call
    hindsight: int = 0     # looked back at after the human's move
    skipped: int = 0       # answered before the coach got to it, and not worth a look back
    failed: int = 0
    late: int = 0
    followed: int = 0
    diverged: int = 0
    after: list = field(default_factory=list)   # seconds from the decision to its advice (looks back aside)
    human: list = field(default_factory=list)   # seconds the human took

    def summary(self):
        def mean(v):
            return round(sum(v) / len(v), 2) if v else None

        def p95(v):
            return round(sorted(v)[min(len(v) - 1, math.ceil(0.95 * len(v)) - 1)], 2) if v else None
        judged = self.followed + self.diverged
        return {"decisions": self.decisions, "advised": self.advised, "auto": self.auto, "hindsight": self.hindsight,
                "skipped": self.skipped, "failed": self.failed, "late": self.late, "followed": self.followed,
                "diverged": self.diverged, "follow_rate": round(self.followed / judged, 3) if judged else None,
                "advice_after_mean_s": mean(self.after), "advice_after_p95_s": p95(self.after),
                "human_mean_s": mean(self.human), "human_p95_s": p95(self.human)}


class Coach(RoomObserver):
    """Coach mode for one arena room. `backend`: the coach's backend profile; `profile`: the deck Profile to coach
    (None: detect it from the deck the human submits); `opponent`: who they play (prompts.opponent_text);
    `review(game)`: called on a thread of its own when a game's log is complete (the post-game review)."""

    def __init__(self, cfg, db, *, backend, profile=None, level="beginner", opponent=None, cards=None, human_pos=0,
                 echo="all", review=None, say=print):
        self.cfg, self.db = cfg, db
        self.backend = backend
        self.profile = profile
        self.level = level
        self.opponent = opponent
        self.cards = cards
        self.human_pos = human_pos
        self.echo = echo
        self.review = review
        self.say = say
        self.detection = None   # coach/detect.py's Detection, once the human's deck is known
        self._deck = None       # the list it was detected from (a new list is detected again)
        self.room = None
        self.loop = None
        self.game = None        # the CoachGame of the game being played (or just finished)
        self.games = []
        self.reviews = []       # threads writing reviews
        self.lock = threading.Lock()

    # ---- the room ----

    def attach(self, room):
        """run_games(on_room=...): watch this room. An AI opponent's reasoning stays off the panel and the terminal
        (it knows its own hand); its game log is still written."""
        self.room = room
        room.room_observers.append(self)
        for p in room.slots:
            seat = getattr(p, "seat", None)
            if p is not None and p.is_local and isinstance(getattr(seat, "log_options", None), dict):
                seat.log_options.update(publish=False, echo="off", latest=False)
                seat.room_chat = notes_for_the_coach(seat.room_chat)

    def on_game_start(self, room, duel):
        human = room.slots[self.human_pos]
        if human is None or human.is_local or human.team is None:
            return
        self.loop = asyncio.get_running_loop()
        profile = self.profile_for(human)
        game = CoachGame(self, len(self.games) + 1, profile, human)
        with self.lock:
            self.game = game
            self.games.append(game)
        from ..arena.spectator import SpectatorFeed
        duel.observers.append(SpectatorFeed(human.team, game.on_spectator))
        duel.observers.append(SeatWatcher(human.team, self.cards, on_event=game.on_event,
                                          on_decision=game.on_decision, on_choice=game.on_choice))

    def on_game_end(self, room, duel, result):
        if self.game is not None:
            self.game.ended = True
            # A duel the room cut short (Ctrl+C, a crash) isn't worth a review; a surrender or a lost connection is.
            self.game.review = not (result.is_draw and result.reason == WIN_REASON_INTERNAL_ERROR)
            self.game.submit(self.game.finish_when_drained)

    def on_chat(self, p, text):
        game = self.game
        if game is None:
            return
        human = self.room.slots[self.human_pos] if self.room else None
        spectator = p is None or p.pos is None or p.pos >= 2
        source = "spectator" if spectator else "duelist"
        player = 0 if p is human else (7 if spectator else 1)
        game.submit(game.chat, {"t": "event", "e": "chat", "player": player, "position": 0, "message": text,
                                "source": source, "name": getattr(p, "name", "")})

    def on_game(self, result):
        """run_games(on_game=...): the coach's log folder gets the game's replay, and the run's results its folder."""
        game = self.game
        if game is None:
            return
        seat = result.seats[self.human_pos]
        game.submit(game.attach_result, result, seat)

    def say_in_room(self, text):
        """A system chat line in the room (the !note acknowledgements)."""
        if self.room is not None and self.loop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.room.say, text)

    # ---- the deck ----

    def profile_for(self, human):
        if self.profile is not None:
            return self.profile
        from ..agent.profile import Profile
        from .detect import detect, write_ydk
        deck = human.deck
        key = (tuple(deck.main), tuple(deck.extra))
        if self._deck == key and self.detection is not None:
            return self.detection.profile
        found = detect(deck.main, deck.extra, self.cfg, self.db)
        if found.key:
            found.profile = Profile(found.key, self.db, self.cfg)
            self.say(paint(BOLD + ";" + GREEN, f"Coach: {found.describe()}; coaching with its playbook."))
        else:
            folder = os.path.join(self.games_dir(), "coach-decks")
            os.makedirs(folder, exist_ok=True)
            from ..agent.gamelog import slug
            path = write_ydk(os.path.join(folder, f"{slug(found.name)}.ydk"), deck.main, deck.extra, deck.side)
            found.profile = Profile(slug(found.name), self.db, self.cfg, ydk=path, playbook="")
            found.profile.name = found.name if found.source else "Your deck"
            self.say(paint(BOLD + ";" + YELLOW, f"Coach: {found.describe()}, so the advice comes from the general "
                                                "playbook and the card texts only. Training the deck first "
                                                "(`ygo-agent train path/to/deck.ydk --name NAME`, then `coach --deck "
                                                "NAME`) gives much better advice."))
        self._deck, self.detection = key, found
        return found.profile

    def games_dir(self):
        from .. import paths
        return paths.resolve(self.cfg.get("games_dir", "games"))

    # ---- the end ----

    def start_review(self, game):
        if self.review is None:
            return
        t = threading.Thread(target=self._review, args=(game,), daemon=True, name=f"coach-review-{game.number}")
        t.start()
        with self.lock:
            self.reviews.append(t)

    def _review(self, game):
        try:
            self.review(game)
        except Exception:
            self.say(paint(RED, "The review failed:\n" + traceback.format_exc()))

    def close(self, timeout=None):
        """End of the run: the current game's coach stops (a game cut short gets no review), and reviews being
        written are waited for (`timeout` seconds each, None = as long as they take)."""
        with self.lock:
            games = list(self.games)
        for game in games:
            game.close(wait=True)
        with self.lock:
            reviews = list(self.reviews)
        for t in reviews:
            t.join(timeout)


class CoachGame:
    """The coach for one game of the human's seat."""

    def __init__(self, coach, number, profile, human):
        self.coach = coach
        self.number = number
        room = coach.room
        cfg = room.config.duel if room else None
        room_event = None
        if cfg is not None:
            room_event = {"t": "event", "e": "room", "duel_flags": cfg.flags & ~0x10, "forbidden_types":
                          cfg.forbidden_types, "best_of": cfg.best_of, "teams": [1, 1], "start_lp": cfg.lp,
                          "start_hand": cfg.start_hand, "draw_count": cfg.draw_count,
                          "time_limit": room.config.time_limit}
        self.brain = CoachBrain(coach.cfg, coach.db, profile, level=coach.level, backend=coach.backend,
                                room=room_event, opponent=coach.opponent, seat=0,
                                log_options={"echo": coach.echo, "latest": True})
        self.label = self.brain.label
        self.worker = concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix=f"coach-{number}")
        self.asker = concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix=f"coach-ask-{number}")
        self.lock = threading.Lock()
        self.answers = {}      # decision id -> (choice, monotonic time): written on the arena's thread
        self.shown = {}        # decision id -> monotonic time it appeared
        self.recs = {}         # the rest is the brain thread's own
        self.queue = []
        self.asking = None
        self.over = False
        self.finished = False  # log closed and review started
        self.draining = False
        self.ended = False     # the duel is over (set on the arena's thread)
        self.done = threading.Event()
        self.review = True     # write the review when it's over
        self.closed = False
        self.waiting_for_drain = False
        self.after_game = HINDSIGHT_AFTER_GAME
        self.stats = CoachStats()
        self.result = None

    # ---- called on the arena's thread: queue only ----

    def submit(self, fn, *args):
        if self.closed:
            return None
        try:
            return self.worker.submit(self._safe, fn, *args)
        except RuntimeError:  # shut down
            return None

    @staticmethod
    def _safe(fn, *args):
        try:
            return fn(*args)
        except Exception:
            print("[coach] " + traceback.format_exc())

    def on_event(self, ev):
        self.submit(self.event, ev)

    def on_spectator(self, state):
        self.submit(lambda: self.log.record("spectator_state", {"state": state}))

    def on_decision(self, d):
        self.shown[d["id"]] = time.monotonic()
        self.submit(self.decision, d)

    def on_choice(self, d, choice):
        with self.lock:
            self.answers[d["id"]] = (choice, time.monotonic())
        self.submit(self.choice, d["id"])

    def answered(self, did):
        with self.lock:
            return did in self.answers

    # ---- the brain thread ----

    @property
    def log(self):
        return self.brain.log

    def show(self, *lines):
        if self.log.echo in ("all", "decisions"):
            self.log.say(*lines)

    def event(self, ev):
        self.brain.on_event(ev)
        self.flush_say()
        if ev["e"] == "new_turn" and self.asking is None:
            self.prewarm(ev["turn"])
        elif ev["e"] == "win":
            self.over = True
            self.pump()

    def chat(self, ev):
        self.brain.on_event(ev)
        self.flush_say()

    def flush_say(self):
        if self.brain.say_queue:
            text = "\n".join(self.brain.say_queue)
            self.brain.say_queue.clear()
            self.coach.say_in_room(text)

    def prewarm(self, turn):
        if not self.over and self.brain.backend_cfg.get("type") not in ("heuristic", "random"):
            try:
                self.brain.ensure_session(turn)  # the CLI starts while the human reads the board
            except Exception:
                print("[coach] could not open a session:\n" + traceback.format_exc())

    def decision(self, d):
        question, options = self.brain.begin(d)
        rec = Rec(d, question, options, self.shown.get(d["id"], time.monotonic()))
        self.recs[rec.id] = rec
        self.stats.decisions += 1
        auto = self.brain.auto_advice(d)
        if auto is not None:
            rec.status = "auto"
            self.stats.auto += 1
            choice, why, source = auto
            self.advise(rec, choice, why, None, source)
        else:
            rec.status = "queued"
            self.queue.append(rec)
        self.pump()

    def choice(self, did):
        rec = self.recs.get(did)
        if rec is None:
            return
        with self.lock:
            choice, at = self.answers[did]
        rec.human = choice if choice is not None else []
        rec.human_seconds = round(at - rec.shown, 2)
        self.stats.human.append(rec.human_seconds)
        self.human_move(rec)
        self.pump()

    # ---- asking ----

    def pump(self):
        """Start the next ask if none is running: the decision the human is looking at, else a look back."""
        if self.asking is not None or self.closed:
            return
        rec = self.pick()
        if rec is None:
            if self.over:
                self.drained()
            else:
                self.prewarm(self.brain.turn)
            return
        self.ask(rec)

    def pick(self):
        """The decision the human is looking at, if it waits for advice; else the oldest answered idle/battle/chain
        decision for a look back (a few at most). Answered decisions of other kinds are dropped: no cost."""
        waiting = [r for r in self.queue if r.status == "queued"]
        live = [r for r in waiting if not self.answered(r.id)]
        past = [r for r in waiting if r not in live]
        for r in past if not self.over else past + live:
            if r.kind not in HINDSIGHT_KINDS or r in live:
                self.skip(r)
        past = [r for r in past if r.status == "queued"]
        budget = max(0, self.after_game if self.over else HINDSIGHT_BACKLOG)
        for r in past[:len(past) - budget]:
            self.skip(r)
        past = past[len(past) - budget:] if budget else []
        live = [r for r in live if r.status == "queued"]
        self.queue = live + past
        if live:
            return live[-1]
        if past:
            if self.over:
                self.after_game -= 1
            return past[0]  # oldest first, so the session's conversation stays in order
        return None

    def ask(self, rec):
        brain = self.brain
        rec.hindsight = self.answered(rec.id)
        # A look back uses the session at hand, even from an earlier turn: no new session for an old decision.
        turn = brain.session_turn if rec.hindsight and brain.session and brain.session.alive else rec.turn
        try:
            session = brain.ensure_session(turn)
        except Exception as e:
            rec.status = "failed"
            self.stats.failed += 1
            self.log.note(f"the coach could not start its backend: {e}")
            return self.pump()
        first = session.messages == 0
        if rec.hindsight:
            with self.lock:
                human = self.answers[rec.id][0]
            text = brain.hindsight_message(rec.d, rec.question, rec.options, human, first)
        else:
            text = brain.build_message(rec.d, rec.question, rec.options, first)
        rec.status = "asking"
        self.asking = rec
        self.send(rec, session, text, None)

    def send(self, rec, session, text, error):
        timeout = float(self.coach.cfg["agent"].get("decision_timeout_seconds", 120))
        future = self.asker.submit(session.ask, Request(text, rec.d, SCHEMA, timeout, error))
        future.add_done_callback(lambda f: self.submit(self.asked, rec, session, text, f))

    def asked(self, rec, session, text, future):
        brain = self.brain
        try:
            out, info = future.result()
        except Exception as e:
            out, info = None, {**new_info(), "error": repr(e)}
        choice, error = brain.check(rec.d, out) if out is not None else (None, None)
        if error:
            info["invalid"] = info.get("invalid", 0) + 1
            info["error"] = f"invalid reply {out.get('choice')}: {error}"
        brain.stats.ask(info)
        brain.log.prompt(rec.id, text, out, info)
        rec.seconds += info.get("seconds") or 0
        if out is None and not session.alive:
            brain.session = None
        if error and rec.attempts < 1 and (rec.hindsight or not self.answered(rec.id)):
            rec.attempts += 1  # one corrective re-ask, unless the human has moved on anyway
            return self.send(rec, session, f"That reply is invalid: {error}. Answer DECISION #{rec.id} again with a "
                                           "valid choice.", error)
        self.asking = None
        brain.stats.latencies.append(round(rec.seconds, 2))
        if out is None or error:
            rec.status = "failed"
            self.stats.failed += 1
            self.advise(rec, None, f"no usable advice: {info.get('error') or 'no reply'}", None, "failed")
        else:
            if out.get("plan"):
                brain.turn_plan = out["plan"]
            rec.status = "advised"
            self.stats.advised += 1
            self.stats.hindsight += rec.hindsight
            self.advise(rec, choice, out.get("why") or "", out.get("plan"), "backend", round(rec.seconds, 2))
        self.pump()

    def skip(self, rec):
        rec.status = "skipped"
        self.stats.skipped += 1
        self.advise(rec, None, "the human answered before the coach got to it", None, "skipped")

    # ---- advice and moves: log, panel, terminal ----

    def advise(self, rec, choice, why, plan, source, seconds=None):
        brain = self.brain
        late = self.answered(rec.id)
        after = round(time.monotonic() - rec.shown, 2)
        rec.advice = {"choice": choice, "why": why, "plan": plan, "source": source, "late": late,
                      "hindsight": rec.hindsight, "seconds": seconds, "after": after}
        if source == "backend" and not rec.hindsight:
            self.stats.after.append(after)  # how long after the decision the advice came, late or not
            self.stats.late += late
        label = self.label if source == "backend" else source
        brain.log.advice(rec.id, choice, why=why, plan=plan, source=source, label=label, seconds=seconds, after=after,
                         late=late, hindsight=rec.hindsight, kind=rec.kind)
        if choice is not None and not late and rec.kind == "select_unselect" and len(choice) > 1:
            brain.plan = [card_key(rec.d["options"][k]) for k in choice[1:] if 0 <= k < len(rec.d["options"])]
            brain.plan_hint = rec.d.get("hint")
        if rec.answered and choice is not None:
            self.judge(rec)
            brain.log.append_md(self.coach_md(rec, late=True))
        if choice is not None:
            self.show_advice(rec)

    def human_move(self, rec):
        brain, advice = self.brain, rec.advice
        verdict = None
        if advice and advice.get("choice") is not None:
            verdict = self.judge(rec)
        if advice is None or rec.status in ("queued", "asking"):
            why = "answered before the coach's advice"
        elif advice.get("choice") is None:
            why = f"(no advice: {advice.get('why')})" if rec.status == "auto" else "answered before the coach got to it"
        elif verdict:
            why = "followed the coach"
        else:
            why = f"the coach advised {brain.picked(rec.options, advice['choice'])}"
        brain.log.decision(rec.id, rec.question, rec.options, rec.human, why, None, "human", rec.human_seconds,
                           label="human", echo=False, turn=rec.turn)
        if advice and advice.get("choice") is not None:
            brain.log.append_md(self.coach_md(rec))
        brain.log.record("reply", {"id": rec.id, "choice": rec.human, "source": "human", "seconds": rec.human_seconds,
                                   "advised": advice.get("choice") if advice else None, "matched": verdict,
                                   "trivial": rec.status == "auto" and (not advice or advice["choice"] is None)})
        brain.stats.decision("human")
        rec.answered = True
        if rec.kind == "select_unselect" and brain.plan and not verdict:
            brain.plan = []  # they picked something else: the rest of the advised selection no longer applies
        if not (rec.status == "auto" and (not advice or advice["choice"] is None)):
            brain.human_moved(rec.d, rec.question, rec.options, rec.human,
                              advice.get("choice") if advice else None, advice.get("source") if advice else None)
        self.show_move(rec, verdict)

    def judge(self, rec):
        """Did the human follow the advice? Counted once per decision."""
        advice = rec.advice
        verdict = same_pick(rec.human, advice["choice"], rec.kind)
        if not advice.get("judged") and advice["source"] == "backend":
            advice["judged"] = True
            if verdict:
                self.stats.followed += 1
            else:
                self.stats.diverged += 1
        return verdict

    def coach_md(self, rec, late=False):
        a = rec.advice
        when = "looking back" if a["hindsight"] else ("late, " if a["late"] else "") + f"{a['after']}s after the decision"
        who = self.label if a["source"] == "backend" else a["source"]
        head = f"> 🎓 **Coach** ({who}, {when})" + (f" on decision #{rec.id}" if late else "")
        lines = [f"{head}: {self.brain.picked(rec.options, a['choice'])}. {a['why'] or ''}".rstrip()]
        if a.get("plan"):
            lines.append(f"> *Coach's plan:* {a['plan']}")
        return "\n".join(lines)

    def header(self, rec):
        if not rec.header:
            rec.header = True
            self.show("", paint(BOLD + ";" + CYAN, f"  ? #{rec.id} {rec.question.split(' Reply')[0]}"))

    def show_advice(self, rec):
        a = rec.advice
        if a["source"] not in ("backend",) and not a["source"].startswith("rule"):
            return  # planned picks and trivial prompts stay quiet
        self.header(rec)
        if a["source"].startswith("rule"):
            tag = paint(YELLOW, f"rule {a['source'][5:]}")
        elif a["hindsight"]:
            tag = paint(MAGENTA, f"looking back ({a['seconds']}s)")
        elif a["late"]:
            tag = paint(MAGENTA, f"late, +{a['after']}s")
        else:
            tag = paint(DIM, f"{a['after']}s")
        picked = self.brain.picked(rec.options, a["choice"])
        lines = [f"    🎓 {paint(BOLD, picked)}  " + tag]
        if a["why"]:
            lines.append(paint(CYAN, f"       {a['why']}"))
        if a.get("plan") and not a["late"]:
            lines.append(paint(YELLOW, "       ✎ plan: " + a["plan"].replace("\n", "\n                ")))
        if rec.answered:
            lines.append(self.verdict_line(rec, same_pick(rec.human, a["choice"], rec.kind)))
        self.show(*lines)

    def show_move(self, rec, verdict):
        a = rec.advice
        if a is None or rec.status in ("queued", "asking"):
            if rec.kind in HINDSIGHT_KINDS or rec.status in ("queued", "asking"):
                self.header(rec)
                self.show(paint(DIM, f"    ▶ you: {self.brain.picked(rec.options, rec.human)} ({rec.human_seconds}s) — "
                                     "before the coach's advice"))
            return
        if a["choice"] is None or a["source"] == "auto":
            return
        self.show(self.verdict_line(rec, verdict))

    def verdict_line(self, rec, verdict):
        if verdict:
            return paint(GREEN, f"    ✓ you followed the coach ({rec.human_seconds}s)")
        return paint(YELLOW, f"    ✗ you chose {self.brain.picked(rec.options, rec.human)} ({rec.human_seconds}s)")

    # ---- the end of the game ----

    def finish_when_drained(self):
        self.over = True
        self.waiting_for_drain = True
        self.pump()

    def drained(self):
        if self.finished or self.draining or not self.waiting_for_drain:
            return
        self.draining = True
        brain = self.brain
        summary = self.stats.summary()
        brain.log.write_meta(coach={"level": self.coach.level, "backend": brain.backend_meta(), **summary,
                                    **({"detected": vars_of(self.coach.detection)} if self.coach.detection else {})})
        self.print_summary(summary)
        brain.close()
        self.asker.shutdown(wait=False)
        if self.review:
            self.coach.start_review(self)
        self.finished = True  # the log is complete and its review under way
        self.done.set()

    def print_summary(self, s):
        if self.log.echo == "off":
            return
        bits = [f"{s['advised']} advised"]
        if s["follow_rate"] is not None:
            bits.append(f"you followed {s['followed']} of {s['followed'] + s['diverged']} ({s['follow_rate']:.0%})")
        if s["advice_after_mean_s"] is not None:
            bits.append(f"advice {s['advice_after_mean_s']}s after the decision on average (p95 "
                        f"{s['advice_after_p95_s']}s)")
        if s["late"]:
            bits.append(f"{s['late']} late")
        if s["human_mean_s"] is not None:
            bits.append(f"you took {s['human_mean_s']}s per decision")
        bits.append(f"{s['auto']} automatic, {s['skipped']} skipped, {s['hindsight']} looked back at")
        cost = self.brain.stats.summary().get("cost_usd")
        if cost is not None:
            bits.append(f"cost ${cost:.4f}")
        self.log.say("", paint(BOLD, "  Coach: " + "; ".join(bits) + "."),
                     paint(BOLD + ";" + YELLOW, f"  Game log: {self.log.dir}/game.md"))

    def attach_result(self, result, seat):
        self.result = result
        log = self.brain._log
        if log is None:
            return
        seat.log_dir = log.dir
        match = {"match": result.match, "game": result.game, "seat": seat.role}
        if result.replay:
            try:
                shutil.copyfile(result.replay, os.path.join(log.dir, "replay.yrpX"))
                match["replay"] = "replay.yrpX"
            except OSError:
                pass
        log.write_meta(match=match)

    def close(self, wait=False):
        """Stop coaching this game. A finished duel first gets its last looks back and its review started (`wait`:
        up to a minute for that); a duel cut short gets no review."""
        if self.closed:
            return
        if wait and self.ended and not self.finished:
            self.done.wait(60)
        self.closed = True
        if not self.finished:  # on the brain thread, after what it's doing (the log's files close under nobody)
            try:
                self.worker.submit(self._safe, self.brain.close).result(10)
            except (RuntimeError, concurrent.futures.TimeoutError):
                pass
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.asker.shutdown(wait=False, cancel_futures=True)


def notes_for_the_coach(room_chat):
    """An AI opponent's chat relay that leaves the human's `!notes` to the coach (they're about the coaching)."""
    def relay(message, source="duelist", name="", own=False):
        if not message.strip().startswith("!"):
            room_chat(message, source, name, own)
    return relay


def vars_of(detection):
    return {"key": detection.key, "name": detection.name, "score": round(detection.score, 3),
            "source": detection.source}
