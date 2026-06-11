"""szl_conjecture_factory.py

Read-only loader that surfaces the SZL Conjecture Factory's output for the
a11oy /console and killinchu /elite consoles.

It reads the conjecture-disclosure records the factory appends to the szl-lake
DSSE Khipu ledger (NDJSON), and exposes them with an HONEST status convention
("live" / "cached" / "unreachable") identical to the other shared console
modules.

Honesty doctrine (do NOT weaken):
  * A factory-generated problem is a CONJECTURE, never a theorem. It stays OPEN
    until a solution is independently verified.
  * "novelty" is an advisory screen, not a proof of originality.
  * "difficulty"/"grade" come from a bounded solver run: OPEN means
    searched-to-budget (NOT proven true); VERIFIED-FINITE certifies only the
    finite enumerated domain; REFUTED carries a concrete witness.
  * The cosign/Rekor signature attests the timestamp + content, NOT the truth
    of the conjecture.
  * An unreachable source is reported as unreachable; it never confirms novelty
    and we never fabricate a value.

Stdlib only (urllib/json) so it drops into the console containers with no extra
dependency, mirroring szl_bounties.py / szl_evidence_research.py.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# --- status labels (shared honest convention) -------------------------------
STATUS_LIVE = "live"
STATUS_CACHED = "cached"
STATUS_UNREACHABLE = "unreachable"

# The factory anchors each disclosure under this receipt kind.
CONJECTURE_KIND = "conjecture-disclosure-anchor"
CONJECTURE_MILESTONE_KIND = "conjecture-disclosure"

# Sources, in priority order. Overridable by env for the box/HF containers.
# The factory anchors its disclosures into the szl-lake DSSE Khipu ledger.
# NOTE: the two surfaces use DIFFERENT path prefixes for the same file --
# HF dataset has no `data/` prefix, GitHub raw does. Probed live.
_DEFAULT_SOURCES = [
    os.environ.get(
        "SZL_LAKE_NDJSON_HF",
        "https://huggingface.co/datasets/szlholdings/szl-lake/resolve/main/khipu/lutar_lean_receipts.ndjson",
    ),
    os.environ.get(
        "SZL_LAKE_NDJSON_GH",
        "https://raw.githubusercontent.com/szl-holdings/szl-lake/main/data/khipu/lutar_lean_receipts.ndjson",
    ),
]

_CACHE_PATH = os.environ.get(
    "SZL_CONJECTURE_CACHE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".conjecture_factory_cache.ndjson"),
)

_HTTP_TIMEOUT = float(os.environ.get("SZL_CONJECTURE_HTTP_TIMEOUT", "6"))

# Verdict tokens we recognise from the factory's own honesty prose when the
# record does not carry discrete fields. We only read what the factory wrote;
# we never invent a verdict.
_NOVELTY_TOKENS = {"novel-candidate", "known-restatement", "duplicate", "inconclusive"}
_DIFFICULTY_TOKENS = {"open-resistant", "hard", "moderate", "easy", "verified-finite", "refuted"}
_GRADE_TOKENS = {"OPEN", "VERIFIED-FINITE", "REFUTED", "RETRACTED"}
_RELEASE_STAGES = {"teaser", "statement", "solution"}


def _first_match(text: Optional[str], allowed: set, lower: bool = True) -> Optional[str]:
    """Return the first single-quoted token in *text* that is in *allowed*."""
    if not text:
        return None
    for tok in re.findall(r"'([^']+)'", text):
        probe = tok.lower() if lower else tok
        bucket = {a.lower() for a in allowed} if lower else allowed
        if probe in bucket:
            return tok
    return None


def _fetch(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "szl-conjecture-factory/1.0"})
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:  # nosec - read-only public ledger
            if getattr(resp, "status", 200) != 200:
                return None
            return resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None


def _read_cache() -> Optional[str]:
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as fh:
            data = fh.read()
        return data if data.strip() else None
    except OSError:
        return None


def _write_cache(raw: str) -> None:
    try:
        tmp = _CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(raw)
        os.replace(tmp, _CACHE_PATH)
    except OSError:
        pass


def _parse_ndjson(raw: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _is_conjecture(rec: Dict[str, Any]) -> bool:
    return (
        rec.get("kind") == CONJECTURE_KIND
        or rec.get("milestone_kind") == CONJECTURE_MILESTONE_KIND
    )


def _normalize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Map one ledger record to a console-friendly, honesty-preserving item.

    Prefers discrete fields if the factory writes them; otherwise reads the
    factory's own honesty prose. Never fabricates a verdict.
    """
    honesty = rec.get("honesty") or {}
    signing = rec.get("signing") or {}
    source_run = rec.get("source_run") or {}

    novelty = (
        rec.get("novelty_verdict")
        or rec.get("novelty")
        or _first_match(honesty.get("novelty"), _NOVELTY_TOKENS)
    )
    difficulty = (
        rec.get("difficulty_grade")
        or rec.get("difficulty")
        or _first_match(honesty.get("difficulty"), _DIFFICULTY_TOKENS)
    )
    grade = (
        rec.get("grade")
        or rec.get("milestone_status")
        or _first_match(honesty.get("difficulty"), _GRADE_TOKENS, lower=False)
    )
    release_stage = (
        rec.get("release_stage")
        or rec.get("stage")
        or _first_match(honesty.get("status"), _RELEASE_STAGES)
        or "statement"
    )

    # Honesty guard: a conjecture is NEVER a theorem and is shown OPEN until
    # independently verified. Only the factory's own VERIFIED-FINITE / REFUTED
    # grades may change that; an absent grade defaults to OPEN, not "proved".
    if not grade:
        grade = "OPEN"

    return {
        "id": rec.get("receipt_id") or rec.get("milestone_id") or rec.get("chain_index"),
        "title": rec.get("milestone_title") or rec.get("title") or "(untitled conjecture)",
        "statement": rec.get("statement") or honesty.get("conjecture") or "",
        "novelty": novelty,
        "difficulty": difficulty,
        "grade": grade,
        "release_stage": release_stage,
        "is_open": grade not in ("VERIFIED-FINITE", "REFUTED"),
        "organ": rec.get("organ"),
        "kernel_commit_short": rec.get("kernel_commit_short") or (rec.get("kernel_commit") or "")[:12] or None,
        "timestamp": rec.get("timestamp"),
        "chain_index": rec.get("chain_index"),
        "prev_hash": rec.get("prev_hash"),
        "honesty": {
            "status": honesty.get("status"),
            "conjecture": honesty.get("conjecture"),
            "novelty": honesty.get("novelty"),
            "difficulty": honesty.get("difficulty"),
            "signing": honesty.get("signing"),
            "doctrine": honesty.get("doctrine") or rec.get("doctrine"),
        },
        "receipt": {
            "receipt_id": rec.get("receipt_id"),
            "chain_index": rec.get("chain_index"),
            "predicate_type": signing.get("predicate_type"),
            "signing_mode": signing.get("mode"),
            "rekor_log_index": signing.get("rekor_log_index"),
            "rekor_integrated_time": signing.get("rekor_integrated_time"),
            "verify_cmd": signing.get("verify_cmd"),
            "fulcio_identity": signing.get("fulcio_identity"),
            "source_run_url": source_run.get("url"),
            "source_run_workflow": source_run.get("workflow"),
        },
    }


def load_conjectures(force_refresh: bool = True) -> Dict[str, Any]:
    """Load factory conjectures with an honest live/cached/unreachable status.

    Returns a dict::

        {
          "status": "live" | "cached" | "unreachable",
          "source": <url-or-cache-or-None>,
          "fetched_at": <iso8601 utc>,
          "count": <int>,
          "items": [ ...normalized conjecture items... ],
          "doctrine_banner": <str>,   # honesty banner, always present
        }
    """
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    raw: Optional[str] = None
    source: Optional[str] = None
    status = STATUS_UNREACHABLE

    if force_refresh:
        for url in _DEFAULT_SOURCES:
            data = _fetch(url)
            if data is not None:
                raw, source, status = data, url, STATUS_LIVE
                _write_cache(data)
                break

    if raw is None:
        cached = _read_cache()
        if cached is not None:
            raw, source, status = cached, _CACHE_PATH, STATUS_CACHED

    items: List[Dict[str, Any]] = []
    if raw is not None:
        for rec in _parse_ndjson(raw):
            if _is_conjecture(rec):
                items.append(_normalize(rec))

    # Stable, newest-first ordering by chain_index when available.
    items.sort(key=lambda it: (it.get("chain_index") or 0), reverse=True)

    return {
        "status": status,
        "source": source,
        "fetched_at": fetched_at,
        "count": len(items),
        "items": items,
        "doctrine_banner": (
            "Factory output is a set of OPEN conjectures \u2014 generated, not proven. "
            "Each stays OPEN until a solution is independently verified; novelty is an "
            "advisory screen; signatures attest timestamp + content, not truth. "
            "Conjecture 1 (unconditional \u039b uniqueness) is and remains OPEN."
        ),
    }


def load_conjecture(receipt_id: str, force_refresh: bool = True) -> Optional[Dict[str, Any]]:
    """Return a single normalized conjecture by receipt_id (or None)."""
    bundle = load_conjectures(force_refresh=force_refresh)
    for it in bundle["items"]:
        if it.get("id") == receipt_id or it.get("receipt", {}).get("receipt_id") == receipt_id:
            return {**it, "_envelope_status": bundle["status"], "_fetched_at": bundle["fetched_at"]}
    return None


# --- registration (FastAPI, mirrors szl_bounties.register) -------------------
def register(app, ns: str = "a11oy") -> None:
    """Attach the Conjecture Factory endpoints for namespace *ns*.

    Mounts (read-only)::

        GET /api/{ns}/v1/conjecture-factory        -> honest bundle
        GET /api/{ns}/v1/conjecture-factory/{rid}  -> single conjecture (404 if absent)

    Mirrors the szl_bounties.register() convention so the deploy is a one-line
    import + register() and the module ships byte-identical to both consoles.
    """
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover - non-FastAPI host
        return

    base = "/api/%s/v1/conjecture-factory" % ns

    @app.get(base)
    async def _conjectures_index():  # noqa: ANN202
        bundle = load_conjectures(force_refresh=True)
        return JSONResponse({
            "layer": "%s conjecture factory" % ns,
            "honest": bundle["doctrine_banner"],
            "doctrine": "v11",
            "status": bundle["status"],
            "source": bundle["source"],
            "count": bundle["count"],
            "conjectures": bundle["items"],
            "checked_at": bundle["fetched_at"],
        })

    @app.get(base + "/{rid}")
    async def _conjecture_one(rid: str):  # noqa: ANN202
        item = load_conjecture(rid, force_refresh=True)
        if item is None:
            return JSONResponse(
                {"error": "unknown conjecture", "receipt_id": rid},
                status_code=404,
            )
        return JSONResponse({
            "layer": "%s conjecture" % ns,
            "doctrine": "v11",
            "conjecture": item,
        })


# --- offline self-test against a local ledger --------------------------------
def _selftest(path: str) -> int:
    """Parse a local NDJSON ledger (no network) and print a summary."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    recs = _parse_ndjson(raw)
    conj = [_normalize(r) for r in recs if _is_conjecture(r)]
    print(f"records={len(recs)} conjectures={len(conj)}")
    for it in conj:
        print(
            f"  - id={it['id'][:16] if it['id'] else None}... "
            f"title={it['title']!r} novelty={it['novelty']} "
            f"difficulty={it['difficulty']} grade={it['grade']} "
            f"stage={it['release_stage']} open={it['is_open']} "
            f"rekor={it['receipt']['rekor_log_index']}"
        )
        # honesty assertions
        assert it["grade"] != "PROVED", "conjecture must never be graded PROVED"
        assert "theorem" not in it["title"].lower() or it["is_open"], "conjecture mislabeled as theorem"
    return 0


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        raise SystemExit(_selftest(target))
    out = load_conjectures()
    print(json.dumps({k: v for k, v in out.items() if k != "items"}, indent=2))
    print(f"items={out['count']}")
