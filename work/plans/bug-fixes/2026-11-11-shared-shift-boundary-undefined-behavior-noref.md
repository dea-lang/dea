# Bug Fix Plan

## Integer shifts expose undefined C boundary behavior

- Date: 2026-11-11
- Status: Draft
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
  - L1 canonical compiler: Pending
  - L2 canonical compiler: Pending
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
- Related:
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/decisions/0004-wide-integer-types.md`
- Repro: Compile `func shift_int(x: int, n: int) -> int { return x << n; }` and execute `(1, 32)`, `(-1, 1)`, and
  `(1, -1)` under UBSan.

## Summary

L1 accepts integer shifts whose runtime operands cause undefined C behavior. A checked-mode `int` left shift emits
`x << n` directly; UBSan confirms invalid positive counts, negative counts, and negative signed left operands. This is a
High-severity correctness defect because accepted integer operations violate the documented UB-free contract. Explicit
input guards are possible, but a later mask cannot repair UB that has already occurred.

The L2 backend has the same lowering strategy, so one shared report owns the correction. L0 does not implement these
bitwise shift operators. No fix has been implemented.

## ADR Impact

- Decision: Define invalid-count, negative-left-operand, and unrepresentable-result semantics for integer shifts.
  - Scope: Shared
  - Disposition: Pending
  - ADR: None
  - Rationale: UB-free execution is already required, but the exact boundary policy must be made explicit for L1 and L2
    before choosing checked failure, count normalization, or defined bit-pattern behavior.

## Current evidence

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

Run the final commands independently because each intentionally fails.

Expected: every accepted runtime shift has a defined result or a controlled Dea error, consistent with
[l1/docs/reference/design-decisions.md][integer-contract]. This report does not prescribe modular shifts or masked
counts.

## Root cause and proposed scope

`be_emit_binary_op` normalizes integer operands through the common-type lattice, selects checked helpers for arithmetic
operators, then emits shifts as raw C operators. C's operand promotions and shift domain are not a substitute for the
L1/L2 integer contract.

1. Define the count domain and result policy after language-level common-type normalization, including signed and
   unsigned operands and mixed integer types.
2. Lower both shift directions without executing an invalid C shift; retain the supported-target signed right-shift
   guarantee and preserve single evaluation of both operands.
3. Replace direct-text-only expectations with runtime semantic and sanitizer regressions, while retaining useful
   generated-code assertions.

No compiler diagnostic code is currently proposed: runtime checking can use the existing failure mechanism. If the
chosen policy adds a static diagnostic, first recheck [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] and
provisionally select nearby unused numbers in the established integer typing area; this report reserves no codes.

## Acceptance criteria

- Cover both directions with counts `-1`, `0`, `width-1`, `width`, and `width+1` after normalization.
- Cover 32-bit and 64-bit signed/unsigned domains, mixed types, negative signed left operands, and unrepresentable
  signed left-shift results.
- Valid cases return correct results; invalid cases follow the selected documented policy without UBSan findings.
- Exercise applicable default/basic/unchecked runtime modes without conflating pointer-check selection with arithmetic
  semantics.
- Keep constant folding, runtime checks, and level-owned suites distinct; record native platform coverage honestly.

[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[integer-contract]: ../../../l1/docs/reference/design-decisions.md#11-integer-and-failure-semantics
