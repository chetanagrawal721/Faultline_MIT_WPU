"""Shows where Faultline keeps its data and what is in it. Read only: it opens the database with mode=ro and only reads the object files.

    python tools/fl.py script scripts/show_store.py                 # location, tables, the evidence store, pair keys, newest events
    python tools/fl.py script scripts/show_store.py --hashes        # the tables that hold hashes, with real rows, and one hash followed end to end
    python tools/fl.py script scripts/show_store.py --prove-append-only   # try to change an event (on a copy): the database refuses
    python tools/fl.py script scripts/show_store.py --object ID     # one stored object, printed as it is on disk
    python tools/fl.py script scripts/show_store.py --check         # re-hash every stored object and report any that does not match its name
    python tools/fl.py script scripts/show_store.py --sql "SELECT kind, COUNT(*) FROM evidence_event GROUP BY kind"   # any read-only query
    python tools/fl.py script scripts/show_store.py --db PATH       # another database (default: FAULTLINE_DB or var/faultline.db)

It is safe to run while the project is running.
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend")]

TABLE_GROUPS = [
    ("Inputs", ["repository", "snapshot", "manifest", "project"]),
    ("Worlds", ["resolved_world", "world_entry", "env_profile"]),
    ("Analysis", ["analysis", "cell", "relationship", "oracle_job", "oracle_run"]),
    ("Results (rebuilt from the evidence store)", ["witness", "attribution", "attribution_attempt", "finding", "finding_evidence", "remediation_plan"]),
    ("Evidence store (the twist)", ["object_index", "pointer", "pair_index", "pair_cell", "ddmin_checkpoint", "evidence_event"]),
    ("Jobs", ["job", "job_attempt"]),
]


def line(title: str = "") -> None:
    print(("\n" + title + "\n" + "-" * len(title)) if title else "")


def connect_ro(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def count(c: sqlite3.Connection, table: str) -> str:
    try:
        return f"{c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:,}"
    except sqlite3.Error:
        return "-"


def show_object(objects: Path, oid: str) -> int:
    f = objects / oid[:2] / f"{oid}.json"
    if not f.exists():
        print(f"no object {oid} under {objects}")
        return 1
    print(f"file: {f}")
    print(f"size: {f.stat().st_size:,} bytes\n")
    print(json.dumps(json.loads(f.read_text(encoding="utf-8")), indent=2, sort_keys=True)[:6000])
    return 0


def check_objects(objects: Path) -> int:
    from faultline.evidence.object_store import FsObjectStore
    st = FsObjectStore(objects)
    bad, total = [], 0
    for oid, status in st.iter_objects():
        total += 1
        if status.value != "OK":
            bad.append((oid, status.value))
    print(f"{total} objects re-read and re-hashed under {objects}")
    print("every object matches its name" if not bad else f"{len(bad)} object(s) do not match: " + ", ".join(f"{o[:12]} ({s})" for o, s in bad[:10]))
    return 1 if bad else 0


HASH_TABLES = [
    ("object_index", "object_id", "Every stored object. object_id is the SHA-256 of the object's kind and content, and it is also the file name in var/evidence/objects."),
    ("pointer", "object_id", "The current version of each result. slot names the thing (for example finding:<cell>), object_id is the hash of its latest object, seq is the version."),
    ("pair_index", "pair_key, pair_record_id, verdict_id", "One row per producer-consumer pair. pair_key is the hash of all the pair's inputs; the other two point at stored objects."),
    ("pair_cell", "pair_key", "Which cell of which analysis was computed for which pair key (this is how a later analysis finds a reusable result)."),
    ("ddmin_checkpoint", "object_id", "The cause search's checkpoints: one immutable object per step, numbered by seq."),
    ("resolved_world", "world_hash", "Every dependency world. world_hash is the hash of the world's exact contents (packages, versions, wheel hashes, runtime)."),
    ("snapshot", "sha", "The exact commit each repository was pinned to."),
    ("snapshot_file", "content_hash, blob_sha", "Every file of a snapshot, by content hash."),
    ("witness", "witness_key, input_hash", "A witness is identified by a hash of what it witnessed, not by when it was found."),
]


def show_hashes(c: sqlite3.Connection, objects: Path) -> int:
    from faultline.evidence.object_store import object_id
    print("Tables that hold hashes (hashes are shortened to 16 characters here; the full value is in the table)")
    for table, cols, note in HASH_TABLES:
        n = count(c, table)
        line(f"{table}   ({n} rows)")
        print(f"  {note}")
        names = [x.strip() for x in cols.split(",")]
        extra = {"object_index": ["kind", "slot", "seq"], "pointer": ["slot", "seq"], "ddmin_checkpoint": ["seq", "status"], "pair_cell": ["cell_id"],
                 "resolved_world": ["kind"], "witness": ["oracle", "entry_point"], "snapshot": ["repository_id"]}.get(table, [])
        try:
            rows = c.execute(f"SELECT {', '.join(names + extra)} FROM {table} ORDER BY rowid DESC LIMIT 3").fetchall()
        except sqlite3.Error as e:
            print(f"  ({e})")
            continue
        for r in rows:
            print("  " + "   ".join(f"{k}={str(r[k])[:16] + ('...' if len(str(r[k])) > 16 and all(ch in '0123456789abcdef_pkwx' for ch in str(r[k])[:6]) else '') if k in names else str(r[k])[:40]}" for k in r.keys()))

    line("One hash followed from the database to the file and back")
    row = c.execute("SELECT pair_key, pair_record_id, verdict_id FROM pair_index WHERE verdict_id IS NOT NULL ORDER BY created_at DESC LIMIT 1").fetchone()
    if not row:
        print("  (no pair with a stored result yet: run an analysis)")
        return 0
    print(f"  pair_index.pair_key       {row['pair_key']}")
    print(f"  pair_index.pair_record_id {row['pair_record_id']}")
    print(f"  pair_index.verdict_id     {row['verdict_id']}")
    f = objects / row["verdict_id"][:2] / f"{row['verdict_id']}.json"
    print(f"\n  the file for verdict_id   {f}")
    d = json.loads(f.read_text(encoding="utf-8"))
    recomputed = object_id(d["kind"], d["schema_version"], d["payload"])
    print(f"  hash recomputed from the file's content: {recomputed}")
    print(f"  equal to verdict_id: {'YES: the stored result is exactly what was written' if recomputed == row['verdict_id'] else 'NO: the file was changed'}")
    p = d["payload"]
    print(f"\n  the verdict inside: {p.get('verdict')}  (policy {p.get('policy')})")
    ev = p.get("evidence", [])
    print(f"  it cites {len(ev)} evidence items, for example: " + ", ".join(f"{k}:{str(i)[:14]}" for k, i in ev[:3]))
    rec = objects / row["pair_record_id"][:2] / f"{row['pair_record_id']}.json"
    if rec.exists():
        inp = json.loads(rec.read_text(encoding="utf-8"))["payload"]["inputs"]
        print("\n  the pair record behind pair_key (the inputs the key is made of):")
        for k in ("reference_world_hash", "consumer_world_hash", "producer_artifact_sha256", "image", "witness_rule", "verdict_rule", "static_rule"):
            if k in inp:
                print(f"    {k:<26}{str(inp[k])[:72]}")
        print(f"    {'producer.commit':<26}{str(inp.get('producer', {}).get('commit'))[:72]}")
    slots = [r["slot"] for r in c.execute("SELECT slot FROM pointer WHERE object_id=?", (row["verdict_id"],))]
    print(f"\n  pointer rows that name this verdict_id: {slots or '(an older version: the pointer has moved on)'}")
    return 0


def prove_append_only(db: Path) -> int:
    """Works on a copy in the temporary folder; the real database is only read."""
    import shutil
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="fl-append-only-")) / "copy.db"
    src = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(work)
    src.backup(dst)
    src.close()
    first = dst.execute("SELECT id, kind FROM evidence_event ORDER BY id LIMIT 1").fetchone()
    print(f"a copy of the database is at {work} (the real file is not touched)")
    print(f"event #{first[0]} is {first[1]}\n")
    code = 0
    for sql in (f"UPDATE evidence_event SET kind='X' WHERE id={first[0]}", f"DELETE FROM evidence_event WHERE id={first[0]}"):
        print("  " + sql)
        try:
            dst.execute(sql)
            dst.commit()
            print("  -> it was ACCEPTED (this should not happen)\n")
            code = 1
        except sqlite3.Error as e:
            print(f"  -> refused by the database: {e}\n")
    dst.close()
    shutil.rmtree(work.parent, ignore_errors=True)
    print("The event log is append-only: the database itself refuses to change or delete a recorded event." if code == 0 else "NOT append-only")
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--object")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--hashes", action="store_true", help="show the tables that hold hashes")
    ap.add_argument("--prove-append-only", action="store_true", help="on a throw-away copy, try to change and delete an event and show that the database refuses")
    ap.add_argument("--sql", help="a single SELECT statement, run read only")
    ap.add_argument("--events", type=int, default=12)
    a = ap.parse_args()
    db = Path(a.db or os.environ.get("FAULTLINE_DB") or ROOT / "var" / "faultline.db").resolve()
    if not db.exists():
        print(f"no database at {db}. Start the project once (python tools/fl.py up) or pass --db.")
        return 1
    objects = Path(os.environ.get("FAULTLINE_EVIDENCE_DIR") or db.parent / "evidence" / "objects")
    if a.object:
        return show_object(objects, a.object)
    if a.check:
        return check_objects(objects)

    if a.prove_append_only:
        return prove_append_only(db)
    c = connect_ro(db)
    if a.hashes:
        return show_hashes(c, objects)
    if a.sql:
        if not a.sql.lstrip().lower().startswith(("select", "with")) or ";" in a.sql.strip().rstrip(";"):
            print("only a single SELECT statement is accepted")
            return 2
        try:
            cur = c.execute(a.sql)
        except sqlite3.Error as e:
            print(f"the query was refused: {e}")
            return 2
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(200)
        widths = [max(len(str(x)) for x in [col, *[r[i] for r in rows]]) for i, col in enumerate(cols)]
        widths = [min(w, 60) for w in widths]
        print("  ".join(col.ljust(w) for col, w in zip(cols, widths, strict=True)))
        print("  ".join("-" * w for w in widths))
        for r in rows:
            print("  ".join(str(r[i])[:w].ljust(w) for i, w in enumerate(widths)))
        print(f"({len(rows)} row{'s' if len(rows) != 1 else ''}{', first 200 shown' if len(rows) == 200 else ''})")
        return 0
    line("1. Where the data is")
    print(f"SQL database : {db}  ({db.stat().st_size / 1e6:.1f} MB, SQLite file, schema v{c.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] if count(c, 'schema_migrations') != '-' else '?'})")
    files = sorted(objects.rglob("*.json")) if objects.exists() else []
    print(f"Evidence store: {objects}  ({len(files):,} immutable object files, {sum(f.stat().st_size for f in files) / 1e6:.1f} MB)")
    print("Each object's file name is the SHA-256 of its content, so a changed or damaged file no longer matches its name.")

    line("2. The tables (row counts)")
    for group, tables in TABLE_GROUPS:
        print(f"  {group}")
        for t in tables:
            print(f"      {t:<22}{count(c, t):>10}")

    line("3. The evidence store, by kind of object")
    kinds = Counter(r["kind"] for r in c.execute("SELECT kind FROM object_index"))
    for kind, n in kinds.most_common():
        print(f"  {kind:<20}{n:>6}")
    print(f"  pointers (the current version of each result): {count(c, 'pointer')}")

    line("4. Pair keys: one per producer-consumer pair (this is how reuse recognises a pair)")
    rows = c.execute("SELECT pair_key, verdict_id IS NOT NULL AS has_result, created_at FROM pair_index ORDER BY created_at DESC LIMIT 8").fetchall()
    for r in rows:
        print(f"  {r['pair_key']}   stored result: {'yes' if r['has_result'] else 'no'}   first seen {r['created_at']}")
    if not rows:
        print("  (none yet: run an analysis)")

    line(f"5. The newest {a.events} events (append-only log: nothing is updated or deleted)")
    for r in c.execute("SELECT id, at, kind, subject FROM evidence_event ORDER BY id DESC LIMIT ?", (a.events,)):
        print(f"  #{r['id']:<6}{r['at'][:19]}  {r['kind']:<28}{(r['subject'] or '')[:34]}")
    by_kind = Counter(r["kind"] for r in c.execute("SELECT kind FROM evidence_event"))
    print("  totals: " + ", ".join(f"{k} {n}" for k, n in by_kind.most_common(8)))

    line("6. One stored object (the latest verdict), as it is on disk")
    row = c.execute("SELECT object_id FROM object_index WHERE kind='verdict' ORDER BY created_at DESC LIMIT 1").fetchone()
    if row:
        f = objects / row["object_id"][:2] / f"{row['object_id']}.json"
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        p = d.get("payload", {})
        print(f"  file    : {f}")
        print(f"  kind    : {d.get('kind')} (schema {d.get('schema_version')})")
        print(f"  verdict : {p.get('verdict')}   policy: {p.get('policy')}")
        print(f"  says    : {str(p.get('finding', {}).get('headline', ''))[:150]}")
        print(f"  cites   : {len(p.get('evidence', []))} evidence items (witnesses and oracle runs)")
        print(f"  show all: python tools/fl.py script scripts/show_store.py --object {row['object_id']}")
    else:
        print("  (no verdict stored yet)")
    print("\nCheck integrity: python tools/fl.py script scripts/show_store.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
