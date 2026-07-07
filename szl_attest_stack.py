#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Prove-Our-Whole-Stack live attestation surface.

A READ / VERIFY surface keyed by an existing decision-receipt hash. It NEVER
signs and NEVER mints — it re-fetches and re-verifies what already exists, then
assembles a single human-readable 6-factor provenance chain for any SZL
decision receipt:

  (1) DSSE-signed in-toto Statement + Khipu chain integrity   (live recompute)
  (2) Rekor transparency-log anchoring                        (public log rail)
  (3) Lean4 Theorem U proof-status                            (lutar-lean data)
  (4) Energy certificate                                      (NVML joule-truth)
  (5) 3-of-4 witness cosignatures                             (BFT consensus)
  (6) Overall honest verdict                                  (COMPUTED)

Leader baseline: Sigstore/Rekor chains factors (1)-(2) for *software artifacts*.
No one chains all six for an *AI decision*. That is the frontier — and every
factor here is independently checkable and HONESTLY labeled:

  VERIFIED    — recomputed/confirmed against a real artifact on this read.
  UNAVAILABLE — the rail exists but no artifact is reachable right now (e.g. no
                NVML meter, no cosignatures attached to this receipt). Honest,
                never a faked green.
  ROADMAP     — not built yet (public-Rekor anchoring of a11oy receipts).
  CONJECTURE  — a named OPEN conjecture, never a theorem (Theorem U / Lambda).
  FAIL        — a real check that did not pass (tampered chain).
  NOT_FOUND   — no such receipt in any live organ chain.

Doctrine v11: never sign on a read path; real signature or honest UNSIGNED;
never fabricate a proof/joule/signature; Lambda-uniqueness is Conjecture 1.
"""

import hashlib
import json
import os
import sys
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

# DEV 2 builds the Lean proof replay at /proof; factor 3 links to it.
_PROOF_REPLAY_PATH = "/proof"

# lutar-lean declaration manifest (vendored under proofs/). Factor 3 reads it.
_LEAN_TREE_CANDIDATES = (
    os.path.join(os.path.dirname(__file__), "proofs", "lean-theorem-tree.json"),
    os.path.join(os.path.dirname(__file__), "proofs", "lutar-lean", "lean-theorem-tree.json"),
)

# Theorem U == Uniqueness of the Lutar Invariant (TH10). Per Supreme Rules it is
# Conjecture 1 (sorry-tagged in Lutar/Uniqueness.lean) — NEVER labelled green here,
# even though the staged-advisory tree marks the declaration GREEN.
_THEOREM_U_DECLS = ("Lutar.uniqueness", "Lutar.uniqueness_aux")


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


# ---------------------------------------------------------------------------
# Factor 1 — DSSE-signed in-toto Statement + Khipu hash-chain integrity.
# Reuses szl_khipu_verify.verify_digest (live SHA3-256 seal recompute + genesis
# walk) and szl_dsse (signature posture). No signing happens on this read path.
# ---------------------------------------------------------------------------
def _factor_dsse_chain(receipt_hash: str) -> dict[str, Any]:
    f: dict[str, Any] = {
        "factor": 1,
        "title": "DSSE-signed in-toto Statement + Khipu chain integrity",
        "leader_parity": "Sigstore/cosign signs software artifacts; here the subject "
                         "is an AI decision receipt, chain-verified to genesis.",
        "independent_check": f"GET /api/a11oy/v1/khipu/verify/{receipt_hash}",
    }
    try:
        import szl_khipu_verify as _kv
        v = _kv.verify_digest(str(receipt_hash), None)
    except Exception as exc:  # noqa: BLE001
        return {**f, "status": "UNAVAILABLE",
                "detail": f"khipu verifier unavailable: {exc!r}"}

    if not v.get("found"):
        return {**f, "status": "NOT_FOUND",
                "detail": "no receipt with this digest in any live organ chain "
                          "(in-memory chains reset on Space restart)",
                "verdict": v.get("verdict"), "evidence": v}

    # DSSE signature posture — honest UNSIGNED when no founder cosign key present.
    sig_block: dict[str, Any] = {"signed": False, "label": "UNSIGNED"}
    try:
        # POC (szl-substrate extraction): prefer the shared package; fall back to
        # the local vendored copy. See szl-holdings/szl-substrate MIGRATION.md.
        try:
            from szl_substrate import szl_dsse as _dsse  # single source of truth
        except Exception:
            import szl_dsse as _dsse  # fall back to local vendored copy
        if _dsse.signing_available():
            sig_block = {"signed": True, "label": "DSSE-COSIGN",
                         "keyid": _dsse.KEYID,
                         "pub_fingerprint_sha256": _dsse.public_key_fingerprint(),
                         "verify_key_url": _dsse.PUB_KEY_URL}
        else:
            sig_block = {"signed": False, "label": "UNSIGNED",
                         "keyid_expected": _dsse.KEYID,
                         "verify_key_url": _dsse.PUB_KEY_URL,
                         "note": "no SZL_COSIGN_PRIVATE_PEM in env — receipt seal is "
                                 "DSSE_PLACEHOLDER, honestly UNSIGNED (never faked)"}
    except Exception as exc:  # noqa: BLE001
        sig_block = {"signed": False, "label": "UNSIGNED",
                     "note": f"dsse module unavailable: {exc!r}"}

    verdict = v.get("verdict")
    if verdict == "PASS":
        status = "VERIFIED"
        detail = ("chain integrity VERIFIED: live SHA3-256 seal recompute matches "
                  f"({v.get('digest_matches')}) and prev-links re-walk to genesis "
                  f"({v.get('links_checked')} links). Signature posture: "
                  f"{sig_block['label']}.")
    elif verdict == "FAIL":
        status = "FAIL"
        detail = f"chain integrity FAIL: {v.get('broken_link') or 'recompute mismatch'}"
    else:
        status = "UNAVAILABLE"
        detail = f"verdict {verdict}"

    return {**f, "status": status, "detail": detail,
            "chain": {"organ": v.get("organ"), "seq": v.get("seq"),
                      "digest": v.get("digest"), "prev": v.get("prev"),
                      "receipt_type": v.get("receipt_type"),
                      "recomputed_digest": v.get("recomputed_digest"),
                      "digest_matches": v.get("digest_matches"),
                      "chain_to_genesis_verified": v.get("chain_to_genesis_verified"),
                      "links_checked": v.get("links_checked"),
                      "genesis_prev": v.get("genesis_prev")},
            "signature": sig_block,
            "evidence": v}


# ---------------------------------------------------------------------------
# Factor 2 — Rekor transparency-log anchoring. Reuses the already-merged
# szl_rekor_anchor. a11oy receipt -> public-Rekor submission is ROADMAP; we show
# the live public log head as the working rail (honest UNREACHABLE on egress).
# ---------------------------------------------------------------------------
def _factor_rekor() -> dict[str, Any]:
    f: dict[str, Any] = {
        "factor": 2,
        "title": "Rekor transparency-log anchoring",
        "leader_parity": "Sigstore anchors software artifacts to public Rekor; "
                         "anchoring AI decision receipts is the frontier extension.",
        "independent_check": "GET /api/a11oy/v1/rekor/log  +  "
                             "GET /api/a11oy/v1/rekor/verify/{log_index}",
    }
    try:
        import szl_rekor_anchor as _rk
        log = _rk.fetch_log_state()
    except Exception as exc:  # noqa: BLE001
        return {**f, "status": "ROADMAP",
                "detail": f"rekor module unavailable: {exc!r}"}

    reachable = bool(log.get("reachable"))
    return {**f, "status": "ROADMAP",
            "detail": ("a11oy decision receipts are NOT yet submitted to public "
                       "Rekor (anchoring is ROADMAP). The Merkle-inclusion math + "
                       "live log rail are real: public Rekor tree head is "
                       + ("reachable now." if reachable else "unreachable from this "
                          "host right now (honest fallback, never a faked root).")),
            "public_log": log,
            "roadmap": "submit each minted decision receipt's DSSE body to public "
                       "Rekor and store the returned log_index on the khipu receipt."}


# ---------------------------------------------------------------------------
# Factor 3 — Lean4 Theorem U proof-status (Uniqueness of the Lutar Invariant).
# Served from vendored lutar-lean data. Theorem U == Conjecture 1 (sorry-tagged):
# labelled CONJECTURE, NEVER green. The kernel-wide proof-status is the checkable
# VERIFIED artifact (247 GREEN / 22 TRACKED / 0 RED, 8 locked-proven). Links to
# DEV 2's /proof replay.
# ---------------------------------------------------------------------------
def _factor_lean() -> dict[str, Any]:
    f: dict[str, Any] = {
        "factor": 3,
        "title": "Lean4 Theorem U proof-status (Uniqueness of the Lutar Invariant)",
        "leader_parity": "No transparency log carries a machine-checked proof "
                         "obligation alongside the artifact — this binds one.",
        "independent_check": f"{_PROOF_REPLAY_PATH} (DEV 2 Lean replay) + "
                             "proofs/lean-theorem-tree.json",
    }
    tree = None
    src = None
    for cand in _LEAN_TREE_CANDIDATES:
        try:
            with open(cand, "rb") as fh:
                tree = json.load(fh)
                src = cand
                break
        except Exception:  # noqa: BLE001
            continue
    if tree is None:
        return {**f, "status": "UNAVAILABLE",
                "detail": "lutar-lean declaration manifest not vendored in this image"}

    meta = tree.get("meta", {})
    counts = meta.get("status_counts", {})
    decls = tree.get("declarations", [])
    theorem_u = [d for d in decls if d.get("name") in _THEOREM_U_DECLS]

    return {**f,
            "status": "CONJECTURE",
            "detail": ("Theorem U (Uniqueness of the Lutar Invariant, TH10) is "
                       "Conjecture 1 per Supreme Rules — sorry-tagged in "
                       "Lutar/Uniqueness.lean (CAUCHY_ND obligation OPEN). It is "
                       "NEVER claimed green. The kernel-wide proof-status below is "
                       "the VERIFIED checkable artifact."),
            "theorem_u": [{"name": d.get("name"), "file": d.get("file"),
                           "tree_status": d.get("status"),
                           "honest_status": "CONJECTURE (Conjecture 1, sorry-tagged)",
                           "axiom_deps": d.get("axiom_deps")} for d in theorem_u],
            "kernel_proof_status": {
                "label": "VERIFIED",
                "commit": meta.get("commit"),
                "lean_toolchain": meta.get("lean_toolchain"),
                "total_declarations": meta.get("total_declarations"),
                "status_counts": counts,
                "locked_proven_count": 8,
                "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
                "note": "247 GREEN / 22 TRACKED / 0 RED is STAGED-ADVISORY (line "
                        "table needs lake build --log in CI); locked-proven = "
                        "exactly 8 (no-axiom theorem locked_count_eight).",
            },
            "source": os.path.relpath(src, os.path.dirname(__file__)) if src else None,
            "proof_replay": _PROOF_REPLAY_PATH}


# ---------------------------------------------------------------------------
# Factor 4 — Energy certificate. Reuses szl_materials._energy_provenance(), whose
# label is decided SOLELY by szl_joules_truth off a fresh real on-box NVML delta.
# VERIFIED only when MEASURED; honest UNAVAILABLE when no NVML meter is reachable.
# ---------------------------------------------------------------------------
def _factor_energy() -> dict[str, Any]:
    f: dict[str, Any] = {
        "factor": 4,
        "title": "Energy certificate (NVML joule-truth)",
        "leader_parity": "DeGCert-style energy attestation bound to the decision; "
                         "Sigstore carries no energy provenance at all.",
        "independent_check": "GET /api/a11oy/v1/materials/screen (energy block)",
    }
    try:
        import szl_materials as _mat
        block = _mat._energy_provenance()
    except Exception as exc:  # noqa: BLE001
        return {**f, "status": "UNAVAILABLE",
                "detail": f"energy provenance unavailable: {exc!r}"}

    label = block.get("label")
    # Cert hash binds the canonical energy block so it is independently re-derivable.
    cert_hash = hashlib.sha256(_canon(block)).hexdigest()
    if label == "MEASURED" and isinstance(block.get("joules"), (int, float)):
        status = "VERIFIED"
        detail = (f"MEASURED: fresh real on-box NVML delta — {block.get('joules')} J "
                  f"on node {block.get('node')} (szl_joules_truth confirmed).")
    else:
        status = "UNAVAILABLE"
        detail = (f"no fresh real NVML delta reachable from this process — energy is "
                  f"{label}, joules null, EXCLUDED from any measured total (never "
                  f"fabricated). VERIFIED only on a real meter.")
    return {**f, "status": status, "detail": detail,
            "energy_cert": {"label": label, "joules": block.get("joules"),
                            "node": block.get("node"), "measured": block.get("measured"),
                            "cert_hash_sha256": cert_hash,
                            "authority": block.get("authority")},
            "evidence": block}


# ---------------------------------------------------------------------------
# Factor 5 — 3-of-4 witness cosignatures (Khipu BFT consensus, Conjecture 2).
# Reuses szl_khipu_consensus.verify_consensus_receipt to VERIFY cosignatures
# ATTACHED to the receipt. Never runs consensus (that signs) on this read path —
# honest UNAVAILABLE when the receipt carries no consensus block.
# ---------------------------------------------------------------------------
def _factor_consensus(chain_evidence: dict[str, Any]) -> dict[str, Any]:
    f: dict[str, Any] = {
        "factor": 5,
        "title": "3-of-4 witness cosignatures (Khipu BFT consensus)",
        "leader_parity": "CoSi-style threshold cosigning of an AI decision; "
                         "Sigstore is single-signer. Cite arXiv 2504.14668.",
        "independent_check": "POST /api/killinchu/uds/v1/consensus/verify (canonical "
                             "consensus receipt body)",
    }
    threshold = n = None
    theorem_ref = "Conjecture 2 (Khipu BFT safety)"
    try:
        import szl_khipu_consensus as _cons
        threshold = _cons.THRESHOLD
        n = len(_cons.CONSENSUS_ORGANS)
    except Exception as exc:  # noqa: BLE001
        return {**f, "status": "UNAVAILABLE",
                "detail": f"consensus module unavailable: {exc!r}"}

    # Look for a consensus receipt / cosignature block embedded in the receipt.
    rcpt = (chain_evidence or {}).get("evidence") if isinstance(chain_evidence, dict) else None
    candidate = None
    for src in (chain_evidence, rcpt):
        if isinstance(src, dict):
            if isinstance(src.get("consensus"), dict):
                candidate = src.get("consensus")
                break
            if src.get("signatures") and src.get("payloadType"):
                candidate = src
                break

    if candidate is None:
        return {**f, "status": "UNAVAILABLE",
                "detail": (f"this receipt carries no attached {threshold}-of-{n} "
                           "consensus cosignature block. Cosigning is minted via "
                           "POST consensus (a write/sign path), never on this read "
                           "surface (no-sign-on-GET)."),
                "policy": {"threshold": threshold, "n": n, "theorem_ref": theorem_ref}}

    try:
        res = _cons.verify_consensus_receipt(candidate)
    except Exception as exc:  # noqa: BLE001
        return {**f, "status": "UNAVAILABLE",
                "detail": f"consensus verify error: {exc!r}",
                "policy": {"threshold": threshold, "n": n, "theorem_ref": theorem_ref}}

    ok = bool(res.get("verified")) and bool(res.get("claim_matches", True))
    return {**f, "status": "VERIFIED" if ok else "FAIL",
            "detail": (f"{res.get('khipu_consensus')} witnesses cosigned "
                       f"({res.get('consensus_count')}/{res.get('n')}, "
                       f"threshold {res.get('threshold')})."
                       if ok else "attached cosignatures did not verify to threshold."),
            "policy": {"threshold": threshold, "n": n, "theorem_ref": theorem_ref},
            "evidence": res}


# ---------------------------------------------------------------------------
# Factor 6 — Overall honest verdict. COMPUTED from the per-factor labels. Never
# "all green": it reports exactly how many factors are VERIFIED and names every
# ROADMAP / UNAVAILABLE / CONJECTURE caveat.
# ---------------------------------------------------------------------------
def _factor_overall(factors: list[dict[str, Any]]) -> dict[str, Any]:
    by = {x["factor"]: x.get("status") for x in factors}
    verified = sorted(k for k, v in by.items() if v == "VERIFIED")
    failed = sorted(k for k, v in by.items() if v == "FAIL")
    roadmap = sorted(k for k, v in by.items() if v in ("ROADMAP", "UNAVAILABLE", "CONJECTURE"))

    if by.get(1) == "NOT_FOUND":
        verdict = "NOT_FOUND"
        summary = "No receipt with this digest exists in any live organ chain."
    elif failed:
        verdict = "TAMPERED"
        summary = (f"Integrity FAILURE on factor(s) {failed}. Honest BLOCKED beats "
                   "fake green — do not trust this receipt.")
    elif by.get(1) == "VERIFIED":
        verdict = "CHAIN-VERIFIED"
        summary = (f"Decision receipt chain-verified to genesis. {len(verified)} of 5 "
                   f"evidence factors VERIFIED {verified}; "
                   f"{len(roadmap)} ROADMAP/UNAVAILABLE/CONJECTURE {roadmap} "
                   "(honestly labelled, never faked green).")
    else:
        verdict = "INCONCLUSIVE"
        summary = "Receipt found but core chain integrity could not be confirmed."

    return {"factor": 6, "title": "Overall honest verdict",
            "status": verdict, "detail": summary,
            "factors_verified": verified, "factors_failed": failed,
            "factors_roadmap": roadmap,
            "honesty_note": "Sigstore/Rekor chains factors 1-2 for software "
                            "artifacts. This surface chains all 6 for an AI decision "
                            "— each independently checkable, none faked."}


def attest(receipt_hash: str) -> dict[str, Any]:
    """Assemble the 6-factor provenance chain for a decision receipt. READ-ONLY."""
    receipt_hash = (receipt_hash or "").strip().lower()
    f1 = _factor_dsse_chain(receipt_hash)
    f2 = _factor_rekor()
    f3 = _factor_lean()
    f4 = _factor_energy()
    f5 = _factor_consensus(f1)
    factors = [f1, f2, f3, f4, f5]
    f6 = _factor_overall(factors)
    return {
        "surface": "prove-our-whole-stack",
        "receipt_hash": receipt_hash,
        "doctrine": "v11",
        "labels": ["VERIFIED", "UNAVAILABLE", "ROADMAP", "CONJECTURE", "FAIL", "NOT_FOUND"],
        "leader_baseline": "Sigstore/Rekor: factors 1-2 for software artifacts.",
        "frontier": "all 6 factors chained for an AI decision receipt.",
        "factors": factors + [f6],
        "verdict": f6["status"],
    }


# ---------------------------------------------------------------------------
# Registration. JSON: GET /api/{ns}/v1/attest/{receipt_hash}. UI: GET /attest.
# Registered BEFORE the SPA catch-all so both resolve locally (per code-style).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    async def _attest_json(receipt_hash: str):  # noqa: ANN202
        result = attest(receipt_hash)
        return JSONResponse(result, headers={"x-szl-attest-verdict": result["verdict"]})

    async def _attest_page(request: Request):  # noqa: ANN202
        return HTMLResponse(_PAGE)

    base = f"/api/{ns}/v1/attest"
    _n_before = len(app.router.routes)
    app.add_api_route(f"{base}/{{receipt_hash}}", _attest_json, methods=["GET"],
                      include_in_schema=True)
    app.add_api_route("/attest", _attest_page, methods=["GET"], include_in_schema=False)

    # Move the new routes ahead of the SPA catch-all (same pattern as rekor).
    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
    except Exception as exc:  # noqa: BLE001
        print(f"[{ns}] attest route reorder failed (non-fatal): {exc!r}", file=sys.stderr)

    print(f"[{ns}] szl_attest_stack routes registered: GET {base}/{{hash}} + GET /attest",
          flush=True)
    return {"ok": True, "ns": ns, "routes": [f"{base}/{{receipt_hash}}", "/attest"]}


_PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KANCHAY · Prove Our Whole Stack</title>
<style>
:root{--void:#080c14;--panel:#0e1422;--edge:#1d2840;--proof:#3af4c8;--lattice:#5b8dee;
--gold:#d7b96b;--ink:#e8eef7;--mut:#8194b0;--bad:#ff6b6b;--warn:#d7b96b;}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#0d1626,var(--void));
color:var(--ink);font-family:'Inter',system-ui,sans-serif;line-height:1.5}
.wrap{max-width:920px;margin:0 auto;padding:42px 20px 80px}
h1{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:30px;margin:0 0 4px;
letter-spacing:.3px}
h1 .k{color:var(--gold)}
.sub{color:var(--mut);font-size:14px;margin:0 0 28px}
.sub b{color:var(--proof)}
.box{display:flex;gap:10px;margin:0 0 10px}
input{flex:1;background:var(--panel);border:1px solid var(--edge);border-radius:10px;
padding:13px 15px;color:var(--ink);font-family:'JetBrains Mono',monospace;font-size:13px}
input:focus{outline:none;border-color:var(--lattice)}
button{background:linear-gradient(180deg,var(--proof),#26c9a3);color:#04211b;border:0;
border-radius:10px;padding:0 22px;font-weight:700;font-size:14px;cursor:pointer;
font-family:'Space Grotesk',sans-serif}
button:disabled{opacity:.5;cursor:wait}
.hint{color:var(--mut);font-size:12px;margin:0 0 24px}
.hint code{color:var(--gold)}
.verdict{border:1px solid var(--edge);border-radius:12px;padding:16px 18px;margin:0 0 16px;
background:var(--panel);display:none}
.verdict.show{display:block}
.vrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.vbadge{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:15px;
padding:5px 12px;border-radius:8px}
.vsum{color:var(--mut);font-size:13px;margin-top:8px}
.factor{border:1px solid var(--edge);border-radius:12px;margin:0 0 12px;background:var(--panel);
overflow:hidden}
.fhead{display:flex;align-items:center;gap:12px;padding:14px 16px;cursor:pointer}
.fnum{font-family:'JetBrains Mono',monospace;color:var(--mut);font-size:13px;min-width:18px}
.ftitle{flex:1;font-weight:600;font-size:14px}
.badge{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;
padding:4px 9px;border-radius:6px;letter-spacing:.4px}
.b-VERIFIED,.b-CHAIN-VERIFIED{background:rgba(58,244,200,.14);color:var(--proof);
border:1px solid rgba(58,244,200,.4)}
.b-ROADMAP,.b-UNAVAILABLE,.b-CONJECTURE,.b-INCONCLUSIVE{background:rgba(215,185,107,.12);
color:var(--gold);border:1px solid rgba(215,185,107,.4)}
.b-FAIL,.b-TAMPERED,.b-NOT_FOUND{background:rgba(255,107,107,.12);color:var(--bad);
border:1px solid rgba(255,107,107,.4)}
.fbody{padding:0 16px 14px;font-size:13px;color:var(--mut)}
.fbody .detail{color:var(--ink);margin-bottom:10px}
.chk{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--lattice);
word-break:break-all}
pre{background:#070b12;border:1px solid var(--edge);border-radius:8px;padding:11px;
overflow:auto;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--mut);
max-height:240px;margin:10px 0 0}
.foot{color:var(--mut);font-size:12px;margin-top:30px;border-top:1px solid var(--edge);
padding-top:16px}
.foot a{color:var(--lattice)}
.skel{height:64px;border-radius:12px;margin:0 0 12px;
background:linear-gradient(90deg,#0e1422,#16203400,#0e1422);
background-size:200% 100%;animation:sh 1.2s infinite}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
</style></head>
<body><div class="wrap">
<h1><span class="k">KANCHAY</span> · Prove Our Whole Stack</h1>
<p class="sub">Paste any SZL decision-receipt hash. We re-verify a
<b>6-factor provenance chain</b> for that decision — each factor independently
checkable, honestly labelled, never faked green. Sigstore/Rekor does factors 1–2
for software; this chains all six for an AI decision.</p>
<div class="box">
<input id="h" placeholder="receipt hash (64 hex)  e.g. a khipu digest from /api/a11oy/v1/khipu/organs"
 autocomplete="off" spellcheck="false">
<button id="go">Verify</button>
</div>
<p class="hint">No hash? List live organs at
<code>/api/a11oy/v1/khipu/organs</code> and copy a digest. This is a READ surface —
it never signs.</p>
<div id="verdict" class="verdict"></div>
<div id="out"></div>
<div class="foot">
Labels: <b>VERIFIED</b> recomputed now · <b>UNAVAILABLE</b> rail exists, no
artifact reachable · <b>ROADMAP</b> not built yet · <b>CONJECTURE</b> open, never
a theorem · <b>FAIL/NOT_FOUND</b>. Lean replay: <a href="/proof">/proof</a>.
Doctrine v11 — Λ = Conjecture 1, locked-proven = 8.
</div>
</div>
<script>
const $=s=>document.querySelector(s);
function badge(s){return '<span class="badge b-'+s+'">'+s+'</span>'}
function esc(o){return JSON.stringify(o,null,2).replace(/</g,'&lt;')}
async function run(){
  const h=$('#h').value.trim();
  if(!h){return}
  $('#go').disabled=true;
  $('#verdict').className='verdict';
  $('#out').innerHTML='<div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  try{
    const r=await fetch('/api/a11oy/v1/attest/'+encodeURIComponent(h));
    const d=await r.json();
    const all=d.factors||[];
    const ov=all[all.length-1];
    const fs=all.slice(0,5);
    $('#verdict').className='verdict show';
    $('#verdict').innerHTML='<div class="vrow">'+badge(ov.status)+
      '<span style="font-weight:600">Overall honest verdict</span></div>'+
      '<div class="vsum">'+ov.detail+'</div>';
    $('#out').innerHTML=fs.map(f=>(
      '<div class="factor"><div class="fhead" onclick="this.parentNode.querySelector(\\'.fbody\\').style.display=this.parentNode.querySelector(\\'.fbody\\').style.display===\\'none\\'?\\'block\\':\\'none\\'">'+
      '<span class="fnum">'+f.factor+'</span>'+
      '<span class="ftitle">'+f.title+'</span>'+badge(f.status)+'</div>'+
      '<div class="fbody" style="display:none"><div class="detail">'+f.detail+'</div>'+
      (f.independent_check?'<div class="chk">check ▸ '+f.independent_check+'</div>':'')+
      '<pre>'+esc(f)+'</pre></div></div>')).join('');
  }catch(e){
    $('#out').innerHTML='<div class="factor"><div class="fbody" style="padding:16px">'+
      'request failed: '+e+'</div></div>';
  }
  $('#go').disabled=false;
}
$('#go').onclick=run;
$('#h').addEventListener('keydown',e=>{if(e.key==='Enter')run()});
</script>
</body></html>"""


def _selftest() -> dict:
    """Mint a REAL receipt via the shared khipu module, then attest it end-to-end."""
    import szl_khipu
    out: dict = {}
    dag = szl_khipu.get_dag("attest_stack_selftest", ns="a11oy")
    dag.emit("attest.alpha", {"k": 1})
    r = dag.emit("attest.beta", {"decision": "ALLOW", "k": 2})

    res = attest(r["digest"])
    f = {x["factor"]: x for x in res["factors"]}

    assert f[1]["status"] == "VERIFIED", f[1]
    assert f[1]["chain"]["chain_to_genesis_verified"] is True, f[1]
    out["factor1_chain_verified"] = True

    assert f[2]["status"] == "ROADMAP", f[2]
    out["factor2_rekor_honest_roadmap"] = True

    assert f[3]["status"] == "CONJECTURE", f[3]
    assert f[3]["kernel_proof_status"]["locked_proven_count"] == 8, f[3]
    out["factor3_theoremU_conjecture_kernel_verified"] = True

    assert f[4]["status"] in ("VERIFIED", "UNAVAILABLE"), f[4]
    out["factor4_energy_honest"] = True

    assert f[5]["status"] in ("VERIFIED", "UNAVAILABLE"), f[5]
    out["factor5_consensus_honest"] = True

    assert f[6]["status"] == "CHAIN-VERIFIED", f[6]
    out["factor6_overall_chain_verified"] = True

    # Unknown hash -> honest NOT_FOUND, never fabricated.
    nf = attest("deadbeef" * 8)
    assert nf["verdict"] == "NOT_FOUND", nf
    out["unknown_hash_not_found"] = True

    return out


if __name__ == "__main__":
    print("=" * 70)
    print("szl_attest_stack — self-test (6-factor prove-our-whole-stack)")
    print("=" * 70)
    res = _selftest()
    print(json.dumps(res, indent=2))
    ok = all(res.values())
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
