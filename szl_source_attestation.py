# SPDX-License-Identifier: Apache-2.0
"""Immutable, fail-closed source/deployment attestation for public SZL surfaces.

Process-environment strings and caller-dict strings are declarations.
This module does not emit MEASURED. Payload limits name the measurement
method an independent observation would have to carry before MEASURED
would be honest.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from pydantic import BaseModel


SCHEMA_VERSION = "szl.source-deploy-attestation/v2"
PRODUCT_SOURCE_SCHEMA = "szl.product-source/v1"
# A 40-hex process environment string. Not a Hugging Face host measurement.
ENV_DECLARATION = "ENV_DECLARATION"
# A 40-hex commit supplied by the caller dict. Not an environment string.
CALLER_DECLARED = "CALLER_DECLARED"
# Revision text from a binding file whose sibling bytes match that file's digest.
DECLARED_WITH_LOCAL_DIGEST = "DECLARED_WITH_LOCAL_DIGEST"
LOCAL_FILE_SHA256 = "LOCAL_FILE_SHA256"
# Not returned here. A MEASURED build digest, image digest, or deploy timestamp
# would require this method: a party who did not supply the string compared it
# to artifact bytes or a signed time outside this process.
INDEPENDENT_ARTIFACT_OBSERVATION = "INDEPENDENT_ARTIFACT_OBSERVATION"
# Not returned here. The observer gate asks for this method together with
# revision_state MEASURED. That would require a party who did not write the
# binding file to compare running artifact bytes with the published git object.
# The local sibling hash does not cover the revision string.
HOST_REVISION_MEASUREMENT = "SPACE_REPOSITORY_COMMIT"
RUNTIME_BINDING_ENV = "A11OY_HF_RUNTIME_BINDING"
RUNTIME_BINDING_SCHEMA = "szl.hf-runtime-binding/v1"
PRODUCT_SOURCE_ROUTE = "/.well-known/source.json"
# Doctrine v11 LOCKED kernel pin. This is the doctrine lock, NOT the Space deploy SHA.
DOCTRINE_KERNEL_PIN = "c7c0ba17"
FORBIDDEN_FIRST_PAINT = frozenset({"LIVE", "RUNNING", "PASS"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


class ObservedValue(BaseModel):
    value: Optional[str]
    evidence_class: str

    class Config:
        extra = "forbid"


class SourceDeployAttestation(BaseModel):
    schema_version: str
    immutable_for_process: bool
    repository_url: str
    source_commit: ObservedValue
    deployed_commit: ObservedValue
    build_digest: ObservedValue
    image_digest: ObservedValue
    deploy_timestamp: ObservedValue
    deployment_target: str
    alignment_state: str
    claims: Dict[str, str]
    limits: list[str]

    class Config:
        extra = "forbid"


def _commit(value: object) -> Optional[str]:
    candidate = str(value or "").strip().lower()
    return candidate if _SHA40.fullmatch(candidate) else None


def _digest(value: object) -> Optional[str]:
    candidate = str(value or "").strip().lower()
    if not _SHA256.fullmatch(candidate):
        return None
    return candidate if candidate.startswith("sha256:") else f"sha256:{candidate}"


def _timestamp(value: object) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _first_env(names: tuple[str, ...], validator) -> Optional[str]:
    for name in names:
        value = validator(os.environ.get(name))
        if value:
            return value
    return None


def _unknown() -> ObservedValue:
    return ObservedValue(value=None, evidence_class="UNKNOWN")


def _env_declaration(value: Optional[str]) -> ObservedValue:
    """Copy a process-environment string, and do not call it MEASURED."""
    if value is None:
        return _unknown()
    return ObservedValue(value=value, evidence_class=ENV_DECLARATION)


def _source_commit_observation(source: Dict[str, object]) -> ObservedValue:
    """Label an environment SHA and a caller-supplied SHA as different facts."""
    from_environment = _first_env(
        (
            "A11OY_SOURCE_COMMIT",
            "SZL_GIT_SHA",
            "GITHUB_SHA",
            "VERCEL_GIT_COMMIT_SHA",
        ),
        _commit,
    )
    if from_environment is not None:
        return _env_declaration(from_environment)
    supplied = _commit(source.get("commit"))
    if supplied is None:
        return _unknown()
    return ObservedValue(value=supplied, evidence_class=CALLER_DECLARED)


def build_attestation_v2(
    space_id: str,
    source: Optional[Dict[str, object]] = None,
    alignment_state: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Build once from immutable runtime/build inputs; ``force`` is ignored for compatibility."""
    del force
    source = dict(source or {})
    # Caller digest and timestamp keys are not observations. Leaving them unread
    # keeps them out of the payload; they are not relabeled as MEASURED.
    for ignored in ("build_digest", "image_digest", "deploy_timestamp", "timestamp"):
        source.pop(ignored, None)
    repository = str(source.get("repo_url") or source.get("repository_url") or "").strip()
    if not repository:
        old = str(source.get("repository") or "").strip()
        repository = f"https://github.com/{old}" if old else "https://github.com/szl-holdings/a11oy"

    source_commit_observed = _source_commit_observation(source)
    source_commit = source_commit_observed.value
    deployed_commit = _first_env(
        ("SPACE_REPOSITORY_COMMIT", "A11OY_DEPLOYED_COMMIT"), _commit
    )
    build_digest = _first_env(("A11OY_BUILD_DIGEST", "SZL_BUILD_DIGEST"), _digest)
    image_digest = _first_env(("A11OY_IMAGE_DIGEST", "CONTAINER_IMAGE_DIGEST"), _digest)
    deploy_timestamp = _first_env(
        ("A11OY_DEPLOYED_AT", "DEPLOYED_AT", "SZL_BUILD_TIME"), _timestamp
    )

    # These are commits in separate Git repositories, not comparable identities.
    # Equal strings do not prove deployment of the source bytes, and different
    # strings do not prove a conflict. A separately verified source -> HF
    # publication byte-binding receipt is required before claiming alignment.
    # This read-only surface does not verify such a receipt, so fail closed.
    computed_alignment = "UNKNOWN"
    # A legacy caller label is not publication evidence.
    del alignment_state

    payload = SourceDeployAttestation(
        schema_version=SCHEMA_VERSION,
        immutable_for_process=True,
        repository_url=repository,
        source_commit=source_commit_observed,
        deployed_commit=_env_declaration(deployed_commit),
        build_digest=_env_declaration(build_digest),
        image_digest=_env_declaration(image_digest),
        deploy_timestamp=_env_declaration(deploy_timestamp),
        deployment_target=space_id,
        alignment_state=computed_alignment,
        claims={
            "reproducible_build": "NOT_CLAIMED",
            "artifact_equivalence": "NOT_CLAIMED",
            "slsa_level": "NOT_CLAIMED",
        },
        limits=[
            "Null/UNKNOWN means this surface did not read a well-formed value from the process environment.",
            "ENV_DECLARATION is a process environment string, including source SHAs, deployed SHAs, build_digest, image_digest, and deploy_timestamp. It is not MEASURED.",
            "CALLER_DECLARED is the source commit supplied by the caller dict when no source environment SHA is set. Caller build_digest, image_digest, and deploy_timestamp are not read. CALLER_DECLARED is not MEASURED.",
            "This producer emits no MEASURED value. MEASURED requires a measurement_method for an observation this process did not perform. A build digest, image digest, or deploy timestamp would require measurement_method INDEPENDENT_ARTIFACT_OBSERVATION: a party who did not supply the string compared it to artifact bytes or a signed time outside this process.",
            "DECLARED_WITH_LOCAL_DIGEST / LOCAL_FILE_SHA256 means a writer-selected binding file named a sibling whose bytes match artifact_sha256. That digest does not cover hf_revision. The result is local consistency only and does not satisfy the observer gate.",
            "A legitimate MEASURED revision with measurement_method SPACE_REPOSITORY_COMMIT requires a party who did not write the binding file to compare the running artifact bytes with the git object published for that 40-hex SHA. This helper does not fetch that object and does not return that pair.",
            "GitHub and Hugging Face commit SHAs belong to separate histories; their equality or inequality does not establish source/deployment alignment.",
            "Alignment requires a separately verified source-to-HF publication byte-binding receipt; none is verified by this surface.",
            "This surface does not represent the separate Replit TypeScript control plane.",
        ],
    )
    return json.loads(payload.json())


def build_attestation(
    space_id: str,
    source: Optional[Dict[str, object]] = None,
    alignment_state: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Backward-compatible v1 shape, derived from the same frozen-safe inputs."""
    v2 = build_attestation_v2(space_id, source, alignment_state, force)
    source_input = dict(source or {})
    revision = v2["deployed_commit"]["value"]
    deployed_class = v2["deployed_commit"]["evidence_class"]
    repository_slug = str(source_input.get("repository") or "szl-holdings/a11oy")
    source_commit = v2["source_commit"]["value"]
    source_class = v2["source_commit"]["evidence_class"]
    return {
        "schema": "szl.deployment-source/v1",
        "observed_at": _now_iso(),
        "transport_state": "REACHABLE",
        "evidence_state": "COMPUTED" if revision else "UNAVAILABLE",
        "verification_state": "STRUCTURAL_ONLY",
        "authority_state": "READ_ONLY",
        "source": {
            "repository": repository_slug,
            "commit": source_commit,
            "path": str(source_input.get("path") or ""),
            "relation": str(source_input.get("relation") or "declared-source-with-hf-overlay"),
            "state": source_class if source_commit else "UNKNOWN",
            "evidence_url": (
                f"https://github.com/{repository_slug}/commit/{source_commit}"
                if source_commit else None
            ),
        },
        "deployment": {
            "hf_space": space_id,
            "hf_revision": revision,
            "revision_state": "UNAVAILABLE" if revision is None else deployed_class,
            "measurement_method": "UNAVAILABLE" if revision is None else "PROCESS_ENVIRONMENT",
        },
        # A caller-supplied label or a direct comparison of cross-repository
        # commit SHAs is not evidence. Preserve the v1 field, fail closed.
        "alignment_state": v2["alignment_state"],
        "attestation_state": "UNSIGNED_STRUCTURAL",
        "claims": {
            "github_parity": "NOT_CLAIMED",
            "reproducible_build": "NOT_CLAIMED",
            "build_provenance": "NOT_CLAIMED",
        },
        "limits": list(v2["limits"]),
    }


def _runtime_unavailable() -> Dict[str, object]:
    return {
        "hf_revision": None,
        "revision_state": "UNAVAILABLE",
        "measurement_method": "UNAVAILABLE",
    }


def _environment_runtime() -> Dict[str, object]:
    revision = _first_env(("SPACE_REPOSITORY_COMMIT",), _commit)
    if revision is None:
        return _runtime_unavailable()
    return {
        "hf_revision": revision,
        "revision_state": ENV_DECLARATION,
        "measurement_method": "PROCESS_ENVIRONMENT",
    }


def _read_regular_file(path: Path) -> bytes:
    """Read a regular file without following a symlink when the OS can say so.

    Linux uses ``O_NOFOLLOW``. A platform without that flag rejects a reparse
    point or symlink by ``lstat`` and then reads the already-checked path.
    """
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        descriptor = os.open(path, os.O_RDONLY | nofollow)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise OSError("not a regular file")
            remaining = info.st_size
            chunks = []
            while remaining > 0:
                block = os.read(descriptor, min(remaining, 1024 * 1024))
                if not block:
                    break
                chunks.append(block)
                remaining -= len(block)
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise OSError("symlink")
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(info, "st_file_attributes", 0) or 0
    if reparse and attributes & reparse:
        raise OSError("reparse point")
    if not stat.S_ISREG(info.st_mode):
        raise OSError("not a regular file")
    return path.read_bytes()


def _independent_runtime_binding() -> Optional[Dict[str, object]]:
    """Check a caller-selected binding file against its sibling bytes.

    ``None`` means no binding was configured. A configured binding never falls
    through to the process-environment string. A digest match keeps the
    revision text from that file and does not call it a Hugging Face host
    measurement: the same writer chose the revision and the bytes.
    """
    configured = str(os.environ.get(RUNTIME_BINDING_ENV) or "").strip()
    if not configured:
        return None
    try:
        path = Path(configured)
        payload = json.loads(_read_regular_file(path).decode("utf-8"))
        if not isinstance(payload, dict):
            return _runtime_unavailable()
        name = payload.get("artifact_name")
        revision = _commit(payload.get("hf_revision"))
        digest = str(payload.get("artifact_sha256") or "")
        if (payload.get("schema") != RUNTIME_BINDING_SCHEMA
                or not isinstance(name, str) or name != Path(name).name
                or name in {"", ".", ".."} or "/" in name or "\\" in name
                or revision is None or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            return _runtime_unavailable()
        artifact = path.parent.joinpath(name)
        if artifact.parent != path.parent:
            return _runtime_unavailable()
        hashed = _read_regular_file(artifact)
        if hashlib.sha256(hashed).hexdigest() != digest:
            return _runtime_unavailable()
        declared = _first_env(("SPACE_REPOSITORY_COMMIT",), _commit)
        if declared is not None and declared != revision:
            return _runtime_unavailable()
    except (OSError, ValueError, TypeError, UnicodeError):
        return _runtime_unavailable()
    return {
        "hf_revision": revision,
        "revision_state": DECLARED_WITH_LOCAL_DIGEST,
        "measurement_method": LOCAL_FILE_SHA256,
    }


def measure_hf_revision(space_id: str, force: bool = False) -> Dict[str, object]:
    """Read a local binding digest or an environment declaration.

    Hugging Face's documented Space environment does not define
    ``SPACE_REPOSITORY_COMMIT`` as an immutable host identity. That string stays
    ``ENV_DECLARATION`` / ``PROCESS_ENVIRONMENT``. A binding file whose sibling
    bytes match its digest stays ``DECLARED_WITH_LOCAL_DIGEST`` /
    ``LOCAL_FILE_SHA256``. The digest does not cover ``hf_revision``. Neither
    result is ``MEASURED`` and neither uses method ``SPACE_REPOSITORY_COMMIT``,
    so neither satisfies the observer gate. Agreement between the environment
    string and the binding revision does not promote the result.

    A legitimate ``MEASURED`` / ``SPACE_REPOSITORY_COMMIT`` result would require
    a party who did not write the binding file to compare the running artifact
    bytes with the git object published for that 40-hex SHA. This helper does
    not fetch that object and does not return that pair. A bad or conflicting
    binding is ``UNAVAILABLE``. This helper makes no network call. ``force``
    is ignored.
    """
    del space_id, force
    bound = _independent_runtime_binding()
    if bound is not None:
        return bound
    return _environment_runtime()


def _honest_git_sha() -> tuple[str, str]:
    """Identity is /api/a11oy/v1/honest git_sha (SZL_GIT_SHA), not the kernel pin."""
    raw = str(os.environ.get("SZL_GIT_SHA") or "").strip()
    if raw:
        return raw, "env:SZL_GIT_SHA"
    return "unknown", "UNKNOWN"


def build_product_source() -> Dict[str, Any]:
    """Honest product source declaration for GET /.well-known/source.json.

    Signer ABSENT / UNSIGNED-honest. certified, proven_trust, and
    publication_eligible stay false. First paint is OBSERVED — never
    LIVE/RUNNING/PASS. This surface does not mint DSSE as product signer.
    """
    git_sha, git_sha_source = _honest_git_sha()
    first_paint = "OBSERVED"
    status = "UNSIGNED-honest"
    if first_paint in FORBIDDEN_FIRST_PAINT or status in FORBIDDEN_FIRST_PAINT:
        raise RuntimeError("refusing LIVE/RUNNING/PASS first paint on product source.json")
    return {
        "schema": PRODUCT_SOURCE_SCHEMA,
        "path": PRODUCT_SOURCE_ROUTE,
        "origin": "https://a-11-oy.com",
        "repository": "szl-holdings/a11oy",
        "repository_url": "https://github.com/szl-holdings/a11oy",
        "identity": "/api/a11oy/v1/honest git_sha",
        "git_sha": git_sha,
        "git_sha_source": git_sha_source,
        "doctrine": "v11",
        "doctrine_lock": {
            "doctrine": "v11",
            "state": "LOCKED",
            "commit": DOCTRINE_KERNEL_PIN,
            "note": (
                "Doctrine v11 LOCKED kernel pin. This is the doctrine lock, "
                "NOT the Space deploy SHA."
            ),
        },
        "signer": "ABSENT",
        "signer_honesty": "UNSIGNED-honest",
        "certified": False,
        "proven_trust": False,
        "publication_eligible": False,
        "first_paint": first_paint,
        "status": status,
        "receipt_minted": False,
        "dsse": None,
        "limits": [
            "First paint is OBSERVED / UNSIGNED-honest; this surface does not stamp LIVE, RUNNING, or PASS.",
            "Signer is ABSENT. This is not a product-signer DSSE.",
            "git_sha is the honest identity from /api/a11oy/v1/honest, not the doctrine kernel pin.",
            "Doctrine v11 LOCKED kernel pin c7c0ba17 is the doctrine lock, not the Space deploy SHA.",
            "certified, proven_trust, and publication_eligible remain false.",
        ],
    }


def register(app, space_id: str, source: Dict[str, object], alignment_state: str) -> Dict[str, object]:
    # Freeze once at process registration: repeated GETs are byte-stable. The v1
    # route and shape remain intact; v2 is additive and typed. Product
    # /.well-known/source.json is additive and does not replace szl-source.json.
    payload_v1 = build_attestation(space_id, source, alignment_state)
    payload_v2 = build_attestation_v2(space_id, source, alignment_state)
    payload_product = build_product_source()

    async def source_attestation(refresh: int = 0):  # noqa: ANN202
        headers = {
            "Cache-Control": "no-store",
            # These headers were part of the original v1 transport contract.
            "X-SZL-Transport-State": str(payload_v1["transport_state"]),
            "X-SZL-Evidence-State": str(payload_v1["evidence_state"]),
            "X-SZL-Verification-State": str(payload_v1["verification_state"]),
            "X-SZL-Authority-State": str(payload_v1["authority_state"]),
        }
        if refresh == 1:
            # v2 is deliberately immutable for the process.  Make the v1
            # compatibility behavior change explicit instead of silently
            # implying that a network refresh occurred.
            headers["Warning"] = '299 A11oy "refresh is deprecated; immutable build facts were returned"'
            headers["Deprecation"] = "true"
        return JSONResponse(
            payload_v1,
            headers=headers,
        )

    async def source_attestation_v2():  # noqa: ANN202
        return JSONResponse(payload_v2, headers={"Cache-Control": "no-store"})

    async def product_source():  # noqa: ANN202
        return JSONResponse(payload_product, headers={"Cache-Control": "no-store"})

    route = "/.well-known/szl-source.json"
    route_v2 = "/.well-known/szl-source-v2.json"
    route_product = PRODUCT_SOURCE_ROUTE
    existing = list(app.router.routes)
    app.add_api_route(
        route,
        source_attestation,
        methods=["GET"],
        include_in_schema=True,
    )
    app.add_api_route(
        route_v2,
        source_attestation_v2,
        methods=["GET"],
        include_in_schema=True,
        response_model=SourceDeployAttestation,
    )
    app.add_api_route(
        route_product,
        product_source,
        methods=["GET"],
        include_in_schema=True,
    )
    added = list(app.router.routes[len(existing):])
    app.router.routes[:] = added + existing
    return {
        "ok": True,
        "route": route,
        "route_v2": route_v2,
        "route_product": route_product,
        "space": space_id,
        "position": 0,
    }


__all__ = [
    "SCHEMA_VERSION", "PRODUCT_SOURCE_SCHEMA", "PRODUCT_SOURCE_ROUTE",
    "DOCTRINE_KERNEL_PIN", "SourceDeployAttestation", "build_attestation",
    "build_attestation_v2", "build_product_source", "measure_hf_revision",
    "register",
]
