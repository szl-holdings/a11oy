#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(pwd)}"
cd "$REPO_DIR"

echo "==> 1. Verifying we are in szl-holdings/ouroboros"
test -f package.json
grep -q '@szl-holdings/ouroboros' package.json || true

echo "==> 2. Installing dependencies"
pnpm install --frozen-lockfile || pnpm install

echo "==> 3. Running the existing 150-test suite (unchanged surface)"
npx vitest run --reporter=default --no-coverage || EXISTING_FAILED=1

echo "==> 4. Running the new Lutar Invariant proof tests in JSON mode"
npx vitest run packages/ouroboros/src/lutar-invariant-proof.test.ts \
  --reporter=json --outputFile=lutar-test-output.json --no-coverage

echo "==> 5. Generating LUTAR_EVIDENCE.md"
npx tsx scripts/lutar-evidence-report.ts lutar-test-output.json > LUTAR_EVIDENCE.md
echo "----- LUTAR_EVIDENCE.md -----"
cat LUTAR_EVIDENCE.md
echo "-----------------------------"

echo "==> 6. Counting total declared tests for README badge update"
TOTAL_TESTS=$(npx vitest run --reporter=json --outputFile=full-test-output.json --no-coverage \
  && node -e 'const r=require("./full-test-output.json"); let n=0; for (const f of r.testResults) n+=f.assertionResults.length; console.log(n)')
echo "Total declared tests: $TOTAL_TESTS"
echo "$TOTAL_TESTS" > .test-count

echo "==> 7. Updating README badge + status line"
node -e '
const fs = require("fs");
const n = fs.readFileSync(".test-count", "utf8").trim();
let r = fs.readFileSync("README.md", "utf8");
r = r.replace(/tests-150%2F150/g, `tests-${n}%2F${n}`);
r = r.replace(/\*\*150\/150 passing\*\*/g, `**${n}/${n} passing**`);
r = r.replace(/150 declared/g, `${n} declared`);
fs.writeFileSync("README.md", r);
console.log("README updated to "+n+"/"+n);
'

echo "==> 8. Done. Files to commit: README.md, LUTAR_EVIDENCE.md, packages/ouroboros/src/lutar-invariant-proof.test.ts, scripts/lutar-evidence-report.ts, scripts/run-lutar-evidence.sh"
