# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Bundle source identities include shared rendering and inventory helpers."""

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("level", ["l0", "l1"])
def test_shared_generator_changes_invalidate_reference_identity(level):
    """Mutate shared helper bytes virtually without changing the checkout."""
    code = '''
from pathlib import Path
import sys
from unittest.mock import patch
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
from docs_artifacts import source_identity
args = (root, "stage2") if root.name == "l0" else (root,)
baseline = source_identity(*args)["input_digest"]
read = Path.read_bytes
for name in ("c_declarators.py", "docgen_c_contracts.py", "docgen_doxygen.py", "docgen_function_inventory.py", "docgen_progress.py", "docgen_pdf.py"):
    changed = (root.parent / "scripts" / name).resolve()
    def virtual_bytes(path):
        contents = read(path)
        return contents + b"\\n# changed generation input\\n" if path.resolve() == changed else contents
    with patch.object(Path, "read_bytes", virtual_bytes):
        assert source_identity(*args)["input_digest"] != baseline, name
assert source_identity(*args)["input_digest"] == baseline
'''
    subprocess.run([sys.executable, "-c", code, str(ROOT / level)], check=True,
                   capture_output=True, text=True)
