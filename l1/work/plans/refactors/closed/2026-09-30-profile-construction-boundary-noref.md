# Refactor Plan

## Isolate profile construction from managed preparation policy

- Date: 2026-10-01
- Status: Completed
- Completed: 2026-10-01
- Title: Isolate the L1 profile construction boundary without changing managed behavior
- Kind: Refactor
- Severity: Medium
- Stage: Shared
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Targets:
  - L1 Stage 1: Completed
  - L1 Stage 2: Completed
- Subsystem: Native preparation, destination ownership and shared construction
- Modules:
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/compiler/stage1_l0/src/preparation/frontend.l0`
  - `l1/compiler/stage1_l0/src/preparation/consumer.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage2_l1/src/preparation.l1`
  - `l1/compiler/stage2_l1/src/preparation/frontend.l1`
  - `l1/compiler/stage2_l1/src/preparation/consumer.l1`
  - `l1/compiler/stage2_l1/src/build_driver.l1`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/support/preparation/`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_test.l0`
  - `l1/compiler/stage2_l1/tests/preparation_test.l1`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_construction_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/preparation/construction.l0`
  - `l1/compiler/stage2_l1/tests/fixtures/preparation/construction.l1`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
  - `l1/tests/test_stage2_tooling.py`
- Related:
  - [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative]
  - [l1/work/plans/features/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan]
  - [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][economy-plan]
- Repro: From `l1/`, exercise explicit preparation plus cold, warm, forced and private-fallback native consumers.

## Summary

The refactor exposes one internal construction operation underneath preparation policy. Its inputs describe what to
build and an already owned staging destination. Its result describes the constructed payload. Cache selection,
persistent reuse eligibility, locks and publication ownership remain with the caller.

This plan adds no CLI option and no public profile format. It prepares the smallest useful implementation boundary for
the subsequent feature, without promising a broad source decomposition or changing the existing native service ABI
beyond what the extraction needs.

## ADR Impact

- Decision: Preserve bundled semantic authority and destination lifetime while separating construction from selection.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: The refactor reorganizes existing ownership; semantic inputs, private fallback and user workflows are
    unchanged. The ADR links this closed plan.
- Decision: Preserve identity coverage, native configurations and conservative managed reuse eligibility.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: The extracted constructor does not decide whether outputs may be reused automatically. Existing policy
    still makes that decision before managed reuse and publication.
- Decision: Preserve completed-profile validation as the managed warm-hit evidence.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0040-warm-preparation-semantic-validation-reuse.md`
  - Rationale: This change must not put bundled frontend validation back onto the unchanged warm path.

## Starting State

Before extraction, the construction path was
`pr_prepare -> pr_build_selected -> pc_begin_profile -> pr_frontend_prepare -> pc_complete_profile`. Preparation context
supplied the destination and configuration; native writers and completion depended on managed identity,
locks/private-root state and completion metadata. The frontend reread merged C options for each module. A wrapper around
`pr_build_selected` alone could not provide explicit construction without cache state.

The preserved contract and earlier economy findings are recorded in
[l1/docs/reference/stdlib-preparation.md][preparation] and
[l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][economy-plan].

## Goal and Non-Goals

The goal is one construction implementation callable from both the existing managed/private paths and a future
caller-directed artifact path. Keep configuration normalization explicit and retain separate generated-stdlib and
runtime C configurations.

Do not add a public manifest, new command, cache schema, background process, dependency scanner, generic task scheduler,
ABI compatibility classifier or new hashing algorithm. Do not change native toolchain support, installed-layout policy,
compiler selection defaults, runtime flags, diagnostic codes or the default build workflow.

## Defaults Chosen

The policy caller owns cache identity, eligibility, lookup, locks, destination allocation, persistence, publication,
managed completion metadata and replacement. The constructor owns only registered construction scratch and payload
production within its supplied destination. Consumers borrow the result for a declared lifetime; they never take
ownership of a cache entry accidentally.

Normalize construction configuration once per command and pass the selected compiler, ordered effective generated-C
options, separate runtime options, frontend code-generation settings, semantic inputs and header inputs explicitly.
Construction must not reread `L1_CFLAGS`, compiler selection or runtime defaults after receiving that configuration.
Reuse existing records when they suffice. A new owned record is justified only where it removes ambient lookups or
lifetime ambiguity; no speculative object hierarchy is required.

The native support remains compiler-private. Do not introduce public stdlib facilities to perform this extraction. Use
shared in-process calls, not recursively spawned `l1c` commands.

## Implementation Phases

### Phase 1: Pin behavior and map responsibilities

Record the live call graph from `pr_prepare` through `pr_build_selected`, the frontend constructor and native support
completion. Identify which probes are required to execute construction and which observations exist to authorize
persistent reuse. Include native writer/completion dependencies and repeated configuration reads such as
`bd_collect_c_option_words` in that inventory. Record the constructor's reads, writes and owned paths in this plan's
implementation notes.

Extend focused tests only where a boundary is currently unobserved. Cover cold preparation, an unchanged warm hit,
explicit prewarming, force, persistent ineligibility with successful private construction, corruption and storage
failure. Use a fixed supported toolchain and matching fixtures for comparisons.

Exit gate: the current behavior is reproducible and the proposed seam can be stated without changing cache policy. If
that requires a new public artifact contract, stop the extraction at the existing boundary and carry that part into the
feature plan rather than expanding this refactor.

### Phase 2: Extract the constructor and destination ownership

Move the minimal construction inputs out of implicit selection state. Give the constructor an already owned staging
root, immutable configuration for this invocation, the verified semantic set/dependency order and public header inputs.
Return an owned payload description or a failure with retained-path information.

Leave cache-key computation, lookup, lock/recheck, persistent refusal and fallback selection outside this operation.
Separate payload production and validation from managed manifest serialization and publication; the managed adapter
retains the existing manifest and identity rules. Remove cache-lock/private-root assumptions from the construction write
authorization in favor of the supplied owned destination. Do not remove input validation or capability checks needed for
correct construction. Keep their scheduling in the existing managed path unchanged unless equivalence is directly
demonstrated. This extraction does not add a public profile format or change managed reuse admission.

Document success and failure ownership: who removes scratch, who publishes, who releases a private directory and who
keeps recovery evidence. Publication remains the existing operation; this phase must not accidentally claim atomic
reader snapshots, crash durability or general concurrent replacement.

Exit gate: a focused internal fixture reaches construction through explicit normalized inputs and an owned destination
without inventing a cache entry or reuse identity. Verify that later ambient-default changes do not alter the supplied
configuration. The fixture uses the same implementation as the existing path and leaves no leaked owners or unregistered
scratch.

### Phase 3: Reconnect managed and command-private callers

Route the existing callers through the extracted boundary, preserving warm-hit short circuits, single-command native
resolution, lock/recheck order, private-support lifetime and diagnostic precedence. Preserve the just-in-time binding of
managed native artifacts without changing authoritative semantic origins.

Retain current cache storage and manifest formats. Changes to compiler inputs naturally change the content-derived
identity; tests must compare policy and work counts, not demand that a rebuilt compiler retain the old literal key. No
identity-input dependency may be dropped merely to make a test reuse an old entry.

Implement paired Stage 1 and Stage 2 behavior in the same change set, preserving Stage 2's reviewed L1 idioms. Keep the
C service shared and avoid another stage-specific copy.

Exit gate: both stages preserve observable behavior, applicable generated-C identity and the established ownership and
cache-reuse regressions.

### Phase 4: Validate and close the bounded refactor

Run focused preparation, native-support, provider/link and Stage 2 tooling tests first. Then run the required aggregate,
trace and strict bootstrap checks for the affected ownership paths. Update current architectural documentation only for
the internal boundary that actually landed; future profile commands remain documented only in the draft feature plan.

Close this plan independently of the feature. Update the initiative's membership, ADR Related Plans links and roadmap
references in the same change. No profile feature is implied by closure.

## Verification Criteria

| Scenario                                            | Required observation                                                                                                                     |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Unchanged managed warm request                      | No profile construction or complete bundled frontend revalidation; no new repeated native resolution.                                    |
| Direct construction fixture                         | Explicit inputs and owned destination suffice without a cache identity; later ambient defaults do not change the supplied configuration. |
| Cold or forced request                              | Same normalized stdlib/runtime configurations and payload inventory, with existing diagnostics and completion rules.                     |
| Invocable but persistently ineligible configuration | Existing explicit prewarm refusal and successful automatic private fallback remain distinct.                                             |
| Explicit provider or runtime override               | Existing precedence and preparation avoidance remain unchanged.                                                                          |
| Corruption, lock contention and storage failure     | Existing recheck, recovery, fallback and retained-evidence behavior is preserved.                                                        |
| Failure and cleanup                                 | No owned allocation or registered scratch leak; private support survives through its last consumer.                                      |
| Stage parity                                        | Stage 1 and Stage 2 exercise the same cases and preserve diagnostics and applicable generated-C bytes.                                   |

Use work counts and attributed timings, not unmeasured speedup claims. Retain before/after cold and warm measurements
when a changed boundary may add work, and investigate any unexplained regression. Do not introduce a new performance
threshold without evidence.

From `l1/`, the final implementation validation includes the applicable focused suites, `make test-extended`, relevant
ownership cases through both `test-stage1-trace` and `test-stage2-trace`, and `make triple-test`. Explicitly select
`TESTS="l1c_stage1_preparation_test l1c_stage1_installed_preparation_test"` with each of `make test-stage1` and
`make test-stage2`; these shared integration cases are excluded from normal discovery by the CI-only policy.
`make test-ci` is the exhaustive hosted-equivalent gate, not an additional repeat of already covered validation.

Exercise the repo-owned Linux Docker path with GCC, and supported Windows/macOS paths when available. Verify actual
compiler executable/version in each environment under [l1/AGENTS.md][l1-agents]. An unavailable platform is an explicit
coverage gap, not a passing result. Existing evidence may be reused only under the repository's current validation
rules.

## Implementation Notes

The landed path keeps resolution, lookup, complete miss validation, eligibility, lock/recheck and fallback in
`pr_prepare`. `pc_begin_profile` allocates the selected destination and invalidates its managed completion marker, then
projects resolved inputs into `pc_begin_construction`. `pr_construct` passes the frozen code-generation settings and C
options through frontend generation; native copy/compile/runtime operations consume the same `PcConstruction` snapshot.
`pc_finish_construction` returns the owned payload inventory. Only `pc_complete_profile` checks managed input freshness,
serializes the existing manifest, validates it and publishes it.

`l1c_prep_construction_create` accepts normalized internal JSON inputs and an already owned directory directly. It does
not resolve toolchain paths, default options, a cache root, `D`, `N`, locks or reuse evidence. The existing context is
reused only as an error/statistics and ownership carrier. Paired frontend fixtures exercise this entry through the same
`pr_construct` implementation; no public CLI or artifact format was added.

Windows native probes observe process exit before draining stdout/stderr, preserving output written during termination.
This prevents missing compiler observations from incorrectly declining persistent reuse. Native test failures retain the
eligibility refusal reason.

| Responsibility                 | Owner and inputs                                                                                                                                                                                                                                                      |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Native execution prerequisites | The policy caller resolves the executable family, runtime target options, archiver and required capabilities before construction, preserving the existing schedule.                                                                                                   |
| Persistent reuse observations  | Dea/native identities, image and dependency observations, option eligibility, memos, lookup and lock/recheck remain outside construction. No identity dependency was removed.                                                                                         |
| Constructor reads              | Explicit compiler/archiver, generated options, separate runtime options/variant, frontend settings, source and semantic roots, module set, verified interface digests, public-header root and dependency order. No repeated `bd_collect_c_option_words` in this path. |
| Constructor writes             | Declared `modules/` and `lib/` payload roles plus registered `generated/` and `runtime-build/` scratch beneath the supplied root. Parent aliases escaping that root are refused before directory creation.                                                            |
| Result and failure ownership   | Construction owns copied inputs, expected roles and the completed inventory; its root is borrowed. Failure retains the root/partial evidence without a complete inventory. Runtime temporary objects are cleaned; generated C remains optional evidence.              |
| Destination and publication    | The caller owns allocation, managed metadata, publication, replacement and eventual directory removal. Managed private support remains live through its final consumer. No new atomic-reader, durability or replacement guarantee is claimed.                         |

### Verification Evidence

Local validation used `/usr/bin/gcc`, Debian GCC 14.2.0, with `L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`. Both stages'
preparation, direct construction, managed-provider, recovery/concurrency and installed-layout tests passed. Direct cases
cover ambient-default isolation, exact semantic copies, real module/runtime commands, invalid configuration, incomplete
payloads, changed interfaces, escaped/undeclared writes, native failure and retained caller-owned paths.

Isolated before/after snapshots used the same GCC and sequential
`--prepare-stdlib --c-compiler /usr/bin/gcc --stdlib-cache PATH -vvv` calls for a cold entry, unchanged warm entry and
`--force`. Times are individual observations, not a speedup claim or a new performance threshold:

| Case   | Before seconds | After seconds | Module compiles | Native commands | Native resolutions | Complete bundled validations |
| ------ | -------------- | ------------- | --------------- | --------------- | ------------------ | ---------------------------- |
| Cold   | 4.448          | 4.538         | 23 / 23         | 33 / 33         | 1 / 1              | 1 / 1                        |
| Warm   | 0.017          | 0.019         | 0 / 0           | 0 / 0           | 1 / 1              | 0 / 0                        |
| Forced | 4.644          | 4.416         | 23 / 23         | 33 / 33         | 1 / 1              | 1 / 1                        |

Native probes remained 43/1/43 and artifact reads 47/47/47. Cold/forced identity content reads increased from 294 to 295
because the new construction header is an identity input; warm identity content reads remain zero. No literal cache-key
equality was required across rebuilt compiler inputs. Payload roles and semantic interface bytes match. All 23 generated
C modules match after substituting only the isolated snapshot root in source-line directives.

Cold native-resolution spans were 0.462/0.479 seconds and warm spans 0.010/0.011 seconds. Total attributed hashing was
0.243/0.245 seconds cold, 0.003/0.003 warm and 0.259/0.251 forced. The small wall-time differences do not correspond to
extra compilation, probing or warm frontend work. Payload-inventory hashing now precedes the managed-publication span;
its hash observations retain the existing `publication` category, so the shorter publication span is not a speedup.

Local `make test-extended`, native identity and optional-selection ownership checks passed. Both stages' direct
constructor traces (`L1_CONSTRUCTION_TRACE=1`) and dedicated preparation/link-driver traces reported zero errors or
leaked objects/strings on the covered success and failure paths. `make triple-test` produced 137 identical retained C
translation units and identical normalized native binaries; the final compiler's tests, examples and smoke test passed.

Hosted `make test-ci` passed on all four platforms below, covering both stages, native storage, construction, ownership
traces and strict triple bootstrap. The Windows native fixture deterministically verifies final stdout/stderr capture,
compiler eligibility and exit-status query failure with real child processes. ADR impact validation passed. Compiler
executables and versions were verified in each environment:

| Platform              | Compiler executable | Version                                     |
| --------------------- | ------------------- | ------------------------------------------- |
| Linux x86_64          | `/usr/bin/gcc`      | GCC 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| Windows UCRT64 x86_64 | `/ucrt64/bin/gcc`   | GCC 16.2.0 (MSYS2 Rev4)                     |
| macOS Intel           | `/usr/bin/clang`    | Apple Clang 17.0.0 (clang-1700.0.13.5)      |
| macOS ARM64           | `/usr/bin/clang`    | Apple Clang 21.0.0 (clang-2100.1.1.101)     |

The repo-owned Linux Bookworm container passed `make test-extended` with `/usr/bin/gcc`, GCC 12.2.0 (Debian
12.2.0-14+deb12u1), selected by `L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`. Coverage included 79 Stage 1 tests, 65 Stage 2
tests, stage parity, all four examples, six Docker/Wine runner checks and 18 Stage 2/bootstrap tooling tests.

## Diagnostics and Documentation

No diagnostic identifiers are added or reassigned. Existing preparation, compile and link errors keep their meanings.
Recheck [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] if implementation reveals a genuinely new failure
category; move that feature-bearing change to the dependent plan rather than silently extending this refactor.

Maintain [l1/docs/reference/architecture.md][architecture] and [l1/docs/reference/stdlib-preparation.md][preparation] as
needed for landed ownership changes. Preserve current user instructions and command examples.

Run `python3 scripts/check_adr_impact.py --all-active` while planning, and the staged ADR, whitespace and required root
pre-commit checks before any implementation commit.

## Dependencies and Authorization

Coordinate overlapping edits with the active preparation-efficiency and Stage 2 source-review work. This refactor does
not authorize their deferred optimizations, legacy-toolchain changes or a Makefile conversion.

Remote pushes, tags, releases, workflow dispatches and deployments are outside this plan. Any such operation requires
its own fresh authorization under `AGENTS.md`; writing or implementing this plan is not that authorization.

[architecture]: ../../../../docs/reference/architecture.md
[diagnostics]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[economy-plan]: 2026-09-12-native-preparation-economy-noref.md
[initiative]: ../../../initiatives/0010-explicit-profiles-and-composable-builds.md
[l1-agents]: ../../../../AGENTS.md
[preparation]: ../../../../docs/reference/stdlib-preparation.md
[profile-plan]: ../../features/2026-09-30-explicit-profile-artifacts-noref.md
