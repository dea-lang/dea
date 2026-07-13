#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

import l0c


def _patch_handlers(monkeypatch):
    calls = []

    def _mk_handler(name):
        def _handler(args):
            calls.append((name, args))
            return 0

        return _handler

    monkeypatch.setattr(l0c, "cmd_run", _mk_handler("run"))
    monkeypatch.setattr(l0c, "cmd_build", _mk_handler("build"))
    monkeypatch.setattr(l0c, "cmd_codegen", _mk_handler("gen"))
    monkeypatch.setattr(l0c, "cmd_check", _mk_handler("check"))
    monkeypatch.setattr(l0c, "cmd_tok", _mk_handler("tok"))
    monkeypatch.setattr(l0c, "cmd_ast", _mk_handler("ast"))
    monkeypatch.setattr(l0c, "cmd_sym", _mk_handler("sym"))
    monkeypatch.setattr(l0c, "cmd_type", _mk_handler("type"))
    return calls


def _run_main(argv):
    with pytest.raises(SystemExit) as exc:
        l0c.main(argv)
    return exc.value.code


def test_default_mode_is_build(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "build"
    assert args.entry == "app.main"


def test_explicit_run_uses_double_dash_for_program_args(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "app.main", "--", "alpha", "--beta"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "run"
    assert args.entry == "app.main"
    assert args.args == ["alpha", "--beta"]


def test_short_run_alias_uses_double_dash_for_program_args(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-r", "app.main", "--", "alpha", "--beta"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "run"
    assert args.entry == "app.main"
    assert args.args == ["alpha", "--beta"]


def test_explicit_run_rejects_implicit_program_args(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "app.main", "alpha"])

    assert rc == 2
    assert calls == []
    assert "use '--' before runtime program arguments" in capsys.readouterr().err


def test_old_style_run_command_is_not_supported(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["run", "app.main", "alpha"])

    assert rc == 2
    assert calls == []
    assert "multiple targets are not supported yet" in capsys.readouterr().err


def test_old_style_codegen_command_is_not_supported(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["codegen", "app.main"])

    assert rc == 2
    assert calls == []
    assert "multiple targets are not supported yet" in capsys.readouterr().err


def test_short_gen_alias_maps_to_gen_mode(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-g", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "gen"
    assert args.entry == "app.main"


def test_multiple_targets_rejected_for_non_run_modes(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--check", "a", "b"])

    assert rc == 2
    assert calls == []
    assert "multiple targets are not supported yet" in capsys.readouterr().err


def test_program_args_separator_only_allowed_for_run(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--check", "app.main", "--", "x"])

    assert rc == 2
    assert calls == []
    assert "arguments after '--' are valid only with '--run'" in capsys.readouterr().err


def test_include_eof_is_valid_in_tok(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--tok", "--include-eof", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "tok"
    assert args.include_eof is True


def test_runtime_include_is_rejected_outside_build_run(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--tok", "-I", "/tmp/runtime", "app.main"])

    assert rc == 2
    assert calls == []
    assert "option '--runtime-include' is valid only with modes: --build, --run" in capsys.readouterr().err


def test_keep_c_is_rejected_outside_build_run(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--check", "--keep-c", "app.main"])

    assert rc == 2
    assert calls == []
    assert "option '--keep-c' is valid only with modes: --build, --run" in capsys.readouterr().err


def test_include_eof_is_rejected_outside_tok(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "--include-eof", "app.main"])

    assert rc == 2
    assert calls == []
    assert "option '--include-eof' is valid only with modes: --tok" in capsys.readouterr().err


def test_all_modules_is_rejected_outside_dump_modes(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--gen", "--all-modules", "app.main"])

    assert rc == 2
    assert calls == []
    assert "option '--all-modules' is valid only with modes: --ast, --sym, --tok, --type" in capsys.readouterr().err


def test_unchecked_is_rejected_outside_build_run_gen(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--check", "--unchecked", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2025]" in stderr
    assert "option '--unchecked' is valid only with modes: --build, --gen, --run" in stderr


def test_unchecked_is_rejected_with_trace_flags(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "--unchecked", "--trace-memory", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2026]" in stderr
    assert "option '--unchecked' cannot be combined with '--trace-arc' or '--trace-memory'" in stderr


def test_unchecked_is_accepted_in_gen_mode(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--gen", "--unchecked", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "gen"
    assert args.unchecked is True


def test_check_basic_is_rejected_outside_build_run_gen(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--check", "--check-basic", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2027]" in stderr
    assert "option '--check-basic' is valid only with modes: --build, --gen, --run" in stderr


def test_check_basic_is_rejected_with_trace_flags(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "--check-basic", "--trace-memory", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2028]" in stderr
    assert "option '--check-basic' cannot be combined with '--unchecked', '--trace-arc', or '--trace-memory'" in stderr


def test_check_basic_is_rejected_with_unchecked(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "--check-basic", "--unchecked", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2028]" in stderr
    assert "option '--check-basic' cannot be combined with '--unchecked', '--trace-arc', or '--trace-memory'" in stderr


def test_check_basic_is_accepted_in_gen_mode(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--gen", "--check-basic", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "gen"
    assert args.check_basic is True


def test_output_is_allowed_in_run_mode(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "--output", "x", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "run"
    assert args.entry == "app.main"
    assert args.output == "x"


def test_default_build_allows_target_named_run(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["run"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "build"
    assert args.entry == "run"


def test_help_uses_compiler_identity_text(capsys):
    with pytest.raises(SystemExit) as exc:
        l0c.main(["--help"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Dea language / L0 compiler (Stage 1)" in captured.out
    assert "show compiler version and exit" in captured.out
    assert captured.err == ""


def test_version_prints_compiler_identity_text(capsys):
    with pytest.raises(SystemExit) as exc:
        l0c.main(["--version"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == "Dea language / L0 compiler (Stage 1)\n"
    assert captured.err == ""


def test_verbose_logs_compiler_identity_text(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-v", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    captured = capsys.readouterr()
    assert "Dea language / L0 compiler (Stage 1)" in captured.err


def test_verbose_missing_target_still_logs_compiler_identity_text(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-v"])

    assert rc == 2
    assert calls == []
    captured = capsys.readouterr()
    assert "the following arguments are required: targets" in captured.err
    assert "Dea language / L0 compiler (Stage 1)" in captured.err
