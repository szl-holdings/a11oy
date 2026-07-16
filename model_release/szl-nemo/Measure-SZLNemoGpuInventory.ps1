[CmdletBinding()]
param(
    [Parameter()]
    [string] $OutputPath
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$contractPath = Join-Path $here 'training-contract.json'
$contract = Get-Content -Raw -LiteralPath $contractPath | ConvertFrom-Json
$minimumFree = [int] $contract.gpu_admission.minimum_free_memory_mib
$maximumUtilization = [int] $contract.gpu_admission.maximum_utilization_pct
$maximumTemperature = [int] $contract.gpu_admission.maximum_temperature_c
if ($OutputPath -and (Test-Path -LiteralPath $OutputPath)) {
    throw 'GPU inventory receipt path already exists; evidence is append-only'
}

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction Stop
$rawGpu = & $nvidiaSmi.Source '--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu' '--format=csv,noheader,nounits'
if ($LASTEXITCODE -ne 0 -or -not $rawGpu) {
    throw 'nvidia-smi GPU inventory failed'
}
$gpuRows = @(
    $rawGpu | Where-Object { $_ } | ForEach-Object {
        $values = @($_.ToString().Split(',') | ForEach-Object { $_.Trim() })
        if ($values.Count -ne 8) {
            throw 'unexpected nvidia-smi GPU inventory shape'
        }
        [pscustomobject][ordered]@{
            index = [int] $values[0]
            uuid = $values[1]
            name = $values[2]
            memory_total_mib = [int] $values[3]
            memory_used_mib = [int] $values[4]
            memory_free_mib = [int] $values[5]
            utilization_pct = [int] $values[6]
            temperature_c = [int] $values[7]
        }
    }
)
$requiredName = [string] $contract.runtime.required_device_name
$matches = @($gpuRows | Where-Object { $_.index -eq 0 -and $_.name -eq $requiredName })
if ($matches.Count -ne 1) {
    throw 'nvidia-smi index 0 does not uniquely match the contract-required GPU'
}
$gpu = $matches[0]

$samples = @()
$processMemoryState = 'PASS'
$processMemoryError = $null
try {
    $samples = @(
        (Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples |
            Where-Object CookedValue -gt 1MB |
            ForEach-Object {
                if ($_.InstanceName -match '^pid_(?<pid>[0-9]+)_') {
                    [pscustomobject]@{
                        pid = [int] $Matches.pid
                        reported_dedicated_mib = [math]::Round($_.CookedValue / 1MB, 1)
                    }
                }
            } |
            Where-Object { $null -ne $_ } |
            Group-Object pid |
            ForEach-Object {
                $pidValue = [int] $_.Name
                $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
                $path = $null
                if ($process) {
                    try { $path = $process.Path } catch { $path = $null }
                }
                [pscustomobject][ordered]@{
                    pid = $pidValue
                    process_name = if ($process) { $process.ProcessName } else { 'UNKNOWN' }
                    executable_path = $path
                    reported_dedicated_mib = [double] (($_.Group | Measure-Object reported_dedicated_mib -Maximum).Maximum)
                    measurement_basis = 'WDDM_COUNTER_REPORTED_NOT_NVML_RESIDENT'
                }
            } |
            Sort-Object reported_dedicated_mib -Descending
    )
} catch {
    $samples = @()
    $processMemoryState = 'UNKNOWN_UNAVAILABLE'
    $processMemoryError = $_.Exception.GetType().Name
}

$freeGap = [math]::Max(0, $minimumFree - $gpu.memory_free_mib)
$receipt = [ordered]@{
    schema_version = 'szl.nemo.gpu-inventory-receipt.v1'
    state = if ($freeGap -eq 0 -and $gpu.utilization_pct -le $maximumUtilization -and $gpu.temperature_c -le $maximumTemperature) { 'SINGLE_SAMPLE_PASS_NOT_ADMISSION' } else { 'OPERATOR_ACTION_REQUIRED' }
    measured_at = [DateTimeOffset]::UtcNow.ToString('o')
    contract_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $contractPath).Hash.ToLowerInvariant()
    helper_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $MyInvocation.MyCommand.Path).Hash.ToLowerInvariant()
    gpu = $gpu
    fixed_policy = [ordered]@{
        minimum_free_memory_mib = $minimumFree
        maximum_utilization_pct = $maximumUtilization
        maximum_temperature_c = $maximumTemperature
        thresholds_may_be_weakened = $false
        processes_may_be_stopped_automatically = $false
    }
    free_memory_gap_mib = $freeGap
    process_memory = $samples
    process_memory_state = $processMemoryState
    process_memory_error_type = $processMemoryError
    process_memory_limitation = 'WDDM counters are scheduling/commit evidence and are not additive NVML-resident VRAM.'
    operator_guidance = 'Move or close GPU-accelerated GUI/overlay workloads manually, cool the laptop, then rerun the governed three-sample WSL preflight.'
    effects = [ordered]@{
        processes_stopped = $false
        gpu_preferences_changed = $false
        training_started = $false
        files_written = [bool] $OutputPath
    }
}

$json = $receipt | ConvertTo-Json -Depth 8
if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $temporary = "$OutputPath.tmp.$PID"
    $committed = $false
    try {
        $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + "`n")
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        } finally {
            $stream.Dispose()
        }
        [IO.File]::Move($temporary, $OutputPath)
        $committed = $true
    } finally {
        if (-not $committed -and (Test-Path -LiteralPath $temporary)) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}
$json
