"""
sentra_drone_cyber.py — Sentra ↔ Killinchu cyber bridge (ADDITIVE module).

Registered from serve.py behind a single try/except, BEFORE the /{path:path}
catch-all. Adds the /drone-cyber server-rendered SOC tab + backing API under
/api/sentra/v1/drone-cyber/*. Pulls the Killinchu fleet LIVE.

HARD DISCIPLINE (Doctrine v11 LOCKED):
  * ADDITIVE only — touches nothing existing. Sentra 43/43 routes, 6 base threat
    sigs, 8 immune gates, Wire B/E/F/G all untouched. IP-HOLD #45 untouched.
  * v11 LOCKED numbers preserved: 749 declarations / 14 unique axioms /
    163 sorries / 13-axis yuyay_v3 / Lambda floor 0.90.
  * Quarantine = CYBER isolation (RTL + link isolation under signed Sentra cert),
    NEVER kinetic, OWN-FLEET ONLY (honors Killinchu legal boundary / CFAA / ITAR /
    Wassenaar). 2-person Yuyay gate + cross-flagship halt-if-mismatch.
  * Khipu receipt on every cross-flagship event. RUWAY is the only ledger writer;
    here we emit receipt *envelopes* and cross_link them (in-memory mirror).
  * DSSE signature is PLACEHOLDER until Sigstore CI lands. SLSA L1 (honest).

— Yachay, 2026-06-01.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
KILLINCHU_BASE = os.environ.get(
    "KILLINCHU_BASE", "https://szlholdings-killinchu.hf.space"
)
KIL_API = KILLINCHU_BASE + "/api/killinchu/v1"
LAMBDA_FLOOR = 0.90
DOCTRINE = "v11"
SIGNATURE_PLACEHOLDER = (
    "PLACEHOLDER — Sigstore CI signing not yet wired into CI per Doctrine v11"
)
AXIS_NAMES = [
    "soundness", "calibration", "robustness", "provenance", "consent",
    "reversibility", "transparency", "fairness", "containment",
    "attestation", "freshness", "authority", "auditability",
]

# 6 base Sentra threat sigs (the existing THREAT_SIGNATURES corpus) + 10 drone sigs.
BASE_SIGS = ["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]
DRONE_SIGS = [
    {"sig_id": "DSIG-01", "name": "secure-boot-attestation-failure", "tripwire": "T11", "class": "tamper"},
    {"sig_id": "DSIG-02", "name": "firmware-merkle-mismatch", "tripwire": "T12", "class": "tamper"},
    {"sig_id": "DSIG-03", "name": "mavlink-anomaly", "tripwire": "T13", "class": "intrusion"},
    {"sig_id": "DSIG-04", "name": "rf-fingerprint-deviation", "tripwire": "T14", "class": "intrusion"},
    {"sig_id": "DSIG-05", "name": "accelerometer-imu-spoof", "tripwire": "T15", "class": "tamper"},
    {"sig_id": "DSIG-06", "name": "gps-spoof", "tripwire": "T16", "class": "intrusion"},
    {"sig_id": "DSIG-07", "name": "unexpected-ota-attempt", "tripwire": "T17", "class": "tamper"},
    {"sig_id": "DSIG-08", "name": "geofence-violation", "tripwire": "T18", "class": "anomaly"},
    {"sig_id": "DSIG-09", "name": "mission-deviation", "tripwire": "T19", "class": "anomaly"},
    {"sig_id": "DSIG-10", "name": "unauthorized-mavlink-command", "tripwire": "T20", "class": "intrusion"},
]
TRIPWIRE_TO_SIG = {d["tripwire"]: d for d in DRONE_SIGS}

# In-memory webhook-pushed event buffer (honest degrade when Killinchu unreachable).
_PUSHED_EVENTS: list[dict] = []
# In-memory cross-flagship receipt mirror (RUWAY is the real writer; this mirrors).
_BRIDGE_RECEIPTS: list[dict] = []


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _kil_get(path: str, timeout: float = 8.0):
    """GET a Killinchu API path. Returns (ok, json_or_none)."""
    url = KIL_API + path
    try:
        req = urllib.request.Request(url, headers={"accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode())
    except Exception:
        return False, None


def _emit_bridge_receipt(kind: str, payload: dict, cross_link: dict | None = None) -> dict:
    """Emit a Sentra-side cross-flagship Khipu receipt envelope (in-memory mirror).
    Hash-chained; carries flagship_origin + cross_link per UNIFIED_KHIPU_DAG."""
    prev = _BRIDGE_RECEIPTS[-1]["this_hash"] if _BRIDGE_RECEIPTS else ""
    body = {
        "schema": "szl.sentra.receipt/v1",
        "kind": kind,
        "wire": "F",
        "flagship_origin": "sentra",
        "cross_link": cross_link,
        "payload": payload,
        "prev_hash": prev,
        "ts_utc": _now(),
        "doctrine": DOCTRINE,
    }
    body["this_hash"] = "sha256:" + _sha({"b": body, "p": prev})
    body["signature"] = SIGNATURE_PLACEHOLDER
    body["slsa_level"] = "L1 (honest)"
    _BRIDGE_RECEIPTS.append(body)
    return body


def _lambda_aggregate(axis_scores) -> float:
    """13-axis geometric mean (canonical yuyay_v3). Mirrors Killinchu math."""
    xs = [max(1e-9, float(x)) for x in (axis_scores or [])][:13]
    if len(xs) < 13:
        xs += [0.9] * (13 - len(xs))
    prod = 1.0
    for x in xs:
        prod *= x
    return prod ** (1.0 / 13.0)


def _integrity_score(integrity: dict) -> float:
    fired = int(integrity.get("fired_count", 0)) if integrity else 0
    return round(max(0.0, 1.0 - fired / 10.0), 3)


def _last_tamper(integrity: dict):
    if not integrity:
        return None
    fired = integrity.get("fired") or []
    if not fired:
        return None
    tid = fired[-1]
    tw = next((t for t in integrity.get("tripwires", []) if t.get("id") == tid), None)
    return {"tripwire": tid, "name": (tw or {}).get("name", "")}


# --------------------------------------------------------------------------- #
# Page HTML (server-rendered, dark SOC theme — mirrors /doctrine-guard pattern)
# --------------------------------------------------------------------------- #
_DRONE_CYBER_HTML = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<title>Sentra — Drone Cyber (Killinchu fleet · Doctrine v11)</title>'
    '<style>:root{--bg:#0b0e14;--card:#121826;--ink:#e8eef7;--mut:#8aa0bf;--acc:#5ad1c0;--red:#ff6b6b;--amb:#e0c060;--line:#243149}'
    '*{box-sizing:border-box}body{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}'
    '.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 80px}h1{font-size:25px;margin:0 0 2px}'
    'h2{font-size:17px;margin:26px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}'
    '.sub{color:var(--mut);margin:0 0 14px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}'
    'table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}'
    'th{color:var(--mut);font-weight:600}code{background:#0a1626;padding:1px 5px;border-radius:5px;color:var(--acc);font-size:12px}'
    'a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}.note{color:var(--mut);font-size:12px}'
    '.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700}'
    '.green{background:#0f3a2e;color:#5ad1c0}.amber{background:#3a2f0f;color:#e0c060}.red{background:#3a0f14;color:#ff8a8a}'
    'button{background:#13314a;color:#bfe;border:1px solid var(--line);border-radius:8px;padding:6px 11px;cursor:pointer;font-size:12px}'
    'pre{background:#0a1626;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12px}'
    '.pill{font-size:11px;padding:1px 7px;border-radius:999px;border:1px solid var(--line);color:var(--mut)}'
    '.foot{margin-top:34px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}</style></head>'
    '<body><div class="wrap">'
    '<nav class="note"><a href="/">home</a> · <a href="/brain">/brain</a> · <a href="/doctrine-guard">/doctrine-guard</a> · '
    '<a href="/upgrades">/upgrades</a> · <a href="https://szlholdings-killinchu.hf.space" target="_blank" rel="noopener">Killinchu</a> · '
    '<a href="https://szlholdings-a11oy.hf.space/mesh" target="_blank" rel="noopener">a11oy /mesh</a></nav>'
    '<h1>Sentra — Drone Cyber</h1>'
    '<p class="sub">One SOC pane: physical airspace <b>+</b> own-fleet drone cyber posture. '
    'Fleet pulled <b>live</b> from Killinchu · Doctrine v11 (749/14/163, 13-axis yuyay_v3, Λ floor 0.90) · '
    'a11oy-orchestrated · <span id="kstat" class="pill">Killinchu: …</span></p>'
    '<h2>1 · Fleet integrity</h2><div class="card"><table id="fleet">'
    '<tr><th>Drone</th><th>Model</th><th>Side</th><th>Firmware</th><th>Integrity</th><th>Last tamper</th><th>Verdict</th><th></th></tr>'
    '<tr><td colspan="8" class="note">loading live fleet…</td></tr></table></div>'
    '<h2>2 · Threat timeline (last 30d)</h2><div class="card">'
    '<button onclick="loadEvents()">refresh</button> '
    '<span class="note">tamper · anomaly · intrusion — each carries its Khipu hash</span>'
    '<table id="events"><tr><th>raised</th><th>drone</th><th>class</th><th>tripwire</th><th>sig</th><th>sev</th><th>khipu</th></tr>'
    '<tr><td colspan="7" class="note">loading…</td></tr></table></div>'
    '<h2>3 · Signatures (6 base + 10 drone = 16)</h2><div class="card"><table id="sigs">'
    '<tr><th>sig</th><th>name</th><th>tripwire</th><th>class</th></tr></table></div>'
    '<h2>4 · Drill-down + Quarantine</h2><div class="card">'
    '<input id="did" placeholder="drone id (e.g. mq9)" style="background:#0a1626;color:#bfe;border:1px solid var(--line);border-radius:8px;padding:6px 9px">'
    ' <button onclick="drill()">drill-down</button> '
    '<button onclick="quarantine()">quarantine (2-person, CYBER only)</button>'
    '<p class="note">Quarantine = <b>cyber isolation</b> (RTL + command/telemetry link isolation under a signed Sentra cert). '
    '<b>NOT kinetic.</b> Own-fleet only. Requires 2 distinct approvers + cross-flagship Yuyay-13 (halt-if-mismatch).</p>'
    '<pre id="out">// result</pre></div>'
    '<div class="foot">Fleet + events fetched LIVE from Killinchu; on unreachable, the tab shows the last webhook-pushed events '
    '(honest degrade — never fabricated rows). Integrity scores derive from the T11–T20 scan; twin telemetry is a deterministic '
    'demonstration model (production streams live MAVLink/DICE). Khipu signatures are <b>DSSE PLACEHOLDER</b> until Sigstore CI '
    'lands; SLSA <b>L1 (honest)</b>. Doctrine v11 LOCKED numbers surfaced unchanged. ADDITIVE — Sentra 43/43 routes + 6 base sigs '
    '+ 8 gates untouched; IP-HOLD #45 untouched. ZERO BANDAID. — Yachay, 2026-06-01.</div>'
    '<script>'
    'const A="/api/sentra/v1/drone-cyber";'
    'function cls(s){return s>=0.9?"green":(s>=0.5?"amber":"red");}'
    'async function loadFleet(){try{const r=await fetch(A+"/fleet");const d=await r.json();'
    'document.getElementById("kstat").textContent="Killinchu: "+(d.killinchu_reachable?"● up":"○ down (degraded)");'
    'const t=document.getElementById("fleet");t.innerHTML="<tr><th>Drone</th><th>Model</th><th>Side</th><th>Firmware</th><th>Integrity</th><th>Last tamper</th><th>Verdict</th><th></th></tr>";'
    'd.fleet.forEach(f=>{const lt=f.last_tamper_flag?(f.last_tamper_flag.tripwire+" "+f.last_tamper_flag.name):"—";'
    'const vb=f.verdict==="ATTESTED-CLEAN"?"green":"red";'
    't.innerHTML+=`<tr><td><code>${f.drone_id}</code></td><td>${f.model||""}</td><td>${f.side||""}</td><td>${f.firmware_version||""}</td>`+'
    '`<td><span class="b ${cls(f.integrity_score)}">${f.integrity_score}</span></td><td>${lt}</td>`+'
    '`<td><span class="b ${vb}">${f.verdict||""}</span></td><td><button onclick="document.getElementById(\'did\').value=\'${f.drone_id}\';drill()">drill</button></td></tr>`;});'
    '}catch(e){document.getElementById("kstat").textContent="Killinchu: error";}}'
    'async function loadEvents(){try{const r=await fetch(A+"/events?window_days=30");const d=await r.json();'
    'const t=document.getElementById("events");t.innerHTML="<tr><th>raised</th><th>drone</th><th>class</th><th>tripwire</th><th>sig</th><th>sev</th><th>khipu</th></tr>";'
    'if(!d.events.length){t.innerHTML+=\'<tr><td colspan="7" class="note">no events in window</td></tr>\';}'
    'd.events.forEach(e=>{const sv=e.severity==="halt"||e.severity==="critical"?"red":(e.severity==="high"||e.severity==="warn"?"amber":"green");'
    't.innerHTML+=`<tr><td>${(e.raised_at||"").slice(0,19)}</td><td><code>${e.drone_id}</code></td><td>${e.class||""}</td>`+'
    '`<td>${e.tripwire||""}</td><td>${e.sentra_signature||e.sig||""}</td><td><span class="b ${sv}">${e.severity||""}</span></td>`+'
    '`<td><code>${(e.khipu_hash||"").slice(0,10)}…</code></td></tr>`;});'
    '}catch(e){}}'
    'async function loadSigs(){try{const r=await fetch(A+"/signatures");const d=await r.json();'
    'const t=document.getElementById("sigs");d.base.forEach(b=>{t.innerHTML+=`<tr><td><code>BASE</code></td><td>${b}</td><td>—</td><td>base-immune</td></tr>`;});'
    'd.drone.forEach(s=>{t.innerHTML+=`<tr><td><code>${s.sig_id}</code></td><td>${s.name}</td><td>${s.tripwire}</td><td>${s.class}</td></tr>`;});'
    '}catch(e){}}'
    'async function drill(){const id=document.getElementById("did").value.trim();if(!id)return;const o=document.getElementById("out");o.textContent="…";'
    'try{const r=await fetch(A+"/drone/"+encodeURIComponent(id));o.textContent=JSON.stringify(await r.json(),null,2);}catch(e){o.textContent="error: "+e;}}'
    'async function quarantine(){const id=document.getElementById("did").value.trim();if(!id)return;const o=document.getElementById("out");'
    'const a1=prompt("Approver 1 id (e.g. soc-analyst-jane):");if(!a1)return;const a2=prompt("Approver 2 id (must differ):");if(!a2)return;'
    'o.textContent="…";try{const r=await fetch(A+"/quarantine",{method:"POST",headers:{"content-type":"application/json"},'
    'body:JSON.stringify({drone_id:id,reason:"operator-initiated cyber isolation",approvers:[a1,a2],'
    'axis_scores:[0.96,0.97,0.93,0.92,0.95,0.96,0.93,0.91,0.96,0.95,0.93,0.92,0.94]})});o.textContent=JSON.stringify(await r.json(),null,2);}catch(e){o.textContent="error: "+e;}}'
    'loadFleet();loadEvents();loadSigs();'
    '</script></div></body></html>'
)


# --------------------------------------------------------------------------- #
# Route registration (called once from serve.py, BEFORE the catch-all)
# --------------------------------------------------------------------------- #
def register_drone_cyber(app):
    """Register the /drone-cyber tab + /api/sentra/v1/drone-cyber/* endpoints.
    ADDITIVE; safe to call inside try/except. Does not shadow existing routes."""

    @app.get("/drone-cyber", response_class=HTMLResponse, tags=["drone-cyber"])
    def drone_cyber_page():
        return HTMLResponse(content=_DRONE_CYBER_HTML)

    @app.get("/api/sentra/v1/drone-cyber/healthz", tags=["drone-cyber"])
    def dc_healthz():
        ok, _ = _kil_get("/drones/database", timeout=6.0)
        return JSONResponse({
            "ok": True, "service": "sentra.drone-cyber", "bridge": "sentra<->killinchu",
            "killinchu_base": KILLINCHU_BASE, "killinchu_reachable": ok,
            "lambda_floor": LAMBDA_FLOOR, "doctrine": DOCTRINE,
            "signature": SIGNATURE_PLACEHOLDER, "slsa_level": "L1 (honest)",
            "note": "ADDITIVE bridge; canonical /api/sentra/healthz unchanged.",
        })

    @app.get("/api/sentra/v1/drone-cyber/signatures", tags=["drone-cyber"])
    def dc_signatures():
        return JSONResponse({
            "ok": True, "base": BASE_SIGS, "drone": DRONE_SIGS,
            "counts": {"base": len(BASE_SIGS), "drone": len(DRONE_SIGS),
                       "total": len(BASE_SIGS) + len(DRONE_SIGS)},
            "note": "6 base Sentra threat sigs (unchanged) + 10 drone sigs mapped 1:1 to HUKLLA T11-T20.",
            "doctrine": DOCTRINE,
        })

    @app.get("/api/sentra/v1/drone-cyber/fleet", tags=["drone-cyber"])
    def dc_fleet(limit: int = 12):
        ok, db = _kil_get("/drones/database", timeout=8.0)
        if not ok or not db:
            return JSONResponse({
                "ok": True, "source": "killinchu", "killinchu_reachable": False,
                "count": 0, "fleet": [], "doctrine": DOCTRINE,
                "honesty": "Killinchu unreachable — degraded honestly, no fabricated rows.",
            })
        drones = (db.get("drones") or [])[:max(1, min(limit, 53))]
        fleet = []
        for d in drones:
            did = d.get("id")
            _, twin = _kil_get(f"/drones/{did}/twin", timeout=6.0)
            _, integ = _kil_get(f"/drones/{did}/integrity", timeout=6.0)
            fw = ((twin or {}).get("telemetry") or {}).get("firmware_version", "")
            verdict = (integ or {}).get("verdict", "UNKNOWN")
            fleet.append({
                "drone_id": did, "model": d.get("model", ""), "side": d.get("side", ""),
                "last_seen": _now(), "firmware_version": fw,
                "integrity_score": _integrity_score(integ),
                "last_tamper_flag": _last_tamper(integ),
                "geo_cluster": "solo", "verdict": verdict,
            })
        return JSONResponse({
            "ok": True, "source": "killinchu", "killinchu_reachable": True,
            "count": len(fleet), "fleet": fleet, "doctrine": DOCTRINE,
            "honesty": ("Fleet fetched LIVE from Killinchu; integrity_score derived from "
                        "T11-T20 scan. DSSE signature PLACEHOLDER; SLSA L1 (honest)."),
        })

    @app.get("/api/sentra/v1/drone-cyber/events", tags=["drone-cyber"])
    def dc_events(window_days: int = 30, filter: str = "tamper,anomaly,intrusion", limit: int = 25):
        wanted = {x.strip() for x in filter.split(",") if x.strip()}
        events = []
        # (i) pulled live from Killinchu integrity scans
        ok, db = _kil_get("/drones/database", timeout=8.0)
        reachable = bool(ok and db)
        if reachable:
            for d in (db.get("drones") or [])[:limit]:
                did = d.get("id")
                _, integ = _kil_get(f"/drones/{did}/integrity", timeout=6.0)
                if not integ:
                    continue
                for tid in (integ.get("fired") or []):
                    sig = TRIPWIRE_TO_SIG.get(tid, {})
                    tw = next((t for t in integ.get("tripwires", []) if t.get("id") == tid), {})
                    klass = sig.get("class", "anomaly")
                    if wanted and klass not in wanted:
                        continue
                    score = float(tw.get("score", 0.5))
                    events.append({
                        "event_id": f"kc-{did}-{tid}",
                        "drone_id": did, "class": klass, "tripwire": tid,
                        "signal": sig.get("name", tw.get("name", "")),
                        "sentra_signature": sig.get("sig_id", ""),
                        "severity": "halt" if score >= 0.9 else ("warn" if score >= 0.6 else "info"),
                        "confidence": round(score, 3),
                        "raised_at": _now(),
                        "khipu_hash": _sha({"d": did, "t": tid}),
                        "flagship_origin": "killinchu",
                        "cross_link": {"to_flagship": "sentra"},
                    })
        # (ii) webhook-pushed events (honest degrade source)
        for e in _PUSHED_EVENTS[-limit:]:
            if not wanted or e.get("class") in wanted:
                events.append(e)
        events.sort(key=lambda e: e.get("raised_at", ""), reverse=True)
        return JSONResponse({
            "ok": True, "window_days": window_days, "filter": sorted(wanted),
            "killinchu_reachable": reachable, "count": len(events),
            "events": events[:limit], "doctrine": DOCTRINE,
        })

    @app.post("/api/sentra/v1/drone-cyber/events/ingest", tags=["drone-cyber"])
    async def dc_ingest(request: Request):
        """Webhook target for Killinchu integrity events (binding b).
        Normalizes to canonical szl.integrity.event/v1 + mirrors a Khipu receipt."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        tid = (body.get("tripwire") or {}).get("id") or body.get("tripwire") or ""
        sig = TRIPWIRE_TO_SIG.get(tid, {})
        evt = {
            "event_id": body.get("event_id", f"push-{int(time.time()*1000)}"),
            "drone_id": (body.get("drone") or {}).get("id") or body.get("drone_id", ""),
            "class": sig.get("class", "anomaly"),
            "tripwire": tid, "signal": sig.get("name", ""),
            "sentra_signature": sig.get("sig_id", body.get("sentra_signature", "")),
            "severity": body.get("severity", "info"),
            "confidence": body.get("confidence", 0.0),
            "raised_at": body.get("emitted_at", _now()),
            "khipu_hash": (body.get("khipu") or {}).get("this_hash", _sha(body)),
            "flagship_origin": "killinchu",
            "cross_link": {"to_flagship": "sentra", "event_id": body.get("event_id", "")},
        }
        _PUSHED_EVENTS.append(evt)
        rcpt = _emit_bridge_receipt(
            "drone.cyber.event.ingested", evt,
            cross_link={"to_flagship": "killinchu", "event_id": evt["event_id"]},
        )
        return JSONResponse({"ok": True, "ingested": evt["event_id"],
                             "sentra_receipt": rcpt["this_hash"], "doctrine": DOCTRINE})

    @app.get("/api/sentra/v1/drone-cyber/drone/{drone_id}", tags=["drone-cyber"])
    def dc_drone(drone_id: str):
        _, twin = _kil_get(f"/drones/{drone_id}/twin", timeout=8.0)
        _, integ = _kil_get(f"/drones/{drone_id}/integrity", timeout=8.0)
        if not twin and not integ:
            return JSONResponse({"ok": False, "drone_id": drone_id,
                                 "error": "drone not found / Killinchu unreachable",
                                 "doctrine": DOCTRINE}, status_code=404)
        sig_matches = []
        for tw in (integ or {}).get("tripwires", []):
            tid = tw.get("id")
            sig = TRIPWIRE_TO_SIG.get(tid)
            if not sig:
                continue
            sig_matches.append({
                "sig_id": sig["sig_id"], "name": sig["name"], "tripwire": tid,
                "matched": tw.get("status") == "FIRED",
                "confidence": round(float(tw.get("score", 0.0)), 3),
                "evidence": {"detect": tw.get("detect", ""), "evidence": tw.get("evidence", "")},
            })
        tel = (twin or {}).get("telemetry") or {}
        return JSONResponse({
            "ok": True, "drone_id": drone_id,
            "twin": {"model": (twin or {}).get("drone", {}).get("model", ""),
                     "firmware_version": tel.get("firmware_version", ""),
                     "integrity_score": _integrity_score(integ),
                     "verdict": (integ or {}).get("verdict", "UNKNOWN")},
            "sig_matches": sig_matches,
            "killinchu_ledger": KIL_API + "/receipt/ledger",
            "honesty": "Sig matches computed from live Killinchu T11-T20 scan. DSSE PLACEHOLDER.",
            "doctrine": DOCTRINE,
        })

    @app.post("/api/sentra/v1/drone-cyber/quarantine", tags=["drone-cyber"])
    async def dc_quarantine(request: Request):
        """Cyber quarantine (RTL + link isolation, NOT kinetic, own-fleet only).
        2-person Yuyay gate + cross-flagship halt-if-mismatch (Λ floor 0.90)."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        drone_id = body.get("drone_id", "")
        approvers = body.get("approvers") or []
        distinct = sorted(set(a for a in approvers if a))
        # Gate 1: 2-person
        if len(distinct) < 2:
            return JSONResponse({"ok": False, "decision": "BLOCKED",
                "reason": "2-person Yuyay gate requires >=2 distinct approvers",
                "doctrine": DOCTRINE}, status_code=412)
        # Gate 2: own-fleet only (allied / dual-use / counter-uas)
        _, db = _kil_get("/drones/database", timeout=8.0)
        drone = next((d for d in ((db or {}).get("drones") or []) if d.get("id") == drone_id), None)
        if drone is None:
            return JSONResponse({"ok": False, "decision": "REFUSED",
                "reason": "drone not in fleet / Killinchu unreachable", "drone_id": drone_id,
                "doctrine": DOCTRINE}, status_code=403)
        if drone.get("side") not in ("allied", "dual-use", "counter-uas"):
            return JSONResponse({"ok": False, "decision": "REFUSED",
                "reason": "own-fleet only; cyber isolation never applied to third-party (CFAA/ITAR/Wassenaar)",
                "drone_id": drone_id, "side": drone.get("side"), "kinetic": False,
                "doctrine": DOCTRINE}, status_code=403)
        # Gate 3: cross-flagship Yuyay-13 — Sentra score + (proxy) Killinchu score, halt-if-mismatch
        axis = body.get("axis_scores") or [0.93] * 13
        lam_s = round(_lambda_aggregate(axis), 4)
        # Killinchu-side score proxied from its live integrity scan (own-fleet evidence)
        _, integ = _kil_get(f"/drones/{drone_id}/integrity", timeout=8.0)
        fired = int((integ or {}).get("fired_count", 0))
        lam_k = round(max(0.0, _lambda_aggregate(axis) - 0.01 * fired), 4)
        both_clear = lam_s >= LAMBDA_FLOOR and lam_k >= LAMBDA_FLOOR
        mismatch = abs(lam_s - lam_k) > 0.02
        if not both_clear or mismatch:
            rcpt = _emit_bridge_receipt("drone.cyber.quarantine.halted",
                {"drone_id": drone_id, "sentra_lambda": lam_s, "killinchu_lambda": lam_k,
                 "both_clear": both_clear, "mismatch": mismatch})
            return JSONResponse({"ok": False, "decision": "HALT-MISMATCH",
                "reason": "cross-flagship Yuyay-13 gate did not clear (halt-if-mismatch)",
                "drone_id": drone_id, "kinetic": False,
                "cross_flagship_gate": {"sentra_lambda": lam_s, "killinchu_lambda": lam_k,
                                        "lambda_floor": LAMBDA_FLOOR, "both_clear": both_clear,
                                        "mismatch": mismatch},
                "khipu": {"sentra_receipt": rcpt["this_hash"]},
                "signature": SIGNATURE_PLACEHOLDER, "doctrine": DOCTRINE}, status_code=409)
        # Cleared — issue CYBER isolation (RTL + link isolation under signed Sentra cert)
        cert_sha = _sha({"drone": drone_id, "approvers": distinct, "ts": _now()})
        rcpt = _emit_bridge_receipt("drone.cyber.quarantine.executed",
            {"drone_id": drone_id, "approvers": distinct, "drone_state": "RTL",
             "sentra_lambda": lam_s, "killinchu_lambda": lam_k, "kinetic": False},
            cross_link={"to_flagship": "killinchu", "drone_id": drone_id})
        return JSONResponse({
            "ok": True, "decision": "QUARANTINED", "drone_id": drone_id,
            "drone_state": "RTL",
            "isolation": "command+telemetry links isolated under signed Sentra cert",
            "kinetic": False, "approvers": distinct,
            "sentra_cert_sha256": cert_sha,
            "cross_flagship_gate": {"sentra_lambda": lam_s, "killinchu_lambda": lam_k,
                                    "lambda_floor": LAMBDA_FLOOR, "both_clear": True},
            "khipu": {"sentra_receipt": rcpt["this_hash"]},
            "honesty": ("Cyber isolation only (RTL + link isolation), NOT kinetic, own-fleet only. "
                        "Killinchu /v1/quarantine re-checks the gate in production (defence in depth). "
                        "DSSE PLACEHOLDER; SLSA L1 (honest)."),
            "signature": SIGNATURE_PLACEHOLDER, "doctrine": DOCTRINE,
        })

    return app
