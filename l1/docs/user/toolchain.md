# Using the L1 Stage 2 development toolchain

Run commands from any working directory. Replace `/path/to/dea-l1` with the prefix location; quote paths containing
spaces. Activation is optional and selects the prefix in the current shell:

```bash
source /path/to/dea-l1/bin/l1-env.sh
l1c --help
l1c --version
l1c --check /path/to/dea-l1/share/dea/l1/smoke/hello.l1
l1c --run /path/to/dea-l1/share/dea/l1/smoke/hello.l1
```

The smoke program prints `hello from Dea L1`. In native Windows Command Prompt, call `bin\l1-env.cmd` and use `l1c.cmd`
with Windows paths. Direct native `bin/l1c-stage2.native` execution uses the same installed-prefix checks.

## Native output and support

Select a compatible C toolchain with `L1_CC`, and select a writable support cache with `--stdlib-cache` or
`L1_STDLIB_CACHE`. Without an explicit cache selector the compiler uses its per-user cache. The installation contains
semantic interfaces and rebuild sources, with no prebuilt native support profile. `--check`, `--gen`, and compile-only
semantic lookup use the bundled interface set. Native build/link/run prepare matching support as needed:

```bash
l1c --compile /path/to/dea-l1/share/dea/l1/smoke/hello.l1 -o hello.o
l1c --link hello.o -o hello
./hello
l1c --build /path/to/dea-l1/share/dea/l1/smoke/hello.l1 -o hello
```

`--no-auto-prepare` requires an already matching native cache profile. Use `--prepare-stdlib` to prepare explicitly;
`--prepare-stdlib --force` replaces the selected profile. Serialize forced preparation and manual cache removal against
other compiler processes. Native configuration changes select different profiles. Explicit system, runtime, compiler,
and cache overrides remain authoritative; an unusable explicit cache does not silently select another root.

## Relocation and repair

Move the entire prefix together, including hidden or metadata files. Compiler operations leave prefix contents unchanged
and place native support in the selected cache. A read-only prefix is supported. Launchers and the native compiler
select their own prefix and discard stale inherited build roots. Activation places this prefix's `bin` first in `PATH`.

Missing, malformed, or incomplete installation metadata produces `L1C-9515`, including for help/version. Repair or retry
the installation using a complete trusted payload. Do not remove or hand-edit the installation manifest to bypass the
check. Inventory metadata is distinct from writable cache metadata; clearing a cache does not repair an installation.

Project source and reference documentation: <https://github.com/dea-lang/dea>.
