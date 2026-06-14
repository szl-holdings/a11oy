# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""pq_signing — SZL-NATIVE POST-QUANTUM SIGNATURE SEAM for the DSSE/cosign path.

GAP 6 (post-quantum readiness). Our PINN compute-bounds certificate
(``agentic_pinn/physics_bounds.py``) is signer-ready but currently anchored on
DSSE Ed25519. The market — and our own quantum/PNT positioning — is moving to
**post-quantum signatures**. This module adds an ALGORITHM-AGILE signing seam so
the SAME DSSE/cosign envelope can be signed and verified under:

    alg ∈ { "ed25519", "ml-dsa", "hybrid" }

ESTABLISHED STANDARDS — CITED, never claimed as SZL's:
  * NIST FIPS 204 (Aug 2024), "Module-Lattice-Based Digital Signature Standard"
    (ML-DSA), derived from CRYSTALS-Dilithium. ML-DSA-65 is NIST's enterprise
    default (Category 3): pk 1952 B, sk 4032 B, sig 3309 B.
    https://csrc.nist.gov/pubs/fips/204/final
  * IETF "Hybrid Ed25519 with ML-DSA-65 for SSH"
    (draft-josefsson-ssh-ed25519mldsa65), and the IETF Agent Trust Negotiation /
    PQUIP hybrid-mode recommendation: pair a classical (Ed25519, RFC 8032)
    signature with a post-quantum (ML-DSA) signature, and require BOTH to verify.
    https://www.ietf.org/archive/id/draft-josefsson-ssh-ed25519mldsa65-01.html
  * IETF LAMPS "Composite ML-DSA" (draft-ietf-lamps-pq-composite-sigs) and BSI
    2021 guidance: during the transition period, PQC lattice schemes "should not
    be used alone … but only in hybrid mode, in combination with a classical
    method." https://www.ietf.org/archive/id/draft-ietf-lamps-pq-composite-sigs-01.html

DOCTRINE v11 (HARD) — HONESTY ABOUT THE PQ PRIMITIVE:
  * Ed25519 is REAL (``cryptography`` hazmat) in every environment.
  * ML-DSA is REAL **iff** a pure-Python FIPS-204 library is importable
    (``dilithium-py``). When it is, alg is labelled "ml-dsa" and the signature is
    a genuine ML-DSA-65 signature.
  * When NO PQ library is present on the box, we DO NOT fabricate a PQ signature.
    We emit a CLEARLY-LABELLED structural stub with
    ``alg = "ml-dsa-STUB (no PQ lib present — STRUCTURAL ONLY, not a real PQ
    signature)"``. The stub is a deterministic HMAC-SHA512 tag whose ONLY purpose
    is to exercise the envelope plumbing (header, transport, verify wiring). It is
    NEVER claimed as post-quantum security. A relying party MUST reject it for any
    real PQ-security decision. Forge wires the real lib on the box (see FINDINGS).
  * Λ = Conjecture 1: a signature is NOT proof of safety (see GAP 1). This seam
    proves *who signed*, never *that the payload is safe*.

Pure-Python + stdlib + (optional) cryptography/dilithium-py → sovereign, own-metal,
auditable, 0 runtime CDN. No key is ever committed; keys are generated in-process
for the demo and tests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Algorithm identifiers (the JWS/DSSE header value drives verify — alg-agility) #
# --------------------------------------------------------------------------- #
ALG_ED25519 = "ed25519"          # classical, REAL (RFC 8032)
ALG_ML_DSA = "ml-dsa"            # post-quantum, REAL iff FIPS-204 lib importable
ALG_HYBRID = "hybrid"            # Ed25519 + ML-DSA, BOTH required (transition posture)

# Honest label used when no PQ library is present on the box. The substring
# "STUB" and "not a real PQ signature" are load-bearing: tests and relying parties
# key off them. NEVER remove or soften this label.
ALG_ML_DSA_STUB = "ml-dsa-STUB (no PQ lib present — STRUCTURAL ONLY, not a real PQ signature)"

SUPPORTED_ALGS = frozenset({ALG_ED25519, ALG_ML_DSA, ALG_HYBRID})

# ML-DSA parameter set we standardize on (FIPS 204 Category 3, NIST enterprise default)
ML_DSA_VARIANT = "ML-DSA-65"

CITATIONS = {
    "fips204": (
        "NIST FIPS 204 (Aug 2024), 'Module-Lattice-Based Digital Signature "
        "Standard' (ML-DSA), from CRYSTALS-Dilithium. "
        "https://csrc.nist.gov/pubs/fips/204/final"
    ),
    "ietf_hybrid_ssh": (
        "IETF draft-josefsson-ssh-ed25519mldsa65: Hybrid Ed25519 + ML-DSA-65; "
        "verify = (Ed25519 verifies) AND (ML-DSA-65 verifies). "
        "https://www.ietf.org/archive/id/draft-josefsson-ssh-ed25519mldsa65-01.html"
    ),
    "ietf_composite_lamps": (
        "IETF draft-ietf-lamps-pq-composite-sigs: PQ/Traditional composite "
        "signatures (ML-DSA + Ed25519) for X.509/PKIX/CMS; BSI 2021 hybrid-mode "
        "guidance. https://www.ietf.org/archive/id/draft-ietf-lamps-pq-composite-sigs-01.html"
    ),
    "rfc8032": "RFC 8032: Edwards-Curve Digital Signature Algorithm (EdDSA), Ed25519.",
    "doctrine": (
        "SZL Doctrine v11: no fabricated signatures; MEASURED vs MODELED labels; "
        "Λ = Conjecture 1 — a signature is NOT proof of safety."
    ),
}

# --------------------------------------------------------------------------- #
# Backend capability probe — HONEST about what is actually present on the box  #
# --------------------------------------------------------------------------- #
try:  # classical Ed25519 — REAL primitive, expected present everywhere
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.exceptions import InvalidSignature as _Ed25519InvalidSignature
    _HAVE_ED25519 = True
except Exception:  # pragma: no cover - environment without cryptography
    _HAVE_ED25519 = False
    _Ed25519InvalidSignature = Exception

try:  # post-quantum ML-DSA (FIPS 204) — REAL iff dilithium-py importable
    from dilithium_py.ml_dsa import ML_DSA_65 as _ML_DSA
    _HAVE_ML_DSA = True
except Exception:
    _ML_DSA = None
    _HAVE_ML_DSA = False


def backend_status() -> dict:
    """Report — HONESTLY — which primitives are real on this box right now."""
    return {
        "ed25519_real": _HAVE_ED25519,
        "ml_dsa_real": _HAVE_ML_DSA,
        "ml_dsa_variant": ML_DSA_VARIANT if _HAVE_ML_DSA else None,
        "ml_dsa_mode": "REAL FIPS-204 (dilithium-py)" if _HAVE_ML_DSA
        else "STUB (STRUCTURAL ONLY — no PQ lib; Forge wires the real lib on the box)",
    }


# --------------------------------------------------------------------------- #
# Keypair container — algorithm-agile                                          #
# --------------------------------------------------------------------------- #
@dataclass
class KeyPair:
    """Algorithm-agile keypair. For hybrid, holds BOTH component keys.

    Keys live only in-process (bytes). NEVER serialized to disk here; NEVER
    committed. The demo/tests generate ephemeral keys.
    """
    alg: str
    # Ed25519 component (raw 32-byte seed for sk, raw 32-byte pk)
    ed25519_sk: Optional[bytes] = None
    ed25519_pk: Optional[bytes] = None
    # ML-DSA component (FIPS-204 byte blobs) — present only when the real lib is here
    ml_dsa_sk: Optional[bytes] = None
    ml_dsa_pk: Optional[bytes] = None
    # STUB component (HMAC key) — present only when NO PQ lib is here
    stub_key: Optional[bytes] = None
    ml_dsa_is_real: bool = False

    def public_bundle(self) -> dict:
        """Public material a relying party needs, with honest per-component labels."""
        out: dict = {"alg": self.alg}
        if self.ed25519_pk is not None:
            out["ed25519_pk_hex"] = self.ed25519_pk.hex()
        if self.ml_dsa_is_real and self.ml_dsa_pk is not None:
            out["ml_dsa_pk_sha256"] = "sha256:" + hashlib.sha256(self.ml_dsa_pk).hexdigest()
            out["ml_dsa_variant"] = ML_DSA_VARIANT
        elif self.stub_key is not None:
            out["ml_dsa_stub_note"] = (
                "STRUCTURAL STUB — no PQ public key; not a real PQ identity"
            )
        return out


# --------------------------------------------------------------------------- #
# Internal component sign/verify                                               #
# --------------------------------------------------------------------------- #
def _ed25519_sign(sk_seed: bytes, payload: bytes) -> bytes:
    if not _HAVE_ED25519:
        raise RuntimeError("Ed25519 backend (cryptography) not available on this box")
    sk = Ed25519PrivateKey.from_private_bytes(sk_seed)
    return sk.sign(payload)


def _ed25519_verify(pk_raw: bytes, payload: bytes, sig: bytes) -> bool:
    if not _HAVE_ED25519:
        raise RuntimeError("Ed25519 backend (cryptography) not available on this box")
    try:
        Ed25519PublicKey.from_public_bytes(pk_raw).verify(sig, payload)
        return True
    except _Ed25519InvalidSignature:
        return False
    except Exception:
        return False


def _ml_dsa_sign(kp: KeyPair, payload: bytes) -> dict:
    """Sign with REAL ML-DSA if present, else an HONESTLY-LABELLED structural stub.

    Returns a dict carrying the component signature AND its honest alg label.
    """
    if kp.ml_dsa_is_real and _HAVE_ML_DSA:
        sig = _ML_DSA.sign(kp.ml_dsa_sk, payload)
        return {"alg": ALG_ML_DSA, "sig_hex": sig.hex(), "real": True}
    # No PQ lib: structural stub ONLY. NOT a real PQ signature. Deterministic
    # HMAC-SHA512 tag over the payload, keyed by the in-process stub key. Exists
    # purely to exercise the envelope/verify plumbing; carries ZERO PQ security.
    tag = hmac.new(kp.stub_key, payload, hashlib.sha512).hexdigest()
    return {
        "alg": ALG_ML_DSA_STUB,
        "sig_hex": tag,
        "real": False,
        "warning": (
            "This is a STRUCTURAL STUB, not a post-quantum signature. It proves "
            "NOTHING about quantum resistance. Reject for any real PQ decision. "
            "Forge installs dilithium-py (or liboqs) on the box to make this real."
        ),
    }


def _ml_dsa_verify(kp_or_pub: dict, payload: bytes, comp: dict) -> bool:
    """Verify the ML-DSA component. Honest about real-vs-stub.

    ``kp_or_pub`` carries either the real ML-DSA public key (hex) or the stub key.
    A real verifier MUST NOT accept a stub as PQ-secure; this returns the
    structural validity only, and the caller is told (via the alg label) that it
    is a stub.
    """
    if comp.get("real"):
        if not _HAVE_ML_DSA:
            # The signature claims to be real ML-DSA but we have no verifier here.
            return False
        pk = bytes.fromhex(kp_or_pub["ml_dsa_pk_hex"])
        try:
            return bool(_ML_DSA.verify(pk, payload, bytes.fromhex(comp["sig_hex"])))
        except Exception:
            return False
    # Stub path: recompute the HMAC tag and compare in constant time.
    stub_key = kp_or_pub.get("stub_key")
    if stub_key is None:
        return False
    expected = hmac.new(stub_key, payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, comp.get("sig_hex", ""))


# --------------------------------------------------------------------------- #
# Public API: keygen / sign / verify                                          #
# --------------------------------------------------------------------------- #
def keygen(alg: str) -> KeyPair:
    """Generate an algorithm-agile keypair for the requested alg.

    For ``hybrid`` both an Ed25519 keypair and an ML-DSA (real or stub) keypair
    are produced. ML-DSA is REAL iff a FIPS-204 library is importable; otherwise
    a stub key is generated and the component is honestly labelled a STUB.
    """
    if alg not in SUPPORTED_ALGS:
        raise ValueError(
            f"unsupported alg {alg!r}; relying parties accept only {sorted(SUPPORTED_ALGS)}"
        )
    kp = KeyPair(alg=alg)
    if alg in (ALG_ED25519, ALG_HYBRID):
        if not _HAVE_ED25519:
            raise RuntimeError("Ed25519 backend (cryptography) not available on this box")
        sk = Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization
        kp.ed25519_sk = sk.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        kp.ed25519_pk = sk.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    if alg in (ALG_ML_DSA, ALG_HYBRID):
        if _HAVE_ML_DSA:
            pk, sk = _ML_DSA.keygen()
            kp.ml_dsa_pk, kp.ml_dsa_sk = pk, sk
            kp.ml_dsa_is_real = True
        else:
            kp.stub_key = os.urandom(32)
            kp.ml_dsa_is_real = False
    return kp


def sign(payload: bytes, alg: str, kp: KeyPair) -> dict:
    """Sign ``payload`` under ``alg``. Returns a DSSE/JWS-style signed envelope.

    The envelope HEADER carries the alg (and, for hybrid/ml-dsa, the honest
    real-vs-stub label). The header is what drives verify (algorithm-agility): a
    relying party reads the header, checks the alg is supported, and dispatches.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    if alg not in SUPPORTED_ALGS:
        raise ValueError(
            f"unsupported alg {alg!r}; relying parties accept only {sorted(SUPPORTED_ALGS)}"
        )
    if kp.alg != alg:
        raise ValueError(f"keypair alg {kp.alg!r} does not match requested alg {alg!r}")

    payload = bytes(payload)
    payload_sha256 = "sha256:" + hashlib.sha256(payload).hexdigest()
    signatures: dict = {}
    header_algs: list = []

    if alg in (ALG_ED25519, ALG_HYBRID):
        signatures["ed25519"] = {
            "alg": ALG_ED25519,
            "sig_hex": _ed25519_sign(kp.ed25519_sk, payload).hex(),
            "real": True,
        }
        header_algs.append(ALG_ED25519)

    if alg in (ALG_ML_DSA, ALG_HYBRID):
        comp = _ml_dsa_sign(kp, payload)
        signatures["ml_dsa"] = comp
        header_algs.append(comp["alg"])  # honest label (real ml-dsa OR the STUB string)

    # DSSE/JWS-style header: this is what relying parties read to drive verify.
    header = {
        "envelope_type": "szl/pq-dsse/v1",
        "alg": alg,                       # logical alg: ed25519 | ml-dsa | hybrid
        "component_algs": header_algs,    # concrete, honestly-labelled components
        "payload_sha256": payload_sha256,
        "ml_dsa_real": kp.ml_dsa_is_real if alg in (ALG_ML_DSA, ALG_HYBRID) else None,
        "hybrid_policy": (
            "BOTH Ed25519 AND ML-DSA must verify (IETF hybrid posture)"
            if alg == ALG_HYBRID else None
        ),
        "lambda_note": "Λ = Conjecture 1 (advisory). A signature is NOT proof of safety.",
        "timestamp_utc": time.time(),
    }
    envelope = {
        "header": header,
        "signatures": signatures,
        "public_bundle": kp.public_bundle(),
    }
    return envelope


def verify(payload: bytes, envelope: dict, kp: KeyPair) -> bool:
    """Verify ``envelope`` over ``payload``. The HEADER alg drives the check.

    Rules (algorithm-agility + IETF hybrid posture):
      * Header alg MUST be in SUPPORTED_ALGS — else REJECT (unsupported alg).
      * Payload hash in the header MUST match the actual payload — else REJECT
        (tamper-evident).
      * ed25519: the Ed25519 component must verify.
      * ml-dsa:  the ML-DSA component must verify (real lib) OR the stub tag must
                 match (when no PQ lib) — the alg label tells the relying party
                 which it got.
      * hybrid:  BOTH components must verify (logical AND). Either failing ⇒ REJECT.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    payload = bytes(payload)
    header = envelope.get("header", {})
    alg = header.get("alg")

    # Algorithm-agility: relying party rejects unsupported algs by header.
    if alg not in SUPPORTED_ALGS:
        return False

    # Tamper-evidence: header payload hash must match the supplied payload.
    expected_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
    if header.get("payload_sha256") != expected_hash:
        return False

    sigs = envelope.get("signatures", {})

    ed_ok = True
    ml_ok = True

    if alg in (ALG_ED25519, ALG_HYBRID):
        comp = sigs.get("ed25519")
        if not comp:
            return False
        ed_ok = _ed25519_verify(kp.ed25519_pk, payload, bytes.fromhex(comp["sig_hex"]))

    if alg in (ALG_ML_DSA, ALG_HYBRID):
        comp = sigs.get("ml_dsa")
        if not comp:
            return False
        pub = {
            "ml_dsa_pk_hex": kp.ml_dsa_pk.hex() if kp.ml_dsa_pk else None,
            "stub_key": kp.stub_key,
        }
        ml_ok = _ml_dsa_verify(pub, payload, comp)

    if alg == ALG_HYBRID:
        return bool(ed_ok and ml_ok)      # BOTH required — IETF hybrid posture
    if alg == ALG_ED25519:
        return bool(ed_ok)
    if alg == ALG_ML_DSA:
        return bool(ml_ok)
    return False


def envelope_is_real_pq(envelope: dict) -> bool:
    """HONEST helper: True iff the envelope's ML-DSA component is a REAL PQ sig.

    A relying party making a PQ-security decision MUST gate on this — a stub
    envelope is structurally valid but carries NO post-quantum security.
    """
    comp = envelope.get("signatures", {}).get("ml_dsa")
    if comp is None:
        return False
    return bool(comp.get("real")) and not str(comp.get("alg", "")).startswith("ml-dsa-STUB")


__all__ = [
    "ALG_ED25519", "ALG_ML_DSA", "ALG_HYBRID", "ALG_ML_DSA_STUB",
    "SUPPORTED_ALGS", "ML_DSA_VARIANT", "CITATIONS",
    "KeyPair", "keygen", "sign", "verify",
    "backend_status", "envelope_is_real_pq",
]


# --------------------------------------------------------------------------- #
# DEMO: sign the SHA-256 of a real workspace file in each mode, honest labels  #
# --------------------------------------------------------------------------- #
def _demo() -> None:
    # Sign over the hash of a REAL workspace file (the DSSE seam we are extending).
    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "agentic_pinn", "physics_bounds.py",
    )
    if not os.path.exists(target):
        target = os.path.abspath(__file__)
    with open(target, "rb") as f:
        digest = hashlib.sha256(f.read()).digest()
    payload = b"szl/pq-dsse/v1 payload sha256:" + digest

    print("SZL POST-QUANTUM SIGNATURE SEAM (GAP 6) — honest demo")
    print("=" * 68)
    print("backend:", json.dumps(backend_status(), indent=2))
    print(f"signing over SHA-256 of: {os.path.relpath(target)}")
    print("=" * 68)

    for alg in (ALG_ED25519, ALG_ML_DSA, ALG_HYBRID):
        kp = keygen(alg)
        env = sign(payload, alg, kp)
        ok = verify(payload, env, kp)
        # tamper test
        tampered_ok = verify(payload + b"X", env, kp)
        print(f"\n--- alg = {alg} ---")
        print("  component_algs :", env["header"]["component_algs"])
        print("  real PQ?       :", envelope_is_real_pq(env))
        print("  verify (good)  :", ok)
        print("  verify (tamper):", tampered_ok, "(must be False)")
        if alg in (ALG_ML_DSA, ALG_HYBRID) and not env["header"]["ml_dsa_real"]:
            print("  HONEST LABEL   : ml-dsa component is a STRUCTURAL STUB, NOT a PQ sig")


if __name__ == "__main__":
    _demo()
