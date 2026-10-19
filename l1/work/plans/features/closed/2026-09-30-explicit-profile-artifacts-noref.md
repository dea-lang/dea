# Feature Plan

## Create and consume explicit L1 profile artifacts

- Date: 2026-10-19
- Status: Completed
- Title: Add caller-owned L1 profiles with `--create-profile` and `--profile PATH`
- Kind: Feature
- Priority: Medium
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Targets:
  - Canonical L1: Completed
- Subsystem: Native support artifacts, CLI selection, compilation and linking
- Depends on: `l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md`
- Modules: `l1/compiler/src/cli_args/`, `preparation.l0`, `preparation/`, build/compile/link drivers, `source_paths.l0`,
  `l1/compiler/support/preparation/profile.h` and native context lifetime support.
- Test modules: `cli_args_test.l0`, `preparation_test.l0`, `l1c_help_output_test.py`, `l1c_profile_test.py`,
  `l1c_profile_variants_test.py`, `preparation_profile_test.py` and existing managed/installed preparation suites.

## Outcome and scope

Implemented `--create-profile -o PATH` and `--profile PATH` for compile, link, build and run in canonical L1. Creation
uses the shared constructor without managed identity, cache lookup or persistent-reuse admission. Selection restores one
recorded configuration before frontend/native preflight, uses the exact profile inventory and copied headers/runtime,
and never repairs, substitutes, prepares or writes managed state. Ordinary commands retain their managed policy.

The manual composition fixture compiles a leaf, dependent provider, side-effect module and entry in a fixed order,
imports bundled `std.io`, supplies a C lifecycle observer through the existing foreign-object surface, links and runs.
Its behavior and applicable module-C bytes agree with both convenient profile-backed build/run and ordinary managed
composition. Explicit `-I` precedence and invalid-provider failure remain intact. Retained C excludes prebuilt profile
providers.

Phase B of [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative] is complete. Managed-client
integration, dependency discovery, compiler Make conversion, L2 adoption and arbitrary-project stdlib construction
remain separate work. No release, artifact-distribution or remote publication action was performed.

## ADR Impact

- Decision: Publish a caller-owned profile and consume an exact artifact independently of managed cache policy.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0044-explicit-profile-artifact-authority.md`
  - Rationale: The public format, compatibility, construction, ownership and strict selection contract is shared with
    the parent initiative and recorded in ADR-0044.
- Decision: Distinguish caller-owned external toolchain stability from managed automatic freshness.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Explicit selection validates payload bytes without reconstructing the compiler/DLL observations needed
    for managed reuse; the caller owns suitable stable external dependencies.
- Decision: Select explicit provider/header/runtime authority without changing ordinary bundled discovery.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: Only the opt-in selector replaces installation discovery with profile inventory.
- Decision: Retain authoritative semantic interfaces and opaque native inputs in profile-backed linking.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md`
  - Rationale: Digests detect damage relative to trusted metadata, without authenticating native semantics or inferring
    arbitrary ABI compatibility.
- Decision: Extend the flag-based CLI with one L1 mode and one selector.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI contract registers the L1 extension without changing L0/L2 behavior or existing meanings.

## Settled artifact and configuration contract

The normative specification is [l1/docs/reference/explicit-profiles.md][profiles]. Public `profile.json` schema 1 uses
Dea compilation contract 1, independently of managed manifests and content keys. Required fields are `schema`, `kind`,
`contract`, `producer`, `configuration`, `include`, `modules`, `runtime` and `payloads`. Compiler descriptions are
optional provenance, not freshness authority. The compilation contract must change for incompatible
interface/fingerprint, generated ABI, header/runtime or lifecycle/wrapper protocols.

Store the absolute selected compiler, ordered effective generated-C argv, separate runtime argv, runtime variant and all
five codegen booleans. Copy the complete public-header tree and preserve sibling interfaces/objects and exact runtime
archive/TinyCC object order. Payload paths are contained relative paths with roles, sizes and digests. Bound manifests,
argv, inventory counts, JSON structure and directory traversal; reject unsupported schema/contract, inconsistent
variants, undeclared files, aliases and damaged consumed inputs before host work.

Recognized native path options become absolute external references. Single-letter include/search options permit joined
forms; multi-letter short path options require separate operands. Reject response/configuration files, selected implicit
compiler configurations, opaque forwarding, sysroot placeholders, unsupported joined path forms and native
output/dependency controls instead of reinterpreting them after a cwd change. Relative includes and forced headers
retain their selected meaning when the profile moves. The caller maintains the external compiler, SDK, environment and
referenced files.

CLI provenance distinguishes omissions from explicit controls. Omitted settings inherit; explicit settings must
normalize to the recorded values without alternate compiler identity probes. Ambient compiler, C flags, system/runtime
roots and cache variables cannot redirect selection. Explicit system/runtime/cache overrides are rejected with the
selector.

Creation rejects existing, unsafe or protected-input-overlapping outputs before mutation. It constructs in exclusive
sibling staging, tracks source/runtime/header stability, validates inventory, writes completion metadata last and
publishes to an absent destination. Cleanup removes only registered contents and retains unexpected evidence. Consumers
cannot write outputs, retained-C trees or temporary workspaces inside the selected profile. Trusted-parent and external
same-destination serialization boundaries remain explicit.

Registered `L1C-2180` through `L1C-2185` for CLI/configuration controls, destinations, manifests, payloads,
contract/configuration or output/temp conflicts, and publication/cleanup. `L1C-2186` through `L1C-2199` remain reserved.
Existing semantic and native compilation diagnostics retain their meanings.

## Verification

Validation tier: exhaustive canonical L1 coverage, including the broad normal suite, relevant native/integration tests,
environment/bootstrap, ownership traces and child fixtures. New context/string/container lifetimes, resolved runtime
configuration and compiler/linker control flow justify trace coverage. This is neither example-only nor a
delivery-layout change. Existing normal results were reused; corrected help and host-access-dependent identity checks
were rerun directly, and only missing aggregate categories were run afterward.

- Normal discovery including CI-only cases: `make -o venv test-ci`, with explicit supported compiler selections. The
  normal suite accounted for 93 cases: 91 initial passes, followed by passing focused replays for help and native
  identity. The stale help assertion was updated for the new help surface. The native identity check required host
  access to its existing macOS `sysctl` probe and was replayed with that access.
- Final focused compiler cases:
  `make -o venv -o build test-compiler TESTS="l1c_profile_test l1c_profile_variants_test preparation_profile_test"`,
  plus help replay and the final read-only/composition assertions. Automatic Python discovery and the existing explicit
  subject-compiler helpers register the new shared integration cases. New L0 ownership cases extend `preparation_test`.
- Remaining normal aggregates: `make -o venv -o build -o test-compiler -o test-docgen test-ci` reused normal/docgen
  results and passed example, tooling and productization fixture gates. Environment/bootstrap was replayed with shared
  uv-cache access, then full canonical and child traces were run through their direct targets.
- Native ownership: `make -o venv -o build test-compiler-trace TESTS="cli_args_test preparation_test"` passed with zero
  leaked object/string pointers. The complete canonical trace sweep passed all 48 default-discovered cases with zero
  leaked object/string pointers; both child-runtime trace fixtures passed with zero leaks. The existing slow-case
  discovery policy remains unchanged.
- Linux GCC: repo-owned `make docker CMD=test-compiler DOCKER_CC=gcc` with the five focused profile/preparation/CLI
  selectors passed positives; the final negative fixture was replayed after correcting its interference with legacy
  Clang configuration-isolation probes. No production change was required for that fixture correction.
- Native option/ownership matrix covers default/basic/unchecked/traced profiles, real TinyCC raw objects, a
  reuse-ineligible invocable compiler wrapper, normalized relative paths, cwd changes, read-only moved profiles with
  original bundled inputs absent, poisoned ambient selectors, invalid explicit providers, corruption/version/path
  failures, output/temp guards, existing/protected destinations, native/publication failures and retained unexpected
  evidence.
- Native Windows lexical branches were compiled from production helper bodies and exercised with drive/UNC paths, mixed
  separators, spaces, case, prefix collisions and distinct-drive/share negatives. This is simulation, not native Windows
  filesystem/compiler validation.
- Finalization runs root staged whitespace, ADR Impact and pre-commit checks before the local commit.
- Additional aggregate results: 46 doc-generator checks, 4 examples, 181 tooling checks (1 platform skip), 289
  productization fixture checks (14 platform/capability skips), and environment/bootstrap integration passed.

Actual native environments: macOS Intel `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`); `/usr/local/bin/tcc`,
TinyCC 0.9.28rc; repo-owned Linux container `/usr/bin/gcc`, Debian GCC 12.2.0. The negative config fixture also
exercises installed Debian Clang 14.0.6 capability isolation. Native Windows and macOS ARM execution were unavailable
locally; simulation and Linux/macOS Intel results do not establish that coverage. Hosted workflows were not dispatched.

Informational hash scope/cost: one macOS profile contained 49 payloads totaling 487637 bytes. Fresh description load
plus compile-mode verification took 30.1 ms with 50 payload-content reads; native-mode verification took 24.8 ms with 74
reads on the subsequently warm filesystem. Both recorded zero identity-content reads, native resolutions, probes, native
build commands and module compiles. These single measurements describe integrity work, not a performance comparison or
an external freshness guarantee. No persistent validation memo was added.

[initiative]: ../../../initiatives/0010-explicit-profiles-and-composable-builds.md
[profiles]: ../../../../docs/reference/explicit-profiles.md
