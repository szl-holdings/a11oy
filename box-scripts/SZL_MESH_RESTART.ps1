# SZL_MESH_RESTART.ps1 — bring the sovereign mesh back up (tunnels + Ollama + meter).
# Companion to box-scripts/SOVEREIGN_MESH_RUNBOOK.md. Run AS ADMINISTRATOR on EACH box
# (tower `omen` AND laptop `betterwithage`). Local unsigned script, so RemoteSigned is
# sufficient — no policy bypass needed:
#
#   powershell -ExecutionPolicy RemoteSigned -File .\SZL_MESH_RESTART.ps1
#
# What it does, honestly and idempotently:
#   1) Finds this box's boot-persisted scheduled tasks (OMEN */laptop equivalents) and starts them.
#   2) If no tunnel task exists, starts cloudflared directly using ~/.cloudflared/config.yml,
#      auto-detecting the tunnel name (omen-szl / laptop-szl / any configured tunnel).
#   3) Verifies from the outside: probes the public hostnames and prints 200/403/530 per host.
# Nothing here installs anything, edits the registry, or changes config files.
# If a probe still shows 530 after this, the box's tunnel is up but the LOCAL service behind
# it (Ollama :11434, exporter :9471, LiteLLM :4000) is the thing to start — steps are below.

$ErrorActionPreference = "Continue"
Write-Host "=== SZL mesh restart — $(hostname) ===`n"

# --- 1) Start existing scheduled tasks (the boot-persisted stack) ---------------
$patterns = @("*Ollama*", "*Joule*", "*Tunnel*", "*cloudflared*", "*LiteLLM*")
$started = @()
foreach ($pat in $patterns) {
    Get-ScheduledTask -TaskName $pat -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.State -ne "Running") {
            Start-ScheduledTask -TaskName $_.TaskName -ErrorAction SilentlyContinue
            $started += $_.TaskName
            Write-Host "started task: $($_.TaskName)"
        } else {
            Write-Host "already running: $($_.TaskName)"
        }
    }
}
if (-not $started) { Write-Host "(no matching scheduled tasks found in a stopped state)" }

# --- 2) Fallback: start cloudflared directly if no tunnel task exists -----------
$tunnelTask = Get-ScheduledTask -TaskName "*Tunnel*" -ErrorAction SilentlyContinue
$cfRunning = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $tunnelTask -and -not $cfRunning) {
    $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
    if (-not $cf) { $cf = "$env:ProgramFiles\cloudflared\cloudflared.exe" }
    $cfg = "$env:USERPROFILE\.cloudflared\config.yml"
    $tname = $null
    if (Test-Path $cfg) {
        $line = Select-String -Path $cfg -Pattern '^\s*tunnel:\s*(\S+)' | Select-Object -First 1
        if ($line) { $tname = $line.Matches[0].Groups[1].Value }
    }
    if (-not $tname) {
        # last resort: ask cloudflared which tunnels this box owns
        $list = & $cf tunnel list 2>$null | Select-String -Pattern 'omen-szl|laptop-szl'
        if ($list) { $tname = ($list[0] -split '\s+')[1] }
    }
    if ($cf -and (Test-Path $cf) -and $tname) {
        Write-Host "starting cloudflared directly for tunnel $tname"
        Start-Process -FilePath $cf -ArgumentList "--config `"$cfg`" tunnel run $tname" -WindowStyle Hidden
    } else {
        Write-Host "WARN: cloudflared or tunnel name not found. Re-run your persist script:"
        Write-Host "  powershell -ExecutionPolicy RemoteSigned -File `$env:USERPROFILE\omen_boot_persist.ps1   # on the tower"
        Write-Host "  (laptop: box-scripts\laptop_persist.ps1 from the a11oy repo)"
    }
}

# --- 3) If the local services are down, start them (native, honest) -------------
$ollama = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollamaExe) { $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" }
    if (Test-Path $ollamaExe) { Start-Process $ollamaExe "serve" -WindowStyle Hidden; Write-Host "started: ollama serve" }
}

Start-Sleep -Seconds 8   # give the tunnel a moment to register connections

# --- 4) Verify from the outside (probes print truth, never green-on-faith) ------
Write-Host "`n=== external probes ==="
$hosts = @("gateway.a-11-oy.com", "gpu.a-11-oy.com", "gpu2.a-11-oy.com", "meter.a-11-oy.com", "meter2.a-11-oy.com", "holdings.a-11-oy.com")
foreach ($h in $hosts) {
    try {
        $code = (curl.exe -s -o NUL -w "%{http_code}" --max-time 10 "https://$h").Trim()
    } catch { $code = "ERR" }
    $note = switch ($code) {
        "200" { "OK" } "301" { "OK (redirect)" } "302" { "OK (redirect)" }
        "403" { "OK — Cloudflare Access is guarding it (expected on gpu2)" }
        "404" { "tunnel up, no route/content behind it" }
        "530" { "tunnel DOWN — cloudflared not connected for this host" }
        "000" { "no DNS record (never created)" }
        default { "check manually" }
    }
    Write-Host ("{0}  {1}  — {2}" -f $code, $h, $note)
}
Write-Host "`nDone. 530s that persist mean the tunnel on THIS box is up but its local service is down:"
Write-Host "  Ollama:   ollama serve           (port 11434, tailnet-only — never public)"
Write-Host "  Exporter: python omen_joule_exporter.py   (port 9471)"
Write-Host "  LiteLLM:  litellm --config box-scripts\litellm_config.yaml --port 4000"
