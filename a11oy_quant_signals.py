# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""
a11oy Quant Signals wall — GET /api/quant/signals + GET /signals

The public, visitor-reachable evidence wall for the doctrine-governed quant
engine (szl-holdings/szl-quant@main). Every signal and backtest ships as a
DSSE envelope; this module re-verifies each envelope's ed25519 signature
SERVER-SIDE on every request against a PINNED engine key and renders the
result honestly.

HONESTY DOCTRINE (law — labels only REDUCE claims):
  * The signals are ADVISORY_PAPER_ONLY research artifacts. There is NO
    execution, NO custody, and this is NOT financial advice — those code
    paths do not exist upstream.
  * Signature verification proves INTEGRITY + ORIGIN only. A green VERIFIED
    badge means "this receipt's bytes were signed by the pinned engine key
    and have not been tampered with" — it is NEVER a claim of accuracy,
    profitability, or that any signal will make money.
  * Λ (Lambda) is "Conjecture 1 (open)", NEVER a theorem. Λ roll-ups are
    advisory only.
  * The receipt's own _doctrine.disclaimer text is reproduced VERBATIM on
    the page banner — never paraphrased.

Verification detail (mirrors a11oy_forge_family.py's server-side, fail-closed,
key-pinned design; reuses the image's `cryptography` lib — no new deps):
  * DSSE PAE = b"DSSEv1 " + len(payloadType) + " " + payloadType + " " +
    len(payload_bytes) + " " + payload_bytes  (lengths as ASCII decimals,
    single spaces). ed25519-verify each envelope signature over the PAE.
  * The key used to verify is the PINNED engine key, NOT the envelope's
    embedded publicKeySpkiBase64. Pin source: env A11OY_QUANT_ENGINE_KEYID
    (expected keyId). We compute keyId = sha256(SPKI DER)[:16 hex] from the
    fetched keys/engine_pubkey.json and REQUIRE it to equal the env pin AND
    require the envelope's embedded SPKI to equal the fetched one. Any
    mismatch, or a missing env pin, renders FAIL-CLOSED ("pin not configured
    / mismatch") — never a green check.

On fetch failure the wall fails CLOSED with an honest "receipts unavailable"
page / JSON — it never serves stale bytes as fresh and never invents a result.
Receipt BYTES are cached ~300s to spare the raw host; the cryptographic
verification itself runs on every request and is never cached or skipped.

Additive module per Space convention: register(app) adds both routes and
front-moves them so the exact paths win over the SPA history fallback.
"""

import base64
import hashlib
import html
import json
import os
import time
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_API_ROUTE = "/api/quant/signals"
_PAGE_ROUTE = "/signals"

_RAW = "https://raw.githubusercontent.com/szl-holdings/szl-quant/main"
_SOURCE = "szl-holdings/szl-quant@main"
_PUBKEY_FILE = "keys/engine_pubkey.json"
_PIN_ENV = "A11OY_QUANT_ENGINE_KEYID"
_CACHE_TTL_SECONDS = 300  # receipt BYTES only; verification always re-runs

# The signal_* and backtest_* receipt sets (source of truth). raw.githubusercontent
# needs the literal names; "$" is percent-encoded in the URL path only.
_RECEIPT_NAMES = (
    "signal_SOL_1784088245451.receipt.json",
    "signal_JUP_1784088245451.receipt.json",
    "signal_Bonk_1784088245451.receipt.json",
    "signal_$WIF_1784088245451.receipt.json",
    "backtest_BTC_365d.receipt.json",
    "backtest_ETH_365d.receipt.json",
    "backtest_SOL_365d.receipt.json",
    "backtest_BONK_365d.receipt.json",
)

# Independent, offline verifier one-liner published by the repo itself.
_VERIFY_CMD = "node verify/verify.mjs --pubkey keys/engine_pubkey.json --dir receipts/"
_REPO_URL = "https://github.com/szl-holdings/szl-quant"

# Estate palette (Doctrine): dark background + teal / blue / gold accents.
_BG = "#0a0e12"
_PANEL = "#0f151b"
_TEAL = "#3af4c8"
_BLUE = "#5b8dee"
_GOLD = "#d7b96b"
_INK = "#c9d6e2"
_MUTE = "#7d93a6"

# name -> {"at": epoch, "bytes": bytes}  (receipt bytes only)
_byte_cache: dict = {}
# engine pubkey bytes cache: {"at": epoch, "bytes": bytes}
_pubkey_cache: dict = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _url_for(name: str) -> str:
    """raw.githubusercontent URL; percent-encode '$' in the path segment only."""
    return f"{_RAW}/receipts/{name.replace('$', '%24')}"


def _dsse_pae(payload_type: str, payload_bytes: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding, spec-exact:
    b"DSSEv1 " + len(payloadType) + " " + payloadType + " " +
    len(payload_bytes) + " " + payload_bytes  (lengths as ASCII decimals)."""
    pt = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(pt)).encode("ascii") + b" "
        + pt + b" "
        + str(len(payload_bytes)).encode("ascii") + b" "
        + payload_bytes
    )


async def _fetch_bytes(client: httpx.AsyncClient, url: str) -> bytes:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


async def _fetch_pubkey_bytes(client: httpx.AsyncClient) -> bytes:
    cached = _pubkey_cache.get("k")
    if cached and (time.time() - cached["at"]) < _CACHE_TTL_SECONDS:
        return cached["bytes"]
    data = await _fetch_bytes(client, f"{_RAW}/{_PUBKEY_FILE}")
    _pubkey_cache["k"] = {"at": time.time(), "bytes": data}
    return data


async def _fetch_receipt_bytes(client: httpx.AsyncClient, name: str) -> bytes:
    cached = _byte_cache.get(name)
    if cached and (time.time() - cached["at"]) < _CACHE_TTL_SECONDS:
        return cached["bytes"]
    data = await _fetch_bytes(client, _url_for(name))
    _byte_cache[name] = {"at": time.time(), "bytes": data}
    return data


def _resolve_pin(pubkey_bytes: bytes) -> dict:
    """Fail-closed key pinning. Returns the pinned-key context; pinOk is False
    (and a reason is given) whenever the env pin is missing or does not match
    the keyId derived from the fetched engine_pubkey.json."""
    key = json.loads(pubkey_bytes)
    fetched_spki_b64 = key.get("publicKeySpkiBase64", "")
    declared_key_id = key.get("keyId", "")
    algo = key.get("alg") or key.get("algo")

    derived_key_id = ""
    try:
        derived_key_id = _sha256_hex(base64.b64decode(fetched_spki_b64, validate=True))[:16]
    except Exception:
        derived_key_id = ""

    env_pin = os.environ.get(_PIN_ENV, "").strip()

    if algo != "ed25519":
        return {"pinOk": False, "reason": "engine key algorithm is not ed25519",
                "keyId": derived_key_id, "spkiB64": fetched_spki_b64, "envPin": env_pin}
    if not derived_key_id or derived_key_id != declared_key_id:
        return {"pinOk": False,
                "reason": "engine keyId does not derive from its SPKI (sha256(SPKI)[:16] mismatch)",
                "keyId": derived_key_id, "spkiB64": fetched_spki_b64, "envPin": env_pin}
    if not env_pin:
        return {"pinOk": False,
                "reason": f"pin not configured: env {_PIN_ENV} is unset (fail-closed)",
                "keyId": derived_key_id, "spkiB64": fetched_spki_b64, "envPin": env_pin}
    if env_pin != derived_key_id:
        return {"pinOk": False,
                "reason": f"pin mismatch: env {_PIN_ENV}={env_pin} != engine keyId {derived_key_id} (fail-closed)",
                "keyId": derived_key_id, "spkiB64": fetched_spki_b64, "envPin": env_pin}
    return {"pinOk": True, "reason": "pinned", "keyId": derived_key_id,
            "spkiB64": fetched_spki_b64, "envPin": env_pin}


def _verify_envelope(raw: bytes, pin: dict) -> dict:
    """Verify one DSSE envelope against the PINNED key. Fail-closed.

    verified is True only when: the pin is OK, the envelope's embedded SPKI
    equals the fetched engine SPKI, and at least one signature verifies over
    the spec-exact PAE with the pinned key."""
    envelope = json.loads(raw)
    payload_type = envelope.get("payloadType", "")
    payload_b64 = envelope.get("payload", "")
    signatures = envelope.get("signatures") or []
    embedded_spki = envelope.get("publicKeySpkiBase64", "")

    checks = {
        "pinConfiguredAndMatches": bool(pin.get("pinOk")),
        "payloadTypeIsInToto": payload_type == "application/vnd.in-toto+json",
        "embeddedSpkiMatchesPinned": bool(embedded_spki) and embedded_spki == pin.get("spkiB64"),
    }

    sig_ok = False
    sig_keyid = ""
    try:
        payload_bytes = base64.b64decode(payload_b64, validate=True)
    except Exception:
        payload_bytes = b""
    if pin.get("pinOk") and checks["embeddedSpkiMatchesPinned"] and payload_bytes:
        try:
            spki_der = base64.b64decode(pin["spkiB64"], validate=True)
            public_key = load_der_public_key(spki_der)
            if isinstance(public_key, Ed25519PublicKey):
                pae = _dsse_pae(payload_type, payload_bytes)
                for sig in signatures:
                    try:
                        public_key.verify(base64.b64decode(sig.get("sig", ""), validate=True), pae)
                        sig_ok = True
                        sig_keyid = sig.get("keyid", "") or sig_keyid
                        break
                    except Exception:
                        continue
        except Exception:
            sig_ok = False
    checks["ed25519SignatureVerifiesWithPinnedKey"] = sig_ok

    payload = {}
    try:
        payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    except Exception:
        payload = {}

    verified = all(checks.values())
    return {
        "verified": verified,
        "checks": checks,
        "sigKeyId": sig_keyid or (signatures[0].get("keyid", "") if signatures else ""),
        "envelope": envelope,
        "payload": payload,
    }


def _summarize(payload: dict) -> dict:
    """Extract the honest highlights that ARE in the predicate — show, never
    editorialize. Different predicate types carry different fields."""
    predicate_type = payload.get("predicateType", "")
    subjects = payload.get("subject") or []
    subject_name = subjects[0].get("name", "") if subjects else ""
    subject_sha = (subjects[0].get("digest") or {}).get("sha256", "") if subjects else ""
    predicate = payload.get("predicate") or {}
    doctrine = predicate.get("_doctrine") or {}

    summary = {
        "predicateType": predicate_type,
        "subject": subject_name,
        "subjectSha256": subject_sha,
    }
    if "signal" in predicate_type:
        decision = predicate.get("decision") or {}
        asset = decision.get("asset") or {}
        summary["kind"] = "signal"
        summary["asset"] = asset.get("symbol", "")
        summary["chain"] = asset.get("chain", "")
        summary["proposedAction"] = decision.get("proposedAction", "")
        summary["verdict"] = decision.get("verdict", "")
        summary["conviction"] = decision.get("conviction")
        summary["blockedBy"] = decision.get("blockedBy") or []
    elif "backtest" in predicate_type:
        smry = predicate.get("summary") or {}
        asset = smry.get("asset") or {}
        wf = smry.get("walkForward") or {}
        summary["kind"] = "backtest"
        summary["asset"] = asset.get("symbol", "")
        summary["populationSize"] = wf.get("populationSize")
        summary["outOfSampleBars"] = wf.get("outOfSampleBars")
    else:
        summary["kind"] = "unknown"
    return {"summary": summary, "doctrine": doctrine}


async def _collect() -> dict:
    """Fetch + verify every receipt. Fail-closed on any fetch failure — never
    serve stale-as-fresh, never invent a result."""
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        pubkey_bytes = await _fetch_pubkey_bytes(client)
        pin = _resolve_pin(pubkey_bytes)
        receipts = []
        for name in _RECEIPT_NAMES:
            raw = await _fetch_receipt_bytes(client, name)
            result = _verify_envelope(raw, pin)
            extra = _summarize(result["payload"])
            receipts.append({
                "name": name,
                "verified": result["verified"],
                "checks": result["checks"],
                "keyId": result["sigKeyId"],
                "summary": extra["summary"],
                "doctrine": extra["doctrine"],
                "envelope": result["envelope"],
                "payload": result["payload"],
                "receiptSha256": _sha256_hex(raw),
            })
    return {"pin": pin, "receipts": receipts}


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------
async def _signals_api():
    try:
        data = await _collect()
        pin = data["pin"]
        return {
            "ok": pin["pinOk"] and all(r["verified"] for r in data["receipts"]),
            "wall": "quant-signals",
            "source": _SOURCE,
            "pinnedKeyId": pin["keyId"] if pin["pinOk"] else None,
            "pinStatus": pin["reason"],
            "posture": "ADVISORY_PAPER_ONLY — no execution, no custody, NOT financial advice",
            "note": "Signature verification proves INTEGRITY + ORIGIN only — never accuracy or profitability.",
            "verifier": {
                "mode": "DSSE PAE + ed25519 via cryptography, server-side, pinned key",
                "perRequest": True,
                "note": "receipt bytes cached briefly; verification never cached; fail-closed",
                "independentCommand": _VERIFY_CMD,
            },
            "fetchedAt": _now_iso(),
            "receipts": [
                {
                    "name": r["name"],
                    "verified": r["verified"],
                    "keyId": r["keyId"],
                    "checks": r["checks"],
                    "summary": r["summary"],
                    "doctrine": r["doctrine"],
                }
                for r in data["receipts"]
            ],
        }
    except Exception as err:  # fail-closed, loud, honest — never stale-as-fresh
        return {
            "ok": False,
            "wall": "quant-signals",
            "source": _SOURCE,
            "pinnedKeyId": None,
            "posture": "ADVISORY_PAPER_ONLY — no execution, no custody, NOT financial advice",
            "receipts": [],
            "fetchedAt": _now_iso(),
            "error": f"receipts unavailable: {type(err).__name__}: {err}",
        }


# ---------------------------------------------------------------------------
# Server-rendered page (0 CDN, no external assets, inline vanilla JS only)
# ---------------------------------------------------------------------------
def _fail_closed_page(message: str, status: int = 503) -> str:
    e = html.escape
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Quant Signals unavailable · a11oy</title></head>"
        f"<body style='background:{_BG};color:{_GOLD};"
        "font:15px/1.6 system-ui,sans-serif;padding:2.2rem;max-width:820px;margin:0 auto'>"
        "<h1 style='color:#fff'>Quant Signals — receipts unavailable</h1>"
        "<p>The wall fails <strong>CLOSED</strong>: it will not serve stale receipts as fresh, "
        "and it never invents a verification result.</p>"
        f"<pre style='background:#070b0e;border:1px solid #16202a;border-radius:8px;"
        f"padding:.8rem;color:{_INK};white-space:pre-wrap'>{e(message)}</pre>"
        "<p style='color:#7d93a6'>Advisory research artifacts. Paper-only. NOT financial advice. "
        "No execution, no custody.</p>"
        f"</body></html>"
    ), status


def _pretty(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _render_page(data: dict) -> str:
    e = html.escape
    pin = data["pin"]
    receipts = data["receipts"]

    # Verbatim disclaimer: reproduce the receipt's own _doctrine.disclaimer text.
    disclaimer = ""
    for r in receipts:
        d = (r.get("doctrine") or {}).get("disclaimer")
        if d:
            disclaimer = d
            break
    if not disclaimer:
        disclaimer = ("Advisory research output. Paper-only. NOT financial advice. "
                      "No execution, no custody.")

    # Pin banner state.
    if pin["pinOk"]:
        pin_line = (f"Pinned engine key <code>{e(pin['keyId'])}</code> "
                    f"(env {e(_PIN_ENV)}) — verification runs server-side, per request.")
    else:
        pin_line = (f"FAIL-CLOSED: {e(pin['reason'])}. No receipt can show a green check "
                    f"until the pin is configured and matches.")

    cards = []
    for i, r in enumerate(receipts):
        verified = r["verified"]
        badge = "VERIFIED" if verified else "VERIFICATION FAILED"
        badge_color = _TEAL if verified else _GOLD
        s = r["summary"]
        doctrine = r.get("doctrine") or {}

        rows = [("subject", s.get("subject", "")),
                ("predicateType", s.get("predicateType", "")),
                ("keyId", r.get("keyId", ""))]
        if s.get("kind") == "signal":
            rows += [("asset", s.get("asset", "")),
                     ("chain", s.get("chain", "")),
                     ("proposedAction", s.get("proposedAction", "")),
                     ("verdict", s.get("verdict", "")),
                     ("conviction", str(s.get("conviction", ""))),
                     ("blockedBy", ", ".join(s.get("blockedBy", []) or []))]
        elif s.get("kind") == "backtest":
            rows += [("asset", s.get("asset", "")),
                     ("populationSize", str(s.get("populationSize", ""))),
                     ("outOfSampleBars", str(s.get("outOfSampleBars", "")))]
        highlight_rows = "".join(
            f"<div class='kv'><span class='k'>{e(str(k))}</span>"
            f"<span class='v'>{e(str(v))}</span></div>"
            for k, v in rows if str(v) != ""
        )

        # Λ Conjecture-1 line — only if the predicate carries it.
        lambda_line = ""
        lam = doctrine.get("lambdaStatus")
        if lam:
            lambda_line = (f"<p class='lam'>Λ — Conjecture 1 (open): "
                           f"{e(str(lam))}</p>")

        checks_ok = "".join(
            f"<li class='{'ok' if v else 'bad'}'>{e(str(k))}: {'PASS' if v else 'FAIL'}</li>"
            for k, v in (r.get("checks") or {}).items()
        )

        raw_envelope = _pretty(r["envelope"])
        raw_payload = _pretty(r["payload"])

        cards.append(f"""
      <article class="card" data-quantsignals-card="s1">
        <header class="card-head">
          <span class="case">{e(str(r['name']))}</span>
          <span class="badge" style="color:{badge_color};border-color:{badge_color}">{badge}</span>
        </header>
        <div class="kvs">{highlight_rows}</div>
        {lambda_line}
        <details>
          <summary>Verification checks (fail-closed)</summary>
          <ul class="checks">{checks_ok}</ul>
        </details>
        <details>
          <summary>Raw DSSE envelope (JSON)</summary>
          <pre id="env-{i}">{e(raw_envelope)}</pre>
          <button class="copy" data-target="env-{i}">Copy envelope JSON</button>
        </details>
        <details>
          <summary>Decoded in-toto payload (JSON)</summary>
          <pre id="pay-{i}">{e(raw_payload)}</pre>
          <button class="copy" data-target="pay-{i}">Copy payload JSON</button>
        </details>
      </article>""")

    cards_html = "".join(cards)
    pinned_id = e(pin["keyId"]) if pin["pinOk"] else "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quant Signals — signed, verifiable · a11oy</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:{_BG}; color:{_INK};
         font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:2rem 1.1rem 4rem; }}
  h1 {{ font-size:1.5rem; margin:.2rem 0 .3rem; color:#fff; }}
  .sub {{ color:{_MUTE}; margin:0 0 1.3rem; }}
  .banner {{ border:1px solid {_GOLD}; border-left-width:5px; border-radius:8px;
             background:rgba(215,185,107,.06); color:{_GOLD};
             padding:.85rem 1rem; margin:0 0 1rem; font-weight:600; }}
  .pin {{ border:1px solid #1c2733; border-radius:8px; background:{_PANEL};
          padding:.7rem 1rem; margin:0 0 1.6rem; color:{_INK}; font-size:.92rem; }}
  .pin code {{ color:{_TEAL}; }}
  .card {{ background:{_PANEL}; border:1px solid #1c2733; border-radius:10px;
           padding:1.05rem 1.1rem; margin:0 0 1.15rem; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:center;
                gap:.6rem; flex-wrap:wrap; }}
  .case {{ font-weight:700; color:#fff; word-break:break-all; }}
  .badge {{ font-size:.72rem; font-weight:700; text-transform:uppercase;
            letter-spacing:.05em; padding:.18em .6em; border:1px solid;
            border-radius:6px; white-space:nowrap; }}
  .kvs {{ margin:.7rem 0 .3rem; }}
  .kv {{ display:flex; gap:.6rem; padding:.12rem 0; border-bottom:1px solid #131c25; }}
  .kv .k {{ color:{_MUTE}; min-width:9.5rem; }}
  .kv .v {{ color:{_INK}; word-break:break-all; }}
  .lam {{ color:{_BLUE}; font-size:.9rem; margin:.6rem 0 .2rem; }}
  details {{ border-top:1px solid #1c2733; padding-top:.55rem; margin-top:.55rem; }}
  summary {{ cursor:pointer; color:{_BLUE}; font-weight:600; }}
  ul.checks {{ list-style:none; padding:.4rem 0 0; margin:0; font-size:.88rem; }}
  ul.checks li.ok {{ color:{_TEAL}; }}
  ul.checks li.bad {{ color:{_GOLD}; }}
  pre {{ background:#070b0e; border:1px solid #16202a; border-radius:8px;
         padding:.75rem .85rem; overflow:auto; max-height:22rem;
         font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
         color:{_INK}; white-space:pre; }}
  button.copy {{ margin:.5rem 0 .2rem; background:transparent; color:{_TEAL};
                 border:1px solid {_TEAL}; border-radius:6px; padding:.35em .8em;
                 font:inherit; font-size:.82rem; cursor:pointer; }}
  button.copy:hover {{ background:rgba(58,244,200,.08); }}
  button.copy.ok {{ color:{_GOLD}; border-color:{_GOLD}; }}
  footer {{ margin-top:2.4rem; padding-top:1rem; border-top:1px solid #1c2733;
            color:{_MUTE}; font-size:.9rem; }}
  footer a {{ color:{_TEAL}; text-decoration:none; }}
  footer a:hover {{ text-decoration:underline; }}
  footer pre {{ margin:.5rem 0; }}
</style>
</head>
<body>
  <main class="wrap">
    <h1>Quant Signals — signed, verifiable</h1>
    <p class="sub">Doctrine-governed quant engine · every signal &amp; backtest ships a
       DSSE-signed receipt, re-verified server-side against a pinned key on every request.</p>
    <div class="banner" data-quantsignals-banner="s1">{e(disclaimer)}</div>
    <div class="pin">{pin_line}
      <br><span style="color:{_MUTE}">A VERIFIED badge proves INTEGRITY + ORIGIN only — that the
      receipt was signed by the pinned engine key and not tampered with. It is
      <strong>never</strong> a claim of accuracy or profitability. Λ is Conjecture&nbsp;1 (open),
      never a theorem.</span>
    </div>
{cards_html}
    <footer>
      Source of truth: <a href="{e(_REPO_URL)}" rel="noopener">{e(_REPO_URL)}</a>
      · pinned engine keyId: <code style="color:{_TEAL}">{pinned_id}</code>
      <br>Verify independently, offline, with the repo's own verifier:
      <pre id="verify-cmd">{e(_VERIFY_CMD)}</pre>
      <button class="copy" data-target="verify-cmd">Copy verify command</button>
    </footer>
  </main>
  <script>
  (function () {{
    document.querySelectorAll("button.copy").forEach(function (btn) {{
      btn.addEventListener("click", function () {{
        var el = document.getElementById(btn.getAttribute("data-target"));
        if (!el) return;
        var text = el.textContent || "";
        var done = function () {{
          var orig = btn.textContent;
          btn.textContent = "Copied";
          btn.classList.add("ok");
          setTimeout(function () {{ btn.textContent = orig; btn.classList.remove("ok"); }}, 1400);
        }};
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(text).then(done, function () {{ fallback(text, done); }});
        }} else {{ fallback(text, done); }}
      }});
    }});
    function fallback(text, done) {{
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", "");
      ta.style.position = "absolute"; ta.style.left = "-9999px";
      document.body.appendChild(ta); ta.select();
      try {{ document.execCommand("copy"); done(); }} catch (e) {{}}
      document.body.removeChild(ta);
    }}
  }})();
  </script>
</body>
</html>"""


async def _signals_page():
    from starlette.responses import HTMLResponse
    try:
        data = await _collect()
        return HTMLResponse(_render_page(data))
    except Exception as page_error:  # fail-closed: never a fabricated page
        body, status = _fail_closed_page(
            f"{type(page_error).__name__}: {page_error}", status=503)
        return HTMLResponse(body, status_code=status)


def register(app, ns: str = "a11oy") -> str:
    """Additive registration + front-move (exact routes must beat SPA fallback).

    Adds two routes off the SAME source of truth (szl-quant@main receipts):
      * GET /api/quant/signals — machine JSON, per-receipt verify result
      * GET /signals           — visitor-reachable, self-contained server-rendered page
    Both are front-moved so the exact paths win over the SPA history fallback."""
    app.add_api_route(_API_ROUTE, _signals_api, methods=["GET"], include_in_schema=False)
    app.add_api_route(_PAGE_ROUTE, _signals_page, methods=["GET"], include_in_schema=False)
    for target in (_API_ROUTE, _PAGE_ROUTE):
        for index, route in enumerate(app.router.routes):
            if getattr(route, "path", None) == target:
                app.router.routes.insert(0, app.router.routes.pop(index))
                break
    return (f"{_API_ROUTE} + {_PAGE_ROUTE} (szl-quant@main signed receipts; "
            f"server-verified, pinned key, fail-closed)")
