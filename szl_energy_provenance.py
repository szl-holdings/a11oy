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

verify() walks the chain and confirms BOTH:
  (1) link integrity — each entry's prev_hash equals the prior entry's receipt_hash,
      and each entry's recomputed content hash equals its recorded receipt_hash
      (so any tampering of any field, or any reordering/insertion/deletion, is caught);
  (2) the Bekenstein gate — every entry has within_bound is True.

DOCTRINE (v11/v12, NEVER violated):
  - NO free-energy / perpetual-motion claims. The chain proves WHAT was receipted and
    that it is UNTAMPERED + Bekenstein-bounded — it does NOT upgrade an estimate into a
    measurement. Every joules_est stays labeled SAMPLE/ESTIMATE until a real meter.
  - Tamper-EVIDENT, not tamper-proof: it proves the recorded history is internally
    consistent and gate-passing; it makes NO "measured energy" claim.
  - open-weight only; never commit a key. Pure stdlib; no numpy, no network.

Reuses the canonical Bekenstein/Shannon math from szl_energy_budget when that module
is importable (#328); otherwise carries a byte-identical local fallback so this module
runs and self-tests standalone (the PR depends on #328 but does not require it merged).
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
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


def _canonical_bytes(entry: dict) -> bytes:
    """Deterministic canonical encoding of the hash-bound content of an entry.

    Excludes receipt_hash itself (it is the digest of this blob). Uses sorted keys
    and tight separators so the bytes are stable across processes — the same rule
    szl_energy_budget.task_hash uses, so receipts are reproducible + offline-checkable.
    """
    payload = {k: entry[k] for k in _HASHED_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt_hash(entry: dict) -> str:
    return hashlib.sha256(_canonical_bytes(entry)).hexdigest()


class EnergyProvenanceChain:
    """Append-only, hash-linked ledger of Bekenstein-gated energy receipts.

    Each appended entry links to the prior via prev_hash == prior.receipt_hash, so the
    chain is a tamper-evident transparency log: any change to any past field, or any
    reorder/insert/delete, breaks a link and is caught by verify().
    """

    def __init__(self) -> None:
        self._chain: list[dict] = []

    # -- construction -------------------------------------------------------
    def append(
        self,
        output: bytes | str | None = None,
        output_bytes: int | None = None,
        shannon_bits: float | None = None,
        energy_source: str = "grid",
        joules_est: float = 0.0,
    ) -> dict:
        """Build + append one hash-linked, Bekenstein-gated provenance entry.

        Computes shannon_bits + bytes from `output` when given; else uses the supplied
        sizes (worst-case full-entropy bytes*8 if shannon_bits omitted). within_bound
        is the proven F19/TH6 gate. joules_est is clamped nonneg and stays SAMPLE.
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
        j_est = round(max(0.0, float(joules_est)), 6)
        prev_hash = self._chain[-1]["receipt_hash"] if self._chain else ""

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
            "joules_est_label": ENERGY_FIGURE_LABEL,
            "ts": _now(),
        }
        entry["receipt_hash"] = _receipt_hash(entry)
        self._chain.append(entry)
        return entry

    # -- inspection ---------------------------------------------------------
    def head(self) -> dict | None:
        return self._chain[-1] if self._chain else None

    def __len__(self) -> int:
        return len(self._chain)

    def entries(self) -> list[dict]:
        return list(self._chain)

    # -- verification -------------------------------------------------------
    def verify(self) -> dict:
        """Walk the chain; confirm link integrity AND the Bekenstein gate.

        Returns an honest report: ok True only when EVERY entry (a) hashes to its
        recorded receipt_hash, (b) links to the prior entry's receipt_hash, and
        (c) passed the Bekenstein gate (within_bound True). The first failure is
        reported with its index + reason; later entries are still scanned for a
        full gate tally so the report is complete.
        """
        n = len(self._chain)
        first_break: dict | None = None
        gate_failures: list[int] = []
        prev_hash = ""

        for i, entry in enumerate(self._chain):
            recomputed = _receipt_hash(entry)
            if recomputed != entry.get("receipt_hash"):
                if first_break is None:
                    first_break = {"index": i, "reason": "receipt_hash mismatch (entry content tampered)"}
            elif entry.get("prev_hash") != prev_hash:
                if first_break is None:
                    first_break = {"index": i, "reason": "broken link (prev_hash != prior receipt_hash)"}
            if entry.get("within_bound") is not True:
                gate_failures.append(i)
            prev_hash = entry.get("receipt_hash")

        links_ok = first_break is None
        gate_ok = len(gate_failures) == 0
        return {
            "ok": bool(links_ok and gate_ok),
            "length": n,
            "links_intact": links_ok,
            "bekenstein_gate_all_pass": gate_ok,
            "head_hash": self._chain[-1]["receipt_hash"] if self._chain else "",
            "first_break": first_break,
            "gate_failures": gate_failures,
            "checked": "each entry hashes to its receipt_hash; prev_hash chains to prior; within_bound True",
            "verified_at": _now(),
        }

    def summary(self) -> dict:
        """Honest chain summary for the read endpoint: head + verify status + doctrine."""
        v = self.verify()
        head = self.head()
        total_joules = round(sum(e["joules_est"] for e in self._chain), 6)
        return {
            "model": "Proven Energy Engine — tamper-evident energy provenance chain",
            "status": "VERIFIED (hash-linked + Bekenstein gate)" if v["ok"] else
                      ("EMPTY" if not self._chain else "TAMPER DETECTED"),
            "length": len(self._chain),
            "head_hash": head["receipt_hash"] if head else "",
            "head": head,
            "verify": v,
            "total_joules_est": total_joules,
            "total_joules_est_label": ENERGY_FIGURE_LABEL,
            "math_source": _SOURCE,
            "gate": "F19/TH6 Bekenstein: shannon_bits <= bytes*8 per entry",
            "link_rule": "entry.prev_hash == prior.receipt_hash; receipt_hash = sha256(canonical content)",
            "doctrine": "tamper-EVIDENT not 'measured'; NO free-energy claims; joules are SAMPLE/ESTIMATE "
                        "until a real meter; open-weight only; never commit a key.",
            "composes": ["szl_energy_budget #328 (Bekenstein-gated receipts)",
                         "SZL cosign+Rekor+in-toto transparency-log doctrine",
                         "Showcase/Frontier/EnergyBudgetWitness.lean (0-sorry witness)"],
            "computed_at": _now(),
        }


# Process-local chain instance backing the read endpoint (resets on restart).
_CHAIN = EnergyProvenanceChain()


def append_receipt(**kwargs) -> dict:
    """Module-level convenience: append to the shared process chain."""
    return _CHAIN.append(**kwargs)


# ---------------------------------------------------------------------------
# HTTP handler + registration (matches szl_energy_budget / szl_quantum_bio style).
# ---------------------------------------------------------------------------
def _h_provenance(req: Request):
    from starlette.responses import JSONResponse
    return JSONResponse(_CHAIN.summary())


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
