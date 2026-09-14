# Experimental L1 Wine/MSYS2 runner

Version: 2026-09-14

Run these commands from `l1/`. Docker must provide Linux amd64 containers and the host needs Python 3.10 or newer. The
container uses Windows UCRT64 GCC and Python through patched Wine, including L0 Stage 2 bootstrap for L1. Native Windows
CI remains the authority for Windows support. ARM64 emulation has not been validated.

```bash
make docker-wine-toolchain                 # expensive first setup; independently cached
make docker-wine-image                     # adds the cached Windows workspace venv
make docker-wine CMD=help                  # automatically prepares missing images
make docker-wine CMD=test-stage1 TESTS=preparation_support_test
make docker-wine CMD='clean test-all' L1_TEST_JOBS=2 L1_TRACE_TEST_JOBS=1
make docker-wine CMD=test-stage1-trace TESTS=string_vector_test L1_TRACE_ARTIFACT_DIR="$PWD/build/wine-traces"
```

## Cache and build stages

The toolchain image has independent MSYS tools, GCC, Python/pip and uv installation layers. A failure in a later
transaction preserves completed layers for the next attempt. Python/uv package downloads also use a persistent BuildKit
cache. Documentation and manual pages are omitted from these later packages; runtime data, headers, libraries and Python
modules are retained. The initial package setup took roughly 35 minutes after the base download on the tested host, plus
roughly five minutes for the venv; these are observations, not timing guarantees. Docker's build cache and local images
must remain available between runs.

The runner derives local image tags from file contents and inspects those tags first. If both images exist, it issues
**no Docker build command**. Worktrees with identical image inputs share these images. There is no timestamp stamp that
can go stale after Docker image pruning.

| Change                                                         | Work required on the next invocation                        |
| -------------------------------------------------------------- | ----------------------------------------------------------- |
| L1/L0 compiler sources, tests, local edits or new source files | Transfer a fresh source snapshot; reuse both images         |
| Root Makefile, workspace manifests or `uv.lock`                | Build the environment image; reuse the toolchain            |
| Container entrypoint                                           | Build the environment image; reuse the cached venv layer    |
| Toolchain Dockerfile, including pinned upstream digest         | Build the affected package layers and dependent environment |
| Deleted local images                                           | Recreate missing images using surviving Docker build layers |

`DOCKER_WINE_IMAGE_PREFIX` changes the local image namespace (default `dea-l1-wine`). The full content hash appears in
each tag printed by the runner. To deliberately retry an unchanged image recipe, remove its printed image tag with
`docker image rm <tag>`, then rerun the preparation target. Docker can still reuse its layers. Changing a toolchain
recipe or its pinned base is an explicit update; ordinary runs never refresh packages or pull a moving base tag.

The venv image uses the root Makefile's pip fallback because the tested uv build rejects the MSYS2 Python platform
`mingw_x86_64_ucrt_gnu`. Its `uv.exe` is renamed to `uv-disabled.exe` in that image; the toolchain image retains the
original executable. This keeps tests on Windows MSYS2 Python. The fallback installs the root dev/docs dependency-group
constraints; ordinary Make targets still perform their existing dependency-satisfaction check. It does not perform a
frozen `uv.lock` installation.

## Execution and isolation

Every run starts from the environment image and copies current `l0/`, `l1/` and shared build scripts from the working
tree, including uncommitted/untracked sources. Host build directories, virtual environments and Python caches are
excluded. Source changes therefore do not trigger image builds. Compiler outputs and native preparation caches are fresh
per run; use multiple targets in one `CMD` to reuse them within that run.

`CMD` contains Make arguments, with shell-style quoting for argument grouping. It is not evaluated as a shell script.
`TESTS`, `L1_TEST_JOBS` and `L1_TRACE_TEST_JOBS` are forwarded explicitly. GCC is the prototype's default for all three
compiler roles; host compiler paths are not inherited. Make assignments inside `CMD` can override container settings.

`L1_TRACE_ARTIFACT_DIR` is resolved relative to the invoking `l1/` directory and mounted at `C:/trace-artifacts` for the
Windows process. This is the only writable host mount. Other outputs disappear with the disposable container. The source
archive uses stdin, so interactive stdin forwarding from the host is not part of this interface; subprocess stdin
fixtures inside the test suite still use their own pipes. Container failure status propagates through Docker and then
Make's normal failure handling.

## Prototype validation

The initial amd64 run built Windows GCC 16.2.0 and MSYS2 Python 3.14.7, bootstrapped L0 Stage 2 and L1, and verified all
23 bundled interfaces. Repeated `CMD=help` calls reused both images without invoking Docker build. A quoted Make
argument probe wrote an artifact through the host mount, and a deliberate Windows shell exit propagated its status. All
four examples and all six runner regressions passed inside the container. The focused `string_vector_test` trace passed
with zero errors, warnings or leaked object/string pointers; its report survived container removal. The existing POSIX
environment-stackability check reported its expected Windows skip. The embedded ARC regression suite, generated-C
identity, installed-layout preparation and native link-set checks also passed.

The complete normal suite returned **75 passed and 7 failed** (successful wrapper statuses can include optional-tool
skips). Its failures are retained as feasibility findings:

| Failing fixture                                     | Observed failure                                                                                                                               |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `compiler_filesystem_support_test.py`               | Harness status 63: a diagnostic probe confirmed `C:\...` from the native helper versus `C:/...` from MSYS2 Python for the same temporary path. |
| `l1c_stage1_preparation_test.py`                    | Exact cache-path membership in repair arguments failed.                                                                                        |
| `l1c_stage1_managed_preparation_test.py`            | Exact header-path/option membership in recorded compiler arguments failed.                                                                     |
| `io_runtime_test.py`, `preparation_support_test.py` | GCC runtime-archiver discovery failed with `L1C-2154`.                                                                                         |
| `preparation_identity_test.py`                      | GCC returned no effective target during dependency-spelling invalidation.                                                                      |
| `runtime_build_config_test.py`                      | Its existing 120-second runtime-build timeout expired.                                                                                         |

The two argument-membership failures are consistent with the observed path-format difference, but were not separately
instrumented. The GCC discovery failures require further isolation; this run does not establish whether Wine, the MSYS2
Python combination, timing, or a compiler-support defect is responsible. No production expectation or timeout was
changed. The aggregate failure prevented the requested trace-smoke target from running; only the independent focused
trace above is claimed. Native L1 validation passed all 82 normal cases and 46 dedicated traces. Broader Wine testing is
substantially slower, and a green native Windows CI run remains necessary for Windows support claims.

## Upstream limitations

The base is the digest-pinned [MSYS2 experimental Docker image][upstream], which supplies patches missing from stock
Wine. The [MSYS2 FAQ][faq] describes the Cygwin/MSYS2 compatibility issue. The image currently disables package
signature verification; this prototype inherits that policy and uses its configured HTTPS package repository. Package
archives are fetched from a rolling repository, whose retention limits can eventually prevent rebuilding an old base.
Installed package versions are recorded in `C:/msys64/etc/dea-wine-packages.txt` in the toolchain image. A
supported/release workflow would need a separately validated package provenance/update policy.

Known upstream output includes a Cygwin `FAST_CWD` warning and X-server shutdown messages. Those messages alone do not
establish failure: check the command's exit status and test results. Passing under Wine does not establish native
Windows filesystem, loader or process parity. Do not weaken production test expectations to make the prototype pass.

[faq]: https://www.msys2.org/docs/faq/#how-can-i-get-msys2-running-under-wine
[upstream]: https://github.com/msys2/msys2-docker
