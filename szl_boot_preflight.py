# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749 declarations · 163 sorries · 14 unique axioms
"""szl_boot_preflight — collision-proof, fail-LOUD boot resilience (Wave R Dev 1).

Why this exists
---------------
On 2026-07-08 the live a11oy HF Space went **down** with
``stage=CONFIG_ERROR, HTTP 503, errorMessage="Collision on variables and secrets
names."`` — a HF Space *Settings* fault (a repo VARIABLE and a SECRET share the
same name). Only the founder can fix the Settings; devs cannot touch Space
secrets. This module makes the **code** resilient so this *class* of failure can
never again silently take the flagship down, and so the Space self-reports what
it needs.

What it does (ADDITIVE, GUARDED — never crashes, never prints a secret VALUE)
-----------------------------------------------------------------------------
* Holds the canonical registry of every env name the app reads that matters at
  boot, each tagged ``secret`` vs ``variable`` (the exact axis HF forbids from
  colliding) with purpose / required-vs-optional / honest default.
* ``preflight_report()`` — on boot, returns which expected names are PRESENT vs
  ABSENT (names only, never values) so a stale/renamed secret is self-evident.
* ``readiness()`` — per-subsystem honest label in {LIVE, DEGRADED, UNAVAILABLE}.
  A missing OPTIONAL secret DEGRADES that subsystem; it never crashes the box.
  There are **no** hard-required secrets: the estate boots in honest DEGRADED
  mode on a totally empty env, exactly as doctrine requires (a truthful DEGRADED
  beats a fake green — and beats a 503).
* ``collision_names()`` — the set of names that MUST be configured as either a
  secret OR a variable, never both. Documented in ``docs/RUNTIME_ENV.md``.

Pure stdlib. No network. No import side-effects beyond ``os``/``sys``.
"""
import os
import sys

DOCTRINE = "v11"

# --- honest readiness labels ------------------------------------------------
LIVE = "LIVE"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"

SECRET = "secret"
VARIABLE = "variable"


class EnvSpec:
    """One canonical env name the app reads. `kind` is the HF axis (secret vs
    variable) that must NEVER collide. `required` means the SUBSYSTEM is
    UNAVAILABLE without it — it never means "crash the process"."""

    __slots__ = ("name", "kind", "required", "subsystem", "purpose", "default")

    def __init__(self, name, kind, subsystem, purpose,
                 required=False, default=None):
        self.name = name
        self.kind = kind
        self.required = required
        self.subsystem = subsystem
        self.purpose = purpose
        self.default = default

    def as_dict(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "required": self.required,
            "subsystem": self.subsystem,
            "purpose": self.purpose,
            "honest_default": self.default,
        }


# ---------------------------------------------------------------------------
# CANONICAL REGISTRY — the single source of truth (docs/RUNTIME_ENV.md mirrors
# this). Grouped by subsystem. `kind` decides where the founder configures it in
# HF Space Settings: SECRET => "Secrets" tab, VARIABLE => "Variables" tab. A name
# must appear in exactly ONE tab (that is the collision rule).
# ---------------------------------------------------------------------------
_REGISTRY = [
    # ---- core / runtime (variables) ----
    EnvSpec("PORT", VARIABLE, "core", "HTTP listen port (HF injects 7860).",
            required=False, default="7860"),
    EnvSpec("SPACE_COMMIT_SHA", VARIABLE, "core",
            "HF Space commit sha, surfaced at /healthz for drift detection.",
            default="(unset)"),
    EnvSpec("SZL_GIT_SHA", VARIABLE, "core",
            "Deployed GitHub commit sha (build-arg / Space variable).",
            default="unknown"),
    EnvSpec("SZL_BUILD_TIME", VARIABLE, "core", "Image build timestamp.",
            default="unknown"),
    EnvSpec("A11OY_CORS_EXTRA_ORIGINS", VARIABLE, "core",
            "Comma-list of extra CORS origins (additive to the allowlist).",
            default="(none)"),

    # ---- brain / LLM providers (SECRETS — API credentials) ----
    EnvSpec("ANTHROPIC_API_KEY", SECRET, "brain",
            "Anthropic Opus flagship key for the v3 Brain router.",
            required=False, default=None),
    EnvSpec("OPENAI_API_KEY", SECRET, "brain", "OpenAI voter/provider key.",
            default=None),
    EnvSpec("GROQ_API_KEY", SECRET, "brain", "Groq voter/provider key.",
            default=None),
    EnvSpec("OPENROUTER_API_KEY", SECRET, "brain",
            "OpenRouter voter/provider key.", default=None),
    EnvSpec("GEMINI_API_KEY", SECRET, "brain", "Google Gemini voter key.",
            default=None),
    EnvSpec("MISTRAL_API_KEY", SECRET, "brain", "Mistral voter key.",
            default=None),
    EnvSpec("DEEPSEEK_API_KEY", SECRET, "brain", "DeepSeek voter key.",
            default=None),
    EnvSpec("TOGETHER_API_KEY", SECRET, "brain", "Together.ai voter key.",
            default=None),
    EnvSpec("VLLM_API_KEY", SECRET, "brain", "Auth for a private vLLM endpoint.",
            default=None),
    # brain routing (VARIABLES — endpoints / model names, NOT secret)
    EnvSpec("A11OY_MODEL_BASE_URL", VARIABLE, "brain",
            "Base URL for the hosted model router.", default=None),
    EnvSpec("A11OY_BRAIN_URL", VARIABLE, "brain",
            "Central Brain hub pulse URL (falls back to shipped organs).",
            default=None),
    EnvSpec("A11OY_LOCAL_MODEL", VARIABLE, "brain",
            "Local model identifier for the sovereign path.", default=None),
    EnvSpec("HF_ROUTER_BASE", VARIABLE, "brain",
            "HF Inference router base URL.", default=None),

    # ---- HuggingFace Hub / corpus (SECRET token + VARIABLE routing) ----
    EnvSpec("HF_TOKEN", SECRET, "hf-hub",
            "HuggingFace Hub token (corpus bucket read/write, router proxy).",
            required=False, default=None),
    EnvSpec("HF_ROUTER_TOKEN", SECRET, "hf-hub",
            "Token for the HF Inference router (voter proxy).", default=None),

    # ---- provenance / signing (SECRET private key; PUBLIC material is a var) ----
    EnvSpec("SZL_COSIGN_PRIVATE_PEM", SECRET, "signing",
            "DSSE/cosign ECDSA-P256 PRIVATE key PEM. Absent => UNSIGNED-LOCAL "
            "receipts (honest), never a fabricated signature.",
            required=False, default=None),
    EnvSpec("COSIGN_PUBLIC_PEM", VARIABLE, "signing",
            "DSSE cosign PUBLIC key PEM (safe to expose; verification only).",
            default=None),
    EnvSpec("COSIGN_KEYID", VARIABLE, "signing",
            "Key identifier surfaced in verify receipts (non-secret).",
            default=None),

    # ---- governed compute authority (store only the bearer SHA-256) ----
    EnvSpec("A11OY_COMPUTE_TOKEN_SHA256", SECRET, "compute",
            "SHA-256 of the bearer accepted by stateful Yupaq compute routes. "
            "Absent => submit/readback routes fail closed.",
            required=False, default=None),

    # ---- energy / GPU lungs (SECRET token + VARIABLE addressing/flags) ----
    EnvSpec("A11OY_GPU_TOKEN", SECRET, "energy",
            "Bearer token for the sovereign GPU node(s). Absent => joules are "
            "honest SAMPLE, never MEASURED.", required=False, default=None),
    EnvSpec("A11OY_OMEN_BASE_URL", VARIABLE, "energy",
            "OMEN GPU-lung base URL (energy MEASURED path).", default=None),
    EnvSpec("A11OY_OMEN_STANDBY", VARIABLE, "energy",
            "1 => OMEN standby (default); 0 => live lung.", default="1"),
    EnvSpec("A11OY_ENERGY_OMEN_ENABLED", VARIABLE, "energy",
            "Runbook alias: 1 flips OMEN live when STANDBY unset.", default="0"),
    EnvSpec("A11OY_JOULE_METER_URL", VARIABLE, "energy",
            "URL of a joule meter (energy MEASURED path).", default=None),
    EnvSpec("SZL_ENERGY_LEDGER_PATH", VARIABLE, "energy",
            "Persistent path for the energy/receipt ledger; ephemeral if unset.",
            default=None),

    # ---- data feeds (SECRET API keys) ----
    EnvSpec("NVD_API_KEY", SECRET, "feeds",
            "NIST NVD CVE feed key (higher rate limit).", default=None),
    EnvSpec("GITHUB_TOKEN", SECRET, "feeds",
            "GitHub API token for live repo/citation feeds.", default=None),
    EnvSpec("SZL_FRED_API_KEY", SECRET, "feeds", "FRED economic-data key.",
            default=None),
    EnvSpec("POLYGON_API_KEY", SECRET, "feeds", "Polygon markets key.",
            default=None),
    EnvSpec("ELECTRICITY_MAPS_API_KEY", SECRET, "feeds",
            "Electricity Maps grid-carbon key (carbon stays ROADMAP w/o it).",
            default=None),

    # ---- billing (SECRET key + VARIABLE pricing) ----
    EnvSpec("STRIPE_API_KEY", SECRET, "billing",
            "Stripe secret key for joule billing.", default=None),
    EnvSpec("STRIPE_PRICE_PER_KWH_CENTS", VARIABLE, "billing",
            "Pricing config in cents/kWh (non-secret).", default=None),
]

_BY_NAME = {s.name: s for s in _REGISTRY}
_SUBSYSTEMS = sorted({s.subsystem for s in _REGISTRY})


def registry():
    """Return the canonical registry as a list of plain dicts (no values)."""
    return [s.as_dict() for s in _REGISTRY]


def subsystems():
    return list(_SUBSYSTEMS)


def collision_names():
    """Names that MUST be configured as EITHER a secret OR a variable in HF
    Space Settings — never both. This is the exact axis whose duplication caused
    the outage. Every registered name qualifies (each has one canonical kind)."""
    return sorted(_BY_NAME.keys())


def _present(env, name):
    """A name is PRESENT when set to a non-empty (stripped) string."""
    v = env.get(name)
    return v is not None and str(v).strip() != ""


def preflight_report(env=None):
    """Honest present/absent report by NAME ONLY — never a secret VALUE.

    Guarded: returns a well-formed dict even on unexpected input; never raises.
    """
    if env is None:
        env = os.environ
    present, absent = [], []
    try:
        for spec in _REGISTRY:
            (present if _present(env, spec.name) else absent).append(spec.name)
    except Exception as exc:  # pragma: no cover — never let preflight crash boot
        return {
            "doctrine": DOCTRINE,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "present": [], "absent": [], "counts": {},
        }
    return {
        "doctrine": DOCTRINE,
        "ok": True,
        "present": sorted(present),
        "absent": sorted(absent),
        "counts": {
            "present": len(present),
            "absent": len(absent),
            "total": len(_REGISTRY),
        },
        # never both — repeated here so an operator sees the rule at a glance
        "collision_rule": "each name is either a HF secret OR a HF variable, "
                          "never both (the 2026-07-08 CONFIG_ERROR cause)",
    }


def _subsystem_label(env, subsystem):
    """Per-subsystem honest readiness. Absent optional secret => DEGRADED;
    absent required (subsystem-critical) => UNAVAILABLE; else LIVE."""
    specs = [s for s in _REGISTRY if s.subsystem == subsystem]
    missing_required = [s.name for s in specs
                        if s.required and not _present(env, s.name)]
    # a subsystem's "credentials" are its secrets; missing ones degrade it
    missing_secrets = [s.name for s in specs
                       if s.kind == SECRET and not _present(env, s.name)]
    if missing_required:
        label = UNAVAILABLE
    elif missing_secrets:
        label = DEGRADED
    else:
        label = LIVE
    return {
        "subsystem": subsystem,
        "label": label,
        "missing_required": sorted(missing_required),
        "missing_secrets": sorted(missing_secrets),
    }


def readiness(env=None):
    """Per-subsystem readiness rollup + honest overall label. NEVER raises.

    overall = UNAVAILABLE if any subsystem is UNAVAILABLE (a hard-required name
    is missing — by design there are none, so a stock env is DEGRADED not
    UNAVAILABLE), else DEGRADED if any subsystem is DEGRADED, else LIVE.
    """
    if env is None:
        env = os.environ
    try:
        subs = [_subsystem_label(env, name) for name in _SUBSYSTEMS]
    except Exception as exc:  # pragma: no cover — honest UNAVAILABLE, no crash
        return {
            "doctrine": DOCTRINE,
            "overall": UNAVAILABLE,
            "error": f"{type(exc).__name__}: {exc}",
            "subsystems": [],
        }
    labels = {s["label"] for s in subs}
    if UNAVAILABLE in labels:
        overall = UNAVAILABLE
    elif DEGRADED in labels:
        overall = DEGRADED
    else:
        overall = LIVE
    return {
        "doctrine": DOCTRINE,
        "overall": overall,
        "subsystems": subs,
    }


def run_preflight(env=None, stream=None):
    """Boot-time entry: log an honest present/absent report + readiness to
    stderr (NAMES ONLY) and return the combined dict. Fully guarded — a failure
    here logs and returns an honest DEGRADED marker, it NEVER propagates and so
    can never 503 the estate on a missing/renamed secret."""
    if stream is None:
        stream = sys.stderr
    try:
        report = preflight_report(env)
        ready = readiness(env)
        absent = report.get("absent", [])
        print(
            f"[a11oy] PREFLIGHT doctrine={DOCTRINE} overall={ready['overall']} "
            f"present={report['counts'].get('present')}/"
            f"{report['counts'].get('total')} absent={len(absent)}",
            file=stream,
        )
        if absent:
            # names only — never a value
            print(f"[a11oy] PREFLIGHT absent env names: {', '.join(absent)}",
                  file=stream)
        for s in ready["subsystems"]:
            if s["label"] != LIVE:
                miss = s["missing_secrets"] or s["missing_required"]
                print(f"[a11oy] PREFLIGHT subsystem {s['subsystem']}="
                      f"{s['label']} (missing: {', '.join(miss) or 'none'})",
                      file=stream)
        return {"report": report, "readiness": ready}
    except Exception as exc:  # pragma: no cover — boot must never die here
        try:
            print(f"[a11oy] PREFLIGHT guarded-degrade: {type(exc).__name__}: "
                  f"{exc}", file=stream)
        except Exception:
            pass
        return {
            "report": {"ok": False, "error": str(exc)},
            "readiness": {"overall": DEGRADED, "subsystems": []},
        }


if __name__ == "__main__":
    import json
    out = run_preflight()
    print(json.dumps(out, indent=2, sort_keys=True))
