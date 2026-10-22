# The Incremental Witness: the jury demonstrations

Two demonstrations run by one script, `scripts/twist_demo.py`, on real sandboxes, from a warm store. A third part shows the editor. For the page-by-page story of the whole product see `docs/DEMO_GUIDE.md`; for what is and is not verified see `docs/INCREMENTAL_WITNESS_REPORT.md`.

Say the mode out loud: everything here is a real run in Docker. Nothing is mocked; the repositories are the committed fixtures served from a local remote, so their pinned commits are the same every time.

## 0. Preparation (once, not shown)

```powershell
cd C:\Users\Chetan\Hackethopia
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --preflight
```

If the preflight says there is no warm store, create it. It is a real cold run of five pairs (about 13 minutes), and it is what makes the demonstrations fast:

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --warm
```

The warm store (database and objects) is kept under `var/twist_demo/warm`, and its checksum is written to `var/twist_demo/warm.json`. Each demonstration copies it first, so the warm store itself is never written to. The preflight re-checks the checksum.

Docker must be running and no other Faultline stack should be running (its worker removes containers it does not own).

## 1. Demo A: it remembers, and it re-runs only what changed (about 6 minutes)

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --demo A
```

What to say and what appears:

1. **"I start from the warm store."** Line: `start from the warm store (checksum equal)`.
2. **"Same repositories, same commits, nothing changed: run it again."** The counters show every pair reused, none computed:
   `every pair is reused, none is computed`, `no oracle ran in this analysis (0 fresh executions)`, `one PAIR_REUSED event per pair`.
   Say: "It found each stored answer, checked the answer and its evidence by hash, and used it. The sandbox did not start for any pair."
3. **"Now one producer gets a new commit"** (a comment line in `acme-showcase`). The counters show one pair computed and the rest reused:
   `only the changed producer's pair is computed; the others are reused`.
   Say: "It tells me why: the printed reason is CHANGED and it names the producer's own inputs that differ. The other pairs did not run."
4. `no stored object was rejected` closes the run.

Reference numbers from the earlier five-pair measurement (not a promise for another machine): cold analysis 680.0 s, unchanged rerun 47.9 s, one changed producer 351.5 s (`evidence/M13.4/`).

## 2. Demo B: a crash does not lose the search (about 8 minutes)

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --demo B
```

The fixture has two repositories whose dependency worlds differ by eight packages; one of them (`werkzeug`) breaks the import. Finding which one takes ten sandbox tests (labelled before the first run in `fixtures/twist/bisect.yaml`).

1. **"I start the analysis in a worker process and stop it for real, right after the third test result was stored."** Line: `the worker ended abruptly (exit code 77, no clean-up)` and `three test results were stored before the stop`.
2. **"Now I restart."** A new analysis of the same pair takes the search over. Lines:
   - `every one of the 10 tests finished exactly once across both processes`
   - `no test whose result was stored was started again`
   - `the stored results were answered from the store (DDMIN_TEST_RESUMED)`
   - `the stored test objects are byte-for-byte the same objects` (their content-addressed ids did not change)
   - `the checkpoint chain is intact`
   - `the attribution is the labelled one` (`['werkzeug'] COMPLETE two_sided`)
   Say: "The three finished tests were not run again. The stop came right after the third result was stored and before its checkpoint, so nothing was lost in the middle of a test, and the stored result was found by its own identity. A worker killed in the middle of a test is shown by the recorded run (`evidence/M13.6/TC-13.6.2.txt`): that test is recorded as interrupted, not as a failure, and runs once more. The answer is the same as an uninterrupted run."

## 3. The editor (about 3 minutes)

Use `docs/DEMO_GUIDE.md`, Part 4, with `fixtures/repos/notify-svc/D` open. Sequence:

1. Open `app/main.py`: line 2 is red, **BREAK WITNESSED**, the same sentence as in the app.
2. Colours: red BREAK WITNESSED, yellow SILENT DIVERGENCE WITNESSED and EXPOSED, blue POTENTIAL, grey INCONCLUSIVE, nothing for NO DIVERGENCE OBSERVED. Only red means a reproduced failure.
3. `Ctrl+.` offers **Faultline: add werkzeug<3 to requirements.in (verified fix)**; it appends `werkzeug<3` and nothing else.
4. **Faultline: Analyse this repository**, then after about ten seconds **Faultline: Cancel the running analysis**; `docker ps` shows the job container gone within seconds and the job is CANCELLED.

The same sequence ran in a real VS Code 1.95.3 as three scripted sessions: `evidence/M13.8/vscode_information_session.jsonl`, `evidence/M13.9/vscode_fix_session.jsonl`, `evidence/M13.10/vscode_cancel_session.jsonl`.

## 4. If a check fails during the demonstration

The script prints `FAIL` for the check and exits with status 1. Do not hide it: say which check failed. Common causes: Docker not running; another Faultline stack running (stop it with `tools/fl.py down`); the warm store changed (run `--warm` again).

## 5. What the demonstrations do not show

They do not show a developer committing the fix to a real repository and re-analysing from GitHub, other editors, other ecosystems, or scale beyond five pairs. The report lists these under "Not done".
