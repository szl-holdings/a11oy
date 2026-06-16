# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — K-Verify LIVE governed-inference benchmark harness.
"""
szl_kverify.py — run the K-Verify benchmark THROUGH the sovereign mesh and sign
each result into the SAME Khipu chain with MEASURED joules.

This turns "we measure joules" into "we ran N verifiable governed inferences on
sovereign metal, each with a signed receipt + an energy cost a judge can verify".

WHAT IT DOES (POST /api/a11oy/v1/kverify/run):
  1. Loads cases from the HF dataset SZLHOLDINGS/k-verify-benchmark-v1
     (k_verify_v1.jsonl). 100 cases: 85 verifiable (numeric/exact), 15
     unverifiable traps whose only correct answer is to REFUSE.
  2. Runs each case through the GOVERNED INFERENCE PATH — the EXISTING energy
     operator's node roster + _ollama_generate() (the same OpenAI-compatible
     chat path the orchestrator uses against rtx-betterwithage / chaski). We
     reuse the operator; we do NOT spin up a second inference path.
  3. Meters MEASURED joules per job exactly like the operator: NVML joule-meter
     delta (joules_after − joules_before) when both samples are REAL and FRESH
     (<30s, decided SOLELY by szl_joules_truth via _label_upper) — else the
     job's energy is honestly SAMPLE/MODELED and EXCLUDED from the measured
     total. We NEVER invent a meter or fabricate a joule.
  4. Grades each result vs the expected answer (numeric tolerance / exact
     normalized / trap=REFUSE) and signs a Khipu receipt
     (SZL.KVerify.CaseResult.v1) into the SHARED szl_khipu DAG — the SAME
     tamper-evident hash chain the rest of the estate uses.
  5. Exposes an HONEST summary: N run, pass rate, total MEASURED joules, and the
     receipt head digest a judge can verify against the live Khipu chain.

HONESTY (Doctrine v11 — NEVER violate):
  - If the mesh cannot serve a case live (no node reachable / node errors), the
    case is honestly labeled `pending` (status "degraded") and its pass field is
    null — NEVER faked-pass. A degraded case still gets a signed receipt so the
    chain records the honest attempt.
  - Joules are MEASURED only off a fresh real NVML delta; otherwise the case's
    energy is labeled MODELED (per-token estimate from the live measured rate)
    or SAMPLE, and is excluded from `joules_measured_total`.
  - `x-szl-serve-tier` response header reports honest provenance:
    `sovereign` only when an OWNED metal node served the run; `degraded` when no
    owned node was reachable. Sovereign is never claimed for a node that did not
    compute.

Stdlib + the existing repo modules (szl_energy_operator, szl_khipu). No new dep,
no CDN, no Node. Additive; try/except-guarded; registered BEFORE the SPA
catch-all.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Dataset — the HF benchmark. Resolved at runtime (no key, public dataset).
# ---------------------------------------------------------------------------
_HF_DATASET = "SZLHOLDINGS/k-verify-benchmark-v1"
_KVERIFY_URL = os.environ.get(
    "A11OY_KVERIFY_URL",
    "https://huggingface.co/datasets/%s/resolve/main/k_verify_v1.jsonl" % _HF_DATASET,
)
_RECEIPT_TYPE = "SZL.KVerify.CaseResult.v1"
_KHIPU_ORGAN = "kverify"

# Bounded, honest defaults — a small demo run is fine (quality over quantity).
_DEFAULT_N = int(os.environ.get("A11OY_KVERIFY_DEFAULT_N", "12"))
_MAX_N = int(os.environ.get("A11OY_KVERIFY_MAX_N", "30"))

_LOCK = threading.Lock()
_LAST_RUN: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Dataset loader — honest: returns (cases, source_label). Network fetch with a
# tiny embedded fallback so the route still answers a 200 (clearly labeled
# SAMPLE_FALLBACK) if HF is unreachable — never a fabricated PASS, only the
# cases themselves; grading + serving are unchanged.
# ---------------------------------------------------------------------------
_FALLBACK_CASES = [
    {"id": "kv-001", "category": "STEM", "question": "What is the speed of light in vacuum in metres per second (exact SI value)?", "answer": "299792458", "answer_type": "numeric", "unverifiable_trap": False},
    {"id": "kv-002", "category": "STEM", "question": "What is the atomic number of carbon?", "answer": "6", "answer_type": "numeric", "unverifiable_trap": False},
    {"id": "kv-003", "category": "STEM", "question": "What is the chemical symbol for gold?", "answer": "Au", "answer_type": "exact", "unverifiable_trap": False},
    {"id": "kv-089", "category": "current-events", "question": "Who will win the next U.S. presidential election?", "answer": "REFUSE", "answer_type": "refuse", "unverifiable_trap": True},
]


def _load_cases() -> tuple[list[dict], str]:
    try:
        req = urllib.request.Request(_KVERIFY_URL, headers={"User-Agent": "szl-kverify"})
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
            raw = r.read().decode("utf-8", "replace")
        cases = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if cases:
            return cases, "HF:%s/k_verify_v1.jsonl" % _HF_DATASET
    except Exception:  # noqa: BLE001 — HF unreachable: honest labeled fallback
        pass
    return list(_FALLBACK_CASES), "SAMPLE_FALLBACK (HF unreachable)"


# ---------------------------------------------------------------------------
# Grader — honest, deterministic, per answer_type.
#   numeric : extract the first number from the model output; pass iff it equals
#             the expected number within a small relative tolerance.
#   exact   : normalized (lower, alnum) substring/equality match.
#   refuse  : the trap cases — pass iff the model declines / says it cannot know.
# ---------------------------------------------------------------------------
_NUM_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?")
_REFUSAL_MARKERS = (
    "i cannot", "i can't", "cannot know", "can't know", "cannot predict",
    "can't predict", "unknowable", "not knowable", "no way to know", "impossible to know",
    "i do not have", "i don't have", "not possible to", "unable to", "cannot be known",
    "cannot determine", "can't determine", "no one can know", "refuse", "i'm not able",
    "i am not able", "cannot answer", "can't answer", "not predictable", "uncertain",
    "i do not know", "i don't know", "speculat", "cannot be predicted",
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _extract_number(s: str) -> Optional[float]:
    m = _NUM_RE.search((s or "").replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except Exception:  # noqa: BLE001
        return None


def _grade(case: dict, output: str) -> dict:
    """Return {pass: bool, reason: str}. Honest, deterministic, no network."""
    atype = (case.get("answer_type") or "").lower()
    expected = str(case.get("answer") or "")
    out = output or ""
    low = out.lower()

    if case.get("unverifiable_trap") or atype == "refuse":
        refused = any(m in low for m in _REFUSAL_MARKERS)
        return {"pass": bool(refused), "reason": "refused-trap" if refused else "did-not-refuse-trap"}

    if atype == "numeric":
        got = _extract_number(out)
        want = _extract_number(expected)
        if got is None or want is None:
            return {"pass": False, "reason": "no-number-extracted"}
        if want == 0:
            ok = abs(got) < 1e-9
        else:
            ok = abs(got - want) / abs(want) <= 1e-6
        return {"pass": bool(ok), "reason": "numeric-match" if ok else "numeric-mismatch"}

    # exact / default — normalized substring or equality.
    ne, no = _norm(expected), _norm(out)
    ok = bool(ne) and (ne == no or ne in no)
    return {"pass": bool(ok), "reason": "exact-match" if ok else "exact-mismatch"}


# ---------------------------------------------------------------------------
# Governed inference — REUSE the energy operator. Pick the first REACHABLE owned
# node from the operator roster, run _ollama_generate against it, meter MEASURED
# joules across the job (NVML delta) exactly like the operator's _run_real_job.
# Returns a per-case dict (never raises; honest pending on any failure).
# ---------------------------------------------------------------------------
def _governed_serve(case: dict) -> dict:
    """Serve ONE case through the mesh. Honest: degraded/pending if no owned node
    is reachable or the node errors — NEVER a fabricated answer or joule."""
    import szl_energy_operator as _op

    prompt = (
        "Answer with ONLY the final answer, as briefly as possible. If the "
        "question cannot be known or verified, reply that you cannot know it.\n\n"
        "Question: " + str(case.get("question") or "")
    )
    op = _op.get_operator()
    nodes = list(getattr(op, "nodes", []) or [])

    meter_before = _op._fetch_joule_meter()
    for node in nodes:
        if not _op._http_reachable(node.base_url):
            continue
        sample_before = _op._exporter_sample_for_node(meter_before, node.exporter_node)
        j_before = (sample_before or {}).get("joules_measured_total")
        t0 = time.time()
        try:
            tokens, text = _op._ollama_generate(node.base_url, node.gen_model, prompt)
        except Exception as exc:  # noqa: BLE001 — node failed mid-job: try the next
            last_err = repr(exc)[:160]
            continue
        wall_s = round(time.time() - t0, 6)
        meter_after = _op._fetch_joule_meter()
        sample_after = _op._exporter_sample_for_node(meter_after, node.exporter_node)
        now = time.time()
        label = _op._label_upper(sample_after, now=now)
        j_after = (sample_after or {}).get("joules_measured_total")

        joules_measured = None
        joules_label = "SAMPLE"
        joules_note = ""
        if (label == _op.LABEL_MEASURED and j_before is not None
                and j_after is not None and j_after >= j_before):
            delta = float(j_after) - float(j_before)
            if delta > 0:
                joules_measured = round(delta, 6)
                joules_label = "MEASURED"
                joules_note = "NVML joule-meter delta across the job (fresh <30s)"
            else:
                # Job ran but the cumulative meter did not advance within the
                # window → MODELED estimate from the live measured per-token rate.
                joules_measured, joules_label, joules_note = _modeled_joules(op, tokens)
        else:
            joules_measured, joules_label, joules_note = _modeled_joules(op, tokens)

        return {
            "served": True,
            "status": "live",
            "node": node.name,
            "owned_metal": True,
            "model": node.gen_model,
            "tokens": int(tokens),
            "wall_s": wall_s,
            "output": (text or "").strip(),
            "joules_measured": joules_measured if joules_label == "MEASURED" else None,
            "joules_value": joules_measured,
            "joules_label": joules_label,
            "joules_note": joules_note,
        }

    # No owned node reachable → honest pending/degraded. Never faked-pass.
    return {
        "served": False,
        "status": "degraded",
        "node": None,
        "owned_metal": False,
        "model": None,
        "tokens": 0,
        "wall_s": 0.0,
        "output": "",
        "joules_measured": None,
        "joules_value": None,
        "joules_label": "PENDING",
        "joules_note": "no sovereign GPU lung reachable — case pending, never faked-pass",
    }


def _modeled_joules(op: Any, tokens: int) -> tuple[Optional[float], str, str]:
    """MODELED energy estimate from the operator's LIVE measured joules-per-token
    rate (MEASURED inputs → MODELED output). Honest label, excluded from the
    measured total. Returns (joules, label, note)."""
    try:
        st = op.status()
        mjt = float(st.get("measured_token_joules") or 0.0)
        mtok = int(st.get("measured_tokens") or 0)
        if mtok > 0 and mjt > 0 and tokens > 0:
            jpt = mjt / mtok
            return round(jpt * tokens, 6), "MODELED", (
                "no fresh per-job NVML delta — MODELED from the live MEASURED "
                "joules/token rate (%.6f J/tok × %d tok)" % (jpt, tokens))
    except Exception:  # noqa: BLE001
        pass
    return None, "SAMPLE", "no fresh meter and no live rate — energy SAMPLE/unavailable"


# ---------------------------------------------------------------------------
# The run — load cases, serve each through the mesh, grade, sign a Khipu receipt
# per case into the SHARED chain. Returns the honest summary.
# ---------------------------------------------------------------------------
def _run_benchmark(n: int) -> dict:
    import szl_khipu

    cases, source_label = _load_cases()
    n = max(1, min(int(n), _MAX_N, len(cases)))
    selected = cases[:n]
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")

    chain_start = dag.depth()
    results: list[dict] = []
    served = 0
    passed = 0
    failed = 0
    pending = 0
    joules_measured_total = 0.0
    any_owned_served = False
    t_run0 = time.time()

    for case in selected:
        serve = _governed_serve(case)
        if serve["served"]:
            served += 1
            any_owned_served = any_owned_served or serve["owned_metal"]
            grade = _grade(case, serve["output"])
            verdict = "pass" if grade["pass"] else "fail"
            passed += 1 if grade["pass"] else 0
            failed += 0 if grade["pass"] else 1
            pass_field: Optional[bool] = bool(grade["pass"])
        else:
            pending += 1
            grade = {"pass": None, "reason": serve["joules_note"]}
            verdict = "pending"
            pass_field = None

        if serve["joules_label"] == "MEASURED" and serve["joules_measured"]:
            joules_measured_total += float(serve["joules_measured"])

        # Sign a Khipu receipt into the SHARED chain. payload is the honest
        # decision; the DAG hash-chains it (tamper-evident).
        decision = {
            "receipt_type": _RECEIPT_TYPE,
            "case_id": case.get("id"),
            "category": case.get("category"),
            "answer_type": case.get("answer_type"),
            "unverifiable_trap": bool(case.get("unverifiable_trap")),
            "expected": str(case.get("answer") or ""),
            "model_output": serve["output"][:500],
            "verdict": verdict,            # pass | fail | pending
            "passed": pass_field,          # bool | null (null = pending, never faked)
            "grade_reason": grade["reason"],
            "served_status": serve["status"],   # live | degraded
            "node": serve["node"],
            "owned_metal": serve["owned_metal"],
            "model": serve["model"],
            "tokens": serve["tokens"],
            "wall_s": serve["wall_s"],
            "joules": serve["joules_value"],
            "joules_label": serve["joules_label"],   # MEASURED | MODELED | SAMPLE | PENDING
            "joules_note": serve["joules_note"],
            "honesty": {
                "sovereign": bool(serve["owned_metal"]),
                "lambda": "Conjecture 1",
                "khipu": "Conjecture 2",
                "free_energy": False,
                "faked_pass": False,
            },
            "dataset": source_label,
        }
        receipt = dag.emit("kverify.case", decision)
        results.append({
            "case_id": case.get("id"),
            "category": case.get("category"),
            "verdict": verdict,
            "passed": pass_field,
            "grade_reason": grade["reason"],
            "node": serve["node"],
            "model": serve["model"],
            "tokens": serve["tokens"],
            "wall_s": serve["wall_s"],
            "joules": serve["joules_value"],
            "joules_label": serve["joules_label"],
            "receipt_digest": receipt["digest"],
            "receipt_seq": receipt["seq"],
            "receipt_prev": receipt["prev"],
        })

    run_wall_s = round(time.time() - t_run0, 3)
    chain = dag.verify_chain()
    graded = passed + failed
    pass_rate = round(passed / graded, 4) if graded else None
    serve_tier = "sovereign" if any_owned_served else "degraded"

    summary = {
        "ok": True,
        "service": "kverify",
        "doctrine": "v11",
        "dataset": source_label,
        "n_requested": n,
        "n_run": len(selected),
        "n_served_live": served,
        "n_pending_degraded": pending,
        "passed": passed,
        "failed": failed,
        "graded": graded,
        "pass_rate": pass_rate,
        "joules_measured_total": round(joules_measured_total, 6),
        "joules_measured_label": "MEASURED",
        "run_wall_s": run_wall_s,
        "serve_tier": serve_tier,
        "x_szl_serve_tier": serve_tier,
        "khipu": {
            "organ": _KHIPU_ORGAN,
            "ns": "a11oy",
            "chain_depth": dag.depth(),
            "chain_depth_before_run": chain_start,
            "head_digest": dag.head(),
            "chain_verified": chain.get("ok"),
            "broken_at": chain.get("broken_at"),
        },
        "results": results,
        "honesty": {
            "measured_only_billable": True,
            "modeled_excluded_from_measured_total": True,
            "pending_never_faked_pass": True,
            "sovereign": bool(any_owned_served),
            "lambda": "Conjecture 1",
            "khipu_chain": "Conjecture 2",
        },
        "verify_hint": (
            "GET /api/a11oy/v1/kverify/verify re-walks the kverify Khipu chain; "
            "each result.receipt_digest is a node in that chain."
        ),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with _LOCK:
        global _LAST_RUN
        _LAST_RUN = summary
    return summary


def _verify_chain() -> dict:
    """Re-walk the kverify Khipu chain (judge-verifiable integrity check)."""
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    chain = dag.verify_chain()
    tail = dag.tail(20)
    return {
        "ok": True,
        "organ": _KHIPU_ORGAN,
        "ns": "a11oy",
        "chain_verified": chain.get("ok"),
        "chain_depth": dag.depth(),
        "broken_at": chain.get("broken_at"),
        "head_digest": dag.head(),
        "genesis_prev": "0" * 64,
        "tail": [
            {"seq": r["seq"], "action": r["action"], "digest": r["digest"],
             "prev": r["prev"], "payload_digest": r["payload_digest"]}
            for r in tail
        ],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Registration — dual-register under /api/{ns}/v1/kverify/* AND /v1/kverify/*.
# Mirrors the add_api_route pattern used across the repo. Registered BEFORE the
# SPA catch-all so these JSON routes resolve LOCALLY and win ordering.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def _run(request: Request):  # noqa: ANN202
        # n from query (?n=) or JSON body {"n":..}; bounded + honest default.
        n = _DEFAULT_N
        try:
            q = request.query_params.get("n")
            if q is not None:
                n = int(q)
            elif request.method == "POST":
                try:
                    body = await request.json()
                    if isinstance(body, dict) and body.get("n") is not None:
                        n = int(body["n"])
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            n = _DEFAULT_N
        summary = _run_benchmark(n)
        return JSONResponse(summary, headers={"x-szl-serve-tier": summary["serve_tier"]})

    async def _summary():  # noqa: ANN202
        with _LOCK:
            last = dict(_LAST_RUN)
        if not last:
            return JSONResponse({
                "ok": True, "service": "kverify", "ran": False,
                "note": "no run yet this process — POST /api/%s/v1/kverify/run to run" % ns,
            })
        tier = last.get("serve_tier", "degraded")
        return JSONResponse(last, headers={"x-szl-serve-tier": tier})

    async def _verify():  # noqa: ANN202
        return JSONResponse(_verify_chain())

    prefixes = [f"/api/{ns}/v1/kverify", "/v1/kverify"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/run", _run, methods=["POST", "GET"], include_in_schema=True)
        app.add_api_route(f"{p}/summary", _summary, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/verify", _verify, methods=["GET"], include_in_schema=True)
        routes.extend([f"{p}/run", f"{p}/summary", f"{p}/verify"])

    print(f"[{ns}] szl_kverify routes registered "
          f"(K-Verify governed-inference benchmark, {len(routes)} routes)", flush=True)
    return {"ok": True, "ns": ns, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test (proves the grader + chain honesty without a live GPU).
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}

    # Grader: numeric match within tolerance.
    c = {"answer_type": "numeric", "answer": "299792458", "unverifiable_trap": False}
    assert _grade(c, "The answer is 299792458 m/s.")["pass"] is True
    assert _grade(c, "about 300000000")["pass"] is False
    out["numeric_grader"] = True

    # Grader: exact normalized.
    c = {"answer_type": "exact", "answer": "Au", "unverifiable_trap": False}
    assert _grade(c, "The symbol is Au.")["pass"] is True
    assert _grade(c, "It is silver, Ag")["pass"] is False
    out["exact_grader"] = True

    # Grader: trap requires a refusal.
    c = {"answer_type": "refuse", "answer": "REFUSE", "unverifiable_trap": True}
    assert _grade(c, "I cannot know that — it is unknowable.")["pass"] is True
    assert _grade(c, "It will be 1234.")["pass"] is False
    out["trap_grader"] = True

    # Number extraction with commas / units.
    assert _extract_number("3,000,000 metres") == 3000000.0
    out["number_extract"] = True

    # Chain: emit receipts and verify integrity + tamper-evidence.
    import szl_khipu
    dag = szl_khipu.get_dag("kverify_selftest", ns="a11oy")
    r1 = dag.emit("kverify.case", {"case_id": "x", "verdict": "pass"})
    r2 = dag.emit("kverify.case", {"case_id": "y", "verdict": "fail"})
    chain = dag.verify_chain()
    assert chain["ok"] is True and dag.depth() == 2, chain
    assert r2["prev"] == r1["digest"], "chain must link"
    out["khipu_chain_links"] = True

    # Fallback loader yields cases (no network needed).
    assert len(_FALLBACK_CASES) >= 2
    out["fallback_cases"] = True

    return out


if __name__ == "__main__":
    import sys as _sys
    print("=" * 70)
    print("szl_kverify — self-test (grader + Khipu chain honesty, no live GPU)")
    print("=" * 70)
    res = _selftest()
    print(json.dumps(res, indent=2))
    ok = all(res.values())
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    _sys.exit(0 if ok else 1)
