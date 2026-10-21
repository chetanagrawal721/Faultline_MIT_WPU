# ADR 0008: Incremental Witness: evidence store, resumable minimisation and the language server

Status: accepted, 2026-10-21.

## Context

The hackathon twist "The Incremental Witness" asks for three things: a content-addressed, append-only evidence store with incremental recomputation and live counters; persistent, resumable delta-debugging state; and an LSP 3.17 server over stdio shown in a real editor. The original SQL workflow must keep working. The master specification describes a SQLite store whose result rows are mutable; the twist departs from that, so the departure is recorded here. The audit of the code is in `docs/INCREMENTAL_WITNESS_AUDIT.md`; the method is in `docs/INCREMENTAL_WITNESS_METHODOLOGY.md`.

## Decisions

### 1. Evidence objects and projections

- Evidence is stored as immutable objects: canonical JSON, one file per object, named by its hash. The id is `sha256(kind + "/" + schema_version + "\n" + canonical_payload)`. The store lives in `var/evidence/objects/<first two hex>/<id>.json` (the `var/` folder is already ignored by git).
- Kinds and schema versions (all version 1): `oracle_result`, `witness`, `attribution`, `verdict`, `fix_plan`, `pair_record`, `ddmin_checkpoint`, `ddmin_test`, `consumer_imports`, `world_ref`.
- The SQL tables `witness`, `attribution`, `attribution_attempt`, `finding`, `finding_evidence`, `remediation_plan` and `oracle_run` become **projections**: rows derived from objects, rebuildable with `tools/fl.py rebuild`. A writer builds the payload and calls `evidence/projections.py::write`, which stores the object (a new version, with a `slot` and a `seq`, when the thing can be superseded), moves the slot's pointer, records a `POINTER_MOVED` event, and then makes the SQL rows follow the object with the kind's `apply_*` function. That module is the only code that writes these rows, and `rebuild` calls the same `apply_*` functions, so a rebuilt row cannot differ from a live one. A row changes only to follow an object; nothing else updates or deletes it.
- Versions and slots: a slot names the thing (`finding:<cell>`, `witness:<witness_key>`, `attribution:<witness_key>`, `fix_plan:<id>`); the object with the highest `seq` is current. A witness re-verification, a recomputed verdict and a re-run attribution are new objects in the same slot. Oracle runs have no slot: each run is its own object.
- `oracle_job` is workflow state (it is created `RUNNING` and finished `DONE` around the sandbox call) and stays an ordinary mutable table, like `job`. Its content needed to recreate it is carried by the `oracle_result` object, so a rebuild can restore a missing job row.
- Inventory, world and cache tables (`repository`, `snapshot`, `project`, `manifest`, `resolved_world`, `world_entry`, `usage_*`, `import_index`, `relationship*`, `analysis`) stay ordinary tables; they are not evidence.
- The `job` table stays a mutable state machine used by the worker. Every state change also appends an event in the same transaction.
- A migration `0007_evidence.sql` adds tables only. The setting `FAULTLINE_EVIDENCE_STORE=on|off` selects the new writers or the original ones; `off` is the regression baseline.

### 2. Events

`evidence_event` is append-only (triggers reject `UPDATE` and `DELETE`). Columns: id, time, analysis id, job id, kind, subject id, payload JSON. Event types:

`JOB_QUEUED`, `JOB_CLAIMED`, `JOB_RETRIED`, `JOB_CANCEL_REQUESTED`, `JOB_CANCELLED`, `JOB_DONE`, `JOB_FAILED`, `PAIR_REUSED`, `PAIR_RECOMPUTE_STARTED`, `PAIR_RECOMPUTE_DONE`, `OBJECT_REJECTED`, `WORLD_REUSED`, `WORLD_BUILT`, `DDMIN_ATTEMPT_STARTED`, `DDMIN_ATTEMPT_FINISHED`, `DDMIN_ATTEMPT_INTERRUPTED`, `DDMIN_TEST_RESUMED`, `DDMIN_CHECKPOINT`, `POINTER_MOVED`, `REBUILD_STARTED`, `REBUILD_DONE`.

Job events are written by database triggers on the `job` table in the same statement that changes the state, so no code path can skip them. A cancel request that also changes the status writes `JOB_CANCEL_REQUESTED` and then `JOB_CANCELLED`. Heartbeats are not events (the heartbeat time stays on the job row). Counters are computed from events and nothing else.

### 2a. Rebuild

`rebuild` is one transaction: it discovers and verifies every object, picks the highest `seq` of each slot, deletes the projection rows, applies the objects in dependency order (each inside a savepoint; a row whose parent is missing is skipped and reported), recomputes `object_index` and `pointer`, and compares a normalised dump of the evidence tables with the dump taken before. If anything differs, or rows that have no object would be lost, it rolls back and reports `REFUSED` (`--allow-loss` overrides this for a database that was written with the store off). A dry run does the same and always rolls back. Objects are never deleted, rewritten or moved. This replaces the "scratch database, then swap" wording of the methodology with an equivalent single SQLite transaction.

### 3. Pair key

`pair_key = sha256("pair/1\n" + canonical(PairKeyInput))`, with the record stored as a `pair_record` object beside the digest. `PairKeyInput`:

| Field | Source |
|---|---|
| `producer_repo`, `producer_commit`, `consumer_repo`, `consumer_commit` | pinned snapshots |
| `producer_artifact_sha256` | content hash of the installed or imported tree |
| `reference_lock_digest`, `consumer_lock_digest` | digest of the lockfile or pinned requirement set |
| `reference_world_hash`, `consumer_world_hash` | `world_hash` |
| `resolver`, `resolver_version` | the pinned `uv` |
| `resolution`: `exclude_newer`, `index` | only when uv resolved the world; absent for a pinned lockfile |
| `platform`: OS, architecture, runtime version | environment profile |
| `entries`: consumer entry modules with file SHA-256 | import scan |
| `oracles`: name, version and harness version for each oracle planned | oracle registry |
| `image_digest` | sandbox image |
| `witness_rule` (`3+3`), `verdict_rule` (`verdict-policy/1`) | policy |

Excluded: wall-clock times, local paths, analysis and job ids, the order of unordered collections.

### 4. DDMin checkpoint

- `minimisation_id = sha256(pair_key, witness signature, sorted candidate set digest, "ddmin/2")`. The algorithm version string is `ddmin/2` (the current in-memory algorithm is version 1).
- `test_id = sha256(minimisation_id, sorted subset, direction)`, direction one of `search`, `sufficiency`, `necessity`.
- `ddmin_checkpoint` payload: `schema_version`, `minimisation_id`, `seq`, `parent` (previous checkpoint id or null), `state` `{phase, c, n, i}` (phase one of `SINGLETONS`, `FULL`, `REDUCE`, `POST`, `DONE`), `tests` (list of `{test_id, outcome, oracle_result_id}`), `budget` `{tests_used, seconds_used, max_tests, max_seconds}`, `status` (`RUNNING`, `COMPLETE`, `BUDGET_LIMITED`, `CANCELLED`, `FAILED`).
- Outcomes: `FAIL`, `PASS`, `UNRESOLVED`, `INTERRUPTED`. Only `FAIL` counts as still failing, as today. `INTERRUPTED` and `UNRESOLVED` are never a cause.
- A unique key `(minimisation_id, seq)` allows one writer per step.
- Per-test order: look up `test_id` in the latest checkpoint, then among stored `ddmin_test` objects (slot `ddmin_test:<test_id>`); else `DDMIN_ATTEMPT_STARTED`, run, store a `ddmin_test` object with the outcome and a reference to the run's `oracle_result`, `DDMIN_ATTEMPT_FINISHED`, append the checkpoint. A test answered from the store emits `DDMIN_TEST_RESUMED`. A test whose process died has no `ddmin_test` object, gets `DDMIN_ATTEMPT_INTERRUPTED` and runs once more. A test that finished and was stored but whose checkpoint was never appended is found through its own object, not run again, and its missing checkpoint is added. The window between a finished sandbox run and the stored `ddmin_test` object is a known limit and is stated in the final report.
- The function that names a test is `identity_of_test` (a name starting with `test` would be collected by pytest). The algorithm version string is `ddmin/2`; the search reports `{phase, c, n, i, part}` before every test and returns the same results as version 1 (a frozen copy of version 1 is compared against it on 40 random oracles).
- A budget is stored as consumed tests and consumed seconds; tests answered from the store do not consume it again. If every checkpoint of a chain is damaged the resume fails with an explicit `ChainDamaged` error, although the individual `ddmin_test` objects are still in the store.

### 5. Severity mapping

Final, following the meaning of each verdict (audit section 6):

| Verdict | LSP severity | Reason |
|---|---|---|
| BREAK WITNESSED | Error | A reproducible failure under the witness rule |
| SILENT DIVERGENCE WITNESSED | Warning | Reproducible difference in output; harm is not established |
| EXPOSED | Warning | A changed symbol is referenced; execution did not settle it |
| POTENTIAL | Information | Breaking changes exist; usage not resolved |
| INCONCLUSIVE | Hint | Not enough evidence; the reason is shown |
| HYGIENE | Hint | Versions differ with no relationship; no source location, shown on the package |
| NO DIVERGENCE OBSERVED | none | Nothing diverged in what was exercised |
| NOT EXPOSED | none | No resolved reference touches a changed symbol |

An unknown verdict raises an error. Messages use only the exact verdict words. The live pipeline produces BREAK WITNESSED, SILENT DIVERGENCE WITNESSED, INCONCLUSIVE and no-diagnostic cases today; EXPOSED, POTENTIAL and NOT EXPOSED come from static analysis that is not wired into the live run, so they are mapped and unit-tested but not shown live.

### 6. Language server

- `pygls==2.1.1` with `lsprotocol==2025.0.0` (LSP 3.17), pinned in `pyproject.toml` and `uv.lock`.
- The server is a client of the REST API. It reads findings, evidence and the stored consumer import sites; it starts and cancels jobs through the API. It never runs analysed code.
- Methods: `initialize`, `initialized`, `shutdown`, `exit`, `textDocument/didOpen`, `didChange`, `didSave`, `didClose`, `textDocument/publishDiagnostics` (push), `textDocument/codeAction`, `workspace/executeCommand`, `$/cancelRequest`, and the custom request `faultline/analyze`.
- Diagnostic location: for a consumer file, the import line of the affected module from the stored import scan (range: the whole line, since the scan has no column); for a producer file, the O-bind site (file, line, column) or the innermost artifact frame; otherwise no precise diagnostic.
- Code action: `quickfix`, only for a `fix_plan` labelled VERIFIED on an import witness whose recorded target-file hash equals the file's current hash. The `WorkspaceEdit` edits the consumer's requirements file.

### 7. Cancellation

`$/cancelRequest` → look up the request id in the request-to-job table → mark cancelled → `POST /api/jobs/{id}/cancel` → the worker's heartbeat sees `cancel_requested` → `SandboxClient.cancel(job_id)` removes the job's containers → the job ends `CANCELLED`. pygls itself only cancels the Python future of the handler; the explicit bridge above is what stops the sandbox. Worst-case delay before the kill is the heartbeat interval (10 s by default); the measured value is recorded by TC-13.10.1.

## Differences from the master

1. The master describes mutable result rows in SQLite. They become projections of immutable objects (decision 1).
2. The master has no event log or object store; both are added.
3. The master has no LSP server; it is added as a client of the existing API.

No verdict word, failure class, witness class or the 3 + 3 witness rule changes. The LLM stays out of every decision.

## Consequences

- Reused pair results are labelled as reused and are never counted as fresh runs inside a new witness. The existing run-level cache stays off for witnesses (`force=True`).
- The consumer import scan is stored from now on.
- Rebuilding projections never touches the object directory.
- The final report lists what was implemented and verified, what was implemented but not verified, and what was not done.
