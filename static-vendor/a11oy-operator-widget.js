/* a11oy-operator-widget.js — floating governed-operator widget for SZL surfaces.
 * Version: 3.0.0 — Chaski agent surface, wired to the LIVE a11oy/killinchu
 * substrate (real SSE chat + agentic loop + v4 ledger). No character codenames.
 *
 * The operator widget is a persistent, honest interface to the substrate. It is
 * not a destination page. It floats bottom-right, opens to a conversation panel,
 * and surfaces notifications (receipt minted, gate denied, build status,
 * doctrine drift). It ROUTES questions to the substrate backends — it has NO
 * model of its own — and is HONEST when a backend is unreachable (it never
 * fabricates an answer). The agent surface is named "Chaski" (the runner who
 * carries the message), per SZL doctrine.
 *
 * Auto-detection: the widget detects the host organ from the page origin
 * (killinchu -> /api/killinchu, otherwise -> /api/a11oy) and calls SAME-ORIGIN
 * endpoints by default, so it works on every served surface with zero config.
 *
 * Optional overrides via data-* attributes on the script tag:
 *   data-a11oy-base  -> absolute base URL for the a11oy substrate (cross-origin)
 *   data-organ       -> force organ id ("a11oy" | "killinchu")
 *   data-surface     -> name of the host surface (for attribution)
 *
 * Vanilla JS, no dependencies, no runtime CDN, embeddable anywhere.
 *
 * Author: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
 * SPDX: Apache-2.0 · DCO · ADDITIVE
 */
(function () {
  'use strict';
  if (window.__a11oyOperatorWidgetLoaded) return;
  window.__a11oyOperatorWidgetLoaded = true;

  // ---- Resolve configuration from the script tag's data-* attributes ----
  var script =
    document.currentScript ||
    (function () {
      var s = document.querySelectorAll('script[src*="a11oy-operator-widget"],script[src*="rosie-widget"]');
      return s.length ? s[s.length - 1] : null;
    })();
  var ds = (script && script.dataset) || {};

  function trim(u) { return u ? u.replace(/\/+$/, '') : ''; }

  // Detect the host organ from the page origin (same-origin by default).
  function detectOrgan() {
    if (ds.organ) return String(ds.organ).toLowerCase();
    var h = (location.hostname || '').toLowerCase();
    if (h.indexOf('killinchu') >= 0) return 'killinchu';
    return 'a11oy';
  }

  var ORGAN = detectOrgan();
  var CFG = {
    organ: ORGAN,
    // same-origin by default ('' => relative); cross-origin only if explicitly set
    base: trim(ds.a11oyBase || ds.base || ''),
    surface: ds.surface || (location.hostname || 'surface'),
  };
  // a11oy.code orchestrator (chat + agent) only lives on the a11oy organ.
  // killinchu has its own v4 surface (ledger/inbox) but routes reasoning to a11oy.
  CFG.codeBase = (ORGAN === 'killinchu' && !CFG.base)
    ? 'https://szlholdings-a11oy.hf.space'   // killinchu reasons via a11oy substrate
    : CFG.base;
  CFG.apiOrgan = ORGAN; // for v4 ledger/inbox on the host organ

  var LS_KEY = 'a11oy.operator.state.v1';
  var SS_KEY = 'a11oy.operator.thread.v1';

  // ---- Inline portrait (no runtime CDN): governed-operator monogram SVG ----
  var PORTRAIT = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
    '<stop offset="0" stop-color="#1c2742"/><stop offset="1" stop-color="#0a0f1e"/>' +
    '</linearGradient></defs>' +
    '<rect width="64" height="64" rx="16" fill="url(#g)"/>' +
    '<circle cx="32" cy="32" r="18" fill="none" stroke="#c9b787" stroke-width="2"/>' +
    '<path d="M32 16 L32 48 M16 32 L48 32" stroke="#c9b787" stroke-width="1.4" opacity="0.55"/>' +
    '<circle cx="32" cy="32" r="4.5" fill="#c9b787"/>' +
    '<text x="32" y="59" font-family="ui-monospace,monospace" font-size="9" fill="#9fb4cc" ' +
    'text-anchor="middle" letter-spacing="1">a11oy</text></svg>'
  );

  // ---- Small DOM helpers ----
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (k === 'class') n.className = attrs[k];
        else if (k === 'text') n.textContent = attrs[k];
        else if (k === 'html') n.innerHTML = attrs[k];
        else if (k.slice(0, 2) === 'on' && typeof attrs[k] === 'function')
          n.addEventListener(k.slice(2), attrs[k]);
        else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
      }
    }
    (kids || []).forEach(function (c) {
      if (c == null) return;
      n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ---- Persistent state ----
  var state = { unread: 0, status: 'unknown' };
  try {
    var saved = JSON.parse(localStorage.getItem(LS_KEY) || '{}');
    if (saved && typeof saved === 'object' && typeof saved.unread === 'number') state.unread = saved.unread;
  } catch (e) {}
  function persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify({ unread: state.unread })); } catch (e) {}
  }

  var thread = [];
  try {
    var t = JSON.parse(sessionStorage.getItem(SS_KEY) || '[]');
    if (Array.isArray(t)) thread = t;
  } catch (e) {}
  function persistThread() {
    try { sessionStorage.setItem(SS_KEY, JSON.stringify(thread.slice(-50))); } catch (e) {}
  }

  // ---- CSS (neutral governed palette: deep navy + signed gold + emerald) ----
  var css = [
    '.aow-root{position:fixed;bottom:24px;right:24px;z-index:2147483647;font-family:"Inter",system-ui,sans-serif;font-size:14px;line-height:1.5;}',
    '.aow-fab{width:56px;height:56px;border-radius:50%;border:1px solid rgba(201,183,135,0.45);cursor:pointer;',
    'background:linear-gradient(135deg,#16203a 0%,#0a0f1e 100%);',
    'box-shadow:0 4px 20px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;',
    'position:relative;transition:transform .18s,box-shadow .18s;outline:none;}',
    '.aow-fab:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(201,183,135,0.35);}',
    '.aow-fab:focus-visible{outline:3px solid #c9b787;outline-offset:3px;}',
    '.aow-fab img{width:40px;height:40px;border-radius:50%;object-fit:cover;}',
    '.aow-fab-fallback{color:#c9b787;font-weight:700;font-size:20px;}',
    '.aow-badge{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;',
    'border-radius:9px;background:#c8415d;color:#fff;font-size:11px;font-weight:700;',
    'display:none;align-items:center;justify-content:center;padding:0 4px;border:2px solid #0a0f1e;}',
    '[data-unread="true"] .aow-badge{display:flex;}',
    '.aow-panel{position:fixed;bottom:92px;right:24px;width:370px;max-width:calc(100vw - 48px);',
    'height:540px;max-height:calc(100vh - 120px);background:#0c1322;',
    'border:1px solid rgba(201,183,135,0.22);border-radius:16px;display:none;flex-direction:column;',
    'box-shadow:0 8px 40px rgba(0,0,0,0.65);overflow:hidden;}',
    '[data-open="true"] .aow-panel{display:flex;}',
    '.aow-head{display:flex;align-items:center;gap:10px;padding:12px 14px;',
    'border-bottom:1px solid rgba(201,183,135,0.16);background:rgba(22,32,58,0.6);}',
    '.aow-head-avatar{width:34px;height:34px;border-radius:50%;object-fit:cover;flex-shrink:0;}',
    '.aow-head-text{display:flex;flex-direction:column;flex:1;min-width:0;}',
    '.aow-eyebrow{font-size:9px;letter-spacing:.12em;color:#c9b787;font-weight:700;text-transform:uppercase;}',
    '.aow-head-name{font-size:13px;font-weight:600;color:#e6edf6;}',
    '.aow-status{display:flex;align-items:center;gap:5px;margin-left:auto;flex-shrink:0;}',
    '.aow-status-dot{width:8px;height:8px;border-radius:50%;background:#7d8aa3;transition:background .3s;}',
    '[data-state="ok"] .aow-status-dot{background:#4ade80;}',
    '[data-state="down"] .aow-status-dot{background:#f87171;}',
    '[data-state="unknown"] .aow-status-dot{background:#7d8aa3;}',
    '.aow-status-label{font-size:11px;color:#9fb0c8;}',
    '.aow-close{background:none;border:none;color:#9fb0c8;font-size:20px;cursor:pointer;',
    'padding:0 4px;line-height:1;margin-left:6px;border-radius:4px;transition:color .15s;}',
    '.aow-close:hover{color:#e6edf6;}',
    /* Quick action buttons */
    '.aow-quick-actions{display:flex;gap:6px;padding:8px 10px;border-bottom:1px solid rgba(201,183,135,0.12);',
    'background:rgba(12,19,34,0.85);flex-wrap:wrap;}',
    '.aow-qa-btn{flex:1;min-width:80px;background:rgba(201,183,135,0.08);border:1px solid rgba(201,183,135,0.22);',
    'color:#cdb98a;font-size:11px;font-family:inherit;border-radius:6px;padding:5px 8px;',
    'cursor:pointer;transition:background .15s,border-color .15s;text-align:center;font-weight:500;',
    'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}',
    '.aow-qa-btn:hover{background:rgba(201,183,135,0.18);border-color:rgba(201,183,135,0.5);color:#fff;}',
    '.aow-qa-btn:active{background:rgba(201,183,135,0.28);}',
    '.aow-qa-btn:disabled{opacity:0.4;cursor:not-allowed;}',
    '.aow-thread{flex:1;overflow-y:auto;padding:12px 10px;display:flex;flex-direction:column;gap:8px;}',
    '.aow-empty{color:#9fb0c8;font-size:13px;text-align:center;padding:20px 6px;}',
    '.aow-msg{max-width:90%;padding:8px 12px;border-radius:10px;font-size:13px;word-break:break-word;white-space:pre-wrap;}',
    '.aow-msg-user{align-self:flex-end;background:rgba(201,183,135,0.16);color:#e6edf6;border-bottom-right-radius:3px;}',
    '.aow-msg-op{align-self:flex-start;background:rgba(22,32,58,0.85);color:#e6edf6;',
    'border-bottom-left-radius:3px;border:1px solid rgba(201,183,135,0.14);}',
    '.aow-msg-meta{font-size:10px;color:#9fb0c8;margin-top:4px;font-family:ui-monospace,"JetBrains Mono",monospace;}',
    '.aow-typing-wrap{align-self:flex-start;}',
    '.aow-typing{display:flex;gap:4px;padding:10px 14px;background:rgba(22,32,58,0.85);',
    'border-radius:10px;border:1px solid rgba(201,183,135,0.14);}',
    '.aow-typing span{width:6px;height:6px;border-radius:50%;background:#c9b787;animation:aow-bounce 1.2s infinite ease-in-out;}',
    '.aow-typing span:nth-child(2){animation-delay:.2s;}',
    '.aow-typing span:nth-child(3){animation-delay:.4s;}',
    '@keyframes aow-bounce{0%,80%,100%{transform:translateY(0);}40%{transform:translateY(-6px);}}',
    '.aow-form{display:flex;align-items:flex-end;gap:6px;padding:10px;border-top:1px solid rgba(201,183,135,0.14);}',
    '.aow-input{flex:1;background:rgba(22,32,58,0.5);border:1px solid rgba(201,183,135,0.22);',
    'border-radius:8px;color:#e6edf6;font-family:inherit;font-size:13px;padding:7px 10px;',
    'resize:none;max-height:90px;outline:none;transition:border-color .15s;}',
    '.aow-input:focus{border-color:rgba(201,183,135,0.55);}',
    '.aow-input::placeholder{color:#7d8aa3;}',
    '.aow-send{background:#c9b787;border:none;border-radius:8px;color:#0a0f1e;',
    'font-weight:700;font-size:16px;width:36px;height:36px;cursor:pointer;flex-shrink:0;',
    'display:flex;align-items:center;justify-content:center;transition:background .15s;}',
    '.aow-send:hover{background:#dccca0;}',
    '.aow-toasts{position:fixed;bottom:92px;right:24px;display:flex;flex-direction:column;gap:8px;',
    'z-index:2147483646;pointer-events:none;width:330px;max-width:calc(100vw - 48px);}',
    '.aow-root[data-open="true"] .aow-toasts{bottom:calc(540px + 100px);}',
    '.aow-toast{display:flex;align-items:flex-start;gap:10px;background:#0c1322;',
    'border:1px solid rgba(201,183,135,0.22);border-radius:12px;padding:10px 12px;',
    'box-shadow:0 4px 16px rgba(0,0,0,0.55);pointer-events:all;animation:aow-toast-in .2s ease-out;}',
    '@keyframes aow-toast-in{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}',
    '.aow-toast-out{animation:aow-toast-out .2s ease-in forwards;}',
    '@keyframes aow-toast-out{to{opacity:0;transform:translateY(10px);}}',
    '.aow-toast-avatar{width:28px;height:28px;border-radius:50%;object-fit:cover;flex-shrink:0;}',
    '.aow-toast-body{flex:1;min-width:0;}',
    '.aow-toast-title{font-size:13px;font-weight:600;color:#e6edf6;}',
    '.aow-toast-text{font-size:12px;color:#9fb0c8;margin-top:2px;}',
    '.aow-toast-meta{font-size:10px;color:#cdb98a;font-family:ui-monospace,"JetBrains Mono",monospace;margin-top:2px;}',
    '.aow-toast-x{background:none;border:none;color:#9fb0c8;cursor:pointer;font-size:16px;padding:0 2px;line-height:1;flex-shrink:0;}',
    '[data-kind="receipt"] .aow-toast-title::before{content:"\\1F4DC ";}',
    '[data-kind="denial"] .aow-toast-title::before{content:"\\1F6AB ";}',
    '[data-kind="build-green"] .aow-toast-title::before{content:"\\2705 ";}',
    '[data-kind="build-red"] .aow-toast-title::before{content:"\\274C ";}',
    '[data-kind="doctrine"] .aow-toast-title::before{content:"\\26A0\\FE0F ";}',
  ].join('');

  var style = document.createElement('style');
  style.textContent = css;
  (document.head || document.documentElement).appendChild(style);

  // ---- Build the DOM ----
  var root = el('div', { class: 'aow-root', 'data-open': 'false', 'data-unread': 'false' });
  root.setAttribute('data-a11oy-operator', 'widget');

  var fabImg = el('img', { src: PORTRAIT, alt: '', 'aria-hidden': 'true' });
  fabImg.addEventListener('error', function () {
    fabImg.style.display = 'none';
    fab.appendChild(el('span', { class: 'aow-fab-fallback', text: 'a11' }));
  });
  var badge = el('span', { class: 'aow-badge', 'aria-hidden': 'true' });
  var fab = el('button', {
    class: 'aow-fab', type: 'button',
    'aria-label': 'Open the a11oy operator assistant',
    'aria-haspopup': 'dialog', 'aria-expanded': 'false',
  }, [fabImg, badge]);

  var headAvatar = el('img', { class: 'aow-head-avatar', src: PORTRAIT, alt: '' });
  var statusDot = el('span', { class: 'aow-status-dot' });
  var statusLabel = el('span', { class: 'aow-status-label', text: 'checking' });
  var statusEl = el('span', { class: 'aow-status', 'data-state': 'unknown' }, [statusDot, statusLabel]);
  var closeBtn = el('button', { class: 'aow-close', type: 'button', 'aria-label': 'Close the operator assistant', text: '\u00d7' });
  var head = el('div', { class: 'aow-head' }, [
    headAvatar,
    el('div', { class: 'aow-head-text' }, [
      el('span', { class: 'aow-eyebrow', text: 'a11oy operator' }),
      el('span', { class: 'aow-head-name', text: 'Chaski \u2014 governed agent surface' }),
    ]),
    statusEl,
    closeBtn,
  ]);

  // Quick action buttons — wired to REAL live endpoints
  var qaReceipt = el('button', {
    class: 'aow-qa-btn', type: 'button', title: 'Show the latest receipts from the ' + CFG.organ + ' v4 ledger',
    text: '\uD83D\uDCDC Receipts',
    onclick: function () { open(); quickAction('receipt'); }
  });
  var qaVerify = el('button', {
    class: 'aow-qa-btn', type: 'button', title: 'Check substrate health + receipt-chain head',
    text: '\uD83D\uDD10 Verify',
    onclick: function () { open(); quickAction('verify'); }
  });
  var qaAgent = el('button', {
    class: 'aow-qa-btn', type: 'button', title: 'Run the governed Chaski agentic loop on a task',
    text: '\u26A1 Agent',
    onclick: function () { open(); quickAction('agent'); }
  });
  var qaAsk = el('button', {
    class: 'aow-qa-btn', type: 'button', title: 'Ask a11oy to explain this surface (governed reasoning)',
    text: '\uD83E\uDDE0 Ask a11oy',
    onclick: function () { open(); quickAction('ask'); }
  });
  var quickActions = el('div', { class: 'aow-quick-actions' }, [qaReceipt, qaVerify, qaAgent, qaAsk]);

  var threadEl = el('div', { class: 'aow-thread', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversation with the a11oy operator' });

  var input = el('textarea', {
    class: 'aow-input', rows: '1', placeholder: 'Ask the a11oy substrate\u2026',
    'aria-label': 'Message to the a11oy operator',
  });
  var sendBtn = el('button', { class: 'aow-send', type: 'submit', 'aria-label': 'Send', html: '&#10148;' });
  var form = el('form', { class: 'aow-form' }, [input, sendBtn]);

  var panel = el('div', { class: 'aow-panel', role: 'dialog', 'aria-label': 'a11oy operator assistant', 'aria-modal': 'false' },
    [head, quickActions, threadEl, form]);

  var toasts = el('div', { class: 'aow-toasts', 'aria-live': 'polite', 'aria-label': 'a11oy operator notifications' });

  root.appendChild(toasts);
  root.appendChild(panel);
  root.appendChild(fab);

  function mount() {
    if (!document.body) { document.addEventListener('DOMContentLoaded', mount); return; }
    document.body.appendChild(root);
    renderThread();
    refreshBadge();
    checkStatus();
  }
  mount();

  // ---- Open / close ----
  var isOpen = false;
  function open() {
    isOpen = true;
    root.setAttribute('data-open', 'true');
    fab.setAttribute('aria-expanded', 'true');
    state.unread = 0; persist(); refreshBadge();
    if (!thread.length) renderThread();
    setTimeout(function () { input.focus(); }, 60);
    scrollThread();
  }
  function close() {
    isOpen = false;
    root.setAttribute('data-open', 'false');
    fab.setAttribute('aria-expanded', 'false');
    fab.focus();
  }
  function toggle() { isOpen ? close() : open(); }

  fab.addEventListener('click', toggle);
  closeBtn.addEventListener('click', close);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && isOpen) close(); });

  // ---- Thread rendering ----
  function refreshBadge() {
    root.setAttribute('data-unread', state.unread > 0 ? 'true' : 'false');
    badge.textContent = state.unread > 9 ? '9+' : String(state.unread || '');
  }
  function scrollThread() { requestAnimationFrame(function () { threadEl.scrollTop = threadEl.scrollHeight; }); }
  function renderThread() {
    threadEl.innerHTML = '';
    if (!thread.length) {
      var em = el('div', { class: 'aow-empty' });
      em.innerHTML =
        '<strong>a11oy operator \u2014 Chaski</strong><br>' +
        'Ask the substrate anything, or use the buttons above. I route to the live ' +
        esc(CFG.organ) + ' backend and stay honest when it is unreachable \u2014 I never fabricate.' +
        '<br><br><small style="color:#6b7a96">Surface: <em>' + esc(CFG.surface) + '</em> \u2022 organ: <em>' + esc(CFG.organ) + '</em></small>';
      threadEl.appendChild(em);
      return;
    }
    thread.forEach(function (m) { threadEl.appendChild(renderMsg(m)); });
    scrollThread();
  }
  function renderMsg(m) {
    var cls = m.role === 'user' ? 'aow-msg aow-msg-user' : 'aow-msg aow-msg-op';
    var node = el('div', { class: cls });
    node.innerHTML = esc(m.text).replace(/\n/g, '<br>');
    if (m.meta) node.appendChild(el('div', { class: 'aow-msg-meta', text: m.meta }));
    if (m.dsse) {
      var dsseNode = el('div', { class: 'aow-msg-meta' });
      dsseNode.innerHTML = '<strong>receipt:</strong> ' + esc(m.dsse);
      node.appendChild(dsseNode);
    }
    return node;
  }
  function pushMsg(role, text, meta, dsse) {
    var m = { role: role, text: text, meta: meta || null, ts: Date.now(), dsse: dsse || null };
    thread.push(m); persistThread();
    if (threadEl.querySelector('.aow-empty')) threadEl.innerHTML = '';
    threadEl.appendChild(renderMsg(m));
    scrollThread();
    return m;
  }
  function showTyping() {
    var t = el('div', { class: 'aow-msg aow-msg-op aow-typing-wrap' }, [
      el('div', { class: 'aow-typing' }, [el('span'), el('span'), el('span')]),
    ]);
    threadEl.appendChild(t); scrollThread();
    return t;
  }
  // Append into an existing op message node (used for streaming).
  function appendStream(node, chunk) {
    node.dataset.acc = (node.dataset.acc || '') + chunk;
    node.innerHTML = esc(node.dataset.acc).replace(/\n/g, '<br>');
    scrollThread();
  }

  // ---- Endpoint helpers (REAL live contract) ----
  function codeUrl(path) { return CFG.codeBase + '/api/a11oy/code' + path; }   // chat/agent/health live on a11oy organ
  function v4Url(path) { return CFG.base + '/api/' + CFG.apiOrgan + '/v4' + path; } // ledger/inbox on host organ
  function healthUrl() { return CFG.base + '/healthz'; }

  // ---- Backend status (honest) ----
  function checkStatus() {
    fetchJson(healthUrl(), { method: 'GET' }, 5000)
      .then(function () { setStatus('ok', CFG.organ + ' online'); })
      .catch(function () { setStatus('down', CFG.organ + ' unreachable'); });
  }
  function setStatus(s, label) {
    state.status = s;
    statusEl.setAttribute('data-state', s);
    statusLabel.textContent = label;
  }

  // ---- Networking ----
  function fetchJson(url, opts, timeoutMs) {
    opts = opts || {};
    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    if (ctrl) opts.signal = ctrl.signal;
    opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeoutMs || 12000) : null;
    return fetch(url, opts).then(function (r) {
      if (timer) clearTimeout(timer);
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      var ct = r.headers.get('content-type') || '';
      return ct.indexOf('application/json') >= 0 ? r.json() : r.text();
    }).catch(function (e) { if (timer) clearTimeout(timer); throw e; });
  }

  // Stream a Server-Sent-Events POST endpoint, calling onEvent({event,data}) per frame.
  function streamSSE(url, body, onEvent, timeoutMs) {
    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeoutMs || 90000) : null;
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(body),
      signal: ctrl ? ctrl.signal : undefined,
    }).then(function (r) {
      if (!r.ok) { if (timer) clearTimeout(timer); var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      if (!r.body || !r.body.getReader) {
        // No streaming support — read whole body and emit one event.
        return r.text().then(function (txt) { if (timer) clearTimeout(timer); parseSSEBlock(txt, onEvent); });
      }
      var reader = r.body.getReader();
      var dec = new TextDecoder();
      var buf = '';
      function pump() {
        return reader.read().then(function (res) {
          if (res.done) { if (timer) clearTimeout(timer); if (buf.trim()) parseSSEBlock(buf, onEvent); return; }
          buf += dec.decode(res.value, { stream: true });
          var parts = buf.split('\n\n');
          buf = parts.pop();
          parts.forEach(function (p) { parseSSEFrame(p, onEvent); });
          return pump();
        });
      }
      return pump();
    }).catch(function (e) { if (timer) clearTimeout(timer); throw e; });
  }
  function parseSSEFrame(frame, onEvent) {
    var ev = 'message', data = '';
    frame.split('\n').forEach(function (line) {
      if (line.indexOf('event:') === 0) ev = line.slice(6).trim();
      else if (line.indexOf('data:') === 0) data += line.slice(5).trim();
    });
    if (data) { var parsed; try { parsed = JSON.parse(data); } catch (e) { parsed = data; } onEvent({ event: ev, data: parsed }); }
  }
  function parseSSEBlock(txt, onEvent) { txt.split('\n\n').forEach(function (f) { if (f.trim()) parseSSEFrame(f, onEvent); }); }

  // ---- Quick Actions (REAL endpoints) ----
  function disableQA(d) { [qaReceipt, qaVerify, qaAgent, qaAsk].forEach(function (b) { b.disabled = d; }); }

  function quickAction(kind) {
    if (kind === 'receipt') {
      pushMsg('user', '\uD83D\uDCDC Latest receipts');
      disableQA(true);
      var typing = showTyping();
      fetchJson(v4Url('/receipts?limit=10'), { method: 'GET' }, 14000)
        .then(function (data) {
          typing.remove(); disableQA(false);
          var items = data.receipts || data.items || (Array.isArray(data) ? data : []);
          if (!items.length) {
            pushMsg('op', 'The ' + CFG.organ + ' v4 ledger is currently empty \u2014 no receipts minted yet. ' +
              (data.note ? '\n\nNote from the substrate: ' + data.note : '') + '\n\nThat is an honest idle state, not an error.');
          } else {
            var top = items[0];
            var hash = top.hash || top.receipt_id || top.id || top.digest;
            var msg = items.length + ' receipt(s) in the chain.';
            if (data.total != null) msg += '\nHead total: ' + data.total;
            if (top.action) msg += '\nMost recent action: ' + top.action;
            if (top.timestamp_utc || top.ts) msg += '\nTime: ' + (top.timestamp_utc || top.ts);
            if (data.note) msg += '\n\n' + data.note;
            pushMsg('op', msg, hash ? 'receipt ' + hash : null);
          }
          setStatus('ok', 'ledger \u2713');
        })
        .catch(function (err) { typing.remove(); disableQA(false); handleNetErr(err); });

    } else if (kind === 'verify') {
      pushMsg('user', '\uD83D\uDD10 Verify substrate + chain head');
      disableQA(true);
      var typing2 = showTyping();
      fetchJson(healthUrl(), { method: 'GET' }, 8000)
        .then(function (h) {
          var lock = (h && (h.lock || h.counts)) || '?';
          var commit = (h && h.commit) || (h && h.lean_sha) || '?';
          return fetchJson(v4Url('/receipts?limit=1'), { method: 'GET' }, 10000)
            .then(function (led) {
              typing2.remove(); disableQA(false);
              var items = led.receipts || led.items || [];
              var head = items.length ? (items[0].hash || items[0].receipt_id || items[0].id) : null;
              var msg = CFG.organ + ' substrate is online.\nKernel lock: ' + lock + '\nLean commit: ' + commit +
                '\nLocked-proven formulas: 8 {F1,F4,F7,F11,F12,F18,F19,F22} \u2014 machine-enforced.';
              if (head) msg += '\nReceipt-chain head: present.';
              else msg += '\nReceipt chain: empty (honest idle).';
              if (led.note) msg += '\n\n' + led.note;
              pushMsg('op', msg, head ? 'head ' + head : null);
              setStatus('ok', 'chain \u2713');
            });
        })
        .catch(function (err) { typing2.remove(); disableQA(false); handleNetErr(err); });

    } else if (kind === 'agent') {
      var task = 'Summarise the governance posture of the ' + CFG.surface + ' surface: what is proven, what is experimental, what is roadmap. Be honest and cite.';
      pushMsg('user', '\u26A1 Run Chaski agent: ' + task);
      disableQA(true);
      runAgent(task, function () { disableQA(false); });

    } else if (kind === 'ask') {
      var q = 'In two or three sentences, what is the a11oy substrate and what does it govern? What runs on this surface (' + CFG.surface + ')?';
      pushMsg('user', '\uD83E\uDDE0 ' + q);
      disableQA(true);
      runChat(q, function () { disableQA(false); });
    }
  }

  // ---- Governed chat (live SSE, real LLM router) ----
  function runChat(q, doneCb) {
    var typing = showTyping();
    var opNode = null, routeMeta = null;
    streamSSE(codeUrl('/chat/stream'), { message: q, thread: CFG.surface, surface: CFG.surface },
      function (ev) {
        if (ev.event === 'route' && ev.data && typeof ev.data === 'object') {
          routeMeta = 'router: ' + (ev.data.tier || '?') + ' \u00b7 ' + (ev.data.model || '?') +
            (ev.data.license_class ? ' \u00b7 ' + ev.data.license_class : '');
        } else if (ev.event === 'token' || ev.event === 'delta' || ev.event === 'message') {
          if (typing) { typing.remove(); typing = null; }
          if (!opNode) { opNode = pushMsg('op', '') ; opNode = threadEl.lastChild; }
          var chunk = (ev.data && (ev.data.text || ev.data.token || ev.data.delta || ev.data.content)) || (typeof ev.data === 'string' ? ev.data : '');
          if (chunk) appendStream(opNode, chunk);
        } else if (ev.event === 'done' || ev.event === 'final' || ev.event === 'end') {
          if (typing) { typing.remove(); typing = null; }
          if (ev.data && ev.data.text && opNode && !opNode.dataset.acc) appendStream(opNode, ev.data.text);
          if (opNode && routeMeta) opNode.appendChild(el('div', { class: 'aow-msg-meta', text: routeMeta }));
          // persist final accumulated text into thread store
          if (opNode && opNode.dataset.acc) { thread[thread.length - 1] = { role: 'op', text: opNode.dataset.acc, meta: routeMeta, ts: Date.now() }; persistThread(); }
          setStatus('ok', CFG.organ + ' online');
        } else if (ev.event === 'error') {
          if (typing) { typing.remove(); typing = null; }
          pushMsg('op', 'The substrate reported an error: ' + (ev.data && ev.data.error ? ev.data.error : 'unknown') + '. I will not guess what it meant.');
        }
      }, 90000)
      .then(function () { if (typing) { typing.remove(); } if (doneCb) doneCb(); })
      .catch(function (err) { if (typing) typing.remove(); handleNetErr(err); if (doneCb) doneCb(); });
  }

  // ---- Governed agentic loop (live SSE FSM: INTAKE..FINALIZE) ----
  function runAgent(task, doneCb) {
    var typing = showTyping();
    var stepNode = null, finalNode = null;
    streamSSE(codeUrl('/agent/stream'), { task: task, thread: CFG.surface, surface: CFG.surface },
      function (ev) {
        var d = ev.data || {};
        if (ev.event === 'state' || d.state) {
          if (typing) { typing.remove(); typing = null; }
          var st = d.state || ev.event;
          if (!stepNode) stepNode = pushMsg('op', '');
          var line = '\u2022 ' + st + (d.note ? ': ' + d.note : (d.summary ? ': ' + d.summary : ''));
          var node = threadEl.lastChild;
          node.dataset.acc = (node.dataset.acc ? node.dataset.acc + '\n' : '') + line;
          node.innerHTML = esc(node.dataset.acc).replace(/\n/g, '<br>');
          scrollThread();
        } else if (ev.event === 'token' || ev.event === 'delta') {
          if (typing) { typing.remove(); typing = null; }
          if (!finalNode) { pushMsg('op', ''); finalNode = threadEl.lastChild; }
          var chunk = d.text || d.token || d.delta || (typeof ev.data === 'string' ? ev.data : '');
          if (chunk) appendStream(finalNode, chunk);
        } else if (ev.event === 'final' || ev.event === 'done' || ev.event === 'finalize') {
          if (typing) { typing.remove(); typing = null; }
          var ans = d.answer || d.text || d.result || d.output;
          var meta = (d.chain_verified != null ? 'chain_verified=' + d.chain_verified : null);
          if (ans) pushMsg('op', String(ans), meta);
          else if (meta) pushMsg('op', 'Agent run complete.', meta);
          setStatus('ok', CFG.organ + ' online');
        } else if (ev.event === 'error') {
          if (typing) { typing.remove(); typing = null; }
          pushMsg('op', 'The agent loop reported an error: ' + (d.error || 'unknown') + '. Honest stop \u2014 no fabricated result.');
        }
      }, 120000)
      .then(function () { if (typing) typing.remove(); if (doneCb) doneCb(); })
      .catch(function (err) { if (typing) typing.remove(); handleNetErr(err); if (doneCb) doneCb(); });
  }

  function handleNetErr(err) {
    if (err && err.status) {
      pushMsg('op', 'The ' + CFG.organ + ' substrate answered with an error (' + err.status + '). I will not guess what it meant \u2014 try rephrasing, or check the service.');
    } else {
      pushMsg('op', 'I cannot reach the ' + CFG.organ + ' substrate right now, so I will not make up an answer. Ask me again in a moment.');
      setStatus('down', CFG.organ + ' unreachable');
    }
  }

  // ---- Free-text routing: chat by default; explicit agent intent -> agent loop ----
  function ask(q) {
    pushMsg('user', q);
    var s = q.toLowerCase();
    if (/\b(agent|act|do|run|build|fix|investigate|plan and execute|carry out)\b/.test(s)) {
      runAgent(q);
    } else {
      runChat(q);
    }
  }

  function safeJson(o) {
    try { var s = JSON.stringify(o, null, 2); return s.length > 800 ? s.slice(0, 800) + '\u2026' : s; }
    catch (e) { return String(o); }
  }

  // ---- Input handling ----
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) return;
    input.value = ''; input.style.height = 'auto';
    ask(q);
  });
  input.addEventListener('input', function () {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 90) + 'px';
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true })); }
  });

  // ---- Notifications API ----
  function notify(opts) {
    opts = opts || {};
    var kind = opts.kind || 'info';
    var avatar = el('img', { class: 'aow-toast-avatar', src: PORTRAIT, alt: '' });
    var body = el('div', { class: 'aow-toast-body' });
    body.appendChild(el('div', { class: 'aow-toast-title', html: '<strong>' + esc(opts.title || 'a11oy operator') + '</strong>' }));
    if (opts.body) body.appendChild(el('div', { class: 'aow-toast-text', text: opts.body }));
    if (opts.meta) body.appendChild(el('div', { class: 'aow-toast-meta', text: opts.meta }));
    var toast;
    function dismiss() {
      if (!toast) return;
      toast.classList.add('aow-toast-out');
      setTimeout(function () { if (toast && toast.parentNode) toast.parentNode.removeChild(toast); }, 220);
    }
    var x = el('button', { class: 'aow-toast-x', type: 'button', 'aria-label': 'Dismiss', text: '\u00d7', onclick: dismiss });
    toast = el('div', { class: 'aow-toast', 'data-kind': kind, role: 'status' }, [avatar, body, x]);
    toasts.appendChild(toast);
    pushMsg('op', (opts.title ? opts.title + (opts.body ? ' \u2014 ' + opts.body : '') : opts.body || ''), opts.meta);
    if (!isOpen) { state.unread = (state.unread || 0) + 1; persist(); refreshBadge(); }
    if (!opts.sticky) setTimeout(dismiss, opts.duration || 8000);
    return { dismiss: dismiss };
  }

  // ---- Public API ----
  var api = {
    open: open, close: close, toggle: toggle,
    ask: function (q) { open(); ask(q); },
    agent: function (task) { open(); runAgent(task); },
    chat: function (q) { open(); runChat(q); },
    notify: notify,
    config: CFG,
    receiptMinted: function (hash, what) {
      return notify({ kind: 'receipt', title: 'New receipt minted', body: what || 'A receipt was added to the ledger.', meta: hash ? 'receipt ' + hash : null });
    },
    gateDenied: function (gate, what) {
      return notify({ kind: 'denial', title: 'Policy denied an action', body: what || 'A proposed action was rejected by the gates.', meta: gate ? 'gate ' + gate : null });
    },
    build: function (green, detail) {
      return notify({ kind: green ? 'build-green' : 'build-red', title: green ? 'Build is green' : 'Build is red', body: detail || '' });
    },
    doctrineDrift: function (detail) {
      return notify({ kind: 'doctrine', title: 'Doctrine drift detected', body: detail || 'Something diverged from doctrine. Worth a look.' });
    },
  };
  window.A11oyOperator = api;
  // Back-compat alias for any existing caller (NOT a user-visible name).
  window.Rosie = api;
})();
