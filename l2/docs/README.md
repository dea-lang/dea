# L2 Documentation

L2 owns its language and compiler references. Its canonical implementation is written in L1; `.l2` programs and `.l2m`
interfaces are the compiler's accepted language. Start with [l2/docs/project-status.md](project-status.md),
[l2/docs/roadmap.md](roadmap.md), [l2/docs/reference/architecture.md](reference/architecture.md), and
[l2/docs/decisions/INDEX.md](decisions/INDEX.md).

From `l2/`, `make docs` generates the native C reference under `build/docs/native/`; `make docs-pdf` also builds the
complete PDF. This bootstrap-independent reference covers the owned runtime and compiler support. L2 has no generated
reference for its `.l1` compiler or `.l2` stdlib bindings, and no release-productization workflow yet. See
[l2/README.md](../README.md) for prerequisites and commands.

Language references: [l2/docs/reference/grammar.md](reference/grammar.md),
[l2/docs/reference/ownership.md](reference/ownership.md),
[l2/docs/reference/standard-library.md](reference/standard-library.md), and
[l2/docs/specs/compiler/module-interface-format.md](specs/compiler/module-interface-format.md).
