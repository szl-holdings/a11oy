"""Bounded deployment-source attestation for public SZL surfaces."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from datetime import datetime, timezone

from fastapi.responses import JSONResponse


_SHA = re.compile(r"^[0-9a-f]{40}$")
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, dict[str, object]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_sha(value: object) -> str | None:
    candidate = str(value or "").strip().lower()
    return candidate if _SHA.fullmatch(candidate) else None


def measure_hf_revision(space_id: str, force: bool = False) -> dict[str, object]:
    env_revision = _valid_sha(os.environ.get("SPACE_REPOSITORY_COMMIT"))
    if env_revision:
        return {
            "hf_revision": env_revision,
            "revision_state": "MEASURED",
            "measurement_method": "SPACE_REPOSITORY_COMMIT",
        }

    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(space_id)
        if not force and cached and now - float(cached["stored_at"]) < 60:
            return dict(cached["measurement"])  # type: ignore[arg-type]

    revision = None
    error = None
    request = urllib.request.Request(
        f"https://huggingface.co/api/spaces/{space_id}?expand[]=sha",
        headers={"Accept": "application/json", "User-Agent": "szl-source-attestation/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            revision = _valid_sha(json.load(response).get("sha"))
    except Exception as exc:
        error = type(exc).__name__

    measurement: dict[str, object] = {
        "hf_revision": revision,
        "revision_state": "MEASURED" if revision else "UNAVAILABLE",
        "measurement_method": "HUGGINGFACE_API" if revision else "UNAVAILABLE",
    }
    if error:
        measurement["measurement_error"] = error
    with _CACHE_LOCK:
        _CACHE[space_id] = {"stored_at": time.monotonic(), "measurement": dict(measurement)}
    return measurement


def build_attestation(
    space_id: str,
    source: dict[str, object],
    alignment_state: str,
    force: bool = False,
) -> dict[str, object]:
    measurement = measure_hf_revision(space_id, force=force)
    return {
        "schema": "szl.deployment-source/v1",
        "observed_at": _now_iso(),
        "transport_state": "REACHABLE",
        "evidence_state": "COMPUTED" if measurement["hf_revision"] else "UNAVAILABLE",
        "verification_state": "STRUCTURAL_ONLY",
        "authority_state": "READ_ONLY",
        "source": dict(source),
        "deployment": {"hf_space": space_id, **measurement},
        "alignment_state": alignment_state,
        "attestation_state": "UNSIGNED_STRUCTURAL",
        "claims": {
            "github_parity": "NOT_CLAIMED",
            "reproducible_build": "NOT_CLAIMED",
            "build_provenance": "NOT_CLAIMED",
        },
        "limits": [
            "The Hugging Face revision is measured independently from the pinned source observation.",
            "A GitHub reference does not establish deployed-artifact equivalence.",
            "This unsigned structural attestation does not prove a reproducible build or build provenance.",
        ],
    }


def register(app, space_id: str, source: dict[str, object], alignment_state: str) -> dict[str, object]:
    async def source_attestation(refresh: int = 0):  # noqa: ANN202
        payload = build_attestation(space_id, source, alignment_state, force=refresh == 1)
        return JSONResponse(
            payload,
            headers={
                "Cache-Control": "no-store",
                "X-SZL-Transport-State": str(payload["transport_state"]),
                "X-SZL-Evidence-State": str(payload["evidence_state"]),
                "X-SZL-Verification-State": str(payload["verification_state"]),
                "X-SZL-Authority-State": str(payload["authority_state"]),
            },
        )

    existing = list(app.router.routes)
    route = "/.well-known/szl-source.json"
    app.add_api_route(route, source_attestation, methods=["GET"], include_in_schema=True)
    added = list(app.router.routes[len(existing):])
    app.router.routes[:] = added + existing
    return {"ok": True, "route": route, "space": space_id, "position": 0}
