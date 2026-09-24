# Phase 2: Disposable digest-seed hints

- Date: 2026-09-24
- Scope: L1 Stage 1 preparation reuse efficiency, Phase 2 only.
- Status: Completed for the validated macOS/Linux configurations; native Windows execution unavailable.

## Decision

Use one disposable hint to locate an existing memo's file records. Keep discovery cwd-sensitive and validate every
selected donor record against current reliable metadata. Copy accepted digests into the new self-contained memo. This
uses existing record construction rather than adding a separate digest store. No locks, writer coordination, merging,
history, directory scans, recovery service or cwd-independence classifier were added.

The accepted implementation plan replaced the earlier prototype-comparison gate. A separate digest store and multiple
donors remain possible future optimizations if measured workloads justify their cost; neither was prototyped or
benchmarked here. Cwd-independent observation reuse is deliberately outside this phase, with no proof investigation
required for completion.

Hints use the existing versioned JSON convention, with schema 1, kind `input-digest-seed` and a 64-hex-character
`memo_key`. They are keyed by the complete discovery selection except cwd, including the compiler-content identity.
Publication follows a successful eligible toolchain-memo write and is best-effort. Unknown formats, unusable files,
missing donors, stale evidence and failed hint writes reduce reuse without becoming compiler errors. Actual source
failures retain their existing diagnostics. JSON record copying does not expose a recoverable failure return; the
existing allocation-failure policy is unchanged.

There is one small hint per configuration excluding cwd. Existing memo storage continues to grow with distinct
selections; automatic reclamation is not introduced. A single donor can miss opportunities when different directories
select different file sets. Deleting a donor does not invalidate records already copied into another memo.

## Measurement method

The baseline is the implementation-time source snapshot, saved before production edits. Baseline and changed Linux
images are built with the existing
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase1/Dockerfile][dockerfile], using the
retained `l1-test` builder and `dea-preparation-investigation-clang` runtime image. Image tags are
`dea-phase2-baseline:local` and `dea-phase2-changed:local`. Each image prepares GCC and Clang native profiles before
runtime measurement. Different compiler builds naturally have different Dea/native keys; identity equality is checked
within each build's scenarios.

[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase2/measure.py][driver] runs three
independent containers per compiler, implementation and verbosity, alternating baseline/changed order by repetition.
Each container runs a warmup pair, a measured warm pair in `/work`, and a pair in `/work/other`. Source, project and
output paths are absolute. Every compilation uses `--no-auto-prepare`; output is verified separately from timing. Debug
runs add only `-vvv`. The first changed-cwd invocation is reported separately from the second.

Each container has one CPU, 256 MiB memory and memory-swap limits, 64 PIDs, no network, a read-only root, no
capabilities, no-new-privileges, UID/GID 65534, and an executable 64 MiB `/work` tmpfs. The same 25-line hello example
is used for all output checks. Capture is local to `/work`; export occurs after the sequence. These are fresh containers
with warm host storage, not cold filesystem experiments. Nested probe/hash durations are not added to parent preparation
spans or total compiler duration.

Run the driver with the repository root and a Docker-visible writable output directory as its positional arguments. The
original investigation and Phase 1 attachments remain unchanged. Raw captures stay in local build artifacts; retained
Phase 2 JSON records contain individual timings, counters, per-file changed-cwd evidence, selected keys, probe purposes,
provider events, storage inventories and output-check status.

## Measurements

All 24 containers completed successfully: 144 compiler invocations and 144 separately verified program outputs. The 72
debug invocations reported zero native preparation build commands and zero managed module compilations. Native keys were
constant across cwd scenarios and repetitions within each compiler/implementation. All memory-event reports had zero OOM
events; there were no timer timeouts. Timed runs began after the full local suite and Linux regressions finished. No
otherwise-idle-host guarantee is made.

Seconds below are median (minimum-maximum). First-cwd columns contain three independent container observations per row;
warm columns combine both measured warm invocations from each of those containers (six observations, paired within
containers). All samples and individual summaries are retained in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase2/report.json][measurements].

| Compiler/control | Baseline first cwd  | Changed first cwd   | Median reduction | Baseline warm       | Changed warm        |
| ---------------- | ------------------- | ------------------- | ---------------- | ------------------- | ------------------- |
| GCC / debug      | 1.210 (1.032-1.247) | 0.847 (0.791-0.916) | 30.0%            | 0.418 (0.393-0.703) | 0.442 (0.398-0.498) |
| GCC / quiet      | 1.051 (1.008-1.232) | 0.931 (0.757-0.936) | 11.4%            | 0.400 (0.390-0.449) | 0.409 (0.379-0.454) |
| CLANG / debug    | 3.005 (2.439-3.039) | 1.373 (1.323-1.491) | 54.3%            | 0.558 (0.475-0.658) | 0.534 (0.523-0.566) |
| CLANG / quiet    | 2.769 (2.613-2.811) | 1.323 (1.318-1.345) | 52.2%            | 0.531 (0.495-0.559) | 0.532 (0.518-0.551) |

Every first changed-cwd debug build avoided all toolchain hashing: GCC went from 46,112,953 bytes to zero, and Clang
from 240,347,792 bytes to zero. GCC reused 103 donor file records and Clang 122. Discovery remained active with exactly
43 GCC probes and 46 Clang probes in both implementations. Per-file reuse/hash reasons and probe purposes are retained
in the JSON. Subsequent cwd invocations used their own saved memos.

Each changed container retained two digest-seed hints (the two prepared compiler configurations), each 117 bytes, for
234 bytes of hint contents total. Cwd changes added no hints. The baseline had none. These counts exclude filesystem
block/directory overhead; complete memo filename/size inventories are retained in the JSON. Existing cwd-specific memo
records still accumulate. Hint lookup time is not separately instrumented; warm distributions expose aggregate costs,
including extra debug records and best-effort hint writes. The sample does not establish a universal overhead bound.

The benchmark runtime is Debian 13 with GCC 14.2.0 and Clang 19.1.7 on Linux 6.8.0-64-generic under local Docker. Exact
image identities and creation times are retained in the report. Historical investigation and Phase 1 attachments are
unchanged. Fresh-container portability and observation-probe optimizations remain outside this phase.

## Validation

The standalone `preparation_identity_test.py` and `preparation_support_test.py` suites passed on macOS with Apple Clang
17 and on Linux with GCC and Clang 19. The support suite compiles the new native digest-seed fixture with strict
warnings. It exercises missing/deleted hints and donors, malformed records, incompatible schemas, invalid keys and
digests, changed identity metadata, replaced inputs, force, eligibility refusal, failed memo/hint publication and
self-contained copied records. Its debug assertions distinguish candidate lookup from validated reuse and hashing
fallback, and ensure verbosity levels below 3 remain quiet. Copy allocation errors are not separately injected because
the JSON helper has no recoverable copy-failure return.

The identity suite confirms that cwd changes preserve effective native identity while still probing discovery and
avoiding content reads. Relative nested response files select each cwd's actual header. Existing environment, new
shadow-candidate, compiler/library replacement, force and unsupported-indirection tests retain their behavior. All 13
reporter tests passed, including retention and Markdown rendering of digest-seed decisions without altering hash totals.

The full local command is `L1_BOOTSTRAP_L0C=<existing-local-L0-stage2> make -C l1 test-all`. An explicit existing L0
bootstrap was used because this fresh worktree had no local L0 build. All 84 normal cases, environment stackability,
four examples and the Docker/Wine runner checks passed. All 46 default parent trace cases and both child fixtures also
passed, each with zero leaked object/string pointers. The intentionally slow math runtime trace is excluded by the
default sweep; its normal case passed. The full validation tier was selected because the new optional donor state adds
owned C allocations and cleanup paths.

Linux native tests use a read-only repository mount and `L1_CC=gcc` or `L1_CC=clang`. The initial Debian 12 `l1-test`
image passed GCC identity/support coverage; its Clang 14 correctly refused the existing `--no-default-config` archiver
requirement before reaching Phase 2. Supported Clang 19 identity/support coverage passed in a validation-only derivative
of the changed benchmark image, with `/usr/local` Python copied from `l1-test` and `ldconfig` run. No packages were
downloaded and the benchmark images were not modified. An initial Dockerfile placement caused Docker to inspect an
unrelated protected temporary directory; an isolated build context resolved that setup issue.

Native Windows execution was unavailable. The normal suite's Windows-environment test reports a platform skip on macOS;
it is not evidence of native Windows validation. There is no claim about Windows timing or fresh-container metadata
portability. No remote writes or publication were performed.

An independent read-only review found no demonstrated production bug or regression, but identified a test gap: changing
only the donor's reliability flag tested metadata inequality rather than the reliability requirement. The native fixture
now also rejects equal cached/current metadata with `reliable: 0`. The standalone fixture and its observation checks
passed. A temporary copy with the reliability guard removed failed at the new assertion, confirming that the regression
detects the missing check. Production sources are unchanged, so the recorded full-suite and Docker results remain
applicable; costly suites and benchmarks were not rerun for this review follow-up.

[dockerfile]: ../phase1/Dockerfile
[driver]: measure.py
[measurements]: report.json
