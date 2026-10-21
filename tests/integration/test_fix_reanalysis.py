"""M13.9 (TC-13.9.4): a verified fix, applied as the code action's edit, makes the witness go away on a new analysis, and a pair it did not touch is reused.

The consumer is notify-svc (scenario D, Werkzeug 3 under Flask 2.2.2: the import breaks). Remediation verifies `werkzeug<3` with fresh runs; the editor's edit
appends that line to the consumer's requirements file. The consumer keeps a lock file, which is authoritative for its world, so the developer's next step is to
lock again: here with the same `uv pip compile` the fixtures were made with. The edited repository is then analysed again.
"""
from pathlib import Path

import pytest

from faultline.analysis.live import run_live_analysis
from faultline.core.hashing import content_hash
from faultline.evidence.counters import counters, pair_statuses
from faultline.lsp.code_actions import FixInfo, build_action
from faultline.remediation.minimal import remediate
from faultline.storage.db import connect
from tests.liveenv import ingest_all
from tests.livefix import fixture_repo
from tests.unit.test_lsp_code_actions import apply, diag

pytestmark = pytest.mark.docker


def relock(spec: Path, out: Path) -> bytes:
    """The same compile the fixtures were made with (scripts/make_fixtures.py), so the new lock differs only by what the constraint changes."""
    import subprocess
    import sys
    cmd = [sys.executable, "-m", "uv", "pip", "compile", str(spec), "--generate-hashes", "--no-header", "--python-version", "3.12", "--python-platform",
           "x86_64-unknown-linux-gnu", "--exclude-newer", "2024-10-30T00:00:00Z", "--only-binary", ":all:", "--no-annotate", "-q", "-o", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return out.read_bytes()


def keep_state(conn, name: str) -> None:
    """A consistent copy of the database and its evidence objects under var/fix_reanalysis/<name> (var/ is not committed)."""
    import shutil

    from faultline.evidence.runtime import objects_dir
    root = Path(__file__).resolve().parents[2] / "var" / "fix_reanalysis" / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    dest = connect(root / "fix.db")
    conn.backup(dest)
    dest.close()
    shutil.copytree(objects_dir(conn), root / "evidence" / "objects")


def repos(tag: str, consumer_files: dict) -> dict:
    return {f"rm_fix{tag}_models": ("faultline-demo/acme-models", fixture_repo("acme-models")),
            f"rm_fix{tag}_notify": ("faultline-demo/notify-svc", consumer_files),
            f"rm_fix{tag}_http": ("faultline-demo/acme-http", fixture_repo("acme-http")),
            f"rm_fix{tag}_orders": ("faultline-demo/orders-svc-c", fixture_repo("orders-svc/C"))}


def test_tc_13_9_4_the_edit_removes_the_witness_and_the_untouched_pair_is_reused(daemon, image, tmp_path):
    import tempfile

    from faultline.sandbox.client import SandboxClient
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    from tests.conftest import TOKEN
    conn = connect(Path(tempfile.mkdtemp()) / "fix.db")
    migrate(conn)
    sbx = SandboxClient(port=daemon.port, token=TOKEN, timeout=900)
    consumer = dict(fixture_repo("notify-svc/D"))
    apid, _ = ingest_all(conn, sbx, image, daemon.store, repos("a", consumer))
    first = run_live_analysis(conn, sbx, image, daemon.store, apid)

    print("\nFIRST ANALYSIS funnel:", first.funnel)
    print("FIRST ANALYSIS stats:", conn.execute("SELECT stats_json FROM analysis WHERE id=?", (first.analysis_id,)).fetchone()[0])
    print("FIRST ANALYSIS findings:", [(r["verdict"], r["h"]) for r in conn.execute("SELECT verdict, substr(headline,1,110) h FROM finding WHERE analysis_id=?", (first.analysis_id,))])
    broken = conn.execute("SELECT f.id, f.cell_id FROM finding f WHERE f.analysis_id=? AND f.verdict='BREAK_WITNESSED' AND f.headline LIKE '%notify-svc%'", (first.analysis_id,)).fetchone()
    assert broken is not None, "the consumer breaks under Werkzeug 3 (scenario D)"
    others = conn.execute("SELECT COUNT(*) FROM finding WHERE analysis_id=? AND id<>?", (first.analysis_id, broken["id"])).fetchone()[0]
    assert others >= 1, "a second pair (acme-http and orders-svc) was analysed too"

    r = remediate(conn, sbx, image, daemon.store, broken["id"])
    assert r.label == "VERIFIED" and r.constraint == "werkzeug<3" and r.fresh_runs >= 6, (r.label, r.reason)
    assert r.target_path in ("requirements.txt", "requirements.in") and r.target_sha256 == content_hash(consumer[r.target_path])
    original = consumer[r.target_path]

    # what the editor would do: build the action from the stored fix and apply its edit to a copy of the consumer
    ws = tmp_path / "notify-svc"
    ws.mkdir()
    for rel, data in consumer.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    fix = FixInfo(broken["id"], r.label, r.constraint, r.consumer, r.target_path, r.target_sha256, r.diff)
    action = build_action(diag(fid=broken["id"]), fix, [ws], lambda uri: None)
    assert action is not None
    assert action.edit.document_changes[0].text_document.uri.endswith("/" + r.target_path), "the edit is on the file the fix names"
    edited = apply((ws / r.target_path).read_bytes().decode("utf-8"), action.edit.document_changes[0].edits[0])
    assert edited.endswith("werkzeug<3\n") and edited.startswith(original.decode())
    fixed = dict(consumer)
    fixed[r.target_path] = edited.encode()
    # the developer locks again: the lock file is authoritative for the consumer's world, so the constraint reaches it only through a new lock
    spec = ws / "requirements.in"
    spec.write_bytes(fixed["requirements.in"] if r.target_path == "requirements.in" else consumer["requirements.in"] + b"werkzeug<3\n")
    fixed["requirements.in"] = spec.read_bytes()
    fixed["requirements.lock.txt"] = relock(spec, ws / "requirements.lock.txt")

    keep_state(conn, "before")                                   # the database as the editor saw it before the fix (for a real VS Code session)
    apid2, _ = ingest_all(conn, sbx, image, daemon.store, repos("b", fixed))
    second = run_live_analysis(conn, sbx, image, daemon.store, apid2)
    c2 = counters(conn, second.analysis_id)
    pairs2 = pair_statuses(conn, second.analysis_id)
    print("\nAFTER THE FIX", c2["pairs"], [(p["status"], p["reason"], p["verdict"]) for p in pairs2], [x["state"] for x in second.cells])

    keep_state(conn, "after")
    # the witness is gone: the notify cell is no longer a break
    notify_cells = [x for x in second.cells if x["finding_id"] is None or conn.execute("SELECT verdict FROM finding WHERE id=?", (x["finding_id"],)).fetchone()["verdict"] != "BREAK_WITNESSED"]
    assert notify_cells, "no cell of the second analysis still reports a break for notify-svc"
    still = conn.execute("SELECT COUNT(*) FROM finding WHERE analysis_id=? AND verdict='BREAK_WITNESSED' AND headline LIKE '%notify-svc%'", (second.analysis_id,)).fetchone()[0]
    assert still == 0
    # the pair the fix did not touch is reused; nothing is computed for it again
    assert c2["pairs"]["reused"] >= 1 and c2["pairs"]["unfinished"] == 0
    reused = [p for p in pairs2 if p["status"] == "REUSED"]
    assert reused and all(p["verdict"] == "BREAK_WITNESSED" for p in reused), "the acme-http pair is the reused one, and its verdict is unchanged"
    # whatever was recomputed names the consumer's inputs as the reason
    for p in pairs2:
        if p["status"] == "RECOMPUTED":
            assert any(x.startswith("consumers.") or x in ("consumer_world_hash",) for x in p["changed"]), p
