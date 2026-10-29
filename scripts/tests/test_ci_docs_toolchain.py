# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Fast, mocked checks for bounded Ubuntu documentation package setup."""

import importlib.util
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / ".github/actions/setup-docs-toolchain"
SPEC = importlib.util.spec_from_file_location("ci_docs_toolchain", ACTION / "install.py")
toolchain = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(toolchain)


@pytest.fixture
def commands(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["check"] is True
        if command[:2] == ["sudo", "tee"]:
            Path(command[2]).write_bytes(kwargs["input"])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(toolchain.subprocess, "run", run)
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: f"/mock/bin/{name}")
    return calls


@pytest.mark.parametrize("relative", [
    "sources.list", "sources.list.d/ubuntu.list", "sources.list.d/ubuntu.sources", "apt-mirrors.txt",
])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_mirror_rewrite_preserves_sources_and_signing(tmp_path, commands, relative, scheme):
    root = tmp_path / "apt config with spaces"
    source = root / relative
    source.parent.mkdir(parents=True)
    old = f"{scheme}://azure.archive.ubuntu.com/ubuntu".encode()
    if source.name == "apt-mirrors.txt":
        original = (old + b"/\tpriority:1\n"
                    b"https://archive.ubuntu.com/ubuntu/\tpriority:2\n"
                    b"https://security.ubuntu.com/ubuntu/\tpriority:3\n")
    elif source.suffix == ".sources":
        original = (b"Types: deb\r\nURIs: " + old + b"/\r\nSuites: noble noble-updates\r\n"
                    b"Components: main restricted universe\r\n"
                    b"Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\r\n\r\n"
                    b"Types: deb\r\nURIs: http://security.ubuntu.com/ubuntu/\r\nSuites: noble-security\r\n")
    else:
        original = (b"deb [arch=amd64 signed-by=/keys/ubuntu.gpg] " + old + b" noble main universe\n"
                    b"deb https://security.ubuntu.com/ubuntu noble-security main\n"
                    b"deb https://packages.example.com/ubuntu noble main\n")
    source.write_bytes(original)
    toolchain.configure_mirror(root)
    assert source.read_bytes() == original.replace(old, b"https://archive.ubuntu.com/ubuntu")
    assert len(commands) == 1
    assert commands[0][0] == ["sudo", "tee", str(source)]
    toolchain.configure_mirror(root)
    assert len(commands) == 1


def test_hosted_runner_mirror_indirection_keeps_source_configuration(tmp_path, commands):
    sources = tmp_path / "sources.list.d/ubuntu.sources"
    sources.parent.mkdir()
    original = (b"Types: deb\nURIs: mirror+file:/etc/apt/apt-mirrors.txt\n"
                b"Suites: noble noble-updates noble-backports noble-security\n"
                b"Components: main universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n")
    sources.write_bytes(original)
    mirrors = tmp_path / "apt-mirrors.txt"
    mirrors.write_bytes(b"http://azure.archive.ubuntu.com/ubuntu/\tpriority:1\n"
                       b"https://archive.ubuntu.com/ubuntu/\tpriority:2\n"
                       b"https://security.ubuntu.com/ubuntu/\tpriority:3\n")
    toolchain.configure_mirror(tmp_path)
    assert sources.read_bytes() == original
    assert mirrors.read_bytes() == (b"https://archive.ubuntu.com/ubuntu/\tpriority:1\n"
                                    b"https://archive.ubuntu.com/ubuntu/\tpriority:2\n"
                                    b"https://security.ubuntu.com/ubuntu/\tpriority:3\n")
    assert [call[0] for call in commands] == [["sudo", "tee", str(mirrors)]]


@pytest.mark.parametrize("url", [
    "https://archive.ubuntu.com/ubuntu",
    "https://security.ubuntu.com/ubuntu",
    "https://azure.archive.ubuntu.com.evil.example/ubuntu",
    "https://azure.archive.ubuntu.com/ubuntu-ports",
])
def test_other_source_urls_are_unchanged(tmp_path, commands, url):
    source = tmp_path / "sources.list"
    content = f"deb {url} noble main\n".encode()
    source.write_bytes(content)
    toolchain.configure_mirror(tmp_path)
    assert source.read_bytes() == content
    assert commands == []


def test_only_apt_source_files_are_rewritten(tmp_path, commands):
    extra = tmp_path / "sources.list.d"
    extra.mkdir()
    ignored = extra / "notes.txt"
    ignored.write_bytes(b"http://azure.archive.ubuntu.com/ubuntu")
    for relative in ("sources.list", "sources.list.d/ubuntu.list", "sources.list.d/ubuntu.sources", "apt-mirrors.txt"):
        (tmp_path / relative).write_bytes(b"http://azure.archive.ubuntu.com/ubuntu")
    toolchain.configure_mirror(tmp_path)
    assert len(commands) == 4
    assert ignored.read_bytes() == b"http://azure.archive.ubuntu.com/ubuntu"


@pytest.mark.parametrize("build_pdf", [False, True])
def test_installation_bounds_fetches_and_selects_required_tools(tmp_path, commands, build_pdf):
    toolchain.install_toolchain(build_pdf, apt_root=tmp_path)
    assert len(commands) == 2
    for command, _ in commands:
        assert command[:4] == ["sudo", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get"]
        for option in ("Acquire::Retries=3", "Acquire::http::Timeout=30", "Acquire::https::Timeout=30"):
            index = command.index(option)
            assert command[index - 1] == "-o"
    assert commands[0][0][-2:] == ["update", "--error-on=any"]
    expected = ["install", "-y", "graphviz", "make", "texlive-font-utils", "ghostscript"]
    if build_pdf:
        expected += ["texlive-latex-recommended", "texlive-latex-extra", "texlive-fonts-recommended"]
    command = commands[1][0]
    assert command[command.index("install"):] == expected


@pytest.mark.parametrize("build_pdf", [False, True])
@pytest.mark.parametrize("missing", ["epstopdf", "gs"])
def test_eps_conversion_commands_are_required_before_optional_pdf_build(tmp_path, commands, monkeypatch, build_pdf, missing):
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: None if name == missing else f"/mock/bin/{name}")
    with pytest.raises(RuntimeError, match=missing):
        toolchain.install_toolchain(build_pdf, apt_root=tmp_path)
    assert len(commands) == 2


@pytest.mark.parametrize("build_pdf", [False, True])
def test_full_pdf_commands_are_only_required_for_pdf_compilation(tmp_path, commands, monkeypatch, build_pdf):
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: None if name in {"pdflatex", "makeindex"} else f"/mock/bin/{name}")
    if build_pdf:
        with pytest.raises(RuntimeError, match="pdflatex, makeindex"):
            toolchain.install_toolchain(True, apt_root=tmp_path)
    else:
        toolchain.install_toolchain(False, apt_root=tmp_path)


def test_action_reports_missing_commands_as_setup_failure(monkeypatch, capsys):
    monkeypatch.setattr(toolchain.sys, "platform", "linux")
    monkeypatch.setattr(toolchain.sys, "argv", ["install.py"])

    def missing_tools(build_pdf):
        raise RuntimeError("Documentation toolchain is missing required commands: epstopdf")

    monkeypatch.setattr(toolchain, "install_toolchain", missing_tools)
    assert toolchain.main() == 1
    assert "missing required commands: epstopdf" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["tee", "update", "install"])
def test_failures_stop_setup_without_command_retry_loops(tmp_path, monkeypatch, failure):
    (tmp_path / "sources.list").write_bytes(b"http://azure.archive.ubuntu.com/ubuntu")
    calls = []

    def run(command, **kwargs):
        operation = next(item for item in ("tee", "update", "install") if item in command)
        calls.append(operation)
        if operation == failure:
            raise subprocess.CalledProcessError(100, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(toolchain.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        toolchain.install_toolchain(True, apt_root=tmp_path)
    assert calls == ["tee", "update", "install"][:["tee", "update", "install"].index(failure) + 1]


@pytest.mark.parametrize("choice,expected", [("true", True), ("false", False)])
def test_action_cli_preserves_pdf_choice(monkeypatch, choice, expected):
    calls = []
    monkeypatch.setattr(toolchain.sys, "platform", "linux")
    monkeypatch.setattr(toolchain.sys, "argv", ["install.py", "--build-pdf", choice])
    monkeypatch.setattr(toolchain, "install_toolchain", lambda build_pdf: calls.append(build_pdf))
    assert toolchain.main() == 0
    assert calls == [expected]


@pytest.mark.parametrize("filename,job", [
    ("l0-docs-build.yml", "build-docs"),
    ("l0-docs-validate.yml", "validate-docs"),
    ("l1-docs-build.yml", "build-docs"),
    ("l1-docs-validate.yml", "validate-docs"),
    ("l1-productization-acceptance.yml", "docs"),
])
def test_every_docs_producer_uses_bounded_setup(filename, job):
    data = yaml.load((ROOT / ".github/workflows" / filename).read_text(), Loader=yaml.BaseLoader)
    selected = data["jobs"][job]
    assert selected["runs-on"] == "ubuntu-26.04"
    steps = selected["steps"]
    setup = [item for item in steps if item.get("uses") == "./.github/actions/setup-docs-toolchain"]
    assert len(setup) == 1
    assert setup[0]["timeout-minutes"] == "15"
    assert "continue-on-error" not in setup[0]
    python = next(item for item in steps if item.get("uses", "").startswith("actions/setup-python@"))
    doxygen = next(item for item in steps if item.get("uses") == "./.github/actions/setup-doxygen")
    assert steps.index(python) < steps.index(setup[0]) < steps.index(doxygen)
    assert not any("apt-get" in item.get("run", "") for item in steps)
    if filename == "l0-docs-build.yml":
        assert setup[0]["with"]["build_pdf"] == "${{ inputs.build_pdf }}"
    else:
        assert setup[0].get("with", {}).get("build_pdf", "true") == "true"
    if filename == "l0-docs-validate.yml":
        diagnostics = next(item for item in steps if item.get("name") == "Upload documentation failure logs")
        assert diagnostics["if"] == "failure()"
        assert diagnostics["with"]["path"] == "l0/build/docs/*-failure/**/*.log"
        assert diagnostics["with"]["include-hidden-files"] == "true"
        assert diagnostics["with"]["if-no-files-found"] == "warn"


def test_shared_action_passes_pdf_selection_and_is_in_ci_checks():
    action = yaml.load((ACTION / "action.yml").read_text(), Loader=yaml.BaseLoader)
    assert action["inputs"]["build_pdf"]["default"] == "true"
    install = action["runs"]["steps"][0]
    assert install["env"]["BUILD_PDF"] == "${{ inputs.build_pdf }}"
    assert install["run"] == 'python3 "$GITHUB_ACTION_PATH/install.py" --build-pdf "$BUILD_PDF"'
    report = action["runs"]["steps"][1]
    assert report["env"]["BUILD_PDF"] == "${{ inputs.build_pdf }}"
    assert report["run"] == 'python3 "$GITHUB_ACTION_PATH/install.py" --report-versions --build-pdf "$BUILD_PDF"'
    makefile = (ROOT / "Makefile").read_text()
    for name in ("test", "test-extended"):
        target = makefile.split(f"{name}: _check-level-dirs venv\n", 1)[1].split("\n\n", 1)[0]
        assert "-m pytest -q -n 0 scripts/tests" in target


@pytest.mark.parametrize("build_pdf", [False, True])
def test_version_reporting_uses_active_table_package_and_respects_pdf_choice(tmp_path, commands, monkeypatch, capsys, build_pdf):
    package = tmp_path / "tex installation with spaces" / "tabularray.sty"
    package.parent.mkdir()
    package.write_text(r"\ProvidesExplPackage{tabularray}{2025-11-27}{2025C}")
    queries = []

    def query(command, **kwargs):
        queries.append(command)
        return str(package) + "\n"

    monkeypatch.setattr(toolchain.subprocess, "check_output", query)
    toolchain.report_versions(build_pdf)
    package_query = commands[0][0]
    assert package_query[:3] == ["dpkg-query", "--show", "--showformat=${Package} ${Version}\\n"]
    assert "texlive-binaries" in package_query
    assert ("texlive-latex-extra" in package_query) == build_pdf
    assert (["pdflatex", "--version"] in [command for command, _ in commands]) == build_pdf
    assert queries == ([["kpsewhich", "tabularray.sty"]] if build_pdf else [])
    output = capsys.readouterr().out
    assert ("tabularray 2025-11-27 2025C:" in output) == build_pdf
    assert all(command[:2] != ["makeindex", "--version"] for command, _ in commands)


@pytest.mark.parametrize("choice,expected", [("true", True), ("false", False)])
def test_version_report_cli_does_not_reinstall(monkeypatch, choice, expected):
    calls = []
    monkeypatch.setattr(toolchain.sys, "platform", "linux")
    monkeypatch.setattr(toolchain.sys, "argv", ["install.py", "--report-versions", "--build-pdf", choice])
    monkeypatch.setattr(toolchain, "report_versions", lambda build_pdf: calls.append(build_pdf))
    monkeypatch.setattr(toolchain, "install_toolchain", lambda *args: pytest.fail("unexpected APT installation"))
    assert toolchain.main() == 0
    assert calls == [expected]


def test_version_report_errors_fail_the_action(monkeypatch, capsys):
    monkeypatch.setattr(toolchain.sys, "platform", "linux")
    monkeypatch.setattr(toolchain.sys, "argv", ["install.py", "--report-versions"])

    def fail(build_pdf):
        raise RuntimeError("Cannot identify tabularray version")

    monkeypatch.setattr(toolchain, "report_versions", fail)
    assert toolchain.main() == 1
    assert "Cannot identify tabularray version" in capsys.readouterr().err
