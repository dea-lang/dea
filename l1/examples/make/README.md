# Separate Compilation with Make

This example uses Make to compile the `support` module once and reuse it when building `main`. The finished program
prints `42`.

## Build and Run

You need `l1c`, GNU Make 3.81 or later, and a supported host C compiler/linker and preparation tools. Use GCC, upstream
Clang 16 or newer, or Apple Clang with the required configuration capabilities. See
[l1/docs/user/README.md](../../docs/user/README.md) for installed-toolchain requirements and
[l1/docs/user/README-WINDOWS.md](../../docs/user/README-WINDOWS.md) for Windows setup.

With an installed toolchain already activated, enter `l1/examples/make/` in the source checkout and run `make run`. The
release package does not bundle this example. Building it with an installed compiler needs no L0 or Python.

To use a development compiler instead, follow the prerequisites and bootstrap selection in
[l1/README.md](../../README.md). From the repository's `l1/` directory:

```sh
make use-dev
source build/dea/bin/l1-env.sh
cd examples/make
make run
```

The Makefile uses `l1c` from `PATH` by default. To select another compiler, set `L1C`:

```sh
make run L1C=/absolute/path/to/l1c
```

Run `make clean` to remove the generated files. All build output stays under `build/`.

## What Make Builds

```text
support.l1  -> build/support.o
            -> build/support.l1m

main.l1 + build/support.o + build/support.l1m -> build/main
```

`l1c --compile support` creates the reusable object and module interface as a pair. When `l1c --build main` receives
`-I build`, it reads `support.l1m` and links `support.o` instead of compiling `support.l1` again.

Make decides when those commands need to run:

- With no changes, another `make` does nothing.
- Changing `main.l1` rebuilds only the executable.
- Changing `support.l1` rebuilds the artifact pair and the executable.
- Removing either `support` artifact recreates the pair.

The Makefile treats `support.o` and `support.l1m` as one logical output while remaining compatible with GNU Make 3.81.
Keep each object and its same-stem interface together, and make consumers depend on both. Run `make clean` after
changing the compiler or compiler options.

For the complete artifact and dependency rules, see
[l1/docs/reference/separate-compilation.md](../../docs/reference/separate-compilation.md).
