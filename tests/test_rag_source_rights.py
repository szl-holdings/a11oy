# SPDX-License-Identifier: Apache-2.0
"""R2 source rights before ingestion + minimal R3 tenant predicate (PROPOSED, local).

Synthetic fixtures only.  A fake GitHub fetcher records every call; no network,
no credentials, no model calls.
"""
from __future__ import annotations

import base64
import sqlite3
import threading
from pathlib import Path

import pytest

import a11oy_org_rag as rag
import a11oy_rag_source_rights as sr
from a11oy_agent_loop import SynthesisAdmissionError, SynthesisHandle, SynthesisSubject

ORG = rag.ORG
POLICY = "a" * 40
C_PUB = "1" * 40
C_PUB_HEAD = "2" * 40
C_PRIV = "3" * 40
SECRET = "PRIVATE-TOKEN-VISIBLE-SECRET-BYTES"
EXCLUDED = "EXCLUDED-STUDIO-BYTES-MUST-NEVER-BE-READ"


def _principal(tenant: str = "tenant-a", authenticated: bool = True) -> sr.VerifiedPrincipal:
    return sr.VerifiedPrincipal(principal_id=f"user@{tenant}", tenant_id=tenant,
                                policy_revision=POLICY, authenticated=authenticated)


class FakeGitHub:
    """Synthetic GitHub API. ``repos`` maps name -> spec. Records every call."""

    def __init__(self, repos: dict, *, per_page_cap: int = 100) -> None:
        self.repos = repos
        self.per_page_cap = per_page_cap
        self.calls: list[tuple[str, dict]] = []

    def _tree(self, spec: dict, ref: str) -> dict:
        files = spec["files"] if ref == spec["commit"] else spec.get("head_files", spec["files"])
        if ref not in (spec["commit"], spec.get("branch", "main")):
            raise RuntimeError("404 ref")
        return {"sha": spec.get("tree_sha", "f" * 40), "truncated": spec.get("truncated", False),
                "tree": [{"path": p, "type": "blob", "size": len(b),
                          "sha": sr.git_blob_sha(b)} for p, b in files.items()]}

    def __call__(self, path: str, token: str, params: dict | None = None):
        params = dict(params or {})
        self.calls.append((path, params))
        if path == f"/orgs/{ORG}/repos":
            page = int(params.get("page", 1))
            per = min(int(params.get("per_page", 30)), self.per_page_cap)
            names = sorted(self.repos)
            return [{"name": n, "private": self.repos[n].get("private", False)}
                    for n in names[(page - 1) * per: page * per]]
        prefix = f"/repos/{ORG}/"
        assert path.startswith(prefix), path
        rest = path[len(prefix):]
        name, _, tail = rest.partition("/")
        spec = self.repos[name]
        if spec.get("error"):
            raise RuntimeError(spec["error"])
        if tail == "":
            return {"default_branch": spec.get("branch", "main"),
                    "private": spec.get("private", False)}
        if tail.startswith("git/trees/"):
            return self._tree(spec, tail[len("git/trees/"):])
        if tail.startswith("contents/"):
            fpath = tail[len("contents/"):]
            ref = params.get("ref")
            files = spec["files"] if ref == spec["commit"] else spec.get("head_files", spec["files"])
            data = spec.get("served", {}).get(fpath, files[fpath])
            return {"content": base64.b64encode(data).decode("ascii")}
        raise AssertionError(path)

    def fetched_paths(self) -> list[str]:
        return [p for p, _ in self.calls if "/contents/" in p]

    def touched(self, repo: str) -> bool:
        return any(p.startswith(f"/repos/{ORG}/{repo}") for p, _ in self.calls)


class Embedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def __call__(self, text: str) -> list[float]:
        self.texts.append(text)
        return [0.5, 0.25]


@pytest.fixture
def env(monkeypatch, tmp_path):
    db_path = tmp_path / "rag.sqlite3"
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(db_path))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(rag, "_build_thread", None)
    monkeypatch.setattr(rag, "_resolve_m1_ledger", lambda: None)
    monkeypatch.setattr(rag, "_gh_token", lambda: "synthetic-not-a-credential")
    emb = Embedder()
    monkeypatch.setattr(rag, "_maybe_embedder", lambda load=True: emb)

    def install(repos: dict, **kw) -> FakeGitHub:
        fake = FakeGitHub(repos, **kw)
        monkeypatch.setattr(rag, "_gh_get", fake)
        return fake

    return {"db": db_path, "emb": emb, "install": install}


def _db_text(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT repo,path,source,body FROM org_chunks_gen").fetchall()
        meta = conn.execute("SELECT COALESCE(graph_json,'')||COALESCE(meta_json,'') "
                            "FROM org_generations").fetchall()
        return "\n".join("|".join(map(str, r)) for r in rows + meta)
    finally:
        conn.close()


def _public_spec() -> dict:
    return {"commit": C_PUB, "files": {
        "README.md": b"public governed retrieval notes alpha\n",
        "src/core.py": b"def governed_alpha():\n    return 1\n",
    }}


def _registry(**kw) -> sr.SourceRightsRegistry:
    return sr.SourceRightsRegistry(ingest_principal=_principal("tenant-a"), **kw)


# ------------------------------------------------------------------ R2: ingestion


def test_registry_none_keeps_legacy_branch_path(env):
    fake = env["install"]({"pubrepo": _public_spec()})
    out = rag.build_index(repos=["pubrepo"])
    assert out["ok"] is True and "source_rights" not in out
    assert (f"/repos/{ORG}/pubrepo", {}) in fake.calls
    assert (f"/repos/{ORG}/pubrepo/git/trees/main", {"recursive": "1"}) in fake.calls


def test_unregistered_private_token_visible_repo_is_never_read(env):
    fake = env["install"]({"pubrepo": _public_spec(),
                           "secretrepo": {"commit": C_PRIV, "private": True,
                                          "files": {"s.md": SECRET.encode()}}})
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"})
    out = rag.build_index(repos=None, rights_registry=reg)
    rights = out["source_rights"]
    assert not fake.touched("secretrepo")
    assert rights["repos_denied"] == 1 and rights["reasons"]["NO_RIGHTS_RECORD"] == 1
    assert rights["partial"] is True
    assert SECRET not in _db_text(env["db"]) and "secretrepo" not in _db_text(env["db"])
    assert not any(SECRET in t for t in env["emb"].texts)


def test_private_source_without_explicit_grant_is_denied():
    reg = _registry()
    reg.register(org=ORG, repo="privrepo", commit_sha=C_PRIV, tenant_owner="tenant-b",
                 visibility="private", rights={"read", "index"},
                 grants={"tenant-c": {"read"}})
    a, b, c = _principal("tenant-a"), _principal("tenant-b"), _principal("tenant-c")
    blob = sr.git_blob_sha(b"x")
    scoped = sr.SCOPED_PRIVATE_STORE
    assert reg.admit(ORG, "privrepo", C_PRIV, "x.md", blob, "read", a,
                     store=scoped).reason == "PRIVATE_NO_EXPLICIT_GRANT"
    assert reg.admit(ORG, "privrepo", C_PRIV, "x.md", blob, "read", b, store=scoped).admitted
    assert reg.admit(ORG, "privrepo", C_PRIV, "x.md", blob, "read", c, store=scoped).admitted
    assert reg.admit(ORG, "privrepo", C_PRIV, "x.md", blob, "index", c,
                     store=scoped).reason == "PRIVATE_NO_EXPLICIT_GRANT"
    assert reg.admit(ORG, "privrepo", C_PRIV, "x.md", blob, "embed", b,
                     store=scoped).reason == "PURPOSE_NOT_GRANTED"
    # Even the owner cannot place a private source in the shared public-default store.
    assert reg.admit(ORG, "privrepo", C_PRIV, "x.md", blob, "read", b).reason == \
        "PRIVATE_NOT_ALLOWED_IN_SHARED_STORE"


def test_registered_private_repo_not_ingested_into_shared_store(env):
    fake = env["install"]({"privrepo": {"commit": C_PRIV, "private": True,
                                        "files": {"s.md": SECRET.encode()}}})
    reg = _registry()
    reg.register(org=ORG, repo="privrepo", commit_sha=C_PRIV, tenant_owner="tenant-a",
                 visibility="private", rights={"read", "index", "embed"})
    out = rag.build_index(repos=["privrepo"], rights_registry=reg)
    assert not fake.touched("privrepo")
    assert out["ok"] is False and out["integrity_state"] == "NOT_PUBLISHED_EMPTY_BUILD"
    assert out["source_rights"]["reasons"] == {"PRIVATE_NOT_ALLOWED_IN_SHARED_STORE": 1}


def test_default_deny_when_rights_absent_and_embed_needs_its_own_right(env):
    reg = _registry()
    reg.register(org=ORG, repo="norights", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights=())
    blob = sr.git_blob_sha(b"x")
    for purpose in sorted(sr.PURPOSES):
        adm = reg.admit_for_ingest(ORG, "norights", C_PUB, "x.md", blob, purpose)
        assert adm.decision == sr.DENY and adm.reason == "PURPOSE_NOT_GRANTED"
    assert reg.admit_for_ingest(ORG, "unknown", C_PUB, "x.md", blob, "read").reason == \
        "NO_RIGHTS_RECORD"
    assert reg.admit_for_ingest(ORG, "norights", C_PUB, "x.md", blob, "train").reason == \
        "PURPOSE_INVALID"

    env["install"]({"pubrepo": _public_spec()})
    reg2 = _registry()
    reg2.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                  visibility="public", rights={"read", "index"})
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg2)
    assert out["ok"] is True and out["chunks"] == 2
    assert env["emb"].texts == []
    assert out["source_rights"]["embed_denied"] == 2


def test_tree_and_file_reads_use_pinned_commit_not_mutable_branch(env):
    spec = _public_spec()
    spec["head_files"] = dict(spec["files"], **{"RACE.md": b"branch moved after pin\n"})
    fake = env["install"]({"pubrepo": spec})
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"})
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg)
    tree_calls = [p for p, _ in fake.calls if "/git/trees/" in p]
    assert tree_calls == [f"/repos/{ORG}/pubrepo/git/trees/{C_PUB}"]
    assert (f"/repos/{ORG}/pubrepo", {}) not in fake.calls
    assert all(params.get("ref") == C_PUB for p, params in fake.calls if "/contents/" in p)
    assert "branch moved after pin" not in _db_text(env["db"])
    assert out["source_rights"]["files_admitted"] == 2 and out["source_rights"]["partial"] is False


def test_excluded_blob_and_identical_copies_denied_before_fetch(env):
    spec = _public_spec()
    spec["files"].update({"studio/secret.md": EXCLUDED.encode(),
                          "elsewhere/copy.md": EXCLUDED.encode()})
    other = {"commit": C_PUB_HEAD, "files": {"vendored/copy2.md": EXCLUDED.encode(),
                                             "ok.md": b"fine public text beta\n"}}
    fake = env["install"]({"pubrepo": spec, "otherrepo": other})
    reg = _registry()
    for name, commit in (("pubrepo", C_PUB), ("otherrepo", C_PUB_HEAD)):
        reg.register(org=ORG, repo=name, commit_sha=commit, tenant_owner="public",
                     visibility="public", rights={"read", "index", "embed"})
    reg.exclude_blob(sr.git_blob_sha(EXCLUDED.encode()), "studio exclusion")
    out = rag.build_index(repos=["pubrepo", "otherrepo"], rights_registry=reg)
    assert not any("copy" in p or "studio" in p for p in fake.fetched_paths())
    assert out["source_rights"]["reasons"]["EXCLUDED_BLOB"] == 3
    assert EXCLUDED not in _db_text(env["db"])
    assert not any(EXCLUDED in t for t in env["emb"].texts)
    assert "studio/secret.md" not in _db_text(env["db"])


def test_revision_and_manifest_mismatch_quarantined_before_fetch(env):
    reg = _registry()
    good = sr.git_blob_sha(b"pinned bytes")
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"},
                 blob_manifest={"README.md": good})
    adm = reg.admit_for_ingest(ORG, "pubrepo", C_PUB_HEAD, "README.md", good, "read")
    assert (adm.decision, adm.reason) == (sr.QUARANTINE, "REVISION_MISMATCH")
    adm = reg.admit_for_ingest(ORG, "pubrepo", "main", "README.md", good, "read")
    assert (adm.decision, adm.reason) == (sr.QUARANTINE, "REVISION_NOT_IMMUTABLE")
    adm = reg.admit_for_ingest(ORG, "pubrepo", C_PUB, "README.md",
                               sr.git_blob_sha(b"changed"), "read")
    assert (adm.decision, adm.reason) == (sr.QUARANTINE, "BLOB_DIGEST_MISMATCH")
    assert reg.admit_for_ingest(ORG, "pubrepo", C_PUB, "other.md", good,
                                "read").reason == "PATH_NOT_IN_MANIFEST"

    fake = env["install"]({"pubrepo": _public_spec()})  # README.md bytes differ from manifest
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg)
    assert fake.fetched_paths() == []
    assert out["source_rights"]["files_quarantined"] == 1
    assert out["source_rights"]["reasons"] == {"BLOB_DIGEST_MISMATCH": 1,
                                               "PATH_NOT_IN_MANIFEST": 1}


def test_tree_digest_mismatch_quarantines_repo(env):
    fake = env["install"]({"pubrepo": dict(_public_spec(), tree_sha="e" * 40)})
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"}, tree_sha="d" * 40)
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg)
    assert fake.fetched_paths() == []
    assert out["source_rights"]["repos_quarantined"] == 1


def test_fetched_bytes_not_matching_admitted_blob_are_quarantined(env):
    spec = _public_spec()
    spec["served"] = {"README.md": b"TAMPERED IN TRANSIT gamma\n"}
    env["install"]({"pubrepo": spec})
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"})
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg)
    assert out["source_rights"]["reasons"] == {"CONTENT_DIGEST_MISMATCH": 1}
    assert "TAMPERED" not in _db_text(env["db"])
    assert not any("TAMPERED" in t for t in env["emb"].texts)


def test_revoked_source_denied_at_ingest(env):
    fake = env["install"]({"pubrepo": _public_spec()})
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"})
    reg.revoke(ORG, "pubrepo")
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg)
    assert not fake.touched("pubrepo")
    assert out["source_rights"]["reasons"] == {"SOURCE_REVOKED": 1}


def test_retention_expiry_denies():
    now = [100.0]
    reg = _registry(clock=lambda: now[0])
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read"}, retention_until=150.0)
    blob = sr.git_blob_sha(b"x")
    assert reg.admit_for_ingest(ORG, "pubrepo", C_PUB, "x", blob, "read").admitted
    now[0] = 150.0
    assert reg.admit_for_ingest(ORG, "pubrepo", C_PUB, "x", blob, "read").reason == \
        "RETENTION_EXPIRED"


def test_errors_and_truncated_trees_reported_partial(env):
    env["install"]({"pubrepo": dict(_public_spec(), truncated=True),
                    "brokenrepo": {"commit": C_PUB_HEAD, "files": {}, "error": "403 forbidden"}})
    reg = _registry()
    for name, commit in (("pubrepo", C_PUB), ("brokenrepo", C_PUB_HEAD)):
        reg.register(org=ORG, repo=name, commit_sha=commit, tenant_owner="public",
                     visibility="public", rights={"read", "index", "embed"})
    out = rag.build_index(repos=["pubrepo", "brokenrepo"], rights_registry=reg)
    r = out["source_rights"]
    assert (r["repo_errors"], r["truncated_trees"], r["partial"]) == (1, 1, True)


def test_mutating_registered_source_requires_revoke_first():
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read"})
    with pytest.raises(sr.SourceRightsError):
        reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB_HEAD, tenant_owner="public",
                     visibility="public", rights={"read"})
    with pytest.raises(sr.SourceRightsError):
        reg.register(org=ORG, repo="other", commit_sha="main", tenant_owner="public",
                     visibility="public", rights={"read"})


# ------------------------------------------------------------------ R3: tenancy


def _two_tenant_registry():
    reg = _registry()
    reg.register(org="tenant-a-org", repo="notes", commit_sha=C_PRIV, tenant_owner="tenant-a",
                 visibility="private", rights={"read", "index"})
    reg.register(org="tenant-b-org", repo="notes", commit_sha=C_PRIV, tenant_owner="tenant-b",
                 visibility="private", rights={"read", "index"}, grants={"tenant-c": {"read"}})
    cid = "c" * 24  # identical chunk id and identical source name for both tenants
    row_a = {"generation_id": "g1", "chunk_id": cid, "sha256": "a" * 64,
             "source": f"gh:{ORG}/notes", "body": "tenant A private text"}
    row_b = {"generation_id": "g1", "chunk_id": cid, "sha256": "b" * 64,
             "source": f"gh:{ORG}/notes", "body": "tenant B private text"}
    reg.bind_chunk("g1", cid, row_a["sha256"], f"tenant-a-org/notes@{C_PRIV}")
    reg.bind_chunk("g1", cid, row_b["sha256"], f"tenant-b-org/notes@{C_PRIV}")
    return reg, row_a, row_b


def test_cross_tenant_identical_chunk_ids_and_source_names_never_leak():
    reg, row_a, row_b = _two_tenant_registry()
    a, b, c = _principal("tenant-a"), _principal("tenant-b"), _principal("tenant-c")
    assert reg.tenant_predicate(a, row_a, scope="tenant").allow is True
    assert reg.tenant_predicate(a, row_b, scope="tenant").allow is False
    assert reg.tenant_predicate(b, row_a, scope="tenant").allow is False
    assert reg.tenant_predicate(b, row_b, scope="tenant").allow is True
    assert reg.tenant_predicate(c, row_b, scope="tenant").allow is True
    assert reg.tenant_predicate(c, row_a, scope="tenant").allow is False
    for p in (a, b, c):
        for row in (row_a, row_b):
            d = reg.tenant_predicate(p, row, scope="public")
            assert d.allow is False and d.reason == "PRIVATE_IN_PUBLIC_SCOPE"
    forged = dict(row_b, tenant_id="tenant-a", visibility="public", owner="tenant-a")
    assert reg.tenant_predicate(a, forged, scope="tenant").allow is False
    assert reg.tenant_predicate(a, forged, scope="public").allow is False


def test_rows_lacking_rights_are_public_unclassified_never_tenant_owned():
    reg, _, _ = _two_tenant_registry()
    legacy = {"generation_id": "g0", "chunk_id": "d" * 24, "sha256": "d" * 64}
    a = _principal("tenant-a")
    d = reg.tenant_predicate(a, legacy, scope="tenant")
    assert (d.allow, d.reason, d.classification) == (False, "UNCLASSIFIED_NOT_OWNED",
                                                     "PUBLIC_UNCLASSIFIED")
    assert reg.tenant_predicate(a, legacy, scope="public").classification == "PUBLIC_UNCLASSIFIED"
    unknown_sha = {"generation_id": "g1", "chunk_id": "c" * 24, "sha256": "e" * 64}
    assert reg.tenant_predicate(a, unknown_sha, scope="tenant").reason == \
        "CONTENT_BINDING_MISMATCH"
    assert reg.tenant_predicate(a, {"chunk_id": "x"}, scope="public").allow is False
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index"})
    pub = {"generation_id": "g1", "chunk_id": "p" * 24, "sha256": "f" * 64}
    reg.bind_chunk("g1", pub["chunk_id"], pub["sha256"], f"{ORG}/pubrepo@{C_PUB}")
    assert reg.tenant_predicate(a, pub, scope="public").allow is True
    assert reg.tenant_predicate(a, pub, scope="tenant").reason == "NOT_OWNED_OR_GRANTED"


def test_concurrent_grant_revocations_do_not_restore_each_other():
    reg = _registry()
    reg.register(org="tenant-b-org", repo="notes", commit_sha=C_PRIV, tenant_owner="tenant-b",
                 visibility="private", rights={"read"},
                 grants={"tenant-c": {"read"}, "tenant-d": {"read"}})
    barrier = threading.Barrier(2)
    errors = []

    def revoke(tenant: str) -> None:
        try:
            barrier.wait(timeout=5)
            reg.revoke_grant("tenant-b-org", "notes", tenant)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=revoke, args=(tenant,)) for tenant in ("tenant-c", "tenant-d")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert reg.entry("tenant-b-org", "notes").grants == ()


def test_revoked_grant_and_revoked_source_deny_reads():
    reg, row_a, row_b = _two_tenant_registry()
    c = _principal("tenant-c")
    assert reg.tenant_predicate(c, row_b, scope="tenant").allow is True
    reg.revoke_grant("tenant-b-org", "notes", "tenant-c")
    assert reg.tenant_predicate(c, row_b, scope="tenant").allow is False
    assert reg.admit("tenant-b-org", "notes", C_PRIV, "x", sr.git_blob_sha(b"x"), "read", c,
                     store=sr.SCOPED_PRIVATE_STORE).reason == "PRIVATE_NO_EXPLICIT_GRANT"
    a = _principal("tenant-a")
    reg.revoke("tenant-a-org", "notes")
    assert reg.tenant_predicate(a, row_a, scope="tenant").reason == "SOURCE_REVOKED"


def test_caller_body_tenant_is_ignored_and_unverified_principals_refused():
    reg, row_a, row_b = _two_tenant_registry()
    a = _principal("tenant-a")
    body = {"tenant": "tenant-b", "tenant_id": "tenant-b", "owner": "tenant-b"}
    resolved = sr.resolve_principal(a, body)
    assert resolved is a and resolved.tenant_id == "tenant-a"
    assert reg.tenant_predicate(resolved, row_b, scope="tenant").allow is False
    with pytest.raises(sr.SourceRightsError):
        sr.resolve_principal(None, body)
    with pytest.raises(sr.SourceRightsError):
        sr.resolve_principal(body, body)
    for bad in (body, "tenant-b", _principal("tenant-b", authenticated=False),
                sr.VerifiedPrincipal("u", "tenant-b", "not-a-revision", True)):
        assert reg.tenant_predicate(bad, row_b, scope="tenant").reason == "PRINCIPAL_UNVERIFIED"
        assert reg.admit("tenant-b-org", "notes", C_PRIV, "x", sr.git_blob_sha(b"x"), "read",
                         bad, store=sr.SCOPED_PRIVATE_STORE).reason == "PRINCIPAL_UNVERIFIED"


def test_hydration_authorizer_denies_after_revocation_before_reading_store(env, monkeypatch):
    env["install"]({"pubrepo": _public_spec()})
    reg = _registry()
    reg.register(org=ORG, repo="pubrepo", commit_sha=C_PUB, tenant_owner="public",
                 visibility="public", rights={"read", "index", "embed"})
    out = rag.build_index(repos=["pubrepo"], rights_registry=reg)
    conn = sqlite3.connect(str(env["db"]))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT chunk_id,node_id,repo,path,source,sha256 FROM org_chunks_gen "
                       "WHERE generation_id=? ORDER BY chunk_id LIMIT 1",
                       (out["generation_id"],)).fetchone()
    conn.close()
    handle = SynthesisHandle(generation_id=out["generation_id"],
                             generation_digest_sha256=out["generation_digest_sha256"],
                             **{k: row[k] for k in row.keys()})
    subject = SynthesisSubject(principal_id="user@tenant-a", tenant_id="tenant-a",
                               policy_revision=POLICY, authenticated=True)
    authz = reg.hydration_authorizer(scope="public")
    got = rag.hydrate_answer_evidence(subject, (handle,), authorizer=authz)
    assert got[0]["handle"] == handle
    reg.revoke(ORG, "pubrepo")
    opened = []
    real = rag._db_readonly
    monkeypatch.setattr(rag, "_db_readonly", lambda: opened.append(1) or real())
    with pytest.raises(SynthesisAdmissionError) as exc:
        rag.hydrate_answer_evidence(subject, (handle,), authorizer=authz)
    assert str(exc.value) == "HYDRATION_ACCESS_DENIED" and opened == []
    tenant_authz = reg.hydration_authorizer(scope="tenant")
    assert tenant_authz(subject, handle) is False


# ------------------------------------------------- documented gaps (not fixed here)


@pytest.mark.xfail(strict=True, reason="GAP R2 (MEASURED by reading a11oy_org_rag.py "
                   "build_index): repo enumeration requests one per_page=100 page and never "
                   "follows pagination; repos beyond the first 100 are silently dropped")
def test_gap_repo_enumeration_beyond_100_repos(env):
    repos = {f"r{i:03d}": {"commit": C_PUB, "files": {"a.md": b"x"}} for i in range(150)}
    fake = env["install"](repos)
    rag.build_index(repos=None)
    seen = {p.split("/")[3] for p, _ in fake.calls if p.startswith(f"/repos/{ORG}/")}
    assert len(seen) == 150


@pytest.mark.xfail(strict=True, reason="GAP R2 (MEASURED): with rights_registry=None, trees "
                   "and contents are read at the mutable default branch, not a pinned commit")
def test_gap_legacy_path_reads_mutable_branch(env):
    fake = env["install"]({"pubrepo": _public_spec()})
    rag.build_index(repos=["pubrepo"])
    assert [p for p, _ in fake.calls if "/git/trees/" in p] == \
        [f"/repos/{ORG}/pubrepo/git/trees/{C_PUB}"]
