#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Focused tests for the ADR Impact policy checker."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import check_adr_impact as checker


ROOT_PLAN = "work/plans/tools/2026-07-26-policy.md"
L1_PLAN = "l1/work/plans/features/2026-07-26-feature.md"
L1_CLOSED = "l1/work/plans/features/closed/2026-07-26-feature.md"
ROOT_ADR = "docs/decisions/0011-policy.md"
L1_ADR = "l1/docs/decisions/0022-feature.md"


def impact(
    *,
    decision: str = "Adopt the durable contract.",
    scope: str = "Shared",
    disposition: str = "New ADR",
    adr: str = "docs/decisions/",
    rationale: str = "This records a durable architectural constraint.",
) -> str:
    return (
        "# Plan\n\n"
        "## ADR Impact\n\n"
        f"- Decision: {decision}\n"
        f"  - Scope: {scope}\n"
        f"  - Disposition: {disposition}\n"
        f"  - ADR: `{adr}`\n"
        f"  - Rationale: {rationale}\n"
    )


def adr_index(name: str) -> str:
    return f"# ADR Index\n\n| ADR | Title |\n| --- | --- |\n| [entry]({name}) | Test |\n"


def adr_with_plan(adr_path: str, plan_path: str) -> str:
    relative = Path(plan_path)
    base = Path(adr_path).parent
    target = Path(
        __import__("os").path.relpath(relative.as_posix(), base.as_posix())
    ).as_posix()
    return (
        "# ADR\n\n"
        "## Related Plans\n\n"
        f"- [{plan_path}]({target})\n\n"
        "## Current Docs\n\n"
        "- None yet.\n"
    )


class DictTree:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = files

    def paths(self) -> set[str]:
        return set(self.files)

    def read_text(self, path: str) -> str:
        return self.files[path]


def messages(diagnostics: list[checker.Diagnostic]) -> str:
    return "\n".join(item.render() for item in diagnostics)


class ParsingTests(unittest.TestCase):
    def test_missing_duplicate_and_empty_sections_are_reported(self) -> None:
        _, missing = checker.parse_impact(ROOT_PLAN, "# Plan\n")
        self.assertIn("missing required", messages(missing))

        duplicate_text = (
            impact()
            + "\n## ADR Impact\n\n"
            + "- Decision: Another.\n"
        )
        _, duplicate = checker.parse_impact(ROOT_PLAN, duplicate_text)
        self.assertIn("duplicate '## ADR Impact'", messages(duplicate))

        _, empty = checker.parse_impact(ROOT_PLAN, "# Plan\n\n## ADR Impact\n")
        self.assertIn("at least one decision", messages(empty))

    def test_malformed_empty_duplicate_and_unknown_fields_are_reported(self) -> None:
        text = (
            "# Plan\n\n## ADR Impact\n\n"
            "- Decision:\n"
            "  - Scope: Shared\n"
            "  - Scope: Shared\n"
            "  - Disposition: Pending\n"
            "  - ADR: None\n"
            "  - Rationale:\n"
            "  - Surprise: value\n"
            "not a nested record line\n"
        )
        _, diagnostics = checker.parse_impact(ROOT_PLAN, text)
        rendered = messages(diagnostics)
        self.assertIn("Decision must not be empty", rendered)
        self.assertIn("duplicate ADR Impact field 'Scope'", rendered)
        self.assertIn("field 'Rationale' must not be empty", rendered)
        self.assertIn("unknown ADR Impact field 'Surprise'", rendered)
        self.assertIn("malformed ADR Impact record line", rendered)

    def test_repeated_records_and_wrapped_rationale_parse(self) -> None:
        text = (
            impact()
            + "\n"
            + "- Decision: Keep another\n"
            + "  durable contract.\n"
            + "  - Scope: Shared\n"
            + "  - Disposition: Pending\n"
            + "  - ADR: None\n"
            + "  - Rationale: Resolution remains\n"
            + "    intentionally pending during active design.\n"
        )
        records, diagnostics = checker.parse_impact(ROOT_PLAN, text)
        self.assertEqual([], diagnostics)
        self.assertEqual(2, len(records))
        self.assertEqual("Keep another durable contract.", records[1].decision)
        self.assertIn("intentionally pending", records[1].values["Rationale"])

    def test_fenced_and_commented_fake_sections_do_not_satisfy_policy(self) -> None:
        fenced = (
            "# Plan\n\n"
            "```markdown\n"
            + impact()
            + "```\n"
        )
        _, fenced_diagnostics = checker.parse_impact(ROOT_PLAN, fenced)
        self.assertIn("missing required", messages(fenced_diagnostics))

        commented = (
            "# Plan\n\n<!--\n"
            + impact()
            + "-->\n"
        )
        _, comment_diagnostics = checker.parse_impact(ROOT_PLAN, commented)
        self.assertIn("missing required", messages(comment_diagnostics))

    def test_fake_sections_do_not_conflict_with_one_visible_section(self) -> None:
        text = (
            "# Plan\n\n"
            "<!-- ## ADR Impact -->\n\n"
            "~~~markdown\n"
            "## ADR Impact\n"
            "~~~\n\n"
            + impact()
        )
        records, diagnostics = checker.parse_impact(ROOT_PLAN, text)
        self.assertEqual([], diagnostics)
        self.assertEqual(1, len(records))

    def test_unclosed_comment_literal_inside_fence_does_not_mask_real_section(
        self,
    ) -> None:
        text = (
            "# Plan\n\n"
            "```markdown\n"
            "<!-- literal unclosed sample comment\n"
            "## ADR Impact\n"
            "```\n\n"
            + impact()
        )
        records, diagnostics = checker.parse_impact(ROOT_PLAN, text)
        self.assertEqual([], diagnostics)
        self.assertEqual(1, len(records))


class DiscoveryTests(unittest.TestCase):
    def test_discovers_plans_and_initiatives_but_excludes_support_files(self) -> None:
        active = {
            "work/plans/tools/a.md",
            "l0/work/plans/features/a.md",
            "l1/work/initiatives/0001-x.md",
        }
        for path in active:
            self.assertTrue(checker.is_active_document(path), path)
        for path in {
            "work/plans/tools/README.md",
            "work/plans/tools/attachments/a.md",
            "work/plans/tools/closed/a.md",
            "l1/work/initiatives/closed/0001-x.md",
            "work/proposals/a.md",
        }:
            self.assertFalse(checker.is_active_document(path), path)

        closed = {
            "work/plans/tools/closed/a.md",
            "l0/work/plans/features/closed/a.md",
            "l1/work/initiatives/closed/0001-x.md",
        }
        for path in closed:
            self.assertTrue(checker.is_closed_document(path), path)

    def test_untouched_closed_history_is_grandfathered(self) -> None:
        tree = DictTree(
            {
                ROOT_PLAN: impact(),
                "work/plans/tools/closed/legacy.md": "# Legacy\n",
            }
        )
        self.assertEqual([], checker.validate_selected_tree(tree))
        diagnostics = checker.validate_selected_tree(
            tree, [checker.ChangedPath("M", "work/plans/tools/closed/legacy.md")]
        )
        self.assertIn("missing required", messages(diagnostics))

    def test_deletion_and_move_out_preserve_source_side_violations(self) -> None:
        active = "work/plans/tools/active.md"
        closed = "work/plans/tools/closed/closed.md"
        deletion = checker.validate_lifecycle_changes(
            [checker.ChangedPath("D", active)]
        )
        self.assertIn("deleting an active", messages(deletion))

        move_out = checker.validate_lifecycle_changes(
            [checker.ChangedPath("R100", "notes/active.md", active)]
        )
        self.assertIn("non-lifecycle destination", messages(move_out))

        reopen = checker.validate_lifecycle_changes(
            [checker.ChangedPath("R100", active, closed)]
        )
        self.assertIn("moving a closed", messages(reopen))

    def test_recognized_lifecycle_renames_are_allowed(self) -> None:
        changes = [
            checker.ChangedPath(
                "R100",
                "work/plans/features/new-name.md",
                "work/plans/tools/old-name.md",
            ),
            checker.ChangedPath(
                "R100",
                "work/plans/tools/closed/closed.md",
                "work/plans/tools/active.md",
            ),
            checker.ChangedPath(
                "R100",
                "work/plans/features/closed/new-name.md",
                "work/plans/tools/closed/old-name.md",
            ),
        ]
        self.assertEqual([], checker.validate_lifecycle_changes(changes))


class ContractTests(unittest.TestCase):
    def test_pending_is_active_only_and_requires_no_adr(self) -> None:
        text = impact(
            scope="L1",
            disposition="Pending",
            adr="None",
            rationale="The final conversion contract remains unresolved.",
        )
        tree = DictTree({L1_PLAN: text})
        self.assertEqual([], checker.validate_selected_tree(tree))

        tree = DictTree({L1_CLOSED: text})
        diagnostics = checker.validate_selected_tree(
            tree, [checker.ChangedPath("M", L1_CLOSED)]
        )
        self.assertIn("Pending is allowed only", messages(diagnostics))

    def test_not_warranted_is_scoped_to_na_and_must_be_sole_record(self) -> None:
        valid = impact(
            scope="N/A",
            disposition="ADR not warranted",
            adr="None",
            rationale="This is only local source organization.",
        )
        self.assertEqual(
            [], checker.validate_selected_tree(DictTree({L1_PLAN: valid}))
        )
        mixed = valid + "\n" + (
            "- Decision: Another durable choice.\n"
            "  - Scope: L1\n"
            "  - Disposition: Pending\n"
            "  - ADR: None\n"
            "  - Rationale: The design still requires resolution.\n"
        )
        diagnostics = checker.validate_selected_tree(DictTree({L1_PLAN: mixed}))
        self.assertIn("must be the sole", messages(diagnostics))

    def test_na_scope_is_rejected_for_every_other_disposition(self) -> None:
        for disposition, adr in (
            ("Pending", "None"),
            ("New ADR", "l1/docs/decisions/"),
            ("Amend ADR", L1_ADR),
            ("Covered by ADR", L1_ADR),
        ):
            tree = DictTree(
                {
                    L1_PLAN: impact(
                        scope="N/A", disposition=disposition, adr=adr
                    ),
                    L1_ADR: "# ADR\n",
                    "l1/docs/decisions/INDEX.md": adr_index(
                        "0022-feature.md"
                    ),
                }
            )
            self.assertIn(
                "requires a real scope",
                messages(checker.validate_selected_tree(tree)),
                disposition,
            )

    def test_all_root_and_level_scopes_route_to_the_expected_directory(self) -> None:
        for scope in ("Dea-wide", "Shared", "Repository/tooling"):
            tree = DictTree({ROOT_PLAN: impact(scope=scope)})
            self.assertEqual([], checker.validate_selected_tree(tree), scope)
        for scope in ("L0", "L1", "L12"):
            level = scope.lower()
            path = f"{level}/work/plans/features/feature.md"
            target = f"{level}/docs/decisions/"
            tree = DictTree({path: impact(scope=scope, adr=target)})
            self.assertEqual([], checker.validate_selected_tree(tree), scope)

    def test_sibling_is_rejected_but_root_may_carry_level_scope(self) -> None:
        sibling = DictTree(
            {L1_PLAN: impact(scope="L0", adr="l0/docs/decisions/")}
        )
        self.assertIn(
            "outside the source document's ownership",
            messages(checker.validate_selected_tree(sibling)),
        )
        root_level = DictTree(
            {ROOT_PLAN: impact(scope="L1", adr="l1/docs/decisions/")}
        )
        self.assertEqual([], checker.validate_selected_tree(root_level))

    def test_existing_adr_must_exist_and_be_indexed(self) -> None:
        plan = impact(
            scope="L1",
            disposition="Covered by ADR",
            adr=L1_ADR,
        )
        missing = checker.validate_selected_tree(DictTree({L1_PLAN: plan}))
        self.assertIn("does not exist", messages(missing))

        files = {
            L1_PLAN: plan,
            L1_ADR: "# ADR\n",
            "l1/docs/decisions/INDEX.md": "# Empty index\n",
        }
        unindexed = checker.validate_selected_tree(DictTree(files))
        self.assertIn("not listed", messages(unindexed))

        files["l1/docs/decisions/INDEX.md"] = adr_index("0022-feature.md")
        self.assertEqual([], checker.validate_selected_tree(DictTree(files)))

    def test_index_links_cannot_escape_and_reenter_the_repository(self) -> None:
        files = {
            ROOT_ADR: "# ADR\n",
            "docs/decisions/INDEX.md": adr_index(
                "../../../docs/decisions/0011-policy.md"
            ),
        }
        tree = DictTree(files)
        self.assertEqual(set(), checker.indexed_adrs(tree, "docs/decisions/"))
        files["docs/decisions/INDEX.md"] = adr_index("0011-policy.md")
        self.assertEqual(
            {ROOT_ADR}, checker.indexed_adrs(tree, "docs/decisions/")
        )

    def test_all_existing_adr_dispositions_accept_an_indexed_target(self) -> None:
        for disposition in ("Amend ADR", "Covered by ADR"):
            plan = impact(
                scope="L1", disposition=disposition, adr=L1_ADR
            )
            files = {
                L1_PLAN: plan,
                L1_ADR: "# ADR\n",
                "l1/docs/decisions/INDEX.md": adr_index("0022-feature.md"),
            }
            self.assertEqual(
                [], checker.validate_selected_tree(DictTree(files)), disposition
            )

    def test_invalid_scope_disposition_and_short_rationale_are_reported(self) -> None:
        text = impact(
            scope="Everywhere",
            disposition="Maybe",
            adr="None",
            rationale="Too short",
        )
        rendered = messages(checker.validate_selected_tree(DictTree({ROOT_PLAN: text})))
        self.assertIn("invalid ADR Impact scope", rendered)
        self.assertIn("invalid ADR Impact disposition", rendered)
        self.assertIn("substantive explanation", rendered)


class ClosureTests(unittest.TestCase):
    def closure_tree(
        self,
        disposition: str,
        *,
        link_plan: bool = True,
        indexed: bool = True,
    ) -> DictTree:
        plan = impact(
            scope="L1",
            disposition=disposition,
            adr=L1_ADR,
        )
        adr = (
            adr_with_plan(L1_ADR, L1_CLOSED) if link_plan else "# ADR\n"
        )
        index = (
            adr_index("0022-feature.md") if indexed else "# Empty index\n"
        )
        return DictTree(
            {
                L1_CLOSED: plan,
                L1_ADR: adr,
                "l1/docs/decisions/INDEX.md": index,
            }
        )

    def closure_base_tree(
        self,
        disposition: str,
        *,
        link_plan: bool = False,
        include_adr: bool | None = None,
        indexed: bool | None = None,
    ) -> DictTree:
        if include_adr is None:
            include_adr = disposition != "New ADR"
        if indexed is None:
            indexed = disposition != "New ADR"
        files = {
            "l1/docs/decisions/INDEX.md": (
                adr_index("0022-feature.md") if indexed else "# Empty index\n"
            )
        }
        if include_adr:
            files[L1_ADR] = (
                adr_with_plan(L1_ADR, L1_CLOSED)
                if link_plan
                else "# ADR\n\n## Related Plans\n\n- None yet.\n"
            )
        return DictTree(files)

    def test_new_adr_closure_requires_adr_index_and_related_plan_link(self) -> None:
        tree = self.closure_tree("New ADR", link_plan=False)
        changed = [checker.ChangedPath("A", L1_CLOSED)]
        base_tree = self.closure_base_tree("New ADR")
        rendered = messages(
            checker.validate_selected_tree(
                tree, changed, base_tree=base_tree
            )
        )
        self.assertIn(f"requires {L1_ADR} to be added", rendered)
        self.assertIn("INDEX.md to change", rendered)
        self.assertIn("must link this document", rendered)

        complete = [
            checker.ChangedPath("A", L1_CLOSED),
            checker.ChangedPath("A", L1_ADR),
            checker.ChangedPath("M", "l1/docs/decisions/INDEX.md"),
        ]
        self.assertEqual(
            [],
            checker.validate_selected_tree(
                self.closure_tree("New ADR"),
                complete,
                base_tree=base_tree,
            ),
        )

    def test_amended_and_covered_closures_require_same_change_evidence(self) -> None:
        for disposition in ("Amend ADR", "Covered by ADR"):
            tree = self.closure_tree(disposition)
            base_tree = self.closure_base_tree(disposition)
            incomplete = [checker.ChangedPath("A", L1_CLOSED)]
            self.assertIn(
                "to exist in the base tree and change",
                messages(
                    checker.validate_selected_tree(
                        tree, incomplete, base_tree=base_tree
                    )
                ),
            )
            complete = incomplete + [checker.ChangedPath("M", L1_ADR)]
            self.assertEqual(
                [],
                checker.validate_selected_tree(
                    tree, complete, base_tree=base_tree
                ),
                disposition,
            )

    def test_new_adr_rejects_an_existing_file_changed_as_modified(self) -> None:
        changes = [
            checker.ChangedPath("A", L1_CLOSED),
            checker.ChangedPath("M", L1_ADR),
            checker.ChangedPath("M", "l1/docs/decisions/INDEX.md"),
        ]
        rendered = messages(
            checker.validate_selected_tree(
                self.closure_tree("New ADR"),
                changes,
                base_tree=self.closure_base_tree(
                    "New ADR", include_adr=True, indexed=True
                ),
            )
        )
        self.assertIn(f"requires {L1_ADR} to be added", rendered)

    def test_amended_and_covered_adrs_must_exist_in_the_base_tree(self) -> None:
        for disposition in ("Amend ADR", "Covered by ADR"):
            changes = [
                checker.ChangedPath("A", L1_CLOSED),
                checker.ChangedPath("A", L1_ADR),
            ]
            rendered = messages(
                checker.validate_selected_tree(
                    self.closure_tree(disposition),
                    changes,
                    base_tree=self.closure_base_tree(
                        disposition, include_adr=False, indexed=False
                    ),
                )
            )
            self.assertIn("to exist in the base tree", rendered, disposition)

    def test_active_to_closed_rename_is_a_closure_but_closed_rename_is_not(self) -> None:
        self.assertTrue(
            checker.ChangedPath("R100", L1_CLOSED, L1_PLAN).is_closure
        )
        old_closed = L1_CLOSED.replace("feature.md", "old.md")
        self.assertFalse(
            checker.ChangedPath("R100", L1_CLOSED, old_closed).is_closure
        )

    def test_added_active_covered_plan_does_not_require_closure_evidence(self) -> None:
        plan = impact(
            scope="L1",
            disposition="Covered by ADR",
            adr=L1_ADR,
        )
        files = {
            L1_PLAN: plan,
            L1_ADR: "# ADR\n\n## Related Plans\n\n- None yet.\n",
            "l1/docs/decisions/INDEX.md": adr_index("0022-feature.md"),
        }
        tree = DictTree(files)
        base_tree = DictTree(
            {
                L1_ADR: files[L1_ADR],
                "l1/docs/decisions/INDEX.md": files[
                    "l1/docs/decisions/INDEX.md"
                ],
            }
        )
        added = checker.ChangedPath("A", L1_PLAN)
        self.assertFalse(added.is_closure)
        self.assertEqual(
            [],
            checker.validate_selected_tree(
                tree, [added], base_tree=base_tree
            ),
        )

    def test_related_plans_accepts_document_wide_reference_links(self) -> None:
        relative = "../../work/plans/features/closed/2026-07-26-feature.md"
        adr_text = (
            "# ADR\n\n"
            "## Related Plans\n\n"
            "- [Closed feature][Feature Plan]\n"
            "- [another unrelated reference]\n\n"
            "## Current Docs\n\n"
            "- None yet.\n\n"
            f"[  feature   plan ]: <{relative}>\n"
            "[another unrelated reference]: ../../../work/plans/closed/nope.md\n"
        )
        self.assertTrue(
            checker.related_plan_link_exists(L1_ADR, adr_text, L1_CLOSED)
        )

    def test_related_plans_rejects_unresolved_or_wrong_reference_links(self) -> None:
        unresolved = (
            "# ADR\n\n"
            "## Related Plans\n\n"
            "- [Closed feature][missing]\n"
        )
        self.assertFalse(
            checker.related_plan_link_exists(L1_ADR, unresolved, L1_CLOSED)
        )
        wrong = (
            "# ADR\n\n"
            "## Related Plans\n\n"
            "- [Closed feature][]\n\n"
            "[Closed feature]: ../../../work/plans/features/closed/other.md\n"
        )
        self.assertFalse(
            checker.related_plan_link_exists(L1_ADR, wrong, L1_CLOSED)
        )

    def test_related_plans_rejects_root_escape_and_leading_slash_targets(self) -> None:
        closed = "work/plans/tools/closed/2026-07-26-policy.md"
        normal = (
            "# ADR\n\n"
            "## Related Plans\n\n"
            f"- [plan](../../{closed})\n"
        )
        self.assertTrue(
            checker.related_plan_link_exists(ROOT_ADR, normal, closed)
        )

        escaping = normal.replace(f"../../{closed}", f"../../../{closed}")
        self.assertFalse(
            checker.related_plan_link_exists(ROOT_ADR, escaping, closed)
        )
        absolute = normal.replace(f"../../{closed}", f"/{closed}")
        self.assertFalse(
            checker.related_plan_link_exists(ROOT_ADR, absolute, closed)
        )


class GitModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "ADR Impact Tests")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *arguments: str) -> str:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=self.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_main(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = checker.main(arguments, root=self.root)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_all_active_staged_and_base_head_read_the_selected_tree(self) -> None:
        self.write(ROOT_PLAN, impact())
        base = self.commit("base")

        code, stdout, _ = self.run_main(["--all-active"])
        self.assertEqual(0, code)
        self.assertIn("passed", stdout)

        self.write(ROOT_PLAN, "# invalid working tree only\n")
        code, _, stderr = self.run_main(["--staged"])
        self.assertEqual(0, code, stderr)

        self.git("add", ROOT_PLAN)
        code, _, stderr = self.run_main(["--staged"])
        self.assertEqual(1, code)
        self.assertIn("missing required", stderr)

        head = self.commit("invalid head")
        code, _, stderr = self.run_main(["--base", base, "--head", head])
        self.assertEqual(1, code)
        self.assertIn("missing required", stderr)

    def test_git_diff_parser_handles_rename_destinations(self) -> None:
        self.write(L1_PLAN, impact(scope="L1", disposition="Pending", adr="None"))
        self.commit("active")
        target = self.root / L1_CLOSED
        target.parent.mkdir(parents=True, exist_ok=True)
        (self.root / L1_PLAN).rename(target)
        self.git("add", "-A")
        changes = checker.changed_paths(self.root, staged=True)
        matching = [change for change in changes if change.path == L1_CLOSED]
        self.assertEqual(1, len(matching))
        self.assertTrue(matching[0].status.startswith("R"))
        self.assertTrue(matching[0].is_closure)

    def test_staged_mode_rejects_lifecycle_deletion_and_move_out(self) -> None:
        self.write(ROOT_PLAN, impact())
        self.commit("active")
        self.git("rm", "-q", ROOT_PLAN)
        code, _, stderr = self.run_main(["--staged"])
        self.assertEqual(1, code)
        self.assertIn("deleting an active lifecycle document", stderr)

        self.git("reset", "-q", "--hard", "HEAD")
        outside = "notes/policy.md"
        target = self.root / outside
        target.parent.mkdir(parents=True, exist_ok=True)
        (self.root / ROOT_PLAN).rename(target)
        self.git("add", "-A")
        code, _, stderr = self.run_main(["--staged"])
        self.assertEqual(1, code)
        self.assertIn("non-lifecycle destination", stderr)

    def test_low_similarity_delete_add_active_to_closed_is_reconciled(self) -> None:
        initial = (
            impact(
                scope="L1",
                disposition="Pending",
                adr="None",
                rationale="The active design still requires final resolution.",
            )
            + "\n## Design Notes\n\n"
            + "\n".join(f"- Original design note {index}" for index in range(120))
            + "\n"
        )
        self.write(L1_PLAN, initial)
        base = self.commit("active plan")

        closed_text = (
            impact(
                scope="N/A",
                disposition="ADR not warranted",
                adr="None",
                rationale="The completed work only changes local implementation mechanics.",
            )
            + "\n## Completion Notes\n\n"
            + "\n".join(
                f"- Entirely rewritten completion evidence {index}"
                for index in range(120)
            )
            + "\n"
        )
        (self.root / L1_PLAN).unlink()
        self.write(L1_CLOSED, closed_text)
        head = self.commit("close rewritten plan")

        changes = checker.changed_paths(self.root, base=base, head=head)
        self.assertIn(
            ("D", L1_PLAN),
            {(change.status[0], change.path) for change in changes},
        )
        self.assertIn(
            ("A", L1_CLOSED),
            {(change.status[0], change.path) for change in changes},
        )
        code, _, stderr = self.run_main(
            ["--base", base, "--head", head]
        )
        self.assertEqual(0, code, stderr)

    def test_covered_closure_rejects_a_preexisting_related_plan_link(self) -> None:
        self.write(
            L1_PLAN,
            impact(
                scope="L1",
                disposition="Covered by ADR",
                adr=L1_ADR,
            ),
        )
        self.write(
            "l1/docs/decisions/INDEX.md", adr_index("0022-feature.md")
        )
        original_adr = adr_with_plan(L1_ADR, L1_CLOSED)
        self.write(L1_ADR, original_adr)
        base = self.commit("prelinked base")

        closed = self.root / L1_CLOSED
        closed.parent.mkdir(parents=True, exist_ok=True)
        (self.root / L1_PLAN).rename(closed)
        self.write(L1_ADR, original_adr + "\n<!-- unrelated edit -->\n")
        head = self.commit("close plan")

        code, _, stderr = self.run_main(
            ["--base", base, "--head", head]
        )
        self.assertEqual(1, code)
        self.assertIn("link to be added by the closure change", stderr)

    def test_new_closure_rejects_a_dangling_base_index_entry(self) -> None:
        self.write(
            L1_PLAN,
            impact(scope="L1", disposition="New ADR", adr="l1/docs/decisions/"),
        )
        original_index = adr_index("0022-feature.md")
        self.write("l1/docs/decisions/INDEX.md", original_index)
        base = self.commit("dangling index base")

        closed = self.root / L1_CLOSED
        closed.parent.mkdir(parents=True, exist_ok=True)
        (self.root / L1_PLAN).rename(closed)
        self.write(
            L1_CLOSED,
            impact(scope="L1", disposition="New ADR", adr=L1_ADR),
        )
        self.write(L1_ADR, adr_with_plan(L1_ADR, L1_CLOSED))
        self.write(
            "l1/docs/decisions/INDEX.md",
            original_index + "\n<!-- closure edit -->\n",
        )
        head = self.commit("close with new ADR")

        code, _, stderr = self.run_main(
            ["--base", base, "--head", head]
        )
        self.assertEqual(1, code)
        self.assertIn("index entry already exists in the base tree", stderr)

    def test_push_range_does_not_apply_a_later_policy_to_an_earlier_closure(
        self,
    ) -> None:
        legacy_active = "work/plans/tools/legacy.md"
        legacy_closed = "work/plans/tools/closed/legacy.md"
        self.write(legacy_active, "# Legacy plan without ADR impact\n")
        base = self.commit("base before ADR policy")

        closed = self.root / legacy_closed
        closed.parent.mkdir(parents=True, exist_ok=True)
        (self.root / legacy_active).rename(closed)
        self.commit("close legacy plan")

        self.write(checker.CHECKER_PATH, "# ADR checker introduced here\n")
        head = self.commit("introduce ADR policy")

        aggregate_code, _, aggregate_stderr = self.run_main(
            ["--base", base, "--head", head]
        )
        self.assertEqual(1, aggregate_code)
        self.assertIn("missing required", aggregate_stderr)

        code, _, stderr = self.run_main(
            ["--push-base", base, "--head", head]
        )
        self.assertEqual(0, code, stderr)

    def test_push_range_preserves_an_adr_added_before_a_covered_closure(
        self,
    ) -> None:
        self.write(checker.CHECKER_PATH, "# Existing ADR checker\n")
        self.write(
            L1_PLAN,
            impact(scope="L1", disposition="New ADR", adr="l1/docs/decisions/"),
        )
        base = self.commit("active plan before ADR")

        self.write(
            "l1/docs/decisions/INDEX.md", adr_index("0022-feature.md")
        )
        self.write(
            L1_ADR,
            "# ADR\n\n## Related Plans\n\n- None yet.\n",
        )
        self.commit("add ADR")

        closed = self.root / L1_CLOSED
        closed.parent.mkdir(parents=True, exist_ok=True)
        (self.root / L1_PLAN).rename(closed)
        self.write(
            L1_CLOSED,
            impact(scope="L1", disposition="Covered by ADR", adr=L1_ADR),
        )
        self.write(L1_ADR, adr_with_plan(L1_ADR, L1_CLOSED))
        head = self.commit("close plan covered by existing ADR")

        aggregate_code, _, aggregate_stderr = self.run_main(
            ["--base", base, "--head", head]
        )
        self.assertEqual(1, aggregate_code)
        self.assertIn("target is absent from the base tree", aggregate_stderr)

        code, _, stderr = self.run_main(
            ["--push-base", base, "--head", head]
        )
        self.assertEqual(0, code, stderr)

    def test_invocation_and_repository_failures_return_two(self) -> None:
        code, _, _ = self.run_main(["--base", "HEAD"])
        self.assertEqual(2, code)
        code, _, _ = self.run_main(["--push-base", "HEAD"])
        self.assertEqual(2, code)
        code, _, stderr = self.run_main(
            ["--base", "not-a-commit", "--head", "also-not-a-commit"]
        )
        self.assertEqual(2, code)
        self.assertIn("repository error", stderr)


if __name__ == "__main__":
    unittest.main()
