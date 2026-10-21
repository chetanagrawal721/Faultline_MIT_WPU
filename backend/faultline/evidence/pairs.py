"""Reads a cell's pair-key inputs from the database and records the pair (ADR 0008, decision 3)."""
import json
import sqlite3

from ..oracles import o_bind, o_contract, o_import, o_tests
from ..resolvers.python import LOGIC_VERSION
from ..verdicts.engine import LIVE_POLICY_VERSION, STATIC_RULE
from . import projections
from .pair_key import PairKeyInput, Side, pair_key, record


def side_of(conn: sqlite3.Connection, project_id: str, world_hash: str | None = None) -> Side:
    """A project's origin and how its world was made. `world_hash` picks the matching resolution when the project has several."""
    p = conn.execute("SELECT p.rel_path, s.sha, r.owner, r.name FROM project p JOIN snapshot s ON s.id=p.snapshot_id "
                     "JOIN repository r ON r.id=s.repository_id WHERE p.id=?", (project_id,)).fetchone()
    manifests = {m["path"]: m["content_hash"] for m in conn.execute("SELECT path, content_hash FROM manifest WHERE project_id=? ORDER BY path", (project_id,))}
    pw = None
    if world_hash:
        pw = conn.execute("SELECT * FROM project_world WHERE project_id=? AND world_hash=? ORDER BY resolved_at DESC LIMIT 1", (project_id, world_hash)).fetchone()
    pw = pw or conn.execute("SELECT * FROM project_world WHERE project_id=? ORDER BY resolved_at DESC LIMIT 1", (project_id,)).fetchone()
    args = json.loads(pw["resolver_args_json"] or "{}") if pw else {}
    by_uv = bool(pw) and pw["source"] == "resolver"
    return Side(
        repo=f"{p['owner']}/{p['name']}", commit=p["sha"], project=p["rel_path"], manifests=manifests,
        world_hash=world_hash or (pw["world_hash"] if pw else None), source=pw["source"] if pw else None,
        resolver="uv" if by_uv else (pw["resolver"] if pw else None),
        resolver_version=args.get("resolver_version") if by_uv else None,
        # a pinned lockfile does not depend on the cut-off time, the index or the flags; a world uv resolved does
        resolution={"exclude_newer": pw["resolved_at"], "index": args.get("index"), "flags": list(args.get("flags") or [])} if by_uv else None,
        platform=args.get("platform"), python=args.get("python"))


def collect_inputs(conn: sqlite3.Connection, cell_id: str, *, artifact_sha256: str, image: str) -> PairKeyInput:
    cell = conn.execute("SELECT * FROM cell WHERE id=?", (cell_id,)).fetchone()
    consumers = conn.execute("SELECT consumer_project_id, imported_modules_json FROM cell_consumer WHERE cell_id=? ORDER BY consumer_project_id", (cell_id,)).fetchall()
    entries = sorted({m for c in consumers for m in json.loads(c["imported_modules_json"] or "[]")})
    return PairKeyInput(
        producer=side_of(conn, cell["artifact_project_id"], cell["ref_world_hash"]),
        consumers=tuple(sorted((side_of(conn, c["consumer_project_id"]) for c in consumers), key=lambda s: (s.repo, s.commit, s.project))),
        reference_world_hash=cell["ref_world_hash"], consumer_world_hash=cell["test_world_hash"],
        producer_artifact_sha256=artifact_sha256, entries=tuple(entries),
        oracles={"o_import": o_import.ORACLE_VERSION, "o_tests": o_tests.ORACLE_VERSION, "o_bind": o_bind.ORACLE_VERSION, "o_contract": o_contract.ORACLE_VERSION},
        image=image, resolver_logic=LOGIC_VERSION, verdict_rule=LIVE_POLICY_VERSION, static_rule=STATIC_RULE)


def record_pair(conn: sqlite3.Connection, cell_id: str, analysis_id: str, inp: PairKeyInput) -> str:
    """Store the pair record (content-addressed: the same pair in another analysis is the same object) and link the cell to its key."""
    key = pair_key(inp)
    oid, _ = projections.store_object(conn, "pair_record", {"pair_key": key, "inputs": record(inp)}, analysis_id=analysis_id)
    conn.execute("INSERT OR IGNORE INTO pair_index(pair_key, pair_record_id, created_at) VALUES (?,?,?)", (key, oid or "", projections._now()))
    conn.execute("INSERT OR REPLACE INTO pair_cell(cell_id, analysis_id, pair_key) VALUES (?,?,?)", (cell_id, analysis_id, key))
    return key
