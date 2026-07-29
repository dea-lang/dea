# L0 Stage 2 Compiler Contract

Version: 2026-07-29

This document covers Stage 2-specific guarantees not part of the shared CLI contract.

Canonical ownership:

- Shared CLI contract (mode flags, options, targets, identity, exit codes): [cli-contract.md](cli-contract.md)
- Architecture and pass flow: [reference/architecture.md](../../reference/architecture.md)
- Diagnostic code assignment and cross-stage parity: [diagnostic-code-policy.md](diagnostic-code-policy.md)

## 1. Scope

Stage 2 is the self-hosted compiler (`compiler/stage2_l0`) that mirrors the Stage 1 pipeline through code generation and
driver execution. This document records the Stage 2-specific parts of the external interface.

## 2. `--version` Provenance Output

Repo-local (`make install-dev-stage2`) and install-prefix (`make install`) Stage 2 artifacts embed build provenance.
When provenance is present, `--version` prints the identity line (optionally suffixed with the release version) followed
by five fields:

```
Dea language / L0 compiler <release-version>
build: <build-id>
build time: <utc-timestamp>
commit: <git-hash>[+dirty]
host: <kernel> <release> <machine>
compiler: <cc-banner>
```

The release version is appended to the identity line when the `DEA_DIST_VERSION` environment variable was set at build
time (CI release and snapshot workflows set this automatically). For local dev builds, the version defaults to
`dev-<short-hash>`. When neither provenance nor a version string is available, `--version` prints only the bare identity
line.

These fields are **informational**; their format is not guaranteed stable for machine parsing.

### 2.1 Field formats

**`build:`** a token identifying the build context.

- Precedence: `DEA_BUILD_ID` environment variable (if set) > GitHub Actions composite id > `<short-hash>-<stamp>` >
  `local-<stamp>`, where `<stamp>` is `YYYYMMDDTHHMMSSz` (UTC).
- GitHub Actions form: `gha-<run_id>.<run_attempt>-<job>-<os>-<arch>`.
- Character set: alphanumeric, `.`, `_`, `-`.

**`build time:`** UTC build timestamp, ISO 8601 with second precision and space separator. Example:
`2026-03-15 09:42:00+00:00`.

**`commit:`** full 40-character git SHA-1 of `HEAD` at build time, suffixed with `+dirty` when the working tree had
uncommitted changes. `unknown` when git is unavailable.

**`host:`** space-separated triplet `<kernel_name> <kernel_release> <machine>` from `uname -s`, `uname -r`, `uname -m`
on POSIX; from Python's `platform` module on Windows. Example: `Darwin 24.6.0 arm64`.

**`compiler:`** first line of `<cc> --version` for the C compiler used to compile the Stage 2 binary. Example:
`Apple clang version 16.0.0 (clang-1600.0.26.3)`.

### 2.2 Fallback behavior

When any of `build`, `build time`, `host`, or `compiler` cannot be determined (value would be `unknown`), the entire
provenance block is suppressed. `--version` prints only the identity line. Raw compiler 2 / compiler 3 binaries produced
by the triple-bootstrap pipeline always use this fallback path.

## 3. Native Build/Run Workspace

Stage 2 `--build` and `--run` implement the shared native temporary-workspace contract in
[docs/specs/compiler/cli-contract.md](../../../../docs/specs/compiler/cli-contract.md#6-native-buildrun-temporary-workspace).
Each command creates exactly one private workspace after source and entry-point validation, passes it through the native
compile path, retains it through child execution for `--run`, and cleans it from one command-owned epilogue.

The Stage 2 binding has these concrete properties:

- `compiler_filesystem.l0` owns temporary-parent selection, canonical trust validation, exclusive reservation,
  registered-child cleanup, and result precedence. Its raw filesystem ABI is compiler-private and implemented by
  `support/compiler_filesystem.c`; it is not a runtime or standard-library API.
- Parent selection uses `TMPDIR`, `TEMP`, `TMP`, `/tmp`, then `.`. Nonexistent and non-directory candidates fall
  through, but a filesystem inspection error is fatal. Canonical resolution or trust failure for the first existing
  directory also reports `L0C-9513` rather than selecting a later candidate.
- Actual POSIX hosts validate the canonical parent chain and request mode `0700`; actual MinGW hosts retain the
  trusted-parent ACL assumption. Platform-behavior aliases do not select the trust policy.
- Workspace and fixed-child paths use actual-host separators, so a trailing literal `\` in a POSIX parent name cannot
  place the workspace beside that selected parent.
- Driver-selected generated C, compiler output captures, and the temporary run executable are registered workspace
  children. A caller-selected executable and `--keep-c` output remain at their documented external paths. The driver
  does not change the host compiler's working directory or temporary-directory environment and does not claim ownership
  of auxiliary files independently created by that compiler.
- Cleanup is bounded and no-follow. It removes only registered regular children and then the empty real workspace
  directory. Unexpected or substituted contents cause `L0C-9514`, retain the workspace for inspection, and change
  success to status 1 without replacing an already nonzero primary result.
