#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import textwrap
from pathlib import Path

import pytest

from l0_driver import L0Driver
from l0_paths import SourceSearchPaths


def write(tmp_root: Path, rel: str, content: str) -> Path:
    path = tmp_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_module_resolves_in_project_when_no_system(tmp_path):
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    write(
        proj_root,
        "app/main.l0",
        """
        module app.main;

        func main() -> int { return 0; }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    mod = driver.load_module("app.main")

    assert mod.name == "app.main"


def test_system_root_has_priority_over_project(tmp_path):
    sys_root = tmp_path / "sys"
    proj_root = tmp_path / "project"
    sys_root.mkdir()
    proj_root.mkdir()

    # System version
    write(
        sys_root,
        "std/io.l0",
        """
        module std.io;

        func identity() -> int { return 1; }
        """,
    )

    # Project version (should be ignored for resolution)
    write(
        proj_root,
        "std/io.l0",
        """
        module std.io;

        func identity() -> int { return 2; }
        """,
    )

    paths = SourceSearchPaths(
        system_roots=[sys_root],
        project_roots=[proj_root],
    )

    driver = L0Driver(search_paths=paths)
    mod = driver.load_module("std.io")

    assert Path(mod.filename).samefile(sys_root / "std/io.l0")


def test_module_not_found_raises(tmp_path):
    paths = SourceSearchPaths()
    paths.add_project_root(tmp_path)

    driver = L0Driver(search_paths=paths)

    try:
        driver.load_module("does.not.exist")
    except FileNotFoundError as e:
        assert "does.not.exist" in str(e)
    else:
        assert False, "expected FileNotFoundError"


@pytest.mark.parametrize("group", ["system_roots", "project_roots"])
def test_resolution_skips_directories_and_returns_absolute_files(tmp_path, monkeypatch, group):
    monkeypatch.chdir(tmp_path)
    first, second = Path("first root"), Path("second root")
    (first / "thing.l0").mkdir(parents=True)
    expected = write(second, "thing.l0", "module thing;")
    paths = SourceSearchPaths(**{group: [first, second]})

    result = paths.resolve("thing")
    assert result.is_absolute()
    assert result.samefile(expected)
    expected.unlink()
    with pytest.raises(FileNotFoundError, match="thing"):
        paths.resolve("thing")
