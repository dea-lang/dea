#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Shared helpers for repo-local Dea build and install-prefix tool generation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from dea_tooling.launchers import (
    render_prefix_env_cmd_script as shared_render_prefix_env_cmd_script,
    render_prefix_env_script as shared_render_prefix_env_script,
    render_prefix_native_cmd_wrapper as shared_render_prefix_native_cmd_wrapper,
    render_prefix_native_wrapper as shared_render_prefix_native_wrapper,
    render_repo_env_cmd_script as shared_render_repo_env_cmd_script,
    render_repo_env_script as shared_render_repo_env_script,
    render_repo_native_cmd_wrapper as shared_render_repo_native_cmd_wrapper,
    render_repo_native_wrapper as shared_render_repo_native_wrapper,
    render_repo_python_stage1_cmd_wrapper as shared_render_repo_python_stage1_cmd_wrapper,
    render_repo_python_stage1_wrapper as shared_render_repo_python_stage1_wrapper,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def is_windows_host() -> bool:
    """Return whether the current Python host is Windows."""

    return os.name == "nt"


def source_tree_stage1_command(repo_root: Path) -> list[str]:
    """Return the command used to invoke the source-tree Stage 1 compiler."""

    if is_windows_host():
        cmd_path = repo_root / "scripts" / "l0c.cmd"
        if cmd_path.is_file():
            return [str(cmd_path)]
        return [sys.executable, str(repo_root / "compiler" / "stage1_py" / "l0c.py")]
    return ["./scripts/l0c"]


def stage2_wrapper_command(wrapper_path: Path) -> list[str]:
    """Return the command used to invoke one generated Stage 2 wrapper."""

    if is_windows_host():
        cmd_path = wrapper_path.with_suffix(".cmd")
        if cmd_path.is_file():
            return [str(cmd_path)]
    return [str(wrapper_path)]


@dataclass(frozen=True)
class DeaBuildLayout:
    """Resolved repo-local Dea build layout paths."""

    repo_root: Path
    dea_build_dir: Path
    bin_dir: Path
    dea_build_relative_from_repo: str
    repo_relative_from_bin: str


@dataclass(frozen=True)
class PrefixLayout:
    """Resolved Phase 3 install-prefix layout paths."""

    repo_root: Path
    prefix_dir: Path
    bin_dir: Path
    shared_dir: Path
    stdlib_dir: Path
    runtime_dir: Path


@dataclass(frozen=True)
class Stage2BuildProvenance:
    """Resolved build-provenance fields embedded into artifact-producing Stage 2 binaries."""

    commit_full: str
    commit_short: str
    tree_state: str
    build_id: str
    build_time: str
    host: str
    compiler_banner: str
    release_version: str
    source_url: str
    has_embedded_version: bool


@dataclass(frozen=True)
class Stage2BuildInfoOverlay:
    """One temporary overlay root plus the exact build env used with it."""

    overlay_root: Path
    build_env: dict[str, str]
    provenance: Stage2BuildProvenance


@dataclass(frozen=True)
class DistributionArchive:
    """One generated distribution tree plus its archive path."""

    dist_dir: Path
    archive_path: Path


def normalize_dea_build_dir(dea_build_dir_text: str) -> DeaBuildLayout:
    """Return the normalized repo-local Dea build layout."""

    if not dea_build_dir_text.strip():
        raise ValueError("DEA_BUILD_DIR must not be empty")

    raw_path = Path(dea_build_dir_text)
    if raw_path.is_absolute():
        dea_build_dir = raw_path.resolve(strict=False)
    else:
        dea_build_dir = (REPO_ROOT / raw_path).resolve(strict=False)

    try:
        dea_build_dir.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(
            f"DEA_BUILD_DIR must resolve to a subdirectory inside the repository: {dea_build_dir}"
        ) from exc

    if dea_build_dir == REPO_ROOT:
        raise ValueError(
            f"DEA_BUILD_DIR must resolve to a subdirectory inside the repository: {dea_build_dir}"
        )

    bin_dir = dea_build_dir / "bin"
    dea_build_relative_from_repo = os.path.relpath(dea_build_dir, REPO_ROOT)
    repo_relative_from_bin = os.path.relpath(REPO_ROOT, bin_dir)
    return DeaBuildLayout(
        repo_root=REPO_ROOT,
        dea_build_dir=dea_build_dir,
        bin_dir=bin_dir,
        dea_build_relative_from_repo=dea_build_relative_from_repo,
        repo_relative_from_bin=repo_relative_from_bin,
    )


def normalize_prefix_dir(prefix_dir_text: str) -> PrefixLayout:
    """Return the normalized install-prefix layout."""

    if not prefix_dir_text.strip():
        raise ValueError("PREFIX must not be empty")

    raw_path = Path(prefix_dir_text)
    if raw_path.is_absolute():
        prefix_dir = raw_path.resolve(strict=False)
    else:
        prefix_dir = (REPO_ROOT / raw_path).resolve(strict=False)

    if prefix_dir == REPO_ROOT:
        raise ValueError("PREFIX must not resolve to the repository root")

    shared_dir = prefix_dir / "shared"
    return PrefixLayout(
        repo_root=REPO_ROOT,
        prefix_dir=prefix_dir,
        bin_dir=prefix_dir / "bin",
        shared_dir=shared_dir,
        stdlib_dir=shared_dir / "l0" / "stdlib",
        runtime_dir=shared_dir / "runtime",
    )


def resolve_host_c_compiler(env: dict[str, str]) -> str | None:
    """Resolve the exact host C compiler command using the shared precedence contract."""

    from_env = env.get("L0_CC", "").strip()
    if from_env:
        return from_env

    path_text = env.get("PATH")
    if path_text is None:
        path_text = env.get("Path")
    for candidate in ("tcc", "gcc", "clang", "cc"):
        if shutil.which(candidate, path=path_text):
            return candidate

    from_cc = env.get("CC", "").strip()
    if from_cc:
        return from_cc
    return None


def _capture_first_line(command: list[str], *, cwd: Path, env: dict[str, str]) -> str | None:
    """Return the first non-empty output line for one subprocess, or `None` on failure."""

    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return None

    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _git_output(repo_root: Path, env: dict[str, str], *args: str) -> str | None:
    """Return stripped git stdout for one repo-relative command, or `None` on failure."""

    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_status_output(repo_root: Path, env: dict[str, str]) -> str | None:
    """Return normalized git status output while ignoring workflow-injected `VERSION`."""

    status_output = _git_output(repo_root, env, "status", "--porcelain", "--untracked-files=normal")
    if status_output is None:
        return None

    filtered_lines: list[str] = []
    for line in status_output.splitlines():
        path_text = line[3:].strip()
        if path_text == "VERSION":
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def format_host_triplet(kernel_name: str, kernel_release: str, machine: str) -> str:
    """Format the compact host triplet used by the Stage 2 `--version` output."""

    return " ".join((kernel_name, kernel_release, machine))


def _host_platform_text(repo_root: Path, env: dict[str, str]) -> str:
    """Return the recorded host platform text with the compact uname triplet contract."""

    if os.name != "nt":
        uname_parts: list[str] = []
        for flag in ("-s", "-r", "-m"):
            value = _capture_first_line(["uname", flag], cwd=repo_root, env=env)
            if value is None:
                uname_parts = []
                break
            uname_parts.append(value)
        if len(uname_parts) == 3:
            return format_host_triplet(uname_parts[0], uname_parts[1], uname_parts[2])

    return format_host_triplet(
        platform.system().strip() or "unknown",
        platform.release().strip() or "unknown",
        platform.machine().strip() or "unknown",
    )


def _compiler_banner_text(repo_root: Path, env: dict[str, str], compiler_text: str) -> str:
    """Return the first line of `<compiler> --version`, or `unknown` when unavailable."""

    try:
        compiler_words = shlex.split(compiler_text)
    except ValueError:
        return "unknown"
    if not compiler_words:
        return "unknown"

    version_line = _capture_first_line([*compiler_words, "--version"], cwd=repo_root, env=env)
    if version_line:
        return version_line
    return "unknown"


def format_build_time_utc(timestamp: datetime) -> str:
    """Render one UTC datetime for the Stage 2 `build time:` line."""

    return timestamp.astimezone(timezone.utc).isoformat(sep=" ", timespec="seconds")


def format_commit_for_version(commit_full: str, tree_state: str) -> str:
    """Return the Stage 2 `commit:` field text."""

    if tree_state == "dirty" and commit_full != "unknown":
        return f"{commit_full}+dirty"
    return commit_full


def _sanitize_build_id_component(text: str, default: str = "unknown") -> str:
    """Normalize one build-id component to a shell- and log-friendly token."""

    stripped = text.strip()
    if not stripped:
        return default
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in stripped)


def _derive_build_id(env: dict[str, str], commit_short: str, build_stamp: str) -> str:
    """Return the build identifier following the approved precedence order."""

    explicit = env.get("DEA_BUILD_ID", "").strip()
    if explicit:
        return explicit

    if env.get("GITHUB_ACTIONS") == "true":
        return (
            "gha-"
            f"{_sanitize_build_id_component(env.get('GITHUB_RUN_ID', ''))}."
            f"{_sanitize_build_id_component(env.get('GITHUB_RUN_ATTEMPT', ''))}-"
            f"{_sanitize_build_id_component(env.get('GITHUB_JOB', ''))}-"
            f"{_sanitize_build_id_component(env.get('RUNNER_OS', ''))}-"
            f"{_sanitize_build_id_component(env.get('RUNNER_ARCH', ''))}"
        )

    if commit_short != "unknown":
        return f"{commit_short}-{build_stamp}"
    return f"local-{build_stamp}"


_DEFAULT_SOURCE_URL = "https://github.com/googlielmo/dea-lang"


def _source_url(repo_root: Path, git_env: dict[str, str], env: dict[str, str]) -> str:
    """Derive the canonical source repository URL.

    Resolution order: GITHUB_REPOSITORY env var, git remote origin, hardcoded default.
    """

    gh_repo = env.get("GITHUB_REPOSITORY", "").strip()
    if gh_repo:
        return f"https://github.com/{gh_repo}"

    remote = _git_output(repo_root, git_env, "remote", "get-url", "origin")
    if remote:
        url = remote.removesuffix(".git")
        if url.startswith("https://"):
            return url
        if url.startswith("git@github.com:"):
            return "https://github.com/" + url.removeprefix("git@github.com:")

    return _DEFAULT_SOURCE_URL


def collect_stage2_build_provenance(repo_root: Path, env: dict[str, str]) -> tuple[Stage2BuildProvenance, str]:
    """Capture one build-provenance snapshot for Stage 2 artifact-producing flows."""

    resolved_compiler = resolve_host_c_compiler(env)
    if resolved_compiler is None:
        raise ValueError("no host C compiler found; set L0_CC or CC")

    git_env = env.copy()
    git_env.setdefault("LC_ALL", "C")
    git_env.setdefault("LANG", "C")

    commit_full = _git_output(repo_root, git_env, "rev-parse", "HEAD") or "unknown"
    commit_short = _git_output(repo_root, git_env, "rev-parse", "--short", "HEAD") or "unknown"

    status_output = _git_status_output(repo_root, git_env)
    if status_output is None:
        tree_state = "unknown"
    elif status_output == "":
        tree_state = "clean"
    else:
        tree_state = "dirty"

    build_timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    build_stamp = build_timestamp.strftime("%Y%m%dT%H%M%SZ")
    build_time = format_build_time_utc(build_timestamp)
    host = _host_platform_text(repo_root, env)
    compiler_banner = _compiler_banner_text(repo_root, env, resolved_compiler)
    build_id = _derive_build_id(env, commit_short, build_stamp)
    release_version = env.get("DEA_DIST_VERSION", "").strip()
    if not release_version:
        release_version = f"dev-{commit_short}"

    source_url = _source_url(repo_root, git_env, env)

    required_fields = (build_id, build_time, host, compiler_banner)
    has_embedded_version = all(field and field != "unknown" for field in required_fields)

    return Stage2BuildProvenance(
        commit_full=commit_full,
        commit_short=commit_short,
        tree_state=tree_state,
        build_id=build_id,
        build_time=build_time,
        host=host,
        compiler_banner=compiler_banner,
        release_version=release_version,
        source_url=source_url,
        has_embedded_version=has_embedded_version,
    ), resolved_compiler


def _render_l0_string(text: str) -> str:
    """Render one Python string as an escaped L0 string literal."""

    return json.dumps(text, ensure_ascii=True)


def render_stage2_build_info_module(provenance: Stage2BuildProvenance) -> str:
    """Render one overlay `build_info.l0` module for embedded Stage 2 provenance."""

    enabled = "true" if provenance.has_embedded_version else "false"
    commit_text = format_commit_for_version(provenance.commit_full, provenance.tree_state)
    return f"""/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

module build_info;

import std.text;

func build_info_has_embedded_version() -> bool {{
    return {enabled};
}}

func build_info_build_id() -> string {{
    return {_render_l0_string(provenance.build_id)};
}}

func build_info_build_time() -> string {{
    return {_render_l0_string(provenance.build_time)};
}}

func build_info_commit() -> string {{
    return {_render_l0_string(commit_text)};
}}

func build_info_host() -> string {{
    return {_render_l0_string(provenance.host)};
}}

func build_info_compiler() -> string {{
    return {_render_l0_string(provenance.compiler_banner)};
}}

func build_info_release_version() -> string {{
    return {_render_l0_string(provenance.release_version)};
}}

func build_info_identity_with_version(identity: string) -> string {{
    if (!build_info_has_embedded_version()) {{
        return identity;
    }}

    with (let sb = sb_create() => sb_free(sb)) {{
        sb_append(sb, identity);
        sb_append(sb, " ");
        sb_append(sb, build_info_release_version());
        return sb_to_string(sb);
    }}
}}

func build_info_version_text(identity: string) -> string? {{
    if (!build_info_has_embedded_version()) {{
        return null;
    }}

    with (let sb = sb_create() => sb_free(sb)) {{
        sb_append(sb, identity);
        sb_append(sb, " ");
        sb_append(sb, build_info_release_version());
        sb_append(sb, "\\nbuild: ");
        sb_append(sb, build_info_build_id());
        sb_append(sb, "\\nbuild time: ");
        sb_append(sb, build_info_build_time());
        sb_append(sb, "\\ncommit: ");
        sb_append(sb, build_info_commit());
        sb_append(sb, "\\nhost: ");
        sb_append(sb, build_info_host());
        sb_append(sb, "\\ncompiler: ");
        sb_append(sb, build_info_compiler());
        return sb_to_string(sb);
    }}
}}
"""


@contextmanager
def stage2_build_info_overlay(
        repo_root: Path,
        env: dict[str, str],
        *,
        temp_parent: Path | None = None,
):
    """Yield one temporary overlay root and exact build env for embedded provenance builds."""

    provenance, resolved_compiler = collect_stage2_build_provenance(repo_root, env)
    temp_dir = Path(tempfile.mkdtemp(prefix="stage2_build_info.", dir=temp_parent))
    try:
        overlay_root = temp_dir.resolve(strict=False)
        (overlay_root / "build_info.l0").write_text(
            render_stage2_build_info_module(provenance),
            encoding="utf-8",
        )
        build_env = env.copy()
        build_env["L0_CC"] = resolved_compiler
        yield Stage2BuildInfoOverlay(
            overlay_root=overlay_root,
            build_env=build_env,
            provenance=provenance,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def ensure_dea_build_bin_dir(layout: DeaBuildLayout) -> None:
    """Create the Dea build bin directory when needed."""

    layout.bin_dir.mkdir(parents=True, exist_ok=True)


def ensure_prefix_bin_dir(layout: PrefixLayout) -> None:
    """Create the install-prefix bin directory when needed."""

    layout.bin_dir.mkdir(parents=True, exist_ok=True)


def write_executable(path: Path, text: str) -> None:
    """Write one executable text file."""

    path.write_text(text, encoding="utf-8")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_relative_symlink(path: Path, target_name: str) -> None:
    """Write one sibling-relative symlink, falling back to copy on Windows."""

    if path.exists() or path.is_symlink():
        path.unlink()
    if is_windows_host():
        # Symlinks require elevated privileges on Windows; copy the selected wrapper pair instead.
        cmd_link_path = path.parent / f"{path.name}.cmd"
        if cmd_link_path.exists() or cmd_link_path.is_symlink():
            cmd_link_path.unlink()
        target_path = path.parent / target_name
        cmd_target = path.parent / f"{target_name}.cmd"
        if target_path.exists():
            shutil.copy2(target_path, path)
        if cmd_target.exists():
            shutil.copy2(cmd_target, cmd_link_path)
    else:
        path.symlink_to(target_name)


def remove_dea_build_tree(layout: DeaBuildLayout) -> None:
    """Delete one validated repo-local Dea build tree."""

    shutil.rmtree(layout.dea_build_dir, ignore_errors=True)


def copy_tree(source: Path, destination: Path) -> None:
    """Replace one directory tree with a copy of another."""

    shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def copy_file(source: Path, destination: Path) -> None:
    """Copy one file into place, creating parent directories as needed."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def render_stage1_wrapper(layout: DeaBuildLayout) -> str:
    """Return the repo-relative Stage 1 launcher."""

    return shared_render_repo_python_stage1_wrapper(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        home_var_name="L0_HOME",
        source_entry_relpath="compiler/stage1_py/l0c.py",
    )


def render_stage1_cmd_wrapper(layout: DeaBuildLayout) -> str:
    """Return the repo-local Windows batch Stage 1 launcher."""

    return shared_render_repo_python_stage1_cmd_wrapper(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        home_var_name="L0_HOME",
        source_entry_relpath="compiler/stage1_py/l0c.py",
    )


def render_stage2_wrapper(layout: DeaBuildLayout) -> str:
    """Return the repo-relative Stage 2 launcher."""

    return shared_render_repo_native_wrapper(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        home_var_name="L0_HOME",
        native_name="l0c-stage2.native",
    )


def render_stage2_cmd_wrapper(
    layout: DeaBuildLayout, native_name: str = "l0c-stage2.native"
) -> str:
    """Return the repo-local Windows batch Stage 2 launcher."""

    return shared_render_repo_native_cmd_wrapper(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        home_var_name="L0_HOME",
        native_name=native_name,
    )


def render_prefix_stage2_cmd_wrapper(
    native_name: str = "l0c-stage2.native",
) -> str:
    """Return the prefix-install Windows batch Stage 2 launcher."""

    return shared_render_prefix_native_cmd_wrapper(
        home_var_name="L0_HOME",
        native_name=native_name,
    )


def render_env_script(layout: DeaBuildLayout) -> str:
    """Return the repo-relative sourceable environment script."""

    return shared_render_repo_env_script(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        build_relative_from_repo=layout.dea_build_relative_from_repo,
        env_script_name="l0-env.sh",
        env_script_label="l0-env",
        home_var_name="L0_HOME",
        compiler_env_var="L0_CC",
    )


def render_env_cmd_script(layout: DeaBuildLayout) -> str:
    """Return the repo-local Windows activation script."""

    return shared_render_repo_env_cmd_script(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        env_script_label="l0-env",
        home_var_name="L0_HOME",
    )


def render_prefix_stage2_wrapper() -> str:
    """Return the prefix-relative Stage 2 launcher."""

    return shared_render_prefix_native_wrapper(
        home_var_name="L0_HOME",
        native_name="l0c-stage2.native",
    )


def render_prefix_env_script() -> str:
    """Return the prefix-relative sourceable environment script."""

    return shared_render_prefix_env_script(
        env_script_name="l0-env.sh",
        home_var_name="L0_HOME",
        compiler_env_var="L0_CC",
    )


def render_prefix_env_cmd_script() -> str:
    """Return the prefix-relative Windows activation script."""

    return shared_render_prefix_env_cmd_script(
        env_script_label="l0-env",
        home_var_name="L0_HOME",
    )


def write_stage1_wrapper(layout: DeaBuildLayout) -> Path:
    """Write the Stage 1 wrapper."""

    ensure_dea_build_bin_dir(layout)
    path = layout.bin_dir / "l0c-stage1"
    write_executable(path, render_stage1_wrapper(layout))
    if is_windows_host():
        (layout.bin_dir / "l0c-stage1.cmd").write_text(
            render_stage1_cmd_wrapper(layout), encoding="utf-8"
        )
    return path


def write_stage2_wrapper(layout: DeaBuildLayout) -> Path:
    """Write the Stage 2 wrapper."""

    ensure_dea_build_bin_dir(layout)
    path = layout.bin_dir / "l0c-stage2"
    write_executable(path, render_stage2_wrapper(layout))
    if is_windows_host():
        (layout.bin_dir / "l0c-stage2.cmd").write_text(
            render_stage2_cmd_wrapper(layout), encoding="utf-8"
        )
    return path


def write_env_script(layout: DeaBuildLayout) -> Path:
    """Write the repo-local Dea build environment script."""

    ensure_dea_build_bin_dir(layout)
    path = layout.bin_dir / "l0-env.sh"
    write_executable(path, render_env_script(layout))
    if is_windows_host():
        (layout.bin_dir / "l0-env.cmd").write_text(
            render_env_cmd_script(layout), encoding="utf-8"
        )
    return path


def write_prefix_stage2_wrapper(layout: PrefixLayout) -> Path:
    """Write the installed Stage 2 wrapper."""

    ensure_prefix_bin_dir(layout)
    path = layout.bin_dir / "l0c-stage2"
    write_executable(path, render_prefix_stage2_wrapper())
    if is_windows_host():
        (layout.bin_dir / "l0c-stage2.cmd").write_text(
            render_prefix_stage2_cmd_wrapper(), encoding="utf-8"
        )
    return path


def write_prefix_env_script(layout: PrefixLayout) -> Path:
    """Write the installed prefix environment script."""

    ensure_prefix_bin_dir(layout)
    path = layout.bin_dir / "l0-env.sh"
    write_executable(path, render_prefix_env_script())
    if is_windows_host():
        (layout.bin_dir / "l0-env.cmd").write_text(
            render_prefix_env_cmd_script(), encoding="utf-8"
        )
    return path


def set_alias(layout: DeaBuildLayout, stage: str) -> Path:
    """Point `l0c` at the selected stage wrapper."""

    if stage not in {"stage1", "stage2"}:
        raise ValueError(f"unknown stage: {stage}")

    ensure_dea_build_bin_dir(layout)
    target_name = "l0c-stage1" if stage == "stage1" else "l0c-stage2"
    link_path = layout.bin_dir / "l0c"
    write_relative_symlink(link_path, target_name)
    return link_path


def set_prefix_alias(layout: PrefixLayout) -> Path:
    """Point installed `l0c` at the Stage 2 wrapper."""

    ensure_prefix_bin_dir(layout)
    link_path = layout.bin_dir / "l0c"
    write_relative_symlink(link_path, "l0c-stage2")
    return link_path


def copy_prefix_shared_assets(layout: PrefixLayout) -> None:
    """Copy the shared stdlib and runtime assets into the install prefix."""

    copy_tree(REPO_ROOT / "compiler" / "shared" / "l0" / "stdlib", layout.stdlib_dir)
    copy_tree(REPO_ROOT / "compiler" / "shared" / "runtime", layout.runtime_dir)


def write_distribution_version_file(layout: PrefixLayout, provenance: Stage2BuildProvenance) -> None:
    """Write the key-value `VERSION` metadata file into one distribution tree."""

    host_parts = provenance.host.split()
    os_name = host_parts[0] if len(host_parts) >= 1 else "unknown"
    arch = host_parts[2] if len(host_parts) >= 3 else "unknown"
    commit_text = format_commit_for_version(provenance.commit_full, provenance.tree_state)

    lines = [
        f"name: dea/l0",
        f"version: {provenance.release_version}",
        f"build: {provenance.build_id}",
        f"commit: {commit_text}",
        f"os: {os_name}",
        f"arch: {arch}",
        f"author: googlielmo a.k.a. gwz <googlielmo@gmail.com>",
        f"license: MIT OR Apache-2.0",
        f"source: {provenance.source_url}",
    ]
    (layout.prefix_dir / "VERSION").write_text("\n".join(lines) + "\n")


def copy_distribution_extras(layout: PrefixLayout) -> None:
    """Copy README, examples, and reference docs into the distribution tree."""

    user_docs_dir = REPO_ROOT / "docs" / "user"
    user_doc_map = {"README.md": layout.prefix_dir / "README.md"}
    if is_windows_host():
        user_doc_map["README-WINDOWS.md"] = layout.prefix_dir / "README-WINDOWS.md"
    for source_name, destination in user_doc_map.items():
        source = user_docs_dir / source_name
        if not source.is_file():
            raise FileNotFoundError(f"missing distribution user doc: {source}")
        copy_file(source, destination)

    examples_src = REPO_ROOT / "examples"
    if examples_src.is_dir():
        copy_tree(examples_src, layout.prefix_dir / "examples")

    status_src = REPO_ROOT / "docs" / "project-status.md"
    if not status_src.is_file():
        raise FileNotFoundError(f"missing distribution project status doc: {status_src}")
    copy_file(status_src, layout.prefix_dir / "docs" / "project-status.md")

    ref_src = REPO_ROOT / "docs" / "reference"
    ref_dst = layout.prefix_dir / "docs" / "reference"
    reference_docs = (
        "architecture.md",
        "c-backend-design.md",
        "design-decisions.md",
        "grammar.md",
        "ownership.md",
        "standard-library.md",
    )
    for name in reference_docs:
        source = ref_src / name
        if not source.is_file():
            raise FileNotFoundError(f"missing distribution reference doc: {source}")
        copy_file(source, ref_dst / name)


def distribution_archive_format() -> str:
    """Return the host-appropriate archive format name."""

    return "zip" if is_windows_host() else "gztar"


def distribution_archive_suffix() -> str:
    """Return the host-appropriate distribution archive suffix."""

    return ".zip" if is_windows_host() else ".tar.gz"


def distribution_root_dir_name() -> str:
    """Return the fixed top-level directory name used inside distribution archives."""

    return "dea-l0"


def distribution_archive_target(host_text: str) -> str:
    """Return the normalized `os-arch` token derived from one recorded host line."""

    words = host_text.split()
    if len(words) < 2:
        return "unknown-unknown"
    os_name = _sanitize_build_id_component(words[0].lower())
    arch = _sanitize_build_id_component(words[-1].lower())
    return f"{os_name}-{arch}"


def distribution_archive_basename(build_timestamp: datetime, host_text: str) -> str:
    """Return the timestamped archive basename for one distribution build."""

    return (
        "dea-l0-lang_"
        f"{distribution_archive_target(host_text)}_"
        f"{build_timestamp.astimezone(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    )


def create_distribution_archive(dist_dir: Path, archive_base_name: str) -> Path:
    """Archive one prepared distribution tree next to itself."""

    archive_base = dist_dir.parent / archive_base_name
    archive_path = Path(
        shutil.make_archive(
            str(archive_base),
            distribution_archive_format(),
            root_dir=dist_dir.parent,
            base_dir=dist_dir.name,
        )
    )
    expected_suffix = distribution_archive_suffix()
    if not str(archive_path).endswith(expected_suffix):
        archive_path = Path(f"{archive_base}{expected_suffix}")
    return archive_path


def install_prefix_stage2(layout: PrefixLayout, stage2_native_source: Path) -> Path:
    """Install the Stage 2 compiler and shared assets into one prefix."""

    ensure_prefix_bin_dir(layout)
    copy_file(stage2_native_source, layout.bin_dir / "l0c-stage2.native")
    copy_prefix_shared_assets(layout)
    write_prefix_stage2_wrapper(layout)
    write_prefix_env_script(layout)
    set_prefix_alias(layout)
    return layout.bin_dir / "l0c-stage2.native"


def list_installed_files(layout: PrefixLayout) -> list[Path]:
    """Return sorted paths of all Dea/L0 files installed under one prefix."""

    files: list[Path] = []
    # bin/ entries
    for name in ("l0c", "l0c-stage2", "l0c-stage2.native", "l0-env.sh"):
        p = layout.bin_dir / name
        if p.exists() or p.is_symlink():
            files.append(p)
    if is_windows_host():
        for name in ("l0c-stage2.cmd", "l0c.cmd", "l0-env.cmd"):
            p = layout.bin_dir / name
            if p.exists():
                files.append(p)
    # shared/ trees
    for tree_root in (layout.stdlib_dir, layout.runtime_dir):
        if tree_root.is_dir():
            for child in sorted(tree_root.rglob("*")):
                if child.is_file():
                    files.append(child)
    return sorted(files)


def create_stage2_distribution(
    layout: PrefixLayout,
    stage2_native_source: Path,
    archive_base_name: str,
    provenance: Stage2BuildProvenance,
) -> DistributionArchive:
    """Create one relocatable distribution tree plus a host-native archive."""

    install_prefix_stage2(layout, stage2_native_source)
    write_distribution_version_file(layout, provenance)
    copy_distribution_extras(layout)
    archive_path = create_distribution_archive(layout.prefix_dir, archive_base_name)
    return DistributionArchive(dist_dir=layout.prefix_dir, archive_path=archive_path)
