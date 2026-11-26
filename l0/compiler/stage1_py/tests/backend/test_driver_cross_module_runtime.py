#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from pathlib import Path

import pytest

from l0_backend import Backend
from l0_driver import L0Driver


def test_cross_module_execution(tmp_path, write_l0_file, search_paths, compile_and_run):
    write_l0_file(
        "util.math",
        """
        module util.math;

        func add(a: int, b: int) -> int {
            return a + b;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;

        import std.io;
        import util.math;

        func main() -> int {
            let v: int = add(20, 22);
            printl_i(v);
            return v;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("main")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert stdout.strip().splitlines()[-1] == "42"


@pytest.mark.parametrize("entry", ["forward", "reverse"])
def test_qualified_type_names(entry, tmp_path, search_paths, compile_and_run):
    """Compile and run both import orders for formerly colliding struct and enum names."""
    fixtures = Path(__file__).resolve().parents[4] / "tests/fixtures/qualified_type_names"
    search_paths.add_project_root(fixtures)
    result = L0Driver(search_paths=search_paths).analyze(entry)
    assert not result.has_errors(), result.diagnostics
    generated = Backend(result).generate()
    success, _, stderr = compile_and_run(generated, tmp_path, strict_c99=True)
    assert success, stderr
    for module in ("aaa_bbb", "7aaa_bbb"):
        assert f"struct l0_{module}_V {{" in generated
        assert f"enum l0_{module}_8Read_Out_tag {{" in generated
