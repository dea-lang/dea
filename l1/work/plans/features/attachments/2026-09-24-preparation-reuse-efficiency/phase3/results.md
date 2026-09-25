# Phase 3: Prepared image inheritance and selective copying

- Date: 2026-09-25
- Scope: First bounded Phase 3 packaging experiment; containerized compiler service stand-ins only.
- Status: Completed experiment; broader Phase 3 deployment and authority decisions remain pending.

## Question and external practice

Can a service image inherit a prepared compiler image, or copy its required Dea files into an equivalent runtime base,
without losing completed native profiles or changing the cost of validating them in fresh containers? Docker documents
both `FROM` inheritance and `COPY --from` across stages or images in its
[multi-stage build guide](https://docs.docker.com/build/building/multi-stage/). Its
[build-cache guide](https://docs.docker.com/build/cache/optimize/) describes cache mounts as persistent build-time
storage; this experiment instead puts prepared artifacts in the resulting image. As a compiler-installation example,
[Compiler Explorer's Go installer](https://github.com/compiler-explorer/infra/blob/main/docs/ce_install_yaml.md)
prebuilds selected standard libraries and stores their cache alongside the installation. These sources establish
packaging options, not Dea memo portability or a runtime trust boundary.

## Reproduction and controls

Use [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/Dockerfile][dockerfile] and
[l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/measure.py][driver]:

```sh
python3 l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/measure.py \
  . l1/build/phase3-image-study
```

The driver archives the tracked source into an isolated build context and builds a fresh `prepared` stage from the
retained `l1-test` builder and `dea-preparation-investigation-clang` runtime base. It prepares GCC and Clang `-O0`
profiles once. `inherited` uses `FROM prepared`; `copied` uses the same runtime base and copies the Dea wrapper/native
compiler, build tree, interfaces, include tree, shared sources and complete prepared `v1` cache into the same paths. The
copy stage first removes corresponding base-image paths so old entries cannot merge with new ones. Both preserve the
base image's native GCC/Clang toolchains. A fourth derivative deliberately corrupts optional toolchain memo JSON while
retaining completed native profiles.

Each of three repetitions starts a fresh container per image, compiler and verbosity. It compiles the same 25-line
example twice in one container and verifies each executable's output separately from the timed compiler command. Each
run uses one CPU, 256 MiB memory and swap, 64 PIDs, no network, a read-only root, no capabilities, no new privileges,
UID/GID 65534 and an executable 64 MiB `/work` tmpfs. Request source is mounted read-only; output and cache copies stay
private to the container. The compiler uses absolute source/project paths and `--no-auto-prepare`. Debug runs add only
`-vvv`; quiet runs control its overhead. Variant order reverses in the middle repetition. Container launch totals and
separate `docker run ... true` startup samples are recorded, alongside image build wall time and inspect size. The
retained [report] contains each invocation, image identity, decision, mismatch, counter, probe, hash byte count,
duration and successful output check. Raw stdout/stderr and build logs remain in the local build directory.

The attached report is stored as `report.json.gz`; decompression recovers the original JSON bytes. The historical driver
continues to write uncompressed `report.json` in its local output directory.

The tested environment was Docker Engine 29.7.2 with overlayfs on an Ubuntu 24.04.2 VM, Linux 6.8.0-64-generic, and
Debian 13.7 containers with GCC 14.2.0 and Clang 19.1.7. The samples used warm host storage and do not represent a cold
host or other container engines. The experiment built three test images, ran 36 fresh compilation containers and 72
successful program output checks, plus nine separate startup containers and one stale-evidence case. No timeouts or
native preparation build commands occurred.

## Results

The `prepared` image build took 148.80 seconds. With that stage cached, `inherited` took 3.75 seconds and `copied` took
7.94 seconds to build. Docker reported 199.4 MiB for each of the three final images. These build times include local
Docker work and cached dependencies; they are not general image build costs. Median standalone startup samples were 754,
739 and 860 ms for `prepared`, `inherited` and `copied`, respectively, with three samples each.

Compiler subprocess seconds below are median (minimum-maximum) across three independent fresh containers per row. Debug
and quiet runs use separate containers; their timings are not paired within a container.

| Compiler | Image     | First quiet         | Second quiet        | First debug         | Second debug        |
| -------- | --------- | ------------------- | ------------------- | ------------------- | ------------------- |
| GCC      | Prepared  | 2.286 (2.169-3.638) | 0.828 (0.761-1.468) | 2.189 (2.165-3.636) | 1.098 (0.750-1.104) |
| GCC      | Inherited | 2.493 (2.204-2.936) | 0.853 (0.798-1.110) | 2.378 (2.059-6.188) | 1.077 (0.923-1.608) |
| GCC      | Copied    | 2.386 (2.300-2.907) | 0.954 (0.864-1.358) | 2.393 (2.151-2.540) | 0.921 (0.841-0.980) |
| Clang    | Prepared  | 4.846 (4.750-8.384) | 0.938 (0.930-1.549) | 5.226 (5.160-9.924) | 0.966 (0.882-1.632) |
| Clang    | Inherited | 5.162 (4.947-5.218) | 1.013 (0.942-1.202) | 6.216 (5.886-6.649) | 1.150 (0.958-1.536) |
| Clang    | Copied    | 5.368 (5.098-6.036) | 1.236 (1.036-1.277) | 5.788 (5.342-6.783) | 1.147 (1.040-1.185) |

Operation counts were identical across all three images in every debug repetition. The native key matched across images
for each compiler. All first invocations hit their completed native profile, selected eleven managed interface
providers, and performed zero preparation build commands and zero managed module compilations. Their build-time
toolchain observation memo was rejected for changed metadata, first reporting `/bin` directory inode `2506904` versus
`2516112`. GCC performed 43 probes and hashed 5,075,860 Dea-input bytes, 41,398,161 toolchain-input bytes and 482,858
artifact-validation bytes. Clang performed 46 probes and hashed the same Dea-input bytes, 232,954,784 toolchain-input
bytes and 521,434 artifact-validation bytes. The artifact memo had no matching runtime selection; its completed profile
still validated and was reused. Every second invocation hit its refreshed toolchain and artifact memos, made one GCC or
two Clang probes, and hashed zero bytes in these three categories.

The stale-evidence derivative kept a profile hit and correct output. It reported malformed toolchain observation/input
memos, performed 46 Clang probes, and hashed 240,347,792 toolchain-input bytes through the normal fallback. This checks
that copied optional evidence cannot authorize reuse merely by being present.

The timing ranges overlap and the first repetition was often slower. They support no reliable speed ranking among these
packaging choices. The exact operation counts do support a narrower conclusion: **inheritance and explicit copying both
retain compiled native support, but neither avoids the first runtime validation cost in this Docker configuration**.
Reusing validation records across fresh requests remains a separate question. This experiment neither implements a
service nor establishes cache portability across hosts, toolchain updates or storage backends. The broader Phase 3
worker, distribution and shared-storage alternatives remain open.

[dockerfile]: Dockerfile
[driver]: measure.py
[report]: report.json.gz
