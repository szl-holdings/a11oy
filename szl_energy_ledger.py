#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_energy_ledger.py — SZL Energy: metering + signed-receipt hash-chained ledger.

Dev 2 (backend). Doctrine v11 (NEVER violate):
  - NO free-energy. Joules billable ONLY when joules_label == MEASURED and the NVML
    sample is fresh (<30s). SAMPLE / ESTIMATE / stale joules are REFUSED at the gate.
  - PROVE-OR-DOWNGRADE: revenue is MEASURED only when a real Stripe charge clears;
    with no STRIPE_API_KEY we run honest DRY-RUN (status:"dry-run" + would_charge_cents).
  - A signature is NOT proof of safety. sovereign=false on this path. Λ = Conjecture 1.
  - NEVER fabricate joules / dollars. Every receipt is re-hashable offline.

What this module does, per completed job:
  1. Consume a JobRecord {node, joules_measured, joules_label, tokens, wall_s, ts, model}
     — the contract Dev1's operator daemon emits. We build against this contract.
  2. Build a SZL.Energy.JouleCharge.v1 receipt via joule_billing.build_receipt()
     (the VENDORED billing core — we do not reinvent the math).
  3. Append the receipt to a HASH-CHAINED, offline-verifiable ledger: each entry carries
     prev_digest (genesis prev = 64 zeros) and an entry_digest binding (seq, prev, receipt).
  4. DRY-RUN bill when no STRIPE_API_KEY: status "dry-run" + would_charge_cents.
  5. Idempotency: the same job (same receipt digest) NEVER double-appends a charge.
  6. Persist the ledger to disk (JSONL) so it survives a restart.

Endpoints (additive, registered before the SPA catch-all, dual-register via add_api_route):
  GET /api/a11oy/v1/energy/ledger        — receipts list + chain integrity verdict + totals
  GET /api/a11oy/v1/energy/receipt/{idem} — single receipt by idempotency key (re-hashable)
  GET /energy/receipt/{idem}             — same, short alias

Run offline:  python szl_energy_ledger.py        (self-test: chain verify + tamper + gates)
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

# module-scope so FastAPI's add_api_route injects the Starlette Request rather than
# treating a 'request' parameter as a required query field (the classic 422). Guarded:
# if starlette is absent (pure offline use), the read endpoints simply aren't mounted.
try:
    from starlette.requests import Request as _Request
except Exception:  # pragma: no cover
    _Request = None  # type: ignore

# ---------------------------------------------------------------------------
# The VENDORED billing core. This is the single source of the receipt math:
# build_receipt() emits the SZL.Energy.JouleCharge.v1 decision + payload_digest,
# JouleReading.is_billable() enforces MEASURED + freshness, d_idem() gives the
# idempotency key. We do NOT duplicate any of that here.
# ---------------------------------------------------------------------------
from joule_billing import (
    JouleReading,
    build_receipt,
    charge_stripe,
    d_idem,
    sha256_canon,
    MAX_NVML_AGE_S,
    JOULES_PER_KWH,
)

GENESIS_PREV = "0" * 64                      # genesis entry's prev_digest (64 zeros)
DEFAULT_PRICE_PER_KWH_CENTS = int(os.getenv("STRIPE_PRICE_PER_KWH_CENTS", "45"))

# Where the chain persists. The receipt chain MUST survive a box redeploy — otherwise
# seq re-genesises to 0 on every deploy and the signed-receipt count visibly drops to ~0.
#
# HONEST PERSISTENCE — the doctrine trap here is that almost EVERY dir in the container is
# writable (incl. $HOME and the module dir), but only a PROVISIONED persistent volume
# survives a redeploy. On HF Spaces that volume is mounted at exactly /data, and ONLY when
# the Space has persistent storage enabled (a per-Space settings toggle — founder/Forge).
# So we must NOT equate "writable" with "persistent": a writable /home or ./ is ephemeral.
#
# Resolution (additive, never fabricates persistence):
#   1. SZL_ENERGY_LEDGER_PATH explicit override → use it verbatim, marked persistent
#      (operator deliberately chose it — e.g. points it at the real mount).
#   2. else, if a KNOWN persistent mount is writable (A11OY_DATA_DIR if set, or /data — the
#      HF persistent disk this repo already standardises on, see szl_unay_routes /
#      szl_pnt_mesh) → use it, marked persistent. The chain then CONTINUES across a redeploy.
#   3. else → module-adjacent file, marked EPHEMERAL, and we LOG a clear warning. We never
#      claim the chain survives when the persistent volume isn't actually mounted. The moment
#      /data is provisioned (founder/Forge) the code uses it on the next boot, no edit needed.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_EPHEMERAL_LEDGER_PATH = os.path.join(_MODULE_DIR, "szl_energy_ledger.jsonl")

# Dirs that are genuinely durable across a redeploy WHEN present/mounted. Deliberately does
# NOT include $HOME or ./ — those are writable but ephemeral, and treating them as persistent
# would be a fabricated-persistence claim. A11OY_DATA_DIR lets the operator name another mount.
_PERSISTENT_MOUNT_CANDIDATES = ("/data", "/opt/szl/a11oy-data")


def _dir_is_writable(d: str) -> bool:
    """True iff we can create `d` and write a probe file in it (a REAL write test, not a
    guess — mirrors szl_unay_routes._pick_data_dir so the persistence story is consistent
    across the repo)."""
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".szl_energy_ledger.wtest")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _persistent_ledger_path() -> tuple[str, bool]:
    """Resolve (path, persistent). `persistent` is True ONLY when the path sits on a volume
    that genuinely survives a redeploy — an explicit operator override, A11OY_DATA_DIR, or a
    mounted /data. A merely-writable $HOME/./ is treated as EPHEMERAL (False), never faked."""
    explicit = os.getenv("SZL_ENERGY_LEDGER_PATH")
    if explicit:
        return explicit, True

    candidates = []
    env_dir = os.environ.get("A11OY_DATA_DIR")
    if env_dir:
        candidates.append(env_dir)
    candidates.extend(_PERSISTENT_MOUNT_CANDIDATES)

    for d in candidates:
        if d and _dir_is_writable(d):
            return os.path.join(d, "szl_energy_ledger.jsonl"), True

    return _EPHEMERAL_LEDGER_PATH, False


def _path_is_persistent(path: str) -> bool:
    """Whether a ledger `path` is on a genuinely durable (survives-redeploy) location.

    True for: the explicit SZL_ENERGY_LEDGER_PATH, anything under A11OY_DATA_DIR, or under a
    known persistent mount (/data, /opt/szl/a11oy-data). False for the ephemeral module path.
    Honest by construction — a merely-writable $HOME/./ is NOT counted as persistent."""
    if not path or path == _EPHEMERAL_LEDGER_PATH:
        return False
    explicit = os.getenv("SZL_ENERGY_LEDGER_PATH")
    if explicit and os.path.abspath(path) == os.path.abspath(explicit):
        return True
    roots = list(_PERSISTENT_MOUNT_CANDIDATES)
    env_dir = os.environ.get("A11OY_DATA_DIR")
    if env_dir:
        roots.append(env_dir)
    ap = os.path.abspath(path)
    return any(ap == os.path.abspath(r) or ap.startswith(os.path.abspath(r) + os.sep)
               for r in roots)


DEFAULT_LEDGER_PATH, _DEFAULT_LEDGER_PERSISTENT = _persistent_ledger_path()

if not _DEFAULT_LEDGER_PERSISTENT:
    # Honest signal: the chain will re-genesis on the next redeploy because no persistent
    # volume is mounted. Set SZL_ENERGY_LEDGER_PATH or mount /data to make it survive.
    print(
        "[szl_energy_ledger] WARNING: ledger path %r is EPHEMERAL (no persistent volume "
        "mounted) — the receipt chain will re-genesis (seq->0) on the next redeploy. "
        "Mount /data or set SZL_ENERGY_LEDGER_PATH to a persistent path to keep the chain."
        % DEFAULT_LEDGER_PATH
    )
else:
    print("[szl_energy_ledger] ledger persists to %r (survives redeploy)" % DEFAULT_LEDGER_PATH)

DOCTRINE_NOTE = (
    "Doctrine v11: NO free-energy. Billable ONLY when joules_label==MEASURED and NVML "
    "sample fresh (<30s); SAMPLE/ESTIMATE/stale REFUSED. DRY-RUN billing with no STRIPE "
    "key (would_charge_cents, no money moves). sovereign=false. Λ=Conjecture 1. Revenue "
    "is MEASURED only when a real charge clears, else ESTIMATE/ZERO. Every receipt "
    "re-hashable offline; chain is hash-linked (prev_digest), tamper breaks the chain."
)


# ---------------------------------------------------------------------------
# JobRecord — the contract Dev1's operator daemon emits per completed inference job.
# We build against THIS interface (coordinated via the shared energy endpoints) and
# do not block on Dev1's implementation.
# ---------------------------------------------------------------------------
@dataclass
class JobRecord:
    node: str
    joules_measured: float
    joules_label: str                 # "measured" | "sample" | "estimate" (operator label)
    tokens: int
    wall_s: float
    ts: str                           # ISO-8601 UTC of job completion
    model: str
    nvml_age_s: Optional[float] = None  # explicit NVML sample age; if None, derived from ts
    grid_price_eur_mwh: float = 0.0     # grid price at the sample (negative = grid paid us)

    @staticmethod
    def from_dict(d: dict) -> "JobRecord":
        # The operator emits joules_measured=None for every non-billable job (SAMPLE
        # energy, stale meter, or stub mode). That is NOT an error — it is the honest
        # "no measured joules" signal. Coerce it to 0.0 here so the receipt still mints
        # (recorded with billable=false at the gate); NEVER let a None crash the
        # subscriber, which would silently drop the job (the demo's 0-receipts bug).
        raw_j = d.get("joules_measured")
        joules_measured = 0.0 if raw_j is None else float(raw_j)
        return JobRecord(
            node=str(d["node"]),
            joules_measured=joules_measured,
            joules_label=str(d.get("joules_label", "sample")),
            tokens=int(d.get("tokens", 0)),
            wall_s=float(d.get("wall_s", 0.0)),
            ts=str(d.get("ts") or datetime.now(timezone.utc).isoformat()),
            model=str(d.get("model", "unknown")),
            nvml_age_s=(None if d.get("nvml_age_s") is None else float(d["nvml_age_s"])),
            grid_price_eur_mwh=float(d.get("grid_price_eur_mwh", 0.0)),
        )


def _derive_nvml_age_s(job: JobRecord, now: Optional[float] = None) -> float:
    """Age of the NVML sample in seconds. Prefer the explicit field; otherwise derive
    it from the job completion timestamp vs now. Unparseable ts -> treated as stale."""
    if job.nvml_age_s is not None:
        return job.nvml_age_s
    now = time.time() if now is None else now
    try:
        ts = datetime.fromisoformat(job.ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, now - ts.timestamp())
    except Exception:
        return float(MAX_NVML_AGE_S + 1)  # cannot prove freshness -> stale -> refused


def _entry_digest(seq: int, prev_digest: str, payload_digest: str) -> str:
    """Hash that binds an entry to its position and its predecessor. Re-derivable
    offline: sha256 over the canonical {seq, prev_digest, payload_digest}."""
    return sha256_canon(
        {"seq": seq, "prev_digest": prev_digest, "payload_digest": payload_digest}
    )


# ---------------------------------------------------------------------------
# The hash-chained ledger.
# ---------------------------------------------------------------------------
class EnergyLedger:
    """Append-only, hash-chained, offline-verifiable ledger of JouleCharge receipts.

    Each entry:
      {seq, prev_digest, receipt, billable, reason, charge, idempotency_key, entry_digest}
    where receipt == build_receipt(...) (carries its own payload_digest), entry_digest
    binds (seq, prev_digest, receipt.payload_digest). Genesis prev_digest = 64 zeros.

    Idempotency: an idempotency_key already present is never appended twice.
    Persistence: JSONL, one entry per line, appended on write; reloaded on construction.
    """

    def __init__(self, path: Optional[str] = None,
                 price_per_kwh_cents: int = DEFAULT_PRICE_PER_KWH_CENTS):
        self.path = path if path is not None else DEFAULT_LEDGER_PATH
        self.price_per_kwh_cents = price_per_kwh_cents
        self._entries: list[dict] = []
        self._idem_seen: set[str] = set()
        self._lock = threading.Lock()
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        """Reload the chain from disk so it survives a restart. Bad lines are skipped
        honestly (never silently fabricated)."""
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._entries.append(entry)
                    k = entry.get("idempotency_key")
                    if k:
                        self._idem_seen.add(k)
        except OSError:
            pass

    def _persist_entry(self, entry: dict) -> None:
        """Append one entry to the JSONL file + fsync so a crash-after-append survives."""
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            pass

    # -- core append -------------------------------------------------------
    def prev_digest(self) -> str:
        """The digest the next entry must chain from (genesis = 64 zeros)."""
        if not self._entries:
            return GENESIS_PREV
        return self._entries[-1]["entry_digest"]

    def append_job(self, job: JobRecord, now: Optional[float] = None) -> dict:
        """Build a JouleCharge receipt for one job and append it to the chain.

        Refuses to BILL non-MEASURED / stale joules (the receipt is still recorded with
        billable=false + charge.status="blocked", so the refusal is itself auditable).
        DRY-RUN bills when no STRIPE_API_KEY. Idempotent on the receipt digest: a repeat
        job that produces the same receipt digest is NOT appended a second time."""
        with self._lock:
            # Normalize the operator's label to the billing core's vocabulary. The
            # billing gate only ever treats the literal "MEASURED" as billable; any
            # other label (sample/estimate/...) is refused — which is the doctrine.
            label = (job.joules_label or "").strip().upper()
            nvml_age_s = _derive_nvml_age_s(job, now=now)

            reading = JouleReading(
                node=job.node,
                joules=job.joules_measured,
                label=label,
                nvml_age_s=nvml_age_s,
                grid_price_eur_mwh=job.grid_price_eur_mwh,
                ts=job.ts,
            )
            billable, reason = reading.is_billable()
            receipt = build_receipt(reading, self.price_per_kwh_cents)
            idem = d_idem(receipt)

            # Idempotency: same receipt digest -> same idem key -> never double-append.
            if idem in self._idem_seen:
                existing = next(
                    (e for e in self._entries if e.get("idempotency_key") == idem), None
                )
                return {
                    "appended": False,
                    "duplicate": True,
                    "idempotency_key": idem,
                    "entry": existing,
                }

            if billable:
                charge = charge_stripe(receipt, customer=os.getenv("STRIPE_CUSTOMER", "cus_demo"),
                                       api_key=os.getenv("STRIPE_API_KEY", ""))
            else:
                charge = {"status": "blocked", "reason": reason}

            seq = len(self._entries)
            prev = self.prev_digest()
            entry = {
                "seq": seq,
                "prev_digest": prev,
                "receipt": receipt,
                "job": {
                    "node": job.node,
                    "tokens": job.tokens,
                    "wall_s": job.wall_s,
                    "model": job.model,
                    "ts": job.ts,
                    "nvml_age_s": nvml_age_s,
                },
                "billable": billable,
                "reason": reason,
                "charge": charge,
                "idempotency_key": idem,
                "entry_digest": _entry_digest(seq, prev, receipt["payload_digest"]),
            }
            self._entries.append(entry)
            self._idem_seen.add(idem)
            self._persist_entry(entry)
            return {"appended": True, "duplicate": False,
                    "idempotency_key": idem, "entry": entry}

    # -- verification ------------------------------------------------------
    def verify(self) -> dict:
        """Offline-verifiable end-to-end chain integrity verdict.

        Checks, in order, for every entry:
          (a) the receipt re-hashes to its own payload_digest (receipt not tampered);
          (b) entry_digest == _entry_digest(seq, prev_digest, payload_digest);
          (c) prev_digest links to the prior entry's entry_digest (genesis = 64 zeros).
        Returns {ok, length, first_break|None, links_intact, receipts_intact}."""
        first_break: Optional[dict] = None
        links_intact = True
        receipts_intact = True
        expected_prev = GENESIS_PREV

        for i, e in enumerate(self._entries):
            receipt = e.get("receipt", {})
            decision = receipt.get("decision", {})
            # (a) receipt re-hashes to its digest
            recomputed = sha256_canon(decision)
            if recomputed != receipt.get("payload_digest"):
                receipts_intact = False
                if first_break is None:
                    first_break = {"index": i, "reason": "receipt payload_digest mismatch "
                                   "(receipt tampered)"}
            # (b) entry_digest binds (seq, prev_digest, payload_digest)
            recomputed_entry = _entry_digest(
                e.get("seq"), e.get("prev_digest"), receipt.get("payload_digest")
            )
            if recomputed_entry != e.get("entry_digest"):
                links_intact = False
                if first_break is None:
                    first_break = {"index": i, "reason": "entry_digest mismatch "
                                   "(entry tampered or reordered)"}
            # (c) prev_digest chains to the prior entry_digest
            if e.get("prev_digest") != expected_prev:
                links_intact = False
                if first_break is None:
                    first_break = {"index": i, "reason": "prev_digest does not link to "
                                   "prior entry_digest (chain broken)"}
            expected_prev = e.get("entry_digest")

        ok = first_break is None and links_intact and receipts_intact
        return {
            "ok": ok,
            "length": len(self._entries),
            "first_break": first_break,
            "links_intact": links_intact,
            "receipts_intact": receipts_intact,
            "genesis_prev": GENESIS_PREV,
        }

    # -- views -------------------------------------------------------------
    def entries(self) -> list[dict]:
        return list(self._entries)

    def get_by_idem(self, idem: str) -> Optional[dict]:
        for e in self._entries:
            if e.get("idempotency_key") == idem:
                return e
        return None

    def totals(self) -> dict:
        """Aggregate totals across the chain. would_charge_cents sums dry-run +
        charged amounts for BILLABLE entries only (blocked entries contribute 0).
        joules_measured_total sums only MEASURED-billable joules (honest)."""
        jobs = len(self._entries)
        joules_total = 0.0
        joules_measured_billable = 0.0
        tokens_total = 0
        would_charge_cents = 0
        charged_cents = 0
        blocked = 0
        dry_run = 0
        for e in self._entries:
            d = e.get("receipt", {}).get("decision", {})
            joules_total += float(d.get("joules_measured", 0.0) or 0.0)
            tokens_total += int(e.get("job", {}).get("tokens", 0) or 0)
            charge = e.get("charge", {})
            status = charge.get("status")
            if e.get("billable"):
                joules_measured_billable += float(d.get("joules_measured", 0.0) or 0.0)
            if status == "dry-run":
                would_charge_cents += int(charge.get("would_charge_cents", 0) or 0)
                dry_run += 1
            elif status == "charged":
                charged_cents += int(charge.get("amount_cents", 0) or 0)
            elif status == "blocked":
                blocked += 1
        return {
            "jobs": jobs,
            "joules_total": round(joules_total, 6),
            "joules_measured_billable": round(joules_measured_billable, 6),
            "tokens_total": tokens_total,
            "would_charge_cents": would_charge_cents,     # MODELED (dry-run projection)
            "charged_cents": charged_cents,               # MEASURED (real cleared charges)
            "blocked_count": blocked,
            "dry_run_count": dry_run,
            "kwh_total": round(joules_measured_billable / JOULES_PER_KWH, 9),
        }

    def persistence_info(self) -> dict:
        """Honest report of WHERE the chain persists and whether that survives a redeploy.

        `survives_redeploy` is True only when the ledger path sits on a genuinely durable
        volume (an explicit SZL_ENERGY_LEDGER_PATH override, A11OY_DATA_DIR, or a mounted
        /data). The ephemeral module-adjacent path is reported plainly as EPHEMERAL — we
        never claim durability we don't have."""
        on_persistent = _path_is_persistent(self.path)
        return {
            "path": self.path,
            "survives_redeploy": on_persistent,
            "label": "MEASURED" if on_persistent else "EPHEMERAL",
            "note": (
                "ledger on persistent volume — receipt chain (seq) continues across a "
                "redeploy" if on_persistent else
                "ledger on EPHEMERAL module path — chain re-genesises (seq->0) on the next "
                "redeploy; mount /data or set SZL_ENERGY_LEDGER_PATH to persist"
            ),
        }

    def summary(self) -> dict:
        """Full ledger view for the GET /energy/ledger endpoint."""
        return {
            "ok": True,
            "receipts": self.entries(),
            "chain": self.verify(),
            "totals": self.totals(),
            "persistence": self.persistence_info(),
            "price_per_kwh_cents": self.price_per_kwh_cents,
            "stripe_mode": "live" if os.getenv("STRIPE_API_KEY") else "dry-run",
            "doctrine": DOCTRINE_NOTE,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton ledger (shared by the operator-facing append path and the
# read endpoints). Constructed lazily so import never fails on a read-only FS.
# ---------------------------------------------------------------------------
_LEDGER: Optional[EnergyLedger] = None
_LEDGER_LOCK = threading.Lock()


def get_ledger() -> EnergyLedger:
    global _LEDGER
    if _LEDGER is None:
        with _LEDGER_LOCK:
            if _LEDGER is None:
                _LEDGER = EnergyLedger()
    return _LEDGER


def record_job(job_dict: dict) -> dict:
    """Convenience entrypoint for Dev1's operator: hand us a JobRecord dict, we build
    the receipt, append to the chain, and return the append result.

    Defensive: a single malformed JobRecord must NEVER crash the operator's emit loop
    (its subscriber dispatch swallows exceptions, so a raise here would silently DROP
    the job — exactly the bug that left the live ledger at 0 receipts). On any parse
    failure we record nothing and report it, rather than fabricating or crashing."""
    try:
        return get_ledger().append_job(JobRecord.from_dict(job_dict))
    except Exception as exc:  # noqa: BLE001 — never let a bad record kill the emit loop
        return {"appended": False, "duplicate": False, "error": str(exc)}


def wire_operator_to_ledger(operator: Any, ledger: Optional["EnergyLedger"] = None,
                            backfill: bool = True) -> dict:
    """Wire an OperatorDaemon's completed-job emit stream into the hash-chained ledger.

    This is THE wiring the demo needs: every completed JobRecord the operator emits is
    minted into a signed JouleCharge receipt and appended to the chain. It:

      1. Subscribes ``record_job`` so all FUTURE completed jobs mint a receipt.
      2. If ``backfill`` and the operator is ALREADY running (the singleton on the box
         started before this wiring), replays the jobs the operator is holding in its
         in-memory recent-records buffer so the ledger shows receipts IMMEDIATELY rather
         than only from the next job. The ledger's idempotency (same receipt digest never
         double-appends) makes replay safe even if those jobs also arrive via the live
         subscription — no double-charge, no double-receipt.

    Honest about backfill limits: the operator persists only AGGREGATE counts across a
    restart (not per-job records), so backfill can only replay jobs still in the live
    in-memory buffer of a running daemon. Jobs from a PRIOR process are gone — we never
    fabricate a per-job receipt for an aggregate we cannot itemize. New jobs always mint.

    Idempotent wiring: calling this twice does not register ``record_job`` twice (the
    operator's subscriber list would otherwise grow), guarded by a sentinel attribute.
    """
    led = ledger if ledger is not None else get_ledger()
    result = {"subscribed": False, "backfilled": 0, "backfill_duplicates": 0,
              "already_wired": False}

    def _append(job_dict: dict) -> None:
        # Subscriber callback: mint a receipt for each completed job onto THIS ledger.
        # Must never raise — the operator's emit loop swallows subscriber exceptions, so
        # a raise would silently drop the job (the 0-receipts bug). Bind to `led` so the
        # live hook and the backfill target the same chain (the singleton in production).
        try:
            led.append_job(JobRecord.from_dict(job_dict))
        except Exception:  # noqa: BLE001 — a bad record never breaks the emit loop
            pass

    # Idempotent subscribe: don't stack the callback twice on repeated wiring.
    if getattr(operator, "_ledger_wired", False):
        result["already_wired"] = True
    else:
        operator.subscribe(_append)
        try:
            operator._ledger_wired = True  # sentinel; harmless if it can't be set
        except Exception:  # noqa: BLE001
            pass
        result["subscribed"] = True

    if backfill:
        # The operator keeps a rolling tail of recent completed JobRecord dicts. Replay
        # them through the ledger; idempotency dedupes anything the live hook also caught.
        recent: list = []
        try:
            recent = list(getattr(operator, "_last_records", []) or [])
        except Exception:  # noqa: BLE001
            recent = []
        for job_dict in recent:
            try:
                out = led.append_job(JobRecord.from_dict(job_dict))
            except Exception:  # noqa: BLE001 — a bad historical record never breaks wiring
                continue
            if out.get("appended"):
                result["backfilled"] += 1
            elif out.get("duplicate"):
                result["backfill_duplicates"] += 1

    return result


# ---------------------------------------------------------------------------
# HTTP handlers + registration (dual-register via add_api_route, matching
# szl_energy_provenance.register()). Registered BEFORE the SPA catch-all.
# ---------------------------------------------------------------------------
def handle_ledger() -> dict:
    return get_ledger().summary()


def handle_receipt(idem: str) -> dict:
    e = get_ledger().get_by_idem(idem)
    if e is None:
        return {"ok": False, "error": "no receipt for idempotency_key", "idempotency_key": idem}
    receipt = e.get("receipt", {})
    recomputed = sha256_canon(receipt.get("decision", {}))
    return {
        "ok": True,
        "idempotency_key": idem,
        "entry": e,
        "rehash": {
            "recomputed_payload_digest": recomputed,
            "stored_payload_digest": receipt.get("payload_digest"),
            "matches": recomputed == receipt.get("payload_digest"),
        },
        "doctrine": DOCTRINE_NOTE,
    }


def register(app, ns: str = "a11oy"):
    """Mount the ledger read endpoints under /api/<ns>/v1/energy/* (and a short alias).

    Dual-register: prefer FastAPI's add_api_route (so routes resolve BEFORE the SPA
    catch-all, matching the other szl_* modules); fall back to a Starlette Route append
    for a bare Starlette app. Returns the list of mounted paths."""
    from starlette.responses import JSONResponse

    base = f"/api/{ns}/v1/energy"

    # Annotated with the module-scope Request so FastAPI injects it (not a 422 query param).
    def _h_ledger(request: _Request):
        return JSONResponse(handle_ledger())

    def _h_receipt(request: _Request):
        idem = request.path_params.get("idem", "")
        return JSONResponse(handle_receipt(idem))

    handlers = [
        (f"{base}/ledger", _h_ledger),
        (f"{base}/receipt/{{idem}}", _h_receipt),
        ("/energy/receipt/{idem}", _h_receipt),   # short alias per spec
    ]

    add_api_route = getattr(app, "add_api_route", None)
    mounted = []
    for path, fn in handlers:
        try:
            if callable(add_api_route):
                app.add_api_route(path, fn, methods=["GET"])
            else:
                from starlette.routing import Route
                app.router.routes.append(Route(path, fn))
            mounted.append(path)
        except Exception:
            continue
    return mounted


# ---------------------------------------------------------------------------
# Self-test — no server. Builds a chain, verifies, tampers, checks the gates.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    import tempfile

    out: dict = {}
    now = 1_000_000.0
    fresh_ts = datetime.fromtimestamp(now - 5.0, tz=timezone.utc).isoformat()
    stale_ts = datetime.fromtimestamp(now - 120.0, tz=timezone.utc).isoformat()

    tmp = tempfile.mktemp(suffix=".jsonl")
    led = EnergyLedger(path=tmp, price_per_kwh_cents=45)

    # (1) a MEASURED, fresh job -> billable, dry-run (no STRIPE key in test).
    r1 = led.append_job(JobRecord(
        node="betterwithage", joules_measured=78369.586, joules_label="measured",
        tokens=512, wall_s=8.0, ts=fresh_ts, model="qwen2.5-coder:7b",
        nvml_age_s=12.0, grid_price_eur_mwh=-2.90), now=now)
    assert r1["appended"] and r1["entry"]["billable"], r1
    assert r1["entry"]["charge"]["status"] == "dry-run", r1["entry"]["charge"]
    assert r1["entry"]["charge"]["would_charge_cents"] >= 1, r1["entry"]["charge"]
    out["measured_fresh_dry_run"] = True

    # (2) receipt re-hashes to its digest.
    rec = r1["entry"]["receipt"]
    assert sha256_canon(rec["decision"]) == rec["payload_digest"]
    out["receipt_rehashes"] = True

    # (3) a SAMPLE job -> refused from billing (recorded, charge blocked).
    r2 = led.append_job(JobRecord(
        node="chaski", joules_measured=5000.0, joules_label="sample",
        tokens=128, wall_s=2.0, ts=fresh_ts, model="mistral",
        nvml_age_s=3.0), now=now)
    assert r2["appended"] and not r2["entry"]["billable"], r2
    assert r2["entry"]["charge"]["status"] == "blocked", r2["entry"]["charge"]
    out["sample_blocked"] = True

    # (4) an ESTIMATE job -> refused.
    r3 = led.append_job(JobRecord(
        node="chaski", joules_measured=4000.0, joules_label="estimate",
        tokens=64, wall_s=1.0, ts=fresh_ts, model="deepseek-r1:14b",
        nvml_age_s=3.0), now=now)
    assert not r3["entry"]["billable"] and r3["entry"]["charge"]["status"] == "blocked"
    out["estimate_blocked"] = True

    # (5) a STALE MEASURED job (>30s) -> refused.
    r4 = led.append_job(JobRecord(
        node="betterwithage", joules_measured=9000.0, joules_label="measured",
        tokens=256, wall_s=4.0, ts=stale_ts, model="llama3.1:8b",
        nvml_age_s=None), now=now)  # derived age ~120s -> stale
    assert not r4["entry"]["billable"], r4
    assert "stale" in r4["entry"]["reason"].lower(), r4["entry"]["reason"]
    out["stale_blocked"] = True

    # (6) chain verifies end-to-end.
    v0 = led.verify()
    assert v0["ok"] and v0["length"] == 4 and v0["first_break"] is None, v0
    assert led.entries()[0]["prev_digest"] == GENESIS_PREV
    out["chain_verifies"] = True

    # (7) idempotency: replaying job #1 does NOT double-append.
    r1b = led.append_job(JobRecord(
        node="betterwithage", joules_measured=78369.586, joules_label="measured",
        tokens=512, wall_s=8.0, ts=fresh_ts, model="qwen2.5-coder:7b",
        nvml_age_s=12.0, grid_price_eur_mwh=-2.90), now=now)
    assert not r1b["appended"] and r1b["duplicate"], r1b
    assert led.verify()["length"] == 4
    out["idempotent_no_double_append"] = True

    # (8) TAMPER one entry -> chain breaks (receipt mutated).
    led._entries[0]["receipt"]["decision"]["amount_cents"] = 999999
    vt = led.verify()
    assert vt["ok"] is False and vt["first_break"]["index"] == 0, vt
    out["tamper_breaks_chain"] = True
    # restore so totals check below is clean
    led._entries[0]["receipt"]["decision"]["amount_cents"] = rec["decision"]["amount_cents"]

    # (9) totals correct: 1 billable dry-run, 3 blocked, would_charge>=1.
    t = led.totals()
    assert t["jobs"] == 4 and t["dry_run_count"] == 1 and t["blocked_count"] == 3, t
    assert t["would_charge_cents"] >= 1 and t["charged_cents"] == 0, t
    out["totals_correct"] = True

    # (10) persistence: a fresh ledger reading the same file reloads the chain + idem set.
    led2 = EnergyLedger(path=tmp, price_per_kwh_cents=45)
    assert led2.verify()["length"] == 4, led2.verify()
    r1c = led2.append_job(JobRecord(
        node="betterwithage", joules_measured=78369.586, joules_label="measured",
        tokens=512, wall_s=8.0, ts=fresh_ts, model="qwen2.5-coder:7b",
        nvml_age_s=12.0, grid_price_eur_mwh=-2.90), now=now)
    assert not r1c["appended"] and r1c["duplicate"], "idempotency must survive restart"
    out["persists_across_restart"] = True

    try:
        os.remove(tmp)
    except OSError:
        pass

    out["doctrine"] = DOCTRINE_NOTE
    out["ok"] = all(v is True for k, v in out.items() if isinstance(v, bool))
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
