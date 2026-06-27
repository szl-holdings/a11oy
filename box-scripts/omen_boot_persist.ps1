# omen_boot_persist.ps1 — make OMEN's sovereign stack survive reboots, headless.
# Registers auto-start (at system startup) for the 3 pieces that must always be up:
#   1) Ollama            (port 11434)  — usually already a Windows service; we verify.
#   2) joule exporter    (port 9471)   — the real NVML meter (Python).
#   3) cloudflared tunnel (omen-szl)   — gpu.a-11-oy.com / meter.a-11-oy.com.
#
# RUN AS ADMINISTRATOR:
#   powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\omen_boot_persist.ps1
#
# Idempotent: re-running just refreshes the tasks. Uses Scheduled Tasks (AtStartup,
# Highest), which is robust and avoids the cloudflared 'service install' tab-completion
# trap. Each task relaunches its process; if a process dies, the next boot restarts it.

$ErrorActionPreference = "Continue"
$me = "$env:USERPROFILE"

function Find-Exe($name, $fallback) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    if ($fallback -and (Test-Path $fallback)) { return $fallback }
    return $null
}

# --- Resolve executables -----------------------------------------------------
$cloudflared = Find-Exe "cloudflared" "$env:ProgramFiles\cloudflared\cloudflared.exe"
$python      = Find-Exe "python" $null
if (-not $python) { $python = Find-Exe "py" $null }
$ollama      = Find-Exe "ollama" "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"

Write-Host "cloudflared : $cloudflared"
Write-Host "python      : $python"
Write-Host "ollama      : $ollama"
Write-Host ""

# --- Helper: register an AtStartup task --------------------------------------
function Register-BootTask($taskName, $exe, $argString) {
    if (-not $exe) { Write-Host "SKIP $taskName (exe not found)"; return }
    $action  = New-ScheduledTaskAction -Execute $exe -Argument $argString
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                  -DontStopIfGoingOnBatteries -StartWhenAvailable `
                  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -RunLevel Highest -Settings $set -Force | Out-Null
    Write-Host "OK   registered task: $taskName"
}

# --- 1) Ollama ----------------------------------------------------------------
# Ollama's installer normally registers a per-user service that autostarts. If a
# service named 'Ollama' exists we leave it alone; else we boot 'ollama serve'.
$ollamaSvc = Get-Service -Name "Ollama*" -ErrorAction SilentlyContinue
if ($ollamaSvc) {
    Write-Host "OK   Ollama already a Windows service ($($ollamaSvc.Name)) — leaving as-is"
} elseif ($ollama) {
    Register-BootTask "OMEN Ollama" $ollama "serve"
} else {
    Write-Host "WARN Ollama exe not found; ensure Ollama autostarts (it usually does)."
}

# --- 2) Joule exporter --------------------------------------------------------
# Prefer the .py if Python exists; both .py and .ps1 are in the repo.
$exporterPy  = "$me\omen_joule_exporter.py"
$exporterPs1 = "$me\omen_joule_exporter.ps1"
if ($python -and (Test-Path $exporterPy)) {
    Register-BootTask "OMEN Joule Exporter" $python "`"$exporterPy`""
} elseif (Test-Path $exporterPs1) {
    Register-BootTask "OMEN Joule Exporter" "powershell.exe" "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$exporterPs1`""
} else {
    Write-Host "WARN exporter script not found at $exporterPy or $exporterPs1"
}

# --- 3) cloudflared tunnel ----------------------------------------------------
$cfg = "$me\.cloudflared\config.yml"
if ($cloudflared -and (Test-Path $cfg)) {
    Register-BootTask "OMEN Tunnel" $cloudflared "--config `"$cfg`" tunnel run omen-szl"
} elseif ($cloudflared) {
    Register-BootTask "OMEN Tunnel" $cloudflared "tunnel run omen-szl"
} else {
    Write-Host "WARN cloudflared not found; tunnel task not registered."
}

Write-Host ""
Write-Host "=== Registered scheduled tasks ==="
Get-ScheduledTask -TaskName "OMEN *" -ErrorAction SilentlyContinue |
    Select-Object TaskName, State | Format-Table -AutoSize

Write-Host ""
Write-Host "Starting tasks now so you don't have to reboot..."
foreach ($t in @("OMEN Ollama","OMEN Joule Exporter","OMEN Tunnel")) {
    $exists = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($exists) { Start-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue; Write-Host "started: $t" }
}
Write-Host ""
Write-Host "Done. These now auto-start on every boot. You can close all PowerShell windows."
