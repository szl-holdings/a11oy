#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Deny-by-default caller identity for code execution, tool use and state writes.

Taxonomy home: governance/.

Two server-held secrets, never request bodies, decide who may act:

* operator  — ``Authorization: Bearer <A11OY_CODE_ADMIN_KEY>``
* second approver — ``X-A11oy-Second-Approver: <A11OY_CODE_SECOND_APPROVER_KEY>``,
  a distinct secret; ``two_person_attested`` is true only when both are present
  and verify.

``two_person_attested`` means two distinct secrets arrived in ONE request. It is a
two-person control only if custody of the two keys is actually split between two
people; it is not cryptographic co-signing and does not identify who sent it.

When a secret is not configured on the Space, the corresponding role cannot be
held by anyone: execution routes answer an honest BLOCKED instead of running.

Covered surfaces (see KNOWN_GOTCHAS.md section 9): the ``/api/a11oy/code/*`` router
(run, kernel exec, tools, RAG writes, profiles, conversation history, agent run and
stream, key issue), code-as-action compose/revise, the ReAct write routes, and every
caller of ``a11oy_code_engine.governed_turn`` — the engine only reaches its sandbox
when a caller passes ``allow_exec=True`` (see :func:`exec_permitted`).
"""
import hmac
import os
from typing import Mapping, Optional

OPERATOR_KEY_ENV = "A11OY_CODE_ADMIN_KEY"
SECOND_APPROVER_KEY_ENV = "A11OY_CODE_SECOND_APPROVER_KEY"
SECOND_APPROVER_HEADER = "x-a11oy-second-approver"


def bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.strip().partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def secret_matches(presented: Optional[str], env_name: str) -> bool:
    expected = (os.environ.get(env_name) or "").strip()
    presented = (presented or "").strip()
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def principal_from_headers(headers: Mapping[str, str]) -> dict:
    """Resolve {operator, two_person_attested} from request headers only."""
    lowered = {str(k).lower(): v for k, v in headers.items()}
    bearer = bearer_token(lowered.get("authorization"))
    operator = secret_matches(bearer, OPERATOR_KEY_ENV)
    second = (lowered.get(SECOND_APPROVER_HEADER) or "").strip()
    # The same secret presented twice is one person, not two.
    two_person = (
        operator
        and bool(second)
        and not hmac.compare_digest(second.encode("utf-8"), bearer.encode("utf-8"))
        and secret_matches(second, SECOND_APPROVER_KEY_ENV)
    )
    return {"operator": operator, "two_person_attested": bool(two_person)}


def principal(request) -> dict:
    return principal_from_headers(request.headers)


def exec_permitted(request) -> bool:
    """True only for a two-person-attested caller; any resolver error denies."""
    try:
        return bool(principal(request)["two_person_attested"])
    except Exception:
        return False


def blocked_body(action: str, needs_second_approver: bool = False) -> dict:
    need = (
        f"the operator credential (Authorization: Bearer <{OPERATOR_KEY_ENV}>) and a "
        f"distinct second approver ({SECOND_APPROVER_HEADER}: <{SECOND_APPROVER_KEY_ENV}>)"
        if needs_second_approver
        else f"the operator credential (Authorization: Bearer <{OPERATOR_KEY_ENV}>)"
    )
    configured = bool((os.environ.get(OPERATOR_KEY_ENV) or "").strip())
    if needs_second_approver:
        configured = configured and bool((os.environ.get(SECOND_APPROVER_KEY_ENV) or "").strip())
    return {
        "ok": False,
        "status": "BLOCKED",
        "error": f"{action} requires {need}. Anonymous callers are denied by default.",
        "credential_configured": configured,
    }


# ---------------------------------------------------------------------------
# Route-level gate (defence in depth, one table for the whole app).
#
# Every entry below is a route that can execute code, dispatch an agent or a tool
# with side effects, sign a caller-supplied payload with the server key, or write
# server state. A request whose method is not GET/HEAD/OPTIONS and whose path
# matches is answered 401 BLOCKED before any handler runs — no code, tool call,
# model call or state write happens — unless it carries the operator Bearer.
# Handlers keep their own checks (execution still needs the second approver);
# this table only makes the anonymous refusal uniform and independent of which
# module registered the route, or in which order.
#
# Read-only GET routes are never gated here. Routes that already enforce their
# own credential registry (GDW, eval-arena rerun, ouroboros run-all, immune
# lorenz, compute jobs, numerics dataset ingest, wire-D probe, deva/devb/vertical
# govern, agent cycle, the OpenAI-compatible API-key surface, loopback-only brain
# refresh) are deliberately left to that registry and are not listed.
# ---------------------------------------------------------------------------
import json as _json
import re as _re

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# (path regex, action label, category). Paths are matched after collapsing
# repeated slashes and dropping one trailing slash.
PROTECTED_ROUTES = (
    # -- code execution --------------------------------------------------------
    (r"/api/a11oy/code/run", "Code execution", "exec"),
    (r"/api/a11oy/code/kernel/[^/]+/exec", "Kernel execution", "exec"),
    (r"/api/a11oy/v1/code/(run|turn|consensus|plan|runstep|approve)", "Governed code turn", "exec"),
    (r"/api/a11oy/v1/agentloop/run", "Governed agent loop", "exec"),
    (r"/api/a11oy/v1/verify/transcript", "Transcript build (POST runs the loop)", "exec"),
    (r"/api/a11oy/v1/agent/code/(compose|revise|inspect)", "Code-as-action", "exec"),
    # -- agents and tools with side effects -------------------------------------
    (r"/api/a11oy/code/agent/(run|stream)", "Agent run", "tool"),
    (r"/api/a11oy/code/rag/(index|refresh|seed)", "RAG writes", "state"),
    (r"/api/a11oy/code/profile/[^/]+", "Profile writes", "state"),
    (r"/api/a11oy/code/v1/keys", "API key issue", "state"),
    (r"/api/a11oy/code/voice/stt", "Speech-to-text (server HF token)", "tool"),
    (r"/api/a11oy/v1/agent/react/(run|resume|reflect|memory/add|skills/admit)", "ReAct writes", "tool"),
    (r"/api/a11oy/v1/agent/resume", "ReAct resume", "tool"),
    (r"/api/a11oy/v1/agent/loop", "Agent tool loop", "tool"),
    (r"/api/a11oy/v1/mcp/call", "MCP tool call", "tool"),
    (r"/api/a11oy/v4/command", "Operator shell command", "tool"),
    (r"/api/a11oy/v1/operator/act", "Operator action", "tool"),
    (r"/api/a11oy/v1/companion/act", "Operator action", "tool"),
    (r"/api/a11oy/v2/operator/command", "Operator command loop", "tool"),
    (r"/api/a11oy/v1/companion/evolve", "Companion strategy change", "state"),
    (r"/api/a11oy/v1/connectors/[^/]+/write", "Connector write", "tool"),
    (r"/api/a11oy/v4/bridge/(hermes|openclaw)", "External agent bridge", "tool"),
    (r"/api/a11oy/v1/factory/run", "Factory workflow run", "state"),
    # -- signing a caller-supplied payload with the server key ------------------
    (r"/khipu/sign", "Receipt signing", "sign"),
    (r"/api/a11oy/khipu/sign", "Receipt signing", "sign"),
    (r"/api/a11oy/v1/brain/receipt/sign", "Receipt signing", "sign"),
    (r"/api/a11oy/v1/provenance/pqc/sign", "Receipt signing", "sign"),
    (r"/api/a11oy/v1/restraint/evaluate", "Restraint receipt signing", "sign"),
    # -- control plane and persistent writes ------------------------------------
    (r"(/api/a11oy)?/v1/energy/operator/(start|stop)", "Energy operator control", "state"),
    (r"/api/a11oy/v1/spend/(record|cap)", "Spend ledger writes", "state"),
    (r"/api/a11oy/v1/constitution/(state|ontology|memory|ledger)", "Constitution writes", "state"),
    (r"/api/a11oy/v1/khipu-os/(checkpoint|archive)", "Khipu OS checkpoint/archive", "state"),
    (r"/api/a11oy/v1/be/khipu/append", "Khipu append", "state"),
    (r"/api/a11oy/v1/wires/inject", "Cross-Space wire injection", "state"),
    (r"/api/a11oy/v4/inbox", "Organ inbox writes", "state"),
    (r"/api/a11oy/v1/provenance/(anchor/anchor|govern)", "Public-ledger anchor", "state"),
    (r"/api/a11oy/wasi-rikuq/chaos", "Chaos experiment scheduling", "state"),
    (r"/api/a11oy/v1/gov/calibration/log", "Calibration log writes", "state"),
    (r"/api/a11oy/v1/research/(prereg|trial)", "Research registry writes", "state"),
    (r"/api/a11oy/v1/brain/audit/record", "Brain audit writes", "state"),
    (r"/api/a11oy/v1/llm/forum/ingest", "LLM forum ingest", "state"),
    (r"(/api/lake/v1|/v1/lake)/receipts", "Lake receipt ingest", "state"),
    (r"/api/a11oy/v1/series-a/(refresh|passports/(evaluate|execute))", "Series-A passport writes", "state"),
)

_COMPILED_ROUTES = tuple(
    (_re.compile(r"\A" + pattern + r"\Z"), action, category)
    for pattern, action, category in PROTECTED_ROUTES
)


def _normalise_path(path: str) -> str:
    path = _re.sub(r"/{2,}", "/", path or "/")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def protected_action(method: str, path: str) -> Optional[tuple]:
    """(action, category) when this request needs the operator, else None."""
    if (method or "").upper() in _SAFE_METHODS:
        return None
    norm = _normalise_path(path)
    for rx, action, category in _COMPILED_ROUTES:
        if rx.match(norm):
            return action, category
    return None


class OperatorGateMiddleware:
    """Pure ASGI gate: answers 401 BLOCKED for a protected route without the operator
    Bearer. Nothing downstream runs; the request body is never read. Any resolver
    error denies."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        hit = protected_action(scope.get("method", ""), scope.get("path", ""))
        if hit is None:
            await self.app(scope, receive, send)
            return
        try:
            headers = {}
            for key, value in scope.get("headers") or []:
                headers[key.decode("latin-1")] = value.decode("latin-1")
            allowed = bool(principal_from_headers(headers)["operator"])
        except Exception:
            allowed = False
        if allowed:
            await self.app(scope, receive, send)
            return
        body = _json.dumps(blocked_body(hit[0]), separators=(",", ":")).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"www-authenticate", b"Bearer"),
                (b"cache-control", b"no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": body})


def install_gate(app) -> bool:
    """Install the gate as the innermost middleware (after CORS, security headers and
    metrics, so a refusal still carries them). Idempotent."""
    from starlette.middleware import Middleware

    for existing in getattr(app, "user_middleware", []):
        if getattr(existing, "cls", None) is OperatorGateMiddleware:
            return False
    app.user_middleware.append(Middleware(OperatorGateMiddleware))
    app.middleware_stack = None  # rebuilt on the next request
    return True


def operator_refusal(request, action: str):
    """Handler-level twin of the gate: a 401 BLOCKED JSONResponse for a caller
    without the operator Bearer, else None. Any resolver error refuses."""
    try:
        if principal(request)["operator"]:
            return None
    except Exception:
        pass
    from starlette.responses import JSONResponse

    return JSONResponse(blocked_body(action), status_code=401,
                        headers={"WWW-Authenticate": "Bearer"})
