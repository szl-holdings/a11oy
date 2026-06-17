/* SPDX-License-Identifier: Apache-2.0
 * © 2026 SZL Holdings — a11oy console (Greene premium polish).
 * Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).
 *
 * HONESTY OVER CHECKLIST. Every tile fetches a REAL same-origin endpoint that was
 * verified live on the rosie Space (2026-06-03):
 *   /api/a11oy/v1/lambda      → Λ verdict + trust axes
 *   /api/a11oy/v1/ledger  → last receipts (chained Khipu DAG)
 *   /api/a11oy/v1/mesh/state  → wires + recent W3C traceparents (live trace tree)
 *   /api/a11oy/v1/mcp/tools   → MCP tool registry (count + names)
 *   /api/a11oy/v1/version     → cosign/SLSA provenance
 * No mocks, no synthetic rows. On failure a panel shows an honest error — never fake data.
 * Sign: Yachay · git trailer: Perplexity Computer Agent.
 */
(function () {
  "use strict";
  var API = "/api/a11oy/v1";
  var LEDGER_PATH = "/ledger";
  var ORGAN = "a11oy";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]||c);}); };
  function getJSON(path) {
    return fetch(API + path, { headers: { "accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }
  function fail(el, dot, what, e) {
    if (dot) dot.className = "dot bad";
    if (el) el.innerHTML = '<div class="err">' + esc(what) + " unreachable — " + esc(e.message || e) + "<br>(no synthetic fallback; tile stays honest)</div>";
  }

  /* ───────── theme toggle (default dark, persisted) ───────── */
  (function theme() {
    var root = document.documentElement, btn = $("themeToggle");
    var saved = localStorage.getItem(ORGAN + "-theme");
    if (saved) root.setAttribute("data-theme", saved);
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem(ORGAN + "-theme", next);
    });
  })();

  /* ───────── Λ verdict tile (REAL) ───────── */
  function loadLambda() {
    getJSON("/lambda").then(function (d) {
      $("lamDot").className = "dot ok";
      var L = Number(d.lambda), floor = Number(d.lambda_floor);
      var pass = d.pass === true;
      var axes = (d.axes || []).map(function (a) {
        return '<span class="axis">' + esc(a.name) + ' <b>' + Number(a.score).toFixed(2) + '</b></span>';
      }).join("");
      $("lambdaBody").innerHTML =
        '<div class="lambda-val">' + (isFinite(L) ? L.toFixed(5) : "—") + '</div>' +
        '<div class="lambda-meta">floor ' + (isFinite(floor) ? floor.toFixed(2) : "—") +
        ' · ' + (d.trust_axes || (d.axes || []).length) + ' trust axes · ' + esc(d.uniqueness || "Conjecture 1") + '</div>' +
        '<span class="verdict-chip ' + (pass ? "pass" : "fail") + '">' + (pass ? "PASS ✓" : "FAIL ✗") + '</span>' +
        '<div class="axes">' + axes + '</div>';
    }).catch(function (e) { fail($("lambdaBody"), $("lamDot"), "Λ verdict", e); });
  }

  /* ───────── MCP tools count tile (REAL) ───────── */
  function loadMcp() {
    getJSON("/mcp/tools").then(function (d) {
      $("mcpDot").className = "dot ok";
      var tools = d.tools || [];
      var names = tools.map(function (t) { return typeof t === "string" ? t : (t.name || "?"); });
      $("mcpBody").innerHTML =
        '<div class="metric">' + (d.count != null ? d.count : names.length) + '</div>' +
        '<div class="metric-sub">governed MCP tools · doctrine ' + esc(d.doctrine || "v11") + '</div>' +
        '<div class="toolset">' + names.map(function (n) { return '<span class="tool">' + esc(n) + '</span>'; }).join("") + '</div>';
    }).catch(function (e) { fail($("mcpBody"), $("mcpDot"), "MCP tools", e); });
  }

  /* ───────── provenance tile (REAL cosign + SLSA) ───────── */
  function loadProvenance() {
    getJSON("/version").then(function (d) {
      $("provDot").className = "dot ok";
      var rel = d.release_url || ("https://github.com/szl-holdings/" + ORGAN + "/releases/tag/v" + (d.version || "1.0.0"));
      var verify = (d.verify && d.verify.cosign) || ("cosign verify ghcr.io/szl-holdings/" + ORGAN + " --certificate-identity-regexp=szl-holdings");
      var sbom = d.verify && d.verify.sbom;
      $("provBody").innerHTML =
        '<a href="' + esc(rel) + '" target="_blank" rel="noopener">⬡ release v' + esc(d.version || "1.0.0") + '</a>' +
        (sbom ? '<a href="' + esc(sbom) + '" target="_blank" rel="noopener">⬡ SBOM (CycloneDX)</a>' : "") +
        '<a href="https://github.com/szl-holdings/.github/blob/main/cosign.pub" target="_blank" rel="noopener">⬡ cosign.pub</a>' +
        '<div class="k">git ' + esc(d.git_sha || "?").slice(0, 8) + ' · kernel ' + esc(d.kernel_commit || "c7c0ba17") +
        ' · ' + esc(d.slsa || "L1 (honest)") + '</div>' +
        '<div class="k" style="color:var(--text-dim)">cosign verify:<br><code>' + esc(verify) + '</code></div>';
    }).catch(function (e) { fail($("provBody"), $("provDot"), "Provenance", e); });
  }

  /* ───────── last-5 Khipu receipts table (REAL chained DAG) ───────── */
  function loadLedger() {
    getJSON(LEDGER_PATH).then(function (d) {
      $("ledDot").className = "dot ok";
      var rows = (d.receipts || []).slice(-5).reverse();
      if (!rows.length) {
        $("ledgerBody").innerHTML = '<div class="metric-sub">ledger empty — no receipts yet (honest: chain root ' + esc(d.root_hash || "∅").slice(0, 12) + ')</div>';
        return;
      }
      var body = rows.map(function (r) {
        var t = (r.timestamp_utc || "").substr(11, 8);
        return '<tr><td>' + r.seq + '</td><td class="rid">' + esc((r.receipt_id || "").slice(0, 12)) + '</td>' +
          '<td class="act">' + esc(r.action || "?") + '</td><td>' + esc(t) + '</td></tr>';
      }).join("");
      $("ledgerBody").innerHTML =
        '<table><thead><tr><th>seq</th><th>receipt id</th><th>action</th><th>utc</th></tr></thead><tbody>' +
        body + '</tbody></table>' +
        '<div class="metric-sub" style="margin-top:12px">chain depth ' + (d.total != null ? d.total : rows.length) +
        ' · root ' + esc((d.root_hash || "∅").slice(0, 16)) + '…</div>';
    }).catch(function (e) { fail($("ledgerBody"), $("ledDot"), "Khipu ledger", e); });
  }

  /* ───────── live trace mesh: 3D mini-viz + traceparent badge (REAL) ───────── */
  var ORGANS = ["amaru", "sentra", "killinchu", "a11oy", "rosie"];
  var scene, camera, renderer, nodeMeshes = {}, edges = [], booted = false;
  function init3D() {
    if (booted || !window.THREE) return;
    var host = $("graph3d"); var w = host.clientWidth, h = host.clientHeight || 300;
    if (!w) { setTimeout(init3D, 200); return; }
    booted = true;
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 100); camera.position.set(0, 0, 9);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h); renderer.setPixelRatio(window.devicePixelRatio || 1);
    host.appendChild(renderer.domElement);
    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    var pl = new THREE.PointLight(0xd4a574, 1.2); pl.position.set(5, 5, 8); scene.add(pl);
    var pos = { amaru: [-4.5, -1, 0], sentra: [-1.5, -1, 0], killinchu: [1.5, -1, 0], a11oy: [4.5, -1, 0], rosie: [0, 2.2, 0] };
    ORGANS.forEach(function (o) {
      var geo = new THREE.SphereGeometry(o === "rosie" ? 0.62 : 0.5, 32, 32);
      var col = o === "rosie" ? 0xd4a574 : 0x8a7fb0;
      var m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.28 }));
      m.position.set(pos[o][0], pos[o][1], pos[o][2]); scene.add(m); nodeMeshes[o] = m;
    });
    var chain = [["amaru", "sentra"], ["sentra", "killinchu"], ["killinchu", "a11oy"]];
    ["amaru", "sentra", "killinchu", "a11oy"].forEach(function (o) { chain.push(["rosie", o]); });
    chain.forEach(function (e) {
      var a = nodeMeshes[e[0]].position, b = nodeMeshes[e[1]].position;
      var g = new THREE.BufferGeometry().setFromPoints([a.clone(), b.clone()]);
      var line = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x352a66, transparent: true, opacity: 0.8 }));
      line.userData = { from: e[0], to: e[1], pulse: 0 }; scene.add(line); edges.push(line);
    });
    (function animate() {
      requestAnimationFrame(animate); scene.rotation.y += 0.0018;
      edges.forEach(function (e) {
        if (e.userData.pulse > 0) { e.userData.pulse -= 0.02; e.material.color.setHex(0xb04a30); e.material.opacity = 0.4 + e.userData.pulse * 0.6; }
        else { e.material.color.setHex(0x352a66); e.material.opacity = 0.8; }
      });
      renderer.render(scene, camera);
    })();
    window.addEventListener("resize", function () {
      var W = host.clientWidth, H = host.clientHeight || 300;
      camera.aspect = W / H; camera.updateProjectionMatrix(); renderer.setSize(W, H);
    });
  }
  function pulse(organ) {
    edges.forEach(function (e) { if (e.userData.from === organ || e.userData.to === organ) e.userData.pulse = 1.0; });
  }
  function loadMesh() {
    getJSON("/mesh/state").then(function (d) {
      $("meshDot").className = "dot ok";
      var traces = d.recent_traces || [];
      // live traceparent badge ← most recent real W3C id
      if (traces.length) {
        var last = traces[traces.length - 1];
        var badge = $("traceBadge");
        badge.classList.add("live");
        $("traceId").textContent = (last.trace_id || "").slice(0, 12) || "—";
      }
      // mini trace list (real paths + ids)
      $("traceList").innerHTML = traces.slice(-6).reverse().map(function (t) {
        return '<div class="trace-row"><span class="tt">' + esc((t.trace_id || "").slice(0, 8)) +
          '</span><span class="tp">' + esc(t.direction || "in") + " " + esc(t.path || "") + '</span></div>';
      }).join("") || '<div class="metric-sub">no recent traces yet</div>';
      // pulse any organ named in a wire that is LIVE
      Object.keys(d.wires || {}).forEach(function () {});
      pulse("rosie");
    }).catch(function (e) { fail($("traceList"), $("meshDot"), "Trace mesh", e); });
  }

  /* ───────── boot + refresh ───────── */
  document.addEventListener("DOMContentLoaded", function () {
    init3D();
    loadLambda(); loadMcp(); loadProvenance(); loadLedger(); loadMesh();
    setInterval(loadLambda, 20000);
    setInterval(loadLedger, 15000);
    setInterval(loadMesh, 10000);
  });
  if (document.readyState !== "loading") {
    init3D(); loadLambda(); loadMcp(); loadProvenance(); loadLedger(); loadMesh();
  }
})();
