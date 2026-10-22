"""A normalised dump of the evidence tables, used to prove that two runs, or a table before and after a rebuild, say the same thing.

Ids, timestamps, durations and paths are left out; everything that carries meaning (verdicts, headlines, witnesses, attribution, fixes, the
shape of the runs) is kept. Rows are sorted by their content, never by id.
"""
import json
import sqlite3

# witness_key is left out: it hashes the producer artifact, whose snapshot holds the pinned commit, and a local test remote gets a new commit every time it is ingested
_WITNESS_BODY_DROP = {"witness_id", "cell_id", "ref_run_ids", "test_run_ids", "reverifications", "witness_key"}


def _j(text: str | None):
    return json.loads(text) if text else None


def _key(*parts) -> str:
    return json.dumps(parts, sort_keys=True, default=str)


def dump_evidence(conn: sqlite3.Connection, analysis_id: str | None = None) -> dict:
    where = " WHERE analysis_id=?" if analysis_id else ""
    args = (analysis_id,) if analysis_id else ()
    findings = sorted(({"verdict": r["verdict"], "sub_label": r["sub_label"], "headline": r["headline"], "scope": _j(r["scope_json"]),
                        "priority": r["priority"], "coverage": r["coverage"], "scope_kind": r["scope_kind"]}
                       for r in conn.execute("SELECT * FROM finding" + where, args)), key=lambda d: _key(d["verdict"], d["headline"]))
    witnesses, wkey = [], {}
    for r in conn.execute("SELECT * FROM witness" + where, args):
        body = {k: v for k, v in (_j(r["body_json"]) or {}).items() if k not in _WITNESS_BODY_DROP}
        d = {"class": r["class"], "divergence": r["divergence"], "oracle": r["oracle"], "oracle_version": r["oracle_version"],
             "entry_point": r["entry_point"], "input_tier": r["input_tier"], "input_hash": r["input_hash"], "signature": _j(r["signature_json"]),
             "ref_pass": r["ref_pass"], "test_fail": r["test_fail"], "body": body, "reverifications": len(_j(r["body_json"]).get("reverifications", []))}
        witnesses.append(d)
        wkey[r["id"]] = _key(r["oracle"], r["entry_point"])
    witnesses.sort(key=lambda d: _key(d["oracle"], d["entry_point"]))
    attributions = []
    for a in conn.execute("SELECT * FROM attribution"):
        if a["witness_id"] not in wkey:
            continue
        attempts = [{"direction": t["direction"], "subset": _j(t["subset_json"]), "outcome": t["outcome"], "note": t["note"]}
                    for t in conn.execute("SELECT * FROM attribution_attempt WHERE attribution_id=? ORDER BY seq", (a["id"],))]
        attributions.append({"witness": wkey[a["witness_id"]], "status": a["status"], "minimal": _j(a["minimal_set_json"]), "sidedness": a["sidedness"],
                             "forced_worlds_used": a["forced_worlds_used"], "runs": a["runs"], "notes": _j(a["notes_json"]), "attempts": attempts})
    attributions.sort(key=lambda d: d["witness"])
    plans = sorted(({"label": p["label"], "rank": p["rank"], "moves": _j(p["moves_json"]), "gates": _j(p["gates_json"]),
                     "world_hashes": _j(p["world_hashes_json"])} for p in conn.execute("SELECT * FROM remediation_plan")), key=lambda d: _key(d["moves"], d["label"]))
    runs: dict[str, dict] = {}
    for r in conn.execute("SELECT j.oracle, j.side, r.provenance, r.failure_class, r.exit_code, r.env_fingerprint, r.result_json FROM oracle_run r "
                          "JOIN oracle_job j ON j.id=r.oracle_job_id" + (" WHERE j.analysis_id=?" if analysis_id else ""), args):
        res = _j(r["result_json"]) or {}
        entries = sorted(_key(e.get("entry"), e.get("passed"), e.get("exc_type"), e.get("message")) for e in res.get("entries", []))
        k = _key(r["oracle"], r["side"], r["provenance"], r["failure_class"], r["exit_code"], entries)           # the fingerprint names the machine's image: not part of the comparison
        runs[k] = {"oracle": r["oracle"], "side": r["side"], "provenance": r["provenance"], "failure_class": r["failure_class"], "exit_code": r["exit_code"],
                   "entries": entries, "count": runs.get(k, {}).get("count", 0) + 1}
    evidence_links: dict[str, int] = {}
    for r in conn.execute("SELECT e.evidence_kind, COUNT(*) AS n FROM finding_evidence e JOIN finding f ON f.id=e.finding_id"
                          + (" WHERE f.analysis_id=?" if analysis_id else "") + " GROUP BY e.evidence_kind", args):
        evidence_links[r["evidence_kind"]] = r["n"]
    return {"findings": findings, "witnesses": witnesses, "attributions": attributions, "remediation": plans,
            "runs": sorted(runs.values(), key=lambda d: _key(d)), "finding_evidence": evidence_links}
