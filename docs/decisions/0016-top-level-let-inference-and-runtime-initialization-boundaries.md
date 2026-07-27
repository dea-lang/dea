# ADR-0016: Top-Level Let Inference and Runtime-Initialization Boundaries

- Decision date: 2026-04-17
- Last edited: 2026-07-27
- Status: Accepted

## Context

Top-level bindings sit at both a semantic and a runtime boundary. A compiler may need to infer a binding's type before
function-body analysis, while the backend must decide whether its initializer can be represented directly in generated C
storage or must execute as program startup work.

L0 Stage 2 introduced its semantic foundation under bootstrap constraints and deliberately kept unannotated top-level
inference narrow. L1 later needed module-level values initialized by function calls and other nonconstant expressions,
including floating-point constants supplied through runtime helpers. Requiring all levels to expose identical capability
would either expand the bootstrap compiler prematurely or retain an unnecessary L1 restriction.

## Decision

L0 Stage 2 infers the type of an unannotated top-level `let` only from:

- primitive `int`, `byte`, `bool`, and `string` literals; or
- constructor-style calls that resolve to a struct or enum variant.

An L0 top-level binding outside that inference set requires an explicit type annotation. The restriction is a declared
bootstrap capability boundary, not a claim that other initializers are semantically impossible for every Dea level.

L1 permits top-level bindings to use arbitrary expressions that pass ordinary semantic checking, including function
calls. Initializers that are valid as direct C storage initializers remain direct. Nonconstant expressions are deferred
to hidden module-initialization functions.

L1 invokes module initialization before user `main`. Module initialization follows the module dependency graph, with
source order preserving the order of initializers within the applicable dependency ordering. Imported modules are
initialized before dependents.

The two levels therefore intentionally differ: cross-level ports must preserve each level's documented inference and
runtime-initialization boundary rather than assuming L1 capability is mechanically available in L0.

## Rationale

- Narrow L0 inference made the self-hosted semantic foundation implementable and predictable before broader expression
  typing was available.
- Requiring annotations outside the narrow L0 set provides a clear diagnostic and type contract without forbidding all
  nonliteral top-level values in the language family.
- L1 needs runtime initialization to expose ordinary module-level values without getter-function workarounds.
- Separating direct C initialization from a generated module-init phase preserves efficient constants while supporting
  general expressions.
- Dependency and source ordering make startup deterministic and prevent a dependent module from observing an
  uninitialized imported binding.

## Consequences

- L0 diagnostics request an annotation when an unannotated top-level initializer is outside its inference set.
- L1 backend and C-emitter logic classify top-level initializers as direct or deferred and generate a module-init chain.
- The generated program entry wrapper runs initialization before dispatching to user `main`.
- Module dependency ordering becomes observable for nonconstant top-level state and must remain deterministic.
- Current L1 APIs may expose values initialized through runtime calls as bindings rather than synthetic getter
  functions.
- Shared or ported source cannot assume that an unannotated top-level expression accepted by L1 is accepted by L0.
- Expansion of L0's inference or runtime-init capability is a future architectural change, not an automatic parity fix.

## Related Plans

- [l0/work/plans/features/closed/2026-02-28-stage2-semantic-foundation-milestone-noref.md](../../l0/work/plans/features/closed/2026-02-28-stage2-semantic-foundation-milestone-noref.md):
  established L0 Stage 2's narrow top-level inference boundary
- [l1/work/plans/features/closed/2026-04-17-l1-let-non-constant-initializers-noref.md](../../l1/work/plans/features/closed/2026-04-17-l1-let-non-constant-initializers-noref.md):
  introduced L1 deferred module initialization for nonconstant top-level expressions
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [l0/docs/reference/design-decisions.md](../../l0/docs/reference/design-decisions.md): L0 top-level inference
  capability
- [l1/docs/reference/design-decisions.md](../../l1/docs/reference/design-decisions.md): L1 top-level binding and
  initialization behavior
- [l1/docs/reference/c-backend-design.md](../../l1/docs/reference/c-backend-design.md): generated module-initialization
  lowering
