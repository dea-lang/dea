# Feature Plan

## Add typed formatting

- Date: 2026-11-05
- Last reviewed: 2026-11-09
- Status: Completed
- Title: Add typed string formatting over L1 variadics
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
- Subsystem: Stdlib / text / I/O / diagnostics
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/format.l1`
  - `l1/compiler/shared/l1/stdlib/std/format_real.l1`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/tests/format_test.l0`
  - `l1/compiler/tests/fixtures/driver/format_main.l1`
  - `l1/compiler/tests/l1c_child_trace_runner_test.py`
- Related:
  - `l1/work/plans/features/closed/2026-04-22-variadic-functions-noref.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Repro: `make -C l1 test-compiler TESTS="format_test diag_print_test analysis_trace_test"`

## Summary

Replace continued growth of combinatorial helpers such as `print_ss`, `print_si`, and `print_ib` with typed formatting
built on the existing `std.types::Value` enum and L1-defined variadic arguments. The result is an ordinary ARC string
that callers pass to concrete output APIs. Later L2 writer integration reuses the adopted engine.

## Implemented Surface

- `format(template: string, args: Value...) -> FormatResult`

Use sequential `{}` placeholders, optional `{:d}`, `{:x}`, `{:X}`, `{:b}`, `{:s}`, and `{:g}` specifiers, and `{{` /
`}}` for literal braces. No width, precision, positional, or named fields in this tranche. Every placeholder consumes
one explicit `Value`; missing and extra values are errors. Integer decimal and radix forms use an explicit minus sign
and unsigned magnitude, including the minimum value. Booleans use `true` / `false`, absent optional values use `null`,
and strings preserve bytes. Real general formatting uses locale-independent round-trip precision, canonical `nan` /
`inf` / `-inf`, and preserves negative zero. Invalid templates, arity, and value/specifier combinations return
structured errors with the template byte offset and argument index.

## Defaults Chosen

1. Use L1 variadics, never C variadic formatting.
2. Keep arguments typed through `Value` rather than converting everything to strings at the call site.
3. Format into a string builder and return an ordinary ARC string. Concrete file and standard-stream writes remain
   separate operations.
4. Make malformed templates and unsupported value/specifier combinations structured errors.
5. Use locale-independent defaults.
6. Permit compiler diagnostics to consume the formatter without importing shell, process, or native `printf` rules.

## Contract Details

- `FormatResult` is `FormatOk(value: string)` or `FormatErr(error: FormatError)`.
- `FormatError` carries `kind: FormatErrorKind`, `offset: int`, and `argument_index: int`.
- Error kinds are `InvalidTemplate`, `MissingArgument`, `ExtraArgument`, and `InvalidSpecifier`.
- Offsets and argument indexes are zero-based. Field failures identify the opening brace; stray closing braces identify
  themselves. Extra arguments identify the template length and first unused argument. Validate each field's grammar
  before its argument, processing left to right and checking surplus arguments last.
- Integer specifiers accept all integer variants, `s` accepts strings, and `g` accepts reals. Default fields also accept
  booleans. Optional values retain their underlying type for compatibility, including absent values rendered as `null`.
- Real output rounds the exact binary value to 9 (`float`) or 17 (`double`) significant decimal digits, ties to even.
  Use fixed notation for rounded decimal exponents in `[-4, precision)`, otherwise scientific notation with lowercase
  `e`, explicit exponent sign and at least two digits. Remove trailing fractional zeroes and preserve negative zero.
- This stdlib API needs no new compiler diagnostic codes. The canonical compiler remains implemented in L0; actual L1
  output fixtures establish formatter usability without importing L1 modules into L0 sources.

## Implementation And Findings

- Added `std.format` parsing, compatibility checking, structured errors, and character-buffer output. Existing
  `std.types`, `std.text`, and `std.io` APIs remain sufficient and unchanged.
- Added `std.format_real`: decompose binary significands exactly with `std.real`, expand powers of two/five into decimal
  digits, round with integer ties-to-even logic, and render the selected notation. No new C runtime or compiler ABI is
  needed. Binary32/binary64 bounds keep conversion storage bounded.
- Added an actual L1 consumer covering all 24 `Value` variants, absent optionals, binary strings, brace grammar,
  structured failure coordinates, integer extrema, real extrema/subnormals/halfway rounding, spreads, and repeated
  successful/error-path cleanup. The L0 harness has the required native preparation support registration.
- Registered the same L1 consumer as an independently checked child trace fixture. Legacy/new print pairs produce
  identical captured bytes. Existing diagnostic-print and analysis tests remain unchanged and pass.
- Added ADR-0054 and refreshed the standard-library reference, design rationale, roadmap, project status, stabilization
  dependency, and capability-audit scope. The reference example compiles and prints `count 2A true`.

## Non-Goals

- C `printf` compatibility or C varargs
- locale-sensitive output in v1
- compile-time format-string checking without a separate language feature
- generic writers or `write_format` (deferred to L2 streams)
- implicit heterogeneous argument conversion
- implicit arbitrary struct reflection
- logging, styling, terminal control, or internationalization frameworks

## ADR Impact

- Decision: Use typed `Value...` arguments, one locale-independent template grammar, and ordinary ARC string results
  instead of expanding combinatorial print helpers or adopting C variadics.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0054-typed-string-formatting.md`
  - Rationale: Formatting is a durable stdlib and diagnostics boundary whose type, error, and determinism rules should
    not inherit `printf`'s unsafe ABI or ambient locale behavior.

## Verification

Validation uses macOS Intel and explicit `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`), for `L0_CC`,
`L1_CC`, and `L1_RUNTIME_CC`. A C99 compilation verified `--no-default-config` support. `L1_BOOTSTRAP_L0C` selects an
existing absolute L0 Stage 2 launcher. Run the following commands from `l1/` with these selections; `-o build` reuses
this task's successful canonical build and verified bundled semantic interfaces.

- `make build`: passed; both new modules are included in the complete bundled interface inventory.
- `make -o build test TESTS="format_test diag_print_test analysis_trace_test"`: passed. This is the fast aggregate with
  explicitly focused compiler cases: 3 compiler tests, 4 examples, 114 docgen tests, 6 Wine-runner checks, 21 tooling
  tests (13 subtests), and 289 productization-fixture tests; 14 platform-specific fixture tests skipped.
- `python3 compiler/tests/l1c_child_trace_runner_test.py` from the root of `l1/`: passed, including the new fixture
  registration and existing failure-artifact checks.
- `../.venv/bin/python compiler/scripts/run_trace_tests.py --children format_main`: passed with 7,192 memory events,
  2,716 ARC events, and zero leaked object/string pointers. Captured legacy and formatted output pairs match exactly.
- `../.venv/bin/python compiler/scripts/run_trace_tests.py format_test`: passed across 16,358,639 events with zero
  leaked object/string pointers. Focused parent traces for `diag_print_test` and `analysis_trace_test` also passed with
  zero leaked object/string pointers.
- Temporary differential probe: 520 seeded finite IEEE values and exponent-boundary neighbors matched Python's
  `.9g`/`.17g` bytes and round-tripped to the original payloads, including signed zero. All cases remained identical
  under the four native rounding modes with a verified decimal-comma numeric locale.
- The reference example compiles and executes successfully. ADR Impact validation and whitespace checks pass.

This is focused normal and trace validation for allocation-bearing stdlib code and its new trace-eligible consumer, not
exhaustive `test-ci` or artifact acceptance. Native Linux, macOS ARM, and Windows validation remain CI follow-up; no
native coverage on those hosts is claimed. No path comparisons or C contracts changed.
