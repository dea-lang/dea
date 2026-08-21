# ADR-0029: Output-Local Standalone Link Transaction

- Decision date: 2026-07-27
- Last edited: 2026-08-21
- Status: Accepted

## Context

Standalone linking needs a generated wrapper C file, its relocatable object, and captured host-tool output. The legacy
global temporary-stem helper does not provide an atomically reserved workspace and is not an acceptable owner for these
artifacts. Standalone link already has a caller-selected executable path whose existing parent provides a natural local
workspace boundary.

The common link executor will also be reused by multi-CU build/run orchestration, whose invocation workspace has
different ownership and cleanup rules. Workspace allocation therefore cannot be hidden inside that executor.

## Decision

Standalone `l1c --link` validates every object, the complete Dea graph and entry, the output destination, the selected
host compiler, and the runtime include and link inputs before allocating scratch state.

While Windows host commands pass through `cmd.exe`, standalone mode also validates the exact compiler, output, runtime,
and parsed wrapper-option words before allocation. Percent, exclamation, literal quote, carriage-return, and line-feed
bytes are rejected. The common executor rechecks every final command word and stdout/stderr path at invocation. Rejected
control bytes are rendered as hexadecimal escapes rather than copied into diagnostic lines.

It then exclusively creates a sibling directory named `.l1c-link-<pid>-<seconds>-<nanoseconds>-<attempt>` beneath the
existing output parent, trying attempts 0 through 99 without an unchecked fallback. POSIX creation requests mode `0700`;
MinGW inherits access control from the trusted parent. The transaction owns fixed `wrapper.c`, `wrapper.o`,
compiler/link stdout, and compiler/link stderr paths. Caller native operands remain outside the transaction and are
passed to the host through their original rendered paths after sibling-interface and graph validation.

The common link executor receives those paths explicitly. It neither allocates nor cleans the enclosing workspace, so a
later build/run caller can supply paths under its own invocation transaction.

Standalone cleanup performs no recursive deletion. It removes only known regular children without following aliases,
then removes the verified empty real directory. Unexpected or substituted content retains the bounded transaction for
inspection. Cleanup failure is result-bearing and makes the command fail even if the executable was successfully linked.

The output parent may contain caller-trusted directory aliases, but the final executable path itself must be absent or a
no-follow regular file. An existing output that identifies the same filesystem object as any caller input or selected
runtime input is rejected before allocation. The host linker writes directly to the output; other final executable
replacement and partial-failure behavior are deliberately outside this transaction and have no rollback protocol.

## Rationale

Exclusive creation prevents concurrent standalone links from sharing wrapper state. Locating scratch beside the output
avoids the unsafe global temporary-root boundary while keeping all owned paths explicit. Bounded no-follow cleanup makes
the deletion authority auditable and prevents unexpected contents from broadening it. Separating executor and workspace
ownership also permits safe reuse by the planned multi-CU build/run transaction.

## Consequences

- Invalid link sets and missing toolchain/runtime inputs do not create `.l1c-link-*` state.
- Caller-owned original objects are never children of the transaction, never cleanup targets, and never snapshotted.
- Wrapper compile and final-link output are captured and replayed while their files remain transaction-owned.
- A retained transaction is reported by exact path when bounded cleanup cannot prove it safe to remove.
- A successful executable can remain visible when cleanup fails and the command returns nonzero.
- Standalone link remains independent of the command-owned native build/run workspace defined by
  [ADR-0020][native-workspace-adr] and does not claim transactional executable publication.
- Until native Windows host tools use direct process spawning, command words and redirection paths containing `%`, `!`,
  literal `"`, carriage return, or line feed are rejected; standalone values fail before transaction allocation.

## Related Plans

- [l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md][interface-authority]
- [l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md][link-set]
- [work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md][native-workspace]
- [l1/work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md][link-hardening]

## Current Docs

- [l1/docs/reference/separate-compilation.md][separate-compilation]: standalone workspace behavior
- [l1/docs/reference/architecture.md][architecture]: link executor and caller-owned scratch boundary
- [docs/specs/compiler/cli-contract.md][cli]: output requirements

[architecture]: ../reference/architecture.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[interface-authority]: ../../work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md
[link-hardening]: ../../work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md
[link-set]: ../../work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[native-workspace]: ../../../work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
[native-workspace-adr]: ../../../docs/decisions/0020-native-compiler-private-temporary-workspaces.md
[separate-compilation]: ../reference/separate-compilation.md
