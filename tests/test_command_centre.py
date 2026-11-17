# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline command-centre route, provenance and failure-boundary tests."""

from datetime import datetime, timedelta, timezone
import inspect
import hashlib
import json
import shutil
import subprocess

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from routers import command_centre as centre


@pytest.fixture
def client():
    app = FastAPI()
    app.add_api_route('/a11oy/atelier', lambda: {'legacy': True})
    centre.register(app)
    return TestClient(app)


def snapshot(age=0):
    return {'observed_at': (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
            'counts': {'models': 49, 'datasets_public': 34, 'kernels': 14, 'spaces_public': 24}}


@pytest.mark.parametrize('path', ['/command-centre', '/a11oy/atelier'])
def test_owned_page_and_security_headers(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert 'Command centre' in response.text
    assert response.headers['cache-control'] == 'no-store, no-transform'
    assert "default-src 'none'" in response.headers['content-security-policy']
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert client.head(path).status_code == 200


def test_owned_page_states_provider_retention_boundary(client):
    page = client.get('/a11oy/atelier').text
    assert 'store: false' in page
    assert 'API audit retention is 30 days by default' in page
    assert 'No server-side conversation history is retained' not in page
    runbook = (centre.ROOT.parents[1] / 'docs' / 'ATELIER_COMMAND_CENTRE.md').read_text(encoding='utf-8')
    assert 'Provider storage is disabled' not in runbook
    assert 'x-zero-data-retention' in runbook


@pytest.mark.parametrize('path', ['/command-centre/app.js', '/command-centre/style.css',
                                 '/command-centre/szl/szl-design-system.css',
                                 '/command-centre/szl/szl-console.css'])
def test_owned_assets(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert len(response.content) > 100
    assert client.head(path).status_code == 200


def test_manifest_has_source_order_not_mutation_or_inference(client, monkeypatch):
    monkeypatch.setenv('SZL_GIT_SHA', 'a' * 40)
    data = client.get('/api/a11oy/v1/command-centre/manifest').json()
    assert data['source_revision'] == 'a' * 40
    assert data['read_only'] is True
    assert data['external_mutation_performed'] is False
    assert data['inference_verified'] is False
    assert data['authorities']['source'] == 'szl-holdings/a11oy'
    assert data['release_order'][0] == 'protected_github_source'
    assert data['release_order'][1] == 'canonical_hf_publication'
    assert len(data['surfaces']) == 18
    assert all(s['href'].startswith(('/', 'https://')) for s in data['surfaces'])
    assert any(s['href'] == '/command-v2' for s in data['surfaces'])
    assert any(s['href'] == 'https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab'
               and 'unsigned' in s['boundary'] for s in data['surfaces'])


@pytest.mark.parametrize('sha', ['', 'main', 'a' * 39, 'A' * 40, '<script>'])
def test_unverified_revision_is_not_asserted(monkeypatch, sha):
    monkeypatch.setenv('SZL_GIT_SHA', sha)
    assert centre.manifest()['source_revision'] is None


def test_inventory_uses_fixed_bounded_public_transport(monkeypatch):
    calls = []
    def transport(url, **kwargs):
        calls.append((url, kwargs))
        return snapshot(), None
    monkeypatch.setattr(centre, 'http_json', transport)
    data = centre.proof_inventory()
    assert data['state'] == 'OBSERVED_SNAPSHOT'
    assert data['inference_verified'] is False
    assert calls == [(centre.PROOF_INVENTORY, {'timeout': 12, 'max_response_bytes': 1048576,
                                             'max_redirects': 0, 'allow_private': False})]


def test_stale_inventory_is_explicit(monkeypatch):
    monkeypatch.setattr(centre, 'http_json', lambda *a, **k: (snapshot(90000), None))
    assert centre.proof_inventory()['state'] == 'STALE_SNAPSHOT'


@pytest.mark.parametrize('value', [None, True, -1, 100001, '49', 1.5])
def test_invalid_count_fails_closed(monkeypatch, value):
    data = snapshot()
    data['counts']['models'] = value
    monkeypatch.setattr(centre, 'http_json', lambda *a, **k: (data, None))
    result = centre.proof_inventory()
    assert result['state'] == 'UNAVAILABLE'
    assert result['counts'] is None


@pytest.mark.parametrize('value', [None, 'garbage', '2026-09-29T00:00:00',
                                 (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()])
def test_invalid_observation_fails_closed(monkeypatch, value):
    data = snapshot()
    data['observed_at'] = value
    monkeypatch.setattr(centre, 'http_json', lambda *a, **k: (data, None))
    assert centre.proof_inventory()['code'] == 'PROOF_INVENTORY_INVALID_TIME'


def test_transport_errors_are_safe(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('SECRET provider body')
    monkeypatch.setattr(centre, 'http_json', broken)
    result = centre.proof_inventory()
    assert result['code'] == 'PROOF_INVENTORY_UNAVAILABLE'
    assert 'SECRET' not in str(result)


def test_get_does_not_call_provider_or_store_credentials():
    code = (centre.ROOT / 'app.js').read_text(encoding='utf-8')
    assert 'localStorage' not in code
    assert 'sessionStorage' not in code
    assert 'innerHTML' not in code
    assert 'textContent' in code
    assert 'reasoning_effort' in code
    assert 'window.confirm' in code
    assert "json('/api/a11oy/v1/atelier/local/health')" in code
    assert "json('/api/a11oy/v1/atelier/local/turn'" in code
    assert "json('/api/a11oy/v1/atelier/cpu-lab/health')" in code
    assert "json('/api/a11oy/v1/atelier/cpu-lab/turn'" in code
    assert "declared: 'PUBLIC'" in code
    assert 'public_share_acknowledged: true' in code
    assert "el('cpu-public-ack').checked = false" in code
    assert 'szlholdings-szl-model-inference-lab.hf.space' not in code
    assert 'localStorage' not in code


def test_css_has_existing_design_system(client):
    page = client.get('/command-centre').text
    assert '/command-centre/szl/szl-design-system.css' in page
    assert '/command-centre/szl/szl-console.css' in page


def test_bundled_study_is_pinned_not_performance_evidence(client):
    response = client.get('/api/a11oy/v1/command-centre/study')
    assert response.status_code == 200
    data = response.json()
    assert data['schema'] == 'szl.atelier.model-intake.v1'
    assert data['collection']['ranking_is_quality'] is False
    assert data['collection']['metadata_is_successful_inference'] is False
    assert data['collection']['model_weights_downloaded'] is False
    assert data['collection']['public_code_executed'] is False
    models = data['collection']['models']
    assert len(models) == len({item['id'] for item in models}) == 17
    assert all(len(item['revision']) == 40 for item in models)
    assert all(item['deployment_admitted'] is False for item in models)


def test_missing_study_is_unavailable(client, monkeypatch, tmp_path):
    monkeypatch.setattr(centre, 'STUDY', tmp_path / 'missing.json')
    response = client.get('/api/a11oy/v1/command-centre/study')
    assert response.status_code == 503
    assert response.json()['inference_verified'] is False


def test_owned_assets_emit_body_not_zero_copy_pathsend(client):
    response = client.get('/command-centre')
    assert '</html>' in response.text
    assert 'id="turn-form"' in response.text
    assert 'id="local-turn-form"' in response.text
    assert 'id="cpu-turn-form"' in response.text
    assert 'id="cpu-public-ack"' in response.text
    for element_id in ('cpu-sources-panel', 'cpu-sources', 'cpu-citations'):
        assert f'id="{element_id}"' in response.text
    assert 'unsigned local lab record' in response.text
    assert 'UNSIGNED_LOCAL' in response.text
    assert 'public source handles' in response.text
    assert 'no action authority' in response.text
    assert 'Grounding consistency checks do not prove' in response.text
    assert 'maxlength="1200"' in response.text
    assert 'This is not Grok' in response.text
    assert 'id="study-models"' in response.text
    assert 'FileResponse(' not in inspect.getsource(centre)


def test_missing_serving_source_is_unavailable(client, monkeypatch, tmp_path):
    monkeypatch.setattr(centre, 'ROOT', tmp_path)
    response = client.get('/command-centre')
    assert response.status_code == 503
    assert response.json()['code'] == 'PAGE_SOURCE_UNAVAILABLE'
    manifest = client.get('/api/a11oy/v1/command-centre/manifest')
    assert manifest.status_code == 503
    assert manifest.json()['code'] == 'PAGE_SOURCE_UNAVAILABLE'


def test_page_is_bound_to_python_renderer_and_exact_public_inputs(client):
    response = client.get('/command-centre')
    assert response.content == centre.page_bytes()
    manifest = client.get('/api/a11oy/v1/command-centre/manifest').json()
    assert manifest['presentation']['mode'] == 'PYTHON_SERVER_RENDERED'
    assert manifest['presentation']['renderer'] == 'routers/command_centre_view.py'
    assert manifest['presentation']['sources'] == centre.presentation_sources()
    assert 'routers/command_centre_web/index.html' not in manifest['presentation']['sources']
    assert manifest['public_estate']['sha256'] == hashlib.sha256(centre.PUBLIC_ESTATE.read_bytes()).hexdigest()
    model_bytes = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    digest = hashlib.sha256(model_bytes).hexdigest()
    assert f'data-view-input-sha256="{digest}"' in response.text
    assert 'INVENTORY_ONLY · ORG_CARD' in response.text
    assert 'not a governed keeper' in response.text


def test_vendor_exception_is_byte_bound_not_application_exemption():
    vendor_root = centre.ROOT / 'szl'
    manifest_bytes = (vendor_root / 'SOURCE.json').read_bytes()
    provenance = json.loads(manifest_bytes)
    assert provenance['version'] == '1.3.0'
    assert provenance['source_commit'] == '27d12e77fc0f9f1a0e5fae8b34adf2380d51d070'
    subset = json.loads((vendor_root / 'VENDORED.json').read_text(encoding='utf-8'))
    assert subset['schema'] == 'szl.kanchay-vendored-subset/v1'
    assert subset['scope'] == 'STATIC_PRESENTATION_ASSETS_ONLY'
    assert subset['upstream'] == {
        'repository': 'szl-holdings/szl-brand',
        'revision': '4309f6fce89179331b0b3ed8c99494e76c5be256',
        'manifest_path': 'kanchay/SOURCE.json',
        'manifest_sha256': '967a77235227f1d75852fb61873e46336e67403cbc0e7e12b141e31c83fbd93d',
    }
    assert hashlib.sha256(manifest_bytes).hexdigest() == subset['upstream']['manifest_sha256']
    assert set(subset['files']) == {'szl-design-system.css', 'szl-console.css'}
    assert {p.name for p in vendor_root.iterdir()} == set(subset['files']) | {'SOURCE.json', 'VENDORED.json'}
    for name, digest in subset['files'].items():
        assert digest == provenance['sha256'][name]
        assert hashlib.sha256((vendor_root / name).read_bytes()).hexdigest() == digest
    from scripts.check_banned_tokens import Allowlist
    allowlist = Allowlist.load(str(centre.ROOT.parents[1] / '.doctrine-allowlist'))
    assert allowlist.is_allowed('routers/command_centre_web/szl/szl-design-system.css')
    assert not allowlist.is_allowed('routers/command_centre_web/app.js')
    assert not allowlist.is_allowed('routers/command_centre_web/index.html')



def test_cpu_form_auth_disclosure_and_proposal_outcomes():
    """Execute the shipped frontend against explicit, adversarial API outcomes."""
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the CPU form behavior contract"
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(0, 'utf8');
const elements = new Map();
function element(id = '') {
  if (id && elements.has(id)) return elements.get(id);
  const value = {
    id, value: '', checked: false, hidden: true, disabled: false,
    textContent: '', innerHTML: '', children: [], listeners: {},
    addEventListener(event, listener) { this.listeners[event] = listener; },
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); },
  };
  if (id) elements.set(id, value);
  return value;
}
const turnPath = '/api/a11oy/v1/atelier/cpu-lab/turn';
const calls = [], windowListeners = {}, timeoutBudgets = [];
let nextResult, allowConfirmation = true, confirmations = 0;
const response = (value, status = 200) => ({
  ok: status >= 200 && status < 300, status,
  headers: { get: name => name === 'content-type' ? 'application/json' : null },
  json: async () => value,
});
const health = {
  ready: true, mode: 'NO_PROVIDER_KEY_PUBLIC_CPU_LAB',
  ready_scope: 'LOCAL_PREREQUISITES_ONLY', model: 'test-owned-model', blockers: [],
};
const getResults = new Map([
  ['/api/a11oy/v1/command-centre/manifest', { surfaces: [] }],
  ['/api/build-info', { git_sha: 'a'.repeat(40) }],
  ['/api/a11oy/v1/atelier/health', { ready: false, blockers: ['NOT_CONFIGURED'] }],
  ['/api/a11oy/v1/command-centre/inventory', {
    counts: { models: 1, kernels: 0, datasets_public: 0, spaces_public: 1 },
    state: 'OBSERVED_SNAPSHOT', observed_at: '2026-11-16T00:00:00Z',
  }],
  ['/api/a11oy/v1/command-centre/study', {
    schema: 'szl.atelier.model-intake.v1', collection: { models: [] },
  }],
  ['/api/a11oy/v1/atelier/local/health', { ready: false, blockers: ['NOT_CONFIGURED'] }],
  ['/api/a11oy/v1/atelier/cpu-lab/health', health],
]);
const context = {
  document: { getElementById: element, createElement: () => element() },
  window: {
    addEventListener: (event, listener) => { windowListeners[event] = listener; },
    confirm: () => { confirmations += 1; return allowConfirmation; },
  },
  AbortController, clearTimeout,
  setTimeout: (callback, milliseconds) => {
    timeoutBudgets.push(milliseconds);
    return setTimeout(callback, milliseconds);
  },
  fetch: async (url, options = {}) => {
    calls.push({ url, options });
    assert.ok(url.startsWith('/') && !url.startsWith('//'), 'Cross-origin request');
    if (options.method === 'POST') {
      assert.equal(url, turnPath);
      assert.equal(options.credentials, 'same-origin');
      assert.equal(options.cache, 'no-store');
      return typeof nextResult === 'function' ? nextResult() : nextResult;
    }
    assert.ok(getResults.has(url), 'Unexpected page-load request');
    assert.equal(options.headers?.Authorization, undefined);
    return response(getResults.get(url));
  },
};
vm.runInNewContext(code, context);
const settle = () => new Promise(resolve => setImmediate(resolve));
const submit = () => element('cpu-turn-form').listeners.submit({ preventDefault() {} });
const posts = () => calls.filter(call => call.options.method === 'POST');
function prepare() {
  element('cpu-operator-key').value = 'frontend-test-operator';
  element('cpu-prompt').value = 'Which public source supports this claim?';
  element('cpu-public-ack').checked = true;
}
const proposal = {
  state: 'COMPLETED', answer: '<img src=x> is inert proposal text.',
  provider_decision: 'PROPOSAL', provider_output_signature_status: 'UNSIGNED_LOCAL',
  grounding_required: true, authority: 'NO_ACTION_AUTHORITY', executed: false,
  evidence_handles: [
    { nodeId: 'public:alpha', nodeKind: 'DOCUMENT', label: '<img src=x> source', note: '<script>inert()</script>' },
    { nodeId: 'public:beta', nodeKind: 'DOCUMENT', label: 'Second public source', note: 'Returned evidence handle' },
  ],
  citations: ['public:alpha'],
  receipt: { digest: 'e'.repeat(64), phase: 'OUTCOME' },
  dsse: { payloadType: 'test-only', payload: 'test-only' },
};

(async () => {
  await settle();
  assert.equal(posts().length, 0, 'Page load caused inference');
  assert.equal(calls.length, getResults.size);
  assert.equal(element('cpu-send').disabled, false);
  assert.match(element('cpu-state').textContent, /remote identity not yet checked/);

  prepare(); element('cpu-operator-key').value = '';
  await submit(); assert.equal(posts().length, 0, 'Anonymous request escaped');
  prepare(); element('cpu-public-ack').checked = false;
  await submit(); assert.equal(posts().length, 0, 'Missing disclosure acknowledgement');
  prepare(); element('cpu-prompt').value += ' ';
  await submit(); assert.equal(posts().length, 0, 'Prompt was silently normalized');
  prepare(); element('cpu-prompt').listeners.input();
  assert.equal(element('cpu-public-ack').checked, false, 'Edited prompt retained acknowledgement');
  await submit(); assert.equal(posts().length, 0);

  prepare(); nextResult = response(proposal);
  await submit();
  assert.equal(posts().length, 1);
  const sent = posts()[0];
  assert.equal(timeoutBudgets.at(-1), 90000);
  assert.ok(timeoutBudgets.at(-1) >= 3 * 4000 + 60000 + 10000,
    'Client budget must cover three preflights, inference and response grace');
  assert.equal(sent.options.headers.Authorization, 'Bearer frontend-test-operator');
  assert.deepEqual(JSON.parse(sent.options.body), {
    prompt: 'Which public source supports this claim?', declared: 'PUBLIC',
    public_share_acknowledged: true, max_output_tokens: 24,
  });
  assert.equal(element('cpu-public-ack').checked, false);
  assert.equal(element('cpu-answer').hidden, false);
  assert.equal(element('cpu-answer').textContent, proposal.answer);
  assert.equal(element('cpu-answer').innerHTML, '');
  assert.equal(element('cpu-receipt-panel').hidden, false);
  assert.equal(JSON.parse(element('cpu-receipt').textContent).answer, undefined);
  assert.equal(element('cpu-sources-panel').hidden, false);
  assert.equal(element('cpu-sources').children.length, proposal.evidence_handles.length);
  for (const [index, row] of element('cpu-sources').children.entries()) {
    const handle = proposal.evidence_handles[index];
    assert.equal(row.textContent, `${handle.label}\n${handle.nodeKind} · ${handle.nodeId}\n${handle.note}`);
    assert.equal(row.innerHTML, '', 'Source metadata became markup');
    assert.equal(row.href, undefined, 'A URL was invented for an evidence handle');
  }
  assert.equal(element('cpu-citations').textContent, 'Citations returned: public:alpha');
  assert.deepEqual(JSON.parse(element('cpu-receipt').textContent).evidence_handles, proposal.evidence_handles);
  assert.match(element('cpu-turn-status').textContent, /UNSIGNED_LOCAL; no action authority/);

  const invalid = [
    { provider_decision: 'HOLD' }, { provider_output_signature_status: 'SIGNED' },
    { grounding_required: false }, { authority: 'ACTION_AUTHORITY' },
    { executed: true }, { state: 'HOLD' }, { answer: '   ' },
    { evidence_handles: [] }, { citations: ['unknown:source'] },
  ];
  const missingDecision = { ...proposal }; delete missingDecision.provider_decision;
  for (const value of [...invalid.map(change => ({ ...proposal, ...change })), missingDecision]) {
    prepare(); nextResult = response(value);
    const before = posts().length;
    await submit(); await settle();
    assert.equal(posts().length, before + 1, 'Automatic retry after invalid outcome');
    assert.equal(element('cpu-answer').hidden, true, 'Unverified proposal displayed');
    assert.equal(element('cpu-answer').textContent, '');
    assert.equal(element('cpu-sources-panel').hidden, true);
    assert.equal(element('cpu-sources').children.length, 0);
    assert.equal(element('cpu-citations').textContent, '');
    assert.equal(JSON.parse(element('cpu-receipt').textContent).evidence_handles, undefined);
    assert.match(element('cpu-turn-status').textContent, /UNAVAILABLE.*CPU_LAB_INVALID_OUTCOME/);
    assert.equal(element('cpu-receipt-panel').hidden, false);
  }

  for (const [state, status] of [['ABSTAIN', 422], ['REVIEW', 409], ['BLOCKED', 503]]) {
    prepare(); nextResult = response({
      ...proposal, state, provider_decision: state, code: 'CPU_LAB_' + state,
    }, status);
    const before = posts().length;
    await submit(); await settle();
    assert.equal(posts().length, before + 1, 'Automatic retry after terminal decision');
    assert.equal(element('cpu-answer').hidden, true, 'Terminal decision exposed an answer');
    assert.equal(element('cpu-sources-panel').hidden, true, 'Terminal decision exposed proposal sources');
    assert.equal(element('cpu-sources').children.length, 0);
    assert.equal(JSON.parse(element('cpu-receipt').textContent).evidence_handles, undefined);
    assert.equal(JSON.parse(element('cpu-receipt').textContent).citations, undefined);
    assert.match(element('cpu-turn-status').textContent, new RegExp(state + '.*CPU_LAB_' + state));
    assert.equal(JSON.parse(element('cpu-receipt').textContent).provider_decision, state);
  }

  for (const reason of ['INCOMPLETE_OUTPUT', '<img src=x>', 'X'.repeat(65)]) {
    prepare(); nextResult = response({
      state: 'UNAVAILABLE', code: 'CPU_LAB_INVALID_RESPONSE', reason_code: reason,
      receipt: { payload: { contract_reason_code: reason } },
    }, 502);
    await submit();
    const status = element('cpu-turn-status').textContent;
    assert.match(status, /UNAVAILABLE · CPU_LAB_INVALID_RESPONSE/);
    assert.equal(status.includes(` · ${reason}.`), reason === 'INCOMPLETE_OUTPUT',
      'Only a bounded uppercase contract reason should appear beside the failure code');
    assert.equal(element('cpu-turn-status').innerHTML, '');
    assert.equal(element('cpu-answer').hidden, true);
  }

  prepare();
  let release;
  nextResult = () => new Promise(resolve => { release = resolve; });
  const beforePending = posts().length;
  const pending = submit();
  await submit();
  assert.equal(posts().length, beforePending + 1, 'Double submission');
  release(response(proposal)); await pending;

  prepare(); nextResult = () => { throw new Error('transport timeout'); };
  await submit(); await settle();
  const beforeRetry = posts().length, beforeConfirm = confirmations;
  assert.match(element('cpu-turn-status').textContent, /outcome uncertain/);
  allowConfirmation = false; prepare(); await submit();
  assert.equal(posts().length, beforeRetry);
  assert.equal(confirmations, beforeConfirm + 1, 'Uncertain retry needs fresh confirmation');

  element('operator-key').value = 'test-grok-operator';
  element('local-operator-key').value = 'test-local-operator';
  windowListeners.pagehide();
  for (const id of ['operator-key', 'local-operator-key', 'cpu-operator-key']) {
    assert.equal(element(id).value, '', 'Credential retained after page exit');
  }
  assert.equal(element('cpu-public-ack').checked, false);
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=(centre.ROOT / "app.js").read_text(encoding="utf-8"),
        encoding="utf-8", capture_output=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
