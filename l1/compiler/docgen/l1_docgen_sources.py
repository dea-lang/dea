# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Explicit L1 documentation inventories aligned with the native builders."""
from dataclasses import dataclass
from pathlib import Path

# build_l1c.py compiles these native implementation units.
SHARED_SUPPORT = (
    'compiler_support.c', 'preparation_support.c', 'installation.h',
    'preparation/platform.h', 'preparation/pe_imports.h',
    'preparation/storage.h', 'preparation/json.h', 'preparation/identity.h',
    'preparation/construction.h', 'preparation/sha256.h',
    'preparation/libraries.h', 'preparation/build.h',
)
RUNTIME_API = ('dea_rt.h', 'l1_real.h')


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
    files.extend(Path('compiler/shared/runtime/include') / name for name in RUNTIME_API)
    files.extend(Path('compiler/support') / name for name in SHARED_SUPPORT)
    files.append(Path('compiler/support/interface_fingerprint.c'))
    files.extend(Path('compiler/shared/runtime/internal') / name for name in
                 ('dea_interface_fingerprint.h', 'dea_siphash.h'))
    return SourceManifest(sorted(set(files)))
