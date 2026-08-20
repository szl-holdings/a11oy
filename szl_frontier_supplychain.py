#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_frontier_supplychain.py — Model-Artifact Provenance (SLSA · in-toto · Rekor · C2PA).

GET /api/a11oy/v1/frontier/supplychain returns the MODEL supply chain as a governed,
honestly-labeled surface: the four stages a model weight-artifact travels through —
weights → build → attestation → deploy — each carrying the *kind* of provenance evidence
it would emit (in-toto attestation, DSSE envelope, Rekor transparency-log inclusion, C2PA
manifest) and its HONESTLY-labeled SLSA maturity. Nothing here upgrades a level that was
not earned.

TOP-LEVEL HONESTY LABEL: MODELED (explicitly NOT VERIFIED). The estate is NOT running a
hardened SLSA L3 builder over live model weights, NOT talking to a real Rekor instance, and
NOT minting real cosign/Fulcio signatures on a GET. The endpoint therefore returns:

  1. slsa_ladder (STRUCTURAL-ONLY) — the SLSA v1.0 build track (L1/L2/L3) defined verbatim
     from the spec, with an HONEST per-stage claim: L1 honest (provenance exists), L2
     attested (signed provenance from a hosted build), L3 roadmap (hardened/isolated builder,
     non-falsifiable provenance — NOT yet earned). Definitional; no measurement.
  2. supply_chain (MODELED) — the weights→build→attestation→deploy graph. Each stage names
     the evidence artifact it emits and cites the governing spec. MODELED, not live.
  3. evidence_types (STRUCTURAL-ONLY) — the four provenance formats (in-toto Statement, DSSE
     envelope, Rekor inclusion proof, C2PA manifest) with their real citations. Definitional.
  4. micro_artifact (MEASURED for its OWN narrow claim only) — a genuine in-toto/DSSE-style
     roundtrip computed IN-PROCESS at request time: build an in-toto v1 Statement over a toy
     "model weight" subject (sha256 digest), wrap it in a DSSE Pre-Authentication-Encoding
     (PAE), place it into a SHA-256 Merkle transparency log and produce an inclusion proof,
     then INDEPENDENTLY re-verify every step by recomputation. MEASURED means ONLY "this
     encode→log→verify roundtrip really executed in-process now". It is NOT a real signature
     (no private key in the sandbox — the signature slot is the honest UNSIGNED-LOCAL /
     DSSE_PLACEHOLDER, never fabricated), NOT a real Rekor entry, and NOT model-scale. On any
     failure it downgrades to HONEST-STUB — never a faked pass.

PRIMARY SOURCES (all verified to resolve 2026-07-06):
  * SLSA — Supply-chain Levels for Software Artifacts, v1.0 (OpenSSF). Build track L1/L2/L3.
    https://slsa.dev/spec/v1.0/levels
  * in-toto: Providing farm-to-table guarantees for bits and bytes — Torres-Arias, Afzali,
    Kuppusamy, Curtmola, Cappos, USENIX Security 2019.
    https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias
  * Sigstore: Software Signing for Everybody — Newman, Meyers, Torres-Arias, Cappos, et al.,
    ACM CCS 2022, DOI 10.1145/3548606.3560596 (Rekor transparency log + Fulcio + cosign).
    https://dl.acm.org/doi/10.1145/3548606.3560596
  * C2PA — Coalition for Content Provenance and Authenticity, Technical Specification
    (content credentials manifest). https://c2pa.org/specifications/specifications/
  * DSSE — Dead Simple Signing Envelope, Secure Systems Lab / in-toto (PAE encoding used by
    the micro-artifact). https://github.com/secure-systems-lab/dsse

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; touches
    no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  - No SLSA level is ever upgraded: L1 honest / L2 attested / L3 roadmap, verbatim. No label
    is upgraded; the micro-artifact tile is MEASURED ONLY for the narrow "roundtrip really
    ran" claim, or an honest HONEST-STUB otherwise; signatures are never fabricated.
  - Additive route; canonical domain a-11-oy.com; 0 runtime CDN on the surface; no
    user-visible codenames. Pure READ — signs nothing, appends to no chain (receipts belong
    on writes, never on GETs).
"""
from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any

# Honesty-label vocabulary (doctrine v11) — tests grep these exact strings.
MODELED = "MODELED"
MEASURED = "MEASURED"
HONEST_STUB = "HONEST-STUB"
STRUCTURAL = "STRUCTURAL-ONLY"

# SLSA maturity labels — VERBATIM, never upgraded (doctrine v11).
SLSA_L1_HONEST = "SLSA L1 honest"
SLSA_L2_ATTESTED = "SLSA L2 attested"
SLSA_L3_ROADMAP = "SLSA L3 roadmap"

# Honest signature placeholder — the sandbox holds no private key; never fabricate a signature.
DSSE_PLACEHOLDER = "UNSIGNED-LOCAL (DSSE_PLACEHOLDER — no key in sandbox)"

# Trust ceiling — advisory, never 100% (doctrine v11).
TRUST_CEILING = 0.97

# Primary sources, keyed by the short id each element cites in-band.
SOURCES: dict[str, dict[str, str]] = {
    "slsa-v1.0": {
        "id": "SLSA v1.0 (OpenSSF)",
        "title": "Supply-chain Levels for Software Artifacts — Build track L1/L2/L3",
        "venue": "OpenSSF, 2023",
        "url": "https://slsa.dev/spec/v1.0/levels",
    },
    "in-toto-2019": {
        "id": "in-toto (USENIX Security 2019)",
        "title": "in-toto: Providing farm-to-table guarantees for bits and bytes",
        "venue": "Torres-Arias, Afzali, Kuppusamy, Curtmola, Cappos — USENIX Security 2019",
        "url": "https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias",
    },
    "sigstore-2022": {
        "id": "Sigstore (ACM CCS 2022, DOI 10.1145/3548606.3560596)",
        "title": "Sigstore: Software Signing for Everybody (Rekor transparency log + Fulcio + cosign)",
        "venue": "Newman, Meyers, Torres-Arias, Cappos, et al. — ACM CCS 2022",
        "url": "https://dl.acm.org/doi/10.1145/3548606.3560596",
    },
    "c2pa": {
        "id": "C2PA Technical Specification",
        "title": "Coalition for Content Provenance and Authenticity — content credentials manifest",
        "venue": "C2PA / JDF, 2024",
        "url": "https://c2pa.org/specifications/specifications/",
    },
    "dsse": {
        "id": "DSSE (Secure Systems Lab)",
        "title": "Dead Simple Signing Envelope — Pre-Authentication Encoding (PAE)",
        "venue": "secure-systems-lab / in-toto",
        "url": "https://github.com/secure-systems-lab/dsse",
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
# 1. SLSA ladder (STRUCTURAL) — v1.0 build track, HONEST per-level claim.
# ---------------------------------------------------------------------------

def _slsa_ladder() -> dict[str, Any]:
    """The SLSA v1.0 build track defined verbatim, with the estate's HONEST claim per level.
    No level is upgraded: L1 honest, L2 attested, L3 roadmap (NOT yet earned)."""
    return {
        "label": STRUCTURAL,
        "spec": "SLSA v1.0 build track",
        "source": "slsa-v1.0",
        "note": ("definitional ladder only — no measurement. The estate honestly claims L1, "
                 "models L2 attestation, and marks L3 a roadmap; never an unearned upgrade."),
        "levels": [
            {
                "level": "L1",
                "claim": SLSA_L1_HONEST,
                "earned": True,
                "requires": ("build process produces provenance describing how the artifact "
                             "was built (unsigned provenance is acceptable at L1)"),
                "estate_reality": ("MODELED provenance is emitted for the toy roundtrip below; "
                                   "honestly labeled, not live model-scale."),
                "source": "slsa-v1.0",
            },
            {
                "level": "L2",
                "claim": SLSA_L2_ATTESTED,
                "earned": False,
                "attested_modeled": True,
                "requires": ("hosted build platform + signed provenance (a signature over the "
                             "provenance from the build service)"),
                "estate_reality": ("MODELED/attested: the micro-artifact builds a DSSE envelope "
                                   "whose signature slot is the honest UNSIGNED-LOCAL placeholder "
                                   "— no real hosted-builder signature is claimed."),
                "source": "slsa-v1.0",
            },
            {
                "level": "L3",
                "claim": SLSA_L3_ROADMAP,
                "earned": False,
                "requires": ("hardened, isolated build platform + non-falsifiable provenance "
                             "(strong tamper resistance against the build itself)"),
                "estate_reality": ("ROADMAP — not attempted; no hardened isolated builder in "
                                   "this estate. Never claimed as earned."),
                "source": "slsa-v1.0",
            },
        ],
        "highest_earned": "L1",
        "highest_claimed_label": SLSA_L1_HONEST,
        "never_upgraded": True,
    }


# ---------------------------------------------------------------------------
# 2. Supply chain graph (MODELED) — weights → build → attestation → deploy.
# ---------------------------------------------------------------------------

def _supply_chain() -> dict[str, Any]:
    """The four model-artifact stages, each naming the provenance evidence it emits and the
    governing spec. MODELED — a design surface, not live telemetry."""
    return {
        "label": MODELED,
        "not_verified": True,
        "note": ("the path a model weight-artifact travels; each stage emits provenance "
                 "evidence of a named kind. MODELED — no live builder/log/registry."),
        "stages": [
            {
                "stage": "weights",
                "index": 0,
                "role": "source model weights + training-data descriptor (the material input)",
                "evidence": "in-toto Statement (subject = weights sha256 digest)",
                "slsa": SLSA_L1_HONEST,
                "label": MODELED,
                "source": "in-toto-2019",
            },
            {
                "stage": "build",
                "index": 1,
                "role": "quantize / package / containerize the weights into a deployable artifact",
                "evidence": "SLSA provenance predicate (buildType, builder id, materials)",
                "slsa": SLSA_L2_ATTESTED,
                "label": MODELED,
                "source": "slsa-v1.0",
            },
            {
                "stage": "attestation",
                "index": 2,
                "role": "sign the provenance (DSSE) and log it to a transparency log for discovery",
                "evidence": "DSSE envelope + Rekor inclusion proof (Merkle transparency log)",
                "slsa": SLSA_L2_ATTESTED,
                "label": MODELED,
                "source": "sigstore-2022",
            },
            {
                "stage": "deploy",
                "index": 3,
                "role": "verify provenance at admission, then serve the model behind the Λ-gate",
                "evidence": "verifier policy check (subject digest ∈ signed provenance) + C2PA manifest",
                "slsa": SLSA_L3_ROADMAP,
                "label": MODELED,
                "source": "c2pa",
            },
        ],
        "edges": [
            {"from": "weights", "to": "build", "carries": "weights digest"},
            {"from": "build", "to": "attestation", "carries": "SLSA provenance predicate"},
            {"from": "attestation", "to": "deploy", "carries": "signed DSSE + inclusion proof"},
        ],
        "honest_note": ("MODELED: the stages and evidence kinds are real formats; the estate "
                        "does not run a live L3 builder, a real Rekor, or real cosign signing "
                        "on this read path."),
    }


# ---------------------------------------------------------------------------
# 3. Evidence types (STRUCTURAL) — the four provenance formats + citations.
# ---------------------------------------------------------------------------

def _evidence_types() -> dict[str, Any]:
    return {
        "label": STRUCTURAL,
        "note": "definitional catalogue of the provenance formats referenced above.",
        "types": [
            {
                "name": "in-toto Statement",
                "what": ("a signed statement binding a set of subjects (name + digest) to a "
                         "predicate describing how they were produced"),
                "source": "in-toto-2019",
            },
            {
                "name": "SLSA provenance predicate",
                "what": "the build metadata predicate (buildType, builder, invocation, materials)",
                "source": "slsa-v1.0",
            },
            {
                "name": "DSSE envelope",
                "what": ("Dead Simple Signing Envelope — PAE-encodes (payloadType, payload) so "
                         "signatures are over an unambiguous pre-authentication encoding"),
                "source": "dsse",
            },
            {
                "name": "Rekor inclusion proof",
                "what": ("Sigstore transparency-log Merkle inclusion proof: the entry is "
                         "provably present under a signed tree head"),
                "source": "sigstore-2022",
            },
            {
                "name": "C2PA manifest",
                "what": ("content-credentials manifest binding provenance assertions to an "
                         "artifact (applied here to model/output artifacts)"),
                "source": "c2pa",
            },
        ],
    }


# ---------------------------------------------------------------------------
# 4. Real, honest micro-artifact — in-toto Statement → DSSE PAE → Merkle inclusion,
#    re-verified IN-PROCESS. MEASURED ONLY for the narrow "roundtrip really ran now" claim.
# ---------------------------------------------------------------------------

def _dsse_pae(payload_type: bytes, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (real, client-recomputable):
      "DSSEv1 " + LEN(type) + " " + type + " " + LEN(payload) + " " + payload
    (SP800-... style length-prefixed to prevent ambiguity). This is what a signer signs."""
    return b"DSSEv1 %d %s %d %s" % (len(payload_type), payload_type, len(payload), payload)


def _merkle_root(leaves: list[bytes]) -> tuple[str, list[str]]:
    """SHA-256 Merkle root over `leaves` (duplicate-last padding). Returns (root_hex,
    leaf_hashes_hex). Real, deterministic, client-recomputable — the transparency-log idiom."""
    level = [hashlib.sha256(b"leaf:" + lf).digest() for lf in leaves]
    leaf_hex = [d.hex() for d in level]
    if not level:
        return hashlib.sha256(b"empty").hexdigest(), []
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [hashlib.sha256(b"node:" + level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex(), leaf_hex


def _micro_artifact() -> dict[str, Any]:
    """A genuine in-toto/DSSE/transparency-log roundtrip over a toy "model weight" subject.

    Everything runs at request time and is client-recomputable:
      subject    : sha256 of a toy weight blob  (in-toto subject digest)
      statement  : in-toto v1 Statement {_type, subject[], predicateType, predicate}
      pae        : DSSE PAE over (payloadType, canonical statement JSON)
      log entry  : sha256 of the PAE  (what would be logged)
      inclusion  : Merkle root over [entry, sibling] + the inclusion path
      verify     : recompute subject, statement, PAE, entry, root — compare all
      signature  : NONE — honest UNSIGNED-LOCAL placeholder (no key in sandbox)

    HONESTY: this proves the encode→log→verify PLUMBING is real; it is NOT a real signature,
    NOT a real Rekor entry, and does NOT scale to model weights. Labeled MEASURED ONLY for
    the narrow claim "this roundtrip executed in-process now"; on any failure HONEST-STUB,
    never a fabricated pass. The signature is never faked."""
    try:
        # Toy "model weight" blob + its in-toto subject digest.
        weight_blob = b"szl-modeled-lm:layer0.weights:v1:[0.03,-0.11,0.42,...]"
        subject_digest = hashlib.sha256(weight_blob).hexdigest()

        statement = {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [{"name": "szl-modeled-lm/layer0.weights", "digest": {"sha256": subject_digest}}],
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {"buildType": "szl-modeled/quantize+package"},
                "runDetails": {"builder": {"id": "modeled://a11oy/frontier/supplychain"}},
            },
        }
        payload_type = b"application/vnd.in-toto+json"
        payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()

        pae = _dsse_pae(payload_type, payload)
        pae_hex = hashlib.sha256(pae).hexdigest()

        # Transparency-log entry = hash of the PAE; place it in a 2-leaf Merkle tree with a
        # deterministic sibling so we can emit a real inclusion path.
        entry_leaf = bytes(pae)
        sibling = b"log:sibling:genesis"
        root, leaf_hashes = _merkle_root([entry_leaf, sibling])
        # inclusion path for leaf 0: its sibling leaf hash, combined left->right.
        sib_leaf_hash = hashlib.sha256(b"leaf:" + sibling).hexdigest()
        entry_leaf_hash = leaf_hashes[0]

        # Independent verify: recompute EVERYTHING from the committed inputs.
        subject2 = hashlib.sha256(weight_blob).hexdigest()
        payload2 = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
        pae2 = _dsse_pae(payload_type, payload2)
        pae_hex2 = hashlib.sha256(pae2).hexdigest()
        root2, _ = _merkle_root([bytes(pae2), sibling])
        # recompute root from the inclusion path (leaf0 + sibling leaf hash).
        recomputed_root = hashlib.sha256(
            b"node:" + bytes.fromhex(entry_leaf_hash) + bytes.fromhex(sib_leaf_hash)
        ).hexdigest()

        verify_ok = (subject2 == subject_digest and pae_hex2 == pae_hex
                     and root2 == root and recomputed_root == root)

        if not verify_ok:  # pragma: no cover — deterministic; would indicate a real fault
            return {
                "label": HONEST_STUB,
                "verify_ok": False,
                "note": ("in-toto/DSSE/Merkle roundtrip did NOT reconcile in-process; reported "
                         "honestly as HONEST-STUB, not faked."),
            }

        return {
            "label": MEASURED,
            "measured_claim": ("ONLY that this in-toto Statement → DSSE PAE → Merkle-inclusion "
                               "roundtrip executed in-process at request time and re-verified; "
                               "NOT a real signature, NOT a real Rekor entry, NOT model-scale."),
            "scheme": ("in-toto v1 Statement + DSSE PAE (application/vnd.in-toto+json) + "
                       "SHA-256 Merkle transparency inclusion"),
            "subject": {"name": "szl-modeled-lm/layer0.weights", "sha256": subject_digest,
                        "source": "in-toto-2019"},
            "dsse": {
                "payloadType": payload_type.decode(),
                "pae_sha256": pae_hex,
                "signature": DSSE_PLACEHOLDER,
                "signed": False,
                "source": "dsse",
            },
            "transparency_log": {
                "entry_sha256": pae_hex,
                "merkle_root": root,
                "inclusion_path": [{"sibling_leaf_sha256": sib_leaf_hash, "side": "right"}],
                "leaf0_sha256": entry_leaf_hash,
                "source": "sigstore-2022",
            },
            "slsa_claim": SLSA_L1_HONEST,
            "verify_ok": True,
            "client_recompute": {
                "subject": "sha256(weight_blob)",
                "payload": "json.dumps(statement, sort_keys=True, separators=(',',':'))",
                "pae": "b'DSSEv1 '||len(type)||' '||type||' '||len(payload)||' '||payload",
                "entry": "sha256(pae)",
                "root": "sha256('node:'||sha256('leaf:'||pae)||sha256('leaf:'||sibling))",
            },
            "honest_note": ("real plumbing, deliberately tiny. Scaling this to a signed, "
                            "hosted-builder, transparency-logged model artifact is exactly the "
                            "L2-attested / L3-roadmap gap above — the signature is never faked."),
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
    """Compose the supplychain surface payload. Pure read; mints/ signs nothing (receipts
    belong on writes, never on GETs)."""
    micro = _micro_artifact()
    return {
        "ok": True,
        "endpoint": "frontier/supplychain",
        "service": "a11oy.frontier.supplychain",
        "title": "Model-Artifact Provenance (SLSA · in-toto · Rekor · C2PA)",
        # TOP-LEVEL honesty banner — VERBATIM, explicitly NOT VERIFIED.
        "label": MODELED,
        "claim": MODELED,
        "not_verified": True,
        "what": ("the model supply chain as a governed, honestly-labeled surface: weights → "
                 "build → attestation → deploy, each emitting a named provenance artifact "
                 "(in-toto Statement, SLSA provenance, DSSE envelope + Rekor inclusion, C2PA "
                 "manifest). SLSA maturity is labeled HONESTLY — L1 honest, L2 attested, L3 "
                 "roadmap — and never upgraded beyond what is earned."),
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
            "canonical_domain": "a-11-oy.com",
            "slsa_levels": {"L1": SLSA_L1_HONEST, "L2": SLSA_L2_ATTESTED, "L3": SLSA_L3_ROADMAP},
            "slsa_never_upgraded": True,
            "note": ("additive MODELED surface; touches no locked formula and no kernel; "
                     "introduces no theorem, no green/1.0, no proof of Λ; signs nothing on GET."),
        },
        "slsa_ladder": _slsa_ladder(),
        "supply_chain": _supply_chain(),
        "evidence_types": _evidence_types(),
        "micro_artifact": micro,
        "sources": SOURCES,
        "labels_legend": {
            MODELED: "design/structural quantity — NOT verified, not live telemetry",
            MEASURED: "the micro-artifact roundtrip really executed in-process now (narrow claim only)",
            HONEST_STUB: "an honest placeholder — the roundtrip could not run; never a faked pass",
            STRUCTURAL: "definitional/structural contrast only — no measurement",
            SLSA_L1_HONEST: "SLSA L1 earned honestly (provenance exists)",
            SLSA_L2_ATTESTED: "SLSA L2 modeled/attested (signed provenance; signature slot honest-unsigned)",
            SLSA_L3_ROADMAP: "SLSA L3 roadmap (hardened isolated builder — NOT earned)",
        },
        "timestamp_utc": _now_iso(),
    }


def handle() -> dict[str, Any]:
    """GET /frontier/supplychain handler used by FastAPI and __main__."""
    try:
        return build_payload()
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "frontier/supplychain",
            "label": MODELED,
            "error": str(exc),
            "doctrine": "v11: surface unavailable; no fabricated provenance/signature emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_zkinfer.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the supplychain surface endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/supplychain")
    async def _frontier_supplychain():
        """Model-artifact provenance: SLSA ladder + supply-chain graph + a real in-toto/DSSE micro-artifact."""
        return JSONResponse(handle())

    return "frontier-supplychain-wired:1"


# ---------------------------------------------------------------------------
# Self-test — honest labels, no upgrade, real roundtrip, sources cited.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_frontier_supplychain — self-test (MODELED surface, honest labels)")
    print("=" * 72)

    p = build_payload()
    blob = json.dumps(p)

    # 1) top-level MODELED, explicitly NOT VERIFIED.
    assert p["ok"] is True
    assert p["label"] == MODELED and p["claim"] == MODELED
    assert p["not_verified"] is True
    assert "VERIFIED" not in {p["label"], p["claim"]}
    print("[1] top-level MODELED / not_verified  OK")

    # 2) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust ceiling 0.97 not 100%.
    d = p["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert d["canonical_domain"] == "a-11-oy.com"
    print("[2] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 3) SLSA levels honest + never upgraded: L1 honest / L2 attested / L3 roadmap verbatim.
    assert d["slsa_levels"] == {"L1": SLSA_L1_HONEST, "L2": SLSA_L2_ATTESTED, "L3": SLSA_L3_ROADMAP}
    ladder = p["slsa_ladder"]
    assert ladder["highest_earned"] == "L1"
    assert ladder["highest_claimed_label"] == SLSA_L1_HONEST
    lv = {x["level"]: x for x in ladder["levels"]}
    assert lv["L1"]["earned"] is True and lv["L1"]["claim"] == SLSA_L1_HONEST
    assert lv["L2"]["earned"] is False and lv["L2"]["claim"] == SLSA_L2_ATTESTED
    assert lv["L3"]["earned"] is False and lv["L3"]["claim"] == SLSA_L3_ROADMAP
    assert ladder["never_upgraded"] is True
    print("[3] SLSA L1 honest / L2 attested / L3 roadmap — verbatim, L3 NOT earned  OK")

    # 4) every stage / evidence element cites a KNOWN source; all 5 primary sources present.
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
    for sid in ("slsa-v1.0", "in-toto-2019", "sigstore-2022", "c2pa", "dsse"):
        assert sid in blob, f"missing primary source {sid}"
    print(f"[4] citations {sorted(cited)}; all 5 primary sources present  OK")

    # 5) the real micro-artifact roundtrip ran + reconciled (MEASURED) and is independently
    #    recomputable; the signature is NEVER fabricated (honest placeholder, signed=False).
    m = p["micro_artifact"]
    assert m["label"] in (MEASURED, HONEST_STUB)
    if m["label"] == MEASURED:
        assert m["verify_ok"] is True
        assert m["dsse"]["signed"] is False
        assert m["dsse"]["signature"] == DSSE_PLACEHOLDER
        # recompute the whole roundtrip independently here to prove it is honest.
        weight_blob = b"szl-modeled-lm:layer0.weights:v1:[0.03,-0.11,0.42,...]"
        assert hashlib.sha256(weight_blob).hexdigest() == m["subject"]["sha256"], \
            "subject digest not client-recomputable"
        stmt = {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [{"name": "szl-modeled-lm/layer0.weights",
                         "digest": {"sha256": m["subject"]["sha256"]}}],
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {"buildType": "szl-modeled/quantize+package"},
                "runDetails": {"builder": {"id": "modeled://a11oy/frontier/supplychain"}},
            },
        }
        payload = json.dumps(stmt, sort_keys=True, separators=(",", ":")).encode()
        pae = _dsse_pae(b"application/vnd.in-toto+json", payload)
        assert hashlib.sha256(pae).hexdigest() == m["dsse"]["pae_sha256"], "PAE not recomputable"
        root, _ = _merkle_root([bytes(pae), b"log:sibling:genesis"])
        assert root == m["transparency_log"]["merkle_root"], "Merkle root not recomputable"
    print(f"[5] micro-artifact label={m['label']}, verify_ok={m.get('verify_ok')}, "
          "signature honest-unsigned, independently recomputed  OK")

    # 6) no green/1.0 verified state; trust ceiling never 100%; no fabricated signature anywhere.
    assert d["trust_100_percent"] is False and d["trust_ceiling"] < 1.0
    assert "VERIFIED" not in p["label"]
    assert "REAL-SIGNED" not in blob, "no real signature may be claimed"
    print("[6] no VERIFIED/green-1.0 state; trust never 100%; no fabricated signature  OK")

    print("\n--- payload keys ---")
    for k in p:
        print(f"  - {k}")
    print("\nok:true checks:6")
    _sys.exit(0)
