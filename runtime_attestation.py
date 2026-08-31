# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""runtime_attestation — SZL-NATIVE 3-AXIS RUNTIME ATTESTATION (GAP 4 closer).

THE GAP (GAPS.md GAP 4): provenance proves a build *happened*; it does NOT prove
the LIVE PROCESS is the attested one. The npm/TanStack lesson (CVE-2026-45321):
valid SLSA/Sigstore provenance signed real malware — a signature is NOT proof of
safety, and "signed at build" is NOT "attested at runtime". The frontier (RATS
RFC 9334, the IETF Agent-Trust-Negotiation draft, in-toto/SLSA) closes this with
THREE chained axes. We build the SZL-native, sovereign, own-metal version.

THE 3 AXES (ATN draft: build < build+model < all-three) -------------------------
  * BUILD  axis — reference our EXISTING SLSA/DSSE build provenance by digest
                  (in-toto Statement subject digest). Proves WHERE code came from.
  * MODEL  axis — a model-weight identity anchor: sha256 over the self-run model
                  identity (qwen2.5-coder we self-host) + sha256 of the system
                  prompt. Proves WHICH model + WHICH instructions are running.
  * RUNTIME axis — a SHORT-VALIDITY runtime receipt (issued_at / valid_until, on
                  the order of minutes — the ATN `valid_until` pattern) asserting
                  "THIS process is serving the attested build", BOUND to a real
                  live liveness signal (the a11oy PINN-cert / /healthz probe).
                  valid_until enforcement is REAL: expired => INVALID.

DOCTRINE v11 (HARD) -------------------------------------------------------------
More axes do NOT mean "proven trust". We label the result "ATTESTED" with the
present axes ENUMERATED — never "trusted", never "safe". An UNSIGNED envelope is
STRUCTURAL-ONLY (it carries claims but no cryptographic authenticity). NO axis is
ever fabricated: a missing axis is REPORTED as absent, not faked. The MODEL axis
in-sandbox hashes an HONESTLY-LABELLED stand-in model-id manifest, with a clearly
marked seam (`weight_sha256=None`, label "SEAM:FORGE-GPU-BOX") for Forge to fill
with the REAL safetensors weight hash on the GPU box. This mirrors our DSSE signer
(Ed25519, DSSEv1 PAE, cosign.pub-anchored) exactly.

RATS RFC 9334 mapping: the Attester (this process) produces Evidence (the 3-axis
attestation); a Relying Party appraises it via a Verifier (verify_attestation()).
We do NOT claim TEE-backed hardware Evidence — that is roadmap (see FINDINGS.md).

Pure stdlib + `cryptography` (Ed25519, already in our DSSE path). Sovereign,
own-metal, auditable. 0 runtime CDN.

Citations (cited, never claimed as SZL's):
  - IETF Agent Trust Negotiation draft — three chained trust axes
    (build SLSA/in-toto + model identity/weight hash + runtime RATS evidence);
    short-validity `valid_until`; ML-DSA optional PQ signature.
  - RATS RFC 9334 (Birkholz et al., 2023), doi:10.17487/RFC9334 — Attester /
    Evidence / Verifier / Relying Party remote-attestation architecture.
    https://datatracker.ietf.org/doc/html/rfc9334
  - in-toto / SLSA (slsa.dev/attestation-model, slsa.dev/provenance/v1) — DSSE
    envelope: payloadType + base64(payload) + signatures[{keyid,sig}]; in-toto
    Statement subject digest as the build anchor.
  - DSSE (Dead Simple Signing Envelope) v1 PAE — github.com/secure-systems-lab/dsse.
  - npm/TanStack SLSA-signed-malware CVE-2026-45321 — motivation: signed != safe.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Optional

try:  # mirror physics_bounds / our DSSE signer — Ed25519, same library
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization

    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover - honest degradation if lib absent
    _HAVE_CRYPTO = False


DOCTRINE = (
    "v11 LOCKED: runtime attestation is ATTESTED-WITH-AXES, NEVER 'proven trust' "
    "(a signature is not proof of safety — npm/TanStack CVE-2026-45321); axes are "
    "ENUMERATED honestly; a MISSING axis is REPORTED, never fabricated; the MODEL "
    "weight hash is a clearly-labelled SEAM until Forge fills the real safetensors "
    "hash on the GPU box; UNSIGNED envelope = STRUCTURAL-ONLY; valid_until is "
    "ENFORCED (expired => invalid); Λ=Conjecture 1 (advisory); sovereign own-metal; "
    "no fabricated numbers/signatures. RATS RFC 9334: we emit Evidence, not a TEE quote."
)

ATTRIBUTION = {
    "atn_draft": (
        "IETF Agent Trust Negotiation (ATN) draft — three chained trust axes: "
        "build (SLSA/in-toto) + model identity (weight hash) + runtime (RATS "
        "evidence); short-validity `valid_until`; trust grows with axes present "
        "(build-only < build+model < all-three). Cited, not claimed as SZL's."
    ),
    "rats_rfc9334": (
        "Birkholz, H., Thaler, D., Richardson, M., Smith, N., Pan, W. (2023), "
        "'Remote ATtestation procedureS (RATS) Architecture', RFC 9334, "
        "doi:10.17487/RFC9334. Attester produces Evidence; a Verifier appraises "
        "it for a Relying Party. https://datatracker.ietf.org/doc/html/rfc9334"
    ),
    "slsa_intoto": (
        "SLSA attestation model (slsa.dev/attestation-model) + SLSA Provenance v1 "
        "(slsa.dev/provenance/v1) + in-toto Statement: DSSE envelope wraps a "
        "base64 payload; subject.digest binds the artifact. Build axis anchor."
    ),
    "dsse": (
        "DSSE (Dead Simple Signing Envelope) v1 PAE — "
        "github.com/secure-systems-lab/dsse. payloadType + base64(payload) + "
        "signatures[{keyid,sig,publicKey}]; Ed25519 (ML-DSA optional, ATN PQ note)."
    ),
    "motivation_cve": (
        "npm/TanStack SLSA-signed-malware CVE-2026-45321 (CVSS 9.6, 633 npm "
        "versions, 2026-05-19): valid build provenance signed real malware. "
        "Signed-at-build is NOT attested-at-runtime; this engine closes that gap."
    ),
    "honesty": (
        "No axis is ever fabricated. A missing axis is reported as absent (not "
        "faked). The MODEL weight hash is a SEAM (None) until Forge fills the real "
        "safetensors hash on the GPU box. UNSIGNED = STRUCTURAL-ONLY. 'Attested' "
        "with axes enumerated — never 'trusted', never 'safe'. Λ advisory."
    ),
}

# Trust LEVELS — ATN's monotone ladder. Higher = MORE AXES PRESENT, explicitly NOT
# "more trustworthy in fact". Naming makes the doctrine impossible to misread.
TRUST_NONE = "NONE"                       # no axes
TRUST_BUILD_ONLY = "BUILD-ONLY"           # build axis only (weakest, == old provenance)
TRUST_BUILD_MODEL = "BUILD+MODEL"         # build + model
TRUST_ALL_THREE = "ALL-THREE-AXES"        # build + model + runtime (strongest STRUCTURE)

_AXIS_LADDER = {
    frozenset(): TRUST_NONE,
    frozenset({"build"}): TRUST_BUILD_ONLY,
    frozenset({"build", "model"}): TRUST_BUILD_MODEL,
    frozenset({"build", "model", "runtime"}): TRUST_ALL_THREE,
}
# Ordinal rank for "rises with axes" assertions (count of present canonical axes).
_LADDER_RANK = {
    TRUST_NONE: 0,
    TRUST_BUILD_ONLY: 1,
    TRUST_BUILD_MODEL: 2,
    TRUST_ALL_THREE: 3,
}


def _sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


# --------------------------------------------------------------------------- #
# AXIS 1 — BUILD (reference existing SLSA/DSSE build provenance by digest)     #
# --------------------------------------------------------------------------- #
@dataclass
class BuildAxis:
    """References our EXISTING SLSA/in-toto build provenance — does NOT re-sign it.

    `provenance_digest` is the sha256 of the already-signed DSSE build envelope
    (e.g. the physical-bounds certificate's `_cert_sha256` / a `.intoto.jsonl`
    subject digest). This axis asserts: 'the build provenance I point at exists
    and has this digest'. Proves WHERE code came from (RATS reference value).
    """

    provenance_digest: str            # sha256:... of the signed build envelope
    builder_id: str                   # SLSA builder identity (e.g. FA-001 on-metal)
    source_uri: str = ""              # in-toto subject / repo
    label: str = "MEASURED"           # MEASURED if the digest came from a real envelope
    present: bool = True

    def to_evidence(self) -> dict:
        return {
            "axis": "build",
            "present": self.present,
            "provenance_digest": self.provenance_digest,
            "builder_id": self.builder_id,
            "source_uri": self.source_uri,
            "label": self.label,
            "note": "References existing SLSA/in-toto DSSE provenance by digest "
                    "(slsa.dev/provenance/v1). Build-time only — NOT runtime proof.",
        }


# --------------------------------------------------------------------------- #
# AXIS 2 — MODEL (model-weight identity anchor + system-prompt hash)           #
# --------------------------------------------------------------------------- #
@dataclass
class ModelAxis:
    """Model-weight identity anchor for the self-run model (qwen2.5-coder).

    HONESTY SEAM: in-sandbox we have NO GPU and NO real safetensors file, so we
    DO NOT fabricate a weight hash. We hash an HONESTLY-LABELLED model-id manifest
    (model name/version/quant/params) — a stable *identity* anchor — and leave
    `weight_sha256=None` with `weight_seam` describing exactly what Forge must
    compute on the box (sha256 over the real weight shards). `system_prompt_sha256`
    binds the running instructions. Proves WHICH model + WHICH prompt are live.
    """

    model_id: str                     # e.g. "qwen2.5-coder:7b"
    model_manifest: dict              # name/version/quant/params — honest identity
    system_prompt_sha256: Optional[str] = None  # sha256 of the live system prompt
    weight_sha256: Optional[str] = None         # SEAM: real safetensors hash (Forge)
    weight_seam: str = (
        "SEAM:FORGE-GPU-BOX — compute sha256 over the real qwen2.5-coder weight "
        "shards (safetensors/gguf) on the sovereign GPU box and set weight_sha256. "
        "In-sandbox this is HONESTLY None (no weights present) — NOT fabricated."
    )
    label: str = "MODEL-IDENTITY-ANCHOR"  # identity anchor (manifest), not weights
    present: bool = True

    @property
    def manifest_sha256(self) -> str:
        """sha256 over the honestly-labelled model-id manifest (always computable)."""
        return _sha256_hex(_canon(self.model_manifest))

    def to_evidence(self) -> dict:
        return {
            "axis": "model",
            "present": self.present,
            "model_id": self.model_id,
            "manifest_sha256": self.manifest_sha256,
            "system_prompt_sha256": self.system_prompt_sha256,
            "weight_sha256": self.weight_sha256,        # None in-sandbox (honest)
            "weight_sha256_is_seam": self.weight_sha256 is None,
            "weight_seam": self.weight_seam,
            "label": self.label,
            "note": "Manifest hash is a MEASURED identity anchor; weight_sha256 is a "
                    "labelled SEAM until Forge fills the real GPU-box weight hash.",
        }


def hash_system_prompt(system_prompt: str) -> str:
    """sha256 of the live system prompt (binds running instructions to the receipt)."""
    return _sha256_hex(system_prompt.encode("utf-8"))


# --------------------------------------------------------------------------- #
# AXIS 3 — RUNTIME (short-validity receipt + live liveness-probe binding)      #
# --------------------------------------------------------------------------- #
@dataclass
class LivenessProbe:
    """A REAL live signal binding. Reads the a11oy PINN-cert (or /healthz) over
    urllib and records a sha256 over the response body + the source URL + status.
    On network failure we DO NOT fabricate a probe — `ok=False`, `label='FALLBACK'`,
    and the error is recorded honestly. The runtime receipt still issues, but its
    liveness binding is explicitly marked unbound.
    """

    source_url: str
    ok: bool
    status: Optional[int]
    body_sha256: Optional[str]
    probed_at: float
    label: str                        # LIVE | FALLBACK (honest)
    error: str = ""

    def to_evidence(self) -> dict:
        return asdict(self)


def probe_liveness(
    url: str = "https://a-11-oy.com/api/a11oy/v1/pinn/certificate",
    timeout: float = 6.0,
    _opener=None,
) -> LivenessProbe:
    """Bind a REAL live signal. Honest fallback on any failure (no fabrication)."""
    now = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "szl-runtime-attest/1"})
        opener = _opener or urllib.request.urlopen
        with opener(req, timeout=timeout) as resp:  # type: ignore[arg-type]
            body = resp.read()
            status = getattr(resp, "status", None) or resp.getcode()
        return LivenessProbe(
            source_url=url,
            ok=True,
            status=int(status),
            body_sha256=_sha256_hex(body),
            probed_at=now,
            label="LIVE",
        )
    except Exception as exc:  # honest fallback — NEVER fabricate a live signal
        return LivenessProbe(
            source_url=url,
            ok=False,
            status=None,
            body_sha256=None,
            probed_at=now,
            label="FALLBACK",
            error=f"{type(exc).__name__}: {exc}",
        )


@dataclass
class RuntimeAxis:
    """SHORT-VALIDITY runtime receipt — ATN `valid_until` pattern (minutes).

    Asserts: 'THIS process is serving the attested build' for a SHORT window.
    valid_until enforcement is REAL: see `is_expired()` / verification below.
    Bound to a real liveness probe (or honest FALLBACK).
    """

    process_id: int
    build_provenance_digest: str      # the build it claims to serve (== BuildAxis)
    issued_at: float
    valid_until: float                # short window — minutes, ATN pattern
    liveness: LivenessProbe
    assertion: str = "this process is serving the attested build"
    label: str = "RUNTIME-RECEIPT"
    present: bool = True

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return now > self.valid_until

    def to_evidence(self) -> dict:
        d = asdict(self)
        d["liveness"] = self.liveness.to_evidence()
        d["axis"] = "runtime"
        d["validity_seconds"] = self.valid_until - self.issued_at
        d["note"] = ("Short-validity receipt (ATN valid_until). Expired => INVALID. "
                     "Liveness is a REAL probe or honest FALLBACK — never fabricated.")
        return d


def make_runtime_receipt(
    build_provenance_digest: str,
    process_id: int,
    validity_seconds: float = 300.0,   # 5 minutes — short, ATN pattern
    liveness_url: str = "https://a-11-oy.com/api/a11oy/v1/pinn/certificate",
    issued_at: Optional[float] = None,
    liveness: Optional[LivenessProbe] = None,
) -> RuntimeAxis:
    issued = time.time() if issued_at is None else issued_at
    probe = liveness if liveness is not None else probe_liveness(liveness_url)
    return RuntimeAxis(
        process_id=process_id,
        build_provenance_digest=build_provenance_digest,
        issued_at=issued,
        valid_until=issued + float(validity_seconds),
        liveness=probe,
    )


# --------------------------------------------------------------------------- #
# COMPOSE — the 3-axis attestation (the in-toto/RATS Evidence payload)         #
# --------------------------------------------------------------------------- #
@dataclass
class RuntimeAttestation:
    """The composed Evidence. Trust-level is HIGHER when MORE axes are present
    (ATN ladder) — but labelled ATTESTED-WITH-AXES, NEVER 'proven trust'.
    """

    attestation_type: str
    build: Optional[BuildAxis]
    model: Optional[ModelAxis]
    runtime: Optional[RuntimeAxis]
    timestamp_utc: float
    doctrine: str = DOCTRINE
    attribution: dict = field(default_factory=lambda: ATTRIBUTION)
    lambda_note: str = (
        "Λ = Conjecture 1 (advisory). This is ATTESTED-WITH-AXES, NOT 'proven "
        "trust'. More axes = more structure, NOT more safety (CVE-2026-45321)."
    )
    signature: Optional[dict] = None   # filled by sign_dsse(); None => STRUCTURAL-ONLY

    # --- axes present (canonical, honest — never fabricated) ---
    def present_axes(self) -> list[str]:
        axes = []
        if self.build is not None and self.build.present:
            axes.append("build")
        if self.model is not None and self.model.present:
            axes.append("model")
        if self.runtime is not None and self.runtime.present:
            axes.append("runtime")
        return axes

    def trust_level(self) -> str:
        """ATN ladder. The runtime axis only 'counts' toward the TOP rung if the
        receipt is non-expired AND its build digest matches the build axis — an
        expired/mismatched runtime receipt does NOT lift you to ALL-THREE.
        """
        present = set(self.present_axes())
        # runtime only counts if currently valid and bound to the same build
        if "runtime" in present:
            r = self.runtime
            assert r is not None
            mismatched = (
                self.build is not None
                and r.build_provenance_digest != self.build.provenance_digest
            )
            if r.is_expired() or mismatched:
                present.discard("runtime")
        # model+runtime without build is not on the canonical ladder; clamp down.
        key = frozenset(present & {"build", "model", "runtime"})
        if key in _AXIS_LADDER:
            return _AXIS_LADDER[key]
        # off-ladder combos (e.g. model-only, runtime-only): rank by count honestly,
        # but never above what the canonical ladder would grant for that count.
        if "build" not in present:
            return TRUST_NONE if not present else TRUST_BUILD_ONLY  # weakest non-zero
        if "runtime" in present and "model" not in present:
            return TRUST_BUILD_ONLY  # build+runtime w/o model: not the full chain
        return TRUST_BUILD_ONLY

    def trust_rank(self) -> int:
        return _LADDER_RANK[self.trust_level()]

    def to_payload(self) -> dict:
        return {
            "attestation_type": self.attestation_type,
            "axes_present": self.present_axes(),
            "trust_level": self.trust_level(),
            "trust_level_meaning": "ATTESTED-WITH-AXES (NOT proven trust; "
                                   "more axes = more structure, not more safety)",
            "build": self.build.to_evidence() if self.build else {"axis": "build", "present": False, "note": "axis ABSENT (reported, not faked)"},
            "model": self.model.to_evidence() if self.model else {"axis": "model", "present": False, "note": "axis ABSENT (reported, not faked)"},
            "runtime": self.runtime.to_evidence() if self.runtime else {"axis": "runtime", "present": False, "note": "axis ABSENT (reported, not faked)"},
            "timestamp_utc": self.timestamp_utc,
            "doctrine": self.doctrine,
            "attribution": self.attribution,
            "lambda_note": self.lambda_note,
        }

    def to_json(self, indent: int = 2) -> str:
        d = self.to_payload()
        d["signature"] = self.signature
        d["signing_status"] = "SIGNED" if self.signature else "UNSIGNED=STRUCTURAL-ONLY"
        return json.dumps(d, indent=indent, default=str)


def compose(
    build: Optional[BuildAxis] = None,
    model: Optional[ModelAxis] = None,
    runtime: Optional[RuntimeAxis] = None,
) -> RuntimeAttestation:
    return RuntimeAttestation(
        attestation_type="szl/runtime-attestation/v1",
        build=build,
        model=model,
        runtime=runtime,
        timestamp_utc=time.time(),
    )


# --------------------------------------------------------------------------- #
# DSSE Ed25519 sign/verify — mirrors our physical-bounds DSSE signer exactly   #
# --------------------------------------------------------------------------- #
DSSE_PAYLOAD_TYPE = "application/vnd.szl.runtime-attestation+json"


def _pae(payload_type: str, payload: bytes) -> bytes:
    """DSSEv1 Pre-Authentication Encoding (github.com/secure-systems-lab/dsse)."""
    t = payload_type.encode()
    return b"DSSEv1 %d %b %d %b" % (len(t), t, len(payload), payload)


def sign_dsse(att: RuntimeAttestation, private_key: "Ed25519PrivateKey") -> dict:
    """Sign the attestation payload into a DSSE Ed25519 envelope (our pattern).

    Returns the DSSE envelope {payloadType, payload(b64), signatures:[{keyid,sig,
    publicKey}]} and ATTACHES a compact `signature` block onto the attestation,
    flipping it from STRUCTURAL-ONLY to SIGNED.
    """
    if not _HAVE_CRYPTO:  # pragma: no cover
        raise RuntimeError("cryptography (Ed25519) unavailable — cannot sign")
    payload = _canon(att.to_payload())
    pae = _pae(DSSE_PAYLOAD_TYPE, payload)
    sig = private_key.sign(pae)
    pub = private_key.public_key()
    pub_pem = pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    pub_raw = pub.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    keyid = _sha256_hex(pub_raw)
    sig_b64 = base64.b64encode(sig).decode()
    att.signature = {
        "alg": "ed25519",
        "pae": "DSSEv1",
        "keyid": keyid,
        "sig": sig_b64,
        "publicKey": pub_pem,
        "key_custody": "SEAM:FORGE — FA-001 on-metal Ed25519 (box secret store); "
                       "in-sandbox we sign with an EPHEMERAL test key (labelled).",
    }
    return {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [{"keyid": keyid, "sig": sig_b64, "publicKey": pub_pem}],
        "_dsse": "DSSEv1 PAE, alg=ed25519 (mirrors szl physical-bounds signer)",
    }


@dataclass
class VerifyResult:
    valid: bool
    structural_only: bool
    trust_level: str
    axes_present: list
    reasons: list
    signature_verified: bool

    def to_dict(self) -> dict:
        return asdict(self)


def verify_attestation(
    att: RuntimeAttestation,
    envelope: Optional[dict] = None,
    now: Optional[float] = None,
) -> VerifyResult:
    """RATS-style appraisal (the Verifier). Honest verdict, deny-by-default.

    Checks, in order:
      1. signature — if absent => STRUCTURAL-ONLY (valid=False, not authentic).
      2. DSSE Ed25519 verify over PAE (if envelope provided).
      3. runtime receipt valid_until — EXPIRED => INVALID (real enforcement).
      4. build<->runtime digest binding — mismatch => INVALID.
      5. model weight seam — reported (None weight hash is honest, not a failure).
      6. axes enumerated; trust_level computed from PRESENT axes only.
    """
    reasons: list[str] = []
    now = time.time() if now is None else now
    axes = att.present_axes()

    sig_verified = False
    structural_only = att.signature is None
    if structural_only:
        reasons.append("UNSIGNED => STRUCTURAL-ONLY (claims carried, NOT authentic)")
    elif envelope is not None and _HAVE_CRYPTO:
        try:
            payload = base64.b64decode(envelope["payload"])
            pae = _pae(envelope["payloadType"], payload)
            pub_pem = envelope["signatures"][0]["publicKey"].encode()
            pub = serialization.load_pem_public_key(pub_pem)
            assert isinstance(pub, Ed25519PublicKey)
            sig = base64.b64decode(envelope["signatures"][0]["sig"])
            pub.verify(sig, pae)
            # also confirm the payload matches the live attestation payload
            if payload != _canon(att.to_payload()):
                reasons.append("DSSE payload does NOT match attestation (tampered)")
            else:
                sig_verified = True
                reasons.append("DSSE Ed25519 signature VERIFIED over PAE")
        except Exception as exc:
            reasons.append(f"DSSE signature verification FAILED: {type(exc).__name__}")
    elif att.signature is not None:
        reasons.append("signature present but no envelope supplied — not re-verified")

    runtime_ok = True
    if att.runtime is not None and att.runtime.present:
        if att.runtime.is_expired(now):
            runtime_ok = False
            reasons.append("RUNTIME receipt EXPIRED (past valid_until) => INVALID")
        else:
            reasons.append("runtime receipt within valid_until window")
        if att.build is not None and (
            att.runtime.build_provenance_digest != att.build.provenance_digest
        ):
            runtime_ok = False
            reasons.append("BUILD<->RUNTIME digest MISMATCH => INVALID")
        if not att.runtime.liveness.ok:
            reasons.append("liveness probe FALLBACK (unbound live signal) — honest")

    if att.model is not None and att.model.present:
        if att.model.weight_sha256 is None:
            reasons.append("MODEL weight_sha256 is a SEAM (None) — honest, Forge fills")
        else:
            reasons.append("MODEL weight_sha256 present (Forge GPU-box hash)")

    # Honesty audit: no axis fabricated. A None/absent axis must be reported absent.
    for name, ax in (("build", att.build), ("model", att.model), ("runtime", att.runtime)):
        if ax is None:
            reasons.append(f"{name} axis ABSENT — reported, not faked")

    # valid = authentic signature AND runtime constraints hold (deny-by-default).
    valid = bool(sig_verified and runtime_ok and not structural_only)
    return VerifyResult(
        valid=valid,
        structural_only=structural_only,
        trust_level=att.trust_level(),
        axes_present=axes,
        reasons=reasons,
        signature_verified=sig_verified,
    )


# --------------------------------------------------------------------------- #
# Honest sample builders (clearly labelled — for demo / tests / Forge seam)    #
# --------------------------------------------------------------------------- #
def sample_build_axis(
    provenance_digest: str = "sha256:586cc6cdc81ca57e9f17f945c03df93fe2c0fa28b4400a2f3275512ebf0bb4b6",
) -> BuildAxis:
    """Anchors to the REAL published physical-bounds cert digest (_cert_sha256)."""
    return BuildAxis(
        provenance_digest=provenance_digest,
        builder_id="FA-001 on-metal (SZL sovereign GPU box)",
        source_uri="github.com/szl-holdings (in-toto subject)",
        label="MEASURED",
    )


def sample_model_axis() -> ModelAxis:
    """Honest model-id manifest for the self-run qwen2.5-coder. NO weight hash
    in-sandbox (seam left for Forge). system_prompt hashed honestly."""
    manifest = {
        "name": "qwen2.5-coder",
        "tag": "7b",
        "params_billion": 7.6,
        "quant": "as-served-on-box",
        "served_by": "SZL sovereign GPU box (betterwithage / RTX 5050 Laptop)",
        "label": "MODEL-ID-MANIFEST (honest identity; NOT the weight bytes)",
    }
    return ModelAxis(
        model_id="qwen2.5-coder:7b",
        model_manifest=manifest,
        system_prompt_sha256=hash_system_prompt(
            "SZL Λ-gate governor system prompt (placeholder; Forge binds live prompt)"
        ),
        weight_sha256=None,  # SEAM — honest
    )


def ephemeral_test_key():
    """Ephemeral Ed25519 key for in-sandbox signing tests (CLEARLY a test key)."""
    if not _HAVE_CRYPTO:  # pragma: no cover
        raise RuntimeError("cryptography unavailable")
    return Ed25519PrivateKey.generate()


__all__ = [
    "DOCTRINE", "ATTRIBUTION",
    "TRUST_NONE", "TRUST_BUILD_ONLY", "TRUST_BUILD_MODEL", "TRUST_ALL_THREE",
    "BuildAxis", "ModelAxis", "RuntimeAxis", "LivenessProbe", "RuntimeAttestation",
    "VerifyResult",
    "hash_system_prompt", "probe_liveness", "make_runtime_receipt", "compose",
    "sign_dsse", "verify_attestation", "DSSE_PAYLOAD_TYPE",
    "sample_build_axis", "sample_model_axis", "ephemeral_test_key",
]


if __name__ == "__main__":
    b = sample_build_axis()
    m = sample_model_axis()
    r = make_runtime_receipt(b.provenance_digest, process_id=1234, validity_seconds=300)
    att = compose(build=b, model=m, runtime=r)
    print("SZL 3-AXIS RUNTIME ATTESTATION (sample)\n" + "=" * 60)
    print("axes present :", att.present_axes())
    print("trust level  :", att.trust_level(), "(rank", att.trust_rank(), ")")
    print("liveness     :", r.liveness.label, "ok=", r.liveness.ok)
    if _HAVE_CRYPTO:
        env = sign_dsse(att, ephemeral_test_key())
        res = verify_attestation(att, envelope=env)
        print("signed/valid :", res.signature_verified, res.valid)
        for why in res.reasons:
            print("   -", why)
    print("=" * 60)
    print(att.to_json())
