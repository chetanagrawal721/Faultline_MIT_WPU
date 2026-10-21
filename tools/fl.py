#!/usr/bin/env python3
"""Cross-platform task runner. The Makefile only forwards here, so Windows and Linux behave the same.

  python tools/fl.py up [--check] [--port 8000]   start API + worker (+ built UI); --check boots, probes, stops
  python tools/fl.py down                          stop processes started with `up --detach`
  python tools/fl.py test                          unit + integration tests
  python tools/fl.py lint                          ruff
  python tools/fl.py fixtures                      run fixture scenarios (arrives with M1.1)
  python tools/fl.py e2e [SCENARIO]                end-to-end scenario run (arrives with M1.8)
  python tools/fl.py check-pins                    verify tool and dependency pins
  python tools/fl.py vscode <folder>               build the VS Code extension and open the folder with it (the language server)
  python tools/fl.py vscode-test <folder> --open FILE --line N   run a real VS Code with the extension and check the diagnostic it holds
  python tools/fl.py rebuild [--dry-run]           recreate the evidence rows of the SQL tables from the stored objects
  python tools/fl.py gen-types                     regenerate OpenAPI JSON and TypeScript types
  python tools/fl.py check-types                   fail if the committed types are stale (the CI drift check)
  python tools/fl.py ci                            everything CI runs, in order

Every command exits non-zero on failure.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VAR = ROOT / "var"


def venv_python() -> str:
    for cand in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if cand.exists():
            return str(cand)
    return sys.executable


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(cwd), env={**os.environ, **(env or {})})


def kill_tree(pid: int) -> None:
    """Stop a process and its children. On Windows the venv python.exe is a launcher that spawns the real
    interpreter, so terminating the launcher alone would leave the server running."""
    if os.name == "nt":
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def npm(*args: str) -> list[str]:
    return [shutil.which("npm") or "npm", *args]


# ----------------------------------------------------------------------------- commands

def cmd_test(_: list[str]) -> int:
    # tests/security needs Docker and the built image; its fixtures skip (and say so) when either is missing
    return run([venv_python(), "-m", "pytest", "-q", "tests/unit", "tests/integration", "tests/security"])


def cmd_lint(_: list[str]) -> int:
    return run([venv_python(), "-m", "ruff", "check", "backend", "tests", "tools", "scripts"])


def cmd_fixtures(_: list[str]) -> int:
    script = ROOT / "scripts" / "run_fixtures.py"
    if not script.exists():
        print("fixtures are not available yet: scripts/run_fixtures.py arrives with milestone M1.1", file=sys.stderr)
        return 2
    return run([venv_python(), str(script), "--assert"])


def cmd_e2e(args: list[str]) -> int:
    if not list((ROOT / "tests" / "e2e").glob("test_*.py")):
        print("no end-to-end tests yet: the first arrives with milestone M1.8", file=sys.stderr)
        return 2
    env = {"FAULTLINE_SCENARIO": args[0]} if args else {}
    return run([venv_python(), "-m", "pytest", "-q", "tests/e2e"], env=env)


def cmd_check_pins(_: list[str]) -> int:
    return run([venv_python(), "scripts/check_pins.py"])


def cmd_images(_: list[str] | None = None) -> int:
    probe = subprocess.run(["docker", "info"], capture_output=True)
    if probe.returncode:
        print("Docker is not running: skipping the image build; sandbox tests will be skipped", file=sys.stderr)
        return 0
    return run([venv_python(), "scripts/build_images.py"])


def cmd_gen_types(_: list[str]) -> int:
    rc = run([venv_python(), "scripts/export_openapi.py"])
    return rc or run(npm("run", "gen:types"), cwd=FRONTEND)


def build_ui() -> int:
    if not (FRONTEND / "node_modules").exists():
        rc = run(npm("ci", "--no-audit", "--no-fund"), cwd=FRONTEND)
        if rc:
            return rc
    return run(npm("run", "build"), cwd=FRONTEND)


def wait_http(url: str, timeout: float = 30.0) -> bytes:
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.read()
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last = exc
            time.sleep(0.3)
    raise RuntimeError(f"{url} did not answer in {timeout}s: {last}")


def cmd_up(args: list[str]) -> int:
    check = "--check" in args
    detach = "--detach" in args
    port = int(args[args.index("--port") + 1]) if "--port" in args else 8000
    if not (FRONTEND / "dist" / "index.html").exists():
        rc = build_ui()
        if rc:
            return rc
    db_dir = Path(tempfile.mkdtemp(prefix="faultline-up-")) if check else VAR
    env = {**os.environ, "FAULTLINE_DB": str(db_dir / "faultline.db"), "PYTHONPATH": str(ROOT / "backend")}
    VAR.mkdir(exist_ok=True)
    py = venv_python()
    out = {}
    if detach:
        out = {"stdout": open(VAR / "api.log", "ab"), "stderr": subprocess.STDOUT}   # keep the caller's terminal free
    api = subprocess.Popen([py, "-m", "uvicorn", "faultline.api.main:app_factory", "--factory",
                            "--host", "127.0.0.1", "--port", str(port)], cwd=str(ROOT), env=env, **out)
    if detach:
        out = {"stdout": open(VAR / "worker.log", "ab"), "stderr": subprocess.STDOUT}
    worker = subprocess.Popen([py, "-m", "faultline.workers.run"], cwd=str(ROOT), env=env, **out)
    procs = [api, worker]
    sandboxd = None
    if (ROOT / "docker" / "images.lock.json").exists():
        out = {"stdout": open(VAR / "sandboxd.log", "ab"), "stderr": subprocess.STDOUT} if detach else {}
        sandboxd = subprocess.Popen([py, "-m", "faultline.sandbox.sandboxd"], cwd=str(ROOT), env=env, **out)
        procs.append(sandboxd)

    def stop(*_):
        for p in procs:
            if p.poll() is None:
                kill_tree(p.pid)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    try:
        base = f"http://127.0.0.1:{port}"
        health = json.loads(wait_http(f"{base}/api/health"))
        caps = json.loads(wait_http(f"{base}/api/capabilities"))
        ui = wait_http(f"{base}/")
        print(f"API ok (schema v{health['schema_version']}, mode {health['mode']}), "
              f"sandbox {caps['sandbox']['state']}, UI {len(ui)} bytes at {base}/")
        if worker.poll() is not None:
            print("worker exited early", file=sys.stderr)
            return 1
        if check:
            return 0
        if detach:
            (VAR / "pids.json").write_text(json.dumps({"api": api.pid, "worker": worker.pid,
                                                      **({"sandboxd": sandboxd.pid} if sandboxd else {})}))
            print("started in the background; stop with: python tools/fl.py down")
            return 0
        print("running. Ctrl-C to stop.")
        signal.signal(signal.SIGINT, stop)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        return 1
    finally:
        if not detach or check:
            stop()
            if check:
                shutil.rmtree(db_dir, ignore_errors=True)


def cmd_rebuild(args: list[str]) -> int:
    """Rebuild the evidence rows of the SQL tables from the immutable objects (--dry-run checks and rolls back)."""
    return run([venv_python(), "-m", "faultline.evidence.cli", *args], env={"PYTHONPATH": str(ROOT / "backend")})


def server_python() -> tuple[str, list[str]]:
    """The interpreter VS Code starts the language server with, and what goes on its PYTHONPATH.

    The virtual environment's own python.exe is a launcher that fails when VS Code starts it ("No Python at ..."), so the server is started with
    the base interpreter the environment was made from, with the backend and the environment's site-packages on PYTHONPATH.
    """
    venv = ROOT / ".venv"
    home = None
    cfg = venv / "pyvenv.cfg"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("home"):
                home = line.split("=", 1)[1].strip()
    for cand in ((Path(home) / "python.exe", venv / "Lib" / "site-packages"), (Path(home) / "python3", next(iter((venv / "lib").glob("python3*/site-packages")), venv / "lib"))) if home else ():
        if cand[0].exists() and cand[1].exists():
            return str(cand[0]), [str(ROOT / "backend"), str(cand[1])]
    return venv_python(), [str(ROOT / "backend")]


def cmd_vscode(args: list[str]) -> int:
    """Build the VS Code extension and open a folder (the consumer repository) in an Extension Development Host with it loaded."""
    folder = next((a for a in args if not a.startswith("--")), None)
    if not folder or not Path(folder).is_dir():
        print("usage: python tools/fl.py vscode <folder> [--open FILE] [--api URL] [--consumer owner/name] [--evidence-log FILE]", file=sys.stderr)
        return 2
    ext = ROOT / "editors" / "vscode"
    if not (ext / "node_modules").exists() and run(npm("install"), cwd=ext):
        return 1
    if run(npm("run", "compile"), cwd=ext):
        return 1
    code = shutil.which("code")
    if not code:
        print("the `code` command is not on PATH: install VS Code and its shell command", file=sys.stderr)
        return 1
    py, paths = server_python()
    env = {"FAULTLINE_PYTHON": py, "FAULTLINE_BACKEND": os.pathsep.join(paths)}
    for flag, name in (("--api", "FAULTLINE_API"), ("--consumer", "FAULTLINE_CONSUMER")):
        if flag in args:
            env[name] = args[args.index(flag) + 1]
    if "--evidence-log" in args:
        env["FAULTLINE_EVIDENCE_LOG"] = str(Path(args[args.index("--evidence-log") + 1]).resolve())
    opened = [str(Path(args[i + 1]).resolve()) for i, a in enumerate(args) if a == "--open"]
    # a profile of its own: a VS Code that is already running would take the new window's environment from itself, not from this command, and
    # the isolated instance also leaves the user's own settings and windows alone
    profile = VAR / "vscode-profile"
    return run([code, f"--extensionDevelopmentPath={ext}", f"--user-data-dir={profile}", "--disable-workspace-trust", "--new-window", str(Path(folder).resolve()), *opened], env=env)


def cmd_vscode_test(args: list[str]) -> int:
    """Run a real VS Code (a pinned build, downloaded once) with the extension and check the diagnostic it holds for a file.

    python tools/fl.py vscode-test <folder> --open FILE --line N [--severity Error] [--api URL] [--consumer owner/name] [--evidence-log FILE]
    """
    def opt(flag: str, default: str | None = None) -> str | None:
        return args[args.index(flag) + 1] if flag in args else default
    folder, file, line = (args[0] if args and not args[0].startswith("--") else None), opt("--open"), opt("--line")
    if not (folder and file and line):
        print(cmd_vscode_test.__doc__, file=sys.stderr)
        return 2
    ext = ROOT / "editors" / "vscode"
    if not (ext / "node_modules").exists() and run(npm("install"), cwd=ext):
        return 1
    py, paths = server_python()
    env = {"FAULTLINE_TEST_FOLDER": str(Path(folder).resolve()), "FAULTLINE_TEST_FILE": str(Path(file).resolve()), "FAULTLINE_TEST_LINE": line,
           "FAULTLINE_TEST_SEVERITY": opt("--severity", "Error") or "Error", "FAULTLINE_PYTHON": py, "FAULTLINE_BACKEND": os.pathsep.join(paths)}
    for flag, name in (("--api", "FAULTLINE_API"), ("--consumer", "FAULTLINE_CONSUMER")):
        if opt(flag):
            env[name] = opt(flag) or ""
    if opt("--evidence-log"):
        env["FAULTLINE_EVIDENCE_LOG"] = str(Path(opt("--evidence-log") or "").resolve())
    return run(npm("test"), cwd=ext, env=env)


def cmd_down(_: list[str]) -> int:
    f = VAR / "pids.json"
    if not f.exists():
        print("nothing to stop")
        return 0
    for name, pid in json.loads(f.read_text()).items():
        kill_tree(pid)
        print(f"stopped {name} ({pid})")
    f.unlink()
    return 0


def cmd_ci(_: list[str]) -> int:
    steps = [
        ("lint", cmd_lint),
        ("pins", cmd_check_pins),
        ("images", lambda a: cmd_images()),
        ("tests", cmd_test),
        ("openapi/types current", lambda a: types_current()),
        ("frontend build", lambda a: build_ui()),
        ("boot", lambda a: cmd_up(["--check", "--port", "8123"])),
    ]
    for name, fn in steps:
        print(f"\n=== {name} ===", flush=True)
        rc = fn([])
        if rc:
            print(f"\nCI step failed: {name}", file=sys.stderr)
            return rc
    print("\nCI: all steps passed")
    return 0


def types_current() -> int:
    """The committed OpenAPI JSON and generated TypeScript types must match the API as it is now."""
    rc = run([venv_python(), "scripts/export_openapi.py", "--check"])
    if rc:
        return rc
    tmp = Path(tempfile.mkdtemp(prefix="fl-types-")) / "schema.d.ts"
    rc = run(npm("exec", "--", "openapi-typescript", "./openapi.json", "-o", str(tmp)), cwd=FRONTEND)
    if rc:
        return rc
    committed = (FRONTEND / "src" / "api" / "schema.d.ts").read_text(encoding="utf-8")
    if tmp.read_text(encoding="utf-8") != committed:
        print("frontend/src/api/schema.d.ts is stale: run `python tools/fl.py gen-types`", file=sys.stderr)
        return 1
    print("TypeScript types are current")
    return 0


COMMANDS = {"up": cmd_up, "down": cmd_down, "test": cmd_test, "lint": cmd_lint, "fixtures": cmd_fixtures,
            "e2e": cmd_e2e, "check-pins": cmd_check_pins, "gen-types": cmd_gen_types,
            "check-types": lambda a: types_current(), "images": cmd_images, "ci": cmd_ci, "rebuild": cmd_rebuild, "vscode": cmd_vscode, "vscode-test": cmd_vscode_test}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))
