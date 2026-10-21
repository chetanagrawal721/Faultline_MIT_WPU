"""M13.6: an interrupted minimisation resumes on real executions, and a test whose outcome was stored is never run again.

The fixture (acme-bisect and bisect-svc) has worlds that differ by eight packages; one of them, werkzeug, breaks `import acme_bisect.web`.
The expected result is in fixtures/twist/bisect.yaml, written before the first run. Workers are lost for real: the analysis runs in a child
process that is killed, or that exits at an exact point (FAULTLINE_FAULT), and a new analysis then takes over.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from faultline.analysis.live import run_live_analysis
from faultline.attribution.checkpoint import identity_of_test
from faultline.evidence.counters import counters
from faultline.evidence.dump import dump_evidence
from faultline.evidence.runtime import objects_dir
from tests.liveenv import ingest_all
from tests.livefix import fixture_repo

pytestmark = pytest.mark.docker

ROOT = Path(__file__).resolve().parents[2]
LABEL = yaml.safe_load((ROOT / "fixtures" / "twist" / "bisect.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def world(daemon, image):
    import tempfile

    from faultline.sandbox.client import SandboxClient
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    from tests.conftest import TOKEN
    return {"dir": Path(tempfile.mkdtemp()), "sbx": SandboxClient(port=daemon.port, token=TOKEN, timeout=900), "image": image, "daemon": daemon,
            "connect": connect, "migrate": migrate, "n": 0}


def fresh(world, tag: str):
    """A new database with the fixture ingested (separate remote names, so the pinned commits are the same in every database)."""
    path = world["dir"] / f"{tag}.db"
    conn = world["connect"](path)
    world["migrate"](conn)
    apid, _ = ingest_all(conn, world["sbx"], world["image"], world["daemon"].store, {
        f"rm_bis_{tag}_art": ("faultline-demo/acme-bisect", fixture_repo("acme-bisect")),
        f"rm_bis_{tag}_svc": ("faultline-demo/bisect-svc", fixture_repo("bisect-svc"))})
    return conn, path, apid


def child(world, path: Path, apid: str, **env) -> subprocess.Popen:
    e = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT)]), **env}
    return subprocess.Popen([sys.executable, "-m", "tests.integration.child_analyse", str(path), str(world["daemon"].port), world["image"],
                             str(world["daemon"].store.root), apid], cwd=str(ROOT), env=e, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def attribution(conn, analysis_id=None):
    """The attribution of the import witness. Not filtered by analysis: a witness belongs to the analysis that first made it (the killed one), and a
    later analysis of the same pair finds it again through the pair key."""
    return next(a for a in dump_evidence(conn)["attributions"] if a["witness"].endswith('"acme_bisect.web"]'))


def events(conn, kind):
    return [dict(r) for r in conn.execute("SELECT * FROM evidence_event WHERE kind=? ORDER BY id", (kind,))]


def last_analysis(conn) -> str:
    return conn.execute("SELECT id FROM analysis ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()[0]


@pytest.fixture(scope="module")
def uninterrupted(world):
    conn, path, apid = fresh(world, "whole")
    res = run_live_analysis(conn, world["sbx"], world["image"], world["daemon"].store, apid)
    return conn, res


def test_tc_13_6_1_the_labelled_change_is_found_and_the_test_count_matches(uninterrupted):
    conn, res = uninterrupted
    exp = LABEL["expect"]
    f = dump_evidence(conn, res.analysis_id)["findings"]
    assert [x["verdict"] for x in f] == [exp["verdict"]]
    w = [x for x in dump_evidence(conn, res.analysis_id)["witnesses"] if x["entry_point"] == exp["entry_point"]]
    assert len(w) == 1 and w[0]["signature"]["exc_type"] == exp["signature"]["exc_type"] and exp["signature"]["message_contains"] in w[0]["signature"]["message_norm"]
    a = attribution(conn, res.analysis_id)
    assert a["minimal"] == exp["attribution"]["minimal_set"] and a["status"] == exp["attribution"]["status"] and a["sidedness"] == exp["attribution"]["sidedness"]
    assert sorted(LABEL["delta"]) == sorted({x for att in a["attempts"] for x in att["subset"]})
    finished = events(conn, "DDMIN_ATTEMPT_FINISHED")
    assert len(finished) == exp["search"]["total_sandbox_tests"], [e["payload_json"] for e in finished]
    assert len({e["subject"] for e in finished}) == len(finished), "every test ran once"
    c = counters(conn, res.analysis_id)["ddmin"]
    assert c == {"tests_resumed": 0, "tests_run": exp["search"]["total_sandbox_tests"]}


def wait_for(cond, timeout=300.0, step=0.05):
    end = time.time() + timeout
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(step)
    raise AssertionError("the condition never became true")


@pytest.fixture(scope="module")
def killed(world, uninterrupted):
    """The worker is killed in the middle of the fourth test; a new analysis then takes the chain over."""
    conn, path, apid = fresh(world, "killed")
    p = child(world, path, apid)
    try:
        # the fourth test has started and the third has finished: the worker is inside a sandbox run
        wait_for(lambda: p.poll() is not None or (len(events(conn, "DDMIN_ATTEMPT_STARTED")) == 4 and len(events(conn, "DDMIN_ATTEMPT_FINISHED")) == 3), timeout=600)
        assert p.poll() is None, "the worker finished before it could be killed: " + (p.stderr.read().decode()[-500:] if p.stderr else "")
        p.kill()
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    before = {"finished": [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_FINISHED")], "started": [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_STARTED")]}
    res = run_live_analysis(conn, world["sbx"], world["image"], world["daemon"].store, apid)
    return conn, res, before


def test_tc_13_6_2_a_killed_worker_resumes_and_no_stored_test_runs_again(killed, uninterrupted):
    conn, res, before = killed
    assert len(before["finished"]) == 3 and len(before["started"]) == 4
    interrupted_test = (set(before["started"]) - set(before["finished"])).pop()
    finished = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_FINISHED")]
    assert len(finished) == len(set(finished)) == LABEL["expect"]["search"]["total_sandbox_tests"], "every test finished exactly once across both processes"
    for t in before["finished"]:
        assert finished.count(t) == 1 and [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_STARTED")].count(t) == 1, "a stored test was not started again"
    assert [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_STARTED")].count(interrupted_test) == 2, "the killed test ran once more"
    assert interrupted_test in [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_INTERRUPTED")], "the lost attempt is recorded as interrupted, not as a failure"
    resumed = events(conn, "DDMIN_TEST_RESUMED")
    assert len({e["subject"] for e in resumed}) == 3 and {e["subject"] for e in resumed} == set(before["finished"])
    a = attribution(conn, res.analysis_id)
    assert a["minimal"] == LABEL["expect"]["attribution"]["minimal_set"] and a["status"] == "COMPLETE"
    pairs = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM pair_cell").fetchone()[0]
    assert pairs == 1, "the killed analysis and the new one worked on the same pair key"


def test_tc_13_6_4_nothing_of_the_killed_job_remains(killed, world):
    conn, res, before = killed
    assert not wait_for_no_containers(), "a container of the killed worker is still there"
    ev = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_INTERRUPTED")]
    assert ev and not conn.execute("SELECT 1 FROM ddmin_checkpoint WHERE status='FAILED'").fetchone()


def wait_for_no_containers(timeout=60.0) -> list[str]:
    end = time.time() + timeout
    ids: list[str] = []
    while time.time() < end:
        r = subprocess.run(["docker", "ps", "--filter", "label=faultline=1", "--format", "{{.Names}}"], capture_output=True, text=True)
        ids = [n for n in r.stdout.split() if not n.startswith("faultline-egress")]          # the egress proxy is long-lived by design
        if not ids:
            return []
        time.sleep(1.0)
    return ids


@pytest.fixture(scope="module")
def faulted(world, uninterrupted):
    """The worker exits right after the third outcome was stored and before its checkpoint was appended."""
    conn, path, apid = fresh(world, "faulted")
    p = child(world, path, apid, FAULTLINE_FAULT="after_test_stored:3")
    assert p.wait(timeout=900) == 77, p.stderr.read().decode()[-800:]
    stored = [r["slot"] for r in conn.execute("SELECT slot FROM object_index WHERE slot LIKE 'ddmin_test:%'")]
    res = run_live_analysis(conn, world["sbx"], world["image"], world["daemon"].store, apid)
    return conn, res, stored


def test_tc_13_6_3_a_stop_before_the_checkpoint_does_not_run_that_test_again(faulted):
    conn, res, stored = faulted
    assert len(stored) == 3
    from faultline.evidence.runtime import store_for
    chk = [store_for(conn).get(r["object_id"]).payload for r in conn.execute("SELECT object_id FROM ddmin_checkpoint ORDER BY seq")]
    third = stored[2].removeprefix("ddmin_test:")
    started = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_STARTED")]
    assert started.count(third) == 1, "the third test was started once, in the process that stored it"
    assert [e["payload"] for e in [{"payload": e["payload_json"]} for e in events(conn, "DDMIN_TEST_RESUMED")] if "stored test" in e["payload"]], "found by its own stored outcome"
    finished = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_FINISHED")]
    assert len(finished) == len(set(finished)) == LABEL["expect"]["search"]["total_sandbox_tests"]
    seqs = [c["seq"] for c in chk]
    assert seqs == list(range(1, len(seqs) + 1)) and chk[-1]["status"] == "COMPLETE"
    assert attribution(conn, res.analysis_id)["minimal"] == LABEL["expect"]["attribution"]["minimal_set"]


def test_tc_13_6_5_a_resumed_attribution_equals_the_uninterrupted_one(uninterrupted, killed, faulted):
    conn0, res0 = uninterrupted
    base = attribution(conn0, res0.analysis_id)
    for conn, res, *_ in (killed, faulted):
        got = attribution(conn, res.analysis_id)
        assert got == base, "same minimal set, statuses, notes and the same attempts in the same order"
    assert identity_of_test("mn", ["a"]) != identity_of_test("mn", ["b"]) and objects_dir(conn0)
