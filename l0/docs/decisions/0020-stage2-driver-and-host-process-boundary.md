# ADR-0020: Stage 2 Driver and Host-Process Boundary

- Decision date: 2026-03-10
- Last edited: 2026-07-27
- Status: Accepted

## Context

Stage 2 initially stopped after analysis and C generation. Adding `--build` and `--run` required compiler discovery,
output policy, C-option handling, host command rendering, status interpretation, and temporary artifact management.
Putting those responsibilities into compiler phases or duplicating them across command modes would couple semantic work
to shell behavior and make Stage 1 parity harder to preserve.

The available `std.system.system()` API is deliberately small. This milestone needed a portable compiler-driver
boundary, not a competing general subprocess API.

## Decision

Stage 2 divides build and host-process responsibilities as follows:

1. The `l0c` facade owns CLI parsing, shared target normalization, and mode dispatch.
2. `build_driver.l0` owns `--build` and `--run` orchestration: semantic analysis, entry-point validation, generated-C
   production, output and retained-C paths, compiler discovery, effective C options, runtime paths, host invocation,
   executable launch, and temporary artifact cleanup.
3. Build and run reuse one build path. Compiler phases do not invoke host tools directly.
4. Host programs are invoked through `std.system.system()` and the runtime normalizes C `system()` results. Ordinary
   child exit codes cross the boundary unchanged; POSIX signal termination becomes `128 + signal`.
5. Platform-specific executable naming, compiler probes, argument quoting, command rendering, and runtime-library syntax
   are confined to the driver/host boundary.
6. Host compiler output may be captured and replayed for compiler diagnostics, while a program launched by `--run`
   inherits its normal standard streams.
7. This boundary does not introduce a second or general subprocess surface. Rich process handles, pipes, and explicit
   stream control require a separate design.

## Rationale

- A thin facade keeps public CLI normalization centralized and lets build/run share one orchestration implementation.
- Isolating shell and toolchain behavior prevents platform-specific command forms from leaking into parsing, semantic
  analysis, or C emission.
- Runtime status normalization gives language code a portable child-result contract instead of exposing encoded C
  wait-status words.
- Reusing `std.system` meets the bootstrap need without prematurely defining a public process abstraction.
- A dedicated driver boundary is independently testable for quoting, compiler selection, paths, and status behavior.

## Consequences

- CLI parity changes affecting build/run land at the facade or `build_driver`, not in arbitrary compiler passes.
- Each supported host may render different command lines while preserving the same observable CLI contract.
- Runtime adapters must preserve normalized status semantics across hosts.
- New modes that compile or launch artifacts should reuse the driver boundary rather than reimplementing discovery and
  command normalization.
- The current system-call boundary cannot provide structured stdout/stderr pipes or long-lived process handles.

## Related Plans

- [l0/work/plans/features/closed/2026-03-10-stage2-build-run-driver-milestone.md](../../work/plans/features/closed/2026-03-10-stage2-build-run-driver-milestone.md):
  established the Stage 2 build/run orchestration and normalized `std.system` boundary
- [l0/work/plans/tools/closed/2026-03-11-windows-build-support.md](../../work/plans/tools/closed/2026-03-11-windows-build-support.md):
  confined Windows command forms, executable naming, and tool discovery to the host boundary
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the Stage 2 driver and host-process boundary into this ADR

## Current Docs

- [l0/docs/reference/architecture.md](../reference/architecture.md): Stage 2 pipeline and `build_driver` role
- [l0/docs/specs/compiler/cli-contract.md](../specs/compiler/cli-contract.md): L0 command modes, options, and exit codes
- [docs/decisions/0003-shared-cli-contract.md](../../../docs/decisions/0003-shared-cli-contract.md): Dea-wide CLI
  ownership and normalization
- [l0/docs/specs/compiler/stage2-contract.md](../specs/compiler/stage2-contract.md): self-hosted compiler contract
