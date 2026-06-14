# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by the NEMOTRON SIGNED-TRAJECTORY build team. Co-Authored-By: Perplexity Computer Agent.
"""
szl_trajectory_sign — DSSE-signed agent-trajectory receipts (SZL-Nemo, NOW slice).

WHAT THIS IS (honest framing — read before extending):
    This module instruments the EXISTING SZL agent loop (ReAct + Reflexion +
    Restraint + Auto-Review) to emit a DSSE-SIGNED JSONL receipt per step. Each
    JSONL line is a self-contained, cryptographically-attested record of one
    agent step: {step, role, action, observation, restraint_verdict, ...,
    signature}. The collection of these lines is a "signed agent-trajectory
    corpus" that is QLoRA-ready and verifiable by anyone via a signature check.

WHAT THIS IS *NOT* (never claim otherwise — Doctrine honesty gates):
    - This is a DATASET property (signed, provenance-attested trajectories),
      NOT a model claim. No model is trained here.
    - We did NOT reproduce Nemotron Ultra and did NOT train from scratch. The
      full Ultra reproduction is impossible from open artifacts (intermediate
      MOPD teacher checkpoints were never released — see NVIDIA MOPD docs).
    - Actual QLoRA / GRPO training needs >=2x80GB GPUs and is ROADMAP (the Forge
      order, FORGE_NEMOTRON_TRAIN.md). This module runs on CPU only.
    - SZL-Nemo (the future student) = a GOVERNED fine-tune of Qwen3-32B (Apache);
      it is not Ultra and not from-scratch.

SIGNING:
    Reuses szl_dsse.sign_payload (ECDSA-P256-SHA256 over the DSSE PAE, backed by
    the SZLHOLDINGS Cosign keypair). When the SZL_COSIGN_PRIVATE_KEY_PEM runtime
    secret is absent the receipt is emitted as an HONEST UNSIGNED envelope
    (signatures: [], honesty marker) — a signature is NEVER fabricated. The
    public key (cosign.pub) is embedded in szl_dsse for offline verification.

SCHEMA (one JSONL line per step):
    {
      "schema": "szl.nemo.trajectory.step/v1",
      "trajectory_id": "<uuid4>",
      "step": <int>,                       # 0-based step index
      "role": "assistant" | "tool" | "user",
      "pattern": "ReAct"|"Reflexion"|"Restraint"|"AutoReview",
      "action": {...} | str,               # the agent's action / tool call
      "observation": str,                  # tool result / environment feedback
      "restraint_verdict": "ALLOW"|"HOLD"|"MONITOR"|"DECLINE",
      "is_correction": bool,               # Reflexion backtrack?
      "correction_of": <int> | null,
      "step_hash": "sha256:<hex>",         # sha256 over canonical(step content)
      "signature": <DSSE envelope dict>,   # signed | honest-unsigned
      "agent_id": "szl-nemo-trajectory-v1",
      "timestamp_utc": "<ISO8601>"
    }
ADDITIVE · stdlib + szl_dsse only · pure-ish (signing reads a runtime secret).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

STEP_SCHEMA = "szl.nemo.trajectory.step/v1"
TRAJ_SCHEMA = "szl.nemo.trajectory/v1"
STEP_PAYLOAD_TYPE = "application/vnd.szl.nemo.trajectory.step+json"
AGENT_ID = "szl-nemo-trajectory-v1"

# Canonical SZL agent patterns (the four loops we instrument).
PATTERNS = ("ReAct", "Reflexion", "Restraint", "AutoReview")
# Restraint verdicts — "never engage on doubt": HOLD/MONITOR are the safe defaults.
VERDICTS = ("ALLOW", "HOLD", "MONITOR", "DECLINE")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def step_hash(action: Any, observation: Any, restraint_verdict: str) -> str:
    """Deterministic SHA-256 over the step's signable content."""
    body = _canon({"action": action, "observation": observation,
                   "restraint_verdict": restraint_verdict})
    return "sha256:" + hashlib.sha256(body).hexdigest()


def new_trajectory_id() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Signing
# --------------------------------------------------------------------------- #
def _sign(payload: Dict[str, Any]) -> Dict[str, Any]:
    """DSSE-sign a step payload; honest-unsigned fallback if no key. Never raises."""
    try:
        import szl_dsse
        return szl_dsse.sign_payload(payload, STEP_PAYLOAD_TYPE)
    except Exception as exc:  # honest degrade, never fabricate
        return {
            "payloadType": STEP_PAYLOAD_TYPE,
            "signatures": [],
            "signed": False,
            "honesty": f"UNSIGNED — signer module unavailable ({type(exc).__name__}); "
                       "no signature fabricated.",
        }


def signing_available() -> bool:
    try:
        import szl_dsse
        return bool(szl_dsse.signing_available())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Per-step receipt builder
# --------------------------------------------------------------------------- #
def sign_step(
    *,
    trajectory_id: str,
    step: int,
    action: Any,
    observation: Any = "",
    role: str = "assistant",
    pattern: str = "ReAct",
    restraint_verdict: str = "ALLOW",
    is_correction: bool = False,
    correction_of: Optional[int] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build ONE DSSE-signed trajectory-step receipt (the JSONL line dict).

    The signature commits to the {action, observation, restraint_verdict} content
    via the canonical step payload, so any third party can re-derive the PAE and
    verify it against the published cosign.pub.
    """
    if pattern not in PATTERNS:
        pattern = "ReAct"
    if restraint_verdict not in VERDICTS:
        restraint_verdict = "MONITOR"  # honest default: never assume ALLOW on doubt
    sh = step_hash(action, observation, restraint_verdict)
    # The signed payload is the content-bearing core (stable, dedup-friendly).
    payload = {
        "schema": STEP_SCHEMA,
        "trajectory_id": trajectory_id,
        "step": int(step),
        "role": role,
        "pattern": pattern,
        "action": action,
        "observation": observation,
        "restraint_verdict": restraint_verdict,
        "is_correction": bool(is_correction),
        "correction_of": correction_of,
        "tool_calls": tool_calls or [],
        "step_hash": sh,
        "agent_id": AGENT_ID,
        "timestamp_utc": _utcnow_iso(),
    }
    if extra:
        payload["extra"] = extra
    envelope = _sign(payload)
    line = dict(payload)
    line["signature"] = envelope
    return line


# --------------------------------------------------------------------------- #
# Trajectory recorder — wraps an agent run, emits signed JSONL
# --------------------------------------------------------------------------- #
class SignedTrajectory:
    """Accumulate DSSE-signed step receipts for one agent run, then seal.

    Usage (instrumentation point — wrap the existing loop's step()):
        t = SignedTrajectory(task="counter-UAS track+classify", environment="cuas")
        t.add(action="track_air_vehicle(...)", observation="3 tracks", pattern="ReAct")
        t.add(action="classify_threat(...)", observation="ERROR: no IFF",
              restraint_verdict="HOLD", pattern="Restraint")
        t.add(action="retry classify with EO/IR", observation="hostile UAS",
              is_correction=True, correction_of=1, pattern="Reflexion")
        sealed = t.seal(outcome="success")           # provenance block + JSONL
    """

    def __init__(self, *, task: str = "", environment: str = "szl",
                 trajectory_id: Optional[str] = None,
                 label: str = "SAMPLE"):
        self.trajectory_id = trajectory_id or new_trajectory_id()
        self.task = task
        self.environment = environment
        self.label = label  # LIVE | SAMPLE | MODELED — honesty surface
        self.steps: List[Dict[str, Any]] = []

    def add(self, **kwargs: Any) -> Dict[str, Any]:
        step = len(self.steps)
        line = sign_step(trajectory_id=self.trajectory_id, step=step, **kwargs)
        self.steps.append(line)
        return line

    def jsonl(self) -> str:
        return "\n".join(json.dumps(s, ensure_ascii=False) for s in self.steps)

    def provenance(self, outcome: str = "unknown") -> Dict[str, Any]:
        corrections = sum(1 for s in self.steps if s.get("is_correction"))
        verdicts = [s.get("restraint_verdict") for s in self.steps]
        signed = sum(1 for s in self.steps
                     if (s.get("signature", {}) or {}).get("signed"))
        return {
            "schema": TRAJ_SCHEMA,
            "trajectory_id": self.trajectory_id,
            "task": self.task,
            "environment": self.environment,
            "label": self.label,
            "signer": AGENT_ID,
            "signed_at": _utcnow_iso(),
            "total_steps": len(self.steps),
            "corrections": corrections,
            "verdicts": verdicts,
            "signed_steps": signed,
            "all_signed": signed == len(self.steps) and len(self.steps) > 0,
            "outcome": outcome,
            "source": "szl",
            "verified": False,  # signatures present; independent verify is the user's job
            "honesty": (
                "DSSE-signed agent-trajectory corpus (DATASET property, not a model "
                "claim). QLoRA-ready; actual training = ROADMAP (needs 2x80GB GPU). "
                "Not an Ultra reproduction; not trained from scratch."
            ),
        }

    def seal(self, outcome: str = "unknown") -> Dict[str, Any]:
        return {"provenance": self.provenance(outcome), "steps": self.steps,
                "jsonl": self.jsonl()}


# --------------------------------------------------------------------------- #
# Verifier — anyone can run this to check every step signature
# --------------------------------------------------------------------------- #
def verify_step(line: Dict[str, Any]) -> Dict[str, Any]:
    """Verify ONE signed-step JSONL line: re-derive step_hash AND verify the DSSE
    signature against the embedded payload. Returns a structured verdict."""
    out: Dict[str, Any] = {"trajectory_id": line.get("trajectory_id"),
                           "step": line.get("step")}
    # 1) content integrity: recompute step_hash
    recomputed = step_hash(line.get("action"), line.get("observation", ""),
                           line.get("restraint_verdict", "ALLOW"))
    out["hash_ok"] = (recomputed == line.get("step_hash"))
    # 2) signature: verify the DSSE envelope (if signed)
    env = line.get("signature") or {}
    sigs = env.get("signatures") or []
    if not sigs:
        out["signed"] = False
        out["sig_ok"] = False
        out["reason"] = env.get("honesty", "unsigned")
        return out
    out["signed"] = True
    try:
        import szl_dsse
        verdict = szl_dsse.verify_envelope(env)
        out["sig_ok"] = bool(verdict.get("verified"))
        out["sig_detail"] = verdict
    except Exception as exc:
        out["sig_ok"] = False
        out["reason"] = f"{type(exc).__name__}: {exc}"
    return out


def verify_jsonl(text: str) -> Dict[str, Any]:
    """Verify every step in a JSONL corpus blob. Returns aggregate stats."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    results = []
    for ln in lines:
        try:
            results.append(verify_step(json.loads(ln)))
        except Exception as exc:
            results.append({"parse_error": f"{type(exc).__name__}: {exc}"})
    total = len(results)
    hash_ok = sum(1 for r in results if r.get("hash_ok"))
    signed = sum(1 for r in results if r.get("signed"))
    sig_ok = sum(1 for r in results if r.get("sig_ok"))
    return {
        "total_steps": total,
        "hash_ok": hash_ok,
        "signed": signed,
        "sig_ok": sig_ok,
        "all_hash_ok": hash_ok == total and total > 0,
        "all_sig_ok": sig_ok == total and total > 0,
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Self-check (pure)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    t = SignedTrajectory(task="demo self-check", environment="selftest")
    t.add(action="step A", observation="ok", pattern="ReAct")
    t.add(action="step B", observation="ERROR", restraint_verdict="HOLD",
          pattern="Restraint")
    t.add(action="retry B", observation="ok", is_correction=True,
          correction_of=1, pattern="Reflexion")
    sealed = t.seal(outcome="success")
    v = verify_jsonl(sealed["jsonl"])
    assert v["total_steps"] == 3
    assert v["all_hash_ok"], v
    print(json.dumps({"signing_available": signing_available(),
                      "provenance": sealed["provenance"], "verify": {
                          k: v[k] for k in ("total_steps", "all_hash_ok",
                                            "signed", "sig_ok")}}, indent=2))
