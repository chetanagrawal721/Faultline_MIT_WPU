# Faultline: The Incremental Witness, revised methodology

Status: **DRAFT 2 for confirmation** (five review corrections applied: crash-safe DDMin test identity, explicit pair-key inputs, request-to-job cancellation mapping, a precise rebuild procedure, and incremental delivery with gates passed only on recorded test results). No code has been changed for the twist. The implementation playbook is written only after this document is confirmed.

This replaces the generic methodology `FAULTLINE_Incremental_Witness_Engineering_Methodology` with one fitted to the Faultline code as it is today. It follows the master specification (`docs/FAULTLINE_MASTER.md`), which stays canonical; every place where the twist departs from it is recorded in an ADR (section 13).

## 1. The twist

Move Faultline from mutable storage to a content-addressed, append-only evidence store; persist the delta-debugging (DDMin) state after every sandbox test so an interrupted minimisation resumes; and expose Faultline as an LSP 3.17 server over stdio for Python consumers, shown in a real editor. The existing SQL analysis workflow must keep working. Implementing the twist earns bonus points; leaving it out costs points. The jury verifies it live.

## 2. Decisions already taken

| # | Decision |
|---|---|
| D1 | Evidence is stored as immutable, content-addressed objects. SQL result tables become rebuildable projections of those objects. Job state stays mutable, and every state transition is also written to an append-only event log. The existing SQL workflow keeps working. |
| D2 | The verdict-to-severity mapping is provisional until the verdict semantics are audited and written into the ADR. The mapping in section 9.3 is a draft. |
| D3 | The LSP server uses `pygls`, pinned and verified for LSP 3.17. `$/cancelRequest` is wired explicitly into the existing job cancellation and container termination. |
| D4 | VS Code is the demonstrated editor. Neovim is optional. |
| D5 | Planning window is 1 to 2 days. Priorities in section 12 follow from that, and are adjusted once the real jury schedule is known. |

## 3. Baseline: what exists today

Found by reading the code, not assumed.

| Area | Today | Consequence |
|---|---|---|
| Hashing | Canonical `object_hash` and `content_hash` in `core/hashing.py`; `env_profile_id` hashes the environment profile | Reuse these. No second serializer. |
| Worlds | `resolved_world` is keyed by `world_hash`. Audited in `core/hashing.py`: it covers ecosystem, runtime name and version, `env_profile_id` (image reference with digest, OS, architecture, locale, time zone, seed) and every resolved entry (name, version, source, artifact digest). It does **not** cover the resolver name and version, the lockfile or manifest digest, or the commit SHA. Snapshots are keyed by commit SHA | World identity is content-addressed for what is installed, but the twist's four inputs are not all in it. The pair key records them explicitly (6.1). |
| Cells | `cell.id = hash(analysis_id, producer project, projection key)`, unique per analysis | A producer-consumer pair has no identity across analyses. This is the main gap for reuse. |
| Result tables | `persist_cell`, attribution `persist` and `write_live_finding` use `DELETE` then `INSERT` | Results are mutable today. They must become append-only. |
| Run provenance | `oracle_run.provenance` already allows `FRESH_EXECUTION` and `REUSED_RESULT`; `witness_key` is UNIQUE | The vocabulary for reuse exists. |
| DDMin | `attribution/ddmin.py` is a pure function; its memo of tested subsets lives only in memory; `attribution_attempt` rows are written only after the whole search | A crash loses the whole search. |
| Attribution | Runs inline in the analysis job, under the job's lease; a retried job is a new analysis (`analysis/lifecycle.py`) | Resume state must be found by content, not by analysis id. |
| Cancellation | The worker heartbeat reads `cancel_requested`; `SandboxClient.cancel(group)` kills the containers started for a job | Cancellation reaches containers already. The LSP bridge calls this. |
| Call sites | `usage_ref` and the O-bind sites carry file, line and column. An import witness carries exception frames only | A diagnostic line comes from these; section 9.4. |
| Fix | `remediation/minimal.py` produces a constraint diff for the consumer's requirements file, labelled VERIFIED only after fresh runs; import witnesses only | The code action edits the requirements file, not the call-site. |
| Toolchain | Python 3.12 pinned; `pygls` and `lsprotocol` are not in `uv.lock`; VS Code is installed on the demo machine; Neovim is not | Dependency pinning and a VS Code client extension are part of the work. |

## 4. Principles

1. One analysis engine. The web UI, the API and the LSP server are clients of the same services. The LSP server never analyses anything itself.
   Sandbox boundary: untrusted code (analysed repositories, packages, install scripts, tests) runs only in the sandbox. The trusted control plane (API, worker, store, LSP server, editor extension) runs outside it and never executes analysed code.
2. A stored result is written once and never edited. A newer result is a new object.
3. A reused result is labelled reused, with the ids of the runs that produced it. A reused result never counts as one of the 3 + 3 fresh runs of a new witness. Reuse happens at pair level (a whole stored result), never inside a witness.
4. Infrastructure failure, timeout, cancellation and an unbuildable world are never a dependency failure and never a witness.
5. Counters are derived from stored events, never from in-memory variables, and are never adjusted by hand.
6. If an object is missing, corrupt, or from an unsupported schema, it is not used. The pair recomputes, or the result is reported unavailable.
7. The LLM is not in any decision path, and the product works with it off.
8. No weakening of a check, and no change of an expected value, to make a test pass.

## 5. Evidence store (T1)

### 5.1 Objects

Each object is canonical JSON stored under its own hash. The hash input is `kind`, the key-schema version and the canonical payload, so two kinds can never collide.

| Kind | Identity inputs | Notes |
|---|---|---|
| `world` | The existing `world_hash` inputs | Already content-addressed. Referenced, not duplicated. |
| `oracle_result` | Oracle and version, image digest, world hash, artifact content hash, entries, run index | One object per fresh run. Provenance is `FRESH_EXECUTION`. |
| `witness` | Pair key, oracle and version, entry, normalized signature, ids of the 3 + 3 runs | Carries the witness rule, never a cached run. |
| `attribution` | Witness id, DDMin algorithm version, final minimal set, attempt ids | Forced worlds stay labelled as experiments. |
| `verdict` | Pair key, evidence object ids, verdict-rule version (`verdict-policy/1`) | Can be recomputed from the evidence by the decision table. |
| `fix_plan` | Finding, constraint, gate results, fresh run ids, hash of the file it edits | Used by the code action. |
| `ddmin_checkpoint` | Minimisation id, sequence, state, memo reference, parent checkpoint | Section 7. |

Pointers (for example "current verdict of this pair") are SQL rows. Objects hold the evidence, and SQL holds indexes, pointers and the mutable job state. SQL is never the only copy of any evidence.

### 5.2 Required operations

`put(kind, payload)` canonicalises, hashes, writes atomically (temporary file, digest check, rename) and returns the id; the same content returns the same id. `get(id)` verifies the digest and schema and reports missing, corrupt or unsupported explicitly. `link(parent, relation, child)` appends a provenance edge. `lookup(key)` returns a complete, schema-matching object or nothing. `append_event(event)` appends to the event log.

Concurrency: two writers of the same content both succeed and one object exists. A crash between object write and SQL linking is repaired by a reconciliation pass that links what is missing and never deletes valid objects. `retention.py` keeps its rule of never removing evidence a finding refers to.

### 5.3 Result tables as projections

Write order is object first, then SQL row. The tables `witness`, `attribution`, `finding`, `remediation_plan`, `oracle_run` and `evidence_bundle` become projections: the code that writes them stops using `DELETE` then `INSERT` and instead records a new object and moves a pointer.

**Rebuild procedure (`rebuild`).** The rebuild only reads objects and only writes projection rows. It never deletes or rewrites an object.
1. Discover: list every object file in the store and check each one: the file name equals the digest of its canonical content, the schema version is supported, and the kind is known. Objects that fail are reported and skipped, never deleted, and every skip is a `REJECTED` event.
2. Order: process kinds in dependency order (worlds, oracle results, witnesses, attributions, fix plans, verdicts, pair records). A record whose referenced object is missing is skipped and reported, so a projection row never points at nothing.
3. Duplicates: an identical object found twice is one object. If two different objects claim the same projection key (for example two verdicts for one pair), the one linked by the later `evidence_event` pointer move wins, and the other stays in the store as history.
4. Pointers: recreate "current" pointers (current verdict of a pair, current attribution of a witness, current fix plan of a finding) by replaying the pointer events in order.
5. Write: create the projection rows in one transaction in a scratch database, then swap them in, so a failed rebuild leaves the previous tables untouched.
6. Verify: report counts per kind, and compare the REST responses (findings, witnesses, attribution, remediation, evidence, counters) before and after.

T1 runs it on the real demo store: snapshot the responses, empty the projection tables, rebuild, compare. It also runs it with a corrupt object and a missing object in the store and requires a clean report and an unchanged object directory.

### 5.4 Job state and the event log

The `job` table remains the mutable state machine the worker uses. Every transition (queued, claimed, heartbeat, retried, cancel requested, cancelled, done, failed) is also appended to an `evidence_event` log with job id, attempt, timestamp and correlation id. State at any past time can be read from the log.

## 6. Pair identity and incremental recomputation (T2)

### 6.1 Pair key

A pair is a producer artifact tested in a consumer's projected world, which is what Faultline calls a cell. Its content key is:

The pair key is a hash of an explicit, canonical record. Nothing is left to be implied by another hash:

| Input in the key | Why |
|---|---|
| Producer repository and pinned commit SHA; consumer repository and pinned commit SHA | Twist input; also covers the producer artifact source |
| Producer artifact content hash (the tree that is installed or imported) | Detects a source change that does not change the commit's lockfile |
| Lockfile or manifest digest for the reference world and for the consumer world (or the digest of the pinned requirement set when uv resolved it) | Twist input |
| Reference world hash and consumer world hash | What is installed (entries, runtime, environment profile) |
| Resolver name and version (the pinned `uv`), and only those resolution settings that can change the resolved result (for example a resolution timestamp, when the resolver output depends on it; never the wall-clock time of the run) | Twist input; not in `world_hash` |
| Platform: OS, architecture, runtime version | Twist input; in `env_profile_id` and recorded again explicitly |
| Consumer entry modules and the hashes of the files they come from | The checks run on them |
| Oracle names and versions, harness version, sandbox image digest | A different oracle or image is a different execution |
| Witness rule (3 + 3) and verdict-rule version | A rule change must not reuse old verdicts |

The audit task A0 re-checks this table against the code before the key is frozen. A test changes each input one at a time and requires the key to change (the key mutation matrix).

### 6.2 Algorithm

1. Pin each repository to a commit and build the snapshot as today.
2. Compute the pair key for every pair.
3. For each pair: if a complete, verified object exists for the key, reuse it (event `REUSED`); if an object exists but fails verification, event `REJECTED` and recompute; otherwise run the full pipeline (event `RECOMPUTED`).
4. A change anywhere in the key changes the key, so invalidation needs no separate graph: an unaffected pair has the same key and is found. A change to the oracle, image, resolver or rule version changes every key that depends on it.
5. A new analysis builds its findings from the reused and recomputed pair objects.

### 6.3 Counters

Counters are computed from `evidence_event`, per analysis and per kind, and are shown in the UI with reused, recomputed and rejected side by side.

| Counter | Counts |
|---|---|
| Pairs reused | A complete verified pair object was found for the key |
| Pairs recomputed | The pipeline ran for the pair (attempt and completion are separate events) |
| Results rejected | An object was missing, corrupt, or from another schema and was not used |
| Worlds reused / built | An existing world was found / a world build ran |
| DDMin tests resumed / run | Completed tests taken from a checkpoint / sandbox tests executed |

A scheduled pair is not counted as recomputed until it finishes; a crash never inflates a completion count.

## 7. Persistent DDMin (T3)

### 7.1 State

`ddmin()` becomes a resumable state machine. Its full state is the phase (singleton pre-check, full-set check, reduction loop, finalisation), the current candidate set `c`, the granularity `n`, and the chunk index `i`, plus the memo of completed tests. Pending tests are not stored: the next test is derived deterministically from this state.

### 7.2 Checkpoint protocol

Every test has a **stable test identity**: `test_id = hash(minimisation_id, candidate subset, direction)`. It does not depend on the analysis, the job attempt or the time.

For each test, in this order:
1. Look up `test_id` in the store. If a complete `oracle_result` object exists for it, take its outcome (reconcile) and do not run the sandbox.
2. Otherwise append an `attempt` event with the `test_id` (state `STARTED`) and run the sandbox.
3. When the sandbox returns, write the `oracle_result` object with the `test_id` inside it, then append the attempt event `FINISHED`.
4. Append the next `ddmin_checkpoint`: monotonic `seq`, the state above, the memo reference, the consumed budget (tests used and seconds used, not a clock reading), and the parent checkpoint.
5. Only then start the next test.

The memo is therefore not a separate source of truth: it is the set of `oracle_result` objects whose `test_id` belongs to this minimisation, and a checkpoint is an index into it.

Crash points and what recovery does:

| Crash point | Recovery |
|---|---|
| Before the attempt event | The test is not in the store; it runs normally. |
| After `STARTED`, sandbox still running or lost | No result object exists. The attempt is marked `INTERRUPTED` (never a failure), any container of the old job is removed, and the test runs again. This test did not complete, so it is the only one that may run twice. |
| Sandbox finished, result object not yet written | Same as above: the result was never durable, so the test runs again. This is the one window that cannot be closed without storing results inside the container; the plan records it as a stated limit, and the demo uses a kill at a point after a result is stored. |
| Result object written, checkpoint not yet appended | On resume, step 1 finds the result by `test_id` and the missing checkpoint is appended. The test is not run again. |
| Checkpoint appended | Resume continues from the next test. |
| Two workers resume together | The unique `(minimisation_id, seq)` constraint lets only one advance. |

T3 kills the worker in the "result written, checkpoint not yet appended" window by fault injection (a test hook that exits at that point), and separately kills it in the middle of a sandbox run. Both must show that no test whose result was durable runs twice, checked against the sandbox run log.

The checkpoint chain is keyed by `minimisation_id = hash(pair key, witness signature, candidate set digest, DDMin algorithm version)`. It is therefore found by a retried job, which is a new analysis. A unique `(minimisation_id, seq)` constraint prevents two writers from advancing the same chain. The sufficiency and necessity checks that follow the search are recorded in the same chain.

### 7.3 Resume

On start, load the latest valid checkpoint, verify its hash, schema and input identity, replay the deterministic algorithm against the memo (completed tests are looked up, not run), and continue with the first test not in the memo. An interrupted test (the worker died mid-run) is not in the memo, and is recorded as `INTERRUPTED`, never as a failure. If the latest checkpoint is corrupt, fall back to the previous valid one or report the problem. A changed input or algorithm version starts a new chain, and the old one stays as history.

### 7.4 Honest results

Timeouts, cancellation and build failures are `UNRESOLVED` or `INTERRUPTED`. When the budget runs out the result is `BUDGET_LIMITED` with the smallest failing set found so far, and the word "minimal" is not used. Non-monotonic behaviour is reported, as today.

### 7.5 Fixture

A deterministic fixture with about eight differing packages between the reference and consumer worlds, where exactly one of them causes a verified failure. Every other change is harmless. The fixture is published to GitHub the same way as the existing demo fixtures and covered by a label in `fixtures/`. The expected minimal set is written down before the first run.

## 8. Jury demonstrations

Both start from a genuine warm run; nothing is pre-filled.

**Demo A: incremental reuse.** The cold run of five producer-consumer pairs (five recomputed, none reused) is done beforehand as setup, its evidence is kept, and the live demo starts from that warm store. Re-run unchanged: five reused, none recomputed. Change one producer revision (a commit that alters the producer's artifact) and re-run: only the pairs that depend on that producer recompute, the rest are reused, and the counters and the event log agree.

**Demo B: DDMin recovery.** Start attribution on the eight-candidate fixture. After a few completed tests, stop the worker process for real. Restart it. Show the checkpoint sequence, the tests taken from the memo, the tests newly run, and that no completed test ran twice (checked against the sandbox run log). The final minimal set matches the label.

## 9. LSP 3.17 server (T4, T5)

### 9.1 Shape

`VS Code <-> Faultline LSP (stdio, pygls) <-> Faultline REST API <-> worker and sandbox`. The server reads findings and evidence through the API, and starts and cancels jobs through the API. It holds no analysis logic. When the API is unreachable it says so; it never shows a clean result because a backend is down.

### 9.2 Transport

stdout carries protocol frames only; logs go to stderr. On Windows the stdio streams are put in binary mode so that `Content-Length` framing is not corrupted by line-ending translation. A framing test sends messages containing `\n` and non-ASCII text through the real process. The `pygls` and `lsprotocol` versions are pinned in `pyproject.toml` and `uv.lock`, checked by `tools/fl.py check-pins`, and verified to implement LSP 3.17 before use.

### 9.3 Diagnostics and severity (provisional)

`textDocument/publishDiagnostics` carries URI, zero-based range, severity, message, `source: "faultline"`, a code that is the finding id, and data holding the finding id, verdict, pinned commit and evidence summary. Messages use only the exact verdict words.

Draft mapping, to be confirmed in the ADR after the audit of the verdict semantics (task A0):

| Verdict | Draft severity |
|---|---|
| BREAK WITNESSED | Error |
| SILENT DIVERGENCE WITNESSED | Warning |
| EXPOSED | Warning or Information (decide in audit) |
| POTENTIAL | Information |
| INCONCLUSIVE, HYGIENE | Hint |
| NO DIVERGENCE OBSERVED, NOT EXPOSED | no diagnostic |

At least four distinct severities are demonstrated with fixtures that produce those verdicts.

### 9.4 Locations

Line numbers come only from data Faultline holds: the usage index (`usage_ref`) and the O-bind sites for calls, and the import statement of the failing entry for import witnesses. The audit checks what each witness type provides. Where no precise line is known, the diagnostic is placed on the import line with a message saying the location is the import, never a made-up call-site. Positions are converted between the one-based parser lines and the zero-based protocol. Diagnostics carry the hash of the file they were computed against; if the open document differs, they are marked stale instead of being placed on changed text.

### 9.5 Code actions

`textDocument/codeAction` returns a quick fix only when the finding has a remediation plan labelled VERIFIED, the plan's recorded hash of the requirements file equals the file's current hash, and the plan is for an import witness (the only kind remediation supports). The `WorkspaceEdit` edits the consumer's requirements file (the constraint that the verified plan pins), not the call-site, and references the diagnostic it fixes. No action is returned for unverified, partially verified, stale or unsupported cases. Nothing is saved, committed or pushed by Faultline. After the user applies the edit, a new analysis shows that only the affected pair recomputes.

### 9.6 Cancellation

**Which request is cancellable.** Analysis is started by one LSP request: the custom request `faultline/analyze` (sent by a command in the VS Code extension, and by `workspace/executeCommand` for clients without the extension). It is the only long-running request. `textDocument/codeAction` and the diagnostic pushes are quick reads and are not cancellable work.

**Mapping.** When `faultline/analyze` arrives, the server creates the Faultline job through the API with an idempotency key built from the LSP session and request id, and stores `request id -> job id` in a table that lives as long as the request. The request is answered when the job reaches a final state.

**On `$/cancelRequest`:**
1. Look up the job id. An unknown id (already finished, or never started) is ignored.
2. Mark the mapping cancelled first, so any result arriving later is dropped and publishes no diagnostics.
3. Call the existing job cancel endpoint. The worker's heartbeat sees `cancel_requested` and calls `SandboxClient.cancel(job_id)`, which stops the job's containers. The analysis keeps its partial evidence, as in `analysis/lifecycle.py`.
4. Answer the original request with the LSP `RequestCancelled` error.
5. The job ends `CANCELLED`. A cancelled run is never a witness, never a dependency failure and never a sandbox failure.

**Races and repeats, each with a test:** repeated `$/cancelRequest` for the same id (no second effect); cancel before the job is created (the job is cancelled as soon as it exists, or never started); cancel arriving as the job finishes (the final state wins, and stale diagnostics are dropped); cancel while a DDMin test is running (the container is removed and the checkpoint chain stays valid and resumable); cancel after the server lost the API connection (reported as unavailable, nothing shown as cancelled that was not).

**Cleanup check.** T5 checks with `docker ps` that no container labelled with the job id remains, records the time from request to stop, and reads the job status and the event log to confirm `CANCELLED`.

### 9.7 VS Code client

VS Code does not start an arbitrary stdio server from a configuration file, so a small client extension (`vscode-languageclient`, pinned) is part of the work. It is run in the Extension Development Host from the repository, with a documented one-command launch. Neovim is documented as optional and is not required for any gate.

## 10. Backward support for the SQL workflow (T6)

Migration `0007` only adds tables (object index, event log, checkpoints, pair index). The REST API, the OpenAPI types and the UI keep their current responses. The store is behind a setting; the full existing unit and integration suites run with it off and with it on. The old and new paths must return the same findings for the same inputs, checked by a comparison test.

## 11. Gates

| Gate | Requirement | Evidence |
|---|---|---|
| T1 Storage | Key determinism; atomic publish; tamper rejection; concurrent identical writes; crash between write and link repaired; result tables rebuilt from objects with identical API responses | Unit and integration tests, rebuild comparison |
| T2 Incremental reuse | Unchanged inputs give all pairs reused; a changed producer recomputes only the pairs that depend on it; counters equal the event log; a corrupt object is rejected and recomputed | Demo A run on real executions |
| T3 DDMin recovery | Kill the worker mid-search; restart; resume from a checkpoint; no completed test re-run; corrupt checkpoint handled; budget-limited result honest | Demo B run on real executions, sandbox run log |
| T4 LSP diagnostics | Clean stdio on Windows; initialize and shutdown; diagnostics on the correct lines in VS Code; at least four severities; stale diagnostics marked | Protocol tests plus a recorded VS Code session |
| T5 Fixes and cancellation | Verified fix gives a `WorkspaceEdit` on the right file; unverified and stale give none; `$/cancelRequest` stops the container; no orphan; state is `CANCELLED`, not a failure | Protocol tests plus live `docker ps` check |
| T6 Regression | Existing unit, integration, replay and security tests pass with the store on and off; CI green | Test output saved under `evidence/` |

Gates follow the repository process: each test case's real output is saved under `evidence/` and recorded with `tools/track.py`; a milestone is not called done until the tracker accepts it.

## 12. Priorities for a 1 to 2 day window

**Must (the twist as the jury reads it):** the evidence store with projections and the event log; pair keys and the reused / recomputed / rejected counters in the UI; persistent and resumable DDMin with the eight-candidate fixture; the stdio LSP server in VS Code with diagnostics, one verified code action, and real cancellation; the SQL workflow still passing.

**Should:** the rebuild command and its comparison test; stale-diagnostic handling; the corrupt-checkpoint fallback; both demos scripted and rehearsed from a warm store; the ADR and the playbook entries.

**Stretch (only if time remains):** Neovim configuration; multiple editor clients sharing one computation; garbage collection beyond the existing retention rule; property-based key tests.

The full required scope stays. It is built in small increments, each ending in tests that pass before the next starts:

1. **Audit and ADR.** Re-check every baseline claim in section 3 against the code and record the result; fix the severity semantics. Nothing else starts before this.
2. **Storage and recovery invariants.** Store, keys, atomic writes, event log, projections, rebuild, tamper and crash tests (T1). These invariants hold before anything depends on them.
3. **Pair reuse and counters** (T2).
4. **Resumable DDMin and the fixture** (T3), including the crash-window tests.
5. **A VS Code vertical slice.** Minimal stdio server, extension, one real diagnostic on the correct line, in the real editor. This is demonstrated before the remaining LSP features are added.
6. **Remaining LSP features.** Severities, stale handling, the verified code action, cancellation (T4, T5).
7. **Regression and rehearsal** (T6), then the two demos from a warm store.

Steps 5 and 6 can overlap with steps 3 and 4, because the server can first read findings that already exist.

The 1 to 2 day window is a target, not a promise. The full scope is kept; if time runs out, unfinished milestones and gates are reported as unfinished.

**A gate is passed only when its tests have run and their real output is recorded.** Code that exists but whose gate tests have not passed is reported as "implemented, not verified". The final report keeps three lists apart: verified (gate passed, evidence saved), implemented but not verified, and not done.

## 13. Repository process

1. Add the twist as a new phase in `playbook/phases/*.yaml`, with milestones and test cases for T1 to T6, and regenerate the playbook through the tracker. `docs/FAULTLINE_PLAYBOOK.md`, `CHECKLIST.md` and `LOGBOOK.md` are not edited by hand.
2. Write ADR 0008, "Incremental Witness: evidence store, resumable minimisation, LSP". It records the departures from the master (SQLite results become projections of immutable objects), the final severity mapping, the pair key, the checkpoint format, and the cancellation path.
3. Commit with the milestone id first, in the four accounts' names, to the `Faultline_MIT_WPU` repository.

## 14. Risks and how they are handled

| Risk | Handling |
|---|---|
| A cold analysis takes 200 to 400 seconds | The store is warmed with a genuine run before the demo; the second run then shows the benefit. A warm store is shipped with the demo release. |
| Jury pastes their own repositories | The first run takes minutes; this is stated, and the LSP shows progress and supports cancel. |
| Docker Desktop is not running | `tools/fl.py` and the demo check report it before the demo starts. |
| Windows stdio framing | Binary mode and a real-process framing test (9.2). |
| The pinned `pygls` does not handle cancellation as needed | Cancellation is implemented in Faultline's own bridge, not left to the library; if the pin fails verification, a small hand-written server is the fallback. |
| Diagnostic line is not available for a witness | Import line with an explicit message; never an invented call-site (9.4). |
| Resume demo needs a long enough search | The eight-candidate fixture (7.5). |
| Time | Priorities in section 12. |

## 15. What is not claimed

Nothing in this document is implemented yet. Every statement about existing code is from reading it; each is re-checked in audit task A0 before design is frozen. After the build, the final report separates what is implemented and verified, what is assumed, and what remains.
