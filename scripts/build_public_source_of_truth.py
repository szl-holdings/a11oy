#!/usr/bin/env python3
"""Build and validate the public a11oy/SZL source-of-truth contract.

External observations are optional and never inherited from an earlier output.
When a fresh observation is absent or malformed, the corresponding metric is
rendered as ``value: null`` and ``label: UNAVAILABLE``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = "szl.public-source-of-truth/v1"
LAMBDA_LIMITATION = "Never render as a theorem or verified trust state."
TERMINAL_STATES = {
    "VERIFIED",
    "REACHABLE",
    "DEGRADED",
    "STALE",
    "FAILED",
    "BLOCKED",
    "UNAVAILABLE",
}
METRIC_LABELS = {"MEASURED", "REPORTED", "UNAVAILABLE"}
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "v1" / "public-source-of-truth.schema.json"
MAX_OBSERVATION_AGE = dt.timedelta(minutes=15)
MAX_FUTURE_SKEW = dt.timedelta(minutes=1)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def canonical_timestamp(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def fresh_timestamp(value: Any, *, generated_at: dt.datetime) -> str | None:
    observed_at = parse_timestamp(value)
    if observed_at is None:
        return None
    if observed_at < generated_at - MAX_OBSERVATION_AGE:
        return None
    if observed_at > generated_at + MAX_FUTURE_SKEW:
        return None
    return canonical_timestamp(observed_at)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_snapshot(snapshot: Mapping[str, Any]) -> str:
    unsigned = dict(snapshot)
    unsigned.pop("digest_sha3_256", None)
    return hashlib.sha3_256(canonical_bytes(unsigned)).hexdigest()


def unavailable_metric(source: str) -> dict[str, Any]:
    return {"value": None, "label": "UNAVAILABLE", "observed_at": None, "source": source}


def is_finite_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (bool, str, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(is_finite_json_value(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and is_finite_json_value(item) for key, item in value.items())
    return False


def normalize_metric(raw: Any, *, source: str, generated_at: dt.datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return unavailable_metric(source)
    label = str(raw.get("label", "UNAVAILABLE")).upper()
    value = raw.get("value")
    observed_at = fresh_timestamp(raw.get("observed_at"), generated_at=generated_at)
    provided_source = raw.get("source")
    observed_source = provided_source.strip() if isinstance(provided_source, str) else ""
    if label not in METRIC_LABELS:
        return unavailable_metric(source)
    if label == "UNAVAILABLE":
        return unavailable_metric(observed_source or source)
    if not observed_source or value is None or not observed_at or not is_finite_json_value(value):
        return unavailable_metric(source)
    return {"value": value, "label": label, "observed_at": observed_at, "source": observed_source}


def normalize_observation(raw: Any, *, source: str, generated_at: dt.datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {"state": "UNAVAILABLE", "observed_at": None, "source": source, "detail": "No fresh observation was supplied."}
    state = str(raw.get("state", "UNAVAILABLE")).upper()
    observed_at = fresh_timestamp(raw.get("observed_at"), generated_at=generated_at)
    if state not in TERMINAL_STATES or not observed_at:
        return {"state": "UNAVAILABLE", "observed_at": None, "source": str(raw.get("source") or source), "detail": "Observation was missing a terminal state or timestamp."}
    return {"state": state, "observed_at": observed_at, "source": str(raw.get("source") or source), "detail": str(raw.get("detail") or "")}


def nested(mapping: Mapping[str, Any], *parts: str) -> Any:
    value: Any = mapping
    for part in parts:
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("observations root must be a JSON object")
    return data


def git_revision() -> str | None:
    candidate = os.getenv("GITHUB_SHA")
    if candidate and SHA_PATTERN.fullmatch(candidate):
        return candidate
    try:
        completed = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    candidate = completed.stdout.strip()
    return candidate if SHA_PATTERN.fullmatch(candidate) else None


def expected_aggregate_state(
    inventory: Any,
    runtime: Any,
    source_revision: Any,
) -> str:
    if not isinstance(source_revision, str) or not SHA_PATTERN.fullmatch(source_revision):
        return "DEGRADED"
    if not isinstance(inventory, Mapping) or not isinstance(runtime, Mapping):
        return "DEGRADED"
    public_contract = runtime.get("public_contract")
    if not isinstance(public_contract, Mapping) or public_contract.get("state") != "VERIFIED":
        return "DEGRADED"
    for section in inventory.values():
        if not isinstance(section, Mapping):
            return "DEGRADED"
        for metric in section.values():
            if not isinstance(metric, Mapping) or metric.get("label") == "UNAVAILABLE":
                return "DEGRADED"
    if any(not isinstance(item, Mapping) or item.get("state") != "VERIFIED" for item in runtime.values()):
        return "DEGRADED"
    return "VERIFIED"


def build_snapshot(*, observations: Mapping[str, Any], generated_at: str, source_revision: str | None, contract_verified: bool) -> dict[str, Any]:
    generated_time = parse_timestamp(generated_at)
    if generated_time is None:
        raise ValueError("generated_at must be a timezone-aware ISO 8601 timestamp")
    normalized_generated_at = canonical_timestamp(generated_time)

    def inventory_metric(section: str, name: str) -> dict[str, Any]:
        return normalize_metric(
            nested(observations, "inventory", section, name),
            source=f"observations.inventory.{section}.{name}",
            generated_at=generated_time,
        )

    runtime_raw = nested(observations, "runtime")
    runtime_raw = runtime_raw if isinstance(runtime_raw, Mapping) else {}
    runtime = {
        str(name): normalize_observation(
            value,
            source=f"observations.runtime.{name}",
            generated_at=generated_time,
        )
        for name, value in sorted(runtime_raw.items())
    }
    runtime["public_contract"] = {
        "state": "VERIFIED" if contract_verified else "UNAVAILABLE",
        "observed_at": normalized_generated_at if contract_verified else None,
        "source": "packages/public-evidence-ui + tests",
        "detail": "Contract tests passed in the current run." if contract_verified else "Contract verification was not asserted for this build.",
    }

    snapshot: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": normalized_generated_at,
        "source_revision": source_revision,
        "inventory": {
            "github": {
                "public_repositories": inventory_metric("github", "public_repositories"),
                "active_repositories": inventory_metric("github", "active_repositories"),
                "archived_repositories": inventory_metric("github", "archived_repositories"),
            },
            "huggingface": {
                "spaces_total": inventory_metric("huggingface", "spaces_total"),
                "spaces_public": inventory_metric("huggingface", "spaces_public"),
                "models": inventory_metric("huggingface", "models"),
                "datasets": inventory_metric("huggingface", "datasets"),
                "kernels": inventory_metric("huggingface", "kernels"),
                "collections": inventory_metric("huggingface", "collections"),
                "buckets": inventory_metric("huggingface", "buckets"),
            },
        },
        "runtime": runtime,
        "doctrine": {
            "version": "v11",
            "state": "LOCKED",
            "lambda_uniqueness": {"label": "CONJECTURE", "name": "Conjecture 1", "limitation": LAMBDA_LIMITATION},
        },
        "claim_classes": ["PROVED", "MEASURED", "REPORTED", "MODELED", "CONJECTURE", "ROADMAP", "UNAVAILABLE"],
        "remote_mutations": 0,
        "secret_values_read": False,
        "state": "DEGRADED",
    }

    snapshot["state"] = expected_aggregate_state(snapshot["inventory"], runtime, source_revision)
    snapshot["digest_sha3_256"] = digest_snapshot(snapshot)
    return snapshot


@lru_cache(maxsize=1)
def schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for violation in schema_validator().iter_errors(snapshot):
        path = ".".join(str(part) for part in violation.absolute_path) or "root"
        errors.append(f"json_schema:{path}")
    if snapshot.get("schema") != SCHEMA:
        errors.append("schema")
    source_revision = snapshot.get("source_revision")
    if source_revision is not None and not SHA_PATTERN.fullmatch(str(source_revision)):
        errors.append("source_revision")
    if snapshot.get("remote_mutations") != 0:
        errors.append("remote_mutations")
    if snapshot.get("secret_values_read") is not False:
        errors.append("secret_values_read")
    doctrine = snapshot.get("doctrine", {})
    lambda_info = doctrine.get("lambda_uniqueness", {}) if isinstance(doctrine, Mapping) else {}
    if not isinstance(doctrine, Mapping) or doctrine.get("version") != "v11":
        errors.append("doctrine_version")
    if not isinstance(doctrine, Mapping) or doctrine.get("state") != "LOCKED":
        errors.append("doctrine_state")
    if lambda_info.get("label") != "CONJECTURE" or lambda_info.get("name") != "Conjecture 1":
        errors.append("lambda_uniqueness")
    if lambda_info.get("limitation") != LAMBDA_LIMITATION:
        errors.append("lambda_uniqueness_limitation")
    digest = str(snapshot.get("digest_sha3_256", ""))
    if not DIGEST_PATTERN.fullmatch(digest) or digest != digest_snapshot(snapshot):
        errors.append("digest_sha3_256")
    inventory = snapshot.get("inventory", {})
    if not isinstance(inventory, Mapping):
        errors.append("inventory")
    else:
        for section in inventory.values():
            if not isinstance(section, Mapping):
                errors.append("inventory_section")
                continue
            for metric in section.values():
                if not isinstance(metric, Mapping):
                    errors.append("metric")
                    continue
                if metric.get("label") == "UNAVAILABLE" and metric.get("value") is not None:
                    errors.append("stale_unavailable_metric")
                if metric.get("label") not in METRIC_LABELS:
                    errors.append("metric_label")
                if not is_finite_json_value(metric.get("value")):
                    errors.append("non_finite_metric")
    runtime = snapshot.get("runtime", {})
    if not isinstance(runtime, Mapping):
        errors.append("runtime")
    else:
        for item in runtime.values():
            if not isinstance(item, Mapping) or item.get("state") not in TERMINAL_STATES:
                errors.append("runtime_state")
    generated_at = parse_timestamp(snapshot.get("generated_at"))
    if generated_at is None:
        errors.append("generated_at")
    else:
        if isinstance(inventory, Mapping):
            for section in inventory.values():
                if not isinstance(section, Mapping):
                    continue
                for metric in section.values():
                    if not isinstance(metric, Mapping) or metric.get("label") == "UNAVAILABLE":
                        continue
                    if fresh_timestamp(metric.get("observed_at"), generated_at=generated_at) is None:
                        errors.append("metric_freshness")
        if isinstance(runtime, Mapping):
            for item in runtime.values():
                if not isinstance(item, Mapping) or item.get("state") == "UNAVAILABLE":
                    continue
                if fresh_timestamp(item.get("observed_at"), generated_at=generated_at) is None:
                    errors.append("runtime_freshness")
    expected_state = expected_aggregate_state(inventory, runtime, source_revision)
    if snapshot.get("state") != expected_state:
        errors.append("aggregate_state")
    return sorted(set(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/public/SOURCE_OF_TRUTH.json"))
    parser.add_argument("--source-revision")
    parser.add_argument("--generated-at")
    parser.add_argument("--contract-verified", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        snapshot = json.loads(args.output.read_text(encoding="utf-8"))
    else:
        revision = args.source_revision or git_revision()
        if revision is not None and not SHA_PATTERN.fullmatch(revision):
            raise SystemExit("--source-revision must be a 40-character lowercase SHA")
        snapshot = build_snapshot(observations=load_json(args.observations), generated_at=args.generated_at or utc_now(), source_revision=revision, contract_verified=args.contract_verified)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    errors = validate_snapshot(snapshot)
    if errors:
        print(json.dumps({"state": "FAILED", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"state": "VERIFIED", "output": str(args.output), "snapshot_state": snapshot["state"], "digest_sha3_256": snapshot["digest_sha3_256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
