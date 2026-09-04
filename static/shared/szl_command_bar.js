/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * szl_command_bar.js — three-zone holographic command bar (KANCHAY).
 * Read-only probes. Never signs. Never fabricates metrics.
 * Λ = Conjecture 1 (advisory, gray). Locked-proven stays 8.
 */
(function (global) {
  'use strict';
  if (global.__szlCommandBarLoaded) return;
  global.__szlCommandBarLoaded = true;

  var PROOF = 'https://a11oy.net';
  var KERNEL = 'https://huggingface.co/SZLHOLDINGS/governed-inference-meter';
  var reduce = false;
  try {
    reduce = !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (e) {}
  try {
    var bootQ = location.search || '';
    if (/[?&]operator=1\b/.test(bootQ) || localStorage.getItem('szl.operator') === '1') {
      document.documentElement.setAttribute('data-operator', '1');
    }
    var bootView = null;
    try { bootView = new URLSearchParams(bootQ).get('view'); } catch (e2) {}
    if (!bootView && /[?&]investor=1\b/.test(bootQ)) bootView = 'investor';
    if (!bootView) bootView = (location.hash || '').replace(/^#/, '').split('/')[0];
    if (bootView) document.documentElement.setAttribute('data-view', bootView);
  } catch (e) {}

  var VERBS = [
    { label: 'Verify a receipt', href: '/verify' },
    { label: 'Open diligence room', href: PROOF },
    { label: 'Proof registry', href: PROOF },
    { label: 'Command Center', href: '/console?view=command' },
    { label: 'Holo', href: '/holographic' },
    { label: 'Frontier', href: '/frontier-now' },
    { label: 'Models + Kernels', href: '/estate' },
    { label: 'Ask & Act', href: '/console?view=ask' },
    { label: 'Investor View', href: '/console?view=investor' },
    { label: 'WILLAY — signed refusals', href: '/willay' },
    { label: 'Pull the kernel', href: KERNEL },
    { label: 'Persistent kernel', href: '', roadmap: true }
  ];

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'class') n.className = attrs[k];
        else if (k === 'text') n.textContent = attrs[k];
        else if (k === 'html') n.innerHTML = attrs[k];
        else if (k.slice(0, 2) === 'on' && typeof attrs[k] === 'function') n.addEventListener(k.slice(2), attrs[k]);
        else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
      });
    }
    (kids || []).forEach(function (c) {
      if (c == null) return;
      n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  }

  function fetchJson(url, ms) {
    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var t = ctrl ? setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, ms || 8000) : null;
    return fetch(url, { cache: 'no-store', signal: ctrl ? ctrl.signal : undefined }).then(function (r) {
      if (t) clearTimeout(t);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).catch(function (e) {
      if (t) clearTimeout(t);
      throw e;
    });
  }

  function setChip(node, live, text) {
    if (!node) return;
    node.classList.toggle('szl-chip--live', !!live);
    node.classList.toggle('szl-chip--off', !live);
    var lab = node.querySelector('[data-lab]');
    if (lab) lab.textContent = text;
  }

  function roll(node, next) {
    if (!node) return;
    var prev = node.getAttribute('data-v');
    node.textContent = next;
    node.setAttribute('data-v', String(next));
    if (!reduce && prev != null && prev !== String(next)) {
      node.classList.remove('is-tick');
      void node.offsetWidth;
      node.classList.add('is-tick');
    }
  }

  function mount(root) {
    if (!root || root.getAttribute('data-szl-mounted') === '1') return;
    root.setAttribute('data-szl-mounted', '1');
    root.classList.add('szl-hbar', 'topbar');

    var surface = root.getAttribute('data-surface') || 'Command Platform';
    var origin = (root.getAttribute('data-origin') || 'product').toLowerCase();
    var menu = root.querySelector('.menu-btn');

    var scope = el('div', { class: 'szl-hbar-zone szl-hbar-scope', 'aria-label': 'Scope' }, [
      el('div', { class: 'szl-hbar-crumb' }, [
        el('span', { text: 'SZL HOLDINGS' }),
        el('span', { class: 'sep', text: '/' }),
        el('span', { text: 'A11OY' }),
        el('span', { class: 'sep', text: '/' }),
        el('span', { class: 'now', text: surface })
      ])
    ]);

    var svc = el('span', { class: 'szl-chip szl-chip--off', id: 'runtime-status' }, [
      el('span', { class: 'szl-dot' }),
      el('span', { 'data-lab': '1', id: 'runtime-status-text', text: 'UNAVAILABLE' })
    ]);
    var lam = el('span', { class: 'szl-chip szl-chip--off szl-chip--lambda', title: 'Λ = Conjecture 1 — advisory, never a theorem, never a gate' }, [
      el('span', { text: 'Λ' }),
      el('span', { 'data-lab': '1', text: 'CONJECTURE 1' })
    ]);
    var chain = el('span', { class: 'szl-chip szl-chip--off' }, [
      el('span', { text: 'CHAIN' }),
      el('span', { class: 'szl-roll', 'data-lab': '1', 'data-roll': '1', text: '—' })
    ]);
    var age = el('span', { class: 'szl-chip szl-chip--off' }, [
      el('span', { text: 'RECEIPT' }),
      el('span', { 'data-lab': '1', text: 'UNAVAILABLE' })
    ]);
    var kern = el('span', {
      class: 'szl-chip szl-chip--off',
      title: 'Lean locked theorems from /api/a11oy/v1/honest locked_formula_count. Genome LOCKED-PROVEN is catalog, never this chip.'
    }, [
      el('span', { text: 'LOCKED-8' }),
      el('span', { 'data-lab': '1', text: 'UNAVAILABLE' })
    ]);
    var live = el('div', { class: 'szl-hbar-zone szl-hbar-live', 'aria-label': 'Live cluster' }, [svc, lam, kern, chain, age]);

    var product = el('a', {
      class: 'szl-origin' + (origin === 'product' ? ' is-on' : ''),
      href: '/console',
      'aria-label': 'Open the command center',
      text: 'Command'
    });
    var proof = el('a', {
      class: 'szl-origin szl-proof' + (origin === 'proof' ? ' is-on' : ''),
      href: PROOF,
      target: '_blank',
      rel: 'noopener noreferrer',
      text: 'Proof registry ↗'
    });
    var investor = el('button', {
      class: 'szl-origin',
      type: 'button',
      id: 'inv-toggle',
      text: 'Investor view',
      onclick: function () {
        if (typeof global.go === 'function') global.go('investor');
        else location.href = '/console?view=investor';
      }
    });
    var cmdkBtn = el('button', { class: 'szl-cmdk', type: 'button', title: 'Command palette', text: '⌘K' });
    var opBtn = el('button', { class: 'szl-op-toggle', type: 'button', text: 'Operator' });
    var moreBtn = el('button', { class: 'szl-more', type: 'button', text: 'More' });
    var moreMenu = el('div', { class: 'szl-overflow-menu', role: 'menu' });
    var overflow = el('div', { class: 'szl-overflow' }, [moreBtn, moreMenu]);

    var estate = el('nav', { class: 'szl-estate extlinks', 'aria-label': 'Estate switcher' }, [
      el('a', { class: 'flag', href: '/console', text: 'A11OY' }),
      el('a', { class: 'flag', href: 'https://huggingface.co/spaces/szlholdings/killinchu', target: '_blank', rel: 'noopener noreferrer', text: 'KILLINCHU' }),
      el('a', { class: 'flag', href: '/anatomy-v5', text: 'ANATOMY' })
    ]);

    var holo = el('a', {
      class: 'szl-origin',
      href: '/holographic',
      text: 'Holo'
    });
    var frontier = el('a', {
      class: 'szl-origin',
      href: '/frontier-now',
      text: 'Frontier'
    });
    var origins = el('div', { class: 'szl-origins' }, [product, holo, frontier, proof]);
    var sw = el('div', { class: 'szl-hbar-zone szl-hbar-switch', 'aria-label': 'Surface switcher' }, [
      origins, investor, cmdkBtn, opBtn, estate, overflow
    ]);

    root.textContent = '';
    if (menu) root.appendChild(menu);
    root.appendChild(scope);
    root.appendChild(live);
    root.appendChild(sw);

    opBtn.addEventListener('click', function () {
      var on = document.documentElement.getAttribute('data-operator') === '1';
      if (on) document.documentElement.removeAttribute('data-operator');
      else document.documentElement.setAttribute('data-operator', '1');
      try { localStorage.setItem('szl.operator', on ? '0' : '1'); } catch (e) {}
    });
    try {
      if (localStorage.getItem('szl.operator') === '1') document.documentElement.setAttribute('data-operator', '1');
    } catch (e) {}

    moreBtn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      overflow.classList.toggle('open');
    });
    document.addEventListener('click', function () { overflow.classList.remove('open'); });

    function collectOverflow() {
      moreMenu.textContent = '';
      var extras = [
        { label: 'Holo', href: '/holographic' },
        { label: 'Frontier', href: '/frontier-now' },
        { label: 'Verify a receipt', href: '/verify' },
        { label: 'WILLAY', href: '/willay' },
        { label: 'Models + Kernels', href: '/estate' },
        { label: 'Ask & Act', href: '/console?view=ask' }
      ];
      extras.forEach(function (it) {
        moreMenu.appendChild(el('a', { href: it.href, role: 'menuitem', text: it.label }));
      });
    }
    collectOverflow();

    var lastHead = null;
    function probe() {
      var operator = document.documentElement.getAttribute('data-operator') === '1';
      Promise.all([
        fetchJson('/healthz', 6000).catch(function () { return null; }),
        fetchJson('/api/a11oy/v1/readiness/tab-matrix?view=summary', 6000).catch(function () { return null; }),
        fetchJson('/api/a11oy/v1/observability/summary', 6000).catch(function () { return null; }),
        fetchJson('/api/a11oy/v1/lambda', 6000).catch(function () { return null; }),
        fetchJson('/api/a11oy/v1/wow/ledger?limit=1', 6000).catch(function () { return null; }),
        fetchJson('/api/a11oy/v1/honest', 6000).catch(function () { return null; })
      ]).then(function (vals) {
        var health = vals[0], matrix = vals[1], summary = vals[2], lambda = vals[3], ledger = vals[4], honest = vals[5];
        if (health && (health.status === 'ok' || health.status === 'healthy')) {
          var label = 'ONLINE';
          if (operator && matrix && matrix.available === false) label = 'ONLINE · CONTRACT GAP';
          else if (operator && matrix && matrix.contract_version) label = 'ONLINE · CONTRACT ' + matrix.contract_version;
          setChip(svc, true, label);
          svc.classList.remove('szl-chip--deny');
        } else {
          setChip(svc, false, 'UNAVAILABLE');
        }

        if (lambda && typeof lambda.lambda === 'number') {
          setChip(lam, true, 'CONJECTURE 1 · ' + lambda.lambda.toFixed(3));
        } else {
          setChip(lam, false, 'CONJECTURE 1 · UNAVAILABLE');
        }
        lam.classList.add('szl-chip--lambda');

        var lockedN = honest && honest.locked_formula_count;
        if (lockedN === 8) setChip(kern, true, '8');
        else setChip(kern, false, 'UNAVAILABLE');

        var depth = (ledger && ledger.chain_depth != null) ? ledger.chain_depth
          : (summary && summary.dag_depth != null) ? summary.dag_depth : null;
        var rollEl = chain.querySelector('[data-roll]');
        if (depth != null) {
          setChip(chain, true, '');
          if (rollEl) {
            rollEl.removeAttribute('data-lab');
            roll(rollEl, String(depth));
          }
        } else {
          setChip(chain, false, 'UNAVAILABLE');
        }

        var recs = (ledger && (ledger.receipts || ledger.items)) || [];
        var rec = recs[0];
        if (rec) {
          var ts = rec.timestamp_utc || rec.ts || rec.t || rec.created_at;
          var ageLabel = 'SIGNED';
          if (rec.unsigned || rec.signer_state === 'UNSIGNED') ageLabel = 'UNSIGNED';
          else if (rec.hash || rec.prev_hash) ageLabel = 'HASH-LINKED';
          if (ts) {
            var then = Date.parse(ts);
            if (!isNaN(then)) {
              var sec = Math.max(0, Math.round((Date.now() - then) / 1000));
              ageLabel += sec < 60 ? (' · ' + sec + 's') : (' · ' + Math.round(sec / 60) + 'm');
            }
          }
          setChip(age, true, ageLabel);
          var head = rec.hash || rec.receipt_id || rec.id;
          if (head && head !== lastHead) {
            lastHead = head;
            if (!reduce) {
              root.classList.remove('szl-pulse');
              void root.offsetWidth;
              root.classList.add('szl-pulse');
            }
          }
        } else {
          setChip(age, false, 'UNAVAILABLE');
        }

        var deny = false;
        try {
          var g = document.getElementById('hero-gate');
          if (g && /DENY|BLOCKED/.test(g.textContent || '')) deny = true;
        } catch (e) {}
        if (deny) svc.classList.add('szl-chip--deny');
      }).catch(function () {
        setChip(svc, false, 'UNAVAILABLE');
        setChip(lam, false, 'CONJECTURE 1 · UNAVAILABLE');
        setChip(kern, false, 'UNAVAILABLE');
        setChip(chain, false, 'UNAVAILABLE');
        setChip(age, false, 'UNAVAILABLE');
      });
    }
    probe();
    setInterval(probe, 20000);

    cmdkBtn.addEventListener('click', openPalette);
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        openPalette();
      }
    });
  }

  var pal = null;
  function openPalette() {
    if (!pal) pal = buildPalette();
    pal.classList.add('open');
    var inp = pal.querySelector('input');
    if (inp) inp.focus();
  }
  function closePalette() { if (pal) pal.classList.remove('open'); }

  function buildPalette() {
    var ov = el('div', { class: 'szl-pal-ov', role: 'dialog', 'aria-label': 'Command palette' });
    var box = el('div', { class: 'szl-pal' });
    var inp = el('input', { type: 'search', placeholder: 'Verify a receipt, jump a surface…', 'aria-label': 'Command' });
    var list = el('div', { class: 'szl-pal-list' });
    function render(q) {
      list.textContent = '';
      var qq = (q || '').toLowerCase();
      VERBS.filter(function (v) { return !qq || v.label.toLowerCase().indexOf(qq) >= 0; }).forEach(function (v) {
        var item = el('div', { class: 'szl-pal-item' }, [
          el('span', { text: v.label }),
          v.roadmap ? el('span', { class: 'road', text: 'ROADMAP' }) : null
        ]);
        item.addEventListener('click', function () {
          if (v.roadmap) return;
          closePalette();
          if (v.href.indexOf('/console?view=') === 0 && typeof global.go === 'function') {
            global.go(v.href.split('view=')[1]);
          } else {
            location.href = v.href;
          }
        });
        list.appendChild(item);
      });
    }
    inp.addEventListener('input', function () { render(inp.value); });
    ov.addEventListener('click', function (e) { if (e.target === ov) closePalette(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePalette(); });
    box.appendChild(inp); box.appendChild(list); ov.appendChild(box);
    document.body.appendChild(ov);
    render('');
    return ov;
  }

  function mountAll() {
    document.querySelectorAll('[data-szl-command-bar]').forEach(mount);
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function chipClass(label) {
    var k = String(label || '').toUpperCase();
    if (k === 'REPORTED' || k === 'LIVE') return 'szl-holo-chip szl-holo-chip--reported';
    if (k === 'MEASURED') return 'szl-holo-chip szl-holo-chip--measured';
    if (k === 'SOFTWARE') return 'szl-holo-chip szl-holo-chip--software';
    if (k === 'ROADMAP') return 'szl-holo-chip szl-holo-chip--roadmap';
    if (k === 'UNAVAILABLE' || k === 'UNKNOWN') return 'szl-holo-chip szl-holo-chip--off';
    return 'szl-holo-chip';
  }

  function shortSha(sha) {
    var s = String(sha || '');
    return s.length === 40 ? (s.slice(0, 12) + '…') : (s || 'UNAVAILABLE');
  }

  function renderCard(card, compact) {
    var listing = (card && card.listing) || {};
    var arts = (card && card.artifacts) || {};
    var evals = (card && card.evals) || {};
    var pin = (card && card.revision_pin) || {};
    var gguf = arts.gguf_files || [];
    var relatedGguf = arts.related_gguf_files || [];
    var ggufNote = '';
    if (gguf.length) ggufNote = gguf.join(', ');
    else if (relatedGguf.length) ggufNote = (arts.related_gguf_repo || '') + ': ' + relatedGguf.join(', ');
    var lane = String((card && card.lane) || 'model').toUpperCase();
    var owner = card && card.owner ? String(card.owner) : lane;
    var github = card && card.github;
    var hubId = (card && card.hub_id) || 'UNAVAILABLE';
    var evidence = (card && card.evidence_class) || listing.label || 'UNAVAILABLE';
    var href = (card && (card.hub_href || card.act_href)) || '#';
    var act = (card && card.act_href) || href;
    var lambda = (card && card.lambda) || {};
    var notTriton = card && card.not_triton_stack;
    var notClaim = (card && card.not) || 'Not OPERATIONAL. Not Lean-8.';
    var filesLine = ggufNote
      ? ('GGUF ' + ggufNote)
      : (arts.has_adapter ? 'adapter file REPORTED' : (arts.weight_bearing ? 'weight filenames REPORTED' : 'no weight file'));
    if (lane === 'KERNEL') filesLine = arts.file_count ? ('kernel files REPORTED · n=' + arts.file_count) : filesLine;
    var html = '<article class="szl-holo-card" data-lane="' + esc(lane.toLowerCase()) + '" data-id="' + esc(card && card.id) + '" data-hub="' + esc(hubId) + '" data-evidence="' + esc(evidence) + '">'
      + '<header class="szl-holo-card-h">'
      + '<span class="szl-holo-k">' + esc(owner) + (notTriton ? ' · NOT TRITON STACK' : '') + '</span>'
      + '<h3 class="szl-holo-title">' + esc(card && card.title) + '</h3>'
      + '<p class="szl-holo-one">' + esc(card && card.one_line) + '</p>'
      + '</header>'
      + '<dl class="szl-holo-facts">'
      + '<div><dt>Hub id</dt><dd><code class="szl-holo-id">' + esc(hubId) + '</code></dd></div>'
      + '<div><dt>GitHub</dt><dd>' + (github
        ? ('<a href="' + esc(github) + '" target="_blank" rel="noopener noreferrer">' + esc(github.replace(/^https:\/\/github.com\//, '')) + '</a>')
        : '<span class="' + chipClass('UNAVAILABLE') + '">UNAVAILABLE</span> no public source repo') + '</dd></div>'
      + '<div><dt>Class</dt><dd><span class="' + chipClass(evidence) + '">' + esc(evidence) + '</span></dd></div>'
      + '<div><dt>Revision</dt><dd><span class="' + chipClass(pin.label) + '">' + esc(pin.label || 'UNAVAILABLE') + '</span> '
      + '<code class="szl-holo-id">' + esc(shortSha(pin.sha)) + '</code></dd></div>'
      + '<div><dt>See</dt><dd><span class="' + chipClass(listing.label) + '">' + esc(listing.label || 'UNAVAILABLE') + '</span> '
      + esc(listing.pipeline_tag || listing.sdk || listing.note || 'Hub listing') + '</dd></div>'
      + '<div><dt>Decide</dt><dd><span class="' + chipClass(arts.label) + '">' + esc(arts.label || 'UNAVAILABLE') + '</span> '
      + esc(filesLine) + '</dd></div>'
      + '<div><dt>Not</dt><dd>' + esc(notClaim) + '</dd></div>'
      + (compact ? '' : ('<div><dt>Evals</dt><dd><span class="' + chipClass(evals.label) + '">' + esc(evals.label || 'ROADMAP') + '</span> '
      + esc(evals.note || '') + '</dd></div>'))
      + '</dl>'
      + '<p class="szl-holo-lambda" title="Λ = Conjecture 1 — advisory, never a theorem, never a gate">Λ = '
      + esc(lambda.label || 'Conjecture 1') + ' · never a theorem</p>'
      + (compact ? '' : ('<p class="szl-holo-note">' + esc(arts.note || listing.note || '') + '</p>'))
      + '<footer class="szl-holo-act">'
      + (card && card.hub_href ? '<a href="' + esc(card.hub_href) + '" target="_blank" rel="noopener noreferrer">Hub card ↗</a>' : '')
      + (github ? '<a href="' + esc(github) + '" target="_blank" rel="noopener noreferrer">GitHub source ↗</a>' : '')
      + (act && act !== href ? '<a href="' + esc(act) + '">Act</a>' : '')
      + '</footer></article>';
    return html;
  }

  function renderRoadmap(card) {
    var notClaim = (card && card.not) || 'Not shipped. Not a Hub id.';
    return '<article class="szl-holo-card szl-holo-card--roadmap" data-lane="kernel" data-id="' + esc(card && card.id) + '" data-hub="UNAVAILABLE" data-evidence="ROADMAP">'
      + '<header class="szl-holo-card-h"><span class="szl-holo-k">KERNEL · NOT SHIPPED</span>'
      + '<h3 class="szl-holo-title">' + esc(card && card.title) + '</h3>'
      + '<p class="szl-holo-one">' + esc(card && card.one_line) + '</p></header>'
      + '<dl class="szl-holo-facts">'
      + '<div><dt>Hub id</dt><dd><code class="szl-holo-id">UNAVAILABLE</code></dd></div>'
      + '<div><dt>GitHub</dt><dd><span class="szl-holo-chip szl-holo-chip--off">UNAVAILABLE</span> no public source repo</dd></div>'
      + '<div><dt>Class</dt><dd><span class="szl-holo-chip szl-holo-chip--roadmap">ROADMAP</span></dd></div>'
      + '<div><dt>Revision</dt><dd><span class="szl-holo-chip szl-holo-chip--off">UNAVAILABLE</span></dd></div>'
      + '<div><dt>Not</dt><dd>' + esc(notClaim) + '</dd></div>'
      + '</dl>'
      + '<p class="szl-holo-lambda">Λ = Conjecture 1 · never a theorem</p></article>';
  }

  function mountEstate(root, opts) {
    if (!root) return;
    opts = opts || {};
    var compact = !!opts.compact;
    root.classList.add('szl-estate-grid');
    if (compact) root.classList.add('is-compact');
    root.setAttribute('data-szl-estate', compact ? 'compact' : 'full');
    root.innerHTML = '<div class="szl-empty" data-kind="unknown"><span class="szl-empty__k">UNKNOWN</span>'
      + '<span class="szl-empty__d">probing Hub listing…</span></div>';
    fetchJson(opts.endpoint || '/api/a11oy/v1/models/series-a', 10000).then(function (d) {
      if (!d || !Array.isArray(d.cards)) throw new Error('bad payload');
      var models = d.cards.filter(function (c) { return c.lane === 'model'; });
      var kernels = d.cards.filter(function (c) { return c.lane === 'kernel'; });
      var road = d.roadmap_kernels || [];
      var parts = [];
      parts.push('<div class="szl-estate-legend" role="note">'
        + '<span>SEE Hub listing</span><span>DECIDE honest label</span><span>ACT open the card</span>'
        + '<span class="szl-holo-lambda">Λ = Conjecture 1 · catalog LOCKED-PROVEN is not Lean-8</span></div>');
      parts.push('<h4 class="szl-estate-h">Models</h4><div class="szl-estate-tiles">');
      models.forEach(function (c) { parts.push(renderCard(c, compact)); });
      parts.push('</div><h4 class="szl-estate-h">Kernels</h4><div class="szl-estate-tiles">');
      kernels.forEach(function (c) { parts.push(renderCard(c, compact)); });
      road.forEach(function (c) { parts.push(renderRoadmap(c)); });
      parts.push('</div>');
      if (!compact) {
        parts.push('<p class="szl-estate-foot">Killinchu-named Hub IDs are outside this inventory. '
          + 'Sage INT8/FP8 stays ROADMAP. YARQA-ATTN is KERNEL-owned, not a fourth Triton stack. '
          + 'Never OPERATIONAL from this listing. Lean-8 reads /api/a11oy/v1/honest locked_formula_count.</p>');
      } else {
        parts.push('<p class="szl-estate-foot"><a href="/estate">Open models + kernels</a></p>');
      }
      root.innerHTML = parts.join('');
    }).catch(function () {
      root.innerHTML = '<div class="szl-empty" data-kind="unavailable"><span class="szl-empty__k">UNAVAILABLE</span>'
        + '<span class="szl-empty__d">Hub listing could not be fetched. No inventory is invented.</span></div>';
    });
  }

  global.SZLCommandBar = { mount: mount, mountAll: mountAll };
  global.SZLEstate = { mount: mountEstate };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountAll);
  else mountAll();
})(window);
