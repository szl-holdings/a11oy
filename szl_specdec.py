# SPDX-License-Identifier: Apache-2.0
# © Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) · Doctrine v11 LOCKED
"""szl_specdec — Governed speculative-decoding FRAMEWORK + honest acceptance accounting.

Closes GAP 4 (GAP_ML.md): a governed surface for speculative decoding with a
MANDATORY MEASURED quality-delta protocol. Doctrine v11: honest labels only, no
half-state, reimplement-not-copy (the acceptance-rejection math below is
reimplemented from the public papers — Leviathan et al. 2023 arXiv:2211.17192,
Chen et al. 2023 arXiv:2302.01318 — NO proprietary code copied; SpecExec/Sequoia
are MIT REFERENCE only).

WHAT IS REAL HERE
-----------------
* The acceptance-rejection algorithm + the expected-speedup accounting are
  reimplemented in pure Python and unit-self-tested (`selftest()`).
* At REQUEST time the run endpoint PROBES the sovereign tower's ollama /api/tags
  for a SAME-FAMILY draft+target pair (lossless speculative decoding requires a
  shared tokenizer/vocabulary). If such a pair is reachable it runs an EXACT
  greedy speculative-decoding acceptance measurement over HTTP and emits a
  MEASURED block {accepted_rate, mean_accepted_len, speedup_measured, n,
  draft_model, target_model, quality_delta}. quality_delta is MEASURED as the
  identical-rate of the speculative assembly vs target-only greedy decoding
  (lossless ⇒ must be 1.0).

THE HONEST LIMITATION (label=ROADMAP, not a faked MEASURED)
----------------------------------------------------------
The two live mesh nodes run DIFFERENT model families (tower llama3.1:8b vs
laptop qwen2.5:3b) with different tokenizers, so a TRUE cross-node lossless
speculative run is NOT possible with the current pairing. And the tower today
holds only a SINGLE llama model (no small same-family draft pulled yet). When no
same-family draft+target pair is reachable from the Space, this module returns
label=ROADMAP with quality_delta=UNAVAILABLE and the precise on-metal runbook
(SPECDEC_ONMETAL.md) — NEVER a MODELED-as-MEASURED number, NEVER a fabricated
speedup. The half-state is the only unacceptable outcome.

PURE stdlib (math, random, json, hashlib, time, urllib) + httpx (an existing repo
dep, imported INSIDE the handler under try/except). No numpy required. Every
optional dep is guarded at request time and degrades HONESTLY — this module can
NEVER raise into app startup.
"""

import json
import math
import os
import time

try:  # Starlette Route is only needed for the bare-app fallback in register().
    from starlette.routing import Route as _Route
except Exception:  # pragma: no cover
    _Route = None

_SCHEMA = "szl.a11oy.specdec.v1"
_DOCTRINE = "v11 LOCKED"

_PROBE_UA = os.environ.get(
    "SZL_PROBE_USER_AGENT",
    "Mozilla/5.0 (compatible; szl-specdec/1.0; +https://a-11-oy.com)")

# Public sovereign tower (Cloudflare-fronted ollama, RTX 4060 Ti anchor). Resolved
# from env at runtime (token-flip law: never hardcode a key); defaults to the LIVE
# public endpoint the govern/health mesh reports. The OpenAI-compatible base is
# <root>/v1 (chat/completions); ollama's native model list is <root>/api/tags.
def _tower_root() -> str:
    # The spec-decode draft+target pair MUST live on the SAME node, and the only
    # node that holds a llama target (llama3.1:8b) is the tower at gpu.a-11-oy.com.
    # We deliberately do NOT inherit the generic mesh base URL envs
    # (A11OY_BETTERWITHAGE_BASE_URL / A11OY_MODEL_BASE_URL) — on the live Space those
    # point at the laptop node (gpu2.a-11-oy.com), which has no llama target, so the
    # auto-light-up would probe the wrong box after the on-metal pull. Only the
    # dedicated A11OY_SPECDEC_TOWER_URL overrides the tower default.
    root = (os.environ.get("A11OY_SPECDEC_TOWER_URL")
            or "https://gpu.a-11-oy.com").strip().rstrip("/")
    if "router.huggingface.co" in root:  # never the cloud router — we want the metal
        root = "https://gpu.a-11-oy.com"
    if root.endswith("/v1"):
        root = root[:-3]
    return root


# ---------------------------------------------------------------------------
# CORE MATH — reimplemented from the public speculative-decoding papers.
# ---------------------------------------------------------------------------
def expected_tokens_per_step(alpha: float, k: int) -> float:
    """E[# tokens emitted per speculative step] for k drafted tokens at mean
    acceptance rate alpha (Leviathan et al. 2023, eq. for E[#generated]):

        E = (1 - alpha^(k+1)) / (1 - alpha)            (alpha < 1)
        E = k + 1                                       (alpha == 1)

    The +1 is the always-accepted bonus token sampled from the target (on full
    acceptance) or the residual (on rejection). Reimplemented, not copied."""
    if k < 0:
        raise ValueError("k must be >= 0")
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError("alpha must be in [0,1]")
    if alpha >= 1.0:
        return float(k + 1)
    return (1.0 - alpha ** (k + 1)) / (1.0 - alpha)


def expected_speedup(alpha: float, k: int, cost_ratio: float) -> float:
    """Honest wall-clock speedup vs target-only autoregressive decoding.

    One speculative step costs: k draft passes (each `cost_ratio` of a target
    pass) + 1 target verification pass = (k * cost_ratio + 1) target-pass units,
    and emits E[tokens] = expected_tokens_per_step(alpha, k). Target-only emits 1
    token per target pass. So:

        speedup = E[tokens] / (k * cost_ratio + 1)

    cost_ratio = (draft forward cost / target forward cost) in [0,1]. This is the
    MODEL of the speedup; a MEASURED speedup must come from real wall-clock
    timing on a real same-family pair (see measure_greedy_specdec)."""
    if cost_ratio < 0.0:
        raise ValueError("cost_ratio must be >= 0")
    denom = (k * cost_ratio + 1.0)
    return expected_tokens_per_step(alpha, k) / denom if denom > 0 else float("nan")


def accept_reject_step(p_tok: float, q_tok: float, u: float) -> bool:
    """The acceptance test for ONE drafted token (Chen/Leviathan): given the
    target prob p_tok and draft prob q_tok of the SAME drafted token, and a
    uniform draw u ~ U[0,1], accept iff u <= min(1, p_tok / q_tok). On rejection
    the next token is resampled from the residual max(p-q,0)/Z. Output
    distribution is provably identical to target-only sampling (lossless).
    Reimplemented from the published rule."""
    if q_tok <= 0.0:
        return False
    return u <= min(1.0, p_tok / q_tok)


def residual_distribution(p: list, q: list) -> list:
    """Residual sampling distribution on rejection: normalize max(p-q, 0).
    Returns a proper probability vector (sums to 1) or a uniform fallback if the
    residual mass is degenerate. Pure Python; used by selftest to demonstrate
    the lossless property empirically."""
    diff = [max(pi - qi, 0.0) for pi, qi in zip(p, q)]
    z = sum(diff)
    if z <= 0.0:
        n = len(p)
        return [1.0 / n for _ in p] if n else []
    return [d / z for d in diff]


# ---------------------------------------------------------------------------
# LIVE PROBE — ollama model inventory + same-family pairing.
# ---------------------------------------------------------------------------
def probe_models(root: str, timeout: float = 8.0) -> dict:
    """List ollama models on a node via its native /api/tags. Returns
    {"ok": bool, "models": [{name, family, parameter_size}], "detail": ...}.
    Never raises — an unreachable node degrades honestly."""
    import urllib.request as _u
    url = root.rstrip("/") + "/api/tags"
    try:
        req = _u.Request(url, method="GET", headers={"User-Agent": _PROBE_UA})
        with _u.urlopen(req, timeout=timeout) as r:  # noqa: S310
            status = getattr(r, "status", r.getcode())
            raw = r.read()
        if not (200 <= status < 300):
            return {"ok": False, "models": [], "detail": f"HTTP {status}", "node": root}
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "models": [], "detail": repr(e)[:160], "node": root}
    out = []
    for m in (data.get("models") or []):
        det = m.get("details") or {}
        out.append({
            "name": m.get("name") or m.get("model") or "",
            "family": (det.get("family") or (det.get("families") or [None])[0] or "unknown"),
            "parameter_size": det.get("parameter_size") or "?",
        })
    return {"ok": True, "models": out, "node": root}


def _param_billions(p) -> float:
    """Parse '8.0B' / '1B' / '3.2B' -> float billions; unknown -> +inf so it is
    never mistaken for the smaller (draft) model."""
    try:
        s = str(p).strip().upper().rstrip("B")
        return float(s)
    except Exception:  # noqa: BLE001
        return float("inf")


def find_same_family_pair(models: list) -> dict:
    """Pick a (draft, target) pair sharing the SAME family (⇒ same tokenizer, the
    precondition for lossless speculative decoding): smallest model as draft,
    largest DISTINCT model as target. Returns {"found": bool, "draft", "target",
    "family", "reason"}. Honest: a single model (no second same-family model) is
    NOT a pair."""
    by_family: dict = {}
    for m in models:
        fam = m.get("family", "unknown")
        by_family.setdefault(fam, []).append(m)
    for fam, members in by_family.items():
        if len(members) < 2:
            continue
        ordered = sorted(members, key=lambda m: _param_billions(m.get("parameter_size")))
        draft, target = ordered[0], ordered[-1]
        if draft.get("name") == target.get("name"):
            continue
        return {"found": True, "draft": draft["name"], "target": target["name"],
                "family": fam,
                "reason": f"same-family pair on one node: draft={draft['name']} "
                          f"target={target['name']} (family={fam})"}
    fams = {m.get("family", "unknown") for m in models}
    return {"found": False, "draft": None, "target": None, "family": None,
            "reason": (f"no same-family draft+target pair reachable "
                       f"(models={[m.get('name') for m in models]}, families={sorted(fams)}); "
                       f"lossless speculative decoding requires a shared tokenizer/vocabulary")}


# ---------------------------------------------------------------------------
# MEASURED greedy speculative-decoding acceptance protocol (HTTP, same-family).
# ---------------------------------------------------------------------------
def _greedy_tokens(client, base_v1: str, model: str, prompt: str, max_tokens: int):
    """One greedy (temperature=0) generation, returning the list of generated
    token STRINGS via the OpenAI-compatible logprobs channel (same tokenizer ⇒
    token strings align between draft and target). Falls back to whitespace
    tokenization only if logprobs are absent (still same-family, so honest)."""
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "max_tokens": max_tokens, "temperature": 0.0,
            "logprobs": True, "top_logprobs": 1}
    headers = {"Content-Type": "application/json", "User-Agent": _PROBE_UA}
    tok = (os.environ.get("A11OY_GPU_TOKEN") or "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    resp = client.post(f"{base_v1.rstrip('/')}/chat/completions", headers=headers, json=body)
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    lp = choice.get("logprobs") or {}
    toks = [t.get("token") for t in (lp.get("content") or []) if t.get("token") is not None]
    if not toks:
        toks = content.split()
    return toks, content


def measure_greedy_specdec(root: str, draft: str, target: str, prompts: list,
                           k: int = 4, max_steps: int = 16, timeout: float = 60.0) -> dict:
    """EXACT greedy speculative-decoding acceptance measurement over HTTP.

    For each prompt, repeatedly: (1) the DRAFT proposes k greedy tokens from the
    running context; (2) for i=0..k-1 the TARGET greedily emits ONE token given
    context+draft[:i]; accept draft[i] iff it equals the target token, stop at the
    first mismatch (taking the target token as the correction). accepted_len is
    the matched prefix length. This is the greedy specialization of the
    acceptance-rejection rule and is LOSSLESS vs target-only greedy decoding.

    Returns a MEASURED block. Raises on transport failure so the caller degrades
    to ROADMAP rather than fabricating a number. Same family ⇒ token strings are
    directly comparable."""
    import httpx
    base_v1 = root.rstrip("/") + "/v1"
    accepted_lens = []
    identical_hits = 0
    identical_total = 0
    t0 = time.time()
    with httpx.Client(timeout=timeout) as client:
        for prompt in prompts:
            context_note = prompt
            spec_emitted = []
            target_only = []
            for _step in range(max_steps):
                draft_toks, _ = _greedy_tokens(client, base_v1, draft, context_note, k)
                if not draft_toks:
                    break
                accepted = 0
                correction = None
                for i in range(min(k, len(draft_toks))):
                    # Target's greedy next token given context + accepted draft prefix.
                    sub_prompt = context_note + "".join(draft_toks[:i])
                    tgt_toks, _ = _greedy_tokens(client, base_v1, target, sub_prompt, 1)
                    tgt = tgt_toks[0] if tgt_toks else None
                    if tgt is not None and tgt == draft_toks[i]:
                        accepted += 1
                        continue
                    correction = tgt
                    break
                accepted_lens.append(accepted)
                emit = draft_toks[:accepted] + ([correction] if correction is not None else [])
                if not emit:
                    break
                spec_emitted.extend(emit)
                context_note = context_note + "".join(emit)
                if correction is None and accepted == 0:
                    break
            # Lossless check: assemble target-only greedy over the same total length.
            n_emit = len(spec_emitted)
            if n_emit:
                tgt_full, _ = _greedy_tokens(client, base_v1, target, prompt, n_emit)
                identical_total += 1
                if len(tgt_full) >= n_emit and tgt_full[:n_emit] == spec_emitted[:n_emit]:
                    identical_hits += 1
    elapsed = time.time() - t0
    n = len(accepted_lens)
    if n == 0:
        raise RuntimeError("no acceptance samples gathered (empty draft outputs)")
    mean_acc = sum(accepted_lens) / n
    accepted_rate = mean_acc / float(k)
    # MEASURED expected tokens-per-step and the resulting MODEL speedup at a
    # documented cost_ratio (the speedup is MODELED from the MEASURED acceptance;
    # a wall-clock-MEASURED speedup is reported separately as ROADMAP until the
    # full block-parallel verify path is run on-metal — we do NOT fake it here).
    cost_ratio = float(os.environ.get("A11OY_SPECDEC_COST_RATIO", "0.2"))
    e_tokens = expected_tokens_per_step(accepted_rate, k)
    speedup_modeled = expected_speedup(accepted_rate, k, cost_ratio)
    quality_delta = (identical_hits / identical_total) if identical_total else None
    return {
        "label": "SPEC-DECODE MEASURED",
        "accepted_rate": round(accepted_rate, 4),
        "mean_accepted_len": round(mean_acc, 4),
        "n": n,
        "k": k,
        "draft_model": draft,
        "target_model": target,
        "expected_tokens_per_step": round(e_tokens, 4),
        "speedup_modeled": round(speedup_modeled, 4),
        "speedup_modeled_cost_ratio": cost_ratio,
        "speedup_measured": ("ROADMAP — wall-clock speedup requires the on-metal "
                             "block-parallel verify path; acceptance is MEASURED, "
                             "the speedup here is MODELED from it (no faked number)"),
        "quality_delta": (round(quality_delta, 4) if quality_delta is not None else "UNAVAILABLE"),
        "quality_delta_metric": "identical_rate(spec vs target-only greedy); lossless ⇒ 1.0",
        "quality_delta_label": ("MEASURED" if quality_delta is not None else "UNAVAILABLE"),
        "wall_clock_s": round(elapsed, 3),
        "method": "greedy_speculative_decoding_exact_acceptance_over_http",
    }


# ---------------------------------------------------------------------------
# ON-METAL RUNBOOK (returned inside the ROADMAP payload).
# ---------------------------------------------------------------------------
def _runbook() -> dict:
    return {
        "doc": "/home/user/workspace/team/frontier/SPECDEC_ONMETAL.md",
        "why": ("The Space can only HTTP the ollama endpoints. A MEASURED block "
                "needs a SAME-FAMILY draft+target pair (shared tokenizer) reachable "
                "on ONE node. The tower currently holds only llama3.1:8b; the laptop "
                "(qwen2.5:3b, different family) is also DOWN. Pull a same-family draft "
                "on the tower and this endpoint lights up MEASURED automatically."),
        "steps": [
            "On the tower (RTX 4060 Ti): ollama pull llama3.2:1b   # same llama family ⇒ same tokenizer",
            "Keep the target: ollama pull llama3.1:8b   # already present",
            "Confirm both appear: curl -s https://gpu.a-11-oy.com/api/tags | jq '.models[].name'",
            "POST /api/a11oy/v1/specdec/run  (the request-time probe finds the pair and runs the MEASURED protocol)",
        ],
        "expected_after": ("label flips to SPEC-DECODE MEASURED with "
                           "{accepted_rate, mean_accepted_len, speedup_modeled, n, "
                           "draft_model=llama3.2:1b, target_model=llama3.1:8b, "
                           "quality_delta=identical_rate(MEASURED, lossless⇒1.0)}"),
    }


# ---------------------------------------------------------------------------
# PAYLOAD BUILDERS.
# ---------------------------------------------------------------------------
def _sha3(b: bytes) -> str:
    import hashlib
    return hashlib.sha3_256(b).hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def health_payload() -> dict:
    """GET health: LIVE capability probe of the tower (no inference, no signing).
    Honest about whether a MEASURED run is currently possible."""
    root = _tower_root()
    probe = probe_models(root)
    pair = find_same_family_pair(probe.get("models") or []) if probe.get("ok") else \
        {"found": False, "reason": f"tower unreachable: {probe.get('detail')}"}
    measured_possible = bool(probe.get("ok") and pair.get("found"))
    return {
        "schema": _SCHEMA,
        "doctrine": _DOCTRINE,
        "service": "a11oy governed speculative decoding",
        "status": "LIVE",
        "tower": root,
        "tower_reachable": bool(probe.get("ok")),
        "models": probe.get("models") or [],
        "same_family_pair": pair,
        "measured_run_possible": measured_possible,
        "label": ("SPEC-DECODE READY (same-family pair reachable)"
                  if measured_possible else "SPEC-DECODE ROADMAP (no same-family pair)"),
        "lambda": "Conjecture 1 (advisory)",
        "honest_note": ("Lossless speculative decoding requires a draft+target sharing the "
                        "SAME tokenizer/vocabulary. The two mesh nodes run different families "
                        "(llama3.1:8b vs qwen2.5:3b), so a cross-node lossless run is NOT possible. "
                        "Pull a same-family draft on the tower to enable a MEASURED run."),
        "endpoints": {
            "health": "GET /api/a11oy/v1/specdec/health",
            "run": "POST /api/a11oy/v1/specdec/run  (GET also allowed)",
        },
        "references_reimplemented_not_copied": [
            "Leviathan et al. 2023 arXiv:2211.17192",
            "Chen et al. 2023 arXiv:2302.01318",
            "SpecExec arXiv:2406.02532 (MIT, REFERENCE ONLY)",
            "Sequoia arXiv:2402.12374 (MIT, REFERENCE ONLY)",
        ],
    }


_DEFAULT_PROMPTS = [
    "In one sentence, define a joule.",
    "Name one law of thermodynamics in a single line.",
    "What is sovereign compute? Answer in one sentence.",
]


def run_payload(n: int = 0, k: int = 4) -> dict:
    """POST run: attempt a MEASURED greedy speculative-decoding measurement if a
    same-family draft+target pair is reachable; otherwise an HONEST ROADMAP with
    quality_delta=UNAVAILABLE + the on-metal runbook. Builds a self-digesting,
    offline-verifiable acceptance-accounting receipt. NEVER fabricates a speedup."""
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    root = _tower_root()
    probe = probe_models(root)
    pair = find_same_family_pair(probe.get("models") or []) if probe.get("ok") else \
        {"found": False, "reason": f"tower unreachable: {probe.get('detail')}"}

    body = {
        "schema": _SCHEMA,
        "doctrine": _DOCTRINE,
        "generated_at": generated_at,
        "tower": root,
        "tower_reachable": bool(probe.get("ok")),
        "models": probe.get("models") or [],
        "same_family_pair": pair,
        "k": int(k),
        "lambda": "Conjecture 1 (advisory)",
        # The framework's MODELED accounting curve is ALWAYS honest to show — it is
        # clearly MODELED (a formula), never presented as a measurement.
        "accounting_modeled": {
            "label": "MODELED (acceptance-rejection accounting curve, not a measurement)",
            "k": int(k),
            "cost_ratio": float(os.environ.get("A11OY_SPECDEC_COST_RATIO", "0.2")),
            "expected_tokens_per_step_at_alpha": {
                str(a): round(expected_tokens_per_step(a, int(k)), 4)
                for a in (0.5, 0.7, 0.9)
            },
            "expected_speedup_at_alpha": {
                str(a): round(expected_speedup(a, int(k),
                              float(os.environ.get("A11OY_SPECDEC_COST_RATIO", "0.2"))), 4)
                for a in (0.5, 0.7, 0.9)
            },
        },
    }

    if probe.get("ok") and pair.get("found"):
        prompts = _DEFAULT_PROMPTS if n <= 0 else (_DEFAULT_PROMPTS * (n // len(_DEFAULT_PROMPTS) + 1))[:n]
        try:
            measured = measure_greedy_specdec(root, pair["draft"], pair["target"], prompts, k=int(k))
            body["measured"] = measured
            body["label"] = measured["label"]
        except Exception as e:  # honest degrade — a transport failure is NOT a measurement
            body["label"] = "SPEC-DECODE ROADMAP"
            body["measured"] = "UNAVAILABLE"
            body["quality_delta"] = "UNAVAILABLE"
            body["roadmap"] = {
                "reason": f"same-family pair present but measurement transport failed: {repr(e)[:160]}",
                "runbook": _runbook(),
            }
    else:
        body["label"] = "SPEC-DECODE ROADMAP"
        body["measured"] = "UNAVAILABLE"
        body["quality_delta"] = "UNAVAILABLE"
        body["roadmap"] = {"reason": pair.get("reason"), "runbook": _runbook()}

    digest = _sha3(_canon(body))
    receipt = {
        "schema": "szl.a11oy.specdec.receipt.v1",
        "payload": body,
        "payload_sha3_256": digest,
        "digest_alg": "sha3_256",
        "digest_canonicalization": ("json.dumps(payload, sort_keys=True, separators=(',',':'), "
                                    "ensure_ascii=False).encode('utf-8') then sha3_256.hexdigest()"),
        "offline_verify": ("Recompute the sha3_256 of the canonicalised 'payload' and confirm it "
                           "equals payload_sha3_256. Zero server round-trip."),
        "signature": _sign(digest),
        "generated_at": generated_at,
    }
    return receipt


def _sign(digest: str) -> dict:
    """Sign the receipt digest with the clearly-labelled DEMO key if present;
    otherwise an HONEST unsigned DSSE_PLACEHOLDER. NEVER a fabricated signature."""
    try:
        import szl_demo_sign as _d
        env = _d.sign_payload_demo({"a11oy_specdec_receipt_sha3_256": digest})
        if env is not None:
            return {"signed": True, "alg": "ECDSA-P256-SHA256 over DSSE PAE",
                    "keyid": env.get("key_id"), "key_kind": "demo",
                    "verify_key_url": "/demo-cosign.pub", "dsse": env,
                    "note": "DEMO key — NOT production cosign. Digest is independently recomputable offline."}
    except Exception as e:  # noqa: BLE001
        return {"signed": False, "status": "DSSE_PLACEHOLDER",
                "note": "signing unavailable — honest-unsigned; digest still recomputable offline.",
                "detail": repr(e)[:160]}
    return {"signed": False, "status": "DSSE_PLACEHOLDER",
            "note": "no demo signing key in runtime — honest-unsigned; digest recomputable offline."}


# ---------------------------------------------------------------------------
# HTTP handlers + registration (front-moved in serve.py to beat the proxy).
# ---------------------------------------------------------------------------
def _json_response(obj):
    from starlette.responses import JSONResponse
    return JSONResponse(obj)


def _h_health(request=None):
    try:
        return _json_response(health_payload())
    except Exception as e:  # last-resort honest degrade — NEVER 404, NEVER raise
        return _json_response({"schema": _SCHEMA, "status": "DEGRADED",
                               "label": "ROADMAP — specdec health temporarily unavailable",
                               "detail": repr(e)[:200], "fabricated": False})


def _parse_int(request, key, default):
    try:
        if request is None:
            return default
        v = request.query_params.get(key)
        return int(v) if v is not None else default
    except Exception:  # noqa: BLE001
        return default


def _h_run(request=None):
    try:
        n = _parse_int(request, "n", 0)
        k = _parse_int(request, "k", 4)
        return _json_response(run_payload(n=n, k=max(1, k)))
    except Exception as e:  # last-resort honest degrade — NEVER 404, NEVER raise
        return _json_response({"schema": "szl.a11oy.specdec.receipt.v1", "status": "DEGRADED",
                               "label": "ROADMAP — specdec run temporarily unavailable",
                               "detail": repr(e)[:200], "fabricated": False})


def register(app, ns: str = "a11oy") -> list:
    """Wire specdec routes under /api/<ns>/v1/specdec/* (and bare /v1/specdec/* so
    the generic Node proxy at /api/a11oy/{path:path} -> Node /v1/* maps too).
    Additive; uses add_api_route when present (FastAPI) so the caller can then
    front-move the just-added routes to the router head — same proven pattern as
    the inverse-PINN block in serve.py."""
    base = f"/api/{ns}/v1/specdec"
    handlers = [
        (f"{base}/health", _h_health, ["GET"]),
        (f"{base}/run", _h_run, ["GET", "POST"]),
        ("/v1/specdec/health", _h_health, ["GET"]),
        ("/v1/specdec/run", _h_run, ["GET", "POST"]),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn, methods in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=methods, include_in_schema=False)
        elif _Route is not None:
            app.router.routes.append(_Route(path, fn, methods=methods))
    return [p for p, _, _ in handlers]


# ---------------------------------------------------------------------------
# No-server self-test of the reimplemented core math (no network).
# ---------------------------------------------------------------------------
def selftest() -> dict:
    out = {}
    # (a) E[tokens] endpoints: alpha=0 ⇒ exactly the +1 bonus token; alpha=1 ⇒ k+1.
    assert abs(expected_tokens_per_step(0.0, 4) - 1.0) < 1e-12
    assert abs(expected_tokens_per_step(1.0, 4) - 5.0) < 1e-12
    # monotone increasing in alpha
    vals = [expected_tokens_per_step(a, 4) for a in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert all(b > a for a, b in zip(vals, vals[1:])), vals
    out["expected_tokens_per_step_ok"] = True

    # (b) speedup > 1 when acceptance is high & draft cheap; sane bounds.
    assert expected_speedup(0.9, 4, 0.1) > 1.0
    assert expected_speedup(0.0, 4, 1.0) < 1.0  # no acceptance, expensive draft ⇒ slowdown
    out["expected_speedup_ok"] = True

    # (c) accept/reject rule: p>=q ⇒ always accept; p<q ⇒ accept w.p. p/q.
    assert accept_reject_step(0.6, 0.3, 0.99) is True   # p/q=2 -> min1 -> u<=1
    assert accept_reject_step(0.2, 0.8, 0.5) is False   # p/q=0.25, u=0.5 > 0.25
    assert accept_reject_step(0.2, 0.8, 0.1) is True    # u=0.1 <= 0.25
    out["accept_reject_ok"] = True

    # (d) LOSSLESS empirical check: simulate spec sampling vs direct target
    # sampling on a toy vocab; the resulting token histograms must match the
    # target distribution within Monte-Carlo error. This demonstrates the
    # acceptance-rejection + residual math is correct (reimplemented honestly).
    import random
    rng = random.Random(7)
    p = [0.5, 0.3, 0.2]   # target
    q = [0.2, 0.5, 0.3]   # draft (different ⇒ exercises rejection + residual)
    res = residual_distribution(p, q)
    assert abs(sum(res) - 1.0) < 1e-9
    counts = [0, 0, 0]
    trials = 60000
    for _ in range(trials):
        # draft proposes
        dr = rng.random()
        cum = 0.0
        di = 0
        for i, qi in enumerate(q):
            cum += qi
            if dr <= cum:
                di = i
                break
        # accept/reject against target
        if accept_reject_step(p[di], q[di], rng.random()):
            counts[di] += 1
        else:
            # resample from residual
            rr = rng.random()
            cum = 0.0
            for i, ri in enumerate(res):
                cum += ri
                if rr <= cum:
                    counts[i] += 1
                    break
    emp = [c / trials for c in counts]
    assert all(abs(e - pt) < 0.02 for e, pt in zip(emp, p)), (emp, p)
    out["lossless_distribution_identity_ok"] = True
    out["empirical_target_hist"] = [round(e, 4) for e in emp]
    out["all_passed"] = True
    return out


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2))
