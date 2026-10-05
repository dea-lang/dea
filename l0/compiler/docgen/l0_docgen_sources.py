# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Inventory documentation inputs without importing rendering dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceManifest:
    """Manifest of sources included in API documentation."""

    files: list[Path]


def build_source_manifest(root: Path, stage: str = "all") -> SourceManifest:
    """Return the exact source inventory for one stage or the inventory union.

    Args:
        root: L0 source root.
        stage: Stage 1, Stage 2, or all source inventories.

    Returns:
        Sorted source paths relative to the L0 root.

    Raises:
        ValueError: The stage selection is invalid.
    """
    files: list[Path] = []

    if stage not in {"stage1", "stage2", "all"}:
        raise ValueError(f"invalid documentation stage: {stage}")
    if stage in {"stage1", "all"}:
        for path in sorted((root / "compiler/stage1_py").rglob("*.py")):
            rel = path.relative_to(root)
            if "tests" not in rel.parts and "__pycache__" not in rel.parts:
                files.append(rel)
    if stage in {"stage2", "all"}:
        files.extend(path.relative_to(root) for path in sorted((root / "compiler/stage2_l0/src").rglob("*.l0")))
        # The trace checker is the explicitly selected Stage 2 support tool.
        files.append(Path("compiler/stage2_l0/scripts/check_trace_log.py"))
    files.extend(path.relative_to(root) for path in sorted((root / "compiler/shared/l0/stdlib").rglob("*.l0")))
    # Keep this inventory aligned with the runtime copied by dist_tools_lib.
    files.extend(Path("compiler/shared/runtime") / name for name in ("dea_rt.h", "dea_siphash.h", "l0_runtime.h"))

    return SourceManifest(files=sorted(set(files)))
