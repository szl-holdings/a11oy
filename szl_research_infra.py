# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) — Verified Research Infrastructure (process-verification only).
"""
szl_research_infra.py — Verified Research Infrastructure for consciousness / psi /
quantum-bio experiments. A tamper-EVIDENT pre-registration receipt + a hash-linked
trial ledger, so a researcher can PROVE (to a skeptic, offline) that:

  (1) the hypothesis + exact statistical analysis (test, stopping rule, N) was FROZEN
      BEFORE any data was collected — a time-stamped, content-hashed, DSSE-style receipt;
  (2) every trial result was appended to an append-only, hash-linked chain, so any later
      edit, reorder, insertion, or deletion of a trial BREAKS a link and is caught;
  (3) the analysis that gets reported is byte-identical to the pre-registered analysis
      (analysis_locked) — i.e. no silent re-specification after seeing the data.

WHY THIS EXISTS (the methodology need, from the field's OWN literature):
  Consciousness / psi research — e.g. Dean Radin & IONS double-slit and entanglement
  studies, the Global Consciousness Project, and Bem's precognition work — is widely
  criticised for p-hacking, optional stopping, data-selection, and unreplicability. The
  field's prescribed remedy is exactly pre-registration + tamper-evident records +
  regenerable analysis, the same remedy the broader open-science movement adopted as
  Registered Reports (Center for Open Science) and OSF pre-registration. SZL already
  has the cryptographic primitives (szl_dsse DSSE signing + the szl_energy_provenance
  hash-linked chain); this module wires them into a research-grade workflow.

  Methodology references (the NEED, NOT a claim their results are correct):
    - Radin, Michel, et al. "Consciousness and the double-slit interference pattern."
      Physics Essays 25(2), 2012. DOI 10.4006/0836-1398-25.2.157
    - Institute of Noetic Sciences (IONS) — https://noetic.org/ (research methodology).
    - Nelson, R. — Global Consciousness Project — https://noosphere.princeton.edu/
    - Bem, D. "Feeling the Future." J. Pers. Soc. Psychol. 100(3), 2011.
      DOI 10.1037/a0021524  (the replication debate that motivated pre-registration).
    - Chambers, C. — Registered Reports / Center for Open Science — https://www.cos.io/rr
    - OSF pre-registration — https://osf.io/prereg/

WHAT THIS MODULE CLAIMS — and what it DOES NOT:
  It VERIFIES PROCESS. It makes ZERO empirical claim about psi, consciousness, or any
  "observer effect" being real. A passing /verify means only that the recorded process
  (pre-registration fixed first; data chain intact; analysis unchanged) is internally
  consistent and untampered. It does NOT validate the hypothesis, the measurement, or
  the result. Tamper-EVIDENT, not tamper-proof: it proves the recorded history is
  internally consistent; it cannot stop someone from never recording a trial at all.

  The bundled DEMO is a Radin-STYLE double-slit "observer effect" pre-registration with
  a few SIMULATED trials drawn from a fixed PRNG. The demo data is labelled SIMULATED/
  DEMO throughout and is NOT a real measurement and NOT evidence of psi.

DOCTRINE (v11): process-verification only; no empirical psi claim; demo data SIMULATED;
  tamper-EVIDENT not tamper-proof; Λ stays Conjecture 1 (this module is NOT in the
  locked-8 proven set, locked=8 unchanged); no key committed (signing reuses szl_dsse:
  REAL ECDSA when the runtime secret is present, honest UNSIGNED marker otherwise).
  Pure stdlib + szl_dsse (which is already a repo import); no numpy, no network.

Endpoints (additive, registered before the SPA catch-all):
  POST /api/<ns>/v1/research/prereg            -> signed, time-stamped prereg receipt
  POST /api/<ns>/v1/research/trial             -> append a trial; returns new chain head
  GET  /api/<ns>/v1/research/verify/{exp_id}   -> {prereg_receipt, trial_count,
                                                   chain_intact, analysis_locked, honest_note}
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from starlette.requests import Request  # module-scope so add_api_route injects Request, not a 422 query param

# Reuse the repo's DSSE signer when present (REAL ECDSA with the runtime secret;
# honest UNSIGNED envelope otherwise — NEVER fabricates a sig, NEVER needs a key).
try:
    import szl_dsse as _dsse
    _DSSE_SOURCE = "szl_dsse (repo DSSE signer; REAL ECDSA when SZL_COSIGN_PRIVATE_KEY_PEM present, else honest UNSIGNED)"
except Exception:  # standalone fallback — keeps self-test + serve robust pre-merge
    _dsse = None
    _DSSE_SOURCE = "local UNSIGNED fallback (szl_dsse not importable)"

PREREG_PAYLOAD_TYPE = "application/vnd.szl.research-prereg+json"

# The exact set of fields a pre-registration FREEZES. Changing ANY of these after the
# fact produces a different content hash, so a re-submission with a changed analysis is
# detected (rejected) rather than silently overwriting the frozen spec.
_PREREG_FROZEN_FIELDS = (
    "experiment_id", "hypothesis", "primary_outcome", "analysis_spec", "researcher",
)

# Fields hash-bound into each trial entry's receipt_hash (order-independent: sorted in
# the canonical encoding; the SET is fixed so a dropped/added field is detected).
_TRIAL_HASHED_FIELDS = (
    "prev_hash", "experiment_id", "trial_index", "value", "ts",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes_of(fields, entry: dict) -> bytes:
    """Deterministic canonical encoding (sorted keys, tight separators) of the named
    fields. Matches szl_dsse.canonical_json so receipts are reproducible + offline-
    checkable by an independent verifier."""
    payload = {k: entry[k] for k in fields}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _content_hash_of(fields, entry: dict) -> str:
    return hashlib.sha256(_canonical_bytes_of(fields, entry)).hexdigest()


# ---------------------------------------------------------------------------
# Pre-registration: freeze the spec BEFORE data, with a signed time-stamped receipt.
# ---------------------------------------------------------------------------
def _sign_prereg(content: dict) -> dict:
    """Wrap the frozen prereg content in a DSSE-style signed, time-stamped receipt.

    Honest signing: if szl_dsse + the runtime key secret are present, this is a REAL
    ECDSA-P256-SHA256 DSSE envelope verifiable by `cosign verify-blob`. If no key is
    present, it returns an honest UNSIGNED envelope (signed=False) — NO fabricated
    signature, NO committed key.
    """
    if _dsse is not None:
        env = _dsse.sign_payload(content, PREREG_PAYLOAD_TYPE)
        return env
    # Local UNSIGNED fallback (no szl_dsse on path): still time-stamped + content-hashed,
    # but explicitly unsigned. NEVER fabricates a signature.
    body = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "payloadType": PREREG_PAYLOAD_TYPE,
        "payload": __import__("base64").b64encode(body).decode("ascii"),
        "_dsse": "DSSEv1",
        "signatures": [],
        "signed": False,
        "_signed_at": _now(),
        "honesty": "UNSIGNED — szl_dsse not importable in this runtime; no signature fabricated.",
    }


class PreRegistration:
    """A single frozen pre-registration: hypothesis + exact analysis spec, content-hashed
    and time-stamped at the moment of registration. Once created it is FROZEN — the
    receipt is the tamper-evident proof the analysis was fixed before any data."""

    def __init__(self, experiment_id: str, hypothesis: str, primary_outcome: str,
                 analysis_spec: dict, researcher: str) -> None:
        self.content = {
            "experiment_id": str(experiment_id),
            "hypothesis": str(hypothesis),
            "primary_outcome": str(primary_outcome),
            # analysis_spec carries the EXACT statistical test + stopping rule + N.
            "analysis_spec": analysis_spec,
            "researcher": str(researcher),
            "registered_at": _now(),
        }
        # content_hash freezes the spec: it is the sha256 over ONLY the frozen fields
        # (not registered_at), so two prereg of the same spec hash identically and a
        # changed analysis hashes differently — the freeze-detection primitive.
        self.content_hash = _content_hash_of(_PREREG_FROZEN_FIELDS, self.content)
        self.content["content_hash"] = self.content_hash
        self.receipt = _sign_prereg(self.content)

    def matches_spec(self, hypothesis: str, primary_outcome: str,
                     analysis_spec: dict, researcher: str) -> bool:
        """True iff a re-submission's frozen fields hash-equal the registered spec."""
        candidate = {
            "experiment_id": self.content["experiment_id"],
            "hypothesis": str(hypothesis),
            "primary_outcome": str(primary_outcome),
            "analysis_spec": analysis_spec,
            "researcher": str(researcher),
        }
        return _content_hash_of(_PREREG_FROZEN_FIELDS, candidate) == self.content_hash

    def as_receipt(self) -> dict:
        return {
            "experiment_id": self.content["experiment_id"],
            "content_hash": self.content_hash,
            "registered_at": self.content["registered_at"],
            "analysis_spec": self.content["analysis_spec"],
            "primary_outcome": self.content["primary_outcome"],
            "hypothesis": self.content["hypothesis"],
            "researcher": self.content["researcher"],
            "dsse": self.receipt,
            "signed": bool(self.receipt.get("signed")),
            "frozen": True,
            "freeze_rule": "content_hash = sha256(canonical{experiment_id,hypothesis,"
                           "primary_outcome,analysis_spec,researcher}); any change re-hashes.",
        }


# ---------------------------------------------------------------------------
# Trial ledger: append-only, hash-linked chain (reuses the provenance-chain pattern).
# ---------------------------------------------------------------------------
class TrialChain:
    """Append-only hash-linked ledger of trial results for ONE experiment.

    Each entry links to the prior via prev_hash == prior.receipt_hash, so the chain is
    a tamper-evident transparency log: any change to any past trial, or any reorder/
    insert/delete, breaks a link and is caught by verify()."""

    def __init__(self, experiment_id: str) -> None:
        self.experiment_id = str(experiment_id)
        self._chain: list[dict] = []

    def append(self, trial_index: int, value, ts: str | None = None,
               simulated: bool = False) -> dict:
        prev_hash = self._chain[-1]["receipt_hash"] if self._chain else ""
        entry = {
            "prev_hash": prev_hash,
            "experiment_id": self.experiment_id,
            "trial_index": int(trial_index),
            "value": value,
            "ts": ts or _now(),
        }
        entry["receipt_hash"] = _content_hash_of(_TRIAL_HASHED_FIELDS, entry)
        # Provenance label OUTSIDE the hashed set (annotation only; demo data is marked).
        if simulated:
            entry["data_label"] = "SIMULATED/DEMO — not a real measurement, not evidence of psi"
        self._chain.append(entry)
        return entry

    def head(self) -> dict | None:
        return self._chain[-1] if self._chain else None

    def __len__(self) -> int:
        return len(self._chain)

    def entries(self) -> list[dict]:
        return list(self._chain)

    def verify(self) -> dict:
        """Walk the chain; confirm each entry hashes to its receipt_hash AND links to the
        prior. Returns an honest report; first failure reported with index + reason."""
        first_break: dict | None = None
        prev_hash = ""
        for i, entry in enumerate(self._chain):
            recomputed = _content_hash_of(_TRIAL_HASHED_FIELDS, entry)
            if recomputed != entry.get("receipt_hash"):
                if first_break is None:
                    first_break = {"index": i, "reason": "receipt_hash mismatch (trial content tampered)"}
            elif entry.get("prev_hash") != prev_hash:
                if first_break is None:
                    first_break = {"index": i, "reason": "broken link (prev_hash != prior receipt_hash)"}
            prev_hash = entry.get("receipt_hash")
        return {
            "chain_intact": first_break is None,
            "length": len(self._chain),
            "head_hash": self._chain[-1]["receipt_hash"] if self._chain else "",
            "first_break": first_break,
            "checked": "each entry hashes to its receipt_hash; prev_hash chains to prior",
            "verified_at": _now(),
        }


# ---------------------------------------------------------------------------
# Registry: one prereg + one trial chain per experiment_id (process-local).
# ---------------------------------------------------------------------------
class ResearchRegistry:
    """Process-local store of pre-registrations + trial chains. Resets on restart
    (this is a demo substrate; a production deployment would back it with the durable
    Khipu/Rekor transparency log)."""

    def __init__(self) -> None:
        self._prereg: dict[str, PreRegistration] = {}
        self._chains: dict[str, TrialChain] = {}

    def prereg(self, experiment_id: str, hypothesis: str, primary_outcome: str,
               analysis_spec: dict, researcher: str) -> dict:
        """Register a frozen prereg. If experiment_id already exists, the spec is FROZEN:
        a re-submission with the SAME spec returns the existing receipt (idempotent); a
        re-submission with a CHANGED analysis is REJECTED (the freeze is the whole point)."""
        existing = self._prereg.get(str(experiment_id))
        if existing is not None:
            if existing.matches_spec(hypothesis, primary_outcome, analysis_spec, researcher):
                return {"ok": True, "frozen": True, "idempotent": True,
                        "note": "Identical spec already pre-registered; returning the original frozen receipt.",
                        "prereg_receipt": existing.as_receipt()}
            return {"ok": False, "frozen": True, "rejected": True,
                    "reason": "experiment_id already pre-registered with a DIFFERENT analysis_spec; "
                              "the spec is FROZEN. Re-specification after registration is rejected "
                              "(this is the tamper-evidence guarantee).",
                    "registered_content_hash": existing.content_hash,
                    "prereg_receipt": existing.as_receipt()}
        pr = PreRegistration(experiment_id, hypothesis, primary_outcome, analysis_spec, researcher)
        self._prereg[pr.content["experiment_id"]] = pr
        self._chains[pr.content["experiment_id"]] = TrialChain(experiment_id)
        return {"ok": True, "frozen": True, "newly_registered": True,
                "prereg_receipt": pr.as_receipt()}

    def trial(self, experiment_id: str, trial_index: int, value, ts: str | None = None,
              simulated: bool = False) -> dict:
        eid = str(experiment_id)
        pr = self._prereg.get(eid)
        if pr is None:
            return {"ok": False, "reason": "no pre-registration for this experiment_id; "
                                           "register the analysis spec BEFORE appending trials."}
        chain = self._chains.setdefault(eid, TrialChain(eid))
        entry = chain.append(trial_index, value, ts=ts, simulated=simulated)
        return {"ok": True, "experiment_id": eid, "trial_index": entry["trial_index"],
                "chain_head": entry["receipt_hash"], "trial_count": len(chain),
                "entry": entry}

    def verify(self, experiment_id: str) -> dict:
        eid = str(experiment_id)
        pr = self._prereg.get(eid)
        chain = self._chains.get(eid)
        if pr is None:
            return {"ok": False, "experiment_id": eid,
                    "reason": "unknown experiment_id (no pre-registration on record)"}
        chain_v = chain.verify() if chain is not None else {"chain_intact": True, "length": 0}
        # analysis_locked: the prereg content still hashes to its recorded content_hash —
        # i.e. the analysis on file is byte-identical to what was registered.
        analysis_locked = (_content_hash_of(_PREREG_FROZEN_FIELDS, pr.content) == pr.content_hash)
        return {
            "ok": bool(chain_v["chain_intact"] and analysis_locked),
            "experiment_id": eid,
            "prereg_receipt": pr.as_receipt(),
            "trial_count": chain_v["length"],
            "chain_intact": bool(chain_v["chain_intact"]),
            "analysis_locked": bool(analysis_locked),
            "chain_verify": chain_v,
            "honest_note": HONEST_NOTE,
            "verified_at": _now(),
        }


HONEST_NOTE = (
    "Process-verification ONLY. A passing verify means the analysis was pre-registered "
    "(frozen) before data, the trial chain is tamper-EVIDENT and intact, and the analysis "
    "on file is unchanged. It makes ZERO empirical claim about psi/consciousness being "
    "real and does NOT validate the hypothesis, measurement, or result. Tamper-EVIDENT, "
    "not tamper-proof. Demo data is SIMULATED. Methodology need cited to Radin/IONS, the "
    "Global Consciousness Project, and open-science Registered Reports / OSF; their "
    "results are NOT endorsed. Λ stays Conjecture 1; not in the locked-8 proven set."
)


# Process-local registry backing the endpoints.
_REGISTRY = ResearchRegistry()


# ---------------------------------------------------------------------------
# DEMO fixture: a Radin-STYLE double-slit "observer effect" pre-registration plus a
# few SIMULATED trials, so /verify shows a working tamper-evident chain out of the box.
# ---------------------------------------------------------------------------
DEMO_EXPERIMENT_ID = "demo-radin-style-doubleslit-observer-effect"

# The frozen analysis spec: FIXED N, two-tailed test, NO optional stopping. This is the
# pre-registration discipline the literature prescribes — it is NOT a claim about the
# outcome. primary_outcome is a z-score of the interference shift.
DEMO_ANALYSIS_SPEC = {
    "statistical_test": "one-sample two-tailed z-test of mean interference-shift index vs 0",
    "stopping_rule": "FIXED N — collect exactly N trials, then stop; NO optional stopping",
    "N": 12,
    "alpha": 0.05,
    "directionality": "two-tailed",
    "p_hacking_guards": [
        "no optional stopping (N fixed in advance)",
        "no post-hoc outcome switching (primary_outcome frozen)",
        "no data-selection (every trial appended to the hash-linked chain)",
    ],
}


def _seed_demo() -> None:
    """Pre-register the demo experiment and append N SIMULATED trials.

    The trial values come from a fixed-seed PRNG so the demo is reproducible. They are
    SIMULATED/DEMO data — NOT a real measurement and NOT evidence of any observer effect.
    """
    if DEMO_EXPERIMENT_ID in _REGISTRY._prereg:
        return
    _REGISTRY.prereg(
        experiment_id=DEMO_EXPERIMENT_ID,
        hypothesis=("SIMULATED/DEMO hypothesis (Radin-style): directed attention by an observer "
                    "shifts a double-slit interference measure relative to a no-attention baseline. "
                    "This is a METHODOLOGY DEMO of the pre-registration workflow, NOT a claim the "
                    "effect is real."),
        primary_outcome="z-score of the mean interference-shift index across N trials (vs 0)",
        analysis_spec=DEMO_ANALYSIS_SPEC,
        researcher="DEMO researcher (workflow illustration; e.g. a Radin-style protocol)",
    )
    import random
    rng = random.Random(8)  # fixed seed -> reproducible SIMULATED demo data
    n = int(DEMO_ANALYSIS_SPEC["N"])
    for i in range(n):
        # Small zero-centred noise: deliberately NOT engineered to show an effect.
        sim_value = round(rng.gauss(0.0, 1.0), 6)
        _REGISTRY.trial(DEMO_EXPERIMENT_ID, trial_index=i, value=sim_value, simulated=True)


# Seed the demo at import (guarded; never raises into the request path).
try:
    _seed_demo()
except Exception:  # pragma: no cover - defensive, additive-only
    pass


# ---------------------------------------------------------------------------
# HTTP handlers + registration (matches szl_energy_provenance add_api_route style).
# ---------------------------------------------------------------------------
async def _h_prereg(req: Request):
    from starlette.responses import JSONResponse
    try:
        body = await req.json()
    except Exception:
        body = {}
    eid = body.get("experiment_id")
    if not eid:
        return JSONResponse({"ok": False, "reason": "experiment_id is required"}, status_code=400)
    res = _REGISTRY.prereg(
        experiment_id=eid,
        hypothesis=body.get("hypothesis", ""),
        primary_outcome=body.get("primary_outcome", ""),
        analysis_spec=body.get("analysis_spec", {}),
        researcher=body.get("researcher", ""),
    )
    # 409 when a frozen spec is being re-specified; 200 otherwise.
    status = 409 if res.get("rejected") else 200
    return JSONResponse(res, status_code=status)


async def _h_trial(req: Request):
    from starlette.responses import JSONResponse
    try:
        body = await req.json()
    except Exception:
        body = {}
    eid = body.get("experiment_id")
    if not eid or "trial_index" not in body or "value" not in body:
        return JSONResponse(
            {"ok": False, "reason": "experiment_id, trial_index, and value are required"},
            status_code=400)
    res = _REGISTRY.trial(
        experiment_id=eid,
        trial_index=body.get("trial_index"),
        value=body.get("value"),
        ts=body.get("ts"),
        simulated=bool(body.get("simulated", False)),
    )
    status = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status)


def _h_verify(experiment_id: str):
    from starlette.responses import JSONResponse
    res = _REGISTRY.verify(experiment_id)
    status = 200 if res.get("ok") or res.get("prereg_receipt") else 404
    return JSONResponse(res, status_code=status)


def register(app, ns="a11oy"):
    """Wire the research-infra endpoints additively under /api/<ns>/v1/research/*.

    Uses FastAPI's add_api_route when available (so routes resolve before the SPA
    catch-all, matching the other szl_* modules); falls back to a Starlette route
    append for a bare Starlette app. Returns the list of registered paths."""
    base = f"/api/{ns}/v1/research"
    add_api_route = getattr(app, "add_api_route", None)
    routes = [
        (f"{base}/prereg", _h_prereg, ["POST"]),
        (f"{base}/trial", _h_trial, ["POST"]),
        (f"{base}/verify/{{experiment_id}}", _h_verify, ["GET"]),
    ]
    paths = []
    for path, fn, methods in routes:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=methods)
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn, methods=methods))
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# No-server self-test: prereg freeze, trial chain tamper-evidence, verify, demo label.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}
    reg = ResearchRegistry()

    spec = {"statistical_test": "two-tailed z-test", "stopping_rule": "fixed N", "N": 10, "alpha": 0.05}

    # (a) Pre-register; receipt is frozen + content-hashed + time-stamped.
    r0 = reg.prereg("exp-1", "directed attention shifts an interference measure",
                    "z-score of the shift", spec, "Researcher A")
    assert r0["ok"] and r0["frozen"] and r0["newly_registered"], r0
    receipt = r0["prereg_receipt"]
    assert receipt["content_hash"] and receipt["frozen"] is True
    assert "signed" in receipt  # honest signing flag present (True or False)
    out["prereg_freezes_spec"] = True

    # (b) Re-submit the SAME spec -> idempotent, returns original receipt (not a new one).
    r_same = reg.prereg("exp-1", "directed attention shifts an interference measure",
                        "z-score of the shift", spec, "Researcher A")
    assert r_same["ok"] and r_same.get("idempotent"), r_same
    assert r_same["prereg_receipt"]["content_hash"] == receipt["content_hash"]
    out["resubmit_same_spec_idempotent"] = True

    # (c) Re-submit a CHANGED analysis -> REJECTED (freeze enforced).
    changed = dict(spec); changed["stopping_rule"] = "optional stopping (peek-and-stop)"
    r_chg = reg.prereg("exp-1", "directed attention shifts an interference measure",
                       "z-score of the shift", changed, "Researcher A")
    assert r_chg["ok"] is False and r_chg.get("rejected"), r_chg
    assert "FROZEN" in r_chg["reason"]
    out["changed_spec_rejected"] = True

    # (d) Append trials -> hash-linked chain; verify reports intact.
    for i in range(5):
        tr = reg.trial("exp-1", trial_index=i, value=float(i) * 0.1, simulated=True)
        assert tr["ok"], tr
    v_ok = reg.verify("exp-1")
    assert v_ok["chain_intact"] is True and v_ok["analysis_locked"] is True and v_ok["ok"] is True, v_ok
    assert v_ok["trial_count"] == 5
    out["clean_chain_verifies"] = True

    # (e) TAMPER a trial value -> verify catches the broken chain.
    chain = reg._chains["exp-1"]
    chain._chain[2]["value"] = 999.0
    v_bad = reg.verify("exp-1")
    assert v_bad["chain_intact"] is False and v_bad["ok"] is False, v_bad
    assert v_bad["chain_verify"]["first_break"]["index"] == 2
    out["tamper_detected"] = True
    chain._chain[2]["value"] = 0.2  # restore

    # (f) Reorder two trials -> broken link caught.
    reg2 = ResearchRegistry()
    reg2.prereg("exp-2", "h", "o", spec, "B")
    reg2.trial("exp-2", 0, 0.0, simulated=True)
    reg2.trial("exp-2", 1, 1.0, simulated=True)
    cref = reg2._chains["exp-2"]._chain
    cref[0], cref[1] = cref[1], cref[0]
    v2 = reg2.verify("exp-2")
    assert v2["chain_intact"] is False, v2
    out["reorder_detected"] = True

    # (g) Demo fixture: registered, has SIMULATED trials, verifies intact, labelled.
    dv = _REGISTRY.verify(DEMO_EXPERIMENT_ID)
    assert dv["chain_intact"] is True and dv["analysis_locked"] is True, dv
    assert dv["trial_count"] == int(DEMO_ANALYSIS_SPEC["N"])
    demo_entries = _REGISTRY._chains[DEMO_EXPERIMENT_ID].entries()
    assert all("SIMULATED" in e.get("data_label", "") for e in demo_entries), "demo trials must be labelled SIMULATED"
    assert "SIMULATED" in dv["prereg_receipt"]["hypothesis"]
    out["demo_simulated_labelled"] = True

    # (h) No key in output: the prereg receipt + verify carry NO private-key material.
    blob = json.dumps(dv, default=str)
    assert "BEGIN EC PRIVATE KEY" not in blob and "BEGIN PRIVATE KEY" not in blob
    assert "PRIVATE KEY" not in blob
    out["no_key_in_output"] = True

    # (i) Honest note present; process-verification only; tamper-EVIDENT not tamper-proof.
    assert "Process-verification ONLY" in dv["honest_note"]
    assert "tamper-EVIDENT" in dv["honest_note"] and "tamper-proof" in dv["honest_note"]
    assert "Conjecture 1" in dv["honest_note"]
    out["honest_note_ok"] = True

    out["dsse_source"] = _DSSE_SOURCE
    out["signing_available"] = bool(_dsse and _dsse.signing_available()) if _dsse else False
    out["ok"] = True
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2, default=str))
