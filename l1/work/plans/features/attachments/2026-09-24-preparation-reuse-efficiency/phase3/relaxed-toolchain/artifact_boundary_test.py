#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Prove each experimentally ignored stamp remains strict for prepared artifacts."""

import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, '/project/l1/compiler/stage1_l0/tests')
from preparation_support_test import Service, build_library, populate, L1_ROOT
from compiler_filesystem_support_test import resolve_c_compiler
from l1c_stage1_compile_only_test import stage1_compiler


def main():
    """Alter one saved artifact stamp at a time and require one content read."""
    with tempfile.TemporaryDirectory(prefix='artifact-boundary-') as temporary:
        root = pathlib.Path(temporary)
        library = build_library(root)
        home = root / 'compiler'
        shutil.copytree(L1_ROOT / 'compiler/shared', home / 'shared')
        (home / 'stage1_l0/src').mkdir(parents=True)
        (home / 'stage1_l0/support').mkdir()
        (home / 'stage1_l0/src/implementation.l0').write_text('implementation fixture')
        shutil.copytree(stage1_compiler().parent.parent / 'interfaces', root / 'build/interfaces')
        shutil.copytree(stage1_compiler().parent.parent / 'include', root / 'build/include')
        executable = root / 'l1c'
        executable.write_text('compiler executable fixture')
        config = dict(home=str(home), self=str(executable), build_dir=str(root / 'build'),
                      cache=str(root / 'cache'), compiler=resolve_c_compiler(), options=['-std=c99'])
        with Service(library, config) as service:
            populate(service)
        for index in range(2):
            with Service(library, config) as service:
                service.require('resolve'); service.require('find')
                if index == 1:
                    assert service.stats()['artifact_content_reads'] == 0
        memo_path, = (root / 'cache/v1/memo/artifacts').glob('*.json')
        for field in ('device', 'inode', 'ctime', 'ctime_ns'):
            memo = json.loads(memo_path.read_text())
            relative = next(iter(memo['files']))
            original = memo['files'][relative]['metadata'][field]
            memo['files'][relative]['metadata'][field] += 1
            memo_path.write_text(json.dumps(memo))
            with Service(library, config) as service:
                service.require('resolve'); service.require('find')
                assert service.stats()['artifact_content_reads'] == 1, (field, service.stats())
            refreshed = json.loads(memo_path.read_text())
            assert refreshed['files'][relative]['metadata'][field] == original
            print(f'artifact {field}-only mismatch: one hash and full metadata refresh PASS')


if __name__ == '__main__':
    main()
