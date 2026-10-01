# L1 Initiative 0010 - Explicit Profiles and Composable Builds

- Version: 2026-10-01
- Status: Draft
- Kind: Initiative
- Open plans:
  - `l1/work/plans/refactors/2026-09-30-profile-construction-boundary-noref.md`
  - `l1/work/plans/features/2026-09-30-explicit-profile-artifacts-noref.md`
- Closed plans: (none)
- Stage: Shared
- Scope: L1 Stage 1 and Stage 2
- Subsystem: Profile construction, native preparation, compiler driver and external build integration

## Summary

Preserve the convenient `l1c --build` and `l1c --run` workflows while making their preparation and compilation
operations explicitly composable. Introduce a caller-owned profile artifact, separate from the managed cache used to
find and reuse profiles automatically.

Start with a behavior-preserving internal extraction. Follow it with a bounded feature that creates a profile at an
explicit destination and consumes it through existing compile, link, build and run modes. Do not begin a general build
system, a new package manager, or a rewrite of the compiler bootstrap.

This initiative records the direction agreed in the September 30 design discussion and reviewed against the repository
on October 1. Its detailed contracts and child plans remain drafts, not descriptions of implemented features. All new
command examples below are proposed syntax.

## ADR Impact

- Decision: Treat a profile as an explicit compilation-support artifact and a cache as a separate lookup, storage and
  automatic-reuse policy.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The distinction determines ownership, CLI composition and the responsibilities of future build tools.
    Create the eventual profile ADR in the L1 decision directory and share it with the feature plan. The shared CLI ADR
    amendment is a separate decision owned by that plan.
- Decision: Keep managed freshness validation while giving explicit profile selection a separately stated caller-owned
  stability contract.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Skipping managed selection is an opt-in change of responsibility, not proof that external toolchain
    mutation can be detected without observation. Existing managed guarantees remain in force.
- Decision: Choose the minimum dependency-discovery interface needed for external orchestration.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: A later, separately scoped plan must choose between a semantic graph export and any associated depfile
    support after the profile path supplies concrete integration evidence. No spelling is selected here.

## Current State

The proposal was drafted against public `dea-lang/dea`, branch `main`, on 2026-09-30 and rechecked against the local
worktree on 2026-10-01. Recheck current sources before each implementation phase. The current architecture is documented
in [l1/docs/reference/architecture.md][architecture] and [l1/docs/reference/stdlib-preparation.md][preparation].

The compiler already has per-module generation, `.o + .l1m` compile-only output, standalone verified linking and a
source-graph build/run pipeline. Managed preparation already produces complete internal native profiles. What is missing
is a public artifact boundary independent of the cache's identity, location and selection machinery.

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

Execute [l1/work/plans/refactors/2026-09-30-profile-construction-boundary-noref.md][boundary-plan].

Separate explicit construction inputs, an owned staging destination and the resulting payload from managed lookup,
eligibility and storage policy. Native writes and completion currently depend on cache/private-directory state, so a
wrapper around `pr_build_selected` alone is insufficient. Keep managed identities, locks, publication policy and
completion metadata with the managed caller while the managed and private paths share construction. Preserve all
external behavior, cache formats, diagnostics and default policies.

This is the first implementation tranche. It must be independently useful and independently closable. Do not add a
public manifest or CLI mode during this refactor.

### Phase B: Introduce explicit profile artifacts

Execute [l1/work/plans/features/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan] only after Phase A's
boundary is verified.

The first vertical slice is `--create-profile` plus `--link --profile`, using objects produced by existing compile-only
mode. The next slice extends the selector to compile-only, build and run, followed by a small explicit composition
fixture. Each slice must keep the ordinary managed path working.

Explicit consumers use one resolved configuration and the profile's provider inventory without rereading ambient native
defaults or consulting the original bundled source directory. The feature's success criterion is an explicit build that
does not consult a managed cache, not an immediate reduction in all filesystem reads. Profile-payload integrity checks
and ordinary host compilation remain legitimate work.

### Phase C: Make managed reuse a client of the public artifact construction model

Spawn a bounded refactor plan after Phase B establishes the artifact contract. Reuse the same normalized configuration,
constructor and payload validation logic; keep cache-specific manifests, memos, locks and identity policy separate.

An adapter around the existing internal layout is acceptable before any cache-format change. Do not expose the private
cache directory convention as the public profile format. Any later storage change must state cold-start behavior and
legacy-entry handling explicitly; no silent migration or pruning is authorized here.

Review whether a cache-output locator is useful only after there is a stable artifact consumers can use. Debug logs are
not a machine-readable API, and no public print/export mode is required by the first two plans.

### Phase D: Expose only the missing semantic dependency information

Spawn a feature plan for compiler-produced dependency discovery. Reuse the existing resolver and graph order, not a
second source parser. Distinguish first-build discovery from compilation-time reporting of actual consumed interfaces.

A graph export must preserve explicit provider precedence, source versus interface origins, import edges and ordered
roots. Incremental integration must account for semantic dependency closure, configuration changes, provider shadowing,
source additions/removals and the two-output publication rule. A public fingerprint alone is not necessarily a complete
rebuild dependency signature. Timestamp-only Make rules will still rebuild consumers when unchanged interface bytes are
republished with a new timestamp; solving that is separate from merely emitting a depfile.

Use a small external build fixture to demonstrate discovery, dependency-ordered compile calls and standalone linking. Do
not serialize every native command into a new build-plan execution language. Exact names and formats remain unchosen.

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
changes are included. Preserve Stage 1 as the semantic/diagnostic oracle and implement paired Stage 2 behavior while
retaining its reviewed L1 idioms.

Production Make-managed compiler builds, changing Stage 1's L0 bootstrap, ordinary-project stdlib construction, treating
the stdlib as an arbitrary third-party package, profile distribution, cross-host reuse, cross-toolchain ABI
compatibility, cache eviction and a native backend are outside this initiative's completion requirements. Production
compiler and stdlib adoption follow the relevant delivered foundations as separately scoped work. Profile selection in
`--check`, `--gen` and `--emit-interface` is deferred beyond the initial plans and is not an initiative completion
requirement.

Do not restart hashing or metadata-policy experiments as a dependency of the profile work. Coordinate touching changes
with [l1/work/plans/features/2026-09-24-preparation-reuse-efficiency-noref.md][efficiency-plan], without adopting its
unselected alternatives. Keep the active Stage 2 source review and legacy compiler compatibility work independently
owned; this initiative must not become their prerequisite or claim their results.

## Completion Criteria

The first two plans may close without waiting for Phases C and D. The initiative closes only after all four phases are
implemented: the construction boundary, explicit artifacts, managed integration and semantic dependency discovery.
Deferring a required phase leaves the initiative active. Open the bounded Phase C and Phase D plans when their
prerequisites are established; their detailed interfaces do not block Phase A.

Completion also requires both the manual composition fixture and the dependency-discovery integration fixture to pass,
every ADR Impact record to be resolved, and roadmap, initiative membership and current CLI/reference documentation to
agree. Reuse the L1 profile ADR established by the feature plan and maintain its related-plan links at initiative
closure.

A valid completion must demonstrate the same program behavior, provider authority, lifecycle semantics and applicable
module-C identity through explicit and managed composition. Do not require byte-identical native executables across
arbitrary host toolchains or identical retention inventories when one workflow consumes prebuilt providers.

Update [l1/docs/roadmap.md][roadmap] when opening this initiative, and maintain the parent/open/closed links as each
child plan advances. No implementation result, user review of exact text, or successful validation is claimed by this
draft. Drafting and local implementation do not authorize remote writes, releases or workflow dispatches.

[architecture]: ../../docs/reference/architecture.md
[boundary-plan]: ../plans/refactors/2026-09-30-profile-construction-boundary-noref.md
[efficiency-plan]: ../plans/features/2026-09-24-preparation-reuse-efficiency-noref.md
[preparation]: ../../docs/reference/stdlib-preparation.md
[profile-plan]: ../plans/features/2026-09-30-explicit-profile-artifacts-noref.md
[reuse-adr]: ../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[roadmap]: ../../docs/roadmap.md
