"""
szl_readiness.py — Operational Readiness layer (a11oy + killinchu)
==================================================================

Proves *deployed-vs-repo reality* for an organ, with honest live / cached /
unreachable labels on every value. This is the operational counterpart to
szl_evidence_research.py: where the evidence layer grounds *claims* in real
citations, this layer grounds *the running system* in real, refreshable signals
read from three independent surfaces —

  * the DEPLOYED app's own ``/healthz`` and ``/version`` endpoints (what the
    live process actually reports about itself — organ, doctrine, lock, build
    commit, build time, release);
  * the public GitHub REPOSITORY API (default branch, HEAD commit + date,
    license, archived flag, latest CI run conclusion, latest release tag);
  * the Hugging Face SPACE API (runtime stage, sdk, last-modified, commit).

The centrepiece is the **deployed-vs-repo parity** section, which compares the
deployment's *reported build commit* (``/version`` ``git_sha``) against the
repository HEAD via the GitHub *compare* API and reports an honest
``behind_by`` delta. The doctrine anchor (``kernel_commit``) is the locked,
kernel-verified formulas commit; it is surfaced verbatim and labelled as such —
it is NEVER equated with HEAD, because the two are different kinds of thing.

Doctrine: nothing here is invented. Every value is (a) read live from one of the
three real surfaces and labelled with its fetch/probe time, (b) served from a
kept-warm on-disk last-good cache and labelled ``cached`` when an upstream is
momentarily down, or (c) honestly absent / ``unreachable``. There are no
synthetic statuses. Where the wider console shows illustrative values they are
labelled there; this layer is pure live operational truth.

Pattern mirrors szl_evidence_research.py:
    from szl_readiness import register as register_readiness
    register_readiness(app, ns="a11oy")

Endpoints (per namespace ns):
    GET /api/{ns}/v1/readiness
        -> index: every readiness section with its current live status
    GET /api/{ns}/v1/readiness/{section_id}/live
        -> force-fresh re-read of one section (deployment|identity|repo|space|parity)
    GET /api/{ns}/v1/readiness/refresh
        -> light freshness sweep / one-line summary across the whole organ
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_UA = "szl-readiness/1.0 (+https://a11oy.net; operational-readiness layer)"
_GH_API = "https://api.github.com/"
_HF_API = "https://huggingface.co/api/"

# Optional, env-supplied tokens — NEVER hard-coded. Public GitHub/HF reads work
# unauthenticated (rate-limited); a token, when present, lifts the limit only.
_GH_TOKEN = (os.environ.get("SZL_READINESS_GH_TOKEN")
             or os.environ.get("GITHUB_TOKEN")
             or os.environ.get("GH_TOKEN") or "").strip()
_HF_TOKEN = (os.environ.get("SZL_READINESS_HF_TOKEN")
             or os.environ.get("HF_TOKEN") or "").strip()

# ---------------------------------------------------------------------------
# Per-namespace deployment descriptor. Every URL below is a real, resolvable
# production surface; bases are env-overridable for portability but default to
# the canonical live endpoints. register(app, ns) selects the matching entry.
# ---------------------------------------------------------------------------

def _envbase(ns: str, default: str) -> str:
    return (os.environ.get("SZL_READINESS_%s_BASE" % ns.upper()) or default).rstrip("/")


def _a11oy_cfg() -> Dict[str, Any]:
    base = _envbase("a11oy", "https://a11oy.net")
    api = base + "/api/a11oy/v1"
    return {
        "organ": "a11oy",
        "repo": "szl-holdings/a11oy",
        "branch": "main",
        "hf_space": "SZLHOLDINGS/a11oy",
        "deployment": {
            "name": "a11oy.net",
            "base": base,
            "healthz_url": base + "/healthz",
            "version_url": api + "/version",
            "endpoints": [
                {"id": "apex", "role": "site",
                 "title": "Public site (apex)", "url": base + "/"},
                {"id": "console", "role": "app",
                 "title": "Operator console", "url": base + "/console"},
                {"id": "healthz", "role": "health",
                 "title": "Liveness probe", "url": base + "/healthz"},
                {"id": "api", "role": "api",
                 "title": "Live API (evidence read)",
                 "url": api + "/evidence/research"},
            ],
        },
    }


def _killinchu_cfg() -> Dict[str, Any]:
    base = _envbase("killinchu", "https://killinchu.a11oy.net")
    api = base + "/api/killinchu/v1"
    return {
        "organ": "killinchu",
        "repo": "szl-holdings/killinchu",
        "branch": "main",
        "hf_space": "SZLHOLDINGS/killinchu",
        "deployment": {
            "name": "killinchu.a11oy.net",
            "base": base,
            "healthz_url": base + "/healthz",
            "version_url": api + "/version",
            "endpoints": [
                {"id": "elite", "role": "app",
                 "title": "Elite console", "url": base + "/elite"},
                {"id": "path", "role": "site",
                 "title": "Path mount (a11oy.net/killinchu)",
                 "url": _envbase("a11oy", "https://a11oy.net") + "/killinchu"},
                {"id": "healthz", "role": "health",
                 "title": "Liveness probe", "url": base + "/healthz"},
                {"id": "api", "role": "api",
                 "title": "Live API (evidence read)",
                 "url": api + "/evidence/research"},
            ],
        },
    }


def _cfg_for(ns: str) -> Dict[str, Any]:
    return _killinchu_cfg() if ns == "killinchu" else _a11oy_cfg()


# ---------------------------------------------------------------------------
# Cache + fetch infra (server-side, honest). On failure we return mode="cached"
# (real last-good reading) or "unreachable" — never a fabricated value.
# Mirrors szl_evidence_research.py's resilience strategy: a kept-warm on-disk
# last-good cache survives restarts and a background timer keeps it fresh, so a
# momentarily down upstream degrades to "cached", not "unreachable".
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_DEPLOY_TTL = 120       # 2 min — deployed /healthz + /version freshness
_DEPLOY_MICRO = 45      # 45 s — a deployed read this recent is still "live"
_GH_TTL = 600           # 10 min — GitHub repo/CI/release/compare freshness
_HF_TTL = 600           # 10 min — Hugging Face Space freshness
_LIVENESS_TTL = 300     # 5 min — endpoint reachability badge freshness
_LIVENESS_TIMEOUT = 8   # 8 s — per-endpoint HEAD/GET probe timeout
_WARM_INTERVAL = int(os.environ.get("SZL_READINESS_WARM_INTERVAL", "240") or "240")
_DISK = os.environ.get(
    "SZL_READINESS_CACHE",
    os.path.join(tempfile.gettempdir(), "szl_readiness_cache.json"),
)

_DISK_LOADED = False
_WARM_STARTED = False
_WARM_NS: set = set()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _get(url: str, timeout: int = 12, headers: Optional[Dict[str, str]] = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only APIs
        return r.read()


def _gh_headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if _GH_TOKEN:
        h["Authorization"] = "Bearer " + _GH_TOKEN
    return h


def _hf_headers() -> Dict[str, str]:
    h: Dict[str, str] = {}
    if _HF_TOKEN:
        h["Authorization"] = "Bearer " + _HF_TOKEN
    return h


# --- on-disk last-good cache (survives restarts; warmed by the timer) --------

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


def _store(key: str, val: Dict[str, Any], at: str, live: bool = True) -> None:
    with _LOCK:
        _CACHE[key] = {"v": val, "_t": time.time(), "at": at, "live": live}
    _disk_save()


def _hit(key: str) -> Optional[Dict[str, Any]]:
    _disk_load()
    return _CACHE.get(key)


# ---------------------------------------------------------------------------
# Deployed-app reader: GET the running process's own JSON endpoint, cached,
# honest. mode: live | cached | unreachable. Never invents a body.
# ---------------------------------------------------------------------------

def _deployed(url: str, fresh: bool = False) -> Dict[str, Any]:
    key = "dep:" + url
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and hit.get("live") and now - hit.get("_t", 0) < _DEPLOY_MICRO:
        return {"json": hit["v"], "mode": "live", "fetched_at": hit["at"]}
    if not fresh and hit and now - hit.get("_t", 0) < _DEPLOY_TTL:
        return {"json": hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        raw = _get(url, timeout=10)
        d = json.loads(raw)
        if not isinstance(d, dict):
            d = {"_raw": str(d)[:400]}
        at = _now_iso()
        _store(key, d, at, live=True)
        return {"json": d, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {"json": hit["v"], "mode": "cached", "fetched_at": hit["at"],
                    "note": "deployed endpoint unreachable; serving last-good cached reading"}
        return {"json": {}, "mode": "unreachable", "fetched_at": _now_iso(),
                "error": str(ex)[:140]}


# ---------------------------------------------------------------------------
# GitHub repository readers (repo meta + HEAD, latest CI run, latest release,
# commit existence, branch compare). All cached + honest.
# ---------------------------------------------------------------------------

def _gh_repo(repo: str, branch: str, fresh: bool = False) -> Dict[str, Any]:
    key = "ghrepo:" + repo + "@" + branch
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _GH_TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        d = json.loads(_get(_GH_API + "repos/" + repo, timeout=10, headers=_gh_headers()))
        head_sha = head_date = None
        try:
            cd = json.loads(_get(_GH_API + "repos/" + repo + "/commits/" + branch,
                                 timeout=10, headers=_gh_headers()))
            head_sha = cd.get("sha")
            head_date = ((cd.get("commit") or {}).get("committer") or {}).get("date")
        except Exception:  # noqa: BLE001 - HEAD commit is best-effort
            pass
        val = {
            "repo": repo,
            "url": d.get("html_url") or ("https://github.com/" + repo),
            "default_branch": d.get("default_branch"),
            "pushed_at": d.get("pushed_at"),
            "archived": bool(d.get("archived")),
            "license": ((d.get("license") or {}) or {}).get("spdx_id"),
            "open_issues": d.get("open_issues_count"),
            "head_sha": head_sha,
            "head_date": head_date,
            "description": (d.get("description") or "")[:160],
        }
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"repo": repo, "url": "https://github.com/" + repo,
                "head_sha": None, "mode": "unreachable", "error": str(ex)[:140]}


def _gh_runs(repo: str, branch: str, fresh: bool = False) -> Dict[str, Any]:
    key = "ghruns:" + repo + "@" + branch
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _GH_TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        q = urllib.parse.urlencode({"branch": branch, "per_page": 1})
        d = json.loads(_get(_GH_API + "repos/" + repo + "/actions/runs?" + q,
                            timeout=10, headers=_gh_headers()))
        runs = d.get("workflow_runs") or []
        r = runs[0] if runs else {}
        val = {
            "name": r.get("name"),
            "status": r.get("status"),
            "conclusion": r.get("conclusion"),
            "created_at": r.get("created_at"),
            "url": r.get("html_url"),
            "head_sha": r.get("head_sha"),
            "event": r.get("event"),
            "has_runs": bool(runs),
        }
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"conclusion": None, "mode": "unreachable", "error": str(ex)[:140]}


def _gh_release(repo: str, fresh: bool = False) -> Dict[str, Any]:
    key = "ghrel:" + repo
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _GH_TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        d = json.loads(_get(_GH_API + "repos/" + repo + "/releases/latest",
                            timeout=10, headers=_gh_headers()))
        val = {"tag": d.get("tag_name"), "name": d.get("name"),
               "published_at": d.get("published_at"), "url": d.get("html_url"),
               "prerelease": bool(d.get("prerelease"))}
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except urllib.error.HTTPError as ex:  # noqa: PERF203
        if ex.code == 404:
            val = {"tag": None, "note": "no published release"}
            at = _now_iso()
            _store(key, val, at, live=True)
            return {**val, "mode": "live", "fetched_at": at}
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"tag": None, "mode": "unreachable", "error": "HTTP %s" % ex.code}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"tag": None, "mode": "unreachable", "error": str(ex)[:140]}


def _gh_commit_exists(repo: str, sha: str, fresh: bool = False) -> Dict[str, Any]:
    if not sha:
        return {"exists": None, "mode": "unreachable"}
    key = "ghcommit:" + repo + ":" + sha
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _GH_TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        _get(_GH_API + "repos/" + repo + "/commits/" + sha, timeout=10,
             headers=_gh_headers())
        val = {"exists": True}
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except urllib.error.HTTPError as ex:  # noqa: PERF203
        if ex.code in (404, 422):
            val = {"exists": False}
            at = _now_iso()
            _store(key, val, at, live=True)
            return {**val, "mode": "live", "fetched_at": at}
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"exists": None, "mode": "unreachable", "error": "HTTP %s" % ex.code}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"exists": None, "mode": "unreachable", "error": str(ex)[:140]}


def _gh_compare(repo: str, base: str, head: str, fresh: bool = False) -> Dict[str, Any]:
    """Compare base...head. With base=deployed_sha, head=branch: ahead_by is how
    many commits the branch is ahead of the deployment (i.e. how far BEHIND the
    deployment is); behind_by is deployment-only commits (normally 0)."""
    if not base or not head:
        return {"mode": "unreachable", "ahead_by": None}
    key = "ghcmp:" + repo + ":" + base + "..." + head
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _GH_TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        d = json.loads(_get(_GH_API + "repos/" + repo + "/compare/" + base + "..." + head,
                            timeout=12, headers=_gh_headers()))
        val = {"status": d.get("status"), "ahead_by": d.get("ahead_by"),
               "behind_by": d.get("behind_by"), "total_commits": d.get("total_commits")}
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"mode": "unreachable", "ahead_by": None, "error": str(ex)[:140]}


# ---------------------------------------------------------------------------
# Hugging Face Space reader.
# ---------------------------------------------------------------------------

def _hf_space(org: str, name: str, fresh: bool = False) -> Dict[str, Any]:
    key = "hf:" + org + "/" + name
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _HF_TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        d = json.loads(_get(_HF_API + "spaces/" + org + "/" + name, timeout=10,
                            headers=_hf_headers()))
        rt = d.get("runtime") or {}
        val = {"id": d.get("id") or (org + "/" + name),
               "stage": rt.get("stage"),
               "sdk": d.get("sdk"),
               "lastModified": d.get("lastModified"),
               "sha": d.get("sha"),
               "private": bool(d.get("private")),
               "likes": d.get("likes"),
               "url": "https://huggingface.co/spaces/" + org + "/" + name}
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"id": org + "/" + name, "stage": None, "mode": "unreachable",
                "url": "https://huggingface.co/spaces/" + org + "/" + name,
                "error": str(ex)[:140]}


# ---------------------------------------------------------------------------
# Endpoint reachability (honest live/cached/unreachable badge) — same probe
# shape as szl_evidence_research.py: a server that answers with ANY HTTP status
# counts as reachable (the real status is surfaced alongside).
# ---------------------------------------------------------------------------

def _probe_url(url: str, timeout: int = _LIVENESS_TIMEOUT) -> Tuple[bool, Optional[int]]:
    def _attempt(method: str):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only
                return True, (getattr(r, "status", None) or r.getcode())
        except urllib.error.HTTPError as ex:
            return None, ex.code
        except Exception:  # noqa: BLE001 - DNS/timeout/conn refused = not reachable
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


def _liveness(url: str, fresh: bool = False) -> Dict[str, Any]:
    if not url:
        return {"url": url, "reachable": False, "http_status": None,
                "mode": "unreachable", "checked_at": _now_iso()}
    key = "live:" + url
    now = time.time()
    hit = _hit(key)
    if not fresh and hit and now - hit.get("_t", 0) < _LIVENESS_TTL:
        return {**hit["v"], "mode": "cached", "checked_at": hit["at"]}
    reachable, status = _probe_url(url)
    if reachable or status is not None:
        val = {"url": url, "reachable": bool(reachable), "http_status": status}
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "checked_at": at}
    if hit:
        return {**hit["v"], "mode": "cached", "checked_at": hit["at"],
                "note": "live reachability check failed; serving last-good cached badge"}
    return {"url": url, "reachable": False, "http_status": None,
            "mode": "unreachable", "checked_at": _now_iso()}


def _endpoints_live(endpoints: List[Dict[str, Any]], fresh: bool = False) -> List[Dict[str, Any]]:
    n = len(endpoints)
    out: List[Optional[Dict[str, Any]]] = [None] * n
    if n == 0:
        return []

    def _fallback(e: Dict[str, Any]) -> Dict[str, Any]:
        return {"url": e.get("url", ""), "reachable": False, "http_status": None,
                "mode": "unreachable", "checked_at": _now_iso()}

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, n)) as ex:
            futs = {ex.submit(_liveness, e.get("url", ""), fresh): i
                    for i, e in enumerate(endpoints)}
            for f, i in futs.items():
                try:
                    out[i] = f.result()
                except Exception:  # noqa: BLE001
                    out[i] = _fallback(endpoints[i])
    except Exception:  # noqa: BLE001 - degrade to sequential probing
        for i, e in enumerate(endpoints):
            try:
                out[i] = _liveness(e.get("url", ""), fresh)
            except Exception:  # noqa: BLE001
                out[i] = _fallback(e)
    return [o if o is not None else _fallback(endpoints[i]) for i, o in enumerate(out)]


# ---------------------------------------------------------------------------
# Section builders. Each returns an honest, self-describing dict the console
# tab renders generically. All values trace to a real surface above.
# ---------------------------------------------------------------------------

def _kv(label: str, value: Any, mode: Optional[str] = None) -> Dict[str, Any]:
    return {"k": label, "v": value, "mode": mode}


def _sec_deployment(cfg: Dict[str, Any], fresh: bool = False) -> Dict[str, Any]:
    dep = cfg["deployment"]
    eps = dep["endpoints"]
    live = _endpoints_live(eps, fresh=fresh)
    rows = [{"id": e.get("id"), "role": e.get("role"), "title": e.get("title"),
             "url": e.get("url"), "liveness": lv} for e, lv in zip(eps, live)]
    reachable = sum(1 for lv in live if lv.get("reachable"))
    return {"id": "deployment", "kind": "endpoints",
            "title": "Deployment surface", "target": dep["name"],
            "endpoints": rows, "reachable": reachable, "total": len(rows)}


def _sec_identity(cfg: Dict[str, Any], fresh: bool = False) -> Dict[str, Any]:
    dep = cfg["deployment"]
    hz = _deployed(dep["healthz_url"], fresh=fresh)
    ver = _deployed(dep["version_url"], fresh=fresh)
    hj, vj = hz.get("json") or {}, ver.get("json") or {}
    fields = [
        _kv("organ", hj.get("organ") or vj.get("name"), hz.get("mode")),
        _kv("status", hj.get("status"), hz.get("mode")),
        _kv("version", vj.get("version"), ver.get("mode")),
        _kv("build commit (git_sha)", vj.get("git_sha"), ver.get("mode")),
        _kv("build time", vj.get("build_time"), ver.get("mode")),
        _kv("doctrine", hj.get("doctrine") or vj.get("doctrine"), hz.get("mode")),
        _kv("doctrine lock", hj.get("lock"), hz.get("mode")),
        _kv("kernel commit (doctrine anchor)", vj.get("kernel_commit") or hj.get("commit"), ver.get("mode")),
        _kv("P6 sign-off", vj.get("p6_status"), ver.get("mode")),
        _kv("P6 grader score", vj.get("p6_grader_score"), ver.get("mode")),
        _kv("release", vj.get("release_url"), ver.get("mode")),
    ]
    fields = [f for f in fields if f["v"] not in (None, "")]
    return {"id": "identity", "kind": "kv",
            "title": "Deployed identity (what the running app reports)",
            "fields": fields,
            "healthz_url": dep["healthz_url"], "version_url": dep["version_url"],
            "healthz_mode": hz.get("mode"), "version_mode": ver.get("mode"),
            "fetched_at": ver.get("fetched_at") or hz.get("fetched_at"),
            "raw_healthz": hj, "raw_version": vj}


def _sec_repo(cfg: Dict[str, Any], fresh: bool = False) -> Dict[str, Any]:
    repo = cfg["repo"]
    branch = cfg["branch"]
    r = _gh_repo(repo, branch, fresh=fresh)
    runs = _gh_runs(repo, branch, fresh=fresh)
    rel = _gh_release(repo, fresh=fresh)
    fields = [
        _kv("repository", repo, r.get("mode")),
        _kv("default branch", r.get("default_branch"), r.get("mode")),
        _kv("HEAD commit", (r.get("head_sha") or "")[:12] or None, r.get("mode")),
        _kv("HEAD date", r.get("head_date"), r.get("mode")),
        _kv("last push", r.get("pushed_at"), r.get("mode")),
        _kv("license", r.get("license"), r.get("mode")),
        _kv("archived", r.get("archived"), r.get("mode")),
        _kv("open issues/PRs", r.get("open_issues"), r.get("mode")),
        _kv("latest CI", ("%s — %s" % (runs.get("name") or "run", runs.get("conclusion") or runs.get("status") or "?")) if runs.get("has_runs") else "no runs", runs.get("mode")),
        _kv("latest release", rel.get("tag") or rel.get("note") or "none", rel.get("mode")),
    ]
    fields = [f for f in fields if f["v"] not in (None, "")]
    return {"id": "repo", "kind": "kv",
            "title": "Repository reality (GitHub)",
            "repo": repo, "repo_url": r.get("url"),
            "fields": fields,
            "ci": {"name": runs.get("name"), "conclusion": runs.get("conclusion"),
                   "status": runs.get("status"), "url": runs.get("url"),
                   "created_at": runs.get("created_at"), "mode": runs.get("mode")},
            "release": {"tag": rel.get("tag"), "url": rel.get("url"),
                        "published_at": rel.get("published_at"), "mode": rel.get("mode")},
            "mode": r.get("mode"), "fetched_at": r.get("fetched_at")}


def _sec_space(cfg: Dict[str, Any], fresh: bool = False) -> Dict[str, Any]:
    org, name = cfg["hf_space"].split("/", 1)
    hf = _hf_space(org, name, fresh=fresh)
    fields = [
        _kv("space", hf.get("id"), hf.get("mode")),
        _kv("runtime stage", hf.get("stage"), hf.get("mode")),
        _kv("sdk", hf.get("sdk"), hf.get("mode")),
        _kv("last modified", hf.get("lastModified"), hf.get("mode")),
        _kv("space commit", (hf.get("sha") or "")[:12] or None, hf.get("mode")),
        _kv("visibility", ("private" if hf.get("private") else "public") if hf.get("mode") != "unreachable" else None, hf.get("mode")),
    ]
    fields = [f for f in fields if f["v"] not in (None, "")]
    return {"id": "space", "kind": "kv",
            "title": "Hugging Face Space", "space_url": hf.get("url"),
            "fields": fields, "stage": hf.get("stage"),
            "mode": hf.get("mode"), "fetched_at": hf.get("fetched_at")}


def _sec_parity(cfg: Dict[str, Any], fresh: bool = False) -> Dict[str, Any]:
    dep = cfg["deployment"]
    repo, branch = cfg["repo"], cfg["branch"]
    ver = _deployed(dep["version_url"], fresh=fresh)
    hz = _deployed(dep["healthz_url"], fresh=fresh)
    r = _gh_repo(repo, branch, fresh=fresh)
    vj, hj = ver.get("json") or {}, hz.get("json") or {}
    git_sha = vj.get("git_sha")
    head = r.get("head_sha")

    # --- build parity: deployed git_sha vs repo HEAD (via compare) -----------
    build: Dict[str, Any] = {
        "deployed_git_sha": git_sha, "repo_head_sha": head,
        "deployed_mode": ver.get("mode"), "repo_mode": r.get("mode"),
        "branch": branch,
    }
    if git_sha and head:
        if git_sha == head:
            build.update(status="current", behind_by=0,
                         detail="deployed build is at repo HEAD")
        else:
            cmp = _gh_compare(repo, git_sha, branch, fresh=fresh)
            build["compare_mode"] = cmp.get("mode")
            ab = cmp.get("ahead_by")
            if cmp.get("mode") == "unreachable" or ab is None:
                build.update(status="unknown",
                             detail="could not compute commit delta (compare unreachable)")
            else:
                build.update(status=("current" if ab == 0 else "behind"),
                             behind_by=ab,
                             deployment_ahead_by=cmp.get("behind_by"),
                             compare_status=cmp.get("status"),
                             detail=("deployed build is %d commit(s) behind %s"
                                     % (ab, branch)) if ab else
                                    ("deployed build matches %s" % branch))
    else:
        build.update(status="unknown",
                     detail="deployed git_sha or repo HEAD unavailable")

    # --- release parity: deployed version vs latest GitHub release tag -------
    rel = _gh_release(repo, fresh=fresh)
    dep_ver = vj.get("version")
    tag = rel.get("tag") or ""
    release = {"deployed_version": dep_ver, "latest_release_tag": rel.get("tag"),
               "release_url": vj.get("release_url") or rel.get("url"),
               "mode": rel.get("mode")}
    if dep_ver and tag:
        norm = tag[1:] if tag[:1].lower() == "v" else tag
        release["status"] = "match" if norm == dep_ver else "drift"
    else:
        release["status"] = "unknown"

    # --- doctrine anchor: surfaced verbatim, resolvability checked (NOT ==HEAD)
    anchor = vj.get("kernel_commit") or hj.get("commit")
    doctrine = {"deployed_kernel_commit": anchor, "healthz_commit": hj.get("commit"),
                "doctrine": vj.get("doctrine") or hj.get("doctrine"),
                "lock": hj.get("lock"),
                "note": "kernel_commit is the locked, kernel-verified formulas commit "
                        "(the doctrine anchor) from the kernel proof repo — surfaced "
                        "verbatim and never equated with the organ's HEAD; it is not "
                        "expected to resolve inside the organ repository"}
    if anchor:
        ex = _gh_commit_exists(repo, anchor, fresh=fresh)
        doctrine["resolvable_in_repo"] = ex.get("exists")
        doctrine["mode"] = ex.get("mode")

    # --- HF Space parity: build-time space sha vs current live space sha ------
    org, name = cfg["hf_space"].split("/", 1)
    hf = _hf_space(org, name, fresh=fresh)
    space = {"deployed_hf_space_sha": vj.get("hf_space_sha"),
             "live_hf_space_sha": hf.get("sha"), "stage": hf.get("stage"),
             "mode": hf.get("mode")}
    if vj.get("hf_space_sha") and hf.get("sha"):
        space["status"] = "match" if vj.get("hf_space_sha") == hf.get("sha") else "drift"
    else:
        space["status"] = "unknown"

    return {"id": "parity", "kind": "parity",
            "title": "Deployed-vs-repo parity",
            "build": build, "release": release,
            "doctrine_anchor": doctrine, "hf_space": space,
            "fetched_at": _now_iso()}


_SECTIONS = {
    "deployment": _sec_deployment,
    "identity": _sec_identity,
    "repo": _sec_repo,
    "space": _sec_space,
    "parity": _sec_parity,
}
_SECTION_ORDER = ["deployment", "identity", "repo", "space", "parity"]


def _summary(sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    by = {s["id"]: s for s in sections}
    out: Dict[str, Any] = {}
    dep = by.get("deployment") or {}
    out["endpoints_reachable"] = dep.get("reachable")
    out["endpoints_total"] = dep.get("total")
    par = by.get("parity") or {}
    b = par.get("build") or {}
    out["build_status"] = b.get("status")
    out["build_behind_by"] = b.get("behind_by")
    repo = by.get("repo") or {}
    out["ci"] = (repo.get("ci") or {}).get("conclusion")
    space = by.get("space") or {}
    out["hf_stage"] = space.get("stage")
    return out


_HONEST = (
    "Operational readiness: every value here is read live from a real surface — "
    "the deployed app's own /healthz and /version endpoints, the public GitHub "
    "repository API, and the Hugging Face Space API — and labelled "
    "live / cached / unreachable. The deployed-vs-repo parity compares the "
    "deployment's reported build commit (git_sha) against the repository HEAD via "
    "the GitHub compare API and reports an honest behind_by delta; the doctrine "
    "anchor (kernel_commit) is the locked, kernel-verified formulas commit, "
    "surfaced verbatim and never equated with HEAD. A kept-warm on-disk cache "
    "means a momentarily unreachable upstream degrades to a real cached reading, "
    "never to a fabricated status. No value on this panel is invented."
)


# --- background snapshot: the full index payload is assembled by the warmer
# (and one-off background builds) and served from cache, so a request NEVER
# blocks on live upstream probes. Every value inside still carries its real
# live / cached / unreachable label and fetch time; the snapshot only adds
# honest age/staleness metadata on top. This is what keeps the panel instant
# even when an upstream (e.g. a hairpinned self-probe) is slow to answer. ----

_SNAPSHOT: Dict[str, Dict[str, Any]] = {}
_SNAPSHOT_LOCK = threading.Lock()
_BUILDING: set = set()
# A snapshot older than this is honestly flagged stale (the warmer fell behind);
# generous vs the warm interval so one slow sweep is not mislabelled stale.
_SNAPSHOT_STALE = max(_WARM_INTERVAL * 2, _DEPLOY_TTL * 2)


def _assemble_index(ns: str) -> Dict[str, Any]:
    """Build the full readiness index payload for ns. This performs the live
    section reads, so it must only ever run off the request path (warmer /
    background build thread)."""
    cfg = _cfg_for(ns)
    sections = [_SECTIONS[sid](cfg) for sid in _SECTION_ORDER]
    return {
        "layer": "%s operational readiness" % ns,
        "honest": _HONEST,
        "organ": cfg["organ"],
        "repo": cfg["repo"],
        "repo_url": "https://github.com/" + cfg["repo"],
        "hf_space": cfg["hf_space"],
        "deployment": cfg["deployment"]["name"],
        "summary": _summary(sections),
        "sections": sections,
        "checked_at": _now_iso(),
    }


def _build_snapshot(ns: str) -> Dict[str, Any]:
    """Assemble and store the index snapshot for ns (background only)."""
    payload = _assemble_index(ns)
    with _SNAPSHOT_LOCK:
        _SNAPSHOT[ns] = {"payload": payload, "_t": time.time(), "at": _now_iso()}
    return payload


def _snapshot(ns: str) -> Optional[Dict[str, Any]]:
    with _SNAPSHOT_LOCK:
        return _SNAPSHOT.get(ns)


def _kick_background_build(ns: str) -> None:
    """Trigger a one-off snapshot build in the background (cold start / explicit
    refresh), de-duplicated so concurrent requests never stampede upstreams."""
    with _SNAPSHOT_LOCK:
        if ns in _BUILDING:
            return
        _BUILDING.add(ns)

    def _run() -> None:
        try:
            _build_snapshot(ns)
        except Exception:  # noqa: BLE001
            pass
        finally:
            with _SNAPSHOT_LOCK:
                _BUILDING.discard(ns)

    try:
        threading.Thread(target=_run, name="szl-readiness-build-%s" % ns,
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        with _SNAPSHOT_LOCK:
            _BUILDING.discard(ns)


# --- background warmer: rebuild every organ's snapshot on a fixed interval ---

def _warm_loop() -> None:
    time.sleep(12)  # let app startup settle before the first sweep
    while True:
        try:
            for ns in list(_WARM_NS):
                try:
                    _build_snapshot(ns)
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(2)  # polite spacing between organs
        except Exception:  # noqa: BLE001
            pass
        time.sleep(_WARM_INTERVAL)


def _start_warmer() -> None:
    global _WARM_STARTED
    if _WARM_STARTED:
        return
    if os.environ.get("SZL_READINESS_WARM", "1").lower() not in ("1", "true", "yes", "on"):
        return
    _WARM_STARTED = True
    try:
        threading.Thread(target=_warm_loop, name="szl-readiness-warmer",
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        _WARM_STARTED = False


def register(app, ns: str = "a11oy") -> None:
    """Attach the operational-readiness endpoints for namespace ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return

    _WARM_NS.add(ns)
    _start_warmer()
    _kick_background_build(ns)  # warm the snapshot ASAP, off the request path

    base = "/api/%s/v1/readiness" % ns

    @app.get(base)
    def _readiness_index():  # noqa: ANN202
        # Serve the background-built snapshot — NEVER probe live on the request
        # path (that is what made this endpoint stall ~36s when a self-probe
        # hairpinned). The snapshot's inner values keep their real
        # live/cached/unreachable labels; we add only honest age/staleness meta.
        snap = _snapshot(ns)
        if snap is not None:
            payload = dict(snap["payload"])
            age = time.time() - snap.get("_t", 0)
            payload["served_from"] = "background-snapshot"
            payload["snapshot_fetched_at"] = snap.get("at")
            payload["snapshot_age_seconds"] = round(age, 1)
            payload["stale"] = age > _SNAPSHOT_STALE
            return JSONResponse(payload)
        # Cold: snapshot not built yet (just-restarted process). Kick a
        # background build and return immediately with an honest "warming"
        # placeholder rather than blocking on the full live probe sweep.
        _kick_background_build(ns)
        cfg = _cfg_for(ns)
        return JSONResponse({
            "layer": "%s operational readiness" % ns,
            "honest": _HONEST,
            "organ": cfg["organ"],
            "repo": cfg["repo"],
            "repo_url": "https://github.com/" + cfg["repo"],
            "hf_space": cfg["hf_space"],
            "deployment": cfg["deployment"]["name"],
            "summary": {},
            "sections": [],
            "served_from": "warming",
            "warming": True,
            "note": ("readiness snapshot is warming after a restart; the "
                     "background probe is running — retry in a few seconds"),
            "checked_at": _now_iso(),
        })

    @app.get(base + "/{section_id}/live")
    def _readiness_section_live(section_id: str):  # noqa: ANN202
        cfg = _cfg_for(ns)
        fn = _SECTIONS.get(section_id)
        if not fn:
            return JSONResponse({"error": "unknown section", "section_id": section_id,
                                 "known": _SECTION_ORDER}, status_code=404)
        return JSONResponse({
            "layer": "%s readiness section" % ns,
            "honest": _HONEST,
            "section": fn(cfg, fresh=True),
            "checked_at": _now_iso(),
        })

    @app.get(base + "/refresh")
    def _readiness_refresh():  # noqa: ANN202
        # Light freshness sweep: trigger a background re-build (so the next poll
        # is fresh) and return the current snapshot summary immediately. Like
        # the index, this never blocks on live upstream probes.
        cfg = _cfg_for(ns)
        _kick_background_build(ns)
        snap = _snapshot(ns)
        if snap is not None:
            age = time.time() - snap.get("_t", 0)
            return JSONResponse({
                "layer": "%s readiness freshness sweep" % ns,
                "honest": _HONEST,
                "organ": cfg["organ"],
                "summary": (snap["payload"].get("summary") or {}),
                "served_from": "background-snapshot",
                "snapshot_fetched_at": snap.get("at"),
                "snapshot_age_seconds": round(age, 1),
                "stale": age > _SNAPSHOT_STALE,
                "refresh_triggered": True,
                "checked_at": _now_iso(),
            })
        return JSONResponse({
            "layer": "%s readiness freshness sweep" % ns,
            "honest": _HONEST,
            "organ": cfg["organ"],
            "summary": {},
            "served_from": "warming",
            "warming": True,
            "refresh_triggered": True,
            "checked_at": _now_iso(),
        })
