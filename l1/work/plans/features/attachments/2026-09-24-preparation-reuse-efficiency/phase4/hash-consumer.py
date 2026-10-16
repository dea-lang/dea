#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#
"""Run a bounded portable SHA-256 actual-consumer gate in an existing Linux image."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time


HERE = Path(__file__).resolve().parent
VARIANTS = ("current", "unrolled")
COMPILERS = ("gcc", "clang")


def run(command: list[str], root: Path, label: str, environment: dict | None = None) -> tuple[float, str]:
    """Capture a checked command and retain its complete local output.

    Args:
        command: Argument vector.
        root: Owned working and evidence directory.
        label: Unique output stem.
        environment: Optional controlled compiler environment.

    Returns:
        Wall milliseconds and completed stderr text.

    Raises:
        RuntimeError: A command failed.
    """
    with (root / f"{label}.stdout").open("w") as out, (root / f"{label}.stderr").open("w") as err:
        started = time.monotonic_ns()
        completed = subprocess.run(command, cwd=root, env=environment, stdout=out, stderr=err, timeout=600)
        elapsed = (time.monotonic_ns() - started) / 1000000
    stderr = (root / f"{label}.stderr").read_text()
    if completed.returncode:
        raise RuntimeError(f"{label} failed ({completed.returncode}); see retained log: " +
                           stderr[-3000:])
    return elapsed, stderr


def fields(stderr: str, name: str) -> list[str]:
    """Return an exact independently prefixed compiler diagnostic stream.

    Args:
        stderr: Completed compiler diagnostics.
        name: Prefix without a colon.

    Returns:
        Matching payloads in emission order.
    """
    prefix = name + ": "
    return [line[len(prefix):] for line in stderr.splitlines() if line.startswith(prefix)]


def environment(root: Path) -> dict:
    """Select fixed semantic/runtime inputs independent of the two compiler binaries.

    Args:
        root: Owned fixture root.

    Returns:
        Compiler invocation environment.
    """
    selected = {key: value for key, value in os.environ.items() if not key.startswith(("L0_", "L1_"))}
    selected.update(L1_HOME=str(root / "compiler"), L1_BUILD_DIR=str(root / "build"))
    return selected


def command(root: Path, variant: str, compiler: str, prepare: bool = False, debug: bool = False) -> list[str]:
    """Return one consumer or preparation command with the same downstream flags.

    Args:
        root: Owned fixture root.
        variant: Hash backend.
        compiler: Supported downstream compiler.
        prepare: Build its own prepared profile.
        debug: Request independent attribution records.

    Returns:
        Compiler argument vector.
    """
    words = [str(root / variant), "--prepare-stdlib" if prepare else "--build", "--c-compiler", compiler,
             "--c-options=-O0", "--runtime-include", str(root / "build/include"),
             "--stdlib-cache", str(root / f"cache-{compiler}-{'baseline' if variant == 'current' else variant}")]
    if not prepare:
        words.extend(["--no-auto-prepare", "--project-root", str(root), "-o", str(root / "program"),
                      str(root / "app.l1")])
    if debug:
        words.append("-vvv")
    return words


def build(args: argparse.Namespace) -> None:
    """Compile one frontend object and link both isolated preparation backends.

    Args:
        args: Resolved fixture paths.
    """
    root, repo = args.output, args.repository
    if root.exists() and any(root.iterdir()):
        raise RuntimeError("build output must be a new or empty directory")
    root.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("hash_measure", HERE / "hash-measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline = (HERE / "hash-baseline-sha256.h").read_text()
    common = root / "frontend.o"
    flags = ["gcc", "-std=c99", "-O0", "-DL0_RT_CHECK_BASIC=1", "-D_RT_QUARANTINE_MAX_COUNT=256",
             "-I", str(repo / "l0/compiler/shared/runtime")]
    if args.reuse_binaries:
        for name in ("frontend.o", *VARIANTS):
            shutil.copy2(args.reuse_binaries / name, root / name)
    else:
        run([*flags, "-c", str(args.generated_c), "-o", str(common)], root, "build-frontend")
    for variant in VARIANTS:
        support = root / f"support-{variant}"
        shutil.copytree(repo / "l1/compiler/support", support)
        run(["git", "apply", "--unsafe-paths", "-p4", f"--directory={support}",
             str(HERE.parent / "measured-preparation.patch")], root, f"restore-{variant}")
        header = baseline if variant == "current" else module.unrolled_header(baseline)
        (support / "preparation/sha256.h").write_text(header)
        if not args.reuse_binaries:
            run(["gcc", "-std=c99", "-O1", str(common),
                 str(support / "interface_fingerprint.c"),
                 str(support / "compiler_support.c"), str(support / "preparation_support.c"),
                 "-o", str(root / variant)], root, f"build-{variant}")
    shutil.copytree(repo / "l1/compiler", root / "compiler")
    run(["git", "apply", "--unsafe-paths", "-p4", f"--directory={root / 'compiler/support'}",
         str(HERE.parent / "measured-preparation.patch")], root, "restore-home")
    for name in ("interfaces", "include"):
        shutil.copytree(repo / f"l1/build/dea/{name}", root / f"build/{name}")
    (root / "app.l1").write_text('module app; import std.io; func main() { printl_s("hash-consumer-ok"); }\n')
    prepared = {}
    for compiler in COMPILERS:
        for variant in VARIANTS:
            _, stderr = run(command(root, variant, compiler, prepare=True, debug=True), root,
                            f"prepare-{compiler}-{variant}", environment(root))
            prepared[f"{compiler}-{variant}"] = {
                "dea_key": fields(stderr, "Preparation Dea key")[-1],
                "native_key": fields(stderr, "Preparation native key")[-1],
            }
    versions = {compiler: subprocess.check_output([compiler, "--version"], text=True) for compiler in COMPILERS}
    (root / "build-record.json").write_text(json.dumps({
        "schema": 1, "frontend_optimization": "-O0", "support_optimization": "-O1",
        "runtime_check_basic": True, "quarantine_max_count": 256,
        "compilers": versions, "prepared": prepared,
        "binary_bytes": {variant: (root / variant).stat().st_size for variant in VARIANTS},
    }, indent=2) + "\n")
    print("Consumer controls and own prepared profiles built.", flush=True)


def measure(args: argparse.Namespace) -> None:
    """Run five quiet pairs plus separate debug checks and classify the fixed gate.

    Args:
        args: Fixture root and fixed repetition budget.
    """
    root = args.output
    provenance = json.loads((root / "build-record.json").read_text())
    records = []
    identities = {}
    for debug in (False, True):
        for compiler in COMPILERS:
            for repetition in range(1 if debug else args.repetitions):
                order = VARIANTS if repetition % 2 == 0 else tuple(reversed(VARIANTS))
                for variant in order:
                    fixture = "baseline" if variant == "current" else variant
                    shutil.rmtree(root / f"cache-{compiler}-{fixture}/v1/memo", ignore_errors=True)
                    for scenario in ("cold", "warm"):
                        label = f"{'debug' if debug else 'quiet'}-{compiler}-{repetition}-{variant}-{scenario}"
                        elapsed, stderr = run(command(root, variant, compiler, debug=debug), root, label,
                                              environment(root))
                        output = subprocess.check_output([str(root / "program")], text=True)
                        assert output == "hash-consumer-ok\n", output
                        record = dict(label=label, compiler=compiler, variant=variant, repetition=repetition,
                                      scenario=scenario, debug=debug, elapsed_ms=elapsed, output_ok=True)
                        if debug:
                            own = provenance["prepared"][f"{compiler}-{variant}"]
                            assert fields(stderr, "Preparation Dea key")[-1] == own["dea_key"]
                            assert fields(stderr, "Preparation native key")[-1] == own["native_key"]
                            assert fields(stderr, "Reuse prepared profile"), stderr
                            if scenario == "cold":
                                identities[compiler, variant] = (
                                    json.loads(fields(stderr, "Preparation Dea inputs")[-1]),
                                    json.loads(fields(stderr, "Preparation native inputs")[-1]))
                            stats = json.loads(fields(stderr, "Preparation statistics")[-1])
                            assert stats["build_commands"] == stats["module_compiles"] == 0, stats
                            events = [json.loads(line) for line in fields(stderr, "Preparation observation")]
                            hashes = [event for event in events if event["event"] == "hash"]
                            record.update(stats=stats, hashes={category: {
                                "count": sum(event["category"] == category for event in hashes),
                                "bytes": sum(event["bytes"] for event in hashes if event["category"] == category),
                            } for category in ("dea-input", "toolchain-input", "artifact-validation")})
                        else:
                            assert not stderr and not (root / f"{label}.stdout").read_text(), label
                        records.append(record)
                        print(label, round(elapsed, 3), flush=True)
    for compiler in COMPILERS:
        before, after = (identities[compiler, variant] for variant in VARIANTS)
        dea_before, dea_after = dict(before[0]), dict(after[0])
        del dea_before["compiler"], dea_after["compiler"]
        assert dea_before == dea_after
        native_before, native_after = dict(before[1]), dict(after[1])
        for name in ("D", "dea_inputs"):
            del native_before[name], native_after[name]
        assert native_before == native_after
        for scenario in ("cold", "warm"):
            selected = [r for r in records if r["debug"] and r["compiler"] == compiler and r["scenario"] == scenario]
            assert selected[0]["hashes"]["toolchain-input"] == selected[1]["hashes"]["toolchain-input"]
            assert selected[0]["hashes"]["artifact-validation"] == selected[1]["hashes"]["artifact-validation"]
            assert selected[0]["stats"]["probes"] == selected[1]["stats"]["probes"]
    summaries = {}
    for compiler in COMPILERS:
        summaries[compiler] = {}
        for scenario in ("cold", "warm"):
            selected = [r for r in records if not r["debug"] and r["compiler"] == compiler and r["scenario"] == scenario]
            current = {r["repetition"]: r["elapsed_ms"] for r in selected if r["variant"] == "current"}
            changed = {r["repetition"]: r["elapsed_ms"] for r in selected if r["variant"] == "unrolled"}
            before, after = statistics.median(current.values()), statistics.median(changed.values())
            differences = [value-changed[key] for key, value in current.items()]
            percentages = [100*(value-changed[key])/value for key, value in current.items()]
            summaries[compiler][scenario] = dict(current_ms=before, unrolled_ms=after,
                improvement_ms=before-after, improvement_percent=100*(before-after)/before,
                improvement_pairs=sum(changed[key] < value for key, value in current.items()),
                current_samples_ms=list(current.values()), unrolled_samples_ms=list(changed.values()),
                paired_improvements_ms=differences, median_paired_improvement_ms=statistics.median(differences),
                median_paired_improvement_percent=statistics.median(percentages))
    qualified = []
    for compiler, threshold in (("gcc", 70), ("clang", 150)):
        chosen = summaries[compiler]["cold"]
        other = summaries["clang" if compiler == "gcc" else "gcc"]["cold"]
        warm_ok = all(summaries[name]["warm"]["improvement_ms"] >= -100 and
                      summaries[name]["warm"]["improvement_percent"] >= -10 for name in COMPILERS)
        if (chosen["improvement_ms"] >= threshold and chosen["improvement_percent"] >= 3 and
                chosen["improvement_pairs"] >= 4 and other["improvement_ms"] >= -50 and
                other["improvement_percent"] >= -3 and warm_ok):
            qualified.append(compiler)
    report = {"schema": 1, "date": "2026-10-16", "repetitions": args.repetitions,
              "construction": provenance, "records": records, "summaries": summaries,
              "gate": {"qualified_compilers": qualified, "adopt": bool(qualified),
                       "identities_own_profile_preserved": True, "noncompiler_identity_inputs_equal": True,
                       "toolchain_and_artifact_hash_coverage_equal": True}}
    (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summaries"], indent=2), flush=True)
    print(json.dumps(report["gate"]), flush=True)


def main() -> None:
    """Parse reproducible build or measurement options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("generated_c", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("build", "measure"), required=True)
    parser.add_argument("--reuse-binaries", type=Path)
    parser.add_argument("--repetitions", type=int, choices=(5,), default=5)
    args = parser.parse_args()
    args.repository, args.generated_c, args.output = (p.resolve() for p in
                                                     (args.repository, args.generated_c, args.output))
    (build if args.mode == "build" else measure)(args)


if __name__ == "__main__":
    main()
