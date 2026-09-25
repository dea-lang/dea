# Phase 3: Complete metadata differences at the image-to-container boundary

- Date: 2026-09-25
- Scope: One fresh-container observability subset of the [same-path experiment][same-path].
- Status: Completed diagnostic subset; Phase 3 deployment and ADR decisions remain pending.

## Reproduction and controls

Run the [capture driver][driver] from the repository root with the same local Docker base images as the earlier
experiment:

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/metadata-details/capture.py \
  . l1/build/phase3-metadata-details
```

The driver archives tracked source containing the complete-difference observation change, rebuilds the prepared,
inherited and copied targets from the [same-path Dockerfile][dockerfile], then runs one fresh container per image and
compiler (GCC and Clang). Each container compiles twice with `-vvv`, and the expected 25 program output lines are
checked after each timed compilation. The cache remains at `/opt/dea/l1/cache-template` throughout. Containers use
UID/GID 65534, one CPU, 256 MiB memory and swap, 64 PIDs, no network, no capabilities, no new privileges, a read-only
input mount, a private writable root layer and a 64 MiB `/work` tmpfs. Compiler options and absolute input paths match
the earlier same-path experiment. The [JSON report][report] retains every observation, decision, probe count, hash-byte
count and individual timing; raw build and compiler logs are under the ignored `l1/build/phase3-metadata-details/`
directory. The generated `l1/build/phase3-metadata-details/report.json` was copied to the [attached report][report]
after this run. The earlier Dockerfile, driver and reports were not changed.

The attached report is now stored as `report.json.gz`; decompression recovers the original JSON bytes. The historical
driver continues to write uncompressed `report.json` in its local output directory.

## What changed

For **each** of the three image variants, the first GCC request produced 206 metadata-mismatch events and the first
Clang request produced 220. The field sets and per-scope counts were identical across the variants. Counts in the last
column show how many events also had a differing subsecond modification time; every event in the row had differing
`inode`, `ctime` and `ctime_ns`.

| Observation scope    | GCC events | Clang events | Also differing `mtime_ns` |
| -------------------- | ---------: | -----------: | ------------------------: |
| Dea input            |         61 |           61 |                        24 |
| Toolchain dependency |          1 |            1 |                         1 |
| Toolchain input      |         97 |          111 |                         1 |
| Prepared artifact    |         47 |           47 |                        47 |

No event reported a difference in `device`, `size`, `mode`, whole-second `mtime`, or `reliable`. The `mtime_ns`
differences all went from a nonzero build-time value to `0` at runtime. For example, a prepared `std/array.o` artifact
had `mtime_ns: 930871224 -> 0`; its `inode` changed from `151042` to `151500`, `ctime` from `1790358488` to
`1790358512`, and `ctime_ns` from `950660842` to `227477239`. The complete emitted observation was:

```json
{
  "current": 151500,
  "differences": {
    "ctime": {"current": 1790358512, "previous": 1790358488},
    "ctime_ns": {"current": 227477239, "previous": 950660842},
    "inode": {"current": 151500, "previous": 151042},
    "mtime_ns": {"current": 0, "previous": 930871224}
  },
  "event": "metadata-mismatch",
  "field": "inode",
  "kind": "file",
  "path": "/opt/dea/l1/cache-template/v1/native/fe71645b6a5639473b83a86b885746aabc66b7e6a0320584e945c113c8638d63/modules/std/array.o",
  "previous": 151042,
  "schema": 1,
  "scope": "artifact"
}
```

The `/bin` toolchain dependency also changed in all four fields: `inode: 2506904 -> 2516112`,
`ctime: 1790235604 -> 1790235844`, `ctime_ns: 849993371 -> 646286939`, and `mtime_ns: 849993371 -> 0` in the prepared
image case. A typical toolchain input such as `/usr/bin/gcc` changed `inode`, `ctime` and `ctime_ns`, but not
`mtime_ns`. The copied image had different current file IDs and change times for some paths; its **set of changed
fields** and validation work matched prepared and inherited images. None of the six second compilations reported a
metadata mismatch.

The first request in every container selected the build-time artifact-validation memo (`hit`, `validated-memo`) and the
completed native profile (`hit`, `validated-profile`). The artifact memo selection did not make its stored digest
metadata valid: all 47 artifact comparisons still required file hashing. The `/bin` metadata mismatch invalidated the
toolchain observation memo (`miss`, `metadata-changed`), which led to discovery and input hashing. Each first GCC
request hashed 482,858 artifact bytes, 5,075,908 Dea-input bytes and 41,398,161 toolchain-input bytes; each first Clang
request hashed 521,434, 5,075,908 and 232,954,784 bytes, respectively. After the first request refreshed local evidence,
each second request hit the memos and hashed zero bytes in these categories. Native preparation build commands and
managed module compilations remained zero, and all programs ran correctly.

This observation establishes **which recorded metadata changed**, including change times and subsecond modification
times that the earlier singular `field: inode` view concealed. It does not isolate which Docker layer, copy operation or
filesystem transition caused each change. In particular, unchanged whole-second `mtime` and file size do not make the
old digest memo safe to trust under the current metadata policy. One sample per image/compiler is sufficient to expose
the fields but is not a timing distribution or evidence that one packaging variant is faster. The private writable layer
remains a diagnostic control, not a proposed service trust boundary.

[dockerfile]: ../same-path/Dockerfile
[driver]: capture.py
[report]: report.json.gz
[same-path]: ../same-path/results.md
