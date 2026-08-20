# SPDX-License-Identifier: Apache-2.0
"""FastAPI delivery for ORO.

The standalone app is runnable as ``python -m uvicorn oro.api:create_app --factory``.
``mount_oro`` is an unactivated integration hook that a separately reviewed
canonical-server successor can call before its API proxy and SPA catch-all.
"""

import json
import os
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .auth import (
    BearerTokenAuthorizer,
    OROAuthorizationError,
    OROAuthorizerUnavailable,
    authorizer_from_environment,
)
from .core import OROContractError, OROSignerUnavailable, OROStateError
from .dashboard import render_dashboard
from .service import OROService, baseline_codex, role_cells
from .signing import signer_from_environment
from .store import OROStore

BODY_LIMIT = 256 * 1024
API_SCHEMA = "szl.oro-api/v1"


class ORORuntimeUnavailable(OROStateError):
    """A required ORO runtime dependency is unavailable."""


class ORORuntime:
    def __init__(self) -> None:
        environment = os.environ.get("SZL_ORO_ENV", "development").strip().lower()
        self.production = environment not in {"development", "test"}
        self.environment = environment
        self.store: OROStore | None = None
        self.service: OROService | None = None
        self.authorizer: BearerTokenAuthorizer | None = None
        self.error: Exception | None = None
        try:
            if environment not in {"development", "test", "production", "prod"}:
                raise OROContractError("unsupported SZL_ORO_ENV value")
            self.authorizer = authorizer_from_environment(production=self.production)
            if self.production and self.authorizer is None:
                raise OROAuthorizerUnavailable("managed write authorizer is unavailable")
            configured_path = os.environ.get("SZL_ORO_DB_PATH", "").strip()
            if self.production and not configured_path:
                raise OROStateError("production requires SZL_ORO_DB_PATH")
            db_path = configured_path or str(Path("/tmp/a11oy-oro.sqlite").resolve())
            self.store = OROStore(db_path, production=self.production)
            signer = signer_from_environment(production=self.production)
            self.service = OROService(
                store=self.store,
                signer=signer,
                production=self.production,
            )
        except Exception as exc:  # readiness remains honest and process stays observable
            self.error = exc

    def close(self) -> None:
        if self.store is not None:
            self.store.close()

    def health(self) -> Mapping[str, Any]:
        return {
            "schema": API_SCHEMA,
            "alive": True,
            "state": "RUNNING",
            "environment": self.environment,
            "service_initialized": self.service is not None,
            "write_authorizer_initialized": self.authorizer is not None,
            "error_class": type(self.error).__name__ if self.error is not None else None,
        }

    def readiness(self) -> tuple[int, Mapping[str, Any]]:
        if self.service is None:
            body = {
                "schema": API_SCHEMA,
                "ready": False,
                "state": "UNAVAILABLE",
                "production": self.production,
                "error_class": type(self.error).__name__ if self.error is not None else "Unavailable",
                "reason": "required ORO runtime dependency is unavailable",
                "secret_value_exposed": False,
                "write_authorizer": (
                    dict(self.authorizer.identity)
                    if self.authorizer is not None
                    else {"state": "UNAVAILABLE"}
                ),
            }
            if self.store is not None:
                body["storage"] = self.store.integrity()
            return 503, body
        body = {"schema": API_SCHEMA, **self.service.readiness()}
        body["write_authorizer"] = (
            dict(self.authorizer.identity)
            if self.authorizer is not None
            else {"state": "UNAVAILABLE"}
        )
        body["ready"] = bool(body["ready"] and self.authorizer is not None)
        body["state"] = "READY" if body["ready"] else "UNAVAILABLE"
        return (200 if body["ready"] else 503), body

    def require_service(self) -> OROService:
        if self.service is None:
            raise ORORuntimeUnavailable("required ORO runtime dependency is unavailable")
        return self.service

    def authorize_write(self, request: Request) -> str:
        if self.authorizer is None:
            raise OROAuthorizerUnavailable("managed write authorizer is unavailable")
        return self.authorizer.authorize(request)


async def _read_json(request: Request) -> Mapping[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise OROContractError("content-type must be application/json")
    declared = request.headers.get("content-length")
    if declared:
        try:
            length = int(declared)
        except ValueError as exc:
            raise OROContractError("content-length must be a non-negative integer") from exc
        if length < 0:
            raise OROContractError("content-length must be a non-negative integer")
        if length > BODY_LIMIT:
            raise OROContractError("request body exceeds 256 KiB")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > BODY_LIMIT:
            raise OROContractError("request body exceeds 256 KiB")
        data.extend(chunk)

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OROContractError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(bytes(data).decode("utf-8"), object_pairs_hook=closed_object)
    except UnicodeDecodeError as exc:
        raise OROContractError("request body must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise OROContractError("request body must be one JSON object") from exc
    if not isinstance(payload, Mapping):
        raise OROContractError("request body must be one JSON object")
    return payload


def _error(
    status: int,
    code: str,
    message: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {
            "schema": API_SCHEMA,
            "accepted": False,
            "error": {"code": code, "message": message[:2048]},
            "secret_value_exposed": False,
        },
        status_code=status,
        headers=dict(headers or {}),
    )


def build_router(runtime: ORORuntime, *, namespace: str = "a11oy") -> APIRouter:
    api = f"/api/{namespace}/v1/oro"
    router = APIRouter()

    @router.get("/oro", response_class=HTMLResponse, include_in_schema=False)
    async def oro_dashboard() -> HTMLResponse:
        return HTMLResponse(
            render_dashboard(api),
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                    "frame-ancestors 'none'"
                ),
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )

    @router.get("/oro/v5", response_class=HTMLResponse, include_in_schema=False)
    async def oro_dashboard_v5() -> HTMLResponse:
        return await oro_dashboard()

    @router.get(f"{api}/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse(runtime.health())

    @router.get(f"{api}/readyz")
    async def readyz() -> JSONResponse:
        status, body = runtime.readiness()
        return JSONResponse(body, status_code=status)

    @router.get(f"{api}/contract")
    async def contract() -> JSONResponse:
        if runtime.service is not None:
            body = runtime.service.contract()
        else:
            codex = baseline_codex()
            body = {
                "schema": "szl.oro-runtime-contract/v1",
                "rank_schema": "szl.oro-rank/v1",
                "codex": codex.as_dict(),
                "codex_digest": codex.digest,
                "roles": [role.__dict__ for role in role_cells()],
                "release_effector": "ABSENT",
                "normal_termination": "STRUCTURAL_RANK_DECREASE",
                "runtime_enforced": "NOT_MEASURED",
                "well_founded_termination": "MODELED",
                "machine_checked_termination": "NOT_PROVED",
                "global_action_optimality": "NOT_CLAIMED",
            }
        return JSONResponse(body)

    @router.get(f"{api}/roles")
    async def roles() -> JSONResponse:
        return JSONResponse({"schema": API_SCHEMA, "items": [role.__dict__ for role in role_cells()]})

    @router.get(f"{api}/counts")
    async def counts() -> JSONResponse:
        service = runtime.require_service()
        return JSONResponse({"schema": API_SCHEMA, **service.store.counts()})

    @router.post(f"{api}/plans", status_code=201)
    async def create_plan(request: Request) -> JSONResponse:
        runtime.authorize_write(request)
        payload = await _read_json(request)
        plan = runtime.require_service().create_plan(payload)
        return JSONResponse({"schema": API_SCHEMA, "accepted": True, "plan": plan}, status_code=201)

    @router.get(f"{api}/plans")
    async def list_plans(limit: int = Query(100, ge=1, le=500)) -> JSONResponse:
        items = runtime.require_service().store.list_plans(limit=limit)
        return JSONResponse({"schema": API_SCHEMA, "count": len(items), "items": items})

    @router.get(f"{api}/plans/{{plan_id}}")
    async def get_plan(plan_id: str) -> JSONResponse:
        plan = runtime.require_service().store.get_plan(plan_id)
        if plan is None:
            return _error(404, "plan_not_found", "plan does not exist")
        return JSONResponse({"schema": API_SCHEMA, "plan": plan})

    @router.post(f"{api}/plans/{{plan_id}}/execute")
    async def execute_plan(plan_id: str, request: Request) -> JSONResponse:
        runtime.authorize_write(request)
        payload = await _read_json(request)
        result = runtime.require_service().execute_plan(plan_id, payload)
        return JSONResponse({"schema": API_SCHEMA, "accepted": True, **result})

    @router.get(f"{api}/orbits")
    async def list_orbits(
        plan_id: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ) -> JSONResponse:
        items = runtime.require_service().store.list_orbits(plan_id=plan_id, limit=limit)
        return JSONResponse({"schema": API_SCHEMA, "count": len(items), "items": items})

    @router.get(f"{api}/orbits/{{orbit_id}}")
    async def get_orbit(orbit_id: str) -> JSONResponse:
        service = runtime.require_service()
        orbit = service.store.get_orbit(orbit_id)
        if orbit is None:
            return _error(404, "orbit_not_found", "orbit does not exist")
        return JSONResponse(
            {
                "schema": API_SCHEMA,
                "orbit": orbit,
                "barriers": service.store.list_barriers(orbit_id),
                "certificates": service.store.list_certificates(orbit_id),
                "negative_results": service.store.list_negative_results(orbit_id=orbit_id),
            }
        )

    @router.get(f"{api}/orbits/{{orbit_id}}/barriers")
    async def list_barriers(
        orbit_id: str,
        limit: int = Query(200, ge=1, le=1000),
    ) -> JSONResponse:
        items = runtime.require_service().store.list_barriers(orbit_id, limit=limit)
        return JSONResponse({"schema": API_SCHEMA, "count": len(items), "items": items})

    @router.get(f"{api}/barriers/{{barrier_id}}")
    async def get_barrier(barrier_id: str) -> JSONResponse:
        barrier = runtime.require_service().store.get_barrier(barrier_id)
        if barrier is None:
            return _error(404, "barrier_not_found", "barrier does not exist")
        return JSONResponse({"schema": API_SCHEMA, "barrier": barrier})

    @router.post(f"{api}/barriers/{{barrier_id}}/approvals")
    async def approve_barrier(barrier_id: str, request: Request) -> JSONResponse:
        approver = runtime.authorize_write(request)
        payload = await _read_json(request)
        if set(payload) != {"approval"}:
            raise OROContractError("approval body requires exactly approval")
        if not isinstance(payload["approval"], Mapping):
            raise OROContractError("approval must be an object")
        result = runtime.require_service().store.approve(
            barrier_id=barrier_id,
            approver=approver,
            approval=payload["approval"],
        )
        return JSONResponse({"schema": API_SCHEMA, "accepted": True, "approval": result})

    @router.get(f"{api}/negative-results")
    async def negative_results(
        orbit_id: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
    ) -> JSONResponse:
        items = runtime.require_service().store.list_negative_results(
            orbit_id=orbit_id,
            limit=limit,
        )
        return JSONResponse({"schema": API_SCHEMA, "count": len(items), "items": items})

    @router.get(f"{api}/orbits/{{orbit_id}}/certificates")
    async def certificates(
        orbit_id: str,
        limit: int = Query(200, ge=1, le=1000),
    ) -> JSONResponse:
        items = runtime.require_service().store.list_certificates(orbit_id, limit=limit)
        return JSONResponse({"schema": API_SCHEMA, "count": len(items), "items": items})

    return router


def _install_handlers(application: FastAPI) -> None:
    @application.exception_handler(OROAuthorizationError)
    async def authorization_error(
        _request: Request, exc: OROAuthorizationError
    ) -> JSONResponse:
        return _error(
            401,
            "authorization_failed",
            str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @application.exception_handler(OROAuthorizerUnavailable)
    async def authorizer_error(
        _request: Request, _exc: OROAuthorizerUnavailable
    ) -> JSONResponse:
        return _error(503, "authorizer_unavailable", "managed write authorizer is unavailable")

    @application.exception_handler(ORORuntimeUnavailable)
    async def runtime_error(
        _request: Request, _exc: ORORuntimeUnavailable
    ) -> JSONResponse:
        return _error(503, "runtime_unavailable", "required ORO runtime dependency is unavailable")

    @application.exception_handler(OROContractError)
    async def contract_error(_request: Request, exc: OROContractError) -> JSONResponse:
        return _error(422, "contract_violation", str(exc))

    @application.exception_handler(OROSignerUnavailable)
    async def signer_error(
        _request: Request, _exc: OROSignerUnavailable
    ) -> JSONResponse:
        return _error(503, "signer_unavailable", "managed signer is unavailable")

    @application.exception_handler(OROStateError)
    async def state_error(_request: Request, exc: OROStateError) -> JSONResponse:
        return _error(409, "state_conflict", str(exc))


def mount_oro(
    application: FastAPI,
    *,
    namespace: str = "a11oy",
    runtime: ORORuntime | None = None,
) -> ORORuntime:
    selected = runtime or ORORuntime()
    application.include_router(build_router(selected, namespace=namespace))
    application.state.oro_runtime = selected
    _install_handlers(application)
    # FastAPI 0.139 removed the application-level add_event_handler shim while
    # retaining Starlette's router-owned lifecycle callback list.
    application.router.on_shutdown.append(selected.close)

    return selected


def create_app() -> FastAPI:
    application = FastAPI(
        title="A11oy ORO Control Plane",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/a11oy/v1/oro/openapi.json",
    )
    mount_oro(application)

    @application.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/oro", status_code=307)

    return application
