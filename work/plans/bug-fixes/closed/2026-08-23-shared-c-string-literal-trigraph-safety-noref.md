# Bug Fix Plan

## Make generated C string literals trigraph-safe

- Date: 2026-08-24
- Status: Completed
- Title: Preserve source bytes when generated C string literals contain trigraph spellings
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: Define one shared byte-preservation invariant, implement it first in L0 Python Stage 1, then port the same
  escaping rule to the native emitters.
- Porting rule: Keep the encoded C literal bytes identical across all three emitters; native ports should be mechanical
  except for language-specific buffer APIs.
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: C backend / String literal emission / Portability
- Modules:
  - `l0/compiler/stage1_py/l0_string_escape.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage2_l0/src/string_escape.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/string_escape.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/interface_literal.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/lexer/test_string_escape.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md`
  - `l0/docs/reference/c-backend-design.md`
  - `l1/docs/reference/c-backend-design.md`
- Repro: Generate and compile a program containing each C trigraph spelling inside a Dea string, including `"??!"`, with
  host trigraph processing enabled, then compare the runtime bytes with the Dea source bytes.

## Summary

All three C emitters pass printable ASCII through their string-escaping helpers except for backslash and double quote.
That policy emits adjacent question marks literally. Under a C implementation or flag set that recognizes trigraphs, a
valid Dea string can therefore be translated before normal C lexical processing and acquire different bytes.

The fix must make generated C string bodies byte-preserving regardless of host trigraph support. It applies to user
string and byte literals plus every other path that feeds decoded text through the same helper, such as generated
filenames, diagnostic reasons, and L1 interface literals.

## ADR Impact

- Decision: Escape C trigraph spellings as part of the existing generated-literal byte-preservation contract.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The work restores the existing requirement that generated C preserve Dea source bytes and does not change
    language syntax, the C ABI, or backend architecture.

## Current State and Root Cause

1. `encode_c_string_bytes()` in L0 Python Stage 1 emits every byte from `0x20` through `0x7e` directly except `\\` and
   `"`.
2. `se_is_direct_c_byte()` in L0 Stage 2 and L1 Stage 1 implements the same rule.
3. Consequently, sequences such as `??!`, `??=`, and the other C trigraph spellings survive unchanged in generated C.
4. Existing tests cover controls, quotes, backslashes, and non-printable bytes, but not translation-phase hazards made
   entirely from printable ASCII.

## Scope of This Fix

1. Define a deterministic encoding for question marks that could complete a trigraph spelling, using `\\?` or a
   fixed-width octal escape without altering runtime bytes.
2. Apply the rule in all three string-escape implementations and every emitter consumer.
3. Cover all nine historical C trigraph spellings, adjacent and overlapping question-mark runs, and ordinary isolated
   question marks.
4. Verify generated filenames and compiler-authored strings use the same safe helper.
5. Keep retained C readable where doing so does not compromise byte preservation.

## Diagnostics

No diagnostic code is added or reassigned. These are valid source strings; only their generated-C representation
changes.

## Non-Goals

1. Changing Dea string or byte escape syntax.
2. Requiring one particular host C compiler or disabling trigraph handling through compiler flags alone.
3. Replacing the shared C-string encoder with a new backend abstraction.

## Verification

1. Unit-test encoded bodies for every trigraph spelling in Python and both native helpers.
2. Assert retained C contains no raw trigraph spelling inside compiler-emitted string literals.
3. Compile and run focused L0 Stage 1, L0 Stage 2, and L1 Stage 1 fixtures with trigraph processing enabled where the
   host compiler exposes that mode.
4. Run the focused emitter/backend suites for all targets, followed by `make test` from the repository root.

## Verification Criteria

1. Every source byte sequence round-trips unchanged through generated C.
2. Ordinary question marks retain their exact runtime value.
3. The same escaping rule is used for literals, filenames, diagnostic strings, and L1 interface literals.
4. Existing string-escape and backend goldens remain stable except for intentionally safer question-mark encoding.

## Implementation Outcome

1. All three encoders now break every physical `??X` trigraph spelling by escaping the second question mark as `\?`,
   preserving the original runtime byte while preventing translation-phase replacement.
2. The Python and native implementations use the same suffix set and original-input look-behind/look-ahead rule,
   including for adjacent and overlapping question-mark runs.
3. Literal, constant-literal, line-directive filename, compiler-authored reason, and L1 interface-literal consumers keep
   routing through the corrected shared encoder.
4. Regression coverage checks all nine historical spellings, question-mark-run boundaries, generated C, strict-C99
   runtime bytes, filename emission, and L1 interface canonicalization fixed points.

## Verification Outcome

1. Focused Python encoder/backend tests and the L0 Stage 2 and L1 Stage 1 emitter/backend suites passed.
2. The L1 interface fingerprint suite passed with canonicalization, canonical fixed-point, and round-trip assertions.
3. Repository-root `make test` passed: 1,459 L0 Python tests, all 55 L0 Stage 2 tests, triple bootstrap, all 67 L1 Stage
   1 tests, examples, runtime checks, and workflow checks completed successfully.
4. The required independent read-only review verified the final C99 encoding with clang `-trigraphs -Werror` and
   reported no remaining actionable findings.
