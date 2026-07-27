# ADR-0026: Stage 2 Semantic Result and Pass Ordering

- Decision date: 2026-02-28
- Last edited: 2026-07-27
- Status: Accepted

## Context

Stage 2 semantic analysis needs driver-loaded modules, diagnostics, module name environments, signatures, local scopes,
and later expression-resolution tables. Returning unrelated pass-owned structures would spread cleanup responsibility
across consumers and make the lifetime of cross-references unclear.

Cross-module resolution also requires a deterministic ordering. Opening imports before each module's own declarations
are collected would make the meaning of an import depend on traversal order or incomplete environments.

## Decision

Stage 2 semantic state and pass ordering follow this architecture:

1. One `AnalysisResult` owns the `DriverState`, combined diagnostic collector, module environments, resolved signatures,
   local scopes, and semantic tables produced by later analysis.
2. Semantic consumers borrow their state through that aggregate and release it through one aggregate cleanup path.
3. Name resolution creates an environment for every loaded module before resolving names.
4. It then collects each module's local declarations.
5. Only after local declaration environments are complete does it open imports and make imported names available.
6. Driver diagnostics are copied into the result before semantic passes begin, and every semantic pass appends to that
   same collector as the ordered work proceeds. The result's collector is the authoritative analysis outcome throughout
   the pipeline.
7. Signature resolution and local-scope construction consume the completed name environments rather than mutating parser
   ownership into an implicit semantic store.

## Rationale

- One lifetime-bearing result makes ownership of semantic tables and their cross-references explicit.
- Precreating all module environments removes load-order dependence.
- Collecting locals before opening imports gives import resolution a complete local declaration universe and preserves
  predictable shadowing and duplicate handling.
- An authoritative diagnostic aggregate lets CLI and backend consumers decide whether analysis succeeded without
  reconstructing pass state.
- Parser and semantic ownership remain separate, which keeps AST representation changes from silently becoming
  semantic-state changes.

## Consequences

- Backends, dumps, and other semantic consumers retain the full `AnalysisResult` for as long as they use any contained
  environment or table.
- Pass reordering is an architectural change and requires checking cross-module resolution behavior.
- New semantic tables should attach to the aggregate or have an explicit borrowed lifetime from it.
- Import opening can rely on all loaded modules having local declaration environments.
- Cleanup remains centralized even as analysis grows beyond the original foundation passes.

## Related Plans

- [l0/work/plans/features/closed/2026-02-28-stage2-semantic-foundation-milestone-noref.md](../../work/plans/features/closed/2026-02-28-stage2-semantic-foundation-milestone-noref.md):
  introduced `AnalysisResult` and the environment, local-declaration, import, and diagnostic pass order
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the Stage 2 semantic ownership and ordering architecture into this ADR

## Current Docs

- [l0/docs/reference/architecture.md](../reference/architecture.md): compiler passes, `AnalysisResult`, and data flow
- [l0/docs/specs/compiler/stage2-contract.md](../specs/compiler/stage2-contract.md): current self-hosted compiler
  contract
