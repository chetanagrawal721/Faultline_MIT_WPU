# Faultline prompt book

HACKTOPIA 2026, PS07 (Cross-Repo Dependency Drift Detector). This book lists the prompts we gave the AI assistant to research, specify and build Faultline, in the order we gave them.

**What is included.** Only prompts that shaped the project: research, specification, build directives, design briefs, demo design, and the requests that changed what the product does.
**What is left out.** Prompts about git commits, repository hosting, commit authorship, status and timing questions ("how long will it take"), retries ("try again"), and other housekeeping.

Short prompts are quoted exactly as typed (spelling kept). Long prompts are stored word for word in [`docs/prompts/`](prompts/) and linked here. "Result" says what the prompt led to in this repository.

How this book is kept up to date: every new prompt that changes the project gets one more entry at the end of the matching section, with the next number, the date and its result. Housekeeping prompts are never added.

---

## 1. Research and positioning (29 Sep 2026)

### P-00 Prior-art check on a similar public project
Full text: [prompts/P00_prior_art_analysis.md](prompts/P00_prior_art_analysis.md)
Asked for a deep technical analysis of an existing public repository against PS07: what it really implements, what overlaps, what it does not solve, and where a clearly more novel direction exists. It required brutal honesty and no "feature additions called innovation".
**Result:** the gap we aimed at: showing that a version mismatch actually breaks something, instead of only listing that versions differ.

### P-01 Architecture and solution analysis
Full text: [prompts/P01_architecture_analysis.md](prompts/P01_architecture_analysis.md)
Role-based brief (supply-chain security, static analysis, dependency resolution, distributed systems). It rejected the basic "parse manifests, compare versions, show a red warning" design and asked for a solution that answers "this mismatch exists, but will it actually break anything, and what exactly?".
**Result:** the Faultline thesis: drift matters only when it becomes observable, shown by running the same checks in two dependency worlds ("witnesses, not warnings").

### P-02 Adversarial review of the proposed design
Full text: [prompts/P02_adversarial_review.md](prompts/P02_adversarial_review.md)
Asked the AI not to restart but to attack its own proposal: weak assumptions, contradictions, missing edge cases, feasibility, novelty and demo risk.
**Result:** the narrowed, defensible scope, the verdict vocabulary and the safety rules recorded in the master document and `CLAUDE.md`.

## 2. Specification (29 Sep to 11 Oct 2026)

### P-03 Master document and implementation blueprint
Full text: [prompts/P03_master_document.md](prompts/P03_master_document.md)
Asked for one extremely detailed source-of-truth document: components, data flow, algorithms, how failures are verified, security, UI, testing, and a build plan from zero to the final demo, without redesigning the agreed architecture.
**Result:** `docs/FAULTLINE_MASTER.md` (canonical specification) and the phased plan `docs/FAULTLINE_PLAYBOOK.md`.

### P-04 Presentation content
Full text: [prompts/P04_slide_content.md](prompts/P04_slide_content.md)
Asked for slide-by-slide text only (no design) for the official template, following a reference deck for depth and structure.
> "give research basis and references proeper with link okk and give it proper good and include importent references okk"

**Result:** the slide text and a research-basis and references slide.

### P-05 Complete project document
> "create complete document for me insted then okk"

**Result:** a standalone project document for sharing outside the chat.

### P-06 Plain-language explanation of the problem and the solution
> "make a proper document so that i understand the problem and current solution around it properly"

**Result:** a student-level explanation of PS07, the novelty gap and the approach.

### P-07 Locate the essential versus improvement milestones
> "so we did have docx which specified which subphases are essential to do and what we can do for improvement like depending on the how essential it is can you locate it"

**Result:** the P0 (essential) and P1 (improvement) split in the playbook. The rule "finish all P0 before P1" is in `CLAUDE.md`.

## 3. Build directives (12 to 13 Oct 2026)

### P-08 Start phase 0
> "start phase 0 ... hackathon is from tomorrow so we cant make commits today ... will you work locally then we stage all commits tomorrow to the repo?"

**Result:** Phase 0 (scaffolding, pinned toolchain, tracker, CI) built locally, then published during the event.

### P-09 Dependency check can wait
> "m0.6 is just dependancy check so we can do that part later while we can move to the next phases while locally you have conpletly the m0.6 so we will check on github ci later you work on next phases"

**Result:** milestone M0.6 deferred to a CI check, work continued on later phases.

### P-10 Phases 2 and 3
> "move on to phase 2 and phase 3 then. finish both phases without asking for anything in between"

**Result:** ingestion, parsers and resolvers, then worlds and oracles.

### P-11 Build all remaining phases without inventing results
> "complete all the next phases required non stop without asking for any permissions or requiring me to direct you again and again . pls finish all the phases one after the other and dont hallucinate as well ..."

**Result:** the milestone-by-milestone build, with each test case's real output saved under `evidence/` and recorded by `tools/track.py`.

### P-12 Finish P0, then ask before P1
> "nwo lets move forward building the project build in okk and after completetion of p0 ask me to move forward okk do it proper"

**Result:** P0 completed first; P1 started only after the check-in.

### P-13 Start the remaining P0 items
> "yes start with M0.6 and M12.1"

**Result:** the dependency check (M0.6) and the hand-verification record for the real historical case (M12.1).

### P-14 Choose the P1 items that unblock Gate D
> "what about this what we have to do this or above ... start the three P1 items that unblock Gate D (M4.6 O-bind, M11.3 egress allowlist, M5.3 and M5.4 durable jobs)"

**Result:** the call-site oracle (O-bind), the allowlisting egress proxy, and durable cancellable jobs.

### P-15 Complete P1
> "do the further steps complete the p1 okk" and "run it from where stop"

**Result:** the remaining P1 milestones: API-surface diff (M6.2), usage index and exposure (M6.3), static verdict wording (M6.4), the data-contract oracle (O-contract), the container image and release manifest (M11.x), and the Gate D declaration.

## 4. Questions that checked the design (13 Oct 2026)

### P-16 Where do the answers come from?
> "explain me where is this answer coming like we are not using any llm is it hard coded or rule based response"

**Result:** confirmed and documented that verdict wording comes from a fixed decision table (`verdict-policy/1`), with no model in the decision path. The product works with the AI off.

### P-17 How is the consumer world built?
> "how does it build the concumer world like how does it know that this dependancy was their earlier"

**Result:** explanation of the reference world versus the projected consumer world, taken from lockfiles or from the native resolver at a pinned timestamp, with an exact delta.

### P-18 Pitch script
> "now i need to pitch this stuff ... to the jury for mid hackethon evaluation so please give me in easy language how can i explain it to them give me simple explanation script hwo it is working okk simple language"

**Result:** a plain-language explanation script for the jury (see also `docs/demo_script.md`).

## 5. Interface (13 to 14 Oct 2026)

### P-19 Make the interface match the frontend v2 design
> "but our current frontend does not look like like that frontedn v2 make it like it i thing there is some issue"

**Result:** the interface restored to the v2 look before any further redesign.

### P-20 Workspace redesign brief
Typed in full:
> "act as senior UI/UX designer
> so let me tell you i want i dynamic side bar so when i select some option of it it should close and opens in such a way so that it shouldnt overlap on overview page the overview page should become lesser and like that part should be used by navbar
> as well as the font size for all the pages looks little bit of large reduce them the loading page is really bad keep it subtle easy going nothing creative simple good (just shouldnt look like AI made)
> now there is formatting issue as well in all pages solve that issue properly
> then on overview page we have lot of text but the thing is visual matters so you can add some poffesional pie charts as per the theme
> the design now looks messy i want it proffesional it strictly shouldnt look like AI no emojis nothing be serious
> as well as the header feels a bit lot filled up it looks messy tbh please solve that be very serious with changes think as designer in UI/UX"

**Result:** collapsible sidebar that pushes the content, one smaller type scale, a plain loader, a slimmer header, and outcome and job charts on the Overview page (`frontend/src/app/Workspace.tsx`, `ui/charts.tsx`, `workspace.css`).

### P-21 Inventory graph redesign and dead buttons
Full text of the brief:
> "Redesign the FAULTLINE Inventory Graph to handle large dependency graphs without making the page excessively tall. Keep the graph inside a fixed-height canvas (approximately 60–70vh) with working zoom in/out, drag-to-pan, fit-to-screen, and reset controls. Automatically arrange nodes into logical layers and use the available canvas space efficiently. When the graph is too large to fit, scale it to show the overall structure initially and let users zoom into specific sections. Add a minimap for navigating large graphs and allow selecting a node to focus on its connected dependencies. Keep the node inspector and inventory table outside the graph canvas, with their own independent scrolling. Do not shrink nodes until unreadable or extend the entire page to accommodate every node. Preserve existing functionality and real data. Inspect the current implementation, fix the graph layout properly, and verify all interactions in the browser.
>
> Fix non-responsive buttons: Audit every button on the graph page, especially Reset view and Add relationship. Ensure each performs its intended action, updates the UI correctly, and provides appropriate feedback. If an action is unsupported or unavailable, show a clear explanation instead of leaving a dead button. Check all other graph controls for the same issue.
>
> Make page headings bold across the entire workbench: Apply a consistent, professional heading style to every page, including Overview, New Analysis, Findings, World Matrix, Relationships, Inventory Graph, Evidence, Jobs, Repositories, Capabilities, and Settings. Page titles should use a semibold or bold weight (600), with consistent sizing, spacing, and hierarchy. Keep the existing FAULTLINE typography and visual identity."

**Result:** layered layout, pan, zoom, fit, reset, minimap, node focus, an "Add relationship" panel, and 600-weight page headings (`frontend/src/app/views/Inventory.tsx`, `graph.css`).

## 6. Demo design (14 Oct 2026)

### P-22 Demo repositories that work in front of judges
> "now the thing is that we want to show our final demo for that we want good repos that actually works and we can show judges everything poperly with it so is it our current repos are better for showing the demo are we we need a proper example if yes create it and run it test it and also tell me how to run okk"

**Result:** new fixture libraries and services, `scripts/demo_check.py` for an end-to-end rehearsal on real GitHub repositories, and `docs/DEMO_RUNBOOK.md`.

### P-23 One paste, everything explained
> "i want to ask one thing that like at the time of demo in front of judges we we have only one chance to pasete the repo and see the result so our repost contant all the the things we want to explain"

**Result:** the "showcase" set: one producer and two consumers (one with breaks, one control) that together show a break, a silent divergence, a call-site mismatch, a data-contract change and a no-drift control.

### P-24 Which repository is the producer and which is the consumer
> "give me which is producer repo and consumer repo with full link and what is the repos issue that also mention"

**Result:** the producer, consumer and control repositories with links and the issue each one demonstrates, in the runbook:
Producer `faultline-fixture-acme-showcase`, breaking consumer `faultline-fixture-fulfilment-svc`, control consumer `faultline-fixture-reporting-svc`.

## 7. Oracles shown in the product (14 Oct 2026)

### P-25 Why the test oracle was not planned
> "why we did not o test why it is not planned"

**Result:** explanation of the conditions for O-tests (the library ships tests and a pinned hash test lock).

### P-26 Run the test oracle for real
> "can you do running of o test actually in 30 min"

(The same session also asked to simply mark O-tests as "ran" in the interface. That was not done, because a result must come from a real run; this prompt asked for the real implementation.)
**Result:** O-tests wired into the live analysis: test overlay worlds, 3 + 3 fresh runs, per-test witnesses (`backend/faultline/analysis/live.py`).

### P-27 Why O-bind shows as not planned
> "why is o bind coming not planned please fix it"

**Result:** the capability report and planner state the conditions under which O-bind and O-contract run, and the showcase repository meets them.

### P-28 Analysis takes far too long, and "6 out of 3 fresh passes"
> "when i inputing three repo it is taking way too long" (with the three showcase links)
> "it is taking way too long for two repos too and see the image why is it showing 6 out of 3 and also after inventory it is taking way too long"

**Result:** wheels already in the wheelhouse are used without asking the package index (world fetch 55 s to 2 s), the witness page judges each witness on its own six runs, and a repeated analysis keeps its attribution and fix (`oracles/harness/fetch_wheels.py`, `witnesses/`, `analysis/read.py`).

## 8. Documentation for handover (21 Oct 2026)

### P-29 Technical status document
> "create a current technical document of the project like what is completed, what is build properly is short complete context of the project till now since i want to give context of the project to my ai ... he knows about [docs/FAULTLINE_MASTER.md] but dont know what is completed and what is not"

**Result:** `docs/FAULTLINE_BUILD_STATUS.md`, updated after the test runs finished.

---

## Entries still to add

New entries go here, in order, under the section they belong to (or a new section). Format:

```
### P-NN Short title
> "the prompt, quoted as typed"
**Result:** what changed in the repository.
```
