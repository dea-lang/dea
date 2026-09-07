# Bug Fix Plan

## Repair the fingerprint bridge declaration conflict in the Stage 2 source port

- Date: 2026-09-07
- Status: Draft
- Title: Repair the fingerprint bridge declaration conflict in the Stage 2 source port
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: L1 compiler-private C bridge / generated extern declarations / native source-port feasibility
- Modules:
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
  - `l1/compiler/stage1_l0/src/c_emitter/declarations.l0`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_hash.c`
  - `l1/compiler/shared/runtime/internal/dea_interface_fingerprint.h`
- Test modules:
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_symbol_manifest_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_generated_c_identity_test.py`
- Related:
  - [l1/work/plans/refactors/closed/2026-07-08-stage1-source-decomposition-noref.md][decomposition]
  - [work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md][self-hosting]
  - [l1/docs/roadmap.md][roadmap]
- Repro: Generate C for the minimal L1 fixture below, then compile it with Clang and the delivered L1 runtime header.

## Summary

A filename-only `.l0` to `.l1` copy of the L1 compiler passes semantic analysis through the existing L1 Stage 1
compiler, but its native Clang build fails when generated C redeclares the fingerprint bridge with an incompatible
input-pointer type. This plan owns that bounded compatibility repair. The Stage 2 source snapshot, self-builds, and
fixed-point validation remain owned by the self-hosting feature plan.

The source-decomposition plan remains completed. Its required feasibility probe found this pre-existing blocker, and
generating and compiling `interface_fingerprint` from the original source layout reproduced the same failure.

## ADR Impact

- Decision: Repair the existing compiler-private fingerprint bridge contract without redesigning C interoperability.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a declaration-compatibility repair that preserves fingerprint bytes, input immutability, public
    runtime behavior, and the existing bootstrap strategy. A general qualifier model or new public FFI contract is
    outside this fix and would need separate architectural planning.

## Current State and Root Cause

The source declaration is:

```text
extern func l1c_interface_fingerprint_sip13_hex(data: byte*, len: int, out_hex: byte*) -> void;
```

L1 emits this C declaration alongside the included runtime header:

```c
void (l1c_interface_fingerprint_sip13_hex)(dea_byte* data, dea_int len, dea_byte* out_hex);
```

The header, runtime implementation, and Stage 1 support implementation instead use:

```c
void l1c_interface_fingerprint_sip13_hex(const uint8_t *data, int32_t len, uint8_t out_hex[16]);
```

`dea_byte` is `uint8_t`, and the array output parameter adjusts to a pointer. The conflicting part is the input's
pointee `const` qualifier. Passing mutable bytes to a const-input function is valid; declaring that same function twice
with these different parameter types is not. The failure occurs during C compilation, before native linking.

The 2026-09-07 full source-port probe passed semantic checks for `l1c`, `util.demangler`, and `util.path`, covering all
116 production modules. Clang then reported `conflicting types for 'l1c_interface_fingerprint_sip13_hex'` at generated
`interface_fingerprint.c:424`, with the previous declaration at delivered `dea_rt.h:699`. The original pre-decomposition
source reproduced the same diagnostic. Those line numbers identify the captured evidence, not a regression-test
assertion.

Existing known-answer C harnesses manually declare the const-input bridge or include its header. They verify hashing and
archive behavior but do not combine the L1-generated extern declaration with that header, which explains the coverage
gap.

## Minimal Reproduction

Run from the repository root with the repo-local L1 Stage 1 compiler and runtime header already built. If needed,
prepare them with `make -C l1 use-dev-stage1`, using the explicit upstream L0 compiler contract.

```bash
fingerprint_probe_dir=$(mktemp -d /tmp/dea-fingerprint-probe.XXXXXX)
cat > "$fingerprint_probe_dir/fingerprint_probe.l1" <<'EOF'
module fingerprint_probe;
extern func l1c_interface_fingerprint_sip13_hex(data: byte*, len: int, out_hex: byte*) -> void;
func probe(data: byte*, out_hex: byte*) {
    l1c_interface_fingerprint_sip13_hex(data, 1, out_hex);
}
EOF
l1/build/dea/bin/l1c-stage1 --check -Rp "$fingerprint_probe_dir" fingerprint_probe
l1/build/dea/bin/l1c-stage1 --gen -Rp "$fingerprint_probe_dir" \
  -o "$fingerprint_probe_dir/fingerprint_probe.c" fingerprint_probe
clang -std=c99 -pedantic-errors -I l1/build/dea/include \
  -c "$fingerprint_probe_dir/fingerprint_probe.c" -o "$fingerprint_probe_dir/fingerprint_probe.o"
```

The first two compiler commands succeed. The final command fails with:

```text
fingerprint_probe.c:22:7: error: conflicting types for 'l1c_interface_fingerprint_sip13_hex'
dea_rt.h:699:6: note: previous declaration is here
```

This minimal fixture was reproduced on 2026-09-07. It needs neither a committed Stage 2 implementation nor the temporary
full compiler snapshot used by the decomposition audit.

## Scope and Approach

1. Add a regression that sends an actual L1 extern declaration through C generation and strict native compilation
   against the delivered header. Extend the existing bridge regression where practical; do not rely on a hand-written C
   prototype alone.
2. Align the compiler-facing bridge with types the existing L1 source can express. Inspect the declaration, generated
   extern, both C implementations, and their harnesses together. Preserve the const-input internal hashing helper and
   actual input immutability. Assess existing const-input C callers before changing a declaration; use a narrowly scoped
   compiler-private adapter if necessary to preserve their contract. Do not suppress arbitrary extern output or weaken
   native compiler diagnostics.
3. Keep the fixed SipHash key, canonical serialization, exact 16-byte lowercase output, and `.l1m` fingerprints
   unchanged. Preserve symbol/linkage expectations, auditing normal and traced runtime manifests if bridge symbols
   change. Verify direct Stage 1 support-object and runtime-archive linkage separately.
4. Rebuild Stage 1, recreate the complete filename-only `.l1` source copy, and rerun all semantic roots plus the native
   Clang build. Record whether it builds a runnable compiler or reaches a separate later blocker. Any independent
   blocker gets its own evidence and tracking rather than silently expanding this fix into the full self-hosting port.
5. Update both linked plans and the roadmap with the actual readiness result. The decomposition plan remains closed;
   successful repair of this bridge alone does not establish a self-hosting fixed point.

## Diagnostic Planning

No new or reassigned Dea diagnostic codes are expected. The failed host compilation already uses `L1C-0010` from
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]. Preserve that meaning; this fix makes the valid bridge
compile rather than introducing a new diagnostic category.

## Non-Goals

- Reopening the source-decomposition refactor or changing its module layout.
- Adding general C const qualifiers, changing L1 pointer semantics, or redesigning the FFI.
- Changing public runtime behavior, canonical fingerprint semantics, or `.l1m` format.
- Committing generated C, temporary source-port trees, or native probe artifacts.
- Delivering the Stage 2 source snapshot, CI workflow, triple bootstrap, or productization.

## Verification Criteria

1. The regression fails on the current conflict and passes after the repair. The production compiler-facing bridge
   compiles with Clang under strict C99 rules; any adapter has compatible declarations and link coverage.
2. Known-answer bridge tests retain their exact output and verify unchanged input bytes for representative empty,
   ordinary, and binary inputs. Direct support-object and all existing runtime archive variants pass without missing or
   duplicate fingerprint symbols.
3. Focused fingerprint, runtime-symbol, and generated-C identity coverage passes. Run the L1 full validation tier
   (`make -C l1 test-all`) for the planned runtime/backend boundary changes, reusing valid unchanged-input results
   according to the finalization policy.
4. The three source-port semantic roots pass. The native Clang probe proceeds past fingerprint C compilation and linkage
   without this conflict or a replacement fingerprint-symbol failure. Record any independent later blocker explicitly; a
   complete native build is evidence to hand to the self-hosting plan, not a fixed-point claim.
5. Staged whitespace, ADR Impact, and root pre-commit checks pass, and the self-hosting prerequisite and roadmap links
   reflect the final outcome before this bug-fix plan closes.

[decomposition]: ../refactors/closed/2026-07-08-stage1-source-decomposition-noref.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[roadmap]: ../../../docs/roadmap.md
[self-hosting]: ../../../../work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
