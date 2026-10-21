"""Delta debugging over the world delta: find a 1-minimal set of package differences that still reproduces a failure.

`test(subset)` answers FAIL (the witness signature reproduces exactly), PASS (it does not fail) or UNRESOLVED (the world
could not be built or tested, or it failed differently). Only FAIL counts as "still failing", so an unresolved subset can never
be mistaken for a cause. The search records every attempt, reports its budget, and flags non-monotonic behaviour.
"""
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class Outcome(StrEnum):
    FAIL = "FAIL"
    PASS = "PASS"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class Budget:
    max_tests: int = 60
    max_seconds: float = 1800.0
    started: float = field(default_factory=time.monotonic)
    used: int = 0

    def spend(self) -> None:
        if self.used >= self.max_tests or time.monotonic() - self.started > self.max_seconds:
            raise BudgetExceeded()
        self.used += 1


class BudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class Attempt:
    subset: tuple[str, ...]
    outcome: Outcome


@dataclass
class DdminResult:
    minimal: tuple[str, ...] | None            # None when the search could not establish any failing subset
    status: str                                # COMPLETE | BUDGET_LIMITED | NO_CAUSE
    attempts: list[Attempt]
    non_monotonic: bool = False
    alternatives: list[tuple[str, ...]] = field(default_factory=list)      # other single causes found by the singleton pre-check
    unresolved: int = 0
    tests: int = 0


ALGORITHM_VERSION = "ddmin/2"      # /1 was the in-memory search; /2 reports its state before every test so that a stored search can resume (same results)


def ddmin(items: Sequence[str], test: Callable[[frozenset[str]], Outcome], budget: Budget | None = None,
          on_state: Callable[[dict], None] | None = None) -> DdminResult:
    """`on_state`, when given, is called with {phase, c, n, i, part} just before every test that is about to run: the search state a checkpoint stores.

    Phases: SINGLETONS (i = the item being tested alone), FULL (the whole delta), REDUCE (c = the current candidate set, n = granularity,
    i = the chunk, part = "subset" or "complement").
    """
    budget = budget or Budget()
    items = sorted(set(items))
    seen: dict[frozenset[str], Outcome] = {}
    attempts: list[Attempt] = []
    state: dict = {"phase": "SINGLETONS", "c": list(items), "n": 2, "i": 0, "part": None}

    def at(**kw) -> None:
        state.update(kw)

    def t(subset: Sequence[str]) -> Outcome:
        key = frozenset(subset)
        if key not in seen:
            if on_state is not None:
                on_state({**state, "c": list(state["c"])})
            budget.spend()
            seen[key] = test(key)
            attempts.append(Attempt(tuple(sorted(key)), seen[key]))
        return seen[key]

    def result(minimal, status):
        # non-monotonic: a set containing the minimal set was tested and did NOT fail, so "more changes" is not always "still failing"
        non_mono = bool(minimal) and any(set(minimal) < set(a.subset) and a.outcome == Outcome.PASS for a in attempts)
        return DdminResult(tuple(minimal) if minimal else None, status, attempts, non_mono, [],
                           sum(a.outcome == Outcome.UNRESOLVED for a in attempts), budget.used)

    if not items:
        return DdminResult(None, "NO_CAUSE", [], tests=0)
    try:
        singles = []
        for idx, x in enumerate(items):                                              # singleton pre-check
            at(phase="SINGLETONS", i=idx, part=None)
            if t([x]) == Outcome.FAIL:
                singles.append(x)
        if singles:
            if len(items) > 1:
                at(phase="FULL", i=0, part=None)
                t(items)                                                             # the full delta must also fail (monotonicity check)
            r = result([singles[0]], "COMPLETE")
            r.alternatives = [(x,) for x in singles[1:]]
            return r
        at(phase="FULL", i=0, part=None)
        if len(items) == 1 or t(items) != Outcome.FAIL:                              # the whole delta must still reproduce it
            return DdminResult(None, "NO_CAUSE", attempts, unresolved=sum(a.outcome == Outcome.UNRESOLVED for a in attempts), tests=budget.used)
        c, n = list(items), 2
        while len(c) >= 2:
            size = max(1, -(-len(c) // n))                                          # ceil: at most n chunks
            chunks = [c[i:i + size] for i in range(0, len(c), size)]
            reduced = False
            for i, ch in enumerate(chunks):
                at(phase="REDUCE", c=list(c), n=n, i=i, part="subset")
                if t(ch) == Outcome.FAIL:
                    c, n, reduced = ch, 2, True
                    break
            if not reduced:
                for i, ch in enumerate(chunks):
                    comp = [x for x in c if x not in ch]
                    at(phase="REDUCE", c=list(c), n=n, i=i, part="complement")
                    if comp and t(comp) == Outcome.FAIL:
                        c, n, reduced = comp, max(n - 1, 2), True
                        break
            if not reduced:
                if len(chunks) >= len(c):                                           # granularity is already one package per chunk
                    break
                n = min(len(c), n * 2)
        return result(c, "COMPLETE")
    except BudgetExceeded:
        fails = [a.subset for a in attempts if a.outcome == Outcome.FAIL]
        best = min(fails, key=lambda s: (len(s), s)) if fails else None
        r = result(best, "BUDGET_LIMITED") if best else DdminResult(None, "BUDGET_LIMITED", attempts, tests=budget.used)
        return r
