"""M13.10: faultline/analyze and $/cancelRequest. The job is created with an idempotency key; a cancel reaches the API once, in every order of events, and a
cancelled request never publishes results. (That the cancel stops the real container is in tests/integration/test_lsp_cancel.py.)"""
import time

from tests.fake_api import FakeApi, cell, finding
from tests.lsp_client import LspClient

PROJECTS = [{"id": "ap_1", "created_at": "2026-10-22T00:00:00Z", "repositories": [{"owner": "faultline-demo", "name": "bisect-svc"}]}]
REPO = {"repository": "faultline-demo/bisect-svc"}
CANCELLED = -32800                                           # LSP: RequestCancelled


def server(tmp_path, **fake_kw):
    a = FakeApi([finding()], {"an_1": [cell()]}, None, None, PROJECTS, {}, **fake_kw)
    c = LspClient()
    c.initialize(tmp_path, {"api": a.url, "consumer": "faultline-demo/bisect-svc"})
    return a, c


def notifications(c: LspClient, method: str) -> list[dict]:
    return [m["params"] for m in c.log if m.get("method") == method]


def wait_until(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_an_analysis_that_finishes_answers_with_the_job_and_publishes_for_open_files(tmp_path):
    a, c = server(tmp_path, job_script=["QUEUED", "RUNNING", "DONE"])
    try:
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, "from acme_bisect.web import make_app\n")
        c.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri)
        r = c.request("faultline/analyze", REPO, timeout=30)
        assert r["result"]["status"] == "DONE" and r["result"]["job_id"] == a.created[0]
        assert [n["state"] for n in notifications(c, "faultline/analysis")] == ["started", "done"]
        assert a.cancelled == []
        assert [k for k in a.jobs_by_key] and next(iter(a.jobs_by_key)).startswith("lsp-"), "the job was created with an idempotency key from this session"
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_two_requests_get_two_keys_and_the_same_key_is_the_same_job(tmp_path):
    a, c = server(tmp_path)
    try:
        c.request("faultline/analyze", REPO, timeout=30)
        c.request("faultline/analyze", REPO, timeout=30)
        keys = list(a.jobs_by_key)
        assert len(keys) == 2 and keys[0] != keys[1] and keys[0].rsplit("-", 1)[0] == keys[1].rsplit("-", 1)[0]
        assert a.jobs_by_key.get(keys[0]) == "job_1" and a.created == ["job_1", "job_2"]
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_tc_13_10_3_cancelling_a_running_request_cancels_the_job_and_answers_request_cancelled(tmp_path):
    a, c = server(tmp_path, job_script=["RUNNING"])
    try:
        rid = c.send_request("faultline/analyze", REPO)
        assert wait_until(lambda: a.created and a.polls.get(a.created[0], 0) >= 2), "the job is running"
        c.cancel(rid)
        r = c.response(rid)
        assert r["error"]["code"] == CANCELLED
        assert a.cancelled == ["job_1"]
        assert "cancel requested" in [n["state"] for n in notifications(c, "faultline/analysis")]
        rest = c.drain(1.0)
        assert not [m for m in rest if m.get("method") == "textDocument/publishDiagnostics"], "a cancelled request publishes nothing"
        assert c.shutdown() == 0
    finally:
        c.kill()
        a.close()


def test_a_repeated_cancel_has_no_second_effect(tmp_path):
    a, c = server(tmp_path, job_script=["RUNNING"])
    try:
        rid = c.send_request("faultline/analyze", REPO)
        assert wait_until(lambda: a.created and a.polls.get(a.created[0], 0) >= 2)
        for _ in range(3):
            c.cancel(rid)
        assert c.response(rid)["error"]["code"] == CANCELLED
        c.drain(0.5)
        assert a.cancelled == ["job_1"] and [r for r in a.requests if r.endswith("/cancel")] == ["POST /api/jobs/job_1/cancel"]
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_a_cancel_for_an_unknown_request_is_ignored(tmp_path):
    a, c = server(tmp_path)
    try:
        c.cancel(424242)
        c.request("faultline/analyze", REPO, timeout=30)
        c.cancel(1)                                                  # an id that has already been answered
        c.drain(0.5)
        assert a.cancelled == [] and c.proc.poll() is None
        assert c.shutdown() == 0
    finally:
        c.kill()
        a.close()


def test_a_cancel_before_the_job_exists_lets_the_creation_finish_and_cancels_what_it_made(tmp_path):
    a, c = server(tmp_path, job_script=["RUNNING"], create_delay=1.5)
    try:
        rid = c.send_request("faultline/analyze", REPO)
        time.sleep(0.4)                                              # the API is still creating the job
        c.cancel(rid)
        assert c.response(rid, timeout=20)["error"]["code"] == CANCELLED
        assert wait_until(lambda: a.cancelled == ["job_1"], 10), (a.created, a.cancelled)
        assert a.created == ["job_1"], "exactly one job was made, and it was cancelled"
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_a_cancel_that_arrives_after_the_job_finished_changes_nothing(tmp_path):
    a, c = server(tmp_path, job_script=["DONE"])
    try:
        rid = c.send_request("faultline/analyze", REPO)
        r = c.response(rid, timeout=30)
        assert r["result"]["status"] == "DONE"
        c.cancel(rid)
        c.drain(0.5)
        assert a.cancelled == [] and c.proc.poll() is None
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_a_cancel_when_the_api_has_gone_is_reported_and_does_not_crash_the_server(tmp_path):
    a, c = server(tmp_path, job_script=["RUNNING"])
    try:
        rid = c.send_request("faultline/analyze", REPO)
        assert wait_until(lambda: a.created and a.polls.get(a.created[0], 0) >= 2)
        a.close()                                                    # the API is gone when the cancel is sent
        c.cancel(rid)
        r = c.response(rid, timeout=30)
        # either order is legitimate: the cancel arrives first (answered as cancelled) or the poll finds the API gone first (answered with an error); a result is never given
        assert "result" not in r and r["error"]["code"] in (CANCELLED, -32603), r
        c.drain(0.5)
        states = [n["state"] for n in notifications(c, "faultline/status")]
        assert "unavailable" in states, "the cancel that could not be sent is reported, never shown as done"
        assert [m for m in c.log if m.get("method") == "window/showMessage"] and c.proc.poll() is None
        assert c.shutdown() == 0
    finally:
        c.kill()


def test_a_failed_job_is_reported_not_published(tmp_path):
    a, c = server(tmp_path, job_script=["RUNNING", "FAILED"])
    try:
        r = c.request("faultline/analyze", REPO, timeout=30)
        assert r["result"]["status"] == "FAILED"
        assert [n["state"] for n in notifications(c, "faultline/analysis")][-1] == "failed"
        c.shutdown()
    finally:
        c.kill()
        a.close()
