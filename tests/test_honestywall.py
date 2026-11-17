"""feat/frontier-honestywall — Honesty Wall contract guard.

The Honesty Wall aggregates the estate's OWN honesty invariants across every
registered frontier surface into a single verifiable verdict. These tests pin the
honest-by-construction invariants that make it trustworthy — no mocks of the honesty
logic itself, only controlled surface inputs where a real violation cannot be forced:

  1. Routes (GET status/info, POST aggregate) are registered and answer 200 (never
     500), BEFORE the SPA / Node-proxy catch-alls.
  2. RECEIPT-ON-WRITE-NOT-ON-READ: GET status mints NOTHING; POST aggregate emits ONE
     UNSIGNED SHA-256 content-digest receipt (signed is False).
  3. NEVER INTACT if anything is violated: when a surface's manifest declares a
     violated invariant, the verdict is VIOLATED (not INTACT/DEGRADED).
  4. Unreachable manifest -> UNKNOWN (degrades to DEGRADED, never a fabricated pass).
  5. NEVER upgrades a label: a surface's declared honest label is read VERBATIM.
  6. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1, trust 0.97 (never 100%).
  7. The honest vocabulary recognises DECLARED (asserted, not measured, never upgraded),
     so an honestly-labelled surface is SATISFIED instead of falsely flagged.
  8. The honest vocabulary recognises UNKNOWN (public-estate contract truthVocabulary; reachable but
     unverified), so the sovereign health surface is SATISFIED and never upgraded, while a
     non-vocabulary label is still VIOLATED.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import pytest

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402
import szl_frontier_index as fi  # noqa: E402
import szl_honestywall as hw  # noqa: E402

STATUS = "/api/a11oy/v1/govern/honestywall/status"
INFO = "/api/a11oy/v1/govern/honestywall/info"
AGG = "/api/a11oy/v1/govern/honestywall/aggregate"
VERDICTS = {hw.INTACT, hw.VERDICT_DEGRADED, hw.VERDICT_VIOLATED}


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


# --------------------------------------------------------------------------- #
# 1. registration + ordering
# --------------------------------------------------------------------------- #
def test_routes_registered_before_catchalls():
    for path in (STATUS, INFO, AGG):
        assert _route_index(path) is not None, f"{path} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    for path in (STATUS, INFO, AGG):
        idx = _route_index(path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


# --------------------------------------------------------------------------- #
# 2. receipt-on-write-not-on-read
# --------------------------------------------------------------------------- #
def test_get_status_answers_and_mints_nothing():
    with TestClient(serve.app) as c:
        r = c.get(STATUS)
    assert r.status_code == 200, f"{STATUS} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert j["verdict"] in VERDICTS
    assert "receipt" not in j, "GET status is a PURE READ — must mint NO receipt"


def test_post_aggregate_mints_unsigned_sha256_receipt():
    with TestClient(serve.app) as c:
        r = c.post(AGG)
    assert r.status_code == 200, f"{AGG} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert j["verdict"] in VERDICTS
    rec = j["receipt"]
    assert rec["algorithm"] == "sha256"
    assert rec["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(rec["content_sha256"], str) and len(rec["content_sha256"]) == 64
    # digest is deterministic over the integrity content (excludes the volatile clock).
    assert rec["content_sha256"] == hw._content_receipt(j)["content_sha256"]


def test_get_info_is_static_pure_read():
    with TestClient(serve.app) as c:
        r = c.get(INFO)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and "receipt" not in j
    assert set(j["verdicts"]) == VERDICTS


# --------------------------------------------------------------------------- #
# 3. NEVER INTACT if anything is violated (controlled surface input)
# --------------------------------------------------------------------------- #
def test_verdict_violated_never_intact_when_manifest_violates(monkeypatch):
    """A surface manifest that inflates the locked-proof count violates an invariant;
    the wall MUST report VIOLATED — never INTACT, never DEGRADED."""
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "fake", "title": "fake", "cat": "governance"}])
    bad = {"label": "MODELED", "doctrine": {"locked_proven": 9, "lambda": "Conjecture 1",
                                            "trust_ceiling": 0.97, "trust_100_percent": False}}
    monkeypatch.setattr(hw, "_probe_surface",
                        lambda app, sid, gp, ns, timeout=3.0: (bad, "fake/x", hw.NATIVE_OK))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["verdict"] == hw.VERDICT_VIOLATED
    assert agg["summary"]["reachable_violations"] >= 1
    assert agg["verdict"] != hw.INTACT
    invs = {v["invariant"] for v in agg["violations"]}
    assert "locked_count_eight" in invs


def test_declared_false_invariant_is_a_violation(monkeypatch):
    """A surface that declares one of its OWN honesty_invariants False is VIOLATED verbatim."""
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "fake", "title": "fake", "cat": "governance"}])
    bad = {"label": "MODELED", "honesty_invariants": {"writer_ne_judge": False}}
    monkeypatch.setattr(hw, "_probe_surface",
                        lambda app, sid, gp, ns, timeout=3.0: (bad, "fake/x", hw.NATIVE_OK))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["verdict"] == hw.VERDICT_VIOLATED


# --------------------------------------------------------------------------- #
# 4. unreachable manifest -> UNKNOWN -> DEGRADED (never fabricated pass)
# --------------------------------------------------------------------------- #
def test_unreachable_manifest_is_unknown_and_degrades(monkeypatch):
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "fake", "title": "fake", "cat": "governance"}])
    monkeypatch.setattr(hw, "_probe_surface",
                        lambda app, sid, gp, ns, timeout=3.0: (None, "fake/x", hw.UNKNOWN))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["summary"]["unknown_surfaces"] == 1
    assert agg["summary"]["reachable_violations"] == 0
    assert agg["verdict"] == hw.VERDICT_DEGRADED, "UNKNOWN must degrade, never pass as INTACT"


# --------------------------------------------------------------------------- #
# 5. never upgrades a label (verbatim)
# --------------------------------------------------------------------------- #
def test_label_read_verbatim_never_upgraded():
    """A surface declaring ROADMAP must NOT be upgraded to MEASURED/PROVEN/etc."""
    label_tok, _prov, _checks = hw._eval_payload({"label": "ROADMAP"})
    assert label_tok == "ROADMAP", f"label upgraded to {label_tok} (must stay verbatim)"
    # a genuinely low label stays low.
    tok2, _, _ = hw._eval_payload({"data_label": "STRUCTURAL-ONLY"})
    assert tok2 == "STRUCTURAL-ONLY"


def test_bogus_marketing_label_is_a_violation():
    """A label that maps to NO honest-vocabulary token is a violation (never invented)."""
    label_tok, _prov, checks = hw._eval_payload({"label": "BOGUS-UNRECOGNIZED-LABEL"})
    assert label_tok is None
    vocab_check = [c for c in checks if c["invariant"] == "label_in_honest_vocabulary"]
    assert vocab_check and vocab_check[0]["status"] == hw.VIOLATED


# --------------------------------------------------------------------------- #
# 6. doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    with TestClient(serve.app) as c:
        j = c.post(AGG).json()
    d = j["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_status_in_real_estate_is_consistent():
    """Against the REAL booted estate: verdict is consistent with observed evidence and
    every per-surface label is in the honest vocabulary (never upgraded)."""
    with TestClient(serve.app) as c:
        j = c.post(AGG).json()
    sm = j["summary"]
    if sm["reachable_violations"] >= 1:
        assert j["verdict"] == hw.VERDICT_VIOLATED
    elif sm["unknown_surfaces"] > 0:
        assert j["verdict"] == hw.VERDICT_DEGRADED
    else:
        assert j["verdict"] == hw.INTACT
    vocab = set(hw.HONEST_LABELS)
    for e in j["surfaces"]:
        if e.get("label") is not None:
            assert e["label"] in vocab, f"{e['id']}: non-vocab label {e['label']}"


# --------------------------------------------------------------------------- #
# 7. DECLARED is an honest label (asserted, not measured, never upgraded)
# --------------------------------------------------------------------------- #
def test_declared_label_is_in_honest_vocabulary():
    """Regression: DECLARED honestly means 'asserted/stated, not measured and not proven'
    (same contract as EvidenceLabel.DECLARED in szl_quantum_utility). Its absence from the
    vocabulary made every honestly-DECLARED surface the single reachable violation that
    dragged the whole estate verdict to VIOLATED."""
    assert "DECLARED" in hw.HONEST_LABELS
    for payload in ({"label": "DECLARED"}, {"data_label": "DECLARED"},
                    {"doctrine": {"label_top": "DECLARED"}}):
        label_tok, _prov, checks = hw._eval_payload(payload)
        assert label_tok == "DECLARED", f"{payload} resolved to {label_tok!r}"
        by = {c["invariant"]: c for c in checks}
        vocab = by.get("label_in_honest_vocabulary")
        assert vocab is not None, f"invariant not evaluated for {payload}"
        assert vocab["status"] == hw.SATISFIED, f"honest DECLARED wrongly flagged: {payload}"


def test_declared_is_never_upgraded_to_measured_or_proven():
    """DECLARED is a WEAK claim and must stay weak — never silently promoted."""
    for raw in ("DECLARED", "DECLARED — static registry, live metadata fetched separately"):
        label_tok, _prov, _checks = hw._eval_payload({"label": raw})
        assert label_tok == "DECLARED", f"{raw!r} upgraded to {label_tok!r}"


def test_shared_label_resolver_also_recognises_declared():
    """The wall delegates token resolution to szl_frontier_index._primary_label, so that
    shared vocabulary — not only the wall's own copy — gates the verdict. Both must agree."""
    assert "DECLARED" in fi.HONEST_LABELS
    assert fi._primary_label("DECLARED") == "DECLARED"
    assert set(hw.HONEST_LABELS) == set(fi.HONEST_LABELS)


def test_frontier_registry_declared_label_is_satisfied():
    """The real surface that triggered this: the primary-project registry labels its static,
    operator-asserted registry DECLARED and labels only live GitHub reads MEASURED. Reading
    its OWN manifest must now be SATISFIED, never a violation."""
    registry = pytest.importorskip("research.a11oy_primary_project_registry")
    assert registry.STATIC_LABEL == "DECLARED"
    assert registry.LIVE_LABEL == "MEASURED", "measurements must keep the MEASURED label"
    label_tok, _prov, checks = hw._eval_payload(registry.info())
    assert label_tok == "DECLARED"
    by = {c["invariant"]: c for c in checks}
    assert by["label_in_honest_vocabulary"]["status"] == hw.SATISFIED


def test_widened_vocabulary_did_not_become_a_rubber_stamp():
    """Recognising DECLARED must not turn the check into a pass-everything. Λ is Conjecture 1,
    never a theorem: the strings below are NEGATIVE examples the estate never declares, kept
    only to prove a label outside the honest set is still VIOLATED."""
    for raw in ("UNRECOGNIZED-MARKETING-LABEL", "TOTALLY-VERIFIED-BY-ASSERTION"):
        label_tok, _prov, checks = hw._eval_payload({"label": raw})
        by = {c["invariant"]: c for c in checks}
        assert label_tok is None, f"{raw!r} must map to NO honest token, got {label_tok!r}"
        assert by["label_in_honest_vocabulary"]["status"] == hw.VIOLATED


# --------------------------------------------------------------------------- #
# 8. UNKNOWN is a contract honest label (reachable-but-unverified never upgrades)
# --------------------------------------------------------------------------- #
# The shape GET /api/a11oy/v1/llm/sovereign/health returns when a sovereign node answers its
# model-list probe but provenance is unverified (pinned by tests/test_sovereign_backend.py).
_SOVEREIGN_REACHABLE_UNVERIFIED = {
    "reachable": True,
    "endpoint_reachable": True,
    "model": None,
    "url": None,
    "label": "UNKNOWN",
    "label_basis": "Metadata reachability only; sovereign provenance not verified.",
    "gpu_verified": False,
    "weights_verified": False,
    "ownership_proof": "UNAVAILABLE",
    "model_ready": True,
    "receipt_binding": "UNKNOWN",
    "operational": False,
    "state": "UNKNOWN",
    "sovereign_status": "UNKNOWN",
    "wired": False,
    "live": False,
    "honest_stub": True,
    "conjecture_note": "Λ = Conjecture 1 — advisory, never 'green'/theorem.",
}


def test_unknown_label_is_in_contract_honest_vocabulary():
    """Regression (live 2026-11-17): the sovereign health surface honestly labels a
    reachable-but-unverified node UNKNOWN. UNKNOWN is listed in the public-estate contract
    truthVocabulary (static/shared/public-estate-contract.v1.json), so the wall must read it
    as SATISFIED, never as the single violation that drags the estate to VIOLATED."""
    import json
    import pathlib

    contract = json.loads((pathlib.Path(__file__).resolve().parents[1]
                           / "static/shared/public-estate-contract.v1.json").read_text())
    assert "UNKNOWN" in contract["truthVocabulary"], "UNKNOWN must stay in the contract truthVocabulary"
    assert "UNKNOWN" in hw.HONEST_LABELS
    assert "UNKNOWN" in fi.HONEST_LABELS
    assert fi._primary_label("UNKNOWN") == "UNKNOWN"
    for payload in ({"label": "UNKNOWN"}, {"data_label": "UNKNOWN"},
                    {"doctrine": {"label_top": "UNKNOWN"}}):
        label_tok, _prov, checks = hw._eval_payload(payload)
        assert label_tok == "UNKNOWN", f"{payload} resolved to {label_tok!r}"
        by = {c["invariant"]: c for c in checks}
        assert by["label_in_honest_vocabulary"]["status"] == hw.SATISFIED, payload


def test_bogus_label_still_violates_after_unknown_is_accepted():
    """Recognising UNKNOWN must not make the vocabulary check a rubber stamp."""
    label_tok, _prov, checks = hw._eval_payload({"label": "TOTALLY-VERIFIED"})
    by = {c["invariant"]: c for c in checks}
    assert label_tok is None, f"'TOTALLY-VERIFIED' must map to no honest token, got {label_tok!r}"
    assert by["label_in_honest_vocabulary"]["status"] == hw.VIOLATED


def test_word_unknown_inside_free_text_is_not_the_unknown_label():
    """UNKNOWN counts only as the whole label value. Free text that merely contains the word
    must keep failing the vocabulary check, as it did before UNKNOWN was accepted."""
    for raw in ("theorem proved; unknown", "PRODUCTION-GRADE, risk unknown",
                "VERIFIED (risk unknown)", "unknown risk, ship it"):
        assert fi._primary_label(raw) is None, raw
        label_tok, _prov, checks = hw._eval_payload({"label": raw})
        by = {c["invariant"]: c for c in checks}
        assert label_tok is None, f"{raw!r} resolved to {label_tok!r}"
        assert by["label_in_honest_vocabulary"]["status"] == hw.VIOLATED, raw
    for raw in ("UNKNOWN", " unknown ", "Unknown"):
        assert fi._primary_label(raw) == "UNKNOWN", raw


def test_wall_fallback_resolver_also_treats_unknown_as_whole_value_only(monkeypatch):
    """If szl_frontier_index cannot be imported, the wall's local fallback must apply the
    same whole-value rule, so the fallback is never looser than the shared resolver."""
    def _boom():
        raise ImportError("simulated")
    monkeypatch.setattr(hw, "_fi", _boom)
    assert hw._extract_label({"label": "UNKNOWN"}) == ("UNKNOWN", "UNKNOWN")
    assert hw._extract_label({"label": "risk unknown"}) == ("risk unknown", None)
    assert hw._extract_label({"label": "MODELED, scale unknown"}) == (
        "MODELED, scale unknown", "MODELED")


def test_sovereign_reachable_unverified_shape_is_satisfied_and_never_upgraded():
    label_tok, _prov, checks = hw._eval_payload(dict(_SOVEREIGN_REACHABLE_UNVERIFIED))
    assert label_tok == "UNKNOWN", f"UNKNOWN upgraded/dropped to {label_tok!r}"
    violated = [c for c in checks if c["status"] != hw.SATISFIED]
    assert violated == [], f"honest reachable-unverified shape wrongly flagged: {violated}"


def test_sovereign_reachable_unverified_aggregate_is_intact(monkeypatch):
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "sovereign", "title": "sovereign", "cat": "energy"}])
    monkeypatch.setattr(
        hw, "_probe_surface",
        lambda app, sid, gp, ns, timeout=3.0: (dict(_SOVEREIGN_REACHABLE_UNVERIFIED),
                                               "/api/a11oy/v1/llm/sovereign/health",
                                               hw.NATIVE_OK))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["violations"] == []
    assert agg["summary"]["reachable_violations"] == 0
    assert agg["verdict"] == hw.INTACT, agg["verdict_reason"]
    assert agg["summary"]["label_counts"] == {"UNKNOWN": 1}
    assert agg["surfaces"][0]["label"] == "UNKNOWN"


def test_real_sovereign_route_reachable_unverified_is_not_a_wall_violation(monkeypatch):
    """Drive the REAL sovereign health route through the wall's REAL in-process probe, with
    the node simulated reachable via the same seams tests/test_sovereign_backend.py uses
    (no network). The route keeps its honest UNKNOWN label; the wall must not flag it."""
    import szl_llm_registry as reg

    model_tag = "llama3-szl-finetuned-q4"
    private_url = "http://secret-tunnel.example.invalid:11434/v1"
    matrix = {
        "node_count": 1, "reachable_count": 1, "any_reachable": True,
        "primary_base_url": private_url,
        "selected": {"index": 0, "role": "primary"},
        "nodes": [{"index": 0, "role": "primary", "reachable": True,
                   "api_style": "openai /v1", "served_models": [model_tag],
                   "base_url": private_url, "error": "HTTP_STATUS:502"}],
        "note": private_url,
    }
    monkeypatch.setattr(reg, "sovereign_mesh_matrix", lambda timeout=None: matrix)
    monkeypatch.setattr(reg, "_sovereign_env_present", lambda: True)
    monkeypatch.setattr(reg, "_sovereign_env_used", lambda: "A11OY_BRAIN_URL")
    monkeypatch.setattr(reg, "_sovereign_model_slug", lambda: model_tag)
    real = [s for s in hw._surface_registry() if s.get("id") == "sovereign"]
    assert real, "sovereign must stay in the app's own surface registry"
    monkeypatch.setattr(hw, "_surface_registry", lambda: real)

    agg = hw._build_aggregate(serve.app, "a11oy")
    (entry,) = agg["surfaces"]
    assert entry["status"] == hw.NATIVE_OK
    assert entry["endpoint"] == "/api/a11oy/v1/llm/sovereign/health"
    assert entry["label"] == "UNKNOWN", "reachable-unverified must stay UNKNOWN, never upgraded"
    assert entry["violations"] == []
    assert agg["violations"] == []
    assert agg["verdict"] == hw.INTACT, agg["verdict_reason"]


def test_real_sovereign_catalog_entry_reports_the_node_health_label(monkeypatch):
    """Pins the second disclosed catalog change. With the node unreachable (the CI default)
    the frontier-index sovereign entry is UNAVAILABLE. With the node reachable but unverified
    (the live case) it now reports the node's own health label, UNKNOWN from
    /llm/sovereign/health, where it used to skip that endpoint and fall through to ROADMAP
    from /energy/sovereign. Neither case claims LIVE or MEASURED."""
    import szl_llm_registry as reg

    (surface,) = [s for s in fi._surface_registry() if s.get("id") == "sovereign"]
    get_paths = fi._registered_get_paths(serve.app, "a11oy")

    default = fi._classify_surface(serve.app, surface, get_paths, "a11oy")
    assert default["label"] == "UNAVAILABLE", default

    model_tag = "llama3-szl-finetuned-q4"
    private_url = "http://secret-tunnel.example.invalid:11434/v1"
    matrix = {
        "node_count": 1, "reachable_count": 1, "any_reachable": True,
        "primary_base_url": private_url,
        "selected": {"index": 0, "role": "primary"},
        "nodes": [{"index": 0, "role": "primary", "reachable": True,
                   "api_style": "openai /v1", "served_models": [model_tag],
                   "base_url": private_url, "error": "HTTP_STATUS:502"}],
        "note": private_url,
    }
    monkeypatch.setattr(reg, "sovereign_mesh_matrix", lambda timeout=None: matrix)
    monkeypatch.setattr(reg, "_sovereign_env_present", lambda: True)
    monkeypatch.setattr(reg, "_sovereign_env_used", lambda: "A11OY_BRAIN_URL")
    monkeypatch.setattr(reg, "_sovereign_model_slug", lambda: model_tag)

    live = fi._classify_surface(serve.app, surface, get_paths, "a11oy")
    assert live["label"] == "UNKNOWN", live
    assert live["endpoint"] == "/api/a11oy/v1/llm/sovereign/health", live
    assert live["label"] not in {"LIVE", "MEASURED", "PROVEN"}


def test_real_router_status_resolves_to_unknown_in_catalog_and_checker():
    """Pins the disclosed catalog side effect against the REAL route: unprobed
    /llm/router/status exposes only the sovereign sub-node label UNKNOWN, so the frontier
    index and the independent CI checker both resolve it to UNKNOWN (a downgrade from the
    MODELED it fell through to before; never an upgrade)."""
    import importlib.util
    import pathlib

    with TestClient(serve.app) as c:
        r = c.get("/api/a11oy/v1/llm/router/status")
    assert r.status_code == 200
    payload = r.json()
    (node,) = payload["local_nodes"]
    assert node["state"] == "UNPROBED" and node["label"] == "UNKNOWN"
    assert fi._extract_label(payload) == "UNKNOWN"

    checker_path = (pathlib.Path(__file__).resolve().parents[1]
                    / ".github/scripts/frontier_index_honesty_check.py")
    spec = importlib.util.spec_from_file_location("fi_honesty_checker_pin", checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    assert checker.independent_label(payload) == "UNKNOWN"


def test_lambda_negated_theorem_is_not_a_violation():
    """Regression: a lambda declared as a Conjecture that explicitly says it is
    'NOT a theorem' / 'never a theorem' must PASS. The prior naive substring test
    (`"theorem" not in low`) false-flagged the honest negated phrasing, which was
    the single reachable violation dragging the live estate verdict to VIOLATED."""
    honest_variants = [
        "Conjecture 1 (advisory, NOT a theorem; never green/proven)",
        "Conjecture 1 — advisory only, never a theorem, never green",
        "Conjecture 1 (advisory, gray; isn't a theorem)",
    ]
    for lam in honest_variants:
        _, _, checks = hw._eval_payload({"doctrine": {"lambda": lam}})
        by = {c["invariant"]: c for c in checks}
        c = by.get("lambda_is_conjecture_not_theorem")
        assert c is not None, f"invariant not evaluated for: {lam!r}"
        assert c["status"] == "SATISFIED", f"honest negated-theorem lambda wrongly flagged: {lam!r}"


def test_lambda_affirmative_theorem_claim_is_a_violation():
    """A lambda that AFFIRMATIVELY claims to be proven must be flagged. The strings
    below are NEGATIVE examples the estate never claims: Λ stays Conjecture 1,
    never a theorem, never green. They exist only so the checker proves it still
    catches a real affirmative claim."""
    for lam in ["Lambda is a theorem, proven green",
                "now a theorem with trust 1.0"]:
        _, _, checks = hw._eval_payload({"doctrine": {"lambda": lam}})
        by = {c["invariant"]: c for c in checks}
        c = by.get("lambda_is_conjecture_not_theorem")
        assert c is not None
        assert c["status"] == "VIOLATED", f"affirmative theorem claim not flagged: {lam!r}"
