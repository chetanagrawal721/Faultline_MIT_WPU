"""The only code that writes the evidence rows of the SQL tables (ADR 0008).

Evidence of record is the immutable object. A writer builds the payload, `write()` stores the object (when the store is on) and then calls the
matching `apply_*`, which makes the SQL rows say what the object says. `rebuild` calls the same `apply_*` functions, so a rebuilt table cannot
differ from a live one. A row changes only to follow a pointer move; no other code updates or deletes these rows.
"""
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .events import append_event
from .runtime import store_for

RESULT_TABLES = ("remediation_plan", "finding_evidence", "finding", "attribution_attempt", "attribution", "witness", "oracle_run")   # delete order


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _insert(conn: sqlite3.Connection, table: str, row: dict, *, conflict: str = "") -> None:
    cols = list(row)
    conn.execute(f"INSERT INTO {table}({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) {conflict}", [row[c] for c in cols])


def _upsert(conn: sqlite3.Connection, table: str, row: dict, key: str = "id") -> None:
    sets = ", ".join(f"{c}=excluded.{c}" for c in row if c != key)
    _insert(conn, table, row, conflict=f"ON CONFLICT({key}) DO UPDATE SET {sets}")


# ---- slots, objects and pointers -------------------------------------------------------------------------------------

def next_seq(conn: sqlite3.Connection, slot: str) -> int:
    r = conn.execute("SELECT seq FROM pointer WHERE slot=?", (slot,)).fetchone()
    top = r["seq"] if r else (conn.execute("SELECT MAX(seq) FROM object_index WHERE slot=?", (slot,)).fetchone()[0] or 0)
    return top + 1


def move_pointer(conn: sqlite3.Connection, slot: str, object_id: str, seq: int, analysis_id: str | None = None) -> None:
    conn.execute("INSERT INTO pointer(slot, object_id, seq, moved_at) VALUES (?,?,?,?) "
                 "ON CONFLICT(slot) DO UPDATE SET object_id=excluded.object_id, seq=excluded.seq, moved_at=excluded.moved_at", (slot, object_id, seq, _now()))
    append_event(conn, "POINTER_MOVED", analysis_id=analysis_id, subject=slot, payload={"object_id": object_id, "seq": seq})


def store_object(conn: sqlite3.Connection, kind: str, payload: dict, *, slot: str | None = None, analysis_id: str | None = None) -> tuple[str | None, dict]:
    """Store one object (a new version when it has a slot). Returns (object id or None when the store is off, the payload as stored)."""
    st = store_for(conn)
    seq = next_seq(conn, slot) if slot else None
    full = {**payload, "slot": slot, "seq": seq} if slot else payload
    if st is None:
        return None, full
    oid = st.put(kind, full)
    conn.execute("INSERT OR IGNORE INTO object_index(object_id, kind, schema_version, slot, seq, created_at) VALUES (?,?,?,?,?,?)",
                 (oid, kind, 1, slot, seq, _now()))
    if slot:
        move_pointer(conn, slot, oid, seq, analysis_id)
    return oid, full


def write(conn: sqlite3.Connection, kind: str, payload: dict, *, slot: str | None = None, analysis_id: str | None = None) -> str | None:
    """Store the object, then make the SQL rows follow it."""
    oid, full = store_object(conn, kind, payload, slot=slot, analysis_id=analysis_id)
    APPLY[kind](conn, full)
    return oid


# ---- one apply per kind: the SQL rows that follow an object ------------------------------------------------------------

def apply_oracle_result(conn: sqlite3.Connection, p: dict) -> None:
    if p.get("job"):
        _insert(conn, "oracle_job", p["job"], conflict="ON CONFLICT(id) DO NOTHING")            # the job row exists while the run is live; a rebuild may need it back
    _insert(conn, "oracle_run", p["run"], conflict="ON CONFLICT(id) DO NOTHING")


def apply_witness(conn: sqlite3.Connection, p: dict) -> None:
    _upsert(conn, "witness", p["row"])


def apply_verdict(conn: sqlite3.Connection, p: dict) -> None:
    row = p["finding"]
    if row.get("cell_id"):                                   # a new finding for a cell replaces the previous one for that cell
        old = [r["id"] for r in conn.execute("SELECT id FROM finding WHERE cell_id=? AND id<>?", (row["cell_id"], row["id"]))]
        for fid in old:
            conn.execute("DELETE FROM finding_evidence WHERE finding_id=?", (fid,))
            conn.execute("DELETE FROM finding WHERE id=?", (fid,))
    _upsert(conn, "finding", row)
    conn.execute("DELETE FROM finding_evidence WHERE finding_id=?", (row["id"],))
    for kind, eid in p["evidence"]:
        conn.execute("INSERT OR IGNORE INTO finding_evidence(finding_id, evidence_kind, evidence_id) VALUES (?,?,?)", (row["id"], kind, eid))


def apply_attribution(conn: sqlite3.Connection, p: dict) -> None:
    row = p["row"]
    conn.execute("DELETE FROM attribution_attempt WHERE attribution_id IN (SELECT id FROM attribution WHERE witness_id=?)", (row["witness_id"],))
    conn.execute("DELETE FROM attribution WHERE witness_id=?", (row["witness_id"],))
    _insert(conn, "attribution", row)
    for att in p["attempts"]:
        _insert(conn, "attribution_attempt", att)


def apply_fix_plan(conn: sqlite3.Connection, p: dict) -> None:
    row = p["row"]
    if p.get("diff") is not None and row.get("diff_path"):
        d = Path(row["diff_path"])
        if not d.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_text(p["diff"], encoding="utf-8", newline="\n")
    conn.execute("DELETE FROM remediation_plan WHERE id=?", (row["id"],))
    _insert(conn, "remediation_plan", row)


def apply_other(conn: sqlite3.Connection, p: dict) -> None:
    """Kinds with no SQL rows of their own (pair records, checkpoints, world references) are indexed only."""


APPLY = {"oracle_result": apply_oracle_result, "witness": apply_witness, "verdict": apply_verdict, "attribution": apply_attribution,
         "fix_plan": apply_fix_plan, "pair_record": apply_other, "ddmin_checkpoint": apply_other, "ddmin_test": apply_other, "consumer_imports": apply_other, "world_ref": apply_other}

# the order a rebuild applies kinds in, so a row never refers to one that does not exist yet
REBUILD_ORDER = ("oracle_result", "witness", "attribution", "verdict", "fix_plan")


def row_of(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in r.keys()}


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True)
