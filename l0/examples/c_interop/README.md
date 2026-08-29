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

The `extern func` declarations in `c_interop.l0` expose the unmangled C symbols to L0. The C definitions use `int32_t`
because L0's `int` has a 32-bit signed ABI. The L0 compiler checks calls against the L0 declarations, but matching each
declaration to its C definition remains the programmer's responsibility.

For the complete command-line and FFI contracts, see
[l0/docs/specs/compiler/cli-contract.md](../../docs/specs/compiler/cli-contract.md) and
[l0/docs/decisions/0005-extern-func-ffi-boundary.md](../../docs/decisions/0005-extern-func-ffi-boundary.md).
