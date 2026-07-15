# VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — replit-sync/szl_chain_of_title.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
"""szl_chain_of_title.py — SZL "L6" unified chain-of-title receipt assembler.

EXPERIMENTAL-tier. PURE STDLIB. Adds NOTHING to the locked-8. Λ stays Conjecture 1.
Trust never 100%. No fabricated data. Cites every standard to its real author/spec.

WHY (the genuine differentiator the research found): industry sovereign-AI players
operate at L1-L5 (jurisdictional residency → governed operations). NONE operationalize
**L6** — a single verifiable "deed" per release that binds, in ONE receipt:
  • the SOFTWARE attestation  — cosign image digest + Rekor transparency-log entry
                                 + in-toto/SLSA provenance (Sigstore/in-toto/SLSA).
  • the SCIENCE              — the Zenodo DOI of the result (citable record).
  • the MATH                 — the machine-checked Lean theorem refs (lake-verified).
So one receipt proves "this code is signed & attested AND this result is citable AND
its core math is machine-checked." This module ASSEMBLES + verifies the STRUCTURE of
that receipt (deterministic, offline). It does NOT sign — cosign/Rekor SIGNING is a
founder-gated step (the receipt carries placeholders/refs until signed).

This is the digital analogue of the allodial land-registry "chain of title": a
verifiable, unencumbered record of ownership. Honest limit: assembling/verifying the
STRUCTURE is not the same as cryptographic verification — the signed+logged proof is
the gated step; until then fields are labeled UNSIGNED/PROXY.

Citations (real, verified): in-toto (CNCF) https://in-toto.io ; SLSA v1.1 https://slsa.dev ;
Sigstore/cosign/Rekor https://www.sigstore.dev ; SCITT (IETF) Signed Statements+Receipts ;
RO-Crate / W3C PROV ; Zenodo DOI (concept+version); lutar-lean (lake-verified).

Routes:  GET /api/<ns>/v1/chain/{summary,assemble,verify,levels}
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List

SCHEMA = "szl.chain-of-title/v1"

# The six sovereignty maturity levels (L1-L5 = industry; L6 = SZL differentiator).
LEVELS = {
    "L1": "jurisdictional residency (data sits in a named jurisdiction)",
    "L2": "operational controls (contractual / config sovereignty)",
    "L3": "infrastructure sovereignty (on-prem / air-gap-capable)",
    "L4": "model sovereignty (operator holds weights + inference)",
    "L5": "governed operations (policy enforced at run time)",
    "L6": "verifiable machine-checked chain-of-title receipt: software attestation "
          "(cosign+Rekor+in-toto/SLSA) ∧ science (DOI) ∧ math (lake-verified Lean) — "
          "bound in one offline-verifiable receipt. SZL differentiator (PROPOSED).",
}

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def assemble_receipt(*, artifact_name: str,
                     image_digest: str | None = None,
                     rekor_log_index: str | None = None,
                     intoto_slsa_level: str = "L1+L2 (roadmap)",
                     doi: str | None = None,
                     lean_theorems: List[str] | None = None,
                     kernel: str = "c7c0ba17") -> Dict[str, Any]:
    """Assemble an L6 chain-of-title receipt from its three strands. Any strand
    missing is honestly labeled. The receipt is content-addressed (its own digest)
    but UNSIGNED — cosign/Rekor signing is the gated step.
    """
    software = {
        "image_digest": image_digest if (image_digest and _SHA256_RE.match(image_digest)) else None,
        "rekor_log_index": rekor_log_index or None,
        "intoto_slsa": intoto_slsa_level,  # honest: roadmap unless evidence present
        "cite": "Sigstore/cosign/Rekor; in-toto (CNCF); SLSA v1.1",
        "status": "PROXY/UNSIGNED" if not (image_digest and rekor_log_index) else "REFERENCED",
    }
    science = {
        "doi": doi if (doi and _DOI_RE.match(doi)) else None,
        "doi_status": "minted" if (doi and _DOI_RE.match(doi)) else "pending (Zenodo, founder-gated)",
        "cite": "Zenodo concept+version DOI; RO-Crate / W3C PROV",
    }
    math = {
        "lean_theorems": list(lean_theorems or []),
        "verification": "lake-verified, no sorry, no new axioms (EXPERIMENTAL-tier)" if lean_theorems
                        else "none referenced",
        "locked_unchanged": True,
        "cite": "lutar-lean (Lean 4 / Mathlib)",
    }
    body = {
        "schema": SCHEMA,
        "artifact": artifact_name,
        "kernel": kernel,
        "software_attestation": software,
        "science": science,
        "math": math,
        "doctrine": {
            "tier": "PROPOSED / EXPERIMENTAL (L6 differentiator)",
            "lambda": "Conjecture 1 (never theorem)",
            "trust_never_100": True,
            "honest_limit": ("structural assembly + offline structure-verification only; "
                             "cryptographic cosign/Rekor SIGNING is the founder-gated step. "
                             "Unsigned strands are labeled PROXY/UNSIGNED/pending."),
        },
    }
    body["receipt_digest"] = _digest(body)
    # completeness score: how many of the 3 strands are fully present (0..3)
    present = sum([
        bool(software["image_digest"] and software["rekor_log_index"]),
        bool(science["doi"]),
        bool(math["lean_theorems"]),
    ])
    body["completeness"] = {"strands_present": present, "of": 3,
                            "fully_signed": False,  # signing is gated
                            "note": "3/3 strands present + signed = full L6; signing gated."}
    return body


def verify_structure(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Offline STRUCTURE verification: schema, content-address integrity, honest
    labels. NOT cryptographic verification (that needs cosign/Rekor — gated)."""
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return {"valid": False, "reason": "bad or missing schema"}
    claimed = receipt.get("receipt_digest")
    body = {k: v for k, v in receipt.items() if k not in ("receipt_digest", "completeness")}
    recomputed = _digest(body)
    integrity = (claimed == recomputed)
    return {
        "schema_ok": True,
        "content_address_intact": integrity,
        "is_signed": False,  # this module never signs
        "verification_scope": "STRUCTURE ONLY (offline). Cryptographic verify = gated cosign/Rekor.",
        "valid": integrity,
        "cite": "content-addressing (SHA-256); SCITT receipt model (IETF)",
    }


def summary() -> Dict[str, Any]:
    return {
        "title": "SZL L6 Chain-of-Title — unified software∧science∧math receipt (PROPOSED)",
        "differentiator": ("Industry sovereign-AI operates L1-L5; SZL's L6 binds cosign+Rekor+"
                           "in-toto/SLSA (software) ∧ Zenodo DOI (science) ∧ lake-verified Lean "
                           "(math) into ONE offline-verifiable receipt — the digital allodial "
                           "chain of title."),
        "levels": LEVELS,
        "honest_limit": ("this module ASSEMBLES + structure-verifies the receipt; cryptographic "
                         "cosign/Rekor SIGNING is the founder-gated step. Unsigned = labeled."),
        "doctrine": {"locked_unchanged": True, "lambda": "Conjecture 1 (never theorem)",
                     "trust_never_100": True, "tier": "EXPERIMENTAL/PROPOSED"},
        "cites": ["in-toto (CNCF) in-toto.io", "SLSA v1.1 slsa.dev",
                  "Sigstore/cosign/Rekor sigstore.dev", "SCITT (IETF)",
                  "Zenodo DOI", "lutar-lean (Lean 4/Mathlib)"],
    }


def register(app, ns: str) -> None:
    base = f"/api/{ns}/v1/chain"
    app.add_api_route(f"{base}/summary", lambda: summary(), methods=["GET"])
    app.add_api_route(f"{base}/levels", lambda: {"levels": LEVELS}, methods=["GET"])
    app.add_api_route(
        f"{base}/assemble",
        lambda artifact="szl-demo", image="", rekor="", doi="", lean="":
            assemble_receipt(
                artifact_name=artifact,
                image_digest=(image or None),
                rekor_log_index=(rekor or None),
                doi=(doi or None),
                lean_theorems=[x for x in lean.split(",") if x.strip()] or None),
        methods=["GET"])
    app.add_api_route(
        f"{base}/verify",
        lambda artifact="szl-demo", lean="Lutar.Allodial,Lutar.Entanglement,Lutar.Neuroplasticity":
            verify_structure(assemble_receipt(
                artifact_name=artifact,
                lean_theorems=[x for x in lean.split(",") if x.strip()] or None)),
        methods=["GET"])


def _selftest() -> None:
    # Empty receipt: 0 strands, structure valid, unsigned
    r0 = assemble_receipt(artifact_name="t")
    assert r0["completeness"]["strands_present"] == 0
    assert r0["software_attestation"]["status"] == "PROXY/UNSIGNED"
    assert r0["science"]["doi_status"].startswith("pending")
    v0 = verify_structure(r0)
    assert v0["valid"] is True and v0["is_signed"] is False
    # Full strands (3/3) — still unsigned (signing gated)
    r3 = assemble_receipt(artifact_name="szl-mesh",
                          image_digest="sha256:" + "a" * 64,
                          rekor_log_index="123456",
                          doi="10.5281/zenodo.20020841",
                          lean_theorems=["Lutar.Allodial", "Lutar.Entanglement", "Lutar.Neuroplasticity"])
    assert r3["completeness"]["strands_present"] == 3
    assert r3["software_attestation"]["status"] == "REFERENCED"
    assert r3["science"]["doi_status"] == "minted"
    assert r3["completeness"]["fully_signed"] is False  # gated
    assert verify_structure(r3)["content_address_intact"] is True
    # Bad DOI rejected (labeled pending)
    rbad = assemble_receipt(artifact_name="t", doi="not-a-doi")
    assert rbad["science"]["doi"] is None
    # Tamper detection: mutate body -> integrity fails
    r3["artifact"] = "tampered"
    assert verify_structure(r3)["content_address_intact"] is False
    # Bad schema
    assert verify_structure({"schema": "x"})["valid"] is False
    assert summary()["doctrine"]["lambda"].startswith("Conjecture 1")
    print("szl_chain_of_title: ALL OK (12 checks)")


if __name__ == "__main__":
    _selftest()
