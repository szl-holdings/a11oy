# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "ops/windows/install-cloudflare-tools.ps1"
AUTHORIZE = ROOT / "ops/windows/authorize-cloudflare-production.ps1"
RUNBOOK = ROOT / "docs/CLOUDFLARE_WINDOWS_AUTHORIZATION.md"


def test_cloudflared_install_is_pinned_and_hash_verified() -> None:
    text = INSTALL.read_text(encoding="utf-8")
    assert '$CloudflaredVersion = "2026.8.3"' in text
    assert (
        '$CloudflaredSha256 = "83e726ed18ea78c5ad5213c4c3a3a27051393950d2bc8ed4de69bec12d14eaae"'
        in text
    )
    assert "Get-FileHash" in text
    assert "Get-AuthenticodeSignature" in text
    assert '$signature.Status -ne "Valid"' in text
    assert '$subject -notmatch "Cloudflare"' in text
    assert "cloudflared-windows-amd64.exe" in text


def test_wrangler_is_exact_and_user_local() -> None:
    text = INSTALL.read_text(encoding="utf-8")
    assert '$WranglerVersion = "4.128.0"' in text
    assert 'Join-Path $env:LOCALAPPDATA "SZL\\Cloudflare"' in text
    assert "& $npm install --prefix $WranglerRoot" in text
    assert "--save-exact" in text
    assert "& $wrangler login" in text
    assert "& $wrangler whoami" in text


def test_authorization_never_persists_or_passes_token_as_argument() -> None:
    text = AUTHORIZE.read_text(encoding="utf-8")
    assert "Read-Host" in text and "-AsSecureString" in text
    assert "SecureStringToBSTR" in text
    assert "ZeroFreeBSTR" in text
    assert "$plainToken | & $gh secret set CLOUDFLARE_API_TOKEN" in text
    assert "--body" not in text
    assert "Set-Content" in text
    assert "token_value_recorded = $false" in text
    assert "CLOUDFLARE_API_TOKEN=" not in text


def test_required_provider_scopes_and_zones_are_explicit() -> None:
    authorize = AUTHORIZE.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for marker in (
        "Workers Scripts > Edit",
        "Workers Routes > Edit",
        "DNS > Edit",
        "Zone > Read",
        "a-11-oy.com",
        "a11oy.net",
    ):
        assert marker in authorize
        assert marker.replace(">", "—") in runbook or marker in runbook
    assert "/user/tokens/verify" in authorize
    assert "/workers/routes" in authorize
    assert "/dns_records" in authorize


def test_existing_governed_workflow_is_dispatched() -> None:
    text = AUTHORIZE.read_text(encoding="utf-8")
    assert '$Workflow = "repair-cloudflare-product-edge-production.yml"' in text
    assert "workflow run $Workflow" in text
    assert "--ref main" in text
    assert "-f dry_run=false" in text
    assert 'GitHubEnvironment = "production"' in text
