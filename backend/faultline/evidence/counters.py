"""Reused, recomputed and rejected counters and the per-pair reasons, computed from the event log and nothing else (ADR 0008).

A pair counts as recomputed only when it finished (PAIR_RECOMPUTE_DONE); one that started and was stopped is reported separately as unfinished,
so a crash can never inflate a completion count.
"""
import sqlite3

from .events import list_events


def counters(conn: sqlite3.Connection, analysis_id: str) -> dict:
    ev = list_events(conn, analysis_id=analysis_id)

    def n(kind: str) -> int:
        return sum(1 for e in ev if e["kind"] == kind)
    started, done = n("PAIR_RECOMPUTE_STARTED"), n("PAIR_RECOMPUTE_DONE")
    return {"analysis_id": analysis_id,
            "pairs": {"reused": n("PAIR_REUSED"), "recomputed": done, "unfinished": max(0, started - done), "rejected_objects": n("OBJECT_REJECTED")},
            "worlds": {"reused": n("WORLD_REUSED"), "built": n("WORLD_BUILT")},
            "ddmin": {"tests_resumed": n("DDMIN_TEST_RESUMED"), "tests_run": n("DDMIN_ATTEMPT_FINISHED")},
            "events": len(ev)}


def pair_statuses(conn: sqlite3.Connection, analysis_id: str) -> list[dict]:
    """One row per pair that was run or reused in this analysis, with the reason, taken from its events."""
    rows: dict[str, dict] = {}
    for e in list_events(conn, analysis_id=analysis_id):
        p = e["payload"]
        if e["kind"] == "PAIR_REUSED":
            rows[p["cell_id"]] = {"cell_id": p["cell_id"], "pair_key": e["subject"], "status": "REUSED", "reason": "REUSED", "changed": [], "detail": [],
                                  "from_analysis": p.get("from_analysis"), "verdict": p.get("verdict")}
        elif e["kind"] == "PAIR_RECOMPUTE_STARTED":
            rows[p["cell_id"]] = {"cell_id": p["cell_id"], "pair_key": e["subject"], "status": "UNFINISHED", "reason": p["reason"], "changed": p.get("changed", []),
                                  "detail": p.get("detail", []), "from_analysis": None, "verdict": None}
        elif e["kind"] == "PAIR_RECOMPUTE_DONE" and p["cell_id"] in rows:
            rows[p["cell_id"]].update(status="RECOMPUTED", verdict=p.get("verdict"))
    return sorted(rows.values(), key=lambda r: r["cell_id"])
