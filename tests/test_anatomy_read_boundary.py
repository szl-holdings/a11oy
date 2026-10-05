#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic fixtures verify read/write separation, not deployed model quality."""

import copy
import json
import re
import shlex
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import a11oy_ecosystem_atlas as atlas
import szl_anatomy_brainloop as brain
import szl_operator_auth as auth


@pytest.fixture
def overlay(tmp_path, monkeypatch):
    path = tmp_path / "overlay.jsonl"
    monkeypatch.setenv("SZL_BRAIN_OVERLAY", str(path))
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, "fixture-not-a-real-secret")
    monkeypatch.setattr(
        brain, "_STATE_CACHE", {"mtime": None, "state": None, "path": None}
    )
    return path


@pytest.fixture
def client():
    app = FastAPI()
    brain.register(app)
    atlas.register(app)
    return TestClient(app)


def _broken_overlay(path):
    events = [
        {"ev": "receipt", "receipt_hash": "bad", "prev_hash": ""},
        {
            "ev": "node",
            "id": "overlay:fixture",
            "text": "private fixture note",
            "receipt_hash": "bad",
            "tier": brain.TIER_CORROBORATED,
            "digest": "private fixture digest",
        },
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_repeated_audit_get_previews_without_applying_demotions(overlay, client):
    _broken_overlay(overlay)
    before = overlay.read_bytes(), overlay.stat().st_mtime_ns
    for _ in range(3):
        response = client.get("/api/a11oy/v1/anatomy/self-audit")
        assert response.status_code == 200
        out = response.json()
        assert out["chain_ok"] is False
        assert out["demotions"] == [
            {
                "id": "overlay:fixture",
                "from": "CORROBORATED",
                "to": "CONJECTURE",
                "quarantined": False,
            }
        ]
        assert out["demotions_applied"] is False
        assert out["storage_writes"] == 0
        assert out["receipt_minted_on_get"] is False
        assert out["label"] == "MODELED"
        assert out["authorization"] == "NONE"
    assert (overlay.read_bytes(), overlay.stat().st_mtime_ns) == before
    assert brain._get_state()["nodes"]["overlay:fixture"]["tier"] == "CORROBORATED"


def test_absent_explicit_overlay_read_creates_neither_parent_nor_file(
    overlay, monkeypatch, client
):
    path = overlay.parent / "absent-parent" / "overlay.jsonl"
    monkeypatch.setenv("SZL_BRAIN_OVERLAY", str(path))
    for leaf in ("self-audit", "salience", "evidence"):
        response = client.get("/api/a11oy/v1/anatomy/" + leaf)
        assert response.status_code == 200
        assert not path.exists() and not path.parent.exists()


def test_default_path_resolution_never_opens_or_creates_storage(monkeypatch):
    monkeypatch.delenv("SZL_BRAIN_OVERLAY", raising=False)
    with (
        patch(
            "builtins.open", side_effect=AssertionError("read must not open for append")
        ),
        patch.object(
            brain.os, "makedirs", side_effect=AssertionError("read must not mkdir")
        ),
    ):
        assert brain._overlay_path().endswith(".szl_brain_overlay.jsonl")


def test_existing_fallback_overlay_is_preserved(monkeypatch, tmp_path):
    monkeypatch.delenv("SZL_BRAIN_OVERLAY", raising=False)
    monkeypatch.setattr(brain, "__file__", str(tmp_path / "repo" / "module.py"))
    monkeypatch.setattr(brain.tempfile, "gettempdir", lambda: str(tmp_path))
    existing = tmp_path / ".szl_brain_overlay.jsonl"
    existing.write_text("", encoding="utf-8")
    assert brain._overlay_path() == str(existing)
    assert not (tmp_path / "repo").exists()


def test_indirect_loop_health_has_no_append(overlay):
    _broken_overlay(overlay)
    before = overlay.read_bytes(), overlay.stat().st_mtime_ns
    with (
        patch.object(brain, "_load_graph", return_value={"available": False}),
        patch.object(brain, "_append_events", side_effect=AssertionError("GET write")),
    ):
        assert brain.loop_health()["self_audit_demotions"] == 1
    assert (overlay.read_bytes(), overlay.stat().st_mtime_ns) == before


def test_later_matching_link_cannot_restore_a_broken_prefix():
    first = brain._make_receipt("q", [], "answer", {}, 0, None, "")
    second = brain._make_receipt(
        "q2", [], "answer2", {}, 0, None, first["receipt_hash"]
    )
    first["answer_digest"] = "tampered"
    state = {
        "receipts": [first, second],
        "nodes": {
            "node": {"receipt_hash": second["receipt_hash"], "tier": "LOAD-BEARING"}
        },
    }
    before = copy.deepcopy(state)
    result = brain._audit_state(state)
    assert result["chain_ok"] is False
    assert len(result["broken"]) == 2
    assert result["demotions"][0]["to"] == "CORROBORATED"
    assert state == before


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer wrong", "Basic abc"])
def test_denied_pulse_has_no_inference_or_write(overlay, client, header):
    headers = {"Authorization": header} if header is not None else {}
    with (
        patch.object(brain, "pulse", side_effect=AssertionError("anonymous pulse")),
        patch.object(
            brain, "_append_events", side_effect=AssertionError("anonymous write")
        ),
    ):
        response = client.post(
            "/api/a11oy/v1/anatomy/pulse",
            headers=headers,
            json={"q": "query", "operator": True},
        )
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    assert not overlay.exists()


def test_unconfigured_and_failed_principal_refuse(overlay, monkeypatch, client):
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, "")
    with patch.object(brain, "pulse", side_effect=AssertionError("unconfigured pulse")):
        assert (
            client.post("/api/a11oy/v1/anatomy/pulse", json={"q": "query"}).status_code
            == 401
        )
    with (
        patch.object(auth, "principal", side_effect=RuntimeError("resolver failure")),
        patch.object(
            brain, "pulse", side_effect=AssertionError("resolver failure pulse")
        ),
    ):
        assert (
            client.post("/api/a11oy/v1/anatomy/pulse", json={"q": "query"}).status_code
            == 401
        )
    assert not overlay.exists()


def test_authorized_pulse_preserves_existing_callable(overlay, client):
    with patch.object(brain, "pulse", return_value={"ok": True}) as called:
        response = client.post(
            "/api/a11oy/v1/anatomy/pulse",
            headers={"Authorization": "Bearer fixture-not-a-real-secret"},
            json={"q": "query"},
        )
    assert response.status_code == 200
    called.assert_called_once_with("query", ns="a11oy")


def test_evidence_get_is_summary_only_and_head_read_only(overlay, client):
    _broken_overlay(overlay)
    before = overlay.read_bytes(), overlay.stat().st_mtime_ns
    with (
        patch.object(
            brain, "_load_graph", side_effect=AssertionError("no graph harvest")
        ),
        patch.object(
            brain, "_sovereign_answer", side_effect=AssertionError("no model")
        ),
    ):
        response = client.get("/api/a11oy/v1/anatomy/evidence")
        assert client.head("/api/a11oy/v1/anatomy/evidence").status_code == 200
    out = response.json()
    assert out["schema"] == "szl.anatomy.evidence/v6"
    assert out["content_access"] == "SUMMARY_ONLY"
    assert out["storage_writes"] == 0 and out["model_invoked"] is False
    assert out["gradient_training"] is False and out["receipt_minted_on_get"] is False
    assert set(out["authority"].values()) == {"NONE"}
    assert out["audit"]["proposed_demotions"] == 1
    assert "private fixture" not in response.text
    assert "overlay:fixture" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert (overlay.read_bytes(), overlay.stat().st_mtime_ns) == before
    assert client.post("/api/a11oy/v1/anatomy/evidence").status_code == 405


def test_evidence_replay_failure_is_unavailable_not_zero_substitution(overlay, client):
    with patch.object(
        brain, "_get_state", side_effect=OSError("private path must not leak")
    ):
        response = client.get("/api/a11oy/v1/anatomy/evidence")
    assert response.status_code == 503
    assert response.json()["evidence_class"] == "UNAVAILABLE"
    assert "private path" not in response.text
    assert "overlay" not in response.json()


@pytest.mark.parametrize(
    "record",
    [
        "{invalid",
        "null",
        "42",
        "[]",
        '{"ev":"unknown"}',
        '{"ev":"node"}',
        '{"ev":"reinforce","edges":[[]]}',
        '{"ev":"corroborate"}',
        '{"ev":"promote","id":"missing"}',
        '{"ev":"reinforce"}',
        '{"ev":"receipt"}',
    ],
)
def test_malformed_overlay_cannot_become_empty_healthy_summary(overlay, client, record):
    overlay.write_text(record + "\n", encoding="utf-8")
    before = overlay.read_bytes(), overlay.stat().st_mtime_ns
    for leaf in ("evidence", "self-audit"):
        response = client.get("/api/a11oy/v1/anatomy/" + leaf)
        assert response.status_code == 503
        assert (
            response.json().get("evidence_class", response.json().get("label"))
            == "UNAVAILABLE"
        )
        assert response.json()["storage_writes"] == 0
        assert "audit" not in response.json()
    assert (overlay.read_bytes(), overlay.stat().st_mtime_ns) == before


def test_v6_registrar_and_existing_v5_are_owned_and_copied(client):
    response = client.get("/anatomy-v6")
    assert response.status_code == 200
    assert "Anatomy v6" in response.text
    assert client.get("/anatomy-v5").status_code == 200
    root = Path(__file__).resolve().parents[1]
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY pages/ ./pages/" in docker
    sources = {
        source
        for match in re.finditer(r"(?m)^COPY\s+(.+)$", docker)
        for source in shlex.split(match.group(1))[:-1]
    }
    assert "szl_anatomy_brainloop.py" in sources
    assert "a11oy_ecosystem_atlas.py" in sources
