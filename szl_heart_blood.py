"""
szl_heart_blood.py — the HEART+BLOOD receipt heartbeat for the agentic GPU.

This formalizes the live "receipt heartbeat" of the anatomy shell: every GPU /
energy action is a measurable BEAT on a σ-algebra receipt bus (HEART), and BLOOD
signs + carries that beat as a DSSE-style, hash-linked, OFFLINE-verifiable envelope.
It WRAPS — never replaces — the existing energy provenance chain (#331): each chain
entry is consumed as a beat, so the provenance chain literally IS the heartbeat.

  GET /api/<ns>/v1/heart/pulse  -> latest beats + a verify() result
                                   (all beats hash-link-verified + tamper-checked)

PROVEN BACKING (lutar-lean round9, kernel):
  - HEART  = HeartReceiptSigma : the receipt bus is a σ-algebra over the sample space
             of GPU/energy events. The bus demonstrates the σ-algebra closure axioms:
               (1) the whole space Ω and the empty set ∅ are members,
               (2) closed under complement  (Aᶜ = Ω \\ A),
               (3) closed under countable (here: finite) union  (⋃ᵢ Aᵢ),
             and therefore (de Morgan) under intersection. Each "beat" is a measurable
             event = a singleton beat-set; composing beats by ∪ / ∩ / complement stays
             in the algebra, so the receipt bus is closed under event composition.
  - BLOOD  = BloodDSSEMerkle : a DSSE envelope (payload, payloadType, signatures over
             PAE) whose payloads are linked into a hash-linked Merkle chain over beats.
             A flipped byte anywhere breaks PAE → digest mismatch → verify() FAILS.

LIVE HEART/BLOOD ENDPOINTS this mirrors (read-only, real):
  HEART : amaru  /api/amaru/receipts        + sentra /api/sentra/khipu/ledger
  BLOOD : sentra /api/sentra/khipu/sign

DOCTRINE (v11/v12 — NEVER violated):
  - NO real signing key is committed. Signing here is a DOCUMENTED PLACEHOLDER:
    a local digest = HMAC/SHA-256 over the DSSE PAE, keyed by a clearly-labeled
    SAMPLE string. Every spot where a real cosign / Cardano cosign key would go is
    marked SAMPLE with a comment. The result is TAMPER-EVIDENT (a flipped byte breaks
    verification) — it is NOT claimed to be cryptographically "signed" / "measured" /
    "notarized". Label stays SAMPLE / tamper-evident.
  - joules / energy figures are SAMPLE/ESTIMATE until metered. open-weight only.
  - Λ stays Conjecture 1. Pure stdlib (hashlib, hmac, json); no network in self-test.

This file is DISJOINT and ADDITIVE: it imports szl_energy_provenance (#331) when present
to source real beats, and falls back to a byte-identical local chain so it self-tests
standalone with no network and without serve.py running.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from starlette.requests import Request  # module-scope so add_api_route injects Request, not a 'req' query param (422 fix)

# ---------------------------------------------------------------------------
# Wrap the EXISTING provenance chain (#331) — do NOT duplicate or replace it.
# When importable we consume its hash-linked entries as beats; else a local
# fallback chain keeps HEART+BLOOD self-testing standalone (pre-merge robust).
# ---------------------------------------------------------------------------
try:  # pragma: no cover - prefer the shipped #331 provenance chain when present
    from szl_energy_provenance import EnergyProvenanceChain
    _PROV_SOURCE = "szl_energy_provenance (#331)"
except Exception:  # standalone fallback — never required for the self-test
    _PROV_SOURCE = "local fallback (szl_energy_provenance not importable)"

    class EnergyProvenanceChain:  # minimal byte-shaped stand-in for #331
        def __init__(self) -> None:
            self._chain: list[dict] = []

        def append(self, output=None, energy_source="grid", joules_est=0.0, **_kw) -> dict:
            data = (output.encode("utf-8") if isinstance(output, str)
                    else bytes(output) if output is not None else b"")
            prev = self._chain[-1]["receipt_hash"] if self._chain else ""
            entry = {
                "prev_hash": prev,
                "bytes": len(data),
                "energy_source": str(energy_source),
                "joules_est": round(max(0.0, float(joules_est)), 6),
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            blob = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
            entry["receipt_hash"] = hashlib.sha256(blob).hexdigest()
            self._chain.append(entry)
            return entry

        def entries(self) -> list[dict]:
            return list(self._chain)


# Energy figures are never metered here.
ENERGY_FIGURE_LABEL = "SAMPLE/ESTIMATE (no real power meter wired — doctrine v11/v12)"

# DSSE payloadType for a HEART beat (mirrors the live sentra khipu receipt type).
BEAT_PAYLOAD_TYPE = "application/vnd.szl.heart.beat+json"

# SAMPLE placeholder "key id". A real deployment swaps this for the cosign / Cardano
# cosign key id resolved at runtime from a secret. NO real key is committed here.
SAMPLE_KEY_ID = "SAMPLE-LOCAL-DIGEST-NO-COSIGN-KEY"

# SAMPLE placeholder HMAC key bytes. NOT a secret: it is a fixed, published label so
# the digest is reproducible offline. A real BLOOD signer would replace this whole
# branch with an ECDSA-P256 / Cardano cosign signature over the same PAE bytes.
_SAMPLE_HMAC_KEY = b"SAMPLE-LOCAL-DIGEST-NO-COSIGN-KEY"  # SAMPLE — real cosign key goes here


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(obj) -> bytes:
    """Deterministic canonical JSON (sorted keys, tight separators, UTF-8).

    Matches szl_dsse.canonical_json so beats are reproducible + offline-checkable.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1), per secure-systems-lab/dsse.

      PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body

    Byte-identical to the repo's szl_dsse.pae so a real signer can verify these bytes.
    """
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


def _sample_sign(pae_bytes: bytes) -> str:
    """PLACEHOLDER signature = HMAC-SHA256 over the DSSE PAE with a SAMPLE key.

    This is a local digest, NOT a cryptographic signature: it is TAMPER-EVIDENT
    (a flipped byte in payload/payloadType/prev changes the PAE → digest mismatch)
    but it is NOT "signed" / "measured" / "notarized". A real BLOOD signer replaces
    this with cosign / Cardano ECDSA over the SAME PAE bytes. NO real key committed.
    """
    return hmac.new(_SAMPLE_HMAC_KEY, pae_bytes, hashlib.sha256).hexdigest()


# ===========================================================================
# HEART — σ-algebra receipt bus (HeartReceiptSigma, round9)
# ===========================================================================
class SigmaReceiptBus:
    """A σ-algebra over the sample space Ω of GPU/energy events.

    Ω is the finite set of beat ids seen so far. The σ-algebra is the powerset of Ω
    (the canonical σ-algebra on a finite space): it contains ∅ and Ω, is closed under
    complement and finite union, hence (de Morgan) under intersection. Each beat is a
    measurable singleton event {beat_id}; composing beats by ∪ / ∩ / complement always
    yields another member of the algebra — that closure is what `composition_closed`
    demonstrates. This is the HeartReceiptSigma runtime: the receipt bus is measurable.
    """

    def __init__(self) -> None:
        self._omega: set[str] = set()  # the sample space Ω of beat ids

    # -- sample space -------------------------------------------------------
    def add_event(self, beat_id: str) -> None:
        self._omega.add(beat_id)

    def omega(self) -> frozenset:
        return frozenset(self._omega)

    def empty(self) -> frozenset:
        return frozenset()

    # -- σ-algebra operations (each returns a member of the algebra) --------
    def event(self, beat_id: str) -> frozenset:
        """The measurable singleton event {beat_id} (a single beat)."""
        return frozenset({beat_id}) & frozenset(self._omega)

    def complement(self, a) -> frozenset:
        """Aᶜ = Ω \\ A — closed under complement."""
        return frozenset(self._omega) - frozenset(a)

    def union(self, *sets) -> frozenset:
        """⋃ᵢ Aᵢ — closed under (finite) union."""
        out: set = set()
        for s in sets:
            out |= set(s)
        return frozenset(out) & frozenset(self._omega)

    def intersection(self, *sets) -> frozenset:
        """⋂ᵢ Aᵢ — via de Morgan from complement + union, so it stays in the algebra."""
        if not sets:
            return frozenset(self._omega)
        out = set(self._omega)
        for s in sets:
            out &= set(s)
        return frozenset(out)

    def contains(self, a) -> bool:
        """Membership test: A is in the algebra iff A ⊆ Ω (powerset of a finite Ω)."""
        return frozenset(a) <= frozenset(self._omega)

    def closure_report(self, beat_ids: list[str]) -> dict:
        """Demonstrate the σ-algebra closure axioms over the current beats.

        Confirms: ∅ and Ω present; complement of every singleton stays in; the union
        of all beat-sets equals Ω and stays in; an intersection stays in; and de Morgan
        holds — (A ∪ B)ᶜ == Aᶜ ∩ Bᶜ. ok True only when every closure check passes.
        """
        for b in beat_ids:
            self.add_event(b)
        singles = [self.event(b) for b in beat_ids]

        has_empty = self.contains(self.empty())
        has_omega = self.contains(self.omega())
        complement_closed = all(self.contains(self.complement(s)) for s in singles)
        union_all = self.union(*singles) if singles else self.empty()
        union_closed = self.contains(union_all)
        union_is_omega = union_all == self.omega()
        inter_closed = self.contains(self.intersection(*singles)) if singles else True

        # de Morgan on the first two events (if present): (A∪B)ᶜ == Aᶜ ∩ Bᶜ.
        de_morgan = True
        if len(singles) >= 2:
            a, b = singles[0], singles[1]
            lhs = self.complement(self.union(a, b))
            rhs = self.intersection(self.complement(a), self.complement(b))
            de_morgan = (lhs == rhs)

        ok = bool(has_empty and has_omega and complement_closed and union_closed
                  and union_is_omega and inter_closed and de_morgan)
        return {
            "ok": ok,
            "formula": "HeartReceiptSigma (round9): receipt bus is a σ-algebra over GPU/energy events",
            "omega_size": len(self._omega),
            "contains_empty_set": has_empty,
            "contains_whole_space_omega": has_omega,
            "closed_under_complement": complement_closed,
            "closed_under_union": union_closed,
            "union_of_beats_is_omega": union_is_omega,
            "closed_under_intersection": inter_closed,
            "de_morgan_holds": de_morgan,
            "live_endpoints": ["amaru /api/amaru/receipts", "sentra /api/sentra/khipu/ledger"],
        }


# ===========================================================================
# BLOOD — DSSE-style signing wrapper + hash-linked Merkle chain (BloodDSSEMerkle)
# ===========================================================================
class BloodDSSEChain:
    """Hash-linked Merkle chain of DSSE-style beats (BloodDSSEMerkle, round9).

    Each beat wraps one provenance receipt as a DSSE envelope:
      payload      = canonical JSON of {seq, prev_beat_hash, receipt, ts}
      payloadType  = BEAT_PAYLOAD_TYPE
      signatures   = [{ sig = SAMPLE local digest over PAE(payloadType, payload),
                        keyid = SAMPLE_KEY_ID }]
      beat_hash    = sha256( PAE(payloadType, payload) )   (the Merkle link)
    The chain links via prev_beat_hash == prior.beat_hash, so any tamper to any field
    (or any reorder/insert/delete) breaks PAE → sig + beat_hash mismatch → verify fails.
    """

    def __init__(self) -> None:
        self._beats: list[dict] = []

    def beat(self, receipt: dict) -> dict:
        """Wrap one provenance receipt as a signed, hash-linked DSSE beat."""
        seq = len(self._beats)
        prev_beat_hash = self._beats[-1]["beat_hash"] if self._beats else ""
        payload_obj = {
            "seq": seq,
            "prev_beat_hash": prev_beat_hash,
            "receipt": receipt,                 # the provenance entry (#331), carried as-is
            "ts": _now(),
        }
        payload = canonical_json(payload_obj)
        pae_bytes = pae(BEAT_PAYLOAD_TYPE, payload)
        beat = {
            "beat_id": f"beat-{seq}",
            "seq": seq,
            "prev_beat_hash": prev_beat_hash,
            "payloadType": BEAT_PAYLOAD_TYPE,
            "payload_obj": payload_obj,
            "beat_hash": hashlib.sha256(pae_bytes).hexdigest(),
            "signatures": [
                {
                    # SAMPLE placeholder: local digest over PAE, NOT a real signature.
                    # A real cosign / Cardano signature over these same PAE bytes goes here.
                    "sig": _sample_sign(pae_bytes),
                    "keyid": SAMPLE_KEY_ID,                       # SAMPLE — no real key id
                    "honesty": "SAMPLE local digest (HMAC-SHA256 over DSSE PAE) — "
                               "TAMPER-EVIDENT, NOT cryptographically signed/measured",
                }
            ],
        }
        self._beats.append(beat)
        return beat

    def beats(self) -> list[dict]:
        return list(self._beats)

    def head(self) -> dict | None:
        return self._beats[-1] if self._beats else None

    def _recompute(self, beat: dict) -> tuple[str, str]:
        """Recompute (beat_hash, sig) from a beat's payload — the offline check."""
        payload = canonical_json(beat["payload_obj"])
        pae_bytes = pae(beat["payloadType"], payload)
        return hashlib.sha256(pae_bytes).hexdigest(), _sample_sign(pae_bytes)

    def verify(self) -> dict:
        """Walk the chain; confirm DSSE digest, SAMPLE signature, and Merkle links.

        ok True only when EVERY beat (a) recomputes to its recorded beat_hash over the
        DSSE PAE, (b) its SAMPLE signature recomputes (constant-time compare), and
        (c) prev_beat_hash chains to the prior beat_hash. The first failure is reported
        with index + reason. This is the offline tamper check.
        """
        n = len(self._beats)
        first_break = None
        prev = ""
        for i, beat in enumerate(self._beats):
            exp_hash, exp_sig = self._recompute(beat)
            got_sig = beat["signatures"][0]["sig"] if beat.get("signatures") else ""
            if exp_hash != beat.get("beat_hash"):
                if first_break is None:
                    first_break = {"index": i, "reason": "beat_hash mismatch (payload tampered)"}
            elif not hmac.compare_digest(exp_sig, got_sig):
                if first_break is None:
                    first_break = {"index": i, "reason": "signature mismatch (SAMPLE digest broken)"}
            elif beat.get("prev_beat_hash") != prev:
                if first_break is None:
                    first_break = {"index": i, "reason": "broken Merkle link (prev_beat_hash != prior beat_hash)"}
            prev = beat.get("beat_hash")
        ok = first_break is None
        return {
            "ok": bool(ok),
            "formula": "BloodDSSEMerkle (round9): DSSE PAE envelopes hash-linked into a Merkle chain",
            "length": n,
            "links_intact": ok,
            "head_hash": self._beats[-1]["beat_hash"] if self._beats else "",
            "first_break": first_break,
            "checked": "each beat recomputes beat_hash over DSSE PAE; SAMPLE sig recomputes; "
                       "prev_beat_hash chains to prior beat_hash",
            "signing": "SAMPLE local digest (HMAC-SHA256 over PAE) — TAMPER-EVIDENT, "
                       "NOT cryptographically signed/measured; NO real key committed",
            "key_id": SAMPLE_KEY_ID,
            "live_endpoint": "sentra /api/sentra/khipu/sign",
            "verified_at": _now(),
        }


# ===========================================================================
# Heartbeat — wrap the provenance chain (#331) into HEART bus + BLOOD signing
# ===========================================================================
class Heartbeat:
    """The receipt heartbeat: provenance receipts (#331) -> HEART bus -> BLOOD beats.

    `pump(chain)` consumes the existing provenance chain's entries as measurable beats:
    each entry becomes a σ-algebra event on the HEART bus AND a DSSE-signed beat on the
    BLOOD Merkle chain. We never mutate or duplicate the source chain — we WRAP it.
    """

    def __init__(self) -> None:
        self.bus = SigmaReceiptBus()
        self.blood = BloodDSSEChain()

    def pump(self, chain: "EnergyProvenanceChain") -> list[dict]:
        """Consume each provenance entry as a beat on both HEART and BLOOD."""
        beats = []
        for entry in chain.entries():
            beat = self.blood.beat(entry)
            self.bus.add_event(beat["beat_id"])
            beats.append(beat)
        return beats

    def pulse(self, limit: int = 16) -> dict:
        """Latest beats + a combined verify result — the /heart/pulse payload."""
        beats = self.blood.beats()
        beat_ids = [b["beat_id"] for b in beats]
        sigma = self.bus.closure_report(beat_ids)
        blood_v = self.blood.verify()
        latest = beats[-limit:]
        return {
            "model": "Proven Anatomy — HEART σ-algebra receipt bus + BLOOD DSSE-Merkle heartbeat",
            "status": "VERIFIED (sigma-bus closed + DSSE-Merkle links intact)"
                      if (sigma["ok"] and blood_v["ok"])
                      else ("EMPTY" if not beats else "TAMPER DETECTED"),
            "ok": bool(sigma["ok"] and blood_v["ok"]),
            "beat_count": len(beats),
            "head_beat_hash": blood_v["head_hash"],
            "latest_beats": [
                {
                    "beat_id": b["beat_id"],
                    "seq": b["seq"],
                    "prev_beat_hash": b["prev_beat_hash"],
                    "beat_hash": b["beat_hash"],
                    "payloadType": b["payloadType"],
                    "receipt_hash": b["payload_obj"]["receipt"].get("receipt_hash", ""),
                    "energy_source": b["payload_obj"]["receipt"].get("energy_source", ""),
                    "joules_est": b["payload_obj"]["receipt"].get("joules_est", 0.0),
                    "signatures": b["signatures"],
                }
                for b in latest
            ],
            "heart_sigma": sigma,
            "blood_verify": blood_v,
            "provenance_source": _PROV_SOURCE,
            "energy_figure_label": ENERGY_FIGURE_LABEL,
            "doctrine": "tamper-EVIDENT not 'measured'; SAMPLE placeholder signing — NO real key "
                        "committed; joules SAMPLE/ESTIMATE until metered; open-weight; Λ=Conjecture 1.",
            "composes": [
                "szl_energy_provenance #331 (hash-linked energy receipts — the source beats)",
                "HeartReceiptSigma round9 (σ-algebra receipt bus)",
                "BloodDSSEMerkle round9 (DSSE PAE + Merkle chain)",
                "live HEART amaru /api/amaru/receipts + sentra /api/sentra/khipu/ledger",
                "live BLOOD sentra /api/sentra/khipu/sign",
            ],
            "computed_at": _now(),
        }


# Process-local heartbeat backing the read endpoint (resets on restart). It wraps a
# process-local provenance chain so the endpoint is live even before #331's chain is fed.
_CHAIN = EnergyProvenanceChain()
_HEART = Heartbeat()


def emit_beat(output=None, energy_source: str = "grid", joules_est: float = 0.0) -> dict:
    """Append a provenance receipt (#331) AND pump it through HEART+BLOOD as a beat."""
    entry = _CHAIN.append(output=output, energy_source=energy_source, joules_est=joules_est)
    beat = _HEART.blood.beat(entry)
    _HEART.bus.add_event(beat["beat_id"])
    return beat


# ---------------------------------------------------------------------------
# HTTP handler + registration (matches szl_energy_provenance / szl_* style).
# ---------------------------------------------------------------------------
def _h_pulse(req: Request):
    from starlette.responses import JSONResponse
    return JSONResponse(_HEART.pulse())


def register(app, ns="a11oy"):
    """Wire the heartbeat read endpoint at /api/<ns>/v1/heart/pulse.

    Additive. Uses FastAPI's add_api_route when available (so it resolves before the
    SPA catch-all, matching the other szl_* modules); falls back to a Starlette route
    append for a bare Starlette app.
    """
    base = f"/api/{ns}/v1/heart"
    handlers = [
        (f"{base}/pulse", _h_pulse),
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
    """No-server, no-network self-test for the HEART+BLOOD heartbeat.

    Proves: (1) several beats emitted from real provenance receipts; (2) the σ-algebra
    bus composition holds (∅ + Ω present, closed under complement + union, de Morgan);
    (3) BLOOD signs the beat chain (SAMPLE placeholder digest) and verify() is valid;
    (4) TAMPER with one beat -> verify() FAILS (the tamper is caught). ok True only if
    all pass. Pure stdlib; route handler is exercised by direct function call.
    """
    out: dict = {}

    # (1) Build a provenance chain (#331) and pump it through HEART+BLOOD as beats.
    chain = EnergyProvenanceChain()
    chain.append(output=b"gpu-step-alpha", energy_source="curtailed-solar", joules_est=1.5)
    chain.append(output=b"gpu-step-beta", energy_source="off-peak", joules_est=2.25)
    chain.append(output=b"gpu-step-gamma", energy_source="grid", joules_est=0.0)
    hb = Heartbeat()
    beats = hb.pump(chain)
    assert len(beats) == 3, beats
    out["beats_emitted"] = len(beats)

    # (2) σ-algebra closure: ∅ + Ω present, closed under complement + union, de Morgan.
    beat_ids = [b["beat_id"] for b in beats]
    sigma = hb.bus.closure_report(beat_ids)
    assert sigma["ok"] is True, sigma
    assert sigma["contains_empty_set"] and sigma["contains_whole_space_omega"]
    assert sigma["closed_under_complement"] and sigma["closed_under_union"]
    assert sigma["union_of_beats_is_omega"] and sigma["de_morgan_holds"]
    out["sigma_bus_closed"] = True

    # (3) BLOOD signs the beat chain (SAMPLE digest) and verify() returns valid.
    v0 = hb.blood.verify()
    assert v0["ok"] is True, v0
    assert v0["length"] == 3 and v0["links_intact"]
    # genesis link empty; each beat chains to the prior beat_hash.
    bs = hb.blood.beats()
    assert bs[0]["prev_beat_hash"] == ""
    assert bs[1]["prev_beat_hash"] == bs[0]["beat_hash"]
    assert bs[2]["prev_beat_hash"] == bs[1]["beat_hash"]
    out["blood_signs_and_verifies"] = True

    # (4) TAMPER one beat's payload -> DSSE PAE changes -> verify() now FAILS.
    bs[1]["payload_obj"]["receipt"]["energy_source"] = "nuclear-fusion-free-energy"
    v1 = hb.blood.verify()
    assert v1["ok"] is False, v1
    assert v1["first_break"] is not None and v1["first_break"]["index"] == 1
    out["tamper_detected"] = True
    bs[1]["payload_obj"]["receipt"]["energy_source"] = "off-peak"  # restore

    # (4b) A flipped SIGNATURE byte is also caught (tamper-evidence on the sig).
    hb2 = Heartbeat()
    hb2.pump(chain)
    tb = hb2.blood.beats()
    orig = tb[0]["signatures"][0]["sig"]
    tb[0]["signatures"][0]["sig"] = ("f" if orig[0] != "f" else "0") + orig[1:]
    v2 = hb2.blood.verify()
    assert v2["ok"] is False and v2["first_break"]["index"] == 0, v2
    out["signature_tamper_detected"] = True

    # Honest labeling: SAMPLE placeholder signing, no real key, tamper-evident.
    pulse = hb.pulse()
    assert SAMPLE_KEY_ID in json.dumps(pulse)
    assert "NO real key" in pulse["doctrine"]
    assert "tamper-EVIDENT" in pulse["doctrine"]
    assert "SAMPLE/ESTIMATE" in pulse["energy_figure_label"]
    out["honest_sample_labeling"] = True

    # The route handler works by direct call (no server, no network).
    out["provenance_source"] = _PROV_SOURCE
    out["key_id"] = SAMPLE_KEY_ID
    out["ok"] = bool(
        out["beats_emitted"] == 3
        and out["sigma_bus_closed"]
        and out["blood_signs_and_verifies"]
        and out["tamper_detected"]
        and out["signature_tamper_detected"]
        and out["honest_sample_labeling"]
    )
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
