#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Measure native preparation capability with isolated, separate-process consumers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time

L1_ROOT = Path(__file__).resolve().parents[1]
STAGES = ("cold", "warm-auto", "warm-guard", "invalidated-guard", "invalidated-auto")
OBSERVABILITY_STAGES = ("observe-warm-1", "observe-warm-2", "observe-cwd-1", "observe-cwd-2",
                        "observe-copy-1", "observe-copy-2", "observe-copy-no-memos-1",
                        "observe-copy-no-memos-2", "observe-explicit-sys-root-1",
                        "observe-explicit-sys-root-2")
COUNTERS = ("module_compiles", "build_commands", "native_resolutions", "identity_content_reads",
            "artifact_content_reads", "metadata_checks", "probes", "option_file_parses", "option_root_expansions")
PRIVATE_REASONS = {
    "opaque compiler wrapper is invocable but cannot authorize persistent reuse",
    "opaque archive-tool wrapper cannot authorize persistent reuse",
    "opaque subordinate compiler-tool wrapper cannot authorize persistent reuse",
    "unsupported native compiler indirection in the environment",
    "unsupported dynamic-loader indirection in the environment",
    "Clang external assembler selection is outside persistent reuse support",
    "compiler plugin, profile, or opaque option indirection is outside persistent reuse support",
}
ARCHIVER_BOUNDARY = "selected compiler must locate a usable runtime archiver with -print-prog-name=ar"
EXPECTED_OUTPUT = "preparation-probe-ok\n"


class ProbeError(RuntimeError):
    """An incomplete or unexpected observation, never a compatibility outcome."""


def require(condition: bool, message: str) -> None:
    """Require evidence, raising ProbeError when it is absent.

    Args:
        condition: Whether the required observation holds.
        message: Failure explanation to preserve in the report.

    Raises:
        ProbeError: If the condition is false.
    """
    if not condition:
        raise ProbeError(message)


def fields(stderr: str, label: str) -> list[str]:
    """Extract exact debug records.

    Args:
        stderr: Compiler diagnostics.
        label: Record prefix without its colon.

    Returns:
        Matching values in output order.
    """
    return re.findall(r"^" + re.escape(label) + r": (.*)$", stderr, re.MULTILINE)


def observation_measurements(stderr: str, partial: bool = False) -> dict:
    """Parse debug records independently of end-of-command identity statistics.

    Args:
        stderr: Complete or interrupted compiler output.
        partial: Retain valid records and record malformed lines instead of raising.

    Returns:
        Observations, categorized accounting and any partial parsing errors.

    Raises:
        ProbeError: If a complete record violates the observation schema.
        ValueError: If complete output contains invalid JSON.
    """
    observations, errors = [], []
    for raw in fields(stderr, "Preparation observation"):
        try:
            observation = json.loads(raw)
            require(isinstance(observation, dict) and type(observation.get("schema")) is int and
                    observation["schema"] == 1 and isinstance(observation.get("event"), str),
                    "invalid preparation observation")
            if observation["event"] in ("hash", "probe", "span"):
                require(type(observation.get("elapsed_us")) is int and observation["elapsed_us"] >= 0,
                        "invalid observation duration")
            if observation["event"] == "hash":
                require(isinstance(observation.get("category"), str) and
                        type(observation.get("bytes")) is int and observation["bytes"] >= 0,
                        "invalid hash accounting")
            observations.append(observation)
        except (ValueError, ProbeError) as exc:
            if not partial:
                raise
            errors.append(str(exc))
    hashes: dict[str, dict[str, int]] = {}
    for observation in observations:
        if observation["event"] == "hash":
            totals = hashes.setdefault(observation["category"], {"count": 0, "bytes": 0, "elapsed_us": 0})
            totals["count"] += 1
            totals["bytes"] += observation["bytes"]
            totals["elapsed_us"] += observation["elapsed_us"]
    return {"observations": observations, "observation_errors": errors, "hashing": hashes,
            "spans": [item for item in observations if item["event"] == "span"],
            "probes": [item for item in observations if item["event"] == "probe"],
            "providers": [item for item in observations if item["event"] == "provider"]}


def measurements(stderr: str) -> dict:
    """Parse one native context, including failed commands.

    Args:
        stderr: Raw compiler diagnostics.

    Returns:
        Counters, selected identity and diagnostic evidence.

    Raises:
        ProbeError: If mandatory statistics are missing or malformed.
        ValueError: If a JSON record is invalid.
    """
    stats = fields(stderr, "Preparation statistics")
    require(len(stats) == 1, "expected exactly one preparation statistics record")
    counts = json.loads(stats[0])
    require(isinstance(counts, dict) and all(type(counts.get(key)) is int and counts[key] >= 0
                                           for key in COUNTERS), "invalid preparation counters")
    result = {"statistics": counts,
              **observation_measurements(stderr),
              "stdlib_validations": stderr.count("Starting analysis for entry module '_dea_preparation'"),
              "managed_analyses": len(re.findall(r"Starting analysis for entry module '(?:std|sys)\.", stderr)),
              "diagnostics": re.findall(r"^.*error: \[([^]]+)\] (.*)$", stderr, re.MULTILINE),
              "private_reasons": fields(stderr, "Fresh preparation"),
              "reuse": fields(stderr, "Reuse prepared profile")}
    for label, key in (("Preparation native key", "native_key"), ("Preparation selected", "selected"),
                       ("Preparation native inputs", "identity")):
        values = fields(stderr, label)
        require(len(values) == 1, f"expected exactly one {label} record")
        result[key] = json.loads(values[0]) if key == "identity" and values[0] else values[0]
    identity = result.pop("identity")
    result["toolchain"] = {key: identity["toolchain"].get(key) for key in
                           ("invocation", "family", "target", "archiver")} if identity else None
    return result


class Probe:
    """Own one probe's environment, retained subprocess logs and evidence checks."""

    def __init__(self, args: argparse.Namespace, report: dict, root: Path):
        """Initialize isolated process state.

        Args:
            args: Reporter CLI options.
            report: Mutable result document, also retained when an exception occurs.
            root: Empty temporary fixture directory.
        """
        self.args, self.report, self.root = args, report, root
        self.env = dict(os.environ)
        for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
            self.env.pop(name, None)
        self.cache = root / "cache"
        self.cache.mkdir()
        self.cc = ""

    def run(self, label: str, argv: list[str], record: dict,
            cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        """Run a bounded command and retain output before interpreting it.

        Args:
            label: Unique log basename and failure stage.
            argv: Literal executable and arguments, without shell interpolation.
            record: Destination for invocation metadata.
            cwd: Optional invocation directory; defaults to the fixture root.

        Returns:
            Captured subprocess result, including nonzero exits.

        Raises:
            OSError: If the process cannot start.
            subprocess.TimeoutExpired: If the process exceeds the deadline.
        """
        self.report["stage"] = label
        invocation_cwd = cwd or self.root
        record.update(argv=argv, exit_code=None, stdout_log=f"{label}.stdout.log", stderr_log=f"{label}.stderr.log")
        (self.args.output_dir / f"{label}.command.json").write_text(
            json.dumps({"argv": argv, "cwd": str(invocation_cwd)}, indent=2) + "\n", encoding="utf-8")
        stdout, stderr = "", ""
        started = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=invocation_cwd, env=self.env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=self.args.timeout)
            stdout, stderr = result.stdout, result.stderr
            record["exit_code"] = result.returncode
            return result
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout or b"", exc.stderr or b""
            record["timeout"] = True
            raise
        except OSError as exc:
            stderr = str(exc)
            raise
        finally:
            record["elapsed_ms"] = (time.monotonic() - started) * 1000.0
            if "--run" in argv:
                text = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
                record.update(observation_measurements(text, partial=True))
            for suffix, value in (("stdout", stdout), ("stderr", stderr)):
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                (self.args.output_dir / f"{label}.{suffix}.log").write_text(value, encoding="utf-8")

    def fixture(self) -> None:
        """Copy only compiler, semantic and runtime inputs into the owned fixture.

        Raises:
            OSError: If an input cannot be copied.
            ProbeError: If the requested compiler cannot be resolved.
        """
        resolved = shutil.which(self.args.c_compiler)
        require(resolved is not None, f"requested C compiler not found: {self.args.c_compiler}")
        # Preserve the invocation basename and symlinks: these can affect driver behavior.
        self.cc = os.path.abspath(resolved)
        self.report["compiler"]["resolved"] = self.cc
        home = self.root / "toolchain/compiler"
        for relative in ("shared", "stage1_l0/src", "stage1_l0/support"):
            shutil.copytree(L1_ROOT / "compiler" / relative, home / relative)
        build = self.root / "toolchain/build"
        for relative in ("interfaces", "include"):
            shutil.copytree(self.args.build_dir / relative, build / relative)
        self.native = self.root / "toolchain/l1c.native"
        shutil.copy2(self.args.build_dir / "bin/l1c-stage1.native", self.native)
        self.env.update(L1_HOME=str(home), L1_BUILD_DIR=str(build))
        self.header = build / "include/dea_rt.h"
        self.report["module_inventory"] = len(list((home / "shared/l1/stdlib").rglob("*.l1")))
        require(self.report["module_inventory"] > 0, "empty bundled module inventory")
        (self.root / "app.l1").write_text(
            'module app; import std.io; func main() { printl_s("preparation-probe-ok"); }\n', encoding="utf-8")

    def consume(self, stage: str, guarded: bool = False, cache: Path | None = None,
                cwd: Path | None = None, absolute_target: bool = False,
                explicit_sys_root: bool = False) -> dict:
        """Run one real consumer and capture its preparation measurements.

        Args:
            stage: Invocation label from STAGES.
            guarded: Disable automatic preparation when true.
            cache: Optional isolated cache root.
            cwd: Optional invocation directory.
            absolute_target: Pass absolute target and project-root paths.
            explicit_sys_root: Select the copied bundled source root explicitly.

        Returns:
            Recorded invocation evidence.
        """
        record = self.report["invocations"][stage] = {"stage": stage}
        selected_cache = cache or self.cache
        argv = [str(self.native), "--run", "--c-compiler", self.cc, "--stdlib-cache", str(selected_cache), "-vvv"]
        if absolute_target:
            argv.extend(["--project-root", str(self.root)])
        if explicit_sys_root:
            argv.extend(["--sys-root", str(self.root / "toolchain/compiler/shared/l1/stdlib")])
        if guarded:
            argv.append("--no-auto-prepare")
        target = str(self.root / "app.l1") if absolute_target else "app"
        result = self.run(stage, [*argv, target], record, cwd=cwd)
        record["output_ok"] = result.stdout == EXPECTED_OUTPUT
        record["output_empty"] = not result.stdout
        record["manifests"] = [str(path) for path in sorted(selected_cache.glob("v1/native/*/manifest.json"))]
        record.update(measurements(result.stderr))
        require(record["statistics"]["native_resolutions"] == 1, "expected one native resolution")
        return record

    def successful(self, record: dict, compiles: int, allow_source_analyses: bool = False) -> None:
        """Check successful output, validation economy and exact compiler attribution.

        Args:
            record: Invocation evidence.
            compiles: Expected managed module compilation count.
            allow_source_analyses: Whether an explicit provider may analyze std/sys sources.

        Raises:
            ProbeError: If any success or identity requirement fails.
        """
        require(record["exit_code"] == 0 and record["output_ok"] and not record["diagnostics"],
                "consumer failed or produced incorrect output; see invocation logs")
        require(record["stdlib_validations"] == (1 if compiles > 0 else 0)
                and (compiles > 0 or allow_source_analyses or record["managed_analyses"] == 0),
                "expected one bundled validation when preparing and none on warm reuse")
        require(record["statistics"]["module_compiles"] == compiles, "unexpected managed module compilation count")
        require(bool(re.fullmatch(r"[0-9a-f]{64}", record["native_key"])), "missing native key")
        toolchain = record["toolchain"]
        require(os.path.normcase(os.path.abspath(toolchain["invocation"])) == os.path.normcase(self.cc),
                "preparation selected a different compiler executable")
        self.report["compiler"]["preparation"] = toolchain
        require(toolchain["target"] in ("unobserved", self.report["compiler"]["target"]),
                "preparation target differs from the requested compiler target")

    def persistent(self, record: dict) -> None:
        """Check the selected persistent manifest and retain its identity.

        Args:
            record: Successful invocation evidence.

        Raises:
            ProbeError: If publication is missing or inconsistent.
        """
        entry = self.cache / "v1/native" / record["native_key"]
        require(Path(record["selected"]) == entry, "selected support is not the designated persistent entry")
        manifest = entry / "manifest.json"
        require(str(manifest) in record["manifests"], "missing persistent manifest")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        require(data["key"] == record["native_key"] and
                all(data["identity"]["toolchain"].get(key) == value for key, value in record["toolchain"].items()),
                "manifest identity differs from preparation")
        shutil.copyfile(manifest, self.args.output_dir / f"{record['stage']}.manifest.json")

    def rejected(self, record: dict) -> None:
        """Check guarded refusal rather than a crash or unrelated failure.

        Args:
            record: Guarded invocation evidence.

        Raises:
            ProbeError: If failure is not solely automatic-preparation refusal.
        """
        require(record["exit_code"] == 1 and len(record["diagnostics"]) == 1 and
                record["diagnostics"][0][0] == "L1C-2159", "guard failed outside the preparation refusal boundary")
        require(record["statistics"]["module_compiles"] == record["statistics"]["build_commands"] == 0 and
                record["stdlib_validations"] == 1 and record["managed_analyses"] == 0 and
                not record["selected"] and record["output_empty"], "guard unexpectedly prepared or consumed support")

    def observability_scenarios(self, baseline: dict) -> None:
        """Run opt-in pairs that expose validation and provider decisions.

        Args:
            baseline: Valid warm persistent invocation used for identity comparison.
        """
        scenarios = self.report["observability"]

        def selection_keys(record: dict) -> list[str]:
            return [item["selection_key"] for item in record["observations"]
                    if item["event"] == "observation-selection"]

        def pair(name: str, allow_source_analyses: bool = False, **kwargs: object) -> tuple[dict, dict]:
            scenario = scenarios[name]
            scenario.update(status="running", reason=None)
            first = self.consume(f"observe-{name}-1", guarded=True, **kwargs)
            second = self.consume(f"observe-{name}-2", guarded=True, **kwargs)
            for record in (first, second):
                self.successful(record, 0, allow_source_analyses=allow_source_analyses)
                require(record["statistics"]["build_commands"] == 0, "scenario unexpectedly built native support")
                if allow_source_analyses:
                    require(any(item.get("decision") == "suppressed" and item.get("reason") == "explicit-system-root"
                                for item in record["observations"]),
                            "explicit system root did not report managed-provider suppression")
                    require(any(item.get("module") == "std.io" and item.get("origin") == "source" and
                                not item.get("managed") for item in record["providers"]),
                            "explicit system root did not select the bundled source provider")
            require(first["native_key"] == second["native_key"], f"{name} pair changed native key")
            scenario.update({
                "status": "completed",
                "native_key_matches_baseline": first["native_key"] == baseline["native_key"],
                "selection_keys": [selection_keys(record) for record in (first, second)],
                "selection_key_matches_baseline": (selection_keys(first) == selection_keys(baseline)
                                                   if selection_keys(first) and selection_keys(baseline) else None),
                "stable_selection_key": (selection_keys(first) == selection_keys(second)
                                         if selection_keys(first) and selection_keys(second) else None),
                "providers": [record["providers"] for record in (first, second)],
                "providers_match_baseline": first["providers"] == baseline["providers"],
                "stable_providers": first["providers"] == second["providers"],
                "statistics": [record["statistics"] for record in (first, second)],
                "spans": [record["spans"] for record in (first, second)],
                "hashing": [record["hashing"] for record in (first, second)],
                "elapsed_ms": [first["elapsed_ms"], second["elapsed_ms"]],
            })
            return first, second

        pair("warm")
        other_cwd = self.root / "alternate-cwd"
        other_cwd.mkdir()
        pair("cwd", cwd=other_cwd, absolute_target=True)

        for name, remove_memos in (("copy", False), ("copy-no-memos", True)):
            copied = self.root / (name + "-cache")
            started = time.monotonic()
            try:
                shutil.copytree(self.cache, copied)
            finally:
                scenarios[name]["copy_elapsed_ms"] = (time.monotonic() - started) * 1000.0
                scenarios[name]["copied_cache_portability"] = "experimental-observation-only"
            if remove_memos:
                memo_root = copied / "v1/memo"
                if memo_root.exists():
                    shutil.rmtree(memo_root)
            pair(name, cache=copied, absolute_target=True)

        pair("explicit-sys-root", allow_source_analyses=True, absolute_target=True, explicit_sys_root=True)

    def execute(self) -> str:
        """Measure the complete available/private sequence or a confirmed resolution boundary.

        Returns:
            Observed capability category.

        Raises:
            ProbeError: If evidence is incomplete or unexpected.
        """
        self.fixture()
        for label, flag in (("version", "--version"), ("target", "-dumpmachine")):
            record = self.report["compiler"][label + "_probe"] = {}
            result = self.run("compiler-" + label, [self.cc, flag], record)
            require(result.returncode == 0 and bool(result.stdout.strip()), f"compiler {label} observation failed")
            self.report["compiler"][label] = result.stdout.strip()
        cold = self.consume("cold")
        if cold["exit_code"] != 0:
            # L1C-2154 alone also describes hard errors. Confirm the existing Clang
            # configuration boundary with a separate, retained diagnostic probe.
            if (cold["exit_code"] == 1 and len(cold["diagnostics"]) == 1 and
                    cold["diagnostics"][0][0] == "L1C-2154" and
                    cold["diagnostics"][0][1].startswith(ARCHIVER_BOUNDARY + ": ") and
                    "clang" in self.report["compiler"]["version"].lower() and
                    cold["stdlib_validations"] == 0 and not cold["manifests"] and
                    cold["statistics"]["module_compiles"] == cold["statistics"]["build_commands"] == 0):
                record = self.report["boundary_probe"] = {}
                result = self.run("runtime-archiver-boundary",
                                  [self.cc, "--no-default-config", "-print-prog-name=ar"], record)
                if (result.returncode == 1 and "unsupported option" in result.stderr and
                        "--no-default-config" in result.stderr):
                    self.report.update(reason=cold["diagnostics"][0][1], stage="cold")
                    return "unsupported"
            raise ProbeError("cold consumer failed; no confirmed unsupported preparation boundary")
        count = self.report["module_inventory"]
        self.successful(cold, count)
        require(cold["statistics"]["build_commands"] > 0, "cold preparation did no native build work")
        private = not cold["manifests"]
        if not private:
            self.persistent(cold)
            require(len(cold["manifests"]) == 1 and not cold["private_reasons"] and not cold["reuse"],
                    "unexpected cold publication or reuse")
        warm = self.consume("warm-auto")
        self.successful(warm, count if private else 0)
        require(warm["native_key"] == cold["native_key"], "ordinary warm invocation changed native key")
        if private:
            reasons = cold["private_reasons"]
            require(len(reasons) == 1 and reasons[0] in PRIVATE_REASONS and warm["private_reasons"] == reasons,
                    "private preparation lacks a repeatable supported ineligibility reason")
            require(not warm["manifests"] and not cold["reuse"] and not warm["reuse"] and
                    warm["statistics"]["build_commands"] > 0 and cold["selected"] and warm["selected"] and
                    cold["selected"] != warm["selected"], "private preparation evidence is inconsistent")
            guard = self.consume("warm-guard", guarded=True)
            self.rejected(guard)
            require(not guard["manifests"] and guard["native_key"] == cold["native_key"] and
                    reasons[0] in guard["diagnostics"][0][1], "guard did not confirm the private boundary")
            self.report["reason"] = reasons[0]
            return "private"
        for stage in ("warm-auto", "warm-guard"):
            record = warm if stage == "warm-auto" else self.consume(stage, guarded=True)
            self.successful(record, 0)
            self.persistent(record)
            require(record["native_key"] == cold["native_key"] and record["selected"] == cold["selected"] and
                    record["reuse"] == [cold["selected"]] and record["statistics"]["build_commands"] == 0 and
                    record["manifests"] == cold["manifests"] and not record["private_reasons"],
                    "warm consumption did not reuse the same persistent entry with zero preparation work")
        self.report["same_persistent_entry"] = True
        if getattr(self.args, "observability_scenarios", False):
            self.observability_scenarios(warm)
        with self.header.open("a", encoding="utf-8") as handle:
            handle.write("\n/* CI preparation invalidation probe. */\n")
        rejected = self.consume("invalidated-guard", guarded=True)
        self.rejected(rejected)
        require(rejected["native_key"] and rejected["native_key"] != cold["native_key"] and
                rejected["manifests"] == cold["manifests"], "header change did not reject the old profile")
        rebuilt = self.consume("invalidated-auto")
        self.successful(rebuilt, count)
        self.persistent(rebuilt)
        require(rebuilt["native_key"] == rejected["native_key"] and len(rebuilt["manifests"]) == 2 and
                rebuilt["statistics"]["build_commands"] > 0 and not rebuilt["reuse"] and not rebuilt["private_reasons"],
                "header change did not prepare a new persistent entry")
        self.report["invalidation"] = "rejected-old-profile-and-rebuilt"
        return "available"


def render_summary(report: dict) -> str:
    """Render a compact job summary without relying on test-runner stdout.

    Args:
        report: Complete or partial report.

    Returns:
        Markdown with compiler identity, capability and per-command counts.
    """
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", "<br>").replace("\r", "")

    compiler = report["compiler"]
    lines = ["## L1 native preparation", "",
             f"Result: **{report['result']}**; capability: **{report['capability']}**; expected: {report['expectation']}.",
             "", f"Platform: {cell(report['platform'])} / {cell(report['architecture'])}.", "",
             f"Compiler requested: {cell(compiler['requested'])}; resolved: {cell(compiler.get('resolved'))}.", "",
             f"Version: {cell(compiler.get('version'))}; target: {cell(compiler.get('target'))}.", "",
             f"Native preparation: {report['native_preparation']}; persistent reuse: {report['persistent_reuse']}.", "",
             f"Stage: {report['stage']}; reason: {cell(report['reason'])}.", "",
             f"Same persistent entry: {report['same_persistent_entry']}; invalidation: {report['invalidation']}.", "",
             "| Invocation | Exit | Elapsed ms | Validations | Probes | Input bytes | Artifact bytes | Module compiles |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for stage, record in report["invocations"].items():
        record = record or {}
        counts = record.get("statistics", {})
        hashing = record.get("hashing", {})
        input_bytes = (sum(hashing.get(name, {}).get("bytes", 0) for name in ("dea-input", "toolchain-input"))
                       if "hashing" in record else None)
        artifact_bytes = (sum(hashing.get(name, {}).get("bytes", 0)
                              for name in ("artifact-validation", "publication")) if "hashing" in record else None)
        elapsed = record.get("elapsed_ms")
        values = [stage, record.get("exit_code"), f"{elapsed:.3f}" if elapsed is not None else None,
                  record.get("stdlib_validations"), counts.get("probes"), input_bytes, artifact_bytes,
                  counts.get("module_compiles")]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    if report.get("observability"):
        lines.extend(["", "### Observability scenarios", "",
                      "| Scenario | Status | Native key matches baseline | Selection key matches baseline | Stable selection key | Providers match baseline | Stable providers | Copy ms |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- |"])
        for name, scenario in report["observability"].items():
            values = [name, scenario["status"], scenario.get("native_key_matches_baseline"),
                      scenario.get("selection_key_matches_baseline"), scenario.get("stable_selection_key"),
                      scenario.get("providers_match_baseline"), scenario.get("stable_providers"),
                      f"{scenario['copy_elapsed_ms']:.3f}" if "copy_elapsed_ms" in scenario else None]
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
            if scenario.get("reason"):
                lines.extend(["", f"{name}: {cell(scenario['reason'])}", ""])
    lines.extend(["", "Preparation spans are inclusive. Probe and hash time is nested within spans; "
                  "do not add them together. Command time includes work outside preparation."])
    for stage, record in report["invocations"].items():
        if not record or not record.get("observations"):
            continue
        lines.extend(["", f"### {stage} observations", "",
                      "| Event | Scope / purpose | Decision / reason | Detail |",
                      "| --- | --- | --- | --- |"])
        for item in record["observations"]:
            event = item["event"]
            if event == "hash":
                continue  # Per-file evidence remains in JSON and the raw log.
            detail = item.get("path", "")
            if event == "metadata-mismatch":
                detail = f"{detail}: {item.get('kind')} {item.get('field')} " + \
                         f"{item.get('previous')} -> {item.get('current')}"
            elif event == "observation-selection":
                detail = f"key={item.get('selection_key')}; cwd={item.get('cwd')}"
            elif event in ("span", "probe"):
                detail = f"{item['elapsed_us']} us; " + (f"status={item.get('status')}; timeout={item.get('timed_out')}"
                         if event == "probe" else f"inclusive; success={item.get('success')}")
            elif event == "provider":
                detail = f"{item.get('origin')}; managed={item.get('managed')}; {detail}"
            values = [event, item.get("scope", item.get("purpose", item.get("name", item.get("module", "")))),
                      "/".join(str(item[key]) for key in ("decision", "reason") if key in item), detail]
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
        lines.extend(["", "| Hash category | Attempts | Bytes read | Elapsed us |",
                      "| --- | --- | --- | --- |"])
        for category, totals in record.get("hashing", {}).items():
            lines.append("| " + " | ".join(cell(value) for value in
                         (category, totals["count"], totals["bytes"], totals["elapsed_us"])) + " |")
    lines.extend(["", "Full counters, identities, commands and raw logs are in the L1 preparation-reuse artifact.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run reporting and publish partial results even on unexpected failure.

    Args:
        argv: Optional CLI arguments for embedding or tests.

    Returns:
        Zero only for an observed expected capability; errors and not-run always fail.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c-compiler", required=True, help="Exact executable name or path; never substituted")
    parser.add_argument("--expect", choices=("available", "private", "unsupported", "observe"), default="available")
    parser.add_argument("--build-dir", type=Path, default=Path(os.environ.get("L1_BUILD_DIR", "build/dea")))
    parser.add_argument("--output-dir", type=Path, default=L1_ROOT / "build/ci/preparation-reuse")
    parser.add_argument("--timeout", type=int, default=600, help="Maximum seconds for each subprocess")
    parser.add_argument("--observability-scenarios", action="store_true",
                        help="Measure paired warm, cwd, copied-cache, memo-free and explicit-sys-root cases")
    args = parser.parse_args(argv)
    args.build_dir = (L1_ROOT / args.build_dir).resolve()
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Repeated local runs must not publish stale measurements from an earlier run.
    for label in (*STAGES, *OBSERVABILITY_STAGES, "compiler-version", "compiler-target", "runtime-archiver-boundary"):
        for suffix in ("command.json", "stdout.log", "stderr.log", "manifest.json"):
            (args.output_dir / f"{label}.{suffix}").unlink(missing_ok=True)
    for name in ("report.json", "summary.md"):
        (args.output_dir / name).unlink(missing_ok=True)
    report = {"schema": 1, "platform": os.environ.get("MSYSTEM") or platform.system(),
              "architecture": platform.machine(), "compiler": {"requested": args.c_compiler},
              "expectation": args.expect, "capability": "error", "result": "FAIL", "stage": "bootstrap",
              "reason": None, "native_preparation": "unknown", "persistent_reuse": "unknown",
              "same_persistent_entry": None, "invalidation": None,
              "observability": {name: {"status": "not-run", "reason": None} for name in
                                ("warm", "cwd", "copy", "copy-no-memos", "explicit-sys-root")}
                               if args.observability_scenarios else None,
              "invocations": dict.fromkeys((*STAGES, *(OBSERVABILITY_STAGES if args.observability_scenarios else ())))}
    try:
        require(args.timeout > 0, "timeout must be positive")
        inventory = list((L1_ROOT / "compiler/shared/l1/stdlib").rglob("*.l1"))
        required = [args.build_dir / "bin/l1c-stage1.native", args.build_dir / "include/dea_rt.h",
                    args.build_dir / "include/l1_real.h"]
        required.extend(args.build_dir / "interfaces" /
                        path.relative_to(L1_ROOT / "compiler/shared/l1/stdlib").with_suffix(".l1m") for path in inventory)
        missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
        if missing:
            report.update(capability="not-run", reason="incomplete bootstrap: " + ", ".join(missing))
        else:
            report["stage"] = "fixture"
            with tempfile.TemporaryDirectory(prefix="fixture-", dir=args.output_dir) as directory:
                report["capability"] = Probe(args, report, Path(directory).resolve()).execute()
            capability = report["capability"]
            report["native_preparation"] = "unsupported" if capability == "unsupported" else "supported"
            report["persistent_reuse"] = "available" if capability == "available" else "unavailable"
            if args.expect in ("observe", capability):
                report["result"] = "PASS"
            else:
                report["reason"] = f"expected {args.expect}, observed {capability}; {report['reason'] or ''}".rstrip("; ")
    except Exception as exc:
        report.update(capability="error", reason=f"{type(exc).__name__}: {exc}")
    finally:
        for scenario in (report.get("observability") or {}).values():
            if scenario["status"] != "completed":
                if scenario["status"] == "running":
                    scenario["status"] = "failed"
                elif report["capability"] in ("private", "unsupported"):
                    scenario["status"] = "unavailable"
                scenario["reason"] = (f"persistent reuse unavailable ({report['capability']})"
                                      if report["capability"] in ("private", "unsupported") else
                                      f"stopped at {report['stage']}: {report['reason']}")
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        summary = render_summary(report)
        (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
        print(summary)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
