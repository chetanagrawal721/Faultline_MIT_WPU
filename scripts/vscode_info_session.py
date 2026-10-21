"""TC-13.8.5: a real VS Code shows the Information diagnostic (POTENTIAL, from static evidence) on the stored import line of plugins-svc.

Serves the database kept by tests/integration/test_lsp_live.py (var/lsp_live) and opens the consumer's file in VS Code 1.95.3.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fix_session", ROOT / "scripts" / "vscode_fix_session.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)
fix.KEPT = ROOT / "var"                                   # serve("lsp_live") reads var/lsp_live/<name>.db
EVIDENCE = ROOT / "evidence" / "M13.8" / "vscode_information_session.jsonl"

CASES = [("notify-svc/D", "faultline-demo/notify-svc", "Error"), ("plugins-svc", "faultline-demo/plugins-svc", "Information"), ("drivers-svc", "faultline-demo/drivers-svc", "Hint"),
         ("billing-svc/H", "faultline-demo/billing-svc-h", "Warning")]


def main() -> int:
    import os
    import time
    db = ROOT / "var" / "lsp_live" / "lsp.db"
    import shutil
    shutil.copy(db, ROOT / "var" / "lsp_live" / "fix.db")                  # the server reads <kept>/<name>/fix.db
    proc, url = fix.serve("lsp_live")
    print("API at", url, "alive:", proc.poll() is None, flush=True)
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.unlink(missing_ok=True)
    rc = 0
    try:
        for directory, repo, severity in CASES:
            folder = ROOT / "fixtures" / "repos" / directory
            r = subprocess.run([sys.executable, "tools/fl.py", "vscode-test", str(folder), "--open", str(folder / "app" / "main.py"), "--line", "2", "--severity", severity,
                                "--api", url, "--consumer", repo, "--evidence-log", str(EVIDENCE)], cwd=ROOT)
            rc = rc or r.returncode
    finally:
        proc.terminate()
        time.sleep(1)
        (ROOT / "var" / "lsp_live" / "fix.db").unlink(missing_ok=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
