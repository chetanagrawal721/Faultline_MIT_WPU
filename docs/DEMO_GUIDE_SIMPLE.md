# How to show the demo: a simple guide, page by page

This guide is for speaking in plain words. It follows the real screens and buttons in the app. It does not replace `docs/demo_script.md` (the short version) or `docs/DEMO_RUNBOOK.md` (what to start and what to paste); it explains the whole story from start to end, including the "Incremental Witness" part.

Words to avoid on stage: "compatible", "proof", "guarantee", "AI detected". Words to use: **BREAK WITNESSED**, **SILENT DIVERGENCE WITNESSED**, **NO DIVERGENCE OBSERVED**, **EXPOSED**, **POTENTIAL**, **INCONCLUSIVE**.

---

## 0. The story in one minute (say this first, before touching anything)

> "Imagine you wrote a small library. It works in your own repository. Then another team uses it, but their project picks **different versions of the same helper packages**. Now it breaks, and nobody knows why.
> Other tools say: *these versions are different*. That is only a warning.
> **Faultline runs the library in both setups, three times each, and shows you the real error.** If it fails the same way three times in one setup and works three times in the other, that is a **witness**. Then it finds which package caused it, and tells you the one-line fix.
> And the new part: it **remembers**. If nothing changed, it does not run again. If something changed, it re-runs only that part. And it shows the result **inside your editor**, on the exact line."

Keep it to these sentences. Everything after this is "let me show you".

Simple picture to use: *two kitchens, same recipe, different ingredients. We cook the dish three times in each kitchen. If it burns every time in kitchen B and never in kitchen A, we found the problem. Then we swap ingredients one by one to find which one burns it.*

---

## 1. Before the audience arrives (do not show this)

| Step | Command or action | You should see |
|---|---|---|
| 1 | Start Docker Desktop and wait until it is running | whale icon steady |
| 2 | `python tools/fl.py up --detach` | "API ok ... mode LIVE" |
| 3 | Open `http://127.0.0.1:8000/#/app` in the browser | the app with the left menu |
| 4 | Open the page **Capabilities** (left menu) once | the sandbox says verified |
| 5 | Run one warm-up: `python scripts/demo_check.py --case hero` | "Ready to demo." (about 2-3 minutes) |
| 6 | Open VS Code on the folder `fixtures/repos/notify-svc/D` with the Faultline extension loaded (see Part 4) | the extension is active |

Why warm up? The first run downloads and builds the dependency worlds. After that they are stored, and the demo is fast.

Say the mode out loud once: **"This is LIVE mode: everything you see is a real run, not a recording."** (The badge in the top bar shows the mode.)

---

## 2. Part 1: the normal website flow (about 4 minutes)

Use two real public repositories (full list in `docs/DEMO_RUNBOOK.md`):

- Library: `https://github.com/chetanagrawal721/faultline-fixture-acme-models`
- Consumer: `https://github.com/chetanagrawal721/faultline-fixture-notify-svc`

### Page 1: **New analysis** (left menu)

- **Do:** paste the library link, then the consumer link. Click **Pin repositories**.
- **Point at:** the **pinned commit** (the short code) next to each repository.
- **Say:** "Faultline fixes each repository to one exact commit. Every claim I make from now on is about these exact commits, not about 'the latest'."
- **Do:** tick the confirmation box, click **Run analysis**.

### Page 2: **Analysis run** (opens by itself)

- **Point at:** the progress messages: "discovering relationships", "building the projected consumer world", "running O-import (3 + 3 fresh runs)", "attributing the break".
- **Say:** "Right now it is building the consumer's setup in a locked sandbox, with no internet, and running the library there three times, and in its own setup three times. Nothing from these repositories runs outside the sandbox."
- **Fill the waiting time** with the story picture (two kitchens).

### Page 3: **Overview**

- **Point at:** the numbers at the top (consumers found, consumers analysed).
- **Say:** "If a consumer could not be analysed, it is listed with the reason. We never hide it."
- **Point at (the new part):** the panel **Reuse and recomputation**. It shows *Pairs reused*, *Pairs recomputed*, *Worlds reused / built*. On this first run: recomputed = 1 (or the number of pairs), reused = 0.
- **Say:** "Remember this panel. I will come back to it."

### Page 4: **Relationships** (left menu)

- **Do:** open the first relationship.
- **Say:** "This is the proof that the two repositories are related: the file and the line in both manifests. Look-alike names go to a 'suspected' list and never become findings."

### Page 5: **World matrix**

- **Do:** click the row.
- **Point at:** the **exact delta**, for example `werkzeug 2.2.3 -> 3.0.6`.
- **Say:** "This is the only difference between the two kitchens: the packages whose versions differ."

### Page 6: **Findings**, then the finding

- **Do:** open the finding. It says **BREAK WITNESSED**.
- **Say:** "Break witnessed means: it failed three times out of three in the consumer's setup with the same error, and passed three times out of three in the library's own setup."
- **Do:** click **Open witness**.
  - **Point at:** the six-run board. Every run says "Fresh execution: Yes".
  - **Say:** "Six real runs, none from a cache. Repeats must be fresh. A cached result can never count as a witness."
  - **Point at:** the error text, for example `cannot import name 'url_quote' from 'werkzeug.urls'`.
  - **Do:** open **raw output** of one failing run. "This is the real exception, not a summary."

### Page 7: the **why-path** on the finding

- **Point at:** the label **attribution experiment (forced world)**.
- **Say:** "To find the cause, Faultline swaps packages one at a time. Adding only `werkzeug` to the library's setup reproduces the failure. Putting the old `werkzeug` back in the consumer removes it. So `werkzeug` is the cause. These swapped setups are experiments, not real environments."

### Page 8: the fix

- **Do:** on the finding, run the fix action (the remediation).
- **Point at:** the diff (`werkzeug<3`) and the label **VERIFIED**.
- **Say:** "It does not push anything. It gives a one-line change, then re-resolves the setup with the normal resolver and runs everything again three times. Only then does it say VERIFIED."

### Page 9: evidence bundle

- **Do:** download the bundle from the witness page.
- **Say:** "Everything is in one zip with hashes. Anyone can check it on another machine, without Docker and without internet: `python -m faultline.witnesses.bundle witness.zip`."

---

## 3. Part 2: the "Incremental Witness" (about 2 minutes)

Plain meaning: **do not repeat work you already did, and prove it.**

### Step A: run the same analysis again, nothing changed

- **Do:** on **New analysis** (or the project's analyze action) run the same two repositories again.
- **Go back to:** **Overview** -> the panel **Reuse and recomputation**.
- **Point at:** *Pairs reused* is now 1, *Pairs recomputed* is 0.
- **Say:** "Nothing changed, so it did not run the sandbox again. It found the stored answer, checked that the answer and its evidence are intact, and reused it. This took seconds, not minutes."
- **Point at:** the pair status and the reason: *REUSED*.
- **Say:** "A reused result is never counted as a fresh run, so it can never fake a witness."

### Step B: change one thing, only that part re-runs

- **Do (prepared in advance):** run an analysis where one repository has a new commit (for example the library). Use the prepared second project.
- **Point at:** *Pairs recomputed* = the changed pair, *Pairs reused* = the untouched pairs. The reason lists what changed (for example the library's code hash).
- **Say:** "It tells you exactly why it re-ran: these inputs changed."

### Step C: damaged data is not trusted (optional, 30 seconds)

- **Say:** "If a stored file is damaged, the hash no longer matches, so Faultline rejects it, shows `OBJECT_REJECTED` in the event list, and recomputes. It never trusts a result it cannot verify."

### Step D: a long search that survives a crash (optional)

- **Say:** "Finding the cause can take many tests. If the worker is killed in the middle, the search resumes from a saved checkpoint. Finished tests are answered from the store; only the unfinished one runs again."
- **Show:** the Jobs page, then (with the prepared script) kill the worker, restart it, and point at the events `DDMIN_TEST_RESUMED`. Note: the one-command demo script (`scripts/twist_demo.py`) is part of milestone M13.12 and is not finished yet; until then this step is shown from the recorded evidence in `evidence/M13.5/`.

---

## 4. Part 3: the editor (about 2-3 minutes)

Open VS Code on `fixtures/repos/notify-svc/D` and open `app/main.py`.

### Show the colours (this is the "wow")

- **Point at:** the line `import acme_models.web as shared` (line 2) with a red underline.
- **Do:** hover over it.
- **Say:** "Same finding as in the website, but on the exact line in my editor. The colour follows the claim:
  - **Red (Error): BREAK WITNESSED.** A real failure was reproduced.
  - **Yellow (Warning): SILENT DIVERGENCE WITNESSED** (it runs but gives a different answer) and **EXPOSED** (your code uses something that changed, but no run settled it).
  - **Blue (Information): POTENTIAL.** Breaking changes exist and some uses could not be resolved. This is *not* a confirmed failure.
  - **Grey (Hint): INCONCLUSIVE.** We could not check; the message says why.
  - Nothing at all for NO DIVERGENCE OBSERVED."
- **Say:** "Blue and yellow from static reading are never presented as a confirmed break. Only red means we reproduced it."

### The fix from the lightbulb

- **Do:** put the cursor on the red line, press `Ctrl+.` (quick fix). Choose **Faultline: add werkzeug<3 to requirements.in (verified fix)**.
- **Point at:** the new line `werkzeug<3` appears in `requirements.in`.
- **Say:** "This is offered only because the fix was verified with fresh runs, and only if my file is still the same as the one that was analysed."
- **Say:** "After I re-lock and re-analyse, the red line is gone, and only the fixed pair is recomputed; the other pair is reused."

### Cancel from the editor

- **Do:** open the command palette (`Ctrl+Shift+P`), run **Faultline: Analyse this repository**, wait about 10 seconds, then run **Faultline: Cancel the running analysis**.
- **Say:** "Cancel is real. The request is cancelled, the sandbox container is stopped within a couple of seconds, and the job is marked cancelled. A cancelled run leaves no findings behind that look valid."
- **Show (optional):** `docker ps` in a terminal: the Faultline container disappears.

---

## 5. Closing (20 seconds)

> "Witnesses, not warnings. Red means we reproduced a failure, three times out of three, with fresh runs, and we found the package that causes it and a fix we re-checked. When we are not sure we say INCONCLUSIVE and tell you what we did not check. And because it remembers, the second run takes seconds, not minutes."

---

## 6. If something goes wrong (say it calmly and honestly)

| Problem | What to do and say |
|---|---|
| Internet or GitHub is down | Switch to FIXTURE mode with the local mirror. Say: "Network is off; this is the warmed fixture mode." |
| Docker is down | Use the REPLAY pack; the badge reads RECORDED and the re-run button is disabled. Say so. |
| A live run is slow | Show the previous run's record (labelled), then continue with the why-path. |
| VS Code shows nothing | The extension shows "API not reachable" rather than a clean result. Check the API address in settings (`faultline.api`). |
| A judge asks "is this a proof it will never break?" | "No. It shows a reproduced failure, or says what it could not check. It never says compatible." |

## 7. Questions judges may ask (short answers)

- **Why three runs?** One run can be luck or a flaky network. Three identical failures against three passes is our rule for a witness.
- **Does it run my code on your machine?** No. Repository code runs only in a locked Docker sandbox, with no internet while running. If the boundary cannot be verified, running is disabled.
- **Do you write your own version solver?** No. The package manager's own resolver and the project's lock file decide the versions.
- **Is AI in the decision?** No. The verdicts come from a fixed table of rules. The product works with the language model switched off.
- **What if the stored result is wrong or damaged?** Every stored result carries a hash; a damaged one is rejected and recomputed.
- **What is not done yet?** See the final report (`docs/INCREMENTAL_WITNESS_REPORT.md`, milestone M13.12) for the verified, implemented-but-not-verified and not-done lists.

## 8. Timing

| Part | Time |
|---|---|
| Story | 1 min |
| Website flow | 4 min |
| Incremental Witness | 2 min |
| Editor | 2-3 min |
| Close and questions | 1 min |
| **Total** | **about 10 minutes** (cut Step C and D for a 7-minute slot) |
