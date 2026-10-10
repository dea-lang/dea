#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Explicit native acceptance for private canonical compiler build-info overlays."""

import hashlib
import json
import shutil
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

L1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(L1_ROOT / "scripts"))
from build_l1c import build_compiler, compiler_build_env
from dea_tooling.bootstrap import wrapper_command
from productization_provenance import collect_provenance
from productization_inventory import MANIFEST_PATH, install_payload
from productization_payload import build_payload


@unittest.skipUnless(os.environ.get("L1_PRODUCTIZATION_COMPILER"), "requires an explicit canonical L1 compiler")
class CompilerBuildOverlayTests(unittest.TestCase):
    """Exercise the real upstream compiler build without replacing development artifacts."""

    def test_build_with_private_metadata(self):
        """The delivered generation embeds only the overlay and outlives its scratch."""
        compiler = Path(os.environ["L1_PRODUCTIZATION_COMPILER"]).absolute()
        env, _ = compiler_build_env(dict(os.environ))
        upstream = Path(env.get("L1_BOOTSTRAP_L0C", str(L1_ROOT.parent / "l0/build/dea/bin/l0c-stage2")))
        env["L1_HOME"] = str(L1_ROOT / "compiler")
        initial_version = subprocess.check_output([*wrapper_command(compiler), "--version"], env=env, text=True)
        self.assertIn("Dea language / L1 compiler", initial_version)
        source_root = L1_ROOT / "compiler/src"
        layout_root = Path(env.get("L1_BUILD_DIR", "build/dea"))
        if not layout_root.is_absolute():
            layout_root = L1_ROOT / layout_root
        paths = [*source_root.rglob("*.l0"), *sorted((layout_root / "bin").glob("*"))]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.is_file()}
        inputs = {"include/dea_rt.h": hashlib.sha256(
            (L1_ROOT / "compiler/shared/runtime/include/dea_rt.h").read_bytes()).hexdigest()}
        provenance, env = collect_provenance(
            L1_ROOT, env | {"DEA_DIST_VERSION": "private-overlay-test"},
            upstream=Path(env.get("L1_BOOTSTRAP_L0C", str(L1_ROOT.parent / "l0/build/dea/bin/l0c-stage2"))),
            compiler=compiler,
            compiler_options=[], preparation_inputs=inputs)
        metadata = provenance.metadata()
        evidence = metadata["provenance"]
        overlay_text = provenance.build_info_module()
        with tempfile.TemporaryDirectory(prefix="l1 package overlay with spaces ") as temporary:
            root = Path(temporary)
            overlay = root / "metadata.l0"
            overlay.write_text(overlay_text, encoding="utf-8")
            # A broad project-root override would wrongly pick this sibling.
            (root / "l1c.l0").write_text("invalid sibling must not be compiled", encoding="utf-8")
            output = root / "bin/l1c.native"
            build_compiler(upstream, output, env, keep_c=True, build_info_overlay=overlay)
            self.assertFalse(list(output.parent.glob("l1-build-*")))
            self.assertTrue(output.with_suffix(".c").is_file())
            overlay.unlink()
            version = subprocess.check_output([str(output), "--version"], cwd=root, env=env, text=True)
            self.assertEqual(version.strip().splitlines(), [
                "Dea language / L1 compiler private-overlay-test",
                f'build: {evidence["build_id"]}',
                f'build time: {evidence["build_time"]}',
                'commit: ' + evidence["source"]["revision"] +
                ("+dirty" if evidence["source"]["tree_state"] == "dirty" else ""),
                f'host: {metadata["os"]}-{metadata["arch"]}',
                "maturity: development",
                f'compiler: {evidence["native_compiler"]["version"].splitlines()[0]}',
            ])
            hello = root / "overlay_smoke.l1"
            hello.write_text('module overlay_smoke;\nfunc main() -> int { return 0; }\n', encoding="utf-8")
            subprocess.run([str(output), "--check", str(hello)], cwd=root, env=env, check=True)
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before})
        self.assertEqual(initial_version, subprocess.check_output(
            [*wrapper_command(compiler), "--version"], env=env, text=True))

    def test_installed_startup_before_all_commands(self):
        """A real marked compiler derives its prefix and fails closed without metadata."""
        compiler = Path(os.environ["L1_PRODUCTIZATION_COMPILER"]).absolute()
        env, _ = compiler_build_env(dict(os.environ))
        layout = compiler.parent.parent
        with tempfile.TemporaryDirectory(prefix="l1 installed startup ") as temporary, build_payload(
                L1_ROOT, layout, compiler, env | {"DEA_DIST_VERSION": "installed-guard-test"},
                upstream=Path(env.get("L1_BOOTSTRAP_L0C", str(L1_ROOT.parent / "l0/build/dea/bin/l0c-stage2"))),
                compiler_options=[]) as (payload, provenance):
            self.assertGreater((payload.parent / "verify-installed.c").stat().st_size, 0)
            self.assertFalse((payload / MANIFEST_PATH).exists())
            command = provenance.metadata()["provenance"]["installed_compiler_command"]
            self.assertEqual(command[command.index("-o") + 1], str(payload / "bin/l1c.native"))
            self.assertEqual(command.count("--project-root"), 2)
            overlay_root = Path(command[command.index("--project-root") + 1])
            self.assertEqual(overlay_root.name, "build-info")
            self.assertFalse(overlay_root.exists())
            self.assertEqual({Path(command[index + 1]).name for index, argument in enumerate(command)
                              if argument == "--c-source"},
                             {"interface_fingerprint.c", "compiler_support.c", "preparation_support.c"})
            root = Path(temporary)
            prefix = root / "prefix"
            record = install_payload(payload, prefix, provenance.metadata())
            relocated = root / "relocated prefix with spaces"
            prefix.rename(relocated)
            child_env = {**env, "L1_HOME": str(root / "absent-repo"), "L1_BUILD_DIR": str(root / "absent-build")}
            for name in ("L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB"):
                child_env.pop(name, None)
            # Keep only the shell directory available to POSIX launchers; native
            # help/version/check/gen must not invoke Python, Make, or a C compiler.
            shell_bin = root / "shell-bin"
            shell_bin.mkdir()
            if os.name != "nt":
                for name in ("sh", "dirname"):
                    (shell_bin / name).symlink_to(shutil.which(name))
            child_env["PATH"] = str(shell_bin)
            entries = [relocated / "bin/l1c.native",
                       relocated / "bin" / ("l1c.cmd" if os.name == "nt" else "l1c")]
            source = root / "hello.l1"
            shutil.copyfile(relocated / "share/dea/l1/smoke/hello.l1", source)

            def invoke(entry, args, expected=0):
                result = subprocess.run([*wrapper_command(entry), *args], cwd=root, env=child_env,
                                        capture_output=True, text=True, timeout=600)
                self.assertEqual(result.returncode, expected, (args, result.stdout, result.stderr))
                return result

            for entry in entries:
                self.assertIn("installed-guard-test", invoke(entry, ["--version"]).stdout)
                invoke(entry, ["--help"])
                invoke(entry, ["--check", str(source)])
                invoke(entry, ["--gen", str(source), "-o", str(root / "smoke.c")])
            originals = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in relocated.rglob("*") if path.is_file()}
            modes = {path: path.stat().st_mode for path in [relocated, *relocated.rglob("*")]}
            try:
                if os.name != "nt":
                    for path, mode in modes.items():
                        path.chmod(0o555 if path.is_dir() or mode & 0o111 else 0o444)
                invoke(entries[0], ["--check", str(source)])
                invoke(entries[0], ["--gen", str(source), "-o", str(root / "readonly.c")])
                # Curated inputs must also suffice for cold native preparation and standalone linking.
                child_env["PATH"] = env["PATH"]
                child_env["L1_STDLIB_CACHE"] = str(root / "fresh cache")
                child_env.pop("L1_CFLAGS", None)
                invoke(entries[0], ["--compile", str(source), "-o", str(root / "hello.o")])
                self.assertFalse((root / "fresh cache").exists())
                missing = invoke(entries[0], ["--run", "--no-auto-prepare", str(source)], 1)
                self.assertIn("L1C-2159", missing.stderr)
                self.assertEqual(invoke(entries[0], ["--run", str(source)]).stdout, "hello from Dea L1\n")
                program = root / ("hello.exe" if os.name == "nt" else "hello")
                invoke(entries[0], ["--link", "--no-auto-prepare", str(root / "hello.o"), "-o", str(program)])
                self.assertEqual(subprocess.check_output([str(program)], text=True), "hello from Dea L1\n")
                self.assertEqual(originals, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in originals})
            finally:
                if os.name != "nt":
                    for path, mode in modes.items():
                        path.chmod(mode)
            manifest = relocated / MANIFEST_PATH
            for state in (None, "not json", json.dumps({**record, "state": "incomplete"}),
                          json.dumps({**record, "schema_version": 1})):
                if state is None:
                    manifest.unlink()
                else:
                    manifest.write_text(state, encoding="utf-8")
                for entry in entries:
                    for args in (["--help"], ["--version"], ["--check", str(source)], ["--unknown"]):
                        result = invoke(entry, args, 1)
                        self.assertIn("[L1C-9515]", result.stderr)
                        self.assertIn("repair or retry installation", result.stderr)
                        self.assertEqual(result.stdout, "")
            manifest.write_text(json.dumps(record), encoding="utf-8")
            invoke(entries[0], ["--check", str(source)])


if __name__ == "__main__":
    unittest.main()
