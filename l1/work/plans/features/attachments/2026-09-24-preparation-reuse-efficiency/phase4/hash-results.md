# Phase 4 SHA-256 backend decision

- Date: 2026-10-16
- Decision: Retain the current dependency-free portable C backend.
- Production hash changes: None.

The final bounded compression-function comparison also retained production SHA-256 after its actual-consumer gate; see
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-portable-results.md][portable].

## Alternatives and environment

This comparison rechecks the unchanged backend, the earlier complete-block portable optimization, and installed platform
crypto libraries. The previous bounded study also tested a 16-word circular schedule and rejected it after 10.59-12.65%
large-file regressions. Its complete prepared-consumer comparison found that complete-block processing missed the
adoption gates: Clang improved by 100.507 ms and 3.22%, while GCC improved by 11.232 ms and 0.85%. See
[l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/results.md][earlier-results].

The current Linux experiment used the retained `dea-sha256-benchmark-baseline:local` image, Debian GCC 14.2.0, `-O1`,
OpenSSL 3.5.7 EVP SHA-256, one CPU, 512 MiB, and no network. These are the actual large inputs from the earlier study:
GCC `cc1` (34,148,896 bytes), LLVM (129,673,080), Clang C++ (71,043,800), and Z3 (27,751,664). The host experiment used
macOS Intel, Apple Clang 17.0.0, `-O2`, CommonCrypto SHA-256, and its 272,034,048-byte Clang executable. Apple Clang
advertises `--no-default-config`; these direct native harness runs do not independently establish full L1 toolchain
acceptance. Windows and macOS ARM backends were unavailable.

Each environment used five interleaved repetitions, reversing backend order on alternate repetitions. The temporary
driver compiled each backend with C99, `-Wall -Wextra -Werror -pedantic`; only the CommonCrypto adapter suppressed its
API deprecation warnings. Both environments included deterministic 4 KiB and 8 MiB controls. Memory measurements load
and initialize input before timing, use deliberately unaligned addresses, and test 64 KiB and irregular streaming
divisions. Complete stable-file measurements use the unchanged production open/read/descriptor/path validation function.
Sequential read controls consume every byte into a repeatable checksum.

These are shared-host observations with other development work potentially running concurrently. A new process or
container does not establish a cold filesystem cache. The retained reports contain every wall/CPU sample, byte count,
digest, range, and median. The platform implementations are acceleration/headroom references; this experiment does not
establish which CPU instructions a system library selected or measure whole compiler consumer benefit.

## Measurements

Linux stable-file hash medians, in milliseconds:

| Input     | Current | Complete-block | OpenSSL EVP |
| --------- | ------: | -------------: | ----------: |
| 4 KiB     |   1.235 |          1.545 |       3.064 |
| 8 MiB     |  61.950 |         63.043 |      33.362 |
| GCC `cc1` | 225.463 |        202.126 |     120.097 |
| LLVM      | 866.791 |        870.568 |     404.369 |
| Clang C++ | 503.583 |        486.420 |     207.693 |
| Z3        | 181.529 |        185.380 |      85.446 |

macOS Intel stable-file hash medians, in milliseconds:

| Input         |  Current | Complete-block | CommonCrypto |
| ------------- | -------: | -------------: | -----------: |
| 4 KiB         |    0.137 |          0.132 |        0.216 |
| 8 MiB         |   45.042 |         42.228 |       25.230 |
| Host compiler | 1445.740 |       1496.619 |      849.916 |

Linux memory-only 64 KiB streaming medians for LLVM were 845.392/714.078/376.149 ms for current/complete-block/OpenSSL.
Corresponding Clang C++ medians were 475.719/486.581/203.267 ms. macOS host-compiler memory medians were
1420.572/1461.056/766.692 ms for current/complete-block/CommonCrypto. These independent operations explain
hash-computation headroom; they must not be added to the inclusive stable-file times.

Complete-block processing remains inconsistent: it improved Linux `cc1` by 10.35%, but regressed LLVM by 0.44%, Z3 by
2.12%, and the macOS compiler input by 3.52%. It does not overturn the earlier complete consumer study. Platform
libraries reduced large-input stable hashing by approximately 41-59%, while startup/context cost worsened the 4 KiB
stable control. The bounded results justify a possible future integrated acceleration study, rather than a production
backend change in this plan.

## Correctness and lifecycle limits

Every measured digest and byte count matched an independent `sha256sum`/`shasum` reference. Each backend also passed
three standard known-answer messages and nine deterministic unaligned irregular-streaming cases: empty, 3, 55, 56, 63,
64, 65, 129, and 1,000,000 bytes. Python `hashlib.sha256` verified those vectors independently. The two timing reports
contain 423 measurements and 72 vector records in total.

Separate correctness builds interposed reads only in the experiment harness. Each of the three backends on both
platforms accepted unchanged files and clean short reads, rejected a partial read followed by I/O failure, rejected
content mutation during reading, and rejected a missing file. Failure left the digest output unpublished and metadata
absent. The correctness reports retain 72 additional vector records and six backend reader-check records. Timed builds
do not include these read interposers.

The OpenSSL adapter allocates an EVP context. Its experiment-only mapping onto `PcSha` releases that allocation on
successful finish; the production reader has no backend abort/free call when a read fails. Thus the rejection checks
establish return/output behavior, **not a leak-free platform lifecycle**. Adoption requires an explicit cleanup path for
every early exit plus allocation-failure and ownership validation. CommonCrypto uses fixed context storage, but its API
deprecation and supported SDK policy still need a production decision. No persisted digest, stable-read predicate,
identity schema, content coverage, or production dependency changed here.

## Selected policy and follow-up boundary

Retain the bundled portable SHA-256 implementation for all supported platforms. The optimized portable candidate has no
reproducible cross-input consumer improvement sufficient for adoption. A substantially imported implementation was not
added: the earlier bounded portable study and this mixed recheck provide no basis to pay its review, licensing,
vendoring, and maintenance cost within this phase.

Defer platform acceleration. CommonCrypto is platform-specific; Linux OpenSSL adds a library/version/build dependency
and the available image has no OpenSSL development headers; Windows CNG was not implemented or measured. Runtime
selection, fallback behavior, cross-backend failures, cleanup, and deployment availability require separate integration
work. This retains the existing identity/reuse boundary and resolves the backend choice for this plan. A future change
must preserve identical SHA-256 bytes, every stable-read check, and dependency coverage, establish the supported
platform/dependency policy, and pass a controlled whole-consumer comparison. No slower or weaker validation mode is
introduced as a fallback.

## Reproduction

The harnesses restore the measured preparation support in isolated copies with
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/measured-preparation.patch][measured-support].
This removes the later legacy-Clang compatibility policy before constructing either hash control. Actual consumers also
restore shared compiler-home support inputs. Production sources and historical report data remain unchanged. Patch
replay was checked byte for byte against the original control support source.

From the repository root:

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --label macos-intel-apple-clang17 --output /tmp/hash-macos.json
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --reader-only --label macos-intel-apple-clang17 --output /tmp/hash-correctness-macos.json
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --docker-image dea-sha256-benchmark-baseline:local --optimization 1 --label linux-x86_64-gcc14 --output /tmp/hash-linux.json
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-measure.py --reader-only --docker-image dea-sha256-benchmark-baseline:local --optimization 1 --label linux-x86_64-gcc14 --output /tmp/hash-correctness-linux.json
```

The retained reports are
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-linux.json.gz][linux],
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-macos.json.gz][macos],
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-correctness-linux.json.gz][linux-checks],
and
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/hash-correctness-macos.json.gz][macos-checks].
The driver creates and removes an owned temporary directory beside the evidence so Colima can mount it; it does not
modify production sources. The OpenSSL opaque declarations and CommonCrypto adapter are experimental harness code. All
four reports parse as JSON; the script compiles with `python3 -m py_compile`; stable-read checks and independent digest
assertions passed. The reports are generated projections of parsed command output with derived summaries; raw stdout was
not retained, so no recursive-equality claim is made against an original raw-log payload. Each measurement retains its
path as the stable `<input:NAME>` alias determined by the recorded input label. The driver now applies exact
string-value path replacement to its complete generated report and verifies recursive equality after reversing that
replacement; container shape and nonstring values remain equal. The retained timing reports restore those aliases from
their recorded input labels. JSON records contain no private host input paths or source revisions.

Repository JSON reports are lossless gzip copies of the generated JSON; decompressed bytes and recursive JSON equality
were verified. Reproduction commands write ordinary JSON before archival compression.

[earlier-results]: ../../../../refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/results.md
[linux]: hash-linux.json.gz
[linux-checks]: hash-correctness-linux.json.gz
[macos]: hash-macos.json.gz
[macos-checks]: hash-correctness-macos.json.gz
[measured-support]: ../measured-preparation.patch
[portable]: hash-portable-results.md
