# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""
a11oy forge-family wall — GET /api/forge/family

The public evidence wall for the owner-forged model family:
  * SZL-Forge-1.5B-ReceiptAgent   (owner keyId e7f01810aaa97394)
  * SZL-Khipu-1.5B-BrainNavigator (owner keyId 89540347a69b789e)

Doctrine: provenance, not vibes. Every band is re-verified SERVER-SIDE on every
request from the owner-signed receipt files fetched from the public HF model
repos (receipt BYTES are cached briefly to spare the Hub; the cryptographic
verification itself runs on every request and is never cached or skipped).
Nothing is asserted that an ed25519 signature does not prove:

  per receipt (training + eval):
    - the canonical string must reproduce BYTE-EXACTLY from the payload
      (sorted keys, compact separators — the forge kit signer's rules)
    - the ed25519 signature must verify over the canonical bytes
    - the embedded SPKI and keyId must equal owner_pubkey.json's, and the
      keyId must equal sha256(SPKI DER)[:16]
  per model:
    - eval payload.trainingReceiptSha256 must equal sha256(training canonical)
    - keyTrust: "PINNED" when the A11OY_*_OWNER_KEYID env pin matches the
      verified keyId; a set-but-different pin is "PIN_MISMATCH" and FAILS THE
      BAND CLOSED; no pin set is "REPO_DECLARED".

Counts (planValid / grounding / abstain / hallucinatedCitations) are DERIVED
from the verified eval payload — never hand-typed. Failures are loud: a band
that cannot be verified says so explicitly; nothing silently degrades.

Additive module per Space convention: register(app) adds the route and
front-moves it so the exact JSON path wins over the SPA history fallback and
the /api proxy. No new dependencies (httpx + cryptography are pinned in the
image).
"""

import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_ROUTE = "/api/forge/family"
_HF = "https://huggingface.co"
_RECEIPT_FILES = ("owner_pubkey.json", "training_receipt.signed.json", "eval_receipt.signed.json")
_CACHE_TTL_SECONDS = 300  # receipt BYTES only; verification always re-runs
_RECONCILIATION_STATE = "ARTIFACT_BYTES_RECONCILED_MEASURED_NOT_PROMOTED"
_RECONCILIATION_PATH = (
    Path(__file__).resolve().parent
    / "model_release"
    / "receipt-agent"
    / "reconciliation"
    / "receipt-agent-artifact-reconciliation.v1.json"
)

_MODELS = (
    {
        "model": "receiptagent",
        "displayName": "SZL-Forge-1.5B-ReceiptAgent",
        "hfRepo": "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent",
        "pinEnv": "A11OY_OWNER_KEYID",
        "artifactReconciliation": True,
    },
    {
        "model": "khipu",
        "displayName": "SZL-Khipu-1.5B-BrainNavigator",
        "hfRepo": "SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator",
        "pinEnv": "A11OY_KHIPU_OWNER_KEYID",
    },
)

# (repo, immutable revision) -> {"at": epoch, "files": {name: bytes}}
_byte_cache: dict[tuple[str, str], dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict) -> str:
    """The forge kit's canonical form: sorted keys, compact separators, raw UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


async def _fetch_receipt_bytes(
    client: httpx.AsyncClient,
    repo: str,
    revision: str,
) -> dict:
    cache_key = (repo, revision)
    cached = _byte_cache.get(cache_key)
    if cached and (time.time() - cached["at"]) < _CACHE_TTL_SECONDS:
        return cached
    files = {}
    for name in _RECEIPT_FILES:
        resp = await client.get(f"{_HF}/{repo}/resolve/{revision}/{name}")
        resp.raise_for_status()
        files[name] = resp.content
    entry = {"at": time.time(), "files": files}
    _byte_cache[cache_key] = entry
    return entry


async def _fetch_public_head(client: httpx.AsyncClient, repo: str) -> str:
    """Observe the current public head independently of cached receipt bytes."""
    response = await client.get(f"{_HF}/api/models/{repo}")
    response.raise_for_status()
    payload = response.json()
    revision = payload.get("sha") if isinstance(payload, dict) else None
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise ValueError("Hugging Face model API did not return a lowercase hex head")
    return revision


def _load_receipt_agent_reconciliation() -> dict:
    """Load and self-verify the frozen, non-promoting reconciliation artifact."""
    value = json.loads(_RECONCILIATION_PATH.read_text(encoding="utf-8"))
    recorded = value.get("reconciliation_sha256")
    unsigned = dict(value)
    unsigned.pop("reconciliation_sha256", None)
    computed = _sha256_hex(_canonical(unsigned).encode("utf-8"))
    if recorded != computed:
        raise ValueError("ReceiptAgent reconciliation self-digest mismatch")
    if value.get("state") != _RECONCILIATION_STATE:
        raise ValueError("ReceiptAgent reconciliation state mismatch")
    if value.get("repository") != "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent":
        raise ValueError("ReceiptAgent reconciliation repository mismatch")
    if value.get("authorization") != {
        "trained": False,
        "uploaded": False,
        "promoted": False,
        "deployed": False,
    }:
        raise ValueError("ReceiptAgent reconciliation overstates authorization")
    binding = value.get("exact_qualified_artifact_binding") or {}
    head = value.get("current_public_head_equivalence") or {}
    if binding.get("verified") is not True or head.get("verified") is not True:
        raise ValueError("ReceiptAgent reconciliation is not fully verified")
    return value


def _verify_one_receipt(receipt: dict, owner_spki_b64: str, owner_key_id: str, expected_kind_word: str) -> dict:
    """Run every check for one signed receipt. Returns {check_name: bool} + meta."""
    checks = {}
    payload = receipt.get("payload") or {}
    canonical = receipt.get("canonical") or ""
    checks["canonicalReproducesFromPayload"] = _canonical(payload) == canonical
    checks["embeddedSpkiMatchesOwner"] = receipt.get("publicKeySpkiBase64") == owner_spki_b64
    checks["embeddedKeyIdMatchesOwner"] = receipt.get("keyId") == owner_key_id
    checks["payloadKeyIdMatchesOwner"] = payload.get("keyId") == owner_key_id
    kind = str(payload.get("kind", ""))
    checks["kindLooksRight"] = expected_kind_word in kind.lower()
    sig_ok = False
    try:
        spki_der = base64.b64decode(owner_spki_b64, validate=True)
        public_key = load_der_public_key(spki_der)
        if isinstance(public_key, Ed25519PublicKey):
            public_key.verify(
                base64.b64decode(receipt.get("signatureBase64", ""), validate=True),
                canonical.encode("utf-8"),
            )
            sig_ok = True
    except Exception:
        sig_ok = False
    checks["ed25519SignatureVerifies"] = sig_ok
    return {
        "checks": checks,
        "allPassed": all(checks.values()),
        "kind": kind,
        "canonicalSha256": _sha256_hex(canonical.encode("utf-8")),
        "payload": payload,
    }


def _band_for_model(
    cfg: dict,
    raw_files: dict,
    fetched_at_epoch: float,
    public_head_revision: str | None = None,
) -> dict:
    """Build one fully-verified wall band. Verification runs on every call."""
    owner = json.loads(raw_files["owner_pubkey.json"])
    training = json.loads(raw_files["training_receipt.signed.json"])
    evaluation = json.loads(raw_files["eval_receipt.signed.json"])

    owner_spki_b64 = owner.get("publicKeySpkiBase64", "")
    owner_key_id = owner.get("keyId", "")
    owner_checks = {
        "ownerAlgoIsEd25519": owner.get("algo") == "ed25519",
        "ownerKeyIdDerivesFromSpki": (
            _sha256_hex(base64.b64decode(owner_spki_b64))[:16] == owner_key_id
            if owner_spki_b64 else False
        ),
    }

    training_result = _verify_one_receipt(training, owner_spki_b64, owner_key_id, "train")
    eval_result = _verify_one_receipt(evaluation, owner_spki_b64, owner_key_id, "eval")

    chain_ok = (
        eval_result["payload"].get("trainingReceiptSha256")
        == _sha256_hex((training.get("canonical") or "").encode("utf-8"))
    )

    pin_env = cfg["pinEnv"]
    pinned_value = os.environ.get(pin_env, "").strip()
    if not pinned_value:
        key_trust = "REPO_DECLARED"
        pin_ok = True
    elif pinned_value == owner_key_id:
        key_trust = "PINNED"
        pin_ok = True
    else:
        key_trust = "PIN_MISMATCH"  # fail CLOSED
        pin_ok = False

    training_verified = owner_checks["ownerAlgoIsEd25519"] and owner_checks["ownerKeyIdDerivesFromSpki"] and training_result["allPassed"] and pin_ok
    eval_verified = owner_checks["ownerAlgoIsEd25519"] and owner_checks["ownerKeyIdDerivesFromSpki"] and eval_result["allPassed"] and chain_ok and pin_ok
    receipt_signatures_verified = training_verified and eval_verified
    verification_layers = {
        "receiptSignatureValidity": {
            "verified": receipt_signatures_verified,
            "training": training_verified,
            "evaluation": eval_verified,
            "trustBoundary": {
                "PINNED": "PINNED_OWNER_KEY",
                "PIN_MISMATCH": "PIN_MISMATCH_FAIL_CLOSED",
                "REPO_DECLARED": (
                    "REPOSITORY_DECLARED_KEY_NOT_INDEPENDENTLY_PINNED"
                ),
            }[key_trust],
        },
        "exactQualifiedArtifactBinding": {
            "verified": None,
            "state": "NOT_EVALUATED_FOR_THIS_PROFILE",
        },
        "currentPublicHeadEquivalence": {
            "verified": None,
            "state": "NOT_EVALUATED_FOR_THIS_PROFILE",
            "observedHead": public_head_revision,
        },
        "promotion": {
            "authorized": False,
            "state": "NOT_PROMOTED",
        },
    }
    profile_state = None
    fully_verified = receipt_signatures_verified
    if cfg.get("artifactReconciliation"):
        reconciliation = _load_receipt_agent_reconciliation()
        artifact_binding = reconciliation["exact_qualified_artifact_binding"]
        frozen_head = reconciliation["public_head_revision"]
        current_head_equivalent = public_head_revision == frozen_head
        verification_layers["exactQualifiedArtifactBinding"] = {
            "verified": artifact_binding["verified"] is True,
            "state": _RECONCILIATION_STATE,
            "qualifiedRevision": reconciliation["qualified_revision"],
            "qualificationReceiptSha256": artifact_binding[
                "qualification_receipt_sha256"
            ],
            "digestDomain": artifact_binding["digest_domain"],
        }
        verification_layers["currentPublicHeadEquivalence"] = {
            "verified": current_head_equivalent,
            "state": (
                "INFERENCE_BEARING_BLOBS_EQUIVALENT_TO_QUALIFIED_REVISION"
                if current_head_equivalent
                else "PUBLIC_HEAD_CHANGED_RECONCILIATION_REQUIRED"
            ),
            "observedHead": public_head_revision,
            "reconciledHead": frozen_head,
            "failClosedOnHeadChange": True,
        }
        fully_verified = (
            receipt_signatures_verified
            and artifact_binding["verified"] is True
            and current_head_equivalent
        )
        profile_state = (
            _RECONCILIATION_STATE
            if fully_verified
            else "ARTIFACT_RECONCILIATION_FAILED_CLOSED"
        )
    ep = eval_result["payload"]
    tp = training_result["payload"]

    return {
        "model": cfg["model"],
        "displayName": cfg["displayName"],
        "hfRepo": cfg["hfRepo"],
        "keyId": owner_key_id,
        "keyTrust": key_trust,
        "pinEnv": pin_env,
        "verified": fully_verified,
        "profileState": profile_state,
        "status": (
            (["TRAINED_RECEIPT_VERIFIED"] if training_verified else ["TRAINING_RECEIPT_FAILED"])
            + (["EVAL_RECEIPT_VERIFIED"] if eval_verified else ["EVAL_RECEIPT_FAILED"])
            + (
                [
                    "ARTIFACT_BYTES_RECONCILED_MEASURED",
                    "CURRENT_PUBLIC_HEAD_EQUIVALENT",
                    "NOT_PROMOTED",
                ]
                if cfg.get("artifactReconciliation") and fully_verified
                else (
                    ["ARTIFACT_RECONCILIATION_FAILED_CLOSED", "NOT_PROMOTED"]
                    if cfg.get("artifactReconciliation")
                    else []
                )
            )
        ),
        "verificationLayers": verification_layers,
        "checks": {
            "owner": owner_checks,
            "training": training_result["checks"],
            "eval": eval_result["checks"],
            "evalChainsToTraining": chain_ok,
        },
        "derived": {
            "baseModel": tp.get("baseModel"),
            "trainedAt": tp.get("trainedAt"),
            "finalTrainLoss": tp.get("finalTrainLoss"),
            "evaluatedAt": ep.get("evaluatedAt"),
            "planValid": ep.get("planValid"),
            "planTotal": ep.get("planTotal"),
            "groundingCorrect": ep.get("groundingCorrect"),
            "groundingTotal": ep.get("groundingTotal"),
            "abstainCorrect": ep.get("abstainCorrect"),
            "abstainTotal": ep.get("abstainTotal"),
            "hallucinatedCitationCount": ep.get("hallucinatedCitationCount"),
        },
        "receiptFiles": {
            name: {"sha256": _sha256_hex(raw_files[name]), "bytes": len(raw_files[name])}
            for name in _RECEIPT_FILES
        },
        "receiptBytesCacheAgeSeconds": round(time.time() - fetched_at_epoch, 1),
    }


async def _forge_family_handler():
    bands = []
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for cfg in _MODELS:
            try:
                public_head_revision = await _fetch_public_head(
                    client, cfg["hfRepo"]
                )
                entry = await _fetch_receipt_bytes(
                    client,
                    cfg["hfRepo"],
                    public_head_revision,
                )
                bands.append(
                    _band_for_model(
                        cfg,
                        entry["files"],
                        entry["at"],
                        public_head_revision,
                    )
                )
            except Exception as band_error:  # loud, honest, isolated per band
                bands.append({
                    "model": cfg["model"],
                    "displayName": cfg["displayName"],
                    "hfRepo": cfg["hfRepo"],
                    "verified": False,
                    "status": ["UNAVAILABLE"],
                    "error": f"{type(band_error).__name__}: {band_error}",
                })
    return {
        "ok": all(b.get("verified") is True for b in bands),
        "wall": "forge-family",
        "servedFrom": "a-11-oy.com (a11oy flagship Space)",
        "verifier": {
            "mode": "ed25519 via cryptography, server-side",
            "perRequest": True,
            "note": "receipt bytes cached briefly; verification never cached",
        },
        "generatedAt": _now_iso(),
        "models": bands,
    }


def register(app) -> str:
    """Additive registration + front-move (exact route must beat SPA fallback)."""
    app.add_api_route(_ROUTE, _forge_family_handler, methods=["GET"], include_in_schema=False)
    for index, route in enumerate(app.router.routes):
        if getattr(route, "path", None) == _ROUTE:
            app.router.routes.insert(0, app.router.routes.pop(index))
            break
    return f"{_ROUTE} (bands: {', '.join(m['model'] for m in _MODELS)})"
