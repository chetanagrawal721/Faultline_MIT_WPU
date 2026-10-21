-- 0007_evidence: the content-addressed evidence store's SQL side (ADR 0008). Tables and triggers only; nothing existing is altered.
-- The evidence itself lives in immutable object files. These tables index them, record events, and hold the "current" pointer of each slot.

CREATE TABLE object_index (
  object_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  slot TEXT,                              -- the logical thing this object is a version of (for example 'finding:<cell>')
  seq INTEGER,                            -- version number within the slot; the highest seq is the current one
  created_at TEXT NOT NULL
);
CREATE INDEX ix_object_slot ON object_index(slot, seq);

CREATE TABLE object_edge (
  parent TEXT NOT NULL,
  relation TEXT NOT NULL,
  child TEXT NOT NULL,
  PRIMARY KEY (parent, relation, child)
);

-- Append-only record of what happened. Rows are never changed or removed.
CREATE TABLE evidence_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  analysis_id TEXT,
  job_id TEXT,
  kind TEXT NOT NULL,
  subject TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_event_analysis ON evidence_event(analysis_id, kind);
CREATE INDEX ix_event_job ON evidence_event(job_id, id);

CREATE TRIGGER trg_event_no_update BEFORE UPDATE ON evidence_event
BEGIN
  SELECT RAISE(ABORT, 'evidence_event is append-only');
END;

CREATE TRIGGER trg_event_no_delete BEFORE DELETE ON evidence_event
BEGIN
  SELECT RAISE(ABORT, 'evidence_event is append-only');
END;

-- The current object of each slot. Derived: rebuild recomputes it from object_index (highest seq per slot).
CREATE TABLE pointer (
  slot TEXT PRIMARY KEY,
  object_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  moved_at TEXT NOT NULL
);

-- Resumable minimisation (M13.5): one row per checkpoint; (minimisation_id, seq) lets exactly one writer advance a chain.
CREATE TABLE ddmin_checkpoint (
  minimisation_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  object_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (minimisation_id, seq)
);

-- Producer-consumer pairs by content key (M13.3, M13.4).
CREATE TABLE pair_index (
  pair_key TEXT PRIMARY KEY,
  pair_record_id TEXT NOT NULL,
  verdict_id TEXT,
  created_at TEXT NOT NULL
);

-- Every job state change is also an event, written by the database in the same transaction as the change.
CREATE TRIGGER trg_job_event_created AFTER INSERT ON job
BEGIN
  INSERT INTO evidence_event(at, analysis_id, job_id, kind, subject, payload_json)
  VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), NEW.analysis_id, NEW.job_id, 'JOB_QUEUED', NEW.kind, json_object('status', NEW.status));
END;

CREATE TRIGGER trg_job_event_claimed AFTER UPDATE OF attempts ON job
WHEN NEW.attempts <> OLD.attempts
BEGIN
  INSERT INTO evidence_event(at, analysis_id, job_id, kind, subject, payload_json)
  VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), NEW.analysis_id, NEW.job_id, 'JOB_CLAIMED', NEW.kind,
          json_object('attempt', NEW.attempts, 'worker', NEW.lease_owner));
END;

-- The cancel flag and a status change can happen in one statement (cancelling a queued job). SQLite does not order triggers, so one
-- trigger writes both events, the request first.
CREATE TRIGGER trg_job_event_cancel_requested AFTER UPDATE OF cancel_requested ON job
WHEN OLD.cancel_requested = 0 AND NEW.cancel_requested = 1 AND OLD.status = NEW.status
BEGIN
  INSERT INTO evidence_event(at, analysis_id, job_id, kind, subject, payload_json)
  VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), NEW.analysis_id, NEW.job_id, 'JOB_CANCEL_REQUESTED', NEW.kind, json_object('status', NEW.status));
END;

CREATE TRIGGER trg_job_event_status AFTER UPDATE OF status ON job
WHEN OLD.status <> NEW.status AND NEW.status <> 'RUNNING'
BEGIN
  INSERT INTO evidence_event(at, analysis_id, job_id, kind, subject, payload_json)
  SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), NEW.analysis_id, NEW.job_id, 'JOB_CANCEL_REQUESTED', NEW.kind, json_object('status', OLD.status)
  WHERE OLD.cancel_requested = 0 AND NEW.cancel_requested = 1;
  INSERT INTO evidence_event(at, analysis_id, job_id, kind, subject, payload_json)
  VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), NEW.analysis_id, NEW.job_id,
          CASE NEW.status WHEN 'QUEUED' THEN 'JOB_RETRIED' WHEN 'DONE' THEN 'JOB_DONE' WHEN 'FAILED' THEN 'JOB_FAILED' ELSE 'JOB_CANCELLED' END,
          NEW.kind, json_object('from', OLD.status, 'to', NEW.status, 'attempt', NEW.attempts));
END;
