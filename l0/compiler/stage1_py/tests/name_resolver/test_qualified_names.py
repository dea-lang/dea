#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code
from l0_driver import L0Driver
from l0_paths import SourceSearchPaths


def test_qualified_expr_resolves_imported_symbol(write_l0_file, temp_project):
    write_l0_file(
        "util.mod",
        """
        module util.mod;

        func value() -> int { return 42; }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import util.mod;

        func get() -> int {
            return util.mod::value();
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()


def test_qualified_type_and_constructor(write_l0_file, temp_project):
    write_l0_file(
        "shapes",
        """
        module shapes;

        struct Point {
            x: int;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import shapes;

        func make() -> shapes::Point {
            return shapes::Point(1);
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()


def test_qualified_variant_pattern_with_current_module_name(write_l0_file, temp_project):
    write_l0_file(
        "colors",
        """
        module colors;

        enum Color {
            Red;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        
        import colors;

        enum LocalColor {
            Red;
        }

        func f(c: LocalColor) -> int {
            match (c) {
                main::Red => {
                    return 1;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()


def test_qualified_expr_requires_import(write_l0_file, temp_project):
    write_l0_file(
        "main",
        """
        module main;

        func f() -> int {
            return missing.mod::value();
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0189")
    assert any("not imported" in diag.message for diag in result.diagnostics)


def test_qualified_type_requires_import(write_l0_file, temp_project):
    write_l0_file(
        "main",
        """
        module main;

        func f(x: missing.mod::Thing) -> int { return 0; }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "SIG-0019")


def test_qualified_variant_pattern(write_l0_file, temp_project):
    write_l0_file(
        "colors",
        """
        module colors;

        enum Color {
            Red;
            Blue;
        }

        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import colors;

        func f(c: colors::Color) -> int {
            match (c) {
                colors::Red => {
                    return 1;
                }
                colors::Blue => {
                    return 2;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()


def test_qualified_variant_pattern_requires_import(write_l0_file, temp_project):
    write_l0_file(
        "colors",
        """
        module colors;

        enum Color {
            Red;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;

        enum LocalColor {
            Red;
        }

        func f(c: LocalColor) -> int {
            match (c) {
                colors::Red => {
                    return 1;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0102")
    assert any("not imported" in diag.message for diag in result.diagnostics)


def test_qualified_variant_pattern_wrong_module(write_l0_file, temp_project):
    write_l0_file(
        "colors",
        """
        module colors;

        enum Color {
            Red;
        }
        """,
    )

    write_l0_file(
        "shapes",
        """
        module shapes;

        enum Color {
            Red;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import colors;
        import shapes;

        func f(c: colors::Color) -> int {
            match (c) {
                shapes::Red => {
                    return 1;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0102")
    assert has_error_code(result.diagnostics, "TYP-0104")


def test_wrong_enum_variant_does_not_complete_match_coverage(write_l0_file, temp_project):
    write_l0_file(
        "main",
        """
        module main;

        enum Color {
            Red;
            Blue;
        }

        enum Shape {
            Circle;
        }

        func f(c: Color) -> int {
            match (c) {
                Red => { return 1; }
                Circle => { return 2; }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0102")
    assert has_error_code(result.diagnostics, "TYP-0104")


def test_invalid_variant_does_not_make_wildcard_unreachable(write_l0_file, temp_project):
    write_l0_file(
        "main",
        """
        module main;

        enum Color {
            Red;
            Blue;
        }

        enum PayloadColor {
            Loaded(value: int);
            Empty;
        }

        func f(c: Color) -> int {
            match (c) {
                Red => { return 1; }
                Missing => { return 2; }
                _ => { return 3; }
            }
        }

        func wildcard_first(c: Color) -> int {
            match (c) {
                _ => { return 1; }
                Red => { return 2; }
                Blue => { return 3; }
            }
        }

        func explicit_exhaustive(c: Color) -> int {
            match (c) {
                Red => { return 1; }
                Blue => { return 2; }
            }
        }

        func invalid_arity(c: PayloadColor) -> int {
            match (c) {
                Loaded(value, extra) => { return value; }
                Empty => { return 0; }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0102")
    assert has_error_code(result.diagnostics, "TYP-0101")
    assert has_error_code(result.diagnostics, "TYP-0104")
    assert has_error_code(result.diagnostics, "TYP-0159")
    assert not has_error_code(result.diagnostics, "TYP-0105")


def test_unqualified_variant_conflict_is_error(write_l0_file, temp_project):
    write_l0_file(
        "colors",
        """
        module colors;

        enum Color {
            Red;
        }
        """,
    )

    write_l0_file(
        "shapes",
        """
        module shapes;

        enum Shape {
            Red;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import colors;
        import shapes;

        func f(c: colors::Color) -> int {
            match (c) {
                Red => {
                    return 1;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    # Match variant patterns resolve against the scrutinee's enum type, not
    # module env, so Red is found in colors::Color and the match succeeds.
    # RES-0022 is a warning (ambiguous import), not an error.
    assert not result.has_errors()
    assert has_error_code(result.diagnostics, "RES-0022")


def test_qualified_variant_disambiguates_conflict(write_l0_file, temp_project):
    write_l0_file(
        "colors",
        """
        module colors;

        enum Color {
            Red;
        }
        """,
    )

    write_l0_file(
        "shapes",
        """
        module shapes;

        enum Shape {
            Red;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import colors;
        import shapes;

        func f(c: colors::Color) -> int {
            match (c) {
                colors::Red => {
                    return 1;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()


def test_ambiguous_identifier_error_message(write_l0_file, temp_project):
    """Bare use of an ambiguous symbol gives 'ambiguous' diagnostic with module names."""
    write_l0_file(
        "uno",
        """
        module uno;

        enum UColor { Red; }
        """,
    )

    write_l0_file(
        "due",
        """
        module due;

        enum DColor { Red; }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import uno;
        import due;

        func f() -> int {
            let x: int = 0;
            if (Red == Red) { x = 1; }
            return x;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    typ_0155_diags = [d for d in result.diagnostics if "TYP-0155" in d.message]
    assert len(typ_0155_diags) > 0
    assert any("ambiguous" in d.message for d in typ_0155_diags)
    assert any("uno" in d.message and "due" in d.message for d in typ_0155_diags)


def test_ambiguous_call_identifier(write_l0_file, temp_project):
    """Call syntax with an ambiguous symbol gives 'ambiguous' diagnostic."""
    write_l0_file(
        "uno",
        """
        module uno;

        enum UColor { Red(value: int); }
        """,
    )

    write_l0_file(
        "due",
        """
        module due;

        enum DColor { Red(value: int); }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import uno;
        import due;

        func f() -> int {
            let x = Red(1);
            return 0;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    typ_0189_diags = [d for d in result.diagnostics if "TYP-0189" in d.message]
    assert len(typ_0189_diags) > 0
    assert any("ambiguous" in d.message for d in typ_0189_diags)
    assert any("uno" in d.message and "due" in d.message for d in typ_0189_diags)


def test_local_shadows_ambiguous_import(write_l0_file, temp_project):
    """`let Red = 33` with ambiguous `Red` emits TYP-0024 warning."""
    write_l0_file(
        "uno",
        """
        module uno;

        enum UColor { Red; }
        """,
    )

    write_l0_file(
        "due",
        """
        module due;

        enum DColor { Red; }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import uno;
        import due;

        func f() -> int {
            let Red = 33;
            return Red;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    # Should not have errors (the local shadows the ambiguous name)
    assert not result.has_errors()
    # Should have TYP-0024 warning
    assert has_error_code(result.diagnostics, "TYP-0024")
    typ_0024_diags = [d for d in result.diagnostics if "TYP-0024" in d.message]
    assert any("ambiguous" in d.message for d in typ_0024_diags)


def test_three_modules_ambiguous(write_l0_file, temp_project):
    """Three modules export `Red`; all three mentioned in diagnostic."""
    write_l0_file(
        "uno",
        """
        module uno;

        enum UColor { Red; }
        """,
    )

    write_l0_file(
        "due",
        """
        module due;

        enum DColor { Red; }
        """,
    )

    write_l0_file(
        "tre",
        """
        module tre;

        enum TColor { Red; }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import uno;
        import due;
        import tre;

        func f() -> int {
            let x: int = 0;
            if (Red == Red) { x = 1; }
            return x;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    typ_0155_diags = [d for d in result.diagnostics if "TYP-0155" in d.message]
    assert len(typ_0155_diags) > 0
    assert any("ambiguous" in d.message for d in typ_0155_diags)
    assert any("uno" in d.message and "due" in d.message and "tre" in d.message for d in typ_0155_diags)


def test_local_shadows_imported_struct(write_l0_file, temp_project):
    """`let Point = 5` with imported struct `Point` emits TYP-0025 warning."""
    write_l0_file(
        "shapes",
        """
        module shapes;

        struct Point { x: int; }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import shapes;

        func f() -> int {
            let Point = 5;
            return Point;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0025")
    typ_0025_diags = [d for d in result.diagnostics if "TYP-0025" in d.message]
    assert any("shadows" in d.message and "struct" in d.message for d in typ_0025_diags)


# --- overqualified name tests ---


def test_overqualified_name_in_expression(write_l0_file, temp_project):
    """color::Color::Red in expression position emits TYP-0158."""
    write_l0_file(
        "color",
        """
        module color;

        enum Color {
            Red;
            Blue;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import color;

        func f() -> int {
            let c = color::Color::Red;
            return 0;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0158")
    diags_0158 = [d for d in result.diagnostics if "TYP-0158" in d.message]
    assert any(
        "nested symbol path 'color::Color::Red': paths must have the form 'module::symbol' "
        "(did you mean 'color::Red'?)" in d.message
        for d in diags_0158
    )


def test_overqualified_name_in_type(write_l0_file, temp_project):
    """color::Color::Red used as a type emits SIG-0018."""
    write_l0_file(
        "color",
        """
        module color;

        enum Color {
            Red;
            Blue;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import color;

        func f(x: color::Color::Red) -> int { return 0; }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "SIG-0018")
    diags_0018 = [d for d in result.diagnostics if "SIG-0018" in d.message]
    assert any(
        "nested symbol path 'color::Color::Red': paths must have the form 'module::symbol' "
        "(did you mean 'color::Red'?)" in d.message
        for d in diags_0018
    )


def test_overqualified_name_in_pattern(write_l0_file, temp_project):
    """color::Color::Red in match pattern emits TYP-0158."""
    write_l0_file(
        "color",
        """
        module color;

        enum Color {
            Red;
            Blue;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import color;

        func f(c: color::Color) -> int {
            match (c) {
                color::Color::Red => {
                    return 1;
                }
                color::Color::Blue => {
                    return 2;
                }
            }
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0158")
    assert has_error_code(result.diagnostics, "TYP-0104")
    diags_0158 = [d for d in result.diagnostics if "TYP-0158" in d.message]
    assert any(
        "nested symbol path 'color::Color::Red': paths must have the form 'module::symbol' "
        "(did you mean 'color::Red'?)" in d.message
        for d in diags_0158
    )


def test_triple_qualified_name(write_l0_file, temp_project):
    """a::B::C::D emits TYP-0158 with all segments mentioned."""
    write_l0_file(
        "a",
        """
        module a;

        enum B {
            D;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import a;

        func f() -> int {
            let x = a::B::C::D;
            return 0;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0158")
    diags_0158 = [d for d in result.diagnostics if "TYP-0158" in d.message]
    assert any(
        "nested symbol path 'a::B::C::D': paths must have the form 'module::symbol' "
        "(did you mean 'a::D'?)" in d.message
        for d in diags_0158
    )


def test_single_qualified_still_works(write_l0_file, temp_project):
    """color::Red (no overqualification) still works without errors."""
    write_l0_file(
        "color",
        """
        module color;

        enum Color {
            Red;
            Blue;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import color;

        func f() -> int {
            let c: color::Color = color::Red;
            return 0;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    driver = L0Driver(search_paths=paths)

    result = driver.analyze("main")
    assert not result.has_errors()
