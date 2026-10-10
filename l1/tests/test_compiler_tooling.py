#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Canonical compiler construction and validation-routing regressions."""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

L1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(L1_ROOT / "scripts"))
sys.path.insert(0, str(L1_ROOT / "compiler/scripts"))
from build_l1c import (L1BuildLayout, build_compiler, compiler_build_options,
                      host_compiler, write_compiler_wrapper, write_env_script)
import run_tests as normal_runner
import run_trace_tests as trace_runner

class CompilerToolingTests(unittest.TestCase):
    """Protect bootstrap isolation and focused validation coverage."""
    def test_windows_launchers_preserve_layout_with_spaces(self):
        """Render native Windows separators independently of the test host."""
        with tempfile.TemporaryDirectory(prefix="canonical launchers ") as temporary:
            root = Path(temporary)
            for relative in ("build/custom output", "build\\custom output", "build/custom\\output"):
                layout = L1BuildLayout(root, root / "build", root / "build/bin", relative, "../../..")
                with patch("build_l1c.is_windows_host", return_value=True):
                    write_compiler_wrapper(layout)
                    write_env_script(layout)
                expected = relative.replace("/", "\\")
                for name in ("l1c.cmd", "l1-env.cmd"):
                    text = (layout.bin_dir / name).read_text()
                    self.assertIn('set "L1_HOME=%REPO_ROOT%\\compiler"', text)
                    self.assertIn(f'set "L1_BUILD_DIR=%REPO_ROOT%\\{expected}"', text)
                    self.assertNotIn('set "L1_BUILD_DIR=%REPO_ROOT%\\different"', text)

    def test_normal_runner_ci_only_selection(self):
        """Default discovery excludes CI-only cases while selectors and CI mode retain access."""
        expected_ci_only = {
            "l1c_arc_trace_regression_test.py",
            "l1c_installed_preparation_test.py",
            "l1c_preparation_test.py",
            "slice_trace_test",
            "math_runtime_compile_test",
            "mul_runtime_compile_test",
            "preparation_ownership_test.py",
            "preparation_identity_test.py",
        }
        self.assertEqual(normal_runner.CI_ONLY_NORMAL_TESTS, expected_ci_only)
        discovered = normal_runner.discover_compiler_tests()
        normal = normal_runner.select_cases(discovered, [])
        included = normal_runner.select_cases(discovered, [], include_ci_only=True)
        self.assertEqual(len(included), len(discovered))
        self.assertFalse(expected_ci_only.intersection(case.name for case in normal))
        for name in expected_ci_only:
            self.assertEqual(
                [case.name for case in normal_runner.select_cases(discovered, [name])], [name],
            )
        self.assertTrue(
            {"mul_runtime_overflow_test.py", "l1c_managed_preparation_test.py"}.issubset(
                case.name for case in normal
            )
        )
        self.assertIn(
            "l1c_arc_trace_regression_test.py",
            normal_runner.CI_ONLY_NORMAL_TESTS,
        )
        self.assertTrue(
            any(
                case.name == "l1c_arc_trace_regression_test.py"
                for case in normal_runner.discover_compiler_tests()
            )
        )

        cases = [
            normal_runner.TestCase(0, "array_test", Path("array_test.l0"), "l0"),
            normal_runner.TestCase(1, "slice_trace_test", Path("slice_trace_test.l0"), "l0"),
        ]
        self.assertEqual(
            [case.name for case in normal_runner.select_cases(cases, [])],
            ["array_test"],
        )
        self.assertEqual(
            [case.name for case in normal_runner.select_cases(cases, ["slice_trace_test"])],
            ["slice_trace_test"],
        )
        self.assertEqual(
            [
                case.name
                for case in normal_runner.select_cases(
                    cases,
                    ["array_test"],
                    include_ci_only=True,
                )
            ],
            ["array_test"],
        )
        with self.assertRaises(ValueError):
            normal_runner.select_cases(cases, ["missing_test"])
        self.assertEqual(
            [case.name for case in normal_runner.select_cases(cases, [], include_ci_only=True)],
            ["array_test", "slice_trace_test"],
        )
        self.assertTrue(normal_runner.parse_args(["--include-ci-only"]).include_ci_only)
        help_output = io.StringIO()
        with self.assertRaises(SystemExit) as exit_result:
            with redirect_stdout(help_output):
                normal_runner.parse_args(["--help"])
        self.assertEqual(exit_result.exception.code, 0)
        self.assertIn("--include-ci-only", help_output.getvalue())


    def test_trace_selection_ignores_normal_cost_classification(self):
        """CI-only normal metadata must not remove dedicated trace coverage."""
        names = {case.name for case in trace_runner.select_trace_cases([])}
        self.assertIn("slice_trace_test", names)
        self.assertIn("mul_runtime_compile_test", names)
        self.assertNotIn("math_runtime_compile_test", names)
        self.assertEqual(
            [case.name for case in trace_runner.select_trace_cases(["math_runtime_compile_test"])],
            ["math_runtime_compile_test"],
        )
        self.assertIn(
            "math_runtime_compile_test",
            {case.name for case in trace_runner.select_trace_cases([], include_slow=True)},
        )


    @patch("build_l1c.shutil.which", side_effect=lambda name: "/tools/" + name if name in {"gcc", "clang", "custom"} else None)
    def test_host_selection_matches_driver(self, _which):
        """The explicit L0 C compiler wins; CC remains the driver's last fallback."""
        self.assertEqual(host_compiler({"L0_CC": "custom", "CC": "clang"}), "/tools/custom")
        self.assertEqual(host_compiler({"CC": "clang"}), "/tools/gcc")
        with self.assertRaises(RuntimeError):
            host_compiler({"L0_CC": "missing", "CC": "clang"})


    def test_runner_ignores_external_subject_override(self):
        """An inherited subject override cannot redirect the canonical suite."""
        scripts = Path(__file__).resolve().parents[1] / "compiler/scripts"
        code = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "from test_runner_common import build_repo_test_env; "
            "assert 'L1_TEST_COMPILER' not in build_repo_test_env('build/dea', Path('build/dea'))"
        )
        subprocess.run([sys.executable, "-c", code, str(scripts)],
                       env={**os.environ, "L1_TEST_COMPILER": "/missing/poison-subject"}, check=True)


    def test_build_info_overlay_is_private_and_narrow(self):
        """Only the requested module shadows sources and scratch survives through the build."""
        fallback = L1_ROOT / "compiler/src/build_info.l0"
        original = fallback.read_bytes()
        with tempfile.TemporaryDirectory(prefix="overlay with spaces ") as temporary:
            root = Path(temporary)
            overlay = root / "package-info.l0"
            overlay.write_bytes(b"module build_info;\n// private metadata\n")
            (root / "l1c.l0").write_text("poison sibling")
            output = root / "package/bin/l1c.native"
            seen_roots = []

            def construct(command, **kwargs):
                roots = [Path(command[i + 1]) for i, arg in enumerate(command) if arg == "--project-root"]
                seen_roots.extend(roots)
                self.assertEqual(len(roots), 2)
                self.assertEqual(roots[1], fallback.parent)
                self.assertNotEqual(roots[0], overlay.parent)
                self.assertEqual([path.name for path in roots[0].iterdir()], ["build_info.l0"])
                self.assertEqual((roots[0] / "build_info.l0").read_bytes(), overlay.read_bytes())
                self.assertEqual(fallback.read_bytes(), original)
                self.assertIn("--keep-c", command)
                self.assertNotIn("L0_HOME", kwargs["env"])
                self.assertNotIn("L0_SYSTEM", kwargs["env"])
                output.write_bytes(b"native compiler")

            env = {"L0_CC": "test-cc", "L0_HOME": "/stale/install", "L0_SYSTEM": "/stale/interfaces"}
            with patch("build_l1c.host_compiler", return_value="test-cc"), \
                    patch("build_l1c.subprocess.run", side_effect=construct):
                command = build_compiler(root / "seed", output, env, keep_c=True, build_info_overlay=overlay)
            self.assertEqual(command[0], str(root / "seed"))
            self.assertEqual(command[command.index("-o") + 1], str(output))
            self.assertIn(str(seen_roots[0]), command)
            self.assertFalse(seen_roots[0].exists())
            self.assertEqual(fallback.read_bytes(), original)
            self.assertEqual(env["L0_HOME"], "/stale/install")
            self.assertEqual(overlay.read_bytes(), b"module build_info;\n// private metadata\n")


    def test_build_info_overlay_failure_cleans_scratch(self):
        """Compiler rejection removes private metadata without touching the supplied module."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            overlay = root / "build_info.l0"
            overlay.write_text("invalid module")
            output = root / "bin/compiler"
            with patch("build_l1c.host_compiler", return_value="test-cc"), \
                    patch("build_l1c.subprocess.run", side_effect=subprocess.CalledProcessError(1, "seed")):
                with self.assertRaises(subprocess.CalledProcessError):
                    build_compiler(root / "seed", output, {}, build_info_overlay=overlay)
            self.assertEqual(list(output.parent.iterdir()), [])
            self.assertEqual(overlay.read_text(), "invalid module")


    def test_missing_build_info_overlay_fails_before_construction(self):
        """An explicit missing module never falls back to source-tree metadata."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("build_l1c.subprocess.run") as support:
                with self.assertRaises(FileNotFoundError):
                    build_compiler(root / "seed", root / "bin/compiler", {},
                                   build_info_overlay=root / "missing.l0")
                support.assert_not_called()
            self.assertFalse((root / "bin").exists())


    def test_default_build_has_no_overlay(self):
        """Existing callers keep the original source root and fallback metadata."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "l1c.native"

            def construct(command, **_kwargs):
                roots = [command[i + 1] for i, arg in enumerate(command) if arg == "--project-root"]
                self.assertEqual(roots, [str(L1_ROOT / "compiler/src")])
                output.write_bytes(b"native compiler")

            with patch("build_l1c.host_compiler", return_value="test-cc"), \
                    patch("build_l1c.subprocess.run", side_effect=construct):
                command = build_compiler(root / "seed", output, {})
            layout = L1BuildLayout(root, root, root, ".", ".")
            recorded = compiler_build_options(layout)
            self.assertEqual(command[1:], recorded)


if __name__ == "__main__":
    unittest.main()
