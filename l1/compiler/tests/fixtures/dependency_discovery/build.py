#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Caller-owned discovery and locking for the example's outer Make invocation."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


def shell_words(words: list[str]) -> str:
    """Quote command arguments for the POSIX shell used by GNU Make.

    Args:
        words: Literal command arguments.

    Returns:
        Shell argument text with dollar signs escaped for Make variable expansion.
    """
    return " ".join(shlex.quote(word) for word in words).replace("$", "$$")


def make_path(value: str) -> str:
    """Escape a native fixture path expanded from a Make environment variable.

    Args:
        value: Native path in the example's documented filename subset.

    Returns:
        Make list text with spaces escaped. Comment markers stay literal because
        Make does not parse comments again after expanding these variables.
    """
    if os.name == "nt":
        value = value.replace("\\", "/")
    return value.replace(" ", "\\ ")


def strip_annotations(value: object) -> object:
    """Remove optional Dea annotations recursively from a decoded report.

    Args:
        value: Decoded JSON value.

    Returns:
        A report containing only standard scheduling fields.
    """
    if isinstance(value, dict):
        return {key: strip_annotations(item) for key, item in value.items() if not key.startswith("_dea_")}
    if isinstance(value, list):
        return [strip_annotations(item) for item in value]
    return value


def build(config_path: Path) -> int:
    """Scan, validate and schedule one project while holding its artifact lock.

    Args:
        config_path: Caller-owned JSON configuration.

    Returns:
        The scanner or inner Make exit status, or zero on success.
    """
    config = json.loads(config_path.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("p1689_make", config["adapter"])
    assert spec is not None and spec.loader is not None
    adapter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = adapter
    spec.loader.exec_module(adapter)
    root = Path(config["artifact_root"])
    fragment = root / "dependencies.mk"
    report = root / "dependencies.json"
    stamp = root / "configuration.json"
    with adapter.artifact_lock(root):
        result = subprocess.run([config["compiler"], "--scan-deps", config["entry"], "--artifact-root", str(root),
                                 *config["inputs"], "-o", str(report)], check=False)
        if result.returncode:
            return result.returncode
        if config.get("strip_annotations", False):
            report.write_text(json.dumps(strip_annotations(json.loads(report.read_text(encoding="utf-8")))),
                              encoding="utf-8")
        adapter.write_fragment(report, root, fragment)
        settings = json.dumps({key: value for key, value in config.items()
                               if key not in ("goals", "strip_annotations")}, sort_keys=True, ensure_ascii=False) + "\n"
        if not stamp.exists() or stamp.read_text(encoding="utf-8") != settings:
            stamp.write_text(settings, encoding="utf-8")
        env = dict(os.environ)
        env.update(PYTHON=sys.executable, L1C=config["compiler"], DEA_INNER="1", DEA_ENTRY=config["entry"],
                   DEA_PROJECT_DRIVER=str(Path(__file__).resolve()), DEA_FRAGMENT=make_path(str(fragment)),
                   DEA_ARTIFACT_ROOT=str(root), DEA_EXECUTABLE=make_path(config["executable"]),
                   DEA_CONFIG_STAMP=make_path(str(stamp)), DEA_ACTION_LOG=config["action_log"],
                   DEA_INPUT_FLAGS=shell_words(config["inputs"]), DEA_NATIVE_FLAGS=shell_words(config["native"]),
                   DEA_LINK_INPUT_FLAGS=shell_words(config["link_inputs"]),
                   DEA_LINK_NATIVE_FLAGS=shell_words(config.get("link_native", [])),
                   DEA_FOREIGN_FLAGS=shell_words(config.get("foreign", [])),
                   DEA_COMPILE_DEPS=" ".join(make_path(path) for path in config.get("compile_deps", [])),
                   DEA_NATIVE_LINK_DEPS=" ".join(make_path(path) for path in config.get("link_deps", [])))
        goals = [goal.replace(os.sep, "/") for goal in config.get("goals", ["all"])]
        return subprocess.run([config["make"], "--no-print-directory", "-f", str(Path(__file__).with_name("Makefile")),
                               "-j4", *goals], env=env, check=False).returncode


def main() -> int:
    """Dispatch the example's outer build and action-log commands.

    Returns:
        Zero on success, or a failing build status.
    """
    if sys.argv[1] == "record":
        with Path(sys.argv[2]).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(sys.argv[3:]) + "\n")
        return 0
    return build(Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
