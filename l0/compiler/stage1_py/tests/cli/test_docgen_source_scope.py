# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for the docs source manifest."""

from pathlib import Path

from compiler.docgen.l0_docgen import build_source_manifest


def test_docgen_source_manifest_includes_expected_roots() -> None:
    repo = Path(__file__).resolve().parents[4]
    manifest = build_source_manifest(repo)
    files = {path.as_posix() for path in manifest.files}

    assert "compiler/stage1_py/l0_analysis.py" in files
    assert "compiler/stage2_l0/src/analysis.l0" in files
    assert "compiler/stage2_l0/scripts/check_trace_log.py" in files
    assert "compiler/shared/l0/stdlib/std/io.l0" in files
    assert "compiler/shared/runtime/dea_rt.h" in files
    assert "compiler/shared/runtime/l0_runtime.h" in files


def test_docgen_source_manifest_excludes_tests_docs_and_examples() -> None:
    repo = Path(__file__).resolve().parents[4]
    manifest = build_source_manifest(repo)
    files = {path.as_posix() for path in manifest.files}

    assert "compiler/stage1_py/tests/cli/test_cli_mode_flags.py" not in files
    assert "compiler/docgen/l0_docgen.py" not in files
    assert "compiler/stage2_l0/tests/parser_test.l0" not in files
    assert "docs/reference/architecture.md" not in files
    assert "examples/hello.l0" not in files
    assert not any(path.startswith("compiler/docgen/") for path in files)
