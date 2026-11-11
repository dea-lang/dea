# Bug Fix Plan

## Remove contradictory process-wrapper documentation

- Date: 2026-11-11
- Status: Completed
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
  - L1 backend reference: Implemented
  - L2 backend reference: Implemented
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
- Repro: The former "Legacy process wrapper" subsection contradicted "Per-module output" and "Standalone executable
  wrapper" in both backend references.

## Summary

The L1 and L2 backend references now assign process-level C `main` and cross-module lifecycle ordering to the separate
wrapper emitted by the common link path. The obsolete subsection describing a backend-owned wrapper and hidden global
initialization chain has been removed. Both document versions are refreshed to 2026-11-11.

This was a Low-severity documentation defect: it could mislead readers assessing separate compilation or embedding,
while the same references already described the correct architecture elsewhere. Compiler/runtime behavior, ABI, and
entry-result normalization are unchanged.

## ADR Impact

- Decision: Describe the existing separation between per-module lifecycle output and the executable wrapper accurately.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Removing stale prose restores agreement with the implemented architecture without changing lifecycle,
    linking, ABI, or embedding policy.

## Findings and Correction

The "Per-module output" and "Standalone executable wrapper" sections already documented the implemented architecture.
The former "Legacy process wrapper" subsection contradicted those sections by presenting removed behavior in the present
tense. Both references now use a brief "Process wrapper ownership" subsection linked to the existing wrapper contract.
The already-correct per-module lifecycle and entry-bridge description remains intact.

[l1/compiler/src/backend/output.l0][l1-output] and [l2/compiler/src/backend/output.l1][l2-output] emit module lifecycle
and the conditional `I5entry` bridge. [l1/compiler/src/wrapper_emitter.l0][l1-wrapper] and
[l2/compiler/src/wrapper_emitter.l1][l2-wrapper] separately emit the process wrapper, including runtime argument
initialization, dependency-first module initialization, entry invocation, and reverse-order finalization.

## Verification

- Reviewed both corrected references against their level-owned output/wrapper implementations and existing backend and
  wrapper test assertions. Per-module output excludes process `main` and the legacy global initialization chain; wrapper
  output owns exactly one process `main`.
- Reused the earlier fresh L1 generation check for `module entry_probe; func main() -> int { return 0; }`, invoked with
  `l1c --gen --no-managed-stdlib --project-root <temporary-directory> -o <temporary-directory>/entry_probe.c entry_probe`.
  It passed and emitted `I4init`, `I4fini`, and `I5entry`, without process `int main(` or `_dea_init_modules`. Compiler,
  runtime, and test inputs remained unchanged; L2 evidence is source inspection only.
- Checked the edited repository links and the new internal section links. Markdown formatting, whitespace, active and
  staged ADR validation, and root pre-commit checks passed.
- No compiler suite or generated API-reference rebuild is needed for these hand-written prose changes; the API-reference
  generators do not consume either backend reference. No new diagnostic or architectural decision was introduced.

[l1-compilation]: ../../../../l1/docs/reference/separate-compilation.md
[l1-output]: ../../../../l1/compiler/src/backend/output.l0
[l1-wrapper]: ../../../../l1/compiler/src/wrapper_emitter.l0
[l2-compilation]: ../../../../l2/docs/reference/separate-compilation.md
[l2-output]: ../../../../l2/compiler/src/backend/output.l1
[l2-wrapper]: ../../../../l2/compiler/src/wrapper_emitter.l1
