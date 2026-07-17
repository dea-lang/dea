# Dea Compiler CLI Contract

Version: 2026-07-16

This document defines the shared command-line contract for Dea compilers. It covers behavior common to the current L0
Stage 1, L0 Stage 2, and L1 Stage 1 implementations. A level may add a documented mode or option without changing the
meaning of the shared surface.

Canonical level-specific detail:

- [l0/docs/specs/compiler/cli-contract.md](../../../l0/docs/specs/compiler/cli-contract.md): complete L0 Stage 1/Stage 2
  contract
- [l1/docs/project-status.md](../../../l1/docs/project-status.md): current L1 bootstrap scope and delivery status
- [docs/specs/compiler/diagnostic-code-catalog.md](diagnostic-code-catalog.md): shared CLI and compiler diagnostic codes

## 1. Operating Model

- Modes are selected with flags. At most one primary mode may be selected.
- `--build` is the default when no primary mode is given.
- Exactly one source target is required, except that `--help` and `--version` short-circuit target validation.
- Runtime arguments for `--run` follow a `--` separator. The separator is invalid in other modes.
- CLI argument errors exit with status 2; analysis or compilation failures exit with status 1; successful operations
  exit with status 0. `--run` forwards the child program's exit status.

## 2. Shared Modes

| Mode        | Aliases            | Purpose                                      |
| ----------- | ------------------ | -------------------------------------------- |
| `--run`     | `-r`               | Build and run one source target              |
| `--build`   |                    | Build one executable                         |
| `--compile` | `-c`               | Compile without linking (currently reserved) |
| `--gen`     | `-Gc`, `--codegen` | Emit generated C                             |
| `--check`   | `--analyze`        | Parse and analyze                            |
| `--tok`     | `--tokens`         | Dump lexer tokens                            |
| `--ast`     |                    | Dump the parsed AST                          |
| `--sym`     | `--symbols`        | Dump module-level symbols                    |
| `--type`    | `--types`          | Dump resolved top-level types                |

The dump modes are developer-facing; their text formats are not stable interfaces. All current compilers recognize
`--compile` / `-c` and report the level-specific `L0C-9510` or `L1C-9510` without analysis or artifact production.
Compile-only output remains future work. L1 Stage 1 additionally implements `--emit-interface`, which emits the target
module's textual `.l1m` interface.

## 3. Shared Options

The current shared option surface is:

- `--help` / `-h`, `--version`, counted `--verbose` / `-v`, and `--log` / `-Vl`
- repeatable project and system roots through `--project-root` / `-Rp` and `--sys-root` / `-Rs`
- repeatable compile-mode interface paths through `--interface-path` / `-I`; paths are stored in declaration order but
  are not consumed until compile-only artifact production lands
- `--output` / `-o` for artifact-producing modes; L1 also accepts it with `--emit-interface`
- `--c-compiler` / `-Cc`, `--c-options` / `-Co`, `--runtime-include` / `-Ri`, and `--runtime-lib` / `-Rl` for build/run
- `--no-line-directives` / `-NLD`, `--trace-arc`, and `--trace-memory` for generated-C modes
- `--keep-c` for build/run
- `--all-modules` / `-a` for token, AST, symbol, and type dumps
- `--include-eof` for token dumps

Using a mode-scoped option with an incompatible mode is a CLI argument error. In particular, interface paths are valid
only with `--compile` and produce `L0C-2031` or `L1C-2031` elsewhere.

The conventional driver spellings `-g`, `-S`, `-L`, and `-l` are reserved for debug information, assembly output,
external-library search, and external-library selection respectively. Those capabilities are not implemented yet;
syntactically complete uses produce `L0C-2032` or `L1C-2032`. `-L` and `-l` accept either an attached value or a
following value when their implementations land.

Multi-letter short options are exact, case-sensitive tokens. Value-taking namespaced options accept a following value or
`=VALUE`, but not an attached suffix. Canonical `-I`, `-L`, and `-l` accept directly attached or following values; their
`-I=...`, `-L=...`, and `-l=...` forms are invalid. Only the counted `-vv...` form is a short-option cluster; other
clusters are invalid. Bare namespace prefixes such as `-C`, `-R`, and `-V` are not options.

## 4. Level-Scoped Environment

Each compiler uses its level prefix for environment-backed defaults:

| Purpose              | L0                   | L1                   |
| -------------------- | -------------------- | -------------------- |
| Compiler home        | `L0_HOME`            | `L1_HOME`            |
| System/stdlib roots  | `L0_SYSTEM`          | `L1_SYSTEM`          |
| C compiler           | `L0_CC`              | `L1_CC`              |
| C compiler options   | `L0_CFLAGS`          | `L1_CFLAGS`          |
| Runtime include path | `L0_RUNTIME_INCLUDE` | `L1_RUNTIME_INCLUDE` |
| Runtime library path | `L0_RUNTIME_LIB`     | `L1_RUNTIME_LIB`     |

The level-specific C compiler variable has highest precedence. Automatic detection then tries `tcc`, `gcc`, `clang`, and
`cc` from `PATH`, followed by `$CC`. C options from the level-specific environment variable are placed before options
supplied through `--c-options`.

## 5. Target and Source-Path Rules

- Absolute targets and targets containing a path separator are treated as file paths.
- Relative targets beginning with `.` or `..` resolve from the current directory.
- Dotted module names map to source-tree path components and search system roots before project roots.
- A plain filename or module name resolves using the active level's source extension (`.l0` or `.l1`).
- Repeated system or project roots preserve declaration order within their root group.

## 6. Compatibility Rule

Equivalent behavior keeps the same flag names, aliases, option ordering, exit-code meanings, and diagnostic meanings
across stages and levels. A level may recognize a shared spelling while reporting that its capability is unavailable,
but it must not reinterpret that spelling. A level-specific extension must be documented in the shared contract and in
its owning level's live docs before it is treated as public behavior.
