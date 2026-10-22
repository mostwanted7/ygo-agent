"""The files of an exam and its runs: the JSON and JSONL helpers (every record is appended as it lands, so a run
resumes from its files), repo-relative paths and hashes, and the newest benchmark run (where the whole-game reviews
take their logs from)."""

from __future__ import annotations

import glob
import hashlib
import json
import os
import threading

from ... import paths
from ..runner import file_sha  # noqa: F401  (the prompt-version hashes in run.json)

BENCH_RESULTS = os.path.join(paths.ROOT, "bench", "results")
FILES = ("exam.json", "run.json", "prepared.json", "answers.jsonl", "judge.jsonl", "games.jsonl")
WRITE_LOCK = threading.Lock()


class ExamError(Exception):
    pass


def rel(path: str) -> str:
    real, root = os.path.realpath(path), os.path.realpath(paths.ROOT)
    return os.path.relpath(real, root) if real.startswith(root + os.sep) else real


def sha(obj, n: int = 12) -> str:
    blob = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:n]


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def load_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_jsonl(path: str) -> list[dict]:
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue  # a line cut off by a crash
    except OSError:
        pass
    return out


def append_jsonl(path: str, record: dict) -> None:
    with WRITE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def latest(records: list[dict], keys: tuple) -> dict:
    """The last record for each key (a later line replaces an earlier one, e.g. a retried answer)."""
    out = {}
    for r in records:
        out[tuple(r.get(k) for k in keys)] = r
    return out


def tally(values) -> dict:
    """How many times each value occurs, by value."""
    out = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def default_bench_run() -> str | None:
    """The newest benchmark run with LLM games."""
    for folder in sorted(glob.glob(os.path.join(BENCH_RESULTS, "*")), reverse=True):
        if os.path.isfile(os.path.join(folder, "results.jsonl")):
            return folder
    return None
