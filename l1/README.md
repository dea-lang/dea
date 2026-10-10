# Dea/L1

L1 provides one canonical `l1c` implemented in L0, with separate compilation/linking, verified `.l1m` interfaces, owned
stdlib/runtime support, and managed native preparation. It accepts `.l1` programs. The former L1 Stage 2 is now L2.

```sh
make build
make use-dev
source build/dea/bin/l1-env.sh
l1c --run -Rp examples hello
make test
```

The upstream L0 selection is explicit under [l1/AGENTS.md](AGENTS.md). Installed L1 does not require L0, checkout,
Python, or Make. Local install/dist machinery and matching offline references are retargeted to canonical L1; fresh
four-platform exact-artifact acceptance remains separate from compiler CI and historical Stage 2 acceptance.

Use [l1/docs/roadmap.md](docs/roadmap.md), [l1/docs/project-status.md](docs/project-status.md), and
[l1/docs/user/toolchain.md](docs/user/toolchain.md). L1 0.1.0 is the intended development release; L1 is not frozen and
its feature backlog is not automatically assigned to L2. Hosted release workflows remain deferred until split
acceptance.
