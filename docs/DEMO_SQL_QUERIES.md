# SQL queries to run during the demo

Every query below was run against the real database (`var/faultline.db`) and returned rows. They are read only: the viewer accepts one `SELECT` at a time, opens the file with `mode=ro`, and is safe to run while the project is running.

How to run any query from a normal PowerShell (not the activated venv):

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/show_store.py --sql "<the query>"
```

Put the whole query in double quotes. Values inside the query use single quotes, as written here. Hashes are shortened with `substr(x,1,16)` so they fit on screen; drop the `substr` to see the full value. The numbers you see will differ from the examples, because they come from your own runs.

Companion commands (no SQL needed): `--hashes` (the tables that hold hashes, and one hash followed to its file), `--check` (re-hash every object), `--prove-append-only` (try to change an event, on a copy). See `docs/DEMO_COMPLETE.md`, Part 5b.

---

## A. The evidence store: objects, pointers, pair keys

### A1. What kinds of object are stored, and how many

```sql
SELECT kind, COUNT(*) AS n FROM object_index GROUP BY kind ORDER BY n DESC
```

You see: `oracle_result`, `ddmin_checkpoint`, `ddmin_test`, `verdict`, `consumer_imports`, `witness`, `pair_record`, `attribution`.

> **Say:** "Every proven thing is stored once as an immutable object. These are the kinds: the raw oracle runs, the witnesses, the verdicts, the attributions, the pair records, and the minimisation's checkpoints and tests."

### A2. The newest stored objects, with their hashes

```sql
SELECT substr(object_id,1,16) AS object, kind, substr(slot,1,34) AS slot, seq, created_at FROM object_index ORDER BY created_at DESC LIMIT 6
```

> **Say:** "The first column is the start of the object's SHA-256, which is also its file name in the evidence folder. The slot says what thing this is a version of; seq is the version number."

### A3. The pointers: which object is current

```sql
SELECT slot, seq, substr(object_id,1,16) AS current_object, moved_at FROM pointer ORDER BY moved_at DESC LIMIT 8
```

> **Say:** "A result is never edited. A new version is a new object with a new hash, and this pointer moves to it. The old object stays."

### A4. The pair keys: one per producer-consumer pair

```sql
SELECT substr(pair_key,1,22) AS pair_key, substr(pair_record_id,1,16) AS pair_record, substr(verdict_id,1,16) AS verdict, created_at FROM pair_index
```

> **Say:** "This is how reuse recognises a pair. The key is a hash of all its inputs. The row points at the stored pair record and at the stored verdict."

### A5. Which analysis used which pair key, and what it found

```sql
SELECT pc.analysis_id, substr(pc.pair_key,1,16) AS pair, f.verdict FROM pair_cell pc JOIN finding f ON f.cell_id = pc.cell_id ORDER BY pc.rowid DESC LIMIT 6
```

> **Say:** "Several analyses carry the same pair key and the same verdict. That is reuse: the later analyses did not compute it again."

---

## B. Reuse and recomputation (the counters on the Overview page)

### B1. Reused versus recomputed, per analysis

```sql
SELECT analysis_id, SUM(kind='PAIR_REUSED') AS reused, SUM(kind='PAIR_RECOMPUTE_DONE') AS recomputed, SUM(kind='OBJECT_REJECTED') AS rejected FROM evidence_event WHERE analysis_id IS NOT NULL GROUP BY analysis_id ORDER BY MAX(id) DESC LIMIT 5
```

> **Say:** "This is the same number that the Overview page shows, counted straight from the event log. A first run has recomputed 1 and reused 0. A repeat has reused 1 and recomputed 0. A damaged result would show up under rejected."

### B2. Why a pair was computed (the reason and what changed)

```sql
SELECT id, kind, json_extract(payload_json,'$.reason') AS reason, json_extract(payload_json,'$.changed') AS changed FROM evidence_event WHERE kind='PAIR_RECOMPUTE_STARTED' ORDER BY id DESC LIMIT 5
```

> **Say:** "NEW means nothing was stored for this pair. CHANGED would list the inputs that changed, for example the producer's commit and code hash. REJECTED means a stored object failed its hash check."

### B3. The reuse and recomputation events themselves

```sql
SELECT id, at, kind, substr(subject,1,24) AS subject FROM evidence_event WHERE kind LIKE 'PAIR_%' OR kind LIKE 'WORLD_%' ORDER BY id DESC LIMIT 10
```

### B4. Count of every kind of event

```sql
SELECT kind, COUNT(*) AS n FROM evidence_event GROUP BY kind ORDER BY n DESC
```

> **Say:** "This is the append-only log. Every job state change, every pointer move, every reuse and every test of the cause search is one row here."

---

## C. The resumable cause search (minimisation)

### C1. The checkpoints of the search, newest first

```sql
SELECT substr(minimisation_id,1,14) AS minimisation, seq, status, substr(object_id,1,16) AS checkpoint FROM ddmin_checkpoint ORDER BY rowid DESC LIMIT 6
```

> **Say:** "After every test the search saves a checkpoint object. The status is RUNNING until the search ends, then COMPLETE. A restarted worker reads the newest one."

### C2. Tests started, finished, resumed or interrupted

```sql
SELECT kind, COUNT(*) AS n FROM evidence_event WHERE kind LIKE 'DDMIN%' GROUP BY kind
```

> **Say:** "Started equals finished when every test finished. After a crash you would also see DDMIN_TEST_RESUMED for the tests answered from the store, and DDMIN_ATTEMPT_INTERRUPTED for the one that was cut off."

---

## D. Results: findings, witnesses, runs, deltas

### D1. Findings by verdict

```sql
SELECT verdict, COUNT(*) AS n FROM finding GROUP BY verdict ORDER BY n DESC
```

### D2. The newest witnesses: three passes against three failures

```sql
SELECT oracle, entry_point, ref_pass, test_fail FROM witness ORDER BY rowid DESC LIMIT 5
```

> **Say:** "ref_pass 3 and test_fail 3: the reference passed three times and the consumer failed three times. That is the witness rule."

### D3. The dependency delta behind a finding

```sql
SELECT d.name, d.v_ref, d.v_test FROM delta_entry d JOIN cell c ON c.id = d.cell_id ORDER BY d.rowid DESC LIMIT 6
```

> **Say:** "These are the packages whose versions differ between the two worlds: for example werkzeug 2.2.3 in the reference and 3.0.6 in the consumer."

### D4. Fresh executions per analysis

```sql
SELECT j.analysis_id, COUNT(*) AS fresh_runs FROM oracle_run r JOIN oracle_job j ON j.id = r.oracle_job_id WHERE r.provenance = 'FRESH_EXECUTION' GROUP BY j.analysis_id ORDER BY MAX(r.created_at) DESC LIMIT 5
```

> **Say:** "Every run here is marked FRESH_EXECUTION. An analysis that reused its result has no row here, because it ran nothing."

### D5. The evidence a finding cites

```sql
SELECT f.id, substr(e.evidence_id,1,18) AS evidence, e.evidence_kind FROM finding_evidence e JOIN finding f ON f.id = e.finding_id WHERE f.verdict = 'BREAK_WITNESSED' LIMIT 6
```

> **Say:** "A finding is not just a sentence. It lists the witnesses and the individual oracle runs it stands on."

---

## E. Inputs and worlds (hashes)

### E1. The pinned commits

```sql
SELECT substr(sha,1,12) AS commit_sha, repository_id, ingest_status FROM snapshot ORDER BY rowid DESC LIMIT 5
```

### E2. The dependency worlds and their hashes

```sql
SELECT substr(world_hash,1,24) AS world_hash, kind FROM resolved_world ORDER BY rowid DESC LIMIT 6
```

> **Say:** "A world is identified by the hash of its exact contents. The same world always gets the same hash, so a world that was already built can be reused."

### E3. The packages inside one world

```sql
SELECT locator, scope, source_kind FROM world_entry WHERE world_hash = (SELECT world_hash FROM resolved_world ORDER BY rowid DESC LIMIT 1) ORDER BY locator LIMIT 12
```

---

## F. Jobs and cancellation

### F1. Job history with outcomes

```sql
SELECT substr(job_id,1,22) AS job, kind, status FROM job ORDER BY rowid DESC LIMIT 8
```

### F2. The life of one job from the event log

```sql
SELECT id, at, kind FROM evidence_event WHERE job_id = (SELECT job_id FROM job WHERE kind='live_analysis' ORDER BY rowid DESC LIMIT 1) ORDER BY id
```

> **Say:** "JOB_QUEUED, JOB_CLAIMED, JOB_DONE. A job cancelled from the editor ends with JOB_CANCEL_REQUESTED and then JOB_CANCELLED."

---

## G. Proof that the log cannot be changed

SQL cannot be used for this from the viewer, because it only accepts `SELECT`. This command tries an `UPDATE` and a `DELETE` on a throw-away copy:

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/show_store.py --prove-append-only
```

You see: `refused by the database: evidence_event is append-only` twice.

> **Say:** "The event log is protected by the database itself, with triggers. I tried to change an event and to delete one, on a copy, and the database refused both. So the history the counters come from cannot be rewritten."

---

## H. Four queries for a 60-second version

1. A1: what is stored.
2. A4: the pair keys.
3. B1: reused versus recomputed.
4. D2: three against three.

## If a query returns "no such table" or no rows

- No rows: the project has not run an analysis yet. Run the main example first.
- `no such column`: the query was typed with a typo, or the database is older than schema v8. The viewer prints the schema version in its first section.
- Many `ddmin` rows are only produced by analyses that found a break and searched for its cause.
