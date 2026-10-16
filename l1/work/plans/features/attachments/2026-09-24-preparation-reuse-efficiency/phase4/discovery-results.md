# Phase 4: Discovery probe comparison

- Date: 2026-10-16
- Status: Completed discovery comparison and scoped implementation.
- Scope: Retain complete-observation invalidation; batch dependency queries only for Apple Clang on macOS.

## Decision and evidence boundary

Retain the existing whole-observation invalidation and metadata policy. For measured Apple Clang on macOS, issue one
dependency command for four separately materialized generated-C configurations, and another for all ten runtime
translation units. Application and runtime argument policies remain separate. Each source is still preprocessed
independently by the host compiler. GCC, upstream Clang, TinyCC, Linux and Windows retain individual dependency probes;
their original per-source debug purpose labels remain available.

The broader batching experiment reduced outer probe counts on every tested adapter, but it did not establish portable
performance improvement. Linux GCC results varied, while the initial Linux Clang comparison regressed. A repeat with the
competing Linux builder paused overlapped the root's twelve-worker native compiler suite and was substantially slower
and more variable. It cannot establish a clean improvement or absence of regression. The implementation therefore
enables batching only for the host/compiler combination with both support-level and actual-consumer benefit. Native
Windows execution was unavailable; no Windows speed claim or batching default is introduced.

Finer-grained invalidation was compared structurally and deferred rather than prototyped as a new persistent schema.
Current evidence stores one union of search dependencies and selected paths, including absent candidates and directories
that can affect several compiler queries. Targeted rechecking would require reliable provenance for every search
decision, option/configuration input, runtime translation unit and generated-C branch. A changed shared search root
could still require every query. The selected batching change reduces repeated driver work without introducing a new
partial-observation authority boundary. These experiments do not establish that finer-grained invalidation cannot help a
future workload.

## Coverage and fallback

The batch decoder accepts a fixed Make target only when every requested source begins exactly one rule. It rejects
missing, duplicate, unexpected and malformed rules. It decodes prerequisites using the existing Make escaping rules,
retains all selected files and parent/search-directory observations, and excludes only the owned scratch inputs as
before. Temporary path/dependency sets are merged only after complete successful validation.

An unsupported or failed batch, timeout, aggregate capture overflow, ambiguous output or unavailable prerequisite
discards that batch's temporary evidence and retries the existing individual depfile workflow. The existing four-MiB
probe-output bound remains in force; each fallback dependency file retains its four-MiB read bound. Thus a large
combined response does not reduce previously supported individual-response capacity. Individual failure diagnostics
still use `L1C-2154`. A debug decision records `dependency-probe-batch` / `sequential-fallback`; normal output is
unchanged.

All four generated configurations retain independent real/float header branches. All ten runtime units, including the
trace implementation, participate with runtime flags and public/internal runtime includes. Existing negative-candidate
and header-shadow observations remain unchanged. Full native identities and digest counts were equal between the
baseline and candidate support controls within each compiler/platform configuration.

## Measurements

Support measurements use independently built baseline/candidate preparation support, fixed compiler-owned inputs and
semantic interfaces, an identical digest backend and a fixed self-input. Cold means absent validation evidence, with the
host filesystem already warm. Partial invalidation adds an unrelated file to an observed generated-header search
directory after a warm request; it forces rediscovery while retaining valid file digests. Three interleaved pairs per
configuration retain every request and probe duration in the compressed JSON reports.

The Linux image actually supplies GCC 14.2.0 and upstream Clang 19.1.7 on x86-64. Runs use one CPU, 256 MiB memory with
no additional swap, 64 PIDs, no network, a read-only source mount and a 128-MiB executable work tmpfs. The macOS host is
Intel and actually selects `/usr/bin/clang`, Apple Clang 17.0.0; its required `--no-default-config` behavior succeeded.
Concurrent host work limits elapsed-time precision. The builder-paused repeat is retained separately instead of being
combined with the first distribution.

| Support configuration       | Scenario             | Baseline median | Batched median | Outer probes |
| --------------------------- | -------------------- | --------------: | -------------: | ------------ |
| macOS Apple Clang 17        | Cold evidence        |         4.366 s |        3.540 s | 28 to 16     |
| macOS Apple Clang 17        | Partial invalidation |         2.359 s |        1.478 s | 28 to 16     |
| Linux GCC 14, initial run   | Cold evidence        |         1.797 s |        2.222 s | 43 to 31     |
| Linux GCC 14, initial run   | Partial invalidation |         1.028 s |        0.970 s | 43 to 31     |
| Linux Clang 19, initial run | Cold evidence        |         3.908 s |        4.253 s | 46 to 34     |
| Linux Clang 19, initial run | Partial invalidation |         1.494 s |        1.700 s | 46 to 34     |

Every cold support request hashes the same bytes in both policies: 273,776,480 toolchain bytes on macOS, 46,113,119 for
Linux GCC and 240,347,958 for Linux Clang. The Linux inputs include the 34,148,896-byte GCC `cc1`, 71,043,800-byte Clang
library, 129,673,080-byte LLVM library and 27,751,664-byte Z3 library. Every warm and partial-invalidation request
hashes zero bytes. Warm probe counts remain four on macOS, one for Linux GCC and two for Linux Clang. Timing variation
does not establish a warm-path speedup.

An external Linux loader observer, run separately from all timing measurements, records actual dynamically loaded
process images for two representative dependency inputs. Separate GCC commands load four images (two drivers and two
`cc1` processes); one batch loads three. Separate Clang commands load two images, while one batch loads three (driver
and two separate `-cc1` images). This explains why fewer outer probes do not imply fewer process startups. The
[LLVM 19.1.7 driver source][clang-driver] independently shows that multiple jobs disable in-process `cc1` execution. The
observer retains the same compiler arguments, but its `LD_PRELOAD` is a diagnostic control only and is absent from the
measured production-support requests. Frontend preprocessing work remains necessary for every translation unit.

Actual macOS consumer controls compile the same current generated L1 frontend object once with `-O0`, then link each
preparation implementation at `-O2`. They use copied stable compiler inputs, matching semantic interfaces, separately
prepared native profiles, an application importing `std.io`, application C options `-O0` and `--no-auto-prepare`. Cold
requests remove memos while retaining completed profiles. Every resulting executable prints exactly `discovery-ok`. All
eighteen debug requests record zero preparation build commands and managed-module compiles; eighteen ordinary-output
controls have empty compiler stdout/stderr and the same successful executable output.

| Actual consumer | Scenario             | Baseline median | Batched median | Improvement |
| --------------- | -------------------- | --------------: | -------------: | ----------: |
| Debug records   | Cold evidence        |         6.870 s |        6.114 s |       11.0% |
| Debug records   | Partial invalidation |         4.144 s |        3.304 s |       20.3% |
| Ordinary output | Cold evidence        |         5.318 s |        4.402 s |       17.2% |
| Ordinary output | Partial invalidation |         3.486 s |        2.647 s |       24.1% |

Warm debug medians are 1.622/1.661 seconds and ordinary-output medians 1.281/1.310 seconds. Batching is not used on the
warm path; these small differences are reported without a warm-performance conclusion. The controls demonstrate actual
managed-consumer benefit and ordinary-output preservation for this compiler construction, not fully optimized compiler
throughput, native Windows behavior or a universal adapter benefit. The measured experimental implementation and final
scoped implementation take the same batching path on this Apple Clang configuration.

## Reproduction and validation

The retained patches reconstruct the original measured support without requiring a particular source revision.
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/measured-preparation.patch][measured-support]
first removes the later legacy-Clang compatibility policy from isolated experiment copies. The measurement script then
reverses `discovery-batching.patch` only for the baseline, retaining the same digest backend. Patch replay and restored
support bytes were checked against the original measured source. The script requires a fresh output directory. The
actual-consumer script also restores the shared compiler-home support inputs before preparing either control.
`--all-adapters-experiment` changes only the temporary candidate copy to reproduce the rejected broader experiment; it
is not a compiler option or production policy.

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-measure.py \
  . l1/build/discovery-macos-fresh --native
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-measure.py \
  . l1/build/discovery-linux-fresh --all-adapters-experiment
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-consumer.py \
  . l1/build/discovery-macos-fresh /absolute/path/to/current-l1c.c l1/build/discovery-consumer-fresh \
  --frontend-optimization=-O0
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-quiet-consumer.py \
  l1/build/discovery-consumer-fresh
sh l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-process-starts.sh .
```

Generate the shared C input with the explicitly selected supported L0 bootstrap compiler in `l1/`, using `--gen`, the
canonical `compiler/src` project root, `-o /absolute/path/to/current-l1c.c` and `l1c`. The three native support files
reported by `compiler_support_args()` in `l1/scripts/build_l1c.py` are supplied during native linking in the consumer
script; `--gen` does not accept `--c-source`. The same monolithic generated C is used for both consumer implementations.

Run the final process-start command inside the Linux measurement image, with the repository mounted read-only. It is an
observation command rather than a timed benchmark and requires GCC/Clang from that image.

Focused validation passed:

- Complete `preparation_identity_test.py` under Apple Clang, including existing negative search candidates and new
  independently changed headers for every runtime translation unit and every generated-C real/float combination.
- Strict-C99 `preparation_dependencies_test.c` under Apple Clang and Linux GCC 14. The fixture covers incomplete,
  duplicate, malformed and unavailable dependency evidence, aggregate overflow, timeout and failure fallback.
- Final scoped fixture under Apple Clang with AddressSanitizer and UndefinedBehaviorSanitizer, including policy guards
  and native POSIX literal-backslash source comparisons. Windows-only mixed-separator/case/space cases are present in
  the native fixture and remain unexecuted locally; synthetic token coverage does not establish native Windows
  validation.
- Final scoped Apple Clang support comparison: equal complete identities and content-read counts, 28 to 16 probes.
- Retained JSON parsing, lossless compressed recursive equality, string-only local-path sanitization and patch replay.

The complete identity suite ran before the final adapter guard and per-source purpose-label restoration. Those final
changes are covered by the scoped native fixture and final production-support identity comparison; batching behavior on
the validated Apple Clang configuration is unchanged. Root-owned normal and trace validation is recorded by the parent
plan rather than duplicated here.

Reports retain individual timings and counts. The process-start transcript trims trailing display separators without
changing argument text. Native/file digests and Docker image identity are evidence values, not source revision
identifiers. Older phase attachments remain unchanged.

## Evidence files

- `discovery-macos.json.gz`: 18 support requests and full-identity equality checks.
- `discovery-linux.json.gz`: 36 initial Linux support requests; broader candidate not adopted.
- `discovery-linux-builder-paused.json.gz`: 36 builder-paused support requests with concurrent native-suite contention.
- `discovery-consumer-debug.json.gz` and `discovery-consumer-quiet.json.gz`: eighteen actual consumers each.
- `discovery-batching.patch`: measured discovery change, usable in reverse after the shared measured-support overlay.
- `discovery-process-starts.c` and `discovery-process-starts.txt`: separate external process-start observation.

[clang-driver]: https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-19.1.7/clang/lib/Driver/Driver.cpp
[measured-support]: ../measured-preparation.patch
