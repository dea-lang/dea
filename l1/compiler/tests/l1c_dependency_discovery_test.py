#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Exercise compiler-produced P1689 reports and caller-owned Make composition."""

from __future__ import annotations

from functools import partial
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from l1c_compile_only_test import L1_ROOT
from l1c_managed_preparation_test import invoke, preparation_c_compiler, toolchain_fixture
from l1c_profile_test import execute, no_preparation, snapshot

sys.path.insert(0, str(L1_ROOT / "scripts"))
from make_test_support import find_gnu_make


FIXTURES = L1_ROOT / "compiler/tests/fixtures"
ADAPTER = L1_ROOT / "scripts/p1689_make.py"
PROJECT = FIXTURES / "dependency_discovery"


def source(root: Path, name: str, body: str) -> Path:
    """Write one canonical module into a fixture source root.

    Args:
        root: Project source root.
        name: Canonical dotted module name.
        body: Module declarations following its header.

    Returns:
        The written source path.
    """
    path = root / (name.replace(".", "/") + ".l1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"module {name};\n{body}\n", encoding="utf-8")
    return path


def rules_by_name(report: dict) -> dict[str, dict]:
    """Validate the P1689 core envelope and index its unique source actions.

    Args:
        report: Decoded compiler report.

    Returns:
        Canonical provider names mapped to their compilation rules.
    """
    assert report["version"] == 1 and report["revision"] == 0, report
    result = {}
    for rule in report["rules"]:
        assert Path(rule["work-directory"]).is_absolute(), rule
        assert len(rule["provides"]) == 1, rule
        provider = rule["provides"][0]
        name = provider["logical-name"]
        assert name not in result, report
        assert provider["compiled-module-path"] in rule["outputs"], rule
        assert Path(provider["source-path"]).suffix == ".l1", provider
        assert Path(rule["primary-output"]).suffix == ".o", rule
        required = [item["logical-name"] for item in rule.get("requires", [])]
        assert name not in required and len(required) == len(set(required)), rule
        result[name] = rule
    return result


def require_names(rule: dict) -> set[str]:
    """Return one action's core prerequisite module names.

    Args:
        rule: P1689 compilation rule.

    Returns:
        Required provider names.
    """
    return {item["logical-name"] for item in rule.get("requires", [])}


def test_reports(root: Path, env: dict[str, str], compiler: Path, cc: str) -> None:
    """Verify clean discovery, provider authority, path fidelity and publication.

    Args:
        root: Isolated test workspace.
        env: Compiler toolchain environment.
        compiler: Canonical native compiler.
        cc: Explicit native C compiler used only to prepare stale interfaces.
    """
    call = partial(invoke, root, env, compiler=compiler)
    # The L0-hosted compiler uses narrow Windows argv/filesystem APIs. Keep
    # native Windows fixtures ASCII; POSIX and the Python adapter cover Unicode.
    project = root / "source quoted"
    if os.name != "nt":
        project = root / 'source Ω "quoted" \\literal'
    source(project, "graph.helper", "export value; func value() -> int { return 1; }")
    source(project, "graph.left", "export value; import graph.helper; func value() -> int { return 2; }")
    source(project, "graph.right", "export value; import graph.helper; func value() -> int { return 3; }")
    source(project, "graph.effect", "let effect: int = 4;")
    entry = source(project, "graph.app", "import graph.left; import graph.right; import graph.effect; "
                   "import graph.left; func main() -> int { return 0; }")
    artifacts = root / ("future output" if os.name == "nt" else "future output Ω")
    args = ("--scan-deps", "graph.app", "--artifact-root", str(artifacts), "-Rp", str(project))
    original_env = dict(env)
    env.update(L1_CC="missing-scan-native-compiler", L1_STDLIB_CACHE=str(root / "scan-cache"),
               L1_RUNTIME_INCLUDE=str(root / "missing-headers"), L1_RUNTIME_LIB=str(root / "missing-library"))
    first = call(*args)
    assert first.stdout == call(*args).stdout, "unchanged scans were not deterministic"
    report = json.loads(first.stdout)
    rules = rules_by_name(report)
    assert set(rules) == {"graph.helper", "graph.left", "graph.right", "graph.effect", "graph.app"}, rules
    assert list(rules).index("graph.helper") < list(rules).index("graph.left") < list(rules).index("graph.app")
    assert {"graph.helper", "graph.left", "graph.right", "graph.effect"} <= require_names(rules["graph.app"])
    assert Path(rules["graph.app"]["provides"][0]["source-path"]).samefile(entry)
    assert not artifacts.exists() and not (root / "scan-cache").exists()
    no_preparation(first)
    output = root / "report.json"
    published = call(*args, "-o", str(output))
    assert not published.stdout and output.read_text(encoding="utf-8") == first.stdout
    missing_parent = root / "missing-report-parent/report.json"
    call(*args, "-o", str(missing_parent), expected=1)
    assert not missing_parent.exists()
    before_source = entry.read_bytes()
    refused = call(*args, "-o", str(entry), expected=1)
    assert "L1C-220" in refused.stderr and entry.read_bytes() == before_source
    if os.name != "nt":
        alias = root / "source-alias.json"
        alias.symlink_to(entry)
        call(*args, "-o", str(alias), expected=1)
        assert entry.read_bytes() == before_source and alias.is_symlink()
        alias.unlink()
        os.link(entry, alias)
        call(*args, "-o", str(alias), expected=1)
        assert entry.read_bytes() == before_source
    old_report = output.read_bytes()
    entry.write_text("module graph.app; import missing.provider; func main() {}\n", encoding="utf-8")
    call(*args, "-o", str(output), expected=1)
    assert output.read_bytes() == old_report, "failed scan replaced the last complete report"
    entry.write_bytes(before_source)
    call("--scan-deps", "graph.app", "-Rp", str(project), expected=2)
    call("--check", "graph.app", "--artifact-root", str(artifacts), "-Rp", str(project), expected=2)
    env.clear()
    env.update(original_env)

    # Prebuilt dependency closure includes graph-loaded link-only interfaces.
    closure = root / "closure-source"
    source(closure, "closure", "import graph.provider; func main() {}")
    selected = FIXTURES / "module_graph/interfaces_first"
    closed = json.loads(call("--scan-deps", "closure", "--artifact-root", str(artifacts), "-Rp", str(closure),
                             "-I", str(selected)).stdout)
    assert {"graph.provider", "graph.required", "graph.linked"} <= require_names(rules_by_name(closed)["closure"])
    malformed = FIXTURES / "module_graph/interfaces_bad_parse"
    failed = call("--scan-deps", "closure", "--artifact-root", str(artifacts), "-Rp", str(closure),
                  "-Rp", str(FIXTURES / "driver"), "-I", str(malformed), expected=1)
    assert "provider.l1m" in failed.stderr and not failed.stdout

    # A prebuilt facade can require a source-backed type provider transitively.
    mixed = json.loads(call("--scan-deps", "mixed_fallback_enum_entry", "--artifact-root", str(artifacts),
                           "-Rp", str(FIXTURES / "semantics"), "-I",
                           str(FIXTURES / "module_graph/interfaces_mixed")).stdout)
    mixed_rules = rules_by_name(mixed)
    assert list(mixed_rules).index("mixed.source_enum") < list(mixed_rules).index("mixed_fallback_enum_entry")
    assert {"mixed.facade", "mixed.source_enum"} <= require_names(mixed_rules["mixed_fallback_enum_entry"])

    # Output mapping is never an implicit input root, even after previous builds.
    stale = root / "stale-source"
    model = source(stale, "model", "export value; func value() -> int { return 1; }")
    source(stale, "app", "import model; func main() -> int { return model::value(); }")
    artifacts.mkdir()
    call("--compile", "model", "-Rp", str(stale), "--c-compiler", cc, "-o", str(artifacts / "model.o"))
    source(stale, "helper", "export value; func value() -> int { return 2; }")
    model.write_text("module model; export value; import helper; func value() -> int { return helper::value(); }\n",
                     encoding="utf-8")
    scan = ("--scan-deps", "app", "--artifact-root", str(artifacts), "-Rp", str(stale))
    assert set(rules_by_name(json.loads(call(*scan).stdout))) == {"app", "model", "helper"}
    explicit = rules_by_name(json.loads(call(*scan, "-I", str(artifacts)).stdout))
    assert set(explicit) == {"app"} and "helper" not in require_names(explicit["app"])
    interface = artifacts / "model.l1m"
    before = interface.read_bytes()
    call(*scan, "-I", str(artifacts), "-o", str(interface), expected=1)
    assert interface.read_bytes() == before


def gnu_make() -> str:
    """Find a GNU Make executable supporting explicit grouped targets.

    Returns:
        An absolute GNU Make 4.3 or newer executable path.

    Raises:
        AssertionError: No supported Make executable is available.
        ValueError: An explicit DEA_TEST_MAKE selection is invalid.
    """
    executable = find_gnu_make()
    assert executable is not None, "dependency Make integration requires GNU Make >= 4.3 (set DEA_TEST_MAKE)"
    return executable


def test_make(root: Path, env: dict[str, str], compiler: Path, cc: str) -> None:
    """Build public reports and exercise conservative incremental composition.

    Args:
        root: Isolated workspace.
        env: Compiler toolchain environment.
        compiler: Canonical native compiler.
        cc: Explicit supported native C compiler.
    """
    call = partial(invoke, root, env, compiler=compiler)
    profile = root / "explicit profile"
    common = ("--c-compiler", cc, "--c-options=-O0", "--no-line-directives")
    call("--create-profile", *common, "-o", str(profile))
    profile_before = snapshot(profile)
    selected = ["--profile", str(profile)]
    project = root / ("make source 'quoted" if os.name == "nt" else "make source 'Ω")
    earlier = root / "earlier source"
    earlier.mkdir()
    provider_root = root / "prebuilt"
    provider_root.mkdir()
    source(project, "helper", "export value; func value() -> int { return 7; }")
    model = source(project, "model", "export value; import helper; func value() -> int { return helper::value(); }")
    source(project, "other_entry", "func main() -> int { return 93; }")
    app = source(project, "app", 'import model; import other_entry; import std.io; '
                 'func main() -> int { printl_s("discovery-ok"); return model::value() - 7; }')
    artifacts = root / ("make output '#" if os.name == "nt" else "make output '\"# Ω")
    executable = artifacts / ("program.exe" if os.name == "nt" else "program")
    config_path = root / "project.json"
    action_log = root / "actions.jsonl"
    header = root / "caller_header.h"
    header.write_text("/* caller compilation prerequisite */\n", encoding="utf-8")
    config = dict(adapter=str(ADAPTER), compiler=str(compiler), make=gnu_make(), entry="app",
                  artifact_root=str(artifacts), executable=str(executable), action_log=str(action_log),
                  inputs=["-Rp", str(earlier), "-Rp", str(project), "-I", str(provider_root), *selected],
                  link_inputs=["-I", str(provider_root), *selected], native=[], compile_deps=[str(header)])

    def build(expected: int = 0) -> list[list[str]]:
        """Run the outer Make entry and return its newly scheduled native actions.

        Args:
            expected: Zero for success, or nonzero for an expected failure.

        Returns:
            Newly recorded compilation and link actions.
        """
        config_path.write_text(json.dumps(config), encoding="utf-8")
        prior = action_log.read_text(encoding="utf-8").splitlines() if action_log.exists() else []
        outer_env = dict(env, PYTHON=sys.executable, DEA_PROJECT_DRIVER=str(PROJECT / "build.py"),
                         DEA_PROJECT_CONFIG=str(config_path))
        result = subprocess.run([config["make"], "--no-print-directory", "-f", str(PROJECT / "Makefile")],
                                cwd=root, env=outer_env, text=True, capture_output=True, timeout=600)
        assert (result.returncode == 0) == (expected == 0), (result.returncode, result.stdout, result.stderr)
        current = action_log.read_text(encoding="utf-8").splitlines() if action_log.exists() else []
        return [json.loads(line) for line in current[len(prior):]]

    first = build()
    assert [action[0] for action in first].count("compile") == 4 and first[-1][0] == "link", first
    execute(executable, "discovery-ok\n")
    fragment = artifacts / "dependencies.mk"
    fragment_time = fragment.stat().st_mtime_ns
    assert build() == [] and fragment.stat().st_mtime_ns == fragment_time
    outer_env = dict(env, PYTHON=sys.executable, DEA_PROJECT_DRIVER=str(PROJECT / "build.py"),
                     DEA_PROJECT_CONFIG=str(config_path))
    children = [subprocess.Popen([config["make"], "--no-print-directory", "-f", str(PROJECT / "Makefile")],
                                cwd=root, env=outer_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(2)]
    before_parallel = action_log.read_bytes()
    for child in children:
        stdout, stderr = child.communicate(timeout=600)
        assert child.returncode == 0, (stdout, stderr)
    assert action_log.read_bytes() == before_parallel and fragment.stat().st_mtime_ns == fragment_time

    # Annotation-free reports retain the same scheduling facts and build behavior.
    config["strip_annotations"] = True
    assert build() == []
    assert build() == []
    execute(executable, "discovery-ok\n")

    # Missing peers of both entry and provider pairs must repair the entire action,
    # including when only the surviving peer is requested from inner Make.
    for module in ("helper", "app"):
        for removed, surviving in ((".o", ".l1m"), (".l1m", ".o")):
            build()
            (artifacts / (module + removed)).unlink()
            config["goals"] = [str(artifacts / (module + surviving))]
            actions = build()
            assert any(action[0] == "compile" and Path(action[1]).name == module + ".o" for action in actions), actions
            assert (artifacts / (module + removed)).is_file()
            config.pop("goals")
    build()
    assert build() == []

    # Caller native headers belong to compilation prerequisites, not just linking.
    time.sleep(0.02)
    header.write_text("/* changed caller compilation prerequisite */\n", encoding="utf-8")
    changed_header = build()
    assert [action[0] for action in changed_header].count("compile") == 4, changed_header
    assert changed_header[-1][0] == "link"

    # An implementation-only update must relink despite an unchanged public shape.
    prior_interface = (artifacts / "model.l1m").read_bytes()
    model.write_text(model.read_text(encoding="utf-8").replace("return helper::value();", "return helper::value() + 0;"),
                     encoding="utf-8")
    changed_body = build()
    assert changed_body[-1][0] == "link" and prior_interface == (artifacts / "model.l1m").read_bytes()

    # Fresh source edges are visible despite stale local generated interfaces.
    source(project, "new_helper", "export value; func value() -> int { return 7; }")
    model.write_text("module model; export value; import new_helper; "
                     "func value() -> int { return new_helper::value(); }\n", encoding="utf-8")
    added = build()
    assert any(Path(action[1]).name == "new_helper.o" for action in added if action[0] == "compile"), added
    assert "helper.o" not in [Path(path).name for path in re.findall(r"[^ ]+\.o", fragment.read_text())]
    execute(executable, "discovery-ok\n")

    # A newly selected source older than outputs still invalidates the whole graph.
    replacement = source(earlier, "model", "export value; import new_helper; "
                          "func value() -> int { return new_helper::value() + 0; }")
    os.utime(replacement, (1, 1))
    changed_roots = build()
    assert [action[0] for action in changed_roots].count("compile") == 4, changed_roots
    assert changed_roots[-1][0] == "link" and build() == []
    config["inputs"] = ["-Rp", str(project), "-Rp", str(earlier), "-I", str(provider_root), *selected]
    reordered = build()
    assert [action[0] for action in reordered].count("compile") == 4, reordered
    config["inputs"] = ["-Rp", str(earlier), "-Rp", str(project), "-I", str(provider_root), *selected]
    build()

    # Source removal invalidates linking and removes the obsolete object argument.
    app.write_text('module app; import model; import std.io; func main() -> int { '
                   'printl_s("discovery-ok"); return model::value() - 7; }\n', encoding="utf-8")
    removed = build()
    assert removed[-1][0] == "link" and "other_entry.o" not in fragment.read_text(encoding="utf-8")

    # Scan failure must never invoke the adapter or consume the older report.
    app_bytes = app.read_bytes()
    saved_fragment = fragment.read_bytes()
    app.write_text("module app; import absent.module; func main() {}\n", encoding="utf-8")
    assert build(expected=1) == [] and fragment.read_bytes() == saved_fragment
    app.write_bytes(app_bytes)

    # Compilation rollback preserves the previous pair and executable.
    build()
    previous = {path: path.read_bytes() for path in (artifacts / "model.o", artifacts / "model.l1m", executable)}
    profile_inputs = config["inputs"]
    config["inputs"] = ["-Rp", str(earlier), "-Rp", str(project)]
    config["native"] = ["--c-compiler", cc, "--c-options=-include missing_dependency_fixture_header.h"]
    build(expected=1)
    assert all(path.read_bytes() == data for path, data in previous.items())
    config["inputs"] = profile_inputs
    config["native"] = []
    build()

    # An imported entry does not rescue a requested target without an eligible main.
    source(project, "no_entry", "export value; import other_entry; func value() -> int { return 1; }")
    config["entry"] = "no_entry"
    build(expected=1)
    config["entry"] = "app"
    build()

    # Prebuilt authority plus generated-root preflight reject residual shadowing
    # candidates before any action, while unrelated leftovers are harmless.
    call("--compile", "model", "-Rp", str(earlier), "-Rp", str(project), "-I", str(artifacts), *selected,
         "-o", str(provider_root / "model.o"))
    for path in provider_root.iterdir():
        os.utime(path, (1, 1))
    assert build(expected=1) == []
    (artifacts / "model.l1m").unlink()
    build()
    assert "model.o" not in fragment.read_text(encoding="utf-8").split("DEA_OBJECTS :=", 1)[1].splitlines()[0]
    (artifacts / "unreferenced.l1m").write_text("unused leftover\n", encoding="utf-8")
    assert build() == []
    saved_provider = root / "saved-model.l1m"
    (provider_root / "model.l1m").rename(saved_provider)
    source_again = build()
    assert any(action[0] == "compile" and Path(action[1]).name == "model.o" for action in source_again), source_again
    saved_provider.rename(provider_root / "model.l1m")
    assert build(expected=1) == []
    (artifacts / "model.l1m").unlink()
    build()
    if os.name != "nt":
        (artifacts / "model.l1m").symlink_to(root / "absent-interface")
        assert build(expected=1) == []
        (artifacts / "model.l1m").unlink()
    (artifacts / "model.l1m").mkdir()
    assert build(expected=1) == []
    (artifacts / "model.l1m").rmdir()
    assert build() == []
    stale_bundled = artifacts / "std/io.l1m"
    stale_bundled.parent.mkdir()
    shutil.copy2(profile / "modules/std/io.l1m", stale_bundled)
    assert build(expected=1) == []
    stale_bundled.unlink()
    assert build() == []
    assert snapshot(profile) == profile_before

    # Compare dependency-driven lifecycle composition to existing managed and
    # explicit native compositions, including matching generated module C bytes.
    lifecycle = root / "lifecycle source"
    shutil.copytree(FIXTURES / "separate_compilation/lifecycle", lifecycle / "lifecycle")
    lifecycle_main = lifecycle / "lifecycle/main.l1"
    lifecycle_main.write_text(lifecycle_main.read_text(encoding="utf-8").replace("module lifecycle.main;",
                              "module lifecycle.main;\nimport std.io;").replace(
                                  "    return 0;", '    printl_s("lifecycle-ok");\n    return 0;'), encoding="utf-8")
    shim = root / "lifecycle_observer.o"
    subprocess.run([cc, "-c", str(FIXTURES / "separate_compilation/lifecycle_observer.c"), "-o", str(shim)], check=True)
    lifecycle_artifacts = root / "lifecycle outputs"
    config.update(entry="lifecycle.main", artifact_root=str(lifecycle_artifacts),
                  executable=str(lifecycle_artifacts / executable.name), inputs=["-Rp", str(lifecycle), *selected],
                  link_inputs=selected, native=["--keep-c"], foreign=["--foreign-object", str(shim)],
                  link_deps=[str(shim)])
    actions = build()
    assert [action[0] for action in actions].count("compile") == 4, actions
    execute(Path(config["executable"]), "lifecycle-ok\n")
    assert build() == []
    for mode in ("explicit", "managed"):
        direct = root / (mode + "-lifecycle" + executable.suffix)
        selection = selected if mode == "explicit" else [*common, "--stdlib-cache", str(root / "composition cache")]
        call("--build", "lifecycle.main", "-Rp", str(lifecycle), *selection, "--foreign-object", str(shim),
             "--keep-c", "-o", str(direct))
        execute(direct, "lifecycle-ok\n")
        for name in ("leaf", "provider", "side_effect", "main"):
            assert (lifecycle_artifacts / "lifecycle" / (name + ".c")).read_bytes() == (
                direct.with_name(direct.name + ".dea-c") / "lifecycle" / (name + ".c")).read_bytes()

    # Build a bundled module from source, then switch to each supported prebuilt
    # policy. Residual interfaces must fail preflight before compile or link.
    source(project, "bundled_app", "import std.types; func main() {}")
    bundled_artifacts = root / "bundled outputs"
    bundled = str(Path(env["L1_HOME"]) / "shared/l1/stdlib")
    source_inputs = ["-Rp", str(project), "--sys-root", bundled, "--no-managed-stdlib"]
    for selection in (selected, []):
        config.update(entry="bundled_app", artifact_root=str(bundled_artifacts),
                      executable=str(bundled_artifacts / executable.name), inputs=source_inputs,
                      link_inputs=[], native=list(common),
                      link_native=[*common[:-1], "--stdlib-cache", str(root / "composition cache")],
                      foreign=[], link_deps=[])
        build()
        execute(Path(config["executable"]), "")
        assert (bundled_artifacts / "std/types.l1m").is_file()
        config.update(inputs=["-Rp", str(project), *selection], link_inputs=selection,
                      native=[] if selection else list(common),
                      link_native=[] if selection else [*common[:-1], "--stdlib-cache", str(root / "composition cache")])
        assert build(expected=1) == []
        (bundled_artifacts / "std/types.l1m").unlink()
        build()
        execute(Path(config["executable"]), "")
        assert build() == []

    # Explicit semantic scans remain usable without original bundled sources or
    # native tool selection and never consult a managed cache.
    isolated = dict(env, L1_CC="missing-scan-compiler", L1_RUNTIME_INCLUDE=str(root / "absent-headers"),
                    L1_RUNTIME_LIB=str(root / "absent-runtime"), L1_STDLIB_CACHE=str(root / "never-cache"))
    shutil.rmtree(Path(env["L1_HOME"]) / "shared")
    shutil.rmtree(Path(env["L1_BUILD_DIR"]) / "interfaces")
    scanned = invoke(root, isolated, "--scan-deps", "app", "--artifact-root", str(root / "profile-scan"),
                     "-Rp", str(project), *selected, compiler=compiler)
    selected_rules = rules_by_name(json.loads(scanned.stdout))
    assert "std.io" in require_names(selected_rules["app"]) and "std.io" not in selected_rules
    assert not (root / "never-cache").exists() and snapshot(profile) == profile_before
    no_preparation(scanned)


def main() -> int:
    """Run dependency discovery and external build integration.

    Returns:
        Zero when all discovery and composition assertions pass.
    """
    cc = preparation_c_compiler()
    assert cc
    env = dict(os.environ)
    for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="l1 dependency discovery ") as directory:
        root = Path(directory).resolve()
        compiler = toolchain_fixture(root, env)
        test_reports(root, env, compiler, cc)
        test_make(root, env, compiler, cc)
    print("L1 dependency discovery and Make composition: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
