# L1 Explicit Profile Artifacts

Version: 2026-10-19

An explicit profile supplies one complete native configuration: bundled `.l1m + .o` providers, copied public headers and
one runtime variant. The caller owns its directory and external toolchain stability. Creation and selection are
independent of managed cache lookup, keys, freshness observations, locks and memos.

## Commands and configuration

```sh
l1c --create-profile --c-compiler clang --check-basic -o build/profile
l1c --compile pkg.util --project-root src --profile build/profile -I build/modules -o build/modules/pkg/util.o
l1c --compile app --project-root src --profile build/profile -I build/modules -o build/modules/app.o
l1c --link build/modules/app.o -I build/modules --profile build/profile -o build/app
l1c --build app --project-root src --profile build/profile -o build/app-direct
l1c --run app --project-root src --profile build/profile
```

Compile imported application providers in dependency order. The compiler still verifies interface fingerprints, graph
requirements, entry selection and lifecycle order. A script choosing that order is not a dependency scanner.

`--create-profile` accepts no target and requires exactly one nonempty output. It accepts the preparation compiler, C
options, public-header override and generated-C/runtime checking controls. It rejects source/project/interface roots,
runtime-library replacement, link operands, program arguments, `--profile`, cache controls, `--no-auto-prepare`,
`--force` and `--keep-c`. Construction requires an invocable supported compiler, not persistent reuse eligibility.

`--profile PATH` is valid only for compile, link, build and run. Relative paths resolve from the invocation directory.
Selection uses exactly that artifact or fails, without repair or fallback. The profile restores its absolute compiler,
ordered generated-C options and codegen/runtime settings, ignoring ambient `L1_CC`, `L1_CFLAGS`, `L1_SYSTEM`,
`L1_RUNTIME_INCLUDE`, `L1_RUNTIME_LIB`, runtime lookup under `L1_BUILD_DIR` and cache variables. Explicit conflicting
settings fail before compilation. Redundant explicit settings must normalize to the recorded configuration.

Explicit `--sys-root`, `--runtime-include`, `--runtime-lib`, `--no-managed-stdlib` and `--stdlib-cache` are incompatible
with selection. `--no-auto-prepare` is redundant in build/run/link and remains invalid in compile-only mode. Project
sources and explicit `-I` retain their existing precedence. The profile inventory supplies the bundled tier without
probing the original bundled sources. Missing providers fail instead of falling back.

CLI misuse exits 2; construction, validation and publication failures exit 1; success exits 0. Progress and native
diagnostics use stderr. Ordinary commands without a selector retain the managed behavior documented in
[l1/docs/reference/stdlib-preparation.md][preparation].

## Versioned manifest

The completion marker is `profile.json`. Schema 1 requires these fields:

| Field           | Meaning                                                                                                                                                              |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema`        | Integer `1`, the serialization format.                                                                                                                               |
| `kind`          | String `l1-explicit-profile`.                                                                                                                                        |
| `contract`      | Integer `1`, the supported Dea compilation protocol.                                                                                                                 |
| `producer`      | Object with `name: "l1c"`, `language: "L1"`; optional `compiler_description` is provenance.                                                                          |
| `configuration` | Absolute `compiler`, `family` (`gcc`, `clang`, `tcc`), ordered `options` and separate `runtime_options`, `runtime_configuration_isolation`, `variant` and `codegen`. |
| `include`       | Relative copied public-header root, `include`.                                                                                                                       |
| `modules`       | Object mapping declared module names to canonical relative interface paths such as `modules/std/io.l1m`.                                                             |
| `runtime`       | Ordered relative runtime payload paths: one archive, or the constructor's selected TinyCC object set.                                                                |
| `payloads`      | Array of `{path, role, size, sha256}` records covering interfaces, objects, runtime inputs and public headers.                                                       |

Codegen fields are numeric booleans (`0` or `1`): `no_line_directives`, `trace_arc`, `trace_memory`, `unchecked`,
`check_basic`. Runtime variants are `default`, `check_basic`, `unchecked` and `traced`. Both tracing controls select the
traced runtime while preserving their distinct generated-C instrumentation. Generated bundled C and application C use
the recorded effective generated-C options. Runtime implementation C retains its separate compiler-owned policy.

Limits are 16 MiB per manifest, 4096 modules, 16384 payloads, 4096 words per native argv and 32768 bytes per word. The
existing JSON reader also bounds nesting and total nodes. Duplicate or malformed inventory entries, escaping paths,
undeclared files/directories, aliases and missing required contents are errors. Objects stay beside their authoritative
interfaces. Public headers are byte copies, including the complete dependency tree needed by generated C and wrappers.
Construction scratch is not consumption authority.

The maintained compilation-contract constant must change whenever an incompatible interface encoding or fingerprint
rule, generated native calling/data layout, public header/runtime protocol, symbol/lifecycle convention or wrapper
protocol makes prior profiles unsuitable. Compatible implementation changes do not require a bump. Consumers reject
unsupported contract versions before host work. Schema changes independently version the reader representation. Neither
version authenticates a native ABI or substitutes for `.l1m` semantic verification.

## Native option paths and external stability

Creation normalizes recognized include, sysroot, toolchain and native search path arguments to absolute external paths.
That preserves their meaning after a cwd change or profile movement. Response files (`@...`), explicit compiler
configuration files, selected implicit compiler configuration files and opaque forwarding options are rejected in this
initial format rather than stored with an ambiguous directory assumption. Unsupported path-bearing forms must be
expressed using supported direct options. The stored argv is data and is never evaluated as shell source.

Supported path spellings include paired or attached `-I`, `-L`, `-B`, `-F`; paired `-isystem`, `-iquote`, `-idirafter`,
`-include`, `-imacros`, `-iframework`, `-isysroot`, `-resource-dir`; and paired or `=PATH` forms of `--sysroot` and
`--gcc-toolchain`. Sysroot placeholders beginning with `=` or `$SYSROOT`, joined multi-letter short path options,
dependency/output controls (`-M*`, `-o*`, working-directory, dump/auxiliary paths and save-temps) are rejected.
Recognized non-path assignments include language standard, explicit target/architecture/CPU/ABI and the
floating-point/visibility controls accepted by the native policy. Other assignment options, plugins, profile-guided
input files and opaque `-X*`, `-Wl,`, `-Wa,` or `-Wp,` forwarding are rejected. Existing floating-point contract checks
still apply.

Absolute references remain external dependencies. The caller keeps the compiler executable, SDK, environment and
referenced native inputs suitable and stable, then creates a new profile when those assumptions change. Selection does
not observe current compiler/DLL identity or promise automatic freshness. An absolute executable path prevents
accidental PATH reselection; it cannot freeze the executable or loader dependencies.

## Ownership and validation

Creation rejects an existing output or unsafe overlap before mutation, including overlap with selected external native
input paths. Selecting an external root such as `/` therefore leaves no nonoverlapping output destination. It constructs
in an exclusively created sibling staging directory, validates the complete inventory, writes completion metadata last
and publishes to an absent output. The parent is trusted and callers externally serialize same-destination writes. This
contract does not promise hostile parent safety, crash durability or atomic replacement. Cleanup removes only registered
owned contents; unexpected files or cleanup failures preserve evidence and report the staging location. `--force` never
overrides explicit ownership.

Consumers read the selected directory without writing it. Output destinations, retained-C roots and temporary allocation
parents that overlap the selected profile are rejected. A profile may be moved or copied on the same host while the
selected external toolchain remains suitable; the creating cache and original bundled source/interface/header roots are
unnecessary. Cross-host distribution, arbitrary compiler ABI compatibility and toolchain relocation are outside this
contract.

Consumption validates the manifest, configuration and inventory before native work, then hashes the bytes it uses.
Compile-only verifies interfaces and public headers without requiring unused native provider objects. Native consumers
also verify provider objects and runtime support. No persistent validation memo is created. Retained C covers only
modules and wrappers generated by that invocation; prebuilt profile providers are not regenerated.

Digests detect damage relative to a trusted manifest. They do not authenticate an untrusted profile, inspect native
symbols or establish agreement between opaque objects and semantic interfaces. The boundary remains
[l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md][native-adr].

[native-adr]: ../decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md
[preparation]: stdlib-preparation.md
