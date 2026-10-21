"""M13.0: the audit record, ADR 0008 and the Phase 13 registration are complete and match the code."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = (ROOT / "docs" / "INCREMENTAL_WITNESS_AUDIT.md").read_text(encoding="utf-8")
ADR = (ROOT / "docs" / "adr" / "0008-incremental-witness.md").read_text(encoding="utf-8")
RESULT_TABLES = "witness|attribution|attribution_attempt|finding|finding_evidence|remediation_plan|oracle_job|oracle_run|evidence_bundle"
WRITER = re.compile(rf"(INSERT\s+(?:OR\s+\w+\s+)?INTO|DELETE\s+FROM|UPDATE)\s+({RESULT_TABLES})\b", re.IGNORECASE)
VERDICT_WORDS = ["BREAK WITNESSED", "SILENT DIVERGENCE WITNESSED", "NO DIVERGENCE OBSERVED", "EXPOSED", "POTENTIAL", "NOT EXPOSED", "INCONCLUSIVE", "HYGIENE"]


def test_every_baseline_row_has_a_result():
    rows = [ln for ln in AUDIT.splitlines() if re.match(r"\| B\d+ \|", ln)]
    assert len(rows) >= 13
    for ln in rows:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        assert cells[2].split(",")[0] in {"confirmed", "corrected", "not found"}, ln
        assert cells[3], f"empty detail: {ln}"


def test_every_result_table_writer_is_listed():
    base = ROOT / "backend" / "faultline"
    writers = sorted({p.relative_to(base).as_posix() for p in base.rglob("*.py") if WRITER.search(p.read_text(encoding="utf-8"))})
    assert writers, "the search found no writers; the pattern is wrong"
    missing = [w for w in writers if f"`{w}`" not in AUDIT]
    assert not missing, f"result-table writers missing from the audit: {missing}"


def test_adr_has_the_frozen_decisions():
    for word in VERDICT_WORDS:
        assert f"| {word} |" in ADR, f"severity row missing for {word}"
    for needle in ("pair_key", "PairKeyInput", "ddmin_checkpoint", "minimisation_id", "test_id", "JOB_CANCELLED", "POINTER_MOVED",
                   "$/cancelRequest", "SandboxClient.cancel", "pygls==2.1.1", "lsprotocol==2025.0.0", "Differences from the master"):
        assert needle in ADR, needle


def test_phase13_is_registered():
    spec = importlib.util.spec_from_file_location("track", ROOT / "tools" / "track.py")
    track = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(track)
    meta, miles, tcs, exits = track.load_plan()
    assert [f"M13.{i}" for i in range(13)] == sorted((m for m in miles if m.startswith("M13.")), key=track.sort_key)
    for g in ("A", "B", "C", "D", "E", "S", "X", "T1", "T2", "T3", "T4", "T5", "T6"):
        assert g in meta["gates"], g
    assert meta["phases"][13]["gate"] == "T6"
    assert {"T1", "T2", "T3", "T4", "T5", "T6"} <= set(exits)
    assert sum(1 for t in tcs if t.startswith("TC-13.")) == 69
