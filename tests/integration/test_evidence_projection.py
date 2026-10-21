"""M13.2: the evidence tables say the same thing before and after the move to objects and projections.

The golden file was recorded from the code as it was before M13.2 (FAULTLINE_WRITE_GOLDEN=1 on the unchanged tree). Every later run, with the
evidence store on or off, must produce the same normalised dump.
"""
import json
import os
from pathlib import Path

import pytest

from faultline.analysis.live import run_live_analysis
from faultline.evidence.dump import dump_evidence
from tests.liveenv import ingest_all
from tests.livefix import fixture_repo

pytestmark = pytest.mark.docker

GOLDEN = Path(__file__).resolve().parents[1] / "data" / "golden_evidence_scenario_d.json"


def analyse_scenario_d(daemon, image, tmp: Path):
    from faultline.sandbox.client import SandboxClient
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    from tests.conftest import TOKEN
    conn = connect(tmp / "t.db")
    migrate(conn)
    sbx = SandboxClient(port=daemon.port, token=TOKEN, timeout=600)
    apid, _ = ingest_all(conn, sbx, image, daemon.store, {
        "rm_ev_prod": ("faultline-demo/acme-models", fixture_repo("acme-models")),
        "rm_ev_notify": ("faultline-demo/notify-svc", fixture_repo("notify-svc/D")),
        "rm_ev_orders": ("faultline-demo/orders-svc", fixture_repo("orders-svc/D"))})
    return conn, run_live_analysis(conn, sbx, image, daemon.store, apid)


@pytest.fixture(scope="module")
def analysed(daemon, image, tmp_path_factory):
    return analyse_scenario_d(daemon, image, tmp_path_factory.mktemp("evidence_d"))


def test_tc_13_2_3_the_evidence_tables_match_the_golden_recording(analysed):
    conn, res = analysed
    got = json.loads(json.dumps(dump_evidence(conn, res.analysis_id), sort_keys=True))
    if os.environ.get("FAULTLINE_WRITE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("golden recording written")
    assert got == json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert got["findings"] and got["witnesses"] and got["attributions"], "the recording must contain real evidence"


def test_every_evidence_row_has_an_object_and_a_pointer(analysed):
    from faultline.evidence.object_store import FsObjectStore
    from faultline.evidence.runtime import objects_dir
    conn, res = analysed
    st = FsObjectStore(objects_dir(conn))
    by_kind: dict[str, int] = {}
    for oid, status in st.iter_objects():
        assert status.value == "OK", oid
        by_kind[st.get(oid).kind] = by_kind.get(st.get(oid).kind, 0) + 1
    rows = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("oracle_run", "witness", "finding", "attribution")}
    assert by_kind == {"oracle_result": rows["oracle_run"], "witness": rows["witness"], "verdict": rows["finding"], "attribution": rows["attribution"]}
    assert rows["oracle_run"] == 12 and rows["witness"] == 2
    slots = {r["slot"] for r in conn.execute("SELECT slot FROM pointer")}
    assert len(slots) == rows["witness"] + rows["finding"] + rows["attribution"]
    moved = conn.execute("SELECT COUNT(*) FROM evidence_event WHERE kind='POINTER_MOVED'").fetchone()[0]
    assert moved >= len(slots)


def test_with_the_store_off_the_tables_are_the_same(daemon, image, tmp_path):
    os.environ["FAULTLINE_EVIDENCE_STORE"] = "off"
    try:
        conn, res = analyse_scenario_d(daemon, image, tmp_path)
    finally:
        del os.environ["FAULTLINE_EVIDENCE_STORE"]
    got = json.loads(json.dumps(dump_evidence(conn, res.analysis_id), sort_keys=True))
    (tmp_path / "got.json").write_text(json.dumps(got, indent=1, sort_keys=True), encoding="utf-8")
    assert got == json.loads(GOLDEN.read_text(encoding="utf-8")), f"differs; see {tmp_path / 'got.json'}"
    assert conn.execute("SELECT COUNT(*) FROM object_index").fetchone()[0] == 0 and conn.execute("SELECT COUNT(*) FROM pointer").fetchone()[0] == 0
