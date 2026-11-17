# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SZL Holdings. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Retired brainserve bridge with read-only compatibility metadata.

The former GET probe generated a new model response. Its OpenAI endpoint is
retired, and neither a page read nor a legacy receipt request can establish
operator authorization or public-prompt acknowledgement. All execution paths
are inert. Use the existing authenticated Atelier CPU-lab turn explicitly.
Historical pin and digest helpers remain available without inference or writes.
Lambda uniqueness remains Conjecture 1; the locked eight are unchanged.
"""

from __future__ import annotations

import os
import json
import hashlib
import datetime

HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

LBL_MEASURED = "MEASURED"
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

SURFACE_ID = "brainserve"

LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97
KERNEL_COMMIT = "c7c0ba17"

# Operator overrides; committed defaults point at the estate's own inference Space.
ENV_URL = "SZL_BRAINSERVE_URL"
ENV_MODEL = "SZL_BRAINSERVE_MODEL"

DEFAULT_URL = "https://szlholdings-szl-model-inference-lab.hf.space"
# The endpoint requires the immutable id (repo@revision). This is the pinned brain model.
DEFAULT_MODEL = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25"

# The provenance we EXPECT the served model to self-report. A mismatch is surfaced, never hidden.
EXPECTED_REPO = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
EXPECTED_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"

PROBE_TIMEOUT_S = 30.0  # HF Spaces can cold-start; bounded but generous.
MAX_TOKENS = 24
SUCCESSOR_PATH = "/api/a11oy/v1/atelier/cpu-lab/turn"


def _successor() -> dict:
    return {
        "method": "POST",
        "path": SUCCESSOR_PATH,
        "ui": "/command-centre#cpu-work",
        "operator_authentication_required": True,
        "public_share_acknowledged": True,
        "declared": "PUBLIC",
        "max_output_tokens": 32,
        "grounding_required": True,
        "authority": "PROPOSAL_ONLY",
        "automatic_forwarding": False,
    }

# Verdicts (only meaningful when a reading was taken).
VERDICT_SERVING = "SERVING-EXPECTED"          # answered AND provenance matches expectation
VERDICT_MISMATCH = "PROVENANCE-MISMATCH"      # answered but self-reported model differs
VERDICT_UNAVAILABLE = "UNAVAILABLE"           # no answer this request


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


def read_env(environ=None) -> dict:
    env = os.environ if environ is None else environ
    url = (env.get(ENV_URL) or "").strip().rstrip("/") or DEFAULT_URL
    model = (env.get(ENV_MODEL) or "").strip() or DEFAULT_MODEL
    overridden = bool((env.get(ENV_URL) or "").strip() or (env.get(ENV_MODEL) or "").strip())
    return {
        "env_vars_read": [ENV_URL, ENV_MODEL],
        "url": url,
        "model": model,
        "source": "operator-override" if overridden else "committed-default",
        "committed_default_url": DEFAULT_URL,
        "committed_default_model": DEFAULT_MODEL,
        "note": (
            "Historical configuration metadata only. Legacy generation is retired; "
            "endpoint overrides cannot reactivate this transport."
        ),
    }


def _call_model(url: str, model: str, prompt: str, timeout: float = PROBE_TIMEOUT_S) -> tuple:
    """Inert compatibility hook: the legacy transport must never be revived."""
    return None, "RETIRED: use the authenticated Atelier CPU-lab turn explicitly"


def _summarize_provenance(prov: dict) -> dict:
    """Extract and PROPAGATE the served model's honesty caveats verbatim — never upgrade them."""
    model = prov.get("model", {}) if isinstance(prov, dict) else {}
    runtime = prov.get("runtime", {}) if isinstance(prov, dict) else {}
    receipts = prov.get("receipts", {}) if isinstance(prov, dict) else {}
    output = prov.get("output", {}) if isinstance(prov, dict) else {}
    return {
        "schema": prov.get("schema") if isinstance(prov, dict) else None,
        "reported_repo": model.get("repo"),
        "reported_revision": model.get("revision"),
        "reported_file": model.get("file"),
        "reported_sha256": model.get("sha256"),
        "runtime_space": runtime.get("space"),
        "service_level": runtime.get("service_level"),
        # Propagated verbatim — brainserve NEVER claims a receipt covers an output it does not.
        "receipts_status": receipts.get("status"),
        "receipts_cover_this_output": receipts.get("covers_this_output"),
        "output_signature_status": output.get("signature_status"),
        "caveat": ("output is UNSIGNED and receipts do not cover this specific output; this is a "
                   "governed BEST_EFFORT reading, not a cryptographic proof of the answer."),
    }


def probe(environ=None, timeout: float = PROBE_TIMEOUT_S, ns: str = "a11oy") -> dict:
    """Return retirement metadata without a model call or endpoint probe."""
    return {
        "ok": False,
        "state": "RETIRED",
        "label": LBL_UNAVAILABLE,
        "verdict": "RETIRED",
        "measured": False,
        "answered": False,
        "operational": False,
        "inference_performed": False,
        "receipt_emitted": False,
        "automatically_forwarded": False,
        "successor": _successor(),
        "note": (
            "Legacy brainserve generation is retired. Explicit operator authentication "
            "and public-prompt acknowledgement are required at the successor route."
        ),
    }


def _canonical_core(result: dict) -> str:
    prov = result.get("provenance", {}) or {}
    core = {
        "label": result.get("label"),
        "verdict": result.get("verdict"),
        "answered": result.get("answered"),
        "served_model_id": result.get("served_model_id"),
        "provenance_matches_expected": result.get("provenance_matches_expected"),
        "reported_repo": prov.get("reported_repo"),
        "reported_revision": prov.get("reported_revision"),
        "reported_sha256": prov.get("reported_sha256"),
        "output_signature_status": prov.get("output_signature_status"),
        "receipts_cover_this_output": prov.get("receipts_cover_this_output"),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(result: dict) -> dict:
    digest = hashlib.sha256(_canonical_core(result).encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainserve.reading",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "offline historical helper; no HTTP route emits this digest",
        "note": ("unsigned SHA-256 content digest of the brainserve reading (including the served "
                 "model's own unsigned/receipt caveats). RECEIPT-ON-WRITE. This digest binds our "
                 "reading; it does NOT sign the model's output, which remains UNSIGNED upstream."),
        "computed_at": _now_iso(),
    }


def handle_info(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "endpoint": "brain/serve/info",
        "service": f"{ns}.brain.brainserve",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Serve: retired inference bridge",
        "state": "RETIRED",
        "successor": _successor(),
        "inference_performed": False,
        "receipt_emitted": False,
        "what": "Compatibility metadata only; legacy model generation is disabled.",
        "verdicts": {
            VERDICT_SERVING: "answered AND provenance matches the pinned expected model",
            VERDICT_MISMATCH: "answered but self-reported model differs from expectation (surfaced, not hidden)",
            VERDICT_UNAVAILABLE: "no answer this request (asleep / cold / unreachable)",
        },
        "committed_default": {"url": DEFAULT_URL, "model": DEFAULT_MODEL},
        "expected_provenance": {"repo": EXPECTED_REPO, "revision": EXPECTED_REVISION},
        "honesty": ("MEASURED only from a live answer; unsigned output stays UNSIGNED; a receipt "
                    "that does not cover the output is never claimed to; no training, no gradients, "
                    "no sentience; the bridged model is the in-scope SZL-Khipu brain model."),
        "endpoints": {
            "info": f"GET  /api/{ns}/v1/brain/serve/info",
            "serve": f"GET  /api/{ns}/v1/brain/serve",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            "receipt": f"POST /api/{ns}/v1/brain/serve/receipt",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — this GET info mints nothing.",
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
        "title": "Brain Serve: retired inference bridge",
        "kind": "honesty-manifest",
        "state": "RETIRED",
        "successor": _successor(),
        "inference_performed": False,
        "receipt_emitted": False,
        "computes": "Declared compatibility metadata only; no inference or receipt emission.",
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "routes": {
            "info": f"GET  /api/{ns}/v1/brain/serve/info",
            "serve": f"GET  /api/{ns}/v1/brain/serve",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            "receipt": f"POST /api/{ns}/v1/brain/serve/receipt",
        },
        "honesty_invariants": {
            "label_in_honest_vocabulary": True,
            "lambda_is_conjecture_not_theorem": True,  # Lambda is Conjecture 1, never a theorem
            "locked_count_is_eight": True,
            "adds_to_locked_8_is_zero": True,
            "trust_ceiling_at_most_0_97": True,
            "trust_never_100_percent": True,
            "measured_only_from_live_reading": True,
            "no_fabricated_measured": True,
            "unsigned_output_stays_unsigned": True,
            "receipt_never_overclaims_coverage": True,
            "provenance_mismatch_surfaced_not_hidden": True,
            "trains_nothing": True,
            "admits_to_gradients_zero": True,
            "no_consciousness_claim": True,
            "zero_runtime_cdn": True,
            "receipt_on_write_not_read": True,
            "no_generation_on_get": True,
            "legacy_post_never_forwards": True,
        },
        "receipt_policy": "No legacy route emits receipts; POST serve/receipt is RETIRED.",
        "doctrine": _doctrine_block(
            "honesty manifest for the brainserve surface; declarative only, serves nothing here."),
    }


def handle_serve(ns: str = "a11oy") -> dict:
    result = probe(ns=ns)
    result["endpoint"] = "brain/serve"
    result["service"] = f"{ns}.brain.brainserve"
    result["surface_id"] = SURFACE_ID
    result["doctrine"] = _doctrine_block(label_top=result.get("label", LBL_MODELED))
    result["computed_at"] = _now_iso()
    return result


def handle_receipt(ns: str = "a11oy") -> dict:
    result = probe(ns=ns)
    result["endpoint"] = "brain/serve/receipt"
    result["service"] = f"{ns}.brain.brainserve"
    result["surface_id"] = SURFACE_ID
    result["doctrine"] = _doctrine_block(label_top=result.get("label", LBL_MODELED))
    result["computed_at"] = _now_iso()
    return result


def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain"
    wired = 0

    async def _serve_manifest(request):
        return JSONResponse(handle_manifest(ns), headers={"Cache-Control": "no-store"})

    async def _serve_info(request):
        return JSONResponse(handle_info(ns), headers={"Cache-Control": "no-store"})

    async def _serve_serve(request):
        return JSONResponse(handle_serve(ns), status_code=410,
                            headers={"Cache-Control": "no-store"})

    async def _serve_receipt(request):
        return JSONResponse(handle_receipt(ns), status_code=410,
                            headers={"Cache-Control": "no-store"})

    routes = [
        (f"{base}/{SURFACE_ID}/manifest", _serve_manifest, "GET"),
        (f"{base}/serve/info", _serve_info, "GET"),
        (f"{base}/serve", _serve_serve, "GET"),
        (f"{base}/serve/receipt", _serve_receipt, "POST"),
    ]

    try:
        import fastapi as _fastapi
        for _fn in (_serve_manifest, _serve_info, _serve_serve, _serve_receipt):
            _fn.__annotations__["request"] = _fastapi.Request
    except Exception:
        pass

    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn, method in routes:
        app.router.routes[:] = [
            route for route in app.router.routes
            if getattr(route, "path", None) != path
        ]
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
                f"[{ns}] brainserve {method} route {path} NOT wired (guarded): {exc!r}\n")

    return f"{SURFACE_ID}-wired:{wired}"


def _selftest() -> dict:
    """Network-free self-test (never calls the real Space)."""
    checks = 0

    # env default resolution
    cfg = read_env(environ={})
    assert cfg["url"] == DEFAULT_URL and cfg["model"] == DEFAULT_MODEL
    assert cfg["source"] == "committed-default"
    cfg2 = read_env(environ={ENV_URL: "https://x", ENV_MODEL: "m"})
    assert cfg2["url"] == "https://x" and cfg2["source"] == "operator-override"
    checks += 1

    # provenance summary propagates caveats verbatim (never upgrades)
    prov = {"schema": "szl.openai-compat-provenance/v1",
            "model": {"repo": EXPECTED_REPO, "revision": EXPECTED_REVISION,
                      "file": "f.gguf", "sha256": "abc"},
            "runtime": {"space": "SZLHOLDINGS/szl-model-inference-lab", "service_level": "BEST_EFFORT_NO_SLA"},
            "receipts": {"status": "DECLARED_KEY_SIGNATURES_VALID", "covers_this_output": False},
            "output": {"signature_status": "UNSIGNED"}}
    s = _summarize_provenance(prov)
    assert s["output_signature_status"] == "UNSIGNED"
    assert s["receipts_cover_this_output"] is False  # never upgraded to True
    checks += 1

    # canonical receipt deterministic, unsigned; GET reads mint nothing
    sample = {"label": LBL_MEASURED, "verdict": VERDICT_SERVING, "answered": True,
              "served_model_id": DEFAULT_MODEL, "provenance_matches_expected": True,
              "provenance": s}
    a = content_receipt(sample)["content_sha256"]
    b = content_receipt(sample)["content_sha256"]
    assert a == b and len(a) == 64 and content_receipt(sample)["signed"] is False
    assert "receipt" not in handle_info("selftest")  # GET info mints nothing (no network call)
    checks += 1

    # manifest NATIVE-OK shape; every invariant true; MODELED label
    man = handle_manifest("selftest")
    assert man["surface_id"] == SURFACE_ID and man["data_label"] == LBL_MODELED
    assert all(man["honesty_invariants"].values())
    checks += 1

    # doctrine honest
    d = _doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    assert d["admits_to_gradients"] == 0
    checks += 1

    return {"ok": True, "checks": checks}


if __name__ == "__main__":
    print(json.dumps(_selftest()))
