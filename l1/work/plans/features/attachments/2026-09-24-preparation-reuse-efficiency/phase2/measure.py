#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run isolated Phase 2 cwd pairs; use the retained image's monotonic timer."""
import json
import pathlib
import re
import shlex
import statistics
import subprocess
import sys

repo = pathlib.Path(sys.argv[1]).resolve()
output = pathlib.Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
fixture = repo / 'l1/examples/hello.l1'
expected = sorted(re.findall(r'^    "(.*)"[,\n]', fixture.read_text(), re.M))
assert len(expected) == 25
report = {'schema': 1, 'repetitions': 3, 'cases': [], 'images': {}, 'resources': {
    'cpus': 1, 'memory_bytes': 268435456, 'memory_swap_bytes': 268435456,
    'pids_limit': 64, 'work_tmpfs_bytes': 67108864},
    'timer': '/opt/dea/bin/investigation-timer', 'fixture': 'l1/examples/hello.l1'}
for variant in ('baseline', 'changed'):
    image = f'dea-phase2-{variant}:local'
    data = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    report['images'][variant] = {'tag': image, 'id': data['Id'], 'created': data['Created']}
for repeat in range(3):
    for cc in ('gcc', 'clang'):
        for debug in (True, False):
            for variant in (('baseline', 'changed') if repeat % 2 == 0 else ('changed', 'baseline')):
                name = f'{variant}-{cc}-{repeat + 1}-{ "debug" if debug else "quiet"}'
                target = output / name
                target.mkdir(exist_ok=True)
                target.chmod(0o777)
                commands = []
                lines = ['set -eu', 'mkdir -p /work/capture /work/other', "trap 'cp /work/capture/* /results/' EXIT", 'cat /sys/fs/cgroup/cpu.stat > /work/capture/cpu-before.txt']
                scenarios = [('warmup', []), ('warm', []), ('cwd', [])]
                for scenario, extra in scenarios:
                    for index in (1, 2):
                        label = f'{scenario}-{index}'
                        argv = ['/opt/dea/bin/l1c-stage1', '--build', '--c-compiler', cc, '--c-options=-O0',
                                '--no-auto-prepare', '--project-root', '/input', '-o', '/work/hello.out',
                                *(['-vvv'] if debug else []), *extra, '/input/hello.l1']
                        commands.append((label, scenario, argv))
                        capture = '/work/capture/' + label
                        timer = ['/opt/dea/bin/investigation-timer', capture + '.json', capture + '.stdout',
                                 capture + '.stderr', '600', *argv]
                        lines += ['cd ' + ('/work/other' if scenario == 'cwd' else '/work'), shlex.join(timer), f'/work/hello.out > {capture}.program']
                lines += ['find /work/dea-l1-cache/v1/memo -type f -printf \"%P %s\\n\" > /work/capture/storage.txt',
                          'cat /sys/fs/cgroup/cpu.stat > /work/capture/cpu-after.txt',
                          'cat /sys/fs/cgroup/memory.events > /work/capture/memory-events.txt',
                          'cp /work/capture/* /results/']
                (target / 'case.sh').write_text('\n'.join(lines) + '\n')
                argv = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--memory', '256m',
                        '--memory-swap', '256m', '--pids-limit', '64', '--cpus', '1', '--user', '65534:65534',
                        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs',
                        '/work:rw,size=64m,exec,mode=1777', '-e', 'TMPDIR=/work', '-e', 'HOME=/work', '-w', '/work',
                        '-v', f'{fixture.parent}:/input:ro', '-v', f'{target}:/results:rw',
                        f'dea-phase2-{variant}:local', 'sh', '/results/case.sh']
                launched = subprocess.run(argv, timeout=900, capture_output=True, text=True)
                if launched.returncode:
                    print(launched.stdout, launched.stderr, flush=True)
                    for failure_log in target.glob('*.stderr'):
                        print(failure_log.read_text(), flush=True)
                    launched.check_returncode()
                records = []
                for label, scenario, argv in commands:
                    timing = json.loads((target / (label + '.json')).read_text())
                    assert timing['exit_code'] == 0 and not timing['timeout'], (name, label, timing)
                    assert sorted((target / (label + '.program')).read_text().splitlines()) == expected, (name, label)
                    stderr = (target / (label + '.stderr')).read_text()
                    events = [json.loads(line.split(': ', 1)[1]) for line in stderr.splitlines()
                              if line.startswith('Preparation observation: ')]
                    providers = [e for e in events if e['event'] == 'provider']
                    analyses = re.findall(r"Starting analysis for entry module '((?:std|sys)\.[^']+)'", stderr)
                    keys = re.findall(r'^Preparation native key: (.*)$', stderr, re.M)
                    counts = re.findall(r'^Preparation statistics: (.*)$', stderr, re.M)
                    rec = {'label': label, 'scenario': scenario, 'argv': argv, 'timing': timing,
                           'cwd': '/work/other' if scenario == 'cwd' else '/work',
                           'output_ok': True, 'providers': providers, 'imported_source_analyses': analyses if debug else None,
                           'native_key': keys[-1] if keys else None, 'counters': json.loads(counts[-1]) if counts else None}
                    rec['hash_bytes'] = sum(e['bytes'] for e in events if e['event'] == 'hash' and e['category'] == 'toolchain-input') if debug else None
                    rec['probe_purposes'] = [e['purpose'] for e in events if e['event'] == 'probe'] if debug else None
                    rec['donor_reuses'] = sum(e.get('reason') == 'validated-donor-record' for e in events) if debug else None
                    rec['digest_seed_events'] = [e for e in events if e.get('scope', '').startswith('digest-seed-')] if debug else None
                    rec['selection_keys'] = [e['selection_key'] for e in events if e['event'] == 'observation-selection'] if debug else None
                    rec['file_evidence'] = [e for e in events if e['event'] == 'hash' or (e.get('scope') == 'input-digest' and e.get('reason') == 'validated-donor-record')] if debug and label == 'cwd-1' else None
                    if debug:
                        assert len(providers) == 11, (name, label, len(providers))
                        assert all(e['origin'] == 'interface' and bool(e['managed']) for e in providers)
                        assert not analyses
                        assert rec['counters']['module_compiles'] == rec['counters']['build_commands'] == 0
                        assert rec['native_key'], (name, label)
                    records.append(rec)
                if debug:
                    assert len({r['native_key'] for r in records}) == 1
                    assert records[2]['providers'] == records[4]['providers']
                    assert records[2]['selection_keys'] != records[4]['selection_keys']
                    assert records[4]['counters']['probes'] > records[3]['counters']['probes']
                    if variant == 'changed':
                        assert records[4]['hash_bytes'] == 0 and records[4]['donor_reuses'] > 0
                case = {'variant': variant, 'compiler': cc, 'repetition': repeat + 1, 'debug': debug,
                        'records': records, 'storage': (target / 'storage.txt').read_text(), 'cpu_before': (target / 'cpu-before.txt').read_text(),
                        'cpu_after': (target / 'cpu-after.txt').read_text(),
                        'memory_events': (target / 'memory-events.txt').read_text()}
                report['cases'].append(case)
                (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                print(name + ': PASS', flush=True)
summary = []
for variant in ('baseline', 'changed'):
    for cc in ('gcc', 'clang'):
        for debug in (True, False):
            for scenario in ('warm-1', 'warm-2', 'cwd-1', 'cwd-2'):
                values = [r['timing']['elapsed_ms'] for c in report['cases']
                          if (c['variant'], c['compiler'], c['debug']) == (variant, cc, debug)
                          for r in c['records'] if r['label'] == scenario]
                if values:
                    summary.append({'variant': variant, 'compiler': cc, 'debug': debug, 'scenario': scenario,
                                    'samples_ms': values, 'median_ms': statistics.median(values),
                                    'min_ms': min(values), 'max_ms': max(values)})
report['summary'] = summary
(output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
