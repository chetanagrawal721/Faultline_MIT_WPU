

<pasted_content id="0072">
You are a senior software supply-chain security architect, developer-tools researcher, programming-languages engineer, static-analysis expert, dependency-resolution expert, AI/ML researcher, distributed-systems engineer, and national-level hackathon-winning solution strategist.
We are building a solution for HACKTOPIA 2026 — PS07: Cross-Repo Dependency Drift Detector.
Official PS07:
Teams running microservices or large monorepos have no lightweight way to see where a dependency-version mismatch will actually break something before it ships.
The system should ingest multiple real public GitHub repositories/manifests such as `package.json`, `requirements.txt`, and `pom.xml`, build a cross-repo dependency graph, and flag version drift with a real compatibility signal — not merely “these numbers differ.”
The system must work on real public GitHub repositories without requiring those repositories to already be instrumented.
CRITICAL OBJECTIVE
Do NOT design a basic:
manifest parser → dependency graph → version mismatch → red warning
system.
That would be too easy to reproduce and would not be sufficiently differentiated for a serious hackathon.
We want to discover a technically deep, novel, defensible and demonstrable solution that can answer:
“This dependency mismatch exists — but will it ACTUALLY break anything?”
And ideally:
“Show me exactly what will break, why it will break, which code is affected, how severe the break is, and prove it with evidence before the change ships.”
The final system should feel like a dependency compatibility intelligence / pre-merge risk analysis platform, not merely a dependency scanner.
Do NOT blindly accept this direction either. Challenge it and improve it if you find a stronger formulation.
PART 1 — FIRST UNDERSTAND PS07 DEEPLY
Before designing anything, explain:

1. What PS07 actually requires.
2. What problem engineering teams are experiencing.
3. Why simple version comparison is insufficient.
4. Why dependency drift occurs.
5. Why cross-repository dependency relationships are difficult.
6. Why monorepos and microservices create different forms of dependency drift.
7. What happens when two repositories use different versions of the same package.
8. What happens when the dependency difference is harmless.
9. What happens when it causes an actual compatibility failure.
10. What PS07 means by:

“a real compatibility signal — not just these numbers differ.”
Then identify the actual technical problem hidden underneath PS07.
Do not immediately jump to implementation.
PART 2 — QUESTION THE BASIC SOLUTION
Assume another hackathon team builds:

```text
GitHub repos
      ↓
Read package.json / requirements.txt / pom.xml
      ↓
Extract dependencies
      ↓
Compare versions
      ↓
Build graph
      ↓
Red = mismatch

```

Explain:

* Why this is insufficient.
* What false positives it creates.
* What important breaking changes it misses.
* What harmless mismatches it flags.
* What transitive dependency problems it misses.
* What API-level changes it misses.
* What runtime compatibility problems it misses.
* What semantic/version-range issues it misses.
* What lockfile information it misses.
* What actual evidence is needed to determine whether drift matters.

Then redesign the solution.
PART 3 — DEFINE THE CORE QUESTION OUR SYSTEM SHOULD ANSWER
Explore several increasingly advanced formulations:
Level 1 — Drift Detection
“Do these repositories use different versions?”
Level 2 — Compatibility Analysis
“Are those versions potentially incompatible?”
Level 3 — Usage-Aware Analysis
“Does either repository actually use functionality affected by the version difference?”
Level 4 — Impact Analysis
“Which symbols, functions, APIs, services or contracts are affected?”
Level 5 — Execution Verification
“Can we reproduce the compatibility failure in isolated environments?”
Level 6 — Preventive Intelligence
“If Repository A upgrades dependency X, what downstream repositories could break before the change is merged?”
Level 7 — Counterfactual Dependency Analysis
“What would happen if Repository A moved from version X to version Y?”
Determine which level should become the core of our system.
Do not assume the most advanced level is automatically best. Evaluate feasibility, novelty and reliability.
PART 4 — DEEPLY ANALYZE EXISTING ECOSYSTEM
Before claiming novelty, analyze the conceptual capabilities of existing tools and approaches such as:

* Dependabot
* Renovate
* GitHub dependency graph
* npm tooling
* Maven dependency tools
* pip dependency tooling
* Poetry
* uv
* pnpm
* npm
* Yarn
* Maven
* Gradle
* OSV
* deps.dev
* Snyk
* Semgrep
* CodeQL
* static analyzers
* API compatibility checkers
* package registries
* SBOM tools
* lockfile analyzers

You do not need to reproduce their documentation.
Instead determine:

1. What they already solve.
2. What they do not solve.
3. Where PS07's white space exists.
4. Which ideas we absolutely should NOT claim as novel.
5. Where our technical contribution could genuinely be differentiated.

Be careful:
Do NOT claim:
“No existing tool does dependency analysis.”
That would be false.
PART 5 — IDENTIFY THE TRUE WHITE SPACE
Find the strongest intersection between:

```text
Cross-Repo
+
Dependency Graph
+
Version Resolution
+
API/ABI Analysis
+
Actual Code Usage
+
Compatibility Reasoning
+
Execution Evidence
+
Pre-Merge Prediction

```

Determine which combination provides the strongest defensible innovation.
Consider a concept such as:
“Execution-Verified Cross-Repo Compatibility Intelligence”
But do NOT blindly accept this name or concept.
Improve it if necessary.
The goal is to move from:
“Version mismatch detected”
to:
“Version mismatch detected → affected API identified → actual usage found → compatibility risk reasoned → failure reproduced → evidence presented → remediation proposed.”
PART 6 — BUILD AN EXHAUSTIVE EDGE-CASE MATRIX
This is extremely important.
Think like a programming-language researcher, senior backend engineer, and skeptical judge.
Analyze every major dependency edge case.
A. VERSION DIFFERENCES
Consider:

* exact versions
* patch differences
* minor differences
* major differences
* prerelease versions
* beta versions
* alpha versions
* release candidates
* pinned versions
* caret ranges
* tilde ranges
* wildcard ranges
* minimum versions
* maximum versions
* incompatible ranges
* overlapping ranges
* disjoint ranges
* malformed versions
* unusual version formats
* missing versions

Determine what should happen in each case.
PART 7 — SEMANTIC VERSIONING EDGE CASES
Do NOT assume:

```text
1.2.3 → 1.2.4 = safe

```

or:

```text
1.x → 2.x = breaking

```

automatically.
Analyze:

* semantic-versioning violations
* libraries that introduce breaking changes in minor releases
* undocumented breaking changes
* deprecated APIs
* changed defaults
* behavioral changes without signature changes
* renamed symbols
* removed symbols
* changed function signatures
* changed return types
* changed exceptions
* changed configuration semantics

Determine how our system should detect these.
PART 8 — TRANSITIVE DEPENDENCIES
This is critical.
Consider:

```text
Repo A
 └── libX@2
      └── libY@5

Repo B
 └── libX@2
      └── libY@7

```

And:

```text
Repo A → X → Y → Z@1
Repo B → X → Y → Z@2

```

Analyze:

* transitive drift
* dependency chains
* diamond dependencies
* conflicting constraints
* lockfile-resolved versions
* direct vs transitive dependencies
* vulnerable transitive dependencies
* shared internal libraries
* transitive breaking changes

Determine how to calculate the shortest causal dependency path between repositories.
PART 9 — CROSS-REPO CONTRACTS
This should be deeply explored.
Consider:

```text
Service A
     ↓
API / Message / Schema
     ↓
Service B

```

Dependencies may affect:

* REST APIs
* GraphQL
* protobuf
* gRPC
* JSON schemas
* Pydantic models
* Java DTOs
* TypeScript types
* serialization
* deserialization
* database clients
* shared libraries
* event schemas

Determine:
How can dependency drift create an actual cross-repo contract failure?
Design mechanisms for identifying these relationships automatically.
PART 10 — CODE-USAGE ANALYSIS
This is potentially one of our strongest differentiators.
Do NOT stop at:
Repo A uses package X@1.5.
Determine:
Which exact APIs from package X does Repo A use?
Analyze:

* imports
* aliases
* `from x import y`
* wildcard imports
* method calls
* function calls
* classes
* attributes
* decorators
* type annotations
* constructors
* chained calls
* dynamic imports
* reflection
* generated code
* monkey patching
* conditional imports

For every package upgrade, determine:

```text
Affected package
      ↓
Changed API
      ↓
Repository usage
      ↓
Affected file
      ↓
Affected symbol
      ↓
Potential breakage

```

Discuss how this could be implemented using AST/static analysis.
PART 11 — API DIFFERENCE ANALYSIS
Explore how to compare two package versions.
For Python:

* public functions
* classes
* signatures
* parameters
* return types
* attributes
* exceptions
* deprecated APIs

For Java:

* classes
* methods
* signatures
* visibility
* inheritance
* binary compatibility

For JavaScript/TypeScript:

* exports
* functions
* types
* interfaces
* declarations
* package exports

Determine which comparisons can be automated reliably.
Also identify what cannot be reliably inferred statically.
PART 12 — EXECUTION-VERIFIED COMPATIBILITY
This should receive extremely deep analysis.
Suppose:

```text
Repo A uses libX@1.8
Repo B uses libX@2.0

```

Static analysis predicts risk.
Can we actually test it?
Design an isolated environment:

```text
Environment A
libX@1.8
Repo A code

Environment B
libX@2.0
Repo B code

```

Then determine whether we can generate a compatibility test.
Consider:

* API calls
* serialization
* deserialization
* schemas
* messages
* function calls
* shared data models
* HTTP contracts

The system should ideally produce evidence such as:

```text
Potential incompatibility detected.

Affected symbol:
Foo.parse()

Repo A expects:
Foo.parse(payload)

Repo B / lib version provides:
Foo.parse(payload, strict=True)

Execution result:
TypeError: missing required argument 'strict'

Confidence:
Execution-verified

```

But critically evaluate:

* Can this be generalized?
* When does execution verification fail?
* What if dependencies require external services?
* What if setup is impossible?
* What if tests are missing?
* What if the failure is nondeterministic?
* What if the package behavior depends on OS/platform?
* What if the package requires secrets?
* What if the package requires a database?

Design graceful fallback levels.
PART 13 — EVIDENCE HIERARCHY
Create an evidence hierarchy such as:
Level 0
Version mismatch only.
Level 1
Constraint conflict.
Level 2
API surface difference.
Level 3
Affected symbol actually used.
Level 4
Static compatibility violation.
Level 5
Synthetic compatibility test failure.
Level 6
Real test failure.
Determine whether this hierarchy makes sense and improve it.
The system should clearly communicate:
“Potential”
versus
“Likely”
versus
“Confirmed”
rather than pretending every prediction is certain.
PART 14 — FALSE POSITIVE / FALSE NEGATIVE ANALYSIS
Generate difficult examples.
False Positive
Versions differ but everything works.
False Negative
Versions appear compatible but behavior changed.
Hidden Breaking Change
API signature remains the same but behavior changes.
Undocumented Breaking Change
Release notes don't mention the break.
Runtime-only Failure
Static analysis cannot detect it.
Environment-specific Failure
Works on Linux but fails on Windows.
Optional Dependency
Only one execution path uses the affected dependency.
Explain how the system should communicate uncertainty.
PART 15 — MULTI-LANGUAGE / MULTI-ECOSYSTEM DESIGN
PS07 explicitly mentions:

* package.json
* requirements.txt
* pom.xml

Design the architecture so that it can eventually support:

```text
Python
JavaScript / TypeScript
Java

```

But do NOT create an unnecessarily huge architecture.
Design:
Common abstraction layer

```text
Repository
Dependency
Version
Constraint
Package
Symbol
API
Usage
Compatibility
Evidence

```

Then ecosystem-specific adapters:

```text
Python Adapter
npm Adapter
Maven Adapter

```

Explain exactly what is shared and what is ecosystem-specific.
PART 16 — REAL PUBLIC GITHUB REPOSITORY WORKFLOW
The solution must work on real public GitHub repositories without requiring instrumentation.
Design:

```text
GitHub URL
   ↓
Repository discovery
   ↓
Manifest discovery
   ↓
Lockfile discovery
   ↓
Dependency extraction
   ↓
Dependency resolution
   ↓
Code analysis
   ↓
Cross-repo graph
   ↓
Compatibility analysis
   ↓
Evidence generation

```

Handle:

* monorepos
* multiple manifests
* nested projects
* multiple languages
* missing lockfiles
* malformed manifests
* private dependencies
* Git submodules
* generated code
* vendored libraries
* huge repositories
* repositories with no tests
* repositories with build failures

PART 17 — MONOREPO VS MULTI-REPO
Analyze separately:
Monorepo

```text
service-a/
service-b/
shared-lib/

```

versus:
Multi-repo

```text
repo-a
repo-b
repo-c

```

Determine:

* dependency discovery
* shared libraries
* internal packages
* version synchronization
* release workflows
* compatibility analysis
* graph construction

PART 18 — TEMPORAL / CHANGE ANALYSIS
This can become another strong innovation.
Don't just analyze the current state.
Analyze:

```text
Before upgrade
      ↓
Proposed dependency change
      ↓
Potential impact
      ↓
Affected repositories
      ↓
Affected symbols
      ↓
Compatibility result

```

Ask:
“What happens if this PR changes X@1.4 → X@2.0?”
This turns the system from a passive scanner into a dependency change impact simulator.
Explore whether this should be a hero feature.
PART 19 — COUNTERFACTUAL DEPENDENCY ANALYSIS
Explore:
“What if Repository A upgraded package X?”
versus:
“What if Repository B stayed on the old version?”
versus:
“What if both repositories aligned?”
The system should potentially compare:
Current world

```text
A → X@1
B → X@2

```

Proposed world

```text
A → X@2
B → X@2

```

Alternative world

```text
A → X@1
B → X@1

```

Then compare compatibility risk.
Determine whether this provides genuine technical value or is just a fancy UI.
PART 20 — BREAKING-CHANGE INTELLIGENCE
Explore combining:

* package API diff
* release notes
* changelog
* migration guide
* source-code changes
* actual repository usage

For example:

```text
Version 1 → Version 2

Changelog:
“Foo.parse() changed behavior.”

API diff:
Signature changed.

Repo usage:
Foo.parse() used in 17 locations.

Execution:
3 compatibility tests fail.

```

The system should produce:
Confirmed breaking impact
rather than merely:
“Major version changed.”
Also investigate:
Undocumented breaking changes
Where:

```text
API diff = breaking
Changelog = silent

```

Determine whether this could become a strong research/novelty component.
PART 21 — GRAPH DESIGN
Design the graph carefully.
Possible nodes:

```text
Repository
Service
Package
Version
Manifest
Lockfile
Symbol
Function
Class
API
Commit
Pull Request
Contract
Schema
Test
Evidence

```

Possible edges:

```text
DEPENDS_ON
USES
EXPOSES
CALLS
IMPORTS
PROVIDES
CONSUMES
CONFLICTS_WITH
BREAKS
AFFECTS
VERIFIED_BY
INTRODUCED_BY

```

Determine which edges are essential.
Do NOT create a giant graph just because graph databases sound impressive.
Explain what queries the graph enables.
PART 22 — RISK / COMPATIBILITY SCORE
Do NOT simply produce:
“Risk = 94%.”
Design an evidence-backed compatibility representation.
For example:

```text
Version Drift
API Surface Change
Actual Usage
Transitive Impact
Contract Exposure
Execution Evidence
Test Evidence
Changelog Evidence
Confidence

```

Determine how these should combine.
Most importantly distinguish:
Version Difference
from
Potential Compatibility Risk
from
Usage-Affected Risk
from
Execution-Verified Breakage
These should not be treated as the same thing.
PART 23 — REMEDIATION ENGINE
Once the system identifies a problem, what should it recommend?
Examples:

```text
Upgrade Repo A
Downgrade Repo B
Align both versions
Pin a compatible version
Apply migration
Update affected API calls
Upgrade transitive dependency
Introduce compatibility layer

```

Determine how recommendations can be generated safely.
Avoid blindly allowing an LLM to modify dependency files.
Explore:

* constraint solving
* minimal-change remediation
* compatibility-preserving upgrade path
* shortest remediation path
* affected repository prioritization

PART 24 — SECURITY / SUPPLY-CHAIN THREAT MODEL
Attack our own system.
Consider:

* malicious package
* compromised package
* malicious repository
* poisoned changelog
* malicious build scripts
* dependency confusion
* typosquatting
* arbitrary code execution
* malicious postinstall scripts
* malicious tests
* untrusted GitHub repositories
* sandbox escape
* malicious generated code

If we execute code for verification, this becomes especially important.
Design a secure execution architecture.
Explain:

* sandboxing
* network isolation
* CPU limits
* memory limits
* filesystem isolation
* timeout
* non-root execution
* ephemeral environments

PART 25 — DATA / BENCHMARK DESIGN
We need to prove the system works.
Design a benchmark containing real-world dependency upgrades such as:

* breaking major upgrades
* subtle minor-version breaks
* deprecated APIs
* renamed APIs
* changed signatures
* transitive conflicts
* harmless version differences

Do NOT invent results.
Design how we could measure:

* drift detection precision
* compatibility prediction precision
* recall
* false-positive rate
* affected-symbol precision
* breaking-change detection
* execution verification success rate
* remediation success rate
* analysis latency
* repository coverage

PART 26 — ABLATION STUDY
Compare:
A — Version comparison only
B — Dependency graph
C — API diff
D — API diff + actual usage
E — + transitive dependency analysis
F — + execution verification
G — + change-impact prediction
Determine what each layer contributes.
The final system should have an evidence-based reason for every major component.
PART 27 — GROUND-BREAKING INNOVATION & DIFFERENTIATION
Do NOT stop at designing a technically complete PS07 system.
We need 1–2 HERO INNOVATIONS that become the centerpiece of the hackathon solution.
Explore ideas such as:
1. Execution-Verified Dependency Drift
Instead of saying:
“Version mismatch detected.”
Our system attempts to prove:
“This mismatch causes an actual compatibility failure.”
Show the traceback/evidence.
2. Usage-Aware API Exposure
Instead of:
“Package X removed API Y.”
Show:
“Repository B uses API Y at 14 call sites, and 6 are exposed to the upgrade.”
3. Cross-Repo Contract Breakage Detection
Detect when dependency changes can break:

* APIs
* schemas
* messages
* serialization
* shared models

4. Counterfactual Dependency Simulator
“What happens if Repo A upgrades X from 1.9 → 2.0?”
Simulate the dependency world before merging.
5. Undocumented Breaking Change Detector
Compare:

```text
Release notes
+
API diff
+
Actual code usage
+
Execution

```

to discover breaking changes that documentation does not clearly identify.
6. Minimal Remediation Planner
Instead of saying:
“Fix dependency mismatch.”
Find the smallest set of version changes needed to restore compatibility.
7. Dependency Blast-Radius Engine
Given:
“Package X changes.”
Show:

```text
X
↓
Y
↓
Repo A
↓
Service A
↓
Contract
↓
Repo B

```

and identify the actual blast radius.
For EACH proposed innovation:

1. Explain the idea simply.
2. Explain the technical mechanism.
3. Explain why ordinary dependency scanners do not already provide the same evidence.
4. Identify existing tools that partially overlap.
5. Identify what is genuinely novel in OUR combination.
6. Identify what is merely engineering integration.
7. Explain implementation difficulty.
8. Explain data requirements.
9. Explain demo potential.
10. Explain replication risk.
11. Explain research potential.
12. Explain potential weaknesses.
13. Give a one-line judge pitch.

Then select the strongest 1–2 innovations.
Do NOT claim:
“No existing product does this.”
Instead say precisely:
“Existing tools provide X, while our proposed contribution combines X + Y + Z to produce evidence of actual cross-repo compatibility impact.”
PART 28 — “CAN ANOTHER TEAM COPY THIS?” TEST
For every proposed hero innovation ask:
If another strong hackathon team sees our demo, can they reproduce 70–80% of it in 1–2 days?
If yes:

* reject it as the primary innovation, OR
* combine it with something more defensible.

Identify what makes our system difficult to replicate.
Examples:

* deep AST analysis
* cross-ecosystem abstraction
* dependency resolution
* API diff engine
* symbol-level usage mapping
* execution sandbox
* synthetic compatibility testing
* benchmark
* evidence model
* remediation optimization

PART 29 — HACKATHON SCOPE CONTROL
Assume we can prepare before the competition, but the final system must remain realistically buildable and demonstrable.
Divide the final system into:
MUST BUILD
Only components necessary to demonstrate the core innovation.
SHOULD BUILD
Components that materially improve judging impact.
NICE TO HAVE
Components that add polish.
DO NOT BUILD
Technologies/features that consume time without increasing differentiation.
Be ruthless.
Do not recommend:

* blockchain without a real need
* Kafka without a real need
* microservices everywhere
* GNNs just because graphs exist
* LLM agents just because AI is fashionable
* Kubernetes without deployment justification

PART 30 — COMPLETE END-TO-END ARCHITECTURE
After all analysis, design the final system.
Provide:

1. High-level architecture
2. Frontend
3. Backend
4. GitHub ingestion
5. Manifest parser
6. Lockfile parser
7. Dependency resolver
8. Registry integration
9. Dependency graph
10. AST/code analysis
11. API diff engine
12. Usage analysis
13. Compatibility engine
14. Execution verification sandbox
15. Evidence engine
16. Risk engine
17. Change-impact simulator
18. Remediation engine
19. Database/storage
20. Caching
21. Security architecture
22. Visualization layer

Show the complete data flow using ASCII diagrams.
PART 31 — END-TO-END EXAMPLE
Create ONE detailed realistic example.
For example:

```text
Repo A
Python service
pydantic 1.x

Repo B
Python service
pydantic 2.x

Repo A exposes model:
CustomerRequest

Repo B consumes:
CustomerRequest

```

Then show:

```text
GitHub ingestion
↓
Dependency extraction
↓
Version resolution
↓
Cross-repo graph
↓
API diff
↓
Actual usage discovery
↓
Contract identification
↓
Compatibility analysis
↓
Execution test
↓
Failure/evidence
↓
Blast radius
↓
Risk
↓
Remediation

```

Show exactly what the investigator/developer sees.
Then create at least 5 variations:
Variation A
Versions differ but no affected API is used.
Variation B
API changed and repository uses it.
Variation C
Versions differ but behavior remains compatible.
Variation D
Transitive dependency causes the break.
Variation E
Static analysis predicts risk but execution succeeds.
For every case explain the system's final conclusion.
PART 32 — FAILURE & UNCERTAINTY HANDLING
The system must be able to say:
UNKNOWN
or:
INSUFFICIENT EVIDENCE
or:
POTENTIAL BREAK
instead of inventing certainty.
Design states such as:

```text
NO DRIFT
DRIFT — LOW IMPACT
POTENTIAL INCOMPATIBILITY
USAGE-AFFECTED
HIGH COMPATIBILITY RISK
EXECUTION-VERIFIED BREAK
INCONCLUSIVE

```

Improve these categories if necessary.
Explain exactly what evidence moves a case from one state to another.
PART 33 — INVESTIGATOR / DEVELOPER UX
Design the complete UI.
The main dashboard should answer:
What changed?

```text
Repo A
X 1.9 → 2.0

```

What is affected?

```text
3 repositories
11 files
17 symbols

```

Why?

```text
API Foo.parse() removed

```

Is it actually used?

```text
YES — 17 call sites

```

Is it confirmed?

```text
EXECUTION VERIFIED

```

What breaks?

```text
Repo B
/api/customer
deserialization failure

```

What should we do?

```text
Upgrade Repo B migration path
OR
pin X@1.9

```

Design the entire UX around evidence, not a generic graph dashboard.
PART 34 — 30-SECOND JUDGE EXPLANATION
After the architecture is complete, produce a simple 30-second explanation.
It must answer:
What problem?
What does our system do?
Why is it different?
Why does it matter?
A judge who knows nothing about dependency engineering should understand it.
Avoid technical jargon unless necessary.
PART 35 — 3–5 MINUTE HACKATHON DEMO
Design the ideal live demo.
The demo should NOT be:
“Here is our dashboard.”
Instead create a dramatic technical story.
For example:

1. Load two real public GitHub repositories.
2. System discovers dependency drift.
3. Show that version mismatch alone is not enough.
4. Identify affected API.
5. Locate actual usage.
6. Build dependency/usage path.
7. Run compatibility verification.
8. Produce actual failure/evidence.
9. Show blast radius.
10. Show remediation.
11. Change the version.
12. Re-run.
13. Show the compatibility issue disappear.

Explain exactly what should be visible on screen at every stage.
The final demo should make the judge understand the value without requiring a long technical explanation.
PART 36 — RESEARCH CONTRIBUTION
Determine whether this project can become more than a hackathon prototype.
Identify potential research contributions such as:

* usage-aware dependency compatibility prediction
* cross-repo compatibility graphs
* execution-verified dependency analysis
* undocumented breaking-change detection
* dependency blast-radius estimation
* minimal dependency remediation
* compatibility evidence hierarchies

For each, explain:

* research question
* hypothesis
* methodology
* baseline
* evaluation
* expected contribution

Do not claim novelty without evidence.
PART 37 — FINAL NOVELTY AUDIT
Create three categories:
NOT NOVEL
Things we should NOT pitch as innovation.
INNOVATIVE ENGINEERING
Strong implementation combinations but not necessarily research novelty.
POTENTIALLY DEFENSIBLE CONTRIBUTION
The strongest technical/research contribution.
This distinction is extremely important.
PART 38 — FINAL SYSTEM DECISION
After all the analysis, provide:
1. Final one-paragraph concept
Exactly what we are building.
2. Hero innovation
The ONE thing judges should remember.
3. Supporting innovation
The second strongest differentiator.
4. Existing tools / prior art
What already exists and how our system differs.
5. Complete feature list
MUST / SHOULD / NICE TO HAVE / DO NOT BUILD.
6. Complete architecture
All major components and data flow.
7. Data model
Entities + relationships.
8. Edge-case strategy
How major failure cases are handled.
9. Detection/compatibility logic
Rules + static analysis + graph + API analysis + execution evidence.
10. Evaluation strategy
Datasets + benchmarks + metrics + ablation.
11. Security model
Especially execution sandboxing.
12. 30-second pitch
Simple judge-friendly explanation.
13. 3–5 minute demo
Exact demo sequence.
14. Novelty defense
Exactly what we can claim and what we cannot claim.
15. First implementation roadmap
Give the first 10 development milestones, in dependency order.
FINAL RULES

1. Do NOT blindly agree with our initial concept.
2. Challenge every assumption.
3. Think like a senior software engineer.
4. Think like a programming-languages researcher.
5. Think like a supply-chain security expert.
6. Think like a hackathon judge.
7. Think like an attacker.
8. Think about false positives.
9. Think about false negatives.
10. Think about transitive dependencies.
11. Think about lockfiles.
12. Think about monorepos.
13. Think about multi-repo systems.
14. Think about multiple languages.
15. Think about API compatibility.
16. Think about behavioral compatibility.
17. Think about runtime failures.
18. Think about missing tests.
19. Think about malicious repositories.
20. Think about sandbox security.
21. Never fabricate evaluation results.
22. Never claim a capability is novel merely because we implemented it.
23. Distinguish clearly between:

* existing capability
* engineering integration
* potentially novel technical contribution

24. Do not add technology merely because it sounds advanced.
25. Prefer evidence over AI-generated explanations.
26. Prefer deterministic analysis where possible.
27. Use LLMs only where they add genuine value.
28. Make the system capable of saying “inconclusive.”
29. Keep the architecture realistic.
30. Optimize for a memorable hackathon demo.
31. Optimize for technical depth AND explainability.
32. The system must work on real public GitHub repositories.
33. The system must not require instrumentation of those repositories.
34. Most importantly:

Do not stop at detecting dependency drift. Find a technically defensible way to determine whether the drift actually matters, prove the impact with evidence whenever possible, and explain exactly what should be changed before the problem reaches production.
After completing the entire analysis, challenge your own final design once more and answer:
“If you were a national hackathon judge trying to reject this project, what would be your strongest criticism — and how should we redesign the system to eliminate that weakness?”
</pasted_content id="0072">
