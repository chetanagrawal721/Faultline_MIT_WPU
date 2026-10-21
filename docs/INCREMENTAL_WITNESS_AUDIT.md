# Incremental Witness: audit record (M13.0)

Read from the code at commit `b8d3a6d` (branch `clean`). The working tree differs from that commit only by the Phase 13 registration files (`playbook/phases/phase13_t*.yaml`, `playbook/phases.yaml`, tracker output) and the three twist documents. Each row below is **confirmed**, **corrected** or **not found**.

## 1. Baseline

| Item | Value |
|---|---|
| Python | 3.12.15 (`.venv`), uv 0.13.0 |
| Migrations | `0001_init` to `0006_attribution` |
| OpenAPI | 27 paths, canonical-JSON SHA-256 `d83c6a01b1014a6db864bf77765525e9225d8a8825cad65b9115ee6c9fe2fe8d` |
| Evidence bundle schema | `docs/schemas/evidence-bundle-v1.json`, SHA-256 `df2ef582b3d866828acaf1bf5a4de831e755ed74bd74af567d76a5bd9aed9522` |
| Unit tests | 394 passed (run 2026-10-21) |
| Integration baseline | `test_durable`, `test_remediation`, `test_rerun`: 9 passed in 468 s (section 9) |
| Docker | Docker Desktop 29.8.0 running |
| Tracker | 49 of 63 milestones before Phase 13 (13 milestones, 69 test cases added) |

## 2. Methodology baseline rows

| ID | Methodology row | Result | Detail |
|---|---|---|---|
| B1 | Hashing is canonical in `core/hashing.py` | confirmed | `canonical_json`, `object_hash`, `content_hash`, `world_hash`, `env_profile_id`. No second serializer will be added. |
| B2 | `world_hash` covers installed entries, runtime, environment | corrected | It covers ecosystem, runtime name and version, `env_profile_id` (image reference with digest, OS, architecture, locale, time zone, seed) and each entry (locator, name, version, scope, source kind and reference, artifact SHA-256). It does **not** cover the resolver name or version, the lockfile or manifest digest, or the commit SHA. The pair key records those explicitly. |
| B3 | Cell identity | confirmed | `cell.id = "cell_" + hash([analysis_id, producer_project_id, projection.key])[:24]`, and the table is `UNIQUE(analysis_id, artifact_project_id, test_world_hash)`. A cell has no identity across analyses. |
| B4 | Result tables are mutable | confirmed | See section 3. Writers use `DELETE` then `INSERT`, `INSERT OR REPLACE` and in-place `UPDATE`. |
| B5 | Run provenance vocabulary exists | corrected | `oracle_run.provenance` has `FRESH_EXECUTION` and `REUSED_RESULT`, and `execute_run` already has a **run-level** cache keyed by `(oracle, version, world, artifact, args, run_index)`. It returns `REUSED_RESULT` unless `force=True`. Every witness verification in `analysis/live.py` passes `force=True` (lines 222, 245, 267, and the contract call), so no reused run enters a 3 + 3. The twist adds reuse at **pair** level only; the run-level cache stays as it is, and TC-13.4.5 checks that no reused run is inside a new witness. |
| B6 | `ddmin()` is a pure function with an in-memory memo | confirmed | `attribution/ddmin.py`. The only caller is `attribution/runner.attribute()` (line 87), itself called once in `analysis/live.py` (line 307). `attribution_attempt` rows are written by `persist()` only after the whole search ends. |
| B7 | Attribution runs inline in the analysis job | confirmed | Under the job's lease, in `execute_cell`. A retry is a new analysis (`analysis/lifecycle.py`), so a checkpoint chain must be found by content, not by analysis id. |
| B8 | Cancellation reaches containers | confirmed | `workers/run.py`: the heartbeat thread reads `cancel_requested` and calls `SandboxClient.cancel(job_id)`. Heartbeat interval is 10 s and lease 30 s (`core/config.py`), so the worst-case delay before the kill is the heartbeat interval. Measured latency is recorded in M13.10. |
| B9 | Call-site data | corrected | See section 5. O-bind sites are call sites **inside the producer artifact**, not in the consumer. The consumer-side data is the import scan (`usage/consumer_imports.py`: module, file, line), which is **computed but not stored** (only module names go into `cell_consumer.imported_modules_json`). |
| B10 | The verified fix edits a constraint file | confirmed | `remediation/minimal.py` writes a diff to the store directory and a `remediation_plan` row labelled `VERIFIED` or `SUGGESTED`; import witnesses only. |
| B11 | Toolchain | confirmed | `pygls` and `lsprotocol` are not in `uv.lock`. VS Code is installed (`code` on PATH). Neovim is not. Node and npm are installed. |
| B12 | Witness rows are immutable | corrected | `witnesses/verify.py::_save_witness` does `UPDATE witness SET body_json=?` to append `reverifications` to an existing witness. Under the new model a witness object is immutable and a re-verification is a separate event or object. |
| B13 | Verdicts are recomputed from stored evidence | confirmed, with a consequence | `verdicts/recompute.py` does `UPDATE finding SET verdict, sub_label, headline, scope_json, priority`. Under the new model a recomputation creates a new `verdict` object and moves the pointer. |

## 3. Result-table writers

Every statement that writes a result table, found by searching `backend/faultline` for `INSERT`, `DELETE FROM` and `UPDATE`. "Evidence" means the table becomes a projection of objects. "Workflow" means it stays a normal mutable table because it is not evidence (inventory, inputs or caches).

| File | Statements | Tables | Class | Change |
|---|---|---|---|---|
| `evidence/projections.py` | the only writer of evidence rows after M13.2: `INSERT`, `UPSERT` and `DELETE` on `oracle_run`, `witness`, `finding`, `finding_evidence`, `attribution`, `attribution_attempt`, `remediation_plan` | those tables | Evidence (projection) | The module every writer and `rebuild` call; rows change only to follow an object. |
| `witnesses/runs.py` | `INSERT oracle_job`, `INSERT oracle_run` (fresh and reused), `UPDATE oracle_job` status | `oracle_job`, `oracle_run` | Evidence | Each fresh run becomes an `oracle_result` object; rows are projections; the status `UPDATE` becomes events. |
| `witnesses/verify.py` | `INSERT witness`, `UPDATE witness.body_json` | `witness` | Evidence | Immutable `witness` object; re-verification recorded separately (B12). |
| `analysis/live.py` | `DELETE finding_evidence`, `DELETE finding`, `INSERT finding`, `INSERT finding_evidence`, `UPDATE cell`, `UPDATE project` (artifact hash), `UPDATE analysis` (status) | `finding`, `finding_evidence`, `cell` | Evidence (finding, evidence); workflow (cell state, project hash) | The finding becomes a `verdict` object plus a pointer; the delete-then-insert goes. |
| `analysis/fixture_runner.py` | `DELETE finding_evidence`, `DELETE finding`, `INSERT` for the fixture path | `finding`, `finding_evidence` | Evidence | Same conversion, so the fixture path keeps working. |
| `attribution/runner.py` | `DELETE attribution_attempt`, `DELETE attribution`, `INSERT attribution`, `INSERT attribution_attempt` | `attribution`, `attribution_attempt` | Evidence | `attribution` object and per-test `oracle_result` objects; attempts become events. |
| `remediation/minimal.py` | `DELETE remediation_plan`, `INSERT remediation_plan`, diff file written | `remediation_plan` | Evidence | `fix_plan` object with the target file path and its hash. |
| `verdicts/recompute.py` | `UPDATE finding` | `finding` | Evidence | New `verdict` object and pointer move (B13). |
| `worlds/cells.py` | `INSERT cell`, `DELETE delta_entry`, `INSERT delta_entry`, `INSERT OR REPLACE cell_consumer` | `cell`, `delta_entry`, `cell_consumer` | Workflow, plus pair record | Planning data; the pair key and the persisted import sites are added. |
| `worlds/canonical.py`, `storage/worlds.py` | `INSERT` into `resolved_world`, `world_entry`, `project_world`, `env_profile`, `package_version` | world tables | Workflow (already content-addressed by `world_hash`) | Referenced from objects, not copied. |
| `ingestion/service.py`, `api/routers/projects.py`, `relationships/engine.py` | repositories, snapshots, projects, manifests, relationships, relationship evidence | inventory tables | Workflow | Unchanged. `relationships/engine.py` deletes and rewrites `relationship_evidence`; it is inventory, not twist evidence. |
| `analysis/lifecycle.py`, `analysis/timemachine.py` | analysis status updates, time-machine rows | `analysis` | Workflow | Unchanged; job transitions also become events. |
| `usage/index.py`, `usage/callsites.py` | usage file and reference caches | `usage_file`, `usage_ref`, `import_index` | Workflow (content-hashed caches) | Unchanged. |
| `storage/jobs.py` | claim, heartbeat, retry, cancel, finish | `job`, `job_attempt` | Mutable state machine | Every transition also appends an event (section 4 of the methodology). |

`evidence_bundle`: the table exists in `0001_init.sql`, but no code inserts into it. Bundles are written as files by `witnesses/bundle.py`. The projection and rebuild treat bundles as objects of their own and do not rely on that table.

## 4. DDMin

- Single call site: `attribution/runner.py::attribute` line 87, called from `analysis/live.py` line 307 inside the analysis job.
- Memo: in memory only (`seen` dictionary in `ddmin()`).
- Persistence: after the search ends, `persist()` deletes any previous attribution for the witness and writes the new one.
- Crash behaviour today: a worker death loses the whole search; the retried job is a new analysis and starts again.
- Phases to checkpoint: singleton pre-check, full-set check, reduction loop with `(c, n, chunk)`, then the post-search sufficiency and necessity tests.
- Attribution is skipped for failing-test witnesses (`test_entries`); the chain applies to import, call-site and contract witnesses that the pipeline attributes.

## 5. Location data by witness type

| Witness type | What Faultline holds | Consumer-side line | Producer-side line |
|---|---|---|---|
| O-import | `frames` per failure: module, file, line, function (`oracles/harness/o_import.py`) | Frames lie in the producer artifact or in world packages, not in consumer files. The consumer line comes from the **import scan**: `{module, file, line}` for each artifact module the consumer imports. | The innermost artifact frame (file and line). |
| O-bind | Site id `bind:<file>:<line>:<col>` of a call **in the producer artifact** into a divergent package | The import scan line for the module that contains the site. | Exact line and column of the call. |
| O-tests | Test id and traceback frames of the library's own test | Not applicable to a consumer file. | Test file and frame lines in the producer repository. |
| O-contract | The input id (model and tier) and bytes | The import scan line for the producer module. | The model definition when it can be located; otherwise none. |

Consequences recorded for the design: (a) consumer-side diagnostics use the import line of the affected module, with the start of the line to its end as the range, because the import scan has no column; (b) producer-side diagnostics use the exact site when the producer repository is open in the editor; (c) the import scan must be **persisted** with the cell (new column or table in migration 0007) so the language server can read it; (d) when no line is known, no precise diagnostic is produced.

## 6. Verdict semantics and the severity mapping

From the master (section 30, verdict table):

| Verdict | Meaning | Does not claim |
|---|---|---|
| BREAK WITNESSED | Reference world passes and the consumer world fails, three fresh runs each, same normalized signature | That every consumer path breaks |
| SILENT DIVERGENCE WITNESSED | Both worlds succeed but normalized outputs differ, reproducibly | That the difference is harmful to every consumer |
| EXPOSED | Static reference to a changed symbol; execution did not settle it | That it will fail |
| POTENTIAL | Breaking changes exist but usage could not be resolved | That the artifact uses them |
| NOT EXPOSED | No resolved reference touches a changed symbol and coverage is at least 0.9 | That there is no risk |
| INCONCLUSIVE(reason) | Not enough evidence | Anything about the pair |
| HYGIENE | Versions differ with no relationship | That the difference matters |
| NO DIVERGENCE OBSERVED | What was exercised did not diverge | Anything outside what was exercised |

**Final mapping** (ADR 0008): BREAK WITNESSED, error; SILENT DIVERGENCE WITNESSED, warning (a witnessed, reproducible difference that may or may not be harmful); EXPOSED, warning (a changed symbol is statically referenced; execution did not settle it); POTENTIAL, information; INCONCLUSIVE, hint; HYGIENE, hint (shown only on the package or relationship, no source location); NO DIVERGENCE OBSERVED and NOT EXPOSED, no diagnostic. The live pipeline does not produce EXPOSED, POTENTIAL or NOT EXPOSED today (static analysis is not wired into the live run, see `docs/FAULTLINE_BUILD_STATUS.md`), so the four severities in the demo come from BREAK WITNESSED, SILENT DIVERGENCE WITNESSED, INCONCLUSIVE and a fixture finding, and POTENTIAL/EXPOSED are mapped and unit-tested only. This limit is stated in the final report.

## 7. Resolver settings that affect the result

`resolvers/python.py` (line 249) passes to uv: Python version `3.12`, `exclude_newer` (the cut-off timestamp), `index_url` and `no_index`. For a lockfile-pinned project the result does not depend on the resolver. For a project resolved by uv, the result depends on `exclude_newer`, the index and the uv version. The pair key therefore includes: resolver name and version, `exclude_newer` and the index setting **when uv resolved the world**; for a pinned lockfile it includes the lockfile digest only. Wall-clock run time, local paths and analysis ids are excluded.

## 8. LSP library

`pygls 2.1.1` (released 2026-03-25, Python 3.9 and later) depends on `lsprotocol==2025.0.0`, `attrs>=24.3.0` and `cattrs>=23.1.2`; `lsprotocol 2025.0.0` is generated from the LSP 3.17 metamodel. Installed in a scratch directory and read:
- `pygls/server.py` reads `sys.stdin.buffer` and writes `sys.stdout.buffer`, so stdio is binary and the Windows line-ending translation does not apply. A framing test in M13.7 still checks this on this machine.
- `pygls/protocol/json_rpc.py` handles `$/cancelRequest` by calling `future.cancel()` on the handler's future (`_handle_cancel_notification`). That cancels the Python task only; it does not stop a container. The explicit bridge to the job cancel endpoint (M13.10) is therefore required, as planned.
- Wheels are universal (`py3-none-any`), so they can be hash-pinned. Resolved extras: `cattrs 26.2.1`, `typing-extensions 4.16.0`. Final versions are fixed in `uv.lock` in M13.7.
Decision: use `pygls==2.1.1` and `lsprotocol==2025.0.0`; the hand-written fallback is not needed unless M13.7 finds a failure.

## 9. Integration baseline

Run on 2026-10-21 against the unchanged code (`pytest tests/integration/test_durable.py test_remediation.py test_rerun.py`): **9 passed in 468 s (7 min 48 s)**, no failures. Output: `evidence/M13.0/baseline_integration.txt`. These three files failed in CI before the earlier fixes and pass now, so the baseline has no known failing test.

## 10. Demo pairs (proposed, validated in M13.4)

Four producers and five consumers in one analysis project:

| # | Producer | Consumer | Fixture | Expected result |
|---|---|---|---|---|
| 1 | `acme-showcase` | `fulfilment-svc` | showcase | BREAK WITNESSED: import break, call-site break, contract break and silent divergence in one finding |
| 2 | `acme-showcase` | `reporting-svc` | showcase | no drift: identical versions, nothing to run (control) |
| 3 | `acme-http` | `orders-svc/C` | scenario C | BREAK WITNESSED (O-bind) |
| 4 | `acme-contracts` | `billing-svc/J` | scenario J | SILENT DIVERGENCE WITNESSED (O-contract) |
| 5 | `acme-models` | `orders-svc/A` | scenario A | no drift control (the exact cell state is recorded in the first cold run) |

Changing one producer revision (a new commit of `acme-showcase`) must recompute pairs 1 and 2 and reuse pairs 3 to 5. The exact repositories and pins are checked in the first cold run; if the scenario tags cannot be combined in one project, the pairs are replaced by equivalent ones from the same fixtures and this table is updated.

## 11. Corrections to the plan found by the audit

1. The consumer import scan must be stored (new table or column in `0007`); otherwise consumer diagnostics have no source (B9).
2. A witness is immutable under the new model; the existing in-place `reverifications` update becomes an event (B12).
3. A verdict recomputation creates a new verdict object (B13).
4. The pair key includes `exclude_newer` and the index setting only when uv resolved the world (section 7).
5. The producer-side call-site line (O-bind) exists, and the consumer-side line is the import line; both are used (section 5).
6. Only four severity levels can be shown from live runs; EXPOSED and POTENTIAL are mapped but not produced live (section 6).
7. Run-level reuse (`REUSED_RESULT`) already exists and is not used for witnesses (B5); pair-level reuse is added above it.
8. The `evidence_bundle` table is unused; bundles are files (section 3).
