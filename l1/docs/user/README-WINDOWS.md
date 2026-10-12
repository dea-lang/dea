# Dea/L1 on Windows

This guide covers setup and commands for the Windows x86_64 package. Use [README.md][readme] for the language
introduction, a program to write yourself, package contents, and offline references.

## Prerequisites

The Windows package targets **MSYS2 UCRT64**. Install [MSYS2](https://www.msys2.org/), then open its **UCRT64** shell
and install GCC:

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc
```

The installed compiler needs no L0, Python, Make, or source checkout. Native compilation and standard-library/runtime
preparation require the UCRT64 C compiler, linker, and host tools. The compiler itself also needs UCRT64 runtime DLLs,
including `libwinpthread-1.dll`, for semantic-only commands such as `--check` and `--gen`. Keep the UCRT64 `bin`
directory on `PATH` even when no C compilation is needed.

## First run in Command Prompt

Open Command Prompt (`cmd.exe`). Replace `C:\path\to\dea-l1` with the extracted package directory:

```cmd
cd /d "C:\path\to\dea-l1"
call bin\l1-env.cmd
l1c --version
l1c --check share\dea\l1\smoke\hello.l1
l1c --run share\dea\l1\smoke\hello.l1
```

Activation selects this package in the current shell and discovers MSYS2 to add the toolchain to `PATH`. `--check`
analyzes the program; `--run` builds and executes it. The smoke program prints:

```text
hello from Dea L1
```

To keep an executable, run from a writable package directory:

```cmd
l1c --build share\dea\l1\smoke\hello.l1 -o hello.exe
.\hello.exe
```

If the package directory is read-only, choose a writable output path, such as `-o "C:\my project\hello.exe"`, and run
the executable from that location. Quote paths containing spaces.

### Selecting the UCRT64 toolchain

For a non-default MSYS2 installation, set `MSYS2_ROOT` before activation. To select the exact toolchain directory, set
`MSYS2_TOOLCHAIN_BIN` instead:

```cmd
set "MSYS2_TOOLCHAIN_BIN=D:\msys64\ucrt64\bin"
call bin\l1-env.cmd
```

Replace the example path with your installation's UCRT64 `bin` directory. `MSYS2_TOOLCHAIN_BIN` takes precedence over
root discovery. Set `L1_CC` if you need to select a particular compatible C compiler explicitly; that setting does not
replace the runtime DLL requirement.

When calling `l1c` from another batch script, use `call l1c.cmd ...` so control returns to that script. Direct
`bin\l1c.cmd` invocation also works without activation when the required native tools and DLLs are already on `PATH`.

## First run in the MSYS2 UCRT64 shell

Open the UCRT64 shell and replace `/c/path/to/dea-l1` with the package location in MSYS2 path syntax:

```bash
cd "/c/path/to/dea-l1"
source ./bin/l1-env.sh
l1c --version
l1c --check share/dea/l1/smoke/hello.l1
l1c --run share/dea/l1/smoke/hello.l1
```

The output is the same `hello from Dea L1` greeting. To keep and run an executable from a writable package directory:

```bash
l1c --build share/dea/l1/smoke/hello.l1 -o hello.exe
./hello.exe
```

Use forward-slash paths in these shell commands and quote paths containing spaces. The UCRT64 shell supplies the host
toolchain environment; sourcing `l1-env.sh` selects the Dea package within it.

## Your own program

Create the `hello.l1` program shown in [README.md][readme] in a writable project directory. Keep the activated shell
open, change to that directory, and use the commands for your shell.

In Command Prompt:

```cmd
l1c --check hello.l1
l1c --run hello.l1
l1c --build hello.l1 -o hello.exe
.\hello.exe
```

In the MSYS2 UCRT64 shell:

```bash
l1c --check hello.l1
l1c --run hello.l1
l1c --build hello.l1 -o hello.exe
./hello.exe
```

The program prints `Hello, L1!`. Use the `.exe` suffix when naming Windows executables.

## Cache and relocation

The first native build prepares matching support in a writable per-user cache and can take longer. The installed package
remains unchanged. For a custom cache, set `L1_STDLIB_CACHE` using `set "L1_STDLIB_CACHE=C:\path\to\cache"` in Command
Prompt, or `export L1_STDLIB_CACHE="C:/path/to/cache"` in the UCRT64 shell. You can also pass `--stdlib-cache` to an
individual compiler command.

Keep the entire package directory together when moving it, including hidden and metadata files. Activate it again from
the new location with `call bin\l1-env.cmd` in Command Prompt or `source ./bin/l1-env.sh` in the UCRT64 shell. A missing
UCRT64 DLL error indicates that the runtime is unavailable on `PATH`; check the toolchain setup and activate again.

See [share/doc/dea/l1/toolchain.md][toolchain] for preparation, cache reuse, and installation repair, and
[README.md][readme] for documentation and examples.

[readme]: README.md
[toolchain]: share/doc/dea/l1/toolchain.md
