# Stage 1 Dea/L0 Language Compiler

This directory contains the implementation of the Stage 1 compiler (Python) for the Dea/L0 programming language.
Documentation-generation tooling is maintained separately under `compiler/docgen/`.

Python 3.14+ is required. Use built-in container annotations (`list[T]`, `dict[K, V]`), `T | None`, and native deferred
annotations. Prefer keyword class patterns for AST/type dispatch where they make the operation easier to follow. The CI
matrix uses Python 3.14. Python 3.15 compatibility has been verified locally.

See:

- Project overview and usage: [l0/README.md](../../README.md)
- Current status and roadmap: [l0/docs/project-status.md](../../docs/project-status.md)
