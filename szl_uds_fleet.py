"""UDS Fleet-Trust layer for the a11oy console (uds-tab-patch).

Two honest halves, both additive and self-contained (pure stdlib):

  1. NARRATIVE — the Defense Unicorns / Unicorn Delivery Service (UDS) fleet
     story told with direct attribution and links to the public UDS repos and
     the Air & Space Forces Magazine coverage. Each fleet trust / provenance /
     drift gap is mapped to a REAL, already-shipped a11oy capability (cosign +
     SLSA attestation, offline-verifiable bundle, DSSE receipt chain, drift
     guards). Defense Unicorns / UDS is a separate company and open-source
     project; a11oy references their PUBLIC work and reimplements PATTERNS
     only — no code is copied or re-badged (uds-core / uds-cli / uds-common are
     AGPL-3.0).

  2. LIVE SIGNAL — real public data pulled from the Defense Unicorns / UDS
     GitHub org via the public GitHub REST API (repo metadata, latest
     release/tag, release cadence + recency) plus per-URL reachability. Every
     figure is labelled live | cached | unreachable; a kept-warm on-disk
     last-good cache means a rate-limited upstream degrades to a real cached
     value, never to a fabricated number. Nothing here is SAMPLE.

Exposes /api/{ns}/v1/uds[...]. a11oy-only (no killinchu mirror).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

_UA = "a11oy-uds-fleet/1.0 (+https://a-11-oy.com) public-read-only"
_GH = "https://api.github.com/repos/"

# --- honest attribution (shown verbatim at the top of the tab) ---------------

_ATTRIB = (
    "Defense Unicorns and the Unicorn Delivery Service (UDS) are a separate "
    "company and open-source project. a11oy references their PUBLIC work and "
    "reimplements PATTERNS only — no UDS source is copied or re-badged "
    "(uds-core / uds-cli / uds-common are AGPL-3.0; Zarf and Pepr are "
    "Apache-2.0). Every fleet-trust gap below is mapped to a capability a11oy "
    "has already shipped, with an honest LIVE / CI-GREEN / ROADMAP status. The "
    "live signal feed pulls REAL public data from the Defense Unicorns / UDS "
    "GitHub org via the public GitHub REST API; each figure is labelled "
    "live / cached / unreachable, never fabricated."
)

# --- public UDS / Defense Unicorns repositories (the live signal feed) --------
# Verified to resolve on the public GitHub REST API before shipping.

_UDS_REPOS: List[Dict[str, str]] = [
    {"repo": "defenseunicorns/uds-core",
     "role": "UDS Core — the secure-by-default runtime baseline (Istio, "
             "Keycloak, NeuVector, monitoring) shipped as one signed bundle."},
    {"repo": "defenseunicorns/uds-cli",
     "role": "UDS CLI — bundles, publishes and deploys UDS packages, "
             "including fully air-gapped."},
    {"repo": "zarf-dev/zarf",
     "role": "Zarf — the air-gap package + deploy engine UDS is built on "
             "(donated by Defense Unicorns to the zarf-dev org).",
     "note": "moved from the defenseunicorns org to zarf-dev"},
    {"repo": "defenseunicorns/pepr",
     "role": "Pepr — the Kubernetes admission/mutation engine UDS uses for "
             "policy (the same webhook pattern a11oy's receipt chain rides)."},
    {"repo": "defenseunicorns/uds-common",
     "role": "UDS Common — shared tasks/actions reused across UDS packages."},
]

# --- curated narrative sources (real, resolvable, reachability-probed) --------

_SRC_ARTICLE = {
    "kind": "press", "title": "Air & Space Forces Magazine — \u201cFaster "
    "Software Updates for More Aircraft\u201d (Defense Unicorns / UDS on the F-22)",
    "url": "https://www.airandspaceforces.com/air-force-faster-software-updates-more-aircraft/",
    "note": "independent coverage of UDS enabling continuous, air-gapped "
            "software delivery to fielded aircraft",
}
_SRC_DU = {
    "kind": "vendor", "title": "Defense Unicorns — UDS platform",
    "url": "https://defenseunicorns.com/platform/uds-platform/",
    "note": "official product page (attribution)",
}
_SRC_UDS_DOCS = {
    "kind": "docs", "title": "UDS documentation",
    "url": "https://uds.defenseunicorns.com/",
    "note": "public UDS docs",
}


def _repo_src(repo: str) -> Dict[str, str]:
    return {"kind": "repo", "title": "GitHub: " + repo,
            "url": "https://github.com/" + repo, "note": "public source"}


# --- fleet trust/provenance/drift gaps -> real a11oy capabilities ------------
# capability_status is a11oy's HONEST shipped state (see PROVEN_FORMULAS / the
# Deploy Posture + receipts tabs): LIVE = shipped & verifiable now; CI-GREEN =
# enforced in CI; ROADMAP = stated next step (e.g. SLSA L3).

_GAPS: List[Dict[str, Any]] = [
    {
        "id": "provenance",
        "gap": "Build \u2192 edge provenance",
        "fleet_context":
            "A fleet operator deploying a UDS bundle to a disconnected site "
            "must trust the artifact is EXACTLY what was built upstream \u2014 "
            "no tampering in the supply chain or at the edge.",
        "a11oy_capability":
            "a11oy publishes every organ image cosign-signed with an in-toto "
            "SLSA build-provenance attestation (.att), verifiable with "
            "`cosign verify-attestation` / `gh attestation verify` (Sigstore "
            "keyless: Fulcio cert + Rekor transparency log).",
        "capability_status": "LIVE",
        "status_note": "SLSA Level 1+2 attested today; Level 3 is roadmap.",
        "github": ["zarf-dev/zarf", "defenseunicorns/uds-cli"],
        "sources": [_SRC_ARTICLE, _SRC_DU,
                    _repo_src("zarf-dev/zarf"), _repo_src("defenseunicorns/uds-cli")],
    },
    {
        "id": "airgap-verify",
        "gap": "Air-gapped / offline verification",
        "fleet_context":
            "Edge and air-gapped fleets cannot phone home to a central "
            "registry or transparency log to verify artifacts at deploy time.",
        "a11oy_capability":
            "a11oy ships a cosign-signed Zarf/UDS bundle whose signatures "
            "(.sig) and attestations travel WITH the bundle, so verification "
            "is fully offline \u2014 the verify-it-yourself commands are "
            "documented on the Deploy Posture tab.",
        "capability_status": "LIVE",
        "status_note": "Offline bundle verify proven; same air-gap pattern UDS "
                       "pioneered with Zarf.",
        "github": ["zarf-dev/zarf", "defenseunicorns/uds-core"],
        "sources": [_SRC_UDS_DOCS, _SRC_DU,
                    _repo_src("zarf-dev/zarf"), _repo_src("defenseunicorns/uds-core")],
    },
    {
        "id": "tamper-evidence",
        "gap": "Tamper-evident deploy audit",
        "fleet_context":
            "When a fleet deploys hundreds of packages across many "
            "disconnected sites, there is no append-only, tamper-evident "
            "record of what actually ran, where and when.",
        "a11oy_capability":
            "Every a11oy deploy emits a DSSE receipt (Ed25519) appended to a "
            "hash-linked chain via a Pepr admission webhook; a duplicate "
            "receipt is a hash collision and any payload mutation makes "
            "re-verify reject. Chain durability is proven across cold "
            "restarts (verifiable at /receipts/ and /pubkey).",
        "capability_status": "LIVE",
        "status_note": "Live receipt chain; rides the same Pepr webhook "
                       "pattern UDS uses for policy.",
        "github": ["defenseunicorns/pepr"],
        "sources": [_SRC_DU, _repo_src("defenseunicorns/pepr")],
    },
    {
        "id": "drift",
        "gap": "Fleet configuration & version drift",
        "fleet_context":
            "Across a large fleet, package versions and image digests drift "
            "from the signed baseline; without a continuous integrity scan "
            "that drift stays invisible until something breaks.",
        "a11oy_capability":
            "a11oy runs continuous drift guards \u2014 image-pin guards (reject "
            "a multi-arch index pin in place of the amd64 child), GitHub\u2194HF "
            "module-drift checks, and a server-side integrity scan exposed on "
            "/metrics \u2014 that fail loud when a deployed artifact diverges "
            "from its signed pin.",
        "capability_status": "CI-GREEN",
        "status_note": "Enforced in CI + on-box watchers; alerts on divergence.",
        "github": ["defenseunicorns/uds-common", "defenseunicorns/uds-core"],
        "sources": [_SRC_UDS_DOCS,
                    _repo_src("defenseunicorns/uds-common"),
                    _repo_src("defenseunicorns/uds-core")],
    },
]


# --- resilient cache (in-memory + on-disk last-good, warmed by a timer) -------

_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_TTL = 1800              # 30 min — GitHub repo/release freshness window
_LIVENESS_TTL = 900     # 15 min — source-URL reachability badge freshness
_LIVENESS_TIMEOUT = 8   # 8 s — per-source HEAD/GET probe timeout
_RATELIMIT_COOLDOWN = 900  # 15 min — back off after a GitHub 403/429
_WARM_INTERVAL = int(os.environ.get("SZL_UDS_WARM_INTERVAL", "1500") or "1500")
_DISK = os.environ.get(
    "SZL_UDS_CACHE",
    os.path.join(tempfile.gettempdir(), "szl_uds_fleet_cache.json"),
)

_RATELIMIT_UNTIL = 0.0
_DISK_LOADED = False
_WARM_STARTED = False
_WARM_NS: set = set()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _auth_headers() -> Dict[str, str]:
    tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("SZL_GITHUB_TOKEN")
           or "").strip()
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    return h


def _get(url: str, timeout: int = 12,
         headers: Optional[Dict[str, str]] = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only APIs
        return r.read()


def _disk_load() -> None:
    global _DISK_LOADED
    if _DISK_LOADED:
        return
    _DISK_LOADED = True
    try:
        with open(_DISK, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            with _LOCK:
                for k, v in data.items():
                    if k not in _CACHE and isinstance(v, dict) and "v" in v:
                        _CACHE[k] = v
    except Exception:  # noqa: BLE001 - cache is best-effort
        pass


def _disk_save() -> None:
    try:
        with _LOCK:
            snap = dict(_CACHE)
        tmp = _DISK + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(snap, fh)
        os.replace(tmp, _DISK)
    except Exception:  # noqa: BLE001 - cache is best-effort
        pass


def _store(key: str, val: Dict[str, Any], at: str) -> None:
    with _LOCK:
        _CACHE[key] = {"v": val, "_t": time.time(), "at": at}
    _disk_save()


def _days_since(iso: str) -> Optional[int]:
    if not iso:
        return None
    try:
        t = time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return max(0, int((time.time() - time.mktime(t) + time.timezone) // 86400))
    except Exception:  # noqa: BLE001
        return None


# --- GitHub repo + release signal (honest live/cached/unreachable) -----------

def _gh_meta(repo: str) -> Optional[Dict[str, Any]]:
    raw = _get(_GH + repo, timeout=10, headers=_auth_headers())
    d = json.loads(raw)
    return {
        "repo": repo,
        "url": d.get("html_url") or ("https://github.com/" + repo),
        "description": (d.get("description") or "")[:200],
        "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"),
        "open_issues": d.get("open_issues_count"),
        "license": ((d.get("license") or {}) or {}).get("spdx_id"),
        "pushed_at": (d.get("pushed_at") or "")[:10],
        "archived": bool(d.get("archived")),
    }


def _gh_release(repo: str) -> Dict[str, Any]:
    """Latest release + 90-day cadence from the public releases list.

    Falls back to the latest tag when a repo cuts no GitHub releases. Returns
    a dict that always carries the keys the UI reads, even when empty."""
    out: Dict[str, Any] = {
        "latest_tag": None, "latest_name": None, "published_at": None,
        "release_url": None, "age_days": None, "releases_90d": None,
        "kind": "none",
    }
    try:
        raw = _get(_GH + repo + "/releases?per_page=30", timeout=10,
                   headers=_auth_headers())
        rels = json.loads(raw)
        rels = [r for r in rels if isinstance(r, dict) and not r.get("draft")]
        if rels:
            top = rels[0]
            pub = (top.get("published_at") or top.get("created_at") or "")
            out.update({
                "latest_tag": top.get("tag_name"),
                "latest_name": (top.get("name") or top.get("tag_name")),
                "published_at": pub[:10] if pub else None,
                "release_url": top.get("html_url"),
                "age_days": _days_since(pub),
                "releases_90d": sum(
                    1 for r in rels
                    if (_days_since(r.get("published_at")
                                    or r.get("created_at") or "") or 9999) <= 90),
                "kind": "release",
            })
            return out
    except urllib.error.HTTPError as ex:
        if ex.code in (403, 429):
            raise
    except Exception:  # noqa: BLE001 - fall through to tags
        pass
    # No releases -> latest tag.
    try:
        raw = _get(_GH + repo + "/tags?per_page=1", timeout=10,
                   headers=_auth_headers())
        tags = json.loads(raw)
        if isinstance(tags, list) and tags:
            out.update({"latest_tag": tags[0].get("name"),
                        "latest_name": tags[0].get("name"), "kind": "tag"})
    except Exception:  # noqa: BLE001
        pass
    return out


def _signal(repo: str, role: str = "", note: str = "") -> Dict[str, Any]:
    """One repo's live signal, with cache + last-good degrade. Never invents."""
    global _RATELIMIT_UNTIL
    _disk_load()
    key = "sig:" + repo
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit.get("_t", 0) < _TTL:
        return {**hit["v"], "role": role, "note": note,
                "mode": "cached", "fetched_at": hit["at"]}
    if now < _RATELIMIT_UNTIL:
        # Backing off GitHub — serve last-good if we have it.
        if hit:
            return {**hit["v"], "role": role, "note": note,
                    "mode": "cached", "fetched_at": hit["at"]}
        return {"repo": repo, "url": "https://github.com/" + repo,
                "role": role, "note": note, "mode": "unreachable",
                "error": "GitHub rate-limited; no cached value yet"}
    try:
        meta = _gh_meta(repo)
        rel = _gh_release(repo)
        val = {**(meta or {}), "release": rel}
        at = _now_iso()
        _store(key, val, at)
        return {**val, "role": role, "note": note, "mode": "live",
                "fetched_at": at}
    except urllib.error.HTTPError as ex:  # noqa: PERF203
        if ex.code in (403, 429):
            _RATELIMIT_UNTIL = time.time() + _RATELIMIT_COOLDOWN
        if hit:
            return {**hit["v"], "role": role, "note": note,
                    "mode": "cached", "fetched_at": hit["at"]}
        return {"repo": repo, "url": "https://github.com/" + repo,
                "role": role, "note": note, "mode": "unreachable",
                "error": ("HTTP %d" % ex.code)}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "role": role, "note": note,
                    "mode": "cached", "fetched_at": hit["at"]}
        return {"repo": repo, "url": "https://github.com/" + repo,
                "role": role, "note": note, "mode": "unreachable",
                "error": str(ex)[:120]}


# --- source-URL reachability (honest live/cached/unreachable badge) ----------

def _probe_url(url: str, timeout: int = _LIVENESS_TIMEOUT):
    def _attempt(method: str):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only
                return True, (getattr(r, "status", None) or r.getcode())
        except urllib.error.HTTPError as ex:
            return None, ex.code
        except Exception:  # noqa: BLE001
            return None, None

    ok, status = _attempt("HEAD")
    if ok:
        return True, status
    gok, gstatus = _attempt("GET")
    if gok:
        return True, gstatus
    if gstatus is not None:
        return True, gstatus
    if status is not None:
        return True, status
    return False, None


def _liveness(url: str) -> Dict[str, Any]:
    if not url:
        return {"url": url, "reachable": False, "http_status": None,
                "mode": "unreachable", "checked_at": _now_iso()}
    _disk_load()
    key = "live:" + url
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit.get("_t", 0) < _LIVENESS_TTL:
        return {**hit["v"], "mode": "cached", "checked_at": hit["at"]}
    reachable, status = _probe_url(url)
    if reachable or status is not None:
        val = {"url": url, "reachable": bool(reachable), "http_status": status}
        at = _now_iso()
        _store(key, val, at)
        return {**val, "mode": "live", "checked_at": at}
    if hit:
        return {**hit["v"], "mode": "cached", "checked_at": hit["at"],
                "note": "live reachability check failed; serving last-good badge"}
    return {"url": url, "reachable": False, "http_status": None,
            "mode": "unreachable", "checked_at": _now_iso()}


def _sources_live(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    n = len(sources)
    out: List[Optional[Dict[str, Any]]] = [None] * n
    if n == 0:
        return []

    def _fallback(s: Dict[str, Any]) -> Dict[str, Any]:
        return {"url": s.get("url", ""), "reachable": False, "http_status": None,
                "mode": "unreachable", "checked_at": _now_iso()}

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, n)) as ex:
            futs = {ex.submit(_liveness, s.get("url", "")): i
                    for i, s in enumerate(sources)}
            for f, i in futs.items():
                try:
                    out[i] = f.result()
                except Exception:  # noqa: BLE001
                    out[i] = _fallback(sources[i])
    except Exception:  # noqa: BLE001 - degrade to sequential
        for i, s in enumerate(sources):
            try:
                out[i] = _liveness(s.get("url", ""))
            except Exception:  # noqa: BLE001
                out[i] = _fallback(s)
    return [o if o is not None else _fallback(sources[i])
            for i, o in enumerate(out)]


def _all_sources() -> List[Dict[str, Any]]:
    seen = {}
    for g in _GAPS:
        for s in g.get("sources", []):
            seen[s["url"]] = s
    return list(seen.values())


# --- background warmer -------------------------------------------------------

def _warm_loop() -> None:
    time.sleep(15)
    while True:
        try:
            for r in _UDS_REPOS:
                _signal(r["repo"])
                time.sleep(1.5)  # be polite to anon GitHub
            _sources_live(_all_sources())
        except Exception:  # noqa: BLE001
            pass
        time.sleep(max(300, _WARM_INTERVAL))


def _start_warmer() -> None:
    global _WARM_STARTED
    if _WARM_STARTED:
        return
    if os.environ.get("SZL_UDS_WARM", "1").lower() not in ("1", "true", "yes", "on"):
        return
    _WARM_STARTED = True
    try:
        threading.Thread(target=_warm_loop, name="szl-uds-warmer",
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        _WARM_STARTED = False


def register(app, ns: str = "a11oy") -> None:
    """Attach the UDS fleet-trust endpoints for namespace ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return

    _WARM_NS.add(ns)
    _start_warmer()

    base = "/api/%s/v1/uds" % ns

    def _gaps_payload(with_liveness: bool) -> List[Dict[str, Any]]:
        out = []
        for g in _GAPS:
            srcs = g.get("sources", [])
            if with_liveness:
                lv = _sources_live(srcs)
                srcs_out = [{**s, "liveness": l} for s, l in zip(srcs, lv)]
                n_ok = sum(1 for l in lv if l.get("reachable"))
            else:
                srcs_out = list(srcs)
                n_ok = None
            out.append({
                "id": g["id"], "gap": g["gap"],
                "fleet_context": g["fleet_context"],
                "a11oy_capability": g["a11oy_capability"],
                "capability_status": g["capability_status"],
                "status_note": g.get("status_note", ""),
                "github": g.get("github", []),
                "sources": srcs_out,
                "sources_reachable": n_ok, "sources_total": len(srcs_out),
            })
        return out

    @app.get(base)
    async def _uds_index():  # noqa: ANN202
        return JSONResponse({
            "layer": "%s \u00d7 UDS fleet-trust" % ns,
            "attribution": _ATTRIB,
            "subject": {
                "name": "Defense Unicorns \u2014 Unicorn Delivery Service (UDS)",
                "site": "https://defenseunicorns.com",
                "docs": "https://uds.defenseunicorns.com/",
                "article": _SRC_ARTICLE["url"],
            },
            "gaps": _gaps_payload(with_liveness=False),
            "repos": [{"repo": r["repo"], "role": r.get("role", ""),
                       "note": r.get("note", ""),
                       "url": "https://github.com/" + r["repo"]}
                      for r in _UDS_REPOS],
            "live_endpoint": base + "/live",
            "sources_live_endpoint": base + "/sources/live",
        })

    @app.get(base + "/live")
    async def _uds_live():  # noqa: ANN202
        signals = [_signal(r["repo"], r.get("role", ""), r.get("note", ""))
                   for r in _UDS_REPOS]
        live_n = sum(1 for s in signals if s.get("mode") == "live")
        return JSONResponse({
            "layer": "%s \u00d7 UDS live signal" % ns,
            "attribution": _ATTRIB,
            "fetched_at": _now_iso(),
            "repos_total": len(signals), "repos_live": live_n,
            "signals": signals,
            "honest": ("Repo metadata, latest release/tag and 90-day release "
                       "cadence are fetched live from the public GitHub REST "
                       "API; each row is labelled live/cached/unreachable. A "
                       "rate-limited GitHub degrades to the last-good cached "
                       "value, never to a fabricated figure."),
        })

    @app.get(base + "/sources/live")
    async def _uds_sources_live():  # noqa: ANN202
        return JSONResponse({
            "layer": "%s \u00d7 UDS source reachability" % ns,
            "attribution": _ATTRIB,
            "gaps": _gaps_payload(with_liveness=True),
            "checked_at": _now_iso(),
        })
