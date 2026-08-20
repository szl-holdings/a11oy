"""szl_cheapest_watt.py — SZL Energy: carbon/cost-aware "cheapest-watt" placement policy.

WHAT THIS IS (and is NOT)
-------------------------
This is PLACEMENT + ACCOUNTING, NOT fused VRAM. Given the reachable sovereign nodes,
their MEASURED per-node energy intensity (joules-per-token), and the LIVE grid price
(€/MWh) at decision time, it picks the ONE node that minimizes energy-cost-per-token
and records the placement decision into a signed, hash-chained receipt. Each separate
worker keeps its own metered joules — nothing is ever merged/fused across the network.

It does NOT execute inference; it reads what the live energy operator already MEASURED
(per-node joules + tokens + power_w + live grid price) and turns that into an honest,
re-hashable placement decision plus a cumulative MEASURED-savings tally. The mesh
coordinator's least-connections balancer still does the actual proxying; this is the
cost/carbon lens that, when wired in, can re-order candidates by cheapest watt.

HONESTY GATES (Doctrine v11 — never weakened here)
--------------------------------------------------
  * NEVER fabricate a grid price or a saving. A node only has an energy-intensity
    (J/token) when its OWN per-node MEASURED joules and tokens are both > 0 this read.
    A node whose joules are PENDING_EXPORTER / 0 has UNKNOWN intensity and is NOT
    ranked on cost (it is reported, honestly, as "intensity unknown — pending exporter").
  * If fewer than TWO nodes have a comparable MEASURED intensity, there is NO real
    placement choice: we report decision="no_choice" with reason "no placement choice
    this tick" — we never invent an alternative to claim a saving against.
  * The grid price is passed through from the live meter verbatim (€/MWh). If it is
    missing, the per-token COST is UNKNOWN (intensity is still MEASURED) and the cost
    delta is labeled accordingly — we never assume a price.
  * SAVINGS LABELLING: a saving is the cost delta between the CHOSEN node and a NAMED
    baseline. It is MEASURED only when BOTH legs are MEASURED (both nodes' J/token from
    real per-node NVML deltas AND a live grid price). The default baseline is the
    *most-expensive comparable node this tick* (a real alternative we declined) — that
    leg is MEASURED, so the delta is MEASURED. Any baseline that is itself MODELED or
    assumed (e.g. a cloud-grid reference intensity) yields an ESTIMATE saving, never
    MEASURED. We label every saving with exactly one of {MEASURED, ESTIMATE}.
  * Receipts are re-hashable offline (sha256_canon over the canonical decision) and
    hash-chained (prev_digest; genesis = 64 zeros). DSSE signing is layered on by the
    caller when a real cosign key is present; absent a key the receipt is honest-but-
    UNSIGNED, never faked.
  * sovereign=false on this accounting path; Λ = Conjecture 1; trust never 100%.

Pure stdlib (hashlib + json). No third-party deps, no network — the caller hands in
the operator-status dict it already fetched. Offline self-test at the bottom.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants. We mirror joule_billing's canonical hashing when that module is
# importable (single source of the receipt-hash math); otherwise a byte-identical
# local fallback so this module also runs fully standalone / offline in tests.
# ---------------------------------------------------------------------------
JOULES_PER_KWH = 3_600_000.0
GENESIS_PREV = "0" * 64

LABEL_MEASURED = "MEASURED"
LABEL_ESTIMATE = "ESTIMATE"
LABEL_UNKNOWN = "UNKNOWN"

DOCTRINE = (
    "Doctrine v11: cheapest-watt PLACEMENT + accounting, NOT fused VRAM. Each node keeps "
    "its own MEASURED joules; nothing merged. Energy-intensity (J/token) is MEASURED only "
    "from a node's own per-node NVML joule delta and tokens (both >0); else intensity is "
    "UNKNOWN and the node is never ranked on cost. Grid price (€/MWh) is the live meter "
    "value passed through verbatim, never assumed. A saving is MEASURED only when BOTH the "
    "chosen leg and the named baseline leg are MEASURED (real per-node J/token + live price); "
    "any modeled/assumed baseline => ESTIMATE. With <2 comparable MEASURED nodes there is no "
    "placement choice this tick (decision=no_choice) — we never invent an alternative. Never "
    "fabricate a price or a saving. Receipts re-hashable offline + hash-chained "
    "(prev_digest). sovereign=false; Λ=Conjecture 1; trust never 100%."
)


def sha256_canon(obj: dict) -> str:
    """Canonical sha256 over a dict (sorted keys, tight separators). Prefers
    joule_billing.sha256_canon so the hash math is the SAME single source the
    JouleCharge receipts use; falls back to a byte-identical local impl."""
    try:
        from joule_billing import sha256_canon as _sc  # type: ignore
        return _sc(obj)
    except Exception:
        return "sha256:" + hashlib.sha256(
            json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


# ---------------------------------------------------------------------------
# Candidate model. One candidate = one reachable, COMPUTING sovereign node with
# its own metered energy this read. We read per-node joules + tokens from the
# operator's by_node block (MEASURED-only) and power_w from status when present.
# ---------------------------------------------------------------------------
@dataclass
class Candidate:
    name: str
    sovereign: bool
    joules_label: str               # MEASURED | PENDING_EXPORTER | NONE (from operator by_node)
    joules_measured: float          # node's own cumulative MEASURED joules (billable)
    tokens: int                     # node's own cumulative tokens
    power_w: Optional[float] = None # latest live exporter power_w for this node, if known

    # derived (filled by the policy)
    joules_per_token: Optional[float] = None  # MEASURED intensity, or None if UNKNOWN
    intensity_label: str = LABEL_UNKNOWN
    eur_per_token: Optional[float] = None      # cost = J/token /3.6e9 *kWh * €/MWh, or None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "node": self.name,
            "sovereign": self.sovereign,
            "joules_label": self.joules_label,
            "joules_measured": round(self.joules_measured, 6),
            "tokens": self.tokens,
            "power_w": self.power_w,
            "joules_per_token": (round(self.joules_per_token, 9)
                                 if self.joules_per_token is not None else None),
            "intensity_label": self.intensity_label,
            "eur_per_token": (None if self.eur_per_token is None
                              else float(f"{self.eur_per_token:.6e}")),
            "note": self.note,
        }


def _candidates_from_status(status: Dict[str, Any]) -> List[Candidate]:
    """Build candidates from a live energy-operator status dict (the SAME shape
    /api/a11oy/v1/energy/operator/status returns). Only nodes that are COMPUTING
    this read are candidates (a standby/DEGRADED node never serves, so it is never
    a placement target). Per-node energy comes from status['by_node'] verbatim —
    MEASURED only; PENDING/NONE => intensity UNKNOWN, never fabricated."""
    by_node = status.get("by_node") or {}
    computing = set(status.get("nodes_computing") or [])
    # power_w_sample is the most-recent live exporter watt reading (single source in
    # this status shape). We attach it to the MEASURED node it belongs to (the one
    # whose joules are MEASURED) — never spread to a node we have no reading for.
    power_w = status.get("power_w_sample")
    exporter_measured_node = None
    for name, b in by_node.items():
        if (b or {}).get("joules_label") == LABEL_MEASURED:
            exporter_measured_node = name
            break
    cands: List[Candidate] = []
    for name, b in by_node.items():
        if name not in computing:
            continue  # only nodes actually computing this read can be chosen
        b = b or {}
        cands.append(Candidate(
            name=name,
            sovereign=True,  # only owned-metal sovereign workers reach by_node compute
            joules_label=str(b.get("joules_label") or "NONE"),
            joules_measured=float(b.get("joules_measured") or 0.0),
            tokens=int(b.get("tokens") or 0),
            power_w=(float(power_w) if (power_w is not None
                                        and name == exporter_measured_node) else None),
        ))
    return cands


# ---------------------------------------------------------------------------
# The policy. Compute MEASURED J/token per candidate, then €/token from the live
# grid price, then pick the cheapest. Build an honest decision + receipt.
# ---------------------------------------------------------------------------
def _eur_per_token(joules_per_token: Optional[float],
                   grid_price_eur_mwh: Optional[float]) -> Optional[float]:
    """€/token = (J/token / 3.6e9 J/kWh) * (€/MWh / 1000 kWh/MWh).
    Returns None (UNKNOWN) when intensity or price is missing — never assumed."""
    if joules_per_token is None or grid_price_eur_mwh is None:
        return None
    kwh_per_token = joules_per_token / JOULES_PER_KWH
    eur_per_kwh = float(grid_price_eur_mwh) / 1000.0
    return kwh_per_token * eur_per_kwh


def evaluate(status: Dict[str, Any],
             baseline: str = "most_expensive_comparable",
             prev_digest: str = GENESIS_PREV,
             now_ts: Optional[float] = None) -> Dict[str, Any]:
    """Run ONE cheapest-watt placement evaluation against a live operator status.

    Returns an honest decision dict carrying a re-hashable receipt. NEVER fabricates
    a price or a saving. With <2 comparable MEASURED-intensity nodes it returns
    decision='no_choice' (reason 'no placement choice this tick').
    """
    now_ts = time.time() if now_ts is None else now_ts
    ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts))
    grid = status.get("grid_price_eur_mwh")
    grid = float(grid) if isinstance(grid, (int, float)) else None

    cands = _candidates_from_status(status)
    # Derive MEASURED intensity + cost for each candidate.
    for c in cands:
        if c.joules_label == LABEL_MEASURED and c.joules_measured > 0 and c.tokens > 0:
            c.joules_per_token = c.joules_measured / c.tokens
            c.intensity_label = LABEL_MEASURED
            c.eur_per_token = _eur_per_token(c.joules_per_token, grid)
            c.note = "MEASURED J/token from this node's own NVML joule delta / its tokens"
        else:
            c.joules_per_token = None
            c.intensity_label = LABEL_UNKNOWN
            c.eur_per_token = None
            c.note = ("intensity unknown — node computed but per-node MEASURED joules "
                      "are pending (%s); never ranked on cost, never fabricated"
                      % (c.joules_label,))

    comparable = [c for c in cands if c.intensity_label == LABEL_MEASURED]

    base_decision: Dict[str, Any] = {
        "receipt_type": "SZL.Energy.CheapestWattPlacement.v1",
        "ts": ts_iso,
        "grid_price_eur_mwh": grid,
        "grid_price_label": (LABEL_MEASURED if grid is not None else LABEL_UNKNOWN),
        "grid_price_note": ("live meter value at decision time, passed through verbatim"
                            if grid is not None else
                            "no live grid price this read — cost is UNKNOWN, never assumed"),
        "baseline_policy": baseline,
        "candidates": [c.to_dict() for c in cands],
        "reachable_computing_count": len(cands),
        "comparable_measured_count": len(comparable),
        "honesty": {
            "sovereign": False,
            "lambda": "Conjecture 1",
            "trust": "never 100%",
            "placement": "horizontal cost/carbon-aware placement; VRAM NOT fused",
            "fabrication": "no price or saving is ever fabricated",
        },
    }

    if len(comparable) < 2:
        decision = dict(base_decision)
        decision.update({
            "decision": "no_choice",
            "chosen_node": None,
            "reason": "no placement choice this tick",
            "detail": (
                "fewer than two nodes have a comparable MEASURED energy-intensity "
                "this read (%d computing, %d MEASURED-intensity); with no real "
                "alternative we decline to claim a saving — never fabricated."
                % (len(cands), len(comparable))
            ),
            "saving": None,
            "saving_label": None,
        })
        return _finalize(decision, prev_digest)

    # Rank comparable nodes by €/token when a price exists; else by J/token (still a
    # real, MEASURED energy ranking — labeled as energy-only, no monetary claim).
    if grid is not None:
        ranked = sorted(comparable, key=lambda c: c.eur_per_token)  # type: ignore[arg-type]
        metric = "eur_per_token"
    else:
        ranked = sorted(comparable, key=lambda c: c.joules_per_token)  # type: ignore[arg-type]
        metric = "joules_per_token"

    chosen = ranked[0]
    # Named baseline = the most-expensive comparable node we DECLINED this tick.
    # That is a REAL alternative leg with MEASURED intensity -> the delta is MEASURED
    # (when a live price also exists; otherwise it is a MEASURED energy delta, and any
    # monetary framing would be ESTIMATE).
    baseline_node = ranked[-1]

    if metric == "eur_per_token":
        chosen_cost = chosen.eur_per_token
        base_cost = baseline_node.eur_per_token
        delta = base_cost - chosen_cost  # €/token saved vs the declined alternative
        # BOTH legs MEASURED (real per-node J/token) AND a live price => MEASURED saving.
        saving_label = LABEL_MEASURED
        saving = {
            "metric": "eur_per_token",
            "chosen_eur_per_token": float(f"{chosen_cost:.6e}"),
            "baseline_eur_per_token": float(f"{base_cost:.6e}"),
            "delta_eur_per_token": float(f"{delta:.6e}"),
            "delta_pct": (round(100.0 * delta / base_cost, 4) if base_cost else None),
            "baseline_node": baseline_node.name,
            "note": (
                "MEASURED: both legs are real per-node NVML J/token AND the grid price "
                "is the live meter value; delta is vs the most-expensive comparable node "
                "we declined this tick (a real alternative), not a hypothetical baseline."
            ),
        }
    else:
        # No live price: we can only state the MEASURED energy delta; any euro figure
        # would require a price we do not have, so we DO NOT emit one (ESTIMATE-or-none).
        chosen_j = chosen.joules_per_token
        base_j = baseline_node.joules_per_token
        jdelta = base_j - chosen_j
        saving_label = LABEL_ESTIMATE  # monetary saving cannot be MEASURED w/o a price
        saving = {
            "metric": "joules_per_token",
            "chosen_joules_per_token": round(chosen_j, 9),
            "baseline_joules_per_token": round(base_j, 9),
            "delta_joules_per_token": round(jdelta, 9),
            "delta_pct": (round(100.0 * jdelta / base_j, 4) if base_j else None),
            "baseline_node": baseline_node.name,
            "note": (
                "ESTIMATE (monetary): energy delta is MEASURED (real per-node J/token), "
                "but NO live grid price this read, so a euro saving cannot be MEASURED — "
                "we report the MEASURED joules delta only and never assume a price."
            ),
        }

    decision = dict(base_decision)
    decision.update({
        "decision": "placed",
        "chosen_node": chosen.name,
        "rank_metric": metric,
        "reason": ("chosen node minimizes %s among comparable MEASURED-intensity "
                   "sovereign nodes this tick" % metric),
        "ranking": [c.name for c in ranked],
        "saving": saving,
        "saving_label": saving_label,
    })
    return _finalize(decision, prev_digest)


def _finalize(decision: Dict[str, Any], prev_digest: str) -> Dict[str, Any]:
    """Attach the re-hashable payload_digest and the chain prev_digest. The
    entry_digest binds (prev_digest, payload_digest) the same way the energy ledger
    binds its entries, so a cheapest-watt receipt slots into the same chain shape."""
    payload_digest = sha256_canon(decision)
    entry_digest = sha256_canon({"prev_digest": prev_digest,
                                 "payload_digest": payload_digest})
    return {
        "decision": decision,
        "payload_digest": payload_digest,
        "prev_digest": prev_digest,
        "entry_digest": entry_digest,
    }


# ---------------------------------------------------------------------------
# CheapestWattLedger — a small, in-process, hash-chained tally of placement
# decisions + cumulative MEASURED savings. Thread-safe; bounded recent tail.
# It NEVER persists a key and NEVER fabricates — it only records what evaluate()
# returned. Cumulative MEASURED savings sum ONLY the receipts whose saving_label
# is MEASURED (both legs real). ESTIMATE/none savings are tallied separately.
# ---------------------------------------------------------------------------
class CheapestWattLedger:
    def __init__(self, max_tail: int = 50) -> None:
        self._lock = threading.RLock()
        self._head = GENESIS_PREV
        self._count = 0
        self._placed = 0
        self._no_choice = 0
        self._cum_measured_eur_per_token_saved = 0.0   # sum of MEASURED €/token deltas
        self._measured_saving_receipts = 0
        self._estimate_saving_receipts = 0
        self._recent: List[Dict[str, Any]] = []

    def record(self, status: Dict[str, Any],
               baseline: str = "most_expensive_comparable") -> Dict[str, Any]:
        """Evaluate against a live status and append the resulting receipt to the
        chain. Returns the receipt. MEASURED savings accumulate ONLY from receipts
        whose saving_label==MEASURED — honest by construction."""
        with self._lock:
            receipt = evaluate(status, baseline=baseline, prev_digest=self._head)
            self._head = receipt["entry_digest"]
            self._count += 1
            d = receipt["decision"]
            if d["decision"] == "placed":
                self._placed += 1
                lab = d.get("saving_label")
                sv = d.get("saving") or {}
                if lab == LABEL_MEASURED and "delta_eur_per_token" in sv:
                    self._cum_measured_eur_per_token_saved += float(sv["delta_eur_per_token"])
                    self._measured_saving_receipts += 1
                elif lab == LABEL_ESTIMATE:
                    self._estimate_saving_receipts += 1
            else:
                self._no_choice += 1
            self._recent.append(receipt)
            if len(self._recent) > 50:
                self._recent.pop(0)
            return receipt

    def verify(self) -> Tuple[bool, int, int]:
        """Re-walk the chain offline: each receipt re-hashes to its payload_digest
        AND its entry_digest binds (prev_digest, payload_digest); each prev links to
        the previous entry_digest. Returns (ok, length, first_break_index)."""
        with self._lock:
            prev = GENESIS_PREV
            for i, r in enumerate(self._recent):
                pd = sha256_canon(r["decision"])
                ed = sha256_canon({"prev_digest": r["prev_digest"],
                                   "payload_digest": pd})
                if (pd != r["payload_digest"] or ed != r["entry_digest"]
                        or r["prev_digest"] != prev):
                    return (False, len(self._recent), i)
                prev = r["entry_digest"]
            return (True, len(self._recent), -1)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            ok, length, brk = self.verify()
            return {
                "service": "cheapest-watt-placement",
                "kind": "carbon/cost-aware placement + accounting (NOT fused VRAM)",
                "decisions_total": self._count,
                "placed": self._placed,
                "no_choice": self._no_choice,
                "cumulative_measured_eur_per_token_saved":
                    float(f"{self._cum_measured_eur_per_token_saved:.9e}")
                    if self._cum_measured_eur_per_token_saved else 0.0,
                "cumulative_measured_saving_label": LABEL_MEASURED,
                "measured_saving_receipts": self._measured_saving_receipts,
                "estimate_saving_receipts": self._estimate_saving_receipts,
                "chain": {
                    "head": self._head,
                    "length": length,
                    "ok": ok,
                    "first_break_index": brk,
                    "genesis_prev": GENESIS_PREV,
                },
                "recent_decisions": [r["decision"] for r in self._recent[-10:]],
                "doctrine": DOCTRINE,
                "honesty": (
                    "cumulative_measured_eur_per_token_saved sums ONLY receipts whose "
                    "saving_label==MEASURED (both the chosen leg and the named declined-"
                    "alternative leg are real per-node MEASURED J/token AND a live grid "
                    "price). ESTIMATE savings (e.g. no live price this read) are counted "
                    "separately and never folded into the MEASURED total. no_choice ticks "
                    "(<2 comparable MEASURED nodes) claim NO saving. Never fabricated."
                ),
            }


# Module-level singleton the endpoint drives (one tally per process).
_LEDGER: Optional[CheapestWattLedger] = None
_LEDGER_LOCK = threading.Lock()


def get_ledger() -> CheapestWattLedger:
    global _LEDGER
    with _LEDGER_LOCK:
        if _LEDGER is None:
            _LEDGER = CheapestWattLedger()
        return _LEDGER


# ---------------------------------------------------------------------------
# Offline self-test — proves the honesty gates with NO live GPU and NO network.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}

    # (a) Two comparable MEASURED nodes + a live price => MEASURED saving, cheaper wins.
    status_two = {
        "grid_price_eur_mwh": 111.24,
        "power_w_sample": 13.02,
        "nodes_computing": ["rtx-betterwithage", "chaski"],
        "by_node": {
            "rtx-betterwithage": {"joules_label": "MEASURED",
                                  "joules_measured": 910844.34, "tokens": 12002478},
            # synthetic 2nd MEASURED node for the gate (more J/token = pricier)
            "chaski": {"joules_label": "MEASURED",
                       "joules_measured": 200000.0, "tokens": 1024134},
        },
    }
    r = evaluate(status_two)
    d = r["decision"]
    assert d["decision"] == "placed", d
    assert d["saving_label"] == "MEASURED", d
    # cheaper = lower J/token. rtx: ~0.0759 J/tok ; chaski: ~0.1953 J/tok -> rtx chosen
    assert d["chosen_node"] == "rtx-betterwithage", d["chosen_node"]
    assert d["saving"]["delta_eur_per_token"] > 0, d["saving"]
    # receipt re-hashes offline
    assert sha256_canon(d) == r["payload_digest"]
    out["two_measured_live_price_measured_saving"] = True

    # (b) Only ONE comparable MEASURED node (chaski PENDING) => no placement choice.
    status_one = {
        "grid_price_eur_mwh": 111.24,
        "power_w_sample": 13.02,
        "nodes_computing": ["rtx-betterwithage", "chaski"],
        "by_node": {
            "rtx-betterwithage": {"joules_label": "MEASURED",
                                  "joules_measured": 910844.34, "tokens": 12002478},
            "chaski": {"joules_label": "PENDING_EXPORTER",
                       "joules_measured": 0.0, "tokens": 1024134},
        },
    }
    r1 = evaluate(status_one)
    assert r1["decision"]["decision"] == "no_choice", r1["decision"]
    assert r1["decision"]["reason"] == "no placement choice this tick"
    assert r1["decision"]["saving"] is None
    out["one_node_no_choice"] = True

    # (c) Two MEASURED nodes but NO live price => energy-only ranking, ESTIMATE saving.
    status_noprice = dict(status_two)
    status_noprice = {**status_two, "grid_price_eur_mwh": None}
    r2 = evaluate(status_noprice)
    d2 = r2["decision"]
    assert d2["decision"] == "placed" and d2["rank_metric"] == "joules_per_token", d2
    assert d2["saving_label"] == "ESTIMATE", d2  # no price => monetary saving not MEASURED
    assert "delta_eur_per_token" not in (d2["saving"] or {}), d2["saving"]
    out["no_price_estimate_saving_no_fabricated_euro"] = True

    # (d) Ledger: MEASURED savings accumulate ONLY from MEASURED receipts; chain verifies.
    led = CheapestWattLedger()
    led.record(status_two)      # MEASURED saving
    led.record(status_one)      # no_choice (no saving)
    led.record(status_noprice)  # ESTIMATE saving (not folded into MEASURED total)
    st = led.status()
    assert st["decisions_total"] == 3 and st["placed"] == 2 and st["no_choice"] == 1, st
    assert st["measured_saving_receipts"] == 1, st
    assert st["estimate_saving_receipts"] == 1, st
    assert st["cumulative_measured_eur_per_token_saved"] > 0, st
    assert st["chain"]["ok"] is True and st["chain"]["length"] == 3, st["chain"]
    out["ledger_measured_only_accumulation_and_chain_ok"] = True

    return out


if __name__ == "__main__":
    import sys as _sys
    print("=" * 70)
    print("szl_cheapest_watt — self-test (honesty gates, no live GPU, no network)")
    print("=" * 70)
    res = _selftest()
    print(json.dumps(res, indent=2))
    ok = all(res.values())
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    _sys.exit(0 if ok else 1)
