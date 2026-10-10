# L2 Project Status

Version: 2026-10-10

L2 begins as the mechanically retargeted former L1 Stage 2 compiler, with one canonical `.l1` implementation under
`compiler/src/`. Its `.l2` target stdlib, native runtime, compiler support, tests, and build machinery are physically
owned by L2. It requires explicit compatible installed `L2_BOOTSTRAP_L1C` for construction; ordinary target operations
use L2 inputs without invoking that bootstrap compiler.

The initial contract preserves L1 syntax/semantics, ABI, separate compilation/linking, and managed support behavior. L2
source suffixes are `.l2`, interfaces are `.l2m`, and level-specific driver diagnostics are `L2C-xxxx`; shared families
retain their registered meanings. Extensionless logical module names remain valid. Compatibility ABI/header symbols may
retain historical names such as `l1_real.h` without changing target ownership.

The shared split plan tracks implementation, local validation, and outstanding platform evidence separately. L2 has no
self-hosting, parity/triple-bootstrap gate, release productization, or new feature scope. See
[work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md).
