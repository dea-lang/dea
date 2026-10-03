# L1 Stage 2

This is the self-hosted L1 compiler, mechanically seeded from the 120-module Stage 1 source graph. Stage 1 remains the
semantic and diagnostic oracle. The initial production snapshot changed only `.l0` filenames to `.l1` and the compiler
identity string. The native-source review updates inherited implementation comments where needed.

The current tree contains 119 production modules. The first shared-utility/model tranche uses typed scalar constants,
unsigned stdlib conversion for canonical bigint decimals, and named fields in the large AST default constructors. It
removes the unused `util.path` wrappers while retaining growable collections, explicit ownership cleanup, structural
type comparison, and native filesystem/process bridges. The frontend/semantic review covers 56 modules and adds native
variadic token matching, guarded bitwise constant folding, typed cleanup flow, and native interface comparisons with a
constant fingerprint domain. Backend/build review uses native byte arithmetic and a caller-owned process-status scalar.
CLI defaults and parse results use named fields; unused entrypoint helpers have been removed. Growable operand vectors,
ordered validation, native bridges, and the tested C-option merge boundary remain intentional. Diagnostic and interface
contracts remain unchanged. Review findings and validation are recorded in
[l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md][native-review].

Run these commands from `l1/`:

```bash
make use-dev-stage2
source build/dea/bin/l1-env.sh
l1c --version
make test-stage2
make test-stage2-trace
make triple-test
```

`build-stage2` builds through the explicit repo-local Stage 1 artifact. It reuses common filesystem/process and native
preparation C support from `compiler/stage1_l0/support/`; fingerprint bridges come from the L1 runtime archive. No new
stdlib capability is required. `L1_CC` and `L1_CFLAGS` select native construction inputs; `L1_COMPILER_RT_*` controls
apply only to the compiler construction environment. Both stages use the same runtime, bundled interfaces, stdlib,
environment variables, and CLI contract.

`use-dev-stage1` selects the bootstrap compiler again. Ordinary build and test commands preserve the selected alias.
`KEEP_C=1 make build-stage2` retains exact per-module C and `__dea_wrapper.c` under
`build/dea/bin/l1c-stage2.native.dea-c/` (relative to a custom `L1_BUILD_DIR` when selected).

The implementation tests are `.l1` ports of the Stage 1 implementation tests; existing L1 fixtures retain their bytes.
Ported harnesses unwrap filesystem metadata as `long` and avoid the L1-reserved local name `opaque`. Compiler-facing
Python integration tests are shared with Stage 1 and receive an explicit `L1_TEST_COMPILER`. Runtime and Stage 1
bootstrap-only tests retain their original ownership. The normal Stage 1 runner clears that override.

The Stage 2 normal runner accepts `--compiler PATH` for testing a self-built native artifact. Trace targets include
`test-stage2-trace-smoke`, `test-stage2-trace-all`, and `test-stage2-trace-children`, with the same selector, slow-test,
parallelism, and artifact-retention policies as Stage 1. Each stage owns separate fixture and temporary-output paths.
With `L1_TRACE_ARTIFACT_DIR` or `--artifact-dir`, Stage 2 writes into its `stage2/` subdirectory so Stage 1 evidence is
preserved.

`triple-test` builds A through Stage 1, B through A, and C through B. It requires B and C to preserve A's retained-C
inventory and match each other's bytes, applies the established native normalization policy (native identity is skipped
for TinyCC and Windows), and runs the full Stage 2 normal suite and examples through C. Failure artifacts remain under
the selected build root; `KEEP_ARTIFACTS=1` also retains successful evidence. `test-ci` includes this gate; local
`test-extended` leaves it explicit.

The initial port and supported-host validation were completed under
[work/plans/features/closed/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md][port-plan]. Future semantic fixes
land in Stage 1 first and carry their Stage 2 equivalents in the same change. Permanent textual identity is not
required.

[native-review]: ../../work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md
[port-plan]: ../../../work/plans/features/closed/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
