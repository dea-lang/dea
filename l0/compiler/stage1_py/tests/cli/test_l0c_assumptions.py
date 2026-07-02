#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import argparse
import textwrap
from types import SimpleNamespace

import l0c
from l0_driver import SourceEncodingError
from l0c import cmd_ast, cmd_build, cmd_check, cmd_codegen, cmd_run, cmd_tok


def _write_module(root, module_name: str, source: str):
    path = root.joinpath(*module_name.split(".")).with_suffix(".l0")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def _build_args(tmp_path, entry: str, **overrides):
    base = dict(
        entry=entry,
        output=str(tmp_path / "a.out"),
        c_compiler="cc",
        c_options=None,
        runtime_include=None,
        runtime_lib=None,
        keep_c=False,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=False,
        trace_memory=False,
        log=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _inspect_args(tmp_path, entry: str, **overrides):
    base = dict(
        entry=entry,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        log=False,
        all_modules=False,
        include_eof=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class _RunResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_build_fails_when_entry_main_missing(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "app.main",
        """
        module app.main;
        func helper() -> int { return 0; }
        """,
    )
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))

    rc = cmd_build(_build_args(tmp_path, "app.main"))

    assert rc == 1
    assert "[L0C-0012]" in capsys.readouterr().err


def test_build_warns_when_entry_main_return_type_is_not_preferred(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "app.main",
        """
        module app.main;
        func main() -> string { return "ok"; }
        """,
    )
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))

    rc = cmd_build(_build_args(tmp_path, "app.main"))

    assert rc == 0
    assert "[L0C-0013]" in capsys.readouterr().err


def test_build_surfaces_analysis_warning_for_duplicate_import(tmp_path, monkeypatch, capsys):
    # Oracle pin: a non-fatal analysis warning must reach stderr in `--build`
    # mode, not only in `--check`.
    _write_module(
        tmp_path,
        "dep",
        """
        module dep;
        func dep_value() -> int { return 0; }
        """,
    )
    _write_module(
        tmp_path,
        "app.main",
        """
        module app.main;
        import dep;
        import dep;
        func main() -> int { return dep_value(); }
        """,
    )
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))

    rc = cmd_build(_build_args(tmp_path, "app.main"))

    assert rc == 0
    assert "[RES-0036] duplicated 'import dep'" in capsys.readouterr().err


def test_codegen_stdout_preserves_single_trailing_newline(monkeypatch, capsys):
    class _FakeBackend:
        def __init__(self, result):
            self.result = result

        def generate(self):
            return "line1\nline2\n"

    monkeypatch.setattr("l0c._run_analysis", lambda args: (object(), object(), 0))
    monkeypatch.setattr("l0c.Backend", _FakeBackend)

    rc = cmd_codegen(argparse.Namespace(output=None))

    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "line1\nline2\n"
    assert captured.err == ""


def test_check_rejects_invalid_entry_module_name(tmp_path, capsys):
    args = argparse.Namespace(
        entry="bad-name",
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        log=False,
    )

    rc = cmd_check(args)

    assert rc == 1
    assert "[L0C-0011]" in capsys.readouterr().err


def test_build_accepts_existing_runtime_lib_directory(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    runtime_dir = tmp_path / "runtime_lib"
    runtime_dir.mkdir()
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(_build_args(tmp_path, "main", runtime_lib=str(runtime_dir)))

    assert rc == 0
    assert "-L" in captured["cmd"]
    assert str(runtime_dir) in captured["cmd"]
    assert "-ll0runtime" not in captured["cmd"]


def test_build_uses_l0_cflags_when_c_options_are_not_provided(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _RunResult(returncode=0)

    monkeypatch.setenv("L0_CFLAGS", "-g -DENV_FLAG")
    monkeypatch.delenv("L0_RUNTIME_LIB", raising=False)
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(_build_args(tmp_path, "main", c_compiler="gcc", c_options=None))

    assert rc == 0
    assert "-g" in captured["cmd"]
    assert "-DENV_FLAG" in captured["cmd"]
    assert "-Og" in captured["cmd"]
    assert "-O1" not in captured["cmd"]


def test_build_merges_l0_cflags_and_cli_c_options_with_cli_last(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _RunResult(returncode=0)

    monkeypatch.setenv("L0_CFLAGS", "-DENV_ONE -DENV_TWO")
    monkeypatch.delenv("L0_RUNTIME_LIB", raising=False)
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(_build_args(tmp_path, "main", c_compiler="gcc", c_options="-DCLI_ONE -DCLI_TWO"))

    assert rc == 0
    env_one_idx = captured["cmd"].index("-DENV_ONE")
    env_two_idx = captured["cmd"].index("-DENV_TWO")
    cli_one_idx = captured["cmd"].index("-DCLI_ONE")
    cli_two_idx = captured["cmd"].index("-DCLI_TWO")

    assert env_one_idx < cli_one_idx
    assert env_two_idx < cli_two_idx


def test_build_uses_a_exe_by_default_on_windows(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c._is_windows_host", lambda: True)
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)
    monkeypatch.delenv("L0_RUNTIME_INCLUDE", raising=False)
    monkeypatch.delenv("L0_RUNTIME_LIB", raising=False)

    rc = cmd_build(_build_args(tmp_path, "main", c_compiler="gcc", output=None))

    assert rc == 0
    c_idx = next(i for i, arg in enumerate(captured["cmd"]) if arg.endswith(".c"))
    assert captured["cmd"].index("-O0") < c_idx
    assert "a.exe" in captured["cmd"]
    assert "a.out" not in captured["cmd"]


def test_build_places_source_after_compiler_flags_for_tcc(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    runtime_lib = tmp_path / "runtime_lib"
    runtime_lib.mkdir()
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _RunResult(returncode=0)

    monkeypatch.delenv("L0_CFLAGS", raising=False)
    monkeypatch.delenv("L0_RUNTIME_INCLUDE", raising=False)
    monkeypatch.delenv("L0_RUNTIME_LIB", raising=False)
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(
        _build_args(
            tmp_path,
            "main",
            c_compiler="tcc",
            c_options="-DVALUE=1",
            runtime_include=str(tmp_path),
            runtime_lib=str(runtime_lib),
        )
    )

    assert rc == 0
    cmd = captured["cmd"]
    c_idx = next(i for i, arg in enumerate(cmd) if arg.endswith(".c"))
    assert cmd[0] == "tcc"
    assert cmd.index("-DVALUE=1") < c_idx
    assert cmd.index("-std=c99") < c_idx
    assert cmd.index("-O1") < c_idx
    assert cmd.index("-I") < c_idx
    assert cmd.index("-o") > c_idx
    assert cmd.index("-L") > c_idx


def test_build_uses_msvc_flag_forms_for_output_and_runtime_paths(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    runtime_lib = tmp_path / "runtime_lib"
    runtime_lib.mkdir()
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(
        _build_args(
            tmp_path,
            "main",
            c_compiler="cl.exe",
            runtime_include=str(tmp_path),
            runtime_lib=str(runtime_lib),
        )
    )

    assert rc == 0
    assert any(arg.startswith("/Fe:") for arg in captured["cmd"])
    assert any(arg.startswith("/I") for arg in captured["cmd"])
    assert "/link" in captured["cmd"]
    assert any(arg.startswith("/LIBPATH:") for arg in captured["cmd"])
    assert "l0runtime.lib" not in captured["cmd"]


def test_run_forwards_c_options_to_build(tmp_path, monkeypatch):
    captured = {}

    def _fake_cmd_build(args):
        captured["c_options"] = args.c_options
        return 1

    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    args = argparse.Namespace(
        entry="app.main",
        args=[],
        c_compiler="cc",
        c_options="-O2 -DDEBUG",
        runtime_include=None,
        runtime_lib=None,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=False,
        trace_memory=False,
        log=False,
    )

    rc = cmd_run(args)

    assert rc == 1
    assert captured["c_options"] == "-O2 -DDEBUG"


def test_run_forwards_trace_flags_to_build(tmp_path, monkeypatch):
    captured = {}

    def _fake_cmd_build(args):
        captured["trace_arc"] = args.trace_arc
        captured["trace_memory"] = args.trace_memory
        return 1

    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    args = argparse.Namespace(
        entry="app.main",
        args=[],
        c_compiler="cc",
        c_options=None,
        runtime_include=None,
        runtime_lib=None,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=True,
        trace_memory=True,
        log=False,
    )

    rc = cmd_run(args)

    assert rc == 1
    assert captured["trace_arc"] is True
    assert captured["trace_memory"] is True


def test_run_with_keep_c_uses_default_build_c_path_and_temp_exe(tmp_path, monkeypatch):
    captured = {}

    def _fake_cmd_build(args):
        captured["output"] = args.output
        captured["keep_c"] = args.keep_c
        captured["c_output_path"] = getattr(args, "c_output_path", None)
        return 1

    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    args = argparse.Namespace(
        entry="app.main",
        args=[],
        c_compiler="cc",
        c_options=None,
        runtime_include=None,
        runtime_lib=None,
        keep_c=True,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=False,
        trace_memory=False,
        log=False,
    )

    rc = cmd_run(args)

    assert rc == 1
    assert captured["keep_c"] is True
    assert captured["output"] != "a.out"
    assert captured["c_output_path"] == "a.c"


def test_run_uses_exe_suffix_for_temp_output_on_windows(tmp_path, monkeypatch):
    captured = {}

    def _fake_cmd_build(args):
        captured["output"] = args.output
        return 1

    monkeypatch.setattr("l0c._is_windows_host", lambda: True)
    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    args = argparse.Namespace(
        entry="app.main",
        args=[],
        c_compiler="cc",
        c_options=None,
        runtime_include=None,
        runtime_lib=None,
        keep_c=False,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=False,
        trace_memory=False,
        log=False,
    )

    rc = cmd_run(args)

    assert rc == 1
    assert captured["output"].endswith(".exe")


def test_run_with_keep_c_and_output_uses_output_stem_for_c_path(tmp_path, monkeypatch):
    captured = {}

    def _fake_cmd_build(args):
        captured["output"] = args.output
        captured["keep_c"] = args.keep_c
        captured["c_output_path"] = getattr(args, "c_output_path", None)
        return 1

    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    args = argparse.Namespace(
        entry="app.main",
        args=[],
        output="custom_name",
        c_compiler="cc",
        c_options=None,
        runtime_include=None,
        runtime_lib=None,
        keep_c=True,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=False,
        trace_memory=False,
        log=False,
    )

    rc = cmd_run(args)

    assert rc == 1
    assert captured["keep_c"] is True
    assert captured["output"] != "custom_name"
    assert captured["c_output_path"] == "custom_name.c"


def test_run_warns_when_output_is_set_without_keep_c(tmp_path, monkeypatch, capsys):
    def _fake_cmd_build(args):
        return 1

    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    args = argparse.Namespace(
        entry="app.main",
        args=[],
        output="custom_name",
        c_compiler="cc",
        c_options=None,
        runtime_include=None,
        runtime_lib=None,
        keep_c=False,
        verbosity=0,
        project_root=[str(tmp_path)],
        sys_root=[],
        no_line_directives=False,
        trace_arc=False,
        trace_memory=False,
        log=False,
    )

    rc = cmd_run(args)

    assert rc == 1
    assert "[L0C-0017]" in capsys.readouterr().err


def test_build_fails_when_no_c_compiler_is_available(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    monkeypatch.setattr("l0c._find_cc", lambda: None)

    rc = cmd_build(_build_args(tmp_path, "main", c_compiler=None))

    assert rc == 1
    assert "[L0C-0009]" in capsys.readouterr().err


def test_build_fails_when_c_compilation_fails(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=1, stderr="cc failed"))

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert "[L0C-0010]" in capsys.readouterr().err


def test_build_fails_when_runtime_lib_path_is_not_a_directory(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    missing_dir = tmp_path / "missing_runtime_dir"
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))

    rc = cmd_build(_build_args(tmp_path, "main", runtime_lib=str(missing_dir)))

    assert rc == 1
    assert "[L0C-0014]" in capsys.readouterr().err


def test_build_fails_when_entry_main_type_info_is_missing(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    orig_analyze = l0c.L0Driver.analyze

    def _analyze_without_main_type(self, entry_module_name):
        result = orig_analyze(self, entry_module_name)
        result.func_types.pop((entry_module_name, "main"), None)
        return result

    monkeypatch.setattr("l0c.L0Driver.analyze", _analyze_without_main_type)
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert "[L0C-0016]" in capsys.readouterr().err


def test_ast_reports_compilation_unit_build_error(tmp_path, monkeypatch, capsys):
    def _boom(self, _entry):
        raise RuntimeError("boom")

    monkeypatch.setattr("l0c.L0Driver.build_compilation_unit", _boom)

    rc = cmd_ast(_inspect_args(tmp_path, "main"))

    assert rc == 1
    assert "[L0C-0020]" in capsys.readouterr().err


def test_ast_reports_missing_entry_module_in_compilation_unit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "l0c.L0Driver.build_compilation_unit",
        lambda self, _entry: SimpleNamespace(modules={"other": object()}),
    )

    rc = cmd_ast(_inspect_args(tmp_path, "main"))

    assert rc == 1
    assert "[L0C-0030]" in capsys.readouterr().err


def test_tok_reports_read_error_for_entry_file(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    monkeypatch.setattr("l0c.load_source_utf8", lambda _path: (_ for _ in ()).throw(OSError("read failed")))

    rc = cmd_tok(_inspect_args(tmp_path, "main"))

    assert rc == 1
    assert "[L0C-0040]" in capsys.readouterr().err


def test_tok_reports_source_encoding_error_for_entry_file(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    monkeypatch.setattr(
        "l0c.load_source_utf8",
        lambda _path: (_ for _ in ()).throw(SourceEncodingError("main.l0", "invalid UTF-8")),
    )

    rc = cmd_tok(_inspect_args(tmp_path, "main"))

    assert rc == 1
    assert "[L0C-0041]" in capsys.readouterr().err


def test_tok_all_modules_reports_compilation_unit_build_error(tmp_path, monkeypatch, capsys):
    def _boom(self, _entry):
        raise RuntimeError("bad compilation unit")

    monkeypatch.setattr("l0c.L0Driver.build_compilation_unit", _boom)

    rc = cmd_tok(_inspect_args(tmp_path, "main", all_modules=True))

    assert rc == 1
    assert "[L0C-0050]" in capsys.readouterr().err


def test_tok_all_modules_reports_resolve_errors_per_module(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "l0c.L0Driver.build_compilation_unit",
        lambda self, _entry: SimpleNamespace(modules={"ghost": object()}),
    )

    def _missing(self, module_name):
        raise FileNotFoundError(f"missing module {module_name}")

    monkeypatch.setattr("l0c.SourceSearchPaths.resolve", _missing)

    rc = cmd_tok(_inspect_args(tmp_path, "main", all_modules=True))

    assert rc == 1
    assert "[L0C-0060]" in capsys.readouterr().err


def test_tok_single_module_reports_resolve_error(tmp_path, capsys):
    rc = cmd_tok(_inspect_args(tmp_path, "missing_module"))

    assert rc == 1
    assert "[L0C-0070]" in capsys.readouterr().err
