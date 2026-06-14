# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""content_credentials — SZL-native C2PA-style Content Credentials (GAP 2).

WHY (regulatory): EU AI Act **Article 50** transparency obligations are enforceable
**2 August 2026**. Providers of generative-AI systems must mark synthetic outputs in
a *machine-readable* format that is detectable as artificially generated or
manipulated (Art. 50(2)); deployers of deepfakes / AI text on matters of public
interest must disclose (Art. 50(4)). The technical marking standard the market
converged on is **C2PA Content Credentials** (OpenAI + Google adopted C2PA, May 2026),
operationalised through the EU **Code of Practice on AI-generated content** (2nd draft
2026-03-03). See CITATIONS at the bottom of this file for exact references.

WHAT this module does: attach a cryptographically-signed, C2PA-ALIGNED manifest to any
asset our estate GENERATES (charts, holographic renders, AI text/outputs). It mirrors
the C2PA manifest model — a single `claim` that lists `assertions` (a hard binding to
the asset bytes via sha256, `c2pa.actions` describing created/edited actions with a
`digitalSourceType`, an explicit AI-generated flag + model id, and `ingredients`
listing source assets) and a `claim_signature` over the canonical claim.

DOCTRINE v11 (HARD), carried verbatim from physics_bounds.py / hatun DSSE:
  * NO fabricated signatures. The signer uses the SAME real Ed25519/cosign identity
    seam as our DSSE certs (env-provided PEM key; never committed). If no key is
    present, the credential stays **STRUCTURAL-ONLY** — it is NEVER painted as a
    validated/green credential. A signature is NOT proof of safety (the npm/TanStack
    lesson, GAP 1) and Λ is advisory, never "proven trust".
  * The Interim-Trust-List lesson (C2PA ITL froze 2026-01-01; self-signed manifests no
    longer validate against the C2PA Trust List): we LABEL TRUST HONESTLY. A self-signed
    own-key Ed25519 manifest validates *cryptographically* but is reported at trust
    level **SELF_SIGNED** — explicitly NOT C2PA-Trust-List-anchored. Never a fake green.

PURE STDLIB manifest (hashlib/json) — does NOT require the c2pa Rust SDK. Structured so
Forge can later embed it into the asset via `c2patool` at generation time (a sidecar
`.c2pa.json` is emitted now; the same claim feeds c2patool for an embedded JUMBF box).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# ── Real Ed25519 crypto, SAME seam as our DSSE certs (cryptography lib) ──────────
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PrivateFormat,
        PublicFormat,
        NoEncryption,
        load_pem_private_key,
        load_pem_public_key,
    )
    from cryptography.exceptions import InvalidSignature

    _CRYPTO = True
except Exception:  # pragma: no cover - cryptography present in our image
    _CRYPTO = False


# --------------------------------------------------------------------------- #
# Constants / doctrine                                                          #
# --------------------------------------------------------------------------- #
CLAIM_GENERATOR_DEFAULT = "szl-content-credentials/1.0.0"
MANIFEST_TYPE = "szl/c2pa-content-credential/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.szl.c2pa-content-credential+json"

# C2PA digitalSourceType IRIs (IPTC vocabulary, used verbatim by C2PA assertions).
DST_TRAINED_ALGORITHMIC = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)  # fully AI-generated
DST_COMPOSITE_WITH_TRAINED = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia"
)  # AI-assisted edit of real content
DST_DIGITAL_CAPTURE = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"
)  # not AI (camera/sensor)
DST_CREATIVE_WORK = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/digitalArt"
)  # human/tool-authored, not AI

# Trust levels, reported HONESTLY (the Interim-Trust-List lesson).
TRUST_STRUCTURAL_ONLY = "STRUCTURAL-ONLY"   # unsigned; structure only, NEVER a green
TRUST_SELF_SIGNED = "SELF_SIGNED"           # real sig, own key, NOT C2PA-TL anchored
TRUST_C2PA_TRUST_LIST = "C2PA_TRUST_LIST"   # would require a CA cert from the C2PA TL
TRUST_TAMPERED = "TAMPERED"                 # hash/sig mismatch — reject

DOCTRINE = (
    "v11 LOCKED: NO fabricated signatures; UNSIGNED stays STRUCTURAL-ONLY (never a fake "
    "green); real Ed25519 over DSSE PAE using the SAME cosign/DSSE identity seam; "
    "self-signed own-key manifests are labelled SELF_SIGNED, NOT C2PA-Trust-List "
    "anchored (ITL froze 2026-01-01); a signature is NOT proof of safety; Λ=Conjecture 1 "
    "(advisory, never 'proven trust'); sovereign own-metal; no committed key."
)

CITATIONS = {
    "c2pa_spec": (
        "C2PA Technical Specification v2.x / Implementation Guidance "
        "(spec.c2pa.org/specifications/.../guidance/Guidance.html): a Manifest has one "
        "claim describing the claim_generator and listing assertions; standard manifests "
        "MUST contain a c2pa.actions assertion stating c2pa.created (de novo, incl. "
        "generative-AI) or c2pa.opened (edit), with a digitalSourceType; a hard binding "
        "(c2pa.hash.data) binds the claim to the asset bytes; ingredients list source "
        "assets; the claim is signed (X.509 in C2PA) giving signer + tamper evidence."
    ),
    "c2pa_ai_assertions": (
        "C2PA AI-content disclosure: c2pa.actions c2pa.created with "
        "digitalSourceType=trainedAlgorithmicMedia => fully AI-generated; "
        "compositeWithTrainedAlgorithmicMedia => AI-assisted edit of real content "
        "(C2PA 2.x; IPTC digitalsourcetype NewsCodes)."
    ),
    "c2pa_trust_list": (
        "C2PA Trust List / Interim Trust List: the ITL froze 2026-01-01; going forward "
        "only certificates from CAs certified under the C2PA Conformance Program / Trust "
        "List validate as trusted. Self-signed manifests are NOT trusted by conformant "
        "validators; validators MUST distinguish ITL trust from C2PA-TL trust "
        "(c2pa.org/faqs; CAI Summit Toronto 2026)."
    ),
    "eu_ai_act_art50": (
        "EU AI Act Article 50 (Regulation (EU) 2024/1689), Chapter IV — transparency. "
        "Enforceable 2 August 2026. Art. 50(2): providers of generative-AI systems must "
        "mark synthetic audio/image/video/text outputs in a machine-readable format and "
        "ensure they are detectable as artificially generated or manipulated, with "
        "solutions effective/interoperable/robust/reliable as far as technically "
        "feasible. Art. 50(4): deployers of deepfakes and of AI text on matters of "
        "public interest must disclose. (AI Omnibus, May 2026: GPAI already on market "
        "before 2026-08-02 has until 2026-12-02 for the machine-readable marking.)"
    ),
    "eu_code_of_practice": (
        "EU Commission draft Guidelines on Article 50 (consultation 2026-05-08) + Code "
        "of Practice on transparency of AI-generated content (2nd draft 2026-03-03, "
        "final expected 2026; multi-layer marking incl. C2PA-style content credentials "
        "+ watermarking). Voluntary tool to support practical Art. 50 marking/labelling."
    ),
    "szl_identity": (
        "Signing reuses SZL's existing DSSE/cosign identity seam (physics_bounds.py + "
        "hatun_mcp.governance.DsseSigner): real key from env PEM (never committed), "
        "DSSE Pre-Authentication Encoding (DSSEv1), cosign.pub external trust anchor. "
        "Here Ed25519 (matches the PINN cert FA-001 Ed25519 keyid pattern)."
    ),
    "honesty": (
        "Doctrine v11: a signature is NOT proof of safety (npm/TanStack SLSA-signed "
        "malware, CVE-2026-45321). C2PA certifies the declared HISTORY of content, not "
        "its truth. Trust level is reported honestly; UNSIGNED => STRUCTURAL-ONLY."
    ),
}


# --------------------------------------------------------------------------- #
# Hashing — same canonical sha256 pattern as physics_bounds._hash_measured     #
# --------------------------------------------------------------------------- #
def sha256_file(path: str, *, chunk: int = 1 << 20) -> str:
    """sha256 of a real file's bytes, streamed. Returns 'sha256:<hex>'."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canon(obj: Any) -> bytes:
    """Deterministic canonical JSON (sorted keys, tight separators) — the bytes we hash
    and sign. Mirrors hatun DsseSigner.sign canonicalization."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def _pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (in-toto/DSSE spec) — identical to
    hatun_mcp.governance._pae, the SAME seam our certs use."""
    return b"DSSEv1 %d %s %d %s" % (
        len(payload_type),
        payload_type.encode(),
        len(payload),
        payload,
    )


# --------------------------------------------------------------------------- #
# Ingredients (source assets that went INTO the generated asset)               #
# --------------------------------------------------------------------------- #
@dataclass
class Ingredient:
    """A source asset incorporated into the current asset (C2PA 'ingredient')."""
    title: str
    asset_hash: str                 # 'sha256:...'
    relationship: str = "componentOf"   # C2PA: parentOf | componentOf | inputTo
    instance_id: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# The C2PA-aligned manifest (claim_generator + assertions + claim)             #
# --------------------------------------------------------------------------- #
@dataclass
class ContentCredentialManifest:
    """A C2PA-ALIGNED manifest. One claim, listing assertions, over one asset.

    Fields map to C2PA concepts:
      * claim_generator           -> the SZL tool/version that produced the asset
      * assertions[c2pa.hash.data]-> hard binding to the asset bytes (sha256)
      * assertions[c2pa.actions]  -> created/edited actions + digitalSourceType
      * ai_generated / model_id   -> explicit AI flag (+ model id when AI)
      * ingredients               -> source assets
    """
    manifest_type: str
    claim_generator: str
    asset_title: str
    asset_format: str               # MIME, e.g. image/png, text/plain
    asset_hash: str                 # 'sha256:...' — the HARD BINDING
    ai_generated: bool              # explicit Art.50(2) flag
    model_id: Optional[str]         # model identity when ai_generated (else None)
    digital_source_type: str        # IPTC IRI (trainedAlgorithmicMedia, etc.)
    actions: list                   # list of {action, when, softwareAgent, ...}
    ingredients: list               # list of Ingredient dicts
    created_utc: float
    instance_id: str
    doctrine: str = DOCTRINE
    labels: dict = field(default_factory=lambda: {
        "ai_generated": "explicit EU AI Act Art.50(2) machine-readable AI flag",
        "asset_hash": "C2PA hard binding (c2pa.hash.data) to the real asset bytes",
        "trust": "reported by verify(): STRUCTURAL-ONLY | SELF_SIGNED | C2PA_TRUST_LIST | TAMPERED",
    })
    citations: dict = field(default_factory=lambda: dict(CITATIONS))

    def assertions(self) -> list:
        """The C2PA assertion list this manifest binds (claim covers these)."""
        a = [
            {
                "label": "c2pa.hash.data",
                "data": {"alg": "sha256", "hash": self.asset_hash,
                         "name": self.asset_title},
            },
            {
                "label": "c2pa.actions",
                "data": {"actions": self.actions,
                         "digitalSourceType": self.digital_source_type},
            },
            {
                # SZL-native explicit AI flag (machine-readable, Art.50(2)).
                "label": "szl.ai_generated",
                "data": {"ai_generated": self.ai_generated, "model_id": self.model_id},
            },
        ]
        if self.ingredients:
            a.append({"label": "c2pa.ingredients", "data": {"ingredients": self.ingredients}})
        return a

    def claim(self) -> dict:
        """The single C2PA claim: describes the generator and the assertions it covers.
        This dict (canonicalized) is exactly what gets signed."""
        return {
            "manifest_type": self.manifest_type,
            "claim_generator": self.claim_generator,
            "instance_id": self.instance_id,
            "asset": {
                "title": self.asset_title,
                "format": self.asset_format,
                "hash": self.asset_hash,
            },
            "ai_generated": self.ai_generated,
            "model_id": self.model_id,
            "created_utc": self.created_utc,
            "assertions": self.assertions(),
        }

    def to_dict(self) -> dict:
        d = asdict(self)
        d["claim"] = self.claim()
        return d


def build_manifest(
    *,
    asset_path: Optional[str] = None,
    asset_bytes: Optional[bytes] = None,
    asset_title: str,
    asset_format: str,
    ai_generated: bool,
    model_id: Optional[str] = None,
    claim_generator: str = CLAIM_GENERATOR_DEFAULT,
    actions: Optional[list] = None,
    ingredients: Optional[list] = None,
    edited: bool = False,
    digital_source_type: Optional[str] = None,
) -> ContentCredentialManifest:
    """Build a C2PA-aligned manifest. Provide EITHER asset_path (a REAL file, hashed
    streaming) OR asset_bytes. `ai_generated` carries the explicit Art.50(2) flag and,
    when True, `model_id` SHOULD be supplied (model identity).

    Honesty guard: if ai_generated is True a model_id of None is permitted but recorded
    as such — we never invent a model id.
    """
    if asset_path is not None:
        asset_hash = sha256_file(asset_path)
    elif asset_bytes is not None:
        asset_hash = sha256_bytes(asset_bytes)
    else:
        raise ValueError("provide asset_path or asset_bytes")

    now = time.time()
    # Default digitalSourceType honestly reflects the AI flag.
    if digital_source_type is None:
        if ai_generated:
            digital_source_type = (
                DST_COMPOSITE_WITH_TRAINED if edited else DST_TRAINED_ALGORITHMIC
            )
        else:
            digital_source_type = DST_CREATIVE_WORK

    if actions is None:
        action = "c2pa.opened" if edited else "c2pa.created"
        actions = [{
            "action": action,
            "when": now,
            "softwareAgent": claim_generator,
            "digitalSourceType": digital_source_type,
        }]

    ing = [i.to_dict() if isinstance(i, Ingredient) else i for i in (ingredients or [])]
    instance_id = "xmp:iid:" + hashlib.sha256(
        f"{asset_hash}:{now}:{asset_title}".encode()
    ).hexdigest()[:32]

    return ContentCredentialManifest(
        manifest_type=MANIFEST_TYPE,
        claim_generator=claim_generator,
        asset_title=asset_title,
        asset_format=asset_format,
        asset_hash=asset_hash,
        ai_generated=ai_generated,
        model_id=model_id,
        digital_source_type=digital_source_type,
        actions=actions,
        ingredients=ing,
        created_utc=now,
        instance_id=instance_id,
    )


# --------------------------------------------------------------------------- #
# Signer — SAME Ed25519/cosign/DSSE identity seam as our certs                  #
# --------------------------------------------------------------------------- #
class CredentialSigner:
    """Signs the canonical claim with a REAL Ed25519 key over the DSSE PAE.

    Key sourcing mirrors hatun_mcp.governance.DsseSigner: PEM from env
    SZL_C2PA_SIGNING_KEY (or _PATH). NEVER committed. If no key is present, the signer
    is in PLACEHOLDER mode and produces NO signature (the credential stays
    STRUCTURAL-ONLY) — disclosed, never faked.

    `keyid` follows the PINN-cert pattern: sha256 of the public key DER, hex.
    """

    def __init__(self, key_pem: Optional[str] = None, keyid_label: str = "szl-c2pa-ed25519") -> None:
        self._key = None
        self._mode = "PLACEHOLDER"
        self._keyid_label = keyid_label
        pem = key_pem or os.environ.get("SZL_C2PA_SIGNING_KEY")
        path = os.environ.get("SZL_C2PA_SIGNING_KEY_PATH")
        if pem is None and path and os.path.exists(path):
            pem = open(path).read()
        if _CRYPTO and pem:
            try:
                k = load_pem_private_key(pem.encode() if isinstance(pem, str) else pem, password=None)
                if isinstance(k, Ed25519PrivateKey):
                    self._key = k
                    self._mode = "ED25519"
            except Exception:
                self._key = None
                self._mode = "PLACEHOLDER"

    @property
    def mode(self) -> str:
        return self._mode

    @staticmethod
    def generate_key_pem() -> str:
        """Generate a fresh Ed25519 private key PEM (for tests / a fresh own-metal key).
        In production the key lives in the box secret store, never committed."""
        if not _CRYPTO:
            raise RuntimeError("cryptography not available")
        k = Ed25519PrivateKey.generate()
        return k.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode()

    def public_key_pem(self) -> Optional[str]:
        if self._key is None:
            return None
        return self._key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def _keyid(self) -> Optional[str]:
        if self._key is None:
            return None
        der = self._key.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        return "sha256:" + hashlib.sha256(der).hexdigest()

    def sign_manifest(self, manifest: ContentCredentialManifest) -> dict:
        """Return a DSSE-style envelope over the canonical claim. If unsigned, the
        envelope carries NO signature and is labelled PLACEHOLDER — never faked."""
        claim = manifest.claim()
        payload = _canon(claim)
        b64 = base64.b64encode(payload).decode()
        env = {
            "payloadType": DSSE_PAYLOAD_TYPE,
            "payload": b64,
            "signatures": [],
            "_mode": self._mode,
            "_pae": "DSSEv1",
            "_note": (
                "REAL Ed25519 signature over DSSE PAE (same cosign/DSSE seam as the PINN "
                "cert). Self-signed own key => trust level SELF_SIGNED, NOT C2PA Trust "
                "List anchored."
                if self._mode == "ED25519"
                else "PLACEHOLDER: no signing key in this process; NO signature produced. "
                "Credential is STRUCTURAL-ONLY. Disclosed, NOT faked."
            ),
        }
        if self._key is not None:
            sig = self._key.sign(_pae(DSSE_PAYLOAD_TYPE, payload))
            env["signatures"].append({
                "keyid": self._keyid(),
                "keyid_label": self._keyid_label,
                "sig": base64.b64encode(sig).decode(),
                "publicKey": self.public_key_pem(),
                "key_custody": "own-metal Ed25519 (box secret store); self-signed, "
                               "NOT a C2PA-Trust-List CA cert",
            })
        return env


# --------------------------------------------------------------------------- #
# Sidecar build + verify                                                        #
# --------------------------------------------------------------------------- #
def build_credential(manifest: ContentCredentialManifest, signer: Optional[CredentialSigner] = None) -> dict:
    """Assemble the full sidecar credential object: manifest + DSSE envelope + an
    honest top-level trust hint. Does NOT write to disk (see write_sidecar)."""
    signer = signer or CredentialSigner()
    dsse = signer.sign_manifest(manifest)
    signed = bool(dsse["signatures"])
    return {
        "credential_type": MANIFEST_TYPE,
        "active_manifest": manifest.to_dict(),
        "dsse": dsse,
        "claim_sha256": sha256_bytes(_canon(manifest.claim())),
        "trust_hint": TRUST_SELF_SIGNED if signed else TRUST_STRUCTURAL_ONLY,
        "trust_hint_note": (
            "SELF_SIGNED: cryptographically valid own-key Ed25519, but NOT anchored to "
            "the C2PA Trust List (ITL froze 2026-01-01). NOT a 'green'."
            if signed else
            "STRUCTURAL-ONLY: unsigned. Structure present, NO cryptographic validation. "
            "NEVER displayed as a validated/green credential."
        ),
        "doctrine": DOCTRINE,
    }


def write_sidecar(asset_path: str, credential: dict) -> str:
    """Write the C2PA sidecar next to the asset as <asset>.c2pa.json. Returns the path.
    (c2patool can later EMBED the same claim as a JUMBF box in the asset itself.)"""
    out = asset_path + ".c2pa.json"
    with open(out, "w") as f:
        json.dump(credential, f, indent=2, default=str)
    return out


@dataclass
class VerifyResult:
    ok: bool                      # cryptographically + structurally consistent
    trust_level: str              # STRUCTURAL-ONLY | SELF_SIGNED | C2PA_TRUST_LIST | TAMPERED
    hash_ok: bool                 # asset bytes match the manifest hard binding
    signature_ok: Optional[bool]  # None when unsigned
    self_signed: bool
    reasons: list
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def verify(
    credential: dict,
    *,
    asset_path: Optional[str] = None,
    asset_bytes: Optional[bytes] = None,
    trust_list_pubkeys: Optional[list] = None,
) -> VerifyResult:
    """Verify a sidecar credential against the REAL asset bytes.

    Checks, in order:
      1. HARD BINDING: recompute sha256 of the asset; must equal manifest asset_hash.
      2. SIGNATURE: if a DSSE signature is present, verify Ed25519 over the DSSE PAE of
         the canonical claim. A tampered claim or wrong key => signature_ok False.
      3. TRUST LEVEL, reported HONESTLY:
           - no signature        => STRUCTURAL-ONLY (never a green)
           - hash or sig mismatch => TAMPERED (reject)
           - valid self-signed   => SELF_SIGNED (NOT C2PA-TL anchored)
           - key in trust_list_pubkeys (a stand-in for the C2PA Trust List) => C2PA_TRUST_LIST

    `trust_list_pubkeys`: optional list of PEM strings standing in for the C2PA Trust
    List anchors. In production this is the real conformant-CA chain check; here it is
    an explicit, honest allow-list so we can demonstrate the trust-level distinction.
    """
    reasons: list = []
    manifest = credential.get("active_manifest", {})
    claim = manifest.get("claim") or {}
    expected_hash = manifest.get("asset_hash") or claim.get("asset", {}).get("hash")

    # 1. Hard binding to real bytes.
    if asset_path is not None:
        actual_hash = sha256_file(asset_path)
    elif asset_bytes is not None:
        actual_hash = sha256_bytes(asset_bytes)
    else:
        raise ValueError("provide asset_path or asset_bytes to verify the hard binding")
    hash_ok = (actual_hash == expected_hash)
    if not hash_ok:
        reasons.append(
            f"HARD-BINDING MISMATCH: asset bytes hash {actual_hash} != manifest "
            f"{expected_hash} (asset modified after signing)."
        )

    # 2. Signature over the DSSE PAE of the canonical claim.
    dsse = credential.get("dsse", {})
    sigs = dsse.get("signatures", [])
    signature_ok: Optional[bool] = None
    self_signed = False
    signer_pub: Optional[str] = None

    if not sigs:
        reasons.append(
            "UNSIGNED: no DSSE signature present. Credential is STRUCTURAL-ONLY — "
            "structure only, NOT cryptographically validated. Never a green."
        )
    else:
        signature_ok = False
        self_signed = True  # our signer is always own-key/self-signed
        if not _CRYPTO:
            reasons.append("cryptography unavailable: cannot verify signature.")
        else:
            try:
                payload = base64.b64decode(dsse["payload"])
                # The signed claim MUST equal the manifest's current claim (tamper check).
                recomputed = _canon(claim)
                if payload != recomputed:
                    reasons.append(
                        "CLAIM TAMPERED: DSSE payload != canonical manifest claim "
                        "(manifest edited after signing)."
                    )
                sig_entry = sigs[0]
                sig = base64.b64decode(sig_entry["sig"])
                signer_pub = sig_entry.get("publicKey")
                pub = load_pem_public_key(signer_pub.encode())
                pae = _pae(dsse["payloadType"], payload)
                pub.verify(sig, pae)
                # Signature is valid over the DSSE payload; require payload==claim too.
                signature_ok = (payload == recomputed)
                if signature_ok:
                    reasons.append(
                        "Signature VALID: real Ed25519 over DSSE PAE of the canonical "
                        "claim (own-key)."
                    )
            except InvalidSignature:
                reasons.append("SIGNATURE INVALID: Ed25519 verification failed (tampered "
                               "or wrong key).")
            except Exception as e:  # malformed envelope
                reasons.append(f"signature check error: {e!r}")

    # 3. Honest trust level.
    if not sigs:
        trust_level = TRUST_STRUCTURAL_ONLY
        ok = hash_ok  # structurally consistent iff the bytes match; still NOT validated
    elif not hash_ok or not signature_ok:
        trust_level = TRUST_TAMPERED
        ok = False
    else:
        # Valid signature + matching bytes. Is the key a C2PA-Trust-List anchor?
        on_trust_list = False
        if trust_list_pubkeys and signer_pub:
            norm = {p.strip() for p in trust_list_pubkeys}
            on_trust_list = signer_pub.strip() in norm
        if on_trust_list:
            trust_level = TRUST_C2PA_TRUST_LIST
            self_signed = False
            reasons.append("Signer key is on the supplied C2PA Trust List anchor set.")
        else:
            trust_level = TRUST_SELF_SIGNED
            reasons.append(
                "SELF_SIGNED: valid own-key Ed25519, but NOT anchored to the C2PA Trust "
                "List (ITL froze 2026-01-01; self-signed no longer validates as trusted). "
                "Honest lower trust — NOT a green."
            )
        ok = True

    summary = (
        f"hard_binding={'OK' if hash_ok else 'MISMATCH'}; "
        f"signature={'n/a (unsigned)' if signature_ok is None else ('OK' if signature_ok else 'FAIL')}; "
        f"trust_level={trust_level}. "
        + ("A signature is NOT proof of safety (Doctrine v11); trust reported honestly.")
    )

    return VerifyResult(
        ok=ok,
        trust_level=trust_level,
        hash_ok=hash_ok,
        signature_ok=signature_ok,
        self_signed=self_signed,
        reasons=reasons,
        summary=summary,
    )


__all__ = [
    "CLAIM_GENERATOR_DEFAULT", "MANIFEST_TYPE", "DSSE_PAYLOAD_TYPE", "DOCTRINE", "CITATIONS",
    "DST_TRAINED_ALGORITHMIC", "DST_COMPOSITE_WITH_TRAINED", "DST_DIGITAL_CAPTURE",
    "DST_CREATIVE_WORK",
    "TRUST_STRUCTURAL_ONLY", "TRUST_SELF_SIGNED", "TRUST_C2PA_TRUST_LIST", "TRUST_TAMPERED",
    "sha256_file", "sha256_bytes",
    "Ingredient", "ContentCredentialManifest", "build_manifest",
    "CredentialSigner", "build_credential", "write_sidecar", "VerifyResult", "verify",
]


if __name__ == "__main__":
    # Demonstrate on a REAL asset in the workspace.
    import sys

    asset = sys.argv[1] if len(sys.argv) > 1 else (
        "/home/user/workspace/agentic_pinn/agentic_pinn_validation.png"
    )
    print("SZL C2PA CONTENT CREDENTIAL — real-asset demo\n" + "=" * 60)
    print(f"asset: {asset}")

    manifest = build_manifest(
        asset_path=asset,
        asset_title="agentic_pinn_validation.png",
        asset_format="image/png",
        ai_generated=True,
        model_id="szl/agentic-pinn-validator (matplotlib render of PINN solve)",
        claim_generator="szl-forge-charts/1.0.0",
        ingredients=[Ingredient(title="agentic_decision_trail.json",
                                asset_hash="sha256:(source-trail)", relationship="inputTo")],
    )
    signer = CredentialSigner()  # PLACEHOLDER unless SZL_C2PA_SIGNING_KEY is set
    cred = build_credential(manifest, signer)
    out = write_sidecar(asset, cred)
    res = verify(cred, asset_path=asset)
    print(f"asset_hash : {manifest.asset_hash}")
    print(f"ai_generated: {manifest.ai_generated} model_id={manifest.model_id}")
    print(f"signer mode: {signer.mode}")
    print(f"sidecar    : {out}")
    print(f"verify     : ok={res.ok} trust={res.trust_level}")
    print(res.summary)
