#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Focused regression for Stage 2 provenance fallback without Git availability."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dist_tools_lib import (
    collect_stage2_build_provenance,
    distribution_archive_basename,
    distribution_archive_target,
    format_commit_for_version,
    render_stage2_build_info_module,
    resolve_host_c_compiler,
)


def fail(message: str) -> None:
    raise SystemExit(f"test_dist_tools_lib_fallback: FAIL: {message}")


def fake_subprocess_run(command: list[str], **_: object) -> SimpleNamespace:
    tool = command[0]
    if tool == "git":
        raise FileNotFoundError("git")
    if tool == "uname":
        mapping = {
            "-s": "Darwin\n",
            "-r": "24.6.0\n",
            "-m": "x86_64\n",
        }
        return SimpleNamespace(returncode=0, stdout=mapping[command[1]], stderr="")
    if tool == "gcc":
        return SimpleNamespace(
            returncode=0,
            stdout="gcc-15 (Homebrew GCC 15.2.0_1) 15.2.0\n",
            stderr="",
        )
    fail(f"unexpected subprocess command: {command!r}")


def fake_which(tool: str, path: str | None = None) -> str | None:
    if tool == "gcc" and path == "C:\\msys64\\ucrt64\\bin":
        return f"{path}\\gcc.exe"
    return None


def local_fallback_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "DEA_BUILD_ID",
        "GITHUB_ACTIONS",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_JOB",
        "RUNNER_OS",
        "RUNNER_ARCH",
    ):
        env.pop(name, None)
    env["L0_CC"] = "gcc"
    return env


def main() -> int:
    env = local_fallback_env()

    with (
        patch("dist_tools_lib.subprocess.run", side_effect=fake_subprocess_run),
        patch("dist_tools_lib.os.name", "posix"),
    ):
        provenance, resolved_compiler = collect_stage2_build_provenance(REPO_ROOT, env)

    if resolved_compiler != "gcc":
        fail(f"expected resolved compiler 'gcc', got {resolved_compiler!r}")
    if provenance.commit_full != "unknown":
        fail(f"expected unknown commit without git, got {provenance.commit_full!r}")
    if provenance.tree_state != "unknown":
        fail(f"expected unknown tree state without git, got {provenance.tree_state!r}")
    if not provenance.build_id.startswith("local-"):
        fail(f"expected local fallback build id, got {provenance.build_id!r}")
    if provenance.build_time.endswith("+00:00") is False:
        fail(f"expected UTC offset build time, got {provenance.build_time!r}")
    if provenance.host != "Darwin 24.6.0 x86_64":
        fail(f"unexpected host text: {provenance.host!r}")
    if distribution_archive_target(provenance.host) != "darwin-x86_64":
        fail(f"unexpected archive target: {distribution_archive_target(provenance.host)!r}")
    if provenance.compiler_banner != "gcc-15 (Homebrew GCC 15.2.0_1) 15.2.0":
        fail(f"unexpected compiler banner: {provenance.compiler_banner!r}")
    if not provenance.has_embedded_version:
        fail("expected embedded version output to remain enabled without git metadata")
    if provenance.release_version != "dev":
        fail(f"expected 'dev' release version without git, got {provenance.release_version!r}")

    gha_env = local_fallback_env()
    gha_env.update(
        {
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": "23854449995",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_JOB": "test-all",
            "RUNNER_OS": "Linux",
            "RUNNER_ARCH": "X64",
        }
    )
    with (
        patch("dist_tools_lib.subprocess.run", side_effect=fake_subprocess_run),
        patch("dist_tools_lib.os.name", "posix"),
    ):
        gha_provenance, gha_resolved_compiler = collect_stage2_build_provenance(REPO_ROOT, gha_env)
    if gha_resolved_compiler != "gcc":
        fail(f"expected GHA resolved compiler 'gcc', got {gha_resolved_compiler!r}")
    if gha_provenance.build_id != "gha-23854449995.1-test-all-Linux-X64":
        fail(f"expected GitHub Actions build id, got {gha_provenance.build_id!r}")
    if gha_provenance.commit_full != "unknown":
        fail(f"expected unknown commit without git in GHA env, got {gha_provenance.commit_full!r}")
    if gha_provenance.tree_state != "unknown":
        fail(f"expected unknown tree state without git in GHA env, got {gha_provenance.tree_state!r}")

    rendered = render_stage2_build_info_module(provenance)
    for expected in ("build: ", "build time: ", "commit: ", "host: ", "compiler: "):
        if expected not in rendered:
            fail(f"expected {expected!r} in rendered build_info module")
    if 'func build_info_commit() -> string {\n    return "unknown";\n}' not in rendered:
        fail("expected rendered build_info module to embed an unknown commit field")
    if 'func build_info_host() -> string {\n    return "Darwin 24.6.0 x86_64";\n}' not in rendered:
        fail("expected rendered build_info module to embed the compact host triplet")
    if 'func build_info_compiler() -> string {\n    return "gcc-15 (Homebrew GCC 15.2.0_1) 15.2.0";\n}' not in rendered:
        fail("expected rendered build_info module to embed the compiler banner")
    if distribution_archive_basename(datetime.fromisoformat("2026-03-16 08:31:20+00:00"), provenance.host) != (
        "dea-l0-lang_darwin-x86_64_20260316-083120"
    ):
        fail("unexpected archive basename")

    path_env = os.environ.copy()
    path_env.pop("L0_CC", None)
    path_env.pop("CC", None)
    path_env.pop("PATH", None)
    path_env["Path"] = "C:\\msys64\\ucrt64\\bin"
    with patch("dist_tools_lib.shutil.which", side_effect=fake_which):
        resolved_from_path = resolve_host_c_compiler(path_env)
    if resolved_from_path != "gcc":
        fail(f"expected Windows Path fallback to resolve 'gcc', got {resolved_from_path!r}")

    with patch(
        "dist_tools_lib._git_output",
        side_effect=[
            "0123456789abcdef0123456789abcdef01234567",
            "0123456",
            "?? VERSION",
            "https://github.com/dea-lang/dea",
        ],
    ) as git_output:
        clean_version_only, _ = collect_stage2_build_provenance(REPO_ROOT, env)
    if git_output.call_args_list[-1].args[2:] != ("remote", "get-url", "origin"):
        fail("expected provenance collection to inspect the conventional origin remote")
    if clean_version_only.source_url != "https://github.com/dea-lang/dea":
        fail(f"unexpected origin-derived source URL: {clean_version_only.source_url!r}")
    if clean_version_only.tree_state != "clean":
        fail(f"expected VERSION-only dirty state to be ignored, got {clean_version_only.tree_state!r}")
    if format_commit_for_version(clean_version_only.commit_full, clean_version_only.tree_state).endswith("+dirty"):
        fail("did not expect a workflow-injected VERSION file to mark the commit dirty")

    github_env = env.copy()
    github_env["GITHUB_REPOSITORY"] = "dea-lang/dea"
    with patch(
        "dist_tools_lib._git_output",
        side_effect=[
            "0123456789abcdef0123456789abcdef01234567",
            "0123456",
            "?? VERSION",
        ],
    ) as git_output:
        github_provenance, _ = collect_stage2_build_provenance(REPO_ROOT, github_env)
    if any(call.args[2:] == ("remote", "get-url", "origin") for call in git_output.call_args_list):
        fail("expected GITHUB_REPOSITORY provenance to bypass the origin remote")
    if github_provenance.source_url != "https://github.com/dea-lang/dea":
        fail(f"unexpected GitHub Actions source URL: {github_provenance.source_url!r}")

    print("test_dist_tools_lib_fallback: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
