#Requires -Version 5.1
<#
.SYNOPSIS
Installs pinned Cloudflare command-line tools into the current Windows user profile.

.DESCRIPTION
Installs cloudflared 2026.8.3 from Cloudflare's official GitHub release and
verifies its published SHA-256 plus Authenticode publisher. Installs Wrangler
4.128.0 under a user-local npm prefix. No Cloudflare or GitHub secret is read,
printed, or persisted by this script.
#>
[CmdletBinding()]
param(
    [switch]$AuthorizeWorkers,
    [switch]$AuthorizeTunnel
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$CloudflaredVersion = "2026.8.3"
$CloudflaredSha256 = "83e726ed18ea78c5ad5213c4c3a3a27051393950d2bc8ed4de69bec12d14eaae"
$WranglerVersion = "4.128.0"
$InstallRoot = Join-Path $env:LOCALAPPDATA "SZL\Cloudflare"
$BinRoot = Join-Path $InstallRoot "bin"
$WranglerRoot = Join-Path $InstallRoot "wrangler"
$ReceiptPath = Join-Path $InstallRoot "installation-receipt.json"

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (($machine, $user) -join ";").Trim(";")
}

function Add-UserPathEntry {
    param([Parameter(Mandatory = $true)][string]$Path)

    $normalized = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @($current -split ";" | Where-Object { $_ -and $_.Trim() })
    $alreadyPresent = $false
    foreach ($part in $parts) {
        try {
            if ([IO.Path]::GetFullPath($part).TrimEnd("\") -ieq $normalized) {
                $alreadyPresent = $true
                break
            }
        }
        catch {
            if ($part.TrimEnd("\") -ieq $normalized) {
                $alreadyPresent = $true
                break
            }
        }
    }
    if (-not $alreadyPresent) {
        $next = (@($normalized) + $parts) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $next, "User")
    }
    Refresh-ProcessPath
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

function Ensure-Node {
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($node -and $npm) {
        return $npm.Source
    }

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Node.js is required for Wrangler and winget is unavailable. Install the current Node.js LTS release, then rerun this script."
    }

    Write-Host "Installing Node.js LTS with winget..."
    & $winget.Source install --id OpenJS.NodeJS.LTS --exact --source winget --accept-package-agreements --accept-source-agreements --silent
    Assert-ExitCode -Operation "Node.js installation" -Code $LASTEXITCODE
    Refresh-ProcessPath

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "Node.js installation completed, but npm is not visible in this shell. Open a new PowerShell window and rerun the script."
    }
    return $npm.Source
}

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "This bootstrap supports 64-bit Windows only."
}

New-Item -ItemType Directory -Force -Path $BinRoot, $WranglerRoot | Out-Null

$cloudflared = Join-Path $BinRoot "cloudflared.exe"
$downloadRequired = $true
if (Test-Path -LiteralPath $cloudflared) {
    $existingHash = (Get-FileHash -LiteralPath $cloudflared -Algorithm SHA256).Hash.ToLowerInvariant()
    $downloadRequired = $existingHash -ne $CloudflaredSha256
}

if ($downloadRequired) {
    $download = Join-Path $env:TEMP "cloudflared-$CloudflaredVersion-windows-amd64.exe"
    $url = "https://github.com/cloudflare/cloudflared/releases/download/$CloudflaredVersion/cloudflared-windows-amd64.exe"
    Write-Host "Downloading cloudflared $CloudflaredVersion from Cloudflare's official release..."
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $download

    $observedHash = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($observedHash -ne $CloudflaredSha256) {
        Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue
        throw "cloudflared SHA-256 mismatch. Expected $CloudflaredSha256; observed $observedHash."
    }

    $signature = Get-AuthenticodeSignature -FilePath $download
    $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { "" }
    if ($signature.Status -ne "Valid" -or $subject -notmatch "Cloudflare") {
        Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue
        throw "cloudflared Authenticode verification failed: status=$($signature.Status), signer=$subject"
    }

    Move-Item -LiteralPath $download -Destination $cloudflared -Force
}

Add-UserPathEntry -Path $BinRoot
& $cloudflared --version
Assert-ExitCode -Operation "cloudflared verification" -Code $LASTEXITCODE

$npm = Ensure-Node
Write-Host "Installing Wrangler $WranglerVersion into the SZL user-local tool root..."
& $npm install --prefix $WranglerRoot --no-audit --no-fund --save-exact "wrangler@$WranglerVersion"
Assert-ExitCode -Operation "Wrangler installation" -Code $LASTEXITCODE

$wranglerBin = Join-Path $WranglerRoot "node_modules\.bin"
$wrangler = Join-Path $wranglerBin "wrangler.cmd"
if (-not (Test-Path -LiteralPath $wrangler)) {
    throw "Wrangler installation did not produce $wrangler."
}
Add-UserPathEntry -Path $wranglerBin
& $wrangler --version
Assert-ExitCode -Operation "Wrangler verification" -Code $LASTEXITCODE

$workerAuthorized = $false
if ($AuthorizeWorkers) {
    Write-Host "Opening Cloudflare's interactive Wrangler authorization flow..."
    & $wrangler login
    Assert-ExitCode -Operation "Wrangler login" -Code $LASTEXITCODE
    & $wrangler whoami
    Assert-ExitCode -Operation "Wrangler identity verification" -Code $LASTEXITCODE
    $workerAuthorized = $true
}

$tunnelAuthorized = $false
if ($AuthorizeTunnel) {
    Write-Host "Opening Cloudflare Tunnel authorization. Select the SZL account and an SZL zone in the browser."
    & $cloudflared tunnel login
    Assert-ExitCode -Operation "cloudflared tunnel login" -Code $LASTEXITCODE
    & $cloudflared tunnel list
    Assert-ExitCode -Operation "cloudflared tunnel inventory" -Code $LASTEXITCODE
    $tunnelAuthorized = $true
}

$receipt = [ordered]@{
    schema = "szl.cloudflare-windows-bootstrap/v1"
    observed_at_utc = [DateTime]::UtcNow.ToString("o")
    cloudflared = [ordered]@{
        version = $CloudflaredVersion
        path = $cloudflared
        sha256 = (Get-FileHash -LiteralPath $cloudflared -Algorithm SHA256).Hash.ToLowerInvariant()
        workers_authorized = $workerAuthorized
        tunnel_authorized = $tunnelAuthorized
    }
    wrangler = [ordered]@{
        version = $WranglerVersion
        path = $wrangler
    }
    secret_values_recorded = $false
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
Write-Host "Cloudflare tools are installed. Secret-free receipt: $ReceiptPath"
