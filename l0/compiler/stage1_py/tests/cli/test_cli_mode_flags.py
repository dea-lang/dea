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
    monkeypatch.setattr(l0c, "cmd_compile", _mk_handler("compile"))
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

    rc = _run_main(["-Gc", "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "gen"
    assert args.entry == "app.main"


@pytest.mark.parametrize("alias", ["-c", "--compile"])
def test_compile_aliases_select_compile_mode(monkeypatch, alias):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main([alias, "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "compile"
    assert args.entry == "app.main"


def test_compile_mode_dispatches_to_nyi_without_artifacts(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.chdir(tmp_path)

    rc = _run_main(["--compile", "app.main"])

    assert rc == 1
    assert "[L0C-9510]" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_compile_mode_preserves_interface_path_order(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(
        [
            "-c",
            "-I",
            "interfaces/first",
            "-Iinterfaces/second",
            "--interface-path=interfaces/third",
            "app.main",
        ]
    )

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "compile"
    assert args.interface_paths == [
        "interfaces/first",
        "interfaces/second",
        "interfaces/third",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["-I", "interfaces", "app.main"],
        ["--run", "-Iinterfaces", "app.main"],
        ["--check", "--interface-path=interfaces", "app.main"],
    ],
)
def test_interface_paths_are_rejected_outside_compile(
    monkeypatch, capsys, argv
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(argv)

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2031]" in stderr
    assert "option '--interface-path' is valid only with mode: --compile" in stderr


@pytest.mark.parametrize("option", ["-I", "--interface-path"])
def test_interface_path_requires_a_value(monkeypatch, capsys, option):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-c", "app.main", option])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2003]" in stderr
    assert f"missing value for option '{option}'" in stderr


def test_compile_mode_requires_exactly_one_target(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-c", "a", "b"])

    assert rc == 2
    assert calls == []
    assert "[L0C-2024]" in capsys.readouterr().err


def test_compile_mode_requires_a_target(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--compile"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2021]" in stderr
    assert "missing required target module/file name" in stderr


def test_compile_mode_conflicts_with_other_modes(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-c", "--run", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2002]" in stderr
    assert "multiple mode flags provided: --compile conflicts with --run" in stderr


@pytest.mark.parametrize(
    "argv, code",
    [
        (["-c", "--output", "out.o", "app.main"], "L0C-2010"),
        (["-c", "-Cc", "clang", "app.main"], "L0C-2012"),
        (["-c", "-Ri", "runtime", "app.main"], "L0C-2014"),
    ],
)
def test_build_only_options_are_rejected_in_compile_mode(
    monkeypatch, capsys, argv, code
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(argv)

    assert rc == 2
    assert calls == []
    assert f"[{code}]" in capsys.readouterr().err


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


@pytest.mark.parametrize("mode_args", [[], ["--check"], ["-c"]])
def test_bare_program_args_separator_is_rejected_outside_run(
    monkeypatch, capsys, mode_args
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main([*mode_args, "app.main", "--"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2023]" in stderr
    assert "arguments after '--' are valid only with '--run'" in stderr


def test_run_accepts_a_bare_program_args_separator(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", "app.main", "--"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "run"
    assert args.entry == "app.main"
    assert args.args == []


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

    rc = _run_main(["--tok", "-Ri", "/tmp/runtime", "app.main"])

    assert rc == 2
    assert calls == []
    assert "option '--runtime-include' is valid only with modes: --build, --run" in capsys.readouterr().err


@pytest.mark.parametrize(
    "option, code",
    [
        ("--output=", "L0C-2010"),
        ("--c-compiler=", "L0C-2012"),
        ("--c-options=", "L0C-2013"),
        ("--c-source=", "L0C-2029"),
        ("--runtime-include=", "L0C-2014"),
        ("--runtime-lib=", "L0C-2015"),
        ("--interface-path=", "L0C-2031"),
    ],
)
def test_empty_mode_scoped_values_remain_present(
    monkeypatch, capsys, option, code
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--check", option, "app.main"])

    assert rc == 2
    assert calls == []
    assert f"[{code}]" in capsys.readouterr().err


def test_namespaced_root_and_log_aliases(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(
        [
            "--check",
            "-Vl",
            "-Rp",
            "project/first",
            "-Rp=project/second",
            "-Rs",
            "system/first",
            "-Rs=system/second",
            "app.main",
        ]
    )

    assert rc == 0
    assert len(calls) == 1
    _, args = calls[0]
    assert args.log is True
    assert args.project_root == ["project/first", "project/second"]
    assert args.sys_root == ["system/first", "system/second"]


def test_namespaced_c_and_runtime_aliases(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(
        [
            "-Cc",
            "clang",
            "-Co=-Og -DDEBUG",
            "-Ri",
            "runtime/include",
            "-Rl=runtime/lib",
            "app.main",
        ]
    )

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "build"
    assert args.c_compiler == "clang"
    assert args.c_options == "-Og -DDEBUG"
    assert args.runtime_include == "runtime/include"
    assert args.runtime_lib == "runtime/lib"


@pytest.mark.parametrize(
    "aliases, expected",
    [
        (["-Gk", "-Va"], {"keep_c": True, "trace_arc": True}),
        (["-Vm"], {"trace_memory": True}),
        (["-Sb"], {"check_basic": True}),
        (["-Su"], {"unchecked": True}),
    ],
)
def test_generated_safety_and_visibility_aliases(
    monkeypatch, aliases, expected
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["--run", *aliases, "app.main"])

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "run"
    for attr, value in expected.items():
        assert getattr(args, attr) is value


def test_long_configuration_forms_are_unchanged(monkeypatch):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(
        [
            "--log",
            "--project-root=project",
            "--sys-root=system",
            "--c-compiler=clang",
            "--c-options=-Og -DDEBUG",
            "--runtime-include=runtime/include",
            "--runtime-lib=runtime/lib",
            "app.main",
        ]
    )

    assert rc == 0
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "build"
    assert args.log is True
    assert args.project_root == ["project"]
    assert args.sys_root == ["system"]
    assert args.c_compiler == "clang"
    assert args.c_options == "-Og -DDEBUG"
    assert args.runtime_include == "runtime/include"
    assert args.runtime_lib == "runtime/lib"


@pytest.mark.parametrize(
    "argv",
    [
        ["-P", "project", "app.main"],
        ["-C", "-Og", "app.main"],
        ["-R", "app.main"],
    ],
)
def test_retired_unprefixed_aliases_are_unknown(monkeypatch, capsys, argv):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(argv)

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2001]" in stderr
    assert "unknown option" in stderr


@pytest.mark.parametrize(
    "argv",
    [
        ["-Rp_project", "app.main"],
        ["-Rs_system", "app.main"],
        ["-Ccclang", "app.main"],
        ["-Co_debug", "app.main"],
        ["-Ri_include", "app.main"],
        ["-Rl_lib", "app.main"],
        ["-Vl_extra", "app.main"],
        ["-Gcmore", "app.main"],
        ["-Gkmore", "app.main"],
        ["-Sbmore", "app.main"],
        ["-Sumore", "app.main"],
        ["-Vamore", "app.main"],
        ["-Vmmore", "app.main"],
        ["-Vmore", "app.main"],
    ],
)
def test_namespaced_aliases_reject_concatenated_values(
    monkeypatch, capsys, argv
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(argv)

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2001]" in stderr
    assert "unknown option" in stderr


@pytest.mark.parametrize("option", ["-Rr", "-Cl"])
def test_deferred_namespaced_aliases_remain_unknown(
    monkeypatch, capsys, option
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main([option, "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2001]" in stderr
    assert f"unknown option '{option}'" in stderr


@pytest.mark.parametrize(
    "argv",
    [
        ["--comp", "app.main"],
        ["-oattached", "app.main"],
        ["-o=attached", "app.main"],
        ["-I=interfaces", "app.main"],
        ["-L=external/lib", "app.main"],
        ["-l=example", "app.main"],
    ],
)
def test_unsupported_option_spellings_are_unknown(monkeypatch, capsys, argv):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(argv)

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2001]" in stderr
    assert "unknown option" in stderr
    assert "[L0C-2032]" not in stderr


@pytest.mark.parametrize(
    "argv, message",
    [
        (
            ["-g", "app.main"],
            "option '-g' is reserved for debug information and is not supported yet",
        ),
        (
            ["-S", "app.main"],
            "option '-S' is reserved for assembly output and is not supported yet",
        ),
        (
            ["-L", "external/lib", "app.main"],
            "option '-L' is reserved for external library search and is not supported yet",
        ),
        (
            ["-Lexternal/lib", "app.main"],
            "option '-L' is reserved for external library search and is not supported yet",
        ),
        (
            ["-l", "example", "app.main"],
            "option '-l' is reserved for external library selection and is not supported yet",
        ),
        (
            ["-lexample", "app.main"],
            "option '-l' is reserved for external library selection and is not supported yet",
        ),
    ],
)
def test_reserved_canonical_options_report_structured_errors(
    monkeypatch, capsys, argv, message
):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(argv)

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2032]" in stderr
    assert message in stderr


@pytest.mark.parametrize("option", ["-L", "-l"])
def test_reserved_library_options_require_values(monkeypatch, capsys, option):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["app.main", option])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2003]" in stderr
    assert f"missing value for option '{option}'" in stderr
    assert "[L0C-2032]" not in stderr


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
    assert "-V, --version" in captured.out
    assert "-Vl, --log" in captured.out
    assert "-Rp, --project-root PROJECT_ROOT" in captured.out
    assert "-Rs, --sys-root SYS_ROOT" in captured.out
    assert "-c, --compile" in captured.out
    assert "--gen, -Gc, --codegen" in captured.out
    assert "-Gk, --keep-c" in captured.out
    assert "-Sb, --check-basic" in captured.out
    assert "-Su, --unchecked" in captured.out
    assert "-Va, --trace-arc" in captured.out
    assert "-Vm, --trace-memory" in captured.out
    assert "-Cc, --c-compiler C_COMPILER" in captured.out
    assert "-Co, --c-options C_OPTIONS" in captured.out
    assert "-I, --interface-path INTERFACE_PATH" in captured.out
    assert "-Ri, --runtime-include RUNTIME_INCLUDE" in captured.out
    assert "-Rl, --runtime-lib RUNTIME_LIB" in captured.out
    assert "--output, -o OUTPUT" in captured.out
    assert "  -g                    Generate debug information" in captured.out
    assert "  -S                    Emit assembly output" in captured.out
    assert "  -L LIBRARY_PATH" in captured.out
    assert "  -l LIBRARY" in captured.out
    assert "-P, --project-root" not in captured.out
    assert "-C, --c-options" not in captured.out
    assert "-I, --runtime-include" not in captured.out
    assert "-L, --runtime-lib" not in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("early_exit", ["--help", "-V", "--version"])
def test_help_and_version_short_circuit_reserved_options(capsys, early_exit):
    with pytest.raises(SystemExit) as exc:
        l0c.main(["-g", early_exit])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "[L0C-2032]" not in captured.err


@pytest.mark.parametrize("early_exit", ["--help", "-V", "--version"])
def test_help_and_version_short_circuit_bare_separator_validation(
    capsys, early_exit
):
    with pytest.raises(SystemExit) as exc:
        l0c.main([early_exit, "--"])

    assert exc.value.code == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("version_option", ["-V", "--version"])
def test_version_prints_compiler_identity_text(capsys, version_option):
    with pytest.raises(SystemExit) as exc:
        l0c.main([version_option])

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


def test_only_v_can_form_a_short_option_cluster(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-vGc", "app.main"])

    assert rc == 2
    assert calls == []
    stderr = capsys.readouterr().err
    assert "[L0C-2001]" in stderr
    assert "unknown option '-vGc'" in stderr


def test_verbose_missing_target_still_logs_compiler_identity_text(monkeypatch, capsys):
    calls = _patch_handlers(monkeypatch)

    rc = _run_main(["-v"])

    assert rc == 2
    assert calls == []
    captured = capsys.readouterr()
    assert "[L0C-2021] missing required target module/file name" in captured.err
    assert "Dea language / L0 compiler (Stage 1)" in captured.err


@pytest.mark.parametrize(
    "value_option",
    [
        "--project-root",
        "--sys-root",
        "--c-compiler",
        "--c-options",
        "--runtime-include",
        "--runtime-lib",
        "--interface-path",
        "--output",
        "-Rp",
        "-Rs",
        "-Cc",
        "-Co",
        "-Ri",
        "-Rl",
        "-I",
        "-L",
        "-l",
        "-o",
    ],
)
def test_option_looking_values_do_not_enable_fallback_verbosity(
    monkeypatch, capsys, value_option
):
    log_calls = []
    monkeypatch.setattr(
        l0c,
        "log_info",
        lambda context, message: log_calls.append((context, message)),
    )

    rc = _run_main([value_option, "-vvv"])

    assert rc == 2
    assert log_calls == []
    assert "[L0C-2021]" in capsys.readouterr().err


@pytest.mark.parametrize("consumed_log_value", ["-Vl", "--log"])
def test_consumed_log_values_do_not_enable_rich_fallback_logging(
    monkeypatch, consumed_log_value
):
    log_calls = []
    monkeypatch.setattr(
        l0c,
        "log_info",
        lambda context, message: log_calls.append((context, message)),
    )

    rc = _run_main(["-v", "-Co", consumed_log_value])

    assert rc == 2
    assert len(log_calls) == 1
    context, message = log_calls[0]
    assert context.log_rich_format is False
    assert message == "Dea language / L0 compiler (Stage 1)"


def test_real_verbosity_and_log_flags_enable_rich_fallback_logging(monkeypatch):
    log_calls = []
    monkeypatch.setattr(
        l0c,
        "log_info",
        lambda context, message: log_calls.append((context, message)),
    )

    rc = _run_main(["-v", "-Vl"])

    assert rc == 2
    assert len(log_calls) == 1
    context, message = log_calls[0]
    assert context.log_rich_format is True
    assert message == "Dea language / L0 compiler (Stage 1)"
