# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Explicit L1 documentation inventories aligned with the native builders."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceManifest:
    """Sorted paths relative to the L1 source root."""

    files: list[Path]


def build_source_manifest(root: Path) -> SourceManifest:
    """Select canonical compiler, standard library, runtime, and build support.

    Args:
        root: L1 source root.

    Returns:
        Selected source paths, excluding tests and generated files.
    """
    files = [p.relative_to(root) for p in (root / 'compiler/src').rglob('*.l0')]
    files.extend(p.relative_to(root) for p in (root / 'compiler/shared/l1/stdlib').rglob('*.l1'))
    # Include implementation units and implementation headers, not only the
    # installed ABI. Doxygen can then attach source contracts to prototypes.
    for directory in ('compiler/shared/runtime', 'compiler/support'):
        for suffix in ('*.c', '*.h'):
            files.extend(p.relative_to(root) for p in (root / directory).rglob(suffix))
    return SourceManifest(sorted(set(files)))
