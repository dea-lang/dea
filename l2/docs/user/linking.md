# Linking External Native Libraries

Version: 2026-10-29

L2 can combine separately compiled Dea modules, caller-asserted native objects, and external host libraries in
`--build`, `--run`, and standalone `--link` mode. This is an explicit command-line contract: L2 does not yet have a
package manifest or per-module declaration for host-library dependencies.

## Current Binding Model

The current source-level bridge is the legacy unmangled `extern func` declaration. For example, a C library that exports
this function:

```c
#include <stdint.h>

int32_t acme_answer(void);
```

can be declared in L2 as:

```l2
extern func acme_answer() -> int;
```

The declaration must match the real C ABI. L2 does not inspect a header, generate a binding, or verify the native
symbol. Keep conversions and complex ABI details in a small C shim when the direct L2/C type correspondence is not
obvious. Broader first-class C interoperability is deferred L2 design work; additional `extern "C"` syntax and dedicated
C-string types have not been adopted. See [l2/docs/roadmap.md](../roadmap.md).

## Build, Run, and Standalone Link

Use `-L` to add a library search directory and `-l` to select a library:

```sh
l2c --build app.main -L /opt/acme/lib -l acme
l2c --run app.main -L/opt/acme/lib -lacme -- program-argument
```

When the binding needs a separately compiled C shim, pass its relocatable object through the typed foreign-object
surface:

```sh
l2c --build app.main --foreign-object build/acme_shim.o -L vendor/lib -l acme
```

Standalone link consumes Dea `.o + .l2m` pairs produced by compile-only mode and accepts the same external inputs:

```sh
l2c --compile app.main -o build/main.o
l2c --link build/main.o --foreign-object build/acme_shim.o \
    -L vendor/lib -l acme -o build/app
```

Standalone link registers explicit Dea objects first, then discovers missing Dea providers through ordered `-I`
interface roots and bundled managed interfaces. It never compiles caller source dependencies. Bundled native support is
prepared on demand, while external libraries and foreign objects remain explicit inputs. See
[l2/docs/reference/stdlib-preparation.md](../reference/stdlib-preparation.md) for preparation controls.

The driver keeps one encounter-ordered stream containing Dea objects, foreign objects, libraries, search paths, rpaths,
and raw arguments. In build/run, the source target expands into its dependency-ordered Dea object set at that position.
This matters for static libraries and other order-sensitive toolchains, so place each `-l` where the host link requires
it instead of assuming that L2 will regroup options by category.

## Runtime Search Paths

`-L` affects link-time discovery. It does not tell a produced executable where to find a shared library at load time. On
a non-Windows host, use `--rpath` / `-Rr` for that separate purpose:

```sh
l2c --build app.main -L vendor/lib -l acme --rpath '$ORIGIN/../lib'
l2c --build app.main -L vendor/lib -l acme -Rr='@loader_path/../lib'
```

L2 lowers rpaths for recognized GCC and Clang driver names, the exact `cc` driver, and TinyCC. GCC/Clang/`cc` forwarding
preserves commas inside the one rpath value; TinyCC's supported driver form cannot, so a comma-containing TinyCC rpath
reports `L2C-2072`. Unknown compiler families and Windows likewise reject rpaths instead of guessing a spelling. Windows
DLL lookup has different deployment rules and no equivalent rpath in this interface.

## Raw Driver Arguments

`--link-arg` / `-Cl` appends exactly one intact host compiler-driver argument at its encounter position:

```sh
l2c --build app.main --link-arg=-Wl,--as-needed -l acme
```

L2 does not automatically wrap the word in `-Wl,` or otherwise reinterpret it as a native-linker option. Repeat the
option when the compiler driver needs multiple words.

The raw-word escape hatch is deliberately bounded so native object roles remain visible:

- an object-suffixed `-l` value, raw word, or `-Wl,` payload segment is rejected; use a positional Dea `.o` with its
  sibling `.l2m`, or `--foreign-object` for a caller-asserted native relocatable
- response-file, object-file-list, and driver-config indirection such as `@arguments.rsp`, `-Wl,@arguments.rsp`, Darwin
  `-filelist`, Clang `--config`, or GCC `-specs` is rejected

These checks are intentionally syntactic and compiler-family-independent. An option or payload that happens to end in
`.o` / `.obj`, or an `@...` payload token that a particular linker gives another meaning, may therefore be unavailable
through `--link-arg`; use a different output suffix or configure that specialized host invocation outside L2.

Archive and shared-library words ending in `.a`, `.so`, `.dylib`, `.lib`, or `.dll` pass raw validation, but the
selected host compiler driver still decides whether that file is a meaningful link input. Prefer `-l` / `-L` for
ordinary named library selection.

## Platform and Trust Boundary

- Positional standalone-link Dea inputs use the exact `.o` suffix because the sibling `.l2m` path is derived from it.
- `--foreign-object` accepts a regular host-compatible relocatable path, commonly `.o` on Unix-like systems or `.obj` on
  Windows. L2 trusts the caller's classification and does not inspect the object format or symbol table.
- Unix-like static and shared libraries commonly use `.a`, `.so`, or `.dylib`. Windows normally links a DLL through its
  `.lib` import library; passing the `.dll` itself depends on the host driver and is not made portable by L2. MinGW-like
  drivers can use canonical `-l` / `-L`; the MSVC driver family rejects those GNU-style controls, so pass an explicit
  accepted `.lib` as a raw driver word or configure the host invocation outside L2.
- On native Windows, `%`, `!`, literal `"`, carriage returns, and line feeds are rejected in build/run external-link
  values with `L2C-2106` before source compilation, and exact command/capture values are checked again before host
  execution. This is required by the current `cmd.exe` transport.
- Native bytes remain opaque. Embedded linker controls, architecture compatibility, duplicate symbols, missing symbols,
  and loader deployment are host-toolchain concerns reported by the final link.

The L2 runtime is different from user libraries: after the complete ordered user stream, the driver appends the already
validated runtime archive or TinyCC object set by exact path. User `-L` entries therefore cannot shadow the selected Dea
runtime.

For the verified Dea object/interface contract and final command lifecycle, see
[Separate Compilation and Linking](../reference/separate-compilation.md).
