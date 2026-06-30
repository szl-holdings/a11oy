#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 8 locked-proven {F1,F4,F7,F11,F12,F18,F19,F22}; Λ = Conjecture 1.
"""
a11oy MODEL INTEL — live external model-intelligence for the `llm` / `arena` tabs.

Taxonomy home: services/ (live read-only market signal that the szl_brain tier
router can consult as an advisory quality input). ADDITIVE; never replaces the
real in-image tier catalog (/v1/llm/tiers) or a11oy's own governance eval-arena
(/v1/eval-arena) — it sits beside them as a second, externally-sourced opinion.

Wires three FREE / no-key public sources (server-side, timeout + warm cache +
HONEST fallback — last-good is kept and marked `stale`; a labelled SAMPLE snapshot
is served only when the feed has NEVER been reachable, and it is never presented
as live):

  GET /api/a11oy/v1/models/leaderboard  — LMArena human-preference Elo
      (HF datasets-server rows API over lmarena-ai/leaderboard-dataset).
      Adapts LMArena's signature blind-pairwise Elo leaderboard.
  GET /api/a11oy/v1/models/hub          — Hugging Face Hub top models by downloads
      (huggingface.co/api/models, no key). Adoption signal.
  GET /api/a11oy/v1/models/pareto       — quality (Elo) × adoption (downloads)
      non-dominated frontier. Adapts the Artificial Analysis multi-axis Pareto
      idea; price / tokens-per-sec axes are ROADMAP (no measured serving feed —
      NOT fabricated here).

All dual-registered at /v1/models/* as well and front-moved ahead of the
/api/a11oy/{path:path} Node proxy + /{full_path:path} SPA catch-all.

Honest labels (doctrine v11): live data carries a freshness stamp; the SAMPLE
snapshot is explicitly SAMPLE + dated + source-cited; price/latency are ROADMAP;
Elo feeding the router is an ADVISORY quality signal (Λ = Conjecture 1), never a
proof. Prior art cited: LMArena (formerly LMSYS Chatbot Arena), Hugging Face Hub,
Artificial Analysis, OpenRouter. No data is fabricated.

Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""

import threading
import time
from typing import Any, Optional

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = "v11"
LOCKED = "8 locked-proven {F1,F4,F7,F11,F12,F18,F19,F22}; Λ = Conjecture 1 (advisory)"
UA = {"User-Agent": "a11oy-model-intel/1.0 (+https://huggingface.co/spaces/SZLHOLDINGS/a11oy) governed-feed"}

_DATASETS_ROWS = "https://datasets-server.huggingface.co/rows"
_DATASETS_SPLITS = "https://datasets-server.huggingface.co/splits"
_LMARENA_DS = "lmarena-ai/leaderboard-dataset"
_HF_MODELS = "https://huggingface.co/api/models"

# Prior-art citations surfaced to the operator (never claimed as ours).
CITED = {
    "leaderboard": "LMArena (formerly LMSYS Chatbot Arena) — blind pairwise human-preference Elo",
    "hub": "Hugging Face Hub model registry (public metadata API)",
    "pareto": "Artificial Analysis — multi-axis (quality/cost/speed) Pareto methodology; OpenRouter routing",
}

# HONEST SAMPLE fallback — served ONLY if the live feed has never been reachable.
# Plausible but NOT freshly measured; dated + source-cited per doctrine (SAMPLE).
# Figures transcribed from VERTICALS_DATA.md (research note, 2026-06-25).
_SAMPLE_LEADERBOARD = {
    "as_of": "2026-06-25",
    "source": "LMArena leaderboard-dataset (research snapshot — NOT a live fetch)",
    "rows": [
        {"rank": 1, "model": "claude-fable-5", "organization": "Anthropic", "elo": 1508, "votes": None, "license": "proprietary"},
        {"rank": 2, "model": "gemini-3.1-pro", "organization": "Google", "elo": 1499, "votes": None, "license": "proprietary"},
        {"rank": 3, "model": "gpt-5.4", "organization": "OpenAI", "elo": 1495, "votes": None, "license": "proprietary"},
        {"rank": 4, "model": "deepseek-r1", "organization": "DeepSeek", "elo": 1448, "votes": None, "license": "open-weight (MIT)"},
        {"rank": 5, "model": "llama-4-maverick", "organization": "Meta", "elo": 1421, "votes": None, "license": "open-weight (Llama)"},
    ],
}


class _Cache:
    """Thread-safe warm cache with honest freshness labels (mirrors a11oy_vertical_feeds)."""

    def __init__(self) -> None:
        self._d: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            v = self._d.get(key)
            return dict(v) if v else None

    def put(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._d[key] = {"value": value, "fetched_at": time.time(), "ttl": ttl}

    def freshness(self, key: str) -> dict[str, Any]:
        rec = self.get(key)
        if not rec:
            return {"status": "empty", "age_s": None}
        age = time.time() - rec["fetched_at"]
        status = "live"
        if age > rec["ttl"]:
            status = "cached"
        if age > rec["ttl"] * 4:
            status = "stale"
        return {"status": status, "age_s": round(age, 1), "fetched_at": rec["fetched_at"]}


_CACHE = _Cache()


def _cached_fetch(key: str, url: str, ttl: float, parser=None, params=None) -> dict[str, Any]:
    """Serve warm cache within TTL; else refetch. On error keep last-good + mark
    stale. Never fabricate — returns value=None when nothing has ever been fetched."""
    rec = _CACHE.get(key)
    now = time.time()
    if rec and (now - rec["fetched_at"]) < rec["ttl"]:
        return {"value": rec["value"], "freshness": _CACHE.freshness(key)}
    try:
        with httpx.Client(timeout=14.0, headers=UA, follow_redirects=True) as cl:
            r = cl.get(url, params=params) if params else cl.get(url)
            r.raise_for_status()
            data = r.json()
        val = parser(data) if parser else data
        _CACHE.put(key, val, ttl)
        return {"value": val, "freshness": _CACHE.freshness(key)}
    except Exception as e:
        if rec:
            f = _CACHE.freshness(key)
            f["status"] = "stale"
            f["error"] = f"{type(e).__name__}: {str(e)[:120]}"
            return {"value": rec["value"], "freshness": f}
        return {"value": None, "freshness": {"status": "unavailable",
                                             "error": f"{type(e).__name__}: {str(e)[:160]}"}}


def _num(x):
    try:
        f = float(x)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _lmarena_split() -> tuple[str, str]:
    """Discover a (config, split) for the LMArena dataset; honest default on failure."""
    try:
        with httpx.Client(timeout=10.0, headers=UA, follow_redirects=True) as cl:
            r = cl.get(_DATASETS_SPLITS, params={"dataset": _LMARENA_DS})
            r.raise_for_status()
            splits = (r.json() or {}).get("splits") or []
            if splits:
                s = splits[0]
                return s.get("config", "default"), s.get("split", "train")
    except Exception:
        pass
    return "default", "train"


def _parse_lmarena(rows_json: dict) -> dict:
    """Map HF datasets-server rows into a normalized Elo leaderboard. Column names
    in community leaderboard datasets vary, so we probe a set of known aliases and
    keep only rows that yield a real Elo — never invent a score."""
    rows = (rows_json or {}).get("rows") or []
    model_keys = ("model", "Model", "model_name", "key", "name")
    elo_keys = ("rating", "elo", "Elo", "score", "arena_score", "arena_elo")
    org_keys = ("organization", "Organization", "provider", "org")
    vote_keys = ("votes", "num_votes", "vote_count", "Votes")
    lic_keys = ("license", "License")
    out = []
    for entry in rows:
        row = entry.get("row", entry) if isinstance(entry, dict) else {}
        model = next((row[k] for k in model_keys if row.get(k)), None)
        elo = next((_num(row[k]) for k in elo_keys if _num(row.get(k)) is not None), None)
        if not model or elo is None:
            continue
        out.append({
            "model": str(model),
            "elo": round(elo, 1),
            "organization": next((str(row[k]) for k in org_keys if row.get(k)), None),
            "votes": next((row[k] for k in vote_keys if row.get(k) is not None), None),
            "license": next((str(row[k]) for k in lic_keys if row.get(k)), None),
        })
    out.sort(key=lambda r: r["elo"], reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return {"rows": out, "source": f"LMArena via HF datasets-server ({_LMARENA_DS})"}


def get_leaderboard(limit: int = 40) -> dict[str, Any]:
    cfg, split = _lmarena_split()
    res = _cached_fetch(
        "lmarena_elo", _DATASETS_ROWS, ttl=1800, parser=_parse_lmarena,
        params={"dataset": _LMARENA_DS, "config": cfg, "split": split, "offset": 0, "length": 100},
    )
    val = res.get("value")
    rows = (val or {}).get("rows") if val else None
    if rows:
        return {"leaderboard": rows[:limit], "count": len(rows), "live": True,
                "source": val.get("source"), "freshness": res["freshness"],
                "cited": CITED["leaderboard"], "doctrine": DOCTRINE}
    # Honest SAMPLE — feed never reachable. Clearly labelled, dated, NOT live.
    return {"leaderboard": _SAMPLE_LEADERBOARD["rows"][:limit],
            "count": len(_SAMPLE_LEADERBOARD["rows"]), "live": False, "label": "SAMPLE",
            "source": _SAMPLE_LEADERBOARD["source"], "as_of": _SAMPLE_LEADERBOARD["as_of"],
            "freshness": res["freshness"], "cited": CITED["leaderboard"],
            "honesty": "LMArena live feed unreachable; serving a labelled, dated SAMPLE snapshot — NOT live.",
            "doctrine": DOCTRINE}


def get_hub(limit: int = 40) -> dict[str, Any]:
    def parse(d):
        items = d if isinstance(d, list) else []
        return [{"id": m.get("id"), "downloads": m.get("downloads"), "likes": m.get("likes"),
                 "pipeline_tag": m.get("pipeline_tag"), "library_name": m.get("library_name")}
                for m in items]
    res = _cached_fetch(
        "hf_hub_downloads", _HF_MODELS, ttl=900, parser=parse,
        params={"sort": "downloads", "direction": -1, "limit": min(max(limit, 1), 100)},
    )
    val = res.get("value")
    return {"models": (val or [])[:limit], "count": len(val or []),
            "live": bool(val), "freshness": res["freshness"],
            "cited": CITED["hub"],
            "honesty": None if val else "Hugging Face Hub unreachable; no fabricated roster returned.",
            "doctrine": DOCTRINE}


def get_pareto(limit: int = 40) -> dict[str, Any]:
    """Quality (LMArena Elo) × adoption (HF downloads) non-dominated frontier.
    Both axes are REAL public signals. Price / tokens-per-sec are ROADMAP (no
    measured serving feed) — we do NOT fabricate them. Λ = Conjecture 1."""
    lb = get_leaderboard(100)
    hub = get_hub(100)
    dl_by_id = {}
    for m in hub.get("models", []):
        mid = (m.get("id") or "").lower()
        if mid and m.get("downloads") is not None:
            dl_by_id[mid] = m["downloads"]
            dl_by_id[mid.split("/")[-1]] = m["downloads"]  # bare name alias

    pts = []
    for row in lb.get("leaderboard", []):
        name = (row.get("model") or "").lower()
        downloads = dl_by_id.get(name) or dl_by_id.get(name.split("/")[-1])
        if downloads is None:
            continue
        pts.append({"model": row["model"], "elo": row["elo"], "downloads": downloads,
                    "organization": row.get("organization"), "license": row.get("license")})

    # Non-dominated set: no other point has BOTH higher elo AND higher downloads.
    frontier = []
    for p in pts:
        dominated = any(q is not p and q["elo"] >= p["elo"] and q["downloads"] >= p["downloads"]
                        and (q["elo"] > p["elo"] or q["downloads"] > p["downloads"]) for q in pts)
        if not dominated:
            frontier.append(p)
    frontier.sort(key=lambda r: r["elo"], reverse=True)

    matched = bool(pts)
    return {
        "points": pts, "frontier": frontier, "matched_count": len(pts),
        "axes": {"x": "downloads (HF Hub, live adoption)", "y": "Elo (LMArena, human preference)"},
        "roadmap_axes": ["price ($/M tokens)", "throughput (tokens/sec)", "time-to-first-token"],
        "live": bool(lb.get("live") and hub.get("live")),
        "leaderboard_freshness": lb.get("freshness"), "hub_freshness": hub.get("freshness"),
        "cited": CITED["pareto"],
        "honesty": ("Quality=LMArena Elo, adoption=HF downloads (both real public signals). "
                    "Price/latency axes are ROADMAP — no measured serving feed, not fabricated. "
                    "Elo is an advisory quality input to tier routing (Λ = Conjecture 1)."
                    if matched else
                    "No model names matched between the LMArena leaderboard and HF Hub downloads "
                    "on this fetch (proprietary frontier models are often absent from the Hub); "
                    "frontier empty rather than fabricated."),
        "doctrine": DOCTRINE,
    }


def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    """ADDITIVE. Front-moves its routes ahead of the Node proxy + SPA catch-all."""
    base = f"/api/{ns}/v1/models"
    _n_before = len(app.router.routes)

    @app.get(base + "/leaderboard", include_in_schema=False)
    @app.get("/v1/models/leaderboard", include_in_schema=False)
    async def _models_leaderboard(limit: int = 40):
        return JSONResponse(get_leaderboard(limit))

    @app.get(base + "/hub", include_in_schema=False)
    @app.get("/v1/models/hub", include_in_schema=False)
    async def _models_hub(limit: int = 40):
        return JSONResponse(get_hub(limit))

    @app.get(base + "/pareto", include_in_schema=False)
    @app.get("/v1/models/pareto", include_in_schema=False)
    async def _models_pareto(limit: int = 40):
        return JSONResponse(get_pareto(limit))

    @app.get(base + "/info", include_in_schema=False)
    @app.get("/v1/models/info", include_in_schema=False)
    async def _models_info():
        return JSONResponse({"module": "a11oy_model_intel", "base": base,
                             "endpoints": ["/leaderboard", "/hub", "/pareto", "/info"],
                             "cited": CITED, "locked": LOCKED, "doctrine": DOCTRINE,
                             "honesty": "Live external model intel; advisory quality signal, "
                                        "never a proof. SAMPLE/ROADMAP labelled where not live."})

    # Front-move new routes so /v1/models/* resolve locally, not via the Node proxy.
    _new = app.router.routes[_n_before:]
    del app.router.routes[_n_before:]
    app.router.routes[0:0] = _new

    return {"module": "a11oy_model_intel", "mounted": base,
            "routes": len(_new), "doctrine": DOCTRINE}
