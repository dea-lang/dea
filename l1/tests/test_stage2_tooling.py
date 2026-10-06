#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression checks for strict fixed-point evidence and Stage 2 construction."""

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
STAGE2_SCRIPTS = L1_ROOT / "compiler/stage2_l1/scripts"
sys.path.insert(0, str(L1_ROOT / "scripts"))
sys.path.insert(0, str(STAGE2_SCRIPTS))
from build_stage2_l1c import build_compiler, compiler_build_env, build_support_objects, write_stage2_wrapper, host_compiler
from build_stage1_l1c import L1BuildLayout, write_relative_alias
from triple_bootstrap import compare_trees, input_manifest
from bootstrap_identity import assert_stable_native_toolchain, compiler_command_words, merge_cflags
import run_tests as stage2_normal_runner
import run_trace_tests as stage2_trace_runner


class Stage2ToolingTests(unittest.TestCase):
    """Prevent false fixed points and accidental stage/bridge selection."""

    def test_validation_tiers_and_ci_union(self):
        """L1 Make targets keep local tiers distinct from the exhaustive CI union."""
        makefile = Path(__file__).resolve().parents[1] / "Makefile"
        text = makefile.read_text(encoding="utf-8")

        self.assertIn(
            "L1_TEST_STAGE1_SMOKE_TESTS := array_test parser_test analysis_test expr_types_test "
            "interface_test backend_test c_emitter_test driver_test",
            text,
        )
        self.assertIn("L1_TEST_STAGE2_SMOKE_TESTS := array_test parser_test", text)
        self.assertIn(
            "test: test-stage1-smoke test-stage2-smoke test-stage-parity check-examples "
            "test-docker-wine-runner test-stage2-tooling test-productization",
            text,
        )
        self.assertNotIn("test: test-stage1-smoke test-stage2-smoke test-stage-parity check-examples test-env", text)
        self.assertIn(
            "test-stage1-smoke: venv build-stage1 runtime _print-test-compiler-env",
            text,
        )
        self.assertIn(
            "test-stage2-smoke: venv build-stage2 _print-test-compiler-env",
            text,
        )
        self.assertIn(
            "compiler/stage1_l0/scripts/run_tests.py $(L1_NORMAL_TEST_RUNNER_ARGS) "
            "$(if $(strip $(TESTS)),$(TESTS),$(L1_TEST_STAGE1_SMOKE_TESTS))",
            text,
        )
        self.assertIn(
            "compiler/stage2_l1/scripts/run_tests.py $(L1_NORMAL_TEST_RUNNER_ARGS) "
            "$(if $(strip $(TESTS)),$(TESTS),$(L1_TEST_STAGE2_SMOKE_TESTS))",
            text,
        )
        self.assertIn(
            "test-extended: test-stage1 test-stage2 test-stage-parity check-examples "
            "test-docker-wine-runner test-stage2-tooling test-productization",
            text,
        )
        extended_section = text.split("test-extended:", 1)[1].split("# Hosted CI", 1)[0]
        self.assertNotIn("test-env", extended_section)
        self.assertNotIn("test-stage1-trace", extended_section)
        self.assertNotIn("test-stage2-trace", extended_section)
        self.assertNotIn("--children", extended_section)
        self.assertNotIn("--include-ci-only", extended_section)
        self.assertIn("test-ci: test-extended test-env test-stage1-trace test-stage2-trace", text)
        self.assertIn("test-ci: L1_NORMAL_TEST_RUNNER_ARGS = --include-ci-only", text)
        ci_section = text.split("test-ci: L1_NORMAL_TEST_RUNNER_ARGS = --include-ci-only", 1)[1].split("test-docker:", 1)[0]
        self.assertIn("run_trace_tests.py --children", ci_section)
        self.assertIn("scripts/triple_bootstrap.py", ci_section)
        self.assertNotIn("run_tests.py", ci_section)
        self.assertEqual(ci_section.count("run_trace_tests.py --children"), 2)
        self.assertEqual(ci_section.count("scripts/triple_bootstrap.py"), 1)
        self.assertIn("L1 Stage 1 dedicated trace sweep:", text)
        self.assertIn("L1 Stage 2 dedicated trace sweep:", text)
        self.assertIn("L1 environment/bootstrap integration:", text)
        self.assertIn("L1 child trace fixtures (Stage 1 and Stage 2):", text)
        self.assertIn("L1 strict triple bootstrap:", text)
        self.assertIn("included CI-only cases; trace checks are separate execution modes", text)
        self.assertIn("CMD=test-extended", text)
        self.assertNotIn("test-all", text)

    def test_stage2_normal_runner_ci_only_selection(self):
        """Default discovery excludes CI-only cases while selectors and CI mode retain access."""
        expected_ci_only = {
            "l1c_stage1_arc_trace_regression_test.py",
            "l1c_stage1_installed_preparation_test.py",
            "l1c_stage1_preparation_test.py",
            "slice_trace_test",
            "math_runtime_compile_test",
            "mul_runtime_compile_test",
        }
        self.assertEqual(stage2_normal_runner.CI_ONLY_NORMAL_STAGE2_TESTS, expected_ci_only)
        discovered = stage2_normal_runner.discover_stage2_l1_tests()
        normal = stage2_normal_runner.select_cases(discovered, [])
        included = stage2_normal_runner.select_cases(discovered, [], include_ci_only=True)
        self.assertEqual(len(included), len(discovered))
        self.assertFalse(expected_ci_only.intersection(case.name for case in normal))
        for name in expected_ci_only:
            self.assertEqual(
                [case.name for case in stage2_normal_runner.select_cases(discovered, [name])], [name],
            )
        self.assertTrue(
            {"mul_runtime_overflow_test.py", "l1c_stage1_managed_preparation_test.py"}.issubset(
                case.name for case in normal
            )
        )
        self.assertIn(
            "l1c_stage1_arc_trace_regression_test.py",
            stage2_normal_runner.CI_ONLY_NORMAL_STAGE2_TESTS,
        )
        self.assertTrue(
            any(
                case.name == "l1c_stage1_arc_trace_regression_test.py"
                for case in stage2_normal_runner.discover_stage2_l1_tests()
            )
        )

        cases = [
            stage2_normal_runner.TestCase(0, "array_test", Path("array_test.l1"), "l1"),
            stage2_normal_runner.TestCase(1, "slice_trace_test", Path("slice_trace_test.l1"), "l1"),
        ]
        self.assertEqual(
            [case.name for case in stage2_normal_runner.select_cases(cases, [])],
            ["array_test"],
        )
        self.assertEqual(
            [case.name for case in stage2_normal_runner.select_cases(cases, ["slice_trace_test"])],
            ["slice_trace_test"],
        )
        self.assertEqual(
            [
                case.name
                for case in stage2_normal_runner.select_cases(
                    cases,
                    ["array_test"],
                    include_ci_only=True,
                )
            ],
            ["array_test"],
        )
        with self.assertRaises(ValueError):
            stage2_normal_runner.select_cases(cases, ["missing_test"])
        self.assertEqual(
            [case.name for case in stage2_normal_runner.select_cases(cases, [], include_ci_only=True)],
            ["array_test", "slice_trace_test"],
        )
        self.assertTrue(stage2_normal_runner.parse_args(["--include-ci-only"]).include_ci_only)
        help_output = io.StringIO()
        with self.assertRaises(SystemExit) as exit_result:
            with redirect_stdout(help_output):
                stage2_normal_runner.parse_args(["--help"])
        self.assertEqual(exit_result.exception.code, 0)
        self.assertIn("--include-ci-only", help_output.getvalue())

    def test_trace_selection_ignores_normal_cost_classification(self):
        """CI-only normal metadata must not remove dedicated trace coverage."""
        names = {case.name for case in stage2_trace_runner.select_trace_cases([])}
        self.assertIn("slice_trace_test", names)
        self.assertIn("mul_runtime_compile_test", names)
        self.assertNotIn("math_runtime_compile_test", names)
        self.assertEqual(
            [case.name for case in stage2_trace_runner.select_trace_cases(["math_runtime_compile_test"])],
            ["math_runtime_compile_test"],
        )
        self.assertIn(
            "math_runtime_compile_test",
            {case.name for case in stage2_trace_runner.select_trace_cases([], include_slow=True)},
        )

    def test_trace_main_selection_and_slow_logging(self):
        """The runner main preserves cost-independent discovery and slow-case logging."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = stage2_trace_runner.TraceResult(0, "sample", "TRACE_OK", "", "", "", root / "trace", 0, 0, 0, 0)
            for argv in ([], ["math_runtime_compile_test"], ["--include-slow"]):
                args = stage2_trace_runner.parse_args(argv)
                output = io.StringIO()
                with (
                    patch.object(stage2_trace_runner, "parse_args", return_value=args),
                    patch.object(stage2_trace_runner, "resolve_trace_job_count", return_value=1),
                    patch.object(stage2_trace_runner, "require_repo_stage2_test_env", return_value=(sys.executable, root, root, {})),
                    patch.object(stage2_trace_runner, "resolve_artifact_dir", return_value=(root, False)),
                    patch.object(stage2_trace_runner, "run_one", return_value=result) as run_one,
                    redirect_stdout(output),
                ):
                    self.assertEqual(stage2_trace_runner.main(), 0)
                selected = {call.args[1] for call in run_one.call_args_list}
                if not argv:
                    self.assertTrue({"slice_trace_test", "mul_runtime_compile_test"}.issubset(selected))
                elif argv == ["math_runtime_compile_test"]:
                    self.assertEqual(selected, {"math_runtime_compile_test"})
                else:
                    self.assertIn("math_runtime_compile_test", selected)
                self.assertEqual("Skipping slow trace tests by default" in output.getvalue(), not argv)

    def test_tinycc_runtime_inputs_are_pinned(self):
        """Changing a loose runtime object invalidates the bootstrap input manifest."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build/dea"
            obj = build / "runtime/tcc/default/dea_rt_sys.o"
            obj.parent.mkdir(parents=True)
            obj.write_bytes(b"original runtime")
            with patch("triple_bootstrap.REPO_ROOT", root):
                before = input_manifest(build)
                obj.write_bytes(b"changed runtime")
                self.assertNotEqual(before, input_manifest(build))

    def test_native_compiler_path_is_one_argument(self):
        """Resolved executable paths retain spaces and native path separators."""
        with tempfile.TemporaryDirectory(prefix="native compiler ") as temporary:
            compiler = Path(temporary) / "gcc.exe"
            compiler.write_bytes(b"compiler fixture")
            self.assertEqual(compiler_command_words(str(compiler)), [str(compiler)])

    def test_unknown_native_toolchain_is_probed(self):
        """A compiler named cc must pass the stability probe and retain its log."""
        def compile_probe(command, **kwargs):
            Path(command[command.index("-o") + 1]).write_bytes(b"stable native")
            return subprocess.CompletedProcess(command, 0, "")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("bootstrap_identity.subprocess.run", side_effect=compile_probe) as run:
                assert_stable_native_toolchain("cc", '-I"include with spaces"', root)
            self.assertEqual(run.call_count, 2)
            self.assertIn("-Iinclude with spaces", run.call_args.args[0])
            self.assertIn("$ cc", (root / "native_stability_probe.log").read_text())

    @patch("build_stage2_l1c.shutil.which", side_effect=lambda name: "/tools/" + name if name in {"gcc", "clang", "custom"} else None)
    def test_host_selection_matches_driver(self, _which):
        """The explicit L1 compiler wins; CC remains the driver's last fallback."""
        self.assertEqual(host_compiler({"L1_CC": "custom", "CC": "clang"}), "/tools/custom")
        self.assertEqual(host_compiler({"CC": "clang"}), "/tools/gcc")
        with self.assertRaises(RuntimeError):
            host_compiler({"L1_CC": "missing", "CC": "clang"})

    def test_retained_traces_do_not_overwrite_stage1(self):
        """Both stages can retain identically named traces beneath one chosen root."""
        scripts = Path(__file__).resolve().parents[1] / "compiler/stage2_l1/scripts"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.stderr.log").write_text("stage1 evidence")
            code = (
                "import sys; from pathlib import Path; from argparse import Namespace; "
                "sys.path.insert(0, sys.argv[1]); from run_trace_tests import resolve_artifact_dir; "
                "root, clean = resolve_artifact_dir(Namespace(artifact_dir=sys.argv[2], keep_artifacts=False)); "
                "assert not clean; (root/'sample.stderr.log').write_text('stage2 evidence')"
            )
            subprocess.run([sys.executable, "-c", code, str(scripts), str(root)], check=True)
            self.assertEqual((root / "sample.stderr.log").read_text(), "stage1 evidence")
            self.assertEqual((root / "stage2/sample.stderr.log").read_text(), "stage2 evidence")

    def test_stage1_runner_ignores_stage2_subject_override(self):
        """A Stage 2 override cannot redirect the oracle suite."""
        scripts = Path(__file__).resolve().parents[1] / "compiler/stage1_l0/scripts"
        code = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "from test_runner_common import build_repo_test_env; "
            "assert 'L1_TEST_COMPILER' not in build_repo_test_env('build/dea', Path('build/dea'))"
        )
        subprocess.run([sys.executable, "-c", code, str(scripts)],
                       env={**os.environ, "L1_TEST_COMPILER": "/missing/poison-subject"}, check=True)

    def test_exact_inventory_and_bytes(self):
        """Missing, extra, and changed retained units must fail."""
        with tempfile.TemporaryDirectory() as temporary:
            roots = [Path(temporary) / name for name in ("B", "C")]
            for root in roots:
                root.mkdir()
                (root / "__dea_wrapper.c").write_bytes(b"wrapper\n")
                (root / "main.c").write_bytes(b"unit\n")
            compare_trees(*roots)
            with self.assertRaisesRegex(AssertionError, "Stage 1-built A"):
                compare_trees(*roots, expected_inventory={"__dea_wrapper.c", "main.c", "omitted.c"})
            (roots[1] / "main.c").write_bytes(b"unit \n")
            with self.assertRaises(AssertionError):
                compare_trees(*roots)
            (roots[1] / "main.c").unlink()
            with self.assertRaises(AssertionError):
                compare_trees(*roots)
            (roots[1] / "main.c").write_bytes(b"unit\n")
            (roots[1] / "extra.c").write_bytes(b"extra\n")
            with self.assertRaises(AssertionError):
                compare_trees(*roots)

    @patch("build_stage2_l1c.host_compiler", return_value="test-cc")
    def test_runtime_controls(self, _compiler):
        """Raw modes win over defaults and compiler tuning does not mutate callers."""
        quoted = '-DNAME="two  spaces"'
        self.assertEqual(merge_cflags(quoted, ["-frandom-seed=l1c-stage2"]),
                         quoted + " -frandom-seed=l1c-stage2")
        source = {"L1_CFLAGS": "-O1 -D_RT_QUARANTINE_MAX_COUNT=42"}
        env, mode = compiler_build_env(source)
        self.assertEqual(mode, ["--check-basic"])
        self.assertEqual(source["L1_CFLAGS"], env["L1_CFLAGS"])
        for values, expected in (({"L1_COMPILER_RT_UNCHECKED": "1"}, ["--unchecked"]),
                                 ({"L1_COMPILER_RT_CHECK_BASIC": ""}, []),
                                 ({"L1_CFLAGS": "-DDEA_RT_UNCHECKED"}, ["--unchecked"])):
            self.assertEqual(compiler_build_env(values)[1], expected)
        self.assertEqual(source, {"L1_CFLAGS": "-O1 -D_RT_QUARANTINE_MAX_COUNT=42"})

    @patch("build_stage2_l1c.host_compiler", return_value="test-cc")
    @patch("build_stage2_l1c.subprocess.run")
    def test_support_symbol_ownership(self, run, _compiler):
        """Only common and preparation support enter an L1 native link."""
        with tempfile.TemporaryDirectory(prefix="support with spaces ") as temporary:
            args = build_support_objects(Path(temporary), {})
            self.assertEqual(args[::2], ["--foreign-object", "--foreign-object"])
            self.assertEqual([Path(args[i]).name for i in (1, 3)], ["compiler_support.o", "preparation_support.o"])
            self.assertEqual(run.call_count, 2)
            self.assertNotIn("interface_fingerprint.c", str(run.call_args_list))

    def test_wrapper_does_not_select_alias(self):
        """Rebuilding a wrapper preserves either explicit alias, including spaced paths."""
        with tempfile.TemporaryDirectory(prefix="stage selection ") as temporary:
            root = Path(temporary)
            layout = L1BuildLayout(root, root / "build", root / "build/bin", "build", "../..")
            layout.bin_dir.mkdir(parents=True)
            first = layout.bin_dir / "l1c-stage1"
            first.write_text("stage1")
            write_relative_alias(layout.bin_dir / "l1c", first.name)
            write_stage2_wrapper(layout)
            self.assertEqual((layout.bin_dir / "l1c").read_text(), "stage1")
            write_relative_alias(layout.bin_dir / "l1c", "l1c-stage2")
            self.assertIn("l1c-stage2.native", (layout.bin_dir / "l1c").read_text())
            write_relative_alias(layout.bin_dir / "l1c", first.name)
            self.assertEqual((layout.bin_dir / "l1c").read_text(), "stage1")

    def test_build_info_overlay_is_private_and_narrow(self):
        """Only the requested module shadows sources and scratch survives through the build."""
        fallback = L1_ROOT / "compiler/stage2_l1/src/build_info.l1"
        original = fallback.read_bytes()
        with tempfile.TemporaryDirectory(prefix="overlay with spaces ") as temporary:
            root = Path(temporary)
            overlay = root / "package-info.l1"
            overlay.write_bytes(b"module build_info;\n// private metadata\n")
            (root / "l1c.l1").write_text("poison sibling")
            output = root / "package/bin/l1c-stage2.native"
            seen_roots = []

            def construct(command, **kwargs):
                roots = [Path(command[i + 1]) for i, arg in enumerate(command) if arg == "--project-root"]
                seen_roots.extend(roots)
                self.assertEqual(len(roots), 2)
                self.assertEqual(roots[1], fallback.parent)
                self.assertNotEqual(roots[0], overlay.parent)
                self.assertEqual([path.name for path in roots[0].iterdir()], ["build_info.l1"])
                self.assertEqual((roots[0] / "build_info.l1").read_bytes(), overlay.read_bytes())
                self.assertEqual(fallback.read_bytes(), original)
                self.assertIn("--keep-c", command)
                self.assertEqual(kwargs["env"]["L1_HOME"], str(L1_ROOT / "compiler"))
                self.assertNotIn("L1_SYSTEM", kwargs["env"])
                output.write_bytes(b"native compiler")

            env = {"L1_CC": "test-cc", "L1_HOME": "/stale/install", "L1_SYSTEM": "/stale/interfaces"}
            with patch("build_stage2_l1c.host_compiler", return_value="test-cc"), \
                    patch("build_stage2_l1c.build_support_objects", return_value=[]), \
                    patch("build_stage2_l1c.subprocess.run", side_effect=construct):
                build_compiler(root / "seed", output, env, keep_c=True, build_info_overlay=overlay)
            self.assertFalse(seen_roots[0].exists())
            self.assertEqual(fallback.read_bytes(), original)
            self.assertEqual(env["L1_HOME"], "/stale/install")
            self.assertEqual(overlay.read_bytes(), b"module build_info;\n// private metadata\n")

    def test_build_info_overlay_failure_cleans_scratch(self):
        """Compiler rejection removes private metadata without touching the supplied module."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            overlay = root / "build_info.l1"
            overlay.write_text("invalid module")
            output = root / "bin/compiler"
            with patch("build_stage2_l1c.host_compiler", return_value="test-cc"), \
                    patch("build_stage2_l1c.build_support_objects", return_value=[]), \
                    patch("build_stage2_l1c.subprocess.run", side_effect=subprocess.CalledProcessError(1, "seed")):
                with self.assertRaises(subprocess.CalledProcessError):
                    build_compiler(root / "seed", output, {}, build_info_overlay=overlay)
            self.assertEqual(list(output.parent.iterdir()), [])
            self.assertEqual(overlay.read_text(), "invalid module")

    def test_missing_build_info_overlay_fails_before_construction(self):
        """An explicit missing module never falls back to source-tree metadata."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("build_stage2_l1c.build_support_objects") as support:
                with self.assertRaises(FileNotFoundError):
                    build_compiler(root / "seed", root / "bin/compiler", {},
                                   build_info_overlay=root / "missing.l1")
                support.assert_not_called()
            self.assertFalse((root / "bin").exists())

    def test_default_build_has_no_overlay(self):
        """Existing callers keep the original source root and fallback metadata."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "compiler"

            def construct(command, **_kwargs):
                roots = [command[i + 1] for i, arg in enumerate(command) if arg == "--project-root"]
                self.assertEqual(roots, [str(L1_ROOT / "compiler/stage2_l1/src")])
                output.write_bytes(b"native compiler")

            with patch("build_stage2_l1c.host_compiler", return_value="test-cc"), \
                    patch("build_stage2_l1c.build_support_objects", return_value=[]), \
                    patch("build_stage2_l1c.subprocess.run", side_effect=construct):
                build_compiler(root / "seed", output, {})


if __name__ == "__main__":
    unittest.main()
