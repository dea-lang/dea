# ADR-0022: Compile-Only Artifact Endpoint Rollback

- Decision date: 2026-07-24
- Last edited: 2026-08-21
- Status: Accepted

## Context

Compile-only mode must turn one L1 source module into a reusable relocatable object and module interface without leaving
a mixed old/new artifact set after an ordinary recoverable failure. Generated C is required internally by the host
compilation step and may be retained explicitly. Imported modules are semantic inputs through verified interfaces; they
must not be compiled into the target object. The implementation also needs same-filesystem publication without depending
on a global temporary-root policy or expanding the Dea runtime and standard-library APIs.

The publication boundary is an endpoint rollback guarantee, not an atomic reader-visible snapshot. The caller-selected
artifact parent and host C compiler are trusted for one invocation. Concurrent readers and same-stem writers require
external serialization. Hostile mutation of the parent, crash recovery, `SIGKILL`, power loss, locking, and `fsync`
durability are outside this boundary.

## Decision

L1 compile-only analysis resolves exactly one source module and requires interface artifacts for every imported module.
It publishes sibling `.o` and `.l1m` destinations by default. `--keep-c` adds the canonical sibling `.c` destination and
publishes the exact generated C used to produce the object.

The driver creates missing destination parents with mode `0777` subject to `umask`. Compiler-private follow
classification accepts existing trusted directory aliases, so missing descendants beneath an alias may be created. When
follow classification reports an absent target, no-follow classification distinguishes a genuinely missing lexical path
from a dangling alias before creation. Dangling aliases and aliases to non-directories are rejected, and a
directory-creation collision is accepted only after follow reclassification confirms a directory. Final `.c`, `.o`, and
`.l1m` destinations and transaction, backup, validation, and cleanup paths retain no-follow classification; an existing
selected destination must be a regular file and a symlink destination is rejected. Without `--keep-c`, the driver never
classifies or otherwise touches the canonical `.c` path.

After analysis succeeds, the driver exclusively creates one hidden transaction directory beside the destination set.
POSIX requests mode `0700`; MinGW inherits the trusted parent's ACL. Staged artifacts and backups of existing selected
destinations remain inside this directory.

A compiler-private raw-byte filesystem ABI in the existing Stage 1 support translation unit provides exclusive directory
creation, follow and no-follow path classification, same-filesystem movement to an absent destination, and empty
directory removal. MinGW uses the same native narrow path encoding as the existing Stage 1 runtime filesystem and
process operations. This ABI is not part of `std.fs`, `sys.rt`, the public runtime, or the Dea language.

Before publication, the driver verifies that every selected staged path is a regular file, parses and fingerprints the
staged interface, and confirms that the interface names the target module. The staged object remains an opaque,
caller-trusted native sibling and is not structurally bound to the interface. The driver then moves existing selected
destinations to backups, publishes generated C only when requested, publishes the object, and publishes the interface
last. A failure rolls selected changes back in reverse order. Successful rollback removes the transaction directory and
reports `L1C-2035`; failed rollback retains recovery files, reports their directory, and uses `L1C-2036`.

The externally observable guarantee is defined at operation endpoints:

- successful return leaves the complete new selected artifact set;
- recoverable failure returns with the exact prior selected set restored; and
- rollback failure retains recovery files and reports their location.

During publication or rollback, selected paths may be temporarily absent or may name artifacts from different
generations. Interface-last ordering constrains the writer's mutation order but does not create a snapshot for
concurrent readers.

Native build/run now uses the command-owned private workspace defined by [ADR-0020][native-workspace-adr] and completed
by the [native workspace safety plan][native-safety]. That lifecycle remains separate from and does not replace this
compile-only publication path.

## Rationale

- A sibling transaction directory guarantees same-filesystem movement without a process-wide temporary-directory policy.
- Publishing the interface last ensures the writer places the new object before the new interface in the sequential
  publication order.
- Validating the interface and regular staged outputs rejects malformed publication endpoints without claiming an
  authenticated or reader-atomic object/interface pair.
- A narrow compiler-private ABI keeps bootstrap filesystem mechanics out of the minimal public language and runtime
  surface.
- Retaining recovery files only when restoration fails preserves evidence needed for manual recovery.

## Consequences

- `-c` / `--compile` publishes the reusable `.o` and `.l1m` pair; `--keep-c` expands the selected set with the exact
  staged `.c`.
- Normal analysis, emission, and host-compilation failures leave the prior selected set unchanged. A recoverable
  publication failure restores that prior set. Ordinary `-c` leaves any canonical `.c` path untouched.
- Publication and rollback are sequential rename operations. They do not prevent reader-visible gaps or mixed
  generations, so readers and same-stem writers must serialize externally.
- Endpoint rollback relies on the trusted-parent assumption and does not promise crash durability.
- Auxiliary files explicitly requested through raw host-C options are not recursively deleted; if one prevents cleanup,
  the compiler reports and retains the transaction directory for inspection.
- `--build` and `--run` use command-owned private workspaces; later multi-CU orchestration must reuse that lifecycle
  without routing compile-only publication through it.
- Future Stage 2 support must preserve the same artifact validation, publication order, and rollback semantics.

## Related Plans

- [l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md][interface-authority]
- [l1/work/plans/bug-fixes/closed/2026-07-26-stage1-cross-platform-ci-regressions-noref.md][cross-platform-ci]
- [l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md][compile-only]
- [l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md][stage1-safety]
- [work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md][native-safety]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli-contract]: compile-mode inputs, outputs, and failure behavior
- [l1/docs/reference/architecture.md][architecture]: compile-only analysis and publication flow
- [l1/docs/reference/c-backend-design.md][backend]: per-module C and native artifact production
- [l1/docs/project-status.md][project-status]: implemented Stage 1 scope

[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[cli-contract]: ../../../docs/specs/compiler/cli-contract.md
[compile-only]: ../../work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[cross-platform-ci]: ../../work/plans/bug-fixes/closed/2026-07-26-stage1-cross-platform-ci-regressions-noref.md
[interface-authority]: ../../work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md
[native-safety]: ../../../work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
[native-workspace-adr]: ../../../docs/decisions/0020-native-compiler-private-temporary-workspaces.md
[project-status]: ../project-status.md
[stage1-safety]: ../../../l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md
