#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for the `make dist` distribution workflow."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_TESTS_ROOT = REPO_ROOT / "build" / "tests"


def fail(message: str) -> None:
    raise SystemExit(f"test_make_dist_workflow: FAIL: {message}")


def is_windows_host() -> bool:
    return os.name == "nt"


def _env_value(env: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def _format_candidate_resolution(env: dict[str, str]) -> str:
    path_value = _env_value(env, "PATH", "Path")
    lines = ["candidate resolution:"]
    for candidate in ("gcc", "clang", "cc", "tcc"):
        resolved = shutil.which(candidate, path=path_value)
        lines.append(f"  {candidate}: {resolved or '<missing>'}")
    return "\n".join(lines)


def _format_file_context(path: Path) -> str:
    lines = [
        f"path exists: {path.exists()}",
        f"path is_file: {path.is_file()}",
        f"path parent: {path.parent}",
    ]
    if path.parent.exists():
        siblings = sorted(child.name for child in path.parent.iterdir())
        lines.append(f"path parent entries: {siblings}")
    if path.is_file():
        try:
            raw = path.read_bytes()
        except OSError as exc:
            lines.append(f"path read failed: {exc}")
        else:
            if b"\x00" in raw[:512]:
                lines.append(f"path is binary ({len(raw)} bytes), skipping contents")
            else:
                text = raw.decode("utf-8", errors="replace")
                lines.append("path contents:")
                lines.extend(f"  {line}" for line in text.splitlines())
    return "\n".join(lines)


def debug_context(command: list[str], env: dict[str, str] | None) -> str:
    actual_env = os.environ.copy() if env is None else env
    lines = [
        f"cwd: {REPO_ROOT}",
        f"host os.name: {os.name}",
        f"host sys.platform: {sys.platform}",
        "selected env:",
    ]
    for name in (
        "PATH",
        "Path",
        "PATHEXT",
        "SYSTEMROOT",
        "SystemRoot",
        "COMSPEC",
        "ComSpec",
        "WINDIR",
        "OS",
        "MSYSTEM",
        "L0_CC",
        "CC",
    ):
        lines.append(f"  {name}={actual_env.get(name, '<unset>')}")

    path_value = _env_value(actual_env, "PATH", "Path")
    if path_value is not None:
        lines.append(f"selected PATH entries: {path_value.split(os.pathsep)}")

    if is_windows_host():
        system_root = _env_value(actual_env, "SYSTEMROOT", "SystemRoot")
        where_path = Path(system_root) / "System32" / "where.exe" if system_root else None
        if where_path is not None:
            lines.append(f"system where.exe: {where_path} exists={where_path.exists()}")

    lines.append(_format_candidate_resolution(actual_env))

    command_path = Path(command[0])
    if command_path.suffix.lower() == ".cmd":
        lines.append("launcher context:")
        lines.append(_format_file_context(command_path))
        native_path = command_path.with_suffix(".native")
        lines.append("native context:")
        lines.append(_format_file_context(native_path))

    return "\n".join(lines)


def run_checked(command: list[str], *, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        fail(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}\n"
            f"context:\n{debug_context(command, env)}"
        )
    return proc.stdout + proc.stderr


def assert_exists(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        fail(f"expected path: {path}")


def assert_contains(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        fail(f"expected {needle!r} in {path}")


def assert_text_equals(path: Path, expected: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text != expected:
        fail(f"expected exact contents {expected!r} in {path}, got {text!r}")


def assert_not_contains(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle in text:
        fail(f"did not expect {needle!r} in {path}")


def assert_missing(path: Path) -> None:
    if path.exists() or path.is_symlink():
        fail(f"did not expect path: {path}")


def assert_same_file_tree(source: Path, destination: Path) -> None:
    source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
    destination_files = sorted(path.relative_to(destination) for path in destination.rglob("*") if path.is_file())
    if source_files != destination_files:
        source_only = sorted(set(source_files) - set(destination_files))
        destination_only = sorted(set(destination_files) - set(source_files))
        fail(
            f"file tree mismatch for {source} -> {destination}: "
            f"missing={source_only}, unexpected={destination_only}"
        )


def clean_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for name in ("PATH", "Path"):
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    if "PATH" not in env and "Path" not in env:
        env["PATH"] = ""
    if is_windows_host():
        for name in ("PATHEXT", "SYSTEMROOT", "SystemRoot", "COMSPEC", "ComSpec", "WINDIR", "OS", "MSYSTEM", "TEMP", "TMP"):
            value = os.environ.get(name)
            if value:
                env[name] = value
    return env


def stage2_launcher_path(base: Path) -> str:
    if is_windows_host():
        cmd_path = base.with_suffix(".cmd")
        if cmd_path.is_file():
            return str(cmd_path)
    return str(base)


def extract_archive(archive_path: Path, destination: Path) -> None:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)
        return
    if archive_path.name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(destination)
        return
    fail(f"unexpected archive format: {archive_path}")


def assert_version_report(text: str) -> None:
    for expected in (
        "Dea language / L0 compiler",
        "build: ",
        "build time: ",
        "commit: ",
        "host: ",
        "compiler: ",
    ):
        if expected not in text:
            fail(f"expected {expected!r} in version output:\n{text}")


def parse_host_target(version_text: str) -> str:
    match = re.search(r"^host: (.+)$", version_text, flags=re.MULTILINE)
    if match is None:
        fail(f"could not parse host line from version output:\n{version_text}")
    words = match.group(1).split()
    if len(words) < 2:
        fail(f"unexpected host line: {match.group(1)!r}")
    return f"{words[0].lower()}-{words[-1].lower()}"


def make_hello_project(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "hello.l0").write_text(
        """module hello;

import std.io;

func main() -> int {
    printl_s("Hello, World!");
    return 0;
}
""",
        encoding="utf-8",
    )


def main() -> int:
    BUILD_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    extract_root = Path(tempfile.mkdtemp(prefix="make_dist_unpack.", dir=BUILD_TESTS_ROOT))
    project_dir = Path(tempfile.mkdtemp(prefix="make_dist_project.", dir=BUILD_TESTS_ROOT))

    try:
        build_env = os.environ.copy()
        build_env.pop("L0_CFLAGS", None)
        output = run_checked(["make", "dist"], env=build_env)
        dist_match = re.search(r"created distribution directory at (.+)", output)
        archive_match = re.search(r"created distribution archive at (.+)", output)
        if dist_match is None:
            fail(f"could not find distribution directory in output:\n{output}")
        if archive_match is None:
            fail(f"could not find distribution archive in output:\n{output}")
        expected_cflags = (
            "gen-dea-build-tools: L0_CFLAGS='-O2 -static -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256'"
            if is_windows_host()
            else "gen-dea-build-tools: L0_CFLAGS='-O2 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256'"
        )
        if expected_cflags not in output:
            fail(f"expected '{expected_cflags}' in output:\n{output}")

        dist_dir = Path(dist_match.group(1).strip())
        archive_path = Path(archive_match.group(1).strip())
        if dist_dir.name != "dea-l0":
            fail(f"expected distribution directory name 'dea-l0', got {dist_dir.name!r}")
        expected_suffix = ".zip" if is_windows_host() else ".tar.gz"
        if not str(archive_path).endswith(expected_suffix):
            fail(f"expected archive suffix {expected_suffix!r}, got {archive_path}")
        assert_exists(dist_dir / "bin" / "l0c-stage2")
        assert_exists(dist_dir / "bin" / "l0c-stage2.native")
        assert_exists(dist_dir / "bin" / "l0c")
        assert_exists(dist_dir / "bin" / "l0-env.sh")
        if is_windows_host():
            assert_exists(dist_dir / "bin" / "l0-env.cmd")
        assert_exists(dist_dir / "VERSION")
        assert_exists(dist_dir / "README.md")
        assert_exists(dist_dir / "README-WINDOWS.md")
        assert_exists(dist_dir / "shared" / "l0" / "stdlib" / "std" / "io.l0")
        assert_exists(dist_dir / "docs" / "README.md")
        assert_exists(dist_dir / "docs" / "project-status.md")
        assert_exists(dist_dir / "docs" / "reference" / "grammar.md")
        assert_exists(dist_dir / "docs" / "specs" / "compiler" / "cli-contract.md")
        assert_exists(dist_dir / "docs" / "specs" / "runtime" / "trace.md")
        assert_exists(dist_dir / "docs" / "user" / "README.md")
        assert_exists(dist_dir / "docs" / "user" / "README-WINDOWS.md")
        assert_same_file_tree(REPO_ROOT / "docs", dist_dir / "docs")
        assert_missing(dist_dir / "CONTRIBUTING.md")
        assert_exists(dist_dir / "shared" / "runtime" / "l0_runtime.h")
        assert_exists(archive_path)
        assert_not_contains(dist_dir / "bin" / "l0c-stage2", str(REPO_ROOT))
        assert_not_contains(dist_dir / "bin" / "l0-env.sh", str(REPO_ROOT))
        assert_contains(dist_dir / "VERSION", "name: dea/l0")
        assert_contains(dist_dir / "VERSION", "version: ")
        assert_contains(dist_dir / "VERSION", "build: ")
        assert_contains(dist_dir / "VERSION", "commit: ")
        assert_contains(dist_dir / "VERSION", "os: ")
        assert_contains(dist_dir / "VERSION", "arch: ")
        assert_contains(dist_dir / "VERSION", "author: ")
        assert_contains(dist_dir / "VERSION", "license: MIT OR Apache-2.0")
        assert_contains(dist_dir / "VERSION", "source: https://github.com/")
        assert_not_contains(dist_dir / "README.md", "MONOREPO.md")
        assert_not_contains(dist_dir / "README.md", "CONTRIBUTING.md")
        assert_not_contains(dist_dir / "README.md", "compiler/stage2_l0/README.md")
        assert_not_contains(dist_dir / "README.md", "cd` into `l0/")

        extract_archive(archive_path, extract_root)
        unpacked_dist = extract_root / "dea-l0"
        assert_exists(unpacked_dist / "bin" / "l0c-stage2")
        assert_exists(unpacked_dist / "bin" / "l0c-stage2.native")
        assert_exists(unpacked_dist / "bin" / "l0c")
        if is_windows_host():
            assert_exists(unpacked_dist / "bin" / "l0-env.cmd")
        assert_exists(unpacked_dist / "VERSION")
        assert_exists(unpacked_dist / "README.md")
        assert_exists(unpacked_dist / "README-WINDOWS.md")
        assert_exists(unpacked_dist / "docs" / "README.md")
        assert_exists(unpacked_dist / "docs" / "project-status.md")
        assert_exists(unpacked_dist / "docs" / "reference" / "grammar.md")
        assert_exists(unpacked_dist / "docs" / "specs" / "compiler" / "cli-contract.md")
        assert_exists(unpacked_dist / "docs" / "specs" / "runtime" / "trace.md")
        assert_exists(unpacked_dist / "docs" / "user" / "README.md")
        assert_exists(unpacked_dist / "docs" / "user" / "README-WINDOWS.md")
        assert_same_file_tree(REPO_ROOT / "docs", unpacked_dist / "docs")
        assert_missing(unpacked_dist / "CONTRIBUTING.md")
        assert_exists(unpacked_dist / "shared" / "l0" / "stdlib" / "std" / "io.l0")
        assert_contains(unpacked_dist / "bin" / "l0-env.sh", 'export L0_HOME="${PREFIX_DIR}"')
        assert_contains(unpacked_dist / "VERSION", "name: dea/l0")
        assert_contains(unpacked_dist / "VERSION", "version: ")
        assert_contains(unpacked_dist / "VERSION", "build: ")
        assert_contains(unpacked_dist / "VERSION", "commit: ")
        assert_contains(unpacked_dist / "VERSION", "os: ")
        assert_contains(unpacked_dist / "VERSION", "arch: ")
        assert_contains(unpacked_dist / "VERSION", "author: ")
        assert_contains(unpacked_dist / "VERSION", "license: MIT OR Apache-2.0")
        assert_contains(unpacked_dist / "VERSION", "source: https://github.com/")
        assert_not_contains(unpacked_dist / "README.md", "MONOREPO.md")
        assert_not_contains(unpacked_dist / "README.md", "CONTRIBUTING.md")
        assert_not_contains(unpacked_dist / "README.md", "compiler/stage2_l0/README.md")
        assert_not_contains(unpacked_dist / "README.md", "cd` into `l0/")

        wrapper_version = run_checked([stage2_launcher_path(unpacked_dist / "bin" / "l0c-stage2"), "--version"], env=clean_env())
        native_version = run_checked([str(unpacked_dist / "bin" / "l0c-stage2.native"), "--version"], env=clean_env())
        assert_version_report(wrapper_version)
        if native_version != wrapper_version:
            fail("expected extracted wrapper/native --version output to match")
        archive_pattern = (
            rf"^dea-l0-lang_{re.escape(parse_host_target(wrapper_version))}_\d{{8}}-\d{{6}}"
            + (r"\.zip$" if is_windows_host() else r"\.tar\.gz$")
        )
        if re.match(archive_pattern, archive_path.name) is None:
            fail(f"unexpected archive name: {archive_path.name}")

        make_hello_project(project_dir)
        hello_bin = project_dir / "hello"
        if is_windows_host():
            hello_bin = hello_bin.with_suffix(".exe")
        run_checked(
            [
                stage2_launcher_path(unpacked_dist / "bin" / "l0c-stage2"),
                "--build",
                "-P",
                str(project_dir),
                "-o",
                str(hello_bin),
                "hello",
            ],
            env=clean_env(),
        )
        hello_output = run_checked([str(hello_bin)], env=clean_env())
        if "Hello, World!" not in hello_output:
            fail(f"expected Hello, World! from built binary, got:\n{hello_output}")
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)

    print("test_make_dist_workflow: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
