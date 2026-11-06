#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Public L1 byte-buffer behavior, opacity, and deterministic limit failures."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from os_runtime_test import L1_ROOT, compiler_path, require_success, runtime_c_compiler
from support.driver_inputs import native_driver_args


FIXTURES = L1_ROOT / "compiler/tests/fixtures/bytes"
SOURCE = L1_ROOT / "compiler/shared/l1/stdlib/std/bytes.l1"
FAILURES = {
    "negative_capacity": ('bytes::with_capacity(-1);', "negative capacity"),
    "negative_reserve": ('bytes::reserve(buf, -1);', "negative capacity"),
    "negative_resize": ('bytes::resize(buf, -1);', "negative length"),
    "negative_get": ('bytes::get(buf, -1);', "index out of bounds"),
    "past_get": ('bytes::get(buf, 2);', "index out of bounds"),
    "past_set": ('bytes::set(buf, 2, 0 as byte);', "index out of bounds"),
    "cleared_get": ('bytes::clear(buf); bytes::get(buf, 0);', "index out of bounds"),
    "range_start": ('bytes::append_range(buf, input, -1, 1);', "source range out of bounds"),
    "range_count": ('bytes::append_range(buf, input, 0, -1);', "source range out of bounds"),
    "range_tail": ('bytes::append_range(buf, input, 1, 2);', "source range out of bounds"),
    "range_empty": ('bytes::append_range(buf, input, 3, 0);', "source range out of bounds"),
    "range_overflow": ('bytes::append_range(buf, input, 1, 2147483647);', "source range out of bounds"),
}


def build(work: Path, name: str, cc: str, flags: list[str], *, root: Path | None = None) -> Path:
    """Compile an actual L1 target against the owned source stdlib.

    Args:
        work: Destination for the native program.
        name: Logical source module name.
        cc: Selected native compiler.
        flags: Runtime mode arguments.
        root: Source root, defaulting to work.

    Returns:
        Path to the executable.

    Raises:
        AssertionError: Compilation fails.
    """
    compiler = compiler_path()
    executable = work / (name + (".exe" if os.name == "nt" else ""))
    require_success([
        str(compiler), "--project-root", str(root or work), "--c-compiler", cc,
        *native_driver_args(compiler, cc), *flags, "--build", name, "-o", str(executable),
    ], timeout=240)
    return executable


def require_failure(executable: Path, case: str, message: str) -> None:
    """Require a contract panic rather than successful execution or a host crash.

    Args:
        executable: Built L1 probe.
        case: Selected branch in its main function.
        message: Expected std.bytes assertion message.

    Raises:
        AssertionError: The program succeeds or omits the expected diagnostic.
    """
    completed = subprocess.run(
        [str(executable), case], cwd=L1_ROOT, capture_output=True, text=True, timeout=60, check=False,
    )
    assert completed.returncode != 0, f"{case} unexpectedly succeeded"
    assert f"std.bytes: {message}" in completed.stderr, (case, completed.stdout, completed.stderr)


def failure_source() -> str:
    """Construct one public consumer containing all independently selected failures.

    Returns:
        L1 source using only exported byte-buffer operations.
    """
    branches = "\n".join(
        f'if (argv(1) == "{name}") {{ {body} }}' for name, (body, _) in FAILURES.items()
    )
    return f"""module bytes_failures;
import std.bytes as bytes;
import std.system;
/**
 * Select one invalid public operation for a separately observed failure.
 */
func main() {{
    with (let buf = bytes::with_capacity(8) => bytes::free(buf)) {{
        bytes::resize(buf, 2);
        let input: byte[2] = [1 as byte, 2 as byte];
        {branches}
    }}
}}
"""


def limit_source() -> str:
    """Add a same-module white-box harness to unchanged production definitions.

    Synthetic lengths test int boundaries without allocating gigabytes. Local
    allocator shims inject failures and observe requests before delegating to
    the real runtime. No synthetic large range is ever accessed.

    Returns:
        Production byte-buffer source with test-only imports and declarations.
    """
    source = SOURCE.read_text(encoding="utf-8").replace("module std.bytes;", "module bytes_limits;")
    source = source.replace("to_string, from_string;", "to_string, from_string, main;")
    source = source.replace("import sys.memory;", "import sys.memory;\nimport sys.memory as memory;\nimport std.system;")
    return source + r'''

let fault: int = 0;
let allocation_calls: int = 0;

/**
 * Inject an allocation failure or delegate a small real allocation.
 *
 * @param count Requested byte extent.
 * @return Real storage, or null for the selected failure.
 */
func rt_alloc(count: int) -> void*? {
    allocation_calls = allocation_calls + 1;
    assert(count > 0 && count < 1024, "unexpected large allocation");
    if (fault == 1) { return null; }
    return memory::rt_alloc(count);
}

/**
 * Inject realloc failure or inspect saturation without allocating large storage.
 *
 * @param data Existing small real allocation.
 * @param count Requested byte extent.
 * @return Storage for the selected simulation, or the real resized allocation.
 */
func rt_realloc(data: void*?, count: int) -> void*? {
    allocation_calls = allocation_calls + 1;
    if (fault == 2) { return null; }
    if (fault == 3) {
        assert(count == int_max(), "growth must saturate without signed overflow");
        return data;
    }
    assert(count > 0 && count < 1024, "unexpected large reallocation");
    return memory::rt_realloc(data, count);
}

/**
 * Probe the production append and growth guards before any large memory access.
 */
func main() {
    if (argv(1) == "alloc_failure") { fault = 1; create(); return; }
    with (let buf = create() => free(buf), let other = with_capacity(2) => free(other)) {
        if (argv(1) == "realloc_failure") { fault = 2; reserve(buf, 2); return; }
        if (argv(1) == "saturation") {
            buf._capacity = int_max() / 2 + 1;
            fault = 3;
            reserve(buf, buf._capacity + 1);
            assert(capacity(buf) == int_max() && size(buf) == 0, "saturated capacity");
            let before = allocation_calls;
            reserve(buf, int_max());
            assert(allocation_calls == before, "no allocation for sufficient capacity");
            buf._length = int_max() - 2;
            assert(_append_length(buf, 2) == int_max(), "exact maximum append length");
            assert(_append_length(buf, 0) == int_max() - 2, "zero append at limit");
            return;
        }
        buf._length = int_max();
        if (argv(1) == "overflow_byte") { append_byte(buf, 1 as byte); }
        if (argv(1) == "overflow_buffer") { resize(other, 2); append_buffer(buf, other); }
        if (argv(1) == "overflow_range") {
            let input: byte[1] = [1 as byte];
            append_range(buf, input, 0, 1);
        }
    }
}
'''


def require_public_interface(work: Path) -> None:
    """Check the public size API and opacity through source and interface imports.

    Args:
        work: Temporary consumer and interface directory.

    Raises:
        AssertionError: The public API, diagnostic, or opacity contract fails.
    """
    compiler = compiler_path()
    source_args = ["--no-managed-stdlib", "--sys-root", str(L1_ROOT / "compiler/shared/l1/stdlib")]
    interfaces = work / "interfaces"
    (interfaces / "std").mkdir(parents=True)
    interface = interfaces / "std/bytes.l1m"
    require_success(
        [str(compiler), *source_args, "--emit-interface", "std.bytes", "-o", str(interface)], timeout=120,
    )
    text = interface.read_text(encoding="utf-8")
    assert "func size(" in text, text
    assert "opaque struct ByteBuffer;" in text, text
    assert "struct ByteBuffer {" not in text, text
    assert "func _check_index(" not in text and "func _append_length(" not in text, text
    for label, operation in (
        ("field", "let hidden = buf._data;"),
        ("layout_size", "let size = sizeof(bytes::ByteBuffer);"),
        ("drop", "drop buf;"),
        ("construct", "let forged = new bytes::ByteBuffer();"),
        ("dereference", "let copied = *buf;"),
    ):
        name = f"buffer_{label}"
        (work / f"{name}.l1").write_text(
            f"module {name};\nimport std.bytes as bytes;\n"
            "/**\n * Attempt an operation outside the public buffer API.\n */\n"
            f"func main() {{ let buf = bytes::create(); {operation} bytes::free(buf); }}\n",
            encoding="utf-8",
        )
        for interface_args in ([], ["-I", str(interfaces)]):
            completed = subprocess.run([
                str(compiler), *source_args, *interface_args, "--project-root", str(work),
                "--gen", name, "-o", str(work / f"{name}.c"),
            ], cwd=L1_ROOT, capture_output=True, text=True, timeout=120, check=False)
            assert completed.returncode == 1, (name, completed.stdout, completed.stderr)
            assert "[RES-0038]" in completed.stderr, (name, completed.stderr)


def main() -> int:
    """Run public and white-box contracts in checked and unchecked runtime modes.

    Returns:
        Zero when every behavior and opacity assertion passes.

    Raises:
        AssertionError: A compilation, execution, or diagnostic contract fails.
    """
    cc = runtime_c_compiler()
    with tempfile.TemporaryDirectory(prefix="l1-bytes-") as temporary:
        work = Path(temporary)
        (work / "bytes_failures.l1").write_text(failure_source(), encoding="utf-8")
        (work / "bytes_limits.l1").write_text(limit_source(), encoding="utf-8")
        for mode, flags in (("checked", []), ("unchecked", ["--unchecked"])):
            real = build(work, "bytes_main", cc, flags, root=FIXTURES)
            result = require_success([str(real)], timeout=60)
            assert result.stdout == "bytes_main: PASS\n" and result.stderr == "", result
            failing = build(work, "bytes_failures", cc, flags)
            for case, (_, message) in FAILURES.items():
                require_failure(failing, case, message)
            limits = build(work, "bytes_limits", cc, flags)
            require_success([str(limits), "saturation"], timeout=60)
            for case in ("alloc_failure", "realloc_failure"):
                require_failure(limits, case, "allocation failed")
            for case in ("overflow_byte", "overflow_buffer", "overflow_range"):
                require_failure(limits, case, "length overflow")
            print(f"bytes_test: {mode} PASS")
        require_public_interface(work)
    print("bytes_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
