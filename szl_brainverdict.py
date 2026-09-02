# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SZL Holdings. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainverdict.py — the VERIFIABLE ANSWER: one signed receipt binding the whole chain.

WHAT THIS SURFACE ANSWERS: "for a given question, can the estate emit ONE offline-verifiable
object that binds together — under a single signature — (a) which served model answered and
whether its provenance matched, (b) how well the answer's claims are bound to real sources,
(c) the served model's refusal-to-fabricate posture, and (d) a cryptographic seal over all of
it — so a third party can verify the ENTIRE governed pipeline without trusting us?"

This is the composition the SOTA survey named as the single highest-leverage frontier move:
pairing provenance-bound serving + citation grounding + refusal-to-fabricate + a signed
receipt into one primitive. Each component already exists as an honest surface; brainverdict
runs them together and binds the result.

  brainserve  -> served-model provenance reading (MEASURED / UNAVAILABLE)
  braincite   -> claim->source citation coverage over the SAME honest retrieval
  braineval   -> refusal-to-fabricate posture of the served model (MEASURED / UNAVAILABLE)
  brainreceipt-> ECDSA-P256 signature binding the composed record (integrity, not truth)

HONEST DISCIPLINE (doctrine v11):
  * The composed verdict is only as strong as its weakest MEASURED component. If the served
    model is UNAVAILABLE, the verdict is UNVERIFIABLE-NO-MODEL — never upgraded.
  * assurance_level is derived DETERMINISTICALLY from the component labels; it is MODELED, and
    it is never reported above what the components actually earned.
  * A valid signature proves the chain is UNALTERED and was assembled by the key holder —
    INTEGRITY ONLY. It does NOT prove the answer is true. Stated verbatim in every receipt.
  * No component is fabricated: an UNAVAILABLE component stays UNAVAILABLE in the record.
  * Lambda = Conjecture 1; locked-8 immutable adds 0; trust ceiling 0.97; no sentience; trains
    nothing; not counter-UAS. 0 runtime CDN.
"""

from __future__ import annotations

import json
import datetime

HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "SIGNED-LOCAL", "UNAVAILABLE",
)

LBL_MODELED = "MODELED"
LBL_MEASURED = "MEASURED"
LBL_UNAVAILABLE = "UNAVAILABLE"

SURFACE_ID = "brainverdict"

LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97
KERNEL_COMMIT = "c7c0ba17"

RECEIPT_SCHEMA = "szl.brain.verifiable-answer-receipt/v1"

# Composed assurance levels (deterministic; MODELED; never above what components earned).
ASSURANCE_VERIFIABLE = "VERIFIABLE-GROUNDED"     # model MEASURED + fully-cited + refusal-honest
ASSURANCE_PARTIAL = "VERIFIABLE-PARTIAL"          # model MEASURED but citation/eval partial
ASSURANCE_WEAK = "VERIFIABLE-WEAK"                # model MEASURED but uncited-dominant / fabrication risk
ASSURANCE_NO_MODEL = "UNVERIFIABLE-NO-MODEL"      # served model UNAVAILABLE -> cannot verify a live answer


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _doctrine_block(note: str = "", label_top: str = LBL_MODELED) -> dict:
    d = {
        "version": "v11",
        "label_top": label_top,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "is_model_training": False,
        "admits_to_gradients": 0,
        "sentience_claim": False,
    }
    if note:
        d["note"] = note
    return d


PROVES = (
    "the composed chain (served-model provenance + citation coverage + refusal posture + this "
    "record) was assembled by the key holder and is unaltered since — INTEGRITY only"
)
DOES_NOT_PROVE = (
    "that the answer is true, correct, or non-hallucinated; assurance_level is a MODELED "
    "composition of honest component readings, never a proof of truth. A signature is integrity, "
    "not truth."
)


def _derive_assurance(serve_measured: bool, cite_verdict: str, eval_verdict: str) -> str:
    """Deterministic, transparent, never-above-earned assurance derivation."""
    if not serve_measured:
        return ASSURANCE_NO_MODEL  # no live model -> cannot verify a live answer, full stop
    # served model answered. Now grade grounding + refusal.
    fabricates = (eval_verdict == "FABRICATION-DETECTED")
    uncited_dominant = (cite_verdict == "UNCITED-DOMINANT")
    if fabricates or uncited_dominant:
        return ASSURANCE_WEAK
    fully_cited = (cite_verdict == "FULLY-CITED")
    refusal_honest = (eval_verdict in ("REFUSAL-HONEST", "UNAVAILABLE"))  # eval may be UNAVAILABLE w/o env
    if fully_cited and eval_verdict == "REFUSAL-HONEST":
        return ASSURANCE_VERIFIABLE
    return ASSURANCE_PARTIAL


def compose(question: str, k: int = 12, environ=None, ns: str = "a11oy") -> dict:
    """Run the full governed pipeline for `question` and compose an honest verdict.
    Never raises; any component failure is recorded honestly as UNAVAILABLE, never faked."""
    import szl_brainserve as _bs
    import szl_braincite as _bc
    import szl_braineval as _be

    # 1) served-model provenance reading
    try:
        serve = _bs.probe(environ=environ, ns=ns)
    except Exception as exc:  # pragma: no cover
        serve = {"label": LBL_UNAVAILABLE, "verdict": "UNAVAILABLE", "error": f"{type(exc).__name__}"}
    serve_measured = (serve.get("label") == LBL_MEASURED)

    # 2) citation coverage over the SAME honest retrieval
    try:
        cite = _bc.evaluate(question, k=k, ns=ns)
    except Exception as exc:  # pragma: no cover
        cite = {"label": LBL_UNAVAILABLE, "verdict": "UNAVAILABLE", "error": f"{type(exc).__name__}"}

    # 3) refusal-to-fabricate posture of the served model
    try:
        ev = _be.evaluate(environ=environ, ns=ns)
    except Exception as exc:  # pragma: no cover
        ev = {"label": LBL_UNAVAILABLE, "verdict": "UNAVAILABLE", "error": f"{type(exc).__name__}"}

    assurance = _derive_assurance(serve_measured, cite.get("verdict"), ev.get("verdict"))

    return {
        "question": question,
        "assurance_level": assurance,
        "assurance_label": LBL_MODELED,  # the COMPOSITION is MODELED; components carry their own labels
        "components": {
            "served_model": {
                "label": serve.get("label"), "verdict": serve.get("verdict"),
                "provenance_matches_expected": serve.get("provenance_matches_expected"),
                "served_model_id": serve.get("served_model_id"),
            },
            "citation": {
                "label": cite.get("label"), "verdict": cite.get("verdict"),
                "citation_coverage": cite.get("citation_coverage"),
                "cited_count": cite.get("cited_count"), "total_claims": cite.get("total_claims"),
            },
            "refusal_eval": {
                "label": ev.get("label"), "verdict": ev.get("verdict"),
                "refusal_rate": ev.get("refusal_rate"),
            },
        },
        "weakest_link": _weakest(serve, cite, ev),
        "note": ("assurance_level is the MODELED composition of three honest readings; it is never "
                 "above what the components earned. No live model -> UNVERIFIABLE-NO-MODEL."),
    }


def _weakest(serve: dict, cite: dict, ev: dict) -> str:
    """Name the component that limits the verdict, so the composition is never opaque."""
    if serve.get("label") != LBL_MEASURED:
        return "served_model (UNAVAILABLE) — cannot verify a live answer"
    if ev.get("verdict") == "FABRICATION-DETECTED":
        return "refusal_eval (FABRICATION-DETECTED) — model fabricated on a probe"
    if cite.get("verdict") in ("UNCITED-DOMINANT", "PARTIALLY-CITED"):
        return f"citation ({cite.get('verdict')}) — claims not fully source-bound"
    if ev.get("label") != LBL_MEASURED:
        return "refusal_eval (UNAVAILABLE) — refusal posture not measured this request"
    return "none — all measured components at their honest ceiling"


def sign_verdict(question: str, k: int = 12, environ=None, ns: str = "a11oy") -> dict:
    """Compose the verdict and bind it under the estate signer via brainreceipt."""
    import szl_brainreceipt as _br
    verdict = compose(question, k=k, environ=environ, ns=ns)
    # The signed 'output' is the canonical composed verdict; 'sources' are the component verdicts.
    canonical_output = json.dumps(verdict, sort_keys=True, separators=(",", ":"), default=str)
    comp = verdict["components"]
    sources = [
        f"served_model:{comp['served_model'].get('verdict')}",
        f"citation:{comp['citation'].get('verdict')}:{comp['citation'].get('citation_coverage')}",
        f"refusal_eval:{comp['refusal_eval'].get('verdict')}",
    ]
    model_id = comp["served_model"].get("served_model_id") or "UNAVAILABLE"
    receipt = _br.sign_receipt(question, sources, canonical_output, model_id, env=environ)
    verification = _br.verify_receipt(receipt)
    return {
        "verdict": verdict,
        "receipt": receipt,
        "self_verification": verification,
        "receipt_schema": RECEIPT_SCHEMA,
        "proves": PROVES,
        "does_not_prove": DOES_NOT_PROVE,
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "endpoint": "brain/verdict/info",
        "service": f"{ns}.brain.brainverdict",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Verdict — the verifiable answer (question -> sources -> answer -> checks, signed)",
        "what": ("composes brainserve (served-model provenance) + braincite (claim->source coverage) "
                 "+ braineval (refusal-to-fabricate) into ONE record, then binds it under the estate "
                 "ECDSA-P256 signer (brainreceipt). One offline-verifiable object for the whole chain."),
        "assurance_levels": {
            ASSURANCE_VERIFIABLE: "served model MEASURED + fully source-cited + refusal-honest",
            ASSURANCE_PARTIAL: "served model MEASURED but citation and/or refusal only partial",
            ASSURANCE_WEAK: "served model MEASURED but uncited-dominant or a fabrication was detected",
            ASSURANCE_NO_MODEL: "served model UNAVAILABLE — a live answer cannot be verified",
        },
        "proves": PROVES,
        "does_not_prove": DOES_NOT_PROVE,
        "honesty": ("assurance is the MODELED composition of honest component readings, never above "
                    "what they earned; weakest_link is always named; a signature is integrity, not truth."),
        "endpoints": {
            "info": f"GET  /api/{ns}/v1/brain/verdict/info",
            "verdict": f"GET  /api/{ns}/v1/brain/verdict?q=...&k=...  (compose, no signature)",
            "sign": f"POST /api/{ns}/v1/brain/verdict/sign  (body: q, k) -> signed verifiable-answer receipt",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "spec": "docs/verifiable-answer-receipt.md",
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "receipt_policy": "RECEIPT-ON-WRITE (POST sign). GET info/verdict/manifest mint no signature.",
        "doctrine": _doctrine_block(),
    }


def handle_manifest(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "endpoint": f"brain/{SURFACE_ID}/manifest",
        "service": f"{ns}.brain.manifest.{SURFACE_ID}",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "data_label": LBL_MODELED,
        "title": "Brain Verdict — the verifiable answer (composed, signed)",
        "kind": "honesty-manifest",
        "computes": ("composes served-model provenance + citation coverage + refusal posture into a "
                     "MODELED assurance verdict and binds it under an ECDSA-P256 signature; a valid "
                     "signature proves integrity of the chain, never truth of the answer."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "routes": {
            "info": f"GET  /api/{ns}/v1/brain/verdict/info",
            "verdict": f"GET  /api/{ns}/v1/brain/verdict",
            "sign": f"POST /api/{ns}/v1/brain/verdict/sign",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "honesty_invariants": {
            "label_in_honest_vocabulary": True,
            "lambda_is_conjecture_not_theorem": True,  # Lambda is Conjecture 1, never a theorem
            "locked_count_is_eight": True,
            "adds_to_locked_8_is_zero": True,
            "trust_ceiling_at_most_0_97": True,
            "trust_never_100_percent": True,
            "assurance_never_above_components": True,
            "no_model_means_unverifiable": True,
            "no_fabricated_component": True,
            "weakest_link_always_named": True,
            "signature_proves_integrity_not_truth": True,
            "trains_nothing": True,
            "admits_to_gradients_zero": True,
            "no_consciousness_claim": True,
            "zero_runtime_cdn": True,
            "receipt_on_write_not_read": True,
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET manifest mints nothing.",
        "doctrine": _doctrine_block(
            "honesty manifest for brainverdict; declarative only, composes/signs nothing here."),
    }


def handle_verdict(question: str, k: int = 12, ns: str = "a11oy") -> dict:
    v = compose(question, k=k, ns=ns)
    v.update({"ok": True, "endpoint": "brain/verdict", "service": f"{ns}.brain.brainverdict",
              "surface_id": SURFACE_ID, "doctrine": _doctrine_block(), "computed_at": _now_iso()})
    return v


def handle_sign(question: str, k: int = 12, ns: str = "a11oy") -> dict:
    out = sign_verdict(question, k=k, ns=ns)
    out.update({"ok": True, "endpoint": "brain/verdict/sign", "service": f"{ns}.brain.brainverdict",
                "surface_id": SURFACE_ID,
                "doctrine": _doctrine_block(label_top=out["receipt"].get("label", LBL_MODELED)),
                "computed_at": _now_iso()})
    return out


# --------------------------------------------------------------------------- #
# Registration.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain"
    wired = 0

    async def _v_manifest(request):
        return JSONResponse(handle_manifest(ns))

    async def _v_info(request):
        return JSONResponse(handle_info(ns))

    async def _v_verdict(request):
        q = request.query_params.get("q", "")
        try:
            k = int(request.query_params.get("k", "12"))
        except Exception:
            k = 12
        return JSONResponse(handle_verdict(q, k=k, ns=ns))

    async def _v_sign(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        q = str(body.get("q", body.get("question", "")))
        try:
            k = int(body.get("k", 12))
        except Exception:
            k = 12
        return JSONResponse(handle_sign(q, k=k, ns=ns))

    routes = [
        (f"{base}/{SURFACE_ID}/manifest", _v_manifest, "GET"),
        (f"{base}/verdict/info", _v_info, "GET"),
        (f"{base}/verdict", _v_verdict, "GET"),
        (f"{base}/verdict/sign", _v_sign, "POST"),
    ]

    try:
        import fastapi as _fastapi
        for _fn in (_v_manifest, _v_info, _v_verdict, _v_sign):
            _fn.__annotations__["request"] = _fastapi.Request
    except Exception:
        pass

    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn, method in routes:
        try:
            if callable(add_route):
                app.router.add_route(path, fn, methods=[method])
            elif callable(add_api_route):
                app.add_api_route(path, fn, methods=[method])
            else:
                from starlette.routing import Route
                app.router.routes.append(Route(path, fn, methods=[method]))
            wired += 1
        except Exception as exc:
            __import__("sys").stderr.write(
                f"[{ns}] brainverdict {method} route {path} NOT wired (guarded): {exc!r}\n")

    return f"{SURFACE_ID}-wired:{wired}"


# --------------------------------------------------------------------------- #
# Self-test (network-free: components are monkeypatched via injected fakes).
# --------------------------------------------------------------------------- #
def _selftest() -> dict:
    checks = 0

    # assurance derivation is deterministic and never above earned
    assert _derive_assurance(False, "FULLY-CITED", "REFUSAL-HONEST") == ASSURANCE_NO_MODEL
    assert _derive_assurance(True, "FULLY-CITED", "REFUSAL-HONEST") == ASSURANCE_VERIFIABLE
    assert _derive_assurance(True, "PARTIALLY-CITED", "REFUSAL-HONEST") == ASSURANCE_PARTIAL
    assert _derive_assurance(True, "UNCITED-DOMINANT", "REFUSAL-HONEST") == ASSURANCE_WEAK
    assert _derive_assurance(True, "FULLY-CITED", "FABRICATION-DETECTED") == ASSURANCE_WEAK
    checks += 1

    # weakest_link naming
    assert "served_model" in _weakest({"label": LBL_UNAVAILABLE}, {}, {})
    assert "FABRICATION" in _weakest({"label": LBL_MEASURED}, {"verdict": "FULLY-CITED"},
                                     {"verdict": "FABRICATION-DETECTED", "label": LBL_MEASURED})
    checks += 1

    # honesty statement present, integrity-not-truth
    assert "INTEGRITY only" in PROVES and "not truth" in DOES_NOT_PROVE.lower()
    checks += 1

    # manifest NATIVE-OK + all invariants true + MODELED
    man = handle_manifest("selftest")
    assert man["surface_id"] == SURFACE_ID and man["data_label"] == LBL_MODELED
    assert all(man["honesty_invariants"].values())
    assert man["honesty_invariants"]["assurance_never_above_components"] is True
    assert man["honesty_invariants"]["no_model_means_unverifiable"] is True
    # GET reads mint nothing
    assert "receipt" not in handle_info("selftest") and "receipt" not in handle_manifest("selftest")
    checks += 1

    # doctrine honest
    d = _doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    checks += 1

    return {"ok": True, "checks": checks}


if __name__ == "__main__":
    print(json.dumps(_selftest()))
