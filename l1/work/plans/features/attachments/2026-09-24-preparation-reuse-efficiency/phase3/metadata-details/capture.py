#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Capture complete Phase 3 metadata differences across image boundaries."""

import importlib.util
import json
import pathlib
import re
import shlex
import subprocess
import sys


def load_same_path_driver(path):
    """Load the historical same-path driver without modifying it.

    Args:
        path: Path to the historical driver.

    Returns:
        Loaded module.
    """
    spec = importlib.util.spec_from_file_location('phase3_same_path', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save_report(path, report):
    """Persist results after each completed build or case.

    Args:
        path: Report path.
        report: Serializable results.
    """
    path.write_text(json.dumps(report, indent=2) + '\n')


def main():
    """Rebuild the three images and run six two-compilation containers."""
    repo = pathlib.Path(sys.argv[1]).resolve()
    output = pathlib.Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    same_path = pathlib.Path(__file__).resolve().parent.parent / 'same-path'
    base = load_same_path_driver(same_path / 'measure.py')
    fixture = repo / 'l1/examples/hello.l1'
    expected = sorted(re.findall(r'^    "(.*)"[,\n]', fixture.read_text(), re.M))
    assert len(expected) == 25
    context = base.archive_context(repo, output)
    report = {
        'schema': 1,
        'purpose': 'Complete metadata mismatch fields in a bounded fresh-container subset',
        'source': 'tracked HEAD at experiment start',
        'dockerfile': 'phase3/same-path/Dockerfile',
        'cache_root': '/opt/dea/l1/cache-template',
        'fixture': 'l1/examples/hello.l1',
        'resources': {'cpus': 1, 'memory_mib': 256, 'pids_limit': 64,
                      'work_tmpfs_mib': 64, 'read_only_root': False},
        'images': {},
        'cases': [],
    }
    report_path = output / 'report.json'
    variants = ('prepared', 'inherited', 'copied')
    for variant in variants:
        image = f'dea-phase3-metadata-{variant}:local'
        duration = base.run(
            ['docker', 'build', '--progress=plain', '--target', variant, '-t', image,
             '-f', str(same_path / 'Dockerfile'), str(context)],
            timeout=1800, log=output / f'build-{variant}.log')
        details = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
        report['images'][variant] = {'tag': image, 'id': details['Id'],
                                     'size_bytes': details['Size'], 'build_ms': duration}
        save_report(report_path, report)
        print(f'Built {variant}: {duration / 1000:.2f}s', flush=True)

    for variant in variants:
        image = report['images'][variant]['tag']
        for compiler in ('gcc', 'clang'):
            name = f'{variant}-{compiler}'
            target = output / name
            target.mkdir(exist_ok=True)
            target.chmod(0o777)
            lines = ['set -eu', 'mkdir -p /work/capture']
            for index in (1, 2):
                label = f'build-{index}'
                command = ['/opt/dea/bin/l1c-stage1', '--build', '--c-compiler', compiler,
                           '--c-options=-O0', '--no-auto-prepare', '--project-root', '/input',
                           '-o', '/work/hello.out', '-vvv', '/input/hello.l1']
                capture = f'/work/capture/{label}'
                timed = ['/opt/dea/bin/investigation-timer', capture + '.json',
                         capture + '.stdout', capture + '.stderr', '600', *command]
                lines.extend((shlex.join(timed), f'/work/hello.out > {capture}.program'))
            lines.append('cp /work/capture/* /results/')
            (target / 'case.sh').write_text('\n'.join(lines) + '\n')
            total = base.run([*base.container_args(image, fixture.parent, target),
                              'sh', '/results/case.sh'], timeout=900,
                             log=target / 'container.log')
            records = [base.compile_record(target, f'build-{index}', expected)
                       for index in (1, 2)]
            assert all(record['native_key'] for record in records)
            assert all(record['counters']['build_commands'] == 0 for record in records)
            assert all(record['counters']['module_compiles'] == 0 for record in records)
            assert all(len(record['providers']) == 11 for record in records)
            assert all(provider['origin'] == 'interface' and provider['managed']
                       for record in records for provider in record['providers'])
            report['cases'].append({'variant': variant, 'compiler': compiler,
                                    'container_total_ms': total, 'records': records})
            save_report(report_path, report)
            print(f'{name}: PASS', flush=True)

    for compiler in ('gcc', 'clang'):
        keys = {case['records'][0]['native_key'] for case in report['cases']
                if case['compiler'] == compiler}
        assert len(keys) == 1, (compiler, keys)
    assert len(report['cases']) == 6


if __name__ == '__main__':
    main()
