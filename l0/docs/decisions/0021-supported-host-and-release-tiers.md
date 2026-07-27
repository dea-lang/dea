# ADR-0021: Supported Host, Toolchain, and Release Tiers

- Decision date: 2026-03-16
- Last edited: 2026-07-27
- Status: Accepted

## Context

L0's C backend can work with several host compilers, but a downloadable toolchain needs narrower, testable support
claims. Windows adds a second distinction: MSYS2 environments, Python families, native shells, and dynamically linked
MinGW runtime libraries can produce materially different installation and execution behavior.

Release workflows, CI coverage, user documentation, and archive portability therefore need one tier model rather than
independent lists of environments that happen to work.

## Decision

L0 support and release artifacts follow these tiers:

1. Stable releases provide four compiler archives: Linux x86_64, macOS x86_64, macOS arm64, and Windows x86_64.
2. Linux and macOS release builds use the hosted GCC or Clang toolchain selected by their workflow runners.
3. The automatic Tier 1 Windows build, test, install, snapshot, and release environment is MSYS2 `UCRT64` with MSYS2
   Python and MinGW-w64 GCC or Clang.
4. MSYS2 `MINGW64` is a supported alternate developer environment with manual CI coverage. Native Windows Python remains
   a supported manual validation path for `cmd.exe`-oriented behavior.
5. MSVC-family handling is experimental and is not part of the validated release matrix.
6. Windows install and distribution builds statically link the GCC runtime by default so the compiler does not require
   undeclared MinGW runtime DLLs outside MSYS2. An explicit caller-provided `L0_CFLAGS` value may override that default.
7. A release archive must run after extraction in its documented host environment and must not depend on the source
   checkout.

## Rationale

- Four artifacts cover the principal current desktop/server host and architecture combinations without claiming every C
  toolchain as a release target.
- `UCRT64` aligns the automatic lane with the recommended current MSYS2 environment.
- Keeping `MINGW64` and native Python as explicit manual lanes preserves important path and shell coverage without
  multiplying every automatic job.
- Separating experimental MSVC handling from validated MinGW support keeps the support claim evidence-based.
- Static Windows runtime linkage makes the downloaded compiler usable from normal Windows shells rather than only from
  an MSYS2 environment whose DLLs happen to be on `PATH`.

## Consequences

- Stable and snapshot workflow matrices must retain all four release artifacts unless a later decision changes the
  supported platform set.
- CI logs and documentation distinguish automatic, manual supported, and experimental Windows configurations.
- Windows package examples prefer `UCRT64` and provide corresponding `MINGW64` instructions.
- Distribution tests must detect unexpected non-system DLL dependencies in the default Windows artifact.
- Explicit custom build flags can trade away the default relocatability guarantee and are the caller's responsibility.

## Related Plans

- [l0/work/plans/tools/closed/2026-03-16-github-release-workflow-noref.md](../../work/plans/tools/closed/2026-03-16-github-release-workflow-noref.md):
  established the four-platform release artifact matrix
- [l0/work/plans/bug-fixes/closed/2026-03-30-windows-dist-libwinpthread-dll-dependency-noref.md](../../work/plans/bug-fixes/closed/2026-03-30-windows-dist-libwinpthread-dll-dependency-noref.md):
  made default Windows distributions independent of MinGW runtime DLLs
- [l0/work/plans/tools/closed/2026-03-31-windows-ci-msys2-mingw-python-noref.md](../../work/plans/tools/closed/2026-03-31-windows-ci-msys2-mingw-python-noref.md):
  selected automatic `UCRT64` and manual `MINGW64` and native-Python lanes
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the host, toolchain, and artifact tiers into this ADR

## Current Docs

- [l0/docs/reference/architecture.md](../reference/architecture.md): host and toolchain assumptions
- [l0/docs/project-status.md](../project-status.md): current platform support tiers
- [l0/docs/releases/README.md](../releases/README.md): stable release surface
- [l0/docs/user/README-WINDOWS.md](../user/README-WINDOWS.md): supported Windows environments and toolchains
