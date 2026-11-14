# SPDX-License-Identifier: Apache-2.0
"""
a11oy_rag_source_rights -- controller-owned source registry (R2) and tenant
predicate (R3) for the org RAG ingestion path.

PROPOSED, LOCAL, NOT DEPLOYED.  Pure standard library.

Contract
--------
* A source is ``(org, repo)`` pinned to ONE immutable commit revision, with a
  tenant owner, a visibility, explicit per-purpose rights
  (``read``/``index``/``embed``/``egress``), optional explicit per-tenant grants,
  an optional retention deadline and a revocation revision.
* DEFAULT DENY: no entry, no right, no grant -> DENY.  Rights are never inferred
  from what a credential can see; this module never talks to GitHub and takes no
  token.
* ``admit`` runs BEFORE any tree or file read.  Excluded blobs (and every
  identical-content copy, which shares the content-addressed git blob id) are
  denied before reading; revision or manifest digest mismatch -> QUARANTINE.
* ``verify_blob_bytes`` re-checks fetched bytes against the admitted blob id.
* Tenant authority comes only from a controller-verified principal object.
  Strings, dicts and request bodies are refused; ``resolve_principal`` ignores
  body tenant fields.
* ``tenant_predicate`` is the R3 read-path check.  Rows with no registry
  binding are PUBLIC_UNCLASSIFIED: visible only in public scope, never as owned
  by a tenant.
* The shared public-default store (``SHARED_PUBLIC_STORE``) never admits a
  private source.  The current index keeps one active generation that default
  reads serve, so a private corpus there would become public.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

ADMIT = "ADMIT"
DENY = "DENY"
QUARANTINE = "QUARANTINE"

PURPOSES = frozenset({"read", "index", "embed", "egress"})
VISIBILITIES = frozenset({"public", "private"})
SHARED_PUBLIC_STORE = "shared_public_default"
SCOPED_PRIVATE_STORE = "scoped_private"
STORES = frozenset({SHARED_PUBLIC_STORE, SCOPED_PRIVATE_STORE})
SCOPES = frozenset({"public", "tenant"})

_HEX_REV = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")


class SourceRightsError(ValueError):
    """Malformed registry mutation. Messages are reason codes only."""


@dataclass(frozen=True)
class VerifiedPrincipal:
    """Controller-minted identity. Never construct from request or planner claims."""
    principal_id: str
    tenant_id: str
    policy_revision: str
    authenticated: bool = False


@dataclass(frozen=True)
class Admission:
    decision: str
    reason: str
    purpose: str
    source_id: Optional[str] = None

    @property
    def admitted(self) -> bool:
        return self.decision == ADMIT


@dataclass(frozen=True)
class TenantDecision:
    allow: bool
    reason: str
    classification: str


@dataclass(frozen=True)
class SourceEntry:
    org: str
    repo: str
    commit_sha: str
    tenant_owner: str
    visibility: str
    rights: frozenset
    grants: tuple = ()                 # ((tenant_id, frozenset(purposes)), ...)
    tree_sha: Optional[str] = None     # optional pinned root tree id
    blob_manifest: Optional[tuple] = None  # ((path, blob_sha), ...) when pinned per file
    retention_until: Optional[float] = None
    registered_revision: int = 0
    revoked_revision: Optional[int] = None

    @property
    def source_id(self) -> str:
        return f"{self.org}/{self.repo}@{self.commit_sha}"

    def grant_for(self, tenant_id: str) -> frozenset:
        for tenant, purposes in self.grants:
            if tenant == tenant_id:
                return purposes
        return frozenset()

    def manifest_blob(self, path: str) -> Optional[str]:
        """None = no manifest pinned; "" = manifest pinned but path absent."""
        if self.blob_manifest is None:
            return None
        for p, b in self.blob_manifest:
            if p == path:
                return b
        return ""


def git_blob_sha(data: bytes, algo: str = "sha1") -> str:
    """Content-addressed git blob id (SHA-1 or SHA-256 object format)."""
    if algo not in ("sha1", "sha256"):
        raise SourceRightsError("BLOB_ALGO_INVALID")
    h = hashlib.new(algo)
    h.update(b"blob %d\x00" % len(data))
    h.update(data)
    return h.hexdigest()


def _principal_types() -> tuple:
    try:  # the existing controller identity type is also accepted, exactly
        from a11oy_agent_loop import SynthesisSubject
        return (VerifiedPrincipal, SynthesisSubject)
    except Exception:
        return (VerifiedPrincipal,)


def _verified(principal: Any) -> bool:
    return (type(principal) in _principal_types()
            and getattr(principal, "authenticated", False) is True
            and all(isinstance(v, str) and v.strip() and len(v) <= 512
                    for v in (principal.principal_id, principal.tenant_id))
            and isinstance(principal.policy_revision, str)
            and _HEX_REV.fullmatch(principal.policy_revision) is not None)


def resolve_principal(verified: Any, request_body: Optional[Mapping[str, Any]] = None) -> Any:
    """Return the controller-verified principal; request bodies carry no authority.

    Any ``tenant``/``tenant_id``/``owner`` keys in ``request_body`` are ignored.
    Without a verified principal this raises; it never falls back to the body.
    """
    if not _verified(verified):
        raise SourceRightsError("PRINCIPAL_UNVERIFIED")
    return verified


class SourceRightsRegistry:
    """In-memory, revisioned registry. Durable persistence is an R4 decision."""

    def __init__(self, *, ingest_principal: Any = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._lock = threading.RLock()
        self._entries: dict[tuple[str, str], SourceEntry] = {}
        self._excluded_blobs: dict[str, str] = {}
        self._bindings: dict[tuple[str, str], set] = {}  # (generation, chunk) -> {(sha256, source_id)}
        self._by_source_id: dict[str, SourceEntry] = {}
        self.revision = 0
        self.events: list[tuple[int, str, str]] = []
        self._clock = clock
        self.ingest_principal = ingest_principal

    # ---------------- mutations (controller only) ---------------- #
    def _bump(self, op: str, key: str) -> int:
        self.revision += 1
        self.events.append((self.revision, op, key))
        return self.revision

    def register(self, *, org: str, repo: str, commit_sha: str, tenant_owner: str,
                 visibility: str, rights, grants: Optional[Mapping[str, Any]] = None,
                 tree_sha: Optional[str] = None,
                 blob_manifest: Optional[Mapping[str, str]] = None,
                 retention_until: Optional[float] = None) -> SourceEntry:
        if not (isinstance(org, str) and _NAME.fullmatch(org)
                and isinstance(repo, str) and _NAME.fullmatch(repo)):
            raise SourceRightsError("SOURCE_NAME_INVALID")
        if not (isinstance(commit_sha, str) and _HEX_REV.fullmatch(commit_sha)):
            raise SourceRightsError("COMMIT_NOT_IMMUTABLE")
        if tree_sha is not None and not (isinstance(tree_sha, str) and _HEX_REV.fullmatch(tree_sha)):
            raise SourceRightsError("TREE_NOT_IMMUTABLE")
        if visibility not in VISIBILITIES:
            raise SourceRightsError("VISIBILITY_INVALID")
        if not (isinstance(tenant_owner, str) and tenant_owner.strip()):
            raise SourceRightsError("TENANT_OWNER_INVALID")
        rights = frozenset(rights)
        if not rights <= PURPOSES:
            raise SourceRightsError("RIGHT_INVALID")
        g: list = []
        for tenant, purposes in sorted((grants or {}).items()):
            purposes = frozenset(purposes)
            if not (isinstance(tenant, str) and tenant.strip()) or not purposes <= PURPOSES:
                raise SourceRightsError("GRANT_INVALID")
            g.append((tenant, purposes))
        manifest = None
        if blob_manifest is not None:
            for p, b in blob_manifest.items():
                if not (isinstance(p, str) and isinstance(b, str) and _HEX_REV.fullmatch(b)):
                    raise SourceRightsError("MANIFEST_INVALID")
            manifest = tuple(sorted(blob_manifest.items()))
        with self._lock:
            key = (org, repo)
            existing = self._entries.get(key)
            if existing is not None and existing.revoked_revision is None:
                raise SourceRightsError("SOURCE_ALREADY_REGISTERED")
            rev = self._bump("register", f"{org}/{repo}@{commit_sha}")
            entry = SourceEntry(org=org, repo=repo, commit_sha=commit_sha,
                                tenant_owner=tenant_owner, visibility=visibility,
                                rights=rights, grants=tuple(g), tree_sha=tree_sha,
                                blob_manifest=manifest, retention_until=retention_until,
                                registered_revision=rev)
            self._entries[key] = entry
            self._by_source_id[entry.source_id] = entry
            return entry

    def _replace(self, org: str, repo: str, op: str, **changes: Any) -> int:
        with self._lock:
            entry = self._entries.get((org, repo))
            if entry is None:
                raise SourceRightsError("SOURCE_UNKNOWN")
            rev = self._bump(op, entry.source_id)
            if "revoked_revision" in changes:
                changes["revoked_revision"] = rev
            new = dataclasses.replace(entry, **changes)
            self._entries[(org, repo)] = new
            self._by_source_id[new.source_id] = new
            return rev

    def revoke(self, org: str, repo: str) -> int:
        return self._replace(org, repo, "revoke", revoked_revision=True)

    def revoke_grant(self, org: str, repo: str, tenant_id: str) -> int:
        # Read and write under one lock. A snapshot taken before _replace
        # would put a stale grants tuple back over a concurrent revocation.
        with self._lock:
            entry = self._entries.get((org, repo))
            if entry is None:
                raise SourceRightsError("SOURCE_UNKNOWN")
            grants = tuple((t, p) for t, p in entry.grants if t != tenant_id)
            return self._replace(org, repo, "revoke_grant", grants=grants)

    def exclude_blob(self, blob_sha: str, reason: str = "EXCLUDED") -> int:
        if not (isinstance(blob_sha, str) and _HEX_REV.fullmatch(blob_sha)):
            raise SourceRightsError("BLOB_ID_INVALID")
        with self._lock:
            self._excluded_blobs[blob_sha] = str(reason)
            return self._bump("exclude_blob", blob_sha)

    def bind_chunk(self, generation_id: str, chunk_id: str, sha256: str, source_id: str) -> None:
        with self._lock:
            if source_id not in self._by_source_id:
                raise SourceRightsError("SOURCE_UNKNOWN")
            self._bindings.setdefault((generation_id, chunk_id), set()).add((sha256, source_id))

    # ---------------- queries ---------------- #
    def entry(self, org: str, repo: str) -> Optional[SourceEntry]:
        with self._lock:
            return self._entries.get((org, repo))

    def _purpose_ok(self, entry: SourceEntry, purpose: str, tenant_id: str) -> Optional[str]:
        """Return None when tenant may use entry for purpose, else a DENY reason."""
        if entry.revoked_revision is not None:
            return "SOURCE_REVOKED"
        if entry.retention_until is not None and self._clock() >= entry.retention_until:
            return "RETENTION_EXPIRED"
        if purpose not in entry.rights:
            return "PURPOSE_NOT_GRANTED"
        if entry.visibility == "public":
            return None
        if tenant_id == entry.tenant_owner:
            return None
        if purpose in entry.grant_for(tenant_id):
            return None
        return "PRIVATE_NO_EXPLICIT_GRANT"

    def admit_source(self, org: str, repo: str, commit_sha: Optional[str], purpose: str,
                     principal: Any, *, store: str = SHARED_PUBLIC_STORE) -> Admission:
        """Repo-level admission, before any tree read."""
        if purpose not in PURPOSES:
            return Admission(DENY, "PURPOSE_INVALID", str(purpose))
        if store not in STORES:
            return Admission(DENY, "STORE_INVALID", purpose)
        if not _verified(principal):
            return Admission(DENY, "PRINCIPAL_UNVERIFIED", purpose)
        with self._lock:
            entry = self._entries.get((org, repo))
            if entry is None:
                return Admission(DENY, "NO_RIGHTS_RECORD", purpose)
            if commit_sha is not None and commit_sha != entry.commit_sha:
                return Admission(QUARANTINE, "REVISION_MISMATCH", purpose, entry.source_id)
            reason = self._purpose_ok(entry, purpose, principal.tenant_id)
            if reason is not None:
                return Admission(DENY, reason, purpose, entry.source_id)
            if store == SHARED_PUBLIC_STORE and entry.visibility != "public":
                return Admission(DENY, "PRIVATE_NOT_ALLOWED_IN_SHARED_STORE", purpose,
                                 entry.source_id)
            return Admission(ADMIT, "ADMITTED", purpose, entry.source_id)

    def admit(self, org: str, repo: str, commit_sha: str, path: str, blob_sha: str,
              purpose: str, principal: Any, *, store: str = SHARED_PUBLIC_STORE) -> Admission:
        """File-level admission. Call BEFORE fetching any bytes."""
        if purpose not in PURPOSES:
            return Admission(DENY, "PURPOSE_INVALID", str(purpose))
        if not (isinstance(blob_sha, str) and _HEX_REV.fullmatch(blob_sha)):
            return Admission(QUARANTINE, "BLOB_ID_INVALID", purpose)
        if not (isinstance(commit_sha, str) and _HEX_REV.fullmatch(commit_sha)):
            return Admission(QUARANTINE, "REVISION_NOT_IMMUTABLE", purpose)
        with self._lock:
            # Excluded content is refused first, whatever the rights say. Git blob
            # ids are content-addressed, so every identical copy shares the id.
            if blob_sha in self._excluded_blobs:
                return Admission(DENY, "EXCLUDED_BLOB", purpose)
            base = self.admit_source(org, repo, commit_sha, purpose, principal, store=store)
            if not base.admitted:
                return base
            entry = self._entries[(org, repo)]
            pinned = entry.manifest_blob(path)
            if pinned == "":
                return Admission(DENY, "PATH_NOT_IN_MANIFEST", purpose, entry.source_id)
            if pinned is not None and pinned != blob_sha:
                return Admission(QUARANTINE, "BLOB_DIGEST_MISMATCH", purpose, entry.source_id)
            return base

    def admit_for_ingest(self, org: str, repo: str, commit_sha: str, path: str,
                         blob_sha: str, purpose: str) -> Admission:
        """Admission for the controller ingest principal into the shared store."""
        return self.admit(org, repo, commit_sha, path, blob_sha, purpose,
                          self.ingest_principal, store=SHARED_PUBLIC_STORE)

    def verify_blob_bytes(self, blob_sha: str, data: bytes) -> Admission:
        """Post-fetch check: fetched bytes must hash to the admitted blob id."""
        if not isinstance(data, (bytes, bytearray)):
            return Admission(QUARANTINE, "CONTENT_UNAVAILABLE", "read")
        algo = "sha1" if len(blob_sha) == 40 else "sha256"
        actual = git_blob_sha(bytes(data), algo)
        with self._lock:
            if actual in self._excluded_blobs:
                return Admission(DENY, "EXCLUDED_BLOB", "read")
        if actual != blob_sha:
            return Admission(QUARANTINE, "CONTENT_DIGEST_MISMATCH", "read")
        return Admission(ADMIT, "CONTENT_VERIFIED", "read")

    # ---------------- R3 read-path predicate ---------------- #
    def tenant_predicate(self, principal: Any, row: Mapping[str, Any], *,
                         scope: str) -> TenantDecision:
        """May ``principal`` see ``row`` in ``scope`` ('public' or 'tenant')?

        ``row`` needs generation_id, chunk_id and sha256. Any tenant/visibility
        fields inside the row are ignored; the registry binding is the authority.
        """
        if scope not in SCOPES:
            return TenantDecision(False, "SCOPE_INVALID", "UNKNOWN")
        if not _verified(principal):
            return TenantDecision(False, "PRINCIPAL_UNVERIFIED", "UNKNOWN")
        try:
            key = (str(row["generation_id"]), str(row["chunk_id"]))
            sha = str(row["sha256"])
        except Exception:
            return TenantDecision(False, "ROW_UNIDENTIFIED", "UNKNOWN")
        with self._lock:
            bound = self._bindings.get(key)
            if not bound:
                if scope == "public":
                    return TenantDecision(True, "PUBLIC_UNCLASSIFIED", "PUBLIC_UNCLASSIFIED")
                return TenantDecision(False, "UNCLASSIFIED_NOT_OWNED", "PUBLIC_UNCLASSIFIED")
            matching = sorted(sid for (s, sid) in bound if s == sha)
            if not matching:
                return TenantDecision(False, "CONTENT_BINDING_MISMATCH", "BOUND")
            reasons = []
            for sid in matching:
                entry = self._by_source_id.get(sid)
                if entry is None:
                    reasons.append("SOURCE_UNKNOWN")
                    continue
                if scope == "public" and entry.visibility != "public":
                    reasons.append("PRIVATE_IN_PUBLIC_SCOPE")
                    continue
                reason = self._purpose_ok(entry, "read", principal.tenant_id)
                if reason is None and scope == "tenant" and not (
                        entry.tenant_owner == principal.tenant_id
                        or "read" in entry.grant_for(principal.tenant_id)):
                    reason = "NOT_OWNED_OR_GRANTED"
                if reason is None:
                    return TenantDecision(True, "ALLOWED", entry.visibility.upper())
                reasons.append(reason)
            return TenantDecision(False, reasons[0], "BOUND")

    def hydration_authorizer(self, *, scope: str) -> Callable[[Any, Any], bool]:
        """Adapter usable as ``authorizer`` for a11oy_org_rag.hydrate_answer_evidence."""
        def _authorize(subject: Any, handle: Any) -> bool:
            row = {"generation_id": handle.generation_id, "chunk_id": handle.chunk_id,
                   "sha256": handle.sha256}
            return self.tenant_predicate(subject, row, scope=scope).allow is True
        return _authorize
