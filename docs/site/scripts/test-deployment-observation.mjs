// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  ARTIFACT_ROOT_SCHEME,
  DONOR_CANONICAL_URL,
  NESTED_WORKFLOW,
  PRODUCT_ORIGIN,
  PROOF_REGISTRY,
  assessCheckedInWorkflow,
  buildObservation,
  foreignStorefrontText,
  inventoryArtifact,
  validateSourceContext,
  verifyObservation,
  writeObservation
} from './deployment-observation.mjs'

const revision = 'a'.repeat(40)
const context = Object.freeze({
  repository: 'szl-holdings/a11oy',
  revision,
  tree: 'c'.repeat(40),
  ref: 'refs/heads/main',
  ref_protected: 'true'
})
const workflow = Object.freeze({
  path: NESTED_WORKFLOW,
  text: [
    'name: deploy-docs-pages',
    'run: npm ci --no-audit --no-fund',
    'uses: actions/upload-pages-artifact@v5',
    'uses: actions/deploy-pages@v5'
  ].join('\n')
})

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'a11oy-docs-observation-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  mkdirSync(join(root, 'assets'))
  writeFileSync(join(root, 'index.html'), '<!doctype html><title>SZL</title>\n')
  writeFileSync(join(root, 'assets', 'app.123.js'), 'console.log("bound")\n')
  return root
}

test('binds artifact bytes without claiming publication or the donor URL', (t) => {
  const root = fixture(t)
  const observation = writeObservation(root, context, workflow)
  assert.equal(observation.contract, 'szl.a11oy.docs-site.checked-in-observation/v1')
  assert.equal(observation.source.revision, revision)
  assert.equal(observation.source.ref_protected, true)
  assert.equal(observation.publication.executed, false)
  assert.equal(observation.publication.provider, null)
  assert.equal(observation.publication.canonical_url, null)
  assert.equal(observation.publication.browser_gate_claimed, false)
  assert.equal(observation.checked_in_workflow.executed_by_github, false)
  assert.equal(observation.surfaces.product_origin, PRODUCT_ORIGIN)
  assert.equal(observation.surfaces.proof_registry, PROOF_REGISTRY)
  assert.notEqual(observation.publication.canonical_url, DONOR_CANONICAL_URL)
  assert.equal(observation.artifact.file_count, 2)
  assert.equal(observation.artifact.root_scheme, ARTIFACT_ROOT_SCHEME)
  assert.equal(verifyObservation(root, context, workflow).artifact.root_sha256, observation.artifact.root_sha256)
})

test('refuses to overwrite observation evidence', (t) => {
  const root = fixture(t)
  writeObservation(root, context, workflow)
  assert.throws(() => writeObservation(root, context, workflow), /refusing to overwrite observation evidence/)
})

test('fails when any inventoried byte changes after binding', (t) => {
  const root = fixture(t)
  writeObservation(root, context, workflow)
  writeFileSync(join(root, 'index.html'), '<!doctype html><title>TAMPERED</title>\n')
  assert.throws(() => verifyObservation(root, context, workflow), /does not match source or artifact bytes/)
})

test('fails when an unbound file appears after binding', (t) => {
  const root = fixture(t)
  writeObservation(root, context, workflow)
  writeFileSync(join(root, 'unexpected.txt'), 'not bound\n')
  assert.throws(() => verifyObservation(root, context, workflow), /does not match source or artifact bytes/)
})

test('fails closed on unprotected source, the wrong repository, and a non-hex revision', () => {
  assert.throws(() => validateSourceContext({ ...context, ref_protected: 'false' }), /not reported protected/)
  assert.throws(() => validateSourceContext({ ...context, repository: 'szl-holdings/docs-site' }), /repository is not canonical/)
  assert.throws(() => validateSourceContext({ ...context, revision: 'ABC' }), /exact lowercase Git SHA/)
})

test('refuses the foreign storefront and still names the proof registry', () => {
  assert.equal(foreignStorefrontText('https://a11oy.com/healthz'), true)
  assert.equal(foreignStorefrontText('https://www.a11oy.com/healthz'), true)
  assert.equal(foreignStorefrontText('https://a11oy.net/health.json'), false)
  assert.equal(foreignStorefrontText(PRODUCT_ORIGIN), false)
  assert.equal(foreignStorefrontText(DONOR_CANONICAL_URL), false)
  assert.throws(() => validateSourceContext({ ...context, repository: 'szl-holdings/a11oy.com' }), /foreign storefront/)
  assert.throws(() => assessCheckedInWorkflow(NESTED_WORKFLOW, `${workflow.text}\nhttps://a11oy.com/\n`), /foreign storefront/)
})

test('a root-shaped workflow path and a playwright marker do not become execution', (t) => {
  const assessed = assessCheckedInWorkflow('.github/workflows/deploy-pages.yml', workflow.text)
  assert.equal(assessed.root_workflow, true)
  assert.equal(assessed.executed_by_github, false)
  assert.equal(assessed.browser_gate_claimed, false)
  const root = fixture(t)
  assert.throws(() => buildObservation(root, context, { path: assessed.path, text: workflow.text }), /not the repository-root publisher/)
  assert.throws(
    () => buildObservation(root, context, { path: NESTED_WORKFLOW, text: `${workflow.text}\nnpx playwright test\n` }),
    /browser publication is not claimed/
  )
})

test('the checked-in nested deploy workflow is not a browser-gated publisher', (t) => {
  const workflowPath = fileURLToPath(new URL('../.github/workflows/deploy-pages.yml', import.meta.url))
  const text = readFileSync(workflowPath, 'utf8')
  const assessed = assessCheckedInWorkflow(NESTED_WORKFLOW, text)
  assert.equal(assessed.root_workflow, false)
  assert.equal(assessed.executed_by_github, false)
  assert.equal(assessed.browser_gate_claimed, false)
  assert.equal(assessed.playwright_marker, false)
  assert.equal(assessed.upload_pages_artifact_marker, true)
  const root = fixture(t)
  const observation = buildObservation(root, context, { path: NESTED_WORKFLOW, text })
  assert.equal(observation.publication.executed, false)
  assert.equal(observation.publication.canonical_url, null)
})

test('inventory ordering and root digest are deterministic', (t) => {
  const root = fixture(t)
  const first = inventoryArtifact(root)
  const second = inventoryArtifact(root)
  assert.deepEqual(first, second)
  assert.deepEqual(first.files.map((file) => file.path), [...first.files.map((file) => file.path)].sort())
  assert.equal(buildObservation(root, context, workflow).artifact.root_sha256, first.root_sha256)
})
