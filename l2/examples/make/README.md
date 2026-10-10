# Separate Compilation with Make

This example uses Make to compile the `support` module once and reuse it when building `main`. The finished program
prints `42`.

## Build and Run

You need `l2c`, GNU Make 3.81 or later, and a C99 compiler.

From the repository's `l2` directory, build and activate the canonical compiler, then enter the example:

```sh
export L2_BOOTSTRAP_L1C=/absolute/installed-l1/bin/l1c
make use-dev
source build/dea/bin/l2-env.sh
cd examples/make
make run
```

The Makefile uses `l2c` from `PATH` by default. To select another compiler, set `L2C`:

```sh
make run L2C=/absolute/path/to/l2c
```

Run `make clean` to remove the generated files. All build output stays under `build/`.

## What Make Builds

```text
support.l2  -> build/support.o
            -> build/support.l2m

main.l2 + build/support.o + build/support.l2m -> build/main
```

`l2c --compile support` creates the reusable object and module interface as a pair. When `l2c --build main` receives
`-I build`, it reads `support.l2m` and links `support.o` instead of compiling `support.l2` again.

Make decides when those commands need to run:

- With no changes, another `make` does nothing.
- Changing `main.l2` rebuilds only the executable.
- Changing `support.l2` rebuilds the artifact pair and the executable.
- Removing either `support` artifact recreates the pair.

The Makefile treats `support.o` and `support.l2m` as one logical output while remaining compatible with GNU Make 3.81.
Keep each object and its same-stem interface together, and make consumers depend on both. Run `make clean` after
changing the compiler or compiler options.

For the complete artifact and dependency rules, see
[l2/docs/reference/separate-compilation.md](../../docs/reference/separate-compilation.md).
