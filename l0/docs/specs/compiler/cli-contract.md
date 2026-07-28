# L0 Compiler CLI Contract

Version: 2026-07-28

This document is the normative shared CLI contract for the L0 compiler across Stage 1 and Stage 2. Stage-specific
differences are called out explicitly in [Section 9](#9-stage-specific-differences).

Canonical ownership:

- Dea-wide shared CLI contract: [docs/specs/compiler/cli-contract.md](../../../../docs/specs/compiler/cli-contract.md)
- Stage 1-specific guarantees: [stage1-contract.md](stage1-contract.md)
- Stage 2-specific guarantees: [stage2-contract.md](stage2-contract.md)
- Architecture and pass flow: [reference/architecture.md](../../reference/architecture.md)
- Trace flags and runtime trace behavior: [specs/runtime/trace.md](../runtime/trace.md)

## 1. Mode Flags

The compiler accepts exactly one primary mode flag per invocation. When no mode flag is given, `--build` is the default.

Primary mode flags:

- `--run` (short: `-r`)
- `--build` (default mode when omitted)
- `--compile` (short: `-c`; reserved and currently reports `L0C-9510` without producing artifacts)
- `--gen` (short: `-Gc`; alias flag: `--codegen`)
- `--check` (alias flag: `--analyze`)
- `--tok` (alias flag: `--tokens`)
- `--ast`
- `--sym` (alias flag: `--symbols`)
- `--type` (alias flag: `--types`)

Mode selection uses flags only.

`--tok`, `--ast`, `--sym`, and `--type` are developer-facing diagnostic modes; their output format is not guaranteed
stable.

## 2. Global Options

Global options are accepted with any mode:

- `--help` / `-h`
- `--version` / `-V`
- `-v` / `--verbose` (counted; `-v` = info, `-vv` currently equivalent to `-v`, `-vvv` = debug)
- `-Vl` / `--log`
- `-Rp` / `--project-root`
- `-Rs` / `--sys-root`

`--help` and `--version` / `-V` short-circuit all other parsing and validation; remaining flags are ignored when either
is present.

## 3. Mode-Scoped Options

The following options are enforced by CLI argument validation and are only accepted with the specified modes:

| Option                          | Valid modes                 |
| ------------------------------- | --------------------------- |
| `-o` / `--output`               | `build`, `gen`, `run`       |
| `-Gk` / `--keep-c`              | `build`, `run`              |
| `-I` / `--interface-path`       | `compile`                   |
| `-Cc` / `--c-compiler`          | `build`, `run`              |
| `-Co` / `--c-options`           | `build`, `run`              |
| `-Ri` / `--runtime-include`     | `build`, `run`              |
| `-Rl` / `--runtime-lib`         | `build`, `run`              |
| `-NLD` / `--no-line-directives` | `build`, `run`, `gen`       |
| `-Va` / `--trace-arc`           | `build`, `run`, `gen`       |
| `-Vm` / `--trace-memory`        | `build`, `run`, `gen`       |
| `-Su` / `--unchecked`           | `build`, `run`, `gen`       |
| `-Sb` / `--check-basic`         | `build`, `run`, `gen`       |
| `--all-modules` / `-a`          | `tok`, `ast`, `sym`, `type` |
| `--include-eof`                 | `tok`                       |

Using a mode-scoped option with an incompatible mode is currently a fatal CLI error (exit code 2). This policy may be
relaxed in a future revision.

`--unchecked` disables runtime pointer validation: L0 emits `L0_RT_UNCHECKED` into the generated C prelude, and L1
additionally selects the unchecked runtime archive. Combining `--unchecked` with `--trace-arc` or `--trace-memory` is a
fatal CLI error (exit code 2); traced builds assert checked-runtime invariants.

`--check-basic` selects the basic checked runtime mode: L0 emits `L0_RT_CHECK_BASIC` into the generated C prelude, and
L1 additionally selects the `libdea_rt_check_basic.a` archive. It is mutually exclusive with `--unchecked`,
`--trace-arc`, and `--trace-memory`.

C compiler flags are merged as: `$L0_CFLAGS` first, then `--c-options`.

`--runtime-lib` / `$L0_RUNTIME_LIB` provide an additional runtime library search directory for build/run. When supplied,
the path must exist and be a directory.

Interface paths are repeatable, preserve declaration order, and are accepted only with `--compile`. The current compile
command reports `L0C-9510` before analysis or artifact creation, so the paths are recorded but not searched and their
directories are not validated yet.

`-g`, `-S`, `-L`, and `-l` are recognized as reserved canonical driver syntax for debug information, assembly output,
external-library search, and external-library selection. Syntactically complete uses report `L0C-2032`; those
capabilities are not implemented in L0. `-L` and `-l` accept either attached or following values at the syntax layer.

Namespaced short options are exact, case-sensitive tokens. Their values use a following token or `=VALUE`, not an
attached suffix. `-I`, `-L`, and `-l` accept directly attached and following values, but their `=VALUE` spellings are
invalid. `-V` is explicitly assigned to version. Only `-vv...` is a valid short-option cluster.

## 4. Target and Separator Rules

- Exactly one target is required per invocation. Omitting the target or providing multiple targets is a fatal CLI error
  (exit code 2).
- Runtime program arguments for `--run` must follow a `--` separator:
  ```
  l0c --run entry.module -- arg1 arg2
  ```
  Positional arguments after the target without `--` are a fatal CLI error when `--run` is active.
- The `--` separator is only valid with `--run`. Using `--` with any other mode is a fatal CLI error (exit code 2).

## 5. Target Normalization

The compiler resolves a target to a source file using the following rules, applied in order:

1. **Absolute path or path with directory separator (`/` or `\`):** treated as a filesystem path directly. The project
   root is derived as the parent directory of the resolved `.l0` file.
2. **Relative path with `.` or `..` prefix:** resolved relative to the current working directory.
3. **Dotted module name (e.g. `std.io`):** mapped to path segments (`std/io.l0`) and searched under each system root,
   then each project root, preserving declaration order within each root group.
4. **Plain name with `.l0` extension (e.g. `hello.l0`):** resolved relative to the project root(s).
5. **Plain name without extension:** resolved as `<name>.l0` under project root(s).

A target containing a path separator always bypasses the module-name search path.

## 6. Search-Path and Root Defaults

- **Project root (`-Rp`):** defaults to the current working directory when not specified.
- **System root (`-Rs`):** defaults to `$L0_SYSTEM` when set; otherwise derived from `$L0_HOME` as
  `$L0_HOME/shared/l0/stdlib`.
- **Search order:** system root(s) are searched before project root(s).
- Multiple `-Rp` and `-Rs` values accumulate; search is in declaration order within each group.

Environment variables that affect root and path derivation:

| Variable             | Effect                                                                          |
| -------------------- | ------------------------------------------------------------------------------- |
| `L0_HOME`            | Repo or install root; launcher derives stdlib and runtime include paths from it |
| `L0_SYSTEM`          | Override for the stdlib system root                                             |
| `L0_RUNTIME_INCLUDE` | Default runtime header include path; overridden (not extended) by `-Ri`         |
| `L0_CFLAGS`          | Prepended to C compiler flags before `--c-options`                              |

`L0_HOME` is derived by the launcher from the install prefix or repository root and is normally set automatically;
callers do not need to set it explicitly when using the `l0c` launcher.

## 7. Compiler Identity, Help, and Version

### 7.1 `--help`

`--help` (or `-h`) prints usage to stdout and exits 0. The help text begins with the compiler identity string (see
[Section 7.4](#74-identity-strings)) and includes a description of the `--version` option.

No output is written to stderr on a clean `--help` invocation.

### 7.2 `--version`

`--version` prints compiler identity information to stdout and exits 0. No output is written to stderr.

The minimum shared output is the identity string on its own line. Stage 2 repo-local and install-prefix artifacts
include additional provenance fields (see [Section 9.2](#92-stage-2)).

### 7.3 `-v` verbose identity

When `-v` is active (any mode), the compiler identity string is included in info-level stderr output early in the
invocation, including on CLI usage failures where the identity is known before argument validation fails.

### 7.4 Identity strings

| Stage   | Identity string                        |
| ------- | -------------------------------------- |
| Stage 1 | `Dea language / L0 compiler (Stage 1)` |
| Stage 2 | `Dea language / L0 compiler`           |

## 8. Exit Codes

| Condition                       | Exit code                    |
| ------------------------------- | ---------------------------- |
| Success                         | 0                            |
| CLI argument error              | 2                            |
| Analysis or compilation failure | 1                            |
| `--run`: program exit code      | forwarded from child process |
| `--run`: interrupted            | OS-defined (POSIX: 130)      |
| `--help`, `--version`           | 0                            |

The exit code for an interrupted run is OS-defined. On POSIX, the convention is 128 + signal number (SIGINT = 2, so
130); on Windows this convention does not apply.

## 9. Stage-Specific Differences

### 9.1 Stage 1

Stage 1 CLI details that are not part of the shared contract are documented in [stage1-contract.md](stage1-contract.md),
including token-dump and debug-dump option semantics, Python-level driver invocation, and source/module encoding
contracts.

### 9.2 Stage 2

Stage 2 CLI details that are not part of the shared contract are documented in [stage2-contract.md](stage2-contract.md),
including `--version` provenance field formats, fallback behavior, and stability guarantees.
