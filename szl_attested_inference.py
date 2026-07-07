# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Wave-H Team 3 (attested-inference deepening).
"""
szl_attested_inference.py — ATTESTED INFERENCE (Wave-H Team 3 deepening of Wave-A cc-attest)

WHAT THIS IS
------------
A full, end-to-end **attested-inference** flow that binds a device-attestation quote
to a governed inference RECEIPT, verifiable-by-design. It DEEPENS the Wave-A cc-attest
measurement-chain simulation (killinchu `cc-attest/verify`) into the complete leader
pattern: device attestation → Λ-gated inference → a signed receipt that embeds the
attestation quote digest + the Λ trust axes + SLSA-style provenance.

    GET /api/a11oy/v1/attest/infer?seed=<int>&model=<id>

    device attestation  (reuse/extend a cc-attest-style measured-boot chain)
        └─► Λ-gate        (weighted geometric mean over the 13 trust axes; Conjecture 1)
              └─► gated inference (deterministic MODELED token stream)
                    └─► receipt (attestation quote digest + Λ axes + SLSA provenance)
                          └─► DSSE envelope (real ECDSA-P256 in-Space; UNSIGNED-LOCAL locally)

HONESTY (Doctrine v11 — NEVER violate)
--------------------------------------
Label = **MODELED**. This SIMULATES the attested path deterministically from (seed, model):
there is **no real TEE, no real GPU, no NRAS/KDS network call, no real inference engine**.
Every synthetic value is derived by SHA-256/384 from the inputs so the flow is replayable and
verifiable, NOT fabricated as a live measurement. Where a REAL measurement is available the
module defers to `szl_tee_attest.get_tee_attestation()` and surfaces its honest label verbatim
(MEASURED on a live TDX/Nitro pod, UNAVAILABLE on the CPU Space) inside `tee_attestation`.
The DSSE envelope is REAL ECDSA-P256 when the cosign secret is present in-Space, and honestly
`signed:false` (UNSIGNED-LOCAL) otherwise — the signature is never fabricated.

Λ = **Conjecture 1** (advisory, gray, NEVER "green"/theorem). Nothing here touches the locked-8.

CONFIDENTIAL-COMPUTE LEADERS STUDIED & CITED (clean-room PATTERN, not their code)
--------------------------------------------------------------------------------
  • NVIDIA H100/H200 Confidential Computing + NRAS remote attestation — the relying party
    checks a signed attestation report (CC-mode ON, genuine unmodified GPU/firmware) against
    NVIDIA's Remote Attestation Service before trusting the GPU with secrets. This is the
    hardware root for attested inference.
    https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/
  • AMD SEV-SNP — guest places a digest in REPORT_DATA, retrieves an attestation report via
    /dev/sev-guest SNP_GET_REPORT; a relying party verifies against the VCEK cert chain from
    the AMD Key Distribution Service (KDS). REPORT_DATA binds an app value (e.g. our nonce/
    prompt digest) into the quote — the pattern we mirror to bind the inference to the quote.
    https://www.amd.com/content/dam/amd/en/documents/developer/lss-snp-attestation.pdf
  • Intel TDX — a TD produces a TDREPORT (MRTD + RTMRs) converted to a signed TD Quote; the
    verifier checks it (DCAP / Intel Trust Authority). We mirror MRTD as the boot measurement.
    https://community.intel.com/t5/Blogs/Products-and-Solutions/Security/Seamless-Attestation-of-Intel-TDX-and-NVIDIA-H100-TEEs-with/post/1525587
  • in-toto / SLSA — signed attestations of "who built/ran what, when," graded L1→L3. Our
    receipt carries an SLSA-style provenance predicate (builder, buildType, invocation, digests).
    https://slsa.dev/spec/v1.0/levels  ·  https://slsa.dev/blog/2023/05/in-toto-and-slsa
  • Sigstore / Rekor — a transparency log for signatures; `cosign`/`slsa-verifier` verify
    receipts with off-the-shelf tooling. Our DSSE envelope is cosign-verifiable (szl_dsse).
    https://docs.sigstore.dev/  ·  https://docs.sigstore.dev/logging/overview/
  • Confidential Containers (CoCo, CNCF) — Kata + attestation-agent + Key Broker Service (KBS)
    gate secret/key release on a verified attestation. Our Λ-gate is the software analogue: it
    releases the (MODELED) inference only when the attested trust meets the advisory floor.
    https://github.com/confidential-containers/confidential-containers
  • Academic frontier — *Laminator: Verifiable ML Property Cards using Hardware-assisted
    Attestations* (arXiv 2406.17548) binds model+input+output into an attested "inference card"
    — exactly the artifact SZL calls a receipt.  *SLSA for ML 2025: Signed Datasets,
    Reproducible Training, Attested Inference* is the reference architecture we map onto.

WHAT SZL ADDS BEYOND THE LEADERS
--------------------------------
The leaders ship attestation (hardware) and provenance (supply chain) separately. SZL fuses
TEE attestation + in-toto/SLSA provenance + a Lean-checked Λ trust gate into ONE DSSE receipt —
"proof-carrying attested inference." (Λ uniqueness stays Conjecture 1; nothing to locked-8.)

ENDPOINT
--------
  GET /api/a11oy/v1/attest/infer?seed=<int>&model=<model_id>
      → 200 JSON {label:"MODELED", seed, model, tee_attestation, attestation_quote,
                  measurement_chain[], lambda{axes,value,floor,pass,uniqueness}, inference,
                  receipt{...}, dsse{...}, slsa_provenance{...}, honest_note, sources[]}

Also mirrors the Wave-A cc-attest shape (device_identity, measurement_chain, final_digest,
golden_match) so the attestinfer.js surface can render the same tower + the inference/receipt.
"""

from __future__ import annotations

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
PAYLOAD_TYPE = "application/vnd.szl.attest-inference+json"

# advisory Λ floor (mirror szl_org_lambda.LAMBDA_FLOOR; kept local to avoid a hard import)
LAMBDA_FLOOR = 0.90

# The measured-boot stage chain we simulate — mirrors the Wave-A cc-attest ordering
# (bootloader → firmware → driver → microcode → gpu-vbios) and adds the inference-bind stage.
_BOOT_STAGES = ["bootloader", "firmware", "gpu-driver", "microcode", "gpu-vbios"]

# Canonical 13 trust axes (mirror szl_org_lambda.ORG_AXIS_NAMES / serve _A11OY_AXIS_NAMES).
_AXIS_NAMES = [
    "soundness", "calibration", "robustness", "provenance", "consent", "reversibility",
    "transparency", "fairness", "containment", "attestation", "freshness", "authority",
    "auditability",
]
_AXIS_WEIGHTS = [0.12, 0.06, 0.08, 0.11, 0.06, 0.07, 0.07, 0.05, 0.08, 0.10, 0.05, 0.07, 0.08]

# Confidential-compute leaders — cited in code AND in the response `sources[]`.
SOURCES: List[Dict[str, str]] = [
    {"name": "NVIDIA — Confidential Computing on H100 GPUs (NRAS remote attestation)",
     "url": "https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/"},
    {"name": "AMD — SEV-SNP Attestation: Establishing Trust in Guests (REPORT_DATA / VCEK / KDS)",
     "url": "https://www.amd.com/content/dam/amd/en/documents/developer/lss-snp-attestation.pdf"},
    {"name": "Intel + NVIDIA — Seamless Attestation of Intel TDX and NVIDIA H100 TEEs",
     "url": "https://community.intel.com/t5/Blogs/Products-and-Solutions/Security/Seamless-Attestation-of-Intel-TDX-and-NVIDIA-H100-TEEs-with/post/1525587"},
    {"name": "SLSA — Supply-chain Levels for Software Artifacts (L1→L3)",
     "url": "https://slsa.dev/spec/v1.0/levels"},
    {"name": "in-toto & SLSA — signed provenance attestations",
     "url": "https://slsa.dev/blog/2023/05/in-toto-and-slsa"},
    {"name": "Sigstore — cosign / Rekor transparency log",
     "url": "https://docs.sigstore.dev/logging/overview/"},
    {"name": "Confidential Containers (CoCo, CNCF) — attestation-agent + Key Broker Service",
     "url": "https://github.com/confidential-containers/confidential-containers"},
    {"name": "Laminator: Verifiable ML Property Cards using Hardware-assisted Attestations (arXiv 2406.17548)",
     "url": "https://arxiv.org/abs/2406.17548"},
]

HONEST_NOTE = (
    "MODELED — deterministic simulation of the attested-inference path keyed on (seed, model). "
    "No real TEE, no real GPU, no NRAS/KDS network call, no real inference engine. Synthetic "
    "measurements are SHA-256/384 of the inputs (replayable, NOT a live hardware quote). If a "
    "real TDX/Nitro measurement is present, szl_tee_attest surfaces it verbatim in "
    "tee_attestation. DSSE is REAL ECDSA-P256 in-Space (cosign-verifiable) and honestly "
    "UNSIGNED-LOCAL when no signing secret is present. Λ = Conjecture 1 (advisory, never green). "
    "Nothing here is in the locked-8."
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
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _det_unit(*parts: str) -> float:
    """Deterministic float in [0,1] from a SHA-256 of the parts (replayable, no RNG)."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    v = int.from_bytes(h[:8], "big") / float(1 << 64)
    return min(max(v, 0.0), 1.0)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(max(x, lo), hi)


# ---------------------------------------------------------------------------
# Λ-gate — weighted geometric mean over the 13 trust axes (mirrors szl_org_lambda)
# ---------------------------------------------------------------------------
def _weighted_geomean(axes: List[float], weights: List[float]) -> float:
    """A4 zero-absorption weighted geometric mean. Any zero axis → 0.0. Λ ∈ [0,1].
    Kept local (no hard dependency) but numerically identical to szl_org_lambda.weighted_geomean."""
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
    """Deterministic per-axis trust scores in [0,1] derived from (seed, model, quote).

    The `attestation` axis is HARD-COUPLED to the measured-boot result: if the boot chain does
    NOT match its golden reference, attestation collapses toward 0 and A4 zero-absorption pulls
    Λ down — exactly the CoCo KBS behaviour (no secret/inference release without a good quote).
    """
    s = str(seed)
    scores: Dict[str, float] = {}
    for name in _AXIS_NAMES:
        base = 0.90 + 0.09 * _det_unit(s, model, quote_digest, name)  # in [0.90, 0.99]
        scores[name] = _clamp(base, 0.0, 0.97)  # trust ceiling 0.97 (Doctrine v11)
    # attestation axis is gated on the boot measurement matching its golden reference
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
# device attestation — reuse/extend the cc-attest measured-boot chain
# ---------------------------------------------------------------------------
def _measurement_chain(seed: int, model: str) -> Dict[str, Any]:
    """Deterministic measured-boot hash-chain (MODELED), mirroring Wave-A cc-attest.

    device_identity (sha384) → stage digests chained → final_digest checked against a fixed
    golden reference. This is the SEV-SNP/TDX/H100-CC measured-boot PATTERN — device identity
    plus an ordered chain of stage measurements folded into a final attestation value — NOT a
    real hardware quote.
    """
    device_identity = _sha384(f"szl-attested-device|{model}|seed={seed}".encode("utf-8"))
    chain: List[Dict[str, str]] = []
    acc = device_identity
    for stage in _BOOT_STAGES:
        stage_measure = _sha384(f"{stage}|{model}|seed={seed}".encode("utf-8"))
        acc = _sha384(f"{acc}|{stage}:{stage_measure}".encode("utf-8"))
        chain.append({"stage": stage, "measurement": stage_measure, "chained_digest": acc})
    final_digest = acc
    # Golden reference = the deterministic final digest for a "known-good" build of this model.
    # In MODELED mode a known-good build is defined as seed with the low bit clear (even seed);
    # odd seeds simulate a tampered/unknown boot so the surface can show a MISMATCH honestly.
    golden_reference = _sha384(
        f"golden|{model}|{_sha384(('|'.join(_BOOT_STAGES) + '|' + model).encode())}".encode("utf-8")
    )
    golden_match = (final_digest == _golden_final(seed, model, golden_reference))
    return {
        "device_identity": device_identity,
        "measurement_chain": [{"stage": c["stage"], "digest": c["chained_digest"]} for c in chain],
        "stage_measurements": chain,
        "final_digest": final_digest,
        "golden_reference": golden_reference,
        "golden_match": golden_match,
        "stages": len(_BOOT_STAGES),
    }


def _golden_final(seed: int, model: str, golden_reference: str) -> str:
    """MODELED golden final digest: for an even seed the boot matches (known-good build);
    for an odd seed we return a different value so golden_match is False (simulated tamper)."""
    if seed % 2 == 0:
        # reconstruct the exact final_digest the good build would produce
        acc = _sha384(f"szl-attested-device|{model}|seed={seed}".encode("utf-8"))
        for stage in _BOOT_STAGES:
            stage_measure = _sha384(f"{stage}|{model}|seed={seed}".encode("utf-8"))
            acc = _sha384(f"{acc}|{stage}:{stage_measure}".encode("utf-8"))
        return acc
    return golden_reference  # deliberately != final_digest for odd seeds → MISMATCH


def _attestation_quote(seed: int, model: str, mc: Dict[str, Any], prompt_digest: str) -> Dict[str, Any]:
    """Build a MODELED attestation quote in the shape of the leaders' reports.

    We mirror the SEV-SNP `REPORT_DATA` binding: the quote commits to an app-supplied value
    (here the prompt/inference digest) so the quote is cryptographically bound to THIS inference.
    We also mirror the TDX MRTD (boot measurement) and NVIDIA CC-mode fields. `quote_digest` is
    the SHA-384 the receipt embeds. NO real hardware quote is produced.
    """
    report_data = _sha384(f"REPORT_DATA|{prompt_digest}|{mc['final_digest']}".encode("utf-8"))
    quote_body = {
        "tee_family": "MODELED-CC",          # stands in for {sev-snp, tdx, h100-cc}
        "cc_mode": "ON (MODELED)",           # NVIDIA H100 CC-mode ON
        "mrtd": mc["final_digest"],          # TDX MRTD analogue = final boot measurement
        "report_data": report_data,          # SEV-SNP REPORT_DATA = binds this inference
        "measurement_stages": [c["stage"] for c in mc["stage_measurements"]],
        "vcek_kds": "MODELED (no AMD KDS / NVIDIA NRAS network call performed)",
        "nonce": _sha256(f"nonce|{seed}|{model}".encode("utf-8"))[:32],
    }
    quote_digest = _sha384(_canon(quote_body))
    return {
        "quote_body": quote_body,
        "quote_digest": quote_digest,
        "verified_against": "MODELED golden reference (no NRAS/KDS/DCAP verifier contacted)",
        "leaders_pattern": "NVIDIA NRAS · AMD SEV-SNP REPORT_DATA/VCEK · Intel TDX MRTD",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# gated inference — deterministic MODELED token stream (no real engine)
# ---------------------------------------------------------------------------
def _tee_attestation() -> Dict[str, Any]:
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


def _gated_inference(seed: int, model: str, allowed: bool, quote_digest: str) -> Dict[str, Any]:
    """MODELED inference. Deterministic pseudo-tokens from (seed, model). If the Λ-gate did NOT
    pass, the inference is WITHHELD (mirrors CoCo KBS refusing key/secret release on a bad quote).
    """
    prompt = f"attested-inference probe seed={seed} model={model}"
    prompt_digest = _sha384(prompt.encode("utf-8"))
    if not allowed:
        return {
            "released": False,
            "reason": "Λ-gate BLOCKED — attested trust below advisory floor; inference withheld "
                      "(CoCo KBS-style: no secret/inference release without a good attestation).",
            "prompt_digest": prompt_digest,
            "output_digest": None,
            "tokens": [],
            "label": LABEL,
        }
    # deterministic token stream: derive N pseudo-token ids from a keyed hash chain
    n_tokens = 8 + (seed % 8)
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
# SLSA-style provenance predicate (in-toto/SLSA v1) — embedded in the receipt
# ---------------------------------------------------------------------------
def _slsa_provenance(seed: int, model: str, mc: Dict[str, Any], quote_digest: str,
                     inference: Dict[str, Any]) -> Dict[str, Any]:
    """Emit an in-toto/SLSA v1 provenance predicate for the attested inference.

    Maps the run onto the SLSA predicate shape (builder, buildType, invocation, subject digests)
    so the receipt is checkable with off-the-shelf `slsa-verifier`/`cosign` — the leader pattern.
    """
    subject_digest = inference.get("output_digest") or mc["final_digest"]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [{
            "name": f"attested-inference/{model}",
            "digest": {"sha384": subject_digest},
        }],
        "predicate": {
            "buildDefinition": {
                "buildType": "https://a-11-oy.com/attested-inference/v1",
                "externalParameters": {"seed": seed, "model": model},
                "internalParameters": {
                    "mrtd": mc["final_digest"],
                    "attestation_quote_digest": quote_digest,
                },
                "resolvedDependencies": [{
                    "name": "device-measured-boot-chain",
                    "digest": {"sha384": mc["final_digest"]},
                }],
            },
            "runDetails": {
                "builder": {"id": "https://a-11-oy.com/builders/attested-inference-MODELED"},
                "metadata": {
                    "invocationId": _sha256(f"{seed}|{model}|{quote_digest}".encode())[:24],
                    "startedOn": _now_iso(),
                },
            },
        },
        "slsa_level_claim": "L1 (honest) — provenance present + signed; NOT an L2/L3 claim.",
        "verify_with": "cosign verify-blob / slsa-verifier against szl-holdings cosign.pub",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# receipt + DSSE — real ECDSA-P256 in-Space; honest UNSIGNED-LOCAL locally
# ---------------------------------------------------------------------------
def _sign_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """DSSE-sign the receipt. Real ECDSA-P256 when the cosign secret is present in-Space;
    honest UNSIGNED-LOCAL envelope otherwise (never fabricates a signature)."""
    try:
        import szl_dsse  # per-file COPY'd, guarded
        env = szl_dsse.sign_payload(receipt, payload_type=PAYLOAD_TYPE)
        if not env.get("signed"):
            # normalise the local (no-secret) honesty marker to the doctrine label
            env.setdefault("honesty", "UNSIGNED-LOCAL — no cosign secret in this runtime; no signature fabricated.")
            env["local_label"] = "UNSIGNED-LOCAL"
        return env
    except Exception as e:  # pragma: no cover — additive
        body = _canon(receipt)
        return {
            "payloadType": PAYLOAD_TYPE,
            "signatures": [],
            "signed": False,
            "local_label": "UNSIGNED-LOCAL",
            "honesty": f"UNSIGNED-LOCAL — szl_dsse unavailable ({type(e).__name__}); no signature fabricated.",
            "_pae_sha256": _sha256(b"DSSEv1 " + str(len(PAYLOAD_TYPE)).encode() + b" " +
                                   PAYLOAD_TYPE.encode() + b" " + str(len(body)).encode() + b" " + body),
        }


def run_attested_inference(seed: int, model: str) -> Dict[str, Any]:
    """The full attested-inference flow, deterministic + MODELED. Returns the response dict.

    device attestation → Λ-gate → gated inference → receipt (quote digest + Λ axes + SLSA
    provenance) → DSSE envelope. Verifiable-by-design: everything is recomputable from (seed,model).
    """
    seed = int(seed)
    model = str(model or "szl-modeled-lm")

    # 1) device attestation (measured-boot chain — extends Wave-A cc-attest)
    mc = _measurement_chain(seed, model)
    tee = _tee_attestation()

    # 2) bind the (about-to-run) inference into the attestation quote (SEV-SNP REPORT_DATA style)
    prompt_digest = _sha384(f"attested-inference probe seed={seed} model={model}".encode("utf-8"))
    quote = _attestation_quote(seed, model, mc, prompt_digest)

    # 3) Λ-gate over the 13 trust axes; attestation axis hard-coupled to the boot match
    lam = _lambda_axes(seed, model, quote["quote_digest"], mc["golden_match"])

    # 4) gated inference (withheld if Λ-gate blocks — CoCo KBS style)
    inference = _gated_inference(seed, model, lam["pass"], quote["quote_digest"])

    # 5) SLSA-style provenance predicate
    slsa = _slsa_provenance(seed, model, mc, quote["quote_digest"], inference)

    # 6) assemble the receipt (embeds attestation quote digest + Λ axes + SLSA provenance)
    receipt_core: Dict[str, Any] = {
        "schema": "szl.attested-inference/v1",
        "label": LABEL,
        "seed": seed,
        "model": model,
        "device_identity": mc["device_identity"],
        "attestation_quote_digest": quote["quote_digest"],
        "mrtd": mc["final_digest"],
        "golden_match": mc["golden_match"],
        "tee_attestation": {"present": tee.get("present"), "label": tee.get("label")},
        "lambda": {"value": lam["value"], "floor": lam["floor"], "pass": lam["pass"],
                   "axes": lam["axes"], "uniqueness": lam["uniqueness"]},
        "inference": {"released": inference["released"],
                      "output_digest": inference.get("output_digest"),
                      "prompt_digest": inference.get("prompt_digest")},
        "slsa_provenance": slsa,
        "issued_at": _now_iso(),
        "honest_note": HONEST_NOTE,
        "sources": SOURCES,
    }
    receipt_digest = _sha384(_canon(receipt_core))
    receipt_core["receipt_digest"] = receipt_digest

    # 7) DSSE envelope over the receipt (real ECDSA-P256 in-Space; UNSIGNED-LOCAL locally)
    dsse = _sign_receipt(receipt_core)

    # 8) forum ingest (additive, off the hot path, never raises) — attested-inference provenance
    try:
        import szl_org_lambda as _ol  # noqa: F401 — presence check only; emit is best-effort
        _ol.emit("a11oy", "attest/infer",
                 {"seed": seed, "model": model, "lambda": lam["value"],
                  "quote_digest": quote["quote_digest"], "label": LABEL},
                 decision="ALLOW" if lam["pass"] else "BLOCK")
    except Exception:
        pass

    return {
        "label": LABEL,
        "seed": seed,
        "model": model,
        "stages": mc["stages"],
        # Wave-A cc-attest compatible fields (so attestinfer.js can render the tower):
        "device_identity": mc["device_identity"],
        "measurement_chain": mc["measurement_chain"],
        "final_digest": mc["final_digest"],
        "golden_match": mc["golden_match"],
        # attested-inference deepening:
        "tee_attestation": tee,
        "attestation_quote": quote,
        "lambda": lam,
        "inference": inference,
        "slsa_provenance": slsa,
        "receipt": receipt_core,
        "dsse": dsse,
        "verifiable_by_design": (
            "Recompute the measured-boot chain + quote from (seed, model), recompute Λ from the "
            "13 axes, recompute the receipt digest, then verify the DSSE envelope with "
            "`cosign verify-blob --key cosign.pub` (in-Space) — every field is checkable."
        ),
        "honest_note": HONEST_NOTE,
        "sources": SOURCES,
        "ts": _now_iso(),
    }


# ---------------------------------------------------------------------------
# HTTP handler + registration (front-inserted route, mirrors szl_tee_attest)
# ---------------------------------------------------------------------------
def _h_attest_infer(request):
    from starlette.responses import JSONResponse  # type: ignore[import]
    qp = request.query_params
    try:
        seed = int(qp.get("seed", "42"))
    except Exception:
        seed = 42
    model = qp.get("model", "szl-modeled-lm")
    try:
        result = run_attested_inference(seed, model)
        return JSONResponse(result)
    except Exception as e:  # pragma: no cover — always return a renderable 200-shaped body
        return JSONResponse({
            "label": LABEL, "seed": seed, "model": model, "error": f"{type(e).__name__}: {e}",
            "honest_note": HONEST_NOTE, "sources": SOURCES,
        }, status_code=200)


def register(app, ns: str = NS_DEFAULT) -> dict:
    """Wire GET /api/<ns>/v1/attest/infer onto the app.

    Additive. Front-inserts the route (routes.insert(0, ...)) so it wins over the generic
    /api/a11oy/{path:path} Node proxy catch-all — the proven pattern used by szl_tee_attest,
    szl_e8, szl_compliance, etc. Never raises into the caller.
    """
    path = f"/api/{ns}/v1/attest/infer"
    prefix = f"/api/{ns}/v1/attest/"
    try:
        from starlette.routing import Route  # type: ignore[import]
    except Exception as e:
        return {"registered": [], "status": f"failed:starlette-absent:{e}"}
    try:
        _r = Route(path, _h_attest_infer, methods=["GET"])
        routes = app.router.routes
        # Belt-and-suspenders: a pre-existing PARAMETRIZED route
        # /api/<ns>/v1/attest/{receipt_hash} (szl_attest_stack) would otherwise match
        # "infer" as a receipt_hash. Insert our STATIC route immediately BEFORE the first
        # such parametrized attest route so exact-path matching wins; else front-insert.
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
# No-server self-test — determinism + honesty invariants
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    a = run_attested_inference(42, "szl-modeled-lm")
    b = run_attested_inference(42, "szl-modeled-lm")
    # determinism: same (seed, model) → identical measured-boot + quote + Λ (ignore timestamps)
    assert a["final_digest"] == b["final_digest"], "measured-boot not deterministic"
    assert a["attestation_quote"]["quote_digest"] == b["attestation_quote"]["quote_digest"]
    assert a["lambda"]["value"] == b["lambda"]["value"], "Λ not deterministic"
    # honesty invariants
    assert a["label"] == "MODELED", a["label"]
    assert a["lambda"]["value"] <= 0.97 + 1e-9, "trust ceiling 0.97 violated"
    assert "Conjecture 1" in a["lambda"]["uniqueness"], "Λ must be Conjecture 1"
    assert a["receipt"]["attestation_quote_digest"] == a["attestation_quote"]["quote_digest"], \
        "receipt must embed the attestation quote digest"
    # even seed → good boot → gate passes → inference released
    assert a["golden_match"] is True and a["inference"]["released"] is True, a["golden_match"]
    # odd seed → tampered boot → attestation axis 0 → Λ=0 → gate blocks → inference withheld
    c = run_attested_inference(43, "szl-modeled-lm")
    assert c["golden_match"] is False, "odd seed should simulate a boot mismatch"
    assert c["lambda"]["value"] == 0.0, "zero-absorption should drive Λ to 0 on bad attestation"
    assert c["inference"]["released"] is False, "inference must be withheld when Λ-gate blocks"
    # DSSE present, honestly labeled (signed or UNSIGNED-LOCAL — never fabricated)
    assert "dsse" in a and ("signed" in a["dsse"]), a["dsse"].keys()
    return {"ok": True, "lambda_even": a["lambda"]["value"], "gate_even": a["lambda"]["pass"],
            "lambda_odd": c["lambda"]["value"], "gate_odd": c["lambda"]["pass"],
            "dsse_signed": a["dsse"].get("signed"), "quote_digest": a["attestation_quote"]["quote_digest"][:16]}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2, default=str))
