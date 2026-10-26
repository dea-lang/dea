// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 gwz

'use strict';

const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {Readable} = require('node:stream');
const {pipeline} = require('node:stream/promises');

const VERSION = '1.18.0';
const BASE_URL = `https://github.com/doxygen/doxygen/releases/download/Release_${VERSION.replaceAll('.', '_')}`;
// Upstream checksums: https://www.doxygen.nl/download.html
const ARTIFACTS = {
    'Linux-X64': {
        file: `doxygen-${VERSION}.linux.bin.tar.gz`,
        sha256: '14fa81bdc34171edb5f1f02b1d60e74802f0439b77fa44e592565d517d72df90',
        binary: `doxygen-${VERSION}/bin/doxygen`,
    },
    'macOS-X64': {
        file: `doxygen-${VERSION}-mac-intel.zip`,
        sha256: '8045d72f6f900fd430042339c1493d6eefcc85a7f990361fb57685682f16a2f9',
        binary: `doxygen-${VERSION}/doxygen`,
    },
    'macOS-ARM64': {
        file: `doxygen-${VERSION}-mac-arm.zip`,
        sha256: '31d1c74467a9f6f456b4e6a4eff0c03e93d1ffa92da5fdf2d53a2f14ebaabbd7',
        binary: `doxygen-${VERSION}/doxygen`,
    },
    'Windows-X64': {
        file: `doxygen-${VERSION}.windows.x64.bin.zip`,
        sha256: 'e84f54cfd49ef06b0b16536056dbec0c496323de28abcce53a4269463de35eaf',
        binary: 'doxygen.exe',
    },
};

function selectArtifact(os, arch) {
    const artifact = ARTIFACTS[`${os}-${arch}`];
    if (!artifact) throw new Error(`Unsupported Doxygen runner: ${os}/${arch}`);
    return artifact;
}

async function download(url, destination) {
    const response = await fetch(url, {signal: AbortSignal.timeout(120_000)});
    if (!response.ok) throw new Error(`Doxygen download failed: HTTP ${response.status}`);
    await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(destination));
}

async function verifyArchive(archive, expected) {
    const hash = createHash('sha256');
    for await (const chunk of fs.createReadStream(archive)) hash.update(chunk);
    if (hash.digest('hex') !== expected) throw new Error('Doxygen archive SHA-256 mismatch');
}

function extractArchive(archive, destination, os, run = execFileSync) {
    if (os === 'Windows') {
        run('powershell.exe', ['-NoLogo', '-NoProfile', '-NonInteractive', '-Command',
            'Expand-Archive -LiteralPath $env:DOXYGEN_ARCHIVE -DestinationPath $env:DOXYGEN_DESTINATION'], {
            env: {...process.env, DOXYGEN_ARCHIVE: archive, DOXYGEN_DESTINATION: destination},
            stdio: 'inherit',
        });
    } else if (os === 'Linux') {
        run('tar', ['-xzf', archive, '-C', destination], {stdio: 'inherit'});
    } else {
        run('unzip', ['-q', archive, '-d', destination], {stdio: 'inherit'});
    }
}

async function install(env = process.env, dependencies = {}) {
    const artifact = selectArtifact(env.RUNNER_OS, env.RUNNER_ARCH);
    for (const name of ['RUNNER_TEMP', 'GITHUB_PATH', 'GITHUB_OUTPUT']) {
        if (!env[name]) throw new Error(`Missing ${name}`);
    }
    const directory = fs.mkdtempSync(path.join(env.RUNNER_TEMP, 'dea-doxygen-'));
    const archive = path.join(directory, artifact.file);
    const destination = path.join(directory, 'extracted');
    fs.mkdirSync(destination);
    await (dependencies.download || download)(`${BASE_URL}/${artifact.file}`, archive);
    await (dependencies.verify || verifyArchive)(archive, artifact.sha256);
    (dependencies.extract || extractArchive)(archive, destination, env.RUNNER_OS);
    const binary = path.join(destination, artifact.binary);
    const version = (dependencies.run || execFileSync)(binary, ['--version'], {encoding: 'utf8'}).trim();
    const releasePattern = new RegExp(`^${VERSION.replaceAll('.', '\\.')}([ ]\\([a-f0-9]{40}\\))?$`);
    if (!releasePattern.test(version)) throw new Error(`Expected Doxygen ${VERSION}, got ${version}`);
    const bin = path.dirname(binary);
    // Native Windows paths are also inherited by MSYS2 jobs using path-type: inherit.
    fs.appendFileSync(env.GITHUB_PATH, `${bin}\n`);
    fs.appendFileSync(env.GITHUB_OUTPUT, `version=${version}\nbin=${bin}\n`);
    fs.rmSync(archive);
    console.log(`Doxygen ${version}: ${binary}`);
    return binary;
}

module.exports = {VERSION, BASE_URL, ARTIFACTS, selectArtifact, verifyArchive, extractArchive, install};

if (require.main === module) {
    install().catch(error => {
        console.error(error);
        process.exitCode = 1;
    });
}
