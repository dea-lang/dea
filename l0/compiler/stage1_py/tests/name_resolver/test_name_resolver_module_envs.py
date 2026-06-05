#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import textwrap
from pathlib import Path

from l0_backend import Backend
from l0_driver import L0Driver
from l0_name_resolver import NameResolver
from l0_paths import SourceSearchPaths


def _write(tmp_root: Path, rel: str, content: str) -> Path:
    path = tmp_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _build_cu(tmp_path: Path):
    """
    Helper to create a tiny project:

      std.io:
        func print_int(x: int) -> void

      app.math:
        struct Number { value: int; }
        func abs(x: Number) -> Number

      app.main:
        import std.io;
        import app.math;
        func main() -> int { return 0; }

    Then returns (driver, compilation_unit, resolver, envs).
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    # std.io
    _write(
        proj_root,
        "std/io.l0",
        """
        module std.io;

        func print_int(x: int) -> void {
        }
        """,
    )

    # app.math
    _write(
        proj_root,
        "app/math.l0",
        """
        module app.math;

        struct Number {
            value: int;
        }

        func abs(x: Number) -> Number {
            return x;
        }
        """,
    )

    # app.main
    _write(
        proj_root,
        "app/main.l0",
        """
        module app.main;
        import std.io;
        import app.math;

        func main() -> int {
            return 0;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    cu = driver.build_compilation_unit("app.main")

    resolver = NameResolver(cu)
    envs = resolver.resolve()
    return driver, cu, resolver, envs


def test_module_envs_for_multi_module_project(tmp_path):
    _, cu, resolver, envs = _build_cu(tmp_path)

    # We expect three modules in the compilation unit
    assert set(cu.modules.keys()) == {"std.io", "app.math", "app.main"}

    env_main = envs["app.main"]
    env_io = envs["std.io"]
    env_math = envs["app.math"]

    # std.io exports print_int
    assert set(env_io.locals.keys()) == {"print_int"}

    # app.math exports Number (struct) and abs (func)
    assert set(env_math.locals.keys()) == {"Number", "abs"}

    # app.main has local main
    assert set(env_main.locals.keys()) == {"main"}

    # app.main imported names are the union of std.io and app.math locals
    assert set(env_main.imported.keys()) == {"print_int", "Number", "abs"}

    # env_main.all is locals U imported (no conflicts here)
    assert set(env_main.all.keys()) == {"main", "print_int", "Number", "abs"}

    # No diagnostics in this scenario
    assert resolver.diagnostics == []


def test_multiple_imports_name_collision_produces_diagnostic(tmp_path):
    """
    m1 and m2 both define f; app.main imports both.

    The name 'f' should not appear in env_main.all, and a diagnostic should be emitted.
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    _write(
        proj_root,
        "m1.l0",
        """
        module m1;

        func f() -> int { return 1; }
        """,
    )

    _write(
        proj_root,
        "m2.l0",
        """
        module m2;

        func f() -> int { return 2; }
        """,
    )

    _write(
        proj_root,
        "app/main.l0",
        """
        module app.main;
        import m1;
        import m2;

        func main() -> int { return 0; }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    cu = driver.build_compilation_unit("app.main")

    resolver = NameResolver(cu)
    envs = resolver.resolve()

    env_main = envs["app.main"]

    # main is local, f is ambiguous and should not be visible in env_main.all
    assert "main" in env_main.all
    assert "f" not in env_main.all

    # There should be at least one diagnostic mentioning the collision on 'f'
    msgs = [d.message for d in resolver.diagnostics]
    assert any("symbol 'f' imported from multiple modules" in msg for msg in msgs)


def test_imported_symbol_conflicts_with_local_definition(tmp_path):
    """
    lib defines f; app.main defines its own f and imports lib.

    Local definition wins, but we still produce a diagnostic.
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    _write(
        proj_root,
        "lib.l0",
        """
        module lib;

        func f() -> int { return 1; }
        """,
    )

    _write(
        proj_root,
        "app/main.l0",
        """
        module app.main;
        import lib;

        func f() -> int { return 2; }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    cu = driver.build_compilation_unit("app.main")

    resolver = NameResolver(cu)
    envs = resolver.resolve()

    env_main = envs["app.main"]

    # 'f' should resolve to the local symbol (not removed from all)
    assert "f" in env_main.locals
    assert "f" in env_main.all
    assert env_main.all["f"].module.name == "app.main"

    # There should be a diagnostic complaining about the conflict (and it should be an error)
    msgs = [d.message for d in resolver.diagnostics]
    assert any("RES-0021" in msg for msg in msgs)
    kinds = {d.kind for d in resolver.diagnostics}
    assert kinds == {"warning"}


def test_local_and_imported_extern_with_same_signature_is_only_warning(tmp_path):
    """
    module1 and test1 both declare the same extern func provide_int() -> int.

    Local definition in test1 should win; no hard error should be produced.
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    # module1 provides an extern declaration
    _write(
        proj_root,
        "module1.l0",
        """
        module module1;

        extern func provide_int() -> int;

        func f1() -> int {
            let v: int = provide_int();
            return v;
        }
        """,
    )

    # test1 re-declares the same extern and imports module1
    _write(
        proj_root,
        "test1.l0",
        """
        module test1;

        import module1;

        extern func provide_int() -> int;

        func f0() -> int {
            let v: int = provide_int();
            return v;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    cu = driver.build_compilation_unit("test1")

    resolver = NameResolver(cu)
    envs = resolver.resolve()

    env_test1 = envs["test1"]

    # Local extern wins and is visible in all
    assert "provide_int" in env_test1.locals
    assert "provide_int" in env_test1.all
    assert env_test1.all["provide_int"].module.name == "test1"

    # No "conflicts with local definition" error should be reported
    msgs = [d.message for d in resolver.diagnostics]
    assert not any("conflicts with local definition" in msg for msg in msgs)

    # Instead, we expect at most a warning about being shadowed by the local extern
    # (depending on implementation it may also be completely silent, so this is a
    # soft assertion: if diagnostics exist, they should be warnings with the
    # appropriate message).
    if resolver.diagnostics:
        kinds = {d.kind for d in resolver.diagnostics}
        assert kinds == {"warning"}
        assert any("RES-0020" in msg for msg in msgs)


def test_local_and_imported_extern_with_different_signature_is_error(tmp_path):
    """
    lib and app.main both declare extern f, but with different signatures.

    Local definition still wins for resolution, but a hard error should be produced.
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    # lib provides an extern with one signature
    _write(
        proj_root,
        "lib.l0",
        """
        module lib;

        extern func f() -> int;
        """,
    )

    # app.main provides a different extern signature for f and imports lib
    _write(
        proj_root,
        "app/main.l0",
        """
        module app.main;
        import lib;

        extern func f(x: int) -> int;

        func main() -> int {
            return f(42);
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    cu = driver.build_compilation_unit("app.main")

    resolver = NameResolver(cu)
    envs = resolver.resolve()

    env_main = envs["app.main"]

    # Local extern wins for resolution
    assert "f" in env_main.locals
    assert "f" in env_main.all
    assert env_main.all["f"].module.name == "app.main"

    # A conflict diagnostic should be reported (as a warning; local wins)
    assert resolver.diagnostics
    msgs = [d.message for d in resolver.diagnostics]
    assert any("RES-0021" in msg for msg in msgs)
    kinds = {d.kind for d in resolver.diagnostics}
    assert kinds == {"warning"}


def test_qualified_enum_variant_runtime_survives_import_shadow_warning(tmp_path, compile_and_run):
    """
    Imported variants shadowed by a local enum should still resolve when referenced via qualification.
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    _write(
        proj_root,
        "uno.l0",
        """
        module uno;

        enum Color {
            Red;
        }
        """,
    )

    _write(
        proj_root,
        "due.l0",
        """
        module due;

        enum Shape {
            Red;
        }
        """,
    )

    _write(
        proj_root,
        "tre.l0",
        """
        module tre;

        import uno;
        import due;

        enum MyColor {
            Zero;
            Red;
        }

        func f(c: uno::Color) -> int {
            match (c) {
                uno::Red => {
                    return ord(Red);
                }
            }
        }

        func main() -> int {
            let c: uno::Color = uno::Red;
            if (f(c) == 1) {
                return 0;
            }
            return 1;
        }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    result = driver.analyze("tre")

    assert not result.has_errors(), [d.message for d in result.diagnostics]
    warnings = [d for d in result.diagnostics if d.kind == "warning"]
    assert len(warnings) == 2
    assert any("RES-0021" in d.message and "uno::Red" in d.message for d in warnings)
    assert any("RES-0021" in d.message and "due::Red" in d.message for d in warnings)

    c_code = Backend(result).generate()
    success, _stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr


def test_duplicate_open_import_warns_once_without_ambiguity(tmp_path, compile_and_run):
    """
    Importing the same module twice is redundant, not ambiguous.

    A single RES-0036 warning is emitted, no RES-0022 ambiguity flood appears,
    and symbols from the duplicated module remain usable.
    """
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    _write(
        proj_root,
        "helper.l0",
        """
        module helper;

        func foo() -> int { return 1; }
        """,
    )

    _write(
        proj_root,
        "main.l0",
        """
        module main;
        import helper;
        import helper;

        func main() -> int { return foo() - 1; }
        """,
    )

    paths = SourceSearchPaths()
    paths.add_project_root(proj_root)

    driver = L0Driver(search_paths=paths)
    result = driver.analyze("main")

    assert not result.has_errors(), [d.message for d in result.diagnostics]

    res_0036 = [d for d in result.diagnostics if "RES-0036" in d.message]
    assert len(res_0036) == 1
    assert res_0036[0].kind == "warning"
    assert "duplicated 'import helper'" in res_0036[0].message
    # The warning points at the redundant (second) import line, not the module.
    assert (res_0036[0].line, res_0036[0].column) == (4, 1)

    # The duplicate must not be misreported as cross-module ambiguity.
    assert not any("RES-0022" in d.message for d in result.diagnostics)

    # foo stays resolvable through the (de-duplicated) import.
    c_code = Backend(result).generate()
    success, _stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
