#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Check and execute every lifted numeric widening supported by L1."""

from pathlib import Path
from tempfile import TemporaryDirectory

from l1c_compile_only_test import stage1_compiler, resolve_host_c_compiler, run_compiler
from support.driver_inputs import native_driver_args


DESTINATIONS = {
    "tiny": ("short", "int", "long"),
    "byte": ("short", "ushort", "int", "uint", "long", "ulong"),
    "short": ("int", "long"),
    "ushort": ("int", "uint", "long", "ulong"),
    "int": ("long",),
    "uint": ("long", "ulong"),
    "float": ("double",),
}

BOUNDARIES = {
    "tiny": ("-128", "0", "127"),
    "byte": ("0", "255"),
    "short": ("-32768", "0", "32767"),
    "ushort": ("0", "65535"),
    "int": ("-2147483648", "0", "2147483647"),
    "uint": ("0", "4294967295"),
    "float": ("-3.402823466e38f", "0.0f", "1.40129846e-45f", "3.402823466e38f"),
}


def matrix_program() -> str:
    """Generate typed calls covering every widening pair and source boundary.

    Returns:
        One program whose exit status identifies the first failed conversion.
    """
    functions = ["module matrix;", "import layers;"]
    checks = []
    for source, targets in DESTINATIONS.items():
        for i, value in enumerate(BOUNDARIES[source]):
            checks.append(f"let {source}_{i}: {source} = {value};")
        for target in targets:
            name = f"check_{source}_{target}"
            functions.append(f"""
func {name}(source: {source}?, present: bool, expected: {target}) -> bool {{
    let implicit: {target}? = source;
    let explicit = source as {target}?;
    if (!present) return implicit == null && explicit == null;
    if (implicit == null || explicit == null) return false;
    return (implicit as {target}) == expected && (explicit as {target}) == expected;
}}
""")
            error = len(functions)
            checks.append(f"if (!{name}(null, false, 0)) return {error};")
            for i in range(len(BOUNDARIES[source])):
                arg = f"{source}_{i}"
                checks.append(f"if (!{name}({arg}, true, {arg})) return {error};")
    body = "\n    ".join(checks)
    functions.append(f"func main() -> int {{\n    {body}\n    return layers::verify_layers();\n}}")
    return "\n".join(functions)


def main() -> None:
    """Run the native matrix and verify the diagnostics for forbidden conversions."""
    compiler = stage1_compiler()
    cc = resolve_host_c_compiler()
    fixtures = Path(__file__).resolve().parent / "fixtures" / "nullable_widening"
    with TemporaryDirectory(prefix="nullable-widening-") as tmp:
        root = Path(tmp)
        entry = root / "matrix.l1"
        entry.write_text(matrix_program(), encoding="utf-8")
        result = run_compiler(compiler, root, "--run", *native_driver_args(compiler, cc),
                              "--c-compiler", cc, "-Rp", str(fixtures), str(entry))
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
        rejected = run_compiler(compiler, root, "--check", str(fixtures / "rejected.l1"))
        assert rejected.returncode == 1, rejected.stderr
        assert rejected.stderr.count("[TYP-0310]") == 7, rejected.stderr
        assert "[TYP-0170]" in rejected.stderr, rejected.stderr
        assert "[TYP-0172]" in rejected.stderr, rejected.stderr
        assert "[TYP-0230]" in rejected.stderr, rejected.stderr


if __name__ == "__main__":
    main()
