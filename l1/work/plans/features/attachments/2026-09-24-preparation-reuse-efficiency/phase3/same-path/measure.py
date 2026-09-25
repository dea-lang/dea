#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Compare L1 image variants with one preparation and consumption cache path."""

import json
import pathlib
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tarfile
import time


def run(argv, *, timeout=900, log=None):
    """Run one command and return its elapsed milliseconds.

    Args:
        argv: Command and arguments.
        timeout: Maximum command duration in seconds.
        log: Optional file for captured output.

    Returns:
        Elapsed milliseconds.

    Raises:
        subprocess.CalledProcessError: If the command fails.
    """
    started = time.monotonic_ns()
    result = subprocess.run(argv, timeout=timeout, capture_output=True, text=True)
    elapsed = (time.monotonic_ns() - started) / 1_000_000
    if log:
        log.write_text(result.stdout + result.stderr)
    if result.returncode:
        print(result.stdout[-2000:], result.stderr[-4000:], file=sys.stderr)
        result.check_returncode()
    return elapsed


def archive_context(repo, output):
    """Build from tracked current source without copying local build artifacts.

    Args:
        repo: Repository root.
        output: Experiment output directory.

    Returns:
        Docker build context path.
    """
    archive = output / 'source.tar'
    context = output / 'context'
    if context.exists():
        shutil.rmtree(context)
    context.mkdir(exist_ok=True)
    with archive.open('wb') as stream:
        subprocess.run(['git', '-C', str(repo), 'archive', 'HEAD'], stdout=stream, check=True)
    with tarfile.open(archive) as stream:
        stream.extractall(context, filter='data')
    return context


def observations(path):
    """Read JSON observations from a captured compiler stderr file.

    Args:
        path: Captured stderr path.

    Returns:
        Observation dictionaries.
    """
    prefix = 'Preparation observation: '
    return [json.loads(line[len(prefix):]) for line in path.read_text().splitlines()
            if line.startswith(prefix)]


def compile_record(target, label, expected):
    """Verify one invocation and retain evidence needed for comparison.

    Args:
        target: Case directory.
        label: Invocation label.
        expected: Expected program output lines.

    Returns:
        Report record.

    Raises:
        AssertionError: If compilation or executable output is wrong.
    """
    timer = json.loads((target / f'{label}.json').read_text())
    assert timer['exit_code'] == 0 and not timer['timeout'], (target, label, timer)
    assert sorted((target / f'{label}.program').read_text().splitlines()) == expected
    stderr = (target / f'{label}.stderr').read_text()
    events = observations(target / f'{label}.stderr')
    counters = re.findall(r'^Preparation statistics: (.*)$', stderr, re.M)
    keys = re.findall(r'^Preparation native key: (.*)$', stderr, re.M)
    hashes = [event for event in events if event['event'] == 'hash']
    decisions = [event for event in events if event['event'] == 'decision']
    return {
        'label': label,
        'elapsed_ms': timer['elapsed_ms'],
        'cpu_user_ms': timer.get('user_ms'),
        'native_key': keys[-1] if keys else None,
        'counters': json.loads(counters[-1]) if counters else None,
        'providers': [event for event in events if event['event'] == 'provider'],
        'decisions': [event for event in decisions if event.get('scope') in (
            'native-profile', 'toolchain-observation-memo', 'toolchain-input-memo',
            'artifact-validation-memo', 'input-digest')],
        'metadata_differences': [event for event in events if event['event'] == 'metadata-mismatch'],
        'selection_keys': [event['selection_key'] for event in events
                           if event['event'] == 'observation-selection'],
        'probe_count': sum(event['event'] == 'probe' for event in events),
        'hash_bytes': {category: sum(event['bytes'] for event in hashes
                                     if event['category'] == category)
                       for category in ('dea-input', 'toolchain-input', 'artifact-validation')},
        'output_ok': True,
    }


def container_args(image, fixture, target=None):
    """Return identical isolation options for all image variants.

    Args:
        image: Image tag.
        fixture: Source fixture directory.
        target: Optional output directory.

    Returns:
        Docker run argument prefix.
    """
    argv = ['docker', 'run', '--rm', '--network', 'none', '--memory', '256m',
            '--memory-swap', '256m', '--pids-limit', '64', '--cpus', '1', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs',
            '/work:rw,size=64m,exec,mode=1777', '-e', 'TMPDIR=/work', '-e', 'HOME=/work',
            '-e', 'L1_STDLIB_CACHE=/opt/dea/l1/cache-template',
            '-w', '/work', '-v', f'{fixture}:/input:ro']
    if target:
        argv += ['-v', f'{target}:/results:rw']
    return [*argv, image]


def main():
    """Build the images and record independent fresh-container comparisons."""
    repo = pathlib.Path(sys.argv[1]).resolve()
    output = pathlib.Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture = repo / 'l1/examples/hello.l1'
    expected = sorted(re.findall(r'^    "(.*)"[,\n]', (fixture.parent / 'hello.l1').read_text(), re.M))
    assert len(expected) == 25
    dockerfile = pathlib.Path(__file__).with_name('Dockerfile')
    context = archive_context(repo, output)
    report = {'schema': 1, 'repetitions': 3, 'resources': {'cpus': 1, 'memory_mib': 256,
              'pids_limit': 64, 'work_tmpfs_mib': 64, 'read_only_root': False},
              'cache_root': '/opt/dea/l1/cache-template', 'images': {}, 'cases': [],
              'source': 'tracked HEAD at experiment start', 'fixture': 'l1/examples/hello.l1'}
    variants = ('prepared', 'inherited', 'copied')
    for variant in (*variants, 'stale-evidence'):
        image = f'dea-phase3-same-path-{variant}:local'
        argv = ['docker', 'build', '--progress=plain', '--target', variant, '-t', image,
                '-f', str(dockerfile), str(context)]
        duration = run(argv, timeout=1800, log=output / f'build-{variant}.log')
        details = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
        report['images'][variant] = {'tag': image, 'id': details['Id'], 'created': details['Created'],
                                     'size_bytes': details['Size'], 'build_ms': duration}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'Built {variant}: {duration / 1000:.2f}s', flush=True)

    for repeat in range(3):
        ordered = variants if repeat % 2 == 0 else tuple(reversed(variants))
        for variant in ordered:
            image = report['images'][variant]['tag']
            startup = run([*container_args(image, fixture.parent), 'true'], timeout=120)
            report['images'][variant].setdefault('startup_samples_ms', []).append(startup)
            for compiler in ('gcc', 'clang'):
                for debug in (True, False):
                    name = f'{variant}-{compiler}-{repeat + 1}-{"debug" if debug else "quiet"}'
                    target = output / name
                    target.mkdir(exist_ok=True)
                    target.chmod(0o777)
                    lines = ['set -eu', 'mkdir -p /work/capture']
                    for index in (1, 2):
                        label = f'build-{index}'
                        command = ['/opt/dea/bin/l1c-stage1', '--build', '--c-compiler', compiler,
                                   '--c-options=-O0', '--no-auto-prepare', '--project-root', '/input',
                                   '-o', '/work/hello.out', *(['-vvv'] if debug else []), '/input/hello.l1']
                        capture = f'/work/capture/{label}'
                        timed = ['/opt/dea/bin/investigation-timer', capture + '.json',
                                 capture + '.stdout', capture + '.stderr', '600', *command]
                        lines += [shlex.join(timed), f'/work/hello.out > {capture}.program']
                    lines += ['cp /work/capture/* /results/']
                    (target / 'case.sh').write_text('\n'.join(lines) + '\n')
                    total = run([*container_args(image, fixture.parent, target), 'sh', '/results/case.sh'],
                                timeout=900, log=target / 'container.log')
                    records = [compile_record(target, f'build-{index}', expected) for index in (1, 2)]
                    if debug:
                        assert all(record['native_key'] for record in records)
                        assert all(record['counters']['build_commands'] == 0 for record in records)
                        assert all(record['counters']['module_compiles'] == 0 for record in records)
                        assert all(len(record['providers']) == 11 for record in records)
                        assert all(provider['origin'] == 'interface' and provider['managed']
                                   for record in records for provider in record['providers'])
                        assert all(decision.get('path', '/opt/dea/l1/cache-template').startswith(
                            '/opt/dea/l1/cache-template') for record in records
                            for decision in record['decisions']
                            if decision.get('scope') in ('native-profile', 'artifact-validation-memo'))
                    report['cases'].append({'variant': variant, 'compiler': compiler,
                                            'repeat': repeat + 1, 'debug': debug,
                                            'container_total_ms': total, 'records': records})
                    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                    print(f'{name}: PASS', flush=True)

    # The stale image keeps profiles but replaces optional toolchain memo JSON.
    stale_target = output / 'stale-evidence'
    stale_target.mkdir(exist_ok=True)
    stale_target.chmod(0o777)
    stale_target.joinpath('case.sh').write_text('\n'.join([
        'set -eu', 'mkdir -p /work/capture',
        shlex.join(['/opt/dea/bin/investigation-timer', '/work/capture/build.json',
                    '/work/capture/build.stdout', '/work/capture/build.stderr', '600',
                    '/opt/dea/bin/l1c-stage1', '--build', '--c-compiler', 'clang', '--c-options=-O0',
                    '--no-auto-prepare', '--project-root', '/input', '-o', '/work/hello.out',
                    '-vvv', '/input/hello.l1']),
        '/work/hello.out > /work/capture/build.program', 'cp /work/capture/* /results/',
    ]) + '\n')
    run([*container_args(report['images']['stale-evidence']['tag'], fixture.parent, stale_target),
         'sh', '/results/case.sh'], timeout=900, log=stale_target / 'container.log')
    stale = compile_record(stale_target, 'build', expected)
    assert stale['counters']['build_commands'] == 0
    assert stale['hash_bytes']['toolchain-input'] > 0
    assert any(event.get('scope') == 'toolchain-observation-memo' and event['decision'] == 'miss'
               for event in stale['decisions'])
    assert any(event.get('scope') == 'native-profile' and event['decision'] == 'hit'
               for event in stale['decisions'])
    report['stale_evidence'] = stale
    for variant in variants:
        for compiler in ('gcc', 'clang'):
            for debug in (True, False):
                for index in (0, 1):
                    samples = [case['records'][index]['elapsed_ms'] for case in report['cases']
                               if (case['variant'], case['compiler'], case['debug']) ==
                               (variant, compiler, debug)]
                    report.setdefault('summary', []).append({'variant': variant, 'compiler': compiler,
                        'debug': debug, 'invocation': index + 1, 'samples_ms': samples,
                        'median_ms': statistics.median(samples), 'min_ms': min(samples),
                        'max_ms': max(samples)})
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Stale evidence: PASS', flush=True)


if __name__ == '__main__':
    main()
