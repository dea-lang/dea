# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Tests for shared AddressSanitizer capability selection."""

from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

MONOREPO_ROOT = Path(__file__).resolve().parents[5]
if str(MONOREPO_ROOT) not in sys.path:
    sys.path.insert(0, str(MONOREPO_ROOT))

from scripts import asan_test_support


def _completed(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    """Return one synthetic subprocess completion."""

    return subprocess.CompletedProcess(["probe"], returncode, "", stderr)


class AsanTestSupportTests(unittest.TestCase):
    """Exercise strict compiler identity and fallback-mode policy."""

    def _detect(self, **overrides) -> asan_test_support.AsanToolchain | None:
        """Run capability detection in a temporary work directory."""

        defaults = {
            "explicit_compiler": "",
            "configured_compilers": ("gcc-selected",),
            "fallback_compilers": ("clang", "gcc"),
            "label": "test ASan",
        }
        defaults.update(overrides)
        with tempfile.TemporaryDirectory() as tmp:
            return asan_test_support.detect_asan_toolchain(
                work_dir=Path(tmp), **defaults
            )

    @mock.patch("scripts.asan_test_support.shutil.which", return_value="/tools/gcc-selected")
    @mock.patch("scripts.asan_test_support.run_asan_command")
    def test_configured_compiler_succeeds_without_substitution(self, run, _which) -> None:
        """A working configured compiler uses the default sanitizer mode."""

        run.side_effect = [_completed(), _completed()]

        selected = self._detect()

        assert selected is not None
        self.assertEqual(selected.compiler, "/tools/gcc-selected")
        self.assertEqual(selected.mode, "default")
        self.assertEqual(selected.compile_flags, ("-fsanitize=address",))
        self.assertEqual(run.call_count, 2)

    @mock.patch("scripts.asan_test_support.shutil.which", return_value="/tools/gcc-selected")
    @mock.patch("scripts.asan_test_support.run_asan_command")
    def test_non_pie_retry_keeps_the_same_compiler(self, run, _which) -> None:
        """A startup timeout retries the same compiler in non-PIE mode."""

        run.side_effect = [
            _completed(),
            asan_test_support.AsanTimeoutError("default startup stalled"),
            _completed(),
            _completed(),
        ]

        selected = self._detect()

        assert selected is not None
        self.assertEqual(selected.compiler, "/tools/gcc-selected")
        self.assertEqual(selected.mode, "non-PIE compatibility")
        self.assertEqual(
            selected.link_flags,
            ("-fsanitize=address", "-fno-pie", "-no-pie"),
        )
        compile_command = run.call_args_list[2].args[0]
        self.assertEqual(compile_command[0], "/tools/gcc-selected")
        self.assertIn("-no-pie", compile_command)

    @mock.patch("scripts.asan_test_support.shutil.which", return_value="/tools/gcc-selected")
    @mock.patch("scripts.asan_test_support.run_asan_command", return_value=_completed(1, "missing ASan"))
    def test_implicit_unavailability_skips_without_trying_fallback(self, run, _which) -> None:
        """An implicit configured compiler does not fall through to Clang."""

        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            selected = self._detect()

        self.assertIsNone(selected)
        self.assertEqual(run.call_count, 2)
        self.assertIn("SKIP ASan", output.getvalue())
        for call in run.call_args_list:
            self.assertEqual(call.args[0][0], "/tools/gcc-selected")

    @mock.patch("scripts.asan_test_support.shutil.which", return_value="/tools/gcc-explicit")
    @mock.patch("scripts.asan_test_support.run_asan_command", return_value=_completed(1, "missing ASan"))
    def test_explicit_unavailability_fails(self, _run, _which) -> None:
        """An explicit sanitizer compiler request cannot be skipped."""

        with self.assertRaisesRegex(
            asan_test_support.AsanUnavailableError, "explicit ASan request"
        ):
            self._detect(explicit_compiler="gcc-explicit")

    @mock.patch("scripts.asan_test_support.shutil.which")
    @mock.patch("scripts.asan_test_support.run_asan_command")
    def test_local_discovery_can_try_multiple_compilers(self, run, which) -> None:
        """Unconfigured local discovery retains conventional fallback names."""

        which.side_effect = lambda candidate: f"/tools/{candidate}"
        run.side_effect = [_completed(1), _completed(1), _completed(), _completed()]

        selected = self._detect(configured_compilers=())

        assert selected is not None
        self.assertEqual(selected.compiler, "/tools/gcc")
        self.assertEqual(selected.mode, "default")

    @mock.patch("scripts.asan_test_support.subprocess.run")
    def test_command_timeout_has_bounded_diagnostic(self, run) -> None:
        """Subprocess deadlines become concise ASan timeout failures."""

        run.side_effect = subprocess.TimeoutExpired(["asan-probe"], 7)

        with self.assertRaisesRegex(
            asan_test_support.AsanTimeoutError,
            "capability execution timed out after 7s: asan-probe",
        ):
            asan_test_support.run_asan_command(
                ["asan-probe"], phase="capability execution", timeout_seconds=7
            )


if __name__ == "__main__":
    unittest.main()
