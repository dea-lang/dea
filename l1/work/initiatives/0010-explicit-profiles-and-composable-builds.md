# L1 Initiative 0010 - Explicit Profiles and Composable Builds

- Version: 2026-10-21
- Status: In progress
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-10-21-semantic-dependency-discovery-noref.md`
- Closed plans:
  - `l1/work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md`
  - `l1/work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md`
  - `l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md`
  - `l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md`
- Scope: L1 canonical L1 compiler
- Subsystem: Profile construction, native preparation, compiler driver and external build integration

## Summary

Preserve the convenient `l1c --build` and `l1c --run` workflows while making their preparation and compilation
operations explicitly composable. Introduce a caller-owned profile artifact, separate from the managed cache used to
find and reuse profiles automatically.

Start with a behavior-preserving internal extraction. Follow it with a bounded feature that creates a profile at an
explicit destination and consumes it through existing compile, link, build and run modes. Do not begin a general build
system, a new package manager, or a rewrite of the compiler bootstrap.

This initiative records the direction agreed in the September 30 design discussion and reviewed against the repository
on October 1. Phase A is complete: the internal constructor accepts frozen inputs and a caller-owned destination. Phase
B implements the public artifact contract and exact compile/link/build/run selection. Phase C is complete: managed,
command-private and explicit creation share configuration projection, and managed/public readers share payload checks
under separate authority. Phase D is drafted as a P1689R5 dependency report followed by an external Make adapter, with
separate discovery and compilation inputs.

## Compiler-lineage placement

Complete this work in canonical L1 first, then carry the accepted implementation forward into L2 under a later scoped
change. This split does not implement or advance profiles/composable builds and adds no dependency on them. Former
paired-stage compatibility scenarios now refer to canonical L1 producer/consumer consistency, not a second L1 compiler.

## ADR Impact

- Decision: Treat a profile as an explicit compilation-support artifact and a cache as a separate lookup, storage and
  automatic-reuse policy.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0044-explicit-profile-artifact-authority.md`
  - Rationale: The distinction determines ownership, CLI composition and the responsibilities of future build tools. The
    profile artifact ADR is shared with the feature plan. The shared CLI ADR amendment is separately owned by that plan.
- Decision: Keep managed freshness validation while giving explicit profile selection a separately stated caller-owned
  stability contract.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Skipping managed selection is an opt-in change of responsibility, not proof that external toolchain
    mutation can be detected without observation. Existing managed guarantees remain in force.
- Decision: Choose the minimum dependency-discovery interface needed for external orchestration.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The Phase D feature plan selects P1689R5 scheduling facts and an external Make consumer, retaining
    existing provider authority through separate discovery and compilation inputs. The new ADR is shared with that plan
    and will record the delivered contract at closure.

## Current State

The proposal was drafted against public `dea-lang/dea`, branch `main`, on 2026-09-30 and rechecked against the local
worktree on 2026-10-01. Recheck current sources before each implementation phase. The current architecture is documented
in [l1/docs/reference/architecture.md][architecture] and [l1/docs/reference/stdlib-preparation.md][preparation].

The compiler already has per-module generation, `.o + .l1m` compile-only output, standalone verified linking and a
source-graph build/run pipeline. Managed preparation already produces complete internal native profiles. Explicit
profiles now provide a public artifact boundary independent of the cache's identity, location and selection machinery.
Phase C shares construction inputs and payload mechanics while retaining managed policy. Phase D will expose semantic
dependency information.

`--prepare-stdlib` explicitly prewarms a persistently reusable managed entry. It is not a caller-directed artifact
constructor. Automatic build/run/link can instead construct fresh command-private support when persistent reuse is
unavailable. `--no-auto-prepare` prevents construction, but does not eliminate managed selection and validation.

The running compiler's own linked runtime is distinct from the runtime it constructs for generated programs. Rebuilding
the stdlib with a running compiler is not, by itself, a circular build dependency. Retain today's semantic bootstrap
initially; a new minimal bootstrap seed is not a prerequisite for this initiative.

## Decisions and Invariants

| Concept               | Contract                                                                                                                                |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Profile               | One complete set of bundled module interfaces/objects, public headers and matching runtime support for a selected native configuration. |
| Profile construction  | Build that artifact at a caller-selected destination. Cache reuse is not its defining operation.                                        |
| Profile selection     | Use exactly the artifact named by `--profile PATH`, or fail. Never substitute or repair it implicitly.                                  |
| Managed cache         | Locate and retain reusable artifacts using managed identity, validation and coordination policy.                                        |
| Primitive compilation | Preserve `.l1 -> .o + .l1m` and verified `.o + .l1m -> executable` contracts.                                                           |
| Convenience build     | Compose the same implementation operations without requiring a Makefile or explicit profile.                                            |

The selected vocabulary is `--create-profile` as a primary mode and `--profile PATH` as a selector. Retain the current
flag-based CLI grammar. Do not introduce `--use-profile`, `--prepare-system`, subcommands, or a second executable in
this initiative.

An explicit profile is immutable by usage contract after publication. It is not an immutable snapshot of the operating
system, external compiler, SDK, loader dependencies or environment. A manifest records configuration and provenance; it
cannot prove that those external inputs remain unchanged. The caller owns that stability in the explicit path.

The managed path continues to own automatic freshness decisions under
[l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-adr]. Neither a successful explicit
build nor an explicit-profile manifest authorizes a managed cache hit.

## Implementation Sequence

### Phase A: Isolate the existing construction boundary

Completed in [l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md][boundary-plan].

The shared constructor consumes frozen native/frontend inputs, a verified semantic dependency order and an already owned
staging destination, and returns a validated payload inventory. Managed and command-private callers use that same
implementation. Cache identities, eligibility, lookup, locks, publication and completion metadata remain with the
managed caller. External behavior, cache formats, diagnostics and default policies are preserved.

This independently closed refactor adds no public manifest or CLI mode. Host, container and cross-platform validation
results are recorded in the closed plan.

### Phase B: Introduce explicit profile artifacts

Implemented by [l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan] after Phase
A's construction boundary.

Creation and compile/link/build/run selection share the existing constructor, frontend and verified linker. The
fixed-order composition fixture verifies application providers, bundled imports, foreign inputs, lifecycle order and
applicable retained-C bytes. Ordinary managed behavior remains covered by its existing regression suites.

Explicit consumers use one resolved configuration and the profile's provider inventory without rereading ambient native
defaults or consulting the original bundled source directory. The feature's success criterion is an explicit build that
does not consult a managed cache, not an immediate reduction in all filesystem reads. Profile-payload integrity checks
and ordinary host compilation remain legitimate work.

### Phase C: Make managed reuse a client of the public artifact construction model

Completed in
[l1/work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md][managed-client-plan]. Managed,
command-private and explicit creation use one resolved configuration projection; managed and public inventory readers
share payload checks beyond the constructor already shared by Phases A and B. Cache-specific manifests, memos, locks,
identity and freshness policy remain separate. Native macOS Intel validation and simulated Windows path checks passed;
the project maintainer also confirmed passing Unified CI on 2026-10-21, providing native L1 `test-ci` coverage on Linux
x86_64 GCC, macOS Intel/ARM64 Clang and Windows UCRT64 GCC, as recorded in the closed plan.

The managed adapter retains the existing internal layout; the private cache directory convention is not the public
profile format. Any later storage change must state cold-start behavior and legacy-entry handling explicitly; no silent
migration or pruning is authorized here.

Review whether a cache-output locator is useful only after there is a stable artifact consumers can use. Debug logs are
not a machine-readable API, and no public print/export mode is required by the first two plans.

### Phase D: Expose only the missing semantic dependency information

Drafted in [l1/work/plans/features/2026-10-21-semantic-dependency-discovery-noref.md][dependency-plan]. Produce a
neutral P1689R5 scheduling report through the existing resolver and graph order, then add an external Make adapter.
Essential scheduling information belongs in core fields; Dea annotations must remain optional. Distinguish first-build
discovery from compilation-time reporting of actual consumed interfaces, which is deferred from the initial conservative
adapter.

Discovery receives project source roots and intentionally prebuilt interface roots. Compilation adds the local
generated-interface root after updating providers and checking that residual interfaces cannot shadow selected prebuilt
providers. V1 rejects such conflicts with clean/fresh-root guidance instead of pruning outputs. Standalone linking
explicitly selects the scanned canonical target as its entry. An output destination never implicitly becomes an input
root. Keep the existing interface-first policy; accidentally supplying old local outputs during discovery is an
integration error, not a reason to introduce source-over-interface precedence.

A graph export must preserve explicit provider precedence, source versus interface origins, import edges and ordered
roots. Incremental integration must account for semantic dependency closure, configuration changes, provider shadowing,
source additions/removals and the two-output publication rule. A public fingerprint alone is not necessarily a complete
rebuild dependency signature. Timestamp-only Make rules will still rebuild consumers when unchanged interface bytes are
republished with a new timestamp; solving that is separate from merely emitting a depfile.

Use a small external Make fixture to demonstrate discovery, dependency-ordered compile calls and standalone linking. Do
not serialize every native command into a new build-plan execution language. P1689R5 is selected for the report; CLI
spellings and the adapter contract are proposed defaults in the draft plan, not shipped behavior.

## CLI Migration Policy

Keep `--prepare-stdlib`, `--stdlib-cache`, `L1_STDLIB_CACHE`, `--no-auto-prepare` and preparation-only `--force` working
during the initial migration. They still serve managed-cache operations. They are not aliases for profile creation or
selection.

`--create-profile -o PATH` constructs an explicit artifact. `--prepare-stdlib` ensures a reusable managed cache entry.
These are different operations, so replacement is not a one-for-one rename. Only a later migration decision may
deprecate or rename existing controls, after prewarming, cache-location selection and cache-miss refusal have
replacement workflows.

Ordinary build/run/link without `--profile` retain their existing behavior. With `--profile`, they never discover,
create, repair or silently substitute managed support.

## Scope and Deferred Work

No language syntax, ownership semantics, ABI mangling, lifecycle ordering, native object inspection or public stdlib API
changes are included. Preserve the canonical L1 semantic/diagnostic contract while retaining its reviewed L1 idioms.

Production Make-managed compiler builds, changing the canonical L1 L0 bootstrap, ordinary-project stdlib construction,
treating the stdlib as an arbitrary third-party package, profile distribution, cross-host reuse, cross-toolchain ABI
compatibility, cache eviction and a native backend are outside this initiative's completion requirements. Production
compiler and stdlib adoption follow the relevant delivered foundations as separately scoped work. Profile selection in
`--check`, `--gen` and `--emit-interface` is deferred beyond the initial plans and is not an initiative completion
requirement.

Do not restart hashing or metadata-policy experiments as a dependency of the profile work. Coordinate touching changes
with [l1/work/plans/features/closed/2026-09-24-preparation-reuse-efficiency-noref.md][efficiency-plan], without adopting
its unselected alternatives. Keep legacy compiler compatibility work independently owned; this initiative must not
become their prerequisite or claim their results.

## Completion Criteria

The first two plans may close without waiting for Phases C and D. The initiative closes only after all four phases are
implemented: the construction boundary, explicit artifacts, managed integration and semantic dependency discovery.
Deferring a required phase leaves the initiative active. Phases A through C are complete; implement and verify the
bounded Phase D draft for semantic dependency discovery and external Make composition.

Completion also requires both the manual composition fixture and the dependency-discovery integration fixture to pass,
every ADR Impact record to be resolved, and roadmap, initiative membership and current CLI/reference documentation to
agree. Reuse the L1 profile ADR established by the feature plan and maintain its related-plan links at initiative
closure.

A valid completion must demonstrate the same program behavior, provider authority, lifecycle semantics and applicable
module-C identity through explicit and managed composition. Do not require byte-identical native executables across
arbitrary host toolchains or identical retention inventories when one workflow consumes prebuilt providers.

Maintain [l1/docs/roadmap.md][roadmap] and the parent/open/closed links as each child plan advances. Phases A through C
record their implementation and verification in their respective closed plans; Phase D is unimplemented. Drafting and
local implementation do not authorize remote writes, releases or workflow dispatches.

[architecture]: ../../docs/reference/architecture.md
[boundary-plan]: ../plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md
[dependency-plan]: ../plans/features/2026-10-21-semantic-dependency-discovery-noref.md
[efficiency-plan]: ../plans/features/closed/2026-09-24-preparation-reuse-efficiency-noref.md
[managed-client-plan]: ../plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md
[preparation]: ../../docs/reference/stdlib-preparation.md
[profile-plan]: ../plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md
[reuse-adr]: ../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[roadmap]: ../../docs/roadmap.md
