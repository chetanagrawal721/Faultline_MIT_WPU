"""Rebuild the evidence rows of the SQL tables from the immutable objects (ADR 0008, methodology 5.3).

Reads objects, writes only projection rows. An object file is never deleted, rewritten or moved. The whole rebuild is one transaction: a
failure, a refusal or a dry run rolls it back and leaves the previous tables untouched.

  1. discover   every object is read and verified; corrupt or unsupported ones are reported and skipped (an OBJECT_REJECTED event each)
  2. choose     for a slot the object with the highest seq is current; objects without a slot (runs) are all applied
  3. apply      the same `apply_*` functions the live writers use, in dependency order, each inside a savepoint; a row whose parent is
                missing is skipped and reported
  4. pointers   the pointer table and object_index are recomputed from the objects
  5. verify     the normalised dump of the evidence tables must equal the dump taken before; rows that have no object are never lost silently
"""
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime

from . import projections
from .dump import dump_evidence
from .events import append_event
from .object_store import FsObjectStore
from .runtime import objects_dir
from .store import Status


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _count(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in projections.RESULT_TABLES}


def rebuild(conn: sqlite3.Connection, *, dry_run: bool = False, allow_loss: bool = False) -> dict:
    store = FsObjectStore(objects_dir(conn))
    report: dict = {"objects": {}, "rejected": [], "skipped": [], "applied": {}, "dry_run": dry_run, "status": "STARTED"}

    # 1. discover
    good: list[tuple[str, str, dict]] = []                             # (id, kind, payload)
    for oid, status in store.iter_objects():
        if status is Status.OK:
            r = store.get(oid)
            good.append((oid, r.kind, r.payload))
            report["objects"][r.kind] = report["objects"].get(r.kind, 0) + 1
        else:
            report["rejected"].append({"object_id": oid, "status": status.value})

    # 2. choose the current object of every slot
    current: dict[str, tuple[int, str, str, dict]] = {}
    unslotted: list[tuple[str, str, dict]] = []
    for oid, kind, payload in good:
        slot, seq = payload.get("slot"), payload.get("seq")
        if slot is None:
            unslotted.append((oid, kind, payload))
        elif slot not in current or (seq, oid) > (current[slot][0], current[slot][1]):
            current[slot] = (seq, oid, kind, payload)
    chosen = defaultdict(list)
    for oid, kind, payload in unslotted:
        chosen[kind].append((oid, payload))
    for _slot, (_seq, oid, kind, payload) in sorted(current.items()):
        chosen[kind].append((oid, payload))

    before_count = _count(conn)
    before = dump_evidence(conn)
    old_index = {r["object_id"]: r["created_at"] for r in conn.execute("SELECT object_id, created_at FROM object_index")}

    conn.execute("BEGIN IMMEDIATE")
    try:
        for t in projections.RESULT_TABLES:
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM pointer")
        conn.execute("DELETE FROM object_index")
        # 3. apply in dependency order
        for kind in projections.REBUILD_ORDER:
            n = 0
            for oid, payload in sorted(chosen.get(kind, []), key=lambda x: (x[1].get("seq") or 0, x[0])):
                conn.execute("SAVEPOINT obj")
                try:
                    projections.APPLY[kind](conn, payload)
                    conn.execute("RELEASE obj")
                    n += 1
                except sqlite3.IntegrityError as e:
                    conn.execute("ROLLBACK TO obj")
                    conn.execute("RELEASE obj")
                    report["skipped"].append({"object_id": oid, "kind": kind, "reason": f"a referenced row is missing ({e})"})
            report["applied"][kind] = n
        # 4. index and pointers
        for oid, kind, payload in good:
            conn.execute("INSERT OR IGNORE INTO object_index(object_id, kind, schema_version, slot, seq, created_at) VALUES (?,?,?,?,?,?)",
                         (oid, kind, 1, payload.get("slot"), payload.get("seq"), old_index.get(oid) or _now()))
        for slot, (seq, oid, _kind, _payload) in current.items():
            conn.execute("INSERT INTO pointer(slot, object_id, seq, moved_at) VALUES (?,?,?,?)", (slot, oid, seq, _now()))
        # 5. verify
        after_count = _count(conn)
        after = dump_evidence(conn)
        report["rows_before"], report["rows_after"] = before_count, after_count
        report["identical"] = before == after
        lost = {t: before_count[t] - after_count[t] for t in before_count if after_count[t] < before_count[t]}
        if lost and not allow_loss:
            report["status"] = "REFUSED"
            report["reason"] = f"rows without an object would be lost: {lost}"
        elif not report["identical"] and not allow_loss:
            report["status"] = "REFUSED"
            report["reason"] = "the rebuilt tables do not say the same as the tables before"
        elif dry_run:
            report["status"] = "DRY_RUN_OK"
        else:
            report["status"] = "REBUILT"
        if report["status"] == "REBUILT":
            conn.execute("COMMIT")
        else:
            conn.execute("ROLLBACK")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    if not dry_run:
        for r in report["rejected"]:
            append_event(conn, "OBJECT_REJECTED", subject=r["object_id"], payload={"status": r["status"], "during": "rebuild"})
        append_event(conn, "REBUILD_DONE", payload={"status": report["status"], "applied": report["applied"], "rejected": len(report["rejected"]),
                                                    "skipped": len(report["skipped"])})
    return report
