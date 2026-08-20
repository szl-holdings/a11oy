# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
"""
szl_crypto_pipeline.py — ADDITIVE a11oy-NATIVE cited backend for the holographic
frontier surface static/3d/surfaces/cryptopipeline.js (surface id `cryptopipeline`).

WHY THIS EXISTS
    The estate already has zkinfer / attestinfer — but both are INFERENCE-ONLY trust
    branches (a single forward pass). No surface modeled cryptographic verifiability
    across the FULL AI lifecycle. This module models the linkable cryptographic-proof
    chain over the whole pipeline —
        data-sourcing → training → inference → unlearning
    — where each stage emits a CONTENT COMMITMENT + a LINKABLE proof object, and the
    stages compose into ONE end-to-end verifiable transcript (a hash-linked chain with a
    Merkle-style transcript root). This is the governance-native fit for SZL's
    receipt/DSSE spine: the same "commit-then-link-then-verify" discipline the Khipu
    receipts already use, generalized across the lifecycle.

METHOD (hash-commit chain — MODELED / SIMULATED; NOT a real SNARK)
    For each lifecycle stage we build a canonical content dict, take a REAL SHA-256
    commitment over it, and chain it to the previous stage:
        commit[k]   = sha256(canonical(stage_content[k]))
        link[k]     = sha256(link[k-1] || commit[k])     (link[-1] = genesis)
        transcript_root = sha256(commit[0] || commit[1] || ... || commit[n-1])
    The HASH-CHAIN LINKAGE is genuinely, deterministically verifiable — a `verify` pass
    recomputes every link + the root from the stage commits and reports per-link
    `link_ok` and a whole-chain `chain_consistent`. That part is REAL and honest.

    Each stage ALSO carries a `proof` object naming a zk system from the literature
    (zkLLM / commit-and-prove / SafetyNets) with a MODELED proof_size_bytes and a MODELED
    verify_ms drawn deterministically from the seed. THIS IS SIMULATED: no zero-knowledge
    argument is generated or checked. proof.label == "SIMULATED" is returned VERBATIM and
    NEVER upgraded. We NEVER claim a real zk/SNARK proof, and NEVER emit "PROVEN".

    To make the honesty legible we also run a TAMPER demo: flipping one stage's committed
    content is shown to break its link (link_ok=False) and the whole `chain_consistent`,
    proving the chain detects mutation — a property of the hash chain, not of any zk proof.

SPINE CHAIN (guarded, READ-ONLY — doctrine v11: NEVER sign on a GET)
    If szl_dsse / szl_durable_ledger are importable we surface, advisory-only, whether a
    DSSE signing key + a durable ledger are available in this environment (so the surface
    can show "would be co-signed / anchored in-Space"). We do NOT sign, and we do NOT
    write a ledger record, on this read path. Locally the transcript receipt is honestly
    UNSIGNED-LOCAL.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Waiwitya, Cheng, Kang et al. (2025) "A Framework for Cryptographic Verifiability of
      End-to-End AI Pipelines", arXiv:2503.22573.  https://arxiv.org/abs/2503.22573
    * Sun, Li, Zhang (2024) "zkLLM: Zero Knowledge Proofs for Large Language Models",
      arXiv:2404.16109 (ACM CCS'24).  https://arxiv.org/abs/2404.16109
    * "Artemis: Efficient Commit-and-Prove SNARKs for zkML", arXiv:2409.12055.
      https://arxiv.org/abs/2409.12055
    * Ghodsi, Gu, Garg (2017) "SafetyNets: Verifiable Execution of Deep Neural Networks
      on an Untrusted Cloud", arXiv:1706.10268 (NeurIPS'17).
      https://arxiv.org/abs/1706.10268

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by cryptopipeline.js, NEVER
      upgraded. The COMMITMENT/LINK/ROOT hashing is real; the per-stage zk PROOF objects
      are SIMULATED (no SNARK). No "PROVEN"/"VERIFIED"/"1.0" anywhere; trust ceiling 0.97.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; nothing to locked-8.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/cryptopipeline/transcript?seed=&tamper_stage=
        -> renderable 200 JSON compatible with cryptopipeline.js:
           {label:"MODELED", surface, title, stages[], transcript_root,
            chain_consistent, tamper{...}, spine{...}, receipt{...},
            citations[], doctrine, honesty}
"""
import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1",
            "locked_proven": 8, "trust_ceiling": 0.97}

CITATIONS = [
    {"id": "e2e_verifiability_2025",
     "cite": ("A Framework for Cryptographic Verifiability of End-to-End AI Pipelines "
              "(2025) — data→train→infer verifiability across the lifecycle."),
     "url": "https://arxiv.org/abs/2503.22573"},
    {"id": "zkllm_2024",
     "cite": "Sun, Li, Zhang (2024) zkLLM: Zero Knowledge Proofs for Large Language Models (CCS'24).",
     "url": "https://arxiv.org/abs/2404.16109"},
    {"id": "artemis_2024",
     "cite": "Artemis: Efficient Commit-and-Prove SNARKs for zkML (2024).",
     "url": "https://arxiv.org/abs/2409.12055"},
    {"id": "safetynets_2017",
     "cite": ("Ghodsi, Gu, Garg (2017) SafetyNets: Verifiable Execution of Deep Neural "
              "Networks on an Untrusted Cloud (NeurIPS'17)."),
     "url": "https://arxiv.org/abs/1706.10268"},
]

# The four AI-lifecycle stages, each mapped to a proof-system LINEAGE from the cited
# literature. proof_system is a NAME ONLY — the object is SIMULATED, never generated.
_STAGES = [
    {"stage": "data_sourcing",
     "title": "Data Sourcing",
     "proof_system": "commit-and-prove (Merkle dataset commitment)",
     "cite": "artemis_2024",
     "claim": "committed dataset root; provenance of every training shard"},
    {"stage": "training",
     "title": "Training",
     "proof_system": "SafetyNets-style verifiable computation",
     "cite": "safetynets_2017",
     "claim": "weights commitment bound to the committed dataset + training transcript"},
    {"stage": "inference",
     "title": "Inference",
     "proof_system": "zkLLM proof-of-inference",
     "cite": "zkllm_2024",
     "claim": "output produced by the committed weights on the committed input"},
    {"stage": "unlearning",
     "title": "Unlearning",
     "proof_system": "commit-and-prove recomputation",
     "cite": "artemis_2024",
     "claim": "target record's influence removed; new weights commitment recomputed"},
]

_GENESIS = "0" * 64


def _rng(seed: int):
    """Deterministic stdlib LCG (no numpy) — same convention as szl_kv_cache."""
    state = (int(seed) * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _stage_content(spec: Dict[str, str], seed: int, idx: int) -> Dict[str, Any]:
    """Canonical committed content for a stage. Deterministic in (seed, idx)."""
    rnd = _rng(seed * 131 + idx)
    # a MODELED per-stage artifact digest (stands in for the real object hashed in-Space)
    artifact = _sha(f"{spec['stage']}:{seed}:{idx}:{rnd():.12f}".encode("utf-8"))
    return {
        "stage": spec["stage"],
        "claim": spec["claim"],
        "artifact_digest": artifact,
        "proof_system": spec["proof_system"],
    }


def _proof_object(spec: Dict[str, str], seed: int, idx: int) -> Dict[str, Any]:
    """A SIMULATED zk-proof object. proof_size / verify_ms are MODELED figures drawn
    deterministically from the literature's rough regime — NOT a generated argument."""
    rnd = _rng(seed * 977 + idx)
    # succinct-argument regime: kilobyte-scale proofs, millisecond-scale verify (MODELED).
    proof_size_bytes = int(1024 * (1.5 + 6.0 * rnd()))          # ~1.5–7.5 kB
    verify_ms = round(2.0 + 40.0 * rnd(), 3)                    # ~2–42 ms (MODELED)
    return {
        "label": "SIMULATED",
        "proof_system": spec["proof_system"],
        "proof_size_bytes": proof_size_bytes,
        "modeled_verify_ms": verify_ms,
        "note": ("SIMULATED proof object — no zero-knowledge argument is generated or "
                 "checked; size/verify are MODELED regime figures, not a benchmark."),
    }


def _build_chain(seed: int, tamper_stage: Optional[str]) -> Dict[str, Any]:
    """Build the four-stage lifecycle transcript: per-stage commit + linkable proof,
    hash-linked into one chain with a Merkle-style transcript root. The linkage is REAL
    (recomputable); the per-stage zk proofs are SIMULATED."""
    stages: List[Dict[str, Any]] = []
    prev_link = _GENESIS
    commits: List[str] = []
    for idx, spec in enumerate(_STAGES):
        tampered = (tamper_stage == spec["stage"])
        content = _stage_content(spec, seed, idx)
        # commit + link are computed over the HONEST content (as they would have been
        # emitted at stage time). Tampering then mutates the content AFTER the commit is
        # fixed, so the recorded commit no longer matches — the chain detects it on verify.
        commit = _sha(_canon(content))
        link = _sha((prev_link + commit).encode("utf-8"))
        if tampered:
            content = dict(content)
            content["artifact_digest"] = _sha((commit + ":TAMPERED").encode("utf-8"))
        commits.append(commit)
        stages.append({
            "index": idx,
            "stage": spec["stage"],
            "title": spec["title"],
            "claim": spec["claim"],
            "cite": spec["cite"],
            "content": content,
            "commit": commit,
            "prev_link": prev_link,
            "link": link,
            "tampered": tampered,
            "proof": _proof_object(spec, seed, idx),
        })
        prev_link = link
    transcript_root = _sha("".join(commits).encode("utf-8"))
    return {"stages": stages, "transcript_root": transcript_root}


def _verify_chain(stages: List[Dict[str, Any]], transcript_root: str) -> Dict[str, Any]:
    """Re-check the hash-linked chain from the stage commits (REAL, deterministic).
    Returns per-link recomputation results + whole-chain consistency. This verifies the
    COMMITMENT LINKAGE only — NOT a zk proof (those are SIMULATED)."""
    prev_link = _GENESIS
    per_link = []
    all_ok = True
    commits = []
    for st in stages:
        commit = st["commit"]
        commits.append(commit)
        expect_link = _sha((prev_link + commit).encode("utf-8"))
        link_ok = (expect_link == st["link"]) and (st["prev_link"] == prev_link)
        # if the committed content was tampered, the recomputed commit won't match
        content_ok = (_sha(_canon(st["content"])) == commit)
        ok = bool(link_ok and content_ok)
        all_ok = all_ok and ok
        per_link.append({"stage": st["stage"], "link_ok": ok,
                         "content_ok": content_ok})
        prev_link = st["link"]
    root_ok = (_sha("".join(commits).encode("utf-8")) == transcript_root)
    return {"per_link": per_link, "root_ok": bool(root_ok),
            "chain_consistent": bool(all_ok and root_ok)}


def _spine(transcript_root: str) -> Dict[str, Any]:
    """GUARDED, READ-ONLY chain to the DSSE / durable-ledger spine. Reports whether a
    signing key + durable ledger are available (advisory) — does NOT sign or write on
    this GET (doctrine v11: receipt-on-write, never on-read)."""
    out: Dict[str, Any] = {"dsse": "UNAVAILABLE", "ledger": "UNAVAILABLE",
                           "signed_on_read": False,
                           "note": ("advisory read-only: DSSE co-signing + ledger "
                                    "anchoring happen on WRITE in-Space, never on this GET.")}
    try:
        import szl_dsse as _dsse  # type: ignore
        avail = bool(_dsse.signing_available())
        out["dsse"] = "SIGNING-KEY-PRESENT" if avail else "UNSIGNED-LOCAL"
        try:
            out["dsse_pubkey_fpr"] = _dsse.public_key_fingerprint()[:16]
        except Exception:
            pass
    except Exception:
        out["dsse"] = "UNAVAILABLE"
    try:
        import szl_durable_ledger as _dl  # type: ignore
        # class presence is enough for an advisory availability read; do NOT append.
        out["ledger"] = "AVAILABLE" if hasattr(_dl, "DurableStore") else "UNAVAILABLE"
    except Exception:
        out["ledger"] = "UNAVAILABLE"
    return out


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = _canon(payload)
    return {
        "digest_sha256": _sha(blob),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED transcript; deterministic in the seed. "
                 "No DSSE signature claimed locally (UNSIGNED-LOCAL); real co-signing "
                 "happens on WRITE in-Space, not on this read path."),
    }


def build_transcript(seed: int = 42, tamper_stage: Optional[str] = None) -> Dict[str, Any]:
    """Public core: build + verify the end-to-end lifecycle transcript."""
    seed = int(seed) & 0xFFFFFFFF
    valid_stages = {s["stage"] for s in _STAGES}
    ts = tamper_stage if tamper_stage in valid_stages else None

    chain = _build_chain(seed, ts)
    verify = _verify_chain(chain["stages"], chain["transcript_root"])

    # tamper demo: an INDEPENDENT chain with one stage mutated, showing the link breaks.
    demo_target = ts or "training"
    tam_chain = _build_chain(seed, demo_target)
    tam_verify = _verify_chain(tam_chain["stages"], tam_chain["transcript_root"])
    tamper = {
        "tampered_stage": demo_target,
        "chain_consistent_after_tamper": tam_verify["chain_consistent"],
        "note": ("flipping one committed artifact breaks that stage's link and the "
                 "whole-chain consistency — the hash chain detects mutation. This is a "
                 "property of the COMMITMENT chain, not of any zk proof (SIMULATED)."),
    }

    digest_src = {"transcript_root": chain["transcript_root"],
                  "stage_commits": [s["commit"] for s in chain["stages"]],
                  "chain_consistent": verify["chain_consistent"]}

    return {
        "label": "MODELED",
        "surface": "cryptopipeline",
        "title": "Crypto-Pipeline · End-to-End AI Lifecycle Verifiable Transcript (MODELED)",
        "method": ("real SHA-256 commitment + hash-chain linkage across the AI lifecycle "
                   "(data→train→infer→unlearn); per-stage zk PROOF objects are SIMULATED "
                   "(no SNARK generated/checked). Deterministic in the seed."),
        "lifecycle": [s["stage"] for s in _STAGES],
        "stages": chain["stages"],
        "transcript_root": chain["transcript_root"],
        "verify": verify,
        "chain_consistent": verify["chain_consistent"],
        "tamper": tamper,
        "spine": _spine(chain["transcript_root"]),
        "receipt": _receipt(digest_src, seed),
        "citations": CITATIONS,
        "doctrine": DOCTRINE,
        "honesty": ("MODELED: the commit/link/root hashing is REAL and recomputable; the "
                    "per-stage zk proofs are SIMULATED (hash-commit chain, NOT a real "
                    "SNARK/zk proof). No real zk argument is asserted; no VERIFIED/1.0 "
                    "state. Λ=Conjecture 1; adds nothing to the locked-8; trust ceiling "
                    "0.97, never 100%."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/cryptopipeline/transcript", include_in_schema=False)
    async def _transcript(seed: int = 42, tamper_stage: str = "") -> JSONResponse:
        t0 = time.time()
        try:
            body = build_transcript(int(seed), tamper_stage or None)
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"transcript build failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        body["elapsed_ms"] = round((time.time() - t0) * 1000, 2)
        return JSONResponse(body, status_code=200)

    return (f"crypto-pipeline transcript mounted: "
            f"GET /api/{ns}/v1/cryptopipeline/transcript (label MODELED)")


def _selftest() -> None:
    tx = build_transcript(42, None)
    # structure
    assert tx["label"] == "MODELED", "label must be MODELED"
    assert len(tx["stages"]) == 4, "four lifecycle stages"
    assert tx["lifecycle"] == ["data_sourcing", "training", "inference", "unlearning"]
    # the honest hash chain must verify for an untampered transcript
    assert tx["chain_consistent"] is True, "untampered chain must be consistent"
    assert tx["verify"]["root_ok"] is True, "transcript root must recompute"
    assert all(l["link_ok"] for l in tx["verify"]["per_link"]), "all links must recompute"
    # per-stage zk proofs must be SIMULATED, never upgraded
    for st in tx["stages"]:
        assert st["proof"]["label"] == "SIMULATED", "proof objects must be SIMULATED"
        assert st["proof"]["proof_size_bytes"] > 0
    # tamper demo: mutating a stage MUST break the chain (honesty proof)
    tam = build_transcript(42, "training")
    assert tam["chain_consistent"] is False, "tampered chain must be inconsistent"
    assert tam["tamper"]["chain_consistent_after_tamper"] is False
    # determinism
    assert build_transcript(42, None)["transcript_root"] == tx["transcript_root"], \
        "non-deterministic for fixed seed"
    # different seed -> different root
    assert build_transcript(7, None)["transcript_root"] != tx["transcript_root"], \
        "seed must vary the transcript"
    # honesty: no fabricated signature, no PROVEN token
    assert tx["receipt"]["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    assert tx["spine"]["signed_on_read"] is False, "must never sign on a read path"
    import re as _re
    blob = json.dumps(tx).upper()
    assert not _re.search(r"\bPROVEN\b", blob), "must never claim PROVEN"
    assert "SNARK PROOF GENERATED" not in blob and "ZK PROOF VERIFIED" not in blob, \
        "must never claim a real proof was generated/verified"
    print("szl_crypto_pipeline: ALL OK (real hash-chain links verify, tamper breaks chain, "
          "zk proofs SIMULATED, deterministic, UNSIGNED-LOCAL receipt, no sign-on-read)")


if __name__ == "__main__":
    _selftest()
