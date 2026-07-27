# ADR-0023: Toolchain Installation and Distribution Layout

- Decision date: 2026-03-10
- Last edited: 2026-07-27
- Status: Accepted

## Context

L0 has three different operating contexts: a source checkout used for bootstrap development, a selected repo-local
compiler used by contributors, and a compiler installed or extracted for use without the repository. Treating all three
as one checkout-relative layout would make installed compilers depend on source-tree paths. Giving installation and
distribution different layouts would create two relocatability contracts.

The Stage 1 Python compiler remains the bootstrap oracle, but shipping it alongside the self-hosted compiler would make
the user toolchain depend on the bootstrap implementation.

## Decision

The L0 toolchain uses these layout rules:

01. Repo-local stage selection is explicit. Developer targets install stage-specific launchers below the selected
    `DEA_BUILD_DIR`, and only `use-dev-stage1` or `use-dev-stage2` changes the `l0c` alias.
02. Repo-local launchers and activation scripts derive the source checkout and shared assets relative to their own
    location. They remain checkout-bound by design.
03. `make PREFIX=<path> install` creates a self-contained, relocatable prefix. It installs the self-hosted Stage 2
    compiler, the selected `l0c` entrypoint, shared stdlib/runtime assets, activation helpers, and version/provenance
    metadata. It does not install Stage 1.
04. Installed launchers and activation scripts derive `L0_HOME` and shared paths from the prefix. They must work after
    the source repository is moved or removed and must not require ambient `L0_HOME` configuration.
05. `make dist` packages the same installed-prefix contract beneath one `dea-l0/` root rather than defining a second
    runtime layout.
06. POSIX hosts use shell launchers, activation scripts, and `.tar.gz` archives. Windows includes native `.cmd`
    launchers and activation plus a `.zip` archive, while retaining the MSYS2 shell path.
07. A local distribution archive unpacks to a `dea-l0/` root. Its basename is
    `dea-l0-lang_<os>-<arch>_<YYYYMMDD-HHMMSS>`, using the recorded host and UTC build time.
08. The distribution contains a `VERSION` metadata file recording its L0 identity, version, build, source revision,
    host, architecture, license, and canonical source location. Release and snapshot workflows supply their release
    identity to this metadata.
09. Distributions bundle user-facing READMEs, examples, and stable user/reference documentation. They omit work plans,
    proposals, internal specifications, attic material, and contributor-only documentation.
10. Internal self-hosting during installation ignores inherited prefix-specific `L0_SYSTEM`, `L0_RUNTIME_INCLUDE`, and
    `L0_RUNTIME_LIB` values so the build cannot accidentally consume assets from a different installation.

## Rationale

- Explicit repo-local selection keeps bootstrap/developer state visible and avoids install targets unexpectedly changing
  the active compiler.
- A single relocatable prefix contract minimizes drift between installed and archived toolchains.
- Shipping only the self-hosted Stage 2 compiler makes Stage 1 a build oracle rather than a user dependency.
- Relative launcher and asset discovery lets an installed or extracted tree move as one unit.
- Host-native launch and archive forms make the same logical toolchain usable from documented POSIX, MSYS2, and
  `cmd.exe` workflows.
- A predictable root and filename make local archives identifiable without opening them, while `VERSION` carries richer
  machine-readable provenance after extraction.
- Bundling stable user material makes the toolchain usable offline without shipping internal lifecycle history.
- Scrubbing inherited roots makes installation reproducible even when the caller has another toolchain activated.

## Consequences

- Installation always requires an explicit `PREFIX`; there is no implicit system destination.
- The installed and distribution trees carry all shared stdlib/runtime inputs needed by Stage 2.
- Packaging tests must unpack the archive away from the repository and compile a program through the extracted launcher.
- Changes to installed paths, launcher derivation, or required shared assets affect both `install` and `dist`.
- Stage 1 remains available in the checkout and repo-local developer workflow but is absent from release archives.
- Windows generation and tests maintain both MSYS2/POSIX and native `.cmd` entrypoints.
- Packaging tests validate the distribution basename, `VERSION` fields, bundled public material, and exclusions.

## Related Plans

- [l0/work/plans/tools/closed/2026-03-09-stage2-bootstrap-compiler-artifact-noref.md](../../work/plans/tools/closed/2026-03-09-stage2-bootstrap-compiler-artifact-noref.md):
  defined explicit repo-local stage selection and the relocatable Stage 2 install prefix
- [l0/work/plans/tools/closed/2026-03-11-windows-build-support.md](../../work/plans/tools/closed/2026-03-11-windows-build-support.md):
  introduced Windows-native launcher forms
- [l0/work/plans/tools/closed/2026-03-13-windows-dev-install-and-prefix-workflow.md](../../work/plans/tools/closed/2026-03-13-windows-dev-install-and-prefix-workflow.md):
  aligned repo-local and prefix activation with native Windows shells
- [l0/work/plans/tools/closed/2026-03-15-stage2-dist-target.md](../../work/plans/tools/closed/2026-03-15-stage2-dist-target.md):
  made distribution archives reuse the relocatable install layout
- [l0/work/plans/tools/closed/2026-03-16-github-release-workflow-noref.md](../../work/plans/tools/closed/2026-03-16-github-release-workflow-noref.md):
  added versioned, platform-native release archives and bundled user material
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the toolchain layout contract into this ADR

## Current Docs

- [l0/docs/specs/compiler/stage2-contract.md](../specs/compiler/stage2-contract.md): installed Stage 2 identity and
  provenance
- [l0/docs/reference/architecture.md](../reference/architecture.md): repo-local, install-prefix, and distribution
  architecture
- [l0/docs/user/README.md](../user/README.md): packaged toolchain quick start
- [l0/docs/user/README-WINDOWS.md](../user/README-WINDOWS.md): Windows launch and activation forms
