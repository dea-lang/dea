# Linking External Native Libraries

Version: 2026-08-30

L1 Stage 1 can combine separately compiled Dea modules, caller-asserted native objects, and external host libraries in
`--build`, `--run`, and standalone `--link` mode. This is an explicit command-line contract: L1 does not yet have a
package manifest or per-module declaration for host-library dependencies.

## Current Binding Model

The current source-level bridge is the legacy unmangled `extern func` declaration. For example, a C library that exports
this function:

```c
#include <stdint.h>

int32_t acme_answer(void);
```

can be declared in L1 as:

```l1
extern func acme_answer() -> int;
```

The declaration must match the real C ABI. L1 does not inspect a header, generate a binding, or verify the native
symbol. Keep conversions and complex ABI details in a small C shim when the direct L1/C type correspondence is not
obvious. The planned `extern "C"` and C-string language surface belongs to
[Initiative 0003](../../work/initiatives/0003-c-ffi.md); it is not part of the current linking feature.

## Build, Run, and Standalone Link

Use `-L` to add a library search directory and `-l` to select a library:

```sh
l1c --build app.main -L /opt/acme/lib -l acme
l1c --run app.main -L/opt/acme/lib -lacme -- program-argument
```

When the binding needs a separately compiled C shim, pass its relocatable object through the typed foreign-object
surface:

```sh
l1c --build app.main --foreign-object build/acme_shim.o -L vendor/lib -l acme
```

Standalone link consumes Dea `.o + .l1m` pairs produced by compile-only mode and accepts the same external inputs:

```sh
l1c --compile app.main -o build/main.o
l1c --link build/main.o --foreign-object build/acme_shim.o \
    -L vendor/lib -l acme -o build/app
```

The driver keeps one encounter-ordered stream containing Dea objects, foreign objects, libraries, search paths, rpaths,
and raw arguments. In build/run, the source target expands into its dependency-ordered Dea object set at that position.
This matters for static libraries and other order-sensitive toolchains, so place each `-l` where the host link requires
it instead of assuming that L1 will regroup options by category.

## Runtime Search Paths

`-L` affects link-time discovery. It does not tell a produced executable where to find a shared library at load time. On
a non-Windows host, use `--rpath` / `-Rr` for that separate purpose:

```sh
l1c --build app.main -L vendor/lib -l acme --rpath '$ORIGIN/../lib'
l1c --build app.main -L vendor/lib -l acme -Rr='@loader_path/../lib'
```

L1 lowers rpaths for recognized GCC and Clang driver names, the exact `cc` driver, and TinyCC. GCC/Clang/`cc` forwarding
preserves commas inside the one rpath value; TinyCC's supported driver form cannot, so a comma-containing TinyCC rpath
reports `L1C-2072`. Unknown compiler families and Windows likewise reject rpaths instead of guessing a spelling. Windows
DLL lookup has different deployment rules and no equivalent rpath in this interface.

## Raw Driver Arguments

`--link-arg` / `-Cl` appends exactly one intact host compiler-driver argument at its encounter position:

```sh
l1c --build app.main --link-arg=-Wl,--as-needed -l acme
```

L1 does not automatically wrap the word in `-Wl,` or otherwise reinterpret it as a native-linker option. Repeat the
option when the compiler driver needs multiple words.

The raw-word escape hatch is deliberately bounded so native object roles remain visible:

- an object-suffixed `-l` value, raw word, or `-Wl,` payload segment is rejected; use a positional Dea `.o` with its
  sibling `.l1m`, or `--foreign-object` for a caller-asserted native relocatable
- response-file, object-file-list, and driver-config indirection such as `@arguments.rsp`, `-Wl,@arguments.rsp`, Darwin
  `-filelist`, Clang `--config`, or GCC `-specs` is rejected

These checks are intentionally syntactic and compiler-family-independent. An option or payload that happens to end in
`.o` / `.obj`, or an `@...` payload token that a particular linker gives another meaning, may therefore be unavailable
through `--link-arg`; use a different output suffix or configure that specialized host invocation outside L1.

Archive and shared-library words ending in `.a`, `.so`, `.dylib`, `.lib`, or `.dll` pass raw validation, but the
selected host compiler driver still decides whether that file is a meaningful link input. Prefer `-l` / `-L` for
ordinary named library selection.

## Platform and Trust Boundary

- Positional standalone-link Dea inputs use the exact `.o` suffix because the sibling `.l1m` path is derived from it.
- `--foreign-object` accepts a regular host-compatible relocatable path, commonly `.o` on Unix-like systems or `.obj` on
  Windows. L1 trusts the caller's classification and does not inspect the object format or symbol table.
- Unix-like static and shared libraries commonly use `.a`, `.so`, or `.dylib`. Windows normally links a DLL through its
  `.lib` import library; passing the `.dll` itself depends on the host driver and is not made portable by L1. MinGW-like
  drivers can use canonical `-l` / `-L`; the MSVC driver family rejects those GNU-style controls, so pass an explicit
  accepted `.lib` as a raw driver word or configure the host invocation outside L1.
- On native Windows, `%`, `!`, literal `"`, carriage returns, and line feeds are rejected in build/run external-link
  values with `L1C-2106` before source compilation, and exact command/capture values are checked again before host
  execution. This is required by the current `cmd.exe` transport.
- Native bytes remain opaque. Embedded linker controls, architecture compatibility, duplicate symbols, missing symbols,
  and loader deployment are host-toolchain concerns reported by the final link.

The L1 runtime is different from user libraries: after the complete ordered user stream, the driver appends the already
validated runtime archive or TinyCC object set by exact path. User `-L` entries therefore cannot shadow the selected Dea
runtime.

For the verified Dea object/interface contract and final command lifecycle, see
[Separate Compilation and Linking](../reference/separate-compilation.md).
