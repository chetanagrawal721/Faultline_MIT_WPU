"""M13.11 (TC-13.11.3): the same pinned inputs give the same findings, witnesses, attribution and remediation with the evidence store off and on.

Two real analyses of scenario D, one per setting, from identical pinned repositories. The normalised dumps (no ids, no timestamps) must be equal, and so must
the verified fix the remediation proposes for the break. This is the guard that the move to objects changed nothing a user of the SQL tables can see.
"""
import os

import pytest

from faultline.evidence.dump import dump_evidence
from faultline.remediation.minimal import remediate
from tests.integration.test_evidence_projection import analyse_scenario_d

pytestmark = [pytest.mark.docker, pytest.mark.slow]


def run(daemon, image, tmp_path, setting: str):
    from faultline.sandbox.client import SandboxClient
    from tests.conftest import TOKEN
    os.environ["FAULTLINE_EVIDENCE_STORE"] = setting
    try:
        conn, res = analyse_scenario_d(daemon, image, tmp_path, tag=f"par{setting}")
        dump = dump_evidence(conn, res.analysis_id)
        sbx = SandboxClient(port=daemon.port, token=TOKEN, timeout=900)
        broken = conn.execute("SELECT id FROM finding WHERE analysis_id=? AND verdict='BREAK_WITNESSED' AND headline LIKE '%notify-svc%'", (res.analysis_id,)).fetchone()
        assert broken is not None, "scenario D breaks the consumer"
        fix = remediate(conn, sbx, image, daemon.store, broken["id"])
        return dump, (fix.label, fix.constraint, getattr(fix, "kind", None), getattr(fix, "target_path", None)), conn
    finally:
        del os.environ["FAULTLINE_EVIDENCE_STORE"]


def test_tc_13_11_3_store_off_and_on_give_identical_findings_witnesses_attribution_and_fix(daemon, image, tmp_path_factory):
    on_dump, on_fix, on_conn = run(daemon, image, tmp_path_factory.mktemp("parity_on"), "on")
    off_dump, off_fix, off_conn = run(daemon, image, tmp_path_factory.mktemp("parity_off"), "off")
    assert on_dump["findings"] and on_dump["witnesses"] and on_dump["attributions"], "the comparison is made on real evidence"
    for part in ("findings", "witnesses", "attributions", "runs"):
        assert on_dump[part] == off_dump[part], f"{part} differ between the store on and off"
    assert on_dump == off_dump
    assert on_fix == off_fix and on_fix[0] == "VERIFIED", on_fix
    n_on = on_conn.execute("SELECT COUNT(*) FROM pointer").fetchone()[0]
    n_off = off_conn.execute("SELECT COUNT(*) FROM pointer").fetchone()[0]
    assert n_on > 0 and n_off == 0, "only the run with the store on keeps objects and pointers"
