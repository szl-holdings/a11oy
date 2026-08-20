#!/usr/bin/env python3
"""Apply the bounded ORO v3 durable-state and authorization repairs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_store() -> None:
    path = ROOT / "oro/store.py"
    replace_once(
        path,
        '''                    CREATE TABLE orbit_runs (
                        orbit_id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL REFERENCES plans(plan_id),
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        status TEXT NOT NULL CHECK(status IN ('RUNNING','CONTINUE','COMPLETE','REFUSED')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    ) STRICT;''',
        '''                    CREATE TABLE orbit_runs (
                        orbit_id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL REFERENCES plans(plan_id),
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        current_rank_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETE','REFUSED')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    ) STRICT;''',
        "durable orbit schema",
    )
    replace_once(
        path,
        '''    def create_orbit(self, *, orbit_id: str, plan_id: str, generation: int) -> Mapping[str, Any]:
        now = utc_now()
        with self._lock:
            existing = self.connection.execute(
                "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
            ).fetchone()
            if existing is not None:
                if existing["plan_id"] != plan_id or int(existing["generation"]) != generation:
                    raise OROStateError("orbit ID already exists with different identity")
                return dict(existing)
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute(
                    "INSERT INTO orbit_runs VALUES (?, ?, ?, 'RUNNING', ?, ?)",
                    (orbit_id, plan_id, generation, now, now),
                )
                self.connection.execute(
                    "UPDATE plans SET status='RUNNING', updated_at=? WHERE plan_id=?",
                    (now, plan_id),
                )
                self.connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self.connection.execute("ROLLBACK")
                raise OROStateError("orbit persistence failed") from exc
        return self.get_orbit(orbit_id) or {}

    def get_orbit(self, orbit_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_orbits(self, *, plan_id: str | None = None, limit: int = 100) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            if plan_id:
                rows = self.connection.execute(
                    "SELECT * FROM orbit_runs WHERE plan_id=? ORDER BY created_at DESC LIMIT ?",
                    (plan_id, limit),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    "SELECT * FROM orbit_runs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(row) for row in rows]
''',
        '''    def create_orbit(
        self,
        *,
        orbit_id: str,
        plan_id: str,
        generation: int,
        rank: Rank,
    ) -> Mapping[str, Any]:
        now = utc_now()
        encoded_rank = canonical_json(rank.as_dict()).decode("utf-8")
        with self._lock:
            existing = self.connection.execute(
                "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
            ).fetchone()
            if existing is not None:
                if (
                    existing["plan_id"] != plan_id
                    or int(existing["generation"]) != generation
                    or existing["current_rank_json"] != encoded_rank
                    or existing["status"] != "RUNNING"
                ):
                    raise OROStateError("orbit ID already exists with a different durable frontier")
                return self._decode(existing, "current_rank_json") or {}
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute(
                    "INSERT INTO orbit_runs "
                    "(orbit_id, plan_id, generation, current_rank_json, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'RUNNING', ?, ?)",
                    (orbit_id, plan_id, generation, encoded_rank, now, now),
                )
                self.connection.execute(
                    "UPDATE plans SET status='RUNNING', updated_at=? WHERE plan_id=?",
                    (now, plan_id),
                )
                self.connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self.connection.execute("ROLLBACK")
                raise OROStateError("orbit persistence failed") from exc
        return self.get_orbit(orbit_id) or {}

    def get_orbit(self, orbit_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
            ).fetchone()
        return self._decode(row, "current_rank_json")

    def list_orbits(self, *, plan_id: str | None = None, limit: int = 100) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            if plan_id:
                rows = self.connection.execute(
                    "SELECT * FROM orbit_runs WHERE plan_id=? ORDER BY created_at DESC LIMIT ?",
                    (plan_id, limit),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    "SELECT * FROM orbit_runs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._decode(row, "current_rank_json") or {} for row in rows]
''',
        "durable orbit methods",
    )
    replace_once(
        path,
        '''        status = "REFUSED" if decision.decision == "REFUSE" else decision.decision
''',
        '''        status_by_decision = {
            "CONTINUE": "RUNNING",
            "COMPLETE": "COMPLETE",
            "REFUSE": "REFUSED",
        }
        status = status_by_decision[decision.decision]
        next_generation = (
            decision.generation + 1 if decision.decision == "CONTINUE" else decision.generation
        )
        encoded_rank_after = canonical_json(decision.rank_after.as_dict()).decode("utf-8")
''',
        "barrier status mapping",
    )
    replace_once(
        path,
        '''                self.connection.execute(
                    "UPDATE orbit_runs SET status=?, updated_at=? WHERE orbit_id=?",
                    (status, now, decision.orbit_id),
                )
''',
        '''                cursor = self.connection.execute(
                    "UPDATE orbit_runs "
                    "SET generation=?, current_rank_json=?, status=?, updated_at=? "
                    "WHERE orbit_id=? AND generation=? AND status='RUNNING'",
                    (
                        next_generation,
                        encoded_rank_after,
                        status,
                        now,
                        decision.orbit_id,
                        decision.generation,
                    ),
                )
                if cursor.rowcount != 1:
                    raise OROStateError("barrier does not match the durable orbit frontier")
''',
        "atomic durable frontier update",
    )


def patch_service() -> None:
    path = ROOT / "oro/service.py"
    replace_once(
        path,
        '''        parse_utc(raw["expires_at"])
        rank_before = Rank.parse(body["rank"])
        rank_after = Rank.parse(raw["rank_after"])
''',
        '''        parse_utc(raw["expires_at"])
        if plan["status"] in {"COMPLETE", "REFUSED"}:
            raise OROStateError("plan is terminal and cannot execute another barrier")
        durable_orbit = self.store.get_orbit(orbit_id)
        if durable_orbit is None:
            if generation != 0:
                raise OROStateError("new orbit must begin at generation zero")
            rank_before = Rank.parse(body["rank"])
        else:
            if durable_orbit["plan_id"] != plan_id:
                raise OROStateError("orbit is bound to a different plan")
            if durable_orbit["status"] != "RUNNING":
                raise OROStateError("orbit is terminal and cannot execute another barrier")
            if int(durable_orbit["generation"]) != generation:
                raise OROStateError("execution generation does not match durable orbit generation")
            rank_before = Rank.parse(durable_orbit["current_rank"])
        rank_after = Rank.parse(raw["rank_after"])
''',
        "durable execution frontier",
    )
    replace_once(
        path,
        '''        self.store.create_orbit(orbit_id=orbit_id, plan_id=plan_id, generation=generation)
''',
        '''        self.store.create_orbit(
            orbit_id=orbit_id,
            plan_id=plan_id,
            generation=generation,
            rank=rank_before,
        )
''',
        "rank-bound orbit creation",
    )


def patch_auth() -> None:
    path = ROOT / "oro/auth.py"
    replace_once(
        path,
        '''class OROAuthorizerUnavailable(OROStateError):
    """The governed write-authorization boundary is unavailable."""


class BearerTokenAuthorizer:
''',
        '''class OROAuthorizerUnavailable(OROStateError):
    """The governed write-authorization boundary is unavailable."""


class OROAuthorizationError(OROContractError):
    """A governed write request did not present valid bearer authority."""


class BearerTokenAuthorizer:
''',
        "authorization error type",
    )
    replace_once(
        path,
        '''    def authorize(self, request: Request) -> None:
        header = request.headers.get("authorization", "")
        scheme, separator, supplied = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not supplied:
            raise OROContractError("a Bearer authorization header is required")
        try:
            supplied_bytes = supplied.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise OROContractError("authorization token is malformed") from exc
        if not secrets.compare_digest(supplied_bytes, self._token):
            raise OROContractError("authorization token is invalid")
''',
        '''    def authorize(self, request: Request) -> str:
        header = request.headers.get("authorization", "")
        scheme, separator, supplied = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not supplied:
            raise OROAuthorizationError("a Bearer authorization header is required")
        try:
            supplied_bytes = supplied.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise OROAuthorizationError("authorization token is malformed") from exc
        if not secrets.compare_digest(supplied_bytes, self._token):
            raise OROAuthorizationError("authorization token is invalid")
        return self._token_id
''',
        "bearer identity return",
    )
    replace_once(
        path,
        '''    if not production and os.environ.get("SZL_ORO_ALLOW_UNAUTHENTICATED_WRITES") == "1":
        return BearerTokenAuthorizer.development()
''',
        '''    if not production and os.environ.get("SZL_ORO_ALLOW_DEVELOPMENT_AUTH") == "1":
        return BearerTokenAuthorizer.development()
''',
        "development auth opt-in",
    )


def patch_api() -> None:
    path = ROOT / "oro/api.py"
    replace_once(path, "from fastapi import APIRouter, FastAPI, Request\n", "from fastapi import APIRouter, FastAPI, Query, Request\n", "bounded query import")
    replace_once(
        path,
        "from .core import OROContractError, OROSignerUnavailable, OROStateError\n",
        '''from .auth import (
    BearerTokenAuthorizer,
    OROAuthorizationError,
    OROAuthorizerUnavailable,
    authorizer_from_environment,
)
from .core import OROContractError, OROSignerUnavailable, OROStateError
''',
        "auth imports",
    )
    replace_once(path, "        self.service: OROService | None = None\n        self.error: Exception | None = None\n", "        self.service: OROService | None = None\n        self.authorizer: BearerTokenAuthorizer | None = None\n        self.error: Exception | None = None\n", "runtime authorizer field")
    replace_once(
        path,
        '''            self.store = OROStore(db_path, production=self.production)
            signer = signer_from_environment(production=self.production)
            self.service = OROService(
''',
        '''            self.store = OROStore(db_path, production=self.production)
            signer = signer_from_environment(production=self.production)
            self.authorizer = authorizer_from_environment(production=self.production)
            if self.production and self.authorizer is None:
                raise OROAuthorizerUnavailable("managed write authorizer is unavailable")
            self.service = OROService(
''',
        "runtime authorizer initialization",
    )
    replace_once(path, '            "service_initialized": self.service is not None,\n', '            "service_initialized": self.service is not None,\n            "write_authorizer_initialized": self.authorizer is not None,\n', "health authorizer state")
    replace_once(path, '                "reason": str(self.error) if self.error is not None else "ORO service is unavailable",\n', '                "reason": "required ORO runtime dependency is unavailable",\n', "bounded readiness reason")
    replace_once(
        path,
        '''        body = {"schema": API_SCHEMA, **self.service.readiness()}
        return (200 if body["ready"] else 503), body

    def require_service(self) -> OROService:
        if self.service is None:
            raise OROSignerUnavailable(
                str(self.error) if self.error is not None else "ORO service is unavailable"
            )
        return self.service
''',
        '''        body = {"schema": API_SCHEMA, **self.service.readiness()}
        body["write_authorizer"] = (
            dict(self.authorizer.identity)
            if self.authorizer is not None
            else {"state": "UNAVAILABLE"}
        )
        body["ready"] = bool(body["ready"] and (self.authorizer is not None or not self.production))
        body["state"] = "READY" if body["ready"] else "UNAVAILABLE"
        return (200 if body["ready"] else 503), body

    def require_service(self) -> OROService:
        if self.service is None:
            raise OROSignerUnavailable("required ORO runtime dependency is unavailable")
        return self.service

    def authorize_write(self, request: Request) -> str:
        if self.authorizer is None:
            raise OROAuthorizerUnavailable("managed write authorizer is unavailable")
        return self.authorizer.authorize(request)
''',
        "runtime write authorization",
    )
    replace_once(path, "def _error(status: int, code: str, message: str) -> JSONResponse:\n    return JSONResponse(\n", "def _error(\n    status: int,\n    code: str,\n    message: str,\n    *,\n    headers: Mapping[str, str] | None = None,\n) -> JSONResponse:\n    return JSONResponse(\n", "error headers signature")
    replace_once(path, "        status_code=status,\n    )\n", "        status_code=status,\n        headers=dict(headers or {}),\n    )\n", "error headers output")
    replace_once(path, "    async def create_plan(request: Request) -> JSONResponse:\n        payload = await _read_json(request)\n", "    async def create_plan(request: Request) -> JSONResponse:\n        runtime.authorize_write(request)\n        payload = await _read_json(request)\n", "create-plan authorization")
    replace_once(path, "async def list_plans(limit: int = 100) -> JSONResponse:", "async def list_plans(limit: int = Query(100, ge=1, le=500)) -> JSONResponse:", "plan query bound")
    replace_once(path, "    async def execute_plan(plan_id: str, request: Request) -> JSONResponse:\n        payload = await _read_json(request)\n", "    async def execute_plan(plan_id: str, request: Request) -> JSONResponse:\n        runtime.authorize_write(request)\n        payload = await _read_json(request)\n", "execute authorization")
    replace_once(path, "async def list_orbits(plan_id: str | None = None, limit: int = 100) -> JSONResponse:", "async def list_orbits(\n        plan_id: str | None = None,\n        limit: int = Query(100, ge=1, le=500),\n    ) -> JSONResponse:", "orbit query bound")
    replace_once(path, "async def list_barriers(orbit_id: str, limit: int = 200) -> JSONResponse:", "async def list_barriers(\n        orbit_id: str,\n        limit: int = Query(200, ge=1, le=1000),\n    ) -> JSONResponse:", "barrier query bound")
    replace_once(
        path,
        '''    async def approve_barrier(barrier_id: str, request: Request) -> JSONResponse:
        payload = await _read_json(request)
        if set(payload) != {"approver", "approval"}:
            raise OROContractError("approval body requires exactly approver and approval")
        if not isinstance(payload["approver"], str) or not payload["approver"].strip():
            raise OROContractError("approver must be a non-empty string")
        if not isinstance(payload["approval"], Mapping):
            raise OROContractError("approval must be an object")
        result = runtime.require_service().store.approve(
            barrier_id=barrier_id,
            approver=payload["approver"].strip(),
            approval=payload["approval"],
        )
''',
        '''    async def approve_barrier(barrier_id: str, request: Request) -> JSONResponse:
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
''',
        "identity-bound approval",
    )
    replace_once(path, "async def negative_results(orbit_id: str | None = None, limit: int = 200) -> JSONResponse:", "async def negative_results(\n        orbit_id: str | None = None,\n        limit: int = Query(200, ge=1, le=1000),\n    ) -> JSONResponse:", "negative query bound")
    replace_once(path, "async def certificates(orbit_id: str, limit: int = 200) -> JSONResponse:", "async def certificates(\n        orbit_id: str,\n        limit: int = Query(200, ge=1, le=1000),\n    ) -> JSONResponse:", "certificate query bound")
    tail = path.read_text(encoding="utf-8")
    marker = "def mount_oro(app: FastAPI, *, namespace: str = \"a11oy\", runtime: ORORuntime | None = None) -> ORORuntime:\n"
    if tail.count(marker) != 1:
        raise RuntimeError("API tail marker is not unique")
    prefix = tail.split(marker, 1)[0]
    replacement = '''def _install_handlers(application: FastAPI) -> None:
    @application.exception_handler(OROAuthorizationError)
    async def authorization_error(_request: Request, exc: OROAuthorizationError) -> JSONResponse:
        return _error(401, "authorization_failed", str(exc), headers={"WWW-Authenticate": "Bearer"})

    @application.exception_handler(OROAuthorizerUnavailable)
    async def authorizer_error(_request: Request, _exc: OROAuthorizerUnavailable) -> JSONResponse:
        return _error(503, "authorizer_unavailable", "managed write authorizer is unavailable")

    @application.exception_handler(OROContractError)
    async def contract_error(_request: Request, exc: OROContractError) -> JSONResponse:
        return _error(422, "contract_violation", str(exc))

    @application.exception_handler(OROSignerUnavailable)
    async def signer_error(_request: Request, _exc: OROSignerUnavailable) -> JSONResponse:
        return _error(503, "signer_unavailable", "managed signer is unavailable")

    @application.exception_handler(OROStateError)
    async def state_error(_request: Request, exc: OROStateError) -> JSONResponse:
        return _error(409, "state_conflict", str(exc))


def mount_oro(application: FastAPI, *, namespace: str = "a11oy", runtime: ORORuntime | None = None) -> ORORuntime:
    selected = runtime or ORORuntime()
    application.include_router(build_router(selected, namespace=namespace))
    application.state.oro_runtime = selected
    _install_handlers(application)

    @application.on_event("shutdown")
    async def close_runtime() -> None:
        selected.close()

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


app = create_app()
'''
    path.write_text(prefix + replacement, encoding="utf-8")


def patch_compose() -> None:
    path = ROOT / "deploy/oro/compose.yaml"
    replace_once(path, "      SZL_ORO_SIGNING_KEY_ID: ${SZL_ORO_SIGNING_KEY_ID:?set a managed key ID}\n", "      SZL_ORO_SIGNING_KEY_ID: ${SZL_ORO_SIGNING_KEY_ID:?set a managed key ID}\n      SZL_ORO_API_TOKEN_PATH: /run/secrets/oro_api_token\n      SZL_ORO_API_TOKEN_ID: ${SZL_ORO_API_TOKEN_ID:?set a managed operator ID}\n", "compose auth environment")
    replace_once(path, "      - source: oro_signing_key\n        target: oro_signing_key\n", "      - source: oro_signing_key\n        target: oro_signing_key\n      - source: oro_api_token\n        target: oro_api_token\n", "compose auth secret mount")
    replace_once(path, "secrets:\n  oro_signing_key:\n    external: true\n", "secrets:\n  oro_signing_key:\n    external: true\n  oro_api_token:\n    external: true\n", "compose auth secret declaration")


def patch_tests() -> None:
    path = ROOT / "tests/test_oro_operational_v3.py"
    replace_once(path, 'EXPIRES_AT = "2030-01-01T00:00:00.000Z"\n', 'EXPIRES_AT = "2030-01-01T00:00:00.000Z"\nDEVELOPMENT_TOKEN = "oro-development-explicit-authorization-token"\nAUTH_HEADERS = {"Authorization": f"Bearer {DEVELOPMENT_TOKEN}"}\n', "test auth constants")
    text = path.read_text(encoding="utf-8")
    text = text.replace('    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")\n    application = create_app()\n', '    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")\n    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")\n    application = create_app()\n')
    text = text.replace('client.post("/api/a11oy/v1/oro/plans", json=plan)', 'client.post("/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS)')
    text = text.replace('            json=execution_payload(orbit_id="http-orbit", barrier_id="http-barrier", objective_converged=True),\n        )', '            json=execution_payload(orbit_id="http-orbit", barrier_id="http-barrier", objective_converged=True),\n            headers=AUTH_HEADERS,\n        )')
    text = text.replace('headers={"Content-Type": "application/json"}', 'headers={"Content-Type": "application/json", **AUTH_HEADERS}')
    text = text.replace('headers={"Content-Type": "application/x-www-form-urlencoded"}', 'headers={"Content-Type": "application/x-www-form-urlencoded", **AUTH_HEADERS}')
    marker = '\ndef test_production_fails_ready_when_managed_signer_is_absent(\n'
    if text.count(marker) != 1:
        raise RuntimeError("test insertion marker is not unique")
    insertion = '''

def test_write_routes_require_valid_bearer_authority(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "auth.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        plan = plan_payload(application.state.oro_runtime.service, plan_id="auth-plan")
        missing = client.post("/api/a11oy/v1/oro/plans", json=plan)
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"
        invalid = client.post("/api/a11oy/v1/oro/plans", json=plan, headers={"Authorization": "Bearer invalid"})
        assert invalid.status_code == 401
        accepted = client.post("/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS)
        assert accepted.status_code == 201


def test_http_approval_identity_comes_from_bearer_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "approval.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        plan = plan_payload(application.state.oro_runtime.service, plan_id="approval-plan")
        assert client.post("/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS).status_code == 201
        execution = client.post(
            "/api/a11oy/v1/oro/plans/approval-plan/execute",
            json=execution_payload(orbit_id="approval-orbit", barrier_id="approval-barrier", objective_converged=True),
            headers=AUTH_HEADERS,
        )
        assert execution.status_code == 200
        spoofed = client.post(
            "/api/a11oy/v1/oro/barriers/approval-barrier/approvals",
            json={"approver": "spoofed", "approval": {"decision": "approve"}},
            headers=AUTH_HEADERS,
        )
        assert spoofed.status_code == 422
        approved = client.post(
            "/api/a11oy/v1/oro/barriers/approval-barrier/approvals",
            json={"approval": {"decision": "approve"}},
            headers=AUTH_HEADERS,
        )
        assert approved.status_code == 200
        assert approved.json()["approval"]["approver"] == "oro-development"


def test_terminal_orbit_cannot_execute_again(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    service.execute_plan("plan-1", execution_payload(objective_converged=True))
    with pytest.raises(Exception, match="terminal"):
        service.execute_plan("plan-1", execution_payload(barrier_id="after-terminal", generation=0))
    service.store.close()
'''
    path.write_text(text.replace(marker, insertion + marker, 1), encoding="utf-8")


def main() -> None:
    patch_store()
    patch_service()
    patch_auth()
    patch_api()
    patch_compose()
    patch_tests()


if __name__ == "__main__":
    main()
