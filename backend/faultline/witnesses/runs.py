"""Executes oracle runs and records them. This is where 'fresh' versus 'reused' is decided.

Only FRESH_EXECUTION records may count toward a witness. A cache hit creates a NEW record marked REUSED_RESULT that
points at the original job, so the history shows exactly which runs really executed.
"""
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass

from ..analysis.fixture import FixtureCell
from ..core.enums import RunProvenance
from ..core.hashing import object_hash
from ..core.ids import new_id
from ..core.models import OracleRunResult
from ..evidence import projections

NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())  # noqa: E731


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    job_id: str
    run_index: int
    side: str                      # "ref" or "test"
    world_hash: str
    provenance: RunProvenance
    result: OracleRunResult

    @property
    def fresh(self) -> bool:
        return self.provenance == RunProvenance.FRESH_EXECUTION


def cache_key(oracle: str, version: str, world_hash: str, artifact_hash: str, args: dict, run_index: int) -> str:
    return object_hash({"oracle": oracle, "version": version, "world": world_hash, "artifact": artifact_hash,
                        "args": args, "run_index": run_index})


def _fingerprint(result: OracleRunResult, world_hash: str) -> str:
    return object_hash({"world": world_hash, "python": (result.data or {}).get("python")})[:16]


def execute_run(conn: sqlite3.Connection, cell: FixtureCell, *, oracle: str, version: str, side: str, world_hash: str,
                run_index: int, args: dict, runner: Callable[[], OracleRunResult], force: bool = False) -> RunRecord:
    key = cache_key(oracle, version, world_hash, cell.artifact_hash, args, run_index)
    cached = conn.execute(
        "SELECT j.id AS job_id, r.result_json FROM oracle_job j JOIN oracle_run r ON r.oracle_job_id = j.id "
        "WHERE j.cache_key = ? AND r.provenance = 'FRESH_EXECUTION' ORDER BY r.created_at LIMIT 1", (key,)).fetchone()
    if cached and not force:
        original = OracleRunResult.model_validate_json(cached["result_json"])
        record_id = new_id("run")
        result = original.model_copy(update={"run_id": record_id, "provenance": RunProvenance.REUSED_RESULT})
        projections.write(conn, "oracle_result", {
            "oracle": oracle, "oracle_version": version, "world_hash": world_hash, "job": None,
            "run": {"id": record_id, "oracle_job_id": cached["job_id"], "run_index": run_index, "provenance": RunProvenance.REUSED_RESULT.value,
                    "created_at": NOW(), "env_fingerprint": _fingerprint(result, world_hash), "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms, "failure_class": result.failure_class.value, "result_json": result.model_dump_json()}},
            analysis_id=cell.analysis_id)
        return RunRecord(record_id, cached["job_id"], run_index, side, world_hash, RunProvenance.REUSED_RESULT, result)

    # a forced re-execution of an already cached key needs its own unique cache_key
    existing = conn.execute("SELECT COUNT(*) FROM oracle_job WHERE cache_key = ? OR cache_key LIKE ?",
                            (key, key + "#%")).fetchone()[0]
    job_key = key if existing == 0 else f"{key}#{existing}"
    job_id = new_id("oj")
    started = NOW()
    conn.execute("INSERT INTO oracle_job(id, analysis_id, cell_id, oracle, oracle_version, world_hash, side, spec_json, "
                 "cache_key, status, queued_at, started_at) VALUES (?,?,?,?,?,?,?,?,?, 'RUNNING', ?, ?)",
                 (job_id, cell.analysis_id, cell.cell_id, oracle, version, world_hash, side,
                  json.dumps(args, sort_keys=True), job_key, started, started))
    result = runner()
    finished = NOW()
    projections.write(conn, "oracle_result", {
        "oracle": oracle, "oracle_version": version, "world_hash": world_hash,
        "job": {"id": job_id, "analysis_id": cell.analysis_id, "cell_id": cell.cell_id, "oracle": oracle, "oracle_version": version, "world_hash": world_hash,
                "side": side, "spec_json": json.dumps(args, sort_keys=True), "cache_key": job_key, "status": "DONE", "queued_at": started, "started_at": started,
                "finished_at": finished},
        "run": {"id": result.run_id, "oracle_job_id": job_id, "run_index": run_index, "provenance": RunProvenance.FRESH_EXECUTION.value, "created_at": finished,
                "env_fingerprint": _fingerprint(result, world_hash), "exit_code": result.exit_code, "duration_ms": result.duration_ms,
                "failure_class": result.failure_class.value, "result_json": result.model_dump_json()}},
        analysis_id=cell.analysis_id)
    conn.execute("UPDATE oracle_job SET status='DONE', finished_at=? WHERE id=?", (finished, job_id))
    return RunRecord(result.run_id, job_id, run_index, side, world_hash, RunProvenance.FRESH_EXECUTION, result)
