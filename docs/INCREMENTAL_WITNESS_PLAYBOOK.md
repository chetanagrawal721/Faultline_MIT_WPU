 # Faultline: The Incremental Witness, implementation playbook

Status: **DRAFT 2 for confirmation** (four review corrections applied: cold run is setup and the live demo starts warm; only result-affecting resolver settings enter the key; the sandbox boundary covers untrusted code, not the trusted control plane; the time target is not a promise). No code has been changed for the twist. This playbook implements `docs/INCREMENTAL_WITNESS_METHODOLOGY.md` (Draft 2), which it does not repeat; read that first.

## How to use this playbook

- It is one new phase, **Phase 13**, with milestones `M13.0` to `M13.12` and six gates `T1` to `T6`.
- **Step zero of the build (M13.0)** converts this document into `playbook/phases/phase13.yaml` and adds the gates and the phase to `playbook/phases.yaml`. After that, progress is recorded only with `tools/track.py`; `LOGBOOK.md`, `CHECKLIST.md`, `docs/FAULTLINE_PLAYBOOK.md` and `playbook/state.json` are never edited by hand.
- Per milestone: `python tools/track.py start M13.x`, run each test case, save the real output to `evidence/M13.x/TC-13.x.y.txt`, record it with `tools/track.py tc`, then `done`. A milestone or gate is complete only when the tracker accepts it. A test case that fails is recorded as failed and the cause is fixed; no check is weakened and no expected value changed.
- Commit with the milestone id first, as one of the four accounts, to `Faultline_MIT_WPU` (see the standing workflow).
- Test case kinds: `auto` (pytest or script, no Docker), `docker` (needs the sandbox), `live` (needs GitHub and the full stack), `manual` (a person looks, with a recording or screenshot saved as evidence).
- Fixed rules from `CLAUDE.md` apply throughout: verdict words exactly as defined, 3 fresh + 3 fresh runs for a witness, cached results never count as repeats, infrastructure failures are never witnesses, no LLM in any decision, no invented numbers.
- **Sandbox boundary, stated precisely.** The rule "no code outside the sandbox" is about *untrusted* code: repository code, package code, package install scripts, and test code from analysed repositories run only in the sandbox, through `SandboxClient` to `sandboxd`, in an allowlisted image. Faultline's own *trusted control plane* runs outside it by design: the API, the worker and orchestration, the object store, the LSP server and the VS Code extension. The LSP server and the extension never import, execute or evaluate analysed code; they read findings through the API and read the open file as text. If the boundary cannot be verified, execution is disabled, as before.
- **Time.** The full scope stays. Nothing here is guaranteed to fit in one or two days. If time runs short, the unfinished milestones and gates are reported as unfinished, with what is implemented but not verified listed separately; no gate is declared and no milestone is marked done without recorded passing evidence.

## Dependency map

```
M13.0 audit, ADR, tracker
   |
M13.1 object store ---- M13.2 events, projections, rebuild ---- [T1]
   |                         |
M13.3 pair key ------- M13.4 incremental analysis, counters ---- [T2]
   |
M13.5 resumable DDMin ---- M13.6 recovery in the pipeline, fixture ---- [T3]
   |
M13.7 stdio LSP + VS Code slice ---- M13.8 diagnostics ---- [T4]
                                         |
                       M13.9 code action ---- M13.10 cancellation ---- [T5]
                                                         |
                                  M13.11 regression ---- M13.12 demos and report ---- [T6]
```

M13.7 and M13.8 only need existing findings, so they can start after M13.0 and run alongside M13.3 to M13.6. M13.9 needs the verified fix object (M13.1). M13.10 needs the job event log (M13.2). M13.11 and M13.12 need everything.

---

## M13.0 Audit, ADR and tracker setup

**Objective.** Confirm every baseline claim against the code, freeze the design decisions that were provisional, and register the phase.

**Files.** `docs/adr/0008-incremental-witness.md` (new), `docs/conformance/` matrix row for the twist, `playbook/phases/phase13.yaml` (new), `playbook/phases.yaml` (gates T1 to T6 and phase 13), `docs/INCREMENTAL_WITNESS_AUDIT.md` (new, the audit record).

**Steps.**
1. Record the baseline: branch, commit, dirty state, `uv.lock` and image digests, migration list, OpenAPI hash. Run the 394 unit tests and the three previously failing integration tests (`test_durable`, `test_remediation`, `test_rerun`) and record the result, including anything already failing.
2. For each row of methodology section 3, read the code and write confirmed / corrected / not found in the audit record. Mandatory checks: `world_hash` inputs; every `DELETE`/`INSERT` result-table writer (list them all: `persist_cell`, attribution `persist`, `write_live_finding`, bundle and remediation writers); where `ddmin()` is called and what survives a worker death; which witness types carry a consumer line (import frames, O-bind sites, `usage_ref`, test ids, contract inputs); the exact meaning of each verdict for severity; the cancel endpoint and its latency.
3. Choose and record the **five demo pairs** from the existing fixtures (at least two producers, so a single producer change leaves some pairs unaffected) and list their expected verdicts.
4. Decide the object-store location and layout (default `var/evidence/objects/<2-hex>/<digest>.json`), the key-schema version string, and the migration number `0007`.
5. Write ADR 0008: store and projections, pair key, checkpoint format and `test_id`, severity mapping (final), cancellation path, and every departure from the master specification.
6. Verify `pygls` and `lsprotocol` versions: LSP 3.17 support, Python 3.12 wheels, hash-pinnable, cancellation behaviour. Record the versions chosen, or record why the fallback (a small hand-written server) is used.
7. Write `phase13.yaml` from this playbook and add the gates; run `python tools/track.py status` and confirm Phase 13 appears.

**Data / control flow.** None; documents and configuration only.

**Interfaces.** The ADR fixes: object kinds and schema versions, the pair-key record, the checkpoint record, the event types, the severity table, and the LSP method list.

**Tests.**
- TC-13.0.1 (`auto`): the audit record lists a result for every methodology baseline row and every result-table writer; none is blank.
- TC-13.0.2 (`auto`): `tools/track.py status` shows Phase 13 and gates T1 to T6; the existing gates A to E and S are unchanged.
- TC-13.0.3 (`auto`): ADR 0008 exists and contains the final severity table, pair-key record, checkpoint record and cancellation path.
- TC-13.0.4 (`auto`): the master-consistency test passes with the ADR (departures are documented, not silent).

**Acceptance.** The design has no open question that blocks M13.1. The five demo pairs are chosen. The pinned LSP library decision is written down.

**Demo / verification.** Open the audit record and the ADR.

**Dependencies / blockers.** None. If an audit result contradicts the methodology, stop and update the methodology before continuing.

---

## M13.1 Content-addressed object store

**Objective.** An immutable, atomic, verifying store for evidence objects, with the operations in methodology 5.2.

**Files.** `backend/faultline/evidence/__init__.py`, `store.py` (interface), `object_store.py` (filesystem backend), `kinds.py` (kind registry, schema versions, validators); reuses `core/hashing.py`; tests `tests/unit/test_evidence_store.py`, `tests/integration/test_evidence_concurrency.py`.

**Steps.**
1. Define the object envelope: `{kind, schema_version, payload}`, canonical JSON via the existing serializer, id = hash of `kind/schema_version` prefix plus canonical bytes.
2. `put`: canonicalise, hash, write to a temporary file in the same directory, flush, verify the digest by re-reading, rename into place. An existing object with the same id is verified and reused.
3. `get`: read, recompute the digest, validate the schema version and kind; return a typed result for missing, corrupt, unsupported and ok.
4. `link(parent, relation, child)` appends an edge row in the SQL index (created in M13.2); until then it writes to an in-store edge log so the store can be tested alone.
5. Kind registry with validators for `oracle_result`, `witness`, `attribution`, `verdict`, `fix_plan`, `pair_record`, `ddmin_checkpoint`, `world_ref`.
6. Crash safety on Windows: tolerate the rename-onto-existing error (the `_publish` retry pattern in `oracles/artifacts.py`), and never leave a partial file visible under its final name.

**Data / control flow.** Callers pass a typed payload; the store returns an id; later readers pass the id and get a verified payload.

**Interfaces.** `EvidenceStore.put(kind, payload) -> id`, `get(id) -> Result`, `exists(id)`, `link(parent, relation, child)`, `iter_objects()` (used by rebuild), `verify_all()`.

**Tests.**
- TC-13.1.1 (`auto`): the same payload gives the same id regardless of key order; a different `kind` with the same payload gives a different id.
- TC-13.1.2 (`auto`): a byte flipped in a stored object is rejected by `get` as corrupt, and never returned.
- TC-13.1.3 (`auto`): a simulated crash after the temporary write leaves no object visible under a final name; a retry succeeds.
- TC-13.1.4 (`auto`): 16 threads and 4 processes putting the same content produce one object and no error.
- TC-13.1.5 (`auto`): an object of an unsupported schema version is reported as unsupported, not as corrupt, and is not used.

**Acceptance.** All tests pass on Windows and in CI (Linux). No code outside `evidence/` writes objects.

**Demo / verification.** A short script writes, reads and tampers with an object and prints the result of each.

**Dependencies / blockers.** M13.0.

---

## M13.2 Event log, SQL projections and rebuild

**Objective.** Append-only job and evidence events; result tables written as projections of objects; a rebuild that recreates them.

**Files.** `backend/faultline/storage/migrations/0007_evidence.sql` (new tables only: `object_index`, `object_edge`, `evidence_event`, `pointer`, `ddmin_checkpoint`, `pair_index`), `backend/faultline/evidence/events.py`, `evidence/projections.py`, `evidence/rebuild.py`, `storage/jobs.py` (emit events), writers in `worlds/cells.py`, `attribution/runner.py`, `analysis/live.py`, `remediation/minimal.py`, `witnesses/bundle.py`; CLI `tools/fl.py rebuild`.

**Steps.**
1. Migration `0007`: tables only; nothing existing is altered or dropped.
2. `append_event`: events are inserted and never updated or deleted (a trigger rejects `UPDATE` and `DELETE` on `evidence_event`). Types: job transitions (`QUEUED`, `CLAIMED`, `HEARTBEAT` sampled, `RETRIED`, `CANCEL_REQUESTED`, `CANCELLED`, `DONE`, `FAILED`), `REUSED`, `RECOMPUTED_STARTED`, `RECOMPUTED_DONE`, `REJECTED`, `DDMIN_ATTEMPT_STARTED`, `DDMIN_ATTEMPT_FINISHED`, `DDMIN_CHECKPOINT`, `POINTER_MOVED`.
3. In `storage/jobs.py` emit one event on every state change, inside the same transaction as the state change.
4. Convert each result-table writer from `DELETE`+`INSERT` to: `put` object, insert projection row, move pointer (event). Keep column values identical so every REST response is unchanged.
5. Implement `rebuild` exactly as methodology 5.3 (discover, order, duplicates, pointers, scratch database then swap, verify).
6. A feature setting `FAULTLINE_EVIDENCE_STORE=on|off`; `off` runs the original writers (needed for the regression comparison in M13.11).

**Data / control flow.** Writer -> object store -> projection row -> `POINTER_MOVED` event. Rebuild: object directory + event log -> scratch database -> swap.

**Interfaces.** `GET /api/evidence/events?analysis_id=`, `GET /api/evidence/objects/{id}`; `tools/fl.py rebuild [--dry-run]`.

**Tests.**
- TC-13.2.1 (`auto`): updating or deleting an `evidence_event` row fails.
- TC-13.2.2 (`auto`): every job state transition produces exactly one event, in order, for a normal run, a retry and a cancellation.
- TC-13.2.3 (`docker`): run the showcase analysis; the REST responses for findings, witnesses, attribution, remediation and evidence are identical to those recorded before the change (golden comparison).
- TC-13.2.4 (`docker`): empty the projection tables, run `rebuild`, compare the REST responses before and after: identical; the object directory is byte-identical.
- TC-13.2.5 (`auto`): rebuild with one corrupt object and one missing referenced object reports both, skips them, deletes nothing, and a failed rebuild leaves the old tables in place.

**Acceptance.** No result-table writer uses `DELETE` followed by `INSERT` for evidence rows. Existing tests pass with the store on.

**Demo / verification.** `tools/fl.py rebuild --dry-run` then `rebuild`, then the API compare script.

**Dependencies / blockers.** M13.1.

### Gate T1: Storage

Declared with `python tools/track.py gate T1` after M13.0, M13.1 and M13.2 are done. Evidence: audit and ADR, key determinism of the object ids, atomic publish, tamper rejection, concurrent writes, crash repair, rebuild comparison.

---

## M13.3 Stable pair key and pair records

**Objective.** A producer-consumer pair has an identity that is the same across separate analyses and changes whenever any relevant input changes.

**Files.** `backend/faultline/evidence/pair_key.py`, `evidence/pairs.py`, `worlds/cells.py` (record the key and lookup), `storage/migrations/0007_evidence.sql` (`pair_index`), tests `tests/unit/test_pair_key.py`.

**Steps.**
1. Define the `PairKeyInput` record with exactly the inputs of methodology 6.1: producer and consumer repository and pinned commit, producer artifact content hash, reference and consumer lockfile digests, both world hashes, resolver name and version, **only those resolver settings that can change the resolved result or the execution** (the audit M13.0 lists them; for example the resolution timestamp, if and only if the resolver output depends on it), platform, entry modules with file hashes, oracle, harness and image versions, witness rule, verdict-rule version. Wall-clock times of the run, local paths, analysis ids and other incidental metadata are never in the key.
2. `pair_key = hash("pair/1" + canonical(PairKeyInput))`. Keep the full input record in the `pair_record` object beside the digest so a key can be explained.
3. Provide `explain(key_a, key_b)` that lists which inputs differ (used by the UI and the demo).
4. In `plan_cells`, compute the key for every cell and store it with the cell; leave `cell.id` unchanged for the existing workflow.

**Data / control flow.** Planned cell -> collect inputs from snapshot, worlds, oracle registry, image digest -> key -> `pair_index` lookup.

**Interfaces.** `pair_key(cell, inputs) -> str`, `PairKeyInput`, `explain()`.

**Tests.**
- TC-13.3.1 (`auto`): the same inputs always give the same key, in a fresh process and with reordered fields.
- TC-13.3.2 (`auto`): **key mutation matrix**: changing each input alone (producer commit, consumer commit, producer artifact byte, each lockfile, resolver version, platform, entry file hash, oracle version, image digest, witness rule, verdict rule) changes the key; changing an irrelevant value (the wall-clock time of the run, a local path, an analysis id) does not; a resolution-timestamp setting changes the key only if the audit found that the resolver output depends on it, and the test asserts exactly what the audit recorded.
- TC-13.3.3 (`auto`): two separate analyses of identical pinned inputs give the same pair key for every cell.
- TC-13.3.4 (`auto`): `explain` names exactly the changed input for each single-change case.

**Acceptance.** The matrix covers every input in the methodology table, and each case is a named test.

**Demo / verification.** Print the key and its input record for one pair, change one input, print the diff.

**Dependencies / blockers.** M13.0 (inputs frozen), M13.1.

---

## M13.4 Incremental analysis and counters

**Objective.** A new analysis reuses stored pair results whose key matches and recomputes only the rest, with accurate counters from events.

**Files.** `backend/faultline/analysis/live.py` (reuse path in `execute_cell`), `analysis/incremental.py` (new), `evidence/counters.py`, `api/routers/analysis.py` (`GET /api/analyses/{id}/counters`), `frontend/src/app/views/Overview.tsx` and a new `ui/Counters.tsx`, generated OpenAPI types.

**Steps.**
1. Before running a cell, look up `pair_key` in `pair_index`. Cases: complete verified pair object found -> load its witness, attribution, verdict and fix objects, write projection rows for this analysis, emit `REUSED` with the original run ids; object present but fails verification -> emit `REJECTED`, then recompute; not found -> emit `RECOMPUTED_STARTED`, run the unchanged pipeline, store the pair record, emit `RECOMPUTED_DONE`.
2. A reused result is labelled with its provenance (`REUSED_RESULT`, original analysis and runs) everywhere it is shown. It is never added to the 3 + 3 runs of any new witness.
3. A pair whose result was `INCONCLUSIVE` because of an infrastructure problem is not stored as reusable.
4. `counters.py` reads only `evidence_event`: pairs reused, recomputed (started and done separately), rejected, worlds reused and built, DDMin tests resumed and run.
5. Counters endpoint and a UI widget on the analysis page showing the numbers side by side, with the list of pairs and, for each, reused or recomputed and why (from `explain`). The widget updates through the existing job polling.

**Data / control flow.** Analysis job -> plan cells -> per cell: lookup -> reuse or pipeline -> events -> counters endpoint -> UI.

**Interfaces.** `GET /api/analyses/{id}/counters`, `GET /api/analyses/{id}/pairs` (per pair status, key, reason).

**Tests.**
- TC-13.4.1 (`docker`): **setup and verification step.** Run the five-pair set cold, on an empty store: five recomputed, none reused, counters equal the event log. This run is what warms the store for the demo; its output, events and timings are kept under `evidence/M13.4/` and are shown to the jury as the recorded cold run.
- TC-13.4.2 (`docker`): re-run unchanged: five reused, none recomputed, zero new sandbox runs (checked against the sandbox run log), identical findings.
- TC-13.4.3 (`docker`): change one producer revision: only the pairs of that producer recompute, the others are reused, counters equal the event log.
- TC-13.4.4 (`docker`): corrupt one stored pair object: that pair reports `REJECTED` and recomputes; the others are reused.
- TC-13.4.5 (`auto`): a reused result never appears as a run inside a new witness (inspect witness run provenance).
- TC-13.4.6 (`manual`): the UI shows the counters and per-pair reasons (screenshot saved).

**Acceptance.** Counters are derived only from events. Reused findings are identical to recomputed ones for identical inputs.

**Demo / verification.** This is Demo A (section "Demos" below).

**Dependencies / blockers.** M13.2, M13.3. Needs Docker and the wheelhouse for the cold run.

### Gate T2: Incremental reuse

Declared after M13.3 and M13.4. Evidence: TC-13.4.1 to TC-13.4.4 on real executions, with the sandbox run log.

---

## M13.5 Resumable DDMin core

**Objective.** `ddmin()` becomes a state machine whose state and completed tests are stored after every test, and which resumes deterministically.

**Files.** `backend/faultline/attribution/ddmin.py` (algorithm version bump, state machine), `attribution/checkpoint.py` (new), `evidence/kinds.py` (`ddmin_checkpoint`, `oracle_result` with `test_id`), tests `tests/unit/test_ddmin_resume.py`.

**Steps.**
1. Refactor to an explicit state `(phase, c, n, i)` with phases for the singleton pre-check, the full-set check, the reduction loop and finalisation, keeping the current results for non-resumed runs (a golden test over the existing ddmin cases proves the output is unchanged).
2. Define `test_id = hash(minimisation_id, sorted subset, direction)` and `minimisation_id = hash(pair key, witness signature, candidate-set digest, algorithm version)`.
3. Wrap the test callback with the protocol of methodology 7.2: lookup by `test_id`, `STARTED` event, run, write `oracle_result`, `FINISHED` event, append checkpoint, next test.
4. Resume: load the latest valid checkpoint (verify hash, schema, input identity), replay the algorithm against the stored results, continue at the first missing test; if the latest checkpoint is corrupt, use the previous one; if none is valid, report it.
5. Persist the budget as consumed tests and consumed seconds. Interrupted, timed-out, cancelled and unbuildable tests are `INTERRUPTED` or `UNRESOLVED`, never `FAIL`.
6. A changed algorithm version, candidate set or input starts a new chain; the old chain is kept.

**Data / control flow.** `ddmin` asks for the next subset -> protocol wrapper -> result stored -> checkpoint appended -> state advanced.

**Interfaces.** `ResumableDdmin(minimisation_id, items, test, store, budget)`, `.run()`, `.resume()`, `.state`.

**Tests.**
- TC-13.5.1 (`auto`): for the existing ddmin test inputs, the resumable version returns the same minimal set, status and attempts as the original.
- TC-13.5.2 (`auto`): stop after every possible test index `k`, resume, and require the same final result as an uninterrupted run, with no stored test run again.
- TC-13.5.3 (`auto`): fault injection exits after the result is stored and before the checkpoint; resume appends the missing checkpoint and does not run that test again.
- TC-13.5.4 (`auto`): an interrupted test is recorded `INTERRUPTED`, never counted as `FAIL`, and runs again on resume.
- TC-13.5.5 (`auto`): a corrupt latest checkpoint falls back to the previous one; with all corrupt it reports an explicit error.
- TC-13.5.6 (`auto`): two resumers race; only one advances `seq` (unique constraint).
- TC-13.5.7 (`auto`): budget exhausted gives `BUDGET_LIMITED`, with the smallest failing set found and no use of the word minimal; a changed algorithm version does not resume the old chain.

**Acceptance.** All tests deterministic and fast (no Docker).

**Demo / verification.** A script runs a synthetic ddmin, kills it, resumes it and prints stored vs newly run tests.

**Dependencies / blockers.** M13.1, M13.2.

---

## M13.6 Recovery in the pipeline and the eight-candidate fixture

**Objective.** Attribution in the live pipeline uses the resumable DDMin with real sandbox executions, and a fixture makes the recovery visible.

**Files.** `attribution/runner.py` (use `ResumableDdmin`; each test stores its `oracle_result`), `analysis/live.py` (attribute step; attribution found by content, not analysis id), `workers/run.py` (retry finds the chain), `fixtures/repos/acme-bisect/` and a consumer `fixtures/repos/bisect-svc/` (new), `fixtures/scenarios/` label, `scripts/publish_demo.py` (publish both), `tests/integration/test_ddmin_recovery.py`.

**Steps.**
1. Build the fixture: a producer library and a consumer whose two worlds differ by exactly eight packages; seven changes are harmless; one (named in the label before the first run) breaks the consumer's import. All eight are available offline in the wheelhouse.
2. Write the label with the expected minimal set, the expected number of tests, and the expected verdict (`BREAK WITNESSED`).
3. Make `attribute()` create or load the chain by `minimisation_id`; store each forced-world run as an `oracle_result` with its `test_id`.
4. Interruption methods for the demo and for tests: a real `kill` of the worker process, and a fault-injection environment variable used only by tests.
5. A retry (new analysis) finds the chain from the pair key and continues; the final attribution is stored once.

**Data / control flow.** Witness -> `ResumableDdmin` -> per test: forced world build (offline) -> sandbox run -> stored result -> checkpoint -> ... -> attribution object.

**Interfaces.** `GET /api/analyses/{id}/attribution` includes `resumed_tests`, `new_tests`, `chain_id`, `checkpoint_seq`.

**Tests.**
- TC-13.6.1 (`docker`): an uninterrupted run on the fixture finds the labelled change as the minimal set and matches the expected test count.
- TC-13.6.2 (`docker`): kill the worker in the middle of a sandbox run; restart; the chain resumes; the final minimal set equals the label; no test whose result was stored runs again (checked by comparing sandbox run ids); the killed test runs once more.
- TC-13.6.3 (`docker`): kill with fault injection after the result is stored and before the checkpoint; resume skips that test.
- TC-13.6.4 (`docker`): after the kill no container of the old job remains and the old job's attempt is marked interrupted.
- TC-13.6.5 (`docker`): the resumed attribution is the same object content as the uninterrupted one (same minimal set, same statuses).
- TC-13.6.6 (`live`): the fixture repositories analyse correctly from GitHub URLs.

**Acceptance.** Recovery shown on real executions, with no mock sandbox.

**Demo / verification.** This is Demo B.

**Dependencies / blockers.** M13.5; Docker; fixture publication needs GitHub access.

### Gate T3: DDMin recovery

Declared after M13.5 and M13.6.

---

## M13.7 Stdio LSP server and VS Code vertical slice

**Objective.** One real Faultline diagnostic appears at a real line in VS Code through a clean stdio LSP 3.17 server.

**Files.** `backend/faultline/lsp/__init__.py`, `server.py`, `client_api.py` (REST client), `lsp/state.py`; `editors/vscode/` (new: `package.json`, `src/extension.ts`, `tsconfig.json`, `.vscode/launch.json`); `pyproject.toml` and `uv.lock` (pinned `pygls`, `lsprotocol`); `tools/fl.py lsp`; tests `tests/unit/test_lsp_framing.py`, `tests/integration/test_lsp_protocol.py`.

**Steps.**
1. Pin `pygls` and `lsprotocol` (versions from M13.0), update `uv.lock`, run `tools/fl.py check-pins`.
2. Server entry `python -m faultline.lsp` over stdio: binary-mode stdin and stdout on Windows, logging to stderr, no output on stdout other than protocol frames.
3. Implement `initialize` (capabilities: text document sync, code actions, execute command), `initialized`, `shutdown`, `exit`, `textDocument/didOpen`, `didChange`, `didClose` (bounded per-document state, removed on close).
4. A REST client for the Faultline API (base URL from initialization options). If the API is unreachable, a status notification says so and no diagnostics are shown as clean.
5. On `didOpen` of a Python file in a known consumer workspace, fetch findings for that file's consumer and publish diagnostics (vertical slice: the range comes from the simplest source, the import line).
6. The VS Code extension: depends on `vscode-languageclient` (pinned), starts the server with the repository's Python, registers the `Faultline: Analyze` command, and is launched from the repository in the Extension Development Host with a documented one-command setup.

**Data / control flow.** VS Code -> extension -> stdio -> server -> REST API -> findings -> `publishDiagnostics` -> editor.

**Interfaces.** LSP methods above; custom request `faultline/analyze` (defined here, implemented in M13.10); the REST endpoints already used by the UI.

**Tests.**
- TC-13.7.1 (`auto`): spawn the real server process, send frames containing `\n`, `\r\n` and non-ASCII text through stdio on Windows and Linux; every response parses and stdout holds only frames.
- TC-13.7.2 (`auto`): `initialize` -> `initialized` -> `shutdown` -> `exit` completes; the exit code is 0 after a shutdown and 1 without.
- TC-13.7.3 (`auto`): a malformed request and an unsupported method get a JSON-RPC error and do not crash the server.
- TC-13.7.4 (`auto`): the API is down: the server reports unavailable and publishes no clean result.
- TC-13.7.5 (`auto`): `check-pins` passes with the new dependencies and the LSP version is 3.17.
- TC-13.7.6 (`manual`): in VS Code (Extension Development Host) open the consumer fixture; a Faultline diagnostic appears; the recording or screenshot is saved as evidence.

**Acceptance.** The slice works in a real editor before any other LSP feature is added.

**Demo / verification.** Open the consumer in VS Code and show the diagnostic and its hover text.

**Dependencies / blockers.** M13.0; existing findings in the database (a warm analysis). Node and npm are available for the extension build.

---

## M13.8 Diagnostic locations, severities and freshness

**Objective.** Diagnostics sit on the correct lines, with severities from the final mapping, and become stale when the code changes.

**Files.** `backend/faultline/lsp/diagnostics.py`, `lsp/locations.py`, `lsp/severity.py`, `storage/findings.py` or the read layer (return location data), tests `tests/unit/test_lsp_locations.py`, `tests/unit/test_lsp_severity.py`, fixtures with one finding per severity.

**Steps.**
1. `locations.py`: for each finding, derive the consumer file and line from the best source in order: O-bind site (`CallSite` file, line, column), `usage_ref` rows for the divergent symbol, the import statement of the failing entry, then none. Record which source was used. If none, produce no precise diagnostic and show the finding in a status message instead.
2. Convert one-based parser positions to zero-based LSP ranges; handle tabs, non-ASCII, CRLF files, Windows drive-letter URIs, URI encoding and case.
3. `severity.py` implements the table from ADR 0008 (final). The draft is: BREAK WITNESSED error; SILENT DIVERGENCE WITNESSED warning; EXPOSED and POTENTIAL information-level; INCONCLUSIVE and HYGIENE hint; NO DIVERGENCE OBSERVED and NOT EXPOSED none.
4. Each diagnostic carries `source: "faultline"`, `code` = finding id, and data: finding id, verdict, pinned consumer commit, file hash, evidence summary, the location source used. Messages use only the exact verdict words.
5. Freshness: store the file hash with each diagnostic; on `didChange` or `didSave` compare with the analysed hash and mark the diagnostic stale (clear it and show a status note) instead of leaving it on shifted text. Re-publish without duplicating after reopen.

**Data / control flow.** Finding + usage index + call sites -> location -> severity -> diagnostic; document change -> hash compare -> stale handling.

**Interfaces.** `to_diagnostics(findings, document) -> list[Diagnostic]`.

**Tests.**
- TC-13.8.1 (`auto`): golden positions: diagnostics land on the expected zero-based line and column for the call-site, import and no-location cases in the fixture consumers.
- TC-13.8.2 (`auto`): URI and path cases: Windows drive letters, spaces, encoded characters, case, CRLF and non-ASCII source lines.
- TC-13.8.3 (`auto`): the severity function returns the ADR's severity for every verdict, and an unknown verdict raises rather than defaulting.
- TC-13.8.4 (`auto`): editing the file marks diagnostics stale; reopening does not duplicate them.
- TC-13.8.5 (`docker`): fixtures produce at least four distinct severities from real analyses.
- TC-13.8.6 (`manual`): VS Code shows the four severities at the right lines (screenshot saved).

**Acceptance.** No diagnostic is placed on a line that Faultline did not derive from data.

**Demo / verification.** The consumer fixture in VS Code showing error, warning, information and hint.

**Dependencies / blockers.** M13.7; the verdict audit in M13.0.

### Gate T4: LSP diagnostics

Declared after M13.7 and M13.8.

---

## M13.9 Verified code action as a WorkspaceEdit

**Objective.** `textDocument/codeAction` offers a fix only when it is verified and current, and edits the correct dependency file.

**Files.** `backend/faultline/lsp/code_actions.py`, `remediation/minimal.py` (store the plan as a `fix_plan` object with the target file path and its hash), `lsp/server.py` (register), tests `tests/unit/test_lsp_code_actions.py`.

**Steps.**
1. Return an action only when the finding has a `fix_plan` labelled VERIFIED, the plan is for an import witness, and the recorded hash of the target requirements file equals the current file content hash.
2. Build a `WorkspaceEdit` with a `TextDocumentEdit` (versioned when the file is open) that applies the plan's diff to the consumer's requirements file at exact ranges; kind `quickfix`; title states the constraint; `diagnostics` links the diagnostic.
3. Return no action for SUGGESTED, partially verified, stale, unsupported (non-import witness) and unknown-file cases.
4. Faultline never saves, commits, pushes or runs package scripts. After the user applies the edit, `faultline/analyze` shows that only the affected pair recomputes.

**Data / control flow.** `codeAction(range, diagnostics)` -> finding id from diagnostic data -> `fix_plan` object -> hash check -> `WorkspaceEdit`.

**Interfaces.** `textDocument/codeAction` result; `fix_plan` object with `target_path`, `target_sha256`, `edits`.

**Tests.**
- TC-13.9.1 (`auto`): a VERIFIED plan with a matching file yields one action whose edit applied to the file gives exactly the plan's diff.
- TC-13.9.2 (`auto`): SUGGESTED, partial, stale-hash, non-import and missing-file cases yield no action.
- TC-13.9.3 (`auto`): the edit targets the requirements file, not the source file.
- TC-13.9.4 (`docker`): after applying the edit to a copy of the consumer, a new analysis shows the witness gone and only the affected pair recomputed.
- TC-13.9.5 (`manual`): in VS Code the lightbulb offers the fix, applying it edits the file, the diagnostic disappears after re-analysis (recording saved).

**Acceptance.** No unverified edit is ever offered.

**Demo / verification.** The fix demo inside the VS Code session.

**Dependencies / blockers.** M13.8, M13.1 (`fix_plan` object).

---

## M13.10 Cancellation

**Objective.** `$/cancelRequest` stops the actual sandbox execution and ends the job as `CANCELLED`.

**Files.** `backend/faultline/lsp/cancel.py`, `lsp/server.py` (`faultline/analyze` handler and the request-to-job table), `api/routers/jobs.py` (existing cancel endpoint, idempotent), `workers/run.py` and `sandbox/client.py` (existing kill; add a label check helper), tests `tests/integration/test_lsp_cancel.py`.

**Steps.**
1. `faultline/analyze` creates the job through the API with an idempotency key from the session and request id, records `request id -> job id`, and answers when the job reaches a final state.
2. On `$/cancelRequest`: look up the id (ignore unknown); mark it cancelled before anything else; call the cancel endpoint; answer the request with `RequestCancelled`; drop any later result.
3. Make the cancel path idempotent and race-safe as listed in methodology 9.6 (repeat, before creation, as the job finishes, during a DDMin test, API unreachable).
4. Add a helper that lists containers by the job label for the orphan check, and record the request-to-stop time in the event log.

**Data / control flow.** `$/cancelRequest` -> mapping -> cancel endpoint -> heartbeat sees the flag -> `SandboxClient.cancel(job_id)` -> containers removed -> job `CANCELLED` -> events.

**Interfaces.** `faultline/analyze`, `$/cancelRequest`, `POST /api/jobs/{id}/cancel` (existing).

**Tests.**
- TC-13.10.1 (`docker`): start `faultline/analyze` on a long fixture, cancel in the middle of a sandbox run; the container is gone within the bound; `docker ps` shows no job-labelled container; the job is `CANCELLED`; the event log has the transitions.
- TC-13.10.2 (`docker`): the cancelled analysis has no witness and no dependency-failure finding from the cancelled run.
- TC-13.10.3 (`auto`): repeated cancel, cancel of an unknown id, cancel before job creation, cancel at completion, API unreachable: each behaves as specified and none crashes.
- TC-13.10.4 (`docker`): cancel during a DDMin test leaves a valid checkpoint chain that resumes.
- TC-13.10.5 (`manual`): cancel from VS Code and watch the container disappear (recording saved).

**Acceptance.** Time from request to stop is measured and recorded, not assumed.

**Demo / verification.** Cancel demo in VS Code with a `docker ps` terminal beside it.

**Dependencies / blockers.** M13.2 (events), M13.7 (server), M13.6 (for TC-13.10.4). Docker.

### Gate T5: Fixes and cancellation

Declared after M13.9 and M13.10.

---

## M13.11 SQL backward support and regression

**Objective.** The original workflow, API, UI and tests keep working with the store on and off.

**Files.** `tests/integration/test_store_parity.py` (new), `.github/workflows/ci.yml` (run the suites with both settings; new LSP protocol job), `docs/schemas/` and generated types (unchanged responses), `tests/unit/test_master_consistency.py` (extended only where an ADR documents a departure).

**Steps.**
1. Run the whole unit suite and the integration suites with `FAULTLINE_EVIDENCE_STORE=off` and `=on`.
2. Parity test: the same pinned inputs analysed with the store off and on produce identical findings, witnesses, attributions and remediation (ignoring ids and timestamps).
3. Frontend: type-check, build and the browser tests against the stack with the store on.
4. Replay the committed witness bundle in CI; confirm the verifier still accepts it.
5. Security tests unchanged and passing.

**Data / control flow.** None new.

**Interfaces.** None new.

**Tests.**
- TC-13.11.1 (`auto`): 394+ unit tests pass with the store on and off.
- TC-13.11.2 (`docker`): the integration suites pass with the store on and off, including `test_durable`, `test_remediation`, `test_rerun`.
- TC-13.11.3 (`docker`): the parity test passes.
- TC-13.11.4 (`auto`): frontend type-check and build pass; the OpenAPI types are unchanged for existing endpoints.
- TC-13.11.5 (`live`): CI is green on both repositories, including the replay step.

**Acceptance.** Nothing existing is removed or weakened. Any pre-existing failure recorded in M13.0 is reported as such, not hidden.

**Demo / verification.** Run the original SQL workflow in the UI and show it unchanged.

**Dependencies / blockers.** M13.1 to M13.10.

---

## M13.12 Jury demonstrations, instructions and final report

**Objective.** Two reproducible demos from a genuinely warm store, written instructions, and a report that separates verified from unverified.

**Files.** `docs/INCREMENTAL_WITNESS_DEMO.md` (instructions), `scripts/twist_demo.py` (preflight and rehearsal for both demos, modelled on `scripts/demo_check.py`), `docs/INCREMENTAL_WITNESS_REPORT.md` (final report), `evidence/M13.12/`, a warm-store release package (store directory plus database), `docs/judge_qa.md` additions, `docs/PROMPT_BOOK.md` entries.

**Steps.**
1. Warm the store with a real cold run of the five pairs and the bisect fixture (the M13.4 setup run, repeated on a clean checkout if the store was rebuilt); keep the cold-run evidence; package the store and database so the jury machine starts warm. A checksum of the packaged store is recorded so the jury copy can be shown to be the one that was produced by the real run.
2. `twist_demo.py --preflight` checks Docker, the stack, the API port, the store, the pinned images, VS Code and the extension, and prints what is missing. `--demo A` and `--demo B` rehearse the two flows and print the counters, the sandbox run ids and the pass or fail of each check.
3. Demo A script. The **cold run is setup, not part of the live demo**: it is done beforehand on an empty store (TC-13.4.1) and its evidence is kept and can be shown. The live demo starts from the resulting warm store: show the stored cold-run counters, rerun unchanged (all reused, no new sandbox runs), change one producer revision, rerun (only the affected pairs recomputed), then show the events and the `explain` output. Every number shown comes from stored events.
4. Demo B script: start attribution on the bisect fixture, stop the worker after a few tests, restart it, show the checkpoint, resumed and new tests, and the unchanged sandbox run ids of completed tests.
5. Editor script: diagnostics with four severities, the verified fix, the cancel with `docker ps`.
6. Final report: three lists, kept apart: verified (gate passed, evidence path), implemented but not verified, not done. Real timings with how they were measured; no invented numbers.
7. Add the twist prompts and results to the prompt book. Update the build status document and the conformance matrix. Record M13.12 in the tracker.

**Data / control flow.** Rehearsal script drives the real stack; nothing is pre-filled.

**Interfaces.** Command lines of `twist_demo.py`.

**Tests.**
- TC-13.12.1 (`live`): `twist_demo.py --demo A` passes end to end on a clean checkout with the warm store.
- TC-13.12.2 (`live`): `twist_demo.py --demo B` passes: interruption, restart, resume, no repeated completed test.
- TC-13.12.3 (`manual`): the full editor sequence in VS Code is recorded once from start to finish.
- TC-13.12.4 (`auto`): the final report's claims each map to an evidence file that exists.
- TC-13.12.5 (`auto`): the docs contain no banned wording ("compatible", "proof", "guarantee", "AI detected") and use the exact verdict words.

**Acceptance.** A person who did not build it can follow `INCREMENTAL_WITNESS_DEMO.md` and reproduce both demos.

**Demo / verification.** The rehearsal itself.

**Dependencies / blockers.** M13.11. GitHub access for publishing fixtures, Docker, VS Code.

### Gate T6: Regression

Declared after M13.11 and M13.12.

---

## Time order for a one to two day window

| Block | Milestones | Why this order |
|---|---|---|
| 1 | M13.0, M13.1, M13.2 | Invariants first; everything depends on the store and the event log |
| 2 | M13.3, M13.4 | Pair reuse is the first thing the jury can see and needs the cold-run warm-up time early |
| 3 | M13.5, M13.6 | Recovery needs the store; the fixture publication can start during block 2 |
| 4 | M13.7, M13.8 | The editor slice can start during blocks 2 and 3 because it reads existing findings |
| 5 | M13.9, M13.10 | Both need M13.1 and M13.2 |
| 6 | M13.11, M13.12 | Final regression and rehearsal |

Cold analyses take minutes each; start the warm-up run as early as the code allows, in the background, and plan other work around it.

## What would make a milestone fail

- A test case that cannot be run in this environment is recorded as not run, with the reason; it is not marked passed.
- If a pinned `pygls` cannot meet the requirements in M13.0, the fallback is a small hand-written stdio server with the same tests; this changes M13.7 only.
- If the VS Code recording cannot be made, T4 and T5 stay undeclared.

## Remaining gaps known before starting

- No audit has been done yet; section 3 of the methodology is read from code, not re-verified.
- The five demo pairs and the final severity table are decided in M13.0.
- The window between a finished sandbox run and its result being stored cannot be closed without storing results inside the container; the plan states it as a limit and the demo avoids it.
- Neovim is optional and not planned in any gate.
