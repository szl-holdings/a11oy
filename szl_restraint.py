# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
"""
szl_restraint.py — a11oy Restraint: a GOVERNED + MEASURED frugality gate for the
a11oy Code agent path.

PROVENANCE (honest, not invented):
    The 6-rung "ladder" reasoning and the intensity levels (lite/full/ultra) are
    ADOPTED from the open-source **Ponytail** coding-agent skill
    (github.com/DietrichGebert/ponytail, MIT, © 2026 DietrichGebert). We studied
    Ponytail's SKILL.md and benchmark methodology and RE-IMPLEMENTED the idea on
    our own stack — we did NOT bulk-copy its files. a11oy Restraint is Ponytail
    *governed* (every restraint decision becomes a signed DSSE receipt + Λ-scored)
    and *measured* (we reproduce the code-reduction / cost / speed numbers on OUR
    stack rather than repeating Ponytail's). Ponytail's published numbers
    (80-94% less code, 47-77% cheaper, 3-6x faster, median across Haiku/Sonnet/
    Opus) are CITED as Ponytail's, never claimed as ours.

WHAT THIS MODULE DOES (all real, deterministic):
    1. A pre-write reasoning gate the code agent applies before emitting a diff.
       It descends the 6-rung ladder and stops at the first rung that holds:
         (1) YAGNI — does this need to exist at all?
         (2) stdlib does it?
         (3) native platform feature?
         (4) already-installed dependency?
         (5) one line?
         (6) only then: minimum viable code.
       Intensity lite/full/ultra changes how aggressively rungs 1/5/6 fire.
    2. Emits `restraint:` ceiling comments (our honest rename of Ponytail's
       `ponytail:`) naming the upgrade path for each deliberate simplification.
    3. GOVERNED: every decision -> a signed DSSE receipt (caller passes the host's
       REAL in-image ECDSA-P256 signer _a11oy_sign_receipt) + a Λ trust score
       (Conjecture 1 is OPEN, advisory floor < 1.0; we never call it proven).
    4. MEASURED: a promptfoo-style benchmark harness with two arms — no-skill
       baseline vs a11oy-restraint — over Ponytail's five everyday tasks. Numbers
       are labelled MEASURED only when an actual run is wired; otherwise SAMPLE /
       ROADMAP. We never reprint Ponytail's numbers as ours.
    5. ENERGY: less code -> fewer tokens -> fewer joules on our GPU. A small,
       honestly-labelled tie-in estimates tokens/joules saved per decision and
       defers the joules honesty label to szl_joules_truth (SAMPLE unless a fresh
       on-box NVML exporter sample is present).

ENDPOINTS (routes insert at position 0 to beat the SPA catch-all):
    POST /api/a11oy/v1/restraint/evaluate  {task[, intensity, lang]} -> ladder
         decision + restraint: ceilings + lines-saved estimate + signed receipt
         + Λ score + energy tie-in.
    POST /api/a11oy/v1/restraint/bench     {[intensity]} -> two-arm benchmark
         (baseline vs a11oy-restraint) over the five tasks, honestly labelled.
    GET  /api/a11oy/v1/restraint/info      -> doctrine + ladder spec + Ponytail
         citation + honesty card.

ADDITIVE, self-contained, try/except-guarded by serve.py. Touches nothing else.
"""
from __future__ import annotations

import math
import re
import time
from hashlib import sha256
from typing import Any, Callable, Dict, List, Optional

DOCTRINE = "v11"
KERNEL_COMMIT = "c7c0ba17"
LOCKED = 8
PONYTAIL_REPO = "https://github.com/DietrichGebert/ponytail"
PONYTAIL_LICENSE = "MIT"

# ---------------------------------------------------------------------------
# THE LADDER — 6 rungs. Stop at the first rung that holds. (Adopted from Ponytail
# SKILL.md, MIT; re-implemented as deterministic detectors over the task text.)
# ---------------------------------------------------------------------------
RUNGS: List[Dict[str, Any]] = [
    {"rung": 1, "key": "yagni",   "name": "Does this need to exist at all? (YAGNI)"},
    {"rung": 2, "key": "stdlib",  "name": "Stdlib does it?"},
    {"rung": 3, "key": "native",  "name": "Native platform feature covers it?"},
    {"rung": 4, "key": "installed", "name": "Already-installed dependency solves it?"},
    {"rung": 5, "key": "oneline", "name": "Can it be one line?"},
    {"rung": 6, "key": "minimal", "name": "Only then: the minimum code that works."},
]

INTENSITIES = ("lite", "full", "ultra")

# When NOT to be lazy (Ponytail: never simplify these away).
NEVER_SIMPLIFY = (
    "input validation at trust boundaries", "data-loss error handling",
    "security measures", "accessibility basics", "anything explicitly requested",
)

# ---------------------------------------------------------------------------
# Deterministic rung detectors. Each returns (matched: bool, detail: dict|None).
# These are honest HEURISTICS (rule advisories), not a proof — the response
# labels them HEURISTIC. The agent uses them as a reflex pre-write gate.
# ---------------------------------------------------------------------------

# rung 2 — stdlib coverage signals (Python + JS), name -> (pattern, stdlib answer, ceiling)
_STDLIB = [
    (r"\bvalidate?\s+(?:an?\s+)?e-?mail", "email.utils.parseaddr / a one-line regex",
     "naive RFC-5322 subset; swap to the `email-validator` dep if full grammar + deliverability matters"),
    (r"\bparse\s+json|\bjson\b", "json (stdlib)", "stdlib json; ujson/orjson only if a profiler shows it matters"),
    (r"\bsum\b.*\bcsv\b|\bcsv\b.*\bsum\b|read .*csv", "csv (stdlib)",
     "csv.DictReader + sum(); reach for pandas only past ~1e6 rows"),
    (r"\bcache\b|memoi[sz]e", "functools.lru_cache", "lru_cache(maxsize=...); a hand-rolled TTL cache only when a profiler demands it"),
    (r"\bhash\b|\bchecksum\b|\bdigest\b", "hashlib", "hashlib; a crypto dep only for keyed/AEAD needs"),
    (r"\bparse\s+(?:a\s+)?date|\bformat\s+(?:a\s+)?date|\btimestamp\b|\bdatetime\b|\bcurrent time\b|\bnow\(\)", "datetime",
     "datetime; arrow/pendulum only if tz arithmetic gets heavy"),
    (r"\bregex\b|\bregular expression", "re (stdlib)", "re; a parser only when the grammar outgrows regex"),
    (r"\bcounter\b|\bcount\b.*\boccur", "collections.Counter", "Counter; nothing fancier needed"),
    (r"\brandom\b|\buuid\b", "random / uuid (stdlib)", "stdlib; secrets for security-sensitive randomness"),
]

# rung 3 — native platform feature signals (browser / DB), name -> (pattern, native answer, ceiling)
_NATIVE = [
    (r"date\s*picker|pick a date|calendar input", '<input type="date">',
     "browser-native date input; a picker lib only for ranges/locales it cannot express"),
    (r"\bdebounce\b", "addEventListener + setTimeout (≈3 lines)",
     "tiny inline debounce; lodash.debounce only if you already ship lodash"),
    (r"\bcountdown\b|\btimer\b", "setInterval + useState (React) / requestAnimationFrame",
     "minimal interval; a timer lib is overkill"),
    (r"\bform validation\b|required field", "HTML5 required/pattern + Constraint Validation API",
     "native form validation; a form lib only for complex cross-field rules"),
    (r"\bcolour|\bcolor picker", '<input type="color">', "native colour input"),
    (r"\bunique constraint|\bforeign key|\bnot null", "DB constraint (schema)",
     "DB constraint over app-code validation; app check only as UX nicety"),
    (r"\bcss\b.*\banimat|animate .*css|\btransition\b", "CSS transition/animation",
     "CSS over JS animation; JS only for physics/interaction-driven motion"),
]

# rung 4 — already-installed dependency signals (very conservative)
_INSTALLED = [
    (r"\bhttp request|\bfetch\b.*\bapi\b|call (?:an? )?api", "fetch() / requests if already present",
     "use the HTTP client already in the project; never add a second one"),
    (r"\brate limit", "your framework's existing middleware (e.g. slowapi if installed)",
     "reuse installed limiter; a Redis token-bucket only at multi-instance scale"),
]

# rung 1 — YAGNI signals: speculative / future-proofing language
_YAGNI = re.compile(
    r"\b(for later|in (?:the )?future|might need|may need|just in case|"
    r"future-proof|extensib(?:le|ility)|pluggable|abstract(?:ion)?|generic|"
    r"configurable|factory|interface for|scaffold|boilerplate|framework around)\b",
    re.IGNORECASE,
)

# rung 5 — one-line signals: trivial transforms
_ONELINE = re.compile(
    r"\b(sort|reverse|uppercase|lowercase|trim|join|split|flatten|dedup(?:licate)?|"
    r"map over|filter|capitali[sz]e|round|format)\b", re.IGNORECASE,
)


def _intensity(level: Optional[str]) -> str:
    lv = (level or "full").strip().lower()
    return lv if lv in INTENSITIES else "full"


def _scan(task: str, table) -> Optional[Dict[str, Any]]:
    for pat, answer, ceiling in table:
        if re.search(pat, task, re.IGNORECASE):
            return {"answer": answer, "ceiling": ceiling, "matched": pat}
    return None


def descend_ladder(task: str, intensity: str = "full") -> Dict[str, Any]:
    """Descend the 6-rung ladder over `task`; stop at the first rung that holds.

    Deterministic + honest: rung detectors are rule HEURISTICS, not a proof. The
    intensity level biases rungs 1/5/6:
      - lite : build what's asked but name the lazier alternative (rarely stops at 1).
      - full : ladder enforced, stdlib/native first (default).
      - ultra: YAGNI-extremist — rung 1 fires on any speculative language.
    """
    intensity = _intensity(intensity)
    t = task or ""
    trail: List[Dict[str, Any]] = []

    def note(rung_key, held, detail=None):
        r = next(x for x in RUNGS if x["key"] == rung_key)
        trail.append({"rung": r["rung"], "key": r["key"], "name": r["name"],
                      "held": held, "detail": detail})

    # Rung 1 — YAGNI. ultra fires on any speculative word; full/lite need an
    # explicit "for later"/"just in case"; lite reports but does not stop.
    yag = _YAGNI.search(t)
    if yag:
        held = (intensity == "ultra") or (intensity == "full")
        note("yagni", held, {"speculative_phrase": yag.group(0),
                             "verdict": "skip the speculative part; add when a real caller needs it"})
        if held and intensity != "lite":
            return _result(1, "yagni", task, intensity, trail,
                           answer="Skip it (YAGNI). " + yag.group(0).lower() + " is speculative.",
                           ceiling="add the abstraction when a SECOND real caller exists, not before")
    else:
        note("yagni", False)

    # Rung 2 — stdlib.
    s = _scan(t, _STDLIB)
    if s:
        note("stdlib", True, s)
        return _result(2, "stdlib", task, intensity, trail, answer=s["answer"], ceiling=s["ceiling"])
    note("stdlib", False)

    # Rung 3 — native platform feature.
    n = _scan(t, _NATIVE)
    if n:
        note("native", True, n)
        return _result(3, "native", task, intensity, trail, answer=n["answer"], ceiling=n["ceiling"])
    note("native", False)

    # Rung 4 — already-installed dependency.
    i = _scan(t, _INSTALLED)
    if i:
        note("installed", True, i)
        return _result(4, "installed", task, intensity, trail, answer=i["answer"], ceiling=i["ceiling"])
    note("installed", False)

    # Rung 5 — one line. ultra/full take it; lite reports.
    o = _ONELINE.search(t)
    if o and intensity != "lite":
        note("oneline", True, {"op": o.group(0)})
        return _result(5, "oneline", task, intensity, trail,
                       answer="One line: a single %s expression — no helper, no class." % o.group(0).lower(),
                       ceiling="extract a function only when the same expression appears a third time")
    note("oneline", bool(o))

    # Rung 6 — minimum viable code.
    note("minimal", True)
    return _result(6, "minimal", task, intensity, trail,
                   answer="The minimum code that works — shortest working diff, fewest files.",
                   ceiling="add structure only when a measured need (profiler / second caller) appears")


def _result(rung: int, key: str, task: str, intensity: str,
            trail: List[Dict[str, Any]], answer: str, ceiling: str) -> Dict[str, Any]:
    saved = estimate_lines_saved(rung, task, intensity)
    comment = restraint_comment(key, ceiling, lang=_guess_lang(task))
    return {
        "task": task,
        "intensity": intensity,
        "stopped_at_rung": rung,
        "rung_key": key,
        "rung_name": next(x["name"] for x in RUNGS if x["rung"] == rung),
        "answer": answer,
        "ceiling": ceiling,
        "restraint_comment": comment,
        "ladder_trail": trail,
        "lines_saved_estimate": saved,
        "never_simplify": list(NEVER_SIMPLIFY),
        "label": "HEURISTIC",
        "honesty": ("Rung detectors are deterministic rule advisories (HEURISTIC), "
                    "not a proof. The agent applies this as a pre-write reflex; the "
                    "human stays on the loop. Ladder + intensity adopted from Ponytail "
                    "(MIT); governance + measurement are ours."),
    }


def _guess_lang(task: str) -> str:
    t = (task or "").lower()
    if any(k in t for k in ("react", "javascript", "<input", "css", "html", "debounce", "dom")):
        return "js"
    return "py"


def restraint_comment(rung_key: str, ceiling: str, lang: str = "py") -> str:
    """Emit a `restraint:` ceiling comment (our honest rename of Ponytail's
    `ponytail:`). It names the deliberate simplification's upgrade path so the
    next reader sees intent, not ignorance."""
    body = "restraint: %s — %s" % (rung_key, ceiling)
    if lang == "js":
        return "// " + body
    return "# " + body


# ---------------------------------------------------------------------------
# Lines-saved estimate. Honest MODELED figure: ladder rung -> a conservative
# code-reduction multiplier applied to a baseline LOC estimate for the task.
# This is OUR model, labelled MODELED — never Ponytail's measured numbers.
# ---------------------------------------------------------------------------
# Conservative per-rung reduction fractions (our model; documented, not claimed
# as measured). Higher rungs = less reduction (you actually write some code).
_RUNG_REDUCTION = {1: 0.95, 2: 0.85, 3: 0.80, 4: 0.55, 5: 0.75, 6: 0.30}


def _baseline_loc_estimate(task: str) -> int:
    """A deterministic, transparent baseline-LOC guess from task length + signals.
    Honest MODELED proxy for 'what an unconstrained agent would emit'."""
    base = 18 + min(60, len(task) // 4)
    if re.search(r"class|component|endpoint|api|service", task, re.IGNORECASE):
        base += 30
    return base


def estimate_lines_saved(rung: int, task: str, intensity: str) -> Dict[str, Any]:
    base = _baseline_loc_estimate(task)
    frac = _RUNG_REDUCTION.get(rung, 0.3)
    if intensity == "ultra":
        frac = min(0.97, frac + 0.05)
    elif intensity == "lite":
        frac = max(0.10, frac - 0.20)
    saved = int(round(base * frac))
    kept = base - saved
    return {
        "baseline_loc_modeled": base,
        "restraint_loc_modeled": kept,
        "lines_saved_modeled": saved,
        "reduction_fraction": round(frac, 3),
        "label": "MODELED",
        "note": ("OUR transparent model (baseline-LOC proxy × per-rung reduction). "
                 "MODELED, not MEASURED. For a measured figure run "
                 "/api/a11oy/v1/restraint/bench on a model-configured Space."),
    }


# ---------------------------------------------------------------------------
# Λ (Lambda) trust score for the decision. Conjecture 1 is OPEN (advisory floor
# < 1.0) — we NEVER claim Λ uniqueness is proven. Geometric mean of bounded
# axis scores, zero-pinned (matches a11oy_code.lambda_signal semantics).
# ---------------------------------------------------------------------------
LAMBDA_ADVISORY_FLOOR = 1.0  # Conjecture 1: a governed decision keeps Λ < 1.0.


def lambda_score(rung: int, intensity: str, task: str) -> Dict[str, Any]:
    """Advisory Λ for the restraint decision. Higher rung held with clear signal
    => higher confidence; speculative/ambiguous => lower. Bounded in (0, 1)."""
    # axis 1: detector confidence (a clear stdlib/native hit is high-trust)
    a_detect = {1: 0.86, 2: 0.93, 3: 0.92, 4: 0.78, 5: 0.84, 6: 0.70}.get(rung, 0.7)
    # axis 2: task clarity (longer, more specific tasks score higher up to a cap)
    a_clarity = min(0.95, 0.55 + len(task or "") / 400.0)
    # axis 3: intensity calibration (full is the calibrated default)
    a_intensity = {"full": 0.95, "lite": 0.88, "ultra": 0.82}.get(intensity, 0.9)
    xs = [a_detect, a_clarity, a_intensity]
    L = math.exp(sum(math.log(max(1e-9, x)) for x in xs) / len(xs))
    L = min(0.999, L)  # advisory floor: stays strictly < 1.0 (Conjecture 1, OPEN)
    return {
        "lambda": round(L, 6),
        "axes": {"detector_confidence": round(a_detect, 4),
                 "task_clarity": round(a_clarity, 4),
                 "intensity_calibration": round(a_intensity, 4)},
        "advisory_floor": LAMBDA_ADVISORY_FLOOR,
        "below_floor": L < LAMBDA_ADVISORY_FLOOR,
        "conjecture": ("Conjecture 1 (Λ uniqueness) is OPEN — NOT a closed theorem. "
                       "Λ here is an advisory trust signal kept strictly < 1.0."),
    }


# ---------------------------------------------------------------------------
# ENERGY tie-in. Less code -> fewer output tokens -> fewer joules on our GPU.
# Honest MODELED estimate; the JOULES label is delegated to szl_joules_truth so
# it reads "measured" ONLY with a fresh on-box NVML exporter sample, else "sample".
# ---------------------------------------------------------------------------
# Transparent constants (our model; documented):
TOKENS_PER_LOC = 9.0          # rough output tokens per line of emitted code
J_PER_OUTPUT_TOKEN = 0.65     # MODELED joules/output-token on our GPU tier (estimate)


def energy_tiein(lines_saved: int, exporter_sample: Any = None) -> Dict[str, Any]:
    tokens_saved = lines_saved * TOKENS_PER_LOC
    joules_saved_modeled = tokens_saved * J_PER_OUTPUT_TOKEN
    out = {
        "tokens_saved_modeled": round(tokens_saved, 1),
        "joules_saved_modeled": round(joules_saved_modeled, 1),
        "tokens_per_loc": TOKENS_PER_LOC,
        "j_per_output_token_modeled": J_PER_OUTPUT_TOKEN,
        "label": "MODELED",
        "thesis": "less code = fewer tokens = fewer joules on our GPU (sovereign thesis).",
        "note": ("MODELED estimate (lines_saved × tokens/LOC × J/token). The J/token "
                 "figure is a modeled estimate, not a live meter reading."),
    }
    # Delegate the joules honesty label to the single source of truth.
    try:
        import szl_joules_truth as _jt
        out.update(_jt.labeled_joules(exporter_sample))
    except Exception:
        out["joules_label"] = "sample"
        out["joules_evidence"] = {}
    return out


# ---------------------------------------------------------------------------
# Full governed evaluation: ladder + Λ + energy + (optional) signed receipt.
# ---------------------------------------------------------------------------

def evaluate(task: str, intensity: str = "full", lang: Optional[str] = None,
             sign_fn: Optional[Callable[[Any], dict]] = None,
             exporter_sample: Any = None) -> Dict[str, Any]:
    t0 = time.time()
    dec = descend_ladder(task, intensity)
    if lang in ("py", "js"):
        dec["restraint_comment"] = restraint_comment(dec["rung_key"], dec["ceiling"], lang=lang)
    lam = lambda_score(dec["stopped_at_rung"], dec["intensity"], task)
    energy = energy_tiein(dec["lines_saved_estimate"]["lines_saved_modeled"], exporter_sample)

    receipt_payload = {
        "kind": "restraint.decision",
        "task_digest": sha256((task or "").encode()).hexdigest(),
        "stopped_at_rung": dec["stopped_at_rung"],
        "rung_key": dec["rung_key"],
        "why": dec["answer"],
        "ceiling": dec["ceiling"],
        "restraint_comment": dec["restraint_comment"],
        "intensity": dec["intensity"],
        "lines_saved_modeled": dec["lines_saved_estimate"]["lines_saved_modeled"],
        "lambda": lam["lambda"],
        "lambda_below_floor": lam["below_floor"],
        "tokens_saved_modeled": energy["tokens_saved_modeled"],
        "joules_saved_modeled": energy["joules_saved_modeled"],
        "joules_label": energy.get("joules_label", "sample"),
        "doctrine": DOCTRINE,
        "kernel_commit": KERNEL_COMMIT,
        "provenance": {"adopted_from": "Ponytail", "repo": PONYTAIL_REPO,
                       "license": PONYTAIL_LICENSE, "relation": "adopted + governed"},
    }
    signed = None
    if sign_fn is not None:
        try:
            signed = sign_fn(receipt_payload)
        except Exception as e:  # never fabricate a signature
            signed = {"signed": False, "honesty": "signer raised: %r" % e}

    out = dict(dec)
    out["lambda_score"] = lam
    out["energy_tiein"] = energy
    out["receipt_payload"] = receipt_payload
    out["signed_receipt"] = signed
    out["latency_ms"] = round((time.time() - t0) * 1000.0, 3)
    out["service"] = "a11oy.restraint"
    out["doctrine"] = DOCTRINE
    return out


# ---------------------------------------------------------------------------
# MEASURED benchmark harness. Ponytail's methodology PORTED to our stack: two
# arms (no-skill baseline vs a11oy-restraint) over the same five everyday tasks.
# Numbers read MEASURED only when an actual model run is wired (a callable
# `run_arm` is supplied that returns real LOC/tokens/latency). Otherwise the arm
# is labelled SAMPLE (our illustrative fixture) and the bench is ROADMAP overall.
# We NEVER reprint Ponytail's published numbers as ours.
# ---------------------------------------------------------------------------
BENCH_TASKS = [
    "Write me a Python function that validates email addresses.",
    "Add debounce to a search input in vanilla JavaScript. It currently fires an API call on every keystroke.",
    "Write Python code that reads sales.csv and sums the 'amount' column.",
    "Build me a countdown timer component in React that counts down from a given number of seconds.",
    "Add rate limiting to my FastAPI endpoint so users can't spam it.",
]


def benchmark(intensity: str = "full",
              run_arm: Optional[Callable[[str, str], Dict[str, float]]] = None) -> Dict[str, Any]:
    """Two-arm benchmark over the five tasks.

    run_arm(task, arm) -> {"loc": int, "tokens": int, "latency_s": float} for a
    REAL model run. If run_arm is None (no model wired on this Space), each arm
    is a SAMPLE fixture and the bench is labelled ROADMAP. The restraint arm's
    SAMPLE LOC is derived from OUR ladder model (lines_saved), so it is internally
    consistent and clearly NOT a measured claim.
    """
    intensity = _intensity(intensity)
    measured = run_arm is not None
    rows = []
    for task in BENCH_TASKS:
        dec = descend_ladder(task, intensity)
        saved = dec["lines_saved_estimate"]
        if measured:
            base = run_arm(task, "baseline")
            rest = run_arm(task, "a11oy-restraint")
            label = "MEASURED"
        else:
            base = {"loc": saved["baseline_loc_modeled"],
                    "tokens": int(saved["baseline_loc_modeled"] * TOKENS_PER_LOC),
                    "latency_s": round(saved["baseline_loc_modeled"] * 0.18, 2)}
            rest = {"loc": saved["restraint_loc_modeled"],
                    "tokens": int(saved["restraint_loc_modeled"] * TOKENS_PER_LOC),
                    "latency_s": round(saved["restraint_loc_modeled"] * 0.18, 2)}
            label = "SAMPLE"
        rows.append({
            "task": task,
            "stopped_at_rung": dec["stopped_at_rung"],
            "baseline": base,
            "a11oy_restraint": rest,
            "loc_reduction_pct": _pct(base["loc"], rest["loc"]),
            "cost_proxy_reduction_pct": _pct(base["tokens"], rest["tokens"]),
            "latency_reduction_pct": _pct(base["latency_s"], rest["latency_s"]),
            "label": label,
        })
    agg = _aggregate(rows)
    return {
        "service": "a11oy.restraint.bench",
        "arms": ["baseline (no skill)", "a11oy-restraint"],
        "intensity": intensity,
        "tasks": len(BENCH_TASKS),
        "rows": rows,
        "aggregate": agg,
        "overall_label": "MEASURED" if measured else "ROADMAP",
        "methodology": ("Ported from Ponytail's promptfoo methodology (MIT): same five "
                        "everyday tasks, two arms (no-skill baseline vs a11oy-restraint), "
                        "median reported. LOC counted from emitted code; tokens/latency "
                        "from the API when a model is wired."),
        "honesty": ("These are OUR numbers measured on OUR stack ONLY when overall_label "
                    "== MEASURED (a model run was wired). Otherwise they are SAMPLE/ROADMAP "
                    "fixtures derived from our ladder model. Ponytail's published numbers "
                    "(80-94% less code, 47-77% cheaper, 3-6x faster, median across "
                    "Haiku/Sonnet/Opus) are CITED as Ponytail's, never claimed as ours."),
        "ponytail_published": {
            "code_reduction": "80-94% less code",
            "cost_reduction": "47-77% cheaper",
            "speed": "3-6x faster",
            "basis": "median of 10 runs across Haiku/Sonnet/Opus (Ponytail benchmarks/, MIT)",
            "source": PONYTAIL_REPO + "/tree/main/benchmarks",
            "label": "CITED (Ponytail's numbers, not ours)",
        },
        "reproduce": ("npx promptfoo@latest eval -c benchmarks/restraint/promptfooconfig.yaml "
                      "--repeat 10  (set the model key; then overall_label flips to MEASURED)"),
    }


def _pct(a: float, b: float) -> float:
    if not a:
        return 0.0
    return round((a - b) / a * 100.0, 1)


def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def med(vals):
        vals = sorted(vals)
        n = len(vals)
        if not n:
            return 0.0
        return vals[n // 2] if n % 2 else round((vals[n // 2 - 1] + vals[n // 2]) / 2.0, 2)
    return {
        "median_loc_reduction_pct": med([r["loc_reduction_pct"] for r in rows]),
        "median_cost_proxy_reduction_pct": med([r["cost_proxy_reduction_pct"] for r in rows]),
        "median_latency_reduction_pct": med([r["latency_reduction_pct"] for r in rows]),
        "total_baseline_loc": sum(r["baseline"]["loc"] for r in rows),
        "total_restraint_loc": sum(r["a11oy_restraint"]["loc"] for r in rows),
    }


def info() -> Dict[str, Any]:
    return {
        "service": "a11oy.restraint",
        "what": ("a GOVERNED + MEASURED frugality gate for the a11oy Code agent: before "
                 "emitting a diff the agent descends a 6-rung ladder and stops at the first "
                 "rung that holds, marking deliberate simplifications with `restraint:` "
                 "ceiling comments that name the upgrade path."),
        "ladder": RUNGS,
        "intensities": {
            "lite": "build what's asked, name the lazier alternative in one line.",
            "full": "ladder enforced, stdlib/native first, shortest diff (default).",
            "ultra": "YAGNI-extremist: deletion before addition; rung 1 fires on speculation.",
        },
        "never_simplify": list(NEVER_SIMPLIFY),
        "governed": ("every decision -> a signed DSSE receipt (host in-image ECDSA-P256 "
                     "signer) + an advisory Λ score. Conjecture 1 is OPEN; Λ kept < 1.0."),
        "measured": ("two-arm benchmark (baseline vs a11oy-restraint) ported from Ponytail's "
                     "promptfoo methodology; MEASURED only when a model run is wired, else "
                     "SAMPLE/ROADMAP."),
        "energy": "less code = fewer tokens = fewer joules; J/token tie-in, honestly labelled.",
        "provenance": {
            "adopted_from": "Ponytail (coding-agent skill)",
            "repo": PONYTAIL_REPO,
            "license": PONYTAIL_LICENSE,
            "stars": "4.6k",
            "relation": "adopted + governed (NOT invented here). Idea & ladder are Ponytail's.",
            "our_differentiators": ["signed DSSE receipts per decision", "Λ trust scoring",
                                    "measured-on-our-stack benchmarks", "J/token energy tie-in"],
            "citation": ("a11oy Restraint adopts the 6-rung ladder + lite/full/ultra intensity "
                         "from the open-source Ponytail skill (MIT, © 2026 DietrichGebert) and "
                         "adds governance (signed receipts + Λ) and honest measurement."),
        },
        "doctrine": {"version": DOCTRINE, "kernel_commit": KERNEL_COMMIT, "locked": LOCKED,
                     "lambda": "Conjecture 1 (OPEN) advisory floor < 1.0",
                     "slsa": "L1 honest; L2/L3 roadmap", "runtime_cdn": 0,
                     "signed_receipts": True, "visible_codenames": 0},
    }


# ---------------------------------------------------------------------------
# Route registration (matches the a11oy register(app, ns, sign_fn, ...) pattern).
# Routes insert at position 0 so they beat the SPA catch-all.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy", sign_fn: Optional[Callable[[Any], dict]] = None,
             verify_fn=None, signer_label: str = "in-image key",
             exporter_sample_fn: Optional[Callable[[], Any]] = None):
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    def _sample():
        if exporter_sample_fn is None:
            return None
        try:
            return exporter_sample_fn()
        except Exception:
            return None

    async def _evaluate(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        # Wave J (Dev 3): honest 400 on a malformed (non-object) body instead of a
        # 500 crash on b.get(...) — closes the silent-degrade/422 class.
        if not isinstance(b, dict):
            return JSONResponse({"error": "request body must be a JSON object",
                                 "got_type": type(b).__name__}, status_code=400)
        task = b.get("task") or b.get("prompt") or b.get("query") or ""
        intensity = b.get("intensity") or "full"
        lang = b.get("lang")
        if not task:
            return JSONResponse({"error": "provide a 'task' (the thing the code agent is about to build)",
                                 "example": {"task": "add a cache for these API responses", "intensity": "full"}},
                                status_code=400)
        out = evaluate(task, intensity=intensity, lang=lang, sign_fn=sign_fn,
                       exporter_sample=_sample())
        out["signer_label"] = signer_label
        return JSONResponse(out)

    async def _bench(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        intensity = b.get("intensity") or "full"
        # No model run wired in this Space path -> SAMPLE/ROADMAP, honestly labelled.
        return JSONResponse(benchmark(intensity=intensity, run_arm=None))

    async def _info(request):
        return JSONResponse(info())

    routes = [
        Route("/api/%s/v1/restraint/evaluate" % ns, _evaluate, methods=["POST"], name="%s_restraint_eval" % ns),
        Route("/api/%s/v1/restraint/bench" % ns, _bench, methods=["POST", "GET"], name="%s_restraint_bench" % ns),
        Route("/api/%s/v1/restraint/info" % ns, _info, methods=["GET"], name="%s_restraint_info" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "service": "a11oy.restraint", "doctrine": DOCTRINE}


if __name__ == "__main__":
    import json
    print("== info ==")
    print(json.dumps(info(), indent=2)[:300])
    for tsk, lv in [("validate an email address", "full"),
                    ("add a date picker", "full"),
                    ("build a generic pluggable plugin framework for later", "ultra"),
                    ("add a cache for these API responses", "full"),
                    ("sort this list of names", "full"),
                    ("write a bespoke distributed consensus protocol", "full")]:
        r = evaluate(tsk, intensity=lv)
        print("rung %d (%s) | Λ=%.3f | saved≈%d LOC | %s"
              % (r["stopped_at_rung"], r["rung_key"], r["lambda_score"]["lambda"],
                 r["lines_saved_estimate"]["lines_saved_modeled"], r["restraint_comment"]))
    b = benchmark()
    print("bench overall:", b["overall_label"], "median LOC reduction:",
          b["aggregate"]["median_loc_reduction_pct"], "%")
    assert info()["doctrine"]["locked"] == 8
    assert all(0.0 < evaluate(t)["lambda_score"]["lambda"] < 1.0 for t in BENCH_TASKS)
    print("OK — a11oy Restraint self-check passed.")
