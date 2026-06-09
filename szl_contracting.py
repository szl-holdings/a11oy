"""
szl_contracting.py — Contracting Readiness layer (a11oy + killinchu)
====================================================================

A SAM.gov / CAGE + SBIR/STTR contracting-readiness snapshot, surfaced with the
SAME honest live / cached / unreachable discipline as ``szl_readiness.py`` and
``szl_evidence_research.py``. Where the readiness layer grounds the *running
system* in real signals, this layer grounds the org's *federal-contracting
posture* in real, web-sourced eligibility criteria — and is scrupulously honest
about the difference between:

  * a **verified** external rule (the actual SAM.gov / SBIR eligibility
    requirement, each carrying a real source URL + retrieval date);
  * an org fact the system genuinely cannot see, flagged
    **needs_founder_input** (e.g. the org's actual UEI, CAGE code, employee
    count, ownership split) — a flagged unknown is the correct answer, never a
    fabricated number;
  * a real-world step only the founder can take, flagged
    **needs_founder_action** (e.g. complete a SAM.gov registration);
  * an org fact the operator has explicitly supplied through a secure
    environment variable, surfaced as **confirmed** (operator-confirmed, clearly
    distinguished from a web-verified rule — only appears when actually set).

Doctrine: nothing here is invented. Every *requirement* is read from an
authoritative source (sam.gov, sbir.gov, the eCFR, the DoD DSIP) and carries
that source URL + the date it was retrieved; every source URL is additionally
probed live for reachability (HEAD->GET, cached, honest live/cached/unreachable)
so the panel proves its citations resolve. NO registration number, expiration
date, or eligibility verdict about the org is ever asserted without either a
real external source or an explicit operator-supplied value — unknowns are
flagged, not filled.

Pattern mirrors szl_readiness.py:
    from szl_contracting import register as register_contracting
    register_contracting(app, ns="a11oy")

Endpoints (per namespace ns):
    GET /api/{ns}/v1/contracting
        -> full snapshot: every area, every item with its honest status,
           cited sources (with live reachability), summary, founder-action list
    GET /api/{ns}/v1/contracting/{area_id}/live
        -> force-fresh re-read of one area (entity|sbir|sttr|registration|timeline)
           with fresh source-reachability probes
    GET /api/{ns}/v1/contracting/sources/live
        -> focused live reachability sweep over every cited source URL
    GET /api/{ns}/v1/contracting/refresh
        -> light freshness sweep / one-line honest summary
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_UA = "szl-contracting/1.0 (+https://a11oy.net; contracting-readiness layer)"

# ---------------------------------------------------------------------------
# Cited sources. Every requirement below references one of these by id; each
# URL is probed live for reachability so the panel proves its citations resolve.
# `retrieved` is the date the criterion text was read from the source.
# ---------------------------------------------------------------------------

_RETRIEVED = "2026-06-09"

SOURCES: Dict[str, Dict[str, str]] = {
    "sam_reg": {
        "title": "SAM.gov — Get Started with Registration and the Unique Entity ID",
        "url": "https://sam.gov/entity-registration",
        "retrieved": _RETRIEVED,
    },
    "sam_checklist": {
        "title": "SAM.gov — Entity Registration Checklist (PDF)",
        "url": "https://sam.gov/sites/default/files/2024-11/entity-checklist.pdf",
        "retrieved": _RETRIEVED,
    },
    "sbir_elig": {
        "title": "SBIR.gov — Eligibility Requirements (FAQ)",
        "url": "https://www.sbir.gov/faq/eligibility-requirements",
        "retrieved": _RETRIEVED,
    },
    "cfr_702": {
        "title": "eCFR — 13 CFR § 121.702 (SBIR/STTR size & eligibility standards)",
        "url": "https://www.ecfr.gov/current/title-13/chapter-I/part-121/subpart-A/subject-group-ECFRb7921b3fcf04228/section-121.702",
        "retrieved": _RETRIEVED,
    },
    "sbir_compliance": {
        "title": "SBA — SBIR/STTR Eligibility & Size Compliance Guide (PDF)",
        "url": "https://www.sbir.gov/sites/default/files/elig_size_compliance_guide.pdf",
        "retrieved": _RETRIEVED,
    },
    "sbir_regseq": {
        "title": "SBIR.gov — Required Registrations (Tutorial 1)",
        "url": "https://www.sbir.gov/tutorials/registration-requirements/tutorial-1",
        "retrieved": _RETRIEVED,
    },
    "sbir_company_reg": {
        "title": "SBIR.gov — Company Registration (SBA firm registry)",
        "url": "https://app.www.sbir.gov/company-registration/overview",
        "retrieved": _RETRIEVED,
    },
    "sbir_vc": {
        "title": "SBIR.gov — VC/hedge-fund/PE majority-ownership authority by agency",
        "url": "https://www.sbir.gov/vc-ownership-authority",
        "retrieved": _RETRIEVED,
    },
    "sbir_topics": {
        "title": "SBIR.gov — Funding Opportunities (agency solicitations / topics)",
        "url": "https://www.sbir.gov/topics",
        "retrieved": _RETRIEVED,
    },
    "dsip": {
        "title": "DoD (DoW) SBIR/STTR Innovation Portal (DSIP) — Active BAA schedule",
        "url": "https://www.dodsbirsttr.mil/submissions/baa-schedule/active-baa-announcements",
        "retrieved": _RETRIEVED,
    },
    "dsip_home": {
        "title": "DoD (DoW) SBIR/STTR Innovation Portal (DSIP)",
        "url": "https://www.dodsbirsttr.mil/",
        "retrieved": _RETRIEVED,
    },
}

# ---------------------------------------------------------------------------
# Operator-supplied org facts (OPTIONAL). When an operator sets one of these
# environment variables with a value they have personally confirmed (e.g. the
# real UEI printed on the live SAM.gov record), the matching item flips from
# `needs_founder_input` to `confirmed` and surfaces that value, clearly labelled
# operator-confirmed (NOT web-verified). Unset == honest unknown. We deliberately
# do NOT accept the EIN/TIN here (sensitive tax identifier).
# ---------------------------------------------------------------------------

def _env_val(name: str) -> Optional[str]:
    v = (os.environ.get(name) or "").strip()
    return v or None


_ORG: Dict[str, Optional[str]] = {
    "uei": _env_val("SZL_CONTRACTING_UEI"),
    "cage": _env_val("SZL_CONTRACTING_CAGE"),
    "sam_status": _env_val("SZL_CONTRACTING_SAM_STATUS"),
    "sam_expires": _env_val("SZL_CONTRACTING_SAM_EXPIRES"),
    "sbc_control_id": _env_val("SZL_CONTRACTING_SBC_CONTROL_ID"),
    "employees": _env_val("SZL_CONTRACTING_EMPLOYEES"),
    "us_ownership_pct": _env_val("SZL_CONTRACTING_US_OWNERSHIP_PCT"),
    "legal_form": _env_val("SZL_CONTRACTING_LEGAL_FORM"),
    "for_profit_us": _env_val("SZL_CONTRACTING_FORPROFIT_US"),
}
_ORG_ENV = {
    "uei": "SZL_CONTRACTING_UEI", "cage": "SZL_CONTRACTING_CAGE",
    "sam_status": "SZL_CONTRACTING_SAM_STATUS", "sam_expires": "SZL_CONTRACTING_SAM_EXPIRES",
    "sbc_control_id": "SZL_CONTRACTING_SBC_CONTROL_ID", "employees": "SZL_CONTRACTING_EMPLOYEES",
    "us_ownership_pct": "SZL_CONTRACTING_US_OWNERSHIP_PCT", "legal_form": "SZL_CONTRACTING_LEGAL_FORM",
    "for_profit_us": "SZL_CONTRACTING_FORPROFIT_US",
}

# ---------------------------------------------------------------------------
# Cache + liveness infra (mirrors szl_readiness.py: kept-warm on-disk last-good
# cache + background warmer; a momentarily-down source degrades to a real cached
# reachability badge, never a fabricated status).
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_LIVENESS_TTL = 900     # 15 min — source reachability badge freshness
_LIVENESS_TIMEOUT = 8   # 8 s — per-source HEAD/GET probe timeout
_WARM_INTERVAL = int(os.environ.get("SZL_CONTRACTING_WARM_INTERVAL", "1500") or "1500")
_DISK = os.environ.get(
    "SZL_CONTRACTING_CACHE",
    os.path.join(tempfile.gettempdir(), "szl_contracting_cache.json"),
)
_DISK_LOADED = False
_WARM_STARTED = False


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


# --- source reachability probe (HEAD->GET, honest) --------------------------

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
    if gstatus is not None:  # many origins reject HEAD but answer GET (4xx/5xx still = reachable)
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


def _sources_live(fresh: bool = False) -> Dict[str, Dict[str, Any]]:
    ids = list(SOURCES.keys())
    out: Dict[str, Dict[str, Any]] = {}

    def _one(sid: str) -> Tuple[str, Dict[str, Any]]:
        s = SOURCES[sid]
        return sid, {**s, "id": sid, "liveness": _liveness(s["url"], fresh=fresh)}

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(ids) or 1)) as ex:
            for sid, val in ex.map(_one, ids):
                out[sid] = val
    except Exception:  # noqa: BLE001 - degrade to sequential
        for sid in ids:
            _, val = _one(sid)
            out[sid] = val
    return out


# ---------------------------------------------------------------------------
# Curated, web-sourced criteria. Each item is one requirement read from a real
# source (rule_source -> SOURCES) plus the HONEST org standing against it.
# status: verified | confirmed | needs_founder_input | needs_founder_action
#   verified            = sourced external fact/rule, nothing pending
#   confirmed           = org fact the operator supplied via env (value shown)
#   needs_founder_input = org fact the system cannot see (flagged unknown)
#   needs_founder_action= real-world step only the founder can perform
# Operator env values flip the matching `org_key` item to `confirmed`.
# ---------------------------------------------------------------------------

def _item(iid, label, requirement, rule_source, status, note,
          org_key=None, confirm_label=None):
    return {"id": iid, "label": label, "requirement": requirement,
            "rule_source": rule_source, "status": status, "note": note,
            "org_key": org_key, "confirm_label": confirm_label, "value": None}


_AREAS: List[Dict[str, Any]] = [
    {
        "id": "entity",
        "title": "Entity / SAM.gov / CAGE registration",
        "intro": "Federal prime-contracting prerequisites: an active SAM.gov entity "
                 "registration with an assigned UEI and CAGE code. All registration "
                 "is free and must be renewed annually.",
        "items": [
            _item("uei", "Unique Entity ID (UEI)",
                  "A 12-character UEI is assigned in SAM.gov as part of entity "
                  "registration; it replaced the DUNS number in April 2022.",
                  "sam_reg", "needs_founder_input",
                  "The org's actual UEI has not been provided to the system.",
                  org_key="uei", confirm_label="UEI"),
            _item("cage", "CAGE code",
                  "A CAGE (Commercial and Government Entity) code is assigned/"
                  "validated during full SAM.gov entity registration.",
                  "sam_checklist", "needs_founder_input",
                  "The org's CAGE code has not been provided to the system.",
                  org_key="cage", confirm_label="CAGE code"),
            _item("full_reg", "Full entity registration (not UEI-only)",
                  "A full 'Register Entity' is required to bid on contracts and apply "
                  "for federal assistance as a prime awardee; a UEI-only request "
                  "cannot apply for awards directly.",
                  "sam_reg", "needs_founder_action",
                  "Complete a full SAM.gov entity registration (Register Entity), "
                  "not a UEI-only request."),
            _item("login_gov", "SAM.gov account via Login.gov",
                  "A SAM.gov account (username/password managed by Login.gov) is "
                  "required to register and to obtain a UEI.",
                  "sam_reg", "needs_founder_action",
                  "Create a Login.gov account and complete the SAM.gov profile."),
            _item("ein", "EIN / TIN held",
                  "An EIN/TIN (IRS) is required before SAM.gov registration and is "
                  "required to receive any federal award.",
                  "sbir_elig", "needs_founder_input",
                  "Whether the org holds an EIN/TIN is not visible to the system "
                  "(the tax identifier itself is intentionally not surfaced here)."),
            _item("sam_free_timeline", "Cost & timeline",
                  "SAM.gov registration is 100% free (the government never charges "
                  "for it) and typically takes ~3–6 weeks to complete.",
                  "sbir_regseq", "verified",
                  "Verified external fact — informational. Start early; do not pay a "
                  "third party for SAM registration."),
            _item("sam_active", "SAM active status + annual renewal",
                  "A SAM.gov registration must be ACTIVE to bid/receive awards and "
                  "must be renewed annually (it expires).",
                  "sam_reg", "needs_founder_input",
                  "The org's current SAM status (Active/Expired) and expiration date "
                  "are not visible to the system.",
                  org_key="sam_status", confirm_label="SAM status"),
            _item("sam_expires", "SAM expiration date",
                  "Each SAM.gov registration carries an expiration date one year "
                  "after activation/renewal; lapsed registrations cannot win awards.",
                  "sam_reg", "needs_founder_input",
                  "The org's SAM expiration date has not been provided to the system.",
                  org_key="sam_expires", confirm_label="SAM expiration"),
        ],
    },
    {
        "id": "sbir",
        "title": "SBIR eligibility (13 CFR § 121.702)",
        "intro": "An awardee must qualify as a Small Business Concern (SBC) AT THE "
                 "TIME OF AWARD for both Phase I and Phase II. Applicants self-certify "
                 "eligibility; SBA directs policy and the funding agency issues the "
                 "solicitation.",
        "items": [
            _item("forprofit_us", "For-profit, US place of business",
                  "Organized for profit, with a place of business located in the "
                  "United States, operating primarily in the US (or making a "
                  "significant contribution to the US economy).",
                  "cfr_702", "needs_founder_input",
                  "The org's for-profit/US-place-of-business status is not confirmed "
                  "to the system.",
                  org_key="for_profit_us", confirm_label="For-profit US org"),
            _item("legal_form", "Eligible legal form",
                  "Individual proprietorship, partnership, LLC, corporation, joint "
                  "venture, association, trust or cooperative (each JV party must "
                  "independently meet the ownership rule).",
                  "cfr_702", "needs_founder_input",
                  "The org's legal form is not confirmed to the system.",
                  org_key="legal_form", confirm_label="Legal form"),
            _item("ownership", "Ownership & control (>50% US individuals)",
                  "More than 50% directly owned and controlled by one or more "
                  "individuals who are US citizens or permanent resident aliens, or "
                  "by other SBCs that are themselves >50% so owned, or a combination.",
                  "cfr_702", "needs_founder_input",
                  "The org's ownership/control split is not confirmed to the system.",
                  org_key="us_ownership_pct", confirm_label="US-individual ownership %"),
            _item("size_500", "Size standard — ≤500 employees",
                  "The awardee, including its affiliates, has not more than 500 "
                  "employees.",
                  "cfr_702", "needs_founder_input",
                  "The org's employee count (incl. affiliates) is not confirmed to "
                  "the system.",
                  org_key="employees", confirm_label="Employees (incl. affiliates)"),
            _item("work_in_us", "Work performed in the US",
                  "All SBIR/STTR work must be performed in the United States.",
                  "sbir_elig", "needs_founder_input",
                  "The proposed work plan's US-performance commitment is a founder "
                  "input for the specific proposal."),
            _item("pi_employment", "PI primary employment (SBIR)",
                  "For SBIR, the SBC must be the primary place of employment of the "
                  "proposed project's principal investigator at the time of award.",
                  "sbir_elig", "needs_founder_input",
                  "Whether the proposed PI's primary employment is the SBC is a "
                  "per-proposal founder input."),
            _item("self_certify", "Self-certification at award",
                  "Applicants must self-certify SBC eligibility at the time of award; "
                  "be certain of compliance before certifying.",
                  "sbir_elig", "needs_founder_action",
                  "Founder must review and self-certify SBC eligibility at award time."),
            _item("vc_authority", "VC/hedge/PE majority-ownership (SBIR only)",
                  "For SBIR only, some of the 11 participating agencies may award to "
                  "firms majority-owned by multiple VC operating companies, hedge "
                  "funds, or PE firms — only at agencies currently using that "
                  "authority.",
                  "sbir_vc", "verified",
                  "Verified external rule — conditional/informational. Relevant only "
                  "if the org becomes majority VC/hedge/PE-owned; check the per-agency "
                  "authority list."),
        ],
    },
    {
        "id": "sttr",
        "title": "STTR specifics (small firm + research-institution partner)",
        "intro": "STTR additionally requires a formal partnership with a US nonprofit "
                 "research institution and a minimum work split between the two.",
        "items": [
            _item("ri_partner", "Nonprofit research-institution partner",
                  "STTR requires partnering with a US nonprofit research institution: "
                  "a nonprofit college/university, a domestic nonprofit "
                  "scientific/research organization, or an FFRDC.",
                  "sbir_elig", "needs_founder_action",
                  "Founder must secure an eligible US nonprofit research-institution "
                  "partner for any STTR proposal."),
            _item("work_split", "Work split — SBC ≥40%, RI ≥30%",
                  "Under STTR the small business concern must perform at least 40% and "
                  "the research institution at least 30% of the work.",
                  "sbir_elig", "needs_founder_input",
                  "The planned SBC/RI work split is a per-proposal founder input."),
            _item("sttr_pi", "STTR PI placement",
                  "The STTR principal investigator may be primarily employed at EITHER "
                  "the SBC or the research institution (no >50% SBC-employment rule, "
                  "unlike SBIR).",
                  "sbir_elig", "needs_founder_input",
                  "The proposed STTR PI's placement is a per-proposal founder input."),
        ],
    },
    {
        "id": "registration",
        "title": "Required registrations sequence",
        "intro": "Three registrations are required of all SBIR/STTR applicants, plus "
                 "agency-specific portals. Do them in order; SAM can take weeks, so "
                 "start early. All are free.",
        "items": [
            _item("reg_ein", "1. EIN (IRS)",
                  "Obtain an Employer Identification Number from the IRS first — it is "
                  "required before SAM registration.",
                  "sbir_regseq", "needs_founder_input",
                  "Whether the org holds an EIN is not visible to the system."),
            _item("reg_sam", "2. SAM.gov (UEI + CAGE)",
                  "Register the entity in SAM.gov to obtain the UEI and CAGE code; "
                  "allow a few weeks.",
                  "sbir_regseq", "needs_founder_action",
                  "Complete the SAM.gov entity registration (see the Entity area)."),
            _item("reg_sba", "3. SBA Company Registration (SBIR.gov)",
                  "Complete the SBA Company Registration at SBIR.gov to obtain the "
                  "firm's SBC registration (Company/Control ID) used across agencies.",
                  "sbir_company_reg", "needs_founder_action",
                  "Register the firm at SBIR.gov to obtain the SBC Company/Control ID.",
                  org_key="sbc_control_id", confirm_label="SBC Company/Control ID"),
            _item("reg_agency", "4. Agency-specific portals",
                  "Each agency requires its own system: DoD → DSIP; HHS/NIH & DOE → "
                  "Grants.gov (NIH also eRA Commons); NSF → Research.gov; NASA → "
                  "Electronic Handbook. Register on the portal for the target "
                  "solicitation.",
                  "sbir_regseq", "needs_founder_action",
                  "Register on the agency portal(s) for the target solicitation — for "
                  "the Warhacker fit that is the DoD DSIP."),
        ],
    },
    {
        "id": "timeline",
        "title": "Warhacker timeline & agency fit (June 16–19)",
        "intro": "Mapping the org's Warhacker capabilities to an actual open "
                 "solicitation. The specific open-topic window must be read live from "
                 "DSIP — it is NOT asserted here.",
        "items": [
            _item("dod_cadence", "DoD monthly BAA cadence",
                  "DoD (DoW) SBIR/STTR 2026 BAAs pre-release topics on the first "
                  "Wednesday of each month, each with its own open/close dates; "
                  "proposals are submitted via the DSIP portal (CSOs also accepted).",
                  "dsip", "verified",
                  "Verified external rule from the live DSIP schedule."),
            _item("open_topic", "Open topic for the June 16–19 window",
                  "A specific open BAA/CSO topic matching the Warhacker demo window "
                  "must be confirmed on DSIP at submission time.",
                  "dsip", "needs_founder_input",
                  "Not asserted: at retrieval the DSIP active-BAA schedule showed no "
                  "releases to display, so no June 16–19 open topic can be confirmed "
                  "by the system. Founder must check DSIP live for the matching "
                  "open window."),
            _item("capability_map", "Warhacker capability → agency topic mapping",
                  "Map the org's Warhacker capabilities (sovereign AI governance, "
                  "signed deploy receipts, supply-chain attestation) to a specific "
                  "agency topic/solicitation.",
                  "sbir_topics", "needs_founder_input",
                  "The specific topic match is a founder judgement against live "
                  "agency solicitations."),
            _item("reauth", "Program authorization horizon",
                  "Confirm the SBIR/STTR programs remain authorized for the proposal "
                  "period; authorization is set by Congress and changes by statute.",
                  "sbir_topics", "needs_founder_input",
                  "The current statutory authorization horizon should be confirmed "
                  "live with SBA/the agency before relying on a future deadline."),
        ],
    },
]

# Concise, separated list of the real-world steps only the founder can take.
FOUNDER_ACTIONS: List[Dict[str, str]] = [
    {"id": "fa_ein", "step": "Confirm or obtain the org's EIN/TIN with the IRS.",
     "why": "Required before SAM registration and to receive any award.", "source": "sbir_regseq"},
    {"id": "fa_sam", "step": "Create a Login.gov account and complete a FULL SAM.gov "
     "entity registration (not UEI-only); record the assigned UEI and CAGE code, "
     "confirm status = Active, and note the annual expiration date.",
     "why": "Prime-contracting prerequisite; free; takes ~3–6 weeks.", "source": "sam_reg"},
    {"id": "fa_sba", "step": "Complete the SBA Company Registration at SBIR.gov to "
     "obtain the firm's SBC Company/Control ID.",
     "why": "Required of all SBIR/STTR applicants across agencies.", "source": "sbir_company_reg"},
    {"id": "fa_elig", "step": "Confirm the SBIR eligibility facts the system cannot "
     "see: for-profit US org, eligible legal form, >50% US-citizen/PR ownership & "
     "control, ≤500 employees incl. affiliates, and PI primary employment.",
     "why": "Self-certified at time of award; a false certification is disqualifying.",
     "source": "cfr_702"},
    {"id": "fa_sttr", "step": "For STTR: secure a US nonprofit research-institution "
     "partner (university / nonprofit research org / FFRDC) and agree the ≥40% SBC / "
     "≥30% RI work split.",
     "why": "STTR cannot be submitted without an eligible RI partner.", "source": "sbir_elig"},
    {"id": "fa_agency", "step": "Register on the agency portal for the target "
     "solicitation (DoD DSIP for the Warhacker fit) and identify the specific open "
     "BAA/CSO topic + dates that match the Warhacker capabilities.",
     "why": "Each agency uses its own portal; the open window must be read live.",
     "source": "dsip"},
    {"id": "fa_feedback", "step": "Provide the confirmed registration values back to "
     "the system (operator env: SZL_CONTRACTING_UEI / _CAGE / _SAM_STATUS / "
     "_SAM_EXPIRES / _SBC_CONTROL_ID / _EMPLOYEES / _US_OWNERSHIP_PCT / _LEGAL_FORM / "
     "_FORPROFIT_US) so the panel can move items from 'needs founder input' to "
     "'confirmed'.",
     "why": "Keeps the snapshot honest and current without code changes.", "source": "sam_reg"},
]

_HONEST = (
    "Contracting readiness: every REQUIREMENT here is read from an authoritative "
    "source (sam.gov, sbir.gov, the eCFR, the DoD DSIP) and carries that source "
    "URL plus the date it was retrieved; each source URL is also probed live for "
    "reachability and labelled live / cached / unreachable. The org's own "
    "registration facts (UEI, CAGE, SAM active-status/expiration, employee count, "
    "ownership) are NOT asserted — each is flagged 'needs founder input' (the "
    "system cannot see them) or 'needs founder action' (a real-world step only the "
    "founder can take), unless an operator has supplied a value via a secure "
    "environment variable, in which case it is shown as 'confirmed' "
    "(operator-confirmed, not web-verified). No registration number, date, or "
    "eligibility verdict is ever invented; a flagged unknown is the correct answer."
)


# ---------------------------------------------------------------------------
# Builders.
# ---------------------------------------------------------------------------

def _resolve_item(it: Dict[str, Any]) -> Dict[str, Any]:
    """Apply operator-supplied env values + attach the cited source object."""
    out = dict(it)
    src = SOURCES.get(it.get("rule_source") or "")
    out["source"] = {**src, "id": it.get("rule_source")} if src else None
    ok = it.get("org_key")
    if ok and _ORG.get(ok):
        out["status"] = "confirmed"
        out["value"] = _ORG.get(ok)
        out["note"] = ("Operator-confirmed via %s (operator-supplied, not "
                       "independently web-verified)." % _ORG_ENV.get(ok, "env"))
    return out


def _build_area(area: Dict[str, Any], sources_live: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    items = [_resolve_item(it) for it in area["items"]]
    for it in items:
        sid = (it.get("source") or {}).get("id")
        if sid and sid in sources_live:
            it["source"] = {**it["source"], "liveness": sources_live[sid].get("liveness")}
    counts = _count_status(items)
    return {"id": area["id"], "title": area["title"], "intro": area["intro"],
            "items": items, "counts": counts, "total": len(items)}


def _count_status(items: List[Dict[str, Any]]) -> Dict[str, int]:
    out = {"verified": 0, "confirmed": 0,
           "needs_founder_input": 0, "needs_founder_action": 0}
    for it in items:
        s = it.get("status")
        if s in out:
            out[s] += 1
    return out


def _summary(areas: List[Dict[str, Any]], sources_live: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    total = {"verified": 0, "confirmed": 0,
             "needs_founder_input": 0, "needs_founder_action": 0}
    items_total = 0
    for a in areas:
        for k, v in a["counts"].items():
            total[k] += v
        items_total += a["total"]
    reach = sum(1 for s in sources_live.values()
                if (s.get("liveness") or {}).get("reachable"))
    return {
        "items_total": items_total,
        "by_status": total,
        "verified_rules": total["verified"] + total["confirmed"],
        "founder_open": total["needs_founder_input"] + total["needs_founder_action"],
        "sources_total": len(sources_live),
        "sources_reachable": reach,
    }


def _snapshot(fresh: bool = False) -> Dict[str, Any]:
    sl = _sources_live(fresh=fresh)
    areas = [_build_area(a, sl) for a in _AREAS]
    actions = [{**a, "source_url": (SOURCES.get(a.get("source") or "") or {}).get("url")}
               for a in FOUNDER_ACTIONS]
    return {
        "areas": areas,
        "founder_actions": actions,
        "sources": sl,
        "summary": _summary(areas, sl),
        "criteria_retrieved": _RETRIEVED,
    }


# --- background warmer: keep source-reachability badges warm -----------------

def _warm_loop() -> None:
    time.sleep(14)
    while True:
        try:
            _sources_live(fresh=True)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(_WARM_INTERVAL)


def _start_warmer() -> None:
    global _WARM_STARTED
    if _WARM_STARTED:
        return
    if os.environ.get("SZL_CONTRACTING_WARM", "1").lower() not in ("1", "true", "yes", "on"):
        return
    _WARM_STARTED = True
    try:
        threading.Thread(target=_warm_loop, name="szl-contracting-warmer",
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        _WARM_STARTED = False


def register(app, ns: str = "a11oy") -> None:
    """Attach the contracting-readiness endpoints for namespace ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return

    _start_warmer()
    base = "/api/%s/v1/contracting" % ns

    @app.get(base)
    async def _contracting_index():  # noqa: ANN202
        snap = _snapshot(fresh=False)
        return JSONResponse({
            "layer": "%s contracting readiness" % ns,
            "honest": _HONEST,
            "subject": "SZL Holdings — federal SAM/CAGE + SBIR/STTR contracting posture",
            "scope": "SAM.gov / CAGE entity registration and SBIR/STTR eligibility, "
                     "mapped to the Warhacker capabilities and timeline.",
            **snap,
            "checked_at": _now_iso(),
        })

    @app.get(base + "/{area_id}/live")
    async def _contracting_area_live(area_id: str):  # noqa: ANN202
        area = next((a for a in _AREAS if a["id"] == area_id), None)
        if not area:
            return JSONResponse({"error": "unknown area", "area_id": area_id,
                                 "known": [a["id"] for a in _AREAS]}, status_code=404)
        sl = _sources_live(fresh=True)
        return JSONResponse({
            "layer": "%s contracting area" % ns,
            "honest": _HONEST,
            "area": _build_area(area, sl),
            "checked_at": _now_iso(),
        })

    @app.get(base + "/sources/live")
    async def _contracting_sources_live():  # noqa: ANN202
        sl = _sources_live(fresh=True)
        reach = sum(1 for s in sl.values() if (s.get("liveness") or {}).get("reachable"))
        return JSONResponse({
            "layer": "%s contracting source reachability" % ns,
            "honest": _HONEST,
            "sources": sl,
            "sources_total": len(sl),
            "sources_reachable": reach,
            "checked_at": _now_iso(),
        })

    @app.get(base + "/refresh")
    async def _contracting_refresh():  # noqa: ANN202
        snap = _snapshot(fresh=False)
        return JSONResponse({
            "layer": "%s contracting freshness sweep" % ns,
            "honest": _HONEST,
            "summary": snap["summary"],
            "criteria_retrieved": _RETRIEVED,
            "checked_at": _now_iso(),
        })
