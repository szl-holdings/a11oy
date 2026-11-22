#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Windows VM-model gateway host preflight; READ-ONLY, never release authority.

Runs one bounded native Windows observation without reading any credentials.
Missing private runtime, disabled task, or foreign port ownership are reported
as fixed finding codes. A structurally complete snapshot still does not prove
the model, signer, task's process ancestry, or production readiness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

OBS_SCHEMA = "szl.vm-model-gateway-host-observation/v1"
RESULT_SCHEMA = "szl.vm-model-gateway-host-preflight/v1"
TASK_NAME = "SZL-VM-Model-Gateway"

# This PowerShell reads only task metadata, file *existence*, and TCP listener
# metadata. It never opens credential files, prints full task arguments, reads
# process command lines, or changes the scheduler or any process.
WINDOWS_READBACK = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$root=Join-Path $env:LOCALAPPDATA 'SZL\VmModelRuntime'
$task=Get-ScheduledTask -TaskName 'SZL-VM-Model-Gateway' -ErrorAction SilentlyContinue
$taskInfo=$null
if($task){$taskInfo=Get-ScheduledTaskInfo -TaskName 'SZL-VM-Model-Gateway' -ErrorAction SilentlyContinue}
$actions=@();if($task){$actions=@($task.Actions)}
$hasAction=($actions.Count -eq 1)
$action=$null;if($hasAction){$action=$actions[0]}
$expectedBootstrap=Join-Path $root 'bootstrap.py'
$argsText='';if($action){$argsText=[string]$action.Arguments}
$bootstrapArgs=$argsText.Contains('"' + $expectedBootstrap + '"')
$binaryIsPythonw=($hasAction -and (Split-Path ([string]$action.Execute) -Leaf) -ieq 'pythonw.exe')
$binaryExists=($hasAction -and (Test-Path -LiteralPath ([string]$action.Execute) -PathType Leaf))
# Probe only the sibling interpreter under the operator's normal per-user
# Python install root. An unexpected task executable is never launched.
$pythonProbeAttempted=$false
$pythonProbePassed=$false
if($binaryIsPythonw -and $binaryExists){
 try{
  $candidate=Join-Path (Split-Path ([string]$action.Execute) -Parent) 'python.exe'
  $allowedRoot=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\Python')).TrimEnd('\') + '\'
  $canonical=[IO.Path]::GetFullPath($candidate)
  $item=Get-Item -LiteralPath $canonical -ErrorAction SilentlyContinue
  if($canonical.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -and
     $item -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){
    $pythonProbeAttempted=$true
    try{
     $probeOutput=(& $canonical -I -B -c 'import encodings;print("SZL_STDLIB_PROBE_OK")' 2>$null | Select-Object -Last 1)
     $pythonProbePassed=($LASTEXITCODE -eq 0 -and
                         ([string]$probeOutput).Trim() -ceq 'SZL_STDLIB_PROBE_OK')
    }catch{$pythonProbePassed=$false}
  }
 }catch{$pythonProbePassed=$false}
}
$nativeCount=$null;if($task){$nativeCount=[int]$task.Settings.RestartCount}
$sourceFiles=@(
 (Join-Path $root 'source\ops\vm-model-gateway\gateway.py'),
 (Join-Path $root 'source\ops\vm-model-gateway\runtime_config.py'),
 (Join-Path $root 'source\szl_dsse.py'),
 (Join-Path $root 'source\szl_content_address.py')
)
$sourceCount=@($sourceFiles|Where-Object{Test-Path -LiteralPath $_ -PathType Leaf}).Count
$portsFound=$false
$listeners=@()
try{
  $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop)
  $portsFound=$true
}catch{$portsFound=$false}
$gatewayListening=[bool](@($listeners|Where-Object {$_.LocalPort -eq 4001 -and $_.LocalAddress -eq '127.0.0.1'}).Count)
$tunnelListening=[bool](@($listeners|Where-Object {$_.LocalPort -eq 19484 -and $_.LocalAddress -eq '127.0.0.1'}).Count)
$foreign4000=[bool](@($listeners|Where-Object {$_.LocalPort -eq 4000}).Count)
$taskState='UNAVAILABLE'
if($task){$taskState=[string]$task.State}
$lastResult=$null
if($taskInfo){$lastResult=[long]$taskInfo.LastTaskResult}
[ordered]@{
 schema='szl.vm-model-gateway-host-observation/v1'
 observed_utc=(Get-Date).ToUniversalTime().ToString('o')
 mutable_actions=0
 credential_bytes_read=$false
 task=[ordered]@{
  present=[bool]$task
  enabled=if($task){[bool]$task.Settings.Enabled}else{$false}
  state=$taskState
  action_count=[int]$actions.Count
  binary_exists=[bool]$binaryExists
  binary_is_pythonw=[bool]$binaryIsPythonw
  python_probe_attempted=[bool]$pythonProbeAttempted
  python_probe_passed=[bool]$pythonProbePassed
  uses_isolated_flag=[bool]($argsText -cmatch '(?<!\S)-I(?!\S)')
  uses_no_bytecode_flag=[bool]($argsText -cmatch '(?<!\S)-B(?!\S)')
  targets_private_bootstrap=[bool]$bootstrapArgs
  native_retry_count=$nativeCount
  last_result=$lastResult
 }
 runtime=[ordered]@{
  dir_exists=[bool](Test-Path -LiteralPath $root -PathType Container)
  bootstrap_exists=[bool](Test-Path -LiteralPath $expectedBootstrap -PathType Leaf)
  supervisor_exists=[bool](Test-Path -LiteralPath (Join-Path $root 'supervisor.py') -PathType Leaf)
  transport_exists=[bool](Test-Path -LiteralPath (Join-Path $root 'transport-config.json') -PathType Leaf)
  ssh_config_exists=[bool](Test-Path -LiteralPath (Join-Path $root 'ssh-config') -PathType Leaf)
  source_files_count=[int]$sourceCount
 }
 ports=[ordered]@{
  readback_available=[bool]$portsFound
  loopback_gateway_listening=[bool]$gatewayListening
  loopback_tunnel_listening=[bool]$tunnelListening
  foreign_4000_listening=[bool]$foreign4000
 }
}|ConvertTo-Json -Depth 6 -Compress
"""


class PreflightInputError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _expect(condition: bool, code: str) -> None:
    if not condition:
        raise PreflightInputError(code)


def _exact_dict(value: object, keys: set[str]) -> dict:
    _expect(type(value) is dict and set(value) == keys, "OBSERVATION_FIELDS_INVALID")
    return value


def _flag(value: object) -> bool:
    _expect(type(value) is bool, "OBSERVATION_TYPE_INVALID")
    return value


def _number(value: object, *, optional: bool = False) -> int | None:
    if optional and value is None:
        return None
    _expect(type(value) is int and 0 <= value <= 2**32 - 1,
            "OBSERVATION_TYPE_INVALID")
    return value


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise PreflightInputError("DUPLICATE_JSON_KEY")
        result[name] = value
    return result


def parse(raw: bytes) -> dict:
    _expect(type(raw) is bytes and 0 < len(raw) <= 16384, "OBSERVATION_SIZE_INVALID")
    try:
        data = json.loads(raw.decode("utf-8"),
                          object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              PreflightInputError("NONFINITE_JSON_NUMBER")))
    except PreflightInputError:
        raise
    except (ValueError, UnicodeError):
        raise PreflightInputError("OBSERVATION_JSON_INVALID") from None
    _exact_dict(data, {
        "schema", "observed_utc", "mutable_actions", "credential_bytes_read",
        "task", "runtime", "ports",
    })
    _expect(data["schema"] == OBS_SCHEMA, "OBSERVATION_SCHEMA_INVALID")
    _expect(data["mutable_actions"] == 0 and type(data["mutable_actions"]) is int
            and data["credential_bytes_read"] is False,
            "OBSERVATION_EFFECT_CLAIM_INVALID")
    _expect(type(data["observed_utc"]) is str and
            len(data["observed_utc"]) <= 48,
            "OBSERVATION_TIME_INVALID")
    try:
        t = datetime.fromisoformat(data["observed_utc"].replace("Z", "+00:00"))
    except ValueError:
        raise PreflightInputError("OBSERVATION_TIME_INVALID") from None
    _expect(t.tzinfo is not None and t.utcoffset() is not None,
            "OBSERVATION_TIME_INVALID")
    task = _exact_dict(data["task"], {
        "present", "enabled", "state", "action_count", "binary_exists",
        "binary_is_pythonw", "python_probe_attempted",
        "python_probe_passed", "uses_isolated_flag", "uses_no_bytecode_flag",
        "targets_private_bootstrap", "native_retry_count", "last_result",
    })
    for k in ("present", "enabled", "binary_exists", "binary_is_pythonw",
              "python_probe_attempted", "python_probe_passed",
              "uses_isolated_flag", "uses_no_bytecode_flag", "targets_private_bootstrap"):
        _flag(task[k])
    _expect(type(task["state"]) is str and task["state"] in
            ("Running", "Ready", "Disabled", "Queued", "Unknown", "UNAVAILABLE"),
            "TASK_STATE_INVALID")
    _number(task["action_count"])
    _number(task["native_retry_count"], optional=True)
    _number(task["last_result"], optional=True)
    runtime = _exact_dict(data["runtime"], {
        "dir_exists", "bootstrap_exists", "supervisor_exists",
        "transport_exists", "ssh_config_exists", "source_files_count",
    })
    for k in ("dir_exists", "bootstrap_exists", "supervisor_exists",
              "transport_exists", "ssh_config_exists"):
        _flag(runtime[k])
    _expect(_number(runtime["source_files_count"]) <= 4,
            "RUNTIME_SOURCE_COUNT_INVALID")
    ports = _exact_dict(data["ports"], {
        "readback_available", "loopback_gateway_listening",
        "loopback_tunnel_listening", "foreign_4000_listening",
    })
    for k in ports:
        _flag(ports[k])
    return data


def assess(observation: dict) -> dict:
    """Return typed structural status only. Never grants production authority."""
    obs = parse(json.dumps(observation, separators=(",", ":")).encode("utf-8"))
    task = obs["task"]
    rt = obs["runtime"]
    ports = obs["ports"]
    failures = []
    def gap(code: str, condition: bool):
        if condition:
            failures.append(code)
    gap("SCHEDULED_TASK_MISSING", not task["present"])
    if task["present"]:
        gap("SCHEDULED_TASK_DISABLED", not task["enabled"])
        gap("SCHEDULED_TASK_NOT_RUNNING", task["state"] != "Running")
        gap("SCHEDULED_TASK_ACTION_COUNT_INVALID", task["action_count"] != 1)
        gap("SCHEDULED_TASK_BINARY_MISSING", not task["binary_exists"])
        gap("SCHEDULED_TASK_BINARY_NOT_PYTHONW", not task["binary_is_pythonw"])
        gap("TASK_INTERPRETER_STDLIB_PROBE_UNAVAILABLE",
            not task["python_probe_attempted"])
        gap("TASK_INTERPRETER_STDLIB_IMPORT_FAILED",
            task["python_probe_attempted"] and not task["python_probe_passed"])
        gap("SCHEDULED_TASK_PYTHON_ISOLATION_MISSING", not task["uses_isolated_flag"]
            or not task["uses_no_bytecode_flag"])
        gap("SCHEDULED_TASK_BOOTSTRAP_TARGET_DRIFT", not task["targets_private_bootstrap"])
        gap("SCHEDULED_TASK_NATIVE_RETRY_UNVERIFIED", task["native_retry_count"] is None)
        gap("SCHEDULED_TASK_NATIVE_RETRY_ENABLED",
            task["native_retry_count"] is not None and task["native_retry_count"] != 0)
        gap("HISTORIC_TASK_FILE_NOT_FOUND",
            task["last_result"] == 0x80070002)
    gap("PRIVATE_RUNTIME_DIRECTORY_MISSING", not rt["dir_exists"])
    gap("PRIVATE_BOOTSTRAP_MISSING", not rt["bootstrap_exists"])
    gap("PRIVATE_SUPERVISOR_MISSING", not rt["supervisor_exists"])
    gap("PRIVATE_TRANSPORT_CONFIG_MISSING", not rt["transport_exists"])
    gap("PRIVATE_SSH_CONFIG_MISSING", not rt["ssh_config_exists"])
    gap("PINNED_SOURCE_BUNDLE_INCOMPLETE", rt["source_files_count"] != 4)
    if not ports["readback_available"]:
        gap("LISTENER_READBACK_UNAVAILABLE", True)
    else:
        gap("GATEWAY_4001_NOT_OBSERVED", not ports["loopback_gateway_listening"])
        gap("OWNED_TUNNEL_19484_NOT_OBSERVED", not ports["loopback_tunnel_listening"])
    # The historical port-4000 owner is informational, not a failure or
    # invitation to adopt/terminate/reconfigure it.
    return {
        "schema": RESULT_SCHEMA,
        "observed_utc": obs["observed_utc"],
        "state": "HOLD" if failures else "STRUCTURAL_ONLY",
        "reason_count": len(failures),
        "reason_codes": sorted(set(failures)),
        "task_last_result": task["last_result"],
        "runtime_source_files_present": rt["source_files_count"],
        "foreign_4000_listener_observed": ports["foreign_4000_listening"],
        "source_sha_independently_verified": False,
        "signer_verified": False,
        "owned_child_pid_ancestry_verified": False,
        "fresh_signed_startup_receipt_verified": False,
        "authenticated_model_inference_verified": False,
        "production_authorized": False,
        "task_started_by_this_tool": False,
        "files_written_to_private_runtime": False,
        "credentials_read": False,
        "external_effects_performed": False,
    }


def collect_native() -> dict:
    if sys.platform != "win32":
        raise PreflightInputError("WINDOWS_HOST_REQUIRED")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-Command", WINDOWS_READBACK],
            capture_output=True, timeout=22, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PreflightInputError("WINDOWS_READBACK_UNAVAILABLE") from None
    if proc.returncode != 0:
        # Do not echo native errors: task metadata can contain file paths.
        raise PreflightInputError("WINDOWS_READBACK_UNAVAILABLE")
    return parse(proc.stdout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Windows VM gateway preflight; no credentials or task actions"
    )
    parser.add_argument("--output", type=Path,
                        help="Private, new receipt path (never the Git checkout)")
    args = parser.parse_args(argv)
    try:
        result = assess(collect_native())
        if args.output is not None:
            output = args.output
            root = Path(__file__).resolve().parent.parent.parent
            _expect(not output.exists() and not output.is_symlink()
                    and output.parent.is_dir()
                    and not output.resolve().is_relative_to(root),
                    "OUTPUT_PATH_DENIED")
            raw = (json.dumps(result, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("utf-8")
            with output.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        print(json.dumps({
            "state": result["state"], "reason_codes": result["reason_codes"],
            "production_authorized": False,
            "task_started_by_this_tool": False,
        }, sort_keys=True))
        return 2 if result["state"] == "HOLD" else 0
    except PreflightInputError as exc:
        code = exc.code
    except Exception:
        code = "PREFLIGHT_UNAVAILABLE"
    print(json.dumps({"state": "UNAVAILABLE", "code": code,
                      "production_authorized": False,
                      "task_started_by_this_tool": False}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
