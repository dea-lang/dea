#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code
from l0_parser import Parser


CASE_DEFAULT_RECOVERY_SRC = """module main;
func main() -> int {
    case (1) {
        else { return 0; }
        "a" => { return 1; }
        _ => 2;
        else 3;
    }
    printl_s("ok");
    return 0;
}
"""


def diag_code_count(diagnostics, code: str) -> int:
    needle = f"[{code}]"
    return sum(1 for diagnostic in diagnostics if needle in diagnostic.message)


def diag_lines(diagnostics, code: str) -> list[int]:
    needle = f"[{code}]"
    return [diagnostic.line for diagnostic in diagnostics if needle in diagnostic.message]


def test_parser_recovery_from_missing_semicolon(analyze_single):
    src = """
    module main;

    func first() -> int {
        let x: int = 1
        let y: int = ;
        return x;
    }

    func later() -> int {
        return 2;
    }
    """
    result = analyze_single("main", src)

    assert result.has_errors()
    assert result.cu is not None
    # We recovered from the missing semicolon on line 5, 
    # but bailed on line 6 (missing expression).
    assert len(result.diagnostics) >= 1
    assert has_error_code(result.diagnostics, "PAR-0100")


def test_parser_recovery_from_missing_import_semicolon(analyze_single):
    src = """
    module main;

    import std.io

    func ok() -> int {
        return 0;
    }

    func broken() -> int {
        let x: int = ;
        return x;
    }
    """
    result = analyze_single("main", src)

    assert result.has_errors()
    assert result.cu is not None
    assert len(result.diagnostics) >= 1
    assert has_error_code(result.diagnostics, "PAR-0321")


def test_stray_else_reports_par0123_without_top_level_cascade(analyze_single):
    src = """
    module main;
    func main() -> int {
        else let hello: int = 1;
        return 0;
    }
    """
    result = analyze_single("main", src)

    assert result.has_errors()
    # Orphaned `else` gets the specific diagnostic, not the generic expression error,
    # and recovery stays inside the function body (no top-level cascade).
    assert has_error_code(result.diagnostics, "PAR-0123")
    assert not has_error_code(result.diagnostics, "PAR-0225")
    assert not has_error_code(result.diagnostics, "PAR-0020")


def test_stray_cleanup_reports_par0506_without_top_level_cascade(analyze_single):
    src = """
    module main;
    func main() -> int {
        cleanup let hello: int = 1;
        return 0;
    }
    """
    result = analyze_single("main", src)

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0506")
    assert not has_error_code(result.diagnostics, "PAR-0225")
    assert not has_error_code(result.diagnostics, "PAR-0020")


def test_case_default_recovery_stays_inside_case():
    parser = Parser.from_source(CASE_DEFAULT_RECOVERY_SRC)
    parser.parse_module()

    assert has_error_code(parser.diagnostics, "PAR-0242")
    assert has_error_code(parser.diagnostics, "PAR-0234")
    assert diag_code_count(parser.diagnostics, "PAR-0236") == 2
    assert not has_error_code(parser.diagnostics, "PAR-0225")
    assert not has_error_code(parser.diagnostics, "PAR-0123")
    assert not has_error_code(parser.diagnostics, "PAR-0020")
    assert diag_lines(parser.diagnostics, "PAR-0242") == [4]
    assert diag_lines(parser.diagnostics, "PAR-0234") == [5]
    assert diag_lines(parser.diagnostics, "PAR-0236") == [6, 7]
