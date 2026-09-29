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
