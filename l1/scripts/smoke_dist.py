#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Validate and run an exact L1 distribution without rebuilding its compiler."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from distribution_archive import digest, extract_archive, verify_distribution
from productization_provenance import host_target


def smoke_environment(root: Path, source: dict[str, str]) -> dict[str, str]:
    """Select host native tools and private cache, excluding development tooling."""
    env = {k: v for k, v in source.items() if not k.startswith(("L0_", "L1_", "PYTHON", "VIRTUAL_ENV", "MAKE"))}
    cc = source.get("L1_CC") or shutil.which("gcc") or shutil.which("clang")
    if not cc or not shutil.which(cc):
        raise ValueError("smoke-dist requires a compatible host C compiler; set L1_CC")
    cc = str(Path(shutil.which(cc)).resolve())
    tools = root / "host-tools"
    tools.mkdir()
    if os.name == "nt":
        # Native UCRT64 tools need their sibling DLLs and Windows system commands.
        env["PATH"] = os.pathsep.join((str(Path(cc).parent), str(Path(env["SystemRoot"]) / "System32")))
    else:
        for name in ("sh", "dirname", "readlink", "realpath", "uname", "ar", "as", "ld", "nm", "ranlib",
                     "gcc", "clang", "cc", "ldd", "readelf", "otool", "xcrun", "xcodebuild", "sw_vers"):
            executable = shutil.which(name)
            if executable:
                (tools / name).symlink_to(executable)
        env["PATH"] = str(tools)
    env.update(L1_CC=cc, L1_RUNTIME_CC=cc, L1_STDLIB_CACHE=str(root / "cache"),
               L1_HOME=str(root / "absent-source"), L1_BUILD_DIR=str(root / "absent-build"),
               TMPDIR=str(root), TMP=str(root), TEMP=str(root))
    # These selectors must never be needed by a delivered compiler.
    env.update(PYTHON=str(root / "no-python"), MAKE=str(root / "no-make"),
               L1_BOOTSTRAP_L0C=str(root / "no-l0"))
    return env


def run_smoke(prefix: Path, work: Path, env: dict[str, str]) -> None:
    """Exercise relocated, read-only compiler operation and cold/warm native support."""
    record = verify_distribution(prefix)
    current = host_target(platform.system(), platform.machine(), env)
    if current != (record["os"], record["arch"]):
        raise ValueError(f"archive targets {record['os']}-{record['arch']}; smoke host is {current[0]}-{current[1]}")
    work.mkdir()
    compiler = prefix / ("bin/l1c.cmd" if os.name == "nt" else "bin/l1c")
    source = str(prefix / "share/dea/l1/smoke/hello.l1")
    cache = Path(env["L1_STDLIB_CACHE"])
    provenance = record["provenance"]
    try:
        source_info = provenance["source"]
        commit = source_info["revision"] + ("+dirty" if source_info["tree_state"] == "dirty" else "")
        expected_version = [f"Dea language / L1 compiler (Stage 2) {record['package_version']}",
                            f"build: {provenance['build_id']}", f"build time: {provenance['build_time']}",
                            f"commit: {commit}", f"host: {record['os']}-{record['arch']}",
                            "maturity: development",
                            f"compiler: {provenance['native_compiler']['version'].splitlines()[0]}"]
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("package is missing native version provenance") from exc
    originals = {p.relative_to(prefix): digest(p) for p in prefix.rglob("*") if p.is_file() and not p.is_symlink()}
    modes = {p: stat.S_IMODE(p.stat().st_mode) for p in [prefix, *prefix.rglob("*")] if not p.is_symlink()}

    def invoke(*args: str, expected: int = 0, executable: Path = compiler, child_env: dict | None = None):
        result = subprocess.run([str(executable), *args], cwd=work, env=child_env or env,
                                text=True, capture_output=True, timeout=600)
        if result.returncode != expected:
            raise ValueError(f"smoke command {args} exited {result.returncode}, expected {expected}:\n"
                             f"{result.stdout}{result.stderr}")
        return result

    def hello(result):
        if result.stdout != "hello from Dea L1\n":
            raise ValueError(f"unexpected smoke program output: {result.stdout!r}")

    try:
        if os.name != "nt":
            for path, mode in modes.items():
                path.chmod(mode & ~0o222)
        print("smoke-dist: checking relocated launchers, native identity, and semantic-only operation", flush=True)
        for name in ("l1c", "l1c-stage2", "l1c-stage2.native"):
            executable = prefix / "bin" / (name + ".cmd" if os.name == "nt" and not name.endswith(".native") else name)
            version = invoke("--version", executable=executable).stdout
            if version.splitlines() != expected_version:
                raise ValueError(f"native version disagrees with package metadata: {version}")
            invoke("--help", executable=executable)
        native = prefix / "bin/l1c-stage2.native"
        semantic_env = {**env, "PATH": "", "L1_CC": str(work / "no-cc")}
        invoke("--check", source, executable=native, child_env=semantic_env)
        invoke("--gen", source, "-o", str(work / "hello.c"), executable=native, child_env=semantic_env)
        invoke("--compile", source, "-o", str(work / "hello.o"))
        if cache.exists():
            raise ValueError("semantic/compile-only smoke unexpectedly prepared native support")
        missing = invoke("--link", "--no-auto-prepare", str(work / "hello.o"), "-o", "missing", expected=1)
        if "L1C-2159" not in missing.stderr:
            raise ValueError("cold no-auto-prepare did not report the expected missing native profile")
        print("smoke-dist: checking standalone link, cold preparation, build/run, and warm reuse", flush=True)
        linked = work / ("linked.exe" if os.name == "nt" else "linked")
        invoke("--link", str(work / "hello.o"), "-o", str(linked))
        hello(invoke(executable=linked))
        invoke("--link", "--no-auto-prepare", str(work / "hello.o"), "-o", str(linked))
        built = work / ("built.exe" if os.name == "nt" else "built")
        invoke("--build", source, "-o", str(built))
        hello(invoke(executable=built))
        hello(invoke("--run", "--no-auto-prepare", source))
        markers = set(cache.glob("v1/native/*/manifest.json"))
        if not markers:
            raise ValueError("native smoke did not publish a managed cache profile")
        hello(invoke("--run", "--check-basic", source))
        changed_markers = set(cache.glob("v1/native/*/manifest.json"))
        if not markers < changed_markers:
            raise ValueError("native configuration switch did not retain and extend cached profiles")
        hello(invoke("--run", "--check-basic", "--no-auto-prepare", source))
        hello(invoke("--run", "--trace-memory", "--trace-arc", source))
        hello(invoke("--run", "--trace-memory", "--trace-arc", "--no-auto-prepare", source))
        hello(invoke("--run", "--no-auto-prepare", source))
        invoke("--prepare-stdlib", "--force")
        shutil.rmtree(cache)
        hello(invoke("--run", source))
        blocked_cache = work / "not-a-cache"
        blocked_cache.write_text("preserve")
        invoke("--run", "--stdlib-cache", str(blocked_cache), source, expected=1)
        invoke("--run", "--c-compiler", str(work / "missing-compiler"), source, expected=1)
        invoke("--run", "--runtime-include", str(work / "missing-headers"), source, expected=1)
        if blocked_cache.read_text() != "preserve":
            raise ValueError("invalid explicit cache was modified")
        if originals != {p.relative_to(prefix): digest(p) for p in prefix.rglob("*") if p.is_file() and not p.is_symlink()}:
            raise ValueError("compiler operations changed installed payload bytes")
        if Path(env["L1_BUILD_DIR"]).exists():
            raise ValueError("compiler used the stale inherited build root")
    finally:
        if os.name != "nt":
            for path, mode in modes.items():
                path.chmod(mode)
    verify_distribution(prefix)


def smoke(archive: Path, env: dict[str, str]) -> None:
    """Safely extract, relocate, and validate one exact native host archive."""
    if not archive.is_absolute() or not archive.is_file():
        raise ValueError("ARCHIVE must be an existing absolute archive path")
    with tempfile.TemporaryDirectory(prefix="l1-dist-smoke-") as temporary:
        root = Path(temporary).resolve()
        prefix = extract_archive(archive, root / "extracted")
        relocated = root / "relocated toolchain with spaces"
        prefix.rename(relocated)
        run_smoke(relocated, root / "unrelated working directory", smoke_environment(root, env))


def main() -> int:
    """Run the public archive smoke command with actionable failure output."""
    try:
        smoke(Path(os.environ.get("ARCHIVE", "")), dict(os.environ))
    except (OSError, RuntimeError, ValueError, tarfile.TarError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"smoke-dist: {exc}", file=sys.stderr)
        return 1
    print("smoke-dist: archive integrity, offline docs, relocation, and standalone compiler operation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
