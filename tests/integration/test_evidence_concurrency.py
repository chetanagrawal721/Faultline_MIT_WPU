"""TC-13.1.4: separate processes writing the same evidence content end with one valid object and no error."""
import multiprocessing as mp
from pathlib import Path

from faultline.evidence.object_store import FsObjectStore
from faultline.evidence.store import Status

PAYLOAD = {"world_hash": "w_shared", "note": "written by many processes"}


def _writer(root: str, n: int, out) -> None:
    s = FsObjectStore(Path(root))
    out.put([s.put("world_ref", PAYLOAD) for _ in range(n)])


def test_four_processes_and_many_writes_make_one_object(tmp_path):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    procs = [ctx.Process(target=_writer, args=(str(tmp_path), 25, q)) for _ in range(4)]
    [p.start() for p in procs]
    results = [q.get(timeout=120) for _ in procs]
    [p.join(timeout=60) for p in procs]
    assert all(p.exitcode == 0 for p in procs)
    ids = {i for r in results for i in r}
    assert len(ids) == 1
    s = FsObjectStore(tmp_path)
    assert s.get(next(iter(ids))).status is Status.OK
    assert s.verify_all() == {"OK": 1, "MISSING": 0, "CORRUPT": 0, "UNSUPPORTED": 0}
    assert not list(tmp_path.rglob("*.tmp"))


def test_processes_writing_different_content_do_not_interfere(tmp_path):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    procs = [ctx.Process(target=_writer, args=(str(tmp_path), 5, q)) for _ in range(3)]
    [p.start() for p in procs]
    [q.get(timeout=120) for _ in procs]
    [p.join(timeout=60) for p in procs]
    other = FsObjectStore(tmp_path).put("world_ref", {"world_hash": "w_other"})
    assert FsObjectStore(tmp_path).get(other).ok
    assert FsObjectStore(tmp_path).verify_all()["OK"] == 2
