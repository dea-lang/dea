#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression checks for strict fixed-point evidence and Stage 2 construction."""

import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_stage2_l1c import compiler_build_env, build_support_objects, write_stage2_wrapper, host_compiler
from build_stage1_l1c import L1BuildLayout, write_relative_alias
from triple_bootstrap import compare_trees, input_manifest
from bootstrap_identity import assert_stable_native_toolchain, compiler_command_words, merge_cflags


class Stage2ToolingTests(unittest.TestCase):
    """Prevent false fixed points and accidental stage/bridge selection."""

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


if __name__ == "__main__":
    unittest.main()
