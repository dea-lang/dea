# Bug Fix Plan

## Darwin arm64 triple-bootstrap UUID normalization

- Date: 2026-07-11
- Status: Closed (fixed)
- Title: Normalize retained Mach-O UUID metadata without disabling Apple Silicon load commands
- Kind: Bug Fix
- Severity: High
- Stage: 2
- Subsystem: Bootstrap/self-hosting validation
- Modules:
  - `compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
  - `compiler/stage2_l0/README.md`
- Test modules:
  - `tests/test_l0c_triple_bootstrap_normalization.py`
  - `compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-03-17-darwin-arm64-triple-bootstrap-native-mismatch-noref.md`
  - `work/plans/bug-fixes/closed/2026-07-11-shared-ci-platform-portability-regressions-noref.md`
- Repro: Force `platform.machine()` to `arm64` while running `compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py` on
  Darwin

## Summary

The Apple Silicon triple-bootstrap job can execute all three compiler generations and compare the retained C artifacts,
but the final stripped native-binary comparison fails. The second and third Mach-O binaries have the same size and
content except for their generated `LC_UUID` payloads.

## Root Cause

The prior portability fix kept UUID and ad hoc signature generation enabled on Darwin arm64 because disabling those load
commands prevents the generated compiler from launching on Apple Silicon. Darwin artifact normalization removes the code
signature and local symbols, but `strip -x` retains `LC_UUID`, so byte comparison still observes linker metadata that is
intentionally different for the two output paths.

The first normalization implementation removed the ad hoc signature before invoking `strip -x`. For GCC-linked Mach-O
files, signature removal leaves a gap in `__LINKEDIT`; Apple strip then rejects the file because the remaining link-edit
information no longer fills the segment. Stripping the still-valid signed layout first succeeds, after which the invalid
residual signature can be removed safely from the comparison copy.

## Scope of This Fix

1. Preserve normal UUID and ad hoc signature generation for executable Darwin arm64 compiler artifacts.
2. Neutralize only the `LC_UUID` payload in the non-executable normalized copies used for byte comparison.
3. Reject malformed or unsupported Mach-O load-command layouts instead of silently rewriting arbitrary bytes.
4. Cover UUID normalization with focused synthetic Mach-O fixtures.
5. Enforce and test the Darwin operation order: strip, remove signature, then neutralize UUID.
6. Update manual triple-bootstrap documentation to distinguish executable build flags from comparison-only
   normalization.

## Non-Goals

- Weakening retained-C or native-code identity checks.
- Modifying normal compiler outputs or installed compiler binaries.
- Supporting universal Mach-O binaries in the triple-bootstrap test, which produces one native architecture.
- Adding or changing compiler diagnostics.

## Verification Criteria

- Focused UUID-normalization tests cover different UUIDs, absent UUIDs, and malformed load commands.
- The forced Darwin arm64 path passes locally with only `-frandom-seed=l0c-stage2` in `L0_CFLAGS`.
- The normal host triple-bootstrap path still passes.
- `git diff --check` and the relevant Python formatting and static checks pass.

## Outcome

- Added bounded thin Mach-O parsing that neutralizes only the payload of one valid `LC_UUID` command in normalized
  comparison copies.
- Reordered normalization to strip the intact Mach-O layout before removing the residual ad hoc signature, preserving
  Apple strip compatibility for GCC-linked binaries.
- Kept UUID and ad hoc signature generation enabled for executable Darwin arm64 compiler artifacts.
- Added focused coverage for differing UUID payloads, UUID-free Mach-O binaries, malformed load-command sizes, and the
  required normalization operation order.
- Updated the Stage 2 manual workflow to document the architecture-specific Darwin behavior and comparison step.

## Verification

```bash
cd l0 && ../.venv/bin/pytest -q tests/test_l0c_triple_bootstrap_normalization.py
cd l0 && KEEP_ARTIFACTS=1 L0_CC=clang DEA_BUILD_DIR=build/dea ../.venv/bin/python -c 'import platform, runpy; platform.machine = lambda: "arm64"; runpy.run_path("compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py", run_name="__main__")'
cd l0 && L0_CC=clang DEA_BUILD_DIR=build/dea ../.venv/bin/python compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py
# An ad hoc-signed local compiler normalized successfully; `codesign -dvv` reported unsigned and `dwarfdump --uuid`
# reported `00000000-0000-0000-0000-000000000000` for the normalized copy.
git diff --check
```
