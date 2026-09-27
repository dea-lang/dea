# Refactor Plan

## Investigate L1 preparation SHA-256 cost

- Date: 2026-09-26
- Status: Completed
- Title: Investigate the cost of SHA-256 in L1 preparation without changing validation
- Kind: Refactor
- Severity: Medium
- Stage: 1
- Subsystem: Native preparation / stable file hashing / performance measurement
- Modules:
  - `l1/compiler/stage1_l0/support/preparation/sha256.h`
  - `l1/compiler/stage1_l0/support/preparation/platform.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/scripts/build_stage1_l1c.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_observability_test.c`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
- Related:
  - [l1/work/plans/features/2026-09-24-preparation-reuse-efficiency-noref.md][reuse-efficiency]
  - [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/investigation.md][earlier-investigation]
  - [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/results.md][image-study]
  - [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md][policy-experiment]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-boundary]
  - [l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/results.md][results]
- Repro: Run `measure.py` from the [retained investigation bundle][results].

## Summary

The actual Stage 1 support build used GCC with `-O1`. Direct processing of complete 64-byte blocks improved interleaved
large-file stable-hash medians by 1.88% to 4.87%, while a 16-word circular message schedule regressed every large input
by 10.59% to 12.65%. The direct-block candidate therefore advanced to prepared-image measurement; the circular schedule
did not.

Direct-block prepared requests were positive but did not qualify. Clang improved by 100.507 ms and 3.22% in four of five
first-request pairs, missing the required 150 ms absolute threshold. GCC improved by 11.232 ms and 0.85% in two of five
pairs. Warm medians remained within the permitted regression budget. The fixed result is **separately investigate**;
production remains unchanged.

## ADR Impact

- Decision: Improve the internal execution cost of the existing SHA-256 implementation without changing its algorithm or
  validation authority.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This bounded measurement and any small same-algorithm code change preserve the established preparation
    identity and reuse boundary. A larger backend, dependency, or policy choice requires a separately scoped decision.

## Baseline and Measurement

1. Record the exact compiler executable, version, emitted C build command, optimization flags, and relevant environment
   used to build `l1c` and `preparation_support.c`. Record separately the downstream GCC or Clang selected by `l1c` for
   preparation. `build_stage1_l1c.py` passes preparation support as an extra C source to L0 Stage 2; that driver's Linux
   GCC-family source default is `-O1` unless overridden. Verify the actual image build rather than inferring its flags
   from the selected downstream compiler. Investigate an unexpectedly unoptimized support build before a hash rewrite.
2. Add an experiment-local C harness around the production SHA-256 and stable-read functions, without changing their
   public or compiler-private interfaces. Measure three operations independently: SHA-256 over already allocated and
   initialized memory; sequential `fread` without SHA-256; and the complete `pc_hash_file_measured` operation. Use the
   production 64 KiB chunk size and smaller/irregular streaming divisions. For the memory case, initialize or load the
   data before timing, allocate large inputs one at a time, and verify the resulting digest. The read-only case must
   consume every byte into a checked checksum so that it actually reads the data. Report bytes, wall time, throughput,
   and process CPU time where available.
3. Include small and multi-megabyte controls and the actual large inputs identified in the earlier logs: GCC `cc1`
   (34,148,896 bytes), Clang `libLLVM.so.19.1` (129,673,080), `libclang-cpp.so.19.1` (71,043,800), and `libz3.so.4`
   (27,751,664). Verify paths and sizes in the selected image before measuring. Label first access and repeated access;
   a fresh container is not evidence of a cold filesystem cache. These operations are complementary estimates, not
   additive parts of an inclusive preparation span. Do not add nested hash timings to preparation totals.

## Candidate Selection and Correctness

After the baseline, test at most two isolated candidates selected by measured cost and compiled-code inspection. Start
with portable, dependency-free C, such as processing complete blocks directly or a small compression/update-loop
restructure. Check whether the build compiler already removes the suspected overhead. An actual preparation-support
optimization-flag defect may take one candidate slot; do not change global optimization settings. An optimized external
SHA-256 implementation may be measured as a headroom reference only, without becoming a production dependency or a
per-file hashing process.

For every candidate, compare digests with an independent SHA-256 reference for empty input; 55, 56, 63, 64, and 65
bytes; multiple blocks; irregular streaming chunks; unaligned addresses; and large preparation-sized inputs. Exercise
existing support, identity, observability, force, failed-read, changed-file, and artifact-recovery tests. Preserve the
stable reader's association among bytes, open file, and selected pathname, including its errors. Keep defined integer
behavior, C99/bootstrap compatibility, supported compiler/platform constraints, alignment assumptions, and CPU
requirements unchanged.

## Limited Container Check

Adapt one prepared, same-path image layout from the earlier Phase 3 experiment. Each baseline or candidate image must
build its own compiler and prepare its own GCC and Clang caches during image construction. Start a fresh container,
compile once, then compile again using refreshed local evidence. Require both requests to reuse that image's prepared
profile. Compare each runtime `D` and `N` with its own image-time values; different compiler builds need not have equal
keys. Explain any Dea-input byte differences caused by rebuilding the compiler itself.

Use normal verbosity for five interleaved baseline/candidate pairs per downstream compiler, reversing pair order on
alternate repetitions. Keep separate `-vvv` diagnostic runs for attribution. Retain first- and warm-request elapsed
time, hash counts and bytes by category, per-file hash timings, discovery/probe counts, profile selection and reuse,
native build-command and managed-module compilation counts, and exact output and diagnostics. Run focused preparation
tests and L1 normal validation before proposing a production edit.

## Decision and Stopping Rules

A candidate qualifies for an isolated production proposal only when paired median quiet first-request time improves by
at least 0.15 seconds and 3% for Clang, or 0.07 seconds and 3% for GCC, with improvement in at least four of five pairs.
The other compiler's first-request median may regress by no more than 0.05 seconds and 3%; each warm median may regress
by no more than 0.10 seconds and 10%. Both the absolute and percentage bounds apply. Required hash counts, byte
coverage, discovery/probe behavior, profile reuse, outputs, and diagnostics must preserve the current policy. Report
noisy or borderline results as inconclusive within the fixed budget rather than extending repetitions indefinitely.

Conclude with **adopt, reject, or separately investigate**. A microbenchmark speedup without material preparation gain
does not justify adoption. If reading, metadata, or other work dominates, identify that cost and close this
investigation. If a worthwhile gain requires a larger acceleration backend or dependency, record a separate follow-up
decision. If neither small candidate qualifies, leave production unchanged. Faster SHA-256 can coexist with a later
metadata-policy decision, but this investigation neither assumes nor decides that policy.

## Outcome

- Verified the emitted Stage 1 native build command and its `-O1` support compilation before testing source changes.
- Measured preloaded-memory SHA-256, checked 64 KiB `fread`, and the complete stable reader independently across
  boundary controls, multi-megabyte controls, GCC `cc1`, and the three large Clang libraries.
- Matched every candidate digest against an independent SHA-256 reference for empty, boundary, irregular-streaming,
  unaligned, multi-block and large inputs. Candidate compiler builds passed the focused preparation support, identity,
  observability, force/recovery and integration coverage under GCC.
- Rejected the circular schedule. Classified direct-block processing as inconclusive because it met Clang's percentage
  and pair-count requirements but not its absolute requirement, and did not approach the GCC requirements.
- Kept production SHA-256, stable-read validation, metadata policy, schemas and interfaces unchanged. A future revisit
  requires a separately scoped investigation with a less noisy dedicated host or a larger acceleration approach; no
  follow-up plan was opened by this bounded study.

## Validation Record

- The retained measurement script's report verification passed.
- `make -C l1 clean test` passed on the unchanged production tree.
- Active/staged ADR checks, staged whitespace checking and root pre-commit passed for the closed plan and retained
  evidence.

## Non-goals

- Do not relax metadata or digest-reuse predicates, discovery or artifact validation, stable-read checks, force
  behavior, or recovery diagnostics.
- Do not change SHA-256 digest bytes, JSON serialization, identity construction, persisted digests, or manifest formats.
- Do not add alternative hashes, partial-file hashing, sampling, digest sharing, parallel hashing, or
  toolchain-discovery changes. Record hardware acceleration, platform crypto, and substantial imported implementations
  only as possible follow-ups.
- Do not repeat the full prepared/inherited/copied image matrix without a finding that requires it.

[earlier-investigation]: ../../features/attachments/2026-09-24-preparation-reuse-efficiency/investigation.md
[image-study]: ../../features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/results.md
[policy-experiment]: ../../features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md
[results]: ../attachments/2026-09-25-preparation-sha256-cost-investigation/results.md
[reuse-boundary]: ../../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[reuse-efficiency]: ../../features/2026-09-24-preparation-reuse-efficiency-noref.md
