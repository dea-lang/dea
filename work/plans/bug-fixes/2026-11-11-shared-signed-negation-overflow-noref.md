# Bug Fix Plan

## Signed minimum negation bypasses checked arithmetic

- Date: 2026-11-11
- Status: Draft
- Title: Prevent undefined C behavior when negating signed minimum values
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 canonical compiler
  - L2 canonical compiler
- Origin: L1 runtime boundary reproduction and shared UB-free integer contract
- Porting rule: Preserve each level's integer domains; apply the equivalent checked-negation lowering to every seeded
  backend and maintain level-owned runtime regressions.
- Target status:
  - L0 Python Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 canonical compiler: Pending
  - L2 canonical compiler: Pending
- Subsystem: Unary integer lowering and checked arithmetic
- Modules:
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/src/backend/lower.l0`
  - `l1/compiler/shared/runtime/src/dea_rt_math.c`
  - `l2/compiler/src/backend/lower.l1`
  - `l2/compiler/shared/runtime/src/dea_rt_math.c`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_overflow_and_control_flow.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_lib_test.l0`
  - `l2/compiler/tests/backend_test.l1`
  - `l2/compiler/tests/l2c_lib_test.l1`
- Related:
  - `l1/docs/decisions/0004-wide-integer-types.md`
  - `l1/docs/reference/design-decisions.md`
- Repro: Compile the parameterized negation functions below and call them with `INT32_MIN` and `INT64_MIN` under UBSan.

## Summary

Accepted L1 `-x` expressions on `int` and `long` lower to raw C negation. Negating the minimum signed value invokes
undefined behavior instead of the defined arithmetic failure required by the language. This is a High-severity
correctness defect because ordinary accepted expressions escape the UB-free integer contract and become optimizer
dependent. An application can guard the minimum explicitly, but that does not restore the compiler guarantee.

The same raw lowering exists in both L0 backends and the L2 backend. This report tracks the shared defect; no fix has
been implemented.

## ADR Impact

- Decision: Restore defined failure for unrepresentable signed negation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The existing integer contract already requires defined overflow handling; repairing an omitted check
    introduces no new arithmetic policy or architectural boundary.

## Current evidence

On 2026-11-11, a fresh L1 compiler was built from current sources with the explicit repository L0 Stage 2 bootstrap. The
host was macOS x86_64, Apple Clang 17.0.0 (`clang-1700.6.4.2`), and macOS SDK 26.2. The selected Clang passed a
`--no-default-config` C99 compile/link/run capability probe. The L1 probes used default checking and separately compiled
caller parameters, excluding constant folding as an explanation.

| Target                  | Evidence                                                                                | Observed behavior                                                                      |
| ----------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| L1 `int`                | Fresh generated C and UBSan execution                                                   | `INT32_MIN` negation reports signed overflow and terminates with `SIGABRT`             |
| L1 `long`               | Fresh generated C and UBSan execution                                                   | `INT64_MIN` negation reports signed overflow and terminates with `SIGABRT`             |
| L0 Python Stage 1 `int` | Current Python compiler generation and UBSan execution                                  | Same `INT32_MIN` negation failure                                                      |
| L0 Stage 2 `int`        | Existing repository compiler generation, current source inspection, and UBSan execution | Same `INT32_MIN` negation failure                                                      |
| L2                      | Current source inspection only                                                          | Homologous `EX_UNARY` path calls `cem_emit_unary_op` without an integer negation guard |

The aborts above come from UBSan, not a Dea arithmetic panic. L2 was not rebuilt or executed for this report. Native
Windows/Linux and other signed widths were not dynamically verified.

## Reproduction

Save the following as `numeric_probe.l1` in a temporary directory:

```text
module numeric_probe;
func negate_int(x: int) -> int { return -x; }
func negate_long(x: long) -> long { return -x; }
```

Save this separate C caller as `negation_harness.c` in the same directory:

```c
#include "dea_rt.h"
#include <stdio.h>
#include <stdlib.h>
dea_int __deaM13numeric_probeN10negate_intF1ii(dea_int);
dea_long __deaM13numeric_probeN11negate_longF1ll(dea_long);
int main(int argc, char **argv) {
    if (argc > 1 && atoi(argv[1]) == 64) {
        printf("%lld\n", (long long)__deaM13numeric_probeN11negate_longF1ll(INT64_MIN));
    } else {
        printf("%d\n", __deaM13numeric_probeN10negate_intF1ii(INT32_MIN));
    }
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
  "$PROBE/negation_harness.c" "$RT"/src/*.c -o "$PROBE/negation_harness"
"$PROBE/negation_harness" 32
"$PROBE/negation_harness" 64
```

Run the final two commands independently because both intentionally fail. Generated function bodies contain
`return (-x);`. UBSan reports `negation of -2147483648 cannot be represented` and
`negation of -9223372036854775808 cannot be represented` respectively.

Expected: a defined Dea arithmetic error before evaluating an unrepresentable negation. Modular negation is not
required. [l1/docs/decisions/0004-wide-integer-types.md][wide-integers] and
[l1/docs/reference/design-decisions.md][integer-contract] explicitly require UB-free overflow handling.

## Root cause and proposed scope

The unary lowering branches guard pointer dereferences, and L1/L2 additionally preserve the type of bitwise complement,
but unary minus falls through to direct C emission. Binary subtraction already selects checked runtime helpers.

1. Select checked negation lowering for signed integer domains, preserving one evaluation of the operand and the
   declared result type. Reuse an existing checked subtraction helper or add a narrowly scoped helper as appropriate.
2. Review narrow signed domains and unsigned unary-minus semantics separately; do not infer their runtime behavior from
   the verified `int`/`long` cases.
3. Add runtime boundary regressions in each owning level, with constant-expression coverage kept separate.

No compiler diagnostic code is expected: the defect concerns runtime values and existing arithmetic failure policy. Do
not assign new codes unless implementation exposes a distinct diagnostic need; recheck
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] before doing so.

## Acceptance criteria

- For every supported signed domain, cover `min`, `min+1`, `-1`, `0`, `1`, and `max` as runtime arguments.
- Under UBSan, the unrepresentable case reaches the intended Dea failure without a sanitizer finding; representable
  cases return the correct value.
- Preserve operand single evaluation, floating-point negation, and unrelated unary operations.
- Check the applicable default/basic/unchecked runtime modes: unchecked pointer access does not grant permission for
  undefined arithmetic.
- Keep L0, L1, and L2 regression ownership independent and explicitly record any untested platform or target.

[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[integer-contract]: ../../../l1/docs/reference/design-decisions.md#11-integer-and-failure-semantics
[wide-integers]: ../../../l1/docs/decisions/0004-wide-integer-types.md
