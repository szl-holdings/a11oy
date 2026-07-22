# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
"""Bounded runtime contracts for the a11oy service layer.

Taxonomy home: services/ (runtime health, identity, and observability posture).

The four read-only endpoints deliberately answer different questions:

* ``/api/livez`` proves only that this Python process can answer a request.
* ``/api/readyz`` re-walks the configured Khipu chain and folds in the existing
  boot-preflight signal.  Missing or non-durable chain state fails closed.
* ``/api/build-info`` emits only observable, allowlisted build metadata.
* ``/api/<ns>/v1/otel/status`` separates in-process propagation, exporter
  configuration, and fresh collector delivery evidence.

GETs never mint receipts, sign data, contact an upstream, or write to disk.
"""

import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional


_STARTED_MONOTONIC = time.monotonic()
_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}\Z")
_ENV_SHA_NAMES = (
    "A11OY_GIT_SHA",
    "GITHUB_SHA",
    "VERCEL_GIT_COMMIT_SHA",
    "SOURCE_VERSION",
    "GIT_COMMIT",
)
_ENV_VERSION_NAMES = ("A11OY_VERSION", "APP_VERSION", "RELEASE_VERSION")
_DURABLE_BACKENDS = {"sqlite", "json", "postgres", "postgresql", "lmdb"}
_FRESH_COLLECTOR_EVIDENCE_S = 120.0
_SPA_HISTORY_PREFIXES = ("/a11oy",)
_SPA_HISTORY_EXACT_PATHS = frozenset({"/holographic"})
_SPA_FALLBACK_HEADER = "X-SZL-Route-State"
_SPA_FALLBACK_VALUE = "SPA_FALLBACK"
_PRESERVED_RESPONSE_HEADERS = (
    "Content-Security-Policy",
    "Referrer-Policy",
    "Server",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-RateLimit-Limit",
    "X-RateLimit-Policy",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-Span-Id",
    "X-Trace-Id",
)


def _no_store_json(
    content: dict[str, Any], status_code: int = 200, source_headers: Any = None
):
    from fastapi.responses import JSONResponse

    response = JSONResponse(content=content, status_code=status_code)
    if source_headers is not None:
        for name in _PRESERVED_RESPONSE_HEADERS:
            value = source_headers.get(name)
            if value is not None:
                response.headers[name] = value
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _safe_env_sha() -> tuple[Optional[str], Optional[str]]:
    for name in _ENV_SHA_NAMES:
        value = str(os.environ.get(name, "")).strip()
        if _SHA_RE.fullmatch(value):
            return value.lower(), f"env:{name}"
    return None, None


def _safe_git(args: list[str]) -> Optional[subprocess.CompletedProcess[str]]:
    """Run one bounded, read-only git query; never uses a shell."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=0.75,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


def _build_identity() -> dict[str, Any]:
    sha, source = _safe_env_sha()
    if sha is None:
        result = _safe_git(["rev-parse", "HEAD"])
        candidate = result.stdout.strip() if result and result.returncode == 0 else ""
        if _SHA_RE.fullmatch(candidate):
            sha, source = candidate.lower(), "git:HEAD"

    version = None
    version_source = None
    for name in _ENV_VERSION_NAMES:
        candidate = str(os.environ.get(name, "")).strip()
        if _VERSION_RE.fullmatch(candidate):
            version, version_source = candidate, f"env:{name}"
            break

    dirty: Optional[bool] = None
    status = _safe_git(["status", "--porcelain", "--untracked-files=normal"])
    if status and status.returncode == 0:
        dirty = bool(status.stdout.strip())

    return {
        "state": "OBSERVED" if sha else "UNKNOWN",
        "revision": sha,
        "revision_source": source or "UNKNOWN",
        "version": version,
        "version_source": version_source or "UNKNOWN",
        "working_tree": (
            "DIRTY" if dirty is True else "CLEAN" if dirty is False else "UNKNOWN"
        ),
    }


def _verify_khipu_store(app: Any) -> dict[str, Any]:
    state = getattr(app, "state", None)
    store = getattr(state, "be_khipu", None) if state is not None else None
    if store is not None and callable(getattr(store, "verify", None)):
        backend = str(getattr(store, "backend", "UNKNOWN"))
        try:
            result = store.verify()
            if not isinstance(result, tuple) or len(result) != 3:
                raise ValueError("verify() returned an unsupported contract")
            intact, depth, first_break = result
            durable = backend.lower() in _DURABLE_BACKENDS
            ready = bool(intact) and durable
            return {
                "state": "READY" if ready else "NOT_READY",
                "source": "app.state.be_khipu",
                "chain_intact": bool(intact),
                "depth": int(depth),
                "first_break_seq": int(first_break),
                "backend": backend,
                "durable": durable,
                "blocking": not ready,
            }
        except Exception as exc:
            return {
                "state": "UNAVAILABLE",
                "source": "app.state.be_khipu",
                "backend": backend,
                "durable": backend.lower() in _DURABLE_BACKENDS,
                "blocking": True,
                "error_type": type(exc).__name__,
            }

    # Some small deployments use the shared in-process DAG registry without
    # szl_be_hardening.  Re-walk it for diagnostic evidence, but never promote
    # an in-memory registry to readiness: intact links do not prove durable
    # receipt persistence.
    try:
        import szl_khipu_verify

        report = szl_khipu_verify.list_organs()
        organs = list(report.get("organs") or [])
        if not organs:
            return {
                "state": "UNKNOWN",
                "source": "szl_khipu_verify.list_organs",
                "organ_count": 0,
                "blocking": True,
                "reason": "no observed Khipu DAG in this process",
            }
        intact_values = [row.get("links_intact") for row in organs]
        all_intact = all(value is True for value in intact_values)
        return {
            "state": "NOT_READY",
            "source": "szl_khipu_verify.list_organs",
            "organ_count": len(organs),
            "chains_intact": all_intact,
            "backend": "in-process-registry",
            "durable": False,
            "blocking": True,
            "reason": (
                "in-process DAG links are intact but durable persistence is not observed"
                if all_intact
                else "in-process DAG links are not intact and durable persistence is not observed"
            ),
        }
    except Exception as exc:
        return {
            "state": "UNAVAILABLE",
            "source": "szl_khipu_verify.list_organs",
            "blocking": True,
            "error_type": type(exc).__name__,
        }


def _boot_preflight() -> dict[str, Any]:
    try:
        import szl_boot_preflight

        report = szl_boot_preflight.readiness()
        overall = str(report.get("overall", "UNKNOWN")).upper()
        # Missing optional cloud credentials are explicitly DEGRADED, not a
        # failure of the local core.  A hard-required dependency is UNAVAILABLE.
        blocking = overall not in {"LIVE", "DEGRADED"}
        return {
            "state": overall,
            "source": "szl_boot_preflight.readiness",
            "subsystem_count": len(report.get("subsystems") or []),
            "blocking": blocking,
        }
    except Exception as exc:
        return {
            "state": "UNAVAILABLE",
            "source": "szl_boot_preflight.readiness",
            "blocking": True,
            "error_type": type(exc).__name__,
        }


def _readiness(app: Any) -> tuple[dict[str, Any], int]:
    components = {
        "khipu": _verify_khipu_store(app),
        "boot_preflight": _boot_preflight(),
    }
    blockers = [name for name, value in components.items() if value.get("blocking")]
    ready = not blockers
    body = {
        "status": "READY" if ready else "NOT_READY",
        "ready": ready,
        "components": components,
        "blocking_components": blockers,
        "receipt_minted": False,
    }
    return body, 200 if ready else 503


def _collector_evidence(app: Any, exporter_configured: bool) -> dict[str, Any]:
    state = getattr(app, "state", None)
    evidence = getattr(state, "otel_collector_evidence", None) if state is not None else None
    if isinstance(evidence, dict):
        try:
            observed = float(evidence["observed_at_unix"])
            age = max(0.0, time.time() - observed)
            if age <= _FRESH_COLLECTOR_EVIDENCE_S and isinstance(
                evidence.get("reachable"), bool
            ):
                reachable = bool(evidence["reachable"])
                return {
                    "state": "REACHABLE" if reachable else "UNREACHABLE",
                    "evidence": "FRESH_PROBE",
                    "age_s": round(age, 3),
                }
            return {
                "state": "UNKNOWN",
                "evidence": "STALE_OR_INVALID_PROBE",
                "age_s": round(age, 3),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    return {
        "state": "UNKNOWN" if exporter_configured else "UNAVAILABLE",
        "evidence": "NO_FRESH_DELIVERY_PROBE",
        "age_s": None,
    }


def _otel_posture(app: Any) -> dict[str, Any]:
    installed = bool(getattr(app, "_vsp_otel_installed", False))
    exporter_raw = str(getattr(app, "_vsp_otel_exporter", "UNAVAILABLE"))
    policy = dict(getattr(app, "_vsp_otel_endpoint_policy", {}) or {})

    # Prefer the existing VSP status object when it is available, but recompute
    # maturity below: VSP propagation is not proof of collector delivery.
    try:
        import vsp_otel.middleware as vsp_otel

        existing = vsp_otel.status(app)
        installed = existing.get("propagation") == "READY"
        exporter_raw = str(existing.get("exporter", exporter_raw))
        endpoint = existing.get("endpoint")
        if isinstance(endpoint, dict):
            policy = endpoint
    except Exception:
        pass

    exporter_configured = exporter_raw.startswith("otlp-grpc:configured:")
    collector = _collector_evidence(app, exporter_configured)
    if collector["state"] == "REACHABLE":
        overall = "LIVE"
    elif installed:
        overall = "DEGRADED"
    else:
        overall = "UNAVAILABLE"
    return {
        "status": overall,
        "in_process": {
            "state": "LIVE" if installed else "UNAVAILABLE",
            "trace_propagation": "READY" if installed else "UNAVAILABLE",
        },
        "exporter": {
            "state": "CONFIGURED_UNVERIFIED" if exporter_configured else "UNAVAILABLE",
            "endpoint_policy": str(policy.get("state", "UNKNOWN")),
            "endpoint_fingerprint": policy.get("fingerprint"),
            "delivery_asserted": False,
        },
        "collector": collector,
        "receipt_minted": False,
        "note": "in-process trace propagation is separate from exporter configuration and collector delivery",
    }


def _looks_like_file_or_well_known(path: str) -> bool:
    if path == "/.well-known" or path.startswith("/.well-known/"):
        return True
    last = path.rsplit("/", 1)[-1]
    return bool(last and "." in last and last not in {".", ".."})


def is_declared_spa_navigation(path: str) -> bool:
    """Return whether ``path`` belongs to a real client-side route family.

    The built Wouter application declares ``/a11oy/*`` routes. The Holographic
    shell declares only the exact ``/holographic`` path; its surface selection
    uses URL hashes rather than pathname deep links. Root-level pages are
    explicit FastAPI routes and therefore never need the catch-all.
    """
    candidate = "/" + str(path or "").strip().lstrip("/")
    if candidate != "/":
        candidate = candidate.rstrip("/")
    return candidate in _SPA_HISTORY_EXACT_PATHS or any(
        candidate == prefix or candidate.startswith(prefix + "/")
        for prefix in _SPA_HISTORY_PREFIXES
    )


def _matched_by_path_catchall(app: Any, scope: dict[str, Any]) -> bool:
    """Return True only when the first matching route is a ``:path`` wildcard."""
    try:
        from starlette.routing import Match

        for route in app.router.routes:
            matches = getattr(route, "matches", None)
            if not callable(matches):
                continue
            match, _ = matches(scope)
            if match == Match.FULL:
                template = str(getattr(route, "path", ""))
                return ":path}" in template
    except Exception:
        return False
    return False


def _install_soft_404_guard(app: Any) -> None:
    if getattr(app.state, "szl_runtime_soft_404_guard", False):
        return

    @app.middleware("http")
    async def _runtime_soft_404_guard(request, call_next):
        suspicious = request.method in {"GET", "HEAD"} and _looks_like_file_or_well_known(
            request.url.path
        )
        catchall_match = _matched_by_path_catchall(app, request.scope)
        response = await call_next(request)
        content_type = str(response.headers.get("content-type", "")).lower()
        marked_fallback = (
            str(response.headers.get(_SPA_FALLBACK_HEADER, "")).upper()
            == _SPA_FALLBACK_VALUE
        )
        undeclared_navigation = marked_fallback and not is_declared_spa_navigation(
            request.url.path
        )
        if (
            request.method in {"GET", "HEAD"}
            and catchall_match
            and response.status_code == 200
            and "text/html" in content_type
            and (suspicious or undeclared_navigation)
        ):
            return _no_store_json(
                {
                    "status": "NOT_FOUND",
                    "path": request.url.path,
                    "reason": "undeclared path refused SPA fallback",
                },
                status_code=404,
                source_headers=response.headers,
            )
        return response

    app.state.szl_runtime_soft_404_guard = True


def _front_move_new_routes(app: Any, previous_ids: set[int]) -> None:
    """Ensure exact contracts win even when register() follows a SPA catch-all."""
    added = [route for route in app.router.routes if id(route) not in previous_ids]
    if not added:
        return
    old = [route for route in app.router.routes if id(route) in previous_ids]
    app.router.routes[:] = added + old


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    """Register idempotent, read-only runtime endpoints and the soft-404 guard."""
    if getattr(app.state, "szl_runtime_contracts_registered", False):
        return {"registered": False, "reason": "already_registered"}

    previous_ids = {id(route) for route in app.router.routes}
    # Git inspection is a bounded startup observation, not request work.  Keep
    # the immutable snapshot in this registration closure so public GETs never
    # spawn child processes or re-read the working tree.
    build_identity = _build_identity()

    @app.get("/api/livez", tags=["runtime"], include_in_schema=True)
    async def _livez():
        return _no_store_json(
            {
                "status": "LIVE",
                "process": {
                    "pid": os.getpid(),
                    "uptime_s": round(time.monotonic() - _STARTED_MONOTONIC, 3),
                    "python_implementation": platform.python_implementation(),
                },
                "scope": "process liveness only; no dependency readiness asserted",
                "receipt_minted": False,
            }
        )

    @app.get("/api/readyz", tags=["runtime"], include_in_schema=True)
    async def _readyz():
        body, status = _readiness(app)
        return _no_store_json(body, status_code=status)

    @app.get("/api/build-info", tags=["runtime"], include_in_schema=True)
    async def _build_info():
        return _no_store_json(
            {
                "status": "OBSERVED",
                "service": ns,
                "build": build_identity,
                "runtime": {
                    "python": platform.python_version(),
                    "platform": sys.platform,
                },
                "receipt_minted": False,
            }
        )

    @app.get(f"/api/{ns}/v1/otel/status", tags=["runtime"], include_in_schema=True)
    async def _otel_status():
        return _no_store_json(_otel_posture(app))

    _front_move_new_routes(app, previous_ids)
    _install_soft_404_guard(app)
    app.state.szl_runtime_contracts_registered = True
    return {
        "registered": True,
        "routes": [
            "/api/livez",
            "/api/readyz",
            "/api/build-info",
            f"/api/{ns}/v1/otel/status",
        ],
        "external_writes": False,
    }
