"""M13.4: stored pair results are reused when the pair key matches, and only the pairs whose inputs changed are computed again.

One database and one store go through four analyses of a five-pair set (four producers, five consumers and one control consumer):
  cold      empty store: every pair is computed                                           (TC-13.4.1, the setup run that warms the store)
  rerun     the same project again: every pair is reused and no oracle runs                (TC-13.4.2)
  changed   one producer gets a new commit: only its pair is computed again                (TC-13.4.3)
  damaged   one stored result is damaged: that pair is rejected and computed again         (TC-13.4.4)
"""
import json
import time
from pathlib import Path

import pytest

from faultline.analysis.live import run_live_analysis
from faultline.evidence.counters import counters, pair_statuses
from faultline.evidence.dump import dump_evidence
from faultline.evidence.runtime import objects_dir
from tests.liveenv import ingest_all
from tests.livefix import fixture_repo

pytestmark = pytest.mark.docker

PRODUCERS = {"models": "acme-models", "http": "acme-http", "contracts": "acme-contracts", "showcase": "acme-showcase"}
# remote tag -> (slug, fixture directory)
PAIR_SET = {
    "models": ("faultline-demo/acme-models", "acme-models"),
    "http": ("faultline-demo/acme-http", "acme-http"),
    "contracts": ("faultline-demo/acme-contracts", "acme-contracts"),
    "showcase": ("faultline-demo/acme-showcase", "acme-showcase"),
    "notify": ("faultline-demo/notify-svc", "notify-svc/D"),
    "billing_b": ("faultline-demo/billing-svc-b", "billing-svc/B"),
    "orders_c": ("faultline-demo/orders-svc-c", "orders-svc/C"),
    "billing_j": ("faultline-demo/billing-svc-j", "billing-svc/J"),
    "fulfilment": ("faultline-demo/fulfilment-svc", "fulfilment-svc"),
    "reporting": ("faultline-demo/reporting-svc", "reporting-svc"),
}
EXPECTED_PAIRS = 5                          # the control consumer matches the showcase reference: no drift, nothing to run


def repos(tag: str, bump_showcase: bool = False) -> dict:
    out = {}
    for k, (slug, directory) in PAIR_SET.items():
        files = dict(fixture_repo(directory))
        if bump_showcase and k == "showcase":
            f = "src/acme_showcase/ids.py"
            files[f] = files[f] + b"\n# revision 2: a comment only\n"          # a new commit and artifact; every behaviour is the same
        out[f"rm_inc{tag}_{k}"] = (slug, files)
    return out


@pytest.fixture(scope="module")
def env(daemon, image):
    import tempfile

    from faultline.sandbox.client import SandboxClient
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    from tests.conftest import TOKEN
    conn = connect(Path(tempfile.mkdtemp()) / "inc.db")
    migrate(conn)
    return {"conn": conn, "sbx": SandboxClient(port=daemon.port, token=TOKEN, timeout=900), "image": image, "store": daemon.store, "seen": {}}


def analyse(env, tag: str, *, bump_showcase: bool = False, apid: str | None = None) -> dict:
    c, sbx = env["conn"], env["sbx"]
    t0 = time.time()
    if apid is None:
        apid, _ = ingest_all(c, sbx, env["image"], env["store"], repos(tag, bump_showcase))
    t1 = time.time()
    res = run_live_analysis(c, sbx, env["image"], env["store"], apid)
    out = {"apid": apid, "res": res, "ingest_s": round(t1 - t0, 1), "analysis_s": round(time.time() - t1, 1),
           "counters": counters(c, res.analysis_id), "pairs": pair_statuses(c, res.analysis_id)}
    env["seen"][tag or "cold"] = out
    print(f"\n[{tag or 'cold'}] ingest {out['ingest_s']} s, analysis {out['analysis_s']} s, counters {json.dumps(out['counters'])}")
    return out


def fresh_runs(conn, analysis_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM oracle_run r JOIN oracle_job j ON j.id=r.oracle_job_id WHERE j.analysis_id=? AND r.provenance='FRESH_EXECUTION'",
                        (analysis_id,)).fetchone()[0]


def findings(conn, analysis_id: str) -> list[dict]:
    """What a finding says, without its ids and without the note that it was reused."""
    out = []
    for f in dump_evidence(conn, analysis_id)["findings"]:
        scope = dict(f["scope"])
        scope.pop("reused", None)
        out.append({k: v for k, v in f.items() if k != "scope"} | {"scope": scope})
    return sorted(out, key=lambda d: json.dumps(d, sort_keys=True))


@pytest.fixture(scope="module")
def cold(env):
    return analyse(env, "")


@pytest.fixture(scope="module")
def rerun(env, cold):
    return analyse(env, "_rerun", apid=cold["apid"])


@pytest.fixture(scope="module")
def changed(env, rerun):
    return analyse(env, "_new", bump_showcase=True)


@pytest.fixture(scope="module")
def damaged(env, changed):
    """Damage the stored verdict of one old pair, then analyse the changed project again."""
    from faultline.evidence.object_store import FsObjectStore
    conn = env["conn"]
    key = next(p["pair_key"] for p in changed["pairs"] if p["status"] == "REUSED")
    oid = conn.execute("SELECT verdict_id FROM pair_index WHERE pair_key=?", (key,)).fetchone()[0]
    f = objects_dir(conn) / oid[:2] / f"{oid}.json"
    raw = bytearray(f.read_bytes())
    raw[len(raw) // 2] ^= 0x01
    f.write_bytes(bytes(raw))
    assert not FsObjectStore(objects_dir(conn)).get(oid).ok
    out = analyse(env, "_damaged", apid=changed["apid"])
    out["damaged_key"], out["damaged_object"] = key, oid
    return out


def test_tc_13_4_1_cold_run_computes_every_pair(env, cold):
    c = cold["counters"]
    assert c["pairs"] == {"reused": 0, "recomputed": EXPECTED_PAIRS, "unfinished": 0, "rejected_objects": 0}
    assert c["worlds"]["built"] > 0
    assert len(cold["pairs"]) == EXPECTED_PAIRS and all(p["status"] == "RECOMPUTED" and p["reason"] == "NEW" for p in cold["pairs"])
    conn = env["conn"]
    started = len(conn.execute("SELECT 1 FROM evidence_event WHERE analysis_id=? AND kind='PAIR_RECOMPUTE_STARTED'", (cold["res"].analysis_id,)).fetchall())
    assert started == EXPECTED_PAIRS and fresh_runs(conn, cold["res"].analysis_id) >= EXPECTED_PAIRS * 6
    states = {x["state"] for x in cold["res"].cells}
    assert states == {"ANALYZED", "NO_DRIFT"}, states
    verdicts = sorted(f["verdict"] for f in dump_evidence(conn, cold["res"].analysis_id)["findings"])
    assert "BREAK_WITNESSED" in verdicts and len(verdicts) == EXPECTED_PAIRS, verdicts


def test_tc_13_4_2_an_unchanged_rerun_reuses_everything_and_runs_nothing(env, cold, rerun):
    c = rerun["counters"]
    assert c["pairs"] == {"reused": EXPECTED_PAIRS, "recomputed": 0, "unfinished": 0, "rejected_objects": 0}
    assert all(p["status"] == "REUSED" for p in rerun["pairs"]) and len(rerun["pairs"]) == EXPECTED_PAIRS
    conn = env["conn"]
    assert fresh_runs(conn, rerun["res"].analysis_id) == 0, "a reused pair must not run any oracle"
    assert conn.execute("SELECT COUNT(*) FROM oracle_job WHERE analysis_id=?", (rerun["res"].analysis_id,)).fetchone()[0] == 0
    assert findings(conn, rerun["res"].analysis_id) == findings(conn, cold["res"].analysis_id), "a reused finding says what the computed one said"
    reused_scope = [json.loads(r["scope_json"]).get("reused") for r in conn.execute("SELECT scope_json FROM finding WHERE analysis_id=?", (rerun["res"].analysis_id,))]
    assert all(s and s["pair_key"] and s["from_analysis"] == cold["res"].analysis_id for s in reused_scope)
    assert rerun["analysis_s"] < cold["analysis_s"]
    print(f"\ncold analysis {cold['analysis_s']} s, reused rerun {rerun['analysis_s']} s")


def test_tc_13_4_3_a_changed_producer_recomputes_only_its_pair(env, cold, rerun, changed):
    c = changed["counters"]
    assert c["pairs"] == {"reused": EXPECTED_PAIRS - 1, "recomputed": 1, "unfinished": 0, "rejected_objects": 0}
    recomputed = [p for p in changed["pairs"] if p["status"] == "RECOMPUTED"]
    assert len(recomputed) == 1 and recomputed[0]["reason"] == "CHANGED"
    assert set(recomputed[0]["changed"]) >= {"producer.commit", "producer_artifact_sha256"}
    assert not [x for x in recomputed[0]["changed"] if x.startswith("consumers.") or x in ("reference_world_hash", "consumer_world_hash")], recomputed[0]["changed"]
    conn = env["conn"]
    assert fresh_runs(conn, changed["res"].analysis_id) >= 6
    assert findings(conn, changed["res"].analysis_id) == findings(conn, cold["res"].analysis_id), "a comment-only producer revision changes no verdict"


def test_tc_13_4_4_a_damaged_stored_result_is_rejected_and_computed_again(env, changed, damaged):
    c = damaged["counters"]
    assert c["pairs"]["rejected_objects"] == 1 and c["pairs"]["recomputed"] == 1 and c["pairs"]["reused"] == EXPECTED_PAIRS - 1, c
    bad = next(p for p in damaged["pairs"] if p["pair_key"] == damaged["damaged_key"])
    assert bad["status"] == "RECOMPUTED" and bad["reason"] == "REJECTED"
    conn = env["conn"]
    ev = conn.execute("SELECT subject, payload_json FROM evidence_event WHERE analysis_id=? AND kind='OBJECT_REJECTED'", (damaged["res"].analysis_id,)).fetchall()
    assert [e["subject"] for e in ev] == [damaged["damaged_object"]]
    assert findings(conn, damaged["res"].analysis_id) == findings(conn, changed["res"].analysis_id)
    # the recomputed pair stored a fresh, valid result for the same key
    new = conn.execute("SELECT verdict_id FROM pair_index WHERE pair_key=?", (damaged["damaged_key"],)).fetchone()[0]
    assert new != damaged["damaged_object"]


def test_tc_13_4_5_no_reused_result_is_inside_a_witness(env, damaged):
    conn = env["conn"]
    assert conn.execute("SELECT COUNT(*) FROM oracle_run WHERE provenance='REUSED_RESULT'").fetchone()[0] == 0
    for w in conn.execute("SELECT body_json FROM witness"):
        body = json.loads(w["body_json"])
        ids = list(body["ref_run_ids"]) + list(body["test_run_ids"])
        marks = ",".join("?" for _ in ids)
        rows = conn.execute(f"SELECT provenance FROM oracle_run WHERE id IN ({marks})", ids).fetchall()
        assert len(rows) == len(ids) and all(r["provenance"] == "FRESH_EXECUTION" for r in rows)
        assert len(body["ref_run_ids"]) == 3 and len(body["test_run_ids"]) == 3
