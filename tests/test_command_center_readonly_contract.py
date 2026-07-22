from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Owner-authored CI refresh after the self-removing repair workflow completed.


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


def test_null_chapaq_result_remains_read_only_and_non_crashing(monkeypatch):
    ecosystem = importlib.import_module("szl_ecosystem_routes")

    def observed(url: str, timeout: float = 12.0):
        if url.endswith("/api/a11oy/v1/honest"):
            return {
                "doctrine_lock": {
                    "locked_formula_ids": ecosystem.LOCKED8,
                    "locked_formula_count": 8,
                }
            }
        if url.endswith("/api/a11oy/v1/lambda"):
            return {"lambda": 0.7, "axes": [{"score": 0.95}]}
        if url.endswith("/api/killinchu/v1/gov/chapaq-verdict"):
            return None
        return None

    monkeypatch.setattr(ecosystem, "_get_json", observed)
    board = ecosystem.build_kpi_board("a11oy")
    assert board["chapaq_verdict"] is None
    assert board["chapaq_source"].startswith("NOT_EVALUATED")


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
