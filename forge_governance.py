"""
forge_governance.py — SZL-native runtime governance for Forge (our own autonomous agent).

GAP 5 (shared/GAPS.md): "We have the gate; we're MISSING standardized hooks, a
replayable execution ledger, and kill switches for Forge itself. Forge already writes
signed exec receipts — extend to a full replayable decision ledger + an explicit kill
switch + ACS-style middleware hooks. This makes Forge itself auditable."

What this module is
-------------------
A clean-room, pure-stdlib, deny-by-default runtime governor that wraps Forge's existing
auto-loop (replit-sync/NEXT_ORDER.md  <->  AUTO_STATE.json) into a tamper-evident,
*replayable* governed decision ledger. It answers the three production questions the
Microsoft Agent Governance Toolkit poses for any autonomous agent:
  1. Is this action allowed?   -> privilege rings + deny-by-default policy (PRE hook)
  2. Which agent did it?        -> every entry carries actor + active-policy fingerprint
  3. Can you prove it happened? -> append-only hash-chained ledger, replay() reproduces it

Design citations (see FINDINGS.md for full URLs):
  * Agent Control Standard (ACS) — open runtime-governance standard launched 2026-05-27.
    Three layers Instrument / Trace / Inspect; four interception points (before input,
    before tool call, after tool returns, before final response); declarative policy with
    allow / warn / deny / escalate verdicts. We implement the two load-bearing hooks:
    pre_action(ctx) -> Decision   and   post_action(ctx, result) -> LedgerEntry.
  * Microsoft Agent Governance Toolkit — a deterministic policy engine intercepts every
    tool call BEFORE the model's intent "reaches the wire", which is what makes a blocked
    action "structurally impossible" rather than merely discouraged; denied actions raise
    GovernanceDenied; the audit log is tamper-evident and references the agent's identity.
    We enforce the same: forbidden/kill-switched actions raise GovernanceDenied and can
    never produce a success receipt.
  * MLflow structured audit logging / tracing — every action recorded as a structured
    record with inputs, outputs, decision and metadata, so behaviour is *measured*, not
    guessed. Our LedgerEntry is that structured trace, hardened with a hash chain.

Doctrine v11 (HARD): no fabricated numbers/flags/signatures. The ledger NEVER fabricates
a decision — there is no entry without a real policy evaluation. A signature is NOT proof
of safety, so this ledger is advisory + tamper-evident, never "proven trust" (Λ =
Conjecture 1). The hash chain is khipu-style: each knot's hash binds the previous knot.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Decisions (ACS-style verdict vocabulary)                                    #
# --------------------------------------------------------------------------- #
class Decision(str, Enum):
    """ACS-style runtime verdicts. We map ACS allow/warn/deny/escalate onto the
    Forge auto-loop's observed vocabulary (done / gated_skipped / blocked)."""
    ALLOW = "ALLOW"          # safe-auto: executes automatically (ACS allow)
    DENY = "DENY"            # policy refused: gated and not approved (ACS deny)
    BLOCKED = "BLOCKED"      # structurally impossible / founder-key-needed (ACS deny, hard)


# --------------------------------------------------------------------------- #
# Privilege rings — classify Forge's REAL action vocabulary                   #
# --------------------------------------------------------------------------- #
class Ring(str, Enum):
    """Privilege rings, inner = most trusted-to-self-execute.

    Modeled directly on Forge's observed auto-loop behaviour (current_session_context):
    Forge auto-runs "safe work", auto-skips "founder-gated items" (gated_skipped),
    and reports BLOCKED when it needs a founder key drop and refuses to fake a signature.
    """
    SAFE_AUTO = "safe-auto"  # ring 0: Forge runs unattended (file order, deploy redeploy, probe, sign w/ present key)
    GATED = "gated"          # ring 1: needs founder/node-owner approval (pull a 32B model, merge a normal PR)
    FORBIDDEN = "forbidden"  # ring 2: never, by any path (merge lutar-lean keystone, commit a key, weaken a gate)


# Forge's actual action vocabulary, harvested from the live auto-loop history.
# (file_order/redeploy_service/probe_endpoint/sign_certificate = safe-auto; pulling a
#  large model or merging a normal PR = gated; merging the lutar-lean keystone or
#  committing a key = forbidden — these are doctrine red lines, see turn_0298.)
DEFAULT_ACTION_RINGS: Dict[str, Ring] = {
    # --- safe-auto (ring 0): Forge does these unattended in its hourly loop ---
    "file_order": Ring.SAFE_AUTO,             # overwrite replit-sync/NEXT_ORDER.md
    "write_auto_state": Ring.SAFE_AUTO,       # write AUTO_STATE.json done-report
    "redeploy_service": Ring.SAFE_AUTO,       # restart a11oy / redeploy a surface
    "probe_endpoint": Ring.SAFE_AUTO,         # curl a live endpoint, record HTTP code
    "run_pinn_solve": Ring.SAFE_AUTO,         # run the agentic PINN loop on rtx-betterwithage
    "open_draft_pr": Ring.SAFE_AUTO,          # open a draft PR (review still gated)
    "sign_certificate": Ring.SAFE_AUTO,       # DSSE-sign IF the FA-001 key is present in box store

    # --- gated (ring 1): auto-skipped, needs founder/node-owner approval ---
    "merge_pr": Ring.GATED,                   # merge a normal (non-keystone) PR
    "pull_model_weights": Ring.GATED,         # pull Qwen2.5-Coder-32B onto the GPU node (node-owner action)
    "spend_money": Ring.GATED,                # register a domain / paid resource
    "rotate_secret": Ring.GATED,              # rotate a non-key secret

    # --- forbidden (ring 2): structurally impossible, doctrine red lines ---
    "merge_lutar_lean_keystone": Ring.FORBIDDEN,  # NEVER merge the lutar-lean keystone PR
    "commit_key": Ring.FORBIDDEN,                 # NEVER commit a key
    "weaken_gate": Ring.FORBIDDEN,                # NEVER weaken a deny-by-default gate
    "fabricate_signature": Ring.FORBIDDEN,        # NEVER fake a signature when the key is absent
    "fabricate_measurement": Ring.FORBIDDEN,      # NEVER label SAMPLE data as MEASURED
}


# --------------------------------------------------------------------------- #
# Policy — deny-by-default, evaluated BEFORE the action (ACS pre / MS toolkit) #
# --------------------------------------------------------------------------- #
class GovernanceDenied(Exception):
    """Raised when a structurally-impossible (FORBIDDEN) or kill-switched action is
    attempted through the governed executor. Mirrors the Microsoft Agent Governance
    Toolkit's GovernanceDenied: the action never reaches the wire."""
    def __init__(self, action: str, decision: Decision, reason: str):
        self.action = action
        self.decision = decision
        self.reason = reason
        super().__init__(f"[{decision.value}] {action}: {reason}")


@dataclass
class Policy:
    """The active policy at execution time. Recorded into EVERY ledger entry so an
    auditor can reconstruct *which* policy produced *which* decision (ACS: 'what policy
    was active'). deny-by-default: an action absent from the ring map is treated as
    unknown -> DENY."""
    name: str = "forge-doctrine-v11"
    version: str = "11.0"
    action_rings: Dict[str, Ring] = field(default_factory=lambda: dict(DEFAULT_ACTION_RINGS))
    # Gated actions require an explicit approval token to be ALLOWed.
    require_approval_for_gated: bool = True

    def ring_of(self, action: str) -> Optional[Ring]:
        return self.action_rings.get(action)

    def fingerprint(self) -> str:
        """Stable hash of the policy content — binds each decision to the exact policy
        text in force at that moment (tamper-evident policy provenance)."""
        payload = json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "rings": {k: v.value for k, v in sorted(self.action_rings.items())},
                "require_approval_for_gated": self.require_approval_for_gated,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Action context + result                                                     #
# --------------------------------------------------------------------------- #
@dataclass
class ActionContext:
    """Everything the governor needs to make and record a decision about one Forge action."""
    order_sha: str                       # the replit-sync order SHA that triggered this action
    action: str                          # action name (must be in Forge's vocabulary)
    actor: str = "forge"                 # which agent — auditability collapses without per-agent identity
    inputs: Dict[str, Any] = field(default_factory=dict)
    approval_token: Optional[str] = None  # founder/node-owner approval for gated actions
    ts: Optional[float] = None           # wall clock; set at decision time if None

    def inputs_hash(self) -> str:
        payload = json.dumps(self.inputs, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class ActionResult:
    """The real artifact Forge produced — a commit SHA, an HTTP code, a receipt id.
    No fabrication: ok=False with an error is honest; we never invent a success."""
    ok: bool
    commit_sha: Optional[str] = None
    http_code: Optional[int] = None
    artifact: Optional[str] = None
    error: Optional[str] = None

    def artifact_summary(self) -> str:
        if self.commit_sha:
            return f"commit:{self.commit_sha}"
        if self.http_code is not None:
            return f"http:{self.http_code}"
        if self.artifact:
            return f"artifact:{self.artifact}"
        if self.error:
            return f"error:{self.error}"
        return "none"


# --------------------------------------------------------------------------- #
# Ledger entry — the khipu knot                                               #
# --------------------------------------------------------------------------- #
GENESIS_HASH = "0" * 64  # khipu primary cord — the chain's anchor


@dataclass
class LedgerEntry:
    """One tamper-evident, replayable decision record. entry_hash binds prev_hash
    (khipu-style: each knot's hash includes the previous knot's hash)."""
    seq: int
    ts: float
    order_sha: str
    actor: str
    action: str
    ring: str
    decision: str
    reason: str
    policy_fingerprint: str
    inputs_hash: str
    result_artifact: str            # commit SHA / HTTP code / receipt — the real outcome, or "blocked"
    prev_hash: str
    entry_hash: str = ""

    def _digest_payload(self) -> str:
        """Canonical payload hashed into entry_hash. Everything EXCEPT entry_hash
        itself — and crucially including prev_hash, which chains the knots."""
        d = {
            "seq": self.seq,
            "ts": self.ts,
            "order_sha": self.order_sha,
            "actor": self.actor,
            "action": self.action,
            "ring": self.ring,
            "decision": self.decision,
            "reason": self.reason,
            "policy_fingerprint": self.policy_fingerprint,
            "inputs_hash": self.inputs_hash,
            "result_artifact": self.result_artifact,
            "prev_hash": self.prev_hash,
        }
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        return hashlib.sha256(self._digest_payload().encode()).hexdigest()

    def seal(self) -> "LedgerEntry":
        self.entry_hash = self.compute_hash()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# The governed ledger                                                         #
# --------------------------------------------------------------------------- #
class ForgeGovernor:
    """ACS-style runtime governor for Forge.

    Append-only, hash-chained decision ledger + privilege rings + kill switch +
    pre/post middleware hooks. The ledger is the single source of truth an auditor
    replays. History is never rewritten (honesty: append-only).
    """

    def __init__(self, policy: Optional[Policy] = None):
        self.policy = policy or Policy()
        self._entries: List[LedgerEntry] = []
        self._kill_switch: bool = False

    # ---- kill switch ---------------------------------------------------- #
    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    def engage_kill_switch(self) -> None:
        """Engage the kill switch: ALL gated + forbidden actions DENY. Safe-auto reads
        remain (read-only) but anything with side-effect risk above ring 0 stops."""
        self._kill_switch = True

    def release_kill_switch(self) -> None:
        self._kill_switch = False

    # ---- ACS pre_action hook ------------------------------------------- #
    def pre_action(self, ctx: ActionContext) -> "DecisionRecord":
        """ACS interception point 'before tool call'. Deterministic, deny-by-default.
        Returns a DecisionRecord; NEVER mutates the ledger (post_action does that).

        Order of checks (most restrictive first):
          1. unknown action          -> DENY  (deny-by-default)
          2. FORBIDDEN ring          -> BLOCKED (structurally impossible)
          3. kill switch engaged     -> DENY (gated/forbidden); forbidden already BLOCKED
          4. GATED w/o approval      -> DENY
          5. else                    -> ALLOW
        """
        ring = self.policy.ring_of(ctx.action)

        # 1. deny-by-default: unknown action is refused.
        if ring is None:
            return DecisionRecord(Decision.DENY, None,
                                  f"unknown action '{ctx.action}' — deny-by-default")

        # 2. forbidden is structurally impossible — even with a kill switch off,
        #    even with an approval token. No path makes this ALLOW.
        if ring is Ring.FORBIDDEN:
            return DecisionRecord(Decision.BLOCKED, ring,
                                  f"action '{ctx.action}' is FORBIDDEN (doctrine red line) — structurally blocked")

        # 3. kill switch: deny everything above ring 0.
        if self._kill_switch and ring in (Ring.GATED,):
            return DecisionRecord(Decision.DENY, ring,
                                  f"kill switch engaged — gated action '{ctx.action}' denied")

        # 4. gated requires explicit approval.
        if ring is Ring.GATED and self.policy.require_approval_for_gated and not ctx.approval_token:
            return DecisionRecord(Decision.DENY, ring,
                                  f"gated action '{ctx.action}' requires founder/node-owner approval")

        # 5. safe-auto, or gated-with-approval -> allow.
        if self._kill_switch and ring is Ring.SAFE_AUTO:
            # ring 0 are effectively read/idempotent; still allowed under kill switch,
            # but we annotate so the audit shows the switch was on.
            return DecisionRecord(Decision.ALLOW, ring,
                                  f"safe-auto '{ctx.action}' allowed (kill switch on; ring-0 only)")
        return DecisionRecord(Decision.ALLOW, ring, f"'{ctx.action}' permitted (ring={ring.value})")

    # ---- ACS post_action hook ------------------------------------------ #
    def post_action(self, ctx: ActionContext, decision_rec: "DecisionRecord",
                    result: Optional[ActionResult]) -> LedgerEntry:
        """ACS interception point 'after tool returns'. Appends ONE sealed, chained
        entry. This is the ONLY method that mutates the ledger.

        Honesty invariants:
          * There is no entry without a real decision_rec (you must call pre_action).
          * If decision != ALLOW, result_artifact records the block — never a fake commit.
          * History is append-only: we read the last hash, we never rewrite earlier knots.
        """
        if decision_rec is None or not isinstance(decision_rec, DecisionRecord):
            raise ValueError("post_action requires a DecisionRecord from pre_action — no entry without a real decision")

        ts = ctx.ts if ctx.ts is not None else time.time()

        if decision_rec.decision is Decision.ALLOW:
            if result is None:
                raise ValueError("ALLOW decision must carry a real ActionResult — no fabricated outcome")
            artifact = result.artifact_summary()
        else:
            # Denied/blocked actions never executed -> no commit, no HTTP success.
            artifact = f"blocked:{decision_rec.decision.value}"

        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        ring_val = decision_rec.ring.value if decision_rec.ring else "unknown"

        entry = LedgerEntry(
            seq=len(self._entries),
            ts=ts,
            order_sha=ctx.order_sha,
            actor=ctx.actor,
            action=ctx.action,
            ring=ring_val,
            decision=decision_rec.decision.value,
            reason=decision_rec.reason,
            policy_fingerprint=self.policy.fingerprint(),
            inputs_hash=ctx.inputs_hash(),
            result_artifact=artifact,
            prev_hash=prev_hash,
        ).seal()

        self._entries.append(entry)
        return entry

    # ---- governed executor (structural enforcement) -------------------- #
    def execute(self, ctx: ActionContext, runner: Callable[[ActionContext], ActionResult]) -> LedgerEntry:
        """End-to-end governed call: pre_action -> (structural block) -> runner -> post_action.

        This is where 'blocked actions are structurally impossible': if the decision is
        not ALLOW, `runner` is NEVER invoked (the intent never reaches the wire) and we
        raise GovernanceDenied AFTER recording the denied attempt in the ledger.
        """
        decision_rec = self.pre_action(ctx)

        if decision_rec.decision is not Decision.ALLOW:
            # Record the denied attempt (auditable), then refuse — runner is not called.
            self.post_action(ctx, decision_rec, None)
            raise GovernanceDenied(ctx.action, decision_rec.decision, decision_rec.reason)

        result = runner(ctx)            # only reached on ALLOW
        return self.post_action(ctx, decision_rec, result)

    # ---- verification + replay ----------------------------------------- #
    def verify_chain(self) -> bool:
        """Walk the chain. Returns True only if every knot's stored hash matches its
        recomputed hash AND its prev_hash matches the prior knot's hash. Any tamper
        (edited field, reordered/spliced entry, rewritten history) breaks this."""
        prev = GENESIS_HASH
        for i, e in enumerate(self._entries):
            if e.seq != i:
                return False
            if e.prev_hash != prev:
                return False
            if e.compute_hash() != e.entry_hash:
                return False
            prev = e.entry_hash
        return True

    def replay(self) -> List[Dict[str, Any]]:
        """Reconstruct the governed decision sequence from the sealed chain. Refuses to
        replay a tampered ledger (you cannot trust a sequence you can't verify)."""
        if not self.verify_chain():
            raise GovernanceDenied("replay", Decision.BLOCKED,
                                   "ledger chain verification FAILED — refusing to replay tampered history")
        return [
            {
                "seq": e.seq,
                "order_sha": e.order_sha,
                "actor": e.actor,
                "action": e.action,
                "ring": e.ring,
                "decision": e.decision,
                "result_artifact": e.result_artifact,
                "policy_fingerprint": e.policy_fingerprint,
                "entry_hash": e.entry_hash,
            }
            for e in self._entries
        ]

    # ---- ledger access / persistence ----------------------------------- #
    @property
    def entries(self) -> List[LedgerEntry]:
        return list(self._entries)  # defensive copy — callers cannot splice the live ledger

    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e.to_dict(), sort_keys=True) for e in self._entries)

    @classmethod
    def from_jsonl(cls, text: str, policy: Optional[Policy] = None) -> "ForgeGovernor":
        """Load a ledger from JSONL and verify it. Raises if the loaded chain is broken."""
        gov = cls(policy=policy)
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            gov._entries.append(LedgerEntry(**d))
        if not gov.verify_chain():
            raise GovernanceDenied("load", Decision.BLOCKED, "loaded ledger failed chain verification")
        return gov


@dataclass
class DecisionRecord:
    """Result of pre_action — the verdict + the ring + a human-readable reason."""
    decision: Decision
    ring: Optional[Ring]
    reason: str


# --------------------------------------------------------------------------- #
# Adapter: ingest Forge's REAL exec receipts / AUTO_STATE into the ledger     #
# --------------------------------------------------------------------------- #
def receipt_to_context(receipt: Dict[str, Any]) -> ActionContext:
    """Map a Forge AUTO_STATE / exec-receipt record onto an ActionContext.

    Observed Forge auto-loop schema (current_session_context turns 0112-0319):
        {
          "state": "done",                # done | gated_skipped | blocked
          "order_sha": "6884c6a7",
          "idle": true/false,
          "action": "redeploy_service",   # the work performed
          "ts": "2026-06-14T16:02:00Z",
          "result": {"commit_sha": "...", "http_code": 200} | {"error": "..."}
        }
    Forge's own states map onto our verdicts: done->ALLOW, gated_skipped->DENY(gated),
    blocked->BLOCKED. We DO NOT trust the receipt's self-reported verdict — pre_action
    recomputes the decision from policy (the receipt only supplies action+inputs+result).
    """
    ts = receipt.get("ts")
    if isinstance(ts, str):
        try:
            ts = time.mktime(time.strptime(ts.replace("Z", "GMT"), "%Y-%m-%dT%H:%M:%S%Z"))
        except (ValueError, OverflowError):
            ts = None
    return ActionContext(
        order_sha=str(receipt.get("order_sha", "unknown")),
        action=str(receipt.get("action", "")),
        actor=str(receipt.get("actor", "forge")),
        inputs=receipt.get("inputs", {}) or {},
        approval_token=receipt.get("approval_token"),
        ts=ts,
    )


def receipt_to_result(receipt: Dict[str, Any]) -> Optional[ActionResult]:
    """Extract the real artifact from a Forge receipt (commit SHA / HTTP code / error)."""
    r = receipt.get("result") or {}
    if not r:
        return None
    return ActionResult(
        ok=bool(r.get("commit_sha") or (isinstance(r.get("http_code"), int) and 200 <= r["http_code"] < 300)),
        commit_sha=r.get("commit_sha"),
        http_code=r.get("http_code"),
        artifact=r.get("artifact"),
        error=r.get("error"),
    )


def ingest_receipts(gov: ForgeGovernor, receipts: List[Dict[str, Any]]) -> List[LedgerEntry]:
    """Feed a batch of real Forge receipts through the governor. Each receipt is
    re-evaluated by policy (pre_action) and appended (post_action) — denied/blocked
    receipts are recorded as such, never silently dropped. Returns the new entries."""
    out: List[LedgerEntry] = []
    for rcpt in receipts:
        ctx = receipt_to_context(rcpt)
        decision_rec = gov.pre_action(ctx)
        result = receipt_to_result(rcpt) if decision_rec.decision is Decision.ALLOW else None
        # If policy ALLOWs but the receipt has no result, that's an honesty violation in
        # the source data — we record it as a result-less ALLOW only if a result exists,
        # otherwise downgrade to a recorded DENY (no fabricated outcome).
        if decision_rec.decision is Decision.ALLOW and result is None:
            decision_rec = DecisionRecord(Decision.DENY, decision_rec.ring,
                                          "ALLOW with no real result artifact — refusing to fabricate outcome")
        out.append(gov.post_action(ctx, decision_rec, result))
    return out
