# tests/test_chaski_token_flip.py
# Proves the TOKEN-FLIP contract of the a11oy Code (Chaski) orchestrator:
# has_inference_credential() and _resolve_hf_token() must reflect the CURRENT
# os.environ on every call, so an HF_TOKEN pasted into the Space secret store
# after process start takes effect INSTANTLY with zero code change.
#
# Honest by construction: no real token is used; we only assert that the
# live/stub decision flips with the environment. No network is touched.
import importlib
import os

import pytest

aco = importlib.import_module("a11oy_code_orchestrator")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Start from a known no-credential baseline for every test.
    for name in aco._HF_TOKEN_NAMES:
        monkeypatch.delenv(name, raising=False)
    for env in ("TOGETHER_API_KEY", "GROQ_API_KEY", "FIREWORKS_API_KEY",
                "DEEPINFRA_API_KEY", "CEREBRAS_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    yield


def test_no_credential_is_stub_mode(monkeypatch):
    assert aco._resolve_hf_token() == ""
    assert aco.has_inference_credential() is False


def test_hf_token_flips_to_live_at_runtime(monkeypatch):
    # No token -> stub.
    assert aco.has_inference_credential() is False
    # Founder pastes HF_TOKEN into the Space secret store (env set AFTER import).
    monkeypatch.setenv("HF_TOKEN", "hf_dummy_not_a_real_key")
    # The decision MUST flip live immediately, with no re-import / redeploy.
    assert aco._resolve_hf_token() == "hf_dummy_not_a_real_key"
    assert aco.has_inference_credential() is True
    # And the live-call headers carry the freshly-resolved token.
    hdrs = aco._inference_headers()
    assert hdrs["Authorization"] == "Bearer hf_dummy_not_a_real_key"


def test_alternate_secret_names_and_quote_stripping(monkeypatch):
    # HF Spaces sometimes saves under a non-standard key with stray quotes.
    monkeypatch.setenv("Token", '  "hf_quoted_value"  ')
    assert aco._resolve_hf_token() == "hf_quoted_value"
    assert aco.has_inference_credential() is True


def test_provider_key_also_enables_live(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_dummy")
    assert aco._resolve_hf_token() == ""  # no HF token
    assert aco.has_inference_credential() is True  # provider key still counts


def test_no_credential_headers_raise_honestly(monkeypatch):
    # With no token, _inference_headers must refuse (503) — never a fake key.
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        aco._inference_headers()
    assert ei.value.status_code == 503
