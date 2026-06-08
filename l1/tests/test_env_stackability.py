#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for stackable repo-local L0/L1 env scripts."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parent.parent
MONOREPO_ROOT = REPO_ROOT.parent
L0_REPO_ROOT = MONOREPO_ROOT / "l0"
L0_BUILD_TESTS_ROOT = L0_REPO_ROOT / "build" / "tests"
L1_BUILD_TESTS_ROOT = REPO_ROOT / "build" / "tests"


def fail(message: str) -> None:
    raise SystemExit(f"test_env_stackability: FAIL: {message}")


def is_windows_host() -> bool:
    return os.name == "nt"


def tempdir_prefix(base: str) -> str:
    return f"{base} " if is_windows_host() else f"{base}_"


def run_checked(
    command: list[str],
    *,
    cwd: Path = REPO_ROOT,
    extra_env: dict[str, str] | None = None,
) -> str:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        fail(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc.stdout + proc.stderr


def source_command(path: Path) -> str:
    return f"source {shlex.quote(str(path))}"


def source_level_envs_and_check(l0_build_dir: Path, l1_build_dir: Path) -> None:
    """Assert L0/L1 env scripts stack and do not duplicate PATH entries."""

    l0_env_script = l0_build_dir / "bin" / "l0-env.sh"
    l1_env_script = l1_build_dir / "bin" / "l1-env.sh"
    venv_bin = MONOREPO_ROOT / ".venv" / "bin"

    def check_sequence(label: str, sources: list[Path]) -> None:
        command = [
            "bash",
            "-lc",
            """
count_path_entry() {
    needle="$1"
    count=0
    old_ifs="${IFS}"
    IFS=:
    for entry in ${PATH}; do
        if [ "${entry}" = "${needle}" ]; then
            count=$((count + 1))
        fi
    done
    IFS="${old_ifs}"
    printf '%s' "${count}"
}
"""
            + "\n".join(source_command(path) for path in sources)
            + f"""
l0c_path="$(command -v l0c || true)"
l1c_path="$(command -v l1c || true)"
if [ -z "${{l0c_path}}" ] || [ -z "${{l1c_path}}" ]; then
    printf '%s\\n' "missing compiler after {label}: l0c=${{l0c_path}} l1c=${{l1c_path}}" >&2
    printf '%s\\n' "PATH=${{PATH}}" >&2
    exit 1
fi
for path_entry in {shlex.quote(str(venv_bin))} {shlex.quote(str(l0_build_dir / "bin"))} {shlex.quote(str(l1_build_dir / "bin"))}; do
    count="$(count_path_entry "${{path_entry}}")"
    if [ "${{count}}" -ne 1 ]; then
        printf '%s\\n' "expected one PATH entry for ${{path_entry}} after {label}, got ${{count}}" >&2
        printf '%s\\n' "PATH=${{PATH}}" >&2
        exit 1
    fi
done
""",
        ]
        run_checked(command, cwd=MONOREPO_ROOT)

    check_sequence("l0 then l1", [l0_env_script, l1_env_script])
    check_sequence("l1 then l0", [l1_env_script, l0_env_script])
    check_sequence("l0 l1 l0 l1", [l0_env_script, l1_env_script, l0_env_script, l1_env_script])


def main() -> int:
    if is_windows_host():
        print("test_env_stackability: SKIP: POSIX env scripts are not used on native Windows")
        return 0

    L0_BUILD_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    L1_BUILD_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    l0_build_dir = Path(tempfile.mkdtemp(prefix=tempdir_prefix("env_l0"), dir=L0_BUILD_TESTS_ROOT))
    l1_build_dir = Path(tempfile.mkdtemp(prefix=tempdir_prefix("env_l1"), dir=L1_BUILD_TESTS_ROOT))
    l0_build_rel = os.path.relpath(l0_build_dir, L0_REPO_ROOT)
    l1_build_rel = os.path.relpath(l1_build_dir, REPO_ROOT)

    try:
        run_checked(["make", f"DEA_BUILD_DIR={l0_build_rel}", "use-dev-stage2"], cwd=L0_REPO_ROOT)
        run_checked(
            ["make", f"L1_BUILD_DIR={l1_build_rel}", "use-dev-stage1"],
            extra_env={"L1_BOOTSTRAP_L0C": str(l0_build_dir / "bin" / "l0c-stage2")},
        )
        source_level_envs_and_check(l0_build_dir, l1_build_dir)
    finally:
        shutil.rmtree(l0_build_dir, ignore_errors=True)
        shutil.rmtree(l1_build_dir, ignore_errors=True)

    print("test_env_stackability: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
