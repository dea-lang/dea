# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Cross-editor smoke tests for the checked-in Dea support package."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


EDITORS_ROOT = Path(__file__).resolve().parents[1]
VSCODE_ROOT = EDITORS_ROOT / "vscode-dea"
FIXTURE_ROOT = VSCODE_ROOT / "test" / "fixtures"
STRICT_TOOLS = os.environ.get("STRICT_EDITOR_TOOLS") == "1"


class EditorSupportTests(unittest.TestCase):
    """Validate shared fixtures and lightweight editor integrations."""

    def _optional_tool(self, name: str) -> str:
        """Resolve an optional host tool or skip when it is unavailable.

        Args:
            name: Executable name to resolve on ``PATH``.

        Returns:
            Absolute or PATH-resolved executable name.
        """
        executable = shutil.which(name)
        if executable is not None:
            return executable
        if STRICT_TOOLS:
            self.fail(f"required editor smoke-test tool is unavailable: {name}")
        self.skipTest(f"{name} is not installed")

    def test_representative_and_incomplete_fixtures_are_present(self) -> None:
        fixture_names = {
            path.name for path in FIXTURE_ROOT.iterdir() if path.suffix in {".l0", ".l1"}
        }
        self.assertEqual(
            fixture_names,
            {
                "l0_hello.l0",
                "l0_incomplete.l0",
                "l0_surface.l0",
                "l1_incomplete.l1",
                "l1_slices.l1",
                "l1_surface.l1",
            },
        )

        l0_example = (FIXTURE_ROOT / "l0_hello.l0").read_text(encoding="utf-8")
        l0_surface = (FIXTURE_ROOT / "l0_surface.l0").read_text(encoding="utf-8")
        l1_example = (FIXTURE_ROOT / "l1_slices.l1").read_text(encoding="utf-8")
        l1_surface = (FIXTURE_ROOT / "l1_surface.l1").read_text(encoding="utf-8")
        incomplete = (
            (FIXTURE_ROOT / "l0_incomplete.l0").read_text(encoding="utf-8")
            + (FIXTURE_ROOT / "l1_incomplete.l1").read_text(encoding="utf-8")
        )

        self.assertIn("Minimized from l0/examples/hello.l0", l0_example)
        self.assertIn("你好，世界", l0_example)
        for spelling in ("std.io::printl_s", "with", "cleanup", "enum", "/**"):
            self.assertIn(spelling, l0_surface)

        self.assertIn("Minimized from l1/examples/slices.l1", l1_example)
        for spelling in (
            "export opaque",
            "unsafe func",
            "int[2][3]",
            "int[]",
            "1.25e+2",
            "right:",
            "int...",
            "const ratio",
        ):
            self.assertIn(spelling, l1_surface)

        for spelling in (
            "unterminated string",
            "unterminated block comment",
            "unterminated documentation comment",
            "match (value)",
            "case (value)",
            "with (let resource",
        ):
            self.assertIn(spelling, incomplete)

    def test_fallback_mappings_keep_language_levels_distinct(self) -> None:
        vim_detect = (EDITORS_ROOT / "vim" / "ftdetect" / "dea.vim").read_text(
            encoding="utf-8"
        )
        emacs_mode = (EDITORS_ROOT / "emacs" / "dea-mode.el").read_text(
            encoding="utf-8"
        )
        ctags = (EDITORS_ROOT / "ctags" / "dea.ctags").read_text(encoding="utf-8")

        self.assertIn("*.l0 setfiletype dea_l0", vim_detect)
        self.assertIn("*.l1 setfiletype dea_l1", vim_detect)
        self.assertIn(r"\\.l1\\'", emacs_mode)
        self.assertIn(r"\\.l[01]\\'", emacs_mode)
        self.assertIn("--map-Dea=+.l0", ctags)
        self.assertIn("--map-Dea=+.l1", ctags)

    def test_vim_detects_and_loads_both_syntaxes(self) -> None:
        vim = self._optional_tool("vim")
        for fixture_name, expected_filetype in (
            ("l0_surface.l0", "dea_l0"),
            ("l1_surface.l1", "dea_l1"),
        ):
            fixture = FIXTURE_ROOT / fixture_name
            runtime = EDITORS_ROOT / "vim"
            script = f"""
set nomore
execute 'set runtimepath^=' . fnameescape('{runtime.as_posix()}')
filetype on
syntax on
execute 'edit ' . fnameescape('{fixture.as_posix()}')
if &filetype !=# '{expected_filetype}'
  cquit 10
endif
if !exists('b:current_syntax') || b:current_syntax !=# '{expected_filetype}'
  cquit 11
endif
let declaration_line = search('^func ')
if declaration_line == 0
  cquit 12
endif
let declaration_column = match(getline(declaration_line), 'func') + 1
if synIDattr(synID(declaration_line, declaration_column, 1), 'name') !=# 'deaDeclaration'
  cquit 13
endif
quitall!
"""
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".vim", encoding="utf-8", delete=False
            ) as handle:
                handle.write(script)
                script_path = Path(handle.name)
            try:
                result = subprocess.run(
                    [vim, "-Nu", "NONE", "-n", "-es", "-S", str(script_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            finally:
                script_path.unlink(missing_ok=True)
            self.assertEqual(
                result.returncode,
                0,
                f"Vim failed for {fixture_name}:\n{result.stdout}\n{result.stderr}",
            )

    def test_emacs_loads_mode_for_both_extensions(self) -> None:
        emacs = self._optional_tool("emacs")
        l0_fixture = (FIXTURE_ROOT / "l0_surface.l0").as_posix()
        l1_fixture = (FIXTURE_ROOT / "l1_surface.l1").as_posix()
        expression = f"""
(progn
  (find-file "{l0_fixture}")
  (unless (and (eq major-mode 'dea-mode) (= dea-language-level 0))
    (kill-emacs 10))
  (font-lock-ensure)
  (kill-buffer)
  (find-file "{l1_fixture}")
  (unless (and (eq major-mode 'dea-mode) (= dea-language-level 1))
    (kill-emacs 11))
  (font-lock-ensure)
  (kill-buffer))
"""
        result = subprocess.run(
            [
                emacs,
                "-Q",
                "--batch",
                "-L",
                str(EDITORS_ROOT / "emacs"),
                "-l",
                "dea-mode.el",
                "--eval",
                expression,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Emacs mode smoke test failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_universal_ctags_indexes_only_supported_top_level_kinds(self) -> None:
        ctags = self._optional_tool("ctags")
        version = subprocess.run(
            [ctags, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        if "Universal Ctags" not in version.stdout + version.stderr:
            if STRICT_TOOLS:
                self.fail(f"{ctags} is not Universal Ctags")
            self.skipTest(f"{ctags} is not Universal Ctags")

        fixtures = [
            str(FIXTURE_ROOT / "l0_surface.l0"),
            str(FIXTURE_ROOT / "l1_surface.l1"),
        ]
        options = str(EDITORS_ROOT / "ctags" / "dea.ctags")
        result = subprocess.run(
            [
                ctags,
                "--options=NONE",
                f"--options={options}",
                "--output-format=json",
                "--fields=+K",
                "-f",
                "-",
                *fixtures,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Universal Ctags failed:\n{result.stdout}\n{result.stderr}",
        )

        tags = [
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.strip() and json.loads(line).get("_type") == "tag"
        ]
        tagged = {(tag["name"], tag["kind"]) for tag in tags}
        expected = {
            ("l0_surface", "module"),
            ("RawPointer", "type"),
            ("Cursor", "struct"),
            ("ParseResult", "enum"),
            ("monotonic_tick", "function"),
            ("parse", "function"),
            ("inspect", "function"),
            ("l1_surface", "module"),
            ("Handle", "struct"),
            ("Result", "enum"),
            ("Callback", "type"),
            ("Matrix", "type"),
            ("ratio", "constant"),
            ("mask", "constant"),
            ("external_read", "function"),
            ("first", "function"),
            ("choose", "function"),
            ("sum", "function"),
            ("demonstrate", "function"),
        }
        self.assertTrue(expected <= tagged, f"missing tags: {sorted(expected - tagged)}")
        for excluded_name in (
            "position",
            "number",
            "message",
            "parsed",
            "matrix",
            "row",
            "std.io",
            "assert",
        ):
            self.assertNotIn(excluded_name, {tag["name"] for tag in tags})

        with tempfile.TemporaryDirectory() as temp_dir:
            tags_path = Path(temp_dir) / "TAGS"
            etags = subprocess.run(
                [
                    ctags,
                    "--options=NONE",
                    f"--options={options}",
                    "-e",
                    "-f",
                    str(tags_path),
                    *fixtures,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                etags.returncode,
                0,
                f"ETAGS output failed:\n{etags.stdout}\n{etags.stderr}",
            )
            etags_text = tags_path.read_text(encoding="utf-8")
            self.assertIn("l0_surface", etags_text)
            self.assertIn("demonstrate", etags_text)


if __name__ == "__main__":
    unittest.main()
