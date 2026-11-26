# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Run the conditional-lvalue fixture against an L0-implemented emitter."""

from collections.abc import Sequence
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


def check_deref_lvalue(
    module: str, emitter_command: Sequence[str | Path], cc: str, target_command: Sequence[str | Path], suffix: str,
) -> None:
    """Compile the emitter's actual C expression and run a checked source-language control.

    Args:
        module: L0 module defining the target emitter helper.
        emitter_command: L0 run command with the target compiler's import and support paths.
        cc: Selected host C compiler.
        target_command: Native run command for the target language.
        suffix: Source extension accepted by the target compiler.
    """
    fixtures = Path(__file__).resolve().parent
    with TemporaryDirectory(prefix="deref-lvalue-") as tmp:
        work = Path(tmp)
        probe = work / "render.l0"
        probe.write_text(
            f"module render; import std.io; import {module};\n"
            'func main() { printl_s(cem_emit_deref_lvalue("take_a ? a : b")); }\n',
            encoding="utf-8",
        )
        lvalue = subprocess.check_output([*emitter_command, str(probe)], text=True).strip()
        template = (fixtures / "conditional.c.in").read_text(encoding="utf-8")
        (work / "conditional.c").write_text(template.replace("@LVALUE@", lvalue), encoding="utf-8")
        if Path(cc).stem.lower() in {"cl", "clang-cl"}:
            flags = ["/std:c11", "/Fe:conditional.exe"]
        else:
            flags = ["-std=c99", "-o", "conditional.exe"]
        subprocess.run([cc, "conditional.c", *flags], cwd=work, check=True)
        subprocess.run([str(work / "conditional.exe")], cwd=work, check=True)

        checked = work / f"checked{suffix}"
        shutil.copyfile(fixtures / "checked.l0", checked)
        subprocess.run([*target_command, str(checked)], check=True)
