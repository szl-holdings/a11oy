#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Composition adapter: R2/R3 ``SourceRightsRegistry`` as an R6 ``SynthesisGrantSource``.

PROPOSED, LOCAL, NOT DEPLOYED. Standard library only.

``RegistryGrantSource`` implements the three methods consumed by
``a11oy_rag_synthesis_controller`` on top of ``a11oy_rag_source_rights``:

``resolve_subject(request, operator)``
    Calls the injected controller ``verify(request, operator)`` callable, which
    must return a controller-minted ``VerifiedPrincipal`` (for example from a
    verified credential-to-principal mapping). ``resolve_principal`` validates it
    and ignores request bodies. The request body is never read here. Anything
    else returns ``None`` (content admission unavailable).
``source_grant(subject, handle)``
    Strict ``allowed=True`` only when all of the following hold:
    * the handle's ``gh:{org}/{repo}`` source names a registry entry;
    * the registry binding for ``(generation, chunk, sha256)`` names exactly
      one current entry, and that entry is the handle's ``org/repo@commit``;
    * ``admit_source(..., purpose="read", store=...)`` returns ``ADMIT``;
    * ``tenant_predicate`` allows the subject (public scope for public sources,
      tenant scope for private ones);
    * a PRIVATE source is never granted when the admitted destination is not
      LOCAL.
    The reported revision is the entry's immutable commit. Visibility and the
    source tenant come from the registry, never from row fields.
``admit_transfer(decision)``
    Default deny. Requires an exact match with this adapter's one destination,
    purpose ``ANSWER_SYNTHESIS``, no forwarded history and no expression
    authority. Every source must resolve to exactly one current entry bound to
    that generation, chunk, and content digest, at the same revision, and must
    be admitted for ``egress``. Any exception denies.

The registry models ``egress`` as a purpose right; it has no per-destination
egress list. Destination binding is therefore enforced by constructing one
adapter per admitted destination.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Optional

import a11oy_agent_loop as _agent
import a11oy_rag_source_rights as _sr

PURPOSE = "ANSWER_SYNTHESIS"
_SOURCE = re.compile(r"gh:([A-Za-z0-9][A-Za-z0-9._-]{0,99})/([A-Za-z0-9][A-Za-z0-9._-]{0,99})")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class RegistryGrantSource:
    def __init__(self, registry: _sr.SourceRightsRegistry, *,
                 verify: Callable[[Any, Mapping[str, Any]], Any],
                 destination: Any,
                 store: str = _sr.SHARED_PUBLIC_STORE) -> None:
        if type(registry) is not _sr.SourceRightsRegistry or not callable(verify):
            raise _sr.SourceRightsError("GRANT_SOURCE_INVALID")
        if store not in _sr.STORES:
            raise _sr.SourceRightsError("STORE_INVALID")
        self.registry, self._verify, self.store = registry, verify, store
        # Snapshot the destination identity; the transport itself is not needed.
        self.provider_id = getattr(destination, "provider_id", None)
        self.model_id = getattr(destination, "model_id", None)
        self.trust_domain = getattr(destination, "trust_domain", None)

    # ------------------------------------------------------------------ #
    # identity
    # ------------------------------------------------------------------ #
    def resolve_subject(self, request: Any, operator: Mapping[str, Any]) -> Optional[Any]:
        if not isinstance(operator, Mapping) or operator.get("operator") is not True:
            return None
        try:
            verified = self._verify(request, operator)
            principal = _sr.resolve_principal(verified, None)
        except Exception:
            return None
        return _agent.SynthesisSubject(principal.principal_id, principal.tenant_id,
                                       principal.policy_revision, True)

    # ------------------------------------------------------------------ #
    # binding lookup
    # ------------------------------------------------------------------ #
    def _current_bound_entries(self, generation_id: str, chunk_id: str, sha256: str) -> list:
        # The rights module exposes no public accessor for chunk bindings; this
        # read-only lookup is the single coupling point (see the module docs).
        # The digest is part of the key: the same chunk id can be bound to
        # more than one source, and those sources are not interchangeable.
        reg = self.registry
        if not isinstance(sha256, str):
            return []
        with reg._lock:
            bound = tuple(reg._bindings.get((generation_id, chunk_id), ()))
        found = []
        seen = set()
        for bound_sha, source_id in bound:
            if bound_sha != sha256 or source_id in seen:
                continue
            seen.add(source_id)
            name, _, _commit = source_id.partition("@")
            org, _, repo = name.partition("/")
            entry = reg.entry(org, repo)
            if entry is not None and entry.source_id == source_id:
                found.append(entry)
        return found

    # ------------------------------------------------------------------ #
    # SynthesisGrantSource
    # ------------------------------------------------------------------ #
    def source_grant(self, subject: Any, handle: Any) -> Any:
        def deny(visibility: str = "UNKNOWN", tenant: Optional[str] = None, revision: str = ""):
            return _agent.SynthesisSourceGrant(subject, handle, revision, visibility, tenant, False)

        try:
            if type(subject) is not _agent.SynthesisSubject or type(handle) is not _agent.SynthesisHandle:
                return deny()
            match = _SOURCE.fullmatch(handle.source) if isinstance(handle.source, str) else None
            if match is None or match.group(2) != handle.repo:
                return deny()
            org, repo = match.group(1), match.group(2)
            bound = self._current_bound_entries(handle.generation_id, handle.chunk_id, handle.sha256)
            if len(bound) != 1 or bound[0].org != org or bound[0].repo != repo:
                return deny()
            entry = bound[0]
            visibility = "PRIVATE" if entry.visibility == "private" else "PUBLIC"
            tenant = entry.tenant_owner if visibility == "PRIVATE" else None
            admission = self.registry.admit_source(org, repo, entry.commit_sha, "read", subject,
                                                   store=self.store)
            if admission.decision != _sr.ADMIT:
                return deny(visibility, tenant, entry.commit_sha)
            row = {"generation_id": handle.generation_id, "chunk_id": handle.chunk_id,
                   "sha256": handle.sha256}
            scope = "public" if visibility == "PUBLIC" else "tenant"
            if self.registry.tenant_predicate(subject, row, scope=scope).allow is not True:
                return deny(visibility, tenant, entry.commit_sha)
            if visibility == "PRIVATE" and self.trust_domain != "LOCAL":
                return deny(visibility, tenant, entry.commit_sha)
            return _agent.SynthesisSourceGrant(subject, handle, entry.commit_sha, visibility, tenant, True)
        except Exception:
            return deny()

    def admit_transfer(self, decision: Any) -> bool:
        try:
            if not (decision.purpose == PURPOSE
                    and decision.provider_id == self.provider_id
                    and decision.model_id == self.model_id
                    and decision.trust_domain == self.trust_domain
                    and decision.history_forwarded is False
                    and decision.expression_authority == "NONE"
                    and isinstance(decision.task_sha256, str) and _HEX64.fullmatch(decision.task_sha256)):
                return False
            subject = decision.subject
            if type(subject) is not _agent.SynthesisSubject:
                return False
            sources = decision.source_revisions
            if not isinstance(sources, tuple) or not 1 <= len(sources) <= 6:
                return False
            for generation_id, chunk_id, sha256, revision in sources:
                current = self._current_bound_entries(generation_id, chunk_id, sha256)
                if len(current) != 1:
                    return False
                entry = current[0]
                if entry.commit_sha != revision:
                    return False
                if entry.visibility == "private" and self.trust_domain != "LOCAL":
                    return False
                egress = self.registry.admit_source(entry.org, entry.repo, entry.commit_sha, "egress",
                                                    subject, store=self.store)
                if egress.decision != _sr.ADMIT:
                    return False
            return True
        except Exception:
            return False
