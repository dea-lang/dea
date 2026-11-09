#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Core-only dependency adapter validation and real grouped Make behavior."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import p1689_make as adapter
from make_test_support import find_gnu_make


def make_include_path(value: str, separator: str = os.sep) -> str:
    """Escape an include filename without rule-only drive-colon quoting.

    Args:
        value: Native include path.
        separator: Native separator, supplied explicitly for portable probes.

    Returns:
        A Make include token preserving spaces, number signs, and drive colons.
    """
    return value.replace(separator, "/").replace(" ", "\\ ").replace("#", "\\#")


class AdapterFixture:
    """Create core reports for independent validation and real Make tests."""

    def setUp(self):
        """Create disjoint source, generated, and prebuilt roots."""
        self.temporary = tempfile.TemporaryDirectory(prefix="p1689 adapter ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build = self.root / "build"
        self.build.mkdir()
        self.fragment = self.root / "dependencies.mk"
        self.report_path = self.root / "dependencies.json"
        self.prebuilt = self.root / "prebuilt"
        self.prebuilt.mkdir()
        self.report = {"version": 1, "revision": 0, "rules": []}
        self.add_rule("helper")
        self.add_rule("app", ["helper"])

    def add_rule(self, name, requirements=()):
        """Append a minimal compiler-shaped rule backed by a real source."""
        source = self.root / (name.replace(".", "/") + ".l1")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("module " + name + ";\n", encoding="utf-8")
        stem = self.build / name.replace(".", "/")
        rule = {
            "work-directory": str(self.root),
            "primary-output": str(stem) + ".o",
            "outputs": [str(stem) + ".l1m"],
            "provides": [{"logical-name": name, "source-path": str(source),
                          "compiled-module-path": str(stem) + ".l1m"}],
            "requires": [{"logical-name": required,
                          "compiled-module-path": str(self.build / required.replace(".", "/")) + ".l1m"}
                         for required in requirements],
        }
        self.report["rules"].append(rule)
        return rule

    def add_prebuilt(self, name="std.io"):
        """Add a selected prebuilt requirement without inventing its object."""
        interface = self.prebuilt / (name.replace(".", "/") + ".l1m")
        interface.parent.mkdir(parents=True, exist_ok=True)
        interface.write_text("interface", encoding="utf-8")
        self.report["rules"][-1]["requires"].append(
            {"logical-name": name, "compiled-module-path": str(interface)}
        )
        return interface

    def render(self):
        """Render the current report without publishing it."""
        return adapter.render_fragment(self.report, self.build, self.fragment)

    def write(self):
        """Publish the current report through the public adapter API."""
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        return adapter.write_fragment(self.report_path, self.build, self.fragment)


class AdapterTests(AdapterFixture, unittest.TestCase):
    """Validate selected providers, publication, and the supported filename subset."""

    def test_core_report_and_annotations_are_independent(self):
        """Optional producer metadata changes no scheduling behavior."""
        expected = self.render()
        self.report["_dea_version"] = 1
        self.report["rules"][0]["_dea_origin"] = "source"
        self.report["rules"][0]["provides"][0]["_dea_note"] = ["ignored"]
        self.assertEqual(self.render(), expected)
        self.assertIn("DEA_OBJECTS :=", expected)
        self.assertIn("DEA_LINK_DEPS :=", expected)
        self.assertIn("&:", expected)
        self.assertIn("$(DEA_COMPILE_DEPS)", expected)
        self.assertIn("$(DEA_CONFIG_STAMP)", expected)

    def test_unchanged_fragment_keeps_timestamp(self):
        """A fresh unchanged scan does not invalidate all compilation actions."""
        self.assertTrue(self.write())
        previous = self.fragment.stat().st_mtime_ns
        self.assertFalse(self.write())
        self.assertEqual(self.fragment.stat().st_mtime_ns, previous)

    def test_relative_paths_use_each_rules_work_directory(self):
        """Relative report fields retain the producer's working context."""
        expected = self.render()
        for rule in self.report["rules"]:
            rule["primary-output"] = os.path.relpath(rule["primary-output"], self.root)
            rule["outputs"] = [os.path.relpath(path, self.root) for path in rule["outputs"]]
            for dependency in rule["provides"] + rule["requires"]:
                for field in ("source-path", "compiled-module-path"):
                    if field in dependency:
                        dependency[field] = os.path.relpath(dependency[field], self.root)
        self.assertEqual(self.render(), expected)

    def test_reject_versions_and_malformed_shapes(self):
        """Invalid or unsupported reports cannot produce accepted fragments."""
        baseline = copy.deepcopy(self.report)
        for field, value in (("version", 2), ("version", True), ("revision", 1),
                             ("revision", False), ("rules", {}), ("rules", [])):
            with self.subTest(field=field, value=value):
                self.report = copy.deepcopy(baseline)
                self.report[field] = value
                with self.assertRaises(adapter.AdapterError):
                    self.render()
        self.report = baseline
        self.report["rules"][0]["provides"] = []
        with self.assertRaises(adapter.AdapterError):
            self.render()

    def test_reject_duplicate_producers_and_output_collisions(self):
        """Two actions cannot own a logical provider or a native output."""
        self.report["rules"].append(copy.deepcopy(self.report["rules"][0]))
        with self.assertRaises(adapter.AdapterError):
            self.render()
        self.report["rules"].pop()
        self.report["rules"][1]["primary-output"] = self.report["rules"][0]["primary-output"]
        with self.assertRaises(adapter.AdapterError):
            self.render()

    def test_reject_output_mapping_and_required_mapping_conflicts(self):
        """Caller root and required provider identity must match core facts."""
        baseline = copy.deepcopy(self.report)
        self.report["rules"][0]["primary-output"] = str(self.root / "other.o")
        with self.assertRaises(adapter.AdapterError):
            self.render()
        self.report = baseline
        self.report["rules"][1]["requires"][0]["compiled-module-path"] = str(self.root / "other.l1m")
        with self.assertRaises(adapter.AdapterError):
            self.render()

    def test_missing_planned_outputs_are_valid_but_missing_prebuilt_is_not(self):
        """Clean source builds and unresolved interface requirements differ."""
        self.render()
        interface = self.add_prebuilt()
        result = self.render()
        self.assertNotIn(str(interface.with_suffix(".o")), result)
        interface.unlink()
        with self.assertRaisesRegex(adapter.AdapterError, "prebuilt"):
            self.render()

    def test_generated_prebuilt_candidates_are_rejected(self):
        """Any selected prebuilt's canonical generated candidate is a conflict."""
        interface = self.add_prebuilt()
        candidate = self.build / "std/io.l1m"
        candidate.parent.mkdir()
        for kind in ("file", "directory", "dangling", "alias"):
            with self.subTest(kind=kind):
                if kind == "file":
                    candidate.write_text("old", encoding="utf-8")
                elif kind == "directory":
                    candidate.mkdir()
                else:
                    try:
                        candidate.symlink_to(interface if kind == "alias" else self.root / "missing")
                    except OSError:
                        continue
                with self.assertRaisesRegex(adapter.AdapterError, "clean or fresh"):
                    self.render()
                if candidate.is_dir():
                    candidate.rmdir()
                else:
                    candidate.unlink()
        (self.build / "unreferenced.l1m").write_text("old", encoding="utf-8")
        self.render()

    def test_generated_root_alias_preserves_the_preflight(self):
        """Directory aliases cannot bypass selected-prebuilt collision checks."""
        self.add_prebuilt()
        alias = self.root / "alias"
        try:
            alias.symlink_to(self.build, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        self.assertEqual(adapter.render_fragment(self.report, alias, self.fragment), self.render())
        candidate = self.build / "std/io.l1m"
        candidate.parent.mkdir()
        candidate.touch()
        with self.assertRaises(adapter.AdapterError):
            adapter.render_fragment(self.report, alias, self.fragment)

    def test_conflicting_selected_prebuilt_paths_and_cycles_fail(self):
        """Global provider selections and source scheduling must be coherent."""
        interface = self.add_prebuilt("external")
        other = self.prebuilt / "other.l1m"
        other.touch()
        self.report["rules"][0]["requires"].append(
            {"logical-name": "external", "compiled-module-path": str(other)}
        )
        with self.assertRaises(adapter.AdapterError):
            self.render()
        self.report["rules"][0]["requires"][0]["compiled-module-path"] = str(interface)
        self.render()
        self.report["rules"][0]["requires"].append(
            {"logical-name": "app", "compiled-module-path": str(self.build / "app.l1m")}
        )
        with self.assertRaisesRegex(adapter.AdapterError, "cycle"):
            self.render()

    def test_prebuilt_artifact_cannot_claim_multiple_logical_names(self):
        """Distinct logical providers cannot alias one selected interface artifact."""
        interface = self.add_prebuilt("external")
        self.report["rules"][0]["requires"].append(
            {"logical-name": "different", "compiled-module-path": str(interface)}
        )
        with self.assertRaisesRegex(adapter.AdapterError, "ownership"):
            self.render()

    def test_protected_publication_and_failed_update_keep_old_fragment(self):
        """Invalid reports and input aliases never overwrite selected inputs."""
        self.write()
        before = self.fragment.read_bytes()
        self.report["version"] = 99
        with self.assertRaises(adapter.AdapterError):
            self.write()
        self.assertEqual(self.fragment.read_bytes(), before)
        self.report["version"] = 1
        source = Path(self.report["rules"][0]["provides"][0]["source-path"])
        with self.assertRaises(adapter.AdapterError):
            adapter.render_fragment(self.report, self.build, source)
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        with self.assertRaises(adapter.AdapterError):
            adapter.write_fragment(self.report_path, self.build, self.report_path)

    def test_fragment_cannot_alias_selected_inputs_or_generated_outputs(self):
        """Fragment destinations remain separate from every build data path."""
        prebuilt = self.add_prebuilt()
        for destination in (prebuilt, self.build / "helper.o", self.build / "app.l1m"):
            with self.subTest(destination=destination):
                with self.assertRaises(adapter.AdapterError):
                    adapter.render_fragment(self.report, self.build, destination)
        alias = self.root / "aliased-fragment.mk"
        try:
            os.link(prebuilt, alias)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(adapter.AdapterError):
            adapter.render_fragment(self.report, self.build, alias)

    def test_output_parent_alias_is_checked_by_physical_identity(self):
        """Equivalent directory spellings retain mapping and collision checks."""
        alias = self.root / "build alias"
        try:
            alias.symlink_to(self.build, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        rule = self.report["rules"][0]
        rule["primary-output"] = str(alias / "helper.o")
        rule["outputs"] = [str(alias / "helper.l1m")]
        rule["provides"][0]["compiled-module-path"] = str(alias / "helper.l1m")
        self.render()

    def test_lock_serializes_directory_aliases(self):
        """An outer build retains one shared lock through scan, preflight, and Make."""
        alias = self.root / "build alias"
        try:
            alias.symlink_to(self.build, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        entered = self.root / "entered"
        started = self.root / "started"
        script = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import p1689_make as adapter; "
            "Path(sys.argv[3]).touch()\n"
            "with adapter.artifact_lock(Path(sys.argv[2])):\n"
            "    Path(sys.argv[4]).touch()\n"
        )
        with adapter.artifact_lock(self.build):
            child = subprocess.Popen([sys.executable, "-c", script, str(Path(adapter.__file__).parent),
                                      str(alias), str(started), str(entered)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                while not started.exists() and time.monotonic() < deadline and child.poll() is None:
                    time.sleep(0.01)
                self.assertTrue(started.exists())
                self.assertFalse(entered.exists())
            except BaseException:
                child.kill()
                child.communicate()
                raise
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stdout + stderr)
        self.assertTrue(entered.exists())

    def test_lock_creates_a_new_root_and_rejects_a_dangling_root(self):
        """Lock creation never treats an unusable generated-root alias as a directory."""
        fresh = self.root / "fresh"
        with adapter.artifact_lock(fresh):
            self.assertTrue(fresh.is_dir())
        dangling = self.root / "dangling"
        try:
            dangling.symlink_to(self.root / "not-created", target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(OSError):
            with adapter.artifact_lock(dangling):
                self.fail("Dangling artifact root unexpectedly accepted")

    def test_hardlinked_output_cannot_overwrite_selected_source(self):
        """Physical input/output aliasing is checked beyond lexical equality."""
        source = Path(self.report["rules"][0]["provides"][0]["source-path"])
        output = Path(self.report["rules"][0]["primary-output"])
        try:
            os.link(source, output)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(adapter.AdapterError):
            self.render()

    def test_reject_unsupported_paths_without_splitting_them(self):
        """Lossy Make spellings get explicit diagnostics before publication."""
        for suffix in ("\nline", "\rline", "\tline", "$cash", "%pattern", "*glob", "?glob",
                       "[glob]", ",comma", "(paren)", "|pipe", ";semi", "\\literal"):
            with self.subTest(suffix=suffix):
                with self.assertRaises(adapter.AdapterError):
                    adapter.make_path("/tmp/name" + suffix, windows=False)

    def test_windows_spelling_normalization_is_explicit_and_host_independent(self):
        """Simulated Windows drive/UNC/mixed paths preserve distinct identities."""
        for value in (r"C:\build dir\app.o", "C:/build dir/app.o", r"C:\build dir/app.o"):
            self.assertEqual(adapter.make_path(value, windows=True), r"C\:/build\ dir/app.o")
        self.assertEqual(adapter.make_path(r"\\server\share\app.o", windows=True), "//server/share/app.o")
        self.assertNotEqual(adapter.make_path("C:/else/app.o", windows=True),
                            adapter.make_path("C:/build dir/app.o", windows=True))
        with self.assertRaises(adapter.AdapterError):
            adapter.make_path("C:/build/app.o", windows=False)

    def test_cli_rejects_duplicate_json_keys_and_leaves_prior_fragment(self):
        """Ambiguous JSON is not silently accepted by last-value wins decoding."""
        self.write()
        previous = self.fragment.read_bytes()
        self.report_path.write_text('{"version":1,"version":2,"rules":[]}', encoding="utf-8")
        result = subprocess.run([sys.executable, adapter.__file__, str(self.report_path),
                                 "--artifact-root", str(self.build), "-o", str(self.fragment)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)
        self.assertEqual(self.fragment.read_bytes(), previous)

    def test_cli_rejects_non_json_constants_even_in_annotations(self):
        """Ignored extension fields cannot smuggle malformed JSON into a report."""
        self.write()
        previous = self.fragment.read_bytes()
        timestamp = self.fragment.stat().st_mtime_ns
        for spelling in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(spelling=spelling):
                text = json.dumps(self.report)[:-1] + ', "_dea_ignored": ' + spelling + "}"
                self.report_path.write_text(text, encoding="utf-8")
                result = subprocess.run([sys.executable, adapter.__file__, str(self.report_path),
                                         "--artifact-root", str(self.build), "-o", str(self.fragment)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid JSON numeric constant", result.stderr)
                self.assertEqual(self.fragment.read_bytes(), previous)
                self.assertEqual(self.fragment.stat().st_mtime_ns, timestamp)

    def test_outer_fixture_normalizes_only_native_goal_separators(self):
        """Forward Windows drive/UNC goals and retain POSIX literal backslashes."""
        driver_path = Path(__file__).resolve().parents[1] / "compiler/tests/fixtures/dependency_discovery/build.py"
        spec = importlib.util.spec_from_file_location("dependency_build_fixture", driver_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        config_path = self.root / "project.json"
        report_path = self.build / "dependencies.json"
        report_path.write_text(json.dumps(self.report), encoding="utf-8")
        config = dict(adapter=adapter.__file__, compiler="fixture-compiler", make="fixture-make", entry="app",
                      artifact_root=str(self.build), executable=str(self.build / "program"),
                      action_log=str(self.root / "actions.jsonl"), inputs=[], link_inputs=[], native=[])
        cases = [
            ("\\", [r"C:\build dir\app.o", "C:/build dir/app.l1m", r"C:\build dir/mixed\helper.o",
                     r"\\server\share\build dir\app.o", r"D:\different\app.o"],
             ["C:/build dir/app.o", "C:/build dir/app.l1m", "C:/build dir/mixed/helper.o",
              "//server/share/build dir/app.o", "D:/different/app.o"]),
            ("/", [r"/tmp/build dir/literal\name.o", "/tmp/build dir/app.o"],
             [r"/tmp/build dir/literal\name.o", "/tmp/build dir/app.o"]),
        ]
        for separator, goals, expected in cases:
            with self.subTest(separator=separator):
                config["goals"] = goals
                config_path.write_text(json.dumps(config), encoding="utf-8")
                with patch.dict(sys.modules, {"p1689_make": adapter}), patch.object(driver.os, "sep", separator), patch.object(
                    driver.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
                ) as invocation:
                    self.assertEqual(driver.build(config_path), 0)
                self.assertEqual(invocation.call_count, 2)
                scan = invocation.call_args_list[0].args[0]
                self.assertEqual(scan[1:3], ["--scan-deps", "app"])
                inner = invocation.call_args_list[1].args[0]
                self.assertEqual(inner[inner.index("-j4") + 1:], expected)
                self.assertTrue((self.build / "dependencies.mk").is_file())


class MakeActionTests(AdapterFixture, unittest.TestCase):
    """Execute generated fragments with fake atomic compile recipes."""

    def setUp(self):
        """Prepare a caller-owned compile recipe and explicit final-link target."""
        super().setUp()
        self.make = find_gnu_make()
        if not self.make:
            self.skipTest("GNU Make 4.3 or newer is unavailable")
        self.compile_script = self.root / "compile.py"
        self.compile_script.write_text(
            "from pathlib import Path\nimport os, sys, time\n"
            "source, output = map(Path, sys.argv[1:])\n"
            "output.parent.mkdir(parents=True, exist_ok=True)\n"
            "with (output.parent / 'actions.log').open('a', encoding='utf-8') as log: log.write(source.stem + '\\n')\n"
            "time.sleep(0.05)\n"
            "for path in (output, output.with_suffix('.l1m')):\n"
            "    temporary = path.with_suffix(path.suffix + '.tmp')\n"
            "    temporary.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')\n"
            "    os.replace(temporary, path)\n",
            encoding="utf-8",
        )
        self.makefile = self.root / "Makefile"
        self.header = self.root / "runtime.h"
        self.header.touch()
        import shlex
        self.makefile.write_text(
            ".DEFAULT_GOAL := all\n"
            "DEA_COMPILE_DEPS := " + adapter.make_path(str(self.header)) + "\n"
            "define DEA_COMPILE\n"
            "@" + shlex.quote(sys.executable.replace(os.sep, "/")) + " "
            + shlex.quote(str(self.compile_script).replace(os.sep, "/")) + " $(1) $(2)\n"
            "endef\n"
            "include " + make_include_path(str(self.fragment)) + "\n"
            ".PHONY: all\nall: $(DEA_OBJECTS) $(DEA_INTERFACES)\n",
            encoding="utf-8",
        )

    def run_make(self, *targets):
        """Run the fixture under parallel Make and expose failures directly."""
        result = subprocess.run([self.make, "--no-print-directory", "-f", str(self.makefile), "-j4",
                                 *(target.replace(os.sep, "/") for target in targets)],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def actions(self):
        """Read completed compile invocations."""
        return (self.build / "actions.log").read_text(encoding="utf-8").splitlines()

    def test_include_paths_do_not_escape_drive_colons(self):
        """Exercise Make's include parser with spaces, number signs, and a drive."""
        if os.name == "nt":
            directory = self.root / "include space #"
            include_name = str(directory / "dependencies.mk")
        else:
            # A POSIX directory named C: exercises Make's drive-colon token
            # parsing without claiming native Windows filesystem coverage.
            directory = self.root / "C:" / "include space #"
            include_name = r"C:\include space #\dependencies.mk"
        directory.mkdir(parents=True)
        (directory / "dependencies.mk").write_text(
            ".PHONY: included\nincluded:\n\t@echo INCLUDED\n", encoding="utf-8"
        )
        encoded = make_include_path(include_name, "\\")
        self.assertNotIn("\\:", encoded)
        self.makefile.write_text("include " + encoded + "\n", encoding="utf-8")
        self.run_make("included")

    def test_clean_unchanged_and_each_missing_peer(self):
        """Either missing output repairs the whole pair even for survivor-only goals."""
        self.write()
        self.run_make()
        self.assertEqual(self.actions(), ["helper", "app"])
        self.assertFalse(self.write())
        self.run_make()
        self.assertEqual(self.actions(), ["helper", "app"])
        for name in ("app", "helper"):
            for missing_suffix, requested_suffix in ((".o", ".l1m"), (".l1m", ".o")):
                with self.subTest(name=name, suffix=missing_suffix):
                    (self.build / (name + missing_suffix)).unlink()
                    previous = len(self.actions())
                    self.assertFalse(self.write())
                    self.run_make(str(self.build / (name + requested_suffix)))
                    self.assertEqual(self.actions()[previous:], [name])
                    self.assertTrue((self.build / (name + missing_suffix)).is_file())

    def test_header_changes_recompile_pairs(self):
        """Caller native compile prerequisites do not degrade to link-only freshness."""
        self.write()
        self.run_make()
        base = int(time.time()) - 60
        for path in [self.header, self.fragment,
                     *(Path(rule["provides"][0]["source-path"]) for rule in self.report["rules"])]:
            os.utime(path, (base, base))
        paired_outputs = [self.build / (name + suffix) for name in ("helper", "app") for suffix in (".o", ".l1m")]
        for path in paired_outputs:
            os.utime(path, (base + 10, base + 10))
        self.run_make()
        self.assertEqual(self.actions(), ["helper", "app"])
        self.header.write_text("/* changed caller header */\n", encoding="utf-8")
        os.utime(self.header, (base + 20, base + 20))
        self.assertTrue(all(int(path.stat().st_mtime) < int(self.header.stat().st_mtime) for path in paired_outputs))
        self.run_make()
        self.assertEqual(self.actions(), ["helper", "app", "helper", "app"])
        self.run_make()
        self.assertEqual(self.actions(), ["helper", "app", "helper", "app"])

    def test_spaces_unicode_quotes_and_hash_are_lossless(self):
        """Make token escaping and recipe shell quoting are separate operations."""
        old = Path(self.report["rules"][0]["provides"][0]["source-path"])
        special = self.root / ("source space ü 'quote #.l1" if os.name == "nt" else "source space ü 'quote\" #.l1")
        old.rename(special)
        self.report["rules"][0]["provides"][0]["source-path"] = str(special)
        self.write()
        self.run_make()
        self.assertEqual(self.actions(), [special.stem, "app"])

    def test_shell_object_arguments_preserve_special_output_roots(self):
        """Final-link argv uses shell quoting independently of Make prerequisites."""
        old_build = self.build
        self.build = self.root / ("build ü 'quote #" if os.name == "nt" else "build ü 'quote\" #")
        self.build.mkdir()
        for rule in self.report["rules"]:
            rule["primary-output"] = rule["primary-output"].replace(str(old_build), str(self.build))
            rule["outputs"] = [path.replace(str(old_build), str(self.build)) for path in rule["outputs"]]
            for description in rule["provides"] + rule["requires"]:
                description["compiled-module-path"] = description["compiled-module-path"].replace(
                    str(old_build), str(self.build)
                )
        argv_script = self.root / "argv.py"
        argv_output = self.root / "argv.json"
        argv_script.write_text(
            "import json, sys; from pathlib import Path; "
            "Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]), encoding='utf-8')\n", encoding="utf-8"
        )
        import shlex
        with self.makefile.open("a", encoding="utf-8") as makefile:
            makefile.write(
                ".PHONY: link\nlink: $(DEA_LINK_DEPS)\n\t@"
                + shlex.quote(sys.executable.replace(os.sep, "/")) + " "
                + shlex.quote(str(argv_script).replace(os.sep, "/")) + " "
                + shlex.quote(str(argv_output).replace(os.sep, "/")) + " $(DEA_OBJECT_ARGS)\n"
            )
        self.write()
        self.run_make("link")
        self.assertEqual([path.replace(os.sep, "/") for path in json.loads(argv_output.read_text(encoding="utf-8"))],
                         [str(self.build / "helper.o").replace(os.sep, "/"),
                          str(self.build / "app.o").replace(os.sep, "/")])
        before = self.actions()
        self.run_make()
        self.assertEqual(self.actions(), before)


if __name__ == "__main__":
    unittest.main()
