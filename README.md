# The Dea Programming Language.

> _C-family syntax, UB-free semantics, ARC strings, sum types and pattern matching._

Welcome to the **Dea** programming language!

Dea is a systems programming language built through a staged bootstrap chain: each compiler level is compiled by the
previous one.

**Level 0 is now self-hosted.** It is the compiler base that will be used to compile L1. L1 will subsequently self-host
to build L2, and the process will repeat for successive levels.

The design is conservative by choice: a small, precisely specified language whose semantics leave no room for undefined
behavior. Operations are either well-defined or rejected - at compile time or with a named runtime error.

_Tertium non datur._

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE-MIT)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE-APACHE)

## Dea/L<sub>0</sub>

**L0 (Level Zero)** is a small systems language that compiles to C99.

## Motivation

Writing a compiler is a systems programming task. You need to manage memory, represent complex data structures, and have
precise control over performance characteristics. Many modern languages either remove that kind of control or bury it
under runtime machinery.

Dea/L0 instead keeps a small, explicit core aimed at bootstrap-friendly implementation work. The objective is a small,
UB-free systems language sufficient to host its own compiler.

That constrains the design considerably. The type system needs sum types and pattern matching - a compiler without them
is fighting its own data. It needs explicit nullable types, because implicit null is a specification gap. It needs
deterministic resource management without requiring a garbage-collected runtime. It needs pointers without UB. It does
not need much else.

The surface syntax is C-family deliberately: operator precedence, braces, explicit types, `return`. Familiarity is
load-bearing when the language is also the implementation vehicle.

The C99 backend is a bootstrap convenience. The trusted C kernel isolates all platform-dependent behavior; the rest of
the semantics are enforced by L0 itself.

## Project status and directions

L0 `1.0.0` is the current release line.

- Stage 1: complete and remains the reference implementation for language behavior.

- Stage 2: self-hosted and is the main delivery vehicle for normal developer, install, and distribution workflows.

  - Bootstrap artifact: buildable today under `build/dea/bin` via `python scripts/build_stage2_l0c.py`.

  - Repo-local Dea build workflow: `make use-dev-stage2` builds, installs, and selects the Stage 2 compiler under
    `build/dea/bin` for development use.

  - Install available via `make PREFIX=/tmp/l0-install install`; this installs the self-hosted Stage 2 compiler
    (`S1 -> S2`, then `S2 -> S2`) plus copied `shared/l0/stdlib` and `shared/runtime` assets.

  - Fixed-point self-hosting verified: retained generated C matches across self-builds, and native compiler-binary
    identity is also checked on the validated reproducibility matrix. See
    [`l0/compiler/stage2_l0/README.md`](l0/compiler/stage2_l0/README.md) for the documented `tcc` and Windows
    exceptions.

- **Built-in Observability:** Language developers need to know what memory is doing. L0 ships with native compiler flags
  to trace ARC events and allocations directly to stderr. Today these are fully usable through the Stage 1 driver and
  are already wired through Stage 2 `--gen`, `--build`, and `--run`:

```shell
l0c --run --trace-arc --trace-memory app.l0
```

## Design highlights

- `match` pattern-matches on enum variants, binding payload fields by name.
- `T?` is an explicit optional type. `expr?` short-circuits: if the expression is null, the enclosing `T?`-returning
  function returns null immediately.
- No exceptions.
- No `defer`: L0 uses `with` and `cleanup` blocks instead. Cleanup runs when the `with` body exits, the scoping is
  explicit, and there is nothing to reason about at a distance.
- No `goto`.
- `ptr.field` auto-dereferences; `->` is not a dereference operator (it is used for return type annotations).
- `=` is a statement. `if (x = 0)` is a type error.
- `case` dispatches on constant values (including strings): `"foobar" => stmt`, or `else stmt` for the default. No
  implicit fallthrough. Strings are valid case keys.
- `;` is not a valid empty statement. Use `null;` or an empty block if you need an explicit no-op.
- Widening conversions are implicit (`byte` to `int`, `T` to `T?`). Narrowing is always explicit and checked both
  statically and at runtime: `300 as byte` is a compiler error, `my_opt_str as string` panics on null. Use
  `unwrap_or_s(my_opt_str, "default")` if null is a valid case.

## Repository layout

The repository root contains the shared virtual environment and build artifacts, while `l0/` contains the compiler
source and the main entrypoints for development and installation workflows.

Monorepo release tags are level-prefixed. Pre-monorepo bare tags such as `v0.9.0` and `v0.9.1` remain historical
references, while current L0 releases use `l0-vX.Y.Z`. The repo-level release-tag policy lives in
[`MONOREPO.md`](MONOREPO.md).

## Getting Started

First, clone the repository and `cd` into `l0/`.

All L0 workflow commands described below are designed to be run from [`l0/`](l0/) unless they explicitly say otherwise.

### Prerequisites for Stage 1

- A C99 compiler (`gcc`, `clang`, and recent `tcc` version are known to work).
- `make` is the primary entrypoint for installation and development workflows.
- Python 3.14+.
- [`uv`](https://github.com/astral-sh/uv) (`make` will fall back to `python3 -m venv` if `uv` is not available).

#### Supported C compilers

The driver will use any C compiler specified in `$L0_CC` if set. Otherwise, it probes the system PATH for the first
available from this list:

- `tcc`
- `gcc`
- `clang`
- `cc`

The `$CC` environment variable will be checked as a last resort if none of the above are found.

If you need a specific compiler, set `$L0_CC` to its executable name or path. For example:

For the current `1.0.0` support matrix, Windows validation is through MSYS2 `UCRT64` with MinGW-w64 GCC. MSYS2 `MINGW64`
is supported as an alternate environment.

MSVC-family builds are still unsupported and are not part of the validated release matrix.

Specific versions of `gcc` and `clang` whose names include version numbers (e.g. `gcc-14`, `clang-22`) are not probed by
default but can be used by setting `$L0_CC` accordingly and will be recognized as such.

Tiny C Compiler (`tcc`) is the default if available, as it is fast and supports all required C99 features. It is not
required, however. If you want to use `tcc` but it is not available on your system, cloning and building it from recent
source is highly recommended, as some platform package managers provide outdated versions.

### Install

From the repository root, create the shared repo-local virtual environment and then enter `l0/`:

```shell
make venv
cd l0
```

You can also enter `l0/` directly and use the level-local entrypoint:

```shell
make venv                # create or reuse ../.venv; prefers uv when available
```

For Windows-specific setup, generated launchers, MSYS2 bash usage, and native `cmd.exe` usage, see
[README-WINDOWS.md](README-WINDOWS.md).

If you prefer to manage the environment manually, `uv sync --all-groups` from the monorepo root is the recommended
direct command (the repo is a single `uv` workspace; the root `pyproject.toml` declares `l0/` and `l1/` as members and
owns the dev/docs dependency groups, and there is one `./.venv` plus one `./uv.lock` at the root). A plain
`python3 -m venv ./.venv` workflow at the root also works.

For an optional reproducible Linux test environment, use the explicit Docker wrapper:

```shell
make docker CMD=test-all
```

For normal developer use, install the repo-local switchable `l0c` alias, choose the stage you want, and source the
generated environment script:

```shell
make use-dev-stage1      # or: make use-dev-stage2
source build/dea/bin/l0-env.sh
l0c --help
l0c --version
```

On Windows `cmd.exe`, the equivalent activation step is `call build\\dea\\bin\\l0-env.cmd`.

The `./scripts/l0c` entrypoint remains available, but it is the source-tree Stage 1 wrapper and is mainly useful for
bootstrap mechanics, internal tooling, and Stage 1-focused testing.

For a repo-independent Stage 2 install prefix:

```shell
make PREFIX=/tmp/l0-install install
source /tmp/l0-install/bin/l0-env.sh
l0c --version
```

On Windows `cmd.exe`, the equivalent activation step is `call <PREFIX>\\bin\\l0-env.cmd`.

`make install` requires an explicit `PREFIX=...`; there is no implicit default install root.

For a relocatable distribution archive under `build/`:

```shell
make dist
```

`make dist` creates one temporary `dea-l0/` tree under `build/` plus a host-native archive named
`dea-l0-lang_<os>-<arch>_YYYYMMDD-HHMMSS.tar.gz` on POSIX or `dea-l0-lang_<os>-<arch>_YYYYMMDD-HHMMSS.zip` on Windows,
using the lower-case OS/architecture from the recorded build host plus the UTC build timestamp in the archive name.

`install` installs the self-hosted Stage 2 compiler (`Compiler 2` from the triple-bootstrap chain), not the initial
Stage 1-built bootstrap artifact.

### First program

```l0
module hello;

import std.io;

func main() -> int {
    printl_s("Hello, L0!");
    return 0;
}
```

```shell
l0c hello.l0 -o hello && ./hello        # produce a binary and run it
l0c --run hello.l0                      # compile and execute in one step
l0c --check hello.l0                    # analyze only, no output (use `-v`/`-vvv` for verbose diagnostics)
l0c --version                           # print the active compiler stage identity and exit
```

### Multi-module projects

```shell
l0c --run -P ./src -P ./lib main        # -P adds a project root to search for modules; main is the target module (main.l0)
```

The compiler resolves modules from system roots (stdlib) then project roots in order.

Environment-variable defaults and launcher-specific path behavior are documented in
[l0/compiler/stage2_l0/README.md](l0/compiler/stage2_l0/README.md),
[l0/docs/project-status.md](l0/docs/project-status.md), and [README-WINDOWS.md](README-WINDOWS.md).

### Examples

```shell
l0c -P examples --run hamurabi
```

The `examples/` directory covers most language features and is worth reading as code.

[Hamurabi](l0/examples/hamurabi.l0) is a faithful L0 port of the 1968 resource-management game - ancient Sumeria, grain
storage, and all.

[optional_config](l0/examples/optional_config.l0) is a smaller example showing optional values in a practical setting:
parse a retry count from the command line or `APP_RETRIES`, validate it, and fall back to a default.

### A more advanced example

The next example is a simple prefix notation calculator that demonstrates recursive data structures, pattern matching,
and scoped resource management using the `with` statement. It also shows how to use the `?` operator to propagate `null`
on parse failure without needing to check for it at every step.

<details>
<summary>Click here to show the source code.</summary>
<p>

```l0
module demo;

import std.io;
import std.string;
import std.text;
import std.system;

// A simple expression language with integers, addition, and multiplication.
enum Expr {
    Num(value: int);
    Add(left: Expr*, right: Expr*);
    Mul(left: Expr*, right: Expr*);
}

struct Cursor { pos: int; } // current position in argv

/* Recursively evaluate an expression tree. */
func eval(e: Expr*) -> int {
    match (*e) {
        Num(value)       => { return value; }
        Add(left, right) => { return eval(left) + eval(right); }
        Mul(left, right) => { return eval(left) * eval(right); }
    }
}

/* Recursively free an expression tree. */
func free_expr(e: Expr*?) {
    if (e == null) return;
    match (*(e as Expr*)) { // unwrap
        Num(value)       => {}
        Add(left, right) => { free_expr(left); free_expr(right); }
        Mul(left, right) => { free_expr(left); free_expr(right); }
    }
    drop e;
}

/* A simple recursive-descent parser for our expression language.
   Returns null on bad input; ? propagates failure upward. */
func parse(c: Cursor*) -> Expr*? {
    if (c.pos >= argc()) { return null; }

    let tok: string = argv(c.pos);
    c.pos = c.pos + 1;

    let n: int? = string_to_int(tok);
    if (n != null) { return new Num(n as int); }

    let result: Expr*? = null;
    with (let left: Expr*? = parse(c)?,
          let right: Expr*? = parse(c)?) {
        case (tok) {
            "add" => { result = new Add(left as Expr*, right as Expr*); }
            "mul" => { result = new Mul(left as Expr*, right as Expr*); }
            // unrecognized operator: leave result as null to signal failure
        }
        return result;
    }
    cleanup {
        if (result == null) { // on parse failure, free any subtrees we allocated
            free_expr(left);
            free_expr(right);
        }
    }
}

/* Main entry point. Expects prefix-notation arguments:
   demo add 2 3          # prints "= 5"
   demo mul 6 add 5 2    # prints "= 42" */
func main() -> int {
    with (let c = new Cursor(1) => drop c,
          let expr = parse(c) => free_expr(expr)) { // release c and expr on exit
        if (expr == null || c.pos != argc()) {
            printl_s("usage: demo <expr>\n<expr> ::= add|mul <expr> <expr> | <int>");
            return 1;
        }
        printl_si("=", eval(expr as Expr*)); // unwrap
        return 0;
    }
}
```

</details>

This program is available in [l0/examples/demo.l0](l0/examples/demo.l0). You can run it from within `l0/` as follows:

```shell
l0c examples/demo.l0 -o demo
./demo mul 6 add 5 2
```

It will parse the expression `mul 6 add 5 2` as a tree, evaluate it to `6 * (5 + 2)`, and print `= 42`.

## Language overview

**Types:** `int`, `bool`, `string`, `byte`, structs, enums with payloads, pointers (`T*`, `T**`), nullable pointers
(`T*?`), optional values (`T?`), type aliases.

`string` is a convenient, small value type: you can assign it, pass it, and return it cheaply. String memory (where the
expensive data is stored) is managed automatically via reference counting.

Manual heap allocation of structs and other data in the language is explicit (`new`/`drop`) and delegated to the
programmer (no GC).

`sizeof()` and `ord()` are language intrinsics that return the size of a type in bytes and the ordinal value of an enum
variant, respectively.

**Modules:** one file, one module. Dotted names (`std.io`). No forward declarations - all top-level symbols in a module
are visible throughout it. Symbols are qualified as `module::Symbol` where disambiguation is needed.

**Pointers:** `T*` is non-null. `T*?` is nullable. No `&` address-of operator in current stages. No pointer arithmetic
in Stage 1. Field access auto-dereferences.

**Null safety:** `T?` for optional values; `null` for the empty case. `T` widens to `T?` implicitly. `T? as T` narrows
with a runtime panic on null; use `unwrap_or_*` variants when null is a valid case. `expr?` propagates null from the
enclosing function.

**No UB:** every operation is defined, rejected at compile time, or produces a named runtime failure. No implicit
narrowing conversions. No assignment-as-expression.

**Extern:** `extern` functions interface directly with the C kernel.

**Control flow:** `if`/`else`, `while`, C-style `for`, `return`, `break`, `continue`, `match` (enum variant dispatch),
`case` (literal dispatch), `with`/`cleanup` (scoped resource management), `expr?` (null propagation).

## Grammar

The authoritative grammar is in [l0/docs/reference/grammar.md](l0/docs/reference/grammar.md).

Types compose as: `T*`, `T**`, `T?`, `T*?`. Expressions follow C precedence, extended with the postfix `?` operator and
`as` casts.

## Compiler implementation architecture

Stage 1 follows a conventional pipeline from lexer to semantic analysis to C99 code generation. Stage 2 mirrors the same
pipeline in L0 itself, with separate lexer, parser, AST, type-checking, backend, and driver modules.

For the full compiler workflow, bootstrap/install layout, test targets, and current Stage 2 command surface, use:

References:

- [Architecture and data flow](l0/docs/reference/architecture.md)
- [Design decisions](l0/docs/reference/design-decisions.md)
- [Ownership and memory management](l0/docs/reference/ownership.md)
- [Stage 1 contract](l0/docs/specs/compiler/stage1-contract.md)
- [Shared CLI contract](l0/docs/specs/compiler/cli-contract.md)
- [Contributing guide](CONTRIBUTING.md) for developer workflow, setup, and validation commands

## CLI

The recommended developer-facing CLI is `l0c` after selecting a stage with `make use-dev-stage1` or
`make use-dev-stage2` and activating the selected environment (`source build/dea/bin/l0-env.sh` on POSIX/MSYS2 bash,
`call build\\dea\\bin\\l0-env.cmd` in `cmd.exe`). The source-tree `./scripts/l0c` wrapper is Stage 1 only and remains
useful mainly for bootstrap mechanics and Stage 1-focused testing.

```shell
l0c [mode] [options] <target>
# or, for the source-tree Stage 1 wrapper only:
# ./scripts/l0c [mode] [options] <target>
```

Global identity and logging options include `--help`, `--version`, `-v/--verbose`, and `-l/--log`. The main mode flags
are as follows:

| Mode           | Action                      |
| -------------- | --------------------------- |
| `--build`      | Compile to binary (default) |
| `--check`      | Analyze only                |
| `--run` / `-r` | Compile and execute         |

```shell
l0c --build --keep-c hello.l0             # retain the generated C
l0c --run app.main -- arg1 arg2           # pass arguments to the program
l0c --run --trace-arc --trace-memory app  # trace ARC and allocation to stderr
l0c -c clang -C "-Og -DDEBUG" hello.l0    # use a specific C compiler with custom flags
```

Full CLI contract, mode flags, options, targets, identity strings, exit codes, and stage-specific differences:
[l0/docs/specs/compiler/cli-contract.md](l0/docs/specs/compiler/cli-contract.md).

Trace output contract: [l0/docs/specs/runtime/trace.md](l0/docs/specs/runtime/trace.md).

## Project status

[l0/docs/project-status.md](l0/docs/project-status.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). It is the source of truth for developer workflow, setup, and validation
commands.

## License

[MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE), at your option.

Third-party notices: [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES).

## Author

[@googlielmo](https://github.com/googlielmo) a.k.a. `gwz`
