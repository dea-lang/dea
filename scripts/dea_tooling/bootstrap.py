#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Helpers for resolving bootstrap compiler commands across language levels."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


def is_windows_host() -> bool:
    """Return whether the current Python host is Windows."""

    return os.name == "nt"


def wrapper_command(path: Path) -> list[str]:
    """Return the executable command for one wrapper/native base path."""

    if path.suffix.lower() == ".cmd":
        return [str(path)]
    if is_windows_host():
        cmd_path = path.with_suffix(".cmd")
        if cmd_path.is_file():
            return [str(cmd_path)]
    return [str(path)]


def resolve_bootstrap_compiler(
    *,
    override_text: str | None,
    default_path: Path,
    env_var_name: str,
    setup_hint: str,
) -> tuple[Path, list[str]]:
    """Resolve one explicit-or-default bootstrap compiler command."""

    selected = Path(override_text).expanduser() if override_text else default_path
    if not selected.is_absolute():
        selected = selected.resolve(strict=False)

    if selected.is_file():
        return selected, wrapper_command(selected)

    if is_windows_host():
        cmd_path = selected.with_suffix(".cmd")
        if cmd_path.is_file():
            return selected, [str(cmd_path)]

    raise RuntimeError(
        f"missing bootstrap compiler at {selected}; set {env_var_name} or {setup_hint}"
    )


def resolve_l1_toolchain(path_text: str, *, mode: str, env: dict[str, str]) -> Path:
    """Validate an explicitly selected installed or development L1 toolchain.

    Args:
        path_text: Explicit L1 compiler path, with no PATH or checkout fallback.
        mode: Installed prefix or explicitly permitted development launcher.
        env: Sanitized environment used to check the compiler identity.

    Returns:
        Absolute host-compatible compiler command path.

    Raises:
        RuntimeError: The selection, owned support, or compiler identity is invalid.
    """
    if mode not in {"installed", "development"}:
        raise RuntimeError("L2_BOOTSTRAP_MODE must be installed or development")
    if not path_text.strip():
        article = "an" if mode == "installed" else "a"
        raise RuntimeError(f"set L2_BOOTSTRAP_L1C to {article} {mode} canonical L1 compiler; "
                           "no sibling checkout or PATH fallback is used")
    compiler = Path(wrapper_command(Path(path_text).expanduser().resolve())[0])
    if is_windows_host() and not compiler.is_file() and mode == "installed":
        executable = compiler.with_suffix(".exe")
        if executable.is_file():
            compiler = executable
    layout = compiler.parent.parent
    if mode == "installed":
        try:
            record = json.loads((layout / "share/dea/l1/install-manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("L2_BOOTSTRAP_L1C must belong to a complete installed L1 prefix") from exc
        if (compiler.parent.name != "bin" or not isinstance(record, dict) or
                record.get("level") != "l1" or record.get("state") != "complete"):
            raise RuntimeError("L2_BOOTSTRAP_L1C must belong to a complete installed L1 prefix")
    else:
        native = compiler.parent / "l1c.native"
        if is_windows_host() and not native.is_file():
            native = native.with_suffix(".native.exe")
        required = (native, layout / "include/dea_rt.h", layout / "include/l1_real.h",
                    layout / "interfaces/std/types.l1m")
        if (compiler.parent.name != "bin" or compiler.name not in {"l1c", "l1c.cmd"} or
                not compiler.is_file() or not all(path.is_file() for path in required)):
            raise RuntimeError("development L1 bootstrap requires its generated bin/l1c launcher, "
                               "native binary, public headers, and semantic interfaces; run make -C l1 build")
    try:
        result = subprocess.run([str(compiler), "--version"], env=env,
                                capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"L2_BOOTSTRAP_L1C did not start as a valid {mode} L1 compiler") from exc
    banner = result.stdout.splitlines()[0] if result.stdout else ""
    if not banner.startswith("Dea language / L1 compiler") or "Stage" in banner:
        raise RuntimeError(f"incompatible L1 bootstrap identity: {banner!r}")
    return compiler


def l1_bootstrap_environment(source: dict[str, str], cache: Path) -> dict[str, str]:
    """Keep explicit L1 construction independent of active development shells.

    Args:
        source: Calling native toolchain and bootstrap environment.
        cache: Successor-owned writable upstream preparation cache.

    Returns:
        Independent environment without inherited source or runtime overrides.
    """
    env = dict(source)
    for name in ("L0_HOME", "L0_SYSTEM", "L0_RUNTIME_INCLUDE", "L0_RUNTIME_LIB", "L1_HOME", "L1_SYSTEM",
                 "L1_BUILD_DIR", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    env["L1_STDLIB_CACHE"] = str(cache)
    return env
