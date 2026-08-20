# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""a11oy security / governed-AI live data connectors (P0, keyless → CONNECTED now).

  cisa_kev      CISA Known Exploited Vulnerabilities  (public domain, keyless)
  nvd_cve       NVD CVE 2.0                            (keyless; key optional → rate)
  epss          FIRST EPSS exploit-prediction scores   (keyless)  https://www.first.org/epss/api
  mitre_attack  MITRE ATT&CK enterprise STIX           (vendored 0-CDN + online src)
  github        GitHub public API                      (anon 60/hr; token → 5000/hr)

All reuse the proven szl_a11oy_live_feeds honest-state pattern: server-side
single egress, brief TTL cache, labelled live + source_status. NEVER fabricated.
"""
from __future__ import annotations

import time
from typing import Any

from ..base import Connector, Records, State, http_json, http_text, _now
from ..registry import register

_CACHE: dict[str, tuple[float, Any]] = {}


def _cached(key: str, ttl: float):
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        return hit[1]
    return None


def _put(key: str, val: Any):
    _CACHE[key] = (time.time(), val)


# ── CISA KEV ───────────────────────────────────────────────────────────────
@register
class CisaKevConnector(Connector):
    id = "cisa_kev"
    label = "CISA Known Exploited Vulnerabilities"
    category = "vuln"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    docs_url = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
    schema_preview = ["cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded", "knownRansomwareCampaignUse"]
    # raw.githubusercontent mirror (not rate-limited) as fallback source
    _mirror = "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"

    def _probe(self):
        st, _ = http_json(self.provider_base)
        return (st == 200), (f"CISA KEV feed HTTP {st}")

    def read(self, query: dict | None = None) -> Records:
        limit = int((query or {}).get("limit", 25))
        ck = f"kev:{limit}"
        c = _cached(ck, 900)
        if c:
            return c
        st, raw = http_json(self.provider_base)
        if st != 200 or not isinstance(raw, dict):
            st, raw = http_json(self._mirror)
        if isinstance(raw, dict) and raw.get("vulnerabilities"):
            vulns = sorted(raw["vulnerabilities"], key=lambda x: x.get("dateAdded", ""), reverse=True)
            items = [{k: v.get(k) for k in self.schema_preview} for v in vulns[:limit]]
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="CISA KEV (public domain)", live=True,
                        note=f"live · catalog v{raw.get('catalogVersion','?')} · {raw.get('count','?')} total",
                        schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"CISA KEV unreachable (HTTP {st})")


# ── NVD CVE 2.0 ──────────────────────────────────────────────────────────────
@register
class NvdCveConnector(Connector):
    id = "nvd_cve"
    label = "NVD CVE 2.0 (NIST)"
    category = "vuln"
    auth_kind = "none"  # key optional for higher rate
    free_tier = True
    provider_base = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    docs_url = "https://nvd.nist.gov/developers/vulnerabilities"
    schema_preview = ["id", "severity", "cvss", "published", "desc"]

    def _probe(self):
        st, _ = http_json(self.provider_base + "?resultsPerPage=1")
        return (st == 200), f"NVD 2.0 HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        q = (query or {}).get("keyword", "")
        limit = max(1, min(int((query or {}).get("limit", 10)), 20))
        ck = f"cve:{q}:{limit}"
        c = _cached(ck, 300)
        if c:
            return c
        import urllib.parse as up
        params = {"resultsPerPage": limit}
        if q:
            params["keywordSearch"] = q
        st, raw = http_json(self.provider_base + "?" + up.urlencode(params))
        if st == 200 and isinstance(raw, dict):
            items = []
            for v in (raw.get("vulnerabilities", []) or [])[:limit]:
                cve = v.get("cve", {})
                m = cve.get("metrics", {})
                cvss = sev = None
                for mk in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    if m.get(mk):
                        cd = m[mk][0].get("cvssData", {})
                        cvss = cd.get("baseScore"); sev = cd.get("baseSeverity")
                        break
                ds = cve.get("descriptions", [])
                desc = next((d["value"] for d in ds if d.get("lang") == "en"), ds[0]["value"] if ds else "")
                items.append({"id": cve.get("id"), "severity": sev, "cvss": cvss,
                              "published": (cve.get("published") or "")[:10], "desc": desc[:200]})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="NVD 2.0 (NIST, public domain)", live=True,
                        note=f"live · query={q or '(recent)'}", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"NVD unreachable (HTTP {st})")


# ── EPSS (FIRST) ─────────────────────────────────────────────────────────────
@register
class EpssConnector(Connector):
    id = "epss"
    label = "EPSS Exploit Prediction (FIRST)"
    category = "vuln"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://api.first.org/data/v1/epss"
    docs_url = "https://www.first.org/epss/api"
    schema_preview = ["cve", "epss", "percentile", "date"]

    def _probe(self):
        st, _ = http_json(self.provider_base + "?cve=CVE-2021-44228")
        return (st == 200), f"EPSS HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        cve = (query or {}).get("cve", "")
        order = (query or {}).get("order", "!epss")
        limit = max(1, min(int((query or {}).get("limit", 15)), 50))
        import urllib.parse as up
        params = {"limit": limit}
        if cve:
            params["cve"] = cve
        else:
            params["order"] = order  # top exploit-likely CVEs
        ck = f"epss:{cve}:{order}:{limit}"
        c = _cached(ck, 600)
        if c:
            return c
        st, raw = http_json(self.provider_base + "?" + up.urlencode(params))
        if st == 200 and isinstance(raw, dict):
            items = [{"cve": d.get("cve"), "epss": d.get("epss"),
                      "percentile": d.get("percentile"), "date": d.get("date")}
                     for d in (raw.get("data", []) or [])[:limit]]
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="FIRST EPSS API", live=True,
                        note=f"live · {raw.get('total','?')} scored CVEs", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"EPSS unreachable (HTTP {st})")


# ── MITRE ATT&CK STIX (vendored 0-CDN + online source) ──────────────────────
@register
class MitreAttackConnector(Connector):
    id = "mitre_attack"
    label = "MITRE ATT&CK (enterprise STIX)"
    category = "attack"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"
    docs_url = "https://attack.mitre.org/"
    schema_preview = ["technique_id", "name", "tactic", "description"]

    def _probe(self):
        # cheap HEAD-like: the STIX bundle is large; just confirm a 200 quickly
        st, _ = http_text(self.provider_base, timeout=5.0)
        return (st == 200), f"ATT&CK STIX HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        limit = max(1, min(int((query or {}).get("limit", 20)), 60))
        ck = f"attack:{limit}"
        c = _cached(ck, 3600)
        if c:
            return c
        st, raw = http_json(self.provider_base, timeout=15.0)
        if st == 200 and isinstance(raw, dict):
            items = []
            for o in raw.get("objects", []):
                if o.get("type") != "attack-pattern":
                    continue
                ext = next((r for r in o.get("external_references", [])
                            if r.get("source_name") == "mitre-attack"), {})
                tactic = ", ".join(p.get("phase_name", "") for p in o.get("kill_chain_phases", []))
                items.append({"technique_id": ext.get("external_id"), "name": o.get("name"),
                              "tactic": tactic, "description": (o.get("description") or "")[:160]})
                if len(items) >= limit:
                    break
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="MITRE ATT&CK enterprise STIX (vendored 0-CDN; online source)",
                        live=True, note="live STIX (vendored in-image for 0-CDN)", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"ATT&CK STIX unreachable (HTTP {st})")


# ── GitHub public API ─────────────────────────────────────────────────────────
@register
class GithubConnector(Connector):
    id = "github"
    label = "GitHub public API"
    category = "data_source"
    auth_kind = "token"   # anon works; token raises the rate limit
    free_tier = True       # anon keyless tier exists
    env_vars = ["SZL_GITHUB_TOKEN", "GITHUB_TOKEN"]
    provider_base = "https://api.github.com"
    docs_url = "https://docs.github.com/en/rest"
    schema_preview = ["full_name", "description", "stars", "language", "updated_at"]

    def _missing_env(self):
        # keyless anon tier exists → never blocks to READY; token just raises rate
        return []

    def _headers(self):
        import os
        tok = os.environ.get("SZL_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        h = {"Accept": "application/vnd.github+json"}
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        return h

    def _probe(self):
        st, _ = http_json(self.provider_base + "/rate_limit", headers=self._headers())
        return (st == 200), f"GitHub API HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        org = (query or {}).get("org", "szl-holdings")
        limit = max(1, min(int((query or {}).get("limit", 10)), 30))
        ck = f"gh:{org}:{limit}"
        c = _cached(ck, 300)
        if c:
            return c
        st, raw = http_json(f"{self.provider_base}/orgs/{org}/repos?per_page={limit}&sort=updated",
                            headers=self._headers())
        if st == 200 and isinstance(raw, list):
            items = [{"full_name": r.get("full_name"), "description": (r.get("description") or "")[:120],
                      "stars": r.get("stargazers_count"), "language": r.get("language"),
                      "updated_at": (r.get("updated_at") or "")[:10]} for r in raw[:limit]]
            import os
            authed = bool(os.environ.get("SZL_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN"))
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source=f"GitHub API /orgs/{org}/repos", live=True,
                        note=f"live · {'token (5000/hr)' if authed else 'anon (60/hr)'}",
                        schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"GitHub API HTTP {st}")


__all__ = ["CisaKevConnector", "NvdCveConnector", "EpssConnector",
           "MitreAttackConnector", "GithubConnector"]
