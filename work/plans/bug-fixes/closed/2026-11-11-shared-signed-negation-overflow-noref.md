# Bug Fix Plan

## Signed minimum negation bypasses checked arithmetic

- Date: 2026-11-11
- Status: Completed
- Report ID: BUG-002
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
  - L0 Python Stage 1: Completed
  - L0 Stage 2: Completed
  - L1 canonical compiler: Completed
  - L2 canonical compiler: Completed
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
  - `l0/compiler/stage2_l0/tests/negation_runtime_test.py`
  - `l1/compiler/tests/integer_boundary_runtime_test.py`
  - `l2/compiler/tests/integer_boundary_runtime_test.py`
- Related:
  - `l1/docs/decisions/0004-wide-integer-types.md`
  - `l1/docs/reference/design-decisions.md`
- Repro: Compile the parameterized negation functions below and call them with `INT32_MIN` and `INT64_MIN` under UBSan.

## Summary

Previously, accepted L1 `-x` expressions on `int` and `long` lowered to raw C negation. Negating the minimum signed
value invokes undefined behavior instead of the defined arithmetic failure required by the language. This is a
High-severity correctness defect because ordinary accepted expressions escape the UB-free integer contract and become
optimizer dependent. An application can guard the minimum explicitly, but that does not restore the compiler guarantee.

The same raw lowering existed in both L0 backends and the L2 backend. This plan tracks the shared correction across the
four owned compiler implementations.

## ADR Impact

- Decision: Restore defined failure for unrepresentable signed negation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The existing integer contract already requires defined overflow handling; repairing an omitted check
    introduces no new arithmetic policy or architectural boundary.

## Original evidence

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

Run the final two commands independently because both intentionally fail. Before the repair, generated function bodies
contained `return (-x);`. UBSan reported `negation of -2147483648 cannot be represented` and
`negation of -9223372036854775808 cannot be represented` respectively.

Expected: a defined Dea arithmetic error before evaluating an unrepresentable negation. Modular negation is not
required. [l1/docs/decisions/0004-wide-integer-types.md][wide-integers] and
[l1/docs/reference/design-decisions.md][integer-contract] explicitly require UB-free overflow handling.

## Root cause and repair

Unary minus fell through to direct C emission even though binary subtraction already selected checked runtime helpers.
The repair reuses checked subtraction and narrowing for the signed result domain, preserving one evaluation of the
operand. Level-owned regressions cover runtime boundaries separately from constant expressions.

The existing runtime arithmetic failure mechanism suffices. No compiler diagnostic code or entry in
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] was added or reassigned.

## Implementation decisions

- L0 checks `int` negation with existing subtraction support and preserves its `byte`-to-`int` promotion.
- L1/L2 check `tiny`, `short`, `int`, and `long` negation in their declared domains. Narrow signed results require the
  existing checked narrowing helpers after checked `int` subtraction.
- Preserve floating-point and unsigned unary lowering. In particular, existing modular `uint`/`ulong` negation is not
  reassigned by this signed-overflow repair; narrow unsigned expression consistency is outside this plan.
- Arithmetic checks remain enabled in default, basic, and unchecked pointer-runtime modes. No new runtime helper or
  compiler diagnostic is needed for signed negation.

## Acceptance criteria

- For every supported signed domain, cover `min`, `min+1`, `-1`, `0`, `1`, and `max` as runtime arguments.
- Under UBSan, the unrepresentable case reaches the intended Dea failure without a sanitizer finding; representable
  cases return the correct value.
- Preserve operand single evaluation, floating-point negation, and unrelated unary operations.
- Check the applicable default/basic/unchecked runtime modes: unchecked pointer access does not grant permission for
  undefined arithmetic.
- Keep L0, L1, and L2 regression ownership independent and explicitly record any untested platform or target.

## Completed implementation

- L0 Python Stage 1 and Stage 2 lower integer negation through existing checked zero-subtraction. L0 byte operands
  retain promotion to `int`.
- L1/L2 use checked `int`/`long` subtraction. Signed narrow negation additionally uses the existing checked narrowing
  helper so `tiny` and `short` minimum values fail in their declared result domains.
- Level-owned runtime regressions cover signed boundaries, single evaluation, unchanged byte/unsigned behavior,
  floating-point values and signed zero where supported, and constant-expression handling. All pointer-runtime modes
  retain the arithmetic checks. No new diagnostic or negation runtime API was required.

## Validation

Native validation used macOS x86_64, Apple Clang 17.0.0 (`clang-1700.6.4.2`), and macOS SDK 26.2. L0 was rebuilt in
`build/bug002-negation`; L1 used that fresh Stage 2 compiler. L2 used its explicitly selected compatible installed L1
bootstrap, followed by a fresh L2 compiler and matching owned runtimes.

| Check                                                                    | Result                                                                                                           |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| L0 Python Stage 1 suite                                                  | All 1,657 cases and 6 subtests covered successfully; changed generated-C assertions rerun                        |
| L0 Stage 2 normal suite                                                  | All 59 cases passed, including triple bootstrap                                                                  |
| L0 Stage 2 trace suite                                                   | All 34 cases passed, zero object/string leaks                                                                    |
| L0 examples and workflow/build/distribution checks                       | 8 examples and all workflow checks passed                                                                        |
| L0 native and capability-proven UBSan negation matrices                  | Stage 1 and Stage 2 passed in default/basic/unchecked modes                                                      |
| L1/L2 fast aggregate components and affected library/runtime regressions | Both passed                                                                                                      |
| L1/L2 generated native and capability-proven UBSan integer matrices      | Each passed 252 numeric cases per mode across 6 native/sanitized mode combinations, plus evaluation/float checks |
| L1/L2 backend/emitter traces and traced bitwise fixtures                 | Both passed with zero leaks                                                                                      |
| Shared repository checks                                                 | 666 passed, one expected skip                                                                                    |

The Stage 1 Windows default-flag mock was exercised with `L0_CFLAGS` unset, as its contract requires. Successful suite
partitions were reused with unchanged production inputs; only the corrected generated-C expectations and the isolated
default-flag mock needed targeted reruns. The native matrices pass signed minimum values through separate C callers,
assert controlled Dea overflow rather than sanitizer termination, and retain ordinary execution if UBSan is unavailable.

Replay the completed L0 coverage from `l0/`, with the compiler/SDK environment above and
`DEA_BUILD_DIR=build/bug002-negation`. The completed run reused passing partitions rather than repeating full suites.

```sh
gmake -o venv install-dev-stage2
env -u L0_CFLAGS ../.venv/bin/python -m pytest -q -n 2 compiler/stage1_py/tests
gmake -o venv -o install-dev-stage2 test-stage2 check-examples
gmake -o venv -o test-docgen test-workflows
gmake -o venv -o install-dev-stage2 test-stage2-trace
L0_REQUIRE_UBSAN=1 ../.venv/bin/python compiler/stage2_l0/tests/negation_runtime_test.py
```

The Stage 1 suite includes docgen; the 59 normal Stage 2 tests include triple bootstrap (also invocable with
`gmake -o venv -o install-dev-stage2 triple-test`). The same native matrix validates Stage 1 by calling
`negation_runtime_test.require_matrix([str(Path("scripts/l0c").resolve())], temporary_path, os.environ["L0_CC"])` with
`PYTHONPATH=compiler/stage2_l0/tests` and `L0_REQUIRE_UBSAN=1`.

The complete shared L1/L2 command and environment record is in
[work/plans/bug-fixes/closed/2026-11-11-shared-shift-boundary-undefined-behavior-noref.md][shift-plan]. Final checks
cover C documentation, Markdown, whitespace, ADR Impact, and root pre-commit against the staged change.

## Limits

Native validation used macOS x86_64; Windows, Linux, and macOS ARM were not run. The existing consistency of narrow
unsigned unary results across expression contexts is outside this signed-negation repair. L2 used its explicitly
selected compatible installed L1 bootstrap and freshly rebuilt owned compiler/runtime; changing its bootstrap API
contract is separate work. Other defect plans and publication are outside this repair.

[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[integer-contract]: ../../../../l1/docs/reference/design-decisions.md#11-integer-and-failure-semantics
[shift-plan]: 2026-11-11-shared-shift-boundary-undefined-behavior-noref.md
[wide-integers]: ../../../../l1/docs/decisions/0004-wide-integer-types.md
