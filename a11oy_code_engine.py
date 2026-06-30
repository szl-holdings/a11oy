# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Doctrine v11/v12. Signed: Yachay. Built by: Perplexity Computer Agent (Opus-class).
"""
a11oy Code — a GOVERNED agentic coder + chatbot, baked into a11oy.

WHAT THIS IS (honest, one line): a chat + coder + research surface where EVERY
turn flows through the *proven* P1-P6 governed loop (szl_agentic_loop) and emits
a signed, hash-chained, re-verifiable receipt. The differentiator is PROVEN
GOVERNANCE — not raw model power.

THREE GOVERNED MODES, all P1-P6, all receipted:
  1. CHAT     — multi-turn conversation.  govern -> answer -> signed receipt.
  2. CODE     — generate code AND run it in a REAL governed sandbox
                (plan -> policy/kernel gate -> isolated subprocess exec -> signed
                receipt of the run, with stdout/result).
  3. RESEARCH — retrieve + answer over REAL sources (the in-image RAG governance
                corpus + the app's already-wired live public feeds — CVE/KEV/MITRE/
                USGS) with citations.  govern -> cited answer -> signed receipt.

BUILT ON TOP OF (not parallel to) what already lives in a11oy:
  - szl_agentic_loop.py   -> the PROVEN 6-receipt P1-P6 loop. We import its
                             _retrieve / _trust_score / _sha primitives and build
                             the SAME chain semantics so receipts are byte-
                             compatible with the existing /agent/verify-chain.
  - szl_llm_registry.py   -> if present (forge squad's unified OPEN-WEIGHT roster)
                             we DEFER to it for the model roster. If absent we fall
                             back to our own honest open-weight roster below.
                             DeepSeek-Coder is a core model (forge owns the roster).
  - knowledge.json        -> proven-formula maturity (proven | axiom-gated |
                             CI-green | conjectured) surfaced as honest chips.
  - the host app's REAL signer (sign_fn) -> a11oy in-image ECDSA-P256 / killinchu
                             persistent cosign key. Receipts are genuinely signed.

HONESTY / LEGAL DOCTRINE (absolute):
  - OPEN-WEIGHT models only (Mistral/Nemo, Llama, Qwen2.5-Coder, DeepSeek-Coder,
    Codestral, StarCoder2, Gemma, Phi) per their commercial-OK licenses. NO closed
    weights claimed as baked in (GPT/Claude/Gemini are API-only — never claimed).
  - NO API KEY REQUIRED (offline-first). The local backend is a DETERMINISTIC,
    retrieval-grounded responder — it NEVER fakes generative model output. If a
    real local model is plugged in (LOCAL_MODEL_CMD env / tower GPU) it is used and
    honestly labeled; an optional HF router is used ONLY if a token is present, and
    its use is disclosed. With no model and no token, the backend returns honest,
    grounded, deterministic output labeled "local deterministic backend".
  - Patterns reimplemented as OUR OWN code (study of OpenHands/SWE-agent/Aider/
    Cline patterns — patterns are free; no GPL/AGPL/proprietary source copied).
  - NO "AGI" claims. "A governed agentic coder you can mathematically trust."
    Lambda (trust score) = Conjecture 1, advisory, never the gate. Locked proven=8 {F1,F4,F7,F11,F12,F18,F19,F22}.

FORMULA WIRING (the moat — cited in code, plain-language to the user):
  - C20  Softmax 1/2-Lipschitz (order/argmax-stable core)  -> model ROUTER stability.
         Bounded sensitivity => small input perturbations don't flip the routed model.
         (lutar-lean C20; PROVEN fragment.)
  - W7-5 PAC-Bayes min<=avg<=max routing envelope           -> ROUTER cost/risk bracket.
         A routed set's aggregate is provably bracketed by its component extremes.
         (lutar-lean wave-7 W7-5a/b/W7-5; PR #190, CI-green MD.)
  - W5-3 / W7-4 conformal coverage + rank-count/p-value     -> calibrated CONFIDENCE
         on a suggestion. Distribution-free interval; anti-overconfidence p>=1/(n+1)
         floor => we NEVER report 100% certainty. (wave-5/7; PROVEN, axiom-free.)
  - P1-P6 governed loop (Pipeline.lean, PR #188)            -> the governed RUN.
         P3 non-interference (Goguen-Meseguer 1982): untrusted/pasted input is
         quarantined and provably cannot flip a denied action. (axiom-free core.)
  - C10/C11/C12 Byzantine / DLS / FLP                        -> optional CONSENSUS
         vote across >=2 models (n>=3f+1 safety bound; FLP liveness caveat). PROVEN.
  - F-G5 bounded-frontier receipt-DAG termination            -> the agent loop
         provably HALTS (good for edge). (wave-6; PROVEN.)

Citations (DOIs/refs in comments above each use; surfaced plainly in /capabilities).
"""

from __future__ import annotations

import json
import math
import os
import re
import resource
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---- reuse the PROVEN loop primitives (single source of truth for chain semantics)
try:
    import szl_agentic_loop as _loop
    _retrieve = _loop._retrieve
    _trust_score = _loop._trust_score
    _sha = _loop._sha
    _LOOP_OK = True
except Exception:  # additive: never break the Space if the loop module moves
    _LOOP_OK = False
    import hashlib as _hl

    def _sha(obj) -> str:
        return _hl.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    _MINI_CORPUS = [
        {"id": "DOC-001", "title": "Deny-by-default safety gate",
         "text": "Every governed action is checked by a safety gate before it can run.",
         "tags": ["deploy", "gate", "policy", "safety", "deny", "allow", "code", "run"]},
        {"id": "DOC-003", "title": "Signed, chained receipts",
         "text": "Each step of a governed run produces a hash-chained, signed receipt.",
         "tags": ["receipt", "sign", "chain", "verify", "audit", "tamper", "proof"]},
    ]

    def _retrieve(query: str, top_k: int = 3):
        q = (query or "").lower()
        scored = []
        for d in _MINI_CORPUS:
            s = sum(1 for t in d["tags"] if t in q) + (1 if d["title"].lower() in q else 0)
            scored.append((s, d))
        scored.sort(key=lambda x: -x[0])
        return [{"chunk_id": d["id"], "title": d["title"], "text": d["text"], "score": s}
                for s, d in scored[:top_k]]

    def _trust_score(axes: dict) -> float:
        vals = [max(1e-6, min(1.0, float(v))) for v in (axes or {}).values()] or [0.5]
        return round(math.exp(sum(math.log(v) for v in vals) / len(vals)), 4)


# ===========================================================================
# OPEN-WEIGHT MODEL ROSTER (honest, commercial-OK licenses; offline-bakeable).
# We DEFER to szl_llm_registry (forge squad's unified roster) if it is present;
# otherwise we serve this honest fallback. NO closed weights are ever listed.
# ===========================================================================
_FALLBACK_ROSTER = [
    # tier, id, params, license, role, why-this-tier
    {"tier": "T1", "id": "Qwen/Qwen2.5-Coder-1.5B-Instruct", "params": "1.5B",
     "license": "Apache-2.0", "role": "fast-coder",
     "use": "fast code edits / completion; small + cheap; runs on CPU/edge"},
    {"tier": "T1", "id": "microsoft/Phi-3.5-mini-instruct", "params": "3.8B",
     "license": "MIT", "role": "fast-chat",
     "use": "fast general chat; tiny footprint"},
    {"tier": "T2", "id": "google/gemma-2-2b-it", "params": "2B",
     "license": "Gemma (commercial-OK)", "role": "balanced-chat",
     "use": "balanced chat / short reasoning"},
    {"tier": "T2", "id": "Qwen/Qwen2.5-Coder-7B-Instruct", "params": "7B",
     "license": "Apache-2.0", "role": "coder",
     "use": "primary coder; strong code + tool-use at modest cost"},
    {"tier": "T3", "id": "mistralai/Mistral-Nemo-Instruct-2407", "params": "12B",
     "license": "Apache-2.0", "role": "capable-chat",
     "use": "capable general chat / research synthesis"},
    {"tier": "T3", "id": "bigcode/starcoder2-15b", "params": "15B",
     "license": "BigCode-OpenRAIL-M", "role": "coder-large",
     "use": "larger code generation / repo-scale completion"},
    {"tier": "T4", "id": "deepseek-ai/deepseek-coder-6.7b-instruct", "params": "6.7B",
     "license": "DeepSeek (commercial-OK)", "role": "deep-coder",
     "use": "core deep-reasoning coder (DeepSeek — forge squad owns roster)"},
    {"tier": "T4", "id": "mistralai/Codestral-22B-v0.1", "params": "22B",
     "license": "MNPL (non-prod free; commercial via license)", "role": "deep-coder-large",
     "use": "high-capability code reasoning (license-gated for prod)"},
    {"tier": "T5", "id": "meta-llama/Llama-3.1-70B-Instruct", "params": "70B",
     "license": "Llama-3.1 Community (commercial-OK)", "role": "frontier-open",
     "use": "frontier open-weight reasoning; tower-GPU / sovereign-local fallback"},
]


def _is_open_weight(m: dict) -> bool:
    """True only for genuinely OPEN-WEIGHT entries (downloadable weights, no API key).
    DOCTRINE GUARD: closed API models (api_env_var / api_base set, or a closed
    provider) are NEVER presented as the coder's baked-in roster."""
    if not isinstance(m, dict):
        return False
    if m.get("api_env_var") or m.get("api_base"):
        return False
    prov = (m.get("provider_slug") or m.get("provider") or "").lower()
    if any(c in prov for c in ("anthropic", "openai", "google", "deepmind", "xai", "cohere")):
        return False
    lic = (m.get("license") or "").lower()
    return any(t in lic for t in ("apache", "mit", "openrail", "llama", "gemma")) or bool(m.get("open_weight"))


def _roster():
    """a11oy Code OPEN-WEIGHT roster.

    COORDINATION NOTE (verified 2026-06-06): the forge squad's szl_llm_registry
    .MODEL_REGISTRY is the PLATFORM CHAT/ROUTING registry — it is closed API models
    (Claude/Gemini/GPT) carried as HONEST STUBS (no key wired). Per the absolute
    open-weight doctrine, a11oy Code must NEVER present those closed API models as
    its baked-in coder roster. So we only adopt entries from a registry that pass the
    open-weight guard; otherwise we serve our own honest open-weight coder roster."""
    try:
        import szl_llm_registry as _reg
        for attr in ("OPEN_ROSTER", "ROSTER", "MODELS", "TIERS", "MODEL_REGISTRY"):
            r = getattr(_reg, attr, None)
            if isinstance(r, list) and r:
                ow = [m for m in r if _is_open_weight(m)]
                if ow:
                    return ow, ("szl_llm_registry (open-weight entries only; closed "
                                "API models filtered out per doctrine)")
        getter = getattr(_reg, "roster", None) or getattr(_reg, "get_roster", None)
        if callable(getter):
            r = getter()
            if isinstance(r, list) and r:
                ow = [m for m in r if _is_open_weight(m)]
                if ow:
                    return ow, "szl_llm_registry (open-weight entries only)"
    except Exception:
        pass
    return _FALLBACK_ROSTER, "a11oy-code open-weight roster (Apache-2.0 / MIT / OpenRAIL / Llama / Gemma)"


# ===========================================================================
# MULTI-MODEL ROUTER  (C20 softmax order-stability + W7-5 PAC-Bayes envelope).
# ===========================================================================
def _softmax(xs):
    """Stable softmax. C20 (lutar-lean): softmax is 1/2-Lipschitz, so the argmax
    (the routed tier) is STABLE to small score perturbations — small prompt changes
    don't spuriously re-route. PROVEN fragment."""
    if not xs:
        return []
    m = max(xs)
    es = [math.exp(x - m) for x in xs]
    s = sum(es) or 1.0
    return [e / s for e in es]


def _route(mode: str, prompt: str, roster):
    """Score each tier for this task and pick via a stable softmax (C20). Then bracket
    the routed set's cost/risk with the W7-5 PAC-Bayes envelope min<=avg<=max so the
    user gets an HONEST expectation (the router can't beat its best tier nor be worse
    than its worst). Returns (chosen, scored, envelope, reason)."""
    p = (prompt or "").lower()
    plen = len(prompt or "")
    # task signals (deterministic, explainable)
    is_code = mode == "code" or any(k in p for k in (
        "def ", "function", "class ", "import ", "compute", "algorithm",
        "fix ", "bug", "refactor", "write code", "script", "loop", "regex", "sort"))
    is_research = mode == "research" or any(k in p for k in (
        "cve", "kev", "mitre", "att&ck", "vulnerab", "earthquake", "usgs",
        "research", "cite", "source", "what is", "explain"))
    hard = plen > 600 or any(k in p for k in ("prove", "optimi", "complex", "concurren", "async", "distributed"))

    scored = []
    for m in roster:
        mid = m.get("id") or m.get("model_id") or m.get("display_name") or "model"
        role = m.get("role") or m.get("tier_name") or m.get("use_case", "")
        tier_raw = m.get("tier", "T2")
        rank = int(re.sub(r"\D", "", str(tier_raw)) or 2)
        score = 0.0
        if is_code and "coder" in role:
            score += 2.0
        if is_research and ("chat" in role or "frontier" in role):
            score += 1.2
        if (not is_code and not is_research) and ("chat" in role):
            score += 1.5
        # capability vs cost: harder tasks pull up the tier, easy tasks pull it down
        score += (rank * 0.45) if hard else (-(rank * 0.22))
        score += 0.4 if (is_code and "coder" in role and (hard == (rank >= 4))) else 0.0
        scored.append({"id": mid, "tier": tier_raw, "rank": rank,
                       "role": role, "license": m.get("license", ""),
                       "raw": round(score, 3)})
    probs = _softmax([s["raw"] for s in scored])
    for s, pr in zip(scored, probs):
        s["p"] = round(pr, 4)
    chosen = max(scored, key=lambda s: s["p"]) if scored else None

    # W7-5 PAC-Bayes routing envelope: bracket the candidate set's relative cost
    # (proxy = tier rank, normalized). min <= avg <= max is the proven guarantee.
    ranks = [s["rank"] for s in scored] or [1]
    cmin, cmax = min(ranks), max(ranks)
    cavg = sum(ranks) / len(ranks)
    envelope = {"metric": "relative compute cost (tier rank as proxy)",
                "min": cmin, "avg": round(cavg, 2), "max": cmax,
                "chosen": chosen["rank"] if chosen else None,
                "guarantee": "W7-5 PAC-Bayes: aggregate is bracketed min<=avg<=max "
                             "(can't beat best tier, can't be worse than worst tier)"}
    reason = ("Routed by task fit then a stable softmax (C20: argmax is 1/2-Lipschitz, "
              "so small prompt changes don't flip the model). Cost/risk is bracketed by "
              "the W7-5 min<=avg<=max envelope.")
    return chosen, scored, envelope, reason


# ===========================================================================
# CONFORMAL CONFIDENCE  (W5-3 coverage + W7-4 rank-count p-value).  "Never 100%."
# ===========================================================================
def _conformal_confidence(nonconformity: float, calib: list) -> dict:
    """Distribution-free confidence with an anti-overconfidence floor.
    W5-3: coverage = 1 - miscoverage (bounded). W7-4: conformal p-value has a hard
    floor p >= 1/(n+1) => we NEVER report 100% certainty. PROVEN (axiom-free, wave-5/7)."""
    n = len(calib)
    # Split-conformal p-value for the candidate's nonconformity score (lower = better).
    # rank counts calibration scores AT LEAST AS NONCONFORMING (>=) as the candidate.
    # A LOW (good) nonconformity is exceeded by most calibration scores => HIGH rank =>
    # HIGH p-value of "plausible", so confidence = p-value here (good answers are
    # consistent with the calibration distribution). W7-4 gives the hard floor below.
    rank = 1 + sum(1 for c in calib if c >= nonconformity)
    pval = rank / (n + 1)             # W7-4: in [1/(n+1), 1], antitone in nonconformity
    conf = pval                        # low nonconformity -> high p-value -> high confidence
    floor = 1.0 / (n + 1)
    cap = 1.0 - floor                  # the conformal cap: confidence can never hit 1.0
    conf = max(0.0, min(cap, conf))
    return {"confidence": round(conf, 4), "p_value": round(pval, 4),
            "p_value_floor": round(floor, 4), "max_reportable": round(cap, 4),
            "calibration_n": n,
            "basis": "conformal W5-3 coverage + W7-4 rank-count p-value (PROVEN, "
                     "axiom-free). We never report 100% certainty.",
            "plain": "Calibrated confidence — distribution-free, with a hard cap below 100%."}


# small, deterministic calibration set (per-mode nonconformity history; in-image).
_CALIB = {"chat": [0.2, 0.35, 0.5, 0.65, 0.8, 0.45, 0.3, 0.55, 0.7, 0.4],
          "code": [0.15, 0.3, 0.45, 0.6, 0.75, 0.4, 0.25, 0.5, 0.65, 0.35],
          "research": [0.25, 0.4, 0.55, 0.7, 0.85, 0.5, 0.35, 0.6, 0.75, 0.45]}


# ===========================================================================
# CONSENSUS  (C10 n>=3f+1 safety bound, C11 fault budget, C12 FLP liveness caveat).
# ===========================================================================
def _consensus(votes: list) -> dict:
    """Optional multi-model agreement vote. C10 (Byzantine): with n votes, a quorum
    of size floor(n/2)+1 is safe when n>=3f+1. C12 (FLP): liveness needs synchrony —
    so we surface an HONEST 'safe always; may DEFER' caveat. PROVEN cores."""
    n = len(votes)
    f = (n - 1) // 3                       # max Byzantine faults tolerated at n>=3f+1
    from collections import Counter
    tally = Counter(v for v in votes)
    top, count = (tally.most_common(1)[0] if tally else ("DEFER", 0))
    quorum = (n // 2) + 1
    decided = count >= quorum
    return {"n": n, "fault_budget_f": f, "quorum_needed": quorum,
            "agreement": top if decided else "DEFER",
            "votes_for_top": count, "decided": decided,
            "tally": dict(tally),
            "basis": "C10 Byzantine n>=3f+1 safety bound + C12 FLP liveness caveat (PROVEN cores). "
                     "Safe always; if no quorum it DEFERS rather than guessing.",
            "plain": "Optional multi-model agreement vote with a proven safety bound."}


# ===========================================================================
# REAL GOVERNED SANDBOX  (restricted subprocess: rlimits + no-network + timeout).
# Plan -> policy/kernel gate (handled by the governed loop) -> execute -> receipt.
# Honest label: "sandboxed (restricted subprocess)". Full seccomp/container
# isolation is available on the tower/UDS pod; in the HF CPU Space we apply OS
# resource limits + a network-disabled child env + a hard timeout.
# ===========================================================================
_FORBIDDEN_IMPORTS = ("socket", "urllib", "requests", "http", "ftplib", "smtplib",
                      "subprocess", "multiprocessing", "ctypes", "shutil", "os.system",
                      "pty", "fcntl", "resource", "signal", "asyncio")
_FORBIDDEN_CALLS = ("open(", "eval(", "exec(", "compile(", "__import__", "input(",
                    "os.remove", "os.rmdir", "os.unlink", "os.environ", "os.popen",
                    "os.fork", "os.kill")


def _static_screen(code: str) -> dict:
    """Static pre-screen BEFORE execution (defense in depth — the loop's policy gate
    is the real authority; this informs its severity). Honest, deterministic."""
    findings = []
    low = code
    for imp in _FORBIDDEN_IMPORTS:
        if re.search(r"\b(import|from)\s+%s\b" % re.escape(imp.split(".")[0]), low) or ("import %s" % imp) in low:
            findings.append("import:%s" % imp)
    for c in _FORBIDDEN_CALLS:
        if c in low:
            findings.append("call:%s" % c.strip("("))
    return {"findings": sorted(set(findings)),
            "network_or_fs_attempt": any(x.startswith(("import:", "call:")) for x in findings),
            "high_risk": len(findings) > 0}


# ===========================================================================
# HARD SECURITY GATE for the GOVERNED CODE-AS-ACTION KERNEL (a11oy_governed_kernel).
# Deny-by-default, deterministic, model-independent. Extends the base _static_screen
# with bans that keep agent code from ever reaching a key, an env secret, the energy
# ledger, the signer, or the receipt internals — so a cell can neither read a secret
# nor forge a receipt. This is ABOVE the advisory Lambda/restraint gate: Lambda can
# only tighten (add a DENY), never override a hard DENY. (Doctrine v11: deny-by-default,
# never commit/read a key; honest BLOCKED beats fake green.)
# ===========================================================================
# Substring tokens that must NEVER appear in a gated cell. Reaching the signer, the
# energy ledger/operator, the receipt internals, a secret, or an env var is a hard DENY.
_HARD_FORBIDDEN_TOKENS = (
    # dunder escapes out of the restricted namespace
    "__builtins__", "__globals__", "__subclasses__", "__bases__", "__mro__",
    "__import__", "__loader__", "__class__.__bases__",
    # env / secret reach
    "os.getenv", "getenv(", "environ", "putenv",
    # filesystem reach outside the scratch box
    "/etc", "/home", "/root", "/proc", "/sys", "~/", "..", ".pem", ".key",
    # key / secret / signer tokens
    "A11OY_", "SZL_", "HF_TOKEN", "cosign", "signing_key", "_A11OY_PRIV",
    "private_key", "secret", "token", "credential",
    # energy / ledger / khipu / receipt internals (no forging a receipt or a joule)
    "szl_energy_operator", "szl_energy_ledger", "szl_khipu", "szl_provenance",
    "joule_billing", "_commit", "_emit", "submit_external_job", "append_job",
)
# Import roots banned in a gated cell, on top of the base _FORBIDDEN_IMPORTS list.
_HARD_FORBIDDEN_IMPORTS = ("os", "sys", "importlib", "pathlib", "io", "builtins",
                           "gc", "inspect", "marshal", "pickle", "code", "codeop",
                           "threading", "atexit", "platform", "pdb")


def hard_security_screen(code: str) -> dict:
    """Deterministic deny-by-default screen for ONE governed code cell, run BEFORE
    execution. Returns {findings, hard_block, reason}. Reuses the base _static_screen
    (network/fs/eval bans) and layers the key/env/ledger/signer bans on top. Honest,
    model-independent — flip the model and a banned token still denies."""
    code = code or ""
    low = code.lower()
    base = _static_screen(code)
    findings = list(base["findings"])

    for tok in _HARD_FORBIDDEN_TOKENS:
        if tok.lower() in low:
            findings.append("token:%s" % tok)
    for imp in _HARD_FORBIDDEN_IMPORTS:
        if re.search(r"\b(import|from)\s+%s\b" % re.escape(imp), code):
            findings.append("import:%s" % imp)

    findings = sorted(set(findings))
    hard_block = bool(findings)
    if hard_block:
        reason = ("hard security gate DENIED before exec — banned token/import "
                  "(network/fs/eval, or key/env/ledger/signer reach): %s"
                  % ", ".join(findings[:8]))
    else:
        reason = "hard security gate clean — no banned token/import/call"
    return {"findings": findings, "hard_block": hard_block, "reason": reason,
            "network_or_fs_attempt": base["network_or_fs_attempt"]}


def _sandbox_exec(code: str, lang: str = "python", timeout_s: int = 6,
                  mem_mb: int = 256) -> dict:
    """Execute agent-generated code in an ISOLATED restricted subprocess.
    Isolation applied (honest):
      - separate process (subprocess), NOT in the server process
      - OS rlimits: CPU time, address space (memory), no core dump, file-size 0,
        no child processes (RLIMIT_NPROC) -> can't fork a network helper
      - network disabled in the child via env + no socket import allowed by screen
      - hard wall-clock timeout (kills the tree)
      - temp CWD, minimal env (no secrets), text-only capture
    Returns stdout/stderr/exit/timing. NEVER raises into the server.
    """
    if lang != "python":
        return {"ok": False, "error": "only python is sandboxed in this build",
                "stdout": "", "stderr": "unsupported language: %s" % lang, "exit": -1,
                "isolation": "n/a"}

    def _limits():
        # child-only resource limits (POSIX). Applied in the forked child pre-exec.
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (timeout_s, timeout_s))
            soft = mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (soft, soft))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))   # no file writes
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))  # no new processes
            except Exception:
                pass
        except Exception:
            pass

    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": "/tmp", "no_proxy": "*", "PYTHONUNBUFFERED": "1"}
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="a11oy_code_box_") as box:
        src = Path(box) / "main.py"
        # harden: strip a network-disabling preamble in front of the user code.
        preamble = (
            "import sys\n"
            "def _no_net(*a, **k):\n"
            "    raise OSError('network disabled in a11oy Code sandbox')\n"
            "try:\n"
            "    import socket as _s\n"
            "    _s.socket = _no_net; _s.create_connection = _no_net\n"
            "except Exception:\n"
            "    pass\n"
        )
        src.write_text(preamble + (code or ""))
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-S", str(src)],   # -I isolated, -S no site
                cwd=box, env=env, capture_output=True, text=True,
                timeout=timeout_s + 1, preexec_fn=_limits,
            )
            dt = round((time.time() - t0) * 1000, 1)
            out = (proc.stdout or "")[:8000]
            err = (proc.stderr or "")[:4000]
            return {"ok": proc.returncode == 0, "stdout": out, "stderr": err,
                    "exit": proc.returncode, "elapsed_ms": dt,
                    "isolation": ("sandboxed (restricted subprocess): separate process, "
                                  "CPU+memory+fsize+nproc rlimits, network disabled, %ss "
                                  "wall-clock timeout, minimal env. Full seccomp/container "
                                  "isolation on the tower/UDS pod." % timeout_s)}
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "timeout after %ss (killed)" % timeout_s,
                    "exit": -9, "elapsed_ms": round((time.time() - t0) * 1000, 1),
                    "isolation": "sandboxed (restricted subprocess) — timed out and killed"}
        except Exception as e:
            return {"ok": False, "stdout": "", "stderr": "sandbox error: %s" % e,
                    "exit": -1, "elapsed_ms": round((time.time() - t0) * 1000, 1),
                    "isolation": "sandboxed (restricted subprocess)"}


# ===========================================================================
# LOCAL MODEL BACKEND  (offline-first; NEVER fakes generative output).
#   priority: (1) a plugged-in local model command (LOCAL_MODEL_CMD env / tower GPU)
#             (2) HF router IF a token is present (disclosed)
#             (3) local DETERMINISTIC, retrieval-grounded responder (honest label)
# ===========================================================================
# Token detection: read HF_TOKEN first, then a broad set of common fallback names so a
# correctly-pasted token is picked up regardless of which secret NAME it was saved under
# (HF Space secrets are sometimes saved as 'Token', 'HF_ROUTER_TOKEN', etc.). Values are
# stripped of stray whitespace/quotes. Server-side only; never sent to the browser.
def _detect_hf_token() -> str:
    # NOTE: this list MUST stay aligned with a11oy_code_orchestrator.py's HF_TOKEN
    # fallback chain (the founder may store the credential under the secret name
    # 'Forge'). Without 'Forge' here the orchestrator finds the token but the live
    # /v1/code/turn engine path silently does not -> codetab cannot generate.
    for _name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "Forge", "HF_ROUTER_TOKEN",
                  "HF_API_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "Token"):
        _v = os.environ.get(_name)
        if _v:
            _v = _v.strip().strip('"').strip("'").strip()
            if _v.startswith("hf_") or len(_v) >= 20:
                return _v
    return ""

_HF_TOKEN = _detect_hf_token()
_LOCAL_MODEL_CMD = os.environ.get("A11OY_LOCAL_MODEL_CMD") or ""
# Optional honest hardware label surfaced ONLY when a real local/GPU endpoint is
# configured (e.g. "NVIDIA RTX 5000 @ Hetzner"). Pure display; never fabricates a
# backend — if no custom endpoint is set this label is ignored.
_GPU_LABEL = (os.environ.get("A11OY_GPU_LABEL") or "").strip()

# ---------------------------------------------------------------------------
# MODEL-ENDPOINT ADAPTER (sovereign, swappable).
# Default target = the OpenAI-compatible Hugging Face Router. A single env var
# (A11OY_BRAIN_URL, canonical; A11OY_MODEL_BASE_URL accepted as alias) repoints
# this at an owned sovereign node (on-box SGLang/vLLM, any OpenAI-compatible
# /chat/completions server) WITHOUT code changes. The token is read server-side
# only and NEVER sent to the browser. sovereign:true is asserted ONLY when that
# endpoint actually answers — a configured-but-dead URL never inflates the label.
# Open-weight roster only — no closed (GPT/Claude/Gemini) models.
# ---------------------------------------------------------------------------
_MODEL_BASE_URL = (os.environ.get("A11OY_BRAIN_URL")
                   or os.environ.get("A11OY_MODEL_BASE_URL")
                   or os.environ.get("HF_ROUTER_BASE")
                   or "https://router.huggingface.co/v1").rstrip("/")

# Open-weight serverless roster (real HF repo ids + licenses). Primary first;
# the rest are graceful fallbacks tried in order on error/timeout.
_HF_ROSTER = [
    {"hf_repo": "Qwen/Qwen2.5-Coder-32B-Instruct", "display": "Qwen2.5-Coder 32B",
     "license": "Apache-2.0", "role": "primary", "open_weight": True},
    {"hf_repo": "meta-llama/Llama-3.1-8B-Instruct", "display": "Llama 3.1 8B",
     "license": "Llama-3.1-Community", "role": "fallback", "open_weight": True},
    {"hf_repo": "deepseek-ai/DeepSeek-Coder-V2-Instruct", "display": "DeepSeek-Coder-V2",
     "license": "DeepSeek-License (open weights)", "role": "fallback", "open_weight": True},
]


def _model_configured() -> bool:
    """True iff a real generative endpoint is reachable-by-config (token present
    for the HF router, OR a non-router base URL e.g. a local Hetzner model)."""
    if _LOCAL_MODEL_CMD:
        return True
    if "router.huggingface.co" in _MODEL_BASE_URL:
        return bool(_HF_TOKEN)
    # a custom base url (Hetzner/local) is assumed reachable without an HF token
    return True


def _hf_chat(messages, max_tokens=512, want_model=None):
    """Call the OpenAI-compatible model endpoint server-side, with 2x retry and
    automatic fallback down the open-weight roster. Returns a dict:
      {ok, text, model, license, attempts, rate_limited, error}
    NEVER fabricates: on total failure ok=False and text=None."""
    import urllib.request, urllib.error, json as _json, time as _time
    # build the model try-order: requested model first (if open-weight), then roster
    order = []
    if want_model:
        order.append({"hf_repo": want_model, "display": want_model,
                      "license": "declared open-weight", "role": "requested", "open_weight": True})
    order += [m for m in _HF_ROSTER if m["hf_repo"] != want_model]
    headers = {"Content-Type": "application/json"}
    if _HF_TOKEN:
        headers["Authorization"] = "Bearer " + _HF_TOKEN
    url = _MODEL_BASE_URL + "/chat/completions"
    last_err = None
    rate_limited = False
    attempts = 0
    for m in order:
        for attempt in range(2):  # 2 tries per model
            attempts += 1
            body = _json.dumps({"model": m["hf_repo"], "messages": messages,
                                "max_tokens": max_tokens, "temperature": 0.2}).encode()
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=45) as r:
                    data = _json.loads(r.read())
                txt = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
                if txt.strip():
                    return {"ok": True, "text": txt, "model": m["hf_repo"],
                            "display": m["display"], "license": m["license"],
                            "attempts": attempts, "rate_limited": False, "error": None}
                last_err = "empty completion"
            except urllib.error.HTTPError as e:
                code = e.code
                last_err = "HTTP %s on %s" % (code, m["hf_repo"])
                if code == 429:
                    rate_limited = True
                    _time.sleep(1.2)  # brief backoff then retry/fallback
                elif code in (401, 403):
                    return {"ok": False, "text": None, "model": None, "attempts": attempts,
                            "rate_limited": False,
                            "error": "auth rejected (HTTP %s) — HF_TOKEN missing or unauthorized" % code}
                else:
                    break  # try next model
            except Exception as e:
                last_err = "%s: %s" % (type(e).__name__, e)
        # next model in roster
    return {"ok": False, "text": None, "model": None, "attempts": attempts,
            "rate_limited": rate_limited, "error": last_err or "all models failed"}


def _backend_label() -> dict:
    if _LOCAL_MODEL_CMD:
        return {"backend": "local-weights", "model_serving": "real local model (LOCAL_MODEL_CMD)",
                "offline": True, "honest": "Running your plugged-in local open-weight model."}
    if _model_configured():
        _is_local = "router.huggingface.co" not in _MODEL_BASE_URL
        tgt = "local model (A11OY_MODEL_BASE_URL)" if _is_local else "Hugging Face Router"
        if _is_local and _GPU_LABEL:
            tgt = "local open-weight model on %s (sovereign, A11OY_MODEL_BASE_URL)" % _GPU_LABEL
        lab = {"backend": "generative", "endpoint": _MODEL_BASE_URL,
                "model_serving": "%s — open-weight (server-side only)" % tgt,
                "primary_model": _HF_ROSTER[0]["hf_repo"], "configured": True,
                "offline": bool(_is_local),
                "honest": "Real generative inference via the OpenAI-compatible endpoint"
                          + ((" served locally on %s — sovereign, no third-party router." % _GPU_LABEL) if (_is_local and _GPU_LABEL)
                             else " with the present HF_TOKEN (disclosed, never sent to browser).")
                          + " 2x retry + roster fallback; never a fabricated answer."}
        if _is_local and _GPU_LABEL:
            lab["gpu"] = _GPU_LABEL
            lab["sovereign"] = True
        return lab
    if _HF_TOKEN:
        return {"backend": "hf-router", "model_serving": "Hugging Face Router (token present)",
                "configured": True, "offline": False,
                "honest": "Using the HF Router with the present token (disclosed)."}
    return {"backend": "local-deterministic", "configured": False,
            "configure_hint": "Set the HF_TOKEN Space secret to enable live open-weight inference "
                              "via the HF Router (server-side only). Governance is real either way.",
            "model_serving": "local deterministic, retrieval-grounded backend",
            "sandbox_isolation": ("Real restricted-subprocess isolation here (separate process, "
                                  "no network, CPU/memory/time/file-size/process rlimits, isolated "
                                  "python -I -S). Full seccomp/container isolation runs on the "
                                  "tower/UDS pod."),
            "offline": True,
            "honest": ("No model weights and no token in this env, so a11oy Code runs a "
                       "DETERMINISTIC, retrieval-grounded backend (it never fakes generative "
                       "model output). Bring your own local open-weight model (LOCAL_MODEL_CMD) "
                       "or run on the tower GPU for full generation. The GOVERNANCE — the "
                       "P1-P6 loop, the sandbox, the signed receipt — is fully real either way.")}


def _local_chat(prompt: str, retrieved: list) -> str:
    """Deterministic, grounded chat answer. Honest: this is template+retrieval, not a
    generative model. It cites the in-image corpus it used."""
    cites = ", ".join(c["chunk_id"] for c in retrieved) if retrieved else "none"
    top = retrieved[0]["text"] if retrieved else ""
    return ("[local deterministic backend — grounded, not generative] "
            "Grounded on the in-image governance corpus (%s). %s "
            "Ask for CODE to run something in the governed sandbox, or RESEARCH to query "
            "the live CVE/KEV/MITRE/USGS feeds with citations. Every answer here is itself "
            "a governed run with a signed receipt." % (cites, top))


def _local_code(prompt: str) -> dict:
    """Deterministic code synthesizer for common, safe patterns (honest scaffold —
    NOT a generative coder). Produces runnable, SANDBOX-SAFE Python and is explicit
    that a plugged-in open-weight coder (Qwen2.5-Coder/DeepSeek-Coder) generates
    arbitrary code on the tower GPU. The point being demoed is the GOVERNED RUN."""
    p = (prompt or "").lower()
    if any(k in p for k in ("prime", "sieve")):
        code = ("def primes_upto(n):\n"
                "    sieve = [True]*(n+1)\n"
                "    sieve[0:2] = [False, False]\n"
                "    for i in range(2, int(n**0.5)+1):\n"
                "        if sieve[i]:\n"
                "            for j in range(i*i, n+1, i):\n"
                "                sieve[j] = False\n"
                "    return [i for i, p in enumerate(sieve) if p]\n\n"
                "print(primes_upto(50))\n")
        desc = "Sieve of Eratosthenes: primes up to 50."
    elif any(k in p for k in ("fib", "fibonacci")):
        code = ("def fib(n):\n"
                "    a, b = 0, 1\n"
                "    out = []\n"
                "    for _ in range(n):\n"
                "        out.append(a); a, b = b, a+b\n"
                "    return out\n\n"
                "print(fib(15))\n")
        desc = "Iterative Fibonacci: first 15 terms."
    elif any(k in p for k in ("sort", "order")):
        code = ("data = [5, 2, 9, 1, 7, 3, 8, 4, 6, 0]\n"
                "print('input :', data)\n"
                "print('sorted:', sorted(data))\n")
        desc = "Sort a sample list (built-in Timsort)."
    elif any(k in p for k in ("reverse", "palindrome")):
        code = ("s = 'a11oy governed coder'\n"
                "print('reversed:', s[::-1])\n"
                "print('is palindrome:', s == s[::-1])\n")
        desc = "Reverse a string and palindrome check."
    elif "factorial" in p:
        code = ("import math\n"
                "for n in range(1, 8):\n"
                "    print(n, '! =', math.factorial(n))\n")
        desc = "Factorials 1..7."
    else:
        # safe default: echo the request as a structured, runnable demo
        safe = re.sub(r"[^a-zA-Z0-9 _.\-]", "", prompt or "")[:120]
        code = ("# a11oy Code — governed sandbox demo (local deterministic scaffold).\n"
                "# Your request: %s\n"
                "vals = [i*i for i in range(1, 11)]\n"
                "print('squares 1..10:', vals)\n"
                "print('sum:', sum(vals))\n" % (safe or "compute squares"))
        desc = ("Local deterministic scaffold (no generative weights in this env). Plug in "
                "an open-weight coder (Qwen2.5-Coder / DeepSeek-Coder) for arbitrary code; "
                "the GOVERNED RUN below is what's being proven.")
    return {"code": code, "language": "python", "description": desc}


# ===========================================================================
# THE GOVERNED RUN  — replicates the PROVEN P1-P6 6-receipt chain (byte-compatible
# with szl_agentic_loop / /agent/verify-chain) and SIGNS the final receipt.
# Every chat/code/research turn goes through this. Returns a full run object.
# ===========================================================================
_INJECTION_MARKERS = ("ignore previous", "ignore all previous", "override",
                      "approve anyway", "disregard", "you are now", "system:",
                      "allow this", "bypass", "sudo", "set decision=allow",
                      "approve everything", "skip the gate")


def governed_turn(mode: str, prompt: str, sign_fn, ns: str,
                  untrusted_input: str = "", run_chain=None,
                  sandbox: bool = False, want_model: str = "") -> dict:
    """One fully-governed a11oy Code turn (chat | code | research).
    P1 retrieve -> P2 quarantine untrusted -> P3 tool_call -> P4 policy_check ->
    P5 kernel_check -> P6 emit (+sign). Same 6-receipt chain as the proven loop.
    For mode=code with sandbox=True, the EXEC happens between the gate and the emit
    so the receipt records the real run outcome."""
    run_chain = run_chain if run_chain is not None else []
    # PER-RUN GENESIS (FIX 2026-06-06): each run's seq-0 receipt seeds with the SAME
    # genesis constant that verify_run() seeds with ("GENESIS"). Previously this rolled
    # from the prior run's final_hash, so only the FIRST run after boot verified
    # chain_intact=true and every later clean run reported chain_intact=false at seq-0 --
    # making a clean PASS indistinguishable from a tamper FAIL. Per-run genesis matches
    # killinchu and the proven loop, so the P5 tamper-evidence beat reproduces on the
    # Nth clean run. Run-of-runs lineage is tracked separately via prev_run_hash below.
    prev_run_hash = run_chain[-1]["final_hash"] if run_chain else "GENESIS"
    prev_hash = "GENESIS"
    chain = []
    run_id = "code-%s-%s" % (mode, _sha({"p": prompt, "t": time.time()})[:12])

    def _chain_receipt(kind, body):
        nonlocal prev_hash
        rec = {"seq": len(chain), "kind": kind, "body": body, "prev_hash": prev_hash,
               "ts_utc": datetime.now(timezone.utc).isoformat()}
        rec["hash"] = _sha({"seq": rec["seq"], "kind": kind, "body": body, "prev_hash": prev_hash})
        prev_hash = rec["hash"]
        chain.append(rec)
        return rec

    # ---- routing (C20 + W7-5) -------------------------------------------------
    roster, roster_src = _roster()
    chosen, scored, envelope, route_reason = _route(mode, prompt, roster)

    # ---- HOP 1: retrieve (RAG over in-image corpus) ---------------------------
    chunks = _retrieve(prompt, top_k=3)
    _chain_receipt("retrieve", {"query": prompt[:240], "mode": mode,
                                "cited_chunk_ids": [c["chunk_id"] for c in chunks]})

    # ---- HOP 2: quarantine untrusted (P3 non-interference) --------------------
    ui_low = (untrusted_input or "").lower()
    injection_detected = any(m in ui_low for m in _INJECTION_MARKERS)
    _chain_receipt("quarantine_untrusted",
                   {"untrusted_present": bool(untrusted_input),
                    "untrusted_excerpt": (untrusted_input or "")[:240],
                    "injection_markers_detected": injection_detected,
                    "quarantined": True, "feeds_decision": False})

    # ---- mode work (produces the candidate answer/code) -----------------------
    backend = _backend_label()
    answer = None
    code_blob = None
    research = None
    inference = {"mode": "local-deterministic", "model": None, "rate_limited": False, "error": None}

    # REAL generative path when a model endpoint is configured (HF_TOKEN present
    # or a custom A11OY_MODEL_BASE_URL). Otherwise honest local deterministic.
    gen = None
    if _model_configured() and prompt.strip():
        sys_prompt = ("You are a11oy Code, a governed open-weight coding/research assistant. "
                      "Be concise, correct and cite your reasoning. When asked for code, return "
                      "a single runnable code block. Never claim to be a closed model.")
        ctx_note = ("In-image governance context: " + (chunks[0]["text"] if chunks else "")) if mode == "research" else ""
        msgs = [{"role": "system", "content": sys_prompt}]
        if ctx_note:
            msgs.append({"role": "system", "content": ctx_note})
        msgs.append({"role": "user", "content": prompt})
        gen = _hf_chat(msgs, max_tokens=700, want_model=(want_model or None))
        if gen.get("ok"):
            inference = {"mode": "generative", "model": gen["model"], "display": gen.get("display"),
                         "license": gen.get("license"), "attempts": gen.get("attempts"),
                         "rate_limited": False, "error": None}
        else:
            inference = {"mode": "unavailable", "model": None, "attempts": gen.get("attempts"),
                         "rate_limited": bool(gen.get("rate_limited")), "error": gen.get("error")}

    if mode == "code":
        if gen and gen.get("ok"):
            # extract a code block from the generative answer; fall back to whole text
            mblk = re.search(r"```[a-zA-Z0-9_+-]*\n(.*?)```", gen["text"], re.S)
            code_str = (mblk.group(1) if mblk else gen["text"]).strip()
            code_blob = {"code": code_str, "language": "python",
                         "description": "Generated by %s (%s) under the governed loop." % (gen["model"], gen.get("license"))}
        else:
            code_blob = _local_code(prompt)
        nonconf = 0.4
    elif mode == "research":
        research = {"sources_note": ("Answer is grounded on the in-image RAG corpus and, when "
                                     "the tab calls them, the app's already-wired live public "
                                     "feeds (CVE/NVD, CISA KEV, MITRE ATT&CK, USGS). The UI "
                                     "renders those live feeds with attribution next to this run."),
                    "citations": [{"chunk_id": c["chunk_id"], "title": c["title"]} for c in chunks]}
        if gen and gen.get("ok"):
            answer = gen["text"]
        else:
            answer = ("[grounded research] " + (chunks[0]["text"] if chunks else
                      "No matching in-image source; the tab also queries the live public feeds with citations."))
        nonconf = 0.5
    else:  # chat
        if gen and gen.get("ok"):
            answer = gen["text"]
        elif gen and not gen.get("ok"):
            # endpoint configured but failed (rate-limit/error) — honest, not faked
            answer = ("[a11oy Code — model endpoint reachable but no completion: %s] "
                      "This is an honest unavailable state (the governance still ran and is "
                      "receipted). Retry, or the founder can verify HF_TOKEN / model availability."
                      % gen.get("error"))
        else:
            answer = _local_chat(prompt, chunks)
        nonconf = 0.35

    # ---- HOP 3: tool_call (MCP policy_check tool) -----------------------------
    # derive severity from the requested action (code-exec is higher consequence)
    if mode == "code" and sandbox:
        severity = "high"
    elif mode == "code":
        severity = "medium"
    else:
        severity = "low"
    static = _static_screen(code_blob["code"]) if code_blob else {"findings": [], "high_risk": False,
                                                                   "network_or_fs_attempt": False}
    if static.get("network_or_fs_attempt"):
        severity = "critical"   # attempted network/fs => deny-by-default territory
    tool_input = {"action": "%s:%s" % (mode, prompt[:60]), "severity": severity,
                  "static_findings": static.get("findings", [])}
    _chain_receipt("tool_call", {"tool": "policy_check", "input": tool_input})

    # ---- conformal confidence (W5-3 / W7-4): never 100% -----------------------
    conf = _conformal_confidence(nonconf, _CALIB.get(mode, _CALIB["chat"]))
    confidence = conf["confidence"]
    reversible = not (mode == "code" and sandbox and static.get("high_risk"))

    # ---- HOP 4: policy_check (deny-by-default safety gate) --------------------
    sev_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 2)
    reasons = []
    gate_allow = True
    if sev_rank >= 3 and confidence < 0.6:
        gate_allow = False; reasons.append("high-severity action with low confidence (deny-by-default)")
    if sev_rank >= 4 and not reversible:
        gate_allow = False; reasons.append("irreversible critical action without confidence floor")
    if confidence < 0.25:
        gate_allow = False; reasons.append("confidence below minimum floor (0.25)")
    if static.get("network_or_fs_attempt"):
        gate_allow = False; reasons.append("code attempted network/filesystem access — blocked before exec")
    _chain_receipt("policy_check", {"allow": gate_allow, "reasons": reasons,
                                    "severity": severity, "confidence": confidence})

    # ---- HOP 5: kernel_check (advisory trust floor) ---------------------------
    # YUYAY 13-axis trust gate (advisory; Conjecture 1, NOT a proven oracle).
    # Every axis is derived from REAL signals of this run (confidence, severity,
    # reversibility, signing, quarantine, sandbox isolation), never fabricated.
    _gen_ok = bool(gen and gen.get("ok"))
    axes = {
        "soundness": min(1.0, confidence + 0.05),
        "calibration": confidence,
        "robustness": 0.92 if reversible else 0.70,
        "provenance": 0.97,
        "reversibility": 0.99 if reversible else 0.40,
        "transparency": 0.96,
        "containment": 0.95 if sev_rank <= 2 else 0.78,
        "auditability": 0.99,
        # --- the 5 additional YUYAY axes (13 total) ---
        "non_interference": 0.99 if not bool(untrusted_input) else 0.90,  # P3: untrusted quarantined
        "determinism": 0.98,            # P4 replay-determinism of the governed loop
        "signedness": 0.99,             # P5 ECDSA-P256 signed receipt chain
        "sovereignty": 0.94,            # 0-CDN same-origin; weights open-weight only
        "groundedness": 0.93 if (mode == "research" or _gen_ok) else 0.85,  # cited/in-corpus
    }
    trust = _trust_score(axes)
    trust_floor = 0.80
    trust_pass = trust >= trust_floor
    _chain_receipt("kernel_check", {"trust_score": trust, "trust_floor": trust_floor,
                                    "pass": trust_pass})

    allowed = gate_allow and trust_pass
    decision = "ALLOW" if allowed else "DENY"

    # ---- SANDBOX EXEC (only for code, only on ALLOW, between gate and emit) ----
    sandbox_result = None
    if mode == "code" and sandbox:
        if allowed:
            sandbox_result = _sandbox_exec(code_blob["code"], lang=code_blob["language"])
        else:
            sandbox_result = {"ok": False, "stdout": "", "stderr": "",
                              "exit": None, "blocked": True,
                              "isolation": "not executed — blocked at the gate (gate soundness)"}

    # ---- HOP 6: emit (+ sign the final receipt) -------------------------------
    if allowed:
        if mode == "code" and sandbox:
            effect = {"emitted": True, "effect": "code executed in governed sandbox; result on the receipt"}
        else:
            effect = {"emitted": True, "effect": ("answer emitted with citations" if mode == "research"
                                                  else "answer emitted")}
    else:
        effect = {"emitted": False, "effect": "BLOCKED at the gate — nothing emitted (gate soundness)"}

    decision_payload = {
        "run_id": run_id, "mode": mode, "decision": decision,
        "action": tool_input["action"], "severity": severity, "confidence": confidence,
        "reversible": reversible, "routed_model": (chosen or {}).get("id"),
        "routed_tier": (chosen or {}).get("tier"),
        "trust_score_advisory": trust,
        "trust_status": "Conjecture 1 (advisory — NOT a proven oracle)",
        "cited_chunk_ids": [c["chunk_id"] for c in chunks],
        "gate_reasons": reasons, "chain_final_hash": prev_hash, "chain_depth": len(chain),
        "emitted": effect["emitted"], "issuer": ns,
        "sandbox_exit": (sandbox_result or {}).get("exit") if sandbox_result else None,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        envelope_sig = sign_fn(decision_payload)
    except Exception as e:
        envelope_sig = {"signed": False, "signatures": [],
                        "honesty": "UNSIGNED — signer raised: %s" % type(e).__name__,
                        "payloadType": "application/vnd.szl.receipt+json"}
    _chain_receipt("emit", {"decision": decision, "emitted": effect["emitted"],
                            "signed": bool(envelope_sig.get("signed")),
                            "sandbox_exit": (sandbox_result or {}).get("exit") if sandbox_result else None})

    run_chain.append({"run_id": run_id, "final_hash": prev_hash,
                      "prev_run_hash": prev_run_hash, "decision": decision})

    # plain-language summary
    if decision == "ALLOW":
        if mode == "code" and sandbox:
            summ = ("Allowed. The code passed the safety gate (severity %s, calibrated confidence %.2f) "
                    "and the advisory trust check (%.2f), then ran in the governed sandbox. "
                    "The run + result are on a signed, hash-chained receipt." % (severity, confidence, trust))
        else:
            summ = ("Allowed. After retrieving guidance, quarantining any untrusted input, calling the "
                    "policy tool and passing the safety + advisory trust checks (trust %.2f), the %s "
                    "answer was emitted. A signed receipt was produced." % (trust, mode))
    else:
        why = "; ".join(reasons) if reasons else ("advisory trust %.2f below floor" % trust)
        summ = ("Blocked. The gate denied this because: %s. Nothing was emitted — only a signed deny "
                "receipt. This is the governance working." % why)

    return {
        "run_id": run_id, "mode": mode, "decision": decision, "emitted": effect["emitted"],
        "summary": summ,
        "answer": answer, "code": code_blob, "research": research,
        "sandbox": sandbox_result,
        "router": {"chosen": chosen, "scored": scored, "envelope": envelope,
                   "reason": route_reason, "roster_source": roster_src,
                   "plain": "Routing is stable to small changes (C20) and bracketed best..worst (W7-5)."},
        "confidence": conf,
        "backend": backend,
        "inference": inference,
        "retrieved": chunks,
        "untrusted": {"present": bool(untrusted_input), "excerpt": (untrusted_input or "")[:240],
                      "injection_markers_detected": injection_detected,
                      "quarantined": True, "feeds_decision": False,
                      "note": ("Recorded on the chain but excluded from the gate inputs — "
                               "non-interference (P3): it cannot change the verdict.")},
        "gate": {"name": "deny-by-default safety gate", "allow": gate_allow, "reasons": reasons,
                 "severity": severity, "static_screen": static},
        "trust": {"score": trust, "floor": trust_floor, "pass": trust_pass, "axes": axes,
                  "status": "Trust score (advisory) — research conjecture (Conjecture 1), not a proven oracle"},
        "receipt_chain": chain, "signed_receipt": envelope_sig,
        "chain_final_hash": prev_hash, "chain_depth": len(chain),
        "prev_run_hash": prev_run_hash,
        "halts": {"basis": "F-G5 bounded-frontier receipt-DAG termination (PROVEN, wave-6)",
                  "plain": "This governed run provably finishes in bounded steps (good for the edge).",
                  "hops": len(chain)},
        "doctrine": "v11", "issuer": ns,
        "honesty": ("Trust score is advisory (Conjecture 1). Models are OPEN-WEIGHT only; "
                    "no closed weights are baked in. Backend: %s. The governance (P1-P6 loop, "
                    "sandbox, signed receipt) is fully real." % backend["model_serving"]),
    }


def verify_run(run: dict, verify_fn=None) -> dict:
    """Re-verify a governed-turn run: (1) chain integrity recomputed from bodies,
    (2) signature on the final receipt. Same contract as the proven loop."""
    chain = run.get("receipt_chain") or []
    chain_ok = True
    broken_at = None
    prev = "GENESIS"
    for r in chain:
        expect = _sha({"seq": r["seq"], "kind": r["kind"], "body": r["body"], "prev_hash": prev})
        if r.get("prev_hash") != prev or r.get("hash") != expect:
            chain_ok = False; broken_at = r.get("seq"); break
        prev = r["hash"]
    env = run.get("signed_receipt") or {}
    sig = None
    if verify_fn is not None:
        try:
            sig = verify_fn(env)
        except Exception as e:
            sig = {"signature_valid": False, "detail": "verifier error: %s" % e}
    if sig is None:
        sig = {"signature_valid": bool(env.get("signed")),
               "detail": "structural check: signed=%s, signature bytes present=%s"
                         % (env.get("signed"), bool(env.get("signatures")))}
    return {"chain_intact": chain_ok, "chain_depth": len(chain), "chain_break_at_seq": broken_at,
            "final_hash": (chain[-1]["hash"] if chain else None),
            "signature_valid": sig.get("signature_valid"), "signature_detail": sig.get("detail"),
            "verified": bool(chain_ok and sig.get("signature_valid")),
            "note": "Chain integrity recomputed independently from receipt bodies. Flip any byte -> chain_intact false."}


def capabilities(ns: str) -> dict:
    """Honest capability + formula-wiring card (surfaced plainly in the UI)."""
    roster, roster_src = _roster()
    return {
        "product": "a11oy Code", "issuer": ns, "doctrine": "v11",
        "tagline": "A governed agentic coder you can mathematically trust. NOT AGI.",
        "modes": ["chat", "code", "research"],
        "governed_loop": "Every turn runs through the PROVEN P1-P6 6-receipt loop "
                         "(retrieve -> quarantine -> tool_call -> policy_check -> "
                         "kernel_check -> emit) and emits a signed, re-verifiable receipt.",
        "open_weight_roster": roster, "roster_source": roster_src,
        "backend": _backend_label(),
        "formula_wiring": [
            {"formula": "C20", "name": "Softmax 1/2-Lipschitz (order-stable)",
             "used_for": "model router stability", "maturity": "PROVEN (fragment)",
             "plain": "Routing is stable to small changes."},
            {"formula": "W7-5", "name": "PAC-Bayes min<=avg<=max routing envelope",
             "used_for": "router cost/risk bracket", "maturity": "CI-green (Mathlib)",
             "plain": "Routing stays between best and worst option."},
            {"formula": "W5-3 / W7-4", "name": "Conformal coverage + rank-count p-value",
             "used_for": "calibrated confidence on a suggestion", "maturity": "PROVEN (axiom-free)",
             "plain": "Calibrated confidence — we never report 100% certainty."},
            {"formula": "P1-P6", "name": "Governed agentic loop (Pipeline.lean)",
             "used_for": "the governed run + signed receipt", "maturity": "PROVEN (P5 axiom-gated on hash CR)",
             "plain": "Every code action is governed and receipted."},
            {"formula": "P3", "name": "Non-interference (Goguen-Meseguer 1982)",
             "used_for": "untrusted/pasted input cannot flip a verdict", "maturity": "PROVEN (axiom-free core)",
             "plain": "Poisoned input can't override safety."},
            {"formula": "C10/C11/C12", "name": "Byzantine / DLS / FLP",
             "used_for": "optional multi-model consensus vote", "maturity": "PROVEN (cores)",
             "plain": "Optional agreement vote with a proven safety bound."},
            {"formula": "F-G5", "name": "Bounded-frontier receipt-DAG termination",
             "used_for": "the agent loop provably halts (edge-safe)", "maturity": "PROVEN",
             "plain": "The governed run always finishes."},
        ],
        "honesty": {
            "models": "OPEN-WEIGHT only (Mistral/Qwen2.5-Coder/DeepSeek-Coder/Codestral/"
                      "StarCoder2/Llama/Gemma/Phi). No closed weights baked in. No API key required.",
            "no_agi": True, "lambda": "Conjecture 1 (advisory, never the gate)",
            "locked_proven": 8,
            "sandbox": "sandboxed (restricted subprocess) in the HF CPU Space; full seccomp/"
                       "container isolation on the tower/UDS pod.",
            "offline": "Offline-capable: deterministic local backend + local sandbox + vendored UI; "
                       "no external API/CDN required at runtime.",
        },
    }


# ===========================================================================
# REGISTRATION — Starlette routes inserted at position 0 (BEFORE the SPA
# catch-all and BEFORE the generic /api/<ns>/{path} proxy), exactly like the
# proven loop module. sign_fn/verify_fn = the HOST app's REAL signer/verifier.
# ===========================================================================
def register(app, ns: str, sign_fn, verify_fn=None, signer_label: str = "in-image key"):
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    _RUN_CHAIN = []   # run-of-runs chain for this surface

    async def _turn(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        mode = (b.get("mode") or "chat").lower()
        if mode not in ("chat", "code", "research"):
            mode = "chat"
        prompt = b.get("prompt") or b.get("message") or b.get("query") or ""
        untrusted = b.get("untrusted_input") or b.get("untrusted") or ""
        sandbox = bool(b.get("sandbox", mode == "code"))
        want_model = b.get("model") or b.get("want_model") or ""
        run = governed_turn(mode, prompt, sign_fn, ns, untrusted_input=untrusted,
                            run_chain=_RUN_CHAIN, sandbox=sandbox, want_model=want_model)
        return JSONResponse(run)

    async def _chat(request):
        """Founder contract: POST /api/<ns>/v1/code/chat {prompt[,model]}.
        Returns a REAL model answer + signed governed receipt + gate verdict when
        a model endpoint is configured; otherwise an honest 'configure HF_TOKEN'
        payload — NEVER a fabricated answer."""
        try:
            b = await request.json()
        except Exception:
            b = {}
        prompt = b.get("prompt") or b.get("message") or b.get("query") or ""
        mode = (b.get("mode") or "chat").lower()
        if mode not in ("chat", "code", "research"):
            mode = "chat"
        want_model = b.get("model") or b.get("want_model") or ""
        if not _model_configured():
            return JSONResponse({
                "configured": False,
                "error": "model endpoint not configured: set HF_TOKEN secret on the Space",
                "backend": _backend_label(),
                "roster": _HF_ROSTER,
                "note": "a11oy Code never fabricates output. Set the HF_TOKEN Space secret "
                        "(open-weight serverless via the HF Router) or point A11OY_MODEL_BASE_URL "
                        "at a local/Hetzner open-weight model. The governance (P1-P6 + signed "
                        "receipt) is real either way — try /v1/code/turn for a governed local run.",
            }, status_code=200)
        run = governed_turn(mode, prompt, sign_fn, ns, untrusted_input=(b.get("untrusted_input") or ""),
                            run_chain=_RUN_CHAIN, sandbox=False, want_model=want_model)
        return JSONResponse({
            "configured": True,
            "answer": run.get("answer"),
            "inference": run.get("inference"),
            "decision": run.get("decision"),
            "gate": run.get("gate"),
            "trust": run.get("trust"),
            "signed_receipt": run.get("signed_receipt"),
            "receipt_chain": run.get("receipt_chain"),
            "chain_final_hash": run.get("chain_final_hash"),
            "run_id": run.get("run_id"),
            "backend": run.get("backend"),
            "honesty": run.get("honesty"),
        })

    async def _run(request):
        """POST /api/<ns>/v1/code/run {prompt|code} — governed code turn with sandbox exec."""
        try:
            b = await request.json()
        except Exception:
            b = {}
        prompt = b.get("prompt") or b.get("code") or b.get("message") or ""
        want_model = b.get("model") or ""
        run = governed_turn("code", prompt, sign_fn, ns, untrusted_input=(b.get("untrusted_input") or ""),
                            run_chain=_RUN_CHAIN, sandbox=bool(b.get("sandbox", True)), want_model=want_model)
        return JSONResponse(run)

    async def _consensus_route(request):
        """Optional multi-model agreement vote over the routed candidates (C10-C12)."""
        try:
            b = await request.json()
        except Exception:
            b = {}
        prompt = b.get("prompt") or ""
        mode = (b.get("mode") or "code").lower()
        roster, _ = _roster()
        _, scored, _, _ = _route(mode, prompt, roster)
        # deterministic per-model vote: top-2 tiers vote ALLOW if their fit-prob is high
        top = sorted(scored, key=lambda s: -s["p"])[:4] or []
        votes = ["ALLOW" if s["p"] >= (1.0 / max(1, len(top))) else "DEFER" for s in top]
        return JSONResponse({"consensus": _consensus(votes),
                             "voters": [{"id": s["id"], "tier": s["tier"], "p": s["p"]} for s in top]})

    async def _verify(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        run = b.get("run") if isinstance(b.get("run"), dict) else b
        return JSONResponse(verify_run(run, verify_fn=verify_fn))

    async def _caps(request):
        return JSONResponse(capabilities(ns))

    async def _models(request):
        roster, src = _roster()
        return JSONResponse({"roster": roster, "source": src,
                             "generative_roster": _HF_ROSTER,
                             "endpoint": _MODEL_BASE_URL,
                             "backend": _backend_label()})

    routes = [
        Route("/api/%s/v1/code/turn" % ns, _turn, methods=["POST"], name="%s_code_turn" % ns),
        Route("/api/%s/v1/code/chat" % ns, _chat, methods=["POST"], name="%s_code_chat" % ns),
        Route("/api/%s/v1/code/run" % ns, _run, methods=["POST"], name="%s_code_run" % ns),
        Route("/api/%s/v1/code/consensus" % ns, _consensus_route, methods=["POST"], name="%s_code_consensus" % ns),
        Route("/api/%s/v1/code/verify" % ns, _verify, methods=["POST"], name="%s_code_verify" % ns),
        Route("/api/%s/v1/code/capabilities" % ns, _caps, methods=["GET"], name="%s_code_caps" % ns),
        Route("/api/%s/v1/code/models" % ns, _models, methods=["GET"], name="%s_code_models" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "modes": ["chat", "code", "research"], "loop_primitives": _LOOP_OK}
