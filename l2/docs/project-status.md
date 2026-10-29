# L2 Project Status

Version: 2026-10-29

L2 begins as the mechanically retargeted former L1 Stage 2 compiler, with one canonical `.l1` implementation under
`compiler/src/`. Its `.l2` target stdlib, native runtime, compiler support, tests, and build machinery are physically
owned by L2. It requires explicit compatible `L2_BOOTSTRAP_L1C` for construction. Installed mode is the default;
explicit `L2_BOOTSTRAP_MODE=development` permits reuse of a generated L1 development toolchain. Ordinary target
operations use L2 inputs without invoking that bootstrap compiler. Unified CI reuses same-run predecessor outputs;
standalone L2 CI constructs an installed L1 bootstrap. Linux Docker isolation remains available only by explicit
request, and Unified's central L2 routing default is off.

The initial contract preserves the L1 syntax/semantics, ABI, separate compilation/linking, and managed support behavior
available at the split. Later L1 changes are not inherited automatically. L2 source suffixes are `.l2`, interfaces are
`.l2m`, and level-specific driver diagnostics are `L2C-xxxx`; shared families retain their registered meanings.
Extensionless logical module names remain valid. Compatibility ABI/header symbols may retain historical names such as
`l1_real.h` without changing target ownership.

The shared split is complete: hosted compiler CI passed on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64,
including coordinated development handoffs; both Linux isolation phases passed. The split added no self-hosting,
parity/triple-bootstrap gate, release productization, or new language features. See
[work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md).

Sustained feature development remains deferred until L1 is declared stable, a baseline is selected, and the L2 phase is
explicitly started. The adopted future scope includes generic streams, networking, JSON, file watching, concurrency,
owned slices, and broader language expressiveness; these capabilities are not implemented by the split. See
[l2/docs/roadmap.md](roadmap.md).

L2 now generates a bootstrap-independent native C reference with `make docs` or `make docs-pdf`, covering owned runtime
and compiler-support inputs under `build/docs/native/`. Compiler-language and stdlib-binding autodocs and release
productization remain unavailable. See [l2/docs/README.md](README.md).
