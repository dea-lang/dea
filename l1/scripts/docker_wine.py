#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run L1 Make targets in cached, experimental Wine/MSYS2 Docker images."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import BinaryIO


ROOT = Path(__file__).resolve().parents[2]
DOCKER_FILES = ROOT / "l1/docker/wine"
ENVIRONMENT_INPUTS = ("Makefile", "pyproject.toml", "uv.lock", "l0/pyproject.toml", "l1/pyproject.toml")
SOURCE_ROOTS = ("Makefile", "pyproject.toml", "uv.lock", "scripts", "l0", "l1")
FORWARDED = ("TESTS", "L1_TEST_JOBS", "L1_TRACE_TEST_JOBS")


def fingerprint(inputs: dict[str, bytes]) -> str:
    """Hash named image inputs without filesystem timestamps.

    Args:
        inputs: Context names and their exact contents.

    Returns:
        A SHA-256 hexadecimal image tag suffix.
    """
    digest = hashlib.sha256()
    for name, data in sorted(inputs.items()):
        digest.update(name.encode() + b"\0" + str(len(data)).encode() + b"\0" + data)
    return digest.hexdigest()


def ensure_image(image: str, inputs: dict[str, bytes], build_args: tuple[str, ...] = ()) -> None:
    """Reuse an existing image or build it from a minimal temporary context.

    Args:
        image: Content-derived local Docker image tag.
        inputs: Files to place in the isolated build context.
        build_args: Additional Docker build arguments.

    Raises:
        subprocess.CalledProcessError: If Docker cannot build the missing image.
    """
    result = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    if result.returncode == 0:
        print(f"docker-wine: reusing {image}", flush=True)
        return
    print(f"docker-wine: building {image} (completed Docker layers remain cached)", flush=True)
    with tempfile.TemporaryDirectory(prefix="dea-wine-build-") as directory:
        context = Path(directory)
        for name, contents in inputs.items():
            destination = context / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(contents)
        subprocess.run(
            ["docker", "build", "--platform", "linux/amd64", "--progress=plain", "-t", image,
             *build_args, str(context)],
            check=True,
        )


def prepare_images(prefix: str, *, toolchain_only: bool = False) -> str:
    """Prepare content-addressed toolchain and workspace-environment images.

    Args:
        prefix: Local image repository prefix.
        toolchain_only: Stop after preparing the expensive package image.

    Returns:
        The image name ready for the requested stage.

    Raises:
        OSError: If a required build input cannot be read.
        subprocess.CalledProcessError: If an image build fails.
    """
    toolchain_inputs = {"Dockerfile": (DOCKER_FILES / "Dockerfile.toolchain").read_bytes()}
    toolchain = f"{prefix}-toolchain:{fingerprint(toolchain_inputs)}"
    ensure_image(toolchain, toolchain_inputs)
    if toolchain_only:
        return toolchain
    environment_inputs = {name: (ROOT / name).read_bytes() for name in ENVIRONMENT_INPUTS}
    environment_inputs["Dockerfile"] = (DOCKER_FILES / "Dockerfile.environment").read_bytes()
    environment_inputs["run.sh"] = (DOCKER_FILES / "run.sh").read_bytes()
    identity = {**environment_inputs, "toolchain-image": toolchain.encode()}
    environment = f"{prefix}-environment:{fingerprint(identity)}"
    ensure_image(environment, environment_inputs, ("--build-arg", f"TOOLCHAIN_IMAGE={toolchain}"))
    return environment


def source_filter(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Exclude host environments, generated artifacts and special files.

    Args:
        member: Candidate working-tree archive member.

    Returns:
        The member to copy, or None to omit it and its descendants.
    """
    path = PurePosixPath(member.name)
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store", "a.out", "a.exe"}
    if excluded.intersection(path.parts) or path.parts[:2] in (("l0", "build"), ("l1", "build")):
        return None
    if any(part.endswith(".dSYM") for part in path.parts) or path.suffix in (".o", ".pyc"):
        return None
    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
        return None
    return member


def write_snapshot(output: BinaryIO) -> None:
    """Archive current sources, including uncommitted and untracked files.

    Args:
        output: Seekable binary stream to receive the source archive.

    Raises:
        OSError: If a source cannot be read.
    """
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name in SOURCE_ROOTS:
            archive.add(ROOT / name, arcname=name, filter=source_filter)
    output.seek(0)


def run_image(image: str, targets: list[str]) -> int:
    """Execute Make with a fresh snapshot and explicitly forwarded settings.

    Args:
        image: Prepared Windows workspace environment image.
        targets: Make arguments, already split at the host boundary.

    Returns:
        Docker's exit code, including the container command's failure status.

    Raises:
        OSError: If snapshot creation or artifact-directory setup fails.
    """
    command = ["docker", "run", "--rm", "--init", "--platform", "linux/amd64", "-i"]
    for name in FORWARDED:
        if os.environ.get(name):
            command.extend(("-e", name))
    artifacts = os.environ.get("L1_TRACE_ARTIFACT_DIR")
    if artifacts:
        directory = Path(artifacts).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        command.extend(("-v", f"{directory}:/root/.wine/drive_c/trace-artifacts",
                        "-e", "L1_TRACE_ARTIFACT_DIR=C:/trace-artifacts"))
    command.extend((image, *targets))
    with tempfile.TemporaryFile() as snapshot:
        write_snapshot(snapshot)
        return subprocess.run(command, stdin=snapshot).returncode


def main() -> int:
    """Parse the explicit image/run mode and report operational failures.

    Returns:
        Zero on success, two for invalid input, or the Docker failure code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("toolchain", "image", "run"))
    args = parser.parse_args()
    try:
        targets = shlex.split(os.environ.get("CMD", "")) if args.mode == "run" else []
        if args.mode == "run" and not targets:
            parser.error("use make docker-wine CMD='<make targets and assignments>'")
        if not shutil.which("docker"):
            parser.error("Docker is required on PATH")
        image = prepare_images(os.environ.get("DOCKER_WINE_IMAGE_PREFIX") or "dea-l1-wine",
                               toolchain_only=args.mode == "toolchain")
        return run_image(image, targets) if args.mode == "run" else 0
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, ValueError) as error:
        print(f"docker-wine: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
