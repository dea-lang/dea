#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import argparse
import os
import re
import stat
import textwrap
from pathlib import Path
from types import SimpleNamespace

import l0c
import pytest
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


def _assert_plain_diagnostic_output(default_stderr: str, rich_stderr: str) -> None:
    """Assert that a diagnostic bypasses logger fallback and rich formatting."""
    assert rich_stderr == default_stderr
    assert "No context provided for logging." not in rich_stderr
    assert "[ERROR]" not in rich_stderr
    assert "[WARNING]" not in rich_stderr
    assert not re.search(
        r"(?m)^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} "
        r"\[(?:ERROR|WARNING|INFO|DEBUG)\] ",
        rich_stderr,
    )


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


def test_build_main_return_warning_is_not_decorated_by_log(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "app.main",
        """
        module app.main;
        func main() -> string { return "ok"; }
        """,
    )
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))

    default_rc = cmd_build(_build_args(tmp_path, "app.main"))
    default = capsys.readouterr()
    rich_rc = cmd_build(_build_args(tmp_path, "app.main", log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (0, 0)
    assert default.out == rich.out == ""
    assert default.err == (
        "warning: [L0C-0013] entry 'main' returns 'string' "
        "(preferred: void/int/bool); generated C entry wrapper will ignore the return value\n"
    )
    _assert_plain_diagnostic_output(default.err, rich.err)


def test_build_structured_duplicate_import_warning_is_not_decorated_by_log(tmp_path, monkeypatch, capsys):
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

    default_rc = cmd_build(_build_args(tmp_path, "app.main"))
    default = capsys.readouterr()
    rich_rc = cmd_build(_build_args(tmp_path, "app.main", log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (0, 0)
    assert default.out == rich.out == ""
    _assert_plain_diagnostic_output(default.err, rich.err)
    lines = default.err.splitlines()
    assert len(lines) == 3
    assert "warning: [RES-0036] duplicated 'import dep'" in lines[0]
    assert " | import dep;" in lines[1]
    assert "^" in lines[2]


def test_build_rich_info_logs_remain_logger_controlled(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    monkeypatch.setattr("l0c.subprocess.run", lambda *args, **kwargs: _RunResult(returncode=0))
    monkeypatch.setattr("l0_logger.time.strftime", lambda *_args: "2042-01-02 03:04:05")

    rc = cmd_build(_build_args(tmp_path, "main", log=True, verbosity=1))

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "2042-01-02 03:04:05 [INFO] Generated C code:" in captured.err
    assert "2042-01-02 03:04:05 [INFO] Using C compiler: cc" in captured.err
    assert "2042-01-02 03:04:05 [INFO] Built executable:" in captured.err


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


def test_check_structured_error_is_not_decorated_by_log(tmp_path, capsys):
    _write_module(tmp_path, "main", "module main; +;")

    default_rc = cmd_check(_inspect_args(tmp_path, "main"))
    default = capsys.readouterr()
    rich_rc = cmd_check(_inspect_args(tmp_path, "main", log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (1, 1)
    assert default.out == rich.out == ""
    _assert_plain_diagnostic_output(default.err, rich.err)
    lines = default.err.splitlines()
    assert len(lines) == 3
    assert "error: [PAR-0020]" in lines[0]
    assert " | module main; +;" in lines[1]
    assert "^" in lines[2]


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


def test_build_writes_anonymous_c_through_reserved_descriptor_and_cleans_it(
    tmp_path, monkeypatch
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    trusted_temp = tmp_path / "compiler-temp"
    trusted_temp.mkdir(mode=0o700)
    selected_temp = trusted_temp
    if os.name != "nt":
        selected_temp = tmp_path / "compiler-temp-alias"
        selected_temp.symlink_to(trusted_temp, target_is_directory=True)

    captured = {}
    real_mkstemp = l0c.tempfile.mkstemp
    real_fdopen = l0c.os.fdopen

    def _tracked_mkstemp(*args, **kwargs):
        captured["mkstemp_dir"] = kwargs.get("dir")
        descriptor, raw_path = real_mkstemp(*args, **kwargs)
        captured["descriptor"] = descriptor
        captured["c_path"] = Path(raw_path)
        if os.name != "nt":
            captured["mode"] = stat.S_IMODE(os.fstat(descriptor).st_mode)
        return descriptor, raw_path

    def _tracked_fdopen(descriptor, *args, **kwargs):
        captured["fdopen_descriptor"] = descriptor
        captured["encoding"] = kwargs.get("encoding")
        return real_fdopen(descriptor, *args, **kwargs)

    def _fake_run(cmd, *args, **kwargs):
        c_path = Path(next(arg for arg in cmd if arg.endswith(".c")))
        captured["compiler_c_path"] = c_path
        captured["c_source"] = c_path.read_text(encoding="utf-8")
        return _RunResult(returncode=0)

    monkeypatch.setattr(
        "l0c.tempfile.gettempdir", lambda: str(selected_temp)
    )
    monkeypatch.setattr("l0c.tempfile.mkstemp", _tracked_mkstemp)
    monkeypatch.setattr("l0c.os.fdopen", _tracked_fdopen)
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 0
    assert captured["mkstemp_dir"] == str(trusted_temp.resolve())
    assert captured["fdopen_descriptor"] == captured["descriptor"]
    assert captured["encoding"] == "utf-8"
    assert captured["compiler_c_path"] == captured["c_path"]
    assert "int main" in captured["c_source"]
    if os.name != "nt":
        assert captured["mode"] == 0o600
    assert not captured["c_path"].exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode trust rules only")
def test_build_accepts_sticky_writable_temporary_directory(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    sticky_temp = tmp_path / "sticky-temp"
    sticky_temp.mkdir()
    sticky_temp.chmod(0o1777)
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["c_path"] = Path(next(arg for arg in cmd if arg.endswith(".c")))
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(sticky_temp))
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 0
    assert captured["c_path"].parent == sticky_temp.resolve()
    assert not captured["c_path"].exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode trust rules only")
def test_build_rejects_nonsticky_writable_temporary_directory(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    unsafe_temp = tmp_path / "unsafe-temp"
    unsafe_temp.mkdir()
    unsafe_temp.chmod(0o777)
    compiler_invoked = False

    def _unexpected_run(*args, **kwargs):
        nonlocal compiler_invoked
        compiler_invoked = True
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(unsafe_temp))
    monkeypatch.setattr("l0c.subprocess.run", _unexpected_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not compiler_invoked
    assert (
        capsys.readouterr().err
        == "error: [L0C-9511] cannot write compiler temporary source\n"
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode trust rules only")
def test_build_rejects_nonsticky_writable_temporary_ancestor(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    unsafe_ancestor = tmp_path / "unsafe-ancestor"
    unsafe_ancestor.mkdir()
    unsafe_ancestor.chmod(0o777)
    nested_temp = unsafe_ancestor / "nested-temp"
    nested_temp.mkdir(mode=0o700)
    compiler_invoked = False

    def _unexpected_run(*args, **kwargs):
        nonlocal compiler_invoked
        compiler_invoked = True
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(nested_temp))
    monkeypatch.setattr("l0c.subprocess.run", _unexpected_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not compiler_invoked
    assert (
        capsys.readouterr().err
        == "error: [L0C-9511] cannot write compiler temporary source\n"
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership trust rules only")
def test_build_rejects_temporary_directory_owned_by_untrusted_uid(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    compiler_temp = tmp_path / "compiler-temp"
    compiler_temp.mkdir(mode=0o700)
    resolved_temp = compiler_temp.resolve()
    real_path_stat = Path.stat
    untrusted_uid = 1 if os.geteuid() != 1 else 2
    compiler_invoked = False

    def _stat_with_untrusted_temp_owner(path, *args, **kwargs):
        result = real_path_stat(path, *args, **kwargs)
        if path == resolved_temp:
            return SimpleNamespace(
                st_mode=result.st_mode,
                st_uid=untrusted_uid,
            )
        return result

    def _unexpected_run(*args, **kwargs):
        nonlocal compiler_invoked
        compiler_invoked = True
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(compiler_temp))
    monkeypatch.setattr(Path, "stat", _stat_with_untrusted_temp_owner)
    monkeypatch.setattr("l0c.subprocess.run", _unexpected_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not compiler_invoked
    assert (
        capsys.readouterr().err
        == "error: [L0C-9511] cannot write compiler temporary source\n"
    )


def test_build_cleans_anonymous_c_after_compiler_failure(tmp_path, monkeypatch):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    captured = {}
    real_mkstemp = l0c.tempfile.mkstemp

    def _tracked_mkstemp(*args, **kwargs):
        kwargs["dir"] = tmp_path
        descriptor, raw_path = real_mkstemp(*args, **kwargs)
        captured["c_path"] = Path(raw_path)
        return descriptor, raw_path

    monkeypatch.setattr("l0c.tempfile.mkstemp", _tracked_mkstemp)
    monkeypatch.setattr(
        "l0c.subprocess.run",
        lambda *args, **kwargs: _RunResult(returncode=1, stderr="compiler failure"),
    )

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not captured["c_path"].exists()


def test_build_cleanup_failure_after_compiler_success_retains_executable(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    compiler_temp = tmp_path / "compiler-temp"
    compiler_temp.mkdir(mode=0o700)
    exe_path = tmp_path / "a.out"
    captured = {}
    real_unlink = Path.unlink

    def _fake_run(cmd, *args, **kwargs):
        captured["c_path"] = Path(next(arg for arg in cmd if arg.endswith(".c")))
        exe_path.write_text("executable", encoding="utf-8")
        return _RunResult(returncode=0)

    def _cleanup_failure(path, *args, **kwargs):
        if path.suffix == ".c" and path.parent == compiler_temp:
            raise OSError("cannot remove generated C")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(compiler_temp))
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)
    monkeypatch.setattr(Path, "unlink", _cleanup_failure)

    rc = cmd_build(_build_args(tmp_path, "main", output=str(exe_path)))

    assert rc == 1
    assert exe_path.read_text(encoding="utf-8") == "executable"
    assert captured["c_path"].exists()
    assert capsys.readouterr().err == (
        "error: [L0C-9512] cannot remove compiler temporary source; "
        f"retained at '{captured['c_path']}'\n"
    )
    os.unlink(captured["c_path"])


def test_build_cleanup_failure_after_compiler_failure_reports_retained_path(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    compiler_temp = tmp_path / "compiler-temp"
    compiler_temp.mkdir(mode=0o700)
    captured = {}
    real_unlink = Path.unlink

    def _fake_run(cmd, *args, **kwargs):
        captured["c_path"] = Path(next(arg for arg in cmd if arg.endswith(".c")))
        return _RunResult(returncode=1, stderr="compiler failure")

    def _cleanup_failure(path, *args, **kwargs):
        if path.suffix == ".c" and path.parent == compiler_temp:
            raise OSError("cannot remove generated C")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(compiler_temp))
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)
    monkeypatch.setattr(Path, "unlink", _cleanup_failure)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert captured["c_path"].exists()
    stderr = capsys.readouterr().err
    assert "error: [L0C-0010] C compilation failed:\n" in stderr
    assert (
        "error: [L0C-9512] cannot remove compiler temporary source; "
        f"retained at '{captured['c_path']}'\n"
    ) in stderr
    os.unlink(captured["c_path"])


def test_build_temporary_source_creation_failure_reports_9511(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    compiler_invoked = False

    def _creation_failure(*args, **kwargs):
        raise OSError("temporary directory unavailable")

    def _unexpected_run(*args, **kwargs):
        nonlocal compiler_invoked
        compiler_invoked = True
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.tempfile.mkstemp", _creation_failure)
    monkeypatch.setattr("l0c.subprocess.run", _unexpected_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not compiler_invoked
    assert (
        capsys.readouterr().err
        == "error: [L0C-9511] cannot write compiler temporary source\n"
    )


def test_build_write_and_cleanup_failures_report_9511_and_9512(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    compiler_temp = tmp_path / "compiler-temp"
    compiler_temp.mkdir(mode=0o700)
    captured = {}
    real_mkstemp = l0c.tempfile.mkstemp
    real_unlink = Path.unlink
    compiler_invoked = False

    def _tracked_mkstemp(*args, **kwargs):
        descriptor, raw_path = real_mkstemp(*args, **kwargs)
        captured["descriptor"] = descriptor
        captured["c_path"] = Path(raw_path)
        return descriptor, raw_path

    def _write_failure(*args, **kwargs):
        raise OSError("cannot open descriptor stream")

    def _cleanup_failure(path, *args, **kwargs):
        if path == captured.get("c_path"):
            raise OSError("cannot remove generated C")
        return real_unlink(path, *args, **kwargs)

    def _unexpected_run(*args, **kwargs):
        nonlocal compiler_invoked
        compiler_invoked = True
        return _RunResult(returncode=0)

    monkeypatch.setattr("l0c.tempfile.gettempdir", lambda: str(compiler_temp))
    monkeypatch.setattr("l0c.tempfile.mkstemp", _tracked_mkstemp)
    monkeypatch.setattr("l0c.os.fdopen", _write_failure)
    monkeypatch.setattr("l0c.subprocess.run", _unexpected_run)
    monkeypatch.setattr(Path, "unlink", _cleanup_failure)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not compiler_invoked
    assert captured["c_path"].exists()
    with pytest.raises(OSError):
        os.fstat(captured["descriptor"])
    assert capsys.readouterr().err == (
        "error: [L0C-9511] cannot write compiler temporary source\n"
        "error: [L0C-9512] cannot remove compiler temporary source; "
        f"retained at '{captured['c_path']}'\n"
    )
    os.unlink(captured["c_path"])


def test_build_temporary_source_write_failure_closes_and_removes_file(
    tmp_path, monkeypatch, capsys
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    captured = {}
    real_mkstemp = l0c.tempfile.mkstemp

    def _tracked_mkstemp(*args, **kwargs):
        kwargs["dir"] = tmp_path
        descriptor, raw_path = real_mkstemp(*args, **kwargs)
        captured["descriptor"] = descriptor
        captured["c_path"] = Path(raw_path)
        return descriptor, raw_path

    def _write_failure(*args, **kwargs):
        raise OSError("cannot open descriptor stream")

    monkeypatch.setattr("l0c.tempfile.mkstemp", _tracked_mkstemp)
    monkeypatch.setattr("l0c.os.fdopen", _write_failure)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 1
    assert not captured["c_path"].exists()
    with pytest.raises(OSError):
        os.fstat(captured["descriptor"])
    assert (
        capsys.readouterr().err
        == "error: [L0C-9511] cannot write compiler temporary source\n"
    )


def test_build_rejects_dangling_symlink_temporary_name_collision(
    tmp_path, monkeypatch
):
    if os.name == "nt":
        pytest.skip("controlled symlink collision requires POSIX symlink semantics")

    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    victim = tmp_path / "victim.c"
    collision_name = "collision"
    reserved_name = "reserved"
    collision_path = tmp_path / (
        f"{l0c.tempfile.gettempprefix()}{collision_name}.c"
    )
    collision_path.symlink_to(victim)
    names = iter((collision_name, reserved_name))
    captured = {}

    def _fake_run(cmd, *args, **kwargs):
        c_path = Path(next(arg for arg in cmd if arg.endswith(".c")))
        captured["c_path"] = c_path
        captured["c_source"] = c_path.read_text(encoding="utf-8")
        return _RunResult(returncode=0)

    monkeypatch.setattr(l0c.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(l0c.tempfile, "_get_candidate_names", lambda: names)
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(_build_args(tmp_path, "main"))

    assert rc == 0
    assert captured["c_path"].name == (
        f"{l0c.tempfile.gettempprefix()}{reserved_name}.c"
    )
    assert "int main" in captured["c_source"]
    assert collision_path.is_symlink()
    assert not victim.exists()
    assert not captured["c_path"].exists()


def test_build_keep_c_preserves_c_path_without_temporary_parent_validation(
    tmp_path, monkeypatch
):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    exe_path = tmp_path / "kept"
    captured = {}

    def _unexpected_validation():
        raise AssertionError("--keep-c build must not use compiler temporaries")

    def _fake_run(cmd, *args, **kwargs):
        captured["c_path"] = Path(next(arg for arg in cmd if arg.endswith(".c")))
        return _RunResult(returncode=0)

    monkeypatch.setattr(
        "l0c._validated_temporary_directory", _unexpected_validation
    )
    monkeypatch.setattr("l0c.subprocess.run", _fake_run)

    rc = cmd_build(
        _build_args(tmp_path, "main", output=str(exe_path), keep_c=True)
    )

    assert rc == 0
    assert captured["c_path"] == exe_path.with_suffix(".c")
    assert captured["c_path"].exists()


def test_run_uses_validated_resolved_directory_for_temporary_executable(
    tmp_path, monkeypatch
):
    trusted_temp = tmp_path / "compiler-temp"
    trusted_temp.mkdir(mode=0o700)
    selected_temp = trusted_temp
    if os.name != "nt":
        selected_temp = tmp_path / "compiler-temp-alias"
        selected_temp.symlink_to(trusted_temp, target_is_directory=True)

    captured = {}
    real_named_temporary_file = l0c.tempfile.NamedTemporaryFile

    def _tracked_named_temporary_file(*args, **kwargs):
        captured["temp_dir"] = kwargs.get("dir")
        return real_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr(
        "l0c.tempfile.gettempdir", lambda: str(selected_temp)
    )
    monkeypatch.setattr(
        "l0c.tempfile.NamedTemporaryFile", _tracked_named_temporary_file
    )
    monkeypatch.setattr("l0c.cmd_build", lambda args: 1)

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
    assert captured["temp_dir"] == str(trusted_temp.resolve())


def test_run_with_keep_c_rejects_unsafe_temporary_parent_before_creation(
    tmp_path, monkeypatch, capsys
):
    temporary_executable_created = False
    build_invoked = False

    def _unsafe_temp():
        raise OSError("unsafe temporary directory")

    def _unexpected_named_temporary_file(*args, **kwargs):
        nonlocal temporary_executable_created
        temporary_executable_created = True
        raise AssertionError("temporary executable must not be created")

    def _unexpected_build(*args, **kwargs):
        nonlocal build_invoked
        build_invoked = True
        return 0

    monkeypatch.setattr("l0c._validated_temporary_directory", _unsafe_temp)
    monkeypatch.setattr(
        "l0c.tempfile.NamedTemporaryFile", _unexpected_named_temporary_file
    )
    monkeypatch.setattr("l0c.cmd_build", _unexpected_build)

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
    assert not temporary_executable_created
    assert not build_invoked
    assert (
        capsys.readouterr().err
        == "error: [L0C-9511] cannot write compiler temporary source\n"
    )


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


def test_run_output_warning_is_not_decorated_by_log(tmp_path, monkeypatch, capsys):
    def _fake_cmd_build(args):
        return 1

    monkeypatch.setattr("l0c.cmd_build", _fake_cmd_build)

    def _args(log: bool) -> argparse.Namespace:
        return argparse.Namespace(
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
            log=log,
        )

    default_rc = cmd_run(_args(log=False))
    default = capsys.readouterr()
    rich_rc = cmd_run(_args(log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (1, 1)
    assert default.out == rich.out == ""
    assert default.err == (
        "warning: [L0C-0017] '--output' is ignored in '--run' mode unless '--keep-c' is set; "
        "the executable path remains temporary\n"
    )
    _assert_plain_diagnostic_output(default.err, rich.err)


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


def test_tok_read_error_is_not_decorated_by_log(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )
    monkeypatch.setattr("l0c.load_source_utf8", lambda _path: (_ for _ in ()).throw(OSError("read failed")))

    default_rc = cmd_tok(_inspect_args(tmp_path, "main"))
    default = capsys.readouterr()
    rich_rc = cmd_tok(_inspect_args(tmp_path, "main", log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (1, 1)
    assert default.out == rich.out == ""
    assert default.err == f"error: [L0C-0040] cannot read {tmp_path / 'main.l0'}: read failed\n"
    _assert_plain_diagnostic_output(default.err, rich.err)


def test_tok_source_encoding_error_is_not_decorated_by_log(tmp_path, monkeypatch, capsys):
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

    default_rc = cmd_tok(_inspect_args(tmp_path, "main"))
    default = capsys.readouterr()
    rich_rc = cmd_tok(_inspect_args(tmp_path, "main", log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (1, 1)
    assert default.out == rich.out == ""
    assert default.err == "error: [L0C-0041] main.l0: invalid UTF-8\n"
    _assert_plain_diagnostic_output(default.err, rich.err)


def test_tok_unstructured_lexer_error_is_not_decorated_by_log(tmp_path, monkeypatch, capsys):
    _write_module(
        tmp_path,
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )

    class _ExplodingLexer:
        def __init__(self, *_args, **_kwargs):
            self.diagnostics = []

        def tokenize(self):
            raise RuntimeError("forced lexer failure")

    monkeypatch.setattr("l0c.Lexer", _ExplodingLexer)

    default_rc = cmd_tok(_inspect_args(tmp_path, "main"))
    default = capsys.readouterr()
    rich_rc = cmd_tok(_inspect_args(tmp_path, "main", log=True))
    rich = capsys.readouterr()

    assert (default_rc, rich_rc) == (1, 1)
    assert default.out == rich.out == ""
    assert default.err == "error: [L0C-0042] forced lexer failure\n"
    _assert_plain_diagnostic_output(default.err, rich.err)


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
