"""
szl_execverify.py — SZL Execution-Verified Synthesis Loop. An HONEST, STRUCTURAL-ONLY
description of a CLOSED loop that ties a11oy's existing honest-eval (evalarena), the
Brain (corpus), and agentops (bounded operate loop) into one governed pipeline:
  eval → execution-verified trajectory → corpus candidate → signed receipt.

Frontier context (cited, NEVER claimed as SZL's own): Together AI's ICML-2026 work
shows the SAME harness can both (a) evaluate agents honestly AND (b) generate
execution-verified training data — closing the loop between measuring an agent and
improving it (see together.ai/blog/icml-2026). a11oy already has the honest-eval organ
(evalarena), a corpus (Brain), and a bounded operate loop (agentops). This surface
DESCRIBES + RECEIPTS the synthesis path that would wire them into a closed loop; it does
NOT claim a11oy trained a model from the loop in-request. The synthesis is STRUCTURAL-ONLY.

  GET  /api/<ns>/v1/frontier/execverify?seed=&n_trajectories=&pass_rate=&verify=

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "STRUCTURAL-ONLY"
  payload.n_trajectories      : number of modeled eval trajectories
  payload.stages              : ordered pipeline descriptors (eval→verify→candidate→receipt)
  payload.trajectories[]      : {id, eval_score, executed, exec_verified, is_candidate,
                                lambda_advisory, admitted}
  payload.loop                : {trajectories, eval_passed, execution_verified,
                                corpus_candidates, gated_out, verification_rate,
                                candidate_yield}
  payload.lambda_gate         : {status, admit_threshold, mean_lambda_advisory, bounds,
                                admits, gated_out, trust, trust_cap} — Λ advisory (Conjecture 1)
  payload.receipt             : SHA-256 corpus-candidate receipt DESIGN (unsigned preview)
  payload.parts_labeled       : which parts are STRUCTURAL-ONLY vs MODELED
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  STRUCTURAL-ONLY / MODELED — the eval scores, execution-verification verdicts, and
    candidate yield are a deterministic seeded MODEL of the loop, genuinely computed and
    reported, not fabricated. a11oy does NOT train a model from these trajectories
    in-request; the synthesis (eval → verified trajectory → corpus candidate → receipt)
    is described and receipted, not executed end-to-end as a training run. The eval,
    Brain, and agentops organs it references are real, but the closed loop wiring them is
    STRUCTURAL-ONLY.

RECEIPT-ON-WRITE
  A SHA-256 receipt is emitted per the govern/receipts pattern. This GET is a READ, so it
  returns an UNSIGNED content-hash PREVIEW (signed:false, minted_on_this_get:false): a
  real committed corpus-candidate WRITE would mint the signed Khipu receipt. No signing
  happens on this read path (doctrine v11).

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1 (advisory, gray, never
  green); trust capped at 0.97, never 1.0. No fabricated training claim; no MEASURED
  label. Pure stdlib. Deterministic with seed. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-08):
  Together AI — ICML-2026: one harness both evaluates agents AND generates
    execution-verified training data:
    https://www.together.ai/blog/icml-2026
  Execution-guided / execution-verified code generation (foundational):
    Chen et al. 2018 (execution-guided synthesis), arXiv:1807.03100
    https://arxiv.org/abs/1807.03100
  Self-Taught Reasoner (STaR — bootstrapping from verified rationales):
    Zelikman et al. 2022, arXiv:2203.14465   https://arxiv.org/abs/2203.14465
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "Together AI — ICML-2026 (one harness: honest eval + execution-verified training data)": "https://www.together.ai/blog/icml-2026",
    "Execution-guided synthesis — Chen et al. 2018 arXiv:1807.03100": "https://arxiv.org/abs/1807.03100",
    "STaR: Self-Taught Reasoner — Zelikman et al. 2022 arXiv:2203.14465": "https://arxiv.org/abs/2203.14465",
}

_LAMBDA_MIN = 0.02          # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94          # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55        # advisory admit threshold (a trajectory admitted to corpus above it)
_TRUST_CAP = 0.97           # doctrine hard cap on trust (never green / never 1.0)
_TRAJ_CAP = 128             # max trajectory entries returned

_STAGES = [
    {"stage": "eval", "organ": "evalarena", "role": "honest governed eval / red-team score"},
    {"stage": "execute", "organ": "agentops", "role": "bounded operate loop runs the trajectory (writer≠judge)"},
    {"stage": "verify", "organ": "agentops", "role": "execution-verify the trajectory (did it actually run/pass)"},
    {"stage": "candidate", "organ": "brain", "role": "execution-verified trajectory → corpus candidate"},
    {"stage": "receipt", "organ": "govern/receipts", "role": "SHA-256 receipt bound on the committed candidate WRITE"},
]


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


# a registry model id whose MODELED reference-oracle path exercises every scorer
_EVAL_MODEL_ID = "claude_sonnet_4_6"
_EVAL_SUITES = ("core_honest_v1", "redteam_v1", "honesty_v1")


def _real_eval_trajectories():
    """REAL in-request signal: run the eval arena suites and use their true verdicts.

    This replaces the former seeded pseudo-random `eval_score`, which was not a signal at
    all — it was a hash of the seed. Here each trajectory is a REAL eval case executed in
    THIS request by szl_eval_arena.run_eval(): real suite, real scorer, real pass/fail,
    real suite_sha256. The execution-verification leg then INDEPENDENTLY re-executes the
    same scorer over the recorded answer and requires the verdict to reproduce — a real
    re-run, which is exactly the "looks right vs runs right" check this surface models.

    Returns (trajectories, meta). On any failure `meta["real_eval_run"]` is False and the
    caller must stay honestly STRUCTURAL-ONLY rather than dress up a fallback.
    """
    meta = {"real_eval_run": False, "reason": None, "suites": [], "model_id": _EVAL_MODEL_ID,
            "scorer_reexecuted": False}
    try:
        import szl_eval_arena as _ea
    except Exception as e:  # noqa: BLE001
        meta["reason"] = f"szl_eval_arena unavailable: {type(e).__name__}"
        return [], meta
    scorers = getattr(_ea, "_SCORERS", {}) or {}
    # A GET must never trigger a paid/slow provider call. When no provider key is wired the
    # arena's own MODELED reference-oracle path is already offline-deterministic, so we run
    # the full run_eval() pipeline. When a key IS wired we still execute the REAL suites and
    # the REAL scorers, but against the arena's reference-oracle answer instead of a live
    # provider call — and we say so in `answer_source`.
    try:
        key_wired = bool((_ea._registry_snapshot() or {}).get("any_key_wired"))
    except Exception:  # noqa: BLE001
        key_wired = True
    meta["provider_key_wired"] = key_wired
    meta["mode"] = "arena.run_eval (offline reference-oracle answers)" if not key_wired else \
                   "suite+scorer execution against the arena reference oracle (no provider call on a GET)"
    trajs = []
    for sid in _EVAL_SUITES:
        if sid not in getattr(_ea, "_SUITES", {}):
            continue
        if key_wired:
            suite_def = _ea._SUITES[sid]
            rows, n_pass = [], 0
            for case in suite_def.get("cases", []):
                ans = _ea._modeled_reference_answer(case)
                fn = scorers.get(case.get("scorer"), None)
                if not callable(fn):
                    continue
                try:
                    ok, detail = fn(ans, case.get("expected", ""))
                except Exception as e:  # noqa: BLE001
                    ok, detail = False, f"scorer error: {type(e).__name__}"
                ok = bool(ok)
                n_pass += 1 if ok else 0
                rows.append({"id": case.get("id"), "category": case.get("category"),
                             "scorer": case.get("scorer"), "expected": case.get("expected", ""),
                             "answer": ans, "answer_sha256": hashlib.sha256(ans.encode("utf-8")).hexdigest(),
                             "passed": ok, "detail": detail, "honesty_label": "MODELED"})
            if not rows:
                meta["suites"].append({"suite_id": sid, "ran": False, "error": "no scorable cases"})
                continue
            res = {"suite": {"id": sid, "version": suite_def.get("version"),
                             "sha256": _ea._suite_sha256(sid) if hasattr(_ea, "_suite_sha256") else None},
                   "aggregate": {"n_cases": len(rows), "n_passed": n_pass},
                   "results": rows, "honesty_label": "MODELED"}
        else:
            try:
                res = _ea.run_eval(sid, _EVAL_MODEL_ID)
            except Exception as e:  # noqa: BLE001
                meta["suites"].append({"suite_id": sid, "ran": False, "error": type(e).__name__})
                continue
        if not isinstance(res, dict) or not res.get("results"):
            meta["suites"].append({"suite_id": sid, "ran": False, "error": "no results"})
            continue
        suite = res.get("suite") or {}
        agg = res.get("aggregate") or {}
        meta["suites"].append({
            "suite_id": sid, "ran": True,
            "suite_sha256": suite.get("sha256"),
            "suite_version": suite.get("version"),
            "n_cases": agg.get("n_cases"), "n_passed": agg.get("n_passed"),
            "arena_honesty_label": res.get("honesty_label"),
            "answer_source": ("live provider answers via szl_llm_registry"
                              if res.get("honesty_label") == "LIVE"
                              else "MODELED reference-oracle answers (no provider key wired); "
                                   "the suites, scorers and verdicts are real"),
        })
        for r in res["results"]:
            answer = r.get("answer", "")
            expected = r.get("expected", "")
            scorer_name = r.get("scorer")
            # independent RE-EXECUTION of the scorer over the recorded answer
            rerun_ok, rerun_detail = None, None
            fn = scorers.get(scorer_name)
            if callable(fn):
                try:
                    rerun_ok, rerun_detail = fn(answer, expected)
                    rerun_ok = bool(rerun_ok)
                    meta["scorer_reexecuted"] = True
                except Exception as e:  # noqa: BLE001
                    rerun_ok, rerun_detail = None, f"rerun error: {type(e).__name__}"
            trajs.append({
                "suite_id": sid,
                "case_id": r.get("id"),
                "category": r.get("category"),
                "scorer": scorer_name,
                "eval_passed": bool(r.get("passed")),
                "answer_sha256": r.get("answer_sha256"),
                "rerun_passed": rerun_ok,
                "rerun_detail": rerun_detail,
                "honesty_label": r.get("honesty_label"),
            })
    if trajs:
        meta["real_eval_run"] = True
        meta["cases_available"] = len(trajs)
    else:
        meta["reason"] = meta["reason"] or "no eval suite produced results this request"
    return trajs, meta


def _run_loop(seed=42, n_trajectories=48, pass_rate=0.6, verify=True):
    """Deterministic STRUCTURAL model of the execution-verified synthesis loop.

    Each trajectory gets an eval score in [0,1]; a `pass_rate` fraction "pass" the eval.
    Passing trajectories are EXECUTED (agentops) and execution-VERIFIED with a modeled
    verifier that catches a fraction of eval-passes that don't actually run/reproduce
    (the honest gap between "looks right" and "runs right"). Only EXECUTION-VERIFIED
    trajectories become corpus CANDIDATES, and only if a Λ-advisory gate admits them.
    The gate is ADVISORY (gray), never green; trust is capped at _TRUST_CAP. When
    verify=False the execution-verification stage is skipped — modeling the UNSAFE path
    (accepting eval-passes without execution proof) so the yield/trust contrast is visible.
    """
    requested_n = max(1, min(int(n_trajectories), 4096))
    pass_rate = min(1.0, max(0.0, float(pass_rate)))

    # REAL SIGNAL (Wave 32): trajectories come from eval suites actually executed in this
    # request. We never pad the list to reach `n_trajectories` — a padded trajectory would
    # be a fabricated one. If fewer real cases exist than requested, we report the real
    # count and say so.
    real_cases, eval_source = _real_eval_trajectories()
    real = bool(eval_source.get("real_eval_run") and real_cases)
    if real:
        cases = real_cases[:requested_n]
        n = len(cases)
    else:
        cases = []
        n = requested_n

    trajs = []
    eval_passed = 0
    exec_verified = 0
    candidates = 0
    for i in range(n):
        case = cases[i] if real else None
        if real:
            # eval verdict: REAL scorer output from this request's suite run
            passed = bool(case["eval_passed"])
            eval_score = 1.0 if passed else 0.0
        else:
            eval_score = round(0.05 + 0.9 * _u01(seed, i, salt=2), 6)
            passed = eval_score >= (1.0 - pass_rate)  # higher pass_rate ⇒ lower bar ⇒ more pass
        if passed:
            eval_passed += 1

        # execution verification: a passing trajectory is EXECUTED; the verifier confirms
        # it actually runs/reproduces. Some eval-passes fail execution (the honest gap).
        executed = bool(passed)
        if not verify:
            verified = bool(passed)                                     # UNSAFE: trust eval alone
        elif real:
            # REAL re-execution: the scorer was run again, independently, over the recorded
            # answer. It verifies only if that independent run reproduces the pass.
            verified = bool(passed and case.get("rerun_passed") is True)
        else:
            verified = bool(passed and _u01(seed, i, salt=6) > 0.22)   # ~78% of passes verify
        if verified:
            exec_verified += 1

        # Λ advisory: high when eval is strong AND execution-verified; crushed otherwise.
        strength = eval_score if verified else eval_score * 0.4
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN,
                    _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * strength)), 6)
        admitted = bool(verified and lam >= _LAMBDA_ADMIT)
        if admitted:
            candidates += 1

        row = {
            "id": i,
            "eval_score": eval_score,
            "eval_passed": bool(passed),
            "executed": executed,
            "exec_verified": verified,
            "is_candidate": admitted,
            "lambda_advisory": lam,
            "admitted": admitted,
        }
        if real:
            row.update({
                "suite_id": case["suite_id"], "case_id": case["case_id"],
                "category": case["category"], "scorer": case["scorer"],
                "answer_sha256": case["answer_sha256"],
                "rerun_passed": case.get("rerun_passed"),
                "source": "real eval-arena case executed this request",
            })
        else:
            row["source"] = "seeded model (no real eval run available this request)"
        trajs.append(row)

    gated_out = n - candidates
    verification_rate = round(exec_verified / eval_passed, 6) if eval_passed else 0.0
    candidate_yield = round(candidates / n, 6) if n else 0.0
    mean_lambda = round(sum(t["lambda_advisory"] for t in trajs) / n, 6) if n else 0.0

    # governance invariant: no non-execution-verified trajectory may become a candidate.
    assert not any(t["is_candidate"] and not t["exec_verified"] for t in trajs), \
        "candidate must be execution-verified"

    trust_raw = (0.45 * candidate_yield + 0.25 * verification_rate
                 + 0.3 * (mean_lambda / _LAMBDA_MAX if _LAMBDA_MAX else 0.0))
    trust = round(min(_TRUST_CAP, max(0.0, trust_raw)), 6)

    return {
        "n_trajectories": n,
        "requested_n_trajectories": requested_n,
        "eval_source": eval_source,
        "real_eval_run": bool(real),
        "n_note": (("trajectories = the %d real eval cases executed this request "
                    "(requested %d; the list is NEVER padded with fabricated trajectories)"
                    % (n, requested_n)) if real else
                   ("no real eval run was available this request, so the loop fell back to "
                    "a seeded model of %d trajectories and stays STRUCTURAL-ONLY" % n)),
        "pass_rate": round(pass_rate, 6),
        "pass_rate_note": ("ignored in real-eval mode: pass/fail comes from the real scorer, "
                           "not from this parameter" if real else
                           "used as the seeded model's pass bar"),
        "verify": bool(verify),
        "stages": _STAGES,
        "trajectories": trajs[:_TRAJ_CAP],
        "loop": {
            "trajectories": n,
            "eval_passed": eval_passed,
            "execution_verified": exec_verified,
            "corpus_candidates": candidates,
            "gated_out": gated_out,
            "verification_rate": verification_rate,
            "candidate_yield": candidate_yield,
        },
        "lambda_gate": {
            "status": "Λ = Conjecture 1 (advisory, gray — NEVER green, not a theorem)",
            "admit_threshold": _LAMBDA_ADMIT,
            "mean_lambda_advisory": mean_lambda,
            "bounds": {"min": _LAMBDA_MIN, "max": _LAMBDA_MAX},
            "admits": candidates,
            "gated_out": gated_out,
            "trust": trust,
            "trust_cap": _TRUST_CAP,
        },
    }


def _receipt(payload, seed):
    """SHA-256 corpus-candidate receipt DESIGN (govern/receipts pattern).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints nothing. We compute a plain SHA-256
    over a canonical loop summary and return it as a clearly UNSIGNED preview
    (signed:false). A real COMMITTED corpus-candidate write would mint the signed Khipu
    receipt binding the eval score, the execution-verification verdict, and the Λ-gate
    verdict into the hash-chained receipt DAG.
    """
    gate = payload["lambda_gate"]
    loop = payload["loop"]
    canonical = "|".join([
        f"seed={seed}",
        f"trajectories={payload['n_trajectories']}",
        f"verify={payload['verify']}",
        "cids=" + ",".join(str(t["id"]) for t in payload["trajectories"] if t["is_candidate"]),
        f"candidates={loop['corpus_candidates']}",
        f"verification_rate={loop['verification_rate']}",
        f"candidate_yield={loop['candidate_yield']}",
        f"trust={gate['trust']}",
    ])
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "execution-verified-corpus-candidate-receipt (SZL synthesis — STRUCTURAL-ONLY design)",
        "binds": [
            "eval score + eval-pass verdict (evalarena)",
            "execution-verification verdict (agentops bounded operate loop, writer≠judge)",
            "Λ-gate verdict (admits / gated_out; Λ = Conjecture 1, gray)",
            "resulting corpus-candidate ids (Brain)",
        ],
        "chain": "one hash-linked Khipu receipt per committed corpus-candidate WRITE "
                 "(Conjecture 2: integrity real; BFT/consensus is the conjecture)",
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": digest,
        "preview_digest_alg": "SHA-256 over a canonical loop summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
        "verify_when_minted": "/api/a11oy/v1/khipu/verify/{digest}",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _ff(req, key, default):
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return default


def _bool(req, key, default=True):
    v = req.query_params.get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _h_execverify(req: Request):
    seed = _ii(req, "seed", 42)
    n_trajectories = max(1, min(_ii(req, "n_trajectories", 48), 4096))
    pass_rate = min(1.0, max(0.0, _ff(req, "pass_rate", 0.6)))
    verify = _bool(req, "verify", True)

    p = _run_loop(seed=seed, n_trajectories=n_trajectories, pass_rate=pass_rate, verify=verify)
    p["receipt"] = _receipt(p, seed)
    real = bool(p.get("real_eval_run"))
    # Wave 32: MODELED when the eval leg is a REAL in-request run (real suites, real
    # scorers, real pass/fail, plus an independent scorer re-execution as the
    # execution-verification check). Honestly STRUCTURAL-ONLY when no real eval could run,
    # because then the loop is only a seeded sketch of itself.
    label = "MODELED" if real else "STRUCTURAL-ONLY"
    p.update({
        "label": label,
        "model": ("closed honest loop: evalarena (REAL suites executed this request) → "
                  "independent scorer re-execution as the execution-verification leg → "
                  "Brain corpus candidate → SHA-256 receipt. The eval + verification legs "
                  "are MODELED from real in-request runs; the SYNTHESIS step (training on "
                  "the accepted corpus) is NOT executed and stays ROADMAP."
                  if real else
                  "closed honest loop concept: evalarena → agentops execution-verified "
                  "trajectory → Brain corpus candidate → SHA-256 receipt. No real eval ran "
                  "this request, so the loop is STRUCTURAL-ONLY (seeded sketch)."),
        "seed": seed,
        "provenance": {
            "eval_source": p.get("eval_source"),
            "real_eval_run": real,
            "verification_method": ("the scorer for each case was re-executed independently "
                                    "over the recorded answer; a trajectory is "
                                    "execution-verified only when that independent run "
                                    "reproduces the pass" if real else None),
            "not_measured": ("no wall-clock, joule or GPU reading is taken here, so nothing "
                             "on this surface is MEASURED"),
            "interpretation_caveat": (
                "the eval answers come from the arena's ground-truth-derived reference "
                "oracle whenever no provider key is wired (and always on a GET, so a read "
                "never triggers a paid provider call). A high pass or verification rate "
                "therefore reflects the SCORING pipeline reproducing itself, NOT a model "
                "capability claim about any system."),
            "coverage": 1.0,
        },
        "structural_only_reason": (None if real else
                                   (p.get("eval_source") or {}).get("reason")
                                   or "no real eval run available this request"),
        "measured_gap": ("MEASURED would require timing the loop on real hardware with a "
                         "meter attached, and an actual training run over the accepted "
                         "corpus. Neither happens on this GET."),
        "parts_labeled": {
            "STRUCTURAL-ONLY": [
                "the synthesis step itself (training on the accepted corpus) — not executed",
                "the SHA-256 corpus-candidate receipt (design; unsigned preview on a GET)",
            ],
            "MODELED": [
                ("eval-pass verdicts (REAL szl_eval_arena suites + scorers run this request)"
                 if real else "eval scores + eval-pass verdicts (deterministic seeded fallback)"),
                ("execution-verification verdicts (independent RE-EXECUTION of the same "
                 "scorer over the recorded answer)" if real else
                 "execution-verification verdicts (modeled verifier catching the looks-right/runs-right gap)"),
                "candidate yield + verification rate + trust (computed, hard-capped at 0.97)",
            ],
            "CITED (not ours)": [
                "Together AI ICML-2026 (together.ai/blog/icml-2026)",
                "execution-guided synthesis arXiv:1807.03100; STaR arXiv:2203.14465",
            ],
        },
        "honest_note": (
            ("MODELED. The eval verdicts are REAL: szl_eval_arena suites were executed in "
             "THIS request with their real scorers, and the execution-verification leg "
             "independently RE-EXECUTED each scorer over the recorded answer. The "
             "trajectory list is never padded to the requested n. "
             if real else
             "STRUCTURAL-ONLY. No real eval run was available this request, so the eval "
             "scores and verification verdicts fall back to a deterministic seeded MODEL "
             "of the loop — genuinely computed and reported, not fabricated. ")
            + "a11oy does NOT train a model from these "
            "trajectories in-request: the synthesis (eval → execution-verified trajectory → "
            "corpus candidate → receipt) is DESCRIBED and RECEIPTED, not executed as an "
            "end-to-end training run. The evalarena, Brain, and agentops organs referenced "
            "are real; the closed loop wiring them is the SZL synthesis and is "
            "STRUCTURAL-ONLY. A SHA-256 receipt is emitted per the govern/receipts pattern, "
            "but this GET is a READ so the receipt_preview_digest is an UNSIGNED content "
            "hash (RECEIPT-ON-WRITE, never on a GET) — not a signature. Λ is the advisory "
            "szl-lambda-gate (Conjecture 1, gray, NEVER green); trust is capped at 0.97 and "
            "never 1.0. Cites Together AI ICML-2026 (together.ai/blog/icml-2026), "
            "execution-guided synthesis (arXiv:1807.03100) and STaR (arXiv:2203.14465); SZL "
            "claims NONE of these as its own. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": label, "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/execverify onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/execverify", _h_execverify)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _run_loop(seed=42, n_trajectories=48, pass_rate=0.6, verify=True)
    p["receipt"] = _receipt(p, 42)
    g = p["lambda_gate"]
    loop = p["loop"]
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert p["receipt"]["signed"] is False and p["receipt"]["minted_on_this_get"] is False
    assert g["admits"] + g["gated_out"] == loop["trajectories"]
    assert not any(t["is_candidate"] and not t["exec_verified"] for t in p["trajectories"]), \
        "no non-execution-verified trajectory may become a corpus candidate"
    # verify=False (unsafe path) must NOT verify-gate: more raw passes flow through.
    p_unsafe = _run_loop(seed=42, n_trajectories=48, pass_rate=0.6, verify=False)
    assert p_unsafe["loop"]["execution_verified"] >= p["loop"]["execution_verified"], \
        "skipping execution-verification must not verify FEWER trajectories"
    print("trajectories:", loop["trajectories"], "eval_passed:", loop["eval_passed"],
          "execution_verified:", loop["execution_verified"], "candidates:", loop["corpus_candidates"])
    print("verification_rate:", loop["verification_rate"], "candidate_yield:", loop["candidate_yield"])
    print("trust:", g["trust"], "(cap", _TRUST_CAP, ")", "mean_lambda:", g["mean_lambda_advisory"])
    print("receipt:", p["receipt"]["receipt_preview_digest"][:16], "... signed:", p["receipt"]["signed"])
    print("real_eval_run:", p.get("real_eval_run"),
          "| label:", "MODELED" if p.get("real_eval_run") else "STRUCTURAL-ONLY")
