# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1. Trust ceiling 0.97 is policy.
"""szl_hf_scout.py — scrape-shaped honesty over public Hub cards.

Everyone else scrapes Hugging Face to find the hottest model.
This module scrapes the same public JSON to produce a hash-linked
catalog of what the Hub does *not* prove.

- HTTP 200 / likes / downloads / Space "Running" are SNAPSHOT, not LIVE.
- library_name=kernels on the Hub is not compiled-kernel v1.
- Owner-run evals stay REPORTED.
- research-only / failed qualification cannot be promoted.
- Unverified or non-open licenses are FORBIDDEN_REUSE.
- No weights are downloaded. No trust_remote_code. No get_kernel load.

Stdlib only. Additive register(); never replace existing routes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

TRUST_CEILING = 0.97
SCHEMA = "szl.hf_scout/v1"
CONJECTURE_1 = "Λ uniqueness remains Conjecture 1 — advisory, never a theorem."

_OPEN_LICENSES = (
    "apache-2.0",
    "mit",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "unlicense",
    "cc0-1.0",
)

_FORBIDDEN_LICENSE_HINTS = (
    "llama2",
    "llama-3",
    "research-only",
    "non-commercial",
    "cc-by-nc",
    "openrail",
    "responsible-ai",
    "unknown",
    "",
)

_KERNEL_IDS = (
    "SZLHOLDINGS/szl-maskmod",
    "SZLHOLDINGS/szl-block-kv",
    "SZLHOLDINGS/szl-receipt-attn",
    "SZLHOLDINGS/YARQA-ATTN",
)

_ADJACENT = (
    {"id": "agent-receipts/obsigna", "license": "apache-2.0", "relation": "named-not-adopted"},
    {"id": "VeritasActa", "license": "apache-2.0", "relation": "named-not-adopted"},
    {"id": "linux-foundation/TRACE", "license": "unknown", "relation": "named-not-adopted"},
    {"id": "unpingable/receipt_kernel", "license": "apache-2.0", "relation": "named-not-adopted"},
    {"id": "caiqizh/xconf", "license": "unknown", "relation": "named-not-adopted", "arxiv": "2609.17708"},
)


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def license_kind(raw: Any) -> dict[str, Any]:
    token = _norm(raw).replace("license:", "")
    if token in _OPEN_LICENSES:
        return {
            "license": token,
            "reuse": "OPEN_SOURCE_CARD",
            "promote": False,
            "reason": "card license is open — reuse still requires source review, not a Hub badge",
        }
    return {
        "license": token or "unknown",
        "reuse": "FORBIDDEN_REUSE",
        "promote": False,
        "reason": "unverified, missing, research-only, or non-commercial license cannot be leveraged",
    }


def classify_hub_row(row: Mapping[str, Any]) -> dict[str, Any]:
    rid = str(row.get("id") or row.get("modelId") or "")
    downloads = row.get("downloads")
    likes = row.get("likes")
    lib = str(row.get("library_name") or "")
    tags = [str(t).lower() for t in (row.get("tags") or [])]
    license_tag = next((t.split(":", 1)[-1] for t in tags if t.startswith("license:")), row.get("license"))
    lic = license_kind(license_tag)
    running = bool(row.get("runtime") == "RUNNING" or row.get("stage") == "RUNNING")

    kind = "UNKNOWN"
    if lib == "kernels" or rid in _KERNEL_IDS:
        kind = "KERNEL_CARD"
    elif row.get("pipeline_tag") == "text-generation" or lib in {"transformers", "peft", "llama.cpp"}:
        kind = "WEIGHTS_CARD"
    elif "dataset" in tags or row.get("kind") == "dataset":
        kind = "DATASET_CARD"
    elif row.get("sdk") in {"docker", "gradio", "static"} or row.get("kind") == "space":
        kind = "SPACE_CARD"

    reasons = [
        "HTTP 200 / Hub list presence is SNAPSHOT, not LIVE",
        "likes and downloads are popularity, not proof",
    ]
    if kind == "KERNEL_CARD":
        reasons.append("library_name=kernels is not a Git branch named v1 and not a native ABI load")
    if "research-only" in tags or "proposal-only" in tags:
        reasons.append("card tags forbid promotion")
    if running:
        reasons.append("Space Running is reachability, not product LIVE")

    return {
        "id": rid,
        "kind": kind,
        "license": lic,
        "downloads": downloads if isinstance(downloads, int) else None,
        "likes": likes if isinstance(likes, int) else None,
        "library_name": lib or None,
        "space_running": running,
        "live": False,
        "promote": False,
        "agi_claim": False,
        "honesty": "SNAPSHOT",
        "reasons": reasons,
        "lambda": "Conjecture 1",
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
    }


def hash_catalog(rows: Iterable[Mapping[str, Any]], *, prior: str | None = None) -> dict[str, Any]:
    classified = [classify_hub_row(r) for r in rows]
    body = {
        "schema": SCHEMA,
        "prior": prior,
        "count": len(classified),
        "live": False,
        "signed": False,
        "agi_claim": False,
        "entries": classified,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha3_256(canonical).hexdigest()
    return {
        **body,
        "hash": f"sha3-256:{digest}",
        "honesty": "UNSIGNED-LOCAL",
        "note": "hash-linked Hub scout is not SIGNED and not a weight download",
    }


def refuse_kernel_promotion(hub_id: str, *, git_has_v1: bool, native_load: bool) -> dict[str, Any]:
    return {
        "id": hub_id,
        "decision": "BLOCKED" if not (git_has_v1 and native_load) else "HOLD",
        "mint_v1": False,
        "git_has_v1": bool(git_has_v1),
        "native_load": bool(native_load),
        "reason": (
            "Hub kernel card / downloads cannot mint compiled-kernel v1"
            if not git_has_v1
            else "v1 ref without native ABI load is still HOLD"
        ),
        "agi_claim": False,
        "leverage": "cite the Hub contract pattern; do not copy weights or trust_remote_code",
    }


def likes_are_not_live(likes: Any, downloads: Any) -> dict[str, Any]:
    return {
        "likes": likes if isinstance(likes, int) and likes >= 0 else None,
        "downloads": downloads if isinstance(downloads, int) and downloads >= 0 else None,
        "live": False,
        "honesty": "SNAPSHOT",
        "reason": "popularity is not LIVE quality",
    }


def conformal_abstain(*, calibration_n: int = 0) -> dict[str, Any]:
    return {
        "abstain": True,
        "coverage_claim": False,
        "calibration_n": int(calibration_n),
        "reason": "no calibration set — conformal coverage cannot be claimed from a Hub scrape",
    }


def adjacent_protocols() -> list[dict[str, Any]]:
    return [dict(x) for x in _ADJACENT]


def scout_status() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "agi_claim": False,
        "lambda": "Conjecture 1",
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
        "estate_gate": "HOLD",
        "weight_download": False,
        "adjacent": adjacent_protocols(),
        "conformal": conformal_abstain(),
        "note": "The undreamed capability is a refusal catalog over public Hub cards.",
    }


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    report = {"ok": False, "registered": []}
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        return report
    base = f"/api/{ns}/v1/hf-scout"

    @app.get(f"{base}/status")
    async def _status():
        return JSONResponse(scout_status())

    @app.post(f"{base}/classify")
    async def _classify(payload: dict[str, Any] | None = None):
        return JSONResponse(classify_hub_row(payload or {}))

    @app.post(f"{base}/catalog")
    async def _catalog(payload: dict[str, Any] | None = None):
        data = payload or {}
        rows = list(data.get("rows") or [])
        return JSONResponse(hash_catalog(rows, prior=data.get("prior")))

    report["ok"] = True
    report["registered"] = [f"{base}/status", f"{base}/classify", f"{base}/catalog"]
    return report


if __name__ == "__main__":
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, ok))
        print(("PASS" if ok else "FAIL"), name)

    k = classify_hub_row({"id": "SZLHOLDINGS/szl-maskmod", "library_name": "kernels", "downloads": 36, "likes": 0, "tags": ["license:apache-2.0"]})
    check("kernel_card_not_live", k["kind"] == "KERNEL_CARD" and k["live"] is False)
    w = classify_hub_row({"id": "SZLHOLDINGS/SZL-Khipu-1.5B", "pipeline_tag": "text-generation", "library_name": "transformers", "downloads": 2982, "tags": ["license:apache-2.0"]})
    check("weights_not_promoted", w["kind"] == "WEIGHTS_CARD" and w["promote"] is False)
    check("nc_forbidden", license_kind("cc-by-nc-4.0")["reuse"] == "FORBIDDEN_REUSE")
    check("apache_open_card", license_kind("apache-2.0")["reuse"] == "OPEN_SOURCE_CARD")
    r = refuse_kernel_promotion("SZLHOLDINGS/szl-maskmod", git_has_v1=False, native_load=False)
    check("refuse_empty_v1", r["mint_v1"] is False and r["decision"] == "BLOCKED")
    cat = hash_catalog([{"id": "SZLHOLDINGS/a11oy", "sdk": "docker", "kind": "space"}])
    check("catalog_unsigned", cat["signed"] is False and cat["hash"].startswith("sha3-256:"))
    check("status_not_agi", scout_status()["agi_claim"] is False)
    failed = [n for n, ok in checks if not ok]
    print({"ok": not failed, "checks": len(checks), "failed": failed})
    raise SystemExit(1 if failed else 0)
