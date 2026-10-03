#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Compare Phase 3 emitter and orchestration tranches using preserved sources and native compilers."""

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
    """Record seven alternating pairs after one warmup pair, with identical outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--l1-root', required=True, type=Path)
    parser.add_argument('--baseline-sources', required=True, type=Path)
    parser.add_argument('--candidate-sources', type=Path)
    parser.add_argument('--baseline-compiler', required=True, type=Path)
    parser.add_argument('--candidate-compiler', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--cc', required=True, type=Path)
    parser.add_argument('--harness', choices=('emitter', 'link'))
    parser.add_argument('--iterations', type=int, default=10000)
    parser.add_argument('--workloads', nargs='+', choices=('emitter', 'link', 'compiler_gen'))
    parser.add_argument('--reverse-pairs', action='store_true')
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error('--iterations must be positive')
    l1 = args.l1_root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cc = str(args.cc.resolve())
    env = dict(os.environ)
    env.update(L0_CC=cc, L1_CC=cc, L1_RUNTIME_CC=cc, L1_HOME=str(l1 / 'compiler'),
               L1_BUILD_DIR=str(l1 / 'build/dea'), L1_STDLIB_CACHE=str(out / 'stdlib-cache'))
    for name in ('L1_SYSTEM', 'L1_CFLAGS', 'L1_RUNTIME_INCLUDE', 'L1_RUNTIME_LIB', 'L1_TEST_COMPILER',
                 'DEA_RT_QUARANTINE_MAX_BYTES', 'DEA_RT_QUARANTINE_MAX_COUNT'):
        env.pop(name, None)
    sources = {'baseline': args.baseline_sources.resolve(), 'candidate': (args.candidate_sources or l1 / 'compiler/stage2_l1/src').resolve()}
    compilers = {'baseline': args.baseline_compiler.resolve(), 'candidate': args.candidate_compiler.resolve()}
    report = {'toolchain': subprocess.check_output([cc, '--version'], text=True), 'samples': 7,
              'warmups': 1, 'reverse_pairs': args.reverse_pairs, 'iterations': args.iterations, 'commands': [], 'builds': {}, 'workloads': {}}

    def run(command, label):
        """Run a measured command and preserve both output streams.

        Args:
            command: Command argument vector.
            label: Unique evidence filename stem.

        Returns:
            Elapsed seconds and standard output bytes.

        Raises:
            RuntimeError: The command fails.
        """
        command = [str(item) for item in command]
        report['commands'].append(command)
        started = time.perf_counter()
        result = subprocess.run(command, cwd=l1, env=env, capture_output=True)
        elapsed = time.perf_counter() - started
        (out / f'{label}.stdout').write_bytes(result.stdout)
        (out / f'{label}.stderr').write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{label}: {result.returncode}: {result.stderr.decode(errors="replace")[-3000:]}')
        return elapsed, result.stdout

    workloads = {}
    if args.harness:
        harness = Path(__file__).with_name(f'{args.harness}_benchmark.l1')
        # Reuse the production test runner's support-object contract.
        os.environ.update(env)
        sys.path.insert(0, str(l1 / 'compiler/stage2_l1/scripts'))
        from test_runner_common import stage2_test_support_args
        support = stage2_test_support_args(Path('link_driver_test.l1') if args.harness == 'link' else harness)
        for kind, source in sources.items():
            for traced in (False, True):
                label = kind + ('-trace' if traced else '')
                command = [compilers['baseline'], '--build', *support]
                if traced:
                    command += ['--trace-arc', '--trace-memory']
                command += ['--project-root', source, '-o', out / label, harness]
                seconds, _ = run(command, f'build-{label}')
                report['builds'][label] = {'seconds': seconds, 'bytes': (out / label).stat().st_size}
        workloads[args.harness] = {kind: [out / kind, str(args.iterations)] for kind in sources}

    workloads['compiler_gen'] = {
        kind: [compiler, '--gen', '--project-root', sources['candidate'], 'l1c']
        for kind, compiler in compilers.items()}
    if args.workloads:
        if set(args.workloads) - workloads.keys():
            parser.error('requested harness workload requires its matching --harness')
        workloads = {name: commands for name, commands in workloads.items() if name in args.workloads}
    for workload, commands in workloads.items():
        print(f'measuring {workload}', flush=True)
        values = {kind: [] for kind in sources}
        expected = None
        for index in range(8):
            order = ('baseline', 'candidate') if (index + args.reverse_pairs) % 2 == 0 else ('candidate', 'baseline')
            for kind in order:
                elapsed, stdout = run(commands[kind], f'{workload}-{index}-{kind}')
                if expected is None:
                    expected = stdout
                if stdout != expected:
                    raise AssertionError(f'{workload} output differs')
                if index:
                    values[kind].append(elapsed)
        stats = {kind: {'seconds': samples, 'median': statistics.median(samples), 'min': min(samples), 'max': max(samples)}
                 for kind, samples in values.items()}
        stats['paired_change_percent'] = [100 * (c / b - 1) for b, c in zip(values['baseline'], values['candidate'])]
        stats['median_paired_change_percent'] = statistics.median(stats['paired_change_percent'])
        stats['median_change_percent'] = 100 * (stats['candidate']['median'] / stats['baseline']['median'] - 1)
        report['workloads'][workload] = stats
    report['trace_events'] = {}
    if args.harness:
        expected_trace_stdout = None
        for kind in sources:
            _, stdout = run([out / f'{kind}-trace', '1'], f'trace-{kind}')
            if expected_trace_stdout is None:
                expected_trace_stdout = stdout
            elif stdout != expected_trace_stdout:
                raise AssertionError('traced harness output differs')
            run([sys.executable, l1 / 'compiler/stage2_l1/scripts/check_trace_log.py', out / f'trace-{kind}.stderr', '--triage'],
                f'trace-check-{kind}')
            counts = Counter(re.findall(r'\bop=(\w+)', (out / f'trace-{kind}.stderr').read_text()))
            report['trace_events'][kind] = dict(counts)
    report['compiler_bytes'] = {kind: compiler.stat().st_size for kind, compiler in compilers.items()}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({name: data['median_change_percent'] for name, data in report['workloads'].items()}), flush=True)


if __name__ == '__main__':
    main()
