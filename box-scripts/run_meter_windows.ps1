# SPDX-License-Identifier: Apache-2.0
# No keys in arguments, source, standard output, or the public telemetry payload.
$ErrorActionPreference = 'Stop'
$privateRoot = Split-Path $PSScriptRoot -Parent
Add-Type -AssemblyName System.Security
$launchStage = 'verify-source'
try {
    $receipt = Get-Content -Raw -LiteralPath (Join-Path $privateRoot 'installation.json') | ConvertFrom-Json
    foreach ($entry in $receipt.files.PSObject.Properties) {
        $filePath = Join-Path $PSScriptRoot $entry.Name
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $filePath).Hash.ToLowerInvariant() -ne $entry.Value) { throw 'Installed source changed' }
    }
    $launchStage = 'decrypt-configuration'
    $configPath = Join-Path $privateRoot 'settings.dpapi'
    $plainBytes = [Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($configPath), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    $config = [Text.Encoding]::UTF8.GetString($plainBytes) | ConvertFrom-Json
    [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    $launchStage = 'validate-identity'
    if ($config.schema -ne 'szl.meter.private-config/v1' -or $config.audience -ne $receipt.audience) { throw 'Unexpected meter identity' }
    $env:SZL_METER_HMAC_AUDIENCE = $config.audience
    $env:SZL_METER_HMAC_CLIENT_KEYS = $config.clients | ConvertTo-Json -Compress
    $env:OMEN_EXPORTER_BIND = '127.0.0.1'
    $env:OMEN_EXPORTER_PORT = '9471'
    $env:OMEN_ENGINE_NAME = 'betterwithage'
    $env:PEER_EXPORTERS = ''
    $env:PYTHONUTF8 = '1'
    $launchStage = 'run-exporter'
    # Windows PowerShell 5 turns redirected native stderr into error records.
    # A Python warning must not terminate a healthy exporter; its exit code decides.
    $nativePreference = $ErrorActionPreference
    $LASTEXITCODE = $null
    try {
        $ErrorActionPreference = 'Continue'
        & $receipt.python -u (Join-Path $PSScriptRoot 'omen_joule_exporter.py')
        $meterExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $nativePreference
    }
    if ($null -eq $meterExitCode -or $meterExitCode -ne 0) { throw 'Meter process exited unsuccessfully' }
} catch {
    Write-Output ('Authenticated meter stopped (stage=' + $launchStage + '; type=' + $_.Exception.GetType().Name + ').')
    exit 1
} finally {
    Remove-Item Env:SZL_METER_HMAC_CLIENT_KEYS -ErrorAction SilentlyContinue
}
