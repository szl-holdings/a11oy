"""Closed response contract for the Phase-B readiness repair.

This module changes only the exact JSON read surfaces named by the current-main
Phase-B execution contract. It adds a request-time observation clock without
upgrading the freshness of any nested source evidence, and it canonicalizes the
KEV response vocabulary without relabeling the bundled snapshot as live.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

PHASE_B_OBSERVATION_PATHS = frozenset(
    {
        "/api/a11oy/provenance",
        "/api/a11oy/v1/energy/sci",
        "/api/a11oy/v1/observability/summary",
        "/api/a11oy/v1/observability/business",
        "/api/a11oy/v1/mesh/state",
    }
)

# The existing public alias resolves to the same business-observability handler.
PHASE_B_OBSERVATION_ALIASES = frozenset({"/v1/observability/business"})
KEVGATE_PATHS = frozenset({"/api/a11oy/v1/sec/kev"})
_MUTATED_PATHS = PHASE_B_OBSERVATION_PATHS | PHASE_B_OBSERVATION_ALIASES | KEVGATE_PATHS


def utc_observation_clock() -> str:
    """Return one genuine request-time UTC observation clock."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_phase_b_payload(
    path: str,
    payload: Any,
    *,
    observed_at: str | None = None,
    status_code: int = 200,
) -> Any:
    """Apply the closed Phase-B vocabulary to one decoded JSON value.

    Supplying ``observed_at`` makes the function deterministic for regression
    tests. Unknown paths and non-object values are returned without semantic
    changes. Error responses are never rewritten into cached KEV evidence.
    """
    if not isinstance(payload, dict):
        return payload

    normalized = dict(payload)
    if path in PHASE_B_OBSERVATION_PATHS or path in PHASE_B_OBSERVATION_ALIASES:
        normalized["observed_at"] = observed_at or utc_observation_clock()

    if path in KEVGATE_PATHS and 200 <= int(status_code) < 300:
        raw_kind = str(normalized.get("data_kind") or "").strip().casefold()
        canonical_kind = "live" if raw_kind == "live" else "cached"
        normalized["data_kind"] = canonical_kind

        detail = normalized.get("detail")
        if not isinstance(detail, str) or not detail.strip():
            note = normalized.get("note")
            if isinstance(note, str) and note.strip():
                detail = note
            elif canonical_kind == "live":
                detail = (
                    "The KEV source identified this response as live during the "
                    "current request; reachability is not independent validation."
                )
            else:
                detail = (
                    "Bundled CISA KEV snapshot served from the current image; "
                    "this is cached source material, not a live catalog fetch."
                )
        normalized["detail"] = detail

    return normalized


async def _single_body(body: bytes) -> AsyncIterator[bytes]:
    yield body


def install_phase_b_response_contract(app: Any) -> None:
    """Install the exact-path JSON normalizer once on a FastAPI application."""
    state = getattr(app, "state", None)
    marker = "_readiness_phase_b_response_contract_installed"
    if state is not None and getattr(state, marker, False):
        return
    if state is not None:
        setattr(state, marker, True)

    @app.middleware("http")
    async def _phase_b_response_contract(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        path = request.url.path
        if path not in _MUTATED_PATHS:
            return response

        content_type = response.headers.get("content-type", "").casefold()
        if "json" not in content_type:
            return response
        content_encoding = response.headers.get("content-encoding", "identity").casefold()
        if content_encoding not in {"", "identity"}:
            return response

        iterator = getattr(response, "body_iterator", None)
        if iterator is None:
            return response

        chunks: list[bytes] = []
        async for chunk in iterator:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
            elif isinstance(chunk, str):
                chunks.append(chunk.encode("utf-8"))
            else:
                chunks.append(bytes(chunk))
        raw = b"".join(chunks)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response.body_iterator = _single_body(raw)
            response.headers["content-length"] = str(len(raw))
            return response

        normalized = normalize_phase_b_payload(
            path,
            payload,
            status_code=int(getattr(response, "status_code", 200)),
        )
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        response.body_iterator = _single_body(encoded)
        response.headers["content-length"] = str(len(encoded))
        for stale_validator in ("etag", "content-md5"):
            if stale_validator in response.headers:
                del response.headers[stale_validator]
        return response
