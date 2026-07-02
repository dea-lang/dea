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
    repo_venv = MONOREPO_ROOT / ".venv"
    shells = [("bash", ["bash", "-lc"])]
    zsh_path = shutil.which("zsh")
    if zsh_path:
        shells.append(("zsh", [zsh_path, "-fc"]))

    def check_sequence(
        label: str,
        source_lines: list[str],
        *,
        setup_lines: list[str] | None = None,
        expected_venv: Path = repo_venv,
        expected_l0_bin: Path = l0_build_dir / "bin",
        expected_l1_bin: Path = l1_build_dir / "bin",
        absent_path_entries: list[Path] | None = None,
    ) -> None:
        setup = "\n".join(setup_lines or [])
        if setup:
            setup += "\n"
        absent_checks = "".join(
            f"""
count="$(count_path_entry {shlex.quote(str(path_entry))})"
if [ "${{count}}" -ne 0 ]; then
    printf '%s\\n' "expected no PATH entry for {shlex.quote(str(path_entry))} after {label}, got ${{count}}" >&2
    printf '%s\\n' "PATH=${{PATH}}" >&2
    exit 1
fi
"""
            for path_entry in absent_path_entries or []
        )
        script = (
            """
count_path_entry() {
    needle="$1"
    count=0
    rest="${PATH}:"
    while [ -n "${rest}" ]; do
        entry="${rest%%:*}"
        rest="${rest#*:}"
        if [ "${entry}" = "${needle}" ]; then
            count=$((count + 1))
        fi
    done
    printf '%s' "${count}"
}
"""
            + setup
            + "\n".join(source_lines)
            + f"""
l0c_path="$(command -v l0c || true)"
l1c_path="$(command -v l1c || true)"
if [ -z "${{l0c_path}}" ] || [ -z "${{l1c_path}}" ]; then
    printf '%s\\n' "missing compiler after {label} (${{DEA_TEST_SHELL}}): l0c=${{l0c_path}} l1c=${{l1c_path}}" >&2
    printf '%s\\n' "PATH=${{PATH}}" >&2
    exit 1
fi
if [ "${{VIRTUAL_ENV:-}}" != {shlex.quote(str(expected_venv))} ]; then
    printf '%s\\n' "expected VIRTUAL_ENV={shlex.quote(str(expected_venv))} after {label} (${{DEA_TEST_SHELL}}), got ${{VIRTUAL_ENV:-<unset>}}" >&2
    printf '%s\\n' "PATH=${{PATH}}" >&2
    exit 1
fi
for path_entry in {shlex.quote(str(expected_venv / "bin"))} {shlex.quote(str(expected_l0_bin))} {shlex.quote(str(expected_l1_bin))}; do
    count="$(count_path_entry "${{path_entry}}")"
    if [ "${{count}}" -ne 1 ]; then
        printf '%s\\n' "expected one PATH entry for ${{path_entry}} after {label} (${{DEA_TEST_SHELL}}), got ${{count}}" >&2
        printf '%s\\n' "PATH=${{PATH}}" >&2
        exit 1
    fi
done
"""
            + absent_checks
        )
        for shell_label, shell_command in shells:
            run_checked(
                [*shell_command, script],
                cwd=MONOREPO_ROOT,
                extra_env={"DEA_TEST_SHELL": shell_label},
            )

    check_sequence(
        "l0 then l1",
        [source_command(l0_env_script), source_command(l1_env_script)],
    )
    check_sequence(
        "l1 then l0",
        [source_command(l1_env_script), source_command(l0_env_script)],
    )
    check_sequence(
        "l0 l1 l0 l1",
        [
            source_command(l0_env_script),
            source_command(l1_env_script),
            source_command(l0_env_script),
            source_command(l1_env_script),
        ],
    )

    foreign_venv = l1_build_dir / "foreign-venv"
    check_sequence(
        "stale virtualenv state between l0 and l1",
        [
            source_command(l0_env_script),
            f"export VIRTUAL_ENV={shlex.quote(str(foreign_venv))}",
            source_command(l1_env_script),
        ],
        setup_lines=[
            'base_path="${PATH}"',
            f'export PATH={shlex.quote(str(foreign_venv / "bin"))}:"${{PATH}}"',
            f"export VIRTUAL_ENV={shlex.quote(str(foreign_venv))}",
            'export _OLD_VIRTUAL_PATH="${base_path}"',
        ],
    )

    stale_root = l1_build_dir / "stale-monorepo"
    stale_l0_build_dir = stale_root / "l0" / l0_build_dir.relative_to(L0_REPO_ROOT)
    stale_l1_build_dir = stale_root / "l1" / l1_build_dir.relative_to(REPO_ROOT)
    stale_l0_build_dir.mkdir(parents=True, exist_ok=True)
    stale_l1_build_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(l0_build_dir / "bin", stale_l0_build_dir / "bin", symlinks=True)
    shutil.copytree(l1_build_dir / "bin", stale_l1_build_dir / "bin", symlinks=True)

    stale_venv = stale_root / ".venv"
    stale_activate = stale_venv / "bin" / "activate"
    stale_activate.parent.mkdir(parents=True, exist_ok=True)
    old_checkout_venv = stale_root / "renamed-from" / ".venv"
    activate_text = (repo_venv / "bin" / "activate").read_text(encoding="utf-8")
    activate_lines = activate_text.splitlines()
    for index, line in enumerate(activate_lines):
        if line.startswith("VIRTUAL_ENV="):
            activate_lines[index] = f"VIRTUAL_ENV={str(old_checkout_venv)!r}"
            break
    else:
        fail("could not find VIRTUAL_ENV assignment in repo venv activation script")
    stale_activate.write_text("\n".join(activate_lines) + "\n", encoding="utf-8")

    check_sequence(
        "stale activation script after checkout rename",
        [
            source_command(stale_l0_build_dir / "bin" / "l0-env.sh"),
            source_command(stale_l1_build_dir / "bin" / "l1-env.sh"),
        ],
        expected_venv=stale_venv,
        expected_l0_bin=stale_l0_build_dir / "bin",
        expected_l1_bin=stale_l1_build_dir / "bin",
        absent_path_entries=[old_checkout_venv / "bin"],
    )


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
