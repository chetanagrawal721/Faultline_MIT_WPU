"""M13.2: the evidence rows can be rebuilt from the immutable objects, and a bad object never makes a rebuild destructive."""
import hashlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from faultline.api.main import create_app
from faultline.core.config import Settings
from faultline.core.enums import Mode
from faultline.evidence import projections
from faultline.evidence.dump import dump_evidence
from faultline.evidence.rebuild import rebuild
from faultline.evidence.runtime import objects_dir
from faultline.storage.db import connect
from tests.integration.test_evidence_projection import analyse_scenario_d

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def analysed(daemon, image, tmp_path_factory):
    return analyse_scenario_d(daemon, image, tmp_path_factory.mktemp("evidence_rebuild"))


def snapshot(conn, analysis_id) -> dict:
    """The REST responses that carry evidence: the analysis, the findings, each finding's detail and why-path, and each witness's bundle manifest."""
    db = conn.execute("PRAGMA database_list").fetchone()["file"]
    settings = Settings(db_path=Path(db), store_path=Path(db).parent / "api-store", mode=Mode.LIVE, admin_token=None, lease_seconds=30,
                        heartbeat_seconds=10, poll_seconds=0.5)
    out: dict = {}
    with TestClient(create_app(settings)) as c:
        out["analysis"] = c.get(f"/api/analyses/{analysis_id}").json()
        out["findings"] = c.get("/api/findings").json()
        for f in out["findings"]:
            out[f"finding {f['finding_id']}"] = c.get(f"/api/findings/{f['finding_id']}").json()
            out[f"why {f['finding_id']}"] = c.get(f"/api/findings/{f['finding_id']}/why-path").json()
        for w in conn.execute("SELECT id FROM witness ORDER BY id"):
            r = c.get(f"/api/witnesses/{w['id']}/bundle/manifest")
            m = r.json() if r.status_code == 200 else r.status_code
            if isinstance(m, dict):
                m.pop("created_at", None)                                        # the time of this request; the bundle id and every file hash stay in
            out[f"manifest {w['id']}"] = m
    return out


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def clone(conn, tmp: Path, monkeypatch):
    """A copy of the database and of the object folder, so a test may damage them."""
    objs = tmp / "objects"
    shutil.copytree(objects_dir(conn), objs)
    c = connect(tmp / "copy.db")
    conn.backup(c)
    monkeypatch.setenv("FAULTLINE_EVIDENCE_DIR", str(objs))
    return c, objs


def counts(conn):
    return projections.RESULT_TABLES and {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in projections.RESULT_TABLES}


def test_tc_13_2_4_rebuild_reproduces_the_api_and_leaves_the_objects_alone(analysed):
    conn, res = analysed
    before = snapshot(conn, res.analysis_id)
    assert before["findings"] and any(k.startswith("manifest") and isinstance(v, dict) for k, v in before.items())
    objs = objects_dir(conn)
    objects_before = tree_hash(objs)
    rows_before = counts(conn)

    dry = rebuild(conn, dry_run=True)                                            # a dry run changes nothing
    assert dry["status"] == "DRY_RUN_OK" and dry["identical"] and counts(conn) == rows_before

    conn.execute("PRAGMA foreign_keys=OFF")
    for t in projections.RESULT_TABLES:                                          # empty the projection tables
        conn.execute(f"DELETE FROM {t}")
    conn.execute("PRAGMA foreign_keys=ON")
    assert snapshot(conn, res.analysis_id)["findings"] == [], "emptying the tables must change what the API serves"

    report = rebuild(conn, allow_loss=True)                                      # nothing is left to lose: the tables are empty on purpose
    assert report["status"] == "REBUILT" and not report["rejected"] and not report["skipped"], report
    assert counts(conn) == rows_before
    assert snapshot(conn, res.analysis_id) == before                             # the API says exactly what it said
    assert tree_hash(objs) == objects_before                                     # the object folder is byte-identical
    assert conn.execute("SELECT COUNT(*) FROM evidence_event WHERE kind='REBUILD_DONE'").fetchone()[0] == 1


def test_a_second_rebuild_changes_nothing(analysed):
    conn, res = analysed
    before = dump_evidence(conn)
    r = rebuild(conn)
    assert r["status"] == "REBUILT" and r["identical"] and dump_evidence(conn) == before


def test_tc_13_2_5_a_corrupt_object_is_reported_and_nothing_is_deleted(analysed, tmp_path, monkeypatch):
    conn, res = analysed
    c, objs = clone(conn, tmp_path, monkeypatch)
    run_obj = next(oid for oid, _ in __import__("faultline.evidence.object_store", fromlist=["x"]).FsObjectStore(objs).iter_objects()
                   if __import__("faultline.evidence.object_store", fromlist=["x"]).FsObjectStore(objs).get(oid).kind == "oracle_result")
    f = objs / run_obj[:2] / f"{run_obj}.json"
    raw = bytearray(f.read_bytes())
    raw[len(raw) // 2] ^= 0x01
    f.write_bytes(bytes(raw))
    objects_before, rows_before, dump_before = tree_hash(objs), counts(c), dump_evidence(c)

    r = rebuild(c)                                                               # without --allow-loss the damaged run row would be lost
    assert r["status"] == "REFUSED" and [x["object_id"] for x in r["rejected"]] == [run_obj] and "without an object" in r["reason"]
    assert counts(c) == rows_before and dump_evidence(c) == dump_before          # the tables are exactly as they were
    assert tree_hash(objs) == objects_before                                     # the damaged object is still there, untouched

    r2 = rebuild(c, allow_loss=True)                                             # the operator accepts losing that one run
    assert r2["status"] == "REBUILT" and [x["object_id"] for x in r2["rejected"]] == [run_obj]
    assert counts(c)["oracle_run"] == rows_before["oracle_run"] - 1 and counts(c)["witness"] == rows_before["witness"]
    assert tree_hash(objs) == objects_before
    assert c.execute("SELECT COUNT(*) FROM evidence_event WHERE kind='OBJECT_REJECTED' AND subject=?", (run_obj,)).fetchone()[0] == 2   # once per attempt


def test_a_missing_parent_object_skips_the_child_and_reports_it(analysed, tmp_path, monkeypatch):
    conn, res = analysed
    c, objs = clone(conn, tmp_path, monkeypatch)
    from faultline.evidence.object_store import FsObjectStore
    st = FsObjectStore(objs)
    wit = next(oid for oid, _ in st.iter_objects() if st.get(oid).kind == "witness" and st.get(oid).payload["row"]["oracle"] == "o_import")
    (objs / wit[:2] / f"{wit}.json").unlink()                                    # the import witness object is gone
    r = rebuild(c, allow_loss=True)
    assert r["status"] == "REBUILT"
    assert any(s["kind"] == "attribution" for s in r["skipped"]), r["skipped"]    # its attribution has no parent row any more
    assert c.execute("SELECT COUNT(*) FROM attribution").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM finding").fetchone()[0] == 1          # the finding itself is still rebuilt


def test_a_failing_rebuild_leaves_the_old_tables_in_place(analysed, tmp_path, monkeypatch):
    conn, res = analysed
    c, objs = clone(conn, tmp_path, monkeypatch)
    rows_before, dump_before, objects_before = counts(c), dump_evidence(c), tree_hash(objs)

    def boom(*_a, **_k):
        raise RuntimeError("the rebuild is interrupted")
    monkeypatch.setitem(projections.APPLY, "verdict", boom)
    with pytest.raises(RuntimeError):
        rebuild(c)
    assert not c.in_transaction
    assert counts(c) == rows_before and dump_evidence(c) == dump_before and tree_hash(objs) == objects_before
