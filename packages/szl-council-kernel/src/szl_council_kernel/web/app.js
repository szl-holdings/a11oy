'use strict';

const byId = (id) => document.getElementById(id);
const shortDigest = (value) => (value ? `${value.slice(0, 18)}…${value.slice(-8)}` : '—');

function replaceCaseRows(cases) {
  const body = byId('cases');
  const fragment = document.createDocumentFragment();
  if (!Array.isArray(cases) || cases.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 4;
    cell.textContent = 'No governed cases recorded.';
    row.appendChild(cell);
    fragment.appendChild(row);
  } else {
    for (const item of cases) {
      const row = document.createElement('tr');
      const values = [
        item.case_id,
        item.state,
        shortDigest(item.envelope_digest),
        item.updated_at,
      ];
      for (const value of values) {
        const cell = document.createElement('td');
        cell.textContent = String(value ?? '—');
        row.appendChild(cell);
      }
      row.children[2].title = String(item.envelope_digest ?? '');
      fragment.appendChild(row);
    }
  }
  body.replaceChildren(fragment);
}

function setUnavailable() {
  byId('health').textContent = 'UNAVAILABLE';
  byId('health').className = 'chip bad';
  byId('ledgerState').textContent = 'UNAVAILABLE';
  byId('caseCount').textContent = '—';
  byId('eventCount').textContent = '—';
  replaceCaseRows([]);
}

async function load() {
  const refresh = byId('refresh');
  refresh.disabled = true;
  refresh.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('/api/v1/status', {
      cache: 'no-store',
      credentials: 'same-origin',
      headers: {Accept: 'application/json'},
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const ledgerPass = data?.ledger?.status === 'PASS';
    byId('health').textContent = ledgerPass ? 'LEDGER VERIFIED' : 'DEGRADED';
    byId('health').className = `chip ${ledgerPass ? 'ok' : 'bad'}`;
    byId('caseCount').textContent = String(Array.isArray(data.cases) ? data.cases.length : 0);
    byId('ledgerState').textContent = String(data?.ledger?.status ?? 'UNAVAILABLE');
    byId('eventCount').textContent = String(data?.ledger?.event_count ?? '—');
    byId('independence').textContent = String(Boolean(data.production_independence_verified)).toUpperCase();
    replaceCaseRows(data.cases);
    byId('lastUpdated').textContent = new Date().toISOString().replace('.000Z', 'Z');
  } catch (_error) {
    setUnavailable();
  } finally {
    refresh.disabled = false;
    refresh.removeAttribute('aria-busy');
  }
}

byId('refresh').addEventListener('click', load);
load();
window.setInterval(load, 15000);
