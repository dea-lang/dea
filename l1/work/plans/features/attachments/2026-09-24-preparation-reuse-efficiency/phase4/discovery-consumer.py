#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Measure actual managed consumers against two discovery implementations on macOS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time


def main() -> None:
    """Compile equal frontend controls and interleave cold, warm and invalidated consumers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("support_comparison", type=Path)
    parser.add_argument("generated_c", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--frontend-optimization", default="-O2")
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    repo, controls, generated, output = (path.resolve() for path in
                                         (args.repository, args.support_comparison, args.generated_c, args.output))
    if output.exists() and any(output.iterdir()):
        parser.error("consumer output must be a new or empty directory")
    output.mkdir(parents=True, exist_ok=True)
    compiler = "/usr/bin/clang"
    commands = []

    def command(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
        """Capture one checked construction, consumer or output-validation command.

        Args:
            argv: Exact argument vector to execute.
            **kwargs: Additional subprocess execution options.

        Returns:
            The completed process with captured output.

        Raises:
            RuntimeError: If execution exits unsuccessfully.
        """
        commands.append(argv)
        result = subprocess.run(argv, capture_output=True, text=True, **kwargs)
        if result.returncode:
            raise RuntimeError(f"command failed: {argv!r}\n{result.stdout}\n{result.stderr}")
        return result

    common = output / "frontend.o"
    command([compiler, "-std=c99", args.frontend_optimization, "-DL0_RT_CHECK_BASIC=1",
             "-D_RT_QUARANTINE_MAX_COUNT=256", "-I", str(repo / "l0/compiler/shared/runtime"),
             "-c", str(generated), "-o", str(common)], timeout=600)
    for variant in ("baseline", "candidate"):
        support = controls / f"{variant}-tree/l1/compiler/support"
        command([compiler, "-std=c99", "-O2", str(common),
                 str(support / "interface_fingerprint.c"),
                 str(support / "compiler_support.c"), str(support / "preparation_support.c"),
                 "-o", str(output / variant)], timeout=180)
    home, build = output / "compiler", output / "build"
    shutil.copytree(repo / "l1/compiler", home)
    command(["git", "apply", "--unsafe-paths", "-p4", f"--directory={home / 'support'}",
             str(Path(__file__).resolve().parent.parent / "measured-preparation.patch")], cwd=output)
    for name in ("interfaces", "include"):
        shutil.copytree(repo / f"l1/build/dea/{name}", build / name)
    source = output / "app.l1"
    source.write_text('module app; import std.io; func main() { printl_s("discovery-ok"); }\n')
    environment = {**os.environ, "L1_HOME": str(home), "L1_BUILD_DIR": str(build),
                   "L0_CC": compiler, "L1_CC": compiler, "L1_RUNTIME_CC": compiler}
    for variant in ("baseline", "candidate"):
        headers = output / f"headers-{variant}"
        shutil.copytree(build / "include", headers)
        command([str(output / variant), "--prepare-stdlib", "--c-compiler", compiler,
                 "--c-options=-O0", "--runtime-include", str(headers), "--stdlib-cache", str(output / f"cache-{variant}")],
                env=environment, timeout=600)
    records = []
    for repetition in range(args.repetitions):
        for variant in (("baseline", "candidate") if repetition % 2 == 0 else ("candidate", "baseline")):
            headers, cache = output / f"headers-{variant}", output / f"cache-{variant}"
            for scenario in ("cold", "warm", "partial"):
                if scenario == "cold":
                    shutil.rmtree(cache / "v1/memo", ignore_errors=True)
                elif scenario == "partial":
                    (headers / f"unrelated-{repetition}").write_text("directory invalidation\n")
                label = f"{variant}-{repetition + 1}-{scenario}"
                binary = output / "program"
                argv = [str(output / variant), "--build", "--c-compiler", compiler, "--c-options=-O0",
                        "--runtime-include", str(headers), "--stdlib-cache", str(cache), "--no-auto-prepare",
                        "--project-root", str(output), "-o", str(binary), "-vvv", str(source)]
                started = time.perf_counter_ns()
                result = command(argv, env=environment, timeout=240)
                elapsed_us = (time.perf_counter_ns() - started) // 1000
                (output / f"{label}.stdout").write_text(result.stdout)
                (output / f"{label}.stderr").write_text(result.stderr)
                assert command([str(binary)], timeout=30).stdout == "discovery-ok\n"
                statistics_lines = [line for line in result.stderr.splitlines()
                                    if line.startswith("Preparation statistics: ")]
                stats = json.loads(statistics_lines[-1].split(": ", 1)[1])
                assert stats["build_commands"] == stats["module_compiles"] == 0, stats
                events = [json.loads(line.removeprefix("Preparation observation: "))
                          for line in result.stderr.splitlines() if line.startswith("Preparation observation: ")]
                records.append(dict(label=label, variant=variant, repetition=repetition + 1, scenario=scenario,
                                    elapsed_us=elapsed_us, stats=stats, output_ok=True,
                                    toolchain_hash_bytes=sum(event["bytes"] for event in events
                                        if event["event"] == "hash" and event["category"] == "toolchain-input")))
                print(label, elapsed_us, flush=True)
    summary = []
    for variant in ("baseline", "candidate"):
        for scenario in ("cold", "warm", "partial"):
            selected = [record for record in records if (record["variant"], record["scenario"]) == (variant, scenario)]
            values = [record["elapsed_us"] for record in selected]
            summary.append(dict(variant=variant, scenario=scenario, samples_us=values,
                                median_us=statistics.median(values), probes=sorted({record["stats"]["probes"] for record in selected})))
    report = dict(schema=1, compiler_version=command([compiler, "--version"]).stdout,
                  frontend_optimization=args.frontend_optimization, preparation_support_optimization="-O2",
                  repetitions=args.repetitions, records=records, summary=summary, commands=commands)

    def sanitize(value):
        """Replace local path strings while preserving measured values and collection shape.

        Args:
            value: JSON-compatible evidence value.

        Returns:
            The same structure with public path placeholders in string values.
        """
        if isinstance(value, str):
            return value.replace(str(controls), "<support-controls>").replace(str(generated), "<generated-c>").replace(
                str(output), "<consumer-measurement>").replace(str(repo), "<repository>")
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    encoded = json.dumps(sanitize(report), indent=2, sort_keys=True) + "\n"
    (output / "report.json").write_text(encoded)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
