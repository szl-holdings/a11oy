# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The console's CPU lab entry is navigation, never anonymous inference."""
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
    panel = _panel_slice()
    assert "Try Khipu" in panel
    assert 'href="/command-centre#cpu-work"' in panel
    assert 'data-view="' not in panel
    assert "data-view='" not in panel
    assert "V.command" in panel
    assert "currentView()!=='command'" in panel
    assert "URLSearchParams" in panel
    assert "get('view')" in panel


def test_try_khipu_panel_has_no_tokens_per_second_marketing():
    lowered = _panel_slice().lower()
    for phrase in ("tokens/s", "tok/s", "tokens_per_second", "tokens per second"):
        assert phrase not in lowered


def test_try_khipu_navigation_preserves_disclosure_and_evidence_boundaries():
    panel = _panel_slice()
    assert "operator credential" in panel
    assert "exact prompt is public" in panel
    assert "UNSIGNED_LOCAL" in panel
    assert "NO_ACTION_AUTHORITY" in panel
    assert "execute no action" in panel
    assert "Energy evidence remains UNAVAILABLE" in panel
    assert "Conjecture 1" in panel
    assert "No prompt is collected or sent here" in panel
    assert "fetch(" not in panel
    assert "XMLHttpRequest" not in panel
    assert "localStorage" not in panel
    assert "sessionStorage" not in panel
    assert "<textarea" not in panel
    assert "<input" not in panel
    assert "not-a-secret" not in panel
    assert "/api/a11oy/v1/khipu/chat" not in panel
    assert "/v1/chat/completions" not in panel


def test_try_khipu_runtime_never_sends_and_honors_deep_links():
    """Run the actual panel, including mount and repeated render behavior."""
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the console behavior contract"
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(0, 'utf8');

function element() {
  return {
    id: '', innerHTML: '', children: [],
    setAttribute() {},
    appendChild(child) { this.children.push(child); },
    querySelector(selector) {
      return this.children.find(child => '#' + child.id === selector) || null;
    },
  };
}

function boot(search, hash) {
  const host = element();
  let networkCalls = 0, originalRenders = 0;
  const callbacks = [];
  const context = {
    URLSearchParams,
    document: {
      readyState: 'complete',
      getElementById: id => id === 'vbody' ? host : null,
      createElement: element,
      addEventListener() { throw new Error('Unexpected document callback'); },
    },
    window: {
      location: { search, hash },
      VIEWS: { command: { async render() { originalRenders += 1; } } },
    },
    fetch() { networkCalls += 1; throw new Error('Navigation must not fetch'); },
    setInterval(callback) { callbacks.push(callback); return callbacks.length; },
    clearInterval() {},
  };
  vm.runInNewContext(source, context);
  return { host, context, callbacks,
    networkCalls: () => networkCalls, renders: () => originalRenders };
}

(async () => {
  const command = boot('', '#command');
  assert.equal(command.host.children.length, 1);
  const html = command.host.children[0].innerHTML;
  assert.match(html, /href="\/command-centre#cpu-work"/);
  assert.doesNotMatch(html, /<(?:input|textarea|button)\b/);
  await command.context.window.VIEWS.command.render(command.host);
  command.callbacks.forEach(callback => callback());
  assert.equal(command.host.children.length, 1, 'Duplicate panel on render');
  assert.equal(command.renders(), 1, 'Existing renderer must still run');
  assert.equal(command.networkCalls(), 0);
  for (const [search, hash] of [
    ['?view=investor', '#command'], ['', '#fleet'], ['?view=proof', ''],
  ]) {
    const other = boot(search, hash);
    await other.context.window.VIEWS.command.render(other.host);
    other.callbacks.forEach(callback => callback());
    assert.equal(other.host.children.length, 0, 'Panel escaped command surface');
    assert.equal(other.networkCalls(), 0);
  }
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
"""
    result = subprocess.run(
        [node, "-e", harness], input=_panel_slice(), text=True,
        capture_output=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_try_khipu_does_not_wire_forge_lab_as_trainer_or_studio():
    lowered = _panel_slice().lower()
    assert "szl-forge-lab.hf.space" not in lowered
    assert "not a trainer" in lowered
    assert "not serve studio" in lowered
    assert "not a live control plane" in lowered
