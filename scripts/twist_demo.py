"""The two jury demonstrations of the Incremental Witness, on real sandboxes, from a warm store.

    python scripts/twist_demo.py --preflight        # Docker, image, fixtures, and the warm store (checksum)
    python scripts/twist_demo.py --warm             # one real cold run that fills the store; keeps it under var/twist_demo and writes its checksum
    python scripts/twist_demo.py --demo A           # start warm: rerun unchanged (all reused), change one producer (only its pair recomputes)
    python scripts/twist_demo.py --demo B           # interrupt the cause search, restart, show the checkpoint and that no stored test ran again

Everything is real: the sandbox daemon is started here, the analyses run in Docker, and the repositories are the committed fixtures served from a local
remote (so the pinned commits are the same every time). Each demo prints what it checks and exits 1 if any check fails. The output is also written to
evidence/M13.12/demo_<name>.txt.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

HOME = ROOT / "var" / "twist_demo"
WARM = HOME / "warm"
EVIDENCE = ROOT / "evidence" / "M13.12"
CHECKS = {"failed": 0, "lines": []}


def say(text: str = "") -> None:
    print(text, flush=True)
    CHECKS["lines"].append(text)


def check(cond: bool, label: str, detail: str = "") -> None:
    if not cond:
        CHECKS["failed"] += 1
    say(f"  {'ok  ' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))


# ---- the sandbox daemon, in this process, as the tests start it -------------------------------------------------------------------------------

class Sandbox:
    def __init__(self) -> None:
        from tests.conftest import TOKEN

        from faultline.sandbox import images, runner
        from faultline.sandbox.client import SandboxClient
        from faultline.sandbox.sandboxd import Daemon, serve
        from faultline.storage.store import Store
        if not runner.docker_ok():
            raise SystemExit("Docker is not running")
        self.image = images.default_image()
        HOME.mkdir(parents=True, exist_ok=True)
        self.store = Store(HOME / "store")
        self.daemon = Daemon(TOKEN, store=self.store)
        self.server = serve("127.0.0.1", 0, self.daemon)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.daemon.port = self.server.server_address[1]
        self.client = SandboxClient(port=self.daemon.port, token=TOKEN, timeout=900)

    def close(self) -> None:
        self.server.shutdown()


def store_checksum(objects: Path) -> str:
    """One digest over the names and contents of every stored object: the store is content-addressed, so this changes if anything in it does."""
    h = hashlib.sha256()
    for f in sorted(objects.rglob("*.json")):
        h.update(f.relative_to(objects).as_posix().encode())
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def pair_repos(tag: str, bump: bool = False) -> dict:
    from tests.integration.test_incremental import repos
    return repos(tag, bump_showcase=bump)


def fresh_runs(conn, analysis_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM oracle_run r JOIN oracle_job j ON j.id=r.oracle_job_id WHERE j.analysis_id=? AND r.provenance='FRESH_EXECUTION'",
                        (analysis_id,)).fetchone()[0]


def events(conn, kind: str, analysis_id: str | None = None) -> list[dict]:
    q, a = "SELECT * FROM evidence_event WHERE kind=?", [kind]
    if analysis_id:
        q, a = q + " AND analysis_id=?", [*a, analysis_id]
    return [dict(r) for r in conn.execute(q + " ORDER BY id", a)]


# ---- --preflight -----------------------------------------------------------------------------------------------------------------------------------

def preflight() -> int:
    from faultline.sandbox import images, runner
    say("Preflight")
    check(runner.docker_ok(), "Docker answers")
    try:
        check(bool(images.default_image()), "the execution image is in the allowlist")
    except ValueError as e:
        check(False, "the execution image is in the allowlist", str(e))
    check((ROOT / "fixtures" / "repos" / "acme-bisect").is_dir() and (ROOT / "fixtures" / "twist" / "bisect.yaml").exists(), "the eight-candidate fixture is present")
    meta = HOME / "warm.json"
    if not meta.exists():
        check(False, "a warm store exists", "run: python scripts/twist_demo.py --warm")
    else:
        w = json.loads(meta.read_text(encoding="utf-8"))
        now = store_checksum(WARM / "evidence" / "objects")
        check(now == w["checksum"], "the warm store matches its checksum", now[:16])
        check(w["pairs"] >= 2, "the warm store holds a completed analysis", f"{w['pairs']} pairs")
    return CHECKS["failed"]


# ---- --warm ----------------------------------------------------------------------------------------------------------------------------------------

def warm() -> int:
    from tests.liveenv import ingest_all

    from faultline.analysis.live import run_live_analysis
    from faultline.evidence.counters import counters
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    shutil.rmtree(WARM, ignore_errors=True)
    WARM.mkdir(parents=True)
    sb = Sandbox()
    try:
        conn = connect(WARM / "faultline.db")
        migrate(conn)
        say("Warm run: a real cold analysis of five pairs (nothing is stored yet, so every pair is computed)")
        t0 = time.time()
        apid, _ = ingest_all(conn, sb.client, sb.image, sb.store, pair_repos("w"))
        res = run_live_analysis(conn, sb.client, sb.image, sb.store, apid)
        c = counters(conn, res.analysis_id)
        say(f"  {int(time.time() - t0)} s, counters {json.dumps(c['pairs'])}")
        check(c["pairs"]["recomputed"] >= 2 and c["pairs"]["reused"] == 0, "every pair was computed, none reused")
        conn.close()
        objects = WARM / "evidence" / "objects"
        digest = store_checksum(objects)
        (HOME / "warm.json").write_text(json.dumps({"apid": apid, "analysis_id": res.analysis_id, "pairs": c["pairs"]["recomputed"], "checksum": digest,
                                                    "objects": sum(1 for _ in objects.rglob("*.json"))}, indent=1), encoding="utf-8")
        say(f"  the store now holds {sum(1 for _ in objects.rglob('*.json'))} objects; checksum {digest[:16]}")
    finally:
        sb.close()
    return CHECKS["failed"]


# ---- --demo A --------------------------------------------------------------------------------------------------------------------------------------

def demo_a() -> int:
    from tests.liveenv import ingest_all

    from faultline.analysis.live import run_live_analysis
    from faultline.evidence.counters import counters, pair_statuses
    from faultline.storage.db import connect
    meta = json.loads((HOME / "warm.json").read_text(encoding="utf-8"))
    run = HOME / "runA"
    shutil.rmtree(run, ignore_errors=True)
    shutil.copytree(WARM, run)                                           # the warm store is never written to by a demo
    check(store_checksum(run / "evidence" / "objects") == meta["checksum"], "start from the warm store (checksum equal)")
    sb = Sandbox()
    try:
        conn = connect(run / "faultline.db")
        say("\nDemo A, step 1: run the same analysis again. Nothing has changed.")
        t0 = time.time()
        res = run_live_analysis(conn, sb.client, sb.image, sb.store, meta["apid"])
        c = counters(conn, res.analysis_id)
        say(f"  {int(time.time() - t0)} s, counters {json.dumps(c['pairs'])}")
        check(c["pairs"]["reused"] == meta["pairs"] and c["pairs"]["recomputed"] == 0, "every pair is reused, none is computed", json.dumps(c["pairs"]))
        check(fresh_runs(conn, res.analysis_id) == 0, "no oracle ran in this analysis (0 fresh executions)")
        check(len(events(conn, "PAIR_REUSED", res.analysis_id)) == meta["pairs"], "one PAIR_REUSED event per pair")
        check(all(p["status"] == "REUSED" for p in pair_statuses(conn, res.analysis_id)), "the pair list says REUSED for each pair")

        say("\nDemo A, step 2: one producer gets a new commit (a comment in acme-showcase); run again.")
        t0 = time.time()
        apid2, _ = ingest_all(conn, sb.client, sb.image, sb.store, pair_repos("x", bump=True))
        res2 = run_live_analysis(conn, sb.client, sb.image, sb.store, apid2)
        c2 = counters(conn, res2.analysis_id)
        say(f"  {int(time.time() - t0)} s, counters {json.dumps(c2['pairs'])}")
        check(c2["pairs"]["recomputed"] == 1 and c2["pairs"]["reused"] == meta["pairs"] - 1, "only the changed producer's pair is computed; the others are reused", json.dumps(c2["pairs"]))
        changed = [p for p in pair_statuses(conn, res2.analysis_id) if p["status"] == "RECOMPUTED"]
        say("  why it was computed again: " + "; ".join(f"{p['reason']} ({', '.join(p['changed'])})" for p in changed))
        check(bool(changed) and all(p["reason"] == "CHANGED" and any(x.startswith(("producer.", "producer_artifact")) for x in p["changed"]) for p in changed),
              "the reason names the producer's own inputs", str([p["changed"] for p in changed]))
        check(events(conn, "OBJECT_REJECTED", res2.analysis_id) == [], "no stored object was rejected")
        conn.close()
    finally:
        sb.close()
    return CHECKS["failed"]


# ---- --demo B --------------------------------------------------------------------------------------------------------------------------------------

def demo_b() -> int:
    import yaml
    from tests.liveenv import ingest_all
    from tests.livefix import fixture_repo

    from faultline.analysis.live import run_live_analysis
    from faultline.evidence.dump import dump_evidence
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    label = yaml.safe_load((ROOT / "fixtures" / "twist" / "bisect.yaml").read_text(encoding="utf-8"))["expect"]
    total = label["search"]["total_sandbox_tests"]
    run = HOME / "runB"
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir(parents=True)
    sb = Sandbox()
    try:
        conn = connect(run / "faultline.db")
        migrate(conn)
        tag = str(int(time.time()))
        apid, _ = ingest_all(conn, sb.client, sb.image, sb.store, {f"rm_twb_{tag}_art": ("faultline-demo/acme-bisect", fixture_repo("acme-bisect")),
                                                                   f"rm_twb_{tag}_svc": ("faultline-demo/bisect-svc", fixture_repo("bisect-svc"))})
        say("Demo B, step 1: start the analysis in a worker process and stop it for real right after the third test result is stored.")
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT)]), "FAULTLINE_FAULT": "after_test_stored:3"}
        p = subprocess.run([sys.executable, "-m", "tests.integration.child_analyse", str(run / "faultline.db"), str(sb.daemon.port), sb.image, str(sb.store.root), apid],
                           cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=900)
        check(p.returncode == 77, "the worker ended abruptly (exit code 77, no clean-up)", f"exit code {p.returncode}")
        stored = {r["slot"]: r["object_id"] for r in conn.execute("SELECT slot, object_id FROM object_index WHERE slot LIKE 'ddmin_test:%'")}
        started_before = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_STARTED")]
        finished_before = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_FINISHED")]
        runs_before = {r["id"] for r in conn.execute("SELECT id FROM oracle_run")}
        say(f"  stored test results: {len(stored)}; tests started {len(started_before)}, finished {len(finished_before)}; checkpoints {conn.execute('SELECT COUNT(*) FROM ddmin_checkpoint').fetchone()[0]}")
        check(len(stored) == 3 and len(finished_before) == 3, "three test results were stored before the stop")

        say("\nDemo B, step 2: restart. A new analysis of the same pair takes the minimisation over.")
        t0 = time.time()
        res = run_live_analysis(conn, sb.client, sb.image, sb.store, apid)
        say(f"  finished in {int(time.time() - t0)} s")
        finished = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_FINISHED")]
        started = [e["subject"] for e in events(conn, "DDMIN_ATTEMPT_STARTED")]
        resumed = {e["subject"] for e in events(conn, "DDMIN_TEST_RESUMED")}
        check(len(finished) == len(set(finished)) == total, f"every one of the {total} tests finished exactly once across both processes")
        check(all(started.count(t) == 1 for t in finished_before), "no test whose result was stored was started again")
        check(resumed == set(finished_before), "the stored results were answered from the store (DDMIN_TEST_RESUMED)", f"{len(resumed)} resumed")
        check(all(r in {x["id"] for x in conn.execute("SELECT id FROM oracle_run")} for r in runs_before), "the earlier sandbox run records are still there, unchanged")
        check(all(conn.execute("SELECT object_id FROM object_index WHERE slot=?", (s,)).fetchone()["object_id"] == o for s, o in stored.items()),
              "the stored test objects are byte-for-byte the same objects (content-addressed ids unchanged)")
        chain = [r["seq"] for r in conn.execute("SELECT seq FROM ddmin_checkpoint ORDER BY seq")]
        check(chain == list(range(1, len(chain) + 1)), "the checkpoint chain is intact", f"{len(chain)} checkpoints")
        att = next(a for a in dump_evidence(conn)["attributions"] if a["witness"].endswith('"acme_bisect.web"]'))
        check(att["minimal"] == label["attribution"]["minimal_set"] and att["status"] == label["attribution"]["status"] and att["sidedness"] == label["attribution"]["sidedness"],
              "the attribution is the labelled one", f"{att['minimal']} {att['status']} {att['sidedness']}")
        check(res.analysis_id is not None, "the restarted analysis finished")
        conn.close()
    finally:
        sb.close()
    return CHECKS["failed"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--warm", action="store_true")
    ap.add_argument("--demo", choices=["A", "B"])
    a = ap.parse_args()
    name = "preflight" if a.preflight else "warm" if a.warm else f"demo_{a.demo}" if a.demo else None
    if name is None:
        ap.print_help()
        return 2
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    tmp = tempfile.mkdtemp(prefix="twist-")
    os.environ.setdefault("TMP", tmp)
    rc = preflight() if a.preflight else warm() if a.warm else demo_a() if a.demo == "A" else demo_b()
    say("\n" + ("ALL CHECKS PASSED" if rc == 0 else f"{rc} CHECK(S) FAILED"))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f"{name}.txt").write_text("\n".join(CHECKS["lines"]) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
