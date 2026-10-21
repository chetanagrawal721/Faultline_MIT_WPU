"""M13.2: the append-only event log and the job-transition events."""
import sqlite3

import pytest

from faultline.evidence.events import append_event, list_events
from faultline.storage import jobs
from faultline.storage.db import connect
from faultline.storage.migrate import migrate


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "f.db")
    migrate(c)
    return c


def kinds(conn, job_id):
    return [e["kind"] for e in list_events(conn, job_id=job_id)]


def test_events_cannot_be_updated_or_deleted(conn):                         # TC-13.2.1
    eid = append_event(conn, "PAIR_REUSED", subject="k", payload={"a": 1})
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE evidence_event SET kind='PAIR_REUSED', subject='x' WHERE id=?", (eid,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM evidence_event WHERE id=?", (eid,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM evidence_event")
    assert [e["id"] for e in list_events(conn)] == [eid]


def test_unknown_event_kinds_are_refused(conn):
    with pytest.raises(ValueError):
        append_event(conn, "SOMETHING_ELSE")


def test_a_normal_job_has_one_event_per_transition(conn):                   # TC-13.2.2
    job, _ = jobs.create_job(conn, "demo")
    c = jobs.claim_next(conn, "w1", 30)
    assert c and jobs.complete(conn, job.job_id, "w1", {"ok": True})
    assert kinds(conn, job.job_id) == ["JOB_QUEUED", "JOB_CLAIMED", "JOB_DONE"]
    claimed = list_events(conn, job_id=job.job_id)[1]
    assert claimed["payload"] == {"attempt": 1, "worker": "w1"}


def test_a_retried_job_shows_each_attempt(conn):
    job, _ = jobs.create_job(conn, "demo")
    jobs.claim_next(conn, "w1", 30)
    assert jobs.fail(conn, job.job_id, "w1", {"code": "BOOM"}, retryable=True) == "QUEUED"
    jobs.claim_next(conn, "w2", 30)
    assert jobs.complete(conn, job.job_id, "w2")
    assert kinds(conn, job.job_id) == ["JOB_QUEUED", "JOB_CLAIMED", "JOB_RETRIED", "JOB_CLAIMED", "JOB_DONE"]


def test_a_failed_job(conn):
    job, _ = jobs.create_job(conn, "demo", max_attempts=1)
    jobs.claim_next(conn, "w1", 30)
    assert jobs.fail(conn, job.job_id, "w1", {"code": "BOOM"}, retryable=True) == "FAILED"
    assert kinds(conn, job.job_id) == ["JOB_QUEUED", "JOB_CLAIMED", "JOB_FAILED"]


def test_a_cancelled_running_job(conn):
    job, _ = jobs.create_job(conn, "demo")
    jobs.claim_next(conn, "w1", 30)
    jobs.request_cancel(conn, job.job_id)
    jobs.request_cancel(conn, job.job_id)                                   # a repeat request adds no event
    assert jobs.mark_cancelled(conn, job.job_id, "w1")
    assert kinds(conn, job.job_id) == ["JOB_QUEUED", "JOB_CLAIMED", "JOB_CANCEL_REQUESTED", "JOB_CANCELLED"]


def test_a_cancelled_queued_job(conn):
    job, _ = jobs.create_job(conn, "demo")
    jobs.request_cancel(conn, job.job_id)
    assert kinds(conn, job.job_id) == ["JOB_QUEUED", "JOB_CANCEL_REQUESTED", "JOB_CANCELLED"]


def test_a_lease_reclaim_is_a_new_claim(conn):
    job, _ = jobs.create_job(conn, "demo")
    jobs.claim_next(conn, "w1", -5)                                         # the lease has already expired
    c = jobs.claim_next(conn, "w2", 30)
    assert c and c.attempt == 2
    assert kinds(conn, job.job_id) == ["JOB_QUEUED", "JOB_CLAIMED", "JOB_CLAIMED"]
    assert list_events(conn, job_id=job.job_id)[-1]["payload"]["worker"] == "w2"


def test_a_heartbeat_adds_no_event(conn):
    job, _ = jobs.create_job(conn, "demo")
    jobs.claim_next(conn, "w1", 30)
    n = len(list_events(conn, job_id=job.job_id))
    jobs.heartbeat(conn, job.job_id, "w1", 30, progress=0.5)
    assert len(list_events(conn, job_id=job.job_id)) == n
