// SPDX-License-Identifier: Apache-2.0
// Authorized read-only diagnostic. Private alert data are encrypted before disk.
import { constants, createCipheriv, createHash, publicEncrypt, randomBytes } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const REPOSITORY = 'szl-holdings/a11oy';
export const KEY_DIGEST = '4f2fda56c2b5730b7426c408553e05ca9d337aa4414401154ebdc4fe3a2ae74c';
const SHA = /^[0-9a-f]{40}$/;
const LIMIT = 4 * 1024 * 1024;

export function seal(report, recipient, binding) {
  if (createHash('sha256').update(recipient).digest('hex') !== KEY_DIGEST) throw new Error('RECIPIENT_MISMATCH');
  const plain = Buffer.from(JSON.stringify(report));
  if (plain.length > 32 * 1024 * 1024) throw new Error('REPORT_BOUND');
  const key = randomBytes(32), nonce = randomBytes(12), aad = Buffer.from(JSON.stringify(binding));
  const cipher = createCipheriv('aes-256-gcm', key, nonce);
  cipher.setAAD(aad);
  const ciphertext = Buffer.concat([cipher.update(plain), cipher.final()]);
  const envelope = {
    schema: 'szl.encrypted-security-observation/v1', algorithm: 'RSA-OAEP-SHA256/AES-256-GCM',
    recipient_sha256: KEY_DIGEST, binding, aad: aad.toString('base64'),
    wrapped_key: publicEncrypt({ key: recipient, oaepHash: 'sha256', padding: constants.RSA_PKCS1_OAEP_PADDING }, key).toString('base64'),
    nonce: nonce.toString('base64'), tag: cipher.getAuthTag().toString('base64'),
    ciphertext: ciphertext.toString('base64'),
  };
  key.fill(0); plain.fill(0);
  return envelope;
}

export async function githubRead(path, token, fetcher = fetch) {
  if (!path.startsWith(`/repos/${REPOSITORY}`) || /[\r\n\\]/.test(path)) throw new Error('DESTINATION');
  const url = new URL(path, 'https://api.github.com');
  if (url.origin !== 'https://api.github.com' || !(url.pathname === `/repos/${REPOSITORY}` || url.pathname.startsWith(`/repos/${REPOSITORY}/`))) throw new Error('DESTINATION');
  let response;
  try {
    response = await fetcher(url, { method: 'GET', redirect: 'error',
      headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`,
        'User-Agent': 'SZL-authorized-encrypted-security-observer/1', 'X-GitHub-Api-Version': '2022-11-28' },
      signal: AbortSignal.timeout(30000) });
  } catch { throw new Error('READ_UNAVAILABLE'); }
  if (response.status !== 200) { await response.body?.cancel(); throw new Error(`READ_HTTP_${response.status}`); }
  const announced = response.headers.get('content-length');
  if (announced !== null && (!/^\d+$/.test(announced) || Number(announced) > LIMIT)) {
    await response.body?.cancel(); throw new Error('RESPONSE_BOUND');
  }
  const chunks = []; let bytes = 0;
  try {
    for await (const chunk of response.body) {
      bytes += chunk.length;
      if (bytes > LIMIT) throw new Error('RESPONSE_BOUND');
      chunks.push(chunk);
    }
  } catch { throw new Error('RESPONSE_READ'); }
  if (announced !== null && !response.headers.get('content-encoding') && bytes !== Number(announced)) throw new Error('RESPONSE_TRUNCATED');
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw new Error('JSON_INVALID'); }
}

export async function collect(read) {
  const report = { schema: 'szl.private-code-scanning-observation/v1', repository: REPOSITORY,
    started_at: new Date().toISOString(), scope: 'open code-scanning alerts on refs/heads/main',
    status: 'UNAVAILABLE', complete: false, alerts: [], high_priority_instances: [],
    repository_mutations: 0, alert_mutations: 0, source_code_executed: false };
  try {
    const repo = await read(`/repos/${REPOSITORY}`);
    if (repo.full_name !== REPOSITORY || repo.private !== false || repo.default_branch !== 'main') throw new Error('REPOSITORY_IDENTITY');
    const before = await read(`/repos/${REPOSITORY}/git/ref/heads/main`);
    const revision = before.object?.sha;
    if (!SHA.test(revision || '')) throw new Error('SOURCE_IDENTITY');
    report.default_revision_before = revision;
    const seen = new Set(); let terminated = false;
    for (let page = 1; page <= 11; page++) {
      const rows = await read(`/repos/${REPOSITORY}/code-scanning/alerts?state=open&ref=refs%2Fheads%2Fmain&per_page=100&page=${page}&sort=created&direction=asc`);
      if (!Array.isArray(rows) || rows.length > 100) throw new Error('ALERT_LIST_SCHEMA');
      for (const row of rows) {
        if (!row || !Number.isSafeInteger(row.number) || row.number < 1 || row.state !== 'open' || seen.has(row.number)) throw new Error('ALERT_IDENTITY');
        if (row.url !== `https://api.github.com/repos/${REPOSITORY}/code-scanning/alerts/${row.number}`) throw new Error('ALERT_ORIGIN');
        seen.add(row.number); report.alerts.push(row);
        if (report.alerts.length > 1000) throw new Error('ALERT_COUNT_BOUND');
      }
      if (rows.length < 100) { terminated = true; break; }
    }
    if (!terminated) throw new Error('ALERT_PAGINATION_BOUND');
    const urgent = report.alerts.filter(row => ['critical', 'high'].includes(row.rule?.security_severity_level));
    if (urgent.length > 100) throw new Error('INSTANCE_REQUEST_BOUND');
    for (const alert of urgent) {
      const rows = await read(`/repos/${REPOSITORY}/code-scanning/alerts/${alert.number}/instances?ref=refs%2Fheads%2Fmain&per_page=100&page=1`);
      if (!Array.isArray(rows) || rows.length >= 100) throw new Error('INSTANCE_COVERAGE');
      report.high_priority_instances.push({ number: alert.number, instances: rows });
    }
    const after = await read(`/repos/${REPOSITORY}/git/ref/heads/main`);
    report.default_revision_after = after.object?.sha;
    if (report.default_revision_after !== revision) throw new Error('DEFAULT_SOURCE_MOVED');
    report.complete = true; report.status = 'OBSERVED';
  } catch (error) {
    // Only fixed locally produced diagnostic codes enter public output.
    report.error_code = /^[A-Z_0-9]{1,64}$/.test(error?.message || '') ? error.message : 'OBSERVATION_FAILED';
  }
  report.finished_at = new Date().toISOString();
  return report;
}

export function publicSummary(report, binding) {
  const counts = { critical: 0, high: 0, medium: 0, low: 0, other: 0 };
  for (const row of report.alerts) {
    const severity = row.rule?.security_severity_level;
    counts[Object.hasOwn(counts, severity) ? severity : 'other']++;
  }
  return { schema: 'szl.security-observation-summary/v1', ...binding,
    status: report.status, complete: report.complete, scope: report.scope,
    default_revision_before: report.default_revision_before ?? null,
    default_revision_after: report.default_revision_after ?? null,
    alert_count: report.complete ? report.alerts.length : null,
    severity_counts: report.complete ? counts : null,
    error_code: report.error_code ?? null, plaintext_alerts_persisted: false,
    plaintext_alert_paths_published: false, alert_dismissals: 0,
    security_clearance: false, finished_at: report.finished_at };
}

async function main() {
  if (process.env.GITHUB_REPOSITORY !== REPOSITORY || !SHA.test(process.env.GITHUB_SHA || '')) throw new Error('WORKFLOW_IDENTITY');
  if (!process.env.GITHUB_TOKEN) throw new Error('READ_CREDENTIAL_UNAVAILABLE');
  const recipient = readFileSync(new URL('./audit-recipient.pem', import.meta.url), 'utf8');
  if (createHash('sha256').update(recipient).digest('hex') !== KEY_DIGEST) throw new Error('RECIPIENT_MISMATCH');
  const binding = { repository: REPOSITORY, observer_revision: process.env.GITHUB_SHA,
    run_id: process.env.GITHUB_RUN_ID, run_attempt: process.env.GITHUB_RUN_ATTEMPT };
  const report = await collect(path => githubRead(path, process.env.GITHUB_TOKEN));
  const encrypted = seal(report, recipient, binding), summary = publicSummary(report, binding);
  mkdirSync('security-observation', { recursive: false, mode: 0o700 });
  writeFileSync('security-observation/encrypted-observation.json', JSON.stringify(encrypted), { mode: 0o600, flag: 'wx' });
  writeFileSync('security-observation/summary.json', JSON.stringify(summary, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  console.log(JSON.stringify(summary));
  if (!report.complete) process.exitCode = 2;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(() => { console.error('SECURITY_OBSERVATION_NOT_COMPLETED'); process.exitCode = 2; });
}
