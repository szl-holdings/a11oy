# SPDX-License-Identifier: Apache-2.0
# Explicit owner operation: install only the authenticated loopback meter.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$SourceRevision,
    [string]$PrivateRoot = (Join-Path $env:LOCALAPPDATA 'SZL\Meter'),
    [ValidateSet('https://meter2.a-11-oy.com')][string]$Audience = 'https://meter2.a-11-oy.com'
)
$ErrorActionPreference = 'Stop'
$repository = Split-Path $PSScriptRoot -Parent
$actualSource = (& git -C $repository rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualSource -ne $SourceRevision) { throw 'Unexpected installer source revision' }
if (& git -C $repository status --porcelain) { throw 'Installer requires a clean committed checkout' }
$pythonPath = (Get-Command python -ErrorAction Stop).Source
Add-Type -AssemblyName System.Security
New-Item -ItemType Directory -Path $PrivateRoot -Force | Out-Null
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls $PrivateRoot /inheritance:r /grant:r ('*' + $ownerSid + ':(OI)(CI)F') '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Private directory access control failed' }
$configPath = Join-Path $PrivateRoot 'settings.dpapi'
if (-not (Test-Path $configPath)) {
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $clients = @{}
    foreach ($clientName in @('canonical-a11oy', 'local-healthcheck')) {
        $keyBytes = New-Object byte[] 32
        $rng.GetBytes($keyBytes)
        $clients[$clientName] = ([BitConverter]::ToString($keyBytes)).Replace('-', '').ToLowerInvariant()
        [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    }
    $rng.Dispose()
    $config = @{schema='szl.meter.private-config/v1';audience=$Audience;clients=$clients;created_at=[DateTime]::UtcNow.ToString('o')}
    $plainBytes = [Text.Encoding]::UTF8.GetBytes(($config | ConvertTo-Json -Depth 5 -Compress))
    $cipherBytes = [Security.Cryptography.ProtectedData]::Protect($plainBytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    [IO.File]::WriteAllBytes($configPath, $cipherBytes)
    [Array]::Clear($plainBytes, 0, $plainBytes.Length)
} else {
    $plainBytes = [Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($configPath), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    $config = [Text.Encoding]::UTF8.GetString($plainBytes) | ConvertFrom-Json
    [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    if ($config.schema -ne 'szl.meter.private-config/v1' -or $config.audience -ne $Audience) { throw 'Existing private configuration has a different identity' }
}
$programRoot = Join-Path $PrivateRoot 'program'
New-Item -ItemType Directory -Path $programRoot -Force | Out-Null
$copies = @{
    'omen_joule_exporter.py' = (Join-Path $PSScriptRoot 'omen_joule_exporter.py')
    'szl_meter_access.py' = (Join-Path $repository 'szl_meter_access.py')
    'run_meter_windows.ps1' = (Join-Path $PSScriptRoot 'run_meter_windows.ps1')
}
$hashes = @{}
foreach ($fileName in $copies.Keys) {
    $destination = Join-Path $programRoot $fileName
    Copy-Item -LiteralPath $copies[$fileName] -Destination $destination -Force
    $hashes[$fileName] = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
}
$receipt = @{schema='szl.meter.installation/v1';source_revision=$SourceRevision;python=$pythonPath;audience=$Audience;files=$hashes;installed_at=[DateTime]::UtcNow.ToString('o');configuration_protection='DPAPI_CURRENT_USER';listener_started=$false;tunnel_started=$false;secret_values_recorded=$false}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PrivateRoot 'installation.json')
[pscustomobject]@{installed=$true;source_revision=$SourceRevision;private_configuration_present=$true;configuration_protection='DPAPI_CURRENT_USER';listener_started=$false;tunnel_started=$false} | ConvertTo-Json -Compress
