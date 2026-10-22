# Faultline: the complete demo, with everything you say

This is the one file to read before you demo. Read it once from top to bottom, then rehearse once with the project running. It has three kinds of text:

- **Understand**: what the project is, in plain words, so you can answer any question without notes.
- **Do**: exactly what to click, what you will see.
- **Say**: the words to speak. Read them out loud once so they feel natural; you do not need to memorise them word for word.

Shorter companions: `docs/DEMO_GUIDE.md` (steps only), `docs/DEMO_GUIDE_SIMPLE.md`, `docs/INCREMENTAL_WITNESS_DEMO.md` (the two script demos), `docs/judge_qa.md`.

Total time: about **15 minutes** (10 minutes if you skip the parts marked *optional*).

---

## Part 1. Understand the project (read this first, 6 minutes)

### 1.1 The problem, in one picture

You write a small library called `acme-models`. In your own repository it works, because your repository **pins** exact versions of its helper packages (for example Flask 2.2.2 and Werkzeug 2.2.3).

A second team writes `notify-svc` and uses your library. They do **not** pin Werkzeug, so their project quietly installs Werkzeug **3.0.6**. Werkzeug 3 removed a function that Flask 2.2.2 needs. Now importing your library inside their project fails with `ImportError: cannot import name 'url_quote'`.

Nobody changed any code. Only the **dependency versions** differed. This is called **dependency drift**, and it is expensive because the error appears far from its cause.

Think of **two kitchens, one recipe, different ingredients**. The dish burns in kitchen B and not in kitchen A. The ingredients are the dependency versions.

### 1.2 What other tools do, and what Faultline does

| | Other tools | Faultline |
|---|---|---|
| What they say | "These versions are different." | "Here is a real failure, run three times, with the exact error." |
| Kind of claim | A warning | A **witness**: reproduced evidence |
| Cause | Not found | Found by swapping packages one by one |
| Fix | A guess | A one-line fix that was **re-run and verified** |

The motto is **"Witnesses, not warnings."**

### 1.3 How it works, step by step (this is the pipeline you will show)

1. **Pin.** Every repository is fixed to one exact commit. Everything said afterwards is about those commits.
2. **Relate.** It finds which repository uses which, using evidence in the manifests (file and line). Look-alikes go to a "suspected" tray and never become findings.
3. **Build two worlds.** The *reference world* is the library's own pinned dependencies (what worked). The *consumer world* is what the consumer's project really resolves. Worlds are built offline inside a locked sandbox from the lock files, using the package manager's own resolver. Faultline does not write its own version solver.
4. **Run the oracles, 3 + 3 times.** An oracle is a check:
   - **O-import**: can the library's modules be imported?
   - **O-bind**: does each call in the library still match the function signature in the new world?
   - **O-tests**: do the library's own tests still pass?
   - **O-contract**: does data written in one world read the same in the other?
   Each runs **three times in the reference world and three times in the consumer world**, always freshly executed.
5. **Witness rule.** If the reference passes 3 of 3 and the consumer fails 3 of 3 with the **same normalised failure signature**, that is a **witness**. A cached result never counts. Infrastructure, timeout or resource failures are never witnesses.
6. **Verdict.** A fixed table of rules gives the verdict. There is no AI in the decision; the product works with the language model switched off.
7. **Attribute.** A two-sided search (DDMin) swaps packages to find the smallest set that causes the failure: adding only that set to the reference reproduces it, and reverting only that set in the consumer removes it.
8. **Fix.** It proposes a version constraint (for example `werkzeug<3`), re-resolves, rebuilds, and re-runs 3 + 3. Only then it says **VERIFIED**. It shows a diff and pushes nothing.
9. **Evidence bundle.** One zip with hashes. Anyone can verify and replay it elsewhere, without Docker and without internet.

### 1.3b The verdict words (use these exact words, nothing else)

| Verdict | Plain meaning |
|---|---|
| **BREAK WITNESSED** | Reproduced failure: 3 of 3 vs 3 of 3, same signature. |
| **SILENT DIVERGENCE WITNESSED** | It runs in both, but the answer differs, reproducibly. |
| **NO DIVERGENCE OBSERVED** | What we ran did not differ. Says nothing about what we did not run. |
| **EXPOSED** | The code uses something that changed; no run settled it. Read from source. |
| **POTENTIAL** | Breaking changes exist; some uses could not be resolved. Read from source. |
| **NOT EXPOSED** | No resolved use touches a changed symbol. |
| **INCONCLUSIVE** | Not enough evidence; the reasons are listed. Never a pass. |
| **HYGIENE** | Versions differ but the repositories are not related. |

Never say: "compatible", "proof", "guarantee", "AI detected".

### 1.4 The new part (the "twist"): the Incremental Witness

The judges' twist asked for four things. Know them as four sentences:

1. **It remembers.** Every proven result is stored as an immutable, hash-checked object. If you ask the same question again, it reuses the stored answer and shows how many pairs were *reused* versus *recomputed*. If one input changes, only the affected pair re-runs, and it tells you which input changed.
2. **It survives a crash.** The long cause search saves its progress after every test. If the worker dies, a new one continues and does not repeat any finished test.
3. **It lives in your editor.** A language server (LSP 3.17, over standard input/output) shows verdicts on the exact line in VS Code, with colours: red for a reproduced break, yellow for a silent difference or exposure, blue for a potential risk, grey for inconclusive. Code actions offer the **verified** fix only.
4. **Cancel is real.** Cancelling in the editor stops the actual sandbox container and marks the job cancelled. A cancelled run leaves no finding behind.

And one promise: **the original SQL workflow still works** (verified with the store switched on and off).

### 1.5 Measured numbers you may quote (each has an evidence file)

| What | Number | Evidence |
|---|---|---|
| Five pairs, cold run (nothing stored) | 680 s analysis | `evidence/M13.4/TC-13.4.1.txt` |
| Same five pairs again, nothing changed | **47.9 s**, 5 of 5 reused, 0 fresh oracle runs | `evidence/M13.4/TC-13.4.2.txt`, `evidence/M13.12/demo_A.txt` |
| One producer changed | 1 pair recomputed, 4 reused | `evidence/M13.4/TC-13.4.3.txt` |
| Cause search stopped after 3 stored tests, restarted | 10 tests finished exactly once, none repeated, cause = `werkzeug`, 83 s after restart | `evidence/M13.12/demo_B.txt` |
| Cancel from the editor | request answered 0.02 s, container gone 1.39 s later | `evidence/M13.10/TC-13.10.1.txt` |
| Hero example from GitHub | about 2-3 minutes with warm caches | `evidence/M13.6/TC-13.6.6.txt` (bisect: 159 s) |

Do not quote any other number. If asked "how fast is it generally?", say it depends on the number of pairs and on whether the worlds are already built, and give the table above.

### 1.6 What is **not** done (say it yourself, before a judge finds it)

- No single screen video of the editor sequence; it was verified as a scripted session in a real VS Code.
- A developer committing the fix to a real repository and re-analysing from GitHub was not run end to end.
- Only Python projects are executed. npm and Maven are inventory only, and the app says so.
- Static findings (EXPOSED, POTENTIAL) come from reading code and are labelled as such.
- Nothing was measured beyond five pairs.

Saying this openly makes the rest more believable.

---

## Part 2. Get ready (30 minutes before)

Do **not** use the virtual environment's python in PowerShell (it fails with "No Python at ..."). Use the commands below exactly.

### 2.1 Start everything

1. Start **Docker Desktop** and wait for it to be ready.
2. Close every other Faultline window or process. Run:

```powershell
cd C:\Users\Chetan\Hackethopia
$env:FAULTLINE_MODE = "LIVE"
& "C:\Python314\python.exe" tools/fl.py up --detach
```

   You should see `API ok (schema v8, mode LIVE) ...` (an `OSError ... handle is invalid` line after it is harmless).
3. Open **http://127.0.0.1:8000/#/app**. Check: top bar shows **LIVE** and "API ok · schema v8"; left menu has Overview, New analysis, Findings, World matrix, Relationships, Inventory graph, Evidence, Jobs, Repositories, Capabilities, Settings.
4. Click **Capabilities**: the sandbox must read verified.

### 2.2 Warm up (3 minutes)

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/demo_check.py --case hero
```

Wait for `Ready to demo.` This builds and stores the dependency worlds, so your live run later takes about two minutes instead of ten. Leave the project running.

### 2.3 Check the two script demos

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --preflight
```

You want `ALL CHECKS PASSED`. If it says there is no warm store, create it once (about 14 minutes, real run):

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --warm
```

Important: the script demos and the project's worker both use Docker. **Stop the project (`tools/fl.py down`) before you run a script demo**, then start it again afterwards. In a short slot, run the script demos *before* the audience arrives and show the saved output (`evidence/M13.12/demo_A.txt` and `demo_B.txt`) instead of running them live.

### 2.4 Prepare VS Code (for Part 6)

```powershell
& "C:\Python314\python.exe" tools/fl.py vscode fixtures/repos/notify-svc/D --api http://127.0.0.1:8000 --consumer chetanagrawal721/faultline-fixture-notify-svc
```

(`deactivate` first if your prompt shows `(.venv)`.) A VS Code window opens with Faultline loaded. The editor only shows what the **newest analysis containing this repository** says, so run the main example (Part 4) at least once before you show the editor.

### 2.5 Tabs and windows

1. Browser tab 1: the app (`#/app`).
2. Browser tab 2: `https://github.com/chetanagrawal721/faultline-fixture-acme-models` (to show the repositories are real and public).
3. VS Code window with `app/main.py` open.
4. A terminal for `docker ps`.
5. Close notifications. Set the browser zoom so text is readable from the back (about 110%).

### 2.6 Backup if something fails

In the app's top bar the **Active project** list contains finished analyses, for example **Live · demo check · hero** and **Live · demo check · bisect**. They open instantly. Say: "This is a stored result from an earlier live run."

---

## Part 3. Opening (1 minute, no clicking)

Stand on the **Overview** page.

> **Say:** "Hello. Imagine you wrote a small library, and it works perfectly in your own repository. Another team starts using it, but their project picks different versions of the helper packages. Suddenly it breaks, and nobody knows why, because no code changed.
>
> Today's tools tell you the versions are different. That is only a warning.
>
> Faultline does something different. It runs the library in both setups, three times each, and shows you the real error. If it fails the same way three times in one setup and works three times in the other, we call that a witness. Then it finds which package caused it and gives you a one-line fix that it has re-checked.
>
> Our twist for today is that it remembers. If nothing changed, it does not re-run. If one thing changed, it re-runs only that part. It survives a crash in the middle of a long search. And it shows the result inside your editor, on the exact line.
>
> Let me show you."

Picture to use if you want one more sentence: "Two kitchens, one recipe, different ingredients. We cook the dish three times in each. If it burns every time in one kitchen and never in the other, we have found the problem."

---

## Part 4. The main example in the app (5 minutes)

Two real, public repositories:

- Library: `https://github.com/chetanagrawal721/faultline-fixture-acme-models`
- Consumer: `https://github.com/chetanagrawal721/faultline-fixture-notify-svc`

### Step 4.1: New analysis (1 minute)

**Do:** left menu → **New analysis**. In **Producer repository → Repository URL** paste the library link. In **Consumer repository → Repository URL** paste the consumer link. Leave "Branch, tag or commit" empty. Click **Pin repositories**.

**You see:** the three steps at the top (1 Repositories, 2 Review pinned inputs, 3 Submit), and the **pinned commit** next to each repository.

> **Say:** "I give it two public repositories: the library, and a service that uses it. I do not tell it how they are related; it works that out from evidence in the files.
>
> The first thing it does is fix each repository to one exact commit. Look at the short commit codes here. Every claim I make from now on is about exactly these commits, not about 'the latest version'. That is what makes the result reproducible.
>
> Below you see the capability table. Python is fully supported. npm and Maven are inventory-only, and it says so instead of pretending."

**Do:** tick the confirmation box, click **Run analysis**.

> **Say:** "This starts a background job. The code is fetched and run only inside a locked Docker sandbox. Nothing from these repositories runs on this laptop."

### Step 4.2: The run (about 2 minutes, you talk)

**You see:** the Analysis run page with messages that change: "discovering relationships", "building the projected consumer world", "running O-import (3 + 3 fresh runs)…", "attributing the break…".

> **Say (while it runs):** "Right now it is building the consumer's dependency setup, offline, from the lock files, with the package manager's own resolver. We do not write our own version solver.
>
> Then it imports the library three times in the library's own setup, and three times in the consumer's setup. Fresh each time. That is the rule: three and three.
>
> If the consumer fails, it starts a second search that swaps packages one by one to find the one that causes it."

Use the two-kitchens picture here. Do not talk about internals. If the audience looks bored, open the browser tab with the GitHub repository and say "these are real public repositories".

### Step 4.3: Overview (1 minute)

**Do:** when the job says done, click **Overview** in the left menu.

**You see:** cards (Investigations, Findings requiring review, Inconclusive, Jobs needing attention), the Outcomes donut, Jobs by status, the **Reuse and recomputation** panel, the **Analysis funnel** (Submitted, Pinned, Inventoried, Relationships, Worlds built, Oracles run, Witness, Verdict) and **Needs attention**.

> **Say:** "This is the overview. The funnel shows every stage as a recorded count. If a consumer cannot be analysed, it appears under 'Needs attention' with the reason; we never hide it.
>
> Remember this panel, 'Reuse and recomputation'. On this first run it says one pair was recomputed and none reused. I will come back to it in a few minutes."

### Step 4.4: Relationships and World matrix (45 seconds)

**Do:** **Relationships** → open the first row. Then **World matrix** → the row.

**You see:** the evidence (file and line in both manifests) and a table PACKAGE / REFERENCE / CONSUMER, for example `werkzeug 2.2.3 → 3.0.6`.

> **Say:** "Here is why the two repositories are related: the file and the line in both manifests at the pinned commit. Look-alike names would go to a 'suspected' list, and never become findings.
>
> And here is the only difference between the two kitchens: the packages whose versions differ. Notice the heading says 'candidate causes only, not an attribution'. A difference is not yet a cause. We have to prove it."

### Step 4.5: The finding (45 seconds)

**Do:** **Findings** → open the top finding. It says **BREAK WITNESSED** and **LIVE**.

> **Say:** "This is the verdict: BREAK WITNESSED. Read it out: 'Reproduced: importing acme_models.web fails with ImportError: cannot import name url_quote from werkzeug.urls … 3 of 3 fresh runs on each side.'
>
> It also says what remains uncertain, here 'static API and usage exposure were not analysed' and 'data-contract replay was not run'. We tell you what we did not check. We never say 'compatible'."

**Do:** point at **Repeatability** and the six-run table.

> **Say:** "Reference passed three of three. Consumer failed three of three. Six runs, every one a fresh execution."

### Step 4.6: The witness (45 seconds)

**Do:** click **Open witness**.

**You see:** Reference 3 / 3 fresh passes, Consumer 3 / 3 fresh failures, the signature, Protocol: Satisfied, "6 fresh · 0 reused", the six-run board, and **Raw output of one failing run**.

> **Say:** "A witness needs three fresh passes and three fresh failures with the same failure signature. A cached result can never count towards a witness. And infrastructure problems, timeouts or resource problems are never a witness.
>
> This is the real exception from a real run, not a summary."

### Step 4.7: The cause and the fix (1 minute)

**Do:** **Back to the finding**. Point at the **Why-path** and the attribution label. Then click **Propose and verify a fix** and wait for the result (1-2 minutes; keep talking).

> **Say:** "To find the cause, Faultline swaps packages one at a time. Adding only werkzeug to the library's own setup reproduces the failure. Putting the old werkzeug back into the consumer's setup removes it. So werkzeug is the cause. Those swapped setups are experiments, not environments anyone uses, and the label says so.
>
> Now the fix. It proposes a constraint, werkzeug less than three, re-resolves the setup, rebuilds it, and runs the check three times on each side again. Only if that passes does it say VERIFIED. It does not push anything. You get a diff."

**You see:** the label **VERIFIED** and the diff `werkzeug<3`.

### Step 4.8: Re-run live (optional, 30 seconds)

**Do:** click **Re-run live (3 + 3)**.

> **Say:** "This button runs the check again right now, three fresh runs on each side. It is live, not a stored result."

### Step 4.9: Evidence bundle (optional, 30 seconds)

**Do:** on the witness page click **Download bundle**.

> **Say:** "Everything is in one zip file with hashes. Anyone can verify it on another machine, without Docker and without internet."

---

## Part 5. The Incremental Witness: it remembers (3 minutes)

### Step 5.1: Same analysis again

**Do:** **New analysis**, paste the same two links, **Pin repositories**, tick, **Run analysis**. It finishes quickly.

> **Say:** "Same repositories, same commits, nothing changed. Watch how long this takes."

### Step 5.2: The counters

**Do:** **Overview** → panel **Reuse and recomputation**.

**You see:** **Pairs reused** 1 (or more), **Pairs recomputed** 0, **Worlds reused / built**, and the pair row with the label **Reused** and the sentence "Every input of the pair key is unchanged, so the stored result was used and no oracle ran."

> **Say:** "Pairs reused: one. Pairs recomputed: zero. It did not start the sandbox. It found the stored answer, checked the answer and all its evidence by hash, and used it.
>
> The note at the bottom matters: 'a reused pair is never counted as a fresh run'. Reuse can never be mistaken for a new witness. The counts come from an append-only event log, so they are real, not computed to look good.
>
> On a set of five pairs we measured 680 seconds the first time and 47.9 seconds the second time, with zero fresh oracle runs."

### Step 5.3: One thing changes (use the recorded run, or run Demo A)

> **Say:** "Now suppose one library gets a new commit. Only the pair that involves it should run again, and Faultline should tell us why."

Show `evidence/M13.12/demo_A.txt` or run Demo A (see 5.5). Point at:
- `every pair is reused, none is computed` and `no oracle ran in this analysis (0 fresh executions)`,
- then after the change `only the changed producer's pair is computed; the others are reused (reused 4, recomputed 1)`,
- and `why it was computed again: CHANGED (producer.commit, producer_artifact_sha256)`.

> **Say:** "Four pairs reused, one recomputed, and the reason names the exact inputs that changed: the producer's commit and its code hash. This works because every pair has a stable key made from all its inputs: the commits, the lock files, the worlds, the tool versions, the rules. Same inputs, same key."

### Step 5.4: A damaged result is not trusted (optional, 20 seconds)

> **Say:** "Every stored result carries a hash. If one file is damaged, the hash no longer matches, Faultline rejects it with an event called OBJECT_REJECTED, and recomputes. We tested this: one rejected, that pair recomputed, the other four reused."

### Step 5.5: Demo B: a crash does not lose the search (optional but strong)

> **Say:** "Finding the cause can take many tests. What if the worker dies in the middle?"

Run it beforehand or show `evidence/M13.12/demo_B.txt`. To run live (about 8 minutes, stop the project first):

```powershell
& "C:\Python314\python.exe" tools/fl.py down
& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --demo B
```

Point at these lines:
- `the worker ended abruptly (exit code 77, no clean-up)`
- `three test results were stored before the stop`
- `every one of the 10 tests finished exactly once across both processes`
- `no test whose result was stored was started again`
- `the stored test objects are byte-for-byte the same objects`
- `the attribution is the labelled one (['werkzeug'] COMPLETE two_sided)`

> **Say:** "We stop the worker for real, right after the third test result is stored. Then we restart. The three finished tests are answered from the store; they are not run again. All ten tests finish exactly once in total, and the answer is the same as if nothing had happened. The fixture has eight differing packages and exactly one of them, werkzeug, is the cause. We wrote that expectation down before the first run."

(Demo A live: `& "C:\Python314\python.exe" tools/fl.py script scripts/twist_demo.py --demo A`; step 1 takes about 47 seconds, step 2 about 6 minutes, so run step 2 beforehand.)

---

## Part 5b. Show where the data is stored (2 minutes, the database)

Judges often ask "where does it store this?". Show it. The viewer is read only, so it is safe to run while the project is running and it cannot change or damage anything.

### Where the data is (say this first)

> **Say:** "Faultline keeps its data in two places. First, a normal SQL database: one SQLite file, `var/faultline.db`. It holds the repositories, the worlds, the runs, the findings, and the jobs. This is the original design and it still works exactly as before.
>
> Second, the twist added an evidence store next to it: a folder of immutable files, `var/evidence/objects`. Every proven result, that is every oracle run, witness, attribution, verdict and fix plan, is written there once, as a file whose name is the SHA-256 hash of its content. The result tables in SQL are written from those objects and can be rebuilt from them."

### Do: run the viewer

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/show_store.py
```

It prints six sections. Walk through them with these words:

1. **Where the data is.** "Here is the SQL file and its size, and here is the evidence folder with its object files. The name of each file is the hash of its content, so a changed or damaged file no longer matches its own name."
2. **The tables.** "These are the row counts of the tables: inputs, worlds, analysis, results, and the new evidence-store tables: `object_index`, `pointer`, `pair_index`, `pair_cell`, `ddmin_checkpoint`, `evidence_event`."
3. **By kind of object.** "These are the kinds of object in the store: oracle results, witnesses, verdicts, attributions, pair records, and the minimisation's checkpoints and tests."
4. **Pair keys.** "One key per producer-consumer pair. This is how reuse recognises a pair: same key, same inputs, so the stored result can be used. These keys are why the second run took 47.9 seconds."
5. **The newest events.** "This is the append-only event log. Look at `PAIR_REUSED`, `WORLD_REUSED`, `POINTER_MOVED`, `JOB_DONE`. The database refuses to update or delete a row here, so it is a trustworthy history. The reuse counters on the Overview page are counted from this log."
6. **One stored object.** "This is the latest verdict, exactly as it is on disk: its kind, its policy, the sentence it says, and how many pieces of evidence it cites."

### Do: show one object in full (optional, 20 seconds)

Copy the command printed under section 6 (`... --object <id>`), run it, and scroll a little.

> **Say:** "This is the real file. You can open it in any editor. It is plain JSON."

### Do: ask the database a question (optional, 30 seconds)

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/show_store.py --sql "SELECT kind, COUNT(*) AS n FROM evidence_event GROUP BY kind ORDER BY n DESC"
```

> **Say:** "It is a normal SQL database, so I can query it. Here is how many events of each kind were recorded. Only SELECT statements are accepted in this viewer."

Other queries that read well:

- `SELECT pair_key, created_at FROM pair_index` - the pair keys.
- `SELECT slot, seq FROM pointer LIMIT 10` - the current version of each result.
- `SELECT kind, subject FROM evidence_event WHERE kind LIKE 'PAIR_%' ORDER BY id DESC LIMIT 10` - reuse and recomputation events.
- `SELECT verdict, COUNT(*) FROM finding GROUP BY verdict` - the findings by verdict.

### Do: show that a damaged object is caught (optional, 1 minute, on a copy)

First the normal check:

```powershell
& "C:\Python314\python.exe" tools/fl.py script scripts/show_store.py --check
```

> **Say:** "This re-reads every stored object and re-computes its hash. All of them match their names."

Now damage a **copy**, never the real store:

```powershell
Copy-Item var\evidence var\evidence_demo -Recurse
$f = Get-ChildItem var\evidence_demo\objects -Recurse -Filter *.json | Select-Object -First 1
(Get-Content $f.FullName -Raw).Replace('"kind":"', '"kind" :"') | Set-Content $f.FullName -NoNewline
$env:FAULTLINE_EVIDENCE_DIR = "var\evidence_demo\objects"
& "C:\Python314\python.exe" tools/fl.py script scripts/show_store.py --check
Remove-Item Env:FAULTLINE_EVIDENCE_DIR
Remove-Item var\evidence_demo -Recurse -Force
```

You see `1 object(s) do not match: ... (CORRUPT)`.

> **Say:** "I changed one character in a copy, and the check finds it immediately. If this were a real stored result, Faultline would reject it, record an `OBJECT_REJECTED` event, and recompute that pair. It never trusts a result it cannot verify."

### If you want a graphical view

Any SQLite viewer opens the same file: for example DB Browser for SQLite (open `varaultline.db`, tab "Browse Data"). Open it **read only** during a demo.

### What to avoid saying

- Do not say the data is "encrypted" or "tamper-proof". Say it is hash-checked: a change is detected.
- Do not say the SQL tables are the source of truth for results. Say: the objects are, and the tables follow them.

---

## Part 6. The editor (3 minutes)

Use the VS Code window with `app/main.py` open (`fixtures/repos/notify-svc/D`).

### Step 6.1: The diagnostic on the exact line

**You see:** line 2, `import acme_models.web as shared`, with a **red** underline. Hover over it: the message starts with **BREAK WITNESSED:** and is the same sentence as on the website.

> **Say:** "Same finding, now on the exact line in my editor. The colour follows exactly what Faultline can claim:
> red is a reproduced failure, BREAK WITNESSED;
> yellow is either a silent difference, meaning it runs but gives a different answer, or EXPOSED, meaning the code uses something that changed but no run settled it;
> blue is POTENTIAL, meaning breaking changes exist but some uses could not be resolved, and it is not a confirmed failure;
> grey is INCONCLUSIVE, with the reason in the message.
> Only red means we reproduced a failure. Blue and yellow from reading code are never dressed up as a confirmed break."

Optional: say "If I edit this file after the analysis, the diagnostic is marked 'this file has changed since the analysis'. It never invents a line."

### Step 6.2: The verified fix

**Do:** click line 2, press **Ctrl+.** and choose **Faultline: add werkzeug<3 to requirements.in (verified fix)**.

**You see:** the line `werkzeug<3` appended to `requirements.in`, and nothing else.

> **Say:** "This quick fix exists only because the fix was verified with fresh runs, and only when my file is exactly the file that was analysed. It edits the consumer's own dependency file and adds one line.
>
> We verified the whole loop in a real VS Code: after the edit and a re-lock, the break is gone, only the fixed pair is recomputed, and the other pair is reused."

(Honest note if asked: re-analysing from GitHub after a real commit was not run end to end.)

### Step 6.3: Cancel

**Do:** **Ctrl+Shift+P** → **Faultline: Analyse this repository**. Wait about 10 seconds. Then **Ctrl+Shift+P** → **Faultline: Cancel the running analysis**. In the terminal run `docker ps`.

> **Say:** "Cancel is real. When I cancel here, the language server sends the standard LSP cancel request, which reaches the job, which stops the actual sandbox container. In our test the request was answered in 0.02 seconds and the container was gone about a second and a half later. The job is marked cancelled, and a cancelled run leaves no finding behind that could look valid."

### Step 6.4: The four colours on real analyses (optional, 1 minute)

> **Say:** "These four colours come from real analyses, not from a mock-up. We have four small example services: one that really breaks, one that really diverges, one whose library uses an API that was removed, one with only a dynamic reference, and one we could not settle. All four were opened in a real VS Code and showed the right colour on line 2."

(Recorded in `evidence/M13.8/vscode_information_session.jsonl`.)

---

## Part 7. Closing (30 seconds)

> **Say:** "To summarise. Faultline gives witnesses, not warnings. Red means we reproduced a failure, three times out of three, with fresh runs. We find the package that causes it, and we give a fix that we re-checked.
>
> The twist makes it practical: it remembers what it proved, so the second run takes under a minute instead of eleven; it survives a crash in the middle of a long search; and it shows the result in your editor on the exact line, with a cancel that really stops the sandbox.
>
> And where we are not sure, we say INCONCLUSIVE and tell you what we did not check. Thank you. Questions?"

---

## Part 8. Questions you may get, with answers

1. **Why three runs on each side?** One run can be luck or a network accident. Three identical failures against three passes, with the same normalised signature, is our rule for a witness.
2. **Does it run my code on your machine?** No. Repository code runs only inside a locked Docker sandbox, with no internet while it runs. If we cannot verify the boundary, running is disabled.
3. **Do you write your own version solver?** No. The package manager's own resolver and the project's lock file decide the versions.
4. **Is AI involved?** No. The verdict comes from a fixed table of rules. The product works with the language model switched off.
5. **How do you know a stored result is not stale or wrong?** Every pair has a key from all its inputs. If any input changes, the key changes and the pair is recomputed. Every stored object has a hash; a damaged one is rejected. And a reused result is never counted as a fresh run.
6. **What exactly is in the pair key?** The commits, the lock and manifest digests, the world hashes, the producer artifact hash, the resolver name and version, the platform, the entry modules, the oracle versions, the sandbox image, the witness rule and the verdict rule.
7. **What if the worker crashes?** The search saves state after every test. A restart replays the search, answers finished tests from the store, and runs only the first unfinished one. We tested a kill in the middle of a test and a stop between a stored result and its checkpoint.
8. **Is the minimal set the true minimum?** It is the smallest the search found, checked in both directions. We do not claim global minimality.
9. **How does the editor know which worlds to use?** It does not build worlds. The backend builds them from the pinned GitHub commits; the editor shows the newest analysis for the repository in your folder. Uncommitted local edits are not analysed; the diagnostic is marked stale.
10. **Why is blue/yellow not red?** Because reading code is not running code. Red is reserved for a reproduced failure.
11. **Which languages?** Python is fully supported. npm and Maven are inventory only, shown as such.
12. **Did the original system keep working?** Yes. We ran the original SQL-based workflow with the new store switched off and on: 604 unit tests each, 72 integration tests with the store off, and a parity test that compares findings, witnesses, attribution and the fix.
13. **What about speed?** Cold five pairs 680 s, same again 47.9 s, one producer changed one pair recomputed. Cancel in about a second.
14. **What did not get done?** See section 1.6. We prefer to say it ourselves.
15. **Can I verify a witness without your system?** Yes: download the bundle; `python -m faultline.witnesses.bundle` verifies hashes; replay needs no Docker and no network.
16. **Why not just pin everything?** Many consumers do not control their dependency versions, and a pin elsewhere does not help the library's other users. Faultline shows the break and the smallest change that avoids it.

---

## Part 9. If something goes wrong

| Problem | What to do | What to say |
|---|---|---|
| Page says "refused to connect" | Start the project (Part 2.1) | - |
| `No Python at ...` or "not recognized" | `deactivate`, then use `C:\Python314\python.exe` as in Part 2 | - |
| Internet or GitHub is down | Pick a finished analysis in **Active project** | "No network here, so this is a stored result from an earlier live run." |
| Docker is down | Same as above; Re-run and the fix button need Docker | "Running is disabled when the sandbox cannot be verified. That is by design." |
| A live run is slow | Talk through the pipeline, or switch to a finished analysis | "This stage is waiting for real sandbox runs." |
| The editor shows nothing | Check `faultline.api`, `faultline.consumer`, and that an analysis containing this repository exists | "No answer is never shown as 'all clear'." |
| A script demo says FAIL | Read the line out; do not hide it | "This check failed; here is why." |
| A judge pushes: "is this a proof it will never break?" | - | "No. It shows a reproduced failure, or says what it could not check." |

## Part 10. One-page cheat sheet

1. Opening: problem, two kitchens, witness, remembers, editor. (1 min)
2. New analysis → **Pin repositories** → **Run analysis**. "Fixed to exact commits." (1 min)
3. While it runs: "built offline, 3 + 3 fresh runs, no solver of our own."
4. Overview: funnel, Reuse panel ("remember this"). Relationships, World matrix: "only the differing packages". (2 min)
5. Finding: BREAK WITNESSED, what is uncertain. **Open witness**: 3/3 vs 3/3, signature, raw output. (1.5 min)
6. Why-path: werkzeug is the cause. **Propose and verify a fix**: VERIFIED, `werkzeug<3`, nothing pushed. (1 min)
7. Reuse: run again → reused 1, recomputed 0, 47.9 s vs 680 s. Changed producer → only that pair, with the reason. (2 min)
8. Crash demo: stop after 3 stored tests, restart, 10 tests once, same answer. (1 min, recorded)
8b. Database: `show_store.py` - SQL file + evidence objects, pair keys, event log, one object, `--check`. (2 min)
9. Editor: red on line 2, colours, **Ctrl+.** verified fix, cancel and `docker ps`. (3 min)
10. Close: "Witnesses, not warnings. If unsure, INCONCLUSIVE." Then questions.

## Part 11. Rehearsal checklist (do this once, the day before)

1. Run Part 2 start to finish.
2. Run the whole of Parts 3 to 7 once with a timer. Target: under 15 minutes.
3. Read Part 8 aloud once.
4. Check that the backup analyses open (**Active project** list).
5. Keep this file open on a second screen, or print Part 10.
