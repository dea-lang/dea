# L1 preparation SHA-256 cost investigation

- Date: 2026-09-26
- Conclusion: **separately investigate**
- Production changes: None

## Environment and build

The retained local base images were `dea-preparation-investigation-clang:latest` and `l1-test:latest`. Measurements used
one CPU, 512 MiB for isolated hashing and 256 MiB for prepared compiler requests. Containers had no network. A first
access means the first operation within its disposable container; it is not claimed to be a cold filesystem-cache
measurement.

The actual Stage 1 build log contained the expected `-O1` optimization flag: `true`. The build compiler and downstream
compiler versions, complete emitted command, image identities, assembly, focused-test logs and raw request diagnostics
are retained in the machine report and raw-log archive.

## Microbenchmarks

Repeated medians below are complete production stable-file hashes. They include opening, 64 KiB reads, SHA-256,
descriptor/path metadata checks and closing; they must not be added to the separately measured memory SHA-256 or
read/checksum operations.

| Candidate       | Input       | Baseline ms | Candidate ms | Improvement |
| --------------- | ----------- | ----------: | -----------: | ----------: |
| `direct-block`  | `gcc-cc1`   |     209.085 |      205.159 |       1.88% |
| `direct-block`  | `llvm`      |     764.467 |      727.241 |       4.87% |
| `direct-block`  | `clang-cpp` |     381.546 |      371.710 |       2.58% |
| `direct-block`  | `z3`        |     150.206 |      145.948 |       2.83% |
| `ring-schedule` | `gcc-cc1`   |     209.085 |      234.854 |     -12.33% |
| `ring-schedule` | `llvm`      |     764.467 |      845.403 |     -10.59% |
| `ring-schedule` | `clang-cpp` |     381.546 |      429.801 |     -12.65% |
| `ring-schedule` | `z3`        |     150.206 |      167.773 |     -11.70% |

The baseline preloaded-memory SHA estimate for the three large Clang libraries was 1218.252 ms. The direct-block
candidate advanced: `true`. The 16-word circular-schedule candidate was measured: `true` and advanced: `false`.

All empty, 55, 56, 63, 64, 65 and 129-byte irregular-streaming vectors, unaligned buffers and large-file digests matched
independent references. Read-only checksums were stable across repetitions.

## Prepared-image comparison

| Candidate      | Compiler | First baseline ms | First candidate ms | Improvement | Pairs | Warm regression |
| -------------- | -------- | ----------------: | -----------------: | ----------: | ----: | --------------: |
| `direct-block` | gcc      |          1323.674 |           1312.441 |       0.85% |   2/5 |        0.000 ms |
| `direct-block` | clang    |          3125.866 |           3025.359 |       3.22% |   4/5 |        2.345 ms |

Every diagnostic comparison preserved image-specific `D` and `N`, prepared-profile reuse, hash counts and bytes,
discovery probes, zero preparation build commands, zero managed module compilations, executable output and diagnostics.

## Decision

**Separately investigate:** at least one candidate showed positive but noisy or sub-threshold prepared compiler
movement. The fixed budget is exhausted, so production remains unchanged.

Production `sha256.h`, stable-read checks, metadata policy, digest bytes, schemas and interfaces remain unchanged. The
experiment-local patches are retained only to reproduce the measurements.

## Validation

- The harness compiled with strict C99 warnings in each measured image.
- Independent SHA-256 vectors and every measured file digest passed.
- `preparation_support_test`, `preparation_identity_test`, and `l1c_stage1_preparation_test` passed in the baseline and
  every measured candidate compiler build under the supported builder-image GCC toolchain.
- `python3 -m py_compile measure.py` and report verification passed.
- Final repository validation is recorded in the closed plan.

The raw archive contains exact build, test and benchmark output, plus image-time and runtime output when a candidate
advanced. `report.json.gz` contains all parsed samples and assertions.
