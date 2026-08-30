# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""szl_attest — L6 CHAIN-OF-TITLE ATTESTATION ORGAN.

WHAT THIS IS
------------
The allodial claim ("the operator holds real title to this substrate, not a
rented tenancy") is only worth what a THIRD PARTY can check. This organ emits
that claim as a machine-checkable **in-toto v1 Statement**, DSSE-signs it with
the estate's existing cosign keypair (``szl_dsse``), structures it for
**Sigstore/Rekor** transparency-log inclusion, and evaluates it against an
explicit policy (mirrored in ``ops/szl_chain_of_title.rego``) that returns
PASSED / FAILED / UNKNOWN — never a fabricated pass.

    subject        = locked-8 kernel gitCommit  (+ sovereign weights sha256 IF
                     a real weights artifact is readable this request; honest
                     null otherwise — a subject is never invented)
    predicateType  = "https://szl.dev/chain-of-title/v1"
    predicate      = doctrine v11 · provenance · energy_measured[] ·
                     honesty_invariants · seal

LEADERS FUSED (cited prior art; SZL claims none of them as its own)
------------------------------------------------------------------
  * in-toto Attestation Framework — Statement/v1 envelope + subject/predicate
    split. https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
  * SLSA v1.1 (Apr 2025) — Build L0-L3 track + Verification Summary Attestation
    (a verifier saying "this passed policy P"). https://slsa.dev/spec/v1.1/
    and https://slsa.dev/spec/v1.1/verification_summary
  * Sigstore / cosign keyless + Rekor transparency log — inclusion proof as the
    third-party-checkable anchor. https://docs.sigstore.dev/logging/overview/
  * DSSE (secure-systems-lab/dsse) — PAE signing envelope, via ``szl_dsse``.
    https://github.com/secure-systems-lab/dsse
  * sigstore/model-transparency — signing ML model weights as the subject.
    https://github.com/sigstore/model-transparency

WHAT MAKES IT SZL'S OWN (not a re-skin of the above)
----------------------------------------------------
  1. ``honesty_invariants`` are IN the signed predicate, so the doctrine itself
     becomes a cryptographically bound, third-party-checkable claim:
     no_fabricated_measured · lambda_is_conjecture_not_theorem ·
     locked8_immutable · provenance_coverage 1.0.
  2. The subject binds the **locked-8 kernel pin** (c7c0ba17) — the immutable
     8-formula proof kernel — not just a container digest.
  3. The verdict is TRI-STATE by construction. A missing transparency log is
     UNKNOWN, never PASSED. A tampered statement is FAILED, never UNKNOWN.
  4. Optional szl-lake receipt-on-write, so the attestation act itself lands in
     the estate ledger.

HONESTY (Doctrine v11 — binding)
--------------------------------
  * ``energy_measured`` is EMPTY unless a joule meter answered THIS request.
    No joule is ever invented.
  * ``rekor.status`` is RECORDED only with a real inclusion proof returned by a
    reachable log; UNREACHABLE / NOT_ATTEMPTED otherwise. No Rekor entry, log
    index, or inclusion proof is ever fabricated.
  * No signature is fabricated: with no ``SZL_COSIGN_PRIVATE_PEM`` runtime
    secret, ``szl_dsse`` emits an explicitly UNSIGNED envelope and this organ
    reports ``signature.status = "UNSIGNED-NO-KEY"``.
  * Λ = **Conjecture 1** — advisory, never a theorem, never green.
  * locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17 — this organ adds
    NOTHING to it and proves nothing new about it; it only ATTESTS the pin.
  * Surface label: MODELED. It would be MEASURED only for the transparency
    strand, and only when a real Rekor inclusion proof came back this request.
  * The seal formula is tier PROPOSED (EU CSF SEAL + HHI prior art), never
    presented as a validated metric.

Pure stdlib. No new dependency. Never raises into a request path.

Routes (registered additively, BEFORE the SPA catch-all):
    GET  /api/<ns>/v1/attest/manifest        — statement + envelope + policy verdict
    GET  /api/<ns>/v1/attest/verify          — verify the freshly built statement
    POST /api/<ns>/v1/attest/verify          — verify a caller-supplied envelope/statement
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Constants — the frozen vocabulary of this organ.
# --------------------------------------------------------------------------- #
SCHEMA = "szl.attest.chain-of-title/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://szl.dev/chain-of-title/v1"
PAYLOAD_TYPE = "application/vnd.in-toto+json"

DOCTRINE_VERSION = "v11"
KERNEL_PIN = "c7c0ba17"
LOCKED_8 = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
TRUST_CEILING = 0.97

SUBJECT_KERNEL_NAME = "locked8_kernel"
SUBJECT_WEIGHTS_NAME = "sovereign_weights"

LABEL_MODELED = "MODELED"
LABEL_MEASURED = "MEASURED"

VERDICT_PASSED = "PASSED"
VERDICT_FAILED = "FAILED"
VERDICT_UNKNOWN = "UNKNOWN"

REKOR_RECORDED = "RECORDED"
REKOR_UNREACHABLE = "UNREACHABLE"
REKOR_NOT_ATTEMPTED = "NOT_ATTEMPTED"

# Public Rekor instance. Only contacted when SZL_REKOR_ENABLE is truthy — the
# estate never reaches out on a plain read by default.
DEFAULT_REKOR_URL = "https://rekor.sigstore.dev"
REKOR_URL_ENV = "SZL_REKOR_URL"
REKOR_ENABLE_ENV = "SZL_REKOR_ENABLE"
REKOR_TIMEOUT_ENV = "SZL_REKOR_TIMEOUT_S"
REQUIRE_TRANSPARENCY_ENV = "SZL_ATTEST_REQUIRE_REKOR"
WEIGHTS_PATH_ENV = "SZL_SOVEREIGN_WEIGHTS_PATH"
CORPUS_PATH_ENV = "SZL_SOVEREIGN_CORPUS_PATH"
JOULE_METER_ENV = "A11OY_JOULE_METER_URLS"
LAKE_DIR_ENV = "SZL_LAKE_DIR"

ROOT = Path(__file__).resolve().parent

# Candidate sovereign-weights artifacts, in resolution order. Absent = honest
# null; a weights subject is NEVER invented.
_WEIGHTS_CANDIDATES = (
    "sovereign-weights/out-lora-szl/adapter_model.safetensors",
    "sovereign-weights/out-lora-szl/adapter_model.bin",
    "sovereign-weights/adapter_model.safetensors",
)
_CORPUS_CANDIDATES = (
    ("sovereign-weights/corpus.jsonl", "corpus"),
    ("corpus.jsonl", "corpus"),
    ("sovereign-weights/corpus_template.jsonl", "corpus_template"),
)

CITES = [
    "in-toto Attestation Framework — Statement v1 — "
    "https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md",
    "SLSA v1.1 (Apr 2025) Build track L0-L3 — https://slsa.dev/spec/v1.1/levels",
    "SLSA v1.1 Verification Summary Attestation — "
    "https://slsa.dev/spec/v1.1/verification_summary",
    "Sigstore/Rekor transparency log — https://docs.sigstore.dev/logging/overview/",
    "DSSE (secure-systems-lab/dsse) — https://github.com/secure-systems-lab/dsse",
    "sigstore/model-transparency — https://github.com/sigstore/model-transparency",
]
SEAL_CITES = [
    "EU Cloud Sovereignty Framework 2025 (SEAL / SovScore assurance levels 0-4)",
    "Herfindahl-Hirschman Index (HHI) — dependency-concentration measure (DCI)",
]
SEAL_FORMULA = "A=[Σ wₖ·SEALₖ/4]×(1−DCI)×100"


# --------------------------------------------------------------------------- #
# Small deterministic helpers.
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> bytes:
    """Deterministic canonical JSON (sorted keys, tight separators, UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest_hex(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def _sha256_file(path: Path, *, chunk: int = 1 << 20) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                block = fh.read(chunk)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    except Exception:
        return None


def _safe_under_root(raw: str) -> Path | None:
    """Resolve a caller/env supplied path and refuse anything outside ROOT."""
    try:
        p = Path(raw)
        p = p if p.is_absolute() else (ROOT / p)
        p = p.resolve()
        p.relative_to(ROOT)
        return p
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Subject strand 1 — sovereign weights (honest null when absent).
# --------------------------------------------------------------------------- #
def sovereign_weights_digest() -> dict[str, Any]:
    """sha256 of the sovereign weights artifact, or an HONEST null.

    A trained-weights blob is not committed to this repo (it is an operator
    artifact). When none is readable this returns ``sha256: None`` with the
    reason spelled out — the attestation says "no weights subject THIS
    request", it does not invent one.
    """
    override = (os.environ.get(WEIGHTS_PATH_ENV) or "").strip()
    candidates: list[Path] = []
    if override:
        p = _safe_under_root(override)
        if p is not None:
            candidates.append(p)
    candidates.extend(ROOT / rel for rel in _WEIGHTS_CANDIDATES)

    for path in candidates:
        try:
            if not path.is_file():
                continue
        except Exception:
            continue
        sha = _sha256_file(path)
        if sha:
            try:
                rel = str(path.relative_to(ROOT))
            except Exception:
                rel = path.name
            return {
                "sha256": sha,
                "path": rel,
                "bytes": path.stat().st_size,
                "present": True,
                "note": "sha256 computed over the readable weights artifact this request",
            }
    return {
        "sha256": None,
        "path": None,
        "bytes": None,
        "present": False,
        "note": ("no sovereign-weights artifact readable this request (operator "
                 f"artifact, not committed; set {WEIGHTS_PATH_ENV} to bind one) — "
                 "honest null, no weights digest fabricated"),
    }


# --------------------------------------------------------------------------- #
# Subject strand 2 — the locked-8 kernel commit.
# --------------------------------------------------------------------------- #
def locked8_kernel_commit() -> dict[str, Any]:
    """The gitCommit the locked-8 proof kernel is pinned at.

    Doctrine v11 pins the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} at commit
    prefix ``c7c0ba17``. That pin — not the rolling build commit — is what the
    chain-of-title subject binds, because the pin is the immutable thing. The
    build commit is recorded separately in the provenance strand.
    """
    return {
        "gitCommit": KERNEL_PIN,
        "locked_proven": list(LOCKED_8),
        "locked_proven_count": len(LOCKED_8),
        "source": "doctrine-v11 locked-kernel pin (immutable)",
    }


def build_commit() -> dict[str, Any]:
    """Best-effort build commit, read from .git without shelling out.

    Reported honestly as ``null`` when the checkout metadata is unreadable (an
    image build strips .git). Never confused with the locked-8 kernel pin.
    """
    git = ROOT / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
    except Exception:
        return {"commit": None, "source": None,
                "note": "no readable .git/HEAD in this image — honest null"}
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        try:
            sha = (git / ref).read_text(encoding="utf-8").strip()
            return {"commit": sha, "source": f".git/{ref}", "note": None}
        except Exception:
            pass
        try:
            for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return {"commit": line.split(" ", 1)[0].strip(),
                            "source": ".git/packed-refs", "note": None}
        except Exception:
            pass
        return {"commit": None, "source": f".git/{ref}",
                "note": "ref present but unresolvable — honest null"}
    if re.fullmatch(r"[0-9a-f]{40}", head):
        return {"commit": head, "source": ".git/HEAD (detached)", "note": None}
    return {"commit": None, "source": ".git/HEAD",
            "note": "unrecognised HEAD form — honest null"}


# --------------------------------------------------------------------------- #
# Provenance strand.
# --------------------------------------------------------------------------- #
def corpus_sha() -> dict[str, Any]:
    """sha256 of the declared training corpus, or an honest null.

    ``kind`` distinguishes a real corpus from the committed TEMPLATE, so a
    template digest can never be read as a trained-corpus digest.
    """
    override = (os.environ.get(CORPUS_PATH_ENV) or "").strip()
    candidates: list[tuple[Path, str]] = []
    if override:
        p = _safe_under_root(override)
        if p is not None:
            candidates.append((p, "corpus"))
    candidates.extend((ROOT / rel, kind) for rel, kind in _CORPUS_CANDIDATES)

    for path, kind in candidates:
        try:
            if not path.is_file():
                continue
        except Exception:
            continue
        sha = _sha256_file(path)
        if sha:
            try:
                rel = str(path.relative_to(ROOT))
            except Exception:
                rel = path.name
            return {"sha256": sha, "path": rel, "kind": kind,
                    "note": ("template corpus digest — NOT a trained-corpus digest"
                             if kind == "corpus_template" else
                             "sha256 over the declared training corpus")}
    return {"sha256": None, "path": None, "kind": None,
            "note": "no training corpus readable this request — honest null"}


_TRAIN_SCRIPT = "sovereign-weights/train_lora.py"
_TRAIN_KNOBS = (
    ("base_model", "--base-model", str),
    ("lora_r", "--lora-r", int),
    ("lora_alpha", "--lora-alpha", int),
    ("lora_dropout", "--lora-dropout", float),
    ("per_device_batch", "--per-device-batch", int),
    ("grad_accum", "--grad-accum", int),
    ("max_seq_len", "--max-seq-len", int),
    ("epochs", "--epochs", float),
    ("learning_rate", "--learning-rate", float),
    ("seed", "--seed", int),
)


def training_config() -> dict[str, Any]:
    """The training configuration, READ from the committed trainer this request.

    Parsed out of ``sovereign-weights/train_lora.py``'s argparse defaults with
    a regex rather than hard-coded here, so the attestation cannot drift away
    from the script it claims to describe. Unreadable script → honest nulls.
    """
    path = ROOT / _TRAIN_SCRIPT
    out: dict[str, Any] = {
        "source": _TRAIN_SCRIPT,
        "source_sha256": None,
        "method": "LoRA (parameter-efficient fine-tune)",
        "config": {},
        "note": None,
    }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        out["note"] = ("committed trainer not readable this request — honest "
                       "nulls, no training configuration fabricated")
        out["config"] = {name: None for name, _, _ in _TRAIN_KNOBS}
        return out
    out["source_sha256"] = _sha256_file(path)
    for name, flag, caster in _TRAIN_KNOBS:
        m = re.search(
            re.escape(flag) + r"\"[^)]*?default\s*=\s*(\"[^\"]*\"|[0-9eE.+-]+)",
            text, re.S)
        value: Any = None
        if m:
            raw = m.group(1)
            try:
                value = raw.strip('"') if raw.startswith('"') else caster(raw)
            except Exception:
                value = None
        out["config"][name] = value
    out["note"] = ("argparse defaults read verbatim from the committed trainer; "
                   "an operator run may override any knob on the command line")
    return out


def kernel_verification() -> dict[str, Any]:
    """Verify the locked-8 kernel claim against the digest-verified registry.

    Real in-request verification (never a hard-coded True):
      1. ``szl_formula_registry`` loads with digest verification ON — it
         recomputes the canonical SHA-256 over the registry payload and
         re-asserts its structural invariants, raising on any drift.
      2. Every doctrine locked-8 id is COVERED by that registry.
      3. The registry's locked_proven set is not inflated beyond the locked-8.
      4. Λ is still ``CONJECTURE_1_ADVISORY`` — a promoted Λ invalidates the
         kernel claim outright.

    Any failed check, or an unreadable registry, yields ``verified: False`` with
    the reason recorded. There is no path to a fabricated True.
    """
    out: dict[str, Any] = {
        "verified": False,
        "kernel_pin": KERNEL_PIN,
        "locked_proven": list(LOCKED_8),
        "checks": {},
        "registry": None,
        "reason": None,
    }
    try:
        import szl_formula_registry as _reg
    except Exception as exc:
        out["reason"] = f"formula registry unreadable ({type(exc).__name__}) — not verified"
        return out
    try:
        basis = _reg.receipt_basis()
        covered = tuple(getattr(_reg, "EXPECTED_COVERED_IDS", ()))
        locked_ids = tuple(basis.get("locked_proven_ids") or ())
        checks = {
            "registry_digest_verified": bool(basis.get("formula_registry_digest")),
            "locked8_covered": all(fid in covered for fid in LOCKED_8),
            "locked_set_not_inflated": set(locked_ids).issubset(set(LOCKED_8)),
            "lambda_is_conjecture": str(basis.get("lambda_status", "")).startswith(
                "CONJECTURE_1"),
        }
        out["checks"] = checks
        out["registry"] = {
            "schema_version": basis.get("schema_version"),
            "registry_version": basis.get("registry_version"),
            "formula_registry_digest": basis.get("formula_registry_digest"),
            "digest_algorithm": basis.get("digest_algorithm"),
            "signature_status": basis.get("signature_status"),
            "registry_locked_proven_ids": list(locked_ids),
            "lambda_status": basis.get("lambda_status"),
        }
        out["verified"] = all(checks.values())
        if not out["verified"]:
            failed = sorted(k for k, v in checks.items() if not v)
            out["reason"] = "failed kernel checks: " + ", ".join(failed)
        return out
    except Exception as exc:
        out["reason"] = (f"kernel verification raised {type(exc).__name__} — "
                         "not verified (no fabricated pass)")
        return out


# --------------------------------------------------------------------------- #
# Energy strand — empty unless a meter answered THIS request.
# --------------------------------------------------------------------------- #
def energy_measured(*, opener: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (readings, disclosure). Readings are [] with no live meter.

    A joule is only ever recorded when a configured meter answered in this
    request. No meter configured, or an unreachable one, yields an EMPTY list —
    never a modelled or remembered joule dressed as MEASURED.
    """
    raw = (os.environ.get(JOULE_METER_ENV) or "").strip()
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    disclosure: dict[str, Any] = {
        "meters_configured": len(urls),
        "meter_env": JOULE_METER_ENV,
        "label": "STRUCTURAL-ONLY",
        "note": (f"no joule meter configured ({JOULE_METER_ENV} unset) — "
                 "energy_measured is honestly EMPTY; no joule fabricated"),
    }
    if not urls:
        return [], disclosure

    readings: list[dict[str, Any]] = []
    errors: list[str] = []
    timeout = 1.5
    for url in urls[:8]:
        try:
            if opener is not None:
                payload = opener(url, timeout)
            else:
                import urllib.request

                with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                    payload = json.loads(resp.read().decode("utf-8", "replace"))
            joules = payload.get("joules") if isinstance(payload, dict) else None
            if isinstance(joules, (int, float)):
                readings.append({
                    "meter": url,
                    "joules": float(joules),
                    "label": LABEL_MEASURED,
                    "read_at": _now_iso(),
                })
            else:
                errors.append(f"{url}: no numeric joules field")
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}")
    disclosure["errors"] = errors
    if readings:
        disclosure["label"] = LABEL_MEASURED
        disclosure["note"] = (f"{len(readings)} live joule reading(s) taken this "
                              "request from the configured meter(s)")
    else:
        disclosure["label"] = "STRUCTURAL-ONLY"
        disclosure["note"] = ("meter(s) configured but none answered with a joule "
                              "reading this request — energy_measured stays EMPTY, "
                              "no joule fabricated")
    return readings, disclosure


# --------------------------------------------------------------------------- #
# The in-toto v1 Statement.
# --------------------------------------------------------------------------- #
def build_statement(*, ns: str = "a11oy", opener: Any = None) -> dict[str, Any]:
    """Assemble the in-toto v1 Statement for the L6 chain-of-title claim."""
    weights = sovereign_weights_digest()
    kernel = locked8_kernel_commit()
    kern_v = kernel_verification()
    corpus = corpus_sha()
    training = training_config()
    build = build_commit()
    readings, energy_disclosure = energy_measured(opener=opener)

    # in-toto requires each subject to carry at least one digest. The kernel
    # subject always does (gitCommit). The weights subject is appended ONLY
    # when a real sha256 exists — an empty digest set is never emitted.
    subject: list[dict[str, Any]] = [{
        "name": SUBJECT_KERNEL_NAME,
        "digest": {"gitCommit": kernel["gitCommit"]},
        "annotations": {
            "locked_proven": kernel["locked_proven"],
            "pin_source": kernel["source"],
        },
    }]
    if weights["sha256"]:
        subject.append({
            "name": SUBJECT_WEIGHTS_NAME,
            "digest": {"sha256": weights["sha256"]},
            "annotations": {"path": weights["path"], "bytes": weights["bytes"]},
        })

    provenance_coverage = 1.0  # every field below is either a real read or an honest null

    predicate: dict[str, Any] = {
        "doctrine": DOCTRINE_VERSION,
        "provenance": {
            "corpus_sha": corpus["sha256"],
            "corpus_source": {"path": corpus["path"], "kind": corpus["kind"],
                              "note": corpus["note"]},
            "training": training,
            "kernel_verified": bool(kern_v["verified"]),
            "kernel_pin": KERNEL_PIN,
            "kernel_verification": kern_v,
            "build_commit": build,
            "sovereign_weights": weights,
            "provenance_coverage": provenance_coverage,
            "coverage_rule": ("every provenance field is either a real read this "
                             "request or an explicit null with its reason — coverage "
                             "1.0 means fully DISCLOSED, not fully populated"),
        },
        # HONEST EMPTY when no meter answered this request. Never a fabricated joule.
        "energy_measured": readings,
        "energy_disclosure": energy_disclosure,
        "honesty_invariants": {
            "no_fabricated_measured": True,
            "lambda_is_conjecture_not_theorem": True,
            "locked8_immutable": True,
            "provenance_coverage": provenance_coverage,
        },
        "honesty_invariants_meaning": {
            "no_fabricated_measured": ("a MEASURED label is emitted only from a live "
                                       "reading in the same request; energy_measured "
                                       "is empty rather than invented"),
            "lambda_is_conjecture_not_theorem": ("Λ is Conjecture 1 — advisory, never "
                                                 "a theorem, never green"),
            "locked8_immutable": ("locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ "
                                  f"{KERNEL_PIN}; this organ adds nothing to it"),
            "provenance_coverage": ("1.0 — every provenance field disclosed, nulls "
                                    "included, none omitted"),
        },
        "seal": {
            "formula": SEAL_FORMULA,
            "tier": "PROPOSED",
            "cites": list(SEAL_CITES),
            "note": ("weights need calibration; the score is an engineering "
                     "composition of cited prior art, not a validated metric, and "
                     "no score is asserted here"),
        },
        "lambda": {
            "status": "Conjecture 1",
            "is_theorem": False,
            "trust_ceiling": TRUST_CEILING,
        },
        "attestation": {
            "schema": SCHEMA,
            "namespace": ns,
            "label": LABEL_MODELED,
            "built_at": _now_iso(),
            "cites": list(CITES),
            "slsa": {
                "build_track": "L0-L3 referenced as the cited direction; no SLSA "
                               "level is CLAIMED for this image",
                "vsa": "this Statement is the SZL analogue of a SLSA v1.1 "
                       "Verification Summary Attestation over the policy in "
                       "ops/szl_chain_of_title.rego",
            },
        },
    }

    return {
        "_type": STATEMENT_TYPE,
        "subject": subject,
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate,
    }


# --------------------------------------------------------------------------- #
# DSSE signing (reuses szl_dsse — the estate is DSSE-LIVE).
# --------------------------------------------------------------------------- #
def sign_statement(statement: dict[str, Any]) -> dict[str, Any]:
    """DSSE-sign the Statement with the estate cosign key via ``szl_dsse``.

    payloadType is the in-toto media type, so the envelope is byte-compatible
    with ``cosign verify-blob`` / ``cosign verify-attestation``. With no runtime
    private key the envelope is explicitly UNSIGNED — never a fake signature.
    """
    try:
        import szl_dsse
    except Exception as exc:  # pragma: no cover — dsse is in-image
        return {
            "payloadType": PAYLOAD_TYPE,
            "payload": None,
            "signatures": [],
            "signed": False,
            "honesty": f"szl_dsse unavailable ({type(exc).__name__}) — no envelope, "
                       "no fabricated signature",
        }
    env = szl_dsse.sign_payload(statement, PAYLOAD_TYPE)
    env["_statement_digest_sha256"] = digest_hex(statement)
    return env


def signature_status(envelope: dict[str, Any]) -> dict[str, Any]:
    """Honest signature verdict for an envelope. Never raises."""
    out: dict[str, Any] = {
        "signed": bool(envelope.get("signed")),
        "verified": None,
        "status": "UNSIGNED-NO-KEY",
        "keyless_ready": True,
        "note": None,
    }
    if not envelope.get("signatures"):
        out["note"] = (envelope.get("honesty")
                       or "no signature present; no signature fabricated")
        return out
    try:
        import szl_dsse

        verdict = szl_dsse.verify_envelope(envelope)
        out["verified"] = bool(verdict.get("verified"))
        out["status"] = "VERIFIED" if out["verified"] else "SIGNATURE-INVALID"
        out["keyid_expected"] = verdict.get("keyid_expected")
        out["pub_fingerprint_sha256"] = verdict.get("pub_fingerprint_sha256")
        out["note"] = ("ECDSA-P256-SHA256 over the DSSE PAE; also checkable by "
                       "`cosign verify-blob --key cosign.pub`")
    except Exception as exc:
        out["verified"] = None
        out["status"] = "UNKNOWN-VERIFIER-ERROR"
        out["note"] = f"verifier raised {type(exc).__name__} — UNKNOWN, not a pass"
    return out


# --------------------------------------------------------------------------- #
# Rekor transparency log — HONEST GUARDED CALL.
# --------------------------------------------------------------------------- #
def _rekor_configured() -> tuple[bool, str]:
    url = (os.environ.get(REKOR_URL_ENV) or DEFAULT_REKOR_URL).rstrip("/")
    enabled = str(os.environ.get(REKOR_ENABLE_ENV, "")).strip().lower() in (
        "1", "true", "yes", "on")
    return enabled, url


def rekor_submit(envelope: dict[str, Any], *, submitter: Any = None) -> dict[str, Any]:
    """Structure the envelope for Rekor and submit it IF submission is enabled.

    Tri-state, by construction:
      * RECORDED       — the log answered with a real entry carrying an
                         inclusion proof / log index. Only then is anything
                         recorded, and it is recorded VERBATIM.
      * UNREACHABLE    — submission was attempted and failed (offline sandbox,
                         DNS, timeout, non-2xx, unparseable body).
      * NOT_ATTEMPTED  — submission is not enabled in this runtime.

    There is NO branch that writes a log index, UUID, or inclusion proof that
    the log did not return. ``submitter`` is an injection seam for tests; the
    default path uses urllib.
    """
    enabled, url = _rekor_configured()
    proposed = {
        "kind": "intoto",
        "apiVersion": "0.0.2",
        "spec": {
            "content": {
                "envelope": {
                    "payloadType": envelope.get("payloadType"),
                    "payloadSha256": envelope.get("_statement_digest_sha256"),
                    "signatures": len(envelope.get("signatures") or []),
                },
                "hash": {"algorithm": "sha256",
                         "value": envelope.get("_statement_digest_sha256")},
            },
        },
    }
    out: dict[str, Any] = {
        "status": REKOR_NOT_ATTEMPTED,
        "log_url": url,
        "attempted": False,
        "reachable": None,
        "log_index": None,
        "entry_uuid": None,
        "inclusion_proof": None,
        "integrated_time": None,
        "proposed_entry": proposed,
        "label": "STRUCTURAL-ONLY",
        "cite": "Sigstore Rekor — https://docs.sigstore.dev/logging/overview/",
        "note": None,
    }
    if not envelope.get("signatures"):
        out["note"] = ("envelope is UNSIGNED (no runtime cosign secret) — nothing "
                       "submitted; a transparency-log entry is never fabricated. "
                       "Structured for cosign keyless + Rekor upload once a key or "
                       "an OIDC identity is present.")
        return out
    if not enabled:
        out["note"] = (f"Rekor submission not enabled in this runtime "
                       f"({REKOR_ENABLE_ENV} unset) — NOT_ATTEMPTED, never a "
                       "fabricated inclusion proof")
        return out

    out["attempted"] = True
    try:
        timeout = float(os.environ.get(REKOR_TIMEOUT_ENV, "3") or 3)
    except Exception:
        timeout = 3.0
    body = canonical_json({"apiVersion": proposed["apiVersion"],
                           "kind": proposed["kind"],
                           "spec": proposed["spec"]})
    try:
        if submitter is not None:
            payload = submitter(url, body, timeout)
        else:
            import urllib.request

            req = urllib.request.Request(  # noqa: S310
                url + "/api/v1/log/entries", data=body,
                headers={"Content-Type": "application/json",
                         "Accept": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:
        out["status"] = REKOR_UNREACHABLE
        out["reachable"] = False
        out["note"] = (f"Rekor unreachable ({type(exc).__name__}) — transparency "
                       "strand is UNKNOWN; no entry, log index, or inclusion proof "
                       "fabricated")
        return out

    entry = _first_rekor_entry(payload)
    proof = (entry or {}).get("verification", {}).get("inclusionProof")
    log_index = (entry or {}).get("logIndex")
    if not entry or proof is None or log_index is None:
        out["status"] = REKOR_UNREACHABLE
        out["reachable"] = True
        out["note"] = ("log answered but returned no inclusion proof / log index — "
                       "transparency strand stays UNKNOWN rather than claim inclusion")
        return out

    out["status"] = REKOR_RECORDED
    out["reachable"] = True
    out["label"] = LABEL_MEASURED
    out["log_index"] = log_index
    out["entry_uuid"] = entry.get("_uuid")
    out["integrated_time"] = entry.get("integratedTime")
    out["inclusion_proof"] = proof
    out["note"] = ("real inclusion proof returned by the transparency log this "
                   "request, recorded verbatim")
    return out


def _first_rekor_entry(payload: Any) -> dict[str, Any] | None:
    """Rekor returns {uuid: entry}. Pull the first entry, tagging its uuid."""
    if isinstance(payload, dict):
        for uuid, entry in payload.items():
            if isinstance(entry, dict):
                out = dict(entry)
                out["_uuid"] = entry.get("uuid") or uuid
                return out
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return dict(payload[0])
    return None


# --------------------------------------------------------------------------- #
# Policy evaluation — the Python twin of ops/szl_chain_of_title.rego.
# --------------------------------------------------------------------------- #
POLICY_RULES = (
    "predicate_type_matches",
    "doctrine_is_v11",
    "kernel_verified",
    "honesty_invariants_all_true",
    "provenance_coverage_is_one",
    "subject_binds_kernel_commit",
)
POLICY_PATH = "ops/szl_chain_of_title.rego"
POLICY_PACKAGE = "szl.attest.chain_of_title"


def evaluate_policy(statement: Any) -> dict[str, Any]:
    """Evaluate the chain-of-title policy over a Statement.

    Deliberately mirrors ``ops/szl_chain_of_title.rego`` rule for rule so an
    external OPA evaluation and this in-process evaluation agree. Returns
    PASSED only when EVERY rule holds; any failure is FAILED with the failing
    rule names named out loud.
    """
    checks: dict[str, bool] = {k: False for k in POLICY_RULES}
    if not isinstance(statement, dict):
        return {"policy": VERDICT_FAILED, "checks": checks,
                "failed": list(POLICY_RULES),
                "reason": "statement is not a JSON object",
                "rego": {"path": POLICY_PATH, "package": POLICY_PACKAGE}}

    predicate = statement.get("predicate")
    predicate = predicate if isinstance(predicate, dict) else {}
    provenance = predicate.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    inv = predicate.get("honesty_invariants")
    inv = inv if isinstance(inv, dict) else {}

    checks["predicate_type_matches"] = statement.get("predicateType") == PREDICATE_TYPE
    checks["doctrine_is_v11"] = predicate.get("doctrine") == DOCTRINE_VERSION
    checks["kernel_verified"] = provenance.get("kernel_verified") is True
    checks["honesty_invariants_all_true"] = (
        inv.get("no_fabricated_measured") is True
        and inv.get("lambda_is_conjecture_not_theorem") is True
        and inv.get("locked8_immutable") is True
        and inv.get("provenance_coverage") == 1.0
    )
    checks["provenance_coverage_is_one"] = provenance.get("provenance_coverage") == 1.0

    subjects = statement.get("subject")
    subjects = subjects if isinstance(subjects, list) else []
    kernel_bound = False
    for s in subjects:
        if not isinstance(s, dict) or s.get("name") != SUBJECT_KERNEL_NAME:
            continue
        digest = s.get("digest")
        commit = digest.get("gitCommit") if isinstance(digest, dict) else None
        if isinstance(commit, str) and commit.strip():
            kernel_bound = True
            break
    checks["subject_binds_kernel_commit"] = kernel_bound

    failed = [k for k, v in checks.items() if not v]
    return {
        "policy": VERDICT_PASSED if not failed else VERDICT_FAILED,
        "checks": checks,
        "failed": failed,
        "reason": None if not failed else "failed policy rules: " + ", ".join(failed),
        "rego": {"path": POLICY_PATH, "package": POLICY_PACKAGE,
                 "rule": "passed",
                 "note": "in-process evaluation mirrors the Rego policy rule for rule"},
    }


# --------------------------------------------------------------------------- #
# Verify — the tri-state verdict.
# --------------------------------------------------------------------------- #
def _require_transparency_default() -> bool:
    return str(os.environ.get(REQUIRE_TRANSPARENCY_ENV, "")).strip().lower() in (
        "1", "true", "yes", "on")


def _statement_from(payload: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Accept a Statement, a DSSE envelope, or {statement}/{envelope}.

    Returns (statement, envelope, error).
    """
    import base64

    if not isinstance(payload, dict):
        return None, None, "body must be a JSON object"
    if isinstance(payload.get("envelope"), dict):
        payload = payload["envelope"]
    elif isinstance(payload.get("statement"), dict):
        stmt = payload["statement"]
        return stmt, None, None
    if payload.get("payload") and payload.get("payloadType"):
        try:
            body = base64.b64decode(payload["payload"])
            stmt = json.loads(body.decode("utf-8"))
        except Exception:
            return None, payload, "envelope payload is not decodable JSON"
        if not isinstance(stmt, dict):
            return None, payload, "envelope payload is not a JSON object"
        return stmt, payload, None
    if payload.get("_type") or payload.get("predicateType"):
        return payload, None, None
    return None, None, "no in-toto Statement or DSSE envelope found in the body"


def verify(statement: Any, *, envelope: dict[str, Any] | None = None,
           require_transparency: bool | None = None,
           rekor: dict[str, Any] | None = None,
           submitter: Any = None) -> dict[str, Any]:
    """Tri-state verification of a chain-of-title Statement.

      FAILED  — the policy failed, or a present signature did not verify. A
                tampered statement is always FAILED, never UNKNOWN.
      UNKNOWN — the policy passed but a REQUIRED transparency-log inclusion
                proof could not be obtained (Rekor unreachable / not attempted).
      PASSED  — the policy passed and, when transparency is required, a real
                inclusion proof came back this request.

    ``verdict_scope`` always states what the verdict covers, so a policy-only
    PASSED is never mistaken for a transparency-anchored one.
    """
    if require_transparency is None:
        require_transparency = _require_transparency_default()

    policy = evaluate_policy(statement)
    sig = signature_status(envelope) if isinstance(envelope, dict) else {
        "signed": False, "verified": None, "status": "NO-ENVELOPE-SUPPLIED",
        "note": "verification ran over a bare Statement; no signature claimed",
    }
    if rekor is None:
        rekor = (rekor_submit(envelope, submitter=submitter)
                 if isinstance(envelope, dict)
                 else {"status": REKOR_NOT_ATTEMPTED, "attempted": False,
                       "reachable": None, "inclusion_proof": None,
                       "label": "STRUCTURAL-ONLY",
                       "note": "no envelope supplied — nothing to submit"})

    transparency_ok = rekor.get("status") == REKOR_RECORDED

    reasons: list[str] = []
    if policy["policy"] == VERDICT_FAILED:
        verdict = VERDICT_FAILED
        reasons.append(policy["reason"] or "policy failed")
    elif sig.get("status") == "SIGNATURE-INVALID":
        verdict = VERDICT_FAILED
        reasons.append("DSSE signature present but did not verify (tamper)")
    elif sig.get("status") == "UNKNOWN-VERIFIER-ERROR":
        verdict = VERDICT_UNKNOWN
        reasons.append("signature verifier error — UNKNOWN, not a pass")
    elif require_transparency and not transparency_ok:
        verdict = VERDICT_UNKNOWN
        reasons.append("transparency-log inclusion required but "
                       f"{rekor.get('status')} — UNKNOWN, never a fabricated PASSED")
    else:
        verdict = VERDICT_PASSED

    if verdict == VERDICT_PASSED and not transparency_ok:
        scope = ("policy-only: every chain-of-title policy rule holds; the "
                 "transparency-log strand is UNKNOWN this request and is NOT "
                 "part of this verdict")
    elif verdict == VERDICT_PASSED:
        scope = ("policy + transparency: policy rules hold AND a real Rekor "
                 "inclusion proof was returned this request")
    else:
        scope = "; ".join(reasons)

    return {
        "ok": True,
        "schema": SCHEMA,
        "verdict": verdict,
        "verdict_scope": scope,
        "policy": policy,
        "signature": sig,
        "transparency": {
            "required": bool(require_transparency),
            "status": rekor.get("status"),
            "label": rekor.get("label", "STRUCTURAL-ONLY"),
            "log_index": rekor.get("log_index"),
            "entry_uuid": rekor.get("entry_uuid"),
            "inclusion_proof": rekor.get("inclusion_proof"),
            "note": rekor.get("note"),
        },
        "reasons": reasons,
        "label": LABEL_MEASURED if transparency_ok else LABEL_MODELED,
        "label_rule": ("MEASURED only when a real transparency-log inclusion proof "
                       "was returned THIS request; MODELED otherwise"),
        "lambda": {"status": "Conjecture 1", "is_theorem": False,
                   "trust_ceiling": TRUST_CEILING},
        "verified_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Manifest — statement + envelope + rekor + verdict in one read.
# --------------------------------------------------------------------------- #
def build_manifest(*, ns: str = "a11oy", require_transparency: bool | None = None,
                   submitter: Any = None, opener: Any = None) -> dict[str, Any]:
    """Build, sign, structure-for-Rekor and self-verify in one pure read."""
    statement = build_statement(ns=ns, opener=opener)
    envelope = sign_statement(statement)
    rekor = rekor_submit(envelope, submitter=submitter)
    verdict = verify(statement, envelope=envelope, rekor=rekor,
                     require_transparency=require_transparency)
    return {
        "ok": True,
        "schema": SCHEMA,
        "label": verdict["label"],
        "statement": statement,
        "statement_digest_sha256": digest_hex(statement),
        "envelope": envelope,
        "rekor": rekor,
        "verdict": verdict["verdict"],
        "verdict_scope": verdict["verdict_scope"],
        "verification": verdict,
        "policy_source": {"path": POLICY_PATH, "package": POLICY_PACKAGE,
                          "rules": list(POLICY_RULES)},
        "cites": list(CITES),
        "honest_note": (
            "This is a chain-of-title ATTESTATION, not a proof of correctness. It "
            "binds what is actually readable this request and says so when a strand "
            "is absent: no weights digest without weights, no joule without a meter, "
            "no Rekor entry without a log answer. Λ stays Conjecture 1; the locked-8 "
            "is attested, never extended; the SEAL score is tier PROPOSED."),
        "built_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# szl-lake receipt (opt-in, guarded, off the hot path).
# --------------------------------------------------------------------------- #
def lake_receipt(manifest: dict[str, Any]) -> dict[str, Any]:
    """Append an attestation receipt to the szl-lake ledger, IF configured.

    Opt-in on ``SZL_LAKE_DIR`` so a plain read never writes to disk. Guarded:
    a lake failure is reported, never raised into the request.
    """
    if not (os.environ.get(LAKE_DIR_ENV) or "").strip():
        return {"appended": False, "status": "NOT_CONFIGURED",
                "note": f"{LAKE_DIR_ENV} unset — no ledger write on a read path"}
    receipt = {
        "organ": "attest",
        "id": manifest.get("statement_digest_sha256"),
        "ts": manifest.get("built_at"),
        "schema": SCHEMA,
        "verdict": manifest.get("verdict"),
        "label": manifest.get("label"),
        "predicate_type": PREDICATE_TYPE,
        "kernel_pin": KERNEL_PIN,
        "rekor_status": (manifest.get("rekor") or {}).get("status"),
        "signed": bool((manifest.get("envelope") or {}).get("signed")),
        # energy is omitted rather than zero-filled — szl_lake_store labels an
        # absent reading UNAVAILABLE, which is the honest state here.
    }
    try:
        import szl_lake_store

        store = szl_lake_store.LakeStore()
        res = store.append(receipt)
        return {"appended": bool(res.get("accepted")), "status": "APPENDED",
                "receipt_id": res.get("receipt_id"),
                "chain_index": res.get("chain_index"),
                "chain_head": res.get("chain_head")}
    except Exception as exc:
        print(f"[attest] lake receipt skipped (guarded): {type(exc).__name__}",
              file=sys.stderr)
        return {"appended": False, "status": "UNAVAILABLE",
                "note": f"lake append failed ({type(exc).__name__}) — not fabricated"}


# --------------------------------------------------------------------------- #
# FastAPI registration.
#
# GET  manifest / verify  and  POST verify. All three are raw-Request handlers
# so the POST is version-proof under fastapi==0.137.x (Starlette passes the
# Request positionally); ``request`` is annotated as ``fastapi.Request`` for the
# add_api_route fallback path.
#
# ROUTE-ORDER GOTCHA: szl_attest_stack already owns the PARAMETRIZED route
# /api/<ns>/v1/attest/{receipt_hash}, which would otherwise swallow "manifest"
# and "verify" as a receipt hash. So these STATIC routes are inserted BEFORE the
# first parametrized /attest/ route (the proven szl_attested_inference pattern),
# and in any case before the SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/attest"

    def _truthy(v: Any) -> bool:
        return str(v or "").strip().lower() in ("1", "true", "yes", "on")

    def _require_flag(request) -> bool | None:
        try:
            raw = request.query_params.get("require_transparency")
        except Exception:
            return None
        if raw is None:
            return None
        return _truthy(raw)

    async def _h_manifest(request):
        """GET manifest — build + sign + structure-for-Rekor + self-verify."""
        try:
            man = build_manifest(ns=ns, require_transparency=_require_flag(request))
            man["lake"] = lake_receipt(man)
            return JSONResponse(man)
        except Exception as exc:  # never 500 into the console
            return JSONResponse({
                "ok": False, "schema": SCHEMA, "label": LABEL_MODELED,
                "verdict": VERDICT_UNKNOWN,
                "verdict_scope": f"manifest build error ({type(exc).__name__}) — "
                                 "UNKNOWN, never a fabricated PASSED",
            }, status_code=200)

    async def _h_verify(request):
        """GET/POST verify — PASSED / FAILED honestly, UNKNOWN when unreachable."""
        try:
            body: Any = None
            if request.method == "POST":
                try:
                    body = await request.json()
                except Exception:
                    body = None
            require = _require_flag(request)
            if body is None:
                statement = build_statement(ns=ns)
                envelope = sign_statement(statement)
                out = verify(statement, envelope=envelope, require_transparency=require)
                out["source"] = "freshly built statement (no body supplied)"
                return JSONResponse(out)
            statement, envelope, err = _statement_from(body)
            if statement is None:
                return JSONResponse({
                    "ok": False, "schema": SCHEMA, "verdict": VERDICT_FAILED,
                    "verdict_scope": err or "unparseable submission",
                    "label": LABEL_MODELED,
                }, status_code=200)
            out = verify(statement, envelope=envelope, require_transparency=require)
            out["source"] = "caller-supplied " + ("envelope" if envelope else "statement")
            return JSONResponse(out)
        except Exception as exc:
            return JSONResponse({
                "ok": False, "schema": SCHEMA, "verdict": VERDICT_UNKNOWN,
                "verdict_scope": f"verifier error ({type(exc).__name__}) — UNKNOWN, "
                                 "never a fabricated PASSED",
                "label": LABEL_MODELED,
            }, status_code=200)

    try:
        import fastapi as _fastapi
        _h_manifest.__annotations__["request"] = _fastapi.Request
        _h_verify.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    wired: list[str] = []
    specs = (
        (f"{base}/manifest", _h_manifest, ["GET"]),
        (f"{base}/verify", _h_verify, ["GET", "POST"]),
    )
    prefix = base + "/"
    for path, handler, methods in specs:
        try:
            from starlette.routing import Route

            routes = app.router.routes
            insert_at = 0
            for i, rt in enumerate(routes):
                p = getattr(rt, "path", "") or ""
                if p.startswith(prefix) and "{" in p and p != path:
                    insert_at = i
                    break
            routes.insert(insert_at, Route(path, handler, methods=methods))
            wired.append(path)
            continue
        except Exception as exc:
            print(f"[{ns}] attest route front-insert failed for {path}: {exc!r}",
                  file=sys.stderr)
        try:
            add_route = getattr(getattr(app, "router", None), "add_route", None)
            if callable(add_route):
                add_route(path, handler, methods=methods)
            else:
                app.add_api_route(path, handler, methods=methods)
            wired.append(path)
        except Exception as exc:  # additive register must never break boot
            print(f"[{ns}] attest route NOT wired (guarded) {path}: {exc!r}",
                  file=sys.stderr)

    return f"attest-wired:{len(wired)}"


# --------------------------------------------------------------------------- #
# No-server self-test — the honesty invariants of this organ.
# --------------------------------------------------------------------------- #
def _selftest() -> dict[str, Any]:
    man = build_manifest()
    stmt = man["statement"]
    assert stmt["_type"] == STATEMENT_TYPE
    assert stmt["predicateType"] == PREDICATE_TYPE
    assert stmt["predicate"]["doctrine"] == DOCTRINE_VERSION
    # subject always binds a non-empty locked-8 kernel commit
    kernels = [s for s in stmt["subject"] if s["name"] == SUBJECT_KERNEL_NAME]
    assert len(kernels) == 1 and kernels[0]["digest"]["gitCommit"] == KERNEL_PIN
    # no fabricated joule, no fabricated Rekor entry in an offline runtime
    assert stmt["predicate"]["energy_measured"] == [] or all(
        r.get("label") == LABEL_MEASURED for r in stmt["predicate"]["energy_measured"])
    assert man["rekor"]["status"] in (REKOR_RECORDED, REKOR_UNREACHABLE,
                                     REKOR_NOT_ATTEMPTED)
    if man["rekor"]["status"] != REKOR_RECORDED:
        assert man["rekor"]["inclusion_proof"] is None
        assert man["rekor"]["log_index"] is None
        assert man["label"] == LABEL_MODELED
    # policy passes on a well-formed statement, fails on a tampered one
    assert evaluate_policy(stmt)["policy"] == VERDICT_PASSED, evaluate_policy(stmt)
    bad = json.loads(json.dumps(stmt))
    bad["predicate"]["honesty_invariants"]["locked8_immutable"] = False
    assert evaluate_policy(bad)["policy"] == VERDICT_FAILED
    assert verify(bad)["verdict"] == VERDICT_FAILED
    # required transparency with no log => UNKNOWN, never PASSED
    unk = verify(stmt, envelope=man["envelope"], require_transparency=True)
    if man["rekor"]["status"] != REKOR_RECORDED:
        assert unk["verdict"] == VERDICT_UNKNOWN, unk["verdict"]
    # Λ never a theorem
    assert stmt["predicate"]["lambda"]["is_theorem"] is False
    assert stmt["predicate"]["lambda"]["status"] == "Conjecture 1"
    print(f"szl_attest: ALL OK — verdict={man['verdict']} "
          f"rekor={man['rekor']['status']} signed={man['envelope'].get('signed')}")
    return man


if __name__ == "__main__":  # pragma: no cover
    _selftest()
