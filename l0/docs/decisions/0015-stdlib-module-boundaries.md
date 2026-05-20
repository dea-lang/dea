# ADR-0015: Stdlib Module Boundaries

- Decision date: 2026-03-13
- Last edited: 2026-05-20
- Status: Accepted

## Context

As the L0 standard library grew, there was ambiguity about which module owned which operations. File-system operations
had leaked into `std.io`, unsafe memory operations were mixed with general runtime utilities, and the naming of modules
like `std.math` did not clearly communicate their scope.

## Decision

Module boundaries follow a strict intent-based taxonomy:

- **`std.io`**: console and stream I/O only, no file-system path operations.
- **`std.fs`**: file-system operations (existence checks, path manipulation).
- **`std.string` / `std.text`**: string utilities and text parsing.
- **`std.integer`** (formerly `std.math`): integer arithmetic helpers for the `int` type only; module name reflects its
  scope.
- **`sys.memory`** (formerly `sys.unsafe`): raw memory operations that require explicit ownership discipline; the
  `unsafe`-ish name signals the module's hazard level.
- **`sys.rt`**: low-level runtime boundary calls.

Shared integer helper contracts belong in `std.integer`; other modules that consume integer utilities (`std.time`, etc.)
may import it but must not own general-purpose arithmetic themselves.

## Rationale

- Strict boundaries make it predictable which module to import for a given operation, reducing accidental coupling.
- Renaming `std.math` to `std.integer` removes the false implication that the module handles floating-point or general
  mathematics.
- Separating `std.fs` from `std.io` mirrors the distinction between "I/O operations on streams" and "filesystem metadata
  and path operations," a distinction that matters when porting to targets without a filesystem.

## Consequences

- Call sites that used `std.math` had to be updated to `std.integer` after the rename.
- Call sites that used `sys.unsafe` had to be updated to `sys.memory`.
- Future stdlib additions must be placed in the module whose stated scope matches the new operation; boundary violations
  are caught in review.

## Related Plans

- [l0/work/plans/refactors/closed/2026-03-13-stdlib-fs-io-boundary-cleanup-noref.md](../../work/plans/refactors/closed/2026-03-13-stdlib-fs-io-boundary-cleanup-noref.md):
  moved path helpers out of `std.io`, added `std.fs::exists`
- [work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md](../../../work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md):
  renamed `sys.unsafe` to `sys.memory`
- [work/plans/refactors/closed/2026-05-13-shared-std-math-to-std-integer-rename-noref.md](../../../work/plans/refactors/closed/2026-05-13-shared-std-math-to-std-integer-rename-noref.md):
  renamed `std.math` to `std.integer`

## Current Docs

- [l0/docs/reference/standard-library.md](../reference/standard-library.md): current `std.*` and `sys.*` module API
  surface
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §5 (early I/O model)
