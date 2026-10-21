

<pasted_content id="0072">
# MASTER PROMPT — CREATE THE COMPLETE FAULTLINE PROJECT DOCUMENT + IMPLEMENTATION BLUEPRINT

You are the **lead software architect, security engineer, developer, DevOps engineer, and technical researcher** responsible for turning the following project discussion into a **complete implementation-ready engineering document**.

The project is:

# FAULTLINE

### Cross-Repo Dependency Drift Detector

**HACKTOPIA 2026 — PS07**

I have already discussed this project extensively with another AI, including the problem statement, architecture, red-team analysis, technical decisions, security concerns, algorithms, novelty, demo strategy, and implementation plan.

I will provide you with those materials.

Your task is NOT to give me another short summary.

Your task is to create a **single, extremely detailed, technically precise MASTER PROJECT DOCUMENT** that explains:

> **What Faultline is, exactly why we are building it, exactly how the final system works, exactly how every component will be implemented, how the components communicate, what data flows through the system, what algorithms are used, how failures are verified, how security is handled, how the UI works, how we test it, and how we will actually build the complete project from zero to final hackathon demo.**

This document will become the **single source of truth for the entire Faultline implementation**.

---

# 1. IMPORTANT INSTRUCTIONS

## Do NOT redesign the project casually

Use the previous discussion and red-team analysis as the primary source of truth.

Do not silently replace our architecture with a generic dependency-management system.

Do not simplify away technically important mechanisms.

Do not introduce technologies just because they are popular.

If you believe something should be changed, clearly mark it as:

**PROPOSED CHANGE**

and explain:

* existing decision
* problem with it
* proposed replacement
* reason
* implementation impact
* whether the change is necessary for MVP

Do not silently modify decisions.

---

# 2. CORE PROJECT IDEA

The central Faultline idea is:

> **“Your shared code is tested in one dependency world and runs in many. Faultline tests it in all of them.”**

The core engineering contribution should be described carefully as:

> Faultline derives dependency worlds from repositories that actually consume a shared artifact, checks that artifact across those consumer-derived worlds, and backs observed compatibility problems with reproducible witnesses narrowed to the package change responsible for the failure.

The project should emphasize:

# “Witnesses, not warnings.”

Do NOT claim:

* “Faultline proves compatibility.”
* “Faultline detects every breaking change.”
* “Faultline guarantees compatibility.”
* “Nobody else does this.”
* “AI found the bug.”

Use precise terminology:

* BREAK WITNESSED
* SILENT DIVERGENCE WITNESSED
* NO DIVERGENCE OBSERVED
* EXPOSED
* POTENTIAL
* NOT EXPOSED
* INCONCLUSIVE
* HYGIENE

Explain the epistemic meaning of each verdict.

---

# 3. START FROM THE PROBLEM STATEMENT

Begin the document with the original PS07 problem.

Explain:

1. What the problem asks us to build.
2. What dependency drift means.
3. Why checking versions alone is insufficient.
4. Why independently maintained repositories create compatibility problems.
5. Why package-level dependency graphs are insufficient.
6. Why actual consumer environments matter.
7. Why static API comparison alone is insufficient.
8. Why testing only the producer's environment is insufficient.
9. Why merely generating warnings is insufficient.

Then clearly convert the problem statement into:

### Functional requirements

### Non-functional requirements

### Security requirements

### Evidence/reproducibility requirements

### Hackathon/demo requirements

---

# 4. EXPLAIN THE FINAL FAULTLINE CONCEPT

Explain Faultline from first principles.

Use this mental model:

A shared artifact is created by one repository.

Different consumer repositories resolve different dependency worlds.

The same artifact may therefore execute against different:

* package versions
* transitive dependencies
* runtimes
* OS assumptions
* serialization environments
* configuration environments

Faultline identifies those worlds and verifies the shared artifact against them.

Explain this carefully with a concrete example.

For example:

```text
acme-models
     |
     | shared artifact
     |
     +--------> orders-service
     |
     +--------> billing-service
     |
     +--------> notify-service
```

Then show:

```text
Producer World
    pydantic 1.x
    flask 2.x
    werkzeug 2.x

Consumer World A
    pydantic 1.x
    flask 2.x
    werkzeug 2.x

Consumer World B
    pydantic 2.x
    flask 3.x
    werkzeug 3.x
```

Explain how the same artifact is tested in each world.

---

# 5. EXPLAIN WHY “PARSE → COMPARE → WARN” IS NOT ENOUGH

Create a dedicated section explaining the failure of simplistic implementations.

Discuss:

* version comparison
* semver checking
* dependency graph comparison
* API diff
* changelog parsing
* static usage analysis
* LLM-only approaches

Explain why these approaches can identify candidates but cannot establish an observed runtime incompatibility.

Then introduce the final Faultline pipeline:

```text
INGEST
  ↓
RESOLVE
  ↓
RELATE
  ↓
BUILD CONSUMER WORLDS
  ↓
DIFF
  ↓
EXPOSURE ANALYSIS
  ↓
VERIFICATION
  ↓
WITNESS
  ↓
ATTRIBUTION
  ↓
VERDICT
  ↓
REMEDIATION
```

Explain every stage.

---

# 6. DEFINE “DEPENDENCY WORLD”

This is one of the most important concepts.

Define:

```text
ResolvedWorld
```

Explain that a world includes:

* repository SHA
* package versions
* transitive dependencies
* runtime version
* OS/base image
* architecture
* environment profile
* locale
* timezone
* relevant configuration
* lockfile
* resolver metadata
* image digest where applicable

Explain which dimensions are treated as package deltas and which are environment dimensions.

Explicitly explain:

* Python version
* Node version
* Java version
* OS
* CPU architecture
* locale
* timezone
* environment variables
* feature flags
* pseudo-package/environment differences

Also explain what is intentionally out of scope.

---

# 7. CHANNEL TAXONOMY

Document the three major relationship channels.

## C1 — Co-residence

Explain cases where code from repository X executes inside the dependency world of repository Y.

Include:

* shared libraries
* plugins
* dynamic loading
* generated code
* build artifacts
* container artifacts
* native ABI/JNI/FFI
* dependency injection
* reflection

## C2 — Data crossing

Explain:

```text
Producer
   ↓
serialized bytes/data
   ↓
Consumer
```

Include:

* HTTP
* gRPC
* GraphQL
* queues
* event buses
* database rows
* files
* caches
* protobuf
* pickle/joblib where safely generated
* model artifacts
* configuration

## C3 — Convergence

Explain version-alignment/counterfactual scenarios.

Clearly distinguish observed relationships from hypothetical what-if relationships.

---

# 8. CROSS-REPO RELATIONSHIP MODEL

Document:

```text
L0
L1
L2
L3
L3'
L4
L5
```

Explain exactly what each level means.

Most importantly:

> Findings require L2+ relationships.

Explain:

* L0 = same package, different versions
* L1 = same package role heuristic
* L2 = shared internal artifact
* L3 = shared schema/generated code
* L3' = suspected model twin
* L4 = producer/consumer data relationship
* L5 = explicitly declared/user-provided relationship

Explain which relationships automatically produce findings.

Explain which relationships only appear in the “suspected relationships” tray.

Explain why weak heuristics must not directly produce high-confidence findings.

---

# 9. RELATIONSHIP DISCOVERY

Design the complete relationship-discovery engine.

Explain:

### High confidence

* published package → dependency
* path dependency
* git dependency
* workspace dependency
* identical schema
* generated code/runtime relationship

### Medium confidence

* Docker co-installation
* producer/consumer topology
* same-name schema
* artifact references

### Low confidence

* naming similarity
* suspected model twins
* indirect topology inference

Explain the evidence chain shown to the user.

For every relationship, answer:

> “Why does Faultline believe these two repositories are related?”

---

# 10. SUPPORTED ECOSYSTEMS

The MVP must support:

### Python

### npm / Node.js

### Maven / Java

But be honest about depth.

Python should have the deepest verification.

npm and Maven should initially provide shallower but real support.

Explain:

## Python

* requirements.txt
* pyproject.toml
* uv
* lockfiles
* pip-style resolution
* VCS dependencies
* sdists
* wheels
* path dependencies
* workspace behavior

## npm

* package.json
* package-lock
* npm/pnpm/Yarn
* workspaces
* peer dependencies
* optional dependencies
* overrides
* ESM/CJS
* multiple package copies
* singleton packages

## Maven

* pom.xml
* dependencyManagement
* BOM
* exclusions
* properties
* parents
* profiles
* multi-module projects
* SNAPSHOT handling

Explain which cases become:

```text
SUPPORTED
EXPERIMENTAL
INCONCLUSIVE
OUT OF SCOPE
```

---

# 11. REPOSITORY INGESTION

Design the complete ingestion subsystem.

Input:

```text
GitHub repository URL
```

Output:

```text
Project
Repository
Pinned SHA
Manifest inventory
Source snapshot
Dependency metadata
```

Explain:

* URL validation
* cloning
* SHA pinning
* branch/tag resolution
* fork handling
* submodules
* symlinks
* Git LFS
* huge files
* generated files
* notebooks
* ignored files
* malicious repositories

Never rely on mutable branch heads for evidence.

---

# 12. RESOLUTION ENGINE

Do NOT reinvent package-manager resolution semantics.

Use native ecosystem resolvers/lockfiles wherever possible.

Define:

```text
ResolvedWorld
```

and:

```text
visible(world, importer)
```

Explain exactly how resolution works.

For Python explain:

* lockfile reuse
* uv
* no-build mode
* VCS dependency restrictions
* sdist restrictions
* build isolation
* resolution sandbox

For npm explain:

* lockfile
* node_modules resolution
* peer dependencies
* workspace
* multiple copies
* overrides

For Maven explain:

* Maven model builder
* dependency resolver
* BOM
* parents
* exclusions
* dependencyManagement
* profiles

---

# 13. SECURITY OF DEPENDENCY RESOLUTION

This must be a major section.

Explain the important discovery:

> Dependency resolution itself can execute code.

Examples:

* Python sdist build
* git dependency build backend
* npm lifecycle scripts
* Maven plugins

Therefore explain how Faultline prevents resolution from becoming a remote-code-execution vulnerability.

Define:

```text
CONTROL PLANE
FETCH ZONE
EXECUTION ZONE
```

Explain:

* sandbox
* network isolation
* read-only filesystem
* non-root
* seccomp
* no-new-privileges
* dropped capabilities
* CPU limit
* memory limit
* disk limit
* process limit
* timeout
* ephemeral execution
* no Docker socket
* no host mounts
* no credentials
* disposable VM
* gVisor/runsc where available

Clearly explain the difference between:

```text
Docker isolation
```

and:

```text
gVisor / Firecracker / disposable VM
```

and what we will actually use in the hackathon.

---

# 14. CONSUMER-DERIVED WORLD MATRIX

This is the HERO ENGINE.

Explain exactly how Faultline constructs the matrix.

Example:

```text
                    Producer
                       |
       +---------------+---------------+
       |               |               |
   Orders World   Billing World   Notify World
       |               |               |
   package set      package set      package set
```

For every consumer:

1. resolve its dependency world
2. identify the shared artifact
3. inject/use the producer artifact
4. preserve consumer dependency environment
5. run verification
6. compare against reference world

Explain why this is different from:

> “The library author tested these three versions.”

Faultline asks:

> “What worlds are your actual consumers using?”

---

# 15. API SURFACE EXTRACTION

Explain how we extract public APIs.

For Python discuss:

* griffe
* module discovery
* functions
* classes
* methods
* signatures
* defaults
* annotations
* enums
* properties
* exports

For npm discuss appropriate static mechanisms.

For Maven discuss:

* public classes
* methods
* signatures
* binary compatibility tooling where feasible

Define an:

```text
ApiDelta
```

Explain classifications:

* removed symbol
* changed signature
* changed parameter
* changed return type
* changed default
* enum removal
* visibility change
* changed inheritance
* changed schema

---

# 16. STATIC USAGE ANALYSIS

Explain exactly how Faultline determines whether a consumer actually uses a changed API.

Cover:

* direct imports
* aliases
* re-exports
* wildcard imports
* **all**
* local type propagation
* pyright
* literal getattr
* dynamic getattr
* importlib
* monkeypatching
* decorators
* metaclasses
* exec
* code generation
* dependency injection
* reflection
* framework string paths
* notebooks
* generated code
* type-only imports
* optional imports
* entry points

Clearly classify:

```text
RESOLVED
UNRESOLVED
LOW CONFIDENCE
DYNAMIC
```

---

# 17. EXPOSURE AND COVERAGE

Define:

```text
Exposure
```

and:

```text
Exposure Coverage
```

Use:

```text
resolved references /
all references to divergent packages
```

Explain why:

```text
NOT_EXPOSED
```

cannot be claimed unless coverage is sufficient.

Every NOT_EXPOSED result must display coverage.

---

# 18. TRANSITIVE ANALYSIS

Explain how Faultline propagates impact.

Only analyze direct importers initially.

If:

```text
A → B → C
```

and B fails, explain how impact propagates toward A.

Explain:

* re-export depth
* max depth
* size limits
* module limits
* time budgets
* caching

Define:

```text
ImportIndex[(package, version, depth)]
```

---

# 19. VERIFICATION ENGINE

This is the heart of Faultline.

Explain every oracle.

## O-import

Import the shared artifact under the target dependency world.

## O-tests

Run the artifact's own tests.

## O-bind

Exercise known API calls.

## O-contract

Replay structured data contracts.

## Differential typecheck

Compare type-checking results.

Explain which are MVP, SHOULD, and NICE.

---

# 20. REPLAY MODEL

Define the witness key:

```text
(
artifact@content-hash,
entry_point,
canonicalized_input_bytes,
World_ref,
World_test,
EnvProfile,
oracle_version
)
```

Explain why reproducibility matters.

Explain:

* pinned artifact
* pinned dependencies
* pinned runtime
* pinned base image
* locale
* timezone
* randomness
* source date epoch
* clean environment
* temporary filesystem
* no network
* fixed working directory

---

# 21. REPRODUCIBILITY RULE

Use:

```text
k = 3
```

Explain that a witness is valid only when:

```text
Reference = PASS 3/3
Test      = FAIL 3/3
```

with the same failure signature.

If the reference also fails:

```text
DISCARD
```

Explain why.

---

# 22. INPUT GENERATION

Document:

### T1 — Real inputs

* call-site literals
* test fixtures
* JSON samples
* OpenAPI examples
* docstrings
* artifact tests

### T2 — Minimal valid inputs

### T3 — Schema-generated inputs

### T4 — Boundary inputs

Explain the anti-garbage rule.

A generated input cannot become the headline witness unless the reference world first accepts it.

Headline witnesses should prioritize:

```text
T1
T2
```

---

# 23. CONTRACT REPLAY

Explain supported cases:

* primitives
* nullable fields
* defaults
* nested objects
* lists
* dictionaries
* enums
* UUID
* datetime
* Decimal
* protobuf

Explain experimental cases:

* recursive models
* unions
* discriminated unions
* custom validators
* custom serializers
* custom encoders
* NaN
* infinity
* huge values
* exotic Unicode

Explain unsupported/inconclusive formats:

* arbitrary binary
* custom serialization
* unsupported Avro/Thrift/MessagePack cases
* database semantics

Explain pickle/joblib safety:

Only artifacts generated inside the sandbox may be replayed.

Never blindly load repository-supplied pickle files.

---

# 24. DIFFERENTIAL TYPECHECKING

Explain how type-checking provides a static compatibility signal.

Example:

```text
Consumer code
     |
     +---- reference world → diagnostics
     |
     +---- candidate world → diagnostics
```

Compare diagnostics.

Explain what constitutes:

```text
NEW DIAGNOSTIC
```

and how this differs from runtime witnesses.

---

# 25. WITNESS GENERATION

Define a Witness object.

Include:

* artifact
* artifact hash
* repository SHA
* world
* oracle
* entry point
* input
* expected result
* observed result
* failure signature
* timestamps
* environment
* image digest
* command
* stdout
* stderr
* traceback
* normalization
* reproducibility count

Explain what makes a witness trustworthy.

---

# 26. DELTA DEBUGGING / DDMin

This is extremely important.

Explain how Faultline identifies the smallest package difference responsible for the failure.

Example:

```text
World A
10 package differences
       ↓
remove half
       ↓
failure remains
       ↓
remove more
       ↓
...
       ↓
minimal difference set
```

Explain:

* algorithm
* test oracle
* resolver consistency
* caching
* complexity
* limits
* timeout
* failure modes

IMPORTANT:

Distinguish between:

### Observed world attribution

and:

### Counterfactual attribution worlds

Do not pretend a forced resolver world is an actual consumer environment.

---

# 27. VERDICT ENGINE

Create exact definitions for:

## BREAK WITNESSED

Reference passes 3/3 and test fails 3/3.

## SILENT DIVERGENCE WITNESSED

Both succeed but normalized outputs differ.

## NO DIVERGENCE OBSERVED

All exposed interactions exercised and matched.

Never call this:

```text
COMPATIBLE
```

## EXPOSED

Static usage found but execution not completed.

## POTENTIAL

Breaking API delta exists but usage is unresolved.

## NOT EXPOSED

No exposed usage under sufficient coverage.

## INCONCLUSIVE

Oracle could not execute or evidence was insufficient.

## HYGIENE

Drift without an L2+ cross-repo relationship.

---

# 28. ARTIFACT FAILURE VS INFRASTRUCTURE FAILURE

This distinction must be explicit.

A failed execution may be caused by:

* actual incompatibility
* missing test dependency
* resolver failure
* sandbox failure
* unsupported build
* timeout
* environment mismatch
* unsupported runtime
* harness bug

Explain how Faultline distinguishes:

```text
ARTIFACT FAILURE
```

from:

```text
HARNESS FAILURE
```

from:

```text
RESOLUTION FAILURE
```

from:

```text
INCONCLUSIVE
```

Never report infrastructure failures as compatibility failures.

---

# 29. EVIDENCE BUNDLE

Define the complete evidence bundle.

Include:

* repository SHA
* package hash
* lockfile
* resolved package list
* image digest
* runtime
* command
* input
* output
* traceback
* witness signature
* oracle version
* environment profile
* attribution result

Explain how another machine can reproduce the witness.

---

# 30. WHAT-IF ENGINE

Explain counterfactual analysis.

Do NOT perform a Cartesian product of every package version.

Use:

* reference version
* consumer versions
* compatible bounds
* latest patch
* limited candidate versions

Constraints:

```text
beam depth ≤ 3
beam width ≤ 5
```

Explain:

* target consumer
* shared constraint
* code migration

Explain pruning.

Explain ranking without pretending it is a certainty score.

---

# 31. REMEDIATION

Define:

```text
G1 Resolver acceptance
G2 Differential typecheck
G3 No unresolved exposures
G4 Existing witnesses pass + no new witnesses
```

Then:

```text
VERIFIED
PARTIALLY VERIFIED
SUGGESTED
```

Explain that LLM-generated patches are never automatically considered safe.

No automatic push or merge.

---

# 32. LLM BOUNDARY

This is mandatory.

Architecture:

```text
Deterministic Engines
        ↓
Typed Evidence
        ↓
Deterministic Verdict
        ↓
Templated Explanation
        ↓
Optional LLM Rephrasing
```

LLM may:

* summarize changelogs
* quote release notes
* explain evidence
* suggest migration code

LLM must NOT decide:

* verdict
* severity
* compatibility
* confirmation
* remediation verification

The MVP must work with:

```text
LLM = OFF
```

---

# 33. DATA MODEL

Design the complete database schema.

At minimum:

```text
Project
Repository
Commit
ResolvedWorld
PackageVersion
Artifact
ApiDelta
UsageIndex
Relationship
Cell
Witness
Finding
EvidenceBundle
Remediation
```

For every entity provide:

* purpose
* fields
* primary key
* foreign keys
* indexes
* relationships

Explain why symbols and usage sites should NOT become graph database nodes.

No graph database unless there is a demonstrated need.

---

# 34. BACKEND ARCHITECTURE

Design the complete backend.

Prefer a practical hackathon architecture.

Explain:

```text
FastAPI
PostgreSQL/SQLite
Worker processes
Sandbox runner
Cache
Object/evidence storage
```

Define services/modules.

For example:

```text
api/
ingestion/
parsers/
resolvers/
relationships/
worlds/
api_diff/
usage/
oracles/
sandbox/
witness/
attribution/
verdict/
what_if/
remediation/
security/
storage/
```

Explain responsibility of every module.

---

# 35. COMPLETE API DESIGN

Define backend endpoints.

Examples:

```text
POST /projects
POST /projects/{id}/repositories
POST /analysis
GET /analysis/{id}
GET /findings
GET /findings/{id}
GET /witnesses/{id}
GET /relationships
GET /worlds
GET /blast-path
GET /why-path
POST /what-if
POST /remediation
```

For each endpoint provide:

* method
* URL
* request
* response
* errors
* authentication assumptions
* example JSON

---

# 36. FRONTEND

Design the complete Faultline UI.

Required screens:

## Dashboard

## Findings

## Dependency World Matrix

## Witness Detail

## Why Path

## Blast Radius

## What-If

## Suspected Relationships

## Inventory Graph

## Evidence Bundle

Explain exact components and user flow.

---

# 37. HERO UI

The most important screen should visually communicate:

```text
37 candidate drifts
        ↓
12 exposed
        ↓
4 verified
        ↓
2 witnessed breaks
```

Then:

```text
Producer
   ↓
Shared Artifact
   ↓
Consumer World
   ↓
Changed Package
   ↓
Changed Symbol
   ↓
Witness
```

The user should immediately understand:

> Detect → Reproduce → Attribute → Fix

---

# 38. WHY-PATH UI

For every finding provide:

```text
Repository A
    ↓
produces artifact X
    ↓
Repository B consumes X
    ↓
B resolves package P v1
    ↓
A/reference world resolves P v2
    ↓
symbol S changed
    ↓
B uses S
    ↓
replay fails
    ↓
minimal cause = P
```

Explain exactly how this evidence chain is constructed.

---

# 39. INVENTORY GRAPH

Create a graph view showing:

```text
Repositories
Artifacts
Packages
Consumers
Schemas
```

But explain why graph visualization is a UI representation rather than necessarily a graph database.

---

# 40. PERFORMANCE ARCHITECTURE

Explain the funnel:

```text
10 repositories
↓
100 manifests
↓
~10,000 dependency entries
↓
tens of L2+ pairs
↓
handful of cells
↓
tens of API deltas
↓
dozens of exposures
↓
small number of oracle runs
```

These are EXPECTATIONS, not claimed benchmark results.

Explain caching:

* package artifact cache
* API surface cache
* API delta cache
* import index cache
* resolved world cache
* file usage cache
* oracle result cache

Deduplicate identical package versions.

---

# 41. MONOREPO SUPPORT

Explain:

* uv workspaces
* Poetry/path dependencies
* npm workspaces
* pnpm
* Yarn PnP
* Maven multi-module
* generated packages
* Docker co-residence

Explain when a relationship is automatically recognized.

Never assume a relationship just because two repositories look similar.

---

# 42. SECURITY THREAT MODEL

Create a proper threat model.

Threats:

* malicious repository
* malicious package
* dependency confusion
* typosquatting
* malicious setup.py/build backend
* npm install scripts
* Maven plugin execution
* zip bombs
* path traversal
* symlink escape
* Git submodule attacks
* Git LFS abuse
* huge files
* fork bombs
* memory exhaustion
* CPU exhaustion
* disk exhaustion
* prompt injection
* XSS
* SSRF
* secret exfiltration
* credential leakage
* Docker socket escape

For every threat specify:

```text
Threat
Attack
Impact
Mitigation
Residual risk
```

---

# 43. PROMPT INJECTION

Repositories are untrusted data.

Explain why source code, README files, comments, changelogs, and package metadata can contain prompt injection.

LLM must never be allowed to treat repository text as system instructions.

The LLM should receive:

```text
structured evidence
```

rather than unrestricted repository instructions whenever possible.

---

# 44. FAILURE HANDLING

Create a complete failure taxonomy.

Examples:

```text
FETCH_FAILED
INVALID_REPOSITORY
MANIFEST_PARSE_FAILED
RESOLUTION_FAILED
UNSUPPORTED_BUILD
SANDBOX_FAILED
TIMEOUT
RESOURCE_LIMIT
ORACLE_FAILED
STATIC_ANALYSIS_FAILED
INSUFFICIENT_COVERAGE
INCONCLUSIVE
```

Explain recovery/retry behavior.

---

# 45. EDGE CASES

Create an exhaustive edge-case table.

At minimum cover:

* empty repository
* monorepo
* nested repository
* fork
* archived repo
* deleted dependency
* private dependency
* mutable tag
* force-pushed branch
* Git submodule
* Git LFS
* symlink
* huge repository
* huge package
* generated code
* dynamic imports
* reflection
* plugins
* optional dependency
* platform-specific dependency
* Python extras
* npm peer dependencies
* npm multiple copies
* Maven BOM
* Maven profile
* SNAPSHOT
* circular dependencies
* dependency conflict
* package yanked
* unavailable version
* native extension
* compiled artifact
* no wheel
* sdist
* unsupported build backend
* network dependency
* time-dependent behavior
* locale-dependent behavior
* timezone-dependent behavior
* randomness
* environment variables
* secrets
* custom serialization
* protobuf evolution
* schema drift
* pickle/joblib
* database interaction
* external API interaction
* test-only dependency
* missing test framework
* flaky test
* nondeterministic output
* huge input
* malformed input
* generated input
* dynamic getattr
* importlib
* monkeypatch
* metaclass
* decorator
* exec
* code generation

For each state:

```text
Supported?
Handling?
Verdict?
Reason?
```

---

# 46. TESTING STRATEGY

Design:

## Unit tests

## Integration tests

## End-to-end tests

## Security tests

## Regression tests

## Determinism tests

## Differential tests

## Sandbox escape tests

## False-positive tests

## False-negative tests

## Performance tests

## Demo tests

---

# 47. FIXTURE ORGANIZATION

Create a controlled fixture organization:

```text
acme-models
orders-svc
billing-svc
notify-svc
```

Design multiple known scenarios.

Examples:

### Fixture A

No drift.

### Fixture B

API removed.

### Fixture C

Signature changed.

### Fixture D

Dependency world drift.

### Fixture E

Silent output divergence.

### Fixture F

Static exposure but runtime inconclusive.

### Fixture G

Unrelated dependency drift.

### Fixture H

False positive candidate.

### Fixture I

Dynamic usage.

### Fixture J

Data contract drift.

For every fixture specify expected Faultline verdict.

---

# 48. BENCHMARK AND ABLATION

Design a benchmark to demonstrate that the project works.

Measure:

* precision
* recall where ground truth exists
* false positives
* false negatives
* witness reproducibility
* attribution accuracy
* analysis time
* world coverage
* static exposure coverage

Create ablations:

### A

Version comparison only.

### B

API diff only.

### C

API diff + static usage.

### D

Author-selected test matrix.

### E

Consumer-derived world matrix.

### F

Consumer-derived worlds + witness verification.

### G

Consumer-derived worlds + witness + ddmin.

Explain what each ablation proves.

---

# 49. WORLD COVERAGE METRIC

Introduce:

```text
World Coverage =
number of consumer dependency worlds analyzed
/
number of consumer dependency worlds discovered
```

Also compare:

```text
Producer CI worlds
vs
Consumer worlds
vs
Faultline analyzed worlds
```

Example:

```text
Producer CI worlds: 1
Consumer worlds: 4
Faultline analyzed: 4

Coverage = 100%
```

Explain that this is a coverage metric, not a compatibility score.

---

# 50. NOVELTY

Do NOT claim that individual techniques are new.

Explicitly acknowledge existing ideas:

* dependency graphs
* semver
* API diff
* reachability
* downstream testing
* matrix testing
* contract testing
* schema compatibility
* delta debugging
* minimal failure localization

Then position the contribution as the combination:

> Faultline derives the test matrix from dependency worlds that consuming repositories actually resolve, checks shared artifacts and relevant data contracts in those worlds, and narrows observed failures to minimal package differences with reproducible witnesses.

Explain why this is technically meaningful.

Also explain the novelty risk:

> “Isn't this just matrix testing + Pact + bisect?”

Provide the precise answer.

---

# 51. JUDGE ATTACK MATRIX

Create a table:

| Judge Attack                                  | Strong Answer |
| --------------------------------------------- | ------------- |
| Dependabot already does this                  | ...           |
| Isn't this just version comparison?           | ...           |
| Isn't replay synthetic?                       | ...           |
| You cannot prove compatibility                | ...           |
| Relationships are guessed                     | ...           |
| What about dynamic code?                      | ...           |
| Why use AI?                                   | ...           |
| Why use a graph?                              | ...           |
| How does this scale?                          | ...           |
| Is it secure?                                 | ...           |
| Is the demo staged?                           | ...           |
| Separate services don't share dependencies    | ...           |
| Why only Python?                              | ...           |
| Isn't this Pact?                              | ...           |
| How do you know the exact package?            | ...           |
| What if the reference world itself is broken? | ...           |
| What about Python version changes?            | ...           |
| How do you evaluate it?                       | ...           |

Answers must be technically honest.

---

# 52. FINAL MVP SCOPE

Clearly separate:

## MUST HAVE

* pinned SHA ingestion
* Python manifest parsing
* npm/Maven manifest parsing
* Python resolution
* npm lockfile handling
* L2/L3 relationships
* consumer worlds
* cells
* sandbox
* O-import
* O-tests
* O-bind
* witness
* k=3
* ddmin
* verdict engine
* evidence bundle
* UI
* inventory graph

## SHOULD HAVE

* Pydantic contract replay
* griffe API diff
* static usage
* pyright
* what-if
* remediation
* real Flask/Werkzeug case
* benchmark
* protobuf

## NICE TO HAVE

* observed usage
* TypeScript `.d.ts`
* tsc
* japicmp
* Maven helper
* topology
* OSV
* typosquat detection
* gVisor
* GitHub Action

---

# 53. EXPLICITLY REJECTED FEATURES

Document why these are NOT part of the MVP:

* graph database
* Kubernetes
* message queues
* GNN/ML risk scoring
* LLM verdicts
* autonomous LLM agents
* arbitrary repository test suites by default
* sdists
* Go
* Rust
* .NET
* SAT solver
* SaaS authentication
* auto merge
* automatic GitHub push
* numeric risk score
* T4 fuzzing as headline
* unconfirmed model-twin findings

---

# 54. COMPLETE REPOSITORY STRUCTURE

Design the exact codebase.

For example:

```text
faultline/
│
├── backend/
│   ├── api/
│   ├── core/
│   ├── ingestion/
│   ├── parsers/
│   ├── resolvers/
│   ├── relationships/
│   ├── worlds/
│   ├── diff/
│   ├── usage/
│   ├── oracles/
│   ├── sandbox/
│   ├── witnesses/
│   ├── attribution/
│   ├── verdicts/
│   ├── whatif/
│   ├── remediation/
│   ├── security/
│   ├── storage/
│   └── workers/
│
├── frontend/
│
├── fixtures/
│
├── benchmarks/
│
├── tests/
│
├── scripts/
│
├── docs/
│
└── docker/
```

Modify this if required by the final architecture.

For EVERY important folder explain:

* purpose
* important files
* responsibilities
* dependencies
* inputs
* outputs

---

# 55. COMPLETE IMPLEMENTATION ORDER

This section must be extremely detailed.

Start from an empty directory.

Explain exactly what we implement first.

Use this baseline order:

## PHASE 0

Project bootstrap.

## PHASE 1

Fixture repositories.

## PHASE 2

Sandbox.

## PHASE 3

Git ingestion.

## PHASE 4

Python manifest parsing.

## PHASE 5

Python resolution.

## PHASE 6

Relationship discovery.

## PHASE 7

Consumer world construction.

## PHASE 8

Cells.

## PHASE 9

O-import.

## PHASE 10

O-tests.

## PHASE 11

Witness generation.

## PHASE 12

k=3 verification.

## PHASE 13

ddmin attribution.

## PHASE 14

Verdict engine.

## PHASE 15

Evidence bundle.

## PHASE 16

Minimal UI.

## PHASE 17

API diff.

## PHASE 18

Static usage.

## PHASE 19

Exposure coverage.

## PHASE 20

Differential type checking.

## PHASE 21

Contract replay.

## PHASE 22

What-if engine.

## PHASE 23

Remediation verification.

## PHASE 24

npm.

## PHASE 25

Maven.

## PHASE 26

Benchmark.

## PHASE 27

Security hardening.

## PHASE 28

Demo packaging.

For EVERY phase provide:

1. Goal
2. Files to create
3. Classes/functions
4. Database changes
5. API changes
6. Inputs
7. Outputs
8. Dependencies
9. Tests
10. Acceptance criteria
11. Common bugs
12. What must be completed before moving on

---

# 56. ACTUAL ALGORITHMS

Provide pseudocode for:

### Algorithm 1

Relationship discovery

### Algorithm 2

Consumer-world/cell construction

### Algorithm 3

API divergence detection

### Algorithm 4

Changed-symbol exposure

### Algorithm 5

Differential type checking

### Algorithm 6

Binding replay

### Algorithm 7

Contract replay

### Algorithm 8

Witness verification

### Algorithm 9

DDMin attribution

### Algorithm 10

Evidence → verdict

### Algorithm 11

Counterfactual what-if generation

### Algorithm 12

Remediation verification

### Algorithm 13

Incremental re-analysis

Pseudocode must be implementation-oriented, not academic filler.

---

# 57. COMPLETE DATA FLOW

Give a detailed data-flow explanation:

```text
GitHub URL
 ↓
Pinned SHA
 ↓
Repository Snapshot
 ↓
Manifest Extraction
 ↓
Dependency Resolution
 ↓
ResolvedWorld
 ↓
Relationship Discovery
 ↓
Consumer Matrix
 ↓
Artifact/API Extraction
 ↓
API Delta
 ↓
UsageIndex
 ↓
Exposure
 ↓
Oracle Plan
 ↓
Sandbox Execution
 ↓
Witness
 ↓
DDMin
 ↓
Verdict
 ↓
Finding
 ↓
UI
```

Explain every transition.

---

# 58. DATABASE FLOW

Show which objects are persisted at every stage.

For example:

```text
Repository
    ↓
ResolvedWorld
    ↓
PackageVersion
    ↓
Relationship
    ↓
Cell
    ↓
ApiDelta
    ↓
UsageIndex
    ↓
Witness
    ↓
Finding
```

---

# 59. 7-DAY HACKATHON IMPLEMENTATION PLAN

Use the previous plan:

### Day 1

Fixtures + sandbox

### Day 2

Ingestion + Python resolution

### Day 3

Relationships + cells + first witness

### Day 4

DDMin + evidence + verdict

### Day 5

UI + hero demo

### Day 6

Contract replay + negative controls

### Day 7

O-bind + usage + exposure + benchmark + freeze

For each day provide:

* tasks
* owners
* expected output
* acceptance criteria
* fallback if blocked

---

# 60. TEAM DIVISION

Assume a 4-person engineering team.

Divide work into:

### Member 1

Backend/control plane

### Member 2

Resolver/world/relationship engine

### Member 3

Sandbox/oracles/witness/ddmin

### Member 4

Frontend/UI/demo/evaluation

Explain integration points and how to avoid parallel work becoming incompatible.

---

# 61. REAL FLASK/VERKZEUG CASE

Include a real-world demonstration scenario involving Flask/Werkzeug dependency compatibility.

Explain:

* historical dependency versions
* producer/consumer setup
* dependency-world difference
* affected API
* expected failure
* witness
* attribution
* remediation

Do not invent exact behavior if it has not been verified.

Mark anything that requires actual runtime validation.

---

# 62. DEMO

Design the complete 3–5 minute hackathon demo.

Narrative:

# DETECT → REPRODUCE → ATTRIBUTE → FIX

Suggested sequence:

### 0:00–0:30

Problem.

### 0:30–1:00

Show repositories.

### 1:00–1:30

Show consumer-derived worlds.

### 1:30–2:00

Show drift funnel.

### 2:00–2:40

Open witness.

### 2:40–3:10

Run witness again.

### 3:10–3:40

Show ddmin attribution.

### 3:40–4:20

Show fix / what-if.

### 4:20–5:00

Show evidence + architecture + final value.

Explain exactly what should be visible on screen.

---

# 63. DEMO MODES

Implement:

```text
LIVE
FIXTURE
REPLAY
```

They must be clearly labelled.

Explain:

### LIVE

Actually performs analysis.

### FIXTURE

Uses deterministic prepared repositories.

### REPLAY

Replays stored evidence.

Prepare:

* pinned SHAs
* package caches
* container images
* resolution caches
* evidence bundles
* fallback static results

Never pretend a cached result is live analysis.

---

# 64. FINAL PROJECT PITCH

Create:

### 15-second pitch

### 30-second pitch

### 60-second pitch

### Technical pitch

### Judge pitch

The core message should remain:

> “Your shared code is tested in one dependency world and runs in many. Faultline finds those consumer worlds and produces witnesses for the failures that actually matter.”

---

# 65. LIMITATIONS

Be extremely honest.

Discuss:

* arbitrary public repositories
* dynamic code
* native dependencies
* private registries
* unsupported build systems
* external services
* database semantics
* runtime differences
* environment differences
* flaky tests
* incomplete static coverage
* unsupported serialization
* resolver failures
* sandbox limitations

Do not hide limitations.

Explain how Faultline communicates them.

---

# 66. WHAT FAULTLINE DOES NOT CLAIM

Create a dedicated section.

Explicitly state:

Faultline does NOT claim:

* universal compatibility proof
* complete repository understanding
* detection of every possible failure
* perfect dynamic analysis
* perfect static analysis
* perfect causal attribution
* zero false positives
* zero false negatives

Instead it claims:

> bounded, reproducible, evidence-backed compatibility observations over analyzed consumer dependency worlds.

---

# 67. FINAL ARCHITECTURE

End with one complete architecture diagram in ASCII.

Use something similar to:

```text
                         ┌──────────────────────┐
                         │      FRONTEND        │
                         │ Matrix / Findings    │
                         │ Witness / What-if    │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │    CONTROL PLANE     │
                         │      FastAPI         │
                         │ Projects / Findings  │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
       ┌──────▼──────┐       ┌──────▼──────┐       ┌──────▼──────┐
       │  INGESTION  │       │  RESOLVERS  │       │ RELATIONSHIP │
       │ Git @ SHA   │       │ Python/npm  │       │   ENGINE     │
       │ manifests   │       │ Maven       │       │ L2/L3/L4    │
       └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  CONSUMER WORLDS     │
                         │     + CELLS          │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   ANALYSIS ENGINE     │
                         │ API Diff / Usage     │
                         │ Exposure / Typecheck │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  EXECUTION ZONE       │
                         │ Import / Bind / Tests │
                         │ Contract Replay       │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │ WITNESS + DDMin       │
                         │ Reproduce + Attribute │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  VERDICT ENGINE       │
                         │ Evidence + Findings   │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │ WHAT-IF / REMEDIATION │
                         └───────────────────────┘
```

Improve the diagram if necessary.

---

# 68. FINAL QUALITY CHECK

Before finishing the document, perform a self-review.

Check:

### Architecture

* Is every component connected?
* Is every responsibility clear?

### Implementation

* Can developers actually start coding from this document?

### Security

* Is repository code treated as hostile?

### Evidence

* Can every finding be reproduced?

### Scientific validity

* Are claims appropriately bounded?

### Cross-repo requirement

* Is Faultline genuinely cross-repository?

### Novelty

* Is the contribution defensible without exaggeration?

### MVP

* Is the MVP realistically buildable?

### Demo

* Can the system produce a convincing 3–5 minute demonstration?

### Edge cases

* Are important failure modes handled?

### LLM

* Is LLM outside the deterministic decision path?

### Attribution

* Is DDMin correctly distinguished from observed-world evidence?

### Terminology

* Are “proof”, “guarantee”, “compatible”, and “AI detected” avoided unless technically justified?

---

# 69. OUTPUT REQUIREMENT

Do NOT give me a short answer.

Produce the complete document.

Use this exact structure:

```text
FAULTLINE
Cross-Repo Dependency Drift Detector

MASTER ENGINEERING & IMPLEMENTATION DOCUMENT

1. Executive Summary
2. Problem Statement
3. PS07 Requirements
4. Problem Analysis
5. Faultline Vision
6. Core Innovation
7. Terminology
8. System Scope
9. Non-Scope
10. Dependency World Model
11. Channel Taxonomy
12. Cross-Repo Relationship Model
13. Relationship Discovery
14. Ecosystem Architecture
15. Repository Ingestion
16. Dependency Resolution
17. Consumer-Derived World Matrix
18. API Extraction
19. API Delta Detection
20. Static Usage Analysis
21. Exposure & Coverage
22. Transitive Analysis
23. Verification Engine
24. Replay Model
25. Input Generation
26. Contract Replay
27. Differential Typechecking
28. Witness Generation
29. DDMin Attribution
30. Verdict Engine
31. Evidence Bundles
32. What-If Engine
33. Remediation
34. Security Architecture
35. Threat Model
36. LLM Boundary
37. Database/Data Model
38. Backend Architecture
39. API Specification
40. Frontend Architecture
41. UI/UX
42. Inventory Graph
43. Performance
44. Caching
45. Monorepos
46. Failure Handling
47. Edge Cases
48. Testing Strategy
49. Fixture Organization
50. Benchmark
51. Ablation Study
52. World Coverage
53. Novelty
54. Prior-Art Positioning
55. Judge Attack Matrix
56. MVP Scope
57. Rejected Features
58. Repository Structure
59. Algorithms
60. Data Flow
61. Database Flow
62. Implementation Phases
63. Detailed Coding Plan
64. 7-Day Plan
65. Team Division
66. Real-World Demo Case
67. Demo Architecture
68. 3–5 Minute Demo Script
69. Pitch
70. Limitations
71. What Faultline Does Not Claim
72. Final Architecture
73. Final Technical Checklist
74. Final Implementation Checklist
75. Final Project Definition
```

---

# 70. STYLE

Write like a combination of:

* senior software architect
* cybersecurity engineer
* distributed systems engineer
* developer
* research engineer
* hackathon technical lead

Do NOT write like a generic AI explanation.

Use:

* tables
* architecture diagrams
* sequence diagrams
* data-flow diagrams
* state machines
* pseudocode
* schemas
* API examples
* JSON examples
* folder structures
* implementation checklists

Whenever possible, explain:

```text
INPUT
↓
PROCESS
↓
OUTPUT
↓
PERSISTED DATA
↓
NEXT COMPONENT
```

For difficult concepts, give:

1. Simple explanation
2. Technical explanation
3. Implementation approach
4. Edge cases
5. Example

---

# 71. CRITICAL FINAL RULE

The final document must answer this question completely:

> **“If our 4-person team opens this document tomorrow morning with an empty repository, can we use it as the technical blueprint to actually build Faultline from zero to a working end-to-end hackathon prototype?”**

If the answer is not clearly YES, expand the missing implementation details.

Do not stop at architecture.

Do not stop at algorithms.

Do not stop at pseudocode.

Explain the actual engineering path from:

```text
EMPTY REPOSITORY
        ↓
CODE
        ↓
WORKING ANALYZER
        ↓
WORKING CROSS-REPO VERIFICATION
        ↓
REPRODUCIBLE WITNESS
        ↓
ATTRIBUTED FINDING
        ↓
UI
        ↓
DEMO
```

The final result should be the **complete Faultline engineering blueprint and implementation bible**.

Make it technically rigorous, implementation-oriented, security-conscious, evidence-driven, and honest about limitations.

# FINAL TAGLINE

**FAULTLINE — WITNESSES, NOT WARNINGS.**
</pasted_content id="0072">
