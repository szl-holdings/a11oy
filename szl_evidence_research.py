"""
szl_evidence_research.py — Evidence & Research layer (a11oy + killinchu)
=======================================================================

Grounds the organ demos in REAL, citeable, REFRESHABLE research instead of
static prose. For every headline claim a console tab makes, this module ships:

  * a CURATED bundle of real, resolvable sources — official standards /
    project homes, public datasets, and GitHub repositories (each with a URL);
  * a LIVE overlay pulled at request time from the arXiv API (papers) and the
    GitHub REST API (repo stars / last-push / license) so the panel is
    refreshable, not frozen prose;
  * a LIVE reachability probe (HEAD, falling back to GET) for every curated
    standard / dataset / project source URL, so each cited page carries an
    honest reachable | unreachable badge — not just the GitHub repos;
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
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

_UA = "szl-evidence-research/1.0 (+https://a11oy.net; research-evidence layer)"
_ARXIV = "https://export.arxiv.org/api/query"
_GH_REPO = "https://api.github.com/repos/"

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
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Dict[str, Any]] = {}
_TTL = 1800  # 30 min


def _get(url: str, timeout: int = 12, headers: Optional[Dict[str, str]] = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only APIs
        return r.read()


def _arxiv(query: str, limit: int = 5) -> Dict[str, Any]:
    key = "arxiv:" + query
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit["_t"] < _TTL:
        return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
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
                "title": title, "url": link or (e.findtext("a:id", default="", namespaces=ns) or ""),
                "published": pub, "authors": [a for a in authors if a],
                "summary": summ[:280],
            })
        val = {"source": "arXiv API", "source_url": "https://arxiv.org",
               "query": query, "count": len(papers), "papers": papers}
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _CACHE[key] = {"v": val, "_t": now, "at": at}
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"],
                    "note": "live arXiv unreachable; cached result"}
        return {"source": "arXiv API", "source_url": "https://arxiv.org",
                "query": query, "count": 0, "papers": [],
                "mode": "unreachable", "error": str(ex)[:120],
                "note": "live arXiv unreachable; see curated sources below"}


def _github(repo: str) -> Dict[str, Any]:
    key = "gh:" + repo
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit["_t"] < _TTL:
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
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _CACHE[key] = {"v": val, "_t": now, "at": at}
        return {**val, "mode": "live", "fetched_at": at}
    except Exception as ex:  # noqa: BLE001
        if hit:
            return {**hit["v"], "mode": "cached", "fetched_at": hit["at"]}
        return {"repo": repo, "url": "https://github.com/" + repo,
                "stars": None, "mode": "unreachable", "error": str(ex)[:120]}


_LIVE_TTL = 900  # 15 min — source reachability is checked more often than papers


def _liveness(url: str, timeout: int = 8) -> Dict[str, Any]:
    """HEAD-then-GET reachability probe for a curated source URL.

    Returns an honest reachable/unreachable badge with the HTTP status and check
    time. A cached successful result is reused for _LIVE_TTL; if a fresh check
    fails but the URL was reachable before, we degrade to the cached badge rather
    than fabricate. Never invents a status — unreachable means unreachable.
    """
    key = "live:" + url
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit["_t"] < _LIVE_TTL:
        return {**hit["v"], "mode": "cached"}
    status: Optional[int] = None
    ok = False
    err: Optional[str] = None
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - public read-only
                status = int(getattr(r, "status", None) or r.getcode())
            ok = 200 <= status < 400
            if ok:
                break
        except urllib.error.HTTPError as he:  # noqa: PERF203
            status = int(he.code)
            # Many CDNs/origins reject HEAD; retry once with GET before judging.
            if method == "HEAD" and he.code in (400, 403, 405, 501):
                err = "HTTP %s on HEAD" % he.code
                continue
            ok = 200 <= he.code < 400
            err = "HTTP %s" % he.code
            break
        except Exception as ex:  # noqa: BLE001
            err = str(ex)[:120]
            continue
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if ok:
        val = {"url": url, "reachable": True, "http_status": status, "checked_at": at}
        _CACHE[key] = {"v": val, "_t": now}
        return {**val, "mode": "live"}
    if hit:  # fresh check failed but we have a last-known-good — degrade, don't lie
        return {**hit["v"], "mode": "cached",
                "note": "live check failed; showing last-known reachable"}
    return {"url": url, "reachable": False, "http_status": status,
            "error": err, "checked_at": at, "mode": "unreachable"}


def _sources_live(sources: List[Dict[str, Any]],
                  max_workers: int = 6) -> List[Dict[str, Any]]:
    """Probe a claim's curated sources concurrently, attaching a liveness badge."""
    if not sources:
        return []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(sources))) as ex:
        badges = list(ex.map(lambda s: _liveness(s["url"]), sources))
    return [{**s, "liveness": b} for s, b in zip(sources, badges)]


_HONEST = (
    "Evidence layer: every source below is a real, resolvable citation — an "
    "official standard, a public dataset, or a GitHub repository. Paper lists "
    "and repo stats are fetched live from the arXiv and GitHub APIs, and every "
    "standard/dataset/project source URL is probed live (HEAD/GET) for a "
    "reachable/unreachable badge — all labelled live/cached/unreachable. A down "
    "feed degrades to the curated citations, never to fabricated figures. No "
    "synthetic numbers are introduced here."
)


def _claims_for(ns: str) -> List[Dict[str, Any]]:
    return CLAIMS.get(ns, CLAIMS.get("a11oy", []))


def register(app, ns: str = "a11oy") -> None:
    """Attach the evidence-research endpoints for namespace ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return

    base = "/api/%s/v1/evidence/research" % ns

    @app.get(base)
    async def _evidence_index():  # noqa: ANN202
        claims = _claims_for(ns)
        out = []
        for c in claims:
            out.append({
                "id": c["id"], "tab": c.get("tab"), "claim": c["claim"],
                "maturity": c.get("maturity"),
                "sources": c["sources"],
                "github_repos": c.get("github", []),
                "arxiv_query": c.get("arxiv_query"),
                "live_endpoint": "%s/%s/live" % (base, c["id"]),
            })
        return JSONResponse({
            "layer": "%s evidence & research" % ns,
            "honest": _HONEST,
            "count": len(out),
            "claims": out,
        })

    @app.get(base + "/{claim_id}/live")
    async def _evidence_live(claim_id: str):  # noqa: ANN202
        claim = next((c for c in _claims_for(ns) if c["id"] == claim_id), None)
        if not claim:
            return JSONResponse({"error": "unknown claim", "claim_id": claim_id}, status_code=404)
        papers = _arxiv(claim.get("arxiv_query", claim["claim"]))
        repos = [_github(r) for r in claim.get("github", [])]
        sources = _sources_live(claim["sources"])
        return JSONResponse({
            "id": claim["id"], "claim": claim["claim"], "tab": claim.get("tab"),
            "honest": _HONEST,
            "sources": sources,
            "sources_reachable": sum(
                1 for s in sources if s.get("liveness", {}).get("reachable")),
            "arxiv": papers,
            "github": repos,
        })

    @app.get(base + "/{claim_id}/sources/live")
    async def _evidence_sources_live(claim_id: str):  # noqa: ANN202
        claim = next((c for c in _claims_for(ns) if c["id"] == claim_id), None)
        if not claim:
            return JSONResponse({"error": "unknown claim", "claim_id": claim_id}, status_code=404)
        sources = _sources_live(claim["sources"])
        return JSONResponse({
            "id": claim["id"], "claim": claim["claim"], "tab": claim.get("tab"),
            "honest": _HONEST,
            "sources": sources,
            "n_sources": len(sources),
            "reachable": sum(
                1 for s in sources if s.get("liveness", {}).get("reachable")),
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    @app.get(base + "/refresh")
    async def _evidence_refresh():  # noqa: ANN202
        claims = _claims_for(ns)
        rows = []
        for c in claims:
            p = _arxiv(c.get("arxiv_query", c["claim"]), limit=2)
            src = _sources_live(c["sources"])
            rows.append({
                "id": c["id"], "claim": c["claim"],
                "arxiv_count": p.get("count", 0), "arxiv_mode": p.get("mode"),
                "n_sources": len(c["sources"]),
                "sources_reachable": sum(
                    1 for s in src if s.get("liveness", {}).get("reachable")),
                "n_repos": len(c.get("github", [])),
            })
        return JSONResponse({
            "layer": "%s evidence freshness sweep" % ns,
            "honest": _HONEST, "claims": rows,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
