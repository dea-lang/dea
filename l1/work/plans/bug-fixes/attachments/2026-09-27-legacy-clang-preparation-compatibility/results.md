# Legacy Clang preparation compatibility validation

- Date: 2026-10-16
- Scope: Clang configuration isolation, selection invalidation, persistent preparation, and supported-host regression
  gates.
- Status: Validation complete.

## Environments

Linux validation uses private writable source copies in disposable containers. The working repository is mounted
read-only; compiler fixtures, caches, scratch, and build products remain inside the containers. The legacy validation
image adds only Debian's Clang 15 packages to a new image derived from the existing Bookworm builder. Retained
investigation images and host compiler installations are unchanged. Tests run with container networking disabled after
dependency installation.

| Lane              | Requested executable | Resolved executable                | Version and package provenance                                              |
| ----------------- | -------------------- | ---------------------------------- | --------------------------------------------------------------------------- |
| Clang 14          | `/usr/bin/clang-14`  | `/usr/lib/llvm-14/bin/clang`       | Debian Clang 14.0.6; `clang-14` `1:14.0.6-12`; Debian 12 Bookworm, x86_64   |
| Clang 15          | `/usr/bin/clang-15`  | `/usr/lib/llvm-15/bin/clang`       | Debian Clang 15.0.6; `clang-15` `1:15.0.6-4+b1`; Debian 12 Bookworm, x86_64 |
| Clang 19 control  | `/usr/bin/clang`     | `/usr/lib/llvm-19/bin/clang`       | Debian Clang 19.1.7; `clang-19` `1:19.1.7-3+b1`; Debian 13 Trixie, x86_64   |
| Linux GCC control | `/usr/bin/gcc`       | `/usr/bin/x86_64-linux-gnu-gcc-12` | Debian GCC 12.2.0; `gcc-12` `12.2.0-14+deb12u1`; Debian 12 Bookworm, x86_64 |
| macOS control     | `/usr/bin/clang`     | `/usr/bin/clang`                   | Apple Clang 17.0.0 (`clang-1700.6.4.2`); x86_64-apple-darwin24.6.0          |

The Bookworm archiver is `/usr/bin/ar`, supplied by binutils `2.40-2`. Linux compiler builds and the exhaustive Linux
gate explicitly set `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` to `/usr/bin/gcc`. Direct checks of the integration-test
compiler selector confirmed that `/usr/bin/clang-14` and `/usr/bin/clang-15` remain the selected paths, without fallback
substitution.

## Driver behavior

Controlled fixtures establish the same legacy behavior in Clang 14 and 15:

- `--no-default-config -print-prog-name=ar` exits 1 and reports the exact unsupported option. It can still print the
  archiver path, so stdout alone does not establish capability.
- Separate `--config /absolute/path/to/empty.cfg` accepts an owned empty regular file, including paths containing
  spaces. Archiver discovery and runtime-style C compilation succeed.
- An explicit configuration with an absolute nested response input exposes its configuration path in `-###` output and
  forwards both detectable application-only macros into the generated-C command.
- A target-prefixed `x86_64-pc-linux-gnu-clang` alias selects its configuration through the supplied user or system
  search directory. An adjacent configuration alone is not selected in these Debian builds. Explicit empty configuration
  suppresses the selected alias configuration and its application-only macro.
- Clang 19 accepts the modern isolation option and remains on that capability path.

The behavioral oracle is compiler output from owned fixtures. No `/dev/null` configuration file or unsupported-syntax
translation is used.

## Acceptance matrix

| Check                                                                                    | Clang 14        | Clang 15        | Clang 19 control           |
| ---------------------------------------------------------------------------------------- | --------------- | --------------- | -------------------------- |
| Dedicated isolation, selection, invalidation, ownership, and detached-constructor matrix | PASS            | PASS            | PASS                       |
| Prewarm, build/run/link, guarded reuse, force, and corruption integration                | PASS            | PASS            | PASS                       |
| Strict persistent-reuse reporter (`--expect available`)                                  | PASS: available | PASS: available | PASS: available            |
| Final-native explicit nested and implicit alias CLI profiles                             | PASS            | PASS            | Legacy-specific acceptance |

The dedicated matrix covers application-only configuration changes, creation/deletion/restoration, user-over-system
shadowing, search overrides, target aliases, explicit nested response input changes, malformed and missing configuration
inputs, and separate scratch directories. It compiles default, traced, unchecked, and basic runtime variants. A managed
snapshot survives destruction of its original preparation context; a detached constructor recreates isolation in fresh
scratch, performs zero discovery probes, and excludes an implicit application configuration that would break runtime
compilation. Controlled native fixtures distinguish unrelated errors, unsupported options, timeouts, unsafe observation,
and safe private fallback, and verify scratch cleanup on success, failed probes, and failed compilation.

The final exact-rejection predicate additionally rejects a diagnostic that merely suggests `--no-default-config` while
reporting a different misspelled option. Dedicated matrices pass with all three Clang versions after this final narrow
predicate change, and the capability-reporter unit suite passes. The exhaustive Linux gate, plain CLI integration lanes,
and Clang 19 persistent reporter retain the immediately preceding implementation snapshot; its only production
difference is that rejection-text predicate. The retained input manifest confirms that the exhaustive gate source stayed
unchanged. A separate final native build supplies the configured-profile CLI probe below.

The rebuilt final native compiler passes strict `--expect available` reporters with both Clang 14 and 15. Final-native
configured CLI probes also pass with both compilers. Each explicit nested configuration and implicit target-alias
configuration publishes a completed profile, then reuses it in two guarded processes with different scratch roots and
zero preparation compilations or commands. Changing only an application macro rejects the old profile with `L1C-2159`;
automatic preparation publishes a second profile, and restoring the original configuration reuses the original profile
without rebuilding. Every scratch root is empty after each command.

Reproducible focused commands, run from `l1/` with each requested compiler selected explicitly:

```sh
L1_CC=/usr/bin/clang-14 L1_RUNTIME_CC=/usr/bin/clang-14 python3 compiler/tests/preparation_clang_compatibility_test.py
L1_CC=/usr/bin/clang-15 L1_RUNTIME_CC=/usr/bin/clang-15 python3 compiler/tests/preparation_clang_compatibility_test.py
L1_CC=/usr/bin/clang-14 L1_RUNTIME_CC=/usr/bin/clang-14 python3 compiler/tests/l1c_preparation_test.py
L1_CC=/usr/bin/clang-14 L1_RUNTIME_CC=/usr/bin/clang-14 python3 compiler/tests/l1c_managed_preparation_test.py
L1_CC=/usr/bin/clang-15 L1_RUNTIME_CC=/usr/bin/clang-15 python3 compiler/tests/l1c_preparation_test.py
L1_CC=/usr/bin/clang-15 L1_RUNTIME_CC=/usr/bin/clang-15 python3 compiler/tests/l1c_managed_preparation_test.py
python3 scripts/check_preparation_reuse.py --c-compiler /usr/bin/clang-14 --expect available --output-dir build/ci/clang14-reuse
python3 scripts/check_preparation_reuse.py --c-compiler /usr/bin/clang-15 --expect available --output-dir build/ci/clang15-reuse
L0_CC=/usr/bin/gcc L1_CC=/usr/bin/gcc L1_RUNTIME_CC=/usr/bin/gcc make test-ci
```

## Warm-resolution work

Every strict reporter requires cold publication, ordinary warm reuse, guarded warm reuse, header-change refusal, and
publication of a new profile after invalidation. Both warm consumers run in separate processes and select the same
completed profile as the cold request.

| Lane           | Warm managed module compilations | Warm preparation build commands | Warm probes | Warm identity content reads | Warm metadata checks |
| -------------- | -------------------------------- | ------------------------------- | ----------- | --------------------------- | -------------------- |
| Clang 14       | 0                                | 0                               | 4           | 0                           | 47                   |
| Clang 15       | 0                                | 0                               | 4           | 0                           | 47                   |
| Clang 19       | 0                                | 0                               | 3           | 0                           | 47                   |
| Apple Clang 17 | 0                                | 0                               | 5           | 0                           | 47                   |

These figures apply to both ordinary and guarded warm consumers with no selected configuration. The first warm request
reads 47 artifact contents to seed artifact-validation evidence; the subsequent guarded request reads zero. Legacy
resolution adds one successful explicit-empty-configuration capability probe to the version, modern-capability, and
original-configuration-selection probes. The modern-capability probe's exit 1 is expected only for its exact unsupported
option diagnostic. No warm request executes a preparation build command.

The explicit nested-response identity fixture separately requires exactly two fresh configuration content reads, at most
six probes, and zero build commands on warm resolution. It preserves the same native key across separate processes and
different scratch roots. Actual configured CLI warm consumers have the same four-probe count: two content reads for an
explicit configuration plus nested response file, or one read for an implicit alias configuration. Both perform zero
preparation compilations and build commands. A separate mutation of the compiler alias directory triggers full discovery
(50 probes) while still reusing the completed profile with zero build work; placing the alias in a stable directory
restores the four-probe warm path. This confirms that the fresh signature supplements existing directory validation.
Counts describe bounded work; concurrently running correctness validation is not a comparative latency benchmark.

## Linux GCC regression validation

The isolated Bookworm `make test-ci` uses explicit `/usr/bin/gcc` selections for `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`,
with two normal-suite jobs and two trace-suite jobs. The source copy remains unchanged throughout this gate, which
completed with exit status 0.

| Linux GCC check                                  | Outcome                                       |
| ------------------------------------------------ | --------------------------------------------- |
| Normal compiler registry including CI-only cases | 88 passed, zero failed                        |
| Documentation generator tests                    | 45 passed, 1 skipped                          |
| Examples                                         | 4 passed                                      |
| Docker Wine runner tests                         | 6 passed                                      |
| Tooling tests                                    | 181 passed, 1 skipped                         |
| Productization fixtures                          | 287 passed, 16 skipped                        |
| Environment/bootstrap integration                | PASS                                          |
| Default trace sweep                              | 47 passed; zero leaked object/string pointers |
| Child trace fixtures                             | 2 passed; zero leaked object/string pointers  |

## Host regression validation

Apple Clang 17 uses explicit `/usr/bin/clang` selections for `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`. The `make test-ci`
compiler sweep reported 87 passing cases and one stable-input refusal in `io_runtime_test.py`: `L1C-2151` named
`compiler/support/preparation/identity.h`, which was being tightened to reject diagnostic suggestions. The unchanged I/O
test then passed with the final source frozen. The broad preparation identity suite and compatibility, construction,
support, ownership, integration, and reporter tests passed. Passing cases were retained; the remaining exhaustive-tier
components were completed separately rather than rerunning them.

| Host check                                                  | Outcome                                                                    |
| ----------------------------------------------------------- | -------------------------------------------------------------------------- |
| Normal compiler registry including CI-only cases            | 87 passed in aggregate; the source-change refusal passed its focused rerun |
| Documentation generator tests                               | 46 passed                                                                  |
| Examples using the final native build                       | 4 passed                                                                   |
| Docker Wine runner tests                                    | 6 passed                                                                   |
| Tooling tests                                               | 181 passed, 1 skipped                                                      |
| Productization fixtures                                     | 289 passed, 14 skipped                                                     |
| Environment/bootstrap integration                           | PASS                                                                       |
| Default trace sweep on the final native build               | 47 passed; zero leaked object/string pointers                              |
| Child trace fixtures on the final native build              | 2 passed; zero leaked object/string pointers                               |
| Strict Apple Clang reuse reporter on the final native build | PASS, `available`; same persistent profile and correct invalidation        |

Reproducible commands, run from `l1/` with the explicit compiler selections above:

```sh
L1_TEST_JOBS=6 L1_TRACE_TEST_JOBS=6 make test-ci
../.venv/bin/python compiler/tests/io_runtime_test.py
make test-docker-wine-runner test-tooling test-productization test-env
L1_BUILD_DIR=build/legacy-final/dea L1_TRACE_TEST_JOBS=6 make check-examples test-compiler-trace test-compiler-trace-children
../.venv/bin/python scripts/check_preparation_reuse.py --build-dir build/legacy-final/dea --c-compiler /usr/bin/clang --expect available --output-dir /tmp/dea-legacy-apple-reuse
```

A repository-local macOS reporter fixture experienced a concurrent `ctime` mutation with unchanged content digest,
device, inode, size, mode, and `mtime`. A retained metadata observer confirmed the change; the responsible process is
unknown. The existing stable-input check correctly refused publication. The OS-temporary-directory control passed
without weakening metadata checks. Native Windows legacy-driver validation was not performed. Synthetic POSIX, drive,
UNC, mixed-separator, space, and quote argument fixtures passed as simulated portability coverage.

The final Apple control used the isolated `build/legacy-final/dea/bin/l1c.native`, rebuilt from the frozen final
compiler sources, with matching headers/interfaces and all three compiler selectors set to `/usr/bin/clang`. The
ordinary reporter completed in 44.902 seconds. Cold preparation compiled 23 modules with 33 build commands.
Separate-process automatic and guarded warm consumers reused the same completed profile with zero module compilations,
zero build commands, five bounded probes, and zero identity content reads; their elapsed times were 1.624 and 1.464
seconds. Automatic warm validation read 47 artifact contents, and guarded warm validation read zero; both checked 47
artifact metadata records. After header invalidation, guarded consumption correctly reported `L1C-2159`, and automatic
preparation rebuilt 23 modules with 33 build commands.

## Evidence retention

The report retains the relevant commands, exact compiler provenance, outcomes, and bounded warm-work accounting. Raw
probe logs and per-process JSON reports are retained in ignored local output under `l1/build/legacy-clang-validation/`.
Compiler binaries and profile fixtures are disposable validation products and are not committed. The task-created
containers and temporary legacy image were removed after evidence export. Historical images and preparation-performance
measurements are unchanged.
