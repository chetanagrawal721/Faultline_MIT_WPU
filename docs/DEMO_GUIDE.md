# Faultline demo guide: every step, from start to end

This is the complete, ordered guide for showing Faultline. Follow it top to bottom. Every step says **where** to be, **what** to click, **what you will see**, and **what to say**.

- Time: about **12 minutes** in full, **7 minutes** if you skip the steps marked *(optional)*.
- Companion files: `docs/demo_script.md` (short script), `docs/DEMO_RUNBOOK.md` (examples and timings), `docs/DEMO_GUIDE_SIMPLE.md` (the same story in simpler words), `docs/judge_qa.md` (questions).
- Labels written in **bold** are the real button and heading names in the app. Marks: **[seen]** means I opened that screen in the running app and read the label. **[prepare]** means you must prepare it before the demo (it is not automatic yet).

**Words to say:** BREAK WITNESSED, SILENT DIVERGENCE WITNESSED, NO DIVERGENCE OBSERVED, EXPOSED, POTENTIAL, NOT EXPOSED, INCONCLUSIVE, HYGIENE.
**Words never to say:** "compatible", "proof", "guarantee", "AI detected".

---

## Part A. Get ready (30 minutes before, not shown)

### A1. Start the project

1. Start **Docker Desktop**. Wait until it says it is running.
2. Open PowerShell in the project folder `C:\Users\Chetan\Hackethopia`.
3. Do **not** activate the virtual environment. Its launcher points into the Claude app's private AppData folder, which a normal PowerShell cannot see, so it fails with "No Python at ..." or "not recognized". Run the tool with any normal Python instead (it needs only the standard library, and it finds the right interpreter for the servers by itself). If `C:\Python314\python.exe` does not exist on your machine, use `py -3` or any Python 3.10+ you have:

```powershell
$env:FAULTLINE_MODE = "LIVE"
& "C:\Python314\python.exe" tools/fl.py up --detach
```

4. Wait for the line `API ok (schema v8, mode LIVE) ...`. (An `OSError: The handle is invalid` printed after it is harmless.)
5. Open **http://127.0.0.1:8000/#/app** in the browser. In the left menu you should see: Overview, New analysis, Findings, World matrix, Relationships, Inventory graph, Evidence, Jobs, Repositories, Capabilities, Settings. The top bar shows **API ok - schema v8** and the badge **LIVE**. **[seen]**
6. To stop everything later: the same Python with `tools/fl.py down`.

### A2. Check the machine (2 minutes)

1. Click **Capabilities** in the left menu. The sandbox must say it is verified. If it does not, running is disabled by design; fix Docker first.
2. In PowerShell run the preflight and a warm-up case (this builds and stores the dependency worlds so the live demo is fast):

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/demo_check.py --case hero
```

3. Wait for `Ready to demo.` (about 2-3 minutes). If it prints `FAIL`, read the line; common causes are Docker not running or no internet.

### A3. Prepare the second run for Part 3 **[prepare]**

Part 3 needs a *second analysis of the same two repositories*. Nothing to prepare: you will run **New analysis** twice with the same links. For the "one thing changed" step you need a project where one repository got a new commit. If you have not prepared one, say the sentence in Step 3.4 and show the reason column on the pair list instead of running it.

### A4. Prepare the editor (Part 4)

1. Open VS Code on the folder `fixtures\repos\notify-svc\D` (File -> Open Folder).
2. The extension must be loaded. From the project folder run:

```powershell
python tools/fl.py vscode fixtures/repos/notify-svc/D
```

   This opens an Extension Development Host with Faultline loaded.
3. In that window open Settings and set **faultline.api** to `http://127.0.0.1:8000` and **faultline.consumer** to `chetanagrawal721/faultline-fixture-notify-svc` (the repository this folder represents).
4. The editor shows findings from the **newest analysis that contains this repository**, so run the main example (Part 2) once before Part 4. The folder you open is only used to find the file and line; the dependency worlds always come from the pinned GitHub commits, never from the folder.
5. Close other VS Code windows that use a different API address.

### A5. Browser tabs to have open

1. Tab 1: `http://127.0.0.1:8000/#/app` (the app).
2. Tab 2: GitHub page of the library: `https://github.com/chetanagrawal721/faultline-fixture-acme-models` (to show the repositories are real).
3. A terminal window ready for `docker ps` (Part 4, cancel).

### A6. Backup (in case live fails)

The app already holds finished analyses. In the project picker (top bar, **Active project**) you can choose, for example, **Live - demo check - hero** or **Live - demo check - bisect**. Finished results open instantly: Overview, Findings, Finding, Witness. Say "this is a stored result from an earlier live run" if you use them.

---

## Part 1. The story (1 minute, no clicking)

Stand on the **Overview** page and say:

> "A shared library works in its own repository. Another team uses it, but their project picks **different versions of the helper packages**. Now it breaks, and nobody knows why.
> Existing tools say: *these versions differ*. That is a warning, not a fact.
> Faultline **runs the library in both setups, three times each, and shows the real error.** If it fails the same way three times in one setup and passes three times in the other, that is a **witness**. Then it finds which package caused it, and gives a one-line fix that it re-checked.
> The new part: it **remembers** what it already proved, so a second run takes seconds, and it shows the result **in your editor, on the exact line.**"

Picture to help: *two kitchens, one recipe, different ingredients. Cook the dish three times in each. If it burns every time in kitchen B and never in A, we found the problem. Then swap ingredients one by one to find which one burns it.*

---

## Part 2. The main example in the app (5 minutes)

Library: `https://github.com/chetanagrawal721/faultline-fixture-acme-models`
Consumer: `https://github.com/chetanagrawal721/faultline-fixture-notify-svc`

### Step 2.1: **New analysis** **[seen]**

1. Left menu -> **New analysis**. The page title is "New analysis" with three steps at the top: **1 Repositories**, **2 Review pinned inputs**, **3 Submit**.
2. In the box **Producer repository**, field **Repository URL**, paste the library link.
3. In the box **Consumer repository**, field **Repository URL**, paste the consumer link.
4. Leave **Branch, tag or commit (optional)** empty.
5. Click **Pin repositories**.
6. Say: "Public GitHub repositories only. Each is fixed to **one exact commit** before anything runs. Every claim from here on is about these commits, not about 'the latest'."
7. Point at the "Capability preview" table: pypi is ENABLED for inventory, resolution, world construction and runtime witness. Say: "Python is fully supported. npm and Maven are inventory only; we say so instead of pretending."

### Step 2.2: Review and submit

1. On step **2 Review pinned inputs** point at the **pinned commit** next to each repository.
2. Tick the confirmation box.
3. Click **Run analysis**.
4. Say: "This starts a background job. The code is fetched and run only inside a locked Docker sandbox with no internet while it runs. Repository code never runs on this machine."

### Step 2.3: Analysis run (opens by itself)

1. Read the progress messages as they appear; they are the real stages:
   - "discovering projects and building worlds"
   - "discovering relationships"
   - "building the projected consumer world"
   - "running O-import (3 + 3 fresh runs) on ..."
   - "attributing the break in ... (two-sided search)"
2. Say while waiting: "It is building the consumer's dependency setup offline, running the library there three times, and in its own setup three times. About 1-3 minutes with warm caches."
3. Fill the time with the two-kitchens picture. Do not talk about internals.

### Step 2.4: **Overview** **[seen]**

1. When the job says done, click **Overview**.
2. Point at **Investigations**, **Findings requiring review**, **Inconclusive**, **Jobs needing attention**.
3. Point at the **Analysis funnel**: 01 Submitted, 02 Pinned, 03 Inventoried, 04 Relationships, 05 Worlds built, 06 Oracles run, 07 Witness, 08 Verdict. Say: "Every stage is a recorded count. If a consumer could not be analysed, it is listed with the reason; we never hide it."
4. Point at the panel **Reuse and recomputation**. On this first run you should see *Pairs recomputed* above 0 and *Pairs reused* 0. Say: "Remember this panel; I will come back to it in Part 3."

### Step 2.5: **Relationships**

1. Left menu -> **Relationships**; open the first row.
2. Say: "This shows why these two repositories are related: the file and line in both manifests at the pinned commit. Look-alike names go to a *suspected* tray and never become findings."

### Step 2.6: **World matrix**

1. Left menu -> **World matrix**; select the row.
2. Point at the exact **dependency delta** table (columns PACKAGE, REFERENCE, CONSUMER). In the main example: `werkzeug 2.2.3 -> 3.0.6` and others.
3. Say: "This is the only difference between the two kitchens. Note the heading says *candidate causes only, not an attribution*: a difference is not yet a cause."

### Step 2.7: **Findings**, then the finding **[seen]**

1. Left menu -> **Findings**; open the top finding. The page says **BREAK WITNESSED** and **LIVE**.
2. Read the sentence out: "Reproduced: importing `acme_models.web` fails with `ImportError: cannot import name 'url_quote' from 'werkzeug.urls'` ... 3 of 3 fresh runs on each side."
3. Point at **What was observed**, then **What remains uncertain** ("static API and usage exposure were not analysed ..."). Say: "It tells you what it did *not* check. We never say compatible."
4. Point at **Repeatability**: "Reference passed 3/3 - consumer failed 3/3 - fresh executions 6/6".
5. Point at the table of six runs: reference 1-3 **PASS**, consumer 1-3 **ARTIFACT FAILURE**, each **fresh execution**.

### Step 2.8: **Open witness** **[seen]**

1. Click **Open witness**. The page is "Witness detail".
2. Point at: **Reference 3 / 3 fresh passes**, **Consumer 3 / 3 fresh failures**, **Signature**, **Protocol: Satisfied**, "6 fresh - 0 reused".
3. Say: "A witness needs three fresh passes and three fresh failures with the *same* failure signature. A cached result can never count."
4. Scroll to **Raw output of one failing run**: show the real exception text.
5. Point at **Inspect the evidence bundle** / **Download bundle**.

### Step 2.9: The why-path and the cause **[seen]**

1. Click **Back to the finding**. Find the **Why-Path** section ("Trace a scoped conclusion through its Why-Path").
2. Point at the label **attribution experiment (forced world)** if shown.
3. Say: "To find the cause, Faultline swaps packages one at a time. Adding only `werkzeug` to the library's own setup reproduces the failure. Putting the old `werkzeug` back in the consumer's setup removes it. So `werkzeug` is the cause. Those swapped setups are experiments, not environments anyone uses."

### Step 2.10: **Re-run live (3 + 3)** **[seen]**

1. On the finding page click **Re-run live (3 + 3)**.
2. Say: "This button runs the check again right now, three fresh runs on each side. It is live, not a stored result." (It takes a minute or two; you can talk during it or skip it if short on time.)

### Step 2.11: **Propose and verify a fix** **[seen]**

1. On the finding page click **Propose and verify a fix** (the area is labelled "Diff only - nothing is pushed").
2. Wait for the result. You should see the label **VERIFIED** and the diff `werkzeug<3`.
3. Say: "It re-resolves the setup with the normal resolver, rebuilds it, and runs the check three times on each side again. Only then it says VERIFIED. Nothing is pushed to anyone's repository. You get a diff."

### Step 2.12: Evidence bundle and replay *(optional)*

1. Back on the witness page click **Download bundle**.
2. In the terminal run `python -m faultline.witnesses.bundle witness.zip` (checks all hashes).
3. Say: "Anyone can verify this on another machine without Docker and without internet."

---

## Part 3. Incremental Witness: it remembers (2-3 minutes)

Plain meaning: **do not repeat work that is already proven, and prove that you did not.**

### Step 3.1: Run the same analysis again

1. **New analysis** -> paste the same two links -> **Pin repositories** -> tick -> **Run analysis**.
2. Say: "Same repositories, same commits, nothing changed."
3. This run finishes in under a minute (47.9 s measured) instead of the 680 s of the first run.

### Step 3.2: Show the counters

1. Open **Overview** and find **Reuse and recomputation** (it shows the newest analysis of the active project).
2. Point at **Pairs reused** (now 1 or more), **Pairs recomputed** (0), and **Worlds reused / built**.
3. Open the pair list in the panel: the pair shows **Reused**.
4. Say: "It did not start the sandbox. It found the stored answer, checked that the answer and its evidence are intact, and reused it. The note at the bottom says it: *a reused pair is never counted as a fresh run*, so reuse can never fake a witness."

### Step 3.3: Show it is not blind trust *(optional)*

Say: "Each stored result carries a hash. If a stored file is damaged, the hash does not match, Faultline rejects it (event `OBJECT_REJECTED`) and recomputes. It never trusts something it cannot verify."

### Step 3.4: One thing changes, only that part re-runs **[prepare]**

1. If you prepared a second project where one repository has a new commit, run it and open the same panel: **Pairs recomputed** = the changed pair, **Pairs reused** = the untouched pairs, and the reason lists what changed.
2. If not prepared, say: "If I change one repository, only the pairs that involve it re-run, and the panel names exactly which input changed."

### Step 3.5: A crash does not lose the search *(optional)*

Say: "Finding the cause can take many tests. If the worker is killed in the middle, the search resumes from a checkpoint; finished tests are answered from the store and only the unfinished one runs again." Show the recorded evidence in `evidence/M13.5/` if asked. (A one-command live version, `scripts/twist_demo.py`, belongs to milestone M13.12 and is not built yet.)

---

## Part 4. The editor (2-3 minutes)

Use the Extension Development Host window from step A4. Open `app/main.py`.

### Step 4.1: See the finding on the exact line

1. Line 2 is `import acme_models.web as shared`. It has a red underline.
2. Hover over it. The message starts with **BREAK WITNESSED:** and is the same sentence as on the website.
3. Say: "Same finding, now on the exact line in my editor. The colour follows what Faultline can claim:"

| Colour in the editor | Verdict | Meaning (say it simply) |
|---|---|---|
| Red (Error) | BREAK WITNESSED | We reproduced a real failure. |
| Yellow (Warning) | SILENT DIVERGENCE WITNESSED | It runs but gives a different answer. |
| Yellow (Warning) | EXPOSED | Your code uses something that changed, but no run settled it. |
| Blue (Information) | POTENTIAL | Breaking changes exist and some uses could not be resolved. Not a confirmed failure. |
| Grey (Hint) | INCONCLUSIVE | We could not check; the message says why. |
| nothing | NO DIVERGENCE OBSERVED, NOT EXPOSED | Nothing to show. |

4. Say: "Only red means we reproduced a failure. Blue and yellow from reading code are never dressed up as a confirmed break."

### Step 4.2: The verified fix from the lightbulb

1. Click on line 2, press **Ctrl+.** (quick fix).
2. Choose **Faultline: add werkzeug<3 to requirements.in (verified fix)**.
3. The line `werkzeug<3` appears at the end of `requirements.in`.
4. Say: "This action exists only because the fix was verified with fresh runs, and only if my file is exactly the file that was analysed."
5. Say: "After I re-lock and re-analyse, the red line disappears, and only the fixed pair is recomputed; the other pair is reused." (To show it live you must commit the change, add the new commit to the project and analyse again. For a quick demo, state it, or show the prepared before/after databases with `python scripts/vscode_fix_session.py`, which is the test used to verify this.)

### Step 4.3: Cancel from the editor

1. Press **Ctrl+Shift+P** and run **Faultline: Analyse this repository**. Wait about 10 seconds.
2. Press **Ctrl+Shift+P** and run **Faultline: Cancel the running analysis**.
3. In the terminal run `docker ps`: the Faultline job container is gone within a couple of seconds.
4. Say: "Cancel is real. It stops the sandbox container and marks the job cancelled. A cancelled run leaves no valid-looking findings behind."

### Step 4.4: The status when the API is down

1. If the API is stopped, the editor says "Faultline: the API is not reachable ... No result is shown, which is not a clean result." Say: "No answer is never shown as 'all clear'."

---

## Part 5. Close (30 seconds)

> "Witnesses, not warnings. Red means we reproduced a failure, three times out of three, with fresh runs, and we found the package that causes it and a fix we re-checked. When we are not sure we say INCONCLUSIVE and tell you what we did not check. And because it remembers, the second run takes under a minute instead of eleven."

---

## Part 6. If something goes wrong

| What happens | What to do | What to say |
|---|---|---|
| The page does not open ("refused to connect") | Start the project with step A1 | - |
| `No Python at ...` or "not recognized" in PowerShell | Do not activate the venv; use the `C:\Python314\python.exe` (or `py -3`) command in A1 | - |
| GitHub or internet is down | Pick a finished analysis in the **Active project** list (for example **demo check - hero**) | "Network is off; this is a stored result from an earlier live run." |
| Docker is down | Same as above; Re-run and the fix button need Docker | "Running is disabled when the sandbox cannot be verified. That is by design." |
| A live run is slow | Show the finished analysis, then do the why-path | "This stage is waiting for real sandbox runs." |
| The editor shows nothing | Check **faultline.api**, **faultline.consumer**, and that an analysis containing this repository exists | - |
| The editor says "API is not reachable" | The API is stopped or the address is wrong | "No result is shown, which is not a clean result." |
| A judge asks "is this proof it will never break?" | - | "No. It shows a reproduced failure, or says what it could not check." |

## Part 7. Short answers for questions

- **Why three runs on each side?** One run can be luck. Three identical failures against three passes is our rule for a witness.
- **Does it run code on my machine?** No. Repository code runs only in a locked Docker sandbox, with no internet while it runs. If the boundary cannot be verified, running is disabled.
- **Do you write your own version solver?** No. The package manager's own resolver and the lock file decide the versions.
- **Is AI deciding?** No. Verdicts come from a fixed table of rules. The product works with the language model switched off.
- **How do you know the stored result is right?** Every stored result has a hash; a damaged one is rejected and recomputed. A reused result never counts as a fresh run.
- **What can it not do?** It never says two setups are compatible (it only reports what it reproduced or could not check), it only fully runs Python today, and static reading (EXPOSED, POTENTIAL) is labelled as reading, not as a failure.
- **How does the editor know which worlds to use?** It does not build worlds. The backend builds them from the pinned GitHub commits; the editor shows the newest analysis for the repository in your folder. Uncommitted local edits are not analysed (the diagnostic is marked "this file has changed since the analysis").

## Part 8. Timeline for the clock

| Minute | Part | What is on screen |
|---|---|---|
| 0:00-1:00 | Story | Overview |
| 1:00-2:30 | New analysis and run | New analysis, Analysis run |
| 2:30-4:30 | Overview, Relationships, World matrix | tables and delta |
| 4:30-7:00 | Finding, Witness, Why-path, Fix | the evidence |
| 7:00-9:00 | Reuse (second run) | Overview, Reuse and recomputation |
| 9:00-11:30 | Editor | VS Code |
| 11:30-12:00 | Close | any |

For a 7-minute slot: skip Steps 2.5, 2.10, 2.12, 3.3, 3.5 and 4.4.

## Part 9. After the demo checklist

1. `python tools/fl.py down` (same base Python as in A1) to stop the project.
2. Nothing from the repositories was pushed anywhere; the fix is only a diff.
