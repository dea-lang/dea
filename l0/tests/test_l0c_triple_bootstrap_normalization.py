#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Focused tests for Darwin triple-bootstrap native artifact normalization."""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import pytest

STAGE2_TEST_DIR = Path(__file__).resolve().parents[1] / "compiler" / "stage2_l0" / "tests"
if str(STAGE2_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE2_TEST_DIR))

import l0c_triple_bootstrap_test as triple_bootstrap


def thin_macho64(*commands: bytes, payload: bytes = b"native-code") -> bytes:
    """Return one synthetic little-endian 64-bit Mach-O binary."""

    command_table = b"".join(commands)
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x01000007,
        3,
        2,
        len(commands),
        len(command_table),
        0,
        0,
    )
    return header + command_table + payload


def uuid_command(value: bytes) -> bytes:
    """Return one synthetic ``LC_UUID`` command."""

    assert len(value) == 16
    return struct.pack("<II16s", 0x1B, 24, value)


def test_neutralize_darwin_uuid_removes_uuid_only(tmp_path: Path) -> None:
    """Different UUID metadata normalizes to identical Mach-O bytes."""

    left = tmp_path / "left.native.stripped"
    right = tmp_path / "right.native.stripped"
    left.write_bytes(thin_macho64(uuid_command(bytes(range(16)))))
    right.write_bytes(thin_macho64(uuid_command(bytes(reversed(range(16))))))

    triple_bootstrap.neutralize_darwin_uuid(left)
    triple_bootstrap.neutralize_darwin_uuid(right)

    assert left.read_bytes() == right.read_bytes()
    assert left.read_bytes()[40:56] == b"\0" * 16
    assert left.read_bytes().endswith(b"native-code")


def test_neutralize_darwin_uuid_preserves_uuid_free_macho(tmp_path: Path) -> None:
    """Mach-O binaries without ``LC_UUID`` remain byte-identical."""

    path = tmp_path / "uuid-free.native.stripped"
    command = struct.pack("<IIQQ", 0x80000028, 24, 0, 0)
    original = thin_macho64(command)
    path.write_bytes(original)

    triple_bootstrap.neutralize_darwin_uuid(path)

    assert path.read_bytes() == original


def test_neutralize_darwin_uuid_rejects_malformed_load_command(tmp_path: Path) -> None:
    """A load command extending beyond the declared table is rejected."""

    path = tmp_path / "malformed.native.stripped"
    path.write_bytes(thin_macho64(struct.pack("<II", 0x1B, 24)))

    with pytest.raises(triple_bootstrap.TripleBootstrapFailure, match="invalid Mach-O load command size"):
        triple_bootstrap.neutralize_darwin_uuid(path)


def test_darwin_normalization_strips_before_removing_signature(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Mach-O stripping runs while the original link-edit layout is intact."""

    source = tmp_path / "compiler.native"
    source.write_bytes(thin_macho64(uuid_command(bytes(range(16)))))
    events: list[str] = []

    def fake_strip(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        events.append("strip")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="")

    monkeypatch.setattr(triple_bootstrap.sys, "platform", "darwin")
    monkeypatch.setattr(triple_bootstrap, "resolve_strip_command", lambda: ["strip"])
    monkeypatch.setattr(triple_bootstrap.subprocess, "run", fake_strip)
    monkeypatch.setattr(
        triple_bootstrap,
        "_remove_darwin_code_signature",
        lambda path: events.append("remove-signature"),
    )
    monkeypatch.setattr(
        triple_bootstrap,
        "neutralize_darwin_uuid",
        lambda path: events.append("neutralize-uuid"),
    )

    triple_bootstrap.normalized_native_artifact(source, tmp_path)

    assert events == ["strip", "remove-signature", "neutralize-uuid"]
