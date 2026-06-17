"""
szl_evidence_research.py — Evidence & Research layer (a11oy + killinchu)
=======================================================================

Grounds the organ demos in REAL, citeable, REFRESHABLE research instead of
static prose. For every headline claim a console tab makes, this module ships:

  * a CURATED bundle of real, resolvable sources — official standards /
    project homes, public datasets, and GitHub repositories (each with a URL);
  * a LIVE overlay pulled at request time from a paper search (the arXiv API
    with a polite back-off, falling back to the OpenAlex API when arXiv
    rate-limits) and the GitHub REST API (repo stars / last-push / license) so
    the panel is refreshable, not frozen prose. Results are kept warm by a
    background timer and an on-disk last-good cache, so a rate-limited upstream
    degrades to "cached", not "unreachable";
  * honest mode labels (live | cached | curated) on every block — a down feed
    degrades to the curated bundle, NEVER to fabricated figures.

Doctrine: claims need machine-readable evidence. Nothing here invents a number.
The only numbers are (a) live counts/stars from the upstream APIs, honestly
labelled with their fetch time, or (b) absent. There are no synthetic figures
in this layer; where the wider console shows illustrative values they are
labelled there. This layer is pure citation + live freshness.

Pattern mirrors a11oy_live_feeds.py / killinchu_live_feeds.py:
    from szl_evidence_research import register as register_evidence_research
    register_evidence_research(app, ns="a11oy")

Endpoints (per namespace ns):
    GET /api/{ns}/v1/evidence/research
        -> index: curated claims + their static sources (fast, always works)
    GET /api/{ns}/v1/evidence/research/{claim_id}/live
        -> refreshable: live arXiv search + live GitHub repo stats for a claim
    GET /api/{ns}/v1/evidence/research/refresh
        -> light freshness sweep across every claim (cached, honest)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

_UA = "szl-evidence-research/1.1 (+https://a11oy.net; research-evidence layer)"
_ARXIV = "https://export.arxiv.org/api/query"
_OPENALEX = "https://api.openalex.org/works"
_GH_REPO = "https://api.github.com/repos/"
# OpenAlex "polite pool" wants a contact; overridable via env, never a secret.
_MAILTO = os.environ.get("SZL_EVIDENCE_MAILTO", "research@a11oy.net")

# ---------------------------------------------------------------------------
# Curated claim -> evidence map. Every URL below is a real, resolvable source:
# an official standard, a public dataset, a canonical project home, or a real
# GitHub repository. arxiv_query drives the LIVE paper overlay.
# ---------------------------------------------------------------------------

def _src(kind: str, title: str, url: str, note: str = "") -> Dict[str, str]:
    return {"kind": kind, "title": title, "url": url, "note": note}


CLAIMS: Dict[str, List[Dict[str, Any]]] = {
    # =====================================================================
    "a11oy": [
        {
            "id": "signed-receipts",
            "tab": "chain",
            "claim": "Every governed decision emits a cryptographically signed, "
                     "tamper-evident receipt (DSSE envelope), verifiable offline.",
            "maturity": "implemented",
            "sources": [
                _src("standard", "in-toto Attestation Framework",
                     "https://github.com/in-toto/attestation",
                     "Signed software-supply-chain statements; our receipt shape."),
                _src("standard", "DSSE — Dead Simple Signing Envelope (spec)",
                     "https://github.com/secure-systems-lab/dsse",
                     "Envelope + PAE pre-auth encoding our receipts use."),
                _src("project", "Sigstore — keyless signing & transparency",
                     "https://www.sigstore.dev/",
                     "Public-good signing model we mirror."),
                _src("dataset", "Rekor public transparency log",
                     "https://rekor.sigstore.dev/",
                     "Append-only signature transparency (our live Rekor feed)."),
            ],
            "github": ["in-toto/attestation", "secure-systems-lab/dsse",
                       "sigstore/cosign", "sigstore/rekor"],
            "arxiv_query": "in-toto software supply chain provenance signing",
        },
        {
            "id": "slsa-provenance",
            "tab": "deploy",
            "claim": "Container images carry verified SLSA build provenance "
                     "(L2 on the organs that claim it; remainder on the roadmap).",
            "maturity": "implemented-partial",
            "sources": [
                _src("standard", "SLSA — Supply-chain Levels for Software Artifacts",
                     "https://slsa.dev/spec/v1.0/levels",
                     "L1-L4 provenance ladder; we claim L2 honestly."),
                _src("project", "SLSA GitHub generator",
                     "https://github.com/slsa-framework/slsa-github-generator",
                     "Reference provenance generator."),
                _src("standard", "NIST SSDF (SP 800-218)",
                     "https://csrc.nist.gov/pubs/sp/800/218/final",
                     "Secure software development framework."),
            ],
            "github": ["slsa-framework/slsa-github-generator", "slsa-framework/slsa"],
            "arxiv_query": "software supply chain security provenance attestation",
        },
        {
            "id": "policy-gates",
            "tab": "gates",
            "claim": "Autonomy is constrained by machine-checkable policy gates; "
                     "severity is an input, the gate verdict is the decision.",
            "maturity": "implemented",
            "sources": [
                _src("project", "Open Policy Agent (OPA) / Rego",
                     "https://www.openpolicyagent.org/",
                     "Policy-as-code engine; our gate model is in this family."),
                _src("standard", "NIST AI Risk Management Framework (AI RMF 1.0)",
                     "https://www.nist.gov/itl/ai-risk-management-framework",
                     "Govern/Map/Measure/Manage functions we map gates onto."),
                _src("standard", "MITRE ATT&CK",
                     "https://attack.mitre.org/",
                     "Adversary technique corpus our gates reference."),
            ],
            "github": ["open-policy-agent/opa", "mitre-attack/attack-stix-data"],
            "arxiv_query": "policy as code safe autonomous agent guardrails",
        },
        {
            "id": "lambda-conjecture",
            "tab": "lambda",
            "claim": "The trust score Lambda is a formally specified research "
                     "conjecture, machine-checked in Lean (advisory, not an oracle).",
            "maturity": "research",
            "sources": [
                _src("project", "Lean 4 theorem prover",
                     "https://github.com/leanprover/lean4",
                     "Proof assistant our Lambda formalisation targets."),
                _src("project", "mathlib4 — Lean mathematical library",
                     "https://github.com/leanprover-community/mathlib4",
                     "Background theory used by the formalisation."),
            ],
            "github": ["leanprover/lean4", "leanprover-community/mathlib4"],
            "arxiv_query": "formal verification trust score multi attribute decision Lean",
        },
        {
            "id": "vuln-grounding",
            "tab": "cve",
            "claim": "Vulnerability prioritisation reads only public signals "
                     "(CVSS + CISA-KEV + OSV + EPSS) and labels that it has no "
                     "environment telemetry.",
            "maturity": "implemented",
            "sources": [
                _src("dataset", "CISA Known Exploited Vulnerabilities (KEV)",
                     "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                     "Exploited-in-the-wild ground truth (our live KEV feed)."),
                _src("dataset", "OSV — Open Source Vulnerabilities",
                     "https://osv.dev/",
                     "Distributed vuln database (our live OSV feed)."),
                _src("dataset", "NVD — National Vulnerability Database",
                     "https://nvd.nist.gov/",
                     "CVSS base scores (the CVE Watch tab reads this live)."),
                _src("dataset", "EPSS — Exploit Prediction Scoring System",
                     "https://www.first.org/epss/",
                     "Data-driven exploit-likelihood, FIRST.org."),
            ],
            "github": ["cisagov/kev-data", "google/osv.dev"],
            "arxiv_query": "exploit prediction scoring system vulnerability prioritization EPSS",
        },
        {
            "id": "ai-oversight",
            "tab": "oversight",
            "claim": "Agentic autonomy is kept under human-auditable oversight; "
                     "no AGI claims are made.",
            "maturity": "research",
            "sources": [
                _src("standard", "NIST AI RMF — Generative AI Profile (600-1)",
                     "https://csrc.nist.gov/pubs/ai/600/1/final",
                     "Risk profile for generative / agentic systems."),
                _src("standard", "ISO/IEC 42001 — AI management systems",
                     "https://www.iso.org/standard/81230.html",
                     "Auditable AI governance management system."),
            ],
            "github": ["openai/evals"],
            "arxiv_query": "AI oversight agent governance constitutional AI alignment",
        },
    ],
    # =====================================================================
    "killinchu": [
        {
            "id": "bft-consensus",
            "tab": "w910gg",
            "claim": "Command authority requires Byzantine-fault-tolerant agreement "
                     "(survives a minority of faulty / compromised nodes).",
            "maturity": "research",
            "sources": [
                _src("project", "PBFT — Practical Byzantine Fault Tolerance (Castro & Liskov)",
                     "https://pmg.csail.mit.edu/papers/osdi99.pdf",
                     "Foundational 3f+1 BFT result."),
                _src("project", "Tendermint / CometBFT consensus",
                     "https://github.com/cometbft/cometbft",
                     "Production BFT state machine replication."),
            ],
            "github": ["cometbft/cometbft", "hyperledger/fabric"],
            "arxiv_query": "byzantine fault tolerant consensus multi agent command",
        },
        {
            "id": "sensor-fusion",
            "tab": "fusion",
            "claim": "Multi-sensor tracks are fused with covariance-aware estimation "
                     "(Kalman / covariance intersection) producing valid uncertainty.",
            "maturity": "implemented",
            "sources": [
                _src("project", "FilterPy — Kalman & Bayesian filters",
                     "https://github.com/rlabbe/filterpy",
                     "Reference Kalman/UKF implementations."),
                _src("project", "Covariance Intersection (Julier & Uhlmann)",
                     "https://en.wikipedia.org/wiki/Covariance_intersection",
                     "Fuse without known cross-covariance; conservative PSD result."),
            ],
            "github": ["rlabbe/filterpy"],
            "arxiv_query": "covariance intersection sensor fusion track estimation",
        },
        {
            "id": "air-picture",
            "tab": "livepic",
            "claim": "The live air picture is built from public ADS-B feeds, "
                     "honestly labelled live vs cached.",
            "maturity": "implemented",
            "sources": [
                _src("dataset", "adsb.lol — community ADS-B (no auth)",
                     "https://adsb.lol/",
                     "Military + civil aircraft feed (our live air feed)."),
                _src("dataset", "The OpenSky Network",
                     "https://opensky-network.org/",
                     "Research-grade ADS-B / Mode-S data."),
                _src("project", "dump1090 — ADS-B decoder",
                     "https://github.com/flightaware/dump1090",
                     "Reference SDR ADS-B decoder."),
            ],
            "github": ["flightaware/dump1090", "wiedehopf/readsb"],
            "arxiv_query": "ADS-B aircraft trajectory anomaly detection surveillance",
        },
        {
            "id": "maritime-picture",
            "tab": "darkhunt",
            "claim": "Maritime / dark-vessel hunting reads public AIS; gaps are "
                     "surfaced as candidate dark vessels, not asserted as targets.",
            "maturity": "implemented",
            "sources": [
                _src("dataset", "Digitraffic — open AIS (Fintraffic)",
                     "https://www.digitraffic.fi/en/marine-traffic/",
                     "Open maritime AIS stream (our live AIS feed)."),
                _src("dataset", "AISStream.io — open AIS websocket",
                     "https://aisstream.io/",
                     "Public AIS message stream."),
            ],
            "github": ["aisstream/example-code"],
            "arxiv_query": "AIS dark vessel detection maritime anomaly trajectory",
        },
        {
            "id": "pqc-signing",
            "tab": "w910audit",
            "claim": "Receipts can be signed with post-quantum signatures "
                     "(ML-DSA / Dilithium) per NIST FIPS 204.",
            "maturity": "implemented",
            "sources": [
                _src("standard", "NIST FIPS 204 — ML-DSA (module-lattice signature)",
                     "https://csrc.nist.gov/pubs/fips/204/final",
                     "Standardised post-quantum signature."),
                _src("project", "pq-crystals/dilithium (reference)",
                     "https://github.com/pq-crystals/dilithium",
                     "Reference ML-DSA / Dilithium implementation."),
                _src("project", "Open Quantum Safe — liboqs",
                     "https://github.com/open-quantum-safe/liboqs",
                     "PQC algorithm library."),
            ],
            "github": ["pq-crystals/dilithium", "open-quantum-safe/liboqs"],
            "arxiv_query": "ML-DSA Dilithium lattice post-quantum digital signature",
        },
        {
            "id": "stl-monitoring",
            "tab": "w910stl",
            "claim": "Runtime behaviour is checked against Signal Temporal Logic "
                     "rules, returning a signed robustness margin rho.",
            "maturity": "research",
            "sources": [
                _src("project", "Robustness of STL (Donze & Maler, FORMATS 2010)",
                     "https://link.springer.com/chapter/10.1007/978-3-642-15297-9_9",
                     "Quantitative robustness semantics (the rho margin)."),
                _src("project", "RTAMT — runtime STL monitoring",
                     "https://github.com/nickovic/rtamt",
                     "Open STL monitor library."),
            ],
            "github": ["nickovic/rtamt"],
            "arxiv_query": "signal temporal logic robustness runtime monitoring",
        },
        {
            "id": "counter-uas",
            "tab": "engage",
            "claim": "Counter-UAS engagement reasoning is grounded in published "
                     "drone-detection research; it is advisory, not a targeting product.",
            "maturity": "research",
            "sources": [
                _src("standard", "FAA UAS Remote ID rule",
                     "https://www.faa.gov/uas/getting_started/remote_id",
                     "Regulatory basis for drone identification."),
                _src("project", "DJI / open drone telemetry references",
                     "https://github.com/opendroneid/opendroneid-core-c",
                     "Open Drone ID core library."),
            ],
            "github": ["opendroneid/opendroneid-core-c"],
            "arxiv_query": "counter UAS drone detection deep learning survey",
        },
    ],
}

# ---------------------------------------------------------------------------
# Live fetch helpers (server-side, cached, honest). No fabrication: on failure
# we return mode="cached"/"unreachable" and lean on the curated bundle.
#
# Resilience strategy (task: papers must load "live", not "unreachable"):
#   1. Paper search tries arXiv first, but with a POLITE back-off — after arXiv
#      rate-limits us (HTTP 429) we stop hammering it for a cool-down window.
#   2. A SECONDARY source (OpenAlex — generous, auth-free "polite pool") is the
#      fallback, so a 429'd arXiv still yields real, citeable papers labelled
#      "live".
#   3. An ON-DISK last-good cache survives process restarts, and a background
#      TIMER keeps every claim warm, so even when BOTH upstreams are momentarily
#      down the panel degrades to "cached" (real prior results), not
#      "unreachable".
# Every paper here is still a real, resolvable record from arXiv or OpenAlex —
# nothing is fabricated.
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_TTL = 1800            # 30 min — GitHub repo-stat freshness window
_MICRO = 180           # 3 min — a paper result fetched this recently is still "live"
_ARXIV_COOLDOWN = 900  # 15 min — skip arXiv after it rate-limits / errors
_LIVENESS_TTL = 900    # 15 min — source-URL reachability badge freshness window
_LIVENESS_TIMEOUT = 8  # 8 s — per-source HEAD/GET probe timeout
_WARM_INTERVAL = int(os.environ.get("SZL_EVIDENCE_WARM_INTERVAL", "1500") or "1500")
_DISK = os.environ.get(
    "SZL_EVIDENCE_CACHE",
    os.path.join(tempfile.gettempdir(), "szl_evidence_cache.json"),
)

_ARXIV_COOLDOWN_UNTIL = 0.0
_DISK_LOADED = False
_WARM_STARTED = False
_WARM_NS: set = set()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _get(url: str, timeout: int = 12, headers: Optional[Dict[str, str]] = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only APIs
        return r.read()


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


# --- paper providers ---------------------------------------------------------

def _try_arxiv(query: str, limit: int) -> Optional[Dict[str, Any]]:
    """Live arXiv search. Returns a value dict, or None on failure/empty.
    Sets the arXiv cool-down on rate-limit / error so we stop hammering it."""
    global _ARXIV_COOLDOWN_UNTIL
    params = urllib.parse.urlencode({
        "search_query": "all:" + query,
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    })
    try:
        raw = _get(_ARXIV + "?" + params, timeout=14)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        papers = []
        for e in root.findall("a:entry", ns):
            link = ""
            for l in e.findall("a:link", ns):
                if l.get("rel") == "alternate" or l.get("type") == "text/html":
                    link = l.get("href") or link
            title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
            summ = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
            pub = (e.findtext("a:published", default="", namespaces=ns) or "")[:10]
            authors = [a.findtext("a:name", default="", namespaces=ns)
                       for a in e.findall("a:author", ns)][:4]
            papers.append({
                "title": title,
                "url": link or (e.findtext("a:id", default="", namespaces=ns) or ""),
                "published": pub, "authors": [a for a in authors if a],
                "summary": summ[:280],
            })
        if not papers:
            return None  # let the secondary source try
        return {"source": "arXiv API", "source_url": "https://arxiv.org",
                "query": query, "count": len(papers), "papers": papers}
    except urllib.error.HTTPError as ex:  # noqa: PERF203
        if ex.code == 429:
            _ARXIV_COOLDOWN_UNTIL = time.time() + _ARXIV_COOLDOWN
        else:
            _ARXIV_COOLDOWN_UNTIL = time.time() + 120
        return None
    except Exception:  # noqa: BLE001 - any failure falls through to OpenAlex
        _ARXIV_COOLDOWN_UNTIL = time.time() + 120
        return None


def _openalex_abstract(inv: Any) -> str:
    """Reconstruct an abstract from OpenAlex's inverted index ({word: [pos,...]})."""
    if not isinstance(inv, dict) or not inv:
        return ""
    try:
        pairs = []
        for word, positions in inv.items():
            for p in positions:
                pairs.append((p, word))
        pairs.sort()
        return " ".join(w for _, w in pairs)
    except Exception:  # noqa: BLE001
        return ""


def _try_openalex(query: str, limit: int) -> Optional[Dict[str, Any]]:
    """Live OpenAlex search — the secondary paper source (auth-free polite pool).
    Returns a value dict, or None on failure/empty."""
    params = urllib.parse.urlencode({
        "search": query,
        "per-page": limit,
        "mailto": _MAILTO,
    })
    try:
        raw = _get(_OPENALEX + "?" + params, timeout=14)
        d = json.loads(raw)
        results = d.get("results") or []
        papers = []
        for w in results[:limit]:
            title = (w.get("display_name") or "").strip()
            if not title:
                continue
            doi = w.get("doi") or ""
            loc = w.get("primary_location") or {}
            landing = loc.get("landing_page_url") if isinstance(loc, dict) else ""
            url = doi or landing or w.get("id") or ""
            authors = []
            for a in (w.get("authorships") or [])[:4]:
                nm = ((a.get("author") or {}) or {}).get("display_name")
                if nm:
                    authors.append(nm)
            summ = _openalex_abstract(w.get("abstract_inverted_index"))
            papers.append({
                "title": title, "url": url,
                "published": (w.get("publication_date") or "")[:10],
                "authors": authors, "summary": summ[:280],
            })
        if not papers:
            return None
        return {"source": "OpenAlex", "source_url": "https://openalex.org",
                "query": query, "count": len(papers), "papers": papers}
    except Exception:  # noqa: BLE001
        return None


def _fetch_live(query: str, limit: int) -> Optional[Dict[str, Any]]:
    """Try arXiv (unless cooling down) then OpenAlex. Returns a value dict or None."""
    skipped_arxiv = False
    if time.time() >= _ARXIV_COOLDOWN_UNTIL:
        r = _try_arxiv(query, limit)
        if r:
            return r
    else:
        skipped_arxiv = True
    r = _try_openalex(query, limit)
    if r:
        return r
    if skipped_arxiv:
        # OpenAlex also failed; arXiv is our only remaining hope despite cool-down.
        r = _try_arxiv(query, limit)
        if r:
            return r
    return None


def _papers(query: str, limit: int = 5) -> Dict[str, Any]:
    """Resilient live paper search with on-disk last-good fallback.
    mode: live (fresh / just-fetched) | cached (last-good) | unreachable."""
    _disk_load()
    key = "papers:" + query
    now = time.time()
    hit = _CACHE.get(key)
    # A result fetched within the micro-window is still genuinely "live".
    if hit and hit.get("live") and now - hit.get("_t", 0) < _MICRO:
        return {**hit["v"], "mode": "live", "fetched_at": hit["at"]}
    val = _fetch_live(query, limit)
    if val:
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    # Both upstreams down: serve the last-good result (any age), honestly cached.
    if hit:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"],
                "note": "live paper sources unreachable; serving last-good cached result"}
    return {"source": "arXiv API / OpenAlex", "source_url": "https://arxiv.org",
            "query": query, "count": 0, "papers": [],
            "mode": "unreachable",
            "note": "live paper sources (arXiv + OpenAlex) unreachable; see curated sources below"}


# Backward-compatible alias (older callers / tests referenced _arxiv).
_arxiv = _papers


def _github(repo: str) -> Dict[str, Any]:
    _disk_load()
    key = "gh:" + repo
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit.get("_t", 0) < _TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
    try:
        raw = _get(_GH_REPO + repo, timeout=10,
                   headers={"Accept": "application/vnd.github+json"})
        d = json.loads(raw)
        val = {
            "repo": repo, "url": d.get("html_url") or ("https://github.com/" + repo),
            "stars": d.get("stargazers_count"),
            "pushed_at": (d.get("pushed_at") or "")[:10],
            "license": ((d.get("license") or {}) or {}).get("spdx_id"),
            "description": (d.get("description") or "")[:160],
            "archived": bool(d.get("archived")),
        }
        at = _now_iso()
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        print(f"[evidence] github fetch error: {ex!r}", file=sys.stderr)
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"repo": repo, "url": "https://github.com/" + repo,
                "stars": None, "mode": "unreachable", "error": "upstream unreachable"}


# --- source-URL reachability (honest live/cached/unreachable badge) ----------

def _probe_url(url: str, timeout: int = _LIVENESS_TIMEOUT):
    """Reachability probe for one curated source URL.

    Returns (reachable: bool, http_status: int | None). Many origins reject a
    HEAD (400/403/405/501) even though the page is fine, so we retry with GET
    before judging. A server that answers with ANY HTTP status counts as
    reachable for the badge (the real status is surfaced alongside)."""
    def _attempt(method: str):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only
                return True, (getattr(r, "status", None) or r.getcode())
        except urllib.error.HTTPError as ex:
            # The origin answered with an HTTP error — it IS reachable; let the
            # caller decide (HEAD-hostile origins are retried with GET below).
            return None, ex.code
        except Exception:  # noqa: BLE001 - DNS/timeout/conn refused = not reachable
            return None, None

    ok, status = _attempt("HEAD")
    if ok:
        return True, status
    # HEAD blocked/rejected by many origins → retry GET before judging.
    gok, gstatus = _attempt("GET")
    if gok:
        return True, gstatus
    # GET produced a real HTTP status (e.g. 403/404) → the server answered.
    if gstatus is not None:
        return True, gstatus
    if status is not None:
        return True, status
    return False, None


def _liveness(url: str) -> Dict[str, Any]:
    """Cached reachability badge for a single source URL.

    mode: live (freshly probed) | cached (last-good badge) | unreachable.
    A failed fresh probe degrades to the last-known-good cached badge, else to
    an honest unreachable — never an invented status."""
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
        _store(key, val, at, live=True)
        return {**val, "mode": "live", "checked_at": at}
    # Probe failed entirely (DNS/timeout/refused): serve last-good if we have it.
    if hit:
        return {**hit["v"], "mode": "cached", "checked_at": hit["at"],
                "note": "live reachability check failed; serving last-good cached badge"}
    return {"url": url, "reachable": False, "http_status": None,
            "mode": "unreachable", "checked_at": _now_iso()}


def _sources_live(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Concurrent reachability sweep over a claim's curated sources."""
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
    except Exception:  # noqa: BLE001 - degrade to sequential probing
        for i, s in enumerate(sources):
            try:
                out[i] = _liveness(s.get("url", ""))
            except Exception:  # noqa: BLE001
                out[i] = _fallback(s)
    return [o if o is not None else _fallback(sources[i])
            for i, o in enumerate(out)]


# --- background warmer: keep every claim's papers fresh in cache -------------

def _warm_loop() -> None:
    time.sleep(15)  # let app startup settle before the first sweep
    while True:
        try:
            seen = set()
            for ns in list(_WARM_NS):
                for c in _claims_for(ns):
                    q = c.get("arxiv_query", c["claim"])
                    if q in seen:
                        continue
                    seen.add(q)
                    try:
                        _papers(q, limit=5)
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        _sources_live(c.get("sources", []))
                    except Exception:  # noqa: BLE001
                        pass
                    time.sleep(5)  # polite spacing between upstream hits
        except Exception:  # noqa: BLE001
            pass
        time.sleep(_WARM_INTERVAL)


def _start_warmer() -> None:
    global _WARM_STARTED
    if _WARM_STARTED:
        return
    if os.environ.get("SZL_EVIDENCE_WARM", "1").lower() not in ("1", "true", "yes", "on"):
        return
    _WARM_STARTED = True
    try:
        threading.Thread(target=_warm_loop, name="szl-evidence-warmer",
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        _WARM_STARTED = False


_HONEST = (
    "Evidence layer: every source below is a real, resolvable citation — an "
    "official standard, a public dataset, or a GitHub repository. Paper lists "
    "are fetched live from the arXiv API (with a polite back-off to the OpenAlex "
    "API when arXiv rate-limits) and repo stats from the GitHub API, all "
    "labelled live/cached/unreachable; a kept-warm on-disk cache means a "
    "rate-limited upstream degrades to a real cached result, never to fabricated "
    "figures. No synthetic numbers are introduced here."
)


def _claims_for(ns: str) -> List[Dict[str, Any]]:
    return CLAIMS.get(ns, CLAIMS.get("a11oy", []))


def register(app, ns: str = "a11oy") -> None:
    """Attach the evidence-research endpoints for namespace ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return

    _WARM_NS.add(ns)
    _start_warmer()

    base = "/api/%s/v1/evidence/research" % ns

    @app.get(base)
    async def _evidence_index():  # noqa: ANN202
        claims = _claims_for(ns)
        out = []
        reachable_total = src_total = 0
        for c in claims:
            liveness = _sources_live(c["sources"])
            sources_out = [{**s, "liveness": lv}
                           for s, lv in zip(c["sources"], liveness)]
            n_ok = sum(1 for lv in liveness if lv.get("reachable"))
            reachable_total += n_ok
            src_total += len(sources_out)
            out.append({
                "id": c["id"], "tab": c.get("tab"), "claim": c["claim"],
                "maturity": c.get("maturity"),
                "sources": sources_out,
                "sources_reachable": n_ok, "sources_total": len(sources_out),
                "github_repos": c.get("github", []),
                "arxiv_query": c.get("arxiv_query"),
                "live_endpoint": "%s/%s/live" % (base, c["id"]),
                "sources_live_endpoint": "%s/%s/sources/live" % (base, c["id"]),
            })
        return JSONResponse({
            "layer": "%s evidence & research" % ns,
            "honest": _HONEST,
            "count": len(out),
            "sources_reachable": reachable_total, "sources_total": src_total,
            "claims": out,
        })

    @app.get(base + "/{claim_id}/live")
    async def _evidence_live(claim_id: str):  # noqa: ANN202
        claim = next((c for c in _claims_for(ns) if c["id"] == claim_id), None)
        if not claim:
            return JSONResponse({"error": "unknown claim", "claim_id": claim_id}, status_code=404)
        papers = _arxiv(claim.get("arxiv_query", claim["claim"]))
        repos = [_github(r) for r in claim.get("github", [])]
        liveness = _sources_live(claim["sources"])
        sources_out = [{**s, "liveness": lv}
                       for s, lv in zip(claim["sources"], liveness)]
        reachable = sum(1 for lv in liveness if lv.get("reachable"))
        return JSONResponse({
            "id": claim["id"], "claim": claim["claim"], "tab": claim.get("tab"),
            "honest": _HONEST,
            "sources": sources_out,
            "sources_reachable": reachable, "sources_total": len(sources_out),
            "arxiv": papers,
            "github": repos,
        })

    @app.get(base + "/{claim_id}/sources/live")
    async def _evidence_sources_live(claim_id: str):  # noqa: ANN202
        claim = next((c for c in _claims_for(ns) if c["id"] == claim_id), None)
        if not claim:
            return JSONResponse({"error": "unknown claim", "claim_id": claim_id}, status_code=404)
        liveness = _sources_live(claim["sources"])
        rows = [{"kind": s.get("kind"), "title": s.get("title"),
                 "url": s.get("url"), "note": s.get("note", ""), "liveness": lv}
                for s, lv in zip(claim["sources"], liveness)]
        reachable = sum(1 for lv in liveness if lv.get("reachable"))
        return JSONResponse({
            "id": claim["id"], "claim": claim["claim"], "tab": claim.get("tab"),
            "honest": _HONEST,
            "sources": rows,
            "sources_reachable": reachable, "sources_total": len(rows),
            "checked_at": _now_iso(),
        })

    @app.get(base + "/refresh")
    async def _evidence_refresh():  # noqa: ANN202
        claims = _claims_for(ns)
        rows = []
        for c in claims:
            p = _arxiv(c.get("arxiv_query", c["claim"]), limit=2)
            lv = _sources_live(c["sources"])
            rows.append({
                "id": c["id"], "claim": c["claim"],
                "arxiv_count": p.get("count", 0), "arxiv_mode": p.get("mode"),
                "n_sources": len(c["sources"]), "n_repos": len(c.get("github", [])),
                "sources_reachable": sum(1 for x in lv if x.get("reachable")),
            })
        return JSONResponse({
            "layer": "%s evidence freshness sweep" % ns,
            "honest": _HONEST, "claims": rows,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
