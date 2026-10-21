"""Minimisation that survives a worker dying (ADR 0008, decision 4).

Every test has an identity that does not depend on the analysis or the job: test_id = hash(minimisation id, the subset, the direction). When a
test finishes its outcome is stored as an immutable `ddmin_test` object, and then a checkpoint (an immutable object plus a row whose
(minimisation_id, seq) key lets exactly one writer advance the chain) records the search state: the phase, the current candidate set, the
granularity and the chunk. Because the search is deterministic, resuming replays it and answers every stored test from the store; only the first
test without a stored outcome runs. A test that was cut short is recorded as INTERRUPTED, never as a failure, and runs again.
"""
import json
import os
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from ..core.hashing import object_hash
from ..evidence import projections
from ..evidence.events import append_event
from ..evidence.runtime import store_for
from .ddmin import ALGORITHM_VERSION, Budget, DdminResult, Outcome, ddmin

DIRECTION = "search"


class ChainAdvanced(Exception):
    """Another writer advanced this chain first; this one stops instead of overwriting it."""


class ChainDamaged(Exception):
    """Checkpoints exist for this minimisation but none of them can be read."""


class Interrupted(Exception):
    """A test callback raises this when its execution was cut short (the worker was stopped, the job cancelled): the subset was not tested."""


def minimisation_id(pair_key: str, signature: dict, items: list[str]) -> str:
    return "mn_" + object_hash({"pair": pair_key, "signature": signature, "items": sorted(set(items)), "algorithm": ALGORITHM_VERSION})[:40]


def identity_of_test(min_id: str, subset, direction: str = DIRECTION) -> str:
    return "tt_" + object_hash({"min": min_id, "subset": sorted(subset), "direction": direction})[:40]


def _fault_from_environment() -> Callable[["Fault"], None] | None:
    """Tests only: FAULTLINE_FAULT=after_test_stored:3 ends this process at once (exit code 77, no cleanup, as a killed worker) the third time that
    point is reached. It is what lets an integration test lose a worker at an exact point of a real run."""
    spec = os.environ.get("FAULTLINE_FAULT")
    if not spec:
        return None
    point, _, nth = spec.partition(":")
    seen = [0]

    def hook(p: "Fault") -> None:
        if p.value == point:
            seen[0] += 1
            if seen[0] == int(nth or 1):
                os._exit(77)
    return hook


class Fault(Enum):
    """Points at which a test may stop the process, to prove the recovery from each (used by tests only)."""
    AFTER_TEST_STORED = "after_test_stored"          # the outcome is stored and the checkpoint is not yet appended
    AFTER_CHECKPOINT = "after_checkpoint"


@dataclass
class ResumeResult:
    result: DdminResult
    chain_id: str
    tests_run: int
    tests_resumed: int
    checkpoints: int
    resumed_from_seq: int | None
    status: str
    interrupted_tests: list[str] = field(default_factory=list)


class ResumableDdmin:
    def __init__(self, conn: sqlite3.Connection, *, minimisation: str, items: list[str], test: Callable[[frozenset[str]], Outcome | tuple[Outcome, str | None]],
                 budget: Budget | None = None, hook: Callable[[Fault], None] | None = None, analysis_id: str | None = None,
                 on_replay: Callable[[str, frozenset[str], Outcome, dict | None], None] | None = None):
        self.conn, self.min_id, self.items = conn, minimisation, sorted(set(items))
        self.test, self.budget, self.hook, self.analysis_id = test, budget or Budget(), hook or _fault_from_environment(), analysis_id
        self.on_replay = on_replay                       # called with (direction, subset, outcome, detail) for every test answered from the store
        self.store = store_for(conn)
        self.memo: dict[str, dict] = {}                   # test_id -> {test_id, outcome, result_ref}, in the order the tests finished
        self.state: dict = {"phase": "SINGLETONS", "c": list(self.items), "n": 2, "i": 0, "part": None}
        self.run = self.resumed = self.checkpoints = 0
        self.seq = 0
        self.parent: str | None = None

    # ---- loading -----------------------------------------------------------------------------------------------------

    def _load(self) -> int | None:
        rows = self.conn.execute("SELECT seq, object_id FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq DESC", (self.min_id,)).fetchall()
        self.seq = rows[0]["seq"] if rows else 0
        for r in rows:
            got = self.store.get(r["object_id"])
            p = got.payload if got.ok else None
            if p and p["minimisation_id"] == self.min_id and p.get("algorithm") == ALGORITHM_VERSION:
                self.parent = r["object_id"]
                for t in p["tests"]:
                    self.memo[t["test_id"]] = t
                self.budget.used = len(self.memo)
                self.budget.started = time.monotonic() - float(p["budget"]["seconds_used"])
                self.state = p["state"]
                return r["seq"]
        if rows:
            raise ChainDamaged(f"{len(rows)} checkpoint(s) exist for {self.min_id} and none can be read; the stored tests are still in the store, "
                               "but the chain is not resumed silently")
        return None

    def _stored_test(self, tid: str) -> dict | None:
        """A finished test whose checkpoint was never appended (the process stopped between the two)."""
        p = self.conn.execute("SELECT object_id FROM pointer WHERE slot=?", (f"ddmin_test:{tid}",)).fetchone()
        if p is None:
            return None
        got = self.store.get(p["object_id"])
        if not got.ok or got.payload["minimisation_id"] != self.min_id:
            return None
        return {"test_id": tid, "outcome": got.payload["outcome"], "result_ref": got.payload.get("result_ref"), "detail": got.payload.get("detail")}

    # ---- writing -----------------------------------------------------------------------------------------------------

    def _checkpoint(self, status: str = "RUNNING", extra: dict | None = None) -> None:
        self.seq += 1
        payload = {"schema": 1, "minimisation_id": self.min_id, "seq": self.seq, "parent": self.parent, "algorithm": ALGORITHM_VERSION,
                   "items": self.items, "state": self.state, "tests": list(self.memo.values()), "status": status,
                   "budget": {"tests_used": self.budget.used, "seconds_used": round(time.monotonic() - self.budget.started, 3),
                              "max_tests": self.budget.max_tests, "max_seconds": self.budget.max_seconds}, **(extra or {})}
        oid, _ = projections.store_object(self.conn, "ddmin_checkpoint", payload, analysis_id=self.analysis_id)
        try:
            self.conn.execute("INSERT INTO ddmin_checkpoint(minimisation_id, seq, object_id, status, created_at) VALUES (?,?,?,?,?)",
                              (self.min_id, self.seq, oid, status, projections._now()))
        except sqlite3.IntegrityError as e:
            raise ChainAdvanced(f"checkpoint {self.seq} of {self.min_id} was written by another process") from e
        self.parent = oid
        self.checkpoints += 1
        append_event(self.conn, "DDMIN_CHECKPOINT", analysis_id=self.analysis_id, subject=self.min_id, payload={"seq": self.seq, "status": status, "tests": len(self.memo)})

    def _record(self, tid: str, subset: frozenset[str], direction: str, outcome: Outcome, ref: str | None, detail: dict | None) -> None:
        projections.store_object(self.conn, "ddmin_test", {"minimisation_id": self.min_id, "test_id": tid, "subset": sorted(subset), "direction": direction,
                                                           "outcome": outcome.value, "result_ref": ref, "detail": detail}, slot=f"ddmin_test:{tid}",
                                 analysis_id=self.analysis_id)

    # ---- the search --------------------------------------------------------------------------------------------------

    def _execute(self, subset: frozenset[str], direction: str, fn: Callable, *, spend: bool) -> tuple[Outcome, dict | None]:
        tid = identity_of_test(self.min_id, subset, direction)
        done = self.memo.get(tid)
        if done is not None:                                               # answered from the stored checkpoint
            return self._replayed(tid, subset, direction, done, "checkpoint")
        found = self._stored_test(tid)
        if found is not None:                                              # finished and stored, but the checkpoint is missing: add it, do not run again
            self.memo[tid] = found
            self.budget.used += 1 if spend else 0
            out = self._replayed(tid, subset, direction, found, "stored test")
            self._checkpoint()
            return out
        if spend:
            self.budget.spend()                                            # raises BudgetExceeded: the search ends BUDGET_LIMITED
        append_event(self.conn, "DDMIN_ATTEMPT_STARTED", analysis_id=self.analysis_id, subject=tid,
                     payload={"minimisation_id": self.min_id, "subset": sorted(subset), "direction": direction})
        try:
            got = fn(subset)
        except BaseException as e:
            if spend:
                self.budget.used -= 1                                      # the test did not complete: it is not spent and not a failure
            append_event(self.conn, "DDMIN_ATTEMPT_INTERRUPTED", analysis_id=self.analysis_id, subject=tid,
                         payload={"minimisation_id": self.min_id, "reason": type(e).__name__})
            raise
        outcome, detail = got if isinstance(got, tuple) else (got, None)
        self._record(tid, subset, direction, outcome, None, detail)
        append_event(self.conn, "DDMIN_ATTEMPT_FINISHED", analysis_id=self.analysis_id, subject=tid, payload={"minimisation_id": self.min_id, "outcome": outcome.value})
        self.run += 1
        self.memo[tid] = {"test_id": tid, "outcome": outcome.value, "result_ref": None, "detail": detail}
        if self.hook:
            self.hook(Fault.AFTER_TEST_STORED)
        self._checkpoint()
        if self.hook:
            self.hook(Fault.AFTER_CHECKPOINT)
        return outcome, detail

    def _replayed(self, tid: str, subset: frozenset[str], direction: str, entry: dict, source: str) -> tuple[Outcome, dict | None]:
        self.resumed += 1
        append_event(self.conn, "DDMIN_TEST_RESUMED", analysis_id=self.analysis_id, subject=tid, payload={"minimisation_id": self.min_id, "from": source})
        outcome = Outcome(entry["outcome"])
        if self.on_replay:
            self.on_replay(direction, subset, outcome, entry.get("detail"))
        return outcome, entry.get("detail")

    def _wrapped(self, subset: frozenset[str]) -> Outcome:
        return self._execute(subset, DIRECTION, self.test, spend=True)[0]

    def check(self, direction: str, subset: frozenset[str], fn: Callable) -> tuple[Outcome, dict | None]:
        """A test outside the search (the necessity check after it) handled the same way: stored when finished, answered from the store on resume."""
        if self.store is None:
            got = fn(subset)
            return got if isinstance(got, tuple) else (got, None)
        return self._execute(subset, direction, fn, spend=False)

    def _close_dangling(self) -> None:
        """A worker that was killed cannot report that it stopped; a test it started and never finished is recorded as interrupted now."""
        rows = self.conn.execute(
            "SELECT s.subject FROM evidence_event s WHERE s.kind='DDMIN_ATTEMPT_STARTED' AND json_extract(s.payload_json,'$.minimisation_id')=? AND NOT EXISTS ("
            "SELECT 1 FROM evidence_event e WHERE e.subject=s.subject AND e.id>s.id AND e.kind IN ('DDMIN_ATTEMPT_FINISHED','DDMIN_ATTEMPT_INTERRUPTED'))", (self.min_id,)).fetchall()
        for r in rows:
            append_event(self.conn, "DDMIN_ATTEMPT_INTERRUPTED", analysis_id=self.analysis_id, subject=r["subject"],
                         payload={"minimisation_id": self.min_id, "reason": "the worker stopped before the test finished"})

    def run_search(self) -> ResumeResult:
        if self.store is None:                                             # with the store off nothing can be saved: the plain search
            plain = ddmin(self.items, self.test, self.budget)
            return ResumeResult(plain, self.min_id, plain.tests, 0, 0, None, plain.status)
        from_seq = self._load()
        self._close_dangling()
        last_status = self.conn.execute("SELECT status FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq DESC LIMIT 1", (self.min_id,)).fetchone()
        res = ddmin(self.items, self._wrapped, Budget(max_tests=10 ** 9, max_seconds=1e12), on_state=self._on_state)
        if not (last_status and last_status["status"] == res.status and self.run == 0):         # an unchanged finished chain gets no duplicate
            self.state = {"phase": "DONE", "c": list(res.minimal or ()), "n": 0, "i": 0, "part": None}
            self._checkpoint(res.status, {"result": {"minimal": list(res.minimal) if res.minimal else None, "alternatives": [list(a) for a in res.alternatives],
                                                     "non_monotonic": res.non_monotonic, "unresolved": res.unresolved}})
        return ResumeResult(res, self.min_id, self.run, self.resumed, self.checkpoints, from_seq, res.status)

    def _on_state(self, state: dict) -> None:
        self.state = json.loads(json.dumps(state))
