#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
a11oy_threat_intel.py — SERVER-SIDE THREAT-INTEL + GOVERNANCE FUSION for the console.

Taxonomy home: services (threat/vuln intel + governance), feeding the
threats/cve/kev/attack/gates/policies/govern tabs. Every feed is fetched + cached
SERVER-SIDE (the browser only ever hits OUR same-origin proxy — sovereign, CORS-safe,
0 client CDN), with a short timeout and an HONEST fallback: a down upstream serves the
last good in-memory value labelled "cached", never a fabricated value.

Free, no-auth public sources (verified reachable):
  cve   NVD CVE 2.0          services.nvd.nist.gov/rest/json/cves/2.0
  kev   CISA KEV catalog     cisagov/kev-data (GitHub mirror)
  epss  FIRST EPSS           api.first.org/data/v1/epss
  attack MITRE ATT&CK v17.1  mitre-attack/attack-stix-data (enterprise, bounded subset)
  oscal NIST SP800-53 rev5   usnistgov/oscal-content (catalog summary)
  scorecard OpenSSF Scorecard api.securityscorecards.dev

Leader features adapted (cited, never claimed as ours):
  - Recorded Future Intelligence Graph  -> CVE<->KEV<->ATT&CK technique correlation graph.
  - Tenable One / CrowdStrike ExPRT.AI  -> transparent Exposure Priority (CVSS+KEV+EPSS),
    severity is an INPUT, priority is a DECISION, top factors always shown.
  - Credo AI policy-as-code / NIST AI RMF + OPA -> OSCAL control families mapped to the
    8 deny-by-default gates (GOVERN->MAP->MEASURE->MANAGE).
  - OpenSSF Scorecard -> supply-chain posture for the governance surfaces.

HONEST DELTA: we have NO environment telemetry / asset criticality, so Exposure Priority
scores on PUBLIC signals ONLY (CVSS base + KEV exploited-in-the-wild + EPSS exploit
probability) and SAYS SO. The Lambda (Λ) advisory is Conjecture 1: advisory only, it can
tighten but NEVER override a hard DENY, and it is never presented as a proven-unique score.
"""
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from starlette.responses import JSONResponse
from starlette.routing import Route

_UA = "a11oy-threat-intel/1.0 (+https://szlholdings-a11oy.hf.space)"

_CACHE = {}
_LOCK = threading.Lock()

# TTLs (seconds): vuln feeds change slowly; EPSS/NVD daily-ish.
_TTL = {"cve": 3600, "kev": 6 * 3600, "epss": 6 * 3600,
        "attack": 24 * 3600, "oscal": 24 * 3600, "scorecard": 12 * 3600}

_SRC = {
    "cve": ("NIST NVD CVE 2.0 (recent published)",
            "https://services.nvd.nist.gov/rest/json/cves/2.0"),
    "kev": ("CISA Known Exploited Vulnerabilities catalog (GitHub mirror)",
            "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"),
    "epss": ("FIRST EPSS (Exploit Prediction Scoring System)",
             "https://api.first.org/data/v1/epss"),
    "attack": ("MITRE ATT&CK v17.1 Enterprise (STIX, bounded subset)",
               "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-17.1.json"),
    "oscal": ("NIST OSCAL SP 800-53 rev5 control catalog",
              "https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"),
    "scorecard": ("OpenSSF Scorecard",
                  "https://api.securityscorecards.dev/projects/github.com"),
}

# The 8 deny-by-default gates mapped to NIST SP800-53 rev5 families + NIST AI RMF
# functions (Credo AI / OPA policy-as-code adaptation; honest mapping, not an audit).
_GATE_OSCAL_MAP = [
    {"gate": "doctrine-deny-by-default", "families": ["AC", "CA"], "rmf": "GOVERN"},
    {"gate": "code-as-action-sandbox", "families": ["SC", "SI"], "rmf": "MANAGE"},
    {"gate": "provenance-receipt", "families": ["AU"], "rmf": "MEASURE"},
    {"gate": "supply-chain-screen", "families": ["SR", "CM"], "rmf": "MAP"},
    {"gate": "lambda-restraint", "families": ["RA"], "rmf": "MEASURE"},
    {"gate": "consent-reversibility", "families": ["PT", "PL"], "rmf": "GOVERN"},
    {"gate": "identity-witness", "families": ["IA"], "rmf": "MAP"},
    {"gate": "incident-tripwire", "families": ["IR"], "rmf": "MANAGE"},
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _http(url, timeout=20, headers=None, data=None, method=None):
    h = {"User-Agent": _UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _envelope(key, mode, data, extra=None):
    src, url = _SRC.get(key, ("unknown", ""))
    out = {"source": src, "source_url": url, "mode": mode,
           "fetched_at": _now_iso(), "ttl_s": _TTL.get(key, 3600), "data": data}
    if extra:
        out.update(extra)
    return out


def _cached(key, builder, ttl=None):
    """Run builder() with short timeout; cache; on failure serve last good as 'cached'."""
    ttl = _TTL.get(key, 3600) if ttl is None else ttl
    now = time.time()
    with _LOCK:
        ent = _CACHE.get(key)
    if ent and (now - ent["ts"]) < ttl:
        return _envelope(key, ent["mode"], ent["data"], {"fetched_at": ent["iso"]})
    try:
        data = builder()
        iso = _now_iso()
        with _LOCK:
            _CACHE[key] = {"data": data, "ts": now, "mode": "live", "iso": iso}
        return _envelope(key, "live", data, {"fetched_at": iso})
    except Exception as e:
        if ent:
            return _envelope(key, "cached", ent["data"],
                             {"fetched_at": ent["iso"],
                              "cache_note": "upstream unreachable (%s) — last good value" % type(e).__name__})
        return _envelope(key, "unavailable", None,
                         {"error": "upstream unreachable and no cache: %s" % e})


# ----------------------------------------------------------------------------- feeds
def _fetch_cve():
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=20)
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000")
    q = urllib.parse.urlencode({"resultsPerPage": 40,
                                "pubStartDate": fmt(start), "pubEndDate": fmt(end)})
    raw = _http(_SRC["cve"][1] + "?" + q, timeout=18)
    out = []
    for v in raw.get("vulnerabilities", []):
        c = v.get("cve", {})
        m = c.get("metrics", {})
        arr = m.get("cvssMetricV31") or m.get("cvssMetricV30") or m.get("cvssMetricV2") or []
        cvss = arr[0]["cvssData"]["baseScore"] if arr else None
        sev = (arr[0]["cvssData"].get("baseSeverity") or arr[0].get("baseSeverity")) if arr else "NONE"
        desc = ""
        for d in c.get("descriptions", []):
            if d.get("lang") == "en":
                desc = d.get("value", "")
                break
        out.append({"id": c.get("id"), "cvss": cvss, "severity": str(sev).upper(),
                    "published": (c.get("published") or "")[:10], "desc": desc[:200]})
    out.sort(key=lambda x: x["published"], reverse=True)
    return {"total_results": raw.get("totalResults", 0), "vulnerabilities": out}


def _fetch_kev():
    raw = _http(_SRC["kev"][1], timeout=40)
    vs = raw.get("vulnerabilities", [])
    return {"catalogVersion": raw.get("catalogVersion"), "count": len(vs),
            "vulnerabilities": [{"cveID": x.get("cveID"), "vendorProject": x.get("vendorProject"),
                                 "product": x.get("product"), "name": x.get("vulnerabilityName"),
                                 "dateAdded": x.get("dateAdded"),
                                 "ransomware": str(x.get("knownRansomwareCampaignUse", "")).lower() == "known"}
                                for x in vs]}


def _fetch_epss(cves):
    """EPSS exploit-probability for up to 100 CVE ids; returns {cve: {epss, percentile}}."""
    if not cves:
        # top-ranked EPSS movers when no ids supplied
        raw = _http(_SRC["epss"][1] + "?order=!epss&limit=50", timeout=15)
    else:
        q = urllib.parse.urlencode({"cve": ",".join(cves[:100])})
        raw = _http(_SRC["epss"][1] + "?" + q, timeout=15)
    out = {}
    for d in raw.get("data", []):
        cid = str(d.get("cve", "")).upper()
        if cid:
            out[cid] = {"epss": float(d.get("epss", 0) or 0),
                        "percentile": float(d.get("percentile", 0) or 0)}
    return out


def _fetch_attack():
    """Bounded MITRE ATT&CK v17.1 STIX -> technique->tactic graph for holographic 3D."""
    try:
        raw = _http(_SRC["attack"][1], timeout=45)
    except Exception:
        raw = _http(_SRC["attack"][1].replace("-17.1", ""), timeout=45)  # honest fallback to master
    objs = raw.get("objects", [])
    tactics = {}
    for o in objs:
        if o.get("type") == "x-mitre-tactic":
            tactics[o.get("x_mitre_shortname")] = o.get("name")
    nodes, links, seen_tac = [], [], set()
    tcount = 0
    for o in objs:
        if o.get("type") != "attack-pattern" or o.get("x_mitre_is_subtechnique"):
            continue
        if tcount >= 140:
            break
        ext = next((r for r in o.get("external_references", [])
                    if r.get("source_name") == "mitre-attack"), {})
        tid = ext.get("external_id") or o.get("id")
        nodes.append({"id": tid, "label": (o.get("name") or "")[:28], "kind": "technique"})
        for p in o.get("kill_chain_phases", []):
            if p.get("kill_chain_name") != "mitre-attack":
                continue
            tac = p.get("phase_name")
            tac_id = "TAC:" + str(tac)
            if tac_id not in seen_tac:
                seen_tac.add(tac_id)
                nodes.append({"id": tac_id, "label": tactics.get(tac, tac), "kind": "tactic"})
            links.append({"source": tid, "target": tac_id})
            break
        tcount += 1
    return {"version": raw.get("spec_version", "ATT&CK v17.1"),
            "techniques": tcount, "tactics": len(seen_tac),
            "nodes": nodes, "links": links}


def _fetch_oscal():
    """SP800-53 rev5 catalog -> control families + counts, mapped to a11oy's 8 gates."""
    raw = _http(_SRC["oscal"][1], timeout=40)
    cat = raw.get("catalog", {})
    families = []
    total = 0

    def _walk(groups):
        nonlocal total
        for g in groups or []:
            ctrls = g.get("controls", []) or []
            n = len(ctrls)
            total += n
            families.append({"id": (g.get("id") or "").upper(), "title": g.get("title"),
                             "controls": n})
            _walk(g.get("groups"))
    _walk(cat.get("groups"))
    return {"catalog": cat.get("metadata", {}).get("title", "NIST SP 800-53 rev5"),
            "version": cat.get("metadata", {}).get("version"),
            "total_controls": total, "families": families,
            "gate_mapping": _GATE_OSCAL_MAP}


def _fetch_scorecard(org, repo):
    raw = _http("%s/%s/%s" % (_SRC["scorecard"][1], org, repo), timeout=20)
    checks = [{"name": c.get("name"), "score": c.get("score"),
               "reason": (c.get("reason") or "")[:120]} for c in (raw.get("checks") or [])]
    return {"repo": "%s/%s" % (org, repo), "score": raw.get("score"),
            "date": raw.get("date"), "checks": checks}


# ----------------------------------------------------------- Λ advisory exposure fusion
def _lambda_advisory(cvss, kev, epss, tech_match):
    """Transparent deterministic 0-100 Exposure Priority on PUBLIC signals only.
    Λ = Conjecture 1: advisory; can tighten, never override a hard DENY; not proven-unique."""
    factors, s = [], 0.0
    base = min(10.0, float(cvss or 0)) * 5.0  # CVSS up to 50
    s += base
    if base > 0:
        factors.append("CVSS %.1f" % float(cvss or 0))
    if kev:
        s += 25
        factors.append("actively exploited (CISA KEV)")
        if kev.get("ransomware"):
            s += 5
            factors.append("ransomware campaign")
    if epss:
        ep = float(epss.get("epss", 0) or 0)
        s += ep * 15  # EPSS exploit-probability up to 15
        if ep >= 0.1:
            factors.append("EPSS %.0f%% (FIRST)" % (ep * 100))
    if tech_match:
        s += 5
        factors.append("matches ATT&CK %s" % tech_match)
    return {"score": int(max(0, min(100, round(s)))), "factors": factors}


def _build_intel_cve():
    cve_env = _cached("cve", _fetch_cve)
    kev_env = _cached("kev", _fetch_kev)
    vulns = (cve_env.get("data") or {}).get("vulnerabilities", []) or []
    kev_map = {}
    for x in ((kev_env.get("data") or {}).get("vulnerabilities", []) or []):
        if x.get("cveID"):
            kev_map[str(x["cveID"]).upper()] = x
    ids = [str(v["id"]).upper() for v in vulns if v.get("id")]
    epss_map = _cached("epss", lambda: _fetch_epss(ids)).get("data") or {}
    rows = []
    kev_hits = 0
    for v in vulns:
        cid = str(v.get("id", "")).upper()
        k = kev_map.get(cid)
        if k:
            kev_hits += 1
        adv = _lambda_advisory(v.get("cvss"), k, epss_map.get(cid), None)
        rows.append({**v, "kev": bool(k),
                     "epss": (epss_map.get(cid) or {}).get("epss"),
                     "exposure": adv["score"], "factors": adv["factors"]})
    rows.sort(key=lambda r: r["exposure"], reverse=True)
    return {"mode": cve_env["mode"], "source": cve_env["source"],
            "source_url": cve_env["source_url"], "fetched_at": cve_env["fetched_at"],
            "kev_correlated": kev_hits, "total": len(rows), "rows": rows,
            "lambda_advisory": "Exposure Priority on PUBLIC signals only (CVSS+KEV+EPSS); "
                               "Λ = Conjecture 1, advisory — tightens, never overrides a hard DENY.",
            "leader_adapted": ["Recorded Future Intelligence Graph", "Tenable One Exposure",
                               "CrowdStrike ExPRT.AI"]}


def _build_intel_kev():
    kev_env = _cached("kev", _fetch_kev)
    vs = (kev_env.get("data") or {}).get("vulnerabilities", []) or []
    ids = [str(x["cveID"]).upper() for x in vs[-100:] if x.get("cveID")]
    epss_map = _cached("epss", lambda: _fetch_epss(ids)).get("data") or {}
    for x in vs:
        e = epss_map.get(str(x.get("cveID", "")).upper())
        x["epss"] = e.get("epss") if e else None
        x["epss_percentile"] = e.get("percentile") if e else None
    return {"mode": kev_env["mode"], "source": kev_env["source"],
            "source_url": kev_env["source_url"], "fetched_at": kev_env["fetched_at"],
            "catalogVersion": (kev_env.get("data") or {}).get("catalogVersion"),
            "count": len(vs), "vulnerabilities": vs,
            "epss_enriched": sum(1 for x in vs if x.get("epss") is not None),
            "lambda_advisory": "EPSS exploit-probability enrichment (FIRST); advisory only.",
            "leader_adapted": ["Recorded Future", "Tenable VPR"]}


# --------------------------------------------------------------------------- routing
def register(app, ns="a11oy"):
    base = "/api/%s/v1/policy" % ns
    import anyio

    async def _json(builder):
        return JSONResponse(await anyio.to_thread.run_sync(builder))

    async def r_cve(request):
        return await _json(_build_intel_cve)

    async def r_kev(request):
        return await _json(_build_intel_kev)

    async def r_epss(request):
        cves = [c for c in (request.query_params.get("cve", "").split(",")) if c]
        return await _json(lambda: _cached("epss", lambda: _fetch_epss(cves), ttl=0 if cves else None))

    async def r_attack(request):
        return await _json(lambda: _cached("attack", _fetch_attack))

    async def r_oscal(request):
        return await _json(lambda: _cached("oscal", _fetch_oscal))

    async def r_scorecard(request):
        org = request.query_params.get("org", "szl-holdings")
        repo = request.query_params.get("repo", "a11oy")
        key = "scorecard:%s/%s" % (org, repo)
        return await _json(lambda: _cached(key, lambda: _fetch_scorecard(org, repo)))

    routes = [
        Route(base + "/intel/cve", r_cve, methods=["GET"], name="%s_intel_cve" % ns),
        Route(base + "/intel/kev", r_kev, methods=["GET"], name="%s_intel_kev" % ns),
        Route(base + "/intel/epss", r_epss, methods=["GET"], name="%s_intel_epss" % ns),
        Route(base + "/intel/attack", r_attack, methods=["GET"], name="%s_intel_attack" % ns),
        Route(base + "/oscal", r_oscal, methods=["GET"], name="%s_oscal" % ns),
        Route(base + "/scorecard", r_scorecard, methods=["GET"], name="%s_scorecard" % ns),
    ]
    # front-insert so these resolve before the SPA catch-all (first-match-wins).
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"status": "ok", "base": base,
            "endpoints": [r.path for r in routes]}
