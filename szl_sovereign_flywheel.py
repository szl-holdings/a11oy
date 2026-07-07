# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — a11oy Sovereign Flywheel bridge
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_sovereign_flywheel — the single call path that lets the GOVERNED FLYWHEEL
(harness /harness/apply, eval-arena /eval/run, agent-loop /agentloop/run, RAG
/rag/query) run on SZL's OWN sovereign local model.

Wave M, Dev 2. This module DOES NOT re-implement the sovereign backend — it is a
thin, guarded ADAPTER over the first-class `sovereign_local` backend that Dev 1
registered in `szl_llm_registry.py` (model tag `llama3-szl-finetuned-q4`, targets
`SZL_LOCAL_LLM_URL`, provider provenance "SZL sovereign (Ollama, local,
Doctrine-v11 system prompt)"). Every flywheel flow imports THIS module and calls
`run_on_sovereign(...)`, so the whole loop routes through exactly ONE code path to
Dev-1's registry functions (`sovereign_probe` / `sovereign_generate`).

DEPENDENCY (Wave M coordination): the routed backend `sovereign_local` lives in
szl_llm_registry.py. As of Wave M it is present on main (PR #791, merged). If a
future refactor removes those registry helpers this module degrades to an honest
UNAVAILABLE (never fabricates a response) — the intended sovereign backend is
still recorded in the receipt. We code against the backend id, not a copy of it.

HONESTY (Doctrine v11 LOCKED):
  * We NEVER fabricate a model response. When the Tower / local endpoint is not
    reachable (CI, cloud, air-gap not up) `run_on_sovereign` returns an honest
    MODELED / UNAVAILABLE result whose `text` is None and whose receipt STILL
    records the intended sovereign backend (id, slug, url, provider, label).
  * `state` is one of:
      LIVE        — the local node answered live THIS request (real text).
      MODELED     — env base present but the node did not answer live this
                    request (honest stub; no fabricated text).
      UNAVAILABLE — SZL_LOCAL_LLM_URL unset (no local fleet base) OR the
                    registry sovereign backend could not be imported.
  * Λ = Conjecture 1 (advisory, never "green", never a theorem). Nothing here
    touches the locked-8.

This closes the loop: SZL's OWN governed model, evaluated + gated + receipted by
SZL's OWN stack. Additive; guarded; pure stdlib (the HTTP call itself lives in the
registry). Nothing added to the locked-8. Doctrine v11 LOCKED — 749/14/163 — c7c0ba17.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
_CONJECTURE_NOTE = "Λ = Conjecture 1 — NOT a theorem. Advisory, never 'green'."

# The registry backend id Dev 1 registered. The brief refers to it as
# "szl-sovereign-local"; the registry entry uses the id "sovereign_local" with
# slug "llama3-szl-finetuned-q4". We accept BOTH spellings as the same request so
# a caller can use either the brief's name or the registry id.
SOVEREIGN_BACKEND_ID = "sovereign_local"
SOVEREIGN_MODEL_SLUG = "llama3-szl-finetuned-q4"
SOVEREIGN_PROVIDER = "SZL sovereign (Ollama, local, Doctrine-v11 system prompt)"
SOVEREIGN_ENV_VAR = "SZL_LOCAL_LLM_URL"
_SOVEREIGN_ALIASES = frozenset({
    "sovereign_local", "szl-sovereign-local", "szl_sovereign_local",
    "sovereign-local", "sovereign", "szl-sovereign",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_sovereign(model_id: str | None) -> bool:
    """True when the caller asked for SZL's sovereign local backend (any alias).

    Accepts the brief's `szl-sovereign-local`, the registry id `sovereign_local`,
    and a few obvious spellings. Case-insensitive; never raises.
    """
    if not model_id:
        return False
    return str(model_id).strip().lower().replace(" ", "") in {
        a.replace(" ", "") for a in _SOVEREIGN_ALIASES
    }


def _reg():
    """Import Dev-1's registry (the sovereign backend lives there). Mirror the
    serve.py resolution order: prefer the extracted substrate package, fall back
    to the local module, so we bind the SAME instance serve.py loaded."""
    try:  # pragma: no cover — substrate package path (in-image)
        from szl_substrate import szl_llm_registry as _r  # type: ignore
        return _r
    except Exception:
        import szl_llm_registry as _r
        return _r


def intended_backend() -> dict[str, Any]:
    """The intended sovereign backend descriptor — recorded in EVERY receipt,
    reachable or not, so an offline run still names WHAT WOULD RUN.

    Reads the live registry entry when importable (single source of truth); falls
    back to the module constants if the registry can't be imported (still honest).
    """
    desc: dict[str, Any] = {
        "requested_model_id": None,          # filled by run_on_sovereign
        "backend_id": SOVEREIGN_BACKEND_ID,
        "model_slug": SOVEREIGN_MODEL_SLUG,
        "provider_provenance": SOVEREIGN_PROVIDER,
        "env_var": SOVEREIGN_ENV_VAR,
        "base_url": None,
        "registry_wired": False,
        "source": "module_constants",
    }
    try:
        reg = _reg()
        entry = getattr(reg, "_MODEL_BY_ID", {}).get(SOVEREIGN_BACKEND_ID)
        if isinstance(entry, dict):
            desc["model_slug"] = entry.get("model_slug", SOVEREIGN_MODEL_SLUG)
            desc["backend_id"] = entry.get("model_id", SOVEREIGN_BACKEND_ID)
            desc["registry_wired"] = True
            desc["source"] = "szl_llm_registry (Dev-1 backend)"
        # resolve the configured base URL (never the secret — this is a URL/env)
        base_fn = getattr(reg, "_sovereign_base", None)
        if callable(base_fn):
            desc["base_url"] = base_fn() or None
        slug_fn = getattr(reg, "_sovereign_model_slug", None)
        if callable(slug_fn):
            desc["served_model_tag"] = slug_fn()
    except Exception as e:  # registry not importable → honest, still records intent
        desc["registry_import_error"] = repr(e)
        desc["dependency_note"] = (
            "szl_llm_registry sovereign backend not importable in this runtime; "
            "recorded the intended backend from module constants — no fabrication.")
    return desc


def run_on_sovereign(prompt: str, *, requested_model_id: str = SOVEREIGN_BACKEND_ID,
                     probe_only: bool = False) -> dict[str, Any]:
    """Route ONE call through Dev-1's sovereign_local backend. NEVER fabricates.

    Returns a dict:
      {
        state: "LIVE" | "MODELED" | "UNAVAILABLE",
        live: bool,
        text: str | None,          # REAL model text ONLY when state == LIVE
        api_style: str | None,     # ollama /api/generate | openai /v1 ... (live only)
        backend: {intended backend descriptor + reachability},
        note: str,                 # honest human-readable label
        conjecture_note, doctrine, kernel_commit,
      }

    state semantics:
      LIVE        — SZL_LOCAL_LLM_URL set AND the node answered live THIS request.
      MODELED     — env base present but node did not answer live (honest stub).
      UNAVAILABLE — no env base (no local fleet) OR registry import failed.
    """
    prompt = str(prompt or "")
    backend = intended_backend()
    backend["requested_model_id"] = requested_model_id
    backend["probed_at"] = _now()

    out: dict[str, Any] = {
        "state": "UNAVAILABLE",
        "live": False,
        "text": None,
        "api_style": None,
        "backend": backend,
        "note": "",
        "conjecture_note": _CONJECTURE_NOTE,
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
    }

    # 1) reachability probe (short timeout) — reflect it in the backend block
    try:
        reg = _reg()
        probe = reg.sovereign_probe()  # {env_present, live, models, base_url, note, ...}
    except Exception as e:  # registry / sovereign helpers unavailable
        backend["reachable"] = False
        backend["probe_error"] = repr(e)
        out["note"] = (
            "UNAVAILABLE — szl_llm_registry sovereign backend not importable in this "
            "runtime; no model call attempted; intended sovereign backend recorded; "
            "no response fabricated.")
        return out

    backend["reachable"] = bool(probe.get("live"))
    backend["env_present"] = bool(probe.get("env_present"))
    backend["base_url"] = probe.get("base_url") or backend.get("base_url")
    backend["served_models"] = probe.get("models", [])
    backend["probe_note"] = probe.get("note")

    if not probe.get("env_present"):
        out["state"] = "UNAVAILABLE"
        out["note"] = (
            f"UNAVAILABLE — {SOVEREIGN_ENV_VAR} is not set, so there is no local "
            "sovereign fleet base to reach (CI / cloud / Tower offline). No model "
            "call attempted; the intended sovereign backend "
            f"('{backend['backend_id']}', slug '{backend['model_slug']}') is still "
            "recorded in the receipt. No response fabricated.")
        return out

    if not probe.get("live"):
        out["state"] = "MODELED"
        out["note"] = (
            f"MODELED — {SOVEREIGN_ENV_VAR} is set ({backend.get('base_url')}) but the "
            "sovereign node did not answer live THIS request (honest stub). No model "
            "text fabricated; the intended sovereign backend is recorded. "
            f"Probe: {probe.get('note')}")
        return out

    # 2) node is live. If probe_only, report LIVE reachability without generating.
    if probe_only:
        out["state"] = "LIVE"
        out["live"] = True
        out["api_style"] = probe.get("api_style")
        out["note"] = (
            "LIVE — sovereign node reachable this request (probe only, no generation). "
            f"Served: {', '.join(backend.get('served_models') or []) or '(none reported)'}")
        return out

    # 3) REAL generation through Dev-1's sovereign_generate (never fabricated)
    try:
        gen = reg.sovereign_generate(prompt)  # {wired, live, text, api_style, ...}
    except Exception as e:
        out["state"] = "MODELED"
        out["note"] = (
            "MODELED — sovereign node probed live but sovereign_generate raised "
            f"({e!r}); no text fabricated; intended backend recorded.")
        return out

    if gen.get("live") and isinstance(gen.get("text"), str):
        out["state"] = "LIVE"
        out["live"] = True
        out["text"] = gen["text"]
        out["api_style"] = gen.get("api_style")
        backend["served_model_tag"] = gen.get("model")
        out["note"] = (
            "LIVE — REAL generation from SZL's sovereign local model this request "
            f"({gen.get('api_style')}). Provider: {SOVEREIGN_PROVIDER}.")
        if isinstance(gen.get("raw"), dict):
            out["raw"] = gen["raw"]
        return out

    # env present, probe live, but generate did not return live text → honest MODELED
    out["state"] = "MODELED"
    out["note"] = (
        "MODELED — sovereign node reachable but did not return live text this "
        f"request (honest stub). No text fabricated. Detail: {gen.get('note')}")
    return out


def receipt_block(sov: dict[str, Any]) -> dict[str, Any]:
    """Compact, receipt-embeddable summary of a run_on_sovereign() result.

    Records the INTENDED sovereign backend + honest state on EVERY run — reachable
    or not — so an offline flywheel run still proves which sovereign backend it
    would have used (never fabricates text into the receipt).
    """
    b = sov.get("backend") or {}
    return {
        "requested": b.get("requested_model_id"),
        "backend_id": b.get("backend_id"),
        "model_slug": b.get("model_slug"),
        "provider_provenance": b.get("provider_provenance"),
        "env_var": b.get("env_var"),
        "base_url": b.get("base_url"),
        "registry_wired": b.get("registry_wired"),
        "reachable": b.get("reachable"),
        "env_present": b.get("env_present"),
        "served_models": b.get("served_models"),
        "state": sov.get("state"),
        "live": sov.get("live"),
        "api_style": sov.get("api_style"),
        # text is recorded ONLY when LIVE (real); never fabricated otherwise
        "text_present": bool(sov.get("text")),
        "note": sov.get("note"),
        "conjecture_note": _CONJECTURE_NOTE,
        "dependency": ("routes through szl_llm_registry.sovereign_local (Dev-1 "
                       "backend, Wave M PR #791). Codes against the backend id; "
                       "degrades to honest UNAVAILABLE if that backend is absent."),
    }


def selected_label(sov: dict[str, Any]) -> str:
    """One-line honest label for the flow's `_selected`/`honesty_label` surface."""
    st = sov.get("state")
    if st == "LIVE":
        return "LIVE (SZL sovereign local model — real generation this request)"
    if st == "MODELED":
        return "MODELED (SZL sovereign backend selected; node not live this request — no fabrication)"
    return "UNAVAILABLE (SZL sovereign backend selected; local endpoint unreachable — no fabrication)"


def _selftest() -> None:  # pragma: no cover — `python3 szl_sovereign_flywheel.py`
    # alias detection
    assert is_sovereign("szl-sovereign-local")
    assert is_sovereign("sovereign_local")
    assert is_sovereign("SOVEREIGN-LOCAL")
    assert not is_sovereign("claude_opus_4_8")
    assert not is_sovereign("")
    # intended backend always records the sovereign identity, reachable or not
    b = intended_backend()
    assert b["backend_id"] == SOVEREIGN_BACKEND_ID
    assert b["model_slug"] == SOVEREIGN_MODEL_SLUG
    assert b["provider_provenance"] == SOVEREIGN_PROVIDER
    # with no SZL_LOCAL_LLM_URL in this env → honest UNAVAILABLE, no fabricated text
    r = run_on_sovereign("State your doctrine in one line.")
    assert r["state"] in ("UNAVAILABLE", "MODELED", "LIVE")
    if r["state"] != "LIVE":
        assert r["text"] is None, "no text may be fabricated when not LIVE"
    rb = receipt_block(r)
    assert rb["backend_id"] == SOVEREIGN_BACKEND_ID
    assert rb["model_slug"] == SOVEREIGN_MODEL_SLUG
    assert rb["state"] == r["state"]
    assert rb["text_present"] == bool(r["text"])
    lbl = selected_label(r)
    assert isinstance(lbl, str) and lbl
    print(f"szl_sovereign_flywheel: ALL OK — is_sovereign works, intended backend "
          f"recorded, run_on_sovereign honest state={r['state']} "
          f"(text fabricated? {'no' if r['text'] is None else 'LIVE-real'}), "
          f"receipt_block records intended backend. Λ=Conjecture 1.")


if __name__ == "__main__":
    _selftest()
