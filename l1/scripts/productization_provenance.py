# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Capture and render one L1 Stage 2 package identity before construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import subprocess

from build_stage2_l1c import compiler_build_env
from dea_tooling.bootstrap import wrapper_command
from productization_inventory import MANIFEST_PATH, validate_inventory

SOURCE_URL = "https://github.com/dea-lang/dea"
L1_ROOT = Path(__file__).resolve().parents[1]


def package_version(env: dict[str, str]) -> str:
    """Select the explicit version or development default, never a Git tag.

    Args:
        env: Explicit packaging environment.

    Returns:
        Portable package version token.

    Raises:
        ValueError: A nonempty override is unsafe for an archive filename.
    """
    value = env.get("DEA_DIST_VERSION", "").strip() or "dev"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value):
        raise ValueError("DEA_DIST_VERSION must be a portable package version token")
    return value


def host_target(system: str, machine: str, env: dict[str, str]) -> tuple[str, str]:
    """Normalize the supported native host matrix without claiming cross compilation.

    Args:
        system: Host OS reported by Python.
        machine: Host architecture reported by Python.
        env: Build environment, including the Windows MSYS2 subsystem.

    Returns:
        Inventory OS and architecture tokens.

    Raises:
        ValueError: The host is outside the initial package support matrix.
    """
    os_name = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(system)
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}.get(machine.lower())
    if (os_name, arch) not in {("linux", "x86_64"), ("macos", "x86_64"),
                               ("macos", "arm64"), ("windows", "x86_64")}:
        raise ValueError(f"unsupported L1 package host: {system}/{machine}")
    if os_name == "windows" and env.get("MSYSTEM") != "UCRT64":
        raise ValueError("Windows L1 packages require the UCRT64 build environment")
    return os_name, arch


def _version(path: Path, env: dict[str, str], cwd: Path, identity: str | None = None) -> str:
    """Probe an explicitly selected compiler and reject missing or wrong identities."""
    output = subprocess.check_output([*wrapper_command(path), "--version"], cwd=cwd, env=env, text=True).strip()
    if not output or "\x00" in output or (identity is not None and identity not in output.splitlines()[0]):
        raise ValueError(f"unexpected compiler identity from {path}")
    return output


def _source(root: Path, env: dict[str, str]) -> dict[str, str]:
    """Record source revision and cleanliness, explicitly unknown outside Git."""
    git_env = {key: value for key, value in env.items() if not key.startswith("GIT_")}
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, env=git_env,
                                           stderr=subprocess.DEVNULL, text=True).strip()
        state = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"],
                                        cwd=root, env=git_env, stderr=subprocess.DEVNULL, text=True)
    except (OSError, subprocess.CalledProcessError):
        revision, state = "unknown", None
    return {"url": SOURCE_URL, "revision": revision,
            "tree_state": "unknown" if state is None else ("dirty" if state else "clean")}


@dataclass(frozen=True)
class PackageProvenance:
    """Immutable serialized snapshot shared by all package metadata renderers."""

    _json: str

    def metadata(self) -> dict:
        """Return an independent inventory metadata object."""
        return json.loads(self._json)

    def version_text(self) -> str:
        """Render standalone VERSION metadata, including all construction evidence."""
        return "Dea language / L1 compiler (Stage 2)\n" + json.dumps(self.metadata(), indent=2, sort_keys=True) + "\n"

    def build_info_module(self, *, installed: bool = False) -> str:
        """Render provenance and optionally enable the native installation guard.

        Args:
            installed: Require physical prefix metadata before every command.

        Returns:
            L1 source suitable for the builder's private module overlay.

        Raises:
            ValueError: The checked-in build-info interface no longer matches.
        """
        metadata = self.metadata()
        provenance = metadata["provenance"]
        source = provenance["source"]
        commit = source["revision"] + ("+dirty" if source["tree_state"] == "dirty" else "")
        values = {"is_installed": installed, "has_embedded_version": True, "build_id": provenance["build_id"],
                  "build_time": provenance["build_time"], "commit": commit,
                  "host": f'{metadata["os"]}-{metadata["arch"]}',
                  "compiler": provenance["native_compiler"]["version"].splitlines()[0],
                  "release_version": metadata["package_version"]}
        text = (L1_ROOT / "compiler/stage2_l1/src/build_info.l1").read_text(encoding="utf-8")
        for name, value in values.items():
            literal = json.dumps(value, ensure_ascii=False)
            pattern = rf'(func build_info_{name}\(\) -> (?:bool|string) \{{\n)    return [^\n]+;\n\}}'
            text, count = re.subn(pattern, lambda match: match[1] + f"    return {literal};\n}}", text)
            if count != 1:
                raise ValueError(f"unexpected build_info interface: {name}")
        # Keep development maturity visible even when an explicit version looks stable.
        needle = '        sb_append(sb, "\\ncompiler: ");'
        if text.count(needle) != 1:
            raise ValueError("unexpected build_info version report")
        return text.replace(needle, '        sb_append(sb, "\\nmaturity: development");\n' + needle)


def collect_provenance(
    root: Path, env: dict[str, str], *, upstream: Path, stage1: Path, stage2: Path,
    stage1_options: list[str], preparation_inputs: dict[str, str],
    preparation_identity: str | None = None, now: datetime | None = None,
) -> tuple[PackageProvenance, dict[str, str]]:
    """Capture explicit bootstrap and effective self-build inputs once.

    Args:
        root: L1 source root used for Git evidence and relative compiler paths.
        env: Calling environment; only selected build options enter provenance.
        upstream: Explicit upstream L0 compiler used to build Stage 1.
        stage1: Explicit L1 Stage 1 artifact used to build the Stage 2 seed.
        stage2: Explicit repository-mode Stage 2 seed for the delivered generation.
        stage1_options: Recorded arguments from the actual Stage 1 construction.
        preparation_inputs: Shipped prefix-relative input names and SHA-256 digests.
        preparation_identity: Optional identity exported by the preparation service.
        now: Aware build timestamp; defaults to current UTC.

    Returns:
        Immutable metadata snapshot and the effective environment to pass to the
        Stage 2 builder. Compiler paths are evidence, never installed lookup roots.

    Raises:
        ValueError: Version, host, timestamp, input digests, or identities are invalid.
        OSError: A selected compiler cannot be invoked.
        subprocess.CalledProcessError: A selected compiler version probe fails.
    """
    version = package_version(env)
    os_name, arch = host_target(platform.system(), platform.machine(), env)
    timestamp = now if now is not None else datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("package build time must have a timezone")
    timestamp = timestamp.astimezone(timezone.utc).replace(microsecond=0)
    if not isinstance(preparation_inputs, dict) or not preparation_inputs:
        raise ValueError("package preparation inputs must not be empty")
    # Use the inventory's path/digest validation instead of a competing path policy.
    metadata = {"package_version": version, "maturity": "development", "os": os_name, "arch": arch,
                "provenance": {"pending": True}}
    validate_inventory({**metadata, "schema_version": 1, "level": "l1", "stage": 2, "state": "complete",
                        "entries": [{"path": MANIFEST_PATH, "kind": "manifest", "mode": 0o644},
                                    *[{"path": path, "kind": "file", "mode": 0o644, "sha256": digest}
                                      for path, digest in preparation_inputs.items()]]})
    if not isinstance(stage1_options, list) or not all(
            isinstance(option, str) and "\x00" not in option for option in stage1_options):
        raise ValueError("Stage 1 options must be argument strings")
    if preparation_identity is not None and (not isinstance(preparation_identity, str) or not preparation_identity.strip()):
        raise ValueError("exported preparation identity must be nonempty")
    build_env, mode = compiler_build_env(env)
    bootstrap = {}
    for name, path, identity in (("upstream_l0", upstream, "Dea language / L0 compiler"),
                                  ("l1_stage1", stage1, "Dea language / L1 compiler (Stage 1)"),
                                  ("l1_stage2_seed", stage2, "Dea language / L1 compiler (Stage 2)")):
        absolute = (root / path).absolute()
        bootstrap[name] = {"path": str(absolute), "version": _version(absolute, build_env, root, identity)}
    native = Path(build_env["L1_CC"])
    source = _source(root, env)
    stamp = timestamp.strftime("%Y%m%d-%H%M%S")
    provenance = {"source": source, "build_id": f'{source["revision"][:12]}-{stamp}',
                  "build_time": timestamp.isoformat().replace("+00:00", "Z"),
                  "bootstrap": bootstrap, "stage1_options": list(stage1_options),
                  "self_build": {"mode": mode, "cflags": build_env.get("L1_CFLAGS", "")},
                  "native_compiler": {"path": str(native), "version": _version(native, build_env, root)},
                  "preparation_inputs": dict(sorted(preparation_inputs.items()))}
    if preparation_identity is not None:
        provenance["preparation_identity"] = preparation_identity
    metadata["provenance"] = provenance
    return PackageProvenance(json.dumps(metadata, sort_keys=True, allow_nan=False)), build_env
