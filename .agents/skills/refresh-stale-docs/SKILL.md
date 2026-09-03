---
name: refresh-stale-docs
description: Audit Dea live docs after feature or workflow changes and refresh stale content plus version metadata.
---

### Refresh stale docs

Use this skill when recent Dea changes may have outpaced the live docs, including reference docs, user guides, READMEs,
and internal agent guidance.

## Scope

Start with live docs only:

- root `README*.md`
- `docs/**`
- `l0/docs/**`
- `l1/docs/**`
- subtree `README.md` files
- internal guidance files such as `AGENTS.md` and `.github/copilot-instructions.md` when the task includes internal docs
- `docs/decisions/INDEX.md`, `l0/docs/decisions/INDEX.md`, `l1/docs/decisions/INDEX.md`: verify each table row matches
  an ADR file present in the directory; flag any gap or orphan row
- ADR `Related Plans` sections: verify newly closed source documents have resolvable links and their final ADR Impact
  dispositions agree with the ADR and scope

Do not sweep `work/plans/**` or archived docs unless the task explicitly asks for lifecycle artifacts.

## Repo-specific workflow

1. Read `AGENTS.md` first. If the audit touches `l0/` or `l1/`, read the matching subtree `AGENTS.md` too.
2. Inventory recent landed changes before editing docs. Prefer:

- `git --no-pager log --since='<date>' --date=short --pretty=format:'%ad %h %s' --name-only -- '*.md' '.github/workflows/*'`
- targeted reads of the relevant `Makefile`, runtime headers, stdlib modules, tests, and workflow files

3. Map change areas to the highest-risk docs first:

- L1 numeric/bootstrap changes: `l1/docs/project-status.md`, `l1/docs/reference/design-decisions.md`,
  `l1/docs/reference/standard-library.md`, `l1/docs/reference/architecture.md`, `l1/README.md`, and
  `l1/compiler/stage1_l0/README.md`
- L0 workflow/release/docs changes: `README.md`, `l0/README.md`, `l0/README-WINDOWS.md`, `l0/docs/user/**`,
  `l0/docs/project-status.md`, `CONTRIBUTING.md`, and relevant `l0/docs/specs/**`
- shared compiler or diagnostic changes: `docs/specs/compiler/**` and root `docs/reference/**`

4. Treat implementation and landed behavior as the oracle:

- code, runtime headers, stdlib sources, Makefiles, workflows, and tests
- closed landed plans can help explain why something shipped
- draft plans are not shipped behavior; do not document them as implemented

5. For docs with `Version: YYYY-MM-DD`, treat the version as a reviewed-current marker, not as a blind mirror of
   `git log`. Refresh the version line only when one of the following is true:

- the document content is changed in the same edit
- the document was audited against newer implementation behavior and is intentionally being marked current

Do not bump `Version:` merely because `git log` reports a later commit date. If the only edit is a version bump, the
handoff or commit body must state that the file was audited and required no content change.

One useful check is:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import subprocess

root = Path(".").resolve()

for base in [root / "docs", root / "l0" / "docs", root / "l1" / "docs"]:
    for path in sorted(base.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^Version:\\s*(\\d{4}-\\d{2}-\\d{2})\\s*$", text, re.M)
        if not match:
            continue
        version = match.group(1)
        rel = path.relative_to(root)
        last = subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "log",
                "-1",
                "--date=short",
                "--format=%ad",
                "--",
                str(rel),
            ],
            text=True,
        ).strip()
        if last and last > version:
            print(f"{rel}\\tversion={version}\\tlast_commit={last}")
PY
```

6. Only edit files that are actually stale:

- wrong behavior or commands
- misleading omissions after shipped features
- stale `Version:` metadata
- broken links to shipped features or workflows
- guidance that still points at a superseded workflow

7. When the task explicitly includes plans or initiatives, enforce the `## ADR Impact` lifecycle contract from root
   `AGENTS.md`. Run `python3 scripts/check_adr_impact.py --all-active` before staging and
   `python3 scripts/check_adr_impact.py --staged` after staging. Do not close a document with `Pending` records or
   missing same-change ADR evidence.
8. Keep docs honest about scope. If L1 is bootstrap-only or a library follow-up is still open, say so plainly.
9. If you commit, follow the commit rules in `AGENTS.md` and run pre-commit against the root config. Run from the
   monorepo root by default:

```bash
uv run --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR)
```

If already in an immediate level directory, keep `uv` pointed at the root project and pass root-relative paths:

```bash
uv run --directory .. --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files $(git -C .. diff --cached --name-only --diff-filter=ACMR)
```

## Remote publication boundary

A documentation audit, refresh, local edit, or local commit does not authorize publishing the documentation. While using
this skill, do not push, dispatch a synchronization workflow, deploy Pages, update a release, or write to a downstream
documentation or blog repository.

If the repository normally publishes documentation as an automatic effect of a push, treat that push as a deployment
operation and leave it for a separately authorized follow-up. Neither a plan that includes publication nor any sandbox,
tool, or escalation approval replaces the required user authorization. End with the local diff or commit and report the
pending publication action explicitly.

## Writing rules

- Prefer concise, factual updates over broad rewrites.
- Use repository-root paths as visible Markdown link text for repo files.
- Keep code names and comments in English.
- Do not create or update plan docs unless the task explicitly asks for lifecycle artifacts.
- Do not "refresh" draft future work into live reference docs.

## Deliverable checklist

- stale file set identified
- content drift fixed
- version metadata refreshed where needed
- ADR indexes, source-plan links, and ADR Impact dispositions agree for lifecycle documents in scope
- no draft-only features documented as shipped
- commit or handoff note explains which docs changed and which audited surfaces needed no edits
- no metadata-only `Version:` bumps unless the handoff or commit body explicitly says the file was audited against newer
  behavior and required no content changes
- no push, workflow dispatch, documentation deployment, release update, or downstream repository write
