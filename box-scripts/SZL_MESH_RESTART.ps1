# SZL_MESH_RESTART.ps1 - bring the sovereign mesh back up (tunnels + Ollama + meter).
# ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 files without a BOM.
# Run AS ADMINISTRATOR on EACH box (tower "omen" AND laptop "betterwithage"):
#
#   powershell -ExecutionPolicy RemoteSigned -File .\SZL_MESH_RESTART.ps1
#
# What it does, honestly and idempotently:
#   1) Finds this box's boot-persisted scheduled tasks (OMEN */ laptop equivalents) and starts them.
#   2) If no tunnel task exists, starts cloudflared directly using ~/.cloudflared/config.yml,
#      auto-detecting the tunnel name (omen-szl / laptop-szl / any configured tunnel).
#   3) Verifies from the outside: probes the public hostnames and prints the code per host.
# Nothing here installs anything, edits the registry, or changes config files.

$ErrorActionPreference = "Continue"
Write-Host "=== SZL mesh restart on $(hostname) ==="
Write-Host ""

# --- 1) Start existing scheduled tasks (the boot-persisted stack) --------------
$patterns = @("*Ollama*", "*Joule*", "*Tunnel*", "*cloudflared*", "*LiteLLM*")
$startedAny = $false
foreach ($pat in $patterns) {
    $tasks = Get-ScheduledTask -TaskName $pat -ErrorAction SilentlyContinue
    foreach ($task in $tasks) {
        if ($task.State -ne "Running") {
            Start-ScheduledTask -TaskName $task.TaskName -ErrorAction SilentlyContinue
            Write-Host ("started task: " + $task.TaskName)
            $startedAny = $true
        } else {
            Write-Host ("already running: " + $task.TaskName)
        }
    }
}
if (-not $startedAny) { Write-Host "(no stopped matching tasks found)" }

# --- 2) Fallback: start cloudflared directly if no tunnel task exists ----------
$tunnelTask = Get-ScheduledTask -TaskName "*Tunnel*" -ErrorAction SilentlyContinue
$cfRunning = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $tunnelTask -and -not $cfRunning) {
    $cf = $null
    $cfCmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cfCmd) { $cf = $cfCmd.Source }
    if (-not $cf) {
        $candidate = Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe"
        if (Test-Path $candidate) { $cf = $candidate }
    }
    $cfg = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
    $tname = $null
    if (Test-Path $cfg) {
        $line = Select-String -Path $cfg -Pattern '^\s*tunnel:\s*(\S+)' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($line) { $tname = $line.Matches[0].Groups[1].Value }
    }
    if (-not $tname -and $cf) {
        $list = & $cf tunnel list 2>$null | Select-String -Pattern "omen-szl|laptop-szl"
        if ($list) { $tname = ($list[0].ToString() -split "\s+")[1] }
    }
    if ($cf -and $tname) {
        Write-Host ("starting cloudflared directly for tunnel " + $tname)
        Start-Process -FilePath $cf -ArgumentList @("--config", $cfg, "tunnel", "run", $tname) -WindowStyle Hidden
    } else {
        Write-Host "WARN: cloudflared or tunnel name not found. Re-run your persist script:"
        Write-Host "  tower:  powershell -ExecutionPolicy RemoteSigned -File $env:USERPROFILE\omen_boot_persist.ps1"
        Write-Host "  laptop: box-scripts\laptop_persist.ps1 from the a11oy repo"
    }
}

# --- 3) Start Ollama if it is down (native, tailnet-only) -----------------------
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    $ollamaExe = $null
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCmd) { $ollamaExe = $ollamaCmd.Source }
    if (-not $ollamaExe) {
        $oc = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path $oc) { $ollamaExe = $oc }
    }
    if ($ollamaExe) {
        Start-Process -FilePath $ollamaExe -ArgumentList @("serve") -WindowStyle Hidden
        Write-Host "started: ollama serve"
    }
}

Start-Sleep -Seconds 8

# --- 4) Verify from the outside (print truth per host) --------------------------
Write-Host ""
Write-Host "=== external probes ==="
$hostsToProbe = @("gateway.a-11-oy.com", "gpu.a-11-oy.com", "gpu2.a-11-oy.com", "meter.a-11-oy.com", "meter2.a-11-oy.com", "holdings.a-11-oy.com")
foreach ($h in $hostsToProbe) {
    $code = "ERR"
    try {
        $code = (curl.exe -s -o NUL -w "%{http_code}" --max-time 10 ("https://" + $h)).Trim()
    } catch { $code = "ERR" }
    $note = "check manually"
    if ($code -eq "200") { $note = "OK" }
    elseif ($code -eq "301" -or $code -eq "302") { $note = "OK (redirect)" }
    elseif ($code -eq "403") { $note = "OK - Cloudflare Access is guarding it (expected on gpu2)" }
    elseif ($code -eq "404") { $note = "tunnel up, no route or content behind it" }
    elseif ($code -eq "530") { $note = "tunnel DOWN - cloudflared not connected for this host" }
    elseif ($code -eq "000") { $note = "no DNS record or unreachable" }
    Write-Host ($code.PadRight(6) + $h + "  -  " + $note)
}

Write-Host ""
Write-Host "Done. Any 530 that persists means the tunnel on this box is up but its local service is down:"
Write-Host "  Ollama:   ollama serve            (port 11434, tailnet-only - never public)"
Write-Host "  Exporter: python omen_joule_exporter.py    (port 9471)"
Write-Host "  LiteLLM:  litellm --config box-scripts\litellm_config.yaml --port 4000"
