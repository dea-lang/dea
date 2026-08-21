# ADR-0032: Deterministic Compile-Only Staging Paths

- Decision date: 2026-08-21
- Last edited: 2026-08-22
- Status: Accepted

## Context

Compile-only used fixed `staged.c` and `staged.o` names reached through a randomized output-local transaction path.
Those random and caller-selected destination prefixes were passed directly to the host compiler. Toolchains may encode
compiler-visible input paths in object bytes, so identical module compilation to different destinations could produce
different objects even though generated C was identical.

The output-local transaction and endpoint rollback remain required. Deterministic staging must therefore change the host
compiler's view without moving publication into the shared build/run workspace.

## Decision

Compile-only stages C, object, and interface files under the canonical dotted module path inside its existing private
transaction. For example, module `pkg.sub` uses `pkg/sub.c`, `pkg/sub.o`, and `pkg/sub.l1m` below the transaction root.

The host compiler runs with the transaction root as its working directory and receives the module-relative C and object
paths. Random transaction identities and caller-selected destination prefixes are absent from those input/output
arguments. A compiler executable containing a relative directory component and a relative runtime-include path are
resolved against the original invocation directory before the working-directory change. Bare compiler names are frozen
to an absolute result of the invocation-time command search. POSIX retains empty and relative `PATH` components. Windows
retains `PATHEXT` ordering and the implicit-current-directory policy selected by `NoDefaultCurrentDirectoryInExePath`;
explicit empty or relative `PATH` components keep their normal meaning. Failure to resolve reports a compilation failure
before transaction allocation rather than repeating lookup from private staging. When a debug-producing GNU-style option
such as `-g`, `-g3`, or `-ggdb` reaches a compiler identified as Clang or GCC by its configured name or canonical
filesystem target, the driver records the private debug compilation directory as `.`. Conventional target-prefixed,
numeric-version-suffixed, and MinGW `-posix` / `-win32` driver basenames are recognized. Recognized canonical targets
outrank alias spelling; on Darwin, filesystem identity also recognizes the standard `gcc` and `cc` hard links to
`/usr/bin/clang`. Clang receives its delimiter-safe compilation-directory option, while GCC receives a debug-prefix
mapping. On a Darwin host, GCC also forwards a stable compilation directory to Apple's external assembler: otherwise
that assembler expands GCC's relative `.file` entries against the private working directory after the prefix mapping has
run. Actual-host detection comes from the native compiler-support ABI and is not affected by the `L1_PLATFORM`
command-behavior test override. Canonicalization and identity checks are used only for classification; invocation
retains the originally selected executable spelling. Opaque wrappers whose canonical target is not recognizably Clang or
GCC remain outside this mapping guarantee.

The transaction remains a same-parent, same-filesystem publication boundary. Cleanup removes only the known regular
staged files, then their now-empty canonical module directories, then the empty transaction root. Unexpected compiler
side artifacts retain the transaction for inspection. Publication order, selected artifact sets, endpoint rollback,
recovery retention, final-path no-follow validation, and external serialization requirements remain those of ADR-0022.

The guarantee is limited to paths controlled by the driver: random transaction identities and caller-selected
destination prefixes do not enter compiler input/output operands or recognized GCC/Clang debug compilation-directory
metadata. Native object byte identity is not guaranteed because host toolchains can encode timestamps, environment
details, paths supplied through raw options or headers, toolchain configuration, and other data outside the driver's
control. Focused byte comparisons with an available recognized toolchain remain regression evidence for this path
neutrality, not a portable object-format contract. Generated-C byte identity remains exact for the same resolved inputs
and code-generation settings.

## Rationale

- Canonical module-relative arguments make compiler-visible source/object identity independent of transaction and
  publication destinations.
- Reusing the existing sibling transaction preserves same-filesystem endpoint rollback and avoids coupling compile-only
  publication to build/run scratch ownership.
- A driver-controlled path-neutrality boundary is testable without claiming control over opaque native object contents.

## Consequences

- Relative path-bearing raw `L1_CFLAGS` or `--c-options` values are interpreted from the private transaction unless the
  option itself carries an absolute path. The driver normalizes only the known compiler executable and runtime include
  inputs; it does not attempt to parse arbitrary host-specific option grammars.
- Compiler symlink targets can select GCC- or Clang-specific debug options without changing invocation spelling.
  Darwin's standard Clang-backed `gcc` and `cc` hard links are also recognized by identity. Opaque wrappers remain
  unclassified unless their canonical target name identifies one of those compilers.
- Host-generated auxiliary files remain outside the selected artifact set and may intentionally cause bounded cleanup
  retention.
- Diagnostics and verbose command display show stable module-relative C/object paths.
- Future build/run fan-out can call the same module generator without adopting compile-only publication.

## Related Plans

- [l1/work/plans/features/closed/2026-08-21-per-module-generated-c-foundation-noref.md][foundation]
- [l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md][compile-only]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: compile-only staging and toolchain exception contract
- [l1/docs/reference/separate-compilation.md][separate-compilation]: artifact and object-determinism behavior
- [l1/docs/reference/architecture.md][architecture]: compile transaction flow
- [l1/docs/reference/c-backend-design.md][backend]: generated-C and native-artifact boundary

[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[compile-only]: ../../work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[foundation]: ../../work/plans/features/closed/2026-08-21-per-module-generated-c-foundation-noref.md
[separate-compilation]: ../reference/separate-compilation.md
