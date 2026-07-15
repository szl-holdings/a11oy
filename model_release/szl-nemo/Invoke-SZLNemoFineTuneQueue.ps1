param(
  [ValidateSet('status', 'queue-train')]
  [string]$Mode = 'status',
  [Parameter(Mandatory = $true)]
  [string]$BaseSnapshot,
  [string]$OutputDirectory = '',
  [string]$Confirmation = '',
  [string]$LicenseAcknowledgement = '',
  [ValidateRange(1, 240)]
  [int]$MaxAttempts = 30,
  [ValidateRange(30, 3600)]
  [int]$RetrySeconds = 120,
  [string]$Python = 'python',
  [string]$GitExecutable = $env:SZL_NEMO_GIT
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $Here 'szl_nemo_finetune.py'
$Contract = Get-Content -Raw -LiteralPath (Join-Path $Here 'training-contract.json') | ConvertFrom-Json
$StateDirectory = Join-Path $Here 'queue-state'
New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null

if (-not (Test-Path -LiteralPath $Runner -PathType Leaf)) { throw "Missing runner: $Runner" }
if (-not (Test-Path -LiteralPath $BaseSnapshot -PathType Container)) { throw "Missing immutable base snapshot: $BaseSnapshot" }
if (-not [string]::IsNullOrWhiteSpace($GitExecutable)) {
  if (-not (Test-Path -LiteralPath $GitExecutable -PathType Leaf)) { throw "Missing Git executable: $GitExecutable" }
  $env:SZL_NEMO_GIT = (Resolve-Path -LiteralPath $GitExecutable).Path
}
if ($Mode -eq 'queue-train' -and $Confirmation -cne $Contract.training.confirmation_phrase) {
  throw 'Exact training confirmation phrase is required.'
}
if ($Mode -eq 'queue-train' -and $LicenseAcknowledgement -cne $Contract.base.license_acknowledgement) {
  throw 'Exact NVIDIA license acknowledgement is required.'
}
if ($Mode -eq 'queue-train' -and [string]::IsNullOrWhiteSpace($OutputDirectory)) {
  throw 'OutputDirectory is required for queue-train.'
}

& $Python $Runner build
if ($LASTEXITCODE -ne 0) { throw "Curriculum build failed with exit code $LASTEXITCODE" }

$QueueId = 'szl-nemo-{0}' -f (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss-fff')
$StatePath = Join-Path $StateDirectory "$QueueId.json"
$Attempts = @()

function Write-State {
  param([string]$State, [string]$Reason, [bool]$TrainingStarted = $false)
  $Document = [ordered]@{
    schema_version = 'szl.nemo.queue-state.v1'
    queue_id = $QueueId
    contract_id = $Contract.contract_id
    candidate_id = $Contract.candidate_id
    mode = $Mode
    state = $State
    reason = $Reason
    updated_at = (Get-Date).ToUniversalTime().ToString('o')
    policy = [ordered]@{
      max_attempts = $MaxAttempts
      retry_seconds = $RetrySeconds
      thresholds_may_be_weakened = $false
      processes_may_be_stopped_automatically = $false
      exclusive_training_lease_required = $true
      network_download_allowed_during_training = $false
      upload_allowed = $false
      promotion_automatic = $false
    }
    attempts = $Attempts
    effects = [ordered]@{
      training_started = $TrainingStarted
      uploaded = $false
      published = $false
      deployed = $false
      promoted = $false
    }
  }
  $Temporary = "$StatePath.tmp"
  [System.IO.File]::WriteAllText($Temporary, ($Document | ConvertTo-Json -Depth 8) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
  Move-Item -LiteralPath $Temporary -Destination $StatePath -Force
}

if ($Mode -eq 'status') {
  & $Python $Runner preflight --base-snapshot $BaseSnapshot
  $ExitCode = $LASTEXITCODE
  Write-State -State $(if ($ExitCode -eq 0) { 'READY_FOR_GPU_ADMISSION' } else { 'BLOCKED' }) -Reason 'Status mode validates the immutable base and curriculum but never starts training.'
  exit $ExitCode
}

Write-State -State 'WAITING_FOR_ADMISSION' -Reason 'No model load or training has started.'
for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
  $ProbeReceipt = Join-Path $StateDirectory "$QueueId-probe-$Attempt.json"
  & $Python $Runner preflight --base-snapshot $BaseSnapshot --check-gpu --probe --receipt $ProbeReceipt
  $ProbeExit = $LASTEXITCODE
  $Attempts += [ordered]@{
    number = $Attempt
    evaluated_at = (Get-Date).ToUniversalTime().ToString('o')
    probe_exit_code = $ProbeExit
    probe_receipt = $ProbeReceipt
  }
  if ($ProbeExit -eq 0) {
    Write-State -State 'TRAINING_SOAK' -Reason 'Three-sample probe passed; the runner must still pass the fixed eleven-sample soak.'
    $AttemptOutput = Join-Path $OutputDirectory "$QueueId-attempt-$Attempt"
    $Attempts[-1]['attempt_output'] = $AttemptOutput
    & $Python $Runner train --base-snapshot $BaseSnapshot --output-dir $AttemptOutput --confirmation $Confirmation --license-acknowledgement $LicenseAcknowledgement
    $TrainExit = $LASTEXITCODE
    $Attempts[-1]['train_exit_code'] = $TrainExit
    $TrainingReceiptPath = Join-Path $AttemptOutput 'receipts\training-receipt.json'
    $TrainingActuallyStarted = $false
    if (Test-Path -LiteralPath $TrainingReceiptPath -PathType Leaf) {
      try {
        $TrainingReceipt = Get-Content -Raw -LiteralPath $TrainingReceiptPath | ConvertFrom-Json
        $TrainingActuallyStarted = $null -ne $TrainingReceipt.training_started_at_unix_ns
      } catch {
        $Attempts[-1]['training_receipt_read_error'] = $_.Exception.Message
      }
    }
    $Attempts[-1]['training_started'] = $TrainingActuallyStarted
    if ($TrainExit -eq 0) {
      Write-State -State 'CANDIDATE_GENERATED_NOT_PROMOTED' -Reason 'Training, adapter reload, and held-out evaluation completed. DSSE, transparency, served-tag, and human promotion remain separate gates.' -TrainingStarted $true
      exit 0
    }
    if ($TrainExit -ne 3) {
      Write-State -State 'ABORTED_NOT_PROMOTED' -Reason "Training path returned non-retryable exit code $TrainExit." -TrainingStarted $TrainingActuallyStarted
      exit $TrainExit
    }
  } elseif ($ProbeExit -ne 3) {
    Write-State -State 'ABORTED_NOT_PROMOTED' -Reason "Probe returned unexpected exit code $ProbeExit."
    exit $ProbeExit
  }
  if ($Attempt -lt $MaxAttempts) {
    Write-State -State 'WAITING_FOR_ADMISSION' -Reason 'A fixed gate refused the run; no threshold was weakened and no process was stopped.'
    Start-Sleep -Seconds $RetrySeconds
  }
}

Write-State -State 'EXHAUSTED_NOT_TRAINED' -Reason 'Maximum attempts reached without a fully admitted run.'
exit 3
