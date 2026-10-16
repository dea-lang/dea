#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Compare isolated discovery policies with equal digest backends and source inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shlex
import shutil
import statistics
import subprocess


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run one checked command and retain its diagnostics.

    Args:
        command: Exact argument vector to execute.
        **kwargs: Additional subprocess execution options.

    Returns:
        The completed process and its captured output.

    Raises:
        RuntimeError: If the command exits unsuccessfully.
    """
    result = subprocess.run(command, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"command failed: {command!r}\n{result.stdout}\n{result.stderr}")
    return result


def main() -> None:
    """Build equal-backend controls, interleave requests and retain individual observations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", default="dea-sha256-prepared-baseline:local")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--all-adapters-experiment", action="store_true")
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    repo, output = args.repository.resolve(), args.output.resolve()
    attachment = Path(__file__).resolve().parent
    if output.exists() and any(output.iterdir()):
        parser.error("measurement output must be a new or empty directory")
    output.mkdir(parents=True, exist_ok=True)
    for variant in ("baseline", "candidate"):
        support = output / f"{variant}-tree/l1/compiler/support"
        if support.exists():
            shutil.rmtree(support)
        shutil.copytree(repo / "l1/compiler/support", support)
        run(["git", "apply", "--unsafe-paths", f"--directory={variant}-tree",
             str(attachment.parent / "measured-preparation.patch")], cwd=output)
    run(["git", "apply", "--reverse", "--unsafe-paths", "--directory=baseline-tree",
         str(attachment / "discovery-batching.patch")], cwd=output)
    if args.all_adapters_experiment:
        identity = output / "candidate-tree/l1/compiler/support/preparation/identity.h"
        text = identity.read_text()
        start = text.index("static int pc_dependency_batch_supported(const PcContext *c) {")
        end = text.index("\n}\n", start) + 3
        text = text[:start] + (
            "static int pc_dependency_batch_supported(const PcContext *c) {\n"
            "    return strcmp(c->family, \"tcc\") != 0;\n}\n") + text[end:]
        identity.write_text(text)
    capture = output / "capture"
    capture.mkdir(exist_ok=True)
    capture.chmod(0o777)
    if args.native:
        work = output / "native-work"
        work.mkdir(exist_ok=True)
        sources, evidence, owned = str(repo), str(output), str(work)
        compilers = ["/usr/bin/clang"]
    else:
        sources, evidence, owned = "/source", "/evidence", "/work"
        compilers = ["/usr/bin/gcc", "/usr/bin/clang"]
    quote = shlex.quote
    lines = ["set -eu", f"mkdir -p {quote(owned)}/compiler/src {quote(owned)}/compiler/support",
             f"cp -R {quote(sources)}/l1/compiler/shared {quote(owned)}/compiler/",
             f"cp -R {quote(sources)}/l1/build/dea/include {quote(owned)}/headers",
             f"printf 'fixed compiler fixture\\n' > {quote(owned)}/self"]
    for variant in ("baseline", "candidate"):
        support = f"{evidence}/{variant}-tree/l1/compiler/support"
        lines.append(shlex.join([compilers[0], "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
                                 "-I", support, f"{sources}/{attachment.relative_to(repo)}/discovery-harness.c",
                                 support + "/compiler_support.c", "-o", owned + "/" + variant]))
    expected = []
    for compiler in compilers:
        name = Path(compiler).name
        lines.append(shlex.join([compiler, "--version"]) + f" > {quote(evidence)}/capture/{name}-version.txt")
        for repetition in range(args.repetitions):
            for variant in (("baseline", "candidate") if repetition % 2 == 0 else ("candidate", "baseline")):
                cache = f"{owned}/cache-{name}-{repetition}-{variant}"
                for scenario in ("cold", "warm", "partial"):
                    label = f"{name}-{repetition + 1}-{variant}-{scenario}"
                    if scenario == "partial":
                        lines.append(f"touch {quote(owned)}/headers/unrelated-{quote(label)}")
                    command = [owned + "/" + variant, owned + "/compiler", sources + "/l1/build/dea",
                               owned + "/self", cache, compiler, owned + "/headers", "3", label]
                    lines.append(shlex.join(command) + f" > {quote(evidence)}/capture/{label}.json"
                                 f" 2> {quote(evidence)}/capture/{label}.stderr")
                    expected.append((label, name, repetition + 1, variant, scenario))
    script = output / "case.sh"
    script.write_text("\n".join(lines) + "\n")
    if args.native:
        run(["sh", str(script)], timeout=900)
        environment = {"platform": platform.platform(), "architecture": platform.machine()}
    else:
        metadata = json.loads(run(["docker", "image", "inspect", args.image]).stdout)[0]
        run(["docker", "run", "--rm", "--network", "none", "--read-only", "--cpus", "1", "--memory", "256m",
             "--memory-swap", "256m", "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt",
             "no-new-privileges", "--tmpfs", "/work:rw,size=128m,exec,mode=1777", "-e", "HOME=/work",
             "-e", "TMPDIR=/work", "-v", str(repo) + ":/source:ro", "-v", str(output) + ":/evidence:rw",
             "-w", "/work", args.image, "sh", "/evidence/case.sh"], timeout=900)
        environment = {"image": args.image, "image_id": metadata["Id"], "architecture": metadata["Architecture"],
                       "cpus": 1, "memory_bytes": 268435456, "pids_limit": 64, "work_tmpfs_bytes": 134217728}
    records = []
    for label, compiler, repetition, variant, scenario in expected:
        record = json.loads((capture / f"{label}.json").read_text())
        events = [json.loads(line.removeprefix("Preparation observation: "))
                  for line in (capture / f"{label}.stderr").read_text().splitlines()
                  if line.startswith("Preparation observation: ")]
        assert record["success"] == 1 and not record["error"] and not record["ineligible"], record
        record.update(compiler=compiler, repetition=repetition, variant=variant, scenario=scenario,
                      probe_events=[event for event in events if event["event"] == "probe"],
                      hash_bytes=sum(event["bytes"] for event in events if event["event"] == "hash"),
                      toolchain_hash_bytes=sum(event["bytes"] for event in events
                                               if event["event"] == "hash" and event["category"] == "toolchain-input"),
                      large_toolchain_inputs=[{"path": event["path"], "bytes": event["bytes"]} for event in events
                                              if event["event"] == "hash" and event["category"] == "toolchain-input"
                                              and event["bytes"] >= 1024 * 1024])
        record["identity_equal"] = True
        records.append(record)
    assert len({record["dea_key"] for record in records}) == 1
    for compiler in {record["compiler"] for record in records}:
        selected = [record for record in records if record["compiler"] == compiler]
        assert all(record["native_identity"] == selected[0]["native_identity"] for record in selected)
    # Identities are checked in full locally; retain their digest rather than repetitive filesystem inventories.
    for record in records:
        del record["native_identity"]
    summary = []
    for compiler in {record["compiler"] for record in records}:
        for variant in ("baseline", "candidate"):
            for scenario in ("cold", "warm", "partial"):
                samples = [record for record in records if (record["compiler"], record["variant"], record["scenario"])
                           == (compiler, variant, scenario)]
                summary.append(dict(compiler=compiler, variant=variant, scenario=scenario,
                                    elapsed_us=[record["elapsed_us"] for record in samples],
                                    median_elapsed_us=statistics.median(record["elapsed_us"] for record in samples),
                                    probes=sorted({record["probes"] for record in samples}),
                                    hash_bytes=sorted({record["hash_bytes"] for record in samples}),
                                    toolchain_hash_bytes=sorted({record["toolchain_hash_bytes"] for record in samples})))
    report = dict(schema=1, repetitions=args.repetitions, environment=environment, records=records, summary=summary,
                  candidate_policy="all-adapters-experiment" if args.all_adapters_experiment else "apple-clang-macos",
                  compiler_versions={path.stem: path.read_text() for path in capture.glob("*-version.txt")})
    # Sanitize string values only. Numerical measurements and collection structure are retained exactly.
    replacements = [(str(repo), "<repository>"), (str(output), "<measurement>")]

    def sanitize(value):
        """Replace local path strings without changing measured values or collection shape.

        Args:
            value: JSON-compatible evidence value.

        Returns:
            The same structure with public path placeholders in string values.
        """
        if isinstance(value, str):
            for old, new in replacements:
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    report = sanitize(report)
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
