# Feature Plan

## Improve preparation reuse efficiency

- Date: 2026-09-24
- Status: Draft
- Title: Improve L1 preparation reuse efficiency using attributed validation costs
- Kind: Feature
- Severity: Medium
- Stage: 1
- Subsystem: Managed providers / native preparation / validation memos / performance measurement
- Modules:
  - `l1/compiler/stage1_l0/src/preparation/consumer.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/compiler/stage1_l0/support/preparation/platform.h`
  - `l1/compiler/stage1_l0/support/preparation/sha256.h`
  - `l1/scripts/check_preparation_reuse.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_windows_environment_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_observability_test.c`
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

This standalone plan organizes five implementation phases within one work item. This draft and its attachments preserve
evidence and describe future work; they do not change compiler behavior, accepted ADRs, cache formats, or CLI semantics.
Unresolved designs remain subject to explicit evidence and compatibility gates.

## ADR Impact

- Decision: Recognize an explicitly selected bundled root without losing managed providers, with an explicit source-use
  compatibility policy.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: ADR-0038 deliberately preserves explicit system-root suppression. The intended bundled-root change must
    amend that provider-selection contract after the Phase 1 compatibility gate; this draft does not amend it yet.
- Decision: Share digest evidence across discovery selections and define any safe cwd-independent observation reuse.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Phase 2 must choose an evidence index and discovery boundary while preserving ADR-0039's machine-local
    accelerators, reliable metadata/stable reads, force behavior, and live search dependencies. Its final architecture
    and ADR disposition remain unresolved; see
    [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary].
- Decision: Define the authority and isolation boundary for evidence distributed across Docker requests.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Phase 3 must establish whether runtime memo distribution fits ADR-0039's local-evidence constraints or
    needs a separately enforced immutable-toolchain contract. Copied/shared portability is currently unsupported, and
    untrusted requests cannot establish authority; see
    [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary].
- Decision: Choose a portable SHA-256 backend and any platform-acceleration/dependency policy.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Phase 4 must compare identical-output backends and their platform/maintenance costs. ADR-0039's content
    coverage and stable validation boundary remain constraints; faster hashing cannot substitute weaker identity
    evidence. The backend choice and final ADR disposition remain open; see
    [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary].

## Evidence and Current State

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
  reuse. This is current deliberate behavior under ADR-0038, so changing it requires a compatibility decision.
- A different cwd changes discovery and input-memo selection without changing the native key. The first such Clang
  invocation hashes 240,347,792 toolchain bytes; the next becomes warm.
- Fresh containers reject image-baked directory and file inode evidence. Revalidation retains the native key.
- Fresh Clang toolchain hashing takes 1.596 seconds median, with another 1.046 seconds in nested discovery probes. These
  are components of its preparation spans, not additional time to add to them.
- Artifact hashing and copying are smaller costs in this sample. About 0.494 seconds for GCC and 0.604 seconds for Clang
  remain outside the warm preparation spans and are not yet attributed to compilation phases.

## Goals and Boundaries

Recognize equivalent bundled-root selections, reuse valid content evidence across discovery selections, test runtime
evidence distribution, reduce measured discovery/hash costs, and attribute substantial remaining warm time. Preserve
content identity, completed-profile validation, explicit interface authority, source ordering, eligibility refusal,
stable-read checks, corruption detection, and force behavior unless an explicit design decision changes a documented
contract.

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

## Phase 2: Separate Digest Reuse from Discovery Selection

**Hypothesis.** A discovery-selection change need not discard previously validated file digests. With absolute inputs, a
cwd change can require discovery while still reusing reliable machine-local content evidence.

**Preferred approach.** Introduce versioned machine-local digest evidence reusable across discovery selections. Reuse
requires the existing reliable metadata and stable-read checks. Preserve force revalidation, malformed-evidence
fallback, file replacement detection, eligibility refusals, and all input coverage. Digest reuse must never authorize
skipping a search decision that needs reobservation.

**Alternatives and gate.** Compare a separately indexed digest store with a bounded secondary index over existing memo
evidence. Measure lookup cost, storage growth and reclamation needs, concurrent writers, atomic publication/recovery,
schema/version compatibility, and maintenance complexity. Do not scan unrelated memos on the ordinary path. Select a
representation only after these measurements and a correctness review of the identity boundary in ADR-0039.

Then separately investigate cwd-independent observation reuse for supported configurations whose effective inputs are
demonstrably unchanged. An unchanged native key after reobservation is evidence for that experiment, not permission to
skip discovery. Retain cwd sensitivity where relative options, response files, environment search paths, implicit
configuration, or unresolved indirection affect selection. Conservative reobservation remains the fallback.

**Experiment.** Repeat the changed-cwd pair with absolute source/project paths. First measure digest sharing while
retaining discovery; then compare any justified observation-sharing design. Track keys, per-file reasons, hash bytes,
probe purposes, storage, and total time separately. Include relative response-file contents and nested paths,
environment search roots, newly shadowing candidates, replaced compiler binaries/libraries, malformed evidence, force,
and concurrent writers.

**Correctness requirements.** Reuse must preserve effective native identity and all live search-dependency checks.
Metadata failures and unstable reads cannot silently authorize a cached digest. Changed relative inputs and newly
introduced candidates must reselect/revalidate correctly; unsupported configurations remain ineligible. No cross-host or
metadata-preserving-mutation guarantee is introduced by a new evidence index.

**Completion criteria.** Absolute-input cwd changes retain the native identity and avoid unnecessary hashing while all
invalidation tests pass. Decide separately whether observation reuse is justified, deferred, or restricted to a proven
subset. Document evidence versioning, concurrency, and bounded storage behavior, together with measured costs.

## Phase 3: Reuse Runtime-Validated Evidence Across Docker Requests

**Hypothesis.** Runtime-validated evidence may be reusable by subsequent isolated containers when their observed
filesystem identity is stable, avoiding repeated rejection of image-build metadata.

**Preferred experiment.** In a controlled trusted setup, validate the installed toolchain once in the runtime filesystem
and distribute the resulting evidence read-only to fresh request containers. Each consumer performs normal metadata
checks and falls back to ordinary validation when evidence does not match. Keep request outputs and writable state
separate from the evidence supplied to later requests.

**Alternatives and gate.** Retain per-container validation if filesystem identity is unstable or distribution costs
outweigh the benefit. Alternatively, design an immutable-toolchain authority supplied by a trusted deployment system in
a separate explicit architecture decision. Such a contract needs independently enforced identity and mutation controls;
successful memo copying or faster timings cannot establish it. Decide whether any supported distribution mechanism fits
the local-cache contract or needs an ADR amendment/new ADR before implementing it.

**Experiment.** Compare multiple fresh containers against an ordinary per-container baseline, runtime restarts, changed
images, changed mounts, altered inputs, stale evidence, and read-only consumers. Record first metadata differences,
selection/native keys, probe counts, hash bytes, copy/distribution costs, and total durations. Include evidence
validation and distribution setup separately so their cost is not hidden.

**Correctness requirements.** Memos remain accelerators under ADR-0039, never self-authenticating authority. Untrusted
executed programs must not publish or modify evidence consumed by subsequent requests. Enforce that boundary through
ownership and mount/process isolation, including staging/publication paths. Read-only consumers must handle unavailable
memo writes without treating stale evidence as valid; changed inputs still invalidate or fail under existing policy.

**Completion criteria.** Record whether runtime identity survives each tested lifecycle boundary and quantify actual
reductions in probes/hashing. Select a correct mechanism with an explicit authority decision, or retain per-container
validation with documented negative evidence. Do not describe an experiment as a general cache-portability guarantee.

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
[preparation]: ../../../docs/reference/stdlib-preparation.md
[reuse-boundary]: ../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[semantic-authority]: ../../../docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md
