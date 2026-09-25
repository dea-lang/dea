#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Build isolated policies, gate a diagnostic pass, then measure paired repetitions."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import pathlib
import re
import shlex
import shutil
import statistics
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('same_path', HERE.parent / 'same-path/measure.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def run(argv, log, timeout=1800):
    """Run a command while streaming diagnostics to its retained log.

    Args:
        argv: Command argument list.
        log: Destination log path.
        timeout: Maximum seconds to run.

    Returns:
        Elapsed milliseconds.

    Raises:
        RuntimeError: If the command fails.
    """
    start = time.monotonic_ns()
    with log.open('w') as stream:
        result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{argv}: exit {result.returncode}; see {log}\n{log.read_text()[-6000:]}')
    return (time.monotonic_ns() - start) / 1_000_000


def save(output, report):
    """Save complete observations and a compact timing summary.

    Args:
        output: Output directory.
        report: Complete report object.
    """
    data = (json.dumps(report, indent=2) + '\n').encode()
    (output / 'report.json.gz').write_bytes(gzip.compress(data, mtime=0))
    rows = []
    groups = {}
    for case in report['cases']:
        for index, record in enumerate(case['records'], 1):
            key = (case['policy'], case['variant'], case['compiler'], index)
            groups.setdefault(key, []).append(record)
    for (policy, variant, compiler, invocation), records in groups.items():
        samples = [r['elapsed_ms'] for r in records]
        rows.append(dict(policy=policy, variant=variant, compiler=compiler, invocation=invocation,
                         samples_ms=samples, median_ms=statistics.median(samples),
                         min_ms=min(samples), max_ms=max(samples),
                         hash_bytes=[r['hash_bytes'] for r in records],
                         probe_counts=[r['probe_count'] for r in records]))
    (output / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')


def keys(stderr):
    """Read identity keys and selected profile from compiler diagnostics.

    Args:
        stderr: Compiler diagnostic text.

    Returns:
        Identity and selected-profile dictionary.
    """
    return {name: re.findall(pattern, stderr, re.M)[-1] for name, pattern in (
        ('D', r'^Preparation Dea key: (.*)$'),
        ('N', r'^Preparation native key: (.*)$'),
        ('profile', r'^Reuse prepared profile: (.*)$'))}


def accept(case, image):
    """Require mechanism boundaries before admitting measurements.

    Args:
        case: Two-request case.
        image: Image-time identities and evidence.

    Raises:
        AssertionError: If profile reuse or policy boundaries fail.
    """
    first, second = case['records']
    for record in (first, second):
        assert record['identity'] == image['prepared'][case['compiler']], (case, 'identity changed')
        assert record['counters']['build_commands'] == record['counters']['module_compiles'] == 0
        assert len(record['providers']) == 11
        assert all(p['managed'] and p['origin'] == 'interface' for p in record['providers'])
        assert any(d['scope'] == 'native-profile' and d['decision'] == 'hit' for d in record['decisions'])
        assert any(d['scope'] == 'artifact-validation-memo' and d['decision'] == 'hit'
                   for d in record['decisions'])
    events = first['events']
    rejection = next(i for i, e in enumerate(events) if e['event'] == 'decision' and
                     e.get('scope') == 'toolchain-observation-memo' and e['decision'] == 'miss')
    assert any(e['event'] == 'probe' for e in events[rejection + 1:])
    assert first['hash_bytes']['dea-input'] > 0 and first['hash_bytes']['artifact-validation'] > 0
    basis = [(i, e) for i, e in enumerate(events) if e['event'] == 'digest-reuse-basis']
    if case['policy'] == 'candidate':
        assert basis, 'candidate must demonstrate relaxed hits'
        assert all(e['scope'] == 'toolchain-input' and i > rejection for i, e in basis)
        last_probe = max(i for i, e in enumerate(events) if e['event'] == 'probe')
        assert all(i > last_probe for i, e in basis), 'reuse must follow discovery probes'
    else:
        assert not basis
    assert not second['metadata_differences']
    assert all(value == 0 for value in second['hash_bytes'].values())
    assert any(e.get('scope') == 'toolchain-observation-memo' and e.get('decision') == 'hit'
               for e in second['events'])


def build(repo, output, report):
    """Build both policies independently and validate candidate source.

    Args:
        repo: Original repository.
        output: Local experiment directory.
        report: Report object updated with image evidence.
    """
    provenance = {'source_revision': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
                  'patch_sha256': hashlib.sha256((HERE / 'candidate.patch').read_bytes()).hexdigest()}
    (output / 'local-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    report['patch_sha256'] = provenance['patch_sha256']
    for policy in ('baseline', 'candidate'):
        policy_dir = output / policy
        policy_dir.mkdir(exist_ok=True)
        context = base.archive_context(repo, policy_dir)
        if policy == 'candidate':
            run(['git', '-C', str(context), 'apply', str(HERE / 'candidate.patch')], policy_dir / 'patch.log')
            shutil.copyfile(HERE / 'candidate_test.c', context / 'l1/compiler/stage1_l0/tests/candidate_test.c')
        for variant in ('prepared', 'inherited', 'copied'):
            tag = f'dea-phase3-relaxed-{policy}-{variant}:local'
            duration = run(['docker', 'build', '--progress=plain', '--target', variant,
                            '-t', tag, '-f', str(HERE / 'Dockerfile'), str(context)],
                           policy_dir / f'build-{variant}.log')
            detail = json.loads(subprocess.check_output(['docker', 'image', 'inspect', tag]))[0]
            image = dict(tag=tag, id=detail['Id'], size_bytes=detail['Size'], build_ms=duration, prepared={})
            image['compiler_sha256'] = subprocess.check_output(
                ['docker', 'run', '--rm', '--network', 'none', tag, 'sha256sum',
                 '/opt/dea/bin/l1c-stage1.native'], text=True).split()[0]
            for compiler in ('gcc', 'clang'):
                evidence = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', tag,
                    'cat', f'/opt/dea/l1/cache-template/v1/experiment/{compiler}.stderr'], text=True)
                (policy_dir / f'{variant}-{compiler}-image.stderr').write_text(evidence)
                image['prepared'][compiler] = keys(evidence)
            report['images'][f'{policy}-{variant}'] = image
            save(output, report)
            print(f'Built {policy}/{variant}: {duration / 1000:.2f}s', flush=True)
        if policy == 'candidate':
            run(['docker', 'build', '--progress=plain', '--target', 'validation',
                 '-t', 'dea-phase3-relaxed-candidate-validation:local',
                 '-f', str(HERE / 'Dockerfile'), str(context)], policy_dir / 'validation.log', timeout=3600)
            run(['docker', 'run', '--rm', '--network', 'none', '-v', f'{HERE}:/experiment:ro',
                 'dea-phase3-relaxed-candidate-validation:local', 'python3',
                 '/experiment/artifact_boundary_test.py'], policy_dir / 'artifact-boundary.log')
            report['artifact_boundary_validation'] = 'passed'
            report['candidate_validation'] = 'passed'
            save(output, report)
            print('Candidate focused validation: PASS', flush=True)


def measure(repo, output, report, maximum):
    """Collect interleaved policy pairs and gate every case.

    Args:
        repo: Repository root containing the immutable request fixture.
        output: Experiment outputs.
        report: Accumulated report.
        maximum: Total repetitions per matrix cell.
    """
    fixture = repo / 'l1/examples/hello.l1'
    expected = sorted(re.findall(r'^    "(.*)"[,\n]', fixture.read_text(), re.M))
    assert len(expected) == 25
    for repeat in range(1, maximum + 1):
        policies = ('baseline', 'candidate') if repeat % 2 else ('candidate', 'baseline')
        for variant in ('prepared', 'inherited', 'copied'):
            for compiler in ('gcc', 'clang'):
                for policy in policies:
                    name = f'{repeat}-{policy}-{variant}-{compiler}'
                    if any(c['name'] == name for c in report['cases']):
                        continue
                    image = report['images'][f'{policy}-{variant}']
                    target = output / name
                    target.mkdir(exist_ok=True); target.chmod(0o777)
                    lines = ['set -eu', 'mkdir -p /work/capture']
                    for index in (1, 2):
                        capture = f'/work/capture/build-{index}'
                        command = ['/opt/dea/bin/l1c-stage1', '--build', '--c-compiler', compiler,
                                   '--c-options=-O0', '--no-auto-prepare', '--project-root', '/input',
                                   '-o', '/work/hello.out', '-vvv', '/input/hello.l1']
                        lines += [shlex.join(['/opt/dea/bin/investigation-timer', capture + '.json',
                            capture + '.stdout', capture + '.stderr', '600', *command]),
                            f'/work/hello.out > {capture}.program']
                    lines.append('cp /work/capture/* /results/')
                    (target / 'case.sh').write_text('\n'.join(lines) + '\n')
                    duration = run([*base.container_args(image['tag'], fixture.parent, target),
                                    'sh', '/results/case.sh'], target / 'container.log', timeout=900)
                    records = []
                    for index in (1, 2):
                        rec = base.compile_record(target, f'build-{index}', expected)
                        stderr = target / f'build-{index}.stderr'
                        rec['events'] = base.observations(stderr)
                        rec['identity'] = keys(stderr.read_text())
                        records.append(rec)
                    case = dict(name=name, repeat=repeat, policy=policy, variant=variant,
                                compiler=compiler, container_total_ms=duration, records=records)
                    report['cases'].append(case)
                    save(output, report)
                    accept(case, image)
                    print(f'{name}: PASS; first toolchain bytes={records[0]["hash_bytes"]["toolchain-input"]}', flush=True)
        report['accepted_repetitions'] = repeat
        save(output, report)
        print(f'Repetition {repeat}: all mechanism gates PASS', flush=True)


def main():
    """Dispatch independently reviewable build, diagnostic and timing stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    parser.add_argument('--phase', choices=('build', 'diagnostic', 'measure'), required=True)
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_file = output / 'report.json.gz'
    report = json.loads(gzip.decompress(report_file.read_bytes())) if report_file.exists() else {
        'schema': 1, 'cache_root': '/opt/dea/l1/cache-template', 'images': {}, 'cases': [],
        'resources': {'cpus': 1, 'memory_mib': 256, 'pids_limit': 64,
                      'work_tmpfs_mib': 64, 'read_only_root': False}}
    if args.phase == 'build':
        assert not report['cases'], 'do not rebuild images after measurement'
        report.pop('candidate_validation', None)
        report.pop('artifact_boundary_validation', None)
        report.pop('accepted_repetitions', None)
        build(repo, output, report)
    else:
        assert report.get('candidate_validation') == 'passed'
        assert report.get('artifact_boundary_validation') == 'passed'
        assert report['patch_sha256'] == hashlib.sha256((HERE / 'candidate.patch').read_bytes()).hexdigest()
        if args.phase == 'measure':
            assert report.get('accepted_repetitions', 0) >= 1, 'inspect diagnostic pass first'
        measure(repo, output, report, 1 if args.phase == 'diagnostic' else 5)


if __name__ == '__main__':
    main()
