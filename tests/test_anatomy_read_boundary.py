#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic fixtures verify read/write separation, not deployed model quality."""

import copy
import errno
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


@pytest.mark.parametrize("existing_fallback", [False, True])
@pytest.mark.parametrize("graph_available", [False, True])
def test_authorized_pulse_uses_appendable_fallback_chain(
    overlay, monkeypatch, client, existing_fallback, graph_available
):
    monkeypatch.delenv("SZL_BRAIN_OVERLAY", raising=False)
    local = overlay.parent / "repo" / ".szl_brain_overlay.jsonl"
    local.parent.mkdir()
    fallback = overlay.parent / ".szl_brain_overlay.jsonl"
    monkeypatch.setattr(brain, "__file__", str(local.parent / "module.py"))
    monkeypatch.setattr(brain.tempfile, "gettempdir", lambda: str(overlay.parent))
    local_receipt = brain._make_receipt("local", [], "local answer", {}, 0, None, "")
    local.write_text(json.dumps(local_receipt) + "\n", encoding="utf-8")
    local_before = local.read_bytes(), local.stat().st_mtime_ns
    expected_prev = ""
    if existing_fallback:
        receipt = brain._make_receipt("fallback", [], "fallback answer", {}, 0, None, "")
        node = {"ev": "node", "id": "overlay:fallback", "tier": "CONJECTURE",
                "receipt_hash": receipt["receipt_hash"], "corroboration": 2}
        fallback.write_text(json.dumps(receipt) + "\n" + json.dumps(node) + "\n",
                            encoding="utf-8")
        expected_prev = receipt["receipt_hash"]

    graph = {"available": graph_available,
             "nodes": [{"id": "source:one", "title": "query"},
                       {"id": "source:two", "title": "query second"}],
             "links": [{"source": "source:one", "target": "source:two"}]}

    real_open = open

    def read_only_local(path, mode="r", *args, **kwargs):
        if str(path) == str(local) and "a" in mode:
            raise OSError(errno.EROFS, "fixture read-only deployment volume")
        return real_open(path, mode, *args, **kwargs)

    with (
        patch("builtins.open", side_effect=read_only_local),
        patch.object(brain, "_load_graph", return_value=graph),
        patch.object(brain, "_energy_snapshot", return_value={"label": "UNAVAILABLE"}),
        patch.object(brain, "_sovereign_answer", return_value={"available": False,
                     "text": None, "tokens": 0, "label": "UNAVAILABLE"}),
    ):
        for _ in range(2):
            response = client.post(
                "/api/a11oy/v1/anatomy/pulse",
                headers={"Authorization": "Bearer fixture-not-a-real-secret"},
                json={"q": "query"},
            )
            assert response.status_code == 200
            out = response.json()
            assert out["ok"] is True
            assert out["receipt"]["prev_hash"] == expected_prev
            expected_prev = out["receipt"]["receipt_hash"]

        fallback_before = fallback.read_bytes(), fallback.stat().st_mtime_ns
        with patch.object(brain, "_write_overlay_path", side_effect=AssertionError("GET writer")):
            for leaf in ("evidence", "self-audit"):
                summary = client.get("/api/a11oy/v1/anatomy/" + leaf)
                assert summary.status_code == 200
                audit = summary.json().get("audit", summary.json())
                assert audit["chain_ok"] is True
                assert audit["receipts_checked"] == 2 + int(existing_fallback)
        assert (fallback.read_bytes(), fallback.stat().st_mtime_ns) == fallback_before

    assert brain._overlay_path() == str(fallback)
    assert (local.read_bytes(), local.stat().st_mtime_ns) == local_before
    if existing_fallback and graph_available:
        # Post-pulse tier maintenance must fold and append against the fallback too.
        assert brain._get_state(strict=True)["nodes"]["overlay:fallback"]["tier"] == "CORROBORATED"


def test_unwritable_explicit_overlay_does_not_redirect_to_fallback(
    overlay, monkeypatch, client
):
    overlay.write_text("", encoding="utf-8")
    fallback_dir = overlay.parent / "unused-fallback"
    monkeypatch.setattr(brain.tempfile, "gettempdir", lambda: str(fallback_dir))
    real_open = open

    def read_only_override(path, mode="r", *args, **kwargs):
        if str(path) == str(overlay) and "a" in mode:
            raise OSError(errno.EROFS, "fixture read-only deployment volume")
        return real_open(path, mode, *args, **kwargs)

    with (
        patch("builtins.open", side_effect=read_only_override),
        patch.object(brain, "_load_graph", return_value={"available": False}),
        patch.object(brain, "_energy_snapshot", return_value={"label": "UNAVAILABLE"}),
    ):
        response = client.post(
            "/api/a11oy/v1/anatomy/pulse",
            headers={"Authorization": "Bearer fixture-not-a-real-secret"},
            json={"q": "query"},
        )
    assert response.json()["ok"] is False
    assert overlay.read_bytes() == b""
    assert not fallback_dir.exists()


@pytest.mark.parametrize("invalid_target", ["directory", "parent-file"])
def test_invalid_overlay_target_is_unavailable_without_writes(
    overlay, monkeypatch, client, invalid_target
):
    # First populate the empty replay cache; invalid storage must not reuse it.
    assert client.get("/api/a11oy/v1/anatomy/evidence").status_code == 200
    if invalid_target == "directory":
        overlay.mkdir()
        target = overlay
    else:
        overlay.write_text("parent is a file", encoding="utf-8")
        target = overlay / "private-overlay.jsonl"
        monkeypatch.setenv("SZL_BRAIN_OVERLAY", str(target))
    before = overlay.stat().st_mtime_ns
    with (
        patch.object(brain, "_append_events", side_effect=AssertionError("GET append")),
        patch.object(brain.os, "makedirs", side_effect=AssertionError("GET mkdir")),
    ):
        for leaf in ("evidence", "self-audit"):
            response = client.get("/api/a11oy/v1/anatomy/" + leaf)
            assert response.status_code == 503
            out = response.json()
            assert out.get("evidence_class", out.get("label")) == "UNAVAILABLE"
            assert out["storage_writes"] == 0
            assert "audit" not in out and "overlay" not in out and "chain_ok" not in out
            assert str(target) not in response.text
        assert client.head("/api/a11oy/v1/anatomy/evidence").status_code == 503
    assert overlay.stat().st_mtime_ns == before


def test_inaccessible_overlay_parent_cannot_reuse_empty_cached_summary(
    overlay, client
):
    assert client.get("/api/a11oy/v1/anatomy/evidence").status_code == 200
    real_stat = brain.os.stat

    def inaccessible_parent(path, *args, **kwargs):
        if str(path) == str(overlay):
            raise PermissionError(errno.EACCES, "private parent cannot be traversed")
        return real_stat(path, *args, **kwargs)

    # Inject the OS error because privileged test runners can traverse chmod(0).
    with (
        patch.object(brain.os, "stat", side_effect=inaccessible_parent),
        patch.object(brain, "_append_events", side_effect=AssertionError("GET append")),
        patch.object(brain.os, "makedirs", side_effect=AssertionError("GET mkdir")),
    ):
        for leaf in ("evidence", "self-audit"):
            response = client.get("/api/a11oy/v1/anatomy/" + leaf)
            assert response.status_code == 503
            assert response.json()["storage_writes"] == 0
            assert "audit" not in response.json() and "chain_ok" not in response.json()
            assert "private parent" not in response.text
    assert not overlay.exists()


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
        patch.object(
            brain, "_write_overlay_path", side_effect=AssertionError("anonymous writer probe")
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
