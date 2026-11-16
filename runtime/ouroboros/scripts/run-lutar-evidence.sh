#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd -- "${REPO_DIR:-$SCRIPT_DIR/..}" && pwd -P)"
WORKSPACE_DIR="$(cd -- "$REPO_DIR/../.." && pwd -P)"

echo "==> Verifying the a11oy workspace and Ouroboros source"
node - "$REPO_DIR" "$WORKSPACE_DIR" <<'NODE'
const fs = require('node:fs');
const path = require('node:path');
const [repo, workspace] = process.argv.slice(2);
const local = JSON.parse(fs.readFileSync(path.join(repo, 'package.json'), 'utf8'));
const root = JSON.parse(fs.readFileSync(path.join(workspace, 'package.json'), 'utf8'));
if (local.name !== '@szl-holdings/ouroboros'
    || root.repository?.url !== 'git+https://github.com/szl-holdings/a11oy.git'
    || path.resolve(repo) !== path.resolve(workspace, 'runtime', 'ouroboros')) {
  throw new Error('Expected the canonical a11oy/runtime/ouroboros source directory');
}
for (const file of ['pnpm-lock.yaml', 'pnpm-workspace.yaml']) {
  if (!fs.statSync(path.join(workspace, file)).isFile()) {
    throw new Error('Missing workspace dependency contract: ' + file);
  }
}
NODE

echo "==> Installing the frozen workspace toolchain"
pnpm --dir "$WORKSPACE_DIR" install --frozen-lockfile --ignore-scripts

STAGE_DIR="$(mktemp -d "$REPO_DIR/.lutar-evidence.XXXXXX")"
trap 'rm -rf -- "$STAGE_DIR"' EXIT

echo "==> Running the configured Ouroboros root suite once"
pnpm --dir "$WORKSPACE_DIR/packages/a11oy-knowledge" exec vitest run \
  --root "$REPO_DIR" --config "$REPO_DIR/vitest.config.ts" \
  --reporter=json --outputFile="$STAGE_DIR/full-test-output.json" --no-coverage

echo "==> Validating all assertions and preparing evidence"
pnpm --dir "$WORKSPACE_DIR" exec tsx "$SCRIPT_DIR/lutar-evidence-report.ts" \
  "$STAGE_DIR/full-test-output.json" "$REPO_DIR/README.md" "$STAGE_DIR"

# No published file is touched until the command and complete report validate.
mv -- "$STAGE_DIR/full-test-output.json" "$REPO_DIR/full-test-output.json"
mv -- "$STAGE_DIR/.test-count" "$REPO_DIR/.test-count"
mv -- "$STAGE_DIR/README.md" "$REPO_DIR/README.md"
mv -- "$STAGE_DIR/LUTAR_EVIDENCE.md" "$REPO_DIR/LUTAR_EVIDENCE.md"

echo "==> Published local test evidence: $REPO_DIR/LUTAR_EVIDENCE.md"
echo "    Exact input: $REPO_DIR/full-test-output.json"
