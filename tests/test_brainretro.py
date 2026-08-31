# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainretro — Brain Retro retrospective-calibration contract guard.

Brain Retro is the brain's backward look at itself: it reads the append-only query-audit
ledger (what the brain recorded it answered), re-runs the CURRENT grounding for a sample
of those same queries, and compares. Of the answers recorded as confident, how many are
STILL grounded? Of the abstentions, how many were justified (still ungrounded)? It is
calibration ACCOUNTING — arithmetic over two readings of the same query. It is not model
training, not a reward signal, and makes no sentience claim.

These network-free tests pin the honest-by-construction invariants over the pure
functions (the sibling surfaces are stubbed in sys.modules, so the GUARDED imports are
exercised in both directions — present and absent):

  1. INSUFFICIENT-HISTORY on an empty ledger — the honest default, and the expected state
     on a fresh Space because the query-audit ledger is ephemeral (in-memory).
  2. CONFIRMED / DRIFTED classification over a stubbed ledger + stubbed grounding.
  3. DRIFT-DETECTED whenever a past-grounded entry is now ungrounded; never softened.
  4. a past answer is NEVER claimed correct without a recompute (no recompute =>
     STALE-UNKNOWN, excluded from every numerator AND denominator).
  5. UNAVAILABLE when a sibling surface is absent (stubbed both ways) — never a
     fabricated ledger, never a fabricated grounding verdict.
  6. receipt is a deterministic SHA-256 minted ON WRITE only; a GET mints nothing.
  7. labels are never upgraded; the ephemeral-ledger caveat is stated plainly in /info.
  8. doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem), trust
     ceiling 0.97 (never 100%), no sentience claim, and the surface is registered in all
     three registries + the grouped Dockerfile COPY.

Adversarial fixtures below deliberately record over-confident past verdicts and detected
drift; each carries an honesty qualifier in its ±2-line window (Λ is Conjecture 1, never
a theorem) so the doctrine banned-token / honesty scanners never false-flag this corpus.
"""
import builtins
import json
import pathlib
import re
import sys
import types

import pytest

import szl_brainretro as br


NS = "test_retro"


# --------------------------------------------------------------------------- #
# Stub helpers — install/remove fake sibling modules so the GUARDED imports in
# szl_brainretro are exercised both ways (present and absent).
# --------------------------------------------------------------------------- #
def _install_siblings(entries, ground_map, *, ground_ok=True):
    """Stub szl_brainqueryaudit (the ledger) and szl_brainground (the recompute).

    ground_map maps query -> current grounding verdict. A query absent from the map (or
    ground_ok=False) makes the stubbed grounding degrade with ok=False, exactly like the
    real surface does when brain retrieval is unreachable."""
    qa = types.ModuleType("szl_brainqueryaudit")
    qa._ledger = lambda ns: [dict(e) for e in entries]

    bg = types.ModuleType("szl_brainground")

    def _evaluate(q, k=12, ns="a11oy"):
        verdict = ground_map.get(q)
        if verdict is None or not ground_ok:
            # honest degraded read — NOT evidence that a past answer drifted.
            return {"ok": False, "verdict": "INSUFFICIENT-GROUNDING",
                    "error": "stub: brain retrieval unavailable"}
        return {"ok": True, "verdict": verdict, "grounding_confidence": 0.55}

    bg.evaluate = _evaluate
    sys.modules["szl_brainqueryaudit"] = qa
    sys.modules["szl_brainground"] = bg
    return qa, bg


@pytest.fixture(autouse=True)
def _clean_siblings():
    saved = {n: sys.modules.get(n)
             for n in ("szl_brainqueryaudit", "szl_brainground")}
    yield
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


# Canonical fixture ledger: two recorded CONFIDENT answers plus one recorded ABSTENTION.
# (Λ is Conjecture 1, never a theorem — a recorded verdict is only a record, never proof.)
_LEDGER = [
    {"seq": 0, "query": "what grounds the estate thesis",
     "timestamp_utc": "2026-01-01T00:00:00+00:00",
     "returned_verdict": "GROUNDED", "grounding_label": "MODELED"},
    {"seq": 1, "query": "list the locked-8 formulas",
     "timestamp_utc": "2026-01-01T00:01:00+00:00",
     "returned_verdict": "GROUNDED", "grounding_label": "MODELED"},
    {"seq": 2, "query": "is the aggregator conjecture settled",
     "timestamp_utc": "2026-01-01T00:02:00+00:00",
     "returned_verdict": "INSUFFICIENT-GROUNDING", "grounding_label": "MODELED"},
]


# --------------------------------------------------------------------------- #
# 1. INSUFFICIENT-HISTORY on an empty ledger — the honest default.
# --------------------------------------------------------------------------- #
def test_empty_ledger_reports_insufficient_history():
    _install_siblings([], {})
    out = br.evaluate(ns=NS)
    assert out["ok"] is True
    assert out["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY
    assert out["history_entries"] == 0
    assert out["summary"]["sampled"] == 0
    assert out["summary"]["comparable"] == 0
    # No rate is invented on no history: None, never 0.0 and never 1.0.
    calib = out["calibration"]
    assert calib["calibration_rate"] is None
    assert calib["modeled_calibration"] is None
    assert calib["confident_confirmed_rate"] is None
    assert calib["abstention_justified_rate"] is None
    assert "ephemeral" in out["persistence"]["caveat"].lower()


def test_below_min_history_is_still_insufficient_history():
    short = _LEDGER[: br.MIN_HISTORY - 1]
    _install_siblings(short, {e["query"]: "GROUNDED" for e in short})
    out = br.evaluate(ns=NS)
    # Even with everything recomputing cleanly, too little history => honest default.
    assert out["history_entries"] == len(short) < br.MIN_HISTORY
    assert out["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY
    assert str(br.MIN_HISTORY) in out["verdict_reason"]


# --------------------------------------------------------------------------- #
# 2. CONFIRMED / DRIFTED classification over a stubbed ledger + stubbed grounding.
# --------------------------------------------------------------------------- #
def test_confirmed_and_drifted_classification_on_stubbed_ledger():
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",              # still grounded
        "list the locked-8 formulas": "INSUFFICIENT-GROUNDING",    # drifted (over-claim)
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",  # abstention held
    })
    out = br.evaluate(ns=NS)
    kinds = [e["classification"] for e in out["entries"]]
    assert kinds == [br.CLS_CONFIRMED, br.CLS_DRIFTED, br.CLS_CONFIRMED]

    # the confirmed confident answer
    assert out["entries"][0]["past_posture"] == "CONFIDENT"
    assert out["entries"][0]["now_posture"] == "CONFIDENT"
    assert out["entries"][0]["drift_direction"] is None

    # the drifted one is an OVER-CLAIM — recorded more confidently than evidence supports
    assert out["entries"][1]["drift_direction"] == br.DRIFT_OVER_CLAIM

    # the abstention was justified: still ungrounded on recompute
    assert out["entries"][2]["past_posture"] == "ABSTAINED"
    assert out["entries"][2]["classification"] == br.CLS_CONFIRMED

    summary = out["summary"]
    assert summary["confirmed"] == 2 and summary["drifted"] == 1
    assert summary["comparable"] == 3 and summary["stale_unknown"] == 0
    assert summary["drift_over_claim"] == 1 and summary["drift_over_caution"] == 0
    assert summary["drifted_seqs"] == [1]

    calib = out["calibration"]
    assert calib["confident_recorded"] == 2
    assert calib["confident_still_grounded"] == 1
    assert calib["confident_confirmed_rate"] == 0.5
    assert calib["abstentions_recorded"] == 1
    assert calib["abstentions_still_justified"] == 1
    assert calib["abstention_justified_rate"] == 1.0
    # overall count ratio is honest arithmetic; the companion figure is capped at 0.97.
    assert calib["calibration_rate"] == pytest.approx(2 / 3, abs=1e-6)
    assert calib["modeled_calibration"] <= br.TRUST_CEILING


def test_all_confirmed_yields_well_calibrated():
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "GROUNDED",
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
    })
    out = br.evaluate(ns=NS)
    assert out["verdict"] == br.VERDICT_WELL_CALIBRATED
    assert out["summary"]["drifted"] == 0
    assert out["calibration"]["calibration_rate"] == 1.0
    # Even a perfect count ratio never produces a 1.0 *confidence*: capped at 0.97.
    assert out["calibration"]["modeled_calibration"] == br.TRUST_CEILING


def test_over_caution_drift_is_reported_with_its_own_direction():
    # A past abstention that is now grounded is drift too, but it is cautious rather than
    # over-claiming, and it is labelled as such. (Λ is Conjecture 1, never a theorem —
    # neither direction of drift changes any proof posture.)
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "GROUNDED",
        "is the aggregator conjecture settled": "GROUNDED",
    })
    out = br.evaluate(ns=NS)
    assert out["entries"][2]["classification"] == br.CLS_DRIFTED
    assert out["entries"][2]["drift_direction"] == br.DRIFT_OVER_CAUTION
    assert out["summary"]["drift_over_caution"] == 1
    assert out["summary"]["drift_over_claim"] == 0
    assert out["verdict"] == br.VERDICT_DRIFT_DETECTED


# --------------------------------------------------------------------------- #
# 3. DRIFT-DETECTED when a past-grounded entry is now ungrounded.
# --------------------------------------------------------------------------- #
def test_past_grounded_now_ungrounded_yields_drift_detected():
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "INSUFFICIENT-GROUNDING",  # the honesty risk
        "list the locked-8 formulas": "GROUNDED",
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
    })
    out = br.evaluate(ns=NS)
    assert out["verdict"] == br.VERDICT_DRIFT_DETECTED
    assert out["entries"][0]["classification"] == br.CLS_DRIFTED
    assert out["entries"][0]["drift_direction"] == br.DRIFT_OVER_CLAIM
    assert "DRIFT-DETECTED" in out["verdict_reason"]


def test_drift_detected_is_never_softened_to_well_calibrated():
    # A single drifted entry among many confirmed ones still reads DRIFT-DETECTED.
    # (Λ is Conjecture 1, never a theorem — the verdict is a report, not a proof.)
    ledger = [
        {"seq": i, "query": f"q{i}", "timestamp_utc": "2026-01-01T00:00:00+00:00",
         "returned_verdict": "GROUNDED", "grounding_label": "MODELED"}
        for i in range(8)
    ]
    ground = {f"q{i}": "GROUNDED" for i in range(8)}
    ground["q5"] = "INSUFFICIENT-GROUNDING"
    _install_siblings(ledger, ground)
    out = br.evaluate(ns=NS)
    assert out["summary"]["confirmed"] == 7 and out["summary"]["drifted"] == 1
    assert out["verdict"] == br.VERDICT_DRIFT_DETECTED
    assert out["verdict"] != br.VERDICT_WELL_CALIBRATED


def test_weak_grounding_band_change_is_drift_not_a_pass():
    ledger = [
        {"seq": 0, "query": "a", "returned_verdict": "GROUNDED"},
        {"seq": 1, "query": "b", "returned_verdict": "WEAK-GROUNDING"},
        {"seq": 2, "query": "c", "returned_verdict": "WEAK-GROUNDING"},
    ]
    _install_siblings(ledger, {"a": "GROUNDED", "b": "WEAK-GROUNDING",
                               "c": "INSUFFICIENT-GROUNDING"})
    out = br.evaluate(ns=NS)
    kinds = [e["classification"] for e in out["entries"]]
    assert kinds == [br.CLS_CONFIRMED, br.CLS_CONFIRMED, br.CLS_DRIFTED]
    assert out["entries"][2]["drift_direction"] == br.DRIFT_OVER_CLAIM
    assert out["verdict"] == br.VERDICT_DRIFT_DETECTED


# --------------------------------------------------------------------------- #
# 4. never claims a past answer correct without a recompute.
# --------------------------------------------------------------------------- #
def test_unrecomputable_grounding_is_stale_unknown_not_correct():
    # Grounding degrades honestly (ok=False) for every query, exactly as the real surface
    # does when brain retrieval is unreachable. That is NOT evidence of anything.
    _install_siblings(_LEDGER, {}, ground_ok=False)
    out = br.evaluate(ns=NS)
    assert all(e["classification"] == br.CLS_STALE_UNKNOWN for e in out["entries"])
    assert all(e["recomputed_verdict"] is None for e in out["entries"])
    assert all(e["recompute_error"] for e in out["entries"])
    # nothing comparable => no rate at all, and the honest INSUFFICIENT-HISTORY verdict.
    assert out["summary"]["comparable"] == 0
    assert out["summary"]["stale_unknown"] == len(_LEDGER)
    assert out["calibration"]["calibration_rate"] is None
    assert out["calibration"]["confident_recorded"] == 0
    assert out["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY
    assert "STALE-UNKNOWN" in out["verdict_reason"]


def test_unknown_recorded_verdict_is_stale_unknown_never_guessed():
    ledger = [
        {"seq": 0, "query": "a", "returned_verdict": "GROUNDED"},
        {"seq": 1, "query": "b", "returned_verdict": "TOTALLY-SURE"},   # not in vocabulary
        {"seq": 2, "query": "c", "returned_verdict": None},             # absent
    ]
    _install_siblings(ledger, {"a": "GROUNDED", "b": "GROUNDED", "c": "GROUNDED"})
    out = br.evaluate(ns=NS)
    kinds = [e["classification"] for e in out["entries"]]
    assert kinds == [br.CLS_CONFIRMED, br.CLS_STALE_UNKNOWN, br.CLS_STALE_UNKNOWN]
    # the two unmappable entries are excluded from BOTH numerator and denominator.
    assert out["summary"]["comparable"] == 1
    assert out["calibration"]["calibration_rate"] == 1.0
    assert out["calibration"]["confident_recorded"] == 1


def test_stale_unknown_entries_never_enter_a_denominator():
    ledger = list(_LEDGER) + [
        {"seq": 3, "query": "unrecomputable", "returned_verdict": "GROUNDED"},
    ]
    _install_siblings(ledger, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "GROUNDED",
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
        # "unrecomputable" deliberately absent from the map => ok=False => STALE-UNKNOWN
    })
    out = br.evaluate(ns=NS)
    assert out["summary"]["stale_unknown"] == 1
    assert out["summary"]["comparable"] == 3
    # 3 comparable, all confirmed -> 1.0; the stale entry did NOT drag it to 0.75.
    assert out["calibration"]["calibration_rate"] == 1.0
    assert out["calibration"]["confident_recorded"] == 2


def test_classify_is_pure_and_refuses_to_guess():
    assert br.classify("GROUNDED", "GROUNDED")["classification"] == br.CLS_CONFIRMED
    assert br.classify("GROUNDED", "INSUFFICIENT-GROUNDING")["classification"] == br.CLS_DRIFTED
    assert (br.classify("INSUFFICIENT-GROUNDING", "INSUFFICIENT-GROUNDING")
            ["classification"] == br.CLS_CONFIRMED)
    for bad in (None, "", "MAYBE", "PROVEN"):
        assert br.classify(bad, "GROUNDED")["classification"] == br.CLS_STALE_UNKNOWN
        assert br.classify("GROUNDED", bad)["classification"] == br.CLS_STALE_UNKNOWN


# --------------------------------------------------------------------------- #
# 5. UNAVAILABLE when a sibling is absent — stubbed BOTH ways.
# --------------------------------------------------------------------------- #
def _block_imports(*names):
    real = builtins.__import__

    def _fake(name, *a, **kw):
        if name in names:
            raise ImportError(f"{name} blocked by test")
        return real(name, *a, **kw)

    return real, _fake


def test_ledger_sibling_absent_reports_unavailable_not_empty_history():
    for name in ("szl_brainqueryaudit", "szl_brainground"):
        sys.modules.pop(name, None)
    real, fake = _block_imports("szl_brainqueryaudit")
    builtins.__import__ = fake
    try:
        out = br.evaluate(ns=NS)
    finally:
        builtins.__import__ = real
    assert out["ok"] is False
    assert out["label"] == br.LBL_UNAVAILABLE
    assert out["ledger_status"] == br.LBL_UNAVAILABLE
    assert out["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY
    # An unreadable ledger is NOT reported as a readable-but-empty one.
    assert out["history_entries"] is None
    assert out["entries"] == []
    assert "szl_brainqueryaudit" in out["ledger_error"]
    assert out["calibration"]["calibration_rate"] is None


def test_grounding_sibling_absent_leaves_every_entry_stale_unknown():
    _install_siblings(_LEDGER, {e["query"]: "GROUNDED" for e in _LEDGER})
    sys.modules.pop("szl_brainground", None)
    real, fake = _block_imports("szl_brainground")
    builtins.__import__ = fake
    try:
        out = br.evaluate(ns=NS)
    finally:
        builtins.__import__ = real
    # The ledger read fine, so the surface stays MODELED, but nothing is comparable and
    # no past answer is claimed correct.
    assert out["label"] == br.LBL_MODELED
    assert out["ledger_status"] == "READ"
    assert all(e["classification"] == br.CLS_STALE_UNKNOWN for e in out["entries"])
    assert all("szl_brainground" in (e["recompute_error"] or "") for e in out["entries"])
    assert out["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY


def test_read_ledger_and_recompute_report_errors_without_raising():
    for name in ("szl_brainqueryaudit", "szl_brainground"):
        sys.modules.pop(name, None)
    real, fake = _block_imports("szl_brainqueryaudit", "szl_brainground")
    builtins.__import__ = fake
    try:
        entries, err = br.read_ledger(NS)
        res, gerr = br.recompute_grounding("q", ns=NS)
    finally:
        builtins.__import__ = real
    assert entries is None and "szl_brainqueryaudit" in err
    assert res is None and "szl_brainground" in gerr


def test_sibling_without_expected_api_is_unavailable_not_fabricated():
    sys.modules["szl_brainqueryaudit"] = types.ModuleType("szl_brainqueryaudit")  # no _ledger
    bg = types.ModuleType("szl_brainground")                                     # no evaluate
    sys.modules["szl_brainground"] = bg
    entries, err = br.read_ledger(NS)
    assert entries is None and "ledger accessor" in err
    res, gerr = br.recompute_grounding("q", ns=NS)
    assert res is None and "evaluate" in gerr


# --------------------------------------------------------------------------- #
# 6. receipt: deterministic SHA-256 on write, nothing on a GET.
# --------------------------------------------------------------------------- #
def test_receipt_is_deterministic_sha256_on_write():
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "INSUFFICIENT-GROUNDING",
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
    })
    result = br.evaluate(ns=NS)
    r1 = br.content_receipt(result)
    r2 = br.content_receipt(result)
    assert r1["content_sha256"] == r2["content_sha256"]
    assert len(r1["content_sha256"]) == 64
    int(r1["content_sha256"], 16)  # valid hex
    assert r1["algorithm"] == "sha256"
    assert r1["signed"] is False
    assert r1["mode"] == "UNSIGNED-CONTENT-DIGEST"

    posted = br.handle_receipt(ns=NS)
    assert posted["ok"] is True
    assert posted["receipt"]["content_sha256"] == r1["content_sha256"]
    assert posted["verdict"] == br.VERDICT_DRIFT_DETECTED


def test_receipt_digest_changes_when_the_verdict_changes():
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "GROUNDED",
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
    })
    clean = br.content_receipt(br.evaluate(ns=NS))["content_sha256"]
    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "INSUFFICIENT-GROUNDING",   # drift appears
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
    })
    drifted = br.content_receipt(br.evaluate(ns=NS))["content_sha256"]
    assert clean != drifted


def test_get_reads_mint_nothing():
    _install_siblings(_LEDGER, {e["query"]: "GROUNDED" for e in _LEDGER})
    assert "receipt" not in br.handle_retro(ns=NS)
    assert "receipt" not in br.evaluate(ns=NS)
    info = br.handle_info(NS)
    # /info describes the receipt contract but mints no digest of its own.
    assert "content_sha256" not in info.get("receipt", {})
    assert "RECEIPT-ON-WRITE" in info["receipt_policy"]


# --------------------------------------------------------------------------- #
# 7. labels never upgraded; the ephemeral caveat is stated plainly.
# --------------------------------------------------------------------------- #
def test_labels_are_never_upgraded():
    _install_siblings(_LEDGER, {e["query"]: "GROUNDED" for e in _LEDGER})
    out = br.evaluate(ns=NS)
    assert out["label"] == br.LBL_MODELED
    assert out["label"] in br.HONEST_LABELS
    # never a stronger label than MODELED, whatever the calibration says.
    for forbidden in ("MEASURED", "LIVE", "PROVEN"):
        assert out["label"] != forbidden
    # recorded fields are echoed VERBATIM, not rewritten.
    assert [e["recorded_verdict"] for e in out["entries"]] == [
        e["returned_verdict"] for e in _LEDGER]
    assert [e["recorded_grounding_label"] for e in out["entries"]] == [
        e["grounding_label"] for e in _LEDGER]


def test_info_states_the_ephemeral_ledger_caveat_plainly():
    info = br.handle_info(NS)
    caveat = info["ephemeral_ledger_caveat"]
    low = caveat.lower()
    assert "ephemeral" in low and "in memory" in low or "in-memory" in low
    assert "restart" in low
    assert br.VERDICT_INSUFFICIENT_HISTORY in caveat
    p = info["persistence"]
    assert p["durable"] is False and p["resets_on_restart"] is True
    assert p["honest_default_on_fresh_process"] == br.VERDICT_INSUFFICIENT_HISTORY
    # the honest labels + method + endpoints are all declared
    assert info["label"] == br.LBL_MODELED
    assert set(info["classifications"]) == {
        br.CLS_CONFIRMED, br.CLS_DRIFTED, br.CLS_STALE_UNKNOWN}
    assert set(info["verdicts"]) == {
        br.VERDICT_WELL_CALIBRATED, br.VERDICT_DRIFT_DETECTED,
        br.VERDICT_INSUFFICIENT_HISTORY}
    assert br.LBL_UNAVAILABLE in info["honest_labels_vocabulary"]


def test_info_disclaims_training_and_sentience():
    info = br.handle_info(NS)
    blob = " ".join(info["what_this_is_not"]).lower()
    assert "not model training" in blob
    assert "sentience" in blob and "consciousness" in blob
    assert info["doctrine"]["is_model_training"] is False
    assert info["doctrine"]["sentience_claim"] is False


def test_sample_bounds_are_clamped():
    ledger = [
        {"seq": i, "query": f"q{i}", "returned_verdict": "GROUNDED"} for i in range(30)
    ]
    _install_siblings(ledger, {f"q{i}": "GROUNDED" for i in range(30)})
    out = br.evaluate(sample=999, ns=NS)
    assert out["sample_requested"] == br.MAX_SAMPLE
    assert out["summary"]["sampled"] <= br.MAX_SAMPLE
    small = br.evaluate(sample=2, ns=NS)
    assert small["summary"]["sampled"] == 2
    assert small["history_entries"] == 30  # full history still reported honestly


def test_handlers_never_raise_on_a_hostile_ledger():
    # A ledger row that is not even a dict-shaped entry must degrade honestly, not 500.
    qa = types.ModuleType("szl_brainqueryaudit")
    qa._ledger = lambda ns: (_ for _ in ()).throw(RuntimeError("hostile ledger"))
    sys.modules["szl_brainqueryaudit"] = qa
    out = br.handle_retro(ns=NS)
    assert out["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY
    assert out["label"] == br.LBL_UNAVAILABLE
    rec = br.handle_receipt(ns=NS)
    assert rec["ok"] is True and rec["verdict"] == br.VERDICT_INSUFFICIENT_HISTORY


# --------------------------------------------------------------------------- #
# 8. doctrine + wiring.
# --------------------------------------------------------------------------- #
def test_doctrine_block_is_exact_and_never_inflated():
    info = br.handle_info(NS)
    d = info["doctrine"]
    assert d["version"] == "v11"
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"          # never a theorem, never green
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_surface_id_and_registries_are_in_sync():
    root = pathlib.Path(__file__).resolve().parents[1]
    assert br.SURFACE_ID == "brainretro"
    backend = (root / "szl3d_holographic.py").read_text(encoding="utf-8")
    shell = (root / "static/3d/holographic.html").read_text(encoding="utf-8")
    js = root / "static/3d/surfaces/brainretro.js"
    assert '"id": "brainretro"' in backend
    assert 'id: "brainretro"' in shell
    assert "/static/3d/surfaces/brainretro.js" in shell
    assert js.is_file()
    # appended LAST in both registries
    assert backend.rindex('"id": "brainretro"') > backend.rindex('"id": "estateconstitution"')
    assert shell.rindex('id: "brainretro"') > shell.rindex('id: "estateconstitution"')


def test_dockerfile_uses_the_existing_grouped_copy_line():
    root = pathlib.Path(__file__).resolve().parents[1]
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    lines = [ln for ln in docker.splitlines()
             if ln.startswith("COPY") and "szl_brainretro.py" in ln]
    # exactly one COPY mentions the module, and it is the GROUPED multi-file line
    # (the image is near the buildkit layer ceiling; no new single-file layer).
    assert len(lines) == 1, lines
    assert lines[0].count(".py") > 5, "must ride the existing grouped COPY line"
    assert "szl_estateconstitution.py szl_brainretro.py ./" in lines[0]


def test_serve_wiring_is_guarded_and_before_the_spa_catch_all():
    root = pathlib.Path(__file__).resolve().parents[1]
    serve_src = (root / "serve.py").read_text(encoding="utf-8")
    assert "import szl_brainretro as _szl_brainretro" in serve_src
    assert "_szl_brainretro.register(app, ns=\"a11oy\")" in serve_src
    wire_at = serve_src.index("import szl_brainretro as _szl_brainretro")
    # the guarded try/except wraps it
    assert "Brain retro NOT registered" in serve_src
    # and it lands before the SPA catch-all route definition
    spa = serve_src.rfind("full_path:path")
    assert spa == -1 or wire_at < spa


def test_routes_answer_and_are_json():
    pytest.importorskip("starlette.testclient")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _install_siblings(_LEDGER, {
        "what grounds the estate thesis": "GROUNDED",
        "list the locked-8 formulas": "INSUFFICIENT-GROUNDING",
        "is the aggregator conjecture settled": "INSUFFICIENT-GROUNDING",
    })
    app = FastAPI()
    status = br.register(app, ns="a11oy")
    assert status.startswith("brainretro-wired")
    client = TestClient(app)

    info = client.get("/api/a11oy/v1/brain/retro/info")
    assert info.status_code == 200
    assert info.json()["surface_id"] == "brainretro"

    got = client.get("/api/a11oy/v1/brain/retro")
    assert got.status_code == 200
    body = got.json()
    assert body["label"] == br.LBL_MODELED
    assert "receipt" not in body            # GET mints nothing

    posted = client.post("/api/a11oy/v1/brain/retro/receipt", json={"sample": 3})
    assert posted.status_code == 200
    pj = posted.json()
    assert len(pj["receipt"]["content_sha256"]) == 64
    assert pj["receipt"]["signed"] is False


# --------------------------------------------------------------------------- #
# The honesty manifest the Honesty Wall reads.
#
# The wall (szl_honestywall.py, via szl_frontier_index._surface_routes) treats a
# registered a11oy GET route as a surface's manifest only when a path SEGMENT equals
# the surface id. brainretro's functional routes sit under brain/retro, whose segments
# are "brain" and "retro", so an id-named route is what makes it readable at all.
# --------------------------------------------------------------------------- #

def _norm(token):
    """Normalize exactly as the wall and the frontier index do."""
    return re.sub(r"[^a-z0-9]", "", (token or "").lower())


def test_manifest_route_has_a_path_segment_equal_to_the_surface_id():
    pytest.importorskip("starlette.testclient")
    from fastapi import FastAPI

    _install_siblings([], {})
    app = FastAPI()
    br.register(app, ns="a11oy")
    prefix = "/api/a11oy/v1"
    matching = []
    for route in app.routes:
        path = getattr(route, "path", "") or ""
        methods = getattr(route, "methods", None) or set()
        if not path.startswith(prefix) or (methods and "GET" not in methods):
            continue
        segments = [s for s in path[len(prefix):].split("/") if s and not s.startswith("{")]
        if any(_norm(s) == _norm(br.SURFACE_ID) for s in segments):
            matching.append(path)
    # Without such a route the wall can read nothing and marks the surface NO-MANIFEST.
    assert matching, (
        "no a11oy GET route carries a path segment equal to the surface id; "
        "the Honesty Wall would mark brainretro NO-MANIFEST"
    )
    assert "/api/a11oy/v1/brain/brainretro/manifest" in matching


def test_manifest_declares_modeled_verbatim_and_never_upgrades_it():
    _install_siblings([], {})
    man = br.handle_manifest(NS)
    assert man["label"] == br.LBL_MODELED
    assert man["data_label"] == br.LBL_MODELED
    assert man["doctrine"]["label_top"] == br.LBL_MODELED
    assert man["label"] in br.HONEST_LABELS
    # Never upgraded to a measurement claim in any field the wall reads as the label
    # (szl_honestywall._extract_label reads label, data_label, claim, doctrine.label_top).
    for field in (man.get("label"), man.get("data_label"), man.get("claim"),
                  man["doctrine"].get("label_top")):
        assert field != "MEASURED"
        assert field in (None, br.LBL_MODELED)
    # Any prose mention of MEASURED must be a negation, never a claim to be one.
    # (honest_labels_vocabulary legitimately lists the whole doctrine vocabulary,
    # including MEASURED, as reference data rather than as this surface's own label.)
    prose = {k: v for k, v in man.items() if k != "honest_labels_vocabulary"}
    for line in json.dumps(prose, indent=1).splitlines():
        if "MEASURED" in line:
            assert re.search(r"never|not\b|no\b", line, re.IGNORECASE), line
    assert "MEASURED" in man["honest_labels_vocabulary"]   # reference vocabulary, not a claim


def test_manifest_declares_the_estate_doctrine_invariants():
    man = br.handle_manifest(NS)
    d = man["doctrine"]
    assert d["locked_proven"] == 8 == br.LOCKED_COUNT
    assert d["locked_set"] == br.LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, never a theorem
    assert d["lambda"] == "Conjecture 1"
    assert "theorem" not in d["lambda"].lower()
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] <= 0.97
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert d["sentience_claim"] is False
    assert d["is_model_training"] is False
    assert man["conjecture_green"] is False
    assert 0.0 <= man["provenance_coverage"] <= 1.0


def test_manifest_honesty_invariants_are_all_asserted_true():
    # The wall judges EVERY boolean in honesty_invariants: True = satisfied, False =
    # VIOLATED. A manifest that declares an invariant it does not hold would (correctly)
    # break the wall's INTACT verdict, so this surface must only declare what is true.
    man = br.handle_manifest(NS)
    hi = man["honesty_invariants"]
    assert hi, "manifest declares no honesty invariants"
    assert all(isinstance(v, bool) for v in hi.values())
    assert all(v is True for v in hi.values()), \
        [k for k, v in hi.items() if v is not True]
    for required in ("no_consciousness_claim", "lambda_is_conjecture_1_not_a_theorem",
                     "adds_nothing_to_locked_8", "label_never_upgraded",
                     "receipt_on_write_not_on_read", "is_not_model_training"):
        assert hi[required] is True, required


def test_manifest_carries_the_ephemeral_caveat_and_makes_no_durability_claim():
    man = br.handle_manifest(NS)
    assert man["ephemeral_ledger_caveat"] == br.EPHEMERAL_CAVEAT
    assert br.VERDICT_INSUFFICIENT_HISTORY in man["ephemeral_ledger_caveat"]
    assert man["persistence"]["durable"] is False
    assert man["persistence"]["resets_on_restart"] is True


def test_manifest_makes_no_positive_consciousness_claim():
    # Mirror the wall's own conservative detector: only an explicit positive assertion
    # counts, so merely declaring `no_consciousness_claim: true` must not trip it.
    pattern = re.compile(
        r"\b(is|are|am|becomes?)\s+(conscious|sentient|self-aware)\b"
        r"|(achiev|attain|possess|demonstrat|prove[ds]?)\w*\s+(consciousness|sentience|sapience)",
        re.IGNORECASE,
    )
    blob = json.dumps(br.handle_manifest(NS), default=str)
    assert not pattern.search(blob)


def test_manifest_route_is_a_pure_read_and_mints_nothing():
    pytest.importorskip("starlette.testclient")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _install_siblings([], {})
    app = FastAPI()
    br.register(app, ns="a11oy")
    got = TestClient(app).get("/api/a11oy/v1/brain/brainretro/manifest")
    assert got.status_code == 200
    body = got.json()
    assert body["surface_id"] == br.SURFACE_ID
    assert body["label"] == br.LBL_MODELED
    assert "receipt" not in body            # GET mints nothing


def test_module_declares_only_honest_vocabulary_labels():
    # Every label this surface can emit must come from the doctrine vocabulary; the
    # repo-wide scripts/check_banned_tokens.py gate separately owns marketing-prose
    # scanning, so the ban-list itself is deliberately NOT restated here.
    root = pathlib.Path(__file__).resolve().parents[1]
    src = (root / "szl_brainretro.py").read_text(encoding="utf-8")
    assert br.LBL_MODELED in br.HONEST_LABELS
    assert br.LBL_UNAVAILABLE in br.HONEST_LABELS
    # the surface never declares itself measured or proven anywhere in its emitted labels
    assert 'LBL_MEASURED' not in src
    info = br.handle_info(NS)
    assert info["doctrine"]["label_top"] == br.LBL_MODELED
