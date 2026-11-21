#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Private L1 temporary objects, pinned cleanup, injected failures and public interfaces."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from entropy_runtime_test import build
from file_runtime_test import check_trace
from os_runtime_test import L1_ROOT, RUNTIME_ROOT, compiler_path, require_success, runtime_c_compiler


FIXTURES = L1_ROOT / "compiler/tests/fixtures/temp_runtime"


def parent_environment(parent: Path) -> dict[str, str]:
    """Select the given default parent for POSIX and ordinary or SYSTEM Windows processes.

    Args:
        parent: Directory spelling to present to host discovery.

    Returns:
        A child environment with the host temporary path overrides set.
    """
    return {**os.environ, **dict.fromkeys(("TMPDIR", "TMP", "TEMP", "SystemTemp"), str(parent))}


def run(work: Path, executable: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """Run a fixture in its owned directory and return the trace.

    Args:
        work: Working directory used for relative parents.
        executable: Compiled L1 program.
        args: Fixture arguments.
        env: Optional complete environment.

    Returns:
        Captured standard error.

    Raises:
        AssertionError: The fixture fails.
    """
    result = subprocess.run([str(executable), *args], cwd=work, env=env, capture_output=True,
                            text=True, timeout=90, check=False, **({} if os.name == "nt" else {"umask": 0o022}))
    assert result.returncode == 0, (work, args, result.returncode, result.stdout, result.stderr[-6000:])
    return result.stderr


def directory_link(target: Path, link: Path) -> None:
    """Create a directory link without requiring Windows developer mode.

    Args:
        target: Existing directory.
        link: New link spelling.

    Raises:
        OSError: POSIX link creation fails.
        subprocess.CalledProcessError: Native Windows junction creation fails.
    """
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/j", link.name, str(target)],
                       cwd=link.parent, check=True, timeout=30, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def main() -> int:
    """Run public contracts, fault injection, and bundled-interface compilation.

    Returns:
        Zero after all contracts pass.

    Raises:
        AssertionError: Any contract or native build fails.
    """
    cc = runtime_c_compiler()
    print(f"temp_runtime_test: {cc} {require_success([cc, '--version']).stdout.splitlines()[0]}", flush=True)
    # MSYS2's shared tmp hierarchy can legitimately fail std.temp's ownership checks.
    profile = os.environ["LOCALAPPDATA"] if os.name == "nt" else None
    with tempfile.TemporaryDirectory(prefix="dea temp ", dir=profile) as temp:
        work = Path(temp)
        parent = work / "parent with spaces"
        parent.mkdir()
        alias = work / "trusted alias"
        directory_link(parent, alias)
        public = build(work, "temp_main", cc, ("--trace-arc", "--trace-memory"), project_root=FIXTURES)
        env = parent_environment(work) if os.name == "nt" else None
        for label, args in (("default", ()), ("relative", (parent.name,)), ("alias", (alias.name,)),
                            ("missing", ("absent", "reject"))):
            check_trace(work, label, run(work, public, *args, env=env))
        check_trace(work, "selected-default", run(work, public, parent.name, "selected-default",
                                                  env=parent_environment(parent)))
        check_trace(work, "bad-default", run(work, public, parent.name, "bad-default",
                                             env=parent_environment(work / "absent")))
        unsafe = work / "unprotected"
        unsafe.mkdir()
        if os.name == "nt":
            run(work, public, str(parent).replace("\\", "/", 1))
            subprocess.run(["icacls.exe", str(unsafe), "/grant", "*S-1-1-0:(DC)"],
                           check=True, capture_output=True, timeout=30)
        else:
            unsafe.chmod(0o777)
        directory_link(parent, unsafe / "alias")
        check_trace(work, "untrusted", run(work, public, str(unsafe / "alias"), "untrusted",
                                           env=parent_environment(unsafe)))
        assert not list(parent.iterdir())

        compiler = compiler_path()
        bundled = compiler.parent.parent / "interfaces"
        assert "opaque struct TempFile;" in (bundled / "std/temp.l1m").read_text(encoding="utf-8")
        empty = work / "empty sources"
        empty.mkdir()
        require_success([str(compiler), "--no-managed-stdlib", "--sys-root", str(empty), "-I", str(bundled),
                         "--project-root", str(FIXTURES), "--c-compiler", cc, "-c", "temp_main",
                         "-o", str(work / "interface-consumer.o")], timeout=120)

        outside = parent / "outside"
        outside.mkdir()
        (outside / "keep").write_bytes(b"outside")
        prepared = parent / "prepared"
        prepared.mkdir()
        directory_link(outside, prepared / "link")
        shim = work / "faults.o"
        require_success([cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                         "-DDEA_TRACE_ARC", "-DDEA_TRACE_MEMORY", "-I" + str(RUNTIME_ROOT / "include"),
                         "-I" + str(RUNTIME_ROOT / "src"), "-c", str(FIXTURES / "temp_faults.c"),
                         "-o", str(shim)], timeout=120)
        injected = build(work, "temp_failure_main", cc,
                         ("--trace-arc", "--trace-memory", "--foreign-object", str(shim)),
                         library=compiler.parent.parent / "lib", project_root=FIXTURES)
        check_trace(work, "injected", run(work, injected, parent.name))
        assert (outside / "keep").read_bytes() == b"outside"
        assert sorted(p.name for p in parent.iterdir()) == ["dea-" + "0" * 32, "outside", "published"]
    print("temp_runtime_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
