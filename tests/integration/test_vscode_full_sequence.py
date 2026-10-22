"""M13.12 (TC-13.12.3): the whole editor sequence in ONE real VS Code session: the diagnostic, the verified fix, and a cancel that stops the sandbox.

One database holds a real analysis of scenario D and the verified fix that the remediation stored for the break. A real VS Code 1.95.3 (started by
@vscode/test-electron, with the extension loaded) then, without being restarted:
  1. opens notify-svc's app/main.py and holds a BREAK WITNESSED error on line 2,
  2. applies the verified fix from its own code action (the line `werkzeug<3` is appended to requirements.in and nothing else),
  3. starts an analysis from the editor and cancels it with the editor's own cancellation; the sandbox container is gone and the job is CANCELLED.
The step log of the session and a `docker ps` timeline are the record (evidence/M13.12/editor_sequence.jsonl). It is a scripted session, not a screen video.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import pytest

from faultline.analysis.live import run_live_analysis
from faultline.remediation.minimal import remediate
from faultline.storage import jobs
from tests.conftest import labelled_containers
from tests.integration.test_lsp_cancel import ROOT, job_of_kind, query, served, start_worker
from tests.livefix import fixture_repo

pytestmark = [pytest.mark.docker, pytest.mark.slow,
              pytest.mark.skipif(sys.platform != "win32" and not os.environ.get("DISPLAY"), reason="a real VS Code window needs a display")]
EVIDENCE = ROOT / "evidence" / "M13.12" / "editor_sequence.jsonl"


@pytest.fixture(scope="module")
def stack(daemon, image, tmp_path_factory):
    from faultline.sandbox.client import SandboxClient
    from tests.conftest import TOKEN
    w = served(tmp_path_factory, daemon, image, {"rm_seq_prod": ("faultline-demo/acme-models", fixture_repo("acme-models")),
                                                 "rm_seq_notify": ("faultline-demo/notify-svc", fixture_repo("notify-svc/D")),
                                                 "rm_seq_orders": ("faultline-demo/orders-svc", fixture_repo("orders-svc/D"))}, "editor_sequence")
    sbx = SandboxClient(port=daemon.port, token=TOKEN, timeout=900)
    res = run_live_analysis(w["conn"], sbx, image, daemon.store, w["apid"])
    broken = w["conn"].execute("SELECT id FROM finding WHERE analysis_id=? AND verdict='BREAK_WITNESSED' AND headline LIKE '%notify-svc%'", (res.analysis_id,)).fetchone()
    assert broken is not None, "scenario D breaks the consumer"
    fix = remediate(w["conn"], sbx, image, daemon.store, broken["id"])
    assert fix.label == "VERIFIED" and fix.constraint == "werkzeug<3", (fix.label, fix.reason)
    w["fix"] = fix
    yield w
    w["server"].should_exit = True
    w["conn"].close()


def test_tc_13_12_3_diagnostic_fix_and_cancel_in_one_vs_code_session(stack, tmp_path, monkeypatch):
    w = stack
    monkeypatch.setenv("FAULTLINE_REUSE", "off")           # the pair was just computed; with reuse on the editor's analysis would finish at once and there would be nothing to cancel
    workspace = tmp_path / "notify-svc"
    shutil.copytree(ROOT / "fixtures" / "repos" / "notify-svc" / "D", workspace)
    target = workspace / w["fix"].target_path
    steps = tmp_path / "steps.json"
    steps.write_text(json.dumps([
        {"open": str(workspace / "app" / "main.py"), "expect": {"line": 2, "severity": "Error"}},
        {"apply_fix": str(workspace / "app" / "main.py"), "target": str(target), "expect_last_line": "werkzeug<3"},
        {"analyze_then_cancel": {"after_ms": 60000}}]), encoding="utf-8")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.unlink(missing_ok=True)

    seen: list[tuple[float, int]] = []
    stop = threading.Event()
    t0 = time.monotonic()

    def sample():
        while not stop.is_set():
            seen.append((time.monotonic() - t0, len(labelled_containers())))
            time.sleep(0.4)
    threading.Thread(target=sample, daemon=True).start()
    worker = start_worker(w)
    try:
        p = subprocess.run([sys.executable, "tools/fl.py", "vscode-test", str(workspace), "--steps", str(steps), "--api", w["url"],
                            "--consumer", "faultline-demo/notify-svc", "--evidence-log", str(EVIDENCE)], cwd=ROOT, capture_output=True, text=True, timeout=1200)
        assert p.returncode == 0, (p.stdout + p.stderr)[-1500:]
        deadline = time.monotonic() + 60
        while labelled_containers() and time.monotonic() < deadline:
            time.sleep(0.3)
    finally:
        stop.set()
        worker.kill()
        worker.wait(timeout=30)

    log = [json.loads(line) for line in EVIDENCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    names = [e.get("event") for e in log if "event" in e]
    for want in ("diagnostic held by VS Code", "code actions offered by VS Code", "fix applied by VS Code and saved", "analysis requested from VS Code",
                 "cancelling from VS Code", "the request ended", "all steps passed"):
        assert want in names, (want, names)
    held = next(e for e in log if e.get("event") == "diagnostic held by VS Code")
    assert held["line"] == 2 and held["severity"] == "Error" and held["message"].startswith("BREAK WITNESSED: ")
    applied = next(e for e in log if e.get("event") == "fix applied by VS Code and saved")
    assert applied["addedLine"].strip() == "werkzeug<3"
    assert any(n > 0 for _, n in seen), "a job container was running while the editor session was open"
    assert not labelled_containers(), "no job container remains"
    job_id = job_of_kind(w)
    assert jobs.get_job(w["conn"], job_id).status.value == "CANCELLED"
    kinds = [e["kind"] for e in query(w, "SELECT kind FROM evidence_event WHERE job_id=? ORDER BY id", job_id)]
    assert kinds[-2:] == ["JOB_CANCEL_REQUESTED", "JOB_CANCELLED"], kinds
    summary = {"event": "container timeline from docker ps", "samples": len(seen), "last_seen_running_s": round(max((t for t, n in seen if n > 0), default=0), 2),
               "job": job_id, "job_events": kinds}
    with EVIDENCE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    print("\n" + json.dumps(summary))
