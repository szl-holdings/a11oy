from __future__ import annotations

import json
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import resolve_cloudflare_relay_account as resolver

ACCOUNT = "a" * 32
OTHER_ACCOUNT = "b" * 32


def zone(name: str, account: str = ACCOUNT, status: str = "active") -> dict:
    return {
        "success": True,
        "result": [{"name": name, "status": status, "account": {"id": account}}],
    }


def test_resolves_only_one_shared_active_account() -> None:
    assert (
        resolver.shared_account({name: zone(name) for name in resolver.ZONES})
        == ACCOUNT
    )
    with pytest.raises(resolver.AccountResolutionError, match="different accounts"):
        resolver.shared_account(
            {
                resolver.ZONES[0]: zone(resolver.ZONES[0]),
                resolver.ZONES[1]: zone(resolver.ZONES[1], OTHER_ACCOUNT),
            }
        )


def test_unfiltered_account_total_does_not_reject_exact_zone() -> None:
    payload = zone("a11oy.net")
    payload["result_info"] = {"count": 1, "total_count": 2000}
    assert resolver.account_from_zone(payload, "a11oy.net") == ACCOUNT


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "result": []},
        {"success": True, "result": []},
        {"success": True, "result": [zone("a11oy.net")["result"][0]] * 2},
        zone("a11oy.net", status="pending"),
        zone("a11oy.net", account="invalid"),
        zone("different.example"),
    ],
)
def test_rejects_unverified_zone_response(payload: dict) -> None:
    with pytest.raises(resolver.AccountResolutionError):
        resolver.account_from_zone(payload, "a11oy.net")


def test_fetch_filters_exact_active_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_open(request, timeout):
        assert timeout == 15
        assert request.get_header("Authorization") == "Bearer synthetic-token"
        assert urlparse(request.full_url).path == "/client/v4/zones"
        assert parse_qs(urlparse(request.full_url).query) == {
            "name": ["a11oy.net"],
            "status": ["active"],
            "per_page": ["50"],
        }
        return BytesIO(json.dumps(zone("a11oy.net")).encode("utf-8"))

    monkeypatch.setattr(resolver, "urlopen", fake_open)
    assert resolver.fetch_zone("synthetic-token", "a11oy.net") == zone("a11oy.net")


def test_fetch_rejects_oversized_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        resolver,
        "urlopen",
        lambda _request, timeout: BytesIO(b"x" * (resolver.MAX_RESPONSE_BYTES + 1)),
    )
    with pytest.raises(resolver.AccountResolutionError, match="exceeded"):
        resolver.fetch_zone("synthetic-token", "a11oy.net")


def test_main_writes_account_only_after_both_zones_agree(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "github-env"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "synthetic-token")
    monkeypatch.setenv("GITHUB_ENV", str(env_path))
    monkeypatch.setattr(resolver, "fetch_zone", lambda _token, name: zone(name))
    assert resolver.main() == 0
    assert env_path.read_text(encoding="utf-8") == f"CLOUDFLARE_ACCOUNT_ID={ACCOUNT}\n"
    assert "synthetic-token" not in capsys.readouterr().out

    failed_env_path = tmp_path / "github-env-failed"
    monkeypatch.setenv("GITHUB_ENV", str(failed_env_path))
    monkeypatch.setattr(
        resolver,
        "fetch_zone",
        lambda _token, name: zone(
            name, OTHER_ACCOUNT if name == resolver.ZONES[1] else ACCOUNT
        ),
    )
    assert resolver.main() == 1
    assert not failed_env_path.exists()
    output = capsys.readouterr()
    assert "synthetic-token" not in output.err
