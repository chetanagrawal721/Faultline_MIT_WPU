"""Where the evidence store is and whether it is on (ADR 0008).

FAULTLINE_EVIDENCE_STORE=on|off (default on). With `off` the result tables are written exactly as before and no objects are stored; it is the
baseline for the parity tests. The object directory sits next to the database file (var/evidence/objects), so every test database gets its own.
"""
import os
import sqlite3
import tempfile
from pathlib import Path

from .object_store import FsObjectStore

_stores: dict[str, FsObjectStore] = {}


def enabled() -> bool:
    return os.environ.get("FAULTLINE_EVIDENCE_STORE", "on").strip().lower() != "off"


def objects_dir(conn: sqlite3.Connection) -> Path:
    override = os.environ.get("FAULTLINE_EVIDENCE_DIR")
    if override:
        return Path(override)
    file = conn.execute("PRAGMA database_list").fetchone()["file"]
    if file:
        return Path(file).parent / "evidence" / "objects"
    return Path(tempfile.gettempdir()) / f"faultline-evidence-memory-{id(conn)}"          # an in-memory database has no folder of its own


def store_for(conn: sqlite3.Connection) -> FsObjectStore | None:
    if not enabled():
        return None
    root = str(objects_dir(conn))
    if root not in _stores:
        _stores[root] = FsObjectStore(Path(root))
    return _stores[root]
