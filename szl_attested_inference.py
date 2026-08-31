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
pattern: device attestation → Λ-gated inference → a frozen receipt that embeds the
attestation quote digest + the Λ trust axes + SLSA-style provenance. A committed
write may sign that receipt; this GET route does not.

    GET /api/a11oy/v1/attest/infer?seed=<int>&model=<id>

The server classifies this public route HIGH_CONSEQUENCE. Missing, misspelled,
or explicitly false query input cannot downgrade the hardware gate. The GET
path is observation-only and cannot invoke the external signing verifier;
verified remote attestation is reserved for an explicit state-changing caller.

    device attestation  (reuse/extend a cc-attest-style measured-boot chain)
        └─► Λ-gate        (weighted geometric mean over the 13 trust axes; Conjecture 1)
              └─► gated inference (deterministic MODELED token stream)
                    └─► receipt (attestation quote digest + Λ axes + SLSA provenance)
                          └─► unsigned frozen envelope (GET never signs)

HONESTY (Doctrine v11 — NEVER violate)
--------------------------------------
Label = **MODELED**. This SIMULATES the advisory path deterministically from (seed, model);
high-consequence requests add a fresh 256-bit nonce before probing hardware, but that transient
security challenge is excluded from the deterministic MODELED digest, trust axes, and token stream:
there is **no real TEE, no real GPU, no NRAS/KDS network call, no real inference engine**.
Every synthetic value is derived by SHA-256/384 from the inputs so the flow is replayable and
verifiable, NOT fabricated as a live measurement. Where a REAL measurement is available the
module defers to `szl_tee_attest.get_tee_attestation()` and surfaces its honest label verbatim.
A locally read report is SAMPLE_UNVERIFIED until a trusted verifier validates its signature, certificate
chain, freshness, nonce, and reference measurements. The GET route never reads a signing secret
or signs a receipt; it returns an unsigned frozen envelope. Signing is reserved for committed
state-changing writes.

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
    https://download.01.org/intel-sgx/latest/dcap-latest/linux/docs/Intel_TDX_DCAP_Quoting_Library_API.pdf
  • in-toto / SLSA — signed attestations of "who built/ran what, when," graded L1→L3. Our
    receipt carries an SLSA-style provenance predicate (builder, buildType, invocation, digests).
    https://slsa.dev/spec/v1.0/levels  ·  https://slsa.dev/blog/2023/05/in-toto-and-slsa
  • Sigstore / Rekor — a transparency log for signatures; `cosign`/`slsa-verifier` can verify
    write-side signed receipts. This read-only response is intentionally unsigned.
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

The public HTTP route is always high-consequence and fail-closed.  Advisory
mode is available only to explicit in-process callers for deterministic
education/tests; a query parameter can never downgrade the deployed gate.
      → 200 JSON {label:"MODELED", seed, model, tee_attestation, attestation_quote,
                  measurement_chain[], lambda{axes,value,floor,pass,uniqueness}, inference,
                  receipt{...}, dsse{...}, slsa_provenance{...},
                  consequence_class:"HIGH_CONSEQUENCE", consequence_control:"SERVER",
                  honest_note, sources[]}

Also mirrors the Wave-A cc-attest shape (device_identity, measurement_chain, final_digest,
golden_match) so the attestinfer.js surface can render the same tower + the inference/receipt.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants — honest labels + citations baked in (Doctrine v11)
# ---------------------------------------------------------------------------
LABEL = "MODELED"
NS_DEFAULT = "a11oy"
HTTP_READ_CONSEQUENCE_CLASS = "HIGH_CONSEQUENCE"
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
    {"name": "Intel — TDX DCAP Quoting Library API (TDREPORT/MRTD/RTMR -> signed TD Quote)",
     "url": "https://download.01.org/intel-sgx/latest/dcap-latest/linux/docs/Intel_TDX_DCAP_Quoting_Library_API.pdf"},
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
    "real TDX/Nitro report is present, szl_tee_attest surfaces it as OBSERVED until a trusted "
    "verifier validates it. The GET route returns an UNSIGNED-READ frozen envelope and never "
    "uses a signing secret. Λ = Conjecture 1 (advisory, never green). "
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


def _attestation_quote(
    seed: int,
    model: str,
    mc: Dict[str, Any],
    prompt_digest: str,
    request_nonce: str,
) -> Dict[str, Any]:
    """Build a MODELED attestation quote in the shape of the leaders' reports.

    We mirror the SEV-SNP `REPORT_DATA` binding in the deterministic MODELED
    body while keeping the fresh security challenge in a separate
    `request_binding` field. The receipt's `quote_digest`, trust axes, and token
    stream therefore remain recomputable from (seed, model); only the live TEE
    challenge varies between consequential requests. NO real hardware quote is
    produced.
    """
    report_data = _sha384(f"REPORT_DATA|{prompt_digest}|{mc['final_digest']}".encode("utf-8"))
    quote_body = {
        "tee_family": "MODELED-CC",          # stands in for {sev-snp, tdx, h100-cc}
        "cc_mode": "ON (MODELED)",           # NVIDIA H100 CC-mode ON
        "mrtd": mc["final_digest"],          # TDX MRTD analogue = final boot measurement
        "report_data": report_data,          # SEV-SNP REPORT_DATA = binds this inference
        "measurement_stages": [c["stage"] for c in mc["stage_measurements"]],
        "vcek_kds": "MODELED (no AMD KDS / NVIDIA NRAS network call performed)",
    }
    quote_digest = _sha384(_canon(quote_body))
    return {
        "quote_body": quote_body,
        "quote_digest": quote_digest,
        "request_binding": {
            "nonce": request_nonce,
            "workload_digest": prompt_digest,
        },
        "digest_scope": "deterministic modeled quote_body; excludes transient request_binding",
        "verified_against": "MODELED golden reference (no NRAS/KDS/DCAP verifier contacted)",
        "leaders_pattern": "NVIDIA NRAS · AMD SEV-SNP REPORT_DATA/VCEK · Intel TDX MRTD",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# gated inference — deterministic MODELED token stream (no real engine)
# ---------------------------------------------------------------------------
def _tee_attestation(
    expected_nonce: str,
    expected_workload_digest: str,
    *,
    verify_external: bool = False,
) -> Dict[str, Any]:
    """Observe TEE evidence; external verification requires explicit opt-in."""
    try:
        import szl_tee_attest  # per-file COPY'd, guarded import
        return szl_tee_attest.get_tee_attestation(
            nonce=expected_nonce,
            workload_digest=expected_workload_digest,
            verify_external=verify_external,
        )
    except Exception as e:  # pragma: no cover — additive, never breaks the request
        return {
            "schema": "szl.tee-attestation/v2",
            "present": False,
            "verified": False,
            "evidence_tier": "UNAVAILABLE",
            "label": "UNAVAILABLE",
            "note": f"szl_tee_attest unavailable in this runtime ({type(e).__name__}); "
                    "no TEE probe performed; no measurement fabricated.",
        }


def _attestation_policy(
    tee: Dict[str, Any],
    high_consequence: bool,
    *,
    expected_nonce: str,
    expected_workload_digest: str,
) -> Dict[str, Any]:
    """Apply the fail-closed v2 hardware evidence policy."""
    try:
        import szl_tee_attest
        return szl_tee_attest.evaluate_attestation_policy(
            tee,
            high_consequence=high_consequence,
            expected_nonce=expected_nonce,
            expected_workload_digest=expected_workload_digest,
            reference_measurements=szl_tee_attest.configured_reference_measurements(),
            trusted_verifiers=szl_tee_attest.configured_trusted_verifiers(),
            verifier_public_keys=szl_tee_attest.configured_verifier_public_keys(),
        )
    except Exception as e:  # pragma: no cover - fail closed for consequential use
        allowed = not high_consequence
        return {
            "schema": "szl.attestation-policy/v1",
            "high_consequence": bool(high_consequence),
            "verified_evidence": False,
            "allowed": allowed,
            "verdict": "ALLOW" if allowed else "BLOCK",
            "reason": (
                "modeled, non-consequential read; hardware evidence is advisory"
                if allowed
                else f"attestation policy unavailable ({type(e).__name__}); fail-closed block"
            ),
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

    Maps the run onto the SLSA predicate shape (builder, buildType, invocation, subject digests).
    This read artifact is unsigned; a committed write can bind and sign the predicate later.
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
        "slsa_level_claim": "L1 (honest) — provenance present; NOT an L2/L3 claim.",
        "verify_with": "unsigned read artifact; sign only when a state-changing write is committed",
        "label": LABEL,
    }


# ---------------------------------------------------------------------------
# receipt freeze — read paths never sign or use a signing secret
# ---------------------------------------------------------------------------
def _freeze_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Freeze a deterministic unsigned envelope for this read-only surface."""
    body = _canon(receipt)
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
        "signed": False,
        "_dsse": "DSSEv1",
        "local_label": "UNSIGNED-READ",
        "honesty": (
            "UNSIGNED-READ — GET is read-only; signing is reserved for a committed "
            "state-changing write"
        ),
        "_pae_sha256": _sha256(
            b"DSSEv1 "
            + str(len(PAYLOAD_TYPE)).encode()
            + b" "
            + PAYLOAD_TYPE.encode()
            + b" "
            + str(len(body)).encode()
            + b" "
            + body
        ),
    }


def run_attested_inference(
    seed: int,
    model: str,
    *,
    high_consequence: bool = True,
    verify_external: bool = False,
) -> Dict[str, Any]:
    """The full attested-inference flow, deterministic + MODELED. Returns the response dict.

    device attestation → Λ-gate → gated inference → receipt (quote digest + Λ axes + SLSA
    provenance) → DSSE envelope. Verifiable-by-design: everything is recomputable from
    (seed, model). External quote verification is observation-only by default and
    must be explicitly enabled by an authorized state-changing caller.
    """
    seed = int(seed)
    model = str(model or "szl-modeled-lm")

    # 1) device attestation (measured-boot chain — extends Wave-A cc-attest)
    mc = _measurement_chain(seed, model)

    # 2) bind the (about-to-run) inference into the attestation quote (SEV-SNP REPORT_DATA style)
    prompt_digest = _sha384(f"attested-inference probe seed={seed} model={model}".encode("utf-8"))
    request_nonce = (
        secrets.token_hex(32)
        if high_consequence
        else _sha256(f"advisory-nonce|{seed}|{model}".encode("utf-8"))
    )
    quote = _attestation_quote(seed, model, mc, prompt_digest, request_nonce)
    tee = _tee_attestation(
        request_nonce,
        prompt_digest,
        verify_external=verify_external,
    )
    attestation_policy = _attestation_policy(
        tee,
        high_consequence,
        expected_nonce=quote["request_binding"]["nonce"],
        expected_workload_digest=prompt_digest,
    )

    # 3) Λ-gate over the 13 trust axes; attestation axis hard-coupled to the boot match
    lam = _lambda_axes(seed, model, quote["quote_digest"], mc["golden_match"])

    # 4) gated inference (withheld if Λ-gate blocks — CoCo KBS style)
    effective_release = bool(
        lam["pass"] and attestation_policy["allowed"]
    )
    release_gate = {
        "pass": effective_release,
        "verdict": "RELEASE" if effective_release else "BLOCK",
        "lambda_pass": bool(lam["pass"]),
        "attestation_allowed": bool(attestation_policy["allowed"]),
    }
    inference = _gated_inference(
        seed,
        model,
        effective_release,
        quote["quote_digest"],
    )
    if lam["pass"] and not attestation_policy["allowed"]:
        inference["reason"] = attestation_policy["reason"]

    # 5) SLSA-style provenance predicate
    slsa = _slsa_provenance(seed, model, mc, quote["quote_digest"], inference)

    # 6) assemble the receipt (embeds attestation quote digest + Λ axes + SLSA provenance)
    receipt_core: Dict[str, Any] = {
        "schema": "szl.attested-inference/v2",
        "label": LABEL,
        "seed": seed,
        "model": model,
        "high_consequence": bool(high_consequence),
        "external_verification_requested": bool(verify_external),
        "device_identity": mc["device_identity"],
        "attestation_quote_digest": quote["quote_digest"],
        "mrtd": mc["final_digest"],
        "golden_match": mc["golden_match"],
        "tee_attestation": {
            "schema": tee.get("schema"),
            "present": tee.get("present"),
            "verified": tee.get("verified"),
            "type": tee.get("type"),
            "quote_digest": tee.get("quote_digest"),
            "measurement": tee.get("measurement"),
            "verified_at": tee.get("verified_at"),
            "verifier": tee.get("verifier"),
            "verifier_envelope": tee.get("verifier_envelope"),
            "evidence_tier": tee.get("evidence_tier"),
            "label": tee.get("label"),
        },
        "attestation_policy": attestation_policy,
        "release_gate": release_gate,
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

    # 7) Freeze an unsigned read artifact. Signing is reserved for committed writes.
    dsse = _freeze_receipt(receipt_core)

    # 8) Deliberately do not append to the forum/ledger here. This helper serves
    # the public GET path, so it must remain observation-only. A separately
    # authorized state-changing operation may persist the returned receipt after
    # its governance gate; reads never perform that write implicitly.

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
        "attestation_policy": attestation_policy,
        "release_gate": release_gate,
        "attestation_quote": quote,
        "lambda": lam,
        "inference": inference,
        "slsa_provenance": slsa,
        "receipt": receipt_core,
        "dsse": dsse,
        "verifiable_by_design": (
            "Recompute the measured-boot chain + quote from (seed, model), recompute Λ from the "
            "13 axes, recompute the receipt digest, and confirm signed=false for this GET. "
            "A committed write requires a separately verifiable signed receipt."
        ),
        "honest_note": HONEST_NOTE,
        "sources": SOURCES,
        "ts": _now_iso(),
    }


# ---------------------------------------------------------------------------
# HTTP handler + registration (front-inserted route, mirrors szl_tee_attest)
# ---------------------------------------------------------------------------
def _http_read_requires_attestation(query_params) -> bool:
    """Return the server-owned consequence verdict for the modeled GET.

    This checked-in route is HIGH_CONSEQUENCE. A caller may strengthen an
    advisory route in another deployment, but false, missing, or misspelled
    query input can never downgrade a route classified consequential by the
    server.
    """
    server_requires = HTTP_READ_CONSEQUENCE_CLASS == "HIGH_CONSEQUENCE"
    caller_requests_strict = str(
        query_params.get("high_consequence", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    return server_requires or caller_requests_strict


def _h_attest_infer(request):
    from starlette.responses import JSONResponse  # type: ignore[import]
    qp = request.query_params
    try:
        seed = int(qp.get("seed", "42"))
    except Exception:
        seed = 42
    model = qp.get("model", "szl-modeled-lm")
    high_consequence = _http_read_requires_attestation(qp)
    try:
        result = run_attested_inference(
            seed,
            model,
            high_consequence=high_consequence,
            verify_external=False,
        )
        result["consequence_class"] = HTTP_READ_CONSEQUENCE_CLASS
        result["consequence_control"] = "SERVER"
        return JSONResponse(result)
    except Exception as e:  # pragma: no cover — always return a renderable 200-shaped body
        return JSONResponse({
            "label": LABEL, "seed": seed, "model": model,
            "high_consequence": high_consequence,
            "consequence_class": HTTP_READ_CONSEQUENCE_CLASS,
            "consequence_control": "SERVER",
            "error": f"{type(e).__name__}: {e}",
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
    a = run_attested_inference(42, "szl-modeled-lm", high_consequence=False)
    b = run_attested_inference(42, "szl-modeled-lm", high_consequence=False)
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
    c = run_attested_inference(43, "szl-modeled-lm", high_consequence=False)
    assert c["golden_match"] is False, "odd seed should simulate a boot mismatch"
    assert c["lambda"]["value"] == 0.0, "zero-absorption should drive Λ to 0 on bad attestation"
    assert c["inference"]["released"] is False, "inference must be withheld when Λ-gate blocks"
    # Read artifact is frozen and unsigned; GET never performs receipt-on-read signing.
    assert a["dsse"]["signed"] is False
    assert a["dsse"]["local_label"] == "UNSIGNED-READ"
    # high-consequence release is blocked without a fresh externally verified quote
    high = run_attested_inference(42, "szl-modeled-lm", high_consequence=True)
    assert high["attestation_policy"]["verdict"] == "BLOCK"
    assert high["inference"]["released"] is False
    return {"ok": True, "lambda_even": a["lambda"]["value"], "gate_even": a["lambda"]["pass"],
            "lambda_odd": c["lambda"]["value"], "gate_odd": c["lambda"]["pass"],
            "dsse_signed": a["dsse"].get("signed"),
            "high_consequence": high["attestation_policy"]["verdict"],
            "quote_digest": a["attestation_quote"]["quote_digest"][:16]}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2, default=str))
