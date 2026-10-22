# The Incremental Witness: final report

This report says what was built for the twist, what was **verified** (with the file that shows it), what is **implemented but not verified**, and what is **not done**. Nothing outside the first list may be claimed as working. Numbers are copied from the evidence files named next to them; none is estimated.

Twist, in one sentence: Faultline stores every proven result as an immutable, hash-checked object, recognises a pair it has already proven (stable pair key) and re-runs only what changed, resumes a long cause search after a crash, and shows verdicts in the editor on the exact line, with a cancel that stops the real sandbox container.

Design and decisions: `docs/INCREMENTAL_WITNESS_METHODOLOGY.md`, `docs/INCREMENTAL_WITNESS_PLAYBOOK.md`, `docs/adr/0008-incremental-witness.md`, `docs/INCREMENTAL_WITNESS_AUDIT.md`. How to show it: `docs/INCREMENTAL_WITNESS_DEMO.md` and `docs/DEMO_GUIDE.md`.

## 1. Verified

Each row is a claim; the second column is the evidence file that shows it. `scripts/check_twist_docs.py` checks that every file named here exists.

| # | Claim | Evidence |
|---|---|---|
| V1 | Every result table row (runs, witnesses, attribution, findings, fix plans) is written from an immutable, content-addressed object and the tables can be rebuilt from the objects; the tables equal the pre-twist recording | `evidence/M13.2/TC-13.2.3.txt`, `evidence/M13.3/regression_projection_rebuild.txt` |
| V2 | An object's identity is deterministic, tampering with a stored object is rejected, and a crash leaves no partial object | `evidence/M13.1/TC-13.1.1.txt`, `evidence/M13.1/TC-13.1.2.txt`, `evidence/M13.1/TC-13.1.3.txt` |
| V3 | The pair key is the same across analyses and processes for the same pinned inputs, changes when and only when a real input changes, and `explain` names the changed input | `evidence/M13.3/TC-13.3.1.txt`, `evidence/M13.3/TC-13.3.2.txt`, `evidence/M13.3/TC-13.3.4.txt` |
| V4 | A cold run of five pairs computes all five (680.0 s analysis); the same project again reuses all five with zero fresh oracle runs (47.9 s) | `evidence/M13.4/TC-13.4.1.txt`, `evidence/M13.4/TC-13.4.2.txt` |
| V5 | A new commit in one producer recomputes only its pair (reused 4, recomputed 1) | `evidence/M13.4/TC-13.4.3.txt` |
| V6 | A damaged stored result is rejected (one `OBJECT_REJECTED`) and that pair is computed again | `evidence/M13.4/TC-13.4.4.txt` |
| V7 | A reused result is never counted as a fresh run and is never inside a witness | `evidence/M13.4/TC-13.4.5.txt` |
| V8 | The interface shows the counters and the per-pair reasons | `evidence/M13.4/TC-13.4.6.txt` |
| V9 | The instrumented cause search gives the same results as the earlier algorithm, can resume at every point, and a worker killed for real resumes without running a stored test again | `evidence/M13.5/TC-13.5.1.txt`, `evidence/M13.5/TC-13.5.2.txt`, `evidence/M13.6/TC-13.6.2.txt` |
| V10 | A stop between a stored result and its checkpoint does not repeat that test; a resumed attribution equals the uninterrupted one | `evidence/M13.6/TC-13.6.3.txt`, `evidence/M13.6/TC-13.6.5.txt` |
| V11 | The eight-candidate fixture finds the labelled cause (`werkzeug`) with the labelled number of sandbox tests, locally and from the published GitHub repositories | `evidence/M13.6/TC-13.6.1.txt`, `evidence/M13.6/TC-13.6.6.txt` |
| V12 | The language server speaks LSP 3.17 over stdio and a real VS Code 1.95.3 holds its diagnostic on the exact line | `evidence/M13.7/TC-13.7.1.txt`, `evidence/M13.7/vscode_diagnostics.jsonl` |
| V13 | Real analyses produce four severities in the editor: Error (BREAK WITNESSED), Warning (SILENT DIVERGENCE WITNESSED, EXPOSED), Information (POTENTIAL) and Hint (INCONCLUSIVE), each on the stored import line, in a real VS Code | `evidence/M13.8/TC-13.8.5.txt`, `evidence/M13.8/TC-13.8.6.txt` |
| V14 | A diagnostic from a changed file is marked stale, and positions are exact; no line is invented | `evidence/M13.8/TC-13.8.1.txt`, `evidence/M13.8/TC-13.8.4.txt` |
| V15 | The verified-fix code action edits the consumer's own requirements file, only when the file matches the one analysed; after the edit and a re-lock the fixed pair is recomputed with no break and the untouched pair is reused | `evidence/M13.9/TC-13.9.4.txt`, `evidence/M13.9/TC-13.9.5.txt` |
| V16 | `$/cancelRequest` stops the real sandbox container (answered in 0.02 s, container gone 1.39 s later), the job ends CANCELLED and the cancelled run leaves no finding or witness | `evidence/M13.10/TC-13.10.1.txt`, `evidence/M13.10/TC-13.10.2.txt` |
| V17 | A cancel in the middle of a minimisation test leaves a chain that resumes; every one of the 10 tests finishes once across both analyses | `evidence/M13.10/TC-13.10.4.txt` |
| V18 | The same cancel from a real VS Code session ends the request as cancelled, removes the container and marks the job CANCELLED | `evidence/M13.10/TC-13.10.5.txt` |
| V19 | Static evidence can only raise an unsettled (INCONCLUSIVE) cell to EXPOSED or POTENTIAL; a settled result is never changed; with no evidence nothing changes; no witness and no fix come from it | `evidence/M13.8/TC-13.8.5.txt` (live), unit tests `tests/unit/test_static_live_adapter.py` |
| V20 | The original SQL workflow passes with the evidence store off and on (unit 604 passed each; integration 72 passed off, 70 + 7 passed on after two fixes) | `evidence/M13.11/TC-13.11.1.txt`, `evidence/M13.11/TC-13.11.2.txt` |
| V21 | Parity: analysing the same pinned inputs with the store off and on gives identical findings, witnesses, attribution and the same verified fix | `evidence/M13.11/TC-13.11.3.txt` |
| V22 | Type check, frontend build and generated API types are current | `evidence/M13.11/TC-13.11.4.txt` |
| V23 | Demo A from a warm store: an unchanged rerun reuses every pair and runs no oracle; changing one producer recomputes only its pair | `evidence/M13.12/demo_A.txt` |
| V24 | Demo B: the cause search is stopped for real, restarted, and no stored test runs again | `evidence/M13.12/demo_B.txt` |
| V25 | The whole editor sequence in one real VS Code session: a BREAK WITNESSED error on line 2, the verified fix applied from the code action (only `werkzeug<3` appended), then an analysis started and cancelled from the editor; the container is gone and the job is CANCELLED | `evidence/M13.12/TC-13.12.3.txt`, `evidence/M13.12/editor_sequence.jsonl` |

## 2. Implemented, not verified

These exist in the code. They have not been shown to work in a real run, so they are not claims.

1. **Producer-side static diagnostics.** EXPOSED findings carry the source line of each reference in the producer and the language server places them. This is covered by unit tests only; no real VS Code session has shown a diagnostic on a producer's exposure line.
2. **Libraries in a sub-folder.** The static reference path is stored relative to the artifact's folder, the same way as call sites. A producer whose source is not at the repository root has not been tested.
3. **Compiled-only packages.** A package whose public API is compiled code cannot be read statically; the evidence says so (`limits`) and EXPOSED or POTENTIAL may still be raised from the readable part. Only `pydantic` (pure Python part) was exercised.
4. **Editors other than VS Code.** The language server follows the standard protocol, but no other editor was tried.
5. **Linux and macOS desktops.** The real-editor tests passed on Windows. The VS Code session test is skipped on a runner without a display.
6. **Scale.** No test measured behaviour with hundreds of pairs or very large stores.
7. **GitHub Actions.** The workflow exists and runs the same lint, pin, test, type-drift, build and boot steps. See section 4 for the state of the last run.

## 3. Not done

1. **A screen video of the editor sequence.** TC-13.12.3 is recorded as a scripted session: one real VS Code 1.95.3 shows the diagnostic, applies the verified fix and cancels an analysis without being restarted (V25). It is a step log and a `docker ps` timeline, not a video; nobody has recorded the screen.
2. **A live before/after editor fix on a real GitHub repository.** The fix is verified in a real VS Code on two prepared databases (before and after); the version where the developer commits the change and the project is re-analysed from GitHub has not been run.
3. **Other ecosystems.** npm and Maven are inventory only (unchanged from before the twist).
4. **Milestones outside the twist** that remain open in `CHECKLIST.md`: M11.4, M11.5, M12.1 to M12.4, M6.1, M7.2, M7.3, M8.1 to M8.3.
5. **What it does not claim.** Faultline does not say two setups are compatible. Where it cannot reproduce or read something, it says INCONCLUSIVE and lists what was not checked. A minimal set is the smallest found by the search, not a proof of global minimality.

## 4. Things found and fixed on the way (so they are not hidden)

| Finding | Fix | Evidence |
|---|---|---|
| With the evidence store off, the cause search returned no cause: the tests return an outcome plus detail and the plain search did not unpack it | unpack the outcome; regression test added | `evidence/M13.11/TC-13.11.3.txt` |
| A second analysis of the same pair reused the first one's result, so the old cancel test had no running verification to cancel | `FAULTLINE_REUSE=off` for that test | `evidence/M13.11/TC-13.11.2.txt` |
| The golden recording contained the image-specific environment fingerprint and could never match on another machine | the dump compares behaviour, not the machine; only those four lines of the recording changed | `evidence/M13.11/projection_after_golden.txt` |
| The tools failed in a normal PowerShell with "No Python at ..." because the packaged desktop app stores the interpreter in a private AppData copy | `fl.py` finds it; the guide says to use a normal Python | `tests/unit/test_fl_real_path.py` |
| 31 unit tests failed when the whole suite ran with the store off, because they test the store itself | they pin the store on for themselves | `evidence/M13.11/unit_store_off_first_run_31_failed.txt` |
| `billing-svc/H` used to be INCONCLUSIVE; it is now EXPOSED because its producer really references `pydantic.BaseSettings`, which pydantic 2 removed | expected value updated with the reason; new fixtures supply the Information and Hint cases | `evidence/M13.8/TC-13.8.5.txt` |

## 5. How to reproduce

1. `python scripts/twist_demo.py --preflight`
2. `python scripts/twist_demo.py --warm` (a real cold run; keeps the warm store and its checksum)
3. `python scripts/twist_demo.py --demo A` and `--demo B`
4. `python scripts/check_twist_docs.py` (claims map to evidence files; wording)
