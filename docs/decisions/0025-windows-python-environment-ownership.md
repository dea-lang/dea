# ADR-0025: Windows Python Environment Ownership

- Decision date: 2026-10-26
- Last edited: 2026-10-26
- Status: Accepted

## Context

Windows repository tooling needs a deliberate interpreter choice while retaining coverage of MSYS2 Python's path and
subprocess behavior. Selecting Python from an MSYS2 shell's PATH can choose a different family from the interpreter uv
uses for the shared environment. Native and MSYS2 CPython also use different environment layouts and binary extension
ABIs. A second dependency list or lockfile would create independent authorities for the same suite.

## Decision

- Use native Windows CPython for the normal shared `.venv`, builds, documentation, tests, and artifact tooling. Continue
  using MSYS2 for the Windows C toolchain and shell. Forward Make's Windows `PYTHON` selection to uv explicitly and
  select `.venv/Scripts/python.exe`; reject a shared MSYS2 environment. POSIX behavior remains unchanged.
- In Windows jobs validating L0, run one additional complete Stage 1 pytest pass through an explicitly selected UCRT64
  Python interpreter. Keep the collection, test data, expectations, pytest options, and xdist parallelism shared with
  the native pass. Do not multiply Stage 2, L1/L2, or dedicated trace suites for interpreter coverage.
- Confine MSYS2 dependency compatibility to provisioning. Create a separate temporary virtual environment outside the
  checkout, export pip-compatible requirements from the existing `uv.lock`, and install them with that environment's own
  pip. Keep `pyproject.toml` and `uv.lock` authoritative; neither generated requirements nor another lockfile belongs in
  the repository. Test execution does not export or install dependencies.
- Invoke MSYS2 Python directly. Keep uv attached to the native project environment and never use uv's `--python` to
  manage MSYS2 Python. Validate interpreter families and temporary-environment ownership before the second pass.
- Use native Python explicitly on fresh artifact-verification runners without requiring a checkout. Retain the manual
  MINGW64 C-toolchain lane, using native tooling plus UCRT64 Stage 1 coverage; the old native-Python lane is an alias.

## Rationale

Native CPython and uv provide the normal Windows tooling environment and compatible package wheels. Separate MSYS2
coverage still exercises the complete Stage 1 compiler contract under its alternate Python implementation. Setup-time
lock export accommodates the alternate ABI without changing dependency ownership or making tests install packages.
Explicit interpreter paths and family checks prevent ambient PATH or environment activation from exchanging the roles.

## Consequences

Windows L0 CI pays for a second full Stage 1 run and its separate setup. Both durations are recorded independently;
actual Windows timing requires Windows execution. Native compiler and trace coverage remains unchanged. Existing MSYS2
shared environments require deliberate recreation as native environments. Native and MSYS2 Python versions may differ
while both satisfy the workspace minimum; package markers are evaluated by each installer from the same lock export.

## Related Plans

- [work/plans/tools/closed/2026-10-26-shared-windows-python-environments-noref.md](../../work/plans/tools/closed/2026-10-26-shared-windows-python-environments-noref.md)

## Current Docs

- [MONOREPO.md](../../MONOREPO.md#windows-python-environments)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [l0/README-WINDOWS.md](../../l0/README-WINDOWS.md)
- [l0/docs/decisions/0021-supported-host-and-release-tiers.md](../../l0/docs/decisions/0021-supported-host-and-release-tiers.md)
