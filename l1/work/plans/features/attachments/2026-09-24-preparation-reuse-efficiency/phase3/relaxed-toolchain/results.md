# Phase 3: Relaxed toolchain-file digest reuse experiment

- Date: 2026-09-25
- Scope: Isolated candidate policy; production compiler sources retain strict metadata matching.
- Status: Completed isolated experiment; the broader Phase 3 architecture and ADR decision remain pending.

## Policy and isolation

The baseline uses the current full-metadata digest predicate. The candidate ignores only `device`, `inode`, `ctime` and
`ctime_ns` for previously established digests of freshly selected regular `toolchain-input` files. It still compares
size, mode, full modification time, reliability and any other represented fields. Missing and explicit-null values
remain distinct. Malformed records or digests, and malformed numeric identity/change stamps, do not obtain relaxed hits.

The candidate changes both current-record and existing donor-record comparisons without changing donor selection. It
saves current complete metadata after reuse. Diagnostic `digest-reuse-basis` events identify the current or donor
source; relaxed hits also emit full `metadata-mismatch` differences. Such a mismatch reports changed metadata, not
necessarily a rejected digest under this candidate. Discovery dependency checks, discovery-selected-file checks,
Dea-input reuse, prepared-artifact validation and stable descriptor/path checks retain their baseline implementations.

Both policies start from the same archived tracked source. The patch is applied only inside the candidate build context
under ignored `l1/build/`; it is not installed into production source. Each policy builds its own compiler and prepares
its own cache. Different policy variants may therefore have different `D` and `N`. Image-time validation logs establish
each image's prepared `D`, `N` and profile, and every measured request must match its own image's values.

The accepted limitation is real: a same-size file rewrite with the compared modification time restored can reuse an old
digest. The controlled fixture demonstrates that outcome, while forced hashing and strict Dea-input validation read the
new bytes. This experiment does not establish byte equality from the relaxed metadata predicate.

## Reproduction and controls

From the repository root, run the stages separately so the diagnostic pass can be inspected before collecting timings:

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/measure.py \
  . l1/build/phase3-relaxed-toolchain --phase build
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/measure.py \
  . l1/build/phase3-relaxed-toolchain --phase diagnostic
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/measure.py \
  . l1/build/phase3-relaxed-toolchain --phase measure
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/analyze.py \
  l1/build/phase3-relaxed-toolchain
```

The Dockerfile derives from the historical same-path recipe. It additionally retains image-time validation diagnostics
and defines an independent candidate-validation target. Measurements use the same runtime base, GCC/Clang options,
absolute fixture path, UID/GID 65534, one CPU, 256 MiB memory with no additional swap, 64 PIDs, no network, no
capabilities, no new privileges, read-only input mount, private writable root layer and 64 MiB executable `/work` tmpfs.
The cache stays at `/opt/dea/l1/cache-template`. No compiler warm-up precedes either policy's first measured request,
and runtime memos are never shared across containers.

All requests use `-vvv`; compiler subprocess time excludes execution of the resulting program. Output validation checks
the exact expected multiset of 25 strings, since the fixture intentionally randomizes their order. Five repetitions of
baseline/candidate, prepared/inherited/copied and GCC/Clang produce 60 fresh containers and 120 requests. Baseline and
candidate are interleaved for each image/compiler pair, with policy order reversed on alternate repetitions. The first
accepted diagnostic pass counts as repetition one. These are fresh-container, warm-host measurements, not cold-disk
measurements or quiet-mode performance estimates.

The compressed report retains all structured events, individual timings, image IDs, compiler binary digests and identity
checks. Raw logs retain exact output and diagnostics. The local ignored `local-provenance.json` additionally records the
source revision and patch digest. Image build durations include Docker layer reuse and are not comparable clean-build
benchmarks.

## Validation

The candidate fixture covers ignored and retained fields, missing versus null values, malformed evidence, unreliable
metadata, force, complete-metadata refresh, strict discovery dependencies and selected files, and the preserved-mtime
content-change limitation. Existing support tests cover donor behavior, observability, artifact integrity and recovery;
identity, preparation integration and reporter tests exercise the candidate compiler and support implementation.

The first validation attempt used the older builder toolchain. Clang 14 rejected `--no-default-config`, causing runtime
archiver discovery to fail despite `ar` being present. The final validation target uses the same modern toolchain base
as the measurements and installs Python only in that separate target. Measured runtime images are unaffected by this
test environment adjustment. The failed log is retained alongside final validation evidence.

All final focused suites passed: the candidate C fixture (strict C99 warnings), preparation support (including donor and
observability fixtures), preparation identity, Stage 1 preparation integration, and the preparation reporter. A separate
artifact-boundary fixture changed only one saved `device`, `inode`, `ctime` or `ctime_ns` at a time: each forced exactly
one artifact read and refreshed full metadata. Source comparison also confirmed that discovery, stable-read, JSON,
preparation-build and artifact-validation code were unchanged. An intermediate malformed-record fixture failure was
corrected by replacing existing JSON values rather than appending duplicate keys; final validation uses the corrected
fixture and guard.

## Mechanism results

All 60 fresh containers and 120 compilations passed their identity, profile, provider, preparation-count and exact
output checks. Every runtime `D`, `N` and selected profile matched its own image-time evidence. Each first request
reused the completed profile and selected its artifact memo, with zero native preparation build commands and zero
managed-module compilations. Baseline and candidate `D` and `N` differ because each uses its own compiler
implementation.

| First-request work, every image variant | Baseline GCC | Candidate GCC | Baseline Clang | Candidate Clang |
| --------------------------------------- | -----------: | ------------: | -------------: | --------------: |
| Toolchain bytes hashed                  |   41,398,161 |         6,591 |    232,954,784 |           6,591 |
| Dea-input bytes hashed                  |    5,075,908 |     5,080,020 |      5,075,908 |       5,080,020 |
| Artifact bytes hashed                   |      482,858 |       482,858 |        521,434 |         521,434 |
| Discovery probes                        |           43 |            43 |             46 |              46 |
| Relaxed toolchain-file digest hits      |            0 |            96 |              0 |             110 |

The only candidate toolchain file hashed was `/etc/ld.so.cache`: 6,591 bytes, because its `mtime_ns` changed from
`8289578` to `0`. The hypothesis held in all 30 candidate first requests. All relaxed hits used current input-memo
records; donor behavior was exercised by focused tests. Event ordering confirms strict discovery rejection at `/bin`,
then fresh probes, then relaxed digest reuse. The old discovery result did not become accepted evidence.

All 47 prepared artifacts still failed strict metadata comparison and were hashed in each first request. The 4,112-byte
increase in Dea inputs belongs to the rebuilt candidate implementation; it is not a policy relaxation. Every second
request had zero hashing in all three categories and no metadata mismatches. Remaining probes were one for GCC and two
for Clang, under both policies.

## Timing results

Compiler subprocess seconds are median (minimum-maximum), five fresh-container repetitions per cell. Each first and
second request belongs to the same container. Individual samples and paired percentage changes are retained in the data.

| Image     | Compiler | First baseline      | First candidate     | Second baseline     | Second candidate    |
| --------- | -------- | ------------------- | ------------------- | ------------------- | ------------------- |
| Prepared  | GCC      | 1.458 (1.109-1.546) | 1.164 (0.847-1.195) | 0.534 (0.425-0.545) | 0.527 (0.395-0.596) |
| Prepared  | Clang    | 3.320 (2.770-3.496) | 1.667 (1.426-1.762) | 0.633 (0.593-0.717) | 0.650 (0.515-0.736) |
| Inherited | GCC      | 1.406 (1.136-1.490) | 1.126 (0.934-1.216) | 0.528 (0.447-0.571) | 0.537 (0.413-0.572) |
| Inherited | Clang    | 3.398 (2.995-3.473) | 1.650 (1.530-2.354) | 0.666 (0.588-0.747) | 0.733 (0.589-0.812) |
| Copied    | GCC      | 1.472 (1.302-1.680) | 1.159 (1.032-1.406) | 0.543 (0.498-0.646) | 0.580 (0.493-0.670) |
| Copied    | Clang    | 3.397 (3.113-4.650) | 1.696 (1.653-2.528) | 0.702 (0.647-0.944) | 0.697 (0.616-1.010) |

The median paired first-request reduction was 16.3-23.6% for GCC and 47.2-51.7% for Clang across image variants.
Toolchain-file hash time dropped from a pooled first-request median of about 295 ms (GCC) / 1,691 ms (Clang) to about
0.1 ms. Fresh discovery remained: summed probe times had pooled medians of about 521 ms (GCC) and 978 ms (Clang) in the
candidate. Candidate native-identity spans, which include Dea identity, probes and hashing, had per-image medians of
597-644 ms for GCC and 1,081-1,083 ms for Clang. These nested timings are not added to inclusive spans or compiler
elapsed time. Discovery and work outside native identity remain substantial after toolchain hashing is removed.

Warm-request medians improved slightly in two cells and worsened by about 1.8-10.0% in four cells; the ranges overlap.
Median paired warm-request percentage changes indicate slowdowns of about 0.1-7.0%, depending on the cell. The two
summaries differ because the median of paired ratios is not the ratio of medians. There is no hash/probe-count
regression, but these five debug samples do not establish absence of a material warm-time regression. Extra current-file
kind checks, diagnostic overhead and ordinary timing variation are possible contributors; this experiment does not
isolate them.

## Interpretation and recommendation

The mechanism succeeds and the first-request benefit is measurable, especially for Clang. The experiment supports
proposing this narrowly scoped best-effort policy for a separate adoption discussion, but does not support changing the
strict default now. The preserved-mtime fixture demonstrates a real content-change detection gap, and warm-time
performance remains unresolved. Any adoption proposal should make that guarantee explicit and settle the deployment
trust assumptions and warm-performance evidence through the pending Phase 3/ADR process.

No production compiler source, public interface, cache schema, or default validation policy was changed. No commit or
push was made. The wider Phase 3 alternatives remain open; this result does not rank image inheritance against copying,
or establish behavior on Windows or other filesystems.

## Retained evidence

- `candidate.patch`: scoped production-code candidate plus candidate donor-test expectations.
- `candidate_test.c` and `artifact_boundary_test.py`: focused policy and boundary fixtures.
- `Dockerfile`, `measure.py` and `analyze.py`: reproducible builds, gated matrix and report checks.
- `report.json.gz`: all 120 request records, complete events, image/compiler identities and profile checks.
- `summary.json`: individual timing samples, medians, ranges, byte totals and probe counts.
- `analysis.json`: per-file hash inventory, paired timing changes and inclusive span medians.
- `raw-logs.tar.gz`: exact program output, diagnostics, image-time evidence, build and validation logs.
- `environment.json` and `source-scope-checks.json`: Docker provenance and unchanged-source checks.

The raw-log archive preserves all 624 member filenames and file contents. For repository storage, members are sorted,
owner/group IDs and archive timestamps are zeroed, owner/group names are empty, and the gzip header omits its original
filename. Experimental timestamps inside the logs are unchanged.

The engine was Docker 29.7.2 with overlayfs on an x86_64 Ubuntu 24.04.2 VM, kernel 6.8.0-64-generic. Runtime images used
GCC 14.2.0 and Clang 19.1.7. Source revision provenance remains in the ignored local experiment output directory.
