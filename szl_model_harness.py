# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — a11oy Governed Model Harness
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_model_harness — a GOVERNED behavior-transfer harness for the SZL ecosystem.

It makes "run model X with behavior profile Y" a first-class, governed, receipted
operation. This is SZL's doctrine-honest generalization of the community
"clone Fable 5 into Opus 4.8" technique: load a model's behavior/instruction layer
into another model to transfer DISPOSITION (autonomy, grounding, voice) — never
capability. The harness plugs into the EXISTING szl_llm_registry.py: it reuses
that module's Λ-gate (_lambda_gm), tier selection, model roster, and the shared
/llm/forum receipt substrate.

WHAT TRANSFERS (honest ceiling — see research Part 1.3):
  * Transfers (instruction layer): identity, autonomy defaults, tool-use posture,
    grounding/verification habits, response voice, effort configuration.
  * Does NOT transfer (weights-bound): raw reasoning depth, capability ceiling.
  * The correct claim, encoded in every receipt: a profile changes MODELED
    behavior; it does NOT raise the model's LIVE capability.

DESIGN (mirrors szl_llm_registry, adds the governance layer no leak-harness ships):
  1. Profile = JSON manifest in harness_profiles/*.json:
       {id, name, version, target_models[], provenance{author,source,license,
        sha256,not_verbatim_of}, system_prompt_ref (path/env — NEVER inline
        leaked text), tags, honesty_label, capability_claim}.
     Prompt BODIES live in harness_profiles/bodies/*.md (SZL's OWN re-expressed
     text) and are referenced by path/env — never inlined into the manifest,
     never leaked third-party text.
  2. apply flow (POST /harness/apply): resolve+sha256 body -> Λ-gate (reuse
     szl_llm_registry._lambda_gm + the exact /llm/route tier logic) -> inject the
     profile's system layer into the target-model call -> honest MODELED/UNAVAILABLE
     if no API key wired (no fabrication) -> emit an ECDSA-P256 DSSE SIGNED receipt
     (szl.harness_apply.receipt/v1) -> ingest into /llm/forum.

ENDPOINTS (ADDITIVE — registered BEFORE the Node proxy + SPA catch-all, mirroring
szl_llm_registry). Guarded by serve.py try/except so a failure never dark-404s
existing routes:
  GET  /api/a11oy/v1/harness/profiles          — roster + provenance + availability
  GET  /api/a11oy/v1/harness/profiles/{id}      — one profile: metadata + sha256 +
                                                  availability ONLY (never the body)
  POST /api/a11oy/v1/harness/apply              — the governed apply flow above

HONESTY (Doctrine v11 LOCKED):
  * No API key wired in the HF Space -> apply returns an honest MODELED response
    describing WHAT WOULD RUN (mirrors szl_llm_registry's [HONEST STUB] pattern).
  * Λ arithmetic, tier selection, sha256 provenance, DSSE signing, forum ingest
    are ALL REAL. Λ = Conjecture 1 (advisory, NEVER "green", never a theorem).
  * Real ECDSA-P256 DSSE signature in-Space (via szl_dsse); honest UNSIGNED
    marker locally when no cosign key secret is present — no fabricated signature.
  * Profile bodies are SZL's OWN re-expression; no third-party leaked prompt is
    ever stored, inlined, or shipped. Every manifest carries `not_verbatim_of`.

Adds NOTHING to the locked-8. Doctrine v11 LOCKED — 749/14/163 — c7c0ba17.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
_LAMBDA_FLOOR = 0.90
_CONJECTURE_NOTE = "Λ = Conjecture 1 — NOT a theorem. Advisory, never 'green'."

# ─────────────────────────────────────────────────────────────────────────────
# Profile store — JSON manifests in harness_profiles/, bodies by path/env.
# ─────────────────────────────────────────────────────────────────────────────

def _profiles_dir() -> Path:
    """On-disk root of the profile manifests. In-image /app/harness_profiles;
    in a dev checkout <repo>/harness_profiles. Resolve from this file, fall back."""
    here = Path(__file__).resolve().parent / "harness_profiles"
    if here.is_dir():
        return here.resolve()
    return Path("/app/harness_profiles").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_manifests() -> list[dict[str, Any]]:
    """Load every *.json manifest in harness_profiles/ (never the bodies/ dir).
    Never raises into the request path — a bad manifest is skipped with a note."""
    d = _profiles_dir()
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(m, dict) and m.get("id"):
                m["_manifest_file"] = f.name
                out.append(m)
        except Exception:  # skip malformed manifest, keep the rest
            continue
    return out


def _resolve_body(profile: dict[str, Any]) -> dict[str, Any]:
    """Resolve a profile's system-prompt BODY via env override -> default path.

    Returns {available, source, sha256, length, honest_note}. The raw body text
    is returned under `_body` for the apply path (injected into the model call);
    it is NEVER surfaced by the metadata endpoints. NEVER raises.
    """
    ref = profile.get("system_prompt_ref") or {}
    env_name = ref.get("env") or ref.get("value")
    default_path = ref.get("default_body_path")

    # 1) env override (operator supplies their own/licensed body inline OR a path)
    if env_name:
        env_val = os.environ.get(env_name, "").strip()
        if env_val:
            # env value may be a filesystem path OR the literal body text
            p = Path(env_val)
            if len(env_val) < 512 and p.is_file():
                try:
                    body = p.read_text(encoding="utf-8")
                    return _body_result(body, f"env:{env_name} -> path:{env_val}")
                except Exception:
                    pass
            # else treat the env value as the literal prompt body
            return _body_result(env_val, f"env:{env_name} (inline)")

    # 2) shipped default body path (SZL's OWN re-expressed text — works OOTB)
    if default_path:
        p = _profiles_dir().parent / default_path if not os.path.isabs(default_path) else Path(default_path)
        # normalize: default_body_path is repo-root-relative "harness_profiles/bodies/..."
        cand = (_profiles_dir().parent / default_path).resolve()
        if cand.is_file():
            try:
                body = cand.read_text(encoding="utf-8")
                return _body_result(body, f"default_body_path:{default_path}")
            except Exception:
                pass
        # fallback: try relative to profiles dir itself
        alt = (_profiles_dir() / Path(default_path).name).resolve()
        if alt.is_file():
            try:
                body = alt.read_text(encoding="utf-8")
                return _body_result(body, f"default_body_path:{alt.name}")
            except Exception:
                pass

    return {
        "available": False,
        "source": None,
        "sha256": None,
        "length": 0,
        "honest_note": "UNAVAILABLE — no env override set and no default body resolved on disk; "
                       "no body fabricated.",
        "_body": None,
    }


def _body_result(body: str, source: str) -> dict[str, Any]:
    raw = body.encode("utf-8")
    return {
        "available": True,
        "source": source,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "length": len(body),
        "honest_note": "resolved (body content NEVER surfaced by metadata endpoints — sha256 only)",
        "_body": body,
    }


def _public_view(profile: dict[str, Any], body_meta: dict[str, Any]) -> dict[str, Any]:
    """Public metadata view of a profile — provenance + availability + sha256 ONLY.
    NEVER includes the resolved body text. Confirms manifest sha256 integrity."""
    prov = dict(profile.get("provenance") or {})
    manifest_sha = prov.get("sha256")
    resolved_sha = body_meta.get("sha256")
    integrity = "unknown"
    if resolved_sha and manifest_sha:
        integrity = "match" if resolved_sha == manifest_sha else "MISMATCH"
    elif not body_meta.get("available"):
        integrity = "unavailable"
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "version": profile.get("version"),
        "target_models": profile.get("target_models", []),
        "tags": profile.get("tags", []),
        "honesty_label": profile.get("honesty_label", "MODELED"),
        "capability_claim": profile.get("capability_claim",
                                        "transfers disposition only; does NOT raise capability ceiling"),
        "lambda_posture": profile.get("lambda_posture", "advisory (Conjecture 1); never 'green'"),
        "provenance": {
            "author": prov.get("author"),
            "source": prov.get("source"),
            "inspiration_urls": prov.get("inspiration_urls", []),
            "license": prov.get("license"),
            "sha256_manifest": manifest_sha,
            "sha256_resolved": resolved_sha,
            "sha256_integrity": integrity,
            "not_verbatim_of": prov.get("not_verbatim_of"),
        },
        "system_prompt_ref": {  # reference ONLY — never the body
            "type": (profile.get("system_prompt_ref") or {}).get("type"),
            "env": (profile.get("system_prompt_ref") or {}).get("env"),
            "default_body_path": (profile.get("system_prompt_ref") or {}).get("default_body_path"),
        },
        "availability": {
            "available": body_meta.get("available", False),
            "source": body_meta.get("source"),
            "length": body_meta.get("length", 0),
            "honest_note": body_meta.get("honest_note"),
        },
        "manifest_file": profile.get("_manifest_file"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Λ-gate — REUSE szl_llm_registry's gate. The harness does NOT invent a new gate;
# it composes with the one that exists (research Part 4.2).
# ─────────────────────────────────────────────────────────────────────────────

def _reg():
    """Import the existing LLM registry (the gate + roster + forum live there)."""
    import szl_llm_registry as _r
    return _r


# Wave M (Dev 2): the shared sovereign-flywheel bridge. Routes an explicit
# sovereign request through Dev-1's registry backend (sovereign_local); degrades
# to honest MODELED/UNAVAILABLE when the local Tower endpoint is unreachable.
try:
    import szl_sovereign_flywheel as _sov  # noqa: F401
    _SOV_OK = True
except Exception:  # pragma: no cover — bridge missing → sovereign option simply off
    _sov = None  # type: ignore
    _SOV_OK = False


def _lambda_gm(axes: list[float]) -> float:
    """Reuse szl_llm_registry._lambda_gm; local geometric-mean fallback if the
    registry import fails (never raises into the request path)."""
    try:
        return _reg()._lambda_gm(axes)
    except Exception:
        import math
        if not axes:
            return 0.5
        c = [max(1e-9, min(1.0, float(v))) for v in axes]
        return math.exp(sum(math.log(v) for v in c) / len(c))


def _select_tier(lam: float, task_hint: str, max_tier: int) -> tuple[int, str]:
    """Tier selection — byte-faithful to szl_llm_registry.llm_route so the harness
    routes through EXACTLY the same gate as /llm/route."""
    if lam >= 0.90:
        rank, reason = 0, f"Λ={lam:.4f} ≥ 0.90 → high-trust fast tier"
    elif lam >= 0.75:
        rank, reason = 2, f"Λ={lam:.4f} ∈ [0.75,0.90) → mid-trust structured tier"
    else:
        rank, reason = 3, f"Λ={lam:.4f} < 0.75 → premium tier + extra gates"
    hint_floor = {"math": 2, "research": 1, "orchestration": 3, "diligence": 4}.get(task_hint)
    if hint_floor is not None and hint_floor > rank:
        rank = hint_floor
        reason += f"; task_hint='{task_hint}' raised floor to tier {hint_floor}"
    if rank > max_tier:
        rank = max_tier
        reason += f"; capped at max_tier={max_tier}"
    return rank, reason


def _model_by_id(model_id: str) -> dict[str, Any] | None:
    try:
        return _reg()._MODEL_BY_ID.get(model_id)
    except Exception:
        return None


def _api_key_wired(env_var: str) -> bool:
    try:
        return _reg()._api_key_wired(env_var)
    except Exception:
        val = os.environ.get(env_var, "").strip()
        return bool(val and val != "NOT_SET" and len(val) > 8)


def _model_weight_sha() -> tuple[str, str]:
    try:
        import szl_rag as _rag
        mw = _rag.get_model_weight_sha256()
        return mw.get("sha256", "not_computed"), mw.get("method", "szl_rag")
    except Exception:
        return "not_computed", "registry_fallback"


# ─────────────────────────────────────────────────────────────────────────────
# DSSE signing — REAL ECDSA-P256 in-Space via szl_dsse; honest UNSIGNED locally.
# ─────────────────────────────────────────────────────────────────────────────

HARNESS_PAYLOAD_TYPE = "application/vnd.szl.harness+json"


def _sign_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Sign the harness receipt with the shared szl_dsse ECDSA-P256 DSSE signer.
    Returns a signature block. Honest UNSIGNED marker when no cosign key secret
    is present — NEVER fabricates a signature."""
    try:
        import szl_dsse
        env = szl_dsse.sign_payload(receipt, HARNESS_PAYLOAD_TYPE)
        signed = bool(env.get("signed"))
        sig_val = None
        if env.get("signatures"):
            sig_val = env["signatures"][0].get("sig")
        return {
            "alg": "ECDSA-P256",
            "envelope": "DSSE",
            "signed": signed,
            "value": sig_val if signed else "UNSIGNED-LOCAL",
            "keyid": (env.get("signatures") or [{}])[0].get("keyid") if signed else None,
            "payloadType": env.get("payloadType"),
            "pae_sha256": env.get("_pae_sha256"),
            "honesty": env.get("honesty"),
            "verify_key_url": env.get("verify_key_url"),
            "dsse": env,
        }
    except Exception as e:  # szl_dsse unavailable -> honest UNSIGNED, no fabrication
        return {
            "alg": "ECDSA-P256",
            "envelope": "DSSE",
            "signed": False,
            "value": "UNSIGNED-LOCAL",
            "honesty": f"UNSIGNED — DSSE signer unavailable ({e!r}); no signature fabricated.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Forum ingest — write the harness receipt into the SHARED szl_llm_registry forum
# so harness applications appear alongside routing events (research Part 4.2 §6).
# ─────────────────────────────────────────────────────────────────────────────

def _forum_ingest(receipt: dict[str, Any], prompt_preview: str = "") -> dict[str, Any]:
    """Append the receipt to the shared /llm/forum ring. Uses the registry's own
    _forum_append so it lands in the same substrate the router writes to."""
    entry = {**receipt, "source": "a11oy", "event": "harness_apply",
             "prompt_preview": prompt_preview[:80] if prompt_preview else ""}
    try:
        _reg()._forum_append(entry)
        return {"ingested": True, "forum": "/api/a11oy/v1/llm/forum"}
    except Exception as e:
        return {"ingested": False, "error": f"{e!r}",
                "honest_note": "forum ingest failed; receipt still returned to caller."}


# Boot note into the shared forum (best-effort, honest).
def _seed_forum() -> None:
    try:
        _reg()._forum_append({
            "ts": _now(), "source": "a11oy", "event": "harness_boot",
            "profile_count": len(_load_manifests()), "doctrine": DOCTRINE,
            "note": "szl_model_harness initialised — governed behavior-transfer harness online",
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# apply() — the IMPORTABLE governed apply core (Wave G).
#
# LEADER FASHION, GOVERNED: LangGraph attaches a persona via a runtime `context`
# (system_message) selected per node; OpenAI Swarm converts the active Agent's
# `instructions` straight into the step's `system` message and switches it on a
# handoff; CrewAI concatenates role/goal/backstory into the system prompt;
# AutoGen sets each agent's `system_message`; Claude Code subagents put the
# Markdown body into the subagent system prompt; MCP exposes named prompts a
# client fetches (prompts/get) and injects. ALL of them = "attach a NAMED,
# selectable instruction/system layer to a step; switch it by choosing another."
#
# Our GOVERNED version returns that same selectable system layer PLUS what the
# leaders don't ship: a resolved+sha256'd provenance body, a Λ-gate (Conjecture
# 1, advisory — never green), an ECDSA-P256 DSSE-signed receipt, and honest
# LIVE/MODELED/UNSIGNED labels. This is the single source of truth the HTTP
# /harness/apply endpoint AND the /code run-loop step both call, so a profile
# swap is receipted identically wherever it happens.
# ─────────────────────────────────────────────────────────────────────────────

def apply(profile_id: str, model_id: str = "", prompt: str = "",
          axis_scores: list[float] | None = None, max_tier: int = 4,
          task_hint: str = "", ns: str = "a11oy",
          forum: bool = True) -> dict[str, Any]:
    """Governed behavior-profile apply — IMPORTABLE core (no FastAPI request).

    Resolves + sha256's the profile body, runs the EXACT szl_llm_registry Λ-gate
    + tier logic, selects the model, builds and SIGNS the receipt
    (szl.harness_apply.receipt/v1), and (optionally) ingests it into /llm/forum.

    Returns a dict with:
      ok, error?, harness_state (LIVE-KEY / MODELED / UNAVAILABLE / NOT_FOUND),
      system_layer  — the resolved profile body TEXT to inject as the step's
                      system layer (empty string when unavailable; callers
                      inject it, the receipt records sha256 only),
      system_layer_available (bool),
      profile_public (metadata + provenance sha256, NEVER the body),
      model_selected, receipt (signed), forum (ingest status), response.

    NEVER raises into the caller's request path; NEVER fabricates a model output.
    Λ = Conjecture 1 (advisory). Real DSSE in-Space; honest UNSIGNED locally.
    """
    profile_id = str(profile_id or "").strip()
    model_id = str(model_id or "").strip()
    prompt = str(prompt or "")
    axis_scores = axis_scores or [
        0.92, 0.90, 0.95, 0.91, 0.94, 0.90, 0.92, 0.91, 0.93, 0.92, 0.93, 0.90, 0.92
    ]
    max_tier = min(4, max(0, int(max_tier)))
    task_hint = str(task_hint or "").lower()

    manifests = _load_manifests()
    profile = next((x for x in manifests if x.get("id") == profile_id), None)
    if not profile:
        return {
            "ok": False,
            "harness_state": "NOT_FOUND",
            "error": f"profile_id '{profile_id}' not found",
            "known": [x.get("id") for x in manifests],
            "system_layer": "",
            "system_layer_available": False,
            "conjecture_note": _CONJECTURE_NOTE,
        }

    # resolve + hash the body (provenance integrity)
    bm = _resolve_body(profile)
    prov = dict(profile.get("provenance") or {})
    manifest_sha = prov.get("sha256")
    resolved_sha = bm.get("sha256")
    body_available = bm.get("available", False)
    integrity = "unavailable"
    if body_available and manifest_sha and resolved_sha:
        integrity = "match" if resolved_sha == manifest_sha else "MISMATCH"

    # Λ-gate (reuse the existing gate + tier logic exactly)
    lam = _lambda_gm(axis_scores)
    rank, reason = _select_tier(lam, task_hint, max_tier)
    reason += f"; profile={profile_id} v{profile.get('version')}"

    selected = _model_by_id(model_id) if model_id else None
    if selected is None:
        try:
            roster = _reg().MODEL_REGISTRY
            selected = next(
                (mm for mm in roster if mm.get("tier") == rank
                 and mm.get("tier_name") not in ("sovereign",)),
                roster[0])
        except Exception:
            selected = None
        if model_id:
            reason += f"; model_id '{model_id}' unknown → fell back to tier-{rank} model"
    chosen_model_id = (selected or {}).get("model_id", model_id or "unknown")
    model_display = (selected or {}).get("display_name", chosen_model_id)
    api_env = (selected or {}).get("api_env_var", "")
    api_key_wired = _api_key_wired(api_env) if api_env else False

    mw_sha, mw_method = _model_weight_sha()

    receipt: dict[str, Any] = {
        "schema": "szl.harness_apply.receipt/v1",
        "ts": _now(),
        "hub": ns,
        "profile": {
            "id": profile.get("id"),
            "version": profile.get("version"),
            "name": profile.get("name"),
            "sha256": resolved_sha,
            "sha256_manifest": manifest_sha,
            "sha256_integrity": integrity,
        },
        "provenance": {
            "author": prov.get("author"),
            "source": prov.get("source"),
            "license": prov.get("license"),
            "not_verbatim_of": prov.get("not_verbatim_of"),
            "inspiration_urls": prov.get("inspiration_urls", []),
        },
        "model_id": chosen_model_id,
        "model_display": model_display,
        "lambda": round(lam, 6),
        "lambda_floor": _LAMBDA_FLOOR,
        "axis_scores": axis_scores,
        "tier_selected": rank,
        "task_hint": task_hint,
        "reason": reason,
        "api_key_wired": api_key_wired,
        "system_layer_injected": bool(body_available),
        "honesty_label": profile.get("honesty_label", "MODELED"),
        "capability_claim": profile.get("capability_claim",
                                        "disposition only; capability ceiling unchanged"),
        "model_weight_sha256": mw_sha,
        "model_weight_method": mw_method,
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "conjecture_note": _CONJECTURE_NOTE,
    }
    # ── Wave M (Dev 2): SOVEREIGN option ──────────────────────────────────────
    # If the caller asked to run this on SZL's OWN governed model, route the
    # profile-applied prompt through Dev-1's sovereign_local backend. The receipt
    # ALWAYS records the intended sovereign backend; when the Tower is offline we
    # return honest MODELED/UNAVAILABLE and NEVER fabricate a model response.
    sovereign_requested = bool(_SOV_OK and _sov and _sov.is_sovereign(model_id))
    if sovereign_requested:
        # Compose the sovereign prompt: profile body (if resolved) as a system
        # preface + the user prompt. The body TEXT is never surfaced in the
        # receipt (sha256 only) — it is only sent to the local, sovereign node.
        sys_layer = (bm.get("_body") or "") if body_available else ""
        sov_prompt = ((sys_layer + "\n\n") if sys_layer else "") + prompt
        sov = _sov.run_on_sovereign(sov_prompt, requested_model_id=model_id)
        receipt["sovereign"] = _sov.receipt_block(sov)
        receipt["model_id"] = _sov.SOVEREIGN_BACKEND_ID
        receipt["model_display"] = "SZL Sovereign Local (llama3-szl-finetuned-q4)"
        receipt["honesty_label"] = sov.get("state")

    receipt["signature"] = _sign_receipt(receipt)

    if sovereign_requested:
        _st = sov.get("state")
        if _st == "LIVE":
            response_text = (
                "[LIVE · SOVEREIGN] Ran the '" + profile_id + "' behavior profile on "
                "SZL's OWN governed model (sovereign_local, llama3-szl-finetuned-q4) "
                "— REAL generation this request. " + (sov.get("note") or ""))
        elif _st == "MODELED":
            response_text = (
                "[HONEST STUB · MODELED · SOVEREIGN] Would run the '" + profile_id +
                "' profile on SZL's sovereign_local model, but the local Tower node "
                "did not answer live this request. No model output fabricated; the "
                "intended sovereign backend + Λ-gate + provenance sha256 + signature "
                "are REAL. " + (sov.get("note") or ""))
        else:
            response_text = (
                "[UNAVAILABLE · SOVEREIGN] The '" + profile_id + "' profile targeted "
                "SZL's sovereign_local model, but the local endpoint is unreachable "
                "(SZL_LOCAL_LLM_URL unset / Tower offline). No model call attempted; "
                "the intended sovereign backend is recorded in the receipt; no output "
                "fabricated. " + (sov.get("note") or ""))
        harness_state = _st
        model_display = receipt["model_display"]
        chosen_model_id = receipt["model_id"]
    elif not body_available:
        response_text = (
            f"[UNAVAILABLE] Profile '{profile_id}' body could not be resolved on disk "
            f"and no {(profile.get('system_prompt_ref') or {}).get('env')} override is set. "
            "No model call attempted; no output fabricated. The receipt still records what "
            "WOULD run.")
        harness_state = "UNAVAILABLE"
    elif api_key_wired:
        response_text = (
            f"[ROUTING READY] API key present for {model_display}. Profile "
            f"'{profile_id}' v{profile.get('version')} system layer "
            f"({bm.get('length')} chars, sha256={(resolved_sha or '')[:12]}…) would be injected "
            f"as the system field and the prompt forwarded. Behavior transfer is MODELED.")
        harness_state = "READY"
    else:
        response_text = (
            f"[HONEST STUB · MODELED] Would run {model_display} (tier {rank}) with the "
            f"'{profile_id}' behavior profile injected as the system layer "
            f"({bm.get('length')} chars, sha256={(resolved_sha or '')[:12]}…). No API key wired in "
            f"this env — no model output fabricated. Λ={lam:.4f}, tier + receipt + "
            f"provenance sha256 + signature are REAL. Behavior transfer changes MODELED "
            f"disposition only; capability ceiling unchanged.")
        harness_state = "MODELED"

    forum_status = _forum_ingest(receipt, prompt) if forum else {"ingested": False, "skipped": True}

    return {
        "ok": True,
        "harness_state": harness_state,
        "response": response_text,
        "system_layer": (bm.get("_body") or "") if body_available else "",
        "system_layer_available": bool(body_available),
        "profile_public": _public_view(profile, bm),
        "model_selected": {
            "model_id": chosen_model_id,
            "display_name": model_display,
            "tier": rank,
            "api_key_wired": api_key_wired,
        },
        "receipt": receipt,
        "forum": forum_status,
        "doctrine": DOCTRINE,
        "conjecture_note": _CONJECTURE_NOTE,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────

def register(app: FastAPI, ns: str = "a11oy") -> dict:
    """Register the harness endpoints BEFORE the proxy/SPA catch-all (mirror
    szl_llm_registry.register). ADDITIVE; never crashes the app — serve.py wraps
    this in try/except."""
    _seed_forum()

    # ── GET /api/a11oy/v1/harness/profiles ───────────────────────────────────
    @app.get(f"/api/{ns}/v1/harness/profiles")
    async def harness_profiles() -> JSONResponse:
        """Profile roster + provenance + availability. NEVER returns body text."""
        manifests = _load_manifests()
        views = []
        for m in manifests:
            bm = _resolve_body(m)
            views.append(_public_view(m, bm))
        available = [v for v in views if v["availability"]["available"]]
        return JSONResponse({
            "timestamp": _now(),
            "hub": ns,
            "role": "Governed behavior-transfer harness — 'run model X with behavior profile Y', receipted",
            "profile_count": len(views),
            "available_count": len(available),
            "profiles": views,
            "endpoints": {
                "detail": f"/api/{ns}/v1/harness/profiles/{{id}}",
                "apply": f"/api/{ns}/v1/harness/apply",
                "forum": f"/api/{ns}/v1/llm/forum",
                "registry": f"/api/{ns}/v1/llm/registry",
            },
            # Wave M (Dev 2): run this profile on SZL's OWN sovereign local model.
            "run_on_sovereign": {
                "available": bool(_SOV_OK),
                "how": ("POST /harness/apply with model_id='szl-sovereign-local' "
                        "(alias of registry backend 'sovereign_local'). Routes the "
                        "profile-applied prompt through the local Tower via Dev-1's "
                        "registry backend; honest MODELED/UNAVAILABLE when offline."),
                "backend_id": "sovereign_local",
                "model_slug": "llama3-szl-finetuned-q4",
                "provider_provenance": "SZL sovereign (Ollama, local, Doctrine-v11 system prompt)",
            },
            "capability_ceiling": "Behavior transfer is MODELED — changes disposition, NOT capability. "
                                  "Only original weights deliver capability (honest ceiling).",
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "conjecture_note": _CONJECTURE_NOTE,
            "honest_note": "Bodies referenced by path/env — never inlined. No third-party leaked prompt "
                           "is stored or shipped; every profile carries provenance + not_verbatim_of.",
        })

    # ── GET /api/a11oy/v1/harness/profiles/{id} ──────────────────────────────
    @app.get(f"/api/{ns}/v1/harness/profiles/{{profile_id}}")
    async def harness_profile_detail(profile_id: str) -> JSONResponse:
        """One profile — metadata + sha256 + availability ONLY. NEVER the body."""
        manifests = _load_manifests()
        m = next((x for x in manifests if x.get("id") == profile_id), None)
        if not m:
            return JSONResponse(
                {"error": f"profile_id '{profile_id}' not found",
                 "known": [x.get("id") for x in manifests]},
                status_code=404)
        bm = _resolve_body(m)
        return JSONResponse({
            **_public_view(m, bm),
            "timestamp": _now(),
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "conjecture_note": _CONJECTURE_NOTE,
            "honest_note": "This endpoint returns metadata + sha256 + availability only — "
                           "the secret/prompt body is NEVER surfaced.",
        })

    # ── POST /api/a11oy/v1/harness/apply ─────────────────────────────────────
    @app.post(f"/api/{ns}/v1/harness/apply")
    async def harness_apply(request: Request) -> JSONResponse:
        """Apply a behavior profile to a target model, Λ-gated + signed + forumed.

        Body: {"profile_id": "szl-fable", "model_id": "claude_opus_4_8",
               "prompt": "…", "axis_scores": [..], "max_tier": 4, "task_hint": ""}

        Wave M (Dev 2): pass model_id="szl-sovereign-local" (or the registry id
        "sovereign_local") to run this profile on SZL's OWN governed model via
        Dev-1's sovereign backend. When the local Tower endpoint is unreachable
        the apply returns honest MODELED/UNAVAILABLE and the receipt still records
        the intended sovereign backend — no model response is ever fabricated.
        """
        try:
            body = await request.json()
        except Exception:
            body = {}
        # Wave J (Dev 3): honest 400 on a malformed (non-object) body instead of a
        # 500 crash on body.get(...) — closes the silent-degrade/422 class.
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "request body must be a JSON object",
                 "got_type": type(body).__name__},
                status_code=400)

        # Wave G: the endpoint is now a thin shell over the IMPORTABLE apply()
        # core (single source of truth shared with the /code run-loop step). The
        # body text is NEVER surfaced — we drop `system_layer` from the HTTP view.
        res = apply(
            profile_id=body.get("profile_id", ""),
            model_id=body.get("model_id", ""),
            prompt=body.get("prompt", ""),
            axis_scores=body.get("axis_scores"),
            max_tier=int(body.get("max_tier", 4)),
            task_hint=body.get("task_hint", ""),
            ns=ns,
            forum=True,
        )
        if not res.get("ok"):
            return JSONResponse(
                {"error": res.get("error"), "known": res.get("known", [])},
                status_code=404)

        return JSONResponse({
            "response": res["response"],
            "harness_state": res["harness_state"],
            "profile_applied": res["profile_public"],
            "model_selected": res["model_selected"],
            "harness_receipt": res["receipt"],
            "forum": res["forum"],
            "doctrine": DOCTRINE,
            "conjecture_note": _CONJECTURE_NOTE,
        })

    return {
        "module": "szl_model_harness",
        "endpoints": [
            f"GET  /api/{ns}/v1/harness/profiles",
            f"GET  /api/{ns}/v1/harness/profiles/{{id}}",
            f"POST /api/{ns}/v1/harness/apply",
        ],
        "profile_count": len(_load_manifests()),
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
    }


def _selftest() -> None:
    """Offline self-check — no network, no app. Verifies manifests load, bodies
    resolve + hash, integrity matches, Λ-gate composes, receipts sign (UNSIGNED
    locally is expected)."""
    manifests = _load_manifests()
    assert len(manifests) >= 3, f"expected >=3 profiles, got {len(manifests)}"
    ids = {m["id"] for m in manifests}
    for want in ("szl-fable", "szl-governed-analyst", "szl-honest-operator"):
        assert want in ids, f"missing shipped profile: {want}"
    for m in manifests:
        bm = _resolve_body(m)
        assert bm["available"], f"body not resolved for {m['id']}"
        assert bm["sha256"], f"no sha256 for {m['id']}"
        manifest_sha = (m.get("provenance") or {}).get("sha256")
        if manifest_sha:
            assert bm["sha256"] == manifest_sha, (
                f"sha256 MISMATCH for {m['id']}: manifest={manifest_sha} resolved={bm['sha256']}")
        # bodies must not be inlined in the manifest
        assert "system_prompt" not in m, f"{m['id']} inlines a prompt body — forbidden"
    # Λ-gate composes
    lam = _lambda_gm([0.92] * 13)
    assert 0.0 < lam <= 1.0
    rank, _r = _select_tier(lam, "", 4)
    assert rank in (0, 2, 3)
    # receipt signs (UNSIGNED locally is the honest expected state)
    sig = _sign_receipt({"schema": "szl.harness_apply.receipt/v1", "ts": _now()})
    assert sig["alg"] == "ECDSA-P256" and sig["envelope"] == "DSSE"
    # env override path works (operator swap for the fable body)
    prof = next(m for m in manifests if m["id"] == "szl-fable")
    os.environ["SZL_HARNESS_FABLE_PROMPT"] = "OPERATOR OVERRIDE BODY — test."
    ov = _resolve_body(prof)
    assert ov["available"] and "inline" in (ov["source"] or ""), "env override did not take effect"
    del os.environ["SZL_HARNESS_FABLE_PROMPT"]
    print(f"szl_model_harness: ALL OK ({len(manifests)} profiles, bodies hashed + integrity-checked, "
          f"Λ-gate composes, DSSE signs, env override works). Signature signed={sig['signed']} "
          f"(UNSIGNED locally is expected).")


if __name__ == "__main__":
    _selftest()
