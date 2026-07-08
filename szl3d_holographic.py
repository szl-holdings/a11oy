# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""szl3d_holographic.py — shared 3D toolkit + holographic shell server (Dev0 foundation).

ADDITIVE, self-contained, 0 runtime CDN. Serves the sovereign in-image 3D estate:

  * GET /static/3d/{path}        — the vendored three.js r170 libs + the szl3d toolkit
                                   (szl3d_boot/live/label) + the 9 surface stub modules +
                                   the selftest harness. Path-traversal-safe, allowlisted by
                                   extension + confined to the on-disk static/3d tree. Served
                                   BEFORE the SPA /{full_path:path} catch-all so the shell's
                                   ES-module imports resolve same-origin (no CDN, doctrine v11).
  * GET /holographic , /a11oy/holographic — the tab-switcher shell hosting the 9 surfaces
                                   (energy, fabric, pnt, counter-uas, governance, pinn, router,
                                   anatomy, estate), each lazy-loading its per-surface module.

This module does NOT invent data. The shell + toolkit render pixels; every value a surface
shows traces to a real a11oy endpoint via szl3d_live.poll and carries its honesty label
(MEASURED/MODELED/SAMPLE/STRUCTURAL-ONLY) read straight from the JSON. WebGPU is attempted
with a graceful WebGL2 fallback (WebGPU is not production-safe on Linux/mobile yet).

Mirrors the existing in-image static-serve pattern (serve.py /static/shared/{fname},
/vendor/{fname}, /hero/vendor3d/{fname}) and the register(app, ns) module pattern
(a11oy_active_flux_router.register).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

# Surface slots (id, human title) — the frontier tier + the 9 estate surfaces.
SURFACES: List[Dict[str, str]] = [
    {"id": "atlas", "cat": "map", "flag": True, "title": "Atlas", "owner": "Wave27"},
    {"id": "frontier", "cat": "map", "title": "Frontier", "owner": "Dev0"},
    {"id": "neuromorphic", "cat": "more", "title": "Neuromorphic", "owner": "Dev0"},
    {"id": "interpretability", "cat": "governance", "title": "Interpretability", "owner": "Dev0"},
    {"id": "circuits", "cat": "governance", "title": "Attribution Graph · Circuit Tracing", "owner": "WaveN-Dev4"},
    {"id": "worldmodel", "cat": "attention", "title": "World Model", "owner": "Dev0"},
    {"id": "qec", "cat": "proof", "title": "Topological QEC", "owner": "Dev0"},
    {"id": "episodic", "cat": "brain", "title": "Episodic Memory", "owner": "Dev0"},
    {"id": "testtime", "cat": "reasoning", "title": "Test-Time Compute", "owner": "Dev0"},
    {"id": "ssm", "cat": "attention", "title": "State-Space (Mamba-3)", "owner": "Dev0"},
    {"id": "genie", "cat": "attention", "title": "Genie World-Model", "owner": "Dev0"},
    {"id": "specdecode", "cat": "attention", "title": "Speculative Decoding", "owner": "Dev0"},
    {"id": "flowmatch", "cat": "attention", "title": "Flow Matching", "owner": "Dev0"},
    {"id": "dllm", "cat": "attention", "title": "Diffusion LLM", "owner": "Dev0"},
    {"id": "moe", "cat": "attention", "title": "MoE Router", "owner": "Dev0"},
    {"id": "formalmath", "cat": "governance", "title": "Formal-Math Retrieval", "owner": "Dev0"},
    {"id": "ccattest", "cat": "proof", "title": "Confidential-Compute Attest", "owner": "Dev0"},
    {"id": "attestinfer", "cat": "proof", "title": "Attested Inference", "owner": "WaveH-Team3"},
    {"id": "pcai", "cat": "proof", "title": "Proof-Carrying Attested Inference", "owner": "WaveN-Dev2"},
    {"id": "ringattn", "cat": "attention", "title": "Ring Attention", "owner": "Dev0"},
    {"id": "grpo", "cat": "rl", "title": "GRPO Reward Dynamics", "owner": "Dev0"},
    {"id": "kvcache", "cat": "quant", "title": "KV-Cache H2O", "owner": "Dev0"},
    {"id": "mla", "cat": "attention", "title": "Latent Attention (MLA)", "owner": "Dev0"},
    {"id": "blt", "cat": "attention", "title": "Byte-Latent Patching", "owner": "Dev0"},
    {"id": "nsa", "cat": "attention", "title": "Native Sparse Attention", "owner": "Dev0"},
    {"id": "kan", "cat": "attention", "title": "Kolmogorov-Arnold Network", "owner": "Dev0"},
    {"id": "steering", "cat": "governance", "title": "Steering Vectors (ActAdd / RepE)", "owner": "Dev0"},
    {"id": "titans", "cat": "brain", "title": "Titans Neural Long-Term Memory", "owner": "Dev0"},
    {"id": "mor", "cat": "reasoning", "title": "Mixture-of-Recursions (adaptive depth)", "owner": "Dev0"},
    {"id": "goat", "cat": "attention", "title": "GOAT Optimal-Transport Attention", "owner": "Dev0"},
    {"id": "kla", "cat": "attention", "title": "Kaczmarz Linear Attention", "owner": "Dev0"},
    {"id": "hrm", "cat": "reasoning", "title": "Hierarchical Reasoning Model", "owner": "Dev0"},
    {"id": "pfield", "cat": "anatomy", "title": "Pressure-Field Coordination", "owner": "Dev0"},
    {"id": "qhall", "cat": "governance", "title": "Quantum-Inspired Hallucination UQ", "owner": "Dev0"},
    {"id": "aimc", "cat": "attention", "title": "Analog In-Memory Attention", "owner": "Dev0"},
    {"id": "ternary", "cat": "quant", "title": "Ternary 1.58-bit Weights", "owner": "Dev0"},
    {"id": "sement", "cat": "governance", "title": "Semantic-Entropy Uncertainty", "owner": "Dev0"},
    {"id": "inplacettt", "cat": "reasoning", "title": "In-Place Test-Time Training", "owner": "Dev0"},
    {"id": "nested", "cat": "brain", "title": "Nested Learning (multi-timescale)", "owner": "Dev0"},
    {"id": "matgran", "cat": "brain", "title": "Matryoshka Representation Granularity", "owner": "Dev0"},
    {"id": "graphmem", "cat": "brain", "title": "Multi-Graph Agentic Memory", "owner": "Dev0"},
    {"id": "elf", "cat": "attention", "title": "Continuous-Embedding Flow LM", "owner": "Dev0"},
    {"id": "s3search", "cat": "quant", "title": "Stratified Denoise Search", "owner": "Dev0"},
    {"id": "slidesparse", "cat": "quant", "title": "Structured-Sparse Layout Packing", "owner": "Dev0"},
    {"id": "catq", "cat": "quant", "title": "Calibration Ternary Quant", "owner": "Dev0"},
    {"id": "rauq", "cat": "governance", "title": "Attention-Pattern Uncertainty", "owner": "Dev0"},
    {"id": "agentcoh", "cat": "brain", "title": "Multi-Agent Memory Coherence", "owner": "Dev0"},
    {"id": "energy", "cat": "energy", "title": "Energy", "owner": "Dev1"},
    {"id": "fabric", "cat": "defense", "title": "Compute Fabric", "owner": "Dev2"},
    {"id": "pnt", "cat": "defense", "title": "PNT", "owner": "Dev3"},
    {"id": "counter-uas", "cat": "defense", "title": "Counter-UAS", "owner": "Dev4"},
    {"id": "governance", "cat": "governance", "flag": True, "title": "Governance", "owner": "Dev5"},
    {"id": "pinn", "cat": "defense", "title": "PINN", "owner": "Dev6"},
    {"id": "router", "cat": "defense", "title": "Router", "owner": "Dev7"},
    {"id": "anatomy", "cat": "anatomy", "title": "Anatomy", "owner": "Dev8"},
    {"id": "anatomy_body", "cat": "anatomy", "flag": True, "title": "Anatomy · Living Body", "owner": "Dev8"},
    {"id": "estate", "cat": "map", "title": "Estate", "owner": "Dev9"},
    {"id": "muon", "cat": "attention", "title": "Muon Orthogonalized-Momentum Optimizer", "owner": "Wave13"},
    {"id": "specexec", "cat": "attention", "title": "Tree Speculative Execution", "owner": "Wave13"},
    {"id": "nvfp4", "cat": "quant", "title": "NVFP4 4-bit Training Format", "owner": "Wave13"},
    {"id": "keyless", "cat": "attention", "title": "Keyless Attention (Value-Only Cache)", "owner": "Wave14"},
    {"id": "gitthoughts", "cat": "reasoning", "title": "GitOfThoughts (Version-Controlled Reasoning)", "owner": "Wave14"},
    {"id": "herotq", "cat": "quant", "title": "HeRo-Q Hessian-Conditioned Quantization", "owner": "Wave14"},
    {"id": "dla", "cat": "attention", "title": "Dynamic Linear Attention", "owner": "Wave15"},
    {"id": "ctxready", "cat": "reasoning", "title": "Context-Ready Transformer", "owner": "Wave15"},
    {"id": "opera", "cat": "reasoning", "title": "OPERA Perplexity-Reward Alignment", "owner": "Wave15"},
    {"id": "brain", "cat": "brain", "flag": True, "title": "Brain — live knowledge graph", "owner": "Wave15"},
    {"id": "zkinfer", "cat": "proof", "title": "zkML Proof-of-Inference (Cryptographic Receipts)", "owner": "Wave18"},
    {"id": "flower", "cat": "brain", "title": "Flower Brain", "owner": "Wave24"},
    {"id": "agentmem", "cat": "brain", "title": "AgentMem · Λ-Governed Agent Memory (synthesis)", "owner": "Wave19"},
    {"id": "loopforge", "cat": "brain", "title": "Loop Forge", "owner": "Wave25"},
    {"id": "edgefusion", "cat": "energy", "title": "EdgeFusion · Λ-Gated Energy-Proportional Sensor Fusion (synthesis)", "owner": "Wave19"},
    {"id": "evalarena", "cat": "governance", "flag": True, "title": "Eval Arena · Governed Eval / Red-Team", "owner": "WaveH-Team2"},
    {"id": "vqc", "cat": "energy", "title": "Governed VQC · Parameter-Shift Hybrid QML (MODELED)", "owner": "WaveH"},
    {"id": "harness", "cat": "governance", "title": "Governed Model Harness · Behavior Transfer", "owner": "WaveF"},
    {"id": "aigov", "cat": "governance", "title": "AI Governance Conformance · Λ-Advisory Readiness (crosswalk)", "owner": "WaveF"},
    {"id": "fmverif", "cat": "proof", "title": "Proof-Carrying Inference (Machine-Checkable Certificates)", "owner": "WaveF"},
    {"id": "supplychain", "cat": "proof", "title": "Model-Artifact Provenance (SLSA / in-toto / Rekor / C2PA)", "owner": "WaveF"},
    {"id": "hybridssm", "cat": "attention", "title": "HybridSSM · Attention vs State-Space vs Hybrid Frontier (synthesis)", "owner": "WaveF"},
    {"id": "governedagent", "cat": "reasoning", "title": "Governed Agent Loop · plan→act→self-eval→gate→retry", "owner": "WaveJ-Dev5"},
    {"id": "governedrag", "cat": "reasoning", "title": "Governed RAG · Retrieval-with-Receipts", "owner": "WaveJ-Dev4"},
    {"id": "ecosystem", "cat": "defense", "flag": True, "title": "Harness · Ecosystem Status", "owner": "Wave30-Dev3"},
    {"id": "brainquery", "cat": "brain", "flag": True, "title": "Brain Query · ask the graph (retrieval)", "owner": "Wave1-Frontier"},
    {"id": "sovereign", "cat": "energy", "flag": True, "title": "Sovereign Local Model · status · doctrine self-test · Stage A/B · signed receipt", "owner": "WaveM-Dev4"},
    {"id": "brainbody", "cat": "anatomy", "title": "Anatomy · Body lit by the Brain (pulse + energy)", "owner": "WaveO-Dev3"},
    {"id": "braincommand", "cat": "brain", "title": "Brain Command · pulse · subscribe/budget · signed receipt (Brain powering the ecosystem)", "owner": "WaveO-Dev5"},
    {"id": "mesh", "cat": "defense", "title": "Sovereign Mesh · Cross-Node Orchestration (status/route/quorum)", "owner": "WaveP-Dev2"},
    {"id": "agenttts", "cat": "reasoning", "title": "Agent Test-Time Compute · Multi-Agent TTC (best-of-N agents + verifier-guided selection)", "owner": "WaveQ-Dev3"},
    {"id": "cryptopipeline", "cat": "proof", "title": "Crypto-Pipeline · End-to-End AI Lifecycle Verifiable Transcript (MODELED)", "owner": "WaveQ-Dev2"},
    {"id": "gateddelta", "cat": "attention", "title": "Gated Delta-Rule Linear Attention · state recall (MODELED)", "owner": "WaveQ-Dev1"},
    {"id": "agentops", "cat": "reasoning", "title": "Agent Ops · bounded operate loop (ground→act→self-eval→gate, Ouroboros-bounded, writer≠judge)", "owner": "WaveP-Dev5"},
    {"id": "lgmi", "cat": "governance", "title": "LGMI · Λ-Governed Mechanistic Interpretability (synthesis)", "owner": "WaveP-Dev4"},
    {"id": "gnqs", "cat": "quant", "title": "GNQS · Governed-Norm Quantization Stability (synthesis)", "owner": "WaveP-Dev4"},
    {"id": "casta", "cat": "defense", "title": "CASTA · Clean-room Anomaly × Streaming Test-time Adaptation (synthesis)", "owner": "WaveP-Dev4"},
    {"id": "frontierindex", "cat": "brain", "title": "Frontier Index · honest ecosystem catalog · per-surface backend label + citations + native/fallback (self-audited)", "owner": "WaveQ-Dev5"},
    {"id": "sparsemoe", "cat": "quant", "title": "Extreme-Sparsity MoE Analyzer · activation-ratio ↔ inference-cost tradeoff (STRUCTURAL-ONLY)", "owner": "WaveP-Dev4"},
    {"id": "pddisagg", "cat": "defense", "title": "Prefill/Decode Disaggregation Map · colocated vs disaggregated latency across the mesh (STRUCTURAL-ONLY/ROADMAP)", "owner": "WaveP-Dev4"},
    {"id": "execverify", "cat": "reasoning", "title": "Execution-Verified Synthesis Loop · eval → verified trajectory → corpus candidate → receipt (STRUCTURAL-ONLY)", "owner": "WaveP-Dev4"},
    {"id": "opsdash", "cat": "governance", "flag": True, "title": "Ops Dashboard · live estate health · GREEN/DEGRADED/UNAVAILABLE rollup + per-surface honest labels + /verify", "owner": "WaveR-Dev3"},
]

# Content-type by extension (the only extensions we serve from the 3d tree).
_CT = {
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def _base_dir() -> Path:
    """The on-disk root of the 3D tree. In-image this is /app/static/3d; in a dev
    checkout it is <repo>/static/3d. Resolve from this file's location, then fall
    back to the image path."""
    here = Path(__file__).resolve().parent / "static" / "3d"
    if here.is_dir():
        return here.resolve()
    return Path("/app/static/3d").resolve()


def _safe_resolve(base: Path, relpath: str) -> Path | None:
    """Resolve `relpath` under `base`, rejecting any path traversal. Returns the
    resolved file Path iff it is a real file strictly inside base, else None."""
    relpath = (relpath or "").lstrip("/")
    if not relpath:
        return None
    candidate = (base / relpath).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None  # escaped the base dir — reject
    if candidate.is_file():
        return candidate
    return None


import re as _re

# Fetch-shaped external references doctrine v11 forbids in OUR code/HTML:
#   <script src="http..."> , <link href="http..."> , import ... from "http..." ,
#   import("http...") , importmap target "http..." , fetch("http...") , url(http...) .
# (Incidental URLs in comments / XML namespaces / vendored minified libs are NOT
#  runtime fetches and are out of scope — see selftest note.)
_CDN_PATTERNS = [
    _re.compile(r"""<script[^>]*\bsrc\s*=\s*['"]https?://""", _re.I),
    _re.compile(r"""<link[^>]*\bhref\s*=\s*['"]https?://""", _re.I),
    _re.compile(r"""\bimport\b[^;\n]*\bfrom\s*['"]https?://""", _re.I),
    _re.compile(r"""\bimport\s*\(\s*['"]https?://""", _re.I),
    _re.compile(r"""['"]https?://[^'"]+['"]\s*:""", _re.I),   # importmap "http...": target
    _re.compile(r"""\bfetch\s*\(\s*['"`]https?://""", _re.I),
    _re.compile(r"""url\(\s*['"]?https?://""", _re.I),        # CSS url(http...)
]


def no_cdn_violations(base: Path):
    """Yield 'file: snippet' strings for any FETCH-SHAPED external URL in the authored
    3d tree (everything except vendor/). Used by both _selftest and the pytest so the
    0-runtime-CDN doctrine is enforced identically in CI and in-image."""
    base = Path(base)
    vendor = (base / "vendor").resolve()
    for root, _dirs, files in os.walk(base):
        rp = Path(root).resolve()
        if rp == vendor or vendor in rp.parents:
            continue  # vendored libs are pinned-by-hash, out of scope
        for fn in files:
            if Path(fn).suffix.lower() not in (".js", ".html", ".css", ".mjs"):
                continue
            p = Path(root) / fn
            txt = p.read_text(encoding="utf-8", errors="ignore")
            for pat in _CDN_PATTERNS:
                m = pat.search(txt)
                if m:
                    s = max(0, m.start() - 10)
                    yield f"{p.name}: ...{txt[s:m.start()+70].strip()}..."
                    break


def shell_html(ns: str = "a11oy") -> str:
    """Read the holographic shell HTML off disk (single source of truth:
    static/3d/holographic.html). Falls back to a minimal honest stub if missing."""
    f = _base_dir() / "holographic.html"
    if f.is_file():
        return f.read_text(encoding="utf-8")
    return (
        "<!doctype html><meta charset=utf-8><title>Holographic Estate</title>"
        "<body style='background:#05070d;color:#9fb1bf;font:14px ui-monospace,monospace;padding:24px'>"
        "<h1>◇ Holographic Estate</h1><p>shell asset missing on disk "
        "(static/3d/holographic.html). 0 CDN; Doctrine v11.</p>"
    )


def info(ns: str = "a11oy") -> Dict[str, Any]:
    return {
        "capability": "Shared szl3d 3D toolkit + holographic shell",
        "ns": ns,
        "toolkit": {
            "boot": "/static/3d/szl3d/szl3d_boot.js",
            "live": "/static/3d/szl3d/szl3d_live.js",
            "label": "/static/3d/szl3d/szl3d_label.js",
        },
        "vendor": {
            "three_webgl2": "/static/3d/vendor/three/three.module.min.js",
            "three_webgpu": "/static/3d/vendor/three/three.webgpu.min.js",
            "addons": "/static/3d/vendor/three/addons/",
            "manifest": "/static/3d/vendor/VENDOR_MANIFEST.md",
            "three_revision": "r170",
        },
        "surfaces": SURFACES,
        "shell": {"page": "/holographic", "alias": "/a11oy/holographic"},
        "selftest": "/static/3d/selftest/index.html",
        "doctrine": {"locked_proven": 8, "lambda": "Conjecture 1", "khipu_bft": "Conjecture 2",
                     "runtime_cdn": 0, "webgpu": "attempt-then-WebGL2-fallback"},
        "status": "FOUNDATION",
    }


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the szl3d static tree + the /holographic shell. ADDITIVE; routes are
    registered BEFORE the SPA/proxy catch-all (call this early in serve.py, like the
    other in-image vendor routes). Never crashes the app — caller wraps in try/except."""
    from starlette.responses import HTMLResponse, JSONResponse, Response

    base = _base_dir()
    registered: List[str] = []

    async def _serve_3d(path: str):
        f = _safe_resolve(base, path)
        if f is None:
            return JSONResponse({"error": "3d asset not found", "path": path}, status_code=404)
        ct = _CT.get(f.suffix.lower())
        if ct is None:
            return JSONResponse({"error": "3d asset type not allowlisted", "path": path}, status_code=404)
        # Vendored libs are immutable; toolkit/surfaces change during dev -> shorter cache.
        immutable = "/vendor/" in ("/" + path)
        cache = "public, max-age=31536000, immutable" if immutable else "public, max-age=300"
        return Response(content=f.read_bytes(), media_type=ct, headers={"Cache-Control": cache})

    app.add_api_route("/static/3d/{path:path}", _serve_3d, methods=["GET"], include_in_schema=False)
    registered.append("GET /static/3d/{path}")

    _html = shell_html(ns)

    async def _shell():
        return HTMLResponse(_html)

    for route in ("/holographic", f"/{ns}/holographic"):
        app.add_api_route(route, _shell, methods=["GET"], include_in_schema=False)
        registered.append(f"GET {route}")

    async def _info():
        return JSONResponse(info(ns))

    for prefix in (f"/api/{ns}/v1/holographic", "/v1/holographic"):
        app.add_api_route(f"{prefix}/info", _info, methods=["GET"], include_in_schema=False)
    registered.append(f"GET /api/{ns}/v1/holographic/info")

    return {"registered": registered, "count": len(registered),
            "capability": "szl3d toolkit + holographic shell", "surfaces": len(SURFACES),
            "base_dir": str(base), "data_label": "FOUNDATION"}


def _selftest() -> None:
    base = _base_dir()
    # 1. toolkit files exist on disk
    for f in ("szl3d/szl3d_boot.js", "szl3d/szl3d_live.js", "szl3d/szl3d_label.js",
              "holographic.html", "vendor/VENDOR_MANIFEST.md",
              "vendor/three/three.module.min.js", "vendor/three/three.webgpu.min.js"):
        assert (base / f).is_file(), f"missing toolkit asset: {f}"
    # 2. all surface modules exist (frontier tier + the 9 estate surfaces)
    for s in SURFACES:
        assert (base / "surfaces" / f"{s['id']}.js").is_file(), f"missing surface: {s['id']}"
    # 3. path traversal is rejected
    assert _safe_resolve(base, "../serve.py") is None
    assert _safe_resolve(base, "../../etc/passwd") is None
    assert _safe_resolve(base, "szl3d/szl3d_boot.js") is not None
    # 4. NO runtime-CDN reference in OUR authored 3d code/HTML. The vendored libs
    #    (vendor/) are trusted upstream builds, pinned by sha256 in VENDOR_MANIFEST.md;
    #    they legitimately contain incidental URLs (XML namespaces, shader/doc comments)
    #    that are NOT fetched at runtime, so they are out of scope here. What doctrine v11
    #    forbids is OUR pages fetching from a CDN: a <script src>, an importmap target, an
    #    import specifier, or a fetch() pointed at an external host. We scan the files WE
    #    author (everything outside vendor/) for those fetch-shaped patterns.
    fetch_shaped = list(no_cdn_violations(base))
    assert not fetch_shaped, ("runtime-CDN reference found in authored 3d code/HTML "
                              "(0-CDN doctrine):\n" + "\n".join(fetch_shaped[:10]))
    # 5. info() surface
    i = info()
    assert i["vendor"]["three_revision"] == "r170"
    assert len(i["surfaces"]) == len(SURFACES) >= 9
    print(f"szl3d_holographic: ALL OK (toolkit+{len(SURFACES)} surfaces+vendor present, 0 CDN, traversal-safe)")


if __name__ == "__main__":
    _selftest()
