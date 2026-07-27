# Tool Plan

## Publish the historical architectural-decision backlog

- Date: 2026-07-27
- Status: Completed
- Title: Publish the historical architectural-decision backlog
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Dea-wide ADR catalog
  - L0 ADR catalog
  - L1 ADR catalog
  - Dated architectural-decision audit resolution overlay
- Origin: `work/audits/architectural-decisions/2026-07-26/missing-adr-candidates.md`
- Porting rule: Preserve each historical decision in its owning ADR directory; do not mechanically duplicate
  level-specific decisions across catalogs.
- Target status:
  - Dea-wide ADR catalog: Implemented
  - L0 ADR catalog: Implemented
  - L1 ADR catalog: Implemented
  - Dated architectural-decision audit resolution overlay: Implemented
- Subsystem: Architectural decision records / documentation lifecycle
- Modules:
  - `docs/decisions/`
  - `l0/docs/decisions/`
  - `l1/docs/decisions/`
  - `work/audits/architectural-decisions/2026-07-26/`
  - `scripts/validate_architectural_decision_audit.py`
- Test modules:
  - `scripts/validate_architectural_decision_audit.py`
  - `scripts/check_adr_impact.py`
- Related:
  - `work/audits/architectural-decisions/2026-07-26/dea-architectural-decision-audit.md`
  - `work/audits/architectural-decisions/2026-07-26/missing-adr-candidates.md`
- Repro: `python3 scripts/validate_architectural_decision_audit.py`

## Summary

The dated architectural-decision audit identified 24 coherent ADR candidates covering 123 current decisions: 23 new
records and one amendment to L0 ADR-0014. The backlog reserved contiguous numbers in each owning catalog, but at the
start of this plan the candidate records had not yet been promoted into accepted ADR files.

This plan publishes the complete backlog in directory sequence, preserves historical decision dates and source-plan
provenance, and adds a current resolution overlay without rewriting the audit's baseline counts.

## ADR Impact

- Decision: Keep ordinary abrupt simple statements in `for` headers, restrict declarations to initialization, target an
  already-enclosing loop from header `break` and `continue`, preserve execution order, and derive definite flow only
  from guaranteed paths while honoring `with` cleanup replacement.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0012-shared-for-header-control-flow-liveness-and-cleanup-semantics.md`
  - Rationale: The rule spans syntax, flow analysis, lowering, and cleanup semantics shared by Dea levels.
- Decision: Stable L0 releases use immutable public `l0-vX.Y.Z` tags, checked-in release notes, complete drafts before
  publication, and a complete bare-name SHA-256 manifest, while snapshots remain explicit prerelease flows.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md`
  - Rationale: Release identity and artifact integrity are durable L0 distribution contracts.
- Decision: Diagnostic collectors remain authoritative, parser recovery preserves braces and partial parse state, and
  accumulated recoverable errors gate semantics and code generation rather than parsing.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md`
  - Rationale: The decision constrains shared parser, phase-boundary, and diagnostic contracts.
- Decision: Forward-only cross-level migrations require every oracle mismatch to be explicit, narrow, and recorded as a
  parity exception until the upstream level catches up.
  - Scope: Dea-wide
  - Disposition: New ADR
  - ADR: `docs/decisions/0014-intentional-cross-level-divergence-and-parity-exceptions.md`
  - Rationale: Intentional parity exceptions govern coordination among all language levels.
- Decision: Shared integer helpers use unsuffixed `int` names and `_ui`, `_l`, and `_ul` wide-family suffixes, assert
  invalid preconditions, and reserve nullable results for domain or representability failure.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0015-shared-integer-standard-library-naming-and-failure-contract.md`
  - Rationale: Naming and failure behavior form one cross-level public standard-library contract.
- Decision: L0 limits unannotated top-level inference to its self-hosting-safe subset, while L1 accepts arbitrary
  top-level runtime expressions and lowers nonconstant initialization into module initialization.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0016-top-level-let-inference-and-runtime-initialization-boundaries.md`
  - Rationale: The intentional level boundary must be recorded as one cross-level semantic decision.
- Decision: Retained bootstrap C is compared raw, native identity is normalized or waived without mutating executables,
  bootstrap compilers omit provenance, and release provenance enters through generated source.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0014-bootstrap-self-hosting-strategy.md`
  - Rationale: This refines the existing L0 bootstrap strategy with its settled platform identity and provenance rules.
- Decision: Safe L0 standard-stream byte I/O uses assertion-checked `ByteArray` subranges, progress counts, `null` for
  I/O failure, zero for EOF, and keeps raw-pointer operations in the low-level memory module.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0018-safe-standard-stream-byte-io.md`
  - Rationale: The public buffer and failure contract is a durable L0 standard-library boundary.
- Decision: L0 Stage 2 uses pointer-owned declarations and shared metadata with arena-backed expression, statement, and
  pattern nodes referenced by IDs, all owned by one `ParseResult`.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0019-stage2-ast-and-parser-ownership.md`
  - Rationale: The AST representation and aggregate ownership model constrain the self-hosted frontend architecture.
- Decision: The L0 `l0c` facade owns build orchestration and host-command construction, invokes tools through
  `std.system`, and consumes normalized runtime status values.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0020-stage2-driver-and-host-process-boundary.md`
  - Rationale: This is the durable boundary between the compiler driver, host process execution, and platform adapters.
- Decision: L0 release artifacts target Linux x86_64, macOS x86_64 and arm64, and Windows x86_64, with UCRT64 as the
  automated Windows tier and portable default runtime linkage.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0021-supported-host-and-release-tiers.md`
  - Rationale: Supported-host tiers and artifact portability materially constrain release engineering.
- Decision: L0 exposes distinct `WallTime`, `MonotonicTime`, `Duration`, and `DateTime` values with normalized
  nanoseconds and explicit failure, separating runtime clock and local-time facts from language-level UTC conversion.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0022-time-model-and-runtime-boundary.md`
  - Rationale: Public values, failure semantics, and the host/runtime boundary form one time architecture.
- Decision: Installed and distributed L0 Stage 2 toolchains are self-contained and relocatable, omit Stage 1, and carry
  shared assets and version metadata while repository-local stage selection remains explicit.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md`
  - Rationale: The install and distribution layout is a durable public toolchain contract.
- Decision: L1 `case` arms use equality comparability, out-of-domain integer arms warn as always false, and their bodies
  remain type-checked even though they cannot become runtime branches.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0023-case-value-comparability-and-unreachable-arm-policy.md`
  - Rationale: Case typing, reachability, diagnostics, and lowering must remain coherent.
- Decision: L1 top-level functions and constructors accept either wholly positional or complete named arguments, map
  labels to declaration order, and evaluate expressions left-to-right in written order.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0024-named-call-syntax-completeness-and-evaluation-order.md`
  - Rationale: Named-call syntax, completeness, mapping, and evaluation order form one language contract.
- Decision: L1 same-type non-null pointers support identity equality and inequality, heterogeneous pointers require an
  explicit cast, and ordered pointer comparison is rejected.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0025-pointer-equality-and-ordering-semantics.md`
  - Rationale: Pointer comparison semantics and compatibility are durable type-system rules.
- Decision: L1 exposes `std.real` over `sys.real` with explicit `_f` and `_d` APIs, gated runtime helpers, and host-math
  linkage only when those helpers are used.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0026-real-library-runtime-and-host-math-linkage-boundary.md`
  - Rationale: The public API and compiler/runtime/linker boundary are one cross-cutting L1 standard-library decision.
- Decision: L1 uses declaration-only public runtime headers backed by driver-selected normal or traced archives, with
  platform objects for official builds, parallel TinyCC objects, and no forced L0 archive migration.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
  - Rationale: Runtime packaging, trace selection, toolchain compatibility, and the L0 boundary are one architecture.
- Decision: Dea owns canonical documentation and export artifacts, validation never publishes, synchronization is opt-in
  and artifact-based, and destination repositories own import, commit, and deployment.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md`
  - Rationale: Cross-repository ownership and authorization are durable repository architecture.
- Decision: One shared editor package exposes distinct L0 and L1 identities, uses an error-tolerant L1-superset grammar
  for structure, defers LSP semantics, and keeps compilers authoritative.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0018-shared-editor-tooling-level-identities-and-compiler-authority.md`
  - Rationale: Shared editor organization and semantic authority constrain future tooling work.
- Decision: Shared public modules use intent-revealing names, specialized containers use type-before-container order,
  and pre-release renames are hard source breaks without aliases or shim modules.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0019-shared-standard-library-naming-and-compatibility-policy.md`
  - Rationale: Naming and compatibility policy constrain the cross-level public standard-library surface.
- Decision: The L0 runtime returns a stable file-info record, while empty files, short reads, and EOF remain recoverable
  outcomes rather than fatal runtime failures.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0024-filesystem-metadata-and-file-read-abi.md`
  - Rationale: Filesystem metadata and ordinary I/O uncertainty define a durable runtime ABI.
- Decision: L0 ARC and memory traces carry Dea source locations through runtime entry macros and generated-C `#line`
  directives.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0025-runtime-trace-source-provenance.md`
  - Rationale: Trace event provenance constrains generated C, runtime ABI, and trace tooling together.
- Decision: One L0 Stage 2 `AnalysisResult` owns semantic state and one authoritative diagnostic collector; name
  resolution establishes module environments, local declarations, then open imports while diagnostics accumulate
  throughout analysis.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0026-stage2-semantic-result-and-pass-ordering.md`
  - Rationale: Semantic ownership and pass ordering are durable self-hosted analyzer architecture.

## Current State

1. The dated audit contains complete source-plan provenance, architectural questions, alternatives, rationale, and
   consequences for all 24 candidates.
2. Dea-wide ADR-0011 and L1 ADR-0022 occupy numbers introduced after the audit baseline; the reserved candidate
   sequences already account for both.
3. No candidate identifier may appear in stable ADRs, indexes, plans, or normative documentation. Audit-only IDs remain
   confined to the dated audit bundle.
4. The audit baseline totals remain historical facts even after the present-day ADR coverage improves.

## Goal

1. Create Dea-wide ADR-0012 through ADR-0019.
2. Amend L0 ADR-0014 and create L0 ADR-0017 through ADR-0026.
3. Create L1 ADR-0023 through ADR-0027.
4. Index every new ADR and link each record to its historical source plans and this publication plan.
5. Record all 24 candidates as implemented in a post-audit resolution overlay without changing baseline totals.

## Implementation Sequence

1. Publish and index the eight Dea-wide ADRs in numeric order.
2. Amend L0 ADR-0014, then publish and index L0 ADR-0017 through ADR-0026 in numeric order.
3. Publish and index L1 ADR-0023 through ADR-0027 in numeric order.
4. Reconcile the dated audit validator, statistics, backlog, report, and manifest with the implemented candidate set.
5. Close this plan only after every ADR record names an exact indexed file and every new or amended ADR links back to
   this closed plan.

## Non-Goals

- Re-deciding or changing the architecture recorded by the source plans.
- Renumbering existing ADRs or reusing retired numbers.
- Copying audit-only identifiers into stable ADRs, indexes, lifecycle documents, or normative documentation.
- Recomputing the dated audit's historical-event, canonical-decision, or baseline ADR-coverage totals.
- Changing compiler, runtime, language, standard-library, CLI, release, or publication behavior.

## Verification Criteria

1. Each ADR follows its directory template and is present exactly once in the matching `INDEX.md`.
2. Decision dates reflect the historical source decision; `Last edited` records this publication pass.
3. Every related plan, initiative, ADR, and current-document link resolves.
4. Audit-only identifiers remain confined to `work/audits/architectural-decisions/2026-07-26/`.
5. The audit validator reports 24 implemented candidates, zero unresolved candidates, and unchanged baseline totals.
6. Active and staged ADR-impact validation, Markdown formatting, `git diff --check`, and root pre-commit pass.

## Completion Notes

- Published and indexed Dea-wide ADR-0012 through ADR-0019, L0 ADR-0017 through ADR-0026, and L1 ADR-0023 through
  ADR-0027 without renumbering existing records.
- Amended L0 ADR-0014 with the settled platform-specific bootstrap artifact identity and provenance rules.
- Preserved historical decision dates, source-plan and initiative provenance, alternatives, rationale, consequences, and
  current-document links in every accepted record.
- Added a 2026-07-27 resolution overlay to the dated audit while preserving its baseline event, canonical-decision, ADR
  inventory, and coverage totals.
- Kept audit-only decision and candidate identifiers confined to the dated audit bundle.
