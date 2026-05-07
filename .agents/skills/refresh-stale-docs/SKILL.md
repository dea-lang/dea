---
name: refresh-stale-docs
description: Audit Dea live docs after feature or workflow changes and refresh stale content plus version metadata.
model: sonnet
effort: medium
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
- internal guidance files such as `CLAUDE.md`, `AGENTS.md`, and `.github/copilot-instructions.md` when the task includes
  internal docs

Do not sweep `work/plans/**` or archived docs unless the task explicitly asks for lifecycle artifacts.

## Repo-specific workflow

1. Read `CLAUDE.md` first. If the audit touches `l0/` or `l1/`, read the matching subtree `CLAUDE.md` too.
2. Inventory recent landed changes before editing docs. Prefer:

-

`git --no-pager log --since='<date>' --date=short --pretty=format:'%ad %h %s' --name-only -- '*.md' '.github/workflows/*'`

- targeted reads of the relevant `Makefile`, runtime headers, stdlib modules, tests, and workflow files

3. Map change areas to the highest-risk docs first:

- L1 numeric/bootstrap changes: `l1/docs/reference/project-status.md`, `l1/docs/reference/design-decisions.md`,
  `l1/docs/reference/standard-library.md`, `l1/docs/reference/architecture.md`, `l1/README.md`, and
  `l1/compiler/stage1_l0/README.md`
- L0 workflow/release/docs changes: `README.md`, `README-WINDOWS.md`, `l0/docs/user/**`,
  `l0/docs/reference/project-status.md`, `CONTRIBUTING.md`, and relevant `l0/docs/specs/**`
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

7. Keep docs honest about scope. If L1 is bootstrap-only or a library follow-up is still open, say so plainly.
8. If you commit, follow the commit rules in `CLAUDE.md` and run pre-commit from a level directory against the root
   config, for example:

```bash
cd l0
uv run --group dev pre-commit run --hook-stage pre-commit -c ../.pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR --relative)
```

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
- no draft-only features documented as shipped
- commit or handoff note explains which docs changed and which audited surfaces needed no edits
- no metadata-only `Version:` bumps unless the handoff or commit body explicitly says the file was audited against newer
  behavior and required no content changes
