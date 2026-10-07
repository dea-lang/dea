# L1 Documentation Layout

This `l1/docs/` tree holds stable documentation for the Dea/L1 subtree.

At the current bootstrap stage, this tree is still intentionally narrow:

- L1 bootstrap/reference documents
- normative L1 language/compiler specifications

L1-local lifecycle artifacts live in the sibling `l1/work/` tree. Dea-wide stable docs live under the root `docs/` tree,
while Dea-wide lifecycle artifacts live under the root `work/` tree.

## Layout

- `roadmap.md` for the singular evergreen L1 roadmap
- `project-status.md` for the current L1 bootstrap status snapshot
- `reference/` for L1-local bootstrap and implementation references
- `specs/` for L1-local compiler and module-interface specifications
- `user/` for task-oriented L1 bootstrap user guides
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

Use initiative and plan filenames as the visible link text where that is the clearest reader-facing label, for example
`[0001-separate-compilation-and-linking][separate-compilation]` or
`[2026-07-17-interface-fingerprint-canonicalization-and-verification-noref][interface-fingerprints]`.

Keep reference ids short and readable, usually one or two words joined with hyphens. Avoid dates, numeric prefixes,
`noref`, and file extensions in the reference id unless a real uniqueness conflict leaves no cleaner option. For other
documents, a short document name such as `[project-status][project-status]` is preferred.

## Generated source references

From `l1/`, run `make docs` for independent Stage 1 and Stage 2 HTML, Markdown, XML, and LaTeX references.
`DOC_STAGE=stage1` or `DOC_STAGE=stage2` selects one stage; the default is `all`. HTML generation requires Doxygen,
Graphviz, the shared Python environment (`make venv`), and vendored m.css under `tools/m.css`. It needs neither an
installed L1 compiler nor TeX. `make docs-pdf` additionally requires `pdflatex`, `makeindex`, and a complete TeX
installation with Doxygen's packages (including `doxygen.sty` generation, `newunicodechar`, and `hanging`).

Outputs live under `build/docs/stage1/` and `build/docs/stage2/`, each containing `html/index.html`, `markdown/`,
`doxygen/xml/`, `doxygen/latex/`, and stage-local warning/coverage reports. Complete PDFs are
`pdf/dea_l1_stage1_api_reference.pdf` and `pdf/dea_l1_stage2_api_reference.pdf`. Each successful selected stage updates
its matching `build/preview/stageS/{html,markdown,pdf}/` tree. The wrapper's `--output-dir` selects the common output
parent. `--pdf-fast` is a preview and cannot produce a distribution bundle.

Each reference contains only its own compiler sources, the bundled L1 standard library, runtime API headers, and
explicit native support inputs. Shared C support remains under `compiler/stage1_l0/support/` physically, but appears in
the shared reference chapter of both documents. The Stage 1 fingerprint bridge is excluded from Stage 2.

### Offline artifact handoff

```sh
make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=dev
```

This requires strict HTML and a full indexed PDF, then creates `build/docs/artifacts/dea_l1_stage2_autodocs.tar.gz`. Its
single `dea-l1-stage2-autodocs/` root contains `html/`, `pdf/`, and `manifest.json`. Extract the whole root to keep
relative PDF links working. The HTML is usable from the filesystem without checkout access or remote assets. Stage 1 can
be built the same way for developer use; Stage 2 distributions consume only the Stage 2 bundle.

The schema-1 manifest records level `l1`, numeric stage, package version, source revision/dirty state, a digest of the
selected sources and generator inputs, tool provenance, strict/full-PDF success, and the exact payload file digests.
`DEA_DIST_VERSION` defaults to `dev`; optional `L1_DOCS_RELEASE_TAG` maps `l1-vX.Y.Z` to `X.Y.Z` and `l1-snapshot-...`
to `snapshot-...` (plain and `v`-prefixed versions also match). The standard-library-only consumer API in
`scripts/docs_artifacts.py` provides `source_identity`, `package_version`, `unpack_bundle`, and `verify_tree`. Consumers
supply the expected stage, version, and source identity, and extract into an empty destination. Validation rejects
unsafe members, links outside the bundle, missing files, network assets, corruption, stale source identity, and
preview/partial evidence. Run `make test-docgen` for focused regression coverage. This target prepares the shared
virtual environment and runs its Python interpreter, independently of an explicit host `PYTHON` override.

A failed selected-stage invocation removes its old consumer bundle, retains previous successful reference output, and
preserves generation failures under `build/docs/stageS-failure/`. The other stage is untouched. Builds need separate
output parents when invoked concurrently for the same stage.

Productization will consume the explicit Stage 2 bundle through `DOCS_ARTIFACT` and place its verified files under
`share/doc/dea/l1/autodocs/stage2/`; install/dist and hosted release attachment remain separate work. Local generation
and verification do not publish documentation or dispatch workflows.

[roadmap]: roadmap.md
