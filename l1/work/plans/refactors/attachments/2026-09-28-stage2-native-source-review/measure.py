#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Measure the Phase 1 numeric refactor with preserved baseline inputs."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time


def main():
    """Build comparable harnesses and record alternating baseline/candidate runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--l1-root', required=True, type=Path)
    parser.add_argument('--baseline-sources', required=True, type=Path)
    parser.add_argument('--baseline-compiler', required=True, type=Path)
    parser.add_argument('--candidate-compiler', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--iterations', type=int, default=10000)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    l1 = args.l1_root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    harness = Path(__file__).with_name('numeric_benchmark.l1').resolve()
    env = dict(os.environ)
    env.update(L0_CC='/usr/bin/clang', L1_CC='/usr/bin/clang', L1_RUNTIME_CC='/usr/bin/clang',
               L1_HOME=str(l1/'compiler'), L1_BUILD_DIR=str(l1/'build/dea'),
               L1_STDLIB_CACHE=str(out/'stdlib-cache'))
    for name in ('L1_SYSTEM', 'L1_CFLAGS', 'L1_RUNTIME_INCLUDE', 'L1_RUNTIME_LIB', 'L1_TEST_COMPILER',
                 'DEA_RT_QUARANTINE_MAX_BYTES', 'DEA_RT_QUARANTINE_MAX_COUNT'):
        env.pop(name, None)
    sources = {'baseline': args.baseline_sources.resolve(), 'candidate': l1/'compiler/stage2_l1/src'}
    compilers = {'baseline': args.baseline_compiler.resolve(), 'candidate': args.candidate_compiler.resolve()}
    report = {'toolchain': subprocess.check_output(['/usr/bin/clang','--version'], text=True),
              'iterations': args.iterations, 'samples': 7, 'warmups': 1, 'commands': [], 'builds': {}, 'workloads': {}}

    def run(command, label):
        """Run one command, retaining output and enforcing success.

        Args:
            command: Argument vector to execute.
            label: Stable evidence filename stem.

        Returns:
            Pair of elapsed seconds and captured standard output.

        Raises:
            RuntimeError: The command exits unsuccessfully.
        """
        report['commands'].append([str(x) for x in command])
        start = time.perf_counter()
        result = subprocess.run(command, cwd=l1, env=env, capture_output=True)
        elapsed = time.perf_counter()-start
        (out/f'{label}.stdout').write_bytes(result.stdout)
        (out/f'{label}.stderr').write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{label}: {result.returncode}: {result.stderr.decode(errors="replace")[-3000:]}')
        return elapsed, result.stdout

    for kind, src in sources.items():
        for traced in (False, True):
            label = kind + ('-trace' if traced else '')
            command = [compilers['baseline'], '--build']
            if traced:
                command += ['--trace-arc', '--trace-memory']
            command += ['--project-root', src, '-o', out/label, harness]
            seconds, _ = run(command, f'build-{label}')
            report['builds'][label] = {'seconds': seconds, 'bytes': (out/label).stat().st_size}

    fixture = out/'phase1_measure.l1'
    declarations = '\n'.join(f'const value_{i}: ulong = 0xffffffffffffffff;' for i in range(100))
    fixture.write_text('module phase1_measure;\nexport *;\n'+declarations+'\n')
    workloads = {
        'numeric': {kind: [out/kind, str(args.iterations)] for kind in sources},
        'harness_build': {kind: [compilers['baseline'], '--build', '--project-root', src, '-o', out/kind, harness] for kind,src in sources.items()},
        'compiler_check': {kind: [compiler, '--check', '--project-root', sources['candidate'], 'l1c'] for kind,compiler in compilers.items()},
        'interface_emit': {kind: [compiler, '--emit-interface', fixture] for kind,compiler in compilers.items()},
    }
    for workload, commands in workloads.items():
        print(f'measuring {workload}', flush=True)
        values = {kind: [] for kind in sources}
        expected = None
        for index in range(8):
            order = ('baseline','candidate') if index % 2 == 0 else ('candidate','baseline')
            for kind in order:
                elapsed, stdout = run(commands[kind], f'{workload}-{index}-{kind}')
                if expected is None:
                    expected = stdout
                if stdout != expected:
                    raise AssertionError(f'{workload} output differs')
                if index:
                    values[kind].append(elapsed)
        stats = {kind: {'seconds': samples, 'median': statistics.median(samples), 'min': min(samples), 'max': max(samples)} for kind,samples in values.items()}
        stats['paired_change_percent'] = [100*(candidate/baseline-1)
                                            for baseline,candidate in zip(values['baseline'],values['candidate'])]
        stats['median_paired_change_percent'] = statistics.median(stats['paired_change_percent'])
        stats['median_change_percent'] = 100*(stats['candidate']['median']/stats['baseline']['median']-1)
        report['workloads'][workload] = stats

    report['trace_events'] = {}
    for kind in sources:
        run([out/f'{kind}-trace', '1'], f'trace-{kind}')
        run([sys.executable, l1/'compiler/stage2_l1/scripts/check_trace_log.py', out/f'trace-{kind}.stderr', '--triage'], f'trace-check-{kind}')
        counts = Counter()
        for line in (out/f'trace-{kind}.stderr').read_text().splitlines():
            # Retain the full trace as the primary evidence; summarize stable event labels.
            match = re.search(r'\bop=(\w+)', line)
            if match:
                counts[match.group(1)] += 1
        if not counts.get('alloc_string'):
            raise AssertionError('numeric trace did not contain string allocations')
        report['trace_events'][kind] = dict(counts)
    report['compiler_bytes'] = {kind: compiler.stat().st_size for kind,compiler in compilers.items()}
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({name: data['median_change_percent'] for name,data in report['workloads'].items()}), flush=True)


if __name__ == '__main__':
    main()
