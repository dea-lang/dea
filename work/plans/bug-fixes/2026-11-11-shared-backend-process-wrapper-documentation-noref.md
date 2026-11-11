# Bug Fix Plan

## Remove contradictory process-wrapper documentation

- Date: 2026-11-11
- Status: Draft
- Title: Correct the current backend reference's legacy process-wrapper description
- Kind: Bug Fix
- Severity: Low
- Scope: Shared
- Targets:
  - L1 backend reference
  - L2 backend reference
- Origin: Confirmed contradiction in the current L1 backend reference
- Porting rule: Correct the seeded L2 description alongside L1 while preserving level-specific names and links.
- Target status:
  - L1 backend reference: Pending
  - L2 backend reference: Pending
- Subsystem: Backend reference / module lifecycle / executable linking
- Modules:
  - `l1/docs/reference/c-backend-design.md`
  - `l2/docs/reference/c-backend-design.md`
- Test modules:
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/wrapper_emitter_test.l0`
  - `l2/compiler/tests/backend_test.l1`
  - `l2/compiler/tests/wrapper_emitter_test.l1`
- Related:
  - [l1/docs/reference/separate-compilation.md][l1-compilation]
  - [l2/docs/reference/separate-compilation.md][l2-compilation]
- Repro: Compare "Per-module output", "Standalone executable wrapper", and "Legacy process wrapper" in either backend
  reference.

## Summary

The current L1 and L2 backend references describe two incompatible owners of the process-level C `main` and module
initialization chain. The stale paragraph can mislead readers assessing separate compilation or embedding into a C
program with its own entry point. Severity is Low because the defect is documentation-only and the same reference also
contains the correct architecture. This report records the defect; no documentation correction or implementation is
included.

## ADR Impact

- Decision: Describe the existing separation between per-module lifecycle output and the executable wrapper accurately.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Removing stale prose restores agreement with the implemented architecture without changing lifecycle,
    linking, ABI, or embedding policy.

## Current State

Source and documentation inspection on 2026-11-11 confirms the defect in both levels:

- "Per-module output" says module C contains no process-level `main`, legacy global initialization chain, or dependency
  lifecycle calls.
- "Standalone executable wrapper" correctly assigns the separate wrapper to `wrapper_emitter` and the common link path.
- "Legacy process wrapper" nevertheless says, in the present tense, that the backend emits host `main` and calls a
  hidden global module-init chain when the entry module defines `main`. Its heading does not say that this behavior was
  removed and is no longer applicable.
- [l1/compiler/src/backend/output.l0][l1-output] and [l2/compiler/src/backend/output.l1][l2-output] emit module
  lifecycle and the conditional `I5entry` bridge. [l1/compiler/src/wrapper_emitter.l0][l1-wrapper] and
  [l2/compiler/src/wrapper_emitter.l1][l2-wrapper] separately emit the process wrapper.
- The listed backend tests assert absence of process `main` and the legacy global chain from module output; wrapper
  tests assert ownership of the single process `main`. These assertions were inspected, not rerun for this report.
- A fresh current-source L1 compiler successfully generated `module entry_probe; func main() -> int { return 0; }`.
  Inspection of that C output confirmed `I4init`, `I4fini`, and `I5entry`, with no process-level `int main(` or legacy
  `_dea_init_modules`. L2 verification remains source and documentation inspection.

## Expected Behavior and Scope

Describe one current architecture: each module owns `I4init`, `I4fini`, and an optional `I5entry`; the common link path
owns the separate process wrapper and dependency lifecycle order. Remove the stale subsection or explicitly mark it as
historical, removed behavior, with a clear pointer to the current contract. Preserve the actual entry-result
normalization rules. Refresh each edited document's version metadata.

This is a reference correction. It requires no compiler, runtime, diagnostic-code, or public-interface change.

## Acceptance Criteria

- Both references contain no present-tense claim that per-module backend output defines process `main` or a global
  initialization chain.
- The entry-point and generated-unit sections agree with each other and with their level-owned implementation and
  existing tests.
- Repository links and Markdown validation pass; no unsupported new embedding or ABI guarantee is introduced.

[l1-compilation]: ../../../l1/docs/reference/separate-compilation.md
[l1-output]: ../../../l1/compiler/src/backend/output.l0
[l1-wrapper]: ../../../l1/compiler/src/wrapper_emitter.l0
[l2-compilation]: ../../../l2/docs/reference/separate-compilation.md
[l2-output]: ../../../l2/compiler/src/backend/output.l1
[l2-wrapper]: ../../../l2/compiler/src/wrapper_emitter.l1
