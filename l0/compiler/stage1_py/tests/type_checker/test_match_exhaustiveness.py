#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from textwrap import dedent

from conftest import has_error_code
from l0_driver import L0Driver


def _analyze_single(tmp_path, name: str, src: str):
    path = tmp_path / f"{name}.l0"
    path.write_text(dedent(src))

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)

    return driver.analyze(name)


def test_missing_enum_variant_rejected(tmp_path):
    src = """
    module main;

    enum Color { Red(); Green(); Blue(); }

    func f(c: Color) -> int {
        match (c) {
            Red() => { return 1; }
            Green() => { return 2; }
        }
    }
    """

    result = _analyze_single(tmp_path, "main", src)
    assert result.has_errors()


def test_unknown_variant_name_reports_error(tmp_path):
    src = """
    module main;

    enum Flag { On(); Off(); }

    func f(f: Flag) -> int {
        match (f) {
            Maybe() => { return 1; }
        }
    }
    """

    result = _analyze_single(tmp_path, "main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0102")


def test_match_on_non_enum_type_rejected(tmp_path):
    src = """
    module main;

    func f(x: int) -> int {
        match (x) {
            _ => { return x; }
        }
    }
    """

    result = _analyze_single(tmp_path, "main", src)
    assert result.has_errors()


def test_pattern_errors_precede_arm_errors_and_exhaustiveness(tmp_path):
    """Pattern validation runs before bodies; coverage reporting runs afterward."""
    result = _analyze_single(tmp_path, "main", """
        module main;
        enum Flag { On(); Off(); }
        func check_flag(flag: Flag) {
            match (flag) {
                Maybe() => { let value = missing; }
                On() => { }
            }
        }
    """)

    assert [diag.message.split("]", 1)[0] + "]" for diag in result.diagnostics] == [
        "[TYP-0102]",
        "[TYP-0159]",
        "[TYP-0051]",
        "[TYP-0104]",
    ]
