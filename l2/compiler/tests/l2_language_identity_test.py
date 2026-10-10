#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Exercise L2 identities, strict file suffixes, and owned separate compilation."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
from l2c_compile_only_test import subject_compiler, L2_ROOT


def main() -> int:
    """Validate public L2 conventions using only the already-built target compiler."""
    compiler = subject_compiler()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("L0_", "L1_"))}
    env.update(L2_HOME=str(L2_ROOT / "compiler"), L2_BUILD_DIR=str(compiler.parent.parent))
    with tempfile.TemporaryDirectory(prefix="l2-language-identity-") as temporary:
        root = Path(temporary)
        def run(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
            result = subprocess.run([str(compiler), *args], cwd=root, env=env,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
            return result
        version = run("--version").stdout
        assert version.startswith("Dea language / L2 compiler") and "Stage" not in version, version
        help_text = run("--help").stdout
        assert "l2c" in help_text and ".l2m" in help_text and "L2_STDLIB_CACHE" in help_text
        (root / "hello.l2").write_text('module hello;\nimport std.io;\nfunc main() -> int { printl_s("L2 owned runtime"); return 0; }\n')
        assert run("--run", "hello.l2").stdout == "L2 owned runtime\n"
        (root / "pkg").mkdir()
        (root / "pkg/entry.l2").write_text('module pkg.entry;\nfunc main() -> int { return 0; }\n')
        run("--run", "pkg.entry")
        # Existing suffixless outputs must not change logical entry resolution.
        (root / "hello").write_text("existing extensionless build output")
        executable = root / ("hello.exe" if os.name == "nt" else "hello")
        run("--build", "hello", "-o", str(executable))
        run("--build", "hello", "-o", str(executable))
        for suffix in (".l0", ".l1", ".txt", ".l2m", ".L2", ""):
            wrong = root / ("invalid" + suffix)
            wrong.write_text('module invalid;\nfunc main() -> int { return 0; }\n')
            result = run("--check", str(wrong), ok=False)
            assert "L2C-0011" in result.stderr and "'.l2'" in result.stderr, result.stderr
            wrong.unlink()
        # Existing suffixed files take precedence over matching dotted modules.
        (root / "bad").mkdir()
        for suffix in ("l1", "txt"):
            (root / f"bad.{suffix}").write_text("wrong source suffix")
            (root / f"bad/{suffix}.l2").write_text(f"module bad.{suffix};\n")
            rejected = run("--check", f"bad.{suffix}", ok=False)
            assert "L2C-0011" in rejected.stderr
        (root / "pkg/entry.l1").write_text('module pkg.entry;\n')
        rejected = run("--check", "pkg/entry.l1", ok=False)
        assert "L2C-0011" in rejected.stderr
        (root / "provider.l2").write_text('module provider;\nfunc answer() -> int { return 42; }\n')
        (root / "main.l2").write_text('module main;\nimport provider;\nfunc main() -> int { return answer() - 42; }\n')
        run("--compile", "provider", "-o", str(root / "provider.o"))
        assert (root / "provider.l2m").is_file() and not (root / "provider.l1m").exists()
        # Verify interface consumption rather than falling back to provider source.
        (root / "provider.l2").unlink()
        run("--compile", "-I", str(root), "main", "-o", str(root / "main.o"))
        output = root / ("linked.exe" if os.name == "nt" else "linked")
        run("--link", str(root / "main.o"), str(root / "provider.o"), "-o", str(output))
        result = subprocess.run([str(output)], capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stderr
        (root / "provider.l2m").rename(root / "provider.l1m")
        run("--check", "-I", str(root), "main", ok=False)
    print("l2_language_identity_test: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
