"""M13.10 on real executions: `$/cancelRequest` for `faultline/analyze` stops the real sandbox container and ends the job as CANCELLED.

The chain under test is the one in the editor: LSP client -> language server process -> REST API (uvicorn) -> job queue -> worker process -> sandboxd -> Docker.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from faultline.api.main import create_app
from faultline.core.config import Settings
from faultline.core.enums import Mode
from faultline.sandbox.client import SandboxClient
from faultline.storage import jobs
from faultline.storage.db import connect
from faultline.storage.migrate import migrate
from tests.conftest import TOKEN, labelled_containers
from tests.liveenv import ingest_all
from tests.livefix import fixture_repo
from tests.lsp_client import ROOT, LspClient

pytestmark = [pytest.mark.docker, pytest.mark.slow]
CANCELLED = -32800


def served(tmp_path_factory, daemon, image, repos: dict, name: str) -> dict:
    d = tmp_path_factory.mktemp(name)
    db = d / "faultline.db"
    conn = connect(db)
    migrate(conn)
    sbx = SandboxClient(port=daemon.port, token=TOKEN, timeout=900)
    apid, _ = ingest_all(conn, sbx, image, daemon.store, repos)
    settings = Settings(db_path=db, store_path=Path(daemon.store.root), mode=Mode.LIVE, admin_token=None, lease_seconds=30, heartbeat_seconds=10, poll_seconds=0.5)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started
    return {"db": db, "conn": conn, "apid": apid, "daemon": daemon, "url": f"http://127.0.0.1:{port}", "server": server, "thread": t}


def start_worker(w: dict) -> subprocess.Popen:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "FAULTLINE_DB": str(w["db"]), "FAULTLINE_STORE": str(w["daemon"].store.root),
           "FAULTLINE_SANDBOX_PORT": str(w["daemon"].port), "FAULTLINE_SANDBOX_TOKEN": TOKEN, "FAULTLINE_LEASE_SECONDS": "20",
           "FAULTLINE_HEARTBEAT_SECONDS": "1", "FAULTLINE_POLL_SECONDS": "0.3", "FAULTLINE_MODE": "LIVE", "PYTHONIOENCODING": "utf-8"}
    return subprocess.Popen([sys.executable, "-m", "faultline.workers.run"], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for(pred, what: str, limit: float = 600.0, step: float = 0.2):
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        v = pred()
        if v:
            return v
        time.sleep(step)
    pytest.fail(f"timed out waiting for {what}")


def query(w: dict, sql: str, *a):
    c = connect(w["db"])
    try:
        return [dict(r) for r in c.execute(sql, a)]
    finally:
        c.close()


def job_of_kind(w: dict) -> str | None:
    r = query(w, "SELECT job_id FROM job WHERE kind='live_analysis' ORDER BY created_at DESC LIMIT 1")
    return r[0]["job_id"] if r else None


@pytest.fixture(scope="module")
def scenario_d(daemon, image, tmp_path_factory):
    w = served(tmp_path_factory, daemon, image, {"rm_cn_prod": ("faultline-demo/acme-models", fixture_repo("acme-models")),
                                                 "rm_cn_notify": ("faultline-demo/notify-svc", fixture_repo("notify-svc/D")),
                                                 "rm_cn_orders": ("faultline-demo/orders-svc", fixture_repo("orders-svc/D"))}, "cancel_d")
    yield w
    w["server"].should_exit = True
    w["conn"].close()


@pytest.fixture(scope="module")
def bisect(daemon, image, tmp_path_factory):
    w = served(tmp_path_factory, daemon, image, {"rm_cb_art": ("faultline-demo/acme-bisect", fixture_repo("acme-bisect")),
                                                 "rm_cb_svc": ("faultline-demo/bisect-svc", fixture_repo("bisect-svc"))}, "cancel_bisect")
    yield w
    w["server"].should_exit = True
    w["conn"].close()


def test_tc_13_10_1_a_cancel_from_the_editor_removes_the_running_container_and_the_job_is_cancelled(scenario_d):
    w = scenario_d
    worker = start_worker(w)
    c = LspClient()
    try:
        c.initialize(ROOT / "fixtures" / "repos" / "notify-svc" / "D", {"api": w["url"], "repository": "faultline-demo/notify-svc"})
        rid = c.send_request("faultline/analyze", {})
        job_id = wait_for(lambda: job_of_kind(w), "the editor's request to create a job")
        wait_for(lambda: query(w, "SELECT 1 FROM oracle_job oj JOIN analysis a ON a.id=oj.analysis_id WHERE a.options_json LIKE ? AND oj.status='RUNNING'", f'%"{job_id}"%')
                 and labelled_containers(), "a sandbox container to be running for this job")
        running = labelled_containers()
        t0 = time.monotonic()
        c.cancel(rid)
        r = c.response(rid, timeout=60)
        answered = time.monotonic() - t0
        assert r["error"]["code"] == CANCELLED
        wait_for(lambda: not labelled_containers(), "the containers to be gone", limit=120)
        stopped = time.monotonic() - t0
        wait_for(lambda: jobs.get_job(w["conn"], job_id).status.value == "CANCELLED", "the job to be CANCELLED", limit=120)
        print(f"\nCANCEL: request answered after {answered:.2f} s, containers {running} gone after {stopped:.2f} s from the cancel")

        events = [e["kind"] for e in query(w, "SELECT kind FROM evidence_event WHERE job_id=? ORDER BY id", job_id)]
        assert events[:2] == ["JOB_QUEUED", "JOB_CLAIMED"] and events[-2:] == ["JOB_CANCEL_REQUESTED", "JOB_CANCELLED"], events
        assert stopped < 30, "the container was removed promptly (heartbeat of 1 s in this test)"
        assert [n for n in labelled_containers()] == []
        # TC-13.10.2: the cancelled run claims nothing
        a = query(w, "SELECT id, status, stats_json FROM analysis WHERE options_json LIKE ?", f'%"{job_id}"%')
        assert len(a) == 1
        stats = json.loads(a[0]["stats_json"])
        assert stats["outcome"] == "CANCELLED" and stats["partial"] is True
        assert query(w, "SELECT COUNT(*) n FROM finding WHERE analysis_id=?", a[0]["id"])[0]["n"] == 0, "no finding for work that did not finish"
        assert query(w, "SELECT COUNT(*) n FROM witness WHERE analysis_id=?", a[0]["id"])[0]["n"] == 0, "no witness from a cancelled run"
        assert query(w, "SELECT COUNT(*) n FROM oracle_job WHERE status='RUNNING' AND analysis_id=?", a[0]["id"])[0]["n"] == 0
        assert not [m for m in c.drain(1.0) if m.get("method") == "textDocument/publishDiagnostics"]
        assert c.shutdown() == 0
    finally:
        c.kill()
        worker.kill()
        worker.wait(timeout=30)


def test_tc_13_10_4_a_cancel_during_a_minimisation_test_leaves_a_chain_that_resumes(bisect):
    w = bisect
    worker = start_worker(w)
    c = LspClient()
    try:
        c.initialize(ROOT / "fixtures" / "repos" / "bisect-svc", {"api": w["url"], "repository": "faultline-demo/bisect-svc"})
        rid = c.send_request("faultline/analyze", {})
        job1 = wait_for(lambda: job_of_kind(w), "the first job")
        wait_for(lambda: len(query(w, "SELECT 1 FROM evidence_event WHERE kind='DDMIN_ATTEMPT_FINISHED'")) >= 3
                 and len(query(w, "SELECT 1 FROM evidence_event WHERE kind='DDMIN_ATTEMPT_STARTED'")) >= 4 and labelled_containers(), "the search to be inside its fourth test")
        c.cancel(rid)
        assert c.response(rid, timeout=60)["error"]["code"] == CANCELLED
        wait_for(lambda: not labelled_containers(), "the containers to be gone", limit=120)
        wait_for(lambda: jobs.get_job(w["conn"], job1).status.value == "CANCELLED", "the job to be CANCELLED", limit=120)

        started = [e["subject"] for e in query(w, "SELECT subject FROM evidence_event WHERE kind='DDMIN_ATTEMPT_STARTED'")]
        finished = [e["subject"] for e in query(w, "SELECT subject FROM evidence_event WHERE kind='DDMIN_ATTEMPT_FINISHED'")]
        interrupted = [e["subject"] for e in query(w, "SELECT subject FROM evidence_event WHERE kind='DDMIN_ATTEMPT_INTERRUPTED'")]
        lost = set(started) - set(finished)
        assert lost and lost <= set(interrupted), "the test the cancel stopped is recorded as interrupted, not as an outcome"
        for t in lost:
            assert not query(w, "SELECT 1 FROM pointer WHERE slot=?", f"ddmin_test:{t}"), "no outcome was stored for a stopped test"
        seqs = [r["seq"] for r in query(w, "SELECT seq FROM ddmin_checkpoint ORDER BY seq")]
        assert seqs == list(range(1, len(seqs) + 1)) and len(seqs) >= 3, "the chain is intact"
        assert query(w, "SELECT COUNT(*) n FROM attribution")[0]["n"] == 0, "no attribution was claimed"

        # the chain resumes in a new analysis
        rid2 = c.send_request("faultline/analyze", {})
        r2 = c.response(rid2, timeout=900)
        assert r2["result"]["status"] == "DONE", r2
        finished2 = [e["subject"] for e in query(w, "SELECT subject FROM evidence_event WHERE kind='DDMIN_ATTEMPT_FINISHED'")]
        assert len(finished2) == len(set(finished2)) == 10, "every test finished exactly once across the cancelled and the resumed analysis"
        resumed = {e["subject"] for e in query(w, "SELECT subject FROM evidence_event WHERE kind='DDMIN_TEST_RESUMED'")}
        assert set(finished) <= resumed, "the tests finished before the cancel were answered from the store"
        a = query(w, "SELECT status, minimal_set_json FROM attribution")
        assert len(a) == 1 and a[0]["status"] == "COMPLETE" and json.loads(a[0]["minimal_set_json"]) == ["werkzeug"]
        assert c.shutdown() == 0
    finally:
        c.kill()
        worker.kill()
        worker.wait(timeout=30)
