# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed truth contracts for the current-main console successor."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"


def _console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def _energy_slice() -> str:
    return _between(_console(), "V['energyReceipts']", "V['energyGrid']")


def test_console_claims_fail_closed() -> None:
    console = _console()

    assert "built for energy-evidence-aware sovereign compute" in console
    assert 'aria-label="platform evidence and runtime receipts"' in console
    assert "built on measured-energy sovereign compute" not in console
    assert 'aria-label="live measured platform receipts"' not in console

    energy = _energy_slice()
    assert "current entry digest" in energy
    assert "does not bind the top-level billing or freshness fields" in energy
    assert "never promotes a reported joule value to MEASURED" in energy
    assert "r.receipt" in energy
    assert "receipt.decision" in energy
    assert "decision.joules_label" in energy
    assert "decision.joules_measured" not in energy
    assert "r.entry_digest" in energy
    assert "receipt.payload_digest" in energy
    assert "getJSON('/api/a11oy/v1/energy/ledger')" in energy
    assert "_szlFetch('/api/a11oy/v1/energy/ledger')" not in energy
    assert "chainOK" in energy
    assert "var admitted" not in energy
    assert "var label='UNAVAILABLE'" in energy
    assert "var joules='UNAVAILABLE'" in energy
    assert "upstream label (not admitted)" in energy
    assert "/^sha256:[0-9a-f]{64}$/i" in energy
    assert "signature: UNAVAILABLE" in energy
    assert "r.joules_label" not in energy
    assert "r.measured_joules" not in energy
    assert "r.idempotency_key" not in energy
    assert "carbon_grams" not in energy
    assert "Every governed inference through a11oy produces a signed energy receipt" not in console
    assert "every inference turn mints a signed energy receipt here" not in console


def test_energy_receipts_runtime_never_promotes_unbound_billing_metadata() -> None:
    """Execute the renderer against honest and adversarial unbound metadata."""
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the energy receipt behavior contract"

    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const logic = fs.readFileSync(0, 'utf8');
let payload = {};
function getJSON(path) {
  assert.equal(path, '/api/a11oy/v1/energy/ledger');
  if (payload instanceof Error) return Promise.reject(payload);
  return Promise.resolve(payload);
}
function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}
const makeView = new Function(
  'V', 'getJSON', 'esc', logic + '\nreturn V["energyReceipts"];'
);
const view = makeView({}, getJSON, esc);
const digest = (char) => 'sha256:' + char.repeat(64);
const validEntry = {
  entry_digest: digest('a'),
  receipt: {
    payload_digest: digest('b'),
    decision: {joules_label: 'MEASURED', joules_measured: 12.5},
  },
  billable: true,
  reason: 'ok',
};
async function render(nextPayload) {
  payload = nextPayload;
  const container = {innerHTML: ''};
  view.render(container);
  await new Promise((resolve) => setImmediate(resolve));
  return container.innerHTML;
}
(async () => {
  const structurallyValid = await render({chain: {ok: true}, receipts: [validEntry]});
  assert.match(structurallyValid, /chain structure: <span>REPORTED OK<\/span>/);
  assert.match(structurallyValid, />UNAVAILABLE<\/span>/);
  assert.match(structurallyValid, /joules: UNAVAILABLE/);
  assert.match(structurallyValid, /upstream label \(not admitted\): MEASURED/);
  assert.match(structurallyValid, /reported disposition: BILLABLE/);
  assert.doesNotMatch(structurallyValid, /joules: 12\.5/);
  assert.doesNotMatch(structurallyValid, new RegExp(digest('a')));

  const brokenChain = await render({chain: {ok: false}, receipts: [validEntry]});
  assert.match(brokenChain, /chain structure: <span>FAILED<\/span>/);
  assert.match(brokenChain, /joules: UNAVAILABLE/);
  assert.doesNotMatch(brokenChain, /joules: 12\.5/);

  const refused = await render({
    chain: {ok: true},
    receipts: [{...validEntry, billable: false, reason: 'NVML sample stale'}],
  });
  assert.match(refused, /disposition: REFUSED/);
  assert.match(refused, /reason: NVML sample stale/);
  assert.match(refused, /joules: UNAVAILABLE/);

  const invalidDigest = await render({
    chain: {ok: true},
    receipts: [{...validEntry, entry_digest: '<img src=x onerror=alert(1)>', reason: '<img src=x>'}],
  });
  assert.match(invalidDigest, /joules: UNAVAILABLE/);
  assert.doesNotMatch(invalidDigest, /<img/);
  assert.match(invalidDigest, /&lt;img src=x&gt;/);

  const unavailable = await render(new Error('<em>ledger unavailable</em>'));
  assert.doesNotMatch(unavailable, /<em>/);
  assert.match(unavailable, /&lt;em&gt;ledger unavailable&lt;\/em&gt;/);
})().catch((error) => {
  console.error(error && error.stack || error);
  process.exitCode = 1;
});
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=_energy_slice(),
        encoding="utf-8",
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_investor_locked_formulas_use_canonical_doctrine_payload() -> None:
    console = _console()
    investor = _between(console, "/* Investor View", "<!-- DEV1 WAVE K")
    compact = re.sub(r"\s+", "", investor)

    assert "/api/a11oy/v1/honest" in investor
    assert 'id="inv-locked-ep">UNAVAILABLE' in investor
    assert 'id="inv-locked-list">UNAVAILABLE' in investor
    assert "locked_formula_count" in investor
    assert "locked_formula_ids" in investor
    assert "H.doctrine==='v11'" in compact
    assert "lockedCount===8" in compact
    assert "lockedIds.length===8" in compact
    assert "(newSet(lockedIds)).size===8" in compact
    assert "['F1','F4','F7','F11','F12','F18','F19','F22']" in compact
    assert "HASH-LINKED" not in investor
    assert "reported id:" in investor
    assert "exactly 8" not in investor
    assert "{F1, F4, F7, F11, F12, F18, F19, F22}" not in investor


def test_investor_receipt_id_is_escaped_at_runtime() -> None:
    """Exercise the real Investor renderer with a hostile ledger identifier."""
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the Investor behavior contract"

    block = _between(_console(), "/* Investor View", "<!-- DEV1 WAVE K")
    logic = block[block.index("(function(){"):block.rindex("</script>")]
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const logic = fs.readFileSync(0, 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {id, innerHTML: '', textContent: ''});
  return elements.get(id);
}
['inv-locked-ep', 'inv-locked-list', 'inv-one-receipt', 'inv-one-ep'].forEach(element);
element('inv-locked-ep').textContent = 'UNAVAILABLE';
element('inv-locked-list').textContent = 'UNAVAILABLE';
global.document = {getElementById: (id) => element(id)};
global.esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);
global.window = {
  VIEWS: {},
  getJSON: async (url) => {
    if (url === '/api/a11oy/v1/honest') {
      return {
        doctrine: 'v11',
        locked_formula_count: 9,
        locked_formula_ids: ['F1','F2','F3','F4','F5','F6','F7','F8','F9'],
      };
    }
    if (url === '/api/a11oy/v1/wow/ledger?limit=1') {
      return {receipts: [{receipt_id: '<img src=x onerror=alert(1)>', hash: 'reported'}]};
    }
    throw new Error('unexpected URL ' + url);
  },
};
vm.runInThisContext(logic);
(async () => {
  const container = {innerHTML: ''};
  await window.VIEWS.investor.render(container);
  const rendered = element('inv-one-receipt').innerHTML;
  assert.doesNotMatch(rendered, /<img/);
  assert.match(rendered, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(rendered, /REPORTED/);
  assert.equal(element('inv-one-ep').textContent, 'REPORTED');
  assert.equal(element('inv-locked-ep').textContent, 'UNAVAILABLE');
  assert.equal(element('inv-locked-list').textContent, 'UNAVAILABLE');
})().catch((error) => {
  console.error(error && error.stack || error);
  process.exitCode = 1;
});
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=logic,
        encoding="utf-8",
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
