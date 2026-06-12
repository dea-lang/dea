# Dea/L0 on Windows

This document is the Windows-specific addendum to [l0/README.md](README.md). It covers building, installing, and
developing the Dea/L0 compiler from the repository on Windows.

Run the commands in this document from the `l0/` directory unless noted otherwise.

For using a shipped Dea/L0 distribution archive on Windows (rather than the repository), see
[l0/docs/user/README-WINDOWS.md](docs/user/README-WINDOWS.md) instead.

- If you want to build, install, and use `l0c` on Windows, read the next section.
- If you are developing Dea/L0 itself, read the developer section after that.
- The rest is a technical addendum about generated launchers, shell behavior, and current Windows-specific caveats.

## How to build and use `l0c`

The recommended Windows path today is:

- MSYS2 `UCRT64`
- MinGW-w64 GCC or Clang
- GNU Make on `PATH`

MSYS2 `MINGW64` is supported as an alternate environment. MSVC-family builds remain outside the validated release
matrix. Native `cmd.exe` entrypoints are supported; the MSYS2 requirement comes from the supported backend C toolchain,
not from the `.cmd` launchers themselves.

Install the recommended `UCRT64` toolchain packages from MSYS2 with:

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-clang make diffutils
```

For the alternate `MINGW64` environment, use:

```bash
pacman -S mingw-w64-x86_64-gcc mingw-w64-x86_64-clang make diffutils
```

To build and install the Stage 2 compiler from the repo:

```bash
make venv
make PREFIX=/c/l0-install install
```

Then use it like this:

### From MSYS2 bash

```bash
source /c/l0-install/bin/l0-env.sh
l0c --version
```

### From `cmd.exe`

```cmd
call C:\l0-install\bin\l0-env.cmd
l0c --version
```

`l0-env.cmd` automatically puts a supported MSYS2 toolchain `bin` directory on `PATH` so that the C compiler (GCC or
Clang) and its support DLLs are visible to `l0c`. It probes for the MSYS2 install in this order:

1. `%MSYS2_TOOLCHAIN_BIN%` if set, for example `C:\msys64\ucrt64\bin` or `C:\msys64\mingw64\bin`.
2. `%MSYS2_ROOT%\ucrt64\bin`, then `%MSYS2_ROOT%\mingw64\bin` (set `MSYS2_ROOT` if MSYS2 is not in the default
   location).
3. The Windows registry (`HKCU\Software\MSYS2`, then `HKLM\Software\MSYS2`), preferring `ucrt64\bin` and then
   `mingw64\bin`.
4. The default paths `C:\msys64\ucrt64\bin`, then `C:\msys64\mingw64\bin`.

If none of these resolve, a warning is printed and you must add `ucrt64\bin` or `mingw64\bin` to `PATH` manually.

You do not need to open the MSYS2 shell just to invoke `l0c.cmd`. You still need a validated MSYS2 `UCRT64` or `MINGW64`
MinGW-w64 GCC or Clang toolchain installed for normal `--build` and `--run` workflows, because those paths require a
supported C compiler.

Notes:

- The installed Windows entry point is `l0c.cmd`; `cmd.exe` resolves bare `l0c` to that launcher.
- `l0-env.cmd` is generated for native `cmd.exe` activation.
- `l0-env.sh` remains the MSYS2/bash activation helper.

## If you are developing Dea/L0 itself

For day-to-day development, MSYS2 `UCRT64` bash is the recommended shell. MSYS2 `MINGW64` bash is supported for
alternate validation.

For repo development in `UCRT64`, install Python and `uv` alongside the C toolchain:

```bash
pacman -S mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-pip mingw-w64-ucrt-x86_64-uv
```

For `MINGW64`, use the matching package family:

```bash
pacman -S mingw-w64-x86_64-python mingw-w64-x86_64-python-pip mingw-w64-x86_64-uv
```

### Work on Stage 2

```bash
make use-dev-stage2
source build/dea/bin/l0-env.sh
l0c --version
```

### Work on Stage 1

```bash
make use-dev-stage1
source build/dea/bin/l0-env.sh
l0c --version
```

`cmd.exe` summary:

- Repo-local Stage 1 and Stage 2 both work through `build\dea\bin\l0c.cmd` after `make use-dev-stage1` or
  `make use-dev-stage2`.
- Installed Stage 2 works through `<PREFIX>\bin\l0-env.cmd` followed by `l0c`, or through the direct launcher
  `<PREFIX>\bin\l0c.cmd`.
- `l0-env.cmd` auto-detects `ucrt64\bin` first, then `mingw64\bin`. Set `MSYS2_TOOLCHAIN_BIN` to force one toolchain
  `bin` directory, or set `MSYS2_ROOT` if MSYS2 is installed in a non-default location.

## Technical addendum

You can ignore the next sections unless you are working on Dea/L0 itself or need to understand the Windows launcher
layout in detail.

### Supported workflow

| Scenario                                      | Recommended entry point on Windows            |
| --------------------------------------------- | --------------------------------------------- |
| Source-tree Stage 1 from MSYS2 bash           | `./scripts/l0c`                               |
| Source-tree Stage 1 from `cmd.exe`            | `scripts\\l0c.cmd`                            |
| Repo-local Stage 1 or Stage 2 from MSYS2 bash | `source build/dea/bin/l0-env.sh` then `l0c`   |
| Repo-local Stage 1 or Stage 2 from `cmd.exe`  | `call build\\dea\\bin\\l0-env.cmd` then `l0c` |
| Installed Stage 2 from MSYS2 bash             | `source <PREFIX>/bin/l0-env.sh` then `l0c`    |
| Installed Stage 2 from `cmd.exe`              | `call <PREFIX>\\bin\\l0-env.cmd` then `l0c`   |

## What the Windows targets generate

### `make install-dev-stage1`

This writes a repo-local Stage 1 launcher layout under `DEA_BUILD_DIR/bin/`:

- `l0c-stage1`
- `l0-env.sh`
- `l0c-stage1.cmd`
- `l0-env.cmd`

Important current behavior:

- `l0c-stage1` is a POSIX shell wrapper.
- `l0c-stage1.cmd` is the Windows batch wrapper.
- There is no selected `l0c` alias yet.

This target is directly usable from MSYS2 bash or through `build\\...\\bin\\l0c-stage1.cmd` in native Windows shells.

### `make install-dev-stage2`

This writes a repo-local Stage 2 launcher layout under `DEA_BUILD_DIR/bin/`:

- `l0c-stage2.native`
- `l0c-stage2`
- `l0c-stage2.cmd`
- `l0-env.sh`
- `l0-env.cmd`

Important current behavior:

- `l0c-stage2` is the POSIX shell wrapper.
- `l0c-stage2.cmd` is the Windows batch wrapper.
- There is still no selected `l0c` alias until you run `make use-dev-stage2`.

### `make install-dev-stages`

This runs both `install-dev-stage1` and `install-dev-stage2`.

After this target, you have both stage-specific launchers, but you still do not have a selected `l0c` command until you
run `make use-dev-stage1` or `make use-dev-stage2`.

### `make use-dev-stage1`

This selects Stage 1 as the repo-local `l0c` alias under `DEA_BUILD_DIR/bin/`.

Current Windows behavior:

- `l0c` is created for the POSIX/MSYS2 side.
- `l0c.cmd`

Practical result:

- In MSYS2 bash, `source build/dea/bin/l0-env.sh` then `l0c ...` works.
- In `cmd.exe`, `call build\\dea\\bin\\l0-env.cmd` then `l0c ...` works.

### `make use-dev-stage2`

This selects Stage 2 as the repo-local `l0c` alias under `DEA_BUILD_DIR/bin/`.

Current Windows behavior:

- `l0c`
- `l0c.cmd`

Both are created by copying the selected Stage 2 wrapper pair:

- `l0c` for POSIX/MSYS2 bash use
- `l0c.cmd` for native Windows shell resolution

This is the repo-local developer workflow that works cleanly in both MSYS2 bash and native Windows shells.

### `make install PREFIX=...`

This installs the self-hosted Stage 2 compiler into `PREFIX`.

On Windows the installed `PREFIX/bin/` layout includes:

- `l0c-stage2.native`
- `l0c-stage2`
- `l0c-stage2.cmd`
- `l0c`
- `l0c.cmd`
- `l0-env.sh`
- `l0-env.cmd`

There is no Stage 1 install-prefix workflow. `make install` installs Stage 2 only.

## MSYS2 bash usage

`l0-env.sh` is generated on Windows and is intended to be sourced from MSYS2 bash.

Repo-local Stage 2:

```bash
make use-dev-stage2
source build/dea/bin/l0-env.sh
l0c --version
```

Repo-local Stage 1:

```bash
make use-dev-stage1
source build/dea/bin/l0-env.sh
l0c --version
```

Installed Stage 2 prefix:

```bash
make PREFIX=/c/l0-install install
source /c/l0-install/bin/l0-env.sh
l0c --version
```

What `l0-env.sh` does:

- sets `L0_HOME`
- prepends the corresponding `bin/` directory to `PATH`
- keeps the repo-local or installed layout self-contained

Important caveat:

- The repo-local `l0-env.sh` only auto-sources the shared monorepo `../.venv/bin/activate`.
- If your Windows virtual environment was created in `../.venv/Scripts`, the script may not activate it automatically.
- That does not block `l0c-stage1`, because the Stage 1 wrappers also probe `../.venv/Scripts/python.exe` directly.

## `cmd.exe` usage

`l0-env.sh` is not for `cmd.exe`. The supported native activation pattern is:

1. `call` the generated `l0-env.cmd` (this also puts MinGW-w64 GCC on `PATH` automatically)
2. run `l0c`

Direct `.cmd` launcher invocation also works when you do not want a shell-local activation step.

### Repo-local Stage 2 in `cmd.exe`

After you have already run `make install-dev-stage2` and `make use-dev-stage2` from MSYS2 bash or another shell with GNU
Make available:

```cmd
call build\dea\bin\l0-env.cmd
l0c --version
```

Direct stage-specific invocation also works:

```cmd
build\dea\bin\l0c-stage2.cmd --version
```

### Installed Stage 2 in `cmd.exe`

After the prefix has already been created with `make install`:

```cmd
call C:\l0-install\bin\l0-env.cmd
l0c --version
```

Direct invocation:

```cmd
C:\l0-install\bin\l0c.cmd --version
```

### Stage 1 in `cmd.exe`

After you have already run `make use-dev-stage1`:

```cmd
call build\dea\bin\l0-env.cmd
l0c --version
l0c --check -P examples hello
```

Direct stage-specific invocation also works:

```cmd
build\dea\bin\l0c-stage1.cmd --version
```

## Why both `l0c-stage2.cmd` and `l0c.cmd` exist

They are not redundant by role.

- `l0c-stage2.cmd` is the stage-specific launcher.
- `l0c.cmd` is the selected/public alias.

When Stage 2 is selected, both may dispatch to the same native binary, but they represent different contracts:

- `l0c-stage2.cmd` stays stable as "the Stage 2 entry point"
- `l0c.cmd` is "whatever stage is currently selected as `l0c`"

This matches the Unix layout conceptually:

- `l0c-stage2`
- `l0c`

The Windows-specific difference is implementation, not intent:

- Unix uses the stage-specific wrapper plus a symlinked alias.
- Windows uses the stage-specific `.cmd` wrapper plus a copied `.cmd` alias, because the tool generator does not rely on
  Windows symlink behavior for the selected command.

## Native-shell command resolution

In `cmd.exe`, bare `l0c` works by resolving `l0c.cmd` via the normal Windows executable-extension lookup rules
(`PATHEXT`).

That is why there is no `l0c.exe` wrapper in the generated layout:

- `l0c` resolves to `l0c.cmd`
- `l0c.cmd` dispatches to the real launcher target

## Current limitations

- `l0-env.sh` remains the MSYS2/bash activation story.
- The source-tree fallback `scripts\\l0c.cmd` still exists for direct Stage 1 use outside the repo-local selected-alias
  workflow.
