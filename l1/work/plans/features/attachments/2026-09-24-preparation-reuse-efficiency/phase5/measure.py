#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Measure warm compiler phases using local logs and alternating baseline/candidate pairs."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time


def records(path: Path, label: str) -> list[dict]:
    """Read one independently prefixed JSON record stream from a retained local log.

    Args:
        path: Completed invocation log.
        label: Exact record prefix without its colon.

    Returns:
        Decoded records in emission order.

    Raises:
        OSError: If the retained log cannot be read.
        ValueError: If a prefixed record contains malformed JSON.
    """
    prefix = label + ": "
    return [json.loads(line[len(prefix):]) for line in path.read_text().splitlines() if line.startswith(prefix)]


def main() -> None:
    """Run warm controls, verify outputs outside timing, and save individual durations.

    Raises:
        RuntimeError: If clock, output, or native-reuse evidence is invalid.
        subprocess.CalledProcessError: If priming or program execution fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--repetitions", type=int, default=7)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    apps = {
        "hello": 'module hello; import std.io; func main() { printl_s("phase5-ok"); }\n',
        "collections": 'module collections; import std.io; import std.hashmap; import std.path; import std.time; '
                       'func main() { with (let words = sv_create(2) => sv_free(words)) { '
                       'sv_push(words, "phase5-ok"); printl_s(sv_get(words, 0)); } }\n',
    }
    # Explicit imports are required by the language; expose vector's names locally.
    apps["collections"] = apps["collections"].replace("import std.hashmap;", "import std.hashmap; import std.vector;")
    for name, text in apps.items():
        (root / (name + ".l1")).write_text(text)
    env = dict(os.environ)
    for name in ("L1_CFLAGS", "L1_CC", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    env.update(L1_HOME=str(args.home), L1_BUILD_DIR=str(args.build))
    binaries = {"baseline": args.baseline, "candidate": args.candidate}
    report = {"schema": 1, "platform": platform.platform(), "machine": platform.machine(),
              "python": platform.python_version(),
              "repetitions": args.repetitions, "applications": apps, "compilers": [], "invocations": []}
    preflight = root / "clock-preflight.stderr.log"
    with preflight.open("w") as log:
        subprocess.run([str(args.candidate), "--check", "hello", "-vvv"],
                       cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=log, check=True)
    clock_spans = records(preflight, "Compiler observation")
    if not clock_spans or any(item["elapsed_us"] is None for item in clock_spans):
        raise RuntimeError("candidate compiler clock preflight failed")
    report["clock_preflight"] = clock_spans
    for compiler in args.compiler:
        version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
        report["compilers"].append({"executable": compiler, "version": version})
        tag = Path(compiler).name
        for variant, binary in binaries.items():
            cache = root / (tag + "-" + variant + "-cache")
            command = [str(binary), "--prepare-stdlib", "--c-compiler", compiler, "--stdlib-cache", str(cache)]
            with (root / (tag + "-" + variant + "-prepare.log")).open("w") as log:
                subprocess.run(command, cwd=root, env=env, stdout=log, stderr=log, check=True)
        for app in apps:
            # Establish each cwd/profile's evidence before either timed variant.
            for variant in binaries:
                cache = root / (tag + "-" + variant + "-cache")
                command = [str(binaries[variant]), "--build", "--no-auto-prepare", "--c-compiler", compiler,
                           "--stdlib-cache", str(cache), app, "-o", str(root / "program")]
                with (root / (tag + "-" + variant + "-" + app + "-warm.log")).open("w") as log:
                    subprocess.run(command, cwd=root, env=env, stdout=log, stderr=log, check=True)
            for repetition in range(args.repetitions):
                for debug in (False, True):
                    order = ("baseline", "candidate") if repetition % 2 == 0 else ("candidate", "baseline")
                    for variant in order:
                        label = f"{tag}-{app}-{repetition}-{'debug' if debug else 'quiet'}-{variant}"
                        cache = root / (tag + "-" + variant + "-cache")
                        command = [str(binaries[variant]), "--build", "--no-auto-prepare", "--c-compiler", compiler,
                                   "--stdlib-cache", str(cache), app, "-o", str(root / "program")]
                        if debug:
                            command.append("-vvv")
                        stderr = root / (label + ".stderr.log")
                        with stderr.open("w") as err, (root / (label + ".stdout.log")).open("w") as out:
                            started = time.monotonic_ns()
                            completed = subprocess.run(command, cwd=root, env=env, stdout=out, stderr=err)
                            elapsed = (time.monotonic_ns() - started) / 1000
                        if completed.returncode:
                            report["failure"] = {"label": label, "returncode": completed.returncode,
                                                 "elapsed_us": elapsed, "stderr_log": stderr.name,
                                                 "compiler_spans": records(stderr, "Compiler observation")}
                            (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
                            raise RuntimeError(f"{label} failed; see {stderr}")
                        output = subprocess.check_output([str(root / "program")], cwd=root, env=env, text=True)
                        if output != "phase5-ok\n":
                            raise RuntimeError(f"unexpected program output for {label}: {output!r}")
                        spans = records(stderr, "Compiler observation")
                        prep = records(stderr, "Preparation observation")
                        counters = records(stderr, "Preparation statistics")
                        if debug:
                            if not counters or any(item["build_commands"] or item["module_compiles"] for item in counters):
                                raise RuntimeError(f"{label} did not reuse native preparation")
                            if variant == "candidate" and not spans:
                                raise RuntimeError(f"{label} has no compiler attribution")
                        elif spans:
                            raise RuntimeError(f"{label} emitted timing records below debug verbosity")
                        report["invocations"].append({"compiler": tag, "application": app, "repetition": repetition,
                                                      "variant": variant, "debug": debug, "elapsed_us": elapsed,
                                                      "compiler_spans": spans,
                                                      "preparation_spans": [item for item in prep if item["event"] == "span"],
                                                      "counters": counters, "output_verified": True})
                        (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
                        print(label, round(elapsed / 1000, 3), flush=True)
    groups = defaultdict(list)
    for item in report["invocations"]:
        key = (item["compiler"], item["application"], item["variant"], item["debug"])
        groups[key].append(item["elapsed_us"])
    report["distributions"] = [{"compiler": key[0], "application": key[1], "variant": key[2], "debug": key[3],
                                "minimum_us": min(values), "median_us": statistics.median(values),
                                "maximum_us": max(values)} for key, values in groups.items()]
    paired = defaultdict(dict)
    attributed = []
    for item in report["invocations"]:
        key = (item["compiler"], item["application"], item["debug"], item["repetition"])
        paired[key][item["variant"]] = item["elapsed_us"]
        if item["variant"] != "candidate" or not item["debug"]:
            continue
        scopes = defaultdict(int)
        for span in item["compiler_spans"]:
            if span["elapsed_us"] is None:
                raise RuntimeError("instrumented sample has an unavailable clock")
            scopes[span["scope"]] += span["elapsed_us"]
        compiler_total = sum(span["elapsed_us"] for span in item["compiler_spans"] if not span["parent"])
        preparation_total = sum(span["elapsed_us"] for span in item["preparation_spans"] if span["name"] in
                                ("native-identity-resolution", "profile-validation", "profile-lock-wait", "native-publication"))
        attributed.append({"compiler": item["compiler"], "application": item["application"],
                           "repetition": item["repetition"], "scope_totals_us": dict(scopes),
                           "compiler_outer_us": compiler_total, "preparation_outer_us": preparation_total,
                           "outside_recorded_us": item["elapsed_us"] - compiler_total - preparation_total,
                           "elapsed_us": item["elapsed_us"]})
    report["paired_overhead"] = [{"compiler": key[0], "application": key[1], "debug": key[2], "repetition": key[3],
                                 "difference_us": value["candidate"] - value["baseline"],
                                 "difference_percent": 100 * (value["candidate"] / value["baseline"] - 1)}
                                for key, value in paired.items()]
    report["attribution"] = attributed
    (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
