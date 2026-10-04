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
  var barId = 0;
  var themeMedia = global.matchMedia('(prefers-color-scheme: light)');
  var consoleTheme = document.documentElement.hasAttribute('data-console-style');
  var themeChoice = null;
  function applyConsoleTheme() {
    if (!consoleTheme) return;
    var light = themeChoice ? themeChoice === 'light' : themeMedia.matches;
    document.documentElement.setAttribute('data-surface', light ? 'light' : 'dark');
    document.querySelectorAll('.szl-theme-toggle').forEach(function (button) {
      button.textContent = light ? 'Dark theme' : 'Light theme';
      button.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
    });
  }
  if (consoleTheme) {
    try { themeChoice = localStorage.getItem('szl.console.theme'); } catch (e) {}
    if (themeChoice !== 'light' && themeChoice !== 'dark') themeChoice = null;
    applyConsoleTheme();
    themeMedia.addEventListener('change', applyConsoleTheme);
  }
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
    { label: 'Command Center', href: '/command-centre' },
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
        // Other consumers define unrelated go functions; only the console owns view routing.
        if (consoleTheme && typeof global.go === 'function') global.go('investor');
        else location.href = '/console?view=investor';
      }
    });
    var cmdkBtn = el('button', { class: 'szl-cmdk', type: 'button', title: 'Command palette', 'aria-label': 'Open command palette', 'aria-haspopup': 'dialog', 'aria-controls': 'szl-command-palette', text: '⌘K' });
    var opBtn = el('button', { class: 'szl-op-toggle', type: 'button', 'aria-pressed': document.documentElement.getAttribute('data-operator') === '1' ? 'true' : 'false', text: 'Operator' });
    var menuId = 'szl-command-more-' + (++barId);
    var moreBtn = el('button', { class: 'szl-more', type: 'button', 'aria-expanded': 'false', 'aria-controls': menuId, 'aria-haspopup': 'menu', text: 'More' });
    var moreMenu = el('div', { class: 'szl-overflow-menu', id: menuId, role: 'menu', 'aria-label': 'More surfaces' });
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
    if (consoleTheme) {
      var themeButton = el('button', { class: 'szl-origin szl-theme-toggle', type: 'button' });
      themeButton.addEventListener('click', function () {
        themeChoice = document.documentElement.getAttribute('data-surface') === 'light' ? 'dark' : 'light';
        try { localStorage.setItem('szl.console.theme', themeChoice); } catch (e) {}
        applyConsoleTheme();
      });
      sw.insertBefore(themeButton, overflow);
      applyConsoleTheme();
    }

    opBtn.addEventListener('click', function () {
      var on = document.documentElement.getAttribute('data-operator') === '1';
      if (on) document.documentElement.removeAttribute('data-operator');
      else document.documentElement.setAttribute('data-operator', '1');
      opBtn.setAttribute('aria-pressed', on ? 'false' : 'true');
      try { localStorage.setItem('szl.operator', on ? '0' : '1'); } catch (e) {}
    });
    try {
      if (localStorage.getItem('szl.operator') === '1') document.documentElement.setAttribute('data-operator', '1');
    } catch (e) {}

    function closeMore(restore) {
      overflow.classList.remove('open');
      moreBtn.setAttribute('aria-expanded', 'false');
      if (restore) moreBtn.focus();
    }
    function openMore(focusLast) {
      overflow.classList.add('open');
      moreBtn.setAttribute('aria-expanded', 'true');
      moreMenu.style.left = '';
      moreMenu.style.right = '0';
      moreMenu.style.maxHeight = '';
      var menuRect = moreMenu.getBoundingClientRect();
      var viewportWidth = document.documentElement.clientWidth || global.innerWidth;
      var viewportHeight = document.documentElement.clientHeight || global.innerHeight;
      var left = Math.min(Math.max(8, menuRect.left), Math.max(8, viewportWidth - menuRect.width - 8));
      moreMenu.style.right = 'auto';
      moreMenu.style.left = (left - overflow.getBoundingClientRect().left) + 'px';
      moreMenu.style.maxHeight = Math.max(44, viewportHeight - menuRect.top - 8) + 'px';
      var items = moreMenu.querySelectorAll('a');
      if (items.length && focusLast != null) items[focusLast ? items.length - 1 : 0].focus();
    }
    moreBtn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      if (overflow.classList.contains('open')) closeMore(false);
      else openMore(null);
    });
    moreBtn.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        openMore(ev.key === 'ArrowUp');
      } else if (ev.key === 'Escape') closeMore(false);
    });
    moreMenu.addEventListener('keydown', function (ev) {
      var items = Array.prototype.slice.call(moreMenu.querySelectorAll('a'));
      var index = items.indexOf(document.activeElement);
      if (ev.key === 'Escape') {
        ev.preventDefault();
        ev.stopPropagation();
        closeMore(true);
      } else if (items.length && /^(ArrowDown|ArrowUp|Home|End)$/.test(ev.key)) {
        ev.preventDefault();
        if (ev.key === 'Home') index = 0;
        else if (ev.key === 'End') index = items.length - 1;
        else index = (index + (ev.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[index].focus();
      }
    });
    overflow.addEventListener('focusout', function () {
      setTimeout(function () {
        if (!overflow.contains(document.activeElement)) closeMore(false);
      }, 0);
    });
    document.addEventListener('click', function () { closeMore(false); });

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
        fetchJson('/api/a11oy/v1/wow/ledger?limit=1&advance=0', 6000).catch(function () { return null; }),
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

        if (lambda && typeof lambda.lambda === 'number' && isFinite(lambda.lambda)) {
          setChip(lam, false, 'CONJECTURE 1 · ADVISORY · ' + lambda.lambda.toFixed(3));
        } else {
          setChip(lam, false, 'CONJECTURE 1 · UNAVAILABLE');
        }
        lam.classList.add('szl-chip--lambda');

        var lockedN = honest && honest.locked_formula_count;
        if (lockedN === 8) setChip(kern, true, '8');
        else setChip(kern, false, 'UNAVAILABLE');

        var ledgerDepth = ledger && ledger.chain_depth;
        var dagDepth = summary && summary.dag_depth;
        var fromLedger = typeof ledgerDepth === 'number' && isFinite(ledgerDepth) && ledgerDepth >= 0 && Math.floor(ledgerDepth) === ledgerDepth;
        var depth = fromLedger ? ledgerDepth
          : (typeof dagDepth === 'number' && isFinite(dagDepth) && dagDepth >= 0 && Math.floor(dagDepth) === dagDepth) ? dagDepth : null;
        var rollEl = chain.querySelector('[data-roll]');
        chain.firstChild.textContent = depth != null && !fromLedger ? 'DAG' : 'CHAIN';
        chain.title = depth == null ? 'Chain and DAG depth sources are unavailable.' : fromLedger ? 'Reported ledger chain depth; not a signature verification result.' : 'Reported observability DAG depth; not a receipt count.';
        if (depth != null) {
          setChip(chain, true, '');
          if (rollEl) {
            roll(rollEl, String(depth));
          }
        } else {
          setChip(chain, false, 'UNAVAILABLE');
        }

        var recs = (ledger && (ledger.receipts || ledger.items)) || [];
        var rec = Array.isArray(recs) && recs[0];
        if (rec && typeof rec === 'object') {
          var ts = rec.timestamp_utc || rec.ts || rec.t || rec.created_at;
          var ageLabel = 'UNVERIFIED';
          if (rec.unsigned || rec.signer_state === 'UNSIGNED') ageLabel = 'UNSIGNED';
          else if (typeof rec.hash === 'string' && rec.hash && typeof rec.prev_hash === 'string' && rec.prev_hash) ageLabel = 'HASH-LINKED';
          if (rec.simulated === true) ageLabel = 'SAMPLE · ' + ageLabel;
          if (ts) {
            var then = Date.parse(ts);
            if (!isNaN(then)) {
              var sec = Math.round((Date.now() - then) / 1000);
              if (sec < 0) ageLabel += ' · FUTURE TIMESTAMP';
              else ageLabel += sec < 60 ? (' · ' + sec + 's') : (' · ' + Math.round(sec / 60) + 'm');
            }
          }
          setChip(age, false, ageLabel);
          age.title = 'Reported ledger entry. A hash link or receipt id does not verify a signature.';
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
      if (e.isComposing || e.keyCode === 229) return;
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        openPalette();
      }
    });
  }

  var pal = null;
  var paletteReturnFocus = null;
  var paletteBackground = [];
  var paletteOverflow = '';
  function openPalette() {
    if (!pal) pal = buildPalette();
    if (!pal.classList.contains('open')) {
      paletteReturnFocus = document.activeElement;
      pal.classList.add('open');
      pal.setAttribute('aria-hidden', 'false');
      var inp = pal.querySelector('input');
      if (inp) inp.focus();
      paletteBackground = [];
      Array.prototype.forEach.call(document.body.children, function (node) {
        if (node === pal) return;
        paletteBackground.push({ node: node, inert: node.hasAttribute('inert'), hidden: node.getAttribute('aria-hidden') });
        node.setAttribute('inert', '');
        node.setAttribute('aria-hidden', 'true');
      });
      paletteOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
    } else {
      var currentInput = pal.querySelector('input');
      if (currentInput) currentInput.focus();
    }
  }
  function closePalette() {
    if (!pal || !pal.classList.contains('open')) return;
    pal.classList.remove('open');
    paletteBackground.forEach(function (item) {
      if (!item.inert) item.node.removeAttribute('inert');
      if (item.hidden == null) item.node.removeAttribute('aria-hidden');
      else item.node.setAttribute('aria-hidden', item.hidden);
    });
    paletteBackground = [];
    document.body.style.overflow = paletteOverflow;
    if (paletteReturnFocus && document.documentElement.contains(paletteReturnFocus) && typeof paletteReturnFocus.focus === 'function') paletteReturnFocus.focus();
    pal.setAttribute('aria-hidden', 'true');
    paletteReturnFocus = null;
  }

  function buildPalette() {
    var ov = el('div', { class: 'szl-pal-ov', id: 'szl-command-palette', role: 'dialog', 'aria-modal': 'true', 'aria-hidden': 'true', 'aria-label': 'Command palette' });
    var box = el('div', { class: 'szl-pal' });
    var inp = el('input', { type: 'search', placeholder: 'Verify a receipt, jump a surface…', 'aria-label': 'Command' });
    var close = el('button', { class: 'szl-pal-close', type: 'button', 'aria-label': 'Close command palette', text: '×', onclick: closePalette });
    var head = el('div', { class: 'szl-pal-head' }, [inp, close]);
    var list = el('nav', { class: 'szl-pal-list', 'aria-label': 'Command destinations' });
    function render(q) {
      list.textContent = '';
      var qq = (q || '').toLowerCase();
      var matches = VERBS.filter(function (v) { return !qq || v.label.toLowerCase().indexOf(qq) >= 0; });
      if (!matches.length) list.appendChild(el('p', { class: 'szl-pal-empty', role: 'status', text: 'No matching commands.' }));
      matches.forEach(function (v) {
        var attrs = { class: 'szl-pal-item' };
        if (v.roadmap) { attrs.type = 'button'; attrs.disabled = ''; }
        else attrs.href = v.href;
        var item = el(v.roadmap ? 'button' : 'a', attrs, [
          el('span', { text: v.label }),
          v.roadmap ? el('span', { class: 'road', text: 'ROADMAP' }) : null
        ]);
        item.addEventListener('click', function (e) {
          if (v.roadmap) return;
          closePalette();
          if (consoleTheme && v.href.indexOf('/console?view=') === 0 && typeof global.go === 'function' && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
            e.preventDefault();
            global.go(v.href.split('view=')[1]);
          }
        });
        list.appendChild(item);
      });
    }
    inp.addEventListener('input', function () { render(inp.value); });
    ov.addEventListener('click', function (e) { if (e.target === ov) closePalette(); });
    ov.addEventListener('keydown', function (e) {
      if (e.isComposing || e.keyCode === 229) return;
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closePalette(); return; }
      var items = Array.prototype.slice.call(list.querySelectorAll('a[href]'));
      if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && (e.target === inp || items.indexOf(e.target) >= 0) && items.length) {
        e.preventDefault();
        var index = items.indexOf(document.activeElement);
        if (index < 0) index = e.key === 'ArrowDown' ? 0 : items.length - 1;
        else index = (index + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[index].focus();
      } else if (e.key === 'Enter' && e.target === inp && items.length) {
        e.preventDefault(); items[0].click();
      } else if (e.key === 'Tab') {
        var focusable = Array.prototype.slice.call(ov.querySelectorAll('input, button:not([disabled]), a[href]'));
        var first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && (document.activeElement === first || focusable.indexOf(document.activeElement) < 0)) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && (document.activeElement === last || focusable.indexOf(document.activeElement) < 0)) {
          e.preventDefault(); first.focus();
        }
      }
    });
    document.addEventListener('focusin', function (e) {
      if (ov.classList.contains('open') && !ov.contains(e.target)) inp.focus();
    });
    box.appendChild(head); box.appendChild(list); ov.appendChild(box);
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
    root.setAttribute('aria-busy', 'true');
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
      if (!models.length) parts.push('<div class="szl-empty" data-kind="unknown"><span class="szl-empty__k">NO ENTRIES REPORTED</span><span class="szl-empty__d">No models were returned by this inventory source.</span></div>');
      parts.push('</div><h4 class="szl-estate-h">Kernels</h4><div class="szl-estate-tiles">');
      kernels.forEach(function (c) { parts.push(renderCard(c, compact)); });
      road.forEach(function (c) { parts.push(renderRoadmap(c)); });
      if (!kernels.length && !road.length) parts.push('<div class="szl-empty" data-kind="unknown"><span class="szl-empty__k">NO ENTRIES REPORTED</span><span class="szl-empty__d">No kernels were returned by this inventory source.</span></div>');
      parts.push('</div>');
      if (!compact) {
        parts.push('<p class="szl-estate-foot">Killinchu-named Hub IDs are outside this inventory. '
          + 'Sage INT8/FP8 stays ROADMAP. YARQA-ATTN is KERNEL-owned, not a fourth Triton stack. '
          + 'Never OPERATIONAL from this listing. Lean-8 reads /api/a11oy/v1/honest locked_formula_count.</p>');
      } else {
        parts.push('<p class="szl-estate-foot"><a href="/estate">Open models + kernels</a></p>');
      }
      root.innerHTML = parts.join('');
      root.setAttribute('aria-busy', 'false');
    }).catch(function () {
      root.innerHTML = '<div class="szl-empty" data-kind="unavailable"><span class="szl-empty__k">UNAVAILABLE</span>'
        + '<span class="szl-empty__d">Hub listing could not be fetched. No inventory is invented.</span></div>';
      root.setAttribute('aria-busy', 'false');
      root.firstChild.appendChild(el('button', { class: 'szl-empty__retry', type: 'button', text: 'Retry inventory', onclick: function () { mountEstate(root, opts); } }));
    });
  }

  global.SZLCommandBar = { mount: mount, mountAll: mountAll };
  global.SZLEstate = { mount: mountEstate };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountAll);
  else mountAll();
})(window);
