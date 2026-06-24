#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code


def test_parser_control_flow_valid(analyze_single):
    src = """
    module main;

    enum Option {
        None;
        Some(value: int);
    }

    func eval(opt: Option) -> int {
        let acc: int = 0;

        while (acc < 5) {
            acc = acc + 1;
            if (acc == 3) { continue; }
            if (acc == 4) { break; }
        }

        for (let i: int = 0; i < 2; i = i + 1) {
            acc = acc + i;
        }

        if (acc > 0) {
            acc = acc + 1;
        } else {
            acc = 1;
        }

        match (opt) {
            None => { return 0; }
            Some(v) => { return v + acc; }
        }

        return acc;
    }
    """
    result = analyze_single("main", src)
    assert not result.has_errors()


def test_parser_if_missing_rparen(analyze_single):
    src = """
    module main;

    func main() -> int {
        if (true { return 1; }
        return 0;
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0122")


def test_parser_while_missing_rparen(analyze_single):
    src = """
    module main;

    func main() -> int {
        while (true { return 1; }
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0132")


def test_parser_for_missing_semicolons(analyze_single):
    src = """
    module main;

    func main() -> int {
        for (let i: int = 0 i < 3; i = i + 1) { return 0; }
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0142")

    src = """
    module main;

    func main() -> int {
        for (let i: int = 0; i < 3 i = i + 1) { return 0; }
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0143")


def test_parser_for_update_rejects_let(analyze_single):
    """A for update cannot introduce a local declaration."""
    valid = analyze_single(
        "main",
        """
        module main;
        func main() -> int {
            for (let i: int = 0; i < 3; i = i + 1) {}
            return 0;
        }
        """,
    )
    assert not valid.has_errors()

    invalid = analyze_single(
        "main",
        """
        module main;
        func main() -> int {
            for (let i: int = 0; i < 3; let j: int = i) {}
            return 0;
        }
        """,
    )
    assert invalid.has_errors()
    assert has_error_code(invalid.diagnostics, "PAR-0145")


def test_parser_match_errors(analyze_single):
    src = """
    module main;

    enum Option { None; Some(value: int); }

    func main(opt: Option) -> int {
        match (opt) {
            None { return 0; }
        }
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0174")

    src = """
    module main;

    enum Option { None; Some(value: int); }

    func main(opt: Option) -> int {
        match (opt) {
        }
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0177")

    src = """
    module main;

    enum Option { None; Some(value: int); }

    func main(opt: Option) -> int {
        match (opt) {
            None => { return 0; }
            None => { return 1; }
        }
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0176")
