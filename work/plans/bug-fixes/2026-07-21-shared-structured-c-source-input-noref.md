# Bug Fix Plan

## Pass additional C sources as structured compiler arguments

- Date: 2026-07-21
- Status: Draft
- Title: Replace C-source injection through whitespace-split compiler options with structured arguments
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 1 Python compiler
  - L0 Stage 2 self-hosted compiler
  - L1 Stage 1 bootstrap integration
- Origin: L0 Stage 1 Python compiler CLI contract
- Porting rule: Settle the repeatable option and C-command ordering in Python Stage 1, port the same observable contract
  mechanically to L0 Stage 2, then migrate L1 build and test helpers as consumers.
- Target status:
  - L0 Stage 1 Python compiler: Pending
  - L0 Stage 2 self-hosted compiler: Pending
  - L1 Stage 1 bootstrap integration: Pending
- Subsystem: Compiler CLI / C compiler invocation / Bootstrap tooling
- Modules:
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage2_l0/src/cli_args.l0`
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l1/scripts/build_stage1_l1c.py`
  - `l1/compiler/stage1_l0/scripts/test_runner_common.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
  - `l0/compiler/stage2_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
- Related:
  - `l0/work/plans/features/closed/2026-03-08-l0-cflags-c-compiler-options-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`
  - `l1/docs/decisions/0019-whole-module-interface-fingerprints.md`
- Repro: build the L1 Stage 1 compiler from a checkout whose absolute path contains whitespace

## Summary

L1 currently links a private compiler-support translation unit by appending its absolute path to `L0_CFLAGS`. Both L0
compiler implementations intentionally split `L0_CFLAGS` and `--c-options` on whitespace, so a checkout path containing
spaces becomes multiple C compiler arguments and the Stage 1 build fails.

The correct fix is an additive structured source-input option, not quoting rules inside option strings. This plan adds a
repeatable `-Cs PATH` / `-Cs=PATH` / `--c-source PATH` contract to both L0 compiler stages and migrates L1 to pass its
support unit through that contract. It is intentionally deferred and remains unimplemented.

This option is a prerequisite for the L0 Stage 2 support translation unit required by the shared native build/run
workspace plan. It is not a prerequisite for standalone L1 `--link`: that mode compiles its generated wrapper through
the L1 compiler's direct host-driver command path and owns an output-local link transaction.

## Required Contract

1. `-Cs PATH` / `-Cs=PATH` / `--c-source PATH` is repeatable in `--build` and `--run` modes; each occurrence contributes
   exactly one argv element regardless of whitespace or platform path syntax.
2. Extra sources retain CLI occurrence order. The C command places generated C first, followed by extra sources, before
   output and runtime-library flags.
3. `L0_CFLAGS` and `--c-options` remain option-only, whitespace-delimited inputs with their existing env-first, CLI-last
   precedence. They do not gain shell-quote parsing.
4. The option is additive and does not change source-language project roots or module discovery.
5. Missing source files continue through the existing C-compilation failure path; no new diagnostic code is required.

## Implementation Approach

1. Add repeatable argument storage, help text, and mode validation to Python Stage 1; append the stored paths as intact
   command words after generated C.
2. Port the same storage, ownership, parsing, display, and command construction to L0 Stage 2.
3. Change L1 compiler construction and normal/trace test commands to pass the absolute support translation unit with
   `--c-source`; remove support-source injection from `L0_CFLAGS` while preserving compiler-runtime defines there.
4. Update bootstrap and parity tests so every compiler generation observes the same structured-source contract.

## Non-Goals

- Shell-quote-aware parsing for `L0_CFLAGS` or `--c-options`.
- A general linker-input or foreign-object interface.
- Changing project source roots, module resolution, runtime library selection, or L1 user-program compilation.
- Implementing this plan as part of the interface-fingerprint feature.

## Verification Criteria

1. Both L0 compiler stages preserve one argv element for paths containing spaces, quotes, backslashes, and Windows drive
   syntax without string re-parsing.
2. Multiple `--c-source` occurrences retain order and compile beside generated C in build and run modes.
3. Help, invalid-mode handling, verbose command rendering, and Stage 1/Stage 2 parity tests pass.
4. L1 compiler construction plus normal and trace implementation tests pass from a checkout path containing whitespace.
5. Existing `L0_CFLAGS` and `--c-options` ordering and diagnostics remain unchanged.
6. Full L0 bootstrap/triple-bootstrap and L1 validation pass before this plan can close.

## Diagnostic-Code Plan

No diagnostic-code reservation is expected. Re-check the live catalog before implementation; use existing CLI
missing-value/mode diagnostics and the current C-compilation failure codes unless a genuinely distinct failure category
is discovered.

## ADR Impact

- Decision: Pass each `--c-source` value as one intact, ordered compiler argument.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI contract already owns repeatable option semantics, argument preservation, and cross-stage
    parity.
