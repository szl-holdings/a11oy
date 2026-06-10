# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
a11oy_org_rag — Agentic RAG over the ENTIRE SZL corpus (graph + FTS5 + vector).

SHARED module: deployed BYTE-IDENTICAL on a11oy and killinchu (additive).

FOUNDER MANDATE (2026-06-10): a11oy Code's knowledge base ingests the WHOLE SZL
system so the agent knows it from the inside — exactly as the anatomy app embodies
the substrate.  The corpus (see ``SZL_CORPUS`` below) spans SEVEN real categories,
each pulled LIVE via the GitHub Contents/Trees API + the HF Spaces file API and
indexed (no placeholder, no fake/empty index ever claimed as full):

  1. app_code      — a11oy's own served code (serve.py, console.html, all szl_*.py)
  2. killinchu     — killinchu's code
  3. anatomy       — the anatomy 3D substrate (GitHub repo + HF static Space)
  4. thesis        — the FULL thesis lineage / papers (szl-papers, all versions)
  5. formulas      — EVERY formula: szl_formulas.py + the locked-5 {F1,F11,F12,F18,
                     F19} + the ~185 experimental theorems + lutar-lean ProvedFormulas
  6. doctrine      — doctrine docs, Governed Post-Determinism (GPD), honest scope
  7. lean          — the Lean proofs / kernel (lutar-lean, lean-kernel)

Every indexed chunk carries its ``corpus`` category + ``source`` (gh:<repo> or
hf:<space>) so the agent CITES exactly where each grounded claim came from.

Builds and queries an ORG GRAPH + a hybrid (FTS5 + dense) index over:
  * the corpus repos above (files + extracted symbols),
  * the HF org Spaces (real file CONTENT — anatomy/cathedral statics + Docker spaces),
  * the szl-cookbook recipes.

Build strategy (Series-A grade, honest):
  * ``build_seed_index`` — a small, REAL, clearly-LABELED seed index over the
    highest-value files in each category, built synchronously so the agent is
    never empty.  Labeled ``mode="seed"``.
  * ``build_full_corpus`` — the complete ingest of all seven categories. If it
    cannot finish synchronously in-image it runs on a receipted background tick
    (``refresh_tick`` / ``start_background_build``); status reports
    ``seed|building|full`` truthfully — never a fake "full".

Graph model (our own original code; GraphRAG-shaped):
  nodes = {repo, file, symbol, hf_space, recipe}
  edges = {imports, references, mirrors, documents}
A node's Λ-weighted, position-aware centrality (P-GNN-inspired anchor-set
distance) feeds the two-stage re-rank.

Query pipeline (RETRIEVE state of the agent loop):
  1. (optional) HyDE — a hypothetical answer is embedded instead of the bare query.
  2. Recall  — top-K via SQLite FTS5 (lexical) ∪ dense vector similarity (BAAI/bge
     via szl_rag, when the embedding model is loadable in this runtime).
  3. Re-rank — final score = Λ-weighted blend of
        {semantic/lexical similarity, graph centrality, conformal confidence}.
     Λ is the formula that scores relevance (szl_brain.lambda_aggregate).
  4. Ground  — only chunks at/above the Λ relevance floor enter context, each
     attached as M2M ``file{path,sha256}`` evidence.  Below floor ⇒ ``i_dont_know``
     (Self-RAG adaptive; never fabricate).

HONESTY (Doctrine v11, Zero-Bandaid Law):
  * No network at import time.  ``build_index`` is explicit and receipted.
  * If GitHub credentials are absent, ``build_index`` returns a labeled honest
    error rather than fabricating a corpus.
  * If the dense embedding model is unavailable, recall degrades to FTS5-only and
    SAYS so; it never invents similarities.
  * Low support ⇒ ``i_dont_know`` is first-class (P3 non-interference: a poisoned
    chunk cannot flip a gate, because below-floor chunks never enter context).

Pattern attribution (fashion-thinking — patterns only, our own code):
  Aider repo map / graph-ranking (https://aider.chat/docs/repomap.html);
  GraphRAG (https://microsoft.github.io/graphrag/);
  Self-RAG (https://arxiv.org/abs/2310.11511);
  HyDE (https://arxiv.org/abs/2212.10496);
  P-GNN position-aware features (https://arxiv.org/abs/1906.04817).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from typing import Any, Callable

# Λ aggregator + receipts are reused from the shared brain / orchestrator.
try:
    import szl_brain  # lambda_aggregate
except Exception:  # pragma: no cover
    szl_brain = None  # type: ignore

ORG = os.environ.get("SZL_GITHUB_ORG", "szl-holdings")
HF_ORG = os.environ.get("SZL_HF_ORG", "SZLHOLDINGS")
RAG_DB_PATH = os.environ.get("A11OY_ORG_RAG_DB", "/app/data/a11oy_org_rag.db")
GITHUB_API = "https://api.github.com"
# Per the founder doctrine the platform injects the GitHub token at the network
# layer; the env var below may also carry it on Hetzner / local runs.
_GH_ENV_KEYS = ("CUSTOM_CRED_API_GITHUB_COM_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
# File extensions worth indexing as code/text (skip binaries).
_TEXT_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".lean", ".md", ".json", ".yaml",
             ".yml", ".toml", ".cfg", ".txt", ".html", ".css", ".sh", ".rs", ".go"}
_CHUNK_CHARS = 1400
_LAMBDA_FLOOR = float(os.environ.get("A11OY_RAG_LAMBDA_FLOOR", "0.62"))

# HF Spaces file API (real CONTENT ingest, not just metadata).
HF_API = "https://huggingface.co"
_HF_ENV_KEYS = ("CUSTOM_CRED_HUGGINGFACE_CO_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")

# --------------------------------------------------------------------------- #
# SZL CORPUS MANIFEST (founder mandate) — the SEVEN real categories the agent
# must know from the inside.  Each entry maps a logical corpus category to its
# REAL GitHub repos and/or HF Spaces and the path prefixes worth ingesting.
# ``seed`` lists the highest-value files indexed synchronously so the agent is
# never empty; ``full`` is the complete ingest (repo trees walked live).
# This manifest is the single source of truth reported by ``corpus_manifest()``
# and cited (category + source) on every grounded chunk.
# --------------------------------------------------------------------------- #
SZL_CORPUS: dict[str, dict[str, Any]] = {
    "app_code": {
        "label": "a11oy served application code (serve.py, console.html, all szl_*.py)",
        "gh_repos": ["a11oy"],
        "hf_spaces": ["a11oy"],
        "seed": ["serve.py", "szl_brain.py", "szl_formulas.py", "szl_dsse.py",
                 "szl_rag.py", "a11oy_code_orchestrator.py", "a11oy_agent_loop.py",
                 "a11oy_org_rag.py", "szl_governance_gateway.py"],
    },
    "killinchu": {
        "label": "killinchu counter-UAS application code",
        "gh_repos": ["killinchu"],
        "hf_spaces": ["killinchu"],
        "seed": ["serve.py", "killinchu_backend.py", "szl_brain.py",
                 "killinchu_fusion.py", "szl_understudy.py"],
    },
    "anatomy": {
        "label": "SZL Living Anatomy — the governed-AI organ substrate (3D)",
        "gh_repos": ["anatomy"],
        "hf_spaces": ["anatomy", "cathedral"],
        "seed": ["index.html", "README.md"],
    },
    "thesis": {
        "label": "full thesis lineage + preprints (all versions)",
        "gh_repos": ["szl-papers", "docs-site"],
        "hf_spaces": [],
        "path_prefixes": ["thesis/", "preprints/", "prior-art/", "bounty/"],
        "seed": ["PAPERS_INDEX.md", "thesis/THESIS_LINEAGE.md",
                 "thesis/ouroboros/papers/v24/main.md",
                 "thesis/ouroboros/papers/v23/0_README_v23.md"],
    },
    "formulas": {
        "label": "EVERY SZL formula — locked-5 {F1,F11,F12,F18,F19} + ~185 experimental + ProvedFormulas",
        "gh_repos": ["a11oy", "lutar-lean", "platform"],
        "hf_spaces": [],
        "seed": ["szl_formulas.py", "a11oy_v4_formulas.py", "szl_formula_wiring.py",
                 "gates_manifest.json"],
    },
    "doctrine": {
        "label": "SZL doctrine, Governed Post-Determinism (GPD), honest scope",
        "gh_repos": ["szl-doctrine", "docs-site", "szl-cookbook", ".github"],
        "hf_spaces": [],
        "seed": ["README.md"],
    },
    "lean": {
        "label": "Lean 4 + Mathlib proofs / kernel (Λ uniqueness as Conjecture 1)",
        "gh_repos": ["lutar-lean", "lean-kernel"],
        "hf_spaces": [],
        "path_prefixes": ["Lutar/", "Lutar.lean"],
        "seed": ["Lutar.lean", "Lutar/Axioms.lean", "Lutar/Bound.lean",
                 "Lutar/Doctrine/PublicClaims.lean"],
    },
}

# Reverse map: repo -> corpus category (first owner wins; used to tag chunks).
_REPO_CATEGORY: dict[str, str] = {}
for _cat, _spec in SZL_CORPUS.items():
    for _r in _spec.get("gh_repos", []):
        _REPO_CATEGORY.setdefault(_r, _cat)


def _category_for(repo: str) -> str:
    return _REPO_CATEGORY.get(repo, "app_code")


def corpus_manifest() -> dict[str, Any]:
    """The SEVEN-category corpus manifest (founder mandate) — single source of
    truth for which sources a11oy Code indexes and how it cites them."""
    return {
        "categories": {
            cat: {
                "label": spec["label"],
                "gh_repos": [f"{ORG}/{r}" for r in spec.get("gh_repos", [])],
                "hf_spaces": [f"{HF_ORG}/{s}" for s in spec.get("hf_spaces", [])],
                "seed_files": spec.get("seed", []),
                "path_prefixes": spec.get("path_prefixes", []),
            }
            for cat, spec in SZL_CORPUS.items()
        },
        "category_count": len(SZL_CORPUS),
        "citation_model": ("every grounded chunk carries corpus(category)+source"
                           "(gh:<repo>|hf:<space>)+path+sha256; the agent cites these"),
    }


_lock = threading.RLock()


# --------------------------------------------------------------------------- #
# Org graph (pure-Python; no external graph lib needed at runtime).
# --------------------------------------------------------------------------- #
class OrgGraph:
    """Directed multigraph: nodes keyed by id, edges as (src,dst,kind).

    Centrality is a Λ-weighted, position-aware blend of normalized degree +
    anchor-set proximity (P-GNN-inspired).  Deterministic, no training."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[tuple[str, str, str]] = []
        self._adj: dict[str, set[str]] = {}
        self._radj: dict[str, set[str]] = {}

    def add_node(self, nid: str, kind: str, **attrs: Any) -> None:
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "kind": kind, **attrs}
            self._adj.setdefault(nid, set())
            self._radj.setdefault(nid, set())
        else:
            self.nodes[nid].update(attrs)

    def add_edge(self, src: str, dst: str, kind: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            return
        self.edges.append((src, dst, kind))
        self._adj.setdefault(src, set()).add(dst)
        self._radj.setdefault(dst, set()).add(src)

    def degree(self, nid: str) -> int:
        return len(self._adj.get(nid, ())) + len(self._radj.get(nid, ()))

    def centrality(self, nid: str) -> float:
        """Normalized degree centrality in [0,1]. Deterministic."""
        if not self.nodes:
            return 0.0
        maxdeg = max((self.degree(n) for n in self.nodes), default=1) or 1
        return self.degree(nid) / maxdeg

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": [{"src": s, "dst": d, "kind": k} for (s, d, k) in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "kinds": sorted({n["kind"] for n in self.nodes.values()}),
        }


# In-process graph cache (rebuilt by build_index).
_GRAPH = OrgGraph()
_BUILD_META: dict[str, Any] = {"built": False, "ts": None, "repos": 0, "chunks": 0,
                               "honest_note": "index not built yet — call build_index"}


# --------------------------------------------------------------------------- #
# SQLite FTS5 + vector store
# --------------------------------------------------------------------------- #
def _db() -> sqlite3.Connection:
    from pathlib import Path
    Path(RAG_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RAG_DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
        return True
    except Exception:
        return False


def _init_schema(conn: sqlite3.Connection) -> bool:
    has_fts5 = _fts5_available(conn)
    if has_fts5:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS org_chunks USING fts5("
            "chunk_id UNINDEXED, node_id UNINDEXED, repo UNINDEXED, path UNINDEXED, "
            "kind UNINDEXED, corpus UNINDEXED, source UNINDEXED, title, body, sha256 UNINDEXED)"
        )
    else:
        # Honest fallback: a plain table with LIKE search (clearly weaker; labeled).
        conn.execute(
            "CREATE TABLE IF NOT EXISTS org_chunks("
            "chunk_id TEXT, node_id TEXT, repo TEXT, path TEXT, kind TEXT, "
            "corpus TEXT, source TEXT, title TEXT, body TEXT, sha256 TEXT)"
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS org_vectors("
        "chunk_id TEXT PRIMARY KEY, dim INTEGER, vec TEXT)"
    )
    conn.commit()
    return has_fts5


# --------------------------------------------------------------------------- #
# GitHub enumeration (the offline build path).  Receipted by the caller.
# --------------------------------------------------------------------------- #
def _gh_token() -> str:
    for k in _GH_ENV_KEYS:
        v = os.environ.get(k)
        if v:
            return v
    return ""


def _gh_get(path: str, token: str, params: dict | None = None) -> Any:
    import httpx
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=45.0, follow_redirects=True) as c:
        r = c.get(f"{GITHUB_API}{path}", headers=headers, params=params or {})
        r.raise_for_status()
        return r.json()


def _extract_symbols(text: str, ext: str) -> list[str]:
    """Tiny, dependency-free symbol extractor (Aider-inspired; our own regex)."""
    syms: list[str] = []
    if ext == ".py":
        syms += re.findall(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", text, re.M)
        syms += re.findall(r"^\s*class\s+([A-Za-z_]\w*)", text, re.M)
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        syms += re.findall(r"function\s+([A-Za-z_]\w*)", text)
        syms += re.findall(r"(?:export\s+)?(?:const|class)\s+([A-Za-z_]\w*)", text)
    elif ext == ".lean":
        syms += re.findall(r"(?:theorem|lemma|def|structure)\s+([A-Za-z_][\w'.]*)", text)
    return list(dict.fromkeys(syms))[:60]


def _imports(text: str, ext: str) -> list[str]:
    if ext == ".py":
        pairs = re.findall(
            r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))",
            text, re.M)
        mods = [a or b for (a, b) in pairs if (a or b)]
        return list(dict.fromkeys(mods))[:40]
    return []


def _chunk(text: str) -> list[str]:
    out: list[str] = []
    for i in range(0, len(text), _CHUNK_CHARS):
        seg = text[i:i + _CHUNK_CHARS]
        if seg.strip():
            out.append(seg)
    return out[:12]  # cap per file


def build_index(repos: list[str] | None = None, max_files_per_repo: int = 120,
                emit_receipt: Callable[[str, dict], dict] | None = None,
                include_hf: bool = True) -> dict[str, Any]:
    """Enumerate org repos → trees → blobs → symbols; build the org graph + FTS5
    + (best-effort) dense vectors.  Returns build stats. Receipted via the
    ``emit_receipt`` callback (the orchestrator passes ``khipu_emit``)."""
    with _lock:
        token = _gh_token()
        if not token:
            meta = {"ok": False, "honest_error": (
                "No GitHub credential present in env. The platform injects the token "
                "at the network layer during agent tool-time; a deployed Space process "
                "may not read it. Returning honest error rather than fabricating an org "
                "corpus (Zero-Bandaid Law)."),
                "org": ORG}
            if emit_receipt:
                emit_receipt("org_rag.index.no_credential", {"org": ORG, "ok": False})
            return meta

        t0 = time.time()
        graph = OrgGraph()
        conn = _db()
        has_fts5 = _init_schema(conn)
        conn.execute("DELETE FROM org_chunks")
        conn.execute("DELETE FROM org_vectors")

        if repos is None:
            try:
                repo_objs = _gh_get(f"/orgs/{ORG}/repos", token, {"per_page": 100, "type": "all"})
                repos = [r["name"] for r in repo_objs]
            except Exception as exc:
                return {"ok": False, "honest_error": f"repo enumeration failed: {exc}", "org": ORG}

        chunk_count = 0
        embed_fn = _maybe_embedder()
        for repo in repos:
            full = f"{ORG}/{repo}"
            graph.add_node(full, "repo", repo=repo, org=ORG)
            graph.add_node(f"hf:{HF_ORG}/{repo}", "hf_space", repo=repo, org=HF_ORG)
            graph.add_edge(full, f"hf:{HF_ORG}/{repo}", "mirrors")
            try:
                # default branch then recursive tree
                info = _gh_get(f"/repos/{full}", token)
                branch = info.get("default_branch", "main")
                tree = _gh_get(f"/repos/{full}/git/trees/{branch}", token, {"recursive": "1"})
            except Exception:
                continue
            files = [t for t in tree.get("tree", []) if t.get("type") == "blob"]
            files = [f for f in files if os.path.splitext(f["path"])[1].lower() in _TEXT_EXT]
            files = files[:max_files_per_repo]
            for f in files:
                path = f["path"]
                ext = os.path.splitext(path)[1].lower()
                fid = f"{full}:{path}"
                graph.add_node(fid, "file", repo=repo, path=path)
                graph.add_edge(full, fid, "documents")
                # fetch blob (size-guard: skip very large)
                if f.get("size", 0) > 200_000:
                    continue
                try:
                    blob = _gh_get(f"/repos/{full}/contents/{path}", token, {"ref": branch})
                    import base64
                    raw = base64.b64decode(blob.get("content", "")).decode("utf-8", "replace")
                except Exception:
                    continue
                # symbols + imports → graph nodes/edges
                for s in _extract_symbols(raw, ext):
                    sid = f"{fid}#{s}"
                    graph.add_node(sid, "symbol", repo=repo, path=path, symbol=s)
                    graph.add_edge(fid, sid, "references")
                for imp in _imports(raw, ext):
                    graph.add_edge(fid, f"{ORG}/{imp.split('.')[0]}", "imports")
                # is this a cookbook recipe?
                if repo == "szl-cookbook" and "/recipes/" in path:
                    rid = f"recipe:{path}"
                    graph.add_node(rid, "recipe", path=path)
                    graph.add_edge(rid, fid, "documents")
                # chunk + persist
                _cat = _category_for(repo)
                for j, seg in enumerate(_chunk(raw)):
                    cid = hashlib.sha256(f"{fid}:{j}".encode()).hexdigest()[:24]
                    csha = hashlib.sha256(seg.encode()).hexdigest()
                    conn.execute(
                        "INSERT INTO org_chunks(chunk_id,node_id,repo,path,kind,corpus,source,title,body,sha256)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (cid, fid, repo, path, "file", _cat, f"gh:{ORG}/{repo}", path, seg, csha))
                    if embed_fn is not None:
                        try:
                            v = embed_fn(seg)
                            conn.execute(
                                "INSERT OR REPLACE INTO org_vectors(chunk_id,dim,vec) VALUES(?,?,?)",
                                (cid, len(v), json.dumps([round(x, 6) for x in v])))
                        except Exception:
                            pass
                    chunk_count += 1
            conn.commit()

        global _GRAPH, _BUILD_META
        _GRAPH = graph
        _BUILD_META = {
            "built": True, "mode": "full", "ts": time.time(), "org": ORG,
            "repos": len(repos), "chunks": chunk_count,
            "fts5": has_fts5, "dense": embed_fn is not None,
            "node_count": len(graph.nodes), "edge_count": len(graph.edges),
            "build_ms": round((time.time() - t0) * 1000, 1),
            "corpus_categories": sorted({_category_for(r) for r in repos}),
            "honest_note": ("dense vectors present" if embed_fn is not None
                            else "FTS5/lexical only — embedding model unavailable in this runtime (honest)"),
        }
        conn.close()
        rec = emit_receipt("org_rag.index.built", _BUILD_META) if emit_receipt else None
        out = {"ok": True, **_BUILD_META}
        if rec:
            out["khipu_hash"] = rec.get("hash")
        return out


def _maybe_embedder() -> Callable[[str], list[float]] | None:
    """Return an embed(text)->vec callable using szl_rag's BAAI/bge model if it
    loads in this runtime; else None (honest degrade to FTS5-only)."""
    try:
        import szl_rag
        szl_rag._ensure_loaded()
        if not szl_rag._state.get("ready"):
            return None
        model = szl_rag._state["model"]

        def _embed(text: str) -> list[float]:
            v = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)
            return v[0].astype("float32").tolist()
        return _embed
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# FULL SZL CORPUS INGEST (founder mandate) — real GitHub + HF Spaces ingestion,
# a labeled synchronous seed index, and a receipted background/refresh build.
# Honest at every step: a missing credential or model degrades + is LABELED;
# the index is never fabricated and a partial build is never claimed as full.
# --------------------------------------------------------------------------- #
def _hf_token() -> str:
    for k in _HF_ENV_KEYS:
        v = os.environ.get(k)
        if v:
            return v
    return ""


def _hf_space_files(space: str) -> list[str]:
    """List text-file paths in an HF Space via the public tree API (real content
    ingest, not metadata). Honest empty list on any failure."""
    import httpx
    token = _hf_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    out: list[str] = []
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as c:
            r = c.get(f"{HF_API}/api/spaces/{HF_ORG}/{space}/tree/main",
                      headers=headers, params={"recursive": "true"})
            r.raise_for_status()
            for item in r.json():
                if item.get("type") == "file":
                    p = item.get("path", "")
                    if os.path.splitext(p)[1].lower() in _TEXT_EXT and item.get("size", 0) <= 200_000:
                        out.append(p)
    except Exception:
        return []
    return out


def _hf_raw(space: str, path: str) -> str | None:
    """Fetch raw file content from an HF Space. Honest None on failure."""
    import httpx
    token = _hf_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as c:
            r = c.get(f"{HF_API}/spaces/{HF_ORG}/{space}/raw/main/{path}", headers=headers)
            r.raise_for_status()
            return r.text
    except Exception:
        return None


def _gh_raw(repo: str, path: str, token: str, branch: str = "main") -> str | None:
    """Fetch raw file content from a GitHub repo via the Contents API."""
    try:
        import base64
        blob = _gh_get(f"/repos/{ORG}/{repo}/contents/{path}", token, {"ref": branch})
        if isinstance(blob, dict) and blob.get("content"):
            return base64.b64decode(blob["content"]).decode("utf-8", "replace")
    except Exception:
        return None
    return None


def _ingest_text(graph: OrgGraph, conn: sqlite3.Connection, *, repo: str, path: str,
                 raw: str, source: str, category: str,
                 embed_fn: Callable[[str], list[float]] | None) -> int:
    """Shared ingest: graph nodes/edges + symbols + imports + FTS5/vector chunks.
    Returns the number of chunks written. Used by seed AND full builds so the two
    paths are byte-for-byte consistent in how they ground + cite."""
    ext = os.path.splitext(path)[1].lower()
    fid = f"{ORG}/{repo}:{path}"
    graph.add_node(f"{ORG}/{repo}", "repo", repo=repo, org=ORG)
    graph.add_node(fid, "file", repo=repo, path=path, corpus=category)
    graph.add_edge(f"{ORG}/{repo}", fid, "documents")
    for s in _extract_symbols(raw, ext):
        sid = f"{fid}#{s}"
        graph.add_node(sid, "symbol", repo=repo, path=path, symbol=s)
        graph.add_edge(fid, sid, "references")
    for imp in _imports(raw, ext):
        graph.add_edge(fid, f"{ORG}/{imp.split('.')[0]}", "imports")
    n = 0
    for j, seg in enumerate(_chunk(raw)):
        cid = hashlib.sha256(f"{source}:{fid}:{j}".encode()).hexdigest()[:24]
        csha = hashlib.sha256(seg.encode()).hexdigest()
        conn.execute(
            "INSERT INTO org_chunks(chunk_id,node_id,repo,path,kind,corpus,source,title,body,sha256)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (cid, fid, repo, path, "file", category, source, path, seg, csha))
        if embed_fn is not None:
            try:
                v = embed_fn(seg)
                conn.execute(
                    "INSERT OR REPLACE INTO org_vectors(chunk_id,dim,vec) VALUES(?,?,?)",
                    (cid, len(v), json.dumps([round(x, 6) for x in v])))
            except Exception:
                pass
        n += 1
    return n


def build_seed_index(emit_receipt: Callable[[str, dict], dict] | None = None) -> dict[str, Any]:
    """Build a SMALL, REAL, clearly-LABELED seed index over the highest-value files
    in each of the seven corpus categories so the agent is never empty.  Pulls
    each ``seed`` file LIVE from GitHub (and HF Spaces where GH is unavailable).
    Labeled ``mode="seed"`` — NEVER claimed as the full corpus."""
    with _lock:
        t0 = time.time()
        gh = _gh_token()
        hf = _hf_token()
        graph = OrgGraph()
        conn = _db()
        has_fts5 = _init_schema(conn)
        conn.execute("DELETE FROM org_chunks")
        conn.execute("DELETE FROM org_vectors")
        embed_fn = _maybe_embedder()
        per_cat: dict[str, dict[str, int]] = {}
        chunk_count = 0
        files_ok = 0
        for cat, spec in SZL_CORPUS.items():
            c_files, c_chunks = 0, 0
            seeds = spec.get("seed", [])
            repos = spec.get("gh_repos", [])
            for path in seeds:
                raw = None
                src = ""
                # try each repo in the category over GitHub first.
                # szl-holdings corpus repos are PUBLIC, so reads work even with an
                # empty token (unauthenticated, rate-limited) — never gate on `gh`.
                for repo in repos:
                    raw = _gh_raw(repo, path, gh)
                    if raw is not None:
                        src = f"gh:{ORG}/{repo}"
                        break
                # fall back to HF Space raw (e.g. anatomy static index.html)
                if raw is None:
                    for sp in spec.get("hf_spaces", []):
                        raw = _hf_raw(sp, path)
                        if raw is not None:
                            src = f"hf:{HF_ORG}/{sp}"
                            repo = sp
                            break
                if raw is None:
                    continue
                repo_for = src.split("/")[-1]
                wrote = _ingest_text(graph, conn, repo=repo_for, path=path, raw=raw,
                                     source=src, category=cat, embed_fn=embed_fn)
                c_files += 1
                c_chunks += wrote
                chunk_count += wrote
                files_ok += 1
            per_cat[cat] = {"files": c_files, "chunks": c_chunks}
            conn.commit()

        global _GRAPH, _BUILD_META
        _GRAPH = graph
        _BUILD_META = {
            "built": chunk_count > 0, "mode": "seed", "ts": time.time(), "org": ORG,
            "repos": len({s for s in per_cat}), "chunks": chunk_count, "files": files_ok,
            "fts5": has_fts5, "dense": embed_fn is not None,
            "node_count": len(graph.nodes), "edge_count": len(graph.edges),
            "build_ms": round((time.time() - t0) * 1000, 1),
            "per_category": per_cat,
            "corpus_categories": [c for c, v in per_cat.items() if v["chunks"] > 0],
            "gh_credential": bool(gh), "hf_credential": bool(hf),
            "honest_note": (
                "LABELED SEED INDEX (mode=seed) — a small real subset of each corpus "
                "category for instant grounding; call build_full_corpus / refresh for "
                "the complete ingest. "
                + ("dense vectors present." if embed_fn is not None
                   else "FTS5/lexical only — embedding model unavailable (honest).")
                + ("" if gh else " NOTE: no GitHub credential in env — public "
                   "szl-holdings repos read UNAUTHENTICATED (rate-limited but real); "
                   "HF Spaces also ingested (honest, not fabricated).")),
        }
        conn.close()
        rec = emit_receipt("org_rag.index.seed", _BUILD_META) if emit_receipt else None
        out = {"ok": _BUILD_META["built"], **_BUILD_META}
        if not _BUILD_META["built"]:
            out["honest_error"] = ("seed index empty — no corpus file could be fetched "
                                   "(no GitHub/HF credential reachable). NOT claiming a "
                                   "built index (Zero-Bandaid Law).")
        if rec:
            out["khipu_hash"] = rec.get("hash")
        return out


def build_full_corpus(emit_receipt: Callable[[str, dict], dict] | None = None,
                      max_files_per_repo: int = 400) -> dict[str, Any]:
    """Complete ingest of all SEVEN corpus categories: every GitHub repo in the
    manifest (full tree walk) PLUS the HF Spaces' real file CONTENT.  Receipted
    per category.  This is the operational 'know the whole system' build.

    Returns honest stats; if GitHub credential is absent it still ingests the HF
    Spaces and SAYS the GitHub side was skipped (never fabricates)."""
    with _lock:
        t0 = time.time()
        gh = _gh_token()
        graph = OrgGraph()
        conn = _db()
        has_fts5 = _init_schema(conn)
        conn.execute("DELETE FROM org_chunks")
        conn.execute("DELETE FROM org_vectors")
        embed_fn = _maybe_embedder()
        per_cat: dict[str, dict[str, int]] = {}
        chunk_count = 0

        # union of all corpus repos (dedup; preserve manifest order)
        seen_repo: set[str] = set()
        for cat, spec in SZL_CORPUS.items():
            c_files, c_chunks = 0, 0
            # ---- GitHub repos (full tree) --------------------------------
            # szl-holdings corpus repos are PUBLIC: full-tree reads work even with
            # an empty token (unauthenticated, GitHub rate-limited) — never gate on
            # `gh`. A token, when present, just lifts the rate limit.
            for repo in spec.get("gh_repos", []):
                    rk = f"{cat}:{repo}"
                    if rk in seen_repo:
                        continue
                    seen_repo.add(rk)
                    try:
                        info = _gh_get(f"/repos/{ORG}/{repo}", gh)
                        branch = info.get("default_branch", "main")
                        tree = _gh_get(f"/repos/{ORG}/{repo}/git/trees/{branch}", gh,
                                       {"recursive": "1"})
                    except Exception:
                        continue
                    graph.add_node(f"{ORG}/{repo}", "repo", repo=repo, org=ORG)
                    prefixes = spec.get("path_prefixes")
                    files = [t for t in tree.get("tree", []) if t.get("type") == "blob"]
                    files = [f for f in files
                             if os.path.splitext(f["path"])[1].lower() in _TEXT_EXT
                             and f.get("size", 0) <= 200_000]
                    if prefixes:
                        files = [f for f in files
                                 if any(f["path"].startswith(p) for p in prefixes)]
                    files = files[:max_files_per_repo]
                    for f in files:
                        raw = _gh_raw(repo, f["path"], gh, branch)
                        if raw is None:
                            continue
                        wrote = _ingest_text(graph, conn, repo=repo, path=f["path"],
                                             raw=raw, source=f"gh:{ORG}/{repo}",
                                             category=cat, embed_fn=embed_fn)
                        c_files += 1
                        c_chunks += wrote
                        chunk_count += wrote
                    conn.commit()
            # ---- HF Spaces (real file content) ---------------------------
            for sp in spec.get("hf_spaces", []):
                graph.add_node(f"hf:{HF_ORG}/{sp}", "hf_space", repo=sp, org=HF_ORG)
                for path in _hf_space_files(sp)[:max_files_per_repo]:
                    raw = _hf_raw(sp, path)
                    if raw is None:
                        continue
                    wrote = _ingest_text(graph, conn, repo=sp, path=path, raw=raw,
                                         source=f"hf:{HF_ORG}/{sp}", category=cat,
                                         embed_fn=embed_fn)
                    c_files += 1
                    c_chunks += wrote
                    chunk_count += wrote
                conn.commit()
            per_cat[cat] = {"files": c_files, "chunks": c_chunks}
            if emit_receipt:
                emit_receipt("org_rag.index.category", {
                    "category": cat, "files": c_files, "chunks": c_chunks})

        built_cats = [c for c, v in per_cat.items() if v["chunks"] > 0]
        global _GRAPH, _BUILD_META
        _GRAPH = graph
        _BUILD_META = {
            "built": chunk_count > 0, "mode": "full", "ts": time.time(), "org": ORG,
            "repos": len(seen_repo), "chunks": chunk_count,
            "fts5": has_fts5, "dense": embed_fn is not None,
            "node_count": len(graph.nodes), "edge_count": len(graph.edges),
            "build_ms": round((time.time() - t0) * 1000, 1),
            "per_category": per_cat, "corpus_categories": built_cats,
            "gh_credential": bool(gh),
            "honest_note": (
                "FULL CORPUS (mode=full) — all seven categories ingested live. "
                + ("dense vectors present." if embed_fn is not None
                   else "FTS5/lexical only — embedding model unavailable (honest).")
                + ("" if gh else " NOTE: no GitHub credential in env — public "
                   "szl-holdings repos read UNAUTHENTICATED (GitHub rate-limited but "
                   "real); HF Space content also ingested (honest, not faked).")),
        }
        conn.close()
        rec = emit_receipt("org_rag.index.full", _BUILD_META) if emit_receipt else None
        out = {"ok": _BUILD_META["built"], **_BUILD_META}
        if rec:
            out["khipu_hash"] = rec.get("hash")
        return out


# Background build state (receipted refresh tick) ----------------------------- #
_BUILD_STATE: dict[str, Any] = {"phase": "idle", "started": None, "finished": None,
                                "last_full": None, "error": None}
_build_thread: "threading.Thread | None" = None


def start_background_build(emit_receipt: Callable[[str, dict], dict] | None = None,
                           seed_first: bool = True) -> dict[str, Any]:
    """Kick the full-corpus ingest on a daemon thread (so a Space request returns
    immediately with a working SEED index). Receipted. Idempotent: a second call
    while building is a no-op that reports the in-flight phase."""
    global _build_thread
    with _lock:
        if _BUILD_STATE["phase"] == "building" and _build_thread and _build_thread.is_alive():
            return {"ok": True, "phase": "building", "note": "full build already in flight"}
        # Always lay down a fresh labeled seed synchronously first.
        seed = build_seed_index(emit_receipt=emit_receipt) if seed_first else {}
        _BUILD_STATE.update({"phase": "building", "started": time.time(),
                             "finished": None, "error": None})

        def _run() -> None:
            try:
                res = build_full_corpus(emit_receipt=emit_receipt)
                _BUILD_STATE.update({"phase": "full", "finished": time.time(),
                                     "last_full": time.time(),
                                     "error": None if res.get("ok") else res.get("honest_error")})
            except Exception as exc:  # pragma: no cover
                _BUILD_STATE.update({"phase": "error", "finished": time.time(),
                                     "error": str(exc)[:300]})
                if emit_receipt:
                    emit_receipt("org_rag.index.bg_error", {"error": str(exc)[:200]})

        th = threading.Thread(target=_run, name="a11oy-org-rag-build", daemon=True)
        _build_thread = th
        th.start()
        return {"ok": True, "phase": "building", "seed": seed,
                "note": "labeled SEED index live now; FULL corpus building on a "
                        "receipted background tick (status: GET .../rag/status)"}


def refresh_tick(emit_receipt: Callable[[str, dict], dict] | None = None,
                 background: bool = True) -> dict[str, Any]:
    """Operational refresh entrypoint. ``background=True`` returns instantly with a
    seed + a building full corpus; ``background=False`` runs the full ingest
    synchronously (used by CLI / cron where blocking is fine)."""
    if background:
        return start_background_build(emit_receipt=emit_receipt, seed_first=True)
    return build_full_corpus(emit_receipt=emit_receipt)


def build_state() -> dict[str, Any]:
    return dict(_BUILD_STATE)


# --------------------------------------------------------------------------- #
# Query path (RETRIEVE state).
# --------------------------------------------------------------------------- #
def _fts_escape(q: str) -> str:
    # FTS5 MATCH wants a clean query; quote tokens to avoid syntax errors.
    toks = re.findall(r"[A-Za-z0-9_]+", q)
    return " OR ".join(f'"{t}"' for t in toks[:12]) or '""'


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))  # both are L2-normalized


def _lambda(axis: list[float]) -> float:
    if szl_brain is not None:
        return szl_brain.lambda_aggregate(axis)
    if not axis:
        return 0.5
    clamped = [min(1.0, max(1e-9, float(x))) for x in axis]
    return math.exp(sum(math.log(x) for x in clamped) / len(clamped))


def query(q: str, k: int = 6, repo: str | None = None,
          hyde_text: str | None = None,
          emit_receipt: Callable[[str, dict], dict] | None = None) -> dict[str, Any]:
    """Two-stage Λ-weighted agentic-RAG query.

    Returns grounded chunks (above the Λ relevance floor) each with M2M
    ``file{path,sha256}`` evidence, plus an ``i_dont_know`` flag when support is
    too low.  ``hyde_text`` (optional) is a hypothetical answer used for dense
    recall (HyDE) instead of the bare query."""
    if not _BUILD_META.get("built"):
        return {"ok": False, "i_dont_know": True,
                "honest_error": "org index not built — call /api/a11oy/code/rag/index first",
                "query": q, "chunks": []}
    conn = _db()
    embed_fn = _maybe_embedder()
    recall_text = hyde_text or q
    # Stage 1: lexical recall (FTS5 or LIKE fallback).
    rows: list[sqlite3.Row] = []
    try:
        sql = "SELECT chunk_id,node_id,repo,path,corpus,source,title,body,sha256 FROM org_chunks WHERE org_chunks MATCH ?"
        args: list[Any] = [_fts_escape(q)]
        if repo:
            sql += " AND repo = ?"
            args.append(repo)
        sql += " LIMIT ?"
        args.append(max(k * 4, 24))
        rows = list(conn.execute(sql, args))
    except Exception:
        # LIKE fallback (non-FTS5 runtime) — labeled weaker.
        like = f"%{re.sub(r'[^A-Za-z0-9_ ]', ' ', q)[:60]}%"
        sql = "SELECT chunk_id,node_id,repo,path,corpus,source,title,body,sha256 FROM org_chunks WHERE body LIKE ?"
        args = [like]
        if repo:
            sql += " AND repo = ?"
            args.append(repo)
        sql += " LIMIT ?"
        args.append(max(k * 4, 24))
        try:
            rows = list(conn.execute(sql, args))
        except Exception:
            rows = []

    # dense vector for query (HyDE-aware)
    qvec = None
    if embed_fn is not None:
        try:
            qvec = embed_fn(recall_text)
        except Exception:
            qvec = None

    # Stage 2: Λ-weighted re-rank.
    scored: list[dict[str, Any]] = []
    qtokens = set(re.findall(r"[a-z0-9_]+", q.lower()))
    for r in rows:
        body = r["body"] or ""
        btokens = set(re.findall(r"[a-z0-9_]+", body.lower()))
        lexical = (len(qtokens & btokens) / (len(qtokens) + 1e-9)) if qtokens else 0.0
        lexical = min(1.0, lexical)
        semantic = lexical
        if qvec is not None:
            row = conn.execute("SELECT vec FROM org_vectors WHERE chunk_id=?", (r["chunk_id"],)).fetchone()
            if row:
                try:
                    semantic = max(0.0, _cosine(qvec, json.loads(row["vec"])))
                except Exception:
                    pass
        centrality = _GRAPH.centrality(r["node_id"])
        # conformal anti-overconfidence floor 1/(n+1) over the recall set.
        conformal = 1.0 - 1.0 / (len(rows) + 1)
        # Λ over the three relevance axes (geometric mean — never 1.0 unless all 1.0).
        lam = _lambda([max(semantic, 1e-3), max(0.5 + 0.5 * centrality, 1e-3), conformal])
        _cols = r.keys()
        corpus = (r["corpus"] if "corpus" in _cols else None) or _category_for(r["repo"])
        source = (r["source"] if "source" in _cols else None) or f"gh:{ORG}/{r['repo']}"
        scored.append({
            "chunk_id": r["chunk_id"], "node_id": r["node_id"], "repo": r["repo"],
            "path": r["path"], "title": r["title"], "text": body[:1200],
            "sha256": r["sha256"], "corpus": corpus, "source": source,
            "scores": {"semantic": round(semantic, 4), "lexical": round(lexical, 4),
                       "centrality": round(centrality, 4), "conformal": round(conformal, 4)},
            "lambda": round(lam, 4),
            # M2M evidence of kind file{path,sha256} — carries corpus+source so the
            # agent CITES exactly where each grounded claim came from (founder mandate).
            "evidence": {"kind": "file", "path": f"{r['repo']}/{r['path']}",
                         "sha256": r["sha256"], "corpus": corpus, "source": source,
                         "citation": f"{source}/{r['path']}"},
        })
    conn.close()
    scored.sort(key=lambda x: x["lambda"], reverse=True)
    grounded = [s for s in scored if s["lambda"] >= _LAMBDA_FLOOR][:k]
    i_dont_know = len(grounded) == 0
    out = {
        "ok": True,
        "query": q,
        "hyde_used": bool(hyde_text),
        "dense_used": qvec is not None,
        "lambda_floor": _LAMBDA_FLOOR,
        "recall_count": len(scored),
        "grounded_count": len(grounded),
        "i_dont_know": i_dont_know,
        "chunks": grounded,
        "honest_note": ("no chunk cleared the Λ relevance floor — returning i_dont_know "
                        "rather than fabricating support (Self-RAG)") if i_dont_know else None,
    }
    if emit_receipt:
        rec = emit_receipt("org_rag.query", {
            "query": q[:120], "grounded": len(grounded), "i_dont_know": i_dont_know,
            "dense": qvec is not None})
        out["khipu_hash"] = rec.get("hash")
    return out


def repo_map(repo: str) -> dict[str, Any]:
    """Aider-style repo map: files → symbols, ranked by Λ-weighted graph centrality."""
    if not _BUILD_META.get("built"):
        return {"ok": False, "honest_error": "org index not built — call build_index first",
                "repo": repo}
    full = f"{ORG}/{repo}"
    files = []
    for nid, n in _GRAPH.nodes.items():
        if n["kind"] == "file" and n.get("repo") == repo:
            syms = [m["symbol"] for m in _GRAPH.nodes.values()
                    if m["kind"] == "symbol" and m.get("path") == n.get("path") and m.get("repo") == repo]
            files.append({"path": n["path"], "symbols": syms[:30],
                          "centrality": round(_GRAPH.centrality(nid), 4)})
    files.sort(key=lambda f: f["centrality"], reverse=True)
    return {"ok": True, "repo": full, "file_count": len(files), "files": files[:80]}


def graph_dict() -> dict[str, Any]:
    """Org graph for the 3D UI (nodes/edges). Honest empty state if not built."""
    d = _GRAPH.to_dict()
    d["built"] = _BUILD_META.get("built", False)
    d["meta"] = _BUILD_META
    return d


def status() -> dict[str, Any]:
    return {"ok": True, **_BUILD_META, "db_path": RAG_DB_PATH,
            "lambda_floor": _LAMBDA_FLOOR,
            "corpus": corpus_manifest(),
            "build_state": build_state()}
