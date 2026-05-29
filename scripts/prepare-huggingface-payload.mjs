#!/usr/bin/env node
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { execFileSync } from 'node:child_process';

const repoRoot = process.cwd();
const outDir = path.join(repoRoot, 'dist', 'huggingface', 'a11oy');

async function copyText(source, target) {
  const body = await readFile(path.join(repoRoot, source), 'utf8');
  const absoluteTarget = path.join(outDir, target);
  await mkdir(path.dirname(absoluteTarget), { recursive: true });
  await writeFile(absoluteTarget, body);
}

function gitValue(args, fallback) {
  try {
    return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim();
  } catch {
    return fallback;
  }
}

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });

const files = [
  ['huggingface/README.md', 'README.md'],
  ['README.md', 'source/README.md'],
  ['ROADMAP.md', 'source/ROADMAP.md'],
  ['CHANGELOG.md', 'source/CHANGELOG.md'],
  ['docs/org-repo-map.md', 'source/docs/org-repo-map.md'],
  ['docs/regulatory_to_lambda.md', 'source/docs/regulatory_to_lambda.md'],
  ['deploy/MANIFEST.json', 'payloads/deploy/MANIFEST.json'],
  ['deploy/zarf.yaml', 'payloads/deploy/zarf.yaml'],
  ['deploy/attestations.jsonl', 'payloads/deploy/attestations.jsonl'],
  ['package.json', 'build/package.json'],
  ['pnpm-lock.yaml', 'build/pnpm-lock.yaml'],
  ['pnpm-workspace.yaml', 'build/pnpm-workspace.yaml'],
  ['tsconfig.base.json', 'build/tsconfig.base.json'],
];

for (const [source, target] of files) {
  await copyText(source, target);
}

const metadata = {
  name: 'a11oy',
  owner: 'szl-holdings',
  sourceRepository: 'https://github.com/szl-holdings/a11oy',
  sourceCommit: gitValue(['rev-parse', 'HEAD'], 'unknown'),
  sourceBranch: gitValue(['rev-parse', '--abbrev-ref', 'HEAD'], 'unknown'),
  doctrineCommands: [
    'pnpm test:doctrine',
    'pnpm typecheck:doctrine',
    'pnpm build:doctrine',
    'pnpm payload:verify',
  ],
  payloads: [
    {
      name: 'deploy',
      manifest: 'payloads/deploy/MANIFEST.json',
      zarf: 'payloads/deploy/zarf.yaml',
    },
  ],
};

await writeFile(path.join(outDir, 'a11oy-metadata.json'), `${JSON.stringify(metadata, null, 2)}\n`);

console.log(`Prepared Hugging Face payload at ${path.relative(repoRoot, outDir)}`);
