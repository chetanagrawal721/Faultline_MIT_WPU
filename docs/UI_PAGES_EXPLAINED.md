# The interface explained, page by page, in detail

This document explains every page of the Faultline workspace, in the order of the left menu, starting with **Overview**. For each page it says:

- **What it is for**: the question the page answers.
- **What is on it**: every block, one by one.
- **Where the data comes from**: the API call and the stored records behind it.
- **How to read it**: what the numbers and labels mean, and what they do **not** mean.
- **What to say**: a sentence you can use in the demo.

Pictures of every page are in `docs/UI_SCREENSHOTS.pdf` (and `docs/screenshots/`). The words in **bold** are the real labels on the screen.

## 0. The frame that every page shares

### 0.1 The left menu (navigation)

Eleven entries, grouped under the heading **WORKBENCH**: Overview, New analysis, Findings, World matrix, Relationships, Inventory graph, Evidence, Jobs, Repositories, Capabilities, Settings. The selected entry is highlighted. The little arrow at the top lets you collapse the menu to icons. At the bottom:

- **API ok · schema v8**: the interface asked the server `/api/health` and got an answer. "schema v8" is the version of the SQL database layout. If the server is down this says the API is not reached, so a missing answer is never shown as an all-clear.
- **Exit workspace**: back to the product site (the public pages).

### 0.2 The top bar

- **Breadcrumb** ("Workbench / Overview"): where you are.
- **Active project** drop-down: a *project* is one investigation (a set of repositories you submitted). The choice is remembered in your browser. It controls the pages that show one analysis: Overview's funnel and Reuse panel, World matrix, Relationships, Inventory graph, Evidence, Repositories.
- **Mode badge** (**LIVE**): how results in this deployment were produced. LIVE means real executions in the sandbox. FIXTURE means committed example scenarios. REPLAY means recorded results without Docker. The mode is always visible because a recorded result must never be mistaken for a live one.
- **Theme button** (sun or moon): light or dark. Saved in the browser.

### 0.3 The mode banner

The bar under the top bar ("Live analysis of public repositories you submit.") with a coloured dot. It restates the mode in a sentence. In REPLAY mode it turns accent-coloured and says that re-runs are disabled; if the server cannot be reached it turns red and says so.

### 0.4 Page heading

Every page has a title, a one-line description, and on the right a button, usually **Overview** (back to the start) or a page-specific action (**New analysis**, **View all jobs**).

### 0.5 Vocabulary used everywhere

| Word | Meaning |
|---|---|
| **Producer / artifact / library** | The repository whose code is being checked (for example `acme-models`). |
| **Consumer** | A repository that uses the producer (for example `notify-svc`). |
| **Reference world** | The producer's own dependency set: what worked. |
| **Consumer world** | The dependency set the consumer's project really resolves. |
| **Delta** | The packages whose versions differ between the two worlds. |
| **Oracle** | A check run in the sandbox: O-import, O-tests, O-bind, O-contract. |
| **Witness** | A reproduced failure: 3 fresh passes in the reference world and 3 fresh failures in the consumer world, with the same failure signature. |
| **Pair** | One producer paired with the consumers that share one consumer world. Reuse is decided per pair. |

---

## 1. Overview

**What it is for:** the state of the whole system in ten seconds. It answers: what has been analysed, what was found, what is running, what failed, and what was reused instead of recomputed.

**Where the data comes from:** three calls: `/api/findings` (all findings), `/api/jobs?limit=50` (the latest 50 jobs), and `/api/projects/<id>/analysis` (the active project's newest analysis). The Reuse panel adds `/api/analyses/<id>/counters` and `/pairs`. Everything is read from the database; nothing is computed in the browser except counting.

### 1.1 The four number cards

| Card | What it counts | Note under it |
|---|---|---|
| **Investigations** | The number of projects. | "Counted from persisted records" |
| **Findings requiring review** | Findings whose verdict is BREAK WITNESSED or SILENT DIVERGENCE WITNESSED. | "Break or silent divergence witnessed" |
| **Inconclusive** | Findings with verdict INCONCLUSIVE. | "Not enough evidence either way" |
| **Jobs needing attention** | Failed jobs among the latest 50. | "Failed jobs among the latest 50" |

Important: the findings cards count **all findings in the database**, across all projects, not only the active project. The word "Loading" or a dash shows while data is on its way; a dash is never a zero.

### 1.2 Outcomes (the donut)

All findings split by verdict: **Break witnessed** (red), **Silent divergence** (purple), **Inconclusive** (amber), **No divergence observed** (green), **Other** (grey: EXPOSED, POTENTIAL, HYGIENE and so on). The centre shows the total. Each row has the count and the percentage. Clicking goes to Findings. Meaning: "of everything we looked at, how much was a reproduced break, how much was unsettled". It is not a statement that the green ones are safe: NO DIVERGENCE OBSERVED is scoped to what was exercised.

### 1.3 Jobs by status

Bars for **Completed**, **Failed**, **Running or queued**, **Cancelled**, counted over the latest 50 jobs. Clicking goes to Jobs. A cancelled job is a job someone stopped on purpose (for example from the editor); it is not a failure.

### 1.4 Reuse and recomputation (the twist)

The panel for the active project's newest analysis. Its meta text ("5 recorded events") is the number of events in the event log for this analysis.

- **Pairs reused**: a stored result was found for the pair key, verified, and used. No oracle ran for it.
- **Pairs recomputed**: the pipeline ran for the pair and finished.
- **Stored objects rejected**: a stored object was damaged or missing, so it was not used and the pair was computed again.
- **Worlds reused / built**: dependency worlds that already existed versus builds that actually ran.
- The table under it has one row per pair: the **Pair** key (shortened hash), the **Result** (Reused, Recomputed, Unfinished), **Why** (a sentence), and **Inputs that changed** (for a changed pair, the names of the inputs, for example `producer.commit, producer_artifact_sha256`; a dash when nothing changed).
- The note: "Counts come from the append-only event log. A reused pair is never counted as a fresh run."

How to read it: first run of a pair = recomputed 1, reused 0. The same analysis again = reused 1, recomputed 0, and the run finishes in under a minute. If one input changes, the reason lists it.

### 1.5 Analysis funnel

Eight tiles for the active project, each with a recorded count; each is clickable:

1. **Submitted**: repositories added to the project.
2. **Pinned**: repositories resolved to one exact commit.
3. **Inventoried**: repositories whose files and manifests were read (state INGESTED).
4. **Relationships**: relationships discovered.
5. **Worlds built**: cells, i.e. unique consumer worlds compared with a reference.
6. **Oracles run**: cells that finished (analysed or inconclusive).
7. **Witness**: cells with a witnessed break or silent divergence.
8. **Verdict**: cells that got a verdict.

Under it: "Latest analysis `an_…` · DONE · LIVE". Before any analysis the tiles say "No analysis yet" and a note tells you to open New analysis. If the analysis found no actionable relationship, a note says there is nothing to analyse, so an empty funnel is explained rather than left blank.

### 1.6 Needs attention

A short list of things that deserve a look: inconclusive findings, consumers that could not be analysed (with the reason), failed jobs. The same problem repeated is **one line with a count** (for example "×3"), and the header says "6 recorded · 2 kinds". Each line says where clicking goes ("Open the finding", "Open jobs"). If the list is empty it says so, with the reminder that this is a statement about the records, not about the repositories.

### 1.7 Recent investigations

The eight newest projects: **Investigation** name, **Repositories**, **Pinned revisions** (short commits joined by an arrow), **Mode**, **Stage** (the analysis status and outcome, or "No analysis"), **Result** (the strongest verdict among its cells). Clicking a row makes it the active project and opens Findings.

**What to say:** "This is the control room. Every number is a recorded fact; anything that failed is listed here instead of hidden."

---

## 2. New analysis

**What it is for:** start an investigation from two or more public GitHub repositories.

**Where the data comes from:** it writes: `POST /api/projects` (create), `POST /api/projects/<id>/repositories` (add and pin each repository), `POST /api/projects/<id>/analyze` (start). It reads `/api/scenarios` (the fixture examples) and `/api/capabilities` (the preview table).

### 2.1 The stepper

**1 Repositories → 2 Review pinned inputs → 3 Submit.** You cannot skip ahead: nothing runs before the commits are pinned and you confirm.

### 2.2 Step 1: the two input boxes

- **Producer repository** ("Reference input") and **Consumer repository** ("Downstream input"): each has **Repository URL** and **Branch, tag or commit (optional)**. Public GitHub repositories only. The ref is resolved to one immutable commit before anything else happens.
- The note: Faultline infers which repository shares code with which from evidence in the files; the labels producer and consumer are a hint for you, not an input to the result.
- **Add another repository**: include more than two (for example several consumers).
- **Pin repositories**: the server resolves each reference to a commit and fetches the files in the sandbox (a background job per repository).

### 2.3 Step 2: review

Each repository shows its **pinned commit**, its snapshot status and a summary of what was found (files, manifests). A repository that failed to fetch offers **Retry the same commit**. You tick a confirmation and click **Run analysis**. This step is where you say: "these exact commits are what every claim is about".

### 2.4 Step 3: submit

An analysis job is queued and the page moves to the Run page.

### 2.5 Capability preview and Fixture scenarios

- **Capability preview**: per ecosystem (pypi, npm, maven): INVENTORY, RESOLUTION, WORLD CONSTRUCTION, RUNTIME WITNESS as ENABLED or UNSUPPORTED. "Inventory support does not imply runtime execution support."
- **Fixture scenarios**: committed example repositories; each runs the real pipeline offline in the sandbox. The mode stays FIXTURE, because it is not analysis of a live repository.

**What to say:** "Everything starts by fixing the exact commits."

---

## 3. Analysis run (opened by New analysis)

**What it is for:** follow the real job while it runs.

**Where the data comes from:** `/api/jobs/<id>` is polled. The progress bar and message are what the worker reports: for example "discovering relationships", "building the projected consumer world", "running O-import (3 + 3 fresh runs) on …", "attributing the break in … (two-sided search)", "checking whether the job was cancelled", "reusing the stored result of this pair: none of its inputs changed, so no oracle runs".

- **Cancel job** calls `/api/jobs/<id>/cancel`. The worker stops the real sandbox container. The job ends CANCELLED, and the page then shows a panel **Cancelled with partial evidence**: a cancelled run leaves no finding behind.
- A failed job shows its error.
- When the job is done it links to the results.

**What to say:** "These are the real stages; nothing here is an animation."

---

## 4. Findings

**What it is for:** every verdict, in one list.

**Where the data comes from:** `/api/findings`.

- **Search box**: filters on repository, finding ID or text of the statement.
- **All verdicts** and **All modes** filters.
- **Table**: **Finding** (a short id), **Artifact → Consumer**, **Verdict** (coloured label), **Mode** (LIVE), **Scoped statement** (the sentence of the finding, shortened to a few lines; repeated reasons for many call sites read as one sentence with a count).
- The panel header says how many records match ("28 of 28 records").
- Clicking a row opens the finding.

Reading it: the verdict label is the claim, the mode says how it was produced, and the statement says exactly what was and was not shown.

---

## 5. Finding detail (the most important page)

**What it is for:** follow one conclusion from the claim down to the evidence.

**Where the data comes from:** `/api/findings/<id>` (the finding, its worlds, delta, runs, witnesses, scope) and `/api/findings/<id>/why-path`.

### 5.1 The verdict card

The verdict (**BREAK WITNESSED**), the mode, the title "Scoped verdict · artifact → consumer", and the full sentence. Two buttons: **World matrix** and **Open witness**. "Scoped" means the claim is limited to these two worlds and what was exercised.

### 5.2 The INCONCLUSIVE notice

For an INCONCLUSIVE finding a block says **This is not a pass.** An infrastructure, setup or timeout problem is never counted as a witness.

### 5.3 What the evidence establishes

Three columns:

- **What was observed**: the sentence of the verdict.
- **What remains uncertain**: what was not decided, for example "static API and usage exposure were not analysed".
- **Scope**: the two world hashes (reference → consumer), the verdict policy (`verdict-policy/1`) and the number of fresh runs.

### 5.4 Why-path

Each link says whether it was analysed:

1. **Why these repositories are related**: the relationship evidence (file and line).
2. **What differs between the two worlds**: the delta.
3. **What was run**: the oracle plan (which oracles ran, which were planned or not).
4. **Why this verdict**: the decision-table predicate and the "not checked" list.
5. **Which difference caused it**: the attribution, for example "COMPLETE, two-sided: werkzeug (minimal)". The experiments are labelled "attribution experiment (forced world)": they are worlds built for the search, not environments anyone uses.

### 5.5 Reference world and Consumer world

For each: the **World hash** (identity of the exact contents), the **Runtime** (for example cpython 3.12.15) and the number of **Packages**.

### 5.6 Dependency delta

Columns **Package**, **Reference**, **Consumer**. Heading: "Candidate causes only · not an attribution". A difference is not yet a cause; the attribution step decides that.

### 5.7 Repeatability

A table of every run: **World** (reference or consumer), **Run** number, **Provenance** ("fresh execution"), **Result** (PASS or ARTIFACT FAILURE), **MS** (milliseconds) and **Run ID**. The header says how many fresh executions there were. With several checks (import, call sites, tests, contract) each runs 3 + 3 times, so the header reads for example "18 fresh executions (3 checks, 6 each)". A reused result would appear as "reused" and is never counted.

### 5.8 Scope of this result

- **Modules imported**: what the consumer imports from the library, as chips.
- **Call sites checked**: for O-bind, grouped by file ("65 call sites in 12 files"); open it to see each file and the line numbers.
- **Not checked**: the honest list of what this result does not cover.
- **Why some interactions were not decided**: the reasons for inconclusive parts, grouped by cause.

### 5.9 Re-run live (3 + 3)

Runs the same check again right now in both worlds, three fresh executions each. It says it is live, not a stored result, and reports "Reference passed x/3, consumer failed y/3".

### 5.10 Propose and verify a fix

Proposes a version constraint for the attributed package (for example `werkzeug<3`), re-resolves with the native resolver, rebuilds the world, and re-runs the check 3 + 3. The result is a **diff only** and a label: **VERIFIED**, SUGGESTED or REJECTED with the reason. **Nothing is pushed.**

---

## 6. Witness detail

**What it is for:** the six runs behind a witness, one by one.

**Where the data comes from:** `/api/findings/<id>` (the witness and its runs) and `/api/witnesses/<id>/bundle`.

- When a finding has more than one witness (the import, the library's own test, a call site, a data contract) there are tabs, one per witness, for example "O-import: acme_models.web" and "O-tests: test_web.py::test_show_customer".
- **Four cards:** **Reference** "3 / 3 fresh passes", **Consumer** "3 / 3 fresh failures", **Signature** (the normalised failure), **Protocol** "Satisfied" (the 3 + 3 rule was met), plus "6 fresh · 0 reused".
- **Six-run witness board**: one card per run (Reference 1-3, Consumer 1-3) with the result tag, the "Expected passing behavior" or "Observed failing behavior" line, **Fresh execution** (Yes), **Run ID**, **Outcome**, **Signature**.
- **Witness** panel: **Interaction** (for example `acme_models.web via o_import 1.0.0`), **Normalized failure**, **Raised in** (the module where the error was raised), **Re-verifications**.
- **Raw output of one failing run** ("Bounded, secrets removed"): the real error text.
- **Inspect the evidence bundle** and **Download bundle**.

Reading it: "normalised" means paths and addresses are replaced so that the same failure in each run has the same text; that is how the three consumer failures are shown to be the same failure.

---

## 7. World matrix

**What it is for:** compare the two worlds and see which checks ran for each cell.

**Where the data comes from:** the active project's analysis (`/api/projects/<id>/analysis`), which carries the cells, worlds, delta, oracle plan and verdicts.

- **Coverage line** ("1 of 1 discovered consumers analysed. This is a count, not a score."): how many discovered consumers were actually analysed.
- **Matrix table**: **Consumer(s)**, **Cell** state (ANALYZED, NO_DRIFT, INCONCLUSIVE…), **Reference world**, **Consumer world** (hashes), **O-import**, **O-tests**, **O-bind** (RAN, PLANNED or NOT PLANNED), **Result** (the verdict).
- A line below the table lists consumers that were not analysed, with reasons ("0 unsupported · 0 failed · 0 inconclusive").
- **Reference world** and **Consumer world** panels: build state (BUILT), world hash, runtime, import visibility ("flat site-packages: the importer sees the resolved version"), modules exercised, consumers.
- **Exact delta against the reference** (labelled "Candidate causes only"): **Package**, **Reference**, **Consumer**, **Change** (CHANGED, ADDED or ABSENT).
- **Open the finding**.

Reading it: a cell is one unique consumer world. Several consumers with the same resolved world share a cell. A cell with state NO_DRIFT means the consumer resolves exactly the reference world, so nothing needs to run.

---

## 8. Relationships

**What it is for:** show why two repositories count as related, and which look-alikes were rejected.

**Where the data comes from:** the project's relationships in the analysis view.

- **Candidates table**: **Candidate** (producer → consumer), **Signals** (for example "shared artifact"), **Evidence level** (L2 · HIGH), **Status** (ACTIONABLE or SUSPECTED). The header counts "1 actionable · 0 suspected".
- **Relationship detail** (right): the evidence as file and line in both manifests at the pinned commit, each marked **OBSERVED**: for example the consumer's `requirements.txt` line naming the producer's git URL, and the producer's `pyproject.toml` line with its published name.
- **Inspect inventory** opens the graph.

Reading it: an actionable relationship needs hard evidence (the consumer declares a dependency on the producer's published name or git URL). A same-name different-source package is a *collision* and goes to the suspected tray; it never becomes a finding.

---

## 9. Inventory graph

**What it is for:** see the structure of everything that was read.

**Where the data comes from:** `/api/projects/<id>/inventory`.

- **Toolbar**: a search box (repositories, packages, manifests), a relationship filter, **Reset view**, **Add relationship** (declare a relationship by hand; it stays a candidate until evidence supports it).
- **Four counters**: **Visible nodes**, **Observed edges**, **Candidate edges**, **Data scope** (Persisted).
- **Dependency graph**: columns REPOSITORIES → PROJECTS → MANIFESTS → RESOLVED PACKAGES. Drag to pan, Ctrl and wheel (or the buttons) to zoom, click a node to highlight what it connects to. A solid line is an **observed** edge, a dashed red line a **candidate**. There is a mini-map at the bottom right.
- **Selected node** (right): the state and connections of the clicked node.
- **Graph inventory** table: every node with **Node**, **Type**, **State**, **Detail**.
- The note: "A connection is not a confirmed breakage."

---

## 10. Evidence

**What it is for:** the downloadable proof package behind a witness, and its checks.

**Where the data comes from:** `/api/witnesses/<id>/bundle/manifest` and `/bundle`.

- A selector at the top chooses the finding (and witness).
- **Artifacts** tab: every file in the bundle with **Artifact**, **Type**, **Size** and **SHA-256**: the README, the reproduction note, the artifact tree (sources, lock files), the run records.
- **Bundle manifest** tab: what the zip declares it contains.
- **Integrity** tab: the verifier's result: every file's hash, path and size checked; missing, changed, duplicated, `../` and oversized entries are rejected.
- **Replay** tab: a note that replay runs outside the interface: `python -m faultline.witnesses.replay bundle.zip` on a machine with Docker re-executes the check and reports EXACT_REPRODUCTION, ENVIRONMENT_LIMITED or NON_REPRODUCIBLE with reasons. The live re-run of a witness is on the finding page.

Reading it: this is the page that answers "can I check this without trusting you?". The hashes are computed over the file contents; a changed file no longer matches.

---

## 11. Jobs

**What it is for:** the history of background work.

**Where the data comes from:** `/api/jobs?limit=…`, refreshed automatically (the header says "refreshed every 3 seconds").

- **Job history**: **Job** (kind such as `live_analysis` or `ingest_repository`, with its id), **Status** (DONE, FAILED, RUNNING, QUEUED, CANCELLED), **Ran for**, **Waited** (time in the queue), **Failure class** (for example HANDLER_ERROR; "none" when it succeeded), **Attempts** (for example 1/3), **Note**.
- Running jobs can be cancelled here. A job that lost its worker is picked up by another after the lease expires (attempts rises).

Reading it: a long "Waited" means the worker was busy. A failure class names the kind of failure, and infrastructure failures are never treated as findings.

---

## 12. Repositories

**What it is for:** what was fetched and pinned.

**Where the data comes from:** `/api/repositories/<id>`, `/files` and `/projects`.

- **Table**: **Repository**, **Pinned** (the short commit), **State** (INGESTED), **Snapshot** ("12 entries · 5 manifest or lockfiles").
- The page also lists the projects detected inside the repository (for example a Python project with its manifests). If none has been resolved yet it says so and offers **Resolve worlds**, which resolves their dependency worlds.

Reading it: the commit shown is the one every claim is about.

---

## 13. Capabilities and coverage

**What it is for:** an honest statement of what this deployment can and cannot do.

**Where the data comes from:** `/api/capabilities` (computed by the server, including whether the sandbox boundary was verified).

- **Ecosystem support**: per ecosystem the four stages INVENTORY, RESOLUTION, WORLD CONSTRUCTION, RUNTIME WITNESS as ENABLED or UNSUPPORTED (hover for the reason). "Anything shown as unsupported or unavailable is not hidden."
- **Oracles**: O-IMPORT, O-TESTS, O-BIND, O-CONTRACT, each with its state and what it does ("3 + 3 fresh runs of the modules the consumer imports, in the sandbox").
- **Features**: repository ingestion, relationship discovery, witness verification, attribution, remediation and others, each with its state and details.
- If the sandbox cannot be verified, execution is disabled and this page says why.

---

## 14. Settings

**What it is for:** preferences and information about this installation.

- **Appearance**: the colour theme (light or dark), stored in the browser.
- **Access**: when the server requires an admin token for actions that start work, you enter it here (**Use this token** or **Forget this token**). If the server does not require one, the page says so.
- **Application information** (from the running API): **Mode**, **Authentication**, **API status**, **Database schema**, **API / capability version**, **Sandbox** (verified or not).

---

## 15. States you will see, and what they mean

| What you see | Meaning |
|---|---|
| A dash instead of a number | Data is still loading. It is not zero. |
| "No analysis yet" | The project has no analysis. Open New analysis. |
| **LIVE / FIXTURE / REPLAY** | How the result was produced. A recorded result is never labelled live. |
| **INCONCLUSIVE, "This is not a pass."** | Not enough evidence. The reasons are listed. |
| **Unsupported** | The deployment cannot do it, and says so. |
| "API not reached" | The interface cannot reach the server. No result is shown, which is not a clean result. |
| **Reused** (pair) | A stored, hash-verified result was used; no oracle ran. |

## 16. A walk through the pages in demo order

1. **New analysis** → paste two links → **Pin repositories** → **Run analysis**.
2. **Analysis run** → talk while it runs.
3. **Overview** → funnel and Reuse panel.
4. **Relationships** → why related. **World matrix** → the delta.
5. **Findings** → the finding → **Open witness** → **Propose and verify a fix**.
6. **Evidence** → the bundle and its hashes.
7. Run the same analysis again → **Overview** → **Reuse and recomputation**.
8. **Jobs**, **Repositories**, **Capabilities** only if asked.
