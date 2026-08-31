#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainlocal.py — BRAIN LOCAL: an honest liveness+capability probe for the
LOCAL OpenAI-compatible inference endpoint the brain can be wired to.

WHAT THIS IS
------------
The estate can point the brain at own-metal inference: Ollama on 127.0.0.1:11434,
a llama.cpp `llama-server`, or either of those exposed through a cloudflared tunnel.
The base URL arrives in the environment as SZL_LOCAL_LLM_URL (the same variable
szl_llm_registry already reads for its sovereign backend); A11OY_JPT_GPU_URLS carries
any additional node base URLs and A11OY_JPT_MODELS the model tags the operator EXPECTS
to be served there.

This surface answers exactly one question, honestly, per request:

    is a local model endpoint reachable RIGHT NOW, and which models does it
    itself say it is serving?

HONESTY (this is the entire point of the surface)
------------------------------------------------
  * env unset      -> status UNAVAILABLE, label UNAVAILABLE, note "no local endpoint
                      configured". No model is named. Nothing is described as wired.
  * env set, node answered THIS request -> status LIVE, label MEASURED. The served
                      model list is echoed VERBATIM from the endpoint's own response.
                      This is the ONLY path that earns the MEASURED label, because it
                      is the only path backed by a real reading taken this request.
  * env set, node answered but names NO model -> status DEGRADED, label MEASURED for
                      the reachability fact and an EMPTY served list. DEGRADED is
                      reported as DEGRADED; it is never presented as a healthy node.
  * env set, timeout / connection refused / HTTP error / unparseable body ->
                      status UNAVAILABLE, label UNAVAILABLE, the transport reason
                      recorded verbatim. A configured-but-asleep node is UNAVAILABLE,
                      never LIVE, and never softened into a healthy DEGRADED.

A11OY_JPT_MODELS is an operator DECLARATION, not evidence. It is reported under
`declared_models` with label MODELED and is never merged into `served_models`; a
declared tag that the endpoint does not name is listed as declared-not-served rather
than counted as available.

WHAT THIS IS NOT
----------------
No inference is performed here: the probe is a GET of the endpoint's own model-listing
route ({base}/v1/models, falling back to {base}/api/tags for native Ollama). No prompt
is sent, no completion is requested, no token is generated, nothing is written to disk,
and no response body is retained beyond the model identifiers it named. It is a
liveness+capability probe with honest labels — pure observability over inference
plumbing. It advances no detection / fusion / effector / targeting / cueing capability,
it is not training and it touches no training data, and it makes no claim about
consciousness or sentience of any kind.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET routes mint NOTHING. Only
POST /brain/local/receipt emits an UNSIGNED SHA-256 content digest over the probe
aggregate: a plain content hash, never a fabricated signature and never a proof.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only OBSERVES.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (advisory, never a theorem). Khipu BFT remains Conjecture 2.
    Trust ceiling 0.97, never 100%.
  * No label is ever upgraded. A truthful UNAVAILABLE beats a fabricated live model.
  * Pure stdlib (urllib for the bounded probe — no new dependency). Additive routes
    registered before the SPA catch-all; canonical domain a-11-oy.com; 0 runtime CDN.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import urllib.error
import urllib.request

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken
# import can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# A reading taken from a node that answered THIS request is MEASURED. An operator
# declaration is MODELED. Anything else is UNAVAILABLE.
LBL_MEASURED = "MEASURED"
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# Probe verdicts.
LIVE = "LIVE"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"

# Environment variables this surface reads. Nothing else is consulted.
ENV_PRIMARY = "SZL_LOCAL_LLM_URL"
ENV_EXTRA_URLS = "A11OY_JPT_GPU_URLS"
ENV_DECLARED_MODELS = "A11OY_JPT_MODELS"

# Bounded probe: a local node either answers fast or it is honestly UNAVAILABLE.
PROBE_TIMEOUT_S = 3.0
MAX_NODES = 8              # bound the fan-out; extra configured nodes are disclosed
MAX_MODELS_PER_NODE = 64   # bound the echoed list; truncation is disclosed
MAX_BODY_BYTES = 262144    # 256 KiB read cap on the probe response

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainlocal"

NOTE_UNSET = "no local endpoint configured"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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
    }
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# Environment reading — configuration only, never evidence of reachability.
# --------------------------------------------------------------------------- #

def _csv(raw) -> list:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def configured_urls(environ=None) -> list:
    """The de-duplicated RAW base URLs to probe, primary first. Raw (never redacted)
    because these are the values actually dialled; every REPORTED copy is redacted."""
    env = os.environ if environ is None else environ
    primary = (env.get(ENV_PRIMARY) or "").strip()
    urls = []
    for candidate in ([primary] if primary else []) + _csv(env.get(ENV_EXTRA_URLS)):
        if candidate and candidate not in urls:
            urls.append(candidate)
    return urls


def read_env(environ=None) -> dict:
    """The configuration this surface reads, reported honestly.

    `configured` means an env var carried a base URL — it does NOT mean the node is
    reachable. Only a live probe can say that, and it is taken separately.
    """
    env = os.environ if environ is None else environ
    primary = (env.get(ENV_PRIMARY) or "").strip()
    extra = _csv(env.get(ENV_EXTRA_URLS))
    declared = _csv(env.get(ENV_DECLARED_MODELS))

    urls = configured_urls(env)
    truncated = len(urls) > MAX_NODES

    return {
        "env_vars_read": [ENV_PRIMARY, ENV_EXTRA_URLS, ENV_DECLARED_MODELS],
        "primary_env": ENV_PRIMARY,
        "primary_present": bool(primary),
        "extra_urls_env": ENV_EXTRA_URLS,
        "extra_url_count": len(extra),
        "declared_models_env": ENV_DECLARED_MODELS,
        "declared_models": declared[:MAX_MODELS_PER_NODE],
        "declared_models_label": LBL_MODELED,
        "declared_models_note": (
            "operator declaration read from the environment; a declared tag is NOT "
            "evidence that any node serves it and is never merged into served_models."
        ),
        # reported REDACTED: any userinfo credential in a tunnel URL is stripped before
        # it can reach a response body, a log line, or a receipt digest.
        "endpoints_configured": [_redact(u) for u in urls[:MAX_NODES]],
        "endpoints_configured_count": len(urls),
        "endpoints_truncated": truncated,
        "configured": bool(urls),
        "configured_meaning": (
            "an env var carried a base URL; reachability is a SEPARATE live probe and "
            "is never inferred from configuration."
        ),
    }


def _redact(url: str) -> str:
    """Base URL with any userinfo credential stripped (host/port/path kept verbatim)."""
    try:
        scheme, _, rest = url.partition("://")
        if not rest:
            return url
        if "@" in rest.split("/", 1)[0]:
            hostpart, _, tail = rest.partition("/")
            rest = hostpart.rsplit("@", 1)[-1] + (("/" + tail) if tail else "")
        return f"{scheme}://{rest}" if scheme else rest
    except Exception:  # noqa: BLE001 — redaction is best-effort, never fatal
        return url


def probe_urls(base: str) -> list:
    """The candidate model-listing URLs for one base, in probe order.

    OpenAI-compatible first ({base}/v1/models, and {base}/models when the operator
    already included the /v1 suffix), then native Ollama ({base}/api/tags).
    """
    trimmed = (base or "").rstrip("/")
    if not trimmed:
        return []
    root = trimmed[: -len("/v1")] if trimmed.endswith("/v1") else trimmed
    return [f"{root}/v1/models", f"{root}/api/tags"]


# --------------------------------------------------------------------------- #
# The bounded live probe. urllib only — no new dependency.
# --------------------------------------------------------------------------- #

def _http_get_json(url: str, timeout: float) -> dict:
    """One bounded GET returning the decoded JSON body.

    Module-level so tests can substitute it and never touch a real endpoint. Raises
    on any transport or decode failure; the caller turns that into UNAVAILABLE.
    """
    request = urllib.request.Request(url, method="GET", headers={
        "accept": "application/json",
        "user-agent": "a11oy-brainlocal-probe/1 (liveness probe, no inference)",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read(MAX_BODY_BYTES)
    return json.loads(raw.decode("utf-8", "replace"))


def _models_from_payload(payload) -> list:
    """Model identifiers a listing payload NAMES, read verbatim.

    Understands the OpenAI shape ({"data":[{"id":...}]}) and the Ollama shape
    ({"models":[{"name":...}]}). An unrecognised shape yields NO models — this
    function never invents an identifier to fill a gap.
    """
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data")
    if not isinstance(rows, list):
        rows = payload.get("models")
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        name = None
        if isinstance(row, dict):
            for key in ("id", "name", "model"):
                value = row.get(key)
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                    break
        elif isinstance(row, str) and row.strip():
            name = row.strip()
        if name and name not in out:
            out.append(name)
    return out[:MAX_MODELS_PER_NODE]


def probe_node(base: str, timeout: float = PROBE_TIMEOUT_S) -> dict:
    """Probe ONE base URL this request and report what actually happened.

    LIVE        — a listing route answered and named at least one model (label
                  MEASURED; models echoed verbatim).
    DEGRADED    — a listing route answered but named NO model. Reachability is
                  MEASURED, served_models stays EMPTY, and the node is reported
                  DEGRADED rather than as a healthy node.
    UNAVAILABLE — nothing answered in the budget, or every answer failed. The
                  transport reason is recorded; no model is ever named.
    """
    attempts = []
    for url in probe_urls(base):
        try:
            payload = _http_get_json(url, timeout)
        except Exception as exc:  # noqa: BLE001 — every failure mode is UNAVAILABLE
            attempts.append({
                "url": _redact(url),
                "reached": False,
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            })
            continue
        models = _models_from_payload(payload)
        attempts.append({
            "url": _redact(url),
            "reached": True,
            "model_count": len(models),
        })
        if models:
            return {
                "endpoint": _redact(base),
                "status": LIVE,
                "label": LBL_MEASURED,
                "reached": True,
                "served_models": models,
                "served_model_count": len(models),
                "probe_url": _redact(url),
                "attempts": attempts,
                "note": (
                    "the node answered THIS request and named these models itself; "
                    "the list is echoed verbatim and no model is assumed."
                ),
                "probed_at": _now_iso(),
            }
        return {
            "endpoint": _redact(base),
            "status": DEGRADED,
            "label": LBL_MEASURED,
            "reached": True,
            "served_models": [],
            "served_model_count": 0,
            "probe_url": _redact(url),
            "attempts": attempts,
            "note": (
                "the node answered but named NO model, so it serves nothing this "
                "request: reported DEGRADED, never as a healthy node."
            ),
            "probed_at": _now_iso(),
        }

    return {
        "endpoint": _redact(base),
        "status": UNAVAILABLE,
        "label": LBL_UNAVAILABLE,
        "reached": False,
        "served_models": [],
        "served_model_count": 0,
        "probe_url": None,
        "attempts": attempts,
        "note": (
            "no listing route answered within the probe budget (offline, asleep, or "
            "unroutable from here): UNAVAILABLE, and no model is named."
        ),
        "probed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Aggregate — one honest verdict over the configured nodes.
# --------------------------------------------------------------------------- #

def probe(environ=None, timeout: float = PROBE_TIMEOUT_S, ns: str = "a11oy") -> dict:
    """Read the env, probe every configured node THIS request, and report honestly."""
    config = read_env(environ)

    if not config["configured"]:
        return {
            "endpoint": "brain/local",
            "surface_id": SURFACE_ID,
            "ok": False,
            "status": UNAVAILABLE,
            "verdict": UNAVAILABLE,
            "label": LBL_UNAVAILABLE,
            "reached_any": False,
            "served_models": [],
            "served_model_count": 0,
            "live_node_count": 0,
            "nodes": [],
            "config": config,
            "note": NOTE_UNSET,
            "verdict_reason": (
                f"{ENV_PRIMARY} is unset and {ENV_EXTRA_URLS} carried no base URL, so "
                "there is nothing to probe: UNAVAILABLE. No model is named and nothing "
                "is described as wired or live."
            ),
            "performs_inference": False,
            "stores_anything": False,
            "receipt_policy": (
                "RECEIPT-ON-WRITE-NOT-ON-READ — this GET mints nothing; "
                "POST /brain/local/receipt digests."
            ),
            "doctrine": _doctrine_block(
                "no local endpoint configured; UNAVAILABLE is the honest reading. "
                "Λ = Conjecture 1, never a theorem.",
                label_top=LBL_UNAVAILABLE),
            "timestamp_utc": _now_iso(),
        }

    nodes = [probe_node(base, timeout)
             for base in configured_urls(environ)[:MAX_NODES]]

    served = []
    for node in nodes:
        for name in node.get("served_models") or []:
            if name not in served:
                served.append(name)

    live_nodes = [n for n in nodes if n["status"] == LIVE]
    reachable = [n for n in nodes if n.get("reached")]

    if live_nodes:
        verdict, label = LIVE, LBL_MEASURED
        reason = (
            f"{len(live_nodes)} of {len(nodes)} configured node(s) answered THIS "
            f"request and named {len(served)} model(s); the list is verbatim from the "
            "endpoint. MEASURED is earned by this live reading alone."
        )
    elif reachable:
        verdict, label = DEGRADED, LBL_MEASURED
        reason = (
            f"{len(reachable)} of {len(nodes)} configured node(s) answered but named "
            "NO model, so nothing is served this request. DEGRADED is reported as "
            "DEGRADED, never as a healthy or live node."
        )
    else:
        verdict, label = UNAVAILABLE, LBL_UNAVAILABLE
        reason = (
            f"none of the {len(nodes)} configured node(s) answered within "
            f"{timeout:g}s (offline, asleep, or unroutable from here): UNAVAILABLE. No "
            "model is named and nothing is described as wired or live."
        )

    declared = config["declared_models"]
    declared_not_served = [tag for tag in declared if tag not in served]

    return {
        # ok is true for LIVE alone: a DEGRADED or UNAVAILABLE node is not healthy.
        "ok": verdict == LIVE,
        "endpoint": "brain/local",
        "surface_id": SURFACE_ID,
        "status": verdict,
        "verdict": verdict,
        "label": label,
        "reached_any": bool(reachable),
        "served_models": served,
        "served_model_count": len(served),
        "served_models_provenance": (
            "verbatim from the endpoint's own model listing this request; never a "
            "hardcoded or assumed model"
        ),
        "declared_models": declared,
        "declared_models_label": LBL_MODELED,
        "declared_not_served": declared_not_served,
        "live_node_count": len(live_nodes),
        "node_count": len(nodes),
        "nodes": nodes,
        "config": config,
        "probe_timeout_s": timeout,
        "verdict_reason": reason,
        "performs_inference": False,
        "stores_anything": False,
        "receipt_policy": (
            "RECEIPT-ON-WRITE-NOT-ON-READ — this GET mints nothing; "
            "POST /brain/local/receipt digests."
        ),
        "doctrine": _doctrine_block(
            "liveness+capability probe over inference plumbing; MEASURED only from a "
            "node that answered THIS request. Λ = Conjecture 1, never a theorem.",
            label_top=label),
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Receipt — RECEIPT-ON-WRITE. Unsigned SHA-256 content digest, never a signature.
# --------------------------------------------------------------------------- #

def _canonical_core(result: dict) -> str:
    core = {
        "surface_id": result.get("surface_id"),
        "status": result.get("status"),
        "verdict": result.get("verdict"),
        "label": result.get("label"),
        "reached_any": result.get("reached_any"),
        "served_models": result.get("served_models"),
        "live_node_count": result.get("live_node_count"),
        "node_count": result.get("node_count"),
        "endpoints_configured": (result.get("config") or {}).get("endpoints_configured"),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(result: dict) -> dict:
    """An UNSIGNED SHA-256 content digest over the probe aggregate. Deterministic:
    the same probe content always yields the same digest. RECEIPT-ON-WRITE — only the
    POST path calls this, and no signature is ever fabricated."""
    digest = hashlib.sha256(_canonical_core(result).encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainlocal.probe",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST brain/local/receipt)",
        "note": (
            "unsigned SHA-256 content digest of the probe aggregate; RECEIPT-ON-WRITE, "
            "never on a GET read. No signature and no proof is fabricated."
        ),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/local/info — static self-describing manifest. PURE READ, no probe."""
    base = f"/api/{ns}/v1/brain/local"
    return {
        "ok": True,
        "service": "a11oy.brain.local",
        "endpoint": "brain/local/info",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Local — local inference endpoint liveness+capability probe",
        "what": (
            "reports whether a LOCAL OpenAI-compatible inference endpoint (Ollama on "
            "127.0.0.1:11434, a llama.cpp llama-server, or either behind a cloudflared "
            "tunnel) is reachable RIGHT NOW and which models the endpoint itself says "
            "it serves. Liveness+capability only: no prompt is sent, no completion is "
            "requested, nothing is stored. Not training, not counter-UAS, and no claim "
            "about consciousness or sentience."
        ),
        "env_vars_read": [
            {
                "name": ENV_PRIMARY,
                "role": "primary local endpoint base URL (e.g. http://127.0.0.1:11434 "
                        "or a cloudflared tunnel origin); the same variable "
                        "szl_llm_registry reads for its sovereign backend",
            },
            {
                "name": ENV_EXTRA_URLS,
                "role": "comma-separated additional node base URLs, probed the same way",
            },
            {
                "name": ENV_DECLARED_MODELS,
                "role": "comma-separated model tags the operator DECLARES; a declaration "
                        "is MODELED and is never merged into the served list",
            },
        ],
        "unavailable_when_unset": (
            f"if {ENV_PRIMARY} and {ENV_EXTRA_URLS} are both unset there is nothing to "
            f"probe, so the status is {UNAVAILABLE} with label {LBL_UNAVAILABLE} and the "
            f"note '{NOTE_UNSET}'. No model is named and nothing is reported as wired "
            "or live."
        ),
        "endpoints": {
            "info": f"GET  {base}/info",
            "probe": f"GET  {base}",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            "receipt": f"POST {base}/receipt",
        },
        "probe_mechanism": {
            "transport": "stdlib urllib.request GET (no new dependency, no inference)",
            "timeout_s": PROBE_TIMEOUT_S,
            "routes_tried_in_order": ["{base}/v1/models", "{base}/api/tags"],
            "max_nodes": MAX_NODES,
            "max_models_per_node": MAX_MODELS_PER_NODE,
        },
        "honest_labels": {
            LBL_MEASURED: (
                "earned ONLY when a node answered THIS request; the served model list "
                "is echoed verbatim from that answer"
            ),
            LBL_MODELED: "an operator declaration read from the environment, not evidence",
            LBL_UNAVAILABLE: (
                "env unset, or configured but nothing answered in the probe budget — "
                "no model is named"
            ),
        },
        "verdicts": [LIVE, DEGRADED, UNAVAILABLE],
        "verdict_legend": {
            LIVE: "a node answered this request and named at least one model",
            DEGRADED: (
                "a node answered but named NO model — served list stays empty and the "
                "node is reported DEGRADED, never as healthy"
            ),
            UNAVAILABLE: (
                "nothing configured, or nothing answered (timeout / refused / error) — "
                "never softened into a healthy reading"
            ),
        },
        "never": [
            "never names a model the endpoint did not name itself",
            "never reports a configured-but-unreachable node as wired or live",
            "never upgrades a label; a truthful UNAVAILABLE beats a fabricated model",
            "never performs inference and never stores a request or response body",
        ],
        "performs_inference": False,
        "stores_anything": False,
        "receipt_policy": (
            f"RECEIPT-ON-WRITE-NOT-ON-READ — only POST {base}/receipt emits an unsigned "
            "SHA-256 content digest."
        ),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive OBSERVE-only surface over inference plumbing; touches no locked "
            "formula and no kernel; Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def handle_probe(ns: str = "a11oy", environ=None,
                 timeout: float = PROBE_TIMEOUT_S) -> dict:
    """GET /brain/local — the live probe result. PURE READ (mints nothing)."""
    try:
        result = probe(environ, timeout, ns)
        result["ok"] = result["verdict"] == LIVE
        return result
    except Exception as exc:  # noqa: BLE001 — an honest UNAVAILABLE, never a 500
        return {
            "ok": False,
            "endpoint": "brain/local",
            "surface_id": SURFACE_ID,
            "status": UNAVAILABLE,
            "verdict": UNAVAILABLE,
            "label": LBL_UNAVAILABLE,
            "reached_any": False,
            "served_models": [],
            "served_model_count": 0,
            "error": str(exc)[:200],
            "note": "probe failed; UNAVAILABLE reported and no model fabricated.",
            "doctrine": _doctrine_block(
                "probe unavailable; no fabricated live model emitted.",
                label_top=LBL_UNAVAILABLE),
            "timestamp_utc": _now_iso(),
        }


def handle_manifest(ns: str = "a11oy") -> dict:
    """GET /brain/brainlocal/manifest — the wall-readable honesty manifest.

    Mirrors the szl_surface_manifests.py mechanism: the path carries a segment equal to
    the surface id, so the Honesty Wall / Frontier Index can read this surface in-process
    and count it NATIVE-OK instead of skipping it as NO-MANIFEST.

    The declared data label is the surface's OWN posture — MODELED, because the surface
    is observability over inference plumbing. It does NOT inherit the MEASURED label a
    single live probe may earn: that label belongs to one reading at one instant, never
    to the surface itself.
    """
    base = f"/api/{ns}/v1/brain/local"
    return {
        "ok": True,
        "service": f"a11oy.brain.manifest.{SURFACE_ID}",
        "endpoint": f"brain/{SURFACE_ID}/manifest",
        "surface_id": SURFACE_ID,
        "title": "Brain Local — local inference endpoint liveness+capability probe",
        "label": LBL_MODELED,
        "data_label": LBL_MODELED,
        "what": (
            "a11oy-native observability surface: it probes the configured LOCAL "
            "OpenAI-compatible inference endpoint once per request and reports whether "
            "it answered and which models it named. The surface's OWN posture is MODELED "
            "(observability over inference plumbing). A single probe reading earns "
            f"{LBL_MEASURED} only when a node actually answered that request; otherwise "
            f"the reading is {LBL_UNAVAILABLE}. The surface label is never upgraded to "
            "MEASURED on the strength of one live reading."
        ),
        "native_backend": True,
        "backing_routes": [
            f"GET  {base}/info",
            f"GET  {base}",
            f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            f"POST {base}/receipt",
        ],
        "doctrine": _doctrine_block(
            "wall-readable manifest for the brainlocal surface; adds nothing to the "
            "locked-8; Λ = Conjecture 1, never a theorem.",
            label_top=LBL_MODELED),
        "honesty_invariants": {
            "lambda_is_conjecture_1_not_a_theorem": True,
            "adds_nothing_to_locked_8": True,
            "no_consciousness_claim": True,
            "label_never_upgraded": True,
            "measured_only_from_a_live_reading_this_request": True,
            "unavailable_when_no_endpoint_configured": True,
            "never_fabricates_a_wired_or_live_model": True,
            "performs_no_inference_and_stores_nothing": True,
            "receipt_on_write_not_on_read": True,
            "trust_ceiling_not_100_percent": True,
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — this GET manifest mints nothing.",
        "timestamp_utc": _now_iso(),
    }


def handle_receipt(ns: str = "a11oy", environ=None,
                   timeout: float = PROBE_TIMEOUT_S) -> dict:
    """POST /brain/local/receipt — probe + an UNSIGNED SHA-256 content digest
    (RECEIPT-ON-WRITE). Never 500s: an honest UNAVAILABLE body on error."""
    try:
        result = probe(environ, timeout, ns)
        result["ok"] = True
        result["endpoint"] = "brain/local/receipt"
        result["receipt"] = content_receipt(result)
        return result
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "endpoint": "brain/local/receipt",
            "surface_id": SURFACE_ID,
            "status": UNAVAILABLE,
            "verdict": UNAVAILABLE,
            "label": LBL_UNAVAILABLE,
            "error": str(exc)[:200],
            "note": "receipt not minted; no fabricated verdict or digest emitted.",
            "doctrine": _doctrine_block(
                "receipt unavailable; nothing fabricated.", label_top=LBL_UNAVAILABLE),
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# Registration.
#   GET  info / probe / manifest — @app.get (pure reads; mint nothing).
#   POST receipt                — raw-Request handler via app.router.add_route
#                                 (Starlette passes the Request positionally,
#                                 version-proof under fastapi==0.137.x), with
#                                 app.add_api_route as the fallback. The handler is
#                                 annotated request: fastapi.Request. Registered
#                                 BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/local"
    manifest_path = f"/api/{ns}/v1/brain/{SURFACE_ID}/manifest"

    @app.get(f"{base}/info")
    def _brainlocal_info():
        """Self-describing brain-local manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainlocal_probe():
        """Bounded live probe of the configured local endpoint (mints nothing)."""
        return JSONResponse(handle_probe(ns))

    @app.get(manifest_path)
    def _brainlocal_manifest():
        """Wall-readable honesty manifest for the brainlocal surface (mints nothing)."""
        return JSONResponse(handle_manifest(ns))

    async def _brainlocal_receipt(request):
        """POST: probe + an UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE).
        The body is ignored; the digest covers the probe aggregate only."""
        try:
            await request.body()
        except Exception:  # noqa: BLE001 — a malformed body never 500s
            pass
        return JSONResponse(handle_receipt(ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature
    # analysis (in the add_api_route fallback path) treats the param as the request
    # object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainlocal_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    receipt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(receipt_path, _brainlocal_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(receipt_path, _brainlocal_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(
                Route(receipt_path, _brainlocal_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainlocal receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainlocal-wired:3(get-only)"

    return "brainlocal-wired:4"


# --------------------------------------------------------------------------- #
# Self-test — honest labels, no fabricated model, receipt only on write.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainlocal — self-test (local inference endpoint liveness probe)")
    print("=" * 72)

    # 1) env unset => UNAVAILABLE, no fabricated model.
    empty = probe({}, timeout=0.01)
    assert empty["verdict"] == UNAVAILABLE and empty["label"] == LBL_UNAVAILABLE
    assert empty["served_models"] == [] and empty["note"] == NOTE_UNSET
    assert empty["reached_any"] is False
    print(f"[1] env unset => {UNAVAILABLE}/{LBL_UNAVAILABLE}, note='{NOTE_UNSET}', "
          "no model named  OK")

    _real_get = _http_get_json

    # 2) reachable endpoint naming models => LIVE + MEASURED, verbatim list.
    def _stub_live(url, timeout):
        assert "/models" in url or "/api/tags" in url
        return {"data": [{"id": "llama3.1:8b"}, {"id": "qwen2.5-coder:7b"}]}

    globals()["_http_get_json"] = _stub_live
    live = probe({ENV_PRIMARY: "http://127.0.0.1:11434/v1"}, timeout=0.5)
    assert live["verdict"] == LIVE and live["label"] == LBL_MEASURED
    assert live["served_models"] == ["llama3.1:8b", "qwen2.5-coder:7b"]
    assert live["live_node_count"] == 1
    print(f"[2] reachable node => {LIVE}/{LBL_MEASURED}, served="
          f"{live['served_models']} (verbatim)  OK")

    # 3) timeout / error => UNAVAILABLE, never a healthy fabrication.
    def _stub_timeout(url, timeout):
        raise TimeoutError("probe budget exhausted")

    globals()["_http_get_json"] = _stub_timeout
    dead = probe({ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert dead["verdict"] == UNAVAILABLE and dead["label"] == LBL_UNAVAILABLE
    assert dead["served_models"] == [] and dead["reached_any"] is False
    print(f"[3] configured but asleep => {UNAVAILABLE}, 0 models fabricated  OK")

    # 4) reachable but empty listing => DEGRADED, never healthy.
    globals()["_http_get_json"] = lambda url, timeout: {"data": []}
    degraded = probe({ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert degraded["verdict"] == DEGRADED and degraded["served_models"] == []
    assert degraded["reached_any"] is True
    print(f"[4] reachable, empty listing => {DEGRADED} (not healthy), 0 models  OK")

    # 5) declared models stay MODELED and never enter served_models.
    globals()["_http_get_json"] = _stub_live
    declared = probe({ENV_PRIMARY: "http://127.0.0.1:11434",
                      ENV_DECLARED_MODELS: "phi4:14b,llama3.1:8b"}, timeout=0.5)
    assert "phi4:14b" not in declared["served_models"]
    assert declared["declared_not_served"] == ["phi4:14b"]
    assert declared["declared_models_label"] == LBL_MODELED
    print("[5] declared A11OY_JPT_MODELS stays MODELED, declared-not-served "
          f"{declared['declared_not_served']}  OK")

    # 6) RECEIPT-ON-WRITE: deterministic unsigned digest; GET mints nothing.
    r1 = content_receipt(declared)
    r2 = content_receipt(declared)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert r1["content_sha256"] == r2["content_sha256"]
    assert "receipt" not in handle_probe("a11oy", {}, 0.01)
    assert "receipt" not in handle_info("a11oy")
    assert "receipt" not in handle_manifest("a11oy")
    print(f"[6] POST digest={r1['content_sha256'][:16]}… unsigned + deterministic; "
          "GETs mint nothing  OK")

    # 7) manifest posture is the surface's OWN MODELED label, never upgraded.
    man = handle_manifest("a11oy")
    assert man["data_label"] == LBL_MODELED and man["surface_id"] == SURFACE_ID
    inv = man["honesty_invariants"]
    assert inv["label_never_upgraded"] and inv["no_consciousness_claim"]
    assert inv["measured_only_from_a_live_reading_this_request"]
    assert man["endpoint"] == f"brain/{SURFACE_ID}/manifest"
    print("[7] manifest: surface posture MODELED, id-matching path (NATIVE-OK)  OK")

    # 8) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = man["doctrine"]
    assert d["locked_proven"] == LOCKED_COUNT and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert LBL_MEASURED in HONEST_LABELS and LBL_UNAVAILABLE in HONEST_LABELS
    print("[8] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    globals()["_http_get_json"] = _real_get
    print("\nok:true checks:8")
    _sys.exit(0)
