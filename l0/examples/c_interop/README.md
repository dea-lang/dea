# Additional C Translation Units

This example passes two C translation units to `l0c` with the repeatable `--c-source` option. The L0 program declares
one `extern func` from each C file, calls both functions, and prints `42` twice.

## Build and Run

You need a working `l0c` compiler.

From the repository's `l0` directory, build and activate the Stage 2 compiler, then enter the example:

```sh
make use-dev-stage2
source build/dea/bin/l0-env.sh
cd examples/c_interop
l0c --run \
    --c-source c_add.c \
    --c-source c_multiply.c \
    c_interop
```

The program prints:

```text
C sum: 42
C product: 42
```

## What the Compiler Builds

```text
generated C for c_interop.l0
    + c_add.c
    + c_multiply.c
    -> temporary executable
    -> run
```

Each `--c-source` value is preserved as one host-compiler argument. The generated C input comes first, followed by the
additional sources in command-line order.

The `extern func` declarations in `c_interop.l0` expose the unmangled C symbols to L0. Each additional C translation
unit includes the public `dea_rt.h` header and uses `dea_int`, the common Dea spelling for L0's 32-bit signed integer
ABI. The generated L0 translation unit includes `l0_runtime.h`, which owns the header-only runtime implementation.
Additional C sources must not include `l0_runtime.h`: doing so would define the implementation once per source and cause
duplicate symbols at link time.

`dea_rt.h` is a declaration-only interface introduced for L0 2.1.0. Its `dea_*` types and the `rt_*` declarations that
both levels implement form the source-compatible subset shared with L1. L0 keeps its existing `l0_*` type names as
aliases. This is a source and ABI-representation compatibility promise for compiling equivalent C code against either
level; it is not binary compatibility between L0 and L1 runtimes. Do not depend on compiler-private `_rt_*` names,
memory-tracker internals, level-mangled structs, build-mode macros, or the levels' different packaging models.

The L0 compiler checks calls against the L0 declarations, but matching each declaration to its C definition remains the
programmer's responsibility.

For the complete command-line and FFI contracts, see
[l0/docs/specs/compiler/cli-contract.md](../../docs/specs/compiler/cli-contract.md) and
[l0/docs/decisions/0005-extern-func-ffi-boundary.md](../../docs/decisions/0005-extern-func-ffi-boundary.md).
