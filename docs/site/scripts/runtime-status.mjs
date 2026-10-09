// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Adapted from public szl-holdings/docs-site scripts/verify-runtime-status.mjs
// at 83664f8b8924b36d3179bd94d133ca0815aaee91 (Apache-2.0).
// readiness_observed_at_observation is a derived probe flag.
// It is not a LIVE, VERIFIED, or AGI stamp. HTTP 200 is REACHABLE.
// This module does not read docs/status.md. That page is a different table.

const allowedSurfaceFields = new Set([
  'id',
  'repository',
  'revision',
  'provider_stage',
  'provider_error',
  'probe',
  'evidence_state',
  'readiness_observed_at_observation'
])
const allowedStatusFields = new Set(['contract', 'observation_window_ended_at', 'method', 'surfaces', 'non_claims'])
const allowedProbeFields = new Set(['url', 'outcome', 'http_status', 'attempt_timeouts_seconds'])
const allowedStages = new Set(['RUNNING', 'PAUSED', 'BUILDING', 'STARTING', 'ERROR', 'STOPPED'])
const allowedStates = new Set(['AVAILABLE_AT_OBSERVATION', 'UNAVAILABLE'])
const expectedSurfaceBindings = new Map([
  ['a11oy', { repository: 'SZLHOLDINGS/a11oy', probe: 'https://szlholdings-a11oy.hf.space/healthz', label: 'a11oy' }],
  ['killinchu', { repository: 'SZLHOLDINGS/killinchu', probe: 'https://szlholdings-killinchu.hf.space/api/killinchu/healthz', label: 'killinchu' }],
  ['hatun-mcp', { repository: 'SZLHOLDINGS/hatun-mcp', probe: 'https://szlholdings-hatun-mcp.hf.space/readyz', label: 'Hatun-MCP' }]
])
const expectedSurfaceIds = [...expectedSurfaceBindings.keys()]
const statusHeaders = ['Surface', 'Published revision', 'Provider state', 'Readiness probe', 'Evidence state']

function exactFields(value, allowed, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} must be an object`)
  const extras = Object.keys(value).filter((key) => !allowed.has(key))
  if (extras.length) throw new Error(`${label} contains unsupported field(s): ${extras.join(', ')}`)
  const missing = [...allowed].filter((key) => !Object.hasOwn(value, key))
  if (missing.length) throw new Error(`${label} is missing required field(s): ${missing.join(', ')}`)
}

function requireNonEmptyStringArray(value, label) {
  if (!Array.isArray(value)
    || value.length === 0
    || value.some((entry) => typeof entry !== 'string' || !entry.trim())) {
    throw new Error(`${label} must contain nonempty strings`)
  }
}

function requireCanonicalUtcSeconds(value, label) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) {
    throw new Error(`${label} must be exact UTC seconds`)
  }
  const instant = new Date(value)
  if (Number.isNaN(instant.valueOf()) || instant.toISOString().replace('.000Z', 'Z') !== value) {
    throw new Error(`${label} must be a real canonical UTC instant`)
  }
}

export function validateRuntimeStatus(status) {
  exactFields(status ?? {}, allowedStatusFields, 'runtime status')
  if (status?.contract !== 'szl.docs.runtime-status/v1') throw new Error('unsupported runtime-status contract')
  requireCanonicalUtcSeconds(status.observation_window_ended_at, 'observation timestamp')
  if (typeof status.method !== 'string' || !status.method.trim()) throw new Error('runtime observation method is required')
  if (!Array.isArray(status.surfaces) || status.surfaces.length === 0) throw new Error('runtime surfaces are required')
  requireNonEmptyStringArray(status.non_claims, 'runtime non-claims')

  const ids = new Set()
  for (const surface of status.surfaces) {
    exactFields(surface, allowedSurfaceFields, `surface ${surface?.id ?? '<unknown>'}`)
    exactFields(surface.probe ?? {}, allowedProbeFields, `probe ${surface?.id ?? '<unknown>'}`)
    if (!/^[a-z0-9-]+$/.test(surface.id ?? '') || ids.has(surface.id)) throw new Error(`invalid or duplicate surface id: ${surface.id}`)
    ids.add(surface.id)
    if (!/^SZLHOLDINGS\/[A-Za-z0-9._-]+$/.test(surface.repository ?? '')) throw new Error(`invalid repository for ${surface.id}`)
    if (!/^[0-9a-f]{40}$/.test(surface.revision ?? '')) throw new Error(`invalid immutable revision for ${surface.id}`)
    if (!allowedStages.has(surface.provider_stage)) throw new Error(`invalid provider stage for ${surface.id}`)
    if (surface.provider_error !== null
      && (typeof surface.provider_error !== 'string' || !surface.provider_error.trim())) {
      throw new Error(`invalid provider error for ${surface.id}`)
    }
    if (!allowedStates.has(surface.evidence_state)) throw new Error(`invalid evidence state for ${surface.id}`)
    if (!/^https:\/\/[^/]+\/.+/.test(surface.probe.url ?? '')) throw new Error(`invalid HTTPS probe URL for ${surface.id}`)
    let probeHost = ''
    try {
      probeHost = new URL(surface.probe.url).hostname.toLowerCase()
    } catch {
      throw new Error(`invalid HTTPS probe URL for ${surface.id}`)
    }
    if (probeHost === 'a11oy.com' || probeHost.endsWith('.a11oy.com')) {
      throw new Error(`foreign storefront probe is refused for ${surface.id}`)
    }
    const binding = expectedSurfaceBindings.get(surface.id)
    if (binding && (surface.repository !== binding.repository || surface.probe.url !== binding.probe)) {
      throw new Error(`canonical repository/probe binding mismatch for ${surface.id}`)
    }
    if (!['RESPONSE', 'TIMEOUT'].includes(surface.probe.outcome)) throw new Error(`invalid probe outcome for ${surface.id}`)
    if (!Array.isArray(surface.probe.attempt_timeouts_seconds)
      || surface.probe.attempt_timeouts_seconds.length === 0
      || surface.probe.attempt_timeouts_seconds.some((seconds) => !Number.isInteger(seconds) || seconds < 1)) {
      throw new Error(`invalid bounded probe timeouts for ${surface.id}`)
    }

    if (surface.probe.outcome === 'TIMEOUT' && surface.probe.http_status !== null) throw new Error(`timeout must not invent an HTTP status for ${surface.id}`)
    if (surface.probe.outcome === 'RESPONSE'
      && (!Number.isInteger(surface.probe.http_status) || surface.probe.http_status < 100 || surface.probe.http_status > 599)) {
      throw new Error(`response must include a valid HTTP status for ${surface.id}`)
    }
    const available = surface.provider_stage === 'RUNNING'
      && surface.probe.outcome === 'RESPONSE'
      && Number.isInteger(surface.probe.http_status)
      && surface.probe.http_status >= 200
      && surface.probe.http_status < 300
    if (surface.readiness_observed_at_observation !== available) throw new Error(`readiness flag is not derived from evidence for ${surface.id}`)
    if ((surface.evidence_state === 'AVAILABLE_AT_OBSERVATION') !== available) throw new Error(`evidence label is not derived from evidence for ${surface.id}`)
  }
  if (JSON.stringify([...ids].sort()) !== JSON.stringify([...expectedSurfaceIds].sort())) {
    throw new Error(`runtime surface set must be exact: ${expectedSurfaceIds.join(', ')}`)
  }
  return status
}

export function validateStatusTable(statusPage, status) {
  const lines = statusPage.split(/\r?\n/)
  const headerIndexes = []
  for (let index = 0; index < lines.length; index++) {
    const cells = markdownTableCells(lines[index])
    if (cells && JSON.stringify(cells) === JSON.stringify(statusHeaders)) headerIndexes.push(index)
  }
  if (headerIndexes.length !== 1) throw new Error('status table must contain exactly one canonical five-cell header')

  const headerIndex = headerIndexes[0]
  const delimiter = markdownTableCells(lines[headerIndex + 1] ?? '')
  if (!delimiter || delimiter.length !== statusHeaders.length || delimiter.some((cell) => !/^:?-{3,}:?$/.test(cell))) {
    throw new Error('status table delimiter must contain exactly five cells')
  }

  const rows = []
  for (let index = headerIndex + 2; index < lines.length && lines[index].trim(); index++) {
    const cells = markdownTableCells(lines[index])
    if (!cells || cells.length !== statusHeaders.length) throw new Error('status table row must contain exactly five cells')
    rows.push(cells)
  }
  if (rows.length !== expectedSurfaceIds.length) throw new Error('status table must contain exactly one row per runtime surface')

  for (const surface of status.surfaces) {
    const binding = expectedSurfaceBindings.get(surface.id)
    const label = `**${binding.label}**`
    const matches = rows.filter((cells) => cells[0] === label)
    if (matches.length !== 1) throw new Error(`status table row is not unique and exactly bound: ${surface.id}`)
    const [, revisionCell, providerCell, probeCell, evidenceCell] = matches[0]

    if (revisionCell !== `\`${surface.revision}\`` || providerCell !== `\`${surface.provider_stage}\``) {
      throw new Error(`status table row is not exactly bound to runtime evidence: ${surface.id}`)
    }
    const route = `\`GET ${new URL(surface.probe.url).pathname}\``
    if (!probeCell.startsWith(route)) throw new Error(`status table row is not exactly bound to runtime evidence: ${surface.id}`)

    if (surface.probe.outcome === 'TIMEOUT') {
      const observedTimeouts = [...probeCell.matchAll(/\b(\d+)\s+s\b/g)].map((match) => Number(match[1]))
      if (!/\btimed out\b/i.test(probeCell)
        || /\bHTTP\s+\d{3}\b/i.test(probeCell)
        || JSON.stringify(observedTimeouts) !== JSON.stringify(surface.probe.attempt_timeouts_seconds)) {
        throw new Error(`status table row is not exactly bound to runtime evidence: ${surface.id}`)
      }
    } else {
      const observedStatuses = [...probeCell.matchAll(/\bHTTP\s+(\d{3})\b/gi)].map((match) => Number(match[1]))
      if (/\btimed out\b/i.test(probeCell)
        || observedStatuses.length !== 1
        || observedStatuses[0] !== surface.probe.http_status) {
        throw new Error(`status table row is not exactly bound to runtime evidence: ${surface.id}`)
      }
    }

    const expectedQuotas = (surface.provider_error?.match(/(?:current|limit)=\d+/g) ?? []).sort()
    const observedQuotas = (probeCell.match(/(?:current|limit)=\d+/g) ?? []).sort()
    const observedStates = [...evidenceCell.matchAll(/\*\*(AVAILABLE_AT_OBSERVATION|UNAVAILABLE)\*\*/g)].map((match) => match[1])
    if (JSON.stringify(observedQuotas) !== JSON.stringify(expectedQuotas)
      || !evidenceCell.startsWith(`**${surface.evidence_state}**`)
      || observedStates.length !== 1
      || observedStates[0] !== surface.evidence_state) {
      throw new Error(`status table row is not exactly bound to runtime evidence: ${surface.id}`)
    }
  }
  return true
}

function markdownTableCells(line) {
  const trimmed = line.trim()
  if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) return null
  return trimmed.slice(1, -1).split('|').map((cell) => cell.trim())
}
