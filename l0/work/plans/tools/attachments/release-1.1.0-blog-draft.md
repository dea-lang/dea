---
title: 'Dea/L0 1.1.0: safer control flow and a frontend that keeps going'
date: 2026-07-13 12:00:00 +0200
categories: [Dea, Releases]
tags: [dea, l0, compiler, systems-programming]
---

I have released **Dea/L0 1.1.0**, a focused update to the self-hosted foundation of the Dea systems programming
language. This release makes control-flow cleanup safer, lets the frontend recover from more source errors, and improves
the portability of the Stage 2 compiler without expanding the command-line or standard-library surface.

## One spelling for the path forward

The canonical default arm for `case` is now `_ =>`:

```l0
case (status) {
    0 => printl_s("ready");
    1 => printl_s("busy");
    _ => printl_s("unknown");
}
```

The wildcard mirrors `match` and makes the default arm explicit in the same way as every other arm. Existing L0 code
using `case ... else` still compiles in 1.1.0, but it emits the `PAR-0242` deprecation warning. Removing that spelling
is reserved for L0 2.0.0, giving users a full minor-release migration window.

There is one ambiguity worth fixing while migrating: brace a `case` value arm containing an unbraced `if ... else` when
the trailing `else` could also be read as the old `case` default. The compiler reports `PAR-0243` and points users
toward the unambiguous form.

## A frontend that keeps going

A compiler is much more useful when one bad character does not erase the structure that follows it. Lexer errors can now
carry a logical recovery token, so the parser can diagnose the invalid input and continue through the surrounding
declaration or statement. That reduces cascades and exposes more genuine errors in one compiler run.

Diagnostic positions are more consistent too. Columns now count Unicode code points in both compiler stages, while the
source contract clearly separates UTF-8 source text from the language vocabulary: strings and comments may contain
Unicode, but identifiers remain ASCII. Orphaned `else` and `cleanup` keywords also receive more precise errors, and
duplicate imports no longer flood the warning output.

## Safer control flow and ownership

This release hardens the paths where control flow and deterministic cleanup meet. `for` headers, loop liveness, and
unreachable-code analysis now agree across Stage 1 and Stage 2. `with` cleanup runs on exits from inline header
expressions, and return analysis accounts for cleanup blocks that return themselves.

Stale `drop` operations now fail deterministically before cleanup can walk or mutate related state. This is a small
surface change with an important consequence: invalid ownership state stops at the boundary where it is detected.

The `for` grammar is also enforced more precisely. A `let` declaration in the update clause now reports `PAR-0145`; move
the declaration outside the update clause and leave a non-declaration simple statement there.

## A steadier self-hosted compiler

Stage 2 now surfaces warnings in `--build`, `--run`, `--gen`, `--sym`, and `--type` modes instead of silently dropping
them in some paths. Host C compiler options are ordered correctly, Dea environment activation is stackable, and nested
test environments are isolated from compiler runs.

Portability work covers Unicode test input on Windows and Apple Silicon triple-bootstrap comparisons. Mach-O UUID
normalization removes a platform-specific source of noise while preserving the fixed-point checks that matter.

## What stays stable, and what comes next

Dea/L0 1.1.0 adds no CLI flags or modes and adds or removes no public L0 types. The L0 standard-library implementation
is unchanged. The release instead concentrates on correctness, diagnostics, and confidence in the self-hosted toolchain.

The main migration for a future major release is already visible: replace `case ... else` defaults with `_ =>`. L0 2.0.0
can then remove the deprecated spelling and its temporary ambiguity diagnostic without surprising 1.x users.

Download the four platform builds, API documentation, and checksums from the
[Dea/L0 1.1.0 release](https://github.com/googlielmo/dea-lang/releases/tag/l0-v1.1.0). The
[full comparison](https://github.com/googlielmo/dea-lang/compare/l0-v1.0.0...l0-v1.1.0) and
[contributor guide](https://github.com/googlielmo/dea-lang/blob/main/CONTRIBUTING.md) are available in the public
repository.
