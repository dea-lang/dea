#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Exercise automatic preparation, completed-corruption recovery and concurrent misses."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

from l1c_stage1_managed_preparation_test import analysis_count, invoke, toolchain_fixture, preparation_c_compiler
from l1c_stage1_compile_only_test import L1_ROOT, stage1_compiler


def statistics(result: subprocess.CompletedProcess[str]) -> dict:
    """Read one native context's operation counts from debug output."""
    reports = re.findall(r"^Preparation statistics: (.*)$", result.stderr, re.MULTILINE)
    assert len(reports) == 1, result.stderr
    return json.loads(reports[0])


def observations(result: subprocess.CompletedProcess[str]) -> list[dict]:
    """Read schema-versioned preparation observations from debug output."""
    records = [json.loads(raw) for raw in
               re.findall(r"^Preparation observation: (.*)$", result.stderr, re.MULTILINE)]
    assert records and all(record.get("schema") == 1 and record.get("event") for record in records), result.stderr
    return records


def main() -> int:
    """Verify consuming commands can recover without replacing completed persistent state."""
    cc = preparation_c_compiler()
    assert cc
    env = dict(os.environ)
    for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="l1-preparation-integration-") as directory:
        root = Path(directory).resolve()
        compiler = toolchain_fixture(root, env)
        call = partial(invoke, root, env, compiler=compiler)
        cache = root / "cache with spaces and 'quotes'"
        headers = root / "runtime headers and 'quotes'"
        shutil.copytree(Path(env["L1_BUILD_DIR"]) / "include", headers)
        common = ("--c-compiler", cc, "--stdlib-cache", str(cache), "--runtime-include", str(headers),
                  "--c-options=-O1 -DREPAIR_OPTIONS=1 -fPIC", "--check-basic")
        source = root / "app.l1"
        source.write_text('module app; import std.io; func main() { printl_s("prepared-ok"); }\n')
        for command in (("--gen", "app"), ("--compile", "--c-compiler", cc, "app", "-o", str(root / "app.o"))):
            semantic = call(*command, "-vvv")
            assert any(item["event"] == "provider" and item.get("module") == "std.io" and
                       item.get("origin") == "interface" for item in observations(semantic)), semantic.stderr
        disabled = call("--run", *common, "--no-auto-prepare", "app", "-vvv", expected=1)
        assert "L1C-2159" in disabled.stderr and "--prepare-stdlib" in disabled.stderr
        disabled_observations = observations(disabled)
        assert any(item["event"] == "probe" and item["purpose"].startswith("runtime dependencies: ")
                   for item in disabled_observations)
        assert any(item["event"] == "decision" and item.get("reason") == "no-matching-memo"
                   for item in disabled_observations)
        assert not list(cache.glob("v1/native/*/manifest.json"))
        # Invalid application and explicit-provider inputs fail before native preparation.
        (root / "invalid_app.l1").write_text("module invalid_app; import std.io; func main() { missing_name(); }\n")
        invalid_app = call("--build", *common, "invalid_app", "-o", str(root / "invalid-app"), "-vvv", expected=1)
        assert analysis_count(invalid_app, "invalid_app") == 1 and analysis_count(invalid_app, "_dea_preparation") == 0
        assert any(item["event"] == "provider" and item.get("module") == "std.io"
                   for item in observations(invalid_app)), invalid_app.stderr
        (root / "external.l1").write_text("module external; func value() -> int { return 1; }\n")
        external_object = root / "external.o"
        call("--compile", "--c-compiler", cc, "external", "-o", str(external_object))
        external_object.unlink()
        (root / "explicit_app.l1").write_text("module explicit_app; import external; import std.io; func main() {}\n")
        invalid_provider = call("--build", *common, "-I", str(root), "explicit_app", "-o", str(root / "invalid-app"),
                                "-v", expected=1)
        assert "L1C-2097" in invalid_provider.stderr
        assert analysis_count(invalid_provider, "explicit_app") == 1 and analysis_count(invalid_provider, "_dea_preparation") == 0
        assert not list(cache.glob("v1/native/*/manifest.json"))
        cold = call("--run", *common, "app", "-vvv")
        count = len(list((L1_ROOT / "compiler/shared/l1/stdlib").rglob("*.l1")))
        assert cold.stdout == "prepared-ok\n" and statistics(cold)["module_compiles"] == count
        assert analysis_count(cold, "app") == 2 and analysis_count(cold, "_dea_preparation") == 1, cold.stderr
        cold_observations = observations(cold)
        assert any(item["event"] == "probe" and item["purpose"] == "compiler family and version"
                   for item in cold_observations)
        assert any(item["event"] == "hash" and item["category"] == "publication" and item["bytes"] > 0
                   for item in cold_observations)
        assert any(item["event"] == "span" and item["name"] == "native-publication" and item["inclusive"] == 1
                   for item in cold_observations)
        assert any("'quotes'" in item.get("path", "") for item in cold_observations), cold.stderr
        marker = next(cache.glob("v1/native/*/manifest.json"))
        entry = marker.parent
        warm = call("--run", *common, "--no-auto-prepare", "app")
        assert warm.stdout == "prepared-ok\n" and warm.stderr == ""
        warm_counts = call("--run", *common, "--no-auto-prepare", "app", "-vvv")
        assert statistics(warm_counts)["module_compiles"] == 0
        assert analysis_count(warm_counts, "app") == 2 and analysis_count(warm_counts, "_dea_preparation") == 0
        assert not re.search(r"Starting analysis for entry module '(?:std|sys)\.", warm_counts.stderr), warm_counts.stderr
        warm_observations = observations(warm_counts)
        assert any(item["event"] == "decision" and item.get("scope") == "native-profile" and
                   item.get("decision") == "hit" for item in warm_observations)
        assert any(item["event"] == "provider" and item.get("module") == "std.io" and
                   item.get("origin") == "interface" for item in warm_observations)
        # Corrupt only a disposable artifact digest, preserving actual file metadata.
        artifact_memo = next((cache / "v1/memo/artifacts").glob("*.json"))
        memo_data = json.loads(artifact_memo.read_text())
        memo_data["files"]["modules/std/io.o"]["sha256"] = "0" * 64
        artifact_memo.write_text(json.dumps(memo_data))
        memo_recovery = call("--run", *common, "--no-auto-prepare", "app", "-vvv")
        # Native joins can mix Windows separators; compare filesystem paths.
        artifact_path = entry / "modules/std/io.o"
        assert any(item["event"] == "hash" and Path(item["path"]) == artifact_path and
                   item["reason"] == "memo-digest-mismatch" for item in observations(memo_recovery)), memo_recovery.stderr
        assert not any(item["event"] == "metadata-mismatch" and Path(item["path"]) == artifact_path
                       for item in observations(memo_recovery)), memo_recovery.stderr
        # The compatibility field and complete differences retain the size change
        # without weakening content observation or guarded miss classification.
        public_header = headers / "dea_rt.h"
        public_bytes = public_header.read_bytes()
        public_header.write_bytes(public_bytes + b"\n/* preparation observability metadata change */\n")
        changed_header = call("--run", *common, "--no-auto-prepare", "app", "-vvv", expected=1)
        changed_observations = observations(changed_header)
        mismatch = next(item for item in changed_observations
                        if item["event"] == "metadata-mismatch" and Path(item["path"]) == public_header)
        assert mismatch["kind"] == "file" and mismatch["field"] == "size", mismatch
        assert mismatch["differences"]["size"]["current"] > mismatch["differences"]["size"]["previous"]
        assert any(item["event"] == "decision" and item.get("reason") == "metadata-changed"
                   for item in changed_observations)
        public_header.write_bytes(public_bytes)
        restored_header = call("--run", *common, "--no-auto-prepare", "app", "-vvv")
        assert restored_header.stdout == "prepared-ok\n"
        toolchain_memo = next(path for path in (cache / "v1/memo/toolchains").glob("*.json")
                              if "discovery" in json.loads(path.read_text()))
        toolchain_memo.write_text("{malformed memo")
        malformed_memo = call("--run", *common, "--no-auto-prepare", "app", "-vvv")
        assert malformed_memo.stdout == "prepared-ok\n"
        assert any(item["event"] == "decision" and item.get("scope") == "toolchain-observation-memo" and
                   item.get("reason") == "malformed-memo" for item in observations(malformed_memo))
        # An application without bundled imports still needs automatic runtime
        # selection. Keep this integration path outside ordinary runtime tests.
        (root / "runtime_only.l1").write_text("module runtime_only; func main() -> int { return 23; }\n")
        runtime_only = call("--run", *common, "--no-auto-prepare", "runtime_only", "-vvv", expected=23)
        runtime_stats = statistics(runtime_only)
        assert runtime_only.stdout == "" and runtime_stats["native_resolutions"] == 1
        assert runtime_stats["module_compiles"] == 0 and runtime_stats["build_commands"] == 0
        assert analysis_count(runtime_only, "_dea_preparation") == 0
        assert "Reuse prepared profile: " in runtime_only.stderr
        damaged = entry / "modules/std/io.o"
        data = damaged.read_bytes()
        damaged.write_bytes(b"!" + data[1:])
        rejected = call("--prepare-stdlib", *common, expected=1)
        assert "L1C-2153" in rejected.stderr and "--force" in rejected.stderr
        noauto = call("--run", *common, "--no-auto-prepare", "app", expected=1)
        assert "L1C-2159" in noauto.stderr and "externally serialize" in noauto.stderr
        manifest_bytes = marker.read_bytes()
        recovered = call("--run", *common, "app", "-v")
        assert recovered.stdout == "prepared-ok\n"
        assert "fresh command-private support" in recovered.stderr and "--force" in recovered.stderr
        assert "external serialization" in recovered.stderr
        assert analysis_count(recovered, "app") == 2 and analysis_count(recovered, "_dea_preparation") == 1
        assert marker.read_bytes() == manifest_bytes and damaged.read_bytes() != data
        shadow = entry / "generated/std/dea_rt.h"
        shadow.write_text("#error stale preparation scratch must never supply native headers\n")
        guidance = next(line.split("repair with ", 1)[1] for line in recovered.stderr.splitlines()
                        if line.startswith("Using fresh command-private support; repair with "))
        if guidance.startswith("literal argv "):
            repair_args, _ = json.JSONDecoder().raw_decode(guidance[len("literal argv "):])
        else:
            repair_args = shlex.split(guidance)
        assert repair_args[0] == "l1c" and "--force" in repair_args
        assert str(cache) in repair_args and "--check-basic" in repair_args
        assert "--c-options=-O1 -DREPAIR_OPTIONS=1 -fPIC" in repair_args
        forced = call(*repair_args[1:], "-vvv")
        assert list(cache.glob("v1/native/*/manifest.json")) == [marker]
        assert not shadow.exists()
        assert statistics(forced)["module_compiles"] == count and statistics(forced)["identity_content_reads"] > 0
        assert analysis_count(forced, "_dea_preparation") == 1, forced.stderr
        assert any(item["event"] == "decision" and item.get("reason") == "force"
                   for item in observations(forced))
        assert call("--run", *common, "--no-auto-prepare", "app").stdout == "prepared-ok\n"
        # Two same-key preparations of an incomplete entry must publish just once.
        marker.unlink()
        damaged.unlink()
        command = [str(compiler), "--prepare-stdlib", *common, "-vvv"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            runs = [executor.submit(subprocess.run, command, cwd=root, env=env, capture_output=True,
                                    text=True, timeout=600) for _ in range(2)]
            results = [future.result() for future in runs]
        for result in results:
            assert result.returncode == 0, result.stderr
            assert analysis_count(result, "_dea_preparation") == 1, result.stderr
        assert sum(statistics(result)["module_compiles"] for result in results) == count
        # The writer that waited on the lock reuses the published profile without recompiling.
        reused = [result for result in results if "Reuse prepared profile: " in result.stderr]
        assert len(reused) == 1, [result.stderr for result in results]
        assert statistics(reused[0])["module_compiles"] == 0, reused[0].stderr
        reused_line = next(line for line in reused[0].stderr.splitlines()
                           if line.startswith("Reuse prepared profile: "))
        assert Path(reused_line[len("Reuse prepared profile: "):]) == entry, reused[0].stderr
        assert marker.is_file()
        # A malformed completion marker is completed corruption, never an ordinary miss.
        marker.write_text("unfinished JSON")
        malformed = call("--prepare-stdlib", *common, "-vvv", expected=1)
        assert "L1C-2153" in malformed.stderr and marker.read_text() == "unfinished JSON"
        assert any(item["event"] == "decision" and item.get("decision") == "unusable"
                   for item in observations(malformed))
        if os.name != "nt":
            wrapper = root / "failing-cc"
            wrapper.write_text('#!/bin/sh\nfor word do\n if [ "$word" = -c ]; then\n'
                               '  echo "intentional native failure" >&2\n  exit 42\n fi\ndone\nexec ' +
                               shlex.quote(cc) + ' "$@"\n')
            wrapper.chmod(0o755)
            failure = call("--run", "--c-compiler", str(wrapper), "--stdlib-cache", str(root / "failed"),
                             "app", "-vvv", expected=1)
            assert "intentional native failure" in failure.stderr and "L1C-2156" in failure.stderr
            assert any(item["event"] in ("probe", "decision", "span") for item in observations(failure))
            assert not list((root / "failed").glob("v1/native/*/manifest.json"))
    print("automatic native preparation, private recovery and concurrent misses: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
