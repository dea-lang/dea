# Phase 4 portable SHA-256 compression comparison

- Date: 2026-10-16
- Candidate: Eight-round unrolling with rotated compression-variable roles.
- Consumer outcome: Separately investigate; inconclusive under the fixed adoption gate.
- Production changes: None.

## Method

This final bounded candidate optimizes the compression function itself. It preserves the current 64-word message
schedule, complete byte coverage, streaming update loop, digest encoding, and stable reader. Each group of eight rounds
uses rotated scalar arguments to avoid explicit per-round state moves. The experiment generates its header from the
retained baseline implementation; it adds no imported implementation, license, dependency, CPU requirement, or platform
dispatch. The earlier complete-block and circular-schedule studies remain independent alternatives.

The comparison uses only `current` and `unrolled` backends. The licensed `hash-baseline-sha256.h` snapshot fixes the
preoptimization source for both this comparison and earlier backend reproductions, independently of later production
changes. Each receives five interleaved repetitions, reversing order on alternate repetitions, with preloaded-memory
SHA-256 in 64 KiB and irregular chunks plus complete stable-file hashing. Linux uses the retained local image with GCC
14.2.0, `-O1`, one CPU, 512 MiB, and no network; inputs include the actual `cc1`, LLVM, Clang C++, and Z3 files and 4
KiB/8 MiB controls. macOS Intel uses Apple Clang 17.0.0, `-O2`, the two controls, and its 272,034,048-byte compiler
executable. Timing starts after the separate Phase 5 warm matrix releases the measurement window. No cold filesystem
cache is claimed.

Each backend in both environments passed strict C99 warning checks, independent standard and unaligned streaming
vectors, unchanged-file and clean-short-read acceptance, and partial-error/content-mutation/missing-file rejection. The
isolated correctness reports contain 48 vector records and four backend reader-check records. Timed binaries do not
contain read-failure interposition. These backends use fixed context storage and introduce no heap context lifecycle.
Production SHA-256 remains unchanged after the completed consumer gate below.

## Microbenchmarks

Complete stable-file hash medians, in milliseconds:

| Environment | Input         |  Current | Unrolled | Improvement |
| ----------- | ------------- | -------: | -------: | ----------: |
| Linux       | 4 KiB         |    1.038 |    1.156 |     -11.30% |
| Linux       | 8 MiB         |   54.367 |   50.676 |       6.79% |
| Linux       | GCC `cc1`     |  185.603 |  152.693 |      17.73% |
| Linux       | LLVM          |  737.214 |  596.265 |      19.12% |
| Linux       | Clang C++     |  386.370 |  345.011 |      10.70% |
| Linux       | Z3            |  148.352 |  132.014 |      11.01% |
| macOS Intel | 4 KiB         |    0.127 |    0.130 |      -2.36% |
| macOS Intel | 8 MiB         |   36.635 |   35.407 |       3.35% |
| macOS Intel | Host compiler | 1307.271 | 1187.172 |       9.19% |

All five pairs improved for Linux `cc1`, Clang C++, and Z3; four improved for LLVM. Summed large-input stable medians
fell from 1457.539 to 1225.983 ms (15.89%). Memory-only 64 KiB streaming improved by 14.81%, 13.19%, 17.25%, and 13.71%,
respectively, with all five pairs positive for each large Linux input. macOS host-compiler memory-only hashing improved
by 6.06%. The 288 timing samples and 48 vector records are retained in `hash-portable-linux.json.gz` and
`hash-portable-macos.json.gz` without overwriting the earlier matrix. These microbenchmarks justify advancing this one
candidate to the fixed actual-consumer gate; they do not by themselves select a production change.

## Actual consumer gate

The isolated consumer comparison used Debian GCC 14.2.0 and Clang 19.1.7 in the existing
`dea-phase3-relaxed-candidate-validation:local` image. One common canonical compiler C translation unit was compiled
once at `-O0`, with basic runtime checks and a quarantine bound of 256. Both controls linked that same object with their
own preparation support at `-O1`, matching the earlier Linux support-build optimization. They used the same copied
compiler home, semantic interfaces, runtime headers, and downstream `--c-options=-O0`. Each compiler/backend pair built
its own prepared profile and retained its own `D` and `N` throughout the comparison.

Construction initially ran on a Colima shared host bind mount and conservatively rejected completion with `L1C-2151`,
reporting a changed `std/unit.l1m` preparation input. That setup produced no timing samples. Reusing the exact compiled
binaries with copied inputs on the container's native filesystem passed construction and the later checks. The precise
cause of the shared-mount rejection was not isolated; its complete diagnostic log is retained. Build construction had a
1 GiB limit. Every measured request used one CPU, 256 MiB, no swap, no network, and native container storage. The
separate warm-attribution matrix had finished before these measurements began.

Five quiet interleaved current/unrolled pairs per downstream compiler each removed the complete disposable memo
directory before the first request, then immediately ran one warm request. Pair order reversed on alternate repetitions.
A separate debug cold/warm pair per compiler/backend verified attribution. All 48 builds and executable outputs passed;
normal builds emitted no diagnostics.

| Compiler | First current ms | First unrolled ms | Difference of medians | Improvement | Improved pairs | Warm current ms | Warm unrolled ms |
| -------- | ---------------: | ----------------: | --------------------: | ----------: | -------------: | --------------: | ---------------: |
| GCC      |         1381.435 |          1378.782 |              2.653 ms |       0.19% |            3/5 |         721.015 |          672.279 |
| Clang    |         2793.911 |          2691.653 |            102.258 ms |       3.66% |            5/5 |         721.843 |          774.538 |

The table uses the difference between each distribution's median, exactly as the earlier retained consumer gate did.
This is distinct from the median of the five paired differences: 0.383 ms for GCC and 142.298 ms for Clang. The latter
Clang value also remains below 150 ms. The report retains every paired difference and both summaries. GCC's quiet
first-request samples ranged from 1376.138 to 1950.797 ms for current and 1276.741 to 1780.978 ms for unrolled. Clang's
warm unrolled samples ranged from 771.014 to 922.482 ms. Its warm median regressed by 52.694 ms and 7.30%, within the
predeclared 100 ms and 10% budget; the variation was retained without extending repetitions.

Separate debug checks preserved every own-profile key, zero native build commands and managed module compilations, and
identical noncompiler identity inputs. Native identities differed only in `D` and its compiler-bearing Dea input
description. The two binaries differ by 4096 bytes, explaining the entire difference in Dea-input hash bytes; all 194
input records remain covered. Cold toolchain hashing covered 103 files/46,113,607 bytes under GCC and 122
files/240,348,446 bytes under Clang for either backend. Both read 47 artifacts, with identical artifact byte coverage
per downstream compiler. Cold probe counts were 43/46 for GCC/Clang, and warm counts were 1/2. Every warm request
performed zero identity/artifact content reads.

**Separately investigate:** Clang meets the percentage and pair-count bounds but misses the required 150 ms absolute
gain; GCC misses its 70 ms and 3% improvement bounds. The fixed budget is exhausted. Retain the existing portable
dependency-free SHA-256 backend, and defer unrolling and platform-library adoption. This result resolves the backend
choice for this plan without weakening content coverage, stable reads, metadata validation, or the adoption gate.

The complete report is
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-portable-consumer.json.gz][consumer].
The normalized raw archive
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-portable-consumer-raw-logs.tar.gz][raw]
retains the 107 construction/request logs and reports, including the rejected shared-mount setup. No native Windows or
macOS ARM execution was available. No additional consumer pairs were run after this outcome.

## Reproduction

The harnesses restore the measured preparation support in isolated copies with
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/measured-preparation.patch][measured-support].
This removes the later legacy-Clang compatibility policy before constructing either hash control. Actual consumers also
restore shared compiler-home support inputs. Production sources and historical report data remain unchanged. Patch
replay was checked byte for byte against the original control support source.

Add `--portable-unroll` to the retained `hash-measure.py` driver. Use distinct output names to preserve the original
comparison. From the repository root:

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --portable-unroll --docker-image dea-sha256-benchmark-baseline:local --optimization 1 --label linux-x86_64-gcc14 --output /tmp/hash-portable-linux.json
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --portable-unroll --reader-only --docker-image dea-sha256-benchmark-baseline:local --optimization 1 --label linux-x86_64-gcc14 --output /tmp/hash-portable-correctness-linux.json
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --portable-unroll --label macos-intel-apple-clang17 --output /tmp/hash-portable-macos.json
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --portable-unroll --reader-only --label macos-intel-apple-clang17 --output /tmp/hash-portable-correctness-macos.json
```

The microbenchmark reports are generated projections of parsed output with derived summaries. Exact path strings become
stable `<input:NAME>` aliases. The driver verifies recursive equality after reversing that string-only replacement; all
container shapes and nonstring values remain unchanged. Raw microbenchmark stdout is not retained, so this does not
claim equality to a raw-log payload. Reports contain no private host input paths or source revisions.

`hash-consumer.py` reproduces the separate compiler consumer gate. Run its `--mode build` followed by `--mode measure`
inside one retained native Linux container, passing the repository root, one common L0-generated canonical compiler C
file, and an empty native output directory as its three positional arguments. Build at the documented 1 GiB limit, then
apply the 256 MiB/no-swap limit before measuring. Copy the completed report/logs out afterward. The original run reused
its already compiled binaries after the shared-mount rejection; `--reuse-binaries` preserves that path without
recompiling either control. The script does not modify production sources. Its current baseline and candidate always
come from the retained header snapshot, independently of subsequent production changes.

Repository JSON reports are lossless gzip copies of the generated JSON; decompressed bytes and recursive JSON equality
were verified. Reproduction commands write ordinary JSON before archival compression.

[consumer]: hash-portable-consumer.json.gz
[measured-support]: ../measured-preparation.patch
[raw]: hash-portable-consumer-raw-logs.tar.gz
