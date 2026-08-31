#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_frontier_fmverif.py — Proof-Carrying Inference (machine-checkable certificates).

GET /api/a11oy/v1/frontier/fmverif returns the SZL SYNTHESIS surface for
proof-carrying inference: the idea that a governed inference can ship with a single,
machine-checkable CERTIFICATE binding four independent guarantees —

  1. a FORMAL proof obligation (Lean/Coq proof-carrying code — Necula's PCC discipline
     applied to a model's safety/robustness property, checked by a small trusted checker),
  2. a ZERO-KNOWLEDGE proof-of-inference (a succinct argument that a COMMITTED model
     produced the specific output — the zkLLM branch, orthogonal to trusted hardware),
  3. the estate's signed RECEIPT chain (a Khipu envelope binding the action's provenance),
  4. a BFT QUORUM attestation over that receipt (multiple validators agreeing the
     certificate was seen and admitted).

TOP-LEVEL HONESTY LABEL: MODELED. The SZL SYNTHESIS — that these four compose into one
end-to-end machine-checkable certificate for a live LLM forward pass — is CONJECTURE,
explicitly NOT a theorem and NOT VERIFIED. The estate is NOT running a production Lean
proof over a live model, NOT running a zk-SNARK prover over a live forward pass, and does
NOT claim BFT safety as proven (that is Khipu BFT = Conjecture 2). The endpoint therefore
returns:

  1. certificate_model (MODELED) — the STRUCTURE of a proof-carrying-inference certificate:
     the four component obligations, what each would prove, the trusted-computing-base each
     adds, and its honest per-component label. Definitional; no component is upgraded.
  2. cost_model (MODELED) — a PARAMETRIC cost envelope for issuing such a certificate,
     anchored to real literature headline figures (formal-verification solve time from the
     Marabou line; zk prover time from the zkLLM headline). Every numeric value carries its
     citing arXiv ID / DOI in-band. EXTRAPOLATED, never a benchmark.
  3. micro_artifact (MEASURED for its OWN narrow claim only) — a genuine in-process
     certificate ASSEMBLY + VERIFY roundtrip: four component digests (formal obligation, zk
     commitment, receipt, quorum attestation) are bound into a Merkle root + a Fiat–Shamir
     transcript, then independently recomputed and checked. MEASURED means ONLY "this
     binding roundtrip really executed in-process now and reconciled" — NOT a real proof,
     NOT zero-knowledge, NOT LLM-scale, NOT a BFT safety claim. On any failure it downgrades
     to HONEST-STUB — never a fabricated passing certificate.

PRIMARY SOURCES (all verified to resolve 2026-07-07):
  * Proof-Carrying Code — George C. Necula (POPL 1997), DOI 10.1145/263699.263712. The
    foundational PCC discipline: untrusted code ships with a machine-checkable safety proof
    a small trusted checker validates before execution. The template this surface applies to
    inference.
  * A Verified Compiler for a Functional Tensor Language — Liu, Bernstein, Chlipala,
    Ragan-Kelley (PLDI 2024), DOI 10.1145/3656390 (PACMPL). A machine-checked (Coq) verified
    compiler for a tensor language — the modern verified-ML end of the PCC lineage.
  * Marabou 2.0: A Versatile Formal Analyzer of Neural Networks — Wu, Isac, Zeljić, et al.
    (CAV 2024), arXiv:2401.14461, DOI 10.1007/978-3-031-65630-9_13. State-of-practice formal
    verification of neural-network properties (robustness / safety) via SMT + abstraction.
  * zkLLM: Zero Knowledge Proofs for Large Language Models — Sun, Li, Zhang (ACM CCS 2024),
    arXiv:2404.16109. 13B-param full-inference proof under 15 min; proof < 200 kB; hides
    parameters. The zero-knowledge proof-of-inference branch.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; touches
    no locked formula and no kernel.
  - The SZL synthesis is CONJECTURE (never theorem/green/1.0). Λ stays Conjecture 1; Khipu
    BFT stays Conjecture 2. Trust ceiling 0.97, never 100%.
  - No label is ever upgraded. MODELED stays MODELED; the micro-artifact tile is MEASURED
    ONLY for the narrow "binding roundtrip really ran" claim, or HONEST-STUB otherwise.
  - Additive route; canonical domain a-11-oy.com; 0 runtime CDN on the surface; no
    user-visible codenames. Pure read — mints/signs nothing (receipts belong on writes).
"""
import datetime
import hashlib
from typing import Any

# Honesty-label vocabulary (doctrine v11) — tests grep these exact strings.
MODELED = "MODELED"
MEASURED = "MEASURED"
HONEST_STUB = "HONEST-STUB"
STRUCTURAL = "STRUCTURAL-ONLY"
CONJECTURE = "CONJECTURE"

# Trust ceiling — advisory, never 100% (doctrine v11).
TRUST_CEILING = 0.97

# Primary sources, keyed by the short id each numeric value cites in-band.
SOURCES: dict[str, dict[str, str]] = {
    "10.1145/263699.263712": {
        "id": "DOI 10.1145/263699.263712",
        "title": "Proof-Carrying Code",
        "author": "George C. Necula",
        "venue": "POPL 1997",
        "url": "https://dl.acm.org/doi/10.1145/263699.263712",
    },
    "10.1145/3656390": {
        "id": "DOI 10.1145/3656390",
        "title": "A Verified Compiler for a Functional Tensor Language",
        "author": "Liu, Bernstein, Chlipala, Ragan-Kelley",
        "venue": "PLDI 2024 (PACMPL)",
        "url": "https://dl.acm.org/doi/10.1145/3656390",
    },
    "2401.14461": {
        "id": "arXiv:2401.14461",
        "title": "Marabou 2.0: A Versatile Formal Analyzer of Neural Networks",
        "author": "Wu, Isac, Zeljić, et al.",
        "venue": "CAV 2024 (DOI 10.1007/978-3-031-65630-9_13)",
        "url": "https://arxiv.org/abs/2401.14461",
    },
    "2404.16109": {
        "id": "arXiv:2404.16109",
        "title": "zkLLM: Zero Knowledge Proofs for Large Language Models",
        "author": "Sun, Li, Zhang",
        "venue": "ACM CCS 2024",
        "url": "https://arxiv.org/abs/2404.16109",
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
# 1. Certificate model (MODELED / STRUCTURAL) — the four component obligations.
# ---------------------------------------------------------------------------

def _certificate_model() -> dict[str, Any]:
    """The STRUCTURE of a proof-carrying-inference certificate: four independent guarantees
    a governed inference could bind together. Definitional only — each component keeps its
    own honest label; none is upgraded and none is claimed live."""
    return {
        "label": STRUCTURAL,
        "not_verified": True,
        "note": ("definitional contrast only — the shape of a proof-carrying-inference "
                 "certificate. No component is running live at LLM scale; each keeps its "
                 "own honest label."),
        "components": [
            {
                "name": "formal_proof_obligation",
                "role": ("a Lean/Coq machine-checkable proof of a stated model property "
                         "(e.g. a robustness / safety obligation), validated by a small "
                         "trusted checker — Necula's proof-carrying-code discipline applied "
                         "to inference."),
                "proves": "the model satisfies a formally-stated property (bounded scope)",
                "trusted_base": "a small proof checker (no need to trust the prover)",
                "label": MODELED,
                "source": "10.1145/263699.263712",
                "modern_anchor": "10.1145/3656390",
                "cross_surface": "/api/a11oy/v1/frontier/formalmath",
            },
            {
                "name": "zk_proof_of_inference",
                "role": ("a succinct zero-knowledge argument that a COMMITTED model produced "
                         "the specific output, checkable against only a public weight "
                         "commitment — no trusted hardware, no vendor in the trust base."),
                "proves": "this committed model produced this output (hiding parameters)",
                "trusted_base": "standard cryptographic hardness assumptions only",
                "label": MODELED,
                "source": "2404.16109",
                "cross_surface": "/api/a11oy/v1/frontier/zkinfer",
            },
            {
                "name": "receipt_chain",
                "role": ("a signed Khipu envelope binding the governed action's provenance "
                         "(inputs, policy verdict, model identity) into the estate's "
                         "receipt-on-write chain."),
                "proves": "the action's provenance was sealed at write time (not on read)",
                "trusted_base": "the estate signing key + receipt substrate",
                "label": MODELED,
                "source": None,
                "cross_surface": "/api/a11oy/v1/provenance/receipt",
            },
            {
                "name": "bft_quorum_attestation",
                "role": ("a Byzantine-fault-tolerant quorum of validators attesting the "
                         "certificate was seen and admitted — the agreement layer over the "
                         "receipt."),
                "proves": "a quorum agreed the certificate was admitted (liveness/agreement)",
                "trusted_base": "< 1/3 Byzantine validators (Khipu BFT = Conjecture 2)",
                "label": CONJECTURE,
                "source": None,
                "note": "Khipu BFT safety is Conjecture 2 — NOT a theorem, never proven green.",
            },
        ],
    }


# ---------------------------------------------------------------------------
# 2. Cost model (MODELED) — parametric certificate-issuance envelope.
#    Every numeric value carries the citing source id.
# ---------------------------------------------------------------------------

def _cost_model() -> dict[str, Any]:
    """A MODELED cost envelope for ISSUING a proof-carrying-inference certificate, anchored
    to real literature headline points. This is an EXTRAPOLATION, not a measurement: the
    dominant costs are the formal-verification solve and the zk proof, which are additive
    (they can run in parallel, but the envelope reports the honest sum as an upper bound).
    NOT VERIFIED — treat every cell as MODELED, never MEASURED."""
    return {
        "label": MODELED,
        "not_verified": True,
        "note": ("EXTRAPOLATED from literature anchors — a design envelope, not a benchmark. "
                 "Real cost is property-, model-, proof-system- and hardware-dependent."),
        "anchor_points": [
            {
                "component": "formal_proof_obligation",
                "system": "Marabou 2.0 (SMT + abstraction)",
                "headline": ("per-property NN verification is decidable but NP-hard in "
                             "general; solve time ranges seconds→timeout by property and "
                             "network size — no single headline value is reproduced here"),
                "value_reproduced": None,
                "source": "2401.14461",
                "label": MODELED,
            },
            {
                "component": "zk_proof_of_inference",
                "system": "zkLLM",
                "model": "LLaMa-2 13B (full inference)",
                "prover_time_s": {"value": 900, "relation": "<", "note": "under 15 minutes",
                                  "source": "2404.16109"},
                "proof_size_kb": {"value": 200, "relation": "<", "note": "succinct proof",
                                  "source": "2404.16109"},
                "hides_parameters": True,
                "label": MODELED,
            },
            {
                "component": "verified_compilation",
                "system": "ATL verified tensor compiler (Coq)",
                "headline": ("the model pipeline itself can be compiled by a machine-checked "
                             "verified compiler; verification cost is paid once at build "
                             "time, not per inference"),
                "value_reproduced": None,
                "source": "10.1145/3656390",
                "label": MODELED,
            },
        ],
        "issuance_envelope": {
            "label": MODELED,
            "formula": ("cert_issue_time_s ≈ formal_solve_s + zk_prover_s "
                        "(receipt sign + quorum round are milliseconds-order, dominated)"),
            "dominant_term_source": "2404.16109",
            "note": ("the zk prover term dominates at LLM scale (minutes); the formal-solve "
                     "term is per-property and the verified-compilation term is amortized at "
                     "build time. Honest upper bound = sum; parallelism only helps."),
        },
        "verify_side": {
            "label": MODELED,
            "note": ("verification is designed to be cheap on all three cryptographic/formal "
                     "legs: the proof checker is small (PCC), the zk verify is succinct "
                     "(< second order), and the receipt/quorum check is a signature set. The "
                     "asymmetry (expensive to issue, cheap to check) is the whole point."),
            "checker_source": "10.1145/263699.263712",
        },
    }


# ---------------------------------------------------------------------------
# 3. Real, honest micro-artifact — certificate ASSEMBLY + VERIFY roundtrip in-process.
#    MEASURED ONLY for the narrow "this binding roundtrip really ran now" claim.
# ---------------------------------------------------------------------------

def _merkle_root(leaves: list[bytes]) -> tuple[str, list[str]]:
    """Plain SHA-256 Merkle root over `leaves` (duplicate-last padding). Returns
    (root_hex, leaf_hashes_hex). Real, deterministic, client-recomputable."""
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
    """A genuine in-process certificate ASSEMBLY + VERIFY roundtrip.

    Four component digests stand in for the four guarantees (each is a real SHA-256 over a
    labeled, client-recomputable string — a STAND-IN, never a real proof):
      formal   : H('formal:'   || property_statement)
      zk       : H('zk:'       || model_commitment || output)
      receipt  : H('receipt:'  || action_id || model_commitment)
      quorum   : H('quorum:'   || receipt_digest || validator_set)
    They are bound into a Merkle root (the certificate root), a Fiat–Shamir challenge
    r = H(root || context), and a transcript H(root || context || r). Verify recomputes
    EVERYTHING from the inputs and compares.

    HONESTY: this proves the ASSEMBLY→BIND→VERIFY plumbing is real; it is NOT a real Lean
    proof, NOT a zk-SNARK, NOT zero-knowledge, NOT LLM-scale, and NOT a BFT safety claim.
    Labeled MEASURED ONLY for the narrow claim "this binding roundtrip executed in-process
    now and reconciled"; on any failure it is HONEST-STUB, never a fabricated pass."""
    try:
        # Deterministic toy certificate context (a governed inference stand-in).
        property_statement = "output_within_declared_output_set(y) under committed policy P"
        model_commitment = _sha256_hex(b"committed-model-weights:toy-linear-8")
        output = "y=31"
        action_id = "action:fmverif:selftest:0001"
        validator_set = "v1,v2,v3,v4"  # 4 validators (BFT tolerates < 1/3 Byzantine)

        formal_d = _sha256_hex(b"formal:", property_statement.encode())
        zk_d = _sha256_hex(b"zk:", model_commitment.encode(), output.encode())
        receipt_d = _sha256_hex(b"receipt:", action_id.encode(), model_commitment.encode())
        quorum_d = _sha256_hex(b"quorum:", receipt_d.encode(), validator_set.encode())

        components = [formal_d, zk_d, receipt_d, quorum_d]
        leaves = [bytes.fromhex(d) for d in components]
        root, leaf_hashes = _merkle_root(leaves)

        context = _sha256_hex(action_id.encode(), model_commitment.encode())
        challenge = _sha256_hex(bytes.fromhex(root), bytes.fromhex(context))
        transcript = _sha256_hex(bytes.fromhex(root), bytes.fromhex(context),
                                 bytes.fromhex(challenge))

        # Independent verify: recompute EVERY digest, the root, challenge, transcript.
        formal2 = _sha256_hex(b"formal:", property_statement.encode())
        zk2 = _sha256_hex(b"zk:", model_commitment.encode(), output.encode())
        receipt2 = _sha256_hex(b"receipt:", action_id.encode(), model_commitment.encode())
        quorum2 = _sha256_hex(b"quorum:", receipt2.encode(), validator_set.encode())
        root2, _ = _merkle_root([bytes.fromhex(d) for d in (formal2, zk2, receipt2, quorum2)])
        context2 = _sha256_hex(action_id.encode(), model_commitment.encode())
        challenge2 = _sha256_hex(bytes.fromhex(root2), bytes.fromhex(context2))
        transcript2 = _sha256_hex(bytes.fromhex(root2), bytes.fromhex(context2),
                                  bytes.fromhex(challenge2))

        verify_ok = (root2 == root and challenge2 == challenge
                     and transcript2 == transcript
                     and formal2 == formal_d and zk2 == zk_d
                     and receipt2 == receipt_d and quorum2 == quorum_d)

        if not verify_ok:  # pragma: no cover — deterministic; would indicate a real fault
            return {
                "label": HONEST_STUB,
                "verify_ok": False,
                "note": ("certificate assembly→verify roundtrip did NOT reconcile in-process; "
                         "reported honestly as HONEST-STUB, not faked."),
            }

        return {
            "label": MEASURED,
            "measured_claim": ("ONLY that this certificate assembly→bind→verify roundtrip "
                               "executed in-process at request time and reconciled; NOT a real "
                               "Lean proof, NOT a zk-SNARK, NOT zero-knowledge, NOT LLM-scale, "
                               "NOT a BFT safety claim."),
            "scheme": ("SHA-256 Merkle binding over four component digests + Fiat–Shamir "
                       "transcript (component digests are labeled stand-ins, not real proofs)"),
            "component_digests": {
                "formal_proof_obligation": formal_d,
                "zk_proof_of_inference": zk_d,
                "receipt_chain": receipt_d,
                "bft_quorum_attestation": quorum_d,
            },
            "certificate_root": root,
            "leaf_hashes": leaf_hashes,
            "context": context,
            "challenge_fiat_shamir": challenge,
            "transcript_hash": transcript,
            "verify_ok": True,
            "client_recompute": {
                "formal": "SHA256(b'formal:' || property_statement)",
                "zk": "SHA256(b'zk:' || model_commitment || output)",
                "receipt": "SHA256(b'receipt:' || action_id || model_commitment)",
                "quorum": "SHA256(b'quorum:' || receipt_digest || validator_set)",
                "root": "SHA256('node:'||L||R) over SHA256('leaf:'||digest_bytes), dup-last pad",
                "challenge": "SHA256(root_bytes || context_bytes)",
                "transcript": "SHA256(root_bytes || context_bytes || challenge_bytes)",
            },
            "honest_note": ("real binding plumbing, deliberately tiny with stand-in digests. "
                            "Turning each stand-in into a REAL guarantee (a Lean proof, a zk "
                            "proof, a signed receipt, a live BFT quorum) is exactly the MODELED "
                            "cost above and the open synthesis CONJECTURE below."),
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
    """Compose the fmverif surface payload. Pure read; mints/signs nothing (receipts
    belong on writes, never on GETs)."""
    micro = _micro_artifact()
    return {
        "ok": True,
        "endpoint": "frontier/fmverif",
        "service": "a11oy.frontier.fmverif",
        "title": "Proof-Carrying Inference (Machine-Checkable Certificates)",
        # TOP-LEVEL honesty banner — VERBATIM. Surface MODELED; SZL synthesis CONJECTURE.
        "label": MODELED,
        "claim": CONJECTURE,
        "not_verified": True,
        "synthesis_is_conjecture": True,
        "what": ("a MODELED model of proof-carrying inference: a governed inference that ships "
                 "with ONE machine-checkable certificate binding a formal proof obligation "
                 "(Lean/Coq PCC), a zero-knowledge proof-of-inference (zkLLM), the signed "
                 "receipt chain, and a BFT quorum attestation. The SZL claim that these four "
                 "compose end-to-end for a live LLM is CONJECTURE — not a theorem, NOT "
                 "VERIFIED."),
        "doctrine": {
            "label_top": MODELED,
            "synthesis_label": CONJECTURE,
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
            "note": ("additive MODELED surface; touches no locked formula and no kernel; the "
                     "synthesis is a CONJECTURE, introduces no theorem, no green/1.0, no proof "
                     "of Λ, and no proof of BFT safety."),
        },
        "certificate_model": _certificate_model(),
        "cost_model": _cost_model(),
        "micro_artifact": micro,
        "synthesis": {
            "label": CONJECTURE,
            "not_verified": True,
            "statement": ("CONJECTURE (SZL synthesis): the four guarantees above can be bound "
                          "into a single machine-checkable certificate for a governed "
                          "inference, such that a verifier cheaply checks — without trusting "
                          "the prover, a chip vendor, or re-running the model — that (a) the "
                          "output satisfies a formally-stated property, (b) a committed model "
                          "produced it, (c) its provenance was sealed, and (d) a BFT quorum "
                          "admitted it."),
            "why_not_theorem": ("no end-to-end formal proof exists; each leg is itself an open "
                                "systems problem at LLM scale (formal NN verification is "
                                "NP-hard per property; zk proving costs minutes; BFT safety is "
                                "Conjecture 2). The composition is a design thesis, not a "
                                "result."),
            "sources": ["10.1145/263699.263712", "10.1145/3656390",
                        "2401.14461", "2404.16109"],
        },
        "sources": SOURCES,
        "labels_legend": {
            MODELED: "design/parametric quantity derived from the literature — NOT verified",
            CONJECTURE: "the SZL synthesis — a design thesis, explicitly NOT a theorem",
            MEASURED: "the micro-artifact binding roundtrip really executed in-process now "
                      "(narrow claim only)",
            HONEST_STUB: "an honest placeholder — the roundtrip could not run; never a faked pass",
            STRUCTURAL: "definitional/structural contrast only — no measurement",
        },
        "timestamp_utc": _now_iso(),
    }


def handle() -> dict[str, Any]:
    """GET /frontier/fmverif handler used by FastAPI and __main__."""
    try:
        return build_payload()
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "frontier/fmverif",
            "label": MODELED,
            "error": str(exc),
            "doctrine": "v11: surface unavailable; no fabricated proof/cost/certificate emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_zkinfer.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the fmverif surface endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/fmverif")
    async def _frontier_fmverif():
        """Proof-carrying inference: certificate model + cost model + a real assembly-verify micro-artifact."""
        return JSONResponse(handle())

    return "frontier-fmverif-wired:1"


# ---------------------------------------------------------------------------
# Self-test — honest labels, no upgrade, real roundtrip, sources cited.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_frontier_fmverif — self-test (MODELED surface, CONJECTURE synthesis)")
    print("=" * 72)

    p = build_payload()
    blob = _json.dumps(p)

    # 1) top-level MODELED, synthesis CONJECTURE, explicitly NOT VERIFIED.
    assert p["ok"] is True
    assert p["label"] == MODELED and p["claim"] == CONJECTURE
    assert p["not_verified"] is True and p["synthesis_is_conjecture"] is True
    assert "VERIFIED" not in {p["label"], p["claim"]}
    print("[1] top-level MODELED / synthesis CONJECTURE / not_verified  OK")

    # 2) doctrine: locked-8 exact, adds nothing, Λ/BFT conjectures, trust 0.97 not 100%.
    d = p["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[2] doctrine: locked-8 exact, +0, Λ/BFT conjectures, trust 0.97 (not 100%)  OK")

    # 3) every cited source resolves to the SOURCES table; all 4 primary sources present.
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

    cited = set(_walk_sources(p))
    assert cited, "no source citations found"
    assert cited <= set(SOURCES), f"cites an unknown source: {cited - set(SOURCES)}"
    for sid in ("10.1145/263699.263712", "10.1145/3656390", "2401.14461", "2404.16109"):
        assert sid in blob, f"missing primary source {sid}"
    print(f"[3] citations {sorted(cited)}; all 4 primary sources present  OK")

    # 4) the real micro-artifact roundtrip ran + reconciled (MEASURED narrow claim) and is
    #    independently recomputable; verify_ok is COMPUTED, never asserted true blindly.
    m = p["micro_artifact"]
    assert m["label"] in (MEASURED, HONEST_STUB)
    if m["label"] == MEASURED:
        assert m["verify_ok"] is True
        cd = m["component_digests"]
        # recompute the four leaves + root here to prove it is honest.
        leaves = [bytes.fromhex(cd[k]) for k in
                  ("formal_proof_obligation", "zk_proof_of_inference",
                   "receipt_chain", "bft_quorum_attestation")]
        root2, _ = _merkle_root(leaves)
        assert root2 == m["certificate_root"], "certificate root not client-recomputable"
        ch2 = _sha256_hex(bytes.fromhex(root2), bytes.fromhex(m["context"]))
        assert ch2 == m["challenge_fiat_shamir"], "Fiat–Shamir challenge not recomputable"
    print(f"[4] micro-artifact label={m['label']}, verify_ok={m.get('verify_ok')}, "
          "independently recomputed  OK")

    # 5) no green/1.0 verified state; synthesis stays CONJECTURE; trust never 100%.
    assert d["trust_100_percent"] is False and d["trust_ceiling"] < 1.0
    assert p["synthesis"]["label"] == CONJECTURE
    assert "VERIFIED" not in p["label"]
    print("[5] no VERIFIED/green-1.0 state; synthesis CONJECTURE; trust never 100%  OK")

    print("\n--- payload keys ---")
    for k in p:
        print(f"  - {k}")
    print("\nok:true checks:5")
    _sys.exit(0)
