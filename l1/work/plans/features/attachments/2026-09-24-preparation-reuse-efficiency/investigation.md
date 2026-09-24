# L1 Preparation Latency: Docker Investigation

- Date: 2026-09-24
- Baseline: `observability-enabled-baseline-2026-09-24`
- Parent plan: [l1/work/plans/features/2026-09-24-preparation-reuse-efficiency-noref.md][plan]

## Findings

A completed native profile can be reused while establishing its validity costs seconds. In this Linux environment,
toolchain discovery and input hashing dominate expensive reuse. Metadata evidence recorded during image construction
does not fully survive into runtime; changing cwd selects different discovery and input memos; explicitly naming the
bundled system root selects source providers despite native-profile reuse. Artifact hashing and cache copying are
smaller costs. Most warm build time lies outside preparation and remains unattributed.

The primary experiment comprises 42 independently initialized container cases: six behavioral scenarios plus a nondebug
fresh/warm control, two compilers, and three repetitions. All 150 compiler invocations and 150 separate executable
output checks passed. Of these builds, 138 used `-vvv`; every one reported zero managed module compilations and zero
preparation build commands. The remaining 12 nondebug builds have no preparation observations. There were no timeouts or
OOM events. Each compiler retained one native key throughout the instrumented matrix, including cwd, cache, and provider
changes.

This report describes the Docker investigation. Earlier macOS measurements motivated it but are not pooled into these
results. All primary individual samples and parsed observations are in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/report.json][measurements]. The additional
logging control is in
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/logging-control-report.json][logging-control].

## Original Comparison and Current Measurements

Times are compiler subprocess elapsed seconds inside the container. Current values are medians with minimum-maximum
ranges across three independent cases. Counter triples mean probes / identity content reads / artifact content reads.
The original illustrative measurements are retained as historical context; they are not extra samples in the JSON.

| Case                         | Original seconds | Original counters | Current seconds (range) | Current counters |
| ---------------------------- | ---------------- | ----------------- | ----------------------- | ---------------- |
| Clang, fresh first           | 3.41             | 46 / 183 / 47     | 3.434 (3.222-3.709)     | 46 / 172 / 47    |
| Clang, same-container second | 0.54             | 2 / 0 / 0         | 0.682 (0.605-0.820)     | 2 / 0 / 0        |
| GCC, memos removed first     | 1.80             | 43 / 164 / 47     | 1.455 (1.447-1.676)     | 43 / 164 / 47    |
| GCC, subsequent second       | 0.58             | 1 / 0 / 0         | 0.607 (0.523-0.720)     | 1 / 0 / 0        |

The fresh Clang identity-read count is 172 rather than the original 183 because eleven small native toolchain files
still have usable metadata in the baked input memo. Removing all memos yields exactly 183 identity reads for Clang.
Fresh GCC similarly reads 158 identities, compared with 164 after removing memos. A discovery miss does not necessarily
force rehashing every input if individual digest evidence remains valid.

This reproduces the mechanism and approximate latency pattern, not a bit-identical historical benchmark. The exact
historical image content digest and complete historical argv were not supplied. Differences in payload, filesystem,
toolchain, flags, or capture behavior cannot be retroactively controlled. Current image content digests, compiler argv,
cwd, relevant environment, and runtime provenance are preserved in the attached JSON, subject only to the sanitization
described below.

## Environment and Prepared Support

The observability-enabled L1 Stage 1 baseline was bootstrapped with L0 from the same checked-out source baseline. L0 and
L1 image provenance labels were checked against that source before measurement. Source identifiers are represented here
by the descriptive baseline label; the retained local source records were not modified.

| Component          | Measured environment                                                                                      |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| Architecture       | x86-64 Linux (`amd64`)                                                                                    |
| C compilers        | GCC 14.2.0, Debian package `14.2.0-19`; Clang 19.1.7, Debian package `3+b1`                               |
| Container runtime  | Docker 29.7.2 through Colima on a macOS host; overlayfs storage                                           |
| Docker VM          | Ubuntu 24.04.2 LTS, kernel `6.8.0-64-generic`, four CPUs and 8,325,083,136 bytes reported memory          |
| Image construction | Python 3.14 bookworm builder with the L0 bootstrap; Debian stable slim runtime                            |
| Runtime payload    | Installed L1 executable, shared sources, public headers, bundled interfaces, and prepared native profiles |
| Cache template     | `/opt/dea/l1/cache-template`, 14,472 KiB across nine profiles                                             |

The separately named local base image is `dea-preparation-investigation-head`; the measured derived image is
`dea-preparation-investigation-clang`. Their immutable image content digests and configuration are in `report.json`
under `provenance.images`. These names identify local artifacts, not published images. Floating package and base-image
names alone are insufficient to reconstruct the exact historical payload.

The base image retained eight GCC profiles: `-O0`, each of no tracing / ARC / memory / both, each with default line
directives or `--no-line-directives`. A derived image added the matching Clang `-O0` profile with default line
directives and no tracing. Preparation/build logs were captured separately from consumer measurements. No support was
prepared to repair a measured consumer failure.

Every case used these restrictions:

- One CPU quota, 256 MiB memory, and an equal 256 MiB memory-swap limit.
- 64 PIDs, non-root UID/GID `65534:65534`, all capabilities dropped, and `no-new-privileges`.
- Read-only root filesystem and no network.
- A 64 MiB executable `/work` tmpfs with mode `1777`; `HOME=/work`, `TMPDIR=/work`, initial cwd `/work`.
- Read-only absolute input mount `/input` and a separate writable results mount `/results`.

The fixture was the bundled [l1/examples/hello.l1][hello], copied to `/input/hello.l1`. Every consumer used absolute
source/project paths, `--c-options=-O0`, default line directives, and `--no-auto-prepare`. L1 directly received the
chosen `--c-compiler gcc` or `--c-compiler clang`, with no routing layer substituting a compiler. No trace flags were
used for measured consumers.

## Matrix and Isolation

All cases ran sequentially. Each compiler/scenario/repetition started a fresh container and isolated writable cache. The
wrapper initially copied the image's `v1` template to `/work/dea-l1-cache/v1` when no explicit cache environment was set
and that destination was absent. This wrapper setup is inside the first compiler subprocess measurement.

| Scenario (`report.json` name)           | Sequence inside one container                                                                                                                            |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fresh (`fresh`)                         | Invoke twice through the wrapper using the prepared cache.                                                                                               |
| Changed cwd (`cwd`)                     | Establish baseline first/second; change only cwd to `/work/alternate`; invoke twice; return to `/work` and invoke once.                                  |
| Copied cache (`copy`)                   | Establish baseline first/second; separately time `cp -a` to `/work/copied-cache`; invoke twice with that explicit cache root.                            |
| Same-path replacement (`same-path`)     | Establish baseline first/second; move the disposable cache aside and separately time a metadata-preserving copy back to its original path; invoke twice. |
| Memos removed (`no-memos`)              | Establish baseline first/second; remove only `v1/memo` in that container's cache; invoke twice with completed profiles retained.                         |
| Explicit bundled root (`explicit-root`) | Establish baseline first/second; append `--sys-root /opt/dea/l1/compiler/shared/l1/stdlib`; invoke twice, still using `--no-auto-prepare`.               |
| Nondebug control (`nondebug`)           | Fresh first/second pair with the same options and fixture but without `-vvv`.                                                                            |

The 150 builds comprise 84 first/second scenario builds, 60 baseline builds, and six return-to-original-cwd builds. Each
had its own successful output check. There were also 24 separately timed copy operations: six relocated copies, six
same-path copies, and twelve image-template copy controls after the fresh/nondebug pairs. Baseline builds remain in
`cases[].commands`; the main `aggregates` summarize the scenario pairs and cwd return controls.

The additional logging control used two further containers, one per compiler, each with two warmup builds/output checks
and twelve alternating warm measurements. Its 24 measured builds, four warmup builds, and four output checks are
separate from the primary totals above; it did not add an executable check after each of its 24 warm measurements.

## Measurement Boundaries

The container helper used `CLOCK_MONOTONIC` around fork/exec/wait and recorded elapsed milliseconds, child user/system
CPU time, maximum RSS, exit status, and timeout evidence. Output files were opened before the timer started; command
execution and writes to those files were timed. Completion detection polled at 1 ms intervals, so scheduling and polling
overhead are included. A 120-second per-command timeout killed the child process group; the host runner separately
bounded the Docker invocation at 700 seconds. Neither limit was reached.

Each compiler command's stdout/stderr went to `/work/capture` on tmpfs in the accepted matrix. Logs and timer metadata
were copied to the host results mount after that timer stopped. Each executable was run and timed separately, checking
all 25 expected greeting lines without imposing order. Output verification is not part of compiler elapsed time. The
host runner used a separate monotonic timer for the whole Docker subprocess, including startup, setup, compiler
invocations, executable checks, copying, log export, and teardown. Host duration is not a compiler timing.

The observation parser from [l1/scripts/check_preparation_reuse.py][reporter] retained partial records on failure. The
primary report has no failed or unavailable commands. Ordinary diagnostic records, raw observations, memo decisions,
metadata differences, keys, provider selections, counters, and timings are retained. Probe records use `status` and
`timed_out`; a missing field is not an inferred timeout. All observed discovery probes completed successfully.

Preparation `span` records are inclusive. For these reuse consumers, Dea identity resolution, native identity
resolution, and profile validation are separate spans, so the report can total them. There are no native-publication or
lock-wait spans in this matrix. Probe and hash timings are nested within preparation spans and must not be added again.
Any future publication/locking or frontend spans require their nesting to be checked before summing. Medians of
components need not sum to the median total or median residual.

Hash byte counts are actual bytes read for SHA-256 input, including failed attempts if present, not total filesystem
I/O, stat activity, probe I/O, or physical storage traffic. There were no failed hash attempts in this matrix. Hash
times include file access and digest work; probe times include subprocess startup and probe work. This investigation
does not separate those components. Existing preparation counters exclude ordinary application and imported-source
compilation.

## Why Validation Repeats

### Image-Baked Evidence Fails Runtime Metadata Checks

Both compilers find their observation selection key but reject the observation memo with `metadata-changed`. The first
toolchain discovery mismatch is `/bin`, category `directory`, field `inode`: the first repetition records previous
`2506904` versus current `2516112`. Comparison reports the first differing field in a fixed order, not proof that every
later metadata field is equal.

Per-file evidence also differs: each first fresh build rehashes 61 Dea inputs; GCC rehashes 97 native toolchain inputs
and Clang 111. Those individual fallback records report inode changes. Six GCC and eleven Clang native input digests
remain reusable. Thus the input memo itself can be a `hit / validated-memo` while some entries still require hashing.

The completed native profile remains `hit / validated-profile` and its native key stays unchanged after revalidation.
These observations establish a build/runtime filesystem metadata difference in this overlayfs setup. They do not
establish that all Docker runtimes behave the same way or that evidence validated in one runtime container will match
another. Cross-container runtime evidence distribution remains an untested remediation.

### Changed Cwd Selects Different Discovery and Input Memos

Moving from `/work` to `/work/alternate` with absolute inputs changes the observation selection key while preserving the
native key and managed providers. The records say `miss / no-matching-memo` for both toolchain observation and input
memos, with no metadata-difference event. The compiler alone does not infer a cwd change from absence; the controlled
experiment and comparison of selection keys provide that evidence.

The first changed-cwd invocation performs 43 probes and 103 native input reads for GCC, totaling 46,112,953 hash bytes.
Clang performs 46 probes and 122 native input reads, totaling 240,347,792 bytes. The input memo shares the cwd-sensitive
selection, so unchanged digest evidence from the original cwd is unavailable to this lookup.

Median changed-cwd first/second times are 1.322/0.572 seconds for GCC and 3.454/0.665 seconds for Clang. The second
build uses the new memo, and returning to `/work` immediately reuses the original memo (0.523 seconds GCC, 0.637 seconds
Clang). This supports separating digest reuse from discovery selection. It does not establish that cwd is irrelevant to
relative options, response files, environment search paths, or implicit compiler configuration.

### Cache Location and Per-File Artifact Evidence Are Different Causes

A warm cache copied to a different path preserves Dea/toolchain input and observation memo reuse. Artifact validation
instead reports `miss / no-matching-memo`: its memo selection includes the canonical profile entry path and manifest
digest. The first invocation reads 47 artifacts, then the identical second invocation reads none.

A metadata-preserving copy replacing a cache at the same path finds the artifact memo (`hit / validated-memo`) but
rejects individual artifact inode evidence. It also hashes 47 artifacts once, followed by no artifact reads. Finding a
memo is distinct from validating every entry without reading contents. Neither copy case changes the native content
identity or requires preparation compilation.

The 47 artifact hashes cover 482,858 bytes for GCC or 521,434 bytes for Clang, roughly 5-7 ms in these copy cases.
Separate image-template copies take roughly 67-73 ms, and warm tmpfs-to-tmpfs copies roughly 35-46 ms. The
image-template copy is measured after each fresh/nondebug pair; it is a control for the copying mechanism, not an exact
isolated measurement of the wrapper copy embedded in the first build. Successful copying here is an experimental
observation, not portability support or permission to ignore changed inode/ctime evidence.

### Removing Memos Exposes Full Validation Cost

Deleting only the disposable cache's memo subtree retains completed profiles but requires new Dea and toolchain input
evidence, discovery, and artifact validation. GCC reads 164 identities and Clang 183, plus 47 artifacts each. Median
first/second durations are 1.455/0.607 seconds for GCC and 3.246/0.723 seconds for Clang. All builds retain
native-profile reuse and zero preparation build commands. Restored warm reuse confirms that the removed evidence, rather
than missing native products, caused the extra work.

### Explicit Bundled Root Selects Source Providers

With the same bundled directory passed explicitly through `--sys-root`, all eleven selected `std.*`/`sys.*` providers
switch from managed interfaces to ordinary sources. The native profile and validation memos remain hits; identity and
artifact content reads remain zero. Every invocation analyzes those eleven source modules again.

Median first/second times become 3.890/3.667 seconds for GCC and 3.487/3.726 seconds for Clang. `--no-auto-prepare` does
not prohibit ordinary source compilation. Native-profile hits and preparation counters therefore cannot establish that
imported stdlib source compilation was avoided. Leaving the bundled root implicit avoids this current behavior; changing
explicit-root semantics is a compatibility decision covered by the parent plan.

### Key and Provider Comparisons

The comparison fields in the JSON are equality results, not success/failure classifications: `true` means values match,
`false` means they differ, and `null` means evidence was unavailable. `selection_keys` refers to discovery selection,
not the separate artifact-validation memo key. The following compares each changed state's first invocation with its
warm baseline; fresh rows compare first with second.

| Change                | Native key equal | Discovery selection equal | Providers equal | Evidence that changed                                                 |
| --------------------- | ---------------- | ------------------------- | --------------- | --------------------------------------------------------------------- |
| Fresh first to second | Yes              | Yes                       | Yes             | Runtime metadata is revalidated and recorded on first use.            |
| Cwd                   | Yes              | No                        | Yes             | New discovery/input memo selection; no metadata mismatch is reported. |
| Copied cache          | Yes              | Yes                       | Yes             | Artifact memo selection changes with the canonical cache entry path.  |
| Same-path copy        | Yes              | Yes                       | Yes             | Artifact memo exists; individual artifact inodes differ.              |
| Memos removed         | Yes              | Yes                       | Yes             | Memo files are absent; completed profiles remain.                     |
| Explicit bundled root | Yes              | Yes                       | No              | Eleven providers change from managed interfaces to sources.           |

## Attributed Costs and Rankings

Fresh-container values below are medians. The byte counts are exact for every sample in the corresponding group.

| Measurement                       | GCC                        | Clang                       |
| --------------------------------- | -------------------------- | --------------------------- |
| Compiler elapsed                  | 1.370 s                    | 3.434 s                     |
| Preparation total                 | 0.891 s                    | 2.752 s                     |
| Dea identity span                 | 0.037 s                    | 0.042 s                     |
| Native identity/observation span  | 0.844 s                    | 2.703 s                     |
| Profile validation span           | 0.008 s                    | 0.009 s                     |
| Dea input hashing (nested)        | 0.033 s / 5,071,548 bytes  | 0.037 s / 5,071,548 bytes   |
| Native toolchain hashing (nested) | 0.278 s / 41,398,161 bytes | 1.596 s / 232,954,784 bytes |
| Artifact hashing (nested)         | 0.005 s / 482,858 bytes    | 0.005 s / 521,434 bytes     |
| All discovery probes (nested)     | 0.483 s / 43 probes        | 1.046 s / 46 probes         |

Clang's LLVM, Clang C++ implementation, and Z3 libraries account for almost all its native hash time. GCC's largest
input is `cc1`. These inputs remain required identity evidence under current policy; their size alone does not justify
excluding them. The rankings below use the median fresh-first per-path or per-purpose total across three cases, ordered
by that median. Probe purposes can repeat within an invocation; counts and totals are grouped accordingly.

| Compiler | Largest native hash inputs                    | Bytes       | Seconds (range)     |
| -------- | --------------------------------------------- | ----------- | ------------------- |
| gcc      | `/usr/libexec/gcc/x86_64-linux-gnu/14/cc1`    | 34,148,896  | 0.231 (0.191-0.233) |
| gcc      | `/lib/x86_64-linux-gnu/libisl.so.23`          | 2,086,872   | 0.011 (0.011-0.013) |
| gcc      | `/usr/bin/gcc`                                | 1,162,264   | 0.008 (0.007-0.010) |
| gcc      | `/lib/x86_64-linux-gnu/libbfd-2.44-system.so` | 1,463,360   | 0.007 (0.007-0.009) |
| gcc      | `/usr/bin/as`                                 | 795,184     | 0.004 (0.004-0.005) |
| clang    | `/lib/x86_64-linux-gnu/libLLVM.so.19.1`       | 129,673,080 | 0.901 (0.842-0.940) |
| clang    | `/lib/x86_64-linux-gnu/libclang-cpp.so.19.1`  | 71,043,800  | 0.484 (0.477-0.586) |
| clang    | `/lib/x86_64-linux-gnu/libz3.so.4`            | 27,751,664  | 0.187 (0.184-0.247) |
| clang    | `/lib/x86_64-linux-gnu/libxml2.so.2`          | 1,799,256   | 0.012 (0.010-0.015) |
| clang    | `/lib/x86_64-linux-gnu/libbfd-2.44-system.so` | 1,463,360   | 0.009 (0.008-0.011) |

| Compiler | Most expensive probe purposes            | Count per build | Seconds (range)     |
| -------- | ---------------------------------------- | --------------- | ------------------- |
| gcc      | compiler implementation libraries        | 4               | 0.045 (0.039-0.046) |
| gcc      | ELF dynamic entries                      | 15              | 0.041 (0.035-0.048) |
| gcc      | runtime dependencies: dea_rt_io          | 1               | 0.027 (0.020-0.029) |
| gcc      | generated-C dependencies: real=0,float=1 | 1               | 0.024 (0.022-0.032) |
| gcc      | generated-C dependencies: real=1,float=1 | 1               | 0.024 (0.024-0.031) |
| gcc      | generated-C dependencies: real=1,float=0 | 1               | 0.024 (0.022-0.030) |
| gcc      | runtime dependencies: dea_rt_time        | 1               | 0.023 (0.020-0.029) |
| gcc      | runtime dependencies: dea_rt_string      | 1               | 0.023 (0.022-0.026) |
| clang    | ELF dynamic entries                      | 21              | 0.067 (0.064-0.068) |
| clang    | generated-C dependencies: real=0,float=1 | 1               | 0.052 (0.047-0.052) |
| clang    | generated-C dependencies: real=0,float=0 | 1               | 0.048 (0.042-0.052) |
| clang    | runtime dependencies: dea_rt_panic       | 1               | 0.047 (0.038-0.049) |
| clang    | runtime dependencies: dea_rt_rand        | 1               | 0.047 (0.040-0.048) |
| clang    | runtime dependencies: dea_rt_trace       | 1               | 0.047 (0.037-0.048) |
| clang    | generated-C dependencies: real=1,float=0 | 1               | 0.046 (0.045-0.056) |
| clang    | generated-C dependencies: real=1,float=1 | 1               | 0.046 (0.044-0.054) |

Ten runtime-source dependency probes total about 0.224 seconds for GCC and 0.447 seconds for Clang. Four generated-C
dependency configurations add about 0.099 and 0.194 seconds, respectively. The full JSON retains every individual probe
purpose, timing, exit status, and timeout indicator. Discovery is distributed across work items rather than dominated by
one failed or pathological process. Pure SHA computation versus access cost and process startup versus probe work remain
separate questions for implementation-time controls.

### Warm Time Outside Preparation

Fresh-container second builds total about 17 ms in preparation for GCC and 78 ms for Clang, with no identity or artifact
content reads. GCC still probes compiler family/version; Clang also probes effective-configuration target options.
Approximately 0.494 seconds for GCC and 0.604 seconds for Clang remain outside preparation spans. This broad residual
includes wrapper overhead and ordinary compilation; it is not a measurement of frontend analysis, C generation, C
compilation, or linking individually.

## All Scenario Distributions

Seconds are median (minimum-maximum), with three independent cases per row. Nested probe/hash columns are explanatory
components, not additions to preparation. Nondebug observations are unavailable, not zero. Raw per-invocation timings,
including every baseline, remain in the JSON.

| Compiler / scenario / invocation | Compiler            | Preparation spans   | Probes (nested)     | Hashing (nested)    | Outside spans       |
| -------------------------------- | ------------------- | ------------------- | ------------------- | ------------------- | ------------------- |
| clang/copy/first                 | 0.780 (0.680-0.818) | 0.080 (0.080-0.102) | 0.056 (0.054-0.075) | 0.007 (0.006-0.007) | 0.700 (0.600-0.716) |
| clang/copy/second                | 0.706 (0.644-0.758) | 0.075 (0.071-0.084) | 0.058 (0.055-0.066) | 0.000 (0.000-0.000) | 0.622 (0.573-0.683) |
| clang/cwd/first                  | 3.454 (2.834-3.695) | 2.965 (2.396-3.056) | 1.080 (0.964-1.208) | 1.700 (1.386-1.918) | 0.490 (0.438-0.639) |
| clang/cwd/return                 | 0.637 (0.633-0.748) | 0.078 (0.070-0.091) | 0.055 (0.054-0.067) | 0.000 (0.000-0.000) | 0.563 (0.560-0.657) |
| clang/cwd/second                 | 0.665 (0.640-0.693) | 0.077 (0.075-0.081) | 0.061 (0.058-0.062) | 0.000 (0.000-0.000) | 0.590 (0.563-0.612) |
| clang/explicit-root/first        | 3.487 (2.954-4.142) | 0.079 (0.067-0.079) | 0.059 (0.050-0.063) | 0.000 (0.000-0.000) | 3.408 (2.887-4.063) |
| clang/explicit-root/second       | 3.726 (2.622-4.020) | 0.070 (0.059-0.079) | 0.054 (0.045-0.063) | 0.000 (0.000-0.000) | 3.656 (2.563-3.941) |
| clang/fresh/first                | 3.434 (3.222-3.709) | 2.752 (2.723-3.061) | 1.046 (1.019-1.092) | 1.635 (1.587-1.861) | 0.648 (0.470-0.711) |
| clang/fresh/second               | 0.682 (0.605-0.820) | 0.078 (0.068-0.102) | 0.060 (0.052-0.070) | 0.000 (0.000-0.000) | 0.604 (0.537-0.718) |
| clang/no-memos/first             | 3.246 (3.246-3.733) | 2.729 (2.636-3.087) | 1.045 (0.994-1.119) | 1.649 (1.496-1.878) | 0.610 (0.517-0.647) |
| clang/no-memos/second            | 0.723 (0.701-0.960) | 0.084 (0.072-0.096) | 0.066 (0.053-0.077) | 0.000 (0.000-0.000) | 0.652 (0.617-0.864) |
| clang/nondebug/first             | 3.633 (3.331-3.960) | unavailable         | unavailable         | unavailable         | unavailable         |
| clang/nondebug/second            | 0.682 (0.658-0.687) | unavailable         | unavailable         | unavailable         | unavailable         |
| clang/same-path/first            | 0.685 (0.672-0.878) | 0.092 (0.088-0.114) | 0.067 (0.054-0.084) | 0.006 (0.006-0.007) | 0.593 (0.584-0.764) |
| clang/same-path/second           | 0.643 (0.631-0.797) | 0.069 (0.069-0.120) | 0.053 (0.053-0.094) | 0.000 (0.000-0.000) | 0.574 (0.562-0.677) |
| gcc/copy/first                   | 0.543 (0.465-0.553) | 0.023 (0.023-0.025) | 0.002 (0.002-0.003) | 0.006 (0.006-0.006) | 0.519 (0.442-0.528) |
| gcc/copy/second                  | 0.501 (0.400-0.521) | 0.017 (0.013-0.018) | 0.002 (0.002-0.003) | 0.000 (0.000-0.000) | 0.484 (0.387-0.503) |
| gcc/cwd/first                    | 1.322 (1.234-1.416) | 0.804 (0.779-0.913) | 0.501 (0.455-0.590) | 0.289 (0.270-0.295) | 0.503 (0.430-0.544) |
| gcc/cwd/return                   | 0.523 (0.488-0.616) | 0.018 (0.014-0.022) | 0.002 (0.002-0.004) | 0.000 (0.000-0.000) | 0.506 (0.474-0.594) |
| gcc/cwd/second                   | 0.572 (0.494-0.582) | 0.019 (0.015-0.021) | 0.002 (0.002-0.003) | 0.000 (0.000-0.000) | 0.551 (0.479-0.563) |
| gcc/explicit-root/first          | 3.890 (3.290-4.017) | 0.020 (0.019-0.028) | 0.003 (0.003-0.007) | 0.000 (0.000-0.000) | 3.870 (3.271-3.988) |
| gcc/explicit-root/second         | 3.667 (2.649-3.944) | 0.018 (0.018-0.021) | 0.003 (0.003-0.004) | 0.000 (0.000-0.000) | 3.646 (2.632-3.926) |
| gcc/fresh/first                  | 1.370 (1.309-1.411) | 0.891 (0.802-0.925) | 0.483 (0.463-0.529) | 0.317 (0.268-0.321) | 0.507 (0.445-0.520) |
| gcc/fresh/second                 | 0.512 (0.494-0.518) | 0.017 (0.016-0.018) | 0.002 (0.002-0.002) | 0.000 (0.000-0.000) | 0.494 (0.478-0.501) |
| gcc/no-memos/first               | 1.455 (1.447-1.676) | 0.983 (0.959-1.054) | 0.538 (0.514-0.587) | 0.367 (0.360-0.375) | 0.496 (0.464-0.622) |
| gcc/no-memos/second              | 0.607 (0.523-0.720) | 0.020 (0.017-0.024) | 0.003 (0.002-0.004) | 0.000 (0.000-0.000) | 0.588 (0.507-0.696) |
| gcc/nondebug/first               | 1.527 (1.428-1.584) | unavailable         | unavailable         | unavailable         | unavailable         |
| gcc/nondebug/second              | 0.511 (0.500-1.435) | unavailable         | unavailable         | unavailable         | unavailable         |
| gcc/same-path/first              | 0.591 (0.533-0.635) | 0.030 (0.023-0.031) | 0.002 (0.002-0.003) | 0.005 (0.005-0.007) | 0.560 (0.510-0.605) |
| gcc/same-path/second             | 0.594 (0.540-0.638) | 0.021 (0.019-0.023) | 0.003 (0.002-0.003) | 0.000 (0.000-0.000) | 0.574 (0.519-0.615) |

## Copy and Host Container Durations

Copy times and host-observed Docker subprocess times are separate from compiler timing. Container duration covers the
whole case, so cases with more builds cannot be compared as single-build latency. A missing copy value means the case
had no copy control.

| Compiler / scenario   | Copy seconds (range) | Container seconds (range) |
| --------------------- | -------------------- | ------------------------- |
| clang / copy          | 0.038 (0.035-0.047)  | 6.308 (5.875-6.673)       |
| clang / cwd           | unavailable          | 8.970 (8.582-10.625)      |
| clang / explicit-root | unavailable          | 12.231 (9.722-13.819)     |
| clang / fresh         | 0.071 (0.066-0.093)  | 4.867 (4.378-5.006)       |
| clang / no-memos      | unavailable          | 8.638 (8.364-9.293)       |
| clang / nondebug      | 0.073 (0.072-0.075)  | 4.884 (4.573-5.290)       |
| clang / same-path     | 0.046 (0.035-0.046)  | 6.300 (5.672-6.660)       |
| gcc / copy            | 0.035 (0.026-0.035)  | 3.676 (3.175-3.736)       |
| gcc / cwd             | unavailable          | 4.890 (4.668-5.511)       |
| gcc / explicit-root   | unavailable          | 10.411 (8.618-10.875)     |
| gcc / fresh           | 0.067 (0.064-0.069)  | 2.384 (2.306-2.645)       |
| gcc / no-memos        | unavailable          | 4.857 (4.636-5.359)       |
| gcc / nondebug        | 0.067 (0.066-0.111)  | 2.687 (2.507-3.659)       |
| gcc / same-path       | 0.039 (0.034-0.052)  | 3.953 (3.939-4.063)       |

## Verbosity and Capture-Location Controls

The preliminary pilot captured compiler stderr directly to a host bind mount. It was stopped after identifying
substantial logging overhead. Its retained local `pilot-host-logs/` files, including an incomplete case, are excluded
from the primary report and are not counted as accepted failures or samples. The accepted matrix captures locally in
tmpfs and exports logs after each timed command.

The additional control alternates debug/quiet and tmpfs/host capture in the same warm container, with three cycles and
three samples per combination. The first/third cycle orders debug-tmpfs, debug-host, quiet-tmpfs, quiet-host; the second
reverses that order. These samples share a warm container per compiler, so they are not three independent container
repetitions. All debug control measurements retain zero identity/artifact reads and zero preparation compilation.

| Compiler | Quiet to tmpfs      | Debug to tmpfs      | Quiet to host       | Debug to host       |
| -------- | ------------------- | ------------------- | ------------------- | ------------------- |
| gcc      | 0.396 (0.390-0.396) | 0.396 (0.393-0.463) | 0.418 (0.401-0.505) | 0.642 (0.623-0.718) |
| clang    | 0.722 (0.720-0.823) | 0.700 (0.678-0.774) | 0.752 (0.697-0.861) | 1.028 (0.929-1.127) |

Host-mounted debug logging adds about 0.25-0.33 seconds relative to debug output to tmpfs in this control. Tmpfs debug
versus quiet differences show no consistent penalty in this small sample; this does not prove zero instrumentation
overhead. Capture location therefore needs to remain controlled in future comparisons.

The main nondebug fresh/warm pairs broadly agree with the debug matrix. One GCC quiet warm sample took 1.435 seconds,
versus about 0.50 seconds in its other two repetitions. It remains in the report and range. The paired logging control
did not reproduce a persistent quiet slowdown; no causal explanation for that outlier is established.

## Reproducible Command Descriptions

### Construct the Baseline Payload

Use the public compiler tree for the selected observability-enabled source baseline. In a Linux builder with Python,
build tools, Clang, and the repository dependency environment, the bootstrap entry points are:

```sh
uv sync --frozen --all-groups
make -C l0 PREFIX=/opt/dea install
make -C l1 L1_BOOTSTRAP_L0C=/opt/dea/bin/l0c-stage2 \
  L1_BUILD_DIR=build/preparation-study build-stage1
```

For a neutral reconstruction, copy `l1/compiler/shared` to `/opt/dea/l1/compiler/shared`, the generated `interfaces` and
`include` directories into `/opt/dea/l1/compiler`, the full generated build tree to
`/opt/dea/l1/build/preparation-study`, and its `bin/l1c-stage1.native` to `/opt/dea/bin/l1c-stage1.native`. Use a
wrapper at `/opt/dea/bin/l1c-stage1` that defaults `L1_HOME` to `/opt/dea/l1/compiler` and `L1_BUILD_DIR` to that
installed build tree. If `L1_STDLIB_CACHE` is unset/empty, it creates `${TMPDIR:-${HOME:-/tmp}}/dea-l1-cache` and copies
`/opt/dea/l1/cache-template/v1` there only when the destination `v1` is absent, then exports that cache root and
executes the native compiler with unchanged arguments. These neutral build-tree names describe reconstruction, not an
additional replacement of recorded container paths or a claim of byte-identical compiler output.

The runtime image needs GCC, Clang, libc development headers, and coreutils. Preserve `/opt/dea/bin` at the front of
PATH. Create `/work` with mode `1777`. With `HOME=/work`, `TMPDIR=/work`, cwd `/work`, and
`L1_STDLIB_CACHE=/opt/dea/l1/cache-template`, prepare the GCC profile using:

```sh
/opt/dea/bin/l1c-stage1 --prepare-stdlib \
  --stdlib-cache /opt/dea/l1/cache-template --c-compiler gcc --c-options=-O0
```

Repeat for all eight combinations of trace flags and line-directive settings listed above. Make the template readable by
the non-root runtime user. In a derived image, add Clang support in the same cwd and environment, with preparation
stdout/stderr captured outside any measured consumer interval:

```sh
/opt/dea/bin/l1c-stage1 --prepare-stdlib \
  --stdlib-cache /opt/dea/l1/cache-template --c-compiler clang --c-options=-O0 -vvv
```

Build/provenance checks, compiler versions, image content identity, and package versions must be recorded before the
consumer matrix. A rebuild using newer source or packages is a new baseline, even if the scenarios are identical. The
image labels containing source revision fields in the attachments are sanitized provenance, not retrievable source
references; image content digests remain exact. This is a reproducible experimental procedure, not an archived complete
image build context or a promise of obtaining the same native keys from a rebuild.

### Launch an Isolated Case

Copy the bundled fixture into a new absolute host input directory and create a writable case directory. A case script
constructed from the sequences below belongs in that case directory. With those absolute directories assigned to
`TASK_INPUT` and `TASK_RESULTS`, and a locally built image assigned to `TASK_IMAGE`, launch:

```sh
docker run --rm --network none --read-only \
  --memory 256m --memory-swap 256m --pids-limit 64 --cpus 1 \
  --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /work:rw,size=64m,exec,mode=1777 \
  -e TMPDIR=/work -e HOME=/work -w /work \
  -v "$TASK_INPUT:/input:ro" -v "$TASK_RESULTS:/results:rw" \
  "$TASK_IMAGE" sh /results/case.sh
```

Inside each case, create `/work/alternate` and `/work/capture` before baseline measurement. Snapshot cgroup `cpu.stat`
before and after and retain `memory.events`. Use the container monotonic helper described above around each command. The
historical helper entry point was `/opt/dea/bin/investigation-timer`, with arguments: timing JSON path, stdout path,
stderr path, timeout seconds, then the complete command argv. Its source/binary and case scripts are original local
provenance, not attached dependencies; an equivalent helper must preserve the measurement boundaries above.

### Consumer and State Changes

The literal measured consumer argv, here shown for GCC, was:

```sh
/opt/dea/bin/l1c-stage1 --build --c-compiler gcc --c-options=-O0 \
  --no-auto-prepare --project-root /input -o /work/hello.out -vvv /input/hello.l1
```

Use `clang` for the other compiler, remove only `-vvv` for the nondebug pair, and invoke from `/work/alternate` for the
cwd pair without changing source/project arguments. For the explicit-root pair append
`--sys-root /opt/dea/l1/compiler/shared/l1/stdlib` before the input. Check `/work/hello.out` separately after every
primary build, comparing its 25 output lines with the fixture's greeting list.

After warming the cache twice, apply exactly one changed-state operation in each disposable case:

```sh
# Relocated cache: time this copy separately; then add --stdlib-cache /work/copied-cache.
cp -a /work/dea-l1-cache /work/copied-cache

# Same-path replacement: time cp separately; retain the original cache selection.
mv /work/dea-l1-cache /work/original-cache
cp -a /work/original-cache /work/dea-l1-cache
rm -rf /work/original-cache

# Memos removed: only in this case's disposable cache, with completed profiles retained.
rm -rf /work/dea-l1-cache/v1/memo
```

Run the identical changed-state command twice. For cwd, add one final invocation from `/work`. Only after a fresh or
nondebug pair, separately time `cp -a /opt/dea/l1/cache-template/v1 /work/copy-measurement`. Export each command's tmpfs
logs and timer JSON after timing, preserve unsuccessful/timeout records, and do not automatically prepare to repair
failures. Use three independent repetitions per compiler, sequentially, without reusing completed case directories.

Parse stderr with the existing reporter's observation parser, retaining partial records, and compute comparisons and
median/min/max distributions. Repeat the separate logging control with the same warm command and the cycle order
described above. Every historical Docker argv, compiler argv, cwd, and relevant environment is retained in the JSON; the
host-path aliases require substitution with actual fixture/results directories before replay.

## Limitations and Follow-Up Priorities

- A fresh container is not a cold host or VM filesystem cache. The cases ran sequentially without dropping shared
  caches. Three independent primary cases give descriptive ranges, not statistical confidence bounds.
- CPU quota throttling occurred and is recorded in per-case `cpu_delta`. These counters include the whole case, not only
  compilation, so they cannot assign a delay to a particular probe/hash. No OOM events occurred.
- Full image and exact original historical argv are unavailable for the earlier comparison. This campaign establishes
  current mechanisms and measurements, not a controlled causal explanation of every historical numerical difference.
- Existing observations establish how much validation occurred and its elapsed cost. They do not separate pure digest
  computation from file access, or process startup from probe computation. Warm frontend/backend phases remain
  uninstrumented. No real wall-time pass/fail thresholds were used.
- Raw logs and build/harness sources remain local provenance, not attached files. The report preserves parsed evidence,
  command metadata, failure fields, and all individual timing samples. Original local files have not been changed.

The evidence ranks explicit-root source compilation, repeated native input hashing (especially Clang's roughly
1.6-second fresh hash cost), and dependency discovery above artifact hashing/copying for this workload. First settle
provider semantics, then separate reusable digest evidence from discovery selection. Experiment with runtime-validated
evidence distribution without granting copied memos new authority. Independently benchmark discovery and SHA-256
improvements, then attribute the substantial warm residual. The parent plan records alternatives and correctness gates;
none of these optimizations was implemented by this investigation.

## Attachment Provenance and Sanitization

The two JSON files are complete structural copies of the retained local reports. No case, observation, comparison,
aggregate, failure field, or outlier was removed. The transformation operates only on string values:

1. Replace the original absolute host checkout prefix consistently with `/HOST/DEA`, preserving every suffix. This
   changes 84 occurrences in `report.json` and four in `logging-control-report.json`, all in Docker bind-mount argv.
2. Replace the single source revision identifier with `observability-enabled-baseline-2026-09-24` wherever it occurs:
   nine occurrences in `report.json` (the source `head`, image labels, and image environment); none in the control file.

Object key names/order, list ordering, numerical values and types, booleans, nulls, equality relationships, native and
selection keys, file digests, and image content digests remain unchanged. Keys were not recomputed from aliased paths.
Fields still named `head` or ending in `sha` now carry the baseline label when they identify source revisions; they must
not be interpreted as literal source identifiers. `HEAD` reference names in recorded configuration remain intact.
Whitespace formatting of JSON is not measurement evidence.

`stdout_log` and `stderr_log` values, such as `runs/clang-fresh-1/first.stderr.log`, refer to the original ignored local
investigation directory. The control file's log references are relative to its original logging-control root. These are
provenance strings, not attachment-relative files or links. Source scripts, raw logs, image build/preparation logs,
version text, and the excluded pilot are not attached; this Markdown deliberately links only available repository files.
Recursive comparison against the documented string transformation verifies measurement preservation, and the
tables/counts are reconciled with the JSON rather than copied from unavailable log links.

[hello]: ../../../../../examples/hello.l1
[logging-control]: logging-control-report.json
[measurements]: report.json
[plan]: ../../2026-09-24-preparation-reuse-efficiency-noref.md
[reporter]: ../../../../../scripts/check_preparation_reuse.py
