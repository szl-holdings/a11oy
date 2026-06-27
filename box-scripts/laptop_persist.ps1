# laptop_persist.ps1 - make the RTX 5050 laptop's sovereign stack survive reboots.
# Pure ASCII (no smart punctuation) so PowerShell 5.1 parses it identically on download.
# RUN AS ADMINISTRATOR:
#   powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\laptop_persist.ps1
#
# Registers AtStartup scheduled tasks (Highest, auto-restart) for:
#   1) Ollama serve with OLLAMA_ORIGINS=* and OLLAMA_HOST=0.0.0.0:11434 (so the
#      tunneled Host header is accepted - this was the 403 fix).
#   2) cloudflared named tunnel "laptop-szl" -> gpu2.a-11-oy.com (uses the
#      config.yml already created).
#   3) the NVML joule exporter on :9471 (engine name "betterwithage" so the Space
#      meters the laptop separately from the tower's "omen").
# Idempotent. Sets the machine-level env vars so EVERY future Ollama start accepts
# the tunnel host - no more manual restarts.

$ErrorActionPreference = "Continue"
$me = "$env:USERPROFILE"

# --- 0) Persist the Ollama origin/host env at MACHINE level (the real 403 fix) ---
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "Machine")
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "Machine")
Write-Host "OK   set machine env OLLAMA_ORIGINS=* and OLLAMA_HOST=0.0.0.0:11434"

function Find-Exe($name, $fallback) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    if ($fallback -and (Test-Path $fallback)) { return $fallback }
    return $null
}

$cloudflared = Find-Exe "cloudflared" "$env:ProgramFiles\cloudflared\cloudflared.exe"
$python      = Find-Exe "python" $null; if (-not $python) { $python = Find-Exe "py" $null }
$ollama      = Find-Exe "ollama" "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
Write-Host "cloudflared : $cloudflared"
Write-Host "python      : $python"
Write-Host "ollama      : $ollama"

function Register-BootTask($taskName, $exe, $argString) {
    if (-not $exe) { Write-Host "SKIP $taskName (exe not found)"; return }
    $action  = New-ScheduledTaskAction -Execute $exe -Argument $argString
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -RunLevel Highest -Settings $set -Force | Out-Null
    Write-Host "OK   registered task: $taskName"
}

# --- 1) Ollama (with the env vars now set machine-wide) ---
if ($ollama) {
    Register-BootTask "Laptop Ollama" $ollama "serve"
} else {
    Write-Host "WARN ollama exe not found; ensure Ollama autostarts."
}

# --- 2) cloudflared named tunnel laptop-szl ---
$cfg = "$me\.cloudflared\config.yml"
if ($cloudflared -and (Test-Path $cfg)) {
    Register-BootTask "Laptop Tunnel" $cloudflared "--config `"$cfg`" tunnel run laptop-szl"
} elseif ($cloudflared) {
    Register-BootTask "Laptop Tunnel" $cloudflared "tunnel run laptop-szl"
} else {
    Write-Host "WARN cloudflared not found; tunnel task not registered."
}

# --- 3) joule exporter (engine name betterwithage so the laptop meters separately) ---
$exporterPy = "$me\omen_joule_exporter.py"
if ($python -and (Test-Path $exporterPy)) {
    # OMEN_ENGINE_NAME=betterwithage matches the Space's GPU-1 exporter_node label.
    Register-BootTask "Laptop Joule Exporter" $python "`"$exporterPy`""
    # Set the engine-name env at machine level so the task picks it up.
    [System.Environment]::SetEnvironmentVariable("OMEN_ENGINE_NAME", "betterwithage", "Machine")
    Write-Host "OK   set OMEN_ENGINE_NAME=betterwithage (laptop meter label)"
} else {
    Write-Host "NOTE exporter script not present yet at $exporterPy (download it to enable laptop metering)."
}

Write-Host ""
Write-Host "=== Registered tasks ==="
Get-ScheduledTask -TaskName "Laptop *" -ErrorAction SilentlyContinue | Select-Object TaskName, State | Format-Table -AutoSize

# --- start them now so no reboot needed ---
# Kill any manual Ollama first so it restarts with the new machine env.
Get-Process *ollama* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2
foreach ($t in @("Laptop Ollama","Laptop Tunnel","Laptop Joule Exporter")) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Start-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        Write-Host "started: $t"
    }
}
Write-Host ""
Write-Host "Done. Laptop stack is boot-persistent. You can close all PowerShell windows."
