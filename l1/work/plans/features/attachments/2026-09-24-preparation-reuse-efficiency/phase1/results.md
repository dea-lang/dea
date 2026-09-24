# Phase 1: Equivalent bundled-root selection

- Date: 2026-09-24
- Scope: L1 Stage 1; preparation reuse efficiency Phase 1 only.
- Status: Completed for Phase 1; platform/configuration limits are recorded below.

## Decision and alternatives

Selected automatic bundled-directory recognition with `--no-managed-stdlib` as an explicit source opt-out. The existing
resolver already proves directory identity and preserves ordered root selection, so no new identity mechanism is needed.
Managed opt-in was rejected because ordinary equivalent explicit roots would remain unnecessarily source-backed.
Automatic recognition without an opt-out was rejected because bootstrap and native test helpers intentionally require
source imports. Both caller families now select that behavior explicitly. This is a compatibility decision supported by
caller inspection, not inferred from timing results.

The option disables automatic bundled interfaces, not explicit `-I` authority or native runtime preparation. It is valid
in source-resolving modes; standalone link and explicit preparation reject it with `L1C-2157`. No new diagnostics, cache
format, dependency, storage index, synchronization, or trust boundary was introduced. Maintenance consists of one CLI
boolean and explicit caller intent; the existing resolver supplies alias and precedence behavior.

## Measurement method

The implementation-time baseline and changed compiler are rebuilt from their respective source snapshots using the same
installed L0 compiler, `l1-test` builder, and retained Debian investigation runtime image. The original investigation
attachments are unchanged. The new compiler binaries naturally have different Dea/native keys; equality is required
between scenarios within each toolchain, not between different compiler builds.

The [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/Dockerfile][dockerfile] rebuilds
semantic inputs and prepares GCC and Clang profiles at image construction time. The templates are readable to the
unprivileged consumer. Image-build metadata may require ordinary runtime revalidation; two warmup invocations precede
measured implicit and explicit pairs in every container.

[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/measure.py][measurement-driver] runs
five independent containers per compiler, toolchain variant, and verbosity setting (40 containers). Each executes a
warmup pair, an implicit pair, and an explicit bundled-root pair. Changed-toolchain containers also execute an
explicit-root opt-out pair. Baseline/changed order alternates by repetition. Within each container the scenario order is
fixed. These are fresh containers with warm host storage, not cold filesystem trials.

Every container has one CPU, 256 MiB memory and memory-swap limit, 64 PIDs, no network, a read-only root, no
capabilities, no-new-privileges, UID/GID 65534, and a writable executable 64 MiB `/work` tmpfs. The fixture is the
existing [l1/examples/hello.l1][hello], mounted read-only at `/input/hello.l1`. Its complete 25-line greeting multiset
is checked after each compilation, outside the timed interval. Capture is to `/work/capture`; logs are exported after
the sequence. Each compilation uses `--build --c-options=-O0 --no-auto-prepare --project-root /input`, with the selected
compiler and absolute input/output paths. Debug cases add only `-vvv`; opt-out cases add `--no-managed-stdlib` to
explicit selection.

The retained `/opt/dea/bin/investigation-timer` measures complete compiler subprocess duration with a monotonic clock.
Preparation counters, provider events, native keys, and imported-source analyses are read only in debug cases; quiet
values remain unknown. Timings are neither summed with nested preparation spans nor asserted by correctness tests.
Individual timing/resource records, provider paths, native keys, counters, command arguments, and aggregates are
retained in the new report. Original raw logs remain local build artifacts; the report stores the derived observations
and verified output status, not full stderr or executable outputs.

To reproduce, supply baseline/changed source trees as Docker build contexts to this Dockerfile, tagging their resulting
images `dea-phase1-baseline:local` and `dea-phase1-changed:local`. Run the measurement driver with repository root and a
Docker-visible writable output directory as its two positional arguments. This requires the named local builder and
investigation images, including the timer; it is not a standalone image reconstruction package. The parent investigation
describes rebuilding the retained runtime/toolchain environment.

Initial setup attempts found a Colima-invisible temporary bind mount and unreadable freshly baked templates. Both were
corrected before retained cases; failed setup attempts are not timing samples. One new source-target regression
initially expected provider events from interface-emission mode; it now checks generated-C mode, which emits those
records.

## Results

All 40 containers completed: 280 successful compiler invocations and 280 separate output checks. The 140 debug
invocations all reported zero native preparation build commands and zero managed module compilations. Native identity
was constant across scenarios and repetitions within each compiler/toolchain variant. Explicit managed selection
preserved the implicit provider paths and origins. Historical explicit selection and the new opt-out each analyzed
eleven imported sources per invocation; equivalent explicit roots after the change analyzed zero.

Seconds below are median (minimum-maximum), with ten measurements from five independent pairs per row. The two
invocations within each pair share a container and are not independent trials. All samples, including outliers, remain
in [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/report.json][measurements].

| Compiler/control | Baseline explicit   | Changed explicit    | Changed implicit    | Changed opt-out     |
| ---------------- | ------------------- | ------------------- | ------------------- | ------------------- |
| GCC / debug      | 3.739 (3.123-4.881) | 0.628 (0.411-0.740) | 0.653 (0.632-0.926) | 3.705 (3.031-4.389) |
| GCC / quiet      | 3.740 (2.607-4.586) | 0.568 (0.474-0.702) | 0.586 (0.477-0.679) | 3.841 (3.216-4.726) |
| CLANG / debug    | 3.908 (2.855-4.759) | 0.704 (0.525-0.817) | 0.780 (0.647-0.936) | 3.597 (3.135-4.352) |
| CLANG / quiet    | 3.717 (3.358-4.452) | 0.679 (0.536-0.883) | 0.754 (0.546-0.993) | 3.963 (3.028-5.131) |

Debug explicit-root medians fell by 83.2% for GCC and 82.0% for Clang; quiet controls fell by 84.8% and 81.7%. The
changed explicit-root distributions are comparable to implicit selection, while opt-out retains the prior source
compilation cost. This benefit is outside the unchanged native preparation counters. The data does not establish a
general instrumentation-overhead bound, and differences between implicit medians are not attributed to this change.

The runtime uses GCC 14.2.0 and Clang 19.1.7 on Linux `6.8.0-64-generic` through Docker 29.7.2/Colima. Exact image
identities and compiler/timer content digests are in the report. Production compiler source and support inputs in the
measured changed snapshot were checked byte-for-byte against the implementation. No OOM kills or command timeouts
occurred. The full test suite was held until the timing matrix finished to avoid concurrent validation load; the first
few cases overlapped only the tail of focused validation. No claim of an otherwise idle host is made.

## Validation and limits

`make -C l1 test-all` completed successfully: all 84 Stage 1 normal cases, environment stackability, four examples, the
Docker/Wine runner tests, all 46 default ARC/memory trace cases, and both child trace fixtures passed. All trace cases
reported zero leaked object/string pointers. The intentionally slow `math_runtime_compile_test` is excluded from the
default trace sweep; its normal case passed. The selected tier is full validation because source-provider helpers and
resolver/CLI cases participate in ARC/memory trace execution. The invocation uses `L1_CC=clang`, `L1_RUNTIME_CC=clang`,
four normal and four trace workers, and an explicit `L1_BOOTSTRAP_L0C` pointing at the existing local upstream L0 Stage
2 compiler. The worktree built fresh L1 artifacts before focused validation. No root/L0 functional behavior changed. The
successful full-suite result is reused for finalization because subsequent edits affect only documentation/evidence; no
tested compiler, test, build, or dependency input changed after it completed.

The full command, with local directories supplied by the caller, is:

```sh
UV_CACHE_DIR="$TASK_UV_CACHE" L1_BOOTSTRAP_L0C="$TASK_L0C" \
  L1_CC=clang L1_RUNTIME_CC=clang L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4 make -C l1 test-all
```

Focused validation also passed the Linux bootstrap/alias regression and the reporter unit suite (13 tests). Final
ADR-impact, repository-link, JSON parsing, evidence path sanitization, staged whitespace, and pre-commit checks passed.
The original three evidence attachments were verified byte-identical to the baseline.

Focused tests cover default/explicit/relative/dot-directory selections and supported directory symlinks; ordered custom
roots, copied trees, project roots, unavailable directory identity, explicit-interface precedence, requested source
targets, missing/corrupt interfaces, independent native-preparation controls, source bootstrap, and installed inputs.
Reporter falsification cases reject key changes, accidental source analysis, missing provider events, and an ineffective
source opt-out. No real-time threshold is used.

The Linux bootstrap/alias/precedence regression passed in the rebuilt builder image. An initial reporter run placed its
fixture on the Colima shared bind mount and hit the existing `L1C-2151` input-stability rejection during publication.
Reporter validation was moved to container-local storage with result export after completion; validation was not
weakened.

An initial sandboxed macOS identity test could not read `kern.osversion` through `sysctl`; the identity test passed in
the full normal suite with host access. A new installed-input assertion matched unrelated debug text and was corrected
to check actual stdlib/runtime preparation. No identity or cache validation was weakened to accommodate these
environment/test issues.

End-to-end `check_preparation_reuse.py --observability-scenarios --expect available` passed all six scenarios with Linux
GCC 12.2 and host Apple Clang 17, including ordinary invalidation after the scenario pairs. Explicit-root providers and
native keys matched the warm baseline; the source opt-out changed providers as intended. The builder's Clang 14 cannot
satisfy the runtime archiver probe and correctly reported `unsupported`; its requested `available` expectation therefore
failed. No workaround was added. The performance matrix independently exercised supported Clang 19. Condensed outcomes
are retained in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/reporter-validation.json][reporter-validation].

Native Windows validation and Windows directory junction behavior have not been exercised in this macOS session; the
bootstrap regression includes a junction case when run on Windows and reports unavailable symlink/junction creation.

[dockerfile]: Dockerfile
[hello]: ../../../../../../examples/hello.l1
[measurement-driver]: measure.py
[measurements]: report.json
[reporter-validation]: reporter-validation.json
