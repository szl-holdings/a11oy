/* console/szl-build-badge.js — SPA footer build badge + meta tags (#3770).
 *
 * Vanilla JS, zero dependencies, 0 CDN. Fetches the read-only /api/build
 * receipt and renders release id + promotion-gate state in the SPA footer.
 * Honesty contract:
 *   - API unreachable → the badge shows the honest label UNKNOWN (release id
 *     unknown, API unreachable). It NEVER invents a build id.
 *   - UNKNOWN gate state renders as BLOCKED, matching the server contract.
 * It also writes two meta tags for crawlable build identity:
 *   <meta name="szl-release-id" content="...">
 *   <meta name="szl-build-gate" content="PASS|BLOCKED|UNKNOWN">
 *
 * WIRE-IN (reviewer step, one line; the SPA is a built artifact): add
 *   <script src="/szl-build-badge.js" defer></script>
 * to console/index.html near the existing deferred scripts.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
(function () {
  'use strict';

  function meta(name, content) {
    var found = document.querySelector('meta[name="' + name + '"]'); 
    if (found) { found.setAttribute('content', content); return; }
    var el = document.createElement('meta');
    el.setAttribute('name', name);
    el.setAttribute('content', content);
    document.head.appendChild(el);
  }

  function render(host, releaseId, gate) {
    var pill = document.createElement('span');
    pill.className = 'szl-build-badge';
    pill.style.cssText =
      'display:inline-block;font-family:ui-monospace,monospace;font-size:10px;' +
      'letter-spacing:.08em;color:#888;border:1px solid #333;border-radius:5px;' +
      'padding:.15rem .5rem;margin-left:.6rem;vertical-align:middle;';
    pill.textContent =
      'build ' + releaseId + ' · gate ' + gate;
    host.appendChild(pill);
  }

  function mount(releaseId, gate) {
    meta('szl-release-id', releaseId);
    meta('szl-build-gate', gate);
    var host = document.getElementById('szl-build-badge');
    if (!host) {
      host = document.createElement('span');
      host.id = 'szl-build-badge';
      var foot = document.querySelector('footer') || document.body;
      foot.appendChild(host);
    }
    host.textContent = '';
    render(host, releaseId, gate);
  }

  function fetchBuild(attempt) {
    if (attempt > 2) { mount('UNKNOWN', 'UNKNOWN'); return; }
    fetch('/api/build', { headers: { Accept: 'application/json' } })
      .then(function (res) { if (!res.ok) throw new Error('http ' + res.status); return res.json(); })
      .then(function (payload) {
        var ri = (payload && payload.release_id) ? String(payload.release_id) : 'UNKNOWN';
        var gate = (payload && payload.promotion_gate && payload.promotion_gate.decision)
          ? String(payload.promotion_gate.decision) : 'UNKNOWN';
        mount(ri, gate === 'UNKNOWN' ? 'BLOCKED' : gate);
      })
      .catch(function () { fetchBuild(attempt + 1); });
  }

  if (document.readyState !== 'loading') fetchBuild(1);
  else document.addEventListener('DOMContentLoaded', function () { fetchBuild(1); });
})();
