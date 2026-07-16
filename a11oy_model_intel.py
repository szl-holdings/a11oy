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

import json
import re
import threading
import time
from pathlib import Path
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
_HF_ORG = "SZLHOLDINGS"
_HF_ORG_REPOSITORY_RE = re.compile(r"^SZLHOLDINGS/[A-Za-z0-9._-]+$")
_HF_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_FRONTIER_REGISTRY = (
    Path(__file__).resolve().parent
    / "model_release"
    / "frontier-qualification"
    / "frontier-adoption.json"
)

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


def _load_frontier_registry() -> dict[str, Any]:
    value = json.loads(_FRONTIER_REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("frontier adoption registry is not a JSON object")
    if value.get("schema_version") != "szl.frontier-adoption.v1":
        raise ValueError("frontier adoption registry schema is unsupported")
    if value.get("status") != "GOVERNED_PLAN_NOT_LOCAL_QUALIFICATION":
        raise ValueError("frontier adoption registry honesty state changed")
    policy = value.get("evidence_policy", {})
    expected_policy = {
        "local_measurements_present": False,
        "download_performed_by_this_contract": False,
        "promotion_authority": False,
        "unknown_repository_policy": "DENY",
        "zero_download_policy": "ZERO_DOWNLOADS_ALONE_NEVER_AUTHORIZES_DELETE_OR_ARCHIVE",
    }
    if not isinstance(policy, dict):
        raise ValueError("frontier adoption registry evidence policy is missing")
    for field, expected in expected_policy.items():
        if policy.get(field) != expected:
            raise ValueError(f"frontier adoption registry policy mismatch: {field}")
    mutations = value.get("external_mutations")
    if not isinstance(mutations, dict) or not mutations:
        raise ValueError("frontier adoption registry mutation ledger is missing")
    if any(item is not False for item in mutations.values()):
        raise ValueError("frontier adoption registry reports an external mutation")
    brain = value.get("brain_model_truth")
    if not isinstance(brain, dict):
        raise ValueError("frontier adoption registry Brain truth is missing")
    if brain.get("raw_nodes_observed") != 9464:
        raise ValueError("frontier adoption registry Brain node count changed")
    if brain.get("raw_nodes_admitted_to_gradients") != 0:
        raise ValueError("frontier adoption registry reports unadmitted gradient rows")
    github_estate = value.get("github_estate_strategy")
    if not isinstance(github_estate, dict):
        raise ValueError("frontier adoption registry GitHub estate strategy is missing")
    if github_estate.get("source_reported_repository_count") != 54:
        raise ValueError("frontier adoption registry GitHub source count changed")
    if github_estate.get("inventory_complete") is not False:
        raise ValueError("frontier adoption registry overclaims a complete GitHub inventory")
    if github_estate.get("public_github_repositories_observed") != 50:
        raise ValueError("frontier adoption registry public GitHub readback count changed")
    if github_estate.get("public_archived_observed") != 9:
        raise ValueError("frontier adoption registry public GitHub archive count changed")
    if github_estate.get("reconciliation_state") != (
        "SOURCE_REPORT_54_PUBLIC_READBACK_50_ATTACHMENT_TRUNCATED_REVIEW_REQUIRED"
    ):
        raise ValueError("frontier adoption registry GitHub reconciliation state changed")
    if github_estate.get("code_to_weight_policy") != (
        "CODE_REPOSITORIES_ARE_SERVICES_LIBRARIES_OR_EVIDENCE_NOT_MODEL_WEIGHTS"
    ):
        raise ValueError("frontier adoption registry code-to-weight boundary changed")
    if github_estate.get("unclassified_repository_policy") != (
        "DISCOVER_CLASSIFY_FAIL_CLOSED_NO_ARCHIVE"
    ):
        raise ValueError("frontier adoption registry unclassified repository policy changed")
    layers = github_estate.get("layers")
    if not isinstance(layers, list) or len(layers) < 8:
        raise ValueError("frontier adoption registry GitHub estate layer map is incomplete")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 9:
        raise ValueError("frontier adoption registry candidate inventory is incomplete")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("frontier adoption registry candidate record is malformed")
        required_candidate = {
            "id", "decision", "upstream", "runtime", "allowed_operations",
            "prohibited_operations", "required_evidence_by_operation",
        }
        if not required_candidate.issubset(candidate):
            raise ValueError("frontier adoption registry candidate record is incomplete")
        upstream = candidate.get("upstream")
        if not isinstance(upstream, dict) or not {
            "repository_id", "revision", "artifact_inventory"
        }.issubset(upstream):
            raise ValueError("frontier adoption registry candidate upstream record is incomplete")
    estate = value.get("hf_estate")
    repositories = estate.get("repositories") if isinstance(estate, dict) else None
    if not isinstance(repositories, list) or len(repositories) < 15:
        raise ValueError("frontier adoption registry Hugging Face estate is incomplete")
    repository_ids = []
    for item in repositories:
        if not isinstance(item, dict):
            raise ValueError("frontier adoption registry estate record is malformed")
        required = {
            "repository_id", "observed_revision", "artifact_class", "weight_bearing",
            "strategy", "canonical_family", "delete_authorized",
        }
        if not required.issubset(item):
            raise ValueError("frontier adoption registry estate record is incomplete")
        if item["delete_authorized"] is not False:
            raise ValueError("frontier adoption registry estate record authorizes deletion")
        repository_ids.append(item["repository_id"])
    if len(repository_ids) != len(set(repository_ids)):
        raise ValueError("frontier adoption registry estate contains duplicate repositories")
    return value


def get_frontier_adoption() -> dict[str, Any]:
    """Return the checked-in adoption contract without upgrading its honesty state."""
    try:
        registry = _load_frontier_registry()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {
            "state": "UNAVAILABLE",
            "reason": f"{type(exc).__name__}: {str(exc)[:180]}",
            "qualificationAuthority": False,
            "promotionAuthority": False,
            "deleteAuthority": False,
            "externalMutationPerformed": False,
            "doctrine": DOCTRINE,
        }
    policy = registry["evidence_policy"]
    mutations = registry["external_mutations"]
    return {
        "state": registry["status"],
        "registry": registry,
        "qualificationAuthority": bool(policy["local_measurements_present"]),
        "promotionAuthority": bool(policy["promotion_authority"]),
        "deleteAuthority": False,
        "externalMutationPerformed": any(bool(value) for value in mutations.values()),
        "doctrine": DOCTRINE,
    }


def _parse_hf_org_models(items: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in items if isinstance(items, list) else []:
        if not isinstance(model, dict):
            continue
        repository_id = model.get("id")
        if not isinstance(repository_id, str) or not _HF_ORG_REPOSITORY_RE.fullmatch(repository_id):
            continue
        revision = model.get("sha")
        if not isinstance(revision, str) or not _HF_REVISION_RE.fullmatch(revision):
            revision = None
        siblings = model.get("siblings")
        filenames = [
            str(item.get("rfilename", ""))
            for item in siblings or []
            if isinstance(item, dict)
        ]
        lowered_filenames = [name.lower() for name in filenames]
        basenames = [name.rsplit("/", 1)[-1] for name in lowered_filenames]
        weight_bearing = any(
            name.endswith(".safetensors")
            or name.endswith(".gguf")
            or name.endswith(".onnx")
            or name.endswith(".pt")
            or name.endswith(".pth")
            or name.endswith(".ckpt")
            or name.endswith(".npz")
            or name.endswith(".h5")
            or name.endswith(".msgpack")
            or name in {"pytorch_model.bin", "adapter_model.bin", "tf_model.h5", "flax_model.msgpack"}
            or bool(re.fullmatch(r"pytorch_model-\d+-of-\d+\.bin", name))
            for name in basenames
        )
        rows.append({
            "repository_id": repository_id,
            "revision": revision,
            "downloads": model.get("downloads"),
            "likes": model.get("likes"),
            "last_modified": model.get("lastModified"),
            "pipeline_tag": model.get("pipeline_tag"),
            "library_name": model.get("library_name"),
            "weight_bearing_from_filenames": weight_bearing,
            "file_count": len(filenames),
        })
    return rows


def _download_sort_value(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(parsed, 0)


def get_szl_estate() -> dict[str, Any]:
    """Merge live no-key Hub metadata with the pinned estate classification.

    Live download counts are observations, never deletion or promotion authority.
    Unknown or revision-drifted repositories remain visible and fail closed.
    """
    try:
        registry = _load_frontier_registry()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {
            "state": "UNAVAILABLE",
            "reason": f"{type(exc).__name__}: {str(exc)[:180]}",
            "models": [],
            "deleteAuthority": False,
            "externalMutationPerformed": False,
            "doctrine": DOCTRINE,
        }

    static_rows = registry["hf_estate"]["repositories"]
    by_id = {item["repository_id"]: item for item in static_rows}
    feed = _cached_fetch(
        "hf_szlholdings_estate",
        _HF_MODELS,
        ttl=900,
        parser=_parse_hf_org_models,
        params={"author": _HF_ORG, "limit": 100, "full": "true"},
    )
    live_rows = feed.get("value") or []
    live_by_id = {item["repository_id"]: item for item in live_rows if item.get("repository_id")}
    merged: list[dict[str, Any]] = []

    for repository_id in sorted(set(by_id) | set(live_by_id)):
        classification = by_id.get(repository_id)
        live = live_by_id.get(repository_id)
        if classification is None:
            merged.append({
                **(live or {"repository_id": repository_id}),
                "live_present": live is not None,
                "classification_state": "UNCLASSIFIED_FAIL_CLOSED",
                "strategy": "REVIEW_REQUIRED",
                "canonical_family": None,
                "delete_authorized": False,
            })
            continue
        revision_state = "NOT_OBSERVED_LIVE"
        if live is not None:
            revision_state = (
                "PIN_MATCH"
                if live.get("revision") == classification["observed_revision"]
                else "REVISION_DRIFT_REVIEW_REQUIRED"
            )
        merged.append({
            **classification,
            **(live or {}),
            "repository_id": repository_id,
            "live_present": live is not None,
            "classification_state": revision_state,
            "delete_authorized": False,
        })

    freshness = feed.get("freshness") or {}
    freshness_status = freshness.get("status")
    if not live_rows:
        state = "STATIC_CLASSIFICATION_LIVE_FEED_UNAVAILABLE"
    elif freshness_status == "live":
        state = "LIVE"
    elif freshness_status == "cached":
        state = "CACHED"
    elif freshness_status == "stale":
        state = "STALE_LAST_GOOD"
    else:
        state = "LIVE_DATA_FRESHNESS_UNKNOWN"

    return {
        "state": state,
        "organization": _HF_ORG,
        "models": sorted(
            merged,
            key=lambda item: _download_sort_value(item.get("downloads")),
            reverse=True,
        ),
        "summary": {
            "classified_repositories": len(by_id),
            "live_repositories": len(live_rows),
            "weight_bearing_live": sum(bool(item.get("weight_bearing_from_filenames")) for item in live_rows),
            "unclassified_live": sum(item.get("classification_state") == "UNCLASSIFIED_FAIL_CLOSED" for item in merged),
            "revision_drift": sum(item.get("classification_state") == "REVISION_DRIFT_REVIEW_REQUIRED" for item in merged),
        },
        "freshness": freshness,
        "downloadsAreAdoptionSignalNotQuality": True,
        "zeroDownloadsAuthorizeDeletion": False,
        "qualificationAuthority": False,
        "promotionAuthority": False,
        "deleteAuthority": False,
        "externalMutationPerformed": False,
        "doctrine": DOCTRINE,
    }


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
    def _models_leaderboard(limit: int = 40):
        return JSONResponse(get_leaderboard(limit))

    @app.get(base + "/hub", include_in_schema=False)
    @app.get("/v1/models/hub", include_in_schema=False)
    def _models_hub(limit: int = 40):
        return JSONResponse(get_hub(limit))

    @app.get(base + "/pareto", include_in_schema=False)
    @app.get("/v1/models/pareto", include_in_schema=False)
    def _models_pareto(limit: int = 40):
        return JSONResponse(get_pareto(limit))

    @app.get(base + "/frontier-adoption", include_in_schema=False)
    @app.get("/v1/models/frontier-adoption", include_in_schema=False)
    async def _models_frontier_adoption():
        payload = get_frontier_adoption()
        return JSONResponse(payload, status_code=200 if payload["state"] != "UNAVAILABLE" else 503)

    @app.get(base + "/estate", include_in_schema=False)
    @app.get("/v1/models/estate", include_in_schema=False)
    def _models_estate():
        payload = get_szl_estate()
        return JSONResponse(payload, status_code=200 if payload["state"] != "UNAVAILABLE" else 503)

    @app.get(base + "/info", include_in_schema=False)
    @app.get("/v1/models/info", include_in_schema=False)
    async def _models_info():
        return JSONResponse({"module": "a11oy_model_intel", "base": base,
                             "endpoints": ["/leaderboard", "/hub", "/pareto", "/frontier-adoption", "/estate", "/info"],
                             "cited": CITED, "locked": LOCKED, "doctrine": DOCTRINE,
                             "honesty": "Live external model intel; advisory quality signal, "
                                        "never a proof. SAMPLE/ROADMAP labelled where not live."})

    # Front-move new routes so /v1/models/* resolve locally, not via the Node proxy.
    _new = app.router.routes[_n_before:]
    del app.router.routes[_n_before:]
    app.router.routes[0:0] = _new

    return {"module": "a11oy_model_intel", "mounted": base,
            "routes": len(_new), "doctrine": DOCTRINE}
