#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bearer authentication and corpus scope for the org-RAG lexical reference.

Services layer. It adds no credential system: identity is the existing
``gdw_auth`` principal (``owner_id`` plus ``key_id``) and the tenant is that
principal's ``namespace``. The admitted namespace and its corpus scope are read
only from controller configuration. Query parameters, headers and request bodies
never name the tenant, principal or corpus.

One tenant is admitted. Its corpus scope is one exact ``repo`` (applied by the
engine's own SQL filter before any row is read) and a closed set of exact
``source`` identifiers that every released citation must match. This is an access
contract on one read mode over a shared store, not tenant storage isolation.

Only the version-1 credential registry, whose entries carry explicit scopes, is
accepted. The legacy principal format derives scopes from fixed user/admin roles
that never include the read scope, so a principal-only configuration is reported
as unconfigured (``LEGACY_PRINCIPALS_CANNOT_GRANT_SCOPE``) instead of advertising
an authentication path that can never succeed.

``gdw_auth`` credentials carry no expiry, so session lifecycle is reported as
``NOT_IMPLEMENTED`` rather than inferred.
"""

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

REFERENCE_READ_SCOPE = "rag-reference:read"
CREDENTIALS_ENV = "A11OY_RAG_REFERENCE_CREDENTIALS_JSON"
SCOPE_ENV = "A11OY_RAG_REFERENCE_SCOPE_JSON"
# Shared GDW registry, used only when neither dedicated variable is set.
GDW_CREDENTIALS_ENV = "GDW_CREDENTIALS_JSON"
# Legacy principal-format variables are never loaded here; their presence is
# only detected so the refusal can name its reason.
PRINCIPALS_ENV = "A11OY_RAG_REFERENCE_PRINCIPALS_JSON"
GDW_PRINCIPALS_ENV = "GDW_PRINCIPALS_JSON"

SESSION_EXPIRY = "NOT_IMPLEMENTED"
LIMITATIONS = {
    "session_expiry": SESSION_EXPIRY,
    "tenant_storage_isolation": "NOT_ESTABLISHED",
    "default_mode_read": "UNAUTHENTICATED_OVER_THE_SAME_STORE",
}

# Same rule as gdw_auth's identifiers, so an admitted namespace is one that
# gdw_auth can bind.
_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")
_SCOPE_MAX_BYTES = 64 * 1024
_SOURCES_MAX = 64
_SOURCE_MAX_CHARS = 512
_DENIED_403 = frozenset({"credential_revoked", "foreign_namespace", "missing_scopes"})


class ReferenceScopeError(ValueError):
    """The configured corpus scope is malformed. Messages never echo values."""


@dataclass(frozen=True)
class ReferenceScope:
    namespace: str
    repo: str
    sources: Tuple[str, ...]


@dataclass(frozen=True)
class ReferenceAuthorization:
    owner_id: str
    key_id: str
    namespace: str
    scope: ReferenceScope

    @property
    def repo(self) -> str:
        return self.scope.repo


@dataclass(frozen=True)
class ReferenceRefusal:
    status_code: int
    body: dict
    headers: Optional[dict] = None


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReferenceScopeError("reference scope has duplicate object keys")
        result[key] = value
    return result


def _valid_source(value: Any) -> bool:
    return (type(value) is str and 0 < len(value) <= _SOURCE_MAX_CHARS
            and not any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value))


def parse_reference_scope(text: Any) -> ReferenceScope:
    """Parse ``{"version": 1, "tenants": {<namespace>: {"repo", "sources"}}}``.

    Exactly one tenant is accepted; a multi-tenant reference is not admitted.
    """
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReferenceScopeError("reference scope is not UTF-8 JSON") from exc
    if type(text) is not str or not text.strip():
        raise ReferenceScopeError("reference scope must be non-empty JSON text")
    if len(text.encode("utf-8")) > _SCOPE_MAX_BYTES:
        raise ReferenceScopeError("reference scope is too large")
    try:
        decoded = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ReferenceScopeError:
        raise
    except (TypeError, ValueError) as exc:
        raise ReferenceScopeError("reference scope is not valid JSON") from exc
    if type(decoded) is not dict or set(decoded) != {"version", "tenants"}:
        raise ReferenceScopeError("reference scope has an invalid top-level shape")
    if type(decoded["version"]) is not int or decoded["version"] != 1:
        raise ReferenceScopeError("reference scope version must be 1")
    tenants = decoded["tenants"]
    if type(tenants) is not dict or len(tenants) != 1:
        raise ReferenceScopeError("reference scope must admit exactly one tenant")
    namespace, entry = next(iter(tenants.items()))
    if not _NAMESPACE_PATTERN.fullmatch(namespace):
        raise ReferenceScopeError("tenant namespace must be a canonical lowercase identifier")
    if type(entry) is not dict or set(entry) != {"repo", "sources"}:
        raise ReferenceScopeError("tenant scope must contain exactly repo and sources")
    repo = entry["repo"]
    if type(repo) is not str or not _REPO_PATTERN.fullmatch(repo):
        raise ReferenceScopeError("tenant repo must be one exact repository name")
    sources = entry["sources"]
    if (type(sources) is not list or not 0 < len(sources) <= _SOURCES_MAX
            or not all(_valid_source(item) for item in sources)
            or len(set(sources)) != len(sources)):
        raise ReferenceScopeError("tenant sources must be a non-empty list of unique source IDs")
    return ReferenceScope(namespace=namespace, repo=repo, sources=tuple(sorted(sources)))


_CACHE_LOCK = threading.Lock()
_CACHE: Optional[tuple] = None


def _configured(environ: Mapping[str, str]) -> tuple:
    """Return ``(registry, scope)`` or raise ``LookupError(reason_code)``."""
    from gdw_auth import AuthConfigurationError, load_credential_registry

    global _CACHE
    scope_json = environ.get(SCOPE_ENV)
    # The dedicated pair wins as a unit; the GDW pair is the fallback.
    registry_json = environ.get(CREDENTIALS_ENV)
    principals_present = environ.get(PRINCIPALS_ENV) is not None
    if registry_json is None and not principals_present:
        registry_json = environ.get(GDW_CREDENTIALS_ENV)
        principals_present = environ.get(GDW_PRINCIPALS_ENV) is not None
    if scope_json is None:
        raise LookupError("REFERENCE_SCOPE_UNCONFIGURED")
    if registry_json is None:
        # Legacy user/admin roles never carry the read scope, so a principal
        # registry could only ever deny; refuse it rather than advertise it.
        raise LookupError("LEGACY_PRINCIPALS_CANNOT_GRANT_SCOPE" if principals_present
                          else "REFERENCE_CREDENTIALS_UNCONFIGURED")
    if principals_present:
        # Same rule as gdw_auth: two registry formats together are ambiguous.
        raise LookupError("REFERENCE_CREDENTIALS_INVALID")
    fingerprint = hashlib.sha256(json.dumps(
        [scope_json, registry_json], separators=(",", ":")).encode("utf-8")).hexdigest()
    with _CACHE_LOCK:
        if _CACHE is not None and _CACHE[0] == fingerprint:
            return _CACHE[1], _CACHE[2]
    try:
        scope = parse_reference_scope(scope_json)
    except ReferenceScopeError:
        raise LookupError("REFERENCE_SCOPE_INVALID") from None
    try:
        registry = load_credential_registry(registry_json)
    except AuthConfigurationError:
        raise LookupError("REFERENCE_CREDENTIALS_INVALID") from None
    with _CACHE_LOCK:
        _CACHE = (fingerprint, registry, scope)
    return registry, scope


def authentication_state(environ: Optional[Mapping[str, str]] = None) -> dict:
    """Content-free configuration state for ``/rag/status``."""
    environ = os.environ if environ is None else environ
    try:
        _configured(environ)
        state, reason = "REQUIRED", None
    except LookupError as exc:
        state, reason = "UNCONFIGURED", exc.args[0]
    return {"authentication": state, "reason_code": reason, "scheme": "bearer",
            "required_scope": REFERENCE_READ_SCOPE, "session_expiry": SESSION_EXPIRY}


def _refusal_body(state: str, reason_code: str, error: str, authentication: str) -> dict:
    return {"state": state, "error": error, "reason_code": reason_code, "mode": "lexical",
            "result_state": "DENIED" if state == "denied" else "UNAVAILABLE",
            "authentication": authentication, "required_scope": REFERENCE_READ_SCOPE,
            "answer": None, "citations": []}


def authorise(authorization: Optional[str], requested_repo: Optional[str] = None,
              environ: Optional[Mapping[str, str]] = None):
    """Return ``(ReferenceAuthorization, None)`` or ``(None, ReferenceRefusal)``.

    Runs before the read path touches the engine, index or store. A request
    ``repo`` may only restate the admitted repo; it can never select another.
    """
    from gdw_auth import AuthConfigurationError, AuthenticationError, authenticate_bearer

    environ = os.environ if environ is None else environ
    try:
        registry, scope = _configured(environ)
        principal = authenticate_bearer(
            authorization, registry, namespace=scope.namespace,
            required_scopes=(REFERENCE_READ_SCOPE,))
    except LookupError as exc:
        return None, ReferenceRefusal(503, _refusal_body(
            "unavailable", exc.args[0],
            "lexical reference authentication is not configured", "UNCONFIGURED"))
    except AuthConfigurationError:
        return None, ReferenceRefusal(503, _refusal_body(
            "unavailable", "REFERENCE_CREDENTIALS_INVALID",
            "lexical reference authentication is not configured", "UNCONFIGURED"))
    except AuthenticationError as exc:
        status = 403 if exc.code in _DENIED_403 else 401
        return None, ReferenceRefusal(
            status, _refusal_body("denied", "LEXICAL_REFERENCE_AUTHENTICATION_DENIED",
                                  exc.code, "REQUIRED"),
            {"WWW-Authenticate": "Bearer"} if status == 401 else None)
    if requested_repo not in (None, "", scope.repo):
        return None, ReferenceRefusal(403, _refusal_body(
            "denied", "LEXICAL_REFERENCE_REQUEST_SCOPE_DENIED",
            "request repo is outside the admitted corpus scope", "REQUIRED"))
    return ReferenceAuthorization(owner_id=principal.owner_id, key_id=principal.key_id,
                                  namespace=principal.namespace, scope=scope), None


def release_within_scope(auth: ReferenceAuthorization, payload: Mapping[str, Any]) -> bool:
    """Every citation and evidence entry must name the admitted repo and a source."""
    allowed = frozenset(auth.scope.sources)
    for key in ("citations", "evidence_set"):
        items = payload.get(key) or []
        if not isinstance(items, list):
            return False
        for item in items:
            if (not isinstance(item, dict) or item.get("repo") != auth.scope.repo
                    or item.get("source") not in allowed):
                return False
    return True


def reference_fields(auth: ReferenceAuthorization) -> dict:
    """Principal reference and corpus scope for an authenticated response."""
    return {
        "authentication": {"state": "AUTHENTICATED", "scheme": "bearer",
                           "credential_registry": "gdw_auth",
                           "required_scope": REFERENCE_READ_SCOPE,
                           "session_expiry": SESSION_EXPIRY},
        "principal": {"owner_id": auth.owner_id, "key_id": auth.key_id,
                      "namespace": auth.namespace},
        "corpus_scope": {"namespace": auth.scope.namespace, "repo": auth.scope.repo,
                         "sources": list(auth.scope.sources),
                         "authority": "controller_configuration",
                         "request_fields_grant_authority": False},
        "limitations": dict(LIMITATIONS),
    }
