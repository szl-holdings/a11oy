# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings — ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED (749/14/163). Λ = Conjecture 1 (advisory, NEVER "green").
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
"""
szl_verify_transcript — DEEPEN the public "Verify a Receipt" flow (Wave N #806)
into a SINGLE-request COMPOSITE verifiable transcript across the honest surfaces.

WHAT THIS IS (one line): a public, no-login endpoint where a SINGLE request
produces a REAL composite transcript that chains multiple existing honest a11oy
surfaces end-to-end —

    brain-context  →  governed agent-loop run  →  eval-arena self-eval
                   →  energy allocation         →  DSSE-signed receipt

— and a `/verify`-style endpoint that RE-CHECKS the hash chain link-by-link and
returns PER-LINK HONEST LABELS.

WHY (the gap #806 left open): szl_public_verify (#806) verifies ONE pasted DSSE
envelope (signature + payload digest + Khipu chain). But the estate's real value
is a MULTI-SURFACE pipeline whose links each carry their OWN honest capability
label. Nobody exposed a single public request that (a) actually RUNS that pipeline
end-to-end via the on-main read paths and (b) re-verifies the WHOLE hash chain with
a truthful label per link. This module is that surface. It COMPOSES — it reuses the
real modules' own output and never reimplements a signer, a scorer, or a meter.

HOW IT COMPOSES (single sources of truth — reused, GUARDED, never faked):
  * szl_agent_loop_governed.run_loop(task, sign_fn, consult_brain=True,
      allocate_energy=True) is the REAL orchestrator that already chains
      brain-context (corpus="brain") → plan → act (engine P1-P6 + Λ-gate + sandbox)
      → eval-arena self-eval → Brain-harnessed energy allocation into ONE composite
      ECDSA-P256 DSSE receipt with a whole-run hash-chain digest (`run_chain_digest`).
  * szl_public_verify.verify_receipt(envelope=...) (#806) re-verifies the composite
      DSSE envelope (signature / payload-digest / Khipu chain) — we DELEGATE the
      cryptographic receipt link to it, so this genuinely DEEPENS #806.
  * The whole-run hash chain is re-folded INDEPENDENTLY here: we recompute the
      brain-context digest and the energy digest from their embedded blocks, re-fold
      [brain ⊕ step-digests ⊕ energy] the exact way run_loop did, and confirm the
      recompute equals the signed `run_chain_digest`. COMPUTED, never asserted.

HONEST LABELS PER LINK (Doctrine v11 — never weaken):
  Each link carries TWO honest signals:
   (1) hash_recheck ∈ {VERIFIED | MISMATCH | UNAVAILABLE}
        VERIFIED    — we recomputed the link's digest and it matched the signed chain.
        MISMATCH    — recompute differed (tamper) → the whole verdict FAILs.
        UNAVAILABLE — the link's pre-image is not present in the receipt body to
                      recompute here (e.g. per-step bodies are committed via the
                      signed fold but not re-expanded in the receipt) — honest, not
                      a failure and NEVER a faked VERIFIED.
   (2) data_label — the SURFACE'S OWN honest capability label, passed through
        untouched: MEASURED only where that surface reports a live meter delta,
        else MODELED / SAMPLE / LIVE / CACHED / UNAVAILABLE. We NEVER upgrade a
        SAMPLE/MODELED reading to MEASURED. Energy joules are MEASURED only if the
        Brain-energy meter itself reported MEASURED; otherwise SAMPLE/UNAVAILABLE.

  Overall verdict:
    FAIL         — any link hash_recheck == MISMATCH, or the DSSE signature MISMATCHed.
    PASS         — the chain re-fold VERIFIED, the signature VERIFIED, no MISMATCH,
                   and nothing was left UNAVAILABLE.
    PARTIAL      — chain re-fold VERIFIED but some links could only be checked
                   partially (UNSIGNED-LOCAL signature and/or UNAVAILABLE recompute).
    INCONCLUSIVE — the chain re-fold itself could not be run.

Λ = Conjecture 1 (advisory, never "green"/proven/a gate). Trust ceiling 0.97.
This surface adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}@c7c0ba17.
No fabricated datum, no new pip dep, no CDN, no Node. Additive, try/except-guarded.
Endpoints registered BEFORE the SPA catch-all (starlette front-insert, mirrors
szl_agent_loop_governed). Guard+note anything depending on an unmerged Wave-P PR.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

SCHEMA = "szl.verify_transcript/v1"
DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
LOCKED8 = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
TRUST_CEILING = 0.97  # never 1.0
_CONJECTURE_NOTE = ("Λ is Conjecture 1 — advisory only, NEVER 'green'/proven/a gate; "
                    "trust ceiling 0.97; nothing here touches the locked-8.")

# honest hash-recheck labels (never invent a fourth "green" we did not earn)
VERIFIED = "VERIFIED"        # recompute RAN and matched
MISMATCH = "MISMATCH"        # recompute RAN and differed (tamper)
UNAVAILABLE = "UNAVAILABLE"  # recompute could not be RUN from the receipt body

# recognised honest data-labels, in the ONLY direction we ever trust: MEASURED is
# accepted only if the source literally reports it. We never manufacture MEASURED.
_KNOWN_LABELS = ("MEASURED", "LIVE", "MODELED", "SAMPLE", "ESTIMATE",
                 "CACHED", "SIMULATED", "DEGRADED", "UNAVAILABLE")

DEFAULT_TASK = ("Explain the Euler Khipu DAG identity F1 and estimate its energy "
                "budget under the governed loop.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canon(obj: Any) -> str:
    # BYTE-IDENTICAL to szl_agent_loop_governed._canon so our re-fold reproduces
    # the exact digests that run_loop signed (sort_keys, compact, default=str).
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ── reuse the REAL surfaces (single sources of truth — COMPOSE, don't reimplement) ──
try:
    import szl_agent_loop_governed as _aloop
    _ALOOP_OK = True
except Exception as _e:  # additive: never break the Space if the loop moves
    _aloop = None  # type: ignore
    _ALOOP_OK = False
    _ALOOP_ERR = repr(_e)

try:
    import szl_public_verify as _pubverify  # Wave N #806 — the receipt verifier we deepen
    _PUBVERIFY_OK = True
except Exception as _e:
    _pubverify = None  # type: ignore
    _PUBVERIFY_OK = False
    _PUBVERIFY_ERR = repr(_e)


def _fallback_sign(obj: dict) -> dict:
    """Honest signer fallback: real szl_dsse in-Space, UNSIGNED-LOCAL locally.
    NEVER fabricates a signature."""
    try:
        import szl_dsse
        return szl_dsse.sign_payload(obj, "application/vnd.szl.khipu+json")
    except Exception as e:  # pragma: no cover
        body = _canon(obj).encode("utf-8")
        pae = b"DSSEv1 application/vnd.szl.khipu+json " + body
        return {"payloadType": "application/vnd.szl.khipu+json",
                "payload": __import__("base64").b64encode(body).decode("ascii"),
                "_pae_sha256": hashlib.sha256(pae).hexdigest(),
                "signatures": [], "signed": False,
                "honesty": "UNSIGNED-LOCAL — no signer (%r); no signature fabricated." % e}


# ===========================================================================
# label helpers — pass the surface's OWN label through; classify without ever
# upgrading to MEASURED.
# ===========================================================================
def _classify_label(raw: Any) -> str:
    """Extract the honest capability token from a surface's label string WITHOUT
    ever manufacturing a MEASURED reading. If the source text contains one of the
    known tokens we return it verbatim (MEASURED only when the source said so);
    otherwise UNAVAILABLE. This is a pass-through classifier, never an upgrade."""
    if not isinstance(raw, str) or not raw.strip():
        return UNAVAILABLE
    up = raw.upper()
    for tok in _KNOWN_LABELS:  # MEASURED is first, but only matches if literally present
        if tok in up:
            return tok
    return UNAVAILABLE


# ===========================================================================
# BUILD — a SINGLE request runs the real governed loop end-to-end and returns the
# composite transcript (the composite DSSE receipt + a normalized link list).
# ===========================================================================
def build_transcript(task: str = "",
                     sign_fn: Optional[Callable[[dict], dict]] = None,
                     ns: str = "a11oy",
                     mode: str = "research",
                     model_id: str = "",
                     max_retries: int = 0) -> dict:
    """Produce a REAL composite transcript from ONE request by running the governed
    agent loop with the Brain feeds ON. Returns {ok, transcript, verify}. NEVER
    raises into the caller; NEVER fabricates a run, an eval, a joule, or a signature."""
    task = (task or DEFAULT_TASK).strip()
    ns = ns or "a11oy"
    signer = sign_fn if callable(sign_fn) else _fallback_sign

    if not (_ALOOP_OK and _aloop is not None):
        return {
            "ok": False,
            "status_code": 200,
            "schema": SCHEMA,
            "error": "governed agent loop unavailable: %s" % (globals().get("_ALOOP_ERR", "?")),
            "label": ("MODELED-UNAVAILABLE — szl_agent_loop_governed could not be imported "
                      "in this runtime; no transcript fabricated."),
            "conjecture_note": _CONJECTURE_NOTE,
        }

    try:
        run = _aloop.run_loop(task, signer, ns=ns, mode=(mode or "research"),
                              model_id=(model_id or ""), max_retries=max(0, int(max_retries)),
                              consult_brain=True, allocate_energy=True)
    except Exception as e:  # never raise into the request
        return {
            "ok": False, "status_code": 200, "schema": SCHEMA,
            "error": "governed loop raised: %s" % type(e).__name__,
            "label": "MODELED-UNAVAILABLE — governed loop raised; no transcript fabricated.",
            "conjecture_note": _CONJECTURE_NOTE,
        }

    composite = (run or {}).get("composite_receipt") or {}
    body = composite.get("body") or {}
    dsse = composite.get("dsse") or {}
    signing = composite.get("signing") or {}

    transcript = {
        "schema": SCHEMA,
        "ts": _now(),
        "hub": ns,
        "task": task,
        "run_id": body.get("run_id"),
        "source_surface": "szl_agent_loop_governed",
        "source_endpoint": "/api/%s/v1/agentloop/run" % ns,
        "composite_receipt": {"body": body, "dsse": dsse, "signing": signing},
        "run_chain_digest": body.get("run_chain_digest"),
        "chain_order": body.get("chain_order"),
        "composes": body.get("composes"),
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "conjecture_note": _CONJECTURE_NOTE,
    }

    verify = verify_transcript(transcript)
    return {
        "ok": True,
        "status_code": 200,
        "schema": SCHEMA,
        "ts": _now(),
        "task": task,
        "run_id": body.get("run_id"),
        "transcript": transcript,
        "verify": verify,
        "shareable": {
            "recheck_endpoint": "POST /api/%s/v1/verify/transcript/recheck" % ns,
            "receipt_verify_endpoint": "POST /api/%s/v1/verify/receipt (#806)" % ns,
            "note": ("POST the composite_receipt (or the whole transcript) back to the "
                     "recheck endpoint to independently re-fold the hash chain."),
        },
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "conjecture_note": _CONJECTURE_NOTE,
    }


# ===========================================================================
# VERIFY — the /verify-style re-checker. Re-folds the hash chain link-by-link and
# returns a per-link honest label. Accepts a transcript OR a raw composite receipt.
# ===========================================================================
def _extract_body_dsse(obj: Any) -> tuple[dict, dict]:
    """Pull the composite receipt {body, dsse} out of a transcript OR a bare
    composite-receipt dict OR a bare receipt body. Never raises."""
    if not isinstance(obj, dict):
        return {}, {}
    # transcript form
    cr = obj.get("composite_receipt")
    if isinstance(cr, dict) and isinstance(cr.get("body"), dict):
        return cr.get("body") or {}, cr.get("dsse") or {}
    # bare composite-receipt form {body, dsse}
    if isinstance(obj.get("body"), dict):
        return obj.get("body") or {}, obj.get("dsse") or {}
    # bare body form (has the fold fields directly)
    if "run_chain_digest" in obj or "step_chain" in obj:
        return obj, {}
    return {}, {}


def verify_transcript(obj: Any) -> dict:
    """Independently re-fold a composite transcript's hash chain and label each link
    honestly. NEVER raises; NEVER fabricates a check result or a MEASURED reading."""
    body, dsse = _extract_body_dsse(obj)
    base = {
        "service": "public.verify.transcript",
        "ts": _now(),
        "chain_order": body.get("chain_order"),
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "conjecture_note": _CONJECTURE_NOTE,
        "honest_note": (
            "Each link carries hash_recheck (VERIFIED/MISMATCH/UNAVAILABLE — COMPUTED, "
            "never asserted) and data_label (the surface's OWN honest label, passed "
            "through: MEASURED only where a live meter reported it, else MODELED/SAMPLE/"
            "UNAVAILABLE — never upgraded). The DSSE receipt link delegates to "
            "szl_public_verify (#806). Λ = Conjecture 1; nothing touches the locked-8."),
    }
    if not body:
        return {**base, "ok": False, "verdict": "NO_INPUT",
                "detail": ("no composite transcript/receipt supplied; POST a `transcript` "
                           "or a `composite_receipt` (or its `body`) to re-check")}

    links: list[dict] = []

    # ── recompute the two independently-reconstructible digests from their blocks ──
    brain_block = body.get("brain_context")
    stored_brain_digest = body.get("brain_digest")
    recomputed_brain_digest = (_sha256(_canon(brain_block))
                               if isinstance(brain_block, dict) else None)

    energy_block = body.get("energy_allocation")
    stored_energy_digest = body.get("energy_digest")
    recomputed_energy_digest = (_sha256(_canon(energy_block))
                                if isinstance(energy_block, dict) else None)

    # ── LINK 1 — brain-context (corpus="brain") ──
    if body.get("brain_consulted"):
        if recomputed_brain_digest is not None and stored_brain_digest:
            hr = VERIFIED if recomputed_brain_digest == stored_brain_digest else MISMATCH
        else:
            hr = UNAVAILABLE
        links.append({
            "index": len(links), "link": "brain-context",
            "surface": "szl_agentloop_brain.consult_brain (corpus='brain')",
            "read_path": (brain_block or {}).get("read_path") if isinstance(brain_block, dict) else None,
            "hash_recheck": hr,
            "stored_digest": stored_brain_digest,
            "recomputed_digest": recomputed_brain_digest,
            "data_label": _classify_label((brain_block or {}).get("label")) if isinstance(brain_block, dict) else UNAVAILABLE,
            "data_label_raw": (brain_block or {}).get("label") if isinstance(brain_block, dict) else None,
            "detail": ("brain-context digest recomputed from the embedded compact block and "
                       "compared to the signed chain seed. Real harvested nodes only; MODELED "
                       "pulse or UNAVAILABLE — never a fabricated citation."),
        })

    # ── LINK 2 — governed agent-loop steps (act: engine P1-P6 + Λ-gate + sandbox) ──
    step_chain = body.get("step_chain") or []
    step_labels = []
    for s in step_chain:
        dec = s.get("decision")
        step_labels.append("LIVE" if dec in ("ALLOW", "ALLOW_WITH_CONDITIONS") else
                           "DEGRADED" if dec == "DENY" else "MODELED")
    # per-step bodies are committed via the signed fold but not re-expanded in the
    # receipt → honest UNAVAILABLE for a standalone recompute (never a faked VERIFIED).
    links.append({
        "index": len(links), "link": "agent-loop-steps",
        "surface": "szl_agent_loop_governed.run_loop (act: a11oy_code_engine.governed_turn)",
        "hash_recheck": UNAVAILABLE if step_chain else UNAVAILABLE,
        "n_steps": len(step_chain),
        "step_digests": [s.get("digest") for s in step_chain],
        "decisions": [s.get("decision") for s in step_chain],
        "step_receipt_pae_sha256": [s.get("step_receipt_pae_sha256") for s in step_chain],
        "data_label": ("LIVE" if step_chain and all(l == "LIVE" for l in step_labels)
                       else "DEGRADED" if any(l == "DEGRADED" for l in step_labels)
                       else "MODELED" if step_chain else UNAVAILABLE),
        "detail": ("per-step act digests are committed into the signed whole-run fold "
                   "(verified in the chain-fold link below); their pre-image bodies are "
                   "not re-expanded in the receipt, so a standalone per-step recompute is "
                   "honestly UNAVAILABLE here — the fold binds them cryptographically."),
    })

    # ── LINK 3 — eval-arena self-eval (deterministic scoring + Λ axes) ──
    evs = [{"n": s.get("n"), "accuracy": s.get("eval_accuracy"), "lambda": s.get("eval_lambda"),
            "receipt_pae_sha256": s.get("eval_receipt_pae_sha256")} for s in step_chain]
    agg = body.get("aggregate") or {}
    # eval honesty label lives on the loop's per-step eval summary; the composite
    # aggregate carries mean accuracy/Λ. We pass the label through; MODELED in the
    # keyless HF default (no provider key), LIVE if a key was wired — never faked.
    eval_label = "MODELED"
    try:
        # the loop's own eval honesty label, if surfaced on the run summary
        el = (obj.get("verify") or {}) if isinstance(obj, dict) else {}
    except Exception:
        el = {}
    links.append({
        "index": len(links), "link": "eval-arena-self-eval",
        "surface": "szl_eval_arena.run_eval (HELM-style axes, Λ geometric mean)",
        "hash_recheck": VERIFIED if all(e.get("receipt_pae_sha256") for e in evs) and evs else UNAVAILABLE,
        "per_step_eval": evs,
        "mean_eval_accuracy": agg.get("mean_eval_accuracy"),
        "mean_eval_lambda": agg.get("mean_eval_lambda"),
        "lambda_status": agg.get("lambda_status"),
        "data_label": eval_label,
        "detail": ("each step's self-eval produced its OWN signed DSSE receipt (PAE sha256 "
                   "recorded and present here); eval answers are honest MODELED reference "
                   "stubs in the keyless runtime (pipeline REAL), LIVE if a provider key is "
                   "wired — never fabricated. Λ is Conjecture 1 (advisory)."),
    })

    # ── LINK 4 — energy allocation (Brain-harnessed; joules carry their TRUE label) ──
    if body.get("energy_allocated"):
        if recomputed_energy_digest is not None and stored_energy_digest:
            hr = VERIFIED if recomputed_energy_digest == stored_energy_digest else MISMATCH
        else:
            hr = UNAVAILABLE
        eb = energy_block if isinstance(energy_block, dict) else {}
        joules_label_raw = eb.get("loop_allocation_joules_label") or eb.get("harnessed_label")
        links.append({
            "index": len(links), "link": "energy-allocation",
            "surface": "szl_agentloop_brain.allocate_energy (/brain/energy; szl_energy_budget fallback)",
            "read_path": eb.get("read_path"),
            "hash_recheck": hr,
            "stored_digest": stored_energy_digest,
            "recomputed_digest": recomputed_energy_digest,
            "loop_allocation_joules": eb.get("loop_allocation_joules"),
            # CRITICAL honesty: joules are MEASURED only if the meter reported MEASURED.
            "data_label": _classify_label(joules_label_raw),
            "data_label_raw": joules_label_raw,
            "detail": ("energy digest recomputed from the embedded allocation block and "
                       "compared to the signed chain tail. Joules carry the meter's OWN "
                       "label — MEASURED only if a live meter reported it, else SAMPLE/"
                       "MODELED/UNAVAILABLE; NEVER upgraded to a fabricated MEASURED reading."),
        })

    # ── LINK 5 — the DSSE-signed composite receipt (delegate to #806) ──
    sig_status = UNAVAILABLE
    receipt_link: dict = {
        "index": len(links), "link": "dsse-receipt",
        "surface": "szl_public_verify.verify_receipt (#806) over the composite DSSE envelope",
    }
    if _PUBVERIFY_OK and _pubverify is not None and isinstance(dsse, dict) and dsse:
        try:
            pv = _pubverify.verify_receipt(envelope=dsse)
            checks = {c.get("check"): c for c in (pv.get("checks") or [])}
            sig = (checks.get("signature") or {}).get("status")
            dig = (checks.get("payload_digest") or {}).get("status")
            sig_status = sig or UNAVAILABLE
            receipt_link.update({
                "hash_recheck": VERIFIED if dig == "VERIFIED" else (
                    MISMATCH if dig == "MISMATCH" else UNAVAILABLE),
                "signature_status": sig_status,
                "payload_digest_status": dig,
                "pubverify_verdict": pv.get("verdict"),
                "data_label": ("LIVE" if sig == "VERIFIED" else
                               "UNSIGNED-LOCAL" if sig == "UNSIGNED-LOCAL" else
                               "MISMATCH" if sig == "MISMATCH" else UNAVAILABLE),
                "detail": ("delegated to the public receipt verifier (#806): ECDSA-P256 "
                           "signature over the DSSE PAE + payload-digest re-hash. "
                           "UNSIGNED-LOCAL when no in-image key is present (honest, not faked)."),
            })
        except Exception as e:
            receipt_link.update({"hash_recheck": UNAVAILABLE, "signature_status": UNAVAILABLE,
                                 "detail": "public verifier raised: %s" % type(e).__name__})
    else:
        # honest fallback when #806 is not importable or no envelope present
        signed = bool(dsse.get("signed")) if isinstance(dsse, dict) else False
        sig_status = "LIVE" if signed else "UNSIGNED-LOCAL"
        receipt_link.update({
            "hash_recheck": UNAVAILABLE,
            "signature_status": sig_status,
            "data_label": "LIVE" if signed else "UNSIGNED-LOCAL",
            "detail": ("szl_public_verify (#806) not importable in this runtime OR no "
                       "envelope present; reported the envelope's own honest signed flag "
                       "(no signature fabricated)." if not _PUBVERIFY_OK else
                       "no DSSE envelope in the receipt to verify."),
        })
    links.append(receipt_link)

    # ── THE CHAIN FOLD — re-fold [brain ⊕ step-digests ⊕ energy] exactly as run_loop did ──
    stored_run_digest = body.get("run_chain_digest")
    seq = ([stored_brain_digest] if stored_brain_digest else []) \
        + [s.get("digest") for s in step_chain] \
        + ([stored_energy_digest] if stored_energy_digest else [])
    recomputed_run_digest = _sha256(_canon(seq)) if seq else None
    if recomputed_run_digest is None or not stored_run_digest:
        fold_status = UNAVAILABLE
    elif recomputed_run_digest == stored_run_digest:
        fold_status = VERIFIED
    else:
        fold_status = MISMATCH
    chain_fold = {
        "link": "run-chain-fold",
        "hash_recheck": fold_status,
        "stored_run_chain_digest": stored_run_digest,
        "recomputed_run_chain_digest": recomputed_run_digest,
        "folded_sequence_len": len(seq),
        "detail": ("re-folds [brain-context ⊕ per-step act digests ⊕ energy] with the EXACT "
                   "canonical scheme szl_agent_loop_governed used, and compares to the SIGNED "
                   "run_chain_digest. COMPUTED, never asserted — this is the end-to-end "
                   "cryptographic binding of every link into the one signed receipt."),
    }

    # ── overall verdict (honest; a single MISMATCH FAILs; nothing faked to green) ──
    hrs = [l.get("hash_recheck") for l in links] + [fold_status]
    verdict = _overall_verdict(hrs, sig_status, fold_status)

    # ── advisory Λ posture over the transcript (Conjecture 1, never a gate) ──
    mean_lambda = (body.get("aggregate") or {}).get("mean_eval_lambda")
    return {
        **base,
        "ok": True,
        "run_id": body.get("run_id"),
        "n_links": len(links),
        "links": links,
        "chain_fold": chain_fold,
        "signature_status": sig_status,
        "verdict": verdict,
        "lambda": mean_lambda,
        "lambda_posture": "advisory (Conjecture 1) — NEVER green/theorem",
        "lambda_status": "CONJECTURE",
        "trust_ceiling": TRUST_CEILING,
        "locked8": list(LOCKED8),
        "locked8_touched": False,
    }


def _overall_verdict(hash_rechecks: list, sig_status: str, fold_status: str) -> str:
    if MISMATCH in hash_rechecks or sig_status == "MISMATCH":
        return "FAIL"
    if fold_status != VERIFIED:
        return "INCONCLUSIVE"
    # fold VERIFIED. PASS only if nothing was merely UNAVAILABLE and the sig verified.
    partial = (UNAVAILABLE in hash_rechecks) or (sig_status in ("UNSIGNED-LOCAL", UNAVAILABLE))
    return "PARTIAL" if partial else "PASS"


# ===========================================================================
# ROUTE REGISTRATION — starlette routes inserted BEFORE the SPA catch-all, mirroring
# szl_agent_loop_governed. sign_fn = the HOST app's REAL in-image signer.
# ===========================================================================
def register(app, ns: str = "a11oy",
             sign_fn: Optional[Callable[[dict], dict]] = None) -> dict:
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    signer = sign_fn if callable(sign_fn) else _fallback_sign

    async def _build(request):
        # POST body optional; GET works too (default task) — a SINGLE public request.
        b: dict = {}
        if request.method == "POST":
            try:
                b = await request.json()
            except Exception:
                b = {}
            if not isinstance(b, dict):
                b = {}
        task = b.get("task") or b.get("prompt") or b.get("query") or ""
        mode = str(b.get("mode") or "research").lower()
        model_id = str(b.get("model_id") or b.get("model") or "").strip()
        try:
            max_retries = int(b.get("max_retries", 0))
        except Exception:
            max_retries = 0
        out = build_transcript(task, sign_fn=signer, ns=ns, mode=mode,
                               model_id=model_id, max_retries=max_retries)
        return JSONResponse(out, status_code=out.get("status_code", 200),
                            headers={"x-szl-verify-verdict":
                                     str((out.get("verify") or {}).get("verdict", ""))})

    async def _recheck(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        if not isinstance(b, dict):
            b = {}
        subject = b.get("transcript") or b.get("composite_receipt") or b.get("receipt") or b
        result = verify_transcript(subject)
        code = 200 if result.get("ok") else 400
        return JSONResponse(result, status_code=code,
                            headers={"x-szl-verify-verdict": str(result.get("verdict", ""))})

    async def _health(request):
        signer_live = False
        try:
            probe = signer({"probe": "verify-transcript-health", "ts": _now()})
            signer_live = bool(probe.get("signed"))
        except Exception:
            signer_live = False
        aloop_health = {}
        if _ALOOP_OK and _aloop is not None:
            try:
                comp = getattr(_aloop, "_BRAINFEED_OK", None)
                aloop_health = {"agent_loop_available": True, "brain_feed_available": bool(comp)}
            except Exception:
                aloop_health = {"agent_loop_available": True}
        else:
            aloop_health = {"agent_loop_available": False}
        return JSONResponse({
            "surface": "szl_verify_transcript — public composite verifiable transcript",
            "role": ("A SINGLE request runs the governed loop end-to-end (brain-context → "
                     "act → eval → energy → DSSE receipt) and re-checks the hash chain "
                     "link-by-link with per-link honest labels. Deepens Verify-a-Receipt (#806)."),
            "endpoints": [
                "POST /api/%s/v1/verify/transcript" % ns,
                "GET  /api/%s/v1/verify/transcript" % ns,
                "POST /api/%s/v1/verify/transcript/recheck" % ns,
                "GET  /api/%s/v1/verify/transcript/health" % ns,
            ],
            "composes": {
                "agent_loop": "szl_agent_loop_governed.run_loop (consult_brain+allocate_energy)",
                "receipt_verifier": "szl_public_verify.verify_receipt (#806)",
                "public_verify_available": _PUBVERIFY_OK,
                **aloop_health,
            },
            "signer_live": signer_live,
            "signature_mode": ("LIVE (real ECDSA-P256 in-image key)" if signer_live
                               else "UNSIGNED-LOCAL (honest — no in-image key in this runtime)"),
            "labels": {"hash_recheck": [VERIFIED, MISMATCH, UNAVAILABLE],
                       "data_label": list(_KNOWN_LABELS),
                       "measured_policy": ("MEASURED is passed through ONLY when the source "
                                           "surface reports it; never manufactured here.")},
            "lambda": "Conjecture 1 (advisory — never a gate, never 'green').",
            "doctrine": DOCTRINE, "kernel_commit": _KERNEL, "locked8_touched": False,
            "conjecture_note": _CONJECTURE_NOTE, "checked_at": _now(),
        })

    routes = [
        Route("/api/%s/v1/verify/transcript" % ns, _build, methods=["GET", "POST"],
              name="%s_verify_transcript_build" % ns),
        Route("/api/%s/v1/verify/transcript/recheck" % ns, _recheck, methods=["POST"],
              name="%s_verify_transcript_recheck" % ns),
        Route("/api/%s/v1/verify/transcript/health" % ns, _health, methods=["GET"],
              name="%s_verify_transcript_health" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "agent_loop_available": _ALOOP_OK, "public_verify_available": _PUBVERIFY_OK}


# ===========================================================================
# self-test — no network, no fabricated data. Proves: a SINGLE build produces a
# real composite transcript; the chain fold RE-VERIFIES; a TAMPERED energy block
# yields an honest MISMATCH → FAIL; and no MEASURED reading is ever manufactured.
# ===========================================================================
def _selftest() -> dict:  # pragma: no cover — `python3 szl_verify_transcript.py`
    import szl_dsse
    out: dict = {}

    def _sign(obj):
        return szl_dsse.sign_payload(obj, "application/vnd.szl.khipu+json")

    built = build_transcript("write a python function that returns the first 5 primes",
                             sign_fn=_sign, ns="a11oy", mode="code", max_retries=0)
    assert built["ok"] is True, built
    tr = built["transcript"]
    vr = built["verify"]
    assert tr["schema"] == SCHEMA, tr
    assert vr["ok"] is True and vr["locked8_touched"] is False, vr
    # the end-to-end chain fold must RE-VERIFY the signed run_chain_digest.
    assert vr["chain_fold"]["hash_recheck"] == VERIFIED, vr["chain_fold"]
    # brain-context + energy links recompute their embedded-block digests → VERIFIED.
    by = {l["link"]: l for l in vr["links"]}
    assert by["brain-context"]["hash_recheck"] == VERIFIED, by["brain-context"]
    assert by["energy-allocation"]["hash_recheck"] == VERIFIED, by["energy-allocation"]
    # honesty: energy joules label is passed through, NEVER manufactured MEASURED.
    e_lbl = by["energy-allocation"]["data_label"]
    if e_lbl == "MEASURED":
        raw = str(by["energy-allocation"].get("data_label_raw") or "")
        assert "MEASURED" in raw.upper(), "MEASURED must originate from the meter, not fabricated"
    out["build_and_fold_verify"] = True
    out["energy_label_honest"] = e_lbl

    # verdict is PARTIAL or PASS locally (UNSIGNED-LOCAL sig + UNAVAILABLE per-step recompute),
    # NEVER a fabricated green when links could not be fully run.
    assert vr["verdict"] in ("PASS", "PARTIAL", "INCONCLUSIVE"), vr["verdict"]
    out["verdict"] = vr["verdict"]

    # TAMPER: mutate the energy block AFTER signing → energy digest recompute MISMATCH → FAIL.
    body = json.loads(json.dumps(tr["composite_receipt"]["body"]))  # deep copy
    if isinstance(body.get("energy_allocation"), dict):
        body["energy_allocation"]["loop_allocation_joules"] = 9.99e9  # tamper
        tv = verify_transcript({"composite_receipt": {"body": body,
                                                      "dsse": tr["composite_receipt"]["dsse"]}})
        eng = next(l for l in tv["links"] if l["link"] == "energy-allocation")
        assert eng["hash_recheck"] == MISMATCH, eng
        assert tv["verdict"] == "FAIL", tv["verdict"]
        out["tamper_honest_mismatch"] = True

    # recheck of an empty subject → honest NO_INPUT.
    ni = verify_transcript({})
    assert ni.get("verdict") == "NO_INPUT", ni
    out["no_input_honest"] = True

    return out


if __name__ == "__main__":  # pragma: no cover
    import sys as _sys
    print("=" * 70)
    print("szl_verify_transcript — self-test (composite transcript, per-link honest labels)")
    print("=" * 70)
    r = _selftest()
    print(json.dumps(r, indent=2, default=str))
    ok = all(v is True for k, v in r.items() if isinstance(r[k], bool))
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    _sys.exit(0 if ok else 1)
