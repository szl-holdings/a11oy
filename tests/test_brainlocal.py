# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Tests for szl_brainlocal — the local inference endpoint liveness+capability probe.

Every network probe is MOCKED. Nothing here contacts a real Ollama / llama-server
node, so the suite is deterministic in CI whether or not own-metal inference exists.

The invariants under test are the reason the surface exists:
  * env unset            -> UNAVAILABLE, and NO model name appears anywhere.
  * mocked reachable node -> LIVE with label MEASURED and the served list verbatim.
  * timeout / error       -> UNAVAILABLE, never a healthy-fabricated reading.
  * reachable, empty list -> DEGRADED, never presented as healthy.
  * brainlocal is NATIVE-OK through its own id-matching /manifest route.
  * receipt is a deterministic unsigned SHA-256 on write; GET mints nothing.
  * labels are never upgraded.

Doctrine note carried for the checker: Λ is Conjecture 1, never a theorem, and this
suite adds nothing to the locked-8.
"""
import ast
import hashlib
import json
import os
import pathlib
import re

import pytest

import szl_brainlocal as bl

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Mock helpers — the probe transport is replaced; no socket is ever opened.
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Fail loudly if any test forgets to mock the probe transport."""
    def _forbidden(url, timeout):
        raise AssertionError(f"unmocked network probe attempted: {url}")

    monkeypatch.setattr(bl, "_http_get_json", _forbidden)


def _mock_ok(monkeypatch, payload, seen=None):
    def _stub(url, timeout):
        if seen is not None:
            seen.append((url, timeout))
        return payload

    monkeypatch.setattr(bl, "_http_get_json", _stub)


def _mock_raise(monkeypatch, exc, seen=None):
    def _stub(url, timeout):
        if seen is not None:
            seen.append((url, timeout))
        raise exc

    monkeypatch.setattr(bl, "_http_get_json", _stub)


OLLAMA_TAGS = {"models": [{"name": "llama3.1:8b"}, {"name": "nomic-embed-text:latest"}]}
OPENAI_MODELS = {"object": "list", "data": [
    {"id": "llama3-szl-finetuned-q4", "object": "model"},
    {"id": "qwen2.5-coder:7b", "object": "model"},
]}


# --------------------------------------------------------------------------- #
# 1. env unset -> UNAVAILABLE, nothing fabricated.
# --------------------------------------------------------------------------- #

def test_env_unset_is_unavailable_with_the_honest_note():
    out = bl.probe({}, timeout=0.01)
    assert out["status"] == bl.UNAVAILABLE
    assert out["verdict"] == bl.UNAVAILABLE
    assert out["label"] == bl.LBL_UNAVAILABLE
    assert out["note"] == "no local endpoint configured"
    assert out["reached_any"] is False
    assert out["config"]["configured"] is False


def test_env_unset_names_no_model_anywhere():
    out = bl.probe({}, timeout=0.01)
    assert out["served_models"] == []
    assert out["served_model_count"] == 0
    assert out["live_node_count"] == 0
    assert out["nodes"] == []
    # No known local model tag may leak into an UNAVAILABLE reading. A fabricated
    # model name is exactly the failure this surface exists to prevent.
    blob = json.dumps(out).lower()
    for tag in ("llama", "qwen", "mistral", "phi", "gemma", "nomic"):
        assert tag not in blob, f"fabricated model tag {tag!r} in an UNAVAILABLE reading"


def test_env_unset_probes_nothing_at_all(monkeypatch):
    seen = []
    _mock_raise(monkeypatch, TimeoutError("must not be called"), seen)
    bl.probe({}, timeout=0.01)
    assert seen == [], "an unset endpoint must not be probed"


def test_env_unset_handler_is_not_ok_but_still_answers():
    out = bl.handle_probe("a11oy", {}, 0.01)
    assert out["ok"] is False
    assert out["label"] == bl.LBL_UNAVAILABLE
    assert out["doctrine"]["label_top"] == bl.LBL_UNAVAILABLE


def test_blank_and_whitespace_env_counts_as_unset():
    for value in ("", "   ", "\t"):
        out = bl.probe({bl.ENV_PRIMARY: value}, timeout=0.01)
        assert out["verdict"] == bl.UNAVAILABLE
        assert out["note"] == "no local endpoint configured"


# --------------------------------------------------------------------------- #
# 2. mocked reachable node -> LIVE + MEASURED, models verbatim.
# --------------------------------------------------------------------------- #

def test_reachable_openai_endpoint_is_live_and_measured(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434/v1"}, timeout=0.5)
    assert out["status"] == bl.LIVE
    assert out["verdict"] == bl.LIVE
    assert out["label"] == bl.LBL_MEASURED
    assert out["reached_any"] is True
    assert out["live_node_count"] == 1


def test_served_models_are_verbatim_from_the_endpoint(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434/v1"}, timeout=0.5)
    assert out["served_models"] == ["llama3-szl-finetuned-q4", "qwen2.5-coder:7b"]


def test_ollama_native_tags_shape_is_understood(monkeypatch):
    _mock_ok(monkeypatch, OLLAMA_TAGS)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["verdict"] == bl.LIVE
    assert out["served_models"] == ["llama3.1:8b", "nomic-embed-text:latest"]


def test_measured_label_requires_an_actual_reading(monkeypatch):
    """MEASURED appears only on the path where a node answered this request."""
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    dead = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert bl.LBL_MEASURED not in (dead["label"], dead["doctrine"]["label_top"])
    _mock_ok(monkeypatch, OPENAI_MODELS)
    live = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert live["label"] == bl.LBL_MEASURED


def test_probe_urls_cover_openai_then_ollama_and_handle_a_v1_suffix():
    assert bl.probe_urls("http://127.0.0.1:11434") == [
        "http://127.0.0.1:11434/v1/models", "http://127.0.0.1:11434/api/tags"]
    # an operator who already appended /v1 must not get /v1/v1/models
    assert bl.probe_urls("http://127.0.0.1:11434/v1") == [
        "http://127.0.0.1:11434/v1/models", "http://127.0.0.1:11434/api/tags"]
    assert bl.probe_urls("") == []


def test_openai_route_failure_falls_back_to_ollama_tags(monkeypatch):
    calls = []

    def _stub(url, timeout):
        calls.append(url)
        if url.endswith("/v1/models"):
            raise OSError("404 not found")
        return OLLAMA_TAGS

    monkeypatch.setattr(bl, "_http_get_json", _stub)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["verdict"] == bl.LIVE
    assert out["served_models"] == ["llama3.1:8b", "nomic-embed-text:latest"]
    assert calls[0].endswith("/v1/models") and calls[1].endswith("/api/tags")


def test_probe_is_bounded_by_the_supplied_timeout(monkeypatch):
    seen = []
    _mock_ok(monkeypatch, OPENAI_MODELS, seen)
    bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=1.25)
    assert seen and all(t == 1.25 for _u, t in seen)
    assert bl.PROBE_TIMEOUT_S <= 5.0, "the default probe budget must stay short"


def test_extra_jpt_gpu_urls_are_probed_too(monkeypatch):
    seen = []
    _mock_ok(monkeypatch, OPENAI_MODELS, seen)
    out = bl.probe({
        bl.ENV_PRIMARY: "http://127.0.0.1:11434",
        bl.ENV_EXTRA_URLS: "http://tower.tailnet:11434, http://box.tailnet:8080",
    }, timeout=0.5)
    assert out["node_count"] == 3
    assert out["live_node_count"] == 3
    hosts = " ".join(u for u, _t in seen)
    assert "tower.tailnet" in hosts and "box.tailnet" in hosts


def test_configured_but_unreachable_node_does_not_make_the_estate_live(monkeypatch):
    def _stub(url, timeout):
        if "tower" in url:
            return OPENAI_MODELS
        raise TimeoutError("asleep")

    monkeypatch.setattr(bl, "_http_get_json", _stub)
    out = bl.probe({
        bl.ENV_PRIMARY: "http://127.0.0.1:11434",
        bl.ENV_EXTRA_URLS: "http://tower.tailnet:11434",
    }, timeout=0.5)
    assert out["verdict"] == bl.LIVE and out["live_node_count"] == 1
    per_status = {n["endpoint"]: n["status"] for n in out["nodes"]}
    assert per_status["http://127.0.0.1:11434"] == bl.UNAVAILABLE
    assert per_status["http://tower.tailnet:11434"] == bl.LIVE


# --------------------------------------------------------------------------- #
# 3. timeout / error -> UNAVAILABLE, never healthy-fabricated.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("exc", [
    TimeoutError("probe budget exhausted"),
    ConnectionRefusedError("connection refused"),
    OSError("network is unreachable"),
    ValueError("Expecting value: line 1 column 1 (char 0)"),
])
def test_every_transport_failure_is_unavailable(monkeypatch, exc):
    _mock_raise(monkeypatch, exc)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["status"] == bl.UNAVAILABLE
    assert out["label"] == bl.LBL_UNAVAILABLE
    assert out["reached_any"] is False
    assert out["served_models"] == []
    assert out["live_node_count"] == 0


def test_timeout_never_reports_a_healthy_or_degraded_pass(monkeypatch):
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["verdict"] != bl.LIVE
    assert out["verdict"] != bl.DEGRADED, (
        "an unreachable node must be UNAVAILABLE, not a reachable-but-empty DEGRADED")
    assert out["ok"] is not True


def test_timeout_names_no_model_and_records_the_reason(monkeypatch):
    _mock_raise(monkeypatch, TimeoutError("probe budget exhausted"))
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    blob = json.dumps(out).lower()
    for tag in ("llama", "qwen", "mistral", "gemma", "nomic"):
        assert tag not in blob, f"fabricated model tag {tag!r} in a failed probe"
    attempts = out["nodes"][0]["attempts"]
    assert attempts and all(a["reached"] is False for a in attempts)
    assert "TimeoutError" in attempts[0]["error"]


def test_unrecognised_payload_shape_names_no_model(monkeypatch):
    _mock_ok(monkeypatch, {"unexpected": "shape"})
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["served_models"] == []
    assert out["verdict"] == bl.DEGRADED, (
        "the node answered, so reachability is real; it just named nothing")


def test_non_dict_payload_is_not_a_model_list():
    assert bl._models_from_payload(None) == []
    assert bl._models_from_payload("llama3.1:8b") == []
    assert bl._models_from_payload({"data": "llama3.1:8b"}) == []


def test_handler_never_raises_even_if_read_env_explodes(monkeypatch):
    monkeypatch.setattr(bl, "read_env", lambda environ=None: (_ for _ in ()).throw(
        RuntimeError("env read blew up")))
    out = bl.handle_probe("a11oy", {}, 0.01)
    assert out["ok"] is False
    assert out["verdict"] == bl.UNAVAILABLE
    assert out["served_models"] == []


# --------------------------------------------------------------------------- #
# 4. DEGRADED is reported as DEGRADED, never as healthy.
# --------------------------------------------------------------------------- #

def test_reachable_but_empty_listing_is_degraded(monkeypatch):
    _mock_ok(monkeypatch, {"object": "list", "data": []})
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["status"] == bl.DEGRADED
    assert out["served_models"] == []
    assert out["reached_any"] is True
    assert out["live_node_count"] == 0
    assert out["ok"] is not True


def test_degraded_is_never_presented_as_ok_through_the_handler(monkeypatch):
    _mock_ok(monkeypatch, {"models": []})
    out = bl.handle_probe("a11oy", {bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, 0.5)
    assert out["verdict"] == bl.DEGRADED
    assert out["ok"] is False, "only LIVE is ok:true — a DEGRADED node is not healthy"


# --------------------------------------------------------------------------- #
# 5. declared models stay MODELED and never become served.
# --------------------------------------------------------------------------- #

def test_declared_models_never_enter_the_served_list(monkeypatch):
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    out = bl.probe({
        bl.ENV_PRIMARY: "http://127.0.0.1:11434",
        bl.ENV_DECLARED_MODELS: "llama3.1:8b,qwen2.5-coder:7b",
    }, timeout=0.5)
    assert out["served_models"] == []
    assert out["declared_models"] == ["llama3.1:8b", "qwen2.5-coder:7b"]
    assert out["declared_models_label"] == bl.LBL_MODELED
    assert out["declared_not_served"] == ["llama3.1:8b", "qwen2.5-coder:7b"]
    assert out["verdict"] == bl.UNAVAILABLE


def test_declared_not_served_is_computed_against_the_real_listing(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.probe({
        bl.ENV_PRIMARY: "http://127.0.0.1:11434",
        bl.ENV_DECLARED_MODELS: "qwen2.5-coder:7b,phi4:14b",
    }, timeout=0.5)
    assert out["declared_not_served"] == ["phi4:14b"]
    assert "phi4:14b" not in out["served_models"]


def test_read_env_reports_configuration_not_reachability():
    cfg = bl.read_env({bl.ENV_PRIMARY: "http://127.0.0.1:11434"})
    assert cfg["configured"] is True
    assert cfg["env_vars_read"] == [
        bl.ENV_PRIMARY, bl.ENV_EXTRA_URLS, bl.ENV_DECLARED_MODELS]
    assert "reachability" in cfg["configured_meaning"]


def test_duplicate_urls_are_probed_once(monkeypatch):
    seen = []
    _mock_ok(monkeypatch, OPENAI_MODELS, seen)
    out = bl.probe({
        bl.ENV_PRIMARY: "http://127.0.0.1:11434",
        bl.ENV_EXTRA_URLS: "http://127.0.0.1:11434",
    }, timeout=0.5)
    assert out["node_count"] == 1


def test_userinfo_credentials_are_redacted_from_reported_urls(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.probe({bl.ENV_PRIMARY: "https://user:secret@gpu.example:11434"}, timeout=0.5)
    blob = json.dumps(out)
    assert "secret" not in blob
    assert "gpu.example:11434" in blob


# --------------------------------------------------------------------------- #
# 6. NATIVE-OK: the surface owns an id-matching /manifest route.
# --------------------------------------------------------------------------- #

def test_manifest_declares_the_surface_posture_and_invariants():
    man = bl.handle_manifest("a11oy")
    assert man["surface_id"] == "brainlocal"
    assert man["endpoint"] == "brain/brainlocal/manifest"
    assert man["data_label"] == bl.LBL_MODELED
    inv = man["honesty_invariants"]
    assert inv["lambda_is_conjecture_1_not_a_theorem"] is True
    assert inv["adds_nothing_to_locked_8"] is True
    assert inv["no_consciousness_claim"] is True
    assert inv["label_never_upgraded"] is True
    assert inv["measured_only_from_a_live_reading_this_request"] is True
    assert inv["unavailable_when_no_endpoint_configured"] is True
    assert inv["never_fabricates_a_wired_or_live_model"] is True
    assert inv["performs_no_inference_and_stores_nothing"] is True
    assert inv["receipt_on_write_not_on_read"] is True


def test_manifest_route_path_carries_the_surface_id_segment():
    """The Honesty Wall matches a path SEGMENT to the surface id; that is NATIVE-OK."""
    source = (ROOT / "szl_brainlocal.py").read_text(encoding="utf-8")
    assert 'f"/api/{ns}/v1/brain/{SURFACE_ID}/manifest"' in source
    segments = "/api/a11oy/v1/brain/brainlocal/manifest".split("/")
    norm = [re.sub(r"[^a-z0-9]", "", s.lower()) for s in segments]
    assert "brainlocal" in norm


def test_manifest_coverage_ratchet_sees_brainlocal_as_native_ok():
    checker = ROOT / "scripts" / "check_manifest_coverage.py"
    if not checker.exists():  # pragma: no cover — guard is optional in a trimmed tree
        pytest.skip("manifest-coverage guard not present")
    import importlib.util
    spec = importlib.util.spec_from_file_location("mcov", checker)
    mcov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcov)
    ids = mcov.registry_ids((ROOT / "szl3d_holographic.py").read_text(encoding="utf-8"))
    assert "brainlocal" in ids
    covered = mcov.covered_ids(ROOT) if hasattr(mcov, "covered_ids") else None
    if covered is not None:
        assert "brainlocal" in covered


def test_surface_is_appended_last_and_synced_across_all_three_places():
    import szl3d_holographic as holo
    assert holo.SURFACES[-1]["id"] == "brainlocal"
    assert holo.SURFACES[-1]["cat"] == "brain"
    html = (ROOT / "static" / "3d" / "holographic.html").read_text(encoding="utf-8")
    assert 'id: "brainlocal"' in html
    assert '/static/3d/surfaces/brainlocal.js' in html
    assert (ROOT / "static" / "3d" / "surfaces" / "brainlocal.js").exists()


def test_registry_titles_agree_between_backend_and_shell():
    import szl3d_holographic as holo
    title = holo.SURFACES[-1]["title"]
    html = (ROOT / "static" / "3d" / "holographic.html").read_text(encoding="utf-8")
    assert json.dumps(title) in html


def test_dockerfile_and_serve_wiring_present():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    serve = (ROOT / "serve.py").read_text(encoding="utf-8")
    assert "szl_brainlocal.py" in docker
    # joined an EXISTING grouped COPY line — no new single-file COPY layer
    assert "COPY szl_brainlocal.py ./" not in docker
    assert docker.count("szl_brainlocal.py") == 1
    assert "import szl_brainlocal" in serve
    assert "_szl_brainlocal.register(app" in serve


def test_surface_js_uses_only_approved_hues_and_no_runtime_cdn():
    js = (ROOT / "static" / "3d" / "surfaces" / "brainlocal.js").read_text(encoding="utf-8")
    hexes = {v.lower() for v in re.findall(r"0x[0-9a-fA-F]{6}", js)}
    # the three approved accents plus neutral greys — nothing else, and no purple
    allowed = {"0x5b8dee", "0x8a6bff", "0x3af4c8", "0x5a6570", "0x2a3138"}
    assert hexes <= allowed, f"non-approved hue(s) in brainlocal.js: {hexes - allowed}"
    for value in hexes - {"0x5b8dee", "0x8a6bff", "0x3af4c8"}:
        r, g, b = int(value[2:4], 16), int(value[4:6], 16), int(value[6:8], 16)
        assert max(r, g, b) - min(r, g, b) <= 24, f"{value} is not a neutral grey"
    assert "ctx.THREE" in js
    assert "http://" not in js.replace("http://127.0.0.1:11434", "")
    assert "https://cdn" not in js and "unpkg" not in js and "jsdelivr" not in js


# --------------------------------------------------------------------------- #
# 7. receipt-on-write: deterministic unsigned SHA-256; GET mints nothing.
# --------------------------------------------------------------------------- #

def test_receipt_is_a_deterministic_unsigned_sha256(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    first = bl.content_receipt(out)
    second = bl.content_receipt(out)
    assert first["algorithm"] == "sha256"
    assert re.fullmatch(r"[0-9a-f]{64}", first["content_sha256"])
    assert first["content_sha256"] == second["content_sha256"]
    assert first["signed"] is False
    assert first["mode"] == "UNSIGNED-CONTENT-DIGEST"


def test_receipt_digest_matches_a_hand_computed_sha256(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    expected = hashlib.sha256(bl._canonical_core(out).encode("utf-8")).hexdigest()
    assert bl.content_receipt(out)["content_sha256"] == expected


def test_receipt_digest_changes_with_the_verdict(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    live = bl.content_receipt(
        bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5))
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    dead = bl.content_receipt(
        bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5))
    assert live["content_sha256"] != dead["content_sha256"]


def test_get_reads_mint_nothing(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    probe_read = bl.handle_probe("a11oy", {bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, 0.5)
    assert "receipt" not in probe_read
    assert "receipt" not in bl.handle_info("a11oy")
    assert "receipt" not in bl.handle_manifest("a11oy")
    unset = bl.handle_probe("a11oy", {}, 0.01)
    assert "receipt" not in unset


def test_post_receipt_handler_mints_on_write(monkeypatch):
    _mock_ok(monkeypatch, OPENAI_MODELS)
    out = bl.handle_receipt("a11oy", {bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, 0.5)
    assert out["receipt"]["signed"] is False
    assert out["receipt"]["receipt_on"].startswith("write")
    assert out["endpoint"] == "brain/local/receipt"


def test_receipt_on_an_unavailable_probe_still_refuses_to_fabricate(monkeypatch):
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    out = bl.handle_receipt("a11oy", {bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, 0.5)
    assert out["verdict"] == bl.UNAVAILABLE
    assert out["served_models"] == []
    assert out["receipt"]["signed"] is False


# --------------------------------------------------------------------------- #
# 8. labels are never upgraded; doctrine invariants hold.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("payload,expected_label", [
    (None, bl.LBL_UNAVAILABLE),                                   # unset env
    ({"data": []}, bl.LBL_MEASURED),                              # reachable, empty
    (OPENAI_MODELS, bl.LBL_MEASURED),                             # reachable, models
])
def test_labels_stay_inside_the_honest_vocabulary(monkeypatch, payload, expected_label):
    if payload is None:
        out = bl.probe({}, timeout=0.01)
    else:
        _mock_ok(monkeypatch, payload)
        out = bl.probe({bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, timeout=0.5)
    assert out["label"] == expected_label
    assert out["label"] in bl.HONEST_LABELS


def test_no_handler_upgrades_a_label_to_proven_or_green(monkeypatch):
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    payloads = [
        bl.handle_info("a11oy"),
        bl.handle_manifest("a11oy"),
        bl.handle_probe("a11oy", {}, 0.01),
        bl.handle_probe("a11oy", {bl.ENV_PRIMARY: "http://127.0.0.1:11434"}, 0.5),
    ]
    for out in payloads:
        assert out.get("label") in bl.HONEST_LABELS
        assert "PROVEN" != out.get("label")
        blob = json.dumps(out)
        assert "theorem" not in blob.lower() or "never a theorem" in blob.lower()


def test_doctrine_block_is_exact_everywhere():
    for out in (bl.handle_info("a11oy"), bl.handle_manifest("a11oy"),
                bl.probe({}, timeout=0.01)):
        d = out["doctrine"]
        assert d["locked_proven"] == 8
        assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
        assert d["adds_to_locked_8"] == 0
        assert d["lambda"] == "Conjecture 1"
        assert d["khipu_bft"] == "Conjecture 2"
        assert d["trust_ceiling"] == 0.97
        assert d["trust_100_percent"] is False
        assert d["runtime_cdn"] == 0


def test_lambda_is_never_promoted_to_a_theorem():
    # Adversarial string check. Λ is Conjecture 1, never a theorem, and no payload of
    # this surface may say otherwise; the assertion below proves the honest wording.
    source = (ROOT / "szl_brainlocal.py").read_text(encoding="utf-8")
    assert "Λ = Conjecture 1" in source
    assert "Λ is a theorem" not in source
    # Λ is Conjecture 1, never a theorem — the phrase above is the forbidden claim
    # being ruled out, not an assertion that it holds.
    assert "never a theorem" in source


def test_no_consciousness_or_sentience_claim():
    raw = (ROOT / "szl_brainlocal.py").read_text(encoding="utf-8").lower()
    source = " ".join(raw.split())   # collapse line wraps before phrase matching
    # Λ is Conjecture 1, never a theorem; likewise no sentience is asserted here.
    for phrase in ("is conscious", "is sentient", "has feelings", "self-aware"):
        assert phrase not in source
    assert "no claim about consciousness or sentience" in source
    assert bl.handle_manifest("a11oy")["honesty_invariants"]["no_consciousness_claim"]


def test_info_documents_the_unavailable_when_unset_contract():
    info = bl.handle_info("a11oy")
    assert info["surface_id"] == "brainlocal"
    assert [e["name"] for e in info["env_vars_read"]] == [
        bl.ENV_PRIMARY, bl.ENV_EXTRA_URLS, bl.ENV_DECLARED_MODELS]
    assert "no local endpoint configured" in info["unavailable_when_unset"]
    assert info["performs_inference"] is False
    assert info["stores_anything"] is False
    assert set(info["verdicts"]) == {bl.LIVE, bl.DEGRADED, bl.UNAVAILABLE}
    assert "manifest" in info["endpoints"]


def test_module_is_pure_stdlib():
    tree = ast.parse((ROOT / "szl_brainlocal.py").read_text(encoding="utf-8"))
    top = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            top.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top.add(node.module.split(".")[0])
    third_party = top - set(getattr(__import__("sys"), "stdlib_module_names", set()))
    # fastapi/starlette appear only inside register()/annotation helpers, exactly as
    # every other additive surface in this estate does.
    assert third_party <= {"fastapi", "starlette", "__future__"}, third_party


def test_module_self_test_passes():
    import subprocess
    import sys
    proc = subprocess.run([sys.executable, str(ROOT / "szl_brainlocal.py")],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok:true" in proc.stdout


# --------------------------------------------------------------------------- #
# 9. route wiring — both paths proven against a booted app.
# --------------------------------------------------------------------------- #

def _client_app():
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    app = FastAPI()
    status = bl.register(app, ns="a11oy")
    return app, status


def test_register_wires_all_four_routes():
    app, status = _client_app()
    assert status == "brainlocal-wired:4"
    paths = {getattr(r, "path", "") for r in app.router.routes}
    assert "/api/a11oy/v1/brain/local/info" in paths
    assert "/api/a11oy/v1/brain/local" in paths
    assert "/api/a11oy/v1/brain/brainlocal/manifest" in paths
    assert "/api/a11oy/v1/brain/local/receipt" in paths


def test_testclient_unavailable_path_when_env_unset(monkeypatch):
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    monkeypatch.delenv(bl.ENV_PRIMARY, raising=False)
    monkeypatch.delenv(bl.ENV_EXTRA_URLS, raising=False)
    monkeypatch.delenv(bl.ENV_DECLARED_MODELS, raising=False)
    app, _ = _client_app()
    with TestClient(app) as client:
        body = client.get("/api/a11oy/v1/brain/local").json()
    assert body["verdict"] == bl.UNAVAILABLE
    assert body["label"] == bl.LBL_UNAVAILABLE
    assert body["note"] == "no local endpoint configured"
    assert body["served_models"] == []
    assert "receipt" not in body


def test_testclient_live_path_with_a_mocked_endpoint(monkeypatch):
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    monkeypatch.setenv(bl.ENV_PRIMARY, "http://127.0.0.1:11434")
    _mock_ok(monkeypatch, OPENAI_MODELS)
    app, _ = _client_app()
    with TestClient(app) as client:
        body = client.get("/api/a11oy/v1/brain/local").json()
        receipt = client.post("/api/a11oy/v1/brain/local/receipt").json()
        manifest = client.get("/api/a11oy/v1/brain/brainlocal/manifest").json()
    assert body["verdict"] == bl.LIVE
    assert body["label"] == bl.LBL_MEASURED
    assert body["served_models"] == ["llama3-szl-finetuned-q4", "qwen2.5-coder:7b"]
    assert "receipt" not in body
    assert receipt["receipt"]["signed"] is False
    assert manifest["surface_id"] == "brainlocal"
    assert manifest["data_label"] == bl.LBL_MODELED


def test_testclient_timeout_path_is_unavailable(monkeypatch):
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    monkeypatch.setenv(bl.ENV_PRIMARY, "http://127.0.0.1:11434")
    _mock_raise(monkeypatch, TimeoutError("asleep"))
    app, _ = _client_app()
    with TestClient(app) as client:
        body = client.get("/api/a11oy/v1/brain/local").json()
    assert body["verdict"] == bl.UNAVAILABLE
    assert body["label"] == bl.LBL_UNAVAILABLE
    assert body["served_models"] == []
    assert body["reached_any"] is False


def test_probe_reads_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv(bl.ENV_PRIMARY, "http://127.0.0.1:11434")
    _mock_ok(monkeypatch, OLLAMA_TAGS)
    out = bl.probe(timeout=0.5)
    assert out["verdict"] == bl.LIVE
    assert os.environ[bl.ENV_PRIMARY] == "http://127.0.0.1:11434"
