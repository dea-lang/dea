# Bug Fix Plan

## Preserve declaration scope during parser recovery

- Date: 2026-10-06
- Status: Closed
- Title: Preserve declaration scope during parser recovery
- Kind: Bug Fix
- Subsystem: Parser
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
  - L1 Stage 2
- Origin: Malformed array parameter types in L0 and L1
- Porting rule: Equivalent brace-aware declaration synchronization in all four frontends
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
  - L1 Stage 2: Implemented

## Findings and implementation

Top-level synchronization accepts `let` inside a rejected function body as a new declaration, producing false `PAR-0020`
diagnostics for subsequent statements. The parsers now track braces from the failed declaration's starting token through
recovery, accepting declaration starts only outside braces. This accounts for braces consumed before the failure as well
as nested blocks encountered while skipping. Existing diagnostic codes and later independent diagnostics are preserved.

## Validation

Regression cases cover malformed parameter and return types, nested bodies, partially consumed declaration bodies,
bodyless declarations, later valid declarations, independent errors, and EOF. The original L0 regression failed with
three diagnostics before the fix; both supplied programs now produce only their original type diagnostic at the
unchanged location. Native parser regressions pass in L0 Stage 2 and both L1 stages.

- L0: `/workspace/dea/.venv/bin/python -m pytest -q compiler/stage1_py/tests/parser`: 57 passed.
- L0: `make test-stage2 check-examples`: 58 tests passed, including triple bootstrap; all 8 examples passed.
- L1: `make test`: both stage smoke suites passed (8 Stage 1 and 2 Stage 2 tests), together with stage parity, all 4
  examples, Docker/Wine runner checks, and Stage 2 tooling checks.
- Whitespace, Markdown formatting, copyright headers, and ADR impact checks passed.

Compiler: `/usr/bin/gcc`, GCC 14.2.0 (Debian 14.2.0-19), selected explicitly with `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`.
Native validation ran outside the sandbox's UID remapping so temporary-directory ownership checks saw the actual
filesystem owners.

The fix changes cursor synchronization only, with no new native allocation, ownership, runtime, or emitted-lifetime
paths; it is trace-independent.

## ADR Impact

- Decision: Preserve structural scope during top-level parser synchronization.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md`
  - Rationale: Restores the established brace-preservation and declaration-boundary contract without changing language
    semantics.
