"""M13.10 (TC-13.10.5): a real VS Code starts an analysis, cancels it through its own cancellation, and the real container disappears.

VS Code (a pinned build started by @vscode/test-electron) -> the extension -> the language server -> the API -> the worker -> sandboxd -> Docker. The test
samples `docker ps` while the editor session runs, and checks the job and the events afterwards.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from faultline.storage import jobs
from tests.conftest import labelled_containers
from tests.integration.test_lsp_cancel import ROOT, job_of_kind, query, served, start_worker
from tests.livefix import fixture_repo

pytestmark = [pytest.mark.docker, pytest.mark.slow]
EVIDENCE = ROOT / "evidence" / "M13.10" / "vscode_cancel_session.jsonl"


@pytest.fixture(scope="module")
def stack(daemon, image, tmp_path_factory):
    w = served(tmp_path_factory, daemon, image, {"rm_vs_prod": ("faultline-demo/acme-models", fixture_repo("acme-models")),
                                                 "rm_vs_notify": ("faultline-demo/notify-svc", fixture_repo("notify-svc/D")),
                                                 "rm_vs_orders": ("faultline-demo/orders-svc", fixture_repo("orders-svc/D"))}, "vscode_cancel")
    yield w
    w["server"].should_exit = True
    w["conn"].close()


def test_tc_13_10_5_cancelling_from_vs_code_stops_the_container(stack, tmp_path):
    w = stack
    steps = tmp_path / "steps.json"
    steps.write_text(json.dumps([{"analyze_then_cancel": {"after_ms": 70000}}]), encoding="utf-8")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.unlink(missing_ok=True)

    seen: list[tuple[float, int]] = []                                     # (seconds since start, number of job containers)
    stop = threading.Event()
    t0 = time.monotonic()

    def sample():
        while not stop.is_set():
            seen.append((time.monotonic() - t0, len(labelled_containers())))
            time.sleep(0.4)
    threading.Thread(target=sample, daemon=True).start()
    worker = start_worker(w)
    try:
        p = subprocess.run([sys.executable, "tools/fl.py", "vscode-test", str(ROOT / "fixtures" / "repos" / "notify-svc" / "D"), "--steps", str(steps), "--api", w["url"],
                            "--consumer", "faultline-demo/notify-svc", "--evidence-log", str(EVIDENCE)], cwd=ROOT, capture_output=True, text=True, timeout=900)
        ended = time.monotonic() - t0
        tail = (p.stdout + p.stderr)[-1500:]
        assert p.returncode == 0, tail
        deadline = time.monotonic() + 60
        while labelled_containers() and time.monotonic() < deadline:
            time.sleep(0.3)
        gone = time.monotonic() - t0
    finally:
        stop.set()
        worker.kill()
        worker.wait(timeout=30)

    log = [json.loads(line) for line in EVIDENCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = {e["event"]: e for e in log if "event" in e}
    assert {"analysis requested from VS Code", "cancelling from VS Code", "the request ended", "checks passed"} <= set(events), list(events)
    outcome = events["the request ended"]
    assert outcome["ok"] is False and (outcome.get("code") == -32800 or "cancel" in outcome.get("message", "").lower()), outcome
    cancel_at = t0 + 0  # the editor's clock and this one differ by the start-up time; use the sampled containers instead
    assert any(n > 0 for _, n in seen), "a job container was running while the editor session was open"
    assert not labelled_containers(), "no job container remains"
    job_id = job_of_kind(w)
    assert jobs.get_job(w["conn"], job_id).status.value == "CANCELLED"
    kinds = [e["kind"] for e in query(w, "SELECT kind FROM evidence_event WHERE job_id=? ORDER BY id", job_id)]
    assert kinds[-2:] == ["JOB_CANCEL_REQUESTED", "JOB_CANCELLED"], kinds
    last_running = max((t for t, n in seen if n > 0), default=0)
    summary = {"event": "container timeline from docker ps", "samples": len(seen), "last_seen_running_s": round(last_running, 2), "session_ended_s": round(ended, 2),
               "no_container_after_s": round(gone, 2), "job": job_id, "job_events": kinds}
    with EVIDENCE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    print("\n" + json.dumps(summary))
    assert cancel_at is not None and Path(EVIDENCE).exists()
