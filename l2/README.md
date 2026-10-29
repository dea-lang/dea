# Dea/L2

L2 owns the former L1 Stage 2 compiler as its canonical `l2c`. The implementation is `.l1`; accepted programs and owned
stdlib modules are `.l2`, with `.l2m` interfaces. Its initial semantics came from the L1 baseline at the split; later L1
changes are not inherited automatically. Shared ABI names, including the compatible `l1_real.h` header, remain internal
compatibility details.

Sustained L2 feature development is deferred until L1 is stable, a baseline is selected, and the L2 phase is explicitly
started. The compiler and validation workflows below remain available for maintenance. Run these commands from `l2/`.

```sh
export L2_BOOTSTRAP_L1C=/absolute/installed-l1/bin/l1c
make build
make use-dev
make test
L2_ISOLATION_BOOTSTRAP_PREFIX=/absolute/installed-bookworm-l1 make test-isolation
```

A compatible L1 toolchain is an explicit build dependency, installed by default. For coordinated development reuse, set
`L2_BOOTSTRAP_MODE=development` and point `L2_BOOTSTRAP_L1C` at a generated L1 development launcher with its native
binary, headers, and semantic interfaces. There is no implicit sibling-checkout or PATH fallback. L2 never resolves
target inputs from L1 and the built compiler operates on L2 programs without invoking L1. Docker isolation is opt-in;
routine Unified CI reuses explicit predecessor outputs and standalone L2 CI constructs an installed bootstrap. See
[l2/AGENTS.md](AGENTS.md), [l2/docs/project-status.md](docs/project-status.md), and
[l2/docs/roadmap.md](docs/roadmap.md). L2 installation/distribution and hosted release workflows are outside this
initial split.

Production C support has a bootstrap-independent native reference:

```sh
make venv
make test-docgen
make docs-pdf
```

This generates HTML, XML, LaTeX, a complete PDF, and an informational `undocumented-functions.txt` report under
`build/docs/native/`. It includes L2-owned runtime `.c` units, public headers, header-only implementations, and private
preparation support. It does not generate references for the `.l1` compiler or `.l2` language bindings; L2 has no such
reference pipeline yet. Tests, benchmark evidence, generated files, and vendored code are outside this production
inventory. C contracts and prototype briefs follow
[docs/reference/c-documentation.md](../docs/reference/c-documentation.md).
