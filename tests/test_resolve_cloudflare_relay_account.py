from __future__ import annotations

import json
from http.client import BadStatusLine
from io import BytesIO
from urllib.error import HTTPError, URLError
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
    with pytest.raises(resolver.AccountResolutionError) as error:
        resolver.shared_account(
            {
                resolver.ZONES[0]: zone(resolver.ZONES[0]),
                resolver.ZONES[1]: zone(resolver.ZONES[1], OTHER_ACCOUNT),
            }
        )
    assert error.value.category is resolver.FailureCategory.ACCOUNT_MISMATCH
    assert "a" * 32 not in error.value.diagnostic()
    assert "b" * 32 not in error.value.diagnostic()


def test_unfiltered_account_total_does_not_reject_exact_zone() -> None:
    payload = zone("a11oy.net")
    payload["result_info"] = {"count": 1, "total_count": 2000}
    assert resolver.account_from_zone(payload, "a11oy.net") == ACCOUNT


@pytest.mark.parametrize(
    ("payload", "category"),
    [
        ({"success": False, "result": []}, "UNSUCCESSFUL_RESPONSE"),
        ({"success": True, "result": []}, "NO_ACTIVE_ZONE"),
        (
            {"success": True, "result": [zone("a11oy.net")["result"][0]] * 2},
            "MULTIPLE_ZONES",
        ),
        (zone("a11oy.net", status="pending"), "INACTIVE_ZONE"),
        (zone("a11oy.net", account="invalid"), "INVALID_ACCOUNT_ID"),
        (zone("different.example"), "MISMATCHED_ZONE"),
        ({"success": True, "result": "secret-response"}, "INVALID_RESPONSE"),
    ],
)
def test_rejects_unverified_zone_response(payload: dict, category: str) -> None:
    with pytest.raises(resolver.AccountResolutionError) as error:
        resolver.account_from_zone(payload, "a11oy.net")
    assert error.value.category.value == category
    assert error.value.diagnostic() == (
        f"::error::Cloudflare relay account preflight failed: "
        f"zone=a11oy.net category={category}."
    )


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
    with pytest.raises(resolver.AccountResolutionError, match="RESPONSE_TOO_LARGE"):
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
    assert ACCOUNT not in output.err
    assert OTHER_ACCOUNT not in output.err
    assert "category=ACCOUNT_MISMATCH" in output.err


@pytest.mark.parametrize(
    ("second_payload", "category"),
    [
        ({"success": True, "result": []}, "NO_ACTIVE_ZONE"),
        (
            {"success": True, "result": [zone("a11oy.net")["result"][0]] * 2},
            "MULTIPLE_ZONES",
        ),
        (zone("a11oy.net", status="pending"), "INACTIVE_ZONE"),
        (zone("a11oy.net", account=OTHER_ACCOUNT), "ACCOUNT_MISMATCH"),
        (
            {"success": False, "errors": [{"message": "synthetic-token"}]},
            "UNSUCCESSFUL_RESPONSE",
        ),
        ({"success": True, "result": "synthetic-token"}, "INVALID_RESPONSE"),
    ],
)
def test_main_does_not_export_account_from_partial_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
    second_payload: dict,
    category: str,
) -> None:
    env_path = tmp_path / "github-env"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "synthetic-token")
    monkeypatch.setenv("GITHUB_ENV", str(env_path))
    monkeypatch.setattr(
        resolver,
        "fetch_zone",
        lambda _token, name: (
            zone(name) if name == resolver.ZONES[0] else second_payload
        ),
    )
    assert resolver.main() == 1
    assert not env_path.exists()
    output = capsys.readouterr()
    assert f"category={category}" in output.err
    assert "synthetic-token" not in output.out + output.err
    assert ACCOUNT not in output.out + output.err
    assert OTHER_ACCOUNT not in output.out + output.err


@pytest.mark.parametrize("status", [403, 429])
def test_http_error_logs_only_public_zone_status_and_category(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
    status: int,
) -> None:
    secret = "synthetic-token-private-response"
    env_path = tmp_path / "github-env"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", secret)
    monkeypatch.setenv("GITHUB_ENV", str(env_path))

    def fake_open(request, timeout):
        assert timeout == 15
        name = parse_qs(urlparse(request.full_url).query)["name"][0]
        if name == resolver.ZONES[0]:
            return BytesIO(json.dumps(zone(name)).encode("utf-8"))
        raise HTTPError(
            request.full_url,
            status,
            f"{secret}\n::warning::forged",
            None,
            BytesIO(f'{{"account":"{ACCOUNT}"}}'.encode("utf-8")),
        )

    monkeypatch.setattr(resolver, "urlopen", fake_open)
    assert resolver.main() == 1
    assert not env_path.exists()
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == (
        "::error::Cloudflare relay account preflight failed: "
        f"zone=a11oy.net category=HTTP_STATUS status={status}.\n"
    )


@pytest.mark.parametrize(
    "error",
    [
        URLError("synthetic-token secret network reason"),
        BadStatusLine("synthetic-token"),
    ],
)
def test_transport_error_does_not_log_exception_reason_or_export_account(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    env_path = tmp_path / "github-env"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "synthetic-token")
    monkeypatch.setenv("GITHUB_ENV", str(env_path))

    def fake_open(request, timeout):
        raise error

    monkeypatch.setattr(resolver, "urlopen", fake_open)
    assert resolver.main() == 1
    assert not env_path.exists()
    output = capsys.readouterr()
    assert output.err == (
        "::error::Cloudflare relay account preflight failed: "
        "zone=a-11-oy.com category=TRANSPORT_ERROR.\n"
    )
