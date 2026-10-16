#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#
"""Compare unchanged, direct-block, and installed platform SHA-256 backends."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[6]
RELATIVE = HERE.relative_to(REPO)
VARIANTS = ("current", "direct-block", "platform")


def direct_header(source: str) -> str:
    """Apply the previously investigated complete-block candidate in memory.

    Args:
        source: Current portable SHA-256 header text.

    Returns:
        Experiment-local direct-block header text.
    """
    start = source.index("static void pc_sha_update(")
    end = source.index("static void pc_sha_finish(", start)
    replacement = """static void pc_sha_update(PcSha *s, const void *data, size_t n) {
    const unsigned char *p = data;
    size_t take;
    s->bytes += n;
    if (s->used) {
        take = 64 - s->used;
        if (take > n) take = n;
        memcpy(s->block + s->used, p, take);
        s->used += take;
        p += take;
        n -= take;
        if (s->used < 64) return;
        pc_sha_block(s, s->block);
        s->used = 0;
    }
    while (n >= 64) {
        pc_sha_block(s, p);
        p += 64;
        n -= 64;
    }
    if (n) {
        memcpy(s->block, p, n);
        s->used = n;
    }
}
"""
    return source[:start] + replacement + source[end:]


def unrolled_header(source: str) -> str:
    """Unroll eight compression rounds while preserving the portable message schedule.

    Args:
        source: Current portable SHA-256 header text.

    Returns:
        Experiment-local header with the same 64-word schedule and update loop.
    """
    start = source.index("    for (i = 0; i < 64; ++i) {")
    end = source.index("    s->h[0] += a;", start)
    replacement = r"""#define PC_HASH_ROUND(a, b, c, d, e, f, g, h, index) do { \
    t1 = (h) + (pc_rotr((e), 6) ^ pc_rotr((e), 11) ^ pc_rotr((e), 25)) + \
         (((e) & (f)) ^ (~(e) & (g))) + k[(index)] + w[(index)]; \
    t2 = (pc_rotr((a), 2) ^ pc_rotr((a), 13) ^ pc_rotr((a), 22)) + \
         (((a) & (b)) ^ ((a) & (c)) ^ ((b) & (c))); \
    (d) += t1; \
    (h) = t1 + t2; \
} while (0)
    for (i = 0; i < 64; i += 8) {
        PC_HASH_ROUND(a, b, c, d, e, f, g, h, i);
        PC_HASH_ROUND(h, a, b, c, d, e, f, g, i + 1);
        PC_HASH_ROUND(g, h, a, b, c, d, e, f, i + 2);
        PC_HASH_ROUND(f, g, h, a, b, c, d, e, i + 3);
        PC_HASH_ROUND(e, f, g, h, a, b, c, d, i + 4);
        PC_HASH_ROUND(d, e, f, g, h, a, b, c, i + 5);
        PC_HASH_ROUND(c, d, e, f, g, h, a, b, i + 6);
        PC_HASH_ROUND(b, c, d, e, f, g, h, a, i + 7);
    }
#undef PC_HASH_ROUND
"""
    return source[:start] + replacement + source[end:]


def quoted(command: list[str]) -> str:
    """Render exact argument boundaries for the temporary shell driver.

    Args:
        command: Command argument list.

    Returns:
        Shell-quoted command text.
    """
    return shlex.join(command)


def measure(args: argparse.Namespace) -> dict:
    """Build isolated candidates, verify every digest, and retain samples.

    Args:
        args: Parsed command-line configuration.

    Returns:
        Sanitized measurements and correctness assertions.

    Raises:
        AssertionError: A digest, byte count, or input invariant differs.
        subprocess.CalledProcessError: A compiler or benchmark fails.
    """
    source = (HERE / "hash-baseline-sha256.h").read_text()
    variants = ("current", "unrolled") if args.portable_unroll else VARIANTS
    with tempfile.TemporaryDirectory(prefix=".hash-", dir=HERE) as directory:
        scratch = Path(directory).resolve()
        support = scratch / "measured-support"
        shutil.copytree(REPO / "l1/compiler/support", support)
        subprocess.run(["git", "apply", "--unsafe-paths", "-p4", f"--directory={support}",
                        str(HERE.parent / "measured-preparation.patch")], check=True)
        (scratch / "direct.h").write_text(direct_header(source))
        (scratch / "unrolled.h").write_text(unrolled_header(source))
        for label, size in (("control-4k", 4096), ("control-8m", 8 * 1024 * 1024)):
            block = bytes((i * 131 + 17) & 255 for i in range(256))
            (scratch / f"{label}.bin").write_bytes((block * ((size + 255) // 256))[:size])
        root = Path("/src") if args.docker_image else REPO
        work = Path("/evidence") if args.docker_image else scratch
        compiler = "gcc" if args.docker_image else args.cc
        inputs = [
            ("control-4k", str(work / "control-4k.bin")),
            ("control-8m", str(work / "control-8m.bin")),
        ]
        if args.docker_image:
            inputs.extend([
                ("gcc-cc1", "/usr/libexec/gcc/x86_64-linux-gnu/14/cc1"),
                ("llvm", "/usr/lib/x86_64-linux-gnu/libLLVM.so.19.1"),
                ("clang-cpp", "/usr/lib/x86_64-linux-gnu/libclang-cpp.so.19.1"),
                ("z3", "/usr/lib/x86_64-linux-gnu/libz3.so.4"),
            ])
        else:
            inputs.append(("host-clang", subprocess.check_output(
                ["xcrun", "--find", "clang"], text=True).strip()))
        script = ["set -eu", "uname -sm >&2", f"{shlex.quote(compiler)} --version >&2"]
        if args.docker_image and not args.portable_unroll:
            script.append("openssl version >&2")
        for variant in variants:
            command = [compiler, "-std=c99", f"-O{args.optimization}", "-Wall", "-Wextra",
                       "-Werror", "-pedantic"]
            if args.reader_only:
                command.append("-DHASH_READER_CHECKS")
            if variant == "current":
                command.append(f'-DHASH_HEADER="{root / RELATIVE / "hash-baseline-sha256.h"}"')
            elif variant == "direct-block":
                command.append(f'-DHASH_HEADER="{work / "direct.h"}"')
            elif variant == "unrolled":
                command.append(f'-DHASH_HEADER="{work / "unrolled.h"}"')
            elif variant == "platform":
                command.append("-DHASH_PLATFORM")
                if not args.docker_image:
                    command.append("-Wno-deprecated-declarations")
            command.extend([f'-DPREPARATION_SUPPORT="{work / "measured-support/preparation_support.c"}"',
                            str(root / RELATIVE / "hash-benchmark.c"),
                            str(work / "measured-support/compiler_support.c")])
            if variant == "platform" and args.docker_image:
                command.append("/usr/lib/x86_64-linux-gnu/libcrypto.so.3")
            command.extend(["-o", str(work / variant)])
            script.append(quoted(command))
            script.append("printf '%s\\n' " + shlex.quote(json.dumps(
                {"kind": "section", "variant": variant, "input": "vectors"})))
            script.append(quoted([str(work / variant), "vectors"]))
            if args.reader_only:
                script.append(quoted([str(work / variant), "reader-checks", str(work / "reader.bin")]))
        # Independent reference commands run outside every measured operation.
        reference = "sha256sum" if args.docker_image else "shasum -a 256"
        for label, path in (() if args.reader_only else inputs):
            script.append("printf '%s\\n' " + shlex.quote(json.dumps(
                {"kind": "section", "variant": "reference", "input": label})))
            script.append(f"wc -c < {shlex.quote(path)}")
            script.append(f"{reference} {shlex.quote(path)}")
        for repetition in (() if args.reader_only else range(args.pairs)):
            order = variants if repetition % 2 == 0 else tuple(reversed(variants))
            for label, path in inputs:
                for variant in order:
                    script.append("printf '%s\\n' " + shlex.quote(json.dumps(
                        {"kind": "section", "variant": variant, "input": label,
                         "pair": repetition})))
                    for mode in ("65536", "irregular"):
                        script.append(quoted([str(work / variant), "memory", path, mode, "1"]))
                    script.append(quoted([str(work / variant), "stable", path, "1"]))
                if repetition == 0:
                    script.append("printf '%s\\n' " + shlex.quote(json.dumps(
                        {"kind": "section", "variant": "current", "input": label,
                         "pair": repetition})))
                    script.append(quoted([str(work / "current"), "read", path, "2"]))
        driver = scratch / "run.sh"
        driver.write_text("\n".join(script) + "\n")
        if args.docker_image:
            command = ["docker", "run", "--rm", "--network", "none", "--cpus", "1",
                       "--memory", "512m", "-v", f"{REPO}:/src:ro", "-v", f"{scratch}:/evidence",
                       args.docker_image, "sh", "/evidence/run.sh"]
        else:
            command = ["sh", str(driver)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=900)
        if completed.returncode:
            raise subprocess.CalledProcessError(completed.returncode, command,
                                                completed.stdout, completed.stderr)
    sections, references, samples, vectors, reader_checks = {}, {}, [], [], []
    standard = [b"", b"abc", b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"]
    reference_lines = []
    for line in completed.stdout.splitlines():
        if not line.startswith("{"):
            reference_lines.append(line)
            if len(reference_lines) == 2:
                references[sections["input"]] = {
                    "bytes": int(reference_lines[0]), "digest": reference_lines[1].split()[0]}
                reference_lines = []
            continue
        record = json.loads(line)
        if record["kind"] == "section":
            sections = record
            continue
        record = {**record, **{key: value for key, value in sections.items() if key != "kind"}}
        if record["kind"] in ("vector", "standard-vector"):
            if record["kind"] == "standard-vector":
                data = standard[record["index"]]
            else:
                data = bytes(((i + 1) * 131 + 17) & 255 for i in range(record["bytes"]))
            assert record["digest"] == hashlib.sha256(data).hexdigest(), record
            vectors.append(record)
        elif record["kind"] == "reader-checks":
            assert all(record[name] for name in ("stable", "short_read", "failed_read", "changed_read", "missing"))
            reader_checks.append(record)
        else:
            expected = references[record["input"]]
            assert record["bytes"] == expected["bytes"], record
            if record["digest"] is not None:
                assert record["digest"] == expected["digest"], record
            samples.append(record)
    summaries = []
    for label, _ in (() if args.reader_only else inputs):
        for operation, mode in (("memory-sha256", "65536"), ("memory-sha256", "irregular"),
                                ("stable-hash", "65536")):
            rows = {}
            for variant in variants:
                selected = [r for r in samples if r["input"] == label and r["variant"] == variant
                            and r["operation"] == operation and r["mode"] == mode]
                assert len(selected) == args.pairs
                rows[variant] = {"median_ms": statistics.median(r["wall_ms"] for r in selected),
                                 "min_ms": min(r["wall_ms"] for r in selected),
                                 "max_ms": max(r["wall_ms"] for r in selected)}
            summaries.append({"input": label, "operation": operation, "mode": mode, "backends": rows})
    report = {
        "schema": 1, "date": "2026-10-16", "environment": args.label,
        "system": "Linux x86_64" if args.docker_image else f"{platform.system()} {platform.machine()}",
        "compiler": completed.stderr.splitlines()[1:], "optimization": f"-O{args.optimization}",
        "backends": list(variants),
        "platform_backend": None if args.portable_unroll else (
            "OpenSSL EVP SHA-256" if args.docker_image else "CommonCrypto SHA-256"),
        "constraints": {"cpu_limit": 1 if args.docker_image else None,
                        "memory_mib": 512 if args.docker_image else None,
                        "cold_filesystem_claimed": False},
        "pairs": args.pairs, "inputs": references, "vectors": vectors,
        "samples": samples, "summaries": summaries, "reader_checks": reader_checks,
        "assertions": {"all_independent_digests_match": True, "all_byte_counts_match": True},
    }
    aliases = {path: f"<input:{label}>" for label, path in inputs}

    def replace_strings(value: object, replacements: dict[str, str]) -> object:
        """Replace exact path string values while preserving container shape and scalars."""
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [replace_strings(item, replacements) for item in value]
        if isinstance(value, dict):
            return {key: replace_strings(item, replacements) for key, item in value.items()}
        return value

    sanitized = replace_strings(report, aliases)
    assert replace_strings(sanitized, {alias: path for path, alias in aliases.items()}) == report
    return sanitized


def main() -> None:
    """Parse bounded experiment options and write the sanitized JSON report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image")
    parser.add_argument("--cc", default="clang")
    parser.add_argument("--optimization", choices=("1", "2"), default="2")
    parser.add_argument("--pairs", type=int, choices=range(3, 8), default=5)
    parser.add_argument("--reader-only", action="store_true")
    parser.add_argument("--portable-unroll", action="store_true")
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = measure(args)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"benchmark command failed:\n{error.stderr}") from error
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Validated {len(report['vectors'])} vectors and {len(report['samples'])} measurements.")


if __name__ == "__main__":
    main()
