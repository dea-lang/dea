#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Falsify capability reporting with controlled subprocess and publication evidence."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import check_preparation_reuse as reporter


class ReporterTest(unittest.TestCase):
    """Reject false compatibility outcomes and preserve failed invocation evidence."""

    def exercise(self, scenario: str = "available", expect: str = "available") -> tuple[int, dict, dict]:
        """Run the actual reporter against a small, controlled process fixture.

        Args:
            scenario: Evidence mutation or capability to simulate.
            expect: Required capability or observation mode.

        Returns:
            Exit status, parsed JSON report, and retained text files.
        """
        with tempfile.TemporaryDirectory(prefix="l1-reporter-test-") as directory:
            root = Path(directory)
            source = root / "compiler/shared/l1/stdlib/std/io.l1"
            source.parent.mkdir(parents=True)
            source.write_text("module std.io;\n")
            for relative in ("stage1_l0/src", "stage1_l0/support"):
                (root / "compiler" / relative).mkdir(parents=True)
            build = root / "build/dea"
            for name in ("bin/l1c-stage1.native", "include/dea_rt.h", "include/l1_real.h", "interfaces/std/io.l1m"):
                path = build / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n")
            if scenario == "not-run":
                (build / "interfaces/std/io.l1m").unlink()
            cc = str(root / "gcc-mp-15")
            output = root / "results"
            output.mkdir()
            (output / "invalidated-auto.manifest.json").write_text("stale prior report")
            calls = 0

            def process(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
                nonlocal calls
                if "--run" not in argv:
                    self.assertEqual(argv[0], cc)
                    if "--no-default-config" in argv:
                        message = "unsupported option '--no-default-config'" if scenario == "unsupported" else "random failure"
                        return subprocess.CompletedProcess(argv, 1, "", message)
                    if "--version" in argv:
                        return subprocess.CompletedProcess(argv, 0, "clang test version\n", "")
                    return subprocess.CompletedProcess(argv, 0, "test-target\n", "")
                calls += 1
                selected_cc = argv[argv.index("--c-compiler") + 1]
                self.assertEqual(selected_cc, cc)
                self.assertNotIn("--keep-c", argv)
                self.assertNotIn("L1_CFLAGS", kwargs["env"])
                self.assertNotIn("L1_RUNTIME_LIB", kwargs["env"])
                cwd = Path(kwargs["cwd"])
                cache = Path(argv[argv.index("--stdlib-cache") + 1])
                guard = "--no-auto-prepare" in argv
                invalidated = "CI preparation" in (cwd / "toolchain/build/include/dea_rt.h").read_text()
                key = "b" * 64 if invalidated and scenario != "stale-header" else "a" * 64
                private = scenario in ("private", "private-cold-error", "private-second-error", "observation-failed")
                entry = cache / "v1/native" / key
                selected = str(cwd / f"private-{calls}") if private else str(entry)
                compiles = 0 if guard or (entry / "manifest.json").exists() else 1
                counts = dict.fromkeys(reporter.COUNTERS, 0)
                counts.update(module_compiles=compiles, build_commands=3 if compiles else 0, native_resolutions=1)
                identity = {"toolchain": {"invocation": selected_cc, "target": "test-target"}}
                guard_miss = guard and not (entry / "manifest.json").exists()
                lines = []
                if compiles or guard_miss:
                    lines.append("Starting analysis for entry module '_dea_preparation'")
                if compiles:
                    lines.append("Starting analysis for entry module 'std.io'")
                stdout, code = reporter.EXPECTED_OUTPUT, 0
                if guard and (private or not (entry / "manifest.json").exists()):
                    selected, stdout, code = "", "", 1
                    reason = "opaque archive-tool wrapper cannot authorize persistent reuse" if private else "cache miss"
                    lines.append("error: [L1C-2159] automatic preparation is disabled: " + reason)
                elif compiles:
                    if private:
                        reason = ("compiler family/version observation is unavailable" if scenario == "observation-failed"
                                  else "opaque archive-tool wrapper cannot authorize persistent reuse")
                        lines.append("Fresh preparation: " + reason)
                    else:
                        entry.mkdir(parents=True)
                        (entry / "manifest.json").write_text(json.dumps({"key": key, "identity": identity}))
                else:
                    lines.append("Reuse prepared profile: " + selected)
                if scenario in ("unsupported", "archiver-error"):
                    code, stdout, selected, key, identity = 1, "", "", "", ""
                    counts.update(module_compiles=0, build_commands=0)
                    (entry / "manifest.json").unlink(missing_ok=True)
                    lines = ["error: [L1C-2154] " + reporter.ARCHIVER_BOUNDARY + ": " + cc]
                if (scenario in ("input-stability", "private-cold-error") and calls == 1 or
                        scenario == "private-second-error" and calls == 2):
                    code, stdout = 1, ""
                    lines.append("error: [L1C-2151] preparation input changed while building: l1c.native")
                if scenario == "substitution" and calls == 1:
                    identity["toolchain"]["invocation"] = str(root / "clang")
                if scenario == "timeout":
                    raise subprocess.TimeoutExpired(argv, 1, output=b"partial output", stderr=b"partial diagnostics")
                if scenario == "launch-error":
                    raise OSError("cannot execute fixture")
                if scenario == "wrong-output":
                    stdout = "wrong\n"
                if calls == 2:
                    if scenario == "warm-build":
                        counts["build_commands"] = 1
                    elif scenario == "warm-compile":
                        counts["module_compiles"] = 1
                    elif scenario == "warm-key":
                        key = "c" * 64
                    elif scenario == "warm-no-reuse":
                        lines = [line for line in lines if not line.startswith("Reuse prepared profile:")]
                if calls == 3 and scenario == "guard-crash":
                    code = -11
                if scenario == "duplicate-validation":
                    lines.append("Starting analysis for entry module '_dea_preparation'")
                if scenario == "duplicate-resolution":
                    counts["native_resolutions"] = 2
                if scenario == "bad-counters":
                    counts["module_compiles"] = False
                lines.extend(["Preparation native key: " + key, "Preparation selected: " + selected,
                              "Preparation native inputs: " + (json.dumps(identity) if identity else "")])
                stats = "Preparation statistics: " + json.dumps(counts)
                if scenario != "missing-stats":
                    lines.append(stats)
                if scenario == "duplicate-stats":
                    lines.append(stats)
                return subprocess.CompletedProcess(argv, code, stdout, "\n".join(lines) + "\n")

            with patch.object(reporter, "L1_ROOT", root), patch.object(reporter.shutil, "which", return_value=cc), \
                    patch.object(reporter.subprocess, "run", side_effect=process), redirect_stdout(io.StringIO()), \
                    patch.dict(reporter.os.environ, {"L1_CFLAGS": "poison", "L1_RUNTIME_LIB": "poison"}):
                result = reporter.main(["--c-compiler", cc, "--build-dir", str(build), "--output-dir", str(output),
                                        "--expect", expect])
            report = json.loads((output / "report.json").read_text())
            files = {path.name: path.read_text() for path in output.iterdir() if path.is_file()}
            return result, report, files

    def test_available_requires_complete_sequence(self):
        """Require both warm consumers, current manifests and successful invalidation."""
        result, report, files = self.exercise()
        self.assertEqual((result, report["capability"]), (0, "available"))
        self.assertTrue(report["same_persistent_entry"])
        self.assertEqual(report["invalidation"], "rejected-old-profile-and-rebuilt")
        self.assertEqual(len(report["invocations"]), 5)
        self.assertIn("cold.manifest.json", files)
        self.assertIn("invalidated-auto.stdout.log", files)

    def test_private_requires_two_successes_and_guarded_refusal(self):
        """Keep successful private preparation separate from expected persistent reuse."""
        result, report, _ = self.exercise("private", "private")
        self.assertEqual((result, report["native_preparation"], report["persistent_reuse"]),
                         (0, "supported", "unavailable"))
        self.assertIsNone(report["invocations"]["invalidated-guard"])
        self.assertEqual(self.exercise("private")[0], 1)

    def test_unsupported_needs_confirming_failed_probe(self):
        """Require boundary evidence in addition to the shared diagnostic code."""
        result, report, files = self.exercise("unsupported", "observe")
        self.assertEqual((result, report["capability"]), (0, "unsupported"))
        self.assertIn("unsupported option", files["runtime-archiver-boundary.stderr.log"])
        self.assertIsNone(report["invocations"]["warm-auto"])
        self.assertEqual(self.exercise("unsupported")[0], 1)

    def test_false_positive_and_inconclusive_evidence_always_fail(self):
        """Reject missing proof, changed identities, unexpected work and process errors."""
        for scenario in ("input-stability", "private-cold-error", "private-second-error", "observation-failed",
                         "archiver-error", "substitution", "wrong-output", "warm-build", "warm-compile", "warm-key",
                         "warm-no-reuse", "guard-crash", "duplicate-validation", "duplicate-resolution", "stale-header", "bad-counters",
                         "missing-stats", "duplicate-stats", "timeout", "launch-error"):
            with self.subTest(scenario=scenario):
                result, report, files = self.exercise(scenario, "observe")
                self.assertEqual((result, report["capability"], report["result"]), (1, "error", "FAIL"))
                self.assertIn("cold.stderr.log", files)
                self.assertIn("**FAIL**", files["summary.md"])
                if scenario == "timeout":
                    self.assertEqual(files["cold.stderr.log"], "partial diagnostics")
                    self.assertIsNone(report["invocations"]["cold"]["exit_code"])

    def test_incomplete_bootstrap_reports_not_run(self):
        """Preserve a failing not-run report without stale measurements."""
        result, report, files = self.exercise("not-run", "observe")
        self.assertEqual((result, report["capability"]), (1, "not-run"))
        self.assertIn("incomplete bootstrap", report["reason"])
        self.assertTrue(all(value is None for value in report["invocations"].values()))
        self.assertIn("summary.md", files)
        self.assertNotIn("invalidated-auto.manifest.json", files)

    def test_unknown_compiler_is_never_substituted(self):
        """Do not fall back when the exact requested executable is missing."""
        with patch.object(reporter.shutil, "which", return_value=None), tempfile.TemporaryDirectory() as directory:
            args = reporter.argparse.Namespace(c_compiler="missing-gcc-mp-15")
            probe = reporter.Probe(args, {"compiler": {}}, Path(directory))
            with self.assertRaisesRegex(reporter.ProbeError, "requested C compiler not found"):
                probe.fixture()


if __name__ == "__main__":
    unittest.main()
