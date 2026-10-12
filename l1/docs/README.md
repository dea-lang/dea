# L1 Documentation Layout

This `l1/docs/` tree holds stable documentation for the Dea/L1 subtree.

It covers the canonical L0-implemented compiler, the L1 language and standard library, installed-toolchain usage, and
release notes. For a packaged compiler, start with [l1/docs/user/README.md][user-guide]; for source builds and
development, start with [l1/README.md][developer-guide].

L1-local lifecycle artifacts live in the sibling `l1/work/` tree. Dea-wide stable docs live under the root `docs/` tree,
while Dea-wide lifecycle artifacts live under the root `work/` tree.

## Layout

- `roadmap.md` for the singular evergreen L1 roadmap
- `project-status.md` for the current L1 development and delivery status snapshot
- `reference/` for L1 language, library, runtime, and implementation references
- `specs/` for L1-local compiler and module-interface specifications
- `user/` for installed-toolchain guides and native linking instructions
- [l1/docs/releases/README.md][releases] for curated versioned-release notes and authoring requirements
- `implementation/` for future accepted implementation notes if needed
- `decisions/` for ADR-style records linking design decisions to the closed plans that shaped them and the current docs
  where they are normatively recorded

Use `l1/work/plans/` for L1-local plans. If L1 work is actually shared with L0 or the monorepo, prefer one shared
root-owned plan under `work/plans/` instead of opening an L1-only follow-up plan for a mechanical downstream port.

## Roadmap

The L1 roadmap lives at [l1/docs/roadmap.md][roadmap]. It is the live direction document for L1 and is not
lifecycle-bound. Active initiatives under `l1/work/` execute the direction recorded there.

The roadmap, initiatives, and plans form a strict hierarchy by scope and lifetime:

- **Roadmap** ([l1/docs/roadmap.md][roadmap]): high level entry point. Captures L1's overall direction, lists active and
  completed initiatives, and records backlog ideas not yet promoted to initiatives. Edited in place; not closed.
- **Initiative** (`l1/work/initiatives/NNNN-*.md`): a coordinated, multiphase body of work with a defined scope and an
  end state. Records cross-cutting design decisions, sequences phases, and spawns one or more plans as phases become
  actionable. There can be many initiatives over L1's lifetime; each is opened, worked on, and eventually closed.
- **Plan** (`l1/work/plans/<kind>/<slug>.md`): a single change or work item with a defined start and end. Often spawned
  by an initiative phase; can also stand alone for work that does not warrant an initiative.

Reach for a roadmap edit when L1's overall direction shifts. Reach for a new initiative when a body of work spans
multiple plans across categories, when decisions made now constrain plans that will only be written later, or when the
sequencing and dependency structure between phases is itself the artifact worth recording. Reach for a plan directly
otherwise (even a large one).

When editing the roadmap, keep it directional rather than release-note-like: routine bug-fix history belongs in closed
plans and, when needed, `project-status.md`. Use roadmap completed sections for shipped work that materially changes the
L1 baseline, direction, or future planning constraints.

### Roadmap link legibility rules

For legibility, prefer reference-style file links with short, readable ids and end-of-file definitions.

Use repository-root paths as the visible link text, for example `[l1/docs/project-status.md][project-status]` or
`[l1/docs/roadmap.md][roadmap]`.

Keep reference ids short and readable, usually one or two words joined with hyphens. Avoid dates, numeric prefixes,
`noref`, and file extensions in the reference id unless a real uniqueness conflict leaves no cleaner option.

## Generated source references

From `l1/`, run `make venv` to prepare the shared Python environment. Then `make docs` builds canonical HTML, Markdown,
XML, and LaTeX references under `build/docs/reference/`. The source inventory includes the canonical `.l0` compiler, L1
stdlib/runtime, and native support actually used by its builder. There is no stage selector. HTML requires Doxygen,
Graphviz, the shared Python environment, and vendored m.css; `make docs-pdf` additionally requires a complete TeX
toolchain and builds the full indexed `pdf/dea_l1_api_reference.pdf`. Preview PDF builds cannot produce distribution
evidence.

```sh
make docs-artifacts DEA_DIST_VERSION=dev
```

This creates `build/docs/artifacts/dea_l1_autodocs.tar.gz` containing `dea-l1-autodocs/{html,pdf,manifest.json}`. The
stage-free schema-2 manifest binds level, package version, source identity/dirty state, selected-input digest, tool
provenance, strict/full-PDF success, and complete payload digests. Consumers reject old stage-selected bundles,
mismatched identities, unsafe members, corruption, remote assets, missing files, and preview/partial evidence. The HTML
and PDF work offline; extract the complete root to preserve relative links.

`DEA_DIST_VERSION` defaults to `dev`. `L1_DOCS_RELEASE_TAG` provides the reserved L1 tag/version mapping without
granting publication authority. `make test-docgen` exercises generator/consumer coverage through the shared Python
environment. Failed generation invalidates the consumer bundle while preserving diagnostic evidence; concurrent builds
need distinct output parents.

Direct `make install PREFIX=... DOCS_ARTIFACT=/absolute/bundle.tar.gz` optionally includes the matching bundle under
`share/doc/dea/l1/autodocs/`. `make dist` requires it and never generates documentation. `make smoke-dist ARCHIVE=...`
checks the exact archive after extraction. Local generation and packaging do not publish or dispatch workflows.

[developer-guide]: ../README.md
[releases]: releases/README.md
[roadmap]: roadmap.md
[user-guide]: user/README.md
