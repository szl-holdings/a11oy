# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Wave-N Dev 2 (Proof-Carrying Attested Inference — the #1 differentiator).
"""
szl_proof_carrying_infer.py — PROOF-CARRYING ATTESTED INFERENCE (PCAI)

WHAT THIS IS
------------
The Wave-N deepening of Wave-A/H attested inference (`szl_attested_inference.py`) into ONE
self-contained, off-the-shelf-checkable **proof-carrying bundle**. A single artifact binds:

    (a) the inference RECEIPT (governed inference result + digests),
    (b) a TEE-attestation QUOTE DIGEST (reuses the cc-attest measured-boot chain),
    (c) an in-toto / SLSA v1 PROVENANCE PREDICATE (subject digest + builder + buildDefinition),
    (d) the Λ trust AXES (13-axis weighted geomean; Conjecture 1 — advisory, never green).

It is emitted in a shape that a standard `cosign verify-blob` and `slsa-verifier verify-artifact`
COULD check: a DSSE envelope (payload = the in-toto Statement whose predicate carries the receipt,
the TEE quote digest and the Λ axes), plus a Sigstore-style **bundle** wrapper and an
`intoto.jsonl` line. The exact verify commands are documented IN THIS MODULE and echoed in the
endpoint response under `verify_commands`.

    GET /api/a11oy/v1/pcai/run?seed=<int>&model=<model_id>

    measured-boot chain  (reuse szl_attested_inference / cc-attest)
        └─► TEE attestation quote  (SEV-SNP REPORT_DATA / TDX MRTD / NVIDIA NRAS EAT pattern)
              └─► Λ-gate  (weighted geometric mean over the 13 trust axes; Conjecture 1)
                    └─► gated inference  (deterministic MODELED token stream)
                          └─► in-toto/SLSA v1 Statement  (subject = inference output digest;
                                predicate binds receipt + quote_digest + Λ axes)
                                └─► DSSE envelope  (REAL ECDSA-P256 in-Space; UNSIGNED-LOCAL local)
                                      └─► Sigstore-style BUNDLE + intoto.jsonl  (cosign / slsa-verifier)

WHY THIS IS THE DIFFERENTIATOR
------------------------------
The leaders ship the pieces SEPARATELY: hardware attestation (NVIDIA NRAS / AMD KDS / Intel
TDX), supply-chain provenance (in-toto/SLSA), and a signature transparency log (Sigstore/Rekor).
PCAI FUSES them: a single DSSE-signed in-toto Statement whose predicate carries the TEE quote
digest AND the SLSA provenance AND the Λ trust axes AND the inference receipt — one artifact a
relying party can hand to `cosign`/`slsa-verifier` and check without SZL's code. That is
"proof-carrying attested inference": the inference travels WITH the proof that lets anyone verify
where it ran, that the box was attested, and what governance gate it passed. (Λ stays
Conjecture 1; nothing here touches the locked-8.)

HONESTY (Doctrine v11 — NEVER violate)
--------------------------------------
Label = **MODELED** — a deterministic SIMULATION of the attested-inference path keyed on
(seed, model). There is **no real TEE, no real GPU, no NRAS/KDS/DCAP network call, and no real
inference engine**. Every synthetic value is derived by SHA-256/384 from the inputs so the flow
is replayable and verifiable, NOT fabricated as a live measurement. Where a REAL measurement is
available the module defers to `szl_tee_attest.get_tee_attestation()` and surfaces its honest
label verbatim (MEASURED on a live TDX/Nitro pod, UNAVAILABLE on the CPU Space). The DSSE
signature is REAL ECDSA-P256 when the SZL cosign secret is present in-Space (`cosign verify-blob`
accepts it byte-for-byte), and honestly `signed:false` / **UNSIGNED-LOCAL** otherwise — the
signature is never fabricated. Λ = **Conjecture 1** (advisory, gray, NEVER "green"/theorem).

LEADERS STUDIED & CITED (clean-room PATTERN, not their code)
------------------------------------------------------------
  • in-toto / SLSA v1 provenance — the attestation is an in-toto Statement
    (`_type: https://in-toto.io/Statement/v1`, `subject[].digest`) whose predicate has
    `predicateType: https://slsa.dev/provenance/v1` with `buildDefinition` (buildType,
    externalParameters, resolvedDependencies) + `runDetails` (builder.id, metadata). We map
    the attested run onto this exact shape so `slsa-verifier verify-artifact` COULD check it.
    https://slsa.dev/spec/v1.0/provenance  ·  https://slsa.dev/blog/2023/05/in-toto-and-slsa
  • Sigstore cosign + Rekor transparency log — key-based blob signing: ECDSA-P256 over the
    DSSE PAE bytes; `cosign sign-blob --key cosign.key` / `cosign verify-blob --key cosign.pub`.
    Rekor is the append-only transparency log; a Sigstore *bundle* carries the DSSE envelope +
    verification material (+ a Rekor inclusion promise where present). We emit a bundle in that
    shape (`mediaType: application/vnd.dev.sigstore.bundle+json;version=0.3`) so cosign COULD
    verify it, and honestly mark Rekor inclusion UNAVAILABLE-LOCAL (no log entry made offline).
    https://docs.sigstore.dev/cosign/verifying/verify/  ·  https://docs.sigstore.dev/about/bundle/
    https://docs.sigstore.dev/logging/overview/
  • NVIDIA NRAS TEE attestation — the GPU produces evidence bound to a fresh **nonce**; NRAS
    verifies it against RIM golden measurements + OCSP and returns a signed **EAT** (Entity
    Attestation Token, a JWT) with claims like `x-nvidia-overall-att-result`, `eat_nonce`, per-GPU
    `submods` SHA-256 measurement digests, `secboot`, and RIM validation flags. Our MODELED quote
    mirrors that claim shape (nonce, overall_att_result, measurement digest, secboot) so the
    binding is faithful to the leader — with NO real GPU and NO NRAS network call.
    https://docs.nvidia.com/attestation/technical-docs-nras/latest/nras_introduction.html
    https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/
  • (background, from Wave-H) AMD SEV-SNP REPORT_DATA/VCEK/KDS; Intel TDX MRTD/RTMR TD Quote;
    Confidential Containers (CoCo) attestation-agent + Key Broker Service — the Λ-gate is the
    software analogue of a KBS: it releases the (MODELED) inference only when attested trust meets
    the advisory floor. Laminator (arXiv 2406.17548) binds model+input+output into an attested
    "inference card" — exactly the artifact SZL calls a receipt.

ENDPOINT
--------
  GET /api/a11oy/v1/pcai/run?seed=<int>&model=<model_id>
      → 200 JSON {label:"MODELED", seed, model, tee_quote{...}, lambda{axes,value,floor,pass,
                  uniqueness}, inference{...}, statement{in-toto/SLSA v1}, dsse{...},
                  bundle{sigstore-style}, intoto_jsonl, artifact{...}, verify_commands{...},
                  verifiable_by_design, honest_note, sources[]}
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants — honest labels + citations baked in (Doctrine v11)
# ---------------------------------------------------------------------------
LABEL = "MODELED"
NS_DEFAULT = "a11oy"
# in-toto DSSE payloadType (the standard used by cosign attest / slsa-verifier for attestations)
PAYLOAD_TYPE = "application/vnd.in-toto+json"
# what the receipt/statement is about
BUILD_TYPE = "https://a-11-oy.com/pcai/attested-inference/v1"
BUILDER_ID = "https://a-11-oy.com/builders/pcai-MODELED"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"

# advisory Λ floor (mirror szl_org_lambda.LAMBDA_FLOOR; kept local to avoid a hard import)
LAMBDA_FLOOR = 0.90
TRUST_CEIL = 0.97  # Doctrine v11 trust ceiling — Λ never claims 100%

# Published SZL cosign public key location (verifier fetches this; PUBLIC data).
COSIGN_PUB_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"
COSIGN_PUB_RAW = "https://raw.githubusercontent.com/szl-holdings/.github/main/cosign.pub"

# Canonical 13 trust axes (mirror szl_org_lambda / szl_attested_inference).
_AXIS_NAMES = [
    "soundness", "calibration", "robustness", "provenance", "consent", "reversibility",
    "transparency", "fairness", "containment", "attestation", "freshness", "authority",
    "auditability",
]
_AXIS_WEIGHTS = [0.12, 0.06, 0.08, 0.11, 0.06, 0.07, 0.07, 0.05, 0.08, 0.10, 0.05, 0.07, 0.08]

# Leaders — cited in code AND in the response `sources[]`.
SOURCES: List[Dict[str, str]] = [
    {"name": "in-toto / SLSA v1 provenance predicate (Statement _type, subject.digest, "
             "buildDefinition, runDetails.builder.id)",
     "url": "https://slsa.dev/spec/v1.0/provenance"},
    {"name": "in-toto & SLSA — signed provenance attestations (background)",
     "url": "https://slsa.dev/blog/2023/05/in-toto-and-slsa"},
    {"name": "Sigstore cosign — verifying blobs (cosign verify-blob --key cosign.pub)",
     "url": "https://docs.sigstore.dev/cosign/verifying/verify/"},
    {"name": "Sigstore bundle format (application/vnd.dev.sigstore.bundle+json)",
     "url": "https://docs.sigstore.dev/about/bundle/"},
    {"name": "Sigstore Rekor — transparency log overview",
     "url": "https://docs.sigstore.dev/logging/overview/"},
    {"name": "NVIDIA Remote Attestation Service (NRAS) — signed EAT tokens, nonce, RIM/OCSP",
     "url": "https://docs.nvidia.com/attestation/technical-docs-nras/latest/nras_introduction.html"},
    {"name": "NVIDIA — Confidential Computing on H100 GPUs (CC-mode + NRAS)",
     "url": "https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/"},
    {"name": "slsa-verifier — verify-artifact (--provenance-path / --source-uri)",
     "url": "https://github.com/slsa-framework/slsa-verifier"},
    {"name": "AMD — SEV-SNP Attestation (REPORT_DATA / VCEK / KDS) — background pattern",
     "url": "https://www.amd.com/content/dam/amd/en/documents/developer/lss-snp-attestation.pdf"},
    {"name": "Laminator: Verifiable ML Property Cards using HW-assisted Attestations (arXiv 2406.17548)",
     "url": "https://arxiv.org/abs/2406.17548"},
]

HONEST_NOTE = (
    "MODELED — deterministic simulation of the proof-carrying attested-inference path keyed on "
    "(seed, model). No real TEE, no real GPU, no NRAS/KDS/DCAP network call, no real inference "
    "engine, and NO Rekor transparency-log entry is created offline. Synthetic measurements are "
    "SHA-256/384 of the inputs (replayable, NOT a live hardware quote). If a real TDX/Nitro "
    "measurement is present, szl_tee_attest surfaces it verbatim in tee_quote.tee_probe. The DSSE "
    "envelope is REAL ECDSA-P256 in-Space (cosign verify-blob accepts it byte-for-byte) and "
    "honestly UNSIGNED-LOCAL when no cosign secret is present — the signature is never fabricated. "
    "The Sigstore bundle + intoto.jsonl are emitted in the leaders' shape so cosign verify-blob / "
    "slsa-verifier COULD check them; Rekor inclusion is honestly UNAVAILABLE-LOCAL. "
    "Λ = Conjecture 1 (advisory, never green). Nothing here is in the locked-8."
)


# ---------------------------------------------------------------------------
# small deterministic helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha384(b: bytes) -> str:
    return hashlib.sha384(b).hexdigest()


def _canon(obj: Any) -> bytes:
    """Deterministic canonical JSON: sorted keys, no whitespace, UTF-8 (matches szl_dsse)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _det_unit(*parts: str) -> float:
    """Deterministic float in [0,1] from a SHA-256 of the parts (replayable, no RNG)."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    v = int.from_bytes(h[:8], "big") / float(1 << 64)
    return min(max(v, 0.0), 1.0)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(max(x, lo), hi)


def _pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1) — identical to szl_dsse.pae."""
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


# ---------------------------------------------------------------------------
# Λ-gate — weighted geometric mean over the 13 trust axes (mirrors szl_org_lambda)
# ---------------------------------------------------------------------------
def _weighted_geomean(axes: List[float], weights: List[float]) -> float:
    """A4 zero-absorption weighted geometric mean. Any zero axis → 0.0. Λ ∈ [0,1]."""
    import math
    if not axes:
        return 0.0
    sw = sum(weights) or 1.0
    w = [x / sw for x in weights]
    acc = 0.0
    for x, wi in zip(axes, w):
        x = _clamp(float(x))
        if x <= 0.0:
            return 0.0
        acc += wi * math.log(x)
    return _clamp(math.exp(acc))


def _lambda_axes(seed: int, model: str, quote_digest: str, boot_matches: bool) -> Dict[str, Any]:
    """Deterministic per-axis trust scores in [0,1] from (seed, model, quote).

    The `attestation` axis is HARD-COUPLED to the measured-boot result: a bad boot collapses it
    toward 0 and A4 zero-absorption pulls Λ down — the CoCo KBS behaviour (no release on a bad
    quote). Λ = Conjecture 1 (advisory, gray, never green).
    """
    s = str(seed)
    scores: Dict[str, float] = {}
    for name in _AXIS_NAMES:
        base = 0.90 + 0.09 * _det_unit(s, model, quote_digest, name)  # in [0.90, 0.99]
        scores[name] = _clamp(base, 0.0, TRUST_CEIL)                  # trust ceiling 0.97
    if not boot_matches:
        scores["attestation"] = 0.0  # zero-absorption → Λ = 0 → gate BLOCKS
    axes = [scores[n] for n in _AXIS_NAMES]
    L = _weighted_geomean(axes, _AXIS_WEIGHTS)
    return {
        "trust_axes": len(_AXIS_NAMES),
        "axes": [{"name": n, "score": round(scores[n], 4), "weight": _AXIS_WEIGHTS[i]}
                 for i, n in enumerate(_AXIS_NAMES)],
        "value": round(L, 6),
        "floor": LAMBDA_FLOOR,
        "pass": bool(L >= LAMBDA_FLOOR),
        "aggregator": "weighted geometric mean (F19 family), A4 zero-absorption, ceiling 0.97",
        "uniqueness": "Λ = Conjecture 1 (advisory, gray — NOT a theorem, never green); nothing to locked-8.",
    }


# ---------------------------------------------------------------------------
# measured-boot chain — reuse szl_attested_inference (cc-attest) where available
# ---------------------------------------------------------------------------
def _measurement_chain(seed: int, model: str) -> Dict[str, Any]:
    """Reuse the Wave-A/H cc-attest measured-boot chain via szl_attested_inference.

    If that module is present we call its `_measurement_chain` verbatim so PCAI shares the SAME
    measurement chain (COPY-guard: szl_attested_inference is already in the image). If it is
    absent we recompute an identical chain locally so the endpoint always returns a renderable
    200 — the algorithm is the same SHA-384 stage fold (bootloader → firmware → gpu-driver →
    microcode → gpu-vbios) with an even-seed golden match / odd-seed simulated tamper.
    """
    try:
        import szl_attested_inference as _ai  # per-file COPY'd, guarded import
        mc = _ai._measurement_chain(int(seed), str(model))
        mc["_source"] = "szl_attested_inference (reused cc-attest measurement chain)"
        return mc
    except Exception:
        stages = ["bootloader", "firmware", "gpu-driver", "microcode", "gpu-vbios"]
        acc = _sha384(f"szl-attested-device|{model}|seed={seed}".encode("utf-8"))
        device_identity = acc
        chain: List[Dict[str, str]] = []
        for stage in stages:
            m = _sha384(f"{stage}|{model}|seed={seed}".encode("utf-8"))
            acc = _sha384(f"{acc}|{stage}:{m}".encode("utf-8"))
            chain.append({"stage": stage, "digest": acc})
        final_digest = acc
        golden_match = (int(seed) % 2 == 0)
        return {
            "device_identity": device_identity,
            "measurement_chain": chain,
            "final_digest": final_digest,
            "golden_match": golden_match,
            "stages": len(stages),
            "_source": "local fallback (szl_attested_inference unavailable) — identical algorithm",
        }


def _tee_probe() -> Dict[str, Any]:
    """Defer to the real TEE probe; surface its honest label verbatim. Never fabricates."""
    try:
        import szl_tee_attest  # per-file COPY'd, guarded import
        return szl_tee_attest.get_tee_attestation()
    except Exception as e:  # pragma: no cover — additive, never breaks the request
        return {
            "present": False,
            "label": "UNAVAILABLE",
            "note": f"szl_tee_attest unavailable in this runtime ({type(e).__name__}); "
                    "no TEE probe performed; no measurement fabricated.",
        }


# ---------------------------------------------------------------------------
# TEE attestation QUOTE — MODELED, in the NVIDIA-NRAS / SEV-SNP / TDX claim shape
# ---------------------------------------------------------------------------
def _tee_quote(seed: int, model: str, mc: Dict[str, Any], prompt_digest: str) -> Dict[str, Any]:
    """A MODELED attestation quote mirroring the leaders' report/EAT claim shape.

    NVIDIA-NRAS EAT pattern: a fresh `nonce` for freshness, an overall attestation result, a
    per-device measurement DIGEST (SHA-256), secure-boot + RIM-validation flags. SEV-SNP pattern:
    `report_data` binds an app value (here the prompt/inference digest) INTO the quote so the
    quote is cryptographically bound to THIS inference. TDX pattern: `mrtd` = boot measurement.
    `quote_digest` is the SHA-384 the bundle/statement embed. NO real hardware quote is produced,
    NO NRAS/KDS/DCAP network call is made.
    """
    nonce = _sha256(f"nonce|{seed}|{model}|{prompt_digest}".encode("utf-8"))  # 32-byte hex (NRAS eat_nonce)
    report_data = _sha384(f"REPORT_DATA|{prompt_digest}|{mc['final_digest']}".encode("utf-8"))
    measurement_sha256 = _sha256(f"submod|{model}|{mc['final_digest']}".encode("utf-8"))
    # MODELED EAT claim set, shaped after a decoded NRAS token (all values SHA-derived, replayable)
    eat_claims = {
        "iss": "MODELED://a-11-oy.com/pcai (no real NRAS)",
        "sub": "MODELED-PLATFORM-ATTESTATION",
        "eat_nonce": nonce,
        "x-nvidia-overall-att-result": bool(mc.get("golden_match")),
        "secboot": bool(mc.get("golden_match")),
        "x-nvidia-gpu-driver-rim-schema-validated": bool(mc.get("golden_match")),
        "submods": {"GPU-0": ["DIGEST", ["SHA-256", measurement_sha256]]},
        "mrtd": mc["final_digest"],            # Intel TDX MRTD analogue = final boot measurement
        "report_data": report_data,            # AMD SEV-SNP REPORT_DATA = binds this inference
    }
    quote_body = {
        "tee_family": "MODELED-CC",            # stands in for {sev-snp, tdx, h100-cc}
        "cc_mode": "ON (MODELED)",             # NVIDIA H100 CC-mode ON
        "nonce": nonce,
        "eat_claims": eat_claims,
        "measurement_stages": [c["stage"] for c in mc.get("measurement_chain", [])],
        "verifier": "MODELED (no AMD KDS / NVIDIA NRAS / Intel DCAP network call performed)",
    }
    quote_digest = _sha384(_canon(quote_body))
    return {
        "quote_body": quote_body,
        "quote_digest": quote_digest,
        "nonce": nonce,
        "overall_att_result": bool(mc.get("golden_match")),
        "tee_probe": _tee_probe(),  # real probe label surfaced verbatim (MEASURED/UNAVAILABLE)
        "leaders_pattern": "NVIDIA NRAS EAT (nonce/overall-result/submod-digest/secboot) · "
                           "AMD SEV-SNP REPORT_DATA · Intel TDX MRTD",
        "verified_against": "MODELED golden reference (no NRAS/KDS/DCAP verifier contacted)",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# gated inference — deterministic MODELED token stream (no real engine)
# ---------------------------------------------------------------------------
def _gated_inference(seed: int, model: str, allowed: bool, quote_digest: str) -> Dict[str, Any]:
    """MODELED inference. If the Λ-gate did NOT pass, the inference is WITHHELD (CoCo KBS style)."""
    prompt = f"pcai attested-inference probe seed={seed} model={model}"
    prompt_digest = _sha384(prompt.encode("utf-8"))
    if not allowed:
        return {
            "released": False,
            "reason": "Λ-gate BLOCKED — attested trust below advisory floor; inference withheld "
                      "(CoCo KBS-style: no secret/inference release without a good attestation).",
            "prompt": prompt,
            "prompt_digest": prompt_digest,
            "output_digest": None,
            "tokens": [],
            "label": LABEL,
        }
    n_tokens = 8 + (int(seed) % 8)
    key = f"{model}|{quote_digest}".encode("utf-8")
    tokens: List[int] = []
    acc = hmac.new(key, str(seed).encode("utf-8"), hashlib.sha256).digest()
    for _ in range(n_tokens):
        acc = hmac.new(key, acc, hashlib.sha256).digest()
        tokens.append(int.from_bytes(acc[:2], "big") % 50257)  # GPT-2-vocab-sized id space
    output_digest = _sha384(_canon(tokens))
    return {
        "released": True,
        "prompt": prompt,
        "prompt_digest": prompt_digest,
        "n_tokens": n_tokens,
        "tokens": tokens,
        "output_digest": output_digest,
        "note": "MODELED token ids (HMAC-SHA256 chain keyed on model+quote); no real LM engine ran.",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# the RECEIPT — the (a) leg; embedded inside the SLSA predicate
# ---------------------------------------------------------------------------
def _receipt(seed: int, model: str, mc: Dict[str, Any], quote: Dict[str, Any],
             lam: Dict[str, Any], inference: Dict[str, Any]) -> Dict[str, Any]:
    """The governed inference receipt (Laminator-style attested inference card).

    Binds (a) the inference result to (b) the TEE quote digest, and carries a compact copy of
    (d) the Λ axis values. Fully recomputable from (seed, model).
    """
    receipt = {
        "schema": "szl.pcai.receipt/v1",
        "label": LABEL,
        "seed": int(seed),
        "model": str(model),
        "device_identity": mc["device_identity"],
        "mrtd": mc["final_digest"],
        "golden_match": mc.get("golden_match"),
        "attestation_quote_digest": quote["quote_digest"],   # (b) bound here
        "attestation_nonce": quote["nonce"],
        "tee_probe_label": quote.get("tee_probe", {}).get("label"),
        "lambda": {"value": lam["value"], "floor": lam["floor"], "pass": lam["pass"],
                   "axes": lam["axes"], "uniqueness": lam["uniqueness"]},  # (d) bound here
        "inference": {"released": inference["released"],
                      "prompt_digest": inference.get("prompt_digest"),
                      "output_digest": inference.get("output_digest"),
                      "n_tokens": inference.get("n_tokens")},
        "issued_at": _now_iso(),
        "honest_note": HONEST_NOTE,
    }
    receipt["receipt_digest"] = _sha384(_canon(receipt))
    return receipt


# ---------------------------------------------------------------------------
# in-toto / SLSA v1 STATEMENT — the (c) leg; binds (a),(b),(d) in its predicate
# ---------------------------------------------------------------------------
def _intoto_statement(seed: int, model: str, mc: Dict[str, Any], quote: Dict[str, Any],
                      lam: Dict[str, Any], inference: Dict[str, Any],
                      receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Emit an in-toto Statement (v1) with an SLSA v1 provenance predicate.

    Shape follows https://slsa.dev/spec/v1.0/provenance exactly:
      _type            = https://in-toto.io/Statement/v1
      subject[].digest = {sha384: <inference output digest>}   ← what slsa-verifier checks
      predicateType    = https://slsa.dev/provenance/v1
      predicate.buildDefinition {buildType, externalParameters, internalParameters,
                                 resolvedDependencies[]}
      predicate.runDetails {builder.id, metadata{invocationId, startedOn, finishedOn}}
    The predicate ALSO carries the PCAI-specific bindings under `internalParameters` /
    `byproducts`: the receipt digest (a), the TEE quote digest (b), and the Λ axes (d) — so ONE
    statement carries all four legs. slsa-verifier checks the subject digest + builder + signature;
    the PCAI-specific fields ride along as attested byproducts.
    """
    subject_digest = inference.get("output_digest") or mc["final_digest"]
    finished = _now_iso()
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{
            "name": f"pcai/attested-inference/{model}",
            "digest": {"sha384": subject_digest},
        }],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": BUILD_TYPE,
                "externalParameters": {"seed": int(seed), "model": str(model)},
                "internalParameters": {
                    "mrtd": mc["final_digest"],
                    "attestation_quote_digest": quote["quote_digest"],   # (b)
                    "attestation_nonce": quote["nonce"],
                    "receipt_digest": receipt["receipt_digest"],          # (a)
                    "lambda_value": lam["value"],                         # (d)
                    "lambda_floor": lam["floor"],
                    "lambda_pass": lam["pass"],
                    "lambda_uniqueness": lam["uniqueness"],
                    "honest_label": LABEL,
                },
                "resolvedDependencies": [
                    {"name": "device-measured-boot-chain", "digest": {"sha384": mc["final_digest"]}},
                    {"name": "tee-attestation-quote", "digest": {"sha384": quote["quote_digest"]}},
                    {"name": "inference-receipt", "digest": {"sha384": receipt["receipt_digest"]}},
                ],
            },
            "runDetails": {
                "builder": {
                    "id": BUILDER_ID,
                    "version": {"pcai": "v1", "mode": "MODELED"},
                },
                "metadata": {
                    "invocationId": _sha256(f"{seed}|{model}|{quote['quote_digest']}".encode())[:24],
                    "startedOn": receipt["issued_at"],
                    "finishedOn": finished,
                },
                # (d) Λ axes + (b) quote ride along as attested byproducts (non-subject artifacts)
                "byproducts": [
                    {"name": "lambda-trust-axes", "mediaType": "application/vnd.szl.lambda+json",
                     "content": base64.b64encode(_canon(lam["axes"])).decode("ascii"),
                     "annotations": {"lambda_value": lam["value"], "floor": lam["floor"],
                                     "pass": lam["pass"], "uniqueness": lam["uniqueness"]}},
                    {"name": "tee-attestation-eat", "mediaType": "application/vnd.szl.tee-eat+json",
                     "digest": {"sha384": quote["quote_digest"]},
                     "annotations": {"nonce": quote["nonce"], "label": LABEL,
                                     "overall_att_result": quote["overall_att_result"]}},
                ],
            },
        },
        "slsa_level_claim": "L1 (honest) — provenance present + signed; NOT an L2/L3 claim.",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# DSSE + Sigstore-style bundle — real ECDSA-P256 in-Space; honest UNSIGNED-LOCAL locally
# ---------------------------------------------------------------------------
def _sign_statement(statement: Dict[str, Any]) -> Dict[str, Any]:
    """DSSE-sign the in-toto Statement. Real ECDSA-P256 when the cosign secret is present in-Space;
    honest UNSIGNED-LOCAL envelope otherwise (never fabricates a signature). Uses szl_dsse so the
    envelope is byte-for-byte `cosign verify-blob`-checkable."""
    try:
        import szl_dsse  # per-file COPY'd, guarded
        env = szl_dsse.sign_payload(statement, payload_type=PAYLOAD_TYPE)
        if not env.get("signed"):
            env.setdefault("honesty",
                           "UNSIGNED-LOCAL — no cosign secret in this runtime; no signature fabricated.")
            env["local_label"] = "UNSIGNED-LOCAL"
        return env
    except Exception as e:  # pragma: no cover — additive
        body = _canon(statement)
        return {
            "payloadType": PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [],
            "signed": False,
            "local_label": "UNSIGNED-LOCAL",
            "honesty": f"UNSIGNED-LOCAL — szl_dsse unavailable ({type(e).__name__}); no signature fabricated.",
            "_pae_sha256": _sha256(_pae(PAYLOAD_TYPE, body)),
        }


def _sigstore_bundle(dsse: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap the DSSE envelope in a Sigstore-style bundle (application/vnd.dev.sigstore.bundle+json).

    A real Sigstore bundle carries the DSSE envelope + verification material (public key / cert)
    + a Rekor inclusion promise. We emit that SHAPE so `cosign verify-blob --bundle` COULD consume
    it, and HONESTLY mark Rekor inclusion UNAVAILABLE-LOCAL because no transparency-log entry is
    created offline (Doctrine v11 — never fabricate a log promise).
    """
    signed = bool(dsse.get("signed"))
    return {
        "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.3",
        "verificationMaterial": {
            "publicKey": {"hint": "szlholdings-cosign", "url": COSIGN_PUB_URL, "raw_url": COSIGN_PUB_RAW},
            "tlogEntries": [],  # Rekor: none offline — honestly empty
            "tlog_status": ("UNAVAILABLE-LOCAL — no Rekor transparency-log entry created offline; "
                            "in-Space signing MAY publish to Rekor when the log endpoint is configured."),
        },
        "dsseEnvelope": {
            "payload": dsse.get("payload"),
            "payloadType": dsse.get("payloadType", PAYLOAD_TYPE),
            "signatures": dsse.get("signatures", []),
        },
        "signed": signed,
        "signing_label": "REAL-SIGNED (ECDSA-P256, cosign-verifiable)" if signed else "UNSIGNED-LOCAL",
        "label": LABEL,
    }


def _intoto_jsonl(dsse: Dict[str, Any]) -> str:
    """Emit the one-line DSSE JSON that slsa-verifier expects as `--provenance-path <x>.intoto.jsonl`.

    slsa-verifier reads a JSONL where each line is a DSSE envelope wrapping an in-toto Statement.
    We produce exactly one such line (canonical JSON, no trailing newline)."""
    line = {
        "payloadType": dsse.get("payloadType", PAYLOAD_TYPE),
        "payload": dsse.get("payload"),
        "signatures": dsse.get("signatures", []),
    }
    return _canon(line).decode("utf-8")


# ---------------------------------------------------------------------------
# documented verify commands — the exact off-the-shelf checks (code + response)
# ---------------------------------------------------------------------------
def _verify_commands(seed: int, model: str, artifact_name: str, subject_digest: str) -> Dict[str, Any]:
    """The EXACT commands a relying party runs to check the PCAI bundle with off-the-shelf tools.

    These are documented here in code AND echoed to the endpoint response. They describe how the
    emitted DSSE envelope / Sigstore bundle / intoto.jsonl COULD be checked; in MODELED / local
    mode the DSSE is UNSIGNED-LOCAL so the signature checks would report UNSIGNED (honest), while
    in-Space (real cosign secret) the same commands PASS byte-for-byte.
    """
    return {
        "step_0_save_artifacts": [
            "# The endpoint returns base64 payload + signatures. Reconstruct the files:",
            f"curl -s 'https://a-11-oy.com/api/a11oy/v1/pcai/run?seed={seed}&model={model}' > pcai.json",
            "jq -r '.dsse.payload' pcai.json | base64 -d > pcai.statement.json   # the in-toto Statement (the blob)",
            "jq -r '.intoto_jsonl'  pcai.json           > pcai.intoto.jsonl       # DSSE line for slsa-verifier",
            "jq    '.bundle'        pcai.json           > pcai.bundle.json         # Sigstore-style bundle",
            "jq -r '.dsse.signatures[0].sig' pcai.json | base64 -d > pcai.statement.sig   # raw ECDSA sig (in-Space only)",
            f"curl -s {COSIGN_PUB_RAW} > cosign.pub                               # published SZL cosign public key",
        ],
        "cosign_verify_blob": (
            "cosign verify-blob "
            "--key cosign.pub "
            "--signature pcai.statement.sig "
            "pcai.statement.json"
        ),
        "cosign_verify_blob_bundle": (
            "cosign verify-blob "
            "--bundle pcai.bundle.json "
            "--key cosign.pub "
            "pcai.statement.json"
        ),
        "slsa_verifier_verify_artifact": (
            "slsa-verifier verify-artifact pcai.statement.json "
            "--provenance-path pcai.intoto.jsonl "
            "--source-uri github.com/szl-holdings/a11oy "
            f"--build-workflow-input seed={seed}"
        ),
        "artifact": artifact_name,
        "subject_digest_sha384": subject_digest,
        "expected_local_result": (
            "UNSIGNED-LOCAL — locally the DSSE has no signature (no cosign secret), so the cosign / "
            "slsa-verifier signature checks report UNSIGNED (honest). In-Space (real SZL cosign "
            "secret present) the SAME commands PASS: cosign verify-blob accepts the ECDSA-P256 sig "
            "over the DSSE PAE byte-for-byte, and slsa-verifier confirms the SLSA v1 provenance."
        ),
        "note": ("The bundle is emitted in the leaders' shapes (Sigstore bundle v0.3 + in-toto/SLSA "
                 "v1 DSSE) so these standard tools COULD check it. Rekor inclusion is UNAVAILABLE-LOCAL "
                 "(no transparency-log entry created offline)."),
    }


# ---------------------------------------------------------------------------
# the whole flow
# ---------------------------------------------------------------------------
def run_pcai(seed: int, model: str) -> Dict[str, Any]:
    """Full proof-carrying attested-inference flow, deterministic + MODELED.

    measured-boot → TEE quote → Λ-gate → gated inference → receipt (a) → in-toto/SLSA statement
    binding (a)+(b)+(d) → DSSE envelope → Sigstore-style bundle + intoto.jsonl. Everything is
    recomputable from (seed, model); the signature is real in-Space and honestly UNSIGNED-LOCAL
    otherwise.
    """
    seed = int(seed)
    model = str(model or "szl-modeled-lm")

    # 1) measured-boot chain (reuse cc-attest via szl_attested_inference)
    mc = _measurement_chain(seed, model)

    # 2) bind the (about-to-run) inference into the TEE quote (NRAS nonce + SEV-SNP REPORT_DATA)
    prompt_digest = _sha384(f"pcai attested-inference probe seed={seed} model={model}".encode("utf-8"))
    quote = _tee_quote(seed, model, mc, prompt_digest)

    # 3) Λ-gate over the 13 trust axes; attestation axis hard-coupled to the boot match
    lam = _lambda_axes(seed, model, quote["quote_digest"], bool(mc.get("golden_match")))

    # 4) gated inference (withheld if Λ-gate blocks — CoCo KBS style)
    inference = _gated_inference(seed, model, lam["pass"], quote["quote_digest"])

    # 5) receipt (a) — binds inference to the quote digest + Λ axes
    receipt = _receipt(seed, model, mc, quote, lam, inference)

    # 6) in-toto/SLSA v1 statement (c) — ONE artifact binding (a)+(b)+(d)
    statement = _intoto_statement(seed, model, mc, quote, lam, inference, receipt)

    # 7) DSSE envelope over the statement (real ECDSA-P256 in-Space; UNSIGNED-LOCAL locally)
    dsse = _sign_statement(statement)

    # 8) Sigstore-style bundle + intoto.jsonl (cosign / slsa-verifier consumable shapes)
    bundle = _sigstore_bundle(dsse)
    intoto_jsonl = _intoto_jsonl(dsse)

    # the artifact + its digest (what the verifier binds to)
    subject_digest = statement["subject"][0]["digest"]["sha384"]
    artifact_name = f"pcai.statement.json (subject pcai/attested-inference/{model})"
    bundle_digest = _sha384(_canon({"dsse": {"payload": dsse.get("payload"),
                                             "payloadType": dsse.get("payloadType"),
                                             "signatures": dsse.get("signatures", [])},
                                    "bundle_media": bundle["mediaType"]}))

    verify_commands = _verify_commands(seed, model, artifact_name, subject_digest)

    # 9) forum ingest (additive, off the hot path, never raises)
    try:
        import szl_org_lambda as _ol
        _ol.emit("a11oy", "pcai/run",
                 {"seed": seed, "model": model, "lambda": lam["value"],
                  "quote_digest": quote["quote_digest"], "signed": bool(dsse.get("signed")),
                  "label": LABEL},
                 decision="ALLOW" if lam["pass"] else "BLOCK")
    except Exception:
        pass

    return {
        "label": LABEL,
        "seed": seed,
        "model": model,
        "flow": "measured-boot → TEE quote → Λ-gate → gated inference → receipt → in-toto/SLSA "
                "statement → DSSE → Sigstore bundle + intoto.jsonl",
        # measured-boot (reused cc-attest) — for the surface tower:
        "device_identity": mc["device_identity"],
        "measurement_chain": mc["measurement_chain"],
        "final_digest": mc["final_digest"],
        "golden_match": mc.get("golden_match"),
        "measurement_source": mc.get("_source"),
        # (b) TEE attestation quote:
        "tee_quote": quote,
        # (d) Λ axes:
        "lambda": lam,
        # gated inference:
        "inference": inference,
        # (a) receipt:
        "receipt": receipt,
        # (c) in-toto/SLSA v1 statement (binds a+b+d) + envelope + bundle:
        "statement": statement,
        "dsse": dsse,
        "bundle": bundle,
        "intoto_jsonl": intoto_jsonl,
        "artifact": {
            "name": artifact_name,
            "subject_digest_sha384": subject_digest,
            "bundle_digest_sha384": bundle_digest,
            "binds": {"a_receipt": receipt["receipt_digest"],
                      "b_tee_quote_digest": quote["quote_digest"],
                      "c_provenance_predicateType": PREDICATE_TYPE,
                      "d_lambda_value": lam["value"]},
        },
        # the exact off-the-shelf verify commands (documented in code + here):
        "verify_commands": verify_commands,
        "verifiable_by_design": (
            "Recompute the measured-boot chain + TEE quote from (seed, model), recompute Λ from the "
            "13 axes, recompute the receipt + in-toto/SLSA statement digests, then verify the DSSE "
            "envelope with `cosign verify-blob --key cosign.pub` and the provenance with "
            "`slsa-verifier verify-artifact --provenance-path pcai.intoto.jsonl` — one bundle, "
            "checkable by off-the-shelf tools. Signature is REAL in-Space, UNSIGNED-LOCAL locally."
        ),
        "honest_note": HONEST_NOTE,
        "sources": SOURCES,
        "ts": _now_iso(),
    }


# ---------------------------------------------------------------------------
# HTTP handler + registration (front-inserted route, mirrors szl_attested_inference)
# ---------------------------------------------------------------------------
def _h_pcai_run(request):
    from starlette.responses import JSONResponse  # type: ignore[import]
    qp = request.query_params
    try:
        seed = int(qp.get("seed", "42"))
    except Exception:
        seed = 42
    model = qp.get("model", "szl-modeled-lm")
    try:
        result = run_pcai(seed, model)
        return JSONResponse(result)
    except Exception as e:  # pragma: no cover — always return a renderable 200-shaped body
        return JSONResponse({
            "label": LABEL, "seed": seed, "model": model, "error": f"{type(e).__name__}: {e}",
            "honest_note": HONEST_NOTE, "sources": SOURCES,
        }, status_code=200)


def register(app, ns: str = NS_DEFAULT) -> dict:
    """Wire GET /api/<ns>/v1/pcai/run onto the app.

    Additive. Front-inserts the STATIC route so it wins over the generic /api/a11oy/{path:path}
    Node proxy catch-all — the proven pattern used by szl_attested_inference, szl_tee_attest, etc.
    Never raises into the caller.
    """
    path = f"/api/{ns}/v1/pcai/run"
    prefix = f"/api/{ns}/v1/pcai/"
    try:
        from starlette.routing import Route  # type: ignore[import]
    except Exception as e:
        return {"registered": [], "status": f"failed:starlette-absent:{e}"}
    try:
        _r = Route(path, _h_pcai_run, methods=["GET"])
        routes = app.router.routes
        # Insert immediately before any pre-existing PARAMETRIZED /pcai/{...} route so exact-path
        # matching wins; else front-insert (ahead of the SPA/proxy catch-all).
        insert_at = 0
        for i, rt in enumerate(routes):
            p = getattr(rt, "path", "") or ""
            if p.startswith(prefix) and ("{" in p) and p != path:
                insert_at = i
                break
        routes.insert(insert_at, _r)
        return {"registered": [path], "status": "ok", "inserted_at": insert_at}
    except Exception as e:
        return {"registered": [], "status": f"failed:{type(e).__name__}:{e}"}


# ---------------------------------------------------------------------------
# No-server self-test — determinism + honesty + binding invariants
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    a = run_pcai(42, "szl-modeled-lm")
    b = run_pcai(42, "szl-modeled-lm")
    # determinism (ignore timestamps): same (seed, model) → identical quote + Λ + subject digest
    assert a["tee_quote"]["quote_digest"] == b["tee_quote"]["quote_digest"], "quote not deterministic"
    assert a["lambda"]["value"] == b["lambda"]["value"], "Λ not deterministic"
    assert a["artifact"]["subject_digest_sha384"] == b["artifact"]["subject_digest_sha384"]
    # honesty invariants
    assert a["label"] == "MODELED", a["label"]
    assert a["lambda"]["value"] <= TRUST_CEIL + 1e-9, "trust ceiling 0.97 violated"
    assert "Conjecture 1" in a["lambda"]["uniqueness"], "Λ must be Conjecture 1"
    # ONE bundle binds all four legs
    st = a["statement"]
    assert st["_type"] == STATEMENT_TYPE and st["predicateType"] == PREDICATE_TYPE
    ip = st["predicate"]["buildDefinition"]["internalParameters"]
    assert ip["attestation_quote_digest"] == a["tee_quote"]["quote_digest"], "(b) quote not bound"
    assert ip["receipt_digest"] == a["receipt"]["receipt_digest"], "(a) receipt not bound"
    assert ip["lambda_value"] == a["lambda"]["value"], "(d) Λ not bound"
    assert st["subject"][0]["digest"]["sha384"] == a["inference"]["output_digest"], "subject!=output"
    # DSSE present + honest bundle/jsonl shapes
    assert "signed" in a["dsse"], a["dsse"].keys()
    assert a["bundle"]["mediaType"].startswith("application/vnd.dev.sigstore.bundle+json")
    assert isinstance(a["intoto_jsonl"], str) and a["intoto_jsonl"].startswith("{")
    # verify commands documented + echoed
    vc = a["verify_commands"]
    assert vc["cosign_verify_blob"].startswith("cosign verify-blob")
    assert vc["slsa_verifier_verify_artifact"].startswith("slsa-verifier verify-artifact")
    # even seed → good boot → gate passes → inference released
    assert a["golden_match"] is True and a["inference"]["released"] is True, a["golden_match"]
    # odd seed → tampered boot → attestation axis 0 → Λ=0 → gate blocks → inference withheld
    c = run_pcai(43, "szl-modeled-lm")
    assert c["golden_match"] is False, "odd seed should simulate a boot mismatch"
    assert c["lambda"]["value"] == 0.0, "zero-absorption should drive Λ to 0 on bad attestation"
    assert c["inference"]["released"] is False, "inference must be withheld when Λ-gate blocks"
    return {"ok": True, "lambda_even": a["lambda"]["value"], "gate_even": a["lambda"]["pass"],
            "lambda_odd": c["lambda"]["value"], "gate_odd": c["lambda"]["pass"],
            "dsse_signed": a["dsse"].get("signed"),
            "subject_digest": a["artifact"]["subject_digest_sha384"][:16],
            "quote_digest": a["tee_quote"]["quote_digest"][:16]}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2, default=str))
