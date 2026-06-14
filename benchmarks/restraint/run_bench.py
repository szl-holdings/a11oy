#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
"""
run_bench.py — a11oy Restraint MEASURED benchmark harness (R4 lane).

Ports Ponytail's promptfoo two-arm methodology to a self-contained Python runner
so the /restraint-bench dashboard can show OUR reproduced numbers, labelled
MEASURED only when a real model run is wired on OUR stack.

PROVENANCE (honest): the methodology, the five everyday tasks, and the two-arm
(no-skill baseline vs a11oy-restraint) design are ADOPTED from the open-source
Ponytail skill (github.com/DietrichGebert/ponytail, MIT, © 2026 DietrichGebert).
We measure OUR arm on OUR stack. We NEVER reprint Ponytail's published numbers
(80-94% less code, 47-77% cheaper, 3-6x faster) as ours.

TWO MODES (the runner picks honestly — never fabricates a "measured" claim):

  --model <id>   A real model run. The runner sends each task to the model twice:
                 once with the bare task (baseline arm) and once with the a11oy
                 Restraint system prompt (a11oy-restraint arm), counts emitted LOC
                 deterministically from fenced code blocks, and records tokens +
                 wall-clock latency from the API. Result rows are labelled
                 MEASURED and the overall label is MEASURED. Requires a model
                 client to be wired (see _call_model below — left as the single
                 integration seam so no fake key is ever needed to read this file).

  (no --model)   SAMPLE mode. The runner uses OUR deterministic ladder model
                 (szl_restraint) to produce internally-consistent SAMPLE rows so
                 the dashboard is never blank. Rows are labelled SAMPLE and the
                 overall label is ROADMAP. These are NOT measured claims.

Output: a results.json that /api/a11oy/v1/restraint/bench-measured reads. When the
file carries overall_label == MEASURED (only a real run writes that), the
dashboard flips to MEASURED for the run you actually executed.

Exact reproduce command:
    python benchmarks/restraint/run_bench.py --model <your-model-id> --repeat 10 \
        --out benchmarks/restraint/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# The five everyday tasks (Ponytail's, cited — facts, not Ponytail's outputs).
TASKS: List[str] = [
    "Write me a Python function that validates email addresses.",
    "Add debounce to a search input in vanilla JavaScript. It currently fires an API call on every keystroke.",
    "Write Python code that reads sales.csv and sums the 'amount' column.",
    "Build me a countdown timer component in React that counts down from a given number of seconds.",
    "Add rate limiting to my FastAPI endpoint so users can't spam it.",
]

PONYTAIL_REPO = "https://github.com/DietrichGebert/ponytail"

# The a11oy-restraint system prompt for the measured arm: the 6-rung ladder, our
# honest rename of Ponytail's ceiling comment. (Adopted from Ponytail SKILL.md, MIT.)
RESTRAINT_SYSTEM_PROMPT = (
    "Before writing code, descend this ladder and STOP at the first rung that holds: "
    "(1) YAGNI — does it need to exist at all? (2) does stdlib do it? (3) is there a "
    "native platform feature? (4) is an already-installed dependency enough? (5) can it "
    "be one line? (6) only then: the minimum code that works. Mark deliberate "
    "simplifications with a `restraint:` comment naming the upgrade path. Never simplify "
    "away input validation at trust boundaries, data-loss error handling, security, "
    "accessibility, or anything explicitly requested. Emit the shortest working answer."
)


def count_loc(markdown: str) -> int:
    """Deterministically count lines of code inside fenced ```code``` blocks.

    Matches Ponytail's promptfoo loc.js intent: count non-blank lines inside fenced
    blocks; if there are no fences, count non-blank, non-prose lines as a fallback.
    """
    blocks = re.findall(r"```[a-zA-Z0-9_+-]*\n(.*?)```", markdown or "", re.DOTALL)
    if blocks:
        loc = 0
        for b in blocks:
            loc += sum(1 for ln in b.splitlines() if ln.strip())
        return loc
    # No fences: count non-blank lines that look like code (have a symbol).
    return sum(1 for ln in (markdown or "").splitlines()
               if ln.strip() and re.search(r"[=(){}\[\];:]|def |class |const |let |function ", ln))


# ---------------------------------------------------------------------------
# Model integration seam. Left intentionally as the SINGLE place to wire a real
# client (OpenAI-compatible, vLLM, NIM, etc.). Returns (text, tokens, latency_s)
# or raises. We DO NOT ship a fake client — without a real one the runner stays
# in SAMPLE mode and never emits a MEASURED claim.
# ---------------------------------------------------------------------------
def _call_model(model: str, system: Optional[str], task: str) -> Dict[str, Any]:
    """Call an OpenAI-compatible chat endpoint if OPENAI_BASE_URL/OPENAI_API_KEY
    (or A11OY_MODEL_BASE) are set; else raise so the runner falls back to SAMPLE.
    Pure-stdlib HTTP (urllib) — no new dependency."""
    import urllib.request

    base = os.environ.get("A11OY_MODEL_BASE") or os.environ.get("OPENAI_BASE_URL")
    key = os.environ.get("A11OY_MODEL_KEY") or os.environ.get("OPENAI_API_KEY")
    if not base:
        raise RuntimeError("no model base URL wired (set A11OY_MODEL_BASE / OPENAI_BASE_URL)")
    url = base.rstrip("/") + "/chat/completions"
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": task})
    body = json.dumps({"model": model, "messages": msgs, "temperature": 0}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer %s" % key} if key else {})})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    latency = time.time() - t0
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    tokens = usage.get("completion_tokens") or usage.get("total_tokens") or 0
    return {"text": text, "tokens": int(tokens), "latency_s": round(latency, 3)}


def _measured_arm(model: str, system: Optional[str], task: str, repeat: int) -> Dict[str, Any]:
    locs, toks, lats = [], [], []
    for _ in range(repeat):
        r = _call_model(model, system, task)
        locs.append(count_loc(r["text"]))
        toks.append(r["tokens"])
        lats.append(r["latency_s"])
    return {"loc": int(statistics.median(locs)),
            "tokens": int(statistics.median(toks)),
            "latency_s": round(statistics.median(lats), 3)}


def _sample_arm(task: str, arm: str, intensity: str) -> Dict[str, Any]:
    """SAMPLE arm via OUR ladder model — internally consistent, clearly NOT measured."""
    import szl_restraint as R
    dec = R.descend_ladder(task, intensity)
    s = dec["lines_saved_estimate"]
    tpl = R.TOKENS_PER_LOC
    if arm == "baseline":
        loc = s["baseline_loc_modeled"]
    else:
        loc = s["restraint_loc_modeled"]
    return {"loc": loc, "tokens": int(loc * tpl), "latency_s": round(loc * 0.18, 2)}


def _pct(a: float, b: float) -> float:
    return round((a - b) / a * 100.0, 1) if a else 0.0


def run(model: Optional[str], repeat: int, intensity: str) -> Dict[str, Any]:
    # Decide mode honestly: MEASURED only if a model is named AND a client is wired.
    measured = False
    if model:
        try:
            _call_model(model, None, "ping")  # probe the wiring
            measured = True
        except Exception as e:
            print("[run_bench] model probe failed (%s) -> SAMPLE mode" % e, file=sys.stderr)
            measured = False

    # SAMPLE mode needs szl_restraint importable.
    if not measured:
        try:
            import szl_restraint  # noqa: F401
        except Exception as e:
            print("[run_bench] szl_restraint not importable: %s" % e, file=sys.stderr)

    rows: List[Dict[str, Any]] = []
    for task in TASKS:
        if measured:
            base = _measured_arm(model, None, task, repeat)
            rest = _measured_arm(model, RESTRAINT_SYSTEM_PROMPT, task, repeat)
            label = "MEASURED"
        else:
            base = _sample_arm(task, "baseline", intensity)
            rest = _sample_arm(task, "a11oy-restraint", intensity)
            label = "SAMPLE"
        rows.append({
            "task": task,
            "baseline": base,
            "a11oy_restraint": rest,
            "loc_reduction_pct": _pct(base["loc"], rest["loc"]),
            "cost_proxy_reduction_pct": _pct(base["tokens"], rest["tokens"]),
            "latency_reduction_pct": _pct(base["latency_s"], rest["latency_s"]),
            "label": label,
        })

    def med(vals):
        return round(statistics.median(vals), 1) if vals else 0.0

    aggregate = {
        "median_loc_reduction_pct": med([r["loc_reduction_pct"] for r in rows]),
        "median_cost_proxy_reduction_pct": med([r["cost_proxy_reduction_pct"] for r in rows]),
        "median_latency_reduction_pct": med([r["latency_reduction_pct"] for r in rows]),
        "total_baseline_loc": sum(r["baseline"]["loc"] for r in rows),
        "total_restraint_loc": sum(r["a11oy_restraint"]["loc"] for r in rows),
    }
    return {
        "service": "a11oy.restraint.bench",
        "arms": ["baseline (no skill)", "a11oy-restraint"],
        "model": model if measured else None,
        "repeat": repeat,
        "intensity": intensity,
        "tasks": len(TASKS),
        "rows": rows,
        "aggregate": aggregate,
        "overall_label": "MEASURED" if measured else "ROADMAP",
        "measured_on": "OUR stack via run_bench.py" if measured else None,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "methodology": ("Ponytail's promptfoo methodology ported to OUR stack (MIT): same "
                        "five tasks, two arms (no-skill baseline vs a11oy-restraint), median "
                        "reported. LOC counted deterministically from fenced code blocks; "
                        "tokens + latency from the API."),
        "honesty": ("OUR numbers on OUR stack ONLY when overall_label == MEASURED. SAMPLE "
                    "rows are derived from our deterministic ladder model, never measured. "
                    "Ponytail's published numbers are CITED as Ponytail's, never claimed as ours."),
        "ponytail_published": {
            "code_reduction": "80-94% less code", "cost_reduction": "47-77% cheaper",
            "speed": "3-6x faster",
            "basis": "median of 10 runs across Haiku/Sonnet/Opus (Ponytail benchmarks/, MIT)",
            "source": PONYTAIL_REPO + "/tree/main/benchmarks",
            "label": "CITED (Ponytail's numbers, not ours)",
        },
        "reproduce": ("python benchmarks/restraint/run_bench.py --model <your-model-id> "
                      "--repeat 10 --out benchmarks/restraint/results.json"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="a11oy Restraint two-arm benchmark (Ponytail methodology, our measurements).")
    ap.add_argument("--model", default=None, help="model id for a REAL run (omit for SAMPLE mode)")
    ap.add_argument("--repeat", type=int, default=10, help="repeats per arm (median reported)")
    ap.add_argument("--intensity", default="full", choices=["lite", "full", "ultra"])
    ap.add_argument("--out", default="benchmarks/restraint/results.json", help="results artifact path")
    args = ap.parse_args()

    # Make szl_restraint importable from repo root when run from anywhere.
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    result = run(args.model, args.repeat, args.intensity)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("[run_bench] overall_label=%s  median LOC reduction=%.1f%%  -> %s"
          % (result["overall_label"], result["aggregate"]["median_loc_reduction_pct"], outp))
    if result["overall_label"] != "MEASURED":
        print("[run_bench] SAMPLE/ROADMAP only — pass --model <id> with a wired client to MEASURE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
