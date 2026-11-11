# Bug Fix Plan

## Emit fixed-array wrappers before aggregate value fields

- Date: 2026-11-11
- Status: Completed
- Title: Emit fixed-array wrappers before aggregate value fields
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Targets:
  - L1 canonical compiler
  - L2 canonical compiler
- Origin: L1 generated-C failure for a struct containing a builtin fixed-size array
- Porting rule: Share the array-related dependency repair while preserving each level's owned implementation, fixtures,
  and runtime validation.
- Target status:
  - L1 canonical compiler: Implemented and validated
  - L2 canonical compiler: Implemented and validated
- Subsystem: C backend type-definition ordering
- Modules:
  - `l1/compiler/src/c_emitter/declarations.l0`
  - `l1/compiler/src/c_emitter/wrappers.l0`
  - `l2/compiler/src/c_emitter/declarations.l1`
  - `l2/compiler/src/c_emitter/wrappers.l1`
- Test modules:
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_compile_only_test.py`
  - `l1/compiler/tests/fixtures/driver/fixed_array_field.l1`
  - `l1/compiler/tests/fixtures/driver/fixed_array_field_main.l1`
  - `l2/compiler/tests/backend_test.l1`
  - `l2/compiler/tests/l2c_compile_only_test.py`
  - `l2/compiler/tests/fixtures/driver/fixed_array_field.l2`
  - `l2/compiler/tests/fixtures/driver/fixed_array_field_main.l2`
- Related:
  - [l1/docs/reference/design-decisions.md][array-contract]
  - [l1/docs/reference/c-backend-design.md][l1-backend]
  - [l2/docs/reference/c-backend-design.md][l2-backend]
  - [l1/work/plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md][slice-plan]
  - [work/plans/bug-fixes/closed/2026-09-11-shared-arc-comparison-temporary-cleanup-noref.md][arc-plan]
- Repro: Generate and compile the level-owned `fixed_array_field` fixture containing `Box { ram: byte[2]; }`.

## Summary

L1 and L2 now emit array-related field and enum-payload typedefs before the aggregate definitions that use them.
Previously, accepted builtin-array fields reached native compilation with an unknown wrapper type. The repair preserves
nominal dependency ordering, flattened multidimensional layout, optional/pointer representation, and existing ownership
behavior. No language, ABI, runtime, or diagnostic-code policy changed.

Severity was High because a documented value layout could not compile; replacing inline storage with a pointer changes
storage and ownership semantics. L0 lacks these source-level fixed arrays and is outside this fix.

## ADR Impact

- Decision: Preserve supported fixed-array value layouts through dependency-correct C emission.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs ordering in the existing C representation without changing language semantics, ABI layout,
    ownership rules, or the compiler architecture.

## Cause and Repair

The general output pipeline emits nominal definitions before its final array-wrapper sweep. The nominal dependency pass
already emits arrays of a just-defined nominal element, but primitive arrays and several array-related optional forms
could remain undefined when a struct field or enum payload referenced them.

Both emitters now call `cem_emit_array_field_wrappers` before opening each aggregate definition. The helper follows
array, pointer, and nullable constructors; it emits array wrappers through the existing dependency-aware emitter and
emits enclosing non-niche optionals only when an array dependency was found. Existing emitted-name sets prevent
duplicate typedefs. Nominal topological sorting and the just-defined-nominal wrapper pass remain unchanged, so nominal
elements still precede arrays that store them by value.

The backend references describe this ordering. The repair does not globally move arrays before nominal definitions or
change unrelated callable/slice emission policy.

## Minimal Reproduction

The independently owned L1 and L2 fixtures contain the same program, using their respective source extensions:

```text
module fixed_array_field;
export Box;
struct Box {
    ram: byte[2];
}
```

Before the repair, a fresh L1 build and a preserved pre-fix L2 artifact generated C successfully but direct C99
compilation failed with `unknown type name '__deaA2_h'`. The field appeared before its wrapper typedef. After the
repair, the wrapper precedes `Box`, and the regression requires both direct generated-C compilation and
`--compile --keep-c` to succeed with identical module C bytes. The executable matrix additionally links the retained
object and checks runtime behavior.

## Coverage

| Area                       | Required assertion                                                                                                                                        |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primitive arrays           | Exported minimal struct compiles; elements can be written and read.                                                                                       |
| Nominal and nested values  | Element definitions precede their array wrappers and enclosing aggregates; value copies remain independent.                                               |
| Multidimensional arrays    | Flattened C storage and nested element access are preserved.                                                                                              |
| Nullable and pointer forms | Nullable elements, nullable array values, arrays of nullable nominal pointers, and pointers to primitive arrays compile and retain their representations. |
| Enum payloads              | Primitive, nominal, and multidimensional array payloads compile and return expected values.                                                               |
| ARC                        | String-array value copies survive replacement in the original; traced execution reports no leaked strings or objects.                                     |
| Emission stability         | Each wrapper appears once; repeated generation is deterministic; retained C equals standalone generated C.                                                |
| Native invocation          | Temporary paths contain spaces; direct C compilation preserves the compiler's whitespace-delimited CFLAGS word contract.                                  |

## Validation

Validation uses macOS x86_64, Apple Clang 17.0.0 (`clang-1700.6.4.2`), and macOS SDK 26.2. The explicit compiler is
`/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang`; its
`--no-default-config` C99 compile/link/run capability probe passed. `L0_CC`, `L1_CC`, `L1_RUNTIME_CC`, `L2_CC`, and
`L2_RUNTIME_CC` select that executable. C/runtime flags include the selected SDK, and `SDKROOT` supplies it to native
helper compilations that do not inherit compiler-driver flags.

L1 is rebuilt through the explicit repository L0 Stage 2 bootstrap. L2 selects installed
`/Users/guglielmo/Downloads/dea-l1/bin/l1c` version 0.1.0 with `L2_BOOTSTRAP_MODE=installed`. This preserves L2's
existing bootstrap API contract: its source uses the installed `int`-seconds time interface, whereas current development
L1 uses `long` seconds. Adapting that pre-existing bootstrap mismatch is outside this fix. L2 target programs continue
to use L2-owned sources, headers, and runtime archives.

Run level commands from the owning subtree with the explicit environment above. The selected tier is fast aggregate
coverage plus compile-only/library integration and focused backend/emitter traces, because this repair changes generated
type declarations and includes ARC-bearing values. Recorded results are:

| Command or check                                                                                                                          | L1                                                             | L2                                                           |
| ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------ |
| Fresh canonical compiler and owned runtime build                                                                                          | Passed                                                         | Passed; 23 bundled interfaces verified                       |
| Normal `array_test`, `parser_test`, `analysis_test`, `expr_types_test`, `interface_test`, `backend_test`, `c_emitter_test`, `driver_test` | Eight passed                                                   | Eight passed                                                 |
| `gmake test-compiler TESTS="l1c_compile_only_test.py"` (L2 uses `l2c_compile_only_test.py`)                                               | Passed, including the new native matrix                        | Passed, including the new native matrix                      |
| `gmake test-compiler TESTS="l1c_lib_test"` (L2 uses `l2c_lib_test`)                                                                       | Passed                                                         | Passed                                                       |
| `gmake check-examples`                                                                                                                    | Four passed                                                    | Four passed                                                  |
| `gmake test-tooling`                                                                                                                      | 53 passed and 72 subtests                                      | 30 passed                                                    |
| `gmake test-docker-wine-runner test-productization`                                                                                       | Six runner tests passed; productization 289 passed, 14 skipped | Not applicable                                               |
| `gmake test-docgen`                                                                                                                       | 114 passed                                                     | Not required for the changed L2 compiler-language sources    |
| `gmake test-compiler-trace TESTS="backend_test c_emitter_test"`                                                                           | Both passed, zero leaked objects/strings                       | Both passed, zero leaked objects/strings                     |
| Traced `fixed_array_field_main` child and level-owned trace analyzer                                                                      | Passed, zero errors/warnings and zero leaked objects/strings   | Passed, zero errors/warnings and zero leaked objects/strings |

Fast aggregate coverage was completed through the listed targets. The normal implementation selectors were
`TESTS="array_test parser_test analysis_test expr_types_test interface_test backend_test c_emitter_test driver_test"`,
with each level's compile-only and library-driver suites added explicitly; L2 also passed
`l2_language_identity_test.py`. After fresh `gmake build` and `gmake -j2 runtime`, compiler and trace targets used
`/opt/local/bin/gmake -o build -o runtime -o venv` to preserve those matching artifacts. Passing checks were reused with
unchanged compiler, fixture, and runtime inputs and the same explicit host compiler/SDK. `SDKROOT` additionally supplies
that SDK to helper and final-link commands; affected native checks passed with it set. Only plan/docs edits followed
their completed validation.

The traced child check uses the following L1 recipe; the L2 invocation substitutes its executable, owned paths, and
analyzer. Set `ARRAY_TRACE_DIR` to a fresh temporary directory and use the explicit environment above:

```sh
build/dea/bin/l1c --build --trace-arc --trace-memory \
  --no-managed-stdlib --no-auto-prepare \
  --runtime-lib "$PWD/build/dea/lib" --runtime-include "$PWD/build/dea/include" \
  --project-root "$PWD/compiler/tests/fixtures/driver" \
  -o "$ARRAY_TRACE_DIR/arrays" fixed_array_field_main
"$ARRAY_TRACE_DIR/arrays" > "$ARRAY_TRACE_DIR/stdout.log" 2> "$ARRAY_TRACE_DIR/stderr.log"
"$PWD/../.venv/bin/python" compiler/scripts/check_trace_log.py \
  "$ARRAY_TRACE_DIR/stderr.log" --triage --max-details 10
```

Finalization checks use `scripts/check_adr_impact.py --all-active` before closure,
`scripts/check_adr_impact.py --staged` after staging, `git diff --cached --check`, and root pre-commit against the
intended staged paths. Relative links are checked from the closed plan location.

## Limits

- Native Windows, Linux, and macOS ARM validation was not performed here. A simulated CFLAGS probe covered Windows
  drive, UNC, and mixed-separator spellings; it does not establish native Windows behavior.
- A self-referential pointer to a nominal array, such as `struct Node { next: Node[1]*; }`, already failed native
  compilation before this fix. Resolving its separate complete-type versus forward-typedef dependency requires
  additional design and is not claimed by this closure. Arrays of nominal pointers and pointers to primitive arrays are
  covered.
- Broader callable/slice declaration-order issues, other arithmetic defect plans, L2 bootstrap API migration, and
  publication are outside this change. No diagnostic codes were introduced or reassigned.

[arc-plan]: 2026-09-11-shared-arc-comparison-temporary-cleanup-noref.md
[array-contract]: ../../../../l1/docs/reference/design-decisions.md#71-fixed-size-array-policy
[l1-backend]: ../../../../l1/docs/reference/c-backend-design.md
[l2-backend]: ../../../../l2/docs/reference/c-backend-design.md
[slice-plan]: ../../../../l1/work/plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md
