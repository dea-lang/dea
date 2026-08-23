# ADR-0034: Multi-Unit Generated-C Retention Tree

- Decision date: 2026-08-23
- Last edited: 2026-08-23
- Status: Accepted

## Context

A single kept C file cannot represent build/run after graph fan-out. Retention must expose every generated translation
unit and the executable wrapper without publishing private objects or interfaces, and it must preserve the exact bytes
seen by the host compiler.

## Decision

Build/run `--keep-c` retains one complete generated-C tree:

- Build retains beneath `OUTPUT.dea-c/`, including when `OUTPUT` is the default executable name. Run retains beneath
  `<canonical-source-target>.dea-c/` in the invocation directory and continues to ignore `--output`.
- The retained root must be absent. The compiler does not merge with, replace, or recursively delete an existing path.
- Each source-backed module is copied to its canonical dotted path below the root, and the exact generated process
  wrapper is copied to root `__dea_wrapper.c`. Interface-backed modules contribute no C file. The valid root module name
  `__dea_wrapper` and its ASCII case variants are rejected only with build/run keep-C because their canonical C files
  may claim that reserved path on case-insensitive filesystems; ordinary build/run keeps private wrapper scratch under a
  disjoint hidden directory and accepts the module.
- Retention copies the already staged bytes after successful linking; it never regenerates or rewrites them. Each module
  file is therefore identical to the bytes passed to its host compilation and, for identical resolution and codegen
  inputs, to `--gen` and compile-only `--keep-c`.
- Only generated C is public. Module objects, staged interfaces, wrapper objects, captures, and the run executable
  remain invocation-owned workspace artifacts.
- Creation tracks every new regular file and nested directory. Failure removes only those known entries in bounded
  reverse order; rollback failure reports the partial tree instead of broadening deletion authority.

## Rationale

- Canonical module paths make the retained tree deterministic and collision-free for dotted names.
- Copying compiled bytes makes retention auditable and prevents a second generation pass from drifting.
- Requiring an absent root gives setup and rollback one explicit ownership boundary.
- Keeping private native and interface artifacts out of the tree preserves compile-only as their publication owner.

## Consequences

- Existing callers expecting `OUTPUT.c` or a run-selected `-o.c` must consume the `.dea-c` directory instead.
- Repeating the same keep-C command requires the caller to move or remove the prior tree explicitly.
- The downstream generated-C completion work owns final four-mode identity coverage and legacy-generator removal; this
  decision owns the build/run tree shape and copy semantics.

## Related Plans

- [l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md][build-run]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: public keep-C paths and failure behavior
- [l1/docs/reference/c-backend-design.md][backend]: generated module and wrapper bytes
- [l1/docs/reference/separate-compilation.md][separate-compilation]: multi-mode artifact relationship

[backend]: ../reference/c-backend-design.md
[build-run]: ../../work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[separate-compilation]: ../reference/separate-compilation.md
