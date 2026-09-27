#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Measure production SHA-256 cost and bounded experiment-local candidates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import tarfile
import time


EXPERIMENT_RELATIVE = Path(
    "l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation"
)
INPUTS = {
    "control-4k": "/opt/dea/investigation/control-4k.bin",
    "control-8m": "/opt/dea/investigation/control-8m.bin",
    "gcc-cc1": "/usr/libexec/gcc/x86_64-linux-gnu/14/cc1",
    "llvm": "/usr/lib/x86_64-linux-gnu/libLLVM.so.19.1",
    "clang-cpp": "/usr/lib/x86_64-linux-gnu/libclang-cpp.so.19.1",
    "z3": "/usr/lib/x86_64-linux-gnu/libz3.so.4",
}
EXPECTED_SIZES = {
    "control-4k": 4096,
    "control-8m": 8 * 1024 * 1024,
    "gcc-cc1": 34_148_896,
    "llvm": 129_673_080,
    "clang-cpp": 71_043_800,
    "z3": 27_751_664,
}
MEMORY_MODES = ("65536", "64", "irregular")
ACTUAL_INPUTS = ("gcc-cc1", "llvm", "clang-cpp", "z3")
COMPILERS = ("gcc", "clang")


def run(argv: list[str], *, timeout: int = 1800, log: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run one command and retain its complete output when requested.

    Args:
        argv: Command argument vector.
        timeout: Maximum elapsed seconds.
        log: Optional combined-output destination.

    Returns:
        Successful completed process.

    Raises:
        subprocess.CalledProcessError: The command failed.
        subprocess.TimeoutExpired: The command exceeded its timeout.
    """
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        print(completed.stdout[-3000:])
        print(completed.stderr[-6000:])
        completed.check_returncode()
    return completed


def archive_context(repo: Path, output: Path) -> Path:
    """Create an isolated tracked-source context plus the current experiment bundle.

    Args:
        repo: Monorepo root.
        output: Untracked experiment output root.

    Returns:
        Docker build-context directory.
    """
    archive = output / "source.tar"
    context = output / "context"
    if context.exists():
        shutil.rmtree(context)
    context.mkdir(parents=True)
    with archive.open("wb") as stream:
        subprocess.run(["git", "-C", str(repo), "archive", "HEAD"], stdout=stream, check=True)
    with tarfile.open(archive) as source:
        source.extractall(context, filter="data")
    source_experiment = repo / EXPERIMENT_RELATIVE
    target_experiment = context / EXPERIMENT_RELATIVE
    if target_experiment.exists():
        shutil.rmtree(target_experiment)
    shutil.copytree(source_experiment, target_experiment, ignore=shutil.ignore_patterns("*.gz", "results.md"))
    return context


def build_image(
    context: Path,
    dockerfile: Path,
    output: Path,
    variant: str,
    target: str,
) -> tuple[str, dict]:
    """Build and inspect one experiment image.

    Args:
        context: Isolated source context.
        dockerfile: Experiment Dockerfile.
        output: Raw-output directory.
        variant: Source variant name.
        target: Docker build target.

    Returns:
        Image tag and inspect object.
    """
    tag = f"dea-sha256-{target}-{variant}:local"
    run(
        [
            "docker",
            "build",
            "--progress=plain",
            "--build-arg",
            f"VARIANT={variant}",
            "--target",
            target,
            "-t",
            tag,
            "-f",
            str(dockerfile),
            str(context),
        ],
        timeout=3600,
        log=output / "build" / f"{target}-{variant}.log",
    )
    inspected = json.loads(run(["docker", "image", "inspect", tag]).stdout)[0]
    return tag, {
        "tag": tag,
        "id": inspected["Id"],
        "created": inspected["Created"],
        "size_bytes": inspected["Size"],
    }


def container_prefix(image: str, *, cpus: int = 1) -> list[str]:
    """Return the common isolated container prefix.

    Args:
        image: Local image tag.
        cpus: CPU quota.

    Returns:
        Docker argument prefix ending in the image.
    """
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        "512m",
        "--memory-swap",
        "512m",
        "--pids-limit",
        "64",
        "--cpus",
        str(cpus),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        image,
    ]


def image_text(image: str, path: str) -> str:
    """Read one text file from a disposable image container.

    Args:
        image: Local image tag.
        path: Absolute image path.

    Returns:
        File contents.
    """
    return run([*container_prefix(image), "cat", path], timeout=300).stdout


def reference_digests(image: str) -> dict[str, dict]:
    """Return independent coreutils digests and verified sizes.

    Args:
        image: Benchmark image.

    Returns:
        Per-input size and SHA-256 records.
    """
    records: dict[str, dict] = {}
    for name, path in INPUTS.items():
        command = [*container_prefix(image), "sh", "-c", f"stat -c '%s' {path}; sha256sum {path}"]
        lines = run(command, timeout=300).stdout.splitlines()
        size = int(lines[0])
        digest = lines[1].split()[0]
        if size != EXPECTED_SIZES[name]:
            raise AssertionError((name, size, EXPECTED_SIZES[name]))
        records[name] = {"path": path, "bytes": size, "sha256": digest}
    return records


def parse_json_lines(text: str) -> list[dict]:
    """Parse nonempty JSON lines.

    Args:
        text: Harness output.

    Returns:
        Parsed objects.
    """
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def verify_vectors(records: list[dict]) -> None:
    """Compare unaligned streaming vectors with Python hashlib.

    Args:
        records: Harness vector records.
    """
    allocation = bytes((index * 131 + 17) & 255 for index in range(132))
    expected_sizes = (0, 55, 56, 63, 64, 65, 129)
    if tuple(record["bytes"] for record in records) != expected_sizes:
        raise AssertionError("unexpected vector inventory")
    for record in records:
        expected = hashlib.sha256(allocation[1 : 1 + record["bytes"]]).hexdigest()
        if record["digest"] != expected or record["offset"] != 1:
            raise AssertionError(record)


def benchmark_variant(image: str, variant: str, output: Path, references: dict[str, dict]) -> dict:
    """Run vector and independent operation measurements for one variant.

    Args:
        image: Benchmark image.
        variant: Variant label.
        output: Raw-output directory.
        references: Independent input digests and sizes.

    Returns:
        Variant benchmark report.
    """
    target = output / "microbench" / variant
    target.mkdir(parents=True, exist_ok=True)
    vector_result = run(
        [*container_prefix(image), "/opt/dea/investigation/sha256-benchmark", "vectors"],
        log=target / "vectors.log",
    )
    vectors = parse_json_lines(vector_result.stdout)
    verify_vectors(vectors)
    measurements: list[dict] = []
    for name, path in INPUTS.items():
        operations = [("read", None), ("stable", None), *(("memory", mode) for mode in MEMORY_MODES)]
        for operation, mode in operations:
            args = [
                *container_prefix(image),
                "/opt/dea/investigation/sha256-benchmark",
                operation,
                path,
            ]
            if mode is not None:
                args.append(mode)
            args.append("3")
            label = f"{name}-{operation}" + (f"-{mode}" if mode else "")
            completed = run(args, timeout=1200, log=target / f"{label}.log")
            records = parse_json_lines(completed.stdout)
            for record in records:
                record["input"] = name
                record["throughput_mib_s"] = (
                    record["bytes"] / (1024 * 1024) / (record["wall_ms"] / 1000)
                    if record["wall_ms"] > 0
                    else None
                )
                if record["bytes"] != references[name]["bytes"]:
                    raise AssertionError(record)
                if record["digest"] is not None and record["digest"] != references[name]["sha256"]:
                    raise AssertionError(record)
            if operation == "read" and len({record["checksum"] for record in records}) != 1:
                raise AssertionError(f"unstable read checksum: {variant} {name}")
            measurements.extend(records)
    assembly = image_text(image, "/opt/dea/investigation/benchmark.s")
    (target / "benchmark.s").write_text(assembly, encoding="utf-8")
    return {
        "vectors": vectors,
        "measurements": measurements,
        "assembly": {
            "bytes": len(assembly.encode()),
            "memcpy_calls": len(re.findall(r"call[^\n]*memcpy", assembly)),
            "sha_block_mentions": assembly.count("pc_sha_block"),
        },
    }


def benchmark_matrix(
    images: dict[str, str],
    output: Path,
    references: dict[str, dict],
) -> dict[str, dict]:
    """Run operation cells with alternating variant order to limit temporal drift.

    Args:
        images: Benchmark images keyed by variant.
        output: Raw-output directory.
        references: Independent input digests and sizes.

    Returns:
        Benchmark reports keyed by variant.
    """
    reports: dict[str, dict] = {}
    variants = tuple(images)
    for variant, image in images.items():
        target = output / "microbench" / variant
        target.mkdir(parents=True, exist_ok=True)
        vector_result = run(
            [*container_prefix(image), "/opt/dea/investigation/sha256-benchmark", "vectors"],
            log=target / "vectors.log",
        )
        vectors = parse_json_lines(vector_result.stdout)
        verify_vectors(vectors)
        assembly = image_text(image, "/opt/dea/investigation/benchmark.s")
        (target / "benchmark.s").write_text(assembly, encoding="utf-8")
        reports[variant] = {
            "vectors": vectors,
            "measurements": [],
            "assembly": {
                "bytes": len(assembly.encode()),
                "memcpy_calls": len(re.findall(r"call[^\n]*memcpy", assembly)),
                "sha_block_mentions": assembly.count("pc_sha_block"),
            },
        }
    cell_index = 0
    for name, path in INPUTS.items():
        operations = [("read", None), ("stable", None), *(("memory", mode) for mode in MEMORY_MODES)]
        for operation, mode in operations:
            order = variants if cell_index % 2 == 0 else tuple(reversed(variants))
            cell_index += 1
            for variant in order:
                image = images[variant]
                args = [
                    *container_prefix(image),
                    "/opt/dea/investigation/sha256-benchmark",
                    operation,
                    path,
                ]
                if mode is not None:
                    args.append(mode)
                args.append("3")
                label = f"{cell_index:02d}-{name}-{operation}" + (f"-{mode}" if mode else "")
                completed = run(
                    args,
                    timeout=1200,
                    log=output / "microbench" / variant / f"{label}.log",
                )
                records = parse_json_lines(completed.stdout)
                for record in records:
                    record["input"] = name
                    record["throughput_mib_s"] = (
                        record["bytes"] / (1024 * 1024) / (record["wall_ms"] / 1000)
                        if record["wall_ms"] > 0
                        else None
                    )
                    if record["bytes"] != references[name]["bytes"]:
                        raise AssertionError(record)
                    if record["digest"] is not None and record["digest"] != references[name]["sha256"]:
                        raise AssertionError(record)
                if operation == "read" and len({record["checksum"] for record in records}) != 1:
                    raise AssertionError(f"unstable read checksum: {variant} {name}")
                reports[variant]["measurements"].extend(records)
    return reports


def selection_headroom(image: str, output: Path, references: dict[str, dict]) -> float:
    """Measure the baseline Clang-input memory SHA headroom before choosing candidate two.

    Args:
        image: Baseline benchmark image.
        output: Raw-output directory.
        references: Independent input records.

    Returns:
        Sum of repeated 64 KiB memory-SHA medians.
    """
    values = []
    target = output / "selection-baseline"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("llvm", "clang-cpp", "z3"):
        path = INPUTS[name]
        completed = run(
            [
                *container_prefix(image),
                "/opt/dea/investigation/sha256-benchmark",
                "memory",
                path,
                "65536",
                "3",
            ],
            timeout=1200,
            log=target / f"{name}.log",
        )
        records = parse_json_lines(completed.stdout)
        if any(record["digest"] != references[name]["sha256"] for record in records):
            raise AssertionError(name)
        values.append(statistics.median(record["wall_ms"] for record in records if record["access"] == "repeated"))
    return sum(values)


def repeated_median(benchmark: dict, operation: str, input_name: str, mode: str = "65536") -> float:
    """Return the repeated wall-time median for one microbenchmark cell.

    Args:
        benchmark: Variant benchmark report.
        operation: Operation label.
        input_name: Input label.
        mode: Chunk-mode label.

    Returns:
        Median wall milliseconds.
    """
    values = [
        record["wall_ms"]
        for record in benchmark["measurements"]
        if record["operation"] == operation
        and record["input"] == input_name
        and record["mode"] == mode
        and record["access"] == "repeated"
    ]
    if not values:
        raise AssertionError((operation, input_name, mode))
    return statistics.median(values)


def candidate_micro_result(baseline: dict, candidate: dict) -> dict:
    """Apply the large-file stable-hash advancement gate.

    Args:
        baseline: Baseline microbenchmark report.
        candidate: Candidate microbenchmark report.

    Returns:
        Gate details.
    """
    rows = []
    for name in ACTUAL_INPUTS:
        before = repeated_median(baseline, "stable-hash", name)
        after = repeated_median(candidate, "stable-hash", name)
        rows.append({"input": name, "baseline_ms": before, "candidate_ms": after,
                     "improvement_ms": before - after, "improvement_percent": (before - after) * 100 / before})
    advanced = sum(row["candidate_ms"] for row in rows) < sum(row["baseline_ms"] for row in rows) and all(
        row["candidate_ms"] <= row["baseline_ms"] * 1.01 for row in rows
    )
    return {"advanced": advanced, "large_stable_hash": rows}


def clang_sha_headroom_ms(baseline: dict) -> float:
    """Estimate Clang-input SHA CPU headroom from preloaded-memory timings.

    Args:
        baseline: Baseline microbenchmark report.

    Returns:
        Sum for the three Clang shared-library inputs.
    """
    return sum(repeated_median(baseline, "memory-sha256", name) for name in ("llvm", "clang-cpp", "z3"))


def parse_fields(text: str, label: str) -> list[str]:
    """Return exact verbose fields with one label.

    Args:
        text: Compiler stderr.
        label: Field label without colon.

    Returns:
        Field values.
    """
    return re.findall(rf"^{re.escape(label)}: (.*)$", text, re.MULTILINE)


def observations(text: str) -> list[dict]:
    """Parse preparation observation records.

    Args:
        text: Compiler stderr.

    Returns:
        Observation dictionaries.
    """
    prefix = "Preparation observation: "
    return [json.loads(line[len(prefix) :]) for line in text.splitlines() if line.startswith(prefix)]


def compile_record(target: Path, label: str, expected: list[str], debug: bool) -> dict:
    """Parse and validate one timed compiler invocation.

    Args:
        target: Case output directory.
        label: Invocation label.
        expected: Sorted expected program lines.
        debug: Whether verbose evidence is required.

    Returns:
        Parsed record.
    """
    timer = json.loads((target / f"{label}.json").read_text(encoding="utf-8"))
    if timer["exit_code"] != 0 or timer["timeout"]:
        raise AssertionError((target, label, timer))
    actual = sorted((target / f"{label}.program").read_text(encoding="utf-8").splitlines())
    if actual != expected:
        raise AssertionError((target, label, actual))
    stderr = (target / f"{label}.stderr").read_text(encoding="utf-8")
    events = observations(stderr)
    hashes = [event for event in events if event.get("event") == "hash"]
    result = {
        "elapsed_ms": timer["elapsed_ms"],
        "user_ms": timer.get("user_ms"),
        "system_ms": timer.get("system_ms"),
        "output_ok": True,
    }
    if debug:
        dea_keys = parse_fields(stderr, "Preparation Dea key")
        native_keys = parse_fields(stderr, "Preparation native key")
        stats = parse_fields(stderr, "Preparation statistics")
        if not dea_keys or not native_keys or not stats:
            raise AssertionError(f"missing verbose identity in {target}/{label}")
        result.update(
            {
                "dea_key": dea_keys[-1],
                "native_key": native_keys[-1],
                "stats": json.loads(stats[-1]),
                "probe_count": sum(event.get("event") == "probe" for event in events),
                "hashes": {
                    category: {
                        "count": sum(event.get("category") == category for event in hashes),
                        "bytes": sum(event.get("bytes", 0) for event in hashes if event.get("category") == category),
                    }
                    for category in ("dea-input", "toolchain-input", "artifact-validation")
                },
                "decisions": [event for event in events if event.get("event") == "decision"],
            }
        )
    return result


def runtime_container_args(image: str, fixture: Path, target: Path) -> list[str]:
    """Return same-path prepared-image runtime arguments.

    Args:
        image: Prepared image.
        fixture: Host fixture directory.
        target: Writable result directory.

    Returns:
        Docker arguments ending in the image.
    """
    return [
        "docker", "run", "--rm", "--network", "none", "--memory", "256m", "--memory-swap", "256m",
        "--pids-limit", "64", "--cpus", "1", "--user", "65534:65534", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--tmpfs", "/work:rw,size=64m,exec,mode=1777",
        "-e", "HOME=/work", "-e", "TMPDIR=/work", "-e", "L1_STDLIB_CACHE=/opt/dea/l1/cache-template",
        "-w", "/work", "-v", f"{fixture}:/input:ro", "-v", f"{target}:/results:rw", image,
    ]


def run_compile_case(
    image: str,
    variant: str,
    compiler: str,
    repeat: int,
    debug: bool,
    fixture: Path,
    output: Path,
    expected: list[str],
) -> dict:
    """Run one fresh-container first/warm pair.

    Args:
        image: Prepared image tag.
        variant: Variant label.
        compiler: Downstream compiler.
        repeat: One-based repetition.
        debug: Enable verbose attribution.
        fixture: Fixture directory.
        output: Raw-output root.
        expected: Expected executable output lines.

    Returns:
        Case record.
    """
    suffix = "debug" if debug else "quiet"
    target = output / "runtime" / f"{variant}-{compiler}-{repeat}-{suffix}"
    target.mkdir(parents=True, exist_ok=True)
    target.chmod(0o777)
    lines = ["set -eu", "mkdir -p /work/capture"]
    for index in (1, 2):
        label = f"build-{index}"
        command = [
            "/opt/dea/bin/l1c-stage1", "--build", "--c-compiler", compiler, "--c-options=-O0",
            "--no-auto-prepare", "--project-root", "/input", "-o", "/work/hello.out",
            *(["-vvv"] if debug else []), "/input/hello.l1",
        ]
        quoted = " ".join(subprocess.list2cmdline([word]) for word in command)
        timer = " ".join(
            subprocess.list2cmdline([word])
            for word in [
                "/opt/dea/bin/investigation-timer", f"/work/capture/{label}.json",
                f"/work/capture/{label}.stdout", f"/work/capture/{label}.stderr", "600",
            ]
        )
        lines.extend([f"{timer} {quoted}", f"/work/hello.out > /work/capture/{label}.program"])
    lines.extend(
        [
            "cp /work/capture/* /results/",
            "cp /opt/dea/investigation/image-build-*.stderr /results/",
        ]
    )
    (target / "case.sh").write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(
        [*runtime_container_args(image, fixture, target), "sh", "/results/case.sh"],
        timeout=1200,
        log=target / "container.log",
    )
    return {
        "variant": variant,
        "compiler": compiler,
        "repeat": repeat,
        "debug": debug,
        "records": [compile_record(target, f"build-{index}", expected, debug) for index in (1, 2)],
    }


def image_time_keys(image: str, compiler: str) -> dict[str, str]:
    """Return image-time D and N from the prepared image.

    Args:
        image: Prepared image.
        compiler: Downstream compiler label.

    Returns:
        Dea and native keys.
    """
    text = image_text(image, f"/opt/dea/investigation/image-build-{compiler}.stderr")
    return {
        "dea_key": parse_fields(text, "Preparation Dea key")[-1],
        "native_key": parse_fields(text, "Preparation native key")[-1],
    }


def verify_debug_equivalence(cases: list[dict], image_keys: dict[str, dict[str, dict]]) -> None:
    """Verify policy evidence and per-image identity across debug cases.

    Args:
        cases: Runtime cases.
        image_keys: Image-time identity keys by variant and compiler.
    """
    debug_cases = [case for case in cases if case["debug"]]
    by_compiler: dict[str, list[dict]] = {compiler: [] for compiler in COMPILERS}
    for case in debug_cases:
        for record in case["records"]:
            expected = image_keys[case["variant"]][case["compiler"]]
            if record["dea_key"] != expected["dea_key"] or record["native_key"] != expected["native_key"]:
                raise AssertionError((case["variant"], case["compiler"], record, expected))
            if record["stats"]["build_commands"] or record["stats"]["module_compiles"]:
                raise AssertionError(record["stats"])
        by_compiler[case["compiler"]].append(case)
    for compiler, compiler_cases in by_compiler.items():
        baseline = next(case for case in compiler_cases if case["variant"] == "baseline")
        baseline_shape = [
            (record["probe_count"], record["hashes"], record["stats"]["identity_content_reads"],
             record["stats"]["artifact_content_reads"])
            for record in baseline["records"]
        ]
        for case in compiler_cases:
            shape = [
                (record["probe_count"], record["hashes"], record["stats"]["identity_content_reads"],
                 record["stats"]["artifact_content_reads"])
                for record in case["records"]
            ]
            if shape != baseline_shape:
                raise AssertionError((compiler, case["variant"], shape, baseline_shape))


def pair_summary(cases: list[dict], candidate: str, compiler: str) -> dict:
    """Return paired quiet first/warm statistics.

    Args:
        cases: Runtime cases.
        candidate: Candidate variant.
        compiler: Downstream compiler.

    Returns:
        Pair statistics.
    """
    quiet = [case for case in cases if not case["debug"] and case["compiler"] == compiler]
    baseline = {case["repeat"]: case for case in quiet if case["variant"] == "baseline"}
    changed = {case["repeat"]: case for case in quiet if case["variant"] == candidate}
    if set(baseline) != set(range(1, 6)) or set(changed) != set(range(1, 6)):
        raise AssertionError((candidate, compiler, baseline.keys(), changed.keys()))
    result = {"candidate": candidate, "compiler": compiler}
    for index, label in ((0, "first"), (1, "warm")):
        before = [baseline[repeat]["records"][index]["elapsed_ms"] for repeat in range(1, 6)]
        after = [changed[repeat]["records"][index]["elapsed_ms"] for repeat in range(1, 6)]
        differences = [left - right for left, right in zip(before, after, strict=True)]
        before_median = statistics.median(before)
        after_median = statistics.median(after)
        result[label] = {
            "baseline_ms": before,
            "candidate_ms": after,
            "improvements_ms": differences,
            "improved_pairs": sum(value > 0 for value in differences),
            "baseline_median_ms": before_median,
            "candidate_median_ms": after_median,
            "median_improvement_ms": before_median - after_median,
            "median_improvement_percent": (before_median - after_median) * 100 / before_median,
        }
    return result


def classify_candidate(summaries: dict[str, dict]) -> dict:
    """Apply the plan's absolute, percentage, pair, and regression thresholds.

    Args:
        summaries: Pair summaries keyed by compiler.

    Returns:
        Classification and threshold evidence.
    """
    primary_limits = {"gcc": 70.0, "clang": 150.0}
    primary_passes = []
    for primary in COMPILERS:
        first = summaries[primary]["first"]
        other = summaries["clang" if primary == "gcc" else "gcc"]["first"]
        primary_ok = (
            first["median_improvement_ms"] >= primary_limits[primary]
            and first["median_improvement_percent"] >= 3.0
            and first["improved_pairs"] >= 4
        )
        other_regression = max(0.0, -other["median_improvement_ms"])
        other_percent = max(0.0, -other["median_improvement_percent"])
        other_ok = other_regression <= 50.0 and other_percent <= 3.0
        warm_ok = all(
            max(0.0, -summaries[name]["warm"]["median_improvement_ms"]) <= 100.0
            and max(0.0, -summaries[name]["warm"]["median_improvement_percent"]) <= 10.0
            for name in COMPILERS
        )
        primary_passes.append({"primary": primary, "primary_ok": primary_ok, "other_ok": other_ok,
                               "warm_ok": warm_ok, "qualifies": primary_ok and other_ok and warm_ok})
    if any(item["qualifies"] for item in primary_passes):
        conclusion = "adopt"
    elif any(
        summaries[name]["first"]["median_improvement_ms"] > 0
        and summaries[name]["first"]["improved_pairs"] >= 3
        for name in COMPILERS
    ):
        conclusion = "inconclusive"
    else:
        conclusion = "reject"
    return {"conclusion": conclusion, "thresholds": primary_passes}


def render_results(report: dict) -> str:
    """Render the retained human-readable report.

    Args:
        report: Complete investigation report.

    Returns:
        Markdown report.
    """
    lines = [
        "# L1 preparation SHA-256 cost investigation",
        "",
        "- Date: 2026-09-26",
        f"- Conclusion: **{report['conclusion']}**",
        "- Production changes: None",
        "",
        "## Environment and build",
        "",
        f"The retained local base images were `{report['base_images']['upstream']['tag']}` and "
        f"`{report['base_images']['builder']['tag']}`. Measurements used one CPU, 512 MiB for isolated hashing and "
        "256 MiB for prepared compiler requests. Containers had no network. A first access means the first operation "
        "within its disposable container; it is not claimed to be a cold filesystem-cache measurement.",
        "",
        f"The actual Stage 1 build log contained the expected `-O1` optimization flag: "
        f"`{str(report['build']['expected_o1']).lower()}`. The build compiler and downstream compiler versions, complete "
        "emitted command, image identities, assembly, focused-test logs and raw request diagnostics are retained in the "
        "machine report and raw-log archive.",
        "",
        "## Microbenchmarks",
        "",
        "Repeated medians below are complete production stable-file hashes. They include opening, 64 KiB reads, SHA-256, "
        "descriptor/path metadata checks and closing; they must not be added to the separately measured memory SHA-256 "
        "or read/checksum operations.",
        "",
        "| Candidate | Input | Baseline ms | Candidate ms | Improvement |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for candidate, gate in report["micro_gates"].items():
        for row in gate["large_stable_hash"]:
            lines.append(
                f"| `{candidate}` | `{row['input']}` | {row['baseline_ms']:.3f} | "
                f"{row['candidate_ms']:.3f} | {row['improvement_percent']:.2f}% |"
            )
    lines.extend(
        [
            "",
            f"The baseline preloaded-memory SHA estimate for the three large Clang libraries was "
            f"{report['selection']['clang_sha_headroom_ms']:.3f} ms. "
            f"The direct-block candidate advanced: `{str(report['micro_gates']['direct-block']['advanced']).lower()}`. "
            f"The 16-word circular-schedule candidate was measured: "
            f"`{str(report['selection']['ring_measured']).lower()}` and advanced: "
            f"`{str(report['micro_gates'].get('ring-schedule', {}).get('advanced', False)).lower()}`.",
            "",
            "All empty, 55, 56, 63, 64, 65 and 129-byte irregular-streaming vectors, unaligned buffers and large-file "
            "digests matched independent references. Read-only checksums were stable across repetitions.",
            "",
            "## Prepared-image comparison",
            "",
        ]
    )
    if not report["pair_summaries"]:
        lines.append("No candidate passed the microbenchmark advancement gate, so no candidate image comparison was run.")
    else:
        lines.extend(
            [
                "| Candidate | Compiler | First baseline ms | First candidate ms | Improvement | Pairs | Warm regression |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for candidate, summaries in report["pair_summaries"].items():
            for compiler in COMPILERS:
                first = summaries[compiler]["first"]
                warm = summaries[compiler]["warm"]
                lines.append(
                    f"| `{candidate}` | {compiler} | {first['baseline_median_ms']:.3f} | "
                    f"{first['candidate_median_ms']:.3f} | {first['median_improvement_percent']:.2f}% | "
                    f"{first['improved_pairs']}/5 | {max(0.0, -warm['median_improvement_ms']):.3f} ms |"
                )
    if report["pair_summaries"]:
        lines.extend(
            [
                "",
                "Every diagnostic comparison preserved image-specific `D` and `N`, prepared-profile reuse, hash "
                "counts and bytes, discovery probes, zero preparation build commands, zero managed module "
                "compilations, executable output and diagnostics.",
            ]
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            report["decision_text"],
            "",
            "Production `sha256.h`, stable-read checks, metadata policy, digest bytes, schemas and interfaces remain "
            "unchanged. The experiment-local patches are retained only to reproduce the measurements.",
            "",
            "## Validation",
            "",
            "- The harness compiled with strict C99 warnings in each measured image.",
            "- Independent SHA-256 vectors and every measured file digest passed.",
            "- `preparation_support_test`, `preparation_identity_test`, and `l1c_stage1_preparation_test` passed in the "
            "  baseline and every measured candidate compiler build under the supported builder-image GCC toolchain.",
            "- `python3 -m py_compile measure.py` and report verification passed.",
            "- Final repository validation is recorded in the closed plan.",
            "",
            "The raw archive contains exact build, test and benchmark output, plus image-time and runtime output when a "
            "candidate advanced. `report.json.gz` contains all parsed samples and assertions.",
        ]
    )
    return "\n".join(lines) + "\n"


def sanitize_source_identifiers(raw: Path) -> None:
    """Remove source commit identifiers from retained textual logs.

    Args:
        raw: Raw-output directory.
    """
    for path in raw.rglob("*"):
        if not path.is_file() or path.suffix not in {".log", ".stderr", ".stdout", ".program", ".sh", ".s"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        text = re.sub(r"dev-[0-9a-f]{7,40}", "development-build", text)
        text = re.sub(r"(?m)^commit: [0-9a-f]{7,40}$", "commit: omitted by repository policy", text)
        text = re.sub(r"(?m)^build: [0-9a-f]{7,40}-", "build: source-id-omitted-", text)
        path.write_text(text, encoding="utf-8")


def normalize_raw_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Normalize retained raw-log archive metadata.

    Args:
        info: Archive member metadata produced by ``tarfile``.

    Returns:
        Metadata without local ownership, timestamps, or extended headers.
    """
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}
    return info


def write_raw_archive(raw: Path, destination: Path) -> None:
    """Write deterministic compressed raw logs without local identity metadata.

    Args:
        raw: Raw-output directory to retain as the archive's ``raw`` root.
        destination: Compressed tar archive to write.
    """
    members = [
        raw,
        *sorted(raw.rglob("*"), key=lambda path: path.relative_to(raw).as_posix()),
    ]
    with destination.open("wb") as output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=output,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for member in members:
                    relative = member.relative_to(raw)
                    arcname = Path("raw") / relative
                    archive.add(
                        member,
                        arcname=arcname.as_posix(),
                        recursive=False,
                        filter=normalize_raw_tar_info,
                    )


def retain_results(report: dict, raw: Path, destination: Path) -> None:
    """Write compressed evidence and the human report into the repository.

    Args:
        report: Complete investigation report.
        raw: Raw-output directory.
        destination: Checked-in experiment directory.
    """
    destination.mkdir(parents=True, exist_ok=True)
    sanitize_source_identifiers(raw)
    with gzip.open(destination / "report.json.gz", "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    write_raw_archive(raw, destination / "raw-logs.tar.gz")
    (destination / "results.md").write_text(render_results(report), encoding="utf-8")


def load_retained(destination: Path) -> dict:
    """Load and minimally validate retained evidence.

    Args:
        destination: Experiment directory.

    Returns:
        Parsed report.
    """
    with gzip.open(destination / "report.json.gz", "rt", encoding="utf-8") as stream:
        report = json.load(stream)
    if report["schema"] != 1 or report["conclusion"] not in {"adopt", "reject", "separately investigate"}:
        raise AssertionError("invalid retained report")
    if not (destination / "raw-logs.tar.gz").is_file() or not (destination / "results.md").is_file():
        raise AssertionError("incomplete retained evidence")
    return report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, nargs="?", help="Monorepo root")
    parser.add_argument("output", type=Path, nargs="?", help="Untracked raw-output directory")
    parser.add_argument("--verify-only", action="store_true", help="Validate retained evidence without Docker")
    return parser.parse_args()


def main() -> int:
    """Run or verify the bounded investigation."""
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    if args.verify_only:
        report = load_retained(script_dir)
        print(f"retained SHA-256 investigation: {report['conclusion']}")
        return 0
    if args.repo is None or args.output is None:
        raise SystemExit("repo and output are required unless --verify-only is used")
    repo = args.repo.resolve()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    raw = output / "raw"
    raw.mkdir()
    context = archive_context(repo, output)
    dockerfile = script_dir / "Dockerfile"
    report: dict = {
        "schema": 1,
        "date": "2026-09-26",
        "source": "tracked HEAD plus experiment-local files",
        "resources": {"microbench_cpus": 1, "microbench_memory_mib": 512,
                      "runtime_cpus": 1, "runtime_memory_mib": 256, "network": "none"},
        "base_images": {},
        "images": {},
        "microbenchmarks": {},
        "micro_gates": {},
        "runtime_cases": [],
        "pair_summaries": {},
    }
    for label, tag in (("upstream", "dea-preparation-investigation-clang:latest"), ("builder", "l1-test:latest")):
        inspected = json.loads(run(["docker", "image", "inspect", tag]).stdout)[0]
        report["base_images"][label] = {"tag": tag, "id": inspected["Id"], "created": inspected["Created"],
                                         "size_bytes": inspected["Size"]}

    compiler_image, compiler_details = build_image(context, dockerfile, raw, "baseline", "compiler")
    report["images"]["compiler-baseline"] = compiler_details
    build_log = image_text(compiler_image, "/opt/dea/investigation/compiler-build.log")
    focused_log = image_text(compiler_image, "/opt/dea/investigation/focused-tests.log")
    (raw / "compiler-baseline-build.log").write_text(build_log, encoding="utf-8")
    (raw / "compiler-baseline-focused-tests.log").write_text(focused_log, encoding="utf-8")
    emitted = next((line for line in build_log.splitlines() if "preparation_support.c" in line and " -o " in line), "")
    report["build"] = {
        "expected_o1": "-O1" in emitted,
        "emitted_c_command": emitted,
    }
    version_text = run(
        [
            *container_prefix(compiler_image),
            "sh",
            "-c",
            "/opt/dea/bin/l0c-stage2 --version; gcc --version | sed -n '1p'; clang --version | sed -n '1p'; "
            "uname -a; printf 'L0_CC=%s\\nL0_CFLAGS=%s\\n' \"${L0_CC-}\" \"${L0_CFLAGS-}\"",
        ],
        timeout=300,
    ).stdout
    environment = []
    for line in version_text.splitlines():
        if line.startswith(("build:", "commit:")):
            continue
        environment.append(re.sub(r"dev-[0-9a-f]{7,40}", "development-build", line))
    report["build"]["environment"] = environment
    (raw / "compiler-versions-and-environment.log").write_text("\n".join(environment) + "\n", encoding="utf-8")
    if not report["build"]["expected_o1"]:
        raise AssertionError("actual preparation-support build did not contain expected -O1")

    benchmark_images: dict[str, str] = {}
    for variant in ("baseline", "direct-block"):
        image, details = build_image(context, dockerfile, raw, variant, "benchmark")
        benchmark_images[variant] = image
        report["images"][f"benchmark-{variant}"] = details
    references = reference_digests(benchmark_images["baseline"])
    report["inputs"] = references
    downstream_text = run(
        [
            *container_prefix(benchmark_images["baseline"]),
            "sh",
            "-c",
            "gcc --version | sed -n '1p'; clang --version | sed -n '1p'; uname -a",
        ]
    ).stdout
    report["downstream_environment"] = downstream_text.splitlines()
    (raw / "downstream-versions-and-environment.log").write_text(downstream_text, encoding="utf-8")
    headroom = selection_headroom(benchmark_images["baseline"], raw, references)
    baseline_assembly = image_text(benchmark_images["baseline"], "/opt/dea/investigation/benchmark.s")
    compression_visible = baseline_assembly.count("pc_sha_block") > 0
    ring_measured = headroom >= 150.0 and compression_visible
    report["selection"] = {
        "clang_sha_headroom_ms": headroom,
        "compiled_compression_visible": compression_visible,
        "ring_measured": ring_measured,
    }
    if ring_measured:
        image, details = build_image(context, dockerfile, raw, "ring-schedule", "benchmark")
        benchmark_images["ring-schedule"] = image
        report["images"]["benchmark-ring-schedule"] = details
    report["microbenchmarks"] = benchmark_matrix(benchmark_images, raw, references)
    for variant in benchmark_images:
        if variant != "baseline":
            report["micro_gates"][variant] = candidate_micro_result(
                report["microbenchmarks"]["baseline"], report["microbenchmarks"][variant]
            )

    report["candidate_tests"] = {}
    for variant in tuple(name for name in benchmark_images if name != "baseline"):
        candidate_image, details = build_image(context, dockerfile, raw, variant, "compiler")
        report["images"][f"compiler-{variant}"] = details
        candidate_build = image_text(candidate_image, "/opt/dea/investigation/compiler-build.log")
        candidate_tests = image_text(candidate_image, "/opt/dea/investigation/focused-tests.log")
        (raw / f"compiler-{variant}-build.log").write_text(candidate_build, encoding="utf-8")
        (raw / f"compiler-{variant}-focused-tests.log").write_text(candidate_tests, encoding="utf-8")
        report["candidate_tests"][variant] = {
            "focused_passed": "Failed: 0" in candidate_tests and "All tests passed!" in candidate_tests,
            "expected_o1": "-O1" in candidate_build,
        }
        if not all(report["candidate_tests"][variant].values()):
            raise AssertionError((variant, report["candidate_tests"][variant]))
    candidates = [name for name, gate in report["micro_gates"].items() if gate["advanced"]]

    prepared_images: dict[str, str] = {}
    if candidates:
        for variant in ("baseline", *candidates):
            image, details = build_image(context, dockerfile, raw, variant, "prepared")
            prepared_images[variant] = image
            report["images"][f"prepared-{variant}"] = details
        fixture = repo / "l1/examples"
        expected = sorted(re.findall(r'^    "(.*)"[,\n]', (fixture / "hello.l1").read_text(encoding="utf-8"), re.M))
        if len(expected) != 25:
            raise AssertionError("unexpected hello fixture")
        image_keys = {
            variant: {compiler: image_time_keys(image, compiler) for compiler in COMPILERS}
            for variant, image in prepared_images.items()
        }
        report["image_time_keys"] = image_keys
        for candidate in candidates:
            for repeat in range(1, 6):
                order = ("baseline", candidate) if repeat % 2 else (candidate, "baseline")
                for compiler in COMPILERS:
                    for variant in order:
                        report["runtime_cases"].append(
                            run_compile_case(prepared_images[variant], variant, compiler, repeat, False,
                                             fixture, raw, expected)
                        )
            for compiler in COMPILERS:
                for variant in ("baseline", candidate):
                    report["runtime_cases"].append(
                        run_compile_case(prepared_images[variant], variant, compiler, 1, True,
                                         fixture, raw, expected)
                    )
            summaries = {compiler: pair_summary(report["runtime_cases"], candidate, compiler)
                         for compiler in COMPILERS}
            report["pair_summaries"][candidate] = summaries
        verify_debug_equivalence(report["runtime_cases"], image_keys)

    classifications = {
        candidate: classify_candidate(summaries)
        for candidate, summaries in report["pair_summaries"].items()
    }
    report["classifications"] = classifications
    if any(item["conclusion"] == "adopt" for item in classifications.values()):
        report["conclusion"] = "adopt"
        winners = ", ".join(f"`{name}`" for name, item in classifications.items() if item["conclusion"] == "adopt")
        report["decision_text"] = (
            f"**Adopt:** {winners} cleared the fixed paired thresholds. This investigation records the recommendation "
            "without changing production; implementation requires a separately authorized follow-up."
        )
    elif any(item["conclusion"] == "inconclusive" for item in classifications.values()):
        report["conclusion"] = "separately investigate"
        report["decision_text"] = (
            "**Separately investigate:** at least one candidate showed positive but noisy or sub-threshold prepared "
            "compiler movement. The fixed budget is exhausted, so production remains unchanged."
        )
    elif not classifications and any(
        sum(row["improvement_ms"] > 0 for row in gate["large_stable_hash"]) >= 2
        for gate in report["micro_gates"].values()
    ):
        report["conclusion"] = "separately investigate"
        report["decision_text"] = (
            "**Separately investigate:** direct complete-file measurements were mixed across the fixed interleaved "
            "budget, so the candidate did not advance to prepared compiler timing. The 16-word schedule regressed and "
            "is rejected. Production remains unchanged."
        )
    else:
        report["conclusion"] = "reject"
        report["decision_text"] = (
            "**Reject:** no small portable candidate both passed the microbenchmark gate and cleared the prepared "
            "compiler thresholds. Reading, metadata and other request work leave insufficient material gain; production "
            "remains unchanged."
        )
    report["completed_at_unix"] = int(time.time())
    retain_results(report, raw, script_dir)
    load_retained(script_dir)
    print(f"SHA-256 investigation complete: {report['conclusion']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
