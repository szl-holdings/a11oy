// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Adapted from public szl-holdings/docs-site scripts/test-runtime-status.mjs
// at 83664f8b8924b36d3179bd94d133ca0815aaee91 (Apache-2.0).
import assert from 'node:assert/strict'
import test from 'node:test'
import { validateRuntimeStatus, validateStatusTable } from './runtime-status.mjs'

const base = Object.freeze({
  contract: 'szl.docs.runtime-status/v1',
  observation_window_ended_at: '2026-08-11T07:27:11Z',
  method: 'public probes',
  surfaces: [{
    id: 'a11oy',
    repository: 'SZLHOLDINGS/a11oy',
    revision: 'a'.repeat(40),
    provider_stage: 'RUNNING',
    provider_error: null,
    probe: { url: 'https://szlholdings-a11oy.hf.space/healthz', outcome: 'RESPONSE', http_status: 200, attempt_timeouts_seconds: [20] },
    evidence_state: 'AVAILABLE_AT_OBSERVATION',
    readiness_observed_at_observation: true
  }, {
    id: 'killinchu',
    repository: 'SZLHOLDINGS/killinchu',
    revision: 'b'.repeat(40),
    provider_stage: 'RUNNING',
    provider_error: null,
    probe: { url: 'https://szlholdings-killinchu.hf.space/api/killinchu/healthz', outcome: 'RESPONSE', http_status: 200, attempt_timeouts_seconds: [20] },
    evidence_state: 'AVAILABLE_AT_OBSERVATION',
    readiness_observed_at_observation: true
  }, {
    id: 'hatun-mcp',
    repository: 'SZLHOLDINGS/hatun-mcp',
    revision: 'c'.repeat(40),
    provider_stage: 'PAUSED',
    provider_error: 'Quota exceeded (current=3, limit=3)',
    probe: { url: 'https://szlholdings-hatun-mcp.hf.space/readyz', outcome: 'RESPONSE', http_status: 503, attempt_timeouts_seconds: [20] },
    evidence_state: 'UNAVAILABLE',
    readiness_observed_at_observation: false
  }],
  non_claims: ['point-in-time only']
})

function copy() {
  return structuredClone(base)
}

test('accepts availability only when provider and readiness evidence agree', () => {
  assert.equal(validateRuntimeStatus(copy()).surfaces[0].readiness_observed_at_observation, true)
})

test('requires every v1 field at the status, surface, and probe levels', () => {
  for (const [path, remove] of [
    ['status method', (status) => delete status.method],
    ['surface provider_error', (status) => delete status.surfaces[0].provider_error],
    ['probe http_status', (status) => delete status.surfaces[0].probe.http_status]
  ]) {
    const status = copy()
    remove(status)
    assert.throws(() => validateRuntimeStatus(status), /missing required field/, path)
  }
})

test('rejects empty methods, blank non-claims, and impossible UTC timestamps', () => {
  const emptyMethod = copy()
  emptyMethod.method = '   '
  assert.throws(() => validateRuntimeStatus(emptyMethod), /observation method is required/)

  const blankNonClaim = copy()
  blankNonClaim.non_claims = ['point-in-time only', '  ']
  assert.throws(() => validateRuntimeStatus(blankNonClaim), /nonempty strings/)

  for (const invalid of ['2026-99-99T99:99:99Z', '2026-02-29T07:27:11Z', '2026-08-11T07:27:11.000Z']) {
    const status = copy()
    status.observation_window_ended_at = invalid
    assert.throws(() => validateRuntimeStatus(status), /observation timestamp must/, invalid)
  }
})

test('rejects provider-running as operational when readiness timed out', () => {
  const status = copy()
  status.surfaces[0].probe = { ...status.surfaces[0].probe, outcome: 'TIMEOUT', http_status: null }
  assert.throws(() => validateRuntimeStatus(status), /readiness flag is not derived/)
})

test('requires a bounded attempt and a coherent HTTP response status', () => {
  const unbounded = copy()
  unbounded.surfaces[0].probe.attempt_timeouts_seconds = []
  assert.throws(() => validateRuntimeStatus(unbounded), /invalid bounded probe timeouts/)

  for (const invalid of [null, 99, 600, '200']) {
    const response = copy()
    response.surfaces[0].probe.http_status = invalid
    response.surfaces[0].evidence_state = 'UNAVAILABLE'
    response.surfaces[0].readiness_observed_at_observation = false
    assert.throws(() => validateRuntimeStatus(response), /valid HTTP status/)
  }
})

test('rejects successful probes when provider is paused', () => {
  const status = copy()
  status.surfaces[0].provider_stage = 'PAUSED'
  assert.throws(() => validateRuntimeStatus(status), /readiness flag is not derived/)
})

test('rejects mutable revisions, invented timeout statuses, and a LIVE stamp field', () => {
  const mutable = copy()
  mutable.surfaces[0].revision = 'main'
  assert.throws(() => validateRuntimeStatus(mutable), /immutable revision/)

  const invented = copy()
  invented.surfaces[0].probe.outcome = 'TIMEOUT'
  assert.throws(() => validateRuntimeStatus(invented), /timeout must not invent/)

  const expanded = copy()
  expanded.surfaces[0].marketing_label = 'LIVE'
  assert.throws(() => validateRuntimeStatus(expanded), /unsupported field/)
})

test('rejects missing, duplicate, or unexpected runtime surfaces', () => {
  const missing = copy()
  missing.surfaces.pop()
  assert.throws(() => validateRuntimeStatus(missing), /surface set must be exact/)

  const unexpected = copy()
  unexpected.surfaces[2].id = 'other'
  assert.throws(() => validateRuntimeStatus(unexpected), /surface set must be exact/)
})

test('rejects swapped runtime repository or probe bindings', () => {
  const status = copy()
  ;[status.surfaces[0].repository, status.surfaces[1].repository] = [status.surfaces[1].repository, status.surfaces[0].repository]
  ;[status.surfaces[0].probe.url, status.surfaces[1].probe.url] = [status.surfaces[1].probe.url, status.surfaces[0].probe.url]
  assert.throws(() => validateRuntimeStatus(status), /canonical repository\/probe binding mismatch/)
})

test('refuses the foreign storefront and does not retarget space probes at product or proof hosts', () => {
  for (const url of ['https://a11oy.com/healthz', 'https://www.a11oy.com/healthz']) {
    const foreign = copy()
    foreign.surfaces[0].probe.url = url
    assert.throws(() => validateRuntimeStatus(foreign), /foreign storefront probe is refused/, url)
  }
  for (const url of ['https://a-11-oy.com/healthz', 'https://a11oy.net/healthz']) {
    const otherSurface = copy()
    otherSurface.surfaces[0].probe.url = url
    assert.throws(() => validateRuntimeStatus(otherSurface), /canonical repository\/probe binding mismatch/, url)
  }
})

test('binds every status-table evidence dimension', () => {
  const status = copy()
  const table = [
    '| Surface | Published revision | Provider state | Readiness probe | Evidence state |',
    '|---|---|---|---|---|',
    `| **a11oy** | \`${'a'.repeat(40)}\` | \`RUNNING\` | \`GET /healthz\` -> HTTP 200 | **AVAILABLE_AT_OBSERVATION** |`,
    `| **killinchu** | \`${'b'.repeat(40)}\` | \`RUNNING\` | \`GET /api/killinchu/healthz\` -> HTTP 200 | **AVAILABLE_AT_OBSERVATION** |`,
    `| **Hatun-MCP** | \`${'c'.repeat(40)}\` | \`PAUSED\` | \`GET /readyz\` -> HTTP 503; quota \`current=3\`, \`limit=3\` | **UNAVAILABLE** |`
  ].join('\n')
  assert.equal(validateStatusTable(table, status), true)
  for (const [from, to] of [['`PAUSED`', '`RUNNING`'], ['HTTP 503', 'HTTP 200'], ['current=3', 'current=2'], ['GET /readyz', 'GET /healthz']]) {
    assert.throws(
      () => validateStatusTable(table.replace(from, to), status),
      /not exactly bound/,
      `table drift ${from} -> ${to} must fail closed`
    )
  }
})

test('rejects contradictory, duplicate, or non-five-cell status rows', () => {
  const status = copy()
  const rows = [
    '| Surface | Published revision | Provider state | Readiness probe | Evidence state |',
    '|---|---|---|---|---|',
    `| **a11oy** | \`${'a'.repeat(40)}\` | \`RUNNING\` | \`GET /healthz\` -> HTTP 200 | **AVAILABLE_AT_OBSERVATION** |`,
    `| **killinchu** | \`${'b'.repeat(40)}\` | \`RUNNING\` | \`GET /api/killinchu/healthz\` -> HTTP 200 | **AVAILABLE_AT_OBSERVATION** |`,
    `| **Hatun-MCP** | \`${'c'.repeat(40)}\` | \`PAUSED\` | \`GET /readyz\` -> HTTP 503; quota \`current=3\`, \`limit=3\` | **UNAVAILABLE** |`
  ]
  const table = rows.join('\n')
  assert.throws(
    () => validateStatusTable(table.replace('**UNAVAILABLE**', '**UNAVAILABLE** and **AVAILABLE_AT_OBSERVATION**'), status),
    /not exactly bound/
  )
  assert.throws(() => validateStatusTable(`${table}\n${rows[2]}`, status), /exactly one row per runtime surface/)
  assert.throws(() => validateStatusTable(table.replace('| **a11oy** |', '| **a11oy** | extra |'), status), /exactly five cells/)
})
