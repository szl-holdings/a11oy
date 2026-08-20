"""Focused regression tests for global/Code sovereign-health alignment."""

from __future__ import annotations

import ipaddress

import szl_llm_registry as registry
import szl_provider_http as provider_http


_ENDPOINT_ENVS = (
    "A11OY_BRAIN_URL",
    "A11OY_MODEL_BASE_URL",
    "A11OY_SOVEREIGN_GATEWAY_URL",
    "SZL_LOCAL_LLM_URL",
)


def _clear_endpoint_envs(monkeypatch) -> None:
    for name in _ENDPOINT_ENVS:
        monkeypatch.delenv(name, raising=False)


def test_registry_uses_code_serving_endpoint_for_global_rollup(monkeypatch):
    _clear_endpoint_envs(monkeypatch)
    monkeypatch.setenv("A11OY_MODEL_BASE_URL", "http://127.0.0.1:11434/v1/")

    assert registry._sovereign_base() == "http://127.0.0.1:11434/v1"
    assert registry._sovereign_env_used() == "A11OY_MODEL_BASE_URL"
    assert registry._sovereign_env_present() is True


def test_brain_url_matches_code_precedence(monkeypatch):
    _clear_endpoint_envs(monkeypatch)
    monkeypatch.setenv("A11OY_MODEL_BASE_URL", "http://model.internal:11434/v1")
    monkeypatch.setenv("A11OY_BRAIN_URL", "http://brain.internal:11434/v1")
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "http://legacy.internal:11434/v1")

    assert registry._sovereign_base() == "http://brain.internal:11434/v1"
    assert registry._sovereign_env_used() == "A11OY_BRAIN_URL"


def test_ipv6_loopback_requires_explicit_private_opt_in():
    # Python may call ::1 both reserved and loopback.  The transport contract is
    # based on loopback identity: deny by default, permit only for an explicitly
    # operator-controlled self-hosted adapter.
    assert ipaddress.ip_address("::1").is_loopback
    assert (
        provider_http._classify_address("::1", allow_private=False)
        == "PRIVATE_DESTINATION_REQUIRES_OPT_IN"
    )
    assert provider_http._classify_address("::1", allow_private=True) is None


def test_link_local_is_denied_even_with_private_opt_in():
    assert (
        provider_http._classify_address("169.254.169.254", allow_private=True)
        == "DESTINATION_FORBIDDEN"
    )
