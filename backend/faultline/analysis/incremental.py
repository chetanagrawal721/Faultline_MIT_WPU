"""Reuse of a stored pair result when the pair key matches, and recomputation of only what changed (ADR 0008, decision 3).

A reused pair is labelled as reused everywhere (its finding says where it came from) and no oracle runs for it, so none of its runs is ever
counted as a fresh run of anything. A stored result is used only if the verdict, the pair record and every witness it cites verify; if one does
not, it is rejected (an OBJECT_REJECTED event) and the pair is computed again.
"""
import json
import sqlite3
from dataclasses import dataclass, field

from ..core.ids import new_id
from ..evidence import projections
from ..evidence.events import append_event
from ..evidence.pair_key import explain
from ..evidence.runtime import store_for
from ..verdicts.engine import LIVE_POLICY_VERSION

NOT_REUSED_VERDICTS = {"INCONCLUSIVE"}               # an inconclusive result may be an infrastructure problem; it is never stored as reusable


@dataclass
class Reuse:
    key: str
    verdict_id: str
    payload: dict
    old_state: str


@dataclass
class Recompute:
    reason: str                                      # NEW (no stored result), CHANGED (an earlier pair of these repositories had other inputs), REJECTED
    changed: list[dict] = field(default_factory=list)
    rejected: dict | None = None


def _verify(conn: sqlite3.Connection, st, row: sqlite3.Row, key: str) -> tuple[str | None, dict | None]:
    """(problem, verdict payload). No problem means every stored object the result stands on verified."""
    v = st.get(row["verdict_id"])
    if not v.ok or v.kind != "verdict":
        return f"the stored verdict is {v.status.value.lower()}", None
    rec = st.get(row["pair_record_id"]) if row["pair_record_id"] else None
    if rec is None or not rec.ok or rec.payload.get("pair_key") != key:
        return "the stored pair record is missing or does not match its key", None
    finding = v.payload["finding"]
    if finding["verdict"] in NOT_REUSED_VERDICTS:
        return f"a {finding['verdict']} result is not reused", None
    for kind, eid in v.payload["evidence"]:
        if kind == "WITNESS":
            w = conn.execute("SELECT witness_key FROM witness WHERE id=?", (eid,)).fetchone()
            if w is None:
                return f"witness {eid} is missing from the result tables", None
            for slot in (f"witness:{w['witness_key']}", f"attribution:{w['witness_key']}"):
                p = conn.execute("SELECT object_id FROM pointer WHERE slot=?", (slot,)).fetchone()
                if p is not None and not st.get(p["object_id"]).ok:
                    return f"the stored object of {slot} is damaged", None
        elif kind == "ORACLE_RUN" and conn.execute("SELECT 1 FROM oracle_run WHERE id=?", (eid,)).fetchone() is None:
            return f"run {eid} is missing from the result tables", None
    return None, v.payload


def decide(conn: sqlite3.Connection, key: str, rec: dict, cell_id: str, analysis_id: str) -> Reuse | Recompute:
    st = store_for(conn)
    if st is None:
        return Recompute("NEW")                      # with the store off nothing is stored, so nothing can be reused
    row = conn.execute("SELECT * FROM pair_index WHERE pair_key=?", (key,)).fetchone()
    rejected = None
    if row is not None and row["verdict_id"]:
        problem, payload = _verify(conn, st, row, key)
        if problem is None:
            old = payload["finding"]
            state = conn.execute("SELECT state FROM cell WHERE id=?", (old["cell_id"],)).fetchone()
            return Reuse(key, row["verdict_id"], payload, state["state"] if state else "ANALYZED")
        rejected = {"object_id": row["verdict_id"], "problem": problem}
        append_event(conn, "OBJECT_REJECTED", analysis_id=analysis_id, subject=row["verdict_id"], payload={"pair_key": key, "cell_id": cell_id, "problem": problem})
    prev = None
    for r in conn.execute("SELECT pair_key, pair_record_id FROM pair_index WHERE pair_record_id<>'' AND pair_key<>? ORDER BY created_at DESC, rowid DESC LIMIT 200", (key,)):
        got = st.get(r["pair_record_id"])
        if got.ok:
            inp = got.payload["inputs"]
            if (inp["producer"]["repo"], inp["producer"]["project"]) == (rec["producer"]["repo"], rec["producer"]["project"]) \
                    and sorted(c["repo"] for c in inp["consumers"]) == sorted(c["repo"] for c in rec["consumers"]):
                prev = inp
                break
    changed = explain(prev, rec) if prev else []
    return Recompute("REJECTED" if rejected else ("CHANGED" if prev else "NEW"), changed, rejected)


def started(conn: sqlite3.Connection, analysis_id: str, cell_id: str, key: str, d: Recompute) -> None:
    append_event(conn, "PAIR_RECOMPUTE_STARTED", analysis_id=analysis_id, subject=key,
                 payload={"cell_id": cell_id, "reason": d.reason, "changed": [c["input"] for c in d.changed], "detail": d.changed[:20]})


def finished(conn: sqlite3.Connection, analysis_id: str, cell_id: str, key: str, state: str, verdict: str) -> None:
    """The pair's result is complete: make it findable by its key and count it as recomputed."""
    p = conn.execute("SELECT object_id FROM pointer WHERE slot=?", (f"finding:{cell_id}",)).fetchone()
    if p is not None and state == "ANALYZED" and verdict not in NOT_REUSED_VERDICTS:
        conn.execute("UPDATE pair_index SET verdict_id=? WHERE pair_key=?", (p["object_id"], key))
    append_event(conn, "PAIR_RECOMPUTE_DONE", analysis_id=analysis_id, subject=key, payload={"cell_id": cell_id, "state": state, "verdict": verdict})


def apply_reuse(conn: sqlite3.Connection, analysis_id: str, cell_id: str, plan, r: Reuse) -> tuple[str, str]:
    """Give the cell of this analysis a finding that says what the stored one said, and name where it came from. Returns (finding_id, state)."""
    old = r.payload["finding"]
    fid = new_id("fnd")
    scope = json.loads(old["scope_json"])
    scope["reused"] = {"pair_key": r.key, "from_analysis": old["analysis_id"], "from_finding": old["id"], "from_verdict_object": r.verdict_id,
                       "note": "no oracle ran for this pair in this analysis: every input of its key is unchanged"}
    row = {**old, "id": fid, "analysis_id": analysis_id, "cell_id": cell_id, "scope_json": json.dumps(scope, sort_keys=True), "created_at": projections._now()}
    evidence = [e for e in r.payload["evidence"] if e[0] != "RELATIONSHIP"] + [["RELATIONSHIP", rid] for _c, rid in plan.consumers]
    projections.write(conn, "verdict", {"finding": row, "verdict": row["verdict"], "policy": r.payload.get("policy") or LIVE_POLICY_VERSION, "evidence": evidence,
                                        "reused_from": {"finding": old["id"], "analysis": old["analysis_id"], "pair_key": r.key}},
                      slot=f"finding:{cell_id}", analysis_id=analysis_id)
    conn.execute("UPDATE cell SET state=? WHERE id=?", (r.old_state, cell_id))
    append_event(conn, "PAIR_REUSED", analysis_id=analysis_id, subject=r.key,
                 payload={"cell_id": cell_id, "from_analysis": old["analysis_id"], "from_finding": old["id"], "verdict": row["verdict"]})
    return fid, r.old_state
