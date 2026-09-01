# SZL_TUNNEL_HEAL.ps1 - diagnose and self-heal tunnel DNS from THIS box.
# ASCII-only (Windows PowerShell 5.1 safe). Run AS ADMINISTRATOR on each box:
#   powershell -ExecutionPolicy RemoteSigned -File .\SZL_TUNNEL_HEAL.ps1
#
# Why this works from the box: cloudflared's local cert.pem already has tunnel
# management rights on the account, so "tunnel route dns" rewrites the CNAMEs
# without any API token. No secrets are printed or transmitted anywhere new.

$ErrorActionPreference = "Continue"
Write-Host ("=== SZL tunnel heal on " + $(hostname) + " ===")
Write-Host ""

# --- 1) Show the tunnels this box can see (IDs live here) ----------------------
Write-Host "--- cloudflared tunnel list ---"
cloudflared tunnel list
Write-Host ""

# --- 2) Read this box's own config: tunnel name + ingress hostnames ------------
$cfg = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
if (-not (Test-Path $cfg)) {
    Write-Host "NO config at $cfg - is cloudflared set up on this box? Run omen_boot_persist.ps1 first."
    exit 1
}
$tnameMatch = Select-String -Path $cfg -Pattern '^\s*tunnel:\s*(\S+)' | Select-Object -First 1
$tname = $null
if ($tnameMatch) { $tname = $tnameMatch.Matches[0].Groups[1].Value }
if (-not $tname) {
    $idMatch = Select-String -Path $cfg -Pattern '^\s*tunnel:\s*([0-9a-f-]{36})' | Select-Object -First 1
}
Write-Host ("config tunnel: " + $tname)

$hostNames = @()
Select-String -Path $cfg -Pattern 'hostname:\s*(\S+)' | ForEach-Object {
    $hostNames += $_.Matches[0].Groups[1].Value
}
if ($hostNames.Count -eq 0) {
    Write-Host "WARN: no ingress hostnames found in config.yml - nothing to re-route."
}
Write-Host ("ingress hostnames: " + ($hostNames -join ", "))
Write-Host ""

# --- 3) Re-route each hostname to THIS tunnel, overwriting stale IDs -----------
foreach ($h in $hostNames) {
    Write-Host ("route dns --overwrite-dns " + $tname + " " + $h)
    cloudflared tunnel route dns --overwrite-dns $tname $h
}
Write-Host ""

# --- 4) Make sure the tunnel process is actually up ----------------------------
$proc = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $proc) {
    $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
    if (-not $cf) { $cf = Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe" }
    if (Test-Path $cf) {
        Write-Host "starting cloudflared now..."
        Start-Process -FilePath $cf -ArgumentList @("--config", $cfg, "tunnel", "run") -WindowStyle Hidden
        Start-Sleep -Seconds 8
    } else {
        Write-Host "WARN: cloudflared.exe not found."
    }
} else {
    Write-Host "cloudflared already running."
}
Write-Host ""

# --- 5) Probe and print truth per host ------------------------------------------
Write-Host "--- external probes ---"
foreach ($h in $hostNames) {
    $code = "ERR"
    try { $code = (curl.exe -s -o NUL -w "%{http_code}" --max-time 10 ("https://" + $h)).Trim() } catch {}
    $note = "check manually"
    if ($code -eq "200") { $note = "OK" }
    elseif ($code -eq "403") { $note = "OK - Access guard (expected where configured)" }
    elseif ($code -eq "404") { $note = "tunnel up, nothing serving on the local port" }
    elseif ($code -eq "502" -or $code -eq "503") { $note = "tunnel connected, local service down (start Ollama/exporter/LiteLLM)" }
    elseif ($code -eq "530") { $note = "STILL DOWN - tunnel not connected; check step 1 output for this tunnel's status" }
    Write-Host ($code.PadRight(6) + $h + "  -  " + $note)
}
Write-Host ""
Write-Host "If a 530 persists after this: run 'cloudflared tunnel info " + $tname + "' and screenshot it."
