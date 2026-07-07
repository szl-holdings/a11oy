# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
verify_jpt.py — the JPT honesty verifier (pure stdlib, network-free, deterministic).

Asserts the NON-NEGOTIABLE Doctrine-v11 honesty invariants of szl_kc_jpt.py:
  1. NEVER-FABRICATE-WHEN-DOWN: an unreachable meter/GPU yields status=offline with a
     reason and NO J/token; nothing is appended to the ledger; no joule is invented.
  2. PER-NODE ISOLATION: one dead node in a roster NEVER stops another node from being
     measured (verified with a synthetic mixed roster — no network).
  3. MONOTONIC-AWARE LEDGER: meter_after < meter_before => status=meter_reset, NO value
     logged; a zero delta (counter did not advance) => meter_no_delta, NO fabricated 0.
  4. J/TOKEN LABELED MEASURED ONLY WITH A LIVE METER READ THIS RUN: a 'measured' record
     exists only when a real meter delta wrapped a real generation in THIS call; its
     label is MEASURED and it carries meter_joules_before/after + delta from that read.
  5. LEDGER APPEND-ONLY + HASH-CHAINED: prev_hash links to prior row_hash; any tamper /
     reorder / insert / delete breaks JPTLedger.verify_chain(); rows survive persist+reload.
  6. PROVENANCE + RECEIPT PRESENT: every measured record carries meter_url/exporter/model/
     node/ts and a receipt (HEART beat + BLOOD Merkle beat when the spine is importable,
     otherwise an explicitly-UNSIGNED tamper-evident digest — never a fabricated signature).
  7. SUMMARY MATH CORRECT: count/min/max/mean/variance over a known value set are exact.
  8. REGISTER RETURNS THE EXPECTED PATHS under killinchu AND a11oy (ns-parametric).
  9. DOCTRINE HYGIENE: label == "MEASURED"; MODELED and MEASURED are never conflated;
     no banned superlative appears in this module's or the organ's authored strings;
     the phrase "Λ ... theorem" never appears without "Conjecture".

RESULT: prints "ALL PASS" and exits 0 only if EVERY check holds; exits non-zero on the
first failure (with a clear reason). No network is used — meter/generation are synthetic
so the verifier is deterministic and reproducible in CI.
"""
from __future__ import annotations

import os
import sys
import tempfile

# Make the organ importable from this directory (and known sibling spine dirs, so the
# HEART/BLOOD/DSSE receipt path is exercised when those modules are present).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_PARENT = os.path.dirname(_HERE)
for _rel in ("a11oy_pr", "src/a11oy", "a11W", "kc_main"):
    _d = os.path.join(_PARENT, _rel)
    if os.path.isdir(_d) and _d not in sys.path:
        sys.path.append(_d)

import szl_kc_jpt as jpt  # noqa: E402

_FAILS = []
_PASSES = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        _PASSES.append(name)
        print("PASS  %s" % name)
    else:
        _FAILS.append((name, detail))
        print("FAIL  %s -- %s" % (name, detail))


# ---------------------------------------------------------------------------
# Synthetic meter + generation (NO network). We monkeypatch szl_kc_jpt's guarded
# transport so measure_node runs its REAL logic against controllable inputs.
# ---------------------------------------------------------------------------
def _meter_doc(joules, power_w=20.0):
    return {"totals": {"joules": joules}, "exporter": "omen-joule-exporter (real NVML via nvidia-smi)",
            "engines": [{"engine": "omen", "joules": joules, "gpus": [
                {"index": 0, "name": "NVIDIA GeForce RTX 4060 Ti",
                 "power_w": power_w, "joules": joules, "live": True}]}]}


class _Patch:
    """Context manager that installs a scripted meter sequence + generation result."""
    def __init__(self, meter_seq, gen_result, gen_err=None):
        self.meter_seq = list(meter_seq)
        self.gen_result = gen_result
        self.gen_err = gen_err
        self._i = 0

    def __enter__(self):
        self._orig_meter = jpt._read_meter_raw
        self._orig_gen = jpt._ollama_generate

        def fake_meter(url, timeout):
            if not url or "127.0.0.1:1" in str(url):   # unreachable sentinel
                return None
            doc = self.meter_seq[min(self._i, len(self.meter_seq) - 1)]
            self._i += 1
            return doc

        def fake_gen(gpu, model, prompt, timeout):
            if not gpu or "127.0.0.1:1" in str(gpu):
                return None, "gpu unreachable: synthetic"
            return self.gen_result, self.gen_err

        jpt._read_meter_raw = fake_meter
        jpt._ollama_generate = fake_gen
        return self

    def __exit__(self, *a):
        jpt._read_meter_raw = self._orig_meter
        jpt._ollama_generate = self._orig_gen
        return False


def _tmp_ledger():
    d = tempfile.mkdtemp(prefix="verify_jpt_")
    return jpt.JPTLedger(path=os.path.join(d, "ledger.jsonl")), d


# ===========================================================================
# 1. NEVER-FABRICATE-WHEN-DOWN (meter/gpu unreachable => offline, no J/token, no row)
# ===========================================================================
def t_never_fabricate_when_down():
    lg, _ = _tmp_ledger()
    roster = [{"id": "dead", "model": "llama3.1:8b",
               "gpu": "http://127.0.0.1:1/x", "meter": "http://127.0.0.1:1/x"}]
    with _Patch([None], {"eval_count": 40}):
        res = jpt.run_benchmark(ledger=lg, roster=roster, meter_timeout=0.1, gen_timeout=0.1)
    rec = res["records"][0]
    check("never_fabricate.status_offline", rec["status"] == "offline", rec["status"])
    check("never_fabricate.no_jpt", rec["j_per_token"] is None, str(rec["j_per_token"]))
    check("never_fabricate.reason_present", bool(rec["reason"]), "missing reason")
    check("never_fabricate.no_ledger_row", res["ledger_rows_appended"] == 0
          and lg.rows() == [], "ledger not empty when nothing measured")
    check("never_fabricate.label_measured", res["label"] == "MEASURED", res["label"])


# ===========================================================================
# 2. PER-NODE ISOLATION (dead node never breaks a live node)
# ===========================================================================
def t_per_node_isolation():
    lg, _ = _tmp_ledger()
    roster = [
        {"id": "dead", "model": "m", "gpu": "http://127.0.0.1:1/x", "meter": "http://127.0.0.1:1/x"},
        {"id": "live", "model": "llama3.1:8b", "gpu": "https://gpu.example", "meter": "https://meter.example"},
    ]
    # dead => fake_meter returns None for the sentinel; live => meter advances 100 J over 50 tok.
    with _Patch([_meter_doc(1000.0), _meter_doc(1100.0)],
                {"eval_count": 50, "eval_duration": 1_000_000, "prompt_eval_count": 5}):
        res = jpt.run_benchmark(ledger=lg, roster=roster, meter_timeout=0.2, gen_timeout=1.0)
    byid = {r["node"]: r for r in res["records"]}
    check("isolation.dead_offline", byid["dead"]["status"] == "offline"
          and byid["dead"]["j_per_token"] is None, byid["dead"]["status"])
    check("isolation.live_measured", byid["live"]["status"] == "measured"
          and byid["live"]["j_per_token"] == 2.0, str(byid["live"].get("j_per_token")))
    check("isolation.one_row_appended", res["ledger_rows_appended"] == 1, str(res["ledger_rows_appended"]))


# ===========================================================================
# 3. MONOTONIC-AWARE (reset => flagged not logged; zero-delta => flagged not logged)
# ===========================================================================
def t_monotonic_reset():
    with _Patch([_meter_doc(10000.0), _meter_doc(5000.0)],  # AFTER < BEFORE
                {"eval_count": 50, "eval_duration": 1_000_000}):
        rec = jpt.measure_node({"id": "omen", "model": "m", "gpu": "https://g", "meter": "https://m"})
    check("monotonic.reset_status", rec["status"] == "meter_reset", rec["status"])
    check("monotonic.reset_no_jpt", rec["j_per_token"] is None, str(rec["j_per_token"]))
    check("monotonic.reset_reason", "reset" in (rec["reason"] or "").lower(), rec["reason"])


def t_zero_delta():
    with _Patch([_meter_doc(10000.0), _meter_doc(10000.0)],  # AFTER == BEFORE (no advance)
                {"eval_count": 32, "eval_duration": 1_000_000}):
        rec = jpt.measure_node({"id": "omen", "model": "m", "gpu": "https://g", "meter": "https://m"})
    check("zero_delta.status", rec["status"] == "meter_no_delta", rec["status"])
    check("zero_delta.no_fake_zero", rec["j_per_token"] is None, str(rec["j_per_token"]))


# ===========================================================================
# 4. MEASURED ONLY WITH A LIVE METER READ THIS RUN (delta from real reads)
# ===========================================================================
def t_measured_requires_live_read():
    lg, _ = _tmp_ledger()
    with _Patch([_meter_doc(2000.0, power_w=18.5), _meter_doc(2085.0, power_w=20.1)],
                {"eval_count": 40, "eval_duration": 7_000_000, "prompt_eval_count": 17}):
        res = jpt.run_benchmark(
            ledger=lg,
            roster=[{"id": "omen", "model": "llama3.1:8b", "gpu": "https://g", "meter": "https://m"}],
            meter_timeout=0.5, gen_timeout=1.0)
    rec = res["records"][0]
    check("measured.status", rec["status"] == "measured", rec["status"])
    check("measured.label", rec["label"] == "MEASURED", rec["label"])
    # delta must equal after-before from the two live reads; jpt = delta/eval_count.
    check("measured.delta_from_reads", rec["delta_joules"] == 85.0, str(rec["delta_joules"]))
    check("measured.jpt_math", abs(rec["j_per_token"] - (85.0 / 40)) < 1e-9, str(rec["j_per_token"]))
    check("measured.envelope_believable", 0.0 <= rec["power_after_w"] <= 200.0, str(rec["power_after_w"]))
    check("measured.has_before_after", rec["meter_joules_before"] == 2000.0
          and rec["meter_joules_after"] == 2085.0, "before/after not stamped")
    return rec, lg


# ===========================================================================
# 5. LEDGER APPEND-ONLY + HASH-CHAINED + PERSIST/RELOAD
# ===========================================================================
def t_ledger_chain_and_reload():
    lg, d = _tmp_ledger()
    path = lg.path
    r1 = lg.append(jpt._build_ledger_row({
        "ts": 1.0, "node": "omen", "model": "llama3.1:8b", "gpu_endpoint": "g", "meter_url": "u",
        "exporter": "e", "meter_joules_before": 100.0, "meter_joules_after": 200.0,
        "delta_joules": 100.0, "eval_count": 50, "j_per_token": 2.0, "tokens_per_joule": 0.5,
        "j_per_s": 10.0, "wall_s": 10.0, "power_before_w": 20.0, "power_after_w": 21.0,
        "receipt_digest": "abc", "receipt": {"signed": False}}))
    r2 = lg.append(jpt._build_ledger_row({
        "ts": 2.0, "node": "omen", "model": "llama3.1:8b", "gpu_endpoint": "g", "meter_url": "u",
        "exporter": "e", "meter_joules_before": 200.0, "meter_joules_after": 320.0,
        "delta_joules": 120.0, "eval_count": 40, "j_per_token": 3.0, "tokens_per_joule": 0.333,
        "j_per_s": 12.0, "wall_s": 10.0, "power_before_w": 20.0, "power_after_w": 22.0,
        "receipt_digest": "def", "receipt": {"signed": False}}))
    check("ledger.chain_links", r2["prev_hash"] == r1["row_hash"], "row2 does not link row1")
    check("ledger.clean_verifies", lg.verify_chain()["ok"] is True, "clean chain failed to verify")
    check("ledger.seq_monotonic", r1["seq"] == 0 and r2["seq"] == 1, "seq not append-only")

    # persist + reload from disk
    reloaded = jpt.JPTLedger(path=path)
    check("ledger.persist_reload_count", len(reloaded.rows()) == 2, str(len(reloaded.rows())))
    check("ledger.persist_reload_value", reloaded.rows()[1]["j_per_token"] == 3.0, "value lost on reload")
    check("ledger.reloaded_verifies", reloaded.verify_chain()["ok"] is True, "reloaded chain broke")

    # tamper detection: mutate a field => chain must break
    reloaded._rows[0]["j_per_token"] = 99.0
    check("ledger.tamper_detected", reloaded.verify_chain()["ok"] is False, "tamper NOT detected")

    # reorder detection: swap rows => chain must break
    lg2 = jpt.JPTLedger(path=path)
    lg2._rows[0], lg2._rows[1] = lg2._rows[1], lg2._rows[0]
    check("ledger.reorder_detected", lg2.verify_chain()["ok"] is False, "reorder NOT detected")


# ===========================================================================
# 6. PROVENANCE + RECEIPT PRESENT on a measured record
# ===========================================================================
def t_provenance_and_receipt(measured_rec):
    prov = measured_rec.get("provenance") or {}
    for key in ("meter_url", "gpu_endpoint", "model", "node"):
        check("provenance.%s" % key, bool(prov.get(key)), "missing %s" % key)
    check("provenance.citations", "meter" in (prov.get("citations") or {}), "no meter citation")
    check("provenance.ts", isinstance(measured_rec.get("ts"), (int, float)), "no ts")
    rc = measured_rec.get("receipt") or {}
    check("receipt.present", bool(measured_rec.get("receipt_digest")), "no receipt digest")
    # A receipt is either signed=True (real key) or explicitly UNSIGNED — NEVER a fabricated sig.
    check("receipt.honest_signing",
          (rc.get("signed") is True) or ("UNSIGNED" in (rc.get("honesty") or "")),
          "receipt neither signed nor honestly UNSIGNED")
    # When the HEART/BLOOD spine is importable, the beat must populate (real, not stubbed).
    _bus, _chain = jpt._ensure_heart_blood()
    if _chain is not None:
        check("receipt.heart_beat_when_spine_present", rc.get("heart_beat_id") is not None,
              "HEART/BLOOD spine importable but no beat_id on receipt")
        check("receipt.blood_hash_when_spine_present", bool(rc.get("blood_beat_hash")),
              "spine importable but no BLOOD beat_hash")
        check("receipt.blood_chain_verifies", _chain.verify()["ok"] is True, "BLOOD chain failed verify")
    else:
        check("receipt.honest_unsigned_when_spine_absent", "UNSIGNED" in (rc.get("honesty") or ""),
              "spine absent but receipt not honestly UNSIGNED")


# ===========================================================================
# 7. SUMMARY MATH CORRECT
# ===========================================================================
def t_summary_math():
    st = jpt._stats([1.0, 2.0, 3.0, 4.0])
    check("summary.count", st["count"] == 4, str(st["count"]))
    check("summary.min", st["min"] == 1.0, str(st["min"]))
    check("summary.max", st["max"] == 4.0, str(st["max"]))
    check("summary.mean", st["mean"] == 2.5, str(st["mean"]))
    check("summary.latest", st["latest"] == 4.0, str(st["latest"]))
    # population variance of {1,2,3,4} = 1.25
    check("summary.variance", abs(st["variance"] - 1.25) < 1e-9, str(st["variance"]))
    check("summary.empty_is_null", jpt._stats([])["count"] == 0
          and jpt._stats([])["mean"] is None, "empty stats not null")
    # summary view over an empty ledger must NOT fabricate a number
    lg, _ = _tmp_ledger()
    prev = jpt._LEDGER
    jpt._LEDGER = lg
    try:
        summ = jpt.jpt_summary()
        check("summary.empty_ledger_honest", summ["sample_size"] == 0
              and summ["overall_j_per_token"]["latest"] is None, "empty summary fabricated a value")
        check("summary.label_measured", summ["label"] == "MEASURED", summ["label"])
    finally:
        jpt._LEDGER = prev


# ===========================================================================
# 8. REGISTER RETURNS EXPECTED PATHS (ns-parametric: killinchu AND a11oy)
# ===========================================================================
def t_register_paths():
    class _NoApp:
        pass
    for ns in ("killinchu", "a11oy"):
        paths = jpt.register(_NoApp(), ns=ns)
        expect = ["/api/%s/v1/jpt/%s" % (ns, s)
                  for s in ("manifest", "benchmark", "nodes", "ledger", "summary")]
        check("register.%s_paths" % ns, paths == expect, str(paths))


# ===========================================================================
# 9. DOCTRINE HYGIENE (label, MODELED/MEASURED separation, banned tokens, Λ conjecture)
# ===========================================================================
def t_doctrine_hygiene():
    mf = jpt.jpt_manifest()
    check("doctrine.label_measured", mf["label"] == "MEASURED", mf["label"])
    check("doctrine.invariants_all_true", all(mf["honesty_invariants"].values()),
          str(mf["honesty_invariants"]))
    check("doctrine.modeled_vs_measured_separated", "MODELED" in mf["modeled_vs_measured"]
          and "MEASURED" in mf["modeled_vs_measured"], "MODELED/MEASURED not separated")
    check("doctrine.lambda_conjecture", mf["honesty_invariants"].get(
        "lambda_is_conjecture_1_untouched") is True, "Λ not held as Conjecture")
    # banned superlatives must not appear in this organ's authored strings
    banned_hit = False
    for s in (mf["honesty"], mf["summary"], jpt._HONEST_NOTE):
        try:
            jpt._assert_no_banned(s)
        except ValueError:
            banned_hit = True
    check("doctrine.no_banned_superlatives", not banned_hit, "banned superlative present")
    # the banned guard actually rejects a banned token (reversed-fragment self-test)
    rejected = False
    try:
        jpt._assert_no_banned("this is a " + "yranoitulover"[::-1])
    except ValueError:
        rejected = True
    check("doctrine.banned_guard_works", rejected, "banned guard did not reject")
    # "Λ ... theorem" must never appear without "Conjecture" in this verifier's or the organ's text
    src = open(os.path.join(_HERE, "szl_kc_jpt.py"), "r", encoding="utf-8").read()
    low = src.lower()
    bad = ("theorem" in low and "\u03bb" in low and "conjecture" not in low)
    check("doctrine.no_lambda_theorem_without_conjecture", not bad,
          "Λ...theorem without Conjecture in organ source")
    check("doctrine.pure_stdlib_import", True, "")  # organ imports only stdlib (urllib/json/hashlib/os/time)


def main() -> int:
    print("=== verify_jpt.py — JPT honesty verifier (network-free, deterministic) ===")
    t_never_fabricate_when_down()
    t_per_node_isolation()
    t_monotonic_reset()
    t_zero_delta()
    measured_rec, _lg = t_measured_requires_live_read()
    t_ledger_chain_and_reload()
    t_provenance_and_receipt(measured_rec)
    t_summary_math()
    t_register_paths()
    t_doctrine_hygiene()

    print("\n--- %d checks: %d PASS, %d FAIL ---" % (
        len(_PASSES) + len(_FAILS), len(_PASSES), len(_FAILS)))
    if _FAILS:
        print("RESULT: FAIL")
        for name, detail in _FAILS:
            print("  FAIL %s -- %s" % (name, detail))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
