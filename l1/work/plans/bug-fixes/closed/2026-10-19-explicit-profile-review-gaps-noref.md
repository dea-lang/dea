# Bug Fix Plan

## Explicit profile review conformance

- Date: 2026-10-19
- Status: Completed
- Title: Resolve explicit profile conformance and correctness findings from independent review
- Kind: Bug Fix
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Severity: Medium
- Subsystem: Explicit profile native option policy and artifact consumption
- Modules: `l1/compiler/support/preparation/profile.h`
- Test modules: `l1/compiler/tests/preparation_profile_test.py`, `l1/compiler/tests/l1c_profile_variants_test.py`,
  `l1/compiler/tests/l1c_installed_preparation_test.py`, `l1/compiler/tests/l1c_profile_test.py`,
  `l1/compiler/tests/l1c_managed_preparation_test.py`
- Related:
  - [l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md][feature-plan]
  - [l1/docs/reference/explicit-profiles.md][profiles]
- Repro: Pass a response-file operand through a paired native option such as `-D @macro.rsp` during profile creation.

## Summary

Independent review compared the implementation with the original feature scope, published artifact contract, and direct
callers and callees. Paired operands bypassed the response-file refusal, and path normalization could exceed the
argument bound and publish an artifact rejected by its own reader. Windows validation exposed a COM header macro
collision in the native service and extensionless executable outputs in the composition fixture. The corrections enforce
the existing caller-owned stability contract and restore native build and fixture portability.

## ADR Impact

- Decision: Preserve the established explicit profile authority and native configuration boundary.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0044-explicit-profile-artifact-authority.md`
  - Rationale: The fixes enforce the existing refusal of ambiguous configuration and preserve exact read-only selection;
    they introduce no new artifact authority or compatibility promise.

## Findings and corrections

- Every original argv word is checked before paired-option parsing. Creation and manifest loading reject response words
  supplied to definitions, target settings, and path options; literal macro values such as `PROFILE_VALUE=@literal`
  remain valid. Rejection occurs before native probes, cache access, or staging.
- The 32768-byte bound also applies after normalization. Relative-to-absolute expansion and joined
  `--gcc-toolchain=PATH` formatting can no longer produce an unreadable artifact. Regression budgets count UTF-8 bytes.
- Windows UCRT64 GCC 16.2.0 could not compile the native service because the COM `interface` macro expanded a local
  identifier to `struct`. Rename the identifier to `interface_path`. The profile suite now compiles the complete native
  service with `-Dinterface=struct` on every host and exercises the existing artifact checks through that library.
- The composition fixture requested extensionless executable outputs on Windows, where MinGW produces `.exe` files.
  Select `.exe` names for managed, manual-link, direct-build, and failure-only executable destinations on Windows.
  Derive retained-C roots from the complete selected output filename, preserving the exact `OUTPUT.dea-c` contract.
- The reference now states that compile-only requires complete inventory while skipping hashes for unused native
  objects. The installed-input fixture additionally creates a profile with read-only source/interface/header roots,
  moves it, deletes those roots, and consumes it with poisoned ambient settings.
- Independent review found no further scoped frontend/provider, lifecycle, runtime, hidden preparation, final-link,
  storage ownership, cleanup, or contract issue. Existing diagnostics suffice; no diagnostic code was added or
  reassigned.

## Windows test portability audit

Reviewed the complete composition, variants, installed-input and native schema suites, their direct fixture helpers, and
the explicit-profile CLI/help and preparation-ownership cases. The audit covered executable and retained-C naming,
native versus canonical manifest paths, spaces and mixed separators, DLL unloading, subprocess transport and text
decoding, newline handling, readonly attributes, cleanup, and guarded POSIX shell/symlink fixtures.

- Exercise readonly payload files and installed input files on Windows. POSIX also protects directories; Windows file
  attributes do not establish directory write protection. Restore original modes on failure, including through an
  `ExitStack` in the composition case.
- Verify installed inputs and moved explicit profiles with byte/size/timestamp snapshots. The composition and variants
  cases retain their existing immutable-payload checks.
- Freeze relative native option paths from a temporary root containing spaces, then consume the moved profile from a
  different cwd. The raw C-options parser remains whitespace-delimited; the fixture does not assume a quoting grammar.
- Read and write profile text explicitly as UTF-8 and decode compiler diagnostics with UTF-8 replacement handling,
  matching the existing compile-only helper. This avoids legacy Windows locale decoding failures for non-ASCII paths.
- The native schema/DLL, canonical manifest, CLI/help, and ownership cases required no additional corrections.

## Validation scope

All four profile suites and the managed integration case passed on macOS Intel with Apple Clang 17.0.0
(`clang-1700.6.4.2`). From `l1/`, set `L1_BOOTSTRAP_L0C` to the explicit L0 bootstrap and `L0_CC`, `L1_CC`, and
`L1_RUNTIME_CC` to `/usr/bin/clang`:

```sh
make -o venv -o build test-compiler TESTS='l1c_profile_test l1c_profile_variants_test l1c_managed_preparation_test'
make -o venv -o build test-compiler TESTS='l1c_installed_preparation_test'
```

The native profile suite passed via `../../../.venv/bin/python preparation_profile_test.py` from `l1/compiler/tests/`
with the same compiler settings. It compiles complete native support with strict C warnings and `-Dinterface=struct`. It
also passed in the network-disabled local `l1-test` image using `L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc` and
`python3 compiler/tests/preparation_profile_test.py` from `l1/`, with Debian GCC 12.2.0. The variants case additionally
exercised native TinyCC 0.9.28rc.

The build and six-case profile/preparation/CLI normal gate also passed with Apple Clang. The focused preparation trace
passed with zero leaked object or string pointers:

```sh
make -o venv build
make -o venv -o build test-compiler TESTS='preparation_test cli_args_test l1c_profile_test l1c_profile_variants_test preparation_profile_test l1c_installed_preparation_test'
make -o venv -o build test-compiler-trace TESTS='preparation_test'
```

That trace covers the native option failure paths before the Windows identifier rename and Python fixture adjustments;
those later changes preserve compiler control flow and ownership. The final focused cases cover their native build and
fixture effects. Broader feature-implementation validation is not claimed as a rerun of these corrections.

Simulated Windows checks cover drive/UNC paths, spaces, mixed separators, distinct-path negatives, readonly file
selection and restoration after exceptions, COM macro visibility, and Unicode diagnostics under a legacy Windows
encoding. Directory write protection remains POSIX-specific. These probes do not establish native Windows execution;
validation of the complete correction on Windows and macOS ARM remains pending.

[feature-plan]: ../../features/closed/2026-09-30-explicit-profile-artifacts-noref.md
[profiles]: ../../../../docs/reference/explicit-profiles.md
