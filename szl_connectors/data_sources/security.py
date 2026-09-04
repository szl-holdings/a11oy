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

from ..base import Connector, Records, State, http_json, http_text
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
    schema_preview = ["cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded", "knownRansomwareCampaignUse", "requiredAction"]
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


# ── Killinchu Defensive CVE Fusion ──────────────────────────────────────────
# Correlates three official defensive sources for one exact CVE. This is a
# prioritization instrument, not exploit guidance, asset scanning, or action
# authority. Missing source evidence is omitted from the weighted denominator
# rather than silently treated as a zero-risk observation.
@register
class DefensiveFusionConnector(Connector):
    id = "defensive_fusion"
    label = "Killinchu Defensive CVE Fusion"
    category = "vuln"
    auth_kind = "none"
    free_tier = True
    provider_base = "source-bound:CISA-KEV+NIST-NVD-2.0+FIRST-EPSS"
    docs_url = "https://github.com/szl-holdings/killinchu/blob/main/docs/DEFENSIVE_FUSION_WAVE4.md"
    schema_preview = [
        "cve",
        "priority",
        "priority_score",
        "coverage",
        "known_exploited",
        "known_ransomware_use",
        "cvss",
        "epss",
        "epss_percentile",
        "recommended_action",
        "normalized_evidence_sha256",
    ]

    _cve_pattern = r"^CVE-\d{4}-\d{4,}$"
    _weights = {
        "cvss": 0.35,
        "epss": 0.30,
        "known_exploited": 0.30,
        "known_ransomware_use": 0.05,
    }

    @classmethod
    def _normalize_cve(cls, value: Any) -> str | None:
        import re

        candidate = str(value or "").strip().upper()
        return candidate if re.fullmatch(cls._cve_pattern, candidate) else None

    @staticmethod
    def _as_probability(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number < 0.0 or number > 1.0:
            return None
        return number

    @staticmethod
    def _as_cvss(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number < 0.0 or number > 10.0:
            return None
        return number

    @staticmethod
    def _nvd_record(raw: Any, cve_id: str) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        for wrapper in raw.get("vulnerabilities", []) or []:
            if not isinstance(wrapper, dict):
                continue
            cve = wrapper.get("cve")
            if not isinstance(cve, dict) or str(cve.get("id") or "").upper() != cve_id:
                continue
            metrics = cve.get("metrics") if isinstance(cve.get("metrics"), dict) else {}
            score = severity = vector = version = None
            for metric_name, metric_version in (
                ("cvssMetricV40", "4.0"),
                ("cvssMetricV31", "3.1"),
                ("cvssMetricV30", "3.0"),
                ("cvssMetricV2", "2.0"),
            ):
                rows = metrics.get(metric_name) or []
                if not rows or not isinstance(rows[0], dict):
                    continue
                data = rows[0].get("cvssData") or {}
                if not isinstance(data, dict):
                    continue
                score = DefensiveFusionConnector._as_cvss(data.get("baseScore"))
                severity = data.get("baseSeverity") or rows[0].get("baseSeverity")
                vector = data.get("vectorString")
                version = metric_version
                if score is not None:
                    break
            weaknesses: list[str] = []
            for weakness in cve.get("weaknesses", []) or []:
                if not isinstance(weakness, dict):
                    continue
                for description in weakness.get("description", []) or []:
                    if not isinstance(description, dict):
                        continue
                    value = str(description.get("value") or "").strip().upper()
                    if value.startswith("CWE-") and value not in weaknesses:
                        weaknesses.append(value[:40])
            return {
                "id": cve_id,
                "cvss": score,
                "severity": str(severity or "UNAVAILABLE").upper(),
                "vector": str(vector or "")[:160] or None,
                "cvss_version": version,
                "weaknesses": weaknesses[:20],
                "published": str(cve.get("published") or "")[:32] or None,
                "last_modified": str(cve.get("lastModified") or "")[:32] or None,
                "vuln_status": str(cve.get("vulnStatus") or "UNAVAILABLE")[:80],
            }
        return None

    @staticmethod
    def _epss_record(raw: Any, cve_id: str) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        for row in raw.get("data", []) or []:
            if not isinstance(row, dict) or str(row.get("cve") or "").upper() != cve_id:
                continue
            score = DefensiveFusionConnector._as_probability(row.get("epss"))
            percentile = DefensiveFusionConnector._as_probability(row.get("percentile"))
            return {
                "cve": cve_id,
                "epss": score,
                "percentile": percentile,
                "date": str(row.get("date") or "")[:32] or None,
            }
        return None

    @classmethod
    def _priority(
        cls,
        *,
        cvss: float | None,
        epss: float | None,
        kev_observed: bool,
        known_exploited: bool,
        ransomware_observed: bool,
        ransomware_known: bool,
    ) -> tuple[float | None, str, dict[str, float]]:
        observed: dict[str, float] = {}
        if cvss is not None:
            observed["cvss"] = cvss / 10.0
        if epss is not None:
            observed["epss"] = epss
        if kev_observed:
            observed["known_exploited"] = 1.0 if known_exploited else 0.0
        if ransomware_observed:
            observed["known_ransomware_use"] = 1.0 if ransomware_known else 0.0
        denominator = sum(cls._weights[key] for key in observed)
        if denominator <= 0.0:
            return None, "UNAVAILABLE", observed
        score = sum(cls._weights[key] * value for key, value in observed.items()) / denominator
        score = min(0.99, max(0.0, score))
        if known_exploited or ransomware_known or score >= 0.85:
            priority = "IMMEDIATE"
        elif score >= 0.65:
            priority = "HIGH"
        elif score >= 0.40:
            priority = "ELEVATED"
        else:
            priority = "ROUTINE"
        return round(score, 4), priority, observed

    @staticmethod
    def _recommendation(priority: str) -> str:
        return {
            "IMMEDIATE": (
                "Confirm affected assets, apply the vendor or CISA mitigation, reduce exposure, "
                "and verify remediation under an approved defensive change process."
            ),
            "HIGH": (
                "Schedule accelerated remediation, validate compensating controls, and verify "
                "the affected inventory against the vendor advisory."
            ),
            "ELEVATED": (
                "Prioritize owner review, patch planning, and exposure validation in the next "
                "defensive maintenance window."
            ),
            "ROUTINE": (
                "Track the CVE through normal vulnerability management and re-evaluate when "
                "official KEV, CVSS, or EPSS evidence changes."
            ),
        }.get(priority, "No defensive priority can be computed until official evidence is available.")

    def _probe(self):
        # A cheap exact-CVE EPSS lookup proves the composite transport without
        # downloading the full KEV catalogue or ATT&CK bundle.
        st, _ = http_json(EpssConnector.provider_base + "?cve=CVE-2021-44228")
        return (st == 200), f"Defensive fusion EPSS dependency HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        import hashlib
        import json
        import urllib.parse as up

        requested = (query or {}).get("cve") or (query or {}).get("q") or ""
        cve_id = self._normalize_cve(requested)
        if cve_id is None:
            return Records(
                connector_id=self.id,
                category=self.category,
                state=State.READY,
                records=[],
                source=self.provider_base,
                live=False,
                note="provide one exact CVE identifier, for example q=CVE-2021-44228",
                schema_preview=list(self.schema_preview),
            )

        cache_key = f"defensive-fusion:{cve_id}"
        cached = _cached(cache_key, 300)
        if cached:
            return cached

        source_states = {
            "cisa_kev": "UNAVAILABLE",
            "nvd_cve": "UNAVAILABLE",
            "epss": "UNAVAILABLE",
        }

        kev_entry: dict[str, Any] | None = None
        kev_records = CisaKevConnector().read({"limit": 10000})
        if kev_records.state == State.CONNECTED:
            source_states["cisa_kev"] = "MEASURED"
            kev_entry = next(
                (
                    row
                    for row in kev_records.records
                    if str(row.get("cveID") or "").upper() == cve_id
                ),
                None,
            )

        nvd_status, nvd_raw = http_json(
            NvdCveConnector.provider_base
            + "?"
            + up.urlencode({"cveId": cve_id, "resultsPerPage": 1})
        )
        nvd = self._nvd_record(nvd_raw, cve_id) if nvd_status == 200 else None
        if nvd_status == 200 and isinstance(nvd_raw, dict):
            source_states["nvd_cve"] = "MEASURED"

        epss_status, epss_raw = http_json(
            EpssConnector.provider_base + "?" + up.urlencode({"cve": cve_id, "limit": 1})
        )
        epss = self._epss_record(epss_raw, cve_id) if epss_status == 200 else None
        if epss_status == 200 and isinstance(epss_raw, dict):
            source_states["epss"] = "MEASURED"

        measured = sum(value == "MEASURED" for value in source_states.values())
        coverage = "FULL" if measured == 3 else "PARTIAL" if measured else "NONE"
        known_exploited = kev_entry is not None
        ransomware_value = str(
            (kev_entry or {}).get("knownRansomwareCampaignUse") or ""
        ).strip()
        ransomware_observed = kev_entry is not None and bool(ransomware_value)
        ransomware_known = ransomware_value.casefold() in {
            "known",
            "yes",
            "true",
            "known ransomware campaign use",
        }
        cvss = nvd.get("cvss") if nvd else None
        epss_score = epss.get("epss") if epss else None
        exact_evidence_observed = any(
            value is not None for value in (kev_entry, nvd, epss)
        )
        if measured > 0 and not exact_evidence_observed:
            result = Records(
                connector_id=self.id,
                category=self.category,
                state=State.READY,
                records=[],
                source=self.provider_base,
                live=False,
                note=(
                    f"{coverage.lower()} transport coverage, but the exact CVE was not "
                    "present in returned official records; no priority fabricated"
                ),
                schema_preview=list(self.schema_preview),
            )
            _put(cache_key, result)
            return result
        priority_score, priority, components = self._priority(
            cvss=cvss,
            epss=epss_score,
            kev_observed=source_states["cisa_kev"] == "MEASURED",
            known_exploited=known_exploited,
            ransomware_observed=ransomware_observed,
            ransomware_known=ransomware_known,
        )

        evidence_core = {
            "cve": cve_id,
            "source_states": source_states,
            "kev": {
                "known_exploited": known_exploited,
                "date_added": (kev_entry or {}).get("dateAdded"),
                "ransomware_use": ransomware_value or None,
            },
            "nvd": nvd,
            "epss": epss,
            "formula": {
                "id": "killinchu.defensive-priority/v1",
                "weights": self._weights,
                "observed_components": components,
                "missing_evidence_is_zero": False,
                "maximum_score": 0.99,
            },
        }
        digest = hashlib.sha256(
            json.dumps(
                evidence_core,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        if measured == 0:
            result = Records(
                connector_id=self.id,
                category=self.category,
                state=State.ERROR,
                records=[],
                source=self.provider_base,
                live=False,
                note="all three official defensive sources are unavailable; no priority fabricated",
                schema_preview=list(self.schema_preview),
            )
            _put(cache_key, result)
            return result

        record = {
            "cve": cve_id,
            "priority": priority,
            "priority_score": priority_score,
            "coverage": coverage,
            "sources_measured": measured,
            "sources_expected": 3,
            "source_states": source_states,
            "known_exploited": known_exploited,
            "known_ransomware_use": ransomware_known,
            "ransomware_source_value": ransomware_value or None,
            "cisa_date_added": (kev_entry or {}).get("dateAdded"),
            "cisa_required_action": (kev_entry or {}).get("requiredAction"),
            "cvss": cvss,
            "cvss_severity": nvd.get("severity") if nvd else None,
            "cvss_version": nvd.get("cvss_version") if nvd else None,
            "cvss_vector": nvd.get("vector") if nvd else None,
            "weaknesses": nvd.get("weaknesses", []) if nvd else [],
            "nvd_published": nvd.get("published") if nvd else None,
            "nvd_last_modified": nvd.get("last_modified") if nvd else None,
            "epss": epss_score,
            "epss_percentile": epss.get("percentile") if epss else None,
            "epss_date": epss.get("date") if epss else None,
            "recommended_action": self._recommendation(priority),
            "formula": evidence_core["formula"],
            "normalized_evidence_sha256": digest,
            "truth_label": "MEASURED_DEFENSIVE_CORRELATION",
            "action_authority": "DEFENSIVE_PRIORITIZATION_ONLY",
            "human_approval_required": True,
            "exploit_content_included": False,
            "asset_scanning_performed": False,
        }
        result = Records(
            connector_id=self.id,
            category=self.category,
            state=State.CONNECTED,
            records=[record],
            source="CISA KEV + NIST NVD CVE 2.0 + FIRST EPSS",
            live=True,
            note=(
                f"{coverage.lower()} official-source coverage · deterministic defensive "
                "prioritization only · no exploit content or execution authority"
            ),
            schema_preview=list(self.schema_preview),
        )
        _put(cache_key, result)
        return result


__all__ = ["CisaKevConnector", "NvdCveConnector", "EpssConnector",
           "MitreAttackConnector", "GithubConnector",
           "DefensiveFusionConnector"]
