#!/usr/bin/env python3
"""Fail-closed qualification probe for the pinned SZL-Nemo Linux runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
import socket
import sys
import tempfile
import time
from pathlib import Path


EXPECTED_PACKAGES = {
    "torch": "2.10.0+cu128",
    "transformers": "4.48.3",
    "mamba-ssm": "2.3.2.post1",
    "causal-conv1d": "1.6.2.post1",
    "bitsandbytes": "0.49.2",
    "trl": "0.15.2",
    "peft": "0.14.0",
    "datasets": "3.2.0",
    "accelerate": "1.12.0",
    "tokenizers": "0.21.4",
    "huggingface-hub": "0.36.2",
}

EXPECTED_CUSTOM_CODE = {
    "configuration_nemotron_h.py": "07fa66e5b3da7e6a71c1a263e3dd68da11c8afa9178b47c49510ba628746fcff",
    "modeling_nemotron_h.py": "ea982af0b805f181573f919ecb001d5bbc0153459923cf4b2f1ccae194e415a4",
}

RECEIPT_PATH: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit(details: dict[str, object]) -> None:
    rendered = json.dumps(details, indent=2, sort_keys=True) + "\n"
    if RECEIPT_PATH is not None:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = RECEIPT_PATH.with_name(f".{RECEIPT_PATH.name}.{os.getpid()}.tmp")
        temporary.write_text(rendered, encoding="utf-8", newline="\n")
        os.replace(temporary, RECEIPT_PATH)
    print(rendered, end="")


def fail(reason: str, details: dict[str, object]) -> None:
    details.update({"status": "BLOCKED", "reason": reason})
    emit(details)
    raise SystemExit(3)


def network_namespace_evidence() -> dict[str, object]:
    interfaces = [name for _index, name in socket.if_nameindex()]
    route_path = Path("/proc/net/route")
    default_routes: list[dict[str, str]] = []
    if route_path.is_file():
        rows = route_path.read_text(encoding="utf-8").splitlines()[1:]
        for row in rows:
            columns = row.split()
            if len(columns) >= 8 and columns[1] == "00000000":
                default_routes.append(
                    {
                        "interface": columns[0],
                        "destination": columns[1],
                        "gateway": columns[2],
                        "flags": columns[3],
                    }
                )
    return {
        "interfaces": interfaces,
        "default_routes": default_routes,
        "isolated_no_default_route": not default_routes,
        "offline_environment": {
            name: os.environ.get(name)
            for name in (
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "HF_DATASETS_OFFLINE",
                "HF_HUB_DISABLE_TELEMETRY",
                "DO_NOT_TRACK",
            )
        },
    }


def main() -> None:
    global RECEIPT_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-snapshot", required=True, type=Path)
    parser.add_argument("--mode", choices=("imports", "config"), default="config")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    RECEIPT_PATH = args.receipt

    probe_path = Path(__file__).resolve()
    setup_path = probe_path.with_name("setup_wsl_runtime.sh")

    evidence: dict[str, object] = {
        "schema": "szl.nemo.wsl-runtime-probe.v1",
        "mode": args.mode,
        "base_snapshot": str(args.base_snapshot.resolve()),
        "observed_at_unix_s": int(time.time()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "network_namespace": network_namespace_evidence(),
        "training_started": False,
        "effects": {
            "weights_loaded": False,
            "model_instantiated": False,
            "network_access_permitted_by_probe": False,
            "artifacts_published": False,
            "external_mutations": [],
        },
        "source_sha256": {
            "probe": sha256(probe_path),
            "setup": sha256(setup_path) if setup_path.is_file() else None,
        },
    }

    namespace = evidence["network_namespace"]
    required_offline = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
    }
    observed_interfaces = set(namespace["interfaces"])  # type: ignore[index]
    observed_offline = namespace["offline_environment"]  # type: ignore[index]
    if not observed_interfaces.issubset({"lo"}):
        fail("NETWORK_NAMESPACE_HAS_NON_LOOPBACK_INTERFACE", evidence)
    if not namespace["isolated_no_default_route"]:  # type: ignore[index]
        fail("NETWORK_NAMESPACE_HAS_DEFAULT_ROUTE", evidence)
    for name, expected in required_offline.items():
        if observed_offline.get(name) != expected:  # type: ignore[union-attr]
            fail(f"OFFLINE_ENVIRONMENT_MISMATCH:{name}", evidence)

    if platform.system() != "Linux":
        fail("LINUX_REQUIRED", evidence)

    observed_packages: dict[str, str] = {}
    for package, expected in EXPECTED_PACKAGES.items():
        try:
            observed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            fail(f"MISSING_PACKAGE:{package}", evidence)
        observed_packages[package] = observed
        if observed != expected:
            evidence["packages"] = observed_packages
            fail(f"PACKAGE_VERSION_MISMATCH:{package}:{observed}!={expected}", evidence)
    evidence["packages"] = observed_packages

    code_hashes: dict[str, str] = {}
    for filename, expected in EXPECTED_CUSTOM_CODE.items():
        path = args.base_snapshot / filename
        if not path.is_file():
            fail(f"MISSING_PINNED_CODE:{filename}", evidence)
        observed = sha256(path)
        code_hashes[filename] = observed
        if observed != expected:
            evidence["custom_code_sha256"] = code_hashes
            fail(f"PINNED_CODE_HASH_MISMATCH:{filename}", evidence)
    evidence["custom_code_sha256"] = code_hashes

    module_cache = tempfile.TemporaryDirectory(prefix="szl-nemo-probe-hf-modules-")
    module_cache_path = Path(module_cache.name)
    if any(module_cache_path.iterdir()):
        fail("FRESH_DYNAMIC_MODULE_CACHE_NOT_EMPTY", evidence)
    os.environ["HF_MODULES_CACHE"] = str(module_cache_path)
    evidence["dynamic_module_cache"] = {
        "state": "FRESH_PROCESS_UNIQUE_CACHE",
        "initial_entry_count": 0,
        "lifecycle": "DELETED_WHEN_PROBE_EXITS",
        "source_policy": "PINNED_SNAPSHOT_HASH_VERIFIED_BEFORE_TRANSFORMERS_IMPORT",
    }

    try:
        import causal_conv1d
        import mamba_ssm
        import torch
        from mamba_ssm.ops.triton.layernorm_gated import rmsnorm_fn
        from mamba_ssm.ops.triton.ssd_combined import (
            mamba_chunk_scan_combined,
            mamba_split_conv1d_scan_combined,
        )
        from transformers import AutoConfig, AutoTokenizer
        from transformers.dynamic_module_utils import get_class_from_dynamic_module
    except Exception as exc:  # noqa: BLE001 - this is an evidence boundary
        fail(f"KERNEL_IMPORT_FAILED:{type(exc).__name__}:{exc}", evidence)

    evidence["cuda"] = {
        "available": torch.cuda.is_available(),
        "runtime": torch.version.cuda,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None,
        "free_total_bytes": list(torch.cuda.mem_get_info()) if torch.cuda.is_available() else None,
    }
    evidence["kernel_symbols"] = {
        "rmsnorm_fn": callable(rmsnorm_fn),
        "mamba_chunk_scan_combined": callable(mamba_chunk_scan_combined),
        "mamba_split_conv1d_scan_combined": callable(mamba_split_conv1d_scan_combined),
    }
    if not torch.cuda.is_available():
        fail("CUDA_NOT_VISIBLE", evidence)

    if args.mode == "imports":
        evidence["status"] = "PASS"
        module_cache.cleanup()
        emit(evidence)
        return

    try:
        config = AutoConfig.from_pretrained(
            args.base_snapshot,
            trust_remote_code=True,
            local_files_only=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            args.base_snapshot,
            trust_remote_code=True,
            local_files_only=True,
        )
    except Exception as exc:  # noqa: BLE001
        fail(f"PINNED_CONFIG_LOAD_FAILED:{type(exc).__name__}:{exc}", evidence)

    config_source = Path(inspect.getfile(type(config))).resolve()
    evidence["dynamic_module"] = {
        "config_class": f"{type(config).__module__}.{type(config).__qualname__}",
        "config_source": str(config_source),
        "config_source_sha256": sha256(config_source),
        "tokenizer_class": f"{type(tokenizer).__module__}.{type(tokenizer).__qualname__}",
        "hybrid_override_pattern": config.hybrid_override_pattern,
    }
    if evidence["dynamic_module"]["config_source_sha256"] != EXPECTED_CUSTOM_CODE["configuration_nemotron_h.py"]:  # type: ignore[index]
        fail("IMPORTED_CONFIG_SOURCE_HASH_MISMATCH", evidence)

    try:
        model_class = get_class_from_dynamic_module(
            config.auto_map["AutoModelForCausalLM"],
            str(args.base_snapshot),
            local_files_only=True,
        )
    except Exception as exc:  # noqa: BLE001
        fail(f"PINNED_MODEL_CLASS_IMPORT_FAILED:{type(exc).__name__}:{exc}", evidence)
    model_class_source = Path(inspect.getfile(model_class)).resolve()
    evidence["dynamic_module"].update(  # type: ignore[union-attr]
        {
            "model_class": f"{model_class.__module__}.{model_class.__qualname__}",
            "model_source": str(model_class_source),
            "model_source_sha256": sha256(model_class_source),
        }
    )
    if evidence["dynamic_module"]["model_source_sha256"] != EXPECTED_CUSTOM_CODE["modeling_nemotron_h.py"]:  # type: ignore[index]
        fail("IMPORTED_MODEL_SOURCE_HASH_MISMATCH", evidence)

    evidence["status"] = "PASS"
    module_cache.cleanup()
    emit(evidence)


if __name__ == "__main__":
    main()
