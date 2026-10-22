# FAULTLINE: what is built, as of 2026-10-21

This is the status companion to `docs/FAULTLINE_MASTER.md`. The master says what FAULTLINE should be. This file says what exists, how it behaves, how it was verified, and what is not done. Where this file and the master disagree, the master is the specification and this file is the truth about the code. Every difference is listed in section 9 and in `docs/adr/`.

Nothing here is aspirational. A thing is "built" only if code exists, a test exercises it, and (for anything that runs code) it was run for real.

## 1. The product in one paragraph

FAULTLINE takes public GitHub repositories, pins each to an exact commit, works out which one consumes which, and builds the dependency world each consumer really resolves. For a shared library (the artifact) it runs the library in its own world and in every consumer's projected world, inside a locked-down sandbox, and reports a **witness** only when the same check passes three times fresh in one world and fails three times fresh with an identical normalized signature in the other. It then names the smallest package difference responsible, says plainly what it did not check, and exports an evidence bundle that can be verified and replayed on another machine. The LLM is never in the decision path; the product works with it off.

Rules that hold across the code (from `CLAUDE.md` and the master):
- Verdict words are exactly: BREAK WITNESSED, SILENT DIVERGENCE WITNESSED, NO DIVERGENCE OBSERVED, EXPOSED, POTENTIAL, NOT EXPOSED, INCONCLUSIVE, HYGIENE. Cell states NO_DRIFT and NOT_APPLICABLE exist but are not verdicts. A short list of overclaiming words (listed in `CLAUDE.md`) never appears in code, UI or docs; a test enforces it for code and UI.
- Infrastructure, harness, resolution, timeout and resource failures are never witnesses.
- Native resolvers and lockfiles are authoritative; there is no version solver of our own.
- No repository or package code runs outside the sandbox. If the boundary cannot be verified, execution is disabled.
- Numbers come from scripts with denominators, never typed by hand.

## 2. Status at a glance

| Measure | Value |
|---|---|
| Milestones done (tracker) | 49 of 63 |
| Test cases recorded as passed | 150 of 175 |
| Gates declared | A, B, C and D. Gate E is 3 of 5. Gate S is 1 of 5. Gate X is 4 of 12 |
| Conformance report | The last complete run that passed gave **MVP conformant: 34 of 34 canonical MUST rows**, with "NOT release-hardened" (that needs Gate E). That run was made **before O-tests was wired into the live pipeline**. A later run showed 3 rows failing (FR-12, FR-13, ER-1). Their causes were fixed (witness page, replay test, wheel fetch, see section 8) and the specific failing tests now pass, but **the full report has not been re-run since**, so the 34 of 34 is not re-confirmed on the current code |
| Unit tests | 394 pass, no container needed (re-run on 2026-10-21) |
| Integration and browser tests | run against real Docker, real wheels, real Chromium. On the latest CI run 587 passed, 3 failed, 2 skipped, 2 xfailed (about 590 tests) |
| CI | The last **green** GitHub Actions run (ubuntu-24.04) was the one that declared Gates A to D; it included a replay of a committed witness bundle on the clean runner. The **two latest runs are red**, each on the same 3 tests (section 8). The fixes pass locally (section 8) and are committed on top of the published history; a CI run with them is pending |
| Backend | 145 Python files, about 14,000 lines (`backend/faultline/`) |
| Frontend | React 19 + Vite, about 9,400 lines (`frontend/src/`) |
| Tests | 71 test files under `tests/` |
| Database | SQLite, 6 migrations, about 40 tables |

Gate meanings: A runnable skeleton; B fixtures run through the real pipeline; C first live vertical slice; D PS07-compliant MVP (every canonical MUST); E release-hardened deployment; S showtime (demo and submission readiness); X expansion items, each independent.

## 3. Architecture as built

```
 browser (React workspace)  ──HTTP──►  FastAPI (api/)  ──►  SQLite + content-addressed store (storage/)
                                            │
                                            ▼
                                  job worker (workers/)  ── leased, heartbeated, cancellable
                                            │
                                            ▼
                              live analysis pipeline (analysis/live.py)
        ingest ─► relationships ─► worlds/cells ─► oracles ─► witnesses ─► attribution ─► verdict ─► bundle
                                            │
                                            ▼  SandboxClient (only path to execution)
                                       sandboxd (sandbox/)
                         exec zone: no network      fetch zone: egress allowlist proxy only
```

**Modes.** FIXTURE (committed repositories run through the real pipeline), LIVE (public GitHub repositories you submit) and REPLAY (recorded evidence only; every action that would start work is refused, and no Docker or network is needed). The mode stored with each record is the mode shown; a request cannot change it.

**Sandbox.** Every job runs in a container with no network in the exec zone, a read-only root, dropped capabilities and resource limits. The image is referenced by digest. The fetch zone has no direct route out: it reaches only `github.com`, `api.github.com`, `codeload.github.com`, `objects.githubusercontent.com`, `raw.githubusercontent.com`, `pypi.org` and `files.pythonhosted.org`, on port 443, through an allowlisting CONNECT proxy (container `faultline-egress`) that refuses IP literals and non-public addresses and connects to the address it verified. sandboxd runs 13 boundary checks at start-up and disables execution if any fails. Harness scripts are baked into the image, so changing one needs `python scripts/build_images.py`.

**Identity and hashing.** All identity hashes come from one module (`core/hashing.py`). A world's hash is content-addressed. The artifact content hash is computed over the sorted relative path text and file hashes, so it is the same on Windows and Linux (an earlier version sorted Path objects and differed by operating system; that was found by the CI replay and fixed).

## 4. What each part does, where it lives, how it was verified

### 4.1 Core, storage, security (`core/`, `storage/`, `security/`)
Frozen domain models (ResolvedWorld, Cell, Witness, Finding, Job and their enums), canonical hashing, structured JSON logging with correlation ids and phase timings, secret scrubbing for logs and bundles, the SQLite schema and six migrations (init, jobs, ingestion, resolution, visibility, attribution), and retention that never removes evidence a finding refers to. Tests: `tests/unit/test_models.py`, `test_hashing.py`, `test_migrations.py`, `test_scrub.py`, `test_logging.py`, `test_retention.py`.

### 4.2 Ingestion, parsers, resolvers, relationships (`ingestion/`, `parsers/`, `resolvers/`, `relationships/`)
- URL and ref validation, resolution to a commit SHA, a restricted sandboxed fetch into an immutable hashed snapshot with a file inventory.
- Python parsers (requirements, pyproject including PEP 621 and 735, setup.py and setup.cfg read statically, never executed) with diagnostics for anything unsupported.
- npm manifests and lockfiles and Maven POMs are read as **inventory only**.
- Worlds come from a lockfile or from `uv pip compile --exclude-newer` (wheels only, `--no-build`, Linux platform). No solver of our own.
- Relationships: published names and git dependencies give L2 with file and line evidence in both manifests. Look-alikes go to a suspected tray and never become findings.

### 4.3 Worlds and cells (`worlds/`)
Reference world (the artifact's own resolved dependencies) and a consumer world projected onto the artifact's dependency closure (using wheel metadata edges). The cell records the exact delta (package, reference version, consumer version). Worlds are built offline from hash-verified wheels in a shared wheelhouse volume. **A wheel already in the wheelhouse with a hash the lock lists is used without contacting PyPI**; this took a world fetch from 55 seconds (and intermittent failure on a slow network) to 2 to 4 seconds. Forced worlds (used by attribution) are labelled "attribution experiment (forced world)". The test overlay (`worlds/overlay.py`) adds test packages to a runtime world without changing any runtime version, and marks the overlay forced if a conflict keeps the runtime version.

### 4.4 Oracles (`oracles/`, harness scripts in `oracles/harness/`)
| Oracle | What it does | When it runs live |
|---|---|---|
| O-import | imports the artifact and the modules the consumer actually imports, 3+3 fresh runs | always, for a cell with drift |
| O-tests | runs the library's own tests per test, on test-overlay worlds, 3+3 | **only if the library ships a `tests/` folder and a fully hash-pinned `requirements.test.lock.txt`**; otherwise the cell shows NOT PLANNED with the reason |
| O-bind | binds each real call shape found in the artifact source to the current signature with `inspect.signature(...).bind`; the call is never executed | when the artifact has resolvable call sites into packages that differ between the worlds |
| O-contract | pydantic only: bytes are produced once in the reference world and parsed in the consumer world; compares with the reference parse | when pydantic differs and the artifact defines pydantic models in modules the consumer imports |

Failure classification (`oracles/classify.py`) runs before anything can be evidence: harness, sandbox, network, timeout and resource failures, and a package a world simply does not contain, are not breaks. O-bind and O-contract limits: star-argument, dynamic and instance-method call sites are not checked; contract replay assumes serialization options (default and `exclude_none`) rather than reading them from call sites, and says so on the witness; other wire formats (protobuf and so on) are not replayed.

### 4.5 Witnesses, attribution, verdicts, evidence (`witnesses/`, `attribution/`, `verdicts/`, `remediation/`)
- **Witness rule** (`witnesses/verify.py`): reference passes 3/3 and consumer fails 3/3 with one normalized signature, all fresh executions classified as artifact failures. A cached result never counts as a repeat. A finding can have several witnesses, one per failing entry (for example an import and a test).
- **Silent divergence**: a contract input both worlds accept but read differently (a `ValueDivergence` signature) is a SILENT_DIVERGENCE witness with both values shown.
- **Attribution**: two-sided ddmin over the delta (add the cause to the reference and reproduce; revert it in the consumer and the failure goes), with a budget, honest partial results and labelled forced worlds. Attribution runs for import, call-site and contract witnesses; a failing-test witness is not separately attributed (its cause is found through the others).
- **Verdict table** (`verdicts/engine.py`, policy `verdict-policy/1`): a pure function of stored evidence with no LLM, clock or randomness. Findings are re-decided from stored runs when the policy version changes.
- **Evidence bundle** (`witnesses/bundle.py`): a versioned, hash-checked zip (schema `docs/schemas/evidence-bundle-v1.json`) with the artifact tree, both worlds and locks, the runs, the stored input bytes for contract witnesses, provenance, the verdict predicate and attribution. The verifier rejects missing, changed, duplicated, `../` and oversized entries and unknown schema versions.
- **Replay** (`witnesses/replay.py`, `scripts/replay_bundle.py`): verifies the bundle first, restores the artifact from the bundle (hash-checked), fetches wheels only by hash. Outcomes: EXACT_REPRODUCTION, ENVIRONMENT_LIMITED, NON_REPRODUCIBLE. **Replay and live re-run support import witnesses only**; for other witnesses they refuse with a clear message.
- **Remediation** (`remediation/minimal.py`): a constraint diff for a single attributed package (for example `werkzeug<3`), re-resolved by the native resolver and re-run 3+3, labelled VERIFIED, SUGGESTED or REJECTED. Nothing is pushed.

### 4.6 Static analysis (`diff/`, `usage/`, `analysis/static.py`) — read only; in the live run it can only raise an unsettled cell
`diff/surface.py` and `diff/delta.py` read a package's public API with the standard-library `ast` (never imported; ADR 0005 explains why not griffe), flag compiled modules and runtime exports, and compute an ApiDelta. `usage/index.py` builds the full usage index (aliases, re-exports through the artifact's own modules, wildcard imports, local type propagation, string paths, notebooks, generated code, dynamic forms) with statuses and **coverage**. `usage/exposure.py` intersects references with the delta and simulates call binding. The decision table has the EXPOSED, POTENTIAL and NOT EXPOSED rules with the 0.9 coverage gate. `python scripts/static_exposure.py --source DIR --pair PKG=old.whl,new.whl` runs it on real wheels. **It is not wired into the live analysis**, because the wheels live inside the sandbox volume. So the live pipeline never produces EXPOSED, POTENTIAL or NOT EXPOSED today.

Since the twist (M13.8), `analysis/static.py` reads the API surface of each changed package from the two worlds' wheels (parsed offline in the sandbox by `wheel_surface.py`, never imported) and the artifact's own references. When execution left a cell INCONCLUSIVE, the decision table is applied once more with that evidence and the result is taken only if it is EXPOSED or POTENTIAL; a witnessed, observed or not-applicable result is never changed, NOT EXPOSED is never taken, and no witness or fix comes from it. The rule is part of the pair key (`static_rule`). Evidence: `evidence/M13.8/TC-13.8.5.txt`.

### 4.6b The Incremental Witness (Phase 13)
An immutable, content-addressed evidence store under the SQL tables (the tables are written only by `evidence/projections.py` and can be rebuilt); stable pair keys with an `explain` of what changed; reuse of a verified stored result and recomputation of only the changed pairs, with counters from the event log; a resumable cause search (`attribution/checkpoint.py`); a language server (`lsp/`, LSP 3.17 over stdio) with diagnostics on exact lines, a verified-fix code action and a cancel that stops the real sandbox container; a VS Code extension (`editors/vscode/`); the demonstrations (`scripts/twist_demo.py`). Verified and unverified items are listed in `docs/INCREMENTAL_WITNESS_REPORT.md`.

### 4.7 Pipeline, worker, API (`analysis/`, `workers/`, `api/`)
`analysis/live.py` connects everything above. The worker leases jobs, heartbeats, honours cancel (it kills the job's containers), recovers from crashes and labels partial analyses CANCELLED, INTERRUPTED or ERROR with their evidence kept. Attribution, the Fix step and policy recompute find a finding's witnesses through the finding itself, so a **repeated analysis of the same repositories keeps its attribution and fix** (the first version looked them up through the first run's cell and lost them; fixed with a regression test). API endpoints: health, capabilities, scenarios (list and run), projects, repositories (add, files, projects, retry, analyze), project analysis and inventory and world, findings (list, detail, why-path, remediate), witnesses (bundle, bundle manifest, re-run), jobs (get, list, cancel). Mutating endpoints need an admin token when one is configured and are refused in REPLAY mode. The OpenAPI document and TypeScript types are generated and checked for drift in CI.

### 4.8 Frontend (`frontend/src/`)
React 19 + Vite, hash routing. A product site (landing, how it works, capabilities, documentation, access) and a workspace with 14 views fed by the API: Overview (outcome donut and job bars, funnel, needs-attention list, recent investigations), New analysis (wizard with capability preview and fixture scenarios), Run, Findings, Finding (why-path), World matrix (opens on the witnessed cell, shows each oracle's RAN, NOT PLANNED or BLOCKED), Witness (per-witness six-run board with tabs when there are several), Relationships (with the suspected tray), Inventory graph, Evidence (bundle inspector and integrity result), Jobs, Repositories, Capabilities, Settings. The inventory graph is a fixed-height canvas with layered layout, pan, zoom, fit, reset, a minimap and node focus, with the inspector and table scrolling independently. The sidebar collapses to an icon rail and pushes the content. Empty, failed, unsupported and inconclusive states are all distinct, and an empty view is never drawn as a clean result.

### 4.9 Tooling and release (`tools/`, `scripts/`, `.github/`, `benchmarks/`)
`tools/fl.py` (up, down, test, lint, check-pins, gen-types, check-types, ci). `scripts/`: build_images, warm_caches, export_replay, conformance_report, demo_check, replay_bundle, release_manifest, static_exposure, run_benchmark, fixture generators and publishers. CI pins every action to a commit SHA. The release manifest hashes the toolchain, image build inputs, lock files, sources, fixtures and contracts without timestamps or paths.

## 5. Verdicts the live pipeline can produce today

BREAK WITNESSED, SILENT DIVERGENCE WITNESSED, NO DIVERGENCE OBSERVED (scoped to what was exercised), INCONCLUSIVE (with reasons), HYGIENE (no L2 relationship), and the cell states NO_DRIFT and NOT_APPLICABLE. EXPOSED, POTENTIAL and NOT EXPOSED exist in the engine and are unit-tested but need the static analysis wired in.

## 6. Evaluation (from `scripts/run_benchmark.py`, denominators stated)

Seven labelled scenarios are evaluated of thirteen registered (A, B, C, D, G, H, L). Of three labelled breaks: consumer-derived worlds with the witness rule find 3 with no false positive; the author-selected matrix finds 0; version-only finds 3 but also raises 1 false positive; consumer-derived worlds without the witness rule find 2. Two of the three breaks are found only by running the artifact in consumer-derived worlds (B and D). These scenarios were written by the same team that built the tool, so this is a demonstration, not an accuracy claim, and there is no accuracy target. Not in the denominator: scenarios E and J (contract replay is built and tested separately, `tests/integration/test_o_contract.py`), F and I (static analysis), and the two real-world cases. **The committed benchmark report predates the static analysis, so its ablation rows B and C still say "not computed".**

## 7. Demo assets

Five demo cases built from public repositories under `https://github.com/chetanagrawal721/` (all prefixed `faultline-fixture-`, labelled as constructed examples):

| Story | Producer (artifact) | Consumer | Result | Measured |
|---|---|---|---|---|
| Import break | `acme-models` | `notify-svc` | BREAK WITNESSED (`url_quote` import fails; also the library's own test fails); cause `werkzeug`; O-import, O-tests and O-bind all RAN | 80 s |
| Call-site break | `acme-http` | `orders-svc` | BREAK WITNESSED at `retry.py:7`; the call that still binds is not reported; cause `urllib3` | 50 s |
| Data-contract break | `acme-contracts` | `billing-svc-contract` | BREAK WITNESSED: `middle_name: Field required` on a stored 2-field payload; cause `pydantic` | 129 s |
| Silent divergence | `acme-contracts` | `billing-svc-union` | SILENT DIVERGENCE WITNESSED: `reference=42, consumer="42"` | 100 s |
| One paste, everything | `acme-showcase` | `fulfilment-svc` + `reporting-svc` (control) | 4 witnesses from 3 oracles and a cell with no drift | 228 s, too long to paste live |

`docs/DEMO_RUNBOOK.md` has the exact steps, `docs/demo_script.md` the talk track, `docs/judge_qa.md` the questions. `python scripts/demo_check.py` is the preflight and rehearsal (`--case all` runs every story). The published `acme-models` carries two extra small functions (`upload_name`, `download_token`) that the local fixture does not, so that O-bind has real call sites to check.

## 8. What is NOT built or not complete (honest list)

- **O-tests** runs live only for a library with a tests folder and a hash-pinned test lock (`acme-models`). Others show NOT PLANNED with the reason.
- **Static analysis** (ApiDelta, usage index, exposure) is not part of the live run (section 4.6).
- **npm and Maven** are inventory only: no runtime witness for them. Python is the only ecosystem verified end to end.
- **Replay and re-run** handle import witnesses only.
- **Attribution** is not run for failing-test witnesses.
- **Remediation** is minimal: one attributed package, a constraint diff. No candidate beam search, what-if ranking or full gates (M8.1 to M8.3).
- **Not started**: differential type checking with pyright (M7.2), expanded O-bind (M7.3), relationship sufficiency matrix (M6.1), npm runtime verification (M9.1), Maven resolution and runtime (M10.1), concurrency and scale envelope (M11.4).
- **M11.5** (release manifest and clean-machine replay): the CI manifest and the clean-machine replay exist and pass (replay outcome ENVIRONMENT_LIMITED because CI builds its own image with a different digest), but the milestone is not recorded in the tracker: its Docker-stopped, network-off check is manual and was only approximated (Docker made unreachable by `DOCKER_HOST`, not stopped).
- **Open verification, as of 2026-10-21.** After O-tests was wired into the live run, a finding for `acme-models` has **two** witnesses (the import and the library's own test `test_web.py::test_show_customer`) and 12 fresh runs instead of 6. Three integration tests still assumed the old shape and failed on CI (the two latest GitHub runs are red for this reason): `test_durable.py::test_tc_5_3_1_...` (it expected 1 witness and 6 runs), `test_remediation.py::test_tc_8_0_1_...` (it expected the fix to clear only the import witness) and `test_rerun.py::test_a_witness_reruns_live_...` (it picked the newest witness, the test witness, and re-ran it as an import check). **Fixed and verified locally against real containers on 2026-10-21: `test_rerun.py`, `test_remediation.py` and `test_durable.py` all pass (9 tests, including a new one that checks a non-import witness is refused).** The fixes: remediation claims only the import witnesses it re-runs, `rerun_witness` refuses a non-import witness with a clear error, and the tests state the two-witness, 12-run reality. These fixes are in the `fix:` commit on top of the published history. **Still pending: a green GitHub Actions run with them, and a re-run of the full conformance report (about 25 minutes) on the current code.** Related fixes already made and verified in a live run: the witness page used to add the runs of both witnesses together ("6 / 3 fresh passes") and now judges each witness on its own six runs; a repeated analysis used to lose its attribution because it was found through the first run's cell.
- **Showtime items that belong to the team**: M12.1 slide-match check, M12.2 network-off rehearsal, M12.3 demo script rehearsal and judge Q&A, M12.4 submission pack.
- **Speed**: the one-paste showcase takes 228 to 405 seconds because it attributes four witnesses one after another; running them in parallel was considered and not done.
- **GitHub API limit**: unauthenticated use allows 60 calls an hour. Start the server with `GITHUB_TOKEN` set for rehearsals and the demo.
- Third-party behaviour marked VERIFY in the master: the fixture facts are covered by the hand-verification records (`fixtures/verification/`, milestone M1.0, done). The real-world case (milestone M12.1) is not fully verified: its slide-match check is open.

## 9. Differences from the master (all documented)

ADR 0001 tooling and runtime; 0002 generic job table; 0003 world identity; 0004 scenario C uses its own artifact (`acme-http`); 0005 the static API surface uses `ast`, not griffe; 0006 scenarios J and E use their own artifact (`acme-contracts`); 0007 the one oracle name `o_contract` replaces the master's `o_contract_producer` and `o_contract_consumer`. Everything else in the frozen contract (enums, verdict words, failure classes, scopes) is identical to the master, and a unit test fails if it drifts.

## 10. Operating notes that save time

- Use the project's Python: `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python`. The system Python lacks the dependencies.
- Start with `python tools/fl.py up --detach`, stop with `down`. After any backend change, restart; a server started earlier runs old code. After any change under `backend/faultline/oracles/harness/`, rebuild the image with `python scripts/build_images.py`.
- Check readiness with `python scripts/demo_check.py --preflight`.
- Record work with the tracker only: `python tools/track.py start|tc|done|note|gate`. Never edit `LOGBOOK.md`, `CHECKLIST.md`, `docs/FAULTLINE_PLAYBOOK.md` or `playbook/state.json` by hand. Do not mark a milestone done unless the tracker accepts it.
- Full verification: `python scripts/conformance_report.py` (about 25 minutes, run with nothing else using Docker; concurrent load causes false failures).
- Windows notes: artifact copy retries a refused rename; line endings are normalised before hashing; `CLAUDE.md`, `.env`, `var/`, `node_modules/` and `frontend/dist/` are git-ignored.

## 11. Where to look

| Area | Path |
|---|---|
| Specification | `docs/FAULTLINE_MASTER.md`, `docs/FAULTLINE_PLAYBOOK.md` |
| Conformance matrix | `docs/conformance/ps07-matrix.yaml` |
| Decisions | `docs/adr/` |
| Demo | `docs/DEMO_RUNBOOK.md`, `docs/demo_script.md`, `docs/judge_qa.md` |
| Backend | `backend/faultline/` (core, storage, sandbox, ingestion, parsers, resolvers, relationships, worlds, oracles, usage, diff, witnesses, attribution, verdicts, remediation, analysis, workers, api) |
| Frontend | `frontend/src/` (`app/views/`, `ui/`, `site/`, `lib/`, `api/`) |
| Fixtures and labels | `fixtures/repos/`, `fixtures/scenarios/`, `fixtures/verification/` |
| Tests | `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/security/` |
| Evidence per test case | `evidence/<milestone>/TC-<id>.txt` |
| Progress record | `LOGBOOK.md`, `CHECKLIST.md`, `playbook/state.json` (tracker-generated) |
