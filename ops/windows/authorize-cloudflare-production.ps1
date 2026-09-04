#Requires -Version 5.1
<#
.SYNOPSIS
Authorizes the bounded SZL Cloudflare production edge without placing a token in shell history.

.DESCRIPTION
Prompts for a scoped Cloudflare user API token as a SecureString, validates the
token and both SZL zones, writes it to the GitHub production environment through
stdin, then dispatches the existing bounded and rollback-capable edge workflow.
The token is never written to disk or included in a command-line argument.
#>
[CmdletBinding()]
param(
    [string]$Repository = "szl-holdings/a11oy",
    [string]$GitHubEnvironment = "production",
    [switch]$SkipDispatch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$InstallRoot = Join-Path $env:LOCALAPPDATA "SZL\Cloudflare"
$ReceiptPath = Join-Path $InstallRoot "authorization-receipt.json"
$RequiredZones = @("a-11-oy.com", "a11oy.net")
$Workflow = "repair-cloudflare-product-edge-production.yml"
$TokenPage = "https://dash.cloudflare.com/profile/api-tokens"

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (($machine, $user) -join ";").Trim(";")
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)][string]$Operation,
        [Parameter(Mandatory = $true)][int]$Code
    )
    if ($Code -ne 0) {
        throw "$Operation failed with exit code $Code."
    }
}

function Ensure-GitHubCli {
    Refresh-ProcessPath
    $gh = Get-Command gh.exe -ErrorAction SilentlyContinue
    if ($gh) {
        return $gh.Source
    }

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "GitHub CLI is required to store the environment secret and dispatch the workflow. Install GitHub CLI, then rerun."
    }

    Write-Host "Installing GitHub CLI with winget..."
    & $winget.Source install --id GitHub.cli --exact --source winget --accept-package-agreements --accept-source-agreements --silent
    Assert-ExitCode -Operation "GitHub CLI installation" -Code $LASTEXITCODE
    Refresh-ProcessPath
    $gh = Get-Command gh.exe -ErrorAction SilentlyContinue
    if (-not $gh) {
        throw "GitHub CLI installation completed, but gh is not visible in this shell. Open a new PowerShell window and rerun."
    }
    return $gh.Source
}

function Invoke-CloudflareJson {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Bearer
    )
    return Invoke-RestMethod -Method Get -Uri $Uri -Headers @{
        Authorization = "Bearer $Bearer"
        Accept = "application/json"
        "User-Agent" = "SZL-Cloudflare-Authorization/1.0"
    }
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$gh = Ensure-GitHubCli

& $gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) {
    Write-Host "Opening GitHub's browser authorization flow..."
    & $gh auth login --hostname github.com --web --git-protocol https --scopes "repo,workflow"
    Assert-ExitCode -Operation "GitHub authorization" -Code $LASTEXITCODE
}

Write-Host "Create a custom Cloudflare USER API token with these exact permissions:"
Write-Host "  Account > Workers Scripts > Edit — your SZL Cloudflare account"
Write-Host "  Zone > Workers Routes > Edit — a-11-oy.com and a11oy.net"
Write-Host "  Zone > DNS > Edit — a-11-oy.com and a11oy.net"
Write-Host "  Zone > Zone > Read — a-11-oy.com and a11oy.net"
Write-Host "Do not use the Global API Key. Do not paste the token into chat or source code."
Start-Process $TokenPage

$secureToken = Read-Host "After Cloudflare shows the token once, paste it here (input is hidden)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
$plainToken = ""
$zoneEvidence = @()
try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plainToken)) {
        throw "No Cloudflare token was entered."
    }

    $verify = Invoke-CloudflareJson -Uri "https://api.cloudflare.com/client/v4/user/tokens/verify" -Bearer $plainToken
    if ($verify.success -ne $true -or $verify.result.status -ne "active") {
        throw "Cloudflare did not report the user API token as active."
    }

    foreach ($zoneName in $RequiredZones) {
        $encoded = [Uri]::EscapeDataString($zoneName)
        $zones = Invoke-CloudflareJson -Uri "https://api.cloudflare.com/client/v4/zones?name=$encoded&status=active&per_page=50" -Bearer $plainToken
        if ($zones.success -ne $true -or @($zones.result).Count -ne 1) {
            throw "The token cannot resolve exactly one active zone for $zoneName. Check its zone resources and Zone Read permission."
        }
        $zone = @($zones.result)[0]
        $zoneId = [string]$zone.id

        $dns = Invoke-CloudflareJson -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records?per_page=1" -Bearer $plainToken
        $routes = Invoke-CloudflareJson -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/workers/routes" -Bearer $plainToken
        if ($dns.success -ne $true -or $routes.success -ne $true) {
            throw "Cloudflare readback failed for $zoneName."
        }
        $zoneEvidence += [ordered]@{
            zone = $zoneName
            zone_id_suffix = $zoneId.Substring([Math]::Max(0, $zoneId.Length - 6))
            dns_readback = $true
            worker_routes_readback = $true
        }
    }

    Write-Host "Writing CLOUDFLARE_API_TOKEN to GitHub environment '$GitHubEnvironment' through stdin..."
    $plainToken | & $gh secret set CLOUDFLARE_API_TOKEN --repo $Repository --env $GitHubEnvironment
    Assert-ExitCode -Operation "GitHub environment secret write" -Code $LASTEXITCODE

    $dispatched = $false
    $run = $null
    if (-not $SkipDispatch) {
        & $gh workflow run $Workflow --repo $Repository --ref main -f dry_run=false
        Assert-ExitCode -Operation "Cloudflare production workflow dispatch" -Code $LASTEXITCODE
        $dispatched = $true
        Start-Sleep -Seconds 4
        $runJson = & $gh run list --repo $Repository --workflow $Workflow --limit 1 --json databaseId,url,status,conclusion,headSha,createdAt
        Assert-ExitCode -Operation "Cloudflare workflow lookup" -Code $LASTEXITCODE
        $run = @($runJson | ConvertFrom-Json)[0]
        if ($run -and $run.url) {
            Start-Process ([string]$run.url)
        }
    }

    $receipt = [ordered]@{
        schema = "szl.cloudflare-production-authorization/v1"
        observed_at_utc = [DateTime]::UtcNow.ToString("o")
        repository = $Repository
        github_environment = $GitHubEnvironment
        secret_name = "CLOUDFLARE_API_TOKEN"
        token_status = "active"
        token_value_recorded = $false
        zones = $zoneEvidence
        workflow = $Workflow
        dispatched = $dispatched
        run = if ($run) { [ordered]@{
            id = $run.databaseId
            url = $run.url
            status = $run.status
            conclusion = $run.conclusion
            head_sha = $run.headSha
            created_at = $run.createdAt
        } } else { $null }
    }
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
    Write-Host "Authorization completed. Secret-free receipt: $ReceiptPath"
    if ($dispatched) {
        Write-Host "The governed production repair is dispatched. Approve the GitHub 'production' environment in the opened run only if GitHub requests it."
    }
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $plainToken = $null
    $secureToken.Dispose()
}
