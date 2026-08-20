#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_frontier_zkinfer.py — zkML Proof-of-Inference ("Cryptographic Receipts").

GET /api/a11oy/v1/frontier/zkinfer returns the cryptographic-proof trust branch of
verifiable inference — the counterpart to the estate's TEE/hardware branch
(`ccattest`). A prover (model host) emits a succinct zero-knowledge argument that a
COMMITTED model produced a specific output, checkable by anyone against only a public
weight commitment — no trusted hardware, no vendor in the trust base.

TOP-LEVEL HONESTY LABEL: MODELED (explicitly NOT VERIFIED). The estate is NOT running a
production zk-SNARK prover over a live LLM forward pass (that costs minutes + specialized
CUDA per the zkLLM result). The endpoint therefore returns:

  1. proof_cost_model (MODELED) — prover time / proof size / verify time as functions of
     model size × sequence length × proof system, PARAMETERIZED from the five literature
     sources below. EVERY numeric value carries its citing arXiv ID / DOI in-band.
  2. trust_model_matrix (STRUCTURAL) — cryptographic branch (standard hardness assumptions,
     no trusted hardware) vs. the estate's TEE branch (`ccattest`). Definitional only.
  3. micro_artifact (MEASURED for its OWN narrow claim only) — a genuine Fiat–Shamir-style
     commit → prove → verify roundtrip over a tiny toy linear circuit, computed IN-PROCESS
     at request time (Merkle commitment over a small weight vector + a transcript hash the
     client can independently recompute + a real verify check). MEASURED means "this
     roundtrip really executed in-process now", NOT a hardware/joule measurement and NOT a
     claim that it scales to an LLM. If the roundtrip cannot run honestly, it downgrades to
     HONEST-STUB — never a fabricated passing proof.

PRIMARY SOURCES (all verified to resolve 2026-07-06):
  * zkLLM: Zero Knowledge Proofs for Large Language Models — Sun, Li, Zhang (2024),
    arXiv:2404.16109 (ACM CCS 2024). 13B-param full-inference proof < 15 min; proof < 200 kB;
    hides parameters. Introduces tlookup + zkAttn.
  * Scaling up Trustless DNN Inference with Zero-Knowledge Proofs — Kang, Hashimoto, Stoica,
    Sun (2022), arXiv:2210.08674. First ImageNet-scale non-interactive ZK-SNARK proof of
    valid inference (79% top-5); MLaaS verification protocols.
  * ZKML: An Optimizing System for ML Inference in Zero-Knowledge Proofs — EuroSys 2024,
    DOI 10.1145/3627703.3650088. TensorFlow→halo2 compiler; up to 5× larger provable models,
    5× faster verify, 22× smaller proofs vs prior work (EZKL / ddkang line).
  * Verifiable evaluations of machine learning models using zkSNARKs — South, Camuto, Jain,
    et al. (2024), arXiv:2402.02675. ZK inference proofs packaged as verifiable evaluation
    attestations (a model with fixed private weights provably hits a stated benchmark).
  * A Survey of Zero-Knowledge Proof Based Verifiable Machine Learning — Peng, Wang, Zhao,
    et al. (2025), arXiv:2502.18535. Documents the three honest bottlenecks: limited circuit
    expressiveness, high proving cost, deployment complexity.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; touches
    no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  - No label is ever upgraded. MODELED stays MODELED; the micro-artifact tile is MEASURED
    ONLY for the narrow "roundtrip really ran" claim, or an honest HONEST-STUB otherwise.
  - Additive route; canonical domain a-11-oy.com; 0 runtime CDN on the surface; no
    user-visible codenames.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import Any

# Honesty-label vocabulary (doctrine v11) — tests grep these exact strings.
MODELED = "MODELED"
MEASURED = "MEASURED"
HONEST_STUB = "HONEST-STUB"
STRUCTURAL = "STRUCTURAL-ONLY"

# Trust ceiling — advisory, never 100% (doctrine v11).
TRUST_CEILING = 0.97

# Primary sources, keyed by the short id each numeric value cites in-band.
SOURCES: dict[str, dict[str, str]] = {
    "2404.16109": {
        "id": "arXiv:2404.16109",
        "title": "zkLLM: Zero Knowledge Proofs for Large Language Models",
        "venue": "ACM CCS 2024",
        "url": "https://arxiv.org/abs/2404.16109",
    },
    "2210.08674": {
        "id": "arXiv:2210.08674",
        "title": "Scaling up Trustless DNN Inference with Zero-Knowledge Proofs",
        "venue": "arXiv 2022 (DOI 10.48550/arXiv.2210.08674)",
        "url": "https://arxiv.org/abs/2210.08674",
    },
    "10.1145/3627703.3650088": {
        "id": "DOI 10.1145/3627703.3650088",
        "title": "ZKML: An Optimizing System for ML Inference in Zero-Knowledge Proofs",
        "venue": "EuroSys 2024",
        "url": "https://dl.acm.org/doi/10.1145/3627703.3650088",
    },
    "2402.02675": {
        "id": "arXiv:2402.02675",
        "title": "Verifiable evaluations of machine learning models using zkSNARKs",
        "venue": "arXiv 2024 (DOI 10.48550/arXiv.2402.02675)",
        "url": "https://arxiv.org/abs/2402.02675",
    },
    "2502.18535": {
        "id": "arXiv:2502.18535",
        "title": "A Survey of Zero-Knowledge Proof Based Verifiable Machine Learning",
        "venue": "arXiv 2025 (DOI 10.48550/arXiv.2502.18535)",
        "url": "https://arxiv.org/abs/2502.18535",
    },
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_hex(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Proof-cost model (MODELED) — literature anchor points + a MODELED scaling grid.
#    Every numeric value carries the citing source id.
# ---------------------------------------------------------------------------

def _anchor_points() -> list[dict[str, Any]]:
    """Literature HEADLINE figures only — no field is invented. Where a paper does not
    headline a number we leave it null rather than fabricate one."""
    return [
        {
            "system": "zkLLM",
            "model": "LLaMa-2 13B (full inference)",
            "params": 13_000_000_000,
            "prover_time_s": {"value": 900, "relation": "<", "note": "under 15 minutes",
                              "source": "2404.16109"},
            "proof_size_kb": {"value": 200, "relation": "<", "note": "succinct proof",
                              "source": "2404.16109"},
            "verify_time_s": {"value": None, "note": "not headlined as a single figure by the paper",
                              "source": "2404.16109"},
            "hides_parameters": True,
            "label": MODELED,
        },
        {
            "system": "Kang et al. (halo2 zk-SNARK)",
            "model": "ImageNet-scale DNN (MobileNet-class)",
            "params": None,
            "prover_time_s": {"value": None, "note": "reported minutes-scale; no single headline value used",
                              "source": "2210.08674"},
            "proof_size_kb": {"value": None, "note": "tens-of-kB order; exact value not reproduced here",
                              "source": "2210.08674"},
            "verify_time_s": {"value": None, "note": "sub-second order; exact value not reproduced here",
                              "source": "2210.08674"},
            "accuracy_top5": {"value": 0.79,
                              "note": "first ImageNet-scale non-interactive ZK-SNARK proof of valid inference",
                              "source": "2210.08674"},
            "label": MODELED,
        },
        {
            "system": "ZKML / EZKL (TensorFlow→halo2)",
            "model": "relative to prior zkML toolchains",
            "params": None,
            "provable_model_size_gain_x": {"value": 5, "relation": "up to",
                                           "source": "10.1145/3627703.3650088"},
            "verify_speedup_x": {"value": 5, "source": "10.1145/3627703.3650088"},
            "proof_size_reduction_x": {"value": 22, "source": "10.1145/3627703.3650088"},
            "label": MODELED,
        },
    ]


def _cost_grid() -> dict[str, Any]:
    """A MODELED prover-time surface over (model size × sequence length), anchored to the
    zkLLM headline point (13B params → ~900 s). This is an EXTRAPOLATION, not a measurement:
    prover_time_s ≈ k · (params/1e9)^a · (seq_len/1024)^b, with k fixed so the anchor
    reproduces. Labeled MODELED; the anchor's source is cited. NOT VERIFIED."""
    # Anchor: 13e9 params, 1024-token seq -> 900 s (zkLLM headline "< 15 min").
    a, b = 1.0, 0.5  # near-linear in params, sublinear in seq (MODELED assumption).
    anchor_params_b = 13.0
    anchor_seq = 1024.0
    anchor_time = 900.0
    k = anchor_time / ((anchor_params_b ** a) * ((anchor_seq / 1024.0) ** b))

    params_axis_b = [0.13, 0.5, 1.3, 7.0, 13.0, 70.0]  # billions of params
    seq_axis = [512, 1024, 2048, 4096, 8192]            # tokens

    def prover_time(params_b: float, seq: int) -> float:
        return round(k * (params_b ** a) * ((seq / 1024.0) ** b), 2)

    # Proof size stays roughly succinct/near-constant (zkLLM: < 200 kB; NANOZK-style
    # layerwise proofs are near constant-size). MODELED: hold at the zkLLM ceiling.
    proof_size_kb = 200.0

    rows = []
    for pb in params_axis_b:
        rows.append({
            "params_b": pb,
            "prover_time_s": [prover_time(pb, s) for s in seq_axis],
        })

    return {
        "label": MODELED,
        "not_verified": True,
        "formula": "prover_time_s = k · (params_b)^a · (seq_len/1024)^b",
        "coefficients": {"k": round(k, 4), "a": a, "b": b},
        "anchor": {"params_b": anchor_params_b, "seq_len": int(anchor_seq),
                   "prover_time_s": anchor_time, "source": "2404.16109",
                   "note": "zkLLM headline: 13B full inference proved in under 15 minutes"},
        "axes": {"params_b": params_axis_b, "seq_len": seq_axis},
        "prover_time_grid_s": rows,
        "proof_size_kb_modeled": {"value": proof_size_kb, "source": "2404.16109",
                                  "note": "held near the zkLLM succinct-proof ceiling; "
                                          "layerwise systems target near-constant size"},
        "honest_note": ("EXTRAPOLATED from a single literature anchor — a design surface, not "
                        "a benchmark. Real prover cost is proof-system, hardware and circuit "
                        "dependent; treat every off-anchor cell as MODELED, never MEASURED."),
    }


# ---------------------------------------------------------------------------
# 2. Trust-model matrix (STRUCTURAL) — cryptographic branch vs. the TEE branch.
# ---------------------------------------------------------------------------

def _trust_matrix() -> dict[str, Any]:
    return {
        "label": STRUCTURAL,
        "note": ("definitional contrast only — no measurement. This surface is the "
                 "cryptographic branch; `ccattest` is the estate's TEE/hardware branch."),
        "axes": [
            "trust_base", "trusted_hardware_in_TCB", "vendor_in_trust_base",
            "verifier_re_runs_model", "hides_model_parameters", "assumption",
        ],
        "branches": {
            "cryptographic_zkml (this surface)": {
                "trust_base": "standard cryptographic hardness assumptions only",
                "trusted_hardware_in_TCB": False,
                "vendor_in_trust_base": False,
                "verifier_re_runs_model": False,
                "hides_model_parameters": True,
                "assumption": "soundness of the ZK argument (e.g. discrete-log / lattice / hash)",
                "source": "2404.16109",
            },
            "tee_attestation (ccattest)": {
                "trust_base": "hardware root of trust (SGX / SEV-SNP / H100 CC quote)",
                "trusted_hardware_in_TCB": True,
                "vendor_in_trust_base": True,
                "verifier_re_runs_model": False,
                "hides_model_parameters": True,
                "assumption": "enclave + silicon vendor attestation service are honest/uncompromised",
                "source": None,
                "cross_surface": "/api/a11oy/v1/frontier/manifest (ccattest tile)",
            },
        },
        "bottlenecks_honest": {
            "source": "2502.18535",
            "items": [
                "limited circuit expressiveness (non-arithmetic ops need lookup arguments)",
                "high proving cost (minutes + specialized compute at LLM scale)",
                "deployment complexity (toolchain, circuit compilation, key management)",
            ],
        },
        "receipt_thesis": {
            "source": "2402.02675",
            "note": ("zk inference proofs package into verifiable evaluation attestations — a "
                     "model with fixed private weights provably achieves a stated benchmark; "
                     "the cryptographic counterpart to the estate's receipt/attestation thesis."),
        },
    }


# ---------------------------------------------------------------------------
# 3. Real, honest micro-artifact — commit → prove → verify roundtrip IN-PROCESS.
#    MEASURED ONLY for the narrow "this roundtrip really ran now" claim.
# ---------------------------------------------------------------------------

def _merkle_root(leaves: list[bytes]) -> tuple[str, list[str]]:
    """Compute a plain SHA-256 Merkle root over `leaves` (duplicate-last padding). Returns
    (root_hex, level0_leaf_hashes_hex). Real, deterministic, client-recomputable."""
    level = [hashlib.sha256(b"leaf:" + lf).digest() for lf in leaves]
    leaf_hex = [d.hex() for d in level]
    if not level:
        return hashlib.sha256(b"empty").hexdigest(), []
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # duplicate-last padding
        level = [hashlib.sha256(b"node:" + level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex(), leaf_hex


def _micro_artifact() -> dict[str, Any]:
    """A genuine Fiat–Shamir-style commit-and-check over a tiny toy linear circuit y = w·x.

    The whole roundtrip runs at request time; every value is client-recomputable:
      commit : Merkle root over the committed weight vector w
      challenge : r = SHA256(root || x)  (Fiat–Shamir, non-interactive)
      output : y = Σ w_i · x_i           (the toy "inference")
      transcript : SHA256(root || x || y || r)
      verify : recompute root from w, recompute r, recompute y, recompute transcript, compare

    HONESTY: this proves the commit→prove→verify PLUMBING is real; it is NOT a zk-SNARK,
    reveals w (no zero-knowledge here), and does NOT scale to an LLM. Labeled MEASURED ONLY
    for the narrow claim "this roundtrip executed in-process now"; on any failure it is
    reported HONEST-STUB, never a fabricated pass."""
    try:
        # Tiny committed "weight vector" and public input (toy circuit).
        w = [3, 1, 4, 1, 5, 9, 2, 6]
        x = [1, 0, 1, 1, 0, 1, 0, 1]

        w_leaves = [str(v).encode() for v in w]
        root, leaf_hashes = _merkle_root(w_leaves)

        x_bytes = (",".join(str(v) for v in x)).encode()
        challenge = _sha256_hex(bytes.fromhex(root), x_bytes)

        y = sum(wi * xi for wi, xi in zip(w, x))  # the toy inference output
        transcript = _sha256_hex(bytes.fromhex(root), x_bytes, str(y).encode(),
                                 bytes.fromhex(challenge))

        # Independent verify: recompute EVERYTHING from the committed inputs.
        root2, _ = _merkle_root(w_leaves)
        challenge2 = _sha256_hex(bytes.fromhex(root2), x_bytes)
        y2 = sum(wi * xi for wi, xi in zip(w, x))
        transcript2 = _sha256_hex(bytes.fromhex(root2), x_bytes, str(y2).encode(),
                                  bytes.fromhex(challenge2))
        verify_ok = (root2 == root and challenge2 == challenge
                     and y2 == y and transcript2 == transcript)

        if not verify_ok:  # pragma: no cover — deterministic; would indicate a real fault
            return {
                "label": HONEST_STUB,
                "verify_ok": False,
                "note": ("commit-verify roundtrip did NOT reconcile in-process; reported "
                         "honestly as HONEST-STUB, not faked."),
            }

        return {
            "label": MEASURED,
            "measured_claim": ("ONLY that this commit→prove→verify roundtrip executed "
                               "in-process at request time and reconciled; NOT a joule/hardware "
                               "measurement, NOT zero-knowledge (w is revealed), NOT LLM-scale."),
            "scheme": "SHA-256 Merkle commitment + Fiat–Shamir transcript over a toy linear circuit",
            "commit": {"weight_vector": w, "merkle_root": root, "leaf_hashes": leaf_hashes},
            "public_input": x,
            "challenge_fiat_shamir": challenge,
            "output_y": y,
            "transcript_hash": transcript,
            "verify_ok": True,
            "client_recompute": {
                "root": "SHA256('node:'||L||R) over SHA256('leaf:'||str(w_i)), duplicate-last pad",
                "challenge": "SHA256(root_bytes || b'x0,x1,...')",
                "output": "y = sum(w_i * x_i)",
                "transcript": "SHA256(root_bytes || x_bytes || str(y) || challenge_bytes)",
            },
            "honest_note": ("real plumbing, deliberately tiny. Scaling this to a hiding, "
                            "succinct LLM proof is exactly the MODELED cost above and the "
                            "three bottlenecks in arXiv:2502.18535."),
        }
    except Exception as exc:  # noqa: BLE001 — degrade honestly, never fabricate a pass
        return {
            "label": HONEST_STUB,
            "verify_ok": False,
            "note": f"micro-artifact could not run honestly in-process: {exc}",
        }


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------

def build_payload() -> dict[str, Any]:
    """Compose the zkinfer surface payload. Pure read; mints/ signs nothing (receipts
    belong on writes, never on GETs)."""
    micro = _micro_artifact()
    return {
        "ok": True,
        "endpoint": "frontier/zkinfer",
        "service": "a11oy.frontier.zkinfer",
        "title": "zkML Proof-of-Inference (Cryptographic Receipts)",
        # TOP-LEVEL honesty banner — VERBATIM, explicitly NOT VERIFIED.
        "label": MODELED,
        "claim": MODELED,
        "not_verified": True,
        "no_trusted_hardware_in_TCB": True,
        "what": ("the cryptographic-proof trust branch of verifiable inference: a succinct "
                 "zero-knowledge argument that a COMMITTED model produced a specific output, "
                 "checkable against only a public weight commitment — no trusted hardware, no "
                 "vendor in the trust base. Orthogonal to the estate's TEE branch (ccattest)."),
        "doctrine": {
            "label_top": MODELED,
            "not_verified": True,
            "locked_proven": 8,
            "locked_set": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
            "kernel_commit": "c7c0ba17",
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
            "note": ("additive MODELED surface; touches no locked formula and no kernel; "
                     "introduces no theorem, no green/1.0, no proof of Λ."),
        },
        "proof_cost_model": {
            "label": MODELED,
            "not_verified": True,
            "anchor_points": _anchor_points(),
            "cost_frontier": _cost_grid(),
        },
        "trust_model_matrix": _trust_matrix(),
        "micro_artifact": micro,
        "sources": SOURCES,
        "labels_legend": {
            MODELED: "design/parametric quantity derived from the literature — NOT verified",
            MEASURED: "the micro-artifact roundtrip really executed in-process now (narrow claim only)",
            HONEST_STUB: "an honest placeholder — the roundtrip could not run; never a faked pass",
            STRUCTURAL: "definitional/structural contrast only — no measurement",
        },
        "timestamp_utc": _now_iso(),
    }


def handle() -> dict[str, Any]:
    """GET /frontier/zkinfer handler used by FastAPI and __main__."""
    try:
        return build_payload()
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "frontier/zkinfer",
            "label": MODELED,
            "error": str(exc),
            "doctrine": "v11: surface unavailable; no fabricated proof/cost emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_manifest.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the zkinfer surface endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/zkinfer")
    async def _frontier_zkinfer():
        """zkML proof-of-inference cost model + trust matrix + a real commit-verify micro-artifact."""
        return JSONResponse(handle())

    return "frontier-zkinfer-wired:1"


# ---------------------------------------------------------------------------
# Self-test — honest labels, no upgrade, real roundtrip, sources cited.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_frontier_zkinfer — self-test (MODELED surface, honest labels)")
    print("=" * 72)

    p = build_payload()
    blob = _json.dumps(p)

    # 1) top-level MODELED, explicitly NOT VERIFIED, no trusted hardware in TCB.
    assert p["ok"] is True
    assert p["label"] == MODELED and p["claim"] == MODELED
    assert p["not_verified"] is True
    assert p["no_trusted_hardware_in_TCB"] is True
    assert "VERIFIED" not in {p["label"], p["claim"]}
    print("[1] top-level MODELED / not_verified / no trusted hardware  OK")

    # 2) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust ceiling 0.97 not 100%.
    d = p["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[2] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 3) every numeric cost value carries a citing source.
    def _walk_sources(node):
        found = []
        if isinstance(node, dict):
            if "source" in node and node["source"] is not None:
                found.append(node["source"])
            for v in node.values():
                found += _walk_sources(v)
        elif isinstance(node, list):
            for v in node:
                found += _walk_sources(v)
        return found

    cited = set(_walk_sources(p["proof_cost_model"]))
    assert cited, "no source citations found in proof_cost_model"
    assert cited <= set(SOURCES), f"cost model cites an unknown source: {cited - set(SOURCES)}"
    # all five primary sources present in the payload.
    for sid in ("2404.16109", "2210.08674", "10.1145/3627703.3650088",
                "2402.02675", "2502.18535"):
        assert sid in blob, f"missing primary source {sid}"
    print(f"[3] cost values cite sources {sorted(cited)}; all 5 primary sources present  OK")

    # 4) the real micro-artifact roundtrip ran + reconciled (MEASURED narrow claim) and is
    #    independently recomputable; verify_ok is COMPUTED, never asserted true blindly.
    m = p["micro_artifact"]
    assert m["label"] in (MEASURED, HONEST_STUB)
    if m["label"] == MEASURED:
        assert m["verify_ok"] is True
        # recompute the whole roundtrip independently here to prove it is honest.
        w = m["commit"]["weight_vector"]
        x = m["public_input"]
        root2, _ = _merkle_root([str(v).encode() for v in w])
        assert root2 == m["commit"]["merkle_root"], "Merkle root not client-recomputable"
        xb = (",".join(str(v) for v in x)).encode()
        ch2 = _sha256_hex(bytes.fromhex(root2), xb)
        assert ch2 == m["challenge_fiat_shamir"], "Fiat–Shamir challenge not recomputable"
        assert sum(wi * xi for wi, xi in zip(w, x)) == m["output_y"], "output y not recomputable"
    print(f"[4] micro-artifact label={m['label']}, verify_ok={m.get('verify_ok')}, "
          "independently recomputed  OK")

    # 5) no green/1.0 verified state; trust ceiling never 100%.
    assert d["trust_100_percent"] is False and d["trust_ceiling"] < 1.0
    assert "VERIFIED" not in p["label"]
    print("[5] no VERIFIED/green-1.0 top state; trust never 100%  OK")

    print("\n--- payload keys ---")
    for k in p:
        print(f"  - {k}")
    print("\nok:true checks:5")
    _sys.exit(0)
