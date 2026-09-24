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

    def exercise(self, scenario: str = "available", expect: str = "available",
                 observability: bool = False) -> tuple[int, dict, dict]:
        """Run the actual reporter against a small, controlled process fixture.

        Args:
            scenario: Evidence mutation or capability to simulate.
            expect: Required capability or observation mode.
            observability: Whether to run the opt-in paired scenarios.

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
            (output / "observe-copy-1.stderr.log").write_text("stale optional report")
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
                fixture_root = Path(kwargs["env"]["L1_BUILD_DIR"]).parents[1]
                cache = Path(argv[argv.index("--stdlib-cache") + 1])
                if observability and cache.name in ("copy-cache", "copy-no-memos-cache") and calls in (8, 10):
                    self.assertEqual((cache / "v1/memo/fixture.json").exists(), cache.name == "copy-cache")
                guard = "--no-auto-prepare" in argv
                invalidated = "CI preparation" in (fixture_root / "toolchain/build/include/dea_rt.h").read_text()
                key = "b" * 64 if invalidated and scenario != "stale-header" else "a" * 64
                private = scenario in ("private", "private-cold-error", "private-second-error", "observation-failed")
                entry = cache / "v1/native" / key
                selected = str(fixture_root / f"private-{calls}") if private else str(entry)
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
                if scenario == "timeout" or (scenario == "copy-timeout" and calls == 8):
                    partial = 'partial diagnostics\nPreparation observation: ' + json.dumps(
                        {"event": "probe", "purpose": "timed probe", "elapsed_us": 37,
                         "status": 1, "timed_out": 1, "schema": 1}) + '\nPreparation observation: {"event":'
                    raise subprocess.TimeoutExpired(argv, 1, output=b"partial output", stderr=partial.encode())
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
                observation = {"event": "observation-selection", "scope": "toolchain-observation-memo",
                               "selection_key": str(cwd), "cwd": str(cwd), "schema": 1}
                if scenario != "no-selection":
                    lines.append("Preparation observation: " + json.dumps(observation))
                lines.append("Preparation observation: " + json.dumps(
                    {"event": "span", "name": "profile-validation", "inclusive": 1,
                     "elapsed_us": 100, "success": 1, "schema": 1}))
                if "--sys-root" in argv:
                    lines.append("Preparation observation: " + json.dumps(
                        {"event": "provider-selection", "scope": "managed-providers", "decision": "suppressed",
                         "reason": "explicit-system-root", "schema": 1}))
                    lines.append("Preparation observation: " + json.dumps(
                        {"event": "provider", "module": "std.io", "origin": "source", "managed": 0,
                         "path": str(root / "toolchain/compiler/shared/l1/stdlib/std/io.l1"), "schema": 1}))
                else:
                    lines.append("Preparation observation: " + json.dumps(
                        {"event": "provider", "module": "std.io", "origin": "interface", "managed": 1,
                         "path": str(fixture_root / "toolchain/build/interfaces/std/io.l1m"), "schema": 1}))
                memo = cache / "v1/memo/fixture.json"
                memo.parent.mkdir(parents=True, exist_ok=True)
                memo.write_text("{}")
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
                arguments = ["--c-compiler", cc, "--build-dir", str(build), "--output-dir", str(output),
                             "--expect", expect]
                if observability:
                    arguments.append("--observability-scenarios")
                result = reporter.main(arguments)
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

    def test_observability_scenarios_are_paired_and_isolated(self):
        """Keep optional scenario caches separate and retain pair comparisons."""
        result, report, files = self.exercise(observability=True)
        self.assertEqual(result, 0)
        self.assertEqual(len(report["invocations"]), 15)
        self.assertEqual(set(report["observability"]),
                         {"warm", "cwd", "copy", "copy-no-memos", "explicit-sys-root"})
        self.assertEqual(report["observability"]["copy"]["copied_cache_portability"],
                         "experimental-observation-only")
        self.assertIn("observe-explicit-sys-root-2.command.json", files)
        cwd = report["observability"]["cwd"]
        self.assertFalse(cwd["selection_key_matches_baseline"])
        self.assertTrue(cwd["stable_selection_key"])
        self.assertFalse(report["observability"]["explicit-sys-root"]["providers_match_baseline"])
        commands = [json.loads(files[f"observe-{name}-1.command.json"]) for name in ("warm", "copy", "copy-no-memos")]
        self.assertEqual(len({item["argv"][item["argv"].index("--stdlib-cache") + 1] for item in commands}), 3)
        self.assertIn("profile-validation", files["summary.md"])
        self.assertIn("inclusive; success=1", files["summary.md"])

    def test_unavailable_scenarios_are_explicit(self):
        """Retain capability results and explain why requested scenarios cannot run."""
        for capability in ("private", "unsupported"):
            result, report, files = self.exercise(capability, "observe", observability=True)
            self.assertEqual(result, 0)
            self.assertTrue(all(item["status"] == "unavailable" and capability in item["reason"]
                                for item in report["observability"].values()))
            self.assertIn("persistent reuse unavailable", files["summary.md"])
            self.assertNotIn("observe-copy-1.stderr.log", files)

    def test_missing_selection_is_unknown(self):
        """Never infer stable selections from absent observation evidence."""
        result, report, _ = self.exercise("no-selection", "observe", observability=True)
        self.assertEqual(result, 0)
        self.assertIsNone(report["observability"]["warm"]["stable_selection_key"])
        self.assertIsNone(report["observability"]["cwd"]["selection_key_matches_baseline"])

    def test_copy_timing_survives_failed_consumer(self):
        """Retain completed copy accounting and partial records when its consumer times out."""
        result, report, files = self.exercise("copy-timeout", "observe", observability=True)
        self.assertEqual(result, 1)
        scenario = report["observability"]["copy"]
        self.assertEqual(scenario["status"], "failed")
        self.assertIn("copy_elapsed_ms", scenario)
        self.assertEqual(report["invocations"]["observe-copy-1"]["probes"][0]["purpose"], "timed probe")
        self.assertIn("timed probe", files["summary.md"])

    def test_measurements_aggregate_structured_observations(self):
        """Parse escaped records and aggregate hash accounting without thresholds."""
        counts = dict.fromkeys(reporter.COUNTERS, 0)
        records = [
            {"event": "hash", "category": "dea-input", "path": 'quoted \\" path',
             "bytes": 7, "elapsed_us": 11, "success": 1, "schema": 1},
            {"event": "hash", "category": "dea-input", "path": "second",
             "bytes": 5, "elapsed_us": 13, "success": 0, "schema": 1},
            {"event": "span", "name": "profile-validation", "inclusive": 1,
             "elapsed_us": 17, "success": 1, "schema": 1},
        ]
        stderr = "\n".join([*("Preparation observation: " + json.dumps(item) for item in records),
                             "Preparation native key: " + "a" * 64,
                             "Preparation selected: /tmp/profile",
                             "Preparation native inputs: {}",
                             "Preparation statistics: " + json.dumps(counts)]) + "\n"
        measured = reporter.measurements(stderr)
        self.assertEqual(measured["hashing"]["dea-input"], {"count": 2, "bytes": 12, "elapsed_us": 24})
        self.assertEqual(measured["observations"][0]["path"], 'quoted \\" path')
        self.assertEqual(measured["spans"][0]["name"], "profile-validation")

    def test_command_elapsed_time_uses_monotonic_clock(self):
        """Account for command duration with a controlled monotonic clock."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = reporter.argparse.Namespace(output_dir=root, timeout=5)
            report = {"stage": None}
            record = {}
            result = subprocess.CompletedProcess(["tool"], 0, "", "")
            probe = reporter.Probe(args, report, root)
            with patch.object(reporter.time, "monotonic", side_effect=(10.0, 10.25)), \
                    patch.object(reporter.subprocess, "run", return_value=result):
                probe.run("timed", ["tool"], record)
            self.assertEqual(record["elapsed_ms"], 250.0)
            for failure in (OSError("launch failed"), subprocess.TimeoutExpired(["tool"], 5)):
                with patch.object(reporter.time, "monotonic", side_effect=(20.0, 20.5)), \
                        patch.object(reporter.subprocess, "run", side_effect=failure), self.assertRaises(type(failure)):
                    probe.run("failed", ["tool"], record)
                self.assertEqual(record["elapsed_ms"], 500.0)

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
                    self.assertTrue(files["cold.stderr.log"].startswith("partial diagnostics"))
                    self.assertIsNone(report["invocations"]["cold"]["exit_code"])
                    partial = report["invocations"]["cold"]
                    self.assertEqual(partial["probes"][0]["purpose"], "timed probe")
                    self.assertEqual(len(partial["observation_errors"]), 1)
                    self.assertIn("timed probe", files["summary.md"])

    def test_incomplete_bootstrap_reports_not_run(self):
        """Preserve a failing not-run report without stale measurements."""
        result, report, files = self.exercise("not-run", "observe")
        self.assertEqual((result, report["capability"]), (1, "not-run"))
        self.assertIn("incomplete bootstrap", report["reason"])
        self.assertTrue(all(value is None for value in report["invocations"].values()))
        self.assertIn("summary.md", files)
        self.assertNotIn("invalidated-auto.manifest.json", files)
        self.assertNotIn("observe-copy-1.stderr.log", files)

    def test_unknown_compiler_is_never_substituted(self):
        """Do not fall back when the exact requested executable is missing."""
        with patch.object(reporter.shutil, "which", return_value=None), tempfile.TemporaryDirectory() as directory:
            args = reporter.argparse.Namespace(c_compiler="missing-gcc-mp-15")
            probe = reporter.Probe(args, {"compiler": {}}, Path(directory))
            with self.assertRaisesRegex(reporter.ProbeError, "requested C compiler not found"):
                probe.fixture()


if __name__ == "__main__":
    unittest.main()
