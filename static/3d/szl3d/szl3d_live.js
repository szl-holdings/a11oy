// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// szl3d_live.js — SHARED live-data poller for the holographic estate (Dev0 foundation).
//
// Doctrine v11: WIRE TO LIVE DATA. Every value on a holographic surface must trace to
// a real a11oy endpoint. This module is the ONE place the 9 surface devs fetch from, so
// degraded/404 handling and the honesty posture are uniform.
//
//   poll(endpoint, intervalMs, onData, opts) -> handle
//     * fetches `endpoint` (same-origin) every intervalMs
//     * calls onData(json, meta) on success
//     * on 404 -> meta.state="missing"; on {degraded:true} -> meta.state="degraded";
//       on network error -> meta.state="error". NEVER fabricates a value — callers must
//       render the honest degraded/NO-LIVE-DATA state, not a crash.
//     * drives a visible "LIVE · last fetch Xs ago" badge element (createBadge()).
//     * reads doctrine honesty fields off the JSON ({label} / {joules_label} / {data_label})
//       and surfaces them via meta.label so szl3d_label can chip them.
//
// 0 runtime CDN. Pure DOM + fetch; no dependencies.

export const LIVE_STATES = Object.freeze({
  LIVE: "live", DEGRADED: "degraded", MISSING: "missing", ERROR: "error", INIT: "init",
});

// Pull the doctrine honesty label out of whatever field the endpoint used.
// Returns an UPPERCASE canonical token or null. Honest: we read it, never invent it.
export function readHonestyLabel(json) {
  if (!json || typeof json !== "object") return null;
  const raw = json.label || json.joules_label || json.data_label || json.status_label ||
              (json.joules_evidence && json.joules_evidence.label) || null;
  if (!raw) return null;
  const t = String(raw).trim().toUpperCase();
  if (t.indexOf("MEASURED") >= 0) return "MEASURED";
  if (t.indexOf("MODELED") >= 0 || t.indexOf("MODELLED") >= 0) return "MODELED";
  if (t.indexOf("SAMPLE") >= 0) return "SAMPLE";
  if (t.indexOf("STRUCTURAL") >= 0) return "STRUCTURAL-ONLY";
  return t; // pass through unknown labels verbatim rather than guessing
}

function _fmtAge(ms) {
  if (ms == null) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 1) return "just now";
  if (s < 60) return s + "s ago";
  const m = Math.floor(s / 60);
  if (m < 60) return m + "m ago";
  return Math.floor(m / 60) + "h ago";
}

// createBadge(opts) -> { el, set(state, info), tick() }
// A self-styled DOM badge ("LIVE · last fetch Xs ago"). System fonts only.
export function createBadge(opts = {}) {
  const el = document.createElement("div");
  el.className = "szl3d-live-badge";
  el.setAttribute("data-state", LIVE_STATES.INIT);
  const dot = document.createElement("span"); dot.className = "szl3d-live-dot";
  const txt = document.createElement("span"); txt.className = "szl3d-live-txt";
  el.appendChild(dot); el.appendChild(txt);

  if (!opts.unstyled) {
    Object.assign(el.style, {
      display: "inline-flex", alignItems: "center", gap: "7px",
      font: "11px ui-monospace,SFMono-Regular,Menlo,monospace",
      padding: "3px 9px", borderRadius: "999px",
      border: "1px solid #1d2a36", background: "#0a1117", color: "#9fb1bf",
      letterSpacing: ".3px", userSelect: "none",
    });
    Object.assign(dot.style, {
      width: "8px", height: "8px", borderRadius: "50%",
      background: "#39d3c4", boxShadow: "0 0 6px #39d3c4",
    });
  }

  let _lastOk = null, _state = LIVE_STATES.INIT, _label = null;
  const COLORS = {
    [LIVE_STATES.LIVE]: "#39d3c4",
    [LIVE_STATES.DEGRADED]: "#e8c074",
    [LIVE_STATES.MISSING]: "#7d8a96",
    [LIVE_STATES.ERROR]: "#ff6b6b",
    [LIVE_STATES.INIT]: "#6fb1ff",
  };

  function _paint() {
    el.setAttribute("data-state", _state);
    if (!opts.unstyled) {
      const c = COLORS[_state] || "#9fb1bf";
      dot.style.background = c; dot.style.boxShadow = "0 0 6px " + c;
    }
    let head;
    if (_state === LIVE_STATES.LIVE) head = "LIVE";
    else if (_state === LIVE_STATES.DEGRADED) head = "DEGRADED";
    else if (_state === LIVE_STATES.MISSING) head = "NO-LIVE-DATA";
    else if (_state === LIVE_STATES.ERROR) head = "OFFLINE";
    else head = "…";
    const age = _lastOk != null ? "last fetch " + _fmtAge(Date.now() - _lastOk) : "no data yet";
    const lab = _label ? " · " + _label : "";
    txt.textContent = head + " · " + age + lab;
  }

  function set(state, info = {}) {
    _state = state;
    if (state === LIVE_STATES.LIVE) _lastOk = info.at != null ? info.at : Date.now();
    if (info.label !== undefined) _label = info.label;
    _paint();
  }
  function tick() { _paint(); } // refresh the "Xs ago" text without a new fetch

  _paint();
  return { el, set, tick, get state() { return _state; } };
}

// poll(endpoint, intervalMs, onData, opts) -> handle { stop(), refresh(), badge, lastMeta }
// opts:
//   badge        (badge object from createBadge, or true to auto-create) — kept in sync
//   onState(meta)         optional state-change callback (live/degraded/missing/error)
//   degradedField         field name treated as the degraded flag (default "degraded")
//   fetchInit             passed to fetch() (headers, signal, ...)
//   tickBadgeMs           how often to refresh the badge "Xs ago" (default 1000)
//   immediate             fetch once immediately (default true)
export function poll(endpoint, intervalMs, onData, opts = {}) {
  if (!endpoint) throw new Error("szl3d.poll: endpoint required");
  const interval = Math.max(250, intervalMs || 5000);
  const degradedField = opts.degradedField || "degraded";
  let badge = opts.badge === true ? createBadge() : (opts.badge || null);
  let _timer = 0, _badgeTimer = 0, _stopped = false;
  let lastMeta = { state: LIVE_STATES.INIT, label: null, status: 0, at: null, error: null };

  function _emitState(meta) {
    lastMeta = meta;
    if (badge) badge.set(meta.state, { label: meta.label, at: meta.at });
    if (typeof opts.onState === "function") { try { opts.onState(meta); } catch (_) {} }
  }

  async function _fetchOnce() {
    if (_stopped) return;
    try {
      const res = await fetch(endpoint, Object.assign({ headers: { "accept": "application/json" } }, opts.fetchInit || {}));
      if (res.status === 404) {
        _emitState({ state: LIVE_STATES.MISSING, label: null, status: 404, at: lastMeta.at, error: null });
        return;
      }
      if (!res.ok) {
        _emitState({ state: LIVE_STATES.ERROR, label: null, status: res.status, at: lastMeta.at, error: "http " + res.status });
        return;
      }
      let json;
      try { json = await res.json(); }
      catch (e) {
        _emitState({ state: LIVE_STATES.ERROR, label: null, status: res.status, at: lastMeta.at, error: "bad json" });
        return;
      }
      const degraded = !!(json && json[degradedField]);
      const label = readHonestyLabel(json);
      const at = Date.now();
      const meta = {
        state: degraded ? LIVE_STATES.DEGRADED : LIVE_STATES.LIVE,
        label, status: res.status, at, error: null, degraded,
      };
      _emitState(meta);
      // Call onData even when degraded so callers can render the honest partial state;
      // they branch on meta.state / meta.degraded. We never swallow the payload.
      if (typeof onData === "function") { try { onData(json, meta); } catch (e) { if (console) console.error("[szl3d] onData threw:", e); } }
    } catch (e) {
      _emitState({ state: LIVE_STATES.ERROR, label: null, status: 0, at: lastMeta.at, error: (e && e.message) || String(e) });
    }
  }

  function _schedule() {
    if (_stopped) return;
    _timer = (typeof setTimeout !== "undefined") ? setTimeout(async () => { await _fetchOnce(); _schedule(); }, interval) : 0;
  }

  function stop() {
    _stopped = true;
    if (_timer) clearTimeout(_timer);
    if (_badgeTimer) clearInterval(_badgeTimer);
    _timer = 0; _badgeTimer = 0;
  }
  function refresh() { return _fetchOnce(); }

  if (badge && typeof setInterval !== "undefined") {
    _badgeTimer = setInterval(() => { if (!_stopped) badge.tick(); }, opts.tickBadgeMs || 1000);
  }

  if (opts.immediate !== false) { _fetchOnce().then(_schedule); }
  else { _schedule(); }

  return {
    stop, refresh, badge,
    get lastMeta() { return lastMeta; },
    get endpoint() { return endpoint; },
  };
}

export default { poll, createBadge, readHonestyLabel, LIVE_STATES };
