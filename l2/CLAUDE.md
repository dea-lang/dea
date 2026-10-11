# CLAUDE.md

Read [AGENTS.md](../AGENTS.md) for shared policy and [l2/AGENTS.md](AGENTS.md) for canonical L2 construction,
validation, and ownership. The `.l1` implementation is built with explicit `L2_BOOTSTRAP_L1C`, installed by default or a
generated development toolchain selected with `L2_BOOTSTRAP_MODE=development`; accepted programs use `.l2` and
interfaces use `.l2m`. Use `build`, `use-dev`, and `test-compiler`. Docker isolation is opt-in. L2 has no stage
selector, self-hosting gate, or productization target.
