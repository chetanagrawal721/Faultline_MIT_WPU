"""M13.1: the content-addressed object store."""
import json
import threading

import pytest

from faultline.evidence.kinds import InvalidObject
from faultline.evidence.object_store import FsObjectStore, object_id
from faultline.evidence.store import Status

WORLD = {"world_hash": "w_abc", "note": "first"}


def test_identity_is_deterministic(tmp_path):                               # TC-13.1.1
    s = FsObjectStore(tmp_path)
    a = s.put("world_ref", {"world_hash": "w_1", "b": 2, "a": 1})
    b = s.put("world_ref", {"a": 1, "b": 2, "world_hash": "w_1"})         # same payload, keys in another order
    assert a == b and len(a) == 64
    other_kind = object_id("pair_record", 1, {"world_hash": "w_1", "b": 2, "a": 1})
    assert other_kind != a                                                  # the kind is part of the identity
    assert s.get(a).payload == {"world_hash": "w_1", "a": 1, "b": 2}
    assert FsObjectStore(tmp_path).put("world_ref", {"world_hash": "w_1", "b": 2, "a": 1}) == a   # a second store object on the same folder agrees


def test_same_payload_under_two_kinds_gives_two_objects(tmp_path):
    s = FsObjectStore(tmp_path)
    payload = {"world_hash": "w_1", "pair_key": "k", "inputs": {}}
    assert s.put("world_ref", payload) != s.put("pair_record", payload)


def test_tampering_is_rejected(tmp_path):                                   # TC-13.1.2
    s = FsObjectStore(tmp_path)
    oid = s.put("world_ref", WORLD)
    path = tmp_path / oid[:2] / f"{oid}.json"
    raw = bytearray(path.read_bytes())
    raw[raw.index(b"first")] ^= 0x01                                        # flip one byte inside the payload
    path.write_bytes(bytes(raw))
    r = s.get(oid)
    assert r.status is Status.CORRUPT and r.payload is None
    assert not s.exists(oid) or s.get(oid).status is not Status.OK
    assert s.verify_all()["CORRUPT"] == 1


def test_a_valid_envelope_with_the_wrong_name_is_corrupt(tmp_path):
    s = FsObjectStore(tmp_path)
    a, b = s.put("world_ref", {"world_hash": "w_a"}), s.put("world_ref", {"world_hash": "w_b"})
    (tmp_path / b[:2] / f"{b}.json").write_bytes((tmp_path / a[:2] / f"{a}.json").read_bytes())    # content of a under the name of b
    assert s.get(b).status is Status.CORRUPT and s.get(a).ok


def test_put_repairs_a_corrupt_object(tmp_path):
    s = FsObjectStore(tmp_path)
    oid = s.put("world_ref", WORLD)
    (tmp_path / oid[:2] / f"{oid}.json").write_bytes(b"{")
    assert s.get(oid).status is Status.CORRUPT
    assert s.put("world_ref", WORLD) == oid and s.get(oid).ok


class _Crash(Exception):
    pass


def test_a_crash_leaves_no_partial_object(tmp_path):                        # TC-13.1.3
    def die(tmp):
        raise _Crash()
    with pytest.raises(_Crash):
        FsObjectStore(tmp_path, on_temp_written=die).put("world_ref", WORLD)
    oid = object_id("world_ref", 1, WORLD)
    assert not (tmp_path / oid[:2] / f"{oid}.json").exists()               # nothing under the final name
    assert FsObjectStore(tmp_path).get(oid).status is Status.MISSING
    assert FsObjectStore(tmp_path).put("world_ref", WORLD) == oid          # the retry succeeds
    assert FsObjectStore(tmp_path).get(oid).ok
    assert not list(tmp_path.rglob("*.tmp"))


def test_a_killed_process_leaves_only_a_temporary_file(tmp_path):
    import subprocess
    import sys
    code = ("import os,sys; sys.path.insert(0, sys.argv[1]);"
            "from faultline.evidence.object_store import FsObjectStore;"
            "from pathlib import Path;"
            "FsObjectStore(Path(sys.argv[2]), on_temp_written=lambda p: os._exit(9)).put('world_ref', {'world_hash': 'w_k'})")
    from pathlib import Path
    backend = str(Path(__file__).resolve().parents[2] / "backend")
    p = subprocess.run([sys.executable, "-c", code, backend, str(tmp_path)])
    assert p.returncode == 9
    oid = object_id("world_ref", 1, {"world_hash": "w_k"})
    assert FsObjectStore(tmp_path).get(oid).status is Status.MISSING
    assert FsObjectStore(tmp_path).put("world_ref", {"world_hash": "w_k"}) == oid
    assert FsObjectStore(tmp_path).verify_all() == {"OK": 1, "MISSING": 0, "CORRUPT": 0, "UNSUPPORTED": 0}


def test_threads_writing_the_same_content_make_one_object(tmp_path):        # TC-13.1.4 (threads; processes are in tests/integration)
    s = FsObjectStore(tmp_path)
    ids, errors = [], []

    def work():
        try:
            ids.append(s.put("world_ref", WORLD))
        except Exception as e:                                              # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=work) for _ in range(16)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and len(set(ids)) == 1
    assert len(list(tmp_path.rglob("*.json"))) == 1 and not list(tmp_path.rglob("*.tmp"))


def test_an_unsupported_schema_is_not_corrupt_and_not_used(tmp_path):       # TC-13.1.5
    s = FsObjectStore(tmp_path)
    future = {"kind": "world_ref", "schema_version": 2, "payload": {"world_hash": "w_f"}}
    from faultline.core.hashing import canonical_json
    oid = object_id("world_ref", 2, future["payload"])
    (tmp_path / oid[:2]).mkdir()
    (tmp_path / oid[:2] / f"{oid}.json").write_bytes(canonical_json(future))
    r = s.get(oid)
    assert r.status is Status.UNSUPPORTED and r.payload is None
    unknown = {"kind": "mystery", "schema_version": 1, "payload": {"x": 1}}
    uid = object_id("mystery", 1, unknown["payload"])
    (tmp_path / uid[:2]).mkdir(exist_ok=True)
    (tmp_path / uid[:2] / f"{uid}.json").write_bytes(canonical_json(unknown))
    assert s.get(uid).status is Status.UNSUPPORTED
    assert s.verify_all()["UNSUPPORTED"] == 2


def test_invalid_payloads_are_refused(tmp_path):
    s = FsObjectStore(tmp_path)
    with pytest.raises(InvalidObject):
        s.put("world_ref", {})                                              # a required field is missing
    with pytest.raises(InvalidObject):
        s.put("mystery", {"x": 1})
    with pytest.raises(InvalidObject):
        s.put("world_ref", ["not", "an", "object"])                        # type: ignore[arg-type]


def test_ids_cannot_escape_the_store(tmp_path):
    s = FsObjectStore(tmp_path)
    assert s.get("../../etc/passwd").status is Status.MISSING
    assert s.get("g" * 64).status is Status.MISSING


def test_edges_are_appended_and_deduplicated(tmp_path):
    s = FsObjectStore(tmp_path)
    a, b = s.put("world_ref", {"world_hash": "w_a"}), s.put("world_ref", {"world_hash": "w_b"})
    s.link(a, "derived_from", b)
    s.link(a, "derived_from", b)
    s.link(b, "derived_from", a)
    assert s.edges(a) == [(a, "derived_from", b)] and len(s.edges()) == 2
    (tmp_path / "edges.log").open("ab").write(b'["torn')
    assert len(s.edges()) == 2                                              # a torn last line is ignored


def test_the_file_is_canonical_json(tmp_path):
    s = FsObjectStore(tmp_path)
    oid = s.put("world_ref", {"world_hash": "w_1", "z": [1, 2], "a": {"y": 1, "x": 2}})
    raw = (tmp_path / oid[:2] / f"{oid}.json").read_bytes()
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
