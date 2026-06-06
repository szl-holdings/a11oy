# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
szl_math_corpus — shared math-corpus loader + endpoint helpers (Doctrine v11 §13/§14).

ADDITIVE, self-contained module dropped beside serve.py in EVERY Space. At boot it
snapshot_downloads the 4 HF math Datasets into /tmp/szl_math_corpus/ and exposes pure
read helpers for the 8 /api/<space>/v1/math/* endpoints:

    /math/lean/theorems        — list lean files + theorem/lemma/def/axiom counts
    /math/lean/<name>          — one lean file's content
    /math/formulas             — the 21 canonical formula registry + proof-status
    /math/formula/<name>       — one formula's source + docstring + status
    /math/thesis/claims        — the 179 formal-block claims
    /math/thesis/claim/<label> — one claim by label
    /math/doctrine             — doctrine v10 + v11 text
    /math/reference-vectors    — the golden Λ verification vectors

Loading is best-effort and degrades honestly: if a dataset is unavailable the helper
returns {"available": False, "reason": ...} rather than fabricating data (ZERO BANDAID).
"""
from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

CORPUS_ROOT = Path(os.environ.get("SZL_MATH_CORPUS", "/tmp/szl_math_corpus"))
DATASETS = {
    "lean-proofs-v1": "SZLHOLDINGS/lean-proofs-v1",
    "canonical-formulas-v1": "SZLHOLDINGS/canonical-formulas-v1",
    "thesis-corpus-v18": "SZLHOLDINGS/thesis-corpus-v18",
    "doctrine-v10-v11": "SZLHOLDINGS/doctrine-v10-v11",
}
_STATUS: Dict[str, str] = {}


def boot_snapshot(token: Optional[str] = None) -> Dict[str, str]:
    """Boot-time snapshot_download of the 4 math datasets. Idempotent + best-effort."""
    try:
        from huggingface_hub import snapshot_download
    except Exception as e:  # huggingface_hub missing → honest degrade
        for k in DATASETS:
            _STATUS[k] = f"unavailable: huggingface_hub import failed ({e})"
        return _STATUS
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    tok = token or os.environ.get("HF_TOKEN")
    for key, repo in DATASETS.items():
        dest = CORPUS_ROOT / key
        try:
            snapshot_download(repo_id=repo, repo_type="dataset", local_dir=str(dest),
                              token=tok, etag_timeout=20)
            _STATUS[key] = "ok"
        except Exception as e:
            _STATUS[key] = f"unavailable: {type(e).__name__}: {e}"
    return _STATUS


def status() -> Dict[str, str]:
    return dict(_STATUS) or {k: "not yet downloaded" for k in DATASETS}


def _root(key: str) -> Path:
    return CORPUS_ROOT / key


# --------------------------------------------------------------------------- lean
def lean_theorems() -> Dict[str, Any]:
    root = _root("lean-proofs-v1")
    if not root.exists():
        return {"available": False, "reason": _STATUS.get("lean-proofs-v1", "not downloaded")}
    files = sorted(root.rglob("*.lean"))
    items = []
    total = {"theorem": 0, "lemma": 0, "def": 0, "axiom": 0, "sorry": 0}
    for f in files:
        txt = f.read_text(errors="replace")
        counts = {k: len(re.findall(rf"\b{k}\b", txt)) for k in ("theorem", "lemma", "def", "axiom")}
        counts["sorry"] = txt.count("sorry")
        for k in total:
            total[k] += counts[k]
        items.append({"name": str(f.relative_to(root)), **counts})
    return {"available": True, "file_count": len(files), "totals": total, "files": items,
            "canonical_numbers": "749 declarations / 14 unique axioms / 163 tracked sorries",
            "doctrine": "v11"}


def lean_file(name: str) -> Dict[str, Any]:
    root = _root("lean-proofs-v1")
    if not root.exists():
        return {"available": False, "reason": _STATUS.get("lean-proofs-v1", "not downloaded")}
    cand = [p for p in root.rglob("*.lean") if p.name == name or str(p.relative_to(root)) == name]
    if not cand:
        return {"available": True, "found": False, "name": name}
    f = cand[0]
    return {"available": True, "found": True, "name": str(f.relative_to(root)),
            "content": f.read_text(errors="replace"), "doctrine": "v11"}


# --------------------------------------------------------------------------- formulas
def _formulas_module():
    root = _root("canonical-formulas-v1")
    py = root / "code" / "python" / "formulas.py"
    if not py.exists():
        return None, root
    import importlib.util
    spec = importlib.util.spec_from_file_location("_szl_formulas_corpus", str(py))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod, root
    except Exception:
        return None, root


def formulas() -> Dict[str, Any]:
    mod, root = _formulas_module()
    if mod is None:
        if not root.exists():
            return {"available": False, "reason": _STATUS.get("canonical-formulas-v1", "not downloaded")}
        return {"available": True, "imported": False, "reason": "formulas.py present but not importable here"}
    reg = getattr(mod, "REGISTRY", {})
    ps = getattr(mod, "PROOF_STATUS", {})
    return {"available": True, "imported": True, "count": len(reg),
            "formulas": [{"name": n, "proof_status": ps.get(n, "?")} for n in reg],
            "doctrine": "v11"}


def formula(name: str) -> Dict[str, Any]:
    mod, root = _formulas_module()
    if mod is None:
        return {"available": bool(root.exists()), "imported": False,
                "reason": _STATUS.get("canonical-formulas-v1", "not importable")}
    reg = getattr(mod, "REGISTRY", {})
    ps = getattr(mod, "PROOF_STATUS", {})
    fn = reg.get(name)
    if fn is None:
        return {"available": True, "found": False, "name": name}
    return {"available": True, "found": True, "name": name,
            "proof_status": ps.get(name, "?"), "docstring": (fn.__doc__ or "").strip(),
            "doctrine": "v11"}


# --------------------------------------------------------------------------- thesis
def _thesis_claims() -> List[Dict[str, Any]]:
    root = _root("thesis-corpus-v18")
    csvp = root / "formal_blocks_179.csv"
    out: List[Dict[str, Any]] = []
    if csvp.exists():
        import csv as _csv
        with open(csvp, newline="") as fh:
            for row in _csv.DictReader(fh):
                out.append(dict(row))
        return out
    jp = root / "claims_v18_extracted.json"
    if jp.exists():
        try:
            return json.load(open(jp))
        except Exception:
            return []
    return []


def thesis_claims() -> Dict[str, Any]:
    root = _root("thesis-corpus-v18")
    if not root.exists():
        return {"available": False, "reason": _STATUS.get("thesis-corpus-v18", "not downloaded")}
    claims = _thesis_claims()
    return {"available": True, "count": len(claims), "claims": claims, "doctrine": "v11"}


def thesis_claim(label: str) -> Dict[str, Any]:
    root = _root("thesis-corpus-v18")
    if not root.exists():
        return {"available": False, "reason": _STATUS.get("thesis-corpus-v18", "not downloaded")}
    for c in _thesis_claims():
        if str(c.get("label", "")) == label:
            return {"available": True, "found": True, "claim": c, "doctrine": "v11"}
    return {"available": True, "found": False, "label": label}


# --------------------------------------------------------------------------- doctrine
def doctrine() -> Dict[str, Any]:
    root = _root("doctrine-v10-v11")
    if not root.exists():
        return {"available": False, "reason": _STATUS.get("doctrine-v10-v11", "not downloaded")}
    docs = {}
    for f in sorted(root.glob("*.md")):
        docs[f.name] = f.read_text(errors="replace")
    return {"available": True, "documents": list(docs.keys()), "content": docs, "doctrine": "v11"}


# --------------------------------------------------------------------------- reference vectors
def reference_vectors() -> Dict[str, Any]:
    root = _root("lean-proofs-v1")
    if not root.exists():
        return {"available": False, "reason": _STATUS.get("lean-proofs-v1", "not downloaded")}
    rv = list(root.rglob("reference-vectors.json"))
    if not rv:
        return {"available": True, "found": False}
    try:
        return {"available": True, "found": True, "vectors": json.load(open(rv[0])), "doctrine": "v11"}
    except Exception as e:
        return {"available": True, "found": True, "parse_error": str(e)}


# --------------------------------------------------------------------------- FastAPI wiring helper
def register_math_routes(app, space: str, token: Optional[str] = None, base_override: Optional[str] = None):
    """Attach the 8 /api/<space>/v1/math/* routes to a FastAPI app. ADDITIVE.

    If the target app is a sub-app mounted at /api/<space> (e.g. amaru's amaru_app),
    pass base_override="/v1/math" so the routes resolve correctly behind the mount.
    """
    from fastapi.responses import JSONResponse
    base = base_override if base_override is not None else f"/api/{space}/v1/math"

    @app.get(base + "/status")
    async def _m_status():
        return JSONResponse({"corpus_status": status(), "doctrine": "v11"})

    @app.get(base + "/lean/theorems")
    async def _m_lean_theorems():
        return JSONResponse(lean_theorems())

    @app.get(base + "/lean/{name}")
    async def _m_lean_file(name: str):
        return JSONResponse(lean_file(name))

    @app.get(base + "/formulas")
    async def _m_formulas():
        return JSONResponse(formulas())

    @app.get(base + "/formula/{name}")
    async def _m_formula(name: str):
        return JSONResponse(formula(name))

    @app.get(base + "/thesis/claims")
    async def _m_thesis_claims():
        return JSONResponse(thesis_claims())

    @app.get(base + "/thesis/claim/{label}")
    async def _m_thesis_claim(label: str):
        return JSONResponse(thesis_claim(label))

    @app.get(base + "/doctrine")
    async def _m_doctrine():
        return JSONResponse(doctrine())

    @app.get(base + "/reference-vectors")
    async def _m_refvecs():
        return JSONResponse(reference_vectors())

    return app


if __name__ == "__main__":
    tok = open("/home/user/workspace/szl/audit_2026-05-30_cursor_offline/.secret/hf_token").read().strip()
    print("booting corpus...")
    print(json.dumps(boot_snapshot(tok), indent=2))
    print("lean:", lean_theorems().get("file_count"), "files")
    print("formulas:", formulas().get("count"))
    print("thesis claims:", thesis_claims().get("count"))
    print("doctrine docs:", doctrine().get("documents"))
    print("refvecs found:", reference_vectors().get("found"))
