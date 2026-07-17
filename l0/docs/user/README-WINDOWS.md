# The Dea Programming Language.

> _C-family syntax, UB-free semantics, ARC strings, sum types and pattern matching._

Welcome to the **Dea** programming language!

## Dea/L<sub>0</sub> on Windows

The validated Windows workflow for this Dea/L0 compiler distribution requires a supported backend C toolchain:

- **MSYS2** `UCRT64`: install MSYS2 from https://www.msys2.org/. `MINGW64` is supported as an alternate environment.
- **MinGW-w64 GCC** (or **Clang**): in `UCRT64`, install `mingw-w64-ucrt-x86_64-gcc` or `mingw-w64-ucrt-x86_64-clang`
  from the MSYS2 package manager.
- **GNU Make**: install the `make` package from the MSYS2 package manager.
- **System PATH**: `l0-env.cmd` auto-detects the MSYS2 install and puts `ucrt64/bin/` or `mingw64/bin/` on `PATH`. Set
  `MSYS2_TOOLCHAIN_BIN` to force a toolchain `bin` directory, or set `MSYS2_ROOT` if MSYS2 is not in the default
  location.

Install the recommended `UCRT64` toolchain packages with:

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc make diffutils
# or use Clang instead: pacman -S mingw-w64-ucrt-x86_64-clang make diffutils
```

For `MINGW64`, use the matching package family:

```bash
pacman -S mingw-w64-x86_64-gcc make diffutils
# or use Clang instead: pacman -S mingw-w64-x86_64-clang make diffutils
```

Native `cmd.exe` launchers are supported. MSYS2 `UCRT64` or `MINGW64` is required as the Dea compiler's `--build` and
`--run` workflows depend on a supported Windows C toolchain.

## Using the shipped archive

After extracting the archive, the Windows launchers live under `bin/`.

### From `cmd.exe`

```cmd
call bin\l0-env.cmd
l0c --version
```

`l0-env.cmd` automatically puts MSYS2 `ucrt64\bin` or `mingw64\bin` on `PATH` so that the C compiler (GCC or Clang) and
its support DLLs are visible. It probes `%MSYS2_TOOLCHAIN_BIN%`, `%MSYS2_ROOT%`, the Windows registry, and the default
`C:\msys64` path, preferring `UCRT64` before `MINGW64`. These native launchers work without opening the MSYS2 shell
first.

## Trying the bundled examples

```cmd
call bin\l0-env.cmd
l0c -Rp examples --run hello
```

The shipped examples live under `examples/`, and the bundled reference docs live under `docs/reference/`.
