#!/usr/bin/env node

import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = resolve(repoRoot, 'vendor', 'platform');
const expectedCommit = '6e0dc7b423fbcfb2c165348e60b41cd55a9b9ace';
const expectedUrl = 'https://github.com/szl-holdings/platform.git';

function fail(message) {
  console.error(`canonical web source verification failed: ${message}`);
  process.exit(1);
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function resolveGitDirectory() {
  const dotGit = resolve(sourcePath, '.git');
  if (!existsSync(dotGit)) {
    fail('vendor/platform is not initialized; run git submodule update --init --depth 1');
  }

  const marker = readFileSync(dotGit, 'utf8').trim();
  const prefix = 'gitdir: ';
  if (!marker.startsWith(prefix)) {
    fail('vendor/platform/.git is not a submodule gitdir marker');
  }
  return resolve(dirname(dotGit), marker.slice(prefix.length));
}

function readHead(gitDirectory) {
  const head = readFileSync(resolve(gitDirectory, 'HEAD'), 'utf8').trim();
  if (/^[0-9a-f]{40}$/.test(head)) return head;
  if (!head.startsWith('ref: ')) fail(`unrecognized submodule HEAD: ${head}`);

  const ref = head.slice('ref: '.length);
  const looseRef = resolve(gitDirectory, ref);
  if (existsSync(looseRef)) return readFileSync(looseRef, 'utf8').trim();

  const packedRefs = resolve(gitDirectory, 'packed-refs');
  if (!existsSync(packedRefs)) fail(`missing submodule ref ${ref}`);
  for (const line of readFileSync(packedRefs, 'utf8').split(/\r?\n/)) {
    if (!line || line.startsWith('#') || line.startsWith('^')) continue;
    const [commit, name] = line.split(' ');
    if (name === ref) return commit;
  }
  fail(`missing submodule ref ${ref}`);
}

const gitmodules = readFileSync(resolve(repoRoot, '.gitmodules'), 'utf8');
if (!gitmodules.includes(`url = ${expectedUrl}`)) {
  fail(`.gitmodules must bind vendor/platform to ${expectedUrl}`);
}

const observedCommit = readHead(resolveGitDirectory());
if (observedCommit !== expectedCommit) {
  fail(`expected ${expectedCommit}, observed ${observedCommit}`);
}

const platformPackage = readJson(resolve(sourcePath, 'package.json'));
if (platformPackage.packageManager !== 'pnpm@10.26.1') {
  fail(`unexpected platform package manager ${platformPackage.packageManager}`);
}

const artifactPackage = readJson(
  resolve(sourcePath, 'artifacts', 'a11oy', 'package.json'),
);
if (artifactPackage.name !== '@workspace/a11oy') {
  fail(`unexpected canonical artifact ${artifactPackage.name}`);
}

console.log(
  JSON.stringify(
    {
      schema: 'szl.canonical-web-source-verification/v1',
      source: expectedUrl,
      commit: observedCommit,
      artifact: 'vendor/platform/artifacts/a11oy',
      package: artifactPackage.name,
      package_manager: platformPackage.packageManager,
      ok: true,
    },
    null,
    2,
  ),
);
