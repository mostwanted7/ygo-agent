"""The training workspace (decks/<name>/train/): checkpointed steps, the cost ledger, the budget and the log.

Every step of the pipeline has an id ("study", "r1.lab.hand-03", "r1.game-2", ...). A finished step stores its result
in state.json, so a resumed run skips it and reuses the result. Costs go to the ledger as they are paid; the budget
check before each paid step compares what is spent plus an estimate for that kind of step with the limit.
"""

from __future__ import annotations

import json
import os
import threading
import time

from ..agent.gamelog import BOLD, DIM, RED, YELLOW, emit, paint

STATE_VERSION = 1
# USD per step before the ledger has real numbers for that kind (claude-code reports API-price equivalents).
DEFAULT_ESTIMATES = {"study": 3.0, "review": 1.5, "lab-review": 2.0, "condense": 1.0, "lab-hand": 0.5, "game": 3.0,
                     "test": 0.1, "interview": 0.3, "learn": 1.5}


class BudgetExhausted(Exception):
    """The next step would go over --budget-usd: the run stops cleanly and still writes its report."""


class TrainerError(Exception):
    """A problem the user can fix (a bad deck, a backend that can't review, a broken workspace)."""


def has_run(deck_dir: str) -> bool:
    """Does the deck folder hold a training run (train/state.json with the run's options)? `ygo-agent learn` keeps its
    own state in the same file, under "learn", which isn't a run to resume or compare."""
    try:
        with open(os.path.join(deck_dir, "train", "state.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("options"))
    except (OSError, ValueError, AttributeError):
        return False


class Workspace:
    LOG = "trainer.log"
    TAG = "[train] "

    def __init__(self, deck_dir: str, budget: float | None = None, quiet: bool = False):
        self.deck_dir = os.path.abspath(deck_dir)
        self.dir = os.path.join(self.deck_dir, "train")
        os.makedirs(self.dir, exist_ok=True)
        self.state_path = os.path.join(self.dir, "state.json")
        self.budget = budget
        self.quiet = quiet
        self._lock = threading.RLock()
        self.state = self._load()

    # ---- state ----

    def _load(self) -> dict:
        if os.path.isfile(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)
            if state.get("version") != STATE_VERSION:
                raise TrainerError(f"{self.state_path} is from another trainer version; start over without --resume")
            state.setdefault("steps", {})  # a file `learn` wrote has only its own key
            state.setdefault("ledger", [])
            return state
        return {"version": STATE_VERSION, "created": now(), "steps": {}, "ledger": [], "status": "new"}

    @property
    def exists(self) -> bool:
        return bool(self.state.get("steps"))

    def save(self) -> None:
        with self._lock:
            self.state["updated"] = now()
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=1)
                f.write("\n")
            os.replace(tmp, self.state_path)

    def done(self, step: str) -> bool:
        return step in self.state["steps"]

    def result(self, step: str, default=None):
        return self.state["steps"].get(step, {}).get("result", default)

    def finish(self, step: str, result=None, seconds: float | None = None) -> None:
        with self._lock:
            self.state["steps"][step] = {"result": result, "at": now(),
                                         **({"seconds": round(seconds, 1)} if seconds is not None else {})}
            self.save()

    def forget(self, prefix: str) -> None:
        """Drop the steps whose id starts with `prefix` (re-run them)."""
        with self._lock:
            for key in [k for k in self.state["steps"] if k.startswith(prefix)]:
                del self.state["steps"][key]
            self.save()

    def set(self, key: str, value) -> None:
        with self._lock:
            self.state[key] = value
            self.save()

    # ---- paths ----

    def path(self, *parts: str) -> str:
        """A path inside the workspace; its folder is created."""
        p = os.path.join(self.dir, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def folder(self, *parts: str) -> str:
        p = os.path.join(self.dir, *parts)
        os.makedirs(p, exist_ok=True)
        return p

    def rel(self, path: str) -> str:
        return os.path.relpath(os.path.abspath(path), self.dir)

    def write(self, rel_path: str, text: str) -> str:
        p = self.path(rel_path)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def write_json(self, rel_path: str, data) -> str:
        return self.write(rel_path, json.dumps(data, indent=1, ensure_ascii=False) + "\n")

    def read(self, rel_path: str, default: str | None = None) -> str | None:
        p = os.path.join(self.dir, rel_path)
        if not os.path.isfile(p):
            return default
        with open(p, encoding="utf-8") as f:
            return f.read()

    # ---- money ----

    @property
    def spent(self) -> float:
        return round(sum(e.get("cost") or 0 for e in self.state["ledger"]), 4)

    def spend(self, step: str, kind: str, cost: float | None, seconds: float | None = None, **extra) -> None:
        with self._lock:
            self.state["ledger"].append({"step": step, "kind": kind, "cost": round(cost or 0.0, 4),
                                         "seconds": round(seconds or 0.0, 1), "at": now(), **extra})
            self.save()

    def estimate(self, kind: str) -> float:
        """The cost of one step of `kind` so far: the ledger's average per run (an entry may cover several, e.g. a
        case gate's replays), else the default."""
        entries = [e for e in self.state["ledger"] if e["kind"] == kind]
        if not entries:
            return DEFAULT_ESTIMATES.get(kind, 1.0)
        return sum(e.get("cost") or 0.0 for e in entries) / sum(e.get("runs") or 1 for e in entries)

    def remaining(self) -> float | None:
        return None if self.budget is None else round(self.budget - self.spent, 4)

    def check_budget(self, kind: str, count: int = 1) -> None:
        """Raise BudgetExhausted when `count` more steps of `kind` would go over the budget."""
        if self.budget is None:
            return
        need = self.estimate(kind) * count
        if self.spent + need > self.budget:
            raise BudgetExhausted(f"${self.spent:.2f} spent of ${self.budget:.2f}; the next {kind} step would cost "
                                  f"about ${need:.2f}")

    def affordable(self, kind: str, wanted: int) -> int:
        """How many of `wanted` steps of `kind` fit in what's left of the budget."""
        if self.budget is None:
            return wanted
        each = max(self.estimate(kind), 0.01)
        return max(0, min(wanted, int((self.budget - self.spent) / each)))

    # ---- log ----

    def log(self, text: str, color: str | None = None) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {text}"
        with self._lock:
            with open(os.path.join(self.dir, self.LOG), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        if not self.quiet:
            emit([paint(color or BOLD, self.TAG) + (paint(color, text) if color else text)])

    def warn(self, text: str) -> None:
        self.log(text, YELLOW)

    def error(self, text: str) -> None:
        self.log(text, RED)

    def note(self, text: str) -> None:
        self.log(text, DIM)


class LearnWorkspace(Workspace):
    """The workspace of one `ygo-agent learn` run: its files in train/learn/<run>/, its state under "learn" in
    train/state.json (beside a training run's, which it never touches), and a budget for this run alone.

    `dir` is the run's folder (calls, gates, snapshots, the report); `train_dir` is train/, where the dossier and the
    scripts are, shared with the training run if there was one."""

    LOG = "learn.log"
    TAG = "[learn] "

    def __init__(self, deck_dir: str, run: str, budget: float | None = None, quiet: bool = False):
        self.deck_dir = os.path.abspath(deck_dir)
        self.train_dir = os.path.join(self.deck_dir, "train")
        self.dir = os.path.join(self.train_dir, "learn", run)
        os.makedirs(self.dir, exist_ok=True)
        self.state_path = os.path.join(self.train_dir, "state.json")
        self.run = run
        self.budget = budget
        self.quiet = quiet
        self._lock = threading.RLock()
        if os.path.isfile(self.state_path):
            self.full = Workspace._load(self)
        else:
            self.full = {"version": STATE_VERSION, "created": now()}
        self.state = self.full.setdefault("learn", {})
        for key, empty in (("steps", {}), ("ledger", []), ("runs", [])):
            self.state.setdefault(key, empty)

    def save(self) -> None:
        with self._lock:
            self.state["updated"] = now()
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.full, f, indent=1)
                f.write("\n")
            os.replace(tmp, self.state_path)

    @property
    def spent(self) -> float:
        """This run's spending: --budget-usd is per run."""
        return round(sum(e.get("cost") or 0 for e in self.state["ledger"] if e.get("run") == self.run), 4)

    def spend(self, step: str, kind: str, cost: float | None, seconds: float | None = None, **extra) -> None:
        super().spend(step, kind, cost, seconds, run=self.run, **extra)

    def run_ledger(self) -> list[dict]:
        return [e for e in self.state["ledger"] if e.get("run") == self.run]


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
