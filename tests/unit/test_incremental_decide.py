"""M13.4: the reuse decision and the counters, on hand-made records (the end-to-end behaviour is in tests/integration/test_incremental.py)."""
import json
from dataclasses import replace

import pytest

from faultline.analysis import incremental
from faultline.evidence import projections
from faultline.evidence.counters import counters, pair_statuses
from faultline.evidence.events import append_event
from faultline.evidence.pair_key import pair_key, record
from faultline.storage.db import connect
from faultline.storage.migrate import migrate
from tests.unit.test_pair_key import base


@pytest.fixture(autouse=True)
def store_on(monkeypatch):
    """These tests are about the evidence store, so they run with it on whatever the suite-wide setting is; the ones about the store being off set it themselves."""
    monkeypatch.setenv("FAULTLINE_EVIDENCE_STORE", "on")


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTLINE_EVIDENCE_DIR", str(tmp_path / "objects"))
    c = connect(tmp_path / "d.db")
    migrate(c)
    c.execute("PRAGMA foreign_keys=OFF")
    return c


def store_pair(conn, inp, *, verdict="BREAK_WITNESSED", with_verdict=True, evidence=None) -> tuple[str, str | None]:
    key = pair_key(inp)
    rec_id, _ = projections.store_object(conn, "pair_record", {"pair_key": key, "inputs": record(inp)})
    vid = None
    if with_verdict:
        row = {"id": "fnd_old", "analysis_id": "an_old", "scope_kind": "ARTIFACT_CELL", "cell_id": "cell_old", "relationship_id": None, "verdict": verdict,
               "sub_label": None, "headline": "h", "scope_json": json.dumps({"consumers": ["x"]}), "coverage": None, "priority": 1, "created_at": "t"}
        vid, _ = projections.store_object(conn, "verdict", {"finding": row, "verdict": verdict, "policy": "verdict-policy/1", "evidence": evidence or []},
                                          slot="finding:cell_old")
    conn.execute("INSERT INTO pair_index(pair_key, pair_record_id, verdict_id, created_at) VALUES (?,?,?,?)", (key, rec_id, vid, "2026-01-01T00:00:00Z"))
    return key, vid


def test_a_verified_stored_result_is_reused(conn):
    inp = base()
    key, vid = store_pair(conn, inp)
    d = incremental.decide(conn, key, record(inp), "cell_new", "an_new")
    assert isinstance(d, incremental.Reuse) and d.verdict_id == vid and d.key == key
    assert not conn.execute("SELECT 1 FROM evidence_event WHERE kind='OBJECT_REJECTED'").fetchone()


def test_no_stored_result_means_a_new_computation(conn):
    inp = base()
    d = incremental.decide(conn, pair_key(inp), record(inp), "c", "a")
    assert isinstance(d, incremental.Recompute) and d.reason == "NEW" and d.changed == []


def test_a_pair_stored_without_a_verdict_is_not_reused(conn):
    inp = base()
    key, _ = store_pair(conn, inp, with_verdict=False)
    assert incremental.decide(conn, key, record(inp), "c", "a").reason == "NEW"


def test_an_inconclusive_result_is_never_reused(conn):
    inp = base()
    key, _ = store_pair(conn, inp, verdict="INCONCLUSIVE")
    d = incremental.decide(conn, key, record(inp), "c", "a")
    assert isinstance(d, incremental.Recompute) and d.reason == "REJECTED" and "INCONCLUSIVE" in d.rejected["problem"]


def test_a_damaged_verdict_is_rejected_and_reported(conn, tmp_path):
    inp = base()
    key, vid = store_pair(conn, inp)
    f = tmp_path / "objects" / vid[:2] / f"{vid}.json"
    raw = bytearray(f.read_bytes())
    raw[len(raw) // 2] ^= 1
    f.write_bytes(bytes(raw))
    d = incremental.decide(conn, key, record(inp), "cell_new", "an_new")
    assert isinstance(d, incremental.Recompute) and d.reason == "REJECTED" and "corrupt" in d.rejected["problem"]
    ev = conn.execute("SELECT subject, analysis_id, payload_json FROM evidence_event WHERE kind='OBJECT_REJECTED'").fetchall()
    assert [(e["subject"], e["analysis_id"]) for e in ev] == [(vid, "an_new")] and json.loads(ev[0]["payload_json"])["pair_key"] == key


def test_a_missing_pair_record_is_rejected(conn, tmp_path):
    inp = base()
    key, _ = store_pair(conn, inp)
    rid = conn.execute("SELECT pair_record_id FROM pair_index").fetchone()[0]
    (tmp_path / "objects" / rid[:2] / f"{rid}.json").unlink()
    d = incremental.decide(conn, key, record(inp), "c", "a")
    assert d.reason == "REJECTED" and "pair record" in d.rejected["problem"]


def test_a_cited_witness_that_is_missing_rejects_the_result(conn):
    inp = base()
    key, _ = store_pair(conn, inp, evidence=[["WITNESS", "wit_gone"]])
    d = incremental.decide(conn, key, record(inp), "c", "a")
    assert d.reason == "REJECTED" and "wit_gone" in d.rejected["problem"]


def test_a_changed_input_is_computed_again_and_the_change_is_named(conn):
    old = base()
    store_pair(conn, old)
    new = replace(old, producer=replace(old.producer, commit="9" * 40), producer_artifact_sha256="a_" + "7" * 40)
    d = incremental.decide(conn, pair_key(new), record(new), "c", "a")
    assert isinstance(d, incremental.Recompute) and d.reason == "CHANGED"
    assert [c["input"] for c in d.changed] == ["producer.commit", "producer_artifact_sha256"]
    assert d.changed[0]["before"] == "a" * 40 and d.changed[0]["after"] == "9" * 40


def test_another_repository_is_not_the_baseline(conn):
    store_pair(conn, base())
    other = replace(base(), producer=replace(base().producer, repo="acme/unrelated"))
    d = incremental.decide(conn, pair_key(other), record(other), "c", "a")
    assert d.reason == "NEW" and d.changed == []


def test_the_store_off_means_nothing_is_reused(conn, monkeypatch):
    inp = base()
    key, _ = store_pair(conn, inp)
    monkeypatch.setenv("FAULTLINE_EVIDENCE_STORE", "off")
    assert incremental.decide(conn, key, record(inp), "c", "a").reason == "NEW"


def test_counters_come_from_events_and_an_unfinished_pair_is_not_counted_as_done(conn):
    for kind, cell, extra in (("PAIR_REUSED", "c1", {"from_analysis": "an0", "verdict": "BREAK_WITNESSED"}),
                              ("PAIR_RECOMPUTE_STARTED", "c2", {"reason": "CHANGED", "changed": ["producer.commit"], "detail": []}),
                              ("PAIR_RECOMPUTE_DONE", "c2", {"state": "ANALYZED", "verdict": "BREAK_WITNESSED"}),
                              ("PAIR_RECOMPUTE_STARTED", "c3", {"reason": "NEW", "changed": [], "detail": []}),          # started and never finished
                              ("OBJECT_REJECTED", "c4", {}), ("WORLD_REUSED", None, {}), ("WORLD_BUILT", None, {}), ("WORLD_BUILT", None, {})):
        append_event(conn, kind, analysis_id="an1", subject=f"key_{cell}", payload={"cell_id": cell, **extra})
    append_event(conn, "PAIR_REUSED", analysis_id="an_other", subject="k", payload={"cell_id": "cx"})
    c = counters(conn, "an1")
    assert c["pairs"] == {"reused": 1, "recomputed": 1, "unfinished": 1, "rejected_objects": 1}
    assert c["worlds"] == {"reused": 1, "built": 2} and c["events"] == 8
    rows = {p["cell_id"]: p for p in pair_statuses(conn, "an1")}
    assert {k: (v["status"], v["reason"]) for k, v in rows.items()} == {"c1": ("REUSED", "REUSED"), "c2": ("RECOMPUTED", "CHANGED"), "c3": ("UNFINISHED", "NEW")}
    assert rows["c2"]["changed"] == ["producer.commit"]


def test_reuse_can_be_switched_off_and_every_pair_is_computed_again(conn, monkeypatch):
    """FAULTLINE_REUSE=off forces a recomputation even when a verified stored result exists (used by tests that need a verification to be running)."""
    monkeypatch.setenv("FAULTLINE_REUSE", "off")
    d = incremental.decide(conn, "pk_any", {"producer": {"repo": "a", "project": "p"}, "consumers": []}, "cell_x", "an_x")
    assert isinstance(d, incremental.Recompute) and d.reason == "FORCED"
