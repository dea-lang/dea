# Phase 5: warm-build attribution

- Date: 2026-10-16
- Scope: Debug-only compiler phase attribution and paired instrumentation controls.

## Selected approach

Retain coarse monotonic spans in the L0 compiler implementation, using a compiler-private native clock ABI. Existing
preparation observations cannot explain time spent after preparation returns. External command timing alone combines
frontend work and native subprocesses; the new spans measure those boundaries directly without changing preparation
identity or provider selection. More detailed semantic instrumentation is deferred until a measured workload requires
it.

At `-vvv`, `Compiler observation: ` records carry schema 1, event `span`, scope, parent, elapsed microseconds, and a
boolean success flag. Lower verbosity skips clocks and span allocations. Missing/backward clocks and integer overflow
produce a null duration. Completed spans are emitted once; early returns emit a failed partial span through their owner.
The reporter retains this stream and its parsing errors separately from preparation records, including on interrupted
commands.

The private clock translation unit enables POSIX feature macros and uses `clock_gettime(CLOCK_MONOTONIC)` on POSIX
hosts, or `QueryPerformanceCounter`/`QueryPerformanceFrequency` on Windows. It writes one native 32-bit seconds and
nanoseconds pair only after validating the clock and output capacity. No bootstrap-runtime policy or production
dependency changes are required.

The accounting boundaries are:

- `load-resolve`: source/interface reading, graph resolution, interface normalization and activation.
- `interface-loading`: read, parse, fingerprint validation and registration of an individual filesystem interface. This
  child is contained in `load-resolve` and ends before dependency recursion, so these child spans do not overlap.
- `application-analysis`: semantic analysis after loading/resolution, including name, signature, local and expression
  checks. Each analysis entry contributes its own duration, including the per-source reanalysis required by build/run.
- `c-generation`: backend construction, emission and backend cleanup for one module.
- `c-compilation`: the module host `system()` call, after shell command construction.
- `wrapper-c-compilation` and `linking`: the existing host-command executor, including shell command construction,
  execution, failure diagnostics and captured-output replay, after argument-vector construction.

An empty parent denotes a top-level compiler span. Warm-build accounting sums those compiler spans plus the existing
outer `native-identity-resolution` and `profile-validation` preparation spans. It excludes `interface-loading` and the
preparation `dea-identity-resolution` child from the sum. Cold preparation can itself generate compiler spans; those
streams must not be added indiscriminately. Host C compiler process startup and internal work are combined within each
native-command span. CLI startup, output publication, link-plan construction, analysis-result cleanup, process exit and
other uninstrumented work remain in the external residual. These measurements invoke the native compiler directly, so
shell-launcher overhead is not included.

## Correctness evidence

- Controlled L0 snapshots cover microsecond truncation, second rollover, backwards/missing clocks and both
  multiplication and addition overflow. Controlled parent/child intervals document inclusive accounting.
- Normal `timing_test` passes. Its ARC/memory trace passes with zero leaked object and string pointers (186 events).
- Managed-provider integration passes all expected compiler scopes, successful warm reuse, a child-sum/parent bound for
  every emitted load span, absence of compiler records below debug verbosity, and preserved `L1C-0010` plus a failed C
  compilation span for a deliberately missing header.
- Fifteen reporter tests pass, including independent compiler/preparation streams, null clocks, negative-duration
  rejection, failed spans, partial malformed records and summary rendering.
- Strict-C99 direct clock ABI checks pass with Linux GCC 14.2 and Clang 19.1.7, and macOS Apple Clang 17.0.0. They cover
  1,000 monotonic snapshots, valid fields and unchanged output for invalid/null/short buffers.
- Native macOS checks select `/usr/bin/clang`, Apple Clang 17.0.0, with the supported preparation behavior. Native
  Windows execution is unavailable; controlled null/backwards clock tests do not establish native Windows coverage.

## Measurement method

[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/measure.py][harness] creates an I/O
application and an imported collections application, verifies each executable's output outside the compilation timer,
and records every individual command duration. Debug and quiet controls use alternating baseline/candidate order across
seven repetitions, with compiler logs written inside the container. Log export happens after measurement. Both controls
use the same unrelated source/support snapshot, semantic interfaces, native target compiler and runtime flags; the
baseline restores the compiler instrumentation sites and omits their private clock helper. The resulting baseline and
candidate compilers are built independently from L0; no inherited historical L1 compiler is used as a control. Each has
its own prepared cache, primed before measurement. Guarded warm invocations must report zero native preparation build
commands and module compiles. The controls isolate the instrumentation from Phase 4 changes.

The Linux experiment uses `dea-preparation-investigation-clang:latest` with two CPUs and 2 GiB. Actual target compiler
executables/versions, platform, applications, individual spans, distributions, paired deltas and accounting residuals
are retained in the accompanying machine-readable report. Other investigation containers are paused or idle during the
warm matrix. Filesystem caches are warm; this is not a cold-filesystem benchmark or a deployment recommendation.

## Reproduction

[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/reproduce.sh][reproduce] constructs
both controls in an owned container, primes their separate caches and runs the final harness. After the normal L1
`make build`, run from the repository root with the retained local investigation image available:

```sh
sh l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/reproduce.sh /tmp/dea-phase5-reproduction
```

The output directory must be new. Seven repetitions reproduce the 112-invocation matrix; an optional final `1` selects a
16-invocation correctness smoke instead. The script exports compiler build logs, image metadata, Python setup output,
the measurement report and local invocation logs, then removes only its owned container and staging directory.

Three source patches make control construction explicit:

- [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/measured-preparation.patch][measured-support]
  first restores the shared support source before the later legacy-Clang compatibility policy. The recipe applies this
  overlay only inside isolated experiment copies. Every restored support file was checked byte for byte against the
  original experimental control source after integrating that independent change.

- [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/measured-discovery.patch][discovery-patch]
  restores the shared discovery source used by both experimental controls, before the final Apple-Clang-only guard and
  individual-probe label refinement. This patch applies only inside isolated experiment copies.

- [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/without-instrumentation.patch][baseline-patch]
  removes instrumentation from five compiler source files, the timing module and the private native clock helper for the
  baseline. The candidate retains the final numeric-clock instrumentation. Replayed production source trees were checked
  byte for byte against the retained experimental snapshots and the final private-clock overlay. The copied semantic
  interfaces and runtime headers also match the original controls.

The script pins the retained image identity and preserves `--user 0 --cpus 2 --memory 2g`, image defaults `HOME=/work`,
`TMPDIR=/work`, working directory `/work`, and bootstrap `/opt/dea/bin/l0c-stage2`. It uses `L0_CC=/usr/bin/gcc` and
`L0_CFLAGS="-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256"`, with the three support translation units in their
original order. L0 `--build` generates its C unit and invokes GCC; there was no separate manual C-generation or
native-compilation command. The expanded native flags are:

```text
-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256 -std=c99 -Wall -Wextra -Wno-unused -Wno-unused-parameter -pedantic-errors -O1 -I /opt/dea/shared/runtime
```

The original build commands were quiet. Their expanded argv and generated C were not archived; the implicit `-O1`
default was recovered with a verbose metadata probe in the unchanged image. Random L0 build-workspace names cannot be
recovered. The explicit L0 command, flags, source relations and image identity are retained here.

Both measured binaries use the common `--home /work/candidate/compiler --build /work/candidate/build`. The baseline is
built before Python setup and the final numeric candidate afterward, preserving the successful experiment's order. The
script does not replay the discarded unavailable-clock matrix. Python setup used the image's apt repositories and
produced Python 3.13.5; no apt repository snapshot or full package manifest was retained. The script records the
installed version, which can change on a later replay. Target compilers are explicitly `/usr/bin/gcc` and
`/usr/bin/clang`, with no extra target C options; original debug logs show `-O1` for both.

The bounded reconstruction check rebuilt both controls and passed 16 output checks with 128 successful numeric compiler
spans, quiet-mode gating and zero warm preparation build commands, module compiles, identity content reads or artifact
content reads. Its timings are excluded from the historical performance distributions.

## Warm-build results

[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/report.json.gz][report] retains all
112 successful warm builds and output checks, with 896 numeric compiler spans. Every debug invocation reports zero
native build commands, module compiles, identity content reads and artifact content reads. There are seven paired
repetitions per compiler/application/verbosity combination. All durations below are milliseconds and are medians of the
seven candidate debug builds; medians of components do not necessarily add to the median total.

| Compiler / application |  Total | Preparation outer | Load / resolve | Application analysis | C generation | Module C | Wrapper C |  Link | Uninstrumented | Accounted fraction |
| ---------------------- | -----: | ----------------: | -------------: | -------------------: | -----------: | -------: | --------: | ----: | -------------: | -----------------: |
| gcc / hello            |  564.9 |              35.1 |          182.1 |                 20.0 |          1.8 |     69.7 |      61.4 |  50.2 |          135.0 |              76.7% |
| gcc / collections      |  801.9 |              41.7 |          295.5 |                 37.7 |          7.1 |     84.3 |      67.1 |  66.7 |          195.5 |              76.1% |
| clang / hello          |  964.2 |             145.5 |          253.2 |                 26.0 |          2.7 |    124.2 |     107.9 | 136.3 |          170.1 |              82.5% |
| clang / collections    | 1073.8 |             153.8 |          322.0 |                 46.6 |          7.4 |    127.4 |     102.1 | 115.6 |          206.7 |              81.0% |

The recorded nonoverlapping boundaries account for 76.1-82.5% of elapsed time. The remaining 17.5-23.9% stays explicitly
uninstrumented; this phase does not assign that residual to a particular subsystem. It includes L1 process startup/exit,
CLI work, publication and cleanup outside the spans listed above. No further permanent granularity is needed to explain
the substantial majority of this workload.

Interface loading accounts for 167.8/266.2 ms in the GCC I/O/collections cases and 232.4/290.6 ms with Clang. It is
already contained in load/resolve, and therefore is excluded from the accounting sum. Native module compilation, wrapper
compilation and linking together also consume substantial warm time. Application analysis and C generation are smaller
in these examples.

## Instrumentation control

| Compiler / application | Quiet baseline median ms | Quiet candidate median ms | Median paired quiet delta | Debug baseline median ms | Debug candidate median ms | Median paired debug delta |
| ---------------------- | -----------------------: | ------------------------: | ------------------------: | -----------------------: | ------------------------: | ------------------------: |
| gcc / hello            |                    538.5 |                     524.2 |                    +0.52% |                    575.8 |                     564.9 |                    +0.13% |
| gcc / collections      |                    784.2 |                     785.5 |                    +0.80% |                    795.0 |                     801.9 |                    -0.67% |
| clang / hello          |                    940.4 |                     982.9 |                    +6.25% |                    960.8 |                     964.2 |                    +1.03% |
| clang / collections    |                   1063.2 |                    1068.3 |                    +0.57% |                   1063.6 |                    1073.8 |                    +5.84% |

Across the 28 matched pairs per verbosity, median paired deltas are +0.94% in quiet mode and +0.65% in debug mode.
Individual paired differences are much wider, including changes in both directions. Shared-host scheduling and
code-layout differences remain confounds; these samples do not establish a small overhead bound or an absence of
regressions. Quiet mode performs no timing allocations or clock reads, which is independently checked by the unit and
integration cases. The retained coarse instrumentation is useful for attribution; no performance improvement is claimed
for adding it.

## Clock compatibility finding

The first 112-build matrix passed output and native-reuse checks, but all 896 compiler durations were null. The
bootstrap runtime exposes its monotonic clock only when `CLOCK_MONOTONIC` is visible. Strict-C99 Linux builds without
the relevant feature-test macro hid that declaration. These samples cannot attribute compiler phase time and are
retained in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5/unavailable-clock-report.json.gz][unavailable].
The final native clock translation unit fixes this independently of bootstrap flags. The repeated matrix uses a
mandatory numeric-clock preflight before priming or timing. Historical null-clock samples are excluded from the final
numeric-clock distributions.

Frozen copies of the exact production clock function were exercised with simulated POSIX and Windows QPC callbacks under
AddressSanitizer and UndefinedBehaviorSanitizer. They cover callback failures, negative counters/time, nonpositive
frequency, seconds overflow, invalid nanoseconds, the `INT32_MAX` boundary, fractional QPC conversion, unsupported
clocks, invalid capacities, and unaligned output with prefix/suffix canaries. All passed. These are simulated branch
checks; native Windows execution remains unavailable. The live-source strict-C99 ABI test remains separate from these
frozen historical extracts. From the repository root, reproduce the extracts with:

```sh
phase5=l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase5
for source in "$phase5"/clock-probes/*.c; do
    /usr/bin/clang -std=c99 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined "$source" -o /tmp/dea-clock-probe
    /tmp/dea-clock-probe
done
```

## Follow-up and limits

The next frontend investigation should profile repeated interface reading/parsing/fingerprint validation inside
`interface-loading`, including the initial graph pass and required per-module pass. Any reuse must preserve provider
authority, validation and analysis ownership. The native-command spans justify separately profiling C compiler
startup/header processing and linking before choosing a native optimization. Application caching and persistent
compiler/deployment architecture remain outside this plan; no such policy is selected here.

The matrix uses warm local evidence in one Linux container, two small imported applications, and direct native compiler
execution. It does not measure cold filesystems, fresh-container portability, shell-launcher overhead, large application
scaling or native Windows performance. The controls isolate Phase 5 and do not establish the final combined
cold-preparation benefit of Phase 4. Python 3.13.5 was installed only in the disposable measurement container; no
production dependency was added. Raw logs stayed inside the container during timing and were exported after completion.
Report invocation records are recursively equal to the exported records; only experiment-context metadata was added, and
no string sanitization was required because all reported paths use generic Linux locations.

Repository JSON reports are lossless gzip copies of the generated JSON; decompressed bytes and recursive JSON equality
were verified. Reproduction commands write ordinary JSON before archival compression.

[baseline-patch]: without-instrumentation.patch
[discovery-patch]: measured-discovery.patch
[harness]: measure.py
[measured-support]: ../measured-preparation.patch
[report]: report.json.gz
[reproduce]: reproduce.sh
[unavailable]: unavailable-clock-report.json.gz
