# ADR-0020: Native Compiler Private Temporary Workspaces

- Decision date: 2026-07-29
- Last edited: 2026-07-29
- Status: Accepted

## Context

The L0 Stage 2 and L1 Stage 1 native build/run drivers previously selected predictable temporary stems, checked derived
paths for absence, and created those paths later. The check and later creation were not one reservation, collision
exhaustion retained an unchecked fallback, and related scratch files were unreserved siblings in a shared temporary
directory. Cleanup consequently had neither an invocation-owned boundary nor a safe way to distinguish expected
artifacts from unexpected contents.

The native drivers must preserve current temporary-parent precedence and host-tool path behavior while removing that
race. They also need a result-bearing cleanup contract that does not hide a compiler, launch, or child-program failure.
The design applies to L0 Stage 2 and L1 Stage 1 `--build` and `--run`; the Python L0 Stage 1 compiler and L1's
output-local compile-only and standalone-link transactions have separate lifecycle boundaries.

## Decision

Each native `--build` or `--run` command owns exactly one private temporary workspace for the complete operation. The
command creates it after CLI, source, and entry-point validation, passes it to subordinate compile and link helpers,
keeps it alive through child execution for `--run`, and releases it from one command epilogue. A subordinate helper does
not create or clean an independent build/run workspace.

Temporary-parent selection preserves this precedence: `TMPDIR`, `TEMP`, `TMP`, `/tmp`, then `.`. An absent, nonexistent,
or non-directory candidate falls through. A filesystem inspection error is fatal. The first existing directory commits
the selection: canonical resolution or trust-validation failure is fatal and does not fall through to a later candidate.
Workspace reservation uses the selected parent's canonical path, exclusive directory creation, and bounded collision
retries with no unchecked fallback. Workspace and fixed-child path construction follows actual-host separator semantics,
so a trailing `\` in a POSIX parent name remains a literal filename byte rather than moving allocation to a sibling.

Trust policy follows the actual compiled host rather than a language target-platform alias. On POSIX, every directory
from the filesystem root through the selected parent must be owned by the effective user or root, and every group- or
other-writable component must have the sticky bit. The private workspace requests mode `0700`. On the supported MinGW
host, the compiler uses the native directory path and retains the trusted-ACL assumption for the selected parent.

The containment guarantee covers paths selected or explicitly supplied by the driver, including generated C, compiler
output captures, temporary objects and interfaces, generated wrappers, and temporary run executables. Publicly retained
`--keep-c` files and caller-selected outputs remain at their documented external paths. The driver does not change the
host compiler's current directory, rewrite its temporary-directory environment, normalize arbitrary path-bearing C
options, or claim containment of auxiliary files that the host compiler independently invents.

Cleanup removes only registered regular children without following substitutions, then removes the verified empty
workspace directory. It never recursively removes unexpected contents. Incomplete cleanup reports `L0C-9514` or
`L1C-9514` with the retained workspace path. Temporary-parent inspection, workspace setup, parent-trust validation, and
exclusive-reservation failures report `L0C-9513` or `L1C-9513`. Cleanup failure changes an otherwise successful command
result to status 1, but it preserves an existing compile or launch failure and a nonzero child-program status. An
already produced retained output remains available.

Each native compiler exposes this policy through a compiler-private `compiler_filesystem.l0` module. Its C support ABI
provides policy-free raw filesystem primitives for canonical parent resolution and trust validation, actual-host child
path construction, exclusive directory creation, no-follow classification, regular-file removal, and empty-directory
removal. Workspace naming, collision retries, child registration, diagnostics, cleanup ordering, and result precedence
stay in Dea. Each operation's owner decides which artifacts to register and which outputs are retained.

L1 compile-only remains on the same-parent staging, sequential publication, endpoint rollback, and recovery boundary
defined by [ADR-0022](../../l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md). It is not routed
through the native build/run workspace.

## Rationale

- One command-owned workspace removes check-then-use stems and gives build, optional execution, and cleanup one explicit
  lifetime.
- Committing to the first existing temporary-parent candidate preserves environment compatibility without hiding an
  unsafe configured directory behind a later fallback.
- Canonical parent validation and exclusive private-directory creation provide a portable safety improvement while
  keeping actual-host filesystem policy separate from target-behavior aliases.
- Limiting containment to driver-controlled paths is enforceable without changing relative include paths, response
  files, raw host options, or other established host-tool behavior.
- Registered-child, no-follow cleanup bounds what the compiler may delete and retains unexpected state for inspection.
- Preserving an earlier nonzero result keeps the primary failure meaningful, while making cleanup failure result-bearing
  on otherwise successful operations.
- A compiler-private Dea abstraction keeps lifecycle policy testable and shared across compiler operations without
  promoting it to the language runtime or standard library or embedding policy in the C support ABI.

## Consequences

- L0 Stage 2 and L1 Stage 1 native build/run scratch paths are children of an atomically reserved invocation directory
  unless an option explicitly selects a retained external output.
- Workspace creation can now fail before host compilation when the first existing temporary parent cannot be resolved or
  does not satisfy the actual host's trust policy.
- Unknown or substituted workspace contents cause retention and a cleanup diagnostic rather than recursive deletion.
- `L0C-9513` / `L1C-9513` identify temporary-parent inspection, setup, trust, and reservation failures; `L0C-9514` /
  `L1C-9514` identify retained cleanup failures. `L0C-9511` / `L1C-9511` remain reserved for actual output-file write
  failures.
- A successfully built caller-selected executable or retained generated-C file can coexist with a final status 1 when
  workspace cleanup fails.
- The guarantee does not defend against another process with the same account or stronger authority, hostile mounts,
  unusual ACL grants, or independently created host-compiler artifacts.
- Future L1 multi-translation-unit build/run orchestration uses the same workspace abstraction but remains responsible
  for registering its own intermediate artifacts and selecting retained outputs.
- L1 compile-only and standalone link keep their output-local transaction boundaries and do not acquire this global
  build/run workspace lifecycle.

## Related Plans

- [work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md](../../work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md):
  introduced and implemented the shared native build/run workspace safety contract

## Current Docs

- [docs/specs/compiler/cli-contract.md](../specs/compiler/cli-contract.md): shared native build/run workspace lifecycle,
  containment, diagnostics, and result precedence
- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): authoritative paired
  workspace diagnostic codes
- [l0/docs/reference/architecture.md](../../l0/docs/reference/architecture.md): L0 Stage 2 driver and compiler-private
  filesystem architecture
- [l0/docs/specs/compiler/cli-contract.md](../../l0/docs/specs/compiler/cli-contract.md): L0 Stage 2 CLI effects and
  exit behavior
- [l0/docs/specs/compiler/stage2-contract.md](../../l0/docs/specs/compiler/stage2-contract.md): L0 Stage 2 workspace
  ownership and cleanup contract
- [l1/docs/reference/architecture.md](../../l1/docs/reference/architecture.md): L1 Stage 1 native workspace and
  filesystem-boundary architecture
