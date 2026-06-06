/* SPDX-License-Identifier: Apache-2.0
 * © 2026 SZL Holdings — Rosie operator console — 13-tab vertical command surface.
 * Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).
 *
 * HONESTY OVER CHECKLIST. Every tab binds to a REAL same-origin endpoint verified
 * live on the rosie Space. No mocks, no synthetic rows. On fetch failure a panel
 * shows an honest error — never fake data. SLSA wording is rendered from the live
 * /version + /honest response, never hardcoded above what the backend reports.
 * Sign: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
 */
(function () {
  "use strict";
  var API = "/api/rosie/v1";
  var API2 = "/api/rosie/v2";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[<>&]/g, function (c) {
      return ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" })[c];
    });
  };
  var cut = function (s, n) { s = String(s == null ? "" : s); return s.length > n ? s.slice(0, n) : s; };
  function getJSON(path, base) {
    return fetch((base || API) + path, { headers: { "accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }
  function dot(id, ok) { var d = $(id); if (d) d.className = "dot " + (ok ? "ok" : "bad"); }
  function tdot(tab, ok) { var d = $("d_" + tab); if (d) d.className = "tdot2 " + (ok ? "ok" : "bad"); }
  function fail(el, dotId, what, e, tab) {
    if (dotId) dot(dotId, false);
    if (tab) tdot(tab, false);
    if (el) el.innerHTML = '<div class="err">' + esc(what) + " unreachable — " +
      esc(e && (e.message || e)) + "<br>(no synthetic fallback; panel stays honest)</div>";
  }
  function metric(el, big, sub) {
    if (el) el.innerHTML = '<div class="metric">' + esc(big) + '</div><div class="metric-sub">' + esc(sub) + '</div>';
  }

  /* ───────── theme toggle (default dark, persisted) ───────── */
  (function theme() {
    var root = document.documentElement, btn = $("themeToggle");
    var saved = localStorage.getItem("rosie-theme");
    if (saved) root.setAttribute("data-theme", saved);
    if (btn) btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("rosie-theme", next);
    });
  })();

  /* ═════════════ header strip (hydrated once, all REAL) ═════════════ */
  function hydrateHeader() {
    getJSON("/llm/tiers").then(function (d) {
      var t = $("chRouter"); if (t) t.innerHTML = "router <b>" + esc(d.default || (d.tiers && d.tiers[0] && d.tiers[0].id) || "—") + "</b>";
    }).catch(function () {});
    getJSON("/skills").then(function (d) {
      var s = $("chSkills"); if (s) s.innerHTML = "skills <b>" + esc(d.count != null ? d.count : (d.skills || []).length) + "</b>";
    }).catch(function () {});
    getJSON("/mcp/tools").then(function (d) {
      var m = $("chTools"); if (m) m.innerHTML = "MCP <b>" + esc(d.count != null ? d.count : (d.tools || []).length) + "</b>";
    }).catch(function () {});
    getJSON("/version").then(function (d) {
      var slsa = d.slsa || "L1 honest";
      var sl = $("slsaLine"); if (sl) sl.textContent = "SLSA " + slsa;
      var fs = $("footSlsa"); if (fs) fs.textContent = "SLSA " + slsa + " · doctrine " + (d.doctrine || "v11") + " · kernel " + (d.kernel_commit || "c7c0ba17");
    }).catch(function () {});
  }

  /* ═════════════ 1. SHARED FORUM (Directive 1 — ingest ALL substrate) ═════════════ */
  function loadForum() {
    getJSON("/khipu/aggregate").then(function (d) {
      tdot("forum", true); dot("forumDot", true);
      metric($("forumDepth"), (d.node_count != null ? d.node_count : (d.nodes || []).length), "forum nodes (DAG)");
      metric($("forumOrgans"), (d.organs_live != null ? d.organs_live : "—") + "/" + (d.organs_total != null ? d.organs_total : "—"), "organ ledgers live");
      metric($("forumNodes"), (d.node_count != null ? d.node_count : (d.nodes || []).length), "receipt nodes");
      metric($("forumEdges"), (d.edge_count != null ? d.edge_count : (d.edges || []).length), "hash-chain edges");
      var organs = d.organs || [];
      $("forumOrganList").innerHTML = organs.length
        ? '<table><thead><tr><th>organ</th><th>status</th><th>nodes</th></tr></thead><tbody>' +
          organs.map(function (o) {
            var live = String(o.status || "").toUpperCase() === "LIVE";
            return '<tr><td class="rid">' + esc(o.organ) + '</td><td><span class="tag ' +
              (live ? "proven" : "axiom") + '">' + esc(o.status || "?") + '</span></td><td>' +
              esc(o.count != null ? o.count : (o.nodes || []).length) + '</td></tr>';
          }).join("") + '</tbody></table>' +
          '<div class="metric-sub" style="margin-top:10px">' + esc(d.honesty || "shared a11oy receipt substrate — live fan-out") + '</div>'
        : '<div class="metric-sub">no organ ledgers reporting yet (honest)</div>';
    }).catch(function (e) { fail($("forumOrganList"), "forumDot", "Khipu aggregate", e, "forum"); });
    getJSON("/ledger").then(function (d) {
      dot("forumLedDot", true);
      var rows = (d.receipts || []).slice(-8).reverse();
      $("forumLedger").innerHTML = rows.length
        ? '<table><thead><tr><th>seq</th><th>receipt</th><th>action</th><th>utc</th></tr></thead><tbody>' +
          rows.map(function (r) {
            return '<tr><td>' + esc(r.seq) + '</td><td class="rid">' + esc(cut(r.receipt_id || "", 12)) +
              '</td><td class="act">' + esc(r.action || "?") + '</td><td>' + esc((r.timestamp_utc || "").substr(11, 8)) + '</td></tr>';
          }).join("") + '</tbody></table>' +
          '<div class="metric-sub" style="margin-top:10px">chain depth ' + esc(d.total != null ? d.total : rows.length) +
          ' · root ' + esc(cut(d.root_hash || "∅", 16)) + '…</div>'
        : '<div class="metric-sub">ledger empty — root ' + esc(cut(d.root_hash || "∅", 12)) + ' (honest)</div>';
    }).catch(function (e) { fail($("forumLedger"), "forumLedDot", "Khipu ledger", e); });
  }

  /* ═════════════ 2. INCIDENT COMMAND (derived from live health) ═════════════ */
  function loadIncident() {
    getJSON("/mesh/3d").then(function (d) {
      tdot("incident", true); dot("incDot", true);
      var nodes = d.nodes || [];
      var down = nodes.filter(function (n) { return n.ok !== true; });
      var healthy = nodes.length - down.length;
      var permitted = d.quorum_permitted === true;
      var open = down.length + (permitted ? 0 : 1);
      metric($("incOpen"), open, open ? "open incident(s)" : "all clear");
      metric($("incHealthy"), healthy + "/" + nodes.length, "organs HTTP 200");
      metric($("incQuorum"), permitted ? "PERMITTED" : "DENIED", (d.bft_bound || "n≥3f+1") + " · " + (d.healthy_witnesses != null ? d.healthy_witnesses : "?") + "/" + (d.n_required != null ? d.n_required : 4));
      metric($("incMesh"), open ? "DEGRADED" : "HEALTHY", "live mesh status");
      var rows = down.map(function (n) {
        return '<div class="incident"><span class="sev crit">CRIT</span>' +
          '<div><div class="iname">' + esc(n.id) + ' organ down</div>' +
          '<div class="imeta">/healthz returned ' + esc(String(n.http != null ? n.http : "—")) + ' · role ' + esc(n.role || "?") + '</div></div>' +
          '<div class="iright">escalated · auto-derived<br>tp ' + esc(cut((n.traceparent || "").split("-")[1] || "", 12)) + '</div></div>';
      });
      if (!permitted) {
        rows.unshift('<div class="incident"><span class="sev crit">CRIT</span>' +
          '<div><div class="iname">Khipu quorum DENIED</div>' +
          '<div class="imeta">' + esc(d.healthy_witnesses != null ? d.healthy_witnesses : "?") + '/' + esc(d.n_required != null ? d.n_required : 4) + ' witnesses — below 3-of-4 BFT bound</div></div>' +
          '<div class="iright">consensus halt</div></div>');
      }
      $("incBoard").innerHTML = rows.length ? rows.join("") :
        '<div class="incident"><span class="sev ok">OK</span><div><div class="iname">No open incidents</div>' +
        '<div class="imeta">all ' + nodes.length + ' organs HTTP 200 · quorum permitted</div></div>' +
        '<div class="iright">mesh nominal</div></div>';
    }).catch(function (e) { fail($("incBoard"), "incDot", "Mesh state", e, "incident"); });
  }

  /* ═════════════ 3. QUORUM / CONSENSUS (3-of-4 BFT) ═════════════ */
  function loadQuorum() {
    getJSON("/mesh/3d").then(function (d) {
      tdot("quorum", d.quorum_permitted === true);
      var permitted = d.quorum_permitted === true;
      var healthy = d.healthy_witnesses != null ? d.healthy_witnesses : 0;
      var nReq = d.n_required != null ? d.n_required : 4;
      var bft = d.bft_bound || "n≥3f+1";
      var nodes = d.nodes || [];
      var witnessTags = nodes.filter(function (n) { return n.id !== "rosie"; }).map(function (n) {
        return '<span class="witness ' + (n.ok ? "ok" : "down") + '">' + esc(n.id) + ' <b>' + esc(String(n.http || 0)) + '</b></span>';
      }).join("");
      dot("quorumDot", permitted);
      $("quorumBody").innerHTML =
        '<div class="quorum-val">' + healthy + '<span style="font-size:22px;color:var(--text-dim)">/' + nReq + '</span></div>' +
        '<div class="quorum-sub">' + esc(bft) + ' · need 3-of-' + nReq + ' healthy witnesses (f=1)</div>' +
        '<span class="quorum-chip ' + (permitted ? "permitted" : "denied") + '">' +
        (permitted ? "QUORUM PERMITTED ✓" : "QUORUM DENIED ✗") + '</span>' +
        '<div class="quorum-witnesses">' + witnessTags + '</div>';
      var chain = d.chain || [];
      $("quorumChain").innerHTML = chain.length
        ? '<div class="metric-sub">consensus chain depth <b style="color:var(--gold)">' + chain.length + '</b></div>' +
          '<table style="margin-top:8px"><thead><tr><th>#</th><th>hash</th></tr></thead><tbody>' +
          chain.slice(-6).map(function (c, i) {
            var h = typeof c === "string" ? c : (c.hash || c.id || JSON.stringify(c));
            return '<tr><td>' + (chain.length - Math.min(6, chain.length) + i) + '</td><td class="rid">' + esc(cut(h, 24)) + '…</td></tr>';
          }).join("") + '</tbody></table>'
        : '<div class="metric-sub">chain depth ' + (d.chain ? d.chain.length : 0) + ' · ' + esc(d.lambda_status || "Conjecture 1") + '</div>';
    }).catch(function (e) {
      fail($("quorumBody"), "quorumDot", "Khipu quorum", e, "quorum");
      var qc = $("quorumChain"); if (qc) qc.innerHTML = '<div class="err">chain unreachable</div>';
    });
  }

  /* ═════════════ 4. POLICY GATES ═════════════ */
  var polGates = [];
  function statusClass(s) {
    s = String(s || "").toUpperCase();
    if (s.indexOf("PROVEN") >= 0) return "proven";
    if (s.indexOf("SORRY") >= 0) return "sorry";
    if (s.indexOf("AXIOM") >= 0) return "axiom";
    return "policy";
  }
  function renderPolTable() {
    var q = (($("polSearch") && $("polSearch").value) || "").toLowerCase();
    var rows = polGates.filter(function (g) {
      if (!q) return true;
      return (esc(g.name) + " " + (g.lean_theorem || "") + " " + (g.status || "")).toLowerCase().indexOf(q) >= 0;
    });
    $("polTable").innerHTML = rows.length
      ? '<table><thead><tr><th>gate</th><th>Lean theorem</th><th>status</th></tr></thead><tbody>' +
        rows.map(function (g) {
          return '<tr><td class="rid">' + esc(g.name) + '</td><td>' + esc(g.lean_theorem || "—") +
            '</td><td><span class="tag ' + statusClass(g.status) + '">' + esc(g.status || "?") + '</span></td></tr>';
        }).join("") + '</tbody></table>'
      : '<div class="metric-sub">no gates match “' + esc(q) + '”</div>';
  }
  function loadPolicy() {
    getJSON("/policy/gates").then(function (d) {
      tdot("policy", true); dot("polDot", true);
      polGates = d.gates || [];
      var by = function (k) { return polGates.filter(function (g) { return statusClass(g.status) === k; }).length; };
      metric($("polTotal"), d.count != null ? d.count : polGates.length, "policy gates · doctrine " + (d.doctrine || "v11"));
      metric($("polProven"), by("proven"), "Lean PROVEN");
      metric($("polSorry"), by("sorry"), "sorry-tracked");
      metric($("polOther"), by("axiom") + by("policy"), "axiom / policy");
      renderPolTable();
    }).catch(function (e) { fail($("polTable"), "polDot", "Policy gates", e, "policy"); });
  }

  /* ═════════════ 5. ORGAN FLEET MAP ═════════════ */
  function loadFleet() {
    getJSON("/mesh/3d").then(function (d) {
      tdot("fleet", true);
      (d.nodes || []).forEach(function (n) {
        var card = document.querySelector('.organ[data-organ="' + n.id + '"]');
        if (!card) return;
        var up = n.ok === true;
        card.classList.remove("up", "down"); card.classList.add(up ? "up" : "down");
        var http = (n.http != null ? n.http : "—");
        var hzClass = (String(http).charAt(0) === "2") ? "g" : "r";
        var tp = (n.traceparent || "").split("-")[1] || (n.traceparent || "");
        var hdr = card.querySelector(".oh") ? card.querySelector(".oh").outerHTML :
          '<div class="oh"><span class="odot"></span><span class="oname">' + esc(n.id) + '</span><span class="orole">' + esc(n.role || "") + '</span></div>';
        card.innerHTML = hdr +
          '<div class="orow"><span>/healthz</span><span class="hz ' + hzClass + '">' + esc(String(http)) + (up ? " ok" : " down") + '</span></div>' +
          '<div class="orow"><span>Λ status</span><span class="ok">' + esc(String(n.lambda || "Conjecture 1")) + '</span></div>' +
          '<div class="orow"><span>MCP tools</span><span class="ok">' + esc(String(n.mcp_tools != null ? n.mcp_tools : "—")) + '</span></div>' +
          '<div class="otp">trace <b>' + esc(cut(String(tp), 16)) + '</b></div>';
      });
      updateTraceBadge(d);
    }).catch(function (e) {
      document.querySelectorAll(".organ").forEach(function (card) {
        var oh = card.querySelector(".oh");
        var hdr = oh ? oh.outerHTML : "";
        card.innerHTML = hdr + '<div class="err">mesh/3d unreachable — ' + esc(e && (e.message || e)) + '</div>';
      });
      tdot("fleet", false);
    });
  }
  function updateTraceBadge(d) {
    var nodes = d.nodes || [];
    for (var i = nodes.length - 1; i >= 0; i--) {
      if (nodes[i].traceparent) {
        var badge = $("traceBadge"); if (badge) badge.classList.add("live");
        var tid = $("traceId"); if (tid) tid.textContent = cut((nodes[i].traceparent.split("-")[1] || nodes[i].traceparent), 12) || "—";
        return;
      }
    }
  }

  /* ═════════════ 6. Λ-GATE MONITOR ═════════════ */
  function loadLambda() {
    getJSON("/lambda").then(function (d) {
      tdot("lambda", d.pass === true); dot("lamDot", d.pass === true);
      var L = Number(d.lambda), floor = Number(d.lambda_floor);
      var pass = d.pass === true;
      var axes = (d.axes || []).map(function (a) {
        var low = Number(a.score) < floor;
        return '<span class="axis' + (low ? " low" : "") + '">' + esc(a.name) + ' <b>' + Number(a.score).toFixed(2) + '</b></span>';
      }).join("");
      $("lambdaBody").innerHTML =
        '<div class="lambda-val">' + (isFinite(L) ? L.toFixed(5) : "—") + '</div>' +
        '<div class="lambda-meta">floor ' + (isFinite(floor) ? floor.toFixed(2) : "—") +
        ' · ' + (d.trust_axes || (d.axes || []).length) + ' trust axes · ' + esc(d.uniqueness || "Conjecture 1 — NOT a Theorem") + '</div>' +
        '<span class="verdict-chip ' + (pass ? "pass" : "fail") + '">' + (pass ? "PASS ✓" : "FAIL ✗") + '</span>' +
        '<div class="axes">' + axes + '</div>';
    }).catch(function (e) { fail($("lambdaBody"), "lamDot", "Λ verdict", e, "lambda"); });
    getJSON("/doctrine-guard").then(function (d) {
      dot("guardDot", d.caught === true);
      var raw = d.raw || {}, clamped = d.doctrine_dinn_clamped || {};
      $("guardBody").innerHTML =
        '<div class="kv"><span class="kk">adversarial prompt</span><span class="vv">' + esc(cut(d.prompt || "—", 60)) + '</span></div>' +
        '<div class="kv"><span class="kk">caught</span><span class="vv">' + (d.caught ? "YES ✓" : "no") + '</span></div>' +
        '<div class="kv"><span class="kk">verdict</span><span class="vv">' + esc(cut(d.verdict || "—", 70)) + '</span></div>' +
        '<div class="kv"><span class="kk">raw min-axis</span><span class="vv">' + esc(String(raw.min_axis != null ? raw.min_axis : "—")) + '</span></div>' +
        '<div class="kv"><span class="kk">clamped min-axis</span><span class="vv">' + esc(String(clamped.min_axis != null ? clamped.min_axis : "—")) + '</span></div>' +
        '<div class="kv"><span class="kk">Λ floor</span><span class="vv">' + esc(String(d.lambda_floor != null ? d.lambda_floor : "0.90")) + '</span></div>' +
        '<div class="metric-sub" style="margin-top:8px">' + esc(d.honesty || "doctrine-guard clamps adversarial prompts to the Λ floor") + '</div>';
    }).catch(function (e) { fail($("guardBody"), "guardDot", "Doctrine guard", e); });
  }

  /* ═════════════ 7. AUDIT LOG SEARCH ═════════════ */
  var audEntries = [], audMeta = {};
  function renderAud() {
    var q = (($("audSearch") && $("audSearch").value) || "").toLowerCase();
    var rows = audEntries.filter(function (en) {
      if (!q) return true;
      return JSON.stringify(en).toLowerCase().indexOf(q) >= 0;
    });
    if (!audEntries.length) {
      $("audTable").innerHTML = '<div class="metric-sub">' + esc(audMeta.note || "ring buffer empty — no audit entries buffered yet (honest; resets on Space rebuild)") + '</div>';
      return;
    }
    $("audTable").innerHTML = rows.length
      ? '<table><thead><tr><th>ts</th><th>action</th><th>detail</th></tr></thead><tbody>' +
        rows.slice().reverse().map(function (en) {
          return '<tr><td>' + esc(cut(en.ts || en.timestamp || en.timestamp_utc || "", 19)) +
            '</td><td class="act">' + esc(en.action || en.event || en.kind || "?") +
            '</td><td>' + esc(cut(en.detail || en.message || JSON.stringify(en), 80)) + '</td></tr>';
        }).join("") + '</tbody></table>'
      : '<div class="metric-sub">no entries match “' + esc(q) + '”</div>';
  }
  function loadAudit() {
    getJSON("/audit-log").then(function (d) {
      tdot("audit", true); dot("audDot", true);
      audEntries = d.entries || [];
      audMeta = d;
      var c = $("audCount"); if (c) c.textContent = (d.total_buffered != null ? d.total_buffered : audEntries.length) + " buffered";
      renderAud();
    }).catch(function (e) { fail($("audTable"), "audDot", "Audit log", e, "audit"); });
  }

  /* ═════════════ 8. COMMAND REPLAY (hash-chained) ═════════════ */
  function loadCommand() {
    getJSON("/command-log", API2).then(function (d) {
      tdot("command", d.chain_verified === true); dot("cmdDot", d.chain_verified === true);
      metric($("cmdDepth"), d.depth != null ? d.depth : (d.count != null ? d.count : (d.receipts || []).length), "commands in chain");
      metric($("cmdVerified"), d.chain_verified ? "VERIFIED ✓" : "BROKEN ✗", "SHA-256 prev→hash continuity");
      var gen = $("cmdGenesis"); if (gen) gen.innerHTML = '<div class="rid" style="font:600 12px var(--mono);word-break:break-all">' + esc(cut(d.genesis_hash || "∅", 32)) + '…</div><div class="metric-sub">genesis</div>';
      var hd = $("cmdHead"); if (hd) hd.innerHTML = '<div class="rid" style="font:600 12px var(--mono);word-break:break-all">' + esc(cut(d.final_hash || d.head_hash || "∅", 32)) + '…</div><div class="metric-sub">head</div>';
      var rows = (d.receipts || []).slice(-12).reverse();
      $("cmdTable").innerHTML = rows.length
        ? '<table><thead><tr><th>seq</th><th>kind</th><th>command</th><th>caller</th><th>gate</th><th>prev→hash</th></tr></thead><tbody>' +
          rows.map(function (r) {
            return '<tr><td>' + esc(r.seq) + '</td><td class="act">' + esc(r.kind || "?") +
              '</td><td>' + esc(cut(r.command || "—", 40)) + '</td><td>' + esc(r.caller || "—") +
              '</td><td><span class="tag ' + (r.gate_pass ? "proven" : "axiom") + '">' + (r.gate_pass ? "pass" : "—") + '</span></td>' +
              '<td class="rid">' + esc(cut(r.prev_hash || "", 8)) + '→' + esc(cut(r.hash || "", 8)) + '</td></tr>';
          }).join("") + '</tbody></table>'
        : '<div class="metric-sub">no commands logged yet (honest; chain genesis ' + esc(cut(d.genesis_hash || "∅", 12)) + ')</div>';
    }).catch(function (e) { fail($("cmdTable"), "cmdDot", "Command log", e, "command"); });
  }

  /* ═════════════ 9. PROVENANCE / ATTESTATION ═════════════ */
  function loadProv() {
    getJSON("/version").then(function (d) {
      tdot("prov", true); dot("provDot", true);
      var rel = d.release_url || ("https://github.com/szl-holdings/rosie/releases/tag/v" + (d.version || "1.0.0"));
      var verify = (d.verify && d.verify.cosign) || "cosign verify ghcr.io/szl-holdings/rosie --certificate-identity-regexp=szl-holdings";
      var sbom = d.verify && d.verify.sbom;
      $("provBody").innerHTML =
        '<a href="' + esc(rel) + '" target="_blank" rel="noopener">⬡ release v' + esc(d.version || "1.0.0") + '</a>' +
        (sbom ? '<a href="' + esc(sbom) + '" target="_blank" rel="noopener">⬡ SBOM (CycloneDX)</a>' : "") +
        '<a href="https://github.com/szl-holdings/.github/blob/main/cosign.pub" target="_blank" rel="noopener">⬡ cosign.pub</a>' +
        '<div class="k">git ' + esc(cut(d.git_sha || "?", 8)) + ' · hf ' + esc(cut(d.hf_space_sha || "?", 8)) +
        ' · kernel ' + esc(d.kernel_commit || "c7c0ba17") + '</div>' +
        '<div class="k">SLSA: ' + esc(d.slsa || "L1 honest") + '</div>' +
        '<div class="k" style="color:var(--text-dim)">cosign verify:<br><code>' + esc(verify) + '</code></div>';
    }).catch(function (e) { fail($("provBody"), "provDot", "Provenance", e, "prov"); });
    getJSON("/honest").then(function (d) {
      dot("honDot", true);
      var L = d.doctrine_lock || {};
      $("honBody").innerHTML =
        '<div class="kv"><span class="kk">doctrine</span><span class="vv">' + esc(L.doctrine || "v11") + ' ' + esc(L.state || "LOCKED") + '</span></div>' +
        '<div class="kv"><span class="kk">declarations</span><span class="vv">' + esc(String(L.declarations != null ? L.declarations : "749")) + '</span></div>' +
        '<div class="kv"><span class="kk">axioms</span><span class="vv">' + esc(String(L.axioms != null ? L.axioms : "14")) + '</span></div>' +
        '<div class="kv"><span class="kk">sorries</span><span class="vv">' + esc(String(L.sorries != null ? L.sorries : "163")) + '</span></div>' +
        '<div class="kv"><span class="kk">kernel commit</span><span class="vv">' + esc(L.commit || "c7c0ba17") + '</span></div>' +
        '<div class="kv"><span class="kk">Λ</span><span class="vv">' + esc(L.lambda || "Conjecture 1") + '</span></div>' +
        '<div class="metric-sub" style="margin-top:8px">' + esc(d.footer || "HONESTY OVER CHECKLIST") + '</div>';
    }).catch(function (e) { fail($("honBody"), "honDot", "Honest disclosure", e); });
  }

  /* ═════════════ 10. MCP TOOL CONSOLE ═════════════ */
  function loadMcp() {
    getJSON("/mcp/tools").then(function (d) {
      tdot("mcp", true); dot("mcpDot", true);
      var tools = (d.tools || []).map(function (t) { return typeof t === "string" ? t : (t.name || "?"); });
      $("mcpBody").innerHTML =
        '<div class="metric">' + (d.count != null ? d.count : tools.length) + '</div>' +
        '<div class="metric-sub">governed MCP tools · doctrine ' + esc(d.doctrine || "v11") + '</div>' +
        '<div class="toolset">' + tools.map(function (n) { return '<span class="tool">' + esc(n) + '</span>'; }).join("") + '</div>';
    }).catch(function (e) { fail($("mcpBody"), "mcpDot", "MCP tools", e, "mcp"); });
  }

  /* ═════════════ 11. DEPLOY / MESH STATUS ═════════════ */
  function loadDeploy() {
    getJSON("/deploy/status").then(function (d) {
      tdot("deploy", true); dot("depDot", true);
      var spaces = d.spaces || {};
      var keys = Object.keys(spaces);
      $("depTable").innerHTML = keys.length
        ? '<table><thead><tr><th>space</th><th>sha</th><th>sdk</th><th>health</th><th>last verified</th></tr></thead><tbody>' +
          keys.map(function (k) {
            var s = spaces[k] || {};
            var ok = s.healthy === true;
            return '<tr><td class="rid">' + esc(k) + '</td><td>' + esc(cut(s.sha || "—", 12)) +
              '</td><td>' + esc(s.sdk || "—") + '</td><td><span class="tag ' + (ok ? "proven" : "axiom") + '">' +
              (ok ? "healthy ✓" : "down ✗") + '</span></td><td>' + esc(cut(s.last_verified || "—", 19)) + '</td></tr>';
          }).join("") + '</tbody></table>'
        : '<div class="metric-sub">no spaces reported</div>';
    }).catch(function (e) { fail($("depTable"), "depDot", "Deploy status", e, "deploy"); });
  }

  /* ═════════════ 12. CORTEX (self-learning + active inference) ═════════════ */
  function loadCortex() {
    getJSON("/self-learning").then(function (d) {
      tdot("cortex", d.ok === true); dot("slDot", d.ok === true);
      $("slBody").innerHTML =
        '<div class="metric">' + esc(String(d.iterations != null ? d.iterations : 0)) + '</div>' +
        '<div class="metric-sub">learning iterations (reset on rebuild — honest)</div>' +
        '<div class="kv" style="margin-top:10px"><span class="kk">belief μ</span><span class="vv">' + esc(String(d.belief_mu != null ? d.belief_mu : "—")) + '</span></div>' +
        '<div class="kv"><span class="kk">precision</span><span class="vv">' + esc(String(d.precision != null ? d.precision : "—")) + '</span></div>' +
        '<div class="kv"><span class="kk">trend</span><span class="vv">' + esc(String(d.trend != null ? d.trend : "—")) + '</span></div>' +
        (d.note ? '<div class="metric-sub" style="margin-top:8px">' + esc(d.note) + '</div>' : "");
    }).catch(function (e) { fail($("slBody"), "slDot", "Self-learning", e, "cortex"); });
    getJSON("/active-inference").then(function (d) {
      dot("aiDot", d.ok === true);
      $("aiBody").innerHTML =
        '<div class="metric">' + esc(String(d.free_energy != null ? d.free_energy : "—")) + '</div>' +
        '<div class="metric-sub">variational free energy</div>' +
        '<div class="kv" style="margin-top:10px"><span class="kk">belief μ</span><span class="vv">' + esc(String(d.belief_mu != null ? d.belief_mu : "—")) + '</span></div>' +
        '<div class="kv"><span class="kk">precision</span><span class="vv">' + esc(String(d.precision != null ? d.precision : "—")) + '</span></div>' +
        '<div class="kv"><span class="kk">steps</span><span class="vv">' + esc(String(d.steps != null ? d.steps : "—")) + '</span></div>' +
        (d.note ? '<div class="metric-sub" style="margin-top:8px">' + esc(d.note) + '</div>' : "");
    }).catch(function (e) { fail($("aiBody"), "aiDot", "Active inference", e); });
  }

  /* ═════════════ 13. LIVE MCP STREAM (WebSocket) ═════════════ */
  var ws = null, wsConnected = false, wsBooted = false;
  function streamLine(tag, body, cls) {
    var box = $("mcpStream"); if (!box) return;
    if (box.querySelector(".metric-sub")) box.innerHTML = "";
    var row = document.createElement("div"); row.className = "sline";
    row.innerHTML = '<span class="stag ' + (cls || "") + '">' + esc(tag) + '</span><span class="sbody">' + esc(body) + '</span>';
    box.appendChild(row); box.scrollTop = box.scrollHeight;
    while (box.children.length > 120) box.removeChild(box.firstChild);
  }
  function connectStream() {
    if (wsBooted && wsConnected) return;
    wsBooted = true;
    try {
      var proto = location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(proto + "//" + location.host + API + "/mcp/stream");
    } catch (e) { streamLine("error", "cannot open WebSocket: " + (e.message || e), "hop"); return; }
    ws.onopen = function () {
      wsConnected = true;
      var s = $("wsStat"); if (s) s.classList.add("on");
      dot("streamDot", true); tdot("stream", true);
      streamLine("open", "live MCP WebSocket connected — real per-hop receipts", "span");
    };
    ws.onmessage = function (ev) {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.type === "span") streamLine("span", (m.name || "") + " · tp " + cut((m.traceparent || "").split("-")[1] || "", 12), "span");
      else if (m.type === "hop") {
        var r = m.receipt || {};
        streamLine("hop", (r.organ || r.tool || "hop") + " → " + (r.verdict || r.status || r.action || "ok") + (r.lambda != null ? (" · Λ " + r.lambda) : ""), "hop");
      } else if (m.type === "summary") {
        var su = m.summary || {};
        streamLine("summary", (su.verdict || "done") + " · " + ((su.receipts || []).length) + " receipts · " + (su.doctrine || "v11"), "sum");
      }
    };
    ws.onclose = function () {
      wsConnected = false;
      var s = $("wsStat"); if (s) s.classList.remove("on");
      dot("streamDot", false); tdot("stream", false);
      streamLine("closed", "stream closed — reconnecting in 4s", "hop");
      setTimeout(function () { wsBooted = false; connectStream(); }, 4000);
    };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }
  function runChain() {
    var goal = ($("streamGoal") && $("streamGoal").value) || "ship doctrine-v11 receipt";
    if (ws && wsConnected) { streamLine("run", "goal: " + goal, "span"); ws.send(JSON.stringify({ op: "run", goal: goal })); }
    else { streamLine("error", "stream not connected yet — open this tab to connect", "hop"); connectStream(); }
  }

  /* ═════════════ Setup MCP modal (REAL example configs) ═════════════ */
  var mcpConfigs = null, activeHost = "claude-desktop";
  function openMcp() {
    var modal = $("mcpModal"); if (!modal) return;
    modal.classList.add("open");
    if (mcpConfigs) { renderMcpModal(); return; }
    getJSON("/mcp/configs").then(function (d) {
      mcpConfigs = (d && d.configs) || {};
      renderMcpModal();
    }).catch(function (e) { $("mcpConfig").textContent = "could not load configs: " + (e.message || e); });
  }
  function renderMcpModal() {
    var cfg = mcpConfigs && mcpConfigs[activeHost];
    $("mcpConfig").textContent = cfg ? JSON.stringify(cfg, null, 2) : "config unavailable";
    document.querySelectorAll(".host-tab").forEach(function (t) {
      t.classList.toggle("active", t.getAttribute("data-host") === activeHost);
    });
  }
  function copyMcp() {
    var txt = $("mcpConfig").textContent || "";
    var done = function () { var c = $("mcpCopied"); if (c) { c.classList.add("show"); setTimeout(function () { c.classList.remove("show"); }, 1600); } };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, function () { fallbackCopy(txt); done(); });
    else { fallbackCopy(txt); done(); }
  }
  function fallbackCopy(txt) {
    var ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta);
    ta.select(); try { document.execCommand("copy"); } catch (e) {} document.body.removeChild(ta);
  }
  function wireMcpModal() {
    var b1 = $("setupMcpBtn"); if (b1) b1.addEventListener("click", openMcp);
    var b2 = $("setupMcpBtn2"); if (b2) b2.addEventListener("click", openMcp);
    var cl = $("mcpClose"); if (cl) cl.addEventListener("click", function () { $("mcpModal").classList.remove("open"); });
    var bg = $("mcpModal"); if (bg) bg.addEventListener("click", function (e) { if (e.target === bg) bg.classList.remove("open"); });
    document.querySelectorAll(".host-tab").forEach(function (t) {
      t.addEventListener("click", function () { activeHost = t.getAttribute("data-host"); renderMcpModal(); });
    });
    var cp = $("mcpCopy"); if (cp) cp.addEventListener("click", copyMcp);
  }

  /* ═════════════ TAB ROUTER ═════════════ */
  var TABS = ["forum", "incident", "quorum", "policy", "fleet", "lambda", "audit", "command", "prov", "mcp", "deploy", "cortex", "stream"];
  var LOADERS = {
    forum: loadForum, incident: loadIncident, quorum: loadQuorum, policy: loadPolicy,
    fleet: loadFleet, lambda: loadLambda, audit: loadAudit, command: loadCommand,
    prov: loadProv, mcp: loadMcp, deploy: loadDeploy, cortex: loadCortex, stream: connectStream
  };
  var loadedOnce = {};
  var current = "forum";

  function activate(tab) {
    if (TABS.indexOf(tab) < 0) return;
    current = tab;
    document.querySelectorAll(".pane").forEach(function (p) { p.classList.remove("active"); });
    var pane = $("pane-" + tab); if (pane) pane.classList.add("active");
    document.querySelectorAll(".tab").forEach(function (t) {
      t.classList.toggle("active", t.getAttribute("data-tab") === tab);
    });
    if (history.replaceState) { try { history.replaceState(null, "", "#" + tab); } catch (e) {} }
    var fn = LOADERS[tab];
    if (fn) {
      fn();
      loadedOnce[tab] = true;
    }
  }

  function wireTabs() {
    document.querySelectorAll(".tab").forEach(function (t) {
      t.addEventListener("click", function () { activate(t.getAttribute("data-tab")); });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { var m = $("mcpModal"); if (m) m.classList.remove("open"); return; }
      var tgt = e.target;
      if (tgt && (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA")) return;
      if (e.key >= "1" && e.key <= "9") { var idx = parseInt(e.key, 10) - 1; if (TABS[idx]) activate(TABS[idx]); }
      else if (e.key === "0") { activate(TABS[9]); }
      else if (e.key === "ArrowRight") { var i = TABS.indexOf(current); activate(TABS[(i + 1) % TABS.length]); }
      else if (e.key === "ArrowLeft") { var j = TABS.indexOf(current); activate(TABS[(j - 1 + TABS.length) % TABS.length]); }
    });
    // audit + policy local filters / refresh
    var ps = $("polSearch"); if (ps) ps.addEventListener("input", renderPolTable);
    var as = $("audSearch"); if (as) as.addEventListener("input", renderAud);
    var ar = $("audRefresh"); if (ar) ar.addEventListener("click", loadAudit);
    var sr = $("streamRun"); if (sr) sr.addEventListener("click", runChain);
  }

  /* ═════════════ boot + refresh active tab ═════════════ */
  function boot() {
    hydrateHeader();
    wireTabs();
    wireMcpModal();
    var hash = (location.hash || "").replace("#", "");
    activate(TABS.indexOf(hash) >= 0 ? hash : "forum");
    // refresh only the active tab every 10 s; trace badge tracks fleet/mesh
    setInterval(function () {
      var fn = LOADERS[current];
      if (fn && current !== "stream") fn();
      // keep trace badge warm even when not on a mesh tab
      if (["forum", "incident", "audit", "command", "prov", "policy"].indexOf(current) >= 0) {
        getJSON("/mesh/3d").then(updateTraceBadge).catch(function () {});
      }
    }, 10000);
  }
  document.addEventListener("DOMContentLoaded", boot);
  if (document.readyState !== "loading") { boot(); }
})();
