# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_energy_wire_operator_ledger.py — guards the demo-critical operator->ledger wiring.

Doctrine v11 — proves, OFFLINE and deterministically (no real GPU needed), that the
press-play operator's completed-job emit stream is wired into the hash-chained ledger so
the signed JouleCharge receipt mint actually happens (the star of the founder demo):

  (a) a simulated RUNNING operator with N completed jobs produces N receipts on the
      ledger with an INTACT hash chain (chain.ok, length == N);
  (b) GET projection?window=running reflects the LIVE operator joules/tokens (not the
      documented ground-truth fallback) when the operator reports running;
  (c) revenue is NEVER labeled MEASURED in any projected block (resale = ESTIMATE,
      total = MODELED) — a projected dollar is an assumption, not an observation;
  (d) the wiring is IDEMPOTENT: re-wiring does not double-subscribe and the ledger
      never double-appends the same job (same receipt digest => same idem key);
  (e) a SAMPLE job whose joules_measured is None does NOT crash the subscriber and is
      recorded as non-billable (the bug that left the live ledger at 0 receipts);
  (f) MEASURED jobs against a reachable node mint BILLABLE dry-run receipts (no Stripe
      key) with would_charge_cents > 0 — honest DRY-RUN billing.

Reuses the faithful local Ollama+NVML stub from test_szl_energy_operator so the
"running operator" computes REAL (stubbed) jobs and meters REAL positive joule deltas.

Run: python -m pytest test_energy_wire_operator_ledger.py
"""
from __future__ import annotations

import json
import os
import tempfile

import szl_energy_operator as OP
import szl_energy_ledger as LED
import szl_energy_projection as PROJ
from test_szl_energy_operator import _FakeNode, _node_cfg


def _running_operator_with_jobs(monkeypatch, d, sweeps=2):
    """A reachable-node operator that has completed real (stubbed) MEASURED jobs.

    Returns (operator, n_jobs). Each sweep = generate+embed = 2 jobs; the fake NVML
    meter advances cumulative joules per call so the operator measures joules > 0.
    """
    node = _FakeNode()
    base = node.start()
    monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
    op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                           state_path=os.path.join(d, "op.json"),
                           allow_stub=False)
    for _ in range(sweeps):
        op.run_once()
    monkeypatch._fake_node = node  # keep alive; monkeypatch teardown is per-test
    return op, op.status()["jobs_done"]


# ---------------------------------------------------------------------------
# (a) N running jobs -> N receipts on an intact chain.
# ---------------------------------------------------------------------------
def test_running_operator_mints_n_receipts_intact_chain(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        op, n = _running_operator_with_jobs(monkeypatch, d, sweeps=3)
        assert n >= 3, n
        led = LED.EnergyLedger(path=os.path.join(d, "led.jsonl"))

        res = LED.wire_operator_to_ledger(op, ledger=led)
        assert res["subscribed"] is True, res
        # Backfill replays the operator's in-memory completed jobs immediately.
        assert res["backfilled"] == n, res

        chain = led.verify()
        assert chain["ok"] is True, chain
        assert chain["length"] == n, (chain, n)
        assert chain["links_intact"] and chain["receipts_intact"], chain
        # Every entry is a re-hashable JouleCharge receipt.
        for e in led.entries():
            rc = e["receipt"]
            assert rc["decision"]["receipt_type"] == "SZL.Energy.JouleCharge.v1"


# ---------------------------------------------------------------------------
# (a-cont) NEW jobs after wiring also mint via the live subscription.
# ---------------------------------------------------------------------------
def test_new_jobs_after_wiring_mint_via_subscription(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        op, n0 = _running_operator_with_jobs(monkeypatch, d, sweeps=1)
        led = LED.EnergyLedger(path=os.path.join(d, "led.jsonl"))
        LED.wire_operator_to_ledger(op, ledger=led)
        assert led.verify()["length"] == n0

        op.run_once()  # 2 more jobs emitted live to the subscriber
        n1 = op.status()["jobs_done"]
        assert n1 > n0
        chain = led.verify()
        assert chain["length"] == n1, chain
        assert chain["ok"] is True, chain


# ---------------------------------------------------------------------------
# (b) projection reflects LIVE operator joules/tokens when running (not fallback).
# ---------------------------------------------------------------------------
def test_projection_uses_live_operator_when_running():
    op_status = {
        "running": True,
        "joules_measured_total": 14716.0,
        "window_seconds": 3600.0,
        "tokens_total": 92539,
        "jobs_completed": 173,
        "power_w_sample": 9.74,
        "exporter_node": "betterwithage",
        "grid_price_eur_mwh": 62.08,
    }
    m = PROJ._extract_window(op_status, None)
    assert m["measured_source"].startswith("live:operator"), m
    assert m["operator_running"] is True, m
    assert m["joules_measured"] == 14716.0, m
    assert m["tokens_measured"] == 92539, m
    assert m["jobs_measured"] == 173, m
    # NOT the documented ground-truth fallback joules.
    assert m["joules_measured"] != PROJ._GROUND_TRUTH_JOULES, m

    proj = PROJ.build_projection(window="running", _measured=m)
    j_day = proj["projection_1day_single_node"]["compute_done"]["joules"]["value"]
    assert abs(j_day - 14716.0 * 24.0) < 1e-3, j_day
    t_day = proj["projection_1day_single_node"]["compute_done"]["tokens"]["value"]
    assert abs(t_day - 92539.0 * 24.0) < 1e-3, t_day


def test_projection_falls_back_only_when_operator_idle():
    idle = {"running": False, "joules_measured_total": 0.0, "window_seconds": 0.0,
            "tokens_total": 0}
    m = PROJ._extract_window(idle, None)
    assert m["measured_source"].startswith("fallback"), m
    assert m["operator_running"] is False, m
    assert m["joules_measured"] == PROJ._GROUND_TRUTH_JOULES, m
    assert m["tokens_measured"] is None, m  # unknown — never fabricated


def test_running_operator_with_zero_joules_does_not_falsely_go_live():
    # A running operator that has not yet measured any joules must NOT present 0 J as a
    # live window; it falls back to the documented sample (honest), never fabricates.
    starting = {"running": True, "joules_measured_total": 0.0, "window_seconds": 5.0,
                "tokens_total": 0}
    m = PROJ._extract_window(starting, None)
    assert m["measured_source"].startswith("fallback"), m


# ---------------------------------------------------------------------------
# (c) revenue is NEVER labeled MEASURED in any projected block.
# ---------------------------------------------------------------------------
def test_revenue_never_measured_in_projection():
    m = {"measured_source": "live:operator (running)", "operator_running": True,
         "joules_measured": 14716.0, "window_seconds": 3600.0,
         "tokens_measured": 92539.0, "jobs_measured": 173.0, "power_w_sample": 9.74,
         "grid_price_eur_mwh": 62.08, "node": "betterwithage", "all_measured": True}
    proj = PROJ.build_projection(window="running", _measured=m)

    for path in ("projection_1day_single_node", "scale_projection"):
        assert PROJ.MEASURED not in json.dumps(proj[path]), \
            f"DOCTRINE VIOLATION: MEASURED label inside projected block {path}"

    earn = proj["projection_1day_single_node"]["earnings"]
    assert earn["compute_resale_usd"]["label"] == PROJ.ESTIMATE
    assert earn["total_usd"]["label"] == PROJ.MODELED
    assert earn["grid_arbitrage_credit_usd"]["label"] == PROJ.MODELED
    assert proj["honesty"]["projected_revenue_label"] == PROJ.MODELED
    assert proj["honesty"]["resale_input_label"] == PROJ.ESTIMATE


def test_ledger_receipt_never_fabricates_measured_revenue():
    # A receipt only carries revenue="MEASURED" when a real positive charge is computed;
    # a non-billable (SAMPLE/blocked) job carries revenue="ZERO" — never MEASURED.
    with tempfile.TemporaryDirectory() as d:
        led = LED.EnergyLedger(path=os.path.join(d, "led.jsonl"))
        out = led.append_job(LED.JobRecord.from_dict({
            "node": "rtx-betterwithage", "model": "llama3.1:8b", "kind": "generate",
            "tokens": 42, "wall_s": 1.0, "joules_measured": None,
            "joules_label": "SAMPLE", "joules_evidence": {}, "ts": "2026-06-14T13:00:00Z",
            "seq": 1}))
        assert out["appended"] is True
        assert out["entry"]["billable"] is False
        assert out["entry"]["receipt"]["decision"]["honesty"]["revenue"] == "ZERO"


# ---------------------------------------------------------------------------
# (d) idempotency: re-wiring + duplicate jobs never double-append.
# ---------------------------------------------------------------------------
def test_wiring_idempotent_no_double_append(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        op, n = _running_operator_with_jobs(monkeypatch, d, sweeps=2)
        led = LED.EnergyLedger(path=os.path.join(d, "led.jsonl"))

        r1 = LED.wire_operator_to_ledger(op, ledger=led)
        assert r1["subscribed"] is True and r1["backfilled"] == n
        len1 = led.verify()["length"]

        # Re-wire: must NOT subscribe again, and the backfill replay dedupes entirely.
        r2 = LED.wire_operator_to_ledger(op, ledger=led)
        assert r2["already_wired"] is True, r2
        assert r2["subscribed"] is False, r2
        assert r2["backfilled"] == 0, r2
        assert r2["backfill_duplicates"] == n, r2
        assert led.verify()["length"] == len1, "re-wiring must not grow the chain"
        # Exactly one subscriber registered despite two wire calls.
        assert len(op._subscribers) == 1, op._subscribers


def test_serve_singleton_wiring_emits_receipt_chain_ok(monkeypatch):
    # Mirrors the serve.py boot wiring EXACTLY: wire_operator_to_ledger(get_operator())
    # with NO explicit ledger arg, so the subscription binds the module-level singleton
    # ledger. Asserts that when the operator emits a completed job, a receipt appears in
    # the singleton ledger AND the hash chain stays intact (links_intact true) — the
    # demo's core "measured AND cryptographically receipted" proof, end to end.
    with tempfile.TemporaryDirectory() as d:
        # Point the singleton ledger at a fresh temp file (clean genesis for the test) and
        # reset the lazily-built singletons so this test is hermetic.
        monkeypatch.setenv("SZL_ENERGY_LEDGER_PATH", os.path.join(d, "singleton.jsonl"))
        monkeypatch.setattr(LED, "_LEDGER", None, raising=False)
        monkeypatch.setattr(LED, "DEFAULT_LEDGER_PATH", os.path.join(d, "singleton.jsonl"),
                            raising=False)

        node = _FakeNode()
        base = node.start()
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                               state_path=os.path.join(d, "op.json"),
                               allow_stub=False)
        monkeypatch.setattr(OP, "_OPERATOR", op, raising=False)
        assert OP.get_operator() is op

        # The serve.py call: singleton operator wired to the singleton ledger.
        report = LED.wire_operator_to_ledger(OP.get_operator())
        assert report["subscribed"] is True, report

        led = LED.get_ledger()
        before = led.verify()["length"]
        op.run_once()  # emits generate+embed jobs to the live subscription
        n = op.status()["jobs_done"]
        assert n > 0, op.status()

        chain = led.verify()
        assert chain["length"] == before + n, (chain, before, n)
        assert chain["ok"] is True, chain
        assert chain["links_intact"] is True, chain
        assert chain["receipts_intact"] is True, chain
        assert led.totals()["jobs"] >= n, led.totals()
        monkeypatch._fake_node = node


def test_record_job_none_joules_does_not_crash():
    # The exact shape the operator emits for a non-billable job: joules_measured=None.
    # record_job must NOT raise (the operator's emit loop swallows exceptions, so a
    # raise would silently DROP the job — the 0-receipts bug).
    sample_job = {"node": "rtx-betterwithage", "model": "stub-llama", "kind": "generate",
                  "tokens": 7, "wall_s": 0.5, "joules_measured": None,
                  "joules_label": "SAMPLE", "joules_evidence": {},
                  "ts": "2026-06-14T13:00:00Z", "seq": 9}
    jr = LED.JobRecord.from_dict(sample_job)
    assert jr.joules_measured == 0.0
    assert jr.joules_label == "SAMPLE"


# ---------------------------------------------------------------------------
# (f) MEASURED jobs mint BILLABLE dry-run receipts (no Stripe key => honest dry-run).
# A receipt's amount rounds to whole cents, so we feed the ledger a MEASURED job with
# enough joules to clear 1¢ at 45¢/kWh (joules >= ~40k) — exactly the box's regime.
# ---------------------------------------------------------------------------
def test_measured_jobs_mint_billable_dry_run(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    with tempfile.TemporaryDirectory() as d:
        led = LED.EnergyLedger(path=os.path.join(d, "led.jsonl"),
                               price_per_kwh_cents=45)
        # A MEASURED, fresh job carrying the box's cumulative joules sample.
        out = led.append_job(LED.JobRecord.from_dict({
            "node": "rtx-betterwithage", "model": "llama3.1:8b", "kind": "generate",
            "tokens": 512, "wall_s": 8.0, "joules_measured": 78369.586,
            "joules_label": "MEASURED", "joules_evidence": {"nvml": True},
            "ts": "2026-06-14T13:00:00Z", "seq": 1,
            "nvml_age_s": 12.0, "grid_price_eur_mwh": 62.08}))
        assert out["appended"] is True, out
        assert out["entry"]["billable"] is True, out
        assert out["entry"]["charge"]["status"] == "dry-run", out["entry"]["charge"]

        totals = led.totals()
        assert totals["dry_run_count"] >= 1, totals
        assert totals["would_charge_cents"] >= 1, totals    # MODELED dry-run projection
        assert totals["charged_cents"] == 0, totals         # no real money moves (no key)
        assert led.summary()["stripe_mode"] == "dry-run"
        # Revenue carries MEASURED only because a real positive charge was computed in
        # DRY-RUN; it is NOT a fabricated dollar — the joules are MEASURED + fresh.
        assert out["entry"]["receipt"]["decision"]["honesty"]["revenue"] == "MEASURED"


def test_measured_but_subcent_job_is_billable_not_fabricated(monkeypatch):
    # Honest edge: a MEASURED job too small to clear 1¢ is billable yet its charge is
    # SKIPPED (amount=0) — we never round a sub-cent up into a fabricated charge.
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    with tempfile.TemporaryDirectory() as d:
        op, n = _running_operator_with_jobs(monkeypatch, d, sweeps=3)
        assert op.status()["joules_measured_total"] > 0, op.status()
        led = LED.EnergyLedger(path=os.path.join(d, "led.jsonl"))
        LED.wire_operator_to_ledger(op, ledger=led)
        # Every minted receipt is recorded with an intact chain regardless of amount.
        assert led.verify()["ok"] is True
        assert led.verify()["length"] == n
        # No money moves and nothing fabricated.
        assert led.totals()["charged_cents"] == 0


if __name__ == "__main__":
    import sys
    sys.exit(__import__("pytest").main([__file__, "-q"]))
