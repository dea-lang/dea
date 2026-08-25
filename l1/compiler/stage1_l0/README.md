# L1 Stage 1 Compiler

This directory contains the active `stage1_l0` bootstrap compiler for Dea/L1.

`stage1_l0` means the compiler is implemented in Dea/L0. It is seeded from the runnable Dea/L0 Stage 2 compiler and
retargeted to the Dea/L1 public interface.

The driver currently provides per-module generated C, compile-only `.o + .l1m` artifacts, verified standalone linking,
and multi-compilation-unit build/run. See [`l1/docs/project-status.md`][project-status] for the complete current
contract.

The implementation sources in this subtree remain `.l0`, and the copied implementation test suite is also `.l0`. Those
tests are exercised through the upstream `l0c-stage2` bootstrap compiler rather than through `l1c` itself. The fixture
programs and copied L1 stdlib modules that those tests compile as L1-language inputs now use the `.l1` extension. Test
names describe the L1 compiler subject where applicable, such as `l1c_lib_test.l0`, even when the test source is written
in L0.

Stage 1 validation here is limited to those `.l0` implementation tests and their focused backend/emitter assertions.
Committed full-file generated-C golden checks are intentionally out of scope for the current Stage 1 bootstrap contract.

Run the local bootstrap workflow from [`l1/`][l1-root]:

```bash
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --version
```

`make use-dev-stage1` auto-prepares the default repo-local upstream `../../l0/build/dea/bin/l0c-stage2` when needed.

`make docker CMD=test-all` runs the explicit Linux container validation path while preserving that same default
repo-local `../../l0` bootstrap layout.

Use `make bench-link-provenance` for the informational standalone-link provenance matrix. It measures warmed validation
over control, direct-provider, terminal-provider, and layered-DAG graphs without including graph construction. Override
the matrix with `BENCH_PROVENANCE_SHAPES`, `BENCH_PROVENANCE_SIZES`, `BENCH_PROVENANCE_WARMUPS`, and
`BENCH_PROVENANCE_RUNS`; save or compare machine-readable results with `BENCH_PROVENANCE_JSON` and
`BENCH_PROVENANCE_COMPARE`. The benchmark has no CI timing threshold and is not part of `test-all`.

For a non-default upstream bootstrap compiler, set `L1_BOOTSTRAP_L0C=/path/to/l0c-stage2` when running
`make build-stage1`.

[l1-root]: ../../README.md
[project-status]: ../../docs/project-status.md
