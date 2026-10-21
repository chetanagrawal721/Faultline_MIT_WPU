"""TC-13.9.5: a real VS Code applies the verified fix, then reads the next analysis (kept by tests/integration/test_fix_reanalysis.py in var/fix_reanalysis).

Two API processes serve the databases as the editor saw them before and after the fix. The consumer's re-lock between them is what the integration test did.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEPT = ROOT / "var" / "fix_reanalysis"
EVIDENCE = ROOT / "evidence" / "M13.9" / "vscode_fix_session.jsonl"


def serve(name: str) -> tuple[subprocess.Popen, str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "FAULTLINE_DB": str(KEPT / name / "fix.db"), "FAULTLINE_STORE": str(KEPT / name / "store"),
           "FAULTLINE_MODE": "LIVE"}
    code = "import uvicorn;from faultline.api.main import create_app;from faultline.core.config import Settings;uvicorn.run(create_app(Settings.from_env()),host='127.0.0.1',port=%d,log_level='warning')" % port
    p = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.3)
    return p, url


def main() -> int:
    ws = Path(tempfile.mkdtemp()) / "notify-svc"
    shutil.copytree(ROOT / "fixtures" / "repos" / "notify-svc" / "D", ws)
    lock = (ws / "requirements.lock.txt").read_bytes()
    spec = (ws / "requirements.in").read_bytes()
    # the developer's re-lock after the edit is simulated only on the files the editor does not touch: the editor edits requirements.txt (or .in) itself
    procs = [serve("before"), serve("after")]
    try:
        before, after = procs[0][1], procs[1][1]
        target = str(ws / "requirements.in")           # the fix plan names requirements.in (stored fix_plan)
        page = str(ws / "app" / "main.py")
        steps = [{"apply_fix": page, "target": target, "expect_last_line": sys.argv[1] if len(sys.argv) > 1 else "werkzeug<3"},
                 {"set_api": after},
                 {"open": page, "expect_none": True}]
        sf = ws.parent / "steps.json"
        sf.write_text(json.dumps(steps), encoding="utf-8")
        EVIDENCE.unlink(missing_ok=True)
        r = subprocess.run([sys.executable, "tools/fl.py", "vscode-test", str(ws), "--steps", str(sf), "--api", before, "--consumer", "faultline-demo/notify-svc",
                            "--evidence-log", str(EVIDENCE)], cwd=ROOT)
        return r.returncode
    finally:
        for p, _ in procs:
            p.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
