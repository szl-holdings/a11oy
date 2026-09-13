# SPDX-License-Identifier: Apache-2.0
"""Immutable, fail-closed source/deployment attestation for public SZL surfaces."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from pydantic import BaseModel


SCHEMA_VERSION = "szl.source-deploy-attestation/v2"
PRODUCT_SOURCE_SCHEMA = "szl.product-source/v1"
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


def _observed(value: Optional[str]) -> ObservedValue:
    return ObservedValue(
        value=value,
        evidence_class="MEASURED" if value is not None else "UNKNOWN",
    )


def build_attestation_v2(
    space_id: str,
    source: Optional[Dict[str, object]] = None,
    alignment_state: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Build once from immutable runtime/build inputs; ``force`` is ignored for compatibility."""
    del force
    source = dict(source or {})
    repository = str(source.get("repo_url") or source.get("repository_url") or "").strip()
    if not repository:
        old = str(source.get("repository") or "").strip()
        repository = f"https://github.com/{old}" if old else "https://github.com/szl-holdings/a11oy"

    source_commit = _first_env(
        (
            "A11OY_SOURCE_COMMIT",
            "SZL_GIT_SHA",
            "SPACE_COMMIT_SHA",
            "GITHUB_SHA",
            "VERCEL_GIT_COMMIT_SHA",
        ),
        _commit,
    ) or _commit(source.get("commit"))
    deployed_commit = _first_env(
        ("SPACE_REPOSITORY_COMMIT", "A11OY_DEPLOYED_COMMIT"), _commit
    )
    build_digest = _first_env(("A11OY_BUILD_DIGEST", "SZL_BUILD_DIGEST"), _digest)
    image_digest = _first_env(("A11OY_IMAGE_DIGEST", "CONTAINER_IMAGE_DIGEST"), _digest)
    deploy_timestamp = _first_env(
        ("A11OY_DEPLOYED_AT", "DEPLOYED_AT", "SZL_BUILD_TIME"), _timestamp
    )

    computed_alignment = "UNKNOWN"
    if source_commit and deployed_commit:
        computed_alignment = "MATCH" if source_commit == deployed_commit else "CONFLICT"
    # The legacy caller label cannot override measured parity. If either commit is
    # absent, computed alignment remains UNKNOWN rather than inheriting a claim.
    del alignment_state

    payload = SourceDeployAttestation(
        schema_version=SCHEMA_VERSION,
        immutable_for_process=True,
        repository_url=repository,
        source_commit=_observed(source_commit),
        deployed_commit=_observed(deployed_commit),
        build_digest=_observed(build_digest),
        image_digest=_observed(image_digest),
        deploy_timestamp=_observed(deploy_timestamp),
        deployment_target=space_id,
        alignment_state=computed_alignment,
        claims={
            "reproducible_build": "NOT_CLAIMED",
            "artifact_equivalence": "NOT_CLAIMED",
            "slsa_level": "NOT_CLAIMED",
        },
        limits=[
            "Null/UNKNOWN means the runtime did not expose that immutable build fact.",
            "Repository identity alone does not establish deployed artifact equivalence.",
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
    repository_slug = str(source_input.get("repository") or "szl-holdings/a11oy")
    source_commit = v2["source_commit"]["value"]
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
            "state": "MEASURED" if source_commit else "UNKNOWN",
            "evidence_url": (
                f"https://github.com/{repository_slug}/commit/{source_commit}"
                if source_commit else None
            ),
        },
        "deployment": {
            "hf_space": space_id,
            "hf_revision": revision,
            "revision_state": "MEASURED" if revision else "UNAVAILABLE",
            "measurement_method": "SPACE_REPOSITORY_COMMIT" if revision else "UNAVAILABLE",
        },
        # A caller-supplied label is not evidence.  Preserve the v1 field while
        # deriving its value only from the two independently observed commits.
        "alignment_state": v2["alignment_state"],
        "attestation_state": "UNSIGNED_STRUCTURAL",
        "claims": {
            "github_parity": "NOT_CLAIMED",
            "reproducible_build": "NOT_CLAIMED",
            "build_provenance": "NOT_CLAIMED",
        },
        "limits": list(v2["limits"]),
    }


def measure_hf_revision(space_id: str, force: bool = False) -> Dict[str, object]:
    """Compatibility helper: environment-only, immutable, and never a network claim."""
    del space_id, force
    revision = _first_env(("SPACE_REPOSITORY_COMMIT",), _commit)
    return {
        "hf_revision": revision,
        "revision_state": "MEASURED" if revision else "UNAVAILABLE",
        "measurement_method": "SPACE_REPOSITORY_COMMIT" if revision else "UNAVAILABLE",
    }


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
