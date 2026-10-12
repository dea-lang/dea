# Dea/L1 Release Notes

Each versioned `l1-vX.Y.Z` release requires a checked-in `l1/docs/releases/X.Y.Z.md` file. The release helper preserves
that file as the opening GitHub release body and automatically appends the commit history. This follows the L0
version-to-file and heading conventions described in [l0/docs/releases/README.md][l0-notes].

## Authoring

Start each file with the exact version heading and development-toolchain notice:

```markdown
# Dea/L1 X.Y.Z

Canonical L0-implemented L1 development toolchain. This release does not declare language or toolchain stability.

## Highlights

Describe the changes relevant to Dea/L1 users.

## Compatibility

Describe compatibility changes and migration steps where needed.
```

Replace `X.Y.Z` with the numeric release version and replace the example prose with reviewed release content. The notice
may wrap across lines within its paragraph. Organize the remaining text by relevant themes; choose sections that fit the
release. Add an entry to the release index below when preparing a versioned document.

The file must be committed in the source revision selected for the release tag. Uncommitted edits and notes on a later
branch revision are not used. Missing or empty files, a mismatched first-line heading, a missing development notice, or
no curated content after the notice fail `validate-release` before documentation and native builds start. The publisher
and draft retries read the same immutable source document.

## Generated commit history

Keep the generated section out of the checked-in document. The helper appends `## Commit history` after all curated
content, then `Changes since <baseline>:` (with the baseline formatted as code) and the commit bullets. Versioned
releases select the nearest reachable earlier valid `l1-vX.Y.Z` tag. With no earlier eligible tag, the introduction is
`Initial L1 publication, including changes since L1 was introduced:` and the list includes L1's introduction commit. All
repository changes in the selected range are included, since shared changes can affect L1.

The composed body has one `# Dea/L1 X.Y.Z` heading and development notice, both supplied by the curated file. Its GitHub
release title is `Dea/L1 X.Y.Z`. The helper preserves the curated text and never writes generated history back to the
source document.

Snapshots keep automatically generated notes and require no curated file. Their baseline can be an earlier reachable L1
snapshot or versioned tag; their introductory phrase also ends with a colon.

Release assets, `make_latest=false`, and published-release immutability are unchanged. Follow [AGENTS.md][agent-policy]
for separate tag-creation, tag-push, and publication authorization. The workflow and note-composition policies are
recorded in [docs/decisions/0023-l1-release-workflow-policy.md][release-policy].

## Releases

- [l1/docs/releases/0.1.0.md][release-0-1-0] (prepared; publication pending)

[agent-policy]: ../../../AGENTS.md
[l0-notes]: ../../../l0/docs/releases/README.md
[release-0-1-0]: 0.1.0.md
[release-policy]: ../../../docs/decisions/0023-l1-release-workflow-policy.md
