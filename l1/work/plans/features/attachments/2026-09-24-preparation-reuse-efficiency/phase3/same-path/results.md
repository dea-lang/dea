# Phase 3: Same-path prepared image rerun

- Date: 2026-09-25
- Scope: Diagnostic rerun of the first image inheritance and selective-copying experiment.
- Status: Completed experiment; broader Phase 3 deployment and ADR decisions remain pending.

## Question and correction to the first experiment

Does keeping the cache at `/opt/dea/l1/cache-template` from preparation through every compilation let a fresh container
select and reuse build-time validation memos? The [first image experiment][original-results] instead copied the cache
from that path to `/work/dea-l1-cache`, where its artifact memo selection returned `no-matching-memo`. Direct inspection
of that experiment's prepared image found **zero** artifact-validation memo files: `--prepare-stdlib` completed profiles
but did not create those memos. The path change would also change the artifact memo selection key, which includes the
canonical profile path, but the first experiment did not isolate its effect because it had no artifact memo to select.
Its original Dockerfile, driver, report and results remain historical evidence of the copy scenario.

This rerun keeps one cache path and deliberately performs one GCC and one Clang build-time validation after preparation.
The prepared, inherited and copied images each contain two artifact memo files before any measured request. The
[Dockerfile] inherits the prepared stage with `FROM prepared` or copies the Dea installation and `v1` cache into the
same runtime base at the same paths, as described by Docker's [multi-stage build guide][docker-multistage]. The `v1`
tree is owned by UID 65534 in each variant. No service application is installed.

## Reproduction and controls

Run the [driver] from the repository root with the local Docker daemon and the existing base images:

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/same-path/measure.py \
  . l1/build/phase3-same-path-study
```

The driver archives tracked source at experiment start, builds the prepared stage and its three derivatives, and records
image build wall time and inspect size separately from container launch and compiler time. The prepared stage uses GCC
and Clang `-O0` and validates both completed profiles with `--build --no-auto-prepare` before packaging. Each of three
repetitions runs a fresh container for every prepared/inherited/copied image, compiler and debug/quiet setting. Each
container compiles twice, and each program's 25 output lines are checked outside the timed compiler interval. The native
key, provider choices, preparation build counts, memo decisions, mismatch fields, probes and bytes hashed are retained
per invocation in the [report].

The attached report is stored as `report.json.gz`; decompression recovers the original JSON bytes. The historical driver
continues to write uncompressed `report.json` in its local output directory.

All measured containers use `L1_STDLIB_CACHE=/opt/dea/l1/cache-template`, which bypasses the wrapper's copy to
`/work/dea-l1-cache`. They use UID/GID 65534, one CPU, 256 MiB memory and swap, 64 PIDs, no network, no capabilities, no
new privileges, a read-only request-source mount, and an executable 64 MiB `/work` output tmpfs. Unlike the first
experiment, the container root has a private **writable** layer so the agreed cache path can accept refreshed memos.
Each container is removed after its case. The writable layer is a diagnostic control, not a service deployment recipe;
its change also prevents a controlled cross-report timing comparison.

The measured engine was Docker 29.7.2 using overlayfs on an Ubuntu 24.04.2 Linux 6.8.0-64-generic VM, with the same
Debian 13.7 runtime base, GCC 14.2.0 and Clang 19.1.7 as the first experiment. Build layers and host storage were warm.
There were 36 fresh compilation containers, 72 correct program executions, nine separate startup containers and one
malformed-memo control. No compilation timed out or ran a native preparation build command.

## Results

The prepared image build took 30.05 seconds; with its layers cached, inherited and copied image builds took 3.11 and
4.93 seconds. Docker reported 199.520, 199.521 and 199.389 MiB for prepared, inherited and copied, respectively. The
prepared stage also holds the small build-time validation fixture and its outputs, hidden at runtime by `/work` tmpfs;
image size is therefore indicative, not a clean packaging-size comparison. Median standalone startup samples were 1,539,
1,454 and 1,907 ms, respectively, with three samples per image. These are local, warm-cache observations, not cold build
or launch estimates.

Compiler subprocess seconds are median (minimum-maximum) across three fresh containers for each row and verbosity. Debug
and quiet runs use separate containers.

| Compiler | Image     | First quiet            | Second quiet        | First debug            | Second debug        |
| -------- | --------- | ---------------------- | ------------------- | ---------------------- | ------------------- |
| GCC      | Prepared  | 4.516 (4.186-4.701)    | 1.710 (1.627-1.872) | 4.242 (3.895-5.819)    | 1.675 (1.309-1.806) |
| GCC      | Inherited | 5.046 (4.171-5.475)    | 1.668 (1.556-3.306) | 5.239 (4.228-5.337)    | 1.924 (1.521-2.350) |
| GCC      | Copied    | 6.680 (3.768-8.478)    | 2.580 (1.534-2.887) | 6.385 (4.907-8.819)    | 2.545 (1.544-2.891) |
| Clang    | Prepared  | 9.952 (9.739-11.847)   | 2.182 (1.863-2.353) | 9.950 (9.908-11.971)   | 1.979 (1.789-2.250) |
| Clang    | Inherited | 13.678 (9.349-14.561)  | 2.004 (1.900-2.788) | 9.421 (8.849-13.514)   | 2.491 (1.932-2.981) |
| Clang    | Copied    | 12.912 (10.569-15.452) | 2.180 (2.161-3.475) | 14.515 (11.882-16.922) | 2.747 (2.010-3.123) |

Every debug run had the same native key and toolchain observation selection key for a given compiler across all three
images. All first invocations hit the completed native profile and selected eleven managed interface providers, with
zero native preparation build commands and zero managed module compilations. **The artifact-validation memo was found
and selected in every first invocation** (`hit`, `validated-memo`), unlike the first experiment's `no-matching-memo`.
Selection did not avoid artifact hashing: all 47 recorded artifact metadata comparisons in each first debug run reported
`inode` as the first changed field. Each first GCC request hashed 482,858 artifact bytes, 5,075,860 Dea-input bytes and
41,398,161 toolchain-input bytes; Clang hashed 521,434, 5,075,860 and 232,954,784 bytes, respectively.

The build-time toolchain observation memo also failed validation at the first runtime request: the first changed
metadata field was the `/bin` directory inode (`2506904` in the image versus `2516112` in the container). The first
GCC/Clang requests made 43/46 probes. Their Dea-input and toolchain-input comparisons likewise first reported inode
changes (61 Dea inputs and 97/111 toolchain inputs for GCC/Clang). This records a metadata mismatch, not a changed
native content key or failed completed profile. The reporter emits only the **first** differing metadata field in a
fixed order; the report cannot establish that later fields such as change time stayed equal. In every second request,
the refreshed toolchain and artifact memos hit, probes fell to one/two, and these three hash categories read zero bytes.

The separate malformed-evidence image corrupts toolchain memo JSON under the same cache root but leaves completed
profiles intact. Its first Clang request reported `malformed-memo`, fell back to 46 probes and 240,347,792
toolchain-input bytes hashed, hit the valid native profile, and produced correct output. Its artifact memo was selected
but its artifact metadata still caused rehashing. Optional evidence did not become authority merely by being present.

## Interpretation and portability

The `inode` field is **validation metadata**, not an ingredient of the native content key. In the current
[preparation implementation][platform], POSIX stores `st_dev`, `st_ino`, size, mode, modification time and change time;
[memo validation][storage] compares those metadata fields before reusing a previously computed digest. If identity or
metadata changes, it hashes the file again. This conservatively catches replacement of a same-path file without trusting
a stale digest, at the cost measured here when the image/container boundary changes file identifiers.

The Windows branch fills the same `inode` field from the `GetFileInformationByHandle` high/low file index, with the
volume serial number as `device`; it also records size and attributes plus `LastWriteTime` and `ChangeTime` from
`FILE_BASIC_INFO`. Microsoft documents that file-ID support and stability depend on the filesystem, and that the 64-bit
identifier is not guaranteed unique on ReFS ([file information][windows-file-info],
[basic information][windows-basic-info]). This establishes an analogous Windows identifier and a portability caveat;
there was no native Windows run, so no Windows hit-rate or performance claim follows.

The agreed path fixes artifact memo **selection** once such a memo exists. It does not make the build-time metadata
valid in these fresh overlayfs containers: artifact files still hash, and toolchain observation still triggers discovery
and input hashing. Image inheritance and selective copying retained compiled artifacts equally in this experiment. The
first report's cache-copy selection miss was real, but its lack of any build-time artifact memo means the original cause
was not isolated to the path move. The private writable layer, build-time validation pass and warm host conditions
differ from that report. Timings and the small sample cannot rank these packaging mechanisms or establish behavior on
other container filesystems. Worker lifetime, read-only deployment, request isolation, toolchain updates and the broader
Phase 3 ADR decision remain open.

[docker-multistage]: https://docs.docker.com/build/building/multi-stage/
[dockerfile]: Dockerfile
[driver]: measure.py
[original-results]: ../results.md
[platform]: ../../../../../../../compiler/stage1_l0/support/preparation/platform.h
[report]: report.json.gz
[storage]: ../../../../../../../compiler/stage1_l0/support/preparation/storage.h
[windows-basic-info]: https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info
[windows-file-info]: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information
