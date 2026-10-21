"""Filesystem backend: one canonical-JSON file per object at <root>/<first two hex>/<id>.json.

Writes go to a temporary file in the same folder, are read back and checked, and only then renamed into place, so a crash can leave a
temporary file but never a partial object under its final name. Identical content written by many threads or processes ends as one file.
"""
import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

from ..core.hashing import canonical_json, sha256_hex
from .kinds import KINDS, check_payload
from .store import EvidenceStore, Result, Status

_HEX = set("0123456789abcdef")


def object_id(kind: str, version: int, payload: dict) -> str:
    """Hash of `kind/version`, a newline and the canonical payload: two kinds with equal payloads can never share an id."""
    return sha256_hex(f"{kind}/{version}\n".encode() + canonical_json(payload))


def _valid_id(oid: str) -> bool:
    return len(oid) == 64 and set(oid) <= _HEX


def _read(path: Path) -> bytes:
    """Read a file. On Windows a read can be refused for a moment while another writer renames a copy over the file; wait and try again."""
    for attempt in range(40):
        try:
            return path.read_bytes()
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.01 * (attempt + 1))
    raise AssertionError("unreachable")


class FsObjectStore(EvidenceStore):
    def __init__(self, root: Path, *, on_temp_written: Callable[[Path], None] | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._on_temp_written = on_temp_written          # test hook: lets a test stop the process between the temporary write and the rename

    def _path(self, oid: str) -> Path:
        if not _valid_id(oid):
            raise ValueError(f"not an object id: {oid!r}")
        return self.root / oid[:2] / f"{oid}.json"

    def put(self, kind: str, payload: dict) -> str:
        k = check_payload(kind, payload)
        oid = object_id(kind, k.version, payload)
        dest = self._path(oid)
        if self.get(oid).ok:
            return oid
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = canonical_json({"kind": kind, "schema_version": k.version, "payload": payload})
        tmp = dest.with_name(f".{oid}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if self._on_temp_written:
                self._on_temp_written(tmp)
            if _read(tmp) != data:
                raise OSError("the temporary object does not match what was written")
            self._publish(tmp, dest, oid)
        finally:
            tmp.unlink(missing_ok=True)
        return oid

    def _publish(self, tmp: Path, dest: Path, oid: str) -> None:
        """Atomic rename. On Windows the rename can be refused while another process holds the destination; a verified copy there is the same content."""
        for attempt in range(8):
            try:
                os.replace(tmp, dest)
                return
            except OSError:
                if self.get(oid).ok:
                    return
                if attempt == 7:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def get(self, oid: str) -> Result:
        try:
            path = self._path(oid)
        except ValueError as e:
            return Result(Status.MISSING, oid, detail=str(e))
        try:
            raw = _read(path)
        except FileNotFoundError:
            return Result(Status.MISSING, oid)
        try:
            env = json.loads(raw)
            kind, version, payload = env["kind"], env["schema_version"], env["payload"]
            if not isinstance(version, int) or isinstance(version, bool) or not isinstance(kind, str):
                raise TypeError("bad envelope")
            if raw != canonical_json(env):
                raise ValueError("the bytes are not canonical")
            if object_id(kind, version, payload) != oid:
                raise ValueError("the content does not match the id")
        except (ValueError, KeyError, TypeError) as e:
            return Result(Status.CORRUPT, oid, detail=str(e))
        known = KINDS.get(kind)
        if known is None or version > known.version:
            return Result(Status.UNSUPPORTED, oid, kind=kind, detail=f"{kind} version {version} is not readable by this code")
        try:
            check_payload(kind, payload)
        except ValueError as e:
            return Result(Status.CORRUPT, oid, kind=kind, detail=str(e))
        return Result(Status.OK, oid, kind=kind, payload=payload)

    def exists(self, oid: str) -> bool:
        return self.get(oid).status in (Status.OK, Status.UNSUPPORTED)

    def link(self, parent: str, relation: str, child: str) -> None:
        line = json.dumps([parent, relation, child], separators=(",", ":")) + "\n"
        with open(self.root / "edges.log", "ab") as f:                 # one small append per edge; appends of this size do not interleave
            f.write(line.encode())

    def edges(self, parent: str | None = None) -> list[tuple[str, str, str]]:
        log = self.root / "edges.log"
        if not log.exists():
            return []
        seen: dict[tuple[str, str, str], None] = {}
        for ln in log.read_text(encoding="utf-8").splitlines():
            try:
                e = tuple(json.loads(ln))
            except ValueError:
                continue                                                # a torn last line is skipped, never guessed
            if len(e) == 3 and (parent is None or e[0] == parent):
                seen[e] = None
        return list(seen)

    def iter_objects(self) -> Iterator[tuple[str, Status]]:
        for d in sorted(p for p in self.root.iterdir() if p.is_dir() and len(p.name) == 2):
            for f in sorted(d.glob("*.json")):
                yield f.stem, (self.get(f.stem).status if _valid_id(f.stem) else Status.CORRUPT)

    def verify_all(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Status}
        for _, st in self.iter_objects():
            counts[st.value] += 1
        return counts
