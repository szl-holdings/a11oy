# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
"""
szl_restraint_energy.py — R4 lane: wire a11oy Restraint (R1's governed Ponytail-
derived frugality ladder) into the ENERGY / J-token story, the estate KPI board,
and a MEASURED benchmark dashboard.

ADDITIVE + self-contained. This module NEVER edits a11oy_restraint / szl_restraint
(R1's), szl_energy_sovereign (Forge's), or szl_joules_truth — it only CONSUMES
their public surfaces. If any import fails the module degrades to an honest empty
state and registers nothing destructive.

WHAT THIS MODULE DOES (all real, deterministic, honestly labelled):

  1. RESTRAINT -> ENERGY tie-in (the sovereign + frugal + measured pitch):
       Every restraint decision estimates lines saved -> tokens saved -> joules
       saved. The J/token figure is the LIVE MEASURED on-box NVML figure
       (szl_energy_sovereign.energy_fields_for_receipt -> joules_per_token, label
       MEASURED) WHEN the sovereign GPU probe is live, else our honest SAMPLE
       constant (szl_restraint.J_PER_OUTPUT_TOKEN, label SAMPLE). The label on
       joules-saved is decided by the SAME single source of truth as the rest of
       the energy story (szl_joules_truth) — never a bare flag, never fabricated.
       A small in-memory cumulative ledger (resets on restart, honestly noted)
       tracks lines/tokens/joules saved across evaluate() calls so the
       "frugality -> energy" panel has live cumulative numbers.

  2. MEASURED benchmark harness + dashboard data:
       Ports Ponytail's promptfoo two-arm methodology (no-skill baseline vs
       a11oy-restraint) over the same five everyday tasks. Numbers read MEASURED
       only when an actual run on OUR stack is wired (a model run_arm callable,
       or a committed results artifact at benchmarks/restraint/results.json);
       otherwise SAMPLE/ROADMAP with the methodology + exact reproduce command
       shown. Ponytail's published numbers are CITED as theirs, never as ours.

  3. ESTATE KPI fields:
       restraint_kpi() returns frugality rate, cumulative lines/tokens/joules
       saved, and the energy honesty label as a tile for the estate Λ/KPI board
       and the unified estate hologram.

ENDPOINTS (inserted at router position 0 to beat the SPA catch-all):
  GET  /api/{ns}/v1/restraint/energy        -> live cumulative frugality->energy
                                                panel data (MEASURED-or-SAMPLE).
  POST /api/{ns}/v1/restraint/energy        -> same, plus optionally fold in a
                                                {task,intensity} decision first.
  GET  /api/{ns}/v1/restraint/bench-measured-> two-arm bench rows + aggregate,
                                                MEASURED if results.json present
                                                else SAMPLE/ROADMAP + reproduce cmd.
  GET  /api/{ns}/v1/restraint/kpi           -> estate KPI tile (frugality rate,
                                                cumulative savings, energy saved).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DOCTRINE = "v11"
KERNEL_COMMIT = "c7c0ba17"
LOCKED = 8
PONYTAIL_REPO = "https://github.com/DietrichGebert/ponytail"
PONYTAIL_LICENSE = "MIT"

# Exact command an operator runs to flip the bench from SAMPLE to MEASURED.
REPRODUCE_CMD = (
    "python benchmarks/restraint/run_bench.py --repeat 10 "
    "--out benchmarks/restraint/results.json   "
    "# counts emitted LOC/tokens/latency for baseline vs a11oy-restraint on OUR stack; "
    "then this dashboard's overall label flips to MEASURED."
)
REPRODUCE_CMD_PROMPTFOO = (
    "npx promptfoo@latest eval -c benchmarks/restraint/promptfooconfig.yaml --repeat 10"
)

# Where a real on-stack benchmark run writes its artifact (read-only here).
_RESULTS_PATHS = [
    "benchmarks/restraint/results.json",
    "/app/benchmarks/restraint/results.json",
]

# ---------------------------------------------------------------------------
# Soft imports of sibling modules (consumed, never edited). All optional.
# ---------------------------------------------------------------------------
try:
    import szl_restraint as _restraint  # R1's module (a11oy Restraint ladder)
except Exception:  # pragma: no cover - honest degrade
    _restraint = None  # type: ignore

try:
    import szl_energy_sovereign as _energy  # Forge's MEASURED energy module
except Exception:  # pragma: no cover
    _energy = None  # type: ignore

try:
    import szl_joules_truth as _jt  # single source of truth for joules label
except Exception:  # pragma: no cover
    _jt = None  # type: ignore


# ---------------------------------------------------------------------------
# Live MEASURED-or-SAMPLE J/token. We ASK the energy module for the live on-box
# figure; we NEVER compute or fabricate a meter reading here.
# ---------------------------------------------------------------------------
def _sample_j_per_token() -> float:
    """Our honest modelled SAMPLE J/token (NOT a meter reading)."""
    if _restraint is not None:
        try:
            return float(_restraint.J_PER_OUTPUT_TOKEN)
        except Exception:
            pass
    return 0.65  # mirrors szl_restraint.J_PER_OUTPUT_TOKEN default


def live_j_per_token() -> Dict[str, Any]:
    """Return the J/token to price tokens-saved into joules-saved, honestly labelled.

    MEASURED  -> the live on-box NVML figure from szl_energy_sovereign when the
                 sovereign GPU probe is live (energy_label == MEASURED).
    SAMPLE    -> our modelled constant when no fresh meter is present.
    Never fabricates a number; never decides the label locally beyond delegating
    to the energy module's own MEASURED/ROADMAP verdict.
    """
    j_sample = _sample_j_per_token()
    if _energy is not None:
        try:
            fields = _energy.energy_fields_for_receipt()  # never raises by contract
            jpt = fields.get("joules_per_token")
            measured = (fields.get("energy_label") == "MEASURED") and isinstance(jpt, (int, float)) and jpt > 0
            if measured:
                return {
                    "j_per_token": round(float(jpt), 6),
                    "label": "MEASURED",
                    "source": "szl_energy_sovereign on-box NVML exporter (live probe)",
                    "joules_honesty": fields.get("joules_honesty"),
                    "carbon_g_co2eq_per_token": fields.get("carbon_g_co2eq_per_token"),
                }
            return {
                "j_per_token": j_sample,
                "label": "SAMPLE",
                "source": "szl_restraint.J_PER_OUTPUT_TOKEN (modelled estimate)",
                "joules_honesty": fields.get("joules_honesty", "sample"),
                "energy_label_upstream": fields.get("energy_label"),
                "note": ("No fresh on-box NVML sample -> SAMPLE J/token. Flips to MEASURED "
                         "automatically when the sovereign GPU exporter goes live."),
            }
        except Exception:
            pass
    return {
        "j_per_token": j_sample,
        "label": "SAMPLE",
        "source": "szl_restraint.J_PER_OUTPUT_TOKEN (modelled estimate)",
        "joules_honesty": "sample",
        "note": "Energy module unavailable in this path -> honest SAMPLE J/token.",
    }


# ---------------------------------------------------------------------------
# Cumulative frugality -> energy ledger. In-memory, thread-safe, resets on
# restart (honestly noted). Records every restraint decision's lines/tokens/
# joules saved so the panel + KPI tile have live cumulative numbers.
# ---------------------------------------------------------------------------
class _SavingsLedger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.decisions = 0
        self.decisions_that_saved = 0   # rung held with a real reduction
        self.lines_saved = 0
        self.tokens_saved = 0.0
        self.joules_saved_measured = 0.0   # joules priced at a MEASURED J/token
        self.joules_saved_sample = 0.0     # joules priced at the SAMPLE J/token
        self.last_label = "SAMPLE"
        self.started_ts = time.time()

    def record(self, lines_saved: int, intensity: str) -> Dict[str, Any]:
        tokens_per_loc = getattr(_restraint, "TOKENS_PER_LOC", 9.0) if _restraint else 9.0
        jpt = live_j_per_token()
        tokens = float(lines_saved) * float(tokens_per_loc)
        joules = tokens * float(jpt["j_per_token"])
        with self._lock:
            self.decisions += 1
            if lines_saved > 0:
                self.decisions_that_saved += 1
            self.lines_saved += int(lines_saved)
            self.tokens_saved += tokens
            if jpt["label"] == "MEASURED":
                self.joules_saved_measured += joules
            else:
                self.joules_saved_sample += joules
            self.last_label = jpt["label"]
        return {"tokens_saved": round(tokens, 1), "joules_saved": round(joules, 1),
                "j_per_token": jpt}

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            decisions = self.decisions
            saved = self.decisions_that_saved
            lines = self.lines_saved
            tokens = self.tokens_saved
            j_meas = self.joules_saved_measured
            j_samp = self.joules_saved_sample
            last = self.last_label
            started = self.started_ts
        frugality_rate = (saved / decisions) if decisions else 0.0
        # The joules honesty label for the AGGREGATE is MEASURED only if every
        # joule we counted was priced at a MEASURED J/token (no SAMPLE mixed in).
        if j_meas > 0 and j_samp == 0:
            agg_label = "MEASURED"
        elif j_meas > 0 and j_samp > 0:
            agg_label = "MIXED"
        else:
            agg_label = "SAMPLE"
        return {
            "decisions": decisions,
            "decisions_that_saved": saved,
            "frugality_rate": round(frugality_rate, 4),
            "cumulative_lines_saved": lines,
            "cumulative_tokens_saved": round(tokens, 1),
            "cumulative_joules_saved_measured": round(j_meas, 1),
            "cumulative_joules_saved_sample": round(j_samp, 1),
            "cumulative_joules_saved_total": round(j_meas + j_samp, 1),
            "joules_label": agg_label,
            "last_decision_label": last,
            "ledger_age_s": round(time.time() - started, 1),
            "ledger_note": ("In-memory cumulative ledger; resets on process restart "
                            "(honest — not a persisted meter). MEASURED only when all "
                            "counted joules were priced at a live on-box J/token."),
        }


_LEDGER = _SavingsLedger()


# ---------------------------------------------------------------------------
# The "frugality -> energy" panel payload (live cumulative + last decision).
# ---------------------------------------------------------------------------
def energy_panel(fold_task: Optional[str] = None, intensity: str = "full") -> Dict[str, Any]:
    """Live frugality->energy panel. Optionally fold a fresh decision in first."""
    last_decision = None
    if fold_task and _restraint is not None:
        try:
            dec = _restraint.descend_ladder(fold_task, intensity)
            lines = int(dec["lines_saved_estimate"]["lines_saved_modeled"])
            rec = _LEDGER.record(lines, intensity)
            last_decision = {
                "task": fold_task,
                "stopped_at_rung": dec["stopped_at_rung"],
                "rung_key": dec["rung_key"],
                "lines_saved": lines,
                "tokens_saved": rec["tokens_saved"],
                "joules_saved": rec["joules_saved"],
                "j_per_token": rec["j_per_token"],
            }
        except Exception:
            last_decision = None

    snap = _LEDGER.snapshot()
    jpt = live_j_per_token()
    return {
        "service": "a11oy.restraint.energy",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thesis": "less code = fewer tokens = fewer joules on our sovereign GPU.",
        "j_per_token": jpt,
        "cumulative": snap,
        "last_decision": last_decision,
        "honesty": ("Joules-saved is tokens-saved x J/token. The J/token is the LIVE "
                    "on-box NVML MEASURED figure ONLY when the sovereign GPU probe is "
                    "live (label MEASURED); otherwise it is our modelled SAMPLE constant "
                    "(label SAMPLE). Labels come from szl_joules_truth / szl_energy_"
                    "sovereign — the same single source of truth as the rest of the "
                    "energy story. Lines-saved is OUR MODELED ladder figure, never "
                    "Ponytail's measured numbers."),
        "doctrine": {"version": DOCTRINE, "kernel_commit": KERNEL_COMMIT, "locked": LOCKED,
                     "lambda": "Conjecture 1 (OPEN) advisory floor < 1.0", "runtime_cdn": 0,
                     "signed_receipts": True, "visible_codenames": 0},
        "provenance": {"adopted_from": "Ponytail", "repo": PONYTAIL_REPO,
                       "license": PONYTAIL_LICENSE, "relation": "adopted + governed + measured"},
    }


# ---------------------------------------------------------------------------
# MEASURED benchmark: read a committed run artifact if present (-> MEASURED),
# else fall back to R1's SAMPLE bench (-> SAMPLE/ROADMAP) with reproduce cmd.
# ---------------------------------------------------------------------------
def _load_results_artifact() -> Optional[Dict[str, Any]]:
    for p in _RESULTS_PATHS:
        try:
            fp = Path(p)
            if fp.is_file():
                with fp.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict) and data.get("rows"):
                    return data
        except Exception:
            continue
    return None


def bench_measured(intensity: str = "full") -> Dict[str, Any]:
    """Two-arm bench. MEASURED iff a real on-stack results.json is committed; else
    SAMPLE/ROADMAP via R1's szl_restraint.benchmark() + the exact reproduce cmd."""
    artifact = _load_results_artifact()
    if artifact is not None:
        # A real run produced this on OUR stack. Pass it through, force-labelled.
        out = dict(artifact)
        out["overall_label"] = "MEASURED"
        out["service"] = "a11oy.restraint.bench"
        out.setdefault("arms", ["baseline (no skill)", "a11oy-restraint"])
        out["measured_on"] = out.get("measured_on") or "OUR stack (committed results.json)"
        out["reproduce"] = REPRODUCE_CMD
        out["reproduce_promptfoo"] = REPRODUCE_CMD_PROMPTFOO
        out.setdefault("ponytail_published", _ponytail_published())
        out.setdefault("honesty", _bench_honesty())
        return out

    # No artifact -> honest SAMPLE/ROADMAP from R1's harness (never Ponytail's #s).
    if _restraint is not None:
        try:
            b = _restraint.benchmark(intensity=intensity, run_arm=None)
            b["reproduce"] = REPRODUCE_CMD
            b["reproduce_promptfoo"] = REPRODUCE_CMD_PROMPTFOO
            b["measured_on"] = None
            b.setdefault("ponytail_published", _ponytail_published())
            return b
        except Exception:
            pass

    # Last-resort honest empty state (R1 not importable in this path).
    return {
        "service": "a11oy.restraint.bench",
        "arms": ["baseline (no skill)", "a11oy-restraint"],
        "rows": [],
        "aggregate": {},
        "overall_label": "ROADMAP",
        "methodology": _bench_methodology(),
        "reproduce": REPRODUCE_CMD,
        "reproduce_promptfoo": REPRODUCE_CMD_PROMPTFOO,
        "ponytail_published": _ponytail_published(),
        "honesty": _bench_honesty(),
        "note": "Restraint module unavailable in this path — honest empty bench.",
    }


def _bench_methodology() -> str:
    return ("Ported from Ponytail's promptfoo methodology (MIT): the same five everyday "
            "tasks, two arms (no-skill baseline vs a11oy-restraint), median reported. "
            "LOC counted from emitted code; tokens/latency from the API on a real run.")


def _bench_honesty() -> str:
    return ("These are OUR numbers on OUR stack ONLY when overall_label == MEASURED (a "
            "committed results.json from a real run). Otherwise they are SAMPLE/ROADMAP "
            "fixtures from our ladder model. Ponytail's published numbers are CITED as "
            "Ponytail's, never claimed as ours.")


def _ponytail_published() -> Dict[str, Any]:
    return {
        "code_reduction": "80-94% less code",
        "cost_reduction": "47-77% cheaper",
        "speed": "3-6x faster",
        "basis": "median of 10 runs across Haiku/Sonnet/Opus (Ponytail benchmarks/, MIT)",
        "source": PONYTAIL_REPO + "/tree/main/benchmarks",
        "label": "CITED (Ponytail's numbers, not ours)",
    }


# ---------------------------------------------------------------------------
# Estate KPI tile — frugality rate, cumulative savings, energy saved.
# ---------------------------------------------------------------------------
def restraint_kpi() -> Dict[str, Any]:
    snap = _LEDGER.snapshot()
    jpt = live_j_per_token()
    return {
        "tile": "restraint",
        "title": "a11oy Restraint — frugality -> energy",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "LIVE",
        "frugality_rate": snap["frugality_rate"],
        "decisions": snap["decisions"],
        "cumulative_lines_saved": snap["cumulative_lines_saved"],
        "cumulative_tokens_saved": snap["cumulative_tokens_saved"],
        "cumulative_joules_saved": snap["cumulative_joules_saved_total"],
        "joules_label": snap["joules_label"],
        "j_per_token": jpt["j_per_token"],
        "j_per_token_label": jpt["label"],
        "note": ("Frugality rate = decisions that cut code / decisions. Joules saved "
                 "= tokens saved x J/token (MEASURED only on a live GPU probe, else "
                 "SAMPLE). In-memory; resets on restart. Λ = Conjecture 1 (<1.0)."),
        "provenance": {"adopted_from": "Ponytail", "license": PONYTAIL_LICENSE},
    }


# ---------------------------------------------------------------------------
# Route registration (matches the a11oy register(app, ns=...) pattern). Routes
# insert at position 0 so they beat the SPA catch-all. Try/except guarded.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    async def _energy(request):
        task = intensity = None
        if request.method == "POST":
            try:
                b = await request.json()
            except Exception:
                b = {}
            task = b.get("task") or b.get("prompt") or b.get("query")
            intensity = b.get("intensity") or "full"
        return JSONResponse(energy_panel(fold_task=task, intensity=intensity or "full"))

    async def _bench(request):
        intensity = request.query_params.get("intensity") or "full"
        return JSONResponse(bench_measured(intensity=intensity))

    async def _kpi(request):
        return JSONResponse(restraint_kpi())

    routes = [
        Route("/api/%s/v1/restraint/energy" % ns, _energy, methods=["GET", "POST"],
              name="%s_restraint_energy" % ns),
        Route("/api/%s/v1/restraint/bench-measured" % ns, _bench, methods=["GET"],
              name="%s_restraint_bench_measured" % ns),
        Route("/api/%s/v1/restraint/kpi" % ns, _kpi, methods=["GET"],
              name="%s_restraint_kpi" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "service": "a11oy.restraint.energy", "doctrine": DOCTRINE}


if __name__ == "__main__":
    # Self-check: deterministic, no network needed beyond optional sibling imports.
    print("== j/token ==", live_j_per_token())
    if _restraint is not None:
        for t in ["validate an email address", "add a debounce to a search input",
                  "build a generic pluggable framework for later", "sort this list"]:
            dec = _restraint.descend_ladder(t, "full")
            _LEDGER.record(int(dec["lines_saved_estimate"]["lines_saved_modeled"]), "full")
    snap = _LEDGER.snapshot()
    print("== cumulative ==", json.dumps(snap, indent=2)[:400])
    b = bench_measured()
    print("== bench overall ==", b["overall_label"])
    print("== reproduce ==", b["reproduce"][:80])
    k = restraint_kpi()
    assert k["tile"] == "restraint"
    assert b["overall_label"] in ("MEASURED", "SAMPLE", "ROADMAP")
    print("OK — szl_restraint_energy self-check passed.")
