// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Adapted from public szl-holdings/docs-site scripts/deployment-manifest.mjs
// at 83664f8b8924b36d3179bd94d133ca0815aaee91 (Apache-2.0).
// The donor binds a root Pages workflow for szl-holdings/docs-site.
// This package records a checked-in nested workflow and does not claim that
// GitHub Actions executed it or that a browser suite gated publication.

import { createHash } from 'node:crypto'
import {
  existsSync,
  lstatSync,
  readFileSync,
  readdirSync,
  writeFileSync
} from 'node:fs'
import { relative, resolve, sep } from 'node:path'

export const CONTRACT = 'szl.a11oy.docs-site.checked-in-observation/v1'
export const EXPECTED_REPOSITORY = 'szl-holdings/a11oy'
export const EXPECTED_REF = 'refs/heads/main'
export const NESTED_WORKFLOW = 'docs/site/.github/workflows/deploy-pages.yml'
export const PRODUCT_ORIGIN = 'https://a-11-oy.com'
export const PROOF_REGISTRY = 'https://a11oy.net'
export const DONOR_CANONICAL_URL = 'https://holdings.a-11-oy.com/docs-site/'
export const ARTIFACT_ROOT_SCHEME = 'sha256-path-nul-bytes-nul-sha256-lf-v1'
export const MANIFEST_NAME = 'checked-in-observation.json'

const SHA256 = /^[0-9a-f]{64}$/
const GIT_SHA = /^[0-9a-f]{40}$/

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function assertExactKeys(value, keys, label) {
  assert(value && typeof value === 'object' && !Array.isArray(value), `${label} must be an object`)
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  assert(JSON.stringify(actual) === JSON.stringify(expected), `${label} field set mismatch`)
}

export function foreignStorefrontText(value) {
  return typeof value === 'string'
    && /(?:^|[^A-Za-z0-9-])(?:[A-Za-z0-9-]+\.)*a11oy\.com(?![A-Za-z0-9-])/i.test(value)
}

function refuseForeignStorefront(value, label) {
  if (foreignStorefrontText(value)) throw new Error(`${label} names the foreign storefront`)
}

function normalizedRelative(root, path) {
  const value = relative(root, path).split(sep).join('/')
  assert(value && !value.startsWith('../') && !value.includes('/../'), `unsafe artifact path: ${value}`)
  assert(
    !value.startsWith('/') &&
    !/[\\%:?#\u0000-\u001f\u007f]/.test(value) &&
    !value.split('/').some((segment) => segment === '.' || segment === '..' || segment === ''),
    `unsafe artifact path: ${value}`
  )
  return value
}

function validateArtifactPath(value) {
  assert(typeof value === 'string' && value.length > 0, 'deployment artifact path is invalid')
  assert(
    !value.startsWith('/') &&
    !/[\\%:?#\u0000-\u001f\u007f]/.test(value) &&
    !value.split('/').some((segment) => segment === '.' || segment === '..' || segment === ''),
    `deployment artifact path is unsafe: ${value}`
  )
}

function artifactRoot(files) {
  const rootHash = createHash('sha256')
  for (const file of files) {
    rootHash.update(file.path, 'utf8')
    rootHash.update('\0')
    rootHash.update(String(file.bytes), 'utf8')
    rootHash.update('\0')
    rootHash.update(file.sha256, 'ascii')
    rootHash.update('\n')
  }
  return rootHash.digest('hex')
}

function walkFiles(root, directory = root, files = []) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name)
    const stat = lstatSync(path)
    assert(!stat.isSymbolicLink(), `artifact symlink is forbidden: ${normalizedRelative(root, path)}`)
    if (stat.isDirectory()) {
      walkFiles(root, path, files)
    } else {
      assert(stat.isFile(), `unsupported artifact entry: ${normalizedRelative(root, path)}`)
      files.push(path)
    }
  }
  return files
}

export function inventoryArtifact(distPath) {
  const root = resolve(distPath)
  assert(existsSync(root) && lstatSync(root).isDirectory(), 'built artifact directory is missing')

  const files = walkFiles(root)
    .map((path) => ({ path, relative: normalizedRelative(root, path) }))
    .filter(({ relative: artifactPath }) => artifactPath !== MANIFEST_NAME)
    .sort((a, b) => (a.relative < b.relative ? -1 : a.relative > b.relative ? 1 : 0))
    .map(({ path, relative: artifactPath }) => {
      const bytes = readFileSync(path)
      return {
        path: artifactPath,
        bytes: bytes.length,
        sha256: createHash('sha256').update(bytes).digest('hex')
      }
    })

  assert(files.length > 0, 'built artifact inventory is empty')
  const seen = new Set()
  for (const file of files) {
    assert(!seen.has(file.path), `duplicate artifact path: ${file.path}`)
    seen.add(file.path)
  }

  return {
    algorithm: 'sha256',
    root_scheme: ARTIFACT_ROOT_SCHEME,
    file_count: files.length,
    total_bytes: files.reduce((total, file) => total + file.bytes, 0),
    root_sha256: artifactRoot(files),
    files
  }
}

export function validateSourceContext(context) {
  assertExactKeys(context, ['repository', 'revision', 'tree', 'ref', 'ref_protected'], 'observation context')
  refuseForeignStorefront(context.repository, 'observation repository')
  assert(context.repository === EXPECTED_REPOSITORY, 'observation repository is not canonical')
  assert(GIT_SHA.test(context.revision ?? ''), 'observation revision must be an exact lowercase Git SHA')
  assert(GIT_SHA.test(context.tree ?? ''), 'observation tree must be an exact lowercase Git SHA')
  assert(context.ref === EXPECTED_REF, 'observation ref must be protected main')
  assert(context.ref_protected === 'true', 'observation ref is not reported protected')
  return context
}

export function assessCheckedInWorkflow(repoRelativePath, text) {
  assert(typeof repoRelativePath === 'string' && typeof text === 'string', 'checked-in workflow identity is invalid')
  assert(
    !repoRelativePath.startsWith('/') &&
    !repoRelativePath.includes('\\') &&
    !repoRelativePath.split('/').some((segment) => segment === '.' || segment === '..' || segment === ''),
    'checked-in workflow path is unsafe'
  )
  refuseForeignStorefront(repoRelativePath, 'workflow path')
  refuseForeignStorefront(text, 'workflow text')
  return {
    path: repoRelativePath,
    root_workflow: /^\.github\/workflows\/[^/]+\.ya?ml$/.test(repoRelativePath),
    executed_by_github: false,
    execution_reason: 'file text is not a GitHub Actions run',
    browser_gate_claimed: false,
    playwright_marker: /playwright|test:browser:built/.test(text),
    upload_pages_artifact_marker: text.includes('actions/upload-pages-artifact@'),
    sha256: createHash('sha256').update(text, 'utf8').digest('hex')
  }
}

function publicationRecord() {
  return {
    executed: false,
    provider: null,
    canonical_url: null,
    browser_gate_claimed: false
  }
}

export function buildObservation(distPath, context, workflow) {
  validateSourceContext(context)
  assert(workflow && typeof workflow === 'object', 'checked-in workflow is required')
  const assessed = assessCheckedInWorkflow(workflow.path, workflow.text)
  assert(assessed.path === NESTED_WORKFLOW, 'nested workflow is not the repository-root publisher')
  assert(assessed.root_workflow === false, 'nested workflow is not the repository-root publisher')
  assert(assessed.executed_by_github === false, 'checked-in workflow text is not execution')
  assert(assessed.playwright_marker === false, 'browser publication is not claimed from workflow text')
  assert(assessed.upload_pages_artifact_marker === true, 'checked-in nested workflow no longer has the upload marker this observation records')
  assert(assessed.browser_gate_claimed === false, 'browser publication is not claimed from workflow text')
  const artifact = inventoryArtifact(distPath)
  return {
    contract: CONTRACT,
    source: {
      repository: context.repository,
      revision: context.revision,
      tree: context.tree,
      ref: context.ref,
      ref_protected: true
    },
    checked_in_workflow: assessed,
    surfaces: {
      product_origin: PRODUCT_ORIGIN,
      proof_registry: PROOF_REGISTRY
    },
    publication: publicationRecord(),
    artifact
  }
}

function assertObservationShape(observation) {
  assertExactKeys(observation, [
    'contract',
    'source',
    'checked_in_workflow',
    'surfaces',
    'publication',
    'artifact'
  ], 'checked-in observation')
  assert(observation.contract === CONTRACT, 'observation contract is unsupported')
  assertExactKeys(observation.source, ['repository', 'revision', 'tree', 'ref', 'ref_protected'], 'observation source')
  assertExactKeys(observation.checked_in_workflow, [
    'path',
    'root_workflow',
    'executed_by_github',
    'execution_reason',
    'browser_gate_claimed',
    'playwright_marker',
    'upload_pages_artifact_marker',
    'sha256'
  ], 'checked-in workflow')
  assertExactKeys(observation.surfaces, ['product_origin', 'proof_registry'], 'observation surfaces')
  assertExactKeys(observation.publication, ['executed', 'provider', 'canonical_url', 'browser_gate_claimed'], 'observation publication')
  assert(observation.publication.executed === false, 'observation must not claim publication executed')
  assert(observation.publication.provider === null, 'observation must not name a publication provider')
  assert(observation.publication.canonical_url === null, 'observation must not name a publication URL')
  assert(observation.publication.browser_gate_claimed === false, 'observation must not claim a browser gate')
  assert(observation.checked_in_workflow.executed_by_github === false, 'checked-in workflow text is not execution')
  assert(observation.checked_in_workflow.browser_gate_claimed === false, 'observation must not claim a browser gate')
  assert(observation.surfaces.product_origin === PRODUCT_ORIGIN, 'product origin does not match the pinned origin')
  assert(observation.surfaces.proof_registry === PROOF_REGISTRY, 'proof registry does not match the pinned registry')
  assert(SHA256.test(observation.checked_in_workflow.sha256 ?? ''), 'workflow digest is invalid')
  assertExactKeys(observation.artifact, [
    'algorithm',
    'root_scheme',
    'file_count',
    'total_bytes',
    'root_sha256',
    'files'
  ], 'observation artifact')
  assert(Array.isArray(observation.artifact.files), 'observation artifact files must be an array')
  const seen = new Set()
  let previous = ''
  for (const file of observation.artifact.files) {
    assertExactKeys(file, ['path', 'bytes', 'sha256'], 'observation artifact file')
    validateArtifactPath(file.path)
    assert(!seen.has(file.path), `duplicate observation artifact path: ${file.path}`)
    assert(previous === '' || previous < file.path, 'observation artifact paths are not in canonical order')
    seen.add(file.path)
    previous = file.path
    assert(Number.isSafeInteger(file.bytes) && file.bytes >= 0, `artifact byte count is invalid: ${file.path}`)
    assert(SHA256.test(file.sha256 ?? ''), `artifact digest is invalid: ${file.path}`)
  }
  assert(Number.isSafeInteger(observation.artifact.file_count) && observation.artifact.file_count > 0, 'observation artifact file count is invalid')
  assert(observation.artifact.file_count === observation.artifact.files.length, 'observation artifact file count is inconsistent')
  assert(Number.isSafeInteger(observation.artifact.total_bytes) && observation.artifact.total_bytes >= 0, 'observation artifact total bytes is invalid')
  assert(
    observation.artifact.total_bytes === observation.artifact.files.reduce((total, file) => total + file.bytes, 0),
    'observation artifact total bytes is inconsistent'
  )
  assert(observation.artifact.algorithm === 'sha256', 'observation artifact algorithm is unsupported')
  assert(observation.artifact.root_scheme === ARTIFACT_ROOT_SCHEME, 'observation artifact root scheme is unsupported')
  assert(SHA256.test(observation.artifact.root_sha256 ?? ''), 'observation artifact root digest is invalid')
  assert(observation.artifact.root_sha256 === artifactRoot(observation.artifact.files), 'observation artifact root digest is inconsistent')
}

export function writeObservation(distPath, context, workflow) {
  const root = resolve(distPath)
  const path = resolve(root, MANIFEST_NAME)
  const observation = buildObservation(root, context, workflow)
  assertObservationShape(observation)
  try {
    writeFileSync(path, `${JSON.stringify(observation, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
  } catch (error) {
    if (error?.code === 'EEXIST') {
      throw new Error(`${MANIFEST_NAME} already exists; refusing to overwrite observation evidence`)
    }
    throw error
  }
  return observation
}

export function verifyObservation(distPath, context, workflow) {
  validateSourceContext(context)
  const root = resolve(distPath)
  const path = resolve(root, MANIFEST_NAME)
  assert(existsSync(path) && lstatSync(path).isFile(), `${MANIFEST_NAME} is missing`)
  const observation = JSON.parse(readFileSync(path, 'utf8'))
  assertObservationShape(observation)
  const expected = buildObservation(root, context, workflow)
  assert(JSON.stringify(observation) === JSON.stringify(expected), 'checked-in observation does not match source or artifact bytes')
  return observation
}
