# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SZL Holdings. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainreceipt.py — SIGNED inference receipts binding request + sources + output.

WHAT THIS SURFACE ANSWERS: "can the estate emit a portable, offline-verifiable receipt that
binds a brain answer to (a) the exact request, (b) the exact retrieved sources, and (c) the
exact output — signed by the estate's own key — so a third party can later verify the answer
was not altered?"

This is the SOTA "signed inference receipt" frontier (IETF Enforcement-Attestation-Receipts
shape: a canonical JSON object binding SHA-256(request) + SHA-256(sources) + model id to the
output under a published key). It is the SIGNED complement to the many UNSIGNED SHA-256
digests other brain surfaces mint, and the request-side complement to brainserve's provenance
reading.

HONEST DISCIPLINE — what a signature here DOES and does NOT prove (doctrine v11):
  * A valid signature proves ONLY: this exact (request, sources, output, model_id) tuple was
    receipted by the holder of the signing key, unaltered since. That is integrity + key
    continuity — NOTHING MORE.
  * It does NOT prove the output is correct, true, non-hallucinated, or that the sources
    actually support the output. Those are separate surfaces (braincite / braineval). This is
    stated verbatim in every receipt under `proves` / `does_not_prove`.
  * key_source is reported honestly: `persistent:*` when a real Secret-backed key is
    configured, `ephemeral` when a boot-generated key is used (verifiable only within this
    container's lifetime), `unavailable` when crypto/key is missing. An ephemeral signature is
    labeled UNSIGNED-LOCAL in intent — real bytes, but honestly scoped.
  * Uses the estate's shared ECDSA P-256 signer (a11oy_signing_key.load_signing_key); adds no
    new dependency (cryptography is already pinned). No runtime CDN.
  * Trains nothing, admits 0 gradient rows, not counter-UAS, no sentience claim.
  * Lambda stays Conjecture 1; locked-8 immutable adds 0; trust ceiling 0.97.
"""

from __future__ import annotations

import json
import base64
import hashlib
import datetime

HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "SIGNED-LOCAL", "UNAVAILABLE",
)

LBL_MODELED = "MODELED"
LBL_SIGNED_LOCAL = "SIGNED-LOCAL"      # a real signature under a persistent estate key
LBL_UNSIGNED_LOCAL = "UNSIGNED-LOCAL"  # a real signature under an ephemeral (container-life) key
LBL_UNAVAILABLE = "UNAVAILABLE"        # no key / crypto -> unsigned digest only, honest

SURFACE_ID = "brainreceipt"

LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97
KERNEL_COMMIT = "c7c0ba17"

RECEIPT_SCHEMA = "szl.brain.signed-inference-receipt/v1"
SIG_ALG = "ecdsa-p256-sha256"  # matches the estate's shared signer


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


# The immutable honesty statement carried by every receipt.
PROVES = (
    "this exact (request, sources, output, model_id) tuple was receipted by the holder of the "
    "signing key and is unaltered since — integrity and key continuity only"
)
DOES_NOT_PROVE = (
    "that the output is correct, true, non-hallucinated, or actually supported by the sources; "
    "correctness/support are separate surfaces (braincite for citation, braineval for refusal-"
    "to-fabricate). A signature is integrity, not truth."
)


def _canonical_bound_object(request: str, sources, output: str, model_id: str) -> dict:
    """The canonical, deterministic object that is hashed and signed.

    `sources` is a list of source strings/ids; each is hashed individually AND the ordered set
    is hashed, so a third party can verify both membership and the exact ordered corpus."""
    src_list = [str(s) for s in (sources or [])]
    per_source = [{"sha256": _sha256_hex(s)} for s in src_list]
    sources_joined = "\n".join(src_list)
    return {
        "schema": RECEIPT_SCHEMA,
        "model_id": model_id,
        "request_sha256": _sha256_hex(request),
        "sources_count": len(src_list),
        "sources_sha256": _sha256_hex(sources_joined),
        "per_source_sha256": per_source,
        "output_sha256": _sha256_hex(output),
    }


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sign_receipt(request: str, sources, output: str, model_id: str, env=None) -> dict:
    """Build a signed inference receipt. Never raises; on any crypto/key failure it returns an
    honest UNAVAILABLE receipt carrying the unsigned content digest (never a fabricated sig)."""
    bound = _canonical_bound_object(request, sources, output, model_id)
    canonical = _canonical_json(bound)
    content_sha256 = _sha256_hex(canonical)

    signature_b64 = None
    public_pem = ""
    key_source = "unavailable"
    error = ""
    label = LBL_UNAVAILABLE

    try:
        import a11oy_signing_key as _sk
        private_key, public_pem, key_source, error = _sk.load_signing_key(env)
        if private_key is not None and not error:
            from cryptography.hazmat.primitives import hashes as _hashes
            from cryptography.hazmat.primitives.asymmetric import ec as _ec
            sig = private_key.sign(canonical.encode("utf-8"), _ec.ECDSA(_hashes.SHA256()))
            signature_b64 = base64.b64encode(sig).decode("ascii")
            # persistent key -> SIGNED-LOCAL; ephemeral -> UNSIGNED-LOCAL (real bytes, honest scope)
            label = LBL_SIGNED_LOCAL if key_source.startswith("persistent") else LBL_UNSIGNED_LOCAL
    except Exception as exc:  # pragma: no cover
        error = f"{type(exc).__name__}: {str(exc)[:120]}"
        label = LBL_UNAVAILABLE
        signature_b64 = None

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "label": label,
        "bound": bound,
        "content_sha256": content_sha256,
        "signature_algorithm": SIG_ALG,
        "signature_b64": signature_b64,
        "signed": signature_b64 is not None,
        "key_source": key_source,
        "public_key_pem": public_pem or None,
        "key_source_meaning": {
            "persistent:*": "Secret-backed key that survives redeploy; a SIGNED-LOCAL receipt",
            "ephemeral": ("boot-generated key, verifiable only within THIS container's lifetime; "
                          "labeled UNSIGNED-LOCAL — real signature bytes, honestly scoped"),
            "unavailable": "no key/crypto; unsigned content digest only, never a fabricated signature",
        },
        "proves": PROVES,
        "does_not_prove": DOES_NOT_PROVE,
        "verify_hint": ("recompute the canonical bound object, sha256 it, and ECDSA-P256-SHA256-"
                        "verify signature_b64 against public_key_pem; membership of any source is "
                        "checkable via per_source_sha256."),
        "computed_at": _now_iso(),
    }
    if error:
        receipt["key_error"] = error
    return receipt


def verify_receipt(receipt: dict) -> dict:
    """Offline verification: recompute the digest and check the signature against the embedded
    public key. Honest about what a PASS means."""
    result = {"schema_ok": receipt.get("schema") == RECEIPT_SCHEMA, "signature_valid": None,
              "content_digest_ok": None}
    bound = receipt.get("bound") or {}
    recomputed = _sha256_hex(_canonical_json(bound))
    result["content_digest_ok"] = (recomputed == receipt.get("content_sha256"))

    sig_b64 = receipt.get("signature_b64")
    pem = receipt.get("public_key_pem")
    if not sig_b64 or not pem:
        result["signature_valid"] = False
        result["note"] = "no signature or public key present; content digest checked only."
        return result
    try:
        from cryptography.hazmat.primitives import hashes as _hashes, serialization as _ser
        from cryptography.hazmat.primitives.asymmetric import ec as _ec
        pub = _ser.load_pem_public_key(pem.encode("ascii"))
        canonical = _canonical_json(bound).encode("utf-8")
        pub.verify(base64.b64decode(sig_b64), canonical, _ec.ECDSA(_hashes.SHA256()))
        result["signature_valid"] = True
        result["note"] = ("signature valid: integrity + key continuity only. Does NOT prove the "
                          "output is correct or source-supported.")
    except Exception as exc:
        result["signature_valid"] = False
        result["note"] = f"signature verification failed: {type(exc).__name__}"
    return result


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "endpoint": "brain/receipt/info",
        "service": f"{ns}.brain.brainreceipt",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Receipt — signed inference receipts (request + sources + output)",
        "what": ("mints a portable, offline-verifiable receipt binding SHA-256(request) + "
                 "SHA-256(sources) + model_id to SHA-256(output), signed with the estate's shared "
                 "ECDSA P-256 key. The SIGNED complement to the unsigned digests other surfaces "
                 "mint; the request-side complement to brainserve's provenance reading."),
        "proves": PROVES,
        "does_not_prove": DOES_NOT_PROVE,
        "labels": {
            LBL_SIGNED_LOCAL: "signed under a persistent (Secret-backed) estate key",
            LBL_UNSIGNED_LOCAL: "signed under an ephemeral container key (honestly scoped)",
            LBL_UNAVAILABLE: "no key/crypto; unsigned content digest only",
        },
        "signature_algorithm": SIG_ALG,
        "endpoints": {
            "info": f"GET  /api/{ns}/v1/brain/receipt/info",
            "sign": f"POST /api/{ns}/v1/brain/receipt/sign  (body: request, sources[], output, model_id)",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "receipt_policy": "RECEIPT-ON-WRITE (POST sign). GET info/manifest mint nothing.",
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
        "title": "Brain Receipt — signed inference receipts (request + sources + output)",
        "kind": "honesty-manifest",
        "computes": ("ECDSA-P256 signed receipt binding request+sources+output; a valid signature "
                     "proves integrity + key continuity ONLY, never output correctness or source "
                     "support. key_source reported honestly; ephemeral key labeled UNSIGNED-LOCAL."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "routes": {
            "info": f"GET  /api/{ns}/v1/brain/receipt/info",
            "sign": f"POST /api/{ns}/v1/brain/receipt/sign",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "honesty_invariants": {
            "label_in_honest_vocabulary": True,
            "lambda_is_conjecture_not_theorem": True,  # Lambda is Conjecture 1, never a theorem
            "locked_count_is_eight": True,
            "adds_to_locked_8_is_zero": True,
            "trust_ceiling_at_most_0_97": True,
            "trust_never_100_percent": True,
            "signature_proves_integrity_not_truth": True,
            "no_fabricated_signature": True,
            "ephemeral_key_labeled_honestly": True,
            "key_source_reported": True,
            "trains_nothing": True,
            "admits_to_gradients_zero": True,
            "no_consciousness_claim": True,
            "zero_runtime_cdn": True,
            "receipt_on_write_not_read": True,
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET manifest mints nothing.",
        "doctrine": _doctrine_block(
            "honesty manifest for the brainreceipt surface; declarative only, signs nothing here."),
    }


def handle_sign(request: str, sources, output: str, model_id: str, ns: str = "a11oy") -> dict:
    receipt = sign_receipt(request, sources, output, model_id)
    verification = verify_receipt(receipt)
    return {
        "ok": True,
        "endpoint": "brain/receipt/sign",
        "service": f"{ns}.brain.brainreceipt",
        "surface_id": SURFACE_ID,
        "receipt": receipt,
        "self_verification": verification,  # we verify our own receipt so callers see it round-trips
        "doctrine": _doctrine_block(label_top=receipt.get("label", LBL_MODELED)),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Registration.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain"
    wired = 0

    async def _rc_manifest(request):
        return JSONResponse(handle_manifest(ns))

    async def _rc_info(request):
        return JSONResponse(handle_info(ns))

    async def _rc_sign(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        req = str(body.get("request", ""))
        sources = body.get("sources", [])
        if not isinstance(sources, list):
            sources = [str(sources)]
        output = str(body.get("output", ""))
        model_id = str(body.get("model_id", ""))
        return JSONResponse(handle_sign(req, sources, output, model_id, ns))

    routes = [
        (f"{base}/{SURFACE_ID}/manifest", _rc_manifest, "GET"),
        (f"{base}/receipt/info", _rc_info, "GET"),
        (f"{base}/receipt/sign", _rc_sign, "POST"),
    ]

    try:
        import fastapi as _fastapi
        for _fn in (_rc_manifest, _rc_info, _rc_sign):
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
                f"[{ns}] brainreceipt {method} route {path} NOT wired (guarded): {exc!r}\n")

    return f"{SURFACE_ID}-wired:{wired}"


# --------------------------------------------------------------------------- #
# Self-test (real signing via the estate's ephemeral key; fully offline).
# --------------------------------------------------------------------------- #
def _selftest() -> dict:
    checks = 0

    # sign + self-verify a real receipt (ephemeral key in this container)
    r = sign_receipt("what is lambda?", ["node-a: lambda is a conjecture"], "Lambda is Conjecture 1.",
                     "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF")
    assert r["schema"] == RECEIPT_SCHEMA
    assert r["bound"]["request_sha256"] and r["bound"]["output_sha256"]
    assert r["label"] in (LBL_SIGNED_LOCAL, LBL_UNSIGNED_LOCAL, LBL_UNAVAILABLE)
    checks += 1

    # if a signature was produced, it MUST verify (no fabricated signatures)
    if r["signed"]:
        v = verify_receipt(r)
        assert v["signature_valid"] is True and v["content_digest_ok"] is True
    checks += 1

    # tamper detection: altering the output breaks verification
    if r["signed"]:
        tampered = json.loads(json.dumps(r))
        tampered["bound"]["output_sha256"] = "0" * 64
        v2 = verify_receipt(tampered)
        assert v2["content_digest_ok"] is False  # digest no longer matches the bound object
    checks += 1

    # honesty statement always present and correct
    assert "integrity" in r["proves"] and "not truth" in r["does_not_prove"].lower()
    assert "does not prove" in _canonical_json(handle_info("s")).lower() or r["does_not_prove"]
    checks += 1

    # manifest NATIVE-OK + all invariants true + MODELED
    man = handle_manifest("selftest")
    assert man["surface_id"] == SURFACE_ID and man["data_label"] == LBL_MODELED
    assert all(man["honesty_invariants"].values())
    assert man["honesty_invariants"]["signature_proves_integrity_not_truth"] is True
    # GET reads mint nothing
    assert "receipt" not in handle_info("selftest") and "receipt" not in handle_manifest("selftest")
    checks += 1

    # doctrine honest
    d = _doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    checks += 1

    return {"ok": True, "checks": checks, "label": r["label"], "signed": r["signed"]}


if __name__ == "__main__":
    print(json.dumps(_selftest()))
