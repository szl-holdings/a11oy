# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""Source contract for the /console Try Khipu panel.

Does not add a nav data-view. No tokens/s marketing
number inside the panel slice.
"""
import re
import shutil
import subprocess
from pathlib import Path

CONSOLE = Path(__file__).resolve().parents[1] / "pages" / "console.html"
BEGIN = "/* try-khipu-panel"
END = "/* end try-khipu-panel */"


def _panel_slice() -> str:
    html = CONSOLE.read_text(encoding="utf-8")
    start = html.find(BEGIN)
    stop = html.find(END)
    assert start >= 0, "Try Khipu panel marker missing from pages/console.html"
    assert stop > start, "Try Khipu panel end marker missing from pages/console.html"
    return html[start:stop]


def test_try_khipu_panel_present_on_command_center_only():
    html = CONSOLE.read_text(encoding="utf-8")
    slice_ = _panel_slice()
    assert "Try Khipu" in slice_
    assert "/api/a11oy/v1/khipu/status" in slice_
    assert "/api/a11oy/v1/khipu/chat" in slice_
    assert "UNSIGNED" in slice_
    assert "Conjecture 1" in slice_
    assert "READY" in slice_
    assert "FAILED" in slice_
    assert "record_sha256" in slice_
    assert 'data-view="' not in slice_
    assert "data-view='" not in slice_
    # wrap Command Center only
    assert "V.command" in slice_ or "command.render" in slice_
    assert "currentView()!=='command'" in slice_ or "currentView()!==\"command\"" in slice_
    # 1396 owns ?view= deep links (Investor View). Honor that param so Try Khipu
    # does not mount on a non-command surface.
    assert "URLSearchParams" in slice_
    assert "get('view')" in slice_ or 'get("view")' in slice_


def test_try_khipu_panel_has_no_tokens_per_second_marketing():
    slice_ = _panel_slice()
    lowered = slice_.lower()
    assert "tokens/s" not in lowered
    assert "tok/s" not in lowered
    assert "tokens_per_second" not in lowered
    assert "tokens per second" not in lowered


def test_try_khipu_honesty_labels():
    slice_ = _panel_slice()
    compact = re.sub(r"\s+", "", slice_)
    assert "ROADMAP" in slice_
    assert "SNAPSHOT" in slice_
    assert "UNAVAILABLE" in slice_
    assert "not-a-secret" in slice_
    assert "https://szlholdings-szl-model-inference-lab.hf.space/v1" in slice_
    assert "not a trainer" in slice_
    assert "not Serve Studio" in slice_
    assert "not a live control plane" in slice_
    assert "forge-lab" not in slice_ or "not forge-lab" in slice_

    # The panel starts fail-closed. Runtime status may become READY or FAILED only
    # from a successful JSON response; transport/malformed-response failures are
    # UNAVAILABLE; the browser has no static numeric fallback for API evidence.
    assert "chip('UNAVAILABLE','UNAVAILABLE')" in compact
    assert "if(!r.ok)thrownewError" in compact
    assert "thrownewError('malformedstatusresponse')" in compact
    assert "renderUnavailable" in slice_
    assert "varenergyRuns='UNAVAILABLE'" in compact
    assert "hon.energy_attested_runs.trim()" not in compact
    assert "pin.energy_attested_runs.trim()" not in compact
    assert "||'8/8 SIMULATED'" not in compact
    assert "locked_formulas:8" not in compact
    assert "doc.locked_formula_count" in compact
    assert "doc.locked_formula_ids" in compact
    assert "doc.locked_formula_count===8" in compact
    assert "lockedIds.length===8" in compact
    assert "(newSet(lockedIds)).size===8" in compact
    assert "['F1','F4','F7','F11','F12','F18','F19','F22']" in compact

    # Proxy elapsed time is independent of receipt proof. The former may be
    # MEASURED from the proxy wall clock; the latter stays UNAVAILABLE because
    # this response carries no payload/key/chain verification tuple.
    assert "elapsedMeasured" in slice_
    assert "hasMeasuredEvidence" not in slice_
    assert "d.elapsed_ms_label==='MEASURED'" in compact
    assert "d.elapsed_ms_source==='PROXY_WALL'" in compact
    assert "responseOK=r.ok&&d.ok===true&&st==='READY'" in compact
    assert "Number.isFinite(d.elapsed_ms)" in compact
    assert "elapsedLabel=elapsedMeasured?'MEASURED':'UNAVAILABLE'" in compact
    assert "chip('RECEIPTUNAVAILABLE','UNAVAILABLE'" in compact
    assert "MEASUREDRECEIPT" not in compact
    assert "receipt_evidence_label==='MEASURED'" not in compact
    assert "reportedSig==='UNSIGNED'?'UNSIGNED':'UNAVAILABLE'" in compact
    assert "recordLabel=recordReported?'REPORTED':'UNAVAILABLE'" in compact
    assert "upstream-reportedandformat-checkedonly;notcryptographicallyverified" in compact
    assert "elapsed_ms_label||'MEASURED'" not in compact
    assert "d.usage_label==='REPORTED'" in compact
    assert "usageLabel=usageAvailable?'REPORTED':'UNAVAILABLE'" in compact
    assert "usage_label||'REPORTED'" not in compact


def test_try_khipu_runtime_separates_measured_elapsed_from_unverified_receipt():
    """Execute the real panel functions with Node DOM/fetch stubs.

    This is a behavior test, not a string snapshot: malformed status and incomplete,
    failed, or provenance-free chat responses must render UNAVAILABLE. A complete
    response may admit measured proxy elapsed time but never receipt proof.
    """
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the console behavior contract"

    panel = _panel_slice()
    start = panel.index("  function esc")
    stop = panel.index("  /* Mount into the Command Center body only. */")
    logic = panel[start:stop]
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const logic = fs.readFileSync(0, 'utf8');

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {id, innerHTML: '', textContent: '', value: '', disabled: false});
  }
  return elements.get(id);
}
['tk-run', 'tk-prompt', 'tk-out', 'tk-state', 'tk-pin', 'tk-honesty'].forEach(element);
element('tk-prompt').value = 'What is Khipu?';

global.document = {getElementById: (id) => element(id)};
global.window = {location: {search: '', hash: '#command'}};
let queue = [];
global.fetch = async () => {
  assert.ok(queue.length > 0, 'unexpected fetch');
  return queue.shift();
};
const response = (payload, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => payload,
});

vm.runInThisContext(
  "var STATUS_URL='/api/a11oy/v1/khipu/status';" +
  "var CHAT_URL='/api/a11oy/v1/khipu/chat';" +
  "var LOCKED_LAB_V1='https://szlholdings-szl-model-inference-lab.hf.space/v1';" +
  "var HOST_ID='tk-panel-host';\n" + logic +
  "\nglobalThis.__tk={ask:ask,loadStatus:loadStatus};"
);

const status = {
  lab_status: 'READY',
  pin: {energy_attested_runs: '99/99 MEASURED'},
  honesty: {energy_attested_runs: '<img src=x onerror=alert(1)>'},
  doctrine: {
    version: 'v11',
    state: 'LOCKED',
    locked_formula_count: 9,
    locked_formula_ids: ['F1','F2','F3','F4','F5','F6','F7','F8','F9'],
    lambda: 'Conjecture 1',
  },
};
const complete = {
  ok: true,
  lab_status: 'READY',
  text: 'receipt-backed answer',
  signature: 'UNSIGNED',
  record_sha256: 'a'.repeat(64),
  elapsed_ms: 12,
  elapsed_ms_source: 'PROXY_WALL',
  elapsed_ms_label: 'MEASURED',
  receipt_evidence_label: 'UNAVAILABLE',
  signature_evidence_label: 'UNAVAILABLE',
  record_hash_evidence_label: 'UNAVAILABLE',
  usage: {prompt_tokens: 2, completion_tokens: 3, total_tokens: 5},
  usage_label: 'REPORTED',
};

async function runChat(payload, ok = true, statusCode = 200) {
  queue = [response(payload, ok, statusCode), response(status)];
  await globalThis.__tk.ask();
  await new Promise((resolve) => setImmediate(resolve));
  return element('tk-out').innerHTML;
}

(async () => {
  queue = [response([])];
  await globalThis.__tk.loadStatus();
  assert.match(element('tk-state').innerHTML, /UNAVAILABLE/);
  assert.match(element('tk-pin').innerHTML, /malformed status response/);

  queue = [response(status)];
  await globalThis.__tk.loadStatus();
  assert.match(element('tk-pin').innerHTML, /ENERGY ATTESTED RUNS/);
  assert.match(element('tk-pin').innerHTML, /UNAVAILABLE/);
  assert.doesNotMatch(element('tk-pin').innerHTML, /99\/99|<img/);
  assert.match(element('tk-pin').innerHTML, /locked formulas UNAVAILABLE/);

  const incomplete = await runChat({...complete, record_sha256: 'not-a-digest'});
  assert.match(incomplete, /RECEIPT UNAVAILABLE/);
  assert.doesNotMatch(incomplete, /MEASURED RECEIPT/);
  assert.match(incomplete, /MEASURED ELAPSED/);

  const noSource = {...complete};
  delete noSource.elapsed_ms_source;
  const noSourceHtml = await runChat(noSource);
  assert.match(noSourceHtml, /RECEIPT UNAVAILABLE/);
  assert.match(noSourceHtml, /ELAPSED UNAVAILABLE/);

  const failed = await runChat(complete, false, 503);
  assert.match(failed, /RECEIPT UNAVAILABLE/);
  assert.match(failed, /ELAPSED UNAVAILABLE/);

  const forgedProof = await runChat({...complete, receipt_evidence_label: 'MEASURED'});
  assert.match(forgedProof, /RECEIPT UNAVAILABLE/);
  assert.doesNotMatch(forgedProof, /MEASURED RECEIPT/);

  const completeHtml = await runChat(complete);
  assert.match(completeHtml, /MEASURED ELAPSED/);
  assert.match(completeHtml, /RECEIPT UNAVAILABLE/);
  assert.doesNotMatch(completeHtml, /MEASURED RECEIPT/);
  assert.match(completeHtml, /12 ms/);
  assert.match(completeHtml, /REPORTED/);
  assert.match(completeHtml, /upstream-reported and format-checked only/);
})().catch((error) => {
  console.error(error && error.stack || error);
  process.exitCode = 1;
});
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=logic,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_try_khipu_does_not_wire_forge_lab_as_trainer_or_studio():
    slice_ = _panel_slice()
    lowered = slice_.lower()
    assert "/api/a11oy/v1/khipu/chat" in slice_
    assert "szl-model-inference-lab" in slice_
    assert "szl-forge-lab.hf.space" not in lowered
    assert "forge-lab as a trainer" not in lowered
    assert "serve studio" in lowered  # disclaimed, not wired
    assert "not serve studio" in lowered or "not a serve studio" in lowered
