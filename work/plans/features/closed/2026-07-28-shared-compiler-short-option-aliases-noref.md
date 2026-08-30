# Feature Plan

## Add semantic short aliases to the shared compiler CLI

- Date: 2026-07-28
- Status: Completed
- Title: Add coordinated semantic short aliases to current and planned compiler options
- Kind: Feature
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1 Python compiler
  - L0 Stage 2 self-hosted compiler
  - L1 Stage 1 bootstrap compiler
- Origin: Shared compiler CLI contract and ADR-0003
- Porting rule: Keep shared aliases, exact-token parsing, help presentation, and diagnostics mechanically aligned across
  all supporting compilers; retain documented L1-only aliases for L1-only modes and options.
- Target status:
  - L0 Stage 1 Python compiler: Implemented
  - L0 Stage 2 self-hosted compiler: Implemented
  - L1 Stage 1 bootstrap compiler: Implemented
- Subsystem: Compiler CLI / help and version output / shared documentation
- Modules:
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage2_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/decisions/0003-shared-cli-contract.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_cli_mode_flags.py`
  - `l0/compiler/stage2_l0/tests/cli_args_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
- Related:
  - `l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-external-library-linking-cli-noref.md`
  - `work/plans/bug-fixes/2026-07-21-shared-structured-c-source-input-noref.md`
- Repro: compare each approved short spelling with its canonical long spelling in compiler CLI parsing and help output

## Summary

Add exact semantic short aliases for current shared compiler behavior and L1 standalone linking. Reserve coordinated
aliases for deferred structured C-source and external-library options in their owning plans without parsing those
spellings before the underlying features land.

The change is additive. Existing long forms remain canonical, option scope and runtime behavior do not change, and
semantic diagnostics continue to name canonical long options. Missing-value diagnostics preserve the exact spelling that
the user supplied.

## Public CLI Contract

The shared current aliases are:

- `-V` / `--version`
- `-Gk` / `--keep-c`
- `-Sb` / `--check-basic`
- `-Su` / `--unchecked`
- `-Va` / `--trace-arc`
- `-Vm` / `--trace-memory`

L1 additionally implements:

- `-k` / `--link`
- `-e MODULE` / `--entry MODULE`
- `-Cf PATH` and `-Cf=PATH` / `--foreign-object PATH`
- `-Gi` / `--emit-interface`

The deferred aliases are `-Cs` / `--c-source`, `-Rr` / `--rpath`, and `-Cl` / `--link-arg`. Their owning plans record
the spellings, but current parsers do not recognize them.

## Implementation Approach

1. Extend each supporting parser with exact aliases and update its usage/help text.
2. Preserve `-V` as a version early-exit token and bare `-S` as reserved assembly output.
3. Route L1 `-k`, `-e`, and `-Cf` through the existing standalone-link mode, entry validation, and ordered typed operand
   paths without changing link behavior.
4. Amend the shared ADR and normative/live CLI documentation, then update active plans that own deferred option
   implementation or future mode-scope expansion.
5. Add parser, help, early-exit, exact-token, and L1 end-to-end link coverage.

## Non-Goals

- No new compiler mode, runtime mode, artifact, linker behavior, or diagnostic code.
- No short alias for default `--build`, inspection modes, or `--include-eof`.
- No placeholder parsing for deferred `-Cs`, `-Rr`, or `-Cl`.
- No reinterpretation of conventional `-g`, `-S`, `-L`, or `-l`.

## Verification Criteria

1. Every immediate alias produces the same parsed state and mode validation as its canonical long form.
2. `-V` short-circuits target and option validation exactly like `--version`.
3. L1 `-k`, `-e`, and `-Cf` retain standalone-link entry validation and exact typed operand ordering.
4. Multi-letter short options remain exact and non-clusterable; concatenated suffixes are rejected.
5. All compiler help output and live CLI documentation list the implemented aliases.
6. Focused CLI/link tests, L0 Stage 2 validation, L1 Stage 1 validation, root normal validation, ADR checks, and
   pre-commit pass.

## Diagnostic-Code Plan

No new diagnostics are expected. Reuse the existing CLI unknown-option, missing-value, mode-scope, conflict,
cardinality, and standalone-link diagnostics.

## ADR Impact

- Decision: Assign coordinated semantic short aliases to shared and L1-specific compiler operations.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: ADR-0003 owns shared option meanings, conventional reservations, semantic namespaces, and cross-stage
    compatibility.

## Completion Notes

Completed on 2026-07-28.

- L0 Stage 1, L0 Stage 2, and L1 Stage 1 now accept `-V`, `-Gk`, `-Sb`, `-Su`, `-Va`, and `-Vm` as exact aliases for the
  corresponding shared long options.
- L1 Stage 1 additionally accepts `-k`, `-e`, `-Cf`, and `-Gi` for standalone linking, entry selection, explicit foreign
  objects, and interface emission. `-Cf` accepts following and `=VALUE` forms; `-e` accepts only a following value.
- Existing long options, option scope, standalone-link operand ordering, entry validation, and canonical semantic
  diagnostics remain unchanged.
- `-Cs`, `-Rr`, and `-Cl` are documented reservations for deferred features and remain unknown in every current parser.
- ADR-0003, shared and level-local CLI specifications, user-facing status/reference documentation, and active plans that
  own the deferred options now describe the coordinated spellings.

## Verification Results

- Focused L0 Stage 1 CLI tests: 122 passed.
- Focused L0 Stage 2 parser and help tests: 2 passed.
- Focused L1 Stage 1 parser, help, and standalone-link tests: 3 passed, including executable links through the short
  aliases.
- `make clean test`: Pass from the repository root. L0 Stage 1 reported 1,446 passing tests; L0 Stage 2 reported 54/54
  normal tests plus 8/8 examples and passing workflow checks; L1 Stage 1 reported 64/64 normal tests plus passing
  environment and 4/4 example checks.
- `make -C l0 test-stage2-trace`: Pass, 33/33 trace checks.
- `make -C l1 test-stage1-trace`: Pass, 44/44 default trace checks; the target's documented slow
  `math_runtime_compile_test` exclusion remained in effect.
- `python3 scripts/check_adr_impact.py --all-active`: Pass.
