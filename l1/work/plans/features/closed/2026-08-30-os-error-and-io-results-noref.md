# Feature Plan

## Add a shared OS error and I/O result model

- Date: 2026-10-21
- Last edited: 2026-10-21
- Status: Completed
- Title: Add a shared OS error and I/O result model
- Kind: Feature
- Priority: High
- Stdlib Tier: 1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / standard-stream I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/os.l1`
  - `l1/compiler/shared/l1/stdlib/sys/os.l1`
  - `l1/compiler/shared/l1/stdlib/std/io.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
- Test modules:
  - `l1/compiler/tests/os_runtime_test.py`
  - `l1/compiler/tests/fixtures/os_runtime/`
  - `l1/compiler/tests/io_runtime_test.py`
  - `l1/compiler/tests/runtime_symbol_manifest_test.py`
  - `l1/compiler/tests/l1c_child_trace_runner_test.py`
  - `l1/compiler/tests/l1c_managed_preparation_test.py`
- Related:
  - [l1/work/initiatives/0005-filesystem-and-stream-io.md][filesystem-io]
  - [l1/docs/reference/standard-library.md][stdlib]
  - [l1/docs/decisions/0045-direct-os-errors-and-io-results.md][os-results]
- Repro:
  `make -C l1 test-compiler TESTS="os_runtime_test io_runtime_test runtime_symbol_manifest_test l1c_child_trace_runner_test"`

## Summary

Establish the shared OS error and I/O result foundation using standard streams as the first working consumer. New
operations return captured errors directly, portable code branches on normalized categories, and diagnostics retain the
native domain and code. Existing public helpers retain their signatures and behavior.

## Selected Contract

### Error representation

`std.os` defines `ErrorKind`, `ErrorDomain`, and `OsError { kind: ErrorKind, domain: ErrorDomain, native_code: long }`
plus `error_message(error) -> string`. The initial native domains are `Runtime`, `Errno`, and `Win32`; Windows CRT stdio
failures use `Errno`. Signed `long` preserves native Windows codes without narrowing through `int`.

The twenty normalized categories are `Other`, `NotFound`, `PermissionDenied`, `AlreadyExists`, `InvalidInput`,
`InvalidHandle`, `Interrupted`, `WouldBlock`, `BrokenPipe`, `TimedOut`, `Unsupported`, `NotSeekable`, `OutOfMemory`,
`ResourceExhausted`, `IoError`, `IsDirectory`, `NotDirectory`, `DirectoryNotEmpty`, `NoSpace`, and `FileTooLarge`.
Unknown native codes normalize to `Other` while retaining their domain and value. Runtime validation uses `Runtime` /
`InvalidInput` with code zero; a failed host I/O operation without a native code uses `Runtime` / `IoError` with code
zero. Message text is diagnostic and may vary by host and locale; fallback diagnostics include category, domain, and
code.

`sys.os` carries flat runtime records with integer category/domain fields and a `long` native code. Each operation
captures the host code before cleanup, allocation, or diagnostic rendering can replace it. No new error path consults
ambient `std.system::errno()` afterward.

### Results and first consumer

The shared `std.os` result enums are:

| Type          | Variants                                                                                |
| ------------- | --------------------------------------------------------------------------------------- |
| `ReadResult`  | `Read(count: int)`, `Eof`, `ReadTimedOut(error: OsError)`, `ReadFailed(error: OsError)` |
| `WriteResult` | `Written(count: int)`, `WriteTimedOut(error: OsError)`, `WriteFailed(error: OsError)`   |
| `FlushResult` | `Flushed`, `FlushTimedOut(error: OsError)`, `FlushFailed(error: OsError)`               |

`std.io` adds `read_stdin_some_result`, `write_stdout_some_result`, `write_stderr_some_result`, `flush_stdout_result`,
and `flush_stderr_result`. The byte helpers retain the existing `ByteArray*`, `start: int`, `count: int` parameters and
asserted subrange contract. A valid zero request returns zero transfer without host I/O or EOF observation. Positive
partial transfers succeed, including when the same stdio call observes an error after transferring bytes. Interrupted
operations return without an implicit retry. Timeout variants preserve the host error; these helpers do not configure
deadlines or timeout durations.

Writes count bytes accepted by C stdio. Explicit flush reports delayed failures and requests no filesystem durability
guarantee. The first consumer retains the host or application's `SIGPIPE` disposition. Raw negative counts and null
buffers with positive counts return structured runtime validation failures; they do not weaken the public range
assertions. Normal and traced symbol manifests expose the same new runtime functions.

L1 enum constructors share module scope, so distinct constructors such as `ReadFailed` and `WriteFailed` replace the
original illustrative repeated `Failed` names. No nested `Type::Variant` language feature is introduced.

## Implementation and Findings

1. Add normalized/native mappings, captured error transport, and message rendering.
2. Add the shared result enums and additive standard-stream read, write, and flush consumers.
3. Verify real L1 fixtures, runtime mapping/error-injection probes, trace behavior, and symbol parity.
4. Refresh the reference, initiative, and architectural record with the implemented contract and validation evidence.

The shared errors, direct runtime transport, standard-stream consumers, and documentation are complete. Managed
preparation now verifies its complete 25-interface bundled inventory and the 12-module transitive `std.io` closure.
File-opening results remain in the file-handle plan because no `std.file::File` or settled ownership contract exists
yet. Later process, pipe, socket, and resolver work reuses or extends this foundation.

## Diagnostic Planning

No compiler diagnostic codes are introduced or reassigned. Invalid raw runtime arguments and host failures use library
results. Existing asserted public byte-array range behavior remains unchanged.

## Non-Goals

- a generic `Result<T, E>` language feature or exception handling
- changing or removing existing nullable, sentinel, boolean, or void helper APIs
- file handles, dynamic byte buffers, exact/all result helpers, or stream adapters
- process/network APIs, resolver or Winsock native domains, and deadline configuration
- changing process-wide signal disposition or guaranteeing broken-pipe survival
- migrating L0 or L2 stdlib/runtime APIs

## ADR Impact

- Decision: Standardize captured normalized/native errors and concrete results with explicit EOF, timeout, successful
  partial transfers, and additive standard-stream consumers.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0045-direct-os-errors-and-io-results.md`
  - Rationale: The foundation supplies portable branching and native diagnostics without ambient error-state
    interpretation, while leaving endpoint ownership and later consumer APIs independently scoped.

## Verification Criteria

1. POSIX and Windows mappings cover representative categories, aliases, unknown values, and native-code preservation.
2. Messages use captured domain/code data and remain useful without exact platform-message assertions.
3. Read results distinguish data, zero request, EOF, timeout, and failure; partial writes preserve positive counts.
4. Deterministic probes cover interruption without retry, positive-count-plus-error, raw argument validation, missing
   native codes, and delayed flush failure.
5. The real `os_error_main.l1` fixture executes normally and under ARC/memory tracing; inherited `.l0` seed tests remain
   unchanged.
6. Normal and traced manifests match. Focused normal regressions, the `os_error_main` child trace, and L1
   `test-extended` coverage pass. Native and simulated portability coverage is recorded separately with its actual
   platform scope.

## Verification Evidence

Native validation used macOS Intel with `/usr/bin/clang`, Apple Clang 17 (`clang-1700.6.4.2`), selected explicitly for
`L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`. The selected bootstrap was
`/Users/guglielmo/devel/googlielmo/DEA/l0/build/dea/bin/l0c-stage2`. Commands below ran from `l1/`.

- `../.venv/bin/python compiler/tests/os_runtime_test.py`: all four compiled L1 modes (checked, check-basic, unchecked,
  and traced), native C mapping/failure probes, and direct/deferred broken-pipe child probes passed.
- `../.venv/bin/python compiler/scripts/run_tests.py io_runtime_test runtime_symbol_manifest_test l1c_child_trace_runner_test`:
  all three focused regressions passed.
- `../.venv/bin/python compiler/scripts/run_trace_tests.py --children os_error_main`: passed with 32 memory events, 8
  ARC events, and no leaked object or string pointers.
- `test-extended` coverage completed through composed checks: 46 docgen tests and all 86 normal compiler cases passed,
  reusing 85 unchanged passing cases and rerunning
  `../.venv/bin/python compiler/scripts/run_tests.py l1c_managed_preparation_test` after updating its dependency
  expectations.
- `make -o build check-examples test-docker-wine-runner test-tooling test-productization`: passed with 4 examples, 6
  Wine-runner unit tests, 181 tooling tests (1 skip), and 289 productization fixture tests (14 skips). This reuses the
  unchanged build and records the remaining broad gates separately from the normal-case coverage.
- Win32 numeric mappings and diagnostic fallbacks passed simulated checks. Native Linux, macOS ARM, and Windows,
  including Windows message rendering, remain unverified in this local run.

[filesystem-io]: ../../../initiatives/0005-filesystem-and-stream-io.md
[os-results]: ../../../../docs/decisions/0045-direct-os-errors-and-io-results.md
[stdlib]: ../../../../docs/reference/standard-library.md
