# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Explicit L1 documentation inventories aligned with the native builders."""
from dataclasses import dataclass
from pathlib import Path

# build_stage{1,2}_l1c.py share these native implementation units.
SHARED_SUPPORT = (
    'compiler_support.c', 'preparation_support.c',
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


def build_source_manifest(root: Path, stage: str = 'all') -> SourceManifest:
    """Select a compiler and its explicit shared reference inputs.

    Args:
        root: L1 source root.
        stage: Concrete stage or inventory union.

    Returns:
        Selected source paths, excluding tests and generated files.

    Raises:
        ValueError: Stage is invalid.
    """
    if stage not in {'stage1', 'stage2', 'all'}:
        raise ValueError(f'invalid documentation stage: {stage}')
    files = []
    for selected, directory, suffix in (
        ('stage1', 'stage1_l0', '.l0'), ('stage2', 'stage2_l1', '.l1'),
    ):
        if stage in {selected, 'all'}:
            files.extend(p.relative_to(root) for p in (root / 'compiler' / directory / 'src').rglob(f'*{suffix}'))
    files.extend(p.relative_to(root) for p in (root / 'compiler/shared/l1/stdlib').rglob('*.l1'))
    files.extend(Path('compiler/shared/runtime/include') / name for name in RUNTIME_API)
    files.extend(Path('compiler/stage1_l0/support') / name for name in SHARED_SUPPORT)
    if stage in {'stage1', 'all'}:
        files.append(Path('compiler/stage1_l0/support/interface_fingerprint.c'))
        files.extend(Path('compiler/shared/runtime/internal') / name for name in
                     ('dea_interface_fingerprint.h', 'dea_siphash.h'))
    return SourceManifest(sorted(set(files)))
