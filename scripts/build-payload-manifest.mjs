#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readdir, readFile, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

function usage() {
  console.error('Usage: node scripts/build-payload-manifest.mjs <payload-dir> --output <manifest> [--verify]');
  process.exit(2);
}

const args = process.argv.slice(2);
const payloadDir = args[0];
const outputIndex = args.indexOf('--output');
const verify = args.includes('--verify');

if (!payloadDir || outputIndex === -1 || !args[outputIndex + 1]) usage();

const root = path.resolve(payloadDir);
const outputPath = path.resolve(args[outputIndex + 1]);
const outputRel = path.relative(root, outputPath).split(path.sep).join('/');

async function collectFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolute = path.join(dir, entry.name);
    const rel = path.relative(root, absolute).split(path.sep).join('/');

    if (entry.isDirectory()) {
      files.push(...await collectFiles(absolute));
      continue;
    }

    if (!entry.isFile()) continue;
    if (rel === outputRel) continue;
    files.push({ absolute, rel });
  }

  return files;
}

async function sha256File(file) {
  const bytes = await readFile(file);
  return createHash('sha256').update(bytes).digest('hex');
}

const files = (await collectFiles(root)).sort((a, b) => a.rel.localeCompare(b.rel));
const manifestFiles = [];

for (const file of files) {
  const info = await stat(file.absolute);
  manifestFiles.push({
    path: file.rel,
    size: info.size,
    sha256: await sha256File(file.absolute),
  });
}

const aggregateInput = manifestFiles
  .map((file) => `${file.path}\0${file.size}\0${file.sha256}`)
  .join('\n');

const manifest = {
  manifestVersion: 1,
  payloadRoot: path.basename(root),
  fileCount: manifestFiles.length,
  aggregateSha256: createHash('sha256').update(aggregateInput).digest('hex'),
  files: manifestFiles,
};

const serialized = `${JSON.stringify(manifest, null, 2)}\n`;

if (verify) {
  const existing = await readFile(outputPath, 'utf8');
  if (existing !== serialized) {
    console.error(`Payload manifest is stale: ${path.relative(process.cwd(), outputPath)}`);
    console.error(`Run: node scripts/build-payload-manifest.mjs ${payloadDir} --output ${args[outputIndex + 1]}`);
    process.exit(1);
  }
  console.log(`Verified payload manifest: ${path.relative(process.cwd(), outputPath)}`);
} else {
  await writeFile(outputPath, serialized);
  console.log(`Wrote payload manifest: ${path.relative(process.cwd(), outputPath)}`);
}
