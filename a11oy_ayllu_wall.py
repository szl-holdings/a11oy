# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""
a11oy Ayllu council wall — GET /api/ayllu/wall (JSON) + GET /ayllu/wall (HTML)

The public verify-then-display surface for AYLLU council decisions.
Doctrine: provenance, not vibes. Every decision shown here is re-verified
SERVER-SIDE on every request from the DSSE-signed council receipts COMMITTED
to the a11oy GitHub repository (`ayllu/decisions/`). Receipt BYTES are cached
briefly to spare raw.githubusercontent.com; the cryptographic verification
itself runs on every request and is never cached or skipped.

Per decision, the band FAILS CLOSED unless ALL of:
  - the DSSE envelope's ECDSA-P256-SHA256 signature verifies over the DSSE PAE
    (`DSSEv1 SP len(type) SP type SP len(body) SP body`) against the PINNED
    council runtime public key committed at `ayllu/keys/` in the same repo;
  - the payload's `payload_digest` reproduces byte-exactly from the canonical
    JSON (sorted keys, compact separators) of the payload `body`;
  - the receipt's `receipt_id` equals the chain receipt id in the body.

KEY HONESTY (do not soften this):
  The envelopes carry keyid "szlholdings-cosign", but the runtime signing key
  in the a11oy Space does NOT match the published org key at
  szl-holdings/.github/cosign.pub (verified 2026-07-21; the live
  /api/a11oy/v1/verify/receipt reports the same MISMATCH). The actual
  verifying public key was recovered from two independent live signatures
  (ECDSA public-key recovery, unique common candidate) and is PINNED in-repo
  with that provenance stated. Owner reconciliation of the secret vs the
  published cosign.pub is still pending — this wall verifies against the
  pinned RUNTIME key and says exactly that.

Optional env pin: A11OY_COUNCIL_PUB_SHA256 = sha256 hex of the pinned PEM
bytes. Set-but-different → keyTrust "PIN_MISMATCH" and the wall FAILS CLOSED.
Unset → "REPO_DECLARED". Matching → "PINNED".

Additive module per Space convention: register(app) adds routes and
front-moves them so exact paths win over the SPA history fallback. No new
dependencies (httpx + cryptography are pinned in the image).
"""

import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

_API_ROUTE = "/api/ayllu/wall"
_PAGE_ROUTE = "/ayllu/wall"
_RAW = "https://raw.githubusercontent.com/szl-holdings/a11oy/main"
_INDEX_PATH = "ayllu/decisions/index.json"
_KEY_PATH = "ayllu/keys/council-runtime-2026-07-21.pub"
_PIN_ENV = "A11OY_COUNCIL_PUB_SHA256"
_CACHE_TTL_SECONDS = 300  # bytes only; verification always re-runs
_MAX_DECISIONS = 24

# path -> {"at": epoch, "data": bytes}
_byte_cache: dict = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _pae(payload_type: str, body: bytes) -> bytes:
    t = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(body), body)


async def _fetch(client: httpx.AsyncClient, path: str) -> bytes:
    cached = _byte_cache.get(path)
    if cached and (time.time() - cached["at"]) < _CACHE_TTL_SECONDS:
        return cached["data"]
    resp = await client.get(f"{_RAW}/{path}")
    resp.raise_for_status()
    _byte_cache[path] = {"at": time.time(), "data": resp.content}
    return resp.content


def _runtime_key_state(pinned_pem: bytes) -> dict:
    """Honest, guarded check: does the CURRENT process signing secret match the
    pinned public key? Never raises; never exposes private material."""
    try:
        import szl_dsse as _dsse  # type: ignore
        priv = _dsse._load_private_key()
        if priv is None:
            return {"state": "RUNTIME_SIGNER_ABSENT",
                    "note": "no signing secret in this runtime; new decisions would be honestly UNSIGNED"}
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat)
        cur = priv.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        if cur.strip() == pinned_pem.strip():
            return {"state": "ENV_SIGNER_MATCHES_PIN",
                    "note": "the szl_dsse env-secret-derived key equals the pinned council key"}
        return {"state": "ENV_SIGNER_DIFFERS_FROM_PIN",
                "note": "this probe compares ONLY the szl_dsse env-secret-derived key with "
                        "the pin; live council receipts have empirically verified against "
                        "the pin across a Space rebuild (see the committed post-rebuild "
                        "continuity decision), so the council's effective signer is a "
                        "persistent key, not this env secret. Trust the per-decision "
                        "verification above — it is the empirical check."}
    except Exception as exc:
        return {"state": "UNKNOWN", "note": f"{type(exc).__name__}: could not compare"}


def _verify_decision(doc: dict, public_key, pinned_fpr: str) -> dict:
    """All checks for one committed council decision. Fail-closed."""
    checks = {}
    env = doc.get("receipt") or {}
    payload_b64 = env.get("payload") or ""
    payload_type = env.get("payloadType") or ""
    sigs = env.get("signatures") or []
    payload_bytes = b""
    payload = {}
    try:
        payload_bytes = base64.b64decode(payload_b64, validate=True)
        payload = json.loads(payload_bytes)
        checks["payloadDecodes"] = True
    except Exception:
        checks["payloadDecodes"] = False
    sig_ok = False
    if checks.get("payloadDecodes") and sigs:
        try:
            public_key.verify(
                base64.b64decode(sigs[0].get("sig", ""), validate=True),
                _pae(payload_type, payload_bytes),
                ec.ECDSA(hashes.SHA256()),
            )
            sig_ok = True
        except Exception:
            sig_ok = False
    checks["ecdsaSignatureVerifiesOverPae"] = sig_ok
    body = payload.get("body") if isinstance(payload, dict) else None
    checks["payloadDigestReproduces"] = (
        isinstance(body, dict)
        and payload.get("payload_digest") == _sha256_hex(_canonical(body))
    )
    chain = (body or {}).get("chain") or {}
    checks["receiptIdMatchesChain"] = (
        payload.get("receipt_id") is not None
        and payload.get("receipt_id") == chain.get("receipt_id")
    )
    verified = all(checks.values())
    return {
        "verified": verified,
        "status": "DECISION_RECEIPT_VERIFIED" if verified else "DECISION_RECEIPT_FAILED",
        "checks": checks,
        "keyid_label": (sigs[0].get("keyid") if sigs else None),
        "verifyingKeyFingerprintSha256": pinned_fpr,
        "signedAt": env.get("_signed_at"),
        "derived": {
            # DERIVED from the verified payload — never hand-typed.
            "councilId": (body or {}).get("council_id"),
            "receiptId": payload.get("receipt_id") if isinstance(payload, dict) else None,
            "participants": (body or {}).get("participants"),
            "mode": (body or {}).get("mode"),
            "models": (body or {}).get("models"),
            "decisionState": (body or {}).get("decision_state"),
            "evidenceState": (body or {}).get("evidence_state"),
            "promptSha256": (body or {}).get("prompt_sha256"),
            "humanCheckpoint": (body or {}).get("human_checkpoint"),
            "chainSeq": chain.get("seq"),
        } if verified else None,
    }


async def _wall_payload() -> dict:
    decisions = []
    key_meta: dict = {}
    error = None
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            pem = await _fetch(client, _KEY_PATH)
            pinned_fpr = _sha256_hex(pem)
            pin = os.environ.get(_PIN_ENV, "").strip()
            if not pin:
                key_trust, pin_ok = "REPO_DECLARED", True
            elif pin.lower() == pinned_fpr:
                key_trust, pin_ok = "PINNED", True
            else:
                key_trust, pin_ok = "PIN_MISMATCH", False  # fail CLOSED
            public_key = load_pem_public_key(pem)
            key_meta = {
                "keyPath": _KEY_PATH,
                "fingerprintSha256": pinned_fpr,
                "keyTrust": key_trust,
                "pinEnv": _PIN_ENV,
                "provenance": (
                    "recovered from two independent live council signatures "
                    "(ECDSA public-key recovery, unique common candidate, "
                    "2026-07-21); does NOT match the published org "
                    "szl-holdings/.github cosign.pub — owner reconciliation "
                    "pending; envelopes' keyid label 'szlholdings-cosign' is a "
                    "LABEL, not proof of that published key"
                ),
                "runtime": _runtime_key_state(pem),
            }
            index = json.loads(await _fetch(client, _INDEX_PATH))
            files = list(index.get("decisions", []))[:_MAX_DECISIONS]
            for name in files:
                try:
                    raw = await _fetch(client, f"ayllu/decisions/{name}")
                    doc = json.loads(raw)
                    band = _verify_decision(doc, public_key, pinned_fpr)
                    if not pin_ok:
                        band["verified"] = False
                        band["status"] = "PIN_MISMATCH_FAILED_CLOSED"
                    band["file"] = name
                    band["fileSha256"] = _sha256_hex(raw)
                    decisions.append(band)
                except Exception as one_err:
                    decisions.append({
                        "file": name, "verified": False,
                        "status": "UNAVAILABLE",
                        "error": f"{type(one_err).__name__}: {one_err}",
                    })
    except Exception as exc:  # loud, honest, fail-closed
        error = f"{type(exc).__name__}: {exc}"
    ok = bool(decisions) and all(d.get("verified") is True for d in decisions) and error is None
    return {
        "ok": ok,
        "wall": "ayllu-council",
        "servedFrom": "a-11-oy.com (a11oy flagship Space)",
        "source": {
            "repo": "szl-holdings/a11oy",
            "decisionsPath": "ayllu/decisions/",
            "note": "decisions fetched from the committed repo files; "
                    "bytes cached briefly; verification never cached",
        },
        "verifier": {
            "mode": "ECDSA-P256-SHA256 over DSSE PAE via cryptography, server-side",
            "perRequest": True,
            "offline": "scripts/verify_ayllu_council_receipt.py (same repo) proves the "
                       "chain with no trust in this server",
        },
        "scope": {
            "whatThisIs": (
                "cryptographic proof that these committed council deliberation "
                "receipts were signed by the pinned a11oy runtime key and were "
                "not altered since"
            ),
            "whatThisIsNot": (
                "NOT proof of decision quality, consensus, model identity, or "
                "autonomous authority — the council PROPOSES only (zero "
                "effectors, tool_dispatch=false); every decision requires the "
                "human checkpoint it declares"
            ),
        },
        "keyHonesty": key_meta,
        "error": error,
        "generatedAt": _now_iso(),
        "count": len(decisions),
        "decisions": decisions,
    }


async def _api_handler():
    return await _wall_payload()


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AYLLU council wall — verify-then-display</title>
<style>
:root{--void:#080c14;--panel:#0d1520;--line:#16202c;--teal:#3af4c8;--fg:#dfe7ee;--dim:#7f93a6;--gold:#d4a444;--bad:#ff5d73}
*{box-sizing:border-box}body{margin:0;background:var(--void);color:var(--fg);font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
main{max-width:960px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:20px;color:var(--teal);letter-spacing:.04em;margin:0 0 4px}
.sub{color:var(--dim);font-size:13px;margin-bottom:20px}
.scope{border:1px solid var(--gold);border-radius:8px;padding:12px 16px;margin:18px 0;background:rgba(212,164,68,.06);font-size:13px}
.scope b{color:var(--gold)}
.card{border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:14px 16px;margin:12px 0}
.ok{color:var(--teal)}.fail{color:var(--bad)}
.kv{color:var(--dim);font-size:12.5px}.kv code{color:var(--fg)}
.badge{display:inline-block;border:1px solid;border-radius:4px;padding:1px 8px;font-size:12px;margin-right:8px}
.badge.ok{border-color:var(--teal)}.badge.fail{border-color:var(--bad)}
.keybox{border:1px dashed var(--line);border-radius:8px;padding:10px 14px;margin:16px 0;font-size:12.5px;color:var(--dim)}
a{color:var(--teal)}
</style></head><body><main>
<h1>AYLLU COUNCIL — SIGNED DECISIONS</h1>
<div class="sub">every band below is re-verified server-side on this request · fail-closed · <a href="/api/ayllu/wall">raw JSON</a> · <a href="/ayllu">council console</a></div>
<div class="scope" id="scope"><b>WHAT THIS IS / WHAT THIS IS NOT</b><div id="scopebody">loading…</div></div>
<div class="keybox" id="keybox">key: loading…</div>
<div id="bands">verifying…</div>
<script>
fetch('/api/ayllu/wall').then(r=>r.json()).then(d=>{
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  document.getElementById('scopebody').innerHTML =
    '<div style="margin-top:6px"><span class="ok">IS:</span> '+esc(d.scope?.whatThisIs)+'</div>'+
    '<div style="margin-top:4px"><span class="fail">IS NOT:</span> '+esc(d.scope?.whatThisIsNot)+'</div>';
  const k=d.keyHonesty||{};
  document.getElementById('keybox').innerHTML =
    'verifying key <code>'+esc((k.fingerprintSha256||'').slice(0,16))+'…</code> · trust '+esc(k.keyTrust||'?')+
    ' · runtime '+esc(k.runtime?.state||'?')+'<br>'+esc(k.provenance||'');
  const el=document.getElementById('bands');
  if(d.error){el.innerHTML='<div class="card fail">WALL FAILED CLOSED — '+esc(d.error)+'</div>';return;}
  if(!(d.decisions||[]).length){el.innerHTML='<div class="card fail">no committed decisions found — failing closed</div>';return;}
  el.innerHTML=d.decisions.map(b=>{
    const v=b.verified===true, dv=b.derived||{};
    return '<div class="card">'
      +'<span class="badge '+(v?'ok':'fail')+'">'+(v?'VERIFIED':'FAILED')+'</span>'
      +'<code>'+esc(b.file)+'</code>'
      +(v?'<div class="kv" style="margin-top:8px">council <code>'+esc(String(dv.councilId||'').slice(0,8))+'</code>'
        +' · receipt <code>'+esc(String(dv.receiptId||'').slice(0,12))+'…</code>'
        +' · personas <code>'+esc((dv.participants||[]).join(', '))+'</code>'
        +' · decision <code>'+esc(dv.decisionState)+'</code>'
        +' · human checkpoint <code>'+esc(dv.humanCheckpoint?.required===true?'REQUIRED':JSON.stringify(dv.humanCheckpoint).slice(0,40))+'</code>'
        +'</div>'
        :'<div class="kv fail" style="margin-top:8px">'+esc(b.status)+(b.error?' — '+esc(b.error):'')+'</div>')
      +'</div>';
  }).join('');
}).catch(e=>{document.getElementById('bands').innerHTML='<div class="card fail">fetch failed — '+String(e)+'</div>';});
</script>
</main></body></html>"""


async def _page_handler():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_PAGE)


def register(app) -> str:
    """Additive registration + front-move (exact routes must beat SPA fallback)."""
    app.add_api_route(_API_ROUTE, _api_handler, methods=["GET"], include_in_schema=False)
    app.add_api_route(_PAGE_ROUTE, _page_handler, methods=["GET"], include_in_schema=False)
    for target in (_API_ROUTE, _PAGE_ROUTE):
        for index, route in enumerate(app.router.routes):
            if getattr(route, "path", None) == target:
                app.router.routes.insert(0, app.router.routes.pop(index))
                break
    return f"{_API_ROUTE} + {_PAGE_ROUTE} (verify-then-display, fail-closed)"
