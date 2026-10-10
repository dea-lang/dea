# Dea/L2

L2 owns the former L1 Stage 2 compiler as its canonical `l2c`. The implementation is `.l1`; accepted programs and owned
stdlib modules are `.l2`, with `.l2m` interfaces. Initial language semantics match the L1 baseline apart from level
identity. Shared ABI names, including the compatible `l1_real.h` header, remain internal compatibility details.

```sh
export L2_BOOTSTRAP_L1C=/absolute/installed-l1/bin/l1c
make build
make use-dev
make test
L2_ISOLATION_BOOTSTRAP_PREFIX=/absolute/installed-bookworm-l1 make test-isolation
```

A compatible installed L1 toolchain is an explicit build dependency. L2 never resolves target inputs from L1 and the
built compiler operates on L2 programs without invoking L1. See [l2/AGENTS.md](AGENTS.md),
[l2/docs/project-status.md](docs/project-status.md), and [l2/docs/roadmap.md](docs/roadmap.md). L2
installation/distribution and hosted release workflows are outside this initial split.
