#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Explicit native acceptance for private Stage 2 build-info overlays."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

L1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(L1_ROOT / "scripts"))
from build_stage2_l1c import build_compiler, compiler_build_env
from dea_tooling.bootstrap import wrapper_command


@unittest.skipUnless(os.environ.get("L1_PRODUCTIZATION_SEED"), "requires an explicit Stage 2 seed")
class Stage2BuildOverlayTests(unittest.TestCase):
    """Exercise the real self-build without replacing development artifacts."""

    def test_self_build_with_private_metadata(self):
        """The delivered generation embeds only the overlay and outlives its scratch."""
        seed = Path(os.environ["L1_PRODUCTIZATION_SEED"]).absolute()
        env, _ = compiler_build_env(dict(os.environ))
        initial_version = subprocess.check_output([*wrapper_command(seed), "--version"], env=env, text=True)
        self.assertIn("Dea language / L1 compiler (Stage 2)", initial_version)
        source_root = L1_ROOT / "compiler/stage2_l1/src"
        layout_root = Path(env.get("L1_BUILD_DIR", "build/dea"))
        if not layout_root.is_absolute():
            layout_root = L1_ROOT / layout_root
        paths = [*source_root.rglob("*.l1"), *sorted((layout_root / "bin").glob("*"))]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.is_file()}
        fallback = (source_root / "build_info.l1").read_text(encoding="utf-8")
        overlay_text = fallback.replace("return false;", "return true;", 1).replace(
            'return "unknown";', 'return "private-overlay-test";')
        with tempfile.TemporaryDirectory(prefix="l1 package overlay with spaces ") as temporary:
            root = Path(temporary)
            overlay = root / "metadata.l1"
            overlay.write_text(overlay_text, encoding="utf-8")
            # A broad project-root override would wrongly pick this sibling.
            (root / "l1c.l1").write_text("invalid sibling must not be compiled", encoding="utf-8")
            output = root / "bin/l1c-stage2.native"
            build_compiler(seed, output, env, keep_c=True, build_info_overlay=overlay)
            self.assertFalse(list(output.parent.glob("stage2-support-*")))
            self.assertTrue(Path(str(output) + ".dea-c").is_dir())
            overlay.unlink()
            version = subprocess.check_output([str(output), "--version"], cwd=root, env=env, text=True)
            self.assertEqual(version.strip().splitlines(), [
                "Dea language / L1 compiler (Stage 2) private-overlay-test",
                "build: private-overlay-test",
                "build time: private-overlay-test",
                "commit: private-overlay-test",
                "host: private-overlay-test",
                "compiler: private-overlay-test",
            ])
            hello = root / "overlay_smoke.l1"
            hello.write_text('module overlay_smoke;\nfunc main() -> int { return 0; }\n', encoding="utf-8")
            subprocess.run([str(output), "--check", str(hello)], cwd=root, env=env, check=True)
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before})
        self.assertEqual(initial_version, subprocess.check_output(
            [*wrapper_command(seed), "--version"], env=env, text=True))


if __name__ == "__main__":
    unittest.main()
