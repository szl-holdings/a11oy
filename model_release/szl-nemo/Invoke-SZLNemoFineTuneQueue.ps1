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
$ContractPath = Join-Path $Here 'training-contract.json'

if (-not (Test-Path -LiteralPath $Runner -PathType Leaf)) { throw "Missing runner: $Runner" }
if (-not (Test-Path -LiteralPath $ContractPath -PathType Leaf)) { throw "Missing contract: $ContractPath" }
if (-not (Test-Path -LiteralPath $BaseSnapshot -PathType Container)) { throw "Missing immutable base snapshot: $BaseSnapshot" }

if ($Mode -eq 'queue-train') {
  throw 'Legacy PowerShell queue-train is retired because it cannot enforce the Linux Mamba runtime and mandatory capacity-receipt state machine. Use python model_release/szl-nemo/szl_nemo_wsl_queue.py from the pinned WSL2/Linux runtime.'
}

# Status is intentionally read-only: no queue directory, curriculum build,
# preflight subprocess, environment mutation, receipt, or model load occurs.
$Contract = Get-Content -Raw -LiteralPath $ContractPath | ConvertFrom-Json
$Status = [ordered]@{
  schema_version = 'szl.nemo.legacy-windows-status.v1'
  state = 'READ_ONLY_STATUS'
  contract_id = $Contract.contract_id
  candidate_id = $Contract.candidate_id
  base_snapshot = (Resolve-Path -LiteralPath $BaseSnapshot).Path
  linux_queue_required = $true
  native_windows_state = $Contract.runtime.native_windows_state
  queue_entrypoint = 'model_release/szl-nemo/szl_nemo_wsl_queue.py'
  effects = [ordered]@{
    training_started = 'PROVEN_FALSE'
    uploaded = $false
    published = $false
    deployed = $false
    promoted = $false
  }
}
$Status | ConvertTo-Json -Depth 6
exit 0
