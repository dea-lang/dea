# Dea/L1

> _C-family syntax, modules and separate compilation, checked arrays and slices, nullable types, and ARC-managed
> strings._

**Dea/L1** is level one of the Dea systems programming language. Its `l1c` compiler translates `.l1` programs through C
into native executables. This package contains the standalone compiler, standard library, runtime support, and runnable
examples.

**Development status:** L1 is under active development. The package version does not promise stable language,
module-interface, or binary compatibility across future releases. Exact package and build metadata are recorded in
[VERSION].

## Prerequisites

Using this package needs no L0, Python, Make, or source checkout. To build and run native programs, install a supported
C compiler, linker, and host preparation tools: supported GCC or capability-verified Clang/Apple Clang. Validated Debian
Clang 14/15 use isolated empty configuration files for runtime preparation; modern Clang uses `--no-default-config`. Set
`L1_CC` to select the C compiler explicitly.

Native packages target Linux x86_64, macOS Intel, macOS Apple Silicon, and Windows x86_64. Use the package matching your
operating system and architecture.

**Windows:** follow [README-WINDOWS.md][windows] for platform setup, activation, and build/run commands. The shell
examples below use bash or zsh on Linux and macOS; the language example and package information apply to all platforms.

## First run

Replace `/path/to/dea-l1` with this package's directory. Quote paths containing spaces.

```bash
cd /path/to/dea-l1
source ./bin/l1-env.sh
l1c --version
l1c --check examples/hello.l1
l1c --run examples/hello.l1
```

Activation selects this compiler in the current shell. `--check` analyzes the program without producing an executable.
`--run` builds and executes `examples/hello.l1`, which prints greetings in 25 languages in a shuffled order. The output
includes `Hello, world! This is Dea/L1.`; displaying every language requires suitable terminal fonts.

The first native build prepares matching standard-library and runtime support in a writable per-user cache and can take
longer. Later builds reuse compatible support. The installation itself remains unchanged.

To keep an executable, choose a writable output directory. For example, from a writable package directory:

```bash
l1c --build examples/hello.l1 -o hello
./hello
```

If the package directory is read-only, pass an output path in your project directory instead.

The file-path form is convenient for a one-shot run. You can equivalently select the project root with `-Rp` and name
its entry module:

```bash
l1c --run -Rp examples hello
```

Here, `-Rp examples` (or its long form, `--project-root examples`) sets the project root and `hello` selects
`examples/hello.l1`. This form is especially useful for multi-module programs, where the project root gives module
lookup a common base.

## More bundled examples

From the package directory, try:

```bash
l1c --run examples/slices.l1
l1c --run examples/demo.l1 -- mul 6 add 5 2
l1c --run examples/hamurabi.l1
```

- [examples/hello.l1][hello] prints multilingual greetings using arrays and randomness.
- [examples/slices.l1][slices] demonstrates slice views and mutations shared with their backing arrays.
- [examples/demo.l1][demo] evaluates prefix-notation expressions using enums and recursive parsing. The command above
  prints `= 42`; arguments after `--` are passed to the program.
- [examples/hamurabi.l1][hamurabi] is an interactive text game.
- [examples/make/README.md][make-example] explains a small project that reuses a separately compiled module. This
  example additionally needs GNU Make 3.81 or newer.

These examples match the packaged compiler version. Copy examples into a writable project directory before editing or
using the Make project; keep the installed package intact. From the copied examples directory, run `l1c --run hello.l1`,
or use the equivalent module form `l1c --run -Rp . hello`.

## Your own program

With the environment still active, create `hello.l1` in a writable project directory:

```l1
module hello;

import std.io;

func main() {
    printl_s("Hello, L1!");
}
```

From that directory:

```bash
l1c --check hello.l1
l1c --run hello.l1
l1c --build hello.l1 -o hello
./hello
```

The program prints `Hello, L1!`. Run `l1c --help` to explore compiler options.

## What is included

- `bin/`: compiler launchers and environment helpers.
- `interfaces/`: bundled semantic module interfaces.
- `shared/`: standard-library and runtime sources used to prepare native support.
- `include/`: public runtime headers.
- `examples/`: runnable language and standard-library examples, plus a separate-compilation Make project.
- [share/doc/dea/l1/toolchain.md][toolchain]: compiler usage, native preparation, cache controls, and relocation.

Release archives also include offline HTML and PDF references. Direct compiler-only installations may omit those
optional files.

## Cache and relocation

Set `L1_STDLIB_CACHE` or use `--stdlib-cache` to select another writable support cache. Different native configurations
select different profiles; matching support is prepared as needed. See [share/doc/dea/l1/toolchain.md][toolchain] for
explicit preparation and cache-reuse controls.

Keep the entire package directory together when moving it, including hidden and metadata files. A read-only installation
is supported. After moving the package, source `bin/l1-env.sh` from its new location. Activation is optional: direct
launcher invocation works from any directory.

## Documentation and examples

For the offline HTML reference, open `share/doc/dea/l1/autodocs/html/index.html`. The full PDF is at
`share/doc/dea/l1/autodocs/pdf/dea_l1_api_reference.pdf`. These references are included in distribution archives; keep
the documentation tree intact so its relative links continue to work.

The bundled [share/doc/dea/l1/toolchain.md][toolchain] covers separate compile/link commands and installation repair.
Further reading is available online in the [Dea repository](https://github.com/dea-lang/dea):

- [l1/examples/](https://github.com/dea-lang/dea/tree/main/l1/examples): language and standard-library examples.
- [l1/docs/user/linking.md](https://github.com/dea-lang/dea/blob/main/l1/docs/user/linking.md): external libraries and
  native linking options.
- [l1/docs/releases/0.1.0.md](https://github.com/dea-lang/dea/blob/main/l1/docs/releases/0.1.0.md): the first release's
  feature baseline and compatibility notes.

Online examples and guides follow repository development and may describe changes newer than this package. Use the
bundled references for the installed version.

## Licensing

See [LICENSE-MIT][mit], [LICENSE-APACHE][apache], and [THIRD_PARTY_NOTICES][notices].

[apache]: LICENSE-APACHE
[demo]: examples/demo.l1
[hamurabi]: examples/hamurabi.l1
[hello]: examples/hello.l1
[make-example]: examples/make/README.md
[mit]: LICENSE-MIT
[notices]: THIRD_PARTY_NOTICES
[slices]: examples/slices.l1
[toolchain]: share/doc/dea/l1/toolchain.md
[version]: VERSION
[windows]: README-WINDOWS.md
