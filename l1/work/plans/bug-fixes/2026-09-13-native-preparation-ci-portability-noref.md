# Bug Fix Plan

## Fix native preparation portability and CI failures

- Date: 2026-09-13
- Status: In Progress
- Title: Fix native preparation portability and CI failures
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Subsystem: Native preparation observations and cross-platform test fixtures
- Modules:
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/libraries.h`
  - `l1/compiler/stage1_l0/support/preparation/platform.h`
  - `l1/compiler/stage1_l0/support/preparation/pe_imports.h`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_dependencies_test.c`
  - `l1/compiler/stage1_l0/tests/preparation_libraries_test.c`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_bootstrap_interfaces_test.py`
- Related:
  - [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][economy]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
- Repro: Hosted Unified CI normal-test failures on Linux and Windows.
- Current Windows repro: The hosted Windows normal-test matrix reports compiler-family and archive-tool observation
  failures under the MSYS2 UCRT toolchain.

## Summary

Repair the diagnosed Linux and Windows failures on the current refactor branch, preserving both original comparison
branches. Keep the CLI, native ABI, cache layout, semantic authority and reuse policy unchanged. No new diagnostic codes
or cache migration are planned. Hosted verification is required before closing this work.

## ADR Impact

- Decision: Repair dependency decoding, inspection and test portability within the existing preparation architecture.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: These bounded correctness fixes preserve the existing interfaces, ownership architecture and native reuse
    contract.

## Root Causes

- Ubuntu GCC 13.3 diagnoses the ignored `fread` result; both strict native-library tests fail under `-Werror`. Their
  captured compiler stderr is omitted from the resulting exception text.
- The dependency parser strips ordinary backslashes from compiler output. Windows then resolves damaged drive-relative
  paths against the current directory and cannot authorize persistent reuse.
- Windows tests compare equivalent paths as raw strings, including source paths embedded in token output.
- The ctypes test adapter frees native contexts but leaves Windows DLL references loaded when temporary cleanup runs.
- Hosted follow-up exposed another Windows observation failure: GNU `objdump -p` includes a large unrelated unwind table
  for GCC's `cc1.exe`, exceeding the bounded probe output before implementation-library discovery completes.
- Fresh local validation exposed an SDK-fixture portability issue: Apple tool-dispatch shims can stall when `SDKROOT`
  points at the fixture's copied SDK outside the registered platform tree. Native Xcode `otool` reads the same compiler
  image successfully under that SDK selection.

Both hosted macOS jobs in the initial validation completed with 81 normal tests and 46 default traces passing. The Linux
job reported two failures and the Windows job seven failures before their trace sweeps. The responsible behavior
predates the command-local reuse refactor.

## Approach

1. Check compiler-inspection byte counts and read errors. Recognize a shebang only after reading both bytes. Refuse
   persistent reuse on an unavailable inspection while preserving invocable automatic fresh preparation. Keep strict
   warnings and report the native-test build command, stdout and stderr on failure.
2. Add one static streaming dependency-token helper using the caller's existing buffer. Decode GCC/Clang-produced Make
   quoting: ordinary backslashes, drive/UNC paths, slash runs before whitespace and `#`, `$$`, LF/CRLF continuations and
   trailing backslashes. Keep filesystem resolution, scratch exclusion and dependency recording in the existing layer.
   Preserve size limits, malformed-input diagnostics and refusal/fallback boundaries; do not evaluate Make variables or
   normalize separators in the decoder.
3. Compare all preparation-root assertions as paths. Give equivalent default and explicit bootstrap roots consistent
   spelling so token-output comparisons remain exact.
4. Give `Service` idempotent context/library cleanup, including constructor failures. Free the context, clear cached
   callables and release its Windows library reference once. Reject closed-service calls, retain overlapping services
   and the lock-child protocol, and preserve POSIX library-loading behavior.
5. Read normal Windows PE import names directly with bounded file reads instead of dumping unrelated native image
   tables. Preserve the existing DLL lookup, recursive observation and content identity rules, without increasing the
   general probe output limit or adding a tool dependency. Exercise the actual private reader with valid PE32/PE32+
   fixtures, large unrelated sections and malformed image boundaries, and restore native Windows DLL-edit invalidation.
6. During the macOS SDK-metadata fixture, put the explicitly selected compiler's native tool directory first on the
   temporary `PATH`. Keep direct and response-file SDK selection, metadata edit/removal/restoration assertions and
   production tool precedence and probe limits unchanged.

## Verification Criteria

- Compile a small native harness from the existing support test. Include the production translation unit to exercise the
  actual static decoder without copied parser logic or exported test APIs. Cover drive/UNC paths, POSIX literal
  backslashes, whitespace and hash escapes, dollars, continuations, trailing backslashes and malformed responses.
- Use real GCC/Clang dependency output and verify that subsequent header edits invalidate native reuse.
- Check Windows DLL deletion after ordinary close, an exception in the context and constructor failure; exercise
  overlapping services, repeated close and rejection of closed-service operations.
- Run both native-service fixtures, all three preparation integrations, bootstrap-interface and stdin-forwarding
  regressions. Require Windows cold preparation and warm `--no-auto-prepare` consumption to succeed.
- Pass the exact strict Ubuntu 24.04/GCC 13.3 native build and exercise available Apple Clang and MacPorts GCC variants.
- Run the L1 `test-all` tier and focused ownership checks because native allocation/lifetime paths change. Require zero
  ARC/memory errors or leaks. Reuse successful results only while their covered inputs remain unchanged.
- Require the hosted Unified CI matrix to pass on the repaired code before closure. Do not replace missing Windows
  execution with a claim based solely on local parser tests.

## Implementation Results

- Compiler inspection checks the byte count, stream error and close result. The shebang check requires two bytes;
  inspection failures decline persistent reuse without suppressing the existing compiler probe or fresh fallback.
- One private streaming token helper reuses the dependency buffer. Filesystem resolution, scratch exclusion and
  dependency recording retain their existing ownership and error paths. The initial repair's production changes affect
  `l1/compiler/stage1_l0/support/preparation/identity.h`: 75 inserted and 40 removed lines, a net increase of 35 lines.
  Quoting follows the [GCC dependency emitter][gcc-deps] and [Clang dependency emitter][clang-deps], including their
  single added escape before `#`.
- The support fixture compiles a C harness containing the production translation unit. Its 21 token cases cover exact
  decoded spellings, and additional checks exercise malformed responses, missing/nonregular dependencies, scratch
  exclusion and native-image inspection failures.
- Real compiler-produced dependencies cover spaces, `#` and `$`; editing the observed header changes only the native
  identity and the next unchanged invocation reuses it. GCC additionally covers literal POSIX backslashes. Apple Clang
  rewrites those backslashes before emitting its dependency response, so that producer cannot authorize reuse for the
  affected names; the adapter retains conservative refusal rather than guessing an alternate path.
- Path assertions use path equality, while the bootstrap fixture retains exact token-output comparisons with matching
  root spelling. Native fixture build failures report the command, stdout and stderr under the existing strict flags.
- The Python service releases its native context before dropping cached functions and its Windows DLL reference.
  Repeated closure, overlapping services, closed calls, body exceptions and constructor exceptions are covered.
- Independent reviews of the final native and Python ownership paths found no remaining actionable issues.
- The Windows follow-up replaces the compiler's inspector-selection query and one `objdump` process per observed image
  with direct normal-import reads. The reader bounds PE sections at 96, imported names at 256 per image and each name at
  4095 bytes; the existing 256-image recursive closure limit remains unchanged. It reads neither unrelated native tables
  nor the entire image into memory. DLL lookup, API-set handling, dependencies and content hashes retain their existing
  rules. This adds 191 production lines and removes 30, a net increase of 161 lines.
- The additional C harness includes the actual private reader on every host, covering PE32/PE32+, absent imports,
  malformed headers/sections/RVAs, truncated files, unterminated names, descriptor/name boundaries and a large unrelated
  unwind table. Its Windows path also exercises the production recursive DLL resolver on its own executable.
- A Windows-native driver fixture imports a private DLL and forwards the original argument tail and standard handles to
  the real compiler. Its identity regression checks DLL observation, a warm memo and invalidation after DLL bytes change
  while the driver and Dea identity stay unchanged.
- The SDK fixture selects native tools from its explicit Apple compiler's toolchain while testing the copied SDK. It
  restores the environment afterward and no longer depends on SDK-sensitive dispatch shims for image inspection.
- Windows compiler probes now pass the selected executable as the process application name, and compiler-reported tool
  paths accept native, MSYS-style and extensionless Windows spellings. The dependency harness covers the archive-tool
  query, a copied executable under a path containing spaces, and Windows path fallback cases.

## Local Validation Record

The following checks validated the initial repair before its publication. Hosted results appear below; the additional
Windows import-reader repair has its own validation record because its native and test inputs changed.

- Ubuntu 24.04 in a disposable Docker image uses GCC 13.3 and Clang 18.1.3. After `make build-stage1 runtime`, running
  `compiler/stage1_l0/scripts/run_tests.py` with `preparation_support_test.py`, `preparation_identity_test.py`,
  `l1c_stage1_preparation_test.py`, `l1c_stage1_managed_preparation_test.py`,
  `l1c_stage1_installed_preparation_test.py`, `l1c_stage1_bootstrap_interfaces_test.py` and `io_runtime_test.py` passes
  all seven cases. This includes the formerly failing strict native build. TinyCC is unavailable in this image.
- The C harness passes strict Apple Clang and MacPorts GCC 15.2 builds. Apple Clang AddressSanitizer and
  UndefinedBehaviorSanitizer report no diagnostics; the macOS `leaks --atExit` check reports zero leaks and zero leaked
  bytes.
- macOS focused support and bootstrap fixtures pass. A deliberately failing native compilation confirms that the
  command, stdout and stderr survive in the failure diagnostic.
- With both `L1_RUNTIME_CC` and `L1_CC` selecting `/opt/local/bin/gcc-mp-15`, isolated invocation of the final native
  fixture helpers passes strict service/harness compilation, service lifetime, storage-root selection, real escaped
  header observation/edit/repeat checks, and actual private runtime compilation/archive/cleanup. The installed MacPorts
  toolchain selects a subordinate assembler wrapper, so persistent locking correctly refuses reuse with existing
  diagnostic 2152. This variant does not provide persistent memo/lock-success coverage; Ubuntu GCC does.
- The macOS `L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=2 make clean test-all` run passes all 81 normal tests, environment
  stackability, all four examples and all 46 default traces. This includes the focused preparation ownership check;
  every ARC/memory check reports zero errors and leaks. Full validation is required because native allocation/lifetime
  paths change. These results apply to the initial repair; the import-reader follow-up requires fresh validation.
- At initial publication, Windows DLL unloading and successful cold/warm consumption still required hosted validation; a
  local Windows executor was unavailable.
- On the current macOS x86_64 host, strict Clang and GCC builds of the dependency harness pass; the sanitized Clang
  harness reports no AddressSanitizer or UndefinedBehaviorSanitizer diagnostics. The full support, identity, managed
  preparation and normal preparation fixtures pass, as does the changed Python syntax check. Hosted Windows cold and
  warm preparation verification remains pending; CI was not run locally.

## Hosted Follow-up

The initial hosted portability-repair validation passes all 81 normal tests, all four examples, environment checks and
all 46 default traces on Linux, macOS ARM64 and macOS Intel, with zero leaks.

Windows passes 75 normal tests and fails six before the trace sweep. All six share the compiler implementation-library
observation failure above; no separate stdin-forwarding failure was found. The bootstrap-interface fixture passes. The
support fixture reaches its persistent-lock check after the native decoder/image-read harness, strict DLL build, root
assertions and every DLL-lifetime/deletion regression have passed. Cold application preparation succeeds in the stdin
and installed-consumer tests; their warm `--no-auto-prepare` operations correctly refuse an ineligible identity. There
are no Windows DLL cleanup permission errors in the completed log.

## Windows Import-Reader Validation

- Both production-reader harnesses compile under strict MinGW GCC in a disposable Ubuntu Docker image and pass under
  64-bit Wine. This includes actual Windows recursive DLL resolution, dependency decoding and compiler-image reads.
- Strict Ubuntu 24.04/GCC 13.3 and Clang 18 builds pass the PE harness. GCC AddressSanitizer, UndefinedBehaviorSanitizer
  and leak detection report no errors. Strict Apple Clang and MacPorts GCC 15.2 builds pass; Apple Clang
  AddressSanitizer and UndefinedBehaviorSanitizer report no errors, and macOS `leaks --atExit` reports zero leaked
  bytes.
- The macOS support integration passes with the additional PE harness.
- A fresh `L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=2 make clean test-all` run completes 80 normal tests successfully and
  exposes the SDK-fixture dispatch timeout. An isolated retry reproduces the same timeout with unchanged production
  limits. Direct native-tool inspection isolates the dispatch problem; after the fixture correction,
  `L1_TEST_JOBS=1 ../.venv/bin/python compiler/stage1_l0/scripts/run_tests.py preparation_identity_test.py` passes the
  complete identity fixture. The other 80 passing tests are retained because their inputs are unchanged, covering all 81
  normal cases on the final implementation, including focused preparation ownership, all three preparation integrations,
  bootstrap-interface, generated-C identity, provider/link selection and stdin-forwarding checks.
- The corrected SDK helper also passes separately with both direct and response-file SDK selection and all metadata
  edit/removal/restoration assertions. Production timeout and output limits are unchanged.
- `make -o build-stage1 test-env check-examples` passes environment stackability and all four examples against the
  already-built compiler.
- Reuse the earlier passing default 46-test trace sweep from `make clean test-all`: the complete preprocessed
  `preparation_support.c` translation unit has identical lexical tokens on Apple and Linux, apart from whitespace in the
  source presentation. `compiler_support.c`, Dea sources, trace-eligible tests, runtime, trace runners/checkers, flags
  and selected toolchains are unchanged. The changed Python fixtures are outside default trace discovery. This unchanged
  trace coverage, the final normal results and fresh focused ownership/native-reader checks satisfy the full local
  validation tier. All ARC/memory checks report zero errors and leaks.
- A temporary harness against the production reader accepts all five compiler images (`gcc`, `cc1`, `cc1plus`,
  `collect2` and `lto1`) from the official [MSYS2 UCRT GCC 16.1.0-5 package][msys-gcc], matching the hosted compiler
  revision. The `cc1` timestamp and seven PE header values match the CI log; its 22 imported DLL names also match in
  order. The package was extracted for inspection only, with no toolchain installation or compiler execution.
- The native Windows forwarder compiles with strict MinGW flags and runs under Wine. Tests cover spaces, embedded
  quotes, repeated and trailing backslashes, inherited stdin, child exit-code propagation and replacement of the
  imported DLL without relinking the driver. Changing the imported function's behavior is observed on the next run.
- Wine provides local WinAPI and PE/DLL execution coverage, not the hosted MSYS2 compiler environment. Full Windows
  identity invalidation, cold preparation and warm `--no-auto-prepare` consumption remain required in a new authorized
  hosted run. The plan stays active until that matrix passes.

## Delivery and Hosted Validation Gate

Commit locally validated fixes with this plan still active and hosted verification explicitly pending. Run staged
whitespace, ADR Impact and root pre-commit checks before committing.

The manual publication gate targets `https://github.com/dea-lang/dea.git`, branch `ci-probe`, through the user's
existing publication workflow. A push there triggers Unified CI and test-artifact uploads. No release tag, release
publication or deployment is part of this cycle. Before any remote write, present the exact action and pending commits
and obtain fresh user confirmation. Do not change upstreams or use an ad hoc refspec to bypass repository push rules.
Workflow dispatches or reruns also require their own applicable approval.

After the authorized publication and hosted matrix succeed, record the results, close this plan, update the roadmap and
make a documentation commit with the required staged checks. Documentation-only closure does not invalidate code tests
when the validated implementation remains identical.

[clang-deps]: https://raw.githubusercontent.com/llvm/llvm-project/main/clang/lib/Basic/MakeSupport.cpp
[economy]: ../refactors/closed/2026-09-12-native-preparation-economy-noref.md
[gcc-deps]: https://raw.githubusercontent.com/gcc-mirror/gcc/master/libcpp/mkdeps.cc
[msys-gcc]: https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-gcc-16.1.0-5-any.pkg.tar.zst
[preparation]: ../../../docs/reference/stdlib-preparation.md
