// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 gwz

'use strict';

const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {test} = require('node:test');
const {VERSION, ARTIFACTS, selectArtifact, verifyArchive, extractArchive, install} = require('./setup.cjs');

function temporaryDirectory(t) {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'dea doxygen test-'));
    t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
    return directory;
}

test('the pinned release covers every native CI architecture', () => {
    assert.equal(VERSION, '1.18.0');
    for (const [runner, binary] of [
        ['Linux-X64', 'doxygen-1.18.0/bin/doxygen'],
        ['macOS-X64', 'doxygen-1.18.0/doxygen'],
        ['macOS-ARM64', 'doxygen-1.18.0/doxygen'],
        ['Windows-X64', 'doxygen.exe'],
    ]) {
        const [system, arch] = runner.split('-');
        const artifact = selectArtifact(system, arch);
        assert.equal(artifact.binary, binary);
        assert.match(artifact.sha256, /^[a-f0-9]{64}$/);
        assert.ok(artifact.file.includes(VERSION));
    }
    assert.equal(Object.keys(ARTIFACTS).length, 4);
});

for (const [system, arch] of [['Linux', 'ARM64'], ['Windows', 'ARM64'], ['macOS', 'X86'], ['Other', 'X64']]) {
    test(`unsupported runner ${system}/${arch} fails explicitly`, () => {
        assert.throws(() => selectArtifact(system, arch), /Unsupported Doxygen runner/);
    });
}

test('archive verification accepts exact bytes and rejects different bytes', async t => {
    const archive = path.join(temporaryDirectory(t), 'release.zip');
    const data = Buffer.from('verified release fixture');
    const expected = createHash('sha256').update(data).digest('hex');
    fs.writeFileSync(archive, data);
    await verifyArchive(archive, expected);
    fs.appendFileSync(archive, 'changed');
    await assert.rejects(verifyArchive(archive, expected), /SHA-256 mismatch/);
});

for (const system of ['Linux', 'macOS']) {
    test(`${system} extraction passes paths as individual arguments`, () => {
        const calls = [];
        const archive = "/runner temp/release's archive";
        const destination = '/runner temp/output';
        extractArchive(archive, destination, system, (...args) => calls.push(args));
        const [command, args] = calls[0];
        assert.equal(command, system === 'Linux' ? 'tar' : 'unzip');
        assert.deepEqual(args, system === 'Linux'
            ? ['-xzf', archive, '-C', destination] : ['-q', archive, '-d', destination]);
    });
}

for (const archive of ["C:\\runner temp\\release's.zip", 'C:/runner temp/mixed\\release.zip', '\\\\host\\share name\\release.zip']) {
    test(`Windows extraction preserves the native archive path: ${archive}`, () => {
        const destination = 'D:\\runner temp\\extracted';
        const calls = [];
        extractArchive(archive, destination, 'Windows', (...args) => calls.push(args));
        const [command, args, options] = calls[0];
        assert.equal(command, 'powershell.exe');
        assert.ok(args.includes('-NonInteractive'));
        assert.match(args.at(-1), /-LiteralPath \$env:DOXYGEN_ARCHIVE/);
        assert.equal(options.env.DOXYGEN_ARCHIVE, archive);
        assert.equal(options.env.DOXYGEN_DESTINATION, destination);
        assert.ok(!args.at(-1).includes(archive));
    });
}

for (const failure of [null, 'build metadata', 'checksum', 'version', 'development suffix', 'missing binary']) {
    test(`installation publishes PATH only after verification (${failure || 'success'})`, async t => {
        const directory = temporaryDirectory(t);
        const env = {
            RUNNER_OS: 'macOS', RUNNER_ARCH: 'X64', RUNNER_TEMP: directory,
            GITHUB_PATH: path.join(directory, 'path'), GITHUB_OUTPUT: path.join(directory, 'output'),
        };
        const calls = [];
        const dependencies = {
            download: async (url, archive) => {
                calls.push('download');
                assert.ok(url.endsWith('/Release_1_18_0/doxygen-1.18.0-mac-intel.zip'));
                fs.writeFileSync(archive, 'fixture');
            },
            verify: async (archive, hash) => {
                calls.push('verify');
                assert.equal(hash, ARTIFACTS['macOS-X64'].sha256);
                if (failure === 'checksum') throw new Error('SHA-256 mismatch');
            },
            extract: (archive, destination, system) => {
                calls.push('extract');
                assert.equal(system, 'macOS');
                assert.ok(fs.existsSync(archive));
                assert.ok(fs.existsSync(destination));
            },
            run: (binary, args) => {
                calls.push('version');
                assert.equal(path.basename(binary), 'doxygen');
                assert.deepEqual(args, ['--version']);
                if (failure === 'missing binary') throw new Error('ENOENT');
                if (failure === 'version') return '1.9.8\n';
                if (failure === 'development suffix') return '1.18.0-dev\n';
                return failure === 'build metadata' ? `1.18.0 (${'a'.repeat(40)})\n` : '1.18.0\n';
            },
        };
        if (failure && failure !== 'build metadata') {
            await assert.rejects(install(env, dependencies), failure === 'checksum'
                ? /SHA-256 mismatch/ : failure === 'missing binary' ? /ENOENT/ : /Expected Doxygen 1.18.0/);
            assert.ok(!fs.existsSync(env.GITHUB_PATH));
            assert.ok(!fs.existsSync(env.GITHUB_OUTPUT));
            if (failure === 'checksum') assert.deepEqual(calls, ['download', 'verify']);
        } else {
            const binary = await install(env, dependencies);
            assert.deepEqual(calls, ['download', 'verify', 'extract', 'version']);
            const bin = path.dirname(binary);
            assert.equal(fs.readFileSync(env.GITHUB_PATH, 'utf8'), `${bin}\n`);
            const version = failure === 'build metadata' ? `${VERSION} (${'a'.repeat(40)})` : VERSION;
            assert.equal(fs.readFileSync(env.GITHUB_OUTPUT, 'utf8'), `version=${version}\nbin=${bin}\n`);
            assert.ok(!fs.existsSync(path.join(path.dirname(path.dirname(bin)), ARTIFACTS['macOS-X64'].file)));
        }
    });
}
