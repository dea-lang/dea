#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Verify the complete matrix and summarize paired timings and per-file work."""

import collections
import gzip
import json
import pathlib
import statistics
import sys

from measure import accept


def main():
    """Check retained observations and write reproducible analysis JSON."""
    directory = pathlib.Path(sys.argv[1])
    report = json.loads(gzip.decompress((directory / 'report.json.gz').read_bytes()))
    assert len(report['cases']) == 60
    assert report['accepted_repetitions'] == 5
    cells = collections.defaultdict(list)
    for case in report['cases']:
        accept(case, report['images'][case['policy'] + '-' + case['variant']])
        cells[(case['policy'], case['variant'], case['compiler'])].append(case)
    assert len(cells) == 12 and all(len(cases) == 5 for cases in cells.values())
    summaries = []
    for variant in ('prepared', 'inherited', 'copied'):
        for compiler in ('gcc', 'clang'):
            for invocation in (0, 1):
                row = dict(variant=variant, compiler=compiler, invocation=invocation + 1)
                samples = {}
                for policy in ('baseline', 'candidate'):
                    cases = sorted(cells[policy, variant, compiler], key=lambda c: c['repeat'])
                    records = [c['records'][invocation] for c in cases]
                    samples[policy] = [r['elapsed_ms'] for r in records]
                    hash_files = collections.defaultdict(set)
                    spans = collections.defaultdict(list)
                    for record in records:
                        for event in record['events']:
                            if event['event'] == 'hash':
                                hash_files[event['category']].add((event['path'], event['bytes']))
                            if event['event'] == 'span':
                                spans[event['name']].append(event['elapsed_us'] / 1000)
                    row[policy] = dict(
                        samples_ms=samples[policy], median_ms=statistics.median(samples[policy]),
                        min_ms=min(samples[policy]), max_ms=max(samples[policy]),
                        hash_bytes={category: sorted({r['hash_bytes'][category] for r in records})
                                    for category in records[0]['hash_bytes']},
                        probe_counts=sorted({r['probe_count'] for r in records}),
                        hash_files={category: sorted(files) for category, files in hash_files.items()},
                        span_medians_ms={name: statistics.median(values) for name, values in spans.items()},
                        relaxed_hit_counts=[sum(e['event'] == 'digest-reuse-basis' for e in r['events'])
                                            for r in records])
                row['paired_reduction_percent'] = [100 * (b-c) / b for b, c in
                                                   zip(samples['baseline'], samples['candidate'])]
                row['median_paired_reduction_percent'] = statistics.median(row['paired_reduction_percent'])
                summaries.append(row)
    (directory / 'analysis.json').write_text(json.dumps(summaries, indent=2) + '\n')
    for row in summaries:
        print(row['variant'], row['compiler'], row['invocation'],
              'baseline/candidate median ms', round(row['baseline']['median_ms'], 2),
              round(row['candidate']['median_ms'], 2),
              'paired reduction %', round(row['median_paired_reduction_percent'], 1))
    print('All 60 cases, profile identities, discovery ordering, policy scopes, and second-request gates: PASS')


if __name__ == '__main__':
    main()
