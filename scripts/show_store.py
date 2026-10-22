"""Shows where Faultline keeps its data and what is in it. Read only: it opens the database with mode=ro and only reads the object files.

    python tools/fl.py script scripts/show_store.py                 # location, tables, the evidence store, pair keys, newest events
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--object")
    ap.add_argument("--check", action="store_true")
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

    c = connect_ro(db)
    if a.sql:
        if not a.sql.lstrip().lower().startswith(("select", "with")) or ";" in a.sql.strip().rstrip(";"):
            print("only a single SELECT statement is accepted")
            return 2
        cur = c.execute(a.sql)
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
