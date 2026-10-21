"""The append-only event log (ADR 0008). Counters, the UI and the rebuild report read events; nothing edits them."""
import json
import sqlite3
from datetime import UTC, datetime

JOB_EVENTS = ("JOB_QUEUED", "JOB_CLAIMED", "JOB_RETRIED", "JOB_CANCEL_REQUESTED", "JOB_CANCELLED", "JOB_DONE", "JOB_FAILED")
EVENT_KINDS = frozenset({
    *JOB_EVENTS,                                                  # written by database triggers on the job table
    "PAIR_REUSED", "PAIR_RECOMPUTE_STARTED", "PAIR_RECOMPUTE_DONE", "OBJECT_REJECTED", "WORLD_REUSED", "WORLD_BUILT",
    "DDMIN_ATTEMPT_STARTED", "DDMIN_ATTEMPT_FINISHED", "DDMIN_ATTEMPT_INTERRUPTED", "DDMIN_CHECKPOINT",
    "POINTER_MOVED", "REBUILD_STARTED", "REBUILD_DONE",
})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def append_event(conn: sqlite3.Connection, kind: str, *, analysis_id: str | None = None, job_id: str | None = None,
                 subject: str | None = None, payload: dict | None = None) -> int:
    if kind not in EVENT_KINDS:
        raise ValueError(f"unknown event kind {kind!r}")
    cur = conn.execute("INSERT INTO evidence_event(at, analysis_id, job_id, kind, subject, payload_json) VALUES (?,?,?,?,?,?)",
                       (_now(), analysis_id, job_id, kind, subject, json.dumps(payload or {}, sort_keys=True)))
    return int(cur.lastrowid)


def list_events(conn: sqlite3.Connection, *, kind: str | None = None, analysis_id: str | None = None, job_id: str | None = None,
                subject: str | None = None) -> list[dict]:
    where, params = [], []
    for col, val in (("kind", kind), ("analysis_id", analysis_id), ("job_id", job_id), ("subject", subject)):
        if val is not None:
            where.append(f"{col}=?")
            params.append(val)
    sql = "SELECT * FROM evidence_event" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id"
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in conn.execute(sql, params)]
