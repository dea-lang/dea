# ADR-0024: C Contracts and Isolated Reference Extraction

- Decision date: 2026-10-25
- Last edited: 2026-10-25
- Status: Accepted

## Context

C function documentation must remain complete when header prototypes carry only an ordinary brief. Public header-only
libraries and private implementation headers also contain canonical definitions. Reference inventories that omit
implementation units or hide header-defined bodies cannot recover those contracts.

Doxygen's association heuristics cross boundaries in a mixed corpus: unrelated same-signature C and translated Dea
functions can inherit each other's bodies and contracts. Alternative native providers can also be combined despite
belonging to separate libraries. Filtering undocumented reports after extraction cannot repair contaminated generated
descriptions. The HTML renderer can additionally rerun Doxygen and replace previously isolated output.

## Decision

- Keep each complete multiline C function contract immediately before its definition. Use Javadoc autobrief without
  explicit brief commands. Corresponding header prototypes carry an ordinary one-line comment reproducing the exact
  first sentence. Header-defined functions retain complete contracts.
- Audit maintained C/header sources, including fixtures and benchmark evidence, while explicitly excluding vendored and
  generated files from bulk changes. Validate spacing, definition contracts, prototype briefs, and executable-token
  preservation independently of Doxygen.
- Select complete production C inputs in reference manifests, including implementation headers and `.c` units. Preserve
  original source paths, signatures, and line structure in shadow copies.
- Extract each language binding independently. Extract alternative native provider roles separately when one external
  ABI has different production definitions. Keep matching C declarations and their implementation in the same native
  group.
- Combine independent XML and LaTeX outputs using disjoint secondary identities, references, filenames, and assets.
  Preserve external references and numeric graph identities. Render HTML from the combined XML without rerunning
  Doxygen.
- Associate report occurrences through explicit declaration/body or XML identities plus binding, linkage, and signature.
  Resolve explicit typedef references and ignore parameter-name spelling when comparing types. Documentation on either
  matching occurrence covers the function; a shared name alone never does.
- Preserve each occurrence's signature and source locations when declaration and definition formal names differ. Use
  Doxygen's explicit `declname`/`defname` relationship to label copied parameter documentation for that occurrence; do
  not drop its description or rename executable source parameters.
- Retain informational undocumented-function reports. An empty report is not a CI requirement.
- Include shared extraction and identity helpers in documentation bundle fingerprints. Record preprocessing profiles and
  reference-inventory limits separately from the complete physical-source audit.

## Rationale

Definition-owned contracts keep implementation and guarantees together while making headers concise. Extraction
isolation prevents incorrect associations before they contaminate parameters, returns, ownership, or failure prose.
Explicit identities recognize real C prototype/body pairs without hiding unrelated private functions, signatures, or
language bindings. Source-preserving adaptation retains useful declaration and definition locations.

## Consequences

L0's two references and L1's canonical reference share extraction and report helpers. Their production inventories
include runtime implementations and compiler support. L2 has a complete native C reference without requiring a compiler
bootstrap; compiler-language and stdlib-binding references remain outside its current pipeline.

Independent extraction adds Doxygen invocations and output-combination validation. Header-only and trace-located APIs
need explicit preprocessing profiles; one profile does not enumerate every mutually exclusive platform or checking
branch. The source checker audits physical definitions separately, including conditional alternatives.

Generated identities in secondary groups can change internal reference URLs. Existing published historical artifacts
remain immutable. Local generation does not grant publication authority.

## Related Plans

- [work/plans/tools/closed/2026-10-25-shared-c-function-documentation-noref.md](../../work/plans/tools/closed/2026-10-25-shared-c-function-documentation-noref.md)

## Current Docs

- [docs/reference/c-documentation.md](../reference/c-documentation.md)
- [AGENTS.md](../../AGENTS.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [l0/docs/README.md](../../l0/docs/README.md)
- [l1/docs/README.md](../../l1/docs/README.md)
- [l2/README.md](../../l2/README.md)
