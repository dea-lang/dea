# Dea/L<sub>1</sub>

This subtree contains the active bootstrap compiler for Dea/L1 inside the Dea monorepo.

The canonical project overview lives in [README.md][root-readme]. Run L1 bootstrap commands from this directory.
L1-local stable documentation lives under [l1/docs/][docs], while L1-local plans and other lifecycle artifacts live
under [l1/work/][work].

The subtree also includes minimal example programs at [examples/][examples].

Useful local documents:

- [l1/docs/project-status.md][project-status] for the current L1 bootstrap implementation status
- [l1/docs/roadmap.md][roadmap] for the live L1 direction document
- [l1/docs/user/linking.md][linking] for external native-library and foreign-object linking
- [l1/CLAUDE.md][claude] for repo-local AI guidance

At the moment the Dea/L1 source surface is `.l1`, including the copied L1 stdlib under `compiler/shared/l1/stdlib/` and
the L1-language fixture programs exercised by the bootstrap compiler tests. The `stage1_l0` compiler implementation and
its implementation tests are `.l0` sources and are built or run with the upstream `l0c-stage2` toolchain during
bootstrap.

The current Stage 1 driver supports per-module generated C, compile-only `.o + .l1m` artifact pairs, verified standalone
linking, and multi-compilation-unit build/run across mixed source/interface graphs. Link-involving modes also accept one
ordered stream of explicit foreign objects, external libraries, search paths, rpaths, and raw host-driver words. These
are bootstrap capabilities; L1 does not yet have a self-hosted Stage 2 compiler or install/dist/release workflow.

Current Stage 1 validation combines the `.l0` implementation test suite under `compiler/stage1_l0/tests/` with
warning-free latest-stage `--check` coverage for `examples/*.l1`. Exact generated-C golden-file parity is not part of
the active L1 Stage 1 contract.

Minimal local workflow:

```bash
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --version
```

`make use-dev-stage1` auto-prepares the default repo-local upstream `../l0/build/dea/bin/l0c-stage2` when needed.

To use an explicit upstream L0 compiler instead of the repo-local default, set `L1_BOOTSTRAP_L0C=/path/to/l0c` when
running `make build-stage1`.

[claude]: CLAUDE.md
[docs]: docs/
[examples]: examples/
[linking]: docs/user/linking.md
[project-status]: docs/project-status.md
[roadmap]: docs/roadmap.md
[root-readme]: ../README.md
[work]: work/
