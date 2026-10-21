"""M13.5: the resumable DDMin core. The search itself is unchanged; what is new is that its state and every finished test are stored."""
import random
import threading
from collections.abc import Callable, Sequence

import pytest

from faultline.attribution import checkpoint as cp
from faultline.attribution.checkpoint import (
    ChainAdvanced,
    ChainDamaged,
    Fault,
    Interrupted,
    ResumableDdmin,
    identity_of_test,
    minimisation_id,
)
from faultline.attribution.ddmin import Attempt, Budget, BudgetExceeded, DdminResult, Outcome
from faultline.evidence.counters import counters
from faultline.evidence.runtime import store_for
from faultline.storage.db import connect
from faultline.storage.migrate import migrate

ITEMS = [f"p{i:02d}" for i in range(12)]


# ---- the algorithm as it was before M13.5 (frozen copy), to prove the instrumented search gives the same results ----------------------

def reference_ddmin(items: Sequence[str], test: Callable[[frozenset[str]], Outcome], budget: Budget | None = None) -> DdminResult:
    budget = budget or Budget()
    items = sorted(set(items))
    seen: dict[frozenset[str], Outcome] = {}
    attempts: list[Attempt] = []

    def t(subset: Sequence[str]) -> Outcome:
        key = frozenset(subset)
        if key not in seen:
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
        singles = [x for x in items if t([x]) == Outcome.FAIL]                       # singleton pre-check
        if singles:
            if len(items) > 1:
                t(items)                                                             # the full delta must also fail (monotonicity check)
            r = result([singles[0]], "COMPLETE")
            r.alternatives = [(x,) for x in singles[1:]]
            return r
        if len(items) == 1 or t(items) != Outcome.FAIL:                              # the whole delta must still reproduce it
            return DdminResult(None, "NO_CAUSE", attempts, unresolved=sum(a.outcome == Outcome.UNRESOLVED for a in attempts), tests=budget.used)
        c, n = list(items), 2
        while len(c) >= 2:
            size = max(1, -(-len(c) // n))                                          # ceil: at most n chunks
            chunks = [c[i:i + size] for i in range(0, len(c), size)]
            reduced = False
            for ch in chunks:
                if t(ch) == Outcome.FAIL:
                    c, n, reduced = ch, 2, True
                    break
            if not reduced:
                for ch in chunks:
                    comp = [x for x in c if x not in ch]
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



# ---- helpers -----------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTLINE_EVIDENCE_DIR", str(tmp_path / "objects"))
    c = connect(tmp_path / "r.db")
    migrate(c)
    return c


def predicate(kind: str):
    return {
        "single": lambda s: "p07" in s,
        "pair": lambda s: {"p02", "p09"} <= s,
        "triple": lambda s: {"p01", "p05", "p10"} <= s,
        "independent": lambda s: bool({"p03", "p08"} & s),
        "non_monotonic": lambda s: s == frozenset({"p04"}),
        "none": lambda s: False,
    }[kind]


def oracle(kind: str, calls: list | None = None, unresolved: frozenset = frozenset()):
    fails = predicate(kind)

    def t(s):
        if calls is not None:
            calls.append(frozenset(s))
        if frozenset(s) in unresolved:
            return Outcome.UNRESOLVED
        return Outcome.FAIL if fails(frozenset(s)) else Outcome.PASS
    return t


def mid(kind="x", items=ITEMS) -> str:
    return minimisation_id("pk_demo", {"kind": kind}, items)


def summary(r: DdminResult):
    return (r.minimal, r.status, [(a.subset, a.outcome) for a in r.attempts], r.non_monotonic, r.alternatives, r.unresolved)


KINDS = ["single", "pair", "triple", "independent", "non_monotonic", "none"]


# ---- TC-13.5.1: the same results as before ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_the_resumable_search_gives_the_results_of_the_original(conn, kind):
    ref = reference_ddmin(ITEMS, oracle(kind))
    got = ResumableDdmin(conn, minimisation=mid(kind), items=ITEMS, test=oracle(kind)).run_search()
    assert summary(got.result) == summary(ref)
    assert got.tests_run == len({a.subset for a in ref.attempts}) and got.tests_resumed == 0 and got.resumed_from_seq is None
    assert got.checkpoints == got.tests_run + 1                                      # one per test, and the final one


def test_random_oracles_give_the_original_results(conn):
    rng = random.Random(13)
    for case in range(40):
        causes = frozenset(rng.sample(ITEMS, rng.choice([1, 1, 2, 3])))
        bad = frozenset(rng.sample(ITEMS, rng.choice([0, 1, 2])))                    # subsets the oracle cannot settle
        singles = {frozenset({b}) for b in bad}

        def t(s, causes=causes, singles=singles):
            if frozenset(s) in singles:
                return Outcome.UNRESOLVED
            return Outcome.FAIL if causes <= frozenset(s) else Outcome.PASS
        ref = reference_ddmin(ITEMS, t)
        got = ResumableDdmin(conn, minimisation=mid(f"rnd{case}"), items=ITEMS, test=t).run_search()
        assert summary(got.result) == summary(ref), case


def test_the_state_reported_before_each_test_names_the_phase_and_granularity(conn):
    from faultline.attribution.ddmin import ddmin
    states = []
    ddmin(ITEMS, oracle("triple"), on_state=lambda s: states.append(s))
    assert states[0]["phase"] == "SINGLETONS" and states[0]["i"] == 0
    assert {s["phase"] for s in states} == {"SINGLETONS", "FULL", "REDUCE"}
    reduce = [s for s in states if s["phase"] == "REDUCE"]
    assert reduce and all(s["n"] >= 2 and s["part"] in ("subset", "complement") and set(s["c"]) <= set(ITEMS) for s in reduce)
    ResumableDdmin(conn, minimisation=mid("s"), items=ITEMS, test=oracle("triple")).run_search()
    last = conn.execute("SELECT object_id FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq DESC LIMIT 1", (mid("s"),)).fetchone()[0]
    final = store_for(conn).get(last).payload
    assert final["status"] == "COMPLETE" and final["state"]["phase"] == "DONE" and final["result"]["minimal"] == ["p01", "p05", "p10"]
    middle = store_for(conn).get(conn.execute("SELECT object_id FROM ddmin_checkpoint WHERE minimisation_id=? AND seq=14", (mid("s"),)).fetchone()[0]).payload
    assert middle["state"]["phase"] in ("FULL", "REDUCE") and middle["status"] == "RUNNING" and len(middle["tests"]) == 14


# ---- TC-13.5.2: stop after every possible test, resume ----------------------------------------------------------------------------

class Stop(Exception):
    pass


def stopping_after(k: int, kind: str, calls: list):
    inner = oracle(kind, calls)

    def t(s):
        if len(calls) >= k:
            raise Interrupted("the worker was stopped")
        return inner(s)
    return t


SMALL = ITEMS[:7]


@pytest.mark.parametrize("kind", ["single", "triple", "non_monotonic"])
def test_stopping_after_any_test_and_resuming_gives_the_same_result_and_repeats_nothing(conn, kind):
    ITEMS = SMALL                                                                    # noqa: N806  (a smaller delta keeps this exhaustive test quick)
    whole_calls: list = []
    whole = ResumableDdmin(conn, minimisation=mid("whole" + kind, ITEMS), items=ITEMS, test=oracle(kind, whole_calls)).run_search()
    total = whole.tests_run
    for k in range(total + 1):
        m = mid(f"{kind}-{k}", ITEMS)
        first_calls: list = []
        try:
            ResumableDdmin(conn, minimisation=m, items=ITEMS, test=stopping_after(k, kind, first_calls)).run_search()
            stopped = False
        except Interrupted:
            stopped = True
        assert stopped == (k < total)
        second_calls: list = []
        r = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle(kind, second_calls)).run_search()
        assert summary(r.result) == summary(whole.result), (kind, k)
        assert not (set(first_calls) & set(second_calls)), "a test whose outcome was stored must not run again"
        assert len(first_calls) + len(second_calls) == total and set(first_calls) | set(second_calls) == set(whole_calls)
        assert r.tests_resumed >= len(first_calls) and r.tests_run == len(second_calls)
        seqs = [x["seq"] for x in conn.execute("SELECT seq FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq", (m,))]
        assert seqs == list(range(1, len(seqs) + 1)), "the chain has no gaps"


# ---- TC-13.5.3: the process stops between the stored outcome and the checkpoint --------------------------------------------------------

def test_a_stop_between_the_stored_outcome_and_the_checkpoint_does_not_run_that_test_again(conn):
    m = mid("fault")
    seen: list = []

    def hook(point):
        if point is Fault.AFTER_TEST_STORED and len(seen) == 3:
            raise Stop()
    with pytest.raises(Stop):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple", seen), hook=hook).run_search()
    assert len(seen) == 3
    stored = [r["slot"] for r in conn.execute("SELECT slot FROM object_index WHERE slot LIKE 'ddmin_test:%'")]
    assert len(stored) == 3
    latest = store_for(conn).get(conn.execute("SELECT object_id FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq DESC LIMIT 1", (m,)).fetchone()[0]).payload
    assert len(latest["tests"]) == 2, "the third outcome is stored but not yet in a checkpoint"
    again: list = []
    r = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple", again)).run_search()
    assert seen[2] not in again and not (set(seen) & set(again))
    assert summary(r.result) == summary(reference_ddmin(ITEMS, oracle("triple")))
    seqs = [x["seq"] for x in conn.execute("SELECT seq FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq", (m,))]
    assert seqs == list(range(1, len(seqs) + 1))


# ---- TC-13.5.4: an interrupted test is not a failure --------------------------------------------------------------------------------------

def test_an_interrupted_test_is_recorded_as_interrupted_and_runs_again(conn):
    m = mid("int")
    calls: list = []
    with pytest.raises(Interrupted):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=stopping_after(2, "single", calls)).run_search()
    ev = conn.execute("SELECT subject, payload_json FROM evidence_event WHERE kind='DDMIN_ATTEMPT_INTERRUPTED'").fetchall()
    assert len(ev) == 1 and "Interrupted" in ev[0]["payload_json"]
    tid = ev[0]["subject"]
    assert conn.execute("SELECT 1 FROM pointer WHERE slot=?", (f"ddmin_test:{tid}",)).fetchone() is None, "an interrupted test has no stored outcome"
    again: list = []
    ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("single", again)).run_search()
    assert any(identity_of_test(m, s) == tid for s in again), "the interrupted test is run again on resume"
    for r in conn.execute("SELECT object_id FROM object_index WHERE slot LIKE 'ddmin_test:%'"):
        assert store_for(conn).get(r["object_id"]).payload["outcome"] in ("FAIL", "PASS", "UNRESOLVED")


def test_an_unresolved_outcome_is_a_finished_test_and_is_not_repeated(conn):
    m = mid("unres")
    unresolved = frozenset({frozenset({"p03"})})
    first: list = []
    r1 = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("single", first, unresolved)).run_search()
    second: list = []
    r2 = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("single", second, unresolved)).run_search()
    assert second == [] and r2.tests_run == 0 and summary(r2.result) == summary(r1.result) and r1.result.unresolved == 1


# ---- TC-13.5.5: damaged checkpoints -----------------------------------------------------------------------------------------------

def damage(conn, tmp_path, seq_from_top=0, m=None):
    oid = conn.execute("SELECT object_id FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq DESC LIMIT 1 OFFSET ?", (m, seq_from_top)).fetchone()[0]
    f = tmp_path / "objects" / oid[:2] / f"{oid}.json"
    raw = bytearray(f.read_bytes())
    raw[len(raw) // 2] ^= 1
    f.write_bytes(bytes(raw))


def test_a_damaged_latest_checkpoint_falls_back_to_the_previous_one(conn, tmp_path):
    m = mid("dmg")
    seen: list = []
    with pytest.raises(Interrupted):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=stopping_after(4, "triple", seen)).run_search()
    damage(conn, tmp_path, 0, m)
    again: list = []
    r = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple", again)).run_search()
    assert r.resumed_from_seq == 3                                                   # the fourth checkpoint was damaged: the third is used
    assert not (set(seen) & set(again)), "the fourth test was still found by its own stored outcome"
    assert summary(r.result) == summary(reference_ddmin(ITEMS, oracle("triple")))
    seqs = [x["seq"] for x in conn.execute("SELECT seq FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq", (m,))]
    assert seqs == list(range(1, len(seqs) + 1)) and len(seqs) > 4, "the damaged checkpoint keeps its place; the chain goes on after it"


def test_when_every_checkpoint_is_damaged_the_error_is_explicit(conn, tmp_path):
    m = mid("alldmg")
    with pytest.raises(Interrupted):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=stopping_after(3, "triple", [])).run_search()
    for i in range(3):
        damage(conn, tmp_path, i, m)
    with pytest.raises(ChainDamaged, match="none can be read"):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple")).run_search()


# ---- TC-13.5.6: two writers ----------------------------------------------------------------------------------------------------------

def test_two_resumers_cannot_both_advance_the_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTLINE_EVIDENCE_DIR", str(tmp_path / "objects"))
    path = tmp_path / "race.db"
    c0 = connect(path)
    migrate(c0)
    m = mid("race")
    barrier = threading.Barrier(2)
    outcomes: list = []

    def worker():
        c = connect(path, check_same_thread=False)

        def t(s):
            try:
                barrier.wait(timeout=10)                                            # both are inside their first test at the same moment
            except threading.BrokenBarrierError:
                pass
            return Outcome.PASS
        try:
            ResumableDdmin(c, minimisation=m, items=["a", "b", "c"], test=t).run_search()
            outcomes.append("finished")
        except ChainAdvanced:
            outcomes.append("advanced")
    ts = [threading.Thread(target=worker) for _ in range(2)]
    [x.start() for x in ts]
    [x.join(timeout=30) for x in ts]
    assert sorted(outcomes) == ["advanced", "finished"], outcomes
    seqs = [r["seq"] for r in c0.execute("SELECT seq FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq", (m,))]
    assert seqs == sorted(set(seqs)) and seqs[0] == 1


def test_the_unique_key_lets_only_one_checkpoint_take_a_position(conn):
    import sqlite3
    conn.execute("INSERT INTO ddmin_checkpoint(minimisation_id, seq, object_id, status, created_at) VALUES ('mn',1,'o1','RUNNING','t')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO ddmin_checkpoint(minimisation_id, seq, object_id, status, created_at) VALUES ('mn',1,'o2','RUNNING','t')")


# ---- TC-13.5.7: budget and algorithm version ----------------------------------------------------------------------------------------

def test_a_budget_that_runs_out_gives_a_limited_result_and_a_later_run_continues(conn):
    m = mid("budget")
    first: list = []
    r1 = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple", first), budget=Budget(max_tests=5)).run_search()
    assert r1.status == "BUDGET_LIMITED" and r1.tests_run == 5
    last = store_for(conn).get(conn.execute("SELECT object_id FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq DESC LIMIT 1", (m,)).fetchone()[0]).payload
    assert last["status"] == "BUDGET_LIMITED" and last["budget"]["tests_used"] == 5 and last["budget"]["max_tests"] == 5
    second: list = []
    r2 = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple", second), budget=Budget(max_tests=200)).run_search()
    assert r2.status == "COMPLETE" and set(r2.result.minimal) == {"p01", "p05", "p10"}
    assert not (set(first) & set(second)) and r2.tests_resumed >= 5, "the five tests already run were not run again"


def test_the_budget_counts_tests_run_before_a_stop(conn):
    m = mid("budget2")
    with pytest.raises(Interrupted):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=stopping_after(3, "triple", []), budget=Budget(max_tests=4)).run_search()
    r = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("triple"), budget=Budget(max_tests=4)).run_search()
    assert r.status == "BUDGET_LIMITED" and r.tests_run == 1, "3 stored + 1 more = the budget of 4, in total across both runs"


def test_a_new_algorithm_version_starts_a_new_chain(conn, monkeypatch):
    a = mid("version")
    ResumableDdmin(conn, minimisation=a, items=ITEMS, test=oracle("single")).run_search()
    monkeypatch.setattr(cp, "ALGORITHM_VERSION", "ddmin/3")
    b = minimisation_id("pk_demo", {"kind": "version"}, ITEMS)
    assert a != b
    calls: list = []
    r = ResumableDdmin(conn, minimisation=b, items=ITEMS, test=oracle("single", calls)).run_search()
    assert r.tests_resumed == 0 and r.resumed_from_seq is None and calls, "the old chain is not resumed"
    assert conn.execute("SELECT COUNT(*) FROM ddmin_checkpoint WHERE minimisation_id=?", (a,)).fetchone()[0] > 0, "the old chain is kept as history"


def test_the_minimisation_id_depends_on_every_input():
    base = minimisation_id("pk", {"e": "x"}, ITEMS)
    assert base == minimisation_id("pk", {"e": "x"}, list(reversed(ITEMS)))
    assert len({base, minimisation_id("pk2", {"e": "x"}, ITEMS), minimisation_id("pk", {"e": "y"}, ITEMS), minimisation_id("pk", {"e": "x"}, ITEMS[:-1])}) == 4
    assert identity_of_test(base, ["a", "b"]) == identity_of_test(base, ["b", "a"]) and identity_of_test(base, ["a"]) != identity_of_test(base, ["a"], "necessity")


def test_a_finished_chain_run_again_runs_nothing_and_adds_no_checkpoint(conn):
    m = mid("again")
    ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("pair")).run_search()
    n = conn.execute("SELECT COUNT(*) FROM ddmin_checkpoint WHERE minimisation_id=?", (m,)).fetchone()[0]
    calls: list = []
    r = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("pair", calls)).run_search()
    assert calls == [] and r.tests_run == 0 and r.tests_resumed > 0
    assert conn.execute("SELECT COUNT(*) FROM ddmin_checkpoint WHERE minimisation_id=?", (m,)).fetchone()[0] == n


def test_the_counters_show_resumed_and_run_tests(conn):
    m = mid("count")
    with pytest.raises(Interrupted):
        ResumableDdmin(conn, minimisation=m, items=ITEMS, test=stopping_after(3, "single", []), analysis_id="an1").run_search()
    ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("single"), analysis_id="an1").run_search()
    c = counters(conn, "an1")["ddmin"]
    assert c["tests_resumed"] >= 3 and c["tests_run"] >= 4


def test_with_the_store_off_the_plain_search_runs(conn, monkeypatch):
    monkeypatch.setenv("FAULTLINE_EVIDENCE_STORE", "off")
    r = ResumableDdmin(conn, minimisation=mid("off"), items=ITEMS, test=oracle("single")).run_search()
    assert r.result.minimal == ("p07",) and r.checkpoints == 0 and r.tests_resumed == 0


def test_a_check_after_the_search_keeps_the_chain_marked_finished(conn):
    m = mid("final")
    rd = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("single"))
    assert rd.run_search().status == "COMPLETE"
    out, detail = rd.check("necessity", frozenset({"p07"}), lambda s: (Outcome.PASS, {"note": "reverted: passes", "world_hash": "w_1"}))
    assert out is Outcome.PASS and detail["note"] == "reverted: passes"
    rows = conn.execute("SELECT seq, status FROM ddmin_checkpoint WHERE minimisation_id=? ORDER BY seq", (m,)).fetchall()
    assert rows[-1]["status"] == "COMPLETE" and len(rows) >= 2, "the checkpoint written for the check does not make a finished chain look unfinished"
    again = ResumableDdmin(conn, minimisation=m, items=ITEMS, test=oracle("single"))
    assert again.run_search().tests_run == 0
    out2, detail2 = again.check("necessity", frozenset({"p07"}), lambda s: (_ for _ in ()).throw(AssertionError("must not run again")))
    assert out2 is Outcome.PASS and detail2["world_hash"] == "w_1"


def test_with_the_store_off_a_test_that_returns_its_detail_gives_the_same_minimal_set(conn, monkeypatch):
    """The attribution's tests return (outcome, detail). With the store off the plain search must unpack them, or no cause is found."""
    def culprit(subset: frozenset[str]):
        return (Outcome.FAIL if "p03" in subset else Outcome.PASS), {"world": "w"}
    on = ResumableDdmin(conn, minimisation=mid("detail-on"), items=ITEMS, test=culprit).run_search()
    monkeypatch.setenv("FAULTLINE_EVIDENCE_STORE", "off")
    off = ResumableDdmin(conn, minimisation=mid("detail-off"), items=ITEMS, test=culprit).run_search()
    assert on.result.minimal == off.result.minimal == ("p03",) and on.status == off.status == "COMPLETE"
