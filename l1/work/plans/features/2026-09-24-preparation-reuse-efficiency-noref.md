# Feature Plan

## Improve preparation reuse efficiency

- Date: 2026-09-24
- Status: In progress
- Title: Improve L1 preparation reuse efficiency using attributed validation costs
- Kind: Feature
- Severity: Medium
- Stage: 1
- Subsystem: Managed providers / native preparation / validation memos / performance measurement
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/cli_args/model.l0`
  - `l1/compiler/stage1_l0/src/cli_args/parse.l0`
  - `l1/compiler/stage1_l0/src/cli_args/help.l0`
  - `l1/scripts/build_stage1_l1c.py`
  - `l1/compiler/stage1_l0/src/preparation/consumer.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/compiler/stage1_l0/support/preparation/platform.h`
  - `l1/compiler/stage1_l0/support/preparation/sha256.h`
  - `l1/scripts/check_preparation_reuse.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/source_paths_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_bootstrap_interfaces_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_windows_environment_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_observability_test.c`
  - `l1/compiler/stage1_l0/tests/preparation_digest_seed_test.c`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_reuse_report_test.py`
- Related:
  - [l1/docs/reference/stdlib-preparation.md][preparation]
  - [l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md][semantic-authority]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary]
  - [l1/work/plans/features/closed/2026-09-24-preparation-observability-noref.md][observability]
- Repro: The Docker matrix and command descriptions in the attached investigation below.

## Summary

Reduce avoidable validation and imported source compilation while preserving preparation correctness. Existing debug
observations distinguish a reusable native profile from reusable evidence about that profile. The attached Docker
investigation confirms that the native identity can remain unchanged while metadata rejection, a changed discovery
selection, or explicit system-root selection incurs substantial work.

This standalone plan organizes five phases within one work item. Phase 1 implements equivalent bundled root recognition
with an explicit source opt-out. Phase 2 implements disposable digest-seed hints while retaining cwd-sensitive
discovery. Phase 3 investigates preparation reuse practices for containerized compiler services and comparable isolated
deployments, with playgrounds as one use case. Phases 3 through 5 remain future work, subject to their evidence and
compatibility gates. The original investigation attachments remain immutable historical evidence; Phase 1 and Phase 2
measurements and validation are recorded separately.

## ADR Impact

- Decision: Recognize an explicitly selected bundled root without losing managed providers, with an explicit source-use
  compatibility policy.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: Phase 1 replaces unconditional explicit-root suppression with filesystem-identity recognition and the
    `--no-managed-stdlib` opt-out. ADR-0038 records that compatibility decision; ADR-0033 delegates its
    provider-selection wording to that contract. Phases 3 through 5 remain independent and unresolved.
- Decision: Share validated file digest records across cwd selections through a disposable donor hint, retaining
  cwd-sensitive discovery.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Phase 2 adds a best-effort locator for existing machine-local evidence. Donor records retain the same
    metadata checks, force behavior and live search dependencies; discovery is never copied. ADR-0039 records the
    bounded lookup and failure policy without a new authority or cwd-independence proof.
- Decision: Define the authority and isolation boundary for preparation reuse in containerized compiler services.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Phase 3 must compare deployment practices and establish whether the recommended approach fits ADR-0039's
    local-evidence constraints or requires an ADR amendment or new architectural contract. Image preparation, worker
    warmup, runtime evidence distribution and shared storage remain candidates. Copied/shared portability is currently
    unsupported, and untrusted requests cannot establish authority; see
    [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary].
- Decision: Choose a portable SHA-256 backend and any platform-acceleration/dependency policy.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Phase 4 must compare identical-output backends and their platform/maintenance costs. ADR-0039's content
    coverage and stable validation boundary remain constraints; faster hashing cannot substitute weaker identity
    evidence. The backend choice and final ADR disposition remain open; see
    [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary].

## Original Evidence (Before Phase 1)

- [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/investigation.md][investigation]: complete
  methodology, findings, limitations, scenario tables, and reproducible command descriptions.
- [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/report.json][measurements]: all primary
  measurements, parsed observations, comparisons, aggregates, and image provenance.
- [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/logging-control-report.json][logging-control]:
  the additional paired verbosity and capture-location control.

The attachments are sanitized copies of retained local evidence. The investigation documents the exact transformation
and the limits of raw-log references; original local files remain unchanged. The Linux findings are distinct from
earlier macOS leads and do not claim identical performance across hosts.

The primary matrix contains 42 container cases, 150 successful builds and output checks, and 138 debug builds with zero
preparation build commands. Median Clang fresh/warm times are 3.434/0.682 seconds. GCC with memos removed and its next
warm invocation takes 1.455/0.607 seconds. In this environment:

- Explicitly naming the same bundled root selects eleven source providers on every invocation despite native-profile
  reuse. This was deliberate baseline behavior under ADR-0038; Phase 1 records its compatibility change below.
- A different cwd changes discovery and input-memo selection without changing the native key. The first such Clang
  invocation hashes 240,347,792 toolchain bytes; the next becomes warm.
- Fresh containers reject image-baked directory and file inode evidence. Revalidation retains the native key.
- Fresh Clang toolchain hashing takes 1.596 seconds median, with another 1.046 seconds in nested discovery probes. These
  are components of its preparation spans, not additional time to add to them.
- Artifact hashing and copying are smaller costs in this sample. About 0.494 seconds for GCC and 0.604 seconds for Clang
  remain outside the warm preparation spans and are not yet attributed to compilation phases.

## Goals and Boundaries

Recognize equivalent bundled-root selections, reuse valid content evidence across discovery selections, investigate
preparation reuse for containerized compiler service images and comparable isolated deployments, reduce measured
discovery/hash costs, and attribute substantial remaining warm time. Preserve content identity, completed-profile
validation, explicit interface authority, source ordering, eligibility refusal, stable-read checks, corruption
detection, and force behavior unless an explicit design decision changes a documented contract.

No new diagnostic codes are planned. Existing debug records and ordinary failure diagnostics remain the starting point.
Do not weaken validation by ignoring metadata differences, dropping large implementation libraries, or trusting a cache
solely because its native key matches. Cross-host cache portability, a general shared cache service, application
caching, and implementing every later profiling recommendation are outside this plan.

## Implementation Gates

At each phase gate, append a decision record to this plan or a linked attachment with: alternatives tested; environment
and configuration; correctness results; individual measurements and distributions; measured benefit; storage,
dependency, concurrency, and maintenance complexity as applicable; and the selected or deferred outcome with rationale.
Record negative results and unavailable configurations. Timing evidence selects among correct implementations; it does
not settle CLI compatibility or establish a new trust boundary.

Use the retained baseline to formulate experiments, then repeat comparisons against the implementation-time baseline.
Keep the original attachments immutable. Any new evidence receives a separately identified attachment. A phase may defer
an alternative when evidence does not justify its cost, but must state what question remains open and what work would
resolve it. Resolve all ADR Impact records before eventual plan closure.

## Phase 1: Recognize Explicitly Selected Bundled Roots

**Status.** Completed on 2026-09-24 for the validated macOS/Linux configurations. Native Windows validation remains
unavailable in this session. Full L1 normal and trace validation passed; 40 Docker containers verified 280 compiler
invocations and program outputs. Explicit-root median times fell by approximately 82-85% across GCC/Clang debug and
quiet controls while native preparation build counters stayed zero. See the Phase 1 decision and evidence below.

**Hypothesis.** An explicit root that identifies the bundled directory can safely retain managed providers, avoiding
repeated imported source compilation. The current suppression depends on how the root was supplied, not different
compiler or stdlib contents.

**Preferred approach.** Reuse the existing resolver's filesystem-identity machinery to recognize the bundled directory
whether selected implicitly or explicitly. Place managed providers at the same ordered root position; preserve explicit
interface precedence and requested source targets. Text equality or matching directory contents is insufficient to
establish bundled identity.

**Alternatives and gate.** Retain suppression with an explicit managed-provider opt-in, or add a separate source-only
control if callers require the current ability to force source imports. Before implementation, decide and document the
CLI compatibility contract and amend ADR-0038 as appropriate. Faster explicit-root timings alone cannot choose that
contract. Inspect existing tests and documented use cases for intentional source-only behavior.

**Experiment.** Compare provider events, imported-source analyses, native keys, counters, and elapsed distributions for
implicit selection, an explicit equivalent root, symlink/directory aliases supported by each platform, ordered custom
roots, explicit interfaces, copied stdlib trees, requested source targets, and missing or invalid managed providers.
Repeat the explicit-root Docker pair with both compilers.

**Correctness requirements.** Equivalent directory identity must not promote a copied tree to bundled authority. Custom
root order, explicit interface authority, source-target semantics, and current invalid-provider failure/fallback rules
remain valid under the chosen CLI contract. Test aliases and unavailable filesystem identity conservatively.

**Completion criteria.** The CLI decision is recorded; equivalent bundled selections retain expected provider origins
and paths and avoid imported source compilation; intentional source use remains expressible if required; negative and
precedence tests pass. Record the measured benefit independently of native preparation counters.

### Phase 1 implementation decision (2026-09-24)

Selected automatic filesystem-identity recognition plus `--no-managed-stdlib`. Retaining suppression with a managed
opt-in would preserve existing commands but would leave equivalent explicit roots on the slow path by default. Automatic
recognition without an opt-out would break intentional source workflows. Inspection found concrete callers: semantic
bootstrap needs source imports before interfaces exist, and native test helpers intentionally combine source imports
with a separately supplied runtime and `--no-auto-prepare`. These callers now use the opt-out.

The opt-out is accepted in source-resolving modes and rejected in standalone link and explicit preparation with the
existing `L1C-2157`. Explicit interfaces keep authority, compile-only keeps its imported-interface requirement, and
requested targets remain source-backed. The option does not disable native runtime preparation. Ordered custom roots,
`L1_SYSTEM`, project-root behavior, identity failures, and invalid managed-provider handling retain their contracts. No
cache format, identity coverage, concurrency protocol, or dependency changes were needed.

Implementation and correctness checks are recorded in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/results.md][phase-one]. The parent
plan remained active for Phases 2 through 5 at that point. Phase 2 is recorded below; Phases 3 through 5 remain pending.

## Phase 2: Separate Digest Reuse from Discovery Selection

**Status.** Completed on 2026-09-24 for the validated macOS/Linux configurations. Native Windows execution was
unavailable. Validation and measurement results are recorded in the
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase2/results.md][phase-two]. The parent
plan remains active for Phases 3 through 5.

**Selected approach.** Retain the complete cwd-sensitive discovery selection and existing toolchain memo format. Add one
`v1/memo/digest-seeds/<seed-key>.json` hint per configuration, keyed by the same selection with only `cwd` omitted. Its
schema is 1, kind is `input-digest-seed`, and `memo_key` is a validated 64-hex-character key naming one existing local
toolchain memo. No selection or native identity fields are removed.

When the current memo cannot supply a valid file digest, lazily load at most one hinted donor per invocation. Discovery
still selects all inputs. Reuse only a selected file's valid digest with matching current reliable metadata, copying it
into the current memo through the existing record path. Never consult donor discovery. The saved current memo has no
remaining dependency on the donor. Force bypasses both evidence sources, and eligibility refusals remain unchanged.

**Failure and storage policy.** Missing, deleted, unreadable, malformed, incompatible or stale optional evidence falls
back to ordinary validation and stable-read hashing. Actual input failures retain their diagnostics. JSON copying has no
recoverable error return; general allocation-failure behavior remains unchanged. Update a hint only after successfully
saving an eligible native toolchain memo. Writes are best-effort; failed writes and lost updates only reduce reuse.
There are no new locks, writer coordination, merges, history, directory scans or automatic reclamation. Storage adds one
small hint per configuration excluding cwd; existing memo accumulation and manual cache deletion remain unchanged.

**Alternatives and scope decision.** The accepted implementation plan supersedes the earlier requirement to prototype
and benchmark both a standalone digest store and a bounded secondary index. A single donor hint reuses existing evidence
and copying behavior without a new digest store. Multiple donors or a separate store might improve hit rates across
changing file sets but are deferred until a measured workload justifies them. This phase does not investigate
cwd-independent discovery, build a configuration classifier or attempt to prove cwd independence. Conservative
reobservation is the chosen behavior, not an unresolved completion gate.

**Observability.** Existing `-vvv` decision records distinguish hint lookup, donor acceptance/rejection, validated
current/donor record reuse, hashing fallback and best-effort hint publication. Per-file decisions name the selected
path. Candidate lookup is not reported as validated digest reuse. Normal output, counters and timing meanings remain
unchanged; the existing reporter retains and renders these records.

**Validation and completion.** Compare repeated changed-cwd pairs with absolute targets/projects, unchanged native
identity, required discovery probes, fewer hash bytes and correct executable output. Include relative nested response
files and search paths, new shadow candidates, replaced inputs, force, deleted/malformed evidence, publication failures
and donor-independent saved memos. Run focused support, identity, ownership and reporter coverage, L1 normal validation
and relevant trace coverage. Record individual timing distributions, storage overhead and unavailable platforms in
separate evidence; preserve all historical attachments. No new diagnostic codes or portability guarantees are
introduced.

## Phase 3: Investigate Preparation Reuse for Containerized Compiler Services

**Objective.** Discover established practices for packaging and operating a containerized compiler service image or
comparable isolated compiler deployment, then assess their applicability to Dea. Playgrounds are one use case, not a
required service architecture. Distinguish reuse of compiled stdlib/runtime artifacts from reuse of validation records:
avoiding recompilation can be valuable even when discovery or hashing must repeat.

**Discovery and alternatives.** Use primary documentation and implementation sources from established compiler services
and container tooling to compare:

- Pre-warmed build images feeding service images through image inheritance or copying the toolchain and prepared cache.
- Workers warmed at startup and serving isolated requests over their lifetime.
- Trusted runtime evidence distributed to fresh request containers with private writable state.
- Shared read-only toolchain storage and prepared support, with request outputs kept separate.

Examine worker lifetime, request isolation, cache ownership, toolchain updates and failure recovery for each candidate.
Separate documented practices from hypotheses about Dea reuse; a packaging mechanism alone does not establish metadata
stability or a trust boundary. Ordinary per-container validation remains the baseline and a valid selected outcome.

**Experiments and gate.** Select bounded prototypes based on the source-backed comparison and record why other
alternatives are deferred. Measure image preparation, service/worker startup, first and subsequent request durations,
copy/distribution overhead, native preparation build commands, discovery probes and bytes hashed. Report individual
measurements and distributions, keeping one-time setup costs separate and showing how worker lifetime affects their
amortization. Record selection/native keys, all metadata differences and artifact versus validation-record reuse at each
tested lifecycle boundary.

Exercise fresh containers, worker/runtime restarts, changed images and mounts, toolchain updates, altered inputs, stale
or unavailable evidence and read-only consumers as applicable to each prototype. Verify compilation and program output
separately from timing. Preserve the original evidence and place reproducible commands, configuration, source references
and results in a new attachment. Decide whether a recommended mechanism fits ADR-0039 or needs an ADR amendment/new ADR
before adopting it. An immutable-toolchain authority remains a separate explicit architecture decision requiring
independently enforced identity and mutation controls; successful cache copying or faster timings cannot establish it.

**Correctness requirements.** Preserve normal validation and fallback behavior. Memos remain accelerators under
ADR-0039, never self-authenticating authority. Untrusted requests and executed programs must not publish or modify
prepared support or evidence trusted by later requests. Enforce ownership and mount/process isolation, including
staging/publication paths, and verify that worker reuse does not carry request-written state into trusted preparation.
Read-only consumers must handle unavailable memo writes without treating stale evidence as valid; changed inputs still
invalidate or fail under existing policy. Any required compiler interface or validation-contract change must be
identified and decided explicitly rather than assumed by the deployment recipe.

**Completion criteria.** Produce a source-backed comparison, reproducible evidence for selected prototypes and a
recommended deployment recipe or explicit deferral with rationale and remaining questions. Report achievable artifact
and validation reuse, latency, setup/storage costs, operational complexity, isolation requirements and unavailable
configurations. Resolve the authority decision for the selected or deferred outcome. Building a production service or
prototyping every alternative is not required. Do not describe an experiment as a general cache-portability guarantee.

## Phase 4: Reduce Discovery and Unavoidable Hashing Costs

**Hypothesis.** Even after evidence reuse improves, fresh or invalidated configurations still spend material time in
discovery and hashing. These mechanisms need independent experiments and decisions.

**Discovery approach and alternatives.** Investigate finer-grained invalidation and targeted rechecking of affected
search decisions. Compare that approach with retaining whole-observation invalidation while reducing repeated dependency
probe work, including safe batching or reuse where configurations permit it. Preserve dependency coverage for every
runtime translation unit and all generated-C configurations; do not collapse distinct runtime and generated-C policies.
Use external profiling to separate process startup from probe work where feasible.

**Hashing approach and alternatives.** Benchmark an optimized portable SHA-256 implementation and platform acceleration
against the current implementation on the observed large libraries and representative small files. Retain the current
backend if alternatives do not justify their cost. Separate hash computation from file access where feasible, using
in-memory/streaming controls as well as end-to-end reads. Decide using measured consumer improvement, supported-platform
availability, dependency burden, build integration, and maintenance cost.

**Experiment and gate.** Run cold-evidence and partial-invalidation cases with discovery and hashing changes isolated,
then combined if justified. Include Clang's LLVM/Clang/Z3 libraries and GCC's `cc1`. Report probe startup/work evidence,
hash throughput and byte counts, and end-to-end distributions without adding nested timings to preparation spans. Select
or defer each mechanism independently; resolve the hash-backend policy record before adopting a backend.

**Correctness requirements.** Test standard SHA-256 vectors, empty and boundary-sized inputs, streaming chunk
boundaries, identical digests across backends, changed content, partial/failed reads, and stable-read rejection.
Preserve input coverage and failure handling. Discovery tests must catch newly introduced search candidates, changed
generated-C branches and runtime sources, partial invalidation, and unavailable observations. Reject speedups that
weaken evidence.

**Completion criteria.** Record a measured and portable choice for each mechanism, including deferred alternatives. All
accepted implementations produce identical identities/artifact digests and preserve invalidation and diagnostics. Update
documentation for any selected backend policy and discovery architecture.

## Phase 5: Attribute Remaining Warm-Build Time

**Hypothesis.** Most warm compiler elapsed time is outside preparation and cannot be explained by preparation counters.
Useful attribution will identify the next optimization target without guessing which compilation phase dominates.

**Preferred approach.** Add debug-only timings for interface loading, application analysis, C generation, C compilation,
and linking, with explicit inclusive/exclusive meanings and nesting relationships to existing preparation spans. Retain
normal output and existing counter/record meanings. Do not sum overlapping parent and child durations.

**Alternatives and gate.** Start with coarse compiler spans and add detail only where measurements justify it. Use
external profiling instead of permanent instrumentation where it answers the question adequately. Record which approach
explains the substantial residual, its overhead, and any remaining uninstrumented boundaries such as wrapper startup.

**Experiment.** Compare paired instrumented/noninstrumented warm builds, with capture to container-local storage and
separate log export. Use both compilers and representative imported applications. Preserve failures and partial timing
records. Controlled clocks verify accounting and nesting; runtime comparisons assess overhead without test thresholds.

**Correctness requirements.** Instrumentation must not alter provider selection, compilation, linking, preparation
policy, or ordinary output. Preserve existing preparation observations and failure diagnostics. New debug measurements
must remain distinguishable from broader subprocess duration.

**Completion criteria.** Substantial time outside preparation has useful attribution and a measured follow-up
recommendation. Document residual uncertainty and overhead. Implementing every optimization subsequently suggested by
profiling is not a completion requirement.

## Future Validation and Documentation

Run focused preparation identity/support/ownership, managed-consumer/provider, observability, and reporter tests as each
phase changes their behavior. Cover cache absence/malformation, force, failed probes/reads, corrupt completed artifacts,
partial observations, reporter timeout preservation and scenario isolation. Test relevant filesystem aliases and
metadata behavior on Linux, macOS, and Windows, with supported compiler/backend coverage; report unavailable cases
explicitly.

After focused checks, run L1 normal validation (`make -C l1 test`) and relevant ARC/memory trace coverage, starting with
`make -C l1 test-stage1-trace-smoke` and broadening according to ownership changes and the subtree rules. Repeat the
Docker matrix with the same resource constraints, multiple independent pairs, output verification outside compilation
timing, and debug/nondebug controls. Compare distributions and operation counts rather than imposing real elapsed-time
thresholds in correctness tests. Record image/runtime identity and distinguish fresh containers from cold filesystems.

Update the preparation reference, provider/CLI documentation where affected, and accepted ADRs only when the relevant
implementation decisions are made. Keep reporter semantics and timing nesting documented. Before closure, resolve each
ADR record, include required ADR amendments/new records and plan backlinks, and update the roadmap/lifecycle location.

For this draft and its attachments, validate JSON parsing and recursive equality after the documented string-only
sanitization, reconcile table/count values with JSON, scan for private names/local user paths/source revision
identifiers, resolve all repository links, and run active-plan ADR, Markdown, and whitespace checks.

[investigation]: attachments/2026-09-24-preparation-reuse-efficiency/investigation.md
[logging-control]: attachments/2026-09-24-preparation-reuse-efficiency/logging-control-report.json
[measurements]: attachments/2026-09-24-preparation-reuse-efficiency/report.json
[observability]: closed/2026-09-24-preparation-observability-noref.md
[phase-one]: attachments/2026-09-24-preparation-reuse-efficiency/phase1/results.md
[phase-two]: attachments/2026-09-24-preparation-reuse-efficiency/phase2/results.md
[preparation]: ../../../docs/reference/stdlib-preparation.md
[reuse-boundary]: ../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[semantic-authority]: ../../../docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md
