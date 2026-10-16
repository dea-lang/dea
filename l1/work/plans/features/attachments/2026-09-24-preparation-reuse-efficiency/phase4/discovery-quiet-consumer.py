#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run ordinary-output controls using previously built discovery consumer fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time


def main() -> None:
    """Interleave quiet consumers while preserving the prior construction and profile fixtures."""
    root = Path(sys.argv[1]).resolve()
    provenance = json.loads((root / "report.json").read_text())
    compiler = "/usr/bin/clang"
    environment = {**os.environ, "L1_HOME": str(root / "compiler"), "L1_BUILD_DIR": str(root / "build"),
                   "L0_CC": compiler, "L1_CC": compiler, "L1_RUNTIME_CC": compiler}
    records = []
    for repetition in range(provenance["repetitions"]):
        for variant in (("baseline", "candidate") if repetition % 2 == 0 else ("candidate", "baseline")):
            headers, cache = root / f"headers-{variant}", root / f"cache-{variant}"
            for scenario in ("cold", "warm", "partial"):
                if scenario == "cold":
                    shutil.rmtree(cache / "v1/memo", ignore_errors=True)
                elif scenario == "partial":
                    (headers / f"quiet-unrelated-{repetition}").write_text("directory invalidation\n")
                label = f"quiet-{variant}-{repetition + 1}-{scenario}"
                binary = root / "program"
                argv = [str(root / variant), "--build", "--c-compiler", compiler, "--c-options=-O0",
                        "--runtime-include", str(headers), "--stdlib-cache", str(cache), "--no-auto-prepare",
                        "--project-root", str(root), "-o", str(binary), str(root / "app.l1")]
                started = time.perf_counter_ns()
                result = subprocess.run(argv, env=environment, capture_output=True, text=True, timeout=240)
                elapsed_us = (time.perf_counter_ns() - started) // 1000
                assert result.returncode == 0 and not result.stdout and not result.stderr, result
                program = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
                assert program.returncode == 0 and program.stdout == "discovery-ok\n", program
                records.append(dict(label=label, variant=variant, repetition=repetition + 1,
                                    scenario=scenario, elapsed_us=elapsed_us, output_ok=True))
                print(label, elapsed_us, flush=True)
    summary = []
    for variant in ("baseline", "candidate"):
        for scenario in ("cold", "warm", "partial"):
            values = [record["elapsed_us"] for record in records
                      if (record["variant"], record["scenario"]) == (variant, scenario)]
            summary.append(dict(variant=variant, scenario=scenario, samples_us=values,
                                median_us=statistics.median(values)))
    report = dict(schema=1, compiler_version=provenance["compiler_version"],
                  frontend_optimization=provenance["frontend_optimization"],
                  preparation_support_optimization=provenance["preparation_support_optimization"],
                  repetitions=provenance["repetitions"], records=records, summary=summary)
    (root / "quiet-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
