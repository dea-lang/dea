# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Documentation tests must use the prepared shared Python environment."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("parallel", [False, True])
def test_docgen_prepares_environment_before_using_its_python(tmp_path, parallel):
    make = shutil.which("make")
    if make is None:
        pytest.skip("GNU Make is required")
    root = tmp_path / "checkout with spaces"
    level = root / "l1"
    (level / "tests").mkdir(parents=True)
    shutil.copyfile(ROOT / "Makefile", level / "Makefile")
    (level / "tests/test_docgen_probe.py").write_text("# selected fixture\n")
    python = Path(sys.executable).as_posix()
    # Simulate root environment setup and the test runner without downloading
    # dependencies or invoking compiler bootstrap in this Make regression.
    (root / "Makefile").write_text(f'.PHONY: venv\nvenv:\n\t"{python}" prepare.py\n')
    (root / "prepare.py").write_text(
        'from pathlib import Path\nPath("environment-ready").touch()\n')
    (level / "pytest.py").write_text('''from pathlib import Path
import sys
assert (Path(__file__).resolve().parent.parent / "environment-ready").is_file(), "environment not prepared"
assert sys.argv[1:] == ["-q", "-n", "0", "tests/test_docgen_probe.py"], sys.argv
print("prepared documentation runner passed")
''')
    env = {key: value for key, value in os.environ.items()
           if key not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "PYTHONPATH"}}
    # CI explicitly selects a host Python for tooling. It must not become the
    # pytest interpreter, even when no shared environment exists at Make startup.
    env["PYTHON"] = "missing-host-python-must-not-run"
    command = [make, "-C", str(level), "test-docgen", f"VENV_PYTHON={python}"]
    if parallel:
        command.append("-j2")
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "prepared documentation runner passed" in result.stdout
