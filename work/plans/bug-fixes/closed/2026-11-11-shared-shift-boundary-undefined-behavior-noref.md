# Bug Fix Plan

## Integer shifts expose undefined C boundary behavior

- Date: 2026-11-11
- Status: Completed
- Report ID: BUG-003
- Title: Define and safely lower integer shift boundary cases
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Targets:
  - L1 canonical compiler
  - L2 canonical compiler
- Origin: L1 checked-mode runtime reproduction
- Porting rule: Settle the boundary semantics against the existing UB-free integer contract, then preserve the same
  common-integer-type and runtime behavior in the seeded L2 backend.
- Target status:
  - L1 canonical compiler: Completed
  - L2 canonical compiler: Completed
- Subsystem: Binary integer shift lowering and runtime arithmetic
- Modules:
  - `l1/compiler/src/backend/lower.l0`
  - `l1/compiler/src/c_emitter/expr.l0`
  - `l1/compiler/shared/runtime/src/dea_rt_math.c`
  - `l2/compiler/src/backend/lower.l1`
  - `l2/compiler/src/c_emitter/expr.l1`
  - `l2/compiler/shared/runtime/src/dea_rt_math.c`
- Test modules:
  - `l1/compiler/tests/l1c_lib_test.l0`
  - `l1/compiler/tests/fixtures/driver/bitwise_main.l1`
  - `l2/compiler/tests/l2c_lib_test.l1`
  - `l2/compiler/tests/fixtures/driver/bitwise_main.l2`
  - `l1/compiler/tests/integer_boundary_runtime_test.py`
  - `l2/compiler/tests/integer_boundary_runtime_test.py`
- Related:
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/decisions/0004-wide-integer-types.md`
- Repro: Compile `func shift_int(x: int, n: int) -> int { return x << n; }` and execute `(1, 32)`, `(-1, 1)`, and
  `(1, -1)` under UBSan.

## Summary

Previously, L1 accepted integer shifts whose runtime operands caused undefined C behavior. A checked-mode `int` left
shift emitted `x << n` directly; UBSan confirms invalid positive counts, negative counts, and negative signed left
operands. This is a High-severity correctness defect because accepted integer operations violate the documented UB-free
contract. Explicit input guards are possible, but a later mask cannot repair UB that has already occurred.

The L2 backend had the same lowering strategy, so one shared report owns the correction. L0 does not implement these
bitwise shift operators. Implementation follows the boundary policy below.

## ADR Impact

- Decision: Define invalid-count, negative-left-operand, and unrepresentable-result semantics for integer shifts.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0028-integer-shift-boundaries.md`
  - Rationale: Record the shared normalized count domain, checked signed scaling, unsigned bit-pattern preservation, and
    arithmetic signed right shift as a durable L1/L2 contract.

## Original evidence

On 2026-11-11, a fresh current-source L1 compiler generated the probe below in default checked mode. The host was macOS
x86_64 with Apple Clang 17.0.0 (`clang-1700.6.4.2`) and macOS SDK 26.2. The selected compiler passed a
`--no-default-config` C99 compile/link/run probe. The C caller was compiled separately from the generated module so the
tested values were runtime parameters to L1 code.

| Runtime arguments | UBSan diagnostic                                 |
| ----------------- | ------------------------------------------------ |
| `x = 1`, `n = 32` | `shift exponent 32 is too large for 32-bit type` |
| `x = -1`, `n = 1` | `left shift of negative value -1`                |
| `x = 1`, `n = -1` | `shift exponent -1 is negative`                  |

All three executions terminated with `SIGABRT` from UBSan, not a Dea arithmetic check. Generated C contains
`return (x << n);`. L2 source inspection finds the same fallthrough to `cem_emit_binary_op`; no fresh L2 runtime
execution was performed. Right shifts, other integer widths, and additional platforms remain acceptance coverage, not
confirmed runtime findings in this report.

The existing `test_run_bitwise_build_and_keep_c` checks direct C-shift text and positive examples. It does not prove
safe boundary behavior. The signed right shift of a negative value with a valid count is a distinct case: the current
contract explicitly promises arithmetic shifting on supported targets, so C99 implementation-defined behavior alone does
not establish another defect.

## Reproduction

Save as `numeric_probe.l1` in a temporary directory:

```text
module numeric_probe;
func shift_int(x: int, n: int) -> int { return x << n; }
```

Save this separate caller as `shift_harness.c` in the same directory:

```c
#include "dea_rt.h"
#include <stdio.h>
#include <stdlib.h>
dea_int __deaM13numeric_probeN9shift_intF2iii(dea_int, dea_int);
int main(int argc, char **argv) {
    int test = argc > 1 ? atoi(argv[1]) : 1;
    dea_int x = test == 2 ? -1 : 1;
    dea_int n = test == 1 ? 32 : test == 2 ? 1 : -1;
    printf("%d\n", __deaM13numeric_probeN9shift_intF2iii(x, n));
    return 0;
}
```

From the repository root, set `L1C` to a compiler freshly built from the checkout and `PROBE` to that temporary
directory. The verified macOS recipe is:

```sh
REPO="$PWD"
CC="$(xcrun --find clang)"
SDK="$(xcrun --sdk macosx --show-sdk-path)"
RT="$REPO/l1/compiler/shared/runtime"
export L1_HOME="$REPO/l1/compiler"
export L1_BUILD_DIR="$PROBE/build"
mkdir -p "$L1_BUILD_DIR"
"$L1C" --gen --no-managed-stdlib --project-root "$PROBE" \
  -o "$PROBE/numeric_probe.c" numeric_probe
"$CC" --no-default-config -std=c99 -O1 -g -isysroot "$SDK" \
  -fsanitize=undefined -fno-sanitize-recover=all \
  -I"$RT/include" -I"$RT/internal" "$PROBE/numeric_probe.c" \
  "$PROBE/shift_harness.c" "$RT"/src/*.c -o "$PROBE/shift_harness"
"$PROBE/shift_harness" 1
"$PROBE/shift_harness" 2
"$PROBE/shift_harness" 3
```

Before the repair, all three commands failed in UBSan. After the repair, the first and third produce controlled Dea
count errors, while the second returns `-2` under the selected signed-left policy.

Expected: every accepted runtime shift has a defined result or a controlled Dea error, consistent with
[l1/docs/reference/design-decisions.md][integer-contract]. This report does not prescribe modular shifts or masked
counts.

## Root cause and repair

`be_emit_binary_op` normalized integer operands through the common-type lattice but emitted shifts as raw C operators.
The repair selects typed helpers for both directions after normalization, checks counts and signed left-shift results,
and preserves arithmetic signed right shift and single evaluation of both operands. Native semantic and sanitizer
regressions supplement the updated generated-code assertions.

Runtime checks use the existing failure mechanism. No source diagnostic or entry in
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] was added; the internal emitter invariant is recorded
below.

## Selected boundary policy

- Apply the existing common-integer-type lattice to both operands before shifting. The resulting `int`, `uint`, `long`,
  or `ulong` domain determines the 32-bit or 64-bit count limit.
- Both directions reject counts outside `[0, width)` through a controlled Dea arithmetic failure. Do not mask or
  truncate invalid counts.
- Signed left shift is mathematical multiplication by `2^count`, including negative operands, with checked
  representability in the normalized signed domain. This policy was selected by the project maintainer.
- Unsigned left shift preserves its existing fixed-width bit behavior and discards shifted-out high bits.
- Signed right shift is arithmetic; unsigned right shift is logical. Helpers must avoid invalid C operations in every
  pointer-runtime mode and evaluate each operand once.
- Keep the constant folder's documented conservative domain separate; this repair does not expand constant evaluation.

## Diagnostic outcome

No source diagnostic or catalog entry is introduced. The central diagnostic catalog excludes internal `ICE` codes. The
L1/L2 source inventories were rechecked before assigning `ICE-1325`, beside `ICE-1320` through `ICE-1324`, to an
impossible checked-shift result type. Each owned emitter has exactly one definition.

## Acceptance criteria

- Cover both directions with counts `-1`, `0`, `width-1`, `width`, and `width+1` after normalization.
- Cover 32-bit and 64-bit signed/unsigned domains, mixed types, negative signed left operands, and unrepresentable
  signed left-shift results.
- Valid cases return correct results; invalid cases follow the selected documented policy without UBSan findings.
- Exercise applicable default/basic/unchecked runtime modes without conflating pointer-check selection with arithmetic
  semantics.
- Keep constant folding, runtime checks, and level-owned suites distinct; record native platform coverage honestly.

## Completed implementation

- Both backends dispatch normalized shifts to eight typed helpers, with matching headers and normal/traced symbol
  manifests in each owned runtime. Signed left helpers use bounded unsigned magnitudes; signed right helpers reconstruct
  arithmetic results without negative signed C shifts.
- Backend/emitter regressions and native boundary fixtures cover both directions, signed/unsigned 32-bit and 64-bit
  domains, promoted narrow values, mixed types, extreme counts, and independent single evaluation of both operands.
- The selected policy is recorded in [docs/decisions/0028-integer-shift-boundaries.md][shift-adr] and the L1/L2 grammar,
  design-decision, and backend references. Constant evaluation remains separate.

## Validation

Validation ran on macOS x86_64 with Apple Clang 17.0.0 (`clang-1700.6.4.2`) and macOS SDK 26.2. The compiler passed the
`--no-default-config` C99 compile/link/run probe. L0/L1/L2 compiler variables selected that same executable; `SDKROOT`
and explicit `-isysroot` flags supplied the SDK. L1 used the freshly repaired L0 Stage 2 bootstrap. L2 used an explicit
installed L1 0.1.0 bootstrap in installed mode, and rebuilt its own native compiler and all four runtime variants. No
sibling target runtime was borrowed.

| Check                                                     | L1                                                                                                    | L2                                                                           |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Fresh `gmake -j2 build runtime`                           | Passed                                                                                                | Passed                                                                       |
| Fast compiler selectors plus library-driver regression    | 11 passed, including symbol manifests and multiplication overflow                                     | 9 implementation tests passed; 2 native identity/multiplication tests passed |
| `integer_boundary_runtime_test.py` with Apple Clang       | Native and UBSan: 3 modes each, 252 numeric cases per mode, plus evaluation and floating-point checks | Same complete matrix passed                                                  |
| Constant-expression checks                                | Valid fixture accepted; invalid negation/count rejected                                               | Same checks passed                                                           |
| `test-compiler-trace TESTS="backend_test c_emitter_test"` | 2 passed, zero leaked objects/strings                                                                 | 2 passed, zero leaked objects/strings                                        |
| Traced `bitwise_main` fixture and owned trace analyzer    | Exit 29; zero errors, warnings, or leaks                                                              | Exit 29; zero errors, warnings, or leaks                                     |
| All four runtime symbol inventories                       | Matched owned manifests                                                                               | Matched owned manifests                                                      |
| Examples                                                  | 4 passed                                                                                              | 4 passed                                                                     |
| Tooling                                                   | 53 passed and 72 subtests                                                                             | 30 passed                                                                    |
| Native/reference documentation                            | 114 passed                                                                                            | 3 passed                                                                     |
| Productization fixtures and Wine runner                   | 289 passed, 14 expected skips; 6 runner tests passed                                                  | Not applicable                                                               |

The boundary harness compiles generated functions and their caller separately, instruments every runtime unit under
UBSan, proves instrumentation with a deliberate fault, and distinguishes controlled Dea panics from sanitizer findings.
L1 also passed all 756 native numeric cases plus evaluation/float checks with TinyCC 0.9.28rc; unsupported sanitizer
instrumentation was explicitly skipped there. A separate direct-runtime Apple Clang UBSan matrix passed 1,584 calls.

Set the native compiler variables explicitly before replay. On the validated host, `xcrun --find clang` selected the
Apple Clang above and `xcrun --sdk macosx --show-sdk-path` selected SDK 26.2. Set `L0_CC`, `L1_CC`, `L1_RUNTIME_CC`,
`L2_CC`, and `L2_RUNTIME_CC` to that compiler; set `SDKROOT` to the SDK, each `L<N>_CFLAGS` to `-O2 -isysroot $SDKROOT`,
and `RUNTIME_CFLAGS` to `-O2 -std=c99 -isysroot $SDKROOT`. Use the absolute repaired
`l0/build/bug002-negation/bin/l0c-stage2` as `L1_BOOTSTRAP_L0C`, an explicit compatible installed compiler as
`L2_BOOTSTRAP_L1C`, and `L2_BOOTSTRAP_MODE=installed`. `DEA_TEST_MAKE=/opt/local/bin/gmake` selects GNU Make; normal
test jobs used two workers and focused traces used one.

Reproduction commands from each owning level:

```sh
gmake -j2 build runtime
# L1 fast aggregate plus the affected library/runtime selectors:
gmake -o build -o runtime -o venv test \
  TESTS="array_test parser_test analysis_test expr_types_test interface_test backend_test c_emitter_test driver_test l1c_lib_test runtime_symbol_manifest_test.py mul_runtime_overflow_test.py"
# L2 fast aggregate components plus the affected library/runtime selectors:
gmake -o build -o runtime -o venv test-tooling test-compiler \
  TESTS="array_test parser_test analysis_test expr_types_test interface_test backend_test c_emitter_test driver_test l2c_lib_test"
gmake -o build -o runtime -o venv test-compiler \
  TESTS="l2_language_identity_test.py mul_runtime_overflow_test.py" check-examples test-docgen
# Each level's newly added native/UBSan harness and focused trace coverage:
../.venv/bin/python compiler/tests/integer_boundary_runtime_test.py
gmake -o build -o runtime -o venv test-compiler-trace TESTS="backend_test c_emitter_test"
```

The `-o` selections preserve already rebuilt matching artifacts; they do not substitute stale binaries. These component
checks cover both levels' fast aggregates, with affected normal and trace selectors added. Successful checks were reused
only with unchanged compiler/runtime/test inputs. Root repository checks passed 666 tests with one expected skip. Final
closure checks cover whitespace, active and staged ADR Impact, C contracts, Markdown, and root pre-commit against the
staged change.

## Limits

Native validation used macOS x86_64; Windows, Linux, and macOS ARM were not run. L2 construction and implementation
tests used an explicitly selected installed L1 toolchain compatible with its existing time signatures; L2 runtime tests
used the freshly rebuilt L2 compiler and L2-owned support. Bootstrap API migration, other defect plans, and publication
are outside this repair.

[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[integer-contract]: ../../../../l1/docs/reference/design-decisions.md#11-integer-and-failure-semantics
[shift-adr]: ../../../../docs/decisions/0028-integer-shift-boundaries.md
