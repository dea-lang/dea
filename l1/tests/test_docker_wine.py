#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Exercise Wine image caching and execution without requiring Docker."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("docker_wine", Path(__file__).resolve().parents[1] / "scripts/docker_wine.py")
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class DockerWineTests(unittest.TestCase):
    """Check cache boundaries, isolation and Make argument transport."""

    def setUp(self) -> None:
        """Prepare a small repository and simulated Docker image store."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.docker_files = self.root / "l1/docker/wine"
        self.docker_files.mkdir(parents=True)
        for name in runner.ENVIRONMENT_INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        for name in ("Dockerfile.toolchain", "Dockerfile.environment", "run.sh"):
            (self.docker_files / name).write_text(name)
        (self.root / "scripts").mkdir()
        self.addCleanup(patch.stopall)
        patch("sys.stdout", new_callable=io.StringIO).start()
        patch("sys.stderr", new_callable=io.StringIO).start()
        patch.object(runner, "ROOT", self.root).start()
        patch.object(runner, "DOCKER_FILES", self.docker_files).start()
        self.images: set[str] = set()
        self.builds: list[list[str]] = []

    def docker(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        """Simulate successful inspection/build, reading the real build context.

        Args:
            command: Docker argument vector.
            **kwargs: Subprocess options.

        Returns:
            The simulated command result.
        """
        if command[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(command, 0 if command[3] in self.images else 1)
        self.assertEqual(command[1], "build")
        self.assertTrue((Path(command[-1]) / "Dockerfile").is_file())
        self.assertNotIn("--no-cache", command)
        self.builds.append(command)
        self.images.add(command[command.index("-t") + 1])
        return subprocess.CompletedProcess(command, 0)

    def test_cache_reuse_and_dependency_boundaries(self) -> None:
        """Source changes reuse both images; dependency changes reuse the toolchain."""
        with patch.object(runner.subprocess, "run", side_effect=self.docker):
            initial = runner.prepare_images("test-wine")
            self.assertEqual(len(self.builds), 2)
            self.assertEqual(runner.prepare_images("test-wine"), initial)
            self.assertEqual(len(self.builds), 2)
            (self.root / "l1/new_source.l0").write_text("new source")
            self.assertEqual(runner.prepare_images("test-wine"), initial)
            self.assertEqual(len(self.builds), 2)
            (self.root / "uv.lock").write_text("changed dependencies")
            updated = runner.prepare_images("test-wine")
            self.assertNotEqual(updated, initial)
            self.assertEqual(len(self.builds), 3)
            (self.docker_files / "Dockerfile.toolchain").write_text("new toolchain recipe")
            runner.prepare_images("test-wine")
            self.assertEqual(len(self.builds), 5)
            self.images.clear()
            runner.prepare_images("test-wine")
            self.assertEqual(len(self.builds), 7)

    def test_toolchain_checkpoint_and_failed_environment_retry(self) -> None:
        """An environment failure does not discard the completed toolchain image."""
        with patch.object(runner.subprocess, "run", side_effect=self.docker):
            toolchain = runner.prepare_images("test-wine", toolchain_only=True)
        self.assertEqual(len(self.builds), 1)

        def fail_environment(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            """Fail the environment build while retaining completed images.

            Args:
                command: Docker argument vector.
                **kwargs: Subprocess options.

            Returns:
                The inspection result.

            Raises:
                subprocess.CalledProcessError: For the requested image build.
            """
            if command[1] == "build":
                raise subprocess.CalledProcessError(17, command)
            return self.docker(command, **kwargs)

        with patch.object(runner.subprocess, "run", side_effect=fail_environment):
            with self.assertRaises(subprocess.CalledProcessError):
                runner.prepare_images("test-wine")
        self.assertEqual(self.images, {toolchain})
        with patch.object(runner.subprocess, "run", side_effect=self.docker):
            runner.prepare_images("test-wine")
        self.assertEqual(len(self.builds), 2)

    def test_snapshot_excludes_host_builds_and_keeps_current_sources(self) -> None:
        """The snapshot includes untracked sources without copying host environments."""
        for name in ("l0/build/host.exe", "l1/build/host.exe", "l1/.venv/bin/python",
                     "l1/__pycache__/host.pyc", "l1/source file.l0", "l0/input.l0"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        snapshot = io.BytesIO()
        runner.write_snapshot(snapshot)
        with tarfile.open(fileobj=snapshot) as archive:
            names = archive.getnames()
            self.assertIn("l1/source file.l0", names)
            self.assertIn("l0/input.l0", names)
            self.assertFalse(any("host" in name or ".venv" in name for name in names))
            self.assertEqual(archive.extractfile("l1/source file.l0").read(), b"l1/source file.l0")

    def test_run_transports_arguments_artifacts_and_failure(self) -> None:
        """Quoted assignments stay intact and container failure reaches the caller."""
        artifacts = self.root / "trace artifacts"
        environment = {"TESTS": "one two", "L1_TEST_JOBS": "2", "L1_TRACE_TEST_JOBS": "1",
                       "L1_TRACE_ARTIFACT_DIR": str(artifacts), "L0_CC": "/host/compiler"}
        targets = ["test-stage1", "LABEL=spaces;$(literal)"]
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 23)) as run:
                self.assertEqual(runner.run_image("prepared-image", targets), 23)
        command = run.call_args.args[0]
        self.assertEqual(command[-3:], ["prepared-image", *targets])
        self.assertIn("TESTS", command)
        self.assertIn("L1_TRACE_ARTIFACT_DIR=C:/trace-artifacts", command)
        self.assertIn(f"{artifacts.resolve()}:/root/.wine/drive_c/trace-artifacts", command)
        self.assertNotIn("L0_CC", command)
        self.assertTrue(artifacts.is_dir())
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_invalid_cmd_never_builds_an_image(self) -> None:
        """Empty and malformed CMD inputs fail before expensive Docker operations."""
        with patch.object(runner, "prepare_images") as prepare:
            with patch.object(runner.sys, "argv", ["docker_wine.py", "run"]):
                with patch.dict(os.environ, {"CMD": ""}, clear=True):
                    with self.assertRaises(SystemExit) as failure:
                        runner.main()
                    self.assertEqual(failure.exception.code, 2)
                with patch.dict(os.environ, {"CMD": "'unterminated"}, clear=True):
                    self.assertEqual(runner.main(), 2)
        prepare.assert_not_called()

    @unittest.skipUnless(shutil.which("make"), "GNU Make is unavailable")
    def test_make_exports_quoted_inputs_to_host_runner(self) -> None:
        """Exercise the actual Make entrypoint without invoking Docker."""
        probe = self.root / "host probe.py"
        probe.write_text('import json, os\nprint("PROBE:" + json.dumps(dict(os.environ)))\n')
        interpreter = f"{shlex.quote(Path(sys.executable).as_posix())} {shlex.quote(probe.as_posix())}"
        result = subprocess.run(
            ["make", "-C", str(Path(__file__).resolve().parents[1]), "docker-wine",
             f"HOST_PYTHON={interpreter}", 'CMD=test-stage1 "LABEL=two words"',
             "TESTS=one two", "L1_TEST_JOBS=3", "L1_TRACE_TEST_JOBS=2",
             "L1_TRACE_ARTIFACT_DIR=trace directory"],
            capture_output=True, text=True, check=True,
        )
        payload = next(line.removeprefix("PROBE:") for line in result.stdout.splitlines() if line.startswith("PROBE:"))
        environment = json.loads(payload)
        self.assertEqual(shlex.split(environment["CMD"]), ["test-stage1", "LABEL=two words"])
        self.assertEqual(environment["TESTS"], "one two")
        self.assertEqual(environment["L1_TEST_JOBS"], "3")
        self.assertEqual(environment["L1_TRACE_ARTIFACT_DIR"], "trace directory")


if __name__ == "__main__":
    unittest.main()
