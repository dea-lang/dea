# Bug Fix Plan

## Emit valid C names for Dea fields

- Date: 2026-11-27
- Status: Completed
- Title: Emit valid C names for Dea fields
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 canonical compiler
- Target status:
  - L0 Stage 1: Verified locally
  - L0 Stage 2: Verified locally
  - L1 canonical compiler: Verified locally
- Subsystem: C aggregate declarations, construction, access and cleanup
- Modules:
  - `l0/compiler/stage1_py/l0_c_declarations.py`, `l0/compiler/stage1_py/l0_c_values.py`,
    `l0/compiler/stage1_py/l0_c_cleanup.py`
  - `l0/compiler/stage2_l0/src/c_emitter/declarations.l0`, `l0/compiler/stage2_l0/src/c_emitter/values.l0`,
    `l0/compiler/stage2_l0/src/c_emitter/lifetime.l0`
  - `l1/compiler/src/c_emitter/declarations.l0`, `l1/compiler/src/c_emitter/expr.l0`,
    `l1/compiler/src/c_emitter/lifetime.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_constructors.py`,
    `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [l0/work/plans/bug-fixes/closed/2026-11-21-module-qualified-lookup-noref.md](../../../../l0/work/plans/bug-fixes/closed/2026-11-21-module-qualified-lookup-noref.md)
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)
  - [l1/docs/reference/c-backend-design.md](../../../../l1/docs/reference/c-backend-design.md)
- Repro: Run `l0/tests/fixtures/field_names/main.l0` with either L0 stage, or the `main` module under
  `l1/compiler/tests/fixtures/field_names/` with L1.

## Findings and fix

All three frontends accepted `struct Box { sizeof: int; }`, but their C emitters copied the field name verbatim. Native
compilation also failed for keyword-named enum union members and payload fields. Object-like macros in included headers
can rewrite a member token even after `.` or `->`.

Each emitter now maps a Dea member name to C at the point of emission. It prepends `dea_field_` to names in the existing
C keyword list, a fixed set of runtime-header macro spellings, names in the C implementation or runtime macro namespaces
(`__`, `_` plus an uppercase letter, `L0_`, and `DEA_`), and source names already beginning with `dea_field_`. This last
rule keeps `sizeof` and `dea_field_sizeof` distinct. Ordinary fields such as `ord` and `mtime_sec` keep their spelling.
The macro exclusions are independent of the host and apply only to aggregate members.

Declarations, static and dynamic constructors, value and pointer access, pattern bindings, retains and cleanup use the
same mapping. Layout, enum discriminants, top-level symbols and source names in diagnostics and L1 interfaces retain
their existing contracts. Handwritten C selecting an escaped member uses its emitted spelling.

## Verification

Focused checks on macOS Intel used Apple Clang 17 for both levels:

- From `l0/`,
  `../.venv/bin/python -m pytest -q compiler/stage1_py/tests/backend/{test_codegen_constructors,test_codegen_semantics,test_trace_arc,test_runtime_public_header}.py`
  passed 123 tests. The trace fixture copies dynamically allocated strings through both structs and enums and drops
  their heap-allocated owners before checking the copies.
- `make -C l0 test-stage2 TESTS="c_emitter_test backend_test l0c_build_run_test"` passed all three suites.
- `make -C l1 test-compiler TESTS="c_emitter_test backend_test l1c_build_run_multi_cu_test"` passed all three suites
  with the updated L0 Stage 2 bootstrap. The consumer used named arguments and accessed the provider's fields and
  variants with only its compiled object and interface available.
- L0 Stage 2 and L1 ran their field fixtures with `--run --trace-arc --trace-memory`. Each level's `check_trace_log.py`
  reported zero leaked objects and strings. The Stage 1 trace test checks the same property.
- Each compiler compiled and executed a 274-field struct containing each of the 137 listed macro names and its prefixed
  counterpart. Separate foreign C probes wrote `RtTimeParts.sec` and `RtFileInfo.mtime_sec` using the public header and
  all three compiled Dea callers read the results. The 10 L1 predecessor compatibility tests also passed.

## ADR Impact

- Decision: Preserve Dea field identity when emitting C aggregate members.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The emitter must already produce valid C for legal Dea fields. The fix concerns the spelling of generated
    members within the existing aggregate layout.
