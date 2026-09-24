# L1 Stage 1 Compiler

This directory contains the active `stage1_l0` bootstrap compiler for Dea/L1.

`stage1_l0` means the compiler is implemented in Dea/L0. It is seeded from the runnable Dea/L0 Stage 2 compiler and
retargeted to the Dea/L1 public interface.

The driver currently provides per-module generated C, compile-only `.o + .l1m` artifacts, verified standalone linking,
ordered interface discovery, and multi-compilation-unit build/run, including ordered external-library inputs in every
link-involving mode. See [`l1/docs/project-status.md`][project-status] for the complete current contract and
[`l1/docs/user/linking.md`][linking] for the user workflow.

`make build-stage1` uses the new compiler frontend to generate and verify the canonical bundled semantic interfaces,
independently of native stdlib/runtime construction. The preparation driver and compiler-private C support provide
on-demand native profiles, conservative toolchain reuse and one local cache. See
[l1/docs/reference/stdlib-preparation.md][preparation] for the workflow and ownership boundaries.

The implementation sources in this subtree remain `.l0`, and the copied implementation test suite is also `.l0`. Those
tests are exercised through the upstream `l0c-stage2` bootstrap compiler rather than through `l1c` itself. The fixture
programs and copied L1 stdlib modules that those tests compile as L1-language inputs now use the `.l1` extension. Test
names describe the L1 compiler subject where applicable, such as `l1c_lib_test.l0`, even when the test source is written
in L0.

Stage 1 validation covers `.l0` implementation tests, Python CLI/artifact integration tests, environment activation,
examples, and the dedicated ARC/memory trace suite. Generated-C identity is checked across producing CLI modes;
committed full-file generated-C golden files remain outside the current bootstrap contract.

Runtime and language-feature cases use [`l1/compiler/stage1_l0/tests/support/driver_inputs.l0`][driver-test-inputs] and
its [`l1/compiler/stage1_l0/tests/support/driver_inputs.py`][python-driver-inputs] counterpart to select explicit
bundled source roots, public headers and the runtime built by Make. The helpers respect `L1_BUILD_DIR` and disable
automatic preparation for these archive-based inputs. TinyCC retains automatic selection of its separate raw-object
runtime. Dedicated `preparation_test` and Python preparation integration tests keep the default discovery, cold
preparation, warm reuse, runtime-only consumption and failure/recovery paths covered.

Normal and trace runners share the `PREPARATION_SUPPORT_TESTS` dependency declaration in
[`l1/compiler/stage1_l0/scripts/test_runner_common.py`][test-runner]. Add a test there when its imported implementation
requires the native preparation ABI. Other implementation tests omit `preparation_support.c`; all retain the common
filesystem and fingerprint support. Compiler builds continue including every support unit with their existing flags.

`make test-stage1-trace-children` runs the declared L1 math runtime fixtures as separate traced executables. It uses the
same native-input selection as Python driver tests and analyzes only each child executable's stderr. Pass
`TESTS="math_int_trace_main"` to select a fixture. `make test-all` always includes both declared child fixtures,
independently of parent `TESTS` selectors.

Production sources are organized into phase and ownership families. Coarse pass/command entrypoints remain at the root;
shared state and helpers are imported directly from their canonical child modules. The 120-module layout and the two
retained recursive kernels are documented in [`l1/docs/reference/architecture.md`][architecture].

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

[architecture]: ../../docs/reference/architecture.md
[driver-test-inputs]: tests/support/driver_inputs.l0
[l1-root]: ../../README.md
[linking]: ../../docs/user/linking.md
[preparation]: ../../docs/reference/stdlib-preparation.md
[project-status]: ../../docs/project-status.md
[python-driver-inputs]: tests/support/driver_inputs.py
[test-runner]: scripts/test_runner_common.py
