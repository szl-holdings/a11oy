#!/usr/bin/env python3
"""Apply the reviewed command-center frontier repair to the feature branch.

This bootstrap is removed before the product commit. Every replacement is
fail-closed: an unexpected source shape aborts without committing partial work.
"""
from __future__ import annotations

import re
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one exact match, found {count}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, flags: int = 0) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(
            f"{path}: expected one regex match, found {count}: {pattern[:100]}"
        )
    write(path, updated)


# Brain hub: GET returns deterministic read-only evidence and never invokes signer.
replace_once(
    "szl_brain_hub.py",
    '''def build_pulse(ns: str = "a11oy") -> dict:
    """Build the current ecosystem pulse — the single beat every subscriber reads.

    Deterministic core (signed) + honest labels + a DSSE receipt. Volatile fields
    (generated timestamp) live OUTSIDE the signed body so the receipt is stable."""
    knowledge = knowledge_summary(ns)
    energy = energy_summary()
    lit = lit_summary(knowledge)
    core = _deterministic_core(ns, knowledge, energy, lit)
    receipt = _sign(core)
    return {''',
    '''def _read_only_receipt(core: dict) -> dict:
    """Return evidence for a read without signing, minting, or writing state."""
    return {
        "mode": "READ_ONLY",
        "signed": False,
        "signatures": [],
        "content_digest_sha256": _content_digest(core),
        "honesty": (
            "READ_ONLY — GET responses expose a deterministic digest only; "
            "no signature or receipt is minted by the read."
        ),
    }


def build_pulse(ns: str = "a11oy", *, sign_receipt: bool = True) -> dict:
    """Build the current ecosystem pulse.

    Explicit internal callers may request signing. HTTP GET handlers pass
    ``sign_receipt=False`` and expose only a deterministic digest.
    """
    knowledge = knowledge_summary(ns)
    energy = energy_summary()
    lit = lit_summary(knowledge)
    core = _deterministic_core(ns, knowledge, energy, lit)
    receipt = _sign(core) if sign_receipt else _read_only_receipt(core)
    return {''',
)
replace_once(
    "szl_brain_hub.py",
    '''        "receipt": receipt,
        "doctrine": _DOCTRINE,''',
    '''        "receipt": receipt,
        "read_only": not sign_receipt,
        "doctrine": _DOCTRINE,''',
)
replace_once(
    "szl_brain_hub.py",
    '''def handle_pulse(ns: str = "a11oy") -> dict:
    return build_pulse(ns)


def handle_subscribe(surface_id: str, ns: str = "a11oy") -> dict:
    return allocate_budget(build_pulse(ns), surface_id)''',
    '''def handle_pulse(ns: str = "a11oy") -> dict:
    return build_pulse(ns, sign_receipt=False)


def handle_subscribe(surface_id: str, ns: str = "a11oy") -> dict:
    return allocate_budget(build_pulse(ns, sign_receipt=False), surface_id)''',
)

# Brain command: GET routes use the same read-only evidence contract.
replace_once(
    "szl_brain_command.py",
    "import datetime\nfrom typing import Any, Optional\n",
    "import datetime\nimport hashlib\nimport json\nfrom typing import Any, Optional\n",
)
replace_once(
    "szl_brain_command.py",
    '''# --------------------------------------------------------------------------- #
# Knowledge summary — reuse a11oy_brain_graph's OWN honest headline. Never restate.
# --------------------------------------------------------------------------- #''',
    '''def _read_only_receipt(payload: dict) -> dict:
    """Deterministic evidence for GET responses; never invokes a signer."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "payloadType": _RECEIPT_TYPE,
        "mode": "READ_ONLY",
        "signed": False,
        "signatures": [],
        "content_digest_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "honesty": "READ_ONLY — this GET response did not sign, mint, or persist a receipt.",
    }


# --------------------------------------------------------------------------- #
# Knowledge summary — reuse a11oy_brain_graph's OWN honest headline. Never restate.
# --------------------------------------------------------------------------- #''',
)
replace_once(
    "szl_brain_command.py",
    '''                p = fn(ns) if _fn_takes_arg(fn) else fn()
                if isinstance(p, dict):''',
    '''                if fn_name == "build_pulse":
                    p = fn(ns, sign_receipt=False)
                else:
                    p = fn(ns) if _fn_takes_arg(fn) else fn()
                if isinstance(p, dict):''',
)
replace_once(
    "szl_brain_command.py",
    'def build_command(ns: str = "a11oy") -> dict:',
    'def build_command(ns: str = "a11oy", *, sign_receipt: bool = False) -> dict:',
)
replace_once(
    "szl_brain_command.py",
    '    payload["receipt"] = _sign(payload_snapshot(payload))\n',
    '    snapshot = payload_snapshot(payload)\n'
    '    payload["receipt"] = (\n'
    '        _sign(snapshot) if sign_receipt else _read_only_receipt(snapshot)\n'
    '    )\n'
    '    payload["read_only"] = not sign_receipt\n',
)
replace_once(
    "szl_brain_command.py",
    'def build_subscribe(surface_id: str, ns: str = "a11oy") -> dict:',
    'def build_subscribe(\n'
    '    surface_id: str,\n'
    '    ns: str = "a11oy",\n'
    '    *,\n'
    '    sign_receipt: bool = False,\n'
    ') -> dict:',
)
replace_once(
    "szl_brain_command.py",
    '''                        out["receipt"] = _sign({"view": "brain-subscribe", "surface_id": surface_id,
                                                "source": "brain-hub"})
                        return out''',
    '''                        receipt_core = {
                            "view": "brain-subscribe",
                            "surface_id": surface_id,
                            "source": "brain-hub",
                        }
                        out["receipt"] = (
                            _sign(receipt_core)
                            if sign_receipt
                            else _read_only_receipt(receipt_core)
                        )
                        out["read_only"] = not sign_receipt
                        return out''',
)
replace_once(
    "szl_brain_command.py",
    '    cmd = build_command(ns)\n',
    '    cmd = build_command(ns, sign_receipt=False)\n',
)
replace_once(
    "szl_brain_command.py",
    '''    out["receipt"] = _sign({"view": "brain-subscribe", "surface_id": surface_id,
                            "source": "local-fallback", "joules_share_modeled": joule_share})
    return out''',
    '''    receipt_core = {
        "view": "brain-subscribe",
        "surface_id": surface_id,
        "source": "local-fallback",
        "joules_share_modeled": joule_share,
    }
    out["receipt"] = (
        _sign(receipt_core)
        if sign_receipt
        else _read_only_receipt(receipt_core)
    )
    out["read_only"] = not sign_receipt
    return out''',
)
replace_once(
    "szl_brain_command.py",
    '        return JSONResponse(build_command(ns))\n',
    '        return JSONResponse(build_command(ns, sign_receipt=False))\n',
)
replace_once(
    "szl_brain_command.py",
    '        return JSONResponse(build_subscribe(surface_id, ns))\n',
    '        return JSONResponse(build_subscribe(surface_id, ns, sign_receipt=False))\n',
)

# Ecosystem GET routes: no hidden policy POST, signing, or verification writes.
regex_once(
    "szl_ecosystem_routes.py",
    r'\n\ndef _post_json\(.*?\n\n# ---------------------------------------------------------------------------\n# Estate data builders',
    '\n\n# ---------------------------------------------------------------------------\n# Estate data builders',
    flags=re.S,
)
regex_once(
    "szl_ecosystem_routes.py",
    r'def _chapaq_verdict\(\) -> Optional\[Dict\[str, Any\]\]:.*?\n\n\ndef build_kpi_board',
    '''def _chapaq_verdict() -> Optional[Dict[str, Any]]:
    """Read-only CHAPAQ status boundary.

    A verdict is a policy decision and requires an explicit authorized POST.
    The ecosystem KPI GET never submits a probe or decides for the operator.
    """
    legacy = _get_json(KILLINCHU_BASE + "/api/killinchu/v1/gov/chapaq-verdict")
    if isinstance(legacy, dict) and legacy.get("data"):
        legacy = dict(legacy)
        legacy["source"] = legacy.get("source") or "killinchu cached/read-only CHAPAQ verdict"
        legacy["read_only"] = True
        return legacy
    return {
        "data": None,
        "source": (
            "NOT_EVALUATED — CHAPAQ policy evaluation requires an explicit "
            "authorized state-changing request; GET performs no decision."
        ),
        "read_only": True,
    }


def build_kpi_board''',
    flags=re.S,
)
regex_once(
    "szl_ecosystem_routes.py",
    r'def build_ledger\(ns: str\) -> Dict\[str, Any\]:.*?\n\n\n# ---------------------------------------------------------------------------\n# HTML surfaces',
    '''def build_ledger(ns: str) -> Dict[str, Any]:
    """Read-only cross-app ledger inventory.

    GET fetches existing ledger state only. Cross-app signature verification is
    explicit and operator-authorized; this route never signs or POSTs an envelope.
    """
    a_ledger = _get_json(A11OY_BASE + "/api/a11oy/v1/provenance/ledger")
    k_ledger = _get_json(KILLINCHU_BASE + "/api/killinchu/v1/receipt/ledger")

    def keyid_of(value):
        if not isinstance(value, dict):
            return None
        envelope = value.get("envelope") or value.get("latest_envelope") or value
        signatures = envelope.get("signatures") if isinstance(envelope, dict) else None
        if isinstance(signatures, list) and signatures and isinstance(signatures[0], dict):
            return signatures[0].get("keyid")
        return None

    a_keyid = keyid_of(a_ledger)
    k_keyid = keyid_of(k_ledger)
    reachable = a_ledger is not None or k_ledger is not None
    return {
        "surface": "cross-app unified DSSE ledger",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "CACHED" if reachable else "UNAVAILABLE",
        "read_only": True,
        "scheme": "ECDSA-P256-SHA256 / cosign",
        "cosign_keyid": COSIGN_KEYID,
        "cosign_pub_url": COSIGN_PUB_URL,
        "a11oy_ledger": {
            "reachable": a_ledger is not None,
            "reported_count": a_ledger.get("count") if isinstance(a_ledger, dict) else None,
        },
        "killinchu_ledger": {
            "reachable": k_ledger is not None,
            "reported_count": k_ledger.get("count") if isinstance(k_ledger, dict) else None,
        },
        "a11oy_signer": {"keyid": a_keyid, "canonical": a_keyid == COSIGN_KEYID if a_keyid else None},
        "killinchu_signer": {"keyid": k_keyid, "canonical": k_keyid == COSIGN_KEYID if k_keyid else None},
        "cross_app_verify": {
            "killinchu_env_on_a11oy": "NOT_EVALUATED",
            "a11oy_env_on_killinchu": "NOT_EVALUATED",
            "same_cosign_chain": None,
            "note": (
                "Verification requires an explicit authorized action. "
                "This GET does not mint, sign, POST, or persist anything."
            ),
        },
        "verdict": (
            "NOT_EVALUATED — existing ledger metadata is visible, but no "
            "cross-app signature verification was executed by this read."
        ),
        "tamper": "tamper-evident, not tamper-proof (G3)",
        "pqc": "roadmap-only (G4) - never shown as deployed",
        "doctrine": "v11",
    }


# ---------------------------------------------------------------------------
# HTML surfaces''',
    flags=re.S,
)

# Rosie companion: typed names are unverified claims only and never authorize.
evolve_pattern = r'    def evolve\(self, strategy: dict\[str, Any\],.*?\n    def brain_jack\('
evolve_replacement = '''    def evolve(
        self,
        strategy: dict[str, Any],
        approvers: Optional[list[str]] = None,
        traceparent: Optional[str] = None,
    ) -> EvolveProposal:
        """Return a proposal only; typed approver names never authorize it.

        This companion has no trusted identity-verification boundary. A separate
        flagship gate must verify two independent signed approvals before execution.
        """
        claimed_approvers = sorted(
            {str(value).strip() for value in (approvers or []) if str(value).strip()}
        )
        axis_scores = strategy.get("axis_scores")
        query = "EVOLVE strategy proposal: " + json.dumps(
            strategy, sort_keys=True, default=str
        )[:800]
        rosie_json, stub, err = self._call_rosie_jack(
            "evolve", query, axis_scores, traceparent, payload_extra=strategy
        )
        L = rosie_json.get("lambda_signal", lambda_signal(axis_scores))
        gate_status = "AWAITING_VERIFIED_2P_YUYAY"
        companion_receipt = make_khipu_receipt(
            self.flagship,
            "evolve",
            query,
            axis_scores,
            traceparent,
            extra={
                "strategy": strategy,
                "approver_claims": claimed_approvers,
                "verified_approvers": [],
                "typed_names_authorize": False,
                "two_person_gate": gate_status,
            },
        )
        rosie_receipt = None if stub else rosie_json.get("lambda_receipt")
        xlink = cross_link_receipt(self.flagship, rosie_receipt, companion_receipt)
        return EvolveProposal(
            flagship=self.flagship,
            proposed_strategy=strategy,
            rationale=rosie_json.get("response_text", ""),
            lambda_signal=L,
            requires_two_person_gate=True,
            gate_status=gate_status,
            approvers=[],
            rosie_receipt=rosie_receipt,
            companion_receipt=companion_receipt,
            cross_link=xlink,
            stub=stub,
            error=err,
        )

    def brain_jack('''
for companion_path in (
    "szl_rosie_companion.py",
    "organs/amaru/szl_rosie_companion.py",
    "organs/sentra/szl_rosie_companion.py",
):
    regex_once(companion_path, evolve_pattern, evolve_replacement, flags=re.S)

# Readiness harness: unattended execution probes GET/HEAD only.
replace_once(
    "tools/readiness-harness/probe_runner.mjs",
    '''const RETRIES = parseInt(arg("retries", "2"), 10); // cold-burst 404s on deep tabs

const matrix''',
    '''const RETRIES = parseInt(arg("retries", "2"), 10); // cold-burst 404s on deep tabs
const SAFE_METHODS = new Set(["GET", "HEAD"]);
const STATE_CHANGE_AUTHORIZED =
  arg("allow-state-changing", false) === true &&
  process.env.A11OY_READINESS_MUTATION_AUTHORIZED === "1";

const matrix''',
)
replace_once(
    "tools/readiness-harness/probe_runner.mjs",
    '''async function probeEndpoint(path, spec) {
  const method = spec.method || "GET";
  const allow = (spec.degradedRules?.allowStatuses) || [200];''',
    '''async function probeEndpoint(path, spec) {
  const method = String(spec.method || "GET").toUpperCase();
  const allow = (spec.degradedRules?.allowStatuses) || [200];
  if (!SAFE_METHODS.has(method) && !STATE_CHANGE_AUTHORIZED) {
    return {
      path, method, status: null, error: null, skipped: true,
      skipReason: "state-changing contract skipped; require --allow-state-changing and A11OY_READINESS_MUTATION_AUTHORIZED=1",
      throttled: false, unreachable: false, p50: null, p95: null, samples: 0,
      schemaOk: null, citationOk: null, freshOk: null, ageSec: null,
      citationsRequired: !!spec.citationsRequired,
      freshnessSLA: spec.freshnessSLA ?? null,
      lie: false, lies: [],
    };
  }''',
)
replace_once(
    "tools/readiness-harness/probe_runner.mjs",
    '''    summary: {
      endpoints: results.length,
      ok: results.filter((r) => !r.lie && !r.unreachable && !r.throttled).length,
      lies: lies.length,
      unreachable: unreachable.length,
      throttled: throttled.length,
      p95_worst: Math.max(0, ...results.map((r) => r.p95 || 0)),
    },''',
    '''    summary: {
      endpoints: results.length,
      ok: results.filter((r) => !r.skipped && !r.lie && !r.unreachable && !r.throttled).length,
      skippedStateChanging: results.filter((r) => r.skipped).length,
      lies: lies.length,
      unreachable: unreachable.length,
      throttled: throttled.length,
      p95_worst: Math.max(0, ...results.map((r) => r.p95 || 0)),
    },''',
)
replace_once(
    "tools/readiness-harness/probe_runner.mjs",
    '''    const tag = r.lie ? "LIE " : r.unreachable ? "DOWN" : r.throttled ? "thr " : "ok  ";
    let why = "";
    if (r.lie) why = "  -> " + r.lies.join("; ");
    else if (r.unreachable) why = `  -> unreachable (${r.error || "status " + r.status})`;
    console.error(`  ${tag} ${r.status} p50=${r.p50}ms p95=${r.p95}ms ${r.path}${why}`);''',
    '''    const tag = r.skipped ? "skip" : r.lie ? "LIE " : r.unreachable ? "DOWN" : r.throttled ? "thr " : "ok  ";
    let why = "";
    if (r.skipped) why = "  -> " + r.skipReason;
    else if (r.lie) why = "  -> " + r.lies.join("; ");
    else if (r.unreachable) why = `  -> unreachable (${r.error || "status " + r.status})`;
    console.error(`  ${tag} ${r.status ?? "-"} p50=${r.p50 ?? "-"}ms p95=${r.p95 ?? "-"}ms ${r.path}${why}`);''',
)
replace_once(
    "tools/readiness-harness/probe_runner.mjs",
    '''  console.error(`[probe] ${verdict.summary.ok}/${verdict.summary.endpoints} clean, ${lies.length} lies, ${unreachable.length} unreachable, ${throttled.length} throttled. wrote ${OUT}`);''',
    '''  console.error(`[probe] ${verdict.summary.ok}/${verdict.summary.endpoints} clean, ${verdict.summary.skippedStateChanging} state-changing skipped, ${lies.length} lies, ${unreachable.length} unreachable, ${throttled.length} throttled. wrote ${OUT}`);''',
)

# Compact readiness summary view.
replace_once(
    "serve.py",
    '    from fastapi.responses import JSONResponse as _RDJSON\n',
    '    from fastapi import Request as _RDRequest\n'
    '    from fastapi.responses import JSONResponse as _RDJSON\n',
)
replace_once(
    "serve.py",
    '''    @app.get("/api/a11oy/v1/readiness/tab-matrix")
    async def _a11oy_readiness_tab_matrix():  # noqa: ANN202
        matrix = _rd_load((''',
    '''    @app.get("/api/a11oy/v1/readiness/tab-matrix")
    async def _a11oy_readiness_tab_matrix(request: _RDRequest):  # noqa: ANN202
        view = (request.query_params.get("view") or "full").strip().lower()
        matrix = _rd_load((''',
)
replace_once(
    "serve.py",
    '''        _verdict_available = verdict is not None
        if _verdict_available:
            verdict = dict(verdict)
            verdict["available"] = True
        return _RDJSON({''',
    '''        _verdict_available = verdict is not None
        if _verdict_available:
            verdict = dict(verdict)
            verdict["available"] = True
        if view == "summary":
            matrix_summary = dict(matrix.get("summary") or {}) if isinstance(matrix, dict) else {}
            verdict_summary = dict(verdict.get("summary") or {}) if isinstance(verdict, dict) else None
            return _RDJSON({
                "layer": "a11oy readiness tab-matrix",
                "view": "summary",
                "honest": True,
                "available": _verdict_available,
                "matrix_available": True,
                "probe_verdict_available": _verdict_available,
                "matrix_summary": matrix_summary,
                "verdict_summary": verdict_summary,
                "checked_at": _now,
            }, status_code=200)
        return _RDJSON({''',
)

# Universal mobile/keyboard evidence rail for every holographic surface.
evidence_css = r'''
 /* ---- Universal evidence rail ----------------------------------------- */
 .evidence-rail{position:fixed;right:12px;bottom:48px;z-index:65;width:min(390px,calc(100vw - 24px));
  border:1px solid var(--line);border-radius:11px;background:rgba(7,13,21,.97);
  box-shadow:0 14px 40px rgba(0,0,0,.55);font:11px/1.45 ui-monospace,monospace}
 .evidence-rail__toggle{width:100%;display:flex;align-items:center;justify-content:space-between;
  gap:10px;padding:8px 11px;border:0;border-radius:10px;background:#0b1620;color:var(--cream);
  font:11px ui-monospace,monospace;cursor:pointer;text-align:left}
 .evidence-rail__toggle:focus-visible{outline:2px solid var(--proof);outline-offset:2px}
 .evidence-rail__state{color:var(--gold);white-space:nowrap}
 .evidence-rail[data-state="OBSERVED"] .evidence-rail__state{color:var(--proof)}
 .evidence-rail__panel{border-top:1px solid var(--line);padding:10px 11px;color:var(--para)}
 .evidence-rail__panel[hidden]{display:none}
 .evidence-rail__title{display:block;color:var(--cream);margin-bottom:5px}
 .evidence-rail__row{display:grid;grid-template-columns:88px minmax(0,1fr);gap:8px;padding:2px 0}
 .evidence-rail__row span:first-child{color:#738796;text-transform:uppercase;font-size:9px}
 .evidence-rail__row code{overflow-wrap:anywhere;color:var(--teal)}
 .evidence-rail__links{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
 .evidence-rail__links a{border:1px solid var(--line);border-radius:6px;padding:4px 7px}
 @media (max-width:640px){.evidence-rail{right:8px;left:8px;bottom:42px;width:auto}.evidence-rail__panel{max-height:38vh;overflow:auto}}
 @media (prefers-reduced-motion:reduce){.evidence-rail *{scroll-behavior:auto!important;transition:none!important}}
'''
replace_once("static/3d/holographic.html", "</style>", evidence_css + "\n</style>")
evidence_html = '''<aside id="evidence-rail" class="evidence-rail" data-state="UNVERIFIED"
 aria-label="Active surface evidence" aria-live="polite">
 <button id="evidence-rail-toggle" class="evidence-rail__toggle" type="button"
  aria-expanded="false" aria-controls="evidence-rail-panel">
  <span>Evidence · active surface</span><span id="evidence-rail-state" class="evidence-rail__state">UNVERIFIED</span>
 </button>
 <div id="evidence-rail-panel" class="evidence-rail__panel" hidden>
  <strong id="evidence-rail-title" class="evidence-rail__title">Loading surface</strong>
  <div class="evidence-rail__row"><span>Surface</span><code id="evidence-rail-id">—</code></div>
  <div class="evidence-rail__row"><span>Contract</span><code id="evidence-rail-contract">—</code></div>
  <div class="evidence-rail__row"><span>Runtime</span><span id="evidence-rail-runtime">NOT_EVALUATED</span></div>
  <div class="evidence-rail__row"><span>Readiness</span><span id="evidence-rail-readiness">NOT_EVALUATED</span></div>
  <div class="evidence-rail__links"><a href="/api/a11oy/v1/readiness/tab-matrix?view=summary">Readiness JSON</a><a href="/api/build-info">Build identity</a><a href="/verify">Verify receipt</a></div>
 </div>
</aside>
'''
replace_once(
    "static/3d/holographic.html",
    '<div id="surface-caption" title=""></div>',
    evidence_html + '<div id="surface-caption" title=""></div>',
)
evidence_js = r'''
const evidenceRail = document.getElementById("evidence-rail");
const evidenceToggle = document.getElementById("evidence-rail-toggle");
const evidencePanel = document.getElementById("evidence-rail-panel");
const evidenceState = document.getElementById("evidence-rail-state");
const evidenceTitle = document.getElementById("evidence-rail-title");
const evidenceId = document.getElementById("evidence-rail-id");
const evidenceContract = document.getElementById("evidence-rail-contract");
const evidenceRuntime = document.getElementById("evidence-rail-runtime");
const evidenceReadiness = document.getElementById("evidence-rail-readiness");
let evidenceSnapshotPromise = null;
if (evidenceToggle && evidencePanel) {
  evidenceToggle.addEventListener("click", () => {
    const open = evidenceToggle.getAttribute("aria-expanded") !== "true";
    evidenceToggle.setAttribute("aria-expanded", String(open));
    evidencePanel.hidden = !open;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !evidencePanel.hidden) {
      evidenceToggle.setAttribute("aria-expanded", "false");
      evidencePanel.hidden = true;
      evidenceToggle.focus();
    }
  });
}
async function _fetchEvidenceSnapshot() {
  if (evidenceSnapshotPromise) return evidenceSnapshotPromise;
  evidenceSnapshotPromise = (async () => {
    const getJson = async (url) => {
      try {
        const response = await fetch(url, {method:"GET",headers:{accept:"application/json"},cache:"no-store"});
        return response.ok ? await response.json() : null;
      } catch (_) { return null; }
    };
    const [readiness, build] = await Promise.all([
      getJson("/api/a11oy/v1/readiness/tab-matrix?view=summary"),
      getJson("/api/build-info"),
    ]);
    return { readiness, build };
  })();
  return evidenceSnapshotPromise;
}
function _updateEvidenceRail(def) {
  if (!evidenceRail || !def) return;
  evidenceRail.dataset.state = "UNVERIFIED";
  if (evidenceState) evidenceState.textContent = "UNVERIFIED";
  if (evidenceTitle) evidenceTitle.textContent = def.title;
  if (evidenceId) evidenceId.textContent = def.id;
  if (evidenceContract) evidenceContract.textContent = `${catOf(def)} · ${def.mod}`;
  if (evidenceRuntime) evidenceRuntime.textContent = "CHECKING";
  if (evidenceReadiness) evidenceReadiness.textContent = "CHECKING";
  _fetchEvidenceSnapshot().then(({ readiness, build }) => {
    const buildState = build?.build?.state || build?.state || "UNAVAILABLE";
    const revision = build?.build?.revision || build?.revision || null;
    if (evidenceRuntime) evidenceRuntime.textContent = revision ? `${buildState} · ${String(revision).slice(0,12)}…` : buildState;
    const matrix = readiness?.matrix_summary || {};
    const verdict = readiness?.verdict_summary || null;
    if (evidenceReadiness) evidenceReadiness.textContent = verdict ? `${verdict.ok ?? 0}/${verdict.endpoints ?? matrix.endpoints ?? 0} observed clean` : `${matrix.tabs ?? SURFACES.length} surfaces · probe UNAVAILABLE`;
    const observed = Boolean(revision && readiness?.matrix_available);
    evidenceRail.dataset.state = observed ? "OBSERVED" : "UNVERIFIED";
    if (evidenceState) evidenceState.textContent = observed ? "OBSERVED" : "UNVERIFIED";
  });
}
'''
replace_once(
    "static/3d/holographic.html",
    '''const activeSurface = document.querySelector("#active-surface strong");
const _panels = {};''',
    '''const activeSurface = document.querySelector("#active-surface strong");
''' + evidence_js + '''const _panels = {};''',
)
replace_once(
    "static/3d/holographic.html",
    '''  if (activeSurface) {
    activeSurface.textContent = def ? _shortLabel(def) : id;
    activeSurface.title = def ? def.title : id;
  }
  const matches''',
    '''  if (activeSurface) {
    activeSurface.textContent = def ? _shortLabel(def) : id;
    activeSurface.title = def ? def.title : id;
  }
  _updateEvidenceRail(def);
  const matches''',
)

# Focused regressions.
Path("tests/test_command_center_readonly_contract.py").write_text(
    '''from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _boom(*_args, **_kwargs):
    raise AssertionError("signer must not run for a GET/read-only path")


def test_brain_get_paths_never_sign(monkeypatch):
    hub = importlib.import_module("szl_brain_hub")
    monkeypatch.setattr(hub, "_sign", _boom)
    pulse = hub.handle_pulse("a11oy")
    assert pulse["read_only"] is True
    assert pulse["receipt"]["mode"] == "READ_ONLY"
    assert pulse["receipt"]["signed"] is False
    budget = hub.handle_subscribe("brain", "a11oy")
    assert budget["pulse_receipt_digest"]


def test_brain_command_get_paths_never_sign(monkeypatch):
    command = importlib.import_module("szl_brain_command")
    monkeypatch.setattr(command, "_sign", _boom)
    result = command.build_command("a11oy")
    assert result["read_only"] is True
    assert result["receipt"]["mode"] == "READ_ONLY"
    subscription = command.build_subscribe("brain", "a11oy")
    assert subscription["read_only"] is True
    assert subscription["receipt"]["mode"] == "READ_ONLY"


def test_ecosystem_gets_contain_no_hidden_posts():
    source = (ROOT / "szl_ecosystem_routes.py").read_text(encoding="utf-8")
    assert "def _post_json" not in source
    assert 'method="POST"' not in source
    assert "NOT_EVALUATED" in source
    assert "GET does not mint, sign, POST, or persist" in source


def test_typed_approver_names_never_authorize(monkeypatch):
    companion = importlib.import_module("szl_rosie_companion")
    shadow = companion.RosieShadow("a11oy")
    monkeypatch.setattr(
        shadow,
        "_call_rosie_jack",
        lambda *_args, **_kwargs: (
            {"response_text": "proposal only", "lambda_signal": 0.5, "lambda_receipt": None},
            False,
            None,
        ),
    )
    proposal = shadow.evolve(
        {"goal": "frontier", "axis_scores": [0.5] * 13},
        approvers=["Alice", "Bob", "Alice"],
    )
    assert proposal.gate_status == "AWAITING_VERIFIED_2P_YUYAY"
    assert proposal.approvers == []
    meta = proposal.companion_receipt["meta"]
    assert meta["approver_claims"] == ["Alice", "Bob"]
    assert meta["typed_names_authorize"] is False


def test_companion_copies_remain_byte_identical():
    paths = [
        ROOT / "szl_rosie_companion.py",
        ROOT / "organs/amaru/szl_rosie_companion.py",
        ROOT / "organs/sentra/szl_rosie_companion.py",
    ]
    bodies = [path.read_bytes() for path in paths]
    assert bodies[0] == bodies[1] == bodies[2]


def test_readiness_runner_is_safe_by_default():
    source = (ROOT / "tools/readiness-harness/probe_runner.mjs").read_text(encoding="utf-8")
    assert 'new Set(["GET", "HEAD"])' in source
    assert "A11OY_READINESS_MUTATION_AUTHORIZED" in source
    assert "state-changing contract skipped" in source
    assert "skippedStateChanging" in source


def test_compact_readiness_and_evidence_rail_are_wired():
    serve = (ROOT / "serve.py").read_text(encoding="utf-8")
    assert 'request.query_params.get("view")' in serve
    assert '"view": "summary"' in serve
    assert '"matrix_summary": matrix_summary' in serve
    html = (ROOT / "static/3d/holographic.html").read_text(encoding="utf-8")
    assert 'id="evidence-rail"' in html
    assert 'aria-label="Active surface evidence"' in html
    assert "_updateEvidenceRail(def);" in html
    assert "prefers-reduced-motion:reduce" in html
''',
    encoding="utf-8",
)

print("command-center frontier repairs applied")
