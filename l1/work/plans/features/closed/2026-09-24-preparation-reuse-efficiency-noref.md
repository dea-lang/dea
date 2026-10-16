# Feature Plan

## Improve preparation reuse efficiency

- Date: 2026-10-16
- Status: Completed
- Title: Improve L1 preparation reuse efficiency using attributed validation costs
- Kind: Feature
- Priority: Medium
- Subsystem: Managed providers / native preparation / validation memos / compiler timing
- Modules:
  - `l1/compiler/src/cli_args.l0`
  - `l1/compiler/src/cli_args/model.l0`
  - `l1/compiler/src/cli_args/parse.l0`
  - `l1/compiler/src/cli_args/help.l0`
  - `l1/scripts/build_l1c.py`
  - `l1/compiler/src/preparation/consumer.l0`
  - `l1/compiler/src/source_paths.l0`
  - `l1/compiler/src/build_driver.l0`
  - `l1/compiler/support/preparation_support.c`
  - `l1/compiler/support/compiler_support.c`
  - `l1/compiler/support/preparation/identity.h`
  - `l1/compiler/support/preparation/storage.h`
  - `l1/compiler/support/preparation/platform.h`
  - `l1/compiler/support/preparation/sha256.h`
  - `l1/compiler/src/util/timing.l0`
  - `l1/compiler/src/analysis.l0`
  - `l1/compiler/src/driver/resolve.l0`
  - `l1/compiler/src/backend.l0`
  - `l1/compiler/src/compile_driver/compile.l0`
  - `l1/compiler/src/link_driver/toolchain.l0`
  - `l1/scripts/check_preparation_reuse.py`
- Test modules:
  - `l1/compiler/tests/cli_args_test.l0`
  - `l1/compiler/tests/source_paths_test.l0`
  - `l1/compiler/tests/l1c_bootstrap_interfaces_test.py`
  - `l1/compiler/tests/l1c_help_output_test.py`
  - `l1/compiler/tests/preparation_identity_test.py`
  - `l1/compiler/tests/preparation_support_test.py`
  - `l1/compiler/tests/preparation_ownership_test.py`
  - `l1/compiler/tests/preparation_identity_windows_environment_test.py`
  - `l1/compiler/tests/preparation_observability_test.c`
  - `l1/compiler/tests/preparation_digest_seed_test.c`
  - `l1/compiler/tests/preparation_dependencies_test.c`
  - `l1/compiler/tests/timing_test.l0`
  - `l1/compiler/tests/compiler_timing_support_test.py`
  - `l1/compiler/tests/l1c_managed_preparation_test.py`
  - `l1/compiler/tests/l1c_preparation_test.py`
  - `l1/compiler/tests/l1c_installed_preparation_test.py`
  - `l1/compiler/tests/preparation_reuse_report_test.py`
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

This standalone plan completed five phases. Equivalent bundled-root recognition and disposable digest-seed hints
preserve managed providers and validated content evidence while keeping discovery cwd-sensitive. The container-reuse
research made no metadata-policy or deployment-architecture decision. Phase 4 adopts measured Apple Clang dependency
batching on macOS and retains the existing portable SHA-256 backend after the compared candidates missed their
consumer/integration gates. Phase 5 adds debug compiler spans and a portable private clock, attributing the substantial
majority of measured warm time. Native Windows validation remains unavailable.

Historical experiment data remains unchanged; the original investigation's parent link is maintained for this archival
move. New phase reports record the accepted and deferred outcomes separately. Reproduction recipes restore the measured
support sources only inside owned copies; current Clang configuration-isolation policy remains enabled in production.

## ADR Impact

- Decision: Recognize an explicitly selected bundled root without losing managed providers, with an explicit source-use
  compatibility policy.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: Phase 1 replaces unconditional explicit-root suppression with filesystem-identity recognition and the
    `--no-managed-stdlib` opt-out. ADR-0038 records that compatibility decision; ADR-0033 delegates its
    provider-selection wording to that contract.
- Decision: Share validated file digest records across cwd selections through a disposable donor hint, retaining
  cwd-sensitive discovery.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Phase 2 adds a best-effort locator for existing machine-local evidence. Donor records retain the same
    metadata checks, force behavior and live search dependencies; discovery is never copied. ADR-0039 records the
    bounded lookup and failure policy without a new authority or cwd-independence proof.
- Decision: Choose a portable SHA-256 backend and any platform-acceleration/dependency policy.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Phase 4 retains dependency-free portable C SHA-256 after the direct-block and round-unrolled candidates
    missed the predeclared consumer gates. Platform acceleration remains deferred pending supported-platform
    integration, failure cleanup and consumer measurements; digest bytes, stable-read validation and metadata policy
    remain unchanged.
- Decision: Reduce discovery process startup while preserving the existing observation invalidation boundary.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Phase 4 batches complete generated-C and runtime dependency groups independently for measured Apple Clang
    on macOS, accepts only complete source coverage and retains individual-probe fallback. Other adapters and
    finer-grained persisted observations remain deferred.

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
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/results.md][phase-one]. The later
phases are recorded below.

## Phase 2: Separate Digest Reuse from Discovery Selection

**Status.** Completed on 2026-09-24 for the validated macOS/Linux configurations. Native Windows execution was
unavailable. Validation and measurement results are recorded in the
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase2/results.md][phase-two]. The later
phases are recorded below.

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

**Status.** Completed on 2026-09-25 as a successful investigation, accepting the experimental results and their stated
limits. The relaxed candidate demonstrated the intended toolchain-digest reuse mechanism and measured first-request
benefits while preserving the tested discovery and artifact-validation boundaries. The same-size, preserved-mtime
content-change detection gap and unresolved warm-performance findings remain part of the evidence, not blockers to
closing this investigation. No decision was made to adopt or reject metadata-policy relaxation. The candidate remains an
isolated experimental patch; unchanged production behavior does not constitute a policy decision.

**ADR disposition: ADR not warranted.** This completed investigation introduced no architectural contract or policy
decision. No decision was made to adopt or reject metadata-policy relaxation, establish a new authority boundary or
select a deployment architecture. Any future adoption requires a separate decision and ADR assessment. The former
pending Phase 3 record is therefore removed from ADR Impact; the other phases retain their existing records.

**Closure scope.** Deployment selection, untested alternatives and any adoption decision are deferred beyond this
completed phase. Historical attachments remain unchanged, including their then-current references to Phase 3 or its ADR
decision as pending. This completion record supersedes those lifecycle statements without changing their findings.

**Investigation results (2026-09-25).** A bounded Linux Docker comparison built one prepared compiler image, then
derived representative service images through inheritance and selective copying. Both retained completed GCC/Clang
native profiles and the same native keys; each fresh container repeated discovery and substantial hashing before a
second request reused refreshed memos. The original wrapper moved the prepared cache to a different path and found no
artifact memo at runtime. Subsequent inspection found that preparation alone had created no artifact memo in that image,
so the original miss cannot be assigned solely to the path move. Preserve the [first image results][phase-three-image]
as evidence of that copy scenario.

A [same-path rerun][phase-three-same-path] held the cache at `/opt/dea/l1/cache-template` and created GCC/Clang artifact
memos through build-time validation. All three images contained and selected those memos in fresh containers, but
per-artifact inode mismatches still forced hashing; a `/bin` inode mismatch also invalidated build-time toolchain
observation evidence. Completed profiles were reused, second requests hashed zero bytes in the measured categories, and
malformed optional evidence fell back to validation. Operation counts matched across packaging variants, while the
small, changed-condition timing sample cannot rank them. Worker lifetime, runtime evidence distribution, shared storage
and deployment authority were not settled by those experiments; they are deferred beyond this completed investigation.

A [complete-metadata subset][phase-three-metadata] rebuilt those same three image variants with multi-field observations
and ran one fresh GCC and Clang container per variant. In every first request, all 47 prepared-artifact mismatches
included `inode`, `ctime`, `ctime_ns` and `mtime_ns`; the latter changed from a nonzero build-time value to zero at
runtime. Dea inputs, toolchain inputs and the `/bin` dependency also changed `inode` and both change-time fields, with
`mtime_ns` changing for some paths. No mismatch reported a changed `device`, size, mode, whole-second `mtime` or
reliability flag. Each second compilation reused refreshed evidence without metadata mismatches or hashing. This
identifies the simultaneous metadata changes, but does not isolate which Docker/filesystem transition caused them or
make an architecture or policy decision.

An isolated experiment, recorded in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md][phase-three-relaxed],
compared the strict baseline with a candidate that ignores device, inode and change time only for selected regular
toolchain-file digests. Across five interleaved repetitions of all three images and both compilers, all 60 containers
and 120 requests passed. Candidate first requests hashed only 6,591 toolchain bytes from `/etc/ld.so.cache`, while
strict discovery still rejected `/bin` evidence and performed the same probes. Dea-input and prepared-artifact
validation remained strict, and each request reused its own image-time profile. Median paired first-request time
improved by 16.3-23.6% for GCC and 47.2-51.7% for Clang. Warm-time results did not establish absence of a regression.
Focused tests demonstrated both the scope boundaries and the accepted same-size, preserved-mtime content-change
detection gap. The patch remains experimental; the report recommends a separate best-effort policy discussion rather
than changing the strict default. That recommendation remains historical experimental analysis; phase closure does not
adopt or reject it. Production behavior is unchanged, and this investigation made no policy decision.

**Scope examined.** The selected experiments compared image inheritance and selective copying, corrected cache-path and
memo-presence confounds, exposed complete metadata differences, and tested a scoped relaxation of toolchain-file digest
reuse. They distinguish reuse of compiled artifacts from reuse of validation evidence and retain reproducible commands,
source references, individual measurements, distributions, correctness checks and limitations. The results establish the
tested mechanism and costs, not a general cache-portability guarantee or a production deployment recipe.

**Deferred alternatives and decisions.** Startup-warmed workers, runtime evidence distribution and shared read-only
storage were not prototyped. A broader deployment comparison is deferred because the accepted experiments complete this
bounded investigation without selecting an architecture. Future work on those alternatives would need to measure worker
lifetime, restart/update behavior and evidence distribution, and establish request isolation, cache ownership and
failure recovery. The private writable container layer used here is an experimental control, not an adopted service
setting.

Any future metadata-policy adoption discussion must separately assess the demonstrated content-change detection gap,
warm-request performance and deployment trust assumptions. These questions remain undecided; they do not reopen Phase 3
or become implicit requirements for Phases 4 and 5. Existing production contracts remain in effect without being newly
selected or reaffirmed by this experiment. No production service, compiler interface, validation policy or architectural
contract was introduced by closing the phase.

## Phase 4: Reduce Discovery and Unavoidable Hashing Costs

**Status.** Completed on 2026-10-16. Discovery batching is enabled only for measured Apple Clang on macOS, with
individual-probe fallback. Other adapters retain individual probes. The SHA-256 backend decision is resolved: production
hashing remains unchanged after portable and platform comparisons.

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

### Phase 4 implementation and backend decision (2026-10-16)

Keep whole-observation invalidation. Apple Clang on macOS batches four generated-C dependency configurations separately
from all ten runtime translation units. Complete source-rule coverage is required before accepting any evidence;
unavailable, malformed, failed, timed-out or oversized batches fall back to individual probes. Full identities and
content coverage stay equal. Actual quiet consumers reduced cold medians from 5.318 to 4.402 seconds (17.2%) and partial
invalidation from 3.486 to 2.647 seconds (24.1%). Outer probes fell from 28 to 16. No warm speedup is claimed. Linux
results did not justify adoption; external process observation showed that Clang multi-source commands can add frontend
processes. Finer-grained persisted invalidation remains deferred pending per-query search provenance.

Retain dependency-free portable C SHA-256. The direct-block candidate remained mixed. Eight-round compression unrolling
improved aggregate large-file Linux hashing by 15.9%, but actual Clang cold medians improved only 102.258 ms (3.66%),
below the predeclared 150 ms gate; GCC improved 2.653 ms (0.19%). Both failed qualification within five fixed pairs, and
no further pairs were added. Platform libraries showed large-file headroom but small-file setup costs and unresolved
supported-platform, dependency and failure-cleanup policy. Standard/boundary/streaming digests and stable-reader failure
checks passed across the compared implementations. No hashing change was selected for a combined experiment.

The discovery and hash mechanisms were evaluated independently. Detailed methods, individual samples, distributions,
coverage, limitations and reproduction are in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-results.md][phase-four-discovery],
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-results.md][phase-four-hash],
and
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-portable-results.md][phase-four-portable].

## Phase 5: Attribute Remaining Warm-Build Time

**Status.** Completed on 2026-10-16. Compiler instrumentation, independent reporter parsing and the private host-clock
ABI are implemented. Controlled/native clock tests and the timing ownership trace pass. The final Linux matrix includes
112 successful warm builds and output checks with numeric timings; the initial unavailable-clock experiment is retained
separately without an attribution claim.

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

### Phase 5 implementation and attribution decision (2026-10-16)

Coarse debug-only compiler spans use a separate schema-1 record stream, preserving preparation observations and ordinary
output. Interface loading is nested within load/resolve; application analysis, C generation, module/wrapper C commands
and linking have documented boundaries. Durations use a compiler-private host clock so strict-C99 Linux builds do not
depend on bootstrap runtime feature-test macros. Unavailable, backward or overflowing clocks remain explicit null
durations. Nondebug commands collect no clocks or span allocations.

Seven interleaved pairs for two imported applications and GCC 14/Clang 19 explain median 76.1-82.5% of warm command
time. Interface loading costs 168-291 ms and is the largest measured frontend component; native compilation/linking also
contributes materially. C generation costs 2-7 ms. The residual 17.5-23.9% remains unlocalized. Median paired overhead
across cases is +0.94% quiet and +0.65% debug, with wide individual variation; these shared-host samples establish no
small overhead bound or absence of regressions. The next frontend investigation should profile interface
reading/parsing/fingerprint validation before choosing reuse. No application cache or deployment architecture is
adopted.

See [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/results.md][phase-five] for
complete boundaries, individual measurements, distributions, failure evidence, reproduction and unavailable native
Windows coverage. The timing trace passes with zero leaked object/string pointers. Linux GCC/Clang and Apple Clang pass
direct strict-C99 clock checks; extracted POSIX/QPC error/range probes pass ASan/UBSan as explicitly simulated evidence.
Retained control-source patches and the construction/measurement script reproduce the experimental source relation and
commands; the report distinguishes recovered build defaults and unavailable historical argv from captured evidence.

## Validation and Documentation

Commands ran from `l1/` with an explicit existing L0 bootstrap and `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` selecting
`/usr/bin/clang`, Apple Clang 17.0.0. Linux reports separately verify GCC 14.2.0 and Clang 19.1.7 inside their actual
containers. Native Windows and macOS ARM performance coverage were unavailable; synthetic Windows path/clock checks do
not substitute for native validation.

- `make test-extended` passed 80 normal compiler tests, 46 docgen tests, four examples, six Docker/Wine runner tests,
  181 tooling tests (one platform skip) and 289 productization fixtures (14 platform skips). This broad gate preceded
  the final adapter guard and private-clock compatibility refinement.
- Final `make build` verified all 23 bundled interfaces. `make -o build test` reused that rebuilt compiler and passed
  all eight representative compiler tests plus the aggregate's docs, examples, runner, tooling and product fixtures.
- Final
  `compiler/scripts/run_tests.py l1c_preparation_test.py l1c_installed_preparation_test.py compiler_timing_support_test.py timing_test`
  passed all four checks, including force/recovery, immutable installed inputs and the live native clock ABI.
- Complete preparation identity coverage passed, including changed headers for every runtime unit/generated-C branch,
  negative candidates and partial invalidation. Final scoped Apple Clang and Linux GCC dependency fixtures passed; Apple
  Clang ASan/UBSan and full-identity equality checks cover the narrowed batching policy.
- The six trace-smoke cases plus `driver_test` and `backend_test` passed with zero leaked object/string pointers. Final
  `timing_test` trace passed with 186 events and zero leaks. `preparation_ownership_test.py` passed automatic compiler
  selection and runtime-override ownership paths.
- Fifteen reporter tests passed. Phase reports retain cold/partial/warm output checks, failures, operation counts,
  nonoverlapping accounting and the documented JSON projection/sanitization/equality evidence. No wall-time thresholds
  were added to correctness tests.

The preparation reference records scoped discovery batching, the retained hash policy, compiler observation schemas and
nesting. ADR-0038 and ADR-0039 link to this closed plan and record the final provider, digest-sharing, discovery and
hash choices. The roadmap records completion. Active/staged ADR, Markdown, copyright and whitespace checks cover the
final archival change. No remote write, deployment or publication is part of this work.

[investigation]: ../attachments/2026-09-24-preparation-reuse-efficiency/investigation.md
[logging-control]: ../attachments/2026-09-24-preparation-reuse-efficiency/logging-control-report.json
[measurements]: ../attachments/2026-09-24-preparation-reuse-efficiency/report.json
[observability]: 2026-09-24-preparation-observability-noref.md
[phase-five]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase5/results.md
[phase-four-discovery]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-results.md
[phase-four-hash]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-results.md
[phase-four-portable]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-portable-results.md
[phase-one]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase1/results.md
[phase-three-image]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase3/results.md
[phase-three-metadata]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase3/metadata-details/results.md
[phase-three-relaxed]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md
[phase-three-same-path]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase3/same-path/results.md
[phase-two]: ../attachments/2026-09-24-preparation-reuse-efficiency/phase2/results.md
[preparation]: ../../../../docs/reference/stdlib-preparation.md
[reuse-boundary]: ../../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[semantic-authority]: ../../../../docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md
