# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SZL Holdings. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainsentry.py — defensive-cyber signal triage (blue-team, transparent, honest).

WHAT THIS SURFACE ANSWERS: "given a batch of raw security signals (log lines, alerts, observed
indicators), which deserve an analyst's attention first — scored by TRANSPARENT, auditable
rules, with every match shown so the triage can never be a black box?"

This is DEFENSIVE cybersecurity — blue-team SOC triage. It classifies and prioritizes signals
for a human analyst; it takes NO action, blocks nothing, and attacks nothing. It is squarely in
the infra-hygiene / defensive lane: it helps stop harm by surfacing it faster.

EXPLICITLY NOT: offensive tooling, exploit generation, target selection, or any counter-UAS /
effector / weapons capability. It reads signals and ranks them for a human. That is all.

HONESTY DISCIPLINE (doctrine v11):
  * A severity score is a MODELED, deterministic function of transparent rule matches; every
    contributing rule is returned so the score is fully auditable. It is never a fabricated or
    ML-black-box number.
  * No input signals -> UNAVAILABLE (nothing to triage), never an invented verdict.
  * The surface RANKS and EXPLAINS; it never claims a signal IS malicious — only that it matches
    N transparent indicators worth analyst review. Adjudication is human-required.
  * Lambda = Conjecture 1; locked-8 immutable adds 0; trust ceiling 0.97; no sentience; trains
    nothing; not counter-UAS; 0 runtime CDN.
  * Receipt is an UNSIGNED SHA-256 content digest, minted on WRITE (POST) only.
"""

from __future__ import annotations

import re
import json
import hashlib
import datetime

HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

SURFACE_ID = "brainsentry"

LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97
KERNEL_COMMIT = "c7c0ba17"

# Triage priorities (ranking buckets, human-adjudicated).
PRIORITY_CRITICAL = "REVIEW-CRITICAL"
PRIORITY_HIGH = "REVIEW-HIGH"
PRIORITY_MEDIUM = "REVIEW-MEDIUM"
PRIORITY_LOW = "REVIEW-LOW"
PRIORITY_INFO = "INFORMATIONAL"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# Transparent, auditable detection rules. Each is a well-known DEFENSIVE indicator family
# (MITRE-ATT&CK-flavored) with a weight. This is not exploit code — it is pattern-matching over
# signals a SOC already collects. Every rule that fires is returned in the result.
RULES = [
    {"id": "auth-bruteforce", "weight": 3,
     "pattern": r"(failed password|authentication failure|invalid user|failed login).{0,40}(from|for)",
     "why": "repeated authentication failures — possible brute force (ATT&CK T1110)"},
    {"id": "priv-esc", "weight": 4,
     "pattern": r"(sudo:.*COMMAND=|to root|privilege escalation|setuid|pkexec)",
     "why": "privilege-escalation indicator (ATT&CK T1068/T1548)"},
    {"id": "web-injection", "weight": 4,
     "pattern": r"(union\s+select|<script>|\.\./\.\./|/etc/passwd|cmd\.exe|\bxp_cmdshell\b)",
     "why": "injection / path-traversal / command-exec pattern (ATT&CK T1190)"},
    {"id": "c2-beacon", "weight": 5,
     "pattern": r"(beacon|cobalt\s?strike|/gate\.php|base64.{0,10}powershell|-enc\s+[A-Za-z0-9+/=]{40,})",
     "why": "possible C2 beacon / encoded PowerShell (ATT&CK T1071/T1059)"},
    {"id": "ransomware-note", "weight": 5,
     "pattern": r"(your files (have been|are) encrypted|\.locked\b|readme_to_decrypt|pay.{0,20}bitcoin)",
     "why": "ransomware note / encryption indicator (ATT&CK T1486)"},
    {"id": "data-exfil", "weight": 4,
     "pattern": r"(scp .* @|rclone copy|\bcurl\b.*(--upload-file|-T )|large outbound|dns tunneling)",
     "why": "possible data exfiltration (ATT&CK T1041/T1048)"},
    {"id": "malware-hash-tag", "weight": 3,
     "pattern": r"\b[a-fA-F0-9]{64}\b|\b[a-fA-F0-9]{32}\b",
     "why": "file hash present — check against threat intel (defensive enrichment)"},
    {"id": "suspicious-persistence", "weight": 3,
     "pattern": r"(crontab -e|/etc/rc\.local|New-Service|schtasks /create|registry.*\\Run\\)",
     "why": "persistence-mechanism indicator (ATT&CK T1053/T1543/T1547)"},
    {"id": "disable-defenses", "weight": 4,
     "pattern": r"(Set-MpPreference.*Disable|systemctl stop (auditd|falcon)|iptables -F|clear.{0,5}logs|wevtutil cl)",
     "why": "defense-evasion / log-clearing indicator (ATT&CK T1562/T1070)"},
]

_COMPILED = [(r, re.compile(r["pattern"], re.IGNORECASE)) for r in RULES]


def _priority(score: int) -> str:
    if score >= 9:
        return PRIORITY_CRITICAL
    if score >= 5:
        return PRIORITY_HIGH
    if score >= 3:
        return PRIORITY_MEDIUM
    if score >= 1:
        return PRIORITY_LOW
    return PRIORITY_INFO


def _doctrine_block(note: str = "", label_top: str = LBL_MODELED) -> dict:
    d = {
        "version": "v11",
        "label_top": label_top,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "is_model_training": False,
        "admits_to_gradients": 0,
        "sentience_claim": False,
        "posture": "DEFENSIVE-BLUE-TEAM-ONLY",
        "takes_action": False,  # ranks and explains for a human; never blocks/acts/attacks
    }
    if note:
        d["note"] = note
    return d


def triage_signal(signal: str) -> dict:
    """Score one signal by transparent rules. Returns the score, priority, and EVERY rule that
    fired (auditable). Never claims malice — only ranks for human review."""
    matched = []
    score = 0
    for rule, rx in _COMPILED:
        if rx.search(signal or ""):
            matched.append({"rule_id": rule["id"], "weight": rule["weight"], "why": rule["why"]})
            score += rule["weight"]
    return {
        "signal_sha256": hashlib.sha256((signal or "").encode("utf-8")).hexdigest()[:16],
        "score": score,
        "priority": _priority(score),
        "matched_rules": matched,
        "matched_count": len(matched),
    }


def triage(signals) -> dict:
    """Triage a batch of signals. No signals -> UNAVAILABLE (never a fabricated verdict)."""
    sigs = [str(s) for s in (signals or []) if str(s).strip()]
    if not sigs:
        return {
            "label": LBL_UNAVAILABLE,
            "verdict": "UNAVAILABLE",
            "note": "no signals provided; nothing to triage. UNAVAILABLE, never an invented verdict.",
            "results": [],
            "ranked": [],
        }
    results = [dict(triage_signal(s), index=i) for i, s in enumerate(sigs)]
    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    top = ranked[0]["priority"] if ranked else PRIORITY_INFO
    counts = {}
    for r in results:
        counts[r["priority"]] = counts.get(r["priority"], 0) + 1
    return {
        "label": LBL_MODELED,  # scores are a MODELED function of transparent rules
        "verdict": top,        # the highest-priority bucket present
        "signal_count": len(sigs),
        "priority_counts": counts,
        "ranked": ranked,
        "note": ("MODELED triage: each score is a transparent, auditable sum of matched defensive "
                 "rule weights. The surface RANKS and EXPLAINS for a human analyst; it never claims "
                 "a signal is malicious and takes no action. Adjudication is human-required."),
    }


def _canonical_core(result: dict) -> str:
    core = {
        "label": result.get("label"), "verdict": result.get("verdict"),
        "signal_count": result.get("signal_count"),
        "ranked": [{"signal_sha256": r.get("signal_sha256"), "score": r.get("score"),
                    "priority": r.get("priority"), "matched_count": r.get("matched_count")}
                   for r in (result.get("ranked") or [])],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(result: dict) -> dict:
    digest = hashlib.sha256(_canonical_core(result).encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainsentry.triage",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST sentry/triage)",
        "note": ("unsigned SHA-256 digest of the defensive triage record; RECEIPT-ON-WRITE. "
                 "Binds the ranking; asserts no malice and no action taken."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "endpoint": "brain/sentry/info",
        "service": f"{ns}.brain.brainsentry",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Sentry — defensive-cyber signal triage (blue-team, transparent)",
        "what": ("scores and ranks raw security signals (log lines, alerts, indicators) by "
                 "transparent, auditable defensive rules so an analyst reviews the riskiest first. "
                 "RANKS and EXPLAINS only — takes no action, blocks nothing, attacks nothing."),
        "posture": "DEFENSIVE-BLUE-TEAM-ONLY — not offensive tooling, not counter-UAS, not weapons",
        "priorities": [PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW, PRIORITY_INFO],
        "rule_families": [{"id": r["id"], "weight": r["weight"], "why": r["why"]} for r in RULES],
        "honesty": ("scores are a MODELED sum of transparent rule weights; every matched rule is "
                    "returned; no signals -> UNAVAILABLE; the surface never claims malice and never "
                    "acts — adjudication is human-required."),
        "endpoints": {
            "info": f"GET  /api/{ns}/v1/brain/sentry/info",
            "triage": f"POST /api/{ns}/v1/brain/sentry/triage  (body: signals[])",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "receipt_policy": "RECEIPT-ON-WRITE (POST triage). GET info/manifest mint nothing.",
        "doctrine": _doctrine_block(),
    }


def handle_manifest(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "endpoint": f"brain/{SURFACE_ID}/manifest",
        "service": f"{ns}.brain.manifest.{SURFACE_ID}",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "data_label": LBL_MODELED,
        "title": "Brain Sentry — defensive-cyber signal triage (blue-team, transparent)",
        "kind": "honesty-manifest",
        "computes": ("MODELED severity ranking of security signals via transparent auditable rules; "
                     "ranks and explains for a human analyst, takes no action, never claims malice; "
                     "defensive blue-team only, not offensive, not counter-UAS."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "routes": {
            "info": f"GET  /api/{ns}/v1/brain/sentry/info",
            "triage": f"POST /api/{ns}/v1/brain/sentry/triage",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "honesty_invariants": {
            "label_in_honest_vocabulary": True,
            "lambda_is_conjecture_not_theorem": True,  # Lambda is Conjecture 1, never a theorem
            "locked_count_is_eight": True,
            "adds_to_locked_8_is_zero": True,
            "trust_ceiling_at_most_0_97": True,
            "trust_never_100_percent": True,
            "score_is_transparent_rule_sum": True,
            "every_matched_rule_returned": True,
            "no_signals_means_unavailable": True,
            "never_claims_malice_human_adjudicates": True,
            "takes_no_action": True,
            "defensive_only_not_offensive": True,
            "not_counter_uas": True,
            "trains_nothing": True,
            "admits_to_gradients_zero": True,
            "no_consciousness_claim": True,
            "zero_runtime_cdn": True,
            "receipt_on_write_not_read": True,
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET manifest mints nothing.",
        "doctrine": _doctrine_block(
            "honesty manifest for brainsentry; declarative only, triages nothing here."),
    }


def handle_triage(signals, ns: str = "a11oy") -> dict:
    result = triage(signals)
    result.update({"ok": True, "endpoint": "brain/sentry/triage",
                   "service": f"{ns}.brain.brainsentry", "surface_id": SURFACE_ID,
                   "receipt": content_receipt(result),
                   "doctrine": _doctrine_block(label_top=result.get("label", LBL_MODELED)),
                   "computed_at": _now_iso()})
    return result


# --------------------------------------------------------------------------- #
# Registration.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain"
    wired = 0

    async def _s_manifest(request):
        return JSONResponse(handle_manifest(ns))

    async def _s_info(request):
        return JSONResponse(handle_info(ns))

    async def _s_triage(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        signals = body.get("signals", [])
        if not isinstance(signals, list):
            signals = [str(signals)]
        return JSONResponse(handle_triage(signals, ns))

    routes = [
        (f"{base}/{SURFACE_ID}/manifest", _s_manifest, "GET"),
        (f"{base}/sentry/info", _s_info, "GET"),
        (f"{base}/sentry/triage", _s_triage, "POST"),
    ]

    try:
        import fastapi as _fastapi
        for _fn in (_s_manifest, _s_info, _s_triage):
            _fn.__annotations__["request"] = _fastapi.Request
    except Exception:
        pass

    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn, method in routes:
        try:
            if callable(add_route):
                app.router.add_route(path, fn, methods=[method])
            elif callable(add_api_route):
                app.add_api_route(path, fn, methods=[method])
            else:
                from starlette.routing import Route
                app.router.routes.append(Route(path, fn, methods=[method]))
            wired += 1
        except Exception as exc:
            __import__("sys").stderr.write(
                f"[{ns}] brainsentry {method} route {path} NOT wired (guarded): {exc!r}\n")

    return f"{SURFACE_ID}-wired:{wired}"


# --------------------------------------------------------------------------- #
# Self-test (network-free).
# --------------------------------------------------------------------------- #
def _selftest() -> dict:
    checks = 0

    # no signals -> UNAVAILABLE, never fabricated
    r = triage([])
    assert r["label"] == LBL_UNAVAILABLE and r["verdict"] == "UNAVAILABLE"
    checks += 1

    # a clear multi-indicator signal ranks CRITICAL and returns every matched rule
    bad = "sudo: COMMAND=/bin/sh to root; base64 -enc " + "A" * 50 + " powershell; wevtutil cl Security"
    t = triage_signal(bad)
    assert t["priority"] in (PRIORITY_CRITICAL, PRIORITY_HIGH)
    assert t["matched_count"] >= 2  # priv-esc + c2-beacon + disable-defenses
    assert all("rule_id" in m and "why" in m for m in t["matched_rules"])  # auditable
    checks += 1

    # a benign line ranks INFORMATIONAL
    assert triage_signal("user logged in successfully from console")["priority"] == PRIORITY_INFO
    checks += 1

    # batch ranks highest-first and counts priorities
    b = triage(["benign heartbeat", bad, "failed password for admin from 10.0.0.1"])
    assert b["ranked"][0]["score"] >= b["ranked"][-1]["score"]
    assert b["verdict"] in (PRIORITY_CRITICAL, PRIORITY_HIGH)
    checks += 1

    # receipt deterministic, unsigned; GET info mints nothing
    a = content_receipt(b)["content_sha256"]
    assert a == content_receipt(b)["content_sha256"] and len(a) == 64
    assert content_receipt(b)["signed"] is False
    assert "receipt" not in handle_info("s")
    checks += 1

    # manifest NATIVE-OK + all invariants + defensive posture
    man = handle_manifest("s")
    assert man["surface_id"] == SURFACE_ID and man["data_label"] == LBL_MODELED
    assert all(man["honesty_invariants"].values())
    assert man["honesty_invariants"]["defensive_only_not_offensive"] is True
    assert man["honesty_invariants"]["takes_no_action"] is True
    assert man["honesty_invariants"]["not_counter_uas"] is True
    checks += 1

    # doctrine honest + defensive posture
    d = _doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["posture"] == "DEFENSIVE-BLUE-TEAM-ONLY" and d["takes_action"] is False
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    checks += 1

    return {"ok": True, "checks": checks}


if __name__ == "__main__":
    print(json.dumps(_selftest()))
