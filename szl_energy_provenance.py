"""
szl_energy_provenance.py — tamper-evident PROVENANCE CHAIN for a11oy energy receipts.

The "honest AI on honest power, with receipts" proof layer. It extends/complements
szl_energy_budget.py (#328): where the budget module produces a Bekenstein-GATED
receipt per compute task, this module binds those receipts into a verifiable,
append-only, hash-linked ledger (a mini Merkle/Rekor-style transparency log) so the
whole energy history is tamper-evident and offline-verifiable — matching SZL's
cosign + Rekor + in-toto receipt doctrine.

  GET  /api/<ns>/v1/energy/provenance   -> chain head + length + verify() status

Each chain entry records (and hash-binds):
  prev_hash        receipt_hash of the immediately prior entry ("" for genesis)
  receipt_hash     sha256 over the canonical bytes of THIS entry's content
  task_hash        stable id of the task inputs (from szl_energy_budget.task_hash)
  bytes            output bytes the task produced (n)
  shannon_bits     Shannon information content of the output (bits)
  bekenstein_bound N·8 — the SZL canonical Bekenstein software bound (TH6/F19)
  within_bound     shannon_bits <= bekenstein_bound (the F19/TH6 gate)
  energy_source    harvest source label (e.g. curtailed-solar, off-peak, grid)
  joules_est       SAMPLE/ESTIMATE energy draw — NOT a metered value
  ts               ISO-8601 UTC timestamp

A v2 entry (schema szl.energy-provenance.entry/v2) additionally hash-binds
  schema, measurement_label, measurement_scope, window_joules_measured, source,
  source_seq and node. measurement_label is MEASURED only when the entry carries a
  verified NVML counter window over a bounded host window (scope
  BOUNDED_METER_WINDOW); every other v2 entry is SAMPLE. A v1 entry keeps its
  historical field set and encoding, so its receipt_hash is unchanged.

verify() walks the chain and confirms BOTH:
  (1) link integrity — each entry's prev_hash equals the prior entry's receipt_hash,
      and each entry's recomputed content hash equals its recorded receipt_hash
      (so any tampering of any field, or any reordering/insertion/deletion, is caught);
  (2) the Bekenstein gate — every entry has within_bound is True.
A bounded chain (max_entries) evicts its oldest entries and verifies the retained
suffix from an explicit retention anchor, which verify() and summary() report.

DOCTRINE (v11/v12, NEVER violated):
  - NO free-energy / perpetual-motion claims. The chain proves WHAT was receipted and
    that it is UNTAMPERED + Bekenstein-bounded — it does NOT upgrade an estimate into a
    measurement. A numeric joules_est stays labeled SAMPLE/ESTIMATE; a v2 entry that
    carries no estimate records joules_est null labeled UNAVAILABLE.
  - Tamper-EVIDENT, not tamper-proof: it proves the recorded history is internally
    consistent and gate-passing. Its only measured claim is scoped: a v2 entry's
    window_joules_measured is MEASURED within BOUNDED_METER_WINDOW when it carries a
    verified NVML counter window over a bounded host window (written by the energy
    operator bridge). That is never per-job billable energy. append_receipt() writes
    SAMPLE entries only. The chain is process-local and resets on restart.
  - open-weight only; never commit a key. Pure stdlib; no numpy, no network.

Reuses the canonical Bekenstein/Shannon math from szl_energy_budget when that module
is importable (#328); otherwise carries a byte-identical local fallback so this module
runs and self-tests standalone (the PR depends on #328 but does not require it merged).
"""
import hashlib
import json
import math
import os
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional
from starlette.requests import Request  # module-scope so add_api_route injects Request, not a 'req' query param (422 fix)

# ---------------------------------------------------------------------------
# Canonical SZL Bekenstein/Shannon math — reuse #328 if present, else fallback.
# The fallback is byte-identical to szl_energy_budget so behavior never diverges.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - prefer the shared #328 module when it is on the path
    from szl_energy_budget import (
        bekenstein_bound,
        shannon_bits_of_bytes,
        task_hash,
        ENERGY_FIGURE_LABEL,
    )
    _SOURCE = "szl_energy_budget (#328)"
except Exception:  # standalone fallback — keeps self-test + serve robust pre-merge
    import math

    ENERGY_FIGURE_LABEL = "SAMPLE/ESTIMATE (no real power meter wired — doctrine v11/v12)"

    def shannon_bits_of_bytes(data: bytes) -> float:
        n = len(data)
        if n == 0:
            return 0.0
        counts = Counter(data)
        probs = [c / n for c in counts.values()]
        per_byte = -sum(p * math.log2(p) for p in probs if p > 0)  # in [0, 8]
        return per_byte * n

    def bekenstein_bound(n_bytes: int) -> int:
        return int(n_bytes) * 8

    def task_hash(inputs: dict) -> str:
        blob = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    _SOURCE = "local fallback (szl_energy_budget not importable)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Fields that are hash-bound into receipt_hash. ORDER-INDEPENDENT (sorted in the
# canonical encoding), but the SET is fixed so a dropped/added field is detected.
_HASHED_FIELDS = (
    "prev_hash", "task_hash", "bytes", "shannon_bits",
    "bekenstein_bound", "within_bound", "energy_source", "joules_est", "ts",
)

ENTRY_SCHEMA_V2 = "szl.energy-provenance.entry/v2"
MEASUREMENT_SCOPE_WINDOW = "BOUNDED_METER_WINDOW"
_HASHED_FIELDS_V2 = _HASHED_FIELDS + (
    "schema", "measurement_label", "measurement_scope", "window_joules_measured",
    "source", "source_seq", "node",
)

# Retention bound for the process chain the operator feeds. Oldest entries are
# evicted behind an explicit anchor rather than growing memory without limit.
MAX_ENTRIES_ENV = "SZL_ENERGY_PROVENANCE_MAX_ENTRIES"
_MAX_ENTRIES_DEFAULT = 2000  # a public read walks the whole chain once
_MAX_ENTRIES_CEILING = 10000
NO_ESTIMATE_LABEL = "UNAVAILABLE (no joules estimate made)"
_UNSET = object()


def _max_entries_from_env() -> int:
    raw = (os.environ.get(MAX_ENTRIES_ENV) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return _MAX_ENTRIES_DEFAULT
    if value < 1:
        return _MAX_ENTRIES_DEFAULT
    return min(value, _MAX_ENTRIES_CEILING)


def _verified_window(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0)


def _hashed_fields(entry: dict) -> Optional[tuple]:
    if "schema" not in entry:
        return _HASHED_FIELDS
    if entry.get("schema") == ENTRY_SCHEMA_V2:
        return _HASHED_FIELDS_V2
    return None  # an unknown schema marker is not a format this chain wrote


def _canonical_bytes(entry: dict) -> bytes:
    """Deterministic canonical encoding of the hash-bound content of an entry.

    Excludes receipt_hash itself (it is the digest of this blob). Uses sorted keys
    and tight separators so the bytes are stable across processes — the same rule
    szl_energy_budget.task_hash uses, so receipts are reproducible + offline-checkable.
    """
    fields = _hashed_fields(entry)
    if fields is None:
        raise KeyError("schema")
    payload = {k: entry[k] for k in fields}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt_hash(entry: dict) -> Optional[str]:
    try:
        return hashlib.sha256(_canonical_bytes(entry)).hexdigest()
    except (KeyError, TypeError, ValueError):
        return None  # a malformed entry can never match its recorded hash


def _claims_measured_window(entry: dict) -> bool:
    """Field shape only; the caller must also confirm the entry's own hash."""
    return (entry.get("schema") == ENTRY_SCHEMA_V2
            and entry.get("measurement_label") == "MEASURED"
            and entry.get("measurement_scope") == MEASUREMENT_SCOPE_WINDOW
            and _verified_window(entry.get("window_joules_measured")))


class EnergyProvenanceChain:
    """Append-only, hash-linked ledger of Bekenstein-gated energy receipts.

    Each appended entry links to the prior via prev_hash == prior.receipt_hash, so the
    chain is a tamper-evident transparency log: any change to any past field, or any
    reorder/insert/delete, breaks a link and is caught by verify().
    """

    def __init__(self, max_entries: Optional[int] = None) -> None:
        self._chain: list[dict] = []
        # The operator appends from its worker thread while reads verify from request
        # threads; one lock keeps every walk consistent with a single chain state.
        self._lock = threading.RLock()
        self._max_entries = (int(max_entries) if max_entries is not None
                             and not isinstance(max_entries, bool)
                             and int(max_entries) > 0 else None)
        self._dropped = 0
        self._anchor_prev_hash = ""
        # A defect found in an entry while it was being evicted. Sticky, so eviction
        # can never make earlier tampering disappear from verify().
        self._evicted_break: Optional[dict] = None

    # -- construction -------------------------------------------------------
    def append(
        self,
        output: bytes | str | None = None,
        output_bytes: int | None = None,
        shannon_bits: float | None = None,
        energy_source: str = "grid",
        joules_est: Any = _UNSET,
        *,
        window_joules_measured: Any = None,
        measurement_scope: Optional[str] = None,
        source: Optional[str] = None,
        source_seq: Any = None,
        node: Optional[str] = None,
    ) -> dict:
        """Build + append one hash-linked, Bekenstein-gated provenance entry.

        Computes shannon_bits + bytes from `output` when given; else uses the supplied
        sizes (worst-case full-entropy bytes*8 if shannon_bits omitted). within_bound
        is the proven F19/TH6 gate. joules_est is clamped nonneg and stays SAMPLE.

        Passing any measurement keyword writes a v2 entry. It is MEASURED only for a
        finite positive window_joules_measured with scope BOUNDED_METER_WINDOW;
        otherwise the entry is SAMPLE and records no window. A v2 entry records no
        joules estimate (null, UNAVAILABLE) unless joules_est is supplied.
        """
        if output is not None:
            data = output.encode("utf-8") if isinstance(output, str) else bytes(output)
            n_bytes = len(data)
            s_bits = round(shannon_bits_of_bytes(data), 6)
        else:
            n_bytes = int(output_bytes or 0)
            s_bits = round(float(shannon_bits) if shannon_bits is not None else float(n_bytes * 8), 6)
        bound = bekenstein_bound(n_bytes)
        within = bool(s_bits <= bound + 1e-9)
        v2 = any(value is not None for value in
                 (window_joules_measured, measurement_scope, source, source_seq, node))
        if joules_est is _UNSET:
            joules_est = None if v2 else 0.0
        if joules_est is None and v2:
            j_est, j_label = None, NO_ESTIMATE_LABEL
        else:
            j_est, j_label = round(max(0.0, float(joules_est)), 6), ENERGY_FIGURE_LABEL

        with self._lock:
            prev_hash = self._chain[-1]["receipt_hash"] if self._chain else self._anchor_prev_hash
            entry = {
                "prev_hash": prev_hash,
                "task_hash": task_hash({
                    "output_bytes": n_bytes, "shannon_bits": s_bits,
                    "energy_source": str(energy_source), "joules_est": j_est,
                }),
                "bytes": n_bytes,
                "shannon_bits": s_bits,
                "bekenstein_bound": bound,
                "within_bound": within,
                "energy_source": str(energy_source),
                "joules_est": j_est,
                "joules_est_label": j_label,
                "ts": _now(),
            }
            if v2:
                measured = (_verified_window(window_joules_measured)
                            and measurement_scope == MEASUREMENT_SCOPE_WINDOW)
                seq_ok = (not isinstance(source_seq, bool) and isinstance(source_seq, int)
                          and source_seq >= 0)
                entry.update({
                    "schema": ENTRY_SCHEMA_V2,
                    "measurement_label": "MEASURED" if measured else "SAMPLE",
                    "measurement_scope": MEASUREMENT_SCOPE_WINDOW if measured else None,
                    "window_joules_measured": (round(float(window_joules_measured), 6)
                                               if measured else None),
                    "source": str(source) if source is not None else None,
                    "source_seq": source_seq if seq_ok else None,
                    "node": str(node) if node is not None else None,
                })
            entry["receipt_hash"] = _receipt_hash(entry)
            self._chain.append(entry)
            if self._max_entries is not None and len(self._chain) > self._max_entries:
                self._evict(len(self._chain) - self._max_entries)
            return entry

    def _evict(self, drop: int) -> None:
        """Check the evicted prefix the way verify() would, then drop it. Called with
        the lock held. The anchor becomes the last evicted entry's receipt_hash, not a
        value the next retained entry declares about itself."""
        prev = self._anchor_prev_hash
        for offset, old in enumerate(self._chain[:drop]):
            recomputed = _receipt_hash(old)
            if self._evicted_break is None:
                reason = None
                if recomputed is None or recomputed != old.get("receipt_hash"):
                    reason = "receipt_hash mismatch in an evicted entry (content tampered)"
                elif old.get("prev_hash") != prev:
                    reason = "broken link in an evicted entry (prev_hash != prior receipt_hash)"
                elif old.get("within_bound") is not True:
                    reason = "Bekenstein gate failure in an evicted entry"
                if reason:
                    self._evicted_break = {"evicted_index": self._dropped + offset,
                                           "reason": reason}
            prev = old.get("receipt_hash")
        del self._chain[:drop]
        self._dropped += drop
        self._anchor_prev_hash = prev

    # -- inspection ---------------------------------------------------------
    def head(self) -> dict | None:
        with self._lock:
            return self._chain[-1] if self._chain else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._chain)

    def entries(self) -> list[dict]:
        with self._lock:
            return list(self._chain)

    def measured_window_entries(self) -> int:
        """Entries whose own hash binds a MEASURED bounded-window measurement."""
        return len(self._walk()[2])

    def _retention(self) -> Optional[dict]:
        if not self._dropped:
            return None
        return {"dropped_entries": self._dropped, "anchor_prev_hash": self._anchor_prev_hash}

    def _state_key(self) -> tuple:
        with self._lock:
            head = self._chain[-1]["receipt_hash"] if self._chain else None
            return (id(self), len(self._chain), self._dropped, head,
                    self._evicted_break is not None)

    def _walk(self) -> tuple:
        """One hashing pass over a consistent snapshot: (verify report, entries,
        MEASURED bounded-window entries). Nothing counts as measured unless the whole
        chain verifies, including every entry checked on eviction."""
        with self._lock:
            chain = list(self._chain)
            prev_hash = self._anchor_prev_hash
            retention = self._retention()
            evicted_break = dict(self._evicted_break) if self._evicted_break else None
        first_break: dict | None = None
        gate_failures: list[int] = []
        measured: list[dict] = []

        for i, entry in enumerate(chain):
            recomputed = _receipt_hash(entry)
            intact = recomputed is not None and recomputed == entry.get("receipt_hash")
            if not intact:
                if first_break is None:
                    first_break = {"index": i, "reason": "receipt_hash mismatch (entry content tampered)"}
            elif entry.get("prev_hash") != prev_hash:
                if first_break is None:
                    first_break = {"index": i, "reason": "broken link (prev_hash != prior receipt_hash)"}
            if intact and _claims_measured_window(entry):
                measured.append(entry)
            if entry.get("within_bound") is not True:
                gate_failures.append(i)
            prev_hash = entry.get("receipt_hash")

        links_ok = first_break is None
        gate_ok = len(gate_failures) == 0
        ok = bool(links_ok and gate_ok and evicted_break is None)
        if not ok:
            measured = []
        report = {
            "ok": ok,
            "length": len(chain),
            "links_intact": links_ok,
            "bekenstein_gate_all_pass": gate_ok,
            "head_hash": chain[-1]["receipt_hash"] if chain else "",
            "first_break": first_break,
            "gate_failures": gate_failures,
            "evicted_break": evicted_break,
            "retention_anchor": retention,
            "checked": ("each entry hashes to its receipt_hash; prev_hash chains to prior "
                        "(from the retention anchor when older entries were evicted); "
                        "within_bound True"),
            "verified_at": _now(),
        }
        return report, chain, measured

    # -- verification -------------------------------------------------------
    def verify(self) -> dict:
        """Walk the chain; confirm link integrity AND the Bekenstein gate.

        Returns an honest report: ok True only when EVERY entry (a) hashes to its
        recorded receipt_hash, (b) links to the prior entry's receipt_hash, and
        (c) passed the Bekenstein gate (within_bound True). The first failure is
        reported with its index + reason; later entries are still scanned for a
        full gate tally so the report is complete.
        """
        return self._walk()[0]

    def summary(self) -> dict:
        """Honest chain summary for the read endpoint: head + verify status + doctrine."""
        v, chain, measured = self._walk()
        retention = v["retention_anchor"] or {"dropped_entries": 0, "anchor_prev_hash": ""}
        head = chain[-1] if chain else None
        estimates = [e.get("joules_est") for e in chain
                     if isinstance(e.get("joules_est"), (int, float))
                     and not isinstance(e.get("joules_est"), bool)]
        unestimated = any(e.get("schema") == ENTRY_SCHEMA_V2 and e.get("joules_est") is None
                          for e in chain)
        if estimates or not unestimated:
            total_joules, total_label = round(sum(estimates), 6), ENERGY_FIGURE_LABEL
        else:
            total_joules, total_label = None, NO_ESTIMATE_LABEL
        v2_count = sum(1 for e in chain if e.get("schema") == ENTRY_SCHEMA_V2)
        if measured:
            window_reason = None
        elif chain and not v["ok"]:
            window_reason = "CHAIN_NOT_VERIFIED"
        else:
            window_reason = "NO_MEASURED_WINDOW_ENTRY"
        return {
            "model": "Proven Energy Engine — tamper-evident energy provenance chain",
            "status": "VERIFIED (hash-linked + Bekenstein gate)" if v["ok"] else
                      ("EMPTY" if not chain else "TAMPER DETECTED"),
            "length": len(chain),
            "head_hash": head["receipt_hash"] if head else "",
            "head": head,
            "verify": v,
            "total_joules_est": total_joules,
            "total_joules_est_label": total_label,
            "entry_schemas": {"v1": len(chain) - v2_count, "v2": v2_count},
            "measured_window_entries": len(measured),
            "window_joules_measured_total": round(
                sum(e["window_joules_measured"] for e in measured), 6),
            "window_joules_label": "MEASURED" if measured else "UNAVAILABLE",
            "window_joules_reason": window_reason,
            "window_joules_scope": MEASUREMENT_SCOPE_WINDOW,
            "retention": retention,
            "math_source": _SOURCE,
            "gate": "F19/TH6 Bekenstein: shannon_bits <= bytes*8 per entry",
            "link_rule": "entry.prev_hash == prior.receipt_hash; receipt_hash = sha256(canonical content)",
            "doctrine": "tamper-EVIDENT, which alone is not a measurement; NO free-energy claims; "
                        "a numeric joules_est stays SAMPLE/ESTIMATE; window_joules_measured is "
                        "MEASURED only on a hash-bound v2 entry carrying a verified NVML counter "
                        "window over a bounded host window, and only while the whole chain "
                        "verifies, never per-job billable energy; process-local, resets on "
                        "restart; open-weight only; never commit a key.",
            "composes": ["szl_energy_budget #328 (Bekenstein-gated receipts)",
                         "SZL cosign+Rekor+in-toto transparency-log doctrine",
                         "Showcase/Frontier/EnergyBudgetWitness.lean (0-sorry witness)"],
            "computed_at": _now(),
        }


# Process-local chain instance backing the read endpoint (resets on restart).
_CHAIN = EnergyProvenanceChain(max_entries=_max_entries_from_env())


def append_receipt(output: bytes | str | None = None, output_bytes: int | None = None,
                   shannon_bits: float | None = None, energy_source: str = "grid",
                   joules_est: float = 0.0) -> dict:
    """Module-level convenience: append a SAMPLE entry to the shared process chain.
    It takes no measurement keywords, so it can never write a MEASURED entry."""
    return _CHAIN.append(output=output, output_bytes=output_bytes,
                         shannon_bits=shannon_bits, energy_source=energy_source,
                         joules_est=joules_est)


_OPERATOR_SOURCE = "energy-operator"


def _public_node_name(node: str) -> str:
    """The operator's public display name; a private host never enters the chain."""
    try:
        from szl_energy_operator import _public_node
        return str(_public_node(node))
    except Exception:  # noqa: BLE001 — unknown mapping collapses to a generic label
        return "sovereign-gpu (private mesh)"


def append_operator_job(job: Any, chain: Optional[EnergyProvenanceChain] = None,
                        allowed_nodes: Optional[frozenset] = None) -> Optional[dict]:
    """Record one completed operator job as a v2 entry. Never raises.

    Only the bounded public summary is hashed as the entry's output: no GPU UUID,
    counter evidence, receipt id or private host. Stub jobs, external submissions
    (for example governed CPU code cells), jobs on a node outside allowed_nodes and
    malformed records are refused, so none of them reads as an operator GPU job.
    """
    target = chain if chain is not None else _CHAIN
    try:
        if not isinstance(job, dict):
            return None
        node = str(job.get("node") or "")
        if not node or node == "local-stub" or node.endswith("-stub"):
            return None
        if job.get("origin", "operator") != "operator":
            return None
        if allowed_nodes is not None and node not in allowed_nodes:
            return None
        seq = job.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            return None
        window = job.get("window_joules_measured")
        scope = job.get("joules_scope")
        verified = _verified_window(window) and scope == MEASUREMENT_SCOPE_WINDOW
        tokens = job.get("tokens")
        wall_s = job.get("wall_s")
        public = _public_node_name(node)
        output = json.dumps({
            "kind": str(job.get("kind") or ""),
            "model": str(job.get("model") or ""),
            "tokens": tokens if isinstance(tokens, int) and not isinstance(tokens, bool) else None,
            "wall_s": (round(float(wall_s), 6) if isinstance(wall_s, (int, float))
                       and not isinstance(wall_s, bool) and math.isfinite(wall_s) else None),
            "ts": str(job.get("ts") or ""),
            "seq": seq,
            "node": public,
            "window_joules_measured": round(float(window), 6) if verified else None,
            "joules_scope": MEASUREMENT_SCOPE_WINDOW if verified else None,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return target.append(
            output=output, energy_source="operator-job (grid mix unattributed)",
            joules_est=None,
            window_joules_measured=window if verified else None,
            measurement_scope=MEASUREMENT_SCOPE_WINDOW if verified else None,
            source=_OPERATOR_SOURCE, source_seq=seq, node=public)
    except Exception:  # noqa: BLE001 — a bad record never breaks the operator loop
        return None


def wire_operator_to_provenance(operator: Any,
                                chain: Optional[EnergyProvenanceChain] = None) -> dict:
    """Subscribe the chain to the operator's completed-job stream (idempotent).

    Wired at import time, before the boot autostart, so no job of this process is
    missed. Jobs completed before wiring are not itemised here; the JouleCharge
    ledger keeps its own record of them. Only the operator's configured GPU nodes
    are admitted.
    """
    if getattr(operator, "_provenance_wired", False):
        return {"subscribed": False, "already_wired": True}
    allowed = frozenset(str(getattr(node, "name", "")) for node in
                        (getattr(operator, "nodes", None) or [])
                        if getattr(node, "name", None))

    def _on_job(job_dict: dict) -> None:
        append_operator_job(job_dict, chain=chain, allowed_nodes=allowed)

    operator.subscribe(_on_job)
    operator._provenance_wired = True
    return {"subscribed": True, "already_wired": False}


# ---------------------------------------------------------------------------
# HTTP handler + registration (matches szl_energy_budget / szl_quantum_bio style).
# ---------------------------------------------------------------------------
# An anonymous read must not re-hash the whole chain on every request. The cached
# body is reused only while the chain state is unchanged and for at most this long.
_PUBLIC_SUMMARY_TTL_S = 5.0
_PUBLIC_SUMMARY_LOCK = threading.Lock()
_PUBLIC_SUMMARY: dict = {"key": None, "at": 0.0, "body": None}


def _public_summary() -> dict:
    chain = _CHAIN
    key = chain._state_key()
    now = time.monotonic()
    with _PUBLIC_SUMMARY_LOCK:
        if (_PUBLIC_SUMMARY["key"] == key and _PUBLIC_SUMMARY["body"] is not None
                and now - _PUBLIC_SUMMARY["at"] < _PUBLIC_SUMMARY_TTL_S):
            return _PUBLIC_SUMMARY["body"]
    body = chain.summary()
    with _PUBLIC_SUMMARY_LOCK:
        _PUBLIC_SUMMARY.update({"key": key, "at": now, "body": body})
    return body


def _h_provenance(req: Request):
    from starlette.responses import JSONResponse
    return JSONResponse(_public_summary())


def register(app, ns="a11oy"):
    """Wire the provenance read endpoint onto the app under /api/<ns>/v1/energy/provenance.

    Additive. Uses FastAPI's add_api_route when available (so it resolves before the
    SPA catch-all, matching the other szl_* modules); falls back to a Starlette route
    append for a bare Starlette app."""
    base = f"/api/{ns}/v1/energy"
    handlers = [
        (f"{base}/provenance", _h_provenance),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


def _selftest() -> dict:
    """No-server self-test: build a chain, tamper one entry, verify() catches it.

    Proves: a clean chain verifies ok; link integrity catches a mutated field; the
    chain catches a broken link (reorder); the Bekenstein gate flags an over-claim;
    energy figures carry the SAMPLE label. Pure core hashing + math.
    """
    out: dict = {}

    # (a) A clean, hash-linked chain of real receipts verifies ok.
    c = EnergyProvenanceChain()
    c.append(output=b"hello world", energy_source="curtailed-solar", joules_est=1.5)
    c.append(output=b"the quick brown fox", energy_source="off-peak", joules_est=2.25)
    c.append(output=b"AAAAAAAA", energy_source="grid", joules_est=0.0)
    v0 = c.verify()
    assert v0["ok"] is True, v0
    assert v0["length"] == 3 and v0["links_intact"] and v0["bekenstein_gate_all_pass"]
    out["clean_chain_verifies"] = True

    # (b) Genesis prev_hash is empty; every link chains to the prior receipt_hash.
    es = c.entries()
    assert es[0]["prev_hash"] == ""
    assert es[1]["prev_hash"] == es[0]["receipt_hash"]
    assert es[2]["prev_hash"] == es[1]["receipt_hash"]
    out["links_chain_to_prior"] = True

    # (c) TAMPER one entry's content -> verify() catches the receipt_hash mismatch.
    es[1]["energy_source"] = "nuclear-fusion-free-energy"  # the over-claim we must catch
    v1 = c.verify()
    assert v1["ok"] is False, v1
    assert v1["first_break"] is not None and v1["first_break"]["index"] == 1
    assert "receipt_hash mismatch" in v1["first_break"]["reason"]
    out["tamper_detected"] = True
    es[1]["energy_source"] = "off-peak"  # restore for the next check

    # (d) Re-fix the tampered hash but BREAK the link (swap two entries) -> caught.
    c2 = EnergyProvenanceChain()
    c2.append(output=b"alpha", energy_source="grid", joules_est=0.1)
    c2.append(output=b"beta", energy_source="grid", joules_est=0.2)
    chain_ref = c2._chain
    chain_ref[0], chain_ref[1] = chain_ref[1], chain_ref[0]  # reorder breaks prev_hash links
    v2 = c2.verify()
    assert v2["ok"] is False and v2["links_intact"] is False, v2
    out["reorder_detected"] = True

    # (e) The Bekenstein gate flags an over-claim entry (shannon_bits > bytes*8).
    c3 = EnergyProvenanceChain()
    c3.append(output_bytes=4, shannon_bits=999.0, energy_source="grid", joules_est=0.0)
    v3 = c3.verify()
    assert v3["bekenstein_gate_all_pass"] is False and v3["ok"] is False, v3
    assert v3["gate_failures"] == [0]
    out["gate_flags_overclaim"] = True

    # (f) Honest labeling: every entry + summary carries SAMPLE/ESTIMATE; no free-energy.
    summ = c.summary()
    assert "SAMPLE/ESTIMATE" in summ["total_joules_est_label"]
    assert "SAMPLE/ESTIMATE" in es[0]["joules_est_label"]
    assert "free-energy" in summ["doctrine"].lower()
    out["summary_honest"] = True

    out["math_source"] = _SOURCE
    out["ok"] = True
    return out


if __name__ == "__main__":
    print(_selftest())
