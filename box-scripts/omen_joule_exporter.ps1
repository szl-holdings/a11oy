# omen-joule-exporter (PowerShell) — REAL NVML power/joule meter for OMEN.
# Serves the exact JSON the a11oy energy-operator expects on http://0.0.0.0:9471/ :
#   {"engines":[{"engine":"omen","joules":<J>,"gpus":[{"index":0,"name":"..","power_w":<W>,"joules":<J>,"live":true}]}],"totals":{"joules":<J>}}
# HONESTY: power_w is read from REAL nvidia-smi power.draw; joules is the time-integral
# of that real power. If a GPU's power is unreadable, live=false and power_w=null for it
# (never a fabricated joule). Pure PowerShell + nvidia-smi — no Python, no installs.
#
# RUN (OMEN PowerShell):  powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\omen_joule_exporter.ps1
# Then tunnel port 9471 and point A11OY_JOULE_METER_URL at the tunnel.
#
# NOTE: per-inference model energy (the top-level models[] array populated from
# ollama_energy_probe.py's OLLAMA_ENERGY_JSON) is served ONLY by the Python exporter
# (omen_joule_exporter.py), which is canonical for the GLM MEASURED joules/token feed.
# This PowerShell exporter serves engines/totals only; if you need the GLM node's
# measured energy on the surface, run the Python exporter instead.

$Port        = if ($env:OMEN_EXPORTER_PORT) { [int]$env:OMEN_EXPORTER_PORT } else { 9471 }
$EngineName  = if ($env:OMEN_ENGINE_NAME)   { $env:OMEN_ENGINE_NAME }        else { "omen" }
$SampleEvery = if ($env:OMEN_SAMPLE_EVERY_S){ [double]$env:OMEN_SAMPLE_EVERY_S } else { 2.0 }

# Cumulative joules + last sample per GPU index (kept in script scope).
$script:cumJoules  = @{}   # index -> joules (double)
$script:lastSample = @{}   # index -> @{ power_w; name; live; ts }
$script:prevTs     = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0

function Read-GpuPower {
    # Returns array of @{ index; name; power_w (or $null) }
    $rows = @()
    try {
        $out = & nvidia-smi --query-gpu=index,name,power.draw --format=csv,noheader,nounits 2>$null
        foreach ($line in $out) {
            $parts = $line -split ','
            if ($parts.Count -lt 3) { continue }
            $idx = 0
            if (-not [int]::TryParse($parts[0].Trim(), [ref]$idx)) { continue }
            $name = $parts[1].Trim()
            $pw = $null
            $tmp = 0.0
            if ([double]::TryParse($parts[2].Trim(), [ref]$tmp)) { $pw = $tmp }
            $rows += @{ index = $idx; name = $name; power_w = $pw }
        }
    } catch { }
    return $rows
}

function Update-Samples {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    $dt  = $now - $script:prevTs
    $script:prevTs = $now
    foreach ($r in (Read-GpuPower)) {
        $idx = $r.index
        if ($null -ne $r.power_w -and $dt -gt 0) {
            if (-not $script:cumJoules.ContainsKey($idx)) { $script:cumJoules[$idx] = 0.0 }
            $script:cumJoules[$idx] += $r.power_w * $dt
        }
        $script:lastSample[$idx] = @{
            power_w = $r.power_w
            name    = $r.name
            live    = ($null -ne $r.power_w)
            ts      = $now
        }
    }
}

function Get-MeterJson {
    $gpus  = @()
    $total = 0.0
    foreach ($idx in ($script:lastSample.Keys | Sort-Object)) {
        $s = $script:lastSample[$idx]
        $j = if ($script:cumJoules.ContainsKey($idx)) { $script:cumJoules[$idx] } else { 0.0 }
        $total += $j
        $gpus += [ordered]@{
            index   = $idx
            name    = $s.name
            power_w = $s.power_w
            joules  = [math]::Round($j, 3)
            live    = $s.live
        }
    }
    $obj = [ordered]@{
        engines = @(@{ engine = $EngineName; joules = [math]::Round($total,3); gpus = $gpus })
        totals  = @{ joules = [math]::Round($total,3) }
        exporter = "omen-joule-exporter (PowerShell, real nvidia-smi)"
        ts = ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0)
    }
    return ($obj | ConvertTo-Json -Depth 6 -Compress)
}

# Warm one sample so the first scrape isn't empty.
Update-Samples

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add("http://+:$Port/")
try {
    $listener.Start()
} catch {
    Write-Host "Could not bind port $Port. Run PowerShell as Administrator, or:"
    Write-Host "  netsh http add urlacl url=http://+:$Port/ user=Everyone"
    throw
}
Write-Host "omen-joule-exporter serving on http://0.0.0.0:$Port/  (engine=$EngineName)"
Write-Host "Press Ctrl+C to stop. Keep this window open."

while ($listener.IsListening) {
    try {
        $ctx = $listener.GetContext()           # blocks for a request
        Update-Samples                          # refresh real readings on each scrape
        $json  = Get-MeterJson
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
        $ctx.Response.ContentType = "application/json"
        $ctx.Response.Headers.Add("Access-Control-Allow-Origin","*")
        $ctx.Response.ContentLength64 = $bytes.Length
        $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
        $ctx.Response.OutputStream.Close()
    } catch {
        Start-Sleep -Milliseconds 200
    }
}
